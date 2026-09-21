"""
آزمون‌های نسخه ۱.۹.۱۶ — «انتظار با اطمینان صفر» در مسیر هوش مصنوعی.

کاربر تصویری فرستاد که در آن چند نماد پشت سر هم با «انتظار» و «۰٪» ثبت
شده بودند. تفاوت این ایراد با چیزی که در ۱.۹.۱۵ رفع شد:

    ۱.۹.۱۵ → عامل **شکست می‌خورد** (JSON نامعتبر) و خروجی توخالی می‌داد.
    ۱.۹.۱۶ → عامل **موفق می‌شود** ولی خودِ مدل «انتظار/۰» برمی‌گرداند.

حالت دوم از فیلتر قبلی رد می‌شد چون `succeeded` درست بود. علت ریشه‌ای:
عامل «کور» شروع می‌کرد و باید کل تحلیل را در چند گام از داده خام
بازمی‌ساخت؛ مدل‌های کوچک‌تر در آن وضعیت به امن‌ترین پاسخ پناه می‌برند.
"""

from __future__ import annotations

from typing import Any

import pytest

from ai.agent.autonomous_agent import AgentOutcome, AutonomousAgent
from ui.controllers.main_controller import MainController


def _outcome(**kwargs: Any) -> AgentOutcome:
    """ساخت نتیجهٔ عامل با مقادیر دلخواه."""
    outcome = AgentOutcome(symbol=kwargs.pop("symbol", "BTC/USDT"))
    for key, value in kwargs.items():
        setattr(outcome, key, value)
    return outcome


class TestAHollowWaitIsNotAnAnalysis:
    """
    «انتظار با اطمینان صفر» حتی وقتی عامل موفق بوده، سیگنال نیست.

    این دقیقاً همان چیزی است که در تصویر کاربر دیده می‌شد.
    """

    def test_successful_but_empty_wait_is_rejected(self) -> None:
        """عاملِ موفق که «انتظار/۰» داده، قابل نمایش نیست."""
        outcome = _outcome(
            succeeded=True,
            decision={
                "direction": "WAIT",
                "confidence": 0,
                "reason": "Market conditions are unclear right now.",
            },
        )
        assert MainController._agent_outcome_is_usable(outcome) is False

    def test_wait_with_real_confidence_is_kept(self) -> None:
        """
        «انتظار» با اطمینان واقعی یک پاسخ معتبر است و باید نمایش داده شود.

        این مرز اصلی اصلاح است: اگر هر «انتظار»ی را دور بیندازیم، یک
        قابلیت درست را خراب کرده‌ایم.
        """
        outcome = _outcome(
            succeeded=True,
            decision={
                "direction": "WAIT",
                "confidence": 55,
                "reason": "بازار در فشردگی است و شکست تأیید نشده",
            },
        )
        assert MainController._agent_outcome_is_usable(outcome) is True

    @pytest.mark.parametrize("confidence", [0, -1])
    def test_non_positive_confidence_is_rejected(self, confidence: int) -> None:
        """اطمینان صفر یا منفی روی «انتظار» پذیرفته نمی‌شود."""
        outcome = _outcome(
            succeeded=True, decision={"direction": "WAIT", "confidence": confidence}
        )
        assert MainController._agent_outcome_is_usable(outcome) is False

    def test_a_directional_trade_at_zero_is_still_rejected(self) -> None:
        """جهت معاملاتی بدون اطمینان و بدون عدد هم قابل اتکا نیست."""
        outcome = _outcome(
            succeeded=False, decision={"direction": "LONG", "confidence": 0}
        )
        assert MainController._agent_outcome_is_usable(outcome) is False


class TestTheAgentStartsFromTheEngineResult:
    """
    علت ریشه‌ای: عامل بدون هیچ شاهد اولیه‌ای شروع می‌کرد.

    حالا نتیجهٔ موتور ریاضی به‌عنوان «شاهد از پیش محاسبه‌شده» در پرامپت
    می‌نشیند تا کار مدل قضاوت باشد، نه کشف دوباره.
    """

    def test_baseline_is_rendered_for_the_model(self) -> None:
        """مقادیر کلیدی سیگنال موتور در متن شاهد ظاهر می‌شوند."""
        text = AutonomousAgent._format_baseline(
            {
                "direction": "LONG",
                "confidence": 75,
                "entry_min": 80196.93,
                "stop_loss": 79067.08,
                "take_profits": [82280.17],
                "trend": "BULLISH",
                "reason": "EMA cross confirmed",
            }
        )
        assert "LONG" in text
        assert "75" in text
        assert "80196.93" in text
        assert "EMA cross confirmed" in text
        # مدل باید بداند حق مخالفت دارد ولی حق بی‌اعتنایی ندارد
        assert "WAIT with confidence 0" in text

    def test_enum_values_are_flattened(self) -> None:
        """
        مقدار شمارشی نباید به شکل `TrendDirection.BULLISH` به مدل برسد.

        دیدن نام کلاس پایتون فقط مدل را گیج می‌کند.
        """

        class _Trend:
            value = "BULLISH"

        text = AutonomousAgent._format_baseline(
            {"direction": "LONG", "confidence": 60, "trend": _Trend()}
        )
        assert "BULLISH" in text
        assert "_Trend" not in text
        assert "object at" not in text

    def test_missing_baseline_is_explained_not_blank(self) -> None:
        """نبود شاهد اولیه باید صریح گفته شود، نه یک بخش خالی."""
        text = AutonomousAgent._format_baseline(None)
        assert "No pre-computed analysis" in text

    def test_run_accepts_a_baseline(self) -> None:
        """امضای `run` باید شاهد اولیه را بپذیرد."""
        import inspect

        assert "baseline" in inspect.signature(AutonomousAgent.run).parameters

    def test_prompt_reserves_a_place_for_the_baseline(self) -> None:
        """جای شاهد در پرامپت سامانه رزرو شده است."""
        from ai.agent.autonomous_agent import SYSTEM_PROMPT

        assert "PRE-COMPUTED EVIDENCE" in SYSTEM_PROMPT
        assert "{baseline}" in SYSTEM_PROMPT

    def test_prompt_forbids_a_lazy_zero_confidence(self) -> None:
        """قانون صریح علیه «اطمینان صفر» در پرامپت هست."""
        from ai.agent.autonomous_agent import SYSTEM_PROMPT

        assert "confidence 0" in SYSTEM_PROMPT


class TestTheUiComputesTheEngineFirst:
    """مسیر رابط کاربری باید اول موتور را اجرا کند و نتیجه را بدهد به عامل."""

    def test_controller_passes_a_baseline_to_the_agent(self) -> None:
        """کنترلر سیگنال موتور را به‌عنوان شاهد به عامل می‌دهد."""
        import inspect

        source = inspect.getsource(MainController._generate_ai_signal)
        assert "baseline=engine_signal" in source

    def test_the_baseline_is_reused_for_the_fallback(self) -> None:
        """
        اگر هوش مصنوعی نتیجهٔ قابل استفاده ندهد، سیگنالِ از قبل حساب‌شده
        دوباره محاسبه نمی‌شود؛ کاربر نباید دو بار منتظر بماند.
        """
        import inspect

        source = inspect.getsource(MainController._fallback_to_engine_signal)
        assert "baseline_signal" in source

    def test_engine_failure_does_not_block_the_ai(self) -> None:
        """شکست موتور نباید جلوی اجرای عامل را بگیرد."""
        import inspect

        source = inspect.getsource(MainController._generate_ai_signal)
        # فراخوانی موتور داخل try/except است و عامل بعد از آن اجرا می‌شود
        assert "engine_signal = None" in source
        assert "except Exception" in source
