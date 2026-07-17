from enum import Enum
from pydantic import BaseModel


class DatabaseType(str, Enum):
    sqlite = "sqlite"
    mysql = "mysql"


class DBConnection(BaseModel):
    enabled: bool = False
    type: DatabaseType = DatabaseType.sqlite
    # SQLite 配置
    sqlite_path: str = "data/wordle.db"
    # MySQL 配置
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    db: str = "wordle"
    charset: str = "utf8mb4"
