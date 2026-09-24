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
    LBANK_REST_URLS,
    RATE_LIMIT_ERROR_CODES,
    RATE_LIMIT_RETRY_AFTER,
    REGION_BLOCKED_ERROR_CODES,
    RETRYABLE_ERROR_CODES,
)
from app.exceptions.errors import AccessBlockedError, TransientExchangeError
from market.rate_limiter import AsyncRateLimiter, retry_async

logger = get_logger(__name__)


#: کدهای خطای API قرارداد (مستندات رسمی contract.html) — با کدهای اسپات فرق دارند
CONTRACT_RATE_LIMIT_ERROR_CODES = frozenset({10012, 183})
CONTRACT_AUTH_ERROR_CODES = frozenset({10003, 10007, 10008, 10009, 10010, 176, 177})
CONTRACT_RETRYABLE_ERROR_CODES = frozenset({10004})


# v2.5.1: سرآیندهای معمول مرورگر برای دامنهٔ پشت Cloudflare (قرارداد)
BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# کدهای رایج صفحهٔ خطای Cloudflare و معنی کوتاه‌شان
CLOUDFLARE_REASONS: dict[str, str] = {
    "1006": "your IP address is banned",
    "1007": "your IP address is banned",
    "1008": "your IP address is banned",
    "1009": "access from your country/region is blocked",
    "1010": "browser signature blocked",
    "1012": "access denied",
    "1020": "access denied by firewall rule",
}


def _cloudflare_code(body: str) -> str:
    """کد چهاررقمی خطای Cloudflare از متن/HTML صفحهٔ رد درخواست."""
    import re

    for pattern in (r"error code:?\s*(1\d{3})", r"Error\s*(1\d{3})", r"cf-error-code[^0-9]{0,20}(1\d{3})"):
        match = re.search(pattern, body or "", flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


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
        # دامنه‌های جایگزین فقط وقتی به کار می‌آیند که نشانی پیش‌فرض استفاده شده
        # باشد؛ نشانی سفارشی کاربر هرگز بی‌اجازه عوض نمی‌شود.
        if self._base_url == LBANK_REST_URL.rstrip("/"):
            self._base_urls: tuple[str, ...] = tuple(u.rstrip("/") for u in LBANK_REST_URLS)
        else:
            self._base_urls = (self._base_url,)
        self._base_index = 0
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
            except httpx.ConnectTimeout as exc:
                await self._rotate_base_url(exc)
                raise TimeoutErrorApp(f"Connect timed out: {endpoint}") from exc
            except httpx.TimeoutException as exc:
                raise TimeoutErrorApp(f"Request timed out: {endpoint}") from exc
            except httpx.ConnectError as exc:
                await self._rotate_base_url(exc)
                raise NetworkError(f"Could not connect while calling {endpoint}") from exc
            except httpx.HTTPError as exc:
                raise NetworkError(f"Network error while calling {endpoint}") from exc
            return self._handle_response(response, endpoint)

        return await retry_async(
            _do_request,
            max_attempts=self._max_retries,
            retry_on=(NetworkError, TransientExchangeError),
            operation_name=f"GET {endpoint}",
            no_retry_on=(RateLimitError, AccessBlockedError),
        )

    @property
    def base_url(self) -> str:
        """دامنهٔ REST فعلی (برای عیب‌یابی)."""
        return self._base_url

    async def _rotate_base_url(self, exc: BaseException) -> None:
        """
        رفتن به دامنهٔ REST بعدی پس از خطای اتصال (DNS/TCP/TLS).

        اگر یک دامنه در شبکهٔ کاربر فیلتر یا از دسترس خارج باشد، تلاش بعدی
        با دامنهٔ جایگزین انجام می‌شود. خطای HTTP یا محدودیت نرخ دامنه را
        عوض نمی‌کند، چون سرور در دسترس بوده است.
        """
        if len(self._base_urls) < 2:
            return
        previous = self._base_url
        self._base_index = (self._base_index + 1) % len(self._base_urls)
        self._base_url = self._base_urls[self._base_index]
        client, self._client = self._client, None
        if client is not None and not client.is_closed:
            try:
                await client.aclose()
            except Exception:  # noqa: BLE001
                pass
        logger.warning(
            "LBank REST host %s unreachable (%s); switching to %s",
            previous, exc.__class__.__name__, self._base_url,
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
        # v2.5.1: مستند رسمی («Request Format») و کتابخانهٔ رسمی LBank
        # (lbank-connector-python) سه مقدار timestamp/signature_method/echostr
        # را در **سرآیند** می‌فرستند. قبلاً فقط در بدنه بودند و سرور امضا را
        # با سرآیند خالی می‌سنجید — درخواست خصوصی (موجودی) شکست می‌خورد و
        # کیف پول هیچ دارایی‌ای نشان نمی‌داد. هر دو جا فرستاده می‌شود.
        headers = self.signed_headers(timestamp, echostr, content_type="application/x-www-form-urlencoded")

        async def _do_request() -> Any:
            await self._rate_limiter.acquire()
            await self.open()
            assert self._client is not None
            try:
                response = await self._client.post(
                    endpoint,
                    data=payload,
                    headers=headers,
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
            no_retry_on=(RateLimitError, AccessBlockedError),
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

        headers = self.signed_headers(timestamp, echostr, content_type="application/json")

        async def _do_request() -> Any:
            await self._rate_limiter.acquire()
            client = await self._contract_client()
            try:
                response = await client.post(endpoint, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                raise TimeoutErrorApp(f"Contract request timed out: {endpoint}") from exc
            except httpx.HTTPError as exc:
                raise NetworkError(f"Network error while calling {endpoint}") from exc
            return self._handle_response(response, endpoint, contract=True)

        return await retry_async(
            _do_request,
            max_attempts=self._max_retries,
            retry_on=(NetworkError,),
            no_retry_on=(RateLimitError, AccessBlockedError),
            operation_name=f"POST {endpoint}",
        )

    async def _contract_client(self) -> httpx.AsyncClient:
        """کلاینت جدا برای دامنهٔ قراردادها (تنبل و قابل استفادهٔ مجدد)."""
        if self._contract_http is None or self._contract_http.is_closed:
            self._contract_http = httpx.AsyncClient(
                base_url=LBANK_CONTRACT_URL,
                timeout=self._timeout,
                # v2.5.1: دامنهٔ قرارداد پشت Cloudflare است و «بررسی امضای مرورگر»
                # آن عامل کاربر ناآشنا («CryptoAITrader/1.5») را با 403 (کد 1010)
                # رد می‌کند؛ سرآیندهای معمول مرورگر فرستاده می‌شود.
                headers=dict(BROWSER_HEADERS),
            )
        return self._contract_http

    @staticmethod
    def signed_headers(timestamp: str, echostr: str, *, content_type: str) -> dict[str, str]:
        """سرآیندهای امضای LBank (اسپات و قرارداد، v2.5.1)."""
        return {
            "Content-Type": content_type,
            "timestamp": str(timestamp),
            "signature_method": "HmacSHA256",
            "echostr": str(echostr),
        }

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
    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        """خواندن سرآیند Retry-After (ثانیه) در صورت وجود."""
        raw = response.headers.get("Retry-After") if response.headers is not None else None
        if not raw:
            return None
        try:
            value = float(str(raw).strip())
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    @staticmethod
    def _classify_forbidden(response: httpx.Response, endpoint: str) -> Exception | None:
        """
        تشخیص علت 401/403 (v2.5.1).

        اگر بدنه JSON صرافی با کد خطا باشد ← None (مسیر عادی کدهای LBank).
        صفحهٔ Cloudflare ← `AccessBlockedError` با کد و معنی (1015 ← محدودیت نرخ).
        هیچ کلید یا امضایی در متن خطا نمی‌آید؛ فقط کد، معنی و Ray ID.
        """
        status = response.status_code
        try:
            body = response.text or ""
        except Exception:  # noqa: BLE001 - بدنهٔ خراب فقط یعنی تشخیص کمتر
            body = ""
        try:
            payload = response.json()
        except Exception:  # noqa: BLE001
            payload = None
        if isinstance(payload, dict) and any(
            key in payload for key in ("error_code", "result", "success", "msg")
        ):
            return None
        headers = getattr(response, "headers", {}) or {}
        server = str(headers.get("server", "") or "").lower()
        ray = str(headers.get("cf-ray", "") or "")
        cloudflare = "cloudflare" in server or bool(ray) or "cloudflare" in body.lower()
        code = _cloudflare_code(body) if cloudflare else ""
        if code == "1015":
            return RateLimitError(
                "LBank rate limit exceeded (Cloudflare 1015)",
                details={"endpoint": endpoint, "status": status, "cf_code": code},
            )
        reason = CLOUDFLARE_REASONS.get(code, "") if code else ""
        if cloudflare:
            label = f"Cloudflare {code}" if code else "Cloudflare"
            text = f"HTTP {status} blocked by {label}" + (f" — {reason}" if reason else "")
        else:
            reason = "access forbidden (IP whitelist / region / firewall)"
            text = f"HTTP {status} — {reason}"
        details: dict[str, Any] = {"endpoint": endpoint, "status": status,
                                   "cloudflare": cloudflare, "cf_code": code, "reason": reason}
        if ray:
            details["cf_ray"] = ray[:40]
        return AccessBlockedError(f"{text} while calling {endpoint}", details=details)

    def _handle_response(
        self, response: httpx.Response, endpoint: str, *, contract: bool = False
    ) -> Any:
        """
        بررسی پوشش پاسخ LBank و استخراج بخش data.

        قالب پاسخ:
            {"result": "true"|true, "data": ..., "error_code": 0, "msg": "Success"}
        """
        if response.status_code in (429, 418):
            # 418 یعنی IP موقتاً مسدود شده؛ هر دو باید مکث سراسری بسازند و
            # هرگز فوراً تکرار نشوند.
            details: dict[str, Any] = {"endpoint": endpoint, "status": response.status_code}
            retry_after = self._retry_after_seconds(response)
            if retry_after is not None:
                details["retry_after"] = retry_after
            raise RateLimitError("LBank rate limit exceeded", details=details)
        if response.status_code >= 500:
            raise ExchangeError(
                f"LBank server error ({response.status_code})",
                details={"endpoint": endpoint, "status": response.status_code},
            )
        if response.status_code in (401, 403):
            blocked = self._classify_forbidden(response, endpoint)
            if blocked is not None:
                raise blocked
            # بدنهٔ JSON صرافی (مثلاً کد خطای کلید) — همان مسیر عادی پایین
        elif response.status_code >= 400:
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
        try:
            error_code = int(payload.get("error_code") or 0)
        except (TypeError, ValueError):
            error_code = -1

        if is_success and error_code == 0:
            return payload.get("data")

        if contract:
            # v2.5.0: پاسخ API قراردادها `{"data":…,"error_code":0,"msg":"",
            # "result":"","success":true}` است — `result` رشتهٔ خالی است و
            # موفقیت در `success` می‌آید. قبلاً همین پاسخ موفق «LBank error 0»
            # حساب می‌شد و موجودی فیوچرز همیشه خالی نمایش داده می‌شد.
            success = payload.get("success")
            if error_code == 0 and (
                success in (True, "true", "True") or (success is None and result in ("", None))
            ):
                return payload.get("data")
            if error_code in CONTRACT_RATE_LIMIT_ERROR_CODES:
                details = {"endpoint": endpoint, "error_code": error_code,
                           "message": str(payload.get("msg") or "too frequent"),
                           "retry_after": RATE_LIMIT_RETRY_AFTER}
                raise RateLimitError("LBank contract rate limit", details=details)
            if error_code in CONTRACT_AUTH_ERROR_CODES:
                details = {"endpoint": endpoint, "error_code": error_code,
                           "message": str(payload.get("msg") or "auth")}
                raise AuthenticationError("LBank contract authentication failed", details=details)
            if error_code in CONTRACT_RETRYABLE_ERROR_CODES:
                details = {"endpoint": endpoint, "error_code": error_code,
                           "message": str(payload.get("msg") or "timeout")}
                raise TransientExchangeError("LBank contract transient error", details=details)

        message = LBANK_ERROR_MESSAGES.get(error_code, str(payload.get("msg", "Unknown error")))
        details = {"endpoint": endpoint, "error_code": error_code, "message": message}

        if error_code in RATE_LIMIT_ERROR_CODES:
            details["retry_after"] = RATE_LIMIT_RETRY_AFTER
            raise RateLimitError(f"LBank rate limit: {message}", details=details)
        if error_code in REGION_BLOCKED_ERROR_CODES:
            raise ExchangeError(f"LBank unavailable in this region: {message}", details=details)
        if error_code in AUTH_ERROR_CODES:
            raise AuthenticationError(f"LBank authentication failed: {message}", details=details)
        if error_code in RETRYABLE_ERROR_CODES:
            raise TransientExchangeError(f"LBank transient error: {message}", details=details)
        raise ExchangeError(f"LBank error {error_code}: {message}", details=details)
