"""
آزمون‌های عیب‌یاب اولاما و نجات از مرگ اجراکننده (نسخهٔ ۱٫۹٫۱۰).

چرا این فایل وجود دارد؟
    سه نسخه پشت سر هم علت «در ترمینال کار می‌کند، در برنامه نه» را
    حدس زدم. علت ریشه‌ای همیشه یکی بود: دستگاه کاربر را نمی‌بینم.
    عیب‌یاب به‌جای حدس اندازه می‌گیرد، و این آزمون‌ها تضمین می‌کنند
    گزارشش درست تفسیر شود.
"""

from __future__ import annotations

import pytest

from ai.ollama_doctor import DoctorReport, StepResult


class TestTheVerdictMatchesTheEvidence:
    """نتیجه‌گیری باید دقیقاً از شواهد بیاید، نه از حدس."""

    def test_an_unreachable_service_is_reported_as_offline(self) -> None:
        """اگر سرویس بالا نباشد، بقیهٔ تشخیص بی‌معناست."""
        report = DoctorReport(reachable=False)

        assert report.verdict_key == "settings.doctor.verdict_offline"

    def test_no_models_is_its_own_diagnosis(self) -> None:
        """سرویس بالا ولی بدون مدل، مشکل دیگری است."""
        report = DoctorReport(reachable=True, models=[])

        assert report.verdict_key == "settings.doctor.verdict_no_models"

    def test_failing_the_lightest_step_blames_ollama_not_the_app(self) -> None:
        """
        اگر «سلام» هم شکست بخورد، برنامه بی‌گناه است.

        این تمایز مهم است: کاربر نباید دنبال تنظیمات برنامه بگردد وقتی
        خود اولاما یا درایور خراب است.
        """
        report = DoctorReport(
            reachable=True,
            models=["llama3.1:8b"],
            steps=[StepResult(key="tiny", prompt_chars=4, ok=False, status=500)],
        )

        assert report.verdict_key == "settings.doctor.verdict_broken_service"

    def test_failing_only_under_load_is_a_capacity_problem(self) -> None:
        """
        درخواست سبک موفق، سنگین شکست ⇒ مدل زیر بار دوام نمی‌آورد.

        این دقیقاً وضعیت کاربر است: `ollama run` با پرامپت کوچک کار
        می‌کند، برنامه با پرامپت بزرگ نه.
        """
        report = DoctorReport(
            reachable=True,
            models=["llama3.1:8b"],
            steps=[
                StepResult(key="tiny", prompt_chars=4, ok=True),
                StepResult(key="tiny_predict", prompt_chars=4, ok=True),
                StepResult(key="system", prompt_chars=1754, ok=True),
                StepResult(key="full", prompt_chars=8581, ok=False, status=500),
            ],
        )

        assert report.verdict_key == "settings.doctor.verdict_load_limit"

    def test_all_steps_passing_means_look_elsewhere(self) -> None:
        """اگر همه‌چیز سالم بود، نباید الکی مقصر بتراشیم."""
        report = DoctorReport(
            reachable=True,
            models=["llama3.1:8b"],
            steps=[
                StepResult(key="tiny", prompt_chars=4, ok=True),
                StepResult(key="full", prompt_chars=8581, ok=True),
            ],
        )

        assert report.verdict_key == "settings.doctor.verdict_healthy"


class TestCpuOffloadDetection:
    """
    تشخیص سرریز به پردازنده.

    کارت کاربر ۲ گیگابایت است و هیچ‌کدام از چهار مدلش در آن جا
    نمی‌شود؛ دیدن این واقعیت مهم‌تر از هر حدسی است.
    """

    def test_a_split_model_is_detected(self) -> None:
        """مدلی که فقط بخشی در VRAM است، باید گزارش شود."""
        report = DoctorReport(
            loaded=[{"name": "llama3.1:8b", "size": 5.4e9, "size_vram": 1.2e9}]
        )

        assert report.cpu_offload_detected is True

    def test_a_fully_resident_model_is_not_flagged(self) -> None:
        """هشدار روی حالت سالم، کاربر را به بی‌اعتنایی عادت می‌دهد."""
        report = DoctorReport(
            loaded=[{"name": "llama3.2:3b", "size": 2.0e9, "size_vram": 2.0e9}]
        )

        assert report.cpu_offload_detected is False

    def test_nothing_loaded_is_not_a_warning(self) -> None:
        """حافظهٔ خالی یعنی هنوز چیزی اجرا نشده، نه اینکه مشکلی هست."""
        assert DoctorReport(loaded=[]).cpu_offload_detected is False


class TestTheStepsMirrorTheRealApp:
    """پله‌ها باید شکل واقعی درخواست برنامه را داشته باشند."""

    def test_the_steps_grow_from_light_to_heavy(self) -> None:
        """
        ترتیب مهم است: اگر سنگین اول بیاید، نمی‌فهمیم سبک سالم بود.
        """
        from ai.ollama_doctor import _steps

        sizes = [
            sum(len(m["content"]) for m in messages)
            for _, messages, _ in _steps("llama3.1:8b")
        ]

        assert sizes == sorted(sizes), sizes
        assert sizes[0] < 100, "پلهٔ اول باید واقعاً سبک باشد"
        assert sizes[-1] > 5000, "پلهٔ آخر باید بار واقعی برنامه را داشته باشد"

    def test_the_system_step_matches_the_real_prompt_size(self) -> None:
        """
        پیام سیستمی نمونه باید هم‌اندازهٔ پیام واقعی برنامه باشد.

        پیام واقعی با ۱۴ ابزار حدود ۱۲۲۲ توکن است؛ اگر نمونه خیلی
        کوچک‌تر باشد، عیب‌یاب مشکل را بازتولید نمی‌کند و بی‌فایده است.
        """
        from ai.ollama_doctor import _SYSTEM_SAMPLE
        from ai.prompt_budget import estimate_tokens

        assert 800 <= estimate_tokens(_SYSTEM_SAMPLE) <= 1800


class TestTheDoctorNeverRaises:
    """
    عیب‌یاب هرگز نباید خودش بشکند.

    ابزاری که هنگام خرابی می‌شکند، دقیقاً وقتی بی‌فایده است که بیش از
    همیشه لازم است.
    """

    @pytest.mark.asyncio
    async def test_an_unreachable_host_returns_a_report_not_an_error(self) -> None:
        """نشانی خاموش باید گزارش بدهد، نه استثنا."""
        from ai.ollama_doctor import run_diagnosis

        report = await run_diagnosis("http://127.0.0.1:1")

        assert report.reachable is False
        assert report.verdict_key == "settings.doctor.verdict_offline"


class TestEveryDoctorStringIsTranslated:
    """هیچ رشتهٔ سخت‌کدشده‌ای در رابط کاربری مجاز نیست."""

    def test_both_languages_define_the_same_keys(self) -> None:
        """کلید گمشده یعنی متن خام انگلیسی در رابط فارسی."""
        import json
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent / "localization"
        fa = json.loads((root / "fa" / "settings.json").read_text(encoding="utf-8"))
        en = json.loads((root / "en" / "settings.json").read_text(encoding="utf-8"))

        assert set(fa["doctor"]) == set(en["doctor"])

    def test_every_verdict_key_has_a_translation(self) -> None:
        """هر نتیجه‌گیری ممکن باید متن داشته باشد."""
        import json
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent / "localization"
        fa = json.loads((root / "fa" / "settings.json").read_text(encoding="utf-8"))

        for verdict in (
            "verdict_offline",
            "verdict_no_models",
            "verdict_healthy",
            "verdict_broken_service",
            "verdict_load_limit",
        ):
            assert fa["doctor"].get(verdict), verdict

    def test_every_step_has_a_label(self) -> None:
        """هر پله در گزارش با نام نمایش داده می‌شود."""
        import json
        from pathlib import Path

        from ai.ollama_doctor import _steps

        root = Path(__file__).resolve().parent.parent / "localization"
        fa = json.loads((root / "fa" / "settings.json").read_text(encoding="utf-8"))

        for key, _, _ in _steps("m"):
            assert fa["doctor"].get(f"step_{key}"), key
