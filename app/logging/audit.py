"""
لاگ ممیزی معاملات و اسکالپ — نسخهٔ ۲.۶.۰.

هدف: برای هر سیگنال، نامزد، رد، ورود و خروج دقیقاً بدانیم «چرا».

    Market Data → Signal → Candidate → Filters → Risk → Entry → Position → Exit

- هر رد یک **کد استاندارد** دارد (`REASON_CODES`). دلیل خام موتور (مثلاً
  `spread_eats_stop:0.123%`) در `reason_detail` می‌ماند تا عدد از دست نرود.
- هر کد در یک **سطل** خلاصهٔ پویش است (`REASON_BUCKETS`): volatility, cost,
  spread, trend, confidence, liquidity, edge, risk, target, orderbook, data, other.
- رویدادهای یک تلاش ورود با `correlation_id` به هم و به `trade_id` وصل‌اند؛
  پس خط زمانی Signal → Candidate → Validation → Entry → Monitoring → Exit
  برای هر معامله بازسازی می‌شود.
- **هیچ تابعی در این ماژول استثنا بیرون نمی‌دهد.** خطای لاگ نباید موتور معامله
  را متوقف کند.
- این ماژول هیچ تصمیم معاملاتی نمی‌گیرد و هیچ آستانه‌ای را عوض نمی‌کند؛ فقط ثبت می‌کند.
"""

from __future__ import annotations

import contextvars
import itertools
import logging
import os
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from app.logging.categories import LogCategory

_logger = logging.getLogger("audit")

# ---------------------------------------------------------------------------
# کدهای استاندارد رد
# ---------------------------------------------------------------------------

#: کد استاندارد → سطل خلاصهٔ پویش
REASON_BUCKETS: dict[str, str] = {
    # داده
    "stale_data": "data",
    "stale_candidate": "data",
    "no_price": "data",
    "data_error": "data",
    "invalid_candidate": "data",
    # نوسان / حرکت
    "low_volatility": "volatility",
    "high_volatility": "volatility",
    "low_momentum": "volatility",
    # هزینه
    "cost_too_high": "cost",
    "negative_expectancy": "cost",
    "fees_exceed_budget": "cost",
    # اسپرد
    "wide_spread": "spread",
    "spread_eats_stop": "spread",
    # روند / جهت
    "trend_conflict": "trend",
    "no_direction": "trend",
    # اطمینان
    "low_confidence": "confidence",
    "ai_rejected": "confidence",
    # نقدینگی
    "low_liquidity": "liquidity",
    # لبه
    "negative_edge": "edge",
    # ریسک و سرمایه
    "risk_exceeded": "risk",
    "daily_loss_limit": "risk",
    "insufficient_margin": "risk",
    "invalid_risk": "risk",
    "poor_reward_risk": "risk",
    "max_concurrent": "risk",
    "symbol_already_open": "risk",
    "symbol_not_selected": "risk",
    "invalid_config": "risk",
    # هدف
    "target_unreachable": "target",
    "target_infeasible": "target",
    # دفتر سفارش
    "no_orderbook": "orderbook",
    # اجرا
    "exchange_error": "other",
    "live_not_enabled": "other",
    # نسخهٔ ۲.۶.۱: حالت تشخیصی — همهٔ دروازه‌ها گذشتند ولی سفارشی نرفت
    "diagnostic_only": "other",
    "rejected": "other",
}

REASON_CODES: tuple[str, ...] = tuple(REASON_BUCKETS)

#: دلیل خام موتور → کد استاندارد (بخش پیش از «:»)
_ALIASES: dict[str, str] = {
    "price_unavailable": "no_price",
    "max_concurrent_reached": "max_concurrent",
    "no_available_margin": "insufficient_margin",
    "invalid_fee_rate": "invalid_config",
    "fees_exceed_loss_budget": "fees_exceed_budget",
    "invalid_risk_levels": "invalid_risk",
    "risk_exceeds_loss_budget": "risk_exceeded",
    "poor_net_reward_risk": "poor_reward_risk",
    "rejected_by_guards": "rejected",
    "stale": "stale_data",
    "quiet": "low_momentum",
    "illiquid": "low_liquidity",
    "no_tick_engine": "data_error",
    "infeasible_target": "target_infeasible",
    "wait": "no_direction",
}

#: سطل‌های خلاصهٔ پویش، به ترتیب نمایش
SUMMARY_BUCKETS: tuple[str, ...] = (
    "volatility", "cost", "spread", "trend", "confidence", "liquidity",
    "edge", "risk", "target", "orderbook", "data", "other",
)

#: مراحل خط زمانی معامله
TIMELINE_STAGES: tuple[str, ...] = ("signal", "candidate", "validation", "entry", "monitoring", "exit")

#: رویداد → مرحلهٔ خط زمانی
EVENT_STAGE: dict[str, str] = {
    "signal": "signal",
    "candidate": "candidate",
    "reject": "validation",
    "validation": "validation",
    "entry": "entry",
    "partial_exit": "monitoring",
    "protection": "monitoring",
    "exit_decision": "monitoring",
    "monitoring": "monitoring",
    "exit": "exit",
}


def normalize_reason(raw: Any) -> str:
    """دلیل خام → کد استاندارد. `wide_spread:0.31%` → `wide_spread`."""
    text = str(raw or "").strip()
    if not text:
        return "rejected"
    head = text.split(":", 1)[0].strip().lower().replace(" ", "_")
    head = _ALIASES.get(head, head)
    return head if head in REASON_BUCKETS else head or "rejected"


def reason_bucket(code: str) -> str:
    """کد استاندارد → سطل خلاصهٔ پویش (ناشناخته → other)."""
    return REASON_BUCKETS.get(normalize_reason(code), "other")


def new_correlation_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# خلاصهٔ هر پویش
# ---------------------------------------------------------------------------

_scan_counter = itertools.count(1)


@dataclass
class ScanDiagnostics:
    """
    شمارنده‌های یک دور پویش؛ منبع نامزد و AutoTrader در همین شیء می‌شمارند.

    - scanned_symbols: نمادهایی که منبع بررسی کرد
    - raw_candidates: نمادهایی که دادهٔ قابل‌ارزیابی داشتند (پیش از فیلترهای کیفی)
    - source_candidates: نامزدهای تحویلی منبع به AutoTrader
    - final_candidates: نامزدهایی که از همهٔ دروازه‌ها گذشتند
    - opened_trades: معامله‌های بازشده
    - rejected[bucket], reasons[code]
    """

    engine: str = ""
    scan_id: str = field(default_factory=lambda: f"{int(time.time())}-{next(_scan_counter)}")
    started: float = field(default_factory=time.time)
    scanned_symbols: int = 0
    raw_candidates: int = 0
    source_candidates: int = 0
    final_candidates: int = 0
    opened_trades: int = 0
    rejected: dict[str, int] = field(default_factory=lambda: {b: 0 for b in SUMMARY_BUCKETS})
    reasons: dict[str, int] = field(default_factory=dict)
    seconds: float = 0.0
    scans: int = 1

    def reject(self, reason: Any, count: int = 1) -> str:
        code = normalize_reason(reason)
        bucket = reason_bucket(code)
        self.rejected[bucket] = self.rejected.get(bucket, 0) + int(count)
        self.reasons[code] = self.reasons.get(code, 0) + int(count)
        return code

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "scan_id": self.scan_id,
            "engine": self.engine,
            "scans": self.scans,
            "scanned_symbols": self.scanned_symbols,
            "raw_candidates": self.raw_candidates,
            "source_candidates": self.source_candidates,
            "final_candidates": self.final_candidates,
            "opened_trades": self.opened_trades,
            "seconds": round(self.seconds, 3),
            "reasons": dict(sorted(self.reasons.items(), key=lambda kv: -kv[1])),
        }
        for bucket in SUMMARY_BUCKETS:
            data[f"rejected_{bucket}"] = int(self.rejected.get(bucket, 0))
        return data

    def merge(self, other: ScanDiagnostics) -> None:
        """جمع کردن پویش دیگر در همین شیء (برای ذخیرهٔ تجمیعی)."""
        self.scans += other.scans
        for name in ("scanned_symbols", "raw_candidates", "source_candidates",
                     "final_candidates", "opened_trades"):
            setattr(self, name, getattr(self, name) + getattr(other, name))
        self.seconds += other.seconds
        for bucket, value in other.rejected.items():
            self.rejected[bucket] = self.rejected.get(bucket, 0) + value
        for code, value in other.reasons.items():
            self.reasons[code] = self.reasons.get(code, 0) + value


_current_scan: contextvars.ContextVar[ScanDiagnostics | None] = contextvars.ContextVar(
    "cai_current_scan", default=None
)


def current_scan() -> ScanDiagnostics | None:
    """پویش جاری (اگر داخل `scan_scope` هستیم)؛ وگرنه None."""
    return _current_scan.get()


@contextmanager
def scan_scope(diagnostics: ScanDiagnostics) -> Iterator[ScanDiagnostics]:
    """منبع نامزدی که داخل این بلوک اجرا شود، در همین شیء می‌شمارد."""
    token = _current_scan.set(diagnostics)
    try:
        yield diagnostics
    finally:
        _current_scan.reset(token)


def note_scan(*, scanned: int = 0, raw: int = 0, reasons: dict[str, int] | None = None) -> None:
    """ثبت آمار منبع نامزد در پویش جاری (بیرون از پویش: بی‌اثر)."""
    try:
        scan = current_scan()
        if scan is None:
            return
        scan.scanned_symbols += int(scanned)
        scan.raw_candidates += int(raw)
        for reason, count in (reasons or {}).items():
            if count:
                scan.reject(reason, int(count))
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# انتشار رویداد
# ---------------------------------------------------------------------------

#: فاصلهٔ تکرار یک رد یکسان (نماد + کد) که دوباره در فایل/پایگاه داده ثبت شود
REJECT_REPEAT_SECONDS = float(os.environ.get("CAI_AUDIT_REJECT_REPEAT", "30") or 30)
#: فاصلهٔ ذخیرهٔ خلاصهٔ تجمیعی پویش (هر پویش در نمای زنده هست)
SCAN_PERSIST_SECONDS = float(os.environ.get("CAI_AUDIT_SCAN_PERSIST", "10") or 10)

_repeat_lock = threading.Lock()
_last_reject: dict[tuple[str, str, str], float] = {}
_suppressed: dict[tuple[str, str, str], int] = {}
_pending_scans: dict[str, ScanDiagnostics] = {}
_last_scan_persist: dict[str, float] = {}


def _level(name: str) -> int:
    return getattr(logging, str(name).upper(), logging.INFO)


def emit(
    event: str,
    message: str,
    *,
    category: LogCategory | str = LogCategory.TRADING,
    level: str = "INFO",
    symbol: str | None = None,
    trade_id: Any = None,
    reason_code: str | None = None,
    scan_id: str | None = None,
    correlation_id: str | None = None,
    persist: bool = True,
    **context: Any,
) -> bool:
    """انتشار یک رویداد ممیزی؛ هرگز استثنا نمی‌دهد. بازگشت: موفق؟"""
    try:
        extra = {
            "audit": True,
            "event": event,
            "category": category.value if isinstance(category, LogCategory) else str(category),
            "context": {k: v for k, v in context.items() if v is not None},
            "persist": persist,
        }
        if symbol:
            extra["symbol"] = str(symbol).upper()
        if trade_id not in (None, ""):
            extra["trade_id"] = int(trade_id) if str(trade_id).isdigit() else trade_id
        if reason_code:
            extra["reason_code"] = reason_code
        if scan_id:
            extra["scan_id"] = scan_id
        if correlation_id:
            extra["correlation_id"] = correlation_id
        _logger.log(_level(level), message, extra=extra)
        return True
    except Exception:  # noqa: BLE001 - لاگ هرگز نباید معامله را متوقف کند
        return False


def domain_category(engine_mode: str | None) -> LogCategory:
    """اسکالپ/اولترا → SCALP؛ بقیه → TRADING."""
    mode = str(engine_mode or "").lower()
    return LogCategory.SCALP if mode in ("scan", "ultra", "scalp", "selected") else LogCategory.TRADING


def signal(symbol: str, direction: str, *, source: str = "", **fields: Any) -> bool:
    """یک سیگنال تولیدشده (اطمینان فنی/نهایی، پیش‌بینی، MTF، رژیم، جریان سفارش…)."""
    return emit("signal", f"Signal {direction} {symbol} ({source})", category=LogCategory.SIGNALS,
                symbol=symbol, direction=direction, source=source, **fields)


def candidate(symbol: str, direction: str, *, engine_mode: str = "", correlation_id: str | None = None,
              scan_id: str | None = None, **fields: Any) -> bool:
    """نامزدی که به دروازه‌های AutoTrader رسید (با عکس کامل بازار/سیگنال)."""
    return emit("candidate", f"Candidate {direction} {symbol}", category=domain_category(engine_mode),
                symbol=symbol, correlation_id=correlation_id, scan_id=scan_id,
                direction=direction, engine_mode=engine_mode, **fields)


def reject(symbol: str, reason: Any, *, stage: str = "", engine_mode: str = "",
           correlation_id: str | None = None, scan_id: str | None = None,
           filters: dict[str, str] | None = None, **fields: Any) -> str:
    """
    رد یک فرصت با کد استاندارد. بازگشت: کد استاندارد.

    رد تکراری همان نماد و همان کد در `REJECT_REPEAT_SECONDS` فقط در نمای زنده
    می‌آید (نه فایل/پایگاه داده)؛ شمار تکرارهای حذف‌شده در رکورد بعدی ثبت می‌شود.
    شمارش خلاصهٔ پویش جدا و همیشه دقیق است.
    """
    try:
        code = normalize_reason(reason)
        key = (str(symbol or "").upper(), code, str(engine_mode or ""))
        now = time.monotonic()
        with _repeat_lock:
            last = _last_reject.get(key)
            persist = last is None or now - last >= REJECT_REPEAT_SECONDS
            suppressed = 0
            if persist:
                _last_reject[key] = now
                suppressed = _suppressed.pop(key, 0)
                if len(_last_reject) > 20_000:
                    _last_reject.clear()
            else:
                _suppressed[key] = _suppressed.get(key, 0) + 1
        category = LogCategory.RISK if reason_bucket(code) == "risk" else domain_category(engine_mode)
        emit("reject", f"Rejected {symbol}: {code}", category=category, symbol=symbol,
             reason_code=code, correlation_id=correlation_id, scan_id=scan_id, persist=persist,
             reason_detail=str(reason or ""), bucket=reason_bucket(code), stage=stage,
             engine_mode=engine_mode, filters=filters or None,
             repeats_suppressed=suppressed or None, **fields)
        return code
    except Exception:  # noqa: BLE001
        return "rejected"


def timeline(trade_id: Any, stage: str, message: str, *, symbol: str | None = None,
             correlation_id: str | None = None, **fields: Any) -> bool:
    """یک گام دلخواه در خط زمانی معامله (مثلاً تصمیم خروج یا جابه‌جایی حد ضرر)."""
    return emit(stage, message, category=LogCategory.TRADING, symbol=symbol, trade_id=trade_id,
                correlation_id=correlation_id, **fields)


def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number else 0.0


def entry_fields(record: dict[str, Any]) -> dict[str, Any]:
    """فیلدهای ممیزی ورود از رکورد معامله (همهٔ مسیرها: خودکار، سیگنال، دستی)."""
    extra = dict(record.get("extra") or {})
    execution = dict(extra.get("execution") or {})
    entry = _number(record.get("entry_price"))
    quantity = _number(record.get("quantity"))
    leverage = _number(record.get("leverage")) or 1.0
    stop = _number(record.get("stop_loss"))
    target = _number(record.get("take_profit"))
    fee_rate = _number(extra.get("fee_rate"))
    margin = _number(extra.get("margin")) or (entry * quantity / leverage if leverage else 0.0)
    bid = _number(execution.get("bid"))
    ask = _number(execution.get("ask"))
    spread_percent = _number(execution.get("spread_percent"))
    if not spread_percent and bid > 0 and ask > 0:
        spread_percent = (ask - bid) / ((ask + bid) / 2) * 100.0
    slippage_percent = _number(execution.get("slippage_percent"))
    reward = abs(target - entry) if target else 0.0
    risk = abs(entry - stop) if stop else 0.0
    exit_reference = target or entry
    estimated_fee = _number(record.get("fee")) + quantity * exit_reference * fee_rate
    # لغزش تخمینی: درصد اعلامی اجرا، وگرنه نصف اسپرد (هزینهٔ عبور از وسط دفتر)
    slip_basis = slippage_percent if slippage_percent else spread_percent / 2.0
    intelligence = dict(extra.get("intelligence") or {})
    return {
        "direction": "LONG" if str(record.get("side", "long")).lower() == "long" else "SHORT",
        "entry_price": entry,
        "bid": bid or None,
        "ask": ask or None,
        "spread_percent": round(spread_percent, 5) if spread_percent else None,
        "quantity": quantity,
        "notional": entry * quantity,
        "margin": margin,
        "leverage": leverage,
        "stop_loss": stop or None,
        "take_profit": target or None,
        "targets": extra.get("targets") or None,
        "expected_rr": round(reward / risk, 4) if reward and risk else None,
        "estimated_fee": round(estimated_fee, 8),
        "estimated_slippage": round(entry * quantity * slip_basis / 100.0, 8) if slip_basis else 0.0,
        "estimated_slippage_percent": round(slip_basis, 5) if slip_basis else 0.0,
        "mode": record.get("mode") or "paper",
        "source": extra.get("source") or ("auto" if extra.get("auto") else ""),
        "engine_mode": extra.get("engine_mode") or None,
        "market_type": extra.get("market_type") or None,
        "signal_id": record.get("signal_id"),
        "signal_snapshot": {
            "score": extra.get("score"),
            "quality": extra.get("quality") or intelligence.get("quality"),
            "technical_confidence": intelligence.get("technical_confidence"),
            "final_confidence": intelligence.get("final_confidence"),
            "prediction_probability": intelligence.get("prediction_probability"),
            "mtf_alignment": intelligence.get("mtf_alignment"),
            "regime_score": intelligence.get("regime_score"),
            "stop_source": extra.get("stop_source"),
            "target_source": extra.get("target_source"),
        },
    }


def entry(record: dict[str, Any]) -> bool:
    """ورود ثبت‌شده (از مخزن معاملات؛ برای همهٔ مسیرها دقیقاً یک بار)."""
    try:
        extra = dict(record.get("extra") or {})
        fields = entry_fields(record)
        return emit(
            "entry",
            f"Entry #{record.get('id')} {fields['direction']} {record.get('symbol')} @ {fields['entry_price']}",
            category=LogCategory.ORDERS, symbol=record.get("symbol"), trade_id=record.get("id"),
            correlation_id=extra.get("audit_id"), **fields,
        )
    except Exception:  # noqa: BLE001
        return False


_CLOSE_PREFIXES = ("بسته شد: ", "closed: ")


def exit_reason_from_note(note: str) -> str:
    """دلیل خروج از یادداشت بستن (`بسته شد: take_profit` → take_profit)."""
    text = str(note or "").strip()
    for prefix in _CLOSE_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix):].strip() or "closed"
    return text or "closed"


def exit_(record: dict[str, Any], *, reason: str = "", exit_fee: float = 0.0,
          **fields: Any) -> bool:
    """خروج ثبت‌شده با سود ناخالص، کارمزد، لغزش و سود خالص."""
    try:
        extra = dict(record.get("extra") or {})
        entry_price = _number(record.get("entry_price"))
        exit_price = _number(record.get("exit_price"))
        pnl = _number(record.get("pnl"))
        fees = _number(record.get("fee"))
        opened = record.get("opened_at")
        closed = record.get("closed_at")
        holding = None
        try:
            from datetime import datetime

            if opened and closed:
                start = opened if isinstance(opened, datetime) else datetime.fromisoformat(str(opened))
                end = closed if isinstance(closed, datetime) else datetime.fromisoformat(str(closed))
                holding = round((end - start).total_seconds(), 3)
        except (TypeError, ValueError):
            holding = None
        quantity = max(_number(record.get("quantity")), _number(extra.get("original_quantity")))
        execution = dict(extra.get("execution") or {})
        slip_pct = _number(execution.get("slippage_percent"))
        result = "win" if pnl > 0 else ("loss" if pnl < 0 else "breakeven")
        reason_text = reason or exit_reason_from_note(record.get("note", ""))
        return emit(
            "exit",
            f"Exit #{record.get('id')} {record.get('symbol')} {reason_text} net={pnl:.4f}",
            category=LogCategory.ORDERS, symbol=record.get("symbol"), trade_id=record.get("id"),
            correlation_id=extra.get("audit_id"),
            exit_price=exit_price, exit_time=str(closed or ""), holding_seconds=holding,
            exit_reason=reason_text, gross_pnl=round(pnl + fees, 8), fees=round(fees, 8),
            exit_fee=round(_number(exit_fee), 8),
            slippage=round(quantity * exit_price * slip_pct / 100.0, 8) if slip_pct else 0.0,
            net_pnl=round(pnl, 8), pnl_percent=_number(record.get("pnl_percent")),
            result=result, entry_price=entry_price,
            direction="LONG" if str(record.get("side", "long")).lower() == "long" else "SHORT",
            **fields,
        )
    except Exception:  # noqa: BLE001
        return False


def partial_exit(record: dict[str, Any], *, quantity: float, price: float, target_index: Any = None) -> bool:
    """بستن جزئی (TP1/TP2) — گام «Monitoring» خط زمانی."""
    extra = dict(record.get("extra") or {})
    return emit("partial_exit", f"Partial exit #{record.get('id')} {record.get('symbol')} qty={quantity} @ {price}",
                category=LogCategory.ORDERS, symbol=record.get("symbol"), trade_id=record.get("id"),
                correlation_id=extra.get("audit_id"), quantity=quantity, price=price,
                target=None if target_index is None else int(target_index) + 1,
                stop_loss=record.get("stop_loss"))


def scan_summary(diagnostics: ScanDiagnostics) -> bool:
    """
    خلاصهٔ یک پویش. هر پویش در نمای زنده هست؛ در فایل/پایگاه داده هر
    `SCAN_PERSIST_SECONDS` یک رکورد **تجمیعی** (جمع پویش‌های آن بازه) ذخیره می‌شود.
    """
    try:
        engine = diagnostics.engine or "auto"
        now = time.monotonic()
        with _repeat_lock:
            pending = _pending_scans.get(engine)
            if pending is None:
                pending = ScanDiagnostics(engine=engine, scan_id=diagnostics.scan_id, scans=0)
                _pending_scans[engine] = pending
            pending.merge(diagnostics)
            last = _last_scan_persist.get(engine)
            due = last is None or now - last >= SCAN_PERSIST_SECONDS or diagnostics.opened_trades > 0
            if due:
                _last_scan_persist[engine] = now
                aggregate = _pending_scans.pop(engine)
            else:
                aggregate = None
        data = diagnostics.to_dict()
        data.pop("scan_id", None)
        emit("scan_summary", _summary_text(data), category=domain_category(engine), scan_id=diagnostics.scan_id,
             persist=False, **data)
        if aggregate is not None:
            agg = aggregate.to_dict()
            agg["scan_id"] = diagnostics.scan_id
            emit("scan_summary", _summary_text(agg), category=domain_category(engine),
                 scan_id=diagnostics.scan_id, persist=True, aggregated=True, **{k: v for k, v in agg.items() if k != "scan_id"})
        return True
    except Exception:  # noqa: BLE001
        return False


def _summary_text(data: dict[str, Any]) -> str:
    rejected = {b: data.get(f"rejected_{b}", 0) for b in SUMMARY_BUCKETS if data.get(f"rejected_{b}")}
    return (f"Scan[{data.get('engine')}] scanned={data.get('scanned_symbols')} raw={data.get('raw_candidates')} "
            f"source={data.get('source_candidates')} final={data.get('final_candidates')} "
            f"opened={data.get('opened_trades')} rejected={rejected}")


def performance(name: str, seconds: float, **fields: Any) -> bool:
    """زمان‌سنجی (پویش، ورود) در دستهٔ PERFORMANCE — فقط وقتی کند است ذخیره می‌شود."""
    try:
        slow = float(seconds) >= float(fields.pop("slow_seconds", 1.0))
    except (TypeError, ValueError):
        return False
    return emit("performance", f"{name} took {seconds * 1000:.1f} ms", category=LogCategory.PERFORMANCE,
                level="WARNING" if slow else "DEBUG", persist=slow, operation=name,
                seconds=round(float(seconds), 4), **fields)


def reset_state() -> None:
    """پاک کردن حالت تکرار/تجمیع (برای آزمون)."""
    with _repeat_lock:
        _last_reject.clear()
        _suppressed.clear()
        _pending_scans.clear()
        _last_scan_persist.clear()


__all__ = [
    "EVENT_STAGE",
    "REASON_BUCKETS",
    "REASON_CODES",
    "SUMMARY_BUCKETS",
    "ScanDiagnostics",
    "TIMELINE_STAGES",
    "candidate",
    "current_scan",
    "emit",
    "entry",
    "entry_fields",
    "exit_",
    "exit_reason_from_note",
    "new_correlation_id",
    "normalize_reason",
    "note_scan",
    "partial_exit",
    "performance",
    "reason_bucket",
    "reject",
    "reset_state",
    "scan_scope",
    "scan_summary",
    "signal",
    "timeline",
]
