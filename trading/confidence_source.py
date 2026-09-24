"""
انتخاب نماد برای معاملهٔ خودکار بر پایهٔ **درصد اطمینان سیگنال**.

خواستهٔ کاربر: «روی همهٔ ارزها تحلیل انجام بده؛ آن‌هایی که درصد
اطمینانشان از ۷۵ به بالا بود شروع کن به معامله کردن.»

تفاوت با منبع قبلی (اسکالپ): اسکالپ نماد را بر پایهٔ نوسان و حجم
پنج‌دقیقه‌ای انتخاب می‌کرد و اصلاً «اطمینان» نداشت — امتیازش از جنس
دیگری بود. این ماژول مستقیم از موتور سیگنال استفاده می‌کند، همان
موتوری که عدد اطمینان را می‌سازد و کاربر در صفحهٔ سیگنال‌ها می‌بیند.

نکتهٔ مهم: اینجا **عمداً** هوش مصنوعی صدا زده نمی‌شود. پویش گروهی روی
ده‌ها نماد با هوش مصنوعی هم کند است هم پرهزینه، و کاربر قبلاً همین را
گفته بود. موتور ریاضی تصمیم می‌گیرد؛ هوش مصنوعی در صفحهٔ تحلیل و روی
نماد انتخابی کار می‌کند.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from trading.universe import RotatingUniverse
from typing import Any

from app.logging import get_logger

logger = get_logger(__name__)

#: پایین‌تر از این حد، اجازهٔ ورود خودکار داده نمی‌شود حتی اگر کاربر
#: عدد کمتری تنظیم کند. زیر ۵۰٪ یعنی موتور خودش هم مطمئن نیست.
ABSOLUTE_MIN_CONFIDENCE = 50


@dataclass
class ConfidenceCandidate:
    """
    یک نامزد معامله که از سیگنال ساخته شده.

    نام فیلدها عمداً با `ScalpCandidate` یکی است تا `AutoTrader` بدون
    هیچ تغییری هر دو را بپذیرد. موتور با `getattr` این‌ها را می‌خواند:
    `symbol`، `direction`، `price`، `score`.
    """

    symbol: str
    price: float
    direction: str  # LONG | SHORT
    #: همان درصد اطمینان سیگنال (۰ تا ۱۰۰)
    score: float
    timeframe: str = ""
    reasons: list[str] = field(default_factory=list)
    take_profit: float = 0.0
    stop_loss: float = 0.0
    turnover_24h: float | None = None
    observed_at: float = field(default_factory=time.time)

    @property
    def confidence(self) -> float:
        """نام گویاتر برای همان امتیاز؛ در گزارش‌ها استفاده می‌شود."""
        return self.score


class ConfidenceCandidateSource:
    """
    پویش بازار و تبدیل سیگنال‌های پراطمینان به نامزد معامله.

    این کلاس فقط مکان چرخش نمادها را نگه می‌دارد؛ هر دور پویش عدد تازهٔ
    کاربر را بخواند؛ اگر کاربر وسط کار حد اطمینان را عوض کند، دور بعد
    اثر می‌کند بدون نیاز به ری‌استارت.
    """

    def __init__(self, app: Any) -> None:
        """نگه‌داشتن ارجاع برنامه برای دسترسی به تنظیم‌ها و موتور پویش."""
        self._app = app
        self._universe = RotatingUniverse()

    # ------------------------------------------------------------------
    # تنظیم‌ها
    # ------------------------------------------------------------------
    @property
    def min_confidence(self) -> int:
        """
        حد اطمینان کاربر، با کفِ ایمنی.

        کاربر می‌تواند سخت‌گیرتر باشد ولی نمی‌تواند زیر کف برود.
        """
        raw = self._app.settings.get_int("scalp.min_confidence", 75)
        return max(ABSOLUTE_MIN_CONFIDENCE, int(raw or 75))

    @property
    def scan_symbols(self) -> int:
        """چند نماد پرگردش در هر دور بررسی شود."""
        return max(5, self._app.settings.get_int("scalp.scan_symbols", 40) or 40)

    # ------------------------------------------------------------------
    # پویش
    # ------------------------------------------------------------------
    async def scan(self, *, symbols: list[str] | None = None) -> list[ConfidenceCandidate]:
        """
        یک دور پویش کامل و برگرداندن نامزدهای واجد شرایط.

        ترتیب خروجی بر پایهٔ اطمینان نزولی است تا اگر ظرفیت معاملهٔ
        هم‌زمان پر شد، بهترین‌ها زودتر باز شوند.
        """
        threshold = self.min_confidence
        tickers = []
        if symbols is not None and not symbols:
            return []
        try:
            market = getattr(self._app, "market", None)
            if market is not None:
                tickers = await market.get_all_tickers()
                settings_get = getattr(self._app.settings, "get", lambda key, default: default)
                raw = str(settings_get("scalp.selected_symbols", "") or "")
                favorites = [s.strip().upper() for s in raw.replace(";", ",").split(",") if s.strip()]
                symbols = self._universe.select(tickers, selected=symbols, favorites=favorites,
                                               limit=self.scan_symbols,
                                               min_turnover=float(settings_get("scalp.min_liquidity", 2_000_000) or 0))
                if not symbols:
                    return []
            result = await self._app.scan_market(
                symbols=symbols,
                limit=self.scan_symbols,
                min_confidence=threshold,
                include_wait=False,
            )
        except Exception:  # noqa: BLE001 - یک دور ناموفق نباید موتور را بکشد
            logger.warning("Confidence scan failed; skipping this round", exc_info=True)
            return []

        candidates: list[ConfidenceCandidate] = []
        for signal in getattr(result, "signals", []) or []:
            candidate = self._to_candidate(signal, threshold)
            if candidate is not None:
                ticker = next((t for t in tickers if t.symbol == candidate.symbol), None)
                if ticker is not None:
                    candidate.turnover_24h = float(ticker.turnover_24h or 0)
                candidates.append(candidate)

        candidates.sort(key=lambda item: item.score, reverse=True)
        logger.info(
            "Confidence scan: %d signals, %d above %d%%",
            len(getattr(result, "signals", []) or []),
            len(candidates),
            threshold,
        )
        return candidates

    def _to_candidate(self, signal: Any, threshold: int) -> ConfidenceCandidate | None:
        """
        تبدیل یک سیگنال به نامزد، یا `None` اگر واجد شرایط نباشد.

        سه چیز رد می‌شود: جهت «انتظار»، اطمینان کمتر از حد، و قیمت
        نامعتبر. قیمت صفر یعنی داده ناقص است و با آن نمی‌شود حجم
        معامله را حساب کرد.
        """
        direction = str(getattr(getattr(signal, "direction", ""), "value", "")
                        or getattr(signal, "direction", "")).upper()
        if direction not in {"LONG", "SHORT"}:
            return None

        confidence = float(getattr(signal, "confidence", 0) or 0)
        if confidence < threshold:
            return None

        # `TradingSignal` قیمت ورود را به‌صورت **بازه** نگه می‌دارد
        # (`entry_min`/`entry_max`) و فیلدی به نام `entry_price` ندارد.
        # وسط بازه منطقی‌ترین نقطهٔ ورود است؛ اگر فقط یکی پر باشد همان
        # استفاده می‌شود.
        low = float(getattr(signal, "entry_min", 0) or 0)
        high = float(getattr(signal, "entry_max", 0) or 0)
        if low > 0 and high > 0:
            price = (low + high) / 2
        else:
            price = low or high
        if price <= 0:
            logger.debug("Skipping %s: no usable entry price", getattr(signal, "symbol", "?"))
            return None

        # فیلد درست `reason` (تک‌رشته‌ای) است، نه `reasons`.
        reason = str(getattr(signal, "reason", "") or "").strip()
        timeframes = list(getattr(signal, "timeframes", []) or [])
        primary = str(getattr(signal, "primary_timeframe", "") or "")
        return ConfidenceCandidate(
            symbol=str(getattr(signal, "symbol", "")),
            price=price,
            direction=direction,
            score=confidence,
            timeframe=primary or (timeframes[0] if timeframes else ""),
            reasons=[reason] if reason else [],
            stop_loss=float(getattr(signal, "stop_loss", 0) or 0),
            take_profit=next((float(p) for p in (getattr(signal, "take_profits", []) or [])
                              if (float(p) - price) * (1 if direction == "LONG" else -1) > 0), 0.0),
        )
