#!/bin/bash
# ===========================================================================
# ChineseIdomWordle Docker 入口脚本
# 处理挂载目录的初始化：挂载空目录时自动复制默认文件
# ===========================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[Entrypoint]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[Entrypoint]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[Entrypoint]${NC} $1"
}

log_error() {
    echo -e "${RED}[Entrypoint]${NC} $1"
}

APP_DIR="/app"
DEFAULTS_DIR="/app/defaults"

echo "============================================================"
echo " ChineseIdomWordle Docker 容器启动中..."
echo "============================================================"

# ---------------------------------------------------------------------------
# 1. 处理 config.toml 挂载
# ---------------------------------------------------------------------------
CONFIG_FILE="$APP_DIR/config.toml"
DEFAULT_CONFIG="$DEFAULTS_DIR/config/config.toml"

if [ ! -f "$CONFIG_FILE" ]; then
    log_warn "未找到 config.toml，正在复制默认配置文件..."
    cp "$DEFAULT_CONFIG" "$CONFIG_FILE"
    log_success "默认配置文件已复制到 $CONFIG_FILE"
    log_warn "提示: 建议将 config.toml 挂载到宿主机进行自定义配置"
else
    log_info "检测到已挂载的 config.toml"
    
    # 检查 listen_host 配置（Docker 中必须监听 0.0.0.0）
    if grep -q 'listen_host\s*=\s*"127\.0\.0\.1"' "$CONFIG_FILE"; then
        log_warn "⚠️  检测到 listen_host 配置为 127.0.0.1，Docker 环境中外部将无法访问！"
        log_warn "    正在自动修正为 0.0.0.0..."
        sed -i 's/listen_host\s*=\s*"127\.0\.0\.1"/listen_host = "0.0.0.0"/' "$CONFIG_FILE"
        log_success "已修正 listen_host 为 0.0.0.0"
    fi
    
    # 检查数据库类型（如果是 MySQL 但地址是 127.0.0.1，给出提示）
    if grep -q 'type\s*=\s*"mysql"' "$CONFIG_FILE" && grep -q 'host\s*=\s*"127\.0\.0\.1"' "$CONFIG_FILE"; then
        log_warn "⚠️  检测到 MySQL 配置指向 127.0.0.1，Docker 内这将无法访问宿主机或外部 MySQL"
        log_warn "    如需使用 MySQL，请配置正确的主机地址（如使用 docker-compose 中的服务名 mysql）"
    fi
fi

# ---------------------------------------------------------------------------
# 2. 处理 data 目录挂载
# ---------------------------------------------------------------------------
DATA_DIR="$APP_DIR/data"
DEFAULT_DATA="$DEFAULTS_DIR/data"

# 检查 data 目录是否为空（或不存在关键文件）
need_init_data=false
if [ ! -d "$DATA_DIR" ]; then
    mkdir -p "$DATA_DIR"
    need_init_data=true
elif [ -z "$(ls -A "$DATA_DIR" 2>/dev/null)" ]; then
    need_init_data=true
elif [ ! -f "$DATA_DIR/easy.json" ] || [ ! -f "$DATA_DIR/medium.json" ] || [ ! -f "$DATA_DIR/hard.json" ]; then
    log_warn "data 目录缺少必要的成语库文件，将补充缺失文件..."
    need_init_data=true
fi

if [ "$need_init_data" = true ]; then
    log_warn "data 目录未完整挂载，正在复制默认数据文件..."
    cp -rn "$DEFAULT_DATA"/* "$DATA_DIR/" 2>/dev/null || true
    log_success "默认数据文件已复制到 $DATA_DIR"
    log_info "如需持久化数据（包括 SQLite 数据库），请将 data 目录挂载到宿主机"
else
    log_info "检测到已挂载的 data 目录，文件数量: $(ls -1 "$DATA_DIR" | wc -l)"
fi

# 确保数据库目录可写
chmod -R 755 "$DATA_DIR" 2>/dev/null || true

# ---------------------------------------------------------------------------
# 3. 处理 client 目录挂载
# ---------------------------------------------------------------------------
CLIENT_DIR="$APP_DIR/client"
DEFAULT_CLIENT="$DEFAULTS_DIR/client"

need_init_client=false
if [ ! -d "$CLIENT_DIR" ]; then
    mkdir -p "$CLIENT_DIR"
    need_init_client=true
elif [ ! -f "$CLIENT_DIR/index.html" ]; then
    need_init_client=true
fi

if [ "$need_init_client" = true ]; then
    log_warn "client 目录未完整挂载（缺少 index.html），正在复制默认前端文件..."
    cp -rn "$DEFAULT_CLIENT"/* "$CLIENT_DIR/" 2>/dev/null || true
    log_success "默认前端文件已复制到 $CLIENT_DIR"
    log_info "如需自定义前端，请将 client 目录挂载到宿主机"
else
    log_info "检测到已挂载的 client 目录"
fi

# ---------------------------------------------------------------------------
# 4. 确保日志目录存在（代码中解析为项目根目录下的 logs/）
# ---------------------------------------------------------------------------
LOG_DIR="$APP_DIR/logs"
mkdir -p "$LOG_DIR"
chmod 755 "$LOG_DIR" 2>/dev/null || true
log_info "日志目录已就绪: $LOG_DIR"

# ---------------------------------------------------------------------------
# 5. 处理配置中的路径问题（Docker 环境下相对路径基于 /app/backend）
# ---------------------------------------------------------------------------
# 检查并修正 config.toml 中的路径配置（如果使用默认路径）
# Docker 中工作目录是 /app，backend 目录在 /app/backend，需要确保路径正确

echo ""
log_success "初始化完成，正在启动服务..."
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# 执行传入的命令
# ---------------------------------------------------------------------------
exec "$@"
