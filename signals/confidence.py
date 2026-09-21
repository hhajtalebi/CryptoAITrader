"""
مدل «میزان اطمینان» واقع‌بینانه.

چرا این پرونده ساخته شد؟
    کاربر گزارش کرد سیگنال‌هایی با اطمینان ۸۰، ۹۰ و ۱۰۰ درصد ضرر داده‌اند.
    بررسی نشان داد فرمول قبلی این بود:

        alignment = |score| * 0.6 + consensus * 0.4

    و `consensus` سهم رأی‌های هم‌جهت **از میان رأی‌های موجود** بود. پس اگر
    فقط **یک** راهبرد قابل اعمال بود و امتیاز کاملی می‌داد، حاصل می‌شد
    ۱۰۰٪ — با یک شاهد. سامانه در مجموع فقط ۳ راهبرد دارد، بنابراین رسیدن
    به اعداد بالا بسیار آسان بود و آن اعداد هیچ ربطی به احتمال موفقیت
    نداشتند.

فلسفهٔ این مدل:
    ضریب اطمینان باید **کمیاب** باشد. عدد بالا فقط وقتی مجاز است که
    شواهد مستقلِ فراوانی هم‌جهت باشند. هر کمبودی در شواهد، سقف را
    پایین می‌آورد — نه اینکه امتیاز را کمی کم کند.

چهار مؤلفه:
    ۱. قدرت امتیاز (چقدر جهت‌دار است)
    ۲. اجماع (چند درصد رأی‌ها هم‌جهت‌اند)
    ۳. پوشش شواهد (چند راهبرد و چند تایم‌فریم واقعاً رأی داده‌اند)
    ۴. کالیبراسیون تاریخی (در عمل چند درصد از این بازه سودده بوده‌اند)

مؤلفهٔ چهارم اختیاری است و تنها وقتی اعمال می‌شود که نمونهٔ کافی وجود
داشته باشد؛ بدون آن، سامانه دربارهٔ خودش ادعای اثبات‌نشده نمی‌کند.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# سقف اطمینان بر اساس تعداد راهبردهای مستقلی که رأی داده‌اند.
#
# با یک شاهد نمی‌توان «۹۰٪ مطمئن» بود. این جدول همان چیزی است که جلوی
# تکرار شکایت کاربر را می‌گیرد.
COVERAGE_CAPS: dict[int, int] = {0: 0, 1: 45, 2: 65, 3: 80}
# بیش از ۳ راهبرد → سقف کامل
FULL_COVERAGE_CAP = 95

# سقف بر اساس تعداد تایم‌فریم‌هایی که تحلیل شده‌اند.
# یک تایم‌فریم تنها، تصویر کاملی از بازار نمی‌دهد.
TIMEFRAME_CAPS: dict[int, int] = {0: 0, 1: 60, 2: 80}
FULL_TIMEFRAME_CAP = 95

# حداکثر اطمینانی که سامانه **هرگز** از آن فراتر نمی‌رود.
#
# ۱۰۰٪ یعنی «قطعی»، و در بازار هیچ‌چیز قطعی نیست. نمایش ۱۰۰٪ به کاربر
# وعده‌ای است که هیچ سامانه‌ای نمی‌تواند به آن عمل کند.
ABSOLUTE_CAP = 92

# کمترین تعداد نمونه برای اینکه آمار تاریخی معنادار باشد.
MIN_SAMPLES_FOR_CALIBRATION = 20

# وزن کالیبراسیون تاریخی وقتی نمونهٔ کافی هست.
CALIBRATION_WEIGHT = 0.35


@dataclass(slots=True)
class ConfidenceBreakdown:
    """
    تفکیک کامل نحوهٔ رسیدن به عدد نهایی.

    کاربر باید بتواند ببیند عدد از کجا آمده؛ «۷۳٪» بدون توضیح، همان
    جعبهٔ سیاهی است که به آن اعتماد نشد.
    """

    score_strength: float = 0.0
    consensus: float = 0.0
    strategy_count: int = 0
    timeframe_count: int = 0
    raw: int = 0
    coverage_cap: int = 100
    timeframe_cap: int = 100
    calibrated_from: int | None = None
    sample_size: int = 0
    final: int = 0
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """نمایش دیکشنری برای ذخیره و آزمون."""
        return {
            "score_strength": round(self.score_strength, 4),
            "consensus": round(self.consensus, 4),
            "strategy_count": self.strategy_count,
            "timeframe_count": self.timeframe_count,
            "raw": self.raw,
            "coverage_cap": self.coverage_cap,
            "timeframe_cap": self.timeframe_cap,
            "calibrated_from": self.calibrated_from,
            "sample_size": self.sample_size,
            "final": self.final,
            "reasons": list(self.reasons),
        }


def coverage_cap(strategy_count: int) -> int:
    """سقف اطمینان بر پایهٔ تعداد راهبردهای رأی‌داده."""
    if strategy_count >= 4:
        return FULL_COVERAGE_CAP
    return COVERAGE_CAPS.get(max(0, strategy_count), FULL_COVERAGE_CAP)


def timeframe_cap(timeframe_count: int) -> int:
    """سقف اطمینان بر پایهٔ تعداد تایم‌فریم‌های تحلیل‌شده."""
    if timeframe_count >= 3:
        return FULL_TIMEFRAME_CAP
    return TIMEFRAME_CAPS.get(max(0, timeframe_count), FULL_TIMEFRAME_CAP)


def historical_win_rate(
    buckets: dict[str, dict[str, Any]] | None, confidence: int
) -> tuple[float | None, int]:
    """
    نرخ برد واقعی برای بازه‌ای که این اطمینان در آن می‌افتد.

    بازگشتی: (نرخ برد ۰ تا ۱ یا None، تعداد نمونه)

    None یعنی «هنوز داده‌ای نداریم» و در آن حالت هیچ تعدیلی انجام
    نمی‌شود؛ حدس‌زدن بدتر از ندانستن است.
    """
    if not buckets:
        return None, 0
    low = max(0, min(100, int(confidence))) // 10 * 10
    key = f"{low}-{low + 9}"
    entry = buckets.get(key)
    if not isinstance(entry, dict):
        return None, 0

    total = int(entry.get("resolved") or entry.get("total") or 0)
    if total < MIN_SAMPLES_FOR_CALIBRATION:
        return None, total

    win_rate = entry.get("win_rate")
    if win_rate is None:
        wins = int(entry.get("wins") or 0)
        win_rate = (wins / total * 100.0) if total else None
    if win_rate is None:
        return None, total

    value = float(win_rate)
    # نرخ برد ممکن است ۰ تا ۱ یا ۰ تا ۱۰۰ باشد
    if value > 1.0:
        value = value / 100.0
    return max(0.0, min(1.0, value)), total


def compute(
    *,
    score: float,
    consensus: float,
    strategy_count: int,
    timeframe_count: int,
    buckets: dict[str, dict[str, Any]] | None = None,
) -> ConfidenceBreakdown:
    """
    محاسبهٔ ضریب اطمینان واقع‌بینانه.

    `score` در بازهٔ ۱- تا ۱+، `consensus` در بازهٔ ۰ تا ۱.
    `strategy_count` تعداد راهبردهای **متمایزی** است که رأی جهت‌دار
    داده‌اند و `timeframe_count` تعداد تایم‌فریم‌های تحلیل‌شده.
    """
    strength = min(abs(float(score)), 1.0)
    agreement = max(0.0, min(1.0, float(consensus)))
    breakdown = ConfidenceBreakdown(
        score_strength=strength,
        consensus=agreement,
        strategy_count=int(strategy_count),
        timeframe_count=int(timeframe_count),
    )

    # پایه: قدرت امتیاز و اجماع، ولی هیچ‌کدام به‌تنهایی کافی نیست.
    base = strength * 0.55 + agreement * 0.45
    breakdown.raw = int(round(base * 100))

    cap_strategies = coverage_cap(int(strategy_count))
    cap_frames = timeframe_cap(int(timeframe_count))
    breakdown.coverage_cap = cap_strategies
    breakdown.timeframe_cap = cap_frames

    value = min(breakdown.raw, cap_strategies, cap_frames, ABSOLUTE_CAP)

    if cap_strategies < breakdown.raw:
        breakdown.reasons.append(
            f"سقف {cap_strategies}٪ چون فقط {strategy_count} راهبرد رأی داده است"
        )
    if cap_frames < breakdown.raw:
        breakdown.reasons.append(
            f"سقف {cap_frames}٪ چون فقط {timeframe_count} تایم‌فریم بررسی شده است"
        )

    # کالیبراسیون با نتایج واقعی گذشته
    win_rate, samples = historical_win_rate(buckets, value)
    breakdown.sample_size = samples
    if win_rate is not None:
        breakdown.calibrated_from = value
        blended = value * (1.0 - CALIBRATION_WEIGHT) + (win_rate * 100.0) * CALIBRATION_WEIGHT
        value = int(round(blended))
        breakdown.reasons.append(
            f"تعدیل با نتایج واقعی: نرخ برد این بازه {win_rate * 100:.0f}٪ "
            f"در {samples} سیگنال گذشته"
        )

    breakdown.final = max(0, min(int(value), ABSOLUTE_CAP))
    if not breakdown.reasons:
        breakdown.reasons.append(
            f"{strategy_count} راهبرد در {timeframe_count} تایم‌فریم هم‌جهت‌اند"
        )
    return breakdown
