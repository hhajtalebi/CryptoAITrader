# افزودن اندیکاتور جدید

معماری اندیکاتورها بر پایه «رجیستری» است: هر اندیکاتور یک کلاس مستقل است که
خودش را معرفی می‌کند. برای افزودن اندیکاتور تازه **نیازی به تغییر موتور،
رابط کاربری یا موتور سیگنال نیست**.

## ۱. جای درست فایل

| دسته | فایل | نمونه‌ها |
|---|---|---|
| روند | `indicators/trend.py` | SMA, EMA, ADX, Ichimoku |
| مومنتوم | `indicators/momentum.py` | RSI, MACD, Stochastic |
| نوسان | `indicators/volatility.py` | ATR, Bollinger, Keltner |
| حجم | `indicators/volume.py` | OBV, VWAP, CMF |
| حمایت/مقاومت | `indicators/support_resistance.py` | Pivot, Fibonacci |

## ۲. نوشتن کلاس

هر اندیکاتور از `BaseIndicator` ارث می‌برد و سه عضو دارد:

```python
class SuperTrendIndicator(BaseIndicator):
    """
    اندیکاتور SuperTrend.

    فرمول: بر پایه ATR و میانه قیمت، یک خط دنبال‌کننده روند می‌سازد که با
    عبور قیمت از آن، جهت روند تغییر می‌کند.
    """

    @property
    def metadata(self) -> IndicatorMetadata:
        """معرفی اندیکاتور به رجیستری و رابط کاربری."""
        return IndicatorMetadata(
            name="SUPERTREND",
            display_name_fa="سوپر ترند",
            display_name_en="SuperTrend",
            category=IndicatorCategory.TREND,
            default_parameters={"period": 10, "multiplier": 3.0},
            min_candles=30,          # حداقل کندل لازم
            output_keys=["supertrend", "direction"],
        )

    def _compute(self, df: pd.DataFrame, **params) -> dict[str, Any]:
        """
        محاسبه اصلی.

        df ستون‌های open/high/low/close/volume دارد و بر اساس زمان مرتب است.
        خروجی: دیکشنری از نام خروجی به سری یا عدد.
        """
        period = int(params["period"])
        multiplier = float(params["multiplier"])
        # ... محاسبه ...
        return {"supertrend": line, "direction": direction}

    def interpret(self, values: dict[str, Any], df: pd.DataFrame) -> str:
        """
        تبدیل عدد به سیگنال قابل فهم.

        فقط از واژگان استاندارد پروژه استفاده کنید:
        BULLISH, BEARISH, NEUTRAL, STRONG_BULLISH, STRONG_BEARISH,
        OVERBOUGHT, OVERSOLD, BREAKOUT_UP, BREAKOUT_DOWN, ...
        """
        return "BULLISH" if values["direction"] > 0 else "BEARISH"
```

## ۳. ثبت در رجیستری

در انتهای `indicators/registry.py` داخل تابع `register_builtin_indicators`
یک سطر اضافه کنید:

```python
indicator_registry.register(SuperTrendIndicator)
```

همین. اندیکاتور بلافاصله در این سه جا ظاهر می‌شود:
- فهرست `IndicatorEngine.available_indicators`
- ابزار `calculate_indicator` عامل هوش مصنوعی
- فهرست انتخاب اندیکاتور در رابط کاربری

## ۴. قواعد مهم

1. **هیچ داده‌ای نسازید.** اگر کندل کافی نیست، `min_candles` را درست تعیین
   کنید؛ کلاس پایه خودش `InsufficientDataError` را بالا می‌آورد.
2. **از کتابخانه خاصی وابسته نشوید.** همه محاسبات با pandas/numpy انجام
   می‌شوند تا نیازی به TA-Lib و کامپایل بومی نباشد.
3. **`_compute` نباید ورودی را تغییر دهد.** روی کپی کار کنید.
4. **NaN را مدیریت کنید.** خروجی نهایی نباید NaN داشته باشد؛ در صورت لزوم
   `dropna` کنید یا خطا بدهید.
5. **Docstring فارسی الزامی است** و باید فرمول را توضیح دهد.
6. **پارامتر منفی یا صفر را رد کنید** (کلاس پایه بررسی پایه‌ای انجام می‌دهد،
   ولی قواعد اختصاصی با خودتان است).

## ۵. آزمودن با داده واقعی

```python
import asyncio
from indicators import IndicatorEngine
from indicators.registry import register_builtin_indicators
from market.engine import MarketDataEngine
from market.providers.lbank import LBankProvider

async def main():
    register_builtin_indicators()
    engine = MarketDataEngine(LBankProvider(), websocket_enabled=False)
    await engine.start()
    candles = await engine.get_candles("BTC/USDT", "1h", 300)
    result = IndicatorEngine().calculate("SUPERTREND", candles, "1h", symbol="BTC/USDT")
    print(result.latest, result.signal)
    await engine.stop()

asyncio.run(main())
```

**داده مصنوعی یکنواخت نسازید:** سری‌های صعودی خالص، سقف و کف موضعی ندارند و
بسیاری از اندیکاتورها روی آن‌ها نتیجه بی‌معنا می‌دهند. یا داده واقعی بگیرید،
یا روند + نوفه تصادفی بسازید.

## چک‌لیست نهایی

- [ ] `metadata` با نام فارسی و انگلیسی کامل شده
- [ ] `min_candles` واقع‌بینانه است
- [ ] `interpret` فقط از واژگان استاندارد استفاده می‌کند
- [ ] در `register_builtin_indicators` ثبت شده
- [ ] با داده واقعی بازار آزموده شده
- [ ] Docstring فارسی دارد
