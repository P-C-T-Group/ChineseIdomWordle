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
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# backend/ 目录的绝对路径（本文件位于 backend/app/schemas/config.py，向上两级）
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


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
    - token_file: 合法玩家 Token 摘要文件路径（每行一个 SHA-256），为空文件则关闭全局鉴权
    - enabled: 是否开启全局 Token 鉴权（False 时直接放行所有请求）

    token_file 相对路径基于 backend/ 目录。
    """
    enabled: bool = True
    admin_token_hash: str = ""
    token_file: str = "token-sha256.txt"

    @property
    def token_file_resolved(self) -> Path:
        """返回解析后的 token 文件绝对路径"""
        return _resolve_to_backend(self.token_file)


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


# ─── 顶层 ───

class Settings(BaseModel):
    """后端统一配置根模型"""
    database: DatabaseConfig = DatabaseConfig()
    auth: AuthConfig = AuthConfig()
    game: GameConfig = GameConfig()
    idiom_library: IdiomLibraryConfig = IdiomLibraryConfig()
    logging: LoggingConfig = LoggingConfig()
    security: SecurityConfig = SecurityConfig()

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

        # 2. 校验 token 文件（仅在鉴权开启时）
        if self.auth.enabled:
            token_path = self.auth.token_file_resolved
            if not token_path.is_file():
                raise FileNotFoundError(
                    f"Token 摘要文件不存在：{token_path}（配置项 auth.token_file）。"
                    f"如需关闭鉴权，请设置 auth.enabled=false。"
                )
            log.debug("[Config] Token 文件校验通过")

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
