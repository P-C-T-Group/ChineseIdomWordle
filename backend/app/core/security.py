"""
安全工具

- 判断 IP 是否在 IP/CIDR 列表内
- 根据可信代理配置从请求中提取客户端真实 IP
- 管理员接口白名单校验
"""
import ipaddress
from typing import Iterable

from fastapi import Request

from app.core.config import get_settings


def _ip_in_list(ip: str, allowlist: Iterable[str]) -> bool:
    """判断 IP 是否命中 IP/CIDR 列表中的任意一项"""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in allowlist:
        entry = entry.strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            else:
                if addr == ipaddress.ip_address(entry):
                    return True
        except ValueError:
            continue
    return False


def get_client_ip(request: Request) -> str:
    """获取客户端真实 IP

    仅当请求直连 IP（request.client.host）命中 trusted_proxies 时，
    才采信 X-Forwarded-For / X-Real-IP 头部；否则直接使用直连 IP。
    这样可防止客户端伪造转发头绕过 IP 限制。
    """
    direct_ip = request.client.host if request.client else "0.0.0.0"
    settings = get_settings()
    if not _ip_in_list(direct_ip, settings.security.trusted_proxies):
        return direct_ip

    # 可信代理：从头部分析析出最早一跳的真实客户端 IP
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        # X-Forwarded-For: client, proxy1, proxy2 —— 取第一个非空项
        for part in xff.split(","):
            part = part.strip()
            if part:
                return part
    xri = request.headers.get("X-Real-IP")
    if xri:
        return xri.strip()
    return direct_ip


def is_admin_allowed(request: Request) -> bool:
    """判断当前请求来源是否允许访问管理员接口

    admin_allowlist 为空时不做限制；非空时要求直连 IP 命中白名单。
    注意：此处用直连 IP 而非解析后的客户端 IP，因为管理员白名单
    通常是限制能直接打到后端的来源（如堡垒机/内网网段）。
    """
    settings = get_settings()
    allowlist = settings.security.admin_allowlist
    if not allowlist:
        return True
    direct_ip = request.client.host if request.client else "0.0.0.0"
    return _ip_in_list(direct_ip, allowlist)
