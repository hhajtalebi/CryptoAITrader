"""
آزمون حساب کاربری حرفه‌ای، بازیابی رمز، اولاما و سیگنال‌گیری خودکار.

چهار خواستهٔ کاربر در این دور:
    ۱. ثبت‌نام با ایمیل و بازیابی رمز با کد تأیید
    ۲. رفع خطای «HTTP 500» اولاما
    ۳. پرکردن کادر خالی نوار کناری
    ۴. سیگنال‌گیری خودکار دوره‌ای

تمرکز آزمون‌ها روی رفتارهایی است که اگر بشکنند کاربر واقعاً آسیب
می‌بیند: بیرون ماندن از حساب خود، نشت کد بازیابی، و پویش‌های روی‌هم
انباشته که برنامه را خفه کنند.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.core.email_service import (
    SMTP_PRESETS,
    EmailService,
    SmtpConfig,
    is_valid_email,
    mask_email,
)
from app.core.password_reset import (
    CODE_LENGTH,
    MAX_ATTEMPTS,
    RESEND_COOLDOWN_SECONDS,
    PasswordResetService,
    generate_code,
)
from localization import Translator
from signals.auto_scanner import (
    MAX_INTERVAL_SECONDS,
    MIN_INTERVAL_SECONDS,
    AutoScanConfig,
    AutoScanScheduler,
    ScanJob,
    clamp_interval,
)

ARABIC_RANGE = re.compile(r"[\u0600-\u06ff]")
LOCALE_ROOT = Path(__file__).resolve().parents[1] / "localization"
BASE_TIME = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)


# ============================================================== ایمیل


def test_email_validation_accepts_real_addresses() -> None:
    """سخت‌گیری بیش از حد، نشانی‌های معتبر را رد می‌کند."""
    for address in ("a@b.co", "hossein.haj@gmail.com", "user+tag@sub.domain.ir"):
        assert is_valid_email(address), address
    for address in ("", "nope", "a@b", "a b@c.com", "@gmail.com"):
        assert not is_valid_email(address), address


def test_mask_email_hides_the_local_part() -> None:
    """نمایش کامل ایمیل به هر کسی که پشت دستگاه است، نشت اطلاعات است."""
    masked = mask_email("hossein@gmail.com")

    assert masked.endswith("@gmail.com")
    assert "hossein" not in masked


def test_every_preset_has_a_translation() -> None:
    """سرویسی که نامش ترجمه ندارد، در فهرست کشویی خام دیده می‌شود."""
    for language in ("fa", "en"):
        data = json.loads((LOCALE_ROOT / language / "email.json").read_text("utf-8"))
        for key in SMTP_PRESETS:
            assert key in data["presets"], (language, key)


def test_gmail_preset_uses_the_submission_port() -> None:
    """۵۸۷ با STARTTLS؛ اشتباه این عدد یعنی شکست خاموش اتصال."""
    preset = SMTP_PRESETS["gmail"]

    assert preset["host"] == "smtp.gmail.com"
    assert preset["port"] == 587
    assert preset["tls"] is True


def test_service_reports_not_configured_instead_of_crashing() -> None:
    """تنظیمات ناقص باید پیام بدهد، نه استثنا."""

    class Settings:
        def get(self, key, default=None):
            return {"email.smtp_port": 587}.get(key, default if default is not None else "")

    ok, error = EmailService(Settings(), None).send(
        to="x@y.com", subject="s", body="b"
    )

    assert not ok
    assert error == "email.error.not_configured"


def test_config_falls_back_to_username_as_sender() -> None:
    """اگر فرستنده جدا وارد نشود، همان حساب ایمیل فرستنده است."""
    config = SmtpConfig(
        host="smtp.gmail.com", port=587, username="me@gmail.com", password="x"
    )

    assert config.configured
    assert config.from_address == "me@gmail.com"


def test_config_without_password_is_not_usable() -> None:
    """نبود رمز یعنی ارسال ناممکن؛ نباید «آماده» گزارش شود."""
    config = SmtpConfig(host="smtp.gmail.com", port=587, username="me@gmail.com", password="")

    assert not config.configured


# ==================================================== بازیابی رمز عبور


class FakeUserRepo:
    """مخزن ساختگی با یک کاربر."""

    def __init__(self) -> None:
        self.reset_calls: list[tuple[int, str]] = []

    def find_by_email(self, email: str):
        if email.strip().lower() == "me@gmail.com":
            return {"id": 7, "username": "hossein", "display_name": "حسین"}
        return None

    def reset_password(self, user_id: int, password: str):
        self.reset_calls.append((int(user_id), password))
        return True, ""


class FakeEmail:
    """سرویس ایمیل ساختگی که پیام‌ها را نگه می‌دارد."""

    def __init__(self, *, configured: bool = True, works: bool = True) -> None:
        self.configured = configured
        self._works = works
        self.sent: list[tuple[str, str]] = []

    def send(self, *, to: str, subject: str, body: str):
        if not self._works:
            return False, "email.error.connection"
        self.sent.append((to, body))
        return True, ""


def extract_code(body: str) -> str:
    """بیرون کشیدن کد شش‌رقمی از متن ایمیل."""
    match = re.search(r"\b(\d{6})\b", body)
    assert match, body
    return match.group(1)


@pytest.fixture()
def reset_service() -> PasswordResetService:
    """سرویس بازیابی با ایمیل کارآمد."""
    return PasswordResetService(FakeUserRepo(), FakeEmail())


def test_generated_code_has_the_expected_shape() -> None:
    """کد باید همیشه شش رقم باشد، حتی وقتی عدد کوچک تولید شود."""
    for _ in range(50):
        code = generate_code()
        assert len(code) == CODE_LENGTH
        assert code.isdigit()


def test_happy_path_changes_the_password(reset_service) -> None:  # noqa: ANN001
    """جریان کامل: درخواست → کد → رمز تازه."""
    ok, _error, info = reset_service.request_code("me@gmail.com")
    assert ok and info["delivered"]

    code = extract_code(reset_service._email.sent[0][1])
    assert reset_service.verify_code("me@gmail.com", code) == (True, "")

    ok, error = reset_service.reset_password("me@gmail.com", code, "Str0ng!Passw0rd")

    assert ok, error
    assert reset_service._repository.reset_calls == [(7, "Str0ng!Passw0rd")]


def test_code_is_single_use(reset_service) -> None:  # noqa: ANN001
    """کد مصرف‌شده نباید دوباره کار کند."""
    reset_service.request_code("me@gmail.com")
    code = extract_code(reset_service._email.sent[0][1])
    reset_service.reset_password("me@gmail.com", code, "Str0ng!Passw0rd")

    ok, error = reset_service.reset_password("me@gmail.com", code, "An0ther!Pass")

    assert not ok
    assert error == "auth.error.reset_not_requested"


def test_unknown_email_does_not_reveal_itself(reset_service) -> None:  # noqa: ANN001
    """
    پاسخ برای ایمیل ناموجود هم باید موفق باشد.

    وگرنه این صفحه به ابزار فهرست‌برداری کاربران تبدیل می‌شود.
    """
    ok, error, _info = reset_service.request_code("nobody@gmail.com")

    assert ok
    assert error == ""
    assert reset_service._email.sent == []


def test_brute_force_burns_the_code(reset_service) -> None:  # noqa: ANN001
    """حدس‌زدن کد شش‌رقمی نباید با تکرار ممکن باشد."""
    reset_service.request_code("me@gmail.com")
    code = extract_code(reset_service._email.sent[0][1])

    for _ in range(MAX_ATTEMPTS):
        reset_service.verify_code("me@gmail.com", "000000")

    ok, error = reset_service.verify_code("me@gmail.com", code)

    assert not ok
    assert error == "auth.error.reset_not_requested"


def test_expired_code_is_refused(reset_service) -> None:  # noqa: ANN001
    """کد کهنه باید باطل باشد، هرچند درست تایپ شده باشد."""
    reset_service.request_code("me@gmail.com")
    code = extract_code(reset_service._email.sent[0][1])
    request = reset_service._requests["me@gmail.com"]
    request.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    ok, error = reset_service.verify_code("me@gmail.com", code)

    assert not ok
    assert error == "auth.error.reset_expired"


def test_resend_is_rate_limited(reset_service) -> None:  # noqa: ANN001
    """درخواست پشت‌سرهم نباید صندوق ایمیل کاربر را پر کند."""
    reset_service.request_code("me@gmail.com")

    ok, error, info = reset_service.request_code("me@gmail.com")

    assert not ok
    assert error == "auth.error.reset_too_soon"
    assert 0 < info["retry_after"] <= RESEND_COOLDOWN_SECONDS


def test_offline_fallback_returns_the_code() -> None:
    """
    بدون SMTP، کد باید درون برنامه در دسترس باشد.

    وگرنه کاربری که ایمیل تنظیم نکرده برای همیشه از حسابش بیرون می‌ماند.
    """
    service = PasswordResetService(FakeUserRepo(), FakeEmail(configured=False))

    ok, _error, info = service.request_code("me@gmail.com")

    assert ok
    assert not info["delivered"]
    assert len(info["offline_code"]) == CODE_LENGTH


def test_failed_delivery_falls_back_instead_of_locking_out() -> None:
    """اگر سرور ایمیل جواب ندهد، کاربر نباید بن‌بست بخورد."""
    service = PasswordResetService(FakeUserRepo(), FakeEmail(works=False))

    ok, _error, info = service.request_code("me@gmail.com")

    assert ok
    assert info["offline_code"]


def test_invalid_email_is_rejected_early(reset_service) -> None:  # noqa: ANN001
    """ایمیل بدشکل نباید حتی به مخزن برسد."""
    ok, error, _info = reset_service.request_code("not-an-email")

    assert not ok
    assert error == "auth.error.invalid_email"


def test_reset_keys_are_translated() -> None:
    """کلیدی که ترجمه ندارد، در بدترین لحظه خام دیده می‌شود."""
    source = Path("app/core/password_reset.py").read_text("utf-8")
    used = set(re.findall(r'"(auth\.error\.[a-z_]+)"', source))
    assert used

    for language in ("fa", "en"):
        translator = Translator(language)
        for key in used:
            text = translator.tr(key, seconds=5)
            assert text and text != key, (language, key)


def test_reset_dialog_texts_are_in_the_right_script() -> None:
    """فارسیِ فارسی، انگلیسیِ انگلیسی."""
    fa = json.loads((LOCALE_ROOT / "fa" / "auth.json").read_text("utf-8"))["reset"]
    en = json.loads((LOCALE_ROOT / "en" / "auth.json").read_text("utf-8"))["reset"]

    assert set(fa) == set(en)
    for value in fa.values():
        assert ARABIC_RANGE.search(value), value
    for value in en.values():
        assert not ARABIC_RANGE.search(value), value


# ================================================= سیگنال‌گیری خودکار


class FakeSignal:
    """سیگنال ساختگی با حداقل چیزی که زمان‌بند لازم دارد."""

    def __init__(self, symbol: str, confidence: float, direction: str = "LONG") -> None:
        self.symbol = symbol
        self.confidence = confidence
        self.direction = type("D", (), {"name": direction})()


@pytest.fixture()
def scheduler() -> AutoScanScheduler:
    """زمان‌بند با تنظیمات روشن و فهرست سه‌تایی."""
    config = AutoScanConfig(
        enabled=True,
        focus_interval=300,
        full_interval=1800,
        focus_size=3,
        focus_min_confidence=55,
    )
    return AutoScanScheduler(config.normalized())


def test_interval_is_clamped_to_a_sane_range() -> None:
    """
    فاصلهٔ صفر یا منفی حلقهٔ بی‌وقفه می‌سازد و صرافی کاربر را می‌بندد.
    """
    assert clamp_interval(0) > 0
    assert clamp_interval(-5) > 0
    assert clamp_interval(1) == MIN_INTERVAL_SECONDS
    assert clamp_interval(10 ** 9) == MAX_INTERVAL_SECONDS
    assert clamp_interval("nonsense") > 0


def test_disabled_scheduler_never_runs() -> None:
    """خاموش یعنی خاموش؛ هیچ ترافیکی نباید تولید شود."""
    idle = AutoScanScheduler(AutoScanConfig(enabled=False))

    assert idle.due(BASE_TIME) is None
    assert idle.seconds_until_next(BASE_TIME) == 0


def test_first_job_is_a_full_sweep(scheduler) -> None:  # noqa: ANN001
    """بدون فهرست تمرکز، باید از چرخش کامل شروع شود."""
    job = scheduler.due(BASE_TIME)

    assert job is not None
    assert job.kind == "full"


def test_full_sweep_builds_the_focus_list(scheduler) -> None:  # noqa: ANN001
    """
    فهرست تمرکز از نتیجهٔ چرخش کامل ساخته می‌شود.

    «انتظار» و ضریب پایین‌تر از آستانه نباید جای نماد واقعی را بگیرند.
    """
    job = scheduler.due(BASE_TIME)
    scheduler.start(job)

    focus = scheduler.complete(
        job,
        [
            FakeSignal("BTC/USDT", 80),
            FakeSignal("ETH/USDT", 72),
            FakeSignal("SOL/USDT", 60),
            FakeSignal("DOGE/USDT", 50),
            FakeSignal("XRP/USDT", 95, "WAIT"),
        ],
        BASE_TIME,
    )

    assert focus == ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    assert "DOGE/USDT" not in focus
    assert "XRP/USDT" not in focus


def test_focus_cycle_runs_on_the_selected_symbols(scheduler) -> None:  # noqa: ANN001
    """خواستهٔ صریح کاربر: نماد پراطمینان مکرر بررسی شود."""
    first = scheduler.due(BASE_TIME)
    scheduler.start(first)
    scheduler.complete(first, [FakeSignal("BTC/USDT", 80), FakeSignal("ETH/USDT", 70)], BASE_TIME)

    job = scheduler.due(BASE_TIME + timedelta(minutes=5))

    assert job is not None
    assert job.kind == "focus"
    assert set(job.symbols) == {"BTC/USDT", "ETH/USDT"}


def test_nothing_is_due_before_the_interval_elapses(scheduler) -> None:  # noqa: ANN001
    """پیش از رسیدن فاصله، نباید پویشی راه بیفتد."""
    job = scheduler.due(BASE_TIME)
    scheduler.start(job)
    scheduler.complete(job, [FakeSignal("BTC/USDT", 80)], BASE_TIME)

    assert scheduler.due(BASE_TIME + timedelta(minutes=2)) is None


def test_full_sweep_wins_over_focus_when_both_are_due(scheduler) -> None:  # noqa: ANN001
    """
    چرخش کامل اولویت دارد.

    فهرست تمرکز از آن ساخته می‌شود؛ عقب افتادنش یعنی دویدن روی داده‌های
    کهنه.
    """
    first = scheduler.due(BASE_TIME)
    scheduler.start(first)
    scheduler.complete(first, [FakeSignal("BTC/USDT", 80)], BASE_TIME)

    job = scheduler.due(BASE_TIME + timedelta(minutes=31))

    assert job.kind == "full"


def test_overlapping_cycles_are_skipped_not_queued(scheduler) -> None:  # noqa: ANN001
    """
    پویش کامل چند دقیقه طول می‌کشد.

    اگر نوبت‌ها صف شوند، برنامه زیر بار درخواست‌های روی‌هم خفه می‌شود.
    """
    scheduler.running = True

    assert scheduler.due(BASE_TIME + timedelta(hours=1)) is None
    assert scheduler.skipped == 1


def test_focus_list_is_reordered_not_emptied(scheduler) -> None:  # noqa: ANN001
    """
    نوسان لحظه‌ای نباید فهرست را خالی کند.

    نمادی که ضریبش افت کرده ته فهرست می‌رود، ولی بلافاصله حذف نمی‌شود.
    """
    first = scheduler.due(BASE_TIME)
    scheduler.start(first)
    scheduler.complete(
        first,
        [FakeSignal("BTC/USDT", 80), FakeSignal("ETH/USDT", 70), FakeSignal("SOL/USDT", 60)],
        BASE_TIME,
    )

    focus_job = scheduler.due(BASE_TIME + timedelta(minutes=5))
    scheduler.start(focus_job)
    scheduler.complete(focus_job, [FakeSignal("ETH/USDT", 90)], BASE_TIME + timedelta(minutes=5))

    assert scheduler.focus_symbols[0] == "ETH/USDT"
    assert "BTC/USDT" in scheduler.focus_symbols


def test_failure_still_advances_the_clock(scheduler) -> None:  # noqa: ANN001
    """
    قطعی شبکه نباید به تلاش هر ثانیه‌ای تبدیل شود.
    """
    job = scheduler.due(BASE_TIME)
    scheduler.start(job)
    scheduler.fail(job, BASE_TIME)

    assert not scheduler.running
    assert scheduler.due(BASE_TIME + timedelta(seconds=30)) is None


def test_countdown_reports_remaining_seconds(scheduler) -> None:  # noqa: ANN001
    """شمارش معکوس روی صفحه باید عدد واقعی نشان دهد."""
    job = scheduler.due(BASE_TIME)
    scheduler.start(job)
    scheduler.complete(job, [FakeSignal("BTC/USDT", 80)], BASE_TIME)

    remaining = scheduler.seconds_until_next(BASE_TIME + timedelta(minutes=2))

    assert remaining == pytest.approx(180, abs=1)


def test_shrinking_focus_size_applies_immediately(scheduler) -> None:  # noqa: ANN001
    """تغییر تنظیمات باید فوراً اثر کند، نه در چرخهٔ بعد."""
    job = scheduler.due(BASE_TIME)
    scheduler.start(job)
    scheduler.complete(
        job,
        [FakeSignal("BTC/USDT", 80), FakeSignal("ETH/USDT", 75), FakeSignal("SOL/USDT", 70)],
        BASE_TIME,
    )

    scheduler.apply_config(AutoScanConfig(enabled=True, focus_size=1))

    assert len(scheduler.focus_symbols) == 1


def test_reset_clears_state(scheduler) -> None:  # noqa: ANN001
    """پس از تعویض صرافی، نمادهای قبلی بی‌معنا هستند."""
    job = scheduler.due(BASE_TIME)
    scheduler.start(job)
    scheduler.complete(job, [FakeSignal("BTC/USDT", 80)], BASE_TIME)

    scheduler.reset()

    assert scheduler.focus_symbols == []
    assert scheduler.due(BASE_TIME).kind == "full"


def test_config_reads_every_setting_key() -> None:
    """هر کلید تنظیمات باید واقعاً خوانده شود، وگرنه گزینه بی‌اثر است."""

    class Settings:
        def __init__(self):
            self.read: list[str] = []

        def get(self, key, default=None):
            self.read.append(key)
            return default

    settings = Settings()
    AutoScanConfig.from_settings(settings)

    expected = {
        "signals.auto_scan_enabled",
        "signals.auto_scan_interval",
        "signals.auto_scan_full_sweep",
        "signals.auto_scan_full_interval",
        "signals.auto_scan_focus_size",
        "signals.auto_scan_min_confidence",
        "signals.auto_scan_sweep_limit",
        "signals.auto_scan_only_visible",
    }
    assert expected <= set(settings.read)


def test_auto_scan_defaults_are_registered() -> None:
    """کلید بدون پیش‌فرض، هنگام خواندن خطا می‌دهد."""
    from app.config.defaults import DEFAULT_SETTINGS

    for key in (
        "signals.auto_scan_enabled",
        "signals.auto_scan_interval",
        "signals.auto_scan_full_sweep",
        "signals.auto_scan_full_interval",
        "signals.auto_scan_focus_size",
        "signals.auto_scan_min_confidence",
        "signals.auto_scan_notify",
    ):
        assert key in DEFAULT_SETTINGS, key


def test_auto_scan_is_off_by_default() -> None:
    """
    پویش خودکار پهنای باند و سهمیهٔ صرافی مصرف می‌کند.

    روشن بودنش باید انتخاب آگاهانهٔ کاربر باشد، نه پیش‌فرض خاموشِ نصب.
    """
    from app.config.defaults import DEFAULT_SETTINGS

    assert DEFAULT_SETTINGS["signals.auto_scan_enabled"] is False


def test_auto_scan_locale_keys_match() -> None:
    """کلید جامانده یعنی متن خام وسط رابط فارسی."""
    fa = json.loads((LOCALE_ROOT / "fa" / "signals.json").read_text("utf-8"))["auto"]
    en = json.loads((LOCALE_ROOT / "en" / "signals.json").read_text("utf-8"))["auto"]

    assert set(fa) == set(en)
    for value in fa.values():
        assert ARABIC_RANGE.search(value), value


def test_scheduler_reasons_have_translations() -> None:
    """دلیل پویش به کاربر نشان داده می‌شود و باید ترجمه داشته باشد."""
    translator = Translator("fa")
    for reason in ("auto.reason_focus", "auto.reason_full_sweep", "auto.reason_bootstrap"):
        key = f"signals.{reason}"
        assert translator.tr(key) != key, key


# ======================================================== اولاما


def test_num_ctx_follows_the_prompt_length() -> None:
    """
    پنجره با طول پرامپت رشد می‌کند، ولی تا سقف حافظهٔ دستگاه.

    نسخهٔ قبلی این آزمون عدد ثابت ۴۰۹۶ را برای پرسش کوتاه مطالبه
    می‌کرد. آن عدد از رفتار `ollama run` در ترمینال گرفته شده بود، نه
    از یک اصل. اصل درست این است: پنجره به‌اندازهٔ نیاز، و هرگز
    بزرگ‌تر از توان دستگاه.
    """
    from ai.providers.base import AIMessage, AIProviderConfig
    from ai.providers.ollama_provider import OllamaProvider

    provider = OllamaProvider(
        AIProviderConfig(name="ollama", model="deepseek-r1:8b", max_tokens=1600)
    )
    provider._context_ceiling = 16384

    short = provider._num_ctx([AIMessage(role="user", content="قیمت الان چند است؟")])
    long = provider._num_ctx([AIMessage(role="user", content="x" * 12000)])

    assert long > short
    assert short <= 4096
    assert long <= 16384


def test_memory_errors_are_recognised() -> None:
    """پیام «HTTP 500» به‌تنهایی عیب‌یابی را ناممکن می‌کند."""
    from ai.providers.ollama_provider import _looks_like_memory

    assert _looks_like_memory("model requires more system memory (9.1 GiB)")
    assert _looks_like_memory("cudaMalloc failed: out of memory")
    assert not _looks_like_memory("invalid model name")


def test_error_body_is_extracted_from_json_and_text() -> None:
    """اولاما گاهی JSON می‌دهد و گاهی متن خام؛ هر دو باید خوانده شود."""
    from ai.providers.ollama_provider import _response_error

    class JsonResponse:
        text = "{}"

        def json(self):
            return {"error": "model requires more system memory"}

    class TextResponse:
        text = "  upstream connect error  "

        def json(self):
            raise ValueError("not json")

    assert _response_error(JsonResponse()) == "model requires more system memory"
    assert _response_error(TextResponse()) == "upstream connect error"


def test_http_error_message_names_the_real_cause() -> None:
    """کاربر باید بفهمد چه کند، نه فقط اینکه «۵۰۰ شد»."""
    from ai.providers.base import AIProviderConfig
    from ai.providers.ollama_provider import OllamaProvider

    provider = OllamaProvider(AIProviderConfig(name="ollama", model="deepseek-r1:8b"))

    class Response:
        status_code = 500
        text = "{}"

        def json(self):
            return {"error": "model requires more system memory (9.1 GiB)"}

    message = provider._describe_http_error(Response(), "deepseek-r1:8b")

    assert "memory" in message.lower()
    assert "deepseek-r1:8b" in message
    assert message != "Ollama returned HTTP 500"
