"""
اعتبارسنجی و ترمیم خروجی JSON مدل زبانی.

چرا وجود دارد؟
    مدل‌های زبانی — به‌ویژه مدل‌های محلی کوچک — گاهی JSON را داخل بلوک کد
    می‌گذارند، قبل و بعدش توضیح می‌نویسند، یا فیلدی را جا می‌اندازند. بند
    ۵۴ سند پروژه می‌گوید خروجی باید ساختاریافته و معتبر باشد و در صورت
    نامعتبر بودن، یک بار تلاش ترمیم انجام شود.

راهبرد سه‌مرحله‌ای:
    ۱) استخراج متن JSON از پاسخ (حذف ```json و متن اضافی)
    ۲) تحلیل نحوی و اصلاح خطاهای رایج (کاما اضافی، نقل‌قول تکی)
    ۳) اعتبارسنجی معنایی: وجود فیلدها، بازه اعداد، منطق حد ضرر و اهداف

اگر مرحله ۳ شکست بخورد، خطاها به مدل بازگردانده می‌شوند تا خودش اصلاح کند.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.constants import SignalDirection
from app.logging import get_logger

logger = get_logger(__name__)

_CODE_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")

VALID_SIGNALS = {"LONG", "SHORT", "WAIT"}
VALID_TRENDS = {"BULLISH", "BEARISH", "NEUTRAL"}
VALID_STRUCTURES = {"BULLISH", "BEARISH", "RANGING", "BREAKOUT", "BREAKDOWN", "UNDEFINED"}


@dataclass(slots=True)
class ValidationOutcome:
    """نتیجه اعتبارسنجی یک پاسخ."""

    valid: bool
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def error_text(self) -> str:
        """خطاها به‌صورت متن، جهت ارسال به مدل برای ترمیم."""
        return "; ".join(self.errors)


class ResponseValidator:
    """اعتبارسنج خروجی سیگنال."""

    def __init__(self, *, max_leverage: int = 10, min_risk_reward: float = 1.5) -> None:
        self._max_leverage = max_leverage
        self._min_risk_reward = min_risk_reward

    def set_max_leverage(self, value: int) -> None:
        """هم‌گام‌سازی سقف اهرم با تنظیمات ریسک کاربر."""
        self._max_leverage = max(1, int(value))

    def set_min_risk_reward(self, value: float) -> None:
        """هم‌گام‌سازی حداقل نسبت ریسک به ریوارد با تنظیمات کاربر."""
        self._min_risk_reward = max(0.0, float(value))

    # ------------------------------------------------------------------
    # مرحله ۱ و ۲: استخراج و تحلیل نحوی
    # ------------------------------------------------------------------
    @staticmethod
    def extract_json(text: str) -> dict[str, Any] | None:
        """
        بیرون کشیدن اولین شیء JSON معتبر از متن پاسخ.

        ترتیب تلاش: کل متن → داخل بلوک کد → از اولین { تا آخرین }
        """
        if not text or not text.strip():
            return None

        candidates: list[str] = [text.strip()]

        fence = _CODE_FENCE.search(text)
        if fence:
            candidates.append(fence.group(1).strip())

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            candidates.append(text[start : end + 1])

        for candidate in candidates:
            for attempt in (candidate, _TRAILING_COMMA.sub(r"\1", candidate)):
                try:
                    parsed = json.loads(attempt)
                except (json.JSONDecodeError, ValueError):
                    continue
                if isinstance(parsed, dict):
                    return parsed
        return None

    # ------------------------------------------------------------------
    # مرحله ۳: اعتبارسنجی معنایی
    # ------------------------------------------------------------------
    def validate_signal(self, text: str, *, symbol: str = "") -> ValidationOutcome:
        """
        بررسی کامل یک پاسخ سیگنال.

        قواعد کلیدی:
            • جهت باید LONG/SHORT/WAIT باشد
            • برای WAIT نیازی به قیمت نیست
            • برای LONG حد ضرر باید زیر ورود و اهداف بالای آن باشند (و برعکس)
            • اهداف باید مرتب و در جهت معامله باشند
            • اهرم نباید از سقف مجاز کاربر بیشتر باشد
        """
        data = self.extract_json(text)
        if data is None:
            return ValidationOutcome(False, errors=["Response is not valid JSON"])

        errors: list[str] = []
        warnings: list[str] = []

        # علامت اختصاصی مدل برای نبود داده کافی
        if str(data.get("signal", "")).upper() == "INSUFFICIENT_DATA":
            data["signal"] = "WAIT"
            warnings.append("Model reported INSUFFICIENT_DATA; converted to WAIT")

        signal = str(data.get("signal", "")).upper().strip()
        if signal not in VALID_SIGNALS:
            errors.append(f"'signal' must be one of LONG/SHORT/WAIT, got '{data.get('signal')}'")
        data["signal"] = signal

        # اعداد اختیاری
        entry_min, entry_max = self._parse_entry(data, errors)
        stop_loss = self._as_float(data.get("stop_loss"))
        take_profits = self._parse_take_profits(data, errors)

        confidence = self._as_float(data.get("confidence"))
        if confidence is None:
            errors.append("'confidence' is required (0-100)")
        elif not 0 <= confidence <= 100:
            errors.append(f"'confidence' must be between 0 and 100, got {confidence}")
        else:
            data["confidence"] = int(round(confidence))

        leverage = self._as_float(data.get("leverage"))
        if leverage is not None:
            if leverage < 1:
                errors.append("'leverage' must be at least 1")
            elif leverage > self._max_leverage:
                warnings.append(
                    f"Leverage {leverage:g} exceeds the user limit; clamped to {self._max_leverage}"
                )
                leverage = self._max_leverage
            data["leverage"] = int(leverage) if leverage else 1

        trend = str(data.get("trend", "NEUTRAL")).upper().strip()
        if trend not in VALID_TRENDS:
            warnings.append(f"Unknown trend '{trend}', defaulted to NEUTRAL")
            trend = "NEUTRAL"
        data["trend"] = trend

        structure = str(data.get("market_structure", "UNDEFINED")).upper().strip()
        if structure not in VALID_STRUCTURES:
            warnings.append(f"Unknown market structure '{structure}', defaulted to UNDEFINED")
            structure = "UNDEFINED"
        data["market_structure"] = structure

        if not str(data.get("reason", "")).strip():
            errors.append("'reason' must explain the decision")

        # قواعد وابسته به جهت
        if signal in {"LONG", "SHORT"}:
            errors.extend(
                self._validate_directional(signal, entry_min, entry_max, stop_loss, take_profits)
            )
            if stop_loss is not None and entry_min is not None and entry_min > 0:
                risk = abs(entry_min - stop_loss) / entry_min * 100
                if risk > 20:
                    warnings.append(f"Stop loss is {risk:.1f}% away — unusually wide")
            if not str(data.get("invalidation", "")).strip():
                warnings.append("No invalidation condition provided")
        elif signal == "WAIT":
            data["entry"] = {"min": None, "max": None}
            data["stop_loss"] = None
            data["take_profit"] = []

        if symbol and not str(data.get("symbol", "")).strip():
            data["symbol"] = symbol

        # محاسبه یا اصلاح نسبت ریسک به ریوارد از روی اعداد واقعی
        computed_rr = self._compute_risk_reward(signal, entry_min, stop_loss, take_profits)
        if computed_rr is not None:
            reported = self._as_float(data.get("risk_reward"))
            if reported is not None and abs(reported - computed_rr) > 0.3:
                warnings.append(
                    f"Model reported R/R {reported:g} but the numbers give {computed_rr:g}; corrected"
                )
            data["risk_reward"] = computed_rr
            if computed_rr < self._min_risk_reward:
                # رد نهایی با موتور ریسک است؛ اینجا فقط پرچم می‌زنیم
                warnings.append(
                    f"Risk/reward {computed_rr:g} is below the user minimum "
                    f"{self._min_risk_reward:g}; the risk engine may reject this setup"
                )

        outcome = ValidationOutcome(valid=not errors, data=data, errors=errors, warnings=warnings)
        if warnings:
            logger.debug("Signal validation warnings: %s", warnings)
        return outcome

    # ------------------------------------------------------------------
    # کمکی‌ها
    # ------------------------------------------------------------------
    @staticmethod
    def _as_float(value: Any) -> float | None:
        """تبدیل امن به عدد؛ None برای مقادیر غیرعددی."""
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return None if number != number else number  # حذف NaN

    def _parse_entry(
        self, data: dict[str, Any], errors: list[str]
    ) -> tuple[float | None, float | None]:
        """
        پذیرش هر دو قالب ورود: عدد تکی یا محدوده {min, max}.
        """
        entry = data.get("entry")
        if entry is None:
            return None, None

        if isinstance(entry, dict):
            entry_min = self._as_float(entry.get("min"))
            entry_max = self._as_float(entry.get("max"))
        else:
            entry_min = entry_max = self._as_float(entry)

        if entry_min is not None and entry_max is None:
            entry_max = entry_min
        if entry_max is not None and entry_min is None:
            entry_min = entry_max
        if entry_min is not None and entry_max is not None and entry_min > entry_max:
            entry_min, entry_max = entry_max, entry_min

        if entry_min is not None and entry_min <= 0:
            errors.append("'entry' must be a positive price")

        data["entry"] = {"min": entry_min, "max": entry_max}
        return entry_min, entry_max

    def _parse_take_profits(self, data: dict[str, Any], errors: list[str]) -> list[float]:
        """نرمال‌سازی فهرست اهداف سود."""
        raw = data.get("take_profit", [])
        if raw is None:
            raw = []
        if isinstance(raw, (int, float, str)):
            raw = [raw]
        if not isinstance(raw, list):
            errors.append("'take_profit' must be a list of prices")
            return []

        targets: list[float] = []
        for item in raw:
            if isinstance(item, dict):
                item = item.get("price", item.get("value"))
            number = self._as_float(item)
            if number is not None and number > 0:
                targets.append(number)
        data["take_profit"] = targets
        return targets

    @staticmethod
    def _validate_directional(
        signal: str,
        entry_min: float | None,
        entry_max: float | None,
        stop_loss: float | None,
        take_profits: list[float],
    ) -> list[str]:
        """بررسی سازگاری منطقی اعداد با جهت معامله."""
        errors: list[str] = []
        if entry_min is None:
            errors.append(f"'entry' is required for a {signal} signal")
        if stop_loss is None:
            errors.append(f"'stop_loss' is required for a {signal} signal")
        if not take_profits:
            errors.append(f"At least one take profit is required for a {signal} signal")

        if entry_min is None or stop_loss is None:
            return errors

        reference = entry_min if signal == "LONG" else (entry_max or entry_min)
        if signal == "LONG":
            if stop_loss >= reference:
                errors.append(f"For LONG, stop_loss ({stop_loss:g}) must be below entry ({reference:g})")
            bad = [tp for tp in take_profits if tp <= reference]
            if bad:
                errors.append(f"For LONG, take profits must be above entry; got {bad}")
            if take_profits != sorted(take_profits):
                errors.append("For LONG, take profits must be in ascending order")
        else:
            if stop_loss <= reference:
                errors.append(f"For SHORT, stop_loss ({stop_loss:g}) must be above entry ({reference:g})")
            bad = [tp for tp in take_profits if tp >= reference]
            if bad:
                errors.append(f"For SHORT, take profits must be below entry; got {bad}")
            if take_profits != sorted(take_profits, reverse=True):
                errors.append("For SHORT, take profits must be in descending order")
        return errors

    @staticmethod
    def _compute_risk_reward(
        signal: str, entry: float | None, stop_loss: float | None, take_profits: list[float]
    ) -> float | None:
        """محاسبه نسبت ریسک به ریوارد بر پایه هدف اول."""
        if signal not in {"LONG", "SHORT"} or entry is None or stop_loss is None or not take_profits:
            return None
        risk = abs(entry - stop_loss)
        if risk <= 0:
            return None
        return round(abs(take_profits[0] - entry) / risk, 2)

    @staticmethod
    def to_signal_direction(value: str) -> SignalDirection:
        """تبدیل رشته سیگنال به Enum داخلی برنامه."""
        try:
            return SignalDirection(value.upper())
        except ValueError:
            return SignalDirection.WAIT
