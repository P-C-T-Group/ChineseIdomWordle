# Docker 部署指南

本文档介绍如何使用 Docker 部署 ChineseIdomWordle。

## 快速开始

### 国内网络环境说明

镜像已内置国内镜像源加速（默认开启）：

| 工具 | 镜像源 |
|------|--------|
| APT | 清华大学 TUNA 镜像站 |
| Pip | 清华大学 TUNA 镜像站 |
| NPM | 淘宝 npmmirror 镜像 |

- **国内构建**：无需额外配置，直接构建即可
- **海外构建**：可通过构建参数关闭国内源：
  ```bash
  # 使用 docker build
  docker build --build-arg USE_CN_MIRROR=false -t chinese-idiom-wordle:latest .
  
  # 使用 docker compose，修改 docker-compose.yml 中的 args:
  #   USE_CN_MIRROR: "false"
  ```

### 使用 Docker Compose（推荐）

1. 确保已安装 Docker 和 Docker Compose

2. 启动服务：
```bash
docker compose up -d
```

3. 访问服务：打开浏览器访问 `http://localhost:8000`

4. 查看日志：
```bash
docker compose logs -f
```

5. 停止服务：
```bash
docker compose down
```

### 仅使用 Docker

1. 构建镜像：
```bash
docker build -t chinese-idiom-wordle:latest .
```

2. 运行容器：
```bash
docker run -d \
  --name chinese-idiom-wordle \
  -p 8000:8000 \
  -v $(pwd)/config.toml:/app/config.toml \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  chinese-idiom-wordle:latest
```

## 目录挂载说明

本镜像支持以下目录/文件挂载，并且**即使挂载空目录也不会影响服务启动**（容器会自动复制默认文件）：

| 挂载点 | 说明 | 必需 |
|--------|------|------|
| `/app/config.toml` | 配置文件 | 推荐 |
| `/app/data` | 数据目录（成语库 + SQLite 数据库） | 推荐 |
| `/app/client` | 前端静态文件目录 | 可选 |
| `/app/logs` | 日志目录 | 可选 |

### 挂载机制说明

当你将宿主机的空目录或空文件挂载到容器时，Docker 会覆盖容器内的对应位置。为了避免服务因缺少必要文件而无法启动，容器启动时会执行以下逻辑：

1. **config.toml**：如果挂载后文件不存在，自动从容器内的默认模板复制一份
2. **data 目录**：如果目录为空或缺少必要的成语库文件（easy.json/medium.json/hard.json/character.json），自动复制默认数据文件
3. **client 目录**：如果目录为空或缺少 index.html，自动复制默认前端文件

这意味着：
- ✅ 你可以直接挂载空目录，容器会自动初始化
- ✅ 挂载后，新增/修改的文件（如 SQLite 数据库）会持久化到宿主机
- ✅ 你可以随时替换挂载目录中的内容进行自定义

## 自定义配置

### 修改配置

1. 首次启动后，宿主机上会生成 `config.toml` 文件（从容器内复制出来）
2. 编辑 `config.toml` 进行自定义配置
3. 重启容器使配置生效：
```bash
docker compose restart
```

### 关键配置项

```toml
[frontend]
# Docker 环境必须监听 0.0.0.0（entrypoint 会自动修正）
listen_host = "0.0.0.0"
# 启动模式：default 或 backend
front_mode = "default"

[database]
# 默认使用 SQLite，数据文件位于 data/wordle.db
type = "sqlite"
sqlite_path = "data/wordle.db"

[auth]
# 设置你的管理员 Token 哈希
# 生成方式: echo -n "你的密码" | sha256sum
admin_token_hash = "your-sha256-hash-here"
```

### 使用 MySQL

如需使用 MySQL 数据库：

1. 在 `docker-compose.yml` 中取消 MySQL 服务的注释
2. 修改 `config.toml`：
```toml
[database]
type = "mysql"
host = "mysql"  # 使用 docker-compose 中的服务名
port = 3306
user = "wordle"
password = "your_password"
db = "wordle"
charset = "utf8mb4"
```
3. 重启服务

### 使用环境变量配置

可以通过环境变量覆盖配置（优先级高于 config.toml）：

```yaml
environment:
  - WORDLE_DB_TYPE=sqlite
  - WORDLE_AUTH_ENABLED=true
  - WORDLE_LOG_LEVEL=INFO
  - WORDLE_ADMIN_TOKEN_HASH=your_sha256_hash
```

## 自定义前端

如果你想自定义前端页面：

1. 先启动一次容器让默认文件复制到宿主机
2. 取消 `docker-compose.yml` 中 client 目录挂载的注释
3. 编辑 `client/` 目录下的文件进行自定义
4. 重启容器

## 构建与更新

### 重新构建镜像

```bash
docker compose build --no-cache
```

### 更新到新版本

```bash
# 拉取最新代码后重新构建
git pull
docker compose up -d --build
```

## 常见问题

### Q: 容器启动后无法访问？
A: 检查 config.toml 中的 `listen_host` 是否为 `0.0.0.0`，entrypoint 通常会自动修正这个问题。

### Q: 挂载 data 目录后数据库丢失？
A: 容器只会在目录缺少必要 JSON 文件时复制默认数据，不会覆盖已存在的 `wordle.db` 文件。

### Q: 如何查看容器日志？
A: `docker compose logs -f wordle`

### Q: 如何进入容器调试？
A: `docker compose exec wordle bash`

## 端口映射

默认容器内服务监听 8000 端口。如需映射到其他端口，修改 `docker-compose.yml`：

```yaml
ports:
  - "9000:8000"  # 宿主机 9000 端口映射到容器 8000 端口
```
