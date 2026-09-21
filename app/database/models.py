"""
تعریف جداول پایگاه داده با SQLAlchemy 2.x (سبک Declarative جدید).

اصول رعایت‌شده:
    • هیچ داده حساسی (کلید/رمز) در این جداول ذخیره نمی‌شود؛ فقط ارجاع و
      وضعیت. مقادیر واقعی در Secret Store سیستم‌عامل هستند.
    • همه زمان‌ها با UTC ذخیره می‌شوند تا در گزارش‌ها ابهام ایجاد نشود.
    • فیلدهای فهرست/دیکشنری به‌صورت JSON ذخیره می‌شوند تا ساختار جدول ساده
      بماند و افزودن فیلد جدید نیازمند Migration سنگین نباشد.

ارتباط با ماژول‌های دیگر:
    repositories روی این مدل‌ها کار می‌کنند و لایه سرویس فقط با Repository
    صحبت می‌کند.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    """زمان جاری UTC؛ به‌عنوان مقدار پیش‌فرض ستون‌های زمانی استفاده می‌شود."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """کلاس پایه تمام مدل‌های پایگاه داده."""

    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class TimestampMixin:
    """ستون‌های مشترک زمان ایجاد و به‌روزرسانی."""

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# تنظیمات
# ---------------------------------------------------------------------------
class SettingRecord(Base, TimestampMixin):
    """
    یک تنظیم کاربر به‌صورت کلید/مقدار.

    value به‌صورت JSON ذخیره می‌شود تا انواع مختلف (عدد، رشته، فهرست،
    دیکشنری) بدون نیاز به ستون‌های متعدد پشتیبانی شوند.
    is_user_modified مشخص می‌کند آیا کاربر این مقدار را تغییر داده است؛
    مقادیری که کاربر تغییر داده، هرگز توسط مقادیر پیش‌فرض بازنویسی نمی‌شوند.
    """

    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)
    category: Mapped[str] = mapped_column(String(40), default="general", nullable=False)
    is_user_modified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)


# ---------------------------------------------------------------------------
# ارائه‌دهندگان صرافی و هوش مصنوعی
# ---------------------------------------------------------------------------
class ExchangeProviderRecord(Base, TimestampMixin):
    """
    پیکربندی غیرحساس یک صرافی.

    توجه: has_credentials فقط یک پرچم است؛ خود کلید در Secret Store است.
    """

    __tablename__ = "exchange_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    rest_url: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    ws_url: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    has_credentials: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rate_limit_per_second: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    request_timeout: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    extra_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class AIProviderRecord(Base, TimestampMixin):
    """
    پیکربندی غیرحساس یک ارائه‌دهنده هوش مصنوعی.

    priority عدد کمتر یعنی اولویت بالاتر؛ زنجیره Fallback بر همین اساس
    مرتب می‌شود.
    """

    __tablename__ = "ai_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    provider_type: Mapped[str] = mapped_column(String(40), default="openai_compatible", nullable=False)
    base_url: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    model: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1600, nullable=False)
    timeout: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_api_key: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    has_credentials: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    extra_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


# ---------------------------------------------------------------------------
# نمادها و فهرست پیگیری
# ---------------------------------------------------------------------------
class SymbolRecord(Base, TimestampMixin):
    """اطلاعات پایه یک نماد معاملاتی که از صرافی همگام‌سازی می‌شود."""

    __tablename__ = "symbols"
    __table_args__ = (UniqueConstraint("exchange", "symbol", name="uq_symbol_exchange"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    exchange_symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    base_asset: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    price_precision: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    quantity_precision: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    min_order_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="symbol_ref", cascade="all, delete-orphan"
    )


class WatchlistItem(Base, TimestampMixin):
    """یک ردیف از فهرست پیگیری کاربر."""

    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("list_name", "symbol_id", name="uq_watchlist_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    list_name: Mapped[str] = mapped_column(String(60), default="default", index=True, nullable=False)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)

    symbol_ref: Mapped[SymbolRecord] = relationship(back_populates="watchlist_items")


# ---------------------------------------------------------------------------
# داده بازار
# ---------------------------------------------------------------------------
class CandleRecord(Base):
    """
    کندل ذخیره‌شده برای مشاهده در حالت آفلاین و کاهش درخواست‌های تکراری.

    برای جلوگیری از بزرگ شدن بی‌رویه پایگاه داده، سرویس نگهداری فقط تعداد
    محدودی کندل اخیر را برای هر نماد/تایم‌فریم نگه می‌دارد.
    """

    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("exchange", "symbol", "timeframe", "open_time", name="uq_candle_unique"),
        Index("ix_candles_lookup", "exchange", "symbol", "timeframe", "open_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    open_time: Mapped[int] = mapped_column(Integer, nullable=False)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)


class MarketDataSnapshot(Base):
    """
    آخرین وضعیت لحظه‌ای هر نماد (Ticker) برای نمایش سریع در حالت آفلاین.
    """

    __tablename__ = "market_data"
    __table_args__ = (UniqueConstraint("exchange", "symbol", name="uq_market_data_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    last_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    high_24h: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    low_24h: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    volume_24h: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    turnover_24h: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    change_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class IndicatorSnapshot(Base):
    """
    آخرین مقادیر محاسبه‌شده یک اندیکاتور، برای پرهیز از محاسبه تکراری.
    """

    __tablename__ = "indicators"
    __table_args__ = (
        UniqueConstraint("exchange", "symbol", "timeframe", "indicator", name="uq_indicator_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    indicator: Mapped[str] = mapped_column(String(40), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    latest_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    interpretation: Mapped[str] = mapped_column(String(40), default="NEUTRAL", nullable=False)
    candle_time: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


# ---------------------------------------------------------------------------
# سیگنال‌ها و تحلیل‌ها
# ---------------------------------------------------------------------------
class SignalRecord(Base, TimestampMixin):
    """
    یک سیگنال تولیدشده به همراه تمام اطلاعات لازم برای بازبینی بعدی.

    یادآوری: confidence صرفاً میزان هم‌راستایی عوامل تحلیلی است و تضمین
    موفقیت معامله نیست.
    """

    __tablename__ = "signals"
    __table_args__ = (Index("ix_signals_lookup", "symbol", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), default="lbank", nullable=False)
    direction: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    entry_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profits: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    risk_reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    leverage: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trend: Mapped[str] = mapped_column(String(20), default="NEUTRAL", nullable=False)
    market_structure: Mapped[str] = mapped_column(String(20), default="UNDEFINED", nullable=False)
    timeframes: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    indicators_used: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    ai_provider: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    ai_model: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    invalidation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OK", nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="engine", nullable=False)
    #: کوچک‌ترین تایم‌فریم تحلیل — سرعت کهنه‌شدن سیگنال را تعیین می‌کند
    primary_timeframe: Mapped[str] = mapped_column(String(10), default="", nullable=False)
    #: تا این لحظه ورود منطقی است؛ پس از آن سیگنال «سوخته» است
    enter_before: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    #: پس از این لحظه سیگنال هیچ اعتباری ندارد
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    #: پیش‌بینی بازهٔ محتمل قیمت برای افق‌های بعدی (خروجی signals.forecast)
    forecast: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)

    analysis: Mapped["SignalAnalysisRecord | None"] = relationship(
        back_populates="signal", cascade="all, delete-orphan", uselist=False
    )


class SignalOutcomeRecord(Base, TimestampMixin):
    """
    نتیجهٔ واقعی یک سیگنال پس از دنبال‌کردن قیمت.

    چرا جدول جدا و نه چند ستون روی `signals`؟
        نتیجه چرخهٔ عمر خودش را دارد: سیگنال یک بار ساخته می‌شود ولی
        نتیجه‌اش بارها به‌روز می‌شود (بیشترین سود شناور، نزدیک‌ترین
        فاصله تا حد ضرر، رسیدن به هدف‌های پی‌درپی). جداکردنش هم جدول
        سیگنال را سبک نگه می‌دارد و هم تاریخچهٔ پیگیری را شفاف می‌کند.

    تنها سنجش صادقانهٔ کیفیت موتور همین است: ضریب اطمینان یک ادعاست،
    این جدول واقعیت را ثبت می‌کند.
    """

    __tablename__ = "signal_outcomes"
    __table_args__ = (Index("ix_outcomes_status", "status", "checked_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[int] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    #: PENDING | TARGET | STOP | EXPIRED | CANCELLED
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    #: هدف‌های سیگنال، برای تشخیص رسیدن پله‌ای
    take_profits: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    #: چند هدف تا کنون لمس شده است
    targets_hit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    primary_timeframe: Mapped[str] = mapped_column(String(10), default="", nullable=False)
    #: قیمتی که سیگنال در آن بسته شد (هدف یا حد ضرر یا انقضا)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: درصد سود یا زیان **بدون** اهرم؛ اهرم انتخاب کاربر است نه سیگنال
    result_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    #: نسبت سود به ریسک واقعاً به‌دست‌آمده (بر حسب R)
    realized_r: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    #: بیشترین سود شناور در طول عمر سیگنال (درصد)
    max_favorable_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    #: بیشترین زیان شناور پیش از بسته‌شدن (درصد)
    max_adverse_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    #: آخرین قیمت دیده‌شده
    last_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    #: آخرین باری که قیمت بررسی شد
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    #: زمان بسته‌شدن
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    #: مهلت پیگیری؛ پس از آن سیگنال «منقضی» می‌شود
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    #: آیا نتیجه را کاربر دستی ثبت کرده است
    manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)


class SignalAnalysisRecord(Base, TimestampMixin):
    """
    متن کامل تحلیل و عکس لحظه‌ای داده‌ای که سیگنال بر اساس آن ساخته شد.

    نگهداری snapshot برای شفافیت ضروری است: بعداً می‌توان بررسی کرد که
    سیگنال با چه داده‌ای تولید شده است.
    """

    __tablename__ = "signal_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"), nullable=False)
    analysis_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    market_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    risk_assessment: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    ai_raw_response: Mapped[str] = mapped_column(Text, default="", nullable=False)
    data_timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    signal: Mapped[SignalRecord] = relationship(back_populates="analysis")


class SignalReviewRecord(Base, TimestampMixin):
    """
    بازبینی هوش مصنوعی روی یک سیگنالِ **بسته‌شده**.

    چرا جدا از `signal_analysis`؟
        آن جدول تحلیلِ *پیش از* معامله را نگه می‌دارد — یعنی پیش‌بینی.
        این جدول تحلیلِ *پس از* معامله را نگه می‌دارد — یعنی درس. دو
        چیز کاملاً متفاوت‌اند و قاتی‌کردنشان یعنی نتوانیم بپرسیم
        «پیش‌بینی‌هایمان چقدر درست بوده‌اند؟»

    کاربر خواست «سابقهٔ سیگنال باید دارای تحلیل با هوش مصنوعی باشد».
    مفیدترین شکل آن همین است: مدل نتیجهٔ واقعی را می‌بیند و توضیح
    می‌دهد چه چیزی درست یا غلط بود. بدون این، سابقه فقط فهرستی از
    عددهاست.
    """

    __tablename__ = "signal_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[int] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    #: وضعیت نتیجه هنگام بازبینی (TARGET | STOP | EXPIRED)
    outcome_status: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    #: متن درس‌آموخته، به زبان کاربر
    review_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    #: یک جملهٔ کوتاه برای نمایش در جدول سابقه
    verdict: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    #: دسته‌بندی درس: GOOD_SETUP | LATE_ENTRY | WEAK_STRUCTURE | BAD_TIMING | NOISE
    lesson: Mapped[str] = mapped_column(String(40), default="", index=True, nullable=False)
    ai_provider: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    ai_model: Mapped[str] = mapped_column(String(100), default="", nullable=False)


# ---------------------------------------------------------------------------
# گفت‌وگوهای هوش مصنوعی
# ---------------------------------------------------------------------------
class ChatConversationRecord(Base, TimestampMixin):
    """
    یک گفت‌وگو (نشست چت) با هوش مصنوعی.

    کاربر خواست تاریخچهٔ چت‌ها مانند ChatGPT نگهداری شود: فهرست گفت‌وگوها
    بر اساس زمان، امکان بازگشت به هر گفت‌وگو و امکان حذف.

    عنوان گفت‌وگو از نخستین پیام کاربر ساخته می‌شود تا فهرست قابل تشخیص
    باشد؛ کاربر می‌تواند بعداً آن را تغییر دهد.
    """

    __tablename__ = "chat_conversations"
    __table_args__ = (Index("ix_chat_conversations_time", "updated_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    symbol: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), default="", nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    messages: Mapped[list["ChatMessageRecord"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessageRecord.id",
    )


class ChatMessageRecord(Base):
    """
    یک پیام درون گفت‌وگو.

    نقش (role) یکی از user / assistant / system است. ابزارهایی که هوش
    مصنوعی برای پاسخ استفاده کرده در tools ذخیره می‌شود تا کاربر بعداً هم
    بتواند منبع پاسخ را ببیند.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_conversation", "conversation_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tools: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    model: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    conversation: Mapped[ChatConversationRecord] = relationship(back_populates="messages")


# ---------------------------------------------------------------------------
# گزارش، پشتیبان و لاگ
# ---------------------------------------------------------------------------
class ReportRecord(Base, TimestampMixin):
    """سابقه گزارش‌های تولید و خروجی‌گرفته‌شده."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(150), default="", nullable=False)
    report_type: Mapped[str] = mapped_column(String(40), default="signals", nullable=False)
    export_format: Mapped[str] = mapped_column(String(10), default="csv", nullable=False)
    file_path: Mapped[str] = mapped_column(String(400), default="", nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class BackupHistory(Base, TimestampMixin):
    """سابقه نسخه‌های پشتیبان تهیه‌شده."""

    __tablename__ = "backup_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_path: Mapped[str] = mapped_column(String(400), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    backup_type: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)


class ApplicationLog(Base):
    """
    ثبت رویدادهای مهم برنامه در پایگاه داده.

    فقط رویدادهای سطح WARNING به بالا اینجا ذخیره می‌شوند تا پایگاه داده
    سبک بماند؛ جزئیات کامل در فایل لاگ است.
    """

    __tablename__ = "application_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    logger_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True, nullable=False)


# ---------------------------------------------------------------------------
# کاربران و نشست‌ها
# ---------------------------------------------------------------------------
class UserRecord(Base, TimestampMixin):
    """
    حساب کاربری محلی برنامه.

    امنیت:
        رمز عبور هرگز ذخیره نمی‌شود؛ فقط چکیده PBKDF2-HMAC-SHA256 همراه
        نمک تصادفی و تعداد تکرار نگهداری می‌گردد تا در آینده بتوان تعداد
        تکرار را بدون باطل‌کردن رمزهای موجود بالا برد.

    چرا کاربر محلی؟
        داده هر کاربر (حساب صرافی، ترجیحات، پوسته) از دیگری جدا می‌ماند
        بدون آنکه برنامه به سرور نیاز پیدا کند.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    password_salt: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    password_iterations: Mapped[int] = mapped_column(Integer, default=390000, nullable=False)
    password_algorithm: Mapped[str] = mapped_column(String(30), default="pbkdf2_sha256", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: ترجیحات کاربر (پوسته، زبان، منطقه زمانی، اعلان‌ها، تنظیمات معاملاتی)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sessions: Mapped[list["UserSessionRecord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    exchange_accounts: Mapped[list["ExchangeAccountRecord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSessionRecord(Base):
    """
    نشست ورود کاربر.

    «مرا به خاطر بسپار» با نگهداری توکن نشست پیاده می‌شود؛ خود توکن
    به‌صورت چکیده ذخیره می‌گردد تا خواندن پایگاه داده امکان جعل نشست را
    ندهد.
    """

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    device_label: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["UserRecord"] = relationship(back_populates="sessions")


class ExchangeAccountRecord(Base, TimestampMixin):
    """
    اتصال یک کاربر به یک صرافی.

    امنیت:
        کلید و رمز API هرگز اینجا نوشته نمی‌شوند. تنها `secret_ref` ذخیره
        می‌شود که کلید جستجو در Secret Store رمزنگاری‌شده است، به‌همراه
        `api_key_masked` که فقط برای نمایش در رابط کاربری است
        (مثل ``abcd••••wxyz``).

    چرا جدا از `exchange_providers`؟
        آن جدول پیکربندی سراسری صرافی است؛ این جدول مالکیت کاربر را
        نگه می‌دارد. یک صرافی می‌تواند چند حساب از چند کاربر داشته باشد.
    """

    __tablename__ = "exchange_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "exchange", "label", name="uq_exchange_account"),
        Index("ix_exchange_accounts_user_exchange", "user_id", "exchange"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    exchange: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    #: ارجاع به رمز در Secret Store — نه خود رمز
    secret_ref: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    #: نسخه پوشیده کلید فقط برای نمایش
    api_key_masked: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    #: فقط خواندن — از سفارش‌گذاری واقعی جلوگیری می‌کند
    read_only: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="disconnected", nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    #: خلاصه دارایی‌ها در آخرین همگام‌سازی (برای نمایش آفلاین)
    balances: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    total_value_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    permissions: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    extra_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    user: Mapped["UserRecord"] = relationship(back_populates="exchange_accounts")


class PaperTradeRecord(Base, TimestampMixin):
    """
    معامله کاغذی (شبیه‌سازی‌شده).

    کاربر خواسته است دکمه «معامله» فعلاً فقط معامله کاغذی ثبت کند؛ ساختار
    طوری است که با روشن‌شدن سفارش‌گذاری واقعی، تنها منبع پرشدن تغییر کند
    و صفحه تاریخچه دست‌نخورده بماند.
    """

    __tablename__ = "paper_trades"
    __table_args__ = (
        Index("ix_paper_trades_user_time", "user_id", "opened_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("exchange_accounts.id", ondelete="SET NULL"), nullable=True
    )
    signal_id: Mapped[int | None] = mapped_column(
        ForeignKey("signals.id", ondelete="SET NULL"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    side: Mapped[str] = mapped_column(String(10), default="long", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(10), default="paper", nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    leverage: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    fee: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    pnl_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    #: آخرین قیمت دیده‌شدهٔ بازار برای معاملهٔ باز.
    #: بدون این، ستون سود/زیان تا لحظهٔ بستن خالی می‌ماند.
    last_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
