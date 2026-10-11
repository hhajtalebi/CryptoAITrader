"""
ردیابی سرتاسری یک اجرای هوش مصنوعی — نسخهٔ ۲.۷.۱.

چرا وجود دارد؟
    گزارش‌های کاربر معمولاً فقط یک خروجی را نشان می‌دهند: «هیچ پاسخی
    نیامد» یا «سیگنال ساخته نشد». برای تشخیص علت، باید بتوان یک اجرا را
    از شروع تا پایان دنبال کرد: کدام سرویس و مدل انتخاب شد، دادهٔ بازار
    رسید یا نه، هر مرحله چقدر طول کشید، مدل چه نوشت، اعتبارسنجی چه گفت و
    در نهایت چرا سیگنال ساخته شد یا رد گردید.

    بدون یک شناسهٔ مشترک، این اطلاعات در چند فایل لاگ پخش می‌شود و عملاً
    غیرقابل اتصال است. `AITrace` یک `trace_id` می‌سازد و آن را به همهٔ
    رویدادهای همان اجرا می‌چسباند.

چه چیزی لاگ می‌شود و چه چیزی نه:
    • لاگ می‌شود: سرویس، مدل، زمان هر مرحله، تعداد ابزارها، نتیجهٔ
      اعتبارسنجی، کد خطا و — فقط در سطح DEBUG — متن خام پاسخِ بریده‌شده.
    • لاگ نمی‌شود: کلید API، توکن، و هر راز دیگر. علاوه بر اینکه اینجا
      اصلاً به آن‌ها دست نمی‌زنیم، لایهٔ لاگ هم پیش از نوشتن، مقادیر
      حساس را ماسک می‌کند.

هزینه:
    هر فراخوانی فقط یک `audit.emit` است که خودش از صف غیرمسدودکننده
    عبور می‌کند؛ مسیر داغ برنامه (معامله، وب‌سوکت) هرگز منتظر دیسک
    نمی‌ماند.
"""

from __future__ import annotations

import time
from typing import Any

from app.logging import audit
from app.logging.categories import LogCategory

#: بیشینهٔ طول متن خام که در سطح debug ثبت می‌شود
RAW_LIMIT = 1500

#: نام مراحل استاندارد تا جست‌وجو در لاگ یکسان باشد
STAGE_START = "start"
STAGE_DATA = "data"
STAGE_MODEL = "model"
STAGE_VALIDATION = "validation"
STAGE_DONE = "done"


def _short(value: Any, limit: int = RAW_LIMIT) -> str:
    """بریدن امنِ متن خام؛ هرگز استثنا نمی‌دهد."""
    try:
        text = str(value)
    except Exception:  # noqa: BLE001 - متنِ خراب نباید لاگ را ببندد
        return "<unprintable>"
    text = text.replace("\r", " ").strip()
    return text if len(text) <= limit else f"{text[:limit]}…(+{len(text) - limit} chars)"


class AITrace:
    """
    ردیاب یک اجرا (تحلیل متنی، تولید سیگنال، گفتگو).

    نمونه‌سازی:
        trace = AITrace("signal", symbol="BTC/USDT")
        trace.stage("data", candles=200)
        ...
        trace.finish(True, "signal LONG accepted", confidence=71)
    """

    def __init__(
        self,
        kind: str,
        *,
        symbol: str = "",
        provider: str = "",
        model: str = "",
        **fields: Any,
    ) -> None:
        self.trace_id = audit.new_correlation_id()
        self.kind = str(kind or "ai")
        self.symbol = str(symbol or "")
        self.provider = str(provider or "")
        self.model = str(model or "")
        self._started = time.perf_counter()
        self._mark = self._started
        self._fields: dict[str, Any] = dict(fields)
        self.emit(
            "ai_start",
            f"AI {self.kind} started",
            stage=STAGE_START,
            symbol=self.symbol or None,
        )

    # ------------------------------------------------------------------ وضعیت
    def note(self, **fields: Any) -> None:
        """ثبت فیلدهای پایدار (مثلاً سرویس و مدلی که واقعاً استفاده شد)."""
        for key, value in fields.items():
            if value not in (None, "", []):
                self._fields[key] = value
                if key == "provider":
                    self.provider = str(value)
                elif key == "model":
                    self.model = str(value)

    @property
    def elapsed(self) -> float:
        """ثانیه از آغاز اجرا."""
        return time.perf_counter() - self._started

    # ------------------------------------------------------------------ رویداد
    def emit(
        self,
        event: str,
        message: str,
        *,
        level: str = "INFO",
        stage: str = "",
        **fields: Any,
    ) -> None:
        """انتشار یک رویداد با شناسهٔ ردیابی؛ هرگز استثنا نمی‌دهد."""
        payload = dict(self._fields)
        payload.update({k: v for k, v in fields.items() if v is not None})
        payload.setdefault("kind", self.kind)
        if self.provider:
            payload.setdefault("provider", self.provider)
        if self.model:
            payload.setdefault("model", self.model)
        if stage:
            payload["stage"] = stage
        # نام‌هایی که خود `audit.emit` به‌صورت پارامتر می‌گیرد نباید دو بار
        # برسند؛ وگرنه خطای «multiple values for keyword argument» می‌گیریم.
        for reserved in ("event", "category", "level", "correlation_id",
                         "trade_id", "reason_code", "scan_id", "persist", "symbol"):
            payload.pop(reserved, None)
        audit.emit(
            event,
            message,
            category=LogCategory.AI,
            level=level,
            symbol=self.symbol or None,
            correlation_id=self.trace_id,
            **payload,
        )

    def stage(self, name: str, message: str = "", **fields: Any) -> float:
        """
        ثبت پایان یک مرحله و مدتِ آن.

        بازگشتی: مدت این مرحله (ثانیه). این همان عددی است که برای یافتن
        گلوگاه لازم است — «کُند از کجاست؟» بدون زمان هر مرحله پاسخ ندارد.
        """
        now = time.perf_counter()
        seconds = round(now - self._mark, 3)
        self._mark = now
        payload = {k: v for k, v in fields.items() if v is not None}
        # `seconds`/`total_seconds` کلیدهای خودِ این متد هستند؛ اگر فراخواننده
        # هم همین نام را بفرستد، مقدارش زیر نامی دیگر حفظ می‌شود تا پیام
        # «multiple values for keyword argument» کل اجرا را نشکند.
        if "seconds" in payload:
            payload["reported_seconds"] = payload.pop("seconds")
        if "total_seconds" in payload:
            payload["reported_total_seconds"] = payload.pop("total_seconds")
        self.emit(
            f"ai_{name}",
            message or f"stage {name} finished",
            stage=name,
            seconds=seconds,
            total_seconds=round(now - self._started, 3),
            **payload,
        )
        return seconds

    def raw(self, name: str, text: Any, *, level: str = "DEBUG") -> None:
        """ثبت متن خامِ بریده‌شده برای عیب‌یابی (فقط debug)."""
        self.emit(
            f"ai_{name}_raw",
            _short(text),
            level=level,
            stage=name,
        )

    def warning(self, event: str, message: str, **fields: Any) -> None:
        """رویداد هشدار — تلاش مجدد، کوچک‌سازی پرامپت، سرویس جایگزین."""
        self.emit(event, message, level="WARNING", **fields)

    def error(self, event: str, message: str, **fields: Any) -> None:
        """رویداد خطا؛ در سطح ERROR تا در مرکز لاگ گم نشود."""
        self.emit(event, message, level="ERROR", **fields)

    def finish(self, ok: bool, message: str, **fields: Any) -> float:
        """پایان اجرا با نتیجهٔ نهایی."""
        total = round(self.elapsed, 3)
        self.emit(
            "ai_finish",
            message,
            level="INFO" if ok else "WARNING",
            stage=STAGE_DONE,
            ok=ok,
            seconds=total,
            **fields,
        )
        return total


__all__ = ["AITrace", "RAW_LIMIT", "STAGE_DATA", "STAGE_DONE", "STAGE_MODEL",
           "STAGE_START", "STAGE_VALIDATION"]
