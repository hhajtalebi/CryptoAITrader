"""
لایه بومی‌سازی (Localization).

طبق بند ۴۱ سند پروژه، هیچ رشته‌ای نباید در کد رابط کاربری Hard-Code شود.
همه متن‌ها از فایل‌های JSON این پوشه خوانده می‌شوند:

    localization/fa/*.json    فارسی (راست‌به‌چپ)
    localization/en/*.json    انگلیسی (چپ‌به‌راست)
"""

from localization.translator import Translator, get_translator, tr

__all__ = ["Translator", "get_translator", "tr"]
