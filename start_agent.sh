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
export DISPLAY="${DISPLAY:-:0}"
exec "$BASE_DIR/venv/bin/python" agent_hailo.py "$@"
