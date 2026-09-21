"""
آزمون بهینه‌سازی سرعت (نسخهٔ ۱.۹.۴).

این آزمون‌ها «سریع بودن» را مستقیم نمی‌سنجند — زمان اجرا روی ماشین‌های
مختلف فرق می‌کند و آزمونِ زمان‌محور شکنندهٔ بی‌فایده است. به‌جای آن،
**ساختارهایی** را می‌سنجند که سرعت از آن‌ها می‌آید:

    • بستهٔ `signals` نباید pandas را به‌زور بار کند
    • لایهٔ رابط کاربری نباید لایهٔ پایگاه داده را بکشد
    • کلید کش اندیکاتور باید بدون ساخت DataFrame حساب شود
    • اصابت کش نباید محاسبه را دوباره اجرا کند

اگر کسی روزی یک `import` بی‌جا اضافه کند، همین‌جا گیر می‌افتد نه در
گزارش کندی کاربر.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_isolated(code: str) -> str:
    """
    اجرای کد در فرایند تازه.

    وارد‌کردن‌ها فرایندی‌اند: اگر آزمون دیگری قبلاً pandas را بار کرده
    باشد، بررسی در همین فرایند بی‌معنا می‌شود. پس هر بررسی در مفسر
    مستقل اجرا می‌شود.
    """
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, f"subprocess failed:\n{result.stderr}"
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# وارد‌کردن تنبل
# ---------------------------------------------------------------------------


def test_outcome_tracker_does_not_pull_pandas() -> None:
    """
    پیگیری نتیجهٔ سیگنال جز `dataclass` و `datetime` وابستگی ندارد.

    این ماژول از راه `app.database.repositories` در مسیر خواندن
    تنظیمات قرار می‌گیرد؛ اگر pandas را بکشد، **باز کردن برنامه** نیم
    ثانیه کند می‌شود بدون آنکه هیچ محاسبه‌ای لازم باشد.
    """
    output = run_isolated(
        "import sys; import signals.outcome_tracker; print('pandas' in sys.modules)"
    )
    assert output == "False"


def test_reading_settings_does_not_pull_pandas() -> None:
    """خواندن تنظیمات نباید موتور محاسباتی را بیدار کند."""
    output = run_isolated(
        "import sys; import app.config.settings_service; print('pandas' in sys.modules)"
    )
    assert output == "False"


def test_widgets_do_not_pull_the_database_layer() -> None:
    """
    ویجت‌ها نباید به SQLAlchemy وابسته باشند.

    یک ثابت رشته‌ای در `ui/widgets/watchlist_panel.py` کل لایهٔ داده را
    وارد می‌کرد. جدا نگه‌داشتن این دو لایه هم معماری درست‌تری است و هم
    بارگذاری رابط کاربری را سبک می‌کند.
    """
    output = run_isolated(
        "import sys; import ui.widgets; "
        "print('sqlalchemy' in sys.modules, 'app.database' in sys.modules)"
    )
    assert output == "False False"


def test_signals_package_still_exports_everything() -> None:
    """
    تنبل‌کردن نباید رابط عمومی بسته را عوض کند.

    ‏`from signals import SignalEngine` باید دقیقاً مثل گذشته کار کند.
    """
    from signals import (  # noqa: F401
        BaseStrategy,
        RiskEngine,
        SignalEngine,
        StrategyContext,
        StrategyRegistry,
        StrategyVote,
        register_builtin_strategies,
        strategy_registry,
    )

    assert isinstance(SignalEngine, type)
    assert isinstance(RiskEngine, type)


def test_signals_dir_lists_lazy_names() -> None:
    """کامل‌کنندهٔ خودکار و `dir()` باید نام‌های تنبل را ببینند."""
    import signals

    names = dir(signals)
    for name in ("SignalEngine", "RiskEngine", "strategy_registry"):
        assert name in names


def test_signals_unknown_attribute_raises() -> None:
    """نام ناشناخته باید `AttributeError` بدهد، نه چیز دیگر."""
    import signals

    with pytest.raises(AttributeError):
        signals.ThisDoesNotExist


# ---------------------------------------------------------------------------
# کش اندیکاتور
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine():  # noqa: ANN201
    """موتور اندیکاتور با اندیکاتورهای داخلی ثبت‌شده."""
    from indicators.engine import IndicatorEngine
    from indicators.registry import indicator_registry, register_builtin_indicators

    if not indicator_registry.available():
        register_builtin_indicators()
    return IndicatorEngine()


def make_candles(count: int = 300):  # noqa: ANN201
    """کندل‌های ساختگی با روند ملایم."""
    from app.core.models import Candle

    out = []
    price = 50000.0
    for index in range(count):
        price *= 1.001 if index % 3 else 0.999
        out.append(
            Candle(
                timestamp=1700000000 + index * 3600,
                open=price,
                high=price * 1.005,
                low=price * 0.995,
                close=price,
                volume=100.0,
            )
        )
    return out


def test_fingerprint_matches_dataframe_and_candles(engine) -> None:  # noqa: ANN001
    """
    اثر انگشت باید برای لیست کندل و DataFrame یکسان باشد.

    اگر این دو فرق کنند، همان دادهٔ یکسان دو کلید کش می‌گیرد و کش
    عملاً بی‌اثر می‌شود.
    """
    from indicators.base import candles_to_dataframe

    candles = make_candles()
    from_list = engine._data_fingerprint(candles)
    from_frame = engine._data_fingerprint(candles_to_dataframe(candles))
    assert from_list == from_frame


def test_fingerprint_handles_empty_input(engine) -> None:  # noqa: ANN001
    """ورودی خالی باید `None` بدهد تا مسیر بدون کش برود."""
    import pandas as pd

    assert engine._data_fingerprint([]) is None
    assert engine._data_fingerprint(pd.DataFrame()) is None


def test_cache_hit_does_not_rebuild_the_dataframe(engine, monkeypatch) -> None:
    """
    گران‌ترین بخش مسیر کش‌شده نباید اجرا شود.

    پیش از این، `candles_to_dataframe()` همیشه پیش از بررسی کش صدا
    می‌شد: برای ۲۴ اندیکاتورِ کاملاً کش‌شده حدود ۱۲ میلی‌ثانیه کار
    دورریختنی به ازای هر نماد، که در پویش ۱۴۰۰ نمادی به چند ثانیه
    می‌رسید.
    """
    import indicators.engine as engine_module

    candles = make_candles()
    engine.calculate("RSI", candles, "1h", symbol="BTC/USDT")

    calls = {"count": 0}
    original = engine_module.candles_to_dataframe

    def counting(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(engine_module, "candles_to_dataframe", counting)
    engine.calculate("RSI", candles, "1h", symbol="BTC/USDT")
    assert calls["count"] == 0


def test_cache_hit_does_not_recompute(engine, monkeypatch) -> None:
    """اصابت کش نباید اندیکاتور را دوباره بسازد."""
    candles = make_candles()
    engine.calculate("RSI", candles, "1h", symbol="BTC/USDT")

    created = {"count": 0}
    original = engine._registry.create

    def counting(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        created["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(engine._registry, "create", counting)
    engine.calculate("RSI", candles, "1h", symbol="BTC/USDT")
    assert created["count"] == 0


def test_cache_miss_still_computes(engine) -> None:  # noqa: ANN001
    """دادهٔ تازه باید واقعاً محاسبه شود، نه اینکه کش اشتباهی بخورد."""
    first = engine.calculate("RSI", make_candles(300), "1h", symbol="BTC/USDT")
    second = engine.calculate("RSI", make_candles(301), "1h", symbol="BTC/USDT")
    assert first.values != second.values or first.metadata != second.metadata


def test_cache_is_not_shared_across_symbols(engine) -> None:  # noqa: ANN001
    """
    دو نماد با کندل یکسان نباید کش هم را بخورند.

    اگر نماد از کلید حذف شود، در پویش انبوه همهٔ نمادها نتیجهٔ نماد
    اول را می‌گیرند — فاجعه‌ای خاموش که کاربر هرگز متوجهش نمی‌شود.
    """
    candles = make_candles()
    engine.calculate("RSI", candles, "1h", symbol="BTC/USDT")
    key_btc = engine._data_fingerprint(candles)
    engine.calculate("RSI", candles, "1h", symbol="ETH/USDT")
    assert key_btc == engine._data_fingerprint(candles)

    from market.cache import MarketCache

    btc = MarketCache.make_key("ind", "RSI", "BTC/USDT", "1h", *key_btc, "")
    eth = MarketCache.make_key("ind", "RSI", "ETH/USDT", "1h", *key_btc, "")
    assert btc != eth


def test_calculate_many_matches_individual_results(engine) -> None:  # noqa: ANN001
    """
    تبدیل تنبل در `calculate_many` نباید نتیجه را عوض کند.

    این مهم‌ترین آزمون این دسته است: بهینه‌سازی‌ای که خروجی را تغییر
    دهد، بهینه‌سازی نیست — نقص است.
    """
    candles = make_candles()
    names = ["RSI", "MACD", "EMA"]

    batch = engine.calculate_many(names, candles, "1h", symbol="SOL/USDT")
    for name in names:
        single = engine.calculate(name, candles, "1h", symbol="SOL/USDT")
        assert batch[name].values == single.values


def test_calculate_many_survives_a_broken_indicator(engine) -> None:  # noqa: ANN001
    """نام ناشناخته نباید کل دسته را از کار بیندازد."""
    candles = make_candles()
    results = engine.calculate_many(
        ["RSI", "NOT_A_REAL_INDICATOR"], candles, "1h", symbol="BTC/USDT"
    )
    assert "RSI" in results
    assert "NOT_A_REAL_INDICATOR" not in results


def test_empty_candles_still_raise(engine) -> None:  # noqa: ANN001
    """
    دادهٔ خالی باید همان خطای قبلی را بدهد.

    مسیر کش نباید این بررسی را دور بزند.
    """
    from app.exceptions import InsufficientDataError

    with pytest.raises(InsufficientDataError):
        engine.calculate("RSI", [], "1h", symbol="BTC/USDT")


# ---------------------------------------------------------------------------
# خروجی CSV روی همهٔ جدول‌ها
# ---------------------------------------------------------------------------


@pytest.fixture()
def translator():  # noqa: ANN201
    """مترجم فارسی — حالت پیش‌فرض کاربر."""
    from localization import Translator

    return Translator("fa")


@pytest.fixture()
def toolbar_table(qt_application):  # noqa: ANN001, ANN201
    """یک جدول نمونه با نوار ابزار وصل‌شده."""
    from PySide6.QtWidgets import (
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    from localization import Translator
    from ui.widgets.table_toolbar import attach_table_toolbar

    host = QWidget()
    layout = QVBoxLayout(host)
    table = QTableWidget(3, 4)
    layout.addWidget(table)
    table.setHorizontalHeaderLabels(["نماد", "جهت", "اطمینان", "تحلیل"])
    sample = [
        ("\u200eBTC/USDT", "خرید", "78%"),
        ("\u200eETH/USDT", "فروش", "64%"),
        ("\u200eSOL/USDT", "خرید", "52%"),
    ]
    for row, values in enumerate(sample):
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(value))
        table.setCellWidget(row, 3, QPushButton("تحلیل"))

    toolbar = attach_table_toolbar(table, Translator("fa"))
    # مرجع نگه داشته می‌شود تا ویجت میزبان زباله‌روبی نشود
    toolbar._host_ref = host  # noqa: SLF001
    return toolbar, table


def test_every_table_gets_an_export_button(qt_application, translator) -> None:
    """
    خواستهٔ اصلی: خروجی روی **همهٔ** جدول‌های برنامه.

    چون نوار ابزار خودکار وصل می‌شود، یک دکمه در یک جا یعنی خروجی در
    همهٔ صفحه‌ها.
    """
    from ui.pages.signals_page import SignalsPage

    page = SignalsPage(translator)
    toolbars = page.table_toolbars()
    assert toolbars
    for toolbar in toolbars:
        assert toolbar.export_button is not None


def test_rows_include_the_header(toolbar_table) -> None:  # noqa: ANN001
    """سطر نخست باید سرستون‌ها باشد."""
    toolbar, _ = toolbar_table
    rows = toolbar.table_to_rows()
    assert rows[0] == ["نماد", "جهت", "اطمینان", "تحلیل"]
    assert len(rows) == 4


def test_direction_marks_are_stripped(toolbar_table) -> None:  # noqa: ANN001
    """
    نشانگرهای جهت‌نویسی نباید در فایل بیایند.

    ‏`\\u200e` روی صفحه لازم است تا `BTC/USDT` وارونه نشود، ولی در
    اکسل فقط یک کاراکتر ناخوانا تولید می‌کند.
    """
    toolbar, _ = toolbar_table
    flat = "".join("".join(row) for row in toolbar.table_to_rows())
    assert "\u200e" not in flat
    assert "\u200f" not in flat
    assert "BTC/USDT" in flat


def test_widget_cells_export_as_empty(toolbar_table) -> None:  # noqa: ANN001
    """سلولی که دکمه دارد داده نیست و باید خالی بماند."""
    toolbar, _ = toolbar_table
    assert all(row[3] == "" for row in toolbar.table_to_rows()[1:])


def test_hidden_columns_are_excluded(toolbar_table) -> None:  # noqa: ANN001
    """کاربر همان چیزی را می‌گیرد که می‌بیند."""
    toolbar, table = toolbar_table
    table.setColumnHidden(1, True)
    rows = toolbar.table_to_rows()
    assert len(rows[0]) == 3
    assert "جهت" not in rows[0]


def test_hidden_rows_are_excluded(toolbar_table) -> None:  # noqa: ANN001
    """ردیف فیلترشده نباید در خروجی بیاید."""
    toolbar, table = toolbar_table
    table.setRowHidden(0, True)
    assert len(toolbar.table_to_rows()) == 3


def test_csv_file_is_excel_safe(toolbar_table, tmp_path) -> None:  # noqa: ANN001
    """
    فایل باید با BOM نوشته شود.

    اکسل ویندوز بدون BOM فایل UTF-8 را با کدگذاری محلی می‌خواند و همهٔ
    متن فارسی به هم می‌ریزد — همان دردی که یک بار در خروجی PDF داشتیم.
    """
    toolbar, _ = toolbar_table
    path = tmp_path / "out.csv"
    toolbar.write_csv(str(path), toolbar.table_to_rows())

    assert path.read_bytes()[:3] == b"\xef\xbb\xbf"
    text = path.read_text(encoding="utf-8-sig")
    assert "نماد" in text
    assert "BTC/USDT" in text


def test_csv_round_trips(toolbar_table, tmp_path) -> None:  # noqa: ANN001
    """آنچه نوشته شد باید دقیقاً همان باشد که خوانده می‌شود."""
    import csv

    toolbar, _ = toolbar_table
    path = tmp_path / "out.csv"
    original = toolbar.table_to_rows()
    toolbar.write_csv(str(path), original)

    with open(path, encoding="utf-8-sig", newline="") as handle:
        assert list(csv.reader(handle)) == original


def test_export_keys_exist_in_both_languages() -> None:
    """کلیدهای ترجمهٔ خروجی در هر دو زبان باشند."""
    from localization import Translator

    for language in ("fa", "en"):
        tr = Translator(language)
        for key in ("export_csv", "export_csv_hint", "export_empty", "export_failed"):
            assert tr.tr(f"common.{key}") != f"common.{key}"
