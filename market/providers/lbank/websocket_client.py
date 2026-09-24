"""
کلاینت WebSocket صرافی LBank با اتصال مجدد خودکار.

چرا وجود دارد؟
    داده لحظه‌ای باید بدون درخواست مکرر REST دریافت شود. مهم‌تر اینکه طبق
    بند ۱۰ سند پروژه، قطع اتصال نباید کاربر را مجبور به Restart کند؛
    بنابراین چرخه زیر به‌صورت خودکار اجرا می‌شود:

        Disconnected → Retry → Reconnect → Resubscribe → Continue

پروتکل (راستی‌آزمایی‌شده با اتصال واقعی):
    اشتراک تیکر : {"action":"subscribe","subscribe":"tick","pair":"btc_usdt"}
    اشتراک کندل : {"action":"subscribe","subscribe":"kbar","kbar":"1min","pair":"btc_usdt"}
    اشتراک عمق  : {"action":"subscribe","subscribe":"depth","depth":"10","pair":"btc_usdt"}
    سرور هر چند ثانیه {"action":"ping","ping":"<id>"} می‌فرستد و کلاینت باید
    {"action":"pong","pong":"<id>"} پاسخ دهد وگرنه اتصال قطع می‌شود.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from app.core.constants import ConnectionStatus
from app.exceptions import TimeframeError
from app.logging import get_logger
from market.timeframes import normalize_timeframe
from market.providers.lbank.constants import LBANK_TIMEFRAME_MAP, LBANK_WS_URL, LBANK_WS_URLS
from market.providers.lbank.parser import LBankParser

logger = get_logger(__name__)

# نسخهٔ ۲.۳.۲: کلاینت هم ping می‌فرستد (مستندات LBank مجاز می‌داند) تا اتصال
# بیکار در NAT/پراکسی کاربر بسته نشود و قطع نیمه‌باز زودتر کشف شود.
CLIENT_PING_INTERVAL = 20.0
# اگر این مدت هیچ فریمی (حتی ping/pong) نرسد، اتصال مرده فرض می‌شود.
RECV_TIMEOUT = 60.0
# فاصلهٔ ارسال پیام‌های اشتراک؛ انفجار صدها پیام در یک لحظه ممکن است سرور را
# به بستن اتصال وادارد.
SUBSCRIBE_PACING = 0.02
CONNECT_TIMEOUT = 15.0
WS_USER_AGENT = "Mozilla/5.0 (compatible; CryptoAITrader)"


def _connect_supports(name: str) -> bool:
    """آیا نسخهٔ نصب‌شدهٔ websockets این آرگومان connect را می‌پذیرد؟"""
    try:
        return name in inspect.signature(websockets.connect).parameters
    except (TypeError, ValueError):
        return False


def _is_proxy_error(exc: BaseException) -> bool:
    """
    خطای ناشی از پراکسی سیستم (مثلاً پراکسی SOCKS بدون python-socks).

    websockets 15 به‌طور پیش‌فرض پراکسی سیستم عامل را به کار می‌برد؛ اگر آن
    پراکسی قابل استفاده نباشد، اتصال مستقیم امتحان می‌شود.
    """
    name = exc.__class__.__name__.lower()
    text = str(exc).lower()
    return "proxy" in name or "python-socks" in text or "proxy" in text

# نگاشت تایم‌فریم داخلی به نام بازه در پروتکل WebSocket صرافی
WS_KBAR_MAP: dict[str, str] = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1hr",
    "4h": "4hr",
    "1d": "day",
    "1w": "week",
}


def _normalize(timeframe: str) -> str:
    """
    یکدست‌سازی کد تایم‌فریم برای جست‌وجو در نگاشت وب‌سوکت.

    برخلاف `normalize_timeframe`، اینجا کد ناشناخته خطا نمی‌دهد: لایه
    وب‌سوکت فقط زیرمجموعه‌ای از تایم‌فریم‌ها را پوشش می‌دهد و بقیه به
    نظرسنجی REST سپرده می‌شوند، پس نبودِ یک کد وضعیت عادی است.
    """
    try:
        return normalize_timeframe(timeframe)
    except TimeframeError:
        return timeframe.strip()



@dataclass(frozen=True, slots=True)
class Subscription:
    """
    یک اشتراک فعال.

    این ساختار Hashable است تا بتوان مجموعه اشتراک‌ها را نگه داشت و پس از
    اتصال مجدد، همه را دوباره ثبت کرد.
    """

    channel: str  # tick | kbar | depth
    pair: str  # قالب صرافی، مثل btc_usdt
    extra: str = ""  # بازه کندل یا عمق دفتر سفارش

    def to_message(self) -> dict[str, Any]:
        """ساخت پیام اشتراک مطابق پروتکل LBank."""
        message: dict[str, Any] = {
            "action": "subscribe",
            "subscribe": self.channel,
            "pair": self.pair,
        }
        if self.channel == "kbar":
            message["kbar"] = self.extra or "1min"
        elif self.channel == "depth":
            message["depth"] = self.extra or "10"
        return message

    def to_unsubscribe_message(self) -> dict[str, Any]:
        """ساخت پیام لغو اشتراک."""
        message = self.to_message()
        message["action"] = "unsubscribe"
        message["unsubscribe"] = message.pop("subscribe")
        return message


class LBankWebSocketClient:
    """
    مدیریت اتصال زنده به LBank.

    فراخوان‌های برگشتی (Callback) اختیاری هستند و در صورت بروز خطا در آن‌ها،
    اتصال قطع نمی‌شود؛ خطا فقط لاگ می‌گردد.
    """

    def __init__(
        self,
        url: str | None = None,
        *,
        urls: tuple[str, ...] | list[str] | None = None,
        on_ticker: Callable[[Any], None] | None = None,
        on_candle: Callable[[str, str, Any], None] | None = None,
        on_orderbook: Callable[[Any], None] | None = None,
        on_status_change: Callable[[ConnectionStatus], None] | None = None,
        max_reconnect_delay: float = 60.0,
    ) -> None:
        # ترتیب: فهرست صریح ← نشانی صریح ← فهرست پیش‌فرض (رسمی + قدیمی).
        if urls:
            candidates = tuple(dict.fromkeys(str(u) for u in urls if u))
        elif url:
            candidates = (url,)
        else:
            candidates = tuple(LBANK_WS_URLS) or (LBANK_WS_URL,)
        self._urls: tuple[str, ...] = candidates
        self._url_index = 0
        self._url = self._urls[0]
        self._use_proxy = True
        self._last_error = ""
        self._last_message_at = 0.0
        self._ping_task: asyncio.Task[None] | None = None
        self._on_ticker = on_ticker
        self._on_candle = on_candle
        self._on_orderbook = on_orderbook
        self._on_status_change = on_status_change
        self._max_reconnect_delay = max_reconnect_delay

        self._subscriptions: set[Subscription] = set()
        self._connection: Any = None
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._status = ConnectionStatus.DISCONNECTED
        self._lock = asyncio.Lock()
        self._reconnect_count = 0

    # ------------------------------------------------------------------
    # وضعیت
    # ------------------------------------------------------------------
    @property
    def status(self) -> ConnectionStatus:
        """وضعیت فعلی اتصال."""
        return self._status

    @property
    def is_connected(self) -> bool:
        """آیا اتصال برقرار است؟"""
        return self._status is ConnectionStatus.CONNECTED

    @property
    def reconnect_count(self) -> int:
        """تعداد دفعات اتصال مجدد (برای نمایش در بخش عیب‌یابی)."""
        return self._reconnect_count

    @property
    def current_url(self) -> str:
        """نشانی‌ای که اکنون (یا در تلاش بعدی) استفاده می‌شود."""
        return self._url

    @property
    def urls(self) -> tuple[str, ...]:
        """همهٔ نشانی‌های جایگزین به ترتیب تلاش."""
        return self._urls

    @property
    def last_error(self) -> str:
        """آخرین علت شکست اتصال (برای عیب‌یابی و گزارش کاربر)."""
        return self._last_error

    def _advance_url(self) -> None:
        """رفتن به نشانی جایگزین بعدی پس از شکست."""
        if len(self._urls) < 2:
            return
        self._url_index = (self._url_index + 1) % len(self._urls)
        self._url = self._urls[self._url_index]

    def _connect_kwargs(self) -> dict[str, Any]:
        """آرگومان‌های connect سازگار با نسخهٔ نصب‌شدهٔ websockets."""
        kwargs: dict[str, Any] = {
            "open_timeout": CONNECT_TIMEOUT,
            "ping_interval": None,  # ping پروتکلی LBank در سطح JSON است
            "close_timeout": 5,
            "max_size": 4 * 1024 * 1024,
        }
        if _connect_supports("user_agent_header"):
            kwargs["user_agent_header"] = WS_USER_AGENT
        if not self._use_proxy and _connect_supports("proxy"):
            kwargs["proxy"] = None
        return kwargs

    def _set_status(self, status: ConnectionStatus) -> None:
        """تغییر وضعیت و اطلاع‌رسانی به شنونده."""
        if self._status is status:
            return
        self._status = status
        logger.info("LBank WebSocket status: %s", status.value)
        if self._on_status_change is not None:
            try:
                self._on_status_change(status)
            except Exception:  # noqa: BLE001 - خطای شنونده نباید اتصال را بشکند
                logger.exception("WebSocket status callback failed")

    # ------------------------------------------------------------------
    # چرخه عمر
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """شروع حلقه اتصال در پس‌زمینه."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_forever(), name="lbank-ws")
        logger.debug("LBank WebSocket loop started")

    async def stop(self) -> None:
        """توقف کامل و بستن اتصال."""
        self._running = False
        if self._connection is not None:
            with contextlib.suppress(Exception):
                await self._connection.close()
            self._connection = None
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._set_status(ConnectionStatus.DISCONNECTED)
        logger.debug("LBank WebSocket loop stopped")

    async def _run_forever(self) -> None:
        """
        حلقه اصلی: اتصال، دریافت پیام و در صورت قطع، تلاش مجدد.

        نسخهٔ ۲.۳.۲: اگر دست‌دادن شکست بخورد یا سرور پیش از ارسال هیچ داده‌ای
        اتصال را ببندد، نشانی بعدی فهرست (دامنهٔ رسمی/قدیمی) امتحان می‌شود. در
        دور اول عبور از فهرست، تأخیر کوتاه است تا کاربر منتظر نماند؛ پس از آن
        تأخیر نمایی همراه با نویز تصادفی است.
        """
        attempt = 0
        while self._running:
            received_any = False
            url = self._url
            try:
                self._set_status(
                    ConnectionStatus.RECONNECTING if attempt else ConnectionStatus.CONNECTING
                )
                async with websockets.connect(url, **self._connect_kwargs()) as connection:
                    self._connection = connection
                    self._last_message_at = time.monotonic()
                    self._set_status(ConnectionStatus.CONNECTED)
                    logger.info("LBank WebSocket connected to %s", url)
                    self._ping_task = asyncio.create_task(
                        self._client_ping_loop(connection), name="lbank-ws-ping"
                    )
                    await self._resubscribe_all()
                    received_any = await self._receive_loop(connection)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - هر خطایی باید به تلاش مجدد منجر شود
                self._last_error = f"{exc.__class__.__name__}: {exc}"[:300]
                logger.warning("LBank WebSocket error on %s: %s", url, self._last_error)
                if self._use_proxy and _is_proxy_error(exc) and _connect_supports("proxy"):
                    # پراکسی سیستم قابل استفاده نیست؛ اتصال مستقیم امتحان شود.
                    self._use_proxy = False
                    logger.warning("System proxy unusable for LBank WebSocket; retrying direct")
            finally:
                await self._stop_ping_task()
                self._connection = None
            if not self._running:
                break
            self._set_status(ConnectionStatus.DISCONNECTED)
            if received_any:
                # دامنه سالم بود و داده داد؛ همان را نگه می‌داریم.
                attempt = 1
            else:
                attempt += 1
                self._advance_url()
            self._reconnect_count += 1
            if attempt <= len(self._urls):
                delay = 1.0 + random.uniform(0, 0.5)
            else:
                step = attempt - len(self._urls)
                delay = min(self._max_reconnect_delay, 2 ** min(step, 6))
                delay += random.uniform(0, delay * 0.3)
            logger.info(
                "Reconnecting to LBank WebSocket via %s in %.1fs (attempt %d)", self._url, delay, attempt
            )
            await asyncio.sleep(delay)

    async def _stop_ping_task(self) -> None:
        task, self._ping_task = self._ping_task, None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def _client_ping_loop(self, connection: Any) -> None:
        """ارسال ping دوره‌ای کلاینت؛ خطای ارسال فقط حلقه را پایان می‌دهد."""
        counter = 0
        while self._running:
            await asyncio.sleep(CLIENT_PING_INTERVAL)
            counter += 1
            try:
                await connection.send(json.dumps({"action": "ping", "ping": f"cat-{counter}"}))
            except Exception:  # noqa: BLE001 - حلقهٔ دریافت، قطع را تشخیص می‌دهد
                return

    async def _receive_loop(self, connection: Any) -> bool:
        """
        دریافت و پردازش پیام‌ها تا زمان قطع اتصال.

        اگر RECV_TIMEOUT ثانیه هیچ فریمی (حتی pong پاسخ ping کلاینت) نرسد،
        اتصال «مرده» فرض شده و بسته می‌شود تا چرخه اتصال مجدد آغاز گردد.
        خروجی: آیا روی این اتصال دست‌کم یک پیام رسید؟
        """
        received_any = False
        while self._running:
            try:
                raw = await asyncio.wait_for(connection.recv(), timeout=RECV_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning("No LBank WebSocket data for %.0fs; forcing reconnect", RECV_TIMEOUT)
                self._last_error = "silent connection"
                with contextlib.suppress(Exception):
                    await connection.close()
                return received_any
            except ConnectionClosed as exc:
                code = getattr(getattr(exc, "rcvd", None), "code", None)
                self._last_error = f"closed by server (code={code})"
                logger.info("LBank WebSocket closed by server (code=%s)", code)
                return received_any
            received_any = True
            self._last_message_at = time.monotonic()
            await self._handle_message(raw, connection)
        return received_any

    async def _handle_message(self, raw: str | bytes, connection: Any) -> None:
        """تجزیه یک پیام دریافتی و فراخوانی شنونده مناسب."""
        try:
            message = json.loads(raw)
        except (ValueError, TypeError):
            logger.debug("Ignoring non-JSON WebSocket frame")
            return
        if not isinstance(message, dict):
            return

        # پاسخ به ping سرور، شرط لازم برای باز ماندن اتصال است
        action = message.get("action")
        if action == "ping":
            with contextlib.suppress(Exception):
                await connection.send(json.dumps({"action": "pong", "pong": message.get("ping")}))
            return
        if action == "pong":
            return  # پاسخ ping کلاینت؛ فقط نشانهٔ زنده بودن است

        message_type = message.get("type")
        if message_type == "tick":
            ticker = LBankParser.parse_ws_tick(message)
            if ticker is not None and self._on_ticker is not None:
                self._safe_callback(self._on_ticker, ticker)
        elif message_type == "kbar":
            parsed = LBankParser.parse_ws_kbar(message)
            if parsed is not None and self._on_candle is not None:
                symbol, candle = parsed
                slot = str((message.get("kbar") or {}).get("slot", ""))
                timeframe = self._timeframe_from_slot(slot)
                self._safe_callback(self._on_candle, symbol, timeframe, candle)
        elif message_type == "depth":
            symbol = LBankParser.to_internal_symbol(str(message.get("pair", "")))
            orderbook = LBankParser.parse_ws_depth(symbol, message)
            if orderbook is not None and self._on_orderbook is not None:
                self._safe_callback(self._on_orderbook, orderbook)

    @staticmethod
    def _safe_callback(callback: Callable[..., None], *args: Any) -> None:
        """فراخوانی امن شنونده؛ خطای آن اتصال را قطع نمی‌کند."""
        try:
            callback(*args)
        except Exception:  # noqa: BLE001
            logger.exception("WebSocket callback failed")

    @staticmethod
    def _timeframe_from_slot(slot: str) -> str:
        """تبدیل نام بازه پروتکل (مثل 1min) به کد داخلی (1m)."""
        for internal, ws_name in WS_KBAR_MAP.items():
            if ws_name == slot:
                return internal
        return slot

    # ------------------------------------------------------------------
    # اشتراک‌ها
    # ------------------------------------------------------------------
    async def _resubscribe_all(self) -> None:
        """
        ثبت مجدد تمام اشتراک‌ها پس از برقراری اتصال.

        این متد قلب قابلیت «ادامه بدون Restart» است.
        """
        if not self._subscriptions or self._connection is None:
            return
        for subscription in list(self._subscriptions):
            connection = self._connection
            if connection is None:
                return
            with contextlib.suppress(Exception):
                await connection.send(json.dumps(subscription.to_message()))
            await asyncio.sleep(SUBSCRIBE_PACING)
        logger.info("Resubscribed to %d WebSocket channels", len(self._subscriptions))

    async def _send_subscription(self, subscription: Subscription, *, subscribe: bool) -> None:
        """ارسال پیام اشتراک یا لغو اشتراک در صورت برقرار بودن اتصال."""
        if self._connection is None:
            return  # پس از اتصال، به‌صورت خودکار ثبت خواهد شد
        payload = subscription.to_message() if subscribe else subscription.to_unsubscribe_message()
        with contextlib.suppress(Exception):
            await self._connection.send(json.dumps(payload))

    async def subscribe_ticker(self, symbol: str) -> None:
        """اشتراک قیمت لحظه‌ای یک نماد."""
        subscription = Subscription("tick", LBankParser.to_exchange_symbol(symbol))
        async with self._lock:
            if subscription in self._subscriptions:
                return
            self._subscriptions.add(subscription)
        await self._send_subscription(subscription, subscribe=True)

    async def unsubscribe_ticker(self, symbol: str) -> None:
        """لغو اشتراک قیمت لحظه‌ای."""
        subscription = Subscription("tick", LBankParser.to_exchange_symbol(symbol))
        async with self._lock:
            self._subscriptions.discard(subscription)
        await self._send_subscription(subscription, subscribe=False)

    async def subscribe_candles(self, symbol: str, timeframe: str) -> None:
        """
        اشتراک کندل زنده یک نماد.

        اگر تایم‌فریم در پروتکل زنده پشتیبانی نشود، هشدار داده می‌شود و
        سیستم به‌جای آن از به‌روزرسانی دوره‌ای REST استفاده می‌کند.
        """
        slot = WS_KBAR_MAP.get(_normalize(timeframe))
        if slot is None:
            logger.warning(
                "Timeframe %s is not available on LBank WebSocket; REST polling will be used", timeframe
            )
            return
        subscription = Subscription("kbar", LBankParser.to_exchange_symbol(symbol), slot)
        async with self._lock:
            if subscription in self._subscriptions:
                return
            self._subscriptions.add(subscription)
        await self._send_subscription(subscription, subscribe=True)

    async def unsubscribe_candles(self, symbol: str, timeframe: str) -> None:
        """لغو اشتراک کندل زنده."""
        slot = WS_KBAR_MAP.get(_normalize(timeframe))
        if slot is None:
            return
        subscription = Subscription("kbar", LBankParser.to_exchange_symbol(symbol), slot)
        async with self._lock:
            self._subscriptions.discard(subscription)
        await self._send_subscription(subscription, subscribe=False)

    async def subscribe_orderbook(self, symbol: str, depth: int = 10) -> None:
        """اشتراک دفتر سفارش زنده."""
        subscription = Subscription("depth", LBankParser.to_exchange_symbol(symbol), str(depth))
        async with self._lock:
            if subscription in self._subscriptions:
                return
            self._subscriptions.add(subscription)
        await self._send_subscription(subscription, subscribe=True)

    async def unsubscribe_all(self) -> None:
        """لغو تمام اشتراک‌ها (مثلاً هنگام تعویض نماد فعال)."""
        async with self._lock:
            subscriptions = list(self._subscriptions)
            self._subscriptions.clear()
        for subscription in subscriptions:
            await self._send_subscription(subscription, subscribe=False)

    @property
    def subscription_count(self) -> int:
        """تعداد اشتراک‌های فعال."""
        return len(self._subscriptions)

    @staticmethod
    def supported_timeframes() -> set[str]:
        """تایم‌فریم‌هایی که کندل زنده آن‌ها در دسترس است."""
        return set(WS_KBAR_MAP) & set(LBANK_TIMEFRAME_MAP)
