"""
کلاینت HTTP صرافی Toobit.

امضای درخواست‌های خصوصی: HMAC-SHA256 روی رشتهٔ پرس‌وجو، با کلید مخفی
به‌عنوان کلید و خروجی **هگزادسیمال با حروف کوچک**. مستندات صرافی صریح
می‌گوید امضا حساس به بزرگی حروف است و نباید بزرگ باشد — برخلاف LBank که
MD5 را با حروف بزرگ می‌خواهد.

امنیت: کلید و رمز هرگز لاگ نمی‌شوند. پیام خطاها پیش از ثبت در لاگ از
پارامترهای حساس پاک می‌شوند.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.exceptions import (
    AuthenticationError,
    ExchangeError,
    NetworkError,
    RateLimitError,
    TimeoutErrorApp,
)
from app.logging import get_logger
from market.providers.toobit.constants import (
    TOOBIT_API_KEY_HEADER,
    TOOBIT_ERROR_CODES,
    TOOBIT_REST_URL,
)

logger = get_logger(__name__)

#: پارامترهایی که هرگز نباید در لاگ دیده شوند
_SENSITIVE_PARAMS = ("signature", "api_key", "apiKey", "accessKey")


#: الگوی یافتن پارامترهای حساس؛ با regex نوشته شده چون جایگزینی درجا
#: با حلقه، نشانه را باقی می‌گذارد و حلقه بی‌پایان می‌شود.
_SENSITIVE_RE = re.compile(
    r"(?i)\b(" + "|".join(_SENSITIVE_PARAMS) + r")=([^&\s\"']*)"
)


def _scrub(text: str) -> str:
    """حذف مقادیر حساس از متن پیش از لاگ‌کردن."""
    return _SENSITIVE_RE.sub(lambda match: f"{match.group(1)}=***", text)


class ToobitRestClient:
    """کلاینت REST با پشتیبانی از درخواست‌های عمومی و امضادار."""

    def __init__(
        self,
        *,
        base_url: str = TOOBIT_REST_URL,
        api_key: str | None = None,
        api_secret: str | None = None,
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or ""
        self._api_secret = api_secret or ""
        self._timeout = timeout
        self._max_retries = max(1, int(max_retries))
        self._http: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # چرخه عمر
    # ------------------------------------------------------------------
    async def connect(self) -> None:
        """ساخت کلاینت HTTP در صورت نبود."""
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={"Accept": "application/json"},
            )

    async def close(self) -> None:
        """بستن اتصال‌ها."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _client(self) -> httpx.AsyncClient:
        """دسترسی تنبل به کلاینت."""
        if self._http is None:
            await self.connect()
        assert self._http is not None
        return self._http

    @property
    def has_credentials(self) -> bool:
        """آیا کلید و رمز تنظیم شده‌اند؟"""
        return bool(self._api_key and self._api_secret)

    # ------------------------------------------------------------------
    # درخواست عمومی
    # ------------------------------------------------------------------
    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """
        درخواست GET عمومی با تلاش مجدد روی خطاهای گذرا.

        خطای دائمی (مثل نماد نامعتبر) تکرار نمی‌شود؛ تکرار آن فقط وقت
        کاربر را تلف می‌کند.
        """
        client = await self._client()
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = await client.get(endpoint, params=params or {})
                return self._unwrap(response, endpoint)
            except httpx.TimeoutException as exc:
                last_error = TimeoutErrorApp(f"Request timed out: {endpoint}")
                logger.debug("Toobit timeout (%s/%s)", attempt + 1, self._max_retries)
            except httpx.HTTPError as exc:
                last_error = NetworkError(f"Network error while calling {endpoint}")
                logger.debug("Toobit network error: %s", _scrub(str(exc)))
            except (AuthenticationError, ValueError):
                raise
            if attempt + 1 < self._max_retries:
                await _sleep_backoff(attempt)
        raise last_error or NetworkError(f"Request failed: {endpoint}")

    # ------------------------------------------------------------------
    # درخواست امضادار
    # ------------------------------------------------------------------
    def _sign(self, params: dict[str, Any]) -> str:
        """
        ساخت امضای HMAC-SHA256 روی رشتهٔ پرس‌وجو.

        ترتیب پارامترها باید دقیقاً همانی باشد که ارسال می‌شود؛ پس امضا
        روی همان رشته‌ای ساخته می‌شود که در URL می‌رود.
        """
        query = urlencode(params)
        digest = hmac.new(
            self._api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return digest.lower()

    async def get_signed(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """
        درخواست GET امضادار.

        اگر کلید تنظیم نشده باشد، پیش از تماس شبکه خطا می‌دهیم تا کاربر
        پیام روشن بگیرد نه خطای مبهم صرافی.
        """
        if not self.has_credentials:
            raise AuthenticationError(
                "Toobit API credentials are not configured",
                user_key="errors.authentication",
            )
        payload = dict(params or {})
        payload["timestamp"] = int(time.time() * 1000)
        payload.setdefault("recvWindow", 5000)
        payload["signature"] = self._sign(payload)

        client = await self._client()
        try:
            response = await client.get(
                endpoint,
                params=payload,
                headers={TOOBIT_API_KEY_HEADER: self._api_key},
            )
        except httpx.TimeoutException as exc:
            raise TimeoutErrorApp(f"Signed request timed out: {endpoint}") from exc
        except httpx.HTTPError as exc:
            raise NetworkError(f"Network error while calling {endpoint}") from exc
        return self._unwrap(response, endpoint, signed=True)

    # ------------------------------------------------------------------
    # بازکردن پاسخ
    # ------------------------------------------------------------------
    def _unwrap(self, response: httpx.Response, endpoint: str, *, signed: bool = False) -> Any:
        """
        بررسی پاسخ و بیرون کشیدن داده.

        Toobit خطاها را هم با کد HTTP و هم با `code`/`msg` در بدنه اعلام
        می‌کند؛ هر دو بررسی می‌شوند.
        """
        if response.status_code in (418, 429):
            # 429 = درخواست زیاد، 418 = مسدودی موقت IP. تکرار فوری مسدودی را
            # طولانی‌تر می‌کند؛ موتور بازار با این اطلاعات مکث سراسری می‌گذارد.
            raise RateLimitError(
                f"Toobit rate limit on {endpoint}",
                details={
                    "status": response.status_code,
                    "retry_after": _retry_after_seconds(response),
                },
            )
        if response.status_code == 401 or response.status_code == 403:
            raise AuthenticationError(
                f"Toobit rejected the credentials for {endpoint}",
                user_key="errors.authentication",
            )
        try:
            payload = response.json()
        except ValueError as exc:
            snippet = _scrub(response.text[:200])
            raise ExchangeError(
                f"Toobit returned a non-JSON response for {endpoint}",
                details={"status": response.status_code, "body": snippet},
            ) from exc

        if isinstance(payload, dict):
            code = payload.get("code")
            if code not in (None, 0, "0", 200):
                message = str(payload.get("msg") or payload.get("message") or "")
                friendly = TOOBIT_ERROR_CODES.get(_safe_int(code), "")
                if _safe_int(code) in (-1107, -1022, -2014, -2015, -1021):
                    raise AuthenticationError(
                        friendly or message or "Toobit authentication failed",
                        user_key="errors.authentication",
                        details={"code": code},
                    )
                raise ExchangeError(
                    friendly or message or f"Toobit error on {endpoint}",
                    details={"code": code},
                )
        if response.status_code >= 400:
            raise ExchangeError(
                f"Toobit HTTP {response.status_code} on {endpoint}",
                details={"status": response.status_code},
            )
        return payload


def _retry_after_seconds(response: httpx.Response) -> float:
    """خواندن Retry-After (ثانیه)؛ نبود یا نامعتبر بودن آن یعنی صفر."""
    try:
        return max(0.0, float(response.headers.get("Retry-After", 0) or 0))
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    """تبدیل امن کد خطا به عدد."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


async def _sleep_backoff(attempt: int) -> None:
    """مکث فزاینده میان تلاش‌ها."""
    import asyncio

    await asyncio.sleep(min(2.0, 0.3 * (2**attempt)))
