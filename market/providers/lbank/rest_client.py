"""
کلاینت REST صرافی LBank.

مسئولیت‌ها:
    • ارسال درخواست HTTP با مهلت زمانی مشخص
    • رعایت محدودیت نرخ درخواست
    • تلاش مجدد هوشمند در خطاهای گذرا
    • تفسیر پوشش پاسخ LBank و تبدیل خطا به استثنای مناسب برنامه
    • امضای درخواست‌های خصوصی با HmacSHA256

نکته امنیتی: کلید API فقط در حافظه نگهداری می‌شود و هرگز لاگ نمی‌گردد؛
پارامترهای امضا نیز پیش از لاگ حذف می‌شوند.
"""

from __future__ import annotations

import hashlib
import hmac
import random
import string
import time
from typing import Any

import httpx

from app.exceptions import (
    AuthenticationError,
    ExchangeError,
    NetworkError,
    RateLimitError,
    TimeoutErrorApp,
)
from app.logging import get_logger
from market.providers.lbank.constants import (
    AUTH_ERROR_CODES,
    LBANK_CONTRACT_URL,
    LBANK_ERROR_MESSAGES,
    LBANK_REST_URL,
    RETRYABLE_ERROR_CODES,
)
from app.exceptions.errors import TransientExchangeError
from market.rate_limiter import AsyncRateLimiter, retry_async

logger = get_logger(__name__)


class LBankRestClient:
    """
    کلاینت سطح پایین ارتباط با REST API صرافی LBank.

    این کلاس هیچ منطق تجاری ندارد؛ فقط درخواست می‌فرستد و «داده» را
    برمی‌گرداند. تفسیر داده بر عهده LBankParser است.
    """

    def __init__(
        self,
        base_url: str = LBANK_REST_URL,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        timeout: float = 15.0,
        max_retries: int = 3,
        rate_limit_per_second: float = 8.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or ""
        self._api_secret = api_secret or ""
        self._timeout = timeout
        self._max_retries = max_retries
        self._rate_limiter = AsyncRateLimiter(rate_limit_per_second)
        self._client: httpx.AsyncClient | None = None
        # کلاینت دامنهٔ قراردادها؛ جداست چون base_url متفاوتی دارد
        self._contract_http: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # چرخه عمر
    # ------------------------------------------------------------------
    async def open(self) -> None:
        """ساخت کلاینت HTTP در صورت نبود (استفاده مجدد از اتصال‌ها)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                headers={"User-Agent": "CryptoAITrader/1.0", "Accept": "application/json"},
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
            logger.debug("LBank REST client opened for %s", self._base_url)

    async def close(self) -> None:
        """بستن کلاینت HTTP و آزادسازی اتصال‌ها."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            logger.debug("LBank REST client closed")
        self._client = None
        if self._contract_http is not None and not self._contract_http.is_closed:
            await self._contract_http.aclose()
        self._contract_http = None

    def set_credentials(self, api_key: str, api_secret: str) -> None:
        """به‌روزرسانی کلیدها در زمان اجرا (پس از تغییر در تنظیمات)."""
        self._api_key = api_key or ""
        self._api_secret = api_secret or ""

    @property
    def has_credentials(self) -> bool:
        """آیا کلید و رمز برای درخواست‌های خصوصی تنظیم شده‌اند؟"""
        return bool(self._api_key and self._api_secret)

    def update_limits(self, *, timeout: float | None = None, rate_limit_per_second: float | None = None) -> None:
        """به‌روزرسانی مهلت زمانی و نرخ درخواست از روی تنظیمات کاربر."""
        if timeout is not None:
            self._timeout = timeout
        if rate_limit_per_second is not None:
            self._rate_limiter.update_rate(rate_limit_per_second)

    # ------------------------------------------------------------------
    # درخواست عمومی
    # ------------------------------------------------------------------
    async def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """
        ارسال درخواست GET عمومی و بازگرداندن بخش data از پاسخ.

        تمام خطاهای شبکه و صرافی به استثناهای داخلی نگاشت می‌شوند تا
        لایه‌های بالاتر بتوانند یکنواخت با آن‌ها برخورد کنند.
        """

        async def _do_request() -> Any:
            await self._rate_limiter.acquire()
            await self.open()
            assert self._client is not None
            try:
                response = await self._client.get(endpoint, params=params or {})
            except httpx.TimeoutException as exc:
                raise TimeoutErrorApp(f"Request timed out: {endpoint}") from exc
            except httpx.HTTPError as exc:
                raise NetworkError(f"Network error while calling {endpoint}") from exc
            return self._handle_response(response, endpoint)

        return await retry_async(
            _do_request,
            max_attempts=self._max_retries,
            retry_on=(NetworkError, TransientExchangeError),
            operation_name=f"GET {endpoint}",
        )

    # ------------------------------------------------------------------
    # درخواست خصوصی (امضاشده)
    # ------------------------------------------------------------------
    async def post_signed(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """
        ارسال درخواست POST امضاشده به Endpointهای خصوصی.

        روش امضا مطابق مستندات LBank:
            ۱) پارامترها (به‌همراه api_key، timestamp، signature_method، echostr)
               بر اساس نام مرتب و به شکل key=value&... زنجیره می‌شوند.
            ۲) از این رشته MD5 گرفته می‌شود و با حروف بزرگ نمایش می‌یابد.
            ۳) این خلاصه با HmacSHA256 و کلید Secret امضا می‌گردد.

        هشدار: در نسخه اول فقط Endpointهای «فقط خواندنی» فراخوانی می‌شوند؛
        هیچ سفارش واقعی ارسال نمی‌شود.
        """
        if not self.has_credentials:
            raise AuthenticationError(
                "API credentials are not configured", details={"endpoint": endpoint}
            )

        payload: dict[str, Any] = dict(params or {})
        payload.update(
            {
                "api_key": self._api_key,
                "signature_method": "HmacSHA256",
                "timestamp": str(int(time.time() * 1000)),
                "echostr": self._random_echostr(),
            }
        )
        payload["sign"] = self._build_signature(payload)

        async def _do_request() -> Any:
            await self._rate_limiter.acquire()
            await self.open()
            assert self._client is not None
            try:
                response = await self._client.post(
                    endpoint,
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            except httpx.TimeoutException as exc:
                raise TimeoutErrorApp(f"Signed request timed out: {endpoint}") from exc
            except httpx.HTTPError as exc:
                raise NetworkError(f"Network error while calling {endpoint}") from exc
            return self._handle_response(response, endpoint)

        return await retry_async(
            _do_request,
            max_attempts=self._max_retries,
            retry_on=(NetworkError,),
            operation_name=f"POST {endpoint}",
        )

    async def post_contract_signed(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> Any:
        """
        درخواست امضاشده به API قراردادهای آتی.

        بخش قراردادها روی دامنهٔ جداگانه (`lbkperp.lbank.com`) است و با
        بخش اسپات دو تفاوت دارد که رعایت نکردنشان به خطای ۴۰۳ می‌انجامد:
        بدنه باید **JSON** باشد و سه پارامتر `timestamp`، `signature_method`
        و `echostr` باید علاوه بر بدنه، در **هدر** هم تکرار شوند.

        الگوریتم امضا همان MD5 → HmacSHA256 اسپات است.
        """
        if not self.has_credentials:
            raise AuthenticationError(
                "API credentials are not configured", details={"endpoint": endpoint}
            )

        timestamp = str(int(time.time() * 1000))
        echostr = self._random_echostr()
        payload: dict[str, Any] = dict(params or {})
        payload.update(
            {
                "api_key": self._api_key,
                "signature_method": "HmacSHA256",
                "timestamp": timestamp,
                "echostr": echostr,
            }
        )
        payload["sign"] = self._build_signature(payload)

        headers = {
            "Content-Type": "application/json",
            "timestamp": timestamp,
            "signature_method": "HmacSHA256",
            "echostr": echostr,
        }

        async def _do_request() -> Any:
            await self._rate_limiter.acquire()
            client = await self._contract_client()
            try:
                response = await client.post(endpoint, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                raise TimeoutErrorApp(f"Contract request timed out: {endpoint}") from exc
            except httpx.HTTPError as exc:
                raise NetworkError(f"Network error while calling {endpoint}") from exc
            return self._handle_response(response, endpoint)

        return await retry_async(
            _do_request,
            max_attempts=self._max_retries,
            retry_on=(NetworkError,),
            operation_name=f"POST {endpoint}",
        )

    async def _contract_client(self) -> httpx.AsyncClient:
        """کلاینت جدا برای دامنهٔ قراردادها (تنبل و قابل استفادهٔ مجدد)."""
        if self._contract_http is None or self._contract_http.is_closed:
            self._contract_http = httpx.AsyncClient(
                base_url=LBANK_CONTRACT_URL,
                timeout=self._timeout,
                headers={"User-Agent": "CryptoAITrader/1.5"},
            )
        return self._contract_http

    def _build_signature(self, payload: dict[str, Any]) -> str:
        """
        ساخت امضای HmacSHA256 مطابق قرارداد LBank.

        نکته: مقدار sign نباید در محاسبه امضا حضور داشته باشد.
        """
        items = sorted((k, v) for k, v in payload.items() if k != "sign")
        query = "&".join(f"{key}={value}" for key, value in items)
        digest = hashlib.md5(query.encode("utf-8")).hexdigest().upper()
        return hmac.new(
            self._api_secret.encode("utf-8"), digest.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    @staticmethod
    def _random_echostr(length: int = 35) -> str:
        """
        ساخت رشته تصادفی echostr (طول مجاز ۳۰ تا ۴۰ کاراکتر).

        این مقدار برای جلوگیری از حمله بازپخش (Replay) استفاده می‌شود.
        """
        alphabet = string.ascii_letters + string.digits
        return "".join(random.choices(alphabet, k=length))

    # ------------------------------------------------------------------
    # تفسیر پاسخ
    # ------------------------------------------------------------------
    def _handle_response(self, response: httpx.Response, endpoint: str) -> Any:
        """
        بررسی پوشش پاسخ LBank و استخراج بخش data.

        قالب پاسخ:
            {"result": "true"|true, "data": ..., "error_code": 0, "msg": "Success"}
        """
        if response.status_code == 429:
            raise RateLimitError("LBank rate limit exceeded", details={"endpoint": endpoint})
        if response.status_code >= 500:
            raise ExchangeError(
                f"LBank server error ({response.status_code})",
                details={"endpoint": endpoint, "status": response.status_code},
            )
        if response.status_code >= 400:
            raise NetworkError(
                f"HTTP {response.status_code} while calling {endpoint}",
                details={"status": response.status_code},
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ExchangeError(f"Invalid JSON response from {endpoint}") from exc

        # برخی Endpointها مستقیماً آرایه برمی‌گردانند
        if not isinstance(payload, dict):
            return payload

        result = payload.get("result")
        is_success = result in (True, "true", "True")
        error_code = int(payload.get("error_code") or 0)

        if is_success and error_code == 0:
            return payload.get("data")

        message = LBANK_ERROR_MESSAGES.get(error_code, str(payload.get("msg", "Unknown error")))
        details = {"endpoint": endpoint, "error_code": error_code, "message": message}

        if error_code in AUTH_ERROR_CODES:
            raise AuthenticationError(f"LBank authentication failed: {message}", details=details)
        if error_code in RETRYABLE_ERROR_CODES:
            raise TransientExchangeError(f"LBank transient error: {message}", details=details)
        raise ExchangeError(f"LBank error {error_code}: {message}", details=details)
