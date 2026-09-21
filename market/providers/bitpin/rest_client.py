"""
کلاینت HTTP صرافی بیت‌پین با مدیریت خودکار توکن.

برخلاف صرافی‌های سبک بایننس، بیت‌پین هر درخواست را امضا نمی‌کند؛ کلید و
رمز یک‌بار با `/usr/authenticate/` مبادله می‌شوند و یک جفت توکن می‌دهند:

    refresh : طول‌عمر بلند، برای گرفتن access جدید
    access  : طول‌عمر کوتاه (حدود ۱۵ دقیقه)، در هدر Authorization

بنابراین این کلاینت باید سه کار را درست انجام دهد:
۱. ورود تنبل (فقط وقتی واقعاً به مسیر خصوصی نیاز شد)
۲. تازه‌سازی خودکار پیش از انقضا
۳. تلاش دوباره یک‌بار در صورت ۴۰۱ (توکن زودتر از انتظار باطل شده)

امنیت: کلید، رمز و هر دو توکن هرگز در لاگ یا پیام خطا ظاهر نمی‌شوند.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.exceptions import (
    AuthenticationError,
    ExchangeError,
    NetworkError,
    TimeoutErrorApp,
)
from app.logging import get_logger
from market.providers.bitpin.constants import (
    BITPIN_ACCESS_TOKEN_TTL,
    BITPIN_ERROR_CODES,
    BITPIN_IP_HINT_CODE,
    BITPIN_REST_URL,
    BITPIN_TOKEN_REFRESH_MARGIN,
    BitpinEndpoints,
)

logger = get_logger(__name__)


class BitpinRestClient:
    """کلاینت REST بیت‌پین با چرخهٔ عمر توکن."""

    def __init__(
        self,
        *,
        base_url: str = BITPIN_REST_URL,
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

        self._access_token: str = ""
        self._refresh_token: str = ""
        self._token_issued_at: float = 0.0
        # قفل تا چند درخواست هم‌زمان، هم‌زمان وارد نشوند
        self._auth_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # چرخه عمر
    # ------------------------------------------------------------------
    async def connect(self) -> None:
        """ساخت کلاینت HTTP."""
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )

    async def close(self) -> None:
        """بستن اتصال و پاک‌کردن توکن‌ها از حافظه."""
        if self._http is not None:
            await self._http.aclose()
            self._http = None
        self._access_token = ""
        self._refresh_token = ""
        self._token_issued_at = 0.0

    async def _client(self) -> httpx.AsyncClient:
        """دسترسی تنبل به کلاینت HTTP."""
        if self._http is None:
            await self.connect()
        assert self._http is not None
        return self._http

    @property
    def has_credentials(self) -> bool:
        """آیا کلید و رمز تنظیم شده‌اند؟"""
        return bool(self._api_key and self._api_secret)

    @property
    def is_authenticated(self) -> bool:
        """آیا توکن معتبر در دست داریم؟"""
        return bool(self._access_token) and not self._token_expired

    @property
    def _token_expired(self) -> bool:
        """آیا توکن به مرز انقضا رسیده است؟"""
        if not self._token_issued_at:
            return True
        age = time.time() - self._token_issued_at
        return age >= (BITPIN_ACCESS_TOKEN_TTL - BITPIN_TOKEN_REFRESH_MARGIN)

    # ------------------------------------------------------------------
    # درخواست عمومی
    # ------------------------------------------------------------------
    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """GET عمومی با تلاش مجدد روی خطاهای گذرا."""
        client = await self._client()
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = await client.get(endpoint, params=params or {})
                return self._unwrap(response, endpoint)
            except httpx.TimeoutException:
                last_error = TimeoutErrorApp(f"Request timed out: {endpoint}")
            except httpx.HTTPError:
                last_error = NetworkError(f"Network error while calling {endpoint}")
            if attempt + 1 < self._max_retries:
                await asyncio.sleep(min(2.0, 0.3 * (2**attempt)))
        raise last_error or NetworkError(f"Request failed: {endpoint}")

    # ------------------------------------------------------------------
    # احراز هویت
    # ------------------------------------------------------------------
    async def authenticate(self) -> None:
        """
        گرفتن جفت توکن با کلید و رمز.

        خطای ۴۰۶ با کد `api_credential_wrong` معمولاً یعنی IP کاربر در
        فهرست مجاز کلید نیست — این رایج‌ترین اشتباه است و باید پیام
        روشنی بدهیم نه «خطای نامشخص».
        """
        if not self.has_credentials:
            raise AuthenticationError(
                "Bitpin API credentials are not configured",
                user_key="errors.authentication",
            )
        client = await self._client()
        try:
            response = await client.post(
                BitpinEndpoints.AUTHENTICATE,
                json={"api_key": self._api_key, "secret_key": self._api_secret},
            )
        except httpx.TimeoutException as exc:
            raise TimeoutErrorApp("Bitpin authentication timed out") from exc
        except httpx.HTTPError as exc:
            raise NetworkError("Network error during Bitpin authentication") from exc

        payload = self._unwrap(response, BitpinEndpoints.AUTHENTICATE, auth_stage=True)
        if not isinstance(payload, dict):
            raise AuthenticationError(
                "Unexpected Bitpin authentication response",
                user_key="errors.authentication",
            )
        access = str(payload.get("access") or payload.get("access_token") or "")
        refresh = str(payload.get("refresh") or payload.get("refresh_token") or "")
        if not access:
            raise AuthenticationError(
                "Bitpin did not return an access token",
                user_key="errors.authentication",
            )
        self._access_token = access
        self._refresh_token = refresh
        self._token_issued_at = time.time()
        logger.info("Bitpin authentication succeeded")

    async def _refresh(self) -> None:
        """
        تازه‌سازی توکن دسترسی.

        اگر refresh هم باطل شده باشد، به ورود کامل برمی‌گردیم؛ این حالت
        پس از چند ساعت بی‌کاری برنامه طبیعی است.
        """
        if not self._refresh_token:
            await self.authenticate()
            return
        client = await self._client()
        try:
            response = await client.post(
                BitpinEndpoints.REFRESH_TOKEN, json={"refresh": self._refresh_token}
            )
        except httpx.HTTPError:
            await self.authenticate()
            return

        if response.status_code >= 400:
            logger.debug("Bitpin refresh rejected; falling back to full login")
            await self.authenticate()
            return
        try:
            payload = response.json()
        except ValueError:
            await self.authenticate()
            return
        access = str((payload or {}).get("access") or "")
        if not access:
            await self.authenticate()
            return
        self._access_token = access
        self._token_issued_at = time.time()

    async def ensure_token(self) -> None:
        """اطمینان از داشتن توکن معتبر، با قفل ضد رقابت."""
        async with self._auth_lock:
            if not self._access_token:
                await self.authenticate()
            elif self._token_expired:
                await self._refresh()

    # ------------------------------------------------------------------
    # درخواست خصوصی
    # ------------------------------------------------------------------
    async def get_private(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """
        GET نیازمند احراز هویت.

        در صورت ۴۰۱ یک‌بار توکن را نو می‌کنیم و دوباره تلاش می‌کنیم؛
        بیش از یک‌بار تلاش نمی‌کنیم تا حلقهٔ بی‌پایان نسازیم.
        """
        await self.ensure_token()
        client = await self._client()

        for attempt in range(2):
            try:
                response = await client.get(
                    endpoint,
                    params=params or {},
                    headers={"Authorization": f"Bearer {self._access_token}"},
                )
            except httpx.TimeoutException as exc:
                raise TimeoutErrorApp(f"Private request timed out: {endpoint}") from exc
            except httpx.HTTPError as exc:
                raise NetworkError(f"Network error while calling {endpoint}") from exc

            if response.status_code == 401 and attempt == 0:
                logger.debug("Bitpin token rejected; refreshing once")
                async with self._auth_lock:
                    await self.authenticate()
                continue
            return self._unwrap(response, endpoint)
        raise AuthenticationError(
            f"Bitpin kept rejecting the token for {endpoint}",
            user_key="errors.authentication",
        )

    # ------------------------------------------------------------------
    # بازکردن پاسخ
    # ------------------------------------------------------------------
    def _unwrap(
        self, response: httpx.Response, endpoint: str, *, auth_stage: bool = False
    ) -> Any:
        """بررسی خطا و بازگرداندن بدنهٔ JSON."""
        try:
            payload = response.json()
        except ValueError:
            if response.status_code >= 400:
                raise ExchangeError(
                    f"Bitpin HTTP {response.status_code} on {endpoint}",
                    details={"status": response.status_code},
                ) from None
            raise ExchangeError(
                f"Bitpin returned a non-JSON response for {endpoint}",
                details={"status": response.status_code},
            ) from None

        if response.status_code >= 400:
            code = ""
            detail = ""
            if isinstance(payload, dict):
                code = str(payload.get("code") or "")
                detail = str(payload.get("detail") or payload.get("message") or "")
            friendly = BITPIN_ERROR_CODES.get(code, "") or detail
            if response.status_code in (401, 403, 406) or code == BITPIN_IP_HINT_CODE:
                raise AuthenticationError(
                    friendly or "Bitpin authentication failed",
                    user_key="errors.authentication",
                    details={"code": code, "status": response.status_code},
                )
            raise ExchangeError(
                friendly or f"Bitpin HTTP {response.status_code} on {endpoint}",
                details={"code": code, "status": response.status_code},
            )
        return payload
