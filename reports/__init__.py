"""
لایه گزارش‌گیری.

خروجی در پنج قالب پشتیبانی می‌شود: CSV، Excel، JSON، PDF و HTML.
همه گزارش‌ها شامل سلب مسئولیت هستند: تحلیل تکنیکال، توصیه مالی نیست.
"""

from reports.builder import ReportBuilder, ReportData
from reports.exporters import ReportExporter

__all__ = ["ReportBuilder", "ReportData", "ReportExporter"]
