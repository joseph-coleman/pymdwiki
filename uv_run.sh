set -a 
source .env 2>/dev/null || echo ".env file not found, using defaults"
set +a

PORT="${PORT:-8000}"

cd app
uv run uvicorn main:app --host 0.0.0.0 --port "$PORT" --reload