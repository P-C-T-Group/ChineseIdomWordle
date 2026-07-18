pip3 install -r requirements.txt
mkdir -p logs
# 统一配置：读取 backend/config.toml（不存在则使用默认值）
uvicorn app.main:app --no-server-header --forwarded-allow-ips "*" --reload --port 8000