"""
موتور Prompt.

طبق بند ۲۰ سند پروژه، Promptها نباید در کد Hard-Code شوند. آن‌ها اینجا
به‌صورت فایل متنی نسخه‌بندی‌شده نگهداری می‌شوند تا کاربر یا توسعه‌دهنده
بتواند بدون تغییر کد آن‌ها را ویرایش کند.
"""

from ai.prompts.prompt_manager import PromptManager, PromptTemplate

__all__ = ["PromptManager", "PromptTemplate"]
