#!/bin/sh
set -u

JOB="${1:-}"
if [ -z "$JOB" ]; then
  echo "missing job name" >&2
  exit 2
fi

if [ -z "${DATABASE_URL:-}" ]; then echo "missing DATABASE_URL" >&2; exit 2; fi
if [ -z "${AWS_ACCESS_KEY_ID:-}" ]; then echo "missing AWS_ACCESS_KEY_ID" >&2; exit 2; fi
if [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; then echo "missing AWS_SECRET_ACCESS_KEY" >&2; exit 2; fi
if [ -z "${R2_ACCOUNT_ID:-}" ]; then echo "missing R2_ACCOUNT_ID" >&2; exit 2; fi
if [ -z "${R2_BUCKET_NAME:-}" ]; then echo "missing R2_BUCKET_NAME" >&2; exit 2; fi

mkdir -p /mnt/r2
R2_ENDPOINT="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

echo "[cloudflare] mounting R2 bucket: ${R2_BUCKET_NAME}"
tigrisfs --endpoint "$R2_ENDPOINT" -f "$R2_BUCKET_NAME" /mnt/r2 &
FUSE_PID=$!

cleanup() {
  fusermount3 -u /mnt/r2 >/dev/null 2>&1 || true
  kill "$FUSE_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

i=0
while [ "$i" -lt 30 ]; do
  if mountpoint -q /mnt/r2; then
    break
  fi
  i=$((i + 1))
  sleep 0.2
done

if ! mountpoint -q /mnt/r2; then
  echo "[cloudflare] R2 mount failed" >&2
  exit 1
fi

export RAW_DATA_DIR="${RAW_DATA_DIR:-/mnt/r2/raw}"
mkdir -p "$RAW_DATA_DIR"

run_step() {
  name="$1"
  shift
  echo "[job:$JOB] >>> $name"
  "$@"
  code=$?
  if [ "$code" -ne 0 ]; then
    echo "[job:$JOB] !!! $name failed with exit code $code" >&2
  else
    echo "[job:$JOB] <<< $name complete"
  fi
  return "$code"
}

case "$JOB" in
  daily)
    TRADE_DATE="$(python - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo
print(datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat())
PY
)"
    rc=0
    run_step "sync-szse-master" python -m stock_data.cli sync-szse-master || rc=1
    run_step "sync-sse-master" python -m stock_data.cli sync-sse-master || rc=1
    run_step "sync-sse-daily" python -m stock_data.cli sync-sse-daily || rc=1
    run_step "sync-szse-daily:$TRADE_DATE" python -m stock_data.cli sync-szse-daily --date "$TRADE_DATE" || rc=1
    exit "$rc"
    ;;
  history-szse)
    exec python -m stock_data.cli bootstrap-baostock --exchange SZSE --start 1991-01-01 --end "${HISTORY_END:-2025-08-31}" --batch-size "${HISTORY_BATCH_SIZE:-50}" --delay "${HISTORY_DELAY_SECONDS:-10}" --retries "${HISTORY_RETRIES:-1}"
    ;;
  history-sse)
    exec python -m stock_data.cli bootstrap-baostock --exchange SSE --start 1990-12-19 --end "${HISTORY_END:-2025-08-31}" --batch-size "${HISTORY_BATCH_SIZE:-50}" --delay "${HISTORY_DELAY_SECONDS:-10}" --retries "${HISTORY_RETRIES:-1}"
    ;;
  master)
    rc=0
    run_step "sync-szse-master" python -m stock_data.cli sync-szse-master || rc=1
    run_step "sync-sse-master" python -m stock_data.cli sync-sse-master || rc=1
    exit "$rc"
    ;;
  migrate)
    exec python -m stock_data.cli migrate
    ;;
  *)
    echo "unknown job: $JOB" >&2
    exit 2
    ;;
esac
