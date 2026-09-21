"""
مخزن کاربران، نشست‌ها و حساب‌های صرافی.

الگوی خروجی: مانند `ChatRepository` همهٔ متدها دیکشنری برمی‌گردانند نه
شیء ORM، تا خارج از `session` خطای `DetachedInstanceError` رخ ندهد.

امنیت:
    • رمز عبور فقط به‌صورت چکیدهٔ PBKDF2 ذخیره می‌شود.
    • توکن نشست به‌صورت چکیدهٔ SHA-256 ذخیره می‌شود.
    • کلید و رمز API هرگز در این جدول‌ها نوشته نمی‌شوند؛ فقط `secret_ref`
      که کلید جستجو در Secret Store رمزنگاری‌شده است.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select

from app.database.models import ExchangeAccountRecord, UserRecord, UserSessionRecord
from app.database.repositories.base import BaseRepository
from app.logging import get_logger
from app.security.passwords import (
    DEFAULT_ITERATIONS,
    hash_password,
    hash_token,
    mask_secret,
    needs_rehash,
    validate_password,
    verify_password,
)

logger = get_logger(__name__)

#: بیشترین تلاش ناموفق پیش از قفل موقت حساب
MAX_FAILED_ATTEMPTS = 5

#: مدت قفل حساب پس از تلاش‌های ناموفق (دقیقه)
LOCKOUT_MINUTES = 10

#: عمر پیش‌فرض نشست (روز)
SESSION_DAYS = 30


def _utcnow() -> datetime:
    """زمان جاری UTC بدون منطقهٔ زمانی (هم‌شکل با ستون‌های DateTime)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _user_to_dict(record: UserRecord) -> dict[str, Any]:
    """
    تبدیل رکورد کاربر به دیکشنری امن.

    هیچ‌یک از فیلدهای رمز (چکیده، نمک) در خروجی نیست تا به‌طور تصادفی در
    رابط کاربری یا لاگ ظاهر نشود.
    """
    return {
        "id": record.id,
        "username": record.username,
        "email": record.email,
        "display_name": record.display_name or record.username,
        "is_active": record.is_active,
        "is_admin": record.is_admin,
        "preferences": dict(record.preferences or {}),
        "last_login_at": record.last_login_at,
        "created_at": record.created_at,
        "is_locked": bool(record.locked_until and record.locked_until > _utcnow()),
    }


def _account_to_dict(record: ExchangeAccountRecord) -> dict[str, Any]:
    """تبدیل حساب صرافی به دیکشنری؛ `secret_ref` بیرون داده نمی‌شود."""
    return {
        "id": record.id,
        "user_id": record.user_id,
        "exchange": record.exchange,
        "label": record.label,
        "api_key_masked": record.api_key_masked,
        "has_credentials": bool(record.secret_ref),
        "is_default": record.is_default,
        "enabled": record.enabled,
        "read_only": record.read_only,
        "status": record.status,
        "last_sync_at": record.last_sync_at,
        "last_error": record.last_error,
        "balances": dict(record.balances or {}),
        "total_value_usdt": record.total_value_usdt,
        "permissions": list(record.permissions or []),
        # تفکیک اسپات/فیوچرز اینجاست؛ بدون بیرون‌دادنش ستون «کیف پول»
        # همیشه خالی می‌ماند. رمزی در این ساختار ذخیره نمی‌شود.
        "extra_config": dict(record.extra_config or {}),
        "created_at": record.created_at,
    }


class UserRepository(BaseRepository[UserRecord]):
    """ثبت‌نام، ورود، پروفایل و ترجیحات کاربران."""

    model = UserRecord

    # ------------------------------------------------------------------
    # ثبت‌نام و بازیابی
    # ------------------------------------------------------------------
    def create_user(
        self,
        *,
        username: str,
        password: str,
        email: str = "",
        display_name: str = "",
        is_admin: bool = False,
        preferences: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        ساخت کاربر تازه.

        اگر نام کاربری تکراری باشد `ValueError` با کلید ترجمه پرتاب
        می‌شود تا لایهٔ بالاتر پیام محلی نشان دهد.
        """
        name = (username or "").strip().lower()
        if not name:
            raise ValueError("auth.error.username_required")

        digest = hash_password(password)
        with self._db.session_scope() as session:
            exists = session.execute(
                select(func.count()).select_from(UserRecord).where(UserRecord.username == name)
            ).scalar_one()
            if exists:
                raise ValueError("auth.error.username_taken")

            # ایمیل باید یکتا باشد وگرنه بازیابی رمز نمی‌داند کدام حساب را
            # بازگرداند. «بدون ایمیل» همچنان مجاز است.
            address = (email or "").strip()
            if address:
                taken = session.execute(
                    select(func.count())
                    .select_from(UserRecord)
                    .where(func.lower(UserRecord.email) == address.lower())
                ).scalar_one()
                if taken:
                    raise ValueError("auth.error.email_taken")

            record = UserRecord(
                username=name,
                email=(email or "").strip(),
                display_name=(display_name or "").strip() or name,
                password_hash=digest.hash_value,
                password_salt=digest.salt,
                password_iterations=digest.iterations,
                password_algorithm=digest.algorithm,
                is_admin=is_admin,
                preferences=dict(preferences or {}),
            )
            session.add(record)
            session.flush()
            logger.info("User created: %s", name)
            return _user_to_dict(record)

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        """یافتن کاربر با نام کاربری."""
        name = (username or "").strip().lower()
        with self._db.session_scope() as session:
            record = session.execute(
                select(UserRecord).where(UserRecord.username == name)
            ).scalar_one_or_none()
            return _user_to_dict(record) if record else None

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        """یافتن کاربر با شناسه."""
        with self._db.session_scope() as session:
            record = session.get(UserRecord, int(user_id))
            return _user_to_dict(record) if record else None

    def list_users(self) -> list[dict[str, Any]]:
        """فهرست همهٔ کاربران بر پایهٔ نام."""
        with self._db.session_scope() as session:
            records = session.execute(
                select(UserRecord).order_by(UserRecord.username)
            ).scalars().all()
            return [_user_to_dict(item) for item in records]

    def count_users(self) -> int:
        """شمار کاربران ثبت‌شده."""
        with self._db.session_scope() as session:
            return int(
                session.execute(select(func.count()).select_from(UserRecord)).scalar_one()
            )

    # ------------------------------------------------------------------
    # احراز هویت
    # ------------------------------------------------------------------
    def authenticate(self, username: str, password: str) -> tuple[dict[str, Any] | None, str]:
        """
        بررسی نام کاربری و رمز.

        بازگشتی: `(کاربر یا None, کلید ترجمهٔ خطا)`.

        شناسه می‌تواند **نام کاربری، ایمیل یا نام نمایشی** باشد. کاربر
        هنگام ثبت‌نام هر سه را وارد می‌کند و طبیعی است بعداً با ایمیل یا
        نام خودش وارد شود؛ پیش‌تر فقط نام کاربری پذیرفته می‌شد و کاربر
        با اطلاعات درست هم نمی‌توانست وارد شود.

        برای جلوگیری از حدس‌زدن نام کاربری، خطای «کاربر ناشناس» و «رمز
        نادرست» یکسان است. پس از چند تلاش ناموفق حساب موقتاً قفل می‌شود.
        """
        raw = (username or "").strip()
        name = raw.lower()
        with self._db.session_scope() as session:
            record = session.execute(
                select(UserRecord).where(UserRecord.username == name)
            ).scalar_one_or_none()

            if record is None and "@" in raw:
                # ورود با ایمیل (بدون حساسیت به بزرگی و کوچکی حروف)
                record = session.execute(
                    select(UserRecord).where(func.lower(UserRecord.email) == name)
                ).scalar_one_or_none()

            if record is None and raw:
                # ورود با نام نمایشی؛ فقط اگر دقیقاً یک نفر با آن نام باشد
                matches = session.execute(
                    select(UserRecord).where(func.lower(UserRecord.display_name) == name)
                ).scalars().all()
                if len(matches) == 1:
                    record = matches[0]

            if record is None:
                return None, "auth.error.invalid_credentials"
            if not record.is_active:
                return None, "auth.error.account_disabled"
            if record.locked_until and record.locked_until > _utcnow():
                return None, "auth.error.account_locked"

            ok = verify_password(
                password,
                hash_value=record.password_hash,
                salt=record.password_salt,
                iterations=record.password_iterations,
                algorithm=record.password_algorithm,
            )
            if not ok:
                record.failed_attempts = int(record.failed_attempts or 0) + 1
                if record.failed_attempts >= MAX_FAILED_ATTEMPTS:
                    record.locked_until = _utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
                    logger.warning("Account locked after failed attempts: %s", name)
                return None, "auth.error.invalid_credentials"

            # ورود موفق — در صورت قدیمی بودن پارامترها، چکیده نوسازی می‌شود
            if needs_rehash(record.password_iterations, record.password_algorithm):
                fresh = hash_password(password, iterations=DEFAULT_ITERATIONS)
                record.password_hash = fresh.hash_value
                record.password_salt = fresh.salt
                record.password_iterations = fresh.iterations
                record.password_algorithm = fresh.algorithm

            record.failed_attempts = 0
            record.locked_until = None
            record.last_login_at = _utcnow()
            session.flush()
            return _user_to_dict(record), ""

    def change_password(
        self, user_id: int, *, current_password: str, new_password: str
    ) -> tuple[bool, str]:
        """
        تغییر رمز عبور با تأیید رمز فعلی.

        همهٔ نشست‌های دیگر پس از تغییر رمز باطل می‌شوند — رفتار مورد
        انتظار از یک برنامهٔ امن.
        """
        with self._db.session_scope() as session:
            record = session.get(UserRecord, int(user_id))
            if record is None:
                return False, "auth.error.user_not_found"
            if not verify_password(
                current_password,
                hash_value=record.password_hash,
                salt=record.password_salt,
                iterations=record.password_iterations,
                algorithm=record.password_algorithm,
            ):
                return False, "auth.error.wrong_current_password"

            digest = hash_password(new_password)
            record.password_hash = digest.hash_value
            record.password_salt = digest.salt
            record.password_iterations = digest.iterations
            record.password_algorithm = digest.algorithm

            session.execute(
                delete(UserSessionRecord).where(UserSessionRecord.user_id == record.id)
            )
            logger.info("Password changed for user id=%s", user_id)
            return True, ""

    def find_by_email(self, email: str) -> dict[str, Any] | None:
        """
        یافتن کاربر از روی ایمیل، برای بازیابی رمز.

        مقایسه بی‌توجه به بزرگی و کوچکی حروف است چون کسی که ایمیلش را
        `Ali@Gmail.com` ثبت کرده، هنگام بازیابی `ali@gmail.com` می‌نویسد.
        """
        address = (email or "").strip().lower()
        if not address:
            return None
        with self._db.session_scope() as session:
            record = session.execute(
                select(UserRecord).where(func.lower(UserRecord.email) == address)
            ).scalar_one_or_none()
            return self._to_dict(record) if record is not None else None

    def reset_password(self, user_id: int, new_password: str) -> tuple[bool, str]:
        """
        نشاندن رمز تازه **بدون** دانستن رمز قبلی.

        فقط پس از تأیید کد بازیابی صدا زده می‌شود؛ خودِ این متد هویت را
        بررسی نمی‌کند، پس هرگز نباید مستقیماً به رابط کاربری وصل شود.
        همهٔ نشست‌ها باطل می‌شوند تا اگر کسی به حساب دسترسی داشته، بیرون
        بیفتد — که کل هدف بازیابی رمز است.
        """
        problem = validate_password(new_password)
        if problem:
            return False, problem

        with self._db.session_scope() as session:
            record = session.get(UserRecord, int(user_id))
            if record is None:
                return False, "auth.error.user_not_found"

            digest = hash_password(new_password)
            record.password_hash = digest.hash_value
            record.password_salt = digest.salt
            record.password_iterations = digest.iterations
            record.password_algorithm = digest.algorithm
            # قفلِ ناشی از تلاش‌های ناموفق هم باید برداشته شود، وگرنه
            # کاربر رمز را عوض می‌کند و باز هم نمی‌تواند وارد شود.
            record.failed_attempts = 0
            record.locked_until = None

            session.execute(
                delete(UserSessionRecord).where(UserSessionRecord.user_id == record.id)
            )
            logger.info("Password reset for user id=%s", user_id)
            return True, ""

    # ------------------------------------------------------------------
    # پروفایل و ترجیحات
    # ------------------------------------------------------------------
    def update_profile(
        self,
        user_id: int,
        *,
        display_name: str | None = None,
        email: str | None = None,
    ) -> bool:
        """به‌روزرسانی نام نمایشی و رایانامه."""
        with self._db.session_scope() as session:
            record = session.get(UserRecord, int(user_id))
            if record is None:
                return False
            if display_name is not None:
                record.display_name = display_name.strip()
            if email is not None:
                address = email.strip()
                if address:
                    taken = session.execute(
                        select(func.count())
                        .select_from(UserRecord)
                        .where(
                            func.lower(UserRecord.email) == address.lower(),
                            UserRecord.id != record.id,
                        )
                    ).scalar_one()
                    if taken:
                        raise ValueError("auth.error.email_taken")
                record.email = address
            return True

    def get_preferences(self, user_id: int) -> dict[str, Any]:
        """خواندن ترجیحات کاربر (پوسته، زبان، منطقه زمانی، اعلان‌ها)."""
        with self._db.session_scope() as session:
            record = session.get(UserRecord, int(user_id))
            return dict(record.preferences or {}) if record else {}

    def set_preferences(self, user_id: int, values: dict[str, Any]) -> bool:
        """
        ادغام ترجیحات تازه با ترجیحات موجود.

        ادغام (نه جایگزینی) تا تنظیم‌های ذخیره‌شدهٔ کاربر پاک نشود.
        """
        with self._db.session_scope() as session:
            record = session.get(UserRecord, int(user_id))
            if record is None:
                return False
            merged = dict(record.preferences or {})
            merged.update(values or {})
            record.preferences = merged
            return True

    def set_active(self, user_id: int, active: bool) -> bool:
        """فعال یا غیرفعال کردن حساب."""
        with self._db.session_scope() as session:
            record = session.get(UserRecord, int(user_id))
            if record is None:
                return False
            record.is_active = bool(active)
            return True

    # ------------------------------------------------------------------
    # نشست‌ها
    # ------------------------------------------------------------------
    def create_session(
        self, user_id: int, token: str, *, device_label: str = "", days: int = SESSION_DAYS
    ) -> int:
        """ثبت نشست تازه؛ فقط چکیدهٔ توکن ذخیره می‌شود."""
        with self._db.session_scope() as session:
            record = UserSessionRecord(
                user_id=int(user_id),
                token_hash=hash_token(token),
                device_label=device_label or "",
                expires_at=_utcnow() + timedelta(days=int(days)),
            )
            session.add(record)
            session.flush()
            return int(record.id)

    def resolve_session(self, token: str) -> dict[str, Any] | None:
        """
        یافتن کاربر یک نشست معتبر.

        نشست باطل‌شده یا منقضی نادیده گرفته می‌شود.
        """
        if not token:
            return None
        digest = hash_token(token)
        with self._db.session_scope() as session:
            record = session.execute(
                select(UserSessionRecord).where(UserSessionRecord.token_hash == digest)
            ).scalar_one_or_none()
            if record is None or record.revoked:
                return None
            if record.expires_at and record.expires_at < _utcnow():
                return None
            record.last_seen_at = _utcnow()
            user = session.get(UserRecord, record.user_id)
            if user is None or not user.is_active:
                return None
            return _user_to_dict(user)

    def list_sessions(self, user_id: int) -> list[dict[str, Any]]:
        """فهرست نشست‌های فعال کاربر برای صفحهٔ امنیت."""
        with self._db.session_scope() as session:
            records = session.execute(
                select(UserSessionRecord)
                .where(UserSessionRecord.user_id == int(user_id))
                .order_by(UserSessionRecord.last_seen_at.desc())
            ).scalars().all()
            return [
                {
                    "id": item.id,
                    "device_label": item.device_label,
                    "created_at": item.created_at,
                    "last_seen_at": item.last_seen_at,
                    "expires_at": item.expires_at,
                    "revoked": item.revoked,
                }
                for item in records
            ]

    def revoke_session(self, session_id: int) -> bool:
        """باطل‌کردن یک نشست مشخص."""
        with self._db.session_scope() as session:
            record = session.get(UserSessionRecord, int(session_id))
            if record is None:
                return False
            record.revoked = True
            return True

    def revoke_all_sessions(self, user_id: int) -> int:
        """باطل‌کردن همهٔ نشست‌های کاربر (خروج از همهٔ دستگاه‌ها)."""
        with self._db.session_scope() as session:
            result = session.execute(
                delete(UserSessionRecord).where(UserSessionRecord.user_id == int(user_id))
            )
            return int(result.rowcount or 0)

    def purge_expired_sessions(self) -> int:
        """پاک‌سازی نشست‌های منقضی — در راه‌اندازی برنامه صدا زده می‌شود."""
        with self._db.session_scope() as session:
            result = session.execute(
                delete(UserSessionRecord).where(UserSessionRecord.expires_at < _utcnow())
            )
            return int(result.rowcount or 0)


class ExchangeAccountRepository(BaseRepository[ExchangeAccountRecord]):
    """حساب‌های صرافی هر کاربر."""

    model = ExchangeAccountRecord

    def create_account(
        self,
        *,
        user_id: int,
        exchange: str,
        label: str = "",
        secret_ref: str = "",
        api_key_plain: str = "",
        read_only: bool = True,
        make_default: bool = False,
    ) -> dict[str, Any]:
        """
        ثبت حساب صرافی تازه.

        `api_key_plain` فقط برای ساختن نسخهٔ پوشیده استفاده می‌شود و
        ذخیره نمی‌گردد؛ مقدار واقعی باید پیش‌تر در Secret Store نوشته شده
        و `secret_ref` به آن اشاره کند.
        """
        with self._db.session_scope() as session:
            record = ExchangeAccountRecord(
                user_id=int(user_id),
                exchange=(exchange or "").strip().lower(),
                label=(label or "").strip() or (exchange or "").strip().lower(),
                secret_ref=secret_ref or "",
                api_key_masked=mask_secret(api_key_plain),
                read_only=bool(read_only),
                status="disconnected",
            )
            session.add(record)
            session.flush()

            if make_default:
                self._clear_defaults(session, user_id, keep=record.id)
                record.is_default = True
            else:
                other = session.execute(
                    select(func.count())
                    .select_from(ExchangeAccountRecord)
                    .where(ExchangeAccountRecord.user_id == int(user_id))
                ).scalar_one()
                if other == 1:
                    record.is_default = True

            logger.info(
                "Exchange account created: user=%s exchange=%s", user_id, record.exchange
            )
            return _account_to_dict(record)

    def list_accounts(self, user_id: int) -> list[dict[str, Any]]:
        """فهرست حساب‌های یک کاربر."""
        with self._db.session_scope() as session:
            records = session.execute(
                select(ExchangeAccountRecord)
                .where(ExchangeAccountRecord.user_id == int(user_id))
                .order_by(
                    ExchangeAccountRecord.is_default.desc(), ExchangeAccountRecord.exchange
                )
            ).scalars().all()
            return [_account_to_dict(item) for item in records]

    def get_account(self, account_id: int) -> dict[str, Any] | None:
        """یافتن یک حساب با شناسه."""
        with self._db.session_scope() as session:
            record = session.get(ExchangeAccountRecord, int(account_id))
            return _account_to_dict(record) if record else None

    def get_default_account(self, user_id: int) -> dict[str, Any] | None:
        """
        حساب پیش‌فرض کاربر.

        اگر هیچ حسابی پیش‌فرض نباشد، نخستین حساب فعال برگردانده می‌شود تا
        برنامه بدون پیکربندی اضافی کار کند.
        """
        with self._db.session_scope() as session:
            stmt = (
                select(ExchangeAccountRecord)
                .where(
                    ExchangeAccountRecord.user_id == int(user_id),
                    ExchangeAccountRecord.enabled.is_(True),
                )
                .order_by(ExchangeAccountRecord.is_default.desc(), ExchangeAccountRecord.id)
            )
            record = session.execute(stmt).scalars().first()
            return _account_to_dict(record) if record else None

    def secret_ref(self, account_id: int) -> str:
        """
        خواندن ارجاع رمز.

        تنها نقطه‌ای که `secret_ref` بیرون می‌آید؛ سرویس صرافی با آن مقدار
        واقعی را از Secret Store می‌گیرد.
        """
        with self._db.session_scope() as session:
            record = session.get(ExchangeAccountRecord, int(account_id))
            return record.secret_ref if record else ""

    def update_credentials(
        self, account_id: int, *, secret_ref: str, api_key_plain: str
    ) -> bool:
        """به‌روزرسانی ارجاع رمز و نسخهٔ پوشیدهٔ کلید."""
        with self._db.session_scope() as session:
            record = session.get(ExchangeAccountRecord, int(account_id))
            if record is None:
                return False
            record.secret_ref = secret_ref or ""
            record.api_key_masked = mask_secret(api_key_plain)
            record.status = "disconnected"
            return True

    def set_status(
        self,
        account_id: int,
        *,
        status: str,
        error: str = "",
        synced: bool = False,
    ) -> bool:
        """
        ثبت وضعیت اتصال.

        پیام خطا پیش از ذخیره پوشانده نمی‌شود چون هرگز نباید حاوی کلید
        باشد؛ لایهٔ صرافی موظف است پیام تمیز بدهد.
        """
        with self._db.session_scope() as session:
            record = session.get(ExchangeAccountRecord, int(account_id))
            if record is None:
                return False
            record.status = status
            record.last_error = error or ""
            if synced:
                record.last_sync_at = _utcnow()
            return True

    def update_balances(
        self,
        account_id: int,
        *,
        balances: dict[str, Any],
        total_value_usdt: float = 0.0,
        spot: dict[str, Any] | None = None,
        futures: dict[str, Any] | None = None,
    ) -> bool:
        """
        ذخیرهٔ خلاصهٔ دارایی‌ها برای نمایش آفلاین.

        تفکیک اسپات/فیوچرز در `extra_config` نگهداری می‌شود تا ستون تازه
        و مهاجرت لازم نشود؛ کاربر باید بداند کدام بخش موجودی کجاست.
        """
        with self._db.session_scope() as session:
            record = session.get(ExchangeAccountRecord, int(account_id))
            if record is None:
                return False
            if spot is not None or futures is not None:
                config = dict(record.extra_config or {})
                config["balances_by_wallet"] = {
                    "spot": dict(spot or {}),
                    "futures": dict(futures or {}),
                }
                record.extra_config = config
            record.balances = dict(balances or {})
            record.total_value_usdt = float(total_value_usdt or 0.0)
            record.last_sync_at = _utcnow()
            record.status = "connected"
            record.last_error = ""
            return True

    def set_default(self, user_id: int, account_id: int) -> bool:
        """تعیین حساب پیش‌فرض کاربر."""
        with self._db.session_scope() as session:
            record = session.get(ExchangeAccountRecord, int(account_id))
            if record is None or record.user_id != int(user_id):
                return False
            self._clear_defaults(session, user_id, keep=account_id)
            record.is_default = True
            return True

    def set_enabled(self, account_id: int, enabled: bool) -> bool:
        """فعال یا غیرفعال کردن حساب."""
        with self._db.session_scope() as session:
            record = session.get(ExchangeAccountRecord, int(account_id))
            if record is None:
                return False
            record.enabled = bool(enabled)
            return True

    def delete_account(self, account_id: int) -> str:
        """
        حذف حساب.

        بازگشتی: `secret_ref` حذف‌شده تا فراخوان بتواند رمز متناظر را هم
        از Secret Store پاک کند و چیزی جا نماند.
        """
        with self._db.session_scope() as session:
            record = session.get(ExchangeAccountRecord, int(account_id))
            if record is None:
                return ""
            reference = record.secret_ref
            session.delete(record)
            return reference

    @staticmethod
    def _clear_defaults(session, user_id: int, *, keep: int | None = None) -> None:
        """برداشتن پرچم پیش‌فرض از سایر حساب‌های همان کاربر."""
        records = session.execute(
            select(ExchangeAccountRecord).where(
                ExchangeAccountRecord.user_id == int(user_id),
                ExchangeAccountRecord.is_default.is_(True),
            )
        ).scalars().all()
        for item in records:
            if keep is None or item.id != keep:
                item.is_default = False


__all__ = ["ExchangeAccountRepository", "UserRepository"]
