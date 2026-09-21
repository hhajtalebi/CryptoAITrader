"""
کلاینت WebSocket صرافی Toobit با اتصال مجدد خودکار.

چرا وجود دارد؟
    تا پیش از این، توبیت `supports_websocket=True` اعلام می‌کرد ولی هیچ
    کلاینتی نداشت و موتور بازار به‌صورت ثابت کلاینت LBank را می‌ساخت؛
    یعنی کاربرِ توبیت داده زندهٔ صرافی دیگری را می‌دید. این ماژول آن شکاف
    را می‌بندد.

پروتکل (با اتصال واقعی به سرور راستی‌آزمایی شد — ۱۴۰۴/۰۶/۲۲):

    اشتراک تیکر :
        {"symbol":"BTCUSDT","topic":"realtimes","event":"sub",
         "params":{"binary":false}}
    اشتراک کندل :
        {"symbol":"BTCUSDT","topic":"kline_1m","event":"sub",
         "params":{"binary":false}}
    لغو اشتراک  : همان پیام با "event":"cancel"

    پاسخ تیکر (topic="realtimes"):
        {"symbol":"BTCUSDT","topic":"realtimes","data":[{"t":...,"s":"BTCUSDT",
         "c":"77283.79","h":...,"l":...,"o":...,"v":...,"qv":...,"m":"-0.0009"}]}
        نکته: `m` نسبت است نه درصد (‎-0.0009‎ یعنی ‎-0.09٪‎) و باید در ۱۰۰ ضرب شود.

    پاسخ کندل (topic="kline"، نه "kline_1m"):
        {"symbol":"BTCUSDT","klineType":"1m","topic":"kline","params":{...,
         "klineType":"1m"},"data":[{"t":...,"o":...,"h":...,"l":...,"c":...,"v":...}]}
        نکته: کلید `klineType` گاهی فقط داخل `params` می‌آید، پس هر دو جا
        خوانده می‌شود.

    نماد نامعتبر: {"code":"-100010","desc":"Invalid Symbols!"}

تفاوت مهم با LBank:
    سرور توبیت **ping نمی‌فرستد** (در آزمون ۷۵ ثانیه‌ای هیچ فریم ping
    نیامد). بنابراین زنده‌نگه‌داشتن اتصال بر عهدهٔ خود کلاینت است و از
    ping داخلیِ کتابخانهٔ websockets استفاده می‌کنیم.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from app.core.constants import ConnectionStatus
from app.core.models import Candle, Ticker
from app.exceptions import TimeframeError
from app.logging import get_logger
from market.providers.toobit.constants import TOOBIT_TIMEFRAME_MAP, TOOBIT_WS_URL
from market.providers.toobit.parser import ToobitParser
from market.timeframes import normalize_timeframe

logger = get_logger(__name__)

#: بازهٔ ping داخلی. سرور توبیت خودش ping نمی‌فرستد، پس کلاینت باید
#: اتصال را زنده نگه دارد وگرنه میان‌راهی‌ها آن را می‌بندند.
PING_INTERVAL = 20.0

#: اگر این مدت هیچ دادهٔ کاربردی نرسد، اتصال «مرده» فرض می‌شود.
#: بلندتر از LBank است چون فریم‌های تیکر توبیت هر ۵ ثانیه می‌آیند ولی
#: بازارهای کم‌رمق ممکن است دقایقی ساکت بمانند.
STALE_TIMEOUT = 120.0


def _normalize(timeframe: str) -> str:
    """
    یکدست‌سازی کد تایم‌فریم.

    مثل نسخهٔ LBank، کد ناشناخته اینجا خطا نمی‌دهد؛ فراخواننده با `None`
    گرفتن از نگاشت تصمیم می‌گیرد که به REST برگردد.
    """
    try:
        return normalize_timeframe(timeframe)
    except TimeframeError:
        return timeframe.strip()


@dataclass(frozen=True, slots=True)
class ToobitSubscription:
    """
    یک اشتراک فعال.

    Hashable است تا مجموعهٔ اشتراک‌ها نگه داشته شود و پس از اتصال مجدد،
    همه دوباره ثبت شوند — همان چیزی که «ادامه بدون Restart» را ممکن
    می‌کند.
    """

    topic: str  # realtimes | kline_1m | depth
    symbol: str  # قالب صرافی، مثل BTCUSDT

    def to_message(self, *, subscribe: bool = True) -> dict[str, Any]:
        """ساخت پیام اشتراک یا لغو اشتراک مطابق پروتکل توبیت."""
        return {
            "symbol": self.symbol,
            "topic": self.topic,
            "event": "sub" if subscribe else "cancel",
            "params": {"binary": False},
        }


class ToobitWebSocketClient:
    """
    مدیریت اتصال زنده به Toobit.

    فراخوان‌های برگشتی اختیاری‌اند و خطای آن‌ها اتصال را نمی‌شکند؛ فقط
    لاگ می‌شود.
    """

    def __init__(
        self,
        url: str = TOOBIT_WS_URL,
        *,
        on_ticker: Callable[[Ticker], None] | None = None,
        on_candle: Callable[[str, str, Candle], None] | None = None,
        on_status_change: Callable[[ConnectionStatus], None] | None = None,
        max_reconnect_delay: float = 60.0,
    ) -> None:
        self._url = url
        self._on_ticker = on_ticker
        self._on_candle = on_candle
        self._on_status_change = on_status_change
        self._max_reconnect_delay = max_reconnect_delay

        self._subscriptions: set[ToobitSubscription] = set()
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
        """تعداد دفعات اتصال مجدد (برای بخش عیب‌یابی)."""
        return self._reconnect_count

    @property
    def subscription_count(self) -> int:
        """تعداد اشتراک‌های فعال."""
        return len(self._subscriptions)

    def _set_status(self, status: ConnectionStatus) -> None:
        """تغییر وضعیت و اطلاع‌رسانی به شنونده."""
        if self._status is status:
            return
        self._status = status
        logger.info("Toobit WebSocket status: %s", status.value)
        if self._on_status_change is not None:
            try:
                self._on_status_change(status)
            except Exception:  # noqa: BLE001 - خطای شنونده نباید اتصال را بشکند
                logger.exception("WebSocket status callback failed")

    def _safe_callback(self, callback: Callable[..., None], *args: Any) -> None:
        """اجرای فراخوان برگشتی بدون اینکه خطایش اتصال را قطع کند."""
        try:
            callback(*args)
        except Exception:  # noqa: BLE001 - خطای مصرف‌کننده نباید جریان را بشکند
            logger.exception("WebSocket data callback failed")

    # ------------------------------------------------------------------
    # چرخه عمر
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """شروع حلقهٔ اتصال در پس‌زمینه."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_forever(), name="toobit-ws")
        logger.debug("Toobit WebSocket loop started")

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
        logger.debug("Toobit WebSocket loop stopped")

    async def _run_forever(self) -> None:
        """
        حلقهٔ اصلی: اتصال، دریافت پیام و در صورت قطع، تلاش مجدد.

        تأخیر تلاش مجدد نمایی است و نویز تصادفی دارد تا در قطعی سراسری،
        همهٔ کلاینت‌ها هم‌زمان به سرور هجوم نبرند.
        """
        attempt = 0
        while self._running:
            try:
                self._set_status(
                    ConnectionStatus.RECONNECTING if attempt else ConnectionStatus.CONNECTING
                )
                # ping داخلی روشن است چون سرور توبیت ping نمی‌فرستد.
                async with websockets.connect(
                    self._url,
                    open_timeout=20,
                    ping_interval=PING_INTERVAL,
                    ping_timeout=PING_INTERVAL,
                    close_timeout=5,
                ) as connection:
                    self._connection = connection
                    attempt = 0
                    self._set_status(ConnectionStatus.CONNECTED)
                    await self._resubscribe_all()
                    await self._receive_loop(connection)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - هر خطایی باید به تلاش مجدد برسد
                logger.warning(
                    "Toobit WebSocket error: %s: %s", exc.__class__.__name__, exc
                )
            finally:
                self._connection = None

            if not self._running:
                break

            self._set_status(ConnectionStatus.DISCONNECTED)
            attempt += 1
            self._reconnect_count += 1
            delay = min(self._max_reconnect_delay, 2 ** min(attempt, 6))
            delay += random.uniform(0, delay * 0.3)
            logger.info(
                "Reconnecting to Toobit WebSocket in %.1fs (attempt %d)", delay, attempt
            )
            await asyncio.sleep(delay)

    async def _receive_loop(self, connection: Any) -> None:
        """
        دریافت و پردازش پیام‌ها تا زمان قطع اتصال.

        سکوت طولانی یعنی اتصال زامبی؛ بسته می‌شود تا چرخهٔ اتصال مجدد
        آغاز شود.
        """
        while self._running:
            try:
                raw = await asyncio.wait_for(connection.recv(), timeout=STALE_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning(
                    "No Toobit WebSocket data for %.0fs; forcing reconnect", STALE_TIMEOUT
                )
                await connection.close()
                return
            except ConnectionClosed:
                logger.info("Toobit WebSocket closed by server")
                return

            await self._handle_message(raw, connection)

    async def _handle_message(self, raw: str | bytes, connection: Any) -> None:
        """تجزیهٔ یک پیام دریافتی و فراخوانی شنوندهٔ مناسب."""
        try:
            message = json.loads(raw)
        except (ValueError, TypeError):
            logger.debug("Ignoring non-JSON Toobit frame")
            return
        if not isinstance(message, dict):
            return

        # سرور توبیت ping نمی‌فرستد، ولی اگر روزی بفرستد پاسخ می‌دهیم تا
        # اتصال قطع نشود. هزینه‌اش ناچیز است و از یک قطعیِ مرموز جلوگیری
        # می‌کند.
        if "ping" in message:
            with contextlib.suppress(Exception):
                await connection.send(json.dumps({"pong": message["ping"]}))
            return

        # خطاهای سطح پروتکل: {"code":"-100010","desc":"Invalid Symbols!"}
        if "code" in message and "data" not in message:
            logger.warning(
                "Toobit WebSocket rejected a request: %s %s",
                message.get("code"),
                message.get("desc") or message.get("msg") or "",
            )
            return

        topic = str(message.get("topic") or "")
        if topic == "realtimes":
            ticker = ToobitParser.parse_ws_ticker(message)
            if ticker is not None and self._on_ticker is not None:
                self._safe_callback(self._on_ticker, ticker)
        elif topic.startswith("kline"):
            parsed = ToobitParser.parse_ws_kline(message)
            if parsed is not None and self._on_candle is not None:
                symbol, timeframe, candle = parsed
                self._safe_callback(self._on_candle, symbol, timeframe, candle)

    # ------------------------------------------------------------------
    # اشتراک‌ها
    # ------------------------------------------------------------------
    async def _resubscribe_all(self) -> None:
        """
        ثبت مجدد تمام اشتراک‌ها پس از برقراری اتصال.

        قلب قابلیت «ادامه بدون Restart».
        """
        if not self._subscriptions or self._connection is None:
            return
        for subscription in list(self._subscriptions):
            with contextlib.suppress(Exception):
                await self._connection.send(json.dumps(subscription.to_message()))
        logger.info(
            "Resubscribed to %d Toobit WebSocket channels", len(self._subscriptions)
        )

    async def _send_subscription(
        self, subscription: ToobitSubscription, *, subscribe: bool
    ) -> None:
        """ارسال پیام اشتراک/لغو در صورت برقرار بودن اتصال."""
        if self._connection is None:
            return  # پس از اتصال، خودکار ثبت خواهد شد
        with contextlib.suppress(Exception):
            await self._connection.send(
                json.dumps(subscription.to_message(subscribe=subscribe))
            )

    async def subscribe_ticker(self, symbol: str) -> None:
        """اشتراک قیمت لحظه‌ای یک نماد."""
        subscription = ToobitSubscription(
            "realtimes", ToobitParser.to_exchange_symbol(symbol)
        )
        async with self._lock:
            if subscription in self._subscriptions:
                return
            self._subscriptions.add(subscription)
        await self._send_subscription(subscription, subscribe=True)

    async def unsubscribe_ticker(self, symbol: str) -> None:
        """لغو اشتراک قیمت لحظه‌ای."""
        subscription = ToobitSubscription(
            "realtimes", ToobitParser.to_exchange_symbol(symbol)
        )
        async with self._lock:
            self._subscriptions.discard(subscription)
        await self._send_subscription(subscription, subscribe=False)

    async def subscribe_candles(self, symbol: str, timeframe: str) -> None:
        """
        اشتراک کندل زندهٔ یک نماد.

        تایم‌فریم پشتیبانی‌نشده خطا نمی‌دهد: هشدار می‌دهد و کار به
        نظرسنجی REST سپرده می‌شود.
        """
        slot = TOOBIT_TIMEFRAME_MAP.get(_normalize(timeframe))
        if slot is None:
            logger.warning(
                "Timeframe %s is not available on Toobit WebSocket; REST polling will be used",
                timeframe,
            )
            return
        subscription = ToobitSubscription(
            f"kline_{slot}", ToobitParser.to_exchange_symbol(symbol)
        )
        async with self._lock:
            if subscription in self._subscriptions:
                return
            self._subscriptions.add(subscription)
        await self._send_subscription(subscription, subscribe=True)

    async def unsubscribe_candles(self, symbol: str, timeframe: str) -> None:
        """لغو اشتراک کندل زنده."""
        slot = TOOBIT_TIMEFRAME_MAP.get(_normalize(timeframe))
        if slot is None:
            return
        subscription = ToobitSubscription(
            f"kline_{slot}", ToobitParser.to_exchange_symbol(symbol)
        )
        async with self._lock:
            self._subscriptions.discard(subscription)
        await self._send_subscription(subscription, subscribe=False)

    async def unsubscribe_all(self) -> None:
        """لغو همهٔ اشتراک‌ها (هنگام تعویض نماد فعال)."""
        async with self._lock:
            current = list(self._subscriptions)
            self._subscriptions.clear()
        for subscription in current:
            await self._send_subscription(subscription, subscribe=False)
