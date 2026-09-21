"""
آزمون‌های نسخه ۱.۹.۱۵ — سه ایرادی که کاربر روی صرافی LBank گزارش کرد.

۱. «تولید سیگنال» با تیک هوش مصنوعی همیشه «صبر» برمی‌گرداند.
۲. دکمهٔ معامله هیچ چیزی باز نمی‌کند و در تاریخچه دیده نمی‌شود.
۳. کیف پول فقط موجودی اسپات را نشان می‌دهد و فیوچرز غایب است.

هر کلاس یک ایراد را می‌بندد و آزمون‌ها روی همان قراردادی می‌ایستند که
اگر دوباره بشکند، کاربر همان شکایت قبلی را تکرار می‌کند.
"""

from __future__ import annotations

from typing import Any

import pytest

from ai.agent.autonomous_agent import AgentOutcome
from market.providers.lbank.provider import LBankProvider
from ui.controllers.main_controller import MainController


def _outcome(**kwargs: Any) -> AgentOutcome:
    """ساخت یک نتیجهٔ عامل با مقادیر دلخواه."""
    outcome = AgentOutcome(symbol=kwargs.pop("symbol", "BTC/USDT"))
    for key, value in kwargs.items():
        setattr(outcome, key, value)
    return outcome


class TestFailedAgentIsNotASignal:
    """
    ایراد اول: خروجیِ شکست‌خوردهٔ عامل نباید به‌جای سیگنال نمایش داده شود.

    عامل خودمختار وقتی مدل JSON معتبر نمی‌دهد یا مهلتش تمام می‌شود، یک
    «صبر با اطمینان صفر» می‌سازد. این از دید کاربر با یک تحلیل واقعی فرق
    ندارد و دقیقاً همان «همیشه صبر می‌دهد» است.
    """

    def test_agent_failure_is_rejected(self) -> None:
        """شکست عامل (JSON نامعتبر) خروجی قابل استفاده نیست."""
        outcome = _outcome(
            succeeded=False,
            decision={"direction": "WAIT", "confidence": 0},
            errors=["The model did not return valid JSON twice in a row"],
        )
        assert MainController._agent_outcome_is_usable(outcome) is False

    def test_provider_failure_is_rejected(self) -> None:
        """شکست سرویس هوش مصنوعی هم خروجی قابل استفاده نیست."""
        outcome = _outcome(
            succeeded=False,
            decision={"direction": "WAIT", "confidence": 0, "reason": "All AI providers failed"},
            errors=["All AI providers failed"],
        )
        assert MainController._agent_outcome_is_usable(outcome) is False

    def test_a_real_wait_is_still_a_valid_answer(self) -> None:
        """
        «صبر»ِ واقعی باید نمایش داده شود.

        این مهم‌ترین آزمون این کلاس است: اگر برای رفع ایراد، هر «صبر»ی را
        دور بیندازیم، قابلیت درست برنامه را خراب کرده‌ایم. «صبر» یک پاسخ
        درجه‌یک است، به شرطی که عامل واقعاً به آن رسیده باشد.
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

    def test_a_real_trade_is_usable(self) -> None:
        """تصمیم موفق با جهت معاملاتی قابل استفاده است."""
        outcome = _outcome(
            succeeded=True,
            decision={"direction": "LONG", "confidence": 72, "entry_min": 81000},
        )
        assert MainController._agent_outcome_is_usable(outcome) is True

    def test_numbers_without_success_still_count(self) -> None:
        """
        اگر اعتبارسنج ایراد گرفته ولی تصمیم عددی واقعی وجود دارد، حیف است
        دور انداخته شود؛ کاربر ترجیح می‌دهد آن را با هشدار ببیند.
        """
        outcome = _outcome(
            succeeded=False,
            decision={
                "direction": "LONG",
                "confidence": 61,
                "entry_min": 81000,
                "stop_loss": 79800,
            },
            errors=["Validation failed: risk/reward below minimum"],
        )
        assert MainController._agent_outcome_is_usable(outcome) is True

    def test_none_outcome_is_rejected(self) -> None:
        """نبود نتیجه هم شکست است، نه سیگنال."""
        assert MainController._agent_outcome_is_usable(None) is False

    def test_controller_has_an_engine_fallback(self) -> None:
        """
        مسیر هوش مصنوعی باید راه برگشتی به موتور ریاضی داشته باشد.

        ایراد نسخهٔ ۱.۹.۱۱ این بود که اصلاح در `Application.generate_signal`
        انجام شد، ولی تیک هوش مصنوعی در رابط کاربری اصلاً از آنجا رد
        نمی‌شود. این آزمون وجود پل را تضمین می‌کند.
        """
        assert callable(getattr(MainController, "_fallback_to_engine_signal", None))

    def test_ai_path_receives_the_selected_timeframes(self) -> None:
        """
        موتور جایگزین باید همان تایم‌فریم‌های انتخابی کاربر را بگیرد.

        بدون این، نتیجهٔ جایگزین با چیزی که کاربر در صفحه انتخاب کرده
        نمی‌خواند.
        """
        import inspect

        signature = inspect.signature(MainController._generate_ai_signal)
        assert "frames" in signature.parameters


class TestTheFallbackMessageExists:
    """پیام «هوش مصنوعی کنار گذاشته شد» باید در هر دو زبان وجود داشته باشد."""

    @pytest.mark.parametrize("language", ["fa", "en"])
    def test_key_is_translated(self, language: str) -> None:
        """کلید ترجمه در هر دو زبان تعریف شده است."""
        import json
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "localization" / language / "signals.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "ai_fell_back" in data
        assert "{reason}" in data["ai_fell_back"]


class TestTradeButtonReachesTheDatabase:
    """
    ایراد دوم: معاملهٔ ثبت‌شده باید در تاریخچه دیده شود.

    `PaperTrader` معامله را در یک رشتهٔ JSON داخل تنظیمات نگه می‌داشت،
    ولی صفحهٔ معاملات از `trade_repository` می‌خواند؛ دو انبار جدا.
    """

    def test_handler_writes_to_the_repository(self) -> None:
        """دکمهٔ معامله باید معامله را در پایگاه داده هم ثبت کند."""
        import inspect

        source = inspect.getsource(MainController._on_trade_requested)
        assert "record_paper_trade" in source, (
            "دکمهٔ معامله باید در پایگاه داده بنویسد وگرنه تاریخچه خالی می‌ماند"
        )

    def test_the_agreed_entry_price_is_passed_on(self) -> None:
        """
        قیمت ورودِ همان معامله باید به ثبت‌کننده برسد.

        `record_paper_trade` روی `entry_price` حساب می‌کند؛ اگر فرستاده
        نشود، به `entry_min` برمی‌گردد و ممکن است با قیمتی که به کاربر
        نشان داده شد فرق کند.
        """
        import inspect

        source = inspect.getsource(MainController._on_trade_requested)
        assert 'record["entry_price"] = position.entry' in source


class TestLbankFuturesBalance:
    """
    ایراد سوم: موجودی فیوچرز LBank خوانده نمی‌شد.

    مستند رسمی LBank برای `prv/account` پارامتر `asset` را لازم دارد؛
    بدون آن درخواست رد می‌شد و چون خطای فیوچرز عمداً بلعیده می‌شود،
    کاربر فقط اسپات را می‌دید.
    """

    def test_asset_parameter_is_sent(self) -> None:
        """برای هر دارایی، پارامتر `asset` همراه درخواست می‌رود."""
        from market.providers.lbank.constants import CONTRACT_ASSETS

        sent: list[dict[str, Any]] = []

        class _Client:
            has_credentials = True

            async def post_contract_signed(self, endpoint: str, params: dict) -> Any:
                sent.append(dict(params))
                return {"data": [{"asset": "USDT", "available": 25.0, "frozen": 5.0}]}

        provider = LBankProvider.__new__(LBankProvider)
        provider._client = _Client()  # noqa: SLF001

        import asyncio

        balances = asyncio.run(provider.fetch_futures_balance())

        assert sent, "هیچ درخواستی فرستاده نشد"
        for params in sent:
            assert "asset" in params, "پارامتر asset جا افتاده — همان ایراد اصلی"
            assert params["productGroup"] == "SwapU"
        assert [p["asset"] for p in sent] == list(CONTRACT_ASSETS)
        # چهار دارایی پرسیده شده و هرکدام ۳۰ واحد داده‌اند
        assert balances["USDT"] == pytest.approx(30.0 * len(CONTRACT_ASSETS))

    def test_a_single_failing_asset_does_not_hide_the_rest(self) -> None:
        """
        اگر یک دارایی خطا بدهد، بقیه باید نمایش داده شوند.

        کاربری که فقط USDT دارد نباید به‌خاطر نبود BTC کل کیف پول
        قراردادش را از دست بدهد.
        """

        class _Client:
            has_credentials = True

            async def post_contract_signed(self, endpoint: str, params: dict) -> Any:
                if params.get("asset") != "USDT":
                    raise RuntimeError("asset not available")
                return {"data": [{"asset": "USDT", "total": 120.0}]}

        provider = LBankProvider.__new__(LBankProvider)
        provider._client = _Client()  # noqa: SLF001

        import asyncio

        balances = asyncio.run(provider.fetch_futures_balance())
        assert balances == {"USDT": pytest.approx(120.0)}

    def test_total_failure_still_raises_for_the_connection_test(self) -> None:
        """
        اگر هیچ دارایی‌ای پاسخ ندهد، خطا باید بالا برود.

        «آزمایش اتصال» باید علت واقعی را بگوید، نه یک کیف پول خالیِ
        بی‌توضیح.
        """

        class _Client:
            has_credentials = True

            async def post_contract_signed(self, endpoint: str, params: dict) -> Any:
                raise RuntimeError("no contract permission")

        provider = LBankProvider.__new__(LBankProvider)
        provider._client = _Client()  # noqa: SLF001

        import asyncio

        with pytest.raises(RuntimeError, match="no contract permission"):
            asyncio.run(provider.fetch_futures_balance())

    def test_sync_still_survives_a_missing_futures_wallet(self) -> None:
        """نسخهٔ مهارشده هرگز خطا پرتاب نمی‌کند تا اسپات نمایش داده شود."""

        class _Client:
            has_credentials = True

            async def post_contract_signed(self, endpoint: str, params: dict) -> Any:
                raise RuntimeError("no contract permission")

        provider = LBankProvider.__new__(LBankProvider)
        provider._client = _Client()  # noqa: SLF001

        import asyncio

        assert asyncio.run(provider.get_futures_balance()) == {}

    def test_unnamed_row_uses_the_requested_asset(self) -> None:
        """
        پاسخی که نام دارایی را تکرار نمی‌کند نباید دور انداخته شود.

        وقتی موجودی یک دارایی مشخص پرسیده می‌شود، صرافی گاهی نامش را
        برنمی‌گرداند؛ پیش‌تر آن ردیف بی‌نام حذف می‌شد و موجودی صفر
        به نظر می‌رسید.
        """
        parsed = LBankProvider._parse_futures_balances(  # noqa: SLF001
            {"data": [{"available": 40.0, "frozen": 2.0}]}, "USDT"
        )
        assert parsed == {"USDT": pytest.approx(42.0)}

    def test_named_row_wins_over_the_default(self) -> None:
        """اگر پاسخ نام دارایی را بگوید، همان معتبر است."""
        parsed = LBankProvider._parse_futures_balances(  # noqa: SLF001
            {"data": [{"asset": "ETH", "total": 1.5}]}, "USDT"
        )
        assert parsed == {"ETH": pytest.approx(1.5)}
