#!/usr/bin/env python3
"""
Docker 构建时配置文件处理脚本
- 将 config.example.toml 复制为默认配置
- 修改 listen_host 为 0.0.0.0（Docker 环境必须）
- 修改默认数据库为 SQLite（避免本地 MySQL 连接失败）
"""
import shutil
from pathlib import Path

EXAMPLE_CONFIG = Path('/app/config.example.toml')
TARGET_PATHS = [
    Path('/app/defaults/config/config.toml'),
    Path('/app/config.toml'),
]

print(f'检查示例配置是否存在: {EXAMPLE_CONFIG} -> {EXAMPLE_CONFIG.exists()}')

if not EXAMPLE_CONFIG.exists():
    print('错误: config.example.toml 不存在!')
    exit(1)

for target in TARGET_PATHS:
    print(f'处理: {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(EXAMPLE_CONFIG, target)

    with open(target, 'r', encoding='utf-8') as f:
        content = f.read()

    # Docker 环境监听 0.0.0.0 - 简单字符串替换
    content = content.replace(
        'listen_host = "127.0.0.1"', 'listen_host = "0.0.0.0"')
    content = content.replace(
        'listen_host="127.0.0.1"', 'listen_host = "0.0.0.0"')

    # 默认使用 SQLite（只替换数据库配置开头的 type）
    content = content.replace('type = "mysql"', 'type = "sqlite"', 1)
    content = content.replace('type="mysql"', 'type = "sqlite"', 1)

    with open(target, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f'已完成: {target}')
