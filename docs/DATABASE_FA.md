<div dir="rtl">

# پایگاه داده و مهاجرت‌ها

---

## کلیات

| مورد | مقدار |
|---|---|
| موتور | SQLite |
| لایه دسترسی | SQLAlchemy 2.x (سبک `Mapped` و `mapped_column`) |
| مهاجرت | Alembic |
| حالت نوشتن | WAL |
| نام فایل | `crypto_ai_trader.db` |

مسیر فایل:

</div>

```
%LOCALAPPDATA%\CryptoAITrader\crypto_ai_trader.db     ویندوز
~/.local/share/CryptoAITrader/crypto_ai_trader.db     لینوکس
```

<div dir="rtl">

برای تغییر مسیر، متغیر محیطی `CAT_DATA_DIR` را تنظیم کنید (در آزمون‌ها همین کار انجام می‌شود تا داده واقعی کاربر دست نخورد).

### چرا SQLite؟

برنامه تک‌کاربره و دسکتاپ است. SQLite نصب نمی‌خواهد، فایل پشتیبانش یک فایل است، و برای این حجم داده به‌اندازه کافی سریع است. حالت WAL هم اجازه می‌دهد رابط گرافیکی هم‌زمان با نوشتن داده بازار، بخواند.

---

## جدول‌ها (۱۳ جدول)

### تنظیمات و پیکربندی

</div>

```
settings                تنظیمات کاربر
├── key                 کلید یکتا، مثل "risk.max_leverage"
├── value               مقدار (متن؛ تبدیل نوع در لایه سرویس)
├── category            دسته برای گروه‌بندی در رابط کاربری
├── is_user_modified    ← ستون حیاتی، پایین توضیح داده شده
└── description
```

<div dir="rtl">

> 🔑 **`is_user_modified` مهم‌ترین ستون این جدول است.**
> وقتی کاربر مقداری را تغییر می‌دهد، این ستون `True` می‌شود. تابع `initialize_defaults()` هنگام اجرای بعدی برنامه یا پس از یک به‌روزرسانی، **فقط سطرهایی را دست می‌زند که `is_user_modified = False` باشند**. بدون این ستون، هر به‌روزرسانی تنظیمات کاربر را پاک می‌کرد.

</div>

```
exchange_providers      پیکربندی صرافی‌ها
├── name, display_name, rest_url, ws_url
├── enabled, has_credentials      ← فقط پرچم، خود کلید اینجا نیست
├── rate_limit_per_second, request_timeout
└── last_connected_at, last_error

ai_providers            پیکربندی ارائه‌دهنده‌های هوش مصنوعی
├── name, provider_type, base_url, model
├── temperature, max_tokens, timeout
├── priority                      ← ترتیب جایگزینی هنگام خطا
├── enabled, requires_api_key, has_credentials
└── last_used_at, last_error
```

<div dir="rtl">

> 🔒 **هیچ کلید API در پایگاه داده ذخیره نمی‌شود.** فقط پرچم `has_credentials` نگهداری می‌شود. خود کلیدها در Windows Credential Manager یا یک فایل رمزنگاری‌شده جداگانه هستند.

### داده بازار

</div>

```
symbols                 نمادهای هر صرافی
├── exchange, symbol, exchange_symbol
├── base_asset, quote_asset
├── price_precision, quantity_precision, min_order_amount
└── is_active, is_favorite

candles                 کندل‌های ذخیره‌شده (برای حالت آفلاین)
├── exchange, symbol, timeframe, open_time    ← کلید یکتای مرکب
└── open, high, low, close, volume

market_data             آخرین وضعیت هر نماد
└── last_price, high_24h, low_24h, volume_24h, change_percent

watchlists              فهرست‌های پیگیری
└── list_name, symbol_id, position, note

indicators              نتیجه‌های کش‌شده اندیکاتور
└── indicator, parameters, latest_values, interpretation, candle_time
```

<div dir="rtl">

جدول `candles` قلب **حالت آفلاین** است: وقتی شبکه قطع می‌شود، موتور بازار به‌جای خطا دادن، از این جدول می‌خواند.

### سیگنال‌ها

</div>

```
signals                 هر سیگنال تولیدشده
├── symbol, exchange, direction              LONG / SHORT / WAIT
├── entry_min, entry_max, stop_loss
├── take_profits                             JSON: [tp1, tp2, tp3]
├── risk_reward, leverage, confidence
├── trend, market_structure
├── timeframes, indicators_used              JSON
├── ai_provider, ai_model
├── reason, invalidation
├── status                                   OK / INSUFFICIENT_DATA / FAILED
├── source                                   engine / app / cli
└── created_at

signal_analysis         جزئیات سنگین، جدا از جدول اصلی
├── signal_id           →  signals.id
├── analysis_text                            متن تحلیل هوش مصنوعی
├── market_snapshot                          JSON: وضعیت بازار در لحظه سیگنال
├── risk_assessment                          JSON: خروجی موتور ریسک
├── ai_raw_response                          پاسخ خام مدل (برای عیب‌یابی)
└── data_timestamp
```

<div dir="rtl">

**چرا دو جدول؟** جدول `signals` سبک می‌ماند تا فهرست‌ها و گزارش‌ها سریع باشند؛ متن‌های بلند فقط وقتی خوانده می‌شوند که کاربر جزئیات یک سیگنال را باز کند.

> `market_snapshot` عمداً ذخیره می‌شود: بدون آن نمی‌توان بعداً فهمید سیگنال بر پایه چه داده‌ای ساخته شده بود.

### سامانه

</div>

```
backup_history          سابقه پشتیبان‌گیری
└── file_path, size_bytes, backup_type, status, note
    backup_type ∈ { manual, pre_migration, pre_restore }

reports                 سابقه گزارش‌های ساخته‌شده
└── title, report_type, export_format, file_path, row_count, filters

application_logs        رویدادهای مهم برنامه
└── level, logger_name, message, context
```

<div dir="rtl">

---

## کار با Alembic

### وضعیت فعلی

</div>

```bash
alembic current          # نسخه فعلی پایگاه داده
alembic history          # همه نسخه‌ها
alembic heads            # آخرین نسخه موجود
```

<div dir="rtl">

### اعمال مهاجرت

</div>

```bash
alembic upgrade head     # به آخرین نسخه
alembic downgrade -1     # یک نسخه به عقب
```

<div dir="rtl">

یا با اسکریپت آماده:

</div>

```bash
scripts/migrate.sh
```

<div dir="rtl">

### ساخت مهاجرت جدید

</div>

```bash
alembic revision --autogenerate -m "add funding_rate to candles"
```

<div dir="rtl">

> ⚠ **دام آزمایش‌شده:** `--autogenerate` باید روی یک پوشه داده **خالی** اجرا شود. اگر پایگاه داده موجود، ستون‌هایی داشته باشد که مدل‌ها ندارند، Alembic دستور حذف آن‌ها را تولید می‌کند.

</div>

```bash
CAT_DATA_DIR=$(mktemp -d) alembic revision --autogenerate -m "your message"
```

<div dir="rtl">

**همیشه فایل تولیدشده را بخوانید و اصلاح کنید.** خودکارسازی Alembic تغییر نام ستون را نمی‌فهمد و آن را «حذف ستون قدیمی + ساخت ستون جدید» می‌بیند، که یعنی از دست رفتن داده.

### پشتیبان خودکار پیش از مهاجرت

پیش از هر مهاجرت، `BackupManager.create_pre_migration()` یک نسخه پشتیبان می‌سازد. اگر هنوز پایگاه داده‌ای وجود نداشته باشد (اولین اجرا)، `None` برمی‌گرداند و مهاجرت را مسدود نمی‌کند.

---

## قاعده‌های همیشگی

### ۱. تنظیمات کاربر را بازنویسی نکنید

</div>

```python
# ✅ درست — فقط مقادیر دست‌نخورده
if not record.is_user_modified:
    record.value = new_default

# ❌ غلط — انتخاب کاربر را پاک می‌کند
record.value = new_default
```

<div dir="rtl">

### ۲. در مهاجرت‌ها ستون‌ها را با مقدار پیش‌فرض اضافه کنید

</div>

```python
# ✅ درست — سطرهای موجود مقدار می‌گیرند
op.add_column("signals", sa.Column("score", sa.Float(), nullable=False, server_default="0"))

# ❌ غلط — روی جدول پرداده شکست می‌خورد
op.add_column("signals", sa.Column("score", sa.Float(), nullable=False))
```

<div dir="rtl">

### ۳. `downgrade` را واقعاً بنویسید

مهاجرتی که راه برگشت ندارد، در صورت بروز مشکل شما را گیر می‌اندازد.

### ۴. همیشه از `session_scope` استفاده کنید

</div>

```python
with self._db.session_scope() as session:
    session.add(record)
    # commit خودکار در خروج موفق، rollback خودکار در خطا
```

<div dir="rtl">

---

## دسترسی از راه مخازن (Repository)

هیچ‌جای برنامه مستقیم با `Session` کار نمی‌کند؛ همه چیز از راه مخازن است:

| مخزن | کاربرد |
|---|---|
| `SettingsRepository` | خواندن و نوشتن تنظیمات |
| `SymbolRepository` | نمادها و فهرست پیگیری |
| `CandleRepository` | ذخیره و خواندن کندل (حالت آفلاین) |
| `SignalRepository` | ذخیره، جست‌وجو و آمار سیگنال‌ها |
| `ExchangeProviderRepository` | پیکربندی صرافی‌ها |
| `AIProviderRepository` | پیکربندی هوش مصنوعی |
| `BackupHistoryRepository` | سابقه پشتیبان‌گیری |
| `ReportRepository` | سابقه گزارش‌ها |

همه از `BaseRepository` ارث می‌برند که `add`, `get_by_id`, `list_all`, `count`, `delete_by_id` را می‌دهد.

</div>

```python
signals = application.signal_repository.search(
    symbol="BTC/USDT",
    direction="LONG",
    min_confidence=60,
    limit=50,
)
```

<div dir="rtl">

---

## پشتیبان‌گیری و بازیابی

### نکته WAL

در حالت WAL، داده تازه ممکن است هنوز در فایل اصلی `.db` نباشد بلکه در `-wal` باشد. پس پیش از کپی گرفتن، باید checkpoint اجرا شود:

</div>

```python
session.execute(text("PRAGMA wal_checkpoint(FULL)"))
```

<div dir="rtl">

و هنگام بازیابی، فایل‌های جانبی `-wal` و `-shm` قدیمی باید حذف شوند، وگرنه SQLite داده جدید را با ژورنال قدیمی ترکیب می‌کند و نتیجه خراب می‌شود. هر دو مورد در `BackupManager` پیاده‌سازی شده‌اند — **آن‌ها را حذف نکنید.**

### محتوای فایل پشتیبان

</div>

```
backup_20260908_134512.zip
├── manifest.json            نسخه برنامه، زمان، جمع کنترلی SHA-256
├── crypto_ai_trader.db      پایگاه داده
└── settings.json            نسخه خوانا از تنظیمات
```

<div dir="rtl">

**فایل رمزهای محرمانه هرگز داخل پشتیبان نمی‌رود** (آزمون خودکار دارد). یعنی پس از بازیابی روی دستگاه دیگر، باید کلیدهای API را دوباره وارد کنید — که رفتار درست و امنی است.

---

## عیب‌یابی

| نشانه | علت و راه‌حل |
|---|---|
| `database is locked` | چند فرایند هم‌زمان. مطمئن شوید فقط یک نمونه برنامه باز است |
| `no such column` | مهاجرت اجرا نشده: `alembic upgrade head` |
| `Can't locate revision` | فایل مهاجرت گم شده. از پشتیبان بازیابی کنید |
| پایگاه داده خیلی بزرگ شده | جدول `candles` انباشته شده؛ کندل‌های قدیمی را پاک کنید |
| تنظیمات بازنشانی شده | `is_user_modified` در جایی نادیده گرفته شده — این یک اشکال است |

بررسی سلامت فایل:

</div>

```bash
sqlite3 ~/.local/share/CryptoAITrader/crypto_ai_trader.db "PRAGMA integrity_check;"
```

<div dir="rtl">

</div>


---

## جدول‌های نسخهٔ ۱٫۵ (مهاجرت `ce3e52be9145`)

مهاجرت **فقط افزایشی** است: هیچ جدول یا ستونی حذف یا تغییر نکرده، پس
پایگاه دادهٔ نسخهٔ ۱٫۴ بدون از دست رفتن داده ارتقا می‌یابد.

### `users`
شناسه، `username` (یکتا)، `email`، `display_name`، `password_hash`،
`password_salt`، `password_iterations`، `password_algorithm`، `is_active`،
`is_admin`، `preferences` (JSON)، `last_login_at`، `failed_attempts`،
`locked_until`.

رابطه‌ها: `user_sessions` و `exchange_accounts` با حذف آبشاری.

### `user_sessions`
`user_id` (FK آبشاری)، `token_hash` (یکتا — **خود توکن ذخیره نمی‌شود**)،
`device_label`، `created_at`، `last_seen_at`، `expires_at`، `revoked`.

### `exchange_accounts`
`user_id` (FK آبشاری)، `exchange`، `label`، **`secret_ref`** (کلید جستجو
در Secret Store، نه خود رمز)، `api_key_masked`، `is_default`، `enabled`،
`read_only` (پیش‌فرض `True`)، `status`، `last_sync_at`، `last_error`،
`balances` (JSON)، `total_value_usdt`، `permissions`، `extra_config`.

قید یکتایی `(user_id, exchange, label)` و نمایهٔ `(user_id, exchange)`.

> این جدول **هیچ ستون رمزی ندارد**. کلید و رمز API رمزنگاری‌شده در Secret
> Store نگه‌داری می‌شوند.

### `paper_trades`
`user_id`/`account_id`/`signal_id` (FK)، `symbol`، `side`، `status`،
**`mode`** (پیش‌فرض `'paper'`)، `quantity`، `entry_price`، `exit_price`،
`stop_loss`، `take_profit`، `leverage`، `fee`، `pnl`، `pnl_percent`،
`opened_at`، `closed_at`، `note`، `extra`. نمایهٔ `(user_id, opened_at)`.

ستون `mode` از همین حالا هست تا روشن‌کردن سفارش‌گذاری واقعی در آینده
نیازی به مهاجرت تازه نداشته باشد.
