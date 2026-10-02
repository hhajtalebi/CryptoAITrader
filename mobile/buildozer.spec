[app]

# --- هویت برنامه ---
title = معامله‌گر هوشمند رمزارز
package.name = cryptoaitrader
package.domain = ir.hajtalebi

source.dir = .
source.include_exts = py,png,jpg,ttf,json,txt
source.include_patterns = assets/*,app/*

version.regex = ^VERSION = ['"](.*)['"]
version.filename = %(source.dir)s/version.py

# --- وابستگی‌ها ---
#  عمداً کوتاه است. هر مورد اضافه یک دستور ساخت تازه روی اندروید است و
#  هر کدام یک جای شکستن.
#
#  مهم: pandas و numpy اینجا **نیستند**. موتور اندیکاتور در
#  `app/indicators_lite.py` با پایتون خالص نوشته شده و هم‌ارزی عددی‌اش
#  با نسخهٔ دسکتاپ آزمون دارد. تلاش برای ساخت pandas روی اندروید،
#  شناخته‌شده‌ترین راه شکست خوردن این نوع پروژه است.
# نسخهٔ ۲.۵.۳: python-bidi ≥ 0.5 با Rust ساخته می‌شود و python-for-android
# نمی‌تواند کامپایلش کند؛ 0.4.2 پایتون خالص است (همان API: bidi.algorithm).
requirements = python3,kivy==2.3.0,openssl,certifi,arabic_reshaper,python-bidi==0.4.2

orientation = portrait
fullscreen = 0

# --- اندروید ---
#  INTERNET تنها مجوز لازم است. هیچ دسترسی دیگری خواسته نمی‌شود.
android.permissions = INTERNET,ACCESS_NETWORK_STATE

#  API 31 کف امن امروز است و 34 هدف فروشگاه.
android.api = 34
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a
# نسخهٔ ۲.۵.۳: بدون این، buildozer برای پذیرش مجوز SDK منتظر ورودی می‌ماند و
# در ربات ساخت (بدون ورودی) گیر می‌کند یا شکست می‌خورد.
android.accept_sdk_license = True

#  اجازهٔ ترافیک HTTPS؛ پاک‌متن لازم نیست.
android.allow_backup = True

presplash.filename = %(source.dir)s/assets/presplash.png
icon.filename = %(source.dir)s/assets/icon.png

[buildozer]
log_level = 2
# ربات ساخت ورودی ندارد؛ پرسش «با root ادامه می‌دهید؟» ساخت را می‌کشت.
warn_on_root = 0
