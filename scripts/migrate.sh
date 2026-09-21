#!/usr/bin/env bash
# اجرای مهاجرت‌های پایگاه داده.
#
# پیش از هر مهاجرت، برنامه خودش یک نسخه پشتیبان می‌سازد؛ این اسکریپت
# فقط alembic را با پوشه داده درست اجرا می‌کند.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -d .venv ]] && source .venv/bin/activate
exec alembic "${@:-upgrade head}"
