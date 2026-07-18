"""
统一配置加载器

- 读取 config.toml（默认 backend/config.toml）
- 支持环境变量覆盖敏感项（DB_PASSWORD 等），便于部署时注入密钥
- 提供全局单例 get_settings() 供各模块访问

Python 3.11+ 内置 tomllib；3.10 需安装 tomli。
"""
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from app.schemas.config import Settings, DatabaseType

# TOML 读取库兼容（3.11+ 内置）
if sys.version_info >= (3, 11):
    import tomllib as _toml_lib
else:  # pragma: no cover
    try:
        import tomli as _toml_lib
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "读取 TOML 配置需要 Python 3.11+ 或安装 tomli（pip install tomli）"
        ) from e

# 默认配置文件位置：backend/config.toml（相对本文件向上两级）
_DEFAULT_CONFIG_PATH = Path(__file__).resolve(
).parent.parent.parent / "config.toml"

# 环境变量覆盖项映射：(env_name, settings_path_tuple, cast_fn)
# settings_path_tuple 用点号拆分定位到 Settings 内的字段
_ENV_OVERRIDES = [
    # 数据库
    ("WORDLE_DB_TYPE", ("database", "type"), lambda v: DatabaseType(v.lower())),
    ("WORDLE_DB_SQLITE_PATH", ("database", "sqlite_path"), str),
    ("WORDLE_DB_HOST", ("database", "host"), str),
    ("WORDLE_DB_PORT", ("database", "port"), int),
    ("WORDLE_DB_USER", ("database", "user"), str),
    ("WORDLE_DB_PASSWORD", ("database", "password"), str),
    ("WORDLE_DB_NAME", ("database", "db"), str),
    ("WORDLE_DB_CHARSET", ("database", "charset"), str),
    # 鉴权
    ("WORDLE_AUTH_ENABLED", ("auth", "enabled"),
     lambda v: v.lower() in ("1", "true", "yes")),
    ("WORDLE_ADMIN_TOKEN_HASH", ("auth", "admin_token_hash"), str),
    ("WORDLE_AUTH_TOKEN_FILE", ("auth", "token_file"), str),
    # 日志
    ("WORDLE_LOG_LEVEL", ("logging", "level"), str),
    ("WORDLE_LOG_DIR", ("logging", "dir"), str),
]

_settings_lock = threading.Lock()
_settings: Optional[Settings] = None
_config_path: Path = _DEFAULT_CONFIG_PATH


def set_config_path(path: str | Path) -> None:
    """指定配置文件路径（测试或自定义部署用），需在首次 get_settings() 前调用"""
    global _config_path, _settings
    _config_path = Path(path)
    _settings = None  # 重置缓存


def _read_toml(path: Path) -> dict:
    """读取 TOML 文件为 dict；文件不存在时返回空 dict（全部使用默认值）"""
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return _toml_lib.load(f)


def _apply_env_overrides(data: dict) -> dict:
    """将环境变量覆盖项合并进 TOML 解析出的 dict"""
    data = dict(data)  # 浅拷贝顶层，避免修改原始
    for env_name, path_tuple, cast in _ENV_OVERRIDES:
        env_val = os.environ.get(env_name)
        if env_val is None:
            continue
        # 逐层进入 dict
        cursor = data
        for key in path_tuple[:-1]:
            if key not in cursor or not isinstance(cursor[key], dict):
                cursor[key] = {}
            cursor = cursor[key]
        cursor[path_tuple[-1]] = cast(env_val)
    return data


def load_config() -> Settings:
    """加载并校验配置，返回 Settings 实例"""
    raw = _read_toml(_config_path)
    raw = _apply_env_overrides(raw)
    return Settings(**raw)


def get_settings() -> Settings:
    """获取全局配置单例（线程安全，首次调用时加载）"""
    global _settings
    if _settings is None:
        with _settings_lock:
            if _settings is None:
                _settings = load_config()
    return _settings


def reload_settings() -> Settings:
    """强制重新加载配置（用于测试或热重载场景）"""
    global _settings
    with _settings_lock:
        _settings = load_config()
    return _settings
