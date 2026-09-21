"""
ثبت کلید یک سرویس هوش مصنوعی به‌صورت رمزنگاری‌شده.

کلید در پایگاه دادهٔ برنامه و رمزنگاری‌شده ذخیره می‌شود؛ هیچ‌جا به‌صورت
متن ساده نوشته نمی‌شود و در لاگ هم نمی‌آید.

اجرا:
    python tools/set_ai_key.py openrouter sk-or-v1-...
    python tools/set_ai_key.py openrouter sk-or-v1-... --model "nex-agi/nex-n2.5-pro:free"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    """خواندن آرگومان‌ها و ذخیرهٔ کلید."""
    parser = argparse.ArgumentParser(description="ثبت کلید سرویس هوش مصنوعی")
    parser.add_argument("provider", help="نام سرویس، مثلاً openrouter")
    parser.add_argument("api_key", help="کلید API")
    parser.add_argument("--model", default="", help="مدل پیش‌فرض (اختیاری)")
    parser.add_argument(
        "--activate",
        action="store_true",
        default=True,
        help="همین سرویس را سرویس فعال کن",
    )
    args = parser.parse_args()

    from app.application import Application

    app = Application()
    app.secrets.set(f"ai.{args.provider}.api_key", args.api_key)
    app.settings.set("ai.enabled", True)
    if args.activate:
        app.settings.set("ai.provider", args.provider)
        # نشانی را خالی می‌گذاریم تا نشانی درستِ همان سرویس از کاتالوگ بیاید
        app.settings.set("ai.base_url", "")
    if args.model:
        app.settings.set("ai.model", args.model)

    masked = args.api_key[:6] + "…" + args.api_key[-4:]
    print(f"کلید سرویس «{args.provider}» ذخیره شد ({masked}).")
    if args.model:
        print(f"مدل پیش‌فرض: {args.model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
