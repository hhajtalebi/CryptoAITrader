> **به‌روزرسانی 2.3.0:** [گزارش مرحله](RELEASE_2.3.0_FA.md) بر وضعیت زیر مقدم است؛ بخش feed/tick/trading از R6 و دامنهٔ پویش از R10 اصلاح شده‌اند، نه تمام آن دو موضوع. R4/R5/R7/R8/R9 همچنان بازند. نتایج تست پایین تاریخی‌اند.

> **وضعیت پس از بررسی:** R1/R2/R3 در نسخهٔ 2.2.2 اصلاح شدند؛ [گزارش رفع‌ها](RELEASE_2.2.2_FA.md). متن و نمونه‌های زیر گزارش تاریخی مبنای 2.2.0/2.2.1 هستند و دیگر نباید انتظار شکست آن سه نمونه را در نسخهٔ جدید داشت. R4 تا R10 همچنان بررسی تکمیلی می‌خواهند.

# گزارش بررسی اولیه، آزمون‌ها و موارد باز

تاریخ: **۲۰۲۶-۰۹-۲۳** · مبنا: **2.2.0 / a66e61a** · تحویل: **2.2.1**

## اصالت ZIP اولیه

نسخهٔ اولیه پیش از هر تغییر ساخته شد:

- نام: `CryptoAITrader-v2.2.0-original-a66e61a.zip`
- تعداد فایل: **۴۸۲**؛ شامل تمام فایل‌های trackشده، از جمله `.env.example`، فونت‌ها و ZIP قدیمی داخل `release/`.
- اندازه: **3,973,369 بایت**.
- SHA-256:

```text
78b360c121be2194a161c4ef3b6e557242947eb2cb350844baf01b1c850a9d71
```

ZIP با `ZipFile.testzip()` بررسی شد و SHA-256 هر فایل داخل آن با checkout اولیه تطبیق داده شد. `original-manifest.json` بیرون مخزن فهرست و هش کامل هر فایل را دارد. `.git`/تاریخچهٔ گیت در بسته نیست. فایل‌های BAT مطابق checkout با CRLF هستند؛ بنابراین با ZIP تولیدشدهٔ مستقیم از blobهای Git ممکن است پایان خط متفاوت باشد، نه منطق کد. هیچ LFS pointer یا submodule در مبنا وجود نداشت. HEAD محلی با `gh api repos/hhajtalebi/CryptoAITrader/commits/main --jq .sha` برابر بود؛ هیچ نیاز به clone مجدد یا تغییر شاخه نبود.

این تحویل **سورس پروژه** است، نه EXE یا APK ساخته‌شده و نه نسخهٔ داده/حساب‌های شخصی کاربر.

## روش بررسی

1. فهرست تمام فایل‌های trackشده، بایت‌ها و هش‌ها.
2. decode تمام فایل‌های متنی؛ AST تمام ۳۴۷ فایل Python (۱۰۶٬۲۸۹ خط) و parse تمام JSONها.
3. نمایه‌سازی ۷۳۹ تعریف کلاس و ۵۵۰۲ تعریف تابع/متد با احتساب تعریف‌های تو در تو؛ ۶۵۹ کلاس در سطح مستقیم ماژول است. نمایهٔ حدود ۹۵۰۰خطی در CODE_MAP برای جست‌وجوی ادامهٔ کار است، نه ادعای خواندن دستی همهٔ بدنه‌ها.
4. بررسی دستی هدفمند مسیرهای حساس و نقاط اتصال در Application/Controller/Market/Signal/Prediction/Trading/DB/Security/Build.
5. آزمون‌های موجود قابل اجرا و سه آزمایش ایزولهٔ یافته‌ها با دادهٔ ساختگی.

## محیط و نتیجهٔ آزمون

- Linux، Python **3.11.2**؛ وابستگی‌ها از `requirements.txt` در `.venv` نصب شدند، بدون تغییر requirements.
- نسخه‌های مهم نصب‌شده: PySide6 6.11.2، numpy 2.4.6، pandas 2.3.3، SQLAlchemy 2.0.54، pytest 9.1.1، pytest-asyncio 1.4.0. محدوده‌های نسخه در پروژه بازه‌ای‌اند؛ این‌ها pin جدید پروژه نیستند.
- مسیر دادهٔ آزمایش با `CAT_DATA_DIR` خارج از سورس انتخاب شد؛ fixtureها نیز DB موقت می‌سازند. کلید/پول/حساب واقعی استفاده نشد.

### اجرای کامل: مسدود به علت محیط

```bash
QT_QPA_PLATFORM=offscreen CAT_DATA_DIR=<temporary-directory> \
  .venv/bin/python -m pytest tests -q -ra
```

نتیجه: **۳۰ خطا در جمع‌آوری** به دلیل `ImportError: libGL.so.1`؛ بررسی `ldd` نبودن `libEGL.so.1`، `libxkbcommon.so.0` و `libdbus-1.so.3` را هم نشان داد. نصب کتابخانه‌های سیستم با apt به علت شکست دسترسی شبکه به Debian موفق نشد. حالت offscreen به‌تنهایی نبود کتابخانهٔ shared را حل نمی‌کند.

این نتیجه شکست منطق آن ۳۰ فایل تست محسوب نمی‌شود؛ آن‌ها اجرا نشده‌اند. آزمون GUI، تصویری و نصب ویندوز در این مرحله **تأیید نشده‌اند**.

### اجرای زیرمجموعهٔ بدون UI

از ۸۴ فایل تست، ۳۳ فایل که در AST هیچ import مستقیم از PySide6 یا ui نداشتند انتخاب شدند؛ ۵۱ فایل دیگر در این اجرای جایگزین شرکت نکردند، حتی اگر بعضی تست‌های داخلشان مستقل از GUI باشند.

نتیجهٔ مبنا از JUnit: **۶۷۶ مورد = ۶۷۴ پاس + ۲ skip؛ ۰ شکست، ۰ خطا؛ ۱۸٫۶۳۵ ثانیه**.

Skipها در `test_predictive_phase2_5.py` برای LightGBM و PyTorch نصب‌نشده‌اند. گروه `ml` اختیاری است؛ موفقیت مدل‌های اختیاری ادعا نمی‌شود.

بازاجرای همین ۳۳ فایل پس از افزایش نسخه و افزودن مستندات در **2.2.1** نیز
**۶۷۴ پاس + ۲ skip، بدون خطا/شکست در ۱۷٫۶۹ ثانیه** داشت
(`final-core-tests.log/xml`). بررسی syntax همهٔ ۳۴۷ فایل Python و parse JSONها
نیز انجام شد؛ تغییر Python محصول فقط رشتهٔ APP_VERSION است.

گزارش‌های خام تحویل بیرون مخزن: `baseline-tests.log/xml`، `core-tests.log/xml` و `test-selection.json`. عدد **۲۲۶۹ پاس + ۱ skip** در مستندات قدیمی، نتیجهٔ تاریخی نویسندهٔ آن‌هاست، نه اجرای این جلسه.

## یافته‌های بازتولیدشده — اصلاح نشده

### R1 — خطای گزارش پیش‌بینی با تایم‌فریم‌های متفاوت

- محل: `signals/prediction/engine.py::PredictiveIntelligenceEngine.assess`، خط ۵۵۲ مبنا.
- شرط: یک نماد قبلاً گزارش دارد؛ بار دوم با tuple تایم‌فریم تازه فراخوانی می‌شود، بنابراین `_latest_for_symbol` موجود ولی `_report_cache` برای کلید جدید None است.
- کد `if latest is None or time.monotonic() - cached[0] >= 0 or True` پیش از رسیدن به `or True`، `cached[0]` را روی None می‌خواند.
- بازتولید: دادهٔ ساختگی از helper آزمون lifecycle؛ یک بار `('15m', '1h')` و سپس `('15m',)`؛ اولی گزارش دارد و دومی `TypeError: 'NoneType' object is not subscriptable` می‌دهد.
- اثر محتمل: مصرف گزارش یک نماد توسط صفحهٔ پیش‌بینی و ترمینال با تایم‌فریم‌های مختلف.
- اقدام پیشنهادی: تست regression دقیق و اصلاح کوچک cache؛ **این مرحله تغییر نداد**.

### R2 — تنظیم‌های جدید معامله به AutoTradeConfig منتقل نمی‌شوند

- محل: `trading/scalp_service.py::ScalpService.build_trader_config` و فراخوان `MainController._auto_trade_config`.
- مشاهده: سازنده فقط فیلدهای قدیمی (margin/target/loss/leverage/…/fee) را انتقال می‌دهد؛ فیلدهای جدید در AutoTradeConfig پیش‌فرض می‌مانند.
- بازتولید با Settings ساختگی و مقدارهای صریح:

| تنظیم ذخیره‌شده | ورودی | config خروجی |
|---|---|---|
| scalp.engine_mode | selected | scan |
| scalp.selected_symbols | BTC/USDT | رشتهٔ خالی |
| scalp.max_spread_percent | 0.05 | 0.25 |
| scalp.trailing_enabled | true | false |
| scalp.max_total_margin_percent | 20 | 60 |

بعضی مسیرهای کنترلر تنظیم را مستقیم می‌خوانند، پس این یافته به‌معنی بی‌اثر بودن همهٔ رفتار selected/AI در همه‌جا نیست؛ **ناهماهنگی UI/تنظیم ذخیره‌شده/config موتور** اثبات شده است. برای پارامترهای ریسک اولویت بالا دارد. قبل از فعال‌سازی معاملهٔ واقعی باید تمام فیلدها تا موتور و `apply_config` تست end-to-end شوند.

### R3 — پشتیبان شامل رکورد راز رمزنگاری‌شده است اما خلاف آن برچسب می‌خورد

- محل: `Application.__init__`، `app/security/db_backend.py`، `BackupManager.create/_snapshot_database`.
- پیش‌فرض برنامه DatabaseBackend را فعال می‌کند؛ کل نگاشت رازها به‌صورت ciphertext در `settings[security.encrypted_secrets]` است.
- BackupManager snapshot کل DB را می‌گیرد و آن ردیف را حذف نمی‌کند؛ manifest همچنان `contains_secrets: false` دارد.
- بازتولید: فقط کلید آزمایشی با مقدار ساختگی در DB موقت؛ پس از باز کردن snapshot، وجود ردیف True و مقدار contains_secrets برابر False بود.
- **این آزمایش افشای کلید واقعی یا ذخیرهٔ plaintext را نشان نمی‌دهد**؛ نشان می‌دهد ادعای «backup فاقد secrets» نادرست است. فایل backup واقعی را عمومی نکنید.
- اقدام پیشنهادی: توافق دربارهٔ سیاست حذف/حفظ secrets رمزنگاری‌شده، تصحیح manifest و آزمون migration/restore؛ بدون دست زدن به کلیدهای کاربر.

## مشاهدات کد که بررسی تکمیلی می‌خواهند

این موارد نه رفع شده‌اند و نه در این مرحله همهٔ سناریوهایشان آزمایش شده است:

- **R4 — امنیت انبار راز:** کلید Fernet از نام کاربر/host/مسیر مشتق می‌شود؛ این مشخصات راز قوی نیستند. بهبود باید با طرح انتقال امن رازهای موجود انجام شود، نه تعویض ناگهانی کلید و از دست دادن credentialها.
- **R5 — checksum به‌روزرسان:** `verify_checksum()` اگر expected خالی باشد True می‌دهد. هیچ نصب‌کننده‌ای در این بررسی دانلود/اجرا نشد. سیاست fail-closed و اعتماد به manifest باید جدا تصمیم‌گیری و تست شود.
- **R6 — تعویض صرافی و وابستگی‌های قدیمی:** switch_exchange موتور بازار/سیگنال و prediction را عوض می‌کند، ولی تمام `_chat_agent/_autonomous_agent/_ai_toolset` و LivePriceFeed/TickEngine/listenerهای کنترلر را بازسازی نمی‌کند. کنترلر بعد از سوئیچ صرفاً فهرست/قیمت‌های UI را پاک و refresh می‌کند. سناریوی «تغییر صرافی بعد از ساخت agent و شروع خوراک» باید با fake provider تست شود.
- **R7 — زمان/هویت در پیش‌بینی:** lookup فعلی از timestamp کندل 1h و صرافی فعلی استفاده می‌کند؛ باید شروع/پایان کندل، کهنگی، افق دقیقه‌ای و صرافی مبدأ رکورد تفکیک شوند. `last_price` گزارش با max آخرین close تایم‌فریم‌ها انتخاب می‌شود، نه تازه‌ترین timestamp. کش آنسامبل steps/افق را در کلید ندارد. این‌ها برای ارزیابی آماری دقیق نیازمند تست عددی‌اند؛ ادعای دقت اثبات‌شده صرفاً از وجود جدول ممکن نیست.
- **R8 — تنظیمات قدیمی:** `_repair_stale_defaults()` مقدار ۴۵ را به ۱۲۰ تبدیل می‌کند، بدون خواندن user_modified. ممکن است مقدار صریح همان عدد نیز تغییر کند؛ هنگام توسعه قاعدهٔ حفظ ترجیح کاربر رعایت شود.
- **R9 — بسته‌بندی:** فهرست packages در pyproject دستی است و main/trading/subpackageها نیاز به بررسی wheel تمیز دارند. build موبایل به assets اشاره دارد که در این checkout زیر `mobile/assets` نیستند؛ APK ساخته و تأیید نشده است.
- **R10 — دامنهٔ پویش ترمینال:** `_ai_candidate_scan()` از selected/watchlist استفاده می‌کند؛ ادعای «تمام بازار» یا مستقل بودن کامل آستانه‌های watch از آستانه‌های ورود باید با کد واقعی تطبیق داده شود. `ai_decide` پیش از تولید ردیف watch برخی نامزدها را رد می‌کند.

## تفاوت مستندات قدیمی با کد مبنا

| موضوع | توضیح قدیمی | مشاهده از کد |
|---|---|---|
| استراتژی | ۳ | ۵ کلاس ثبت‌شده |
| تایم‌فریم | ۱۳ تا هفتگی | ۱۴ کد با 1M؛ افق پیش‌بینی جداگانه ۱۳ مورد |
| مسیر داده | LOCALAPPDATA / ~/.local/share | پوشهٔ data کنار سورس/EXE، مگر CAT_DATA_DIR |
| AI | فقط روایت و هیچ تغییر قیمت | ai_only و مسیر عامل GUI می‌توانند تصمیم/سطوح بدهند |
| اسرار | هرگز داخل SQLite | پیش‌فرض DatabaseBackend رمزنگاری‌شده |
| پشتیبان | بدون کلید | ciphertext داخل DB snapshot باقی می‌ماند |
| نقطهٔ ترکیب | فقط Application | کنترلر نیز feed/tick/trader را می‌سازد |
| جدول‌های DB | برخی docs: ۱۳ | ۲۲ جدول در Base.metadata |
| تنظیمات | برخی docs: ۱۴۲ | ۱۶۴ پیش‌فرض در DEFAULT_SETTINGS |
| نسخهٔ موبایل | گاهی هم‌نسخه تلقی شده | مستقل و برابر 1.9.12 |

این مرحله در READMEها هشدار و پیوند به گزارش جدید اضافه می‌کند؛ تاریخچهٔ قدیمی و ادعاهای آن بازنویسی سراسری نشده‌اند تا منشأ نسخهٔ مبنا از بین نرود.

## حدود تحویل 2.2.1

افزوده‌ها: قواعد توسعه (`AGENTS.md`)، حافظهٔ پروژه، نمایهٔ کامل کد و این گزارش. فایل‌های معرفی/تحویل/تاریخچه و شمارهٔ نسخه همگام شدند. تنها تغییر Python محصول مقدار `APP_VERSION` است. پایگاه داده، منطق سیگنال/ریسک/AI/معامله، ترجمه‌ها، UI و تست‌های موجود دست‌نخورده‌اند. ZIP جدید سورس همراه فایل‌های جدید است و شامل محیط مجازی/کش/دادهٔ آزمون نیست. ZIP تاریخی `release/CryptoAITrader-v2.2.0-2026-09-23.zip` به‌عنوان فایل از پیش موجود نگه داشته شده و انتشار جدیدی در GitHub ساخته نشده است.

**گام بعد منوط به انتخاب و تأیید کاربر است؛ commit/push هنوز مجاز نشده است.**

## بازاجرای دقیق زیرمجموعهٔ هسته

پس از نصب requirements و فعال‌سازی محیط مجازی؛ مسیر داده باید موقت باشد:

```bash
export QT_QPA_PLATFORM=offscreen
export CAT_DATA_DIR="$(mktemp -d)"
python -m pytest -o addopts='' -q -ra \
  tests/test_ai_providers.py \
  tests/test_ai_validator.py \
  tests/test_auth.py \
  tests/test_autonomous_agent.py \
  tests/test_backup.py \
  tests/test_chat_agent.py \
  tests/test_chat_repository.py \
  tests/test_indicators.py \
  tests/test_localization.py \
  tests/test_market_resilience.py \
  tests/test_narrative.py \
  tests/test_paper_trader.py \
  tests/test_persian_pdf.py \
  tests/test_prediction_lifecycle.py \
  tests/test_predictive_phase1.py \
  tests/test_predictive_phase2_5.py \
  tests/test_reports.py \
  tests/test_risk_engine.py \
  tests/test_signal_engine.py \
  tests/test_timeframes.py \
  tests/test_toobit_bitpin_providers.py \
  tests/test_trades_and_wallet.py \
  tests/test_v154_packaging.py \
  tests/test_v154_security_money.py \
  tests/test_v162_toobit_websocket.py \
  tests/test_v190_account_and_auto_scan.py \
  tests/test_v1910_ollama_doctor.py \
  tests/test_v1911_ai_signal_mode.py \
  tests/test_v1911_build_and_update.py \
  tests/test_v1912_mobile.py \
  tests/test_v1914_scalp.py \
  tests/test_v1917_trust_and_trades.py \
  tests/test_v1922_micro_speed.py
```

## نمونهٔ بازتولید R1 و R2 بدون شبکه

از ریشهٔ پروژه با Python محیط مجازی اجرا شود. کندل‌ها فقط دادهٔ تست هستند:

```python
import asyncio
from types import SimpleNamespace
from tests.test_prediction_lifecycle import make_candles
from signals.prediction.engine import PredictiveIntelligenceEngine
from trading.scalp_service import ScalpService

async def prediction_probe():
    data = {
        "15m": make_candles(300, seed=5, step=900),
        "1h": make_candles(300, seed=6, step=3600),
    }
    engine = PredictiveIntelligenceEngine(
        lambda symbol, timeframe, limit=600: data.get(timeframe, []),
        include_dl=False,
    )
    assert await engine.assess("REVIEW/USDT", timeframes=("15m", "1h"))
    # در مبنا و تحویل مستندات 2.2.1 این خط TypeError می‌دهد:
    await engine.assess("REVIEW/USDT", timeframes=("15m",))

class Settings:
    def get(self, key, default=None):
        return {
            "scalp.engine_mode": "selected",
            "scalp.selected_symbols": "BTC/USDT",
            "scalp.max_spread_percent": 0.05,
            "scalp.trailing_enabled": True,
            "scalp.max_total_margin_percent": 20,
        }.get(key, default)

config = ScalpService(SimpleNamespace(settings=Settings())).build_trader_config()
print(config.engine_mode, config.max_spread_percent,
      config.trailing_enabled, config.max_total_margin_percent)
# مبنا: scan 0.25 False 60.0
asyncio.run(prediction_probe())
```

## نمونهٔ بازتولید R3 بدون راز واقعی

فقط DB موقت و مقدار ساختگی؛ هیچ credential واقعی وارد نشود:

```python
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from app.core.paths import AppPaths
from app.database.session import DatabaseManager
from app.database.repositories.settings_repository import SettingsRepository
from app.security.db_backend import DatabaseBackend, SECRETS_SETTING_KEY
from backup.manager import BackupManager

with tempfile.TemporaryDirectory() as directory:
    paths = AppPaths(Path(directory)).ensure()
    db = DatabaseManager(paths.database_url)
    try:
        db.create_all()
        backend = DatabaseBackend(SettingsRepository(db))
        backend.set("audit_dummy", "not-a-real-secret")
        backup = BackupManager(paths).create(note="synthetic review probe")
        manifest = BackupManager.read_manifest(backup.path)
        with zipfile.ZipFile(backup.path) as archive:
            entry = next(name for name in archive.namelist() if name.endswith(".db"))
            snapshot = Path(directory) / "inspection.db"
            snapshot.write_bytes(archive.read(entry))
        with sqlite3.connect(snapshot) as connection:
            count = connection.execute(
                "SELECT count(*) FROM settings WHERE key=?", (SECRETS_SETTING_KEY,)
            ).fetchone()[0]
        print(bool(count), manifest["contains_secrets"])
        # مبنا: True False
    finally:
        db.dispose()
```
