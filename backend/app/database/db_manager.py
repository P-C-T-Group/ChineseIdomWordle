"""
数据库管理器 - 抽象 SQLite 与 MySQL 差异，提供统一的游戏数据 CRUD 接口

配置来源：统一配置文件 config.toml（见 app.core.config），
敏感项可由环境变量覆盖。
"""
import json
import logging
import secrets
import string
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any

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
        target_explanation=row["target_explanation"] if "target_explanation" in row.keys(
        ) else "",
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


def _now_iso() -> str:
    return datetime.utcnow().isoformat(sep=' ', timespec='seconds')


def clean_expired_tokens() -> None:
    """清理数据库中过期的 token（valid_until < now）。"""
    cfg = get_config()
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                conn.execute(
                    "DELETE FROM tokens WHERE valid_until IS NOT NULL AND valid_until < datetime('now')")
                conn.commit()
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM tokens WHERE valid_until IS NOT NULL AND valid_until < NOW()")
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
    log.info(
        f"[Cleanup] 清理过期对局: 保留天数={retention_days}, 模式={mode.value}, 删除数量={deleted}")
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
                cursor = conn.execute(
                    "SELECT id, sha256hash, create_time, creator_ip, valid_until, whitelist_ips, last_call_time FROM tokens")
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
                cursor.execute(
                    "SELECT id, sha256hash, create_time, creator_ip, valid_until, whitelist_ips, last_call_time FROM tokens")
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
                cursor = conn.execute(
                    "SELECT id, sha256hash, create_time, creator_ip, valid_until, whitelist_ips, last_call_time FROM tokens WHERE sha256hash = ?", (sha256hash,))
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
                cursor.execute(
                    "SELECT id, sha256hash, create_time, creator_ip, valid_until, whitelist_ips, last_call_time FROM tokens WHERE sha256hash = %s", (sha256hash,))
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
                cursor = conn.execute(
                    "SELECT id FROM tokens WHERE sha256hash = ?", (sha256hash,))
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("Token插入后查询失败")
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
                cursor.execute(
                    "SELECT id FROM tokens WHERE sha256hash = %s", (sha256hash,))
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("Token插入后查询失败")
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
                conn.execute(
                    "UPDATE tokens SET last_call_time = ? WHERE id = ?", (now, token_id))
                conn.commit()
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE tokens SET last_call_time = NOW() WHERE id = %s", (token_id,))
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
    deleted = 0
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                if target_id is not None:
                    cursor = conn.execute(
                        "DELETE FROM tokens WHERE id = ?", (target_id,))
                else:
                    cursor = conn.execute(
                        "DELETE FROM tokens WHERE sha256hash = ?", (target_sha,))
                deleted = cursor.rowcount
                conn.commit()
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                if target_id is not None:
                    cursor.execute(
                        "DELETE FROM tokens WHERE id = %s", (target_id,))
                else:
                    cursor.execute(
                        "DELETE FROM tokens WHERE sha256hash = %s", (target_sha,))
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


# ─── 排行榜相关数据库操作 ───


def _generate_user_id(length: int = 8) -> str:
    """生成简短且不易重复的用户ID（大写字母+数字，排除易混淆字符）"""
    alphabet = string.ascii_uppercase.replace('O', '').replace(
        'I', '') + string.digits.replace('0', '').replace('1', '')
    while True:
        user_id = ''.join(secrets.choice(alphabet) for _ in range(length))
        # 检查是否已存在
        if not get_user_by_id(user_id):
            return user_id


def _generate_cookie_token() -> str:
    """生成安全的cookie token"""
    return secrets.token_urlsafe(32)


def get_user_by_cookie(cookie_token: str) -> Optional[Dict[str, Any]]:
    """通过cookie token获取用户信息，同时检查是否被吊销"""
    if not cookie_token:
        return None
    # 先检查是否被吊销
    if is_cookie_revoked(cookie_token):
        return None
    cfg = get_config()
    ph = _placeholder()
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                cursor = conn.execute(
                    f"SELECT * FROM top_user WHERE cookie_token = {ph}", (cookie_token,))
                row = cursor.fetchone()
                if not row:
                    return None
                return dict(row)
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT * FROM top_user WHERE cookie_token = {ph}", (cookie_token,))
                row = cursor.fetchone()
                if not row:
                    return None
                return row
        finally:
            conn.close()


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """通过用户ID获取用户信息"""
    if not user_id:
        return None
    cfg = get_config()
    ph = _placeholder()
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                cursor = conn.execute(
                    f"SELECT * FROM top_user WHERE user_id = {ph}", (user_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return dict(row)
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT * FROM top_user WHERE user_id = {ph}", (user_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return row
        finally:
            conn.close()


def create_user(username: str, cookie_token: str, ip_location: str) -> Dict[str, Any]:
    """创建新用户存档"""
    user_id = _generate_user_id()
    cfg = get_config()
    ph = _placeholder()
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                conn.execute(
                    f"INSERT INTO top_user (user_id, username, cookie_token, ip_location) VALUES ({ph}, {ph}, {ph}, {ph})",
                    (user_id, username, cookie_token, ip_location)
                )
                conn.commit()
                user = get_user_by_id(user_id)
                if user is None:
                    raise RuntimeError(f"创建用户后查询失败: user_id={user_id}")
                return user
            except Exception as err:
                conn.rollback()
                log.error(f"[DB] 创建用户失败: {err}")
                raise
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"INSERT INTO top_user (user_id, username, cookie_token, ip_location) VALUES ({ph}, {ph}, {ph}, {ph})",
                    (user_id, username, cookie_token, ip_location)
                )
            conn.commit()
            user = get_user_by_id(user_id)
            if user is None:
                raise RuntimeError(f"创建用户后查询失败: user_id={user_id}")
            return user
        except Exception as err:
            conn.rollback()
            log.error(f"[DB] 创建用户失败: {err}")
            raise
        finally:
            conn.close()


def update_user_stats(user_id: str, difficulty: str, total_delta: int, won_delta: int, win_rounds_delta: int) -> None:
    """更新用户统计数据"""
    cfg = get_config()
    ph = _placeholder()
    total_col = f"{difficulty}_total"
    won_col = f"{difficulty}_won"
    rounds_col = f"{difficulty}_win_rounds"
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                conn.execute(
                    f"UPDATE top_user SET {total_col} = {total_col} + {ph}, {won_col} = {won_col} + {ph}, {rounds_col} = {rounds_col} + {ph}, update_time = datetime('now') WHERE user_id = {ph}",
                    (total_delta, won_delta, win_rounds_delta, user_id)
                )
                conn.commit()
            except Exception as err:
                conn.rollback()
                log.error(f"[DB] 更新用户统计失败: {err}")
                raise
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"UPDATE top_user SET {total_col} = {total_col} + %s, {won_col} = {won_col} + %s, {rounds_col} = {rounds_col} + %s, update_time = NOW() WHERE user_id = %s",
                    (total_delta, won_delta, win_rounds_delta, user_id)
                )
            conn.commit()
        except Exception as err:
            conn.rollback()
            log.error(f"[DB] 更新用户统计失败: {err}")
            raise
        finally:
            conn.close()


def update_username(user_id: str, username: str) -> None:
    """更新用户名"""
    cfg = get_config()
    ph = _placeholder()
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                conn.execute(
                    f"UPDATE top_user SET username = {ph}, update_time = datetime('now') WHERE user_id = {ph}", (username, user_id))
                conn.commit()
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE top_user SET username = %s, update_time = NOW() WHERE user_id = %s", (username, user_id))
            conn.commit()
        finally:
            conn.close()


def delete_user(user_id: str) -> int:
    """删除用户存档及其日榜记录，返回删除的行数"""
    cfg = get_config()
    ph = _placeholder()
    deleted = 0
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                # 先获取cookie_token以吊销
                cursor = conn.execute(
                    f"SELECT cookie_token FROM top_user WHERE user_id = {ph}", (user_id,))
                row = cursor.fetchone()
                if row:
                    revoke_cookie(row[0])
                # 删除日榜记录
                cursor = conn.execute(
                    f"DELETE FROM top_daily WHERE user_id = {ph}", (user_id,))
                deleted += cursor.rowcount
                # 删除已上传游戏记录（去重表）
                cursor = conn.execute(
                    f"DELETE FROM top_user_games WHERE user_id = {ph}", (user_id,))
                deleted += cursor.rowcount
                # 删除用户
                cursor = conn.execute(
                    f"DELETE FROM top_user WHERE user_id = {ph}", (user_id,))
                deleted += cursor.rowcount
                conn.commit()
            except Exception as err:
                conn.rollback()
                log.error(f"[DB] 删除用户失败: {err}")
                raise
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT cookie_token FROM top_user WHERE user_id = {ph}", (user_id,))
                row = cursor.fetchone()
                if row:
                    revoke_cookie(row['cookie_token'])
                cursor.execute(
                    "DELETE FROM top_daily WHERE user_id = %s", (user_id,))
                deleted += cursor.rowcount
                cursor.execute(
                    "DELETE FROM top_user_games WHERE user_id = %s", (user_id,))
                deleted += cursor.rowcount
                cursor.execute(
                    "DELETE FROM top_user WHERE user_id = %s", (user_id,))
                deleted += cursor.rowcount
            conn.commit()
        except Exception as err:
            conn.rollback()
            log.error(f"[DB] 删除用户失败: {err}")
            raise
        finally:
            conn.close()
    return deleted


def revoke_cookie(cookie_token: str) -> None:
    """吊销cookie（加入黑名单）"""
    if not cookie_token:
        return
    cfg = get_config()
    ph = _placeholder()
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                conn.execute(
                    f"INSERT OR IGNORE INTO lb_revoked_cookies (cookie_token) VALUES ({ph})", (cookie_token,))
                conn.commit()
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT IGNORE INTO lb_revoked_cookies (cookie_token) VALUES (%s)", (cookie_token,))
            conn.commit()
        finally:
            conn.close()


def is_cookie_revoked(cookie_token: str) -> bool:
    """检查cookie是否已被吊销"""
    if not cookie_token:
        return False
    cfg = get_config()
    ph = _placeholder()
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                cursor = conn.execute(
                    f"SELECT 1 FROM lb_revoked_cookies WHERE cookie_token = {ph}", (cookie_token,))
                return cursor.fetchone() is not None
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM lb_revoked_cookies WHERE cookie_token = %s", (cookie_token,))
                return cursor.fetchone() is not None
        finally:
            conn.close()


def add_daily_record(user_id: str, game_id: str, difficulty: str, mode: str, won: int, rounds: int, play_date: str) -> bool:
    """添加日榜记录，如果是同一用户同一game_id则返回False（去重）"""
    import sqlite3
    import pymysql
    cfg = get_config()
    ph = _placeholder()
    try:
        if cfg.type == DatabaseType.sqlite:
            with _sqlite_lock:
                conn = _get_sqlite_conn()
                try:
                    conn.execute(
                        f"INSERT INTO top_daily (user_id, game_id, difficulty, mode, won, rounds, play_date) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                        (user_id, game_id, difficulty,
                         mode, won, rounds, play_date)
                    )
                    conn.commit()
                    return True
                except sqlite3.IntegrityError:
                    return False
                finally:
                    conn.close()
        else:
            conn = _get_mysql_conn()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO top_daily (user_id, game_id, difficulty, mode, won, rounds, play_date) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (user_id, game_id, difficulty,
                         mode, won, rounds, play_date)
                    )
                conn.commit()
                return True
            except pymysql.err.IntegrityError:
                return False
            except pymysql.err.MySQLError as e:
                # 1062 = Duplicate entry
                if e.args[0] == 1062:
                    return False
                raise
            finally:
                conn.close()
    except Exception as err:
        log.error(f"[DB] 添加日榜记录失败: {err}")
        return False


def get_leaderboard(difficulty: str, board_type: str, limit: int = 100, user_id: Optional[str] = None) -> tuple[list[Dict[str, Any]], Optional[int]]:
    """获取用户排行榜

    board_type: 'wins'（胜利数）/ 'win_rate'（胜率）/ 'avg_rounds'（平均回合数）
    返回: (排行榜列表, 当前用户名次)
    """
    cfg = get_config()
    total_col = f"{difficulty}_total"
    won_col = f"{difficulty}_won"
    rounds_col = f"{difficulty}_win_rounds"

    # 基础查询：至少需要1局才上榜（胜率榜至少需要一定局数避免偶然）
    min_games = 10 if board_type == 'win_rate' else 1

    if board_type == 'wins':
        order_clause = f"{won_col} DESC"
        value_expr = won_col
    elif board_type == 'win_rate':
        value_expr = f"CASE WHEN {total_col} > 0 THEN CAST({won_col} AS FLOAT) / {total_col} ELSE 0 END"
        order_clause = f"{value_expr} DESC"
    elif board_type == 'avg_rounds':
        # 只有胜利的才计入平均回合，回合越少越好
        value_expr = f"CASE WHEN {won_col} > 0 THEN CAST({rounds_col} AS FLOAT) / {won_col} ELSE 999 END"
        order_clause = f"{value_expr} ASC"
    else:
        return [], None

    results = []
    my_rank = None

    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                # 查询排行榜
                query = f"""
                    SELECT user_id, username, ip_location, {total_col} as total, {won_col} as won, {rounds_col} as win_rounds,
                           {value_expr} as value,
                           CASE WHEN {total_col} > 0 THEN CAST({won_col} AS FLOAT) / {total_col} ELSE 0 END as win_rate,
                           CASE WHEN {won_col} > 0 THEN CAST({rounds_col} AS FLOAT) / {won_col} ELSE 0 END as avg_rounds
                    FROM top_user
                    WHERE {total_col} >= ?
                    ORDER BY {order_clause}
                    LIMIT ?
                """
                cursor = conn.execute(query, (min_games, limit))
                rows = cursor.fetchall()

                for idx, row in enumerate(rows):
                    rank = idx + 1
                    d = dict(row)
                    d['rank'] = rank
                    results.append(d)
                    if user_id and d['user_id'] == user_id:
                        my_rank = rank

                # 如果用户不在前limit名，单独查询其名次
                if user_id and my_rank is None:
                    rank_query = f"""
                        SELECT COUNT(*) + 1 as rank FROM top_user
                        WHERE {total_col} >= ? AND {order_clause} < (SELECT {value_expr} FROM top_user WHERE user_id = ?)
                    """
                    cursor = conn.execute(rank_query, (min_games, user_id))
                    rank_row = cursor.fetchone()
                    if rank_row:
                        my_rank = rank_row[0]
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                query = f"""
                    SELECT user_id, username, ip_location, {total_col} as total, {won_col} as won, {rounds_col} as win_rounds,
                           {value_expr} as value,
                           CASE WHEN {total_col} > 0 THEN CAST({won_col} AS DECIMAL(10,4)) / {total_col} ELSE 0 END as win_rate,
                           CASE WHEN {won_col} > 0 THEN CAST({rounds_col} AS DECIMAL(10,4)) / {won_col} ELSE 999 END as avg_rounds
                    FROM top_user
                    WHERE {total_col} >= %s
                    ORDER BY {order_clause}
                    LIMIT %s
                """
                cursor.execute(query, (min_games, limit))
                rows = cursor.fetchall()

                for idx, row in enumerate(rows):
                    rank = idx + 1
                    row['rank'] = rank
                    results.append(row)
                    if user_id and row['user_id'] == user_id:
                        my_rank = rank

                if user_id and my_rank is None:
                    rank_query = f"""
                        SELECT COUNT(*) + 1 as rank FROM top_user
                        WHERE {total_col} >= %s AND {order_clause} < (SELECT {value_expr} FROM top_user WHERE user_id = %s)
                    """
                    cursor.execute(rank_query, (min_games, user_id))
                    rank_row = cursor.fetchone()
                    if rank_row:
                        my_rank = rank_row['rank']
        finally:
            conn.close()

    return results, my_rank


def get_daily_leaderboard(difficulty: str, play_date: str, limit: int = 100, user_id: Optional[str] = None) -> tuple[list[Dict[str, Any]], Optional[int]]:
    """获取日榜（只看胜利的，按回合数升序）"""
    cfg = get_config()
    ph = _placeholder()
    results = []
    my_rank = None

    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                query = f"""
                    SELECT d.user_id, u.username, u.ip_location, d.rounds
                    FROM top_daily d
                    JOIN top_user u ON d.user_id = u.user_id
                    WHERE d.difficulty = {ph} AND d.play_date = {ph} AND d.won = 1 AND d.mode = 'daily'
                    ORDER BY d.rounds ASC
                    LIMIT {ph}
                """
                cursor = conn.execute(query, (difficulty, play_date, limit))
                rows = cursor.fetchall()

                for idx, row in enumerate(rows):
                    rank = idx + 1
                    d = dict(row)
                    d['rank'] = rank
                    results.append(d)
                    if user_id and d['user_id'] == user_id:
                        my_rank = rank

                if user_id and my_rank is None:
                    rank_query = f"""
                        SELECT COUNT(*) + 1 as rank
                        FROM top_daily d
                        WHERE d.difficulty = {ph} AND d.play_date = {ph} AND d.won = 1 AND d.mode = 'daily'
                          AND d.rounds < (SELECT rounds FROM top_daily WHERE user_id = {ph} AND difficulty = {ph} AND play_date = {ph} AND mode = 'daily')
                    """
                    cursor = conn.execute(
                        rank_query, (difficulty, play_date, user_id, difficulty, play_date))
                    rank_row = cursor.fetchone()
                    if rank_row:
                        my_rank = rank_row[0]
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                query = """
                    SELECT d.user_id, u.username, u.ip_location, d.rounds
                    FROM top_daily d
                    JOIN top_user u ON d.user_id = u.user_id
                    WHERE d.difficulty = %s AND d.play_date = %s AND d.won = 1 AND d.mode = 'daily'
                    ORDER BY d.rounds ASC
                    LIMIT %s
                """
                cursor.execute(query, (difficulty, play_date, limit))
                rows = cursor.fetchall()

                for idx, row in enumerate(rows):
                    rank = idx + 1
                    row['rank'] = rank
                    results.append(row)
                    if user_id and row['user_id'] == user_id:
                        my_rank = rank

                if user_id and my_rank is None:
                    rank_query = """
                        SELECT COUNT(*) + 1 as rank
                        FROM top_daily d
                        WHERE d.difficulty = %s AND d.play_date = %s AND d.won = 1 AND d.mode = 'daily'
                          AND d.rounds < (SELECT rounds FROM top_daily WHERE user_id = %s AND difficulty = %s AND play_date = %s AND mode = 'daily')
                    """
                    cursor.execute(
                        rank_query, (difficulty, play_date, user_id, difficulty, play_date))
                    rank_row = cursor.fetchone()
                    if rank_row:
                        my_rank = rank_row['rank']
        finally:
            conn.close()

    return results, my_rank


def clean_daily_board(play_date: Optional[str] = None) -> int:
    """清空日榜，指定日期或清空所有"""
    cfg = get_config()
    ph = _placeholder()
    deleted = 0
    if play_date:
        sql = f"DELETE FROM top_daily WHERE play_date = {ph}"
        params = (play_date,)
    else:
        sql = "DELETE FROM top_daily"
        params = ()

    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                cursor = conn.execute(sql, params)
                deleted = cursor.rowcount
                conn.commit()
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                deleted = cursor.rowcount
            conn.commit()
        finally:
            conn.close()
    log.info(f"[Cleanup] 清理日榜: 日期={play_date or 'ALL'}, 删除数量={deleted}")
    return deleted


def clean_inactive_users(inactive_days: int) -> int:
    """清理不活跃用户存档"""
    cfg = get_config()
    deleted = 0
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                # 先获取要删除的用户的cookie_token
                cursor = conn.execute(
                    "SELECT cookie_token FROM top_user WHERE update_time < datetime('now', '-' || ? || ' days')", (inactive_days,))
                tokens = [row[0] for row in cursor.fetchall()]
                for token in tokens:
                    revoke_cookie(token)
                # 删除日榜记录
                cursor = conn.execute(
                    "DELETE FROM top_daily WHERE user_id IN (SELECT user_id FROM top_user WHERE update_time < datetime('now', '-' || ? || ' days'))", (inactive_days,))
                deleted += cursor.rowcount
                # 删除已上传游戏记录（去重表）
                cursor = conn.execute(
                    "DELETE FROM top_user_games WHERE user_id IN (SELECT user_id FROM top_user WHERE update_time < datetime('now', '-' || ? || ' days'))", (inactive_days,))
                deleted += cursor.rowcount
                # 删除用户
                cursor = conn.execute(
                    "DELETE FROM top_user WHERE update_time < datetime('now', '-' || ? || ' days')", (inactive_days,))
                deleted += cursor.rowcount
                conn.commit()
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT cookie_token FROM top_user WHERE update_time < DATE_SUB(NOW(), INTERVAL %s DAY)", (inactive_days,))
                tokens = [row['cookie_token'] for row in cursor.fetchall()]
                for token in tokens:
                    revoke_cookie(token)
                cursor.execute(
                    "DELETE FROM top_daily WHERE user_id IN (SELECT user_id FROM top_user WHERE update_time < DATE_SUB(NOW(), INTERVAL %s DAY))", (inactive_days,))
                deleted += cursor.rowcount
                cursor.execute(
                    "DELETE FROM top_user_games WHERE user_id IN (SELECT user_id FROM top_user WHERE update_time < DATE_SUB(NOW(), INTERVAL %s DAY))", (inactive_days,))
                deleted += cursor.rowcount
                cursor.execute(
                    "DELETE FROM top_user WHERE update_time < DATE_SUB(NOW(), INTERVAL %s DAY)", (inactive_days,))
                deleted += cursor.rowcount
            conn.commit()
        finally:
            conn.close()
    log.info(f"[Cleanup] 清理不活跃用户: 不活跃天数={inactive_days}, 删除记录数={deleted}")
    return deleted


def get_existing_game_ids(user_id: str) -> set[str]:
    """获取用户已上传的game_id集合，用于去重防止刷记录"""
    cfg = get_config()
    game_ids = set()
    ph = _placeholder()
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                cursor = conn.execute(
                    f"SELECT game_id FROM top_user_games WHERE user_id = {ph}", (user_id,))
                for row in cursor.fetchall():
                    game_ids.add(row[0])
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT game_id FROM top_user_games WHERE user_id = %s", (user_id,))
                for row in cursor.fetchall():
                    game_ids.add(row['game_id'])
        finally:
            conn.close()
    return game_ids


def record_uploaded_games(user_id: str, records: list[dict]) -> int:
    """记录用户已上传的game_id，返回实际新增的数量（去重后）"""
    cfg = get_config()
    ph = _placeholder()
    added = 0
    if cfg.type == DatabaseType.sqlite:
        with _sqlite_lock:
            conn = _get_sqlite_conn()
            try:
                for rec in records:
                    try:
                        conn.execute(
                            f"INSERT OR IGNORE INTO top_user_games (user_id, game_id, timestamp) VALUES ({ph}, {ph}, {ph})",
                            (user_id, rec['game_id'], rec['timestamp']))
                        added += conn.total_changes and 1 or 0
                    except Exception:
                        pass
                conn.commit()
            finally:
                conn.close()
    else:
        conn = _get_mysql_conn()
        try:
            with conn.cursor() as cursor:
                for rec in records:
                    try:
                        cursor.execute(
                            "INSERT IGNORE INTO top_user_games (user_id, game_id, timestamp) VALUES (%s, %s, %s)",
                            (user_id, rec['game_id'], rec['timestamp']))
                        added += cursor.rowcount
                    except Exception:
                        pass
            conn.commit()
        finally:
            conn.close()
    return added
