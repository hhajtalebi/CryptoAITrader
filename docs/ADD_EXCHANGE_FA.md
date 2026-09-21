<div dir="rtl">

# افزودن صرافی جدید

این راهنما نشان می‌دهد چگونه یک صرافی تازه به برنامه اضافه کنید، بدون آنکه حتی یک خط از هسته برنامه تغییر کند.

---

## اصل طراحی

هسته برنامه هیچ‌گاه نام هیچ صرافی‌ای را نمی‌داند. همه چیز از راه رابط `ExchangeProvider` انجام می‌شود:

</div>

```
                       ┌──────────────────────┐
   موتور سیگنال  ──→   │  MarketDataEngine    │
   موتور اندیکاتور     └──────────┬───────────┘
                                  │  فقط رابط عمومی
                       ┌──────────▼───────────┐
                       │   ExchangeProvider   │  (انتزاعی)
                       └──────────┬───────────┘
                        ┌─────────┼─────────┐
                   LBankProvider  │   BinanceProvider …
                                  │
                            (صرافی شما)
```

<div dir="rtl">

اگر جایی در `market/engine.py`، `signals/` یا `indicators/` نام صرافی خاصی را دیدید، آن یک اشکال است.

---

## گام ۱ — ساخت پوشه

</div>

```
market/providers/mybourse/
├── __init__.py
├── constants.py          نشانی‌ها، نگاشت تایم‌فریم‌ها، کدهای خطا
├── rest_client.py        درخواست‌های HTTP و امضا
├── parser.py             تبدیل پاسخ خام به دیتاکلاس‌های برنامه
├── websocket_client.py   جریان زنده (اختیاری)
└── provider.py           پیاده‌سازی ExchangeProvider
```

<div dir="rtl">

> ⚠ **همه فایل‌ها را پیش از نوشتن `__init__.py` بسازید.** اگر `__init__.py` ماژولی را import کند که هنوز وجود ندارد، کل پکیج از کار می‌افتد.

---

## گام ۲ — ثابت‌ها

</div>

```python
"""ثابت‌های صرافی MyBourse."""

REST_BASE_URL = "https://api.mybourse.com/v1"
WS_URL = "wss://stream.mybourse.com/ws"

#: نگاشت تایم‌فریم داخلی به کد صرافی.
#: فقط تایم‌فریم‌هایی را بیاورید که صرافی **واقعاً** پشتیبانی می‌کند؛
#: بقیه به‌صورت خودکار از تایم‌فریم پایین‌تر ساخته می‌شوند.
TIMEFRAME_MAP: dict[str, str] = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "1h": "1hour",
    "4h": "4hour",
    "1d": "1day",
    "1w": "1week",
}

#: کدهای خطای صرافی و معنایشان (برای پیام خطای قابل فهم)
ERROR_CODES: dict[int, str] = {
    10008: "Trading pair is not supported",
    10016: "Insufficient balance",
}

RATE_LIMIT_PER_SECOND = 10
REQUEST_TIMEOUT = 15.0
```

<div dir="rtl">

**نکته مهم درباره تایم‌فریم‌ها:** وسوسه نشوید همه ۱۳ تایم‌فریم را در این نگاشت بیاورید. اگر صرافی `2h` را نمی‌دهد، آن را ننویسید؛ موتور تایم‌فریم خودش `2h` را از دو کندل `1h` می‌سازد. (در LBank دقیقاً همین وضعیت برای `3m, 2h, 6h, 8h, 12h` وجود دارد.)

---

## گام ۳ — کلاینت REST

</div>

```python
class MyBourseRestClient:
    """کلاینت HTTP صرافی MyBourse."""

    def __init__(self, api_key: str = "", api_secret: str = "") -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._client: httpx.AsyncClient | None = None
        self._limiter = RateLimiter(RATE_LIMIT_PER_SECOND)

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """
        درخواست GET با محدودسازی نرخ و تلاش مجدد.

        هر پاسخ باید از فیلتر `_check_response` بگذرد تا خطای منطقی
        صرافی (که با کد HTTP ۲۰۰ هم می‌آید) به خطای برنامه تبدیل شود.
        """
        await self._limiter.acquire()
        response = await self._client.get(path, params=params or {})
        response.raise_for_status()
        return self._check_response(response.json())

    @staticmethod
    def _check_response(payload: dict[str, Any]) -> Any:
        """
        بررسی موفقیت پاسخ.

        بیشتر صرافی‌ها خطا را با کد HTTP ۲۰۰ و یک فیلد داخل بدنه اعلام
        می‌کنند؛ نادیده گرفتن این فیلد یعنی داده خراب وارد برنامه شود.
        """
        if payload.get("code") not in (0, "0", None):
            code = int(payload.get("code", -1))
            raise ExchangeError(
                ERROR_CODES.get(code, f"Exchange error {code}"),
                user_key="errors.exchange_error",
                details={"code": code},
            )
        return payload.get("data", payload)
```

<div dir="rtl">

---

## گام ۴ — تبدیل داده (parser)

هر صرافی قالب خودش را دارد. این لایه آن را به دیتاکلاس‌های برنامه تبدیل می‌کند و **تنها جایی است که باید قالب صرافی را بشناسد**.

</div>

```python
def parse_candle(raw: list[Any]) -> Candle:
    """
    تبدیل یک کندل خام به دیتاکلاس Candle.

    مراقب واحد زمان باشید: برخی صرافی‌ها ثانیه و برخی میلی‌ثانیه
    می‌دهند. برنامه همه‌جا **ثانیه** را انتظار دارد.
    """
    return Candle(
        timestamp=int(raw[0]) // 1000,   # اگر میلی‌ثانیه است
        open=float(raw[1]),
        high=float(raw[2]),
        low=float(raw[3]),
        close=float(raw[4]),
        volume=float(raw[5]),
    )
```

<div dir="rtl">

---

## گام ۵ — پیاده‌سازی Provider

</div>

```python
class MyBourseProvider(ExchangeProvider):
    """پیاده‌سازی صرافی MyBourse."""

    name = "mybourse"
    display_name = "MyBourse"

    def __init__(self, api_key: str = "", api_secret: str = "") -> None:
        self._client = MyBourseRestClient(api_key, api_secret)

    @property
    def capabilities(self) -> ProviderCapabilities:
        """توانمندی‌های واقعی — نه آرزوها."""
        return ProviderCapabilities(
            name=self.name,
            supports_websocket=True,
            supports_orderbook=True,
            supports_private_api=False,      # نسخه ۱ معامله ندارد
            native_timeframes=set(TIMEFRAME_MAP),
            max_candles_per_request=1000,
        )

    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def ping(self) -> bool: ...
    async def get_symbols(self) -> list[SymbolInfo]: ...
    async def get_ticker(self, symbol: str) -> Ticker: ...
    async def get_all_tickers(self) -> list[Ticker]: ...
    async def get_current_price(self, symbol: str) -> float: ...
    async def get_ohlcv(self, symbol, timeframe, limit=300, end_time=None): ...
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook: ...

    def to_exchange_symbol(self, symbol: str) -> str:
        """BTC/USDT → btc_usdt (قالب دلخواه صرافی)."""
        return symbol.replace("/", "_").lower()

    def from_exchange_symbol(self, exchange_symbol: str) -> str:
        """btc_usdt → BTC/USDT."""
        base, _, quote = exchange_symbol.partition("_")
        return f"{base.upper()}/{quote.upper()}"
```

<div dir="rtl">

### متدهای اجباری

| متد | باید چه کند |
|---|---|
| `capabilities` | توانمندی‌های واقعی صرافی |
| `connect` / `close` | ساخت و آزادسازی منابع شبکه |
| `ping` | بررسی در دسترس بودن (بدون پرتاب خطا؛ `False` برگرداند) |
| `get_symbols` | فهرست کامل نمادها |
| `get_ticker` / `get_all_tickers` | وضعیت ۲۴ ساعته |
| `get_current_price` | قیمت لحظه‌ای |
| `get_ohlcv` | کندل‌ها، مرتب‌شده صعودی بر پایه زمان |
| `get_orderbook` | دفتر سفارش |
| `to_exchange_symbol` / `from_exchange_symbol` | نگاشت دوطرفه نماد |

متدهای خصوصی (`get_account_balance`, `test_credentials`, …) پیاده‌سازی پیش‌فرض خالی دارند و اختیاری‌اند.

---

## گام ۶ — ثبت در رجیستری

در `market/providers/registry.py`، داخل تابع `register_builtin_providers`:

</div>

```python
def register_builtin_providers() -> None:
    """
    ثبت صرافی‌های داخلی.

    این تابع باید صریحاً فراخوانی شود (در `Application.__init__`)؛
    ثبت خودکار هنگام import عمداً انجام نمی‌شود تا وارد کردن یک ماژول
    عارضه جانبی نداشته باشد.
    """
    from market.providers.lbank import LBankProvider
    from market.providers.mybourse import MyBourseProvider   # ← افزوده شد

    provider_registry.register("lbank", LBankProvider)
    provider_registry.register("mybourse", MyBourseProvider)  # ← افزوده شد
```

<div dir="rtl">

همین. صرافی جدید حالا در صفحه تنظیمات و ویزارد اولین اجرا دیده می‌شود.

---

## گام ۷ — آزمون

</div>

```python
@pytest.mark.asyncio
async def test_symbol_mapping_round_trips() -> None:
    """نگاشت نماد باید برگشت‌پذیر باشد."""
    provider = MyBourseProvider()
    assert provider.from_exchange_symbol(provider.to_exchange_symbol("BTC/USDT")) == "BTC/USDT"


@pytest.mark.asyncio
async def test_candles_are_sorted_and_complete() -> None:
    """کندل‌ها باید صعودی و بدون حفره باشند."""
    provider = MyBourseProvider()
    await provider.connect()
    try:
        candles = await provider.get_ohlcv("BTC/USDT", "1h", limit=100)
    finally:
        await provider.close()

    assert len(candles) >= 90
    times = [c.timestamp for c in candles]
    assert times == sorted(times)
```

<div dir="rtl">

---

## اشتباه‌های رایج

| اشتباه | نتیجه |
|---|---|
| نادیده گرفتن فیلد خطای داخل بدنه پاسخ | داده خراب بی‌صدا وارد تحلیل می‌شود |
| اشتباه گرفتن ثانیه و میلی‌ثانیه | نمودار به سال ۱۹۷۰ یا ۵۴۰۰۰ می‌پرد |
| نیاوردن محدودساز نرخ | صرافی IP شما را مسدود می‌کند |
| ادعای پشتیبانی از تایم‌فریمی که صرافی ندارد | خطای زمان اجرا به‌جای تجمیع خودکار |
| برنگرداندن کندل‌ها به ترتیب صعودی | همه اندیکاتورها وارونه محاسبه می‌شوند |
| ثبت کلید API در لاگ | نشت اطلاعات محرمانه |

---

## سیاهه بررسی نهایی

- [ ] همه متدهای انتزاعی پیاده‌سازی شده‌اند
- [ ] `capabilities` واقعیت را می‌گوید
- [ ] کندل‌ها صعودی و بر حسب **ثانیه** هستند
- [ ] خطاهای صرافی به `ExchangeError` با `user_key` ترجمه شده‌اند
- [ ] محدودساز نرخ فعال است
- [ ] `close()` همه منابع را آزاد می‌کند
- [ ] هیچ کلید API در لاگ یا پیام خطا نیست
- [ ] در `register_builtin_providers()` ثبت شده است
- [ ] آزمون نگاشت نماد و دریافت کندل نوشته شده است
- [ ] `python main.py --check` با صرافی جدید سبز است

</div>
