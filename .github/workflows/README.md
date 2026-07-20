# GitHub Actions Docker 自动构建说明

## 功能

- 每次推送到 `main` 分支自动构建镜像并推送到 GHCR
- 自动递增版本号：如果最新 release 是 `2.0`，则构建的镜像 tag 为 `2.0.1`、`2.0.2`...
- 同时更新 `latest` 标签
- 支持多架构构建（amd64/arm64）
- 自动使用国内镜像源加速构建

## 初始设置

### 1. 启用 GitHub Packages 写入权限

在仓库设置中确保 Actions 有 Packages 写入权限：
1. 进入仓库 → Settings → Actions → General
2. 找到 "Workflow permissions"
3. 选择 "Read and write permissions"
4. 保存

### 2. 创建 Release（可选）

版本号基于最新 release：
- 如果当前最新 release tag 是 `v2.0`，第一个镜像 tag 是 `2.0.1`
- 如果没有 release，版本从 `0.0.1` 开始

### 3. 查看镜像

镜像地址：
- 所有版本：https://github.com/orgs/P-C-T-Group/packages/container/package/c-i-wordle
- 拉取命令：`docker pull ghcr.io/p-c-t-group/c-i-wordle:latest`

## 使用构建好的镜像

### docker-compose.yml 示例

```yaml
services:
  wordle:
    image: ghcr.io/p-c-t-group/c-i-wordle:latest
    container_name: chinese-idiom-wordle
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      # 需要自定义配置时再挂载
      # - ./config.toml:/app/config.toml
```

### 仅使用 Docker

```bash
docker run -d \
  --name chinese-idiom-wordle \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  ghcr.io/p-c-t-group/c-i-wordle:latest
```

## 手动触发

除了推送到 main 分支自动触发，也可以在 GitHub 网页上手动运行：
1. 进入仓库 → Actions → "Build and Push Docker Image"
2. 点击 "Run workflow" 选择 main 分支运行
