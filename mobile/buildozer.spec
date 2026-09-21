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
requirements = python3,kivy==2.3.0,openssl,certifi,arabic_reshaper,python-bidi

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

#  اجازهٔ ترافیک HTTPS؛ پاک‌متن لازم نیست.
android.allow_backup = True

presplash.filename = %(source.dir)s/assets/presplash.png
icon.filename = %(source.dir)s/assets/icon.png

[buildozer]
log_level = 2
warn_on_root = 1
