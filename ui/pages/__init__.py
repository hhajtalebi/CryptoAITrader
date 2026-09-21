"""
صفحات اصلی برنامه.

داشبورد، بازارها، تحلیل، سیگنال‌ها، چت هوشمند، تاریخچه معاملات، کیف پول،
گزارش‌ها، تنظیمات و راهنما.
"""

from ui.pages.analysis_page import AnalysisPage
from ui.pages.base_page import BasePage
from ui.pages.chat_page import ChatBubble, ChatPage
from ui.pages.dashboard_page import DashboardPage
from ui.pages.help_page import HelpPage
from ui.pages.markets_page import MarketsPage
from ui.pages.reports_page import ReportsPage
from ui.pages.settings_page import SettingsPage
from ui.pages.signals_page import SignalsPage
from ui.pages.trades_page import TradesPage
from ui.pages.wallet_page import WalletPage

__all__ = [
    "BasePage",
    "DashboardPage",
    "MarketsPage",
    "AnalysisPage",
    "SignalsPage",
    "ChatPage",
    "ChatBubble",
    "TradesPage",
    "WalletPage",
    "ReportsPage",
    "SettingsPage",
    "HelpPage",
]
