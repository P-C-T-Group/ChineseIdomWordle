"""
数据库管理器 - 抽象 SQLite 与 MySQL 差异，提供统一的游戏数据 CRUD 接口

配置读取优先级（环境变量 DB_TYPE / DB_SQLITE_PATH / DB_HOST 等）：
  - DB_TYPE=sqlite（默认）: 使用本地 SQLite 文件，DB_SQLITE_PATH 指定路径
  - DB_TYPE=mysql: 使用 MySQL，需配置 DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME
"""
import json
import logging
import os
import threading
from typing import Optional

from app.core.models import Game, CharFeedback, Difficulty, GameMode
from app.schemas.DB import DBConnection, DatabaseType

log = logging.getLogger('uvicorn')

# 全局配置实例
_config: Optional[DBConnection] = None
# SQLite 连接锁（SQLite 需要串行写入）
_sqlite_lock = threading.Lock()


def _load_config() -> DBConnection:
    """从环境变量加载数据库配置"""
    db_type = os.environ.get("DB_TYPE", "sqlite").lower()
    if db_type == "mysql":
        cfg = DBConnection(
            enabled=True,
            type=DatabaseType.mysql,
            host=os.environ.get("DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("DB_PORT", "3306")),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", ""),
            db=os.environ.get("DB_NAME", "wordle"),
            charset=os.environ.get("DB_CHARSET", "utf8mb4"),
        )
    else:
        cfg = DBConnection(
            enabled=True,
            type=DatabaseType.sqlite,
            sqlite_path=os.environ.get("DB_SQLITE_PATH", "data/wordle.db"),
        )
    return cfg


def get_config() -> DBConnection:
    global _config
    if _config is None:
        _config = _load_config()
    return _config


def _get_sqlite_conn():
    """获取 SQLite 连接"""
    import sqlite3
    cfg = get_config()
    db_path = cfg.sqlite_path
    # 确保目录存在
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_mysql_conn():
    """获取 MySQL 连接"""
    import pymysql
    cfg = get_config()
    return pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.db,
        charset=cfg.charset,
        cursorclass=pymysql.cursors.DictCursor,
    )


def _get_conn():
    """根据配置获取数据库连接"""
    cfg = get_config()
    if cfg.type == DatabaseType.mysql:
        return _get_mysql_conn()
    return _get_sqlite_conn()


def _placeholder() -> str:
    """返回当前数据库的参数占位符"""
    cfg = get_config()
    if cfg.type == DatabaseType.mysql:
        return "%s"
    return "?"


# ─── 序列化 / 反序列化 ───

def _serialize_game(game: Game) -> dict:
    """将 Game 对象序列化为可存入数据库的字典"""
    return {
        "game_id": game.game_id,
        "create_time": None,  # 由数据库自动填充
        "create_ip": "0.0.0.0",
        "mode": game.mode.value,
        "difficulty": game.difficulty.value,
        "max_rounds": game.max_rounds,
        "candidate_chars": json.dumps(game.candidate_chars, ensure_ascii=False),
        "target_idiom": game.target_idiom,
        "target_pinyin": game.target_pinyin,
        "target_explanation": game.target_explanation,
        "guesses": json.dumps(
            [[fb.model_dump() for fb in row] for row in game.guesses],
            ensure_ascii=False,
        ),
        "game_status": game.game_status,
        "round": game.round,
        "hints_used": game.hints_used,
        "max_hints": game.max_hints,
        "revealed_pinyins": json.dumps(game.revealed_pinyins, ensure_ascii=False),
    }


def _deserialize_game(row) -> Game:
    """从数据库行还原 Game 对象"""
    def _loads(raw, default):
        if raw is None:
            return default
        if isinstance(raw, str):
            return json.loads(raw)
        return raw  # SQLite 可能已经解析

    return Game(
        game_id=row["game_id"],
        mode=GameMode(row["mode"]),
        difficulty=Difficulty(row["difficulty"]),
        max_rounds=row["max_rounds"],
        candidate_chars=_loads(row["candidate_chars"], []),
        target_idiom=row["target_idiom"],
        target_pinyin=row["target_pinyin"],
        target_explanation=row["target_explanation"] if "target_explanation" in row.keys() else "",
        guesses=[
            [CharFeedback(**fb) for fb in row_data]
            for row_data in _loads(row["guesses"], [])
        ],
        game_status=row["game_status"],
        round=row["round"],
        hints_used=row["hints_used"],
        max_hints=row["max_hints"],
        revealed_pinyins=_loads(row["revealed_pinyins"], []),
    )


# ─── CRUD 接口 ───

def save_game(game: Game) -> None:
    """保存（或更新）一局游戏到数据库"""
    cfg = get_config()
    ph = _placeholder()
    data = _serialize_game(game)
    # 去掉 create_time（由数据库管理）
    data.pop("create_time")

    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                conn.execute(
                    f"""
                    INSERT INTO games ({', '.join(data.keys())}, create_time)
                    VALUES ({', '.join([ph] * len(data))}, datetime('now'))
                    ON CONFLICT(game_id) DO UPDATE SET
                        {', '.join(f"{k}=excluded.{k}" for k in data.keys() if k != 'game_id')}
                    """,
                    list(data.values()),
                )
                conn.commit()
            except Exception as err:
                conn.rollback()
                log.error(f"[DB] 保存游戏失败: {err}")
                raise
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                # MySQL 使用 INSERT ... ON DUPLICATE KEY UPDATE
                columns = list(data.keys())
                placeholders = ", ".join([ph] * len(columns))
                col_str = ", ".join(columns)
                update_str = ", ".join(
                    f"{c}=VALUES({c})" for c in columns if c != "game_id"
                )
                sql = (
                    f"INSERT INTO games ({col_str}) VALUES ({placeholders}) "
                    f"ON DUPLICATE KEY UPDATE {update_str}"
                )
                cursor.execute(sql, list(data.values()))
            conn.commit()
        except Exception as err:
            conn.rollback()
            log.error(f"[DB] 保存游戏失败: {err}")
            raise
        finally:
            conn.close()


def load_game(game_id: str) -> Optional[Game]:
    """从数据库加载一局游戏，不存在则返回 None"""
    ph = _placeholder()
    cfg = get_config()

    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                cursor = conn.execute(
                    f"SELECT * FROM games WHERE game_id = {ph}",
                    (game_id,),
                )
                row = cursor.fetchone()
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT * FROM games WHERE game_id = {ph}",
                    (game_id,),
                )
                row = cursor.fetchone()
        finally:
            conn.close()

    if row is None:
        return None
    return _deserialize_game(row)


def game_exists(game_id: str) -> bool:
    """判断游戏是否存在"""
    return load_game(game_id) is not None
