"""
صفحه داشبورد.

نمای کلی: وضعیت اتصال، خلاصه بازار نمادهای منتخب، و آخرین سیگنال‌ها.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from localization import Translator
from ui.pages.base_page import BasePage
from ui.widgets.arrangeable import ArrangeableContainer
from ui.widgets.dashboard_widgets import BreadthBar, HealthTile, MoversList
from ui.widgets import (
    Card,
    KeyValueRow,
    RefreshButton,
    SegmentedControl,
    Sparkline,
    StatCard,
    StatusPill,
    TickerStrip,
    configure_table,
    make_button,
)

#: تایم‌فریم‌های نوار بالای داشبورد (مطابق طرح‌ها)
TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h", "1d", "1w")

#: ترتیب پیش‌فرض بخش‌های داشبورد. کاربر می‌تواند این ترتیب را عوض کند و
#: انتخابش ذخیره می‌شود؛ این فقط نقطهٔ شروع است.
DEFAULT_BLOCK_ORDER = ("command", "ticker", "stats", "overview", "signals")

#: کاشی‌های مرکز فرمان (کلید ← کلید عنوان)
COMMAND_TILES = ("connection", "portfolio", "engine", "breadth")


class DashboardPage(BasePage):
    """صفحه نخست برنامه."""

    title_key = "nav.dashboard"
    subtitle_key = "dashboard.subtitle"
    #: مرکز فرمان + جدول‌ها از ارتفاع لپ‌تاپ بلندترند؛ صفحه پیمایش می‌شود
    #: تا چیزی روی هم فشرده نشود.
    scrollable = True

    #: کاربر روی نام یک ارز در جدول خلاصهٔ بازار کلیک کرد (نماد)
    coin_activated = Signal(str)
    #: تایم‌فریم فعال داشبورد عوض شد
    timeframe_changed = Signal(str)
    #: چیدمان کارت‌ها تغییر کرد (رشتهٔ قابل ذخیره)
    layout_changed = Signal(str)

    def __init__(self, translator: Translator, parent: Any = None) -> None:
        self._market_rows: list[dict[str, Any]] = []
        self._status_rows: dict[str, KeyValueRow] = {}
        self._theme: Any = None
        #: آخرین دادهٔ خام کاشی‌ها؛ برای بازسازی متن‌ها پس از تغییر زبان
        self._command_data: dict[str, dict[str, Any]] = {}
        self._movers: tuple[list[dict[str, Any]], list[dict[str, Any]]] = ([], [])
        super().__init__(translator, parent)

    def build(self) -> None:
        """ساخت کارت‌های وضعیت، بازار و سیگنال."""
        self.refresh_button = RefreshButton(
            self.tr_.tr("common.refresh"),
            busy_text=self.tr_.tr("markets.updating"),
            done_text=self.tr_.tr("common.refresh"),
        )
        self.header.add_action(self.refresh_button)

        self.status_pill = StatusPill(self.tr_.tr("common.disconnected"))
        self.header.add_action(self.status_pill)

        # دکمهٔ حالت چیدمان: کاربر خواست بتواند ترتیب کارت‌ها را خودش
        # تعیین کند. کنترل‌های جابه‌جایی تا وقتی این دکمه زده نشده پنهان
        # می‌مانند تا صفحهٔ عادی شلوغ نشود.
        self.arrange_button = make_button("", role="ghost", checkable=True)
        self.arrange_button.toggled.connect(self._on_arrange_toggled)
        self.header.add_action(self.arrange_button)

        # ظرف بخش‌های جابه‌جاشدنی
        self.blocks = ArrangeableContainer(self.tr_, self)
        self.blocks.layout_changed.connect(self.layout_changed)
        self.layout_root().addWidget(self.blocks, 1)

        # مرکز فرمان: سلامت اتصال، پرتفوی، موتور و پهنای بازار در یک نگاه
        command_holder = QWidget()
        command_row = QGridLayout(command_holder)
        command_row.setContentsMargins(0, 0, 0, 0)
        command_row.setHorizontalSpacing(12)
        self.command_tiles: dict[str, HealthTile] = {}
        for column, key in enumerate(COMMAND_TILES):
            tile = HealthTile(self.tr_.tr(f"dashboard.command.{key}"))
            self.command_tiles[key] = tile
            command_row.addWidget(tile, 0, column)
            command_row.setColumnStretch(column, 1)
        self.breadth_bar = BreadthBar()
        breadth_layout = self.command_tiles["breadth"].layout()
        breadth_layout.insertWidget(3, self.breadth_bar)
        self.blocks.add_block("command", self.tr_.tr("dashboard.block_command"), command_holder)
        self._render_command_defaults()

        # نوار قیمت زنده — نخستین چیزی که در طرح‌ها دیده می‌شود
        self.ticker = TickerStrip(self)
        self.ticker.symbol_clicked.connect(self.coin_activated)
        self.blocks.add_block("ticker", self.tr_.tr("dashboard.block_ticker"), self.ticker)

        # چهار کارت آمار
        stats_holder = QWidget()
        cards = QHBoxLayout(stats_holder)
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setSpacing(12)
        self.stat_cards: dict[str, StatCard] = {}
        # نکته: کلید `market_cap` به دلایل سازگاری حفظ شده ولی محتوای آن
        # «سهم بازارهای صعودی» است؛ برچسبش هم همین را می‌گوید.
        for key, icon in (
            ("market_cap", "◎"),
            ("volume", "◫"),
            ("signals_today", "◈"),
            ("win_rate", "✦"),
        ):
            card = StatCard(icon=icon)
            card.set_data(title=self.tr_.tr(f"dashboard.stats.{key}"), value="—")
            self.stat_cards[key] = card
            cards.addWidget(card)
        self.blocks.add_block("stats", self.tr_.tr("dashboard.block_stats"), stats_holder)

        # نوار تایم‌فریم
        self.timeframe_bar = SegmentedControl(
            [(value, value.upper()) for value in TIMEFRAMES]
        )
        self.timeframe_bar.set_current("1h", emit=False)
        self.timeframe_bar.selection_changed.connect(self.timeframe_changed)
        timeframe_holder = QWidget()
        timeframe_row = QHBoxLayout(timeframe_holder)
        timeframe_row.setContentsMargins(0, 0, 0, 0)
        timeframe_row.addWidget(self.timeframe_bar)
        timeframe_row.addStretch(1)
        self.layout_root().insertWidget(
            self.layout_root().indexOf(self.blocks), timeframe_holder
        )

        overview_holder = QWidget()
        grid = QGridLayout(overview_holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        # کارت وضعیت سامانه
        self.status_card = Card(self.tr_.tr("dashboard.system_status"))
        for key in ("exchange", "connection", "ai_provider", "last_update"):
            row = KeyValueRow(self.tr_.tr(f"dashboard.{key}"))
            self._status_rows[key] = row
            self.status_card.add(row)
        self.status_card.body().addStretch(1)

        # بیشترین رشد و افت بازارهای نقدشونده — کلیک، جزئیات همان ارز
        self.movers_card = Card(self.tr_.tr("dashboard.movers"))
        movers_row = QHBoxLayout()
        movers_row.setSpacing(18)
        self.gainers_list = MoversList(self.tr_.tr("dashboard.command.top_gainers"))
        self.losers_list = MoversList(self.tr_.tr("dashboard.command.top_losers"))
        for movers in (self.gainers_list, self.losers_list):
            movers.set_empty_text(self.tr_.tr("dashboard.command.no_movers"))
            movers.symbol_clicked.connect(self.coin_activated)
            movers_row.addWidget(movers, 1)
        self.movers_card.body().addLayout(movers_row)
        grid.addWidget(self.movers_card, 0, 1)
        grid.addWidget(self.status_card, 1, 1)

        # کارت خلاصه بازار
        self.market_card = Card(self.tr_.tr("dashboard.market_overview"))
        self.market_table = QTableWidget(0, 5)
        self.market_table.setAlternatingRowColors(True)
        self.market_table.verticalHeader().setVisible(False)
        self.market_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.market_table.setCursor(Qt.CursorShape.PointingHandCursor)
        self.market_table.cellClicked.connect(self._on_market_cell_clicked)
        self.market_table.setMinimumHeight(300)
        self.market_card.add(self.market_table)
        grid.addWidget(self.market_card, 0, 0, 2, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)

        self.blocks.add_block(
            "overview", self.tr_.tr("dashboard.block_overview"), overview_holder
        )

        # کارت آخرین سیگنال‌ها
        self.signals_card = Card(self.tr_.tr("dashboard.recent_signals"))
        self.signals_table = QTableWidget(0, 5)
        self.signals_table.setAlternatingRowColors(True)
        self.signals_table.verticalHeader().setVisible(False)
        self.signals_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.signals_table.setMinimumHeight(220)
        self.signals_card.add(self.signals_table)
        self.blocks.add_block(
            "signals", self.tr_.tr("dashboard.block_signals"), self.signals_card, stretch=1
        )

        self._sync_arrange_button()

        self.disclaimer = QLabel(self.tr_.tr("signals.not_financial_advice"))
        self.disclaimer.setProperty("role", "muted")
        self.disclaimer.setWordWrap(True)
        self.layout_root().addWidget(self.disclaimer)

        self._apply_headers()

    def _apply_headers(self) -> None:
        """تنظیم سرستون‌های جدول‌ها بر پایه زبان جاری."""
        self.market_table.setHorizontalHeaderLabels([
            self.tr_.tr("common.symbol"), self.tr_.tr("common.price"),
            self.tr_.tr("common.change"), self.tr_.tr("common.volume"),
            self.tr_.tr("markets.trend"),
        ])
        self.signals_table.setHorizontalHeaderLabels([
            self.tr_.tr("common.symbol"), self.tr_.tr("signals.direction"),
            self.tr_.tr("signals.confidence"), self.tr_.tr("signals.risk_reward"),
            self.tr_.tr("signals.generated_at"),
        ])
        configure_table(self.market_table, stretch_column=0)
        configure_table(self.signals_table, stretch_column=4)

    # ------------------------------------------------------------------
    # به‌روزرسانی داده
    # ------------------------------------------------------------------
    def set_connection_status(self, status: str, role: str = "neutral") -> None:
        """به‌روزرسانی نشانگر وضعیت اتصال."""
        self.status_pill.set_status(status, role)

    def set_status_value(self, key: str, value: str, role: str = "") -> None:
        """به‌روزرسانی یک سطر از کارت وضعیت."""
        if key in self._status_rows:
            self._status_rows[key].set_value(value, role)

    def set_market_rows(self, rows: list[dict[str, Any]]) -> None:
        """
        پر کردن جدول خلاصه بازار.

        ستون آخر یک نمودار کوچک روند است؛ اگر تاریخچه‌ای نرسیده باشد خالی
        می‌ماند و ردیف همچنان درست نمایش داده می‌شود.
        """
        self._market_rows = [dict(r) for r in rows]
        self.market_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            change = float(row.get("change_percent", 0.0) or 0.0)
            values = [
                row.get("symbol", ""),
                self.tr_.format_number(row.get("price", 0.0), 2),
                f"\u200e{change:+.2f}%",
                self.tr_.format_number(row.get("volume", 0.0), 0),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    # نماد بازار نباید در چیدمان راست‌به‌چپ به‌هم بریزد
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 2 and self._theme is not None:
                    colors = self._theme.colors
                    item.setForeground(
                        QColor(colors.success if change >= 0 else colors.danger)
                    )
                self.market_table.setItem(index, column, item)

            history = row.get("history") or []
            if history:
                spark = Sparkline()
                if self._theme is not None:
                    spark.apply_theme(self._theme)
                spark.set_values([float(value) for value in history])
                self.market_table.setCellWidget(index, 4, spark)
            else:
                self.market_table.setCellWidget(index, 4, None)

    def set_ticker_items(self, items: list[dict[str, Any]]) -> None:
        """تنظیم اقلام نوار قیمت زنده."""
        self.ticker.set_items(items)

    def set_stat(self, key: str, value: str, *, delta: float | None = None,
                 caption: str = "", series: list[float] | None = None) -> None:
        """
        به‌روزرسانی یکی از چهار کارت آمار.

        کلیدهای معتبر: `market_cap`، `volume`، `signals_today`، `win_rate`.
        """
        card = self.stat_cards.get(key)
        if card is None:
            return
        card.set_data(
            title=self.tr_.tr(f"dashboard.stats.{key}"),
            value=value,
            delta=delta,
            caption=caption,
            series=series or [],
        )

    def apply_theme(self, theme: Any) -> None:
        """انتقال پوسته به کارت‌ها و نمودارهای کوچک."""
        self._theme = theme
        for card in self.stat_cards.values():
            card.apply_theme(theme)
        self.ticker.apply_theme(theme)
        for tile in self.command_tiles.values():
            tile.apply_theme(theme)
        self.breadth_bar.apply_theme(theme)
        if self._market_rows:
            self.set_market_rows(self._market_rows)

    def _on_market_cell_clicked(self, row: int, column: int) -> None:  # noqa: ARG002
        """کلیک روی هر ردیف، مدال جزئیات همان ارز را باز می‌کند."""
        item = self.market_table.item(row, 0)
        if item is not None and item.text():
            self.coin_activated.emit(item.text())

    def market_row_data(self, symbol: str) -> dict[str, Any]:
        """دادهٔ خام یک نماد برای پر کردن مدال جزئیات."""
        for row in self._market_rows:
            if str(row.get("symbol", "")) == str(symbol):
                return dict(row)
        return {}

    def set_signal_rows(self, rows: list[dict[str, Any]]) -> None:
        """پر کردن جدول آخرین سیگنال‌ها."""
        self.signals_table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            direction = str(row.get("direction", "WAIT")).lower()
            values = [
                row.get("symbol", ""),
                self.tr_.tr(f"signals.{direction}", direction.upper()),
                f"{row.get('confidence', 0)}%",
                f"{row.get('risk_reward'):.2f}" if row.get("risk_reward") else "—",
                str(row.get("created_at", "")),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                if column == 1 and self._theme is not None and direction in ("long", "buy", "short", "sell"):
                    colors = self._theme.colors
                    item.setForeground(QColor(
                        colors.success if direction in ("long", "buy") else colors.danger
                    ))
                self.signals_table.setItem(index, column, item)


    # ------------------------------------------------------------------
    # مرکز فرمان (2.3.1)
    # ------------------------------------------------------------------
    def _t(self, key: str, **variables: Any) -> str:
        return self.tr_.tr(f"dashboard.command.{key}", **variables)

    def _money(self, value: float | None, *, signed: bool = True) -> str:
        if value is None:
            return "—"
        number = self.tr_.format_number(abs(float(value)), 2)
        if not signed:
            return f"\u200e${number}"
        sign = "+" if value > 0 else ("−" if value < 0 else "")
        return f"\u200e{sign}${number}"

    @staticmethod
    def _pnl_role(value: float | None) -> str:
        if value is None or abs(float(value)) < 1e-9:
            return ""
        return "bullish" if value > 0 else "bearish"

    def _render_command_defaults(self) -> None:
        """حالت اولیه: هیچ عدد ساختگی؛ فقط «در حال راه‌اندازی»."""
        self.set_connection_health({"state": "starting"})
        self.set_portfolio({})
        self.set_engine_status({})
        self.set_breadth({})

    def set_connection_health(self, data: dict[str, Any]) -> None:
        """
        کاشی سلامت اتصال.

        data: state (online/degraded/offline/starting)، exchange، data_age
        (ثانیه یا None)، streams {connected,total}، rest {failures,cooldown_seconds}.
        """
        self._command_data["connection"] = dict(data)
        state = str(data.get("state") or "starting")
        rest = data.get("rest") or {}
        cooldown = float(rest.get("cooldown_seconds") or 0.0)
        if cooldown > 0 and state != "online":
            label_key, role = "rate_limited", "neutral"
        else:
            label_key, role = {
                "online": ("online", "bullish"),
                "degraded": ("degraded", "neutral"),
                "offline": ("offline", "bearish"),
            }.get(state, ("starting", "info"))
        age = data.get("data_age")
        age_text = (
            self._t("data_age_value", seconds=self.tr_.format_number(float(age), 0))
            if age is not None else self._t("no_data")
        )
        streams = data.get("streams") or {}
        total = int(streams.get("connections") or streams.get("total") or 0)
        connected = int(streams.get("connected") or 0)
        if total > 0:
            stream_text = self._t("streams_value", connected=self.tr_.format_number(connected, 0), total=self.tr_.format_number(total, 0))
            stream_role = "bullish" if connected == total else ("neutral" if connected else "bearish")
        else:
            stream_text, stream_role = self._t("streams_off"), ""
        failures = int(rest.get("failures") or 0)
        if cooldown > 0:
            rest_text, rest_role = self._t("rest_cooldown", seconds=int(round(cooldown))), "neutral"
        elif failures:
            rest_text, rest_role = self._t("rest_failing", count=failures), "bearish"
        elif rest:
            rest_text, rest_role = self._t("rest_ok"), "bullish"
        else:
            rest_text, rest_role = "—", ""
        exchange = str(data.get("exchange") or "").upper()
        self.command_tiles["connection"].set_state(
            value=self._t(label_key),
            role=role,
            chip=exchange,
            caption=self._t("cooldown_caption") if cooldown > 0 else "",
            details=[
                (self._t("data_age"), age_text, "" if age is None or float(age) < 20 else "bearish"),
                (self._t("streams"), stream_text, stream_role),
                (self._t("rest"), rest_text, rest_role),
            ],
        )

    def set_portfolio(self, data: dict[str, Any]) -> None:
        """
        کاشی پرتفوی کاغذی.

        data: open_count، unrealised (خالص یا None اگر قیمت تازه نیست)،
        realised_today، margin، win_rate.
        """
        self._command_data["portfolio"] = dict(data)
        count = data.get("open_count")
        unrealised = data.get("unrealised")
        realised = data.get("realised_today")
        headline = unrealised if unrealised is not None else realised
        win_rate = data.get("win_rate")
        self.command_tiles["portfolio"].set_state(
            value=self._money(headline) if headline is not None else "—",
            value_role={"bullish": "metric_up", "bearish": "metric_down"}.get(self._pnl_role(headline), "metric"),
            role="bullish" if (headline or 0) > 0 else ("bearish" if (headline or 0) < 0 else "info"),
            caption=self._t("portfolio_caption", count=self.tr_.format_number(int(count), 0))
            if count is not None else "",
            details=[
                (self._t("unrealised"), self._money(unrealised), self._pnl_role(unrealised)),
                (self._t("realised_today"), self._money(realised), self._pnl_role(realised)),
                (self._t("margin_used"), self._money(data.get("margin"), signed=False)
                 if data.get("margin") is not None else "—", ""),
                (self._t("win_rate"), self.tr_.format_number(float(win_rate), 1) + "%"
                 if win_rate is not None else "—", ""),
            ],
        )

    def set_engine_status(self, data: dict[str, Any]) -> None:
        """
        کاشی موتور معامله.

        data: exists، running، open، max، live، halted، daily_limit.
        """
        self._command_data["engine"] = dict(data)
        if not data.get("exists"):
            state_key, role = "engine_idle", "info"
        elif data.get("halted"):
            state_key, role = "daily_halted", "bearish"
        elif data.get("running"):
            state_key, role = "engine_running", "bullish"
        else:
            state_key, role = "engine_stopped", "neutral"
        slots = (
            self._t("slots_value", open=self.tr_.format_number(int(data.get("open") or 0), 0), max=self.tr_.format_number(int(data.get("max") or 0), 0))
            if data.get("max") else "—"
        )
        limit = data.get("daily_limit")
        self.command_tiles["engine"].set_state(
            value=self._t(state_key),
            role=role,
            value_role={"bullish": "metric_up", "bearish": "metric_down"}.get(role, "metric"),
            chip=self._t("mode_live") if data.get("live") else self._t("mode_paper"),
            caption=self._t("engine_caption", state=self._t(
                "engine_running" if data.get("running") else "engine_stopped"
            )) if data.get("exists") else "",
            details=[
                (self._t("slots"), slots, ""),
                (self._t("mode"), self._t("mode_live") if data.get("live") else self._t("mode_paper"),
                 "bearish" if data.get("live") else ""),
                (self._t("daily_limit"), self._money(limit, signed=False) if limit else "—", ""),
            ],
        )

    def set_breadth(self, data: dict[str, Any]) -> None:
        """کاشی پهنای بازار. data: up، down، flat، avg_change، total."""
        self._command_data["breadth"] = dict(data)
        up = int(data.get("up") or 0)
        down = int(data.get("down") or 0)
        flat = int(data.get("flat") or 0)
        total = int(data.get("total") or (up + down + flat))
        self.breadth_bar.set_counts(up, flat, down)
        share = (up / total * 100.0) if total else None
        avg = data.get("avg_change")
        self.command_tiles["breadth"].set_state(
            value=(self.tr_.format_number(share, 1) + "%") if share is not None else "—",
            value_role="metric_up" if share is not None and share >= 55 else (
                "metric_down" if share is not None and share <= 45 else "metric"),
            role="bullish" if share is not None and share >= 55 else (
                "bearish" if share is not None and share <= 45 else "neutral"),
            chip=self._t("advancers") if share is not None else "",
            caption=self._t("breadth_caption", up=self.tr_.format_number(up, 0), down=self.tr_.format_number(down, 0), total=self.tr_.format_number(total, 0)) if total else "",
            details=[
                (self._t("avg_change"), f"\u200e{float(avg):+.2f}%" if avg is not None else "—",
                 self._pnl_role(avg)),
                (self._t("markets"), self.tr_.format_number(total, 0) if total else "—", ""),
                (self._t("unchanged"), self.tr_.format_number(flat, 0) if total else "—", ""),
            ],
        )

    def set_movers(self, gainers: list[dict[str, Any]], losers: list[dict[str, Any]]) -> None:
        """بیشترین رشد/افت (از پیش مرتب و فیلترشده برای نقدشوندگی)."""
        self._movers = ([dict(r) for r in gainers], [dict(r) for r in losers])
        fmt = lambda value: self.tr_.format_number(value, 6 if value < 1 else 2)  # noqa: E731
        self.gainers_list.set_rows(gainers, fmt)
        self.losers_list.set_rows(losers, fmt)

    def _retranslate_command(self) -> None:
        for key, tile in self.command_tiles.items():
            tile.set_title(self._t(key))
        data = dict(self._command_data)
        self.set_connection_health(data.get("connection", {"state": "starting"}))
        self.set_portfolio(data.get("portfolio", {}))
        self.set_engine_status(data.get("engine", {}))
        self.set_breadth(data.get("breadth", {}))
        self.movers_card.set_title(self.tr_.tr("dashboard.movers"))
        self.gainers_list.set_title(self._t("top_gainers"))
        self.losers_list.set_title(self._t("top_losers"))
        for movers in (self.gainers_list, self.losers_list):
            movers.set_empty_text(self._t("no_movers"))
        self.set_movers(*self._movers)

    # ------------------------------------------------------------------
    # چیدمان قابل تنظیم
    # ------------------------------------------------------------------
    def _arrange_text(self) -> str:
        """متن دکمهٔ حالت چیدمان بر پایهٔ وضعیت فعلی."""
        key = "layout.done" if self.arrange_button.isChecked() else "layout.arrange"
        return self.tr_.tr(key)

    def _sync_arrange_button(self) -> None:
        """هماهنگ‌کردن متن و راهنمای دکمه."""
        self.arrange_button.setText(self._arrange_text())
        self.arrange_button.setToolTip(self.tr_.tr("layout.arrange_hint"))

    def _on_arrange_toggled(self, enabled: bool) -> None:
        """ورود و خروج از حالت چیدمان."""
        self.blocks.set_arrange_mode(bool(enabled))
        self._sync_arrange_button()

    def layout_state(self) -> str:
        """چیدمان فعلی به رشته‌ای قابل ذخیره."""
        return self.blocks.serialise()

    def apply_layout_state(self, state: str) -> None:
        """اعمال چیدمان ذخیره‌شدهٔ کاربر."""
        self.blocks.apply_state(state)
        if state and "command" not in str(state):
            # چیدمان ذخیره‌شدهٔ نسخه‌های قبل «مرکز فرمان» را نمی‌شناسد؛
            # بخش تازه بالای صفحه می‌نشیند، نه انتهای آن.
            while self.blocks.order and self.blocks.order[0] != "command":
                before = self.blocks.order
                self.blocks.move_up("command")
                if self.blocks.order == before:
                    break

    def reset_layout(self) -> None:
        """بازگرداندن چیدمان به ترتیب پیش‌فرض."""
        self.blocks.reset(list(DEFAULT_BLOCK_ORDER))

    def retranslate(self) -> None:
        """بازسازی همه متن‌های صفحه."""
        super().retranslate()
        self.refresh_button.set_texts(
            self.tr_.tr("common.refresh"),
            self.tr_.tr("markets.updating"),
            self.tr_.tr("common.refresh"),
        )
        self.arrange_button.setText(self._arrange_text())
        self.blocks.retranslate()
        for key, label_key in (
            ("command", "dashboard.block_command"),
            ("ticker", "dashboard.block_ticker"),
            ("stats", "dashboard.block_stats"),
            ("overview", "dashboard.block_overview"),
            ("signals", "dashboard.block_signals"),
        ):
            block = self.blocks.blocks.get(key)
            if block is not None:
                block.set_title(self.tr_.tr(label_key))
        self.status_card.set_title(self.tr_.tr("dashboard.system_status"))
        self.market_card.set_title(self.tr_.tr("dashboard.market_overview"))
        self.signals_card.set_title(self.tr_.tr("dashboard.recent_signals"))
        for key, row in self._status_rows.items():
            row.set_key(self.tr_.tr(f"dashboard.{key}"))
        self.disclaimer.setText(self.tr_.tr("signals.not_financial_advice"))
        for key, card in self.stat_cards.items():
            card.set_data(title=self.tr_.tr(f"dashboard.stats.{key}"))
        self._retranslate_command()
        self._apply_headers()
