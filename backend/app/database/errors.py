"""
数据库错误美化处理模块

将原始的数据库异常转换为用户友好的中文错误提示，
包含错误原因、诊断信息和解决建议。
"""
import logging
import sys
from typing import Optional, Tuple

# ANSI 颜色代码


class Colors:
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'


# MySQL 常见错误码映射
MYSQL_ERROR_CODES = {
    1045: {
        "title": "❌ 数据库访问被拒绝",
        "reason": "用户名或密码错误，认证失败",
        "suggestion": "请检查 config.toml 中 [database] 部分的 user 和 password 配置"
    },
    1049: {
        "title": "❌ 数据库不存在",
        "reason": "配置中指定的数据库尚未创建",
        "suggestion": "请先手动创建数据库，或在 MySQL 中执行: CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    },
    2003: {
        "title": "❌ 无法连接到数据库服务器",
        "reason": "数据库服务未启动或网络不可达",
        "suggestion": "1. 确认 MySQL 服务已启动\n2. 检查 host 和 port 配置是否正确\n3. 确认防火墙未阻止连接"
    },
    2005: {
        "title": "❌ 数据库主机地址错误",
        "reason": "无法解析配置的主机名或 IP 地址",
        "suggestion": "请检查 config.toml 中 [database] 的 host 配置"
    },
    2006: {
        "title": "❌ 数据库连接已断开",
        "reason": "MySQL 服务器已关闭连接",
        "suggestion": "检查 MySQL 服务状态，或增大 wait_timeout 配置"
    },
    2013: {
        "title": "❌ 数据库连接中断",
        "reason": "连接过程中网络中断或查询超时",
        "suggestion": "检查网络稳定性，或增大 connect_timeout 配置"
    },
    1007: {
        "title": "❌ 数据库已存在",
        "reason": "尝试创建已存在的数据库",
        "suggestion": "数据库已存在，无需重复创建"
    },
    1050: {
        "title": "❌ 数据表已存在",
        "reason": "尝试创建已存在的数据表",
        "suggestion": "数据表已存在，初始化将自动跳过"
    },
    1061: {
        "title": "❌ 索引已存在",
        "reason": "尝试创建已存在的索引",
        "suggestion": "索引已存在，将自动跳过"
    },
    1146: {
        "title": "❌ 数据表不存在",
        "reason": "查询时引用了不存在的数据表",
        "suggestion": "请先运行数据库初始化创建所需表结构"
    },
    1364: {
        "title": "❌ 字段缺少默认值",
        "reason": "插入数据时未为 NOT NULL 字段提供值",
        "suggestion": "检查代码中的插入逻辑，确保必填字段都有值"
    },
    1406: {
        "title": "❌ 数据过长",
        "reason": "插入的数据超出了字段定义的长度限制",
        "suggestion": "检查输入数据长度，或调整数据库字段长度定义"
    },
}

# SQLite 常见错误映射
SQLITE_ERROR_CODES = {
    1: {
        "title": "❌ SQL 语法错误或表不存在",
        "reason": "SQL 语句有语法问题，或引用的数据表尚未创建",
        "suggestion": "请先运行数据库初始化创建所需表结构"
    },
    5: {
        "title": "❌ 数据库被锁定",
        "reason": "数据库正被其他进程占用，无法获取写入锁",
        "suggestion": "1. 等待其他进程完成操作\n2. 检查是否有并发写入冲突\n3. 如无其他进程使用，可能是锁文件残留，可尝试重启程序"
    },
    8: {
        "title": "❌ 数据库文件只读",
        "reason": "数据库文件或目录没有写入权限",
        "suggestion": "请检查数据库文件和父目录的权限设置"
    },
    10: {
        "title": "❌ 磁盘 I/O 错误",
        "reason": "读写数据库文件时发生磁盘错误",
        "suggestion": "1. 检查磁盘是否有坏道\n2. 确认磁盘空间充足\n3. 检查文件系统权限"
    },
    11: {
        "title": "❌ 数据库文件已损坏",
        "reason": "数据库文件格式错误或磁盘损坏导致数据不可读",
        "suggestion": "如果数据库损坏，请从备份恢复，或删除数据库文件重新初始化"
    },
    13: {
        "title": "❌ 数据库文件无法打开",
        "reason": "文件路径不存在、权限不足或磁盘已满",
        "suggestion": "1. 检查数据库文件路径配置是否正确\n2. 确认程序对数据库目录有读写权限\n3. 检查磁盘剩余空间"
    },
    14: {
        "title": "❌ 数据库文件格式错误",
        "reason": "文件不是有效的 SQLite 数据库或已损坏",
        "suggestion": "如果数据库损坏，请从备份恢复，或删除数据库文件重新初始化"
    },
    19: {
        "title": "❌ 数据约束违反",
        "reason": "插入/更新操作违反了唯一约束、主键约束或非空约束",
        "suggestion": "检查是否有重复的主键或唯一字段值，以及必填字段是否为空"
    },
    21: {
        "title": "❌ 数据库对象类型误用",
        "reason": "对非表对象执行了表操作，或对象类型不匹配",
        "suggestion": "检查数据库表名和字段名是否正确"
    },
}


def _is_tty() -> bool:
    """检测是否在终端中运行（支持彩色输出）"""
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


def _c(text: str, color: str) -> str:
    """给文本添加颜色（仅在终端中生效）"""
    if not _is_tty():
        return text
    return f"{color}{text}{Colors.RESET}"


def format_database_error(
    error: Exception,
    db_type: str = "unknown",
    context: Optional[dict] = None
) -> Tuple[str, str, str]:
    """
    格式化数据库错误信息

    Args:
        error: 捕获到的异常对象
        db_type: 数据库类型 ("mysql" | "sqlite" | "unknown")
        context: 上下文信息（host, port, db 等配置）

    Returns:
        (title, reason, suggestion) 三元组
    """
    context = context or {}
    error_code = None
    error_msg = str(error)

    # 获取错误码（MySQL 和 SQLite 方式不同）
    if hasattr(error, 'args') and error.args:
        if isinstance(error.args[0], int):
            error_code = error.args[0]
            if len(error.args) > 1:
                error_msg = str(error.args[1])
        else:
            # SQLite 错误可能在 sqlite_errorcode 属性中
            error_code = getattr(error, 'sqlite_errorcode', None)

    # 针对 SQLite 错误消息进行模糊匹配
    if db_type.lower() == "sqlite" or "sqlite" in str(type(error)).lower():
        error_str = str(error).lower()
        if 'unable to open' in error_str or 'cannot open' in error_str:
            error_code = 13  # SQLITE_CANTOPEN
        elif 'readonly' in error_str or 'read-only' in error_str:
            error_code = 8   # SQLITE_READONLY
        elif 'database is locked' in error_str or 'database lock' in error_str:
            error_code = 5   # SQLITE_BUSY
        elif 'disk i/o' in error_str:
            error_code = 10  # SQLITE_IOERR
        elif 'constraint' in error_str or 'unique' in error_str:
            error_code = 19  # SQLITE_CONSTRAINT
        elif 'malformed' in error_str or 'database disk image' in error_str:
            error_code = 11  # SQLITE_CORRUPT
        elif 'no such table' in error_str:
            error_code = 1   # SQLITE_ERROR

    # 根据数据库类型选择错误码映射
    if db_type.lower() == "mysql" or "pymysql" in str(type(error)):
        error_map = MYSQL_ERROR_CODES
    elif db_type.lower() == "sqlite" or "sqlite" in str(type(error)):
        error_map = SQLITE_ERROR_CODES
    else:
        error_map = {**MYSQL_ERROR_CODES, **SQLITE_ERROR_CODES}

    # 查找匹配的错误信息
    default_info = {
        "title": "❌ 数据库操作失败",
        "reason": error_msg,
        "suggestion": "请检查数据库配置和服务状态后重试"
    }
    error_info = error_map.get(
        error_code, default_info) if error_code is not None else default_info

    title = error_info["title"]
    reason = error_info["reason"]
    suggestion = error_info["suggestion"]

    # 替换模板变量
    if "{db_name}" in suggestion:
        suggestion = suggestion.replace(
            "{db_name}", context.get("db", "unknown"))
    if "{host}" in suggestion:
        suggestion = suggestion.replace(
            "{host}", context.get("host", "unknown"))
    if "{port}" in suggestion:
        suggestion = suggestion.replace(
            "{port}", str(context.get("port", "3306")))

    # 特殊情况：连接错误时追加详细配置
    if error_code in (2003, 2005, 2006, 1045):
        host = context.get("host", "unknown")
        port = context.get("port", 3306)
        user = context.get("user", "unknown")
        reason = f"{reason}\n   连接信息: {user}@{host}:{port}"

    return title, reason, suggestion


def print_database_error(
    error: Exception,
    db_type: str = "unknown",
    context: Optional[dict] = None,
    exit_program: bool = True
) -> None:
    """
    打印美化后的数据库错误信息到终端

    Args:
        error: 捕获到的异常对象
        db_type: 数据库类型
        context: 上下文配置信息
        exit_program: 是否在打印后退出程序
    """
    title, reason, suggestion = format_database_error(error, db_type, context)

    # 构造输出
    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append(_c(title, Colors.RED + Colors.BOLD))
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  {_c('错误原因:', Colors.YELLOW)} {reason}")
    lines.append("")
    lines.append(f"  {_c('解决建议:', Colors.GREEN)}")
    for line in suggestion.split('\n'):
        stripped = line.strip()
        if stripped:
            # 检测是否为列表项（以数字开头）
            if stripped and stripped[0].isdigit() and '. ' in stripped[:5]:
                lines.append(f"    {stripped}")
            else:
                lines.append(f"    {stripped}")
    lines.append("")

    # 显示原始错误信息（调试用）
    if _is_tty():
        lines.append(
            f"  {_c('原始错误:', Colors.MAGENTA)} {type(error).__name__}: {error}")
        lines.append("")

    lines.append("=" * 60)

    # 输出
    print('\n'.join(lines), file=sys.stderr)

    # 记录到日志
    log = logging.getLogger('uvicorn')
    log.error(f"数据库错误: {title} | 原因: {reason}")

    if exit_program:
        sys.exit(1)


def wrap_database_errors(db_type: str = "unknown", context: Optional[dict] = None):
    """
    装饰器：自动捕获并美化函数中的数据库错误

    Usage:
        @wrap_database_errors("mysql", {"host": "localhost"})
        def connect():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 只包装数据库相关异常
                err_str = str(type(e))
                if 'pymysql' in err_str or 'sqlite' in err_str or 'MySQLdb' in err_str:
                    print_database_error(e, db_type, context)
                raise
        return wrapper
    return decorator
