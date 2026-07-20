#!/bin/bash
# ===========================================================================
# ChineseIdomWordle 统一启动脚本
# 根据 config.toml 中的 [frontend] 配置自动选择启动模式
# ===========================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo " ChineseIdomWordle 启动器"
echo "============================================================"

# 检查 Python 依赖
echo "[1/3] 检查依赖..."
pip3 install -q -r backend/requirements.txt

# 创建日志目录
mkdir -p backend/logs

# 使用统一入口启动（支持参数传递，如 --reinit）
echo "[2/3] 初始化检查，启动服务..."
echo "[3/3] 按 Ctrl+C 停止服务"
echo "  提示: 重新初始化前端配置运行 ./start.sh --reinit"
echo ""

exec python3 run.py "$@"
