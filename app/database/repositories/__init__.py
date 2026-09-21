"""
مخازن داده (Repository Pattern).

هر مخزن مسئول یک موجودیت است و تنها نقطه دسترسی به پایگاه داده برای
لایه‌های بالاتر محسوب می‌شود. مزیت این کار:
    • تست‌پذیری (می‌توان مخزن جعلی جایگزین کرد)
    • جلوگیری از پخش شدن Query در سراسر پروژه
    • امکان تغییر پایگاه داده در آینده بدون دست‌زدن به لایه سرویس
"""

from app.database.repositories.base import BaseRepository
from app.database.repositories.candle_repository import CandleRepository
from app.database.repositories.chat_repository import ChatRepository
from app.database.repositories.provider_repository import (
    AIProviderRepository,
    ExchangeProviderRepository,
)
from app.database.repositories.outcome_repository import SignalOutcomeRepository
from app.database.repositories.review_repository import SignalReviewRepository
from app.database.repositories.settings_repository import SettingsRepository
from app.database.repositories.signal_repository import SignalRepository
from app.database.repositories.symbol_repository import SymbolRepository
from app.database.repositories.trade_repository import PaperTradeRepository
from app.database.repositories.user_repository import (
    ExchangeAccountRepository,
    UserRepository,
)
from app.database.repositories.system_repository import (
    BackupHistoryRepository,
    ReportRepository,
)

__all__ = [
    "BaseRepository",
    "SettingsRepository",
    "SymbolRepository",
    "CandleRepository",
    "ChatRepository",
    "SignalRepository",
    "SignalOutcomeRepository",
    "SignalReviewRepository",
    "ExchangeProviderRepository",
    "AIProviderRepository",
    "BackupHistoryRepository",
    "ReportRepository",
    "UserRepository",
    "ExchangeAccountRepository",
    "PaperTradeRepository",
]
