"""
سرویس حساب‌های صرافی کاربر.

زنجیرهٔ طراحی‌شده:
    ``Exchange Provider → Exchange Adapter → Exchange API → Application``

هیچ صرافی‌ای در این لایه سخت‌کد نشده است: نام صرافی از حساب کاربر خوانده
می‌شود و نمونهٔ ارائه‌دهنده از رجیستری ساخته می‌گردد. افزودن صرافی تازه
یعنی ثبت یک `ExchangeProvider` دیگر در رجیستری، نه تغییر این فایل.

امنیت:
    • کلید و رمز API فقط در Secret Store رمزنگاری‌شده می‌نشینند.
    • پایگاه داده تنها `secret_ref` و نسخهٔ پوشیدهٔ کلید را دارد.
    • مقدار خام هرگز لاگ یا در استثنا منعکس نمی‌شود؛ پیام خطاها پیش از
      انتشار پاک‌سازی می‌گردد.
"""

from __future__ import annotations

import inspect
import json
from typing import Any

from app.database.repositories.user_repository import ExchangeAccountRepository
from app.logging import get_logger
from app.security.passwords import mask_secret
from app.security.secret_store import SecretStore

logger = get_logger(__name__)

#: فضای نام رمزها در Secret Store
SECRET_NAMESPACE = "exchange_account"


def _sanitize(message: str, *secrets: str) -> str:
    """
    حذف هر نشانی از مقادیر حساس از یک پیام خطا.

    حتی اگر لایهٔ پایین اشتباهاً کلید را در پیام بگذارد، اینجا گرفته
    می‌شود — دفاع لایه‌ای.
    """
    text = str(message or "")
    for secret in secrets:
        if secret and len(secret) >= 6 and secret in text:
            text = text.replace(secret, "•••")
    return text


class ExchangeAccountService:
    """
    مدیریت اتصال کاربران به صرافی‌ها.

    نمونه‌سازی:
        service = ExchangeAccountService(repository, secret_store)
        service.add_account(user_id=1, exchange="lbank", api_key=..., api_secret=...)
    """

    def __init__(
        self,
        repository: ExchangeAccountRepository,
        secrets: SecretStore,
    ) -> None:
        self._repository = repository
        self._secrets = secrets

    # ------------------------------------------------------------------
    # خواندن
    # ------------------------------------------------------------------
    def list_accounts(self, user_id: int) -> list[dict[str, Any]]:
        """فهرست حساب‌های کاربر (بدون هیچ مقدار حساس)."""
        return self._repository.list_accounts(user_id)

    def get_account(self, account_id: int) -> dict[str, Any] | None:
        """یک حساب مشخص."""
        return self._repository.get_account(account_id)

    def default_account(self, user_id: int) -> dict[str, Any] | None:
        """حساب پیش‌فرض کاربر برای اتصال خودکار."""
        return self._repository.get_default_account(user_id)

    # ------------------------------------------------------------------
    # نوشتن
    # ------------------------------------------------------------------
    def add_account(
        self,
        *,
        user_id: int,
        exchange: str,
        api_key: str,
        api_secret: str,
        label: str = "",
        read_only: bool = True,
        make_default: bool = False,
        passphrase: str = "",
    ) -> dict[str, Any]:
        """
        افزودن حساب صرافی.

        ترتیب کار مهم است: نخست رکورد ساخته می‌شود تا شناسه به دست آید،
        سپس رمز با کلیدی مبتنی بر همان شناسه ذخیره می‌گردد. این‌طور هرگز
        دو حساب رمز یکدیگر را بازنویسی نمی‌کنند.
        """
        account = self._repository.create_account(
            user_id=user_id,
            exchange=exchange,
            label=label,
            api_key_plain=api_key,
            read_only=read_only,
            make_default=make_default,
        )
        reference = self._store_secret(
            account["id"], api_key=api_key, api_secret=api_secret, passphrase=passphrase
        )
        self._repository.update_credentials(
            account["id"], secret_ref=reference, api_key_plain=api_key
        )
        logger.info(
            "Exchange account added: id=%s exchange=%s (key masked: %s)",
            account["id"],
            account["exchange"],
            mask_secret(api_key),
        )
        return self._repository.get_account(account["id"]) or account

    def update_credentials(
        self, account_id: int, *, api_key: str, api_secret: str, passphrase: str = ""
    ) -> bool:
        """جایگزینی کلیدهای یک حساب موجود."""
        reference = self._store_secret(
            account_id, api_key=api_key, api_secret=api_secret, passphrase=passphrase
        )
        ok = self._repository.update_credentials(
            account_id, secret_ref=reference, api_key_plain=api_key
        )
        if ok:
            logger.info("Credentials updated for account id=%s", account_id)
        return ok

    def delete_account(self, account_id: int) -> bool:
        """
        حذف حساب و رمز متناظر آن.

        رمز هم پاک می‌شود تا چیزی در Secret Store یتیم نماند.
        """
        reference = self._repository.delete_account(account_id)
        if reference:
            self._secrets.delete(reference)
            logger.info("Exchange account removed: id=%s", account_id)
        return True

    def set_default(self, user_id: int, account_id: int) -> bool:
        """تعیین حساب پیش‌فرض."""
        return self._repository.set_default(user_id, account_id)

    def set_enabled(self, account_id: int, enabled: bool) -> bool:
        """فعال/غیرفعال کردن حساب."""
        return self._repository.set_enabled(account_id, enabled)

    # ------------------------------------------------------------------
    # اعتبارنامه‌ها
    # ------------------------------------------------------------------
    def credentials(self, account_id: int) -> dict[str, str]:
        """
        خواندن کلیدهای یک حساب از Secret Store.

        تنها لایهٔ صرافی مجاز است این متد را صدا بزند. خروجی هرگز نباید
        لاگ شود.
        """
        reference = self._repository.secret_ref(account_id)
        if not reference:
            return {}
        raw = self._secrets.get(reference)
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            logger.warning("Stored credentials for account id=%s are unreadable", account_id)
            return {}
        return {
            "api_key": str(data.get("api_key", "")),
            "api_secret": str(data.get("api_secret", "")),
            "passphrase": str(data.get("passphrase", "")),
        }

    def has_credentials(self, account_id: int) -> bool:
        """آیا برای این حساب رمزی ذخیره شده است؟"""
        return bool(self._repository.secret_ref(account_id))

    # ------------------------------------------------------------------
    # وضعیت و همگام‌سازی
    # ------------------------------------------------------------------
    async def test_connection(self, account_id: int, provider_factory) -> tuple[bool, str]:
        """
        آزمایش اتصال یک حساب.

        `provider_factory` یک فراخوان‌پذیر است که با
        `(exchange, api_key, api_secret)` صدا زده می‌شود و یک
        `ExchangeProvider` برمی‌گرداند؛ به این ترتیب این سرویس به هیچ
        صرافی مشخصی وابسته نیست و در تست هم می‌توان آداپتور جعلی داد.

        بازگشتی: `(موفقیت، پیام پاک‌سازی‌شده)`.
        """
        account = self._repository.get_account(account_id)
        if account is None:
            return False, "exchange.error.account_not_found"

        creds = self.credentials(account_id)
        if not creds.get("api_key"):
            self._repository.set_status(
                account_id, status="error", error="exchange.error.no_credentials"
            )
            return False, "exchange.error.no_credentials"

        provider = None
        try:
            provider = provider_factory(
                account["exchange"], creds["api_key"], creds["api_secret"]
            )
            ok, message = await provider.test_credentials()
            clean = _sanitize(message, creds["api_key"], creds["api_secret"])

            # دسترسی قرارداد جداگانه است: کلیدی که فقط مجوز اسپات دارد
            # اینجا «موفق» می‌گیرد ولی بعداً کیف پول فیوچرز خالی می‌ماند و
            # کاربر علتش را نمی‌فهمد. پس همان‌جا صریح گزارش می‌شود.
            if ok:
                fetch_futures = getattr(provider, "fetch_futures_balance", None)
                if callable(fetch_futures):
                    try:
                        await fetch_futures()
                    except Exception:  # noqa: BLE001
                        clean = f"{clean} (futures access unavailable)"
            self._repository.set_status(
                account_id,
                status="connected" if ok else "error",
                error="" if ok else clean,
                synced=ok,
            )
            return ok, clean
        except Exception as exc:  # noqa: BLE001 - هر خطایی باید پاک‌سازی شود
            clean = _sanitize(str(exc), creds["api_key"], creds["api_secret"])
            logger.warning("Connection test failed for account id=%s: %s", account_id, clean)
            self._repository.set_status(account_id, status="error", error=clean)
            return False, clean
        finally:
            if provider is not None:
                try:
                    await provider.close()
                except Exception:  # noqa: BLE001
                    pass

    async def sync_balances(
        self, account_id: int, provider_factory, *, price_lookup=None
    ) -> dict[str, Any]:
        """
        همگام‌سازی موجودی حساب.

        `price_lookup` اختیاری است و اگر داده شود برای تبدیل هر دارایی به
        ارزش تتری استفاده می‌گردد؛ نبودش فقط یعنی ارزش کل صفر می‌ماند.
        """
        account = self._repository.get_account(account_id)
        if account is None:
            return {}

        creds = self.credentials(account_id)
        if not creds.get("api_key"):
            return {}

        provider = None
        try:
            provider = provider_factory(
                account["exchange"], creds["api_key"], creds["api_secret"]
            )
            balances = await provider.get_account_balance()

            # موجودی فیوچرز جداست؛ بدون این، کاربری که سرمایه‌اش را به کیف
            # پول قراردادها منتقل کرده، کیف پول را تقریباً خالی می‌بیند.
            futures: dict[str, float] = {}
            fetch_futures = getattr(provider, "get_futures_balance", None)
            if callable(fetch_futures):
                try:
                    futures = await fetch_futures() or {}
                except Exception as exc:  # noqa: BLE001 - نبود فیوچرز خطا نیست
                    logger.info(
                        "Futures balance skipped for account id=%s: %s",
                        account_id,
                        exc.__class__.__name__,
                    )

            spot_only: dict[str, float] = dict(balances or {})
            combined: dict[str, float] = dict(balances or {})
            for asset, amount in futures.items():
                combined[asset] = combined.get(asset, 0.0) + float(amount or 0.0)
            balances = combined

            total = 0.0
            if price_lookup is not None:
                for asset, amount in (balances or {}).items():
                    try:
                        price = price_lookup(asset)
                        # قیمت‌یاب می‌تواند هم‌زمان یا ناهم‌زمان باشد؛ دومی
                        # لازم است تا برای رمزارزهای کم‌طرفدار که در جدول
                        # بازارها نیستند بتوان قیمت زنده گرفت.
                        if inspect.isawaitable(price):
                            price = await price
                        total += float(amount) * float(price)
                    except (TypeError, ValueError):
                        continue
            self._repository.update_balances(
                account_id,
                balances=balances or {},
                total_value_usdt=total,
                spot=spot_only,
                futures=futures,
            )
            return {
                "balances": balances or {},
                "total_value_usdt": total,
                "spot": dict(spot_only),
                "futures": dict(futures),
            }
        except Exception as exc:  # noqa: BLE001
            clean = _sanitize(str(exc), creds["api_key"], creds["api_secret"])
            logger.warning("Balance sync failed for account id=%s: %s", account_id, clean)
            self._repository.set_status(account_id, status="error", error=clean)
            return {}
        finally:
            if provider is not None:
                try:
                    await provider.close()
                except Exception:  # noqa: BLE001
                    pass

    # ------------------------------------------------------------------
    # داخلی
    # ------------------------------------------------------------------
    def _store_secret(
        self, account_id: int, *, api_key: str, api_secret: str, passphrase: str = ""
    ) -> str:
        """
        نوشتن اعتبارنامه در Secret Store و بازگرداندن کلید ارجاع.

        همه در یک مقدار JSON ذخیره می‌شوند تا با یک عملیات اتمی نوشته و
        پاک شوند.
        """
        reference = SecretStore.make_key(SECRET_NAMESPACE, str(account_id))
        payload = json.dumps(
            {
                "api_key": api_key or "",
                "api_secret": api_secret or "",
                "passphrase": passphrase or "",
            }
        )
        self._secrets.set(reference, payload)
        return reference


__all__ = ["SECRET_NAMESPACE", "ExchangeAccountService"]
