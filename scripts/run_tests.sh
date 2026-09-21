#!/usr/bin/env bash
# اجرای کامل آزمون‌ها در یک پوشه داده موقت.
#
# پوشه موقت لازم است تا آزمون‌ها هرگز به پایگاه داده واقعی کاربر دست نزنند.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -d .venv ]] && source .venv/bin/activate

export CAT_DATA_DIR="$(mktemp -d)"
export QT_QPA_PLATFORM=offscreen
trap 'rm -rf "$CAT_DATA_DIR"' EXIT

echo "پوشه داده آزمون: $CAT_DATA_DIR"
python -m pytest tests "$@"
