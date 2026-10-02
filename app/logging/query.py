"""
فیلتر، خط زمانی و خروجی رویدادهای لاگ — مستقل از رابط کاربری (نسخهٔ ۲.۶.۰).

«مرکز لاگ» همین توابع را صدا می‌زند تا منطق فیلتر بدون Qt آزمون‌پذیر باشد.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.logging.audit import EVENT_STAGE, SUMMARY_BUCKETS, TIMELINE_STAGES

LEVEL_ORDER = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


@dataclass
class LogFilter:
    """
    معیارهای فیلتر. خالی = بدون محدودیت.

    `min_level`: حداقل سطح (WARNING یعنی WARNING و بالاتر).
    """

    categories: set[str] = field(default_factory=set)
    min_level: str = ""
    symbol: str = ""
    trade_id: str = ""
    start: datetime | None = None
    end: datetime | None = None
    search: str = ""
    events: set[str] = field(default_factory=set)

    def matches(self, event: dict[str, Any]) -> bool:
        if self.categories and str(event.get("category", "")) not in self.categories:
            return False
        if self.min_level:
            if LEVEL_ORDER.get(str(event.get("level", "")).upper(), 0) < LEVEL_ORDER.get(self.min_level.upper(), 0):
                return False
        if self.events and str(event.get("event", "")) not in self.events:
            return False
        if self.symbol:
            wanted = self.symbol.strip().upper().replace("/", "")
            have = str(event.get("symbol") or "").upper().replace("/", "")
            if wanted not in have:
                return False
        if self.trade_id:
            if str(event.get("trade_id", "")) != self.trade_id.strip().lstrip("#"):
                return False
        epoch = float(event.get("epoch") or 0.0)
        if self.start is not None and epoch < self.start.timestamp():
            return False
        if self.end is not None and epoch > self.end.timestamp():
            return False
        if self.search:
            needle = self.search.strip().lower()
            haystack = " ".join(str(event.get(k, "")) for k in ("message", "module", "reason_code", "symbol", "event")).lower()
            if needle not in haystack and needle not in json.dumps(event.get("context") or {}, ensure_ascii=False).lower():
                return False
        return True


def filter_events(events: Iterable[dict[str, Any]], criteria: LogFilter) -> list[dict[str, Any]]:
    return [event for event in events if criteria.matches(event)]


def timeline_stages(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    رویدادهای یک معامله → مراحل Signal → Candidate → Validation → Entry →
    Monitoring → Exit؛ هر مرحله: وضعیت (done/missing)، زمان اولین رویداد و
    فهرست رویدادها. مرحلهٔ بی‌رویداد «missing» است (مثلاً معاملهٔ دستی سیگنال ندارد).
    """
    grouped: dict[str, list[dict[str, Any]]] = {stage: [] for stage in TIMELINE_STAGES}
    for event in sorted(events, key=lambda e: float(e.get("epoch") or 0.0)):
        stage = EVENT_STAGE.get(str(event.get("event", "")))
        if stage:
            grouped[stage].append(event)
    result = []
    for stage in TIMELINE_STAGES:
        items = grouped[stage]
        result.append({
            "stage": stage,
            "status": "done" if items else "missing",
            "ts": items[0].get("ts") if items else "",
            "events": items,
        })
    return result


SUMMARY_COLUMNS: tuple[str, ...] = (
    "scanned_symbols", "raw_candidates",
    *(f"rejected_{bucket}" for bucket in SUMMARY_BUCKETS),
    "source_candidates", "final_candidates", "opened_trades",
)


def summary_row(event: dict[str, Any]) -> dict[str, Any]:
    """رویداد scan_summary → ردیف جدول تشخیص."""
    context = dict(event.get("context") or {})
    row = {"ts": event.get("ts", ""), "engine": context.get("engine", ""), "scans": context.get("scans", 1)}
    for column in SUMMARY_COLUMNS:
        row[column] = int(context.get(column) or 0)
    row["reasons"] = context.get("reasons") or {}
    return row


def total_summary(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """جمع ستون‌های چند خلاصه (ردیف «جمع» جدول)."""
    total: dict[str, Any] = {column: 0 for column in SUMMARY_COLUMNS}
    total["scans"] = 0
    reasons: dict[str, int] = {}
    for row in rows:
        total["scans"] += int(row.get("scans") or 1)
        for column in SUMMARY_COLUMNS:
            total[column] += int(row.get(column) or 0)
        for code, count in (row.get("reasons") or {}).items():
            reasons[code] = reasons.get(code, 0) + int(count)
    total["reasons"] = dict(sorted(reasons.items(), key=lambda kv: -kv[1]))
    return total


def format_event_line(event: dict[str, Any]) -> str:
    """یک خط خوانا برای کپی."""
    parts = [str(event.get("ts", "")), str(event.get("level", "")), str(event.get("category", "")).upper(),
             str(event.get("module", ""))]
    for key in ("event", "symbol", "trade_id", "reason_code"):
        if event.get(key) not in (None, ""):
            parts.append(f"{key}={event[key]}")
    parts.append(str(event.get("message", "")))
    context = event.get("context") or {}
    if context:
        parts.append(json.dumps(context, ensure_ascii=False, default=str))
    return " | ".join(parts)


EXPORT_FIELDS = ("ts", "level", "category", "module", "event", "symbol", "trade_id", "reason_code",
                 "scan_id", "correlation_id", "message", "context")


def export_events(events: Iterable[dict[str, Any]], path: Path | str) -> int:
    """
    خروجی رویدادها: پسوند `.csv` → CSV (UTF-8 با BOM برای اکسل)، `.txt` → متن،
    بقیه → JSONL. بازگشت: تعداد ردیف.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    items = list(events)
    suffix = target.suffix.lower()
    if suffix == ".csv":
        with open(target, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(EXPORT_FIELDS), extrasaction="ignore")
            writer.writeheader()
            for event in items:
                row = {k: event.get(k, "") for k in EXPORT_FIELDS}
                row["context"] = json.dumps(event.get("context") or {}, ensure_ascii=False, default=str)
                writer.writerow(row)
    elif suffix == ".txt":
        with open(target, "w", encoding="utf-8") as handle:
            for event in items:
                handle.write(format_event_line(event) + "\n")
    else:
        with open(target, "w", encoding="utf-8") as handle:
            for event in items:
                public = {k: v for k, v in event.items() if k not in ("persist", "seq")}
                handle.write(json.dumps(public, ensure_ascii=False, default=str) + "\n")
    return len(items)


__all__ = [
    "LEVEL_ORDER",
    "LogFilter",
    "SUMMARY_COLUMNS",
    "export_events",
    "filter_events",
    "format_event_line",
    "summary_row",
    "timeline_stages",
    "total_summary",
]
