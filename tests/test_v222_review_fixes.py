"""رگرسیون سه یافتهٔ بررسی اولیه؛ همه با داده/SQLite موقت و بدون Qt یا شبکه."""

from dataclasses import asdict, fields
import json
import sqlite3
from types import SimpleNamespace
import zipfile

import pytest

from app.config.settings_service import SettingsService
from app.database.repositories.settings_repository import SettingsRepository
from app.security.db_backend import DatabaseBackend, SECRETS_SETTING_KEY
from backup.manager import BackupManager, DATABASE_ENTRY
from signals.prediction.engine import PredictiveIntelligenceEngine, REPORT_TTL
from tests.test_prediction_lifecycle import make_candles
from trading.auto_trader import AutoTradeConfig, AutoTrader, LIVE_CONFIRMATION_PHRASE
from trading.price_cache import TickEngine
from trading.scalp_service import ScalpService


@pytest.mark.asyncio
async def test_prediction_distinct_timeframes_and_latest_cache():
    """دو مصرف‌کنندهٔ یک نماد نباید با کلید تازه روی cached=None سقوط کنند."""
    data = {"15m": make_candles(300, step=900), "1h": make_candles(300, step=3600)}
    engine = PredictiveIntelligenceEngine(
        lambda symbol, timeframe, limit=600: data.get(timeframe, []), include_dl=False
    )
    first = await engine.assess("BTC/USDT", timeframes=("15m", "1h"))
    second = await engine.assess("BTC/USDT", timeframes=("15m",))
    assert first is not None and second is not None and first is not second
    assert engine.report("BTC/USDT") is second
    assert await engine.assess("BTC/USDT", timeframes=("15m", "1h")) is first
    # خواندن cache قدیمی نباید آخرین گزارش ساخته‌شده را عقب ببرد.
    assert engine.report("BTC/USDT") is second
    forced = await engine.assess("BTC/USDT", timeframes=("15m",), force=True)
    assert forced is not second and engine.report("BTC/USDT") is forced
    key = ("BTC/USDT", ("15m",))
    timestamp, report = engine._report_cache[key]
    engine._report_cache[key] = (timestamp - REPORT_TTL - 1, report)
    refreshed = await engine.assess("BTC/USDT", timeframes=("15m",))
    assert refreshed is not forced and engine.report("BTC/USDT") is refreshed
    assert await engine.assess("EMPTY/USDT", timeframes=("1m",)) is None
    assert engine.report("BTC/USDT") is refreshed


# همهٔ فیلدها عمداً صریح‌اند: افزودن فیلد تازه باید این تست را هم توسعه دهد.
CONFIG_VALUES = dict(
    margin_per_trade=23.0, target_profit=4.0, max_loss=6.0, leverage=12.0,
    max_concurrent=2, max_hold_seconds=120, poll_seconds=0.5, daily_loss_limit=17.0,
    mode="paper", live_confirmation="", fee_rate=0.0, engine_mode="selected",
    selected_symbols="BTC/USDT", scan_interval_seconds=7.0, min_liquidity=3_000_000.0,
    max_spread_percent=0.05, stale_after_seconds=2.0, slippage_percent=0.0,
    break_even_enabled=False, break_even_trigger=2.3, trailing_enabled=True,
    trailing_activation=2.7, trailing_offset=0.8, signal_invalidation=False,
    trend_conflict_policy="penalize", allocation_mode="percent", allocation_percent=8.0,
    max_total_margin_percent=20.0,
)


def config_service(settings):
    return ScalpService(SimpleNamespace(settings=settings))


class FakeSettings:
    def __init__(self, values):
        self.values = values

    def get(self, key, fallback=None):
        return self.values.get(key, fallback)


def test_all_config_fields_roundtrip_through_database(database):
    """تنظیم‌های ذخیره‌شده، شامل صفر و False، دقیقاً به موتور منتقل شوند."""
    assert set(CONFIG_VALUES) == {field.name for field in fields(AutoTradeConfig)}
    settings = SettingsService(SettingsRepository(database))
    settings.initialize_defaults()
    values = {
        "scalp." + ("taker_fee_rate" if name == "fee_rate" else name): value
        for name, value in CONFIG_VALUES.items()
    }
    settings.set_many(values)
    settings.reload()
    config = config_service(settings).build_trader_config()
    assert asdict(config) == CONFIG_VALUES
    assert config.selected_symbol_list == ["BTC/USDT"]
    assert not config.is_live
    assert {key: settings.get(key) for key in values} == values


@pytest.mark.parametrize("raw,expected", [(False, False), (True, True), ("false", False),
    ("true", True), ("0", False), ("1", True), (0, False), (1, True)])
def test_boolean_settings_are_not_python_string_truthiness(raw, expected):
    config = config_service(FakeSettings({"scalp.trailing_enabled": raw})).build_trader_config()
    assert config.trailing_enabled is expected


def test_missing_settings_keep_config_defaults_and_hard_limits():
    assert asdict(config_service(FakeSettings({})).build_trader_config()) == asdict(
        AutoTradeConfig().validated()
    )
    config = config_service(FakeSettings({"scalp.leverage": 900, "scalp.poll_seconds": 0.1,
        "scalp.max_concurrent": 1000, "scalp.mode": "live"})).build_trader_config()
    assert config_service(FakeSettings({"scalp.taker_fee_rate": None})).build_trader_config().fee_rate == 0.0006
    assert config.leverage == 200 and config.poll_seconds == 0.25
    assert not config.is_live
    accepted = config_service(FakeSettings({"scalp.mode": "live",
        "scalp.live_confirmation": LIVE_CONFIRMATION_PHRASE})).build_trader_config()
    assert accepted.is_live  # هیچ gateway یا سفارشی اجرا نمی‌شود.


def test_apply_config_updates_entry_guards_and_tick_freshness():
    """ذخیرهٔ دوباره تنظیم باید روی محافظ موتور و cache متصل اثر بگذارد."""
    settings = FakeSettings({"scalp.engine_mode": "selected", "scalp.selected_symbols": "BTC/USDT",
        "scalp.max_spread_percent": 0.05, "scalp.stale_after_seconds": 2.0})
    service = config_service(settings)
    trader = AutoTrader(config=service.build_trader_config(), price_source=None, repository=None)
    ticks = TickEngine(stale_after_seconds=30)
    trader.attach_tick_engine(ticks)
    assert ticks.stale_after_ms == 2000
    assert trader._allowed_symbols() == ["BTC/USDT"]
    ticks.record("BTC/USDT", 100, bid=99.95, ask=100.05)
    candidate = SimpleNamespace(symbol="BTC/USDT", turnover_24h=5_000_000)
    assert trader._check_entry_guards(candidate, "long")[0] is False
    settings.values.update({"scalp.max_spread_percent": 0.2, "scalp.stale_after_seconds": 5.0})
    trader.apply_config(service.build_trader_config())
    assert ticks.stale_after_ms == 5000
    assert trader._check_entry_guards(candidate, "long") == (True, "")


@pytest.mark.parametrize("backup_type", ["manual", "pre_migration", "pre_restore"])
def test_backup_labels_encrypted_secrets_and_preserves_restore(database, temp_paths, backup_type):
    """رفع برچسب غلط نباید راز را از DB اصلی یا backup بازیابی‌پذیر حذف کند."""
    repo = SettingsRepository(database)
    backend = DatabaseBackend(repo)
    backend.set("audit_dummy", "synthetic-value-only")
    before = repo.get(SECRETS_SETTING_KEY)
    manager = BackupManager(temp_paths)
    info = manager.create(backup_type=backup_type)
    manifest = manager.read_manifest(info.path)
    assert manifest["contains_secrets"] is True
    assert manifest["contains_encrypted_db_secrets"] is True
    assert manifest["contains_uninspected_settings"] is False
    assert manager.verify(info.path)[0]
    with zipfile.ZipFile(info.path) as archive:
        snapshot = temp_paths.data_dir / "inspection.db"
        snapshot.write_bytes(archive.read(DATABASE_ENTRY))
    with sqlite3.connect(snapshot) as conn:
        value = json.loads(conn.execute("SELECT value FROM settings WHERE key=?",
            (SECRETS_SETTING_KEY,)).fetchone()[0])["v"]
    assert value == before and repo.get(SECRETS_SETTING_KEY) == before
    backend.set("audit_dummy", "changed")
    database.dispose()
    manager.restore(info.path)
    assert DatabaseBackend(SettingsRepository(database)).get("audit_dummy") == "synthetic-value-only"


def test_backup_without_secret_row_is_not_labelled_sensitive(database, temp_paths):
    info = BackupManager(temp_paths).create()
    manifest = BackupManager.read_manifest(info.path)
    assert manifest["contains_secrets"] is False
    assert manifest["contains_encrypted_db_secrets"] is False


def test_legacy_settings_file_is_conservatively_sensitive(database, temp_paths):
    """ساختار settings.json قراردادی ندارد؛ نباید بی‌بررسی فاقد راز معرفی شود."""
    temp_paths.settings_file.write_text('{"legacy_key": "synthetic"}')
    manager = BackupManager(temp_paths)
    info = manager.create()
    manifest = manager.read_manifest(info.path)
    assert manifest["contains_secrets"] is True
    assert manifest["contains_uninspected_settings"] is True
    assert manifest["contains_encrypted_db_secrets"] is False


def test_pre_schema_backup_still_works(temp_paths):
    """DB قدیمی بدون جدول settings هم پیش از migration قابل پشتیبان‌گیری است."""
    with sqlite3.connect(temp_paths.database_file) as conn:
        conn.execute("CREATE TABLE legacy (id INTEGER)")
    manager = BackupManager(temp_paths)
    info = manager.create_pre_migration()
    assert info is not None and manager.verify(info.path)[0]
    assert manager.read_manifest(info.path)["contains_secrets"] is False


def test_unreadable_secret_metadata_fails_closed(database, temp_paths, monkeypatch):
    """شکست بررسی نباید backup با ادعای اشتباه «بدون راز» باقی بگذارد."""
    from app.exceptions import BackupError

    manager = BackupManager(temp_paths)

    def fail(_path):
        raise sqlite3.DatabaseError("synthetic read failure")

    monkeypatch.setattr(manager, "_has_encrypted_secrets", fail)
    with pytest.raises(BackupError):
        manager.create()
    assert not list(temp_paths.backups_dir.glob("*.zip"))
    assert not list(temp_paths.backups_dir.glob(".tmp_*.db"))


def test_empty_or_unreadable_secret_row_is_conservatively_flagged(database, temp_paths):
    SettingsRepository(database).set(SECRETS_SETTING_KEY, None)
    manager = BackupManager(temp_paths)
    assert manager.read_manifest(manager.create().path)["contains_secrets"] is True
