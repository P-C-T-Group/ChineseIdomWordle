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

            -- tokens 表：用于存储玩家有效 Token 及其属性
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sha256hash TEXT UNIQUE NOT NULL,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                creator_ip TEXT DEFAULT '',
                valid_until TIMESTAMP NULL DEFAULT NULL,
                whitelist_ips TEXT DEFAULT '', -- 存储为 JSON 数组或逗号分隔字符串
                last_call_time TIMESTAMP NULL DEFAULT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tokens_sha ON tokens(sha256hash);
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
    from pymysql.err import ProgrammingError, OperationalError

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
            # 创建游戏表
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

            # 先查询已存在的索引，避免重复创建
            cursor.execute("""
                SELECT INDEX_NAME FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'games'
            """)
            existing_indexes = {row[0] for row in cursor.fetchall()}

            # 索引列表
            index_sqls = [
                ("GAME_CREATE_IP",  "CREATE INDEX `GAME_CREATE_IP` ON `games` (`create_ip`)"),
                ("GAME_DIFFICULTY", "CREATE INDEX `GAME_DIFFICULTY` ON `games` (`difficulty`)"),
                ("GAME_STATUS",     "CREATE INDEX `GAME_STATUS` ON `games` (`game_status`)"),
            ]
            for idx_name, sql in index_sqls:
                if idx_name in existing_indexes:
                    log.debug(f"[DB] 索引 {idx_name} 已存在，跳过创建")
                    continue
                try:
                    cursor.execute(sql)
                except (ProgrammingError, OperationalError) as e:
                    # 1061 = Duplicate key name，兼容旧版本数据库
                    if e.args[0] == 1061:
                        log.debug(f"[DB] 索引 {idx_name} 已存在（跳过）")
                        continue
                    raise

            # 创建 tokens 表用于存储玩家有效 Token 及其属性（若尚未创建）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `tokens` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `sha256hash` varchar(128) NOT NULL UNIQUE,
                    `create_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    `creator_ip` varchar(64) DEFAULT '',
                    `valid_until` datetime NULL DEFAULT NULL,
                    `whitelist_ips` text,
                    `last_call_time` timestamp NULL DEFAULT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            try:
                cursor.execute("CREATE INDEX `TOKENS_SHA` ON `tokens` (`sha256hash`)")
            except (ProgrammingError, OperationalError) as e:
                # 1061 Duplicate key name
                if getattr(e, 'args', None) and e.args[0] == 1061:
                    pass
                else:
                    raise

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
