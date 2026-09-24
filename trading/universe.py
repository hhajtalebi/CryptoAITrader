"""Bounded, deterministic rotation across liquid markets and favorites.

Ranking is an input filter, not a prediction or a promise of profitability.
"""
from __future__ import annotations

import math


class RotatingUniverse:
    def __init__(self):
        self._offsets = {}

    def _take(self, key, symbols, count):
        symbols = list(dict.fromkeys(symbols))
        if not symbols or count <= 0:
            return []
        start = self._offsets.get(key, 0) % len(symbols)
        rotated = symbols[start:] + symbols[:start]
        result = rotated[:count]
        self._offsets[key] = (start + len(result)) % len(symbols)
        return result

    def select(self, tickers, *, limit, selected=None, favorites=(), min_turnover=0):
        limit = max(1, min(120, int(limit)))
        if selected is not None:
            return self._take("selected", [s.strip().upper() for s in selected if s.strip()], limit)
        valid = [t for t in tickers if math.isfinite(float(t.turnover_24h or 0))
                 and float(t.turnover_24h or 0) >= min_turnover and float(t.last_price or 0) > 0]
        ranked = [t.symbol for t in sorted(valid, key=lambda t: t.turnover_24h, reverse=True)]
        available = set(ranked)
        favored = [s for s in favorites if s in available]
        picked = self._take("favorites", favored, max(1, limit // 2))
        # Reserve room for market exploration even with a large watchlist.
        rest = [s for s in ranked if s not in picked]
        return picked + self._take("market", rest, limit - len(picked))
