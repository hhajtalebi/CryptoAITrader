"""
نویسندهٔ تحلیل نوشتاری فارسی برای هر سیگنال.

کاربر خواست:

    «در قسمت سیگنال برای هر سیگنال یک تحلیل نوشتاری دقیق اضافه کن تا هوش
     مصنوعی تحلیل نوشتاری هم بزند … و از تحلیل همیشه خروجی PDF فارسی
     گرفت، تحلیل به زبان فارسی باشد»

دو مسیر برای تولید متن وجود دارد و هر دو پیاده شده‌اند:

۱. **مسیر هوش مصنوعی** — متن روان و انسانی می‌نویسد.
۲. **مسیر قالبی (fallback)** — اگر سرویس هوش مصنوعی در دسترس نباشد،
   کند باشد یا اعتبار نداشته باشد، متن از روی همان اعداد واقعی سیگنال
   ساخته می‌شود.

چرا مسیر دوم حیاتی است؟ کاربر گزارش داد «الان سیگنال تولید نمی‌شود».
یکی از دلایلش این بود که همه‌چیز به پاسخ سرویس هوش مصنوعی گره خورده بود.
با این طراحی، **هیچ سیگنالی بدون تحلیل نوشتاری نمی‌ماند** حتی وقتی
اینترنت یا اعتبار نیست. متن قالبی هرگز عدد از خودش نمی‌سازد؛ فقط همان
مقادیر محاسبه‌شده را به زبان فارسی روایت می‌کند.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ai.providers.base import AIMessage
from app.core.constants import SignalDirection
from app.logging import get_logger

logger = get_logger(__name__)

#: سقف زمان انتظار برای متن هوش مصنوعی؛ پس از آن متن قالبی جایگزین می‌شود
DEFAULT_NARRATIVE_TIMEOUT = 45.0

#: دستور سیستمی نویسندهٔ فارسی
NARRATIVE_SYSTEM_PROMPT = """تو یک تحلیل‌گر ارشد بازار ارز دیجیتال هستی که به فارسی روان می‌نویسد.

قواعد نوشتن:
۱. فقط از داده‌هایی که به تو داده می‌شود استفاده کن. هیچ عددی از خودت نساز.
۲. به فارسی بنویس. اصطلاح‌های تخصصی انگلیسی را می‌توانی در پرانتز بیاوری.
۳. ساختار متن دقیقاً این چهار بخش باشد، هر بخش با همین عنوان‌ها:
   ## خلاصه
   ## دلایل فنی
   ## سطوح کلیدی و سناریوها
   ## مدیریت ریسک
۴. در بخش «خلاصه» در دو یا سه جمله بگو جهت چیست و چرا.
۵. در «دلایل فنی» به اندیکاتورها و تایم‌فریم‌ها اشاره کن و بگو هرکدام چه می‌گویند.
۶. در «سطوح کلیدی» بگو چه اتفاقی سناریو را باطل می‌کند.
۷. در «مدیریت ریسک» دربارهٔ حد ضرر و نسبت ریسک به سود بنویس.
۸. اگر جهت WAIT است، صادقانه توضیح بده چرا صبر کردن بهتر است. صبر کردن ضعف نیست.
۹. لحن حرفه‌ای و بی‌طرف باشد. وعدهٔ سود نده. این تحلیل توصیهٔ مالی نیست.
۱۰. بین ۱۵۰ تا ۳۵۰ کلمه بنویس. کوتاه و پرمغز، نه پرگو."""


def _is_mostly_latin(text: str) -> bool:
    """
    آیا متن عمدتاً لاتین است؟

    موتور سیگنال دلایلش را به انگلیسی می‌نویسد (زبان‌خنثی و مستقل از
    رابط کاربری). این متن نباید وسط تحلیل فارسی بیاید و آن را نامفهوم
    کند؛ به‌جایش در پیوستی جداگانه و برچسب‌دار نمایش داده می‌شود تا هیچ
    اطلاعاتی هم گم نشود.
    """
    letters = [c for c in str(text or "") if c.isalpha()]
    if not letters:
        return False
    latin = sum(1 for c in letters if "a" <= c.lower() <= "z")
    return latin > len(letters) * 0.5


def _fa(value: Any) -> str:
    """تبدیل عدد به رشتهٔ خوانا با جداکنندهٔ هزارگان."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == 0:
        return "۰"
    if abs(number) >= 1000:
        text = f"{number:,.2f}"
    elif abs(number) >= 1:
        text = f"{number:,.4f}".rstrip("0").rstrip(".")
    else:
        text = f"{number:.8f}".rstrip("0").rstrip(".")
    digits = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return text.translate(digits)


class NarrativeWriter:
    """
    تولید تحلیل نوشتاری فارسی برای یک سیگنال.

    مثال:
        writer = NarrativeWriter(provider_manager)
        text = await writer.write(signal, market_data)
    """

    def __init__(
        self,
        provider_manager: Any = None,
        *,
        timeout_seconds: float = DEFAULT_NARRATIVE_TIMEOUT,
        preferred_provider: str | None = None,
    ) -> None:
        self._providers = provider_manager
        self._timeout = float(timeout_seconds)
        #: سرویس انتخابی کاربر، تا زنجیره از سرویس خاموش شروع نشود
        self._preferred = preferred_provider

    # ------------------------------------------------------------------
    # نقطهٔ ورود
    # ------------------------------------------------------------------
    async def write(
        self,
        signal: Any,
        market_data: dict[str, Any] | None = None,
        *,
        prefer_ai: bool = True,
    ) -> tuple[str, str]:
        """
        نوشتن تحلیل.

        بازگشتی: (متن تحلیل، منبع) که منبع یکی از "ai" یا "template" است.

        این متد **هرگز خطا نمی‌دهد**. اگر هوش مصنوعی نتواند بنویسد، متن
        قالبی برگردانده می‌شود.
        """
        if prefer_ai and self._providers is not None:
            try:
                text = await asyncio.wait_for(
                    self._write_with_ai(signal, market_data or {}),
                    timeout=self._timeout,
                )
                if text and len(text.strip()) > 80:
                    return text.strip(), "ai"
                logger.info("AI narrative too short for %s; using template", getattr(signal, "symbol", "?"))
            except TimeoutError:
                logger.warning(
                    "AI narrative timed out after %.0fs for %s; using template",
                    self._timeout,
                    getattr(signal, "symbol", "?"),
                )
            except Exception as exc:  # noqa: BLE001 - نبود هوش مصنوعی نباید سیگنال را خراب کند
                logger.warning("AI narrative failed (%s); using template", exc.__class__.__name__)

        return self.template_narrative(signal, market_data or {}), "template"

    # ------------------------------------------------------------------
    # مسیر هوش مصنوعی
    # ------------------------------------------------------------------
    async def _write_with_ai(self, signal: Any, market_data: dict[str, Any]) -> str:
        """درخواست متن از سرویس هوش مصنوعی."""
        # باید AIMessage باشد نه dict خام: مدیر سرویس روی هر پیام
        # `to_dict()` صدا می‌زند. با dict خام یک AttributeError می‌گرفتیم
        # که در بالادست بلعیده می‌شد و تحلیل فارسی **همیشه** به قالب
        # آماده برمی‌گشت — بی‌آنکه کسی خطا ببیند.
        messages = [
            AIMessage(role="system", content=NARRATIVE_SYSTEM_PROMPT),
            AIMessage(role="user", content=self.build_prompt(signal, market_data)),
        ]
        response = await self._providers.generate(
            messages, temperature=0.35, preferred=self._preferred
        )
        if response is None:
            return ""
        content = getattr(response, "content", "") or ""
        return str(content)

    def build_prompt(self, signal: Any, market_data: dict[str, Any]) -> str:
        """
        ساخت متن ورودی برای مدل از روی دادهٔ واقعی سیگنال.

        همهٔ اعداد از خود سیگنال می‌آیند تا مدل چیزی از خودش نسازد.
        """
        direction = self._direction_of(signal)
        lines = [
            f"نماد: {getattr(signal, 'symbol', '؟')}",
            f"جهت پیشنهادی موتور تحلیل: {direction}",
            f"درجهٔ هم‌راستایی عوامل: {getattr(signal, 'confidence', 0)} از ۱۰۰",
        ]

        entry_min = getattr(signal, "entry_min", None)
        entry_max = getattr(signal, "entry_max", None)
        if entry_min and entry_max:
            lines.append(f"محدودهٔ ورود: {_fa(entry_min)} تا {_fa(entry_max)}")
        stop = getattr(signal, "stop_loss", None)
        if stop:
            lines.append(f"حد ضرر: {_fa(stop)}")
        targets = getattr(signal, "take_profits", None) or []
        if targets:
            lines.append("اهداف سود: " + "، ".join(_fa(t) for t in targets))
        rr = getattr(signal, "risk_reward", None)
        if rr:
            lines.append(f"نسبت ریسک به سود: {_fa(rr)}")
        trend = getattr(signal, "trend", None)
        if trend:
            lines.append(f"روند کلی: {getattr(trend, 'value', trend)}")
        structure = getattr(signal, "market_structure", None)
        if structure:
            lines.append(f"ساختار بازار: {getattr(structure, 'value', structure)}")
        timeframes = getattr(signal, "timeframes", None) or []
        if timeframes:
            lines.append("تایم‌فریم‌های بررسی‌شده: " + "، ".join(str(t) for t in timeframes))
        reason = getattr(signal, "reason", "")
        if reason:
            lines.append(f"خلاصهٔ دلیل موتور: {reason}")
        invalidation = getattr(signal, "invalidation", "")
        if invalidation:
            lines.append(f"شرط ابطال: {invalidation}")

        indicators = self._collect_indicators(market_data)
        if indicators:
            lines.append("")
            lines.append("مقادیر اندیکاتورها:")
            lines.extend(indicators)

        lines.append("")
        lines.append("بر پایهٔ همین داده‌ها تحلیل نوشتاری فارسی بنویس.")
        return "\n".join(lines)

    @staticmethod
    def _collect_indicators(market_data: dict[str, Any]) -> list[str]:
        """استخراج مقادیر اندیکاتور از دادهٔ بازار برای متن ورودی مدل."""
        lines: list[str] = []
        timeframes = market_data.get("timeframes") or {}
        if not isinstance(timeframes, dict):
            return lines
        for timeframe, payload in list(timeframes.items())[:6]:
            if not isinstance(payload, dict):
                continue
            indicators = payload.get("indicators") or {}
            if not isinstance(indicators, dict) or not indicators:
                continue
            parts: list[str] = []
            for name, value in list(indicators.items())[:8]:
                if isinstance(value, dict):
                    inner = value.get("value", value.get("signal"))
                    if inner is not None:
                        parts.append(f"{name}={_fa(inner)}")
                elif isinstance(value, (int, float)):
                    parts.append(f"{name}={_fa(value)}")
                elif isinstance(value, str):
                    parts.append(f"{name}={value}")
            if parts:
                lines.append(f"  • {timeframe}: " + "، ".join(parts))
        return lines

    # ------------------------------------------------------------------
    # مسیر قالبی
    # ------------------------------------------------------------------
    def template_narrative(self, signal: Any, market_data: dict[str, Any] | None = None) -> str:
        """
        ساخت تحلیل نوشتاری بدون هوش مصنوعی.

        متن از روی اعداد واقعی سیگنال ساخته می‌شود. ساختار آن همان چهار
        بخش مسیر هوش مصنوعی است تا خروجی PDF در هر دو حالت یکسان بماند.
        """
        symbol = getattr(signal, "symbol", "؟")
        direction = self._direction_of(signal)
        confidence = getattr(signal, "confidence", 0)
        timeframes = getattr(signal, "timeframes", None) or []
        trend = getattr(signal, "trend", None)
        trend_text = getattr(trend, "value", trend) or "نامشخص"
        structure = getattr(signal, "market_structure", None)
        structure_text = getattr(structure, "value", structure) or "نامشخص"

        direction_fa = {
            "LONG": "خرید (LONG)",
            "SHORT": "فروش (SHORT)",
            "WAIT": "انتظار (WAIT)",
        }.get(direction, direction)

        # ---- خلاصه ----
        if direction == "WAIT":
            summary = (
                f"در حال حاضر برای {symbol} سیگنال ورود صادر نمی‌شود و وضعیت «انتظار» است. "
                f"عوامل تحلیلی به اندازهٔ کافی هم‌جهت نیستند (هم‌راستایی {_fa(confidence)} از ۱۰۰) "
                "و ورود در چنین شرایطی ریسک بالایی دارد. صبر کردن هم یک تصمیم معاملاتی است."
            )
        else:
            summary = (
                f"برای {symbol} جهت پیشنهادی {direction_fa} است. "
                f"درجهٔ هم‌راستایی عوامل تحلیلی {_fa(confidence)} از ۱۰۰ است؛ "
                "این عدد میزان توافق شاخص‌هاست، نه احتمال سود."
            )

        # ---- دلایل فنی ----
        technical = [f"روند کلی بازار «{trend_text}» و ساختار قیمتی «{structure_text}» ارزیابی شده است."]
        if timeframes:
            technical.append(
                "تایم‌فریم‌های بررسی‌شده: " + "، ".join(str(t) for t in timeframes) + "."
            )
        indicators_used = getattr(signal, "indicators_used", None) or []
        if indicators_used:
            technical.append(
                "اندیکاتورهای مؤثر در این تصمیم: " + "، ".join(str(i) for i in indicators_used[:10]) + "."
            )
        reason = getattr(signal, "reason", "")
        engine_notes = ""
        if reason:
            if _is_mostly_latin(reason):
                # متن انگلیسی موتور را به پیوست منتقل می‌کنیم
                engine_notes = str(reason)
            else:
                technical.append(str(reason))

        # ---- سطوح کلیدی ----
        levels: list[str] = []
        entry_min = getattr(signal, "entry_min", None)
        entry_max = getattr(signal, "entry_max", None)
        if entry_min and entry_max:
            levels.append(f"محدودهٔ ورود پیشنهادی بین {_fa(entry_min)} و {_fa(entry_max)} است.")
        stop = getattr(signal, "stop_loss", None)
        if stop:
            levels.append(f"حد ضرر روی {_fa(stop)} در نظر گرفته شده است.")
        targets = getattr(signal, "take_profits", None) or []
        if targets:
            levels.append("اهداف سود به ترتیب: " + "، ".join(_fa(t) for t in targets) + ".")
        invalidation = getattr(signal, "invalidation", "")
        if invalidation and not _is_mostly_latin(invalidation):
            levels.append(f"شرط ابطال سناریو: {invalidation}")
        elif invalidation:
            levels.append(
                "سناریو زمانی باطل می‌شود که هم‌راستایی تایم‌فریم‌ها یا شرایط نوسان تغییر کند."
            )
        if not levels:
            levels.append(
                "تا وقتی قیمت از محدودهٔ فعلی خارج نشده، سطح ورود مشخصی پیشنهاد نمی‌شود."
            )

        # ---- مدیریت ریسک ----
        risk: list[str] = []
        rr = getattr(signal, "risk_reward", None)
        if rr:
            risk.append(f"نسبت ریسک به سود این موقعیت {_fa(rr)} برآورد شده است.")
        leverage = getattr(signal, "leverage", None)
        if leverage:
            risk.append(f"اهرم پیشنهادی {_fa(leverage)} است.")
        risk.append(
            "حجم معامله باید بر پایهٔ درصد ریسک تعیین‌شده در تنظیمات محاسبه شود و "
            "حد ضرر پیش از ورود ثبت گردد."
        )
        risk.append("این تحلیل توصیهٔ مالی نیست و مسئولیت معامله با کاربر است.")

        sections = [
            "## خلاصه",
            summary,
            "## دلایل فنی",
            " ".join(technical),
            "## سطوح کلیدی و سناریوها",
            " ".join(levels),
            "## مدیریت ریسک",
            " ".join(risk),
        ]
        if engine_notes:
            sections.extend(["## گزارش فنی موتور تحلیل", engine_notes])
        return "\n\n".join(sections)

    @staticmethod
    def _direction_of(signal: Any) -> str:
        """خواندن جهت سیگنال به‌صورت رشته، چه Enum باشد چه متن."""
        direction = getattr(signal, "direction", SignalDirection.WAIT)
        return str(getattr(direction, "value", direction)).upper()
