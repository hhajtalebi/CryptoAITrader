"""
صفحهٔ «هوش پیش‌بینی» — پنجرهٔ موتور پیش‌بینی چندافقی (v1.11.0).

این صفحه چیزی محاسبه نمی‌کند؛ فقط گزارشِ `PredictiveIntelligenceEngine`
را نشان می‌دهد. همهٔ اعداد از مدل‌های کمی روی دادهٔ واقعی می‌آیند:
    • نردبان ۱۳ افق (۱ دقیقه تا ۷ روز) با توزیع چندک، نه یک عدد
    • رژیم بازار هر تایم‌فریم + مرحلهٔ بازار و احتمال گذار
    • سناریوها، هشدارهای زودهنگام و «چه عوض شد»
    • دقتِ «ثبت‌شده» — فقط از پیش‌بینی‌هایی که با قیمت واقعی حل شده‌اند

صفحه صادق است: افق بدونِ داده با دلیلش «خاموش» نشان داده می‌شود و
وقتی داده‌ای نیست جای خالی را اعلام می‌کند، نه اینکه چیزی بسازد.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from localization import Translator
from ui.pages.base_page import BasePage
from ui.widgets import Card, set_role


class PredictionPage(BasePage):
    """نمایش گزارش موتور هوش پیش‌بینی."""

    title_key = "nav.prediction"
    subtitle_key = "prediction.subtitle"

    #: درخواست بازمحاسبهٔ گزارش برای نماد فعلی
    refresh_requested = Signal()

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._payload: dict[str, Any] | None = None
        self._symbol: str = ""
        self._rows: dict[str, list[QWidget]] = {}
        super().__init__(translator, parent)

    # ------------------------------------------------------------------
    # ساخت
    # ------------------------------------------------------------------
    def build(self) -> None:
        """ساخت نوار کنترل و کارت‌های گزارش."""
        # --- نوار کنترل ---
        controls = QHBoxLayout()
        self.symbol_label = QLabel(self.tr_.tr("prediction.no_symbol"), self)
        self.symbol_label.setObjectName("predictionSymbol")
        self.refresh_button = QPushButton(self.tr_.tr("prediction.refresh"), self)
        set_role(self.refresh_button, "primary")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        controls.addWidget(self.symbol_label, 1)
        controls.addWidget(self.refresh_button)
        self.layout_root().addLayout(controls)

        self.empty_label = QLabel(self.tr_.tr("prediction.empty"), self)
        self.empty_label.setWordWrap(True)
        set_role(self.empty_label, "muted")
        self.layout_root().addWidget(self.empty_label)

        # --- کارت‌ها ---
        self.horizons_card = Card(self.tr_.tr("prediction.horizons_title"), self)
        self.market_card = Card(self.tr_.tr("prediction.market_title"), self)
        self.scenarios_card = Card(self.tr_.tr("prediction.scenarios_title"), self)
        self.warnings_card = Card(self.tr_.tr("prediction.warnings_title"), self)
        self.changed_card = Card(self.tr_.tr("prediction.changed_title"), self)
        self.accuracy_card = Card(self.tr_.tr("prediction.accuracy_title"), self)
        self.timeline_card = Card(self.tr_.tr("prediction.timeline_title"), self)

        for card in (
            self.horizons_card,
            self.market_card,
            self.scenarios_card,
            self.warnings_card,
            self.changed_card,
            self.accuracy_card,
            self.timeline_card,
        ):
            self.layout_root().addWidget(card)

        self._apply_payload()

    # ------------------------------------------------------------------
    # API عمومی
    # ------------------------------------------------------------------
    def set_symbol(self, symbol: str) -> None:
        """نماد فعلی (از کنترلر، همگام با صفحهٔ تحلیل)."""
        self._symbol = symbol or ""
        text = self._symbol if self._symbol else self.tr_.tr("prediction.no_symbol")
        self.symbol_label.setText(text)

    def set_busy(self, busy: bool) -> None:
        """قفل دکمه هنگام محاسبه تا درخواست تکراری روانه نشود."""
        self.refresh_button.setEnabled(not busy)
        if busy:
            self.refresh_button.setText(self.tr_.tr("prediction.computing"))
        else:
            self.refresh_button.setText(self.tr_.tr("prediction.refresh"))

    def update_report(self, payload: dict[str, Any] | None) -> None:
        """نمایش گزارش تازه — None یعنی داده کافی نبود."""
        self._payload = payload
        self._apply_payload()

    # ------------------------------------------------------------------
    # ترجمهٔ مجدد
    # ------------------------------------------------------------------
    def retranslate(self) -> None:
        """بازسازی متن‌ها پس از تغییر زبان."""
        super().retranslate()
        self.refresh_button.setText(self.tr_.tr("prediction.refresh"))
        self.set_symbol(self._symbol)
        titles = {
            self.horizons_card: "prediction.horizons_title",
            self.market_card: "prediction.market_title",
            self.scenarios_card: "prediction.scenarios_title",
            self.warnings_card: "prediction.warnings_title",
            self.changed_card: "prediction.changed_title",
            self.accuracy_card: "prediction.accuracy_title",
            self.timeline_card: "prediction.timeline_title",
        }
        for card, key in titles.items():
            card.set_title(self.tr_.tr(key))
        self._apply_payload()

    # ------------------------------------------------------------------
    # رندر
    # ------------------------------------------------------------------
    def _apply_payload(self) -> None:
        """پرکردن کارت‌ها از payload ذخیره‌شده."""
        payload = self._payload
        self.empty_label.setVisible(payload is None)
        horizons = (payload or {}).get("horizons") or []
        for card in (
            self.horizons_card,
            self.market_card,
            self.scenarios_card,
            self.warnings_card,
            self.changed_card,
            self.accuracy_card,
            self.timeline_card,
        ):
            card.setVisible(payload is not None)
        if payload is None:
            return

        self._render_horizons(payload)
        self._render_market(payload)
        self._render_scenarios(horizons)
        self._render_warnings(payload)
        self._render_changed(payload)
        self._render_accuracy(payload)
        self._render_timeline(payload)

    def _row(self, card: Card, key: str) -> tuple[QWidget, QVBoxLayout]:
        """ساخت ردیف جدید داخل کارت؛ ردیف‌های قبلی پاک می‌شوند."""
        layout = card.body()
        # پاک‌سازی ردیف‌های قبلی همین کارت
        for stale in self._rows.pop(key, []):
            stale.setParent(None)
            stale.deleteLater()
        row = QWidget(card)
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(2)
        layout.addWidget(row)
        self._rows.setdefault(key, []).append(row)
        return row, row_layout

    def _muted(self, text: str) -> QLabel:
        label = QLabel(text, self)
        set_role(label, "muted")
        label.setWordWrap(True)
        return label

    def _render_horizons(self, payload: dict[str, Any]) -> None:
        _, layout = self._row(self.horizons_card, "horizons")
        header = self.tr_.tr("prediction.horizons_hint")
        layout.addWidget(self._muted(header))

        for horizon in payload.get("horizons") or []:
            data = horizon if isinstance(horizon, dict) else horizon.to_dict()
            name = str(data.get("horizon", "?"))
            direction = str(data.get("direction", "uncertain"))
            probability = float(data.get("probability") or 0.0)
            confidence = float(data.get("confidence") or 0.0)
            quantiles = data.get("quantiles") or {}
            volatility = data.get("volatility") or {}
            samples = int(data.get("samples") or 0)
            method = str(data.get("method") or "—")
            agreement = data.get("model_agreement")
            conflict = bool(data.get("conflict"))

            line = QHBoxLayout()
            name_label = QLabel(name, self)
            name_label.setMinimumWidth(52)
            dir_label = QLabel(self.tr_.tr(f"prediction.direction.{direction}",
                                           default=direction), self)
            set_role(dir_label, direction if direction in ("bullish", "bearish", "neutral") else "info")
            prob_label = QLabel(
                "{}%".format(self.tr_.format_number(probability, 0)), self
            )
            line.addWidget(name_label)
            line.addWidget(dir_label)
            line.addWidget(prob_label)
            line.addStretch(1)

            p10 = quantiles.get("p10")
            p50 = quantiles.get("p50")
            p90 = quantiles.get("p90")
            range_text = self.tr_.tr(
                "prediction.range_value",
                default="{low} — {high}",
                low=self.tr_.format_number(float(p10), 4) if p10 is not None else "—",
                high=self.tr_.format_number(float(p90), 4) if p90 is not None else "—",
            )
            detail_parts = [
                self.tr_.tr("prediction.confidence_short", default="Conf") +
                " " + self.tr_.format_number(confidence, 0) + "%",
                self.tr_.tr(f"prediction.method.{method}", default=method),
                self.tr_.tr("prediction.samples", default="Samples") + ": " +
                self.tr_.format_number(samples, 0),
            ]
            if agreement is not None:
                detail_parts.append(
                    self.tr_.tr("prediction.agreement", default="Agreement") + ": " +
                    self.tr_.format_number(float(agreement) * 100, 0) + "%"
                )
            if conflict:
                detail_parts.append(self.tr_.tr("prediction.conflict", default="Conflict"))
            vol_value = volatility.get("forecast_percent") if isinstance(volatility, dict) else None
            if vol_value is not None:
                detail_parts.append(
                    self.tr_.tr("prediction.volatility_short", default="Vol") + ": " +
                    self.tr_.format_number(float(vol_value), 2) + "%"
                )
            if p50 is not None:
                detail_parts.append("P50: " + self.tr_.format_number(float(p50), 4))

            detail = QLabel(" · ".join(detail_parts), self)
            set_role(detail, "muted")
            detail.setWordWrap(True)

            block = QVBoxLayout()
            block.addLayout(line)
            range_label = QLabel(range_text, self)
            range_label.setWordWrap(True)
            block.addWidget(range_label)
            block.addWidget(detail)

            frame = QFrame(self)
            frame.setProperty("role", "card")
            frame.setLayout(block)
            layout.addWidget(frame)

        # افق‌های خاموش — با دلیل، نه پنهان
        for item in payload.get("disabled_horizons") or []:
            data = item if isinstance(item, dict) else item.to_dict()
            label = self._muted(
                self.tr_.tr(
                    "prediction.disabled_row",
                    default="{horizon}: {reason}",
                    horizon=str(data.get("horizon", "?")),
                    reason=str(data.get("reason", "")),
                )
            )
            layout.addWidget(label)

    def _render_market(self, payload: dict[str, Any]) -> None:
        _, layout = self._row(self.market_card, "market")
        tr = self.tr_.tr
        fmt = self.tr_.format_number

        stage = payload.get("market_stage") or {}
        if isinstance(stage, dict) and stage.get("stage"):
            layout.addWidget(QLabel(
                tr("prediction.stage_row", default="Stage: {stage} ({confidence}%)",
                   stage=tr(f"prediction.stage.{stage.get('stage')}",
                            default=str(stage.get("stage"))),
                   confidence=fmt(float(stage.get("confidence") or 0), 0)),
                self,
            ))
        for timeframe, regime in (payload.get("regimes") or {}).items():
            if not isinstance(regime, dict):
                continue
            name = regime.get("regime") or "?"
            direction = int(regime.get("direction") or 0)
            layout.addWidget(QLabel(
                tr("prediction.regime_row", default="{tf}: {regime} (dir {dir})",
                   tf=timeframe,
                   regime=tr(f"prediction.regime.{name}", default=str(name)),
                   dir=fmt(direction, 0)),
                self,
            ))
        mtf = payload.get("multi_timeframe") or {}
        alignment = mtf.get("alignment")
        if alignment:
            layout.addWidget(QLabel(
                tr("prediction.alignment_row", default="Alignment: {value}",
                   value=tr(f"prediction.alignment.{alignment}", default=str(alignment))),
                self,
            ))
        quality = payload.get("data_quality") or {}
        ratio = quality.get("ratio") if isinstance(quality, dict) else None
        if ratio is not None:
            layout.addWidget(self._muted(
                tr("prediction.data_quality", default="Data quality: {value}%",
                   value=fmt(float(ratio) * 100, 0))
            ))
        last_price = payload.get("last_price")
        if last_price:
            layout.addWidget(self._muted(
                tr("prediction.last_price", default="Last price: {price}",
                   price=fmt(float(last_price), 4))
            ))

    def _render_scenarios(self, horizons: list[Any]) -> None:
        _, layout = self._row(self.scenarios_card, "scenarios")
        if not horizons:
            layout.addWidget(self._muted(self.tr_.tr("prediction.no_data")))
            return
        primary = horizons[0]
        data = primary if isinstance(primary, dict) else primary.to_dict()
        layout.addWidget(self._muted(
            self.tr_.tr("prediction.primary_horizon",
                        default="Primary horizon: {horizon}",
                        horizon=str(data.get("horizon", "?")))
        ))
        for scenario in (data.get("scenarios") or {}).get("scenarios") or []:
            if not isinstance(scenario, dict):
                continue
            label = QLabel(
                self.tr_.tr(
                    "prediction.scenario_row",
                    default="{name}: {probability}% — {low} to {high}",
                    name=self.tr_.tr(
                        f"prediction.scenario.{scenario.get('name', '?')}",
                        default=str(scenario.get("name", "?")),
                    ),
                    probability=self.tr_.format_number(
                        float(scenario.get("probability") or 0) * 100, 0
                    ),
                    low=self.tr_.format_number(float(scenario.get("low") or 0), 4),
                    high=self.tr_.format_number(float(scenario.get("high") or 0), 4),
                ),
                self,
            )
            role = scenario.get("name")
            if role in ("bull", "bear", "base"):
                set_role(label, "bullish" if role == "bull" else
                         ("bearish" if role == "bear" else "neutral"))
            label.setWordWrap(True)
            layout.addWidget(label)
        events = data.get("event_pressure")
        if events:
            layout.addWidget(self._muted(
                self.tr_.tr("prediction.event_pressure",
                            default="Event pressure: {value}",
                            value=str(events))
            ))

    def _render_warnings(self, payload: dict[str, Any]) -> None:
        _, layout = self._row(self.warnings_card, "warnings")
        tr = self.tr_.tr
        items: list[str] = []
        for warning in payload.get("warnings") or []:
            items.append(str(warning))
        anomalies = payload.get("anomalies") or {}
        if isinstance(anomalies, dict):
            for anomaly in anomalies.get("anomalies") or []:
                items.append(str(anomaly))
        breakout = payload.get("breakout") or {}
        if isinstance(breakout, dict) and breakout.get("state"):
            items.append(tr("prediction.breakout_state",
                            default="Breakout: {state}",
                            state=str(breakout.get("state"))))
        false_breakout = payload.get("false_breakout") or {}
        if isinstance(false_breakout, dict) and false_breakout.get("risk"):
            items.append(tr("prediction.false_breakout",
                            default="False-breakout risk: {risk}",
                            risk=str(false_breakout.get("risk"))))
        if not items:
            layout.addWidget(self._muted(tr("prediction.no_warnings")))
        for text in items:
            label = QLabel(text, self)
            label.setWordWrap(True)
            layout.addWidget(label)

    def _render_changed(self, payload: dict[str, Any]) -> None:
        _, layout = self._row(self.changed_card, "changed")
        tr = self.tr_.tr
        changed = payload.get("what_changed")
        if not isinstance(changed, dict):
            layout.addWidget(self._muted(tr("prediction.no_change_data")))
            return
        probability = changed.get("probability_delta")
        if probability is not None:
            layout.addWidget(QLabel(
                tr("prediction.probability_delta",
                   default="Probability change: {value}",
                   value="{}{}".format(
                       "+" if float(probability) >= 0 else "",
                       self.tr_.format_number(float(probability), 0),
                   )),
                self,
            ))
        if changed.get("direction_changed"):
            layout.addWidget(QLabel(tr("prediction.direction_changed"), self))
        for factor in changed.get("changed_factors") or []:
            if not isinstance(factor, dict):
                continue
            layout.addWidget(QLabel(
                tr("prediction.factor_row",
                   default="{name}: {before} → {after} ({direction})",
                   name=str(factor.get("name", "?")),
                   before=self.tr_.format_number(float(factor.get("before") or 0), 1),
                   after=self.tr_.format_number(float(factor.get("after") or 0), 1),
                   direction=tr(f"prediction.factor_dir.{factor.get('direction', '?')}",
                                default=str(factor.get("direction", "?")))),
                self,
            ))

    def _render_accuracy(self, payload: dict[str, Any]) -> None:
        _, layout = self._row(self.accuracy_card, "accuracy")
        tr = self.tr_.tr
        fmt = self.tr_.format_number
        accuracy = payload.get("accuracy") or {}
        resolved = accuracy.get("resolved")
        if not resolved:
            layout.addWidget(self._muted(tr("prediction.no_resolved")))
            return
        layout.addWidget(QLabel(
            tr("prediction.accuracy_row",
               default="Resolved: {count} — direction {dir}% — range {rng}% — Brier {brier}",
               count=fmt(int(resolved), 0),
               dir=fmt(float(accuracy.get("direction_accuracy") or 0), 1),
               rng=fmt(float(accuracy.get("range_accuracy") or 0), 1),
               brier=fmt(float(accuracy.get("brier") or 0), 3)),
            self,
        ))
        for name, health in (payload.get("model_health") or {}).items():
            if not isinstance(health, dict):
                continue
            layout.addWidget(self._muted(
                tr("prediction.health_row",
                   default="{model}: {acc}% ({status})",
                   model=str(name),
                   acc=fmt(float(health.get("accuracy") or 0), 1),
                   status=tr(f"prediction.health.{health.get('status', '?')}",
                             default=str(health.get("status", "?"))))
            ))

    def _render_timeline(self, payload: dict[str, Any]) -> None:
        _, layout = self._row(self.timeline_card, "timeline")
        entries = payload.get("timeline") or []
        if not entries:
            layout.addWidget(self._muted(self.tr_.tr("prediction.no_timeline")))
            return
        for entry in entries[-12:]:
            if not isinstance(entry, dict):
                continue
            layout.addWidget(QLabel(
                self.tr_.tr(
                    "prediction.timeline_row",
                    default="{when} — {direction} {probability}%",
                    when=str(entry.get("created_at", "")),
                    direction=self.tr_.tr(
                        f"prediction.direction.{entry.get('direction', 'uncertain')}",
                        default=str(entry.get("direction", "?")),
                    ),
                    probability=self.tr_.format_number(
                        float(entry.get("probability") or 0), 0
                    ),
                ),
                self,
            ))


__all__ = ["PredictionPage"]
