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
from app.schemas.config import CleanupMode

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


# ─── Token 管理 ───

import json
from datetime import datetime
from typing import Optional, List, Dict, Any


def _now_iso() -> str:
    return datetime.utcnow().isoformat(sep=' ', timespec='seconds')


def clean_expired_tokens() -> None:
    """清理数据库中过期的 token（valid_until < now）。"""
    cfg = get_config()
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                conn.execute("DELETE FROM tokens WHERE valid_until IS NOT NULL AND valid_until < datetime('now')")
                conn.commit()
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM tokens WHERE valid_until IS NOT NULL AND valid_until < NOW()")
            conn.commit()
        finally:
            conn.close()


def clean_old_games(retention_days: int, mode: CleanupMode = CleanupMode.non_playing) -> int:
    """清理指定天数前创建的对局，返回被删除的对局数量。

    - retention_days: 清理多少天前创建的对局
    - mode: CleanupMode.all 清理所有过期对局，不论状态；
            CleanupMode.non_playing 仅清理非 playing 状态（won / lost）的过期对局
    """
    cfg = get_config()
    ph = _placeholder()
    # 根据模式构造 WHERE 条件
    if mode == CleanupMode.non_playing:
        status_clause = "AND game_status <> " + ph
        params = [retention_days, "playing"]
    else:
        status_clause = ""
        params = [retention_days]

    deleted = 0
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                sql = f"DELETE FROM games WHERE create_time < datetime('now', '-' || ? || ' days') {status_clause}"
                cursor = conn.execute(sql, params)
                deleted = cursor.rowcount
                conn.commit()
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                sql = f"DELETE FROM games WHERE create_time < DATE_SUB(NOW(), INTERVAL %s DAY) {status_clause}"
                cursor.execute(sql, params)
                deleted = cursor.rowcount
            conn.commit()
        finally:
            conn.close()
    log.info(f"[Cleanup] 清理过期对局: 保留天数={retention_days}, 模式={mode.value}, 删除数量={deleted}")
    return deleted


def list_tokens() -> List[Dict[str, Any]]:
    """列出数据库中所有 token 及其属性（返回字典列表）。"""
    clean_expired_tokens()
    cfg = get_config()
    results: List[Dict[str, Any]] = []
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                cursor = conn.execute("SELECT id, sha256hash, create_time, creator_ip, valid_until, whitelist_ips, last_call_time FROM tokens")
                rows = cursor.fetchall()
                for r in rows:
                    results.append({
                        "id": r[0],
                        "sha256hash": r[1],
                        "create_time": r[2],
                        "creator_ip": r[3],
                        "valid_until": r[4],
                        "whitelist_ips": json.loads(r[5]) if r[5] else [],
                        "last_call_time": r[6],
                    })
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, sha256hash, create_time, creator_ip, valid_until, whitelist_ips, last_call_time FROM tokens")
                rows = cursor.fetchall()
                for r in rows:
                    results.append({
                        "id": r['id'],
                        "sha256hash": r['sha256hash'],
                        "create_time": r['create_time'],
                        "creator_ip": r.get('creator_ip', ''),
                        "valid_until": r.get('valid_until'),
                        "whitelist_ips": json.loads(r.get('whitelist_ips') or '[]'),
                        "last_call_time": r.get('last_call_time'),
                    })
        finally:
            conn.close()
    return results


def get_token_by_hash(sha256hash: str) -> Optional[Dict[str, Any]]:
    """按 sha256 摘要查询 token（若不存在或已过期则返回 None）。返回包含全部字段的 dict。"""
    clean_expired_tokens()
    cfg = get_config()
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                cursor = conn.execute("SELECT id, sha256hash, create_time, creator_ip, valid_until, whitelist_ips, last_call_time FROM tokens WHERE sha256hash = ?", (sha256hash,))
                r = cursor.fetchone()
                if not r:
                    return None
                return {
                    "id": r[0],
                    "sha256hash": r[1],
                    "create_time": r[2],
                    "creator_ip": r[3],
                    "valid_until": r[4],
                    "whitelist_ips": json.loads(r[5]) if r[5] else [],
                    "last_call_time": r[6],
                }
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, sha256hash, create_time, creator_ip, valid_until, whitelist_ips, last_call_time FROM tokens WHERE sha256hash = %s", (sha256hash,))
                r = cursor.fetchone()
                if not r:
                    return None
                return {
                    "id": r['id'],
                    "sha256hash": r['sha256hash'],
                    "create_time": r['create_time'],
                    "creator_ip": r.get('creator_ip', ''),
                    "valid_until": r.get('valid_until'),
                    "whitelist_ips": json.loads(r.get('whitelist_ips') or '[]'),
                    "last_call_time": r.get('last_call_time'),
                }
        finally:
            conn.close()


def add_token(sha256hash: str, creator_ip: str = "", valid_until: Optional[str] = None, whitelist_ips: Optional[List[str]] = None) -> int:
    """添加或更新一个 token，返回插入/存在的 token id。

    - whitelist_ips: 列表，将以 JSON 字符串存储；空或 None 表示不限制 IP。
    - valid_until: ISO 时间字符串（UTC）或 None 表示长期有效。

    管理员 Token（配置中的摘要）禁止写入数据库以避免重复或冲突。
    """
    # 防止管理员 token 被写入数据库（无论哪个入口）
    try:
        admin_hash = get_settings().auth.admin_token_hash
    except Exception:
        admin_hash = None
    if admin_hash and sha256hash == admin_hash:
        raise ValueError("管理员 Token 禁止写入数据库")

    cfg = get_config()
    whitelist_json = json.dumps(whitelist_ips or [], ensure_ascii=False)
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                # 尝试插入，若存在则更新字段（保持唯一性并更新属性）
                conn.execute(
                    "INSERT INTO tokens (sha256hash, creator_ip, valid_until, whitelist_ips) VALUES (?, ?, ?, ?) ON CONFLICT(sha256hash) DO UPDATE SET valid_until=excluded.valid_until, whitelist_ips=excluded.whitelist_ips, creator_ip=excluded.creator_ip",
                    (sha256hash, creator_ip, valid_until, whitelist_json),
                )
                conn.commit()
                # 查询 id 返回
                cursor = conn.execute("SELECT id FROM tokens WHERE sha256hash = ?", (sha256hash,))
                row = cursor.fetchone()
                return row[0]
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO tokens (sha256hash, creator_ip, valid_until, whitelist_ips) VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE valid_until=VALUES(valid_until), whitelist_ips=VALUES(whitelist_ips), creator_ip=VALUES(creator_ip)",
                    (sha256hash, creator_ip, valid_until, whitelist_json),
                )
                conn.commit()
                cursor.execute("SELECT id FROM tokens WHERE sha256hash = %s", (sha256hash,))
                row = cursor.fetchone()
                return row['id']
        finally:
            conn.close()


def update_last_call_time(token_id: int) -> None:
    """更新 token 的 last_call_time 为当前 UTC 时间（ISO 格式）。"""
    cfg = get_config()
    now = _now_iso()
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                conn.execute("UPDATE tokens SET last_call_time = ? WHERE id = ?", (now, token_id))
                conn.commit()
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE tokens SET last_call_time = NOW() WHERE id = %s", (token_id,))
            conn.commit()
        finally:
            conn.close()


def delete_token(identifier: str) -> int:
    """删除指定 token，返回删除的行数（0 表示未找到）。

    identifier 的识别顺序（避免歧义）：
    1. 若以 "sha:" 或 "raw:" 为前缀，分别强制按 sha256 摘要 / token 原文处理；
    2. 若以 "id:" 为前缀，强制按数字 id 处理；
    3. 否则若能解析为纯整数，则按 id 删除；
    4. 否则若匹配 64 位十六进制，则按 sha256 摘要删除；
    5. 其余情况按 token 原文计算 sha256 后删除。
    """
    import hashlib
    import re

    if not isinstance(identifier, str):
        identifier = str(identifier)
    identifier = identifier.strip()
    if not identifier:
        return 0

    # 显式前缀优先，避免歧义
    if identifier.startswith("sha:"):
        mode, value = "sha", identifier[4:].strip()
    elif identifier.startswith("raw:"):
        mode, value = "raw", identifier[4:].strip()
    elif identifier.startswith("id:"):
        mode, value = "id", identifier[3:].strip()
    elif re.fullmatch(r"\d+", identifier):
        mode, value = "id", identifier
    elif re.fullmatch(r"[0-9a-fA-F]{64}", identifier):
        mode, value = "sha", identifier
    else:
        mode, value = "raw", identifier

    target_id = None
    target_sha = None
    if mode == "id":
        try:
            target_id = int(value)
        except Exception:
            return 0
    elif mode == "sha":
        if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            return 0
        target_sha = value.lower()
    else:  # raw
        target_sha = hashlib.sha256(value.encode("utf-8")).hexdigest()

    cfg = get_config()
    ph = _placeholder()
    deleted = 0
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                if target_id is not None:
                    cursor = conn.execute("DELETE FROM tokens WHERE id = ?", (target_id,))
                else:
                    cursor = conn.execute("DELETE FROM tokens WHERE sha256hash = ?", (target_sha,))
                deleted = cursor.rowcount
                conn.commit()
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                if target_id is not None:
                    cursor.execute("DELETE FROM tokens WHERE id = %s", (target_id,))
                else:
                    cursor.execute("DELETE FROM tokens WHERE sha256hash = %s", (target_sha,))
                deleted = cursor.rowcount
            conn.commit()
        finally:
            conn.close()
    return deleted


# 兼容旧接口：保留名称以最小化改动
def get_token_hashes() -> list[str]:
    return [t['sha256hash'] for t in list_tokens()]


def add_token_hash(sha256hash: str, creator_ip: str = "") -> None:
    add_token(sha256hash, creator_ip)