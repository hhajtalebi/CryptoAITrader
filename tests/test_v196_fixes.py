"""
آزمون‌های نسخهٔ ۱.۹.۶ — سه گزارش کاربر از ماشین خودش.

۱. کرش `OverflowError` در تیک سیگنال‌گیری خودکار.
۲. چت با «همهٔ ارائه‌دهنده‌ها شکست خوردند» برمی‌گشت، در حالی که خطای
   اولاما این بار «wsarecv: forcibly closed» بود — یعنی مرگ زیرفرایند
   مدل، نه سرریز پنجره.
۳. پوستهٔ پیش‌فرض باید همیشه «سرمه‌ای اداری» باشد.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


# ---------------------------------------------------------------------------
# ۱) کرش شمارش معکوس سیگنال‌گیری خودکار
# ---------------------------------------------------------------------------


class TestAutoScanCountdown:
    """
    `seconds_until_next()` هرگز نباید استثنا بدهد.

    از داخل تایمر رابط کاربری صدا زده می‌شود؛ استثنا در آنجا یعنی هر
    تیک دوباره می‌ترکد و کاربر سیلی از خطا می‌بیند — دقیقاً چیزی که
    در ترمینال گزارش شد.
    """

    @staticmethod
    def _scheduler(**overrides):
        """زمان‌بند با پیکربندی دلخواه."""
        from signals.auto_scanner import AutoScanConfig, AutoScanScheduler

        return AutoScanScheduler(AutoScanConfig(enabled=True, **overrides))

    def test_a_fresh_scheduler_does_not_crash(self) -> None:
        """
        بازتولید دقیق گزارش کاربر.

        تازه روشن شده، هنوز هیچ چرخشی اجرا نشده: زمان سپری‌شده
        بی‌نهایت است، باقی‌مانده منفیِ بی‌نهایت می‌شود و `int()` روی
        آن `OverflowError` می‌داد.
        """
        assert self._scheduler().seconds_until_next() == 0

    def test_never_run_means_due_now(self) -> None:
        """
        صفر یعنی «همین حالا موعدش است» که معنای درست «هرگز اجرا نشده»
        است. هر عدد دیگری، شروع سامانه را عقب می‌انداخت.
        """
        scheduler = self._scheduler(full_sweep_enabled=False)
        scheduler.focus_symbols = ["BTC/USDT"]

        assert scheduler.seconds_until_next() == 0

    def test_a_normal_countdown_still_works(self) -> None:
        """رفع نباید شمارش معکوس واقعی را خراب کند."""
        scheduler = self._scheduler(full_interval=1800)
        scheduler.last_full_at = datetime.now(timezone.utc) - timedelta(seconds=600)

        remaining = scheduler.seconds_until_next()

        assert 1195 <= remaining <= 1200

    def test_an_overdue_sweep_reports_zero(self) -> None:
        """عدد منفی در شمارش معکوس بی‌معناست."""
        scheduler = self._scheduler(full_interval=60)
        scheduler.last_full_at = datetime.now(timezone.utc) - timedelta(seconds=600)

        assert scheduler.seconds_until_next() == 0

    def test_a_disabled_scheduler_reports_zero(self) -> None:
        """خاموش یعنی نوبتی در کار نیست."""
        from signals.auto_scanner import AutoScanConfig, AutoScanScheduler

        scheduler = AutoScanScheduler(AutoScanConfig(enabled=False))

        assert scheduler.seconds_until_next() == 0

    @pytest.mark.parametrize("full_sweep", [True, False])
    @pytest.mark.parametrize("has_focus", [True, False])
    def test_every_combination_returns_a_usable_integer(
        self, full_sweep: bool, has_focus: bool
    ) -> None:
        """
        پوشش کامل چهار حالت.

        کرش در حالتی رخ داد که هیچ‌کس جداگانه آزمونش نکرده بود؛ پس
        این بار همهٔ ترکیب‌ها بررسی می‌شوند.
        """
        scheduler = self._scheduler(full_sweep_enabled=full_sweep)
        if has_focus:
            scheduler.focus_symbols = ["BTC/USDT"]

        result = scheduler.seconds_until_next()

        assert isinstance(result, int)
        assert result >= 0


# ---------------------------------------------------------------------------
# ۲) مرگ زیرفرایند مدل محلی
# ---------------------------------------------------------------------------


class FakeResponse:
    """پاسخ ساختگی اولاما."""

    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = str(self._payload)

    def json(self) -> dict:
        """بدنهٔ پاسخ."""
        return self._payload


#: پیام واقعی که کاربر روی ویندوز دید.
WINDOWS_CRASH = (
    "an error was encountered while running the model: read tcp "
    "127.0.0.1:54234->127.0.0.1:52697: wsarecv: An existing connection "
    "was forcibly closed by the remote host."
)


class TestRunnerCrashDetection:
    """
    مرگ اجراکننده با سرریز پنجره فرق دارد و درمانش هم فرق دارد.

    سرریز پنجره با کوچک‌کردن پنجره حل می‌شود؛ مرگ اجراکننده با تلاش
    مجدد و بارگذاری دوبارهٔ مدل. تشخیص ندادن این تفاوت باعث شد چت
    بدون هیچ تلاش مجددی شکست بخورد.
    """

    def test_the_windows_message_is_recognised(self) -> None:
        """پیام دقیقی که کاربر گزارش کرد."""
        from ai.providers.ollama_provider import _is_runner_crash

        assert _is_runner_crash(FakeResponse(500, {"error": WINDOWS_CRASH}))

    @pytest.mark.parametrize(
        "message",
        [
            "connection reset by peer",
            "broken pipe",
            "unexpected EOF",
            "llama runner process has terminated: exit status 2",
            "an error was encountered while running the model",
        ],
    )
    def test_other_platforms_and_phrasings(self, message: str) -> None:
        """لینوکس و مک عبارت دیگری می‌نویسند؛ همه یک معنا دارند."""
        from ai.providers.ollama_provider import _is_runner_crash

        assert _is_runner_crash(FakeResponse(500, {"error": message}))

    def test_a_memory_error_is_not_a_runner_crash(self) -> None:
        """
        این دو نباید قاطی شوند.

        کمبود حافظه پیام خودش را دارد و تلاش مجدد حلش نمی‌کند — باید
        به کاربر گفته شود مدل کوچک‌تری بردارد.
        """
        from ai.providers.ollama_provider import _is_runner_crash

        assert not _is_runner_crash(
            FakeResponse(500, {"error": "model requires more system memory than is available"})
        )

    def test_an_empty_body_is_not_a_runner_crash(self) -> None:
        """
        «۵۰۰ با بدنهٔ خالی» نشانهٔ سرریز پنجره است، نه مرگ اجراکننده.

        اشتباه گرفتنشان یعنی به‌جای کوچک‌کردن پنجره، بیهوده تلاش مجدد
        کنیم.
        """
        from ai.providers.ollama_provider import _is_runner_crash

        assert not _is_runner_crash(FakeResponse(500, {}))


class TestRunnerCrashRecovery:
    """پس از تشخیص، برنامه باید خودش را نجات دهد."""

    @staticmethod
    def _provider(base_url: str = "http://127.0.0.1:11434"):
        """ارائه‌دهندهٔ اولاما با پیکربندی آزمونی."""
        from ai.providers.base import AIProviderConfig
        from ai.providers.ollama_provider import OllamaProvider

        return OllamaProvider(
            AIProviderConfig(
                name="ollama",
                base_url=base_url,
                model="deepseek-r1:8b",
                max_tokens=1500,
                extra={"provider_type": "ollama"},
            )
        )

    @pytest.mark.asyncio
    async def test_a_transient_crash_is_retried_and_succeeds(self, monkeypatch) -> None:
        """
        سناریوی کاربر: چت با پنجرهٔ ۲۰۴۸ که اصلاً وارد نردبان
        کوچک‌کردن نمی‌شد و بی‌درنگ شکست می‌خورد.
        """
        from ai.providers.base import AIMessage
        from ai.providers.ollama_provider import OllamaProvider

        calls: list[dict] = []

        class FakeClient:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                calls.append(json)
                if len(calls) == 1:
                    return FakeResponse(500, {"error": WINDOWS_CRASH})
                return FakeResponse(
                    200, {"model": "deepseek-r1:8b", "message": {"content": "سلام"}, "done": True}
                )

        provider = self._provider()
        monkeypatch.setattr(provider, "_get_client", lambda: _async(FakeClient()))
        monkeypatch.setattr(provider, "resolve_model", lambda: _async("deepseek-r1:8b"))
        monkeypatch.setattr("ai.providers.ollama_provider.RUNNER_CRASH_BACKOFF", 0.0)

        response = await provider.generate([AIMessage("user", "سلام")])

        assert response.content == "سلام"
        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_retries_are_bounded(self, monkeypatch) -> None:
        """
        خرابی پایدار نباید به حلقهٔ بی‌پایان تبدیل شود.

        کاربر پشت صفحه منتظر است؛ تلاش بی‌نهایت بدتر از خطای صریح است.
        """
        from ai.providers.base import AIMessage
        from ai.providers.ollama_provider import RUNNER_CRASH_RETRIES
        from app.exceptions import AIProviderError

        calls: list[dict] = []

        class AlwaysDead:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                calls.append(json)
                return FakeResponse(500, {"error": WINDOWS_CRASH})

        provider = self._provider()
        monkeypatch.setattr(provider, "_get_client", lambda: _async(AlwaysDead()))
        monkeypatch.setattr(provider, "resolve_model", lambda: _async("deepseek-r1:8b"))
        monkeypatch.setattr("ai.providers.ollama_provider.RUNNER_CRASH_BACKOFF", 0.0)

        with pytest.raises(AIProviderError):
            await provider.generate([AIMessage("user", "سلام")])

        # تلاش اول + تلاش‌های مجدد
        assert len(calls) == RUNNER_CRASH_RETRIES + 1

    @pytest.mark.asyncio
    async def test_each_retry_asks_for_a_shorter_reply(self, monkeypatch) -> None:
        """
        پاسخ کوتاه‌تر یعنی بافر تولید کوچک‌تر و حافظهٔ کمتر.

        تکرار عین همان درخواستی که مدل را کشت، بعید است نتیجهٔ
        متفاوتی بدهد.
        """
        from ai.providers.base import AIMessage
        from app.exceptions import AIProviderError

        budgets: list[int] = []

        class AlwaysDead:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                # روی پرامپت کوتاه، `num_predict` اصلاً فرستاده نمی‌شود
                # (همان رفتار ترمینال). در آن حالت سقف پیکربندی ملاک است.
                budgets.append(json["options"].get("num_predict", 1600))
                return FakeResponse(500, {"error": WINDOWS_CRASH})

        provider = self._provider()
        monkeypatch.setattr(provider, "_get_client", lambda: _async(AlwaysDead()))
        monkeypatch.setattr(provider, "resolve_model", lambda: _async("deepseek-r1:8b"))
        monkeypatch.setattr("ai.providers.ollama_provider.RUNNER_CRASH_BACKOFF", 0.0)

        with pytest.raises(AIProviderError):
            await provider.generate([AIMessage("user", "سلام")])

        assert budgets == sorted(budgets, reverse=True)
        assert budgets[-1] < budgets[0]

    @pytest.mark.asyncio
    async def test_the_error_message_is_actionable(self, monkeypatch) -> None:
        """
        «wsarecv» برای کاربر بی‌معناست و شبیه مشکل شبکه به نظر می‌رسد،
        در حالی که ربطی به شبکه ندارد. پیام باید بگوید چه شد و چه کار
        می‌شود کرد.
        """
        from ai.providers.base import AIMessage
        from app.exceptions import AIProviderError

        class AlwaysDead:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                return FakeResponse(500, {"error": WINDOWS_CRASH})

        provider = self._provider()
        monkeypatch.setattr(provider, "_get_client", lambda: _async(AlwaysDead()))
        monkeypatch.setattr(provider, "resolve_model", lambda: _async("deepseek-r1:8b"))
        monkeypatch.setattr("ai.providers.ollama_provider.RUNNER_CRASH_BACKOFF", 0.0)

        with pytest.raises(AIProviderError) as raised:
            await provider.generate([AIMessage("user", "سلام")])

        message = str(raised.value).lower()
        assert "stopped unexpectedly" in message
        # پیام نباید اندازهٔ مدل را مقصر اعلام کند: مدلی که در ترمینال
        # کار می‌کند «بزرگ» نیست، و این حدس کاربر را ساعت‌ها دنبال نخ
        # اشتباه فرستاد.
        assert "too large" not in message
        assert "ollama run" in message


async def _async(value):  # noqa: ANN001, ANN202
    """کمک‌کننده: مقدار را در یک کوروتین می‌پیچد."""
    return value


# ---------------------------------------------------------------------------
# ۳) پوستهٔ پیش‌فرض
# ---------------------------------------------------------------------------


class TestDefaultTheme:
    """کاربر خواست «سرمه‌ای اداری» همیشه پیش‌فرض باشد."""

    def test_the_catalog_default_is_corporate_navy(self) -> None:
        """پایه‌ای‌ترین بررسی."""
        from ui.themes.catalog import DEFAULT_THEME

        assert DEFAULT_THEME == "corporate_navy"

    def test_the_default_theme_exists(self) -> None:
        """
        پیش‌فرضی که در کاتالوگ نباشد، برنامه را در اولین اجرا
        می‌شکند.
        """
        from ui.themes.catalog import DEFAULT_THEME, THEME_CATALOG

        assert DEFAULT_THEME in THEME_CATALOG

    def test_both_settings_keys_agree(self) -> None:
        """
        دو کلید پوسته وجود دارد و ناهماهنگی‌شان یعنی برنامه با یک
        پوسته بالا بیاید و با پوستهٔ دیگری رنگ شود.
        """
        from app.config.defaults import DEFAULT_SETTINGS, SettingKey

        assert DEFAULT_SETTINGS[SettingKey.THEME.value] == "corporate_navy"
        assert DEFAULT_SETTINGS[SettingKey.UI_THEME.value] == "corporate_navy"

    def test_the_theme_is_named_in_both_languages(self) -> None:
        """قاعدهٔ پروژه: کاربر پوسته را با نام انتخاب می‌کند."""
        from localization import Translator

        for language in ("fa", "en"):
            assert Translator(language).tr("settings.themes.corporate_navy") != (
                "settings.themes.corporate_navy"
            )

    def test_every_theme_still_loads(self) -> None:
        """
        عوض‌کردن پیش‌فرض نباید هیچ پوستهٔ دیگری را از دسترس خارج کند.

        قاعدهٔ پروژه: پوسته نباید امکانات را محدود کند.
        """
        from ui.themes.catalog import THEME_CATALOG

        assert len(THEME_CATALOG) >= 9
        for key, tokens in THEME_CATALOG.items():
            assert tokens.colors is not None, key


# ---------------------------------------------------------------------------
# ۴) سنجش تناسب مدل محلی با حافظهٔ دستگاه
# ---------------------------------------------------------------------------


class TestLocalModelFit:
    """
    درمان ریشه‌ای مرگ مدل: کاربر پیش از انتخاب بداند چه چیزی جا می‌شود.

    تلاش مجدد، نشانه را درمان می‌کند؛ این بخش علت را.
    """

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("deepseek-r1:8b", 8.0),
            ("qwen2.5-7b-instruct", 7.0),
            ("phi3.5:3.8b", 3.8),
            ("llama3.1:70b", 70.0),
            ("mistral:latest", 0.0),
            ("", 0.0),
        ],
    )
    def test_size_is_read_from_the_name(self, name: str, expected: float) -> None:
        """صفر یعنی «نشد بخوانم» — که با «مدل کوچک است» فرق دارد."""
        from ai.local_model_fit import parse_model_size

        assert parse_model_size(name) == expected

    def test_the_users_installed_models_are_not_falsely_flagged(self) -> None:
        """
        **تصحیح فرضیهٔ غلط.**

        نسخهٔ ۱.۹.۶ ادعا می‌کرد `deepseek-r1:8b` روی ۱۶ گیگابایت جا
        نمی‌شود. کاربر تصویر `ollama list` را فرستاد: همان مدل روی
        دیسک ۵٫۲ گیگابایت است و در ترمینال بی‌نقص کار می‌کند.

        هشداری که روی مدل سالم روشن شود، کاربر را عادت می‌دهد همهٔ
        هشدارها را نادیده بگیرد — بدتر از نبودنش.
        """
        from ai.local_model_fit import FITS, evaluate_fit

        for model in (
            "gemma4:e4b-it-qat",
            "deepseek-r1:8b",
            "deepseek-coder:6.7b",
            "llama3.1:8b",
        ):
            assert evaluate_fit(model, 16).status == FITS, model

    def test_genuinely_oversized_models_are_still_flagged(self) -> None:
        """
        کالیبراسیون واقع‌بینانه نباید هشدار را بی‌اثر کند.

        مدل ۷۰ میلیاردی روی ۱۶ گیگابایت واقعاً اجرا نمی‌شود.
        """
        from ai.local_model_fit import TOO_BIG, evaluate_fit

        assert evaluate_fit("llama3.1:70b", 16).status == TOO_BIG
        assert evaluate_fit("qwq:32b", 16).status == TOO_BIG

    def test_reasoning_models_need_more_room(self) -> None:
        """
        بلوک `<think>` کش KV را بزرگ‌تر می‌کند، پس تخمین باید بالاتر
        باشد — ولی ملایم، نه آن‌قدر که مدل سالم را قرمز کند.
        """
        from ai.local_model_fit import evaluate_fit

        reasoning = evaluate_fit("deepseek-r1:8b", 16)
        plain = evaluate_fit("llama3.1:8b", 16)

        assert reasoning.required_gb > plain.required_gb

    @pytest.mark.parametrize(
        "name", ["deepseek-r1:8b", "qwq:32b", "marco-o1:7b", "some-thinking-model:7b"]
    )
    def test_reasoning_models_are_recognised(self, name: str) -> None:
        """تشخیص باید خانواده‌های مختلف را پوشش دهد."""
        from ai.local_model_fit import is_reasoning_model

        assert is_reasoning_model(name)

    def test_a_small_model_fits_comfortably(self) -> None:
        """هشدار روی مدل سبک، هشدار را بی‌ارزش می‌کند."""
        from ai.local_model_fit import FITS, evaluate_fit

        assert evaluate_fit("llama3.2:3b", 16).status == FITS

    def test_an_unparseable_name_makes_no_claim(self) -> None:
        """
        وقتی اندازه معلوم نیست، سکوت بهتر از حدس است.

        همان قاعده‌ای که در توصیهٔ خرید/فروش هم رعایت شد.
        """
        from ai.local_model_fit import UNKNOWN, evaluate_fit

        assert evaluate_fit("mistral:latest", 16).status == UNKNOWN
        assert evaluate_fit("llama3.2:3b", None).status == UNKNOWN

    def test_suggestions_fit_the_machine(self) -> None:
        """پیشنهاد دادن مدلی که باز هم نمی‌کشد، بدتر از پیشنهاد ندادن است."""
        from ai.local_model_fit import FITS, evaluate_fit, suggest_models

        for memory in (8, 16, 32):
            for name in suggest_models(memory):
                assert evaluate_fit(name, memory).status == FITS, f"{name} @ {memory}GB"

    def test_suggestions_prefer_the_largest_that_fits(self) -> None:
        """بزرگ‌ترین مدلی که جا می‌شود، معمولاً بهترین کیفیت را می‌دهد."""
        from ai.local_model_fit import parse_model_size, suggest_models

        sizes = [parse_model_size(name) for name in suggest_models(32)]

        assert sizes == sorted(sizes, reverse=True)

    def test_no_reasoning_model_is_ever_suggested(self) -> None:
        """
        آن‌ها دقیقاً همان مشکلی را می‌سازند که کاربر داشت.

        پیشنهادشان یعنی کاربر را به همان چاه دوباره بفرستیم.
        """
        from ai.local_model_fit import is_reasoning_model, suggest_models

        for memory in (8, 16, 32, 64):
            for name in suggest_models(memory):
                assert not is_reasoning_model(name), name

    def test_a_tiny_machine_gets_no_false_hope(self) -> None:
        """روی دستگاهی که هیچ مدلی جا نمی‌شود، فهرست خالی صادقانه است."""
        from ai.local_model_fit import suggest_models

        assert suggest_models(4) == []

    def test_translations_exist_in_both_languages(self) -> None:
        """قاعدهٔ پروژه: هیچ رشتهٔ سخت‌کدشده‌ای در رابط کاربری نیست."""
        from localization import Translator

        for language in ("fa", "en"):
            translator = Translator(language)
            for status in ("fits", "tight", "too_big", "unknown"):
                key = f"settings.model_fit.{status}"
                assert translator.tr(key) != key, f"{language}: {key}"

    def test_the_warning_names_a_way_out(self) -> None:
        """
        هشداری که نگوید چه کار کنم، فقط نگرانی می‌سازد.

        پیام باید هم مدل پیشنهادی بدهد و هم عددها را.
        """
        from localization import Translator

        message = Translator("fa").tr(
            "settings.model_fit.too_big",
            model="deepseek-r1:8b",
            required=12.0,
            available=11.0,
            suggestions="qwen2.5:7b",
        )

        assert "qwen2.5:7b" in message
        assert "12.0" in message


# ---------------------------------------------------------------------------
# ۵) چرا در ترمینال کار می‌کرد و در برنامه نه
# ---------------------------------------------------------------------------


class TestRequestShapeMatchesTheTerminal:
    """
    ریشهٔ واقعی «در ترمینال اوکی است، در نرم‌افزار نه».

    کاربر تصویر فرستاد: چهار مدل نصب‌شده، `ollama run llama3.1:8b`
    بی‌نقص جواب می‌دهد. پس نه مدل خراب بود، نه حافظه کم — فرضیهٔ
    حافظهٔ نسخهٔ ۱.۹.۶ اشتباه بود.

    تفاوت واقعی در شکل درخواست بود. `ollama run` هیچ `num_ctx` و هیچ
    `num_predict` نمی‌فرستد؛ اولاما مدل را یک بار با پنجرهٔ پیش‌فرض
    بارگذاری می‌کند و در حافظه نگه می‌دارد. برنامه اما برای هر درخواست
    مقدار متفاوتی می‌فرستاد — ۲۰۴۸ برای یک پیام کوتاه چت، ۸۱۹۲ برای
    تحلیل. هر تغییر `num_ctx` یعنی تخلیه و بارگذاری دوبارهٔ چند
    گیگابایت، و همان‌جاست که اجراکننده می‌میرد.
    """

    @staticmethod
    def _provider(max_tokens: int = 1600):
        """ارائه‌دهنده با پیکربندی واقعی برنامه."""
        from ai.providers.base import AIProviderConfig
        from ai.providers.ollama_provider import OllamaProvider

        return OllamaProvider(
            AIProviderConfig(
                name="ollama",
                base_url="http://127.0.0.1:11434",
                model="llama3.1:8b",
                max_tokens=max_tokens,
                extra={"provider_type": "ollama"},
            )
        )

    @staticmethod
    async def _capture(provider, messages):  # noqa: ANN001, ANN205
        """یک درخواست می‌فرستد و بدنه‌اش را برمی‌گرداند."""
        sent: dict = {}

        class Recorder:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                sent.update(json)
                return FakeResponse(
                    200, {"model": "llama3.1:8b", "message": {"content": "ok"}, "done": True}
                )

        provider._get_client = lambda: _async(Recorder())  # noqa: SLF001
        provider.resolve_model = lambda: _async("llama3.1:8b")  # noqa: SLF001
        await provider.generate(messages)
        return sent

    @pytest.mark.asyncio
    async def test_a_short_chat_never_asks_for_a_different_window(self) -> None:
        """
        پیام «hi» نباید پنجره‌ای متفاوت از بقیهٔ درخواست‌ها بخواهد.

        در ۱٫۹٫۷ اینجا ادعا شده بود که باید **هیچ** `num_ctx` فرستاده
        نشود. آن استدلال ناقص بود: «نفرستادن» یعنی پنجرهٔ پیش‌فرض ۴۰۹۶،
        که خودش یک مقدار است. اگر درخواست بعدی ۸۱۹۲ بخواهد، همان گذارِ
        کشنده رخ می‌دهد. چیزی که واقعاً اهمیت دارد یکسان‌بودن است، نه
        خالی‌بودن.
        """
        from ai.providers.base import AIMessage

        provider = self._provider()
        short = await self._capture(provider, [AIMessage("user", "hi")])
        long = await self._capture(provider, [AIMessage("user", "x" * 40_000)])

        assert short["options"].get("num_ctx") == long["options"].get("num_ctx")

    @pytest.mark.asyncio
    async def test_a_short_chat_still_sends_temperature(self) -> None:
        """حذف بیش از حد هم اشتباه است؛ دما همچنان کنترل کاربر است."""
        from ai.providers.base import AIMessage

        sent = await self._capture(self._provider(), [AIMessage("user", "hi")])

        assert "temperature" in sent["options"]

    @pytest.mark.asyncio
    async def test_the_model_is_kept_in_memory(self) -> None:
        """
        بدون `keep_alive`، اولاما مدل را پس از ۵ دقیقه تخلیه می‌کند.

        کاربری که بین دو پرسش فکر می‌کند، هر بار منتظر بارگذاری دوبارهٔ
        چند گیگابایت می‌ماند — و آن لحظه دقیقاً پرخطرترین لحظه برای
        مرگ اجراکننده است.
        """
        from ai.providers.base import AIMessage

        sent = await self._capture(self._provider(), [AIMessage("user", "hi")])

        assert sent.get("keep_alive")

    @pytest.mark.asyncio
    async def test_a_large_prompt_is_trimmed_instead_of_widening_the_window(self) -> None:
        """
        پرامپت بزرگ نباید پنجره را بازتعریف کند؛ باید کوتاه شود.

        این آزمون در ۱٫۹٫۸ برعکس بود و `num_ctx` را لازم می‌دانست. لاگ
        خود اولاما نشان داد پنجرهٔ پیش‌فرض از روی **VRAM** انتخاب
        می‌شود (کارت ۲ گیگابایتی کاربر ⇒ ۴۰۹۶) و ما که فقط رم سیستم را
        می‌بینیم، حق نداریم عدد بزرگ‌تری تحمیل کنیم.

        پس راه درست: پنجره دست اولاما، و پرامپت را خودمان جا می‌دهیم.
        """
        from ai.providers.base import AIMessage

        sent = await self._capture(self._provider(), [AIMessage("user", "x" * 40_000)])

        assert "num_ctx" not in sent["options"]
        # و پرامپت واقعاً کوتاه شده باشد، وگرنه اولاما بی‌صدا می‌بُرَدش.
        assert len(sent["messages"][0]["content"]) < 40_000

    @pytest.mark.asyncio
    async def test_the_reply_budget_never_eats_the_window(self) -> None:
        """
        نقص دومی که همین‌جا پیدا شد.

        برنامه `ai.max_tokens` را مستقیم می‌فرستاد: روی پنجرهٔ ۲۰۴۸،
        درخواست ۱۶۰۰ توکن پاسخ یعنی ۷۸٪ پنجره فقط بافر تولید. حالا
        سقف پاسخ هرگز از فضای باقی‌مانده بیشتر نمی‌شود.
        """
        from ai.providers.base import AIMessage

        from ai.providers.ollama_provider import DEFAULT_MODEL_CONTEXT

        sent = await self._capture(self._provider(), [AIMessage("user", "x" * 40_000)])

        # پنجره فرستاده نمی‌شود، پس بودجهٔ پاسخ باید نسبت به پنجرهٔ
        # مؤثر (پیش‌فرض اولاما) سنجیده شود.
        assert sent["options"]["num_predict"] < DEFAULT_MODEL_CONTEXT

    @pytest.mark.asyncio
    async def test_the_reply_budget_stays_useful(self) -> None:
        """
        محدودکردن نباید به پاسخ‌های بی‌فایده منجر شود.

        پاسخ ۵۰ توکنی یعنی تحلیل نیمه‌کاره؛ کف نگه داشته می‌شود.
        """
        from ai.providers.base import AIMessage
        from ai.providers.ollama_provider import MIN_NUM_PREDICT

        sent = await self._capture(self._provider(), [AIMessage("user", "x" * 40_000)])

        assert sent["options"]["num_predict"] >= MIN_NUM_PREDICT

    def test_the_threshold_matches_ollamas_own_default(self) -> None:
        """
        آستانه باید با پنجرهٔ پیش‌فرض واقعی اولاما بخواند.

        اگر بزرگ‌تر بگیریم، پرامپت بی‌صدا بریده می‌شود؛ اگر کوچک‌تر،
        بی‌دلیل مدل را دوباره بارگذاری می‌کنیم.
        """
        from ai.providers.ollama_provider import DEFAULT_MODEL_CONTEXT

        assert DEFAULT_MODEL_CONTEXT == 4096

    @pytest.mark.asyncio
    async def test_the_users_four_models_all_take_the_quiet_path(self) -> None:
        """
        هر چهار مدلی که کاربر نصب دارد باید مسیر کم‌خطر را بروند.

        این آزمون مستقیماً از تصویر ترمینال کاربر آمده است.
        """
        from ai.providers.base import AIMessage, AIProviderConfig
        from ai.providers.ollama_provider import OllamaProvider

        for model in (
            "gemma4:e4b-it-qat",
            "deepseek-r1:8b",
            "deepseek-coder:6.7b",
            "llama3.1:8b",
        ):
            provider = OllamaProvider(
                AIProviderConfig(
                    name="ollama",
                    base_url="http://127.0.0.1:11434",
                    model=model,
                    max_tokens=1600,
                    extra={"provider_type": "ollama"},
                )
            )
            first = await self._capture(provider, [AIMessage("user", "سلام")])
            second = await self._capture(provider, [AIMessage("user", "x" * 40_000)])

            # هر چهار مدل باید در تمام عمر اجرا فقط یک بار بارگذاری شوند.
            assert first["options"].get("num_ctx") == second["options"].get("num_ctx"), model


class TestTheWindowNeverChangesMidSession:
    """
    نیمهٔ دومِ همان اشکال — چیزی که در ۱٫۹٫۷ از قلم افتاد.

    در ۱٫۹٫۷ شرط «فقط وقتی لازم شد `num_ctx` بفرست» گذاشته شد و برای یک
    پیام کوتاه درست کار می‌کرد. ولی یک نوبت چت چند دور دارد و هر دور،
    نتیجهٔ ابزارها را به تاریخچه اضافه می‌کند. پس:

        دور ۱ → ۱۲۳۲ توکن → چیزی نمی‌فرستد → مدل با ۴۰۹۶ بارگذاری می‌شود
        دور ۳ → ۴۱۶۷ توکن → `num_ctx=8192` می‌فرستد → تخلیه + بارگذاری دوباره

    یعنی وسط همان یک نوبت، مدل چندگیگابایتی یک بار کامل عوض می‌شد —
    دقیقاً همان‌جا که کاربر «forcibly closed» می‌گرفت. حالا پنجره به‌محض
    نیاز قفل می‌شود و تا پایان اجرا ثابت می‌ماند.
    """

    @staticmethod
    def _provider(ceiling: int = 8192):
        """ارائه‌دهنده با سقف حافظهٔ دستگاه کاربر (۱۶ گیگابایت ⇒ ۸۱۹۲)."""
        from ai.providers.base import AIProviderConfig
        from ai.providers.ollama_provider import OllamaProvider

        return OllamaProvider(
            AIProviderConfig(
                name="ollama",
                base_url="http://127.0.0.1:11434",
                model="llama3.1:8b",
                max_tokens=1600,
                extra={"provider_type": "ollama", "max_context": ceiling},
            )
        )

    @staticmethod
    async def _windows(provider, conversations) -> list:  # noqa: ANN001
        """پنجرهٔ فرستاده‌شده در هر درخواست را به ترتیب برمی‌گرداند."""
        seen: list = []

        class Recorder:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                seen.append((json.get("options") or {}).get("num_ctx"))
                return FakeResponse(
                    200, {"model": "llama3.1:8b", "message": {"content": "ok"}, "done": True}
                )

        provider._get_client = lambda: _async(Recorder())  # noqa: SLF001
        provider.resolve_model = lambda: _async("llama3.1:8b")  # noqa: SLF001
        for messages in conversations:
            await provider.generate(messages)
        return seen

    @staticmethod
    def _turn():
        """یک نوبت واقعی چت: پرسش کوتاه، سپس دو دور نتیجهٔ ابزار."""
        from ai.providers.base import AIMessage

        system = AIMessage("system", "S" * 3643)  # اندازهٔ واقعی پیام سیستمی
        first = [system, AIMessage("user", "تحلیل BTC/USDT")]
        second = first + [
            AIMessage("assistant", "X" * 200),
            AIMessage("user", "Tool results:\n" + "D" * 4200),
        ]
        third = second + [
            AIMessage("assistant", "Y" * 200),
            AIMessage("user", "Tool results:\n" + "E" * 5000),
        ]
        return [first, second, third]

    @pytest.mark.asyncio
    async def test_the_window_is_never_changed_once_it_is_set(self) -> None:
        """مهم‌ترین آزمون این نسخه: هیچ دو پنجرهٔ متفاوتی فرستاده نشود."""
        windows = await self._windows(self._provider(), self._turn())

        # «هیچ‌چیز نفرستادن» هم خودش یک پنجره است: پنجرهٔ پیش‌فرض ۴۰۹۶.
        # پس گذار None → 8192 دقیقاً همان بارگذاری دوباره‌ای است که
        # اجراکننده را می‌کشد و نباید از شمارش کنار گذاشته شود.
        from ai.providers.ollama_provider import DEFAULT_MODEL_CONTEXT

        effective = [w or DEFAULT_MODEL_CONTEXT for w in windows]
        assert len(set(effective)) == 1, f"پنجره وسط نوبت عوض شد: {windows}"

    @pytest.mark.asyncio
    async def test_a_short_follow_up_keeps_the_locked_window(self) -> None:
        """
        پس از قفل‌شدن پنجره، حتی «مرسی» هم باید همان عدد را بفرستد.

        وسوسه این است که برای پیام کوتاه دوباره چیزی نفرستیم؛ ولی آن هم
        یک تغییر است و مدل را دوباره بارگذاری می‌کند.
        """
        from ai.providers.base import AIMessage

        provider = self._provider()
        conversations = self._turn() + [[AIMessage("user", "مرسی")]]

        windows = await self._windows(provider, conversations)

        assert windows[-1] == 8192

    @pytest.mark.asyncio
    async def test_a_quiet_session_is_also_constant(self) -> None:
        """
        گفت‌وگوی کوتاه هم باید پنجرهٔ یکسان بفرستد.

        فرق نمی‌کند کدام مقدار؛ مهم این است که در هیچ درخواستی عوض نشود.
        """
        from ai.providers.base import AIMessage

        windows = await self._windows(
            self._provider(),
            [[AIMessage("user", "سلام")], [AIMessage("user", "خوبی؟")]],
        )

        assert len(set(windows)) == 1

    @pytest.mark.asyncio
    async def test_the_locked_window_is_the_machine_ceiling(self) -> None:
        """
        هنگام قفل‌شدن، سقف دستگاه انتخاب می‌شود نه اندازهٔ همان درخواست.

        انتخاب اندازهٔ دقیقِ هر درخواست یعنی درخواست بعدی که کمی بزرگ‌تر
        است، عدد دیگری می‌خواهد و باز هم بارگذاری دوباره.
        """
        from ai.providers.base import AIMessage

        provider = self._provider(ceiling=8192)
        windows = await self._windows(
            provider, [[AIMessage("user", "x" * 15_000)]]
        )

        assert windows == [8192]

    @pytest.mark.asyncio
    async def test_requests_are_serialised(self) -> None:
        """
        اولاما پیش‌فرض همزمانی ندارد؛ دو درخواست همزمان حافظهٔ KV را دو
        برابر می‌کنند و اجراکننده می‌میرد.

        چت کاربر و بازبینی خودکار سیگنال دقیقاً می‌توانند همزمان شوند.
        """
        import asyncio

        from ai.providers.base import AIMessage

        provider = self._provider()
        overlap = {"max": 0, "now": 0}

        class Recorder:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                overlap["now"] += 1
                overlap["max"] = max(overlap["max"], overlap["now"])
                await asyncio.sleep(0.01)
                overlap["now"] -= 1
                return FakeResponse(
                    200, {"model": "llama3.1:8b", "message": {"content": "ok"}, "done": True}
                )

        provider._get_client = lambda: _async(Recorder())  # noqa: SLF001
        provider.resolve_model = lambda: _async("llama3.1:8b")  # noqa: SLF001

        await asyncio.gather(
            *(provider.generate([AIMessage("user", "سلام")]) for _ in range(4))
        )

        assert overlap["max"] == 1


class TestOllamaSizesTheWindowNotUs:
    """
    درس نسخهٔ ۱٫۹٫۹، مستقیماً از لاگ خود اولاما روی دستگاه کاربر.

        library=Vulkan name="NVIDIA GeForce GT 740"
            total="2.0 GiB" available="1.7 GiB"
        msg="vram-based default context" default_num_ctx=4096

    اولاما پنجره را از روی **VRAM** حساب می‌کند. کاربر ۱۶ گیگابایت رم
    سیستم دارد ولی فقط ۲ گیگابایت VRAM. من سقف را از رم سیستم
    درمی‌آوردم و ۸۱۹۲ می‌فرستادم — دو برابر چیزی که کارت تحمل می‌کرد.

    ما به VRAM دسترسی نداریم و اولاما دارد. پس تصمیم مال اوست.
    """

    @staticmethod
    def _provider(max_context: int = 0):
        from ai.providers.base import AIProviderConfig
        from ai.providers.ollama_provider import OllamaProvider

        extra = {"provider_type": "ollama"}
        if max_context:
            extra["max_context"] = max_context
        return OllamaProvider(
            AIProviderConfig(
                name="ollama",
                base_url="http://127.0.0.1:11434",
                model="llama3.1:8b",
                max_tokens=1600,
                extra=extra,
            )
        )

    @staticmethod
    async def _options(provider, messages):  # noqa: ANN001, ANN205
        sent: dict = {}

        class Recorder:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                sent.update(json)
                return FakeResponse(
                    200, {"model": "llama3.1:8b", "message": {"content": "ok"}, "done": True}
                )

        provider._get_client = lambda: _async(Recorder())  # noqa: SLF001
        provider.resolve_model = lambda: _async("llama3.1:8b")  # noqa: SLF001
        await provider.generate(messages)
        return sent["options"]

    @pytest.mark.asyncio
    async def test_system_ram_never_decides_the_window(self) -> None:
        """
        مهم‌ترین آزمون این نسخه.

        دستگاهی با رم فراوان ولی کارت گرافیک کوچک نباید باعث شود
        پنجرهٔ بزرگ تحمیل کنیم. چون اصلاً چیزی نمی‌فرستیم، رم سیستم
        بی‌اثر است.
        """
        from ai.providers.base import AIMessage

        provider = self._provider()
        provider._memory_ceiling = lambda: 32768  # noqa: SLF001 - رم فراوان

        options = await self._options(provider, [AIMessage("user", "x" * 40_000)])

        assert "num_ctx" not in options

    @pytest.mark.asyncio
    async def test_an_explicit_user_setting_is_still_honoured(self) -> None:
        """
        اگر کاربر آگاهانه عددی گذاشته باشد، به او احترام می‌گذاریم.

        او سخت‌افزارش را می‌شناسد؛ ما فقط نباید *حدس* بزنیم.
        """
        from ai.providers.base import AIMessage

        options = await self._options(
            self._provider(max_context=2048), [AIMessage("user", "سلام")]
        )

        assert options["num_ctx"] == 2048

    @pytest.mark.asyncio
    async def test_the_pinned_value_never_changes_either(self) -> None:
        """عدد صریح کاربر هم باید در همهٔ درخواست‌ها یکسان بماند."""
        from ai.providers.base import AIMessage

        provider = self._provider(max_context=2048)

        short = await self._options(provider, [AIMessage("user", "سلام")])
        long = await self._options(provider, [AIMessage("user", "x" * 40_000)])

        assert short["num_ctx"] == long["num_ctx"] == 2048

    @pytest.mark.asyncio
    async def test_the_users_max_tokens_setting_still_applies(self) -> None:
        """
        حذف `num_ctx` نباید `ai.max_tokens` را هم بی‌اثر کند.

        `num_predict` پارامتر زمان تولید است، نه بارگذاری؛ فرستادنش
        مدل را دوباره بارگذاری نمی‌کند.
        """
        from ai.providers.base import AIMessage

        options = await self._options(self._provider(), [AIMessage("user", "سلام")])

        assert options["num_predict"] > 0


class TestTheAppSurvivesADyingRunner:
    """
    نسخهٔ ۱٫۹٫۱۰ — وقتی نمی‌توان از مرگ جلوگیری کرد، باید از آن جان به در برد.

    سه نسخه تلاش کردم جلوی مرگ اجراکننده را بگیرم و هر بار علت را
    اشتباه حدس زدم. این بار فرض را عوض کردم: **شاید نتوانم جلویش را
    بگیرم.** کارت گرافیک کاربر ۲ گیگابایت است و هیچ‌کدام از چهار مدلش
    در آن جا نمی‌شود؛ همه به CPU سرریز می‌کنند از مسیر Vulkan آزمایشی.

    پس هدف عوض شد: به‌جای «هرگز نشکند»، «وقتی شکست، پاسخ بدهد».
    """

    @staticmethod
    def _provider():
        from ai.providers.base import AIProviderConfig
        from ai.providers.ollama_provider import OllamaProvider

        return OllamaProvider(
            AIProviderConfig(
                name="ollama",
                base_url="http://127.0.0.1:11434",
                model="llama3.1:8b",
                max_tokens=1600,
                extra={"provider_type": "ollama"},
            )
        )

    @staticmethod
    def _crashing_client(limit_chars: int, sizes: list):
        """کلاینتی که مثل کارت کم‌حافظه، زیر بار بزرگ می‌شکند."""

        class Client:
            async def post(self, path: str, json: dict):  # noqa: A002, ANN001
                chars = sum(len(m["content"]) for m in json["messages"])
                sizes.append(chars)
                if chars > limit_chars:
                    return FakeResponse(
                        500,
                        {
                            "error": "an error was encountered while running the model: "
                            "wsarecv: An existing connection was forcibly closed "
                            "by the remote host."
                        },
                    )
                return FakeResponse(
                    200,
                    {"model": "llama3.1:8b", "message": {"content": "پاسخ"}, "done": True},
                )

        return Client()

    @pytest.mark.asyncio
    async def test_a_crash_is_survived_by_shrinking_the_prompt(self) -> None:
        """
        مهم‌ترین آزمون این نسخه: کاربر باید پاسخ بگیرد، نه پیام خطا.
        """
        from ai.providers.base import AIMessage

        sizes: list = []
        provider = self._provider()
        provider._get_client = lambda: _async(  # noqa: SLF001
            self._crashing_client(4000, sizes)
        )
        provider.resolve_model = lambda: _async("llama3.1:8b")  # noqa: SLF001

        response = await provider.generate(
            [
                AIMessage("system", "S" * 3643),
                AIMessage("user", "D" * 9000),
            ]
        )

        assert response.content == "پاسخ"
        assert sizes[-1] <= 4000, f"پرامپت واقعاً کوچک نشد: {sizes}"

    @pytest.mark.asyncio
    async def test_the_prompt_actually_gets_smaller_each_attempt(self) -> None:
        """
        نقصی که اندازه‌گیری پیدا کرد.

        نسخهٔ اول این رفع، فقط `num_predict` را نصف می‌کرد و پرامپت روی
        ۴٬۴۱۱ نویسه ثابت می‌ماند — چون پیام سیستمیِ ۱۲۲۲ توکنی هرگز
        کوتاه نمی‌شد و به‌تنهایی از پنجرهٔ نجات بزرگ‌تر بود.
        """
        from ai.providers.base import AIMessage

        sizes: list = []
        provider = self._provider()
        # هیچ‌وقت موفق نمی‌شود: می‌خواهیم همهٔ پله‌ها را ببینیم
        provider._get_client = lambda: _async(  # noqa: SLF001
            self._crashing_client(1, sizes)
        )
        provider.resolve_model = lambda: _async("llama3.1:8b")  # noqa: SLF001

        with pytest.raises(Exception):  # noqa: B017, PT011
            await provider.generate(
                [AIMessage("system", "S" * 3643), AIMessage("user", "D" * 9000)]
            )

        assert len(sizes) >= 3, sizes
        assert sizes[1] < sizes[0], f"تلاش دوم کوچک‌تر نشد: {sizes}"
        assert sizes[2] < sizes[1], f"تلاش سوم کوچک‌تر نشد: {sizes}"

    def test_the_normal_path_still_protects_the_system_prompt(self) -> None:
        """
        کوتاه‌کردن پیام سیستمی فقط مجاز نجات است.

        در مسیر عادی، حذف دستورالعمل یعنی مدل نمی‌داند چه می‌خواهیم و
        پاسخ بی‌ربط می‌دهد — بدتر از خطا، چون بی‌سر و صداست.
        """
        from ai.providers.base import AIMessage

        provider = self._provider()
        fitted = provider._fit_messages(  # noqa: SLF001
            [AIMessage("system", "S" * 3643), AIMessage("user", "D" * 9000)],
            1024,
        )

        assert len(fitted[0]["content"]) == 3643

    def test_the_rescue_path_may_trim_the_system_prompt(self) -> None:
        """در حالت نجات، جایگزینِ کوتاه‌کردن «هیچ پاسخی» است."""
        from ai.providers.base import AIMessage

        provider = self._provider()
        fitted = provider._fit_messages(  # noqa: SLF001
            [AIMessage("system", "S" * 3643), AIMessage("user", "D" * 9000)],
            1024,
            protect_system=False,
        )

        assert len(fitted[0]["content"]) < 3643
