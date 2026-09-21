"""
لایه پایگاه داده نرم‌افزار (SQLite + SQLAlchemy).

این لایه شامل تعریف جداول (models)، مدیریت نشست (session) و مخازن داده
(repositories) است. لایه‌های بالاتر هرگز نباید مستقیماً Query خام بنویسند؛
دسترسی فقط از طریق Repository انجام می‌شود (الگوی Repository).
"""

from app.database.models import (
    AIProviderRecord,
    ApplicationLog,
    BackupHistory,
    Base,
    CandleRecord,
    ExchangeAccountRecord,
    ExchangeProviderRecord,
    PaperTradeRecord,
    ReportRecord,
    SettingRecord,
    SignalAnalysisRecord,
    SignalOutcomeRecord,
    SignalRecord,
    SymbolRecord,
    UserRecord,
    UserSessionRecord,
    WatchlistItem,
)
from app.database.session import DatabaseManager, get_database_manager

__all__ = [
    "Base",
    "SettingRecord",
    "ExchangeProviderRecord",
    "ExchangeAccountRecord",
    "PaperTradeRecord",
    "UserRecord",
    "UserSessionRecord",
    "AIProviderRecord",
    "SymbolRecord",
    "WatchlistItem",
    "CandleRecord",
    "SignalRecord",
    "SignalAnalysisRecord",
    "SignalOutcomeRecord",
    "ReportRecord",
    "BackupHistory",
    "ApplicationLog",
    "DatabaseManager",
    "get_database_manager",
]
