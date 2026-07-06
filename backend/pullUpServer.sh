pip install -r requirements.txt
uvicorn app.main:app --no-server-header --forwarded-allow-ips "*" --reload --port 8000