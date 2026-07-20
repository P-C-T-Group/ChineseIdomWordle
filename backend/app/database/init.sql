-- SQLite 建表脚本（默认使用）
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

-- 排行榜：用户存档表
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
    UNIQUE(user_id, difficulty, play_date)
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
