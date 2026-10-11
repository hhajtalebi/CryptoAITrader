"""
برچسبِ منبعِ نتیجه و پوشاندنِ داده‌های حساس — نسخهٔ ۲.۷.۱.

دو تعهد کاربر:
    ۱. در صفحهٔ سیگنال/تحلیل باید روشن باشد نتیجه از «هوش مصنوعی» آمده
       یا از «موتور ریاضی» یا منبع دیگر؛ و هیچ خروجیِ موتور پشتیبان نباید
       با برچسب خروجیِ مدل نمایش داده شود.
    ۲. کلیدها و رمزها هرگز — نه در رابط کاربری، نه در لاگ — دیده نشوند.

این فایل هر دو را قفل می‌کند. برای بخش رابط کاربری، متدِ کنترلر را روی یک
بدلِ بسیار سبک صدا می‌زنیم (ساخت MainWindow کامل در هر آزمون، مجموعه را
دقایق کند می‌کرد).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.logging.logger import SensitiveDataFilter
from localization.translator import Translator

ROOT = Path(__file__).resolve().parents[1]
MASK = "***REDACTED***"


# ----------------------------------------------------------------------
# ۱. منبع نتیجه
# ----------------------------------------------------------------------
class _FakeLabel:
    """بدلِ یک QLabel ساده: فقط متن نگه می‌دارد."""

    def __init__(self) -> None:
        self._text = ""

    def text(self) -> str:
        return self._text

    def setText(self, value: str) -> None:  # noqa: N802 - امضای Qt
        self._text = str(value)

    def show(self) -> None:
        """بی‌اثر؛ فقط برای شباهت به Qt."""


def _controller(language: str = "fa") -> Any:
    """یک MainController با حداقل اعضای لازم برای متدِ برچسبِ منبع."""

    from ui.controllers.main_controller import MainController

    controller = MainController.__new__(MainController)
    controller.tr_ = Translator(language)
    controller.signals = SimpleNamespace(agent_trail=_FakeLabel())
    return controller


def _outcome(*, source: str, model: str = "", provider: str = "") -> Any:
    return SimpleNamespace(source=source, model=model, provider=provider)


def MainController_announce(controller: Any, outcome: Any) -> None:
    """فراخوانی متدِ واقعیِ کنترلر روی نمونهٔ بدل."""

    from ui.controllers.main_controller import MainController

    MainController._announce_signal_origin(controller, outcome)


@pytest.mark.parametrize("language", ["fa", "en"])
def test_ai_result_is_labelled_with_the_model_that_answered(language: str) -> None:
    """خروجی واقعیِ مدل باید با نام همان مدل برچسب بخورد."""

    controller = _controller(language)
    MainController_announce(controller, _outcome(source="ai", model="llama3.2:3b", provider="ollama"))
    text = controller.signals.agent_trail.text()
    assert text, "هیچ برچسبی نمایش داده نشد"
    assert "llama3.2:3b" in text, f"نام مدل در برچسب نیست: {text}"
    assert "REDACTED" not in text


@pytest.mark.parametrize("language", ["fa", "en"])
def test_engine_result_is_never_labelled_as_ai(language: str) -> None:
    """
    خروجی موتور پشتیبان نباید هیچ نشانی از «هوش مصنوعی»/«مدل» داشته باشد.

    این دقیقاً همان تعهدی است که اگر شکسته شود، کاربر به خروجیِ ریاضی
    اعتباری می‌دهد که ندارد.
    """

    controller = _controller(language)
    MainController_announce(controller, _outcome(source="fallback", model="", provider=""))
    text = controller.signals.agent_trail.text()
    translator = Translator(language)
    assert text, "هیچ برچسبی نمایش داده نشد"
    # برچسب باید دقیقاً برچسبِ موتور باشد، نه برچسبِ هوش مصنوعی.
    assert text == translator.tr("signals.origin_engine"), (
        f"برچسب نادرست برای خروجی موتور: {text}"
    )
    ai_label = translator.tr("signals.origin_ai", model="llama3.2:3b")
    assert text != ai_label
    assert "llama" not in text, "نام مدل روی خروجی موتور آمده است"


def test_previous_trail_is_preserved_alongside_the_origin_label() -> None:
    """برچسبِ منبع باید کنار مسیرِ ابزارها نشان داده شود، نه به‌جای آن."""

    controller = _controller("fa")
    controller.signals.agent_trail.setText("✓ trend · ✓ rsi")
    MainController_announce(controller, _outcome(source="ai", model="qwen2.5:7b"))
    text = controller.signals.agent_trail.text()
    assert "✓ trend" in text, "مسیر ابزارها پاک شد"
    assert "qwen2.5:7b" in text


def test_agent_payload_carries_source_and_trace_id() -> None:
    """قالبِ سیگنال باید منبع و شناسهٔ ردیابی را همراه داشته باشد."""

    from ui.controllers.main_controller import MainController

    controller = MainController.__new__(MainController)
    outcome = SimpleNamespace(
        decision={"entry_min": 100.0, "entry_max": 101.0, "stop_loss": 98.0, "take_profits": [104.0]},
        direction="LONG", confidence=70, narrative=None, provider="ollama",
        model="llama3.2:3b", source="fallback", trace_id="tr-1234567890",
    )
    payload = MainController._agent_outcome_to_signal(controller, outcome, "BTC/USDT", "1h")
    assert payload["source"] == "fallback", "منبع در قالب سیگنال نیست"
    assert payload["trace_id"] == "tr-1234567890", "شناسهٔ ردیابی در قالب سیگنال نیست"
    assert payload["ai_provider"] == "ollama"


# ----------------------------------------------------------------------
# ۲. کلیدها و رمزها
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "sample",
    [
        "api_key=ABCD1234SECRET",
        "apiKey: 'sk-live-abcdef123456'",
        'api_secret="zzzYYYxxx111"',
        "secret: mysecretvalue",
        "Authorization: Bearer abcdef1234567890",
        "sk-abcdefghijklmnop",
        '{"passphrase": "MyPassphrase123"}',
        "x-api-key: XYZ987654321",
        '{"token": "a1b2c3d4e5f6g7h8i9j0"}',
    ],
)
def test_secrets_are_masked_in_log_text(sample: str) -> None:
    """هر کلید/رمز/توکن در هر قالبی که باشد باید پوشانده شود."""

    masked = SensitiveDataFilter.mask(sample)
    assert MASK in masked, f"مقدار حساس پوشانده نشد: {sample}"


@pytest.mark.parametrize(
    "sample",
    [
        "max_tokens: 1600 and prompt_tokens=11",
        "prompt_eval_count: 42, eval_count: 120",
        "Ollama generation completed in 12.4s (model=qwen2.5:7b)",
        "connecting to https://127.0.0.1:11434/api/chat",
        "signal BTC/USDT LONG confidence=72",
    ],
)
def test_ordinary_log_text_is_not_mangled(sample: str) -> None:
    """ماسک نباید متن‌های عادی برنامه را خراب کند (هشدار کاذب ممنوع)."""

    assert SensitiveDataFilter.mask(sample) == sample, f"متن عادی تغییر کرد: {sample}"


def test_masking_covers_log_arguments_not_only_the_message() -> None:
    """مقدار حساس ممکن است در آرگومان‌های لاگ باشد، نه در قالب پیام."""

    import logging

    from app.logging.logger import SensitiveDataFilter

    record = logging.LogRecord("t", logging.INFO, __file__, 1, "key=%s", ("api_key=SUPERSECRET123",), None)
    SensitiveDataFilter().filter(record)
    assert MASK in str(record.args[0])


# ----------------------------------------------------------------------
# ۳. یکپارچگی بستهٔ زبان
# ----------------------------------------------------------------------
def test_new_origin_keys_exist_in_every_language_pack() -> None:
    """کلیدهای تازه باید در هر دو بستهٔ زبان باشند و پارامتر یکسان بگیرند."""

    data: dict[str, dict[str, Any]] = {}
    for language in ("fa", "en"):
        path = ROOT / "localization" / language / "signals.json"
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict) and loaded, f"{path.name} بارگذاری نشد"
        assert "origin_ai" in loaded and "origin_engine" in loaded, (
            f"{path.name}: کلید منبع نیست"
        )
        data[language] = loaded

    assert "{model}" in data["fa"]["origin_ai"]
    assert "{model}" in data["en"]["origin_ai"], (
        "نسخهٔ انگلیسی پارامتر مدل را ندارد؛ ترجمه ناقص است"
    )
