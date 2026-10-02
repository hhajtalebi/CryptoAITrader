"""
نسخهٔ ۲.۶.۰ — سیستم لاگ و تشخیص معاملات.

پوشش خواستهٔ کاربر: لاگ سیگنال، نامزد، رد، ورود، خروج و خطا؛ خط زمانی
معامله؛ خلاصهٔ پویش؛ چرخش فایل لاگ؛ فیلتر رابط کاربری؛ خروجی؛ و اینکه
خرابی لاگ هرگز معامله را متوقف نمی‌کند. هیچ آستانه‌ای در این نسخه عوض
نشده — آزمون‌های «بدون تغییر رفتار» هم همین را قفل می‌کنند.
"""

from __future__ import annotations

import csv
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from app.database.repositories.audit_repository import AuditRepository
from app.database.repositories.trade_repository import PaperTradeRepository
from app.database.session import DatabaseManager
from app.logging import audit
from app.logging.audit_store import AuditStoreWriter, attach_audit_store, audit_store, detach_audit_store
from app.logging.categories import LogCategory, category_for_logger
from app.logging.query import LogFilter, export_events, filter_events, summary_row, timeline_stages, total_summary
from app.logging.structured import (
    DailySizeRotatingFile,
    current,
    log_buffer,
    read_log_files,
    setup_structured_logging,
    shutdown_structured_logging,
)
from tests.test_v230_execution import Repo, candidate, make
from trading.price_cache import TickEngine

ULTRA = dict(engine_mode="ultra", margin_per_trade=10, leverage=50, target_profit=2, max_loss=2,
             fee_rate=0.0006, max_hold_seconds=180, min_liquidity=0, max_total_margin_percent=100,
             daily_loss_limit=10_000, max_concurrent=10)


# ---------------------------------------------------------------------------
# ابزار
# ---------------------------------------------------------------------------
@pytest.fixture()
def structured(tmp_path):
    audit.reset_state()
    logs = setup_structured_logging(tmp_path / "logs")
    yield logs
    detach_audit_store()
    shutdown_structured_logging()
    audit.reset_state()


@pytest.fixture()
def db(tmp_path):
    manager = DatabaseManager(f"sqlite:///{tmp_path / 'audit.db'}")
    manager.create_all()
    return manager


def flush(logs, store=None):
    logs.flush(5.0)
    if store is not None:
        store.writer.flush(5.0)


def events(name=None, **match):
    found = [e for e in log_buffer().snapshot() if name is None or e.get("event") == name]
    return [e for e in found if all(e.get(k) == v for k, v in match.items())]


def ticks_with_book(symbol="BTC/USDT", bid=99.999, ask=100.001):
    ticks = TickEngine()
    ticks.record(symbol, 100.0, bid=bid, ask=ask)
    return ticks


# ---------------------------------------------------------------------------
# ۱) دسته‌ها و کد استاندارد دلیل رد
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(("logger_name", "category"), [
    ("trading.auto_trader", LogCategory.TRADING),
    ("trading.scalp_service", LogCategory.SCALP),
    ("trading.ultra_scalp", LogCategory.SCALP),
    ("signals.scanner", LogCategory.SIGNALS),
    ("market.providers.lbank.ws", LogCategory.EXCHANGE),
    ("ai.ollama_launcher", LogCategory.AI),
    ("app.application", LogCategory.APPLICATION),
    ("something.unknown", LogCategory.APPLICATION),
])
def test_logger_names_map_to_categories(logger_name, category):
    assert category_for_logger(logger_name) is category


@pytest.mark.parametrize(("raw", "code", "bucket"), [
    ("spread_eats_stop:0.123%", "spread_eats_stop", "spread"),
    ("wide_spread:0.400%", "wide_spread", "spread"),
    ("target_unreachable:0.010%<0.300%", "target_unreachable", "target"),
    ("trend_conflict:1h,4h", "trend_conflict", "trend"),
    ("risk_exceeds_loss_budget", "risk_exceeded", "risk"),
    ("poor_net_reward_risk", "poor_reward_risk", "risk"),
    ("invalid_risk_levels", "invalid_risk", "risk"),
    ("no_orderbook", "no_orderbook", "orderbook"),
    ("negative_edge", "negative_edge", "edge"),
    ("daily_loss_limit", "daily_loss_limit", "risk"),
    ("symbol_already_open", "symbol_already_open", "risk"),
    ("stale_data", "stale_data", "data"),
    ("low_liquidity", "low_liquidity", "liquidity"),
    ("cost_too_high", "cost_too_high", "cost"),
    ("low_volatility", "low_volatility", "volatility"),
    ("low_confidence", "low_confidence", "confidence"),
    ("totally_new_reason", "totally_new_reason", "other"),
])
def test_engine_reasons_normalise_to_standard_codes(raw, code, bucket):
    assert audit.normalize_reason(raw) == code
    assert audit.reason_bucket(code) == bucket


# ---------------------------------------------------------------------------
# ۲) لاگ رد، نامزد، سیگنال، ورود، خروج
# ---------------------------------------------------------------------------
async def test_reject_is_logged_with_code_detail_snapshot_and_filters(structured):
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0, bid=99.9, ask=100.1)  # اسپرد ۰٫۲٪ حد ضرر را می‌بلعد
    trader = make(ticks=ticks, **ULTRA)
    assert await trader.open_trade(candidate(turnover_24h=5e6)) is None
    flush(structured)
    rejected = events("reject", symbol="BTC/USDT")
    assert len(rejected) == 1
    event = rejected[0]
    assert event["reason_code"] == "spread_eats_stop"
    assert event["category"] == "scalp"
    ctx = event["context"]
    assert ctx["reason_detail"].startswith("spread_eats_stop:")
    assert ctx["bucket"] == "spread"
    assert ctx["stage"] == "risk_levels"
    assert ctx["filters"]["market_guards"] == "pass"
    assert ctx["filters"]["orderbook"] == "pass"
    assert ctx["filters"]["risk_levels"] == "fail"
    assert ctx["filters"]["revalidation"] == "not_run"
    # عکس بازار: قیمت، Bid/Ask، اسپرد، نقدینگی، اطمینان و هزینه
    assert ctx["bid"] == pytest.approx(99.9) and ctx["ask"] == pytest.approx(100.1)
    assert ctx["spread_percent"] == pytest.approx(0.2, rel=1e-3)
    assert ctx["liquidity_24h"] == pytest.approx(5e6)
    assert ctx["technical_confidence"] == pytest.approx(80.0)
    assert ctx["round_trip_cost_percent"] > 0.2
    assert ctx["decision"] == "skip"
    assert event["correlation_id"]


async def test_repeated_reject_is_kept_live_but_not_spammed_to_disk(structured):
    ticks = TickEngine()
    ticks.record("BTC/USDT", 100.0)  # فید بدون Bid/Ask → no_orderbook
    trader = make(ticks=ticks, **ULTRA)
    for _ in range(3):
        assert await trader.open_trade(candidate()) is None
    flush(structured)
    rejected = events("reject", reason_code="no_orderbook")
    assert len(rejected) == 3  # نمای زنده همه را دارد
    assert [e["persist"] for e in rejected] == [True, False, False]
    files = read_log_files(structured.logs_dir, categories={"scalp"})
    assert len([e for e in files if e.get("event") == "reject"]) == 1


async def test_entry_logs_signal_candidate_validation_and_entry_fields(structured, db):
    repo = PaperTradeRepository(db)
    trader = make(repo=repo, ticks=ticks_with_book(), **ULTRA)
    trade = await trader.open_trade(candidate(intelligence={"final_confidence": 71.0, "mtf_alignment": 0.8},
                                              turnover_24h=8e6, volatility_per_second=0.08))
    assert trade is not None
    flush(structured)
    correlation = events("entry")[0]["correlation_id"]
    assert correlation
    for name in ("signal", "candidate", "validation", "entry"):
        assert events(name, correlation_id=correlation), name
    signal = events("signal")[0]
    assert signal["category"] == "signals"
    assert signal["context"]["intelligence"]["final_confidence"] == 71.0
    validation = events("validation")[0]["context"]
    assert set(validation["filters"].values()) == {"pass"}
    entry = events("entry")[0]
    assert entry["category"] == "orders"
    assert entry["trade_id"] == trade.trade_id
    ctx = entry["context"]
    for field in ("direction", "entry_price", "bid", "ask", "quantity", "margin", "leverage",
                  "stop_loss", "take_profit", "expected_rr", "estimated_fee", "estimated_slippage",
                  "signal_snapshot"):
        assert field in ctx, field
    assert ctx["entry_price"] == pytest.approx(100.001)  # LONG روی Ask
    assert ctx["leverage"] == 50
    # نسبت قیمتی هدف/حد ضرر (هدف خالص پس از کارمزد دورتر است، پس > ۱)
    assert ctx["expected_rr"] == pytest.approx(abs(ctx["take_profit"] - ctx["entry_price"])
                                               / abs(ctx["entry_price"] - ctx["stop_loss"]), rel=1e-3)
    assert ctx["estimated_fee"] > 0
    assert ctx["signal_snapshot"]["final_confidence"] == 71.0


async def test_exit_logs_reason_pnl_fees_and_holding_time(structured, db):
    repo = PaperTradeRepository(db)
    trader = make(repo=repo, ticks=ticks_with_book(), **ULTRA)
    trade = await trader.open_trade(candidate())
    record = await trader.close_trade(trade, "take_profit")
    assert record is not None and record["status"] == "closed"
    flush(structured)
    exit_event = events("exit", trade_id=trade.trade_id)[0]
    ctx = exit_event["context"]
    assert ctx["exit_reason"] == "take_profit"
    assert ctx["net_pnl"] == pytest.approx(record["pnl"])
    assert ctx["fees"] == pytest.approx(record["fee"])
    assert ctx["gross_pnl"] == pytest.approx(record["pnl"] + record["fee"])
    assert ctx["result"] in {"win", "loss", "breakeven"}
    assert ctx["holding_seconds"] is not None and ctx["holding_seconds"] >= 0
    decision = events("exit_decision", trade_id=trade.trade_id)[0]["context"]
    assert decision["exit_reason"] == "take_profit"
    assert decision["trade_direction"] == "LONG"


def test_manual_and_partial_paths_are_audited_through_the_repository(structured, db):
    repo = PaperTradeRepository(db)
    opened = repo.open_trade(symbol="ETH/USDT", side="short", quantity=3.0, entry_price=2000.0,
                             stop_loss=2050.0, take_profit=1900.0, leverage=10, fee=1.2, note="manual")
    repo.partial_close(opened["id"], quantity=1.0, exit_price=1950.0, fee=0.4, target_index=0)
    repo.close_trade(opened["id"], exit_price=1940.0, fee=0.8, note="manual")
    flush(structured)
    assert events("entry", trade_id=opened["id"])[0]["context"]["direction"] == "SHORT"
    partial = events("partial_exit", trade_id=opened["id"])[0]["context"]
    assert partial["target"] == 1 and partial["quantity"] == 1.0
    assert events("exit", trade_id=opened["id"])[0]["context"]["exit_reason"] == "manual"


def test_errors_go_to_their_category_and_the_global_error_log(structured):
    logging.getLogger("trading.auto_trader").error("order rejected by exchange")
    try:
        raise ValueError("boom")
    except ValueError:
        logging.getLogger("market.providers.lbank").exception("ws failure")
    flush(structured)
    base = structured.logs_dir
    errors = read_log_files(base, categories={"errors"})
    messages = {e["message"] for e in errors}
    assert {"order rejected by exchange", "ws failure"} <= messages
    assert any("ValueError: boom" in (e.get("exc") or "") for e in errors)
    trading = read_log_files(base, categories={"trading"})
    assert any(e["message"] == "order rejected by exchange" for e in trading)
    exchange = read_log_files(base, categories={"exchange"})
    assert any(e["message"] == "ws failure" for e in exchange)
    # بدون فیلتر دسته، نسخهٔ تکراری errors/ حذف می‌شود
    every = read_log_files(base)
    assert len([e for e in every if e["message"] == "ws failure"]) == 1


def test_sensitive_values_are_masked_in_files(structured):
    logging.getLogger("exchange.client").warning("request api_key=ABCDEF1234567890 secret=topsecretvalue")
    flush(structured)
    raw = "".join(p.read_text(encoding="utf-8") for p in structured.logs_dir.rglob("*.jsonl"))
    assert "ABCDEF1234567890" not in raw and "topsecretvalue" not in raw


# ---------------------------------------------------------------------------
# ۳) پایگاه داده و خط زمانی
# ---------------------------------------------------------------------------
async def test_trade_timeline_is_retrievable_from_sqlite(structured, db):
    store = attach_audit_store(AuditRepository(db))
    repo = PaperTradeRepository(db)
    trader = make(repo=repo, ticks=ticks_with_book(), **ULTRA)
    trade = await trader.open_trade(candidate())
    trades = repo.get_by_id(trade.trade_id)
    repo.partial_close(trade.trade_id, quantity=trades.quantity / 3, exit_price=100.01, fee=0.01, target_index=0)
    await trader.close_trade(trade, "take_profit")
    flush(structured, store)
    audit_repo = AuditRepository(db)
    timeline = audit_repo.timeline(trade.trade_id)
    names = [e["event"] for e in timeline]
    assert names[:4] == ["signal", "candidate", "validation", "entry"]
    assert "partial_exit" in names and "exit_decision" in names and names[-1] == "exit"
    stages = timeline_stages(timeline)
    assert [s["stage"] for s in stages] == ["signal", "candidate", "validation", "entry", "monitoring", "exit"]
    assert all(s["status"] == "done" for s in stages)
    assert trade.trade_id in audit_repo.recent_trade_ids()


async def test_audit_repository_search_filters(structured, db):
    store = attach_audit_store(AuditRepository(db))
    audit.reject("SOL/USDT", "wide_spread:0.5%", engine_mode="scan")
    audit.reject("BTC/USDT", "negative_edge", engine_mode="scan")
    audit.emit("entry", "Entry #7", category=LogCategory.ORDERS, symbol="BTC/USDT", trade_id=7)
    flush(structured, store)
    repo = AuditRepository(db)
    assert {e["symbol"] for e in repo.query(symbol="btc")} == {"BTC/USDT"}
    assert [e["reason_code"] for e in repo.query(reason_code="wide_spread")] == ["wide_spread"]
    assert [e["trade_id"] for e in repo.query(trade_id=7)] == [7]
    assert len(repo.query(categories=["orders"])) == 1
    assert len(repo.query(search="negative")) == 1
    future = datetime.now() + timedelta(hours=1)
    assert repo.query(start=future) == []
    assert repo.purge(older_than_days=30, max_rows=1) == 2
    assert len(repo.query()) == 1


def test_audit_store_writer_survives_database_failure():
    class Broken:
        def add_events(self, batch):
            raise RuntimeError("database is locked")

        def purge(self, **kwargs):
            raise RuntimeError("database is locked")

    writer = AuditStoreWriter(Broken()).start()
    for index in range(5):
        writer.put({"event": "reject", "epoch": time.time(), "message": str(index)})
    assert writer.flush(5.0)
    assert writer.failures >= 1 and writer.written == 0
    writer.stop()


# ---------------------------------------------------------------------------
# ۴) خلاصهٔ پویش
# ---------------------------------------------------------------------------
async def test_scan_summary_counts_source_and_gate_rejections(structured, db):
    store = attach_audit_store(AuditRepository(db))
    ticks = ticks_with_book("BTC/USDT")
    ticks.record("ETH/USDT", 100.0)  # بدون دفتر → no_orderbook
    trader = make(repo=Repo(), ticks=ticks, **ULTRA)

    async def source():
        audit.note_scan(scanned=40, raw=30, reasons={"low_momentum": 25, "stale_data": 10, "low_liquidity": 3})
        return [candidate("BTC/USDT"), candidate("ETH/USDT")]

    trader._candidate_source = source
    await trader._scan_for_entries()
    flush(structured, store)
    summary = events("scan_summary")[0]["context"]
    assert summary["engine"] == "ultra"
    assert summary["scanned_symbols"] == 40
    assert summary["raw_candidates"] == 30
    assert summary["source_candidates"] == 2
    assert summary["final_candidates"] == 1
    assert summary["opened_trades"] == 1
    assert summary["rejected_volatility"] == 25
    assert summary["rejected_data"] == 10
    assert summary["rejected_liquidity"] == 3
    assert summary["rejected_orderbook"] == 1
    assert summary["reasons"]["no_orderbook"] == 1
    # همان پویش (چون معامله باز شد) تجمیعی در SQLite هم هست
    stored = AuditRepository(db).scan_summaries(engine="ultra")
    assert stored and stored[-1]["context"]["opened_trades"] == 1
    row = summary_row(stored[-1])
    assert row["rejected_orderbook"] == 1 and row["final_candidates"] == 1
    assert total_summary([row, row])["opened_trades"] == 2


async def test_ultra_source_reports_its_filter_counts():
    from trading.ultra_scalp import UltraScalpSource

    ticks = TickEngine()
    now_ms = time.time() * 1000
    ticks.record("QUIET/USDT", 100.0)
    source = UltraScalpSource(lambda: ticks, settings=lambda key, default: default)
    diagnostics = audit.ScanDiagnostics(engine="ultra")
    with audit.scan_scope(diagnostics):
        await source.scan(symbols=["QUIET/USDT"])
    assert diagnostics.scanned_symbols == 1
    stats = source.last_stats
    assert diagnostics.reasons.get("low_momentum", 0) == stats["quiet"]
    assert diagnostics.reasons.get("stale_data", 0) == stats["stale"]
    assert now_ms > 0


def test_scalp_scanner_reports_reason_without_changing_result():
    from app.core.models import Ticker
    from tests.conftest import make_candles
    from trading.scalp_scanner import score_candidate

    ticker = Ticker(symbol="BTC/USDT", last_price=100.0, high_24h=101.0, low_24h=99.0, volume_24h=1e6,
                    turnover_24h=5e7, change_percent=0.0, timestamp=0)
    candles = make_candles(60)
    codes: list[str] = []
    for spread in (0.01, 5.0):
        plain = score_candidate(ticker, candles, spread=spread)
        counted = score_candidate(ticker, candles, spread=spread, on_reject=codes.append)
        assert (plain is None) == (counted is None)
        if plain is not None:
            assert plain.score == counted.score
    assert codes, "دست‌کم یک رد باید کد داشته باشد"
    assert set(codes) <= set(audit.REASON_BUCKETS)

    def explode(code):
        raise RuntimeError("callback broke")

    # خرابی شمارنده هرگز امتیازدهی را نمی‌شکند
    assert (score_candidate(ticker, candles, spread=5.0, on_reject=explode) is None)


# ---------------------------------------------------------------------------
# ۵) چرخش فایل
# ---------------------------------------------------------------------------
def test_log_file_rotates_by_size_and_day_and_keeps_retention(tmp_path):
    now = [datetime(2026, 10, 1, 12, 0)]
    sink = DailySizeRotatingFile(tmp_path / "scalp", "scalp", max_bytes=2048, retention_days=2,
                                 max_files=50, clock=lambda: now[0])
    line = json.dumps({"message": "x" * 200})
    for _ in range(30):
        sink.write(line)
    day1 = [p.name for p in sink.files()]
    assert "scalp-2026-10-01.jsonl" in day1
    assert any(name.startswith("scalp-2026-10-01.") and name.count(".") == 2 for name in day1)
    assert all(p.stat().st_size <= 2048 + len(line) + 1 for p in sink.files())
    now[0] = datetime(2026, 10, 2, 0, 1)
    sink.write(line)
    assert (tmp_path / "scalp" / "scalp-2026-10-02.jsonl").exists()
    now[0] = datetime(2026, 10, 5, 0, 1)
    sink.write(line)
    names = [p.name for p in sink.files()]
    assert not any("2026-10-01" in name for name in names)  # قدیمی‌تر از نگه‌داری پاک شد
    assert "scalp-2026-10-05.jsonl" in names
    sink.close()


def test_log_file_count_is_capped(tmp_path):
    sink = DailySizeRotatingFile(tmp_path, "trading", max_bytes=1024, max_files=4,
                                 clock=lambda: datetime(2026, 10, 1))
    for _ in range(60):
        sink.write("y" * 300)
    assert len(sink.files()) <= 4
    sink.close()


def test_category_folders_are_created(structured):
    for name in ("trading.auto_trader", "trading.scalp_service", "signals.scanner", "ai.client",
                 "market.feed", "app.application"):
        logging.getLogger(name).warning("hello")
    audit.emit("entry", "e", category=LogCategory.ORDERS, symbol="X/USDT", trade_id=1)
    audit.performance("scan_source", 5.0)
    flush(structured)
    folders = {p.name for p in structured.logs_dir.iterdir() if p.is_dir()}
    assert {"trading", "scalp", "signals", "ai", "market", "application", "orders", "audit",
            "performance"} <= folders


# ---------------------------------------------------------------------------
# ۶) فیلتر و خروجی
# ---------------------------------------------------------------------------
SAMPLE = [
    {"ts": "2026-10-01T10:00:00.000", "epoch": 1000.0, "level": "INFO", "category": "scalp", "module": "audit",
     "event": "reject", "symbol": "BTC/USDT", "reason_code": "wide_spread", "message": "Rejected BTC/USDT",
     "context": {"spread_percent": 0.4}},
    {"ts": "2026-10-01T10:00:01.000", "epoch": 1001.0, "level": "ERROR", "category": "exchange",
     "module": "market.lbank", "message": "socket closed", "context": {}},
    {"ts": "2026-10-01T10:00:02.000", "epoch": 1002.0, "level": "INFO", "category": "orders", "module": "audit",
     "event": "entry", "symbol": "ETH/USDT", "trade_id": 12, "message": "Entry #12", "context": {"leverage": 20}},
]


def test_log_filter_by_category_level_symbol_trade_time_and_text():
    assert [e["category"] for e in filter_events(SAMPLE, LogFilter(categories={"exchange"}))] == ["exchange"]
    assert [e["level"] for e in filter_events(SAMPLE, LogFilter(min_level="WARNING"))] == ["ERROR"]
    assert [e["symbol"] for e in filter_events(SAMPLE, LogFilter(symbol="btcusdt"))] == ["BTC/USDT"]
    assert [e.get("trade_id") for e in filter_events(SAMPLE, LogFilter(trade_id="#12"))] == [12]
    assert len(filter_events(SAMPLE, LogFilter(search="SOCKET"))) == 1
    assert len(filter_events(SAMPLE, LogFilter(search="0.4"))) == 1  # جست‌وجو در جزئیات
    window = LogFilter(start=datetime.fromtimestamp(1000.5), end=datetime.fromtimestamp(1001.5))
    assert [e["message"] for e in filter_events(SAMPLE, window)] == ["socket closed"]


def test_export_csv_jsonl_and_text(tmp_path):
    assert export_events(SAMPLE, tmp_path / "out.csv") == 3
    with open(tmp_path / "out.csv", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["reason_code"] == "wide_spread"
    assert json.loads(rows[2]["context"]) == {"leverage": 20}
    assert export_events(SAMPLE, tmp_path / "out.jsonl") == 3
    lines = (tmp_path / "out.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[2])["trade_id"] == 12
    assert export_events(SAMPLE, tmp_path / "out.txt") == 3
    assert "reason_code=wide_spread" in (tmp_path / "out.txt").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# ۷) خرابی لاگ ≠ توقف معامله
# ---------------------------------------------------------------------------
async def test_trading_continues_when_audit_logger_raises(structured, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("logger exploded")

    monkeypatch.setattr(audit._logger, "log", broken)
    trader = make(ticks=ticks_with_book(), **ULTRA)
    assert await trader.open_trade(candidate()) is not None
    ticks = TickEngine()
    ticks.record("ETH/USDT", 100.0)
    trader2 = make(ticks=ticks, **ULTRA)
    assert await trader2.open_trade(candidate("ETH/USDT")) is None
    assert trader2.rejection_reason("ETH/USDT") == "no_orderbook"


async def test_trading_continues_when_every_audit_function_raises(monkeypatch, db):
    def broken(*args, **kwargs):
        raise RuntimeError("audit down")

    for name in ("emit", "reject", "candidate", "entry", "exit_", "timeline", "scan_summary",
                 "performance", "current_scan"):
        monkeypatch.setattr(audit, name, broken)
    repo = PaperTradeRepository(db)
    trader = make(repo=repo, ticks=ticks_with_book(), **ULTRA)

    async def source():
        return [candidate()]

    trader._candidate_source = source
    with pytest.raises(RuntimeError):
        audit.emit("x", "y")
    try:
        await trader._scan_for_entries()
    except RuntimeError:
        pytest.fail("scan must not die because audit helpers fail")
    assert len(trader.open_trades) == 1
    trade = trader.open_trades[0]
    assert await trader.close_trade(trade, "manual") is not None


async def test_trading_continues_when_a_log_handler_breaks(structured):
    class Exploding(logging.Handler):
        def emit(self, record):
            raise OSError("disk full")

    structured.add_handler(Exploding())
    trader = make(ticks=ticks_with_book(), **ULTRA)
    assert await trader.open_trade(candidate()) is not None
    flush(structured)
    assert events("entry") or events("validation")  # بقیهٔ هندلرها کار کردند


def test_full_queue_drops_without_blocking(tmp_path):
    logs = setup_structured_logging(tmp_path / "logs", queue_size=100)
    try:
        logs.listener.stop()  # شنونده متوقف: صف پر می‌شود
        logs._started = False
        started = time.perf_counter()
        for index in range(2000):
            logging.getLogger("trading.auto_trader").warning("flood %d", index)
        elapsed = time.perf_counter() - started
        from app.logging.structured import stats

        assert stats()["dropped"] >= 1800
        assert elapsed < 2.0
    finally:
        shutdown_structured_logging()


def test_audit_event_cost_is_small(structured):
    started = time.perf_counter()
    for index in range(2000):
        audit.reject(f"S{index % 50}/USDT", "low_momentum", engine_mode="ultra")
    per_event = (time.perf_counter() - started) / 2000
    assert per_event < 0.001  # کمتر از ۱ میلی‌ثانیه در مسیر داغ
    flush(structured)


def test_audit_store_attaches_to_the_structured_pipeline(structured, db):
    store = attach_audit_store(AuditRepository(db))
    assert audit_store() is store
    assert store in current().fanout.targets()
    detach_audit_store()
    assert audit_store() is None


# ---------------------------------------------------------------------------
# ۸) صفحهٔ مرکز لاگ
# ---------------------------------------------------------------------------
@pytest.fixture()
def page(qt_application, structured, db):  # noqa: ARG001
    from localization import Translator
    from ui.pages.log_center_page import LogCenterPage

    store = attach_audit_store(AuditRepository(db))
    widget = LogCenterPage(Translator("fa"))
    widget.set_sources(audit_repository=AuditRepository(db), logs_dir=structured.logs_dir)
    widget._store = store
    yield widget
    widget.deleteLater()


def _seed():
    logging.getLogger("market.providers.lbank").error("socket closed")
    audit.reject("BTC/USDT", "wide_spread:0.4%", engine_mode="scan")
    audit.emit("entry", "Entry #12 LONG ETH/USDT", category=LogCategory.ORDERS, symbol="ETH/USDT", trade_id=12)
    logging.getLogger("trading.auto_trader").warning("plain warning")


def test_log_center_live_view_and_filters(page, structured):
    _seed()
    flush(structured)
    assert page.poll_live() >= 4
    assert page.table.rowCount() >= 4
    page.set_filter(category="exchange")
    assert [e["message"] for e in page.visible_events()] == ["socket closed"]
    page.set_filter(level="ERROR")
    assert all(e["level"] in ("ERROR", "CRITICAL") for e in page.visible_events())
    page.set_filter(symbol="BTC")
    assert [e.get("reason_code") for e in page.visible_events()] == ["wide_spread"]
    page.set_filter(trade_id="12")
    assert [e.get("trade_id") for e in page.visible_events()] == [12]
    page.set_filter(search="plain warning")
    assert page.table.rowCount() == 1
    page.set_filter(start=datetime.now() + timedelta(hours=1), end=datetime.now() + timedelta(hours=2))
    assert page.visible_events() == []
    page.set_filter()
    # رکورد تازه فقط اگر با فیلتر بخواند به جدول اضافه می‌شود
    page.set_filter(category="exchange")
    before = page.table.rowCount()
    logging.getLogger("trading.auto_trader").warning("not exchange")
    logging.getLogger("market.providers.lbank").warning("exchange again")
    flush(structured)
    page.poll_live()
    assert page.table.rowCount() == before + 1


def test_log_center_copy_export_clear_and_history(page, structured, tmp_path):
    _seed()
    flush(structured, page._store)
    page.refresh()
    page.set_filter(symbol="BTC")
    text = page.copy_selected()
    assert "wide_spread" in text
    assert page.export_to(tmp_path / "out.csv") == 1
    page.set_filter()
    page.clear_view()
    assert page.table.rowCount() == 0
    page.history_check.setChecked(True)  # تاریخچه از فایل‌ها
    assert any(e["message"] == "socket closed" for e in page.visible_events())


async def test_log_center_scan_and_timeline_tabs(page, structured, db):
    trader = make(repo=PaperTradeRepository(db), ticks=ticks_with_book(), **ULTRA)

    async def source():
        audit.note_scan(scanned=12, raw=9, reasons={"low_momentum": 8})
        return [candidate()]

    trader._candidate_source = source
    await trader._scan_for_entries()
    trade = trader.open_trades[0]
    await trader.close_trade(trade, "take_profit")
    flush(structured, page._store)
    result = page.refresh_scan()
    assert result["latest"]["scanned_symbols"] == 12
    assert result["latest"]["opened_trades"] == 1
    assert result["total"]["rejected_volatility"] == 8
    assert page.reason_table.rowCount() >= 1
    page.refresh_trade_ids()
    assert page.timeline_combo.count() >= 1
    stages = page.load_timeline(f"#{trade.trade_id}")
    assert all(stage["status"] == "done" for stage in stages)
    assert page.timeline_table.rowCount() >= 6


def test_log_center_fits_a_laptop_screen_and_retranslates(page):
    from localization import Translator

    assert page.minimumSizeHint().height() <= 660
    page.tr_ = Translator("en")
    page.retranslate()
    assert page.tabs.tabText(0) == "Live log"
    assert page.export_button.text() == "Export"


def test_log_center_is_registered_in_the_main_window():
    from ui.icons.paths import ICON_PATHS
    from ui.windows.main_window import NAV_ICONS, MainWindow

    keys = [key for key, _cls in MainWindow.PAGES]
    assert keys.index("nav.logs") == keys.index("nav.reports") + 1
    assert NAV_ICONS["nav.logs"] in ICON_PATHS
    for lang in ("fa", "en"):
        base = Path(__file__).resolve().parents[1] / "localization" / lang
        assert "logs" in json.loads((base / "nav.json").read_text(encoding="utf-8"))
        assert (base / "logs.json").exists()
    fa = json.loads((Path(__file__).resolve().parents[1] / "localization/fa/logs.json").read_text(encoding="utf-8"))
    en = json.loads((Path(__file__).resolve().parents[1] / "localization/en/logs.json").read_text(encoding="utf-8"))
    assert fa.keys() == en.keys()
