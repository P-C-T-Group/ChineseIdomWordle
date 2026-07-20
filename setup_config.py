#!/usr/bin/env python3
"""
Docker 构建时配置文件处理脚本
- 将 config.example.toml 复制为默认配置
- 修改 listen_host 为 0.0.0.0（Docker 环境必须）
- 修改默认数据库为 SQLite（避免本地 MySQL 连接失败）
"""
import re
import shutil
from pathlib import Path

EXAMPLE_CONFIG = Path('/app/config.example.toml')
TARGET_PATHS = [
    Path('/app/defaults/config/config.toml'),
    Path('/app/config.toml'),
]

for target in TARGET_PATHS:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(EXAMPLE_CONFIG, target)

    with open(target, 'r', encoding='utf-8') as f:
        content = f.read()

    # Docker 环境监听 0.0.0.0
    content = re.sub(
        r'listen_host\s*=\s*"127\.0\.0\.1"',
        'listen_host = "0.0.0.0"',
        content
    )

    # 默认使用 SQLite（只替换 [database] 节下的 type）
    content = re.sub(
        r'^(\s*type\s*=\s*)"mysql"',
        r'\1"sqlite"',
        content,
        flags=re.MULTILINE
    )

    with open(target, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f'已处理: {target}')

print('配置文件处理完成')
