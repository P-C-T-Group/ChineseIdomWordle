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
