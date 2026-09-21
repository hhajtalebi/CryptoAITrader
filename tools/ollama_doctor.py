"""
پزشک اولاما — تشخیص قطعی، روی دستگاه خود کاربر.

چرا این ابزار وجود دارد؟
    سه نسخه پشت سر هم، علت «در ترمینال کار می‌کند، در برنامه نه» را از
    روی شواهد غیرمستقیم حدس زدم و هر سه بار بخشی از ماجرا را اشتباه
    فهمیدم. مشکل این بود که من دستگاه کاربر را نمی‌بینم: نه VRAM، نه
    درایور، نه رفتار واقعی مدل زیر بار.

    این ابزار به‌جای حدس، **اندازه می‌گیرد**. دقیقاً همان درخواستی را
    می‌فرستد که برنامه می‌فرستد، ولی پله‌پله: از کوچک‌ترین حالت ممکن تا
    بار کامل. اولین پله‌ای که می‌شکند، علت را لو می‌دهد.

اجرا:
    python tools/ollama_doctor.py

خروجی یک گزارش متنی است که می‌توان مستقیم کپی کرد و فرستاد.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:11434"
TIMEOUT = 300


def _post(path: str, payload: dict) -> tuple[int, str, float]:
    """یک درخواست POST و بازگرداندن (کد وضعیت، بدنه، ثانیه)."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BASE_URL + path, data=data, headers={"Content-Type": "application/json"}
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read().decode("utf-8", "replace"), time.monotonic() - started
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace"), time.monotonic() - started
    except Exception as exc:  # noqa: BLE001 - گزارش، نه توقف
        return 0, f"{exc.__class__.__name__}: {exc}", time.monotonic() - started


def _get(path: str) -> tuple[int, str]:
    """یک درخواست GET."""
    try:
        with urllib.request.urlopen(BASE_URL + path, timeout=30) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return 0, f"{exc.__class__.__name__}: {exc}"


def _short(text: str, limit: int = 200) -> str:
    """کوتاه‌کردن متن خطا برای نمایش."""
    cleaned = " ".join(str(text).split())
    return cleaned[:limit]


def main() -> int:
    """اجرای پله‌به‌پله و چاپ گزارش."""
    print("=" * 72)
    print("پزشک اولاما — گزارش تشخیصی")
    print("=" * 72)

    # ---- گام ۱: آیا سرویس بالاست؟ ----
    status, body = _get("/")
    print(f"\n[۱] سرویس روی {BASE_URL} : ", end="")
    if status == 200:
        print(f"بالاست ({_short(body, 40)})")
    else:
        print(f"در دسترس نیست — {_short(body)}")
        print("\nنتیجه: اولاما اجرا نیست. `ollama serve` را اجرا کنید.")
        return 1

    # ---- گام ۲: چه مدل‌هایی نصب است؟ ----
    status, body = _get("/api/tags")
    models: list[str] = []
    if status == 200:
        try:
            models = [m.get("name", "") for m in json.loads(body).get("models", [])]
        except ValueError:
            pass
    print(f"[۲] مدل‌های نصب‌شده : {', '.join(models) if models else 'هیچ'}")
    if not models:
        print("\nنتیجه: هیچ مدلی نصب نیست.")
        return 1

    # ---- گام ۳: مدل‌های در حال اجرا و محل اجرا (GPU یا CPU) ----
    status, body = _get("/api/ps")
    print("[۳] مدل‌های بارگذاری‌شده :", end=" ")
    if status == 200:
        try:
            running = json.loads(body).get("models", [])
            if not running:
                print("هیچ (حافظه خالی است)")
            for item in running:
                size = item.get("size", 0) / 1024**3
                vram = item.get("size_vram", 0) / 1024**3
                where = "کاملاً روی GPU" if vram >= size * 0.99 else (
                    "کاملاً روی CPU" if vram <= 0.01 else
                    f"تقسیم‌شده: {vram/size*100:.0f}% GPU"
                )
                print(f"\n      {item.get('name')}: {size:.1f}G ({where})")
        except ValueError:
            print(_short(body))
    else:
        print(_short(body))

    # ---- گام ۴: پله‌های بار، از سبک به سنگین ----
    target = models[0]
    for preferred in ("gemma4:e4b-it-qat", "llama3.1:8b", "deepseek-coder:6.7b"):
        if preferred in models:
            target = preferred
            break

    print(f"\n[۴] آزمون پله‌ای روی «{target}»")
    print("    هر پله دقیقاً شکل درخواست برنامه را دارد، فقط بزرگ‌تر.\n")

    system_prompt = "You are a trading assistant. " * 125  # ≈ ۱۲۲۰ توکن، مثل برنامه
    steps = [
        ("۴٫۱  پیام کوتاه، بدون گزینه (مثل ollama run)", [{"role": "user", "content": "سلام"}], {}),
        ("۴٫۲  پیام کوتاه + num_predict", [{"role": "user", "content": "سلام"}], {"num_predict": 1600}),
        ("۴٫۳  پیام سیستمی کامل برنامه", [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "تحلیل BTC/USDT"},
        ], {"num_predict": 1600}),
        ("۴٫۴  + نتیجهٔ ابزار (پرامپت بزرگ)", [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "تحلیل BTC/USDT"},
            {"role": "assistant", "content": "بررسی می‌کنم."},
            {"role": "user", "content": "Tool results:\n" + "قیمت ۷۶۰۰۰ دلار. " * 400},
        ], {"num_predict": 1600}),
    ]

    first_failure = None
    for label, messages, options in steps:
        payload = {
            "model": target,
            "messages": messages,
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0.2, **options},
        }
        chars = sum(len(m["content"]) for m in messages)
        print(f"    {label}")
        print(f"         حجم پرامپت: {chars:,} نویسه", end=" ... ", flush=True)
        status, body, seconds = _post("/api/chat", payload)
        if status == 200:
            print(f"موفق ({seconds:.1f}s)")
        else:
            print(f"شکست — HTTP {status} پس از {seconds:.1f}s")
            print(f"         پیام اولاما: {_short(body)}")
            if first_failure is None:
                first_failure = label
            break

    # ---- نتیجه‌گیری ----
    print("\n" + "=" * 72)
    if first_failure is None:
        print("نتیجه: همهٔ پله‌ها موفق بودند.")
        print("یعنی اولاما با بار کامل برنامه هم سالم کار می‌کند و مشکل")
        print("جای دیگری است. این گزارش را بفرستید.")
    else:
        print(f"نتیجه: اولین شکست در «{first_failure.strip()}» رخ داد.")
        print()
        if first_failure.startswith("۴٫۱"):
            print("حتی سبک‌ترین درخواست هم شکست — مشکل از خود اولاما یا")
            print("درایور کارت گرافیک است، نه از برنامه.")
        else:
            print("درخواست سبک موفق بود ولی سنگین‌تر شکست. یعنی مدل زیر بار")
            print("واقعی دوام نمی‌آورد. روی کارت‌های کم‌حافظه معمول است.")
        print()
        print("دو راه‌حل که بیشترین اثر را دارند:")
        print()
        print("  ۱) خاموش‌کردن Vulkan و اجرای کامل روی CPU (پایدارترین):")
        print("       $env:OLLAMA_VULKAN=\"false\"")
        print("       ollama serve")
        print()
        print("  ۲) مدل کوچک‌تر:")
        print("       ollama pull llama3.2:3b")
        print()
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
