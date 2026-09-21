#!/usr/bin/env bash
# اجرای برنامه در حالت توسعه با گزارش کامل.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -d .venv ]] && source .venv/bin/activate
export CAT_LOG_LEVEL="${CAT_LOG_LEVEL:-DEBUG}"
exec python main.py --log-level "${CAT_LOG_LEVEL}" "$@"
