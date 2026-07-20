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

# OCI 镜像元数据（GitHub Actions 构建时会通过 annotations 覆盖）
LABEL org.opencontainers.image.title="ChineseIdomWordle" \
      org.opencontainers.image.description="ChineseIdomWordle 成语 Wordle 游戏服务" \
      org.opencontainers.image.source="https://github.com/P-C-T-Group/ChineseIdomWordle" \
      org.opencontainers.image.vendor="P-C-T-Group" \
      org.opencontainers.image.licenses="MIT"

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Shanghai

# ──────────────────────────── APT 换源 + 安装 Node.js ────────────────────────────
RUN set -eux; \
    # 第一步：配置 APT 源（仅 Debian 基础源，不折腾 NodeSource 镜像）
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
    else \
        echo "=== [海外模式] 使用官方源 ==="; \
    fi; \
    # 第二步：安装基础依赖
    apt-get update && apt-get install -y --no-install-recommends \
       curl \
       ca-certificates \
       gnupg; \
    # 第三步：直接用官方脚本安装 Node.js 20.x（通过代理加速，包体积小）
    echo "=== 安装 Node.js 20.x ==="; \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -; \
    apt-get install -y --no-install-recommends nodejs; \
    # 清理缓存减小镜像体积
    rm -rf /var/lib/apt/lists/*; \
    # 第四步：配置 pip 国内源
    if [ "$USE_CN_MIRROR" = "true" ]; then \
        echo "=== 配置 pip 清华源 ==="; \
        pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple || true; \
        pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn || true; \
    fi; \
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
ARG USE_CN_MIRROR=true
RUN echo "=== 安装 Node.js 依赖（javascript-obfuscator） ===" \
    && cd /app/tool \
    && if [ "$USE_CN_MIRROR" = "true" ]; then \
         npm install --production=false --registry=https://registry.npmmirror.com; \
       else \
         npm install --production=false; \
       fi \
    && npm cache clean --force

# 创建用于存放默认文件的目录（挂载空目录时用于恢复）
RUN mkdir -p /app/defaults/config /app/defaults/data /app/defaults/client /app/logs

# 处理默认配置文件
RUN python3 /app/setup_config.py

# 保存默认 data 目录内容（用于挂载空目录时恢复）
RUN cp -r /app/data/* /app/defaults/data/

# 保存默认 client 目录内容（用于挂载空目录时恢复）
RUN cp -r /app/client/* /app/defaults/client/

# 赋予 entrypoint 执行权限
RUN chmod +x /app/docker-entrypoint.sh

# 暴露服务端口（默认 8000）
EXPOSE 8000

# 设置入口点
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# 默认启动命令
CMD ["python", "run.py"]
