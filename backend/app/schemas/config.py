"""
统一配置 Schema 定义（Pydantic v2）

所有后端可配置项集中于此，对应 config.toml 的结构。
通过 app.core.config.load_config() 加载并校验后得到全局单例。

路径字段约定：
- 配置文件中可填写相对路径（相对于 backend/ 目录，即 config.toml 所在目录）或绝对路径
- Settings 构造时会自动将相对路径解析为绝对路径，使用方无需再处理
"""
from enum import Enum
from pathlib import Path

# from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# backend/ 目录的绝对路径（本文件位于 backend/app/schemas/config.py，向上两级）
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _resolve_to_backend(path_str: str) -> Path:
    """将相对路径解析为基于 backend/ 目录的绝对路径；绝对路径直接返回"""
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (_BACKEND_DIR / p).resolve()


# ─── 数据库 ───

class DatabaseType(str, Enum):
    sqlite = "sqlite"
    mysql = "mysql"


class DatabaseConfig(BaseModel):
    """数据库配置，默认 SQLite"""
    type: DatabaseType = DatabaseType.sqlite
    # SQLite 路径（相对路径基于 backend/ 目录）
    sqlite_path: str = "data/wordle.db"
    # MySQL
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    db: str = "wordle"
    charset: str = "utf8mb4"

    @property
    def sqlite_path_resolved(self) -> Path:
        """返回解析后的 SQLite 绝对路径"""
        return _resolve_to_backend(self.sqlite_path)


# ─── 管理员 / 鉴权 ───

class AuthConfig(BaseModel):
    """鉴权配置

    - admin_token_hash: 管理员 Token 的 SHA-256 摘要（hex），用于 /api/admin/* 接口
    - enabled: 是否开启全局 Token 鉴权（False 时直接放行所有请求）

    管理员 Token 摘要仍保存在配置中；玩家 Token 统一存储于数据库，无需文件配置。
    """
    enabled: bool = True
    admin_token_hash: str = ""


# ─── 游戏设置 ───

class DifficultySettings(BaseModel):
    """单难度游戏参数"""
    max_rounds: int = Field(..., ge=1, le=50, description="最大猜测轮数")
    candidate_count: int = Field(..., ge=4, le=50, description="候选字数量")
    max_hints: int = Field(2, ge=0, le=5, description="最大可用提示次数，不超过5")

    @field_validator("candidate_count")
    @classmethod
    def candidate_at_least_target(cls, v: int) -> int:
        if v < 4:
            raise ValueError("候选字数量不能少于4（目标成语字数）")
        return v


class GameConfig(BaseModel):
    """游戏全局设置，按难度分档"""
    easy: DifficultySettings = DifficultySettings(
        max_rounds=12, candidate_count=10, max_hints=2)
    medium: DifficultySettings = DifficultySettings(
        max_rounds=10, candidate_count=14, max_hints=2)
    hard: DifficultySettings = DifficultySettings(
        max_rounds=8, candidate_count=20, max_hints=2)


# ─── 成语库 ───

class IdiomLibraryConfig(BaseModel):
    """成语库路径配置（按难度）

    相对路径基于 backend/ 目录。
    """
    easy: str = "data/easy.json"
    medium: str = "data/medium.json"
    hard: str = "data/hard.json"
    # 干扰字库
    characters: str = "data/character.json"

    @property
    def easy_resolved(self) -> Path:
        return _resolve_to_backend(self.easy)

    @property
    def medium_resolved(self) -> Path:
        return _resolve_to_backend(self.medium)

    @property
    def hard_resolved(self) -> Path:
        return _resolve_to_backend(self.hard)

    @property
    def characters_resolved(self) -> Path:
        return _resolve_to_backend(self.characters)

    def all_paths(self) -> dict[str, Path]:
        """返回所有字库文件的绝对路径映射"""
        return {
            "easy": self.easy_resolved,
            "medium": self.medium_resolved,
            "hard": self.hard_resolved,
            "characters": self.characters_resolved,
        }


# ─── 日志 ───

class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = "INFO"
    # 日志文件目录，留空则仅输出到控制台
    dir: str = "logs"
    # 日志文件名
    filename: str = "app.log"
    # 按日期轮转保留的份数
    backup_count: int = 10

    @field_validator("level")
    @classmethod
    def normalize_level(cls, v: str) -> str:
        return v.upper()

    @property
    def dir_resolved(self) -> Path | None:
        """返回解析后的日志目录绝对路径；dir 为空时返回 None"""
        if not self.dir:
            return None
        return _resolve_to_backend(self.dir)


# ─── 安全 ───

class SecurityConfig(BaseModel):
    """安全相关配置

    - cors_origins: 允许的跨域来源列表，["*"] 表示全部
    - trusted_proxies: 可信任的代理来源 IP/CIDR 列表，仅当请求直连 IP 命中时才采信
      X-Forwarded-For / X-Real-IP 等头部获取客户端真实 IP；默认仅信任本机
    - admin_allowlist: 管理员接口白名单 IP/CIDR；为空列表时不做来源限制
    """
    cors_origins: list[str] = ["*"]
    trusted_proxies: list[str] = ["127.0.0.1"]
    admin_allowlist: list[str] = []


# ─── 垃圾清理 ───

class CleanupMode(str, Enum):
    """对局清理模式

    - all: 清理所有过期对局，不论状态
    - non_playing: 仅清理状态不为 playing 的过期对局（won / lost）
    """
    all = "all"
    non_playing = "non_playing"


class CleanupConfig(BaseModel):
    """垃圾清理配置

    - enabled: 是否开启后台自动清理
    - retention_days: 清理多少天前创建的对局
    - mode: 清理模式，all（清理所有过期对局）或 non_playing（仅清理非 playing 的过期对局）
    - interval_seconds: 后台清理任务的执行间隔（秒），默认每小时一次
    - run_on_startup: 是否在服务启动时执行一次清理
    """
    enabled: bool = True
    retention_days: int = Field(
        default=30, ge=1, le=3650, description="清理天数前创建的对局")
    mode: CleanupMode = CleanupMode.non_playing
    interval_seconds: int = Field(
        default=3600, ge=60, le=86400, description="后台清理间隔（秒）")
    run_on_startup: bool = True


# ─── 排行榜 ───

class LeaderboardConfig(BaseModel):
    """排行榜配置

    - min_games_to_upload: 允许上传排行榜的最低对局数（不论 daily/unlimited）
    - min_new_records_to_append: 追加战绩时至少需要的新记录数
    - inactive_days: 多少天未更新的存档将被自动清理
    - top_display_limit: 前端展示的名次上限（前 N 名）
    - cookie_name: 用于区分终端的 Cookie 名称
    - cookie_max_age_days: Cookie 有效期（天）
    """
    min_games_to_upload: int = Field(
        default=20, ge=1, le=10000, description="允许上传排行榜的最低对局数")
    min_new_records_to_append: int = Field(
        default=5, ge=1, le=1000, description="追加战绩时至少需要的新记录数")
    inactive_days: int = Field(
        default=90, ge=1, le=3650, description="不活跃存档清理天数")
    top_display_limit: int = Field(
        default=100, ge=1, le=500, description="前端展示的名次上限")
    cookie_name: str = "cw_lb_token"
    cookie_max_age_days: int = Field(
        default=365, ge=1, le=3650, description="Cookie 有效期（天）")


# ─── 前端配置 ───

class FrontMode(str, Enum):
    """前端启动模式"""
    default = "default"  # 静态服务器 + API 代理（同域部署）
    backend = "backend"  # 仅启动后端 API，不提供静态文件服务


class FrontendConfig(BaseModel):
    """前端服务配置

    - listen_host: 监听地址，格式为 "host" 或 "host:port"（默认端口 8000）
    - front_mode: 启动模式，default 或 backend
    - front_token: 前端 JS 中硬编码的 API Token
    """
    listen_host: str = "127.0.0.1"
    front_mode: FrontMode = FrontMode.default
    front_token: str = "test-token"

    @property
    def host(self) -> str:
        """解析获取主机名"""
        return self.listen_host.split(":")[0] if ":" in self.listen_host else self.listen_host

    @property
    def port(self) -> int:
        """解析获取端口号，默认 8000"""
        if ":" in self.listen_host:
            try:
                return int(self.listen_host.split(":")[1])
            except (ValueError, IndexError):
                return 8000
        return 8000

    @property
    def api_base_url(self) -> str:
        """返回用于 JS 替换的 API Base URL（不含协议头）"""
        host = self.host
        port = self.port
        # 默认端口简化显示
        if port in (80, 443):
            return host
        return f"{host}:{port}"


# ─── 顶层 ───

class Settings(BaseModel):
    """后端统一配置根模型"""
    database: DatabaseConfig = DatabaseConfig()
    auth: AuthConfig = AuthConfig()
    game: GameConfig = GameConfig()
    idiom_library: IdiomLibraryConfig = IdiomLibraryConfig()
    logging: LoggingConfig = LoggingConfig()
    security: SecurityConfig = SecurityConfig()
    cleanup: CleanupConfig = CleanupConfig()
    leaderboard: LeaderboardConfig = LeaderboardConfig()
    frontend: FrontendConfig = FrontendConfig()

    @model_validator(mode="after")
    def _check_admin_token_when_enabled(self) -> "Settings":
        """开启鉴权时，管理员接口若被访问，admin_token_hash 应非空（否则 reload-token 无法鉴权）。
        这里仅给出告警式校验：enabled=True 且 admin_token_hash 为空时提示。"""
        if self.auth.enabled and not self.auth.admin_token_hash:
            # 不抛错以免阻断启动（管理员接口可选），交由调用时处理
            pass
        return self

    @model_validator(mode="after")
    def _validate_paths(self) -> "Settings":
        """校验所有关键路径文件/目录是否存在，不存在则抛出明确错误。

        - 字库文件（easy/medium/hard/characters）：必须存在，否则无法出题
        - token 文件：仅当 auth.enabled=True 时必须存在
        - SQLite 路径：父目录需存在（自动创建）
        - 日志目录：自动创建
        """
        import logging
        log = logging.getLogger("uvicorn")

        # 1. 校验字库文件
        for name, path in self.idiom_library.all_paths().items():
            if not path.is_file():
                raise FileNotFoundError(
                    f"成语字库文件不存在：{path}（配置项 idiom_library.{name}）。"
                    f"请检查 config.toml 中的路径配置。"
                )
        log.debug("[Config] 字库文件校验通过")

        # 3. 确保 SQLite 父目录存在
        if self.database.type == DatabaseType.sqlite:
            db_path = self.database.sqlite_path_resolved
            db_path.parent.mkdir(parents=True, exist_ok=True)
            log.debug(f"[Config] SQLite 目录已确认：{db_path.parent}")

        # 4. 确保日志目录存在
        log_dir = self.logging.dir_resolved
        if log_dir is not None:
            log_dir.mkdir(parents=True, exist_ok=True)
            log.debug(f"[Config] 日志目录已确认：{log_dir}")

        return self
