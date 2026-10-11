#!/bin/bash
# =================================================================
#  Crypto AI Trader 2.7.1 — ساخت خودکارِ محیط مجازی (لینوکس/مک)
# =================================================================
#
#  استفاده:  bash setup_env.sh
#  بعد از آن: source venv/bin/activate  و سپس  python main.py
#
# =================================================================
set -euo pipefail

echo "=== Crypto AI Trader 2.7.1 — آماده‌سازی محیط ==="

PY=python3
command -v "$PY" >/dev/null 2>&1 || { echo "[خطا] پایتون 3 پیدا نشد."; exit 1; }

VER=$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
echo "پایتون شناسایی‌شده: $VER"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
  || { echo "[خطا] پایتون 3.11 یا بالاتر لازم است."; exit 1; }

[ -d venv ] && { echo "پوشه‌ی venv از قبل وجود دارد؛ حذف و ساخت دوباره..."; rm -rf venv; }

echo "در حال ساخت محیط مجازی..."
"$PY" -m venv venv
./venv/bin/python -m pip install --upgrade pip wheel setuptools

if [ -f requirements.lock.txt ]; then
    echo "نصب با نسخه‌های قفل‌شده (requirements.lock.txt)..."
    ./venv/bin/python -m pip install -r requirements.lock.txt
else
    echo "فایل قفل پیدا نشد؛ نصب با requirements.txt..."
    ./venv/bin/python -m pip install -r requirements.txt
fi

echo
echo "=== محیط آماده است ==="
echo
echo "  source venv/bin/activate"
echo "  python main.py"
echo
echo "بررسی سلامت:   ./venv/bin/python main.py --check"
echo "اجرای آزمون‌ها: ./venv/bin/python -m pytest tests -q"
echo
