import pymysql
from app.schemas.DB import DBConnection


def initDB(DBConnection: DBConnection):
    # 初始化数据库
    RED = "\033[31m"
    GREEN = "\033[32m"
    RESET = "\033[0m"

    # 连接到数据库
    conn = pymysql.connect(
        host=DBConnection.host,
        port=DBConnection.port,
        user=DBConnection.user,
        password=DBConnection.password,
        database=DBConnection.db,
        charset=DBConnection.charset
    )
    cursor = conn.cursor()

    # 事务1: 创建Games表
    sql_create_table_games: str = 'CREATE TABLE IF NOT EXISTS `games` (`game_id` varchar(64) DEFAULT "none",`create_time` timestamp NOT NULL ON UPDATE CURRENT_TIMESTAMP,`create_ip` varchar(255) DEFAULT "0.0.0.0",`mode` enum("daily", "unlimited") NOT NULL DEFAULT "unlimited",`difficulty` enum("easy", "medium", "hard") NOT NULL DEFAULT "medium",`max_rounds` tinyint(2) NOT NULL DEFAULT 16,`candidate_chars` set("1", "2", "3", "4", "5", "6", "7", "8", "9", "10","11", "12", "13", "14", "15", "16", "17", "18", "19", "20"),`target_idiom` varchar(8),`target_pinyin` varchar(32) NOT NULL,`guesses` set("1", "2", "3", "4", "5", "6", "7", "8", "9", "10","11", "12", "13", "14", "15", "16", "17", "18", "19", "20"),`game_status` enum("playing", "won", "lost") NOT NULL DEFAULT "playing",`round` tinyint(2) NOT NULL DEFAULT 0,`hints_used` tinyint(2) NOT NULL DEFAULT 0,`max_hints` varchar(255) NOT NULL DEFAULT "2",`revealed_pinyins` set("1", "2"),PRIMARY KEY (`game_id`, `target_idiom`));'
    sql_set_index_games_ID: str = 'CREATE UNIQUE INDEX `GAME_ID` ON `games` (`game_id`)'
    sql_set_index_games_IP: str = 'CREATE INDEX `GAME_CREATE_IP` ON `games` (`create_ip`)'
    sql_set_index_games_difficulty: str = 'CREATE INDEX `GAME_DIFFICULTY` ON `games` (`difficulty`)'
    sql_set_index_games_status: str = 'CREATE INDEX `GAME_STATUS` ON `games` (`game_status`)'
    try:
        cursor.execute(sql_create_table_games)
        cursor.execute(sql_set_index_games_ID)
        cursor.execute(sql_set_index_games_IP)
        cursor.execute(sql_set_index_games_difficulty)
        cursor.execute(sql_set_index_games_status)
        print(
            f"{GREEN}INFO{RESET}:     [DB] 数据库Games表初始化成功"
        )
    except Exception as err:
        conn.rollback()
        print(
            f"{RED}ERROR{RESET}:     [DB] 数据库Games表初始化失败：", err
        )
