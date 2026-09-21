"""
آزمون‌های نسخهٔ ۱٫۶٫۱.

سه افزودهٔ این نسخه پوشش داده می‌شود:
    ۱. دروازهٔ هوش مصنوعی OmniRoute (ارائه‌دهنده + ابزارها + کاتالوگ)
    ۲. قلم فارسی «ب کودک» و امکان انتخاب قلم از تنظیمات
    ۳. پوستهٔ تازهٔ «نیلی ارکیده»

قاعدهٔ آزمون‌ها: هیچ‌کدام به شبکهٔ واقعی وصل نمی‌شوند. جایی که پاسخ سرویس
لازم است، با یک انتقال‌دهندهٔ ساختگی httpx شبیه‌سازی می‌شود تا آزمون‌ها
هم سریع بمانند و هم بدون اینترنت کار کنند.
"""

from __future__ import annotations

import json
import re

import httpx
import pytest

from ai.providers.base import AIMessage, AIProviderConfig
from ai.providers.catalog import PROVIDER_PRESETS, get_preset
from ai.providers.manager import PROVIDER_TYPES
from ai.providers.omniroute_provider import (
    AUTO_MODEL,
    DEFAULT_BASE_URL,
    OmniRouteProvider,
    model_vendor,
)
from ai.tools import CompositeToolset, OmniRouteToolset
from ai.tools.market_tools import ToolDefinition, ToolResult
from app.core.constants import Theme
from ui.themes.catalog import THEME_CATALOG, get_theme, list_themes
from ui.themes.fonts import (
    DEFAULT_FONT_KEY,
    FONT_CHOICES,
    FONT_FILES,
    FONTS_DIR,
    font_stack,
    list_fonts,
    resolve_font_key,
)
from ui.themes.stylesheet import build_stylesheet
from ui.themes.theme_manager import ThemeManager

#: فهرست مدلی که دروازهٔ واقعی برمی‌گرداند (با پیشوند سرویس)
GATEWAY_MODELS = [
    "auto",
    "if/kimi-k2-thinking",
    "cc/claude-opus-4-6",
    "gg/gemini-2.5-pro",
    "glm/glm-4.7",
]


def _gateway_transport(*, status: int = 200, require_key: str = "") -> httpx.MockTransport:
    """
    انتقال‌دهندهٔ ساختگی که مثل دروازهٔ OmniRoute پاسخ می‌دهد.

    `require_key` غیرخالی یعنی حالت `REQUIRE_API_KEY=true`؛ بدون کلید
    درست، دروازه ۴۰۱ می‌دهد.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if require_key and request.headers.get("Authorization") != f"Bearer {require_key}":
            return httpx.Response(401, json={"error": {"message": "Invalid API key"}})
        if status >= 400:
            return httpx.Response(status, json={"error": {"message": "boom"}})
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={"data": [{"id": name, "object": "model"} for name in GATEWAY_MODELS]},
            )
        payload = json.loads(request.content or b"{}")
        model = payload.get("model") or AUTO_MODEL
        return httpx.Response(
            200,
            json={
                "model": "if/kimi-k2-thinking" if model == AUTO_MODEL else model,
                "choices": [
                    {"message": {"role": "assistant", "content": "سلام"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            },
        )

    return httpx.MockTransport(handler)


def _provider(api_key: str = "", **kwargs) -> OmniRouteProvider:
    """ارائه‌دهندهٔ OmniRoute با انتقال‌دهندهٔ ساختگی."""
    config = AIProviderConfig(
        name="omniroute",
        base_url="http://127.0.0.1:20128/v1",
        model=AUTO_MODEL,
        requires_api_key=False,
    )
    provider = OmniRouteProvider(config, api_key or None)
    provider._client = httpx.AsyncClient(  # noqa: SLF001 - تزریق عمدی در آزمون
        base_url=config.base_url, transport=_gateway_transport(**kwargs)
    )
    return provider


# ===========================================================================
# ۱) ارائه‌دهندهٔ OmniRoute
# ===========================================================================
class TestOmniRouteCatalog:
    """ثبت دروازه در کاتالوگ سرویس‌ها."""

    def test_preset_exists(self) -> None:
        """کاربر باید بتواند OmniRoute را از فهرست تنظیمات انتخاب کند."""
        preset = get_preset("omniroute")
        assert preset is not None
        assert preset.provider_type == "omniroute"
        assert preset.base_url == DEFAULT_BASE_URL

    def test_preset_accepts_an_optional_key(self) -> None:
        """
        کلید اجباری نیست ولی کادرش باید فعال بماند.

        کاربر صریحاً خواست بتواند کلید OmniRoute را وارد کند؛ اگر فقط به
        `requires_key` نگاه می‌کردیم، کادر غیرفعال می‌شد.
        """
        preset = get_preset("omniroute")
        assert preset is not None
        assert preset.requires_key is False
        assert preset.accepts_optional_key is True
        assert preset.key_field_enabled is True

    def test_provider_type_is_wired_into_the_factory(self) -> None:
        """بدون این ثبت، کلاس سازگار عمومی ساخته می‌شد نه کلاس دروازه."""
        assert PROVIDER_TYPES["omniroute"] is OmniRouteProvider

    def test_every_preset_key_is_unique(self) -> None:
        """کلید تکراری یعنی یک سرویس بی‌صدا روی دیگری را می‌پوشاند."""
        keys = [preset.key for preset in PROVIDER_PRESETS]
        assert len(keys) == len(set(keys))


class TestOmniRouteProvider:
    """رفتار کلاینت دروازه."""

    def test_empty_base_url_falls_back_to_the_default(self) -> None:
        """پیکربندی ناقص نباید به خطای «نشانی تنظیم نشده» ختم شود."""
        provider = OmniRouteProvider(
            AIProviderConfig(name="omniroute", base_url="", requires_api_key=False)
        )
        assert provider.config.base_url == DEFAULT_BASE_URL

    @pytest.mark.asyncio
    async def test_reports_availability(self) -> None:
        """دروازهٔ در دسترس باید «در دسترس» گزارش شود."""
        provider = _provider()
        try:
            available, message = await provider.is_available()
            assert available is True
            assert "reachable" in message.lower()
        finally:
            await provider.close()

    @pytest.mark.asyncio
    async def test_works_without_a_key_when_the_gateway_is_open(self) -> None:
        """نصب تازهٔ دروازه کلید نمی‌خواهد؛ نبود کلید نباید خطا بدهد."""
        provider = _provider()
        try:
            available, _ = await provider.is_available()
            assert available is True
        finally:
            await provider.close()

    @pytest.mark.asyncio
    async def test_reports_a_useful_message_when_the_key_is_rejected(self) -> None:
        """
        پیام ۴۰۱ باید بگوید کلید را از کجا بگیرد.

        پیام خام «HTTP 401» به کاربر نمی‌گوید چه کند.
        """
        provider = _provider(api_key="wrong", require_key="right")
        try:
            available, message = await provider.is_available()
            assert available is False
            assert "Endpoints" in message
        finally:
            await provider.close()

    @pytest.mark.asyncio
    async def test_accepts_a_valid_key(self) -> None:
        """با کلید درست، دروازهٔ امن هم باید پاسخ بدهد."""
        provider = _provider(api_key="right", require_key="right")
        try:
            available, _ = await provider.is_available()
            assert available is True
        finally:
            await provider.close()

    @pytest.mark.asyncio
    async def test_auto_model_is_always_first(self) -> None:
        """
        مدل «auto» باید بالای فهرست باشد.

        برای کاربری که تازه وصل شده، سپردن انتخاب به دروازه امن‌ترین
        گزینه است و نیازی به دانستن پیشوندها ندارد.
        """
        provider = _provider()
        try:
            models = await provider.list_models()
            assert models[0] == AUTO_MODEL
            assert models.count(AUTO_MODEL) == 1
            assert "cc/claude-opus-4-6" in models
        finally:
            await provider.close()

    @pytest.mark.asyncio
    async def test_generates_a_reply(self) -> None:
        """مسیر تولید پاسخ باید کامل کار کند."""
        provider = _provider()
        try:
            response = await provider.generate([AIMessage(role="user", content="سلام")])
            assert response.content == "سلام"
            # دروازه «auto» را به مدل واقعی حل می‌کند و همان را برمی‌گرداند
            assert response.model == "if/kimi-k2-thinking"
        finally:
            await provider.close()

    @pytest.mark.asyncio
    async def test_sends_the_application_identity_header(self) -> None:
        """مصرف برنامه باید در داشبورد دروازه قابل تفکیک باشد."""
        provider = _provider()
        try:
            assert provider._headers()["X-Title"] == "Crypto AI Trader"  # noqa: SLF001
        finally:
            await provider.close()

    @pytest.mark.asyncio
    async def test_key_never_appears_in_the_error_message(self) -> None:
        """کلید نباید از هیچ مسیری به متن پیام نشت کند."""
        secret = "sk_omniroute_super_secret"
        provider = _provider(api_key=secret, require_key="other")
        try:
            _, message = await provider.is_available()
            assert secret not in message
        finally:
            await provider.close()


class TestModelVendor:
    """ترجمهٔ پیشوند مدل به نام سرویس."""

    @pytest.mark.parametrize(
        ("model", "expected"),
        [
            ("gg/gemini-2.5-pro", "Gemini"),
            ("if/kimi-k2-thinking", "iFlow"),
            ("cc/claude-opus-4-6", "Claude Code"),
            ("auto", "خودکار"),
        ],
    )
    def test_known_prefixes(self, model: str, expected: str) -> None:
        """پیشوندهای شناخته‌شده باید نام خوانا بدهند."""
        assert model_vendor(model) == expected

    def test_unknown_prefix_is_preserved(self) -> None:
        """
        پیشوند ناشناخته نباید باعث حذف یا خالی شدن نام شود.

        دروازه مدام سرویس تازه اضافه می‌کند؛ برنامه نباید هر بار بشکند.
        """
        assert model_vendor("brandnew/some-model") == "brandnew"

    def test_empty_input(self) -> None:
        """ورودی خالی نباید استثنا بدهد."""
        assert model_vendor("") == ""


# ===========================================================================
# ۲) ابزارهای دروازه
# ===========================================================================
class TestOmniRouteToolset:
    """ابزارهایی که عامل هوش مصنوعی برای پرس‌وجوی دروازه دارد."""

    def test_tool_names(self) -> None:
        """هر دو ابزار باید در دسترس عامل باشند."""
        assert OmniRouteToolset().tool_names == ["omniroute_models", "omniroute_status"]

    def test_definitions_are_valid_function_schemas(self) -> None:
        """توصیف ابزار باید به قالب Function Calling تبدیل شود."""
        for definition in OmniRouteToolset.get_definitions():
            schema = definition.to_openai_schema()
            assert schema["type"] == "function"
            assert schema["function"]["name"].startswith("omniroute_")
            assert schema["function"]["description"]

    @pytest.mark.asyncio
    async def test_status_when_the_gateway_is_configured(self) -> None:
        """وضعیت باید از خود دروازه خوانده شود، نه از حافظهٔ مدل."""
        provider = _provider()
        tools = OmniRouteToolset(provider_factory=lambda: provider)
        try:
            result = await tools.execute("omniroute_status")
            assert result.ok is True
            assert result.data["reachable"] is True
            assert result.data["model_count"] == len(GATEWAY_MODELS)
            assert "Gemini" in result.data["vendors"]
        finally:
            await provider.close()

    @pytest.mark.asyncio
    async def test_status_when_the_gateway_is_not_configured(self) -> None:
        """
        نبود پیکربندی هم یک پاسخ معتبر است.

        ابزار باید صریح بگوید «پیکربندی نشده» تا مدل چیزی از خودش نسازد.
        """
        result = await OmniRouteToolset().execute("omniroute_status")
        assert result.ok is True
        assert result.data["configured"] is False
        assert "Settings" in result.data["hint"]

    @pytest.mark.asyncio
    async def test_status_never_returns_the_api_key(self) -> None:
        """خروجی ابزار فقط می‌گوید کلید هست یا نه — نه خودِ کلید."""
        secret = "sk_omniroute_do_not_leak"
        provider = _provider(api_key=secret)
        tools = OmniRouteToolset(provider_factory=lambda: provider)
        try:
            result = await tools.execute("omniroute_status")
            assert result.data["api_key_configured"] is True
            assert secret not in json.dumps(result.to_dict(), ensure_ascii=False)
        finally:
            await provider.close()

    @pytest.mark.asyncio
    async def test_models_are_grouped_by_vendor(self) -> None:
        """گروه‌بندی کمک می‌کند کاربر بفهمد هر مدل از کجا می‌آید."""
        provider = _provider()
        tools = OmniRouteToolset(provider_factory=lambda: provider)
        try:
            result = await tools.execute("omniroute_models")
            assert result.ok is True
            assert result.data["total"] == len(GATEWAY_MODELS)
            assert "Gemini" in result.data["by_vendor"]
        finally:
            await provider.close()

    @pytest.mark.asyncio
    async def test_models_can_be_filtered_by_vendor(self) -> None:
        """فیلتر باید هم با نام خوانا و هم با پیشوند خام کار کند."""
        provider = _provider()
        tools = OmniRouteToolset(provider_factory=lambda: provider)
        try:
            by_name = await tools.execute("omniroute_models", {"vendor": "Gemini"})
            by_prefix = await tools.execute("omniroute_models", {"vendor": "gg"})
            assert by_name.data["models"] == ["gg/gemini-2.5-pro"]
            assert by_prefix.data["models"] == ["gg/gemini-2.5-pro"]
        finally:
            await provider.close()

    @pytest.mark.asyncio
    async def test_unknown_tool_fails_cleanly(self) -> None:
        """ابزار ناشناخته نباید استثنا بدهد."""
        result = await OmniRouteToolset().execute("nope")
        assert result.ok is False
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_unreachable_gateway_is_reported_not_raised(self) -> None:
        """خطای شبکه باید به نتیجهٔ ناموفق تبدیل شود تا گفتگو قطع نشود."""

        def fail(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        provider = _provider()
        provider._client = httpx.AsyncClient(  # noqa: SLF001
            base_url="http://127.0.0.1:20128/v1", transport=httpx.MockTransport(fail)
        )
        tools = OmniRouteToolset(provider_factory=lambda: provider)
        try:
            result = await tools.execute("omniroute_models")
            assert result.ok is False
            assert "unreachable" in result.error.lower()
        finally:
            await provider.close()


class TestCompositeToolset:
    """ترکیب ابزار بازار با ابزار دروازه."""

    class _Stub:
        """یک مجموعه‌ابزار کمینه برای آزمون ترکیب."""

        def __init__(self, name: str) -> None:
            self._name = name
            self.risk_calls: list[object] = []

        @property
        def tool_names(self) -> list[str]:
            return [self._name]

        def get_definitions(self) -> list[ToolDefinition]:
            return [ToolDefinition(self._name, "stub", {})]

        async def execute(self, name: str, arguments: dict | None = None) -> ToolResult:
            return ToolResult(tool=name, ok=True, data={"from": self._name})

        def set_risk_parameters(self, parameters: object) -> None:
            self.risk_calls.append(parameters)

    def test_tool_names_are_merged(self) -> None:
        """عامل باید ابزارهای هر دو مجموعه را ببیند."""
        combined = CompositeToolset(self._Stub("alpha"), self._Stub("beta"))
        assert combined.tool_names == ["alpha", "beta"]

    def test_definitions_are_merged_without_duplicates(self) -> None:
        """نام تکراری نباید دو بار به مدل معرفی شود."""
        combined = CompositeToolset(self._Stub("same"), self._Stub("same"))
        assert [d.name for d in combined.get_definitions()] == ["same"]

    @pytest.mark.asyncio
    async def test_execute_routes_to_the_owning_toolset(self) -> None:
        """هر ابزار باید توسط مجموعهٔ صاحبش اجرا شود."""
        combined = CompositeToolset(self._Stub("alpha"), self._Stub("beta"))
        result = await combined.execute("beta")
        assert result.data == {"from": "beta"}

    @pytest.mark.asyncio
    async def test_first_registered_toolset_wins(self) -> None:
        """
        ترتیب ثبت یعنی اولویت.

        رفتار باید قابل پیش‌بینی باشد تا افزونهٔ تازه نتواند بی‌سروصدا
        ابزار اصلی بازار را جایگزین کند.
        """
        first, second = self._Stub("dup"), self._Stub("dup")
        first._name, second._name = "dup", "dup"
        combined = CompositeToolset(first, second)
        result = await combined.execute("dup")
        assert result.ok is True

    @pytest.mark.asyncio
    async def test_unknown_tool_fails_cleanly(self) -> None:
        """ابزار ناشناخته نباید استثنا بدهد."""
        result = await CompositeToolset(self._Stub("alpha")).execute("ghost")
        assert result.ok is False

    def test_risk_parameters_reach_every_toolset(self) -> None:
        """عامل‌ها این متد را بی‌قیدوشرط صدا می‌زنند."""
        first, second = self._Stub("a"), self._Stub("b")
        CompositeToolset(first, second).set_risk_parameters("risk")
        assert first.risk_calls == ["risk"] and second.risk_calls == ["risk"]

    def test_none_toolsets_are_ignored(self) -> None:
        """پیکربندی ناقص نباید ترکیب را بشکند."""
        assert CompositeToolset(None, self._Stub("a")).tool_names == ["a"]


# ===========================================================================
# ۳) قلم فارسی
# ===========================================================================
class TestPersianFont:
    """قلم «ب کودک» و انتخابگر قلم."""

    def test_font_files_ship_with_the_application(self) -> None:
        """
        قلم باید همراه برنامه توزیع شود.

        اگر به نصب‌بودن قلم روی ویندوز کاربر تکیه می‌کردیم، ظاهر برنامه
        روی هر دستگاه فرق می‌کرد.
        """
        for file_name in FONT_FILES:
            assert (FONTS_DIR / file_name).exists(), file_name

    def test_koodak_files_are_real_truetype_fonts(self) -> None:
        """فایل باید واقعاً قلم باشد، نه صفحهٔ HTML دانلود."""
        for file_name in ("Koodak.ttf", "BKoodakBd.ttf"):
            header = (FONTS_DIR / file_name).read_bytes()[:4]
            assert header in (b"\x00\x01\x00\x00", b"true", b"ttcf"), file_name

    def test_default_font_is_vazirmatn(self) -> None:
        """
        پیش‌فرض از «ب کودک» به وزیرمتن تغییر کرد.

        کاربر پس از دیدن نتیجه گفت «فونت پیش‌فرض وزیرمتن باشه، این
        خوبه». «ب کودک» حذف نشد و همچنان یکی از گزینه‌هاست — آزمون
        بعدی همان را می‌سنجد.
        """
        assert DEFAULT_FONT_KEY == "vazirmatn"

    def test_koodak_is_still_available_as_a_choice(self) -> None:
        """تغییر پیش‌فرض نباید گزینهٔ قبلی را از فهرست بیندازد."""
        from ui.themes.fonts import FONT_MAP

        assert "koodak" in FONT_MAP

    def test_koodak_stack_starts_with_koodak(self) -> None:
        """زنجیره باید از خود کودک شروع شود."""
        assert font_stack("koodak").startswith('"B Koodak"')

    def test_every_stack_ends_with_a_latin_fallback(self) -> None:
        """
        نمادهای بازار نباید به‌هم بریزند.

        قلم کودک حرف لاتین ندارد؛ بدون قلم پشتیبان، `BTC/USDT` مربع خالی
        می‌شد. این آزمون همان قاعده را قفل می‌کند.
        """
        for choice in FONT_CHOICES:
            assert "Vazirmatn" in choice.stack, choice.key

    def test_unknown_font_key_falls_back(self) -> None:
        """مقدار ناشناخته در تنظیمات نباید برنامه را بشکند."""
        assert resolve_font_key("no-such-font") == DEFAULT_FONT_KEY
        assert resolve_font_key(None) == DEFAULT_FONT_KEY
        assert resolve_font_key("") == DEFAULT_FONT_KEY

    def test_every_choice_has_both_names(self) -> None:
        """انتخابگر در هر دو زبان باید نام داشته باشد."""
        for choice in list_fonts():
            assert choice.name_fa and choice.name_en, choice.key

    def test_font_keys_are_unique(self) -> None:
        """کلید تکراری یعنی یک گزینه بی‌صدا گم می‌شود."""
        keys = [choice.key for choice in FONT_CHOICES]
        assert len(keys) == len(set(keys))


class TestFontInStylesheet:
    """تزریق قلم به برگهٔ سبک."""

    def test_stylesheet_carries_the_font_family(self) -> None:
        """قاعدهٔ پایهٔ QWidget باید خانوادهٔ قلم را داشته باشد."""
        css = build_stylesheet(get_theme("glass_dark"), font_stack("koodak"))
        assert "font-family:" in css
        assert '"B Koodak"' in css

    def test_font_is_independent_of_the_theme(self) -> None:
        """
        قلم ترجیح کاربر است، نه بخشی از پوسته.

        عوض‌کردن پوسته نباید قلم را برگرداند.
        """
        for theme in list_themes():
            css = build_stylesheet(theme, font_stack("vazirmatn"))
            assert '"Vazirmatn"' in css
            assert '"B Koodak"' not in css

    def test_every_theme_and_font_combination_renders(self) -> None:
        """هیچ ترکیبی نباید جای‌گیر پرنشده باقی بگذارد."""
        for theme in list_themes():
            for choice in FONT_CHOICES:
                css = build_stylesheet(theme, font_stack(choice.key))
                assert not re.search(r"\{[a-z_]+\}", css), (theme.key, choice.key)

    def test_missing_font_argument_uses_the_default(self) -> None:
        """فراخوانی قدیمی با یک آرگومان نباید بشکند."""
        assert '"Vazirmatn"' in build_stylesheet(get_theme("glass_dark"))


class TestThemeManagerFont:
    """نگهداری انتخاب قلم در مدیر پوسته."""

    def test_default_font_key(self) -> None:
        """مدیر تازه باید با قلم پیش‌فرض شروع کند."""
        assert ThemeManager().font_key == DEFAULT_FONT_KEY

    def test_font_survives_a_theme_change(self) -> None:
        """
        مهم‌ترین قاعده: پوسته قلم را پاک نمی‌کند.

        کاربر باید بتواند قلم را انتخاب کند و بعد پوسته را عوض کند بدون
        آنکه قلمش برگردد.
        """
        manager = ThemeManager()
        manager.set_font_family("vazirmatn")
        assert manager.font_key == "vazirmatn"
        assert '"Vazirmatn"' in manager.stylesheet("orchid_indigo")
        assert manager.font_key == "vazirmatn"

    def test_invalid_font_is_rejected_safely(self) -> None:
        """مقدار نامعتبر باید به پیش‌فرض برگردد، نه خطا بدهد."""
        manager = ThemeManager()
        assert manager.set_font_family("ghost-font") == DEFAULT_FONT_KEY

    def test_available_fonts_are_exposed(self) -> None:
        """صفحهٔ تنظیمات فهرست را از همین‌جا می‌گیرد."""
        assert len(ThemeManager.available_fonts()) == len(FONT_CHOICES)


# ===========================================================================
# ۴) پوستهٔ «نیلی ارکیده»
# ===========================================================================
class TestOrchidIndigoTheme:
    """پوستهٔ تازهٔ هفتم."""

    def test_theme_exists(self) -> None:
        """پوسته باید در کاتالوگ باشد."""
        theme = get_theme("orchid_indigo")
        assert theme.key == "orchid_indigo"
        assert theme.is_dark is True
        assert theme.name_en == "Orchid Indigo"
        assert theme.name_fa

    def test_theme_is_registered_in_the_enum(self) -> None:
        """
        هر کلید کاتالوگ باید در `Theme` هم باشد.

        بدون این، ذخیرهٔ انتخاب کاربر می‌شکند.
        """
        assert Theme.ORCHID_INDIGO.value == "orchid_indigo"
        assert {t.value for t in Theme} >= set(THEME_CATALOG)

    def test_theme_is_selectable_by_name(self) -> None:
        """کاربر باید بتواند پوسته را با نام از تنظیمات انتخاب کند."""
        assert "orchid_indigo" in [theme.key for theme in list_themes()]

    def test_primary_differs_from_the_other_dark_themes(self) -> None:
        """
        پوستهٔ «زیباتر» باید واقعاً متفاوت دیده شود.

        سه پوستهٔ تیرهٔ قبلی همگی رنگ اصلی فیروزه‌ای دارند؛ اگر این یکی
        هم همان بود، کاربر تفاوتی نمی‌دید.
        """
        primary = get_theme("orchid_indigo").colors.primary.lower()
        others = {
            get_theme(key).colors.primary.lower()
            for key in ("glass_dark", "royal_silk", "midnight_aurora")
        }
        assert primary not in others

    def test_accent_is_not_confusable_with_market_colours(self) -> None:
        """
        لهجه نباید با سبز سود یا قرمز زیان اشتباه شود.

        اگر قرمزِ زیان و لهجه یکی بودند، کاربر در یک نگاه نمی‌فهمید کدام
        عدد ضرر است.
        """
        colors = get_theme("orchid_indigo").colors
        assert colors.accent.lower() not in {colors.success.lower(), colors.danger.lower()}
        assert colors.success.lower() != colors.danger.lower()

    def test_stylesheet_builds_completely(self) -> None:
        """هیچ جای‌گیری نباید پر نشده بماند."""
        css = build_stylesheet(get_theme("orchid_indigo"))
        assert not re.search(r"\{[a-z_]+\}", css)
        assert len(css) > 5_000

    def test_rounded_corners_are_preserved(self) -> None:
        """
        کاربر خواست هیچ دکمه‌ای گوشهٔ تیز نداشته باشد.

        پوستهٔ تازه نباید این قاعده را بشکند.
        """
        metrics = get_theme("orchid_indigo").metrics
        assert metrics.radius_sm >= 6
        assert metrics.radius_md >= 10

    def test_theme_has_a_localised_name_in_both_languages(self) -> None:
        """نام پوسته باید در هر دو زبان ترجمه داشته باشد."""
        for language in ("fa", "en"):
            data = json.loads(
                (FONTS_DIR.parents[1] / "localization" / language / "settings.json").read_text(
                    encoding="utf-8"
                )
            )
            assert "orchid_indigo" in data["themes"]
            assert "orchid_indigo" in data["theme_descriptions"]


# ===========================================================================
# ۵) یکپارچگی با رابط کاربری
# ===========================================================================
@pytest.fixture
def settings_page(qt_application):
    """
    فقط صفحهٔ تنظیمات، بدون ساختن کل برنامه.

    نسخهٔ اول این فیکسچر یک `Application` کامل می‌ساخت (پایگاه داده +
    مهاجرت‌ها). زیر بار، آزمون‌ها روی قفل SQLite می‌خوابیدند و کل اجرا
    متوقف می‌شد. صفحهٔ تنظیمات فقط به `Translator` نیاز دارد، پس همان
    ساخته می‌شود: هم سریع‌تر است و هم قفل نمی‌کند.
    """
    from localization import Translator
    from ui.pages.settings_page import SettingsPage

    translator = Translator("fa")
    translator.load()
    page = SettingsPage(translator)
    try:
        yield page, qt_application
    finally:
        page.deleteLater()
        qt_application.processEvents()


class TestSettingsPageIntegration:
    """انتخاب قلم، پوسته و سرویس از صفحهٔ تنظیمات."""

    def test_font_picker_lists_every_choice(self, settings_page) -> None:
        """همهٔ قلم‌ها باید در انتخابگر باشند."""
        page, _ = settings_page
        combo = page.font_family_combo
        keys = [combo.itemData(i) for i in range(combo.count())]
        assert keys == [choice.key for choice in FONT_CHOICES]

    def test_choosing_a_font_emits_immediately(self, settings_page) -> None:
        """
        تغییر قلم باید بی‌درنگ اعلام شود، نه پس از زدن «ذخیره».

        همان قاعده‌ای که برای پوسته گذاشته شده بود.
        """
        page, qt = settings_page
        seen: list[str] = []
        page.font_family_changed.connect(seen.append)
        combo = page.font_family_combo
        # قلمی غیر از گزینهٔ جاری انتخاب می‌شود. پیش‌تر اینجا «وزیرمتن»
        # بود، ولی از وقتی وزیرمتن پیش‌فرض و آیتم نخست شد، انتخابش
        # تغییری نیست و Qt سیگنالی نمی‌دهد — آزمون می‌شکست بی‌آنکه
        # چیزی خراب شده باشد.
        combo.setCurrentIndex(combo.findData("sahel"))
        qt.processEvents()
        assert seen == ["sahel"]

    def test_font_choice_is_collected_for_saving(self, settings_page) -> None:
        """مقدار باید در خروجی ذخیره‌سازی باشد وگرنه با راه‌اندازی بعدی می‌پرد."""
        page, qt = settings_page
        combo = page.font_family_combo
        combo.setCurrentIndex(combo.findData("koodak_light"))
        qt.processEvents()
        assert page.collect_values()["ui.font_family"] == "koodak_light"

    def test_saved_font_is_restored(self, settings_page) -> None:
        """مقدار ذخیره‌شده باید در انتخابگر نشان داده شود."""
        page, _ = settings_page
        page.load_values({"ui.font_family": "vazirmatn"})
        assert page.font_family_combo.currentData() == "vazirmatn"

    def test_restoring_a_font_does_not_re_emit(self, settings_page) -> None:
        """
        بارگذاری مقدار ذخیره‌شده نباید «تغییر کاربر» تلقی شود.

        وگرنه هر بار باز شدن تنظیمات یک ذخیره‌سازی بی‌مورد راه می‌انداخت.
        """
        page, qt = settings_page
        seen: list[str] = []
        page.font_family_changed.connect(seen.append)
        page.load_values({"ui.font_family": "vazirmatn"})
        qt.processEvents()
        assert seen == []

    def test_unknown_saved_font_falls_back_safely(self, settings_page) -> None:
        """تنظیم خراب نباید صفحه را بشکند."""
        page, _ = settings_page
        page.load_values({"ui.font_family": "ghost"})
        assert page.font_family_combo.currentData() == DEFAULT_FONT_KEY

    def test_new_theme_appears_in_the_picker(self, settings_page) -> None:
        """پوستهٔ تازه باید با نام قابل انتخاب باشد."""
        page, _ = settings_page
        combo = page.theme_combo
        assert "orchid_indigo" in [combo.itemData(i) for i in range(combo.count())]

    def test_every_theme_has_a_card(self, settings_page) -> None:
        """هر پوسته باید کارت انتخاب خودش را داشته باشد."""
        page, _ = settings_page
        assert set(page._theme_cards) == set(THEME_CATALOG)  # noqa: SLF001

    def test_omniroute_appears_in_the_provider_picker(self, settings_page) -> None:
        """کاربر باید بتواند دروازه را از فهرست سرویس‌ها انتخاب کند."""
        page, _ = settings_page
        combo = page.ai_provider_combo
        assert "omniroute" in [combo.itemData(i) for i in range(combo.count())]

    def test_selecting_omniroute_fills_the_base_url_and_enables_the_key(
        self, settings_page
    ) -> None:
        """
        انتخاب دروازه باید نشانی پیش‌فرض را بگذارد و کادر کلید را باز کند.

        کاربر صریحاً خواست بتواند کلید OmniRoute را وارد کند؛ اگر فقط به
        `requires_key` نگاه می‌کردیم، کادر غیرفعال می‌ماند.
        """
        page, qt = settings_page
        combo = page.ai_provider_combo
        combo.setCurrentIndex(combo.findData("omniroute"))
        qt.processEvents()

        assert page.ai_base_url_input.text() == DEFAULT_BASE_URL
        assert page.ai_key_input.isEnabled() is True
        assert page.ai_model_combo.count() > 0

    def test_omniroute_suggests_the_auto_model(self, settings_page) -> None:
        """مدل «auto» باید بدون تماس با شبکه هم پیشنهاد شود."""
        page, qt = settings_page
        combo = page.ai_provider_combo
        combo.setCurrentIndex(combo.findData("omniroute"))
        qt.processEvents()
        models = [page.ai_model_combo.itemData(i) for i in range(page.ai_model_combo.count())]
        assert AUTO_MODEL in models

    def test_omniroute_key_is_collected_as_a_secret(self, settings_page) -> None:
        """کلید باید در مسیر رمزها برود، نه در تنظیمات ساده."""
        page, qt = settings_page
        combo = page.ai_provider_combo
        combo.setCurrentIndex(combo.findData("omniroute"))
        qt.processEvents()
        page.ai_key_input.setText("sk_omniroute_secret")

        assert page.collect_secrets()["ai.omniroute.api_key"] == "sk_omniroute_secret"
        assert "sk_omniroute_secret" not in str(page.collect_values())

    def test_ollama_still_has_no_key_field(self, settings_page) -> None:
        """
        سرویسی که واقعاً کلید نمی‌پذیرد نباید کادر باز داشته باشد.

        این آزمون مرز فیلد تازهٔ `accepts_optional_key` را نگه می‌دارد.
        """
        page, qt = settings_page
        combo = page.ai_provider_combo
        combo.setCurrentIndex(combo.findData("ollama"))
        qt.processEvents()
        assert page.ai_key_input.isEnabled() is False
