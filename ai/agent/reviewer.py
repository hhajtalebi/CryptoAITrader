"""
بازبین سیگنال‌های بسته‌شده.

چرا وجود دارد؟
    کاربر دو چیز خواست که یک ریشه دارند: «سابقهٔ سیگنال باید تحلیل با
    هوش مصنوعی داشته باشد» و «بعضی سیگنال‌ها سودی نداده‌اند». پاسخ هر
    دو یکی است — برنامه باید از نتیجهٔ واقعی **درس بگیرد** و آن درس را
    نشان بدهد.

    تا امروز هوش مصنوعی فقط *پیش از* معامله حرف می‌زد: تحلیل می‌نوشت و
    سیگنال می‌ساخت. هیچ‌وقت برنمی‌گشت ببیند چه شد. برنامه‌ای که
    پیش‌بینی می‌کند ولی هرگز نتیجه را بازبینی نمی‌کند، هیچ‌گاه بهتر
    نمی‌شود و کاربر هم نمی‌فهمد به کدام نوع سیگنالش می‌تواند اعتماد
    کند.

طراحی:
    این کلاس فقط روی سیگنال‌های **بسته‌شده** کار می‌کند (هدف، حد ضرر یا
    انقضا). مدل نتیجهٔ واقعی را می‌بیند، پس کارش پیش‌بینی نیست — قضاوت
    گذشته است، که کار بسیار ساده‌تر و قابل‌اعتمادتری برای یک مدل زبانی
    است.

    نکتهٔ کلیدی در قالب پرامپت: مدل موظف است **تصمیم** را قضاوت کند نه
    فقط نتیجه را. معاملهٔ بازنده‌ای که منطق درستی داشت، تصمیم بدی نبود؛
    معاملهٔ برنده‌ای که روی ساختار ضعیف گرفته شد، تصمیم خوبی نبود. این
    تمایز، تفاوت بین مربی و تماشاگر است.

    بازبینی همیشه در پس‌زمینه و دسته‌ای انجام می‌شود، هرگز در مسیر
    تعامل کاربر.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timezone
from typing import Any

from ai.prompt_budget import strip_reasoning_block
from ai.providers.base import AIMessage
from app.core.constants import Language
from app.logging import get_logger

logger = get_logger(__name__)

#: دسته‌بندی‌های مجاز درس. هر چیز دیگری از مدل، به NOISE نگاشت می‌شود
#: تا داده‌های آماری آلوده نشوند.
VALID_LESSONS: frozenset[str] = frozenset(
    {
        "GOOD_SETUP",
        "LATE_ENTRY",
        "WEAK_STRUCTURE",
        "BAD_TIMING",
        "STOP_TOO_TIGHT",
        "TARGET_TOO_FAR",
        "NOISE",
    }
)

#: وضعیت‌هایی که «بسته‌شده» حساب می‌شوند و ارزش بازبینی دارند.
REVIEWABLE_STATUSES: frozenset[str] = frozenset({"TARGET", "STOP", "EXPIRED"})

#: بیشترین تعداد بازبینی در هر دور، تا مدل محلی خفه نشود.
DEFAULT_BATCH_SIZE = 5

LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    Language.FA.value: (
        "Write 'verdict' and 'review' in Persian (فارسی). Keep the 'lesson' "
        "value in English exactly as listed. Keep symbol names and numbers in "
        "Latin characters."
    ),
    Language.EN.value: "Write 'verdict' and 'review' in clear, professional English.",
}


@dataclass(slots=True)
class ReviewResult:
    """
    نتیجهٔ یک بازبینی.

    `ok` جدا از محتوا نگه داشته می‌شود چون شکست بازبینی یک حالت عادی و
    پشتیبانی‌شده است: مدل محلی ممکن است در دسترس نباشد و این هرگز
    نباید جلوی کار کاربر را بگیرد.
    """

    signal_id: int
    ok: bool = False
    verdict: str = ""
    lesson: str = ""
    review: str = ""
    provider: str = ""
    model: str = ""
    error: str = ""


def _fmt(value: Any, digits: int = 2) -> str:
    """قالب‌بندی امن عدد برای درج در پرامپت."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "unknown"
    return f"{number:.{digits}f}"


def _duration_hours(created_at: Any, closed_at: Any) -> str:
    """طول عمر معامله به ساعت."""
    if not created_at or not closed_at:
        return "unknown"
    try:
        start = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
        end = closed_at if closed_at.tzinfo else closed_at.replace(tzinfo=timezone.utc)
        return f"{(end - start).total_seconds() / 3600:.1f}"
    except (AttributeError, TypeError):
        return "unknown"


def normalize_lesson(value: str) -> str:
    """
    نگاشت پاسخ مدل به یکی از دسته‌های مجاز.

    مدل‌های کوچک گاهی چیزی شبیه ولی نه دقیقاً برچسب خواسته‌شده
    برمی‌گردانند. بدون این نگاشت، صفحهٔ آمار پر از دسته‌های تک‌عضوی
    می‌شود و هیچ الگویی دیده نمی‌شود.
    """
    raw = (value or "").strip().upper().replace(" ", "_").replace("-", "_")
    if raw in VALID_LESSONS:
        return raw
    # رشتهٔ خیلی کوتاه هیچ اطلاعاتی ندارد؛ تطبیق زیررشته‌ای روی آن به
    # نخستین دستهٔ فهرست می‌چسبد و آمار را بی‌صدا خراب می‌کند.
    if len(raw) >= 4:
        for lesson in sorted(VALID_LESSONS):
            if lesson in raw or raw in lesson:
                return lesson
    return "NOISE"


class SignalReviewer:
    """
    تولیدکنندهٔ بازبینی برای سیگنال‌های بسته‌شده.

    وابستگی‌ها تزریق می‌شوند تا در آزمون بتوان جایگزینشان کرد.
    """

    def __init__(
        self,
        providers: Any,
        prompts: Any,
        *,
        language: str = Language.FA.value,
        preferred_provider: str = "",
    ) -> None:
        self._providers = providers
        self._prompts = prompts
        self._language = language
        self._preferred = preferred_provider or None

    def set_language(self, language: str) -> None:
        """تغییر زبان خروجی بازبینی."""
        self._language = language

    # ------------------------------------------------------------------
    # ساخت پرامپت
    # ------------------------------------------------------------------
    def build_prompt(self, signal: Any, outcome: Any) -> str:
        """
        ساخت پرامپت بازبینی از سیگنال و نتیجهٔ آن.

        فقط اعدادی که واقعاً وجود دارند فرستاده می‌شوند؛ جای خالی با
        `unknown` پر می‌شود تا مدل وسوسه نشود عدد بسازد.
        """
        template = self._prompts.get("signal_review")
        take_profits = getattr(signal, "take_profits", None) or []
        return template.render(
            symbol=getattr(signal, "symbol", ""),
            direction=getattr(signal, "direction", ""),
            outcome=getattr(outcome, "status", ""),
            entry=_fmt(getattr(outcome, "entry_price", 0), 8),
            stop_loss=_fmt(getattr(outcome, "stop_loss", 0), 8),
            take_profits=", ".join(_fmt(t, 8) for t in take_profits) or "none",
            confidence=int(getattr(outcome, "confidence", 0) or 0),
            timeframe=getattr(outcome, "primary_timeframe", "") or "unknown",
            result_percent=_fmt(getattr(outcome, "result_percent", 0)),
            realized_r=_fmt(getattr(outcome, "realized_r", 0)),
            max_favorable=_fmt(getattr(outcome, "max_favorable_percent", 0)),
            max_adverse=_fmt(getattr(outcome, "max_adverse_percent", 0)),
            duration_hours=_duration_hours(
                getattr(signal, "created_at", None), getattr(outcome, "closed_at", None)
            ),
            original_reason=(getattr(signal, "reason", "") or "not recorded")[:800],
            language_instruction=LANGUAGE_INSTRUCTIONS.get(
                self._language, LANGUAGE_INSTRUCTIONS[Language.EN.value]
            ),
        )

    # ------------------------------------------------------------------
    # بازبینی
    # ------------------------------------------------------------------
    async def review(self, signal: Any, outcome: Any) -> ReviewResult:
        """
        بازبینی یک سیگنال بسته‌شده.

        هرگز استثنا پرتاب نمی‌کند: نبود هوش مصنوعی یک حالت عادی است و
        `ok=False` برمی‌گردد.
        """
        signal_id = int(getattr(signal, "id", 0) or 0)
        status = str(getattr(outcome, "status", "") or "").upper()

        if status not in REVIEWABLE_STATUSES:
            return ReviewResult(
                signal_id=signal_id,
                error=f"outcome '{status}' is not closed yet",
            )

        try:
            prompt = self.build_prompt(signal, outcome)
        except Exception as exc:  # noqa: BLE001 - قالب خراب نباید برنامه را بکشد
            logger.warning("Could not build review prompt: %s", exc.__class__.__name__)
            return ReviewResult(signal_id=signal_id, error=exc.__class__.__name__)

        try:
            response = await self._providers.generate(
                [
                    AIMessage(
                        "system",
                        "You are an honest, numerate trading coach reviewing closed trades.",
                    ),
                    AIMessage("user", prompt),
                ],
                preferred=self._preferred,
                json_mode=True,
            )
        except Exception as exc:  # noqa: BLE001 - نبود مدل، حالت پشتیبانی‌شده است
            logger.info(
                "Review unavailable for signal %s: %s", signal_id, exc.__class__.__name__
            )
            return ReviewResult(
                signal_id=signal_id,
                error=getattr(exc, "message", str(exc)),
            )

        parsed = self._parse(response.content)
        if parsed is None:
            return ReviewResult(
                signal_id=signal_id,
                provider=response.provider,
                model=response.model,
                error="the model did not return usable JSON",
            )

        return ReviewResult(
            signal_id=signal_id,
            ok=True,
            verdict=str(parsed.get("verdict") or "")[:300],
            lesson=normalize_lesson(str(parsed.get("lesson") or "")),
            review=str(parsed.get("review") or ""),
            provider=response.provider,
            model=response.model,
        )

    @staticmethod
    def _parse(content: str) -> dict[str, Any] | None:
        """
        استخراج JSON از پاسخ مدل.

        بلوک استدلال مدل‌های reasoning اول پاک می‌شود؛ بدون آن،
        `json.loads` روی خروجی `deepseek-r1` همیشه شکست می‌خورد.
        """
        text = strip_reasoning_block(content or "")
        if not text:
            return None

        candidates = [text]
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            candidates.append(text[start : end + 1])

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    # ------------------------------------------------------------------
    # اجرای دسته‌ای
    # ------------------------------------------------------------------
    async def review_batch(
        self,
        pairs: list[tuple[Any, Any]],
        *,
        limit: int = DEFAULT_BATCH_SIZE,
    ) -> list[ReviewResult]:
        """
        بازبینی چند سیگنال، یکی پس از دیگری.

        چرا ترتیبی و نه موازی؟
            مدل محلی روی همان دستگاه کاربر اجرا می‌شود و چند درخواست
            هم‌زمان، حافظه را تمام می‌کند — همان خطای ۵۰۰ که کاربر با
            اولاما دید. اینجا کندی کاملاً بی‌اهمیت است چون کار در
            پس‌زمینه انجام می‌شود.
        """
        results: list[ReviewResult] = []
        for signal, outcome in pairs[: max(1, int(limit))]:
            results.append(await self.review(signal, outcome))
        return results
