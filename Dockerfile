# =============================================================================
# ChineseIdomWordle Docker 镜像（国内网络优化版）
# =============================================================================
# 构建阶段可以使用:
#   docker build -t chinese-idiom-wordle:latest .
#
# 国内源说明:
#   - APT:   清华大学镜像站
#   - Pip:   清华大学镜像站
#   - NPM:   淘宝 npmmirror 镜像
# =============================================================================

# 使用官方 Python 3.11 slim 镜像作为基础
FROM python:3.11-slim

# 构建参数：是否使用国内镜像源（国内构建设为 true，海外设为 false）
ARG USE_CN_MIRROR=true

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Shanghai

# ──────────────────────────── APT 换源 + 安装 Node.js ────────────────────────────
RUN set -eux; \
    if [ "$USE_CN_MIRROR" = "true" ]; then \
        echo "=== [国内模式] 配置清华 APT 镜像源 ==="; \
        # 兼容两种 sources 格式（DEB822 格式和传统格式）
        if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
            sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources; \
            sed -i 's|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources; \
        else \
            sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list; \
            sed -i 's|security.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list; \
        fi; \
        # pip 配置清华源
        pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple; \
        pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn; \
        # npm 配置淘宝源
        npm config set registry https://registry.npmmirror.com; \
    else \
        echo "=== [海外模式] 使用官方源 ==="; \
    fi; \
    # 安装基础依赖
    apt-get update && apt-get install -y --no-install-recommends \
       curl \
       ca-certificates \
       gnupg; \
    # 安装 Node.js 20.x
    echo "=== 安装 Node.js 20.x ==="; \
    if [ "$USE_CN_MIRROR" = "true" ]; then \
        # 国内：使用清华镜像 + jsdelivr 获取 GPG 密钥
        curl -fsSL https://cdn.jsdelivr.net/gh/nodesource/distributions@dev/keyrings/nodesource.gpg | gpg --dearmor -o /usr/share/keyrings/nodesource.gpg; \
        echo "deb [signed-by=/usr/share/keyrings/nodesource.gpg] https://mirrors.tuna.tsinghua.edu.cn/nodesource/deb/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list; \
    else \
        # 海外：使用官方源
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends nodejs; \
    # 清理缓存减小镜像体积
    rm -rf /var/lib/apt/lists/*; \
    # 验证 Node.js 和 npm 版本
    node -v && npm -v

# 首先复制 requirements 文件以利用 Docker 缓存
COPY backend/requirements.txt /app/backend/requirements.txt

# 安装 Python 依赖（源已在前面根据 USE_CN_MIRROR 配置）
RUN echo "=== 安装 Python 依赖 ===" \
    && pip install --no-cache-dir -r /app/backend/requirements.txt

# 复制项目文件（先复制全部，后面 entrypoint 会处理挂载时的默认文件）
COPY . /app/

# 安装 Node.js 依赖（javascript-obfuscator，用于前端 JS 混淆）
# 在 COPY 之后执行，避免被本地空目录覆盖；即使本地有 node_modules 也会重新构建适配容器环境
# npm 源已在前面根据 USE_CN_MIRROR 配置
RUN echo "=== 安装 Node.js 依赖（javascript-obfuscator） ===" \
    && cd /app/tool && npm install --production=false && npm cache clean --force

# 创建用于存放默认文件的目录（挂载空目录时用于恢复）
RUN mkdir -p /app/defaults/config \
    /app/defaults/data \
    /app/defaults/client \
    # 保存默认 config.toml（始终使用 example 模板，避免打包本地敏感配置）
    && cp /app/config.example.toml /app/defaults/config/config.toml \
    # 将 example 配置也作为容器内的初始 config.toml
    && cp /app/config.example.toml /app/config.toml \
    # Docker 环境下必须监听 0.0.0.0 才能被外部访问
    && sed -i 's/listen_host\s*=\s*"127\.0\.0\.1"/listen_host = "0.0.0.0"/' /app/defaults/config/config.toml \
    && sed -i 's/listen_host\s*=\s*"127\.0\.0\.1"/listen_host = "0.0.0.0"/' /app/config.toml \
    # 默认使用 SQLite 而非本地 MySQL
    && sed -i 's/type\s*=\s*"mysql"/type = "sqlite"/' /app/defaults/config/config.toml \
    && sed -i 's/type\s*=\s*"mysql"/type = "sqlite"/' /app/config.toml \
    # 保存默认 data 目录内容
    && cp -r /app/data/* /app/defaults/data/ \
    # 保存默认 client 目录内容
    && cp -r /app/client/* /app/defaults/client/ \
    # 创建必要的目录
    && mkdir -p /app/logs \
    # 赋予 entrypoint 执行权限（文件已由 COPY . /app/ 复制）
    && chmod +x /app/docker-entrypoint.sh

# 暴露服务端口（默认 8000）
EXPOSE 8000

# 设置入口点
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# 默认启动命令
CMD ["python", "run.py"]
