#!/usr/bin/env bash
# ======================================================================
#  ساخت نسخه اجرایی — Crypto AI Trader (لینوکس و مک، برای توسعه)
#
#  نسخه رسمی ویندوز باید روی خود ویندوز ساخته شود؛ PyInstaller
#  کراس‌کامپایل نمی‌کند.
# ======================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"

echo "[1/4] محیط مجازی…"
[[ -d .venv ]] || "$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[2/4] وابستگی‌ها…"
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet

echo "[3/4] آزمون‌ها…"
if [[ "${SKIP_TESTS:-0}" != "1" ]]; then
    QT_QPA_PLATFORM=offscreen python -m pytest tests -q
fi

echo "[4/4] بسته‌بندی…"
rm -rf build dist
python -m PyInstaller CryptoAITrader.spec --noconfirm --clean

echo
echo "خروجی: $(pwd)/dist/CryptoAITrader/"
