#!/bin/bash
set -euo pipefail
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BASE_DIR"
systemctl --user start be-more-hailo-ollama.service
for attempt in {1..30}; do
    if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null; then break; fi
    sleep 1
done
curl -fsS http://127.0.0.1:11434/api/tags >/dev/null
exec "$BASE_DIR/venv/bin/python" -m uvicorn web_app:app --host 127.0.0.1 --port 8080 "$@"
