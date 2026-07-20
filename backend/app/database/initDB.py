"""
数据库初始化 - 支持 SQLite 与 MySQL 双模式建表
"""
import logging

from app.schemas.DB import DatabaseType
from app.database import db_manager

log = logging.getLogger('uvicorn')


def _init_sqlite():
    """初始化 SQLite 表结构"""
    from app.database.errors import print_database_error

    cfg = db_manager.get_config()
    db_path = getattr(cfg, 'sqlite_path_resolved', 'unknown')
    db_context = {"db": str(db_path)}

    try:
        conn = db_manager._get_sqlite_conn()
    except Exception as err:
        print_database_error(err, "sqlite", db_context, exit_program=False)
        raise

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

            -- 排行榜：用户存档表
            -- 每个终端（cookie_token）一条记录，user_id 为可展示的唯一标识
            -- 各难度统计列：total（总局数）/ won（胜利数）/ win_rounds（取胜总回合数）
            CREATE TABLE IF NOT EXISTS top_user (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL DEFAULT '',
                cookie_token TEXT UNIQUE NOT NULL,
                ip_location TEXT NOT NULL DEFAULT '',
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                easy_total INTEGER NOT NULL DEFAULT 0,
                easy_won INTEGER NOT NULL DEFAULT 0,
                easy_win_rounds INTEGER NOT NULL DEFAULT 0,
                medium_total INTEGER NOT NULL DEFAULT 0,
                medium_won INTEGER NOT NULL DEFAULT 0,
                medium_win_rounds INTEGER NOT NULL DEFAULT 0,
                hard_total INTEGER NOT NULL DEFAULT 0,
                hard_won INTEGER NOT NULL DEFAULT 0,
                hard_win_rounds INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_top_user_cookie ON top_user(cookie_token);

            -- 排行榜：每日挑战对局明细表
            -- 每个用户每天同一种模式只能提交一次成绩（daily模式每天仅第一次胜利可提交，任意难度）
            CREATE TABLE IF NOT EXISTS top_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                game_id TEXT NOT NULL DEFAULT '',
                difficulty TEXT NOT NULL,
                mode TEXT NOT NULL DEFAULT 'unlimited',
                won INTEGER NOT NULL DEFAULT 0,
                rounds INTEGER NOT NULL DEFAULT 0,
                play_date TEXT NOT NULL DEFAULT '',
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, play_date, mode)
            );
            CREATE INDEX IF NOT EXISTS idx_top_daily_user ON top_daily(user_id);
            CREATE INDEX IF NOT EXISTS idx_top_daily_diff ON top_daily(difficulty);

            -- 排行榜：被管理员吊销的 cookie 列表（使终端 cookie 失效）
            CREATE TABLE IF NOT EXISTS lb_revoked_cookies (
                cookie_token TEXT PRIMARY KEY,
                revoke_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- 排行榜：用户已上传的对局记录（用于去重，防止刷记录）
            CREATE TABLE IF NOT EXISTS top_user_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                game_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL DEFAULT 0,
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, game_id)
            );
            CREATE INDEX IF NOT EXISTS idx_top_user_games_uid ON top_user_games(user_id);
        """)
        conn.commit()
        log.info("[DB] SQLite 数据库初始化成功")
    except Exception as err:
        conn.rollback()
        log.error(f"[DB] SQLite 数据库初始化失败: {err}")
        print_database_error(err, "sqlite", db_context, exit_program=False)
        raise
    finally:
        conn.close()


def _init_mysql():
    """初始化 MySQL 表结构"""
    import pymysql
    from pymysql.err import ProgrammingError, OperationalError
    from app.database.errors import print_database_error

    cfg = db_manager.get_config()

    # 构建数据库连接上下文（用于错误提示）
    db_context = {
        "host": cfg.host,
        "port": cfg.port,
        "user": cfg.user,
        "db": cfg.db,
        "charset": cfg.charset,
    }

    try:
        conn = pymysql.connect(
            host=cfg.host,
            port=cfg.port,
            user=cfg.user,
            password=cfg.password,
            database=cfg.db,
            charset=cfg.charset,
        )
    except (ProgrammingError, OperationalError, pymysql.Error) as err:
        print_database_error(err, "mysql", db_context, exit_program=False)
        raise
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
                ("GAME_CREATE_IP",
                 "CREATE INDEX `GAME_CREATE_IP` ON `games` (`create_ip`)"),
                ("GAME_DIFFICULTY",
                 "CREATE INDEX `GAME_DIFFICULTY` ON `games` (`difficulty`)"),
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
                cursor.execute(
                    "CREATE INDEX `TOKENS_SHA` ON `tokens` (`sha256hash`)")
            except (ProgrammingError, OperationalError) as e:
                # 1061 Duplicate key name
                if getattr(e, 'args', None) and e.args[0] == 1061:
                    pass
                else:
                    raise

            # 创建排行榜用户存档表 top_user
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `top_user` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `user_id` varchar(32) NOT NULL UNIQUE,
                    `username` varchar(64) NOT NULL DEFAULT '',
                    `cookie_token` varchar(128) NOT NULL UNIQUE,
                    `ip_location` varchar(255) NOT NULL DEFAULT '',
                    `create_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    `update_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    `easy_total` INT NOT NULL DEFAULT 0,
                    `easy_won` INT NOT NULL DEFAULT 0,
                    `easy_win_rounds` INT NOT NULL DEFAULT 0,
                    `medium_total` INT NOT NULL DEFAULT 0,
                    `medium_won` INT NOT NULL DEFAULT 0,
                    `medium_win_rounds` INT NOT NULL DEFAULT 0,
                    `hard_total` INT NOT NULL DEFAULT 0,
                    `hard_won` INT NOT NULL DEFAULT 0,
                    `hard_win_rounds` INT NOT NULL DEFAULT 0
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            try:
                cursor.execute(
                    "CREATE INDEX `TOP_USER_COOKIE` ON `top_user` (`cookie_token`)")
            except (ProgrammingError, OperationalError) as e:
                if getattr(e, 'args', None) and e.args[0] == 1061:
                    pass
                else:
                    raise

            # 创建排行榜每日挑战明细表 top_daily
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `top_daily` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `user_id` varchar(32) NOT NULL,
                    `game_id` varchar(64) NOT NULL DEFAULT '',
                    `difficulty` enum('easy', 'medium', 'hard') NOT NULL,
                    `mode` enum('daily', 'unlimited') NOT NULL DEFAULT 'unlimited',
                    `won` TINYINT(1) NOT NULL DEFAULT 0,
                    `rounds` INT NOT NULL DEFAULT 0,
                    `play_date` varchar(10) NOT NULL DEFAULT '',
                    `create_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY `uniq_user_date_mode` (`user_id`, `play_date`, `mode`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            for idx_name, sql in [
                ("TOP_DAILY_USER",
                 "CREATE INDEX `TOP_DAILY_USER` ON `top_daily` (`user_id`)"),
                ("TOP_DAILY_DIFF",
                 "CREATE INDEX `TOP_DAILY_DIFF` ON `top_daily` (`difficulty`)"),
            ]:
                if idx_name in existing_indexes:
                    continue
                try:
                    cursor.execute(sql)
                except (ProgrammingError, OperationalError) as e:
                    if getattr(e, 'args', None) and e.args[0] == 1061:
                        continue
                    raise

            # 创建被吊销 cookie 表 lb_revoked_cookies
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `lb_revoked_cookies` (
                    `cookie_token` varchar(128) PRIMARY KEY,
                    `revoke_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 创建用户已上传对局记录表 top_user_games（用于去重）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `top_user_games` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `user_id` varchar(32) NOT NULL,
                    `game_id` varchar(64) NOT NULL,
                    `timestamp` BIGINT NOT NULL DEFAULT 0,
                    `create_time` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY `uniq_user_game` (`user_id`, `game_id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            try:
                cursor.execute(
                    "CREATE INDEX `TOP_USER_GAMES_UID` ON `top_user_games` (`user_id`)")
            except (ProgrammingError, OperationalError) as e:
                if getattr(e, 'args', None) and e.args[0] == 1061:
                    pass
                else:
                    raise

        conn.commit()
        log.info("[DB] MySQL 数据库初始化成功")

        # 初始化完成后执行 schema 升级检查（处理旧版本表结构）
        from app.database.db_manager import _ensure_mysql_schema
        _ensure_mysql_schema(conn)
    except Exception as err:
        conn.rollback()
        log.error(f"[DB] MySQL 数据库初始化失败: {err}")
        raise
    finally:
        conn.close()


def initDB():
    """根据配置初始化数据库"""
    from app.database.errors import print_database_error

    cfg = db_manager.get_config()
    db_context = {
        "host": getattr(cfg, 'host', 'N/A'),
        "port": getattr(cfg, 'port', 'N/A'),
        "user": getattr(cfg, 'user', 'N/A'),
        "db": getattr(cfg, 'db', getattr(cfg, 'sqlite_path_resolved', 'N/A')),
    }

    try:
        if cfg.type == DatabaseType.mysql:
            print(
                f"\n[DB] 正在连接 MySQL 数据库: {cfg.user}@{cfg.host}:{cfg.port}/{cfg.db}")
            _init_mysql()
        else:
            db_path = getattr(cfg, 'sqlite_path_resolved', 'unknown')
            print(f"\n[DB] 正在初始化 SQLite 数据库: {db_path}")
            _init_sqlite()
    except Exception as err:
        err_str = str(type(err)).lower()
        if 'sqlite' in err_str or 'mysql' in err_str or 'pymysql' in err_str:
            db_type = "mysql" if cfg.type == DatabaseType.mysql else "sqlite"
            print_database_error(err, db_type, db_context, exit_program=False)
        raise
