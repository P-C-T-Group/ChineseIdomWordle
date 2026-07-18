"""
数据库管理器 - 抽象 SQLite 与 MySQL 差异，提供统一的游戏数据 CRUD 接口

配置来源：统一配置文件 config.toml（见 app.core.config），
敏感项可由环境变量覆盖。
"""
import json
import logging
import threading
from typing import Optional

from app.core.models import Game, CharFeedback, Difficulty, GameMode
from app.core.config import get_settings
from app.schemas.DB import DatabaseType

log = logging.getLogger('uvicorn')

# SQLite 连接锁（SQLite 需要串行写入）
_sqlite_lock = threading.Lock()


def get_config():
    """获取数据库配置（来自统一配置单例）"""
    return get_settings().database


def _get_sqlite_conn():
    """获取 SQLite 连接"""
    import sqlite3
    cfg = get_config()
    # 路径已由 Settings 统一解析为绝对路径，且父目录已自动创建
    db_path = cfg.sqlite_path_resolved
    conn = sqlite3.connect(str(db_path))
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
        "create_ip": game.create_ip,
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
        create_ip=row["create_ip"] if "create_ip" in row.keys() else "0.0.0.0",
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
