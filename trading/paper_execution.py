"""بستن معاملهٔ کاغذی خارج از موتور، با قیمت تازه و کارمزد خروج واقعی.

این مسیر هرگز رکورد live را مانند یک معاملهٔ شبیه‌سازی‌شده نمی‌بندد.
"""
from __future__ import annotations

import asyncio


async def close_paper_position(repository, trade_id, ticks, refresh_price, *,
                               slippage_percent=0.0, fee_rate=0.0006):
    record = repository.get_by_id(trade_id)
    if record is None:
        return None

    def get(key, default=None):
        return record.get(key, default) if isinstance(record, dict) else getattr(record, key, default)

    if get("status") != "open":
        return None
    if get("mode", "paper") != "paper":
        raise RuntimeError("Live positions must be closed through the verified live gateway")
    symbol = get("symbol", "")
    if ticks.is_stale(symbol):
        await asyncio.wait_for(refresh_price(symbol), timeout=5.0)
    if ticks.is_stale(symbol):
        raise RuntimeError("stale_data")
    quote = ticks.get(symbol)
    side = get("side", "long")
    price = quote.exit_price(side)
    price *= 1 - slippage_percent / 100 if side == "long" else 1 + slippage_percent / 100
    if price <= 0:
        raise RuntimeError("no_price")
    extra = get("extra", {}) or {}
    rate = float(extra.get("fee_rate", fee_rate))
    return repository.close_trade(trade_id, exit_price=price,
                                  fee=float(get("quantity", 0)) * price * rate,
                                  note="manual")
