#!/bin/bash
# ===========================================================================
# ChineseIdomWordle 统一启动脚本
# 根据 config.toml 中的 [frontend] 配置自动选择启动模式
# ===========================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/backend"

echo "============================================================"
echo " ChineseIdomWordle 启动器"
echo "============================================================"

# 检查 Python 依赖
echo "[1/3] 检查依赖..."
pip3 install -q -r requirements.txt

# 创建日志目录
mkdir -p logs

# 使用统一入口启动
echo "[2/3] 初始化完成，启动服务..."
echo "[3/3] 按 Ctrl+C 停止服务"
echo ""

exec python3 run.py
