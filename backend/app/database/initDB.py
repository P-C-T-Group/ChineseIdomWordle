"""
数据库初始化 - 支持 SQLite 与 MySQL 双模式建表
"""
import logging

from app.schemas.DB import DatabaseType
from app.database import db_manager

log = logging.getLogger('uvicorn')


def _init_sqlite():
    """初始化 SQLite 表结构"""
    conn = db_manager._get_sqlite_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS games (
                game_id            TEXT PRIMARY KEY,
                create_time        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                create_ip          TEXT DEFAULT '0.0.0.0',
                mode               TEXT NOT NULL DEFAULT 'unlimited',
                difficulty         TEXT NOT NULL DEFAULT 'medium',
                max_rounds         INTEGER NOT NULL DEFAULT 16,
                candidate_chars    TEXT,
                target_idiom       TEXT,
                target_pinyin      TEXT NOT NULL,
                target_explanation TEXT DEFAULT '',
                guesses            TEXT,
                game_status        TEXT NOT NULL DEFAULT 'playing',
                round              INTEGER NOT NULL DEFAULT 0,
                hints_used         INTEGER NOT NULL DEFAULT 0,
                max_hints          TEXT NOT NULL DEFAULT '2',
                revealed_pinyins   TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_games_create_ip  ON games(create_ip);
            CREATE INDEX IF NOT EXISTS idx_games_difficulty ON games(difficulty);
            CREATE INDEX IF NOT EXISTS idx_games_status     ON games(game_status);
        """)
        conn.commit()
        log.info("[DB] SQLite 数据库初始化成功")
    except Exception as err:
        conn.rollback()
        log.error(f"[DB] SQLite 数据库初始化失败: {err}")
        raise
    finally:
        conn.close()


def _init_mysql():
    """初始化 MySQL 表结构"""
    import pymysql

    cfg = db_manager.get_config()
    conn = pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.db,
        charset=cfg.charset,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `games` (
                    `game_id`            varchar(64) PRIMARY KEY,
                    `create_time`        timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    `create_ip`          varchar(255) DEFAULT '0.0.0.0',
                    `mode`               enum('daily', 'unlimited') NOT NULL DEFAULT 'unlimited',
                    `difficulty`         enum('easy', 'medium', 'hard') NOT NULL DEFAULT 'medium',
                    `max_rounds`         tinyint(2) NOT NULL DEFAULT 16,
                    `candidate_chars`    text,
                    `target_idiom`       varchar(8),
                    `target_pinyin`      varchar(32) NOT NULL,
                    `target_explanation` text,
                    `guesses`            longtext,
                    `game_status`        enum('playing', 'won', 'lost') NOT NULL DEFAULT 'playing',
                    `round`              tinyint(2) NOT NULL DEFAULT 0,
                    `hints_used`         tinyint(2) NOT NULL DEFAULT 0,
                    `max_hints`          varchar(255) NOT NULL DEFAULT '2',
                    `revealed_pinyins`   text
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS `GAME_CREATE_IP` ON `games` (`create_ip`)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS `GAME_DIFFICULTY` ON `games` (`difficulty`)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS `GAME_STATUS` ON `games` (`game_status`)"
            )
        conn.commit()
        log.info("[DB] MySQL 数据库初始化成功")
    except Exception as err:
        conn.rollback()
        log.error(f"[DB] MySQL 数据库初始化失败: {err}")
        raise
    finally:
        conn.close()


def initDB():
    """根据配置初始化数据库"""
    cfg = db_manager.get_config()
    if cfg.type == DatabaseType.mysql:
        _init_mysql()
    else:
        _init_sqlite()
