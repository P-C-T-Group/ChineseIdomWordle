pip3 install -r requirements.txt
mkdir -p logs
uvicorn app.main:app --no-server-header --forwarded-allow-ips "*" --reload --port 8000 --log-config uvicorn_config.json --env-file .env