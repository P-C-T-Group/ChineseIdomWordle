"""
日志配置

根据统一配置（Settings.logging）构建 logging.config.dictConfig，
替代原先硬编码的 uvicorn_config.json。Uvicorn 启动时若通过
--log-config 传入 json 仍可工作，但本模块提供应用层统一配置入口，
使日志路径/级别可在 config.toml 中调整。
"""
import logging.config

from app.schemas.config import Settings


def setup_logging(settings: Settings) -> None:
    """根据配置初始化日志系统

    - 控制台输出始终启用（带颜色）
    - 当 logging.dir 非空时，额外写入按日期轮转的文件
    """
    log_cfg = settings.logging
    level = log_cfg.level

    # 日志目录路径已由 Settings 统一解析为绝对路径
    log_dir = log_cfg.dir_resolved
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
    log_file = str(log_dir / log_cfg.filename) if log_dir else None

    handlers: dict[str, dict[str, str | int | bool]] = {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    }
    uvicorn_handlers = ["default"]
    access_handlers = ["access"]

    if log_file:
        handlers["default_file"] = {
            "formatter": "default_no_color",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": log_file,
            "when": "midnight",
            "encoding": "utf-8",
            "backupCount": log_cfg.backup_count,
        }
        handlers["access_file"] = {
            "formatter": "access_no_color",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": log_file,
            "when": "midnight",
            "encoding": "utf-8",
            "backupCount": log_cfg.backup_count,
        }
        uvicorn_handlers.append("default_file")
        access_handlers.append("access_file")

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "[%(asctime)s] %(levelprefix)s %(message)s",
                "use_colors": None,
            },
            "access": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": "[%(asctime)s] %(levelprefix)s %(client_addr)s - '%(request_line)s' %(status_code)s",
                "use_colors": None,
            },
            "default_no_color": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "[%(asctime)s] %(levelprefix)s %(message)s",
                "use_colors": False,
            },
            "access_no_color": {
                "()": "uvicorn.logging.AccessFormatter",
                "fmt": "[%(asctime)s] %(levelprefix)s %(client_addr)s - '%(request_line)s' %(status_code)s",
                "use_colors": False,
            },
        },
        "handlers": handlers,
        "loggers": {
            "uvicorn": {"handlers": uvicorn_handlers, "level": level, "propagate": False},
            "uvicorn.error": {"level": level},
            "uvicorn.access": {"handlers": access_handlers, "level": level, "propagate": False},
        },
    }
    logging.config.dictConfig(config)
