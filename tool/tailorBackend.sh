#!/bin/bash
# -- coding: utf-8 --
# tailorBackend.sh - 后端配置定制脚本
# (c) 2026 P.C.T.G. MIT License.

set -e

# 颜色定义
RED='\033[31m'
GREEN='\033[32m'
YELLOW='\033[33m'
BLUE='\033[34m'
RESET='\033[0m'

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/../backend"
MAIN_PY_PATH="$BACKEND_DIR/app/main.py"
TOKEN_FILE_PATH="$BACKEND_DIR/token-sha256.txt"
PULLUP_SCRIPT="$BACKEND_DIR/pullUpServer.sh"

echo -e "${BLUE}========================================${RESET}"
echo -e "${BLUE}    IdiomWordle 后端配置定制工具    ${RESET}"
echo -e "${BLUE}========================================${RESET}"
echo ""

# 函数：计算字符串的sha256
get_sha256() {
    echo -n "$1" | sha256sum | awk '{print $1}'
}

# 1. 处理管理员Token
echo -e "${YELLOW}[步骤1] 配置管理员Token${RESET}"
echo "管理员Token用于访问/api/admin下的管理接口"
echo "当前默认管理员Token为: test-admin"
read -p "请输入新的管理员Token (直接回车保持默认): " admin_token_input

if [ -z "$admin_token_input" ]; then
    admin_token="test-admin"
    admin_hash="db09d473d4b6461b91bfa47e4fed3ef55e0234df4132ca7a827b0a69e8927cac"
    echo -e "${YELLOW}保持默认管理员Token: test-admin${RESET}"
else
    admin_token="$admin_token_input"
    admin_hash=$(get_sha256 "$admin_token")
    echo -e "${GREEN}新管理员Token已设置: $admin_token${RESET}"
    echo "对应的SHA256哈希: $admin_hash"
fi

# 更新main.py中的ADMIN_TOKEN_HASH
echo "正在更新main.py中的管理员Token哈希..."
sed -i.bak "s/^ADMIN_TOKEN_HASH = \".*\"$/ADMIN_TOKEN_HASH = \"$admin_hash\"/" "$MAIN_PY_PATH"
rm -f "$MAIN_PY_PATH.bak"
echo -e "${GREEN}main.py更新完成${RESET}"
echo ""

# 2. 处理用户Token和鉴权设置
echo -e "${YELLOW}[步骤2] 配置用户Token与鉴权${RESET}"
read -p "是否开启后端Token鉴权? (Y/n，默认开启): " enable_auth_input
enable_auth_input=${enable_auth_input:-Y}

# 先清空token文件
> "$TOKEN_FILE_PATH"

if [[ "$enable_auth_input" =~ ^[Nn]$ ]]; then
    echo -e "${YELLOW}已关闭后端Token鉴权，token-sha256.txt已清空${RESET}"
else
    echo -e "${GREEN}已开启后端Token鉴权${RESET}"
    
    # 第一行写入管理员token哈希
    echo "$admin_hash" > "$TOKEN_FILE_PATH"
    echo "已自动添加管理员Token到合法Token列表"
    
    read -p "请输入需要添加的普通用户Token数量: " token_count
    if [ -n "$token_count" ] && [ "$token_count" -gt 0 ] 2>/dev/null; then
        for ((i=1; i<=token_count; i++)); do
            read -p "请输入第 $i 个用户Token: " user_token
            if [ -n "$user_token" ]; then
                user_hash=$(get_sha256 "$user_token")
                echo "$user_hash" >> "$TOKEN_FILE_PATH"
                echo "  -> 已添加Token: $user_token (哈希: ${user_hash:0:16}...)"
            else
                echo -e "${RED}  -> Token不能为空，跳过${RESET}"
            fi
        done
    else
        echo "未添加额外用户Token"
    fi
    echo -e "${GREEN}token-sha256.txt配置完成${RESET}"
fi
echo ""

# 3. 赋予pullUpServer.sh执行权限
echo -e "${YELLOW}[步骤3] 配置启动脚本权限${RESET}"
chmod +x "$PULLUP_SCRIPT"
echo -e "${GREEN}已赋予pullUpServer.sh执行权限${RESET}"
echo ""

# 4. 询问是否立即运行后端
echo -e "${YELLOW}[步骤4] 启动后端服务${RESET}"
read -p "是否立即启动后端服务? (y/N): " run_now
if [[ "$run_now" =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}正在启动后端服务...${RESET}"
    cd "$BACKEND_DIR"
    exec ./pullUpServer.sh
else
    echo ""
    echo -e "${GREEN}========================================${RESET}"
    echo -e "${GREEN}    配置完成!    ${RESET}"
    echo -e "${GREEN}========================================${RESET}"
    echo ""
    echo "管理员Token: $admin_token"
    if [[ "$enable_auth_input" =~ ^[Nn]$ ]]; then
        echo "鉴权状态: 已关闭"
    else
        echo "鉴权状态: 已开启"
        echo "合法Token总数: $(wc -l < "$TOKEN_FILE_PATH")"
    fi
    echo ""
    echo "后续启动后端请运行:"
    echo "  cd $BACKEND_DIR && ./pullUpServer.sh"
fi