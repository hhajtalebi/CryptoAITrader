"""
آزمون صفحهٔ «هوش پیش‌بینی» و ابزارهای عامل AI (v1.11.0).

سه چیز محافظت می‌شود:
    • صفحه فقط «نمایش‌دهنده» است — payload درست، ردیف درست.
    • افق‌های خاموش با دلیل دیده می‌شوند، نه پنهان.
    • ابزارهای get_prediction_report / get_prediction_accuracy بدون
      موتور، صادقانه خطا می‌دهند و با موتور، دادهٔ واقعی برمی‌گردانند.
"""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from localization import Translator
from tests.conftest import destroy_window
from ui.pages.prediction_page import PredictionPage


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def translator() -> Translator:
    instance = Translator("fa")
    instance.load()
    return instance


@pytest.fixture()
def page(qt_app: QApplication, translator: Translator) -> PredictionPage:
    instance = PredictionPage(translator)
    try:
        yield instance
    finally:
        destroy_window(instance, qt_app)


def sample_payload() -> dict[str, Any]:
    """گزارش نمونه با همان کلیدهای IntelligenceReport.to_dict."""
    return {
        "symbol": "BTC/USDT",
        "generated_at": "2026-09-22T12:00:00+00:00",
        "last_price": 64000.0,
        "horizons": [
            {
                "horizon": "1h",
                "direction": "bullish",
                "probability": 63,
                "confidence": 58,
                "quantiles": {"p10": 63500, "p25": 63700, "p50": 64000,
                              "p75": 64300, "p90": 64600},
                "expected_range": {"low": 63500, "high": 64600},
                "method": "empirical",
                "samples": 480,
                "volatility": {"forecast_percent": 1.4},
                "models": [],
                "model_agreement": 0.83,
                "conflict": False,
                "scenarios": {
                    "scenarios": [
                        {"name": "bull", "probability": 0.38, "low": 64300, "high": 64800},
                        {"name": "base", "probability": 0.44, "low": 63800, "high": 64300},
                        {"name": "bear", "probability": 0.18, "low": 63300, "high": 63800},
                    ]
                },
                "event_pressure": None,
                "reasons": ["رژیم روندی صعودی در ۱ ساعت"],
            }
        ],
        "disabled_horizons": [{"horizon": "7d", "reason": "insufficient_history_1d"}],
        "regimes": {"1h": {"regime": "strong_trend_up", "confidence": 72, "direction": 1}},
        "market_stage": {"stage": "MARKUP", "confidence": 66},
        "regime_transition": {},
        "multi_timeframe": {"alignment": "aligned", "per_timeframe": {}},
        "breakout": {"state": "none"},
        "false_breakout": {},
        "anomalies": {},
        "warnings": ["نوسان بالا"],
        "contributors": [],
        "cross_asset": None,
        "timeline": [],
        "what_changed": {
            "probability_delta": -8,
            "direction_changed": False,
            "changed_factors": [
                {"name": "momentum", "before": 12.0, "after": 3.0, "direction": "down"}
            ],
        },
        "accuracy": {"resolved": 12, "direction_accuracy": 58.3,
                     "range_accuracy": 41.6, "brier": 0.21},
        "model_health": {"statistical": {"accuracy": 60.0, "status": "good",
                                         "samples": 12}},
        "data_quality": {"ratio": 0.99},
    }


def _all_texts(widget) -> list[str]:  # noqa: ANN001
    """همهٔ متن‌های QLabel داخل درخت ویجت (برای اطمینان از رندر)."""
    from PySide6.QtWidgets import QLabel

    texts: list[str] = []
    if isinstance(widget, QLabel):
        texts.append(widget.text())
    for child in widget.findChildren(QLabel):
        texts.append(child.text())
    return texts


class TestPredictionPage:
    def test_builds_and_shows_empty(self, page: PredictionPage) -> None:
        assert page.empty_label.isVisibleTo(page) or not page._payload
        assert page.refresh_button.text()

    def test_update_report_renders_horizons(self, page: PredictionPage) -> None:
        page.update_report(sample_payload())
        # کارت‌ها نمایان و ردیف افق ساخته شده
        assert page.horizons_card.isVisibleTo(page)
        assert page._rows["horizons"]
        texts = _all_texts(page.horizons_card)
        assert any("1h" in text for text in texts)
        assert any("۶۳" in text or "63" in text for text in texts)

    def test_disabled_horizons_visible_with_reason(self, page: PredictionPage) -> None:
        page.update_report(sample_payload())
        texts = _all_texts(page.horizons_card)
        assert any("7d" in text for text in texts)
        assert any("insufficient_history_1d" in text for text in texts)

    def test_reset_to_none_shows_empty(self, page: PredictionPage) -> None:
        page.update_report(sample_payload())
        page.update_report(None)
        assert not page.horizons_card.isVisibleTo(page)
        assert page.empty_label.isVisibleTo(page)

    def test_busy_locks_refresh(self, page: PredictionPage) -> None:
        page.set_busy(True)
        assert not page.refresh_button.isEnabled()
        page.set_busy(False)
        assert page.refresh_button.isEnabled()

    def test_retranslate_keeps_data(self, page: PredictionPage,
                                    translator: Translator) -> None:
        page.update_report(sample_payload())
        page.retranslate()
        assert page._payload is not None
        assert any("1h" in text for text in _all_texts(page.horizons_card))

    def test_symbol_sync(self, page: PredictionPage) -> None:
        page.set_symbol("ETH/USDT")
        assert page.symbol_label.text() == "ETH/USDT"

    def test_all_titles_translated(self, page: PredictionPage) -> None:
        for key in (
            "prediction.horizons_title",
            "prediction.market_title",
            "prediction.scenarios_title",
            "prediction.warnings_title",
            "prediction.changed_title",
            "prediction.accuracy_title",
            "prediction.timeline_title",
            "prediction.subtitle",
            "nav.prediction",
        ):
            value = page.tr_.tr(key)
            assert value and not value.startswith("prediction."), key


class TestPredictionTools:
    """ابزارهای عامل — بدون موتور صادقانه خطا، با موتور دادهٔ واقعی."""

    def _toolset(self, prediction_engine: Any = None):  # noqa: ANN202
        from ai.tools.market_tools import MarketToolset

        class FakeMarket:  # noqa: D106
            exchange_name = "test"

            async def get_candles(self, symbol: str, timeframe: str,
                                  limit: int = 600):  # noqa: ANN201
                return []

        return MarketToolset(FakeMarket(), _FakeIndicators(),
                             prediction_engine=prediction_engine)

    def test_report_without_engine_raises(self) -> None:
        import asyncio

        toolset = self._toolset()
        with pytest.raises(RuntimeError):
            asyncio.run(toolset.get_prediction_report("BTC/USDT"))

    def test_report_with_engine(self) -> None:
        import asyncio

        toolset = self._toolset(prediction_engine=_FakeEngine())
        payload = asyncio.run(toolset.get_prediction_report("BTC/USDT"))
        assert payload["available"] is True
        assert payload["symbol"] == "BTC/USDT"
        assert payload["horizons"]
        assert "note" in payload

    def test_report_none_when_no_data(self) -> None:
        import asyncio

        toolset = self._toolset(prediction_engine=_FakeEngine(returns_none=True))
        payload = asyncio.run(toolset.get_prediction_report("BTC/USDT"))
        assert payload["available"] is False
        assert payload["reason"] == "insufficient_market_data"

    def test_accuracy_snapshot(self) -> None:
        import asyncio

        toolset = self._toolset(prediction_engine=_FakeEngine())
        payload = asyncio.run(toolset.get_prediction_accuracy("BTC/USDT"))
        assert payload["available"] is True
        assert payload["resolved"] == 5
        assert "model_health" in payload

    def test_tool_definitions_registered(self) -> None:
        toolset = self._toolset()
        names = set(toolset.tool_names)  # در این کلاس property است
        assert "get_prediction_report" in names
        assert "get_prediction_accuracy" in names
        # تعریف‌های JSON-Schema هم برای Function Calling ثبت شده‌اند
        from ai.tools.market_tools import MarketToolset as _MT

        definitions = {tool.name for tool in _MT.get_definitions()}
        assert {"get_prediction_report", "get_prediction_accuracy"} <= definitions


class _FakeIndicators:  # noqa: D101
    def calculate_many(self, names, candles, timeframe, symbol="", parameters=None):  # noqa: ANN202
        return {}


class _FakeEngine:  # noqa: D101
    def __init__(self, returns_none: bool = False) -> None:
        self._returns_none = returns_none

    async def assess(self, symbol: str, **_: Any):  # noqa: ANN202
        if self._returns_none:
            return None
        from types import SimpleNamespace

        return SimpleNamespace(to_dict=lambda: sample_payload())

    async def accuracy_snapshot(self, symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "available": True,
            "resolved": 5,
            "direction_accuracy": 60.0,
            "range_accuracy": 40.0,
            "brier": 0.2,
            "model_health": {"statistical": {"accuracy": 60.0, "status": "good"}},
        }
