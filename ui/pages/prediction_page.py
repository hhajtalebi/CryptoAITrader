"""
صفحهٔ «هوش پیش‌بینی» — داشبورد تحلیلی موتور پیش‌بینی چندافقی (v2.0).

این صفحه چیزی محاسبه نمی‌کند؛ فقط گزارشِ `PredictiveIntelligenceEngine`
را نشان می‌دهد. همهٔ اعداد از مدل‌های کمی روی دادهٔ واقعی می‌آیند:
    • خلاصهٔ تصمیم: جهت، احتمال، اطمینان، رژیم، مرحله، هم‌راستایی MTF
    • نمودار بادبزن چندک افق‌ها (P10/P25/P50/P75/P90) — نه یک عدد
    • جدول کامل ۱۳ افق با توزیع چندک، نوسان و توافق مدل‌ها
    • رژیم بازار هر تایم‌فریم + مرحلهٔ بازار
    • سناریوها، هشدارهای زودهنگام، رخداد شکست/شکست کاذب و «چه عوض شد»
    • دقتِ «ثبت‌شده» — فقط از پیش‌بینی‌هایی که با قیمت واقعی حل شده‌اند
    • خط زمانی پیش‌بینی‌ها

چیدمان واکنش‌گرا (خواستهٔ §۱۰): در صفحهٔ پهن خلاصه|نمودار کنار هم و
بخش‌ها دو ستونی؛ در صفحهٔ باریک همه زیر هم با پیمایش. هیچ داده‌ای
در هیچ عرضی حذف نمی‌شود.

صفحه صادق است: افق بدونِ داده با دلیلش «خاموش» نشان داده می‌شود و
وقتی داده‌ای نیست جای خالی را اعلام می‌کند، نه اینکه چیزی بسازد.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from localization import Translator
from ui.pages.base_page import BasePage
from ui.widgets import (
    Card,
    ResponsiveRow,
    set_role,
    configure_table,
    harden_table,
)
from ui.widgets.charts_mini import ConfidenceRing, QuantileFan

#: ستون‌های جدول افق‌ها (خواستهٔ §۱۰ — همهٔ فیلدهای موجود)
HORIZON_COLUMNS = (
    "horizon", "direction", "probability", "confidence", "p10", "p50", "p90",
    "volatility", "agreement", "samples", "method", "status",
)

#: تایم‌فریم‌های نمایش رژیم به ترتیب نردبان روند
REGIME_TIMEFRAMES = ("4h", "1h", "15m", "5m", "1m", "1d")


class PredictionPage(BasePage):
    """داشبورد تحلیلی گزارش موتور هوش پیش‌بینی."""

    title_key = "nav.prediction"
    subtitle_key = "prediction.subtitle"

    #: درخواست بازمحاسبهٔ گزارش برای نماد فعلی
    refresh_requested = Signal()

    #: در رزولوشن کم، بخش‌ها زیر هم می‌روند و پیمایش لازم است
    scrollable = True

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._payload: dict[str, Any] | None = None
        self._symbol: str = ""
        self._rows: dict[str, list[QWidget]] = {}
        super().__init__(translator, parent)
        if self._scroll is not None:
            self._scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )

    # ------------------------------------------------------------------
    # ساخت
    # ------------------------------------------------------------------
    def build(self) -> None:
        """ساخت داشبورد: خلاصه، نمودار، جدول افق‌ها، بخش‌های تحلیل."""
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

        # --- ردیف ۱: خلاصهٔ تصمیم | نمودار بادبزن چندک ---
        self.summary_card = Card(self.tr_.tr("prediction.summary_title"), self)
        self._build_summary_body()
        self.chart_card = Card(self.tr_.tr("prediction.fan_title"), self)
        self.fan_chart = QuantileFan()
        self.chart_card.body().addWidget(self.fan_chart)
        self.fan_legend = self._muted(
            self.tr_.tr("prediction.fan_legend", default="P10–P90 / P50")
        )
        self.chart_card.body().addWidget(self.fan_legend)
        self.summary_row = ResponsiveRow(self.summary_card, self.chart_card)
        self.layout_root().addWidget(self.summary_row)

        # --- ردیف ۲: جدول افق‌ها (تمام‌عرض) ---
        self.horizons_card = Card(self.tr_.tr("prediction.horizons_title"), self)
        self._build_horizons_body()
        self.layout_root().addWidget(self.horizons_card)

        # --- ردیف ۳: رژیم/MTF | سناریوها ---
        self.market_card = Card(self.tr_.tr("prediction.market_title"), self)
        self.scenarios_card = Card(self.tr_.tr("prediction.scenarios_title"), self)
        self.market_row = ResponsiveRow(self.market_card, self.scenarios_card)
        self.layout_root().addWidget(self.market_row)

        # --- ردیف ۴: هشدارها | دقت و تغییرات ---
        self.warnings_card = Card(self.tr_.tr("prediction.warnings_title"), self)
        self.accuracy_card = Card(self.tr_.tr("prediction.accuracy_title"), self)
        self.warn_row = ResponsiveRow(self.warnings_card, self.accuracy_card)
        self.layout_root().addWidget(self.warn_row)

        # --- ردیف ۵: چه عوض شد + خط زمانی ---
        self.changed_card = Card(self.tr_.tr("prediction.changed_title"), self)
        self.timeline_card = Card(self.tr_.tr("prediction.timeline_title"), self)
        self.changed_row = ResponsiveRow(self.changed_card, self.timeline_card)
        self.layout_root().addWidget(self.changed_row)

        self._apply_payload()

    def _build_horizons_body(self) -> None:
        """
        بدنهٔ پایدار کارت افق‌ها.

        جدول یک‌بار ساخته می‌شود و رندرهای بعدی فقط محتوایش را
        عوض می‌کنند؛ به این ترتیب نوار ابزار جدول (تمام‌صفحه/CSV)
        که `BasePage` هنگام ساخت صفحه وصل می‌کند، حفظ می‌شود و
        ویجت‌ها با هر گزارش دوباره ساخته نمی‌شوند.
        """
        holder = QWidget(self.horizons_card)
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setSpacing(6)
        self.horizons_card.body().addWidget(holder)
        self._rows.setdefault("horizons", []).append(holder)

        self.horizons_table = QTableWidget(0, len(HORIZON_COLUMNS), holder)
        configure_table(self.horizons_table, stretch_column=0)
        harden_table(self.horizons_table, min_row_height=30, min_table_height=160)
        self._retranslate_table_headers()
        holder_layout.addWidget(self.horizons_table)

        self.primary_label = QLabel("", holder)
        set_role(self.primary_label, "info")
        self.primary_label.setWordWrap(True)
        holder_layout.addWidget(self.primary_label)

        self.disabled_label = QLabel("", holder)
        set_role(self.disabled_label, "muted")
        self.disabled_label.setWordWrap(True)
        holder_layout.addWidget(self.disabled_label)

        self._horizons_hint = QLabel(self.tr_.tr("prediction.horizons_hint"), holder)
        set_role(self._horizons_hint, "muted")
        self._horizons_hint.setWordWrap(True)
        holder_layout.addWidget(self._horizons_hint)

    def _build_summary_body(self) -> None:
        """بدنهٔ کارت خلاصه: حلقهٔ اطمینان + خانه‌های کلیدی."""

        def cell(caption_key: str) -> QLabel:
            holder = QWidget(self.summary_card)
            holder_layout = QVBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setSpacing(2)
            caption = QLabel(self.tr_.tr(caption_key), holder)
            set_role(caption, "muted")
            value = QLabel("—", holder)
            value.setStyleSheet("font-size: 17px;")
            holder_layout.addWidget(caption)
            holder_layout.addWidget(value)
            return value

        head = QHBoxLayout()
        self.ring = ConfidenceRing(size=104)
        head.addWidget(self.ring)
        self.summary_direction_label = cell("prediction.current_direction")
        self.summary_direction_label.setStyleSheet("font-size: 21px;")
        head.addWidget(self.summary_direction_label)
        head.addStretch(1)
        self.summary_card.body().addLayout(head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        self._summary_cells: dict[str, QLabel] = {
            "price": cell("prediction.last_price"),
            "probability": cell("prediction.probability"),
            "confidence": cell("prediction.confidence_short"),
            "stage": cell("prediction.stage"),
            "regime": cell("prediction.regime"),
            "alignment": cell("prediction.alignment"),
            "quality": cell("prediction.data_quality"),
            "volatility": cell("prediction.volatility"),
            "generated": cell("prediction.generated"),
        }
        for index, label in enumerate(self._summary_cells.values()):
            grid.addWidget(label.parent(), index // 3, index % 3)
        self.summary_card.body().addLayout(grid)

        self.summary_stage_detail = self._muted("—")
        self.summary_card.body().addWidget(self.summary_stage_detail)

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
            self.summary_card: "prediction.summary_title",
            self.chart_card: "prediction.fan_title",
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
        self.fan_legend.setText(self.tr_.tr("prediction.fan_legend"))
        self._retranslate_table_headers()
        self._apply_payload()

    # ------------------------------------------------------------------
    # رندر
    # ------------------------------------------------------------------
    def _apply_payload(self) -> None:
        """پرکردن بخش‌ها از payload ذخیره‌شده."""
        payload = self._payload
        self.empty_label.setVisible(payload is None)
        cards = (
            self.summary_card,
            self.chart_card,
            self.horizons_card,
            self.market_card,
            self.scenarios_card,
            self.warnings_card,
            self.changed_card,
            self.accuracy_card,
            self.timeline_card,
        )
        for card in cards:
            card.setVisible(payload is not None)
        if payload is None:
            self.ring.set_value(0, label="—")
            return

        self._render_summary(payload)
        self._render_fan(payload)
        self._render_horizons(payload)
        self._render_market(payload)
        self._render_scenarios(payload)
        self._render_warnings(payload)
        self._render_changed(payload)
        self._render_accuracy(payload)
        self._render_timeline(payload)

    # --- خلاصه و نمودار ---------------------------------------------

    def _render_summary(self, payload: dict[str, Any]) -> None:
        """خلاصهٔ تصمیم: افق مرجع + وضعیت بازار."""
        tr = self.tr_.tr
        fmt = self.tr_.format_number
        horizons = [h if isinstance(h, dict) else h.to_dict() for h in payload.get("horizons") or []]
        primary = horizons[0] if horizons else None

        cells = self._summary_cells
        if primary is not None:
            direction = str(primary.get("direction", "uncertain"))
            direction_text = tr(f"prediction.direction.{direction}", default=direction)
            self.summary_direction_label.setText(direction_text)
            set_role(
                self.summary_direction_label,
                direction if direction in ("bullish", "bearish", "neutral") else "info",
            )
            self.ring.set_value(
                float(primary.get("confidence") or 0),
                label="{}٪".format(fmt(float(primary.get("confidence") or 0), 0)),
            )
            cells["probability"].setText(
                "{}٪".format(fmt(float(primary.get("probability") or 0), 0))
            )
            cells["confidence"].setText(
                "{}٪".format(fmt(float(primary.get("confidence") or 0), 0))
            )
            volatility = primary.get("volatility") or {}
            vol_value = (
                volatility.get("forecast_percent") if isinstance(volatility, dict) else None
            )
            cells["volatility"].setText(
                "{}٪".format(fmt(float(vol_value), 2)) if vol_value is not None else "—"
            )
        else:
            self.summary_direction_label.setText("—")
            self.ring.set_value(0, label="—")
            for key in ("probability", "confidence", "volatility"):
                cells[key].setText("—")

        last_price = payload.get("last_price")
        cells["price"].setText(
            fmt(float(last_price), 4) if last_price else "—"
        )

        stage = payload.get("market_stage") or {}
        if isinstance(stage, dict) and stage.get("stage"):
            stage_name = tr(
                f"prediction.stage.{stage.get('stage')}",
                default=str(stage.get("stage")),
            )
            cells["stage"].setText(stage_name)
            self.summary_stage_detail.setText(
                tr(
                    "prediction.stage_row",
                    stage=stage_name,
                    confidence=fmt(float(stage.get("confidence") or 0), 0),
                )
            )
        else:
            cells["stage"].setText("—")
            self.summary_stage_detail.setText("—")

        regimes = payload.get("regimes") or {}
        primary_tf = next(iter(regimes), None)
        if primary_tf and isinstance(regimes[primary_tf], dict):
            name = regimes[primary_tf].get("regime") or "?"
            cells["regime"].setText(
                tr(f"prediction.regime.{name}", default=str(name))
            )
        else:
            cells["regime"].setText("—")

        mtf = payload.get("multi_timeframe") or {}
        alignment = mtf.get("alignment")
        cells["alignment"].setText(
            tr(f"prediction.alignment.{alignment}", default=str(alignment)) if alignment else "—"
        )
        quality = payload.get("data_quality") or {}
        ratio = quality.get("ratio") if isinstance(quality, dict) else None
        cells["quality"].setText(
            "{}٪".format(fmt(float(ratio) * 100, 0)) if ratio is not None else "—"
        )
        generated = str(payload.get("generated_at", ""))
        cells["generated"].setText(generated or "—")

    def _render_fan(self, payload: dict[str, Any]) -> None:
        """نمودار بادبزن چندک از افق‌های فعال — دادهٔ خام موتور."""
        points: list[tuple[str, float, float, float, float, float]] = []
        for horizon in payload.get("horizons") or []:
            data = horizon if isinstance(horizon, dict) else horizon.to_dict()
            quantiles = data.get("quantiles") or {}
            if not quantiles:
                continue
            try:
                points.append(
                    (
                        str(data.get("horizon", "?")),
                        float(quantiles.get("p10", 0) or 0),
                        float(quantiles.get("p25", 0) or 0),
                        float(quantiles.get("p50", 0) or 0),
                        float(quantiles.get("p75", 0) or 0),
                        float(quantiles.get("p90", 0) or 0),
                    )
                )
            except (TypeError, ValueError):
                continue
        self.fan_chart.set_points(
            points, last_price=float(payload.get("last_price") or 0.0)
        )

    # --- جدول افق‌ها -------------------------------------------------

    def _render_horizons(self, payload: dict[str, Any]) -> None:
        """
        پرکردن جدول افق‌ها + فهرست افق‌های خاموش با دلیل.

        افق‌های خاموش صادقانه با دلیل نمایش داده می‌شوند (خواستهٔ
        اصلی صفحه از v1.11) و جدول همان فیلدهای قبلی را دارد — حالت
        جدولی خواناتر.
        """
        tr = self.tr_.tr
        fmt = self.tr_.format_number
        horizons = payload.get("horizons") or []
        table = self.horizons_table

        rows: list[dict[str, Any]] = [
            horizon if isinstance(horizon, dict) else horizon.to_dict()
            for horizon in horizons
        ]
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for index, data in enumerate(rows):
            direction = str(data.get("direction", "uncertain"))
            quantiles = data.get("quantiles") or {}
            volatility = data.get("volatility") or {}
            vol_value = (
                volatility.get("forecast_percent")
                if isinstance(volatility, dict)
                else None
            )
            agreement = data.get("model_agreement")
            method = str(data.get("method") or "—")
            conflict = bool(data.get("conflict"))
            cells = [
                str(data.get("horizon", "?")),
                tr(f"prediction.direction.{direction}", default=direction),
                fmt(float(data.get("probability") or 0), 0) + "٪",
                fmt(float(data.get("confidence") or 0), 0) + "٪",
                fmt(float(quantiles.get("p10", 0) or 0), 4)
                if quantiles.get("p10") else "—",
                fmt(float(quantiles.get("p50", 0) or 0), 4)
                if quantiles.get("p50") else "—",
                fmt(float(quantiles.get("p90", 0) or 0), 4)
                if quantiles.get("p90") else "—",
                fmt(float(vol_value), 2) + "٪" if vol_value is not None else "—",
                fmt(float(agreement) * 100, 0) + "٪" if agreement is not None else "—",
                fmt(float(data.get("samples") or 0), 0),
                tr(f"prediction.method.{method}", default=method)
                + (" / " + tr("prediction.conflict") if conflict else ""),
                tr("prediction.status_active"),
            ]
            for column, value in enumerate(cells):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(index, column, item)
        table.setSortingEnabled(True)

        # افق مرجع — سرنشان خوانا بالای جدول
        if rows:
            primary = rows[0]
            self.primary_label.setText(
                tr(
                    "prediction.primary_horizon",
                    horizon="{} — {} {}٪".format(
                        str(primary.get("horizon", "?")),
                        tr(
                            f"prediction.direction.{primary.get('direction', 'uncertain')}",
                            default=str(primary.get("direction", "?")),
                        ),
                        fmt(float(primary.get("probability") or 0), 0),
                    ),
                )
            )
            self.primary_label.setVisible(True)
        else:
            self.primary_label.setVisible(False)

        # افق‌های خاموش با دلیل
        disabled = payload.get("disabled_horizons") or []
        if disabled:
            parts = [
                tr(
                    "prediction.disabled_row",
                    horizon=str(item.get("horizon", "?")),
                    reason=str(item.get("reason", "")),
                )
                for item in disabled
                if isinstance(item, dict)
            ]
            self.disabled_label.setText(
                tr("prediction.disabled_title") + ": " + "، ".join(parts)
            )
            self.disabled_label.setVisible(True)
        else:
            self.disabled_label.setVisible(False)
        self._horizons_hint.setText(tr("prediction.horizons_hint"))

    def _retranslate_table_headers(self) -> None:
        """عنوان ستون‌های جدول افق‌ها."""
        if not hasattr(self, "horizons_table"):
            return
        self.horizons_table.setHorizontalHeaderLabels(
            [self.tr_.tr(f"prediction.col_{name}") for name in HORIZON_COLUMNS]
        )

    # --- رژیم / MTF --------------------------------------------------

    def _render_market(self, payload: dict[str, Any]) -> None:
        """رژیم هر تایم‌فریم به‌صورت خانه‌های جهت‌دار + هم‌راستایی MTF."""
        row, layout = self._row(self.market_card, "market")
        tr = self.tr_.tr
        fmt = self.tr_.format_number

        regimes = payload.get("regimes") or {}
        # تایم‌فریم‌های موجود اول؛ بعد ترتیب نردبان برای بقیه
        timeframes = [
            tf for tf in REGIME_TIMEFRAMES if tf in regimes
        ] + [
            tf for tf in regimes if tf not in REGIME_TIMEFRAMES
        ]

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        for index, timeframe in enumerate(timeframes):
            regime = regimes.get(timeframe)
            if not isinstance(regime, dict):
                continue
            name = regime.get("regime") or "?"
            direction = int(regime.get("direction") or 0)
            arrow = {"1": "▲", "0": "•", "1-": "▼"}.get(str(direction), "•")
            cell = QWidget(row)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(2)
            head = QHBoxLayout()
            tf_label = QLabel(timeframe, cell)
            set_role(tf_label, "chip_info")
            tf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            arrow_label = QLabel(arrow, cell)
            arrow_label.setStyleSheet("font-size: 16px;")
            if direction == 1:
                set_role(arrow_label, "bullish")
            elif direction == -1:
                set_role(arrow_label, "bearish")
            head.addWidget(tf_label)
            head.addWidget(arrow_label)
            head.addStretch(1)
            cell_layout.addLayout(head)
            name_label = QLabel(tr(f"prediction.regime.{name}", default=str(name)), cell)
            name_label.setWordWrap(True)
            cell_layout.addWidget(name_label)
            conf_label = self._muted(
                "{}٪".format(fmt(float(regime.get("confidence") or 0), 0))
            )
            cell_layout.addWidget(conf_label)
            grid.addWidget(cell, index // 2, index % 2)
        layout.addLayout(grid)

        mtf = payload.get("multi_timeframe") or {}
        alignment = mtf.get("alignment")
        if alignment:
            label = QLabel(
                tr(
                    "prediction.alignment_row",
                    value=tr(f"prediction.alignment.{alignment}", default=str(alignment)),
                ),
                row,
            )
            set_role(label, "chip_info")
            label.setWordWrap(True)
            layout.addWidget(label)
        quality = payload.get("data_quality") or {}
        ratio = quality.get("ratio") if isinstance(quality, dict) else None
        if ratio is not None:
            layout.addWidget(
                self._muted(
                    tr("prediction.data_quality", value=fmt(float(ratio) * 100, 0))
                )
            )
        last_price = payload.get("last_price")
        if last_price:
            layout.addWidget(
                self._muted(tr("prediction.last_price", price=fmt(float(last_price), 4)))
            )
        transition = payload.get("regime_transition") or {}
        if isinstance(transition, dict) and transition.get("likely_next"):
            layout.addWidget(
                self._muted(
                    tr(
                        "prediction.transition_row",
                        default="گذار محتمل: {value}",
                        value=str(transition.get("likely_next")),
                    )
                )
            )

    # --- سناریوها ----------------------------------------------------

    def _render_scenarios(self, payload: dict[str, Any]) -> None:
        """سناریوهای افق مرجع با احتمال و بازهٔ قیمت."""
        row, layout = self._row(self.scenarios_card, "scenarios")
        horizons = payload.get("horizons") or []
        if not horizons:
            layout.addWidget(self._muted(self.tr_.tr("prediction.no_data")))
            return
        primary = horizons[0]
        data = primary if isinstance(primary, dict) else primary.to_dict()

        # بازهٔ موردانتظار و فشار رخداد
        expected = data.get("expected_range") or {}
        if expected:
            layout.addWidget(
                self._muted(
                    self.tr_.tr(
                        "prediction.expected_range_row",
                        default="بازهٔ موردانتظار: {low} — {high}",
                        low=self.tr_.format_number(float(expected.get("low") or 0), 4),
                        high=self.tr_.format_number(float(expected.get("high") or 0), 4),
                    )
                )
            )

        for scenario in (data.get("scenarios") or {}).get("scenarios") or []:
            if not isinstance(scenario, dict):
                continue
            holder = QWidget(row)
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setSpacing(8)
            name = str(scenario.get("name", "?"))
            name_label = QLabel(
                self.tr_.tr(f"prediction.scenario.{name}", default=name), holder
            )
            role = "bullish" if name == "bull" else ("bearish" if name == "bear" else "neutral")
            set_role(name_label, role)
            name_label.setMinimumWidth(70)
            probability_label = QLabel(
                "{}٪".format(
                    self.tr_.format_number(
                        float(scenario.get("probability") or 0) * 100, 0
                    )
                ),
                holder,
            )
            range_label = QLabel(
                "{} — {}".format(
                    self.tr_.format_number(float(scenario.get("low") or 0), 4),
                    self.tr_.format_number(float(scenario.get("high") or 0), 4),
                ),
                holder,
            )
            holder_layout.addWidget(name_label)
            holder_layout.addWidget(probability_label)
            holder_layout.addWidget(range_label, 1)
            layout.addWidget(holder)

        events = data.get("event_pressure")
        if events:
            layout.addWidget(
                self._muted(
                    self.tr_.tr("prediction.event_pressure", value=str(events))
                )
            )
        for reason in (data.get("reasons") or [])[:3]:
            layout.addWidget(self._muted(str(reason)))

    # --- هشدارها -----------------------------------------------------

    def _render_warnings(self, payload: dict[str, Any]) -> None:
        """هشدارها، ناهنجاری‌ها، شکست و شکست کاذب."""
        row, layout = self._row(self.warnings_card, "warnings")
        tr = self.tr_.tr
        items: list[tuple[str, str]] = []
        for warning in payload.get("warnings") or []:
            text = str(warning.get("message", "") if isinstance(warning, dict) else warning)
            if text:
                items.append((text, "warn"))
        anomalies = payload.get("anomalies") or {}
        if isinstance(anomalies, dict):
            for anomaly in anomalies.get("anomalies") or []:
                items.append((str(anomaly), "warn"))
        breakout = payload.get("breakout") or {}
        if isinstance(breakout, dict) and breakout.get("state") not in (None, "", "none"):
            items.append(
                (tr("prediction.breakout_state", state=str(breakout.get("state"))), "info")
            )
        false_breakout = payload.get("false_breakout") or {}
        if isinstance(false_breakout, dict) and false_breakout.get("risk"):
            items.append(
                (
                    tr("prediction.false_breakout", risk=str(false_breakout.get("risk"))),
                    "info",
                )
            )
        if not items:
            layout.addWidget(self._muted(tr("prediction.no_warnings")))
        for text, role in items:
            label = QLabel(text, row)
            label.setWordWrap(True)
            set_role(label, "chip_warn" if role == "warn" else "chip_info")
            layout.addWidget(label)

    # --- دقت مدل‌ها ---------------------------------------------------

    def _render_accuracy(self, payload: dict[str, Any]) -> None:
        """دقت ثبت‌شده + سلامت مدل‌ها به‌صورت خانه‌های خوانا."""
        row, layout = self._row(self.accuracy_card, "accuracy")
        tr = self.tr_.tr
        fmt = self.tr_.format_number
        accuracy = payload.get("accuracy") or {}
        resolved = accuracy.get("resolved")
        if not resolved:
            layout.addWidget(self._muted(tr("prediction.no_resolved")))
        else:
            grid = QGridLayout()
            grid.setHorizontalSpacing(16)
            grid.setVerticalSpacing(6)
            stats = (
                ("prediction.accuracy_resolved", fmt(int(resolved), 0)),
                ("prediction.accuracy_direction", fmt(float(accuracy.get("direction_accuracy") or 0), 1) + "٪"),
                ("prediction.accuracy_range", fmt(float(accuracy.get("range_accuracy") or 0), 1) + "٪"),
                ("prediction.accuracy_brier", fmt(float(accuracy.get("brier") or 0), 3)),
            )
            for index, (key, value) in enumerate(stats):
                caption = QLabel(tr(key, default=key), row)
                set_role(caption, "muted")
                value_label = QLabel(value, row)
                value_label.setStyleSheet("font-size: 16px;")
                grid.addWidget(caption, index // 2, (index % 2) * 2)
                grid.addWidget(value_label, index // 2, (index % 2) * 2 + 1)
            layout.addLayout(grid)

        for name, health in (payload.get("model_health") or {}).items():
            if not isinstance(health, dict):
                continue
            label = QLabel(
                tr(
                    "prediction.health_row",
                    model=str(name),
                    acc=fmt(float(health.get("accuracy") or 0), 1),
                    status=tr(
                        f"prediction.health.{health.get('status', '?')}",
                        default=str(health.get("status", "?")),
                    ),
                ),
                row,
            )
            set_role(label, "chip_info")
            label.setWordWrap(True)
            layout.addWidget(label)

    # --- چه عوض شد ----------------------------------------------------

    def _render_changed(self, payload: dict[str, Any]) -> None:
        """تغییر نسبت به گزارش قبلی: احتمال، جهت، عوامل."""
        row, layout = self._row(self.changed_card, "changed")
        tr = self.tr_.tr
        changed = payload.get("what_changed")
        if not isinstance(changed, dict):
            layout.addWidget(self._muted(tr("prediction.no_change_data")))
            return
        probability = changed.get("probability_delta")
        if probability is not None:
            label = QLabel(
                tr(
                    "prediction.probability_delta",
                    value="{}{}".format(
                        "+" if float(probability) >= 0 else "",
                        self.tr_.format_number(float(probability), 0),
                    ),
                ),
                row,
            )
            set_role(label, "bullish" if float(probability) >= 0 else "bearish")
            layout.addWidget(label)
        if changed.get("direction_changed"):
            label = QLabel(tr("prediction.direction_changed"), row)
            set_role(label, "chip_warn")
            layout.addWidget(label)
        for factor in changed.get("changed_factors") or []:
            if not isinstance(factor, dict):
                continue
            layout.addWidget(
                QLabel(
                    tr(
                        "prediction.factor_row",
                        name=str(factor.get("name", "?")),
                        before=self.tr_.format_number(float(factor.get("before") or 0), 1),
                        after=self.tr_.format_number(float(factor.get("after") or 0), 1),
                        direction=tr(
                            f"prediction.factor_dir.{factor.get('direction', '?')}",
                            default=str(factor.get("direction", "?")),
                        ),
                    ),
                    row,
                )
            )

    # --- خط زمانی ----------------------------------------------------

    def _render_timeline(self, payload: dict[str, Any]) -> None:
        """خط زمانی پیش‌بینی‌های ثبت‌شده."""
        row, layout = self._row(self.timeline_card, "timeline")
        entries = payload.get("timeline") or []
        if not entries:
            layout.addWidget(self._muted(self.tr_.tr("prediction.no_timeline")))
            return
        for entry in entries[-12:]:
            if not isinstance(entry, dict):
                continue
            holder = QWidget(row)
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setSpacing(10)
            when = QLabel(str(entry.get("created_at", "")), holder)
            set_role(when, "muted")
            direction = str(entry.get("direction", "uncertain"))
            direction_label = QLabel(
                self.tr_.tr(f"prediction.direction.{direction}", default=direction),
                holder,
            )
            if direction in ("bullish", "bearish", "neutral"):
                set_role(direction_label, direction)
            probability_label = QLabel(
                "{}٪".format(
                    self.tr_.format_number(float(entry.get("probability") or 0), 0)
                ),
                holder,
            )
            holder_layout.addWidget(when, 1)
            holder_layout.addWidget(direction_label)
            holder_layout.addWidget(probability_label)
            layout.addWidget(holder)

    # ------------------------------------------------------------------
    # داخلی
    # ------------------------------------------------------------------
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
        row_layout.setSpacing(4)
        layout.addWidget(row)
        self._rows.setdefault(key, []).append(row)
        return row, row_layout

    def _muted(self, text: str) -> QLabel:
        label = QLabel(text, self)
        set_role(label, "muted")
        label.setWordWrap(True)
        return label

    def resizeEvent(self, event) -> None:  # noqa: N802 - نام Qt
        """چیدمان واکنش‌گرا: در عرض کم ردیف‌ها زیر هم می‌روند (§۱۰)."""
        super().resizeEvent(event)
        stacked = self.width() < 1100
        for row in (
            getattr(self, "summary_row", None),
            getattr(self, "market_row", None),
            getattr(self, "warn_row", None),
            getattr(self, "changed_row", None),
        ):
            if row is not None:
                row.set_stacked(stacked)


__all__ = ["HORIZON_COLUMNS", "PredictionPage"]
