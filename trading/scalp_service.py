"""
سرویس اسکلپ — چسبِ میان پویشگر، هوش مصنوعی و موتور معامله.

جریان کار:

    ۱. همهٔ تیکرها (یک درخواست، حدود هزار نماد)
    ۲. فیلتر نقدینگی — هزار نماد به چند ده نماد
    ۳. کندل و دفتر سفارش فقط برای همان چند ده
    ۴. امتیازدهی ریاضی
    ۵. **اختیاری:** هوش مصنوعی چند نامزد برتر را بازبینی می‌کند
    ۶. تحویل به موتور معاملهٔ خودکار

چرا هوش مصنوعی فقط در گام ۵؟
    فرستادن هزار نماد به مدل، هم کند است و هم توکن می‌سوزاند — همان
    اشتباهی که در پویش انبوه سیگنال‌ها از آن پرهیز کردیم. ریاضی
    فهرست را کوتاه می‌کند، هوش مصنوعی فقط دربارهٔ چند گزینهٔ نهایی
    قضاوت می‌کند.

    و اگر هوش مصنوعی در دسترس نباشد، سرویس **بدون آن کار می‌کند**.
    موتور ریاضی هرگز نباید گروگان مدل باشد.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.logging import get_logger
from trading.scalp_scanner import (
    ScalpCandidate,
    feasibility_note,
    prefilter_symbols,
    rank_candidates,
    score_candidate,
    spread_from_orderbook,
)

logger = get_logger(__name__)

#: چند نامزد برتر به هوش مصنوعی داده شود. بیشتر از این، فقط هزینه است.
AI_REVIEW_LIMIT = 5

#: همزمانی گرفتن داده. زیاد کردنش صرافی را عصبانی می‌کند.
FETCH_CONCURRENCY = 6

AI_SYSTEM_PROMPT = (
    "تو یک تحلیل‌گر معاملات بسیار کوتاه‌مدت (اسکلپ) هستی. فهرستی از "
    "نامزدها با داده‌های عددی می‌گیری و باید بگویی کدام‌ها برای معاملهٔ "
    "چند دقیقه‌ای مناسب‌ترند.\n"
    "قواعد:\n"
    "۱. فقط بر پایهٔ داده قضاوت کن؛ چیزی از خودت نساز.\n"
    "۲. «مناسب نیست» پاسخ کاملاً معتبری است.\n"
    "۳. نوسان بدون نقدینگی بی‌ارزش است.\n"
    "۴. خروجی فقط JSON معتبر باشد، بدون هیچ متن اضافه.\n"
    'قالب: {"picks":[{"symbol":"...","verdict":"good|skip",'
    '"confidence":0-100,"reason":"یک جملهٔ کوتاه فارسی"}]}'
)


class ScalpService:
    """سرویس پویش و پیشنهاد اسکلپ."""

    def __init__(self, app: Any) -> None:
        self._app = app

    # ---- خواندن تنظیم‌ها ---------------------------------------------

    def _setting(self, key: str, fallback: Any) -> Any:
        """خواندن یک تنظیم با پشتیبان امن."""
        try:
            return self._app.settings.get(key, fallback)
        except Exception:  # noqa: BLE001
            return fallback

    # ---- پویش --------------------------------------------------------

    async def scan(self, *, use_ai: bool | None = None) -> list[ScalpCandidate]:
        """
        یک دور کامل پویش.

        همیشه فهرست برمی‌گرداند — شاید خالی. فهرست خالی یعنی «الان
        فرصت خوبی نیست»، که پاسخ درستی است.
        """
        min_turnover = float(self._setting("scalp.min_turnover", 2_000_000.0))
        max_spread = float(self._setting("scalp.max_spread", 0.25))
        scan_limit = int(self._setting("scalp.scan_limit", 25))

        tickers = await self._app.market.get_all_tickers()
        shortlist = prefilter_symbols(
            tickers, min_turnover=min_turnover, limit=scan_limit
        )
        logger.info(
            "Scalp scan: %d tickers -> %d after liquidity filter",
            len(tickers), len(shortlist),
        )

        semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)

        async def evaluate(ticker: Any) -> ScalpCandidate | None:
            async with semaphore:
                try:
                    candles = await self._app.market.get_candles(ticker.symbol, "5m", 60)
                    book = await self._app.market.get_orderbook(ticker.symbol, 5)
                except Exception:  # noqa: BLE001
                    # یک نماد خراب نباید کل پویش را متوقف کند.
                    logger.debug("Scalp data fetch failed for %s", ticker.symbol)
                    return None
                return score_candidate(
                    ticker,
                    candles,
                    spread=spread_from_orderbook(book),
                    max_spread=max_spread,
                )

        results = await asyncio.gather(
            *(evaluate(ticker) for ticker in shortlist), return_exceptions=True
        )
        candidates = [
            item for item in results if isinstance(item, ScalpCandidate)
        ]
        ranked = rank_candidates(candidates, limit=10)
        logger.info("Scalp scan produced %d candidates", len(ranked))

        should_use_ai = (
            self._setting("scalp.ai_review", True) if use_ai is None else use_ai
        )
        if should_use_ai and ranked:
            ranked = await self._ai_review(ranked)
        return ranked

    # ---- بازبینی هوش مصنوعی ------------------------------------------

    async def _ai_review(self, candidates: list[ScalpCandidate]) -> list[ScalpCandidate]:
        """
        بازبینی چند نامزد برتر توسط هوش مصنوعی.

        اگر مدل در دسترس نباشد یا پاسخ نامعتبر بدهد، فهرست ریاضی
        دست‌نخورده برمی‌گردد. هوش مصنوعی اینجا **مشاور** است نه دروازه‌بان.
        """
        provider = getattr(self._app, "ai_provider", None) or getattr(
            self._app, "ai", None
        )
        if provider is None:
            return candidates

        top = candidates[:AI_REVIEW_LIMIT]
        payload = [
            {
                "symbol": c.symbol,
                "direction": c.direction,
                "volatility_5m_percent": round(c.volatility_5m, 3),
                "momentum_percent": round(c.momentum, 3),
                "spread_percent": round(c.spread_percent, 4),
                "turnover_24h_usd": round(c.turnover_24h),
                "expected_net_percent": round(c.expected_net_percent, 3),
            }
            for c in top
        ]

        try:
            from ai.providers.base import AIMessage

            response = await asyncio.wait_for(
                provider.generate(
                    [
                        AIMessage(role="system", content=AI_SYSTEM_PROMPT),
                        AIMessage(
                            role="user",
                            content=json.dumps(payload, ensure_ascii=False),
                        ),
                    ],
                    json_mode=True,
                ),
                timeout=float(self._setting("signals.ai_timeout", 120)),
            )
        except (TimeoutError, asyncio.TimeoutError):
            logger.warning("Scalp AI review timed out; using maths-only ranking")
            return candidates
        except Exception:  # noqa: BLE001
            logger.exception("Scalp AI review failed; using maths-only ranking")
            return candidates

        verdicts = self._parse_ai_verdicts(getattr(response, "content", ""))
        if not verdicts:
            return candidates

        for candidate in top:
            verdict = verdicts.get(candidate.symbol.upper())
            if not verdict:
                continue
            candidate.reasons.append(f"هوش مصنوعی: {verdict['reason']}")
            if verdict["verdict"] == "skip":
                # رد هوش مصنوعی امتیاز را پایین می‌آورد ولی نامزد را حذف
                # نمی‌کند؛ تصمیم نهایی با کاربر است.
                candidate.score -= 100.0
                candidate.reasons.append("هوش مصنوعی این نماد را توصیه نکرد")
        return rank_candidates(candidates, limit=10)

    @staticmethod
    def _parse_ai_verdicts(content: str) -> dict[str, dict[str, Any]]:
        """
        استخراج نظر مدل.

        مدل‌های محلی گاهی JSON را داخل متن می‌پیچند؛ پس بخش میان
        نخستین `{` و آخرین `}` برداشته می‌شود.
        """
        if not content:
            return {}
        text = content.strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return {}
        try:
            data = json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            return {}

        picks = data.get("picks") if isinstance(data, dict) else None
        if not isinstance(picks, list):
            return {}

        verdicts: dict[str, dict[str, Any]] = {}
        for item in picks:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol") or "").upper()
            if not symbol:
                continue
            verdict = str(item.get("verdict") or "good").lower()
            verdicts[symbol] = {
                "verdict": "skip" if verdict == "skip" else "good",
                "reason": str(item.get("reason") or "").strip() or "بدون توضیح",
                "confidence": item.get("confidence"),
            }
        return verdicts

    # ---- صداقت دربارهٔ هدف --------------------------------------------

    def feasibility(self, candidate: ScalpCandidate) -> tuple[bool, str]:
        """آیا هدف سود کاربر با این نامزد شدنی است؟"""
        return feasibility_note(
            float(self._setting("scalp.target_profit", 2.0)),
            float(self._setting("scalp.margin_per_trade", 10.0)),
            float(self._setting("scalp.leverage", 10.0)),
            candidate.volatility_5m,
        )

    def build_trader_config(self) -> Any:
        """ساخت پیکربندی موتور خودکار از روی تنظیم‌های کاربر."""
        from trading.auto_trader import AutoTradeConfig

        return AutoTradeConfig(
            margin_per_trade=float(self._setting("scalp.margin_per_trade", 10.0)),
            target_profit=float(self._setting("scalp.target_profit", 2.0)),
            max_loss=float(self._setting("scalp.max_loss", 3.0)),
            leverage=float(self._setting("scalp.leverage", 10.0)),
            max_concurrent=int(self._setting("scalp.max_concurrent", 3)),
            max_hold_seconds=int(self._setting("scalp.max_hold_seconds", 900)),
            poll_seconds=float(self._setting("scalp.poll_seconds", 5.0)),
            daily_loss_limit=float(self._setting("scalp.daily_loss_limit", 20.0)),
            mode=str(self._setting("scalp.mode", "paper")),
            live_confirmation=str(self._setting("scalp.live_confirmation", "")),
            fee_rate=float(self._setting("scalp.taker_fee_rate", 0.0006) or 0.0006),
        ).validated()
