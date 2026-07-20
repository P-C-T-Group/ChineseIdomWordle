"""
IP 归属地查询器（基于 ip2region.xdb 离线数据库）

纯 Python 实现，将 xdb 文件整体加载到内存（约 11MB），单例模式，
查询效率在微秒级，无外部依赖。

数据格式：Country|Province|City|ISP|ISO-alpha2-code
本模块对外提供 get_region(ip) -> str，返回精简后的归属地描述。
"""
import io
import ipaddress
import threading
from pathlib import Path
from typing import Optional

from app.core.config import get_settings

# xdb 文件结构常量
_HEADER_INFO_LENGTH = 256
_VECTOR_INDEX_ROWS = 256
_VECTOR_INDEX_COLS = 256
_VECTOR_INDEX_SIZE = 8
_VECTOR_INDEX_LENGTH = 524288  # 256 * 256 * 8

# xdb 文件头偏移
_XDB_STRUCTURE_30 = 3
_XDB_IPV4_ID = 4
_XDB_IPV6_ID = 6


def _le_get_uint32(buff: bytes, offset: int) -> int:
    return (
        (buff[offset] & 0xFF)
        | ((buff[offset + 1] << 8) & 0xFF00)
        | ((buff[offset + 2] << 16) & 0xFF0000)
        | ((buff[offset + 3] << 24) & 0xFF000000)
    )


def _le_get_uint16(buff: bytes, offset: int) -> int:
    return (buff[offset] & 0xFF) | ((buff[offset + 1] << 8) & 0xFF00)


def _v4_sub_compare(ip1: bytes, buff: bytes, offset: int) -> int:
    """IPv4 比较：ip1 为大端序，xdb 索引中小端序存储，故反向比对"""
    j = offset + len(ip1) - 1
    for i in range(len(ip1)):
        i1, i2 = ip1[i], buff[j]
        if i1 < i2:
            return -1
        if i1 > i2:
            return 1
        j -= 1
    return 0


def _v6_sub_compare(ip1: bytes, buff: bytes, offset: int) -> int:
    """IPv6 比较：均为大端序，直接逐字节比较"""
    ip2 = buff[offset:offset + len(ip1)]
    if ip1 > ip2:
        return 1
    if ip1 < ip2:
        return -1
    return 0


class _IpSearcher:
    """xdb 查询器：将整个文件加载到内存，支持 IPv4/IPv6"""

    def __init__(self, db_path: str):
        with io.open(db_path, "rb") as f:
            self._buffer = f.read()
        self._parse_header()

    def _parse_header(self):
        header = self._buffer[:16]
        version = _le_get_uint16(header, 0)
        # xdb 3.0+ 在偏移 16 处有 ipVersion 字段
        if version >= _XDB_STRUCTURE_30:
            ip_version = _le_get_uint16(self._buffer, 16)
        else:
            ip_version = _XDB_IPV4_ID
        self._is_v6 = (ip_version == _XDB_IPV6_ID)
        self._byte_num = 16 if self._is_v6 else 4
        self._index_size = 38 if self._is_v6 else 14
        self._compare_fn = _v6_sub_compare if self._is_v6 else _v4_sub_compare

    def search(self, ip: str) -> str:
        try:
            ip_bytes = ipaddress.ip_address(ip).packed
        except ValueError:
            return ""

        if len(ip_bytes) != self._byte_num:
            return ""

        i0, i1 = ip_bytes[0], ip_bytes[1]
        idx = i0 * _VECTOR_INDEX_COLS * _VECTOR_INDEX_SIZE + i1 * _VECTOR_INDEX_SIZE
        offset = _HEADER_INFO_LENGTH + idx
        s_ptr = _le_get_uint32(self._buffer, offset)
        e_ptr = _le_get_uint32(self._buffer, offset + 4)
        if s_ptr == 0 or e_ptr == 0:
            return ""

        _bytes = len(ip_bytes)
        _d_bytes = _bytes << 1
        d_len, d_ptr = 0, 0
        l, h = 0, int((e_ptr - s_ptr) / self._index_size)
        while l <= h:
            m = (l + h) >> 1
            p = int(s_ptr + m * self._index_size)
            buff = self._buffer[p:p + self._index_size]
            if self._compare_fn(ip_bytes, buff, 0) < 0:
                h = m - 1
            elif self._compare_fn(ip_bytes, buff, _bytes) > 0:
                l = m + 1
            else:
                d_len = _le_get_uint16(buff, _d_bytes)
                d_ptr = _le_get_uint32(buff, _d_bytes + 2)
                break

        if d_len == 0:
            return ""
        return self._buffer[d_ptr:d_ptr + d_len].decode("utf-8")


# ─── 单例管理 ───

_searcher: Optional[_IpSearcher] = None
_searcher_lock = threading.Lock()


def _get_searcher() -> Optional[_IpSearcher]:
    """懒加载获取 IP 查询器单例"""
    global _searcher
    if _searcher is not None:
        return _searcher
    with _searcher_lock:
        if _searcher is not None:
            return _searcher
        # 默认 xdb 路径：项目根目录 data/ip2region.xdb
        db_path = Path(__file__).resolve(
        ).parent.parent.parent.parent / "data" / "ip2region.xdb"
        if not db_path.is_file():
            return None
        try:
            _searcher = _IpSearcher(str(db_path))
        except Exception:
            return None
        return _searcher


def _format_region(raw: str) -> str:
    """将原始 'Country|Province|City|ISP|Code' 格式精简为可展示文本"""
    if not raw:
        return "未知"
    parts = raw.split("|")
    # 补齐为 5 段
    while len(parts) < 5:
        parts.append("0")
    country, province, city, isp, _code = parts[:5]

    # 保留原始字段中的 0 表示无数据
    if country in ("0", "Reserved"):
        return "内网/保留地址"
    if country != "中国":
        return country

    # 中国地址：省+市（若市为 0 或与省相同则省略）
    result = country
    if province and province != "0":
        result = province
        if city and city != "0" and city != province:
            result = f"{province}{city}"
    return result


def get_region(ip: str) -> str:
    """查询 IP 的归属地，返回精简后的可展示文本。

    查询失败或无数据时返回 '未知'。
    内网/保留地址返回 '内网/保留地址'。
    """
    if not ip:
        return "未知"
    searcher = _get_searcher()
    if searcher is None:
        return "未知"
    try:
        raw = searcher.search(ip)
    except Exception:
        return "未知"
    return _format_region(raw)
