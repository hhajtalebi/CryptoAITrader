"""
آزمون‌های ارائه‌دهندهٔ «آشنا» (AshnaAI) — نسخهٔ ۱٫۹٫۱۳.

آشنا یک دروازهٔ سازگار با OpenAI است، پس کلاس تازه‌ای لازم ندارد و از
`OpenAICompatibleProvider` موجود استفاده می‌کند. چیزی که آزمون می‌خواهد،
**درستی پیکربندی** است.

حساس‌ترین نکته: مسیر پایه `/v1/api` است، نه `/v1`.
    این تنها تفاوت آشنا با بقیهٔ سرویس‌هاست و اگر اشتباه باشد همهٔ
    درخواست‌ها ۴۰۴ می‌گیرند — با پیامی که هیچ ربطی به علت واقعی ندارد.
"""

from __future__ import annotations

import pytest

from ai.providers.catalog import PROVIDER_PRESETS, get_preset


@pytest.fixture
def ashna():
    """پیکربندی آمادهٔ آشنا."""
    preset = get_preset("ashna")
    assert preset is not None, "ارائه‌دهندهٔ آشنا ثبت نشده است"
    return preset


class TestAshnaIsRegistered:
    """آشنا باید در فهرست ارائه‌دهنده‌ها باشد و درست پیکربندی شده باشد."""

    def test_the_provider_exists(self, ashna) -> None:  # noqa: ANN001
        """بدون این، هیچ‌چیز دیگری معنا ندارد."""
        assert ashna.key == "ashna"

    def test_the_base_url_includes_the_api_segment(self, ashna) -> None:
        """
        مهم‌ترین آزمون این فایل.

        مستندات آشنا صریح است: `https://api.ashna.ai/v1/api`. کلاینت
        خودش `/chat/completions` و `/models` را به آن می‌چسباند. اگر
        کسی این را به `/v1` «اصلاح» کند، همه‌چیز ۴۰۴ می‌شود.
        """
        assert ashna.base_url == "https://api.ashna.ai/v1/api"
        assert ashna.base_url.endswith("/v1/api")

    def test_the_base_url_has_no_trailing_slash(self, ashna) -> None:
        """اسلش انتهایی مسیر را به `//chat/completions` تبدیل می‌کند."""
        assert not ashna.base_url.endswith("/")

    def test_it_reuses_the_openai_compatible_transport(self, ashna) -> None:
        """
        آشنا سازگار با OpenAI است؛ نوشتن کلاس تازه فقط کد تکراری و یک
        مسیر آزمون‌نشدهٔ دیگر می‌ساخت.
        """
        assert ashna.provider_type == "openai_compatible"

    def test_an_api_key_is_required_and_typeable(self, ashna) -> None:
        """کاربر کلید دارد؛ کادر ورودی باید فعال باشد."""
        assert ashna.requires_key is True
        assert ashna.key_field_enabled is True

    def test_it_is_not_marked_local(self, ashna) -> None:
        """سرویس ابری است؛ علامت «محلی» رفتار اتصال را عوض می‌کند."""
        assert ashna.is_local is False

    def test_the_signup_url_points_at_the_key_page(self, ashna) -> None:
        """کاربر باید مستقیم به صفحهٔ ساخت کلید برود."""
        assert ashna.signup_url == "https://app.ashna.ai/account?tab=api"

    def test_model_listing_is_supported(self, ashna) -> None:
        """آشنا `GET /models` دارد، پس کشف خودکار مدل کار می‌کند."""
        assert ashna.supports_model_listing is True

    def test_the_persian_display_name_is_used(self, ashna) -> None:
        """رابط فارسی است؛ نام باید فارسی دیده شود."""
        assert "آشنا" in ashna.display_name

    def test_the_key_is_unique_in_the_catalog(self) -> None:
        """کلید تکراری، ارائه‌دهندهٔ دیگری را بی‌صدا پنهان می‌کند."""
        keys = [preset.key for preset in PROVIDER_PRESETS]

        assert keys.count("ashna") == 1
        assert len(keys) == len(set(keys))


class TestAshnaSuggestedModels:
    """مدل‌های پیشنهادی باید از شناسه‌های واقعی کاتالوگ آشنا باشند."""

    def test_the_house_model_is_offered(self, ashna) -> None:
        """`ashna-x1` مدل اختصاصی خود سرویس است."""
        assert "ashna-x1" in ashna.suggested_models

    def test_several_families_are_represented(self, ashna) -> None:
        """
        ارزش آشنا در چندمدلی بودن است؛ فهرست پیشنهادی باید این را
        نشان دهد نه اینکه فقط یک خانواده را بیاورد.
        """
        models = " ".join(ashna.suggested_models)

        assert "gpt" in models
        assert "claude" in models
        assert "gemini" in models

    @pytest.mark.parametrize(
        "model_id",
        [
            "ashna-x1",
            "gpt-4o-mini",
            "claude-sonnet-5",
            "gemini-3.1-Pro",
            "deepseek-v4-flash",
            "glm-5.3-flash",
            "kimi-k3",
            "grok-4.3",
        ],
    )
    def test_every_suggested_id_is_a_documented_catalog_id(
        self, ashna, model_id: str
    ) -> None:
        """
        هر شناسه باید عیناً از مستندات آشنا آمده باشد.

        شناسهٔ حدسی، خطای ۴۰۴ «مدل ناشناخته» می‌دهد و کاربر فکر می‌کند
        کلیدش خراب است.
        """
        assert model_id in ashna.suggested_models

    def test_no_vendor_prefix_is_used(self, ashna) -> None:
        """
        آشنا شناسهٔ ساده می‌خواهد (`gpt-4o-mini`)، نه سبک OpenRouter
        (`openai/gpt-4o-mini`). قاطی کردن این دو خطای رایجی است.
        """
        for model in ashna.suggested_models:
            assert "/" not in model


class TestAshnaTransport:
    """رفتار واقعی روی سیم، با یک سرور ساختگی."""

    @staticmethod
    def _provider(api_key: str | None, base_url: str):  # noqa: ANN205
        from ai.providers.base import AIProviderConfig
        from ai.providers.openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider(
            AIProviderConfig(name="ashna", model="ashna-x1", base_url=base_url),
            api_key=api_key,
        )

    def test_a_missing_key_fails_before_any_request(self) -> None:
        """
        بدون کلید نباید درخواستی برود.

        پیام باید دربارهٔ کلید باشد، نه یک خطای شبکهٔ گنگ.
        """
        import asyncio

        provider = self._provider(None, "https://api.ashna.ai/v1/api")
        available, message = asyncio.run(provider.is_available())

        assert available is False
        assert "key" in message.lower() or "کلید" in message
        asyncio.run(provider.close())

    def test_the_provider_accepts_an_agent_id_as_model(self) -> None:
        """
        آشنا اجازه می‌دهد شناسهٔ ایجنت سفارشی به‌جای نام مدل بیاید.

        پس نباید هیچ اعتبارسنجی‌ای مدل‌های ناشناس را رد کند.
        """
        from ai.providers.base import AIProviderConfig
        from ai.providers.openai_compatible import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider(
            AIProviderConfig(
                name="ashna",
                model="my-support-agent-8k2qv",
                base_url="https://api.ashna.ai/v1/api",
            ),
            api_key="test",
        )

        assert provider.model == "my-support-agent-8k2qv"


class TestAshnaAppearsInTheSettingsUI:
    """
    ثبت در کاتالوگ کافی نیست؛ کاربر باید واقعاً بتواند انتخابش کند.

    این آزمون همان چیزی را می‌سنجد که کاربر می‌بیند.
    """

    def test_the_provider_is_selectable_and_autofills(self, qt_application) -> None:  # noqa: ANN001, ARG002
        """انتخاب آشنا باید نشانی را خودکار پر کند و کادر کلید را باز کند."""
        from localization.translator import Translator
        from ui.pages.settings_page import SettingsPage

        page = SettingsPage(Translator())
        combo = page.ai_provider_combo
        index = next(
            i for i in range(combo.count()) if combo.itemData(i) == "ashna"
        )
        combo.setCurrentIndex(index)

        assert page.ai_base_url_input.text() == "https://api.ashna.ai/v1/api"
        assert page.ai_key_input.isEnabled() is True
        assert page.ai_model_combo.count() > 0


class TestTheBuildDoctor:
    """
    عیب‌یاب باید واقعیت دستگاه را گزارش کند، نه حدس بزند.

    این ابزار بعد از سه حدس اشتباه دربارهٔ ویندوز نوشته شد. ارزشش به
    این است که هر مشکل یک **چارهٔ مشخص** داشته باشد.
    """

    @staticmethod
    def _report():  # noqa: ANN205
        from tools.build_doctor import run_diagnosis

        return run_diagnosis()

    def test_the_diagnosis_runs_anywhere(self) -> None:
        """عیب‌یاب خودش نباید جایی بشکند — حتی وقتی همه‌چیز خراب است."""
        report = self._report()

        assert report.checks

    def test_every_failure_offers_a_concrete_fix(self) -> None:
        """
        «خطا رخ داد» بی‌فایده است.

        هر بررسی ناموفق باید بگوید کاربر دقیقاً چه کار کند.
        """
        from tools.build_doctor import FAIL

        for check in self._report().checks:
            if check.status == FAIL:
                assert check.fix, f"بررسی «{check.name}» بدون راه‌حل است"

    def test_the_first_problem_is_surfaced(self) -> None:
        """
        نمایش همهٔ خطاها با هم گیج‌کننده است.

        معمولاً خطاهای بعدی نتیجهٔ اولی‌اند.
        """
        report = self._report()

        if report.failures:
            assert report.first_problem is report.failures[0]
        else:
            assert report.first_problem is None

    def test_python_version_is_checked(self) -> None:
        """نسخهٔ پایتون رایج‌ترین علت شکست ساخت است."""
        names = [check.name for check in self._report().checks]

        assert any("پایتون" in name for name in names)

    def test_the_batch_files_are_inspected(self) -> None:
        """
        همان سه دامی که سازنده را بی‌صدا می‌بست باید بررسی شوند.
        """
        report = self._report()
        script_checks = [c for c in report.checks if ".bat" in c.name]

        assert len(script_checks) == 2
        assert all(check.status == "موفق" for check in script_checks)

    def test_a_healthy_tree_reports_the_scripts_as_sound(self) -> None:
        """اسکریپت‌های داخل آرشیو باید سالم تشخیص داده شوند."""
        from tools.build_doctor import OK

        report = self._report()
        installer = next(c for c in report.checks if "build_installer" in c.name)

        assert installer.status == OK

    def test_the_doctor_script_exists_and_is_windows_safe(self) -> None:
        """خود عیب‌یاب هم نباید قربانی همان دام‌ها شود."""
        from pathlib import Path

        data = (
            Path(__file__).resolve().parent.parent / "scripts" / "doctor.bat"
        ).read_bytes()

        assert b"pause" in data
        assert b"\r\n" in data
        assert b"chcp 65001" in data
