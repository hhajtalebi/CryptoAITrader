"""دو اتصال مستقل به همان provider؛ افزونگی بدون مخلوط‌کردن صرافی‌ها.

قطع یک اتصال، دیگری را نمی‌بندد. watchdog سکوت داده را از ping تفکیک
می‌کند؛ هیچ اتصال یا سود دائمی تضمین نمی‌شود. REST همچنان مسیر جایگزین است.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.core.constants import ConnectionStatus

logger = logging.getLogger(__name__)


class RedundantStream:
    def __init__(self, factory, *, on_ticker, on_candle, on_status_change,
                 connections: int = 2, silent_seconds: float = 60.0) -> None:
        self._ticker_callback = on_ticker
        self._candle_callback = on_candle
        self._status_callback = on_status_change
        self._silent_seconds = silent_seconds
        self._clients: list[Any] = []
        self._last_data: list[float] = []
        self._tickers: set[str] = set()
        self._candles: set[tuple[str, str]] = set()
        self._seen: dict[tuple, tuple] = {}
        self._task = None
        self._running = False
        self._last_status = ConnectionStatus.DISCONNECTED
        for index in range(max(1, min(3, connections))):
            try:
                client = factory(
                    on_ticker=lambda ticker, i=index: self._on_ticker(i, ticker),
                    on_candle=lambda symbol, tf, candle, i=index: self._on_candle(i, symbol, tf, candle),
                    on_status_change=lambda status: self._notify_status(),
                )
            except Exception:
                logger.warning("Could not construct redundant stream", exc_info=True)
                break
            if client is None or any(client is item for item in self._clients):
                break
            self._clients.append(client)
            self._last_data.append(time.monotonic())

    @property
    def available(self) -> bool:
        return bool(self._clients)

    @property
    def status(self) -> ConnectionStatus:
        if not self._running:
            return ConnectionStatus.DISCONNECTED
        now = time.monotonic()
        for index, client in enumerate(self._clients):
            if client.status is ConnectionStatus.CONNECTED and (
                not self._tickers and not self._candles
                or now - self._last_data[index] < self._silent_seconds
            ):
                return ConnectionStatus.CONNECTED
        return ConnectionStatus.RECONNECTING

    def stats(self) -> dict:
        result = {"connections": len(self._clients), "connected": sum(
            client.status is ConnectionStatus.CONNECTED
            and time.monotonic() - self._last_data[index] < self._silent_seconds
            for index, client in enumerate(self._clients)
        ), "status": self.status.value}
        # عیب‌یابی (۲.۳.۲): نشانی فعلی و آخرین علت شکست هر اتصال، اگر کلاینت ارائه دهد.
        endpoints = [str(getattr(client, "current_url", "") or "") for client in self._clients]
        errors = [str(getattr(client, "last_error", "") or "") for client in self._clients]
        if any(endpoints):
            result["endpoints"] = endpoints
        last_error = next((error for error in errors if error), "")
        if last_error:
            result["last_error"] = last_error
        return result

    def _notify_status(self) -> None:
        status = self.status
        if status != self._last_status:
            self._last_status = status
            self._status_callback(status)

    def _accept(self, key, stamp, signature) -> bool:
        """تیک عقب‌افتاده و نسخهٔ همزمان اتصال دوم نباید قیمت را عقب ببرند."""
        now = time.monotonic()
        previous = self._seen.get(key)
        if previous:
            old_stamp, old_signature, received = previous
            if stamp and old_stamp and stamp < old_stamp:
                return False
            if signature == old_signature and stamp == old_stamp and now - received < 0.25:
                return False
        self._seen[key] = (stamp, signature, now)
        return True

    def _on_ticker(self, index, ticker) -> None:
        self._last_data[index] = time.monotonic()
        stamp = float(ticker.timestamp or 0)
        if stamp > 100_000_000_000:
            stamp /= 1000
        if self._accept(("tick", ticker.symbol), stamp,
                        (ticker.last_price, ticker.volume_24h, ticker.change_percent)):
            self._ticker_callback(ticker)
        self._notify_status()

    def _on_candle(self, index, symbol, timeframe, candle) -> None:
        self._last_data[index] = time.monotonic()
        if self._accept(("candle", symbol, timeframe), candle.timestamp,
                        (candle.open, candle.high, candle.low, candle.close, candle.volume)):
            self._candle_callback(symbol, timeframe, candle)
        self._notify_status()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        await self._broadcast("start")
        self._task = asyncio.create_task(self._watchdog(), name="redundant-stream-watchdog")
        self._notify_status()

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        await self._broadcast("stop")
        self._notify_status()

    async def _broadcast(self, method: str, *args) -> None:
        results = await asyncio.gather(
            *(getattr(client, method)(*args) for client in self._clients), return_exceptions=True
        )
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Stream %s failed: %s", method, type(result).__name__)

    async def _check_health(self) -> None:
        for index, client in enumerate(self._clients):
            task = getattr(client, "_task", None)
            dead_task = task is not None and task.done()
            silent = (self._tickers or self._candles) and (
                time.monotonic() - self._last_data[index] > self._silent_seconds
            )
            if dead_task or silent:
                try:
                    await client.stop()
                    self._last_data[index] = time.monotonic()
                    await client.start()
                    for symbol in self._tickers:
                        await client.subscribe_ticker(symbol)
                    for symbol, timeframe in self._candles:
                        await client.subscribe_candles(symbol, timeframe)
                except Exception:
                    logger.warning("Stream recovery failed", exc_info=True)
        self._notify_status()

    async def _watchdog(self) -> None:
        while self._running:
            await asyncio.sleep(5)
            await self._check_health()

    async def subscribe_ticker(self, symbol) -> None:
        self._tickers.add(symbol)
        await self._broadcast("subscribe_ticker", symbol)

    async def unsubscribe_ticker(self, symbol) -> None:
        self._tickers.discard(symbol)
        self._seen.pop(("tick", symbol), None)
        await self._broadcast("unsubscribe_ticker", symbol)

    async def subscribe_candles(self, symbol, timeframe) -> None:
        self._candles.add((symbol, timeframe))
        await self._broadcast("subscribe_candles", symbol, timeframe)

    async def unsubscribe_candles(self, symbol, timeframe) -> None:
        self._candles.discard((symbol, timeframe))
        self._seen.pop(("candle", symbol, timeframe), None)
        await self._broadcast("unsubscribe_candles", symbol, timeframe)

    async def unsubscribe_all(self) -> None:
        self._tickers.clear()
        self._candles.clear()
        self._seen.clear()
        await self._broadcast("unsubscribe_all")
