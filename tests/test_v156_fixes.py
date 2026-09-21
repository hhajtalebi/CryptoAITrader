"""
آزمون‌های رگرسیون نسخهٔ ۱.۵.۶.

چهار نقصی که کاربر گزارش کرد اینجا قفل می‌شوند تا دوباره برنگردند:
کیف پول خالی LBank، ورود ناموفق با ایمیل/نام، شکست هوش مصنوعی در مسیر
سیگنال، و بی‌نظمی فهرست مدل‌ها.
"""

from __future__ import annotations

import pytest

from ai.agent.autonomous_agent import AutonomousAgent
from ai.providers.ranking import is_free_model, score_model, sort_models
from market.providers.lbank.provider import LBankProvider


# ---------------------------------------------------------------------------
# ۱) تجزیهٔ موجودی LBank
# ---------------------------------------------------------------------------
class TestLBankBalanceParsing:
    """پاسخ user_info.do یک «لیست» است، نه دیکشنری."""

    @staticmethod
    def _parse(payload):
        """فراخوانی تجزیه‌گر واقعی بدون تماس شبکه."""
        return LBankProvider._parse_balances(payload)

    def test_list_payload_is_parsed(self):
        """شکل واقعی پاسخ صرافی باید موجودی بدهد."""
        payload = [
            {"coin": "conway", "usableAmt": "80540.596", "freezeAmt": "0", "assetAmt": "80540.596"},
            {"coin": "trx", "usableAmt": "0.46", "freezeAmt": "0", "assetAmt": "0.46"},
        ]
        result = self._parse(payload)
        assert result["CONWAY"] == pytest.approx(80540.596)
        assert result["TRX"] == pytest.approx(0.46)

    def test_dict_payload_still_supported(self):
        """شکل قدیمی (دیکشنری) نباید بشکند."""
        payload = {"balances": [{"coin": "usdt", "free": "12.5", "locked": "0"}]}
        assert self._parse(payload)["USDT"] == pytest.approx(12.5)

    def test_zero_free_does_not_fall_through(self):
        """
        الگوی «free or usableAmt» باگ است.

        وقتی free برابر صفر است نباید مقدار کلید دیگر جایش بنشیند.
        """
        payload = [{"coin": "btc", "free": "0", "usableAmt": "99", "locked": "0"}]
        assert self._parse(payload).get("BTC", 0.0) == pytest.approx(0.0)

    def test_empty_and_malformed_are_safe(self):
        """ورودی خراب نباید استثنا بدهد."""
        for payload in ([], {}, None, [{"no_coin": 1}], "junk"):
            assert isinstance(self._parse(payload), dict)


# ---------------------------------------------------------------------------
# ۲) ورود با نام کاربری، ایمیل یا نام نمایشی
# ---------------------------------------------------------------------------
class TestLoginIdentifiers:
    """کاربر باید با هر سه شناسه بتواند وارد شود."""

    @pytest.fixture
    def account(self, database):
        """ساخت یک کاربر نمونه."""
        from app.database.repositories.user_repository import UserRepository

        repo = UserRepository(database)
        repo.create_user(
            username="hosein",
            password="StrongPass!234",
            email="hosein@example.com",
            display_name="حسین حاج طالبی",
        )
        return repo

    @pytest.mark.parametrize(
        "identifier",
        ["hosein", "Hosein", "  hosein  ", "hosein@example.com",
         "HOSEIN@EXAMPLE.COM", "حسین حاج طالبی"],
    )
    def test_valid_identifiers_authenticate(self, account, identifier):
        """هر شناسهٔ معتبر با رمز درست باید بپذیرد."""
        record, reason = account.authenticate(identifier, "StrongPass!234")
        assert record is not None, reason
        assert record["username"] == "hosein"

    def test_wrong_password_rejected(self, account):
        """رمز غلط حتی با شناسهٔ درست باید رد شود."""
        record, reason = account.authenticate("hosein@example.com", "nope")
        assert record is None
        assert reason == "auth.error.invalid_credentials"

    def test_unknown_identifier_rejected(self, account):
        """شناسهٔ ناشناس نباید وارد شود."""
        record, reason = account.authenticate("ghost@example.com", "StrongPass!234")
        assert record is None
        assert reason == "auth.error.invalid_credentials"


# ---------------------------------------------------------------------------
# ۳) نجات پاسخ بریدهٔ مدل در مسیر سیگنال
# ---------------------------------------------------------------------------
class TestTruncatedJsonRecovery:
    """مدل‌های استدلالی وسط JSON تمام می‌شوند؛ باید ترمیم شود."""

    def test_truncated_final_is_recovered(self):
        """تصمیم نیمه‌کاره باید با مقادیر کامل بازیابی شود."""
        raw = (
            '{"thought":"bearish","final":{"direction":"SHORT","confidence":68,'
            '"entry":76958.1,"stop_loss":77649.8,"take_profits":[76266.9,75578.1'
        )
        parsed = AutonomousAgent._parse(raw)
        assert parsed["final"]["direction"] == "SHORT"
        assert parsed["final"]["confidence"] == 68
        assert parsed["final"]["stop_loss"] == pytest.approx(77649.8)

    def test_truncated_number_is_dropped_not_corrupted(self):
        """
        مهم‌ترین آزمون ایمنی.

        عدد نیمه‌بریده هرگز نباید به عدد کوچک‌تر تبدیل شود؛ «۷۵» بریده
        نباید «۷» شود چون مستقیم روی حجم معامله اثر می‌گذارد.
        """
        parsed = AutonomousAgent._parse(
            '{"thought":"x","final":{"direction":"LONG","confidence":7'
        )
        assert parsed["final"]["direction"] == "LONG"
        assert "confidence" not in parsed["final"]

    def test_complete_json_unchanged(self):
        """پاسخ سالم نباید دست بخورد."""
        parsed = AutonomousAgent._parse('{"thought":"x","final":{"direction":"WAIT"}}')
        assert parsed == {"thought": "x", "final": {"direction": "WAIT"}}

    def test_fenced_json_supported(self):
        """JSON داخل ``` هم باید خوانده شود."""
        parsed = AutonomousAgent._parse('```json\n{"tool":"get_current_price"}\n```')
        assert parsed["tool"] == "get_current_price"

    def test_pure_prose_returns_none(self):
        """متن بدون JSON نباید الکی چیزی بسازد."""
        assert AutonomousAgent._parse("I think maybe the ATR is 1.19 so we wait.") is None


# ---------------------------------------------------------------------------
# ۴) ترتیب مدل‌ها
# ---------------------------------------------------------------------------
class TestModelRanking:
    """قوی‌ترین مدل‌ها باید بالای فهرست بیایند."""

    def test_flagship_beats_small_model(self):
        """مدل پرچم‌دار از مدل کوچک بالاتر است."""
        assert score_model("openai/gpt-5") > score_model("meta-llama/llama-3.2-1b:free")

    def test_irrelevant_models_sink(self):
        """مدل تعبیه‌سازی/صوتی/تصویری ته فهرست می‌رود."""
        ordered = sort_models(
            ["text-embedding-3-large", "openai/gpt-5", "whisper-large-v3", "stable-diffusion-xl"]
        )
        assert ordered[0] == "openai/gpt-5"
        assert set(ordered[1:]) == {"text-embedding-3-large", "whisper-large-v3", "stable-diffusion-xl"}

    def test_opus_outranks_haiku(self):
        """درون یک خانواده هم ترتیب توان رعایت شود."""
        assert score_model("anthropic/claude-opus-4.5") > score_model("anthropic/claude-haiku-4.5")

    def test_vendor_diversity_in_top_results(self):
        """
        صدر فهرست نباید در انحصار یک سازنده باشد.

        بدون تنوع، ده‌ها نسخهٔ هم‌خانواده کل بالای فهرست را می‌گیرند.
        """
        models = [f"openai/gpt-5.{i}" for i in range(10)] + [
            "anthropic/claude-opus-4.5", "google/gemini-2.5-pro",
        ]
        top = sort_models(models)[:3]
        assert len({m.split("/")[0] for m in top}) == 3

    def test_free_flag_detected(self):
        """تشخیص مدل رایگان طبق قرارداد OpenRouter."""
        assert is_free_model("deepseek/deepseek-r1:free")
        assert not is_free_model("openai/gpt-5")

    def test_sorting_is_stable_and_deduplicated(self):
        """خروجی نباید تکراری داشته باشد یا بین دو فراخوانی بپرد."""
        models = ["openai/gpt-5", "openai/gpt-5", "google/gemini-2.5-pro"]
        assert sort_models(models) == sort_models(models)
        assert len(sort_models(models)) == 2


# ---------------------------------------------------------------------------
# ۵) بهبودهای دور دوم: مسیر قیمت واسط، سهمیهٔ روزانه، فراخوانی تکراری
# ---------------------------------------------------------------------------
class TestIndirectPricing:
    """دارایی بدون جفت تتری باید از راه ارز واسط قیمت بگیرد."""

    @staticmethod
    def _controller(prices):
        """کنترلری سبک که فقط قیمت‌یابی‌اش آزموده می‌شود."""
        from ui.controllers.main_controller import MainController

        controller = MainController.__new__(MainController)
        controller._asset_prices = {}
        controller._price_history = {}
        controller.markets = None

        async def fake_ticker(symbol):
            return float(prices.get(symbol, 0.0))

        controller._ticker_price = fake_ticker
        controller._last_price = lambda symbol: 0.0
        return controller

    def test_direct_usdt_pair_preferred(self, qt_application):
        """وقتی جفت تتری هست، همان استفاده شود."""
        import asyncio

        controller = self._controller({"TRX/USDT": 0.34, "TRX/BTC": 0.000004})
        assert asyncio.run(controller._usdt_price("TRX")) == pytest.approx(0.34)

    def test_bridge_pair_used_when_no_usdt_market(self, qt_application):
        """
        BTCV در LBank جفت تتری ندارد ولی BTCV/BTC دارد.

        بدون مسیر واسط، این دارایی بی‌ارزش نمایش داده می‌شد.
        """
        import asyncio

        controller = self._controller({"BTCV/BTC": 5.33e-06, "BTC/USDT": 77158.69})
        value = asyncio.run(controller._usdt_price("BTCV"))
        assert value == pytest.approx(5.33e-06 * 77158.69)

    def test_tether_is_one_without_any_market(self, qt_application):
        """بازار «USDT/USDT» وجود ندارد؛ خود متد باید این را بداند."""
        import asyncio

        assert asyncio.run(self._controller({})._usdt_price("USDT")) == pytest.approx(1.0)

    def test_unpriceable_asset_returns_zero(self, qt_application):
        """
        دارایی بدون هیچ بازاری باید صفر بدهد، نه عددی ساختگی.

        CONWAY در LBank هیچ جفتی ندارد و «—» صادقانه‌تر از عدد است.
        """
        import asyncio

        assert asyncio.run(self._controller({})._usdt_price("CONWAY")) == pytest.approx(0.0)


class TestDailyQuotaMessage:
    """سقف روزانه با «اعتبار تمام‌شده» اشتباه گرفته می‌شد."""

    @staticmethod
    def _raise_for(status, detail):
        """اجرای مسیر خطای واقعی ارائه‌دهنده روی یک پاسخ ساختگی."""
        from ai.providers.openai_compatible import OpenAICompatibleProvider

        class FakeResponse:
            status_code = status

            @staticmethod
            def json():
                return {"error": {"message": detail}}

            text = detail

        provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
        # ویژگی name از روی config خوانده می‌شود، پس هر دو باید ست شوند
        provider._config = type("C", (), {"model": "m", "name": "openrouter"})()
        try:
            provider._raise_for_status(FakeResponse())
        except Exception as exc:  # noqa: BLE001
            return exc
        return None

    def test_daily_limit_is_not_reported_as_missing_credit(self):
        """
        پیام واقعی OpenRouter واژهٔ «credits» دارد.

        اگر «اعتبار تمام شد» گزارش شود کاربر فکر می‌کند باید پول بدهد،
        در حالی‌که سهمیه فردا خودش برمی‌گردد.
        """
        exc = self._raise_for(
            429,
            "Rate limit exceeded: free-models-per-day. Add 10 credits to unlock 1000 free model requests per day",
        )
        assert exc is not None
        assert getattr(exc, "details", {}).get("reason") == "daily_quota"
        assert "resets automatically" in str(exc)

    def test_real_credit_exhaustion_still_detected(self):
        """کمبود واقعی اعتبار نباید با سهمیهٔ روزانه قاطی شود."""
        exc = self._raise_for(402, "Insufficient credit balance for this request")
        assert getattr(exc, "details", {}).get("reason") == "insufficient_quota"


class TestDuplicateToolCalls:
    """فراخوانی تکراری ابزار، گام و سهمیهٔ روزانه را هدر می‌دهد."""

    def test_repeated_identical_call_is_blocked(self, qt_application):
        """
        مدل اگر مدام یک ابزار را با همان پارامترها صدا بزند، فقط بار اول
        واقعاً اجرا می‌شود و بقیه با تذکر برمی‌گردند.
        """
        import asyncio
        import json as _json

        from ai.agent.autonomous_agent import AgentOutcome, AutonomousAgent
        from ai.providers.base import AIMessage

        executions: list[str] = []

        class FakeTools:
            @staticmethod
            def get_definitions():
                return []

            @staticmethod
            async def execute(name, arguments):
                executions.append(name)
                return type("R", (), {"ok": True, "data": {"price": 1}, "error": ""})()

        class FakeProviders:
            @staticmethod
            async def generate(messages, **kwargs):
                last = messages[-1].content
                if "STOP analysing" in last:
                    content = _json.dumps(
                        {"thought": "d", "final": {"direction": "WAIT", "confidence": 20}}
                    )
                else:
                    content = _json.dumps(
                        {"thought": "again", "tool": "get_current_price",
                         "arguments": {"symbol": "BTC/USDT"}}
                    )
                return type("Resp", (), {"content": content, "provider": "p", "model": "m"})()

        agent = AutonomousAgent.__new__(AutonomousAgent)
        agent._tools = FakeTools()
        agent._providers = FakeProviders()
        agent._preferred = None
        agent._max_iterations = 6
        agent._risk = type("R", (), {"max_leverage": 5, "min_risk_reward": 1.5})()
        agent._emit = lambda step: None
        agent._finalise = lambda final, outcome: setattr(outcome, "decision", final)

        outcome = AgentOutcome(symbol="BTC/USDT")
        asyncio.run(agent._loop("BTC/USDT", "4h", outcome))

        # از نسخهٔ ۱.۹.۱۸ سه ابزار پایه پیش از حلقه و به‌صورت موازی
        # گرفته می‌شوند، پس شمار کل اجراها دیگر یک نیست. چیزی که این
        # آزمون تضمین می‌کند این است: ابزاری که مدل **تکراری** صدا
        # می‌زند فقط یک‌بار واقعاً اجرا شود.
        repeated = [name for name in executions if name == "get_current_price"]
        assert len(repeated) == 1, (
            f"duplicate tool ran {len(repeated)} times instead of once: {executions}"
        )
        blocked = [s for s in outcome.steps if "already called" in (s.observation or "")]
        assert blocked, "duplicate calls were not reported back to the model"


# ---------------------------------------------------------------------------
# ۶) دور سوم: موجودی فیوچرز، سوییچ صرافی، پنجرهٔ متن اولاما
# ---------------------------------------------------------------------------
class TestFuturesBalances:
    """موجودی فیوچرز جدا از اسپات است و باید دیده شود."""

    @staticmethod
    def _parse(payload):
        from market.providers.lbank.provider import LBankProvider

        return LBankProvider._parse_futures_balances(payload)

    def test_list_and_wrapped_shapes(self):
        """هر دو قالب پاسخ باید خوانده شود."""
        assert self._parse([{"asset": "usdt", "available": "120.5", "frozen": "30"}]) == {
            "USDT": pytest.approx(150.5)
        }
        assert self._parse({"data": [{"symbol": "USDT", "total": "200.75"}]}) == {
            "USDT": pytest.approx(200.75)
        }

    def test_malformed_is_safe(self):
        """ورودی خراب نباید استثنا بدهد."""
        for payload in ({}, None, "junk", [123], {"data": None}):
            assert self._parse(payload) == {}

    @pytest.mark.asyncio
    async def test_spot_and_futures_are_merged(self, temp_paths):
        """
        موجودی دو کیف پول با هم جمع و تفکیکش ذخیره می‌شود.

        کاربری که سرمایه‌اش در فیوچرز است، پیش‌تر کیف پول را خالی می‌دید.
        """
        from app.application import Application

        class Provider:
            async def get_account_balance(self):
                return {"USDT": 5.0, "TRX": 100.0}

            async def get_futures_balance(self):
                return {"USDT": 250.0}

            async def close(self):
                return None

        app = Application(paths=temp_paths)
        await app.start()
        try:
            user, _ = app.auth.register("futures_user", "StrongPass!234", email="f@e.com")
            account = app.exchange_accounts.add_account(
                user_id=user["id"], exchange="lbank", api_key="k", api_secret="s"
            )
            result = await app.exchange_accounts.sync_balances(
                account["id"], lambda *a, **k: Provider(), price_lookup=lambda a: 1.0
            )
            assert result["balances"]["USDT"] == pytest.approx(255.0)
            assert result["futures"] == {"USDT": pytest.approx(250.0)}
            stored = app.exchange_accounts.get_account(account["id"])
            split = stored["extra_config"]["balances_by_wallet"]
            assert split["spot"]["TRX"] == pytest.approx(100.0)
            assert split["futures"]["USDT"] == pytest.approx(250.0)
        finally:
            await app.stop()

    @pytest.mark.asyncio
    async def test_futures_failure_keeps_spot(self, temp_paths):
        """
        نبود دسترسی فیوچرز نباید موجودی اسپات را از بین ببرد.

        کلید بدون مجوز قرارداد یا مسدودی شبکه نباید کیف پول را خالی کند.
        """
        from app.application import Application

        class Provider:
            async def get_account_balance(self):
                return {"USDT": 7.5}

            async def get_futures_balance(self):
                raise RuntimeError("403 Forbidden")

            async def close(self):
                return None

        app = Application(paths=temp_paths)
        await app.start()
        try:
            user, _ = app.auth.register("spot_only", "StrongPass!234", email="s@e.com")
            account = app.exchange_accounts.add_account(
                user_id=user["id"], exchange="lbank", api_key="k", api_secret="s"
            )
            result = await app.exchange_accounts.sync_balances(
                account["id"], lambda *a, **k: Provider()
            )
            assert result["balances"] == {"USDT": pytest.approx(7.5)}
        finally:
            await app.stop()


class TestWalletAccountSwitching:
    """کاربر با چند حساب باید بتواند صرافی کیف پول را عوض کند."""

    def test_set_default_moves_the_active_flag(self, database):
        """
        فقط یک حساب می‌تواند فعال باشد.

        بدون این، کیف پول نمی‌داند از کدام حساب بخواند.
        """
        from app.database.repositories.user_repository import (
            ExchangeAccountRepository,
            UserRepository,
        )

        users = UserRepository(database)
        accounts = ExchangeAccountRepository(database)
        user = users.create_user(username="multi", password="StrongPass!234")

        first = accounts.create_account(
            user_id=user["id"], exchange="lbank", secret_ref="r1", api_key_plain="aaaabbbbcccc"
        )
        second = accounts.create_account(
            user_id=user["id"], exchange="binance", secret_ref="r2", api_key_plain="ddddeeeeffff"
        )

        # اولین حساب خودبه‌خود پیش‌فرض می‌شود
        assert accounts.get_default_account(user["id"])["id"] == first["id"]

        assert accounts.set_default(user["id"], second["id"]) is True
        flags = {a["id"]: a["is_default"] for a in accounts.list_accounts(user["id"])}
        assert flags[second["id"]] is True
        assert flags[first["id"]] is False
        assert accounts.get_default_account(user["id"])["id"] == second["id"]


class TestOllamaContextWindow:
    """
    پنجرهٔ متن باید هم به پرامپت برسد و هم از توان دستگاه رد نشود.

    تاریخچهٔ این آزمون درس مهمی دارد. نسخهٔ اول پنجرهٔ ثابت و بزرگ
    می‌خواست؛ نسخهٔ دوم آن را به طول پرامپت گره زد و همین‌جا ادعا شد
    «پرامپت بلند باید همیشه جا شود». هر دو اشتباه بودند و کاربر باز
    هم خطای ۵۰۰ گرفت.

    علت: «جا شدن پرامپت» تنها قید مسئله نیست. قید سخت‌تر، حافظهٔ
    دستگاه است. روی ماشین ۱۶ گیگابایتی، `deepseek-r1:8b` با پنجرهٔ
    ۱۶۳۸۴ اصلاً بارگذاری نمی‌شود؛ اجراکنندهٔ اولاما می‌میرد و «۵۰۰ با
    بدنهٔ خالی» برمی‌گرداند. پس پنجره **نباید** برای رسیدن به پرامپت
    بی‌نهایت بزرگ شود — به‌جایش پرامپت باید کوچک شود.
    """

    @staticmethod
    def _provider(max_tokens: int, ceiling: int):
        """ارائه‌دهنده با سقف حافظهٔ مشخص، بدون نیاز به اولامای واقعی."""
        from ai.providers.base import AIProviderConfig
        from ai.providers.ollama_provider import OllamaProvider

        provider = OllamaProvider(
            AIProviderConfig(name="ollama", model="deepseek-r1:8b", max_tokens=max_tokens)
        )
        provider._context_ceiling = ceiling
        return provider

    @pytest.mark.parametrize("max_tokens", [800, 1600, 3000])
    def test_window_grows_for_a_long_prompt_when_memory_allows(self, max_tokens):
        """
        روی دستگاه بزرگ، پنجره باید تا اندازهٔ پرامپت رشد کند.

        این نیمهٔ درست ادعای قبلی است و حفظ می‌شود.
        """
        from ai.providers.base import AIMessage

        provider = self._provider(max_tokens, ceiling=32768)
        long_prompt = [AIMessage(role="user", content="x" * 6000)]

        assert provider._num_ctx(long_prompt) >= 2000 + max_tokens

    def test_window_never_exceeds_what_the_machine_can_load(self):
        """
        قید سخت: سقف حافظه هرگز شکسته نمی‌شود.

        این همان چیزی است که در نسخه‌های پیشین نبود و باعث شد مدلی که
        در ترمینال کار می‌کرد، از راه برنامه شکست بخورد.
        """
        from ai.providers.base import AIMessage

        provider = self._provider(3000, ceiling=8192)
        # پرامپتی که برای جا شدن، پنجرهٔ ۱۶۳۸۴ لازم دارد
        huge = [AIMessage(role="user", content="x" * 30000)]

        assert provider._num_ctx(huge) == 8192

    def test_short_chat_prompt_does_not_ask_for_a_big_window(self):
        """
        یک پرسش کوتاه نباید پنجرهٔ بزرگ بخواهد.

        ادعای اصلی همان است، ولی عدد دقیق دیگر مطالبه نمی‌شود: کوچک‌تر
        از ۴۰۹۶ هم کاملاً درست است و حتی کم‌مصرف‌تر. چیزی که اهمیت
        دارد این است که پرسش ساده، پنجرهٔ بزرگ نگیرد.
        """
        from ai.providers.base import AIMessage

        provider = self._provider(1600, ceiling=8192)
        window = provider._num_ctx([AIMessage(role="user", content="قیمت الان چند است؟")])

        assert window <= 4096

    def test_prompt_budget_leaves_room_for_the_answer(self):
        """
        بودجهٔ پرامپت باید کمتر از کل پنجره باشد.

        پرکردن کل پنجره با پرامپت یعنی مدل جایی برای پاسخ ندارد —
        به‌ویژه مدل‌های استدلالی که پیش از پاسخ، بلوک فکر می‌سازند.
        """
        provider = self._provider(1600, ceiling=8192)

        budget = provider.prompt_token_budget()

        assert 0 < budget < 8192


class TestWaitReasonFallback:
    """WAIT بدون دلیل نباید به «اطمینان ۰٪ بدون توضیح» تبدیل شود."""

    def test_thought_is_used_when_reason_missing(self):
        """اندیشهٔ مدل به‌عنوان دلیل جایگزین به کار می‌رود."""
        from ai.agent.autonomous_agent import AgentOutcome, AgentStep, AutonomousAgent
        from ai.agent.validator import ResponseValidator

        agent = AutonomousAgent.__new__(AutonomousAgent)
        agent._validator = ResponseValidator()
        agent._risk = type("R", (), {"max_leverage": 5, "min_risk_reward": 1.5})()

        outcome = AgentOutcome(symbol="BTC/USDT")
        outcome.steps.append(
            AgentStep(index=1, thought="Both timeframes bearish but momentum fading", ok=True)
        )
        agent._finalise({"direction": "WAIT", "confidence": 25}, outcome)

        assert outcome.succeeded is True
        assert "momentum" in outcome.decision["reason"]


# ---------------------------------------------------------------------------
# ۷) شفافیت دسترسی فیوچرز و تفکیک موجودی در خلاصه
# ---------------------------------------------------------------------------
class TestFuturesAccessVisibility:
    """کلید بدون مجوز قرارداد نباید بی‌سروصدا «سالم» گزارش شود."""

    @pytest.mark.asyncio
    async def test_missing_futures_access_is_reported(self, temp_paths):
        """
        اتصال موفق ولی بدون دسترسی قرارداد باید در پیام دیده شود.

        وگرنه کاربر «اتصال برقرار» می‌بیند و بعد کیف پول فیوچرز خالی
        می‌ماند — همان تلهٔ `test_credentials` که قبلاً کیف پول را
        شکسته بود.
        """
        from app.application import Application

        class Provider:
            async def test_credentials(self):
                return True, "Credentials verified successfully"

            async def fetch_futures_balance(self):
                raise RuntimeError("403 Forbidden")

            async def close(self):
                return None

        app = Application(paths=temp_paths)
        await app.start()
        try:
            user, _ = app.auth.register("noperm", "StrongPass!234", email="np@e.com")
            account = app.exchange_accounts.add_account(
                user_id=user["id"], exchange="lbank", api_key="k", api_secret="s"
            )
            ok, message = await app.exchange_accounts.test_connection(
                account["id"], lambda *a, **k: Provider()
            )
            assert ok is True
            assert "futures access unavailable" in message
        finally:
            await app.stop()

    @pytest.mark.asyncio
    async def test_full_access_has_no_warning(self, temp_paths):
        """کلید کامل نباید هشدار بی‌مورد بگیرد."""
        from app.application import Application

        class Provider:
            async def test_credentials(self):
                return True, "Credentials verified successfully"

            async def fetch_futures_balance(self):
                return {"USDT": 99.0}

            async def close(self):
                return None

        app = Application(paths=temp_paths)
        await app.start()
        try:
            user, _ = app.auth.register("okperm", "StrongPass!234", email="op@e.com")
            account = app.exchange_accounts.add_account(
                user_id=user["id"], exchange="lbank", api_key="k", api_secret="s"
            )
            ok, message = await app.exchange_accounts.test_connection(
                account["id"], lambda *a, **k: Provider()
            )
            assert ok is True
            assert "unavailable" not in message
        finally:
            await app.stop()

    def test_sync_uses_the_guarded_variant(self):
        """
        همگام‌سازی باید نسخهٔ مهارشده را صدا بزند.

        اگر مسیر همگام‌سازی به نسخهٔ بدون‌مهار وصل شود، یک کلید بدون
        مجوز قرارداد کل کیف پول را از کار می‌اندازد.
        """
        import inspect

        from app.core import exchange_account_service as service

        source = inspect.getsource(service.ExchangeAccountService.sync_balances)
        assert '"get_futures_balance"' in source
        assert "fetch_futures_balance" not in source
