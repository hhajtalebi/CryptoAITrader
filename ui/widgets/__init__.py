"""ویجت‌های مشترک و قابل استفاده مجدد در صفحات مختلف."""

from ui.widgets.ai_status_card import AIStatusCard
from ui.widgets.avatar import Avatar
from ui.widgets.charts_mini import (
    AreaChart,
    ConfidenceRing,
    DonutChart,
    Sparkline,
    ThemedWidget,
)
from ui.widgets.chrome import (
    ConnectionCard,
    FeatureStrip,
    IconSidebar,
    NotificationButton,
    SearchBox,
    TopBar,
    UserMenuButton,
)
from ui.widgets.common import (
    Card,
    HeaderBar,
    KeyValueRow,
    RefreshButton,
    SignalCard,
    StatusPill,
    configure_button_column,
    configure_table,
    make_button,
    make_title,
)
from ui.widgets.performance_view import PerformanceView
from ui.widgets.watchlist_panel import WatchlistPanel
from ui.widgets.trend_cell import TrendCell
from ui.widgets.table_toolbar import FullscreenTableDialog, TableToolbar
from ui.widgets.theme_card import ThemeCard, ThemeSwatch
from ui.widgets.theme_preview import ThemePreview
from ui.widgets.controls import (
    ChipBar,
    EmptyState,
    Pagination,
    SegmentedControl,
    StatCard,
    StatusDot,
    TickerStrip,
    Toast,
    ToggleSwitch,
    set_role,
)

__all__ = [
    "Avatar",
    "AreaChart",
    "Card",
    "ChipBar",
    "ConfidenceRing",
    "ConnectionCard",
    "DonutChart",
    "EmptyState",
    "FeatureStrip",
    "HeaderBar",
    "IconSidebar",
    "KeyValueRow",
    "NotificationButton",
    "Pagination",
    "PerformanceView",
    "WatchlistPanel",
    "RefreshButton",
    "SearchBox",
    "SegmentedControl",
    "SignalCard",
    "Sparkline",
    "TrendCell",
    "StatCard",
    "StatusDot",
    "StatusPill",
    "ThemeCard",
    "ThemePreview",
    "ThemeSwatch",
    "ThemedWidget",
    "TickerStrip",
    "Toast",
    "ToggleSwitch",
    "TopBar",
    "UserMenuButton",
    "AIStatusCard",
    "FullscreenTableDialog",
    "TableToolbar",
    "configure_button_column",
    "configure_table",
    "make_button",
    "make_title",
]
