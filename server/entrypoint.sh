#!/bin/sh
set -e
# Migrations run on every boot. Alembic is idempotent — already-applied
# revisions are skipped — so this is safe to repeat and means a deploy is just
# "docker compose up -d --build".
echo "running migrations…"
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8080 \
     --proxy-headers --forwarded-allow-ips '*'
