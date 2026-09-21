"""
آزمون مدیریت کاربر، رمز عبور و حساب‌های صرافی.

تمرکز اصلی روی امنیت است: رمز عبور و کلید API هرگز نباید به‌صورت متن
ساده ذخیره، برگردانده یا در پیام خطا ظاهر شوند.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config.settings_service import SettingsService
from app.core.auth_service import AuthService
from app.core.exchange_account_service import ExchangeAccountService
from app.database.models import Base
from app.database.repositories import (
    ExchangeAccountRepository,
    SettingsRepository,
    UserRepository,
)
from app.database.session import DatabaseManager
from app.security.passwords import (
    hash_password,
    hash_token,
    mask_secret,
    needs_rehash,
    password_strength,
    validate_password,
    verify_password,
)
from app.security.secret_store import EncryptedFileBackend, SecretStore


@pytest.fixture()
def database(tmp_path: Path) -> DatabaseManager:
    """پایگاه دادهٔ موقت برای هر آزمون."""
    manager = DatabaseManager(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(manager.engine)
    return manager


@pytest.fixture()
def users(database: DatabaseManager) -> UserRepository:
    """مخزن کاربران."""
    return UserRepository(database)


@pytest.fixture()
def auth(database: DatabaseManager, users: UserRepository) -> AuthService:
    """سرویس احراز هویت با تنظیمات موقت."""
    settings = SettingsService(SettingsRepository(database))
    settings.initialize_defaults()
    return AuthService(users, settings)


# ---------------------------------------------------------------------------
# رمز عبور
# ---------------------------------------------------------------------------
def test_password_hash_is_salted_and_verifiable() -> None:
    """چکیدهٔ رمز باید با نمک تصادفی ساخته و قابل راستی‌آزمایی باشد."""
    first = hash_password("CorrectHorse!7")
    second = hash_password("CorrectHorse!7")

    assert first.salt != second.salt, "نمک باید برای هر رمز تازه باشد"
    assert first.hash_value != second.hash_value
    assert "CorrectHorse!7" not in first.hash_value

    assert verify_password(
        "CorrectHorse!7",
        hash_value=first.hash_value,
        salt=first.salt,
        iterations=first.iterations,
    )
    assert not verify_password(
        "WrongPassword",
        hash_value=first.hash_value,
        salt=first.salt,
        iterations=first.iterations,
    )


def test_password_verification_never_raises_on_bad_input() -> None:
    """ورودی خراب باید «نادرست» بدهد نه استثنا — تا پیام خطا چیزی لو ندهد."""
    assert not verify_password("x", hash_value="", salt="", iterations=1)
    assert not verify_password("", hash_value="abc", salt="zz", iterations=1)
    assert not verify_password("x", hash_value="abc", salt="not-hex", iterations=1)


def test_iteration_count_is_current_and_upgradeable() -> None:
    """چکیدهٔ ضعیف قدیمی باید برای نوسازی علامت بخورد."""
    assert needs_rehash(1000) is True
    assert needs_rehash(390_000) is False


def test_password_policy_rejects_weak_values() -> None:
    """سیاست رمز باید مقادیر ضعیف را رد کند."""
    assert validate_password("123") == "auth.error.password_too_short"
    assert validate_password("12345678") == "auth.error.password_too_simple"
    assert validate_password("abcdefgh") == "auth.error.password_too_simple"
    assert validate_password("Good!pass1") is None
    assert password_strength("Good!pass12")[0] >= 3


def test_mask_secret_hides_the_middle() -> None:
    """پوشاندن باید ابتدا و انتها را نگه دارد و میانه را بپوشاند."""
    masked = mask_secret("abcdefghijklmnopqrstuvwxyz")
    assert masked.startswith("abcd")
    assert masked.endswith("wxyz")
    assert "efghijklmnop" not in masked
    # مقدار کوتاه کاملاً پوشانده می‌شود
    assert set(mask_secret("short")) == {"•"}
    assert mask_secret("") == ""


def test_session_token_is_stored_only_as_hash() -> None:
    """توکن نشست نباید قابل بازیابی از چکیده باشد."""
    token = "super-secret-session-token"
    digest = hash_token(token)
    assert token not in digest
    assert len(digest) == 64
    assert hash_token(token) == digest


# ---------------------------------------------------------------------------
# چرخهٔ کاربر
# ---------------------------------------------------------------------------
def test_user_dict_never_leaks_password_fields(users: UserRepository) -> None:
    """خروجی مخزن نباید چکیده یا نمک را بیرون بدهد."""
    user = users.create_user(username="hossein", password="Strong!pass1")
    for field in ("password_hash", "password_salt", "password_iterations"):
        assert field not in user


def test_duplicate_username_is_rejected(users: UserRepository) -> None:
    """نام کاربری تکراری (بدون توجه به بزرگی حروف) پذیرفته نمی‌شود."""
    users.create_user(username="hossein", password="Strong!pass1")
    with pytest.raises(ValueError, match="username_taken"):
        users.create_user(username="Hossein", password="Other!pass2")


def test_authenticate_returns_same_error_for_unknown_and_wrong(
    users: UserRepository,
) -> None:
    """
    پیام خطای «کاربر ناشناس» و «رمز نادرست» باید یکی باشد.

    در غیر این صورت می‌شود فهمید کدام نام کاربری وجود دارد.
    """
    users.create_user(username="hossein", password="Strong!pass1")
    _, unknown_error = users.authenticate("ghost", "whatever")
    _, wrong_error = users.authenticate("hossein", "whatever")
    assert unknown_error == wrong_error == "auth.error.invalid_credentials"


def test_account_locks_after_repeated_failures(users: UserRepository) -> None:
    """پس از پنج تلاش ناموفق حساب باید موقتاً قفل شود."""
    users.create_user(username="hossein", password="Strong!pass1")
    for _ in range(5):
        users.authenticate("hossein", "nope")
    user, error = users.authenticate("hossein", "Strong!pass1")
    assert user is None
    assert error == "auth.error.account_locked"


def test_change_password_revokes_sessions(users: UserRepository) -> None:
    """تغییر رمز باید همهٔ نشست‌ها را باطل کند."""
    user = users.create_user(username="hossein", password="Strong!pass1")
    users.create_session(user["id"], "token-1")
    assert users.resolve_session("token-1") is not None

    ok, error = users.change_password(
        user["id"], current_password="Strong!pass1", new_password="Another!pass9"
    )
    assert ok and not error
    assert users.resolve_session("token-1") is None
    assert users.authenticate("hossein", "Another!pass9")[0] is not None


def test_change_password_requires_correct_current(users: UserRepository) -> None:
    """بدون رمز فعلی درست نباید رمز عوض شود."""
    user = users.create_user(username="hossein", password="Strong!pass1")
    ok, error = users.change_password(
        user["id"], current_password="wrong", new_password="Another!pass9"
    )
    assert not ok
    assert error == "auth.error.wrong_current_password"


def test_expired_and_revoked_sessions_are_ignored(users: UserRepository) -> None:
    """نشست باطل‌شده نباید کاربر را وارد کند."""
    user = users.create_user(username="hossein", password="Strong!pass1")
    session_id = users.create_session(user["id"], "token-1")
    users.revoke_session(session_id)
    assert users.resolve_session("token-1") is None
    assert users.resolve_session("never-issued") is None


# ---------------------------------------------------------------------------
# سرویس احراز هویت
# ---------------------------------------------------------------------------
def test_guest_mode_is_default(auth: AuthService) -> None:
    """برنامه بدون ورود هم باید کار کند."""
    assert auth.is_authenticated is False
    assert auth.user_id is None
    assert auth.display_name == "auth.guest"


def test_register_login_logout_cycle(auth: AuthService) -> None:
    """چرخهٔ کامل ثبت‌نام، خروج و ورود دوباره."""
    user, error = auth.register("hossein", "Strong!pass1", display_name="حسین")
    assert user is not None and not error
    assert auth.is_authenticated
    assert user["is_admin"] is True, "نخستین کاربر باید مدیر باشد"

    auth.logout()
    assert not auth.is_authenticated

    again, error = auth.login("hossein", "Strong!pass1")
    assert again is not None and not error
    assert auth.display_name == "حسین"


def test_register_rejects_weak_password(auth: AuthService) -> None:
    """رمز ضعیف نباید حساب بسازد."""
    user, error = auth.register("someone", "123")
    assert user is None
    assert error == "auth.error.password_too_short"


def test_remember_me_restores_session(
    database: DatabaseManager, users: UserRepository
) -> None:
    """با «مرا به خاطر بسپار» اجرای بعدی برنامه باید کاربر را بشناسد."""
    settings = SettingsService(SettingsRepository(database))
    settings.initialize_defaults()

    first = AuthService(users, settings)
    first.register("hossein", "Strong!pass1", login_after=False)
    first.login("hossein", "Strong!pass1", remember=True)

    # نمونهٔ تازه = اجرای دوبارهٔ برنامه
    second = AuthService(users, settings)
    restored = second.restore_session()
    assert restored is not None
    assert restored["username"] == "hossein"


def test_logout_prevents_auto_login(
    database: DatabaseManager, users: UserRepository
) -> None:
    """پس از خروج، اجرای بعدی نباید خودکار وارد شود."""
    settings = SettingsService(SettingsRepository(database))
    settings.initialize_defaults()

    first = AuthService(users, settings)
    first.register("hossein", "Strong!pass1", login_after=False)
    first.login("hossein", "Strong!pass1", remember=True)
    first.logout()

    second = AuthService(users, settings)
    assert second.restore_session() is None


def test_theme_preference_is_per_user_and_survives_restart(
    database: DatabaseManager, users: UserRepository
) -> None:
    """
    پوستهٔ انتخابی کاربر باید در پروفایل او بماند.

    این همان چیزی است که کاربر خواسته: انتخاب پوسته پس از راه‌اندازی
    دوباره حفظ شود.
    """
    settings = SettingsService(SettingsRepository(database))
    settings.initialize_defaults()

    service = AuthService(users, settings)
    service.register("hossein", "Strong!pass1")
    service.set_preference("ui.theme", "corporate_navy")
    service.logout()

    fresh = AuthService(users, settings)
    fresh.login("hossein", "Strong!pass1")
    assert fresh.preference("ui.theme") == "corporate_navy"


def test_preferences_merge_instead_of_replacing(auth: AuthService) -> None:
    """ذخیرهٔ یک ترجیح نباید بقیه را پاک کند."""
    auth.register("hossein", "Strong!pass1")
    auth.set_preference("ui.theme", "violet_light")
    auth.set_preference("ui.language", "en")
    assert auth.preference("ui.theme") == "violet_light"
    assert auth.preference("ui.language") == "en"


# ---------------------------------------------------------------------------
# حساب‌های صرافی
# ---------------------------------------------------------------------------
@pytest.fixture()
def accounts(
    database: DatabaseManager, tmp_path: Path
) -> ExchangeAccountService:
    """سرویس حساب صرافی با انبارهٔ رمز رمزنگاری‌شدهٔ موقت."""
    store = SecretStore(EncryptedFileBackend(tmp_path / "secrets.enc"))
    return ExchangeAccountService(ExchangeAccountRepository(database), store)


def test_api_credentials_are_never_stored_in_plaintext(
    tmp_path: Path, database: DatabaseManager, users: UserRepository
) -> None:
    """
    کلید و رمز API نباید در فایل پایگاه داده به‌صورت متن ساده پیدا شوند.

    این آزمون مستقیماً بایت‌های فایل را می‌گردد — سخت‌گیرانه‌ترین شکل
    بررسی.
    """
    secrets_file = tmp_path / "secrets.enc"
    store = SecretStore(EncryptedFileBackend(secrets_file))
    service = ExchangeAccountService(ExchangeAccountRepository(database), store)

    user = users.create_user(username="hossein", password="Strong!pass1")
    api_key = "PUBLICKEY1234567890"
    api_secret = "PRIVATESECRET0987654321"
    service.add_account(
        user_id=user["id"], exchange="lbank", api_key=api_key, api_secret=api_secret
    )

    database.engine.dispose()
    database_bytes = Path(str(database.engine.url).replace("sqlite:///", "")).read_bytes()
    assert api_key.encode() not in database_bytes
    assert api_secret.encode() not in database_bytes

    if secrets_file.exists():
        assert api_secret.encode() not in secrets_file.read_bytes()


def test_credentials_roundtrip_through_secret_store(
    accounts: ExchangeAccountService, users: UserRepository
) -> None:
    """کلیدها باید دقیقاً همان‌طور که ذخیره شده‌اند برگردند."""
    user = users.create_user(username="hossein", password="Strong!pass1")
    account = accounts.add_account(
        user_id=user["id"],
        exchange="lbank",
        api_key="KEY1234567890ABCD",
        api_secret="SECRET1234567890",
    )
    credentials = accounts.credentials(account["id"])
    assert credentials["api_key"] == "KEY1234567890ABCD"
    assert credentials["api_secret"] == "SECRET1234567890"


def test_account_listing_exposes_only_masked_key(
    accounts: ExchangeAccountService, users: UserRepository
) -> None:
    """فهرست حساب‌ها نباید کلید کامل یا ارجاع رمز را بیرون بدهد."""
    user = users.create_user(username="hossein", password="Strong!pass1")
    accounts.add_account(
        user_id=user["id"],
        exchange="lbank",
        api_key="KEY1234567890ABCD",
        api_secret="SECRET1234567890",
    )
    listed = accounts.list_accounts(user["id"])[0]
    assert "secret_ref" not in listed
    assert "api_secret" not in listed
    assert listed["api_key_masked"].startswith("KEY1")
    assert "1234567890" not in listed["api_key_masked"]
    assert listed["has_credentials"] is True


def test_first_account_becomes_default(
    accounts: ExchangeAccountService, users: UserRepository
) -> None:
    """نخستین حساب باید خودکار پیش‌فرض شود تا برنامه بدون تنظیم کار کند."""
    user = users.create_user(username="hossein", password="Strong!pass1")
    first = accounts.add_account(
        user_id=user["id"], exchange="lbank", api_key="k" * 20, api_secret="s" * 20
    )
    assert first["is_default"] is True
    assert accounts.default_account(user["id"])["id"] == first["id"]


def test_deleting_account_purges_its_secret(
    accounts: ExchangeAccountService, users: UserRepository
) -> None:
    """حذف حساب باید رمز آن را هم پاک کند تا چیزی یتیم نماند."""
    user = users.create_user(username="hossein", password="Strong!pass1")
    account = accounts.add_account(
        user_id=user["id"], exchange="lbank", api_key="k" * 20, api_secret="s" * 20
    )
    accounts.delete_account(account["id"])
    assert accounts.credentials(account["id"]) == {}


@pytest.mark.asyncio()
async def test_connection_error_message_is_scrubbed(
    accounts: ExchangeAccountService, users: UserRepository
) -> None:
    """
    اگر لایهٔ صرافی کلید را در پیام خطا بگذارد، باید پاک‌سازی شود.

    دفاع لایه‌ای: حتی خطای بی‌دقتِ یک ارائه‌دهنده نباید کلید را لو دهد.
    """
    user = users.create_user(username="hossein", password="Strong!pass1")
    api_key = "LEAKYKEY1234567890"
    account = accounts.add_account(
        user_id=user["id"], exchange="lbank", api_key=api_key, api_secret="s" * 20
    )

    class LeakyProvider:
        """ارائه‌دهندهٔ ساختگی که کلید را در پیام خطا می‌گذارد."""

        async def test_credentials(self) -> tuple[bool, str]:
            return False, f"invalid signature for key {api_key}"

        async def close(self) -> None:
            return None

    ok, message = await accounts.test_connection(
        account["id"], lambda exchange, key, secret: LeakyProvider()
    )
    assert ok is False
    assert api_key not in message


@pytest.mark.asyncio()
async def test_balance_sync_updates_account(
    accounts: ExchangeAccountService, users: UserRepository
) -> None:
    """همگام‌سازی موجودی باید وضعیت و ارزش کل را ذخیره کند."""
    user = users.create_user(username="hossein", password="Strong!pass1")
    account = accounts.add_account(
        user_id=user["id"], exchange="lbank", api_key="k" * 20, api_secret="s" * 20
    )

    class Provider:
        """ارائه‌دهندهٔ ساختگی با موجودی ثابت."""

        async def get_account_balance(self) -> dict[str, float]:
            return {"USDT": 1000.0, "BTC": 0.5}

        async def close(self) -> None:
            return None

    result = await accounts.sync_balances(
        account["id"],
        lambda exchange, key, secret: Provider(),
        price_lookup=lambda asset: 1.0 if asset == "USDT" else 60_000.0,
    )
    assert result["total_value_usdt"] == pytest.approx(31_000.0)

    stored = accounts.get_account(account["id"])
    assert stored["status"] == "connected"
    assert stored["balances"]["BTC"] == 0.5
