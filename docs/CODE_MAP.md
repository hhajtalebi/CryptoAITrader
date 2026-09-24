> **مکمل 2.2.2:** نمایهٔ زیر برای مبنای 2.2.0 ثابت نگه داشته شده است. تغییرهای جاری در `signals/prediction/engine.py`، `trading/scalp_service.py`، `trading/auto_trader.py` و `backup/manager.py` هستند. افزوده‌ها: `tests/test_v222_review_fixes.py`، `tests/test_v222_config_ui.py`، `tests/test_download_server.py`، `tools/serve_downloads.py` و `tools/download_page.html`. شمارهٔ خطوط مبنا برای فایل‌های تغییرکرده معتبر نیست؛ [گزارش جاری](RELEASE_2.2.2_FA.md) را بخوانید.

# نمایهٔ ایستای تمام فایل‌ها و نمادهای پروژه

مبنای این نمایه: `2.2.0` / `a66e61a2d45721aff46d1d08a804012e3c907084`، بررسی ۲۰۲۶-۰۹-۲۳؛ همراه تحویل مستندات 2.2.1.

این نمایه با خواندن همهٔ فایل‌های trackشده، AST پایتون و JSON ساخته شده است. شرح کوتاه فایل‌ها از docstring/عنوان خودشان استخراج شده و ممکن است قدیمی باشد؛ حقیقت رفتاری و یافته‌های بررسی در [PROJECT_MEMORY_FA.md](PROJECT_MEMORY_FA.md) و [REVIEW_VALIDATION_FA.md](REVIEW_VALIDATION_FA.md) آمده است.

**محدودیت:** این فهرست call graph کامل اجرا نیست. importهای شرطی نیز شمرده شده‌اند؛ dynamic import، reflection، registry، تزریق وابستگی و callbackها ممکن است اتصال‌های دیگری بسازند. شمارهٔ خط‌ها برای نسخهٔ مبنا هستند؛ پس از تغییر کد، نام نماد را جست‌وجو و بدنه را دوباره بخوان.

## موجودی مبنا

| ناحیه | فایل | بایت | خطوط متن UTF-8 |
|---|---:|---:|---:|
| (root) | 16 | 382149 | 5722 |
| ai | 34 | 405392 | 8804 |
| app | 42 | 449120 | 10181 |
| assets | 8 | 542288 | 35 |
| backup | 2 | 18241 | 410 |
| docs | 31 | 304611 | 5900 |
| indicators | 9 | 86873 | 1985 |
| installer | 1 | 3263 | 68 |
| localization | 62 | 232164 | 3852 |
| market | 31 | 300356 | 6981 |
| migrations | 11 | 43106 | 937 |
| mobile | 7 | 31738 | 847 |
| release | 4 | 2031822 | 132 |
| reports | 4 | 39023 | 942 |
| scripts | 8 | 12121 | 328 |
| signals | 48 | 417834 | 10046 |
| tests | 86 | 1214722 | 29481 |
| tools | 7 | 51731 | 1356 |
| trading | 11 | 138996 | 3301 |
| ui | 60 | 1344297 | 30855 |

مجموع: **482 فایل**، **122,163 خط متن**؛ 347 ماژول پایتون. فونت/ZIP دودویی از نظر نام/اندازه/هش ثبت شده‌اند، نه تحلیل معنایی یا اجرای باینری.

## موجودی کامل فایل‌ها

هش‌ها متعلق به محتوای checkout اولیه‌اند؛ فایل‌های `.bat` در checkout پایان خط CRLF دارند، ولی blob گیت LF است. SHA-256 کوتاه فقط برای مرور است؛ هش کامل در `original-manifest.json` همراه تحویل اولیه قرار دارد.

| فایل | بایت | SHA-256 (ابتدای هش) |
|---|---:|---|
| [.env.example](../.env.example) | 1753 | `b6b219614ca3f672` |
| [.gitattributes](../.gitattributes) | 2046 | `b4bd0e4c4dfba162` |
| [.gitignore](../.gitignore) | 644 | `0a24a803019c7b5c` |
| [ADVANCED_FEATURES_FA.md](../ADVANCED_FEATURES_FA.md) | 6148 | `caa899f0e8771bf7` |
| [AI_HANDOVER.md](../AI_HANDOVER.md) | 25713 | `d826ca216fbf560c` |
| [BUILD_INFO.txt](../BUILD_INFO.txt) | 92084 | `974ffa0b4910e936` |
| [CryptoAITrader.spec](../CryptoAITrader.spec) | 4794 | `a61b77d371a5ef59` |
| [NEXT_TASK.md](../NEXT_TASK.md) | 6230 | `a7f9843419f2708d` |
| [PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md) | 206185 | `460b5350da2c801f` |
| [README.md](../README.md) | 14262 | `c34bf15b4e5274b3` |
| [README_EN.md](../README_EN.md) | 9059 | `55a9989d47b7bb57` |
| [RUN_WINDOWS.bat](../RUN_WINDOWS.bat) | 1807 | `7d99b756e3ef90bf` |
| [ai/__init__.py](../ai/__init__.py) | 425 | `0aeb6435f3e914ff` |
| [ai/agent/__init__.py](../ai/agent/__init__.py) | 870 | `6b599b1f559ac33c` |
| [ai/agent/analyst.py](../ai/agent/analyst.py) | 25480 | `91d52a95f45dcd72` |
| [ai/agent/autonomous_agent.py](../ai/agent/autonomous_agent.py) | 45304 | `02eb88d76d67f3cf` |
| [ai/agent/chat_agent.py](../ai/agent/chat_agent.py) | 31025 | `5664d893c18a3a3c` |
| [ai/agent/narrative.py](../ai/agent/narrative.py) | 18140 | `9b15339f0404e3c9` |
| [ai/agent/reviewer.py](../ai/agent/reviewer.py) | 12887 | `a4413c1be4664e21` |
| [ai/agent/stream_extractor.py](../ai/agent/stream_extractor.py) | 8590 | `a6970db1061f1bbc` |
| [ai/agent/validator.py](../ai/agent/validator.py) | 14460 | `aa06233ee5940a38` |
| [ai/local_model_fit.py](../ai/local_model_fit.py) | 8757 | `5e7c7a7c8104aee0` |
| [ai/ollama_doctor.py](../ai/ollama_doctor.py) | 8160 | `a6be3916c7797c8e` |
| [ai/prompt_budget.py](../ai/prompt_budget.py) | 17225 | `9d84df9597e7dd2d` |
| [ai/prompts/__init__.py](../ai/prompts/__init__.py) | 473 | `25a10e037661374b` |
| [ai/prompts/prompt_manager.py](../ai/prompts/prompt_manager.py) | 5606 | `1b2af6029a1a5181` |
| [ai/prompts/templates/futures_signal_v1.txt](../ai/prompts/templates/futures_signal_v1.txt) | 2071 | `42e221cfb5782220` |
| [ai/prompts/templates/market_structure_v1.txt](../ai/prompts/templates/market_structure_v1.txt) | 681 | `e7c7fb28673a7d74` |
| [ai/prompts/templates/risk_analysis_v1.txt](../ai/prompts/templates/risk_analysis_v1.txt) | 779 | `5db8b329c06b6484` |
| [ai/prompts/templates/signal_review_v1.txt](../ai/prompts/templates/signal_review_v1.txt) | 3106 | `a665f0e96c84540d` |
| [ai/prompts/templates/technical_analysis_v1.txt](../ai/prompts/templates/technical_analysis_v1.txt) | 2429 | `11a3bd22b8fe3f67` |
| [ai/providers/__init__.py](../ai/providers/__init__.py) | 1134 | `a9185217bcc90f4e` |
| [ai/providers/base.py](../ai/providers/base.py) | 6517 | `97a3164b28b6634d` |
| [ai/providers/catalog.py](../ai/providers/catalog.py) | 12647 | `aafab38f263a965d` |
| [ai/providers/free_models.py](../ai/providers/free_models.py) | 8677 | `3de319a9af8a9b28` |
| [ai/providers/manager.py](../ai/providers/manager.py) | 16139 | `5edf4fd7a1796a43` |
| [ai/providers/ollama_provider.py](../ai/providers/ollama_provider.py) | 53498 | `d5bcb387d33d6dba` |
| [ai/providers/omniroute_provider.py](../ai/providers/omniroute_provider.py) | 11199 | `93436afee72ef525` |
| [ai/providers/openai_compatible.py](../ai/providers/openai_compatible.py) | 25599 | `661121f53cd59b35` |
| [ai/providers/ranking.py](../ai/providers/ranking.py) | 6291 | `189972dc2d7eb02d` |
| [ai/recommendation.py](../ai/recommendation.py) | 6634 | `fdd50c0205548cd4` |
| [ai/speed_profile.py](../ai/speed_profile.py) | 3076 | `119fc3f35a04f283` |
| [ai/tools/__init__.py](../ai/tools/__init__.py) | 1149 | `d36871baf171e642` |
| [ai/tools/composite.py](../ai/tools/composite.py) | 6837 | `f42b44de4c6e9960` |
| [ai/tools/market_tools.py](../ai/tools/market_tools.py) | 30063 | `8b07d7005e2334fa` |
| [ai/tools/omniroute_tools.py](../ai/tools/omniroute_tools.py) | 9464 | `62c5589edf6fb471` |
| [alembic.ini](../alembic.ini) | 840 | `425d023abfa7e749` |
| [app/__init__.py](../app/__init__.py) | 479 | `c63e200846d6ccc3` |
| [app/application.py](../app/application.py) | 61291 | `f15e15d4ccb1b27b` |
| [app/config/__init__.py](../app/config/__init__.py) | 868 | `12a01ea8c4554bbe` |
| [app/config/defaults.py](../app/config/defaults.py) | 32270 | `806e9a23665a39e2` |
| [app/config/settings.py](../app/config/settings.py) | 4487 | `6e84446f7f1cb838` |
| [app/config/settings_service.py](../app/config/settings_service.py) | 12602 | `aa01ebdb3afc00b2` |
| [app/core/__init__.py](../app/core/__init__.py) | 408 | `148885d3c01b2752` |
| [app/core/auth_service.py](../app/core/auth_service.py) | 14448 | `81e5fb5c8adcce6e` |
| [app/core/constants.py](../app/core/constants.py) | 4633 | `631b708d8ba84d1f` |
| [app/core/email_service.py](../app/core/email_service.py) | 10912 | `8e6c9f409cba725a` |
| [app/core/events.py](../app/core/events.py) | 4921 | `642801dd6c27fdaa` |
| [app/core/exchange_account_service.py](../app/core/exchange_account_service.py) | 15180 | `3f5933e71f1100d6` |
| [app/core/models.py](../app/core/models.py) | 16221 | `477081373cd7b8f8` |
| [app/core/password_reset.py](../app/core/password_reset.py) | 11372 | `b23ff5d176931f57` |
| [app/core/paths.py](../app/core/paths.py) | 4372 | `203d41ac50fd55b6` |
| [app/core/timeutil.py](../app/core/timeutil.py) | 5295 | `8682fe8a2aced3a5` |
| [app/core/updater.py](../app/core/updater.py) | 9288 | `02080c29de1d46c5` |
| [app/database/__init__.py](../app/database/__init__.py) | 1316 | `4c9900b66417ceae` |
| [app/database/models.py](../app/database/models.py) | 41241 | `ff3c7a985c602052` |
| [app/database/repositories/__init__.py](../app/database/repositories/__init__.py) | 2060 | `3fc2ed69436c8ff5` |
| [app/database/repositories/base.py](../app/database/repositories/base.py) | 2972 | `626aa19d342a733b` |
| [app/database/repositories/candle_repository.py](../app/database/repositories/candle_repository.py) | 7562 | `dfb2b1bdc9cf17a7` |
| [app/database/repositories/chat_repository.py](../app/database/repositories/chat_repository.py) | 10005 | `ba7b19bf21baf19e` |
| [app/database/repositories/outcome_repository.py](../app/database/repositories/outcome_repository.py) | 14243 | `77ec5d6c7d496800` |
| [app/database/repositories/prediction_repository.py](../app/database/repositories/prediction_repository.py) | 5758 | `d6be5593685b5c4d` |
| [app/database/repositories/provider_repository.py](../app/database/repositories/provider_repository.py) | 6573 | `6caff3fb6ab4bcfe` |
| [app/database/repositories/review_repository.py](../app/database/repositories/review_repository.py) | 6357 | `5685e244581d3bc0` |
| [app/database/repositories/settings_repository.py](../app/database/repositories/settings_repository.py) | 5794 | `40d436e668ffbafb` |
| [app/database/repositories/signal_repository.py](../app/database/repositories/signal_repository.py) | 10918 | `1a8f6468db185063` |
| [app/database/repositories/symbol_repository.py](../app/database/repositories/symbol_repository.py) | 18976 | `eee46c52acaed1cf` |
| [app/database/repositories/system_repository.py](../app/database/repositories/system_repository.py) | 2692 | `cf424831ee511eda` |
| [app/database/repositories/trade_repository.py](../app/database/repositories/trade_repository.py) | 14342 | `38520996cf57a623` |
| [app/database/repositories/user_repository.py](../app/database/repositories/user_repository.py) | 30761 | `089465b31d9f4682` |
| [app/database/session.py](../app/database/session.py) | 13360 | `a272ec695f100fac` |
| [app/exceptions/__init__.py](../app/exceptions/__init__.py) | 1624 | `73c09064599ca212` |
| [app/exceptions/errors.py](../app/exceptions/errors.py) | 6604 | `728bf25f66141fc7` |
| [app/logging/__init__.py](../app/logging/__init__.py) | 542 | `e68387975c744ee3` |
| [app/logging/logger.py](../app/logging/logger.py) | 5856 | `da501cb80bc7f55b` |
| [app/security/__init__.py](../app/security/__init__.py) | 1147 | `72b42de6901e7117` |
| [app/security/db_backend.py](../app/security/db_backend.py) | 5765 | `90690332ecdea91c` |
| [app/security/passwords.py](../app/security/passwords.py) | 6347 | `8779a64d199dc00a` |
| [app/security/secret_store.py](../app/security/secret_store.py) | 17258 | `9d2c34e0f25f95ca` |
| [assets/README.md](../assets/README.md) | 476 | `24029dc6f3678ed4` |
| [assets/fonts/BKoodakBd.ttf](../assets/fonts/BKoodakBd.ttf) | 60584 | `a90573a0f5724422` |
| [assets/fonts/Koodak.ttf](../assets/fonts/Koodak.ttf) | 82155 | `3ee264cf64cb8f24` |
| [assets/fonts/Sahel-Bold.ttf](../assets/fonts/Sahel-Bold.ttf) | 76372 | `d714fa224c92bc51` |
| [assets/fonts/Sahel.ttf](../assets/fonts/Sahel.ttf) | 75308 | `5de2fe8cd1995f10` |
| [assets/fonts/Vazirmatn-Bold.ttf](../assets/fonts/Vazirmatn-Bold.ttf) | 123036 | `f635fdbea28f265d` |
| [assets/fonts/Vazirmatn-Regular.ttf](../assets/fonts/Vazirmatn-Regular.ttf) | 122752 | `b69fd4c680b8f3f2` |
| [assets/fonts/user/README.txt](../assets/fonts/user/README.txt) | 1605 | `b3d53c344bdb47ef` |
| [backup/__init__.py](../backup/__init__.py) | 416 | `de94dbffd34bb2bd` |
| [backup/manager.py](../backup/manager.py) | 17825 | `5603cbfadda0c472` |
| [docs/ADD_AI_PROVIDER_FA.md](../docs/ADD_AI_PROVIDER_FA.md) | 7761 | `3ae3898fc90a15c5` |
| [docs/ADD_EXCHANGE_FA.md](../docs/ADD_EXCHANGE_FA.md) | 12200 | `9d55b333aa8eba0b` |
| [docs/ADD_INDICATOR_FA.md](../docs/ADD_INDICATOR_FA.md) | 5620 | `873c2dcfcf80f559` |
| [docs/AI_OMNIROUTE_FA.md](../docs/AI_OMNIROUTE_FA.md) | 10944 | `1bfd9c69a6a5072d` |
| [docs/AI_SETUP_FA.md](../docs/AI_SETUP_FA.md) | 12644 | `55204e72772b2493` |
| [docs/ARCHITECTURE_FA.md](../docs/ARCHITECTURE_FA.md) | 13376 | `6746876c9624e93c` |
| [docs/ASHNA_FA.md](../docs/ASHNA_FA.md) | 3795 | `96abf994890b6c58` |
| [docs/BUGFIX_SIGNALS_FA.md](../docs/BUGFIX_SIGNALS_FA.md) | 10734 | `3179adcef9c0a203` |
| [docs/BUILD_INSTALLER_FA.md](../docs/BUILD_INSTALLER_FA.md) | 4730 | `c8e04549c572d9c6` |
| [docs/BUILD_WINDOWS_FA.md](../docs/BUILD_WINDOWS_FA.md) | 4062 | `24d62bdedc65f429` |
| [docs/CHAT_TOOL_STEPS_FA.md](../docs/CHAT_TOOL_STEPS_FA.md) | 5915 | `eff8af6958c95463` |
| [docs/DATABASE_FA.md](../docs/DATABASE_FA.md) | 14732 | `08024dbff2a38b98` |
| [docs/DESIGN_ANALYSIS_FA.md](../docs/DESIGN_ANALYSIS_FA.md) | 13306 | `486c94e9f58716fa` |
| [docs/EXCHANGES_BITPIN_TOOBIT_FA.md](../docs/EXCHANGES_BITPIN_TOOBIT_FA.md) | 12272 | `8b16508a99565a33` |
| [docs/FONTS_FA.md](../docs/FONTS_FA.md) | 3897 | `89480e78096078e9` |
| [docs/HANDOVER_FA.md](../docs/HANDOVER_FA.md) | 14093 | `10efedb1068e6000` |
| [docs/LBANK_API_FA.md](../docs/LBANK_API_FA.md) | 11218 | `7e17cf9f680238a5` |
| [docs/LIVE_DATA_AND_STREAMING_FA.md](../docs/LIVE_DATA_AND_STREAMING_FA.md) | 9375 | `d4b20837569ea3c1` |
| [docs/MARKET_SCANNER_FA.md](../docs/MARKET_SCANNER_FA.md) | 5828 | `1cfcb2939b1aa716` |
| [docs/MOBILE_FA.md](../docs/MOBILE_FA.md) | 5378 | `4266c5287d40abd1` |
| [docs/NEW_FEATURES_V1918_FA.md](../docs/NEW_FEATURES_V1918_FA.md) | 7239 | `f4de6a9962cd678d` |
| [docs/NEW_TOOLS_PROPOSAL_FA.md](../docs/NEW_TOOLS_PROPOSAL_FA.md) | 9724 | `14588149e90c3334` |
| [docs/NEW_TOOL_PROPOSAL_v195_FA.md](../docs/NEW_TOOL_PROPOSAL_v195_FA.md) | 8142 | `740f586017bd6543` |
| [docs/PREDICTIVE_ENGINE_FA.md](../docs/PREDICTIVE_ENGINE_FA.md) | 18249 | `835ffdc64018368d` |
| [docs/PROFESSIONAL_ROADMAP_FA.md](../docs/PROFESSIONAL_ROADMAP_FA.md) | 18861 | `fe8dfd7b40d6c272` |
| [docs/SCALP_FA.md](../docs/SCALP_FA.md) | 10304 | `f6bf8abd595b680e` |
| [docs/SECURITY_FA.md](../docs/SECURITY_FA.md) | 4516 | `b53bd1ff5b6461cf` |
| [docs/SIGNAL_AI_TROUBLESHOOTING_FA.md](../docs/SIGNAL_AI_TROUBLESHOOTING_FA.md) | 5306 | `576ca2959cea88ff` |
| [docs/SIGNAL_TABLES_FA.md](../docs/SIGNAL_TABLES_FA.md) | 20245 | `71c60aa6585bca10` |
| [docs/THEMES_FA.md](../docs/THEMES_FA.md) | 4058 | `6d5c545db47b1802` |
| [docs/TROUBLESHOOTING_FA.md](../docs/TROUBLESHOOTING_FA.md) | 16087 | `b9fbfabdcd5f8457` |
| [indicators/__init__.py](../indicators/__init__.py) | 923 | `a041e775448f2b85` |
| [indicators/base.py](../indicators/base.py) | 7486 | `5181f820a2a6acb0` |
| [indicators/engine.py](../indicators/engine.py) | 14941 | `43c06a328f532f91` |
| [indicators/momentum.py](../indicators/momentum.py) | 12850 | `94ca0e781621ad69` |
| [indicators/registry.py](../indicators/registry.py) | 4683 | `e0a3d92dc0ea0304` |
| [indicators/support_resistance.py](../indicators/support_resistance.py) | 14181 | `52c98729f53f51f3` |
| [indicators/trend.py](../indicators/trend.py) | 15406 | `0d154434cdc003a7` |
| [indicators/volatility.py](../indicators/volatility.py) | 9180 | `ebe7dc7a0c7ad1dc` |
| [indicators/volume.py](../indicators/volume.py) | 7223 | `0665cfa48e6638d3` |
| [installer/CryptoAITrader.iss](../installer/CryptoAITrader.iss) | 3263 | `cc3ad1d574f1f381` |
| [localization/__init__.py](../localization/__init__.py) | 527 | `5b4fe458d702953d` |
| [localization/en/alerts.json](../localization/en/alerts.json) | 474 | `b4b6d58a699ba688` |
| [localization/en/analysis.json](../localization/en/analysis.json) | 1274 | `b5125e30d14393d6` |
| [localization/en/auth.json](../localization/en/auth.json) | 3615 | `9b98f7ecb9c73118` |
| [localization/en/charts.json](../localization/en/charts.json) | 524 | `c07644eb647cd048` |
| [localization/en/chat.json](../localization/en/chat.json) | 2768 | `0d2619de892f2376` |
| [localization/en/common.json](../localization/en/common.json) | 2654 | `cde0a5cdeb0e8032` |
| [localization/en/dashboard.json](../localization/en/dashboard.json) | 767 | `b28dd9b6f3a51c7f` |
| [localization/en/email.json](../localization/en/email.json) | 1385 | `a61049d9744bd63b` |
| [localization/en/errors.json](../localization/en/errors.json) | 1773 | `3529215439e69639` |
| [localization/en/exchange.json](../localization/en/exchange.json) | 734 | `67e8f8a9f17fe74b` |
| [localization/en/help.json](../localization/en/help.json) | 3618 | `10248ca6d58a37a6` |
| [localization/en/layout.json](../localization/en/layout.json) | 273 | `e7b24e1825b4c870` |
| [localization/en/markets.json](../localization/en/markets.json) | 2364 | `b67c6f58bf6fe25f` |
| [localization/en/nav.json](../localization/en/nav.json) | 276 | `e338db2f1699ccff` |
| [localization/en/performance.json](../localization/en/performance.json) | 1176 | `ac79ab413b2c329f` |
| [localization/en/prediction.json](../localization/en/prediction.json) | 4330 | `ab9b036c5843a69d` |
| [localization/en/recommendation.json](../localization/en/recommendation.json) | 387 | `46ab9023a08c3b05` |
| [localization/en/reports.json](../localization/en/reports.json) | 1131 | `9d3ba6d27411cd8f` |
| [localization/en/review.json](../localization/en/review.json) | 901 | `dd57f67ba67fa2ed` |
| [localization/en/scorecard.json](../localization/en/scorecard.json) | 1218 | `81be5861216037af` |
| [localization/en/settings.json](../localization/en/settings.json) | 14904 | `1fef54016e32d498` |
| [localization/en/sidebar.json](../localization/en/sidebar.json) | 91 | `8ed11d267c7ec78f` |
| [localization/en/signals.json](../localization/en/signals.json) | 6796 | `35db842445759c6b` |
| [localization/en/sizing.json](../localization/en/sizing.json) | 1921 | `092383b041db2172` |
| [localization/en/trades.json](../localization/en/trades.json) | 10938 | `ad17f0b216e36f41` |
| [localization/en/tutorial.json](../localization/en/tutorial.json) | 18544 | `52789b8c7477e6fb` |
| [localization/en/validity.json](../localization/en/validity.json) | 1548 | `c314bb123358ae8b` |
| [localization/en/wallet.json](../localization/en/wallet.json) | 1373 | `117058082d0e079e` |
| [localization/en/watchlist.json](../localization/en/watchlist.json) | 1071 | `0d487268376a716b` |
| [localization/en/wizard.json](../localization/en/wizard.json) | 1479 | `a56b7f6670b94920` |
| [localization/fa/alerts.json](../localization/fa/alerts.json) | 680 | `d4940fdcac4c2d05` |
| [localization/fa/analysis.json](../localization/fa/analysis.json) | 1727 | `04ae3725726ef664` |
| [localization/fa/auth.json](../localization/fa/auth.json) | 5138 | `ae9fdc002253b27c` |
| [localization/fa/charts.json](../localization/fa/charts.json) | 731 | `3741fc5474580acd` |
| [localization/fa/chat.json](../localization/fa/chat.json) | 3850 | `ffac86167ae50756` |
| [localization/fa/common.json](../localization/fa/common.json) | 3613 | `6b0d8d8dfc4475b1` |
| [localization/fa/dashboard.json](../localization/fa/dashboard.json) | 1089 | `2bad58f324cf8808` |
| [localization/fa/email.json](../localization/fa/email.json) | 1930 | `0060e9ac252353cf` |
| [localization/fa/errors.json](../localization/fa/errors.json) | 2777 | `49052590678d98e1` |
| [localization/fa/exchange.json](../localization/fa/exchange.json) | 1024 | `5ced514f75f2da68` |
| [localization/fa/help.json](../localization/fa/help.json) | 5961 | `f554cf06bcea87fc` |
| [localization/fa/layout.json](../localization/fa/layout.json) | 438 | `b7dc410da2a88d65` |
| [localization/fa/markets.json](../localization/fa/markets.json) | 3156 | `a20c08659aae87d5` |
| [localization/fa/nav.json](../localization/fa/nav.json) | 365 | `cafbdc8861d5d194` |
| [localization/fa/performance.json](../localization/fa/performance.json) | 1555 | `ba4728ec685fcdec` |
| [localization/fa/prediction.json](../localization/fa/prediction.json) | 5269 | `ff5ad8a57aefb7d6` |
| [localization/fa/recommendation.json](../localization/fa/recommendation.json) | 456 | `6ba3289928badb01` |
| [localization/fa/reports.json](../localization/fa/reports.json) | 1464 | `5f168de3a7d88a57` |
| [localization/fa/review.json](../localization/fa/review.json) | 1374 | `16db0ca77785bfb7` |
| [localization/fa/scorecard.json](../localization/fa/scorecard.json) | 1816 | `d90d0b89cbfa4201` |
| [localization/fa/settings.json](../localization/fa/settings.json) | 20989 | `2d43a76a7aa397a5` |
| [localization/fa/sidebar.json](../localization/fa/sidebar.json) | 119 | `155f8a9652a41f4a` |
| [localization/fa/signals.json](../localization/fa/signals.json) | 9737 | `79b975a52957384c` |
| [localization/fa/sizing.json](../localization/fa/sizing.json) | 2753 | `619f45d83e8a35fc` |
| [localization/fa/trades.json](../localization/fa/trades.json) | 14354 | `80d4adca237b2274` |
| [localization/fa/tutorial.json](../localization/fa/tutorial.json) | 29986 | `2b2d808aa5581026` |
| [localization/fa/validity.json](../localization/fa/validity.json) | 2205 | `fdf98893d8998496` |
| [localization/fa/wallet.json](../localization/fa/wallet.json) | 1855 | `a4d6d7433cab0652` |
| [localization/fa/watchlist.json](../localization/fa/watchlist.json) | 1538 | `ed6df2084ada4d46` |
| [localization/fa/wizard.json](../localization/fa/wizard.json) | 2405 | `646929bd717e22c0` |
| [localization/translator.py](../localization/translator.py) | 10976 | `1ca8caa70f3ef677` |
| [main.py](../main.py) | 6278 | `916513aa3c62eb3d` |
| [market/__init__.py](../market/__init__.py) | 421 | `a42798500dd31610` |
| [market/cache/__init__.py](../market/cache/__init__.py) | 151 | `d201181b1f0b67f8` |
| [market/cache/memory_cache.py](../market/cache/memory_cache.py) | 4888 | `d12e4a46e77b5b32` |
| [market/engine.py](../market/engine.py) | 31382 | `3dcac006741a6a8e` |
| [market/exchange_catalog.py](../market/exchange_catalog.py) | 7183 | `058c0a85a6ffef5b` |
| [market/fiat_rates.py](../market/fiat_rates.py) | 11865 | `31e038a33c04533d` |
| [market/live_feed.py](../market/live_feed.py) | 12974 | `525520e614736e38` |
| [market/providers/__init__.py](../market/providers/__init__.py) | 596 | `35cf7d0989bf4c2c` |
| [market/providers/base.py](../market/providers/base.py) | 9382 | `31530d2f0eef7542` |
| [market/providers/bitpin/__init__.py](../market/providers/bitpin/__init__.py) | 225 | `a740567e607916b6` |
| [market/providers/bitpin/constants.py](../market/providers/bitpin/constants.py) | 4516 | `ce45057c5dfe7001` |
| [market/providers/bitpin/parser.py](../market/providers/bitpin/parser.py) | 11368 | `852c53dd4c18de2d` |
| [market/providers/bitpin/provider.py](../market/providers/bitpin/provider.py) | 12381 | `ee420fe8d4942749` |
| [market/providers/bitpin/rest_client.py](../market/providers/bitpin/rest_client.py) | 12261 | `e4201c96ff140ae6` |
| [market/providers/lbank/__init__.py](../market/providers/lbank/__init__.py) | 991 | `aad4b60d0399fe96` |
| [market/providers/lbank/constants.py](../market/providers/lbank/constants.py) | 5715 | `831489c398f52ee2` |
| [market/providers/lbank/parser.py](../market/providers/lbank/parser.py) | 13958 | `40de18de93e76bdf` |
| [market/providers/lbank/provider.py](../market/providers/lbank/provider.py) | 23320 | `645dfed067e6a077` |
| [market/providers/lbank/rest_client.py](../market/providers/lbank/rest_client.py) | 14502 | `22bdbe6640ad94a6` |
| [market/providers/lbank/websocket_client.py](../market/providers/lbank/websocket_client.py) | 17264 | `cbe052bb8dfcfcfd` |
| [market/providers/registry.py](../market/providers/registry.py) | 3041 | `63e898888bbe5e1d` |
| [market/providers/toobit/__init__.py](../market/providers/toobit/__init__.py) | 203 | `3d5d44f0a83ec66a` |
| [market/providers/toobit/constants.py](../market/providers/toobit/constants.py) | 3069 | `b768850c41dd672f` |
| [market/providers/toobit/parser.py](../market/providers/toobit/parser.py) | 17420 | `480a87e5e79a7181` |
| [market/providers/toobit/provider.py](../market/providers/toobit/provider.py) | 13207 | `56f4b7c7942dc1b6` |
| [market/providers/toobit/rest_client.py](../market/providers/toobit/rest_client.py) | 9524 | `19393c90f35cd2ef` |
| [market/providers/toobit/websocket_client.py](../market/providers/toobit/websocket_client.py) | 17293 | `44e6a4c064e6a542` |
| [market/quality.py](../market/quality.py) | 14267 | `cd5ba6ffd06624a0` |
| [market/rate_limiter.py](../market/rate_limiter.py) | 4579 | `5bb0af61601c8aea` |
| [market/resilience.py](../market/resilience.py) | 12102 | `b4945e7bc4726775` |
| [market/timeframes.py](../market/timeframes.py) | 10308 | `59ba26533e695a2c` |
| [migrations/README](../migrations/README) | 243 | `a4e7fe9ddfc8e6db` |
| [migrations/env.py](../migrations/env.py) | 3465 | `97ec3a477292527e` |
| [migrations/script.py.mako](../migrations/script.py.mako) | 732 | `9f2c08af589d989a` |
| [migrations/versions/20260908_1316_initial_schema.py](../migrations/versions/20260908_1316_initial_schema.py) | 15037 | `9a4e03b76a25d0fb` |
| [migrations/versions/20260911_0817_chat_conversations.py](../migrations/versions/20260911_0817_chat_conversations.py) | 2716 | `12283229a79f64f8` |
| [migrations/versions/20260911_1040_users_sessions_exchange_accounts_paper_.py](../migrations/versions/20260911_1040_users_sessions_exchange_accounts_paper_.py) | 8388 | `3decddab67291a2e` |
| [migrations/versions/20260914_0700_signal_outcomes.py](../migrations/versions/20260914_0700_signal_outcomes.py) | 3625 | `70e2d716ffa6b5da` |
| [migrations/versions/20260915_0900_signal_validity_and_reviews.py](../migrations/versions/20260915_0900_signal_validity_and_reviews.py) | 3432 | `6243c3c719006293` |
| [migrations/versions/20260920_1200_trade_last_price.py](../migrations/versions/20260920_1200_trade_last_price.py) | 989 | `de7126ce748226ba` |
| [migrations/versions/20260920_1400_signal_forecast.py](../migrations/versions/20260920_1400_signal_forecast.py) | 960 | `300bdde4a1a8f3ec` |
| [migrations/versions/20260922_1600_prediction_records.py](../migrations/versions/20260922_1600_prediction_records.py) | 3519 | `89ed4aeb01fde20e` |
| [mobile/app/__init__.py](../mobile/app/__init__.py) | 124 | `edcfa85f61160b11` |
| [mobile/app/indicators_lite.py](../mobile/app/indicators_lite.py) | 8520 | `b93e72e93b8a8868` |
| [mobile/app/market_lite.py](../mobile/app/market_lite.py) | 4229 | `018e72a4f02ed5d7` |
| [mobile/app/signal_lite.py](../mobile/app/signal_lite.py) | 6570 | `402fff67842c0675` |
| [mobile/buildozer.spec](../mobile/buildozer.spec) | 1665 | `3c88669dfe38823e` |
| [mobile/main.py](../mobile/main.py) | 10611 | `c75adcda346165ee` |
| [mobile/version.py](../mobile/version.py) | 19 | `317bfbd15b1df042` |
| [pyproject.toml](../pyproject.toml) | 1918 | `aca2ac97eb1595f6` |
| [release/CryptoAITrader-v2.2.0-2026-09-23.zip](../release/CryptoAITrader-v2.2.0-2026-09-23.zip) | 2023150 | `4c24fe90ac8a5ce8` |
| [release/PR_DESCRIPTION.md](../release/PR_DESCRIPTION.md) | 3844 | `cf7579001c9575dc` |
| [release/RELEASE_NOTES_FA.md](../release/RELEASE_NOTES_FA.md) | 4725 | `684c56e465cab3a6` |
| [release/SHA256SUMS.txt](../release/SHA256SUMS.txt) | 103 | `68be59966ab4b117` |
| [reports/__init__.py](../reports/__init__.py) | 426 | `73aaee2f22fb83f9` |
| [reports/builder.py](../reports/builder.py) | 8269 | `b7f69d7cd17488f0` |
| [reports/exporters.py](../reports/exporters.py) | 16346 | `35995b160c00e0b6` |
| [reports/persian_pdf.py](../reports/persian_pdf.py) | 13982 | `beccd42770e35bdd` |
| [requirements.txt](../requirements.txt) | 2388 | `b576ba67b289c0f8` |
| [scripts/build.sh](../scripts/build.sh) | 1058 | `b2f89a14a5c1ace9` |
| [scripts/build_apk.bat](../scripts/build_apk.bat) | 2955 | `40642473c6cedce1` |
| [scripts/build_installer.bat](../scripts/build_installer.bat) | 3726 | `7d575f58b2a7c9eb` |
| [scripts/build_windows.bat](../scripts/build_windows.bat) | 1815 | `4dcfca33e6541b2b` |
| [scripts/doctor.bat](../scripts/doctor.bat) | 1372 | `8a7a0cc2278448ad` |
| [scripts/migrate.sh](../scripts/migrate.sh) | 403 | `e4ffc0e69fe9da1b` |
| [scripts/run_dev.sh](../scripts/run_dev.sh) | 286 | `441d4b8967e73018` |
| [scripts/run_tests.sh](../scripts/run_tests.sh) | 506 | `0fbfd808c74f2b54` |
| [signals/__init__.py](../signals/__init__.py) | 3800 | `a443ae9bcf508a59` |
| [signals/alerts.py](../signals/alerts.py) | 10499 | `45c262612beb0aae` |
| [signals/auto_scanner.py](../signals/auto_scanner.py) | 16747 | `e135a314dde52cf1` |
| [signals/confidence.py](../signals/confidence.py) | 9026 | `78e64de45dd920a1` |
| [signals/engine.py](../signals/engine.py) | 29935 | `cc475092f6263c25` |
| [signals/forecast.py](../signals/forecast.py) | 12917 | `398a7f430045723b` |
| [signals/outcome_tracker.py](../signals/outcome_tracker.py) | 15957 | `af577b10996cc84d` |
| [signals/paper_trader.py](../signals/paper_trader.py) | 10273 | `3bf1f3aa29863860` |
| [signals/position_sizing.py](../signals/position_sizing.py) | 12558 | `6944072ed89169b5` |
| [signals/prediction/__init__.py](../signals/prediction/__init__.py) | 1999 | `cac5c5535727c752` |
| [signals/prediction/anomaly.py](../signals/prediction/anomaly.py) | 6797 | `7183f36711648a23` |
| [signals/prediction/breakout.py](../signals/prediction/breakout.py) | 9102 | `0ad35cda88124da0` |
| [signals/prediction/crossasset.py](../signals/prediction/crossasset.py) | 6586 | `c8ea0edddfac20e5` |
| [signals/prediction/distribution.py](../signals/prediction/distribution.py) | 10017 | `f984912aaf7b5deb` |
| [signals/prediction/engine.py](../signals/prediction/engine.py) | 35603 | `c05ab114c3e487bd` |
| [signals/prediction/events.py](../signals/prediction/events.py) | 6916 | `d7958edf8fb0f3eb` |
| [signals/prediction/explain.py](../signals/prediction/explain.py) | 5245 | `24235983e3108c16` |
| [signals/prediction/features.py](../signals/prediction/features.py) | 14061 | `aa20b8c38879a68a` |
| [signals/prediction/fusion.py](../signals/prediction/fusion.py) | 8425 | `3736a69d5c388784` |
| [signals/prediction/horizons.py](../signals/prediction/horizons.py) | 6610 | `89cf302d16d7d8a9` |
| [signals/prediction/models/__init__.py](../signals/prediction/models/__init__.py) | 1571 | `87764cc86ea6d14c` |
| [signals/prediction/models/base.py](../signals/prediction/models/base.py) | 5063 | `70c2dc129143b1de` |
| [signals/prediction/models/drift.py](../signals/prediction/models/drift.py) | 3373 | `b312ebf90b789656` |
| [signals/prediction/models/ensemble.py](../signals/prediction/models/ensemble.py) | 8800 | `017a7f5e0aa3ab1f` |
| [signals/prediction/models/gbm.py](../signals/prediction/models/gbm.py) | 6064 | `281800b7c655f3c9` |
| [signals/prediction/models/lstm.py](../signals/prediction/models/lstm.py) | 6913 | `314069b7ad0c16a6` |
| [signals/prediction/models/statistical.py](../signals/prediction/models/statistical.py) | 4983 | `ec78ac984b4fa71c` |
| [signals/prediction/models/walkforward.py](../signals/prediction/models/walkforward.py) | 5585 | `76a1caa311f60988` |
| [signals/prediction/regime.py](../signals/prediction/regime.py) | 15619 | `8a32cde0ca1b70b2` |
| [signals/prediction/scenarios.py](../signals/prediction/scenarios.py) | 7971 | `deb8f0b382c81c57` |
| [signals/prediction/scoring.py](../signals/prediction/scoring.py) | 6416 | `51653f47d4db5bfc` |
| [signals/prediction/store.py](../signals/prediction/store.py) | 7343 | `59dab9117f5daafc` |
| [signals/prediction/timeline.py](../signals/prediction/timeline.py) | 4537 | `14262df3fb53cd27` |
| [signals/prediction/uncertainty.py](../signals/prediction/uncertainty.py) | 5436 | `ad3328df31ad8fa4` |
| [signals/prediction/volatility.py](../signals/prediction/volatility.py) | 5599 | `e00e9604e5a12f00` |
| [signals/prediction/warning.py](../signals/prediction/warning.py) | 7047 | `018d035cde5d4daa` |
| [signals/risk_engine.py](../signals/risk_engine.py) | 12806 | `cba2b139ec3641fe` |
| [signals/scanner.py](../signals/scanner.py) | 11258 | `192c69aa582736f0` |
| [signals/scorecard.py](../signals/scorecard.py) | 8943 | `c5465bc5f617cd24` |
| [signals/strategies/__init__.py](../signals/strategies/__init__.py) | 842 | `9784e540c3e6a8e2` |
| [signals/strategies/base.py](../signals/strategies/base.py) | 5699 | `257450ce74d37d20` |
| [signals/strategies/breakout.py](../signals/strategies/breakout.py) | 2959 | `31e0dbfd59059176` |
| [signals/strategies/mean_reversion.py](../signals/strategies/mean_reversion.py) | 3646 | `6e7514b13ac09948` |
| [signals/strategies/momentum.py](../signals/strategies/momentum.py) | 5331 | `c32e70bc57fd295c` |
| [signals/strategies/registry.py](../signals/strategies/registry.py) | 3201 | `0da647383d3f70b0` |
| [signals/strategies/trend_following.py](../signals/strategies/trend_following.py) | 3666 | `6d87adb9b319c889` |
| [signals/strategies/volatility_regime.py](../signals/strategies/volatility_regime.py) | 4841 | `c6489076a1514800` |
| [signals/validity.py](../signals/validity.py) | 19249 | `827d319ea7839541` |
| [tests/__init__.py](../tests/__init__.py) | 66 | `60b53a2e49d96826` |
| [tests/conftest.py](../tests/conftest.py) | 9096 | `5b3623da1ccef9d7` |
| [tests/test_ai_providers.py](../tests/test_ai_providers.py) | 15700 | `4de0b4fd40b3f4bf` |
| [tests/test_ai_validator.py](../tests/test_ai_validator.py) | 4977 | `9a2c26332044e5d4` |
| [tests/test_async_runner.py](../tests/test_async_runner.py) | 5199 | `4d5cea517518a94a` |
| [tests/test_auth.py](../tests/test_auth.py) | 18406 | `b1bde196522a0344` |
| [tests/test_autonomous_agent.py](../tests/test_autonomous_agent.py) | 12245 | `641a59d5509f914d` |
| [tests/test_backup.py](../tests/test_backup.py) | 4492 | `5a7e36f72a8d729d` |
| [tests/test_chat_agent.py](../tests/test_chat_agent.py) | 12798 | `cc259928ac2af4f7` |
| [tests/test_chat_page.py](../tests/test_chat_page.py) | 9771 | `c6484eaf50081fbb` |
| [tests/test_chat_repository.py](../tests/test_chat_repository.py) | 7271 | `e2efbc803623e3e2` |
| [tests/test_chat_ui_v2.py](../tests/test_chat_ui_v2.py) | 12363 | `f262557333f535fe` |
| [tests/test_exchange_login_flow.py](../tests/test_exchange_login_flow.py) | 11184 | `4d6c6a01ace4781a` |
| [tests/test_exchange_switching.py](../tests/test_exchange_switching.py) | 9973 | `dbccc2acf9f300c2` |
| [tests/test_icons_search_theme.py](../tests/test_icons_search_theme.py) | 8400 | `4ffcf4fe24ee9c1a` |
| [tests/test_indicators.py](../tests/test_indicators.py) | 3537 | `bda5536787798bbc` |
| [tests/test_localization.py](../tests/test_localization.py) | 3344 | `1db82f318e5ec208` |
| [tests/test_market_resilience.py](../tests/test_market_resilience.py) | 10587 | `67c2587691618e72` |
| [tests/test_markets_sorting.py](../tests/test_markets_sorting.py) | 11762 | `da20e3f62864ffc0` |
| [tests/test_narrative.py](../tests/test_narrative.py) | 8914 | `e241cf3323b0b00d` |
| [tests/test_new_pages.py](../tests/test_new_pages.py) | 10885 | `ae60239a978efe83` |
| [tests/test_pages_design_v151.py](../tests/test_pages_design_v151.py) | 12943 | `8068dd1e32ce89d0` |
| [tests/test_paper_trader.py](../tests/test_paper_trader.py) | 5488 | `348923b262ade72d` |
| [tests/test_persian_pdf.py](../tests/test_persian_pdf.py) | 6529 | `6d09442586160829` |
| [tests/test_prediction_lifecycle.py](../tests/test_prediction_lifecycle.py) | 14515 | `4d36837da38a3586` |
| [tests/test_prediction_ui_and_tools.py](../tests/test_prediction_ui_and_tools.py) | 10083 | `8813be187c3a0171` |
| [tests/test_predictive_phase1.py](../tests/test_predictive_phase1.py) | 13713 | `ad509f4a24077ea1` |
| [tests/test_predictive_phase2_5.py](../tests/test_predictive_phase2_5.py) | 33646 | `c8fd6ca5d64bdb3d` |
| [tests/test_reports.py](../tests/test_reports.py) | 5948 | `bef302289d460a2b` |
| [tests/test_risk_engine.py](../tests/test_risk_engine.py) | 5539 | `2aec1c06d12c35bc` |
| [tests/test_settings_expanded.py](../tests/test_settings_expanded.py) | 11028 | `154d73c2553b0049` |
| [tests/test_signal_engine.py](../tests/test_signal_engine.py) | 5776 | `8c9c9866807e8c35` |
| [tests/test_themes.py](../tests/test_themes.py) | 6714 | `0d530068bd703b2a` |
| [tests/test_timeframes.py](../tests/test_timeframes.py) | 5242 | `089814e98abcdc2d` |
| [tests/test_toobit_bitpin_providers.py](../tests/test_toobit_bitpin_providers.py) | 16544 | `6daac1dfbd65c82f` |
| [tests/test_trades_and_wallet.py](../tests/test_trades_and_wallet.py) | 9290 | `da90f58a20031985` |
| [tests/test_ui_wiring.py](../tests/test_ui_wiring.py) | 11322 | `e72986e17c8c0566` |
| [tests/test_v153_fixes.py](../tests/test_v153_fixes.py) | 11301 | `75212b57ec20bdda` |
| [tests/test_v154_ai_signal.py](../tests/test_v154_ai_signal.py) | 9684 | `0c6c776c8692288e` |
| [tests/test_v154_localization.py](../tests/test_v154_localization.py) | 5305 | `b9d079ba80242f54` |
| [tests/test_v154_packaging.py](../tests/test_v154_packaging.py) | 3823 | `4a327b2cf0572b7f` |
| [tests/test_v154_security_money.py](../tests/test_v154_security_money.py) | 7471 | `ef2b0c0d627a28f3` |
| [tests/test_v155_ui_and_ai.py](../tests/test_v155_ui_and_ai.py) | 7420 | `93624365b5e80f8b` |
| [tests/test_v156_fixes.py](../tests/test_v156_fixes.py) | 30847 | `f9f2fda5a0b9253b` |
| [tests/test_v158_security_tab.py](../tests/test_v158_security_tab.py) | 16289 | `972876875fb44ca3` |
| [tests/test_v160_error_keys.py](../tests/test_v160_error_keys.py) | 9929 | `6b4c52f934c8215b` |
| [tests/test_v160_ui_polish.py](../tests/test_v160_ui_polish.py) | 11777 | `ed5b1a775cd0ee63` |
| [tests/test_v161_omniroute_font_theme.py](../tests/test_v161_omniroute_font_theme.py) | 36704 | `ad7d79d75ed11c26` |
| [tests/test_v162_chat_streaming.py](../tests/test_v162_chat_streaming.py) | 21718 | `34be3ddaa96ae108` |
| [tests/test_v162_modal_close.py](../tests/test_v162_modal_close.py) | 7123 | `4ac2362f58f10fea` |
| [tests/test_v162_toobit_websocket.py](../tests/test_v162_toobit_websocket.py) | 20842 | `d0c3d9c29582b064` |
| [tests/test_v170_scanner_fonts_theme.py](../tests/test_v170_scanner_fonts_theme.py) | 20004 | `63922362c71b5079` |
| [tests/test_v170_signals_ui.py](../tests/test_v170_signals_ui.py) | 15528 | `1d76e822e450930b` |
| [tests/test_v171_chat_tool_steps.py](../tests/test_v171_chat_tool_steps.py) | 15986 | `636f62614cadf1ae` |
| [tests/test_v172_signal_ai_and_scan_ui.py](../tests/test_v172_signal_ai_and_scan_ui.py) | 14816 | `7d175f381b51f161` |
| [tests/test_v180_ai_status_card.py](../tests/test_v180_ai_status_card.py) | 6579 | `e56ea34ec9d52a2c` |
| [tests/test_v180_arrangeable_layout.py](../tests/test_v180_arrangeable_layout.py) | 12036 | `1b3ef0a07ef1b857` |
| [tests/test_v180_custom_themes.py](../tests/test_v180_custom_themes.py) | 14671 | `687f218b02473974` |
| [tests/test_v180_table_fullscreen.py](../tests/test_v180_table_fullscreen.py) | 7255 | `cca3026ad68efeb3` |
| [tests/test_v180_tutorial.py](../tests/test_v180_tutorial.py) | 6495 | `529ddb647efc1799` |
| [tests/test_v190_account_and_auto_scan.py](../tests/test_v190_account_and_auto_scan.py) | 23687 | `6e171e24b7793ef9` |
| [tests/test_v190_position_sizing.py](../tests/test_v190_position_sizing.py) | 20672 | `b106066d93f45a4a` |
| [tests/test_v1910_ollama_doctor.py](../tests/test_v1910_ollama_doctor.py) | 8536 | `1660b86b094af076` |
| [tests/test_v1911_ai_signal_mode.py](../tests/test_v1911_ai_signal_mode.py) | 12352 | `2837bb358cf82595` |
| [tests/test_v1911_build_and_update.py](../tests/test_v1911_build_and_update.py) | 16124 | `0cb1fda4a007da1f` |
| [tests/test_v1912_mobile.py](../tests/test_v1912_mobile.py) | 17356 | `e1494b6429c91526` |
| [tests/test_v1913_ashna.py](../tests/test_v1913_ashna.py) | 11797 | `01c1c86d3f2c4533` |
| [tests/test_v1914_scalp.py](../tests/test_v1914_scalp.py) | 25399 | `d8cecbdffd41ef47` |
| [tests/test_v1915_bugfixes.py](../tests/test_v1915_bugfixes.py) | 13082 | `050b0b2dd7d5e070` |
| [tests/test_v1916_ai_wait.py](../tests/test_v1916_ai_wait.py) | 8084 | `6c3e5644a9eedaf1` |
| [tests/test_v1917_forecast.py](../tests/test_v1917_forecast.py) | 22063 | `7becb10a8b797ca5` |
| [tests/test_v1917_trust_and_trades.py](../tests/test_v1917_trust_and_trades.py) | 20590 | `3ee22f51c7678bd9` |
| [tests/test_v1918_alerts.py](../tests/test_v1918_alerts.py) | 13061 | `37fb91f871b48967` |
| [tests/test_v1918_live_and_auto.py](../tests/test_v1918_live_and_auto.py) | 18694 | `8e75e84a1842f26d` |
| [tests/test_v1918_scorecard.py](../tests/test_v1918_scorecard.py) | 13355 | `b2867acf98f465c8` |
| [tests/test_v191_outcome_tracking.py](../tests/test_v191_outcome_tracking.py) | 37475 | `13dd19e21ff8b7b0` |
| [tests/test_v1920_ashna_settings.py](../tests/test_v1920_ashna_settings.py) | 8339 | `eccaadb2af258749` |
| [tests/test_v1921_online_and_autotrade.py](../tests/test_v1921_online_and_autotrade.py) | 16762 | `857bf273655a2c3b` |
| [tests/test_v1922_micro_speed.py](../tests/test_v1922_micro_speed.py) | 5380 | `887968ad2413a8ab` |
| [tests/test_v192_watchlist.py](../tests/test_v192_watchlist.py) | 21737 | `2cb3f28df0045dbb` |
| [tests/test_v193_page_scrolling.py](../tests/test_v193_page_scrolling.py) | 11487 | `ed4e2cfc9166d38b` |
| [tests/test_v194_performance.py](../tests/test_v194_performance.py) | 16610 | `db4f32ab08a9cc7e` |
| [tests/test_v195_ai_and_validity.py](../tests/test_v195_ai_and_validity.py) | 46292 | `b42d90f1383f98cf` |
| [tests/test_v196_fixes.py](../tests/test_v196_fixes.py) | 49957 | `6d041d4b250c1547` |
| [tests/test_v200_event_driven_trading.py](../tests/test_v200_event_driven_trading.py) | 59409 | `2854a616a363d475` |
| [tests/test_v22_terminal_pro.py](../tests/test_v22_terminal_pro.py) | 17529 | `c1f2ca456e1b8f96` |
| [tools/build_apk.py](../tools/build_apk.py) | 9781 | `f33d7b1df1ad5150` |
| [tools/build_doctor.py](../tools/build_doctor.py) | 12326 | `3d14e0e0ed119442` |
| [tools/build_installer.py](../tools/build_installer.py) | 11354 | `62384897961be680` |
| [tools/ollama_doctor.py](../tools/ollama_doctor.py) | 8592 | `3a4e2922b13f65c3` |
| [tools/preview_shot.py](../tools/preview_shot.py) | 5813 | `ec480f1f5bb5587d` |
| [tools/set_ai_key.py](../tools/set_ai_key.py) | 2045 | `9a7acd64c0fadc78` |
| [tools/sweep_ui.py](../tools/sweep_ui.py) | 1820 | `05a73813c0c30304` |
| [trading/__init__.py](../trading/__init__.py) | 360 | `d5cc850ce8b4dd9a` |
| [trading/ai_decider.py](../trading/ai_decider.py) | 15430 | `32ea1365d2bef57e` |
| [trading/auto_trader.py](../trading/auto_trader.py) | 54375 | `10b17ff50afde219` |
| [trading/confidence_source.py](../trading/confidence_source.py) | 7671 | `526ffd276d90767c` |
| [trading/execution.py](../trading/execution.py) | 907 | `5c6d178429fdc042` |
| [trading/micro_plan.py](../trading/micro_plan.py) | 3262 | `f8af0e00dce3f106` |
| [trading/price_cache.py](../trading/price_cache.py) | 16193 | `e223ce3c5f79f722` |
| [trading/scalp_scanner.py](../trading/scalp_scanner.py) | 12943 | `3c3a1cf4f4d325b1` |
| [trading/scalp_service.py](../trading/scalp_service.py) | 11444 | `54128771f8b93793` |
| [trading/trade_monitor.py](../trading/trade_monitor.py) | 7037 | `fbe0ba77e5daf1c0` |
| [trading/trend_ladder.py](../trading/trend_ladder.py) | 9374 | `bfaa2990648e070d` |
| [ui/__init__.py](../ui/__init__.py) | 394 | `b1433f5db168fcfe` |
| [ui/charts/__init__.py](../ui/charts/__init__.py) | 181 | `1b56f42636e6cd00` |
| [ui/charts/candlestick_item.py](../ui/charts/candlestick_item.py) | 4772 | `2d2e5552039058ea` |
| [ui/charts/price_chart.py](../ui/charts/price_chart.py) | 22780 | `4ea383a0d6424032` |
| [ui/controllers/__init__.py](../ui/controllers/__init__.py) | 297 | `9e3aabf762801b4c` |
| [ui/controllers/async_runner.py](../ui/controllers/async_runner.py) | 10992 | `f7a9b285a5dd8abc` |
| [ui/controllers/main_controller.py](../ui/controllers/main_controller.py) | 347708 | `a1ce330c77bde7d1` |
| [ui/dialogs/__init__.py](../ui/dialogs/__init__.py) | 557 | `498781a8a3cc9582` |
| [ui/dialogs/analysis_dialog.py](../ui/dialogs/analysis_dialog.py) | 9322 | `001a6107b4ab64d5` |
| [ui/dialogs/auth_dialog.py](../ui/dialogs/auth_dialog.py) | 12034 | `19c041a62fa143fd` |
| [ui/dialogs/coin_detail_dialog.py](../ui/dialogs/coin_detail_dialog.py) | 16019 | `3368c3f713e3962f` |
| [ui/dialogs/first_run_wizard.py](../ui/dialogs/first_run_wizard.py) | 8315 | `0e892185b3d3d3a5` |
| [ui/dialogs/password_reset_dialog.py](../ui/dialogs/password_reset_dialog.py) | 15832 | `f79179cc21617961` |
| [ui/dialogs/signal_detail_dialog.py](../ui/dialogs/signal_detail_dialog.py) | 29387 | `f156fa87d1b8490a` |
| [ui/dialogs/trading_dialogs.py](../ui/dialogs/trading_dialogs.py) | 15814 | `82fd06f9f243624b` |
| [ui/icons/__init__.py](../ui/icons/__init__.py) | 1249 | `7393b8e131de9ac1` |
| [ui/icons/paths.py](../ui/icons/paths.py) | 7983 | `bd8722b89e3894db` |
| [ui/icons/registry.py](../ui/icons/registry.py) | 4826 | `95f07373f3f3170c` |
| [ui/pages/__init__.py](../ui/pages/__init__.py) | 1046 | `61e6a435b93f37fe` |
| [ui/pages/analysis_page.py](../ui/pages/analysis_page.py) | 21010 | `72d1eee6cd5fd354` |
| [ui/pages/base_page.py](../ui/pages/base_page.py) | 5380 | `396a625608da7879` |
| [ui/pages/chat_page.py](../ui/pages/chat_page.py) | 40586 | `0bced7183f99950a` |
| [ui/pages/dashboard_page.py](../ui/pages/dashboard_page.py) | 15986 | `558ebf24a66a0153` |
| [ui/pages/help_page.py](../ui/pages/help_page.py) | 4161 | `da4127fc29d0875d` |
| [ui/pages/markets_page.py](../ui/pages/markets_page.py) | 35373 | `d7212ecfc228c0c3` |
| [ui/pages/prediction_page.py](../ui/pages/prediction_page.py) | 39411 | `c7dae9e6eb3fcc98` |
| [ui/pages/reports_page.py](../ui/pages/reports_page.py) | 19932 | `12dbcceb0656dddb` |
| [ui/pages/settings_page.py](../ui/pages/settings_page.py) | 90903 | `61b9361a21005231` |
| [ui/pages/signals_page.py](../ui/pages/signals_page.py) | 49989 | `82703025d5cfcc1e` |
| [ui/pages/trades_page.py](../ui/pages/trades_page.py) | 107412 | `5267321b1c58fc31` |
| [ui/pages/wallet_page.py](../ui/pages/wallet_page.py) | 15995 | `135434fcf776d126` |
| [ui/signal_grading.py](../ui/signal_grading.py) | 10652 | `193184124f0ea921` |
| [ui/themes/__init__.py](../ui/themes/__init__.py) | 1316 | `d2cf5eae78235f0a` |
| [ui/themes/catalog.py](../ui/themes/catalog.py) | 22966 | `4cadf09f10abc179` |
| [ui/themes/custom.py](../ui/themes/custom.py) | 13550 | `adcecab6a8253b17` |
| [ui/themes/fonts.py](../ui/themes/fonts.py) | 13460 | `20166d8a34298286` |
| [ui/themes/stylesheet.py](../ui/themes/stylesheet.py) | 23686 | `bbea6cab86fed169` |
| [ui/themes/theme_manager.py](../ui/themes/theme_manager.py) | 11954 | `68f2c9aa823d09d2` |
| [ui/themes/tokens.py](../ui/themes/tokens.py) | 6180 | `02bc9a1f6a778bc5` |
| [ui/widgets/__init__.py](../ui/widgets/__init__.py) | 2091 | `ca03ece5329087d4` |
| [ui/widgets/ai_status_card.py](../ui/widgets/ai_status_card.py) | 8664 | `478084b9bb104b9d` |
| [ui/widgets/arrangeable.py](../ui/widgets/arrangeable.py) | 14080 | `0202fa4bb8ce1593` |
| [ui/widgets/avatar.py](../ui/widgets/avatar.py) | 4613 | `ce086887902971a5` |
| [ui/widgets/charts_mini.py](../ui/widgets/charts_mini.py) | 22442 | `206eda720e6cc16f` |
| [ui/widgets/chrome.py](../ui/widgets/chrome.py) | 29381 | `e4acee9db8fda540` |
| [ui/widgets/common.py](../ui/widgets/common.py) | 25661 | `66a369c240787bd6` |
| [ui/widgets/controls.py](../ui/widgets/controls.py) | 24801 | `5dc62b14c3df0d95` |
| [ui/widgets/performance_view.py](../ui/widgets/performance_view.py) | 18810 | `4d1465a0bbfccb26` |
| [ui/widgets/position_calculator.py](../ui/widgets/position_calculator.py) | 14635 | `89efe6f2aa14391a` |
| [ui/widgets/responsive_grid.py](../ui/widgets/responsive_grid.py) | 7167 | `1eaa2f725f71f5b9` |
| [ui/widgets/table_toolbar.py](../ui/widgets/table_toolbar.py) | 17108 | `f06dd7a00a8c26c3` |
| [ui/widgets/theme_card.py](../ui/widgets/theme_card.py) | 8058 | `598ab4b796ea869f` |
| [ui/widgets/theme_editor.py](../ui/widgets/theme_editor.py) | 15274 | `6fc622874a3ad73a` |
| [ui/widgets/theme_preview.py](../ui/widgets/theme_preview.py) | 4048 | `4ee64041c390991a` |
| [ui/widgets/tool_trail.py](../ui/widgets/tool_trail.py) | 11989 | `dd87851ff72329d9` |
| [ui/widgets/trend_cell.py](../ui/widgets/trend_cell.py) | 5658 | `dcd18b36dbf07c62` |
| [ui/widgets/tutorial_view.py](../ui/widgets/tutorial_view.py) | 9952 | `4e2365c8ca35e117` |
| [ui/widgets/watchlist_panel.py](../ui/widgets/watchlist_panel.py) | 15112 | `8330acd26c1db346` |
| [ui/windows/__init__.py](../ui/windows/__init__.py) | 131 | `2314215bdf54a5fe` |
| [ui/windows/main_window.py](../ui/windows/main_window.py) | 25212 | `4035bd22a06b5e9b` |

## نمایهٔ پایتون و وابستگی‌ها

کلاس‌ها، توابع، متدها و تعریف‌های تو در تو در ترتیب منبع آمده‌اند. `Lx–Ly` محدودهٔ بدنه است. «ارجاع داخلی» واردسازی صریح AST است؛ aliasها و import از بسته‌ها لزوماً مصرف‌کنندهٔ نهایی یک تابع را مشخص نمی‌کنند.

### `ai/__init__.py`

لایه هوش مصنوعی.


### `ai/agent/__init__.py`

عامل تحلیل‌گر هوش مصنوعی.

ارجاع داخلی: `ai/agent/analyst.py`, `ai/agent/autonomous_agent.py`, `ai/agent/chat_agent.py`, `ai/agent/validator.py`.
واردکنندگان ایستا: `app/application.py`.

### `ai/agent/analyst.py`

عامل تحلیل‌گر چند تایم‌فریمی.

ارجاع داخلی: `ai/agent/validator.py`, `ai/prompt_budget.py`, `ai/prompts/__init__.py`, `ai/providers/base.py`, `ai/providers/manager.py`, `ai/recommendation.py`, `ai/tools/__init__.py`, `app/core/constants.py`, `app/core/models.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `ai/agent/__init__.py`, `app/application.py`, `signals/engine.py`, `tests/test_v154_ai_signal.py`, `tests/test_v1911_ai_signal_mode.py`, `tests/test_v195_ai_and_validity.py`.
- `class AnalysisRequest` — L55–L69
- `class AnalysisResult` — L73–L121
- `def AnalysisResult.succeeded` — L100–L102
- `def AnalysisResult.to_dict` — L104–L121
- `class AIAnalyst` — L124–L540
- `def AIAnalyst.__init__` — L132–L152
- `def AIAnalyst.set_risk_parameters` — L154–L159
- `def AIAnalyst._fit_for_model` — L161–L191
- `def AIAnalyst._provider_prompt_budget` — L193–L212
- `async def AIAnalyst.collect_market_data` — L217–L281
- `def AIAnalyst._tools_exchange_name` — L283–L285
- `async def AIAnalyst.analyze` — L290–L369
- `async def AIAnalyst.generate_signal` — L374–L486
- `def AIAnalyst._current_price` — L492–L502
- `def AIAnalyst._risk_context` — L504–L514
- `async def AIAnalyst.quick_check` — L516–L540

### `ai/agent/autonomous_agent.py`

عامل خودمختار تحلیل ارز دیجیتال.

ارجاع داخلی: `ai/agent/validator.py`, `ai/providers/base.py`, `ai/providers/manager.py`, `ai/tools/market_tools.py`, `app/core/constants.py`, `app/core/models.py`, `app/core/timeutil.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `ai/agent/__init__.py`, `tests/test_autonomous_agent.py`, `tests/test_v154_ai_signal.py`, `tests/test_v156_fixes.py`, `tests/test_v1915_bugfixes.py`, `tests/test_v1916_ai_wait.py`, `tests/test_v1917_trust_and_trades.py`, `tests/test_v1918_live_and_auto.py`.
- `class AgentStep` — L56–L71
- `def AgentStep.summary` — L66–L71
- `class AgentOutcome` — L75–L122
- `def AgentOutcome.direction` — L91–L93
- `def AgentOutcome.confidence` — L96–L101
- `def AgentOutcome.to_dict` — L103–L122
- `class AutonomousAgent` — L217–L963
- `def AutonomousAgent.__init__` — L229–L249
- `def AutonomousAgent.set_risk_parameters` — L251–L258
- `def AutonomousAgent.set_progress_callback` — L260–L267
- `def AutonomousAgent._emit` — L269–L276
- `async def AutonomousAgent.run` — L281–L328
- `async def AutonomousAgent._loop` — L330–L539
- `def AutonomousAgent._loop.remaining` — L389–L400
- `async def AutonomousAgent._force_final` — L541–L588
- `def AutonomousAgent._parse` — L594–L626
- `def AutonomousAgent._repair_json` — L629–L684
- `def AutonomousAgent._observation` — L687–L701
- `async def AutonomousAgent._preload_evidence` — L703–L748
- `async def AutonomousAgent._preload_evidence.one` — L723–L729
- `def AutonomousAgent._render_tool_data` — L751–L766
- `def AutonomousAgent._format_baseline` — L769–L825
- `def AutonomousAgent._format_baseline._get` — L782–L786
- `def AutonomousAgent._to_validator_schema` — L828–L869
- `def AutonomousAgent._from_validator_schema` — L872–L885
- `def AutonomousAgent._finalise` — L887–L939
- `async def AutonomousAgent.health_check` — L944–L958
- `def AutonomousAgent.minimum_candles` — L961–L963

### `ai/agent/chat_agent.py`

دستیار گفتگوی هوش مصنوعی متصل به داده‌های زنده بازار.

ارجاع داخلی: `ai/agent/stream_extractor.py`, `ai/providers/base.py`, `app/core/timeutil.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `ai/agent/__init__.py`, `tests/test_chat_agent.py`, `tests/test_v153_fixes.py`, `tests/test_v154_ai_signal.py`, `tests/test_v160_ui_polish.py`, `tests/test_v162_chat_streaming.py`, `tests/test_v171_chat_tool_steps.py`.
- `class ChatToolCall` — L96–L108
- `def ChatToolCall.summary` — L104–L108
- `class ChatAction` — L112–L131
- `def ChatAction.to_dict` — L124–L131
- `class ChatReply` — L135–L171
- `def ChatReply.succeeded` — L152–L154
- `def ChatReply.tools_used` — L157–L159
- `def ChatReply.to_dict` — L161–L171
- `class ChatAgent` — L174–L664
- `def ChatAgent.__init__` — L186–L206
- `def ChatAgent.set_risk_parameters` — L211–L215
- `def ChatAgent.set_progress_callback` — L217–L224
- `def ChatAgent.set_stream_callback` — L226–L236
- `def ChatAgent.streaming_enabled` — L239–L241
- `def ChatAgent._emit` — L243–L266
- `def ChatAgent._emit_stream` — L268–L275
- `def ChatAgent.reset` — L277–L280
- `def ChatAgent.history` — L283–L285
- `def ChatAgent.message_count` — L288–L290
- `def ChatAgent._trim_history` — L292–L299
- `async def ChatAgent.send` — L304–L336
- `async def ChatAgent._generate_round` — L338–L381
- `def ChatAgent._generate_round.on_chunk` — L362–L371
- `async def ChatAgent._turn` — L383–L470
- `def ChatAgent._system_prompt` — L475–L487
- `def ChatAgent._with_context` — L508–L523
- `def ChatAgent._strip_internal_blocks` — L533–L547
- `def ChatAgent._strip_fences` — L550–L557
- `def ChatAgent._parse` — L560–L585
- `def ChatAgent._extract_calls` — L587–L615
- `def ChatAgent._extract_action` — L618–L636
- `def ChatAgent._observation` — L639–L648
- `async def ChatAgent.health_check` — L653–L664

### `ai/agent/narrative.py`

نویسندهٔ تحلیل نوشتاری فارسی برای هر سیگنال.

ارجاع داخلی: `ai/providers/base.py`, `app/core/constants.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/application.py`, `tests/test_narrative.py`, `tests/test_v154_ai_signal.py`.
- `def _is_mostly_latin` — L58–L71
- `def _fa` — L74–L89
- `class NarrativeWriter` — L92–L366
- `def NarrativeWriter.__init__` — L101–L111
- `async def NarrativeWriter.write` — L116–L149
- `async def NarrativeWriter._write_with_ai` — L154–L170
- `def NarrativeWriter.build_prompt` — L172–L222
- `def NarrativeWriter._collect_indicators` — L225–L249
- `def NarrativeWriter.template_narrative` — L254–L360
- `def NarrativeWriter._direction_of` — L363–L366

### `ai/agent/reviewer.py`

بازبین سیگنال‌های بسته‌شده.

ارجاع داخلی: `ai/prompt_budget.py`, `ai/providers/base.py`, `app/core/constants.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/application.py`, `tests/test_v195_ai_and_validity.py`.
- `class ReviewResult` — L76–L92
- `def _fmt` — L95–L101
- `def _duration_hours` — L104–L113
- `def normalize_lesson` — L116–L133
- `class SignalReviewer` — L136–L306
- `def SignalReviewer.__init__` — L143–L154
- `def SignalReviewer.set_language` — L156–L158
- `def SignalReviewer.build_prompt` — L163–L192
- `async def SignalReviewer.review` — L197–L257
- `def SignalReviewer._parse` — L260–L283
- `async def SignalReviewer.review_batch` — L288–L306

### `ai/agent/stream_extractor.py`

استخراج تدریجی متن پاسخ از جریانِ ناقص مدل.

واردکنندگان ایستا: `ai/agent/chat_agent.py`, `tests/test_v162_chat_streaming.py`.
- `class StreamingAnswerExtractor` — L28–L228
- `def StreamingAnswerExtractor.__init__` — L39–L41
- `def StreamingAnswerExtractor.feed` — L46–L66
- `def StreamingAnswerExtractor.reset` — L68–L76
- `def StreamingAnswerExtractor.raw` — L82–L84
- `def StreamingAnswerExtractor.visible` — L87–L89
- `def StreamingAnswerExtractor.finish` — L91–L93
- `def StreamingAnswerExtractor._visible_text` — L98–L120
- `def StreamingAnswerExtractor._after_fence` — L123–L135
- `def StreamingAnswerExtractor._extract_answer` — L138–L150
- `def StreamingAnswerExtractor._value_start` — L153–L174
- `def StreamingAnswerExtractor._read_string` — L177–L228

### `ai/agent/validator.py`

اعتبارسنجی و ترمیم خروجی JSON مدل زبانی.

ارجاع داخلی: `app/core/constants.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `ai/agent/__init__.py`, `ai/agent/analyst.py`, `ai/agent/autonomous_agent.py`, `tests/test_ai_validator.py`, `tests/test_v156_fixes.py`.
- `class ValidationOutcome` — L39–L50
- `def ValidationOutcome.error_text` — L48–L50
- `class ResponseValidator` — L53–L333
- `def ResponseValidator.__init__` — L56–L58
- `def ResponseValidator.set_max_leverage` — L60–L62
- `def ResponseValidator.set_min_risk_reward` — L64–L66
- `def ResponseValidator.extract_json` — L72–L100
- `def ResponseValidator.validate_signal` — L105–L210
- `def ResponseValidator._as_float` — L216–L224
- `def ResponseValidator._parse_entry` — L226–L253
- `def ResponseValidator._parse_take_profits` — L255–L274
- `def ResponseValidator._validate_directional` — L277–L313
- `def ResponseValidator._compute_risk_reward` — L316–L325
- `def ResponseValidator.to_signal_direction` — L328–L333

### `ai/local_model_fit.py`

سنجش تناسب مدل محلی با حافظهٔ دستگاه.

واردکنندگان ایستا: `tests/test_v196_fixes.py`, `ui/pages/settings_page.py`.
- `class ModelFit` — L82–L104
- `def ModelFit.is_risky` — L97–L99
- `def ModelFit.reason_key` — L102–L104
- `def is_reasoning_model` — L107–L114
- `def parse_model_size` — L117–L134
- `def evaluate_fit` — L137–L178
- `def suggest_models` — L181–L199

### `ai/ollama_doctor.py`

تشخیص پله‌به‌پلهٔ مشکل اولاما — منطق خالص، بدون Qt و بدون چاپ.

واردکنندگان ایستا: `tests/test_v1910_ollama_doctor.py`, `ui/controllers/main_controller.py`.
- `class StepResult` — L34–L42
- `class DoctorReport` — L46–L91
- `def DoctorReport.first_failure` — L56–L61
- `def DoctorReport.verdict_key` — L64–L75
- `def DoctorReport.cpu_offload_detected` — L78–L91
- `def _steps` — L94–L117
- `async def run_diagnosis` — L120–L193
- `def _error_text` — L196–L206

### `ai/prompt_budget.py`

بودجه‌بندی اندازهٔ پرامپت بر پایهٔ توان واقعی مدل.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `ai/agent/analyst.py`, `ai/agent/reviewer.py`, `ai/providers/ollama_provider.py`, `tests/test_v1910_ollama_doctor.py`, `tests/test_v195_ai_and_validity.py`, `ui/pages/settings_page.py`.
- `class BudgetResult` — L84–L110
- `def BudgetResult.note` — L100–L110
- `def estimate_tokens` — L113–L120
- `def estimate_payload_tokens` — L123–L125
- `def compact_json` — L128–L136
- `def safe_context_for_memory` — L139–L152
- `def detect_total_memory_gb` — L155–L199
- `class detect_total_memory_gb.MemoryStatus : ctypes.Structure` — L177–L190
- `def choose_context_window` — L202–L215
- `def available_prompt_tokens` — L218–L225
- `def shrink_market_data` — L233–L305
- `def _timeframes_by_importance` — L316–L328
- `def strip_reasoning_block` — L331–L373

### `ai/prompts/__init__.py`

موتور Prompt.

ارجاع داخلی: `ai/prompts/prompt_manager.py`.
واردکنندگان ایستا: `ai/agent/analyst.py`, `app/application.py`, `tests/test_v195_ai_and_validity.py`.

### `ai/prompts/prompt_manager.py`

مدیریت قالب‌های Prompt نسخه‌بندی‌شده.

ارجاع داخلی: `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `ai/prompts/__init__.py`.
- `class PromptTemplate` — L31–L56
- `def PromptTemplate.identifier` — L40–L42
- `def PromptTemplate.render` — L44–L56
- `class PromptManager` — L59–L143
- `def PromptManager.__init__` — L69–L72
- `def PromptManager.reload` — L74–L110
- `def PromptManager.get` — L112–L128
- `def PromptManager.render` — L130–L132
- `def PromptManager.available` — L134–L136
- `def PromptManager.latest_versions` — L138–L143

### `ai/providers/__init__.py`

ارائه‌دهندگان هوش مصنوعی.

ارجاع داخلی: `ai/providers/base.py`, `ai/providers/catalog.py`, `ai/providers/free_models.py`, `ai/providers/manager.py`, `ai/providers/ollama_provider.py`, `ai/providers/openai_compatible.py`.
واردکنندگان ایستا: `app/application.py`, `tests/test_autonomous_agent.py`, `tests/test_icons_search_theme.py`.

### `ai/providers/base.py`

واسط انتزاعی ارائه‌دهنده هوش مصنوعی.

واردکنندگان ایستا: `ai/agent/analyst.py`, `ai/agent/autonomous_agent.py`, `ai/agent/chat_agent.py`, `ai/agent/narrative.py`, `ai/agent/reviewer.py`, `ai/providers/__init__.py`, `ai/providers/manager.py`, `ai/providers/ollama_provider.py`, `ai/providers/omniroute_provider.py`, `ai/providers/openai_compatible.py`, `app/application.py`, `tests/test_ai_providers.py`, `tests/test_autonomous_agent.py`, `tests/test_chat_agent.py`, `tests/test_v154_ai_signal.py`, `tests/test_v156_fixes.py`, `tests/test_v161_omniroute_font_theme.py`, `tests/test_v162_chat_streaming.py`, `tests/test_v190_account_and_auto_scan.py`, `tests/test_v1913_ashna.py`, `tests/test_v196_fixes.py`, `trading/scalp_service.py`.
- `class AIProviderConfig` — L22–L39
- `class AIMessage` — L43–L51
- `def AIMessage.to_dict` — L49–L51
- `class AIResponse` — L55–L74
- `def AIResponse.is_empty` — L72–L74
- `class AIProvider : ABC` — L77–L183
- `def AIProvider.__init__` — L86–L88
- `def AIProvider.name` — L91–L93
- `def AIProvider.model` — L96–L98
- `def AIProvider.config` — L101–L103
- `def AIProvider.has_api_key` — L106–L108
- `def AIProvider.set_api_key` — L110–L112
- `def AIProvider.update_config` — L114–L116
- `async def AIProvider.is_available` — L119–L124
- `async def AIProvider.generate` — L127–L135
- `async def AIProvider.list_models` — L138–L139
- `def AIProvider.supports_streaming` — L145–L152
- `async def AIProvider.stream` — L154–L176
- `async def AIProvider.close` — L178–L180
- `def AIProvider.__repr__` — L182–L183

### `ai/providers/catalog.py`

فهرست ارائه‌دهنده‌های هوش مصنوعی پشتیبانی‌شده.

واردکنندگان ایستا: `ai/providers/__init__.py`, `app/application.py`, `tests/test_v161_omniroute_font_theme.py`, `tests/test_v1913_ashna.py`, `tests/test_v1920_ashna_settings.py`, `ui/pages/settings_page.py`.
- `class ProviderPreset` — L18–L54
- `def ProviderPreset.key_field_enabled` — L52–L54
- `def get_preset` — L263–L265
- `def preset_keys` — L268–L270
- `def local_presets` — L273–L275
- `def keyless_presets` — L278–L280

### `ai/providers/free_models.py`

تفکیک مدل‌های رایگان از مدل‌های پولی.

واردکنندگان ایستا: `ai/providers/__init__.py`, `tests/test_ai_providers.py`, `ui/pages/settings_page.py`.
- `def _tokens` — L83–L85
- `def _is_small` — L88–L92
- `class ModelInfo` — L96–L117
- `def ModelInfo.is_free` — L109–L111
- `def ModelInfo.label` — L113–L117
- `def classify_model` — L120–L152
- `def sort_models` — L155–L163
- `def free_models` — L166–L168
- `def pick_default_model` — L171–L179
- `def known_free_models` — L215–L217

### `ai/providers/manager.py`

مدیر ارائه‌دهندگان هوش مصنوعی و زنجیره جایگزینی (Fallback).

ارجاع داخلی: `ai/providers/base.py`, `ai/providers/ollama_provider.py`, `ai/providers/omniroute_provider.py`, `ai/providers/openai_compatible.py`, `app/core/events.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `ai/agent/analyst.py`, `ai/agent/autonomous_agent.py`, `ai/providers/__init__.py`, `tests/test_autonomous_agent.py`, `tests/test_v161_omniroute_font_theme.py`, `tests/test_v162_chat_streaming.py`.
- `class AIProviderManager` — L41–L345
- `def AIProviderManager.__init__` — L51–L57
- `def AIProviderManager.register` — L62–L77
- `def AIProviderManager.register_from_type` — L79–L88
- `def AIProviderManager.unregister` — L90–L93
- `def AIProviderManager.get` — L95–L97
- `def AIProviderManager.set_api_key` — L99–L103
- `def AIProviderManager.set_fallback_enabled` — L105–L107
- `def AIProviderManager.has_providers` — L113–L115
- `def AIProviderManager.last_used_provider` — L118–L120
- `def AIProviderManager.ordered_providers` — L122–L139
- `def AIProviderManager.active_provider` — L141–L157
- `async def AIProviderManager.check_all` — L159–L169
- `async def AIProviderManager.generate` — L174–L246
- `async def AIProviderManager.stream` — L248–L319
- `def AIProviderManager.stream.collect` — L278–L281
- `def AIProviderManager._reset_stream` — L322–L332
- `def AIProviderManager.last_errors` — L335–L337
- `async def AIProviderManager.close` — L339–L345

### `ai/providers/ollama_provider.py`

ارائه‌دهنده مدل محلی Ollama.

ارجاع داخلی: `ai/prompt_budget.py`, `ai/providers/base.py`, `ai/providers/ranking.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `ai/providers/__init__.py`, `ai/providers/manager.py`, `tests/test_ai_providers.py`, `tests/test_v153_fixes.py`, `tests/test_v156_fixes.py`, `tests/test_v190_account_and_auto_scan.py`, `tests/test_v196_fixes.py`.
- `def _is_runner_crash` — L141–L164
- `def _response_error` — L167–L183
- `def _looks_like_memory` — L186–L189
- `def host_candidates` — L192–L225
- `def model_matches` — L228–L243
- `class OllamaProvider : AIProvider` — L246–L973
- `def OllamaProvider.__init__` — L257–L278
- `async def OllamaProvider._resolve_base_url` — L283–L309
- `async def OllamaProvider._get_client` — L311–L323
- `async def OllamaProvider.installed_models` — L328–L342
- `async def OllamaProvider.resolve_model` — L344–L374
- `def OllamaProvider.update_config` — L376–L381
- `def OllamaProvider.active_model` — L384–L386
- `async def OllamaProvider.is_available` — L391–L413
- `async def OllamaProvider.generate` — L418–L438
- `async def OllamaProvider._generate_once` — L440–L656
- `def OllamaProvider._fit_messages` — L658–L738
- `def OllamaProvider._describe_http_error` — L740–L773
- `def OllamaProvider._is_memory_error` — L775–L777
- `def OllamaProvider._memory_ceiling` — L779–L807
- `def OllamaProvider.prompt_token_budget` — L809–L820
- `def OllamaProvider._needed_context` — L822–L832
- `def OllamaProvider._reply_budget` — L834–L870
- `def OllamaProvider._sticky_context` — L872–L917
- `def OllamaProvider._context_override` — L919–L924
- `def OllamaProvider._effective_window` — L926–L940
- `def OllamaProvider._num_ctx` — L942–L960
- `async def OllamaProvider.list_models` — L962–L967
- `async def OllamaProvider.close` — L969–L973

### `ai/providers/omniroute_provider.py`

ارائه‌دهنده OmniRoute — دروازهٔ چندسرویسی هوش مصنوعی.

ارجاع داخلی: `ai/providers/base.py`, `ai/providers/openai_compatible.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `ai/providers/manager.py`, `ai/tools/omniroute_tools.py`, `app/application.py`, `tests/test_v161_omniroute_font_theme.py`.
- `def model_vendor` — L87–L100
- `class OmniRouteProvider : OpenAICompatibleProvider` — L103–L228
- `def OmniRouteProvider.__init__` — L118–L125
- `def OmniRouteProvider.last_listing_ok` — L128–L136
- `def OmniRouteProvider._headers` — L141–L155
- `async def OmniRouteProvider.is_available` — L160–L194
- `async def OmniRouteProvider.list_models` — L199–L216
- `async def OmniRouteProvider.list_models_detailed` — L218–L228

### `ai/providers/openai_compatible.py`

ارائه‌دهنده سازگار با API استاندارد OpenAI.

ارجاع داخلی: `ai/providers/base.py`, `ai/providers/ranking.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `ai/providers/__init__.py`, `ai/providers/manager.py`, `ai/providers/omniroute_provider.py`, `tests/test_ai_providers.py`, `tests/test_v153_fixes.py`, `tests/test_v156_fixes.py`, `tests/test_v162_chat_streaming.py`, `tests/test_v1913_ashna.py`.
- `def uses_completion_tokens` — L49–L57
- `class OpenAICompatibleProvider : AIProvider` — L60–L529
- `def OpenAICompatibleProvider.__init__` — L71–L75
- `async def OpenAICompatibleProvider._get_client` — L77–L92
- `def OpenAICompatibleProvider._is_local` — L95–L101
- `def OpenAICompatibleProvider._headers` — L103–L113
- `def OpenAICompatibleProvider.update_config` — L115–L118
- `def OpenAICompatibleProvider._error_text` — L124–L149
- `def OpenAICompatibleProvider._raise_for_status` — L151–L197
- `async def OpenAICompatibleProvider.is_available` — L202–L225
- `def OpenAICompatibleProvider._build_payload` — L230–L250
- `def OpenAICompatibleProvider._adapt_to_error` — L252–L271
- `async def OpenAICompatibleProvider.generate` — L273–L341
- `def OpenAICompatibleProvider.supports_streaming` — L347–L349
- `async def OpenAICompatibleProvider.stream` — L351–L447
- `def OpenAICompatibleProvider._parse_sse_line` — L450–L500
- `async def OpenAICompatibleProvider.list_models` — L502–L523
- `async def OpenAICompatibleProvider.close` — L525–L529

### `ai/providers/ranking.py`

رتبه‌بندی مدل‌های هوش مصنوعی بر اساس توان تحلیل.

واردکنندگان ایستا: `ai/providers/ollama_provider.py`, `ai/providers/openai_compatible.py`, `tests/test_v156_fixes.py`.
- `def is_free_model` — L71–L73
- `def score_model` — L76–L117
- `def _vendor` — L120–L123
- `def sort_models` — L126–L150

### `ai/recommendation.py`

استخراج توصیهٔ صریح خرید/فروش از پاسخ هوش مصنوعی.

واردکنندگان ایستا: `ai/agent/analyst.py`, `tests/test_v195_ai_and_validity.py`, `ui/controllers/main_controller.py`.
- `class Recommendation` — L71–L95
- `def Recommendation.is_actionable` — L85–L87
- `def Recommendation.to_dict` — L89–L95
- `def normalize_action` — L98–L114
- `def _parse_confidence` — L117–L133
- `def parse_recommendation` — L136–L162
- `def strip_recommendation_line` — L165–L174

### `ai/speed_profile.py`

پروفایل سرعت هوش مصنوعی.

واردکنندگان ایستا: `app/application.py`, `tests/test_v1922_micro_speed.py`.
- `class SpeedProfile` — L15–L23
- `def resolve_profile` — L33–L36
- `def _read` — L39–L48
- `def _read_int` — L51–L56
- `def limits_for` — L59–L76
- `def signal_timeout_seconds` — L79–L81

### `ai/tools/__init__.py`

ابزارهای عامل هوش مصنوعی.

ارجاع داخلی: `ai/tools/composite.py`, `ai/tools/market_tools.py`, `ai/tools/omniroute_tools.py`.
واردکنندگان ایستا: `ai/agent/analyst.py`, `app/application.py`, `tests/test_v161_omniroute_font_theme.py`.

### `ai/tools/composite.py`

ترکیب چند مجموعه‌ابزار در یک واسط واحد.

ارجاع داخلی: `ai/tools/market_tools.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `ai/tools/__init__.py`.
- `class Toolset : Protocol` — L32–L47
- `def Toolset.tool_names` — L36–L38
- `async def Toolset.execute` — L40–L42
- `def Toolset.get_definitions` — L45–L47
- `class CompositeToolset` — L50–L152
- `def CompositeToolset.__init__` — L59–L60
- `def CompositeToolset.add` — L65–L68
- `def CompositeToolset.toolsets` — L71–L73
- `def CompositeToolset.tool_names` — L76–L83
- `def CompositeToolset._owner` — L85–L90
- `def CompositeToolset.get_definitions` — L95–L118
- `async def CompositeToolset.execute` — L120–L125
- `def CompositeToolset.set_risk_parameters` — L130–L140
- `def CompositeToolset.__getattr__` — L142–L152

### `ai/tools/market_tools.py`

جعبه‌ابزار داده بازار برای عامل هوش مصنوعی.

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`, `indicators/engine.py`, `indicators/support_resistance.py`, `market/engine.py`, `signals/forecast.py`.
واردکنندگان ایستا: `ai/agent/autonomous_agent.py`, `ai/tools/__init__.py`, `ai/tools/composite.py`, `ai/tools/omniroute_tools.py`, `tests/test_autonomous_agent.py`, `tests/test_prediction_ui_and_tools.py`, `tests/test_v161_omniroute_font_theme.py`, `tests/test_v171_chat_tool_steps.py`, `tests/test_v1917_forecast.py`.
- `class ToolDefinition` — L38–L65
- `def ToolDefinition.to_openai_schema` — L50–L65
- `class ToolResult` — L69–L96
- `def ToolResult.to_dict` — L84–L96
- `class MarketToolset` — L99–L650
- `def MarketToolset.__init__` — L108–L148
- `async def MarketToolset.get_engine_signal` — L150–L180
- `async def MarketToolset.forecast_next_timeframe` — L182–L197
- `async def MarketToolset.get_prediction_report` — L199–L223
- `async def MarketToolset.get_prediction_accuracy` — L225–L239
- `def MarketToolset.set_risk_parameters` — L241–L243
- `def MarketToolset.tool_names` — L249–L251
- `async def MarketToolset.execute` — L253–L279
- `async def MarketToolset.get_current_price` — L284–L287
- `async def MarketToolset.get_ticker` — L289–L292
- `async def MarketToolset.get_ohlcv` — L294–L321
- `async def MarketToolset.get_multi_timeframe_data` — L323–L349
- `async def MarketToolset.calculate_indicator` — L354–L362
- `async def MarketToolset.calculate_multiple_indicators` — L364–L377
- `async def MarketToolset.get_volume` — L379–L403
- `async def MarketToolset.get_orderbook` — L405–L429
- `async def MarketToolset.detect_trend_tool` — L434–L444
- `async def MarketToolset.detect_market_structure` — L446–L454
- `async def MarketToolset.find_support_resistance_tool` — L456–L477
- `async def MarketToolset.calculate_risk` — L482–L540
- `def MarketToolset.get_definitions` — L546–L650

### `ai/tools/omniroute_tools.py`

ابزارهای دروازهٔ OmniRoute برای عامل هوش مصنوعی.

ارجاع داخلی: `ai/providers/omniroute_provider.py`, `ai/tools/market_tools.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `ai/tools/__init__.py`.
- `class OmniRouteToolset` — L45–L212
- `def OmniRouteToolset.__init__` — L57–L68
- `def OmniRouteToolset.tool_names` — L74–L76
- `async def OmniRouteToolset.execute` — L78–L96
- `def OmniRouteToolset._provider` — L101–L105
- `async def OmniRouteToolset.gateway_status` — L107–L137
- `async def OmniRouteToolset.list_gateway_models` — L139–L185
- `def OmniRouteToolset.get_definitions` — L191–L212

### `app/__init__.py`

بسته اصلی هسته نرم‌افزار Crypto AI Trader.


### `app/application.py`

هماهنگ‌کننده اصلی برنامه (Composition Root).

ارجاع داخلی: `ai/agent/__init__.py`, `ai/agent/analyst.py`, `ai/agent/narrative.py`, `ai/agent/reviewer.py`, `ai/prompts/__init__.py`, `ai/providers/__init__.py`, `ai/providers/base.py`, `ai/providers/catalog.py`, `ai/providers/omniroute_provider.py`, `ai/speed_profile.py`, `ai/tools/__init__.py`, `app/config/settings_service.py`, `app/core/auth_service.py`, `app/core/constants.py`, `app/core/email_service.py`, `app/core/events.py`, `app/core/exchange_account_service.py`, `app/core/models.py`, `app/core/password_reset.py`, `app/core/paths.py`, `app/database/repositories/__init__.py`, `app/database/session.py`, `app/logging/__init__.py`, `app/security/db_backend.py`, `app/security/secret_store.py`, `backup/__init__.py`, `indicators/__init__.py`, `indicators/registry.py`, `market/engine.py`, `market/providers/registry.py`, `reports/__init__.py`, `signals/__init__.py`, `signals/outcome_tracker.py`, `signals/prediction/engine.py`, `signals/prediction/store.py`, `signals/scanner.py`, `signals/scorecard.py`, `signals/strategies/registry.py`.
واردکنندگان ایستا: `main.py`, `tests/test_exchange_login_flow.py`, `tests/test_exchange_switching.py`, `tests/test_icons_search_theme.py`, `tests/test_v154_security_money.py`, `tests/test_v155_ui_and_ai.py`, `tests/test_v156_fixes.py`, `tests/test_v1911_ai_signal_mode.py`, `tests/test_v1918_live_and_auto.py`, `tests/test_v1918_scorecard.py`, `tools/preview_shot.py`, `tools/set_ai_key.py`, `tools/sweep_ui.py`, `ui/controllers/main_controller.py`.
- `def _as_float` — L65–L72
- `class Application` — L75–L1251
- `def Application.__init__` — L86–L169
- `def Application.prediction_engine` — L175–L217
- `def Application.prediction_engine.lookup_price` — L192–L208
- `def Application.invalidate_prediction_engine` — L219–L221
- `def Application.risk_parameters` — L223–L229
- `def Application.apply_risk_settings` — L231–L238
- `async def Application.start` — L243–L262
- `async def Application.switch_exchange` — L264–L326
- `async def Application.stop` — L328–L334
- `def Application.ai_enabled` — L339–L341
- `def Application.ai_analyst` — L343–L434
- `def Application._register_fallback_providers` — L436–L473
- `def Application._resolve_base_url` — L476–L501
- `def Application._resolve_base_url._is_local` — L490–L492
- `def Application._omniroute_provider` — L503–L536
- `def Application._provider_extra` — L538–L549
- `def Application._ai_api_key` — L551–L564
- `def Application.exchange_credentials` — L566–L578
- `def Application.ai_speed_limits` — L581–L585
- `def Application.signal_ai_timeout` — L587–L591
- `def Application.autonomous_agent` — L593–L625
- `def Application.chat_agent` — L627–L661
- `def Application.reset_ai` — L663–L678
- `async def Application.list_ai_models` — L680–L709
- `async def Application.generate_signal` — L714–L783
- `async def Application.scan_market` — L785–L837
- `async def Application.score_forecasts` — L842–L916
- `def Application._track_outcome` — L918–L933
- `async def Application.refresh_outcomes` — L935–L988
- `async def Application.review_closed_signals` — L990–L1055
- `async def Application._outcome_prices` — L1057–L1091
- `async def Application.analyze_scanned_signal` — L1093–L1115
- `async def Application._apply_ai_decision` — L1117–L1221
- `async def Application._write_narrative` — L1223–L1243
- `def Application.create_backup` — L1245–L1251

### `app/config/__init__.py`

ماژول پیکربندی نرم‌افزار.

ارجاع داخلی: `app/config/defaults.py`, `app/config/settings.py`, `app/config/settings_service.py`.

### `app/config/defaults.py`

تعریف کلیدها و مقادیر پیش‌فرض تنظیمات کاربر.

واردکنندگان ایستا: `app/config/__init__.py`, `app/config/settings_service.py`, `tests/test_settings_expanded.py`, `tests/test_v155_ui_and_ai.py`, `tests/test_v162_chat_streaming.py`, `tests/test_v170_scanner_fonts_theme.py`, `tests/test_v172_signal_ai_and_scan_ui.py`, `tests/test_v180_arrangeable_layout.py`, `tests/test_v190_account_and_auto_scan.py`, `tests/test_v1917_forecast.py`, `tests/test_v1918_alerts.py`, `tests/test_v191_outcome_tracking.py`, `tests/test_v195_ai_and_validity.py`, `tests/test_v196_fixes.py`, `ui/controllers/main_controller.py`.
- `class SettingKey : str, Enum` — L21–L280

### `app/config/settings.py`

تنظیمات پایه و محیطی نرم‌افزار مبتنی بر Pydantic Settings.

ارجاع داخلی: `app/core/constants.py`, `app/core/paths.py`.
واردکنندگان ایستا: `app/config/__init__.py`, `app/database/session.py`.
- `class AppSettings : BaseSettings` — L25–L85
- `def AppSettings._validate_log_level` — L65–L70
- `def AppSettings.effective_database_url` — L73–L80
- `def AppSettings.is_development` — L83–L85
- `def get_app_settings` — L89–L96

### `app/config/settings_service.py`

سرویس تنظیمات کاربر: لایه‌ای بالاتر از SettingsRepository.

ارجاع داخلی: `app/config/defaults.py`, `app/core/constants.py`, `app/core/events.py`, `app/core/models.py`, `app/database/repositories/settings_repository.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/application.py`, `app/config/__init__.py`, `app/core/auth_service.py`, `tests/test_auth.py`, `tests/test_backup.py`, `tests/test_v172_signal_ai_and_scan_ui.py`.
- `class SettingsService` — L31–L261
- `def SettingsService.__init__` — L40–L44
- `def SettingsService.initialize_defaults` — L49–L59
- `def SettingsService._repair_stale_defaults` — L74–L94
- `def SettingsService.reload` — L96–L100
- `def SettingsService.get` — L105–L120
- `def SettingsService.get_int` — L122–L128
- `def SettingsService.get_float` — L130–L136
- `def SettingsService.get_bool` — L138–L145
- `def SettingsService.get_list` — L147–L150
- `def SettingsService.get_dict` — L152–L155
- `def SettingsService.set` — L160–L180
- `def SettingsService.set_many` — L182–L189
- `def SettingsService._category_for` — L192–L197
- `def SettingsService.language` — L203–L209
- `def SettingsService.theme` — L212–L218
- `def SettingsService.is_first_run_completed` — L221–L223
- `def SettingsService.mark_first_run_completed` — L225–L227
- `def SettingsService.active_exchange` — L230–L232
- `def SettingsService.analysis_timeframes` — L235–L237
- `def SettingsService.timeframe_roles` — L240–L242
- `def SettingsService.get_risk_parameters` — L244–L257
- `def SettingsService.export_all` — L259–L261

### `app/core/__init__.py`

هسته مشترک نرم‌افزار: مسیرها، ثابت‌ها، مدل‌های داده‌ای پایه و گذرگاه رویداد.

واردکنندگان ایستا: `tests/test_v156_fixes.py`.

### `app/core/auth_service.py`

سرویس احراز هویت و مدیریت کاربر.

ارجاع داخلی: `app/config/settings_service.py`, `app/database/repositories/user_repository.py`, `app/logging/__init__.py`, `app/security/passwords.py`.
واردکنندگان ایستا: `app/application.py`, `tests/test_auth.py`, `tests/test_v162_chat_streaming.py`, `tests/test_v180_arrangeable_layout.py`.
- `class AuthService` — L53–L348
- `def AuthService.__init__` — L63–L75
- `def AuthService.current_user` — L81–L83
- `def AuthService.is_authenticated` — L86–L88
- `def AuthService.user_id` — L91–L93
- `def AuthService.display_name` — L96–L105
- `def AuthService.has_users` — L108–L110
- `def AuthService.add_listener` — L112–L120
- `def AuthService.register` — L125–L158
- `def AuthService.login` — L160–L173
- `def AuthService.logout` — L175–L189
- `def AuthService.restore_session` — L191–L209
- `def AuthService.update_profile` — L214–L226
- `def AuthService.change_password` — L228–L247
- `def AuthService.sessions` — L249–L253
- `def AuthService.revoke_session` — L255–L257
- `def AuthService.revoke_other_sessions` — L259–L265
- `def AuthService.preference` — L270–L281
- `def AuthService.set_preference` — L283–L295
- `def AuthService.set_preferences` — L297–L300
- `def AuthService._activate` — L305–L316
- `def AuthService._apply_preferences` — L318–L328
- `def AuthService._snapshot_preferences` — L330–L332
- `def AuthService._device_label` — L334–L339
- `def AuthService._notify` — L341–L348

### `app/core/constants.py`

ثابت‌های سراسری نرم‌افزار.

واردکنندگان ایستا: `ai/agent/analyst.py`, `ai/agent/autonomous_agent.py`, `ai/agent/narrative.py`, `ai/agent/reviewer.py`, `ai/agent/validator.py`, `ai/tools/market_tools.py`, `app/application.py`, `app/config/settings.py`, `app/config/settings_service.py`, `app/core/models.py`, `app/core/updater.py`, `app/database/repositories/symbol_repository.py`, `app/security/secret_store.py`, `backup/manager.py`, `indicators/engine.py`, `indicators/support_resistance.py`, `indicators/trend.py`, `localization/translator.py`, `main.py`, `market/engine.py`, `market/live_feed.py`, `market/providers/base.py`, `market/providers/lbank/provider.py`, `market/providers/lbank/websocket_client.py`, `market/providers/toobit/provider.py`, `market/providers/toobit/websocket_client.py`, `reports/builder.py`, `signals/engine.py`, `signals/forecast.py`, `signals/risk_engine.py`, `signals/scanner.py`, `signals/strategies/base.py`, `signals/strategies/breakout.py`, `signals/strategies/trend_following.py`, `signals/strategies/volatility_regime.py`, `tests/test_reports.py`, `tests/test_risk_engine.py`, `tests/test_signal_engine.py`, `tests/test_v154_packaging.py`, `tests/test_v155_ui_and_ai.py`, `tests/test_v160_ui_polish.py`, `tests/test_v161_omniroute_font_theme.py`, `tests/test_v162_toobit_websocket.py`, `tests/test_v170_scanner_fonts_theme.py`, `tests/test_v1911_ai_signal_mode.py`, `tests/test_v1911_build_and_update.py`, `tests/test_v1917_forecast.py`, `tests/test_v191_outcome_tracking.py`, `tests/test_v195_ai_and_validity.py`, `ui/controllers/main_controller.py`, `ui/dialogs/first_run_wizard.py`, `ui/themes/theme_manager.py`, `ui/widgets/watchlist_panel.py`, `ui/windows/main_window.py`.
- `class Language : str, Enum` — L38–L47
- `def Language.is_rtl` — L45–L47
- `class Theme : str, Enum` — L50–L73
- `class ConnectionStatus : str, Enum` — L76–L83
- `class SignalDirection : str, Enum` — L86–L95
- `class TrendDirection : str, Enum` — L98–L103
- `class MarketStructureType : str, Enum` — L106–L118
- `class AnalysisStatus : str, Enum` — L121–L126
- `class NotificationLevel : str, Enum` — L129–L135

### `app/core/email_service.py`

ارسال ایمیل از طریق SMTP کاربر.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `app/application.py`, `app/core/password_reset.py`, `tests/test_v190_account_and_auto_scan.py`, `ui/dialogs/auth_dialog.py`, `ui/pages/settings_page.py`.
- `def is_valid_email` — L58–L60
- `def mask_email` — L63–L79
- `class SmtpConfig` — L83–L102
- `def SmtpConfig.configured` — L95–L97
- `def SmtpConfig.from_address` — L100–L102
- `class EmailService` — L105–L252
- `def EmailService.__init__` — L113–L115
- `def EmailService.config` — L120–L131
- `def EmailService.configured` — L134–L136
- `def EmailService._password` — L138–L146
- `def EmailService.set_password` — L148–L155
- `def EmailService.send` — L160–L196
- `def EmailService._deliver` — L198–L221
- `def EmailService.test_connection` — L223–L252

### `app/core/events.py`

گذرگاه رویداد داخلی (Event Bus) برای ارتباط سست بین ماژول‌ها.

واردکنندگان ایستا: `ai/providers/manager.py`, `app/application.py`, `app/config/settings_service.py`, `market/engine.py`, `market/resilience.py`.
- `class EventType : str, Enum` — L28–L59
- `class Event` — L63–L68
- `class EventBus` — L74–L118
- `def EventBus.__init__` — L82–L84
- `def EventBus.subscribe` — L86–L92
- `def EventBus.unsubscribe` — L94–L100
- `def EventBus.publish` — L102–L113
- `def EventBus.clear` — L115–L118

### `app/core/exchange_account_service.py`

سرویس حساب‌های صرافی کاربر.

ارجاع داخلی: `app/database/repositories/user_repository.py`, `app/logging/__init__.py`, `app/security/passwords.py`, `app/security/secret_store.py`.
واردکنندگان ایستا: `app/application.py`, `tests/test_auth.py`, `tests/test_v156_fixes.py`.
- `def _sanitize` — L35–L46
- `class ExchangeAccountService` — L49–L355
- `def ExchangeAccountService.__init__` — L58–L64
- `def ExchangeAccountService.list_accounts` — L69–L71
- `def ExchangeAccountService.get_account` — L73–L75
- `def ExchangeAccountService.default_account` — L77–L79
- `def ExchangeAccountService.add_account` — L84–L123
- `def ExchangeAccountService.update_credentials` — L125–L137
- `def ExchangeAccountService.delete_account` — L139–L149
- `def ExchangeAccountService.set_default` — L151–L153
- `def ExchangeAccountService.set_enabled` — L155–L157
- `def ExchangeAccountService.credentials` — L162–L184
- `def ExchangeAccountService.has_credentials` — L186–L188
- `async def ExchangeAccountService.test_connection` — L193–L250
- `async def ExchangeAccountService.sync_balances` — L252–L332
- `def ExchangeAccountService._store_secret` — L337–L355

### `app/core/models.py`

مدل‌های داده‌ای پایه و مستقل از پایگاه داده (Domain Models).

ارجاع داخلی: `app/core/constants.py`.
واردکنندگان ایستا: `ai/agent/analyst.py`, `ai/agent/autonomous_agent.py`, `ai/tools/market_tools.py`, `app/application.py`, `app/config/settings_service.py`, `app/database/repositories/candle_repository.py`, `app/database/repositories/signal_repository.py`, `app/database/repositories/symbol_repository.py`, `indicators/base.py`, `indicators/engine.py`, `indicators/support_resistance.py`, `market/engine.py`, `market/live_feed.py`, `market/providers/base.py`, `market/providers/bitpin/parser.py`, `market/providers/bitpin/provider.py`, `market/providers/lbank/parser.py`, `market/providers/lbank/provider.py`, `market/providers/toobit/parser.py`, `market/providers/toobit/provider.py`, `market/providers/toobit/websocket_client.py`, `market/quality.py`, `market/timeframes.py`, `signals/engine.py`, `signals/prediction/anomaly.py`, `signals/prediction/breakout.py`, `signals/prediction/crossasset.py`, `signals/prediction/distribution.py`, `signals/prediction/engine.py`, `signals/prediction/features.py`, `signals/prediction/regime.py`, `signals/prediction/store.py`, `signals/prediction/volatility.py`, `signals/risk_engine.py`, `signals/scanner.py`, `signals/strategies/base.py`, `tests/conftest.py`, `tests/test_autonomous_agent.py`, `tests/test_prediction_lifecycle.py`, `tests/test_predictive_phase1.py`, `tests/test_predictive_phase2_5.py`, `tests/test_reports.py`, `tests/test_risk_engine.py`, `tests/test_signal_engine.py`, `tests/test_v162_toobit_websocket.py`, `tests/test_v170_scanner_fonts_theme.py`, `tests/test_v1911_ai_signal_mode.py`, `tests/test_v1914_scalp.py`, `tests/test_v1917_forecast.py`, `tests/test_v1917_trust_and_trades.py`, `tests/test_v1918_live_and_auto.py`, `tests/test_v191_outcome_tracking.py`, `tests/test_v192_watchlist.py`, `tests/test_v194_performance.py`, `tests/test_v195_ai_and_validity.py`, `tests/test_v200_event_driven_trading.py`, `trading/scalp_scanner.py`, `ui/charts/candlestick_item.py`, `ui/charts/price_chart.py`, `ui/controllers/main_controller.py`.
- `def utc_now` — L29–L31
- `class Candle` — L35–L69
- `def Candle.datetime_utc` — L51–L53
- `def Candle.is_bullish` — L56–L58
- `def Candle.to_dict` — L60–L69
- `class Ticker` — L73–L101
- `def Ticker.to_dict` — L90–L101
- `class OrderBookLevel` — L105–L109
- `class OrderBook` — L113–L141
- `def OrderBook.best_bid` — L127–L129
- `def OrderBook.best_ask` — L132–L134
- `def OrderBook.spread` — L137–L141
- `class SymbolInfo` — L145–L160
- `class IndicatorResult` — L164–L194
- `def IndicatorResult.to_summary` — L181–L194
- `class SupportResistanceLevel` — L198–L205
- `class MarketStructure` — L209–L235
- `def MarketStructure.to_dict` — L225–L235
- `class TimeframeAnalysis` — L239–L273
- `def TimeframeAnalysis.to_summary` — L252–L273
- `class MarketSnapshot` — L277–L319
- `def MarketSnapshot.current_price` — L294–L301
- `def MarketSnapshot.to_payload` — L303–L319
- `class RiskParameters` — L323–L335
- `class RiskAssessment` — L339–L350
- `class TradingSignal` — L354–L428
- `def TradingSignal.to_dict` — L399–L428

### `app/core/password_reset.py`

بازیابی رمز عبور با کد تأیید.

ارجاع داخلی: `app/core/email_service.py`, `app/logging/__init__.py`, `app/security/passwords.py`.
واردکنندگان ایستا: `app/application.py`, `tests/test_v190_account_and_auto_scan.py`.
- `def generate_code` — L50–L57
- `class ResetRequest` — L61–L83
- `def ResetRequest.__post_init__` — L71–L73
- `def ResetRequest.expired` — L76–L78
- `def ResetRequest.exhausted` — L81–L83
- `class PasswordResetService` — L86–L258
- `def PasswordResetService.__init__` — L95–L101
- `def PasswordResetService.request_code` — L106–L167
- `def PasswordResetService._compose` — L169–L181
- `def PasswordResetService.verify_code` — L186–L209
- `def PasswordResetService.reset_password` — L214–L238
- `def PasswordResetService.cancel` — L243–L246
- `def PasswordResetService.pending` — L248–L251
- `def PasswordResetService.purge_expired` — L253–L258

### `app/core/paths.py`

مدیریت متمرکز مسیرهای فایل و پوشه‌های نرم‌افزار.

واردکنندگان ایستا: `app/application.py`, `app/config/settings.py`, `app/security/db_backend.py`, `app/security/secret_store.py`, `backup/manager.py`, `migrations/env.py`, `reports/exporters.py`, `tests/conftest.py`, `tests/test_backup.py`, `tests/test_exchange_login_flow.py`, `tests/test_exchange_switching.py`, `tests/test_reports.py`, `tests/test_v154_security_money.py`, `ui/controllers/main_controller.py`.
- `def is_frozen` — L21–L25
- `def get_base_dir` — L28–L37
- `def get_data_dir` — L40–L50
- `class AppPaths` — L53–L104
- `def AppPaths.__init__` — L61–L80
- `def AppPaths.ensure` — L82–L94
- `def AppPaths.database_url` — L97–L101
- `def AppPaths.__repr__` — L103–L104

### `app/core/timeutil.py`

کار با زمان و منطقه زمانی.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `ai/agent/autonomous_agent.py`, `ai/agent/chat_agent.py`, `market/fiat_rates.py`, `market/live_feed.py`, `market/resilience.py`, `signals/paper_trader.py`, `ui/controllers/main_controller.py`, `ui/windows/main_window.py`.
- `def set_display_timezone` — L31–L47
- `def local_timezone` — L50–L55
- `def now_utc` — L58–L60
- `def now_local` — L63–L65
- `def to_local` — L68–L79
- `def format_datetime` — L82–L85
- `def format_time` — L88–L90
- `def format_timestamp` — L93–L100
- `def utc_offset_label` — L103–L113
- `def timezone_name` — L116–L120
- `def relative_label` — L123–L142

### `app/core/updater.py`

ربات به‌روزرسانی — رساندن نسخهٔ نصب‌شده روی دسکتاپ به آخرین نسخه.

ارجاع داخلی: `app/core/constants.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `tests/test_v1911_build_and_update.py`, `ui/controllers/main_controller.py`.
- `class UpdateInfo` — L45–L57
- `def UpdateInfo.usable` — L55–L57
- `def parse_version` — L60–L69
- `def is_newer` — L72–L74
- `def parse_manifest` — L77–L91
- `def verify_checksum` — L94–L112
- `class UpdateChecker` — L115–L218
- `def UpdateChecker.__init__` — L124–L125
- `def UpdateChecker.is_remote` — L128–L130
- `async def UpdateChecker.fetch_manifest` — L132–L152
- `async def UpdateChecker.check` — L154–L160
- `async def UpdateChecker.download` — L162–L192
- `def UpdateChecker.launch_installer` — L195–L218

### `app/database/__init__.py`

لایه پایگاه داده نرم‌افزار (SQLite + SQLAlchemy).

ارجاع داخلی: `app/database/models.py`, `app/database/session.py`.

### `app/database/models.py`

تعریف جداول پایگاه داده با SQLAlchemy 2.x (سبک Declarative جدید).

واردکنندگان ایستا: `app/database/__init__.py`, `app/database/repositories/base.py`, `app/database/repositories/candle_repository.py`, `app/database/repositories/chat_repository.py`, `app/database/repositories/outcome_repository.py`, `app/database/repositories/prediction_repository.py`, `app/database/repositories/provider_repository.py`, `app/database/repositories/review_repository.py`, `app/database/repositories/settings_repository.py`, `app/database/repositories/signal_repository.py`, `app/database/repositories/symbol_repository.py`, `app/database/repositories/system_repository.py`, `app/database/repositories/trade_repository.py`, `app/database/repositories/user_repository.py`, `app/database/session.py`, `migrations/env.py`, `signals/prediction/store.py`, `tests/test_auth.py`, `tests/test_prediction_lifecycle.py`, `tests/test_trades_and_wallet.py`, `tests/test_v1917_forecast.py`, `tests/test_v195_ai_and_validity.py`.
- `def _utcnow` — L36–L38
- `class Base : DeclarativeBase` — L41–L44
- `class TimestampMixin` — L47–L53
- `class SettingRecord : Base, TimestampMixin` — L59–L76
- `class ExchangeProviderRecord : Base, TimestampMixin` — L82–L102
- `class AIProviderRecord : Base, TimestampMixin` — L105–L130
- `class SymbolRecord : Base, TimestampMixin` — L136–L156
- `class WatchlistItem : Base, TimestampMixin` — L159–L171
- `class CandleRecord : Base` — L177–L200
- `class MarketDataSnapshot : Base` — L203–L220
- `class IndicatorSnapshot : Base` — L223–L242
- `class SignalRecord : Base, TimestampMixin` — L248–L291
- `class SignalOutcomeRecord : Base, TimestampMixin` — L294–L347
- `class SignalAnalysisRecord : Base, TimestampMixin` — L350–L368
- `class SignalReviewRecord : Base, TimestampMixin` — L371–L402
- `class ChatConversationRecord : Base, TimestampMixin` — L408–L433
- `class ChatMessageRecord : Base` — L436–L459
- `class ReportRecord : Base, TimestampMixin` — L465–L476
- `class BackupHistory : Base, TimestampMixin` — L479–L489
- `class ApplicationLog : Base` — L492–L507
- `class UserRecord : Base, TimestampMixin` — L513–L550
- `class UserSessionRecord : Base` — L553–L575
- `class ExchangeAccountRecord : Base, TimestampMixin` — L578–L622
- `class PaperTradeRecord : Base, TimestampMixin` — L625–L668
- `class PredictionRecord : Base, TimestampMixin` — L671–L717

### `app/database/repositories/__init__.py`

مخازن داده (Repository Pattern).

ارجاع داخلی: `app/database/repositories/base.py`, `app/database/repositories/candle_repository.py`, `app/database/repositories/chat_repository.py`, `app/database/repositories/outcome_repository.py`, `app/database/repositories/prediction_repository.py`, `app/database/repositories/provider_repository.py`, `app/database/repositories/review_repository.py`, `app/database/repositories/settings_repository.py`, `app/database/repositories/signal_repository.py`, `app/database/repositories/symbol_repository.py`, `app/database/repositories/system_repository.py`, `app/database/repositories/trade_repository.py`, `app/database/repositories/user_repository.py`.
واردکنندگان ایستا: `app/application.py`, `reports/builder.py`, `tests/test_auth.py`, `tests/test_backup.py`, `tests/test_chat_repository.py`, `tests/test_reports.py`, `tests/test_trades_and_wallet.py`, `tests/test_v195_ai_and_validity.py`.

### `app/database/repositories/base.py`

کلاس پایه مخازن داده.

ارجاع داخلی: `app/database/models.py`, `app/database/session.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/database/repositories/__init__.py`, `app/database/repositories/candle_repository.py`, `app/database/repositories/chat_repository.py`, `app/database/repositories/outcome_repository.py`, `app/database/repositories/prediction_repository.py`, `app/database/repositories/provider_repository.py`, `app/database/repositories/review_repository.py`, `app/database/repositories/settings_repository.py`, `app/database/repositories/signal_repository.py`, `app/database/repositories/symbol_repository.py`, `app/database/repositories/system_repository.py`, `app/database/repositories/trade_repository.py`, `app/database/repositories/user_repository.py`.
- `class BaseRepository : Generic[ModelType]` — L25–L79
- `def BaseRepository.__init__` — L35–L36
- `def BaseRepository.db` — L39–L41
- `def BaseRepository.add` — L43–L52
- `def BaseRepository.get_by_id` — L54–L57
- `def BaseRepository.list_all` — L59–L65
- `def BaseRepository.delete_by_id` — L67–L74
- `def BaseRepository.count` — L76–L79

### `app/database/repositories/candle_repository.py`

مخزن کندل‌ها.

ارجاع داخلی: `app/core/models.py`, `app/database/models.py`, `app/database/repositories/base.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/database/repositories/__init__.py`, `market/engine.py`.
- `class CandleRepository : BaseRepository[CandleRecord]` — L21–L193
- `def CandleRepository.save_candles` — L26–L73
- `def CandleRepository.get_candles` — L75–L102
- `def CandleRepository.prune` — L104–L146
- `def CandleRepository.save_ticker_snapshot` — L148–L175
- `def CandleRepository.get_ticker_snapshots` — L177–L193

### `app/database/repositories/chat_repository.py`

مخزن گفت‌وگوهای هوش مصنوعی.

ارجاع داخلی: `app/database/models.py`, `app/database/repositories/base.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/database/repositories/__init__.py`, `tests/test_chat_repository.py`.
- `class ChatRepository : BaseRepository[ChatConversationRecord]` — L31–L235
- `def ChatRepository.create_conversation` — L39–L55
- `def ChatRepository.list_conversations` — L57–L74
- `def ChatRepository.get_conversation` — L76–L88
- `def ChatRepository.rename_conversation` — L90–L97
- `def ChatRepository.set_pinned` — L99–L106
- `def ChatRepository.delete_conversation` — L108–L115
- `def ChatRepository.clear_all` — L117–L123
- `def ChatRepository.add_message` — L128–L166
- `def ChatRepository.messages` — L168–L177
- `def ChatRepository.search` — L179–L194
- `def ChatRepository.make_title` — L200–L207
- `def ChatRepository._conversation_to_dict` — L210–L221
- `def ChatRepository._message_to_dict` — L224–L235

### `app/database/repositories/outcome_repository.py`

مخزن نتیجهٔ واقعی سیگنال‌ها.

ارجاع داخلی: `app/database/models.py`, `app/database/repositories/base.py`, `app/logging/__init__.py`, `signals/outcome_tracker.py`.
واردکنندگان ایستا: `app/database/repositories/__init__.py`, `tests/test_v191_outcome_tracking.py`.
- `def _naive` — L36–L47
- `class SignalOutcomeRepository : BaseRepository[SignalOutcomeRecord]` — L50–L325
- `def SignalOutcomeRepository.track_signal` — L57–L111
- `def SignalOutcomeRepository._entry_price` — L114–L125
- `def SignalOutcomeRepository.track_many` — L127–L129
- `def SignalOutcomeRepository.open_outcomes` — L133–L150
- `def SignalOutcomeRepository.open_symbols` — L152–L160
- `def SignalOutcomeRepository.get_by_signal` — L162–L169
- `def SignalOutcomeRepository.history` — L171–L196
- `def SignalOutcomeRepository.apply_state` — L200–L220
- `def SignalOutcomeRepository.cancel` — L222–L232
- `def SignalOutcomeRepository.to_state` — L234–L254
- `def SignalOutcomeRepository.performance` — L258–L270
- `def SignalOutcomeRepository.confidence_buckets` — L272–L293
- `def SignalOutcomeRepository.pending_count` — L295–L305
- `def SignalOutcomeRepository.backfill` — L307–L325

### `app/database/repositories/prediction_repository.py`

مخزن پیش‌بینی‌های ثبت‌شده — پل DB برای قانون حیاتی ۵.

ارجاع داخلی: `app/database/models.py`, `app/database/repositories/base.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/database/repositories/__init__.py`, `tests/test_prediction_lifecycle.py`.
- `def _naive` — L26–L30
- `class PredictionRepository : BaseRepository[PredictionRecord]` — L33–L138
- `def PredictionRepository.record` — L38–L40
- `def PredictionRepository.due_for_resolution` — L42–L65
- `def PredictionRepository.resolve` — L67–L87
- `def PredictionRepository.recent` — L89–L97
- `def PredictionRepository.resolved` — L99–L111
- `def PredictionRepository.accuracy_group` — L113–L138

### `app/database/repositories/provider_repository.py`

مخازن پیکربندی ارائه‌دهندگان (صرافی و هوش مصنوعی).

ارجاع داخلی: `app/database/models.py`, `app/database/repositories/base.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/database/repositories/__init__.py`.
- `class ExchangeProviderRepository : BaseRepository[ExchangeProviderRecord]` — L22–L73
- `def ExchangeProviderRepository.get_by_name` — L27–L32
- `def ExchangeProviderRepository.ensure_provider` — L34–L48
- `def ExchangeProviderRepository.update_status` — L50–L64
- `def ExchangeProviderRepository.list_enabled` — L66–L73
- `class AIProviderRepository : BaseRepository[AIProviderRecord]` — L76–L146
- `def AIProviderRepository.get_by_name` — L81–L86
- `def AIProviderRepository.ensure_provider` — L88–L100
- `def AIProviderRepository.list_by_priority` — L102–L113
- `def AIProviderRepository.update_config` — L115–L135
- `def AIProviderRepository.mark_used` — L137–L146

### `app/database/repositories/review_repository.py`

مخزن بازبینی‌های هوش مصنوعی روی سیگنال‌های بسته‌شده.

ارجاع داخلی: `app/database/models.py`, `app/database/repositories/base.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/database/repositories/__init__.py`.
- `class SignalReviewRepository : BaseRepository[SignalReviewRecord]` — L27–L157
- `def SignalReviewRepository.for_signal` — L34–L44
- `def SignalReviewRepository.reviewed_ids` — L46–L52
- `def SignalReviewRepository.pending_reviews` — L54–L78
- `def SignalReviewRepository.lesson_counts` — L80–L94
- `def SignalReviewRepository.save` — L98–L133
- `def SignalReviewRepository.stats` — L135–L157

### `app/database/repositories/settings_repository.py`

مخزن تنظیمات کاربر.

ارجاع داخلی: `app/database/models.py`, `app/database/repositories/base.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/config/settings_service.py`, `app/database/repositories/__init__.py`.
- `class SettingsRepository : BaseRepository[SettingRecord]` — L22–L132
- `def SettingsRepository.get` — L27–L40
- `def SettingsRepository.set` — L42–L64
- `def SettingsRepository.get_many` — L66–L72
- `def SettingsRepository.get_all` — L74–L78
- `def SettingsRepository.get_by_category` — L80–L86
- `def SettingsRepository.exists` — L88–L94
- `def SettingsRepository.ensure_defaults` — L96–L128
- `def SettingsRepository.reset_key` — L130–L132

### `app/database/repositories/signal_repository.py`

مخزن سیگنال‌ها و تحلیل‌های مرتبط.

ارجاع داخلی: `app/core/models.py`, `app/database/models.py`, `app/database/repositories/base.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/database/repositories/__init__.py`, `tests/test_v1918_live_and_auto.py`, `tests/test_v191_outcome_tracking.py`.
- `class SignalRepository : BaseRepository[SignalRecord]` — L24–L249
- `def SignalRepository.save_signal` — L29–L101
- `def SignalRepository.search` — L103–L145
- `def SignalRepository.get_latest` — L147–L149
- `def SignalRepository.get_with_analysis` — L151–L161
- `def SignalRepository.analysis_payload` — L163–L190
- `def SignalRepository.update_analysis` — L192–L221
- `def SignalRepository.get_statistics` — L223–L249

### `app/database/repositories/symbol_repository.py`

مخزن نمادها و فهرست پیگیری (Watchlist).

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`, `app/database/models.py`, `app/database/repositories/base.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/database/repositories/__init__.py`, `tests/test_v192_watchlist.py`.
- `class SymbolRepository : BaseRepository[SymbolRecord]` — L28–L421
- `def SymbolRepository.sync_symbols` — L33–L82
- `def SymbolRepository.search` — L84–L114
- `def SymbolRepository.get_by_symbol` — L116–L123
- `def SymbolRepository.set_favorite` — L125–L136
- `def SymbolRepository.count_active` — L138–L148
- `def SymbolRepository.get_watchlist` — L151–L160
- `def SymbolRepository.add_to_watchlist` — L162–L194
- `def SymbolRepository.remove_from_watchlist` — L196–L214
- `def SymbolRepository.watchlist_names` — L220–L234
- `def SymbolRepository.watchlist_counts` — L236–L245
- `def SymbolRepository.create_watchlist` — L247–L258
- `def SymbolRepository.rename_watchlist` — L260–L283
- `def SymbolRepository.delete_watchlist` — L285–L304
- `def SymbolRepository.watchlist_details` — L306–L333
- `def SymbolRepository.reorder_watchlist` — L335–L365
- `def SymbolRepository.move_in_watchlist` — L367–L381
- `def SymbolRepository.set_watchlist_note` — L383–L404
- `def SymbolRepository.find_symbol_lists` — L406–L421

### `app/database/repositories/system_repository.py`

مخازن سیستمی: سابقه پشتیبان‌گیری و گزارش‌ها.

ارجاع داخلی: `app/database/models.py`, `app/database/repositories/base.py`.
واردکنندگان ایستا: `app/database/repositories/__init__.py`.
- `class BackupHistoryRepository : BaseRepository[BackupHistory]` — L15–L43
- `def BackupHistoryRepository.record_backup` — L20–L34
- `def BackupHistoryRepository.list_recent` — L36–L43
- `class ReportRepository : BaseRepository[ReportRecord]` — L46–L82
- `def ReportRepository.record_report` — L51–L73
- `def ReportRepository.list_recent` — L75–L82

### `app/database/repositories/trade_repository.py`

مخزن معاملات کاغذی.

ارجاع داخلی: `app/database/models.py`, `app/database/repositories/base.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/database/repositories/__init__.py`.
- `def _utcnow` — L26–L28
- `def _to_dict` — L31–L56
- `class PaperTradeRepository : BaseRepository[PaperTradeRecord]` — L59–L347
- `def PaperTradeRepository.open_trade` — L67–L114
- `def PaperTradeRepository.update_live_pnl` — L116–L133
- `def PaperTradeRepository.close_trade` — L135–L174
- `def PaperTradeRepository.cancel_trade` — L176–L184
- `def PaperTradeRepository.delete_trade` — L186–L193
- `def PaperTradeRepository.clear_history` — L195–L201
- `def PaperTradeRepository.list_trades` — L206–L232
- `def PaperTradeRepository.count_trades` — L234–L248
- `def PaperTradeRepository.open_trades` — L250–L252
- `def PaperTradeRepository.statistics` — L254–L296
- `def PaperTradeRepository.equity_curve` — L298–L319
- `def PaperTradeRepository.symbols_traded` — L321–L327
- `def PaperTradeRepository._apply_filters` — L333–L347

### `app/database/repositories/user_repository.py`

مخزن کاربران، نشست‌ها و حساب‌های صرافی.

ارجاع داخلی: `app/database/models.py`, `app/database/repositories/base.py`, `app/logging/__init__.py`, `app/security/passwords.py`.
واردکنندگان ایستا: `app/core/auth_service.py`, `app/core/exchange_account_service.py`, `app/database/repositories/__init__.py`, `tests/test_v156_fixes.py`.
- `def _utcnow` — L46–L48
- `def _user_to_dict` — L51–L69
- `def _account_to_dict` — L72–L94
- `class UserRepository : BaseRepository[UserRecord]` — L97–L495
- `def UserRepository.create_user` — L105–L159
- `def UserRepository.get_by_username` — L161–L168
- `def UserRepository.get_user` — L170–L174
- `def UserRepository.list_users` — L176–L182
- `def UserRepository.count_users` — L184–L189
- `def UserRepository.authenticate` — L194–L262
- `def UserRepository.change_password` — L264–L296
- `def UserRepository.find_by_email` — L298–L312
- `def UserRepository.reset_password` — L314–L346
- `def UserRepository.update_profile` — L351–L379
- `def UserRepository.get_preferences` — L381–L385
- `def UserRepository.set_preferences` — L387–L400
- `def UserRepository.set_active` — L402–L409
- `def UserRepository.create_session` — L414–L427
- `def UserRepository.resolve_session` — L429–L450
- `def UserRepository.list_sessions` — L452–L470
- `def UserRepository.revoke_session` — L472–L479
- `def UserRepository.revoke_all_sessions` — L481–L487
- `def UserRepository.purge_expired_sessions` — L489–L495
- `class ExchangeAccountRepository : BaseRepository[ExchangeAccountRecord]` — L498–L714
- `def ExchangeAccountRepository.create_account` — L503–L549
- `def ExchangeAccountRepository.list_accounts` — L551–L561
- `def ExchangeAccountRepository.get_account` — L563–L567
- `def ExchangeAccountRepository.get_default_account` — L569–L586
- `def ExchangeAccountRepository.secret_ref` — L588–L597
- `def ExchangeAccountRepository.update_credentials` — L599–L610
- `def ExchangeAccountRepository.set_status` — L612–L634
- `def ExchangeAccountRepository.update_balances` — L636–L667
- `def ExchangeAccountRepository.set_default` — L669–L677
- `def ExchangeAccountRepository.set_enabled` — L679–L686
- `def ExchangeAccountRepository.delete_account` — L688–L701
- `def ExchangeAccountRepository._clear_defaults` — L704–L714

### `app/database/session.py`

مدیریت اتصال و نشست پایگاه داده.

ارجاع داخلی: `app/config/settings.py`, `app/database/models.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/application.py`, `app/database/__init__.py`, `app/database/repositories/base.py`, `tests/conftest.py`, `tests/test_auth.py`, `tests/test_backup.py`, `tests/test_reports.py`, `tests/test_trades_and_wallet.py`, `tests/test_v1917_trust_and_trades.py`.
- `class DatabaseManager` — L34–L278
- `def DatabaseManager.__init__` — L45–L49
- `def DatabaseManager._create_engine` — L54–L84
- `def DatabaseManager._create_engine._configure_sqlite` — L73–L82
- `def DatabaseManager._safe_url` — L86–L91
- `def DatabaseManager.engine` — L97–L99
- `def DatabaseManager.create_all` — L101–L113
- `def DatabaseManager._add_missing_columns` — L115–L175
- `def DatabaseManager._column_ddl` — L178–L217
- `def DatabaseManager.create_session` — L219–L221
- `def DatabaseManager.session_scope` — L224–L242
- `def DatabaseManager.check_connection` — L244–L252
- `def DatabaseManager.get_database_size` — L254–L259
- `def DatabaseManager.vacuum` — L261–L273
- `def DatabaseManager.dispose` — L275–L278
- `def get_database_manager` — L284–L298
- `def reset_database_manager` — L301–L306

### `app/exceptions/__init__.py`

ماژول استثناهای اختصاصی نرم‌افزار.

ارجاع داخلی: `app/exceptions/errors.py`.
واردکنندگان ایستا: `ai/agent/analyst.py`, `ai/agent/autonomous_agent.py`, `ai/agent/chat_agent.py`, `ai/prompts/prompt_manager.py`, `ai/providers/manager.py`, `ai/providers/ollama_provider.py`, `ai/providers/openai_compatible.py`, `ai/tools/market_tools.py`, `app/database/repositories/base.py`, `app/database/session.py`, `app/security/db_backend.py`, `app/security/secret_store.py`, `backup/manager.py`, `indicators/base.py`, `indicators/engine.py`, `indicators/registry.py`, `market/engine.py`, `market/providers/bitpin/provider.py`, `market/providers/bitpin/rest_client.py`, `market/providers/lbank/parser.py`, `market/providers/lbank/provider.py`, `market/providers/lbank/rest_client.py`, `market/providers/lbank/websocket_client.py`, `market/providers/registry.py`, `market/providers/toobit/provider.py`, `market/providers/toobit/rest_client.py`, `market/providers/toobit/websocket_client.py`, `market/quality.py`, `market/rate_limiter.py`, `market/timeframes.py`, `reports/exporters.py`, `signals/engine.py`, `signals/strategies/registry.py`, `tests/conftest.py`, `tests/test_ai_providers.py`, `tests/test_async_runner.py`, `tests/test_backup.py`, `tests/test_indicators.py`, `tests/test_reports.py`, `tests/test_toobit_bitpin_providers.py`, `tests/test_v194_performance.py`, `tests/test_v196_fixes.py`, `ui/controllers/async_runner.py`.

### `app/exceptions/errors.py`

تعریف سلسله‌مراتب استثناهای نرم‌افزار.

واردکنندگان ایستا: `app/exceptions/__init__.py`, `market/providers/lbank/rest_client.py`, `tests/test_v160_error_keys.py`.
- `class AppError : Exception` — L18–L45
- `def AppError.__init__` — L30–L40
- `def AppError.__str__` — L42–L45
- `class ConfigurationError : AppError` — L51–L54
- `class DatabaseError : AppError` — L57–L60
- `class SecurityError : AppError` — L63–L66
- `class BackupError : AppError` — L69–L72
- `class ValidationError : AppError` — L75–L78
- `class NetworkError : AppError` — L84–L87
- `class TimeoutErrorApp : NetworkError` — L90–L93
- `class RateLimitError : NetworkError` — L96–L99
- `class AuthenticationError : AppError` — L102–L105
- `class ExchangeError : AppError` — L108–L116
- `class TransientExchangeError : ExchangeError` — L119–L127
- `class WebSocketError : NetworkError` — L130–L133
- `class TimeframeError : AppError` — L139–L142
- `class IndicatorError : AppError` — L145–L148
- `class InsufficientDataError : AppError` — L151–L159
- `class AIError : AppError` — L165–L168
- `class AIProviderError : AIError` — L171–L174
- `class AIResponseValidationError : AIError` — L177–L180
- `class SignalEngineError : AppError` — L183–L186

### `app/logging/__init__.py`

ماژول لاگ‌گیری حرفه‌ای نرم‌افزار.

ارجاع داخلی: `app/logging/logger.py`.
واردکنندگان ایستا: `ai/agent/analyst.py`, `ai/agent/autonomous_agent.py`, `ai/agent/chat_agent.py`, `ai/agent/narrative.py`, `ai/agent/reviewer.py`, `ai/agent/validator.py`, `ai/prompt_budget.py`, `ai/prompts/prompt_manager.py`, `ai/providers/manager.py`, `ai/providers/ollama_provider.py`, `ai/providers/omniroute_provider.py`, `ai/providers/openai_compatible.py`, `ai/tools/composite.py`, `ai/tools/market_tools.py`, `ai/tools/omniroute_tools.py`, `app/application.py`, `app/config/settings_service.py`, `app/core/auth_service.py`, `app/core/email_service.py`, `app/core/exchange_account_service.py`, `app/core/password_reset.py`, `app/core/timeutil.py`, `app/core/updater.py`, `app/database/repositories/base.py`, `app/database/repositories/candle_repository.py`, `app/database/repositories/chat_repository.py`, `app/database/repositories/outcome_repository.py`, `app/database/repositories/prediction_repository.py`, `app/database/repositories/provider_repository.py`, `app/database/repositories/review_repository.py`, `app/database/repositories/settings_repository.py`, `app/database/repositories/signal_repository.py`, `app/database/repositories/symbol_repository.py`, `app/database/repositories/trade_repository.py`, `app/database/repositories/user_repository.py`, `app/database/session.py`, `app/security/db_backend.py`, `app/security/secret_store.py`, `backup/manager.py`, `indicators/base.py`, `indicators/engine.py`, `indicators/registry.py`, `localization/translator.py`, `main.py`, `market/cache/memory_cache.py`, `market/engine.py`, `market/fiat_rates.py`, `market/live_feed.py`, `market/providers/bitpin/provider.py`, `market/providers/bitpin/rest_client.py`, `market/providers/lbank/parser.py`, `market/providers/lbank/provider.py`, `market/providers/lbank/rest_client.py`, `market/providers/lbank/websocket_client.py`, `market/providers/registry.py`, `market/providers/toobit/parser.py`, `market/providers/toobit/provider.py`, `market/providers/toobit/rest_client.py`, `market/providers/toobit/websocket_client.py`, `market/quality.py`, `market/rate_limiter.py`, `market/resilience.py`, `market/timeframes.py`, `reports/builder.py`, `reports/exporters.py`, `reports/persian_pdf.py`, `signals/auto_scanner.py`, `signals/engine.py`, `signals/outcome_tracker.py`, `signals/paper_trader.py`, `signals/prediction/breakout.py`, `signals/prediction/distribution.py`, `signals/prediction/engine.py`, `signals/prediction/events.py`, `signals/prediction/explain.py`, `signals/prediction/features.py`, `signals/prediction/fusion.py`, `signals/prediction/models/ensemble.py`, `signals/prediction/models/gbm.py`, `signals/prediction/models/lstm.py`, `signals/prediction/models/statistical.py`, `signals/prediction/models/walkforward.py`, `signals/prediction/regime.py`, `signals/prediction/scenarios.py`, `signals/prediction/scoring.py`, `signals/prediction/store.py`, `signals/prediction/timeline.py`, `signals/prediction/warning.py`, `signals/risk_engine.py`, `signals/scanner.py`, `signals/strategies/registry.py`, `trading/auto_trader.py`, `trading/confidence_source.py`, `trading/price_cache.py`, `trading/scalp_service.py`, `ui/charts/price_chart.py`, `ui/controllers/async_runner.py`, `ui/controllers/main_controller.py`, `ui/dialogs/first_run_wizard.py`, `ui/themes/custom.py`, `ui/themes/fonts.py`, `ui/themes/theme_manager.py`, `ui/windows/main_window.py`.

### `app/logging/logger.py`

پیکربندی سامانه لاگ‌گیری.

واردکنندگان ایستا: `app/logging/__init__.py`.
- `class SensitiveDataFilter : logging.Filter` — L41–L74
- `def SensitiveDataFilter.filter` — L50–L62
- `def SensitiveDataFilter.mask` — L65–L70
- `def SensitiveDataFilter._mask_value` — L72–L74
- `def configure_logging` — L77–L128
- `def get_logger` — L131–L137

### `app/security/__init__.py`

ماژول امنیت: نگهداری امن اطلاعات حساس.

ارجاع داخلی: `app/security/passwords.py`, `app/security/secret_store.py`.

### `app/security/db_backend.py`

نگهداری رازها به‌صورت رمزنگاری‌شده در پایگاه داده.

ارجاع داخلی: `app/core/paths.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`, `app/security/secret_store.py`.
واردکنندگان ایستا: `app/application.py`.
- `class DatabaseBackend : SecretStoreBackend` — L35–L134
- `def DatabaseBackend.__init__` — L47–L55
- `def DatabaseBackend._derive_key` — L58–L73
- `def DatabaseBackend.is_available` — L75–L77
- `def DatabaseBackend._read_all` — L82–L104
- `def DatabaseBackend._write_all` — L106–L117
- `def DatabaseBackend.get` — L119–L121
- `def DatabaseBackend.set` — L123–L127
- `def DatabaseBackend.delete` — L129–L134

### `app/security/passwords.py`

چکیده‌سازی و راستی‌آزمایی رمز عبور.

واردکنندگان ایستا: `app/core/auth_service.py`, `app/core/exchange_account_service.py`, `app/core/password_reset.py`, `app/database/repositories/user_repository.py`, `app/security/__init__.py`, `tests/test_auth.py`, `ui/dialogs/auth_dialog.py`, `ui/dialogs/password_reset_dialog.py`.
- `class PasswordHash` — L38–L44
- `def hash_password` — L47–L75
- `def verify_password` — L78–L103
- `def needs_rehash` — L106–L112
- `def password_strength` — L115–L142
- `def validate_password` — L145–L155
- `def generate_token` — L158–L160
- `def hash_token` — L163–L169
- `def mask_secret` — L172–L184

### `app/security/secret_store.py`

مخزن امن اطلاعات حساس (کلید API، Secret و توکن‌ها).

ارجاع داخلی: `app/core/constants.py`, `app/core/paths.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/application.py`, `app/core/exchange_account_service.py`, `app/security/__init__.py`, `app/security/db_backend.py`, `tests/test_auth.py`.
- `class SecretStoreBackend : ABC` — L42–L66
- `def SecretStoreBackend.get` — L53–L54
- `def SecretStoreBackend.set` — L57–L58
- `def SecretStoreBackend.delete` — L61–L62
- `def SecretStoreBackend.is_available` — L65–L66
- `class KeyringBackend : SecretStoreBackend` — L69–L137
- `def KeyringBackend.__init__` — L80–L95
- `def KeyringBackend.is_available` — L97–L110
- `def KeyringBackend.get` — L112–L119
- `def KeyringBackend.set` — L121–L128
- `def KeyringBackend.delete` — L130–L137
- `class EncryptedFileBackend : SecretStoreBackend` — L140–L237
- `def EncryptedFileBackend.__init__` — L152–L160
- `def EncryptedFileBackend._derive_key` — L162–L177
- `def EncryptedFileBackend.is_available` — L179–L181
- `def EncryptedFileBackend._read_all` — L183–L199
- `def EncryptedFileBackend._write_all` — L201–L220
- `def EncryptedFileBackend.get` — L222–L224
- `def EncryptedFileBackend.set` — L226–L230
- `def EncryptedFileBackend.delete` — L232–L237
- `class SecretStore` — L240–L376
- `def SecretStore.__init__` — L248–L250
- `def SecretStore._select_backend` — L253–L267
- `def SecretStore.backend_name` — L270–L272
- `def SecretStore.make_key` — L275–L277
- `def SecretStore.get` — L279–L290
- `def SecretStore.set` — L292–L300
- `def SecretStore.delete` — L302–L313
- `def SecretStore.use_backend` — L315–L327
- `def SecretStore.get_secret` — L329–L340
- `def SecretStore.set_secret` — L342–L348
- `def SecretStore.delete_secret` — L350–L352
- `def SecretStore.has_secret` — L354–L356
- `def SecretStore.get_exchange_credentials` — L359–L362
- `def SecretStore.set_exchange_credentials` — L364–L368
- `def SecretStore.get_ai_api_key` — L370–L372
- `def SecretStore.set_ai_api_key` — L374–L376
- `def get_secret_store` — L382–L389

### `backup/__init__.py`

لایه پشتیبان‌گیری و بازیابی.

ارجاع داخلی: `backup/manager.py`.
واردکنندگان ایستا: `app/application.py`, `migrations/env.py`, `tests/test_backup.py`.

### `backup/manager.py`

مدیریت پشتیبان‌گیری و بازیابی.

ارجاع داخلی: `app/core/constants.py`, `app/core/paths.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `backup/__init__.py`.
- `class BackupInfo` — L48–L77
- `def BackupInfo.size_mb` — L61–L63
- `def BackupInfo.to_dict` — L65–L77
- `class BackupManager` — L80–L400
- `def BackupManager.__init__` — L89–L91
- `def BackupManager.create` — L96–L157
- `def BackupManager.create_pre_migration` — L159–L171
- `def BackupManager.list_backups` — L176–L214
- `def BackupManager.read_manifest` — L217–L222
- `def BackupManager.verify` — L224–L245
- `def BackupManager.restore` — L250–L310
- `def BackupManager.delete` — L312–L315
- `def BackupManager._remove_wal_sidecars` — L320–L332
- `def BackupManager._unique_target` — L334–L347
- `def BackupManager._snapshot_database` — L350–L366
- `def BackupManager._assert_valid_sqlite` — L369–L377
- `def BackupManager._sha256` — L380–L386
- `def BackupManager._prune` — L388–L400

### `indicators/__init__.py`

موتور اندیکاتورهای تکنیکال.

ارجاع داخلی: `indicators/base.py`, `indicators/engine.py`, `indicators/registry.py`.
واردکنندگان ایستا: `app/application.py`, `tests/test_indicators.py`, `tests/test_signal_engine.py`.

### `indicators/base.py`

واسط پایه تمام اندیکاتورها.

ارجاع داخلی: `app/core/models.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `indicators/__init__.py`, `indicators/engine.py`, `indicators/momentum.py`, `indicators/registry.py`, `indicators/support_resistance.py`, `indicators/trend.py`, `indicators/volatility.py`, `indicators/volume.py`, `tests/test_v194_performance.py`.
- `class IndicatorCategory : str, Enum` — L27–L34
- `class IndicatorMetadata` — L38–L53
- `class BaseIndicator : ABC` — L56–L165
- `def BaseIndicator.__init__` — L67–L69
- `def BaseIndicator.metadata` — L76–L77
- `def BaseIndicator.name` — L80–L82
- `def BaseIndicator.parameters` — L85–L87
- `def BaseIndicator._validate_parameters` — L89–L102
- `def BaseIndicator._compute` — L108–L113
- `def BaseIndicator.interpret` — L115–L122
- `def BaseIndicator.calculate` — L124–L165
- `def candles_to_dataframe` — L168–L187

### `indicators/engine.py`

موتور اندیکاتور (Indicator Engine).

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`, `indicators/base.py`, `indicators/registry.py`, `indicators/support_resistance.py`, `market/cache/memory_cache.py`.
واردکنندگان ایستا: `ai/tools/market_tools.py`, `indicators/__init__.py`, `signals/engine.py`, `signals/prediction/features.py`, `tests/test_v194_performance.py`.
- `class IndicatorEngine` — L39–L340
- `def IndicatorEngine.__init__` — L48–L57
- `def IndicatorEngine.set_default_parameters` — L62–L70
- `def IndicatorEngine.available_indicators` — L72–L74
- `def IndicatorEngine.indicators_by_category` — L76–L78
- `def IndicatorEngine.get_metadata` — L80–L82
- `def IndicatorEngine._data_fingerprint` — L88–L113
- `def IndicatorEngine.calculate` — L115–L169
- `def IndicatorEngine.calculate_many` — L171–L208
- `def IndicatorEngine.analyze_timeframe` — L213–L253
- `def IndicatorEngine.analyze_multi_timeframe` — L255–L282
- `def IndicatorEngine._describe_volume` — L285–L312
- `def IndicatorEngine.summarize_trend` — L315–L340

### `indicators/momentum.py`

اندیکاتورهای شتاب (Momentum).

ارجاع داخلی: `indicators/base.py`.
واردکنندگان ایستا: `indicators/registry.py`.
- `class RSIIndicator : BaseIndicator` — L16–L59
- `def RSIIndicator.metadata` — L25–L34
- `def RSIIndicator._compute` — L36–L48
- `def RSIIndicator.interpret` — L50–L59
- `class MACDIndicator : BaseIndicator` — L62–L104
- `def MACDIndicator.metadata` — L68–L77
- `def MACDIndicator._compute` — L79–L88
- `def MACDIndicator.interpret` — L90–L104
- `class StochasticIndicator : BaseIndicator` — L107–L142
- `def StochasticIndicator.metadata` — L111–L120
- `def StochasticIndicator._compute` — L122–L131
- `def StochasticIndicator.interpret` — L133–L142
- `class CCIIndicator : BaseIndicator` — L145–L180
- `def CCIIndicator.metadata` — L149–L158
- `def CCIIndicator._compute` — L160–L169
- `def CCIIndicator.interpret` — L171–L180
- `class ROCIndicator : BaseIndicator` — L183–L208
- `def ROCIndicator.metadata` — L187–L196
- `def ROCIndicator._compute` — L198–L201
- `def ROCIndicator.interpret` — L203–L208
- `class WilliamsRIndicator : BaseIndicator` — L211–L243
- `def WilliamsRIndicator.metadata` — L215–L224
- `def WilliamsRIndicator._compute` — L226–L232
- `def WilliamsRIndicator.interpret` — L234–L243
- `class MFIIndicator : BaseIndicator` — L246–L284
- `def MFIIndicator.metadata` — L252–L261
- `def MFIIndicator._compute` — L263–L273
- `def MFIIndicator.interpret` — L275–L284

### `indicators/registry.py`

ثبت‌کننده اندیکاتورها (Factory Pattern).

ارجاع داخلی: `app/exceptions/__init__.py`, `app/logging/__init__.py`, `indicators/base.py`, `indicators/momentum.py`, `indicators/support_resistance.py`, `indicators/trend.py`, `indicators/volatility.py`, `indicators/volume.py`.
واردکنندگان ایستا: `app/application.py`, `indicators/__init__.py`, `indicators/engine.py`, `tests/conftest.py`, `tests/test_indicators.py`, `tests/test_v194_performance.py`.
- `class IndicatorRegistry` — L21–L69
- `def IndicatorRegistry.__init__` — L24–L25
- `def IndicatorRegistry.register` — L27–L33
- `def IndicatorRegistry.create` — L35–L43
- `def IndicatorRegistry.available` — L45–L47
- `def IndicatorRegistry.by_category` — L49–L54
- `def IndicatorRegistry.get_metadata` — L56–L69
- `def register_builtin_indicators` — L75–L112

### `indicators/support_resistance.py`

سطوح حمایت/مقاومت و تحلیل ساختار بازار.

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`, `indicators/base.py`.
واردکنندگان ایستا: `ai/tools/market_tools.py`, `indicators/engine.py`, `indicators/registry.py`, `signals/engine.py`, `signals/prediction/breakout.py`, `ui/controllers/main_controller.py`.
- `class PivotPointsIndicator : BaseIndicator` — L26–L66
- `def PivotPointsIndicator.metadata` — L35–L45
- `def PivotPointsIndicator._compute` — L47–L59
- `def PivotPointsIndicator.interpret` — L61–L66
- `class FibonacciIndicator : BaseIndicator` — L69–L123
- `def FibonacciIndicator.metadata` — L78–L88
- `def FibonacciIndicator._compute` — L90–L106
- `def FibonacciIndicator.interpret` — L108–L123
- `def find_swing_points` — L126–L153
- `def analyze_market_structure` — L156–L229
- `def find_support_resistance` — L232–L287
- `def detect_trend` — L290–L315

### `indicators/trend.py`

اندیکاتورهای روند (Trend).

ارجاع داخلی: `app/core/constants.py`, `indicators/base.py`.
واردکنندگان ایستا: `indicators/registry.py`, `ui/controllers/main_controller.py`.
- `class SMAIndicator : BaseIndicator` — L17–L44
- `def SMAIndicator.metadata` — L21–L31
- `def SMAIndicator._compute` — L33–L36
- `def SMAIndicator.interpret` — L38–L44
- `class EMAIndicator : BaseIndicator` — L47–L74
- `def EMAIndicator.metadata` — L51–L61
- `def EMAIndicator._compute` — L63–L66
- `def EMAIndicator.interpret` — L68–L74
- `class WMAIndicator : BaseIndicator` — L77–L115
- `def WMAIndicator.metadata` — L81–L91
- `def WMAIndicator._wma` — L94–L99
- `def WMAIndicator._compute` — L101–L104
- `def WMAIndicator.interpret` — L106–L115
- `class HMAIndicator : BaseIndicator` — L118–L157
- `def HMAIndicator.metadata` — L126–L136
- `def HMAIndicator._compute` — L138–L146
- `def HMAIndicator.interpret` — L148–L157
- `class ADXIndicator : BaseIndicator` — L160–L213
- `def ADXIndicator.metadata` — L168–L177
- `def ADXIndicator._compute` — L179–L200
- `def ADXIndicator.interpret` — L202–L213
- `class IchimokuIndicator : BaseIndicator` — L216–L277
- `def IchimokuIndicator.metadata` — L224–L234
- `def IchimokuIndicator._compute` — L236–L262
- `def IchimokuIndicator._compute._midpoint` — L248–L253
- `def IchimokuIndicator.interpret` — L264–L277
- `class ParabolicSARIndicator : BaseIndicator` — L280–L353
- `def ParabolicSARIndicator.metadata` — L286–L296
- `def ParabolicSARIndicator._compute` — L298–L342
- `def ParabolicSARIndicator.interpret` — L344–L353

### `indicators/volatility.py`

اندیکاتورهای نوسان (Volatility).

ارجاع داخلی: `indicators/base.py`.
واردکنندگان ایستا: `indicators/registry.py`, `ui/controllers/main_controller.py`.
- `def true_range` — L15–L25
- `class ATRIndicator : BaseIndicator` — L28–L70
- `def ATRIndicator.metadata` — L37–L46
- `def ATRIndicator._compute` — L48–L52
- `def ATRIndicator.interpret` — L54–L70
- `class BollingerBandsIndicator : BaseIndicator` — L73–L129
- `def BollingerBandsIndicator.metadata` — L79–L89
- `def BollingerBandsIndicator._compute` — L91–L106
- `def BollingerBandsIndicator.interpret` — L108–L129
- `class KeltnerChannelIndicator : BaseIndicator` — L132–L171
- `def KeltnerChannelIndicator.metadata` — L136–L146
- `def KeltnerChannelIndicator._compute` — L148–L159
- `def KeltnerChannelIndicator.interpret` — L161–L171
- `class DonchianChannelIndicator : BaseIndicator` — L174–L214
- `def DonchianChannelIndicator.metadata` — L178–L188
- `def DonchianChannelIndicator._compute` — L190–L195
- `def DonchianChannelIndicator.interpret` — L197–L214

### `indicators/volume.py`

اندیکاتورهای حجم (Volume).

ارجاع داخلی: `indicators/base.py`.
واردکنندگان ایستا: `indicators/registry.py`.
- `class OBVIndicator : BaseIndicator` — L16–L48
- `def OBVIndicator.metadata` — L24–L33
- `def OBVIndicator._compute` — L35–L40
- `def OBVIndicator.interpret` — L42–L48
- `class VWAPIndicator : BaseIndicator` — L51–L86
- `def VWAPIndicator.metadata` — L61–L71
- `def VWAPIndicator._compute` — L73–L79
- `def VWAPIndicator.interpret` — L81–L86
- `class VolumeSMAIndicator : BaseIndicator` — L89–L121
- `def VolumeSMAIndicator.metadata` — L93–L102
- `def VolumeSMAIndicator._compute` — L104–L108
- `def VolumeSMAIndicator.interpret` — L110–L121
- `class CMFIndicator : BaseIndicator` — L124–L159
- `def CMFIndicator.metadata` — L128–L137
- `def CMFIndicator._compute` — L139–L148
- `def CMFIndicator.interpret` — L150–L159

### `localization/__init__.py`

لایه بومی‌سازی (Localization).

ارجاع داخلی: `localization/translator.py`.
واردکنندگان ایستا: `main.py`, `tests/test_chat_page.py`, `tests/test_chat_ui_v2.py`, `tests/test_exchange_login_flow.py`, `tests/test_exchange_switching.py`, `tests/test_localization.py`, `tests/test_markets_sorting.py`, `tests/test_new_pages.py`, `tests/test_pages_design_v151.py`, `tests/test_prediction_ui_and_tools.py`, `tests/test_settings_expanded.py`, `tests/test_toobit_bitpin_providers.py`, `tests/test_ui_wiring.py`, `tests/test_v153_fixes.py`, `tests/test_v154_ai_signal.py`, `tests/test_v154_localization.py`, `tests/test_v155_ui_and_ai.py`, `tests/test_v158_security_tab.py`, `tests/test_v160_error_keys.py`, `tests/test_v161_omniroute_font_theme.py`, `tests/test_v162_modal_close.py`, `tests/test_v170_signals_ui.py`, `tests/test_v180_ai_status_card.py`, `tests/test_v180_arrangeable_layout.py`, `tests/test_v180_custom_themes.py`, `tests/test_v180_table_fullscreen.py`, `tests/test_v180_tutorial.py`, `tests/test_v190_account_and_auto_scan.py`, `tests/test_v190_position_sizing.py`, `tests/test_v1917_forecast.py`, `tests/test_v1918_alerts.py`, `tests/test_v1918_live_and_auto.py`, `tests/test_v1918_scorecard.py`, `tests/test_v191_outcome_tracking.py`, `tests/test_v1920_ashna_settings.py`, `tests/test_v1921_online_and_autotrade.py`, `tests/test_v192_watchlist.py`, `tests/test_v193_page_scrolling.py`, `tests/test_v194_performance.py`, `tests/test_v195_ai_and_validity.py`, `tests/test_v196_fixes.py`, `tests/test_v200_event_driven_trading.py`, `tests/test_v22_terminal_pro.py`, `tools/preview_shot.py`, `tools/sweep_ui.py`, `ui/charts/price_chart.py`, `ui/controllers/main_controller.py`, `ui/dialogs/analysis_dialog.py`, `ui/dialogs/auth_dialog.py`, `ui/dialogs/coin_detail_dialog.py`, `ui/dialogs/first_run_wizard.py`, `ui/dialogs/password_reset_dialog.py`, `ui/dialogs/signal_detail_dialog.py`, `ui/dialogs/trading_dialogs.py`, `ui/pages/analysis_page.py`, `ui/pages/base_page.py`, `ui/pages/chat_page.py`, `ui/pages/dashboard_page.py`, `ui/pages/help_page.py`, `ui/pages/markets_page.py`, `ui/pages/prediction_page.py`, `ui/pages/reports_page.py`, `ui/pages/settings_page.py`, `ui/pages/signals_page.py`, `ui/pages/trades_page.py`, `ui/pages/wallet_page.py`, `ui/widgets/performance_view.py`, `ui/widgets/watchlist_panel.py`, `ui/windows/main_window.py`.

### `localization/translator.py`

موتور ترجمه.

ارجاع داخلی: `app/core/constants.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `localization/__init__.py`, `tests/test_v162_chat_streaming.py`, `tests/test_v171_chat_tool_steps.py`, `tests/test_v172_signal_ai_and_scan_ui.py`, `tests/test_v1913_ashna.py`.
- `class Translator` — L37–L236
- `def Translator.__init__` — L46–L51
- `def Translator._normalize` — L57–L61
- `def Translator.load` — L63–L77
- `def Translator._load_language` — L79–L96
- `def Translator._count_keys` — L99–L103
- `def Translator.language` — L109–L111
- `def Translator.is_rtl` — L114–L116
- `def Translator.direction` — L119–L121
- `def Translator.set_language` — L123–L129
- `def Translator.available_languages` — L131–L137
- `def Translator.tr` — L142–L165
- `def Translator._lookup` — L168–L175
- `def Translator.raw` — L177–L188
- `def Translator.has` — L190–L192
- `def Translator.missing_keys` — L194–L211
- `def Translator.missing_keys.walk` — L203–L208
- `def Translator.format_number` — L216–L226
- `def Translator.to_persian_digits` — L229–L231
- `def Translator.to_latin_digits` — L234–L236
- `def get_translator` — L243–L254
- `def tr` — L257–L259

### `main.py`

نقطه ورود برنامه Crypto AI Trader.

ارجاع داخلی: `app/application.py`, `app/core/constants.py`, `app/logging/__init__.py`, `localization/__init__.py`, `signals/strategies/registry.py`, `ui/controllers/__init__.py`, `ui/dialogs/__init__.py`, `ui/themes/__init__.py`, `ui/themes/fonts.py`, `ui/windows/__init__.py`.
- `async def run_check` — L32–L55
- `async def run_signal` — L58–L75
- `def run_gui` — L78–L132
- `def main` — L135–L149

### `market/__init__.py`

لایه داده بازار.


### `market/cache/__init__.py`

حافظه نهان داده بازار.

ارجاع داخلی: `market/cache/memory_cache.py`.
واردکنندگان ایستا: `tests/test_v194_performance.py`.

### `market/cache/memory_cache.py`

حافظه نهان درون‌حافظه‌ای برای داده بازار.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `indicators/engine.py`, `market/cache/__init__.py`, `market/engine.py`.
- `class CacheEntry : Generic[T]` — L29–L38
- `def CacheEntry.is_expired` — L36–L38
- `class MarketCache` — L41–L131
- `def MarketCache.__init__` — L49–L54
- `def MarketCache.make_key` — L57–L59
- `def MarketCache.get` — L61–L77
- `def MarketCache.set` — L79–L84
- `def MarketCache.invalidate` — L86–L89
- `def MarketCache.invalidate_prefix` — L91–L102
- `def MarketCache.clear` — L104–L107
- `def MarketCache._evict` — L109–L119
- `def MarketCache.stats` — L122–L131

### `market/engine.py`

موتور داده بازار (Market Data Engine).

ارجاع داخلی: `app/core/constants.py`, `app/core/events.py`, `app/core/models.py`, `app/database/repositories/candle_repository.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`, `market/cache/memory_cache.py`, `market/providers/base.py`, `market/timeframes.py`.
واردکنندگان ایستا: `ai/tools/market_tools.py`, `app/application.py`, `market/live_feed.py`, `signals/engine.py`, `tests/test_v162_toobit_websocket.py`, `tests/test_v1921_online_and_autotrade.py`.
- `class MarketDataEngine` — L47–L674
- `def MarketDataEngine.__init__` — L56–L85
- `async def MarketDataEngine.start` — L90–L108
- `async def MarketDataEngine.ensure_streaming` — L110–L142
- `async def MarketDataEngine.keepalive` — L144–L158
- `async def MarketDataEngine.stop` — L160–L167
- `def MarketDataEngine.exchange_name` — L173–L175
- `def MarketDataEngine.connection_status` — L178–L180
- `def MarketDataEngine.is_online` — L183–L185
- `def MarketDataEngine.websocket_status` — L188–L190
- `def MarketDataEngine.cache_stats` — L193–L195
- `def MarketDataEngine._update_status` — L197–L211
- `def MarketDataEngine._mark_rest_alive` — L213–L245
- `def MarketDataEngine.add_ticker_listener` — L247–L250
- `def MarketDataEngine.remove_ticker_listener` — L252–L255
- `def MarketDataEngine._handle_ws_status` — L257–L269
- `def MarketDataEngine._handle_live_ticker` — L274–L295
- `def MarketDataEngine._handle_live_candle` — L297–L311
- `async def MarketDataEngine._deduplicated` — L316–L341
- `async def MarketDataEngine.get_symbols` — L346–L364
- `async def MarketDataEngine.get_symbols._fetch` — L358–L362
- `def MarketDataEngine.get_symbol_info` — L366–L368
- `async def MarketDataEngine.get_ticker` — L373–L395
- `async def MarketDataEngine.get_ticker._fetch` — L389–L393
- `def MarketDataEngine._ticker_is_fresh` — L399–L407
- `async def MarketDataEngine.get_current_price` — L409–L431
- `async def MarketDataEngine.get_current_price._fetch` — L425–L429
- `def MarketDataEngine.peek_candles` — L433–L448
- `async def MarketDataEngine.get_all_tickers` — L450–L475
- `async def MarketDataEngine.get_all_tickers._fetch` — L462–L469
- `def MarketDataEngine._persist_ticker` — L477–L493
- `async def MarketDataEngine.get_candles` — L498–L550
- `async def MarketDataEngine.get_candles._fetch` — L523–L532
- `def MarketDataEngine._merge_live_candle` — L552–L569
- `def MarketDataEngine._cache_ttl_for` — L572–L579
- `def MarketDataEngine._persist_candles` — L581–L588
- `def MarketDataEngine._load_stored_candles` — L590–L597
- `async def MarketDataEngine.get_multi_timeframe_candles` — L599–L620
- `async def MarketDataEngine.get_orderbook` — L625–L637
- `async def MarketDataEngine.get_orderbook._fetch` — L632–L635
- `async def MarketDataEngine.subscribe_symbol` — L642–L653
- `async def MarketDataEngine.unsubscribe_symbol` — L655–L661
- `async def MarketDataEngine.set_watchlist_subscriptions` — L663–L674

### `market/exchange_catalog.py`

فهرست صرافی‌های پشتیبانی‌شده و تعویض میان آن‌ها.

واردکنندگان ایستا: `tests/test_toobit_bitpin_providers.py`, `ui/pages/settings_page.py`.
- `class ExchangePreset` — L22–L42
- `def ExchangePreset.is_selectable` — L40–L42
- `def get_exchange` — L136–L146
- `def exchange_keys` — L149–L151
- `def implemented_exchanges` — L154–L156
- `def selectable_choices` — L159–L174

### `market/fiat_rates.py`

نرخ تبدیل دلار (تتر) به تومان.

ارجاع داخلی: `app/core/timeutil.py`, `app/logging/__init__.py`, `market/providers/bitpin/constants.py`.
واردکنندگان ایستا: `ui/controllers/main_controller.py`.
- `class FiatRate` — L47–L63
- `def FiatRate.age_seconds` — L56–L58
- `def FiatRate.is_stale` — L61–L63
- `def _plausible` — L66–L85
- `class FiatRateService` — L88–L265
- `def FiatRateService.__init__` — L98–L107
- `def FiatRateService.set_manual_rate` — L112–L127
- `def FiatRateService.manual_rate` — L130–L132
- `def FiatRateService.cached` — L135–L137
- `async def FiatRateService.get_rate` — L142–L174
- `async def FiatRateService._fetch_from_sources` — L176–L192
- `async def FiatRateService._from_nobitex` — L198–L208
- `async def FiatRateService._from_wallex` — L211–L219
- `async def FiatRateService._from_ramzinex` — L222–L232
- `async def FiatRateService._from_bitpin` — L235–L253
- `def FiatRateService.to_toman` — L258–L265
- `def format_toman` — L268–L283

### `market/live_feed.py`

سرویس قیمت زنده.

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`, `app/core/timeutil.py`, `app/logging/__init__.py`, `market/engine.py`.
واردکنندگان ایستا: `tests/test_market_resilience.py`, `ui/controllers/main_controller.py`.
- `class PriceUpdate` — L40–L66
- `def PriceUpdate.is_up` — L59–L61
- `def PriceUpdate.is_down` — L64–L66
- `class LivePriceFeed` — L69–L307
- `def LivePriceFeed.__init__` — L80–L93
- `async def LivePriceFeed.start` — L98–L105
- `async def LivePriceFeed.stop` — L107–L118
- `def LivePriceFeed.running` — L121–L123
- `def LivePriceFeed.poll_alive` — L126–L135
- `def LivePriceFeed.is_fresh` — L138–L148
- `async def LivePriceFeed.set_streamed_symbols` — L153–L167
- `def LivePriceFeed.get` — L172–L174
- `def LivePriceFeed.snapshot` — L176–L178
- `def LivePriceFeed.symbol_count` — L181–L183
- `def LivePriceFeed.add_listener` — L188–L191
- `def LivePriceFeed.remove_listener` — L193–L196
- `def LivePriceFeed._notify` — L198–L211
- `def LivePriceFeed._store` — L216–L248
- `def LivePriceFeed._on_live_ticker` — L250–L254
- `async def LivePriceFeed._poll_loop` — L256–L291
- `def LivePriceFeed.status` — L296–L307

### `market/providers/__init__.py`

ارائه‌دهندگان صرافی.

ارجاع داخلی: `market/providers/base.py`, `market/providers/registry.py`.

### `market/providers/base.py`

واسط انتزاعی صرافی (Adapter Pattern).

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`.
واردکنندگان ایستا: `market/engine.py`, `market/providers/__init__.py`, `market/providers/bitpin/provider.py`, `market/providers/lbank/provider.py`, `market/providers/registry.py`, `market/providers/toobit/provider.py`, `tests/test_exchange_switching.py`, `tests/test_v162_toobit_websocket.py`.
- `class MarketWebSocketClient : Protocol` — L26–L73
- `def MarketWebSocketClient.status` — L43–L45
- `async def MarketWebSocketClient.start` — L47–L49
- `async def MarketWebSocketClient.stop` — L51–L53
- `async def MarketWebSocketClient.subscribe_ticker` — L55–L57
- `async def MarketWebSocketClient.unsubscribe_ticker` — L59–L61
- `async def MarketWebSocketClient.subscribe_candles` — L63–L65
- `async def MarketWebSocketClient.unsubscribe_candles` — L67–L69
- `async def MarketWebSocketClient.unsubscribe_all` — L71–L73
- `class ProviderCapabilities` — L77–L90
- `class ExchangeProvider : ABC` — L93–L227
- `def ExchangeProvider.capabilities` — L105–L106
- `async def ExchangeProvider.connect` — L112–L113
- `async def ExchangeProvider.close` — L116–L117
- `async def ExchangeProvider.ping` — L120–L121
- `async def ExchangeProvider.get_symbols` — L127–L128
- `async def ExchangeProvider.get_ticker` — L131–L132
- `async def ExchangeProvider.get_all_tickers` — L135–L136
- `async def ExchangeProvider.get_current_price` — L139–L140
- `async def ExchangeProvider.get_ohlcv` — L143–L151
- `async def ExchangeProvider.get_orderbook` — L154–L155
- `def ExchangeProvider.to_exchange_symbol` — L161–L162
- `def ExchangeProvider.from_exchange_symbol` — L165–L166
- `async def ExchangeProvider.get_account_balance` — L171–L178
- `async def ExchangeProvider.get_open_orders` — L180–L182
- `async def ExchangeProvider.get_order_history` — L184–L186
- `async def ExchangeProvider.test_credentials` — L188–L194
- `def ExchangeProvider.create_websocket_client` — L199–L217
- `def ExchangeProvider.supports_timeframe_natively` — L222–L224
- `def ExchangeProvider.__repr__` — L226–L227

### `market/providers/bitpin/__init__.py`

بستهٔ ارائه‌دهندهٔ صرافی ایرانی بیت‌پین.

ارجاع داخلی: `market/providers/bitpin/provider.py`.

### `market/providers/bitpin/constants.py`

ثابت‌های صرافی ایرانی بیت‌پین (Bitpin).

واردکنندگان ایستا: `market/fiat_rates.py`, `market/providers/bitpin/parser.py`, `market/providers/bitpin/provider.py`, `market/providers/bitpin/rest_client.py`.
- `class BitpinEndpoints` — L46–L66

### `market/providers/bitpin/parser.py`

تبدیل پاسخ‌های بیت‌پین به مدل‌های داخلی برنامه.

ارجاع داخلی: `app/core/models.py`, `market/providers/bitpin/constants.py`.
واردکنندگان ایستا: `market/providers/bitpin/provider.py`, `tests/test_toobit_bitpin_providers.py`.
- `def _to_float` — L31–L38
- `def _to_int` — L41–L46
- `class BitpinParser` — L49–L271
- `def BitpinParser.to_exchange_symbol` — L56–L58
- `def BitpinParser.to_internal_symbol` — L61–L63
- `def BitpinParser.parse_symbols` — L69–L101
- `def BitpinParser.parse_ticker` — L107–L122
- `def BitpinParser.parse_tickers` — L125–L133
- `def BitpinParser.find_ticker` — L136–L149
- `def BitpinParser.parse_orderbook` — L155–L175
- `def BitpinParser._parse_level` — L178–L185
- `def BitpinParser.candles_from_matches` — L191–L233
- `def BitpinParser.parse_balances` — L239–L271

### `market/providers/bitpin/provider.py`

پیاده‌سازی ExchangeProvider برای صرافی ایرانی بیت‌پین.

ارجاع داخلی: `app/core/models.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`, `market/providers/base.py`, `market/providers/bitpin/constants.py`, `market/providers/bitpin/parser.py`, `market/providers/bitpin/rest_client.py`, `market/timeframes.py`.
واردکنندگان ایستا: `market/providers/bitpin/__init__.py`, `market/providers/registry.py`, `tests/test_toobit_bitpin_providers.py`, `tests/test_v162_toobit_websocket.py`.
- `class BitpinProvider : ExchangeProvider` — L37–L268
- `def BitpinProvider.__init__` — L43–L60
- `def BitpinProvider.capabilities` — L66–L77
- `async def BitpinProvider.connect` — L79–L81
- `async def BitpinProvider.close` — L83–L85
- `async def BitpinProvider.ping` — L87–L94
- `def BitpinProvider.to_exchange_symbol` — L99–L101
- `def BitpinProvider.from_exchange_symbol` — L103–L105
- `async def BitpinProvider.get_symbols` — L110–L117
- `async def BitpinProvider.get_ticker` — L119–L137
- `async def BitpinProvider.get_all_tickers` — L139–L145
- `async def BitpinProvider.get_current_price` — L147–L155
- `async def BitpinProvider.get_usdt_irt_rate` — L157–L169
- `async def BitpinProvider.get_ohlcv` — L171–L201
- `async def BitpinProvider.get_orderbook` — L203–L209
- `async def BitpinProvider.fetch_wallets` — L214–L216
- `async def BitpinProvider.get_account_balance` — L218–L225
- `async def BitpinProvider.get_open_orders` — L227–L237
- `async def BitpinProvider.get_order_history` — L239–L249
- `async def BitpinProvider.test_credentials` — L251–L268
- `def _as_rows` — L271–L280
- `def create_bitpin_provider` — L283–L285

### `market/providers/bitpin/rest_client.py`

کلاینت HTTP صرافی بیت‌پین با مدیریت خودکار توکن.

ارجاع داخلی: `app/exceptions/__init__.py`, `app/logging/__init__.py`, `market/providers/bitpin/constants.py`.
واردکنندگان ایستا: `market/providers/bitpin/provider.py`.
- `class BitpinRestClient` — L45–L299
- `def BitpinRestClient.__init__` — L48–L68
- `async def BitpinRestClient.connect` — L73–L83
- `async def BitpinRestClient.close` — L85–L92
- `async def BitpinRestClient._client` — L94–L99
- `def BitpinRestClient.has_credentials` — L102–L104
- `def BitpinRestClient.is_authenticated` — L107–L109
- `def BitpinRestClient._token_expired` — L112–L117
- `async def BitpinRestClient.get` — L122–L136
- `async def BitpinRestClient.authenticate` — L141–L181
- `async def BitpinRestClient._refresh` — L183–L216
- `async def BitpinRestClient.ensure_token` — L218–L224
- `async def BitpinRestClient.get_private` — L229–L260
- `def BitpinRestClient._unwrap` — L265–L299

### `market/providers/lbank/__init__.py`

پیاده‌سازی صرافی LBank.

ارجاع داخلی: `market/providers/lbank/constants.py`, `market/providers/lbank/parser.py`, `market/providers/lbank/provider.py`, `market/providers/lbank/websocket_client.py`.

### `market/providers/lbank/constants.py`

ثابت‌ها و نگاشت‌های اختصاصی صرافی LBank.

واردکنندگان ایستا: `market/providers/lbank/__init__.py`, `market/providers/lbank/provider.py`, `market/providers/lbank/rest_client.py`, `market/providers/lbank/websocket_client.py`, `tests/test_v1915_bugfixes.py`.
- `class LBankEndpoints` — L23–L43
- `class LBankContractEndpoints` — L55–L62

### `market/providers/lbank/parser.py`

مبدل پاسخ خام LBank به مدل‌های داخلی نرم‌افزار.

ارجاع داخلی: `app/core/models.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `market/providers/lbank/__init__.py`, `market/providers/lbank/provider.py`, `market/providers/lbank/websocket_client.py`.
- `class LBankParser` — L25–L327
- `def LBankParser.to_internal_symbol` — L37–L44
- `def LBankParser.to_exchange_symbol` — L47–L51
- `def LBankParser.parse_symbols` — L57–L87
- `def LBankParser.parse_klines` — L93–L128
- `def LBankParser.parse_ticker` — L134–L157
- `def LBankParser.parse_tickers` — L160–L168
- `def LBankParser.parse_price_list` — L171–L188
- `def LBankParser.parse_orderbook` — L194–L219
- `def LBankParser.parse_orderbook._levels` — L199–L210
- `def LBankParser.parse_ws_tick` — L225–L246
- `def LBankParser.parse_ws_kbar` — L249–L275
- `def LBankParser.parse_ws_depth` — L278–L286
- `def LBankParser._safe_float` — L292–L299
- `def LBankParser._safe_int` — L302–L309
- `def LBankParser._parse_iso_seconds` — L312–L327

### `market/providers/lbank/provider.py`

پیاده‌سازی واسط ExchangeProvider برای صرافی LBank.

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`, `market/providers/base.py`, `market/providers/lbank/constants.py`, `market/providers/lbank/parser.py`, `market/providers/lbank/rest_client.py`, `market/providers/lbank/websocket_client.py`, `market/timeframes.py`.
واردکنندگان ایستا: `market/providers/lbank/__init__.py`, `market/providers/registry.py`, `tests/test_v156_fixes.py`, `tests/test_v162_toobit_websocket.py`, `tests/test_v1915_bugfixes.py`.
- `class LBankProvider : ExchangeProvider` — L45–L494
- `def LBankProvider.__init__` — L56–L82
- `def LBankProvider.capabilities` — L88–L90
- `def LBankProvider.rest_client` — L93–L95
- `async def LBankProvider.connect` — L97–L99
- `async def LBankProvider.close` — L101–L103
- `async def LBankProvider.ping` — L105–L116
- `async def LBankProvider.get_server_time` — L118–L121
- `def LBankProvider.to_exchange_symbol` — L126–L128
- `def LBankProvider.from_exchange_symbol` — L130–L132
- `async def LBankProvider.get_symbols` — L137–L159
- `async def LBankProvider.get_ticker` — L161–L168
- `async def LBankProvider.get_all_tickers` — L170–L180
- `async def LBankProvider.get_all_prices` — L182–L192
- `async def LBankProvider.get_current_price` — L194–L208
- `async def LBankProvider.get_ohlcv` — L210–L242
- `async def LBankProvider._fetch_native_klines` — L244–L297
- `async def LBankProvider.get_orderbook` — L299–L311
- `async def LBankProvider.get_account_balance` — L316–L324
- `def LBankProvider._parse_balances` — L327–L359
- `async def LBankProvider.get_futures_balance` — L361–L375
- `async def LBankProvider.fetch_futures_balance` — L377–L416
- `def LBankProvider._parse_futures_balances` — L419–L459
- `async def LBankProvider.test_credentials` — L461–L474
- `def LBankProvider.create_websocket_client` — L480–L494
- `def create_lbank_provider` — L497–L501

### `market/providers/lbank/rest_client.py`

کلاینت REST صرافی LBank.

ارجاع داخلی: `app/exceptions/__init__.py`, `app/exceptions/errors.py`, `app/logging/__init__.py`, `market/providers/lbank/constants.py`, `market/rate_limiter.py`.
واردکنندگان ایستا: `market/providers/lbank/provider.py`.
- `class LBankRestClient` — L47–L336
- `def LBankRestClient.__init__` — L55–L73
- `async def LBankRestClient.open` — L78–L87
- `async def LBankRestClient.close` — L89–L97
- `def LBankRestClient.set_credentials` — L99–L102
- `def LBankRestClient.has_credentials` — L105–L107
- `def LBankRestClient.update_limits` — L109–L114
- `async def LBankRestClient.get` — L119–L144
- `async def LBankRestClient.get._do_request` — L127–L137
- `async def LBankRestClient.post_signed` — L149–L199
- `async def LBankRestClient.post_signed._do_request` — L178–L192
- `async def LBankRestClient.post_contract_signed` — L201–L255
- `async def LBankRestClient.post_contract_signed._do_request` — L239–L248
- `async def LBankRestClient._contract_client` — L257–L265
- `def LBankRestClient._build_signature` — L267–L278
- `def LBankRestClient._random_echostr` — L281–L288
- `def LBankRestClient._handle_response` — L293–L336

### `market/providers/lbank/websocket_client.py`

کلاینت WebSocket صرافی LBank با اتصال مجدد خودکار.

ارجاع داخلی: `app/core/constants.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`, `market/providers/lbank/constants.py`, `market/providers/lbank/parser.py`, `market/timeframes.py`.
واردکنندگان ایستا: `market/providers/lbank/__init__.py`, `market/providers/lbank/provider.py`, `tests/test_v162_toobit_websocket.py`.
- `def _normalize` — L54–L65
- `class Subscription` — L70–L100
- `def Subscription.to_message` — L82–L93
- `def Subscription.to_unsubscribe_message` — L95–L100
- `class LBankWebSocketClient` — L103–L396
- `def LBankWebSocketClient.__init__` — L111–L134
- `def LBankWebSocketClient.status` — L140–L142
- `def LBankWebSocketClient.is_connected` — L145–L147
- `def LBankWebSocketClient.reconnect_count` — L150–L152
- `def LBankWebSocketClient._set_status` — L154–L164
- `async def LBankWebSocketClient.start` — L169–L175
- `async def LBankWebSocketClient.stop` — L177–L190
- `async def LBankWebSocketClient._run_forever` — L192–L229
- `async def LBankWebSocketClient._receive_loop` — L231–L249
- `async def LBankWebSocketClient._handle_message` — L251–L283
- `def LBankWebSocketClient._safe_callback` — L286–L291
- `def LBankWebSocketClient._timeframe_from_slot` — L294–L299
- `async def LBankWebSocketClient._resubscribe_all` — L304–L315
- `async def LBankWebSocketClient._send_subscription` — L317–L323
- `async def LBankWebSocketClient.subscribe_ticker` — L325–L332
- `async def LBankWebSocketClient.unsubscribe_ticker` — L334–L339
- `async def LBankWebSocketClient.subscribe_candles` — L341–L359
- `async def LBankWebSocketClient.unsubscribe_candles` — L361–L369
- `async def LBankWebSocketClient.subscribe_orderbook` — L371–L378
- `async def LBankWebSocketClient.unsubscribe_all` — L380–L386
- `def LBankWebSocketClient.subscription_count` — L389–L391
- `def LBankWebSocketClient.supported_timeframes` — L394–L396

### `market/providers/registry.py`

ثبت‌کننده صرافی‌ها (Factory Pattern).

ارجاع داخلی: `app/exceptions/__init__.py`, `app/logging/__init__.py`, `market/providers/base.py`, `market/providers/bitpin/provider.py`, `market/providers/lbank/provider.py`, `market/providers/toobit/provider.py`.
واردکنندگان ایستا: `app/application.py`, `market/providers/__init__.py`, `tests/test_exchange_switching.py`, `tests/test_toobit_bitpin_providers.py`, `ui/controllers/main_controller.py`.
- `class ExchangeRegistry` — L23–L59
- `def ExchangeRegistry.__init__` — L26–L27
- `def ExchangeRegistry.register` — L29–L40
- `def ExchangeRegistry.create` — L42–L51
- `def ExchangeRegistry.available` — L53–L55
- `def ExchangeRegistry.is_registered` — L57–L59
- `def register_builtin_providers` — L66–L79

### `market/providers/toobit/__init__.py`

بستهٔ ارائه‌دهندهٔ صرافی Toobit.

ارجاع داخلی: `market/providers/toobit/provider.py`.

### `market/providers/toobit/constants.py`

ثابت‌های صرافی Toobit.

واردکنندگان ایستا: `market/providers/toobit/provider.py`, `market/providers/toobit/rest_client.py`, `market/providers/toobit/websocket_client.py`.
- `class ToobitEndpoints` — L30–L48

### `market/providers/toobit/parser.py`

تبدیل پاسخ‌های Toobit به مدل‌های داخلی برنامه.

ارجاع داخلی: `app/core/models.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `market/providers/toobit/provider.py`, `market/providers/toobit/websocket_client.py`, `tests/test_toobit_bitpin_providers.py`, `tests/test_v162_toobit_websocket.py`.
- `def _as_float` — L29–L36
- `def _as_int` — L39–L46
- `class ToobitParser` — L49–L389
- `def ToobitParser.to_internal_symbol` — L53–L68
- `def ToobitParser.to_exchange_symbol` — L71–L73
- `def ToobitParser.parse_symbols` — L79–L117
- `def ToobitParser._precisions` — L120–L140
- `def ToobitParser.parse_ticker` — L146–L164
- `def ToobitParser._change_percent` — L167–L182
- `def ToobitParser.parse_tickers` — L185–L195
- `def ToobitParser.parse_ws_ticker` — L201–L229
- `def ToobitParser.parse_ws_kline` — L232–L284
- `def ToobitParser.parse_price_map` — L287–L298
- `def ToobitParser.parse_candles` — L304–L328
- `def ToobitParser.parse_orderbook` — L334–L354
- `def ToobitParser.parse_balances` — L360–L389
- `def _decimals` — L392–L412

### `market/providers/toobit/provider.py`

پیاده‌سازی ExchangeProvider برای صرافی Toobit.

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`, `market/providers/base.py`, `market/providers/toobit/constants.py`, `market/providers/toobit/parser.py`, `market/providers/toobit/rest_client.py`, `market/providers/toobit/websocket_client.py`, `market/timeframes.py`.
واردکنندگان ایستا: `market/providers/registry.py`, `market/providers/toobit/__init__.py`, `tests/test_toobit_bitpin_providers.py`, `tests/test_v162_toobit_websocket.py`.
- `class ToobitProvider : ExchangeProvider` — L41–L312
- `def ToobitProvider.__init__` — L47–L65
- `def ToobitProvider.capabilities` — L71–L80
- `async def ToobitProvider.connect` — L82–L84
- `async def ToobitProvider.close` — L86–L88
- `async def ToobitProvider.ping` — L90–L97
- `def ToobitProvider.to_exchange_symbol` — L102–L104
- `def ToobitProvider.from_exchange_symbol` — L106–L111
- `async def ToobitProvider.get_symbols` — L116–L126
- `async def ToobitProvider.get_ticker` — L128–L142
- `async def ToobitProvider.get_all_tickers` — L144–L150
- `async def ToobitProvider.get_current_price` — L152–L165
- `async def ToobitProvider.get_ohlcv` — L167–L196
- `async def ToobitProvider._fetch_candles` — L198–L211
- `async def ToobitProvider.get_orderbook` — L213–L220
- `async def ToobitProvider.fetch_account` — L225–L231
- `async def ToobitProvider.get_account_balance` — L233–L245
- `async def ToobitProvider.get_open_orders` — L247–L257
- `async def ToobitProvider.get_order_history` — L259–L269
- `async def ToobitProvider.test_credentials` — L271–L287
- `def ToobitProvider.create_websocket_client` — L293–L312
- `def create_toobit_provider` — L315–L317

### `market/providers/toobit/rest_client.py`

کلاینت HTTP صرافی Toobit.

ارجاع داخلی: `app/exceptions/__init__.py`, `app/logging/__init__.py`, `market/providers/toobit/constants.py`.
واردکنندگان ایستا: `market/providers/toobit/provider.py`, `tests/test_toobit_bitpin_providers.py`.
- `def _scrub` — L50–L52
- `class ToobitRestClient` — L55–L224
- `def ToobitRestClient.__init__` — L58–L72
- `async def ToobitRestClient.connect` — L77–L84
- `async def ToobitRestClient.close` — L86–L90
- `async def ToobitRestClient._client` — L92–L97
- `def ToobitRestClient.has_credentials` — L100–L102
- `async def ToobitRestClient.get` — L107–L130
- `def ToobitRestClient._sign` — L135–L148
- `async def ToobitRestClient.get_signed` — L150–L178
- `def ToobitRestClient._unwrap` — L183–L224
- `def _safe_int` — L227–L232
- `async def _sleep_backoff` — L235–L239

### `market/providers/toobit/websocket_client.py`

کلاینت WebSocket صرافی Toobit با اتصال مجدد خودکار.

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`, `market/providers/toobit/constants.py`, `market/providers/toobit/parser.py`, `market/timeframes.py`.
واردکنندگان ایستا: `market/providers/toobit/provider.py`, `tests/test_v162_toobit_websocket.py`.
- `def _normalize` — L72–L82
- `class ToobitSubscription` — L86–L105
- `def ToobitSubscription.to_message` — L98–L105
- `class ToobitWebSocketClient` — L108–L405
- `def ToobitWebSocketClient.__init__` — L116–L137
- `def ToobitWebSocketClient.status` — L143–L145
- `def ToobitWebSocketClient.is_connected` — L148–L150
- `def ToobitWebSocketClient.reconnect_count` — L153–L155
- `def ToobitWebSocketClient.subscription_count` — L158–L160
- `def ToobitWebSocketClient._set_status` — L162–L172
- `def ToobitWebSocketClient._safe_callback` — L174–L179
- `async def ToobitWebSocketClient.start` — L184–L190
- `async def ToobitWebSocketClient.stop` — L192–L205
- `async def ToobitWebSocketClient._run_forever` — L207–L253
- `async def ToobitWebSocketClient._receive_loop` — L255–L275
- `async def ToobitWebSocketClient._handle_message` — L277–L313
- `async def ToobitWebSocketClient._resubscribe_all` — L318–L331
- `async def ToobitWebSocketClient._send_subscription` — L333–L342
- `async def ToobitWebSocketClient.subscribe_ticker` — L344–L353
- `async def ToobitWebSocketClient.unsubscribe_ticker` — L355–L362
- `async def ToobitWebSocketClient.subscribe_candles` — L364–L385
- `async def ToobitWebSocketClient.unsubscribe_candles` — L387–L397
- `async def ToobitWebSocketClient.unsubscribe_all` — L399–L405

### `market/quality.py`

موتور کیفیت داده (Data Quality Engine).

ارجاع داخلی: `app/core/models.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`, `market/timeframes.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`, `signals/prediction/features.py`, `signals/prediction/horizons.py`, `tests/test_predictive_phase1.py`.
- `class IssueKind : str, Enum` — L35–L47
- `class Severity : str, Enum` — L50–L54
- `class QualityIssue` — L72–L79
- `class QualityReport` — L83–L144
- `def QualityReport.usable` — L105–L110
- `def QualityReport.counts_by_severity` — L112–L117
- `def QualityReport.to_dict` — L119–L144
- `def timeframe_seconds` — L147–L164
- `def _row_is_invalid` — L167–L182
- `def inspect_candles` — L185–L313
- `def clean_candles` — L316–L349

### `market/rate_limiter.py`

محدودکننده نرخ درخواست (Rate Limiter) و کمک‌کننده تلاش مجدد (Retry).

ارجاع داخلی: `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `market/providers/lbank/rest_client.py`.
- `class AsyncRateLimiter` — L29–L65
- `def AsyncRateLimiter.__init__` — L38–L43
- `async def AsyncRateLimiter.acquire` — L45–L60
- `def AsyncRateLimiter.update_rate` — L62–L65
- `async def retry_async` — L68–L106

### `market/resilience.py`

نظارت‌چی اتصال (Connection Supervisor) — قلب قابلیت «همیشه آنلاین».

ارجاع داخلی: `app/core/events.py`, `app/core/timeutil.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `tests/test_market_resilience.py`, `ui/controllers/main_controller.py`.
- `class ConnectivityState : str, Enum` — L57–L62
- `class RevivalAttempt` — L66–L72
- `class ConnectionSupervisor` — L76–L253
- `async def ConnectionSupervisor.start` — L109–L115
- `async def ConnectionSupervisor.stop` — L117–L126
- `def ConnectionSupervisor.running` — L129–L131
- `def ConnectionSupervisor._poll_alive` — L136–L140
- `async def ConnectionSupervisor._revive` — L142–L164
- `def ConnectionSupervisor._next_delay` — L166–L172
- `def ConnectionSupervisor._evaluate` — L174–L200
- `def ConnectionSupervisor._publish_state` — L202–L218
- `async def ConnectionSupervisor._watch_loop` — L220–L237
- `def ConnectionSupervisor.status` — L242–L253
- `def _safe_age` — L256–L262

### `market/timeframes.py`

موتور تایم‌فریم (Timeframe Engine).

ارجاع داخلی: `app/core/models.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `market/engine.py`, `market/providers/bitpin/provider.py`, `market/providers/lbank/provider.py`, `market/providers/lbank/websocket_client.py`, `market/providers/toobit/provider.py`, `market/providers/toobit/websocket_client.py`, `market/quality.py`, `tests/test_chat_page.py`, `tests/test_timeframes.py`, `tests/test_ui_wiring.py`, `ui/charts/price_chart.py`, `ui/dialogs/coin_detail_dialog.py`, `ui/pages/analysis_page.py`, `ui/pages/chat_page.py`, `ui/pages/signals_page.py`.
- `class Timeframe` — L29–L45
- `def Timeframe.minutes` — L43–L45
- `def get_timeframe` — L72–L91
- `def normalize_timeframe` — L94–L107
- `def timeframe_seconds` — L110–L112
- `def align_timestamp` — L115–L137
- `def aggregate_candles` — L140–L197
- `def find_aggregation_source` — L200–L223
- `def candles_needed` — L226–L234

### `migrations/env.py`

پیکربندی زمان اجرای Alembic.

ارجاع داخلی: `app/core/paths.py`, `app/database/models.py`, `backup/__init__.py`.
- `def _backup_before_migration` — L41–L63
- `def run_migrations_offline` — L66–L76
- `def run_migrations_online` — L79–L97

### `migrations/versions/20260908_1316_initial_schema.py`

initial schema

- `def upgrade` — L22–L245
- `def downgrade` — L250–L296

### `migrations/versions/20260911_0817_chat_conversations.py`

chat conversations

- `def upgrade` — L22–L52
- `def downgrade` — L57–L67

### `migrations/versions/20260911_1040_users_sessions_exchange_accounts_paper_.py`

افزودن جداول کاربران، نشست‌ها، حساب‌های صرافی و معاملات کاغذی

- `def upgrade` — L25–L128
- `def downgrade` — L133–L158

### `migrations/versions/20260914_0700_signal_outcomes.py`

افزودن جدول نتیجهٔ واقعی سیگنال‌ها.

- `def upgrade` — L23–L61
- `def downgrade` — L64–L70

### `migrations/versions/20260915_0900_signal_validity_and_reviews.py`

پنجرهٔ اعتبار سیگنال و جدول بازبینی هوش مصنوعی.

- `def upgrade` — L29–L62
- `def downgrade` — L65–L73

### `migrations/versions/20260920_1200_trade_last_price.py`

افزودن ستون آخرین قیمت به معاملات کاغذی.

- `def upgrade` — L21–L26
- `def downgrade` — L29–L32

### `migrations/versions/20260920_1400_signal_forecast.py`

افزودن ستون پیش‌بینی به جدول سیگنال‌ها.

- `def upgrade` — L21–L26
- `def downgrade` — L29–L32

### `migrations/versions/20260922_1600_prediction_records.py`

افزودن جدول پیش‌بینی‌های موتور هوش پیش‌بینی.

- `def upgrade` — L24–L61
- `def downgrade` — L64–L70

### `mobile/app/__init__.py`

هستهٔ نسخهٔ موبایل — سبک، بدون وابستگی سنگین، هم‌ارز با دسکتاپ.

واردکنندگان ایستا: `mobile/app/signal_lite.py`, `tests/test_v1912_mobile.py`.

### `mobile/app/indicators_lite.py`

موتور اندیکاتور «سبک» — همان ریاضی، بدون pandas و numpy.

واردکنندگان ایستا: `mobile/app/signal_lite.py`, `tests/test_v1912_mobile.py`.
- `def _ewm` — L33–L48
- `def ema` — L51–L55
- `def sma` — L58–L69
- `def rsi` — L72–L106
- `def macd` — L109–L130
- `def atr` — L133–L157
- `def bollinger` — L160–L184
- `def stochastic` — L187–L211

### `mobile/app/market_lite.py`

دریافت دادهٔ بازار روی موبایل — فقط با کتابخانهٔ استاندارد.

- `class MarketError : Exception` — L42–L43
- `def _get` — L46–L69
- `def to_lbank_symbol` — L72–L74
- `def fetch_candles` — L77–L108
- `def fetch_price` — L111–L119

### `mobile/app/signal_lite.py`

موتور سیگنال موبایل — همان منطق دسکتاپ، بدون وابستگی سنگین.

ارجاع داخلی: `mobile/app/__init__.py`, `mobile/app/indicators_lite.py`.
واردکنندگان ایستا: `tests/test_v1912_mobile.py`.
- `class MobileSignal` — L29–L58
- `def MobileSignal.is_tradeable` — L45–L47
- `def MobileSignal.risk_reward` — L50–L58
- `def analyse` — L73–L184

### `mobile/main.py`

معامله‌گر هوشمند رمزارز — نسخهٔ موبایل (اندروید).

- `def shape` — L59–L72
- `class SignalCard : BoxLayout` — L75–L132
- `def SignalCard.__init__` — L78–L116
- `def SignalCard._add` — L118–L132
- `class TraderApp : App` — L135–L281
- `def TraderApp.build` — L138–L219
- `def TraderApp._set_status` — L225–L226
- `def TraderApp._set_busy` — L228–L233
- `def TraderApp._set_busy.apply` — L229–L231
- `def TraderApp._show` — L235–L241
- `def TraderApp._show.apply` — L236–L239
- `def TraderApp.on_analyse` — L243–L250
- `def TraderApp.on_scan` — L252–L258
- `def TraderApp._work` — L260–L281

### `mobile/version.py`


### `reports/__init__.py`

لایه گزارش‌گیری.

ارجاع داخلی: `reports/builder.py`, `reports/exporters.py`.
واردکنندگان ایستا: `app/application.py`, `tests/test_reports.py`.

### `reports/builder.py`

گردآوری داده گزارش.

ارجاع داخلی: `app/core/constants.py`, `app/database/repositories/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `reports/__init__.py`, `reports/exporters.py`.
- `class ReportData` — L24–L72
- `def ReportData.is_empty` — L43–L45
- `def ReportData.period_label` — L48–L52
- `def ReportData.to_dict` — L54–L72
- `class ReportBuilder` — L95–L214
- `def ReportBuilder.__init__` — L104–L105
- `def ReportBuilder.build_signal_report` — L107–L162
- `def ReportBuilder._summarize` — L165–L199
- `def ReportBuilder.build_statistics_report` — L201–L214

### `reports/exporters.py`

خروجی‌گیری گزارش در قالب‌های مختلف.

ارجاع داخلی: `app/core/paths.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`, `reports/builder.py`.
واردکنندگان ایستا: `reports/__init__.py`.
- `class ReportExporter` — L37–L364
- `def ReportExporter.__init__` — L46–L47
- `def ReportExporter.export` — L52–L83
- `def ReportExporter._default_path` — L85–L90
- `def ReportExporter._write_csv` — L96–L110
- `def ReportExporter._write_xlsx` — L116–L165
- `def ReportExporter._write_json` — L171–L176
- `def ReportExporter._write_pdf` — L182–L279
- `def ReportExporter._write_html` — L285–L354
- `def ReportExporter.export_all` — L356–L364

### `reports/persian_pdf.py`

تولید PDF فارسی با شکل‌دهی درست حروف.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `tests/test_persian_pdf.py`, `ui/controllers/main_controller.py`.
- `def has_persian` — L57–L59
- `def register_fonts` — L62–L97
- `def shape` — L100–L117
- `def wrap_persian` — L120–L166
- `def wrap_persian.width_of` — L142–L144
- `def wrap_persian.width_of` — L146–L148
- `def shape_paragraph` — L169–L179
- `def build_analysis_pdf` — L182–L353

### `signals/__init__.py`

لایه تولید سیگنال.

ارجاع داخلی: `signals/engine.py`, `signals/risk_engine.py`, `signals/strategies/base.py`, `signals/strategies/registry.py`.
واردکنندگان ایستا: `app/application.py`, `signals/engine.py`, `tests/test_signal_engine.py`, `tests/test_v190_position_sizing.py`, `tests/test_v1917_trust_and_trades.py`, `tests/test_v194_performance.py`.
- `def __getattr__` — L52–L69
- `def __dir__` — L72–L74

### `signals/alerts.py`

هشدار قیمت و هشدار سیگنال.

واردکنندگان ایستا: `tests/test_v1918_alerts.py`, `ui/controllers/main_controller.py`.
- `class Alert` — L37–L147
- `def Alert.is_valid` — L57–L76
- `def Alert.matches_price` — L78–L86
- `def Alert.matches_signal` — L88–L101
- `def Alert.describe` — L103–L109
- `def Alert.as_dict` — L111–L124
- `def Alert.from_dict` — L127–L147
- `class AlertHit` — L151–L156
- `class AlertBook` — L160–L272
- `def AlertBook.from_list` — L173–L183
- `def AlertBook.as_list` — L185–L187
- `def AlertBook.add` — L189–L196
- `def AlertBook.remove` — L198–L202
- `def AlertBook.rearm` — L204–L211
- `def AlertBook.active_symbols` — L213–L228
- `def AlertBook.check_prices` — L230–L250
- `def AlertBook.check_signal` — L252–L272

### `signals/auto_scanner.py`

سیگنال‌گیری خودکار و دوره‌ای.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `tests/test_v190_account_and_auto_scan.py`, `tests/test_v196_fixes.py`, `ui/controllers/main_controller.py`.
- `def clamp_interval` — L58–L71
- `class AutoScanConfig` — L75–L123
- `def AutoScanConfig.normalized` — L95–L106
- `def AutoScanConfig.from_settings` — L109–L123
- `class ScanJob` — L127–L135
- `class AutoScanScheduler` — L139–L358
- `def AutoScanScheduler.due` — L170–L206
- `def AutoScanScheduler.seconds_until_next` — L208–L241
- `def AutoScanScheduler._elapsed` — L243–L247
- `def AutoScanScheduler.start` — L252–L255
- `def AutoScanScheduler.complete` — L257–L282
- `def AutoScanScheduler.fail` — L284–L296
- `def AutoScanScheduler._rank` — L298–L317
- `def AutoScanScheduler._refresh_focus` — L319–L330
- `def AutoScanScheduler.apply_config` — L335–L343
- `def AutoScanScheduler.reset` — L345–L351
- `def AutoScanScheduler.next_run_at` — L353–L358

### `signals/confidence.py`

مدل «میزان اطمینان» واقع‌بینانه.

واردکنندگان ایستا: `signals/engine.py`, `tests/test_v1917_trust_and_trades.py`.
- `class ConfidenceBreakdown` — L63–L97
- `def ConfidenceBreakdown.as_dict` — L83–L97
- `def coverage_cap` — L100–L104
- `def timeframe_cap` — L107–L111
- `def historical_win_rate` — L114–L148
- `def compute` — L151–L212

### `signals/engine.py`

موتور تولید سیگنال.

ارجاع داخلی: `ai/agent/analyst.py`, `app/core/constants.py`, `app/core/models.py`, `app/exceptions/__init__.py`, `app/logging/__init__.py`, `indicators/engine.py`, `indicators/support_resistance.py`, `market/engine.py`, `signals/__init__.py`, `signals/confidence.py`, `signals/forecast.py`, `signals/risk_engine.py`, `signals/strategies/base.py`, `signals/strategies/registry.py`, `signals/validity.py`.
واردکنندگان ایستا: `signals/__init__.py`, `tests/test_v1917_trust_and_trades.py`.
- `class SignalEngine` — L82–L656
- `def SignalEngine.__init__` — L89–L108
- `def SignalEngine.risk_engine` — L111–L113
- `def SignalEngine.set_risk_parameters` — L115–L117
- `async def SignalEngine.generate` — L122–L296
- `def SignalEngine._attach_forecast` — L299–L339
- `def SignalEngine._stamp_validity` — L342–L355
- `async def SignalEngine.enrich_with_ai` — L360–L384
- `async def SignalEngine._analyze_timeframe` — L389–L414
- `def SignalEngine._confidence_buckets` — L419–L434
- `def SignalEngine._aggregate` — L436–L521
- `def SignalEngine._decide` — L524–L530
- `def SignalEngine._pick_primary` — L536–L550
- `def SignalEngine._higher_timeframe_trend` — L553–L560
- `def SignalEngine._atr_of` — L563–L569
- `def SignalEngine._structure_type` — L572–L575
- `def SignalEngine._build_reason` — L578–L591
- `def SignalEngine._build_invalidation` — L594–L608
- `def SignalEngine._wait_signal` — L610–L656

### `signals/forecast.py`

پیش‌بینی تایم‌فریم بعدی.

ارجاع داخلی: `app/core/constants.py`.
واردکنندگان ایستا: `ai/tools/market_tools.py`, `signals/engine.py`, `signals/scorecard.py`, `tests/test_v1917_forecast.py`.
- `class HorizonForecast` — L59–L82
- `def HorizonForecast.as_dict` — L71–L82
- `class Forecast` — L86–L103
- `def Forecast.as_dict` — L95–L103
- `def _atr_from_candles` — L106–L127
- `def _bias_label` — L130–L138
- `def forecast_next` — L141–L260
- `def score_forecast` — L262–L335

### `signals/outcome_tracker.py`

ردیابی نتیجهٔ واقعی سیگنال‌ها (مورد ۱.۵ نقشهٔ راه).

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `app/application.py`, `app/database/repositories/outcome_repository.py`, `tests/test_v191_outcome_tracking.py`.
- `def as_utc` — L73–L81
- `def expiry_for` — L84–L93
- `class PriceWindow` — L97–L119
- `def PriceWindow.ceiling` — L111–L113
- `def PriceWindow.floor` — L116–L119
- `class OutcomeState` — L123–L162
- `def OutcomeState.is_long` — L150–L152
- `def OutcomeState.closed` — L155–L157
- `def OutcomeState.risk_distance` — L160–L162
- `def percent_change` — L165–L175
- `def update_outcome` — L178–L233
- `def _stop_touched` — L236–L240
- `def _count_targets` — L243–L255
- `def _close` — L258–L272
- `def _to_r` — L275–L286
- `def summarize` — L292–L339
- `def group_by` — L342–L353
- `def confidence_buckets` — L356–L369
- `def _status` — L372–L376

### `signals/paper_trader.py`

دفتر معاملهٔ کاغذی (تمرینی).

ارجاع داخلی: `app/core/timeutil.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `tests/test_paper_trader.py`, `tests/test_v154_security_money.py`, `ui/controllers/main_controller.py`.
- `class PaperPosition` — L34–L85
- `def PaperPosition.to_dict` — L49–L63
- `def PaperPosition.from_dict` — L66–L85
- `class OrderExecutor : Protocol` — L88–L98
- `async def OrderExecutor.place_order` — L96–L98
- `class PaperTrader` — L101–L261
- `def PaperTrader.__init__` — L111–L113
- `def PaperTrader.live_trading_enabled` — L116–L118
- `def PaperTrader._load` — L123–L133
- `def PaperTrader._save` — L135–L138
- `def PaperTrader.open_from_signal` — L143–L191
- `def PaperTrader.open_positions` — L193–L199
- `def PaperTrader.all_positions` — L201–L203
- `def PaperTrader.close_position` — L205–L213
- `def PaperTrader.clear` — L215–L217
- `def PaperTrader._pick_entry` — L223–L241
- `def PaperTrader._position_size` — L244–L261

### `signals/position_sizing.py`

محاسبهٔ حجم پوزیشن.

واردکنندگان ایستا: `tests/test_v190_position_sizing.py`, `ui/widgets/position_calculator.py`.
- `class PositionPlan` — L36–L77
- `def calculate_position` — L80–L168
- `def required_win_rate` — L171–L180
- `def breakeven_price` — L183–L196
- `def _validate` — L202–L214
- `def _empty_plan` — L217–L233
- `def _liquidation` — L236–L254
- `def _collect_warnings` — L257–L304

### `signals/prediction/__init__.py`

بستهٔ موتور هوش پیش‌بینی (Predictive Intelligence Engine).

ارجاع داخلی: `signals/prediction/engine.py`, `signals/prediction/features.py`, `signals/prediction/horizons.py`, `signals/prediction/scoring.py`, `signals/prediction/store.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`.

### `signals/prediction/anomaly.py`

تشخیص آنومالی و آلفای زودهنگام — خواسته‌های ۱۸ و ۴۰.

ارجاع داخلی: `app/core/models.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`, `tests/test_predictive_phase2_5.py`.
- `class MetricAnomaly` — L35–L50
- `def MetricAnomaly.to_dict` — L43–L50
- `class AnomalyReport` — L54–L69
- `def AnomalyReport.to_dict` — L62–L69
- `def _robust_z` — L72–L83
- `def detect_anomalies` — L86–L128
- `def _early_alpha` — L131–L174

### `signals/prediction/breakout.py`

موتور احتمال شکست و شکستِ کاذب — خواسته‌های ۹ و ۱۰.

ارجاع داخلی: `app/core/models.py`, `app/logging/__init__.py`, `indicators/support_resistance.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`, `tests/test_predictive_phase2_5.py`.
- `class BreakoutAssessment` — L32–L55
- `def BreakoutAssessment.to_dict` — L44–L55
- `def _atr` — L58–L71
- `def assess_breakout` — L74–L154
- `def detect_false_breakout` — L157–L220
- `def _ema` — L223–L231

### `signals/prediction/crossasset.py`

هوش کراس-asset و تشخیص پیش‌تازی — خواسته‌های ۱۶ و ۱۷.

ارجاع داخلی: `app/core/models.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`, `tests/test_predictive_phase2_5.py`.
- `class LeadLagResult` — L26–L45
- `def LeadLagResult.to_dict` — L36–L45
- `def _closes_by_time` — L48–L50
- `def _aligned_returns` — L53–L70
- `def _pearson` — L73–L85
- `def rolling_correlation` — L88–L97
- `def lagged_cross_correlation` — L100–L114
- `def detect_lead_lag` — L117–L154
- `def market_context` — L157–L179

### `signals/prediction/distribution.py`

موتور توزیع احتمال (Probability Distribution Engine) — فاز ۴.

ارجاع داخلی: `app/core/models.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`, `signals/prediction/scenarios.py`, `tests/test_predictive_phase2_5.py`.
- `class HorizonDistribution` — L56–L86
- `def HorizonDistribution.to_dict` — L72–L86
- `def forward_log_returns` — L89–L104
- `def _empirical_quantile` — L107–L115
- `def build_distribution` — L118–L193
- `def probability_of_range` — L196–L220
- `def probability_of_range.cdf` — L206–L218
- `def _std` — L223–L229

### `signals/prediction/engine.py`

موتور مرکزی هوش پیش‌بینی (Predictive Intelligence Engine) — خواستهٔ ۵۰.

ارجاع داخلی: `app/core/models.py`, `app/logging/__init__.py`, `market/quality.py`, `signals/prediction/__init__.py`, `signals/prediction/anomaly.py`, `signals/prediction/breakout.py`, `signals/prediction/crossasset.py`, `signals/prediction/distribution.py`, `signals/prediction/events.py`, `signals/prediction/explain.py`, `signals/prediction/features.py`, `signals/prediction/fusion.py`, `signals/prediction/horizons.py`, `signals/prediction/models/base.py`, `signals/prediction/models/ensemble.py`, `signals/prediction/regime.py`, `signals/prediction/scenarios.py`, `signals/prediction/scoring.py`, `signals/prediction/timeline.py`, `signals/prediction/uncertainty.py`, `signals/prediction/volatility.py`, `signals/prediction/warning.py`.
واردکنندگان ایستا: `app/application.py`, `signals/prediction/__init__.py`, `tests/test_prediction_lifecycle.py`.
- `class HorizonReport` — L79–L120
- `def HorizonReport.to_dict` — L100–L120
- `class IntelligenceReport` — L124–L179
- `def IntelligenceReport.to_dict` — L152–L179
- `class PredictiveIntelligenceEngine` — L182–L744
- `def PredictiveIntelligenceEngine.__init__` — L194–L218
- `async def PredictiveIntelligenceEngine._fetch` — L221–L226
- `def PredictiveIntelligenceEngine.report` — L228–L236
- `async def PredictiveIntelligenceEngine.assess` — L238–L554
- `def PredictiveIntelligenceEngine._primary_timeframe` — L559–L563
- `def PredictiveIntelligenceEngine._atr_of` — L565–L574
- `def PredictiveIntelligenceEngine._momentum_probability` — L576–L587
- `def PredictiveIntelligenceEngine._regime_stability` — L589–L599
- `def PredictiveIntelligenceEngine._ensemble_for` — L601–L669
- `def PredictiveIntelligenceEngine._latest_row` — L671–L679
- `def PredictiveIntelligenceEngine._load_events` — L681–L685
- `def PredictiveIntelligenceEngine._should_record` — L688–L705
- `def PredictiveIntelligenceEngine.set_weights` — L707–L709
- `def PredictiveIntelligenceEngine.invalidate` — L711–L715
- `async def PredictiveIntelligenceEngine.accuracy_snapshot` — L717–L744
- `def _recent_for_horizon` — L748–L759
- `def _components_dicts` — L762–L772
- `def _models_avg_prob` — L775–L779

### `signals/prediction/events.py`

رویدادهای مهم بازار (Event Impact) — خواسته‌های ۳۱ و ۳۲، حالت دستی.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`, `tests/test_predictive_phase2_5.py`.
- `class MarketEvent` — L40–L55
- `def MarketEvent.to_dict` — L48–L55
- `def parse_events` — L58–L94
- `def load_events` — L97–L106
- `class EventPressure` — L110–L128
- `def EventPressure.to_dict` — L120–L128
- `def event_pressure` — L131–L177

### `signals/prediction/explain.py`

توضیح‌پذیری پیش‌بینی (Explainable AI) — خواستهٔ ۳۰.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`.
- `def explain_from_fusion` — L42–L65
- `def feature_highlights` — L68–L107
- `def split_contributors` — L110–L114

### `signals/prediction/features.py`

خزانهٔ فیچر (Feature Store).

ارجاع داخلی: `app/core/models.py`, `app/logging/__init__.py`, `indicators/engine.py`, `market/quality.py`.
واردکنندگان ایستا: `signals/prediction/__init__.py`, `signals/prediction/engine.py`, `tests/test_predictive_phase1.py`, `tests/test_predictive_phase2_5.py`.
- `class FeatureVector` — L84–L97
- `def FeatureVector.get` — L95–L97
- `class FeatureSet` — L101–L161
- `def FeatureSet.__len__` — L114–L116
- `def FeatureSet.latest` — L118–L120
- `def FeatureSet.matrix` — L122–L145
- `def FeatureSet.to_dict` — L147–L161
- `class FeatureStore` — L164–L308
- `def FeatureStore.__init__` — L173–L176
- `def FeatureStore.build` — L178–L308

### `signals/prediction/fusion.py`

موتور فیوژن هوشمند (Smart Signal Fusion) — خواسته‌های ۴، ۱۹ و ۳۶.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`, `tests/test_predictive_phase2_5.py`.
- `class FusionComponent` — L42–L59
- `def FusionComponent.to_dict` — L51–L59
- `class FusionResult` — L63–L82
- `def FusionResult.to_dict` — L73–L82
- `def fuse` — L85–L157
- `def _bucket_direction` — L169–L178
- `def multi_timeframe_view` — L181–L214

### `signals/prediction/horizons.py`

نردبان افق‌های پیش‌بینی (Horizon Ladder) — فاز ۲.

ارجاع داخلی: `market/quality.py`.
واردکنندگان ایستا: `signals/prediction/__init__.py`, `signals/prediction/engine.py`, `tests/test_predictive_phase2_5.py`.
- `class HorizonPlan` — L54–L75
- `def HorizonPlan.to_dict` — L65–L75
- `def plan_horizons` — L78–L148
- `def _tf_minutes` — L151–L156

### `signals/prediction/models/__init__.py`

بستهٔ مدل‌های پیش‌بینی — فاز ۵ و ۱۳.

ارجاع داخلی: `signals/prediction/models/base.py`, `signals/prediction/models/ensemble.py`, `signals/prediction/models/walkforward.py`.

### `signals/prediction/models/base.py`

قرارداد پایهٔ مدل‌های پیش‌بینی.

واردکنندگان ایستا: `signals/prediction/engine.py`, `signals/prediction/models/__init__.py`, `signals/prediction/models/ensemble.py`, `signals/prediction/models/gbm.py`, `signals/prediction/models/lstm.py`, `signals/prediction/models/statistical.py`, `tests/test_predictive_phase2_5.py`.
- `class ModelOutput` — L25–L40
- `def ModelOutput.to_dict` — L33–L40
- `class ForecastModel : ABC` — L43–L74
- `def ForecastModel.fit` — L56–L57
- `def ForecastModel.predict` — L60–L61
- `def ForecastModel.is_available` — L64–L65
- `def ForecastModel.predict_direction` — L67–L74
- `def forward_labels` — L77–L118
- `def _std` — L121–L126

### `signals/prediction/models/drift.py`

تشخیص افت عملکرد مدل (Concept Drift) — فاز ۱۰، خواستهٔ ۲۶.

واردکنندگان ایستا: `tests/test_predictive_phase2_5.py`.
- `class DriftReport` — L35–L54
- `def DriftReport.to_dict` — L45–L54
- `def assess_drift` — L57–L95

### `signals/prediction/models/ensemble.py`

آنسامبل وزن‌دار مدل‌ها — خواسته‌های ۲۰، ۲۱، ۲۷ و ۳۶.

ارجاع داخلی: `app/logging/__init__.py`, `signals/prediction/models/base.py`, `signals/prediction/models/gbm.py`, `signals/prediction/models/lstm.py`, `signals/prediction/models/statistical.py`, `signals/prediction/models/walkforward.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`, `signals/prediction/models/__init__.py`, `tests/test_predictive_phase2_5.py`.
- `class EnsembleForecast` — L39–L56
- `def EnsembleForecast.to_dict` — L48–L56
- `class ModelEnsemble` — L59–L207
- `def ModelEnsemble.__init__` — L67–L74
- `def ModelEnsemble.model_names` — L78–L80
- `def ModelEnsemble.validation_summary` — L82–L86
- `def ModelEnsemble.fit` — L89–L135
- `def ModelEnsemble._compute_weights` — L137–L151
- `def ModelEnsemble.reweight` — L153–L170
- `def ModelEnsemble.predict` — L173–L202
- `def ModelEnsemble.weights` — L205–L207

### `signals/prediction/models/gbm.py`

مدل گرادیان بوتینگ (LightGBM → XGBoost) — اختیاری.

ارجاع داخلی: `app/logging/__init__.py`, `signals/prediction/models/base.py`.
واردکنندگان ایستا: `signals/prediction/models/ensemble.py`, `tests/test_predictive_phase2_5.py`.
- `class GBMModel : ForecastModel` — L63–L152
- `def GBMModel.__init__` — L68–L71
- `def GBMModel.is_available` — L73–L77
- `def GBMModel.fit` — L79–L111
- `def GBMModel._fit_lightgbm` — L114–L122
- `def GBMModel._fit_xgboost` — L125–L131
- `def GBMModel.predict` — L133–L152

### `signals/prediction/models/lstm.py`

مدل LSTM کوچک با PyTorch — اختیاری و سبک.

ارجاع داخلی: `app/logging/__init__.py`, `signals/prediction/models/base.py`.
واردکنندگان ایستا: `signals/prediction/models/ensemble.py`, `tests/test_predictive_phase2_5.py`.
- `class LSTMModel : ForecastModel` — L41–L176
- `def LSTMModel.__init__` — L46–L52
- `def LSTMModel.is_available` — L54–L58
- `def LSTMModel.fit` — L60–L144
- `def LSTMModel.fit.normalized` — L103–L110
- `class LSTMModel.fit._Net : nn.Module` — L115–L123
- `def LSTMModel.fit._Net.__init__` — L116–L119
- `def LSTMModel.fit._Net.forward` — L121–L123
- `def LSTMModel.remember` — L146–L150
- `def LSTMModel.predict` — L152–L176
- `def _std` — L179–L184

### `signals/prediction/models/statistical.py`

مدل آماری همیشه‌در دسترس — مومنتوم + بازگشت به میانگین.

ارجاع داخلی: `app/logging/__init__.py`, `signals/prediction/models/base.py`.
واردکنندگان ایستا: `signals/prediction/models/ensemble.py`, `tests/test_predictive_phase2_5.py`.
- `class StatisticalModel : ForecastModel` — L48–L114
- `def StatisticalModel.__init__` — L53–L57
- `def StatisticalModel.is_available` — L59–L61
- `def StatisticalModel.fit` — L63–L83
- `def StatisticalModel.predict` — L85–L114
- `def StatisticalModel.predict.scaled` — L91–L95
- `def _std` — L117–L122

### `signals/prediction/models/walkforward.py`

اعتبارسنجی غلتان (Walk-Forward Validation) — خواسته‌های ۴۱ و ۴۲.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `signals/prediction/models/__init__.py`, `signals/prediction/models/ensemble.py`, `tests/test_predictive_phase2_5.py`.
- `class FoldResult` — L29–L44
- `def FoldResult.to_dict` — L37–L44
- `class WalkForwardResult` — L48–L70
- `def WalkForwardResult.valid` — L58–L60
- `def WalkForwardResult.to_dict` — L62–L70
- `def walk_forward` — L73–L169

### `signals/prediction/regime.py`

موتور رژیم بازار (Market Regime Engine) — فاز ۳.

ارجاع داخلی: `app/core/models.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`, `tests/test_predictive_phase2_5.py`.
- `class Regime : str, Enum` — L36–L53
- `class RegimeAssessment` — L77–L94
- `def RegimeAssessment.to_dict` — L86–L94
- `def _percentile_of_latest` — L97–L109
- `def _donchian_position` — L112–L121
- `def _last` — L124–L129
- `def _series_from_features` — L132–L136
- `def classify_timeframe` — L139–L267
- `class RegimeTransition` — L274–L295
- `def RegimeTransition.changed` — L283–L285
- `def RegimeTransition.to_dict` — L287–L295
- `def detect_transition` — L298–L321
- `def stage_of` — L354–L356
- `def transition_probabilities` — L359–L385

### `signals/prediction/scenarios.py`

موتور سناریو (Scenario Engine) — فاز ۶، خواسته‌های ۳ و ۴۷.

ارجاع داخلی: `app/logging/__init__.py`, `signals/prediction/distribution.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`, `tests/test_predictive_phase2_5.py`.
- `class Scenario` — L43–L61
- `def Scenario.to_dict` — L53–L61
- `class ScenarioTree` — L65–L82
- `def ScenarioTree.to_dict` — L73–L82
- `def build_scenarios` — L85–L182
- `def build_scenarios._conditions` — L121–L138
- `def _tail_split` — L185–L197

### `signals/prediction/scoring.py`

امتیازدهی و کالیبراسیون — خواسته‌های ۲۴ و ۲۵، فاز ۹.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `signals/prediction/__init__.py`, `signals/prediction/engine.py`, `tests/test_prediction_lifecycle.py`.
- `def brier_score` — L30–L50
- `def calibration_buckets` — L53–L84
- `def accuracy_summary` — L87–L112
- `def accuracy_summary.rate` — L95–L97
- `def model_health` — L115–L155

### `signals/prediction/store.py`

ثبت و حل پیش‌بینی‌ها — اجرای قانون حیاتی ۵.

ارجاع داخلی: `app/core/models.py`, `app/database/models.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/application.py`, `signals/prediction/__init__.py`, `tests/test_prediction_lifecycle.py`.
- `def _as_utc` — L29–L31
- `class PredictionStore` — L34–L158
- `def PredictionStore.__init__` — L45–L51
- `def PredictionStore.save_horizon` — L54–L98
- `def PredictionStore.resolve_due` — L101–L133
- `def PredictionStore._lookup` — L135–L144
- `def PredictionStore._judge_direction` — L147–L158
- `def price_lookup_from_candles` — L161–L182
- `def price_lookup_from_candles.lookup` — L172–L180

### `signals/prediction/timeline.py`

خط زمانی پیش‌بینی و «چه چیزی عوض شد؟» — خواسته‌های ۲۸ و ۲۹.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`, `tests/test_prediction_lifecycle.py`.
- `def prediction_timeline` — L23–L43
- `def what_changed` — L46–L113
- `def what_changed.field` — L57–L60
- `def what_changed.contributions` — L69–L76
- `def what_changed.moment` — L97–L103

### `signals/prediction/uncertainty.py`

موتور عدم‌قطعیت و اعتبار زمانی — خواسته‌های ۳۳ و ۳۴.

واردکنندگان ایستا: `signals/prediction/engine.py`, `tests/test_predictive_phase2_5.py`.
- `class UncertaintyAdjustment` — L31–L48
- `def UncertaintyAdjustment.to_dict` — L40–L48
- `def effective_confidence` — L51–L103
- `def decayed_validity` — L106–L136

### `signals/prediction/volatility.py`

پیش‌بینی نوسان (Volatility Forecasting) — خواسته‌های ۱۱ و ۱۲.

ارجاع داخلی: `app/core/models.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`, `tests/test_predictive_phase2_5.py`.
- `class VolatilityForecast` — L40–L66
- `def VolatilityForecast.sigma_percent` — L52–L54
- `def VolatilityForecast.to_dict` — L56–L66
- `def ewma_sigma` — L69–L84
- `def ewma_history` — L87–L92
- `def forecast_for_horizon` — L95–L153

### `signals/prediction/warning.py`

سیستم هشدار زودهنگام (Early Warning System) — خواستهٔ ۸.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `signals/prediction/engine.py`, `tests/test_predictive_phase2_5.py`.
- `class EarlyWarning` — L38–L56
- `def EarlyWarning.to_dict` — L47–L56
- `def build_warnings` — L59–L177

### `signals/risk_engine.py`

موتور مدیریت ریسک.

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `signals/__init__.py`, `signals/engine.py`, `tests/test_risk_engine.py`.
- `class RiskEngine` — L30–L287
- `def RiskEngine.__init__` — L38–L39
- `def RiskEngine.parameters` — L42–L44
- `def RiskEngine.set_parameters` — L46–L48
- `def RiskEngine.calculate_stop_loss` — L53–L119
- `def RiskEngine.calculate_take_profits` — L124–L171
- `def RiskEngine.assess` — L176–L254
- `def RiskEngine._suggest_leverage` — L259–L270
- `def RiskEngine._volatility_note` — L273–L287

### `signals/scanner.py`

پویشگر بازار — گرفتن سیگنال از همهٔ نمادها، یکی‌یکی.

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `app/application.py`, `tests/test_v170_scanner_fonts_theme.py`.
- `class ScanProgress` — L47–L60
- `def ScanProgress.percent` — L56–L60
- `class ScanResult` — L64–L85
- `def ScanResult.actionable` — L79–L81
- `def ScanResult.top` — L83–L85
- `class MarketScanner` — L88–L233
- `def MarketScanner.__init__` — L96–L107
- `async def MarketScanner.candidate_symbols` — L112–L139
- `async def MarketScanner.scan` — L144–L233
- `async def MarketScanner.scan.worker` — L188–L220
- `def _scan_sort_key` — L236–L243

### `signals/scorecard.py`

دفترچهٔ نتیجهٔ پیش‌بینی‌ها.

ارجاع داخلی: `signals/forecast.py`.
واردکنندگان ایستا: `app/application.py`, `tests/test_v1918_scorecard.py`.
- `class ScorecardRow` — L52–L79
- `def ScorecardRow.hit_rate` — L61–L63
- `def ScorecardRow.average_miss` — L66–L69
- `def ScorecardRow.as_dict` — L71–L79
- `class ScorecardReport` — L83–L148
- `def ScorecardReport.checked` — L91–L93
- `def ScorecardReport.hits` — L96–L98
- `def ScorecardReport.hit_rate` — L101–L103
- `def ScorecardReport.verdict` — L106–L120
- `def ScorecardReport.suggested_sigma_shift` — L123–L134
- `def ScorecardReport.as_dict` — L136–L148
- `def horizon_is_due` — L151–L162
- `def build_report` — L165–L238

### `signals/strategies/__init__.py`

راهبردهای معاملاتی قابل افزودن.

ارجاع داخلی: `signals/strategies/base.py`, `signals/strategies/breakout.py`, `signals/strategies/mean_reversion.py`, `signals/strategies/registry.py`, `signals/strategies/trend_following.py`.

### `signals/strategies/base.py`

قرارداد راهبردهای معاملاتی.

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`.
واردکنندگان ایستا: `signals/__init__.py`, `signals/engine.py`, `signals/strategies/__init__.py`, `signals/strategies/breakout.py`, `signals/strategies/mean_reversion.py`, `signals/strategies/momentum.py`, `signals/strategies/registry.py`, `signals/strategies/trend_following.py`, `signals/strategies/volatility_regime.py`, `tests/test_v1917_forecast.py`, `tests/test_v1917_trust_and_trades.py`.
- `class StrategyContext` — L23–L65
- `def StrategyContext.last_price` — L40–L42
- `def StrategyContext.indicator_value` — L44–L58
- `def StrategyContext.indicator_signal` — L60–L65
- `class StrategyVote` — L69–L98
- `def StrategyVote.weighted_score` — L85–L87
- `def StrategyVote.to_dict` — L89–L98
- `class BaseStrategy : ABC` — L101–L158
- `def BaseStrategy.evaluate` — L117–L123
- `def BaseStrategy._vote` — L125–L147
- `def BaseStrategy._not_applicable` — L149–L158

### `signals/strategies/breakout.py`

راهبرد شکست سطوح.

ارجاع داخلی: `app/core/constants.py`, `signals/strategies/base.py`.
واردکنندگان ایستا: `signals/strategies/__init__.py`, `signals/strategies/registry.py`.
- `class BreakoutStrategy : BaseStrategy` — L19–L67
- `def BreakoutStrategy.evaluate` — L26–L67

### `signals/strategies/mean_reversion.py`

راهبرد بازگشت به میانگین.

ارجاع داخلی: `signals/strategies/base.py`.
واردکنندگان ایستا: `signals/strategies/__init__.py`, `signals/strategies/registry.py`.
- `class MeanReversionStrategy : BaseStrategy` — L20–L83
- `def MeanReversionStrategy.evaluate` — L27–L83

### `signals/strategies/momentum.py`

راهبرد مومنتوم.

ارجاع داخلی: `signals/strategies/base.py`.
واردکنندگان ایستا: `signals/strategies/registry.py`, `tests/test_v1917_forecast.py`.
- `class MomentumStrategy : BaseStrategy` — L26–L107
- `def MomentumStrategy.evaluate` — L33–L107

### `signals/strategies/registry.py`

رجیستری راهبردها.

ارجاع داخلی: `app/exceptions/__init__.py`, `app/logging/__init__.py`, `signals/strategies/base.py`, `signals/strategies/breakout.py`, `signals/strategies/mean_reversion.py`, `signals/strategies/momentum.py`, `signals/strategies/trend_following.py`, `signals/strategies/volatility_regime.py`.
واردکنندگان ایستا: `app/application.py`, `main.py`, `signals/__init__.py`, `signals/engine.py`, `signals/strategies/__init__.py`, `tests/conftest.py`, `tests/test_v1917_forecast.py`.
- `class StrategyRegistry` — L17–L50
- `def StrategyRegistry.__init__` — L20–L21
- `def StrategyRegistry.register` — L23–L29
- `def StrategyRegistry.get` — L31–L38
- `def StrategyRegistry.all` — L40–L42
- `def StrategyRegistry.available` — L44–L46
- `def StrategyRegistry.clear` — L48–L50
- `def register_builtin_strategies` — L57–L81

### `signals/strategies/trend_following.py`

راهبرد دنبال‌کننده روند.

ارجاع داخلی: `app/core/constants.py`, `signals/strategies/base.py`.
واردکنندگان ایستا: `signals/strategies/__init__.py`, `signals/strategies/registry.py`.
- `class TrendFollowingStrategy : BaseStrategy` — L19–L83
- `def TrendFollowingStrategy.evaluate` — L26–L83

### `signals/strategies/volatility_regime.py`

راهبرد رژیم نوسان.

ارجاع داخلی: `app/core/constants.py`, `signals/strategies/base.py`.
واردکنندگان ایستا: `signals/strategies/registry.py`, `tests/test_v1917_forecast.py`.
- `class VolatilityRegimeStrategy : BaseStrategy` — L25–L100
- `def VolatilityRegimeStrategy.evaluate` — L32–L100

### `signals/validity.py`

پنجرهٔ اعتبار سیگنال و تشخیص «سیگنال سوخته».

واردکنندگان ایستا: `signals/engine.py`, `tests/test_v1917_forecast.py`, `tests/test_v195_ai_and_validity.py`, `ui/controllers/main_controller.py`.
- `class Freshness : str, Enum` — L72–L88
- `class ValidityWindow` — L96–L156
- `def ValidityWindow.__post_init__` — L127–L130
- `def ValidityWindow.is_enterable` — L133–L135
- `def ValidityWindow.is_burned` — L138–L140
- `def ValidityWindow.to_dict` — L142–L156
- `def as_utc` — L159–L167
- `def timeframe_minutes` — L170–L172
- `def entry_window_minutes` — L175–L183
- `def expiry_minutes` — L186–L189
- `def primary_timeframe` — L192–L205
- `def _consumed_fraction` — L208–L231
- `def _adverse_fraction` — L234–L251
- `def _effective_risk_reward` — L254–L278
- `def evaluate` — L281–L430
- `def _reference_entry` — L433–L446

### `tests/__init__.py`

مجموعه آزمون‌های خودکار برنامه.


### `tests/conftest.py`

پیکربندی مشترک آزمون‌ها.

ارجاع داخلی: `app/core/models.py`, `app/core/paths.py`, `app/database/session.py`, `app/exceptions/__init__.py`, `indicators/registry.py`, `signals/strategies/registry.py`.
واردکنندگان ایستا: `tests/test_exchange_login_flow.py`, `tests/test_indicators.py`, `tests/test_new_pages.py`, `tests/test_prediction_ui_and_tools.py`, `tests/test_signal_engine.py`, `tests/test_timeframes.py`, `tests/test_v200_event_driven_trading.py`, `tests/test_v22_terminal_pro.py`.
- `def _register_plugins` — L23–L28
- `def temp_paths` — L32–L34
- `def database` — L38–L42
- `def risk_parameters` — L46–L55
- `def make_candles` — L58–L95
- `def uptrend_candles` — L99–L101
- `def downtrend_candles` — L105–L107
- `def ranging_candles` — L111–L113
- `class FakeMarketEngine` — L116–L137
- `def FakeMarketEngine.__init__` — L126–L128
- `async def FakeMarketEngine.get_candles` — L130–L137
- `def _isolate_qt_app_look` — L141–L170
- `def qt_application` — L174–L185
- `def destroy_window` — L188–L229

### `tests/test_ai_providers.py`

آزمون‌های لایه ارائه‌دهندگان هوش مصنوعی.

ارجاع داخلی: `ai/providers/base.py`, `ai/providers/free_models.py`, `ai/providers/ollama_provider.py`, `ai/providers/openai_compatible.py`, `app/exceptions/__init__.py`.
- `def test_local_provider_models_are_always_free` — L44–L47
- `def test_explicit_free_marker_wins` — L50–L54
- `def test_expensive_models_are_marked_paid` — L57–L60
- `def test_cheap_models_are_low_cost_not_free` — L63–L70
- `def test_free_tier_provider_small_models_are_free` — L73–L76
- `def test_sorting_puts_free_models_first` — L79–L84
- `def test_pick_default_prefers_free` — L87–L90
- `def test_free_models_filter` — L93–L96
- `def test_large_model_is_not_mistaken_for_small` — L99–L108
- `def test_known_free_models_exist_for_main_providers` — L111–L114
- `def test_model_label_shows_tier` — L117–L121
- `def test_model_matching_ignores_tag` — L127–L131
- `def test_host_candidates_include_loopback_swap` — L134–L142
- `def test_host_candidates_handle_missing_scheme` — L145–L147
- `def test_empty_base_url_falls_back_to_default` — L150–L154
- `def _ollama_transport` — L157–L178
- `def _ollama_transport.handler` — L160–L176
- `class _StubbedOllama : OllamaProvider` — L181–L198
- `def _StubbedOllama.__init__` — L184–L186
- `async def _StubbedOllama._resolve_base_url` — L188–L190
- `async def _StubbedOllama._get_client` — L192–L198
- `async def test_missing_model_falls_back_to_installed_one` — L202–L219
- `async def test_configured_model_is_used_when_installed` — L223–L228
- `async def test_no_installed_model_reports_actionable_message` — L232–L239
- `async def test_ollama_never_requires_api_key` — L243–L247
- `def test_new_models_need_completion_tokens` — L253–L257
- `def _openai_transport` — L260–L267
- `def _openai_transport.handler` — L263–L265
- `class _StubbedOpenAI : OpenAICompatibleProvider` — L270–L283
- `def _StubbedOpenAI.__init__` — L273–L275
- `async def _StubbedOpenAI._get_client` — L277–L283
- `async def test_exhausted_credit_is_reported_distinctly` — L287–L307
- `async def test_invalid_key_raises_authentication_error` — L311–L319
- `async def test_missing_key_is_caught_before_network` — L323–L329
- `async def test_missing_base_url_is_reported` — L333–L339
- `async def test_successful_generation_is_parsed` — L343–L355
- `async def test_error_returned_with_status_200_is_detected` — L359–L365

### `tests/test_ai_validator.py`

آزمون اعتبارسنج خروجی هوش مصنوعی.

ارجاع داخلی: `ai/agent/validator.py`.
- `def _validator` — L8–L10
- `def test_clean_json_is_accepted` — L13–L21
- `def test_json_inside_code_fence_is_extracted` — L24–L29
- `def test_trailing_comma_is_repaired` — L32–L35
- `def test_non_json_is_rejected` — L38–L42
- `def test_long_with_stop_above_entry_is_rejected` — L45–L50
- `def test_unordered_take_profits_are_rejected` — L53–L60
- `def test_excessive_leverage_is_clamped` — L63–L72
- `def test_risk_reward_is_recomputed_from_numbers` — L75–L81
- `def test_insufficient_data_becomes_wait` — L84–L88
- `def test_confidence_out_of_range_is_rejected` — L91–L94
- `def test_wait_signal_clears_price_fields` — L97–L104
- `def test_low_risk_reward_raises_warning` — L107–L115

### `tests/test_async_runner.py`

آزمون اجراکننده کارهای پس‌زمینه.

ارجاع داخلی: `app/exceptions/__init__.py`, `ui/controllers/async_runner.py`.
- `def qt_app` — L23–L30
- `def runner` — L34–L39
- `def _wait` — L42–L47
- `def test_runner_starts_and_stops` — L50–L54
- `def test_successful_task_emits_result` — L57–L67
- `async def test_successful_task_emits_result.work` — L61–L63
- `def test_failing_task_reports_error_instead_of_raising` — L70–L83
- `async def test_failing_task_reports_error_instead_of_raising.work` — L78–L79
- `def test_unexpected_exception_is_also_captured` — L86–L95
- `async def test_unexpected_exception_is_also_captured.work` — L90–L91
- `def test_cancelled_handle_does_not_deliver_result` — L98–L113
- `async def test_cancelled_handle_does_not_deliver_result.work` — L106–L108
- `def test_finished_fires_for_both_outcomes` — L116–L129
- `async def test_finished_fires_for_both_outcomes.good` — L120–L121
- `async def test_finished_fires_for_both_outcomes.bad` — L123–L124
- `def test_blocking_function_runs_off_the_main_thread` — L132–L147
- `def test_submit_without_running_loop_fails_gracefully` — L150–L160
- `async def test_submit_without_running_loop_fails_gracefully.work` — L155–L156

### `tests/test_auth.py`

آزمون مدیریت کاربر، رمز عبور و حساب‌های صرافی.

ارجاع داخلی: `app/config/settings_service.py`, `app/core/auth_service.py`, `app/core/exchange_account_service.py`, `app/database/models.py`, `app/database/repositories/__init__.py`, `app/database/session.py`, `app/security/passwords.py`, `app/security/secret_store.py`.
- `def database` — L38–L42
- `def users` — L46–L48
- `def auth` — L52–L56
- `def test_password_hash_is_salted_and_verifiable` — L62–L82
- `def test_password_verification_never_raises_on_bad_input` — L85–L89
- `def test_iteration_count_is_current_and_upgradeable` — L92–L95
- `def test_password_policy_rejects_weak_values` — L98–L104
- `def test_mask_secret_hides_the_middle` — L107–L115
- `def test_session_token_is_stored_only_as_hash` — L118–L124
- `def test_user_dict_never_leaks_password_fields` — L130–L134
- `def test_duplicate_username_is_rejected` — L137–L141
- `def test_authenticate_returns_same_error_for_unknown_and_wrong` — L144–L155
- `def test_account_locks_after_repeated_failures` — L158–L165
- `def test_change_password_revokes_sessions` — L168–L179
- `def test_change_password_requires_correct_current` — L182–L189
- `def test_expired_and_revoked_sessions_are_ignored` — L192–L198
- `def test_guest_mode_is_default` — L204–L208
- `def test_register_login_logout_cycle` — L211–L223
- `def test_register_rejects_weak_password` — L226–L230
- `def test_remember_me_restores_session` — L233–L248
- `def test_logout_prevents_auto_login` — L251–L264
- `def test_theme_preference_is_per_user_and_survives_restart` — L267–L286
- `def test_preferences_merge_instead_of_replacing` — L289–L295
- `def accounts` — L302–L307
- `def test_api_credentials_are_never_stored_in_plaintext` — L310–L336
- `def test_credentials_roundtrip_through_secret_store` — L339–L352
- `def test_account_listing_exposes_only_masked_key` — L355–L371
- `def test_first_account_becomes_default` — L374–L383
- `def test_deleting_account_purges_its_secret` — L386–L395
- `async def test_connection_error_message_is_scrubbed` — L399–L426
- `class test_connection_error_message_is_scrubbed.LeakyProvider` — L413–L420
- `async def test_connection_error_message_is_scrubbed.LeakyProvider.test_credentials` — L416–L417
- `async def test_connection_error_message_is_scrubbed.LeakyProvider.close` — L419–L420
- `async def test_balance_sync_updates_account` — L430–L457
- `class test_balance_sync_updates_account.Provider` — L439–L446
- `async def test_balance_sync_updates_account.Provider.get_account_balance` — L442–L443
- `async def test_balance_sync_updates_account.Provider.close` — L445–L446

### `tests/test_autonomous_agent.py`

آزمون‌های عامل خودمختار.

ارجاع داخلی: `ai/agent/autonomous_agent.py`, `ai/providers/__init__.py`, `ai/providers/base.py`, `ai/providers/manager.py`, `ai/tools/market_tools.py`, `app/core/models.py`.
- `class _StubToolset` — L57–L79
- `def _StubToolset.__init__` — L60–L62
- `def _StubToolset.set_risk_parameters` — L64–L65
- `def _StubToolset.get_definitions` — L68–L71
- `async def _StubToolset.execute` — L73–L79
- `def _manager_with` — L82–L109
- `class _manager_with._Scripted : AIProvider` — L85–L97
- `async def _manager_with._Scripted.is_available` — L88–L89
- `async def _manager_with._Scripted.list_models` — L91–L92
- `async def _manager_with._Scripted.generate` — L94–L97
- `def risk` — L113–L114
- `async def test_agent_returns_validated_long` — L118–L130
- `async def test_agent_refuses_invalid_trade` — L134–L144
- `async def test_agent_clamps_leverage_to_user_limit` — L148–L160
- `async def test_agent_uses_tools_before_deciding` — L164–L187
- `async def test_agent_survives_failing_tool` — L191–L202
- `async def test_agent_recovers_from_unparseable_response` — L206–L214
- `async def test_agent_gives_up_after_repeated_garbage` — L218–L228
- `async def test_agent_reports_missing_provider` — L232–L240
- `async def test_agent_stops_at_iteration_limit` — L244–L255
- `async def test_progress_callback_receives_steps` — L259–L273
- `async def test_broken_progress_callback_does_not_break_analysis` — L277–L288
- `def test_broken_progress_callback_does_not_break_analysis.explode` — L280–L281
- `def test_parse_handles_fenced_json` — L291–L297
- `def test_parse_handles_prose_around_json` — L300–L306
- `def test_parse_rejects_garbage` — L309–L312
- `def test_schema_mapping_round_trip` — L315–L326

### `tests/test_backup.py`

آزمون پشتیبان‌گیری و بازیابی.

ارجاع داخلی: `app/config/settings_service.py`, `app/core/paths.py`, `app/database/repositories/__init__.py`, `app/database/session.py`, `app/exceptions/__init__.py`, `backup/__init__.py`.
- `def prepared` — L16–L23
- `def test_backup_creates_valid_archive` — L26–L33
- `def test_manifest_records_metadata` — L36–L44
- `def test_secrets_are_never_included` — L47–L59
- `def test_restore_recovers_previous_value` — L62–L73
- `def test_restore_creates_safety_backup` — L76–L83
- `def test_backups_in_same_second_do_not_overwrite` — L86–L93
- `def test_corrupt_archive_is_refused` — L96–L106
- `def test_corrupt_archive_is_listed_as_invalid` — L109–L115
- `def test_pre_migration_backup_skipped_without_database` — L118–L121

### `tests/test_chat_agent.py`

آزمون‌های دستیار گفتگو.

ارجاع داخلی: `ai/agent/chat_agent.py`, `ai/providers/base.py`.
- `class FakeToolResult` — L24–L33
- `def FakeToolResult.__init__` — L27–L29
- `def FakeToolResult.to_dict` — L31–L33
- `class FakeToolset` — L36–L61
- `def FakeToolset.__init__` — L41–L43
- `def FakeToolset.get_definitions` — L45–L53
- `def FakeToolset.set_risk_parameters` — L55–L56
- `async def FakeToolset.execute` — L58–L61
- `class ScriptedManager` — L64–L80
- `def ScriptedManager.__init__` — L67–L70
- `async def ScriptedManager.generate` — L72–L76
- `async def ScriptedManager.check_all` — L78–L80
- `def make_agent` — L86–L89
- `async def test_plain_json_answer` — L96–L102
- `async def test_non_json_reply_is_accepted` — L106–L115
- `async def test_fenced_json_is_parsed` — L119–L123
- `async def test_empty_message_is_rejected` — L127–L132
- `async def test_no_provider_reports_clearly` — L136–L141
- `async def test_tool_call_then_answer` — L148–L159
- `async def test_single_tool_format_is_supported` — L163–L171
- `async def test_unknown_tool_is_never_executed` — L175–L189
- `async def test_context_symbol_is_injected` — L193–L201
- `async def test_tool_call_limit_is_enforced` — L205–L212
- `async def test_failed_tool_does_not_break_chat` — L216–L226
- `async def test_progress_callback_receives_calls` — L230–L241
- `async def test_valid_action_is_returned` — L248–L258
- `async def test_unknown_action_type_is_dropped` — L262–L271
- `async def test_action_falls_back_to_context_symbol` — L275–L281
- `async def test_history_is_kept_between_turns` — L288–L293
- `async def test_reset_clears_history` — L297–L303
- `async def test_history_is_trimmed` — L307–L313
- `async def test_health_check_reports_ready` — L317–L322

### `tests/test_chat_page.py`

آزمون‌های صفحه چت.

ارجاع داخلی: `localization/__init__.py`, `market/timeframes.py`, `ui/pages/chat_page.py`.
- `def qt_app` — L26–L28
- `def page` — L32–L34
- `def test_page_starts_with_welcome_message` — L40–L43
- `def test_all_timeframes_are_available` — L46–L50
- `def test_default_timeframe_is_4h` — L53–L55
- `def test_symbol_list_is_searchable` — L58–L63
- `def test_set_symbols_fills_combo` — L66–L69
- `def test_current_context_reports_selection` — L72–L78
- `def test_sending_emits_signal_and_adds_bubble` — L84–L94
- `def test_empty_message_is_ignored` — L97–L104
- `def test_reply_lifecycle_replaces_placeholder` — L107–L122
- `def test_tools_are_shown_under_answer` — L125–L130
- `def test_answer_without_tools_hides_tool_row` — L133–L137
- `def test_busy_state_locks_input` — L140–L147
- `def test_failed_reply_is_displayed` — L150–L155
- `def test_action_button_hidden_by_default` — L161–L163
- `def test_show_action_reveals_button` — L166–L171
- `def test_action_requires_explicit_click` — L174–L188
- `def test_action_hides_after_click` — L191–L196
- `def test_empty_action_is_ignored` — L199–L202
- `def test_new_message_hides_pending_action` — L205–L211
- `def test_clear_resets_to_welcome` — L217–L230
- `def test_language_switch_updates_texts` — L233–L243
- `def test_bubble_alignment_follows_direction` — L246–L259

### `tests/test_chat_repository.py`

آزمون‌های مخزن گفت‌وگوهای چت.

ارجاع داخلی: `app/database/repositories/__init__.py`, `app/database/repositories/chat_repository.py`.
- `def repository` — L16–L18
- `def test_create_and_list` — L21–L30
- `def test_title_generated_from_first_user_message` — L33–L40
- `def test_long_title_is_truncated` — L43–L50
- `def test_assistant_message_does_not_set_title` — L53–L60
- `def test_messages_keep_order_and_tools` — L63–L80
- `def test_message_count_increments` — L83–L91
- `def test_delete_removes_conversation_and_messages` — L94–L101
- `def test_delete_missing_conversation_is_safe` — L104–L106
- `def test_rename_conversation` — L109–L116
- `def test_pinned_conversations_come_first` — L119–L127
- `def test_search_finds_by_message_content` — L130–L138
- `def test_search_with_empty_term_returns_all` — L141–L145
- `def test_add_message_to_missing_conversation_raises` — L148–L151
- `def test_clear_all` — L154–L161
- `def test_make_title_collapses_whitespace` — L164–L166
- `def test_make_title_of_empty_text` — L169–L171

### `tests/test_chat_ui_v2.py`

آزمون‌های بازطراحی چت (نسخهٔ ۱.۴) و مدال تحلیل نوشتاری.

ارجاع داخلی: `localization/__init__.py`, `ui/dialogs/analysis_dialog.py`, `ui/pages/chat_page.py`.
- `def page` — L23–L27
- `def test_input_is_multiline` — L33–L40
- `def test_long_text_is_fully_retrievable` — L43–L48
- `def test_input_grows_with_content` — L51–L57
- `def test_input_starts_at_minimum_height` — L60–L62
- `def test_enter_sends_message` — L65–L72
- `def test_shift_enter_does_not_send` — L75–L84
- `def test_bubble_shows_full_long_text` — L90–L94
- `def test_bubble_wraps_text` — L97–L100
- `def test_bubble_text_is_selectable` — L103–L107
- `def test_bubble_width_follows_window` — L110–L120
- `def test_history_panel_exists` — L126–L129
- `def test_set_conversations_fills_list` — L132–L139
- `def test_untitled_conversation_gets_placeholder` — L142–L145
- `def test_pinned_conversation_is_marked` — L148–L151
- `def test_clicking_history_emits_id` — L154–L160
- `def test_new_chat_button_emits` — L163–L168
- `def test_history_search_filters` — L171–L179
- `def test_history_search_clears` — L182–L187
- `def test_select_conversation_highlights` — L190–L194
- `def test_load_messages_replaces_conversation` — L197–L206
- `def test_load_messages_skips_system` — L209–L215
- `def test_load_empty_messages_shows_welcome` — L218–L221
- `def test_load_messages_restores_tools` — L224–L227
- `def test_set_context_updates_combos` — L230–L236
- `def test_retranslate_updates_history_widgets` — L239–L244
- `def translator` — L251–L255
- `def test_analysis_dialog_renders_headings` — L258–L264
- `def test_analysis_dialog_empty_text` — L267–L270
- `def test_analysis_dialog_pdf_button_emits` — L273–L280
- `def test_analysis_dialog_escapes_html` — L283–L294
- `def test_analysis_dialog_shows_source` — L297–L303

### `tests/test_exchange_login_flow.py`

آزمون مسیر کامل «ورود به حساب صرافی» از دید کاربر.

ارجاع داخلی: `app/application.py`, `app/core/paths.py`, `localization/__init__.py`, `tests/conftest.py`, `ui/controllers/main_controller.py`, `ui/themes/theme_manager.py`, `ui/windows/main_window.py`.
- `class _FakeProvider` — L32–L49
- `def _FakeProvider.__init__` — L35–L36
- `async def _FakeProvider.test_credentials` — L38–L42
- `async def _FakeProvider.get_account_balance` — L44–L46
- `async def _FakeProvider.close` — L48–L49
- `def gui` — L53–L92
- `def _settings` — L95–L97
- `def _add_account` — L100–L107
- `def test_user_can_add_accounts_for_both_new_exchanges` — L110–L124
- `def test_inputs_are_cleared_so_the_key_does_not_stay_on_screen` — L127–L133
- `def test_stored_key_is_masked_in_the_table` — L136–L154
- `def test_secret_is_never_written_to_the_database_in_plain_text` — L157–L171
- `def test_test_button_without_selection_warns_instead_of_doing_nothing` — L174–L193
- `def test_connection_test_uses_the_registry_and_reports_success` — L196–L222
- `def test_failed_connection_message_is_localized` — L225–L243
- `def test_exchange_hint_is_shown_when_selecting_bitpin` — L246–L261
- `def test_switching_exchange_clears_credentials_fields` — L264–L275

### `tests/test_exchange_switching.py`

آزمون تعویض زندهٔ صرافی فعال و ارزش‌گذاری دارایی تومانی.

ارجاع داخلی: `app/application.py`, `app/core/paths.py`, `localization/__init__.py`, `market/providers/base.py`, `market/providers/registry.py`, `ui/controllers/main_controller.py`, `ui/themes/theme_manager.py`, `ui/windows/main_window.py`.
- `class _StubProvider : ExchangeProvider` — L28–L86
- `def _StubProvider.__init__` — L35–L38
- `def _StubProvider.capabilities` — L41–L43
- `async def _StubProvider.connect` — L45–L46
- `async def _StubProvider.close` — L48–L50
- `async def _StubProvider.ping` — L52–L54
- `async def _StubProvider.get_symbols` — L56–L58
- `async def _StubProvider.get_ticker` — L60–L62
- `async def _StubProvider.get_all_tickers` — L64–L66
- `async def _StubProvider.get_current_price` — L68–L70
- `async def _StubProvider.get_ohlcv` — L72–L74
- `async def _StubProvider.get_orderbook` — L76–L78
- `def _StubProvider.to_exchange_symbol` — L80–L82
- `def _StubProvider.from_exchange_symbol` — L84–L86
- `def app_with_stubs` — L90–L113
- `def test_switch_exchange_replaces_the_market_engine` — L116–L131
- `def test_switch_rebuilds_the_signal_engine` — L134–L144
- `def test_previous_provider_is_closed` — L147–L152
- `def test_switching_to_the_same_exchange_is_a_no_op` — L155–L160
- `def test_unknown_exchange_keeps_the_current_engine` — L163–L174
- `class TestTomanValuation` — L177–L239
- `def TestTomanValuation.controller` — L181–L205
- `def TestTomanValuation.test_irt_is_valued_from_the_toman_rate` — L207–L220
- `def TestTomanValuation.test_rial_is_ten_times_cheaper_than_toman` — L222–L228
- `def TestTomanValuation.test_without_a_rate_it_returns_zero_instead_of_crashing` — L230–L234
- `def TestTomanValuation.test_usdt_is_always_one` — L236–L239

### `tests/test_icons_search_theme.py`

آزمون‌های نقص‌های گزارش‌شده در نسخهٔ ۱٫۵٫۱.

ارجاع داخلی: `ai/providers/__init__.py`, `app/application.py`, `ui/icons/__init__.py`, `ui/widgets/chrome.py`, `ui/windows/main_window.py`.
- `def test_every_icon_renders_a_non_empty_pixmap` — L22–L32
- `def test_icon_returns_qicon_with_content` — L35–L39
- `def test_unknown_icon_falls_back_instead_of_crashing` — L42–L45
- `def test_icon_svg_has_no_unresolved_currentcolor` — L48–L56
- `def test_all_navigation_icons_exist` — L59–L64
- `def search_box` — L71–L84
- `def test_search_box_has_completer_with_suggestions` — L87–L93
- `def test_search_suggestions_match_in_the_middle` — L96–L100
- `def test_choosing_a_suggestion_emits_kind_and_value` — L103–L108
- `def test_fallback_registers_more_than_the_active_provider` — L114–L136
- `def test_provider_without_key_is_not_registered` — L139–L150
- `def test_fallback_disabled_registers_nothing_extra` — L153–L166
- `def test_chat_agent_prefers_the_selected_provider` — L169–L196

### `tests/test_indicators.py`

آزمون موتور اندیکاتور.

ارجاع داخلی: `app/exceptions/__init__.py`, `indicators/__init__.py`, `indicators/registry.py`, `tests/conftest.py`.
- `def test_all_builtin_indicators_are_registered` — L13–L18
- `def test_indicator_categories_cover_five_groups` — L21–L24
- `def test_sma_matches_manual_calculation` — L27–L32
- `def test_rsi_stays_within_bounds` — L35–L39
- `def test_uptrend_produces_bullish_signals` — L42–L46
- `def test_insufficient_data_raises` — L49–L53
- `def test_invalid_parameter_raises` — L56–L60
- `def test_calculate_many_isolates_failures` — L63–L68
- `def test_cache_returns_same_values` — L71–L76
- `def test_analyze_timeframe_requires_minimum_candles` — L79–L83

### `tests/test_localization.py`

آزمون بومی‌سازی — تضمین اینکه هیچ ترجمه‌ای جا نیفتاده است.

ارجاع داخلی: `localization/__init__.py`.
- `def fa` — L11–L13
- `def en` — L17–L19
- `def test_both_languages_are_available` — L22–L24
- `def test_persian_is_rtl_english_is_ltr` — L27–L30
- `def test_no_missing_keys_in_persian` — L33–L35
- `def test_no_missing_keys_in_english` — L38–L40
- `def test_navigation_keys_are_translated` — L43–L47
- `def test_missing_key_falls_back_to_key_name` — L50–L52
- `def test_variable_interpolation` — L55–L58
- `def test_language_switch_changes_output` — L61–L66
- `def test_persian_digits_round_trip` — L69–L71
- `def test_number_formatting_uses_persian_digits` — L74–L77
- `def test_confidence_note_exists_in_both_languages` — L80–L86

### `tests/test_market_resilience.py`

آزمون‌های نگهبان اتصال — قابلیت «همیشه آنلاین».

ارجاع داخلی: `market/live_feed.py`, `market/resilience.py`.
- `class FakeFeed` — L29–L48
- `def FakeFeed.__init__` — L32–L39
- `async def FakeFeed.start` — L41–L45
- `async def FakeFeed.stop` — L47–L48
- `class FakeBus` — L51–L58
- `def FakeBus.__init__` — L54–L55
- `def FakeBus.publish` — L57–L58
- `class NoSleep` — L61–L71
- `def NoSleep.__init__` — L64–L65
- `async def NoSleep.__call__` — L67–L71
- `def make_supervisor` — L74–L86
- `class TestStateDetection` — L89–L137
- `async def TestStateDetection.test_alive_and_fresh_is_online` — L92–L99
- `async def TestStateDetection.test_alive_but_stale_is_degraded` — L101–L108
- `async def TestStateDetection.test_dead_loop_is_offline_then_revived` — L110–L124
- `async def TestStateDetection.test_running_flag_alone_does_not_fool_supervisor` — L126–L137
- `class TestRevivalBackoff` — L140–L184
- `async def TestRevivalBackoff.test_exponential_growth_and_reset` — L143–L166
- `async def TestRevivalBackoff.test_delay_capped` — L168–L173
- `def TestRevivalBackoff.test_jitter_applied` — L175–L184
- `class TestEventsAndStatus` — L187–L251
- `async def TestEventsAndStatus.test_transition_publishes_event` — L190–L203
- `async def TestEventsAndStatus.test_failed_revival_counted` — L205–L215
- `async def TestEventsAndStatus.test_status_shape` — L217–L228
- `async def TestEventsAndStatus.test_supervisor_survives_feed_exceptions` — L230–L251
- `class TestEventsAndStatus.test_supervisor_survives_feed_exceptions.PoisonFlag` — L233–L237
- `def TestEventsAndStatus.test_supervisor_survives_feed_exceptions.PoisonFlag.__bool__` — L236–L237
- `class TestLiveFeedPollAlive` — L254–L277
- `def TestLiveFeedPollAlive.test_poll_alive_reflects_task_state` — L257–L277
- `class TestLiveFeedPollAlive.test_poll_alive_reflects_task_state.DoneTask` — L265–L267
- `def TestLiveFeedPollAlive.test_poll_alive_reflects_task_state.DoneTask.done` — L266–L267
- `class TestLiveFeedPollAlive.test_poll_alive_reflects_task_state.LiveTask` — L272–L274
- `def TestLiveFeedPollAlive.test_poll_alive_reflects_task_state.LiveTask.done` — L273–L274

### `tests/test_markets_sorting.py`

آزمون‌های مرتب‌سازی و کلیک صفحهٔ بازارها و مدال جزئیات ارز.

ارجاع داخلی: `localization/__init__.py`, `ui/dialogs/coin_detail_dialog.py`, `ui/pages/markets_page.py`.
- `def page` — L38–L44
- `def order_of` — L47–L52
- `def test_default_sort_is_by_quote_value` — L58–L65
- `def test_sort_by_volume` — L68–L72
- `def test_sort_by_gainers` — L75–L79
- `def test_sort_by_losers` — L82–L86
- `def test_sort_by_price_descending` — L89–L93
- `def test_sort_by_price_ascending` — L96–L100
- `def test_sort_by_name` — L103–L107
- `def test_explicit_quote_volume_field_wins` — L110–L116
- `def test_sort_combo_has_all_modes` — L119–L123
- `def test_changing_combo_reorders_table` — L126–L130
- `def test_sorting_survives_filtering` — L133–L141
- `def test_numeric_item_compares_by_number` — L147–L154
- `def test_header_click_sorts_numerically` — L157–L162
- `def test_header_click_rebuilds_index` — L165–L169
- `def test_clicking_row_emits_symbol` — L175–L180
- `def test_row_data_returns_raw_row` — L183–L187
- `def test_row_data_of_unknown_symbol` — L190–L192
- `def dialog` — L199–L207
- `def test_dialog_shows_symbol` — L210–L213
- `def test_dialog_default_timeframe` — L216–L218
- `def test_dialog_has_all_timeframes` — L221–L223
- `def test_dialog_analyze_button_emits` — L226–L231
- `def test_dialog_signal_button_emits` — L234–L239
- `def test_dialog_respects_selected_timeframe` — L242–L249
- `def test_dialog_chat_and_market_buttons` — L252–L261
- `def test_dialog_watchlist_toggles` — L264–L271
- `def test_dialog_apply_details` — L274–L277
- `def test_dialog_details_error_keeps_window_usable` — L280–L283
- `def test_dialog_snapshot_updates_price` — L286–L289
- `def test_dialog_rtl_layout` — L292–L297

### `tests/test_narrative.py`

آزمون‌های نویسندهٔ تحلیل نوشتاری فارسی.

ارجاع داخلی: `ai/agent/narrative.py`.
- `def make_signal` — L19–L39
- `def test_template_has_all_four_sections` — L45–L49
- `def test_template_uses_real_numbers` — L52–L57
- `def test_wait_signal_explains_waiting` — L60–L65
- `def test_english_engine_reason_moves_to_appendix` — L68–L79
- `def test_persian_engine_reason_stays_inline` — L82–L86
- `def test_template_survives_empty_signal` — L89–L93
- `async def test_write_without_provider_uses_template` — L100–L104
- `async def test_write_uses_ai_when_available` — L108–L117
- `class test_write_uses_ai_when_available.Provider` — L111–L113
- `async def test_write_uses_ai_when_available.Provider.generate` — L112–L113
- `async def test_ai_failure_falls_back_to_template` — L121–L130
- `class test_ai_failure_falls_back_to_template.Broken` — L124–L126
- `async def test_ai_failure_falls_back_to_template.Broken.generate` — L125–L126
- `async def test_ai_timeout_falls_back_to_template` — L134–L145
- `class test_ai_timeout_falls_back_to_template.Slow` — L137–L140
- `async def test_ai_timeout_falls_back_to_template.Slow.generate` — L138–L140
- `async def test_short_ai_reply_falls_back` — L149–L157
- `class test_short_ai_reply_falls_back.Terse` — L152–L154
- `async def test_short_ai_reply_falls_back.Terse.generate` — L153–L154
- `async def test_none_response_falls_back` — L161–L169
- `class test_none_response_falls_back.Empty` — L164–L166
- `async def test_none_response_falls_back.Empty.generate` — L165–L166
- `async def test_prefer_ai_false_skips_provider` — L173–L184
- `class test_prefer_ai_false_skips_provider.Provider` — L177–L180
- `async def test_prefer_ai_false_skips_provider.Provider.generate` — L178–L180
- `def test_prompt_contains_signal_facts` — L190–L195
- `def test_prompt_includes_indicator_values` — L198–L203
- `def test_is_mostly_latin` — L209–L214
- `def test_fa_converts_digits` — L217–L220
- `def test_fa_handles_non_numeric` — L223–L225

### `tests/test_new_pages.py`

آزمون صفحه‌های تازه و پوستهٔ بیرونی پنجره.

ارجاع داخلی: `localization/__init__.py`, `tests/conftest.py`, `ui/pages/__init__.py`, `ui/themes/__init__.py`, `ui/windows/__init__.py`.
- `def qt_app` — L22–L28
- `def translator` — L32–L36
- `def window` — L40–L55
- `def test_window_exposes_core_pages` — L61–L77
- `def test_every_page_is_reachable` — L80–L84
- `def test_page_index_lookup` — L87–L93
- `def test_shortcuts_registry_is_populated` — L96–L102
- `def test_focus_mode_hides_chrome_but_keeps_pages` — L105–L117
- `def test_all_pages_survive_every_theme` — L121–L137
- `def test_theme_switch_preserves_table_data` — L140–L170
- `def test_language_switch_updates_navigation` — L173–L185
- `def test_wallet_shows_guidance_when_no_account` — L191–L204
- `def test_wallet_populates_assets_and_donut` — L207–L223
- `def test_wallet_emits_connect_request` — L226–L234
- `def test_trades_page_shows_empty_state` — L240–L246
- `def test_trades_filters_default_to_all` — L249–L258
- `def test_trades_filter_change_resets_to_first_page` — L261–L277
- `def test_trades_symbol_filter_keeps_selection_on_refresh` — L280–L290
- `def test_trades_page_carries_paper_mode_notice` — L293–L299

### `tests/test_pages_design_v151.py`

آزمون‌های طراحی نسخهٔ ۱.۵.۱ برای صفحات قدیمی.

ارجاع داخلی: `localization/__init__.py`, `ui/pages/analysis_page.py`, `ui/pages/markets_page.py`, `ui/pages/reports_page.py`, `ui/pages/signals_page.py`, `ui/themes/__init__.py`.
- `def translator` — L37–L41
- `def market_rows` — L45–L70
- `def test_markets_has_star_and_trend_columns` — L76–L91
- `def test_markets_star_click_toggles_watchlist` — L94–L113
- `def test_markets_quote_filter_and_chips` — L116–L138
- `def test_markets_watchlist_only_filter` — L141–L150
- `def test_markets_change_sign_survives_rtl` — L153–L160
- `def test_markets_star_column_is_not_sortable` — L163–L177
- `def test_analysis_indicator_panel_toggles` — L183–L206
- `def test_analysis_timeframe_bar_syncs_with_combo` — L209–L224
- `def test_signal_card_has_confidence_ring` — L230–L250
- `def test_signals_retranslate_keeps_history` — L253–L278
- `def test_reports_charts_and_stat_cards` — L284–L302
- `def test_reports_empty_summary_is_safe` — L305–L312
- `def test_updated_pages_accept_every_theme` — L319–L342

### `tests/test_paper_trader.py`

آزمون دفتر معاملهٔ تمرینی.

ارجاع داخلی: `signals/paper_trader.py`.
- `class _FakeSettings` — L18–L28
- `def _FakeSettings.__init__` — L21–L22
- `def _FakeSettings.get` — L24–L25
- `def _FakeSettings.set` — L27–L28
- `def trader` — L45–L46
- `def test_opens_position_from_long_signal` — L49–L59
- `def test_position_size_follows_risk_rule` — L62–L72
- `def test_wait_signal_opens_nothing` — L75–L80
- `def test_signal_without_entry_is_refused` — L83–L87
- `def test_positions_persist_and_reload` — L90–L97
- `def test_close_position_marks_it_closed` — L100–L107
- `def test_live_trading_is_off_by_default` — L110–L117
- `def test_corrupt_storage_does_not_crash` — L120–L127
- `def test_short_signal_uses_correct_direction` — L130–L144
- `def test_position_round_trips_through_dict` — L147–L158

### `tests/test_persian_pdf.py`

آزمون‌های خروجی PDF فارسی.

ارجاع داخلی: `reports/persian_pdf.py`.
- `def test_font_file_ships_with_project` — L28–L31
- `def test_register_fonts_succeeds` — L34–L36
- `def test_has_persian` — L42–L47
- `def test_shape_changes_persian_text` — L50–L53
- `def test_shape_leaves_english_untouched` — L56–L58
- `def test_shape_of_empty_text` — L61–L63
- `def test_shape_paragraph_keeps_line_count` — L66–L69
- `def test_wrap_persian_respects_width` — L75–L80
- `def test_wrap_persian_preserves_word_order` — L83–L93
- `def test_wrap_persian_keeps_explicit_newlines` — L96–L99
- `def test_wrap_empty_text` — L102–L104
- `def test_build_pdf_creates_file` — L110–L123
- `def test_build_pdf_without_optional_parts` — L126–L130
- `def test_build_pdf_with_english_text` — L133–L140
- `def test_build_pdf_with_mixed_text` — L143–L150
- `def test_build_pdf_creates_parent_directory` — L153–L156
- `def test_build_pdf_with_multiline_section` — L159–L163

### `tests/test_prediction_lifecycle.py`

آزمون چرخهٔ عمر پیش‌بینی: ثبت → حل → امتیاز → تایم‌لاین → موتور کامل.

ارجاع داخلی: `app/core/models.py`, `app/database/models.py`, `app/database/repositories/prediction_repository.py`, `signals/prediction/engine.py`, `signals/prediction/scoring.py`, `signals/prediction/store.py`, `signals/prediction/timeline.py`.
- `def make_candles` — L32–L46
- `def repo` — L50–L52
- `class TestRecordAndResolve` — L55–L135
- `def TestRecordAndResolve.test_record_and_due` — L58–L74
- `def TestRecordAndResolve.test_resolve_bullish_correct` — L76–L99
- `def TestRecordAndResolve.test_resolve_skips_without_price` — L101–L115
- `def TestRecordAndResolve.test_neutral_judged_by_range` — L117–L135
- `class TestScoring` — L138–L197
- `def TestScoring._record` — L141–L153
- `def TestScoring.test_accuracy_summary` — L155–L163
- `def TestScoring.test_brier_of_perfect_forecast` — L165–L167
- `def TestScoring.test_brier_of_chance_forecast` — L169–L171
- `def TestScoring.test_calibration_buckets_shape` — L173–L180
- `def TestScoring.test_model_health_from_models_json` — L182–L197
- `class TestTimeline` — L200–L252
- `def TestTimeline.test_timeline_ordered` — L203–L215
- `def TestTimeline.test_what_changed_detects_shift` — L217–L234
- `def TestTimeline.test_what_changed_none_when_stable` — L236–L239
- `def TestTimeline._fake` — L242–L252
- `class TestEngineEndToEnd` — L255–L333
- `async def TestEngineEndToEnd.test_full_assessment` — L259–L310
- `def TestEngineEndToEnd.test_full_assessment.source` — L267–L268
- `async def TestEngineEndToEnd.test_engine_returns_none_without_data` — L313–L318
- `async def TestEngineEndToEnd.test_no_duplicate_spam_records` — L321–L333

### `tests/test_prediction_ui_and_tools.py`

آزمون صفحهٔ «هوش پیش‌بینی» و ابزارهای عامل AI (v1.11.0).

ارجاع داخلی: `ai/tools/market_tools.py`, `localization/__init__.py`, `tests/conftest.py`, `ui/pages/prediction_page.py`.
- `def qt_app` — L24–L25
- `def translator` — L29–L32
- `def page` — L36–L41
- `def sample_payload` — L44–L100
- `def _all_texts` — L103–L112
- `class TestPredictionPage` — L115–L171
- `def TestPredictionPage.test_builds_and_shows_empty` — L116–L118
- `def TestPredictionPage.test_update_report_renders_horizons` — L120–L127
- `def TestPredictionPage.test_disabled_horizons_visible_with_reason` — L129–L133
- `def TestPredictionPage.test_reset_to_none_shows_empty` — L135–L139
- `def TestPredictionPage.test_busy_locks_refresh` — L141–L145
- `def TestPredictionPage.test_retranslate_keeps_data` — L147–L152
- `def TestPredictionPage.test_symbol_sync` — L154–L156
- `def TestPredictionPage.test_all_titles_translated` — L158–L171
- `class TestPredictionTools` — L174–L233
- `def TestPredictionTools._toolset` — L177–L188
- `class TestPredictionTools._toolset.FakeMarket` — L180–L185
- `async def TestPredictionTools._toolset.FakeMarket.get_candles` — L183–L185
- `def TestPredictionTools.test_report_without_engine_raises` — L190–L195
- `def TestPredictionTools.test_report_with_engine` — L197–L205
- `def TestPredictionTools.test_report_none_when_no_data` — L207–L213
- `def TestPredictionTools.test_accuracy_snapshot` — L215–L222
- `def TestPredictionTools.test_tool_definitions_registered` — L224–L233
- `class _FakeIndicators` — L236–L238
- `def _FakeIndicators.calculate_many` — L237–L238
- `class _FakeEngine` — L241–L261
- `def _FakeEngine.__init__` — L242–L243
- `async def _FakeEngine.assess` — L245–L250
- `async def _FakeEngine.accuracy_snapshot` — L252–L261

### `tests/test_predictive_phase1.py`

آزمون‌های فاز ۱ موتور هوش پیش‌بینی: کیفیت داده + خزانهٔ فیچر.

ارجاع داخلی: `app/core/models.py`, `market/quality.py`, `signals/prediction/features.py`.
- `def make_candle` — L34–L51
- `def random_walk` — L54–L76
- `class TestDataQualityDetectsProblems` — L82–L138
- `def TestDataQualityDetectsProblems.test_empty_input_is_critical` — L85–L89
- `def TestDataQualityDetectsProblems.test_duplicate_timestamps_counted` — L91–L96
- `def TestDataQualityDetectsProblems.test_gap_between_candles_detected` — L98–L103
- `def TestDataQualityDetectsProblems.test_invalid_ohlc_flagged` — L105–L109
- `def TestDataQualityDetectsProblems.test_future_candle_rejected_within_tolerance` — L111–L122
- `def TestDataQualityDetectsProblems.test_suspicious_spike_kept_but_warned` — L124–L128
- `def TestDataQualityDetectsProblems.test_misaligned_timestamp_warned` — L130–L133
- `def TestDataQualityDetectsProblems.test_unordered_input_reported` — L135–L138
- `class TestDataCleaning` — L141–L178
- `def TestDataCleaning.test_clean_removes_invalid_and_sorts_and_dedupes` — L144–L157
- `def TestDataCleaning.test_clean_never_fills_gaps` — L159–L163
- `def TestDataCleaning.test_duplicate_keeps_last_occurrence` — L165–L170
- `def TestDataCleaning.test_usable_threshold` — L172–L178
- `class TestFeatureStoreBasics` — L184–L233
- `def TestFeatureStoreBasics.test_minimal_history_returns_empty` — L187–L191
- `def TestFeatureStoreBasics.test_vectors_carry_close_time` — L193–L200
- `def TestFeatureStoreBasics.test_last_forming_candle_dropped_by_default` — L202–L207
- `def TestFeatureStoreBasics.test_base_features_available_on_realistic_data` — L209–L214
- `def TestFeatureStoreBasics.test_rsi_within_bounds` — L216–L222
- `def TestFeatureStoreBasics.test_extra_features_attached_and_aligned` — L224–L233
- `class TestNoLookAhead` — L236–L258
- `def TestNoLookAhead.test_truncated_build_matches_full_prefix` — L239–L250
- `def TestNoLookAhead.test_now_hides_unclosed_candles` — L252–L258
- `class TestFeatureMatrix` — L261–L297
- `def TestFeatureMatrix.test_matrix_drops_incomplete_rows` — L264–L277
- `def TestFeatureMatrix.test_matrix_never_imputes` — L279–L288
- `def TestFeatureMatrix.test_to_dict_shape` — L290–L297
- `class TestFeatureVectorDataclass` — L300–L307
- `def TestFeatureVectorDataclass.test_get_default` — L303–L307

### `tests/test_predictive_phase2_5.py`

آزمون‌های فازهای ۲ تا ۸ موتور هوش پیش‌بینی.

ارجاع داخلی: `app/core/models.py`, `signals/prediction/anomaly.py`, `signals/prediction/breakout.py`, `signals/prediction/crossasset.py`, `signals/prediction/distribution.py`, `signals/prediction/events.py`, `signals/prediction/features.py`, `signals/prediction/fusion.py`, `signals/prediction/horizons.py`, `signals/prediction/models/base.py`, `signals/prediction/models/drift.py`, `signals/prediction/models/ensemble.py`, `signals/prediction/models/gbm.py`, `signals/prediction/models/lstm.py`, `signals/prediction/models/statistical.py`, `signals/prediction/models/walkforward.py`, `signals/prediction/regime.py`, `signals/prediction/scenarios.py`, `signals/prediction/uncertainty.py`, `signals/prediction/volatility.py`, `signals/prediction/warning.py`.
- `def random_walk` — L62–L90
- `class TestHorizonLadder` — L96–L130
- `def TestHorizonLadder.test_ladder_is_complete` — L99–L103
- `def TestHorizonLadder.test_disabled_without_data` — L105–L109
- `def TestHorizonLadder.test_enabled_with_history_and_prefers_larger_tf` — L111–L122
- `def TestHorizonLadder.test_short_history_disables_long_horizons_only` — L124–L130
- `class TestRegimeEngine` — L136–L218
- `def TestRegimeEngine._assess` — L139–L141
- `def TestRegimeEngine.test_trending_market_detected` — L143–L150
- `def TestRegimeEngine.test_downtrend_detected` — L152–L163
- `def TestRegimeEngine.test_flat_market_is_neutral_or_range` — L165–L172
- `def TestRegimeEngine.test_insufficient_data_is_unknown` — L174–L178
- `def TestRegimeEngine.test_liquidation_never_guessed` — L180–L187
- `def TestRegimeEngine.test_drivers_present` — L189–L193
- `def TestRegimeEngine.test_transition_risk_and_confidence` — L195–L202
- `def TestRegimeEngine.test_state_machine_stage_mapping` — L204–L207
- `def TestRegimeEngine.test_transition_probabilities_from_history` — L209–L218
- `class TestDistribution` — L224–L268
- `def TestDistribution.test_empirical_quantiles_ordered` — L227–L234
- `def TestDistribution.test_probability_capped` — L236–L240
- `def TestDistribution.test_analytic_fallback_labeled` — L242–L249
- `def TestDistribution.test_none_without_data` — L251–L252
- `def TestDistribution.test_forward_returns_no_lookahead` — L254–L258
- `def TestDistribution.test_probability_of_range` — L260–L268
- `class TestVolatilityForecast` — L271–L291
- `def TestVolatilityForecast.test_sigma_grows_with_sqrt_steps` — L274–L281
- `def TestVolatilityForecast.test_labels_are_relative` — L283–L288
- `def TestVolatilityForecast.test_none_without_data` — L290–L291
- `class TestScenarios` — L297–L329
- `def TestScenarios._dist` — L300–L304
- `def TestScenarios.test_three_scenarios_sum_to_100` — L306–L310
- `def TestScenarios.test_ranges_consistent_with_quantiles` — L312–L316
- `def TestScenarios.test_conditions_and_triggers_present` — L318–L324
- `def TestScenarios.test_tree_dominant_split` — L326–L329
- `class TestBreakout` — L335–L388
- `def TestBreakout.test_probabilities_sum_to_100` — L338–L346
- `def TestBreakout.test_unavailable_factors_never_fabricated` — L348–L352
- `def TestBreakout.test_none_without_data` — L354–L355
- `def TestBreakout.test_false_breakout_detected_on_weak_volume_break` — L357–L378
- `def TestBreakout.test_no_false_breakout_without_break` — L380–L388
- `class TestAnomaly` — L394–L421
- `def TestAnomaly.test_volume_spike_detected` — L397–L401
- `def TestAnomaly.test_quiet_market_clean` — L403–L405
- `def TestAnomaly.test_early_alpha_on_flat_price_big_volume` — L407–L416
- `def TestAnomaly.test_insufficient_data_returns_empty` — L418–L421
- `class TestEarlyWarnings` — L424–L458
- `def TestEarlyWarnings.test_momentum_divergence_warning` — L427–L439
- `def TestEarlyWarnings.test_volatility_expansion_warning` — L441–L448
- `def TestEarlyWarnings.test_distribution_regime_high_severity` — L450–L458
- `class TestUncertainty` — L464–L499
- `def TestUncertainty.test_low_confidence_becomes_uncertain` — L467–L478
- `def TestUncertainty.test_clean_inputs_keep_confidence` — L480–L484
- `def TestUncertainty.test_decay_reduces_with_age` — L486–L492
- `def TestUncertainty.test_decay_monotonic` — L494–L499
- `class TestFusion` — L502–L541
- `def TestFusion.test_weighted_average` — L505–L512
- `def TestFusion.test_conflict_detected_and_declared` — L514–L521
- `def TestFusion.test_same_name_components_merged` — L523–L529
- `def TestFusion.test_multi_timeframe_reversal_detection` — L531–L541
- `class TestCrossAsset` — L547–L591
- `def TestCrossAsset.test_lead_lag_detected` — L550–L575
- `def TestCrossAsset.test_lead_lag_detected.series_from` — L558–L568
- `def TestCrossAsset.test_none_without_overlap` — L577–L578
- `def TestCrossAsset.test_market_context_labels` — L580–L583
- `def TestCrossAsset.test_rolling_correlation_shape` — L585–L591
- `class TestEvents` — L594–L631
- `def TestEvents.test_parse_and_pressure` — L597–L608
- `def TestEvents.test_far_event_no_pressure` — L610–L618
- `def TestEvents.test_malformed_entries_skipped` — L620–L626
- `def TestEvents.test_json_string_accepted` — L628–L631
- `def make_dataset` — L638–L660
- `def with_volume` — L663–L671
- `def full_row` — L674–L676
- `class TestModels` — L679–L791
- `def TestModels.test_forward_labels_exclude_neutral_band` — L682–L687
- `def TestModels.test_statistical_model_fits_and_predicts` — L689–L699
- `def TestModels.test_gbm_learns_real_signal` — L701–L712
- `def TestModels.test_gbm_unavailable_without_libs` — L714–L720
- `def TestModels.test_walk_forward_blocks_leakage` — L722–L738
- `def TestModels.test_walk_forward_insufficient_data` — L740–L744
- `def TestModels.test_ensemble_weights_and_predict` — L746–L758
- `def TestModels.test_ensemble_reweight` — L760–L768
- `def TestModels.test_lstm_trains_and_predicts` — L770–L780
- `def TestModels.test_drift_detection` — L782–L787
- `def TestModels.test_drift_ok_and_unknown` — L789–L791

### `tests/test_reports.py`

آزمون گزارش‌گیری در همه قالب‌ها.

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`, `app/core/paths.py`, `app/database/repositories/__init__.py`, `app/database/session.py`, `app/exceptions/__init__.py`, `reports/__init__.py`.
- `def report_setup` — L21–L52
- `def test_report_contains_all_signals` — L55–L60
- `def test_summary_has_no_win_rate` — L63–L70
- `def test_every_format_produces_a_file` — L74–L79
- `def test_json_export_is_parsable` — L82–L89
- `def test_excel_has_two_sheets` — L92–L100
- `def test_pdf_has_valid_header` — L103–L108
- `def test_html_is_self_contained` — L111–L120
- `def test_csv_uses_bom_for_excel_compatibility` — L123–L130
- `def test_empty_report_does_not_crash` — L133–L139
- `def test_unsupported_format_is_rejected` — L142–L147

### `tests/test_risk_engine.py`

آزمون موتور ریسک — حساس‌ترین بخش از نظر ایمنی سرمایه.

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`, `signals/risk_engine.py`.
- `def test_long_stop_loss_is_below_entry` — L12–L16
- `def test_short_stop_loss_is_above_entry` — L19–L23
- `def test_structural_stop_is_preferred_when_valid` — L26–L32
- `def test_stop_distance_is_clamped_to_user_limit` — L35–L41
- `def test_take_profits_are_ordered_for_long` — L44–L49
- `def test_take_profits_are_ordered_for_short` — L52–L57
- `def test_low_risk_reward_is_rejected` — L60–L65
- `def test_stop_tighter_than_atr_is_rejected` — L68–L73
- `def test_wrong_side_stop_is_rejected` — L76–L80
- `def test_valid_setup_is_approved` — L83–L89
- `def test_leverage_never_exceeds_user_maximum` — L92–L97
- `def test_position_size_respects_risk_percent` — L100–L107

### `tests/test_settings_expanded.py`

آزمون‌های تنظیمات گسترش‌یافته (نسخهٔ ۱.۴).

ارجاع داخلی: `app/config/defaults.py`, `localization/__init__.py`, `ui/pages/markets_page.py`, `ui/pages/settings_page.py`, `ui/themes/__init__.py`.
- `def page` — L41–L45
- `def test_new_setting_has_default` — L52–L54
- `def test_default_signal_mode_is_hybrid` — L57–L59
- `def test_default_markets_sort_is_value` — L62–L64
- `def test_narrative_enabled_by_default` — L67–L69
- `def test_chat_history_saved_by_default` — L72–L74
- `def test_page_has_eight_tabs` — L80–L89
- `def test_appearance_tab_exists_with_theme_cards` — L92–L101
- `def test_selecting_theme_card_emits_live_preview` — L104–L109
- `def test_tab_titles_are_translated` — L112–L117
- `def test_tab_titles_change_with_language` — L120–L127
- `def test_signal_mode_combo_has_three_modes` — L130–L133
- `def test_markets_sort_combo_matches_markets_page` — L136–L141
- `def test_font_scale_range` — L144–L147
- `def test_refresh_interval_has_sane_minimum` — L150–L157
- `def test_parallel_requests_bounded` — L160–L163
- `def test_round_trip_of_new_keys` — L169–L195
- `def test_collect_covers_all_new_keys` — L198–L202
- `def test_load_with_missing_keys_uses_defaults` — L205–L211
- `def test_load_with_unknown_sort_mode_is_safe` — L214–L217
- `def test_boolean_settings_round_trip_true` — L220–L226
- `def test_new_translation_keys_exist` — L257–L266

### `tests/test_signal_engine.py`

آزمون موتور سیگنال — با تأکید بر استقلال از هوش مصنوعی.

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`, `indicators/__init__.py`, `signals/__init__.py`, `tests/conftest.py`.
- `def _engine` — L14–L16
- `async def test_strong_uptrend_produces_long` — L20–L27
- `async def test_strong_downtrend_produces_short` — L31–L38
- `async def test_no_data_returns_wait_not_crash` — L42–L48
- `async def test_impossible_risk_reward_forces_wait` — L52–L58
- `async def test_confidence_is_within_bounds` — L62–L66
- `async def test_leverage_respects_user_limit` — L70–L75
- `async def test_signal_works_without_any_ai` — L79–L87
- `async def test_ai_failure_does_not_break_signal` — L91–L106
- `class test_ai_failure_does_not_break_signal.BrokenAnalyst` — L98–L102
- `async def test_ai_failure_does_not_break_signal.BrokenAnalyst.analyze` — L101–L102
- `async def test_partial_timeframe_failure_is_tolerated` — L110–L115

### `tests/test_themes.py`

آزمون سامانهٔ پوسته.

ارجاع داخلی: `ui/themes/__init__.py`, `ui/themes/tokens.py`.
- `def test_catalog_has_all_named_themes` — L27–L39
- `def test_default_theme_is_corporate_navy` — L42–L55
- `def test_every_theme_has_a_name_in_both_languages` — L58–L62
- `def test_stylesheet_builds_without_leftover_placeholders` — L66–L76
- `def test_stylesheet_covers_all_component_roles` — L80–L112
- `def test_legacy_theme_names_still_resolve` — L115–L121
- `def test_manager_resolves_and_reports_current` — L124–L133
- `def test_font_scale_changes_metrics_not_colors` — L136–L146
- `def test_compact_mode_reduces_spacing` — L149–L154
- `def test_all_themes_define_the_same_color_tokens` — L157–L166
- `def test_theme_tokens_are_immutable` — L169–L174

### `tests/test_timeframes.py`

آزمون موتور تایم‌فریم.

ارجاع داخلی: `market/timeframes.py`, `tests/conftest.py`.
- `def test_fourteen_timeframes_are_defined` — L18–L30
- `def test_monthly_timeframe_is_available` — L33–L38
- `def test_monthly_alignment_snaps_to_first_of_month` — L41–L53
- `def test_monthly_cannot_be_aggregated` — L56–L61
- `def test_monthly_is_never_confused_with_one_minute` — L64–L79
- `def test_timeframe_seconds_are_correct` — L82–L88
- `def test_weekly_alignment_starts_on_monday` — L91–L102
- `def test_aggregation_produces_fewer_candles` — L105–L109
- `def test_aggregation_preserves_ohlc_semantics` — L112–L121
- `def test_unsupported_timeframes_find_an_aggregation_source` — L124–L132
- `def test_candles_needed_accounts_for_aggregation` — L135–L137

### `tests/test_toobit_bitpin_providers.py`

آزمون‌های ارائه‌دهنده‌های Toobit و Bitpin.

ارجاع داخلی: `app/exceptions/__init__.py`, `localization/__init__.py`, `market/exchange_catalog.py`, `market/providers/bitpin/parser.py`, `market/providers/bitpin/provider.py`, `market/providers/registry.py`, `market/providers/toobit/parser.py`, `market/providers/toobit/provider.py`, `market/providers/toobit/rest_client.py`.
- `def test_toobit_ticker_converts_fraction_to_percent` — L125–L130
- `def test_toobit_klines_convert_ms_to_seconds` — L133–L138
- `def test_toobit_symbols_derive_precision_from_filters` — L141–L150
- `def test_toobit_symbol_roundtrip` — L153–L157
- `def test_toobit_signature_is_lowercase_hex` — L163–L184
- `def test_toobit_signed_request_requires_credentials` — L187–L191
- `def test_toobit_scrub_removes_secrets_from_log_text` — L194–L201
- `def test_bitpin_markets_skip_untradable` — L207–L211
- `def test_bitpin_change_percent_is_not_rescaled` — L214–L218
- `def test_bitpin_symbol_roundtrip` — L221–L224
- `def test_bitpin_candles_built_from_matches` — L227–L251
- `def test_bitpin_balances_accept_paginated_payload` — L254–L260
- `def test_bitpin_rejects_long_timeframes` — L263–L272
- `def test_bitpin_orderbook_is_sorted` — L275–L284
- `def test_both_exchanges_are_registered` — L290–L298
- `def test_factories_build_providers` — L301–L304
- `def test_presets_are_selectable_in_settings` — L307–L322
- `def test_provider_capabilities_are_honest` — L325–L339
- `def test_credential_errors_never_echo_the_secret` — L342–L353
- `def test_missing_credentials_are_reported_before_network` — L356–L361
- `def test_connection_messages_are_translation_keys` — L364–L390
- `def test_exchange_hints_exist_for_new_exchanges` — L393–L406

### `tests/test_trades_and_wallet.py`

آزمون معاملات کاغذی و صفحه‌های تازه (تاریخچهٔ معاملات و کیف پول).

ارجاع داخلی: `app/database/models.py`, `app/database/repositories/__init__.py`, `app/database/session.py`.
- `def trades` — L20–L32
- `def test_trade_defaults_to_paper_mode` — L38–L48
- `def test_long_profit_is_positive_when_price_rises` — L51–L59
- `def test_short_profits_when_price_falls` — L62–L69
- `def test_short_loses_when_price_rises` — L72–L79
- `def test_leverage_multiplies_percent_not_absolute` — L82–L89
- `def test_fee_is_deducted_from_profit` — L92–L99
- `def test_closing_twice_is_rejected` — L102–L108
- `def test_cancel_leaves_no_profit` — L111–L117
- `def _seed` — L123–L135
- `def test_filters_narrow_results` — L138–L145
- `def test_pagination_uses_limit_and_offset` — L148–L157
- `def test_statistics_are_consistent` — L160–L171
- `def test_statistics_on_empty_history_do_not_divide_by_zero` — L174–L181
- `def test_equity_curve_follows_closed_trades` — L184–L190
- `def test_trades_are_isolated_per_user` — L193–L202
- `def test_clear_history_only_affects_target_user` — L205–L215

### `tests/test_ui_wiring.py`

آزمون‌های اتصال رابط کاربری.

ارجاع داخلی: `localization/__init__.py`, `market/timeframes.py`, `ui/pages/analysis_page.py`, `ui/pages/markets_page.py`, `ui/pages/settings_page.py`, `ui/pages/signals_page.py`, `ui/themes/__init__.py`, `ui/widgets/__init__.py`.
- `def qt_app` — L32–L34
- `def translator` — L38–L39
- `def palette` — L43–L46
- `def test_refresh_button_shows_busy_then_done` — L52–L65
- `def test_refresh_button_restores_on_failure` — L68–L76
- `def test_analysis_page_offers_every_timeframe` — L82–L88
- `def test_signals_page_offers_every_timeframe` — L91–L97
- `def test_pages_accept_full_symbol_list` — L103–L113
- `def test_symbol_selection_survives_reload` — L116–L124
- `def test_markets_page_has_usd_and_toman_columns` — L130–L135
- `def test_toman_column_needs_a_rate` — L138–L146
- `def test_rising_price_is_green_falling_is_red` — L149–L171
- `def test_price_update_lands_on_the_correct_row` — L174–L196
- `def test_live_update_preserves_colour_on_periodic_reload` — L199–L212
- `def test_settings_offers_multiple_exchanges` — L218–L226
- `def test_settings_offers_many_ai_providers` — L229–L238
- `def test_ai_key_field_disabled_for_local_providers` — L241–L253
- `def test_secrets_are_namespaced_per_exchange_and_provider` — L256–L271
- `def test_settings_collects_ai_enabled_flag` — L274–L281

### `tests/test_v153_fixes.py`

آزمون‌های ایرادهای گزارش‌شده روی نسخهٔ ۱٫۵٫۲.

ارجاع داخلی: `ai/agent/chat_agent.py`, `ai/providers/ollama_provider.py`, `ai/providers/openai_compatible.py`, `localization/__init__.py`, `ui/controllers/async_runner.py`, `ui/pages/analysis_page.py`, `ui/pages/chat_page.py`, `ui/pages/markets_page.py`, `ui/widgets/trend_cell.py`.
- `def translator` — L24–L28
- `def test_repeated_submits_do_not_pile_up` — L34–L69
- `async def test_repeated_submits_do_not_pile_up.slow` — L47–L51
- `def test_different_keys_still_run_in_parallel` — L72–L95
- `async def test_different_keys_still_run_in_parallel.slow` — L80–L84
- `def test_opting_out_of_coalescing_keeps_both` — L98–L119
- `async def test_opting_out_of_coalescing_keeps_both.work` — L106–L108
- `def test_trend_cell_shows_persian_direction_and_colour` — L125–L140
- `def test_trend_cell_without_history_still_labels` — L143–L154
- `def test_markets_price_column_says_tether` — L157–L163
- `def test_every_market_row_gets_a_trend_widget` — L166–L178
- `def test_indicator_select_all_and_clear` — L184–L201
- `def test_indicator_toggle_is_reachable` — L204–L213
- `def test_chat_prompt_allows_general_conversation` — L219–L233
- `def test_chat_prompt_prefers_plain_text` — L236–L244
- `def test_chat_bubble_is_chatgpt_style` — L247–L258
- `def test_long_chat_message_is_not_clipped` — L261–L279
- `def test_local_provider_uses_short_connect_timeout` — L285–L295
- `def test_ollama_probe_timeout_is_short` — L298–L302

### `tests/test_v154_ai_signal.py`

آزمون‌های نقص‌های مسیر سیگنالِ هوش مصنوعی (نسخهٔ ۱٫۵٫۴).

ارجاع داخلی: `ai/agent/analyst.py`, `ai/agent/autonomous_agent.py`, `ai/agent/chat_agent.py`, `ai/agent/narrative.py`, `ai/providers/base.py`, `localization/__init__.py`, `ui/pages/chat_page.py`, `ui/pages/signals_page.py`.
- `def test_reasoning_alias_is_accepted` — L18–L37
- `def test_every_reason_alias_maps` — L44–L49
- `def test_explicit_reason_wins_over_alias` — L52–L59
- `def test_stop_loss_aliases_map` — L62–L68
- `def test_narrative_sends_real_message_objects` — L74–L116
- `class test_narrative_sends_real_message_objects.FakeManager` — L93–L103
- `async def test_narrative_sends_real_message_objects.FakeManager.generate` — L96–L103
- `class test_narrative_sends_real_message_objects.FakeManager.generate.Response` — L100–L101
- `def test_agents_accept_preferred_provider` — L122–L137
- `def test_signals_page_exposes_timeframe_selection` — L143–L155
- `def test_empty_timeframe_selection_falls_back` — L158–L171
- `def test_chat_mode_chips_default_and_switch` — L177–L194
- `def test_chat_mode_reaches_the_model` — L197–L210
- `def test_chat_modes_do_not_gate_tools` — L213–L227

### `tests/test_v154_localization.py`

آزمون‌های کامل‌بودن ترجمه و درستی راست‌به‌چپ.

ارجاع داخلی: `localization/__init__.py`, `ui/pages/markets_page.py`.
- `def _flatten` — L20–L27
- `def _load` — L30–L35
- `def catalogs` — L39–L41
- `def test_languages_have_identical_keys` — L44–L52
- `def test_no_empty_translations` — L55–L60
- `def test_every_key_used_in_code_exists` — L63–L81
- `def test_previously_missing_keys_resolve` — L88–L97
- `def test_wait_message_interpolates_direction` — L100–L113
- `def test_market_symbols_are_not_rtl_mangled` — L116–L138

### `tests/test_v154_packaging.py`

آزمون‌های پیکربندی بسته‌بندی ویندوزی.

ارجاع داخلی: `app/core/constants.py`.
- `def spec_text` — L19–L22
- `def test_critical_data_is_bundled` — L35–L37
- `def test_persian_font_is_bundled` — L40–L56
- `def test_pandas_submodules_are_not_excluded` — L59–L68
- `def test_dynamic_registries_are_hidden_imports` — L71–L74
- `def test_gui_app_has_no_console_window` — L77–L79
- `def test_version_is_consistent` — L82–L91

### `tests/test_v154_security_money.py`

آزمون‌های امنیت راز و مسیر پول.

ارجاع داخلی: `app/application.py`, `app/core/paths.py`, `signals/paper_trader.py`.
- `def tmp_data_dir` — L21–L23
- `def app_instance` — L27–L40
- `def _make_account` — L46–L61
- `def test_secrets_are_never_stored_in_plain_text` — L64–L81
- `def test_secret_roundtrip_and_masking` — L84–L93
- `def test_upstream_errors_do_not_leak_secrets` — L96–L120
- `class test_upstream_errors_do_not_leak_secrets.ExplodingProvider` — L105–L112
- `async def test_upstream_errors_do_not_leak_secrets.ExplodingProvider.test_credentials` — L108–L109
- `async def test_upstream_errors_do_not_leak_secrets.ExplodingProvider.close` — L111–L112
- `def test_live_trading_is_off_by_default` — L126–L134
- `def test_position_size_matches_allowed_risk` — L137–L164
- `def test_wait_signal_opens_no_position` — L167–L172
- `def test_positions_survive_a_new_instance` — L175–L197

### `tests/test_v155_ui_and_ai.py`

آزمون‌های نسخهٔ ۱٫۵٫۵ — کرش مدال بازار، نشانی سرویس هوش مصنوعی و ظاهر.

ارجاع داخلی: `app/application.py`, `app/config/defaults.py`, `app/core/constants.py`, `localization/__init__.py`, `ui/controllers/async_runner.py`, `ui/controllers/main_controller.py`, `ui/dialogs/coin_detail_dialog.py`, `ui/themes/__init__.py`, `ui/widgets/__init__.py`.
- `def test_dialog_alive_detects_destroyed_widget` — L17–L45
- `def test_async_runner_can_cancel_by_key` — L48–L75
- `async def test_async_runner_can_cancel_by_key.slow` — L63–L65
- `def test_base_url_resolution` — L95–L106
- `def test_default_base_url_is_empty` — L109–L113
- `def test_midnight_aurora_theme_is_registered` — L119–L130
- `def test_every_theme_builds_a_stylesheet` — L133–L142
- `def test_avatar_paints_in_both_states` — L145–L162
- `def test_buttons_use_soft_corners` — L165–L179

### `tests/test_v156_fixes.py`

آزمون‌های رگرسیون نسخهٔ ۱.۵.۶.

ارجاع داخلی: `ai/agent/autonomous_agent.py`, `ai/agent/validator.py`, `ai/providers/base.py`, `ai/providers/ollama_provider.py`, `ai/providers/openai_compatible.py`, `ai/providers/ranking.py`, `app/application.py`, `app/core/__init__.py`, `app/core/exchange_account_service.py`, `app/database/repositories/user_repository.py`, `market/providers/lbank/provider.py`, `ui/controllers/main_controller.py`.
- `class TestLBankBalanceParsing` — L21–L56
- `def TestLBankBalanceParsing._parse` — L25–L27
- `def TestLBankBalanceParsing.test_list_payload_is_parsed` — L29–L37
- `def TestLBankBalanceParsing.test_dict_payload_still_supported` — L39–L42
- `def TestLBankBalanceParsing.test_zero_free_does_not_fall_through` — L44–L51
- `def TestLBankBalanceParsing.test_empty_and_malformed_are_safe` — L53–L56
- `class TestLoginIdentifiers` — L62–L100
- `def TestLoginIdentifiers.account` — L66–L77
- `def TestLoginIdentifiers.test_valid_identifiers_authenticate` — L84–L88
- `def TestLoginIdentifiers.test_wrong_password_rejected` — L90–L94
- `def TestLoginIdentifiers.test_unknown_identifier_rejected` — L96–L100
- `class TestTruncatedJsonRecovery` — L106–L145
- `def TestTruncatedJsonRecovery.test_truncated_final_is_recovered` — L109–L118
- `def TestTruncatedJsonRecovery.test_truncated_number_is_dropped_not_corrupted` — L120–L131
- `def TestTruncatedJsonRecovery.test_complete_json_unchanged` — L133–L136
- `def TestTruncatedJsonRecovery.test_fenced_json_supported` — L138–L141
- `def TestTruncatedJsonRecovery.test_pure_prose_returns_none` — L143–L145
- `class TestModelRanking` — L151–L191
- `def TestModelRanking.test_flagship_beats_small_model` — L154–L156
- `def TestModelRanking.test_irrelevant_models_sink` — L158–L164
- `def TestModelRanking.test_opus_outranks_haiku` — L166–L168
- `def TestModelRanking.test_vendor_diversity_in_top_results` — L170–L180
- `def TestModelRanking.test_free_flag_detected` — L182–L185
- `def TestModelRanking.test_sorting_is_stable_and_deduplicated` — L187–L191
- `class TestIndirectPricing` — L197–L250
- `def TestIndirectPricing._controller` — L201–L215
- `async def TestIndirectPricing._controller.fake_ticker` — L210–L211
- `def TestIndirectPricing.test_direct_usdt_pair_preferred` — L217–L222
- `def TestIndirectPricing.test_bridge_pair_used_when_no_usdt_market` — L224–L234
- `def TestIndirectPricing.test_tether_is_one_without_any_market` — L236–L240
- `def TestIndirectPricing.test_unpriceable_asset_returns_zero` — L242–L250
- `class TestDailyQuotaMessage` — L253–L297
- `def TestDailyQuotaMessage._raise_for` — L257–L277
- `class TestDailyQuotaMessage._raise_for.FakeResponse` — L261–L268
- `def TestDailyQuotaMessage._raise_for.FakeResponse.json` — L265–L266
- `def TestDailyQuotaMessage.test_daily_limit_is_not_reported_as_missing_credit` — L279–L292
- `def TestDailyQuotaMessage.test_real_credit_exhaustion_still_detected` — L294–L297
- `class TestDuplicateToolCalls` — L300–L362
- `def TestDuplicateToolCalls.test_repeated_identical_call_is_blocked` — L303–L362
- `class TestDuplicateToolCalls.test_repeated_identical_call_is_blocked.FakeTools` — L316–L324
- `def TestDuplicateToolCalls.test_repeated_identical_call_is_blocked.FakeTools.get_definitions` — L318–L319
- `async def TestDuplicateToolCalls.test_repeated_identical_call_is_blocked.FakeTools.execute` — L322–L324
- `class TestDuplicateToolCalls.test_repeated_identical_call_is_blocked.FakeProviders` — L326–L339
- `async def TestDuplicateToolCalls.test_repeated_identical_call_is_blocked.FakeProviders.generate` — L328–L339
- `class TestFuturesBalances` — L368–L460
- `def TestFuturesBalances._parse` — L372–L375
- `def TestFuturesBalances.test_list_and_wrapped_shapes` — L377–L384
- `def TestFuturesBalances.test_malformed_is_safe` — L386–L389
- `async def TestFuturesBalances.test_spot_and_futures_are_merged` — L392–L427
- `class TestFuturesBalances.test_spot_and_futures_are_merged.Provider` — L400–L408
- `async def TestFuturesBalances.test_spot_and_futures_are_merged.Provider.get_account_balance` — L401–L402
- `async def TestFuturesBalances.test_spot_and_futures_are_merged.Provider.get_futures_balance` — L404–L405
- `async def TestFuturesBalances.test_spot_and_futures_are_merged.Provider.close` — L407–L408
- `async def TestFuturesBalances.test_futures_failure_keeps_spot` — L430–L460
- `class TestFuturesBalances.test_futures_failure_keeps_spot.Provider` — L438–L446
- `async def TestFuturesBalances.test_futures_failure_keeps_spot.Provider.get_account_balance` — L439–L440
- `async def TestFuturesBalances.test_futures_failure_keeps_spot.Provider.get_futures_balance` — L442–L443
- `async def TestFuturesBalances.test_futures_failure_keeps_spot.Provider.close` — L445–L446
- `class TestWalletAccountSwitching` — L463–L495
- `def TestWalletAccountSwitching.test_set_default_moves_the_active_flag` — L466–L495
- `class TestOllamaContextWindow` — L498–L581
- `def TestOllamaContextWindow._provider` — L515–L524
- `def TestOllamaContextWindow.test_window_grows_for_a_long_prompt_when_memory_allows` — L527–L538
- `def TestOllamaContextWindow.test_window_never_exceeds_what_the_machine_can_load` — L540–L553
- `def TestOllamaContextWindow.test_short_chat_prompt_does_not_ask_for_a_big_window` — L555–L568
- `def TestOllamaContextWindow.test_prompt_budget_leaves_room_for_the_answer` — L570–L581
- `class TestWaitReasonFallback` — L584–L603
- `def TestWaitReasonFallback.test_thought_is_used_when_reason_missing` — L587–L603
- `class TestFuturesAccessVisibility` — L609–L691
- `async def TestFuturesAccessVisibility.test_missing_futures_access_is_reported` — L613–L646
- `class TestFuturesAccessVisibility.test_missing_futures_access_is_reported.Provider` — L623–L631
- `async def TestFuturesAccessVisibility.test_missing_futures_access_is_reported.Provider.test_credentials` — L624–L625
- `async def TestFuturesAccessVisibility.test_missing_futures_access_is_reported.Provider.fetch_futures_balance` — L627–L628
- `async def TestFuturesAccessVisibility.test_missing_futures_access_is_reported.Provider.close` — L630–L631
- `async def TestFuturesAccessVisibility.test_full_access_has_no_warning` — L649–L676
- `class TestFuturesAccessVisibility.test_full_access_has_no_warning.Provider` — L653–L661
- `async def TestFuturesAccessVisibility.test_full_access_has_no_warning.Provider.test_credentials` — L654–L655
- `async def TestFuturesAccessVisibility.test_full_access_has_no_warning.Provider.fetch_futures_balance` — L657–L658
- `async def TestFuturesAccessVisibility.test_full_access_has_no_warning.Provider.close` — L660–L661
- `def TestFuturesAccessVisibility.test_sync_uses_the_guarded_variant` — L678–L691

### `tests/test_v158_security_tab.py`

آزمون‌های زبانهٔ امنیت (نسخهٔ ۱.۵.۸).

ارجاع داخلی: `localization/__init__.py`, `ui/controllers/main_controller.py`, `ui/pages/markets_page.py`, `ui/pages/settings_page.py`.
- `class TestTabKeyAlignment` — L23–L47
- `def TestTabKeyAlignment.test_tab_count_matches_keys` — L26–L29
- `def TestTabKeyAlignment.test_labels_survive_language_switch` — L31–L43
- `def TestTabKeyAlignment.test_security_tab_exists` — L45–L47
- `class TestSecurityTabWidgets` — L53–L192
- `def TestSecurityTabWidgets.page` — L57–L59
- `def TestSecurityTabWidgets.test_widgets_present` — L61–L75
- `def TestSecurityTabWidgets.test_password_fields_are_masked` — L77–L86
- `def TestSecurityTabWidgets.test_password_signal_carries_three_values` — L88–L98
- `def TestSecurityTabWidgets.test_clear_password_inputs` — L100–L108
- `def TestSecurityTabWidgets.test_sessions_table_fills` — L110–L128
- `def TestSecurityTabWidgets.test_revoke_emits_selected_id` — L130–L142
- `def TestSecurityTabWidgets.test_revoke_works_in_rtl_layout` — L144–L171
- `def TestSecurityTabWidgets.test_revoke_without_selection_warns` — L173–L182
- `def TestSecurityTabWidgets.test_guest_mode_disables_controls` — L184–L192
- `class TestSecurityController` — L198–L246
- `def TestSecurityController.test_password_mismatch_never_reaches_service` — L201–L230
- `class TestSecurityController.test_password_mismatch_never_reaches_service.FakeAuth` — L211–L216
- `def TestSecurityController.test_password_mismatch_never_reaches_service.FakeAuth.change_password` — L214–L216
- `class TestSecurityController.test_password_mismatch_never_reaches_service.FakeApp` — L218–L219
- `def TestSecurityController.test_expired_detection_handles_bad_input` — L232–L237
- `def TestSecurityController.test_expired_detection_flags_past` — L239–L246
- `class TestSecurityTranslations` — L252–L288
- `def TestSecurityTranslations.test_key_resolves` — L279–L283
- `def TestSecurityTranslations.test_others_revoked_has_placeholder` — L285–L288
- `class TestRtlRowSelection` — L294–L380
- `def TestRtlRowSelection.rtl` — L325–L332
- `def TestRtlRowSelection.test_default_account_is_selected_in_rtl` — L334–L343
- `def TestRtlRowSelection.test_account_buttons_fire_in_rtl` — L345–L360
- `def TestRtlRowSelection.test_markets_selected_symbol_in_rtl` — L362–L380

### `tests/test_v160_error_keys.py`

آزمون‌های نسخهٔ ۱.۶.۰ — پیام‌های خطا، قالب گزارش و بستن معامله.

ارجاع داخلی: `app/exceptions/errors.py`, `localization/__init__.py`, `ui/controllers/main_controller.py`, `ui/pages/reports_page.py`, `ui/pages/trades_page.py`.
- `def _declared_keys` — L24–L27
- `class TestExceptionUserKeys` — L33–L107
- `def TestExceptionUserKeys.test_at_least_one_key_declared` — L36–L38
- `def TestExceptionUserKeys.test_no_singular_namespace_remains` — L40–L47
- `def TestExceptionUserKeys.test_every_key_resolves` — L50–L54
- `def TestExceptionUserKeys.test_translations_are_not_echoes` — L57–L61
- `def TestExceptionUserKeys.test_real_exceptions_produce_persian_text` — L63–L86
- `def TestExceptionUserKeys.test_controller_prefers_the_user_key` — L88–L107
- `class TestReportFormatSelection` — L113–L159
- `def TestReportFormatSelection.page` — L117–L121
- `def TestReportFormatSelection.test_default_is_csv` — L123–L125
- `def TestReportFormatSelection.test_every_entry_maps_to_a_code` — L127–L133
- `def TestReportFormatSelection.test_selection_survives_language_switch` — L135–L150
- `def TestReportFormatSelection.test_format_labels_translate` — L153–L159
- `class TestCloseTradeButton` — L165–L249
- `def TestCloseTradeButton.page` — L195–L201
- `def TestCloseTradeButton.test_button_exists` — L203–L206
- `def TestCloseTradeButton.test_open_trade_closes` — L208–L214
- `def TestCloseTradeButton.test_closed_trade_is_rejected` — L216–L225
- `def TestCloseTradeButton.test_no_selection_warns` — L227–L234
- `def TestCloseTradeButton.test_works_in_rtl` — L236–L249

### `tests/test_v160_ui_polish.py`

آزمون‌های زیباسازی نسخهٔ ۱٫۶٫۰.

ارجاع داخلی: `ai/agent/chat_agent.py`, `app/core/constants.py`, `ui/themes/catalog.py`, `ui/themes/stylesheet.py`, `ui/widgets/chrome.py`.
- `class TestRoyalSilkTheme` — L20–L66
- `def TestRoyalSilkTheme.test_theme_exists_and_is_dark` — L23–L29
- `def TestRoyalSilkTheme.test_theme_is_selectable_from_settings` — L31–L38
- `def TestRoyalSilkTheme.test_theme_is_registered_in_the_enum` — L40–L48
- `def TestRoyalSilkTheme.test_accent_differs_from_market_colors` — L50–L60
- `def TestRoyalSilkTheme.test_stylesheet_renders_without_leftover_placeholders` — L62–L66
- `class TestAllThemesRender` — L69–L84
- `def TestAllThemesRender.test_stylesheet_is_complete` — L73–L77
- `def TestAllThemesRender.test_legacy_keys_still_resolve` — L79–L84
- `class TestRoundedCorners` — L87–L158
- `def TestRoundedCorners.test_key_widgets_declare_a_radius` — L107–L116
- `def TestRoundedCorners.test_button_radius_matches_theme_character` — L123–L135
- `def TestRoundedCorners.test_tabs_declare_top_corner_radius` — L138–L144
- `def TestRoundedCorners.test_square_theme_is_square_everywhere` — L146–L158
- `class TestUserChipStates` — L161–L209
- `def TestUserChipStates.test_both_states_are_styled` — L165–L169
- `def TestUserChipStates.test_guest_and_signed_in_look_different` — L171–L182
- `def TestUserChipStates.test_chip_reflects_authentication` — L184–L192
- `def TestUserChipStates.test_inline_padding_does_not_kill_theme_colors` — L194–L209
- `class TestChatInternalLeak` — L212–L260
- `def TestChatInternalLeak.test_app_context_block_is_removed` — L215–L223
- `def TestChatInternalLeak.test_mode_guidance_block_is_removed` — L225–L228
- `def TestChatInternalLeak.test_both_blocks_removed_together` — L230–L242
- `def TestChatInternalLeak.test_code_fences_still_stripped` — L244–L246
- `def TestChatInternalLeak.test_normal_text_is_untouched` — L248–L251
- `def TestChatInternalLeak.test_brackets_in_normal_text_survive` — L253–L260

### `tests/test_v161_omniroute_font_theme.py`

آزمون‌های نسخهٔ ۱٫۶٫۱.

ارجاع داخلی: `ai/providers/base.py`, `ai/providers/catalog.py`, `ai/providers/manager.py`, `ai/providers/omniroute_provider.py`, `ai/tools/__init__.py`, `ai/tools/market_tools.py`, `app/core/constants.py`, `localization/__init__.py`, `ui/pages/settings_page.py`, `ui/themes/catalog.py`, `ui/themes/fonts.py`, `ui/themes/stylesheet.py`, `ui/themes/theme_manager.py`.
- `def _gateway_transport` — L57–L88
- `def _gateway_transport.handler` — L65–L86
- `def _provider` — L91–L103
- `class TestOmniRouteCatalog` — L109–L139
- `def TestOmniRouteCatalog.test_preset_exists` — L112–L117
- `def TestOmniRouteCatalog.test_preset_accepts_an_optional_key` — L119–L130
- `def TestOmniRouteCatalog.test_provider_type_is_wired_into_the_factory` — L132–L134
- `def TestOmniRouteCatalog.test_every_preset_key_is_unique` — L136–L139
- `class TestOmniRouteProvider` — L142–L245
- `def TestOmniRouteProvider.test_empty_base_url_falls_back_to_the_default` — L145–L150
- `async def TestOmniRouteProvider.test_reports_availability` — L153–L161
- `async def TestOmniRouteProvider.test_works_without_a_key_when_the_gateway_is_open` — L164–L171
- `async def TestOmniRouteProvider.test_reports_a_useful_message_when_the_key_is_rejected` — L174–L186
- `async def TestOmniRouteProvider.test_accepts_a_valid_key` — L189–L196
- `async def TestOmniRouteProvider.test_auto_model_is_always_first` — L199–L213
- `async def TestOmniRouteProvider.test_generates_a_reply` — L216–L225
- `async def TestOmniRouteProvider.test_sends_the_application_identity_header` — L228–L234
- `async def TestOmniRouteProvider.test_key_never_appears_in_the_error_message` — L237–L245
- `class TestModelVendor` — L248–L274
- `def TestModelVendor.test_known_prefixes` — L260–L262
- `def TestModelVendor.test_unknown_prefix_is_preserved` — L264–L270
- `def TestModelVendor.test_empty_input` — L272–L274
- `class TestOmniRouteToolset` — L280–L384
- `def TestOmniRouteToolset.test_tool_names` — L283–L285
- `def TestOmniRouteToolset.test_definitions_are_valid_function_schemas` — L287–L293
- `async def TestOmniRouteToolset.test_status_when_the_gateway_is_configured` — L296–L307
- `async def TestOmniRouteToolset.test_status_when_the_gateway_is_not_configured` — L310–L319
- `async def TestOmniRouteToolset.test_status_never_returns_the_api_key` — L322–L332
- `async def TestOmniRouteToolset.test_models_are_grouped_by_vendor` — L335–L345
- `async def TestOmniRouteToolset.test_models_can_be_filtered_by_vendor` — L348–L358
- `async def TestOmniRouteToolset.test_unknown_tool_fails_cleanly` — L361–L365
- `async def TestOmniRouteToolset.test_unreachable_gateway_is_reported_not_raised` — L368–L384
- `def TestOmniRouteToolset.test_unreachable_gateway_is_reported_not_raised.fail` — L371–L372
- `class TestCompositeToolset` — L387–L455
- `class TestCompositeToolset._Stub` — L390–L408
- `def TestCompositeToolset._Stub.__init__` — L393–L395
- `def TestCompositeToolset._Stub.tool_names` — L398–L399
- `def TestCompositeToolset._Stub.get_definitions` — L401–L402
- `async def TestCompositeToolset._Stub.execute` — L404–L405
- `def TestCompositeToolset._Stub.set_risk_parameters` — L407–L408
- `def TestCompositeToolset.test_tool_names_are_merged` — L410–L413
- `def TestCompositeToolset.test_definitions_are_merged_without_duplicates` — L415–L418
- `async def TestCompositeToolset.test_execute_routes_to_the_owning_toolset` — L421–L425
- `async def TestCompositeToolset.test_first_registered_toolset_wins` — L428–L439
- `async def TestCompositeToolset.test_unknown_tool_fails_cleanly` — L442–L445
- `def TestCompositeToolset.test_risk_parameters_reach_every_toolset` — L447–L451
- `def TestCompositeToolset.test_none_toolsets_are_ignored` — L453–L455
- `class TestPersianFont` — L461–L524
- `def TestPersianFont.test_font_files_ship_with_the_application` — L464–L472
- `def TestPersianFont.test_koodak_files_are_real_truetype_fonts` — L474–L478
- `def TestPersianFont.test_default_font_is_vazirmatn` — L480–L488
- `def TestPersianFont.test_koodak_is_still_available_as_a_choice` — L490–L494
- `def TestPersianFont.test_koodak_stack_starts_with_koodak` — L496–L498
- `def TestPersianFont.test_every_stack_ends_with_a_latin_fallback` — L500–L508
- `def TestPersianFont.test_unknown_font_key_falls_back` — L510–L514
- `def TestPersianFont.test_every_choice_has_both_names` — L516–L519
- `def TestPersianFont.test_font_keys_are_unique` — L521–L524
- `class TestFontInStylesheet` — L527–L556
- `def TestFontInStylesheet.test_stylesheet_carries_the_font_family` — L530–L534
- `def TestFontInStylesheet.test_font_is_independent_of_the_theme` — L536–L545
- `def TestFontInStylesheet.test_every_theme_and_font_combination_renders` — L547–L552
- `def TestFontInStylesheet.test_missing_font_argument_uses_the_default` — L554–L556
- `class TestThemeManagerFont` — L559–L586
- `def TestThemeManagerFont.test_default_font_key` — L562–L564
- `def TestThemeManagerFont.test_font_survives_a_theme_change` — L566–L577
- `def TestThemeManagerFont.test_invalid_font_is_rejected_safely` — L579–L582
- `def TestThemeManagerFont.test_available_fonts_are_exposed` — L584–L586
- `class TestOrchidIndigoTheme` — L592–L666
- `def TestOrchidIndigoTheme.test_theme_exists` — L595–L601
- `def TestOrchidIndigoTheme.test_theme_is_registered_in_the_enum` — L603–L610
- `def TestOrchidIndigoTheme.test_theme_is_selectable_by_name` — L612–L614
- `def TestOrchidIndigoTheme.test_primary_differs_from_the_other_dark_themes` — L616–L628
- `def TestOrchidIndigoTheme.test_accent_is_not_confusable_with_market_colours` — L630–L639
- `def TestOrchidIndigoTheme.test_stylesheet_builds_completely` — L641–L645
- `def TestOrchidIndigoTheme.test_rounded_corners_are_preserved` — L647–L655
- `def TestOrchidIndigoTheme.test_theme_has_a_localised_name_in_both_languages` — L657–L666
- `def settings_page` — L673–L692
- `class TestSettingsPageIntegration` — L695–L821
- `def TestSettingsPageIntegration.test_font_picker_lists_every_choice` — L698–L703
- `def TestSettingsPageIntegration.test_choosing_a_font_emits_immediately` — L705–L721
- `def TestSettingsPageIntegration.test_font_choice_is_collected_for_saving` — L723–L729
- `def TestSettingsPageIntegration.test_saved_font_is_restored` — L731–L735
- `def TestSettingsPageIntegration.test_restoring_a_font_does_not_re_emit` — L737–L748
- `def TestSettingsPageIntegration.test_unknown_saved_font_falls_back_safely` — L750–L754
- `def TestSettingsPageIntegration.test_new_theme_appears_in_the_picker` — L756–L760
- `def TestSettingsPageIntegration.test_every_theme_has_a_card` — L762–L765
- `def TestSettingsPageIntegration.test_omniroute_appears_in_the_provider_picker` — L767–L771
- `def TestSettingsPageIntegration.test_selecting_omniroute_fills_the_base_url_and_enables_the_key` — L773–L789
- `def TestSettingsPageIntegration.test_omniroute_suggests_the_auto_model` — L791–L798
- `def TestSettingsPageIntegration.test_omniroute_key_is_collected_as_a_secret` — L800–L809
- `def TestSettingsPageIntegration.test_ollama_still_has_no_key_field` — L811–L821

### `tests/test_v162_chat_streaming.py`

آزمون‌های پاسخ جریانی چت (تایپ تدریجی).

ارجاع داخلی: `ai/agent/chat_agent.py`, `ai/agent/stream_extractor.py`, `ai/providers/base.py`, `ai/providers/manager.py`, `ai/providers/openai_compatible.py`, `app/config/defaults.py`, `app/core/auth_service.py`, `localization/translator.py`, `ui/pages/chat_page.py`.
- `def test_blank_and_comment_lines_are_ignored` — L30–L34
- `def test_done_marker_is_recognised` — L37–L40
- `def test_broken_json_is_skipped_not_raised` — L43–L51
- `def test_content_delta_is_extracted` — L54–L61
- `def test_reasoning_field_is_used_when_content_is_empty` — L64–L68
- `def test_finish_reason_and_usage_are_captured` — L71–L81
- `def test_openai_compatible_advertises_streaming` — L84–L89
- `def _drain` — L95–L101
- `def test_json_answer_is_revealed_progressively` — L104–L113
- `def test_structure_before_answer_is_not_shown` — L116–L119
- `def test_answer_after_another_key_is_found` — L122–L125
- `def test_text_key_is_accepted_as_answer` — L128–L131
- `def test_plain_text_streams_through_untouched` — L134–L137
- `def test_escaped_newline_becomes_a_real_newline` — L140–L143
- `def test_unicode_escape_split_across_chunks` — L146–L154
- `def test_inner_quotes_are_unescaped` — L157–L160
- `def test_code_fence_is_skipped` — L163–L166
- `def test_feed_returns_only_the_delta` — L169–L180
- `def test_reset_clears_everything` — L183–L189
- `def test_empty_chunk_is_harmless` — L192–L195
- `class _FakeStreamProvider : AIProvider` — L201–L236
- `def _FakeStreamProvider.__init__` — L204–L208
- `def _FakeStreamProvider.supports_streaming` — L211–L212
- `async def _FakeStreamProvider.is_available` — L214–L215
- `async def _FakeStreamProvider.list_models` — L217–L218
- `async def _FakeStreamProvider.generate` — L220–L224
- `async def _FakeStreamProvider.stream` — L226–L236
- `def test_base_provider_falls_back_to_generate` — L239–L262
- `class test_base_provider_falls_back_to_generate._NoStream : AIProvider` — L246–L254
- `async def test_base_provider_falls_back_to_generate._NoStream.is_available` — L247–L248
- `async def test_base_provider_falls_back_to_generate._NoStream.list_models` — L250–L251
- `async def test_base_provider_falls_back_to_generate._NoStream.generate` — L253–L254
- `def test_manager_streams_from_the_first_provider` — L265–L274
- `def test_manager_resets_the_view_before_switching_provider` — L277–L301
- `class test_manager_resets_the_view_before_switching_provider._HalfThenFail : _FakeStreamProvider` — L284–L287
- `async def test_manager_resets_the_view_before_switching_provider._HalfThenFail.stream` — L285–L287
- `class _EmptyToolset` — L307–L316
- `def _EmptyToolset.get_definitions` — L312–L313
- `async def _EmptyToolset.execute` — L315–L316
- `def _manager_with` — L319–L332
- `def _agent_with` — L335–L340
- `def test_agent_streams_when_no_tools_are_registered` — L343–L357
- `class _ToolsetWithDefinitions : _EmptyToolset` — L360–L379
- `def _ToolsetWithDefinitions.get_definitions` — L371–L379
- `def test_agent_streams_even_when_tools_are_registered` — L382–L401
- `def test_tool_request_is_not_shown_to_the_user` — L404–L452
- `class test_tool_request_is_not_shown_to_the_user._TwoRound : _FakeStreamProvider` — L413–L430
- `def test_tool_request_is_not_shown_to_the_user._TwoRound.__init__` — L416–L418
- `async def test_tool_request_is_not_shown_to_the_user._TwoRound.stream` — L420–L430
- `class test_tool_request_is_not_shown_to_the_user._RunnableTools : _ToolsetWithDefinitions` — L432–L434
- `async def test_tool_request_is_not_shown_to_the_user._RunnableTools.execute` — L433–L434
- `def test_tool_request_is_not_shown_to_the_user.on_stream` — L441–L443
- `def test_agent_without_callback_uses_plain_generate` — L455–L461
- `def test_streaming_enabled_reflects_the_callback` — L464–L471
- `def test_stream_callback_error_does_not_break_the_reply` — L474–L484
- `def test_stream_callback_error_does_not_break_the_reply.boom` — L479–L480
- `def chat_page` — L491–L496
- `def test_stream_delta_appends_to_the_pending_bubble` — L499–L504
- `def test_stream_delta_with_replace_clears_previous_text` — L507–L514
- `def test_stream_delta_without_a_pending_bubble_is_safe` — L517–L523
- `def test_begin_reply_clears_the_previous_stream` — L526–L532
- `def test_finish_reply_overrides_streamed_text` — L535–L545
- `def test_streaming_setting_defaults_to_on` — L548–L552
- `def test_streaming_setting_is_a_user_preference` — L555–L560

### `tests/test_v162_modal_close.py`

آزمون‌های بسته‌شدن مطمئن مدال‌ها.

ارجاع داخلی: `localization/__init__.py`, `ui/controllers/main_controller.py`, `ui/dialogs/coin_detail_dialog.py`.
- `def translator` — L39–L41
- `def _dialog` — L44–L46
- `def test_guard_accepts_a_live_dialog` — L52–L55
- `def test_guard_rejects_none` — L58–L60
- `def test_guard_detects_a_destroyed_dialog` — L63–L73
- `def test_touching_a_destroyed_dialog_really_raises` — L76–L88
- `def test_guard_prevents_the_crash` — L91–L99
- `def test_every_close_path_works` — L107–L115
- `def test_closing_twice_is_harmless` — L118–L129
- `def test_close_button_is_wired_to_accept` — L132–L136
- `def test_pdf_export_path_is_guarded` — L142–L156
- `def test_coin_details_callbacks_are_guarded` — L159–L171
- `def test_show_coin_details_cancels_its_background_job` — L174–L187

### `tests/test_v162_toobit_websocket.py`

آزمون‌های وب‌سوکت توبیت و انتخاب کلاینت زنده بر پایهٔ صرافی.

ارجاع داخلی: `app/core/constants.py`, `app/core/models.py`, `market/engine.py`, `market/providers/base.py`, `market/providers/bitpin/provider.py`, `market/providers/lbank/provider.py`, `market/providers/lbank/websocket_client.py`, `market/providers/toobit/parser.py`, `market/providers/toobit/provider.py`, `market/providers/toobit/websocket_client.py`.
- `def test_ws_ticker_is_parsed` — L110–L117
- `def test_ws_ticker_converts_fraction_to_percent` — L120–L129
- `def test_ws_ticker_rejects_empty_payload` — L132–L136
- `def test_ws_kline_is_parsed_with_seconds` — L139–L152
- `def test_ws_kline_reads_timeframe_from_params` — L155–L160
- `def test_ws_kline_without_timeframe_is_dropped` — L163–L166
- `def test_ws_kline_with_broken_numbers_is_dropped` — L169–L177
- `def test_subscription_message_matches_protocol` — L183–L192
- `def test_cancel_uses_cancel_event` — L195–L198
- `def test_subscription_is_hashable` — L201–L205
- `class _FakeConnection` — L211–L221
- `def _FakeConnection.__init__` — L214–L215
- `async def _FakeConnection.send` — L217–L218
- `async def _FakeConnection.close` — L220–L221
- `def test_subscriptions_are_queued_before_connection` — L224–L233
- `def test_resubscribe_sends_every_subscription` — L236–L251
- `async def test_resubscribe_sends_every_subscription.scenario` — L240–L246
- `def test_unsubscribe_all_clears_and_cancels` — L254–L267
- `async def test_unsubscribe_all_clears_and_cancels.scenario` — L258–L263
- `def test_unknown_timeframe_falls_back_to_rest` — L270–L278
- `def test_error_frame_does_not_crash_the_client` — L281–L287
- `def test_ticker_frame_reaches_the_callback` — L290–L297
- `def test_kline_frame_reaches_the_callback` — L300–L309
- `def test_callback_error_does_not_break_the_stream` — L312–L321
- `def test_callback_error_does_not_break_the_stream.boom` — L315–L316
- `def test_non_json_frame_is_ignored` — L324–L328
- `def test_client_answers_ping_if_server_ever_sends_one` — L331–L340
- `def test_status_starts_disconnected` — L343–L345
- `def test_keepalive_is_enabled_because_server_is_silent` — L348–L355
- `def test_toobit_builds_its_own_client` — L361–L364
- `def test_lbank_builds_its_own_client` — L367–L370
- `def test_both_clients_satisfy_the_shared_contract` — L373–L381
- `def test_default_provider_has_no_live_client` — L384–L412
- `class test_default_provider_has_no_live_client._Bare : ExchangeProvider` — L391–L410
- `def test_default_provider_has_no_live_client._Bare.capabilities` — L395–L396
- `async def test_default_provider_has_no_live_client._Bare.connect` — L398–L398
- `async def test_default_provider_has_no_live_client._Bare.close` — L399–L399
- `async def test_default_provider_has_no_live_client._Bare.ping` — L400–L401
- `async def test_default_provider_has_no_live_client._Bare.get_symbols` — L403–L403
- `async def test_default_provider_has_no_live_client._Bare.get_ticker` — L404–L404
- `async def test_default_provider_has_no_live_client._Bare.get_all_tickers` — L405–L405
- `async def test_default_provider_has_no_live_client._Bare.get_current_price` — L406–L406
- `async def test_default_provider_has_no_live_client._Bare.get_ohlcv` — L407–L407
- `async def test_default_provider_has_no_live_client._Bare.get_orderbook` — L408–L408
- `def test_default_provider_has_no_live_client._Bare.to_exchange_symbol` — L409–L409
- `def test_default_provider_has_no_live_client._Bare.from_exchange_symbol` — L410–L410
- `def test_bitpin_declares_no_websocket` — L415–L419
- `class _StubClient` — L425–L460
- `def _StubClient.__init__` — L428–L432
- `def _StubClient.status` — L435–L436
- `async def _StubClient.start` — L438–L439
- `async def _StubClient.stop` — L441–L442
- `async def _StubClient.subscribe_ticker` — L444–L445
- `async def _StubClient.unsubscribe_ticker` — L447–L449
- `async def _StubClient.subscribe_candles` — L451–L452
- `async def _StubClient.unsubscribe_candles` — L454–L456
- `async def _StubClient.unsubscribe_all` — L458–L460
- `class _StubProvider : ExchangeProvider` — L463–L491
- `def _StubProvider.__init__` — L468–L470
- `def _StubProvider.capabilities` — L473–L474
- `async def _StubProvider.connect` — L476–L476
- `async def _StubProvider.close` — L477–L477
- `async def _StubProvider.ping` — L478–L479
- `async def _StubProvider.get_symbols` — L481–L481
- `async def _StubProvider.get_ticker` — L482–L482
- `async def _StubProvider.get_all_tickers` — L483–L483
- `async def _StubProvider.get_current_price` — L484–L484
- `async def _StubProvider.get_ohlcv` — L485–L485
- `async def _StubProvider.get_orderbook` — L486–L486
- `def _StubProvider.to_exchange_symbol` — L487–L487
- `def _StubProvider.from_exchange_symbol` — L488–L488
- `def _StubProvider.create_websocket_client` — L490–L491
- `def test_engine_uses_the_client_the_provider_supplies` — L494–L512
- `async def test_engine_uses_the_client_the_provider_supplies.scenario` — L503–L506
- `def test_engine_survives_a_provider_that_lies_about_websocket` — L515–L529
- `async def test_engine_survives_a_provider_that_lies_about_websocket.scenario` — L524–L526
- `def test_engine_skips_websocket_when_disabled` — L532–L542
- `async def test_engine_skips_websocket_when_disabled.scenario` — L537–L539

### `tests/test_v170_scanner_fonts_theme.py`

آزمون‌های نسخهٔ ۱٫۷٫۰.

ارجاع داخلی: `app/config/defaults.py`, `app/core/constants.py`, `app/core/models.py`, `signals/scanner.py`, `ui/signal_grading.py`, `ui/themes/catalog.py`, `ui/themes/fonts.py`, `ui/themes/stylesheet.py`.
- `def _signal` — L36–L46
- `class _Market` — L49–L62
- `def _Market.__init__` — L52–L53
- `async def _Market.get_all_tickers` — L55–L59
- `async def _Market.get_symbols` — L61–L62
- `class _Engine` — L65–L80
- `def _Engine.__init__` — L68–L71
- `async def _Engine.generate` — L73–L80
- `def test_scan_sorts_by_confidence_descending` — L86–L93
- `def test_scan_ranks_candidates_by_turnover_not_volume` — L96–L103
- `def test_scan_survives_a_failing_symbol` — L106–L118
- `def test_scan_excludes_wait_unless_requested` — L121–L129
- `def test_scan_applies_minimum_confidence` — L132–L138
- `def test_scan_reports_progress_for_every_symbol` — L141–L150
- `def test_scan_progress_callback_failure_does_not_break_scan` — L153–L161
- `def test_scan_progress_callback_failure_does_not_break_scan.boom` — L155–L156
- `def test_scan_never_calls_ai` — L164–L177
- `def test_scan_result_helpers` — L180–L188
- `def test_scan_falls_back_when_tickers_unavailable` — L191–L199
- `class test_scan_falls_back_when_tickers_unavailable.Broken : _Market` — L193–L195
- `async def test_scan_falls_back_when_tickers_unavailable.Broken.get_all_tickers` — L194–L195
- `def test_default_scan_limit_is_sane` — L202–L204
- `def test_confidence_grades_match_requested_thresholds` — L223–L229
- `def test_fifty_and_sixty_are_both_green` — L232–L238
- `def test_confidence_grade_tolerates_bad_input` — L241–L244
- `def test_risk_level_uses_worst_factor` — L258–L265
- `def test_risk_colours_follow_requested_scale` — L268–L273
- `def test_wait_direction_has_its_own_colour` — L276–L281
- `def test_wait_rows_are_not_labelled_low_risk` — L284–L291
- `def test_signal_without_risk_data_is_unknown_not_low` — L294–L299
- `def test_signal_risk_level_reads_both_data_shapes` — L302–L308
- `def test_default_font_is_vazirmatn` — L314–L318
- `def test_default_setting_matches_default_font` — L321–L326
- `def test_iransans_and_sahel_are_offered` — L329–L334
- `def test_iransans_is_not_bundled_but_sahel_is` — L337–L349
- `def test_bundled_font_files_exist_on_disk` — L352–L357
- `def test_every_font_stack_ends_with_vazirmatn` — L360–L368
- `def test_user_font_directory_is_documented` — L371–L377
- `def test_font_names_are_translated_in_both_languages` — L380–L391
- `def test_carbon_neon_theme_exists` — L397–L404
- `def test_carbon_neon_is_translated_and_registered` — L407–L420
- `def test_adding_a_theme_does_not_change_the_default` — L423–L433
- `def test_carbon_neon_builds_a_complete_stylesheet` — L436–L445
- `def test_spinbox_arrows_are_styled_per_theme` — L448–L464
- `def test_default_font_is_first_in_the_picker` — L467–L478
- `def test_font_hint_mentions_the_bundled_fonts_and_iransans` — L481–L495

### `tests/test_v170_signals_ui.py`

آزمون‌های رابط کاربری نسخهٔ ۱٫۷٫۰.

ارجاع داخلی: `localization/__init__.py`, `ui/pages/settings_page.py`, `ui/pages/signals_page.py`, `ui/signal_grading.py`, `ui/themes/catalog.py`, `ui/widgets/responsive_grid.py`, `ui/widgets/theme_card.py`.
- `def signals_page` — L22–L26
- `def test_scan_button_exists_and_emits` — L44–L49
- `def test_scan_options_are_read_from_the_page` — L52–L62
- `def test_default_minimum_confidence_matches_the_green_threshold` — L65–L69
- `def test_scanning_state_locks_controls_and_shows_stop` — L72–L86
- `def test_scan_progress_updates_bar_and_status` — L89–L96
- `def test_scan_results_are_displayed_in_given_order` — L99–L110
- `def test_high_confidence_rows_are_green_and_bold` — L113–L121
- `def test_confidence_fifty_five_is_also_green` — L124–L130
- `def test_mid_confidence_is_amber_not_green` — L133–L140
- `def test_risk_column_uses_three_distinct_colours` — L143–L150
- `def test_wait_row_has_its_own_colour` — L153–L162
- `def test_colours_follow_the_active_theme` — L165–L179
- `def test_ai_analysis_button_emits_symbol` — L182–L196
- `def test_history_table_uses_the_same_colour_language` — L199–L206
- `def test_scan_rows_survive_language_change` — L209–L216
- `def test_theme_grid_column_count_is_responsive` — L226–L239
- `def test_theme_grid_never_drops_below_two_columns` — L242–L251
- `def test_theme_grid_keeps_all_items_after_relayout` — L254–L267
- `def test_theme_cards_keep_an_aspect_ratio` — L270–L285
- `def test_theme_cards_have_a_width_cap` — L288–L300
- `def test_settings_theme_grid_holds_every_theme` — L303–L309
- `def test_numeric_inputs_are_centred` — L315–L331
- `def test_font_scale_has_a_slider_and_stays_in_sync` — L334–L353
- `def test_font_scale_sync_does_not_loop_forever` — L356–L369

### `tests/test_v171_chat_tool_steps.py`

آزمون‌های نمایش گام‌به‌گام ابزارها در گفتگو (نسخه ۱٫۷٫۱).

ارجاع داخلی: `ai/agent/chat_agent.py`, `ai/tools/market_tools.py`, `localization/translator.py`, `ui/controllers/main_controller.py`, `ui/pages/chat_page.py`, `ui/themes/catalog.py`, `ui/widgets/tool_trail.py`.
- `def chat_page` — L26–L40
- `def test_a_new_step_starts_in_the_running_state` — L46–L50
- `def test_a_successful_result_switches_the_mark` — L53–L58
- `def test_a_failed_result_is_visually_distinct` — L61–L67
- `def test_arguments_appear_next_to_the_tool_name` — L70–L75
- `def test_the_result_is_hidden_until_the_step_is_clicked` — L78–L86
- `def test_a_step_without_a_result_cannot_be_expanded` — L89–L94
- `def test_a_huge_observation_is_truncated` — L97–L109
- `def test_the_display_name_replaces_the_technical_name` — L112–L117
- `def test_the_trail_is_invisible_until_a_tool_runs` — L123–L127
- `def test_finishing_a_step_updates_the_row_that_started_it` — L130–L137
- `def test_the_same_tool_called_twice_keeps_two_rows` — L140–L152
- `def test_a_result_without_a_start_still_shows_up` — L155–L160
- `def test_clearing_removes_every_row` — L163–L169
- `def test_display_names_reach_steps_added_later` — L172–L177
- `def test_theme_colours_follow_the_active_theme` — L180–L190
- `class _FakeResult` — L197–L202
- `class _RecordingProgress` — L205–L212
- `def _RecordingProgress.__init__` — L208–L209
- `def _RecordingProgress.__call__` — L211–L212
- `def test_the_agent_announces_a_tool_before_running_it` — L215–L231
- `def test_a_legacy_single_argument_callback_still_works` — L234–L244
- `def test_a_broken_progress_callback_never_breaks_the_chat` — L247–L254
- `def test_a_broken_progress_callback_never_breaks_the_chat.explode` — L249–L250
- `def test_the_chat_page_shows_a_running_tool_on_the_pending_bubble` — L260–L269
- `def test_the_chat_page_records_the_tool_result` — L272–L281
- `def test_tool_events_without_a_pending_bubble_are_ignored` — L284–L292
- `def test_the_summary_line_is_dropped_when_live_steps_exist` — L296–L311
- `def test_history_replies_still_use_the_summary_line` — L314–L325
- `def test_persian_tool_names_are_used_on_the_page` — L328–L335
- `def test_every_known_tool_has_a_persian_name` — L338–L353
- `def test_the_tool_name_list_matches_the_real_toolset` — L356–L371
- `def test_the_controller_emits_both_tool_signals` — L377–L392

### `tests/test_v172_signal_ai_and_scan_ui.py`

آزمون‌های رفع سه ایراد گزارش‌شدهٔ کاربر (نسخه ۱٫۷٫۲).

ارجاع داخلی: `app/config/defaults.py`, `app/config/settings_service.py`, `localization/translator.py`, `ui/controllers/main_controller.py`, `ui/pages/signals_page.py`, `ui/themes/__init__.py`, `ui/themes/catalog.py`, `ui/widgets/common.py`.
- `def test_signal_ai_timeout_is_not_shorter_than_the_chat_timeout` — L35–L45
- `def test_signal_ai_timeout_allows_a_local_model_to_warm_up` — L48–L53
- `class _FakeRepository` — L56–L76
- `def _FakeRepository.__init__` — L59–L61
- `def _FakeRepository.ensure_defaults` — L63–L66
- `def _FakeRepository.get_all` — L68–L69
- `def _FakeRepository.get` — L71–L72
- `def _FakeRepository.set` — L74–L76
- `def test_an_existing_install_gets_the_raised_timeout` — L79–L91
- `def test_a_value_the_user_chose_is_never_overwritten` — L94–L107
- `def test_a_raised_value_is_left_alone` — L110–L118
- `def signals_page` — L125–L161
- `def test_the_analyse_button_is_tall_enough_to_read` — L172–L184
- `def test_the_analyse_button_shows_its_full_label` — L187–L193
- `def test_the_analyse_button_emits_its_symbol` — L196–L203
- `def test_the_history_table_button_is_also_tall_enough` — L206–L219
- `def test_the_button_column_helper_sets_both_width_and_row_height` — L222–L243
- `def test_the_helper_ignores_a_column_that_does_not_exist` — L246–L255
- `def test_clicking_a_scanned_symbol_asks_for_details` — L261–L272
- `def test_double_clicking_also_opens_details` — L275–L282
- `def test_clicking_the_button_column_does_not_also_open_details` — L285–L298
- `def test_clicking_an_empty_row_is_harmless` — L301–L308
- `def test_the_controller_connects_the_detail_signal` — L311–L316
- `def test_the_controller_can_open_a_scanned_signal` — L319–L323
- `def test_the_user_is_told_when_the_engine_wrote_the_analysis` — L329–L341
- `def test_a_disabled_ai_is_reported_before_any_work` — L344–L350
- `def test_the_new_messages_are_translated` — L355–L363

### `tests/test_v180_ai_status_card.py`

آزمون کارت وضعیت هوش مصنوعی در نوار کناری.

ارجاع داخلی: `localization/__init__.py`, `ui/controllers/main_controller.py`, `ui/themes/catalog.py`, `ui/themes/stylesheet.py`, `ui/widgets/ai_status_card.py`, `ui/widgets/chrome.py`.
- `def card` — L25–L27
- `def test_refresh_interval_is_three_minutes` — L30–L32
- `def test_controller_timer_uses_the_card_interval` — L35–L39
- `def test_set_status_shows_provider_and_model` — L42–L53
- `def test_unknown_state_for_unexpected_value` — L56–L60
- `def test_disconnected_state_is_recorded` — L63–L67
- `def test_checking_state_is_distinct_from_connected` — L70–L75
- `def test_latin_labels_are_left_to_right` — L78–L83
- `def test_long_model_name_is_shortened_but_kept_in_tooltip` — L86–L92
- `def test_short_model_name_strips_provider_prefix` — L95–L97
- `def test_card_is_clickable` — L100–L124
- `def test_card_is_clickable.press` — L108–L118
- `def test_sidebar_mounts_the_card` — L127–L134
- `def test_card_survives_theme_change` — L137–L145
- `def test_stylesheet_defines_the_card_role` — L148–L158
- `def test_locale_keys_exist_in_both_languages` — L161–L168

### `tests/test_v180_arrangeable_layout.py`

آزمون چیدمان قابل جابه‌جایی صفحات.

ارجاع داخلی: `app/config/defaults.py`, `app/core/auth_service.py`, `localization/__init__.py`, `ui/pages/dashboard_page.py`, `ui/widgets/arrangeable.py`.
- `def container` — L19–L24
- `class TestOrdering` — L27–L90
- `def TestOrdering.test_initial_order_follows_insertion` — L30–L32
- `def TestOrdering.test_move_down_swaps_with_the_next_block` — L34–L38
- `def TestOrdering.test_move_up_swaps_with_the_previous_block` — L40–L44
- `def TestOrdering.test_cannot_move_past_the_edges` — L46–L50
- `def TestOrdering.test_unknown_key_is_ignored` — L52–L54
- `def TestOrdering.test_edge_buttons_are_disabled_at_the_ends` — L56–L62
- `def TestOrdering.test_layout_widget_order_matches_logical_order` — L64–L72
- `def TestOrdering.test_moving_preserves_widget_content` — L74–L90
- `class TestVisibility` — L93–L118
- `def TestVisibility.test_hiding_a_block_hides_its_content` — L96–L103
- `def TestVisibility.test_hidden_block_stays_reachable_in_arrange_mode` — L105–L118
- `class TestPersistence` — L121–L195
- `def TestPersistence.test_serialise_records_order_and_visibility` — L124–L129
- `def TestPersistence.test_apply_state_restores_order_and_visibility` — L131–L141
- `def TestPersistence.test_new_blocks_are_appended_not_lost` — L143–L156
- `def TestPersistence.test_unknown_keys_in_state_are_skipped` — L158–L162
- `def TestPersistence.test_empty_state_leaves_the_default_order` — L164–L168
- `def TestPersistence.test_duplicate_keys_are_collapsed` — L170–L174
- `def TestPersistence.test_changes_emit_a_saveable_string` — L176–L185
- `def TestPersistence.test_reset_restores_defaults` — L187–L195
- `class TestDashboardIntegration` — L198–L283
- `def TestDashboardIntegration.dashboard` — L202–L206
- `def TestDashboardIntegration.test_dashboard_sections_are_arrangeable` — L208–L212
- `def TestDashboardIntegration.test_arrange_bars_hidden_until_requested` — L214–L221
- `def TestDashboardIntegration.test_arrange_button_label_follows_state` — L223–L228
- `def TestDashboardIntegration.test_dashboard_layout_round_trip` — L230–L242
- `def TestDashboardIntegration.test_dashboard_emits_layout_changes` — L244–L251
- `def TestDashboardIntegration.test_reset_layout_restores_default_order` — L253–L260
- `def TestDashboardIntegration.test_layout_preference_key_is_registered` — L262–L268
- `def TestDashboardIntegration.test_locale_keys_exist_for_both_languages` — L270–L283

### `tests/test_v180_custom_themes.py`

آزمون پوسته‌های سفارشی و ویرایشگر زندهٔ ظاهر.

ارجاع داخلی: `localization/__init__.py`, `ui/pages/settings_page.py`, `ui/themes/catalog.py`, `ui/themes/custom.py`, `ui/themes/stylesheet.py`, `ui/widgets/theme_editor.py`.
- `def store` — L31–L36
- `class TestSanitising` — L39–L79
- `def TestSanitising.test_invalid_colour_is_dropped` — L42–L46
- `def TestSanitising.test_valid_colour_formats_pass` — L48–L54
- `def TestSanitising.test_unknown_token_is_ignored` — L56–L60
- `def TestSanitising.test_metric_is_clamped_to_its_range` — L62–L69
- `def TestSanitising.test_non_numeric_metric_is_dropped` — L71–L73
- `def TestSanitising.test_effect_flags_are_coerced_to_bool` — L75–L79
- `class TestBuildTokens` — L82–L142
- `def TestBuildTokens.test_unset_values_come_from_the_base` — L85–L92
- `def TestBuildTokens.test_overrides_win_over_the_base` — L94–L100
- `def TestBuildTokens.test_changing_primary_clears_a_stale_gradient` — L102–L116
- `def TestBuildTokens.test_explicit_gradient_is_respected` — L118–L130
- `def TestBuildTokens.test_generated_stylesheet_is_complete` — L132–L142
- `class TestStore` — L145–L228
- `def TestStore.test_save_registers_the_theme_immediately` — L148–L153
- `def TestStore.test_saved_theme_survives_a_restart` — L155–L165
- `def TestStore.test_duplicate_name_does_not_overwrite` — L167–L173
- `def TestStore.test_saving_with_an_explicit_key_updates_in_place` — L175–L182
- `def TestStore.test_only_differences_are_written` — L184–L194
- `def TestStore.test_corrupt_file_is_skipped_not_fatal` — L196–L206
- `def TestStore.test_delete_removes_theme_and_file` — L208–L214
- `def TestStore.test_builtin_themes_cannot_be_deleted` — L216–L219
- `def TestStore.test_persian_name_produces_a_usable_key` — L221–L224
- `def TestStore.test_missing_directory_is_not_an_error` — L226–L228
- `class TestEditorWidget` — L231–L333
- `def TestEditorWidget.editor` — L235–L241
- `def TestEditorWidget.test_loading_a_theme_emits_nothing` — L243–L254
- `def TestEditorWidget.test_changing_a_metric_records_an_override` — L256–L262
- `def TestEditorWidget.test_returning_to_the_base_value_drops_the_override` — L264–L272
- `def TestEditorWidget.test_reset_clears_every_override` — L274–L281
- `def TestEditorWidget.test_colour_buttons_show_the_theme_colours` — L283–L288
- `def TestEditorWidget.test_editor_labels_are_translated` — L290–L295
- `def TestEditorWidget.test_editor_exists_in_settings_appearance_tab` — L297–L305
- `def TestEditorWidget.test_settings_page_relays_token_changes` — L307–L318
- `def TestEditorWidget.test_refresh_theme_cards_includes_custom_themes` — L320–L333
- `def test_custom_prefix_cannot_collide_with_builtin_themes` — L336–L340

### `tests/test_v180_table_fullscreen.py`

آزمون کنترل تمام‌صفحهٔ جدول‌ها و کارت وضعیت هوش مصنوعی.

ارجاع داخلی: `localization/__init__.py`, `ui/pages/signals_page.py`, `ui/pages/trades_page.py`, `ui/widgets/table_toolbar.py`.
- `def translator` — L39–L41
- `def host` — L45–L52
- `def test_attach_inserts_toolbar_directly_above_table` — L55–L64
- `def test_attach_returns_none_for_table_without_layout` — L67–L71
- `def test_fullscreen_roundtrip_restores_position_and_data` — L74–L95
- `def test_toggle_emits_state_changes` — L98–L108
- `def test_button_label_follows_state` — L111–L124
- `def test_closing_dialog_directly_restores_table` — L127–L137
- `def test_attach_all_skips_already_attached_tables` — L140–L147
- `def test_every_page_table_has_a_toolbar` — L151–L166
- `def test_fullscreen_title_comes_from_enclosing_card` — L169–L177
- `def test_retranslate_updates_toolbar_text` — L180–L189

### `tests/test_v180_tutorial.py`

آزمون آموزش معامله‌گری در صفحهٔ راهنما.

ارجاع داخلی: `localization/__init__.py`, `ui/pages/help_page.py`, `ui/widgets/tutorial_view.py`.
- `def view` — L31–L33
- `def test_tutorial_covers_the_essential_topics` — L36–L41
- `def test_chapters_have_substantial_text` — L44–L47
- `def test_every_chapter_declares_a_known_level` — L50–L53
- `def test_both_languages_have_the_same_chapters` — L56–L61
- `def test_selecting_a_chapter_shows_its_text` — L64–L70
- `def test_navigation_moves_between_chapters` — L73–L83
- `def test_navigation_stops_at_the_edges` — L86–L92
- `def test_search_narrows_the_chapter_list` — L95–L102
- `def test_search_with_no_match_shows_a_message` — L105–L111
- `def test_clearing_search_restores_every_chapter` — L114–L121
- `def test_help_page_exposes_the_tutorial_tab` — L124–L133
- `def test_help_page_keeps_its_original_sections` — L136–L144
- `def test_language_change_reloads_the_tutorial` — L147–L162
- `def test_reload_keeps_the_reader_on_the_same_chapter` — L165–L174

### `tests/test_v190_account_and_auto_scan.py`

آزمون حساب کاربری حرفه‌ای، بازیابی رمز، اولاما و سیگنال‌گیری خودکار.

ارجاع داخلی: `ai/providers/base.py`, `ai/providers/ollama_provider.py`, `app/config/defaults.py`, `app/core/email_service.py`, `app/core/password_reset.py`, `localization/__init__.py`, `signals/auto_scanner.py`.
- `def test_email_validation_accepts_real_addresses` — L56–L61
- `def test_mask_email_hides_the_local_part` — L64–L69
- `def test_every_preset_has_a_translation` — L72–L77
- `def test_gmail_preset_uses_the_submission_port` — L80–L86
- `def test_service_reports_not_configured_instead_of_crashing` — L89–L101
- `class test_service_reports_not_configured_instead_of_crashing.Settings` — L92–L94
- `def test_service_reports_not_configured_instead_of_crashing.Settings.get` — L93–L94
- `def test_config_falls_back_to_username_as_sender` — L104–L111
- `def test_config_without_password_is_not_usable` — L114–L118
- `class FakeUserRepo` — L124–L137
- `def FakeUserRepo.__init__` — L127–L128
- `def FakeUserRepo.find_by_email` — L130–L133
- `def FakeUserRepo.reset_password` — L135–L137
- `class FakeEmail` — L140–L152
- `def FakeEmail.__init__` — L143–L146
- `def FakeEmail.send` — L148–L152
- `def extract_code` — L155–L159
- `def reset_service` — L163–L165
- `def test_generated_code_has_the_expected_shape` — L168–L173
- `def test_happy_path_changes_the_password` — L176–L187
- `def test_code_is_single_use` — L190–L199
- `def test_unknown_email_does_not_reveal_itself` — L202–L212
- `def test_brute_force_burns_the_code` — L215–L226
- `def test_expired_code_is_refused` — L229–L239
- `def test_resend_is_rate_limited` — L242–L250
- `def test_offline_fallback_returns_the_code` — L253–L265
- `def test_failed_delivery_falls_back_instead_of_locking_out` — L268–L275
- `def test_invalid_email_is_rejected_early` — L278–L283
- `def test_reset_keys_are_translated` — L286–L296
- `def test_reset_dialog_texts_are_in_the_right_script` — L299–L308
- `class FakeSignal` — L314–L320
- `def FakeSignal.__init__` — L317–L320
- `def scheduler` — L324–L333
- `def test_interval_is_clamped_to_a_sane_range` — L336–L344
- `def test_disabled_scheduler_never_runs` — L347–L352
- `def test_first_job_is_a_full_sweep` — L355–L360
- `def test_full_sweep_builds_the_focus_list` — L363–L386
- `def test_focus_cycle_runs_on_the_selected_symbols` — L389–L399
- `def test_nothing_is_due_before_the_interval_elapses` — L402–L408
- `def test_full_sweep_wins_over_focus_when_both_are_due` — L411–L424
- `def test_overlapping_cycles_are_skipped_not_queued` — L427–L436
- `def test_focus_list_is_reordered_not_emptied` — L439–L458
- `def test_failure_still_advances_the_clock` — L461–L470
- `def test_countdown_reports_remaining_seconds` — L473–L481
- `def test_shrinking_focus_size_applies_immediately` — L484–L496
- `def test_reset_clears_state` — L499–L508
- `def test_config_reads_every_setting_key` — L511–L535
- `class test_config_reads_every_setting_key.Settings` — L514–L520
- `def test_config_reads_every_setting_key.Settings.__init__` — L515–L516
- `def test_config_reads_every_setting_key.Settings.get` — L518–L520
- `def test_auto_scan_defaults_are_registered` — L538–L551
- `def test_auto_scan_is_off_by_default` — L554–L562
- `def test_auto_scan_locale_keys_match` — L565–L572
- `def test_scheduler_reasons_have_translations` — L575–L580
- `def test_num_ctx_follows_the_prompt_length` — L586–L608
- `def test_memory_errors_are_recognised` — L611–L617
- `def test_error_body_is_extracted_from_json_and_text` — L620–L637
- `class test_error_body_is_extracted_from_json_and_text.JsonResponse` — L624–L628
- `def test_error_body_is_extracted_from_json_and_text.JsonResponse.json` — L627–L628
- `class test_error_body_is_extracted_from_json_and_text.TextResponse` — L630–L634
- `def test_error_body_is_extracted_from_json_and_text.TextResponse.json` — L633–L634
- `def test_http_error_message_names_the_real_cause` — L640–L658
- `class test_http_error_message_names_the_real_cause.Response` — L647–L652
- `def test_http_error_message_names_the_real_cause.Response.json` — L651–L652

### `tests/test_v190_position_sizing.py`

آزمون ماشین‌حساب حجم پوزیشن (مورد ۲.۱ نقشهٔ راه).

ارجاع داخلی: `localization/__init__.py`, `signals/__init__.py`, `signals/position_sizing.py`, `ui/dialogs/signal_detail_dialog.py`, `ui/widgets/position_calculator.py`.
- `def test_worked_example_matches_the_tutorial` — L35–L61
- `def test_direction_is_inferred_from_stop_placement` — L64–L74
- `def test_short_position_profits_when_price_falls` — L77–L89
- `def test_target_on_the_wrong_side_yields_no_reward` — L92–L103
- `def test_risk_amount_is_independent_of_leverage` — L106–L121
- `def test_liquidation_price_moves_against_the_position` — L124–L134
- `def test_spot_position_has_no_liquidation_price` — L137–L143
- `def test_stop_beyond_liquidation_is_warned` — L146–L158
- `def test_margin_exceeding_capital_is_warned` — L161–L172
- `def test_safe_plan_has_no_warnings` — L175–L186
- `def test_invalid_input_returns_error_instead_of_raising` — L189–L201
- `def test_leverage_is_clamped_to_the_exchange_maximum` — L204–L214
- `def test_fee_scales_with_notional_and_counts_both_sides` — L217–L229
- `def test_required_win_rate_matches_the_textbook_values` — L232–L239
- `def test_breakeven_price_accounts_for_fees` — L242–L249
- `def calculator` — L256–L260
- `def test_widget_recalculates_without_a_button` — L263–L274
- `def test_widget_emits_plan_changed` — L277–L286
- `def test_load_signal_keeps_the_user_capital` — L289–L313
- `def test_warnings_are_shown_as_translated_text` — L316–L327
- `def test_warnings_hidden_for_a_safe_plan` — L330–L339
- `def test_quantity_is_shown_in_latin_digits` — L342–L354
- `def test_price_input_hides_trailing_zeros` — L357–L361
- `def test_price_input_keeps_small_coin_precision` — L364–L369
- `def test_invalid_state_shows_a_message_not_a_crash` — L372–L379
- `def test_retranslate_switches_language` — L382–L392
- `def _load` — L398–L399
- `def test_sizing_locale_keys_match_across_languages` — L402–L404
- `def test_sizing_texts_are_in_the_right_script` — L407–L412
- `def test_every_warning_and_error_key_has_a_translation` — L415–L428
- `def test_calculator_rows_have_labels_in_both_languages` — L431–L438
- `def detail_dialog` — L445–L462
- `def test_dialog_embeds_a_prefilled_calculator` — L465–L477
- `def test_dialog_shows_the_entry_price` — L480–L490
- `def test_dialog_prices_have_no_padding_zeros` — L493–L500
- `def test_set_account_balance_overrides_the_default_capital` — L503–L510
- `def test_zero_balance_does_not_wipe_the_calculator` — L513–L523
- `def test_controller_primes_the_calculator_from_settings` — L526–L538

### `tests/test_v1910_ollama_doctor.py`

آزمون‌های عیب‌یاب اولاما و نجات از مرگ اجراکننده (نسخهٔ ۱٫۹٫۱۰).

ارجاع داخلی: `ai/ollama_doctor.py`, `ai/prompt_budget.py`.
- `class TestTheVerdictMatchesTheEvidence` — L18–L79
- `def TestTheVerdictMatchesTheEvidence.test_an_unreachable_service_is_reported_as_offline` — L21–L25
- `def TestTheVerdictMatchesTheEvidence.test_no_models_is_its_own_diagnosis` — L27–L31
- `def TestTheVerdictMatchesTheEvidence.test_failing_the_lightest_step_blames_ollama_not_the_app` — L33–L46
- `def TestTheVerdictMatchesTheEvidence.test_failing_only_under_load_is_a_capacity_problem` — L48–L66
- `def TestTheVerdictMatchesTheEvidence.test_all_steps_passing_means_look_elsewhere` — L68–L79
- `class TestCpuOffloadDetection` — L82–L108
- `def TestCpuOffloadDetection.test_a_split_model_is_detected` — L90–L96
- `def TestCpuOffloadDetection.test_a_fully_resident_model_is_not_flagged` — L98–L104
- `def TestCpuOffloadDetection.test_nothing_loaded_is_not_a_warning` — L106–L108
- `class TestTheStepsMirrorTheRealApp` — L111–L139
- `def TestTheStepsMirrorTheRealApp.test_the_steps_grow_from_light_to_heavy` — L114–L127
- `def TestTheStepsMirrorTheRealApp.test_the_system_step_matches_the_real_prompt_size` — L129–L139
- `class TestTheDoctorNeverRaises` — L142–L158
- `async def TestTheDoctorNeverRaises.test_an_unreachable_host_returns_a_report_not_an_error` — L151–L158
- `class TestEveryDoctorStringIsTranslated` — L161–L203
- `def TestEveryDoctorStringIsTranslated.test_both_languages_define_the_same_keys` — L164–L173
- `def TestEveryDoctorStringIsTranslated.test_every_verdict_key_has_a_translation` — L175–L190
- `def TestEveryDoctorStringIsTranslated.test_every_step_has_a_label` — L192–L203

### `tests/test_v1911_ai_signal_mode.py`

آزمون‌های حالت «کاملاً هوش مصنوعی» و سرعت سیگنال‌گیری دستی (۱٫۹٫۱۱).

ارجاع داخلی: `ai/agent/analyst.py`, `app/application.py`, `app/core/constants.py`, `app/core/models.py`.
- `def _decision` — L29–L47
- `def _engine_wait` — L50–L57
- `def _settings` — L60–L91
- `class _settings.Settings` — L79–L89
- `def _settings.Settings.get` — L80–L86
- `def _settings.Settings.get_int` — L88–L89
- `def _app` — L94–L104
- `class _app.Analyst` — L98–L100
- `async def _app.Analyst.generate_signal` — L99–L100
- `class TestTheAiDecisionActuallyReachesTheUser` — L107–L167
- `def TestTheAiDecisionActuallyReachesTheUser.test_a_long_from_the_ai_overrides_the_engine_wait` — L110–L121
- `def TestTheAiDecisionActuallyReachesTheUser.test_every_price_level_is_carried_over` — L123–L132
- `def TestTheAiDecisionActuallyReachesTheUser.test_confidence_and_leverage_come_from_the_ai` — L134–L141
- `def TestTheAiDecisionActuallyReachesTheUser.test_the_model_is_recorded_for_traceability` — L143–L150
- `def TestTheAiDecisionActuallyReachesTheUser.test_trend_and_structure_are_mapped` — L152–L159
- `def TestTheAiDecisionActuallyReachesTheUser.test_a_short_is_honoured_too` — L161–L167
- `class TestTheEngineResultSurvivesBadAiOutput` — L170–L221
- `def TestTheEngineResultSurvivesBadAiOutput.test_a_missing_direction_keeps_the_engine_signal` — L177–L185
- `def TestTheEngineResultSurvivesBadAiOutput.test_an_invalid_direction_is_refused` — L187–L193
- `def TestTheEngineResultSurvivesBadAiOutput.test_a_none_decision_is_safe` — L195–L201
- `def TestTheEngineResultSurvivesBadAiOutput.test_a_wait_from_the_ai_is_respected` — L203–L213
- `def TestTheEngineResultSurvivesBadAiOutput.test_garbage_numbers_do_not_crash_the_mapping` — L215–L221
- `class TestZeroConfidenceIsARealValue` — L224–L246
- `def TestZeroConfidenceIsARealValue.test_zero_confidence_is_not_silently_dropped` — L232–L238
- `def TestZeroConfidenceIsARealValue.test_confidence_is_clamped_to_a_sane_range` — L240–L246
- `class TestManualSignalSpeed` — L249–L273
- `def TestManualSignalSpeed.test_a_slow_model_does_not_block_forever` — L257–L273
- `class TestManualSignalSpeed.test_a_slow_model_does_not_block_forever.SlowAnalyst` — L261–L264
- `async def TestManualSignalSpeed.test_a_slow_model_does_not_block_forever.SlowAnalyst.generate_signal` — L262–L264
- `async def _timed` — L276–L282
- `def test_all_valid_directions_round_trip` — L286–L292

### `tests/test_v1911_build_and_update.py`

آزمون‌های ربات ساخت فایل نصبی و ربات به‌روزرسانی (۱٫۹٫۱۱).

ارجاع داخلی: `app/core/constants.py`, `app/core/updater.py`, `tools/build_installer.py`.
- `class TestVersionComparison` — L30–L59
- `def TestVersionComparison.test_two_digit_patch_beats_single_digit` — L39–L41
- `def TestVersionComparison.test_the_naive_string_compare_would_be_wrong` — L43–L46
- `def TestVersionComparison.test_an_equal_version_is_not_newer` — L48–L50
- `def TestVersionComparison.test_a_major_bump_wins` — L52–L54
- `def TestVersionComparison.test_garbage_does_not_crash` — L56–L59
- `class TestManifestParsing` — L62–L91
- `def TestManifestParsing.test_a_complete_manifest_is_read` — L65–L78
- `def TestManifestParsing.test_a_manifest_without_installer_is_unusable` — L80–L82
- `def TestManifestParsing.test_malformed_payloads_are_survived` — L85–L87
- `def TestManifestParsing.test_a_bad_size_does_not_crash` — L89–L91
- `class TestChecksumVerification` — L94–L122
- `def TestChecksumVerification.test_a_matching_checksum_passes` — L97–L103
- `def TestChecksumVerification.test_a_wrong_checksum_is_rejected` — L105–L110
- `def TestChecksumVerification.test_a_missing_checksum_is_allowed_but_noted` — L112–L122
- `class TestTheTwoRobotsWorkTogether` — L125–L177
- `def TestTheTwoRobotsWorkTogether.test_the_build_manifest_is_readable_by_the_updater` — L131–L141
- `def TestTheTwoRobotsWorkTogether.test_a_full_local_update_round_trip` — L143–L158
- `def TestTheTwoRobotsWorkTogether.test_a_corrupt_download_is_refused` — L160–L177
- `class TestTheUpdaterIsSafeWhenIdle` — L180–L201
- `def TestTheUpdaterIsSafeWhenIdle.test_an_empty_source_checks_nothing` — L183–L185
- `def TestTheUpdaterIsSafeWhenIdle.test_a_missing_folder_is_survived` — L187–L189
- `def TestTheUpdaterIsSafeWhenIdle.test_an_older_remote_version_is_ignored` — L191–L197
- `def TestTheUpdaterIsSafeWhenIdle.test_launching_a_missing_installer_fails_safely` — L199–L201
- `class TestTheBuildRobot` — L204–L241
- `def TestTheBuildRobot.test_the_version_comes_from_constants` — L207–L211
- `def TestTheBuildRobot.test_a_missing_iscc_is_reported_not_crashed` — L213–L220
- `def TestTheBuildRobot.test_the_manifest_records_a_real_checksum` — L222–L230
- `def TestTheBuildRobot.test_a_manifest_without_an_installer_still_records_the_version` — L232–L241
- `class TestTheInstallerScriptProtectsUserData` — L244–L276
- `def TestTheInstallerScriptProtectsUserData._script` — L252–L255
- `def TestTheInstallerScriptProtectsUserData.test_the_installer_script_exists` — L257–L259
- `def TestTheInstallerScriptProtectsUserData.test_the_database_is_never_deleted_on_uninstall` — L261–L265
- `def TestTheInstallerScriptProtectsUserData.test_shortcuts_are_created` — L267–L272
- `def TestTheInstallerScriptProtectsUserData.test_the_version_is_injected_not_hardcoded` — L274–L276
- `class TestTheBatchFilesSurviveWindows` — L278–L346
- `def TestTheBatchFilesSurviveWindows._bat` — L287–L290
- `def TestTheBatchFilesSurviveWindows.test_the_window_never_closes_silently` — L293–L299
- `def TestTheBatchFilesSurviveWindows.test_line_endings_are_windows_style` — L302–L310
- `def TestTheBatchFilesSurviveWindows.test_persian_text_has_a_code_page` — L313–L318
- `def TestTheBatchFilesSurviveWindows.test_a_half_built_venv_is_detected` — L320–L337
- `def TestTheBatchFilesSurviveWindows.test_the_store_python_stub_is_avoided` — L339–L346
- `class TestIsccDiscovery` — L349–L376
- `def TestIsccDiscovery.test_the_registry_is_consulted_on_windows` — L352–L359
- `def TestIsccDiscovery.test_registry_lookup_is_harmless_off_windows` — L361–L365
- `def TestIsccDiscovery.test_a_silent_iscc_success_without_output_is_caught` — L367–L376

### `tests/test_v1912_mobile.py`

آزمون‌های نسخهٔ موبایل (۱٫۹٫۱۲).

ارجاع داخلی: `mobile/app/__init__.py`, `mobile/app/indicators_lite.py`, `mobile/app/signal_lite.py`, `tools/build_apk.py`.
- `def candles` — L30–L40
- `def assert_matches` — L43–L55
- `class TestMathMatchesDesktop` — L58–L145
- `def TestMathMatchesDesktop.test_ema_matches` — L61–L66
- `def TestMathMatchesDesktop.test_sma_matches` — L68–L73
- `def TestMathMatchesDesktop.test_rsi_matches_wilder_smoothing` — L75–L93
- `def TestMathMatchesDesktop.test_macd_line_matches` — L95–L102
- `def TestMathMatchesDesktop.test_macd_signal_matches` — L104–L112
- `def TestMathMatchesDesktop.test_atr_matches` — L114–L129
- `def TestMathMatchesDesktop.test_bollinger_uses_population_deviation` — L131–L145
- `class TestIndicatorEdges` — L148–L183
- `def TestIndicatorEdges.test_empty_input_does_not_crash` — L151–L154
- `def TestIndicatorEdges.test_a_flat_market_gives_neutral_rsi` — L156–L164
- `def TestIndicatorEdges.test_a_flat_market_gives_mid_stochastic` — L166–L170
- `def TestIndicatorEdges.test_warmup_period_is_respected` — L172–L178
- `def TestIndicatorEdges.test_a_zero_period_is_rejected` — L180–L183
- `class TestMobileSignalEngine` — L186–L291
- `def TestMobileSignalEngine.test_insufficient_data_returns_wait` — L189–L200
- `def TestMobileSignalEngine.test_wait_is_a_first_class_result` — L202–L207
- `def TestMobileSignalEngine.test_a_tradeable_signal_has_a_complete_plan` — L209–L223
- `def TestMobileSignalEngine.test_stop_loss_sits_on_the_correct_side` — L225–L235
- `def TestMobileSignalEngine.test_every_signal_states_its_timeframe` — L237–L241
- `def TestMobileSignalEngine.test_validity_scales_with_timeframe` — L243–L250
- `def TestMobileSignalEngine.test_confidence_stays_in_range` — L252–L257
- `def TestMobileSignalEngine.test_risk_reward_is_computed` — L259–L272
- `def TestMobileSignalEngine.test_risk_reward_survives_a_zero_risk` — L274–L287
- `def TestMobileSignalEngine.test_minimum_candles_matches_desktop_contract` — L289–L291
- `class TestMobileStaysLightweight` — L294–L366
- `def TestMobileStaysLightweight._source` — L304–L309
- `def TestMobileStaysLightweight.test_no_heavy_imports` — L314–L319
- `def TestMobileStaysLightweight.test_market_layer_uses_only_the_standard_library` — L321–L330
- `def TestMobileStaysLightweight.test_the_engine_has_no_qt_dependency` — L332–L335
- `def TestMobileStaysLightweight.test_buildozer_does_not_request_pandas` — L337–L354
- `def TestMobileStaysLightweight.test_only_internet_permission_is_requested` — L356–L366
- `class TestTheApkRobot` — L369–L428
- `def TestTheApkRobot.test_windows_paths_are_translated_for_wsl` — L372–L386
- `def TestTheApkRobot.test_the_robot_reports_a_missing_wsl_clearly` — L388–L406
- `def TestTheApkRobot.test_a_failed_environment_stops_the_build` — L408–L421
- `def TestTheApkRobot.test_the_mobile_entry_point_exists` — L423–L428

### `tests/test_v1913_ashna.py`

آزمون‌های ارائه‌دهندهٔ «آشنا» (AshnaAI) — نسخهٔ ۱٫۹٫۱۳.

ارجاع داخلی: `ai/providers/base.py`, `ai/providers/catalog.py`, `ai/providers/openai_compatible.py`, `localization/translator.py`, `tools/build_doctor.py`, `ui/pages/settings_page.py`.
- `def ashna` — L21–L25
- `class TestAshnaIsRegistered` — L28–L83
- `def TestAshnaIsRegistered.test_the_provider_exists` — L31–L33
- `def TestAshnaIsRegistered.test_the_base_url_includes_the_api_segment` — L35–L44
- `def TestAshnaIsRegistered.test_the_base_url_has_no_trailing_slash` — L46–L48
- `def TestAshnaIsRegistered.test_it_reuses_the_openai_compatible_transport` — L50–L55
- `def TestAshnaIsRegistered.test_an_api_key_is_required_and_typeable` — L57–L60
- `def TestAshnaIsRegistered.test_it_is_not_marked_local` — L62–L64
- `def TestAshnaIsRegistered.test_the_signup_url_points_at_the_key_page` — L66–L68
- `def TestAshnaIsRegistered.test_model_listing_is_supported` — L70–L72
- `def TestAshnaIsRegistered.test_the_persian_display_name_is_used` — L74–L76
- `def TestAshnaIsRegistered.test_the_key_is_unique_in_the_catalog` — L78–L83
- `class TestAshnaSuggestedModels` — L86–L134
- `def TestAshnaSuggestedModels.test_the_house_model_is_offered` — L89–L91
- `def TestAshnaSuggestedModels.test_several_families_are_represented` — L93–L102
- `def TestAshnaSuggestedModels.test_every_suggested_id_is_a_documented_catalog_id` — L117–L126
- `def TestAshnaSuggestedModels.test_no_vendor_prefix_is_used` — L128–L134
- `class TestAshnaTransport` — L137–L183
- `def TestAshnaTransport._provider` — L141–L148
- `def TestAshnaTransport.test_a_missing_key_fails_before_any_request` — L150–L163
- `def TestAshnaTransport.test_the_provider_accepts_an_agent_id_as_model` — L165–L183
- `class TestAshnaAppearsInTheSettingsUI` — L186–L207
- `def TestAshnaAppearsInTheSettingsUI.test_the_provider_is_selectable_and_autofills` — L193–L207
- `class TestTheBuildDoctor` — L210–L290
- `def TestTheBuildDoctor._report` — L219–L222
- `def TestTheBuildDoctor.test_the_diagnosis_runs_anywhere` — L224–L228
- `def TestTheBuildDoctor.test_every_failure_offers_a_concrete_fix` — L230–L240
- `def TestTheBuildDoctor.test_the_first_problem_is_surfaced` — L242–L253
- `def TestTheBuildDoctor.test_python_version_is_checked` — L255–L259
- `def TestTheBuildDoctor.test_the_batch_files_are_inspected` — L261–L269
- `def TestTheBuildDoctor.test_a_healthy_tree_reports_the_scripts_as_sound` — L271–L278
- `def TestTheBuildDoctor.test_the_doctor_script_exists_and_is_windows_safe` — L280–L290

### `tests/test_v1914_scalp.py`

آزمون‌های اسکلپ و معاملهٔ خودکار (۱٫۹٫۱۴).

ارجاع داخلی: `app/core/models.py`, `trading/auto_trader.py`, `trading/scalp_scanner.py`, `trading/scalp_service.py`.
- `def make_ticker` — L47–L55
- `def make_candles` — L58–L73
- `def make_book` — L76–L83
- `class TestLiquidityIsTheHardFilter` — L86–L135
- `def TestLiquidityIsTheHardFilter.test_a_high_volatility_ghost_coin_is_rejected` — L96–L100
- `def TestLiquidityIsTheHardFilter.test_a_four_dollar_market_is_rejected` — L102–L104
- `def TestLiquidityIsTheHardFilter.test_a_liquid_pair_passes` — L106–L108
- `def TestLiquidityIsTheHardFilter.test_prefilter_removes_the_traps_before_any_candle_fetch` — L110–L124
- `def TestLiquidityIsTheHardFilter.test_non_quote_pairs_are_excluded` — L126–L135
- `class TestSpreadComesFromTheOrderBook` — L138–L181
- `def TestSpreadComesFromTheOrderBook.test_a_tight_book_gives_a_tiny_spread` — L146–L150
- `def TestSpreadComesFromTheOrderBook.test_a_wide_book_is_detected` — L152–L160
- `def TestSpreadComesFromTheOrderBook.test_an_empty_book_is_treated_as_worst_case` — L162–L169
- `def TestSpreadComesFromTheOrderBook.test_a_malformed_book_does_not_crash` — L171–L173
- `def TestSpreadComesFromTheOrderBook.test_a_wide_spread_blocks_the_candidate` — L175–L181
- `class TestScoringHonesty` — L184–L251
- `def TestScoringHonesty.test_a_calm_market_produces_nothing` — L187–L195
- `def TestScoringHonesty.test_a_chaotic_market_is_rejected` — L197–L201
- `def TestScoringHonesty.test_fees_and_spread_are_subtracted_from_the_profit` — L203–L218
- `def TestScoringHonesty.test_a_candidate_that_cannot_beat_fees_is_dropped` — L220–L224
- `def TestScoringHonesty.test_direction_follows_momentum` — L226–L236
- `def TestScoringHonesty.test_ranking_puts_the_best_first` — L238–L246
- `def TestScoringHonesty.test_volatility_of_empty_candles_is_zero` — L248–L251
- `class TestTheHonestyCheck` — L254–L296
- `def TestTheHonestyCheck.test_twenty_percent_without_leverage_is_called_unrealistic` — L262–L267
- `def TestTheHonestyCheck.test_the_same_goal_becomes_reachable_with_leverage` — L269–L273
- `def TestTheHonestyCheck.test_the_message_names_the_required_move` — L275–L283
- `def TestTheHonestyCheck.test_zero_margin_is_handled` — L285–L289
- `def TestTheHonestyCheck.test_required_move_includes_fees` — L291–L296
- `class TestLiveTradingIsHardToTurnOn` — L299–L353
- `def TestLiveTradingIsHardToTurnOn.test_the_default_is_paper` — L307–L309
- `def TestLiveTradingIsHardToTurnOn.test_live_mode_alone_is_not_enough` — L311–L317
- `def TestLiveTradingIsHardToTurnOn.test_a_wrong_confirmation_phrase_is_rejected` — L319–L322
- `def TestLiveTradingIsHardToTurnOn.test_the_exact_phrase_enables_live` — L324–L328
- `def TestLiveTradingIsHardToTurnOn.test_starting_live_without_confirmation_fails_with_a_clear_message` — L330–L341
- `def TestLiveTradingIsHardToTurnOn.test_the_live_gateway_refuses_instead_of_pretending` — L343–L353
- `class TestHardCaps` — L356–L383
- `def TestHardCaps.test_leverage_is_capped` — L359–L361
- `def TestHardCaps.test_concurrency_is_capped` — L363–L367
- `def TestHardCaps.test_leverage_never_drops_below_one` — L369–L371
- `def TestHardCaps.test_a_reckless_target_is_refused_at_preflight` — L373–L383
- `class TestTradeLifecycle` — L386–L497
- `def TestTradeLifecycle.test_a_trade_closes_at_the_profit_target` — L389–L400
- `def TestTradeLifecycle.test_a_trade_closes_at_the_stop_loss` — L402–L411
- `def TestTradeLifecycle.test_the_stop_loss_wins_when_both_levels_are_crossed` — L413–L424
- `def TestTradeLifecycle.test_a_stale_trade_times_out` — L426–L434
- `def TestTradeLifecycle.test_a_short_profits_when_price_falls` — L436–L445
- `def TestTradeLifecycle.test_concurrency_limit_is_respected` — L447–L453
- `def TestTradeLifecycle.test_the_daily_loss_limit_halts_the_engine` — L455–L468
- `def TestTradeLifecycle.test_stopping_does_not_force_close_open_trades` — L470–L480
- `def TestTradeLifecycle.test_close_all_closes_everything` — L482–L490
- `def TestTradeLifecycle.test_a_listener_error_does_not_break_trading` — L492–L497
- `class _Candidate` — L504–L509
- `class _FakeRepo` — L512–L532
- `def _FakeRepo.__init__` — L515–L517
- `def _FakeRepo.open_trade` — L519–L525
- `def _FakeRepo.close_trade` — L527–L532
- `def _fixed_price` — L535–L539
- `async def _fixed_price._get` — L536–L537
- `def _trader` — L542–L554
- `async def _trader.price_source` — L546–L547
- `class TestScalpServiceAiReview` — L557–L654
- `def TestScalpServiceAiReview._service` — L566–L586
- `class TestScalpServiceAiReview._service._Response` — L569–L570
- `class TestScalpServiceAiReview._service._Provider` — L572–L576
- `async def TestScalpServiceAiReview._service._Provider.generate` — L573–L576
- `class TestScalpServiceAiReview._service._App` — L578–L584
- `class TestScalpServiceAiReview._service._App.settings` — L579–L582
- `def TestScalpServiceAiReview._service._App.settings.get` — L581–L582
- `def TestScalpServiceAiReview._candidates` — L589–L593
- `def TestScalpServiceAiReview.test_a_missing_model_leaves_the_ranking_untouched` — L595–L600
- `def TestScalpServiceAiReview.test_a_broken_model_does_not_break_the_scan` — L602–L611
- `def TestScalpServiceAiReview.test_a_skip_verdict_demotes_but_does_not_delete` — L613–L626
- `def TestScalpServiceAiReview.test_the_ai_reason_is_shown_to_the_user` — L628–L637
- `def TestScalpServiceAiReview.test_json_wrapped_in_prose_is_still_parsed` — L639–L647
- `def TestScalpServiceAiReview.test_malformed_ai_output_is_ignored_safely` — L650–L654

### `tests/test_v1915_bugfixes.py`

آزمون‌های نسخه ۱.۹.۱۵ — سه ایرادی که کاربر روی صرافی LBank گزارش کرد.

ارجاع داخلی: `ai/agent/autonomous_agent.py`, `market/providers/lbank/constants.py`, `market/providers/lbank/provider.py`, `ui/controllers/main_controller.py`.
- `def _outcome` — L23–L28
- `class TestFailedAgentIsNotASignal` — L31–L125
- `def TestFailedAgentIsNotASignal.test_agent_failure_is_rejected` — L40–L47
- `def TestFailedAgentIsNotASignal.test_provider_failure_is_rejected` — L49–L56
- `def TestFailedAgentIsNotASignal.test_a_real_wait_is_still_a_valid_answer` — L58–L74
- `def TestFailedAgentIsNotASignal.test_a_real_trade_is_usable` — L76–L82
- `def TestFailedAgentIsNotASignal.test_numbers_without_success_still_count` — L84–L99
- `def TestFailedAgentIsNotASignal.test_none_outcome_is_rejected` — L101–L103
- `def TestFailedAgentIsNotASignal.test_controller_has_an_engine_fallback` — L105–L113
- `def TestFailedAgentIsNotASignal.test_ai_path_receives_the_selected_timeframes` — L115–L125
- `class TestTheFallbackMessageExists` — L128–L140
- `def TestTheFallbackMessageExists.test_key_is_translated` — L132–L140
- `class TestTradeButtonReachesTheDatabase` — L143–L171
- `def TestTradeButtonReachesTheDatabase.test_handler_writes_to_the_repository` — L151–L158
- `def TestTradeButtonReachesTheDatabase.test_the_agreed_entry_price_is_passed_on` — L160–L171
- `class TestLbankFuturesBalance` — L174–L291
- `def TestLbankFuturesBalance.test_asset_parameter_is_sent` — L183–L209
- `class TestLbankFuturesBalance.test_asset_parameter_is_sent._Client` — L189–L194
- `async def TestLbankFuturesBalance.test_asset_parameter_is_sent._Client.post_contract_signed` — L192–L194
- `def TestLbankFuturesBalance.test_a_single_failing_asset_does_not_hide_the_rest` — L211–L233
- `class TestLbankFuturesBalance.test_a_single_failing_asset_does_not_hide_the_rest._Client` — L219–L225
- `async def TestLbankFuturesBalance.test_a_single_failing_asset_does_not_hide_the_rest._Client.post_contract_signed` — L222–L225
- `def TestLbankFuturesBalance.test_total_failure_still_raises_for_the_connection_test` — L235–L255
- `class TestLbankFuturesBalance.test_total_failure_still_raises_for_the_connection_test._Client` — L243–L247
- `async def TestLbankFuturesBalance.test_total_failure_still_raises_for_the_connection_test._Client.post_contract_signed` — L246–L247
- `def TestLbankFuturesBalance.test_sync_still_survives_a_missing_futures_wallet` — L257–L271
- `class TestLbankFuturesBalance.test_sync_still_survives_a_missing_futures_wallet._Client` — L260–L264
- `async def TestLbankFuturesBalance.test_sync_still_survives_a_missing_futures_wallet._Client.post_contract_signed` — L263–L264
- `def TestLbankFuturesBalance.test_unnamed_row_uses_the_requested_asset` — L273–L284
- `def TestLbankFuturesBalance.test_named_row_wins_over_the_default` — L286–L291

### `tests/test_v1916_ai_wait.py`

آزمون‌های نسخه ۱.۹.۱۶ — «انتظار با اطمینان صفر» در مسیر هوش مصنوعی.

ارجاع داخلی: `ai/agent/autonomous_agent.py`, `ui/controllers/main_controller.py`.
- `def _outcome` — L25–L30
- `class TestAHollowWaitIsNotAnAnalysis` — L33–L82
- `def TestAHollowWaitIsNotAnAnalysis.test_successful_but_empty_wait_is_rejected` — L40–L50
- `def TestAHollowWaitIsNotAnAnalysis.test_wait_with_real_confidence_is_kept` — L52–L67
- `def TestAHollowWaitIsNotAnAnalysis.test_non_positive_confidence_is_rejected` — L70–L75
- `def TestAHollowWaitIsNotAnAnalysis.test_a_directional_trade_at_zero_is_still_rejected` — L77–L82
- `class TestTheAgentStartsFromTheEngineResult` — L85–L152
- `def TestTheAgentStartsFromTheEngineResult.test_baseline_is_rendered_for_the_model` — L93–L111
- `def TestTheAgentStartsFromTheEngineResult.test_enum_values_are_flattened` — L113–L128
- `class TestTheAgentStartsFromTheEngineResult.test_enum_values_are_flattened._Trend` — L120–L121
- `def TestTheAgentStartsFromTheEngineResult.test_missing_baseline_is_explained_not_blank` — L130–L133
- `def TestTheAgentStartsFromTheEngineResult.test_run_accepts_a_baseline` — L135–L139
- `def TestTheAgentStartsFromTheEngineResult.test_prompt_reserves_a_place_for_the_baseline` — L141–L146
- `def TestTheAgentStartsFromTheEngineResult.test_prompt_forbids_a_lazy_zero_confidence` — L148–L152
- `class TestTheUiComputesTheEngineFirst` — L155–L182
- `def TestTheUiComputesTheEngineFirst.test_controller_passes_a_baseline_to_the_agent` — L158–L163
- `def TestTheUiComputesTheEngineFirst.test_the_baseline_is_reused_for_the_fallback` — L165–L173
- `def TestTheUiComputesTheEngineFirst.test_engine_failure_does_not_block_the_ai` — L175–L182

### `tests/test_v1917_forecast.py`

آزمون‌های پیش‌بینی تایم‌فریم بعدی و راهبردهای تازه.

ارجاع داخلی: `ai/tools/market_tools.py`, `app/config/defaults.py`, `app/core/constants.py`, `app/core/models.py`, `app/database/models.py`, `localization/__init__.py`, `signals/forecast.py`, `signals/strategies/base.py`, `signals/strategies/momentum.py`, `signals/strategies/registry.py`, `signals/strategies/volatility_regime.py`, `signals/validity.py`, `ui/dialogs/signal_detail_dialog.py`.
- `class _Candle` — L20–L31
- `def _Candle.__init__` — L25–L31
- `def _series` — L34–L41
- `class TestTheForecastIsHonest` — L44–L172
- `def TestTheForecastIsHonest.test_it_produces_the_requested_horizons` — L47–L51
- `def TestTheForecastIsHonest.test_the_range_widens_with_distance` — L53–L63
- `def TestTheForecastIsHonest.test_the_probability_decays_with_distance` — L65–L75
- `def TestTheForecastIsHonest.test_probability_never_exceeds_the_cap` — L77–L87
- `def TestTheForecastIsHonest.test_the_actual_price_sits_inside_the_range` — L89–L95
- `def TestTheForecastIsHonest.test_a_bullish_signal_shifts_the_centre_up` — L97–L109
- `def TestTheForecastIsHonest.test_a_bearish_signal_shifts_the_centre_down` — L111–L123
- `def TestTheForecastIsHonest.test_the_bias_never_collapses_the_range` — L125–L142
- `def TestTheForecastIsHonest.test_a_wait_signal_stays_neutral` — L144–L155
- `def TestTheForecastIsHonest.test_a_calmer_market_gets_a_tighter_range` — L157–L165
- `def TestTheForecastIsHonest.test_the_price_is_never_negative` — L167–L172
- `class TestTheForecastRefusesToGuess` — L175–L215
- `def TestTheForecastRefusesToGuess.test_no_candles_means_no_forecast` — L178–L182
- `def TestTheForecastRefusesToGuess.test_a_short_history_means_no_forecast` — L184–L188
- `def TestTheForecastRefusesToGuess.test_a_flat_market_means_no_forecast` — L190–L195
- `def TestTheForecastRefusesToGuess.test_an_unknown_timeframe_is_refused` — L197–L201
- `def TestTheForecastRefusesToGuess.test_every_supported_timeframe_has_horizons` — L203–L207
- `def TestTheForecastRefusesToGuess.test_the_result_serialises` — L209–L215
- `class TestTheNewStrategiesAreRegistered` — L218–L317
- `def TestTheNewStrategiesAreRegistered.test_five_strategies_are_registered` — L221–L235
- `def TestTheNewStrategiesAreRegistered.test_momentum_abstains_without_data` — L237–L250
- `def TestTheNewStrategiesAreRegistered.test_volatility_regime_abstains_without_a_trend` — L252–L266
- `def TestTheNewStrategiesAreRegistered.test_volatility_regime_prefers_a_compressed_market` — L268–L299
- `def TestTheNewStrategiesAreRegistered.test_the_two_tools_are_exposed_to_the_ai` — L301–L307
- `def TestTheNewStrategiesAreRegistered.test_the_signal_model_carries_a_forecast_field` — L309–L317
- `class TestForecastAccuracyCanBeMeasured` — L320–L385
- `def TestForecastAccuracyCanBeMeasured._horizons` — L329–L334
- `def TestForecastAccuracyCanBeMeasured.test_a_price_inside_the_range_counts_as_a_hit` — L336–L343
- `def TestForecastAccuracyCanBeMeasured.test_a_price_outside_the_range_counts_as_a_miss` — L345–L352
- `def TestForecastAccuracyCanBeMeasured.test_the_boundary_counts_as_inside` — L354–L359
- `def TestForecastAccuracyCanBeMeasured.test_a_missing_actual_price_is_not_counted` — L361–L371
- `def TestForecastAccuracyCanBeMeasured.test_no_data_yields_a_zero_sample` — L373–L379
- `def TestForecastAccuracyCanBeMeasured.test_the_target_rate_is_reported` — L381–L385
- `class TestStaleSignalsCanBeHidden` — L388–L407
- `def TestStaleSignalsCanBeHidden.test_the_not_enterable_set_defines_stale` — L395–L401
- `def TestStaleSignalsCanBeHidden.test_the_setting_is_registered_with_a_safe_default` — L403–L407
- `class TestTheValidityWindowIsPersisted` — L410–L421
- `def TestTheValidityWindowIsPersisted.test_the_signal_record_has_the_columns` — L413–L421
- `class TestTheForecastIsVisibleInTheDetailDialog` — L424–L512
- `def TestTheForecastIsVisibleInTheDetailDialog._signal` — L428–L438
- `def TestTheForecastIsVisibleInTheDetailDialog.test_the_section_appears_when_a_forecast_exists` — L440–L457
- `def TestTheForecastIsVisibleInTheDetailDialog.test_the_section_is_absent_for_older_signals` — L459–L469
- `def TestTheForecastIsVisibleInTheDetailDialog.test_malformed_rows_are_skipped` — L471–L479
- `def TestTheForecastIsVisibleInTheDetailDialog.test_an_inverted_range_is_rejected` — L481–L490
- `def TestTheForecastIsVisibleInTheDetailDialog.test_one_good_row_survives_a_bad_neighbour` — L492–L512

### `tests/test_v1917_trust_and_trades.py`

آزمون‌های نسخه ۱.۹.۱۷ — بازبینی اعتماد به سیگنال و معاملات زنده.

ارجاع داخلی: `ai/agent/autonomous_agent.py`, `app/core/models.py`, `app/database/session.py`, `signals/__init__.py`, `signals/confidence.py`, `signals/engine.py`, `signals/strategies/base.py`, `trading/trade_monitor.py`.
- `class TestConfidenceIsNowEarned` — L29–L92
- `def TestConfidenceIsNowEarned.test_a_single_strategy_cannot_reach_high_confidence` — L32–L42
- `def TestConfidenceIsNowEarned.test_confidence_grows_with_independent_evidence` — L44–L55
- `def TestConfidenceIsNowEarned.test_one_hundred_percent_is_never_shown` — L57–L67
- `def TestConfidenceIsNowEarned.test_no_evidence_means_no_confidence` — L69–L74
- `def TestConfidenceIsNowEarned.test_disagreement_lowers_confidence` — L76–L84
- `def TestConfidenceIsNowEarned.test_the_reason_is_explained_to_the_user` — L86–L92
- `class TestHistoricalCalibration` — L95–L163
- `def TestHistoricalCalibration.test_a_bad_track_record_pulls_confidence_down` — L98–L119
- `def TestHistoricalCalibration.test_a_good_track_record_is_rewarded` — L121–L134
- `def TestHistoricalCalibration.test_a_tiny_sample_is_ignored` — L136–L153
- `def TestHistoricalCalibration.test_missing_statistics_change_nothing` — L155–L163
- `class TestTheEngineUsesTheNewModel` — L166–L210
- `def TestTheEngineUsesTheNewModel.test_one_vote_no_longer_yields_full_confidence` — L169–L187
- `def TestTheEngineUsesTheNewModel.test_broken_calibration_source_does_not_break_signals` — L189–L210
- `class TestTheEngineUsesTheNewModel.test_broken_calibration_source_does_not_break_signals._Broken` — L195–L197
- `def TestTheEngineUsesTheNewModel.test_broken_calibration_source_does_not_break_signals._Broken.confidence_buckets` — L196–L197
- `class TestOpenTradesAreAlive` — L213–L332
- `def TestOpenTradesAreAlive._long` — L216–L226
- `def TestOpenTradesAreAlive.test_profit_is_measured_against_margin_not_price` — L228–L236
- `def TestOpenTradesAreAlive.test_loss_is_negative` — L238–L242
- `def TestOpenTradesAreAlive.test_short_profits_when_price_falls` — L244–L255
- `def TestOpenTradesAreAlive.test_take_profit_closes_the_trade` — L257–L261
- `def TestOpenTradesAreAlive.test_stop_loss_closes_the_trade` — L263–L267
- `def TestOpenTradesAreAlive.test_stop_loss_wins_when_both_are_hit` — L269–L286
- `def TestOpenTradesAreAlive.test_a_quiet_market_keeps_the_trade_open` — L288–L291
- `def TestOpenTradesAreAlive.test_a_missing_price_is_skipped_not_zeroed` — L293–L301
- `def TestOpenTradesAreAlive.test_evaluate_reports_both_updates_and_closures` — L303–L308
- `def TestOpenTradesAreAlive.test_a_broken_record_is_skipped` — L310–L313
- `def TestOpenTradesAreAlive.test_a_valid_record_is_converted` — L315–L332
- `class TestTheSignalHistoryCanBeSorted` — L335–L383
- `def TestTheSignalHistoryCanBeSorted._rows` — L339–L344
- `def TestTheSignalHistoryCanBeSorted.test_sort_keys_exist_in_both_languages` — L346–L367
- `def TestTheSignalHistoryCanBeSorted.test_close_reason_messages_exist` — L369–L383
- `class TestTheAiIsAFuturesSpecialist` — L386–L412
- `def TestTheAiIsAFuturesSpecialist.test_the_prompt_describes_a_senior_derivatives_analyst` — L389–L394
- `def TestTheAiIsAFuturesSpecialist.test_the_prompt_anchors_confidence_bands` — L396–L405
- `def TestTheAiIsAFuturesSpecialist.test_the_prompt_covers_futures_specific_risk` — L407–L412
- `class TestUpgradingAnExistingDatabase` — L415–L508
- `def TestUpgradingAnExistingDatabase.test_a_missing_column_is_added_to_an_existing_table` — L425–L457
- `def TestUpgradingAnExistingDatabase.test_existing_rows_survive_the_upgrade` — L459–L499
- `def TestUpgradingAnExistingDatabase.test_reconciliation_is_safe_to_run_twice` — L501–L508

### `tests/test_v1918_alerts.py`

آزمون‌های سامانهٔ هشدار.

ارجاع داخلی: `app/config/defaults.py`, `localization/__init__.py`, `signals/alerts.py`, `ui/controllers/main_controller.py`, `ui/pages/markets_page.py`.
- `class TestAlertValidation` — L24–L56
- `def TestAlertValidation.test_valid_price_alert` — L27–L30
- `def TestAlertValidation.test_price_alert_needs_a_symbol` — L32–L36
- `def TestAlertValidation.test_price_alert_rejects_zero` — L38–L41
- `def TestAlertValidation.test_price_alert_rejects_bad_direction` — L43–L46
- `def TestAlertValidation.test_signal_alert_needs_confidence_in_range` — L48–L52
- `def TestAlertValidation.test_unknown_kind_is_rejected` — L54–L56
- `class TestPriceMatching` — L59–L94
- `def TestPriceMatching.test_above_fires_at_or_over_target` — L62–L67
- `def TestPriceMatching.test_below_fires_at_or_under_target` — L69–L74
- `def TestPriceMatching.test_disabled_alert_never_fires` — L76–L79
- `def TestPriceMatching.test_already_triggered_alert_does_not_refire` — L81–L89
- `def TestPriceMatching.test_zero_price_is_ignored` — L91–L94
- `class TestSignalMatching` — L97–L144
- `def TestSignalMatching._alert` — L100–L103
- `def TestSignalMatching.test_high_confidence_signal_fires` — L105–L109
- `def TestSignalMatching.test_low_confidence_signal_does_not_fire` — L111–L115
- `def TestSignalMatching.test_wait_signal_never_fires` — L117–L125
- `def TestSignalMatching.test_symbol_filter_is_respected` — L127–L132
- `def TestSignalMatching.test_empty_symbol_means_all_symbols` — L134–L138
- `def TestSignalMatching.test_malformed_confidence_does_not_crash` — L140–L144
- `class TestAlertBook` — L147–L236
- `def TestAlertBook.test_add_assigns_unique_ids` — L150–L155
- `def TestAlertBook.test_add_rejects_invalid` — L157–L163
- `def TestAlertBook.test_remove_works` — L165–L171
- `def TestAlertBook.test_rearm_resets_triggered` — L173–L180
- `def TestAlertBook.test_active_symbols_only_lists_armed_price_alerts` — L182–L192
- `def TestAlertBook.test_check_prices_marks_triggered` — L194–L199
- `def TestAlertBook.test_missing_symbol_price_is_skipped` — L201–L205
- `def TestAlertBook.test_round_trip_through_storage` — L207–L217
- `def TestAlertBook.test_malformed_storage_is_tolerated` — L219–L224
- `def TestAlertBook.test_non_list_storage_is_tolerated` — L226–L229
- `def TestAlertBook.test_describe_is_human_readable` — L231–L236
- `class TestWiring` — L239–L284
- `def TestWiring.test_settings_define_alert_keys` — L242–L248
- `def TestWiring.test_controller_checks_price_alerts` — L250–L256
- `def TestWiring.test_price_check_only_fetches_armed_symbols` — L258–L263
- `def TestWiring.test_controller_checks_signal_alerts` — L265–L269
- `def TestWiring.test_triggered_state_is_persisted` — L271–L278
- `def TestWiring.test_controller_can_create_an_alert` — L280–L284
- `class TestMarketsPageButton` — L288–L310
- `def TestMarketsPageButton.test_markets_page_has_alert_button` — L291–L298
- `def TestMarketsPageButton.test_alert_button_emits_selected_symbol` — L300–L310

### `tests/test_v1918_live_and_auto.py`

آزمون‌های نسخهٔ ۱.۹.۱۸.

ارجاع داخلی: `ai/agent/autonomous_agent.py`, `app/application.py`, `app/core/models.py`, `app/database/repositories/signal_repository.py`, `localization/__init__.py`, `trading/auto_trader.py`, `ui/charts/price_chart.py`, `ui/controllers/main_controller.py`, `ui/dialogs/analysis_dialog.py`, `ui/pages/analysis_page.py`, `ui/pages/trades_page.py`.
- `class TestAgentPreload` — L27–L68
- `def TestAgentPreload.test_preload_helper_exists` — L30–L33
- `def TestAgentPreload.test_preload_runs_tools_in_parallel` — L35–L43
- `def TestAgentPreload.test_preload_collects_the_three_core_tools` — L45–L53
- `def TestAgentPreload.test_loop_injects_preloaded_evidence` — L55–L58
- `def TestAgentPreload.test_render_tool_data_truncates` — L60–L63
- `def TestAgentPreload.test_render_tool_data_handles_empty` — L65–L68
- `class TestDeadlineGuard` — L71–L82
- `def TestDeadlineGuard.test_loop_tracks_elapsed_time` — L74–L77
- `def TestDeadlineGuard.test_loop_forces_a_final_answer_before_timeout` — L79–L82
- `class TestRerunAnalysis` — L88–L141
- `def TestRerunAnalysis.test_repository_exposes_flat_payload` — L91–L93
- `def TestRerunAnalysis.test_repository_can_update_analysis` — L95–L97
- `def TestRerunAnalysis.test_get_with_analysis_still_returns_tuple` — L99–L107
- `def TestRerunAnalysis.test_controller_no_longer_unpacks_tuple` — L109–L117
- `def TestRerunAnalysis.test_controller_has_rerun_handler` — L119–L123
- `def TestRerunAnalysis.test_rerun_persists_result` — L125–L130
- `def TestRerunAnalysis.test_application_keeps_last_signal_id` — L132–L141
- `class TestRerunDialog` — L145–L182
- `def TestRerunDialog._dialog` — L148–L152
- `def TestRerunDialog.test_dialog_has_rerun_button` — L154–L156
- `def TestRerunDialog.test_rerun_emits_signal_with_payload` — L158–L164
- `def TestRerunDialog.test_button_locks_while_running` — L166–L170
- `def TestRerunDialog.test_new_text_replaces_viewer_content` — L172–L177
- `def TestRerunDialog.test_empty_analysis_shows_guidance_not_blank` — L179–L182
- `class TestLiveChart` — L189–L305
- `def TestLiveChart._chart` — L192–L196
- `def TestLiveChart._candles` — L198–L215
- `def TestLiveChart.test_chart_supports_three_types` — L217–L229
- `def TestLiveChart.test_unknown_type_falls_back_to_candles` — L231–L236
- `def TestLiveChart.test_live_price_line_appears` — L238–L244
- `def TestLiveChart.test_live_price_ignores_invalid_values` — L246–L251
- `def TestLiveChart.test_manual_zoom_survives_a_refresh` — L253–L268
- `def TestLiveChart.test_fit_button_restores_auto_range` — L270–L277
- `def TestLiveChart.test_analysis_page_exposes_chart_tools` — L279–L288
- `def TestLiveChart.test_analysis_page_updates_live_price` — L290–L298
- `def TestLiveChart.test_controller_has_a_separate_price_ticker` — L300–L305
- `class TestAutoTradingVisible` — L312–L418
- `def TestAutoTradingVisible._page` — L315–L319
- `def TestAutoTradingVisible.test_trades_page_has_auto_panel` — L321–L326
- `def TestAutoTradingVisible.test_toggle_emits_start_then_stop` — L328–L339
- `def TestAutoTradingVisible.test_state_label_reflects_engine` — L341–L346
- `def TestAutoTradingVisible.test_no_untranslated_keys_on_screen` — L348–L356
- `def TestAutoTradingVisible.test_controller_wires_the_engine` — L358–L365
- `def TestAutoTradingVisible.test_controller_uses_user_settings_not_hardcoded_numbers` — L367–L410
- `class TestAutoTradingVisible.test_controller_uses_user_settings_not_hardcoded_numbers.Settings` — L396–L398
- `def TestAutoTradingVisible.test_controller_uses_user_settings_not_hardcoded_numbers.Settings.get` — L397–L398
- `def TestAutoTradingVisible.test_engine_defaults_to_paper` — L412–L418

### `tests/test_v1918_scorecard.py`

آزمون‌های دفترچهٔ نتیجهٔ پیش‌بینی‌ها.

ارجاع داخلی: `app/application.py`, `localization/__init__.py`, `signals/scorecard.py`, `ui/controllers/main_controller.py`, `ui/pages/reports_page.py`.
- `def _forecast` — L26–L28
- `def _signal` — L31–L33
- `class TestHorizonDue` — L36–L58
- `def TestHorizonDue.test_matured_horizon_is_due` — L39–L41
- `def TestHorizonDue.test_immature_horizon_is_not_due` — L43–L45
- `def TestHorizonDue.test_exactly_at_boundary_counts_as_due` — L47–L49
- `def TestHorizonDue.test_unknown_horizon_is_never_due` — L51–L53
- `def TestHorizonDue.test_naive_datetime_is_treated_as_utc` — L55–L58
- `class TestBuildReport` — L61–L165
- `def TestBuildReport.test_empty_input_is_safe` — L64–L69
- `def TestBuildReport.test_price_inside_band_counts_as_hit` — L71–L77
- `def TestBuildReport.test_price_outside_band_counts_as_miss` — L79–L84
- `def TestBuildReport.test_immature_horizon_is_pending_not_counted` — L86–L95
- `def TestBuildReport.test_missing_price_is_pending_not_a_miss` — L97–L102
- `def TestBuildReport.test_rows_are_grouped_by_horizon` — L104–L117
- `def TestBuildReport.test_rows_keep_a_stable_order` — L119–L135
- `def TestBuildReport.test_signal_without_forecast_is_skipped` — L137–L142
- `def TestBuildReport.test_malformed_rows_do_not_crash` — L144–L154
- `def TestBuildReport.test_multiple_symbols_are_kept_separate` — L156–L165
- `class TestVerdict` — L168–L225
- `def TestVerdict._report_with` — L171–L184
- `def TestVerdict.test_small_sample_gives_no_verdict` — L186–L194
- `def TestVerdict.test_low_hit_rate_means_bands_too_narrow` — L196–L201
- `def TestVerdict.test_perfect_hit_rate_means_bands_too_wide` — L203–L207
- `def TestVerdict.test_on_target_is_calibrated` — L209–L214
- `def TestVerdict.test_small_drift_is_tolerated` — L216–L220
- `def TestVerdict.test_sigma_shift_is_capped` — L222–L225
- `class TestApplicationWiring` — L228–L255
- `def TestApplicationWiring.test_application_exposes_score_forecasts` — L231–L236
- `def TestApplicationWiring.test_it_uses_historical_candles_not_current_price` — L238–L247
- `def TestApplicationWiring.test_controller_can_refresh_the_scorecard` — L249–L255
- `class TestScorecardPage` — L259–L319
- `def TestScorecardPage._page` — L262–L266
- `def TestScorecardPage.test_reports_page_has_three_tabs` — L268–L270
- `def TestScorecardPage.test_table_renders_rows` — L272–L295
- `def TestScorecardPage.test_empty_report_shows_guidance` — L297–L301
- `def TestScorecardPage.test_no_untranslated_keys` — L303–L311
- `def TestScorecardPage.test_refresh_button_emits` — L313–L319

### `tests/test_v191_outcome_tracking.py`

آزمون پیگیری نتیجهٔ واقعی سیگنال‌ها (مورد ۱.۵ نقشهٔ راه).

ارجاع داخلی: `app/config/defaults.py`, `app/core/constants.py`, `app/core/models.py`, `app/database/repositories/outcome_repository.py`, `app/database/repositories/signal_repository.py`, `localization/__init__.py`, `signals/outcome_tracker.py`, `ui/pages/reports_page.py`, `ui/widgets/performance_view.py`.
- `def make_state` — L53–L69
- `class TestPercentChange` — L75–L96
- `def TestPercentChange.test_long_profits_when_price_rises` — L78–L80
- `def TestPercentChange.test_short_profits_when_price_falls` — L82–L88
- `def TestPercentChange.test_short_loses_when_price_rises` — L90–L92
- `def TestPercentChange.test_zero_entry_is_not_a_division_error` — L94–L96
- `class TestStopBeatsTarget` — L99–L119
- `def TestStopBeatsTarget.test_a_window_touching_both_is_recorded_as_a_loss` — L102–L112
- `def TestStopBeatsTarget.test_target_alone_still_wins` — L114–L119
- `class TestTargets` — L122–L165
- `def TestTargets.test_first_target_counts_but_does_not_close` — L125–L134
- `def TestTargets.test_last_target_closes_the_signal` — L136–L143
- `def TestTargets.test_targets_are_counted_in_order` — L145–L155
- `def TestTargets.test_short_targets_are_below_entry` — L157–L165
- `class TestRMultiple` — L168–L190
- `def TestRMultiple.test_full_target_run_equals_the_risk_reward` — L171–L176
- `def TestRMultiple.test_a_stop_is_exactly_minus_one_r` — L178–L183
- `def TestRMultiple.test_zero_risk_distance_does_not_divide_by_zero` — L185–L190
- `class TestLeverageIsExcluded` — L193–L205
- `def TestLeverageIsExcluded.test_result_percent_is_unleveraged` — L196–L205
- `class TestExcursions` — L208–L226
- `def TestExcursions.test_favorable_and_adverse_are_tracked` — L211–L217
- `def TestExcursions.test_extremes_never_shrink` — L219–L226
- `class TestClosedSignalsAreFrozen` — L229–L244
- `def TestClosedSignalsAreFrozen.test_further_prices_do_not_change_a_closed_outcome` — L232–L244
- `class TestExpiry` — L247–L291
- `def TestExpiry.test_expiry_depends_on_the_timeframe` — L250–L253
- `def TestExpiry.test_unknown_timeframe_falls_back_to_a_week` — L255–L260
- `def TestExpiry.test_every_known_timeframe_has_a_positive_window` — L262–L264
- `def TestExpiry.test_passing_the_deadline_closes_as_expired` — L266–L271
- `def TestExpiry.test_a_target_hit_beats_an_expiry_in_the_same_window` — L273–L281
- `def TestExpiry.test_naive_deadline_does_not_raise` — L283–L291
- `class TestPriceWindow` — L294–L308
- `def TestPriceWindow.test_a_single_price_fills_all_three_bounds` — L297–L302
- `def TestPriceWindow.test_zero_low_is_ignored` — L304–L308
- `class FakeOutcome` — L314–L331
- `def FakeOutcome.__init__` — L317–L331
- `class TestSummary` — L334–L386
- `def TestSummary.test_open_signals_do_not_dilute_the_win_rate` — L337–L353
- `def TestSummary.test_expired_signals_are_counted_separately` — L355–L366
- `def TestSummary.test_profit_factor_divides_gains_by_losses` — L368–L378
- `def TestSummary.test_an_empty_history_is_safe` — L380–L386
- `class TestGrouping` — L389–L437
- `def TestGrouping.test_confidence_buckets_are_ten_wide` — L392–L403
- `def TestGrouping.test_confidence_bucket_answers_the_key_question` — L405–L421
- `def TestGrouping.test_grouping_by_symbol_and_timeframe` — L423–L431
- `def TestGrouping.test_missing_attribute_becomes_a_dash` — L433–L437
- `def repos` — L444–L446
- `def make_signal` — L449–L475
- `class TestRepository` — L478–L618
- `def TestRepository.test_entry_price_is_the_middle_of_the_range` — L481–L491
- `def TestRepository.test_tracking_is_idempotent` — L493–L505
- `def TestRepository.test_wait_signals_are_not_tracked` — L507–L512
- `def TestRepository.test_a_signal_without_a_stop_is_not_tracked` — L514–L519
- `def TestRepository.test_unknown_signal_is_handled` — L521–L525
- `def TestRepository.test_state_round_trip` — L527–L542
- `def TestRepository.test_open_outcomes_exclude_closed_ones` — L544–L559
- `def TestRepository.test_open_symbols_are_unique` — L561–L567
- `def TestRepository.test_cancel_marks_the_outcome_manual` — L569–L579
- `def TestRepository.test_backfill_picks_up_untracked_signals` — L581–L593
- `def TestRepository.test_history_filters_by_confidence` — L595–L604
- `def TestRepository.test_performance_report_has_every_breakdown` — L606–L618
- `def view` — L625–L629
- `class TestPerformanceView` — L650–L770
- `def TestPerformanceView.test_report_fills_the_breakdown_table` — L653–L657
- `def TestPerformanceView.test_wins_and_losses_keep_their_order_in_rtl` — L659–L670
- `def TestPerformanceView.test_negative_numbers_keep_the_minus_in_front` — L672–L677
- `def TestPerformanceView.test_win_rate_card_reports_the_sample_size` — L679–L686
- `def TestPerformanceView.test_an_empty_report_is_safe` — L688–L693
- `def TestPerformanceView.test_history_shows_the_empty_state` — L695–L699
- `def TestPerformanceView.test_history_rows_are_rendered` — L701–L712
- `def TestPerformanceView.test_symbol_is_never_rtl_mangled` — L714–L725
- `def TestPerformanceView.test_period_selection_reports_days` — L727–L731
- `def TestPerformanceView.test_all_period_means_no_limit` — L733–L737
- `def TestPerformanceView.test_infinite_profit_factor_is_readable` — L739–L744
- `def TestPerformanceView.test_theme_key_string_does_not_crash_colouring` — L746–L760
- `def TestPerformanceView.test_retranslate_switches_language` — L762–L770
- `class TestReportsPageTabs` — L773–L811
- `def TestReportsPageTabs.test_performance_is_a_tab_of_the_reports_page` — L776–L791
- `def TestReportsPageTabs.test_the_export_tab_still_works` — L793–L802
- `def TestReportsPageTabs.test_show_performance_opens_the_right_tab` — L804–L811
- `class TestLocalization` — L817–L856
- `def TestLocalization.test_every_performance_key_exists` — L821–L842
- `def TestLocalization.test_placeholders_are_filled` — L852–L856
- `class TestSettings` — L862–L887
- `def TestSettings.test_tracking_is_on_by_default` — L865–L872
- `def TestSettings.test_interval_and_batch_have_sane_defaults` — L874–L879
- `def TestSettings.test_keys_are_registered_in_the_signals_group` — L881–L887

### `tests/test_v1920_ashna_settings.py`

آزمون‌های دسترسی کاربر به «آشنا هوش مصنوعی» از صفحهٔ تنظیمات.

ارجاع داخلی: `ai/providers/catalog.py`, `localization/__init__.py`, `ui/pages/settings_page.py`.
- `def qt_application` — L24–L26
- `def page` — L30–L42
- `class TestAshnaPreset` — L45–L70
- `def TestAshnaPreset.test_ashna_is_registered` — L48–L50
- `def TestAshnaPreset.test_base_url_keeps_the_v1_api_suffix` — L52–L60
- `def TestAshnaPreset.test_ashna_asks_for_a_key` — L62–L66
- `def TestAshnaPreset.test_signup_url_points_at_the_key_page` — L68–L70
- `class TestProviderDropdown` — L73–L91
- `def TestProviderDropdown.test_ashna_appears_in_the_dropdown` — L76–L78
- `def TestProviderDropdown.test_dropdown_lists_every_catalog_preset` — L80–L86
- `def TestProviderDropdown.test_display_name_is_findable_in_persian` — L88–L91
- `class TestSelectingAshna` — L94–L143
- `def TestSelectingAshna._select` — L97–L101
- `def TestSelectingAshna.test_key_field_is_visible_and_enabled` — L103–L107
- `def TestSelectingAshna.test_key_field_hides_what_is_typed` — L109–L112
- `def TestSelectingAshna.test_base_url_is_filled_automatically` — L114–L117
- `def TestSelectingAshna.test_suggested_models_are_offered` — L119–L123
- `def TestSelectingAshna.test_hint_shows_where_to_get_the_key` — L125–L133
- `def TestSelectingAshna.test_every_provider_with_a_signup_url_shows_it` — L135–L143
- `class TestKeyReachesStorage` — L146–L186
- `def TestKeyReachesStorage.test_typed_key_is_collected_under_the_provider_name` — L149–L163
- `def TestKeyReachesStorage.test_provider_choice_is_collected` — L165–L171
- `def TestKeyReachesStorage.test_key_is_not_collected_as_a_plain_setting` — L173–L186

### `tests/test_v1921_online_and_autotrade.py`

آزمون‌های سه خواستهٔ کاربر در نسخهٔ ۱.۹.۲۱.

ارجاع داخلی: `localization/__init__.py`, `market/engine.py`, `trading/auto_trader.py`, `trading/confidence_source.py`, `ui/pages/trades_page.py`.
- `def qt_application` — L29–L31
- `class _StubProvider` — L37–L45
- `def _StubProvider.create_websocket` — L43–L45
- `def market_engine` — L49–L58
- `class TestOfflineTolerance` — L61–L110
- `def TestOfflineTolerance.test_tolerance_is_more_than_one` — L68–L70
- `def TestOfflineTolerance.test_a_single_blip_keeps_us_online` — L72–L77
- `def TestOfflineTolerance.test_repeated_failures_eventually_report_offline` — L79–L85
- `def TestOfflineTolerance.test_one_success_heals_immediately` — L87–L98
- `def TestOfflineTolerance.test_counter_resets_so_blips_do_not_accumulate` — L100–L110
- `class _FakeDirection` — L117–L120
- `class _FakeSignal` — L124–L139
- `class _FakeSettings` — L142–L155
- `def _FakeSettings.__init__` — L145–L147
- `def _FakeSettings.get_int` — L149–L151
- `def _FakeSettings.get` — L153–L155
- `class _FakeApp` — L158–L174
- `def _FakeApp.__init__` — L161–L165
- `async def _FakeApp.scan_market` — L167–L174
- `class _FakeApp.scan_market._Result` — L171–L172
- `def _long` — L177–L179
- `class TestConfidenceSelection` — L182–L283
- `async def TestConfidenceSelection.test_only_signals_above_the_threshold_are_returned` — L186–L194
- `async def TestConfidenceSelection.test_results_are_sorted_by_confidence` — L197–L205
- `async def TestConfidenceSelection.test_wait_signals_never_become_trades` — L208–L213
- `async def TestConfidenceSelection.test_entry_price_is_the_middle_of_the_range` — L216–L227
- `async def TestConfidenceSelection.test_signal_without_a_price_is_skipped` — L230–L236
- `async def TestConfidenceSelection.test_threshold_is_passed_down_to_the_scanner` — L239–L245
- `async def TestConfidenceSelection.test_a_failed_scan_does_not_kill_the_engine` — L248–L256
- `class TestConfidenceSelection.test_a_failed_scan_does_not_kill_the_engine._Boom : _FakeApp` — L251–L254
- `async def TestConfidenceSelection.test_a_failed_scan_does_not_kill_the_engine._Boom.scan_market` — L252–L254
- `def TestConfidenceSelection.test_confidence_floor_cannot_be_bypassed` — L258–L262
- `def TestConfidenceSelection.test_user_can_be_stricter` — L264–L268
- `def TestConfidenceSelection.test_candidate_exposes_the_fields_autotrader_reads` — L270–L283
- `class TestManualAutoTradeControls` — L289–L412
- `def TestManualAutoTradeControls.page` — L293–L299
- `def TestManualAutoTradeControls.test_manual_inputs_exist` — L301–L312
- `def TestManualAutoTradeControls.test_inputs_start_locked` — L314–L320
- `def TestManualAutoTradeControls.test_checkbox_unlocks_the_inputs` — L322–L327
- `def TestManualAutoTradeControls.test_values_load_from_settings` — L329–L345
- `def TestManualAutoTradeControls.test_collect_returns_the_scalp_keys` — L347–L357
- `def TestManualAutoTradeControls.test_apply_button_emits_the_values` — L359–L369
- `def TestManualAutoTradeControls.test_confidence_input_cannot_go_below_the_floor` — L371–L375
- `def TestManualAutoTradeControls.test_collapsed_box_does_not_steal_height` — L377–L406
- `def TestManualAutoTradeControls.test_collapsed_box_does_not_steal_height.body_height` — L388–L391
- `def TestManualAutoTradeControls.test_leverage_is_capped_in_the_ui` — L408–L412

### `tests/test_v1922_micro_speed.py`

آزمون‌های نسخهٔ ۱.۹.۲۲ بدون وابستگی به PySide6.

ارجاع داخلی: `ai/speed_profile.py`, `trading/auto_trader.py`, `trading/execution.py`, `trading/micro_plan.py`.
- `class _Settings : dict` — L24–L28
- `def _Settings.get` — L27–L28
- `class _Executor` — L31–L43
- `def _Executor.__init__` — L34–L35
- `async def _Executor.open_position` — L37–L39
- `async def _Executor.close_position` — L41–L43
- `class TestMicroEconomics` — L46–L75
- `def TestMicroEconomics.test_ten_dollars_at_two_hundred_needs_five_forty_gross_for_three_net` — L49–L56
- `def TestMicroEconomics.test_existing_small_targets_still_clear_the_old_test_prices` — L58–L67
- `def TestMicroEconomics.test_poll_can_be_faster_than_one_second_but_not_reckless` — L69–L71
- `def TestMicroEconomics.test_leverage_cap_is_the_requested_two_hundred` — L73–L75
- `class TestLiveGateway` — L78–L111
- `def TestLiveGateway.test_missing_executor_fails_loudly` — L81–L87
- `def TestLiveGateway.test_old_constructor_still_refuses` — L89–L93
- `def TestLiveGateway.test_zero_quantity_never_reaches_the_executor` — L95–L102
- `def TestLiveGateway.test_positive_quantity_can_use_an_injected_executor` — L104–L111
- `class TestSpeedProfile` — L114–L145
- `def TestSpeedProfile.test_unknown_name_is_balanced_not_fast` — L117–L119
- `def TestSpeedProfile.test_fast_uses_one_step` — L121–L126
- `def TestSpeedProfile.test_balanced_keeps_saved_numbers` — L128–L145

### `tests/test_v192_watchlist.py`

آزمون فهرست‌های دیده‌بانی چندگانه (مورد ۵.۳ نقشهٔ راه).

ارجاع داخلی: `app/core/models.py`, `app/database/repositories/symbol_repository.py`, `localization/__init__.py`, `ui/pages/markets_page.py`, `ui/widgets/watchlist_panel.py`.
- `def make_symbols` — L31–L41
- `def repo` — L45–L49
- `def filled` — L53–L57
- `def test_names_empty_database_still_offers_default` — L65–L67
- `def test_default_list_is_always_first` — L70–L76
- `def test_counts_are_per_list` — L79–L84
- `def test_same_symbol_can_live_in_two_lists` — L87–L92
- `def test_create_rejects_blank_name` — L100–L103
- `def test_create_rejects_duplicate` — L106–L108
- `def test_rename_moves_every_member` — L111–L116
- `def test_rename_onto_existing_name_is_refused` — L119–L129
- `def test_default_list_cannot_be_renamed` — L132–L134
- `def test_delete_removes_named_list` — L137–L141
- `def test_delete_default_empties_but_keeps_it` — L144–L148
- `def test_delete_unknown_list_is_harmless` — L151–L154
- `def test_details_are_ordered_by_position` — L162–L166
- `def test_positions_are_contiguous` — L169–L173
- `def test_move_down_swaps_with_next` — L176–L183
- `def test_move_up_swaps_with_previous` — L186–L193
- `def test_move_up_at_top_is_refused` — L196–L201
- `def test_move_down_at_bottom_is_refused` — L204–L206
- `def test_move_unknown_symbol_is_refused` — L209–L211
- `def test_reorder_applies_given_order` — L214–L221
- `def test_reorder_keeps_unlisted_members_at_the_end` — L224–L235
- `def test_removing_middle_member_keeps_order_of_rest` — L238–L244
- `def test_order_is_independent_per_list` — L247–L258
- `def test_note_round_trips` — L266–L270
- `def test_note_is_capped` — L273–L277
- `def test_note_on_unknown_member_is_refused` — L280–L282
- `def test_legacy_get_watchlist_reads_default_list` — L290–L292
- `def test_legacy_get_watchlist_ignores_other_lists` — L295–L303
- `def test_duplicate_add_is_idempotent` — L306–L309
- `def panel` — L318–L322
- `def test_panel_starts_empty` — L325–L328
- `def test_panel_lists_carry_counts` — L331–L335
- `def test_panel_combo_stores_raw_name_as_data` — L338–L347
- `def test_panel_rows_match_items` — L350–L359
- `def test_panel_symbol_cells_are_ltr_marked` — L362–L371
- `def test_panel_disables_actions_without_selection` — L374–L380
- `def test_panel_protects_the_default_list` — L383–L387
- `def test_panel_enables_delete_for_named_list` — L390–L395
- `def test_panel_select_symbol_works_in_rtl` — L398–L420
- `def test_panel_select_unknown_symbol_returns_false` — L423–L426
- `def test_panel_emits_moved_signal` — L429–L442
- `def test_panel_emits_removed_signal` — L445–L453
- `def test_panel_current_list_defaults_when_empty` — L456–L458
- `def test_panel_retranslate_keeps_selection` — L461–L466
- `def test_watchlist_keys_exist` — L496–L500
- `def test_markets_tab_keys_exist` — L504–L510
- `def test_both_languages_share_watchlist_keys` — L513–L521

### `tests/test_v193_page_scrolling.py`

آزمون پیمایش صفحه و اندازه‌های صفحهٔ سیگنال‌ها (نسخهٔ ۱.۹.۳).

ارجاع داخلی: `localization/__init__.py`, `ui/pages/markets_page.py`, `ui/pages/reports_page.py`, `ui/pages/signals_page.py`, `ui/pages/trades_page.py`.
- `def translator` — L45–L47
- `def build_page` — L50–L53
- `def test_page_fits_a_laptop_screen` — L57–L70
- `def test_signals_page_is_marked_scrollable` — L73–L80
- `def test_signals_page_really_scrolls` — L83–L103
- `def test_signals_page_has_no_horizontal_scrollbar` — L106–L120
- `def test_header_stays_outside_the_scroll_area` — L123–L136
- `def test_wait_note_is_not_clipped` — L139–L154
- `def make_scan_rows` — L157–L169
- `def test_scan_table_grows_with_results` — L173–L193
- `def test_scan_table_is_capped_for_long_results` — L196–L216
- `def test_scan_table_shrinks_back_when_cleared` — L219–L232
- `def test_hidden_progress_bar_takes_no_space` — L235–L251
- `def test_table_toolbars_survive_inside_the_scroll_area` — L254–L267
- `def test_non_scrollable_pages_keep_their_layout` — L270–L283
- `def test_trades_page_is_scrollable_terminal` — L286–L301
- `def test_reports_report_tab_is_scrollable` — L304–L318

### `tests/test_v194_performance.py`

آزمون بهینه‌سازی سرعت (نسخهٔ ۱.۹.۴).

ارجاع داخلی: `app/core/models.py`, `app/exceptions/__init__.py`, `indicators/base.py`, `indicators/engine.py`, `indicators/registry.py`, `localization/__init__.py`, `market/cache/__init__.py`, `signals/__init__.py`, `ui/pages/signals_page.py`, `ui/widgets/table_toolbar.py`.
- `def run_isolated` — L28–L44
- `def test_outcome_tracker_does_not_pull_pandas` — L52–L63
- `def test_reading_settings_does_not_pull_pandas` — L66–L71
- `def test_widgets_do_not_pull_the_database_layer` — L74–L86
- `def test_signals_package_still_exports_everything` — L89–L107
- `def test_signals_dir_lists_lazy_names` — L110–L116
- `def test_signals_unknown_attribute_raises` — L119–L124
- `def engine` — L133–L140
- `def make_candles` — L143–L161
- `def test_fingerprint_matches_dataframe_and_candles` — L164–L176
- `def test_fingerprint_handles_empty_input` — L179–L184
- `def test_cache_hit_does_not_rebuild_the_dataframe` — L187–L210
- `def test_cache_hit_does_not_rebuild_the_dataframe.counting` — L204–L206
- `def test_cache_hit_does_not_recompute` — L213–L227
- `def test_cache_hit_does_not_recompute.counting` — L221–L223
- `def test_cache_miss_still_computes` — L230–L234
- `def test_cache_is_not_shared_across_symbols` — L237–L254
- `def test_calculate_many_matches_individual_results` — L257–L270
- `def test_calculate_many_survives_a_broken_indicator` — L273–L280
- `def test_empty_candles_still_raise` — L283–L292
- `def translator` — L301–L305
- `def toolbar_table` — L309–L340
- `def test_every_table_gets_an_export_button` — L343–L356
- `def test_rows_include_the_header` — L359–L364
- `def test_direction_marks_are_stripped` — L367–L378
- `def test_widget_cells_export_as_empty` — L381–L384
- `def test_hidden_columns_are_excluded` — L387–L393
- `def test_hidden_rows_are_excluded` — L396–L400
- `def test_csv_file_is_excel_safe` — L403–L417
- `def test_csv_round_trips` — L420–L430
- `def test_export_keys_exist_in_both_languages` — L433–L440

### `tests/test_v195_ai_and_validity.py`

آزمون‌های نسخهٔ ۱.۹.۵ — کار روی هوش مصنوعی و اعتبار سیگنال.

ارجاع داخلی: `ai/agent/analyst.py`, `ai/agent/reviewer.py`, `ai/prompt_budget.py`, `ai/prompts/__init__.py`, `ai/recommendation.py`, `app/config/defaults.py`, `app/core/constants.py`, `app/core/models.py`, `app/database/models.py`, `app/database/repositories/__init__.py`, `localization/__init__.py`, `signals/validity.py`, `ui/dialogs/signal_detail_dialog.py`, `ui/pages/signals_page.py`, `ui/signal_grading.py`.
- `class TestPromptBudget` — L35–L106
- `def TestPromptBudget.test_memory_tiers_match_real_hardware` — L38–L50
- `def TestPromptBudget.test_unknown_memory_is_conservative` — L52–L62
- `def TestPromptBudget.test_context_never_exceeds_the_ceiling` — L64–L68
- `def TestPromptBudget.test_window_is_the_smallest_that_fits` — L70–L79
- `def TestPromptBudget.test_reply_space_is_reserved` — L81–L91
- `def TestPromptBudget.test_compact_json_is_smaller_than_indented` — L93–L106
- `class TestMarketDataShrinking` — L109–L210
- `def TestMarketDataShrinking._market_data` — L113–L129
- `def TestMarketDataShrinking.test_nothing_is_dropped_when_it_already_fits` — L131–L138
- `def TestMarketDataShrinking.test_orderbook_goes_first` — L140–L152
- `def TestMarketDataShrinking.test_the_primary_timeframe_survives` — L154–L166
- `def TestMarketDataShrinking.test_the_widest_timeframe_survives` — L168–L181
- `def TestMarketDataShrinking.test_the_model_is_told_what_is_missing` — L183–L195
- `def TestMarketDataShrinking.test_shrinking_stops_as_soon_as_it_fits` — L197–L210
- `class TestReasoningBlock` — L218–L261
- `def TestReasoningBlock.test_the_think_block_is_removed` — L221–L232
- `def TestReasoningBlock.test_other_reasoning_tag_styles` — L238–L244
- `def TestReasoningBlock.test_an_unclosed_block_yields_nothing` — L246–L255
- `def TestReasoningBlock.test_plain_text_is_untouched` — L257–L261
- `def check` — L281–L291
- `class TestValidityWindow` — L294–L369
- `def TestValidityWindow.test_a_new_signal_is_fresh` — L297–L304
- `def TestValidityWindow.test_the_window_closes_before_it_expires` — L306–L315
- `def TestValidityWindow.test_a_late_signal_is_burned` — L317–L324
- `def TestValidityWindow.test_expiry_follows_the_timeframe` — L326–L337
- `def TestValidityWindow.test_the_fastest_timeframe_sets_the_pace` — L339–L349
- `def TestValidityWindow.test_a_stop_hit_invalidates_immediately` — L351–L361
- `def TestValidityWindow.test_wait_signals_have_no_entry_deadline` — L363–L369
- `class TestBurnedByPriceMovement` — L372–L437
- `def TestBurnedByPriceMovement.test_a_consumed_move_burns_a_brand_new_signal` — L379–L390
- `def TestBurnedByPriceMovement.test_effective_risk_reward_collapses` — L392–L403
- `def TestBurnedByPriceMovement.test_reaching_the_first_target_burns_it` — L405–L412
- `def TestBurnedByPriceMovement.test_an_adverse_move_raises_a_warning` — L414–L426
- `def TestBurnedByPriceMovement.test_without_a_price_only_time_is_judged` — L428–L437
- `class TestValidityOnTheSignalItself` — L440–L471
- `def TestValidityOnTheSignalItself.test_the_trading_signal_carries_its_deadlines` — L443–L454
- `def TestValidityOnTheSignalItself.test_the_deadlines_are_serialised` — L456–L471
- `class TestSignalReviewer` — L479–L652
- `def TestSignalReviewer._signal` — L483–L494
- `def TestSignalReviewer._outcome` — L497–L512
- `def TestSignalReviewer._providers` — L515–L526
- `class TestSignalReviewer._providers.FakeProviders` — L518–L524
- `async def TestSignalReviewer._providers.FakeProviders.generate` — L519–L524
- `def TestSignalReviewer._reviewer` — L528–L533
- `async def TestSignalReviewer.test_a_closed_signal_is_reviewed` — L536–L546
- `async def TestSignalReviewer.test_the_think_block_does_not_break_the_review` — L549–L564
- `async def TestSignalReviewer.test_an_open_signal_is_not_reviewed` — L567–L578
- `async def TestSignalReviewer.test_a_missing_model_is_not_a_crash` — L581–L600
- `class TestSignalReviewer.test_a_missing_model_is_not_a_crash.BrokenProviders` — L591–L593
- `async def TestSignalReviewer.test_a_missing_model_is_not_a_crash.BrokenProviders.generate` — L592–L593
- `async def TestSignalReviewer.test_the_review_prompt_is_small` — L603–L614
- `async def TestSignalReviewer.test_the_prompt_includes_the_real_numbers` — L617–L630
- `def TestSignalReviewer.test_lesson_labels_are_normalised` — L643–L652
- `class TestReviewRepository` — L655–L742
- `def TestReviewRepository.repository` — L659–L663
- `def TestReviewRepository.signal_id` — L666–L676
- `def TestReviewRepository.test_a_review_is_saved_and_read_back` — L678–L693
- `def TestReviewRepository.test_re_reviewing_replaces_instead_of_duplicating` — L695–L709
- `def TestReviewRepository.test_lesson_counts_answer_the_users_question` — L711–L742
- `class TestValidityInTheInterface` — L750–L842
- `def TestValidityInTheInterface.test_unknown_freshness_is_treated_as_expired` — L753–L763
- `def TestValidityInTheInterface.test_burned_and_fresh_look_different` — L765–L773
- `def TestValidityInTheInterface.test_the_trade_button_is_disabled_on_burned_signals` — L776–L793
- `def TestValidityInTheInterface.test_the_trade_button_stays_enabled_when_usable` — L796–L808
- `def TestValidityInTheInterface.test_both_signal_tables_have_a_validity_column` — L810–L824
- `def TestValidityInTheInterface.test_translations_exist_in_both_languages` — L826–L842
- `class TestNewSettings` — L850–L879
- `def TestNewSettings.test_the_new_keys_have_defaults` — L853–L862
- `def TestNewSettings.test_stale_signals_are_labelled_not_hidden_by_default` — L864–L873
- `def TestNewSettings.test_context_override_is_off_by_default` — L875–L879
- `class TestExplicitRecommendation` — L887–L1046
- `def TestExplicitRecommendation.test_a_plain_recommendation_line_is_read` — L895–L904
- `def TestExplicitRecommendation.test_markdown_bold_does_not_break_it` — L906–L918
- `def TestExplicitRecommendation.test_synonyms_are_understood` — L933–L941
- `def TestExplicitRecommendation.test_confidence_formats` — L944–L951
- `def TestExplicitRecommendation.test_a_missing_confidence_is_none_not_zero` — L953–L965
- `def TestExplicitRecommendation.test_the_last_line_wins` — L967–L981
- `def TestExplicitRecommendation.test_no_line_means_no_guessing` — L983–L994
- `def TestExplicitRecommendation.test_an_unrecognised_action_is_rejected` — L996–L1000
- `def TestExplicitRecommendation.test_wait_is_not_actionable` — L1002–L1013
- `def TestExplicitRecommendation.test_the_machine_line_is_hidden_from_the_user` — L1015–L1027
- `def TestExplicitRecommendation.test_the_prompt_demands_the_line` — L1029–L1036
- `def TestExplicitRecommendation.test_the_prompt_permits_wait` — L1038–L1046
- `class TestRecommendationInTheDialog` — L1049–L1120
- `def TestRecommendationInTheDialog._dialog` — L1053–L1059
- `def TestRecommendationInTheDialog.test_the_card_appears_when_a_recommendation_exists` — L1061–L1069
- `def TestRecommendationInTheDialog.test_no_card_without_a_recommendation` — L1071–L1079
- `def TestRecommendationInTheDialog.test_a_burned_signal_strikes_through_its_recommendation` — L1081–L1095
- `def TestRecommendationInTheDialog.test_a_fresh_signal_keeps_its_recommendation_bold` — L1097–L1105
- `def TestRecommendationInTheDialog.test_translations_exist` — L1107–L1120
- `class TestAnalystWiring` — L1123–L1134
- `def TestAnalystWiring.test_the_result_carries_a_recommendation_field` — L1126–L1134

### `tests/test_v196_fixes.py`

آزمون‌های نسخهٔ ۱.۹.۶ — سه گزارش کاربر از ماشین خودش.

ارجاع داخلی: `ai/local_model_fit.py`, `ai/providers/base.py`, `ai/providers/ollama_provider.py`, `app/config/defaults.py`, `app/exceptions/__init__.py`, `localization/__init__.py`, `signals/auto_scanner.py`, `ui/themes/catalog.py`.
- `class TestAutoScanCountdown` — L23–L101
- `def TestAutoScanCountdown._scheduler` — L33–L37
- `def TestAutoScanCountdown.test_a_fresh_scheduler_does_not_crash` — L39–L47
- `def TestAutoScanCountdown.test_never_run_means_due_now` — L49–L57
- `def TestAutoScanCountdown.test_a_normal_countdown_still_works` — L59–L66
- `def TestAutoScanCountdown.test_an_overdue_sweep_reports_zero` — L68–L73
- `def TestAutoScanCountdown.test_a_disabled_scheduler_reports_zero` — L75–L81
- `def TestAutoScanCountdown.test_every_combination_returns_a_usable_integer` — L85–L101
- `class FakeResponse` — L109–L119
- `def FakeResponse.__init__` — L112–L115
- `def FakeResponse.json` — L117–L119
- `class TestRunnerCrashDetection` — L130–L183
- `def TestRunnerCrashDetection.test_the_windows_message_is_recognised` — L139–L143
- `def TestRunnerCrashDetection.test_other_platforms_and_phrasings` — L155–L159
- `def TestRunnerCrashDetection.test_a_memory_error_is_not_a_runner_crash` — L161–L172
- `def TestRunnerCrashDetection.test_an_empty_body_is_not_a_runner_crash` — L174–L183
- `class TestRunnerCrashRecovery` — L186–L323
- `def TestRunnerCrashRecovery._provider` — L190–L203
- `async def TestRunnerCrashRecovery.test_a_transient_crash_is_retried_and_succeeds` — L206–L233
- `class TestRunnerCrashRecovery.test_a_transient_crash_is_retried_and_succeeds.FakeClient` — L216–L223
- `async def TestRunnerCrashRecovery.test_a_transient_crash_is_retried_and_succeeds.FakeClient.post` — L217–L223
- `async def TestRunnerCrashRecovery.test_retries_are_bounded` — L236–L262
- `class TestRunnerCrashRecovery.test_retries_are_bounded.AlwaysDead` — L248–L251
- `async def TestRunnerCrashRecovery.test_retries_are_bounded.AlwaysDead.post` — L249–L251
- `async def TestRunnerCrashRecovery.test_each_retry_asks_for_a_shorter_reply` — L265–L293
- `class TestRunnerCrashRecovery.test_each_retry_asks_for_a_shorter_reply.AlwaysDead` — L277–L282
- `async def TestRunnerCrashRecovery.test_each_retry_asks_for_a_shorter_reply.AlwaysDead.post` — L278–L282
- `async def TestRunnerCrashRecovery.test_the_error_message_is_actionable` — L296–L323
- `class TestRunnerCrashRecovery.test_the_error_message_is_actionable.AlwaysDead` — L305–L307
- `async def TestRunnerCrashRecovery.test_the_error_message_is_actionable.AlwaysDead.post` — L306–L307
- `async def _async` — L326–L328
- `class TestDefaultTheme` — L336–L383
- `def TestDefaultTheme.test_the_catalog_default_is_corporate_navy` — L339–L343
- `def TestDefaultTheme.test_the_default_theme_exists` — L345–L352
- `def TestDefaultTheme.test_both_settings_keys_agree` — L354–L362
- `def TestDefaultTheme.test_the_theme_is_named_in_both_languages` — L364–L371
- `def TestDefaultTheme.test_every_theme_still_loads` — L373–L383
- `class TestLocalModelFit` — L391–L546
- `def TestLocalModelFit.test_size_is_read_from_the_name` — L409–L413
- `def TestLocalModelFit.test_the_users_installed_models_are_not_falsely_flagged` — L415–L434
- `def TestLocalModelFit.test_genuinely_oversized_models_are_still_flagged` — L436–L445
- `def TestLocalModelFit.test_reasoning_models_need_more_room` — L447–L457
- `def TestLocalModelFit.test_reasoning_models_are_recognised` — L462–L466
- `def TestLocalModelFit.test_a_small_model_fits_comfortably` — L468–L472
- `def TestLocalModelFit.test_an_unparseable_name_makes_no_claim` — L474–L483
- `def TestLocalModelFit.test_suggestions_fit_the_machine` — L485–L491
- `def TestLocalModelFit.test_suggestions_prefer_the_largest_that_fits` — L493–L499
- `def TestLocalModelFit.test_no_reasoning_model_is_ever_suggested` — L501–L511
- `def TestLocalModelFit.test_a_tiny_machine_gets_no_false_hope` — L513–L517
- `def TestLocalModelFit.test_translations_exist_in_both_languages` — L519–L527
- `def TestLocalModelFit.test_the_warning_names_a_way_out` — L529–L546
- `class TestRequestShapeMatchesTheTerminal` — L554–L739
- `def TestRequestShapeMatchesTheTerminal._provider` — L571–L584
- `async def TestRequestShapeMatchesTheTerminal._capture` — L587–L601
- `class TestRequestShapeMatchesTheTerminal._capture.Recorder` — L591–L596
- `async def TestRequestShapeMatchesTheTerminal._capture.Recorder.post` — L592–L596
- `async def TestRequestShapeMatchesTheTerminal.test_a_short_chat_never_asks_for_a_different_window` — L604–L620
- `async def TestRequestShapeMatchesTheTerminal.test_a_short_chat_still_sends_temperature` — L623–L629
- `async def TestRequestShapeMatchesTheTerminal.test_the_model_is_kept_in_memory` — L632–L644
- `async def TestRequestShapeMatchesTheTerminal.test_a_large_prompt_is_trimmed_instead_of_widening_the_window` — L647–L664
- `async def TestRequestShapeMatchesTheTerminal.test_the_reply_budget_never_eats_the_window` — L667–L683
- `async def TestRequestShapeMatchesTheTerminal.test_the_reply_budget_stays_useful` — L686–L697
- `def TestRequestShapeMatchesTheTerminal.test_the_threshold_matches_ollamas_own_default` — L699–L708
- `async def TestRequestShapeMatchesTheTerminal.test_the_users_four_models_all_take_the_quiet_path` — L711–L739
- `class TestTheWindowNeverChangesMidSession` — L742–L904
- `def TestTheWindowNeverChangesMidSession._provider` — L759–L772
- `async def TestTheWindowNeverChangesMidSession._windows` — L775–L790
- `class TestTheWindowNeverChangesMidSession._windows.Recorder` — L779–L784
- `async def TestTheWindowNeverChangesMidSession._windows.Recorder.post` — L780–L784
- `def TestTheWindowNeverChangesMidSession._turn` — L793–L807
- `async def TestTheWindowNeverChangesMidSession.test_the_window_is_never_changed_once_it_is_set` — L810–L820
- `async def TestTheWindowNeverChangesMidSession.test_a_short_follow_up_keeps_the_locked_window` — L823–L837
- `async def TestTheWindowNeverChangesMidSession.test_a_quiet_session_is_also_constant` — L840–L853
- `async def TestTheWindowNeverChangesMidSession.test_the_locked_window_is_the_machine_ceiling` — L856–L870
- `async def TestTheWindowNeverChangesMidSession.test_requests_are_serialised` — L873–L904
- `class TestTheWindowNeverChangesMidSession.test_requests_are_serialised.Recorder` — L887–L895
- `async def TestTheWindowNeverChangesMidSession.test_requests_are_serialised.Recorder.post` — L888–L895
- `class TestOllamaSizesTheWindowNotUs` — L907–L1013
- `def TestOllamaSizesTheWindowNotUs._provider` — L923–L938
- `async def TestOllamaSizesTheWindowNotUs._options` — L941–L954
- `class TestOllamaSizesTheWindowNotUs._options.Recorder` — L944–L949
- `async def TestOllamaSizesTheWindowNotUs._options.Recorder.post` — L945–L949
- `async def TestOllamaSizesTheWindowNotUs.test_system_ram_never_decides_the_window` — L957–L972
- `async def TestOllamaSizesTheWindowNotUs.test_an_explicit_user_setting_is_still_honoured` — L975–L987
- `async def TestOllamaSizesTheWindowNotUs.test_the_pinned_value_never_changes_either` — L990–L999
- `async def TestOllamaSizesTheWindowNotUs.test_the_users_max_tokens_setting_still_applies` — L1002–L1013
- `class TestTheAppSurvivesADyingRunner` — L1016–L1147
- `def TestTheAppSurvivesADyingRunner._provider` — L1029–L1041
- `def TestTheAppSurvivesADyingRunner._crashing_client` — L1044–L1065
- `class TestTheAppSurvivesADyingRunner._crashing_client.Client` — L1047–L1063
- `async def TestTheAppSurvivesADyingRunner._crashing_client.Client.post` — L1048–L1063
- `async def TestTheAppSurvivesADyingRunner.test_a_crash_is_survived_by_shrinking_the_prompt` — L1068–L1089
- `async def TestTheAppSurvivesADyingRunner.test_the_prompt_actually_gets_smaller_each_attempt` — L1092–L1117
- `def TestTheAppSurvivesADyingRunner.test_the_normal_path_still_protects_the_system_prompt` — L1119–L1134
- `def TestTheAppSurvivesADyingRunner.test_the_rescue_path_may_trim_the_system_prompt` — L1136–L1147

### `tests/test_v200_event_driven_trading.py`

آزمون‌های نسخهٔ ۲.۰ — ترمینال رویدادمحور معاملهٔ خودکار.

ارجاع داخلی: `app/core/models.py`, `localization/__init__.py`, `tests/conftest.py`, `trading/ai_decider.py`, `trading/auto_trader.py`, `trading/price_cache.py`, `trading/trend_ladder.py`, `ui/controllers/main_controller.py`, `ui/pages/prediction_page.py`, `ui/pages/trades_page.py`.
- `def qt_app` — L37–L38
- `def translator` — L42–L45
- `class _Candidate` — L49–L60
- `class _Repo` — L63–L79
- `def _Repo.__init__` — L66–L69
- `def _Repo.open_trade` — L71–L75
- `def _Repo.close_trade` — L77–L79
- `def _report` — L82–L104
- `def _bullish_ladder` — L107–L116
- `class TestTickEngine` — L122–L213
- `def TestTickEngine.test_record_sets_all_three_timestamps` — L123–L135
- `def TestTickEngine.test_latency_metrics_present` — L137–L149
- `def TestTickEngine.test_missing_exchange_ts_is_honest` — L151–L157
- `def TestTickEngine.test_entry_uses_ask_for_long_and_bid_for_short` — L159–L170
- `def TestTickEngine.test_stale_detection` — L172–L181
- `def TestTickEngine.test_record_book_layers_bid_ask_only` — L183–L201
- `class TestTickEngine.test_record_book_layers_bid_ask_only._Book` — L188–L192
- `def TestTickEngine.test_dedupe_unchanged_tick` — L203–L213
- `class TestTrendLadder` — L219–L288
- `def TestTrendLadder.test_weighted_direction_prefers_higher_timeframes` — L220–L238
- `def TestTrendLadder.test_serious_conflict_blocks` — L240–L255
- `def TestTrendLadder.test_minor_friction_penalizes_not_blocks` — L257–L269
- `def TestTrendLadder.test_no_data_is_unknown_not_zero` — L271–L276
- `def TestTrendLadder.test_1m_direction_from_live_ticks` — L278–L288
- `class TestAIDecider` — L294–L387
- `def TestAIDecider._decide` — L295–L307
- `def TestAIDecider._fresh_engine` — L309–L314
- `def TestAIDecider.test_full_decision_has_quantile_tp_sl` — L316–L324
- `def TestAIDecider.test_no_trade_when_trend_conflicts` — L326–L335
- `def TestAIDecider.test_no_trade_when_stale` — L337–L341
- `def TestAIDecider.test_no_trade_when_spread_abnormal` — L343–L349
- `def TestAIDecider.test_no_trade_when_low_liquidity` — L351–L353
- `def TestAIDecider.test_no_trade_when_capacity_full` — L355–L362
- `def TestAIDecider.test_no_trade_when_neutral_prediction` — L364–L366
- `def TestAIDecider.test_leverage_scales_inverse_with_volatility` — L368–L373
- `def TestAIDecider.test_allocation_modes` — L375–L387
- `class TestAutoTraderLifecycle` — L393–L643
- `def TestAutoTraderLifecycle._trader` — L394–L415
- `async def TestAutoTraderLifecycle._trader.price_source` — L399–L403
- `def TestAutoTraderLifecycle.test_stop_loss_exits_on_tick_immediately` — L417–L442
- `async def TestAutoTraderLifecycle.test_stop_loss_exits_on_tick_immediately.scenario` — L424–L440
- `def TestAutoTraderLifecycle.test_take_profit_exits_on_tick` — L444–L461
- `async def TestAutoTraderLifecycle.test_take_profit_exits_on_tick.scenario` — L450–L459
- `def TestAutoTraderLifecycle.test_break_even_moves_stop_after_trigger` — L463–L475
- `def TestAutoTraderLifecycle.test_trailing_follows_price_and_never_recedes` — L477–L491
- `def TestAutoTraderLifecycle.test_timeout_fallback_without_ticks` — L493–L510
- `async def TestAutoTraderLifecycle.test_timeout_fallback_without_ticks.scenario` — L500–L508
- `def TestAutoTraderLifecycle.test_emergency_exit_closes_all` — L512–L527
- `async def TestAutoTraderLifecycle.test_emergency_exit_closes_all.scenario` — L518–L525
- `def TestAutoTraderLifecycle.test_signal_invalidation_closes_on_reversal` — L529–L545
- `async def TestAutoTraderLifecycle.test_signal_invalidation_closes_on_reversal.scenario` — L536–L543
- `def TestAutoTraderLifecycle.test_entry_guards_reject_with_reason` — L547–L568
- `async def TestAutoTraderLifecycle.test_entry_guards_reject_with_reason.scenario` — L554–L566
- `def TestAutoTraderLifecycle.test_trend_conflict_blocks_entry` — L570–L592
- `async def TestAutoTraderLifecycle.test_trend_conflict_blocks_entry.scenario` — L581–L590
- `def TestAutoTraderLifecycle.test_ai_candidate_keeps_quantile_levels` — L594–L621
- `async def TestAutoTraderLifecycle.test_ai_candidate_keeps_quantile_levels.scenario` — L602–L619
- `def TestAutoTraderLifecycle.test_selected_mode_filters_symbols` — L623–L632
- `def TestAutoTraderLifecycle.test_paper_mode_is_default_and_live_needs_phrase` — L634–L643
- `class TestTradesTerminalUI` — L649–L1057
- `def TestTradesTerminalUI.page` — L651–L658
- `def TestTradesTerminalUI.test_tabs_built` — L660–L662
- `def TestTradesTerminalUI.test_info_cards_exist` — L664–L673
- `def TestTradesTerminalUI.test_terminal_header_pills` — L675–L693
- `def TestTradesTerminalUI.test_opportunity_table_search_and_filter` — L695–L742
- `def TestTradesTerminalUI.test_opportunity_table_search_and_filter.symbols_visible` — L716–L720
- `def TestTradesTerminalUI.test_opportunity_manual_enter_signal` — L744–L761
- `def TestTradesTerminalUI.test_positions_table_never_shrinks` — L763–L784
- `def TestTradesTerminalUI.test_close_selected_position_signal` — L786–L805
- `def TestTradesTerminalUI.test_prediction_summary_and_ladder` — L807–L838
- `def TestTradesTerminalUI.test_tick_status_display` — L840–L852
- `def TestTradesTerminalUI.test_close_selected_position_signal` — L854–L873
- `def TestTradesTerminalUI.test_prediction_summary_and_ladder` — L875–L906
- `def TestTradesTerminalUI.test_mode_combo_and_selected_input` — L908–L919
- `def TestTradesTerminalUI.test_responsive_reflow` — L921–L937
- `def TestTradesTerminalUI.test_four_resolutions` — L940–L946
- `def TestTradesTerminalUI.test_chart_card_with_real_candles` — L948–L962
- `def TestTradesTerminalUI.test_timeframe_selector_signal` — L964–L972
- `def TestTradesTerminalUI.test_risk_panel_renders` — L974–L994
- `def TestTradesTerminalUI.test_config_panel_collapsible` — L996–L1002
- `def TestTradesTerminalUI.test_terminal_tabs_with_counts` — L1004–L1013
- `def TestTradesTerminalUI.test_auto_symbols_population_selects_first` — L1015–L1030
- `def TestTradesTerminalUI.test_set_auto_symbol_adds_missing_and_emits` — L1032–L1040
- `def TestTradesTerminalUI.test_history_tab_preserved` — L1042–L1047
- `def TestTradesTerminalUI.test_tables_have_toolbars` — L1049–L1052
- `def TestTradesTerminalUI.test_scroll_envelopes_terminal` — L1054–L1057
- `class TestPredictionDashboard` — L1063–L1174
- `def TestPredictionDashboard.page` — L1065–L1072
- `def TestPredictionDashboard._payload` — L1074–L1119
- `def TestPredictionDashboard.test_dashboard_renders_all_sections` — L1121–L1132
- `def TestPredictionDashboard.test_fan_chart_ignores_bad_points` — L1134–L1139
- `def TestPredictionDashboard.test_horizons_table_columns` — L1141–L1152
- `def TestPredictionDashboard.test_no_data_shows_empty_honestly` — L1154–L1158
- `def TestPredictionDashboard.test_responsive_rows_reflow` — L1160–L1168
- `def TestPredictionDashboard.test_retranslate_keeps_data` — L1170–L1174
- `class TestControllerWiring` — L1180–L1286
- `def TestControllerWiring.controller` — L1182–L1222
- `class TestControllerWiring.controller._Settings` — L1191–L1196
- `def TestControllerWiring.controller._Settings.__init__` — L1192–L1193
- `def TestControllerWiring.controller._Settings.get` — L1195–L1196
- `class TestControllerWiring.controller._Market` — L1198–L1207
- `def TestControllerWiring.controller._Market.add_ticker_listener` — L1203–L1204
- `async def TestControllerWiring.controller._Market.get_orderbook` — L1206–L1207
- `class TestControllerWiring.controller._App` — L1209–L1215
- `def TestControllerWiring.test_ensure_tick_engine_is_singleton` — L1224–L1227
- `def TestControllerWiring.test_market_ticker_flows_into_cache` — L1229–L1243
- `class TestControllerWiring.test_market_ticker_flows_into_cache._Ticker` — L1233–L1237
- `def TestControllerWiring.test_enrich_auto_prediction_injects_1m` — L1245–L1252
- `def TestControllerWiring.test_prediction_direction_from_cached_report` — L1254–L1266
- `class TestControllerWiring.test_prediction_direction_from_cached_report._Report` — L1255–L1257
- `def TestControllerWiring.test_prediction_direction_from_cached_report._Report.to_dict` — L1256–L1257
- `class TestControllerWiring.test_prediction_direction_from_cached_report._Engine` — L1259–L1261
- `def TestControllerWiring.test_prediction_direction_from_cached_report._Engine.report` — L1260–L1261
- `def TestControllerWiring.test_terminal_refresh_is_safe_without_market` — L1268–L1272
- `def TestControllerWiring.test_auto_timeframe_roundtrip` — L1274–L1279
- `def TestControllerWiring.test_opportunity_enter_without_engine_is_safe` — L1281–L1286

### `tests/test_v22_terminal_pro.py`

آزمون‌های نسخهٔ ۲.۲ — ترمینال حرفه‌ای معاملهٔ خودکار.

ارجاع داخلی: `localization/__init__.py`, `tests/conftest.py`, `ui/controllers/main_controller.py`, `ui/dialogs/trading_dialogs.py`, `ui/pages/trades_page.py`.
- `def qt_app` — L30–L31
- `def translator` — L35–L38
- `class _WatchCandidate` — L42–L60
- `class TestInfoCards` — L66–L91
- `def TestInfoCards.page` — L68–L75
- `def TestInfoCards.test_cards_have_icon_headers` — L77–L82
- `def TestInfoCards.test_daily_pnl_color_follows_sign` — L84–L91
- `class TestChartToolbar` — L97–L147
- `def TestChartToolbar.page` — L99–L106
- `def TestChartToolbar.test_indicator_menu_emits_state` — L108–L116
- `def TestChartToolbar.test_draw_tools_on_chart` — L118–L127
- `def TestChartToolbar.test_chart_type_switch` — L129–L134
- `def TestChartToolbar.test_screenshot_grab` — L136–L139
- `def TestChartToolbar.test_symbol_combo_has_icon_delegate` — L141–L147
- `class TestAIOpinion` — L153–L185
- `def TestAIOpinion.page` — L155–L162
- `def TestAIOpinion.test_button_emits_symbol` — L164–L170
- `def TestAIOpinion.test_no_symbol_notice` — L172–L179
- `def TestAIOpinion.test_set_ai_opinion` — L181–L185
- `class TestWatchScan` — L191–L250
- `def TestWatchScan.controller` — L193–L217
- `class TestWatchScan.controller._Settings` — L200–L205
- `def TestWatchScan.controller._Settings.__init__` — L201–L202
- `def TestWatchScan.controller._Settings.get` — L204–L205
- `class TestWatchScan.controller._Market` — L207–L208
- `class TestWatchScan.controller._App` — L210–L212
- `def TestWatchScan.test_watch_rows_respect_thresholds` — L219–L233
- `def TestWatchScan.test_watch_rows_sorted_and_capped` — L235–L243
- `def TestWatchScan.test_manual_enter_requires_engine` — L245–L250
- `class TestPositionsActions` — L256–L331
- `def TestPositionsActions.page` — L258–L265
- `def TestPositionsActions._row` — L267–L280
- `def TestPositionsActions.test_action_column_with_close_button` — L282–L290
- `def TestPositionsActions.test_detail_dialog_shows_fields_and_close` — L292–L306
- `def TestPositionsActions.test_symbol_click_opens_detail` — L308–L331
- `class TestPositionsActions.test_symbol_click_opens_detail._FakeDialog : QObject` — L313–L321
- `def TestPositionsActions.test_symbol_click_opens_detail._FakeDialog.__init__` — L316–L318
- `def TestPositionsActions.test_symbol_click_opens_detail._FakeDialog.exec` — L320–L321
- `class TestSymbolPicker` — L337–L420
- `def TestSymbolPicker.page` — L339–L346
- `def TestSymbolPicker.test_picker_dialog_check_and_search` — L348–L369
- `def TestSymbolPicker.test_page_picker_writeback` — L371–L400
- `class TestSymbolPicker.test_page_picker_writeback._FakePicker` — L376–L385
- `def TestSymbolPicker.test_page_picker_writeback._FakePicker.__init__` — L377–L379
- `def TestSymbolPicker.test_page_picker_writeback._FakePicker.exec` — L381–L382
- `def TestSymbolPicker.test_page_picker_writeback._FakePicker.checked_symbols` — L384–L385
- `def TestSymbolPicker.test_scanner_settings_dialog_roundtrip` — L402–L420

### `tools/build_apk.py`

ربات ساخت APK — نسخهٔ موبایل معامله‌گر هوشمند رمزارز.

واردکنندگان ایستا: `tests/test_v1912_mobile.py`.
- `class Step` — L39–L45
- `class ApkReport` — L49–L58
- `def ApkReport.succeeded` — L56–L58
- `def is_windows` — L61–L63
- `def has_wsl` — L66–L78
- `def wrap_for_platform` — L81–L90
- `def to_wsl_path` — L93–L103
- `def _run` — L106–L124
- `def check_environment` — L127–L146
- `def verify_math_equivalence` — L149–L170
- `def build_apk` — L173–L209
- `def build` — L212–L228
- `def main` — L231–L268

### `tools/build_doctor.py`

عیب‌یاب سازنده‌ها — می‌گوید دقیقاً چه چیزی کم است.

ارجاع داخلی: `tools/build_installer.py`.
واردکنندگان ایستا: `tests/test_v1913_ashna.py`.
- `class Check` — L37–L43
- `class DoctorReport` — L47–L71
- `def DoctorReport.failures` — L53–L55
- `def DoctorReport.healthy` — L58–L60
- `def DoctorReport.first_problem` — L63–L71
- `def _run` — L74–L85
- `def check_python` — L88–L97
- `def check_platform` — L100–L107
- `def check_dependencies` — L110–L125
- `def check_pyinstaller` — L128–L142
- `def check_spec_file` — L145–L155
- `def check_inno_setup` — L158–L177
- `def check_wsl` — L180–L202
- `def check_buildozer` — L205–L232
- `def check_scripts` — L235–L264
- `def check_disk_space` — L267–L286
- `def run_diagnosis` — L289–L302
- `def main` — L305–L333

### `tools/build_installer.py`

ربات ساخت فایل نصبی ویندوز — از سورس تا `setup.exe` با یک دستور.

واردکنندگان ایستا: `tests/test_v1911_build_and_update.py`, `tools/build_doctor.py`.
- `class BuildStep` — L49–L55
- `class BuildReport` — L59–L70
- `def BuildReport.succeeded` — L68–L70
- `def read_version` — L73–L86
- `def find_iscc` — L89–L100
- `def _iscc_from_registry` — L103–L130
- `def file_checksum` — L133–L139
- `def write_manifest` — L142–L162
- `def _run` — L165–L178
- `def build` — L181–L274
- `def main` — L277–L298

### `tools/ollama_doctor.py`

پزشک اولاما — تشخیص قطعی، روی دستگاه خود کاربر.

- `def _post` — L32–L45
- `def _get` — L48–L56
- `def _short` — L59–L62
- `def main` — L65–L189

### `tools/preview_shot.py`

ابزار توسعه: گرفتن تصویر از پنجرهٔ برنامه با دادهٔ نمونه.

ارجاع داخلی: `app/application.py`, `localization/__init__.py`, `ui/controllers/__init__.py`, `ui/themes/__init__.py`, `ui/windows/__init__.py`.

### `tools/set_ai_key.py`

ثبت کلید یک سرویس هوش مصنوعی به‌صورت رمزنگاری‌شده.

ارجاع داخلی: `app/application.py`.
- `def main` — L21–L51

### `tools/sweep_ui.py`

پویش همهٔ ترکیب‌های پوسته × زبان × صفحه، برای یافتن خطای ترسیم.

ارجاع داخلی: `app/application.py`, `localization/__init__.py`, `ui/controllers/__init__.py`, `ui/themes/__init__.py`, `ui/windows/__init__.py`.

### `trading/__init__.py`

لایهٔ معاملات — پویش اسکلپ و اجرای خودکار.


### `trading/ai_decider.py`

تصمیم‌ساز حالت AI Auto (خواستهٔ §۳ تسک).

ارجاع داخلی: `trading/price_cache.py`, `trading/trend_ladder.py`.
واردکنندگان ایستا: `tests/test_v200_event_driven_trading.py`, `ui/controllers/main_controller.py`.
- `class TradeDecision` — L38–L91
- `def TradeDecision.no_trade` — L55–L59
- `def TradeDecision.notional` — L62–L64
- `def TradeDecision.risk_reward` — L67–L73
- `def TradeDecision.to_dict` — L75–L91
- `def pick_horizon` — L94–L104
- `def direction_from_horizon` — L107–L114
- `class AICandidate` — L118–L150
- `class PortfolioState` — L154–L183
- `def PortfolioState.available_margin` — L167–L169
- `def PortfolioState.total_margin_cap` — L172–L174
- `def PortfolioState.to_dict` — L176–L183
- `def size_margin` — L186–L228
- `def suggest_leverage` — L231–L246
- `def decide` — L249–L386

### `trading/auto_trader.py`

موتور معاملهٔ خودکار — باز کردن، پایش و بستن خودکار معامله‌ها.

ارجاع داخلی: `app/logging/__init__.py`, `trading/micro_plan.py`.
واردکنندگان ایستا: `tests/test_v1914_scalp.py`, `tests/test_v1918_live_and_auto.py`, `tests/test_v1921_online_and_autotrade.py`, `tests/test_v1922_micro_speed.py`, `tests/test_v200_event_driven_trading.py`, `trading/execution.py`, `trading/scalp_service.py`, `ui/controllers/main_controller.py`, `ui/pages/trades_page.py`.
- `class LiveTradingNotEnabledError : RuntimeError` — L62–L63
- `class LiveOrderGateway` — L66–L110
- `def LiveOrderGateway.__init__` — L75–L77
- `async def LiveOrderGateway.open_position` — L79–L94
- `async def LiveOrderGateway.close_position` — L96–L110
- `class AutoTradeConfig` — L114–L255
- `def AutoTradeConfig.validated` — L179–L219
- `def AutoTradeConfig.is_live` — L222–L231
- `def AutoTradeConfig.notional` — L234–L236
- `def AutoTradeConfig.selected_symbol_list` — L239–L247
- `def AutoTradeConfig.target_percent` — L249–L251
- `def AutoTradeConfig.stop_percent` — L253–L255
- `class ManagedTrade` — L259–L394
- `def ManagedTrade.__post_init__` — L292–L297
- `def ManagedTrade.is_long` — L300–L302
- `def ManagedTrade.direction_sign` — L305–L307
- `def ManagedTrade.unrealised` — L309–L311
- `def ManagedTrade.used_margin` — L313–L317
- `def ManagedTrade.mark` — L319–L365
- `def ManagedTrade.should_close` — L367–L388
- `def ManagedTrade.data_age_ms` — L390–L394
- `class AutoTrader` — L397–L1211
- `def AutoTrader.__init__` — L411–L447
- `def AutoTrader.apply_config` — L449–L456
- `def AutoTrader.attach_tick_engine` — L458–L466
- `def AutoTrader.is_running` — L471–L473
- `def AutoTrader.open_trades` — L476–L478
- `def AutoTrader.realised_today` — L481–L483
- `def AutoTrader.halted_reason` — L486–L488
- `def AutoTrader.opportunities` — L490–L492
- `def AutoTrader.portfolio` — L494–L520
- `def AutoTrader.add_listener` — L522–L524
- `def AutoTrader._emit` — L526–L536
- `def AutoTrader._on_tick` — L540–L565
- `def AutoTrader._schedule_tick_check` — L567–L573
- `def AutoTrader._exit_price_for` — L575–L587
- `async def AutoTrader.check_symbol` — L589–L598
- `async def AutoTrader._price_for_entry` — L600–L629
- `async def AutoTrader._price_for_exit` — L631–L646
- `def AutoTrader._check_daily_limit` — L650–L661
- `def AutoTrader._is_stale` — L663–L670
- `def AutoTrader._notify_stale_if_new` — L672–L678
- `def AutoTrader._check_entry_guards` — L680–L720
- `def AutoTrader._allowed_symbols` — L722–L732
- `def AutoTrader.preflight` — L734–L753
- `def AutoTrader._resolve_margin` — L757–L791
- `async def AutoTrader.open_trade` — L793–L919
- `def AutoTrader.open_trade.reject` — L806–L808
- `async def AutoTrader.close_trade` — L921–L957
- `async def AutoTrader.check_open_trades` — L959–L973
- `async def AutoTrader.check_signal_invalidation` — L975–L993
- `async def AutoTrader.emergency_exit_all` — L995–L1002
- `def AutoTrader._record_opportunity` — L1006–L1067
- `def AutoTrader._optional_number` — L1070–L1079
- `def AutoTrader.opportunity_candidate` — L1081–L1089
- `def AutoTrader.note_rejected` — L1091–L1119
- `class AutoTrader.note_rejected._Row` — L1109–L1110
- `async def AutoTrader._scan_for_entries` — L1121–L1136
- `async def AutoTrader._loop` — L1138–L1165
- `async def AutoTrader.start` — L1167–L1184
- `async def AutoTrader.stop` — L1186–L1202
- `async def AutoTrader.close_all` — L1204–L1211

### `trading/confidence_source.py`

انتخاب نماد برای معاملهٔ خودکار بر پایهٔ **درصد اطمینان سیگنال**.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `tests/test_v1921_online_and_autotrade.py`, `ui/controllers/main_controller.py`.
- `class ConfidenceCandidate` — L33–L53
- `def ConfidenceCandidate.confidence` — L51–L53
- `class ConfidenceCandidateSource` — L56–L166
- `def ConfidenceCandidateSource.__init__` — L65–L67
- `def ConfidenceCandidateSource.min_confidence` — L73–L80
- `def ConfidenceCandidateSource.scan_symbols` — L83–L85
- `async def ConfidenceCandidateSource.scan` — L90–L122
- `def ConfidenceCandidateSource._to_candidate` — L124–L166

### `trading/execution.py`

ساخت درگاه سفارش واقعی، بدون حدس‌زدن بدنهٔ سفارش صرافی.

ارجاع داخلی: `trading/auto_trader.py`.
واردکنندگان ایستا: `tests/test_v1922_micro_speed.py`, `ui/controllers/main_controller.py`.
- `def build_gateway` — L15–L24

### `trading/micro_plan.py`

محاسبهٔ سود خالص اسکالپ خیلی کوتاه، بعد از کارمزد.

واردکنندگان ایستا: `tests/test_v1922_micro_speed.py`, `trading/auto_trader.py`, `ui/controllers/main_controller.py`.
- `class MicroPlan` — L27–L48
- `def MicroPlan.entry_fee` — L41–L43
- `def MicroPlan.exit_fee` — L46–L48
- `def plan_levels` — L51–L86
- `def exit_fee_from_notional` — L89–L94

### `trading/price_cache.py`

کش قیمت تیک‌محور — قلب معماری رویدادمحور معامله‌گری.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `tests/test_v200_event_driven_trading.py`, `trading/ai_decider.py`, `ui/controllers/main_controller.py`.
- `def _now_ms` — L45–L47
- `def _parse_exchange_ms` — L50–L68
- `class TickQuote` — L72–L187
- `def TickQuote.spread` — L90–L94
- `def TickQuote.spread_percent` — L97–L102
- `def TickQuote.mid` — L105–L109
- `def TickQuote.receive_latency_ms` — L112–L116
- `def TickQuote.processing_latency_ms` — L119–L123
- `def TickQuote.total_latency_ms` — L126–L130
- `def TickQuote.age_ms` — L133–L137
- `def TickQuote.exit_price` — L139–L149
- `def TickQuote.entry_price` — L151–L162
- `def TickQuote.to_dict` — L164–L187
- `class TickEngine` — L190–L396
- `def TickEngine.__init__` — L198–L206
- `def TickEngine.record` — L211–L282
- `def TickEngine.record_book` — L284–L311
- `def TickEngine.get` — L316–L318
- `def TickEngine.price` — L320–L323
- `def TickEngine.history` — L325–L332
- `def TickEngine.is_stale` — L334–L345
- `def TickEngine.stale_symbols` — L347–L349
- `def TickEngine.add_listener` — L354–L357
- `def TickEngine.remove_listener` — L359–L362
- `def TickEngine._notify` — L364–L370
- `def TickEngine.stats` — L375–L396

### `trading/scalp_scanner.py`

پویشگر اسکلپ — یافتن ارزهایی که همین حالا فرصت کوتاه‌مدت دارند.

ارجاع داخلی: `app/core/models.py`.
واردکنندگان ایستا: `tests/test_v1914_scalp.py`, `trading/scalp_service.py`.
- `class ScalpCandidate` — L52–L86
- `def ScalpCandidate.projected_profit` — L68–L75
- `def ScalpCandidate.required_move_percent` — L77–L86
- `def _percentile` — L89–L95
- `def recent_volatility` — L98–L112
- `def momentum_percent` — L115–L121
- `def passes_liquidity` — L124–L131
- `def spread_from_orderbook` — L134–L157
- `def score_candidate` — L160–L222
- `def rank_candidates` — L225–L227
- `def prefilter_symbols` — L230–L253
- `def feasibility_note` — L256–L286

### `trading/scalp_service.py`

سرویس اسکلپ — چسبِ میان پویشگر، هوش مصنوعی و موتور معامله.

ارجاع داخلی: `ai/providers/base.py`, `app/logging/__init__.py`, `trading/auto_trader.py`, `trading/scalp_scanner.py`.
واردکنندگان ایستا: `tests/test_v1914_scalp.py`, `ui/controllers/main_controller.py`.
- `class ScalpService` — L61–L265
- `def ScalpService.__init__` — L64–L65
- `def ScalpService._setting` — L69–L74
- `async def ScalpService.scan` — L78–L130
- `async def ScalpService.scan.evaluate` — L100–L114
- `async def ScalpService._ai_review` — L134–L198
- `def ScalpService._parse_ai_verdicts` — L201–L236
- `def ScalpService.feasibility` — L240–L247
- `def ScalpService.build_trader_config` — L249–L265

### `trading/trade_monitor.py`

پایش زندهٔ معاملات باز.

واردکنندگان ایستا: `tests/test_v1917_trust_and_trades.py`, `ui/controllers/main_controller.py`.
- `class LivePosition` — L29–L86
- `def LivePosition.is_long` — L42–L44
- `def LivePosition.unrealised` — L46–L64
- `def LivePosition.should_close` — L66–L86
- `def position_from_record` — L89–L136
- `def position_from_record._get` — L97–L100
- `def position_from_record._optional` — L111–L119
- `def evaluate` — L139–L174

### `trading/trend_ladder.py`

هستهٔ روند اسکلپ — نردبان چندتایم‌فریمی (خواستهٔ §۴ تسک).

واردکنندگان ایستا: `tests/test_v200_event_driven_trading.py`, `trading/ai_decider.py`, `ui/controllers/main_controller.py`.
- `class LadderStep` — L33–L44
- `def LadderStep.known` — L42–L44
- `class TrendLadder` — L48–L135
- `def TrendLadder.step` — L54–L56
- `def TrendLadder.regime_4h` — L59–L61
- `def TrendLadder.main_trend_1h` — L64–L66
- `def TrendLadder.known_steps` — L69–L71
- `def TrendLadder.weighted_direction` — L74–L90
- `def TrendLadder.has_data` — L93–L95
- `def TrendLadder.conflict_with` — L97–L110
- `def TrendLadder.minor_friction` — L112–L119
- `def TrendLadder.to_dict` — L121–L135
- `def step_from_regime` — L138–L157
- `def _direction_from_name` — L160–L169
- `def build_ladder` — L172–L196
- `def _direction_from_1m` — L199–L224
- `def conflict_verdict` — L227–L248

### `ui/__init__.py`

لایه رابط کاربری (PySide6).


### `ui/charts/__init__.py`

ماژول نمودارها.

ارجاع داخلی: `ui/charts/candlestick_item.py`, `ui/charts/price_chart.py`.
واردکنندگان ایستا: `ui/pages/analysis_page.py`, `ui/pages/trades_page.py`.

### `ui/charts/candlestick_item.py`

آیتم نمودار شمعی برای pyqtgraph.

ارجاع داخلی: `app/core/models.py`.
واردکنندگان ایستا: `ui/charts/__init__.py`, `ui/charts/price_chart.py`.
- `class CandlestickItem : GraphicsObject` — L19–L117
- `def CandlestickItem.__init__` — L28–L41
- `def CandlestickItem.set_data` — L46–L53
- `def CandlestickItem.set_colors` — L55–L60
- `def CandlestickItem.candles` — L63–L65
- `def CandlestickItem._generate_picture` — L70–L101
- `def CandlestickItem.paint` — L103–L104
- `def CandlestickItem.boundingRect` — L106–L114
- `def CandlestickItem.shape` — L116–L117

### `ui/charts/price_chart.py`

ویجت نمودار قیمت.

ارجاع داخلی: `app/core/models.py`, `app/logging/__init__.py`, `localization/__init__.py`, `market/timeframes.py`, `ui/charts/candlestick_item.py`.
واردکنندگان ایستا: `tests/test_v1918_live_and_auto.py`, `ui/charts/__init__.py`, `ui/controllers/main_controller.py`.
- `class TimeAxis : pg.AxisItem` — L31–L56
- `def TimeAxis.__init__` — L39–L41
- `def TimeAxis.set_format` — L43–L46
- `def TimeAxis.tickStrings` — L48–L56
- `class PriceChart : QWidget` — L59–L516
- `def PriceChart.__init__` — L70–L164
- `def PriceChart.set_candles` — L169–L215
- `def PriceChart.set_overlay` — L217–L241
- `def PriceChart.remove_overlay` — L243–L247
- `def PriceChart.set_levels` — L249–L268
- `def PriceChart.mark_signal` — L270–L297
- `def PriceChart._on_manual_range` — L302–L304
- `def PriceChart.set_draw_mode` — L309–L322
- `def PriceChart.draw_count` — L324–L326
- `def PriceChart.clear_drawings` — L328–L337
- `def PriceChart._add_hline` — L339–L348
- `def PriceChart._add_trend` — L350–L357
- `def PriceChart._on_chart_clicked` — L359–L377
- `def PriceChart.screenshot_pixmap` — L379–L381
- `def PriceChart.reset_zoom` — L383–L387
- `def PriceChart.set_chart_type` — L389–L396
- `def PriceChart._apply_chart_type` — L398–L409
- `def PriceChart.set_live_price` — L411–L438
- `def PriceChart.clear` — L440–L448
- `def PriceChart.show_placeholder` — L450–L454
- `def PriceChart.apply_palette` — L456–L471
- `def PriceChart.retranslate` — L473–L476
- `def PriceChart._clear_levels` — L481–L485
- `def PriceChart._clear_signal_lines` — L487–L491
- `def PriceChart._on_mouse_moved` — L493–L516

### `ui/controllers/__init__.py`

لایه کنترلر — پل میان صفحات رابط گرافیکی و موتورهای برنامه.

ارجاع داخلی: `ui/controllers/async_runner.py`, `ui/controllers/main_controller.py`.
واردکنندگان ایستا: `main.py`, `tools/preview_shot.py`, `tools/sweep_ui.py`.

### `ui/controllers/async_runner.py`

اجرای کارهای ناهمگام بدون قفل شدن رابط گرافیکی.

ارجاع داخلی: `app/exceptions/__init__.py`, `app/logging/__init__.py`.
واردکنندگان ایستا: `tests/test_async_runner.py`, `tests/test_v153_fixes.py`, `tests/test_v155_ui_and_ai.py`, `ui/controllers/__init__.py`, `ui/controllers/main_controller.py`.
- `class TaskHandle : QObject` — L30–L59
- `def TaskHandle.__init__` — L42–L45
- `def TaskHandle.cancel` — L47–L54
- `def TaskHandle.cancelled` — L57–L59
- `class AsyncRunner : QObject` — L62–L259
- `def AsyncRunner.__init__` — L73–L81
- `def AsyncRunner.start` — L86–L94
- `def AsyncRunner._run_loop` — L96–L112
- `def AsyncRunner.stop` — L114–L127
- `def AsyncRunner.running` — L130–L132
- `def AsyncRunner.submit` — L137–L194
- `def AsyncRunner._release` — L196–L201
- `def AsyncRunner.cancel` — L203–L222
- `def AsyncRunner.active_keys` — L224–L227
- `def AsyncRunner.run_blocking` — L229–L237
- `async def AsyncRunner.run_blocking._call` — L234–L235
- `async def AsyncRunner._wrap` — L239–L259

### `ui/controllers/main_controller.py`

کنترلر اصلی رابط گرافیکی.

ارجاع داخلی: `ai/ollama_doctor.py`, `ai/recommendation.py`, `app/application.py`, `app/config/defaults.py`, `app/core/constants.py`, `app/core/models.py`, `app/core/paths.py`, `app/core/timeutil.py`, `app/core/updater.py`, `app/logging/__init__.py`, `indicators/support_resistance.py`, `indicators/trend.py`, `indicators/volatility.py`, `localization/__init__.py`, `market/fiat_rates.py`, `market/live_feed.py`, `market/providers/registry.py`, `market/resilience.py`, `reports/persian_pdf.py`, `signals/alerts.py`, `signals/auto_scanner.py`, `signals/paper_trader.py`, `signals/validity.py`, `trading/ai_decider.py`, `trading/auto_trader.py`, `trading/confidence_source.py`, `trading/execution.py`, `trading/micro_plan.py`, `trading/price_cache.py`, `trading/scalp_service.py`, `trading/trade_monitor.py`, `trading/trend_ladder.py`, `ui/charts/price_chart.py`, `ui/controllers/async_runner.py`, `ui/dialogs/__init__.py`, `ui/dialogs/analysis_dialog.py`, `ui/dialogs/coin_detail_dialog.py`, `ui/dialogs/signal_detail_dialog.py`, `ui/themes/__init__.py`, `ui/themes/catalog.py`, `ui/themes/custom.py`, `ui/themes/fonts.py`, `ui/widgets/__init__.py`, `ui/windows/__init__.py`.
واردکنندگان ایستا: `tests/test_exchange_login_flow.py`, `tests/test_exchange_switching.py`, `tests/test_v155_ui_and_ai.py`, `tests/test_v156_fixes.py`, `tests/test_v158_security_tab.py`, `tests/test_v160_error_keys.py`, `tests/test_v162_modal_close.py`, `tests/test_v171_chat_tool_steps.py`, `tests/test_v172_signal_ai_and_scan_ui.py`, `tests/test_v180_ai_status_card.py`, `tests/test_v1915_bugfixes.py`, `tests/test_v1916_ai_wait.py`, `tests/test_v1918_alerts.py`, `tests/test_v1918_live_and_auto.py`, `tests/test_v1918_scorecard.py`, `tests/test_v200_event_driven_trading.py`, `tests/test_v22_terminal_pro.py`, `ui/controllers/__init__.py`.
- `def _dialog_alive` — L49–L62
- `class MainController : QObject` — L131–L7410
- `def MainController.__init__` — L157–L242
- `def MainController._connect` — L247–L418
- `def MainController.start` — L420–L449
- `def MainController.shutdown` — L451–L488
- `def MainController._on_engines_ready` — L490–L528
- `def MainController._start_live_feed` — L533–L567
- `def MainController._update_streamed_symbols` — L569–L590
- `def MainController._stream_symbols` — L592–L629
- `async def MainController._sync_streams` — L631–L643
- `def MainController._on_price_update` — L645–L663
- `def MainController._flush_live_updates` — L665–L684
- `def MainController._apply_dashboard_prices` — L686–L702
- `def MainController._refresh_connection_indicator` — L704–L747
- `def MainController.save_dashboard_layout` — L752–L761
- `def MainController.restore_dashboard_layout` — L763–L767
- `def MainController.open_ai_settings` — L769–L772
- `def MainController.refresh_ai_status` — L774–L835
- `async def MainController.refresh_ai_status.probe` — L797–L802
- `def MainController.refresh_ai_status.apply` — L804–L815
- `def MainController.refresh_ai_status.failed` — L817–L827
- `def MainController.refresh_fiat_rate` — L840–L871
- `async def MainController.refresh_fiat_rate.fetch` — L853–L855
- `def MainController.refresh_fiat_rate.apply` — L857–L864
- `def MainController._apply_timezone_setting` — L873–L876
- `def MainController.refresh_dashboard` — L881–L974
- `async def MainController.refresh_dashboard.collect` — L888–L936
- `def MainController.refresh_dashboard.apply` — L938–L965
- `def MainController.refresh_markets` — L979–L1043
- `async def MainController.refresh_markets.collect` — L985–L1002
- `def MainController.refresh_markets.apply` — L1004–L1034
- `def MainController.add_to_watchlist` — L1045–L1055
- `def MainController._on_watchlist_toggled` — L1057–L1078
- `def MainController.refresh_watchlist_panel` — L1083–L1105
- `def MainController._on_watchlist_list_selected` — L1107–L1110
- `def MainController._create_watchlist` — L1112–L1126
- `def MainController._rename_watchlist` — L1128–L1136
- `def MainController._delete_watchlist` — L1138–L1163
- `def MainController._move_watchlist_symbol` — L1165–L1172
- `def MainController._remove_watchlist_symbol` — L1174–L1181
- `def MainController._save_watchlist_note` — L1183–L1192
- `def MainController._open_watchlist_symbol` — L1194–L1200
- `def MainController._on_market_double_clicked` — L1202–L1209
- `def MainController._watchlist_symbols` — L1211–L1222
- `def MainController._populate_indicator_catalog` — L1227–L1251
- `def MainController._on_analysis_activated` — L1253–L1268
- `def MainController._on_indicator_toggled` — L1270–L1274
- `def MainController.run_analysis` — L1276–L1379
- `async def MainController.run_analysis.analyse` — L1294–L1313
- `def MainController.run_analysis.apply` — L1315–L1371
- `def MainController._sync_prediction_symbol` — L1381–L1383
- `def MainController.run_prediction_report` — L1385–L1430
- `async def MainController.run_prediction_report.compute` — L1404–L1410
- `def MainController.run_prediction_report.apply` — L1412–L1422
- `def MainController._run_ai_analysis` — L1432–L1462
- `def MainController._run_ai_analysis.apply` — L1446–L1450
- `def MainController._run_ai_analysis.failed` — L1452–L1455
- `def MainController._format_agent_outcome` — L1464–L1500
- `def MainController._overlay_series` — L1503–L1518
- `def MainController._format_latest` — L1521–L1530
- `def MainController.generate_signal` — L1535–L1604
- `def MainController.generate_signal.apply` — L1568–L1596
- `def MainController.scan_market` — L1606–L1671
- `def MainController.scan_market.on_progress` — L1624–L1629
- `def MainController.scan_market.apply` — L1631–L1651
- `def MainController.scan_market.on_error` — L1653–L1656
- `def MainController.start_auto_scanner` — L1676–L1708
- `def MainController.save_auto_scan_config` — L1710–L1720
- `def MainController.run_auto_scan_now` — L1722–L1742
- `def MainController._auto_scan_tick` — L1744–L1760
- `def MainController._execute_auto_job` — L1762–L1819
- `def MainController._execute_auto_job.apply` — L1782–L1798
- `def MainController._execute_auto_job.failed` — L1800–L1806
- `def MainController._notify_auto_signals` — L1821–L1853
- `def MainController._refresh_auto_scan_status` — L1855–L1878
- `def MainController._format_duration` — L1880–L1896
- `def MainController._note_market_offline` — L1901–L1915
- `def MainController._note_market_online` — L1917–L1921
- `def MainController.start_live_chart` — L1923–L1944
- `def MainController._live_price_tick` — L1946–L1984
- `async def MainController._live_price_tick.fetch` — L1967–L1969
- `def MainController._live_price_tick.apply` — L1971–L1976
- `def MainController._live_chart_tick` — L1986–L2027
- `async def MainController._live_chart_tick.fetch` — L2009–L2014
- `def MainController._live_chart_tick.apply` — L2016–L2019
- `def MainController.start_trade_monitor` — L2029–L2043
- `def MainController._trade_monitor_tick` — L2045–L2139
- `async def MainController._trade_monitor_tick.fetch` — L2076–L2093
- `def MainController._trade_monitor_tick.apply` — L2095–L2128
- `def MainController._trade_monitor_tick.finished` — L2130–L2131
- `def MainController.start_outcome_tracker` — L2141–L2165
- `def MainController._outcome_tick` — L2167–L2176
- `def MainController._alert_book` — L2181–L2185
- `def MainController._save_alert_book` — L2187–L2194
- `def MainController.create_price_alert` — L2196–L2239
- `def MainController._run_alert_check` — L2241–L2293
- `async def MainController._run_alert_check.fetch` — L2261–L2274
- `async def MainController._run_alert_check.fetch.one` — L2265–L2271
- `def MainController._run_alert_check.apply` — L2276–L2286
- `def MainController.check_signal_alerts` — L2295–L2316
- `def MainController._run_outcome_check` — L2318–L2362
- `def MainController._run_outcome_check.apply` — L2329–L2350
- `def MainController._run_outcome_check.failed` — L2352–L2355
- `def MainController._run_signal_review` — L2364–L2389
- `def MainController._run_signal_review.done` — L2377–L2379
- `def MainController._run_signal_review.failed` — L2381–L2382
- `def MainController.refresh_scorecard` — L2391–L2426
- `def MainController.refresh_scorecard.apply` — L2403–L2410
- `def MainController.refresh_scorecard.failed` — L2412–L2414
- `def MainController.refresh_scorecard.finished` — L2416–L2418
- `def MainController.refresh_outcomes_now` — L2428–L2431
- `def MainController._refresh_outcome_view` — L2433–L2453
- `def MainController._outcome_row` — L2455–L2473
- `def MainController.stop_market_scan` — L2475–L2480
- `def MainController.analyze_scanned_symbol` — L2482–L2546
- `def MainController.analyze_scanned_symbol.apply` — L2512–L2539
- `def MainController.show_scanned_signal_detail` — L2548–L2579
- `def MainController._generate_ai_signal` — L2581–L2684
- `def MainController._generate_ai_signal.on_step` — L2609–L2612
- `def MainController._generate_ai_signal.apply` — L2616–L2645
- `def MainController._generate_ai_signal.finished` — L2647–L2650
- `async def MainController._generate_ai_signal.analyse` — L2652–L2676
- `def MainController._go_to` — L2689–L2700
- `def MainController._streaming_chat_enabled` — L2702–L2709
- `def MainController.send_chat_message` — L2711–L2791
- `def MainController.send_chat_message.on_tool` — L2733–L2744
- `def MainController.send_chat_message.apply` — L2757–L2778
- `def MainController._on_chat_action` — L2793–L2831
- `def MainController._on_chat_tool_started` — L2833–L2835
- `def MainController._on_chat_tool_finished` — L2837–L2843
- `def MainController._on_chat_cleared` — L2845–L2853
- `def MainController.load_conversations` — L2858–L2870
- `def MainController.start_new_conversation` — L2872–L2879
- `def MainController.open_conversation` — L2881–L2896
- `def MainController.delete_conversation` — L2898–L2917
- `def MainController.rename_conversation` — L2919–L2924
- `def MainController._ensure_conversation` — L2926–L2942
- `def MainController._store_chat_message` — L2944–L2971
- `def MainController.show_coin_details` — L2976–L3017
- `def MainController.show_coin_details._act` — L3001–L3004
- `def MainController._load_coin_details` — L3019–L3073
- `async def MainController._load_coin_details.collect` — L3026–L3044
- `def MainController._load_coin_details.apply` — L3046–L3059
- `def MainController._load_coin_details._safe_details_error` — L3061–L3066
- `def MainController._summarise_candles` — L3075–L3104
- `def MainController._coin_analyze` — L3106–L3113
- `def MainController._coin_signal` — L3115–L3122
- `def MainController._coin_chat` — L3124–L3127
- `def MainController._coin_open_market` — L3129–L3132
- `def MainController._coin_watchlist_toggled` — L3134–L3150
- `def MainController.show_signal_analysis` — L3155–L3176
- `def MainController._rerun_signal_analysis` — L3178–L3237
- `def MainController._rerun_signal_analysis.done` — L3206–L3225
- `def MainController._rerun_signal_analysis.failed` — L3227–L3230
- `def MainController._export_analysis_pdf` — L3239–L3301
- `def MainController._split_analysis_sections` — L3304–L3327
- `def MainController._agent_outcome_is_usable` — L3330–L3367
- `def MainController._fallback_to_engine_signal` — L3369–L3433
- `def MainController._fallback_to_engine_signal.apply` — L3392–L3413
- `def MainController._agent_outcome_to_signal` — L3435–L3457
- `def MainController._save_agent_signal` — L3459–L3489
- `def MainController._decorate_validity` — L3491–L3540
- `def MainController._apply_stale_filter` — L3542–L3559
- `def MainController._load_signal_history` — L3561–L3590
- `def MainController._on_signal_cell_clicked` — L3595–L3597
- `def MainController._on_history_double_clicked` — L3599–L3601
- `def MainController._open_signal_detail` — L3603–L3630
- `def MainController._prime_calculator` — L3632–L3647
- `def MainController._load_signal_detail` — L3649–L3688
- `def MainController._analysis_payload` — L3690–L3712
- `def MainController._review_payload` — L3714–L3732
- `def MainController._on_trade_requested` — L3734–L3794
- `def MainController._paper_trader` — L3796–L3802
- `def MainController.generate_report` — L3807–L3836
- `def MainController.generate_report.build` — L3814–L3818
- `def MainController.generate_report.apply` — L3820–L3828
- `def MainController._apply_performance_settings` — L3841–L3850
- `def MainController._apply_display_settings` — L3852–L3859
- `def MainController.save_settings` — L3861–L3908
- `def MainController.apply_exchange_switch` — L3910–L3943
- `def MainController.apply_exchange_switch.done` — L3919–L3931
- `def MainController.apply_exchange_switch.failed` — L3933–L3936
- `def MainController._on_exchange_selected` — L3945–L3957
- `def MainController._on_ai_provider_selected` — L3959–L3964
- `def MainController.test_ai_connection` — L3966–L4001
- `async def MainController.test_ai_connection.check` — L3980–L3985
- `def MainController.test_ai_connection.apply` — L3987–L3991
- `def MainController.check_for_update` — L4003–L4046
- `def MainController.check_for_update.apply` — L4022–L4036
- `def MainController.install_update` — L4048–L4098
- `def MainController.install_update.apply` — L4075–L4089
- `def MainController.run_ollama_doctor` — L4100–L4162
- `def MainController.run_ollama_doctor.apply` — L4123–L4152
- `def MainController.load_ai_models` — L4164–L4214
- `async def MainController.load_ai_models.fetch` — L4172–L4180
- `def MainController.load_ai_models.apply` — L4182–L4204
- `def MainController._persist_ai_settings` — L4216–L4225
- `def MainController.create_backup` — L4227–L4240
- `def MainController.create_backup.run` — L4230–L4232
- `def MainController.create_backup.apply` — L4234–L4238
- `def MainController.restore_backup` — L4242–L4277
- `def MainController.change_language` — L4282–L4294
- `def MainController._rerender_dynamic_content` — L4296–L4310
- `def MainController._on_font_scale_changed` — L4312–L4321
- `def MainController._on_compact_mode_changed` — L4323–L4327
- `def MainController._on_theme_combo_changed` — L4329–L4338
- `def MainController.change_theme` — L4340–L4366
- `def MainController.preview_theme_tokens` — L4371–L4401
- `def MainController._apply_theme_tokens` — L4403–L4420
- `def MainController.save_custom_theme` — L4422–L4457
- `def MainController.delete_custom_theme` — L4459–L4485
- `def MainController._sync_theme_editor` — L4487–L4507
- `def MainController.change_font_family` — L4509–L4521
- `def MainController.apply_display_preferences` — L4523–L4540
- `def MainController._update_dashboard_stats` — L4542–L4576
- `def MainController._compact_number` — L4578–L4587
- `def MainController.show_auth_dialog` — L4592–L4604
- `def MainController.logout` — L4606–L4610
- `def MainController._on_user_changed` — L4612–L4628
- `def MainController.refresh_accounts` — L4633–L4642
- `def MainController.refresh_security` — L4647–L4679
- `def MainController._session_row` — L4681–L4695
- `def MainController._is_expired` — L4698–L4710
- `def MainController.save_email_settings` — L4712–L4734
- `def MainController.test_email_connection` — L4736–L4759
- `async def MainController.test_email_connection.probe` — L4744–L4747
- `def MainController.test_email_connection.done` — L4749–L4754
- `def MainController.test_email_connection.failed` — L4756–L4757
- `def MainController.save_profile` — L4761–L4781
- `def MainController.change_password` — L4783–L4810
- `def MainController.revoke_session` — L4812–L4824
- `def MainController.revoke_other_sessions` — L4826–L4843
- `def MainController.add_exchange_account` — L4845–L4874
- `def MainController.test_exchange_account` — L4876–L4886
- `def MainController.activate_exchange_account` — L4888–L4907
- `def MainController.remove_exchange_account` — L4909–L4920
- `def MainController._localize_exchange_message` — L4922–L4934
- `def MainController._on_account_tested` — L4936–L4949
- `def MainController._wallet_price_lookup` — L4951–L4994
- `async def MainController._wallet_price_lookup.price_lookup` — L4959–L4992
- `def MainController._build_private_provider` — L4996–L5007
- `def MainController.refresh_trades` — L5012–L5058
- `def MainController.record_paper_trade` — L5060–L5107
- `def MainController._auto_trader` — L5112–L5198
- `async def MainController._auto_trader.price_source` — L5130–L5135
- `async def MainController._auto_trader.candidate_source` — L5146–L5177
- `def MainController.save_auto_trade_settings` — L5200–L5217
- `def MainController.refresh_auto_config` — L5219–L5249
- `def MainController._on_auto_trade_event` — L5251–L5258
- `def MainController._handle_auto_trade_event` — L5260–L5296
- `def MainController._refresh_auto_trade_panel` — L5298–L5348
- `def MainController.toggle_auto_trading` — L5350–L5388
- `def MainController.toggle_auto_trading.started` — L5355–L5364
- `def MainController.toggle_auto_trading.stopped` — L5379–L5381
- `def MainController.close_paper_trade` — L5390–L5408
- `def MainController.clear_trade_history` — L5410–L5420
- `def MainController.export_trades` — L5422–L5458
- `def MainController.sync_wallet` — L5463–L5521
- `async def MainController.sync_wallet.run` — L5492–L5496
- `def MainController.sync_wallet.done` — L5498–L5511
- `def MainController.sync_wallet.failed` — L5513–L5517
- `def MainController.refresh_wallet` — L5523–L5574
- `def MainController._remember_prices` — L5579–L5602
- `def MainController._refresh_search_suggestions` — L5604–L5621
- `def MainController._on_search_suggestion` — L5623–L5633
- `def MainController.global_search` — L5635–L5657
- `def MainController.refresh_current_page` — L5659–L5673
- `def MainController._sync_user_chrome` — L5678–L5684
- `def MainController._trade_row` — L5686–L5710
- `def MainController._digits` — L5712–L5715
- `def MainController._localized_datetime` — L5717–L5726
- `def MainController._trade_metrics` — L5728–L5735
- `def MainController._wallet_split_text` — L5737–L5768
- `def MainController._wallet_split_text.total_of` — L5749–L5763
- `def MainController._wallet_assets` — L5770–L5828
- `async def MainController._ticker_price` — L5830–L5837
- `async def MainController._usdt_price` — L5839–L5874
- `def MainController._remember_price` — L5878–L5883
- `def MainController._auto_economics_text` — L5885–L5906
- `def MainController._auto_trade_config` — L5908–L5912
- `def MainController._ensure_tick_engine` — L5917–L5949
- `def MainController._on_market_ticker` — L5951–L5965
- `def MainController._refresh_orderbooks` — L5967–L5997
- `async def MainController._refresh_orderbooks.refresh` — L5980–L5989
- `def MainController._auto_selected_symbols` — L5999–L6016
- `def MainController._portfolio_snapshot` — L6018–L6062
- `def MainController._cached_prediction_dict` — L6064–L6078
- `def MainController._prediction_direction` — L6080–L6093
- `def MainController.change_auto_engine_mode` — L6095–L6109
- `def MainController.on_auto_symbol_selected` — L6111–L6119
- `def MainController._auto_timeframe` — L6121–L6124
- `def MainController.on_auto_timeframe_changed` — L6126–L6135
- `def MainController._load_terminal_chart` — L6137–L6176
- `async def MainController._load_terminal_chart.load` — L6149–L6152
- `def MainController._load_terminal_chart.apply` — L6154–L6167
- `def MainController._mark_terminal_chart` — L6178–L6211
- `def MainController.on_opportunity_enter` — L6213–L6262
- `def MainController.on_opportunity_enter.done` — L6241–L6255
- `def MainController.on_chart_indicators_changed` — L6267–L6270
- `def MainController._apply_chart_indicators` — L6272–L6296
- `def MainController._draw_terminal_indicator` — L6298–L6329
- `def MainController.on_ai_opinion_requested` — L6334–L6365
- `def MainController.on_ai_opinion_requested.apply` — L6352–L6353
- `def MainController.on_ai_opinion_requested.failed` — L6355–L6358
- `def MainController.on_scanner_settings_saved` — L6370–L6374
- `def MainController.on_selected_symbols_saved` — L6376–L6411
- `def MainController._run_watch_scan` — L6416–L6449
- `def MainController._run_watch_scan.apply` — L6431–L6439
- `def MainController._run_watch_scan.failed` — L6441–L6442
- `def MainController._watch_rows_from_candidates` — L6451–L6504
- `def MainController._run_auto_prediction` — L6506–L6541
- `async def MainController._run_auto_prediction.compute` — L6519–L6526
- `def MainController._run_auto_prediction.apply` — L6528–L6532
- `def MainController._enrich_auto_prediction` — L6543–L6567
- `def MainController.close_auto_position` — L6569–L6582
- `def MainController.emergency_exit_positions` — L6584–L6600
- `def MainController.emergency_exit_positions.done` — L6591–L6593
- `def MainController._position_rows` — L6602–L6745
- `def MainController._position_rows.quote_for` — L6617–L6618
- `def MainController._risk_panel_data` — L6747–L6848
- `def MainController._refresh_auto_terminal` — L6850–L7039
- `async def MainController._ai_candidate_scan` — L7041–L7184
- `def MainController._market_reachable` — L7186–L7196
- `def MainController._cached_symbol_price` — L7198–L7231
- `def MainController._peek_chart` — L7233–L7241
- `def MainController._exit_fee` — L7243–L7257
- `def MainController._exit_fee._get` — L7247–L7254
- `def MainController.start_connection_keepalive` — L7259–L7264
- `def MainController._connection_keepalive` — L7266–L7278
- `def MainController.start_scorecard_timer` — L7280–L7285
- `def MainController._scorecard_tick` — L7287–L7293
- `def MainController.save_scorecard_auto` — L7295–L7297
- `def MainController._last_price` — L7299–L7333
- `def MainController._change_percent` — L7335–L7343
- `def MainController._change_text` — L7345–L7348
- `def MainController._money` — L7350–L7356
- `def MainController._toman_text` — L7358–L7370
- `def MainController._as_datetime` — L7373–L7383
- `def MainController._toast` — L7385–L7392
- `def MainController.status` — L7397–L7399
- `def MainController._on_error` — L7401–L7410

### `ui/dialogs/__init__.py`

پنجره‌های گفت‌وگو: ورود، ویزارد اولین اجرا، جزئیات سیگنال، جزئیات ارز و تحلیل.

ارجاع داخلی: `ui/dialogs/analysis_dialog.py`, `ui/dialogs/auth_dialog.py`, `ui/dialogs/coin_detail_dialog.py`, `ui/dialogs/first_run_wizard.py`, `ui/dialogs/signal_detail_dialog.py`.
واردکنندگان ایستا: `main.py`, `ui/controllers/main_controller.py`.

### `ui/dialogs/analysis_dialog.py`

پنجرهٔ نمایش تحلیل نوشتاری یک سیگنال.

ارجاع داخلی: `localization/__init__.py`, `ui/widgets/__init__.py`.
واردکنندگان ایستا: `tests/test_chat_ui_v2.py`, `tests/test_v1918_live_and_auto.py`, `ui/controllers/main_controller.py`, `ui/dialogs/__init__.py`.
- `class AnalysisDialog : QDialog` — L36–L235
- `def AnalysisDialog.__init__` — L51–L67
- `def AnalysisDialog._build` — L72–L113
- `def AnalysisDialog._build_header` — L115–L150
- `def AnalysisDialog._to_html` — L155–L187
- `def AnalysisDialog._copy_text` — L189–L196
- `def AnalysisDialog._on_rerun` — L198–L201
- `def AnalysisDialog.set_busy` — L203–L216
- `def AnalysisDialog.set_analysis_text` — L218–L226
- `def AnalysisDialog.set_status` — L228–L230
- `def AnalysisDialog.analysis_text` — L233–L235

### `ui/dialogs/auth_dialog.py`

گفت‌وگوی ورود و ثبت‌نام.

ارجاع داخلی: `app/core/email_service.py`, `app/security/passwords.py`, `localization/__init__.py`, `ui/dialogs/password_reset_dialog.py`, `ui/widgets/__init__.py`.
واردکنندگان ایستا: `ui/dialogs/__init__.py`.
- `class AuthDialog : QDialog` — L34–L307
- `def AuthDialog.__init__` — L47–L66
- `def AuthDialog._build` — L71–L169
- `def AuthDialog._apply_mode` — L174–L212
- `def AuthDialog._toggle_mode` — L214–L217
- `def AuthDialog._update_strength` — L219–L225
- `def AuthDialog._submit` — L230–L273
- `def AuthDialog.open_password_reset` — L275–L295
- `def AuthDialog._show_message` — L297–L301
- `def AuthDialog._show_error` — L303–L307

### `ui/dialogs/coin_detail_dialog.py`

پنجرهٔ جزئیات کامل یک ارز.

ارجاع داخلی: `localization/__init__.py`, `market/timeframes.py`, `ui/widgets/__init__.py`.
واردکنندگان ایستا: `tests/test_markets_sorting.py`, `tests/test_v155_ui_and_ai.py`, `tests/test_v162_modal_close.py`, `ui/controllers/main_controller.py`, `ui/dialogs/__init__.py`.
- `class CoinDetailDialog : QDialog` — L43–L393
- `def CoinDetailDialog.__init__` — L64–L86
- `def CoinDetailDialog._build` — L91–L126
- `def CoinDetailDialog._build_header` — L128–L164
- `def CoinDetailDialog._build_stats` — L166–L191
- `def CoinDetailDialog._build_details` — L193–L214
- `def CoinDetailDialog._build_actions` — L216–L274
- `def CoinDetailDialog.selected_timeframe` — L279–L281
- `def CoinDetailDialog.apply_snapshot` — L283–L299
- `def CoinDetailDialog.apply_details` — L301–L325
- `def CoinDetailDialog.set_busy` — L327–L331
- `def CoinDetailDialog.set_status` — L333–L335
- `def CoinDetailDialog.set_details_error` — L337–L340
- `def CoinDetailDialog.symbol` — L343–L345
- `def CoinDetailDialog._toggle_watchlist` — L350–L354
- `def CoinDetailDialog._watchlist_text` — L356–L359
- `def CoinDetailDialog._apply_change` — L361–L369
- `def CoinDetailDialog._format_number` — L371–L383
- `def CoinDetailDialog.retranslate` — L385–L393

### `ui/dialogs/first_run_wizard.py`

ویزارد اولین اجرا.

ارجاع داخلی: `app/core/constants.py`, `app/logging/__init__.py`, `localization/__init__.py`.
واردکنندگان ایستا: `ui/dialogs/__init__.py`.
- `class _Page : QWizardPage` — L35–L53
- `def _Page.__init__` — L38–L44
- `def _Page.add` — L46–L49
- `def _Page.add_stretch` — L51–L53
- `class FirstRunWizard : QWizard` — L56–L220
- `def FirstRunWizard.__init__` — L66–L80
- `def FirstRunWizard._build_welcome` — L85–L97
- `def FirstRunWizard._build_appearance` — L99–L117
- `def FirstRunWizard._build_exchange` — L119–L133
- `def FirstRunWizard._build_ai` — L135–L158
- `def FirstRunWizard._build_risk` — L160–L190
- `def FirstRunWizard._build_finish` — L192–L199
- `def FirstRunWizard.collected_settings` — L204–L220

### `ui/dialogs/password_reset_dialog.py`

بازیابی رمز عبور فراموش‌شده.

ارجاع داخلی: `app/security/passwords.py`, `localization/__init__.py`, `ui/widgets/common.py`, `ui/widgets/controls.py`.
واردکنندگان ایستا: `ui/dialogs/auth_dialog.py`.
- `class PasswordResetDialog : QDialog` — L41–L416
- `def PasswordResetDialog.__init__` — L57–L79
- `def PasswordResetDialog._build` — L84–L130
- `def PasswordResetDialog._build_email_step` — L132–L145
- `def PasswordResetDialog._build_code_step` — L147–L202
- `def PasswordResetDialog._build_password_step` — L204–L233
- `def PasswordResetDialog._show_step` — L238–L277
- `def PasswordResetDialog._go_back` — L279–L283
- `def PasswordResetDialog._advance` — L285–L293
- `def PasswordResetDialog._request_code` — L295–L325
- `def PasswordResetDialog._verify_code` — L327–L341
- `def PasswordResetDialog._save_password` — L343–L362
- `def PasswordResetDialog._resend` — L364–L367
- `def PasswordResetDialog._start_cooldown` — L372–L382
- `def PasswordResetDialog._tick` — L384–L397
- `def PasswordResetDialog._update_strength` — L399–L403
- `def PasswordResetDialog._show_message` — L405–L409
- `def PasswordResetDialog.closeEvent` — L411–L416

### `ui/dialogs/signal_detail_dialog.py`

پنجرهٔ جزئیات کامل یک سیگنال.

ارجاع داخلی: `localization/__init__.py`, `ui/signal_grading.py`, `ui/widgets/__init__.py`, `ui/widgets/position_calculator.py`.
واردکنندگان ایستا: `tests/test_v190_position_sizing.py`, `tests/test_v1917_forecast.py`, `tests/test_v195_ai_and_validity.py`, `ui/controllers/main_controller.py`, `ui/dialogs/__init__.py`.
- `class _TokenOnly` — L43–L55
- `def _TokenOnly.__init__` — L54–L55
- `class SignalDetailDialog : QDialog` — L58–L711
- `def SignalDetailDialog.__init__` — L71–L93
- `def SignalDetailDialog._build` — L98–L138
- `def SignalDetailDialog._build_header` — L140–L182
- `def SignalDetailDialog._build_levels` — L184–L233
- `def SignalDetailDialog._build_forecast` — L235–L306
- `def SignalDetailDialog._build_calculator` — L308–L334
- `def SignalDetailDialog.set_account_balance` — L336–L346
- `def SignalDetailDialog._build_meta` — L348–L385
- `def SignalDetailDialog._build_reasoning` — L387–L412
- `def SignalDetailDialog._build_recommendation` — L414–L503
- `def SignalDetailDialog._build_validity` — L505–L565
- `def SignalDetailDialog._build_review` — L567–L609
- `def SignalDetailDialog._build_disclaimer` — L611–L616
- `def SignalDetailDialog._build_buttons` — L618–L652
- `def SignalDetailDialog._on_trade_clicked` — L657–L659
- `def SignalDetailDialog._entry_text` — L661–L681
- `def SignalDetailDialog._price` — L683–L702
- `def SignalDetailDialog._direction_role` — L705–L711

### `ui/dialogs/trading_dialogs.py`

مودال‌های صفحهٔ معاملهٔ خودکار (v2.2).

ارجاع داخلی: `localization/__init__.py`, `ui/widgets/__init__.py`.
واردکنندگان ایستا: `tests/test_v22_terminal_pro.py`, `ui/pages/trades_page.py`.
- `def _symbol_hue` — L39–L41
- `class SymbolIconWidget : QWidget` — L44–L68
- `def SymbolIconWidget.__init__` — L47–L51
- `def SymbolIconWidget.paintEvent` — L53–L68
- `class SymbolIconDelegate : QStyledItemDelegate` — L71–L107
- `def SymbolIconDelegate.paint` — L79–L104
- `def SymbolIconDelegate.sizeHint` — L106–L107
- `class SymbolPickerDialog : QDialog` — L110–L209
- `def SymbolPickerDialog.__init__` — L118–L179
- `def SymbolPickerDialog._toggle` — L181–L188
- `def SymbolPickerDialog._filter` — L190–L196
- `def SymbolPickerDialog._update_count` — L198–L200
- `def SymbolPickerDialog.checked_symbols` — L202–L209
- `class PositionDetailDialog : QDialog` — L212–L321
- `def PositionDetailDialog.__init__` — L245–L313
- `def PositionDetailDialog._emit_close` — L315–L321
- `class ScannerSettingsDialog : QDialog` — L324–L412
- `def ScannerSettingsDialog.__init__` — L332–L402
- `def ScannerSettingsDialog.__init__.add_spin` — L363–L382
- `def ScannerSettingsDialog.values` — L404–L412

### `ui/icons/__init__.py`

مجموعهٔ آیکون‌های برداری برنامه.

ارجاع داخلی: `ui/icons/registry.py`.
واردکنندگان ایستا: `tests/test_icons_search_theme.py`, `ui/pages/chat_page.py`, `ui/widgets/ai_status_card.py`, `ui/widgets/chrome.py`, `ui/widgets/theme_card.py`.

### `ui/icons/paths.py`

تعریف مسیر برداری هر آیکون.

واردکنندگان ایستا: `ui/icons/registry.py`.

### `ui/icons/registry.py`

ساخت آیکون از روی مسیرهای برداری.

ارجاع داخلی: `ui/icons/paths.py`.
واردکنندگان ایستا: `ui/icons/__init__.py`, `ui/widgets/chrome.py`.
- `def available_icons` — L29–L31
- `def register_icon` — L34–L42
- `def resolve_name` — L45–L58
- `def icon_svg` — L62–L73
- `def _render_pixmap` — L77–L99
- `def icon_pixmap` — L102–L114
- `def icon` — L117–L134
- `def icon_size` — L137–L139

### `ui/pages/__init__.py`

صفحات اصلی برنامه.

ارجاع داخلی: `ui/pages/analysis_page.py`, `ui/pages/base_page.py`, `ui/pages/chat_page.py`, `ui/pages/dashboard_page.py`, `ui/pages/help_page.py`, `ui/pages/markets_page.py`, `ui/pages/prediction_page.py`, `ui/pages/reports_page.py`, `ui/pages/settings_page.py`, `ui/pages/signals_page.py`, `ui/pages/trades_page.py`, `ui/pages/wallet_page.py`.
واردکنندگان ایستا: `tests/test_new_pages.py`, `ui/windows/main_window.py`.

### `ui/pages/analysis_page.py`

صفحه تحلیل.

ارجاع داخلی: `localization/__init__.py`, `market/timeframes.py`, `ui/charts/__init__.py`, `ui/pages/base_page.py`, `ui/widgets/__init__.py`.
واردکنندگان ایستا: `tests/test_pages_design_v151.py`, `tests/test_ui_wiring.py`, `tests/test_v153_fixes.py`, `tests/test_v1918_live_and_auto.py`, `ui/pages/__init__.py`.
- `class AnalysisPage : BasePage` — L41–L459
- `def AnalysisPage.__init__` — L52–L53
- `def AnalysisPage.build` — L55–L211
- `def AnalysisPage._apply_headers` — L213–L224
- `def AnalysisPage._on_timeframe_bar_changed` — L229–L239
- `def AnalysisPage._sync_timeframe_bar` — L241–L245
- `def AnalysisPage.set_indicator_catalog` — L247–L312
- `def AnalysisPage.select_all_indicators` — L314–L316
- `def AnalysisPage.clear_indicators` — L318–L320
- `def AnalysisPage._on_indicator_toggled` — L322–L324
- `def AnalysisPage.enabled_indicators` — L326–L330
- `def AnalysisPage.set_enabled_indicators` — L332–L344
- `def AnalysisPage.apply_theme` — L346–L349
- `def AnalysisPage.set_busy` — L351–L357
- `def AnalysisPage.set_symbols` — L359–L367
- `def AnalysisPage.set_indicator_rows` — L369–L377
- `def AnalysisPage.set_level_rows` — L379–L392
- `def AnalysisPage._on_chart_type_changed` — L394–L396
- `def AnalysisPage._on_fit_clicked` — L398–L400
- `def AnalysisPage.set_live_price` — L402–L422
- `def AnalysisPage.set_chart_data` — L424–L426
- `def AnalysisPage.set_chart_overlay` — L428–L430
- `def AnalysisPage.set_chart_levels` — L432–L434
- `def AnalysisPage.apply_chart_palette` — L436–L438
- `def AnalysisPage.set_ai_text` — L440–L442
- `def AnalysisPage.retranslate` — L444–L459

### `ui/pages/base_page.py`

کلاس پایه صفحات.

ارجاع داخلی: `localization/__init__.py`, `ui/widgets/__init__.py`, `ui/widgets/common.py`, `ui/widgets/table_toolbar.py`.
واردکنندگان ایستا: `ui/pages/__init__.py`, `ui/pages/analysis_page.py`, `ui/pages/chat_page.py`, `ui/pages/dashboard_page.py`, `ui/pages/help_page.py`, `ui/pages/markets_page.py`, `ui/pages/prediction_page.py`, `ui/pages/reports_page.py`, `ui/pages/settings_page.py`, `ui/pages/signals_page.py`, `ui/pages/trades_page.py`, `ui/pages/wallet_page.py`.
- `class BasePage : QWidget` — L22–L118
- `def BasePage.__init__` — L39–L84
- `def BasePage.table_toolbars` — L86–L88
- `def BasePage.layout_root` — L90–L92
- `def BasePage.build` — L95–L96
- `def BasePage.retranslate` — L98–L110
- `def BasePage.on_activated` — L112–L118

### `ui/pages/chat_page.py`

صفحهٔ گفت‌وگو با دستیار هوش مصنوعی.

ارجاع داخلی: `localization/__init__.py`, `market/timeframes.py`, `ui/icons/__init__.py`, `ui/pages/base_page.py`, `ui/widgets/__init__.py`, `ui/widgets/tool_trail.py`.
واردکنندگان ایستا: `tests/test_chat_page.py`, `tests/test_chat_ui_v2.py`, `tests/test_v153_fixes.py`, `tests/test_v154_ai_signal.py`, `tests/test_v162_chat_streaming.py`, `tests/test_v171_chat_tool_steps.py`, `ui/pages/__init__.py`.
- `class ChatInput : QTextEdit` — L66–L115
- `def ChatInput.__init__` — L82–L89
- `def ChatInput.text` — L91–L93
- `def ChatInput.setText` — L95–L97
- `def ChatInput.keyPressEvent` — L99–L107
- `def ChatInput._auto_resize` — L109–L115
- `class ChatBubble : QFrame` — L118–L241
- `def ChatBubble.__init__` — L139–L197
- `def ChatBubble.set_author` — L199–L201
- `def ChatBubble.set_avatar_icon` — L203–L210
- `def ChatBubble.set_text` — L212–L215
- `def ChatBubble.text` — L217–L219
- `def ChatBubble.set_tools` — L221–L227
- `def ChatBubble.apply_max_width` — L229–L241
- `class ChatPage : BasePage` — L277–L887
- `def ChatPage.__init__` — L298–L306
- `def ChatPage.build` — L311–L326
- `def ChatPage._build_history_panel` — L328–L359
- `def ChatPage._build_chat_panel` — L361–L453
- `def ChatPage._build_suggestions` — L455–L468
- `def ChatPage._use_suggestion` — L470–L473
- `def ChatPage.set_conversations` — L478–L496
- `def ChatPage.select_conversation` — L498–L505
- `def ChatPage._filter_history` — L507–L512
- `def ChatPage._on_history_clicked` — L514–L518
- `def ChatPage._show_history_menu` — L520–L536
- `def ChatPage._start_rename` — L538–L549
- `def ChatPage.load_messages` — L551–L569
- `def ChatPage._bubble_alignment` — L574–L583
- `def ChatPage.add_message` — L585–L594
- `def ChatPage._label_bubble` — L596–L600
- `def ChatPage._avatar_color` — L602–L608
- `def ChatPage._bubble_width` — L610–L616
- `def ChatPage.resizeEvent` — L618–L623
- `def ChatPage._scroll_to_bottom` — L625–L630
- `def ChatPage._show_welcome` — L632–L634
- `def ChatPage.send_current` — L636–L644
- `def ChatPage.begin_reply` — L646–L651
- `def ChatPage.update_progress` — L653–L657
- `def ChatPage.tool_started` — L659–L672
- `def ChatPage.tool_finished` — L674–L688
- `def ChatPage._tool_display_names` — L690–L702
- `def ChatPage.stream_delta` — L704–L724
- `def ChatPage.streamed_text` — L727–L729
- `def ChatPage.finish_reply` — L731–L748
- `def ChatPage.fail_reply` — L750–L752
- `def ChatPage.set_busy` — L754–L762
- `def ChatPage.show_action` — L767–L780
- `def ChatPage.hide_action` — L782–L785
- `def ChatPage._on_action_clicked` — L787–L793
- `def ChatPage.set_status` — L798–L800
- `def ChatPage.set_symbols` — L802–L810
- `def ChatPage.set_context` — L812–L819
- `def ChatPage.current_context` — L821–L827
- `def ChatPage.current_mode` — L829–L832
- `def ChatPage._remove_all_bubbles` — L834–L840
- `def ChatPage.clear_conversation` — L842–L847
- `def ChatPage.message_count` — L850–L852
- `def ChatPage.apply_theme` — L854–L867
- `def ChatPage.retranslate` — L869–L887

### `ui/pages/dashboard_page.py`

صفحه داشبورد.

ارجاع داخلی: `localization/__init__.py`, `ui/pages/base_page.py`, `ui/widgets/__init__.py`, `ui/widgets/arrangeable.py`.
واردکنندگان ایستا: `tests/test_v180_arrangeable_layout.py`, `ui/pages/__init__.py`.
- `class DashboardPage : BasePage` — L46–L363
- `def DashboardPage.__init__` — L59–L63
- `def DashboardPage.build` — L65–L175
- `def DashboardPage._apply_headers` — L177–L190
- `def DashboardPage.set_connection_status` — L195–L197
- `def DashboardPage.set_status_value` — L199–L202
- `def DashboardPage.set_market_rows` — L204–L245
- `def DashboardPage.set_ticker_items` — L247–L249
- `def DashboardPage.set_stat` — L251–L267
- `def DashboardPage.apply_theme` — L269–L276
- `def DashboardPage._on_market_cell_clicked` — L278–L282
- `def DashboardPage.market_row_data` — L284–L289
- `def DashboardPage.set_signal_rows` — L291–L304
- `def DashboardPage._arrange_text` — L309–L312
- `def DashboardPage._sync_arrange_button` — L314–L317
- `def DashboardPage._on_arrange_toggled` — L319–L322
- `def DashboardPage.layout_state` — L324–L326
- `def DashboardPage.apply_layout_state` — L328–L330
- `def DashboardPage.reset_layout` — L332–L334
- `def DashboardPage.retranslate` — L336–L363

### `ui/pages/help_page.py`

صفحه راهنما.

ارجاع داخلی: `localization/__init__.py`, `ui/pages/base_page.py`, `ui/widgets/__init__.py`, `ui/widgets/tutorial_view.py`.
واردکنندگان ایستا: `tests/test_v180_tutorial.py`, `ui/pages/__init__.py`.
- `class HelpPage : BasePage` — L26–L104
- `def HelpPage.__init__` — L48–L50
- `def HelpPage.build` — L52–L60
- `def HelpPage._build_guide` — L62–L83
- `def HelpPage.open_tutorial` — L85–L94
- `def HelpPage.retranslate` — L96–L104

### `ui/pages/markets_page.py`

صفحه بازارها.

ارجاع داخلی: `localization/__init__.py`, `ui/pages/base_page.py`, `ui/widgets/__init__.py`.
واردکنندگان ایستا: `tests/test_markets_sorting.py`, `tests/test_pages_design_v151.py`, `tests/test_settings_expanded.py`, `tests/test_ui_wiring.py`, `tests/test_v153_fixes.py`, `tests/test_v154_localization.py`, `tests/test_v158_security_tab.py`, `tests/test_v1918_alerts.py`, `tests/test_v192_watchlist.py`, `tests/test_v193_page_scrolling.py`, `ui/pages/__init__.py`, `ui/pages/settings_page.py`.
- `class NumericItem : QTableWidgetItem` — L82–L105
- `def NumericItem.__init__` — L92–L94
- `def NumericItem.__lt__` — L96–L100
- `def NumericItem.value` — L103–L105
- `class MarketsPage : BasePage` — L108–L784
- `def MarketsPage.__init__` — L121–L131
- `def MarketsPage.build` — L136–L257
- `def MarketsPage.show_watchlists` — L259–L261
- `def MarketsPage._apply_headers` — L263–L286
- `def MarketsPage.set_palette` — L291–L293
- `def MarketsPage.apply_theme` — L295–L310
- `def MarketsPage.set_toman_rate` — L312–L329
- `def MarketsPage.set_rows` — L331–L349
- `def MarketsPage._update_values_in_place` — L351–L373
- `def MarketsPage.apply_price_updates` — L375–L419
- `def MarketsPage._on_sort_changed` — L424–L427
- `def MarketsPage.sort_rows` — L429–L482
- `def MarketsPage.sort_rows.price_of` — L439–L443
- `def MarketsPage.sort_rows.volume_of` — L445–L449
- `def MarketsPage.sort_rows.change_of` — L451–L455
- `def MarketsPage.sort_rows.value_of` — L457–L466
- `def MarketsPage._on_header_clicked` — L484–L503
- `def MarketsPage._on_cell_clicked` — L505–L518
- `def MarketsPage.row_data` — L520–L525
- `def MarketsPage._filter` — L527–L615
- `def MarketsPage._apply_quick_filters` — L617–L651
- `def MarketsPage._on_quote_changed` — L653–L656
- `def MarketsPage._on_chip_changed` — L658–L661
- `def MarketsPage.set_watchlist` — L663–L670
- `def MarketsPage._on_star_clicked` — L672–L680
- `def MarketsPage._rebuild_index` — L682–L688
- `def MarketsPage._tint` — L690–L703
- `def MarketsPage._toman_text` — L705–L713
- `def MarketsPage._price_decimals` — L716–L730
- `def MarketsPage._on_alert_clicked` — L732–L736
- `def MarketsPage.selected_symbol` — L738–L755
- `def MarketsPage.retranslate` — L757–L784

### `ui/pages/prediction_page.py`

صفحهٔ «هوش پیش‌بینی» — داشبورد تحلیلی موتور پیش‌بینی چندافقی (v2.0).

ارجاع داخلی: `localization/__init__.py`, `ui/pages/base_page.py`, `ui/widgets/__init__.py`, `ui/widgets/charts_mini.py`.
واردکنندگان ایستا: `tests/test_prediction_ui_and_tools.py`, `tests/test_v200_event_driven_trading.py`, `ui/pages/__init__.py`.
- `class PredictionPage : BasePage` — L59–L886
- `def PredictionPage.__init__` — L71–L79
- `def PredictionPage.build` — L84–L138
- `def PredictionPage._build_horizons_body` — L140–L175
- `def PredictionPage._build_summary_body` — L177–L221
- `def PredictionPage._build_summary_body.cell` — L180–L191
- `def PredictionPage.set_symbol` — L226–L230
- `def PredictionPage.set_busy` — L232–L238
- `def PredictionPage.update_report` — L240–L243
- `def PredictionPage.retranslate` — L248–L268
- `def PredictionPage._apply_payload` — L273–L302
- `def PredictionPage._render_summary` — L306–L389
- `def PredictionPage._render_fan` — L391–L414
- `def PredictionPage._render_horizons` — L418–L511
- `def PredictionPage._retranslate_table_headers` — L513–L519
- `def PredictionPage._render_market` — L523–L611
- `def PredictionPage._render_scenarios` — L615–L681
- `def PredictionPage._render_warnings` — L685–L717
- `def PredictionPage._render_accuracy` — L721–L766
- `def PredictionPage._render_changed` — L770–L813
- `def PredictionPage._render_timeline` — L817–L849
- `def PredictionPage._row` — L854–L867
- `def PredictionPage._muted` — L869–L873
- `def PredictionPage.resizeEvent` — L875–L886

### `ui/pages/reports_page.py`

صفحه گزارش‌ها.

ارجاع داخلی: `localization/__init__.py`, `ui/pages/base_page.py`, `ui/widgets/__init__.py`.
واردکنندگان ایستا: `tests/test_pages_design_v151.py`, `tests/test_v160_error_keys.py`, `tests/test_v1918_scorecard.py`, `tests/test_v191_outcome_tracking.py`, `tests/test_v193_page_scrolling.py`, `ui/pages/__init__.py`.
- `class ReportsPage : BasePage` — L51–L466
- `def ReportsPage.__init__` — L61–L65
- `def ReportsPage.build` — L67–L93
- `def ReportsPage._build_scorecard_tab` — L95–L147
- `def ReportsPage.set_scorecard_auto` — L149–L156
- `def ReportsPage.set_scorecard` — L158–L195
- `def ReportsPage._wrap_scroll` — L198–L209
- `def ReportsPage._build_report_tab` — L211–L290
- `def ReportsPage._apply_headers` — L292–L299
- `def ReportsPage._fill_format_combo` — L310–L325
- `def ReportsPage.selected_format` — L327–L332
- `def ReportsPage.set_summary` — L334–L354
- `def ReportsPage._update_visuals` — L356–L407
- `def ReportsPage._update_visuals.share` — L372–L376
- `def ReportsPage.apply_theme` — L409–L415
- `def ReportsPage.show_performance` — L417–L419
- `def ReportsPage.set_preview` — L421–L441
- `def ReportsPage.retranslate` — L443–L466

### `ui/pages/settings_page.py`

صفحه تنظیمات.

ارجاع داخلی: `ai/local_model_fit.py`, `ai/prompt_budget.py`, `ai/providers/catalog.py`, `ai/providers/free_models.py`, `app/core/email_service.py`, `localization/__init__.py`, `market/exchange_catalog.py`, `ui/pages/base_page.py`, `ui/pages/markets_page.py`, `ui/themes/__init__.py`, `ui/themes/catalog.py`, `ui/themes/fonts.py`, `ui/widgets/__init__.py`, `ui/widgets/responsive_grid.py`, `ui/widgets/theme_card.py`, `ui/widgets/theme_editor.py`, `ui/widgets/theme_preview.py`.
واردکنندگان ایستا: `tests/test_settings_expanded.py`, `tests/test_ui_wiring.py`, `tests/test_v158_security_tab.py`, `tests/test_v161_omniroute_font_theme.py`, `tests/test_v170_signals_ui.py`, `tests/test_v180_custom_themes.py`, `tests/test_v1913_ashna.py`, `tests/test_v1920_ashna_settings.py`, `ui/pages/__init__.py`.
- `class SettingsPage : BasePage` — L61–L1839
- `def SettingsPage.__init__` — L125–L129
- `def SettingsPage.build` — L131–L158
- `def SettingsPage._form` — L160–L166
- `def SettingsPage._add_row` — L168–L173
- `def SettingsPage._build_general` — L175–L214
- `def SettingsPage._fill_theme_combo` — L216–L234
- `def SettingsPage._fill_font_combo` — L236–L270
- `def SettingsPage._on_font_scale_changed` — L272–L287
- `def SettingsPage._on_font_family_selected` — L289–L293
- `def SettingsPage.select_font_family` — L295–L302
- `def SettingsPage._update_theme_preview` — L304–L308
- `def SettingsPage._build_appearance` — L310–L458
- `def SettingsPage._on_editor_toggled` — L460–L463
- `def SettingsPage._on_editor_reset` — L465–L467
- `def SettingsPage.load_theme_editor` — L469–L471
- `def SettingsPage.set_custom_theme_active` — L473–L479
- `def SettingsPage.refresh_theme_cards` — L481–L501
- `def SettingsPage._sync_editor_texts` — L503–L515
- `def SettingsPage._theme_name` — L517–L522
- `def SettingsPage._theme_description` — L524–L527
- `def SettingsPage._on_theme_card_selected` — L529–L537
- `def SettingsPage.select_theme` — L539–L548
- `def SettingsPage._build_exchange` — L550–L587
- `def SettingsPage._build_accounts_panel` — L589–L641
- `def SettingsPage._retranslate_accounts_headers` — L643–L654
- `def SettingsPage.set_accounts` — L656–L696
- `def SettingsPage.selected_account_id` — L698–L714
- `def SettingsPage._emit_account_test` — L716–L727
- `def SettingsPage._emit_account_activate` — L729–L735
- `def SettingsPage._emit_account_remove` — L737–L743
- `def SettingsPage._on_exchange_changed` — L745–L773
- `def SettingsPage._build_ai` — L775–L858
- `def SettingsPage._on_ai_provider_changed` — L860–L896
- `def SettingsPage._refresh_model_fit` — L898–L941
- `def SettingsPage._refresh_model_list` — L943–L972
- `def SettingsPage.set_model_list` — L974–L977
- `def SettingsPage.selected_model` — L979–L990
- `def SettingsPage.auto_pick_free_model` — L992–L1003
- `def SettingsPage.free_model_count` — L1005–L1012
- `def SettingsPage.set_ai_status` — L1014–L1020
- `def SettingsPage._build_risk` — L1022–L1049
- `def SettingsPage._build_display` — L1051–L1077
- `def SettingsPage._build_performance` — L1079–L1197
- `def SettingsPage._build_security` — L1199–L1397
- `def SettingsPage._apply_email_preset` — L1399–L1412
- `def SettingsPage._emit_email_save` — L1414–L1425
- `def SettingsPage.set_email_settings` — L1427–L1448
- `def SettingsPage.set_email_status` — L1450–L1456
- `def SettingsPage._emit_password_change` — L1458–L1464
- `def SettingsPage.clear_password_inputs` — L1466–L1470
- `def SettingsPage._selected_session_row` — L1472–L1488
- `def SettingsPage._emit_revoke_selected` — L1490–L1501
- `def SettingsPage._retranslate_session_headers` — L1503–L1512
- `def SettingsPage.set_profile` — L1514–L1517
- `def SettingsPage.set_sessions` — L1519–L1536
- `def SettingsPage.set_security_enabled` — L1538–L1560
- `def SettingsPage._build_backup` — L1562–L1610
- `def SettingsPage.set_update_status` — L1612–L1620
- `def SettingsPage.load_values` — L1625–L1730
- `def SettingsPage.collect_values` — L1732–L1784
- `def SettingsPage.collect_secrets` — L1786–L1794
- `def SettingsPage.open_tab` — L1796–L1806
- `def SettingsPage.retranslate` — L1808–L1839

### `ui/pages/signals_page.py`

صفحه سیگنال‌ها.

ارجاع داخلی: `localization/__init__.py`, `market/timeframes.py`, `ui/pages/base_page.py`, `ui/signal_grading.py`, `ui/widgets/__init__.py`.
واردکنندگان ایستا: `tests/test_pages_design_v151.py`, `tests/test_ui_wiring.py`, `tests/test_v154_ai_signal.py`, `tests/test_v170_signals_ui.py`, `tests/test_v172_signal_ai_and_scan_ui.py`, `tests/test_v180_table_fullscreen.py`, `tests/test_v193_page_scrolling.py`, `tests/test_v194_performance.py`, `tests/test_v195_ai_and_validity.py`, `ui/pages/__init__.py`.
- `class _RecommendationTone` — L54–L65
- `def _RecommendationTone.__init__` — L64–L65
- `class SignalsPage : BasePage` — L68–L1045
- `def SignalsPage.__init__` — L108–L112
- `def SignalsPage.build` — L114–L262
- `def SignalsPage._build_scanner` — L264–L364
- `def SignalsPage._build_auto_scan` — L366–L476
- `def SignalsPage._on_auto_toggled` — L478–L494
- `def SignalsPage._emit_auto_config` — L496–L498
- `def SignalsPage.auto_scan_options` — L500–L510
- `def SignalsPage.set_auto_scan_options` — L512–L568
- `def SignalsPage.set_auto_scan_status` — L570–L580
- `def SignalsPage._apply_scan_headers` — L582–L598
- `def SignalsPage.scan_options` — L600–L606
- `def SignalsPage.set_scanning` — L608–L624
- `def SignalsPage.set_scan_progress` — L626–L634
- `def SignalsPage.set_scan_status` — L636–L638
- `def SignalsPage._fit_scan_table_height` — L644–L661
- `def SignalsPage.set_scan_results` — L663–L731
- `def SignalsPage._freshness_item` — L733–L755
- `def SignalsPage._on_scan_cell_clicked` — L757–L771
- `def SignalsPage.scan_row` — L773–L778
- `def SignalsPage._emphasise` — L781–L787
- `def SignalsPage._on_current_analysis` — L789–L793
- `def SignalsPage.selected_timeframes` — L795–L803
- `def SignalsPage._signal_labels` — L805–L820
- `def SignalsPage._apply_headers` — L822–L833
- `def SignalsPage.show_signal` — L835–L841
- `def SignalsPage.apply_theme` — L843–L853
- `def SignalsPage._sort_history_rows` — L855–L895
- `def SignalsPage._sort_history_rows.confidence` — L872–L876
- `def SignalsPage._sort_history_rows.direction_rank` — L878–L880
- `def SignalsPage._resort_history` — L897–L901
- `def SignalsPage.set_history` — L903–L961
- `def SignalsPage._recommendation_item` — L963–L994
- `def SignalsPage.history_row` — L996–L1001
- `def SignalsPage.set_symbols` — L1003–L1011
- `def SignalsPage.set_busy` — L1013–L1018
- `def SignalsPage.retranslate` — L1020–L1045

### `ui/pages/trades_page.py`

صفحهٔ تاریخچه معاملات + ترمینال معاملهٔ خودکار.

ارجاع داخلی: `localization/__init__.py`, `trading/auto_trader.py`, `ui/charts/__init__.py`, `ui/dialogs/trading_dialogs.py`, `ui/pages/base_page.py`, `ui/widgets/__init__.py`.
واردکنندگان ایستا: `tests/test_v160_error_keys.py`, `tests/test_v180_table_fullscreen.py`, `tests/test_v1918_live_and_auto.py`, `tests/test_v1921_online_and_autotrade.py`, `tests/test_v193_page_scrolling.py`, `tests/test_v200_event_driven_trading.py`, `tests/test_v22_terminal_pro.py`, `ui/pages/__init__.py`.
- `class TradesPage : BasePage` — L119–L2313
- `def TradesPage.__init__` — L173–L189
- `def TradesPage.build` — L194–L221
- `def TradesPage._build_auto_tab` — L226–L277
- `def TradesPage._build_terminal_header` — L279–L330
- `def TradesPage._toggle_config_panel` — L332–L350
- `def TradesPage._build_config_panel` — L352–L428
- `def TradesPage._build_auto_guards_box` — L430–L504
- `def TradesPage._build_auto_guards_box._spin` — L455–L461
- `def TradesPage._build_auto_dashboard` — L506–L549
- `def TradesPage._build_chart_card` — L551–L672
- `def TradesPage._on_indicator_toggled` — L677–L680
- `def TradesPage.set_indicator_state` — L682–L690
- `def TradesPage._set_draw_mode` — L692–L694
- `def TradesPage._screenshot_chart` — L696–L713
- `def TradesPage._auto_timeframe` — L715–L720
- `def TradesPage._build_risk_panel` — L722–L756
- `def TradesPage._build_prediction_card` — L758–L874
- `def TradesPage._build_prediction_card.cell` — L782–L787
- `def TradesPage._request_ai_opinion` — L876–L883
- `def TradesPage.set_ai_opinion` — L885–L890
- `def TradesPage._build_opportunity_card` — L892–L942
- `def TradesPage._build_positions_card` — L944–L981
- `def TradesPage._build_history_tab` — L986–L1022
- `def TradesPage._build_auto_manual_box` — L1024–L1118
- `def TradesPage._build_auto_manual_box._money` — L1056–L1063
- `def TradesPage._on_auto_manual_toggled` — L1120–L1132
- `def TradesPage.load_auto_settings` — L1134–L1189
- `def TradesPage._set_spin` — L1192–L1197
- `def TradesPage.collect_auto_settings` — L1199–L1226
- `def TradesPage._emit_auto_settings` — L1228–L1230
- `def TradesPage._emit_automatic_profile` — L1232–L1252
- `def TradesPage._on_auto_toggle` — L1254–L1257
- `def TradesPage.set_auto_config` — L1259–L1261
- `def TradesPage.set_auto_state` — L1263–L1281
- `def TradesPage.set_auto_economics` — L1283–L1287
- `def TradesPage.set_auto_dashboard` — L1292–L1306
- `def TradesPage._open_symbol_picker` — L1308–L1332
- `def TradesPage.set_auto_symbols` — L1334–L1365
- `def TradesPage.update_prediction_summary` — L1367–L1495
- `def TradesPage.update_price_tick` — L1497–L1508
- `def TradesPage.set_auto_symbol` — L1510–L1530
- `def TradesPage._update_terminal_tab_titles` — L1532–L1550
- `def TradesPage._on_chart_symbol_changed` — L1552–L1564
- `def TradesPage.set_opportunities` — L1566–L1576
- `def TradesPage._render_opportunities` — L1578–L1677
- `def TradesPage._render_opportunities.maybe` — L1599–L1606
- `def TradesPage._filter_opportunities` — L1679–L1681
- `def TradesPage.set_scanner_values` — L1683–L1685
- `def TradesPage._open_scanner_settings` — L1687–L1695
- `def TradesPage._on_opportunity_activated` — L1697–L1715
- `def TradesPage.set_open_positions` — L1717–L1788
- `def TradesPage.set_tick_status` — L1793–L1826
- `def TradesPage.set_paper_live` — L1828–L1838
- `def TradesPage.set_risk_panel` — L1840–L1854
- `def TradesPage.set_chart_candles` — L1858–L1860
- `def TradesPage.set_chart_live_price` — L1862–L1864
- `def TradesPage.mark_chart_position` — L1866–L1870
- `def TradesPage.set_chart_status` — L1872–L1879
- `def TradesPage.apply_chart_palette` — L1881–L1883
- `def TradesPage.retranslate_chart` — L1885–L1887
- `def TradesPage._position_row_from_table` — L1889–L1908
- `def TradesPage.selected_position_id` — L1910–L1919
- `def TradesPage._emit_close_position` — L1921–L1927
- `def TradesPage._on_position_cell_clicked` — L1929–L1940
- `def TradesPage._on_position_activated` — L1942–L1949
- `def TradesPage._set_columns` — L1951–L1955
- `def TradesPage._build_filters` — L1960–L2004
- `def TradesPage._build_metrics` — L2006–L2033
- `def TradesPage.set_trades` — L2038–L2111
- `def TradesPage.set_metrics` — L2113–L2116
- `def TradesPage.set_symbols` — L2118–L2135
- `def TradesPage.filters` — L2137–L2147
- `def TradesPage.trade_row` — L2149–L2153
- `def TradesPage.apply_theme` — L2158–L2168
- `def TradesPage.resizeEvent` — L2170–L2175
- `def TradesPage.retranslate` — L2177–L2232
- `def TradesPage._fill_filter_combos` — L2237–L2251
- `def TradesPage._retranslate_headers` — L2253–L2268
- `def TradesPage._emit_filters` — L2270–L2273
- `def TradesPage._on_page_changed` — L2275–L2278
- `def TradesPage._selected_row` — L2280–L2291
- `def TradesPage._emit_close_selected` — L2293–L2300
- `def TradesPage._on_row_activated` — L2302–L2306
- `def TradesPage._cell` — L2309–L2313
- `def set_role_item` — L2316–L2329

### `ui/pages/wallet_page.py`

صفحه کیف پول.

ارجاع داخلی: `localization/__init__.py`, `ui/pages/base_page.py`, `ui/widgets/__init__.py`.
واردکنندگان ایستا: `ui/pages/__init__.py`.
- `class WalletPage : BasePage` — L53–L402
- `def WalletPage.__init__` — L68–L71
- `def WalletPage.build` — L76–L96
- `def WalletPage._build_content` — L98–L177
- `def WalletPage._build_empty` — L179–L194
- `def WalletPage.set_connected` — L199–L206
- `def WalletPage.set_busy` — L208–L215
- `def WalletPage.set_summary` — L217–L247
- `def WalletPage.set_assets` — L249–L297
- `def WalletPage.set_growth` — L299–L301
- `def WalletPage.set_last_sync` — L303–L307
- `def WalletPage.asset_row` — L309–L313
- `def WalletPage.apply_theme` — L318–L327
- `def WalletPage.retranslate` — L329–L345
- `def WalletPage._retranslate_headers` — L350–L361
- `def WalletPage._render_legend` — L363–L389
- `def WalletPage._cell` — L392–L396
- `def WalletPage._on_asset_clicked` — L398–L402

### `ui/signal_grading.py`

درجه‌بندی دیداری سیگنال‌ها — رنگ و نشانه.

واردکنندگان ایستا: `tests/test_v170_scanner_fonts_theme.py`, `tests/test_v170_signals_ui.py`, `tests/test_v195_ai_and_validity.py`, `ui/dialogs/signal_detail_dialog.py`, `ui/pages/signals_page.py`.
- `class Grade` — L42–L56
- `def confidence_grade` — L98–L115
- `def risk_level` — L118–L166
- `def risk_grade` — L169–L171
- `def direction_grade` — L174–L176
- `def signal_risk_level` — L179–L209
- `def freshness_grade` — L212–L221
- `def color_for` — L224–L234

### `ui/themes/__init__.py`

پوسته‌های ظاهری برنامه.

ارجاع داخلی: `ui/themes/catalog.py`, `ui/themes/fonts.py`, `ui/themes/stylesheet.py`, `ui/themes/theme_manager.py`, `ui/themes/tokens.py`.
واردکنندگان ایستا: `main.py`, `tests/test_new_pages.py`, `tests/test_pages_design_v151.py`, `tests/test_settings_expanded.py`, `tests/test_themes.py`, `tests/test_ui_wiring.py`, `tests/test_v155_ui_and_ai.py`, `tests/test_v172_signal_ai_and_scan_ui.py`, `tools/preview_shot.py`, `tools/sweep_ui.py`, `ui/controllers/main_controller.py`, `ui/pages/settings_page.py`, `ui/widgets/charts_mini.py`, `ui/widgets/chrome.py`, `ui/widgets/theme_preview.py`, `ui/windows/main_window.py`.

### `ui/themes/catalog.py`

فهرست پوسته‌های نام‌دار برنامه.

ارجاع داخلی: `ui/themes/tokens.py`.
واردکنندگان ایستا: `tests/test_v160_ui_polish.py`, `tests/test_v161_omniroute_font_theme.py`, `tests/test_v170_scanner_fonts_theme.py`, `tests/test_v170_signals_ui.py`, `tests/test_v171_chat_tool_steps.py`, `tests/test_v172_signal_ai_and_scan_ui.py`, `tests/test_v180_ai_status_card.py`, `tests/test_v180_custom_themes.py`, `tests/test_v196_fixes.py`, `ui/controllers/main_controller.py`, `ui/pages/settings_page.py`, `ui/themes/__init__.py`, `ui/themes/custom.py`, `ui/themes/theme_manager.py`, `ui/widgets/theme_card.py`.
- `def resolve_key` — L624–L638
- `def get_theme` — L641–L643
- `def list_themes` — L646–L648

### `ui/themes/custom.py`

پوسته‌های سفارشی کاربر.

ارجاع داخلی: `app/logging/__init__.py`, `ui/themes/catalog.py`, `ui/themes/tokens.py`.
واردکنندگان ایستا: `tests/test_v180_custom_themes.py`, `ui/controllers/main_controller.py`, `ui/widgets/theme_editor.py`.
- `def is_custom` — L78–L80
- `def slugify` — L83–L92
- `def _valid_colour` — L95–L97
- `def sanitise_overrides` — L100–L136
- `def build_tokens` — L139–L179
- `class CustomThemeStore` — L182–L329
- `def CustomThemeStore.__init__` — L192–L194
- `def CustomThemeStore._path_for` — L197–L199
- `def CustomThemeStore.load_all` — L201–L222
- `def CustomThemeStore._register` — L224–L243
- `def CustomThemeStore.save` — L245–L281
- `def CustomThemeStore.delete` — L283–L300
- `def CustomThemeStore.read` — L302–L313
- `def CustomThemeStore.registered` — L317–L319
- `def CustomThemeStore._unique_key` — L321–L329

### `ui/themes/fonts.py`

بارگذاری و انتخاب قلم‌های فارسی برنامه.

ارجاع داخلی: `app/logging/__init__.py`.
واردکنندگان ایستا: `main.py`, `tests/test_v161_omniroute_font_theme.py`, `tests/test_v170_scanner_fonts_theme.py`, `ui/controllers/main_controller.py`, `ui/pages/settings_page.py`, `ui/themes/__init__.py`, `ui/themes/stylesheet.py`, `ui/themes/theme_manager.py`.
- `class FontChoice` — L51–L73
- `def load_application_fonts` — L145–L205
- `def load_application_fonts._register` — L168–L179
- `def loaded_families` — L208–L210
- `def resolve_font_key` — L213–L221
- `def font_stack` — L224–L226
- `def font_name` — L229–L232
- `def list_fonts` — L235–L237
- `def is_available` — L240–L257
- `def apply_default_font` — L260–L292

### `ui/themes/stylesheet.py`

ساخت برگهٔ سبک (QSS) از روی توکن‌های پوسته.

ارجاع داخلی: `ui/themes/fonts.py`, `ui/themes/tokens.py`.
واردکنندگان ایستا: `tests/test_v160_ui_polish.py`, `tests/test_v161_omniroute_font_theme.py`, `tests/test_v170_scanner_fonts_theme.py`, `tests/test_v180_ai_status_card.py`, `tests/test_v180_custom_themes.py`, `ui/themes/__init__.py`, `ui/themes/theme_manager.py`.
- `def _arrow_data_uri` — L570–L585
- `def build_stylesheet` — L588–L604

### `ui/themes/theme_manager.py`

مدیریت پوسته ظاهری برنامه.

ارجاع داخلی: `app/core/constants.py`, `app/logging/__init__.py`, `ui/themes/catalog.py`, `ui/themes/fonts.py`, `ui/themes/stylesheet.py`, `ui/themes/tokens.py`.
واردکنندگان ایستا: `tests/test_exchange_login_flow.py`, `tests/test_exchange_switching.py`, `tests/test_v161_omniroute_font_theme.py`, `ui/themes/__init__.py`.
- `class ThemeManager` — L54–L274
- `def ThemeManager.__init__` — L66–L72
- `def ThemeManager.current` — L78–L80
- `def ThemeManager.tokens` — L83–L85
- `def ThemeManager.palette` — L88–L95
- `def ThemeManager.is_dark` — L98–L100
- `def ThemeManager.font_scale` — L103–L105
- `def ThemeManager.compact_mode` — L108–L110
- `def ThemeManager.font_key` — L113–L115
- `def ThemeManager.font_stack` — L118–L120
- `def ThemeManager.available_fonts` — L123–L125
- `def ThemeManager.set_font_family` — L127–L144
- `def ThemeManager.available` — L150–L152
- `def ThemeManager.display_name` — L155–L158
- `def ThemeManager.tokens_for` — L161–L163
- `def ThemeManager.detect_system_theme` — L169–L190
- `def ThemeManager.resolve` — L192–L202
- `def ThemeManager.stylesheet` — L207–L209
- `def ThemeManager.apply` — L211–L226
- `def ThemeManager.set_font_scale` — L228–L243
- `def ThemeManager.set_compact_mode` — L245–L251
- `def ThemeManager._effective` — L256–L259
- `def ThemeManager._reapply` — L261–L274
- `def apply_theme` — L281–L283

### `ui/themes/tokens.py`

توکن‌های سیستم طراحی.

واردکنندگان ایستا: `tests/test_themes.py`, `ui/themes/__init__.py`, `ui/themes/catalog.py`, `ui/themes/custom.py`, `ui/themes/stylesheet.py`, `ui/themes/theme_manager.py`, `ui/widgets/charts_mini.py`, `ui/widgets/theme_preview.py`.
- `class ColorTokens` — L21–L74
- `class MetricTokens` — L78–L105
- `class EffectTokens` — L109–L121
- `class ThemeTokens` — L125–L194
- `def ThemeTokens.as_format_map` — L136–L155
- `def ThemeTokens.scaled` — L157–L182
- `def ThemeTokens.scaled.scale` — L167–L168
- `def ThemeTokens.compact` — L184–L194

### `ui/widgets/__init__.py`

ویجت‌های مشترک و قابل استفاده مجدد در صفحات مختلف.

ارجاع داخلی: `ui/widgets/ai_status_card.py`, `ui/widgets/avatar.py`, `ui/widgets/charts_mini.py`, `ui/widgets/chrome.py`, `ui/widgets/common.py`, `ui/widgets/controls.py`, `ui/widgets/performance_view.py`, `ui/widgets/table_toolbar.py`, `ui/widgets/theme_card.py`, `ui/widgets/theme_preview.py`, `ui/widgets/trend_cell.py`, `ui/widgets/watchlist_panel.py`.
واردکنندگان ایستا: `tests/test_ui_wiring.py`, `tests/test_v155_ui_and_ai.py`, `ui/controllers/main_controller.py`, `ui/dialogs/analysis_dialog.py`, `ui/dialogs/auth_dialog.py`, `ui/dialogs/coin_detail_dialog.py`, `ui/dialogs/signal_detail_dialog.py`, `ui/dialogs/trading_dialogs.py`, `ui/pages/analysis_page.py`, `ui/pages/base_page.py`, `ui/pages/chat_page.py`, `ui/pages/dashboard_page.py`, `ui/pages/help_page.py`, `ui/pages/markets_page.py`, `ui/pages/prediction_page.py`, `ui/pages/reports_page.py`, `ui/pages/settings_page.py`, `ui/pages/signals_page.py`, `ui/pages/trades_page.py`, `ui/pages/wallet_page.py`, `ui/windows/main_window.py`.

### `ui/widgets/ai_status_card.py`

کارت وضعیت هوش مصنوعی در نوار کناری.

ارجاع داخلی: `ui/icons/__init__.py`, `ui/widgets/controls.py`.
واردکنندگان ایستا: `tests/test_v180_ai_status_card.py`, `ui/widgets/__init__.py`, `ui/widgets/chrome.py`.
- `def short_model_name` — L45–L62
- `class AIStatusCard : QFrame` — L65–L210
- `def AIStatusCard.__init__` — L78–L128
- `def AIStatusCard.state` — L132–L134
- `def AIStatusCard.set_status` — L136–L166
- `def AIStatusCard.set_checking` — L168–L179
- `def AIStatusCard.apply_theme` — L181–L185
- `def AIStatusCard._paint_dot` — L188–L204
- `def AIStatusCard.mousePressEvent` — L206–L210

### `ui/widgets/arrangeable.py`

چیدمان قابل جابه‌جایی صفحات.

ارجاع داخلی: `ui/widgets/common.py`, `ui/widgets/controls.py`.
واردکنندگان ایستا: `tests/test_v180_arrangeable_layout.py`, `ui/pages/dashboard_page.py`.
- `class LayoutBlock : QWidget` — L41–L164
- `def LayoutBlock.__init__` — L53–L102
- `def LayoutBlock.key` — L106–L108
- `def LayoutBlock.content_visible` — L111–L113
- `def LayoutBlock.set_arrange_mode` — L115–L124
- `def LayoutBlock.set_content_visible` — L126–L138
- `def LayoutBlock.set_edges` — L140–L143
- `def LayoutBlock.retranslate` — L145–L154
- `def LayoutBlock.set_title` — L156–L159
- `def LayoutBlock._on_visible_toggled` — L162–L164
- `class ArrangeableContainer : QWidget` — L167–L344
- `def ArrangeableContainer.__init__` — L180–L189
- `def ArrangeableContainer.order` — L193–L195
- `def ArrangeableContainer.blocks` — L198–L200
- `def ArrangeableContainer.arrange_mode` — L203–L205
- `def ArrangeableContainer.add_block` — L207–L217
- `def ArrangeableContainer.set_arrange_mode` — L219–L224
- `def ArrangeableContainer.move_up` — L226–L228
- `def ArrangeableContainer.move_down` — L230–L232
- `def ArrangeableContainer.serialise` — L234–L245
- `def ArrangeableContainer.apply_state` — L247–L282
- `def ArrangeableContainer.reset` — L284–L294
- `def ArrangeableContainer.retranslate` — L296–L299
- `def ArrangeableContainer._move` — L302–L314
- `def ArrangeableContainer._relayout` — L316–L333
- `def ArrangeableContainer._sync_edges` — L335–L340
- `def ArrangeableContainer._on_visibility_changed` — L342–L344

### `ui/widgets/avatar.py`

نشان کاربر (آواتار) برای نوار بالایی.

واردکنندگان ایستا: `ui/widgets/__init__.py`, `ui/widgets/chrome.py`.
- `class Avatar : QWidget` — L23–L106
- `def Avatar.__init__` — L33–L48
- `def Avatar.set_user` — L53–L58
- `def Avatar.apply_theme` — L60–L69
- `def Avatar.paintEvent` — L74–L106

### `ui/widgets/charts_mini.py`

نمودارهای کوچک و بدون وابستگی: اسپارک‌لاین، حلقهٔ اطمینان، دونات و نمودار مساحتی.

ارجاع داخلی: `ui/themes/__init__.py`, `ui/themes/tokens.py`.
واردکنندگان ایستا: `ui/pages/prediction_page.py`, `ui/widgets/__init__.py`, `ui/widgets/common.py`, `ui/widgets/controls.py`, `ui/widgets/trend_cell.py`.
- `class ThemedWidget : QWidget` — L27–L50
- `def ThemedWidget.__init__` — L34–L36
- `def ThemedWidget.apply_theme` — L38–L41
- `def ThemedWidget.theme` — L44–L46
- `def ThemedWidget._color` — L48–L50
- `class Sparkline : ThemedWidget` — L53–L165
- `def Sparkline.__init__` — L65–L91
- `def Sparkline.set_values` — L93–L110
- `def Sparkline.clear` — L112–L114
- `def Sparkline.paintEvent` — L116–L165
- `class ConfidenceRing : ThemedWidget` — L168–L258
- `def ConfidenceRing.__init__` — L180–L193
- `def ConfidenceRing.set_value` — L195–L204
- `def ConfidenceRing._ring_color` — L206–L212
- `def ConfidenceRing.paintEvent` — L214–L258
- `class DonutChart : ThemedWidget` — L261–L332
- `def DonutChart.__init__` — L270–L283
- `def DonutChart.set_segments` — L285–L294
- `def DonutChart.paintEvent` — L296–L332
- `class AreaChart : ThemedWidget` — L335–L434
- `def AreaChart.__init__` — L344–L350
- `def AreaChart.set_series` — L352–L371
- `def AreaChart.paintEvent` — L373–L434
- `class QuantileFan : ThemedWidget` — L440–L583
- `def QuantileFan.__init__` — L455–L460
- `def QuantileFan.set_points` — L462–L491
- `def QuantileFan.clear` — L493–L495
- `def QuantileFan.paintEvent` — L497–L583
- `def QuantileFan.paintEvent.y_of` — L530–L531

### `ui/widgets/chrome.py`

پوستهٔ بیرونی پنجره: نوار بالایی، نوار کناری آیکون‌دار، کارت وضعیت اتصال و نوار ویژگی‌ها.

ارجاع داخلی: `ui/icons/__init__.py`, `ui/icons/registry.py`, `ui/themes/__init__.py`, `ui/widgets/ai_status_card.py`, `ui/widgets/avatar.py`, `ui/widgets/controls.py`.
واردکنندگان ایستا: `tests/test_icons_search_theme.py`, `tests/test_v160_ui_polish.py`, `tests/test_v180_ai_status_card.py`, `ui/widgets/__init__.py`.
- `class SearchBox : QLineEdit` — L38–L119
- `def SearchBox.__init__` — L50–L76
- `def SearchBox.set_icon_color` — L78–L80
- `def SearchBox.set_suggestions` — L82–L96
- `def SearchBox._on_suggestion_chosen` — L98–L101
- `def SearchBox._on_return` — L103–L114
- `def SearchBox.focus_and_select` — L116–L119
- `class NotificationButton : QToolButton` — L122–L163
- `def NotificationButton.__init__` — L129–L140
- `def NotificationButton.set_count` — L142–L147
- `def NotificationButton.set_badge_color` — L149–L153
- `def NotificationButton._place_badge` — L155–L158
- `def NotificationButton.resizeEvent` — L160–L163
- `class UserMenuButton : QToolButton` — L166–L284
- `def UserMenuButton.__init__` — L179–L204
- `def UserMenuButton.apply_theme` — L206–L213
- `def UserMenuButton._sync_avatar_geometry` — L215–L242
- `def UserMenuButton.resizeEvent` — L244–L247
- `def UserMenuButton.set_labels` — L249–L261
- `def UserMenuButton.set_user` — L263–L284
- `class TopBar : QFrame` — L287–L401
- `def TopBar.__init__` — L300–L360
- `def TopBar.set_page` — L362–L366
- `def TopBar.apply_theme` — L368–L388
- `def TopBar.set_placeholders` — L390–L401
- `class ConnectionCard : QFrame` — L404–L465
- `def ConnectionCard.__init__` — L413–L441
- `def ConnectionCard.set_state` — L443–L454
- `def ConnectionCard.apply_theme` — L456–L460
- `def ConnectionCard.mousePressEvent` — L462–L465
- `class IconSidebar : QFrame` — L468–L651
- `def IconSidebar.__init__` — L483–L533
- `def IconSidebar.apply_theme` — L535–L549
- `def IconSidebar.set_brand` — L551–L555
- `def IconSidebar.set_items` — L557–L585
- `def IconSidebar.set_labels` — L587–L590
- `def IconSidebar.set_collapsed` — L592–L604
- `def IconSidebar.is_collapsed` — L606–L608
- `def IconSidebar.set_current` — L610–L614
- `def IconSidebar._highlight_current` — L616–L627
- `def IconSidebar._render_labels` — L629–L646
- `def IconSidebar._on_clicked` — L648–L651
- `class FeatureStrip : QFrame` — L654–L709
- `def FeatureStrip.__init__` — L663–L673
- `def FeatureStrip.set_features` — L675–L700
- `def FeatureStrip.apply_theme` — L702–L709

### `ui/widgets/common.py`

ویجت‌های پایه مشترک.

ارجاع داخلی: `ui/widgets/charts_mini.py`.
واردکنندگان ایستا: `tests/test_v172_signal_ai_and_scan_ui.py`, `ui/dialogs/password_reset_dialog.py`, `ui/pages/base_page.py`, `ui/widgets/__init__.py`, `ui/widgets/arrangeable.py`, `ui/widgets/performance_view.py`, `ui/widgets/table_toolbar.py`, `ui/widgets/theme_editor.py`, `ui/widgets/tutorial_view.py`, `ui/widgets/watchlist_panel.py`.
- `def make_title` — L27–L31
- `def make_button` — L34–L53
- `class RefreshButton : QPushButton` — L56–L129
- `def RefreshButton.__init__` — L78–L97
- `def RefreshButton.set_texts` — L99–L105
- `def RefreshButton.start_busy` — L107–L111
- `def RefreshButton.finish_busy` — L113–L125
- `def RefreshButton._restore` — L127–L129
- `class Card : QFrame` — L132–L163
- `def Card.__init__` — L139–L149
- `def Card.body` — L151–L153
- `def Card.add` — L155–L158
- `def Card.set_title` — L160–L163
- `class KeyValueRow : QWidget` — L166–L193
- `def KeyValueRow.__init__` — L169–L182
- `def KeyValueRow.set_value` — L184–L189
- `def KeyValueRow.set_key` — L191–L193
- `class StatusPill : QLabel` — L196–L213
- `def StatusPill.__init__` — L203–L206
- `def StatusPill.set_status` — L208–L213
- `class SignalCard : Card` — L216–L377
- `def SignalCard.__init__` — L224–L280
- `def SignalCard.apply_theme` — L282–L284
- `def SignalCard.set_labels` — L286–L297
- `def SignalCard.show_signal` — L299–L339
- `def SignalCard._render_forecast` — L341–L377
- `class HeaderBar : QWidget` — L380–L413
- `def HeaderBar.__init__` — L383–L402
- `def HeaderBar.add_action` — L404–L407
- `def HeaderBar.set_texts` — L409–L413
- `def configure_table` — L416–L434
- `def configure_button_column` — L454–L484
- `def center_numeric_inputs` — L487–L512
- `def harden_table` — L519–L551
- `def _fit_total_width` — L554–L561
- `class ResponsiveRow : QWidget` — L564–L614
- `def ResponsiveRow.__init__` — L572–L587
- `def ResponsiveRow.set_stacked` — L589–L591
- `def ResponsiveRow._apply` — L593–L610
- `def ResponsiveRow.reflow` — L612–L614

### `ui/widgets/controls.py`

کنترل‌های مشترک رابط کاربری: بخش‌بندی تایم‌فریم، کلید روشن/خاموش، نوار تراشه‌ها، کارت آمار، صفحه‌بندی و اعلان شناور.

ارجاع داخلی: `ui/widgets/charts_mini.py`.
واردکنندگان ایستا: `ui/dialogs/password_reset_dialog.py`, `ui/widgets/__init__.py`, `ui/widgets/ai_status_card.py`, `ui/widgets/arrangeable.py`, `ui/widgets/chrome.py`, `ui/widgets/performance_view.py`, `ui/widgets/position_calculator.py`, `ui/widgets/table_toolbar.py`, `ui/widgets/theme_card.py`, `ui/widgets/theme_editor.py`, `ui/widgets/tool_trail.py`, `ui/widgets/tutorial_view.py`, `ui/widgets/watchlist_panel.py`.
- `def set_role` — L39–L50
- `class SegmentedControl : QWidget` — L53–L135
- `def SegmentedControl.__init__` — L66–L85
- `def SegmentedControl.set_options` — L87–L109
- `def SegmentedControl.set_labels` — L111–L115
- `def SegmentedControl.current` — L117–L122
- `def SegmentedControl.set_current` — L124–L131
- `def SegmentedControl._on_clicked` — L133–L135
- `class ChipBar : QWidget` — L138–L208
- `def ChipBar.__init__` — L148–L164
- `def ChipBar.set_options` — L166–L183
- `def ChipBar.set_labels` — L185–L189
- `def ChipBar.selection` — L191–L193
- `def ChipBar.set_selection` — L195–L201
- `def ChipBar._on_clicked` — L203–L208
- `class ToggleSwitch : QAbstractButton` — L211–L292
- `def ToggleSwitch.__init__` — L224–L236
- `def ToggleSwitch.get_offset` — L238–L240
- `def ToggleSwitch.set_offset` — L242–L245
- `def ToggleSwitch.apply_theme` — L249–L255
- `def ToggleSwitch._animate` — L257–L262
- `def ToggleSwitch.setChecked` — L264–L268
- `def ToggleSwitch.paintEvent` — L270–L288
- `def ToggleSwitch.sizeHint` — L290–L292
- `class StatCard : QFrame` — L295–L386
- `def StatCard.__init__` — L304–L344
- `def StatCard.set_data` — L346–L382
- `def StatCard.apply_theme` — L384–L386
- `class TickerStrip : QFrame` — L389–L460
- `def TickerStrip.__init__` — L398–L405
- `def TickerStrip.set_items` — L407–L450
- `def TickerStrip.apply_theme` — L452–L460
- `class Pagination : QWidget` — L463–L518
- `def Pagination.__init__` — L472–L497
- `def Pagination.configure` — L499–L505
- `def Pagination.page` — L507–L509
- `def Pagination.set_page` — L511–L518
- `class Toast : QFrame` — L521–L581
- `def Toast.__init__` — L538–L563
- `def Toast.show_message` — L566–L581
- `class StatusDot : QLabel` — L584–L613
- `def StatusDot.__init__` — L591–L595
- `def StatusDot.set_status` — L597–L600
- `def StatusDot.paintEvent` — L602–L613
- `class EmptyState : QWidget` — L616–L672
- `def EmptyState.__init__` — L626–L655
- `def EmptyState.configure` — L657–L672

### `ui/widgets/performance_view.py`

نمای عملکرد واقعی سیگنال‌ها.

ارجاع داخلی: `localization/__init__.py`, `ui/widgets/common.py`, `ui/widgets/controls.py`.
واردکنندگان ایستا: `tests/test_v191_outcome_tracking.py`, `ui/widgets/__init__.py`.
- `class PerformanceView : QWidget` — L74–L436
- `def PerformanceView.__init__` — L82–L98
- `def PerformanceView._build_controls` — L102–L125
- `def PerformanceView._build_stats` — L127–L137
- `def PerformanceView._build_breakdown` — L139–L162
- `def PerformanceView._build_history` — L164–L178
- `def PerformanceView._apply_headers` — L180–L206
- `def PerformanceView.selected_period` — L210–L216
- `def PerformanceView.set_performance` — L218–L249
- `def PerformanceView._format_factor` — L251–L264
- `def PerformanceView._fill_breakdown` — L266–L303
- `def PerformanceView._ltr` — L306–L313
- `def PerformanceView._breakdown_label` — L315–L326
- `def PerformanceView.set_history` — L328–L359
- `def PerformanceView._colourise` — L361–L371
- `def PerformanceView._colour_status` — L373–L379
- `def PerformanceView.set_status` — L381–L383
- `def PerformanceView._on_period` — L387–L392
- `def PerformanceView._period_label` — L394–L398
- `def PerformanceView.apply_theme` — L400–L414
- `def PerformanceView.retranslate` — L416–L436

### `ui/widgets/position_calculator.py`

ماشین‌حساب حجم پوزیشن.

ارجاع داخلی: `signals/position_sizing.py`, `ui/widgets/controls.py`.
واردکنندگان ایستا: `tests/test_v190_position_sizing.py`, `ui/dialogs/signal_detail_dialog.py`.
- `class PriceSpinBox : QDoubleSpinBox` — L55–L68
- `def PriceSpinBox.textFromValue` — L64–L68
- `class PositionCalculator : QWidget` — L71–L347
- `def PositionCalculator.__init__` — L84–L106
- `def PositionCalculator._build_inputs` — L109–L147
- `def PositionCalculator._money_input` — L149–L162
- `def PositionCalculator._percent_input` — L164–L173
- `def PositionCalculator._build_results` — L175–L202
- `def PositionCalculator.plan` — L206–L208
- `def PositionCalculator.set_capital` — L210–L213
- `def PositionCalculator.set_risk_percent` — L215–L218
- `def PositionCalculator.load_signal` — L220–L247
- `def PositionCalculator.recalculate` — L249–L265
- `def PositionCalculator.result_value` — L267–L270
- `def PositionCalculator.retranslate` — L272–L287
- `def PositionCalculator._set_silently` — L290–L296
- `def PositionCalculator._render` — L298–L340
- `def PositionCalculator._number` — L342–L347
- `def _trim` — L350–L360
- `def _first_number` — L363–L372

### `ui/widgets/responsive_grid.py`

شبکهٔ بازچینش‌شونده.

واردکنندگان ایستا: `tests/test_v170_signals_ui.py`, `ui/pages/settings_page.py`.
- `class ResponsiveGrid : QWidget` — L26–L143
- `def ResponsiveGrid.__init__` — L29–L48
- `def ResponsiveGrid.add_widget` — L51–L54
- `def ResponsiveGrid.set_widgets` — L56–L59
- `def ResponsiveGrid.items` — L61–L63
- `def ResponsiveGrid.column_count` — L65–L67
- `def ResponsiveGrid.columns_for_width` — L69–L81
- `def ResponsiveGrid._relayout` — L84–L105
- `def ResponsiveGrid.minimumSizeHint` — L107–L132
- `def ResponsiveGrid.sizeHint` — L134–L138
- `def ResponsiveGrid.resizeEvent` — L140–L143

### `ui/widgets/table_toolbar.py`

نوار ابزار بالای جدول‌ها: تمام‌صفحه، خروجی و جست‌وجو.

ارجاع داخلی: `ui/widgets/common.py`, `ui/widgets/controls.py`.
واردکنندگان ایستا: `tests/test_v180_table_fullscreen.py`, `tests/test_v194_performance.py`, `ui/pages/base_page.py`, `ui/widgets/__init__.py`.
- `class FullscreenTableDialog : QDialog` — L40–L109
- `def FullscreenTableDialog.__init__` — L50–L90
- `def FullscreenTableDialog.restore` — L92–L104
- `def FullscreenTableDialog.closeEvent` — L106–L109
- `class TableToolbar : QWidget` — L112–L354
- `def TableToolbar.__init__` — L126–L160
- `def TableToolbar.add_widget` — L163–L165
- `def TableToolbar.is_fullscreen` — L168–L170
- `def TableToolbar.set_title` — L172–L174
- `def TableToolbar.toggle_fullscreen` — L176–L181
- `def TableToolbar.enter_fullscreen` — L183–L216
- `def TableToolbar.exit_fullscreen` — L218–L221
- `def TableToolbar.table_to_rows` — L224–L254
- `def TableToolbar.export_csv` — L256–L294
- `def TableToolbar.write_csv` — L297–L308
- `def TableToolbar.retranslate` — L310–L312
- `def TableToolbar._on_dialog_finished` — L315–L319
- `def TableToolbar._resolve_title` — L321–L343
- `def TableToolbar._sync_button` — L345–L354
- `def attach_table_toolbar` — L357–L384
- `def attach_table_toolbars` — L387–L410

### `ui/widgets/theme_card.py`

کارت انتخاب پوسته.

ارجاع داخلی: `ui/icons/__init__.py`, `ui/themes/catalog.py`, `ui/widgets/controls.py`.
واردکنندگان ایستا: `tests/test_v170_signals_ui.py`, `ui/pages/settings_page.py`, `ui/widgets/__init__.py`.
- `class ThemeSwatch : QWidget` — L20–L94
- `def ThemeSwatch.__init__` — L23–L35
- `def ThemeSwatch.hasHeightForWidth` — L37–L39
- `def ThemeSwatch.heightForWidth` — L41–L49
- `def ThemeSwatch.set_theme` — L51–L54
- `def ThemeSwatch.paintEvent` — L56–L94
- `class ThemeCard : QFrame` — L97–L180
- `def ThemeCard.__init__` — L107–L147
- `def ThemeCard.key` — L150–L152
- `def ThemeCard.set_texts` — L154–L160
- `def ThemeCard.set_selected` — L162–L174
- `def ThemeCard.mousePressEvent` — L176–L180

### `ui/widgets/theme_editor.py`

ویرایشگر زندهٔ پوسته.

ارجاع داخلی: `ui/themes/custom.py`, `ui/widgets/common.py`, `ui/widgets/controls.py`.
واردکنندگان ایستا: `tests/test_v180_custom_themes.py`, `ui/pages/settings_page.py`.
- `class ColorButton : QPushButton` — L65–L116
- `def ColorButton.__init__` — L76–L83
- `def ColorButton.token` — L86–L88
- `def ColorButton.color` — L91–L93
- `def ColorButton.set_color` — L95–L102
- `def ColorButton._choose` — L104–L116
- `class ThemeEditor : QWidget` — L119–L355
- `def ThemeEditor.__init__` — L134–L181
- `def ThemeEditor.overrides` — L185–L187
- `def ThemeEditor.load_theme` — L189–L225
- `def ThemeEditor.clear_overrides` — L227–L231
- `def ThemeEditor.retranslate` — L233–L241
- `def ThemeEditor._add_group_title` — L244–L249
- `def ThemeEditor._new_form` — L251–L259
- `def ThemeEditor._token_label` — L261–L265
- `def ThemeEditor._build_colour_section` — L267–L276
- `def ThemeEditor._build_metric_section` — L278–L304
- `def ThemeEditor._build_effect_section` — L306–L316
- `def ThemeEditor._on_colour_picked` — L319–L323
- `def ThemeEditor._on_metric_changed` — L325–L330
- `def ThemeEditor._on_effect_changed` — L332–L336
- `def ThemeEditor._record` — L338–L351
- `def ThemeEditor._emit` — L353–L355

### `ui/widgets/theme_preview.py`

نوار پیش‌نمایش پوسته.

ارجاع داخلی: `ui/themes/__init__.py`, `ui/themes/tokens.py`.
واردکنندگان ایستا: `ui/pages/settings_page.py`, `ui/widgets/__init__.py`.
- `class ThemePreview : QWidget` — L22–L97
- `def ThemePreview.__init__` — L31–L36
- `def ThemePreview.show_theme` — L38–L42
- `def ThemePreview.paintEvent` — L44–L97

### `ui/widgets/tool_trail.py`

نمایش گام‌های ابزار زیر پاسخ دستیار.

ارجاع داخلی: `ui/widgets/controls.py`.
واردکنندگان ایستا: `tests/test_v171_chat_tool_steps.py`, `ui/pages/chat_page.py`.
- `class ToolStep : QFrame` — L48–L203
- `def ToolStep.__init__` — L58–L110
- `def ToolStep.tool_name` — L114–L116
- `def ToolStep.state` — L119–L121
- `def ToolStep.expanded` — L124–L126
- `def ToolStep.set_result` — L128–L132
- `def ToolStep.set_arguments` — L134–L137
- `def ToolStep.set_display_name` — L139–L147
- `def ToolStep.apply_theme` — L149–L152
- `def ToolStep.toggle` — L154–L159
- `def ToolStep._refresh` — L162–L191
- `def ToolStep._colour` — L193–L197
- `def ToolStep.mousePressEvent` — L199–L203
- `class ToolTrail : QWidget` — L206–L290
- `def ToolTrail.__init__` — L215–L225
- `def ToolTrail.set_display_names` — L228–L232
- `def ToolTrail.begin_step` — L234–L249
- `def ToolTrail.finish_step` — L251–L269
- `def ToolTrail.steps` — L271–L273
- `def ToolTrail.clear` — L275–L284
- `def ToolTrail.apply_theme` — L286–L290

### `ui/widgets/trend_cell.py`

سلول «روند» جدول بازارها.

ارجاع داخلی: `ui/widgets/charts_mini.py`.
واردکنندگان ایستا: `tests/test_v153_fixes.py`, `ui/widgets/__init__.py`.
- `class TrendCell : QWidget` — L32–L128
- `def TrendCell.__init__` — L41–L60
- `def TrendCell.set_trend` — L65–L101
- `def TrendCell._apply_color` — L103–L110
- `def TrendCell.apply_theme` — L115–L124
- `def TrendCell.retranslate` — L126–L128

### `ui/widgets/tutorial_view.py`

نمای آموزش معامله‌گری.

ارجاع داخلی: `ui/widgets/common.py`, `ui/widgets/controls.py`.
واردکنندگان ایستا: `tests/test_v180_tutorial.py`, `ui/pages/help_page.py`.
- `class TutorialView : QWidget` — L42–L250
- `def TutorialView.__init__` — L45–L122
- `def TutorialView.chapters` — L126–L128
- `def TutorialView.current_index` — L130–L135
- `def TutorialView.select_chapter` — L137–L145
- `def TutorialView.go_next` — L147–L151
- `def TutorialView.go_previous` — L153–L157
- `def TutorialView.reload` — L159–L180
- `def TutorialView._apply_filter` — L183–L209
- `def TutorialView._show_empty` — L211–L219
- `def TutorialView._on_row_changed` — L221–L243
- `def TutorialView._localised_number` — L245–L250

### `ui/widgets/watchlist_panel.py`

مدیریت فهرست‌های دیده‌بانی (مورد ۵.۳ نقشهٔ راه).

ارجاع داخلی: `app/core/constants.py`, `localization/__init__.py`, `ui/widgets/common.py`, `ui/widgets/controls.py`.
واردکنندگان ایستا: `tests/test_v192_watchlist.py`, `ui/widgets/__init__.py`.
- `class WatchlistPanel : QWidget` — L48–L353
- `def WatchlistPanel.__init__` — L68–L91
- `def WatchlistPanel._build_list_row` — L95–L118
- `def WatchlistPanel._build_action_row` — L120–L145
- `def WatchlistPanel._build_table` — L147–L156
- `def WatchlistPanel._apply_headers` — L158–L167
- `def WatchlistPanel.set_lists` — L171–L193
- `def WatchlistPanel._list_label` — L195–L200
- `def WatchlistPanel.set_items` — L202–L224
- `def WatchlistPanel.current_list` — L226–L229
- `def WatchlistPanel.selected_symbol` — L231–L236
- `def WatchlistPanel._update_buttons` — L238–L242
- `def WatchlistPanel._on_list_changed` — L246–L253
- `def WatchlistPanel._on_double_click` — L255–L258
- `def WatchlistPanel._ask_new_name` — L260–L266
- `def WatchlistPanel._ask_rename` — L268–L280
- `def WatchlistPanel._confirm_delete` — L282–L291
- `def WatchlistPanel._move` — L293–L297
- `def WatchlistPanel._remove_selected` — L299–L303
- `def WatchlistPanel._ask_note` — L305–L319
- `def WatchlistPanel.select_symbol` — L321–L337
- `def WatchlistPanel.retranslate` — L339–L353

### `ui/windows/__init__.py`

پنجره‌های سطح بالای برنامه.

ارجاع داخلی: `ui/windows/main_window.py`.
واردکنندگان ایستا: `main.py`, `tests/test_new_pages.py`, `tools/preview_shot.py`, `tools/sweep_ui.py`, `ui/controllers/main_controller.py`.

### `ui/windows/main_window.py`

پنجره اصلی برنامه.

ارجاع داخلی: `app/core/constants.py`, `app/core/timeutil.py`, `app/logging/__init__.py`, `localization/__init__.py`, `ui/pages/__init__.py`, `ui/themes/__init__.py`, `ui/widgets/__init__.py`.
واردکنندگان ایستا: `tests/test_exchange_login_flow.py`, `tests/test_exchange_switching.py`, `tests/test_icons_search_theme.py`, `ui/windows/__init__.py`.
- `class MainWindow : QMainWindow` — L87–L578
- `def MainWindow.__init__` — L120–L141
- `def MainWindow._build_ui` — L146–L202
- `def MainWindow._build_status_bar` — L204–L238
- `def MainWindow._register_shortcuts` — L240–L267
- `def MainWindow._register_shortcuts.bind` — L249–L252
- `def MainWindow._connect_signals` — L269–L303
- `def MainWindow.go_to_page` — L308–L317
- `def MainWindow.page_index` — L319–L324
- `def MainWindow.page` — L326–L328
- `def MainWindow.focus_search` — L330–L332
- `def MainWindow.toggle_sidebar` — L334–L336
- `def MainWindow.toggle_focus_mode` — L338–L340
- `def MainWindow.set_focus_mode` — L342–L350
- `def MainWindow.resizeEvent` — L352–L367
- `def MainWindow.apply_direction` — L372–L397
- `def MainWindow.apply_theme_tokens` — L399–L415
- `def MainWindow.retranslate` — L417–L429
- `def MainWindow._retranslate_chrome` — L431–L459
- `def MainWindow._force_ltr_widgets` — L461–L470
- `def MainWindow._cycle_theme` — L472–L486
- `def MainWindow.set_connection_indicator` — L491–L497
- `def MainWindow.set_connection_card` — L499–L510
- `def MainWindow.set_market_count` — L512–L521
- `def MainWindow.set_user` — L523–L528
- `def MainWindow.set_notification_count` — L530–L532
- `def MainWindow.set_status` — L534–L536
- `def MainWindow._sync_topbar_title` — L541–L550
- `def MainWindow._on_feature_clicked` — L552–L557
- `def MainWindow._producer_text` — L559–L561
- `def MainWindow._tick_clock` — L563–L578

## اتصال‌های صریح Qt در کنترلر اصلی

این خطوط از `.connect(...)` در `ui/controllers/main_controller.py` استخراج شده‌اند. اتصال‌های داخلی صفحات/ویجت‌ها در سورس خودشان هستند؛ `.connect()` شبکه با این اتصال‌های Qt متفاوت است.

```python
# L222
self._refresh_timer.timeout.connect(self.refresh_dashboard)
# L228
self._live_timer.timeout.connect(self._flush_live_updates)
# L232
self._fiat_timer.timeout.connect(self.refresh_fiat_rate)
# L240
self._ai_status_timer.timeout.connect(self.refresh_ai_status)
# L249
self.prediction.refresh_requested.connect(self.run_prediction_report)
# L250
self.analysis.symbol_combo.currentTextChanged.connect(self._sync_prediction_symbol)
# L253
self.dashboard.refresh_button.clicked.connect(self.refresh_dashboard)
# L254
self.markets.refresh_button.clicked.connect(self.refresh_markets)
# L255
self.markets.watchlist_button.clicked.connect(self.add_to_watchlist)
# L256
self.markets.watchlist_toggled.connect(self._on_watchlist_toggled)
# L259
panel.list_selected.connect(self._on_watchlist_list_selected)
# L260
panel.list_created.connect(self._create_watchlist)
# L261
panel.list_renamed.connect(self._rename_watchlist)
# L262
panel.list_deleted.connect(self._delete_watchlist)
# L263
panel.symbol_moved.connect(self._move_watchlist_symbol)
# L264
panel.symbol_removed.connect(self._remove_watchlist_symbol)
# L265
panel.note_changed.connect(self._save_watchlist_note)
# L266
panel.symbol_activated.connect(self._open_watchlist_symbol)
# L267
self.markets.table.itemDoubleClicked.connect(self._on_market_double_clicked)
# L270
self.dashboard.signals_table.cellClicked.connect(self._on_signal_cell_clicked)
# L271
self.signals.history_table.cellDoubleClicked.connect(self._on_history_double_clicked)
# L274
self.settings_page.exchange_changed.connect(self._on_exchange_selected)
# L275
self.settings_page.ai_provider_changed.connect(self._on_ai_provider_selected)
# L276
self.settings_page.test_ai_button.clicked.connect(self.test_ai_connection)
# L277
self.settings_page.doctor_button.clicked.connect(self.run_ollama_doctor)
# L278
self.settings_page.check_update_button.clicked.connect(self.check_for_update)
# L279
self.settings_page.install_update_button.clicked.connect(self.install_update)
# L281
self.settings_page.theme_preview_requested.connect(self.change_theme)
# L282
self.settings_page.font_scale_changed.connect(self._on_font_scale_changed)
# L283
self.settings_page.compact_mode_changed.connect(self._on_compact_mode_changed)
# L284
self.settings_page.font_family_changed.connect(self.change_font_family)
# L286
self.settings_page.theme_tokens_changed.connect(self.preview_theme_tokens)
# L287
self.settings_page.custom_theme_save_requested.connect(self.save_custom_theme)
# L288
self.settings_page.custom_theme_delete_requested.connect(self.delete_custom_theme)
# L289
self.settings_page.theme_combo.currentIndexChanged.connect(self._on_theme_combo_changed)
# L292
self.settings_page.load_models_button.clicked.connect(self.load_ai_models)
# L294
self.chat.message_sent.connect(self.send_chat_message)
# L297
self.chat_stream_delta.connect(self.chat.stream_delta)
# L299
self.chat_tool_started.connect(self._on_chat_tool_started)
# L300
self.chat_tool_finished.connect(self._on_chat_tool_finished)
# L301
self.scan_progress_changed.connect(self.signals.set_scan_progress)
# L302
self.auto_trade_event.connect(self._handle_auto_trade_event)
# L303
self.chat.action_requested.connect(self._on_chat_action)
# L304
self.chat.chat_cleared.connect(self._on_chat_cleared)
# L305
self.chat.conversation_selected.connect(self.open_conversation)
# L306
self.chat.conversation_deleted.connect(self.delete_conversation)
# L307
self.chat.new_conversation_requested.connect(self.start_new_conversation)
# L308
self.chat.conversation_renamed.connect(self.rename_conversation)
# L310
self.dashboard.coin_activated.connect(self.show_coin_details)
# L311
self.markets.coin_activated.connect(self.show_coin_details)
# L313
self.signals.analysis_requested.connect(self.show_signal_analysis)
# L315
self.dashboard.layout_changed.connect(self.save_dashboard_layout)
# L319
ai_card.clicked.connect(self.open_ai_settings)
# L321
self.analysis.run_button.clicked.connect(self.run_analysis)
# L322
self.analysis.indicator_toggled.connect(self._on_indicator_toggled)
# L323
self.signals.generate_button.clicked.connect(self.generate_signal)
# L324
self.signals.scan_requested.connect(self.scan_market)
# L325
self.signals.auto_scan_changed.connect(self.save_auto_scan_config)
# L326
self.signals.auto_scan_run_now.connect(self.run_auto_scan_now)
# L327
self.signals.scan_stop_requested.connect(self.stop_market_scan)
# L328
self.signals.scan_ai_requested.connect(self.analyze_scanned_symbol)
# L329
self.signals.scan_detail_requested.connect(self.show_scanned_signal_detail)
# L330
self.reports.generate_button.clicked.connect(self.generate_report)
# L332
self.performance.refresh_requested.connect(self.refresh_outcomes_now)
# L333
self.performance.period_changed.connect(lambda _days: self._refresh_outcome_view())
# L336
self.reports.scorecard_refresh_requested.connect(self.refresh_scorecard)
# L338
self.reports.scorecard_auto_changed.connect(self.save_scorecard_auto)
# L339
self.settings_page.save_button.clicked.connect(self.save_settings)
# L340
self.settings_page.backup_button.clicked.connect(self.create_backup)
# L341
self.settings_page.restore_button.clicked.connect(self.restore_backup)
# L344
self.trades.filters_changed.connect(lambda _f: self.refresh_trades())
# L345
self.trades.refresh_requested.connect(self.refresh_trades)
# L346
self.trades.close_requested.connect(self.close_paper_trade)
# L347
self.trades.close_blocked.connect(lambda: self._toast(self.tr_.tr('trades.no_open_trade_selected'), level='warning'))
# L352
self.trades.auto_trade_toggled.connect(self.toggle_auto_trading)
# L353
self.trades.auto_settings_changed.connect(self.save_auto_trade_settings)
# L355
self.trades.auto_mode_changed.connect(self.change_auto_engine_mode)
# L356
self.trades.auto_symbol_changed.connect(self.on_auto_symbol_selected)
# L357
self.trades.close_position_requested.connect(self.close_auto_position)
# L358
self.trades.close_position_blocked.connect(lambda: self._toast(self.tr_.tr('trades.no_open_trade_selected'), level='warning'))
# L363
self.trades.emergency_exit_requested.connect(self.emergency_exit_positions)
# L365
self.trades.auto_timeframe_changed.connect(self.on_auto_timeframe_changed)
# L366
self.trades.opportunity_enter_requested.connect(self.on_opportunity_enter)
# L368
self.trades.chart_indicators_changed.connect(self.on_chart_indicators_changed)
# L369
self.trades.scanner_settings_saved.connect(self.on_scanner_settings_saved)
# L370
self.trades.selected_symbols_saved.connect(self.on_selected_symbols_saved)
# L371
self.trades.ai_opinion_requested.connect(self.on_ai_opinion_requested)
# L372
self.trades.notice_requested.connect(lambda message: self._toast(message))
# L377
self._terminal_timer.timeout.connect(self._refresh_auto_terminal)
# L383
self.trades.export_requested.connect(self.export_trades)
# L384
self.trades.clear_requested.connect(self.clear_trade_history)
# L385
self.markets.alert_requested.connect(self.create_price_alert)
# L386
self.wallet.sync_requested.connect(self.sync_wallet)
# L387
self.wallet.range_changed.connect(lambda _r: self.refresh_wallet())
# L390
self.window.login_requested.connect(self.show_auth_dialog)
# L391
self.window.logout_requested.connect(self.logout)
# L392
self.settings_page.account_add_requested.connect(self.add_exchange_account)
# L393
self.settings_page.account_test_requested.connect(self.test_exchange_account)
# L394
self.settings_page.account_remove_requested.connect(self.remove_exchange_account)
# L395
self.settings_page.account_activate_requested.connect(self.activate_exchange_account)
# L396
self.settings_page.account_selection_blocked.connect(lambda: self._toast(self.tr_.tr('settings.accounts.no_account_selected'), level='warning'))
# L401
self.settings_page.profile_save_requested.connect(self.save_profile)
# L402
self.settings_page.email_save_requested.connect(self.save_email_settings)
# L403
self.settings_page.email_test_requested.connect(self.test_email_connection)
# L404
self.settings_page.password_change_requested.connect(self.change_password)
# L405
self.settings_page.session_revoke_requested.connect(self.revoke_session)
# L406
self.settings_page.session_revoke_blocked.connect(lambda: self._toast(self.tr_.tr('settings.security.no_session_selected'), level='warning'))
# L411
self.settings_page.revoke_others_requested.connect(self.revoke_other_sessions)
# L414
self.window.search_requested.connect(self.global_search)
# L415
self.window.search_suggestion_activated.connect(self._on_search_suggestion)
# L416
self.window.refresh_requested.connect(self.refresh_current_page)
# L417
self.window.language_change_requested.connect(self.change_language)
# L418
self.window.theme_change_requested.connect(self.change_theme)
# L1706
self._auto_timer.timeout.connect(self._auto_scan_tick)
# L1933
self._chart_timer.timeout.connect(self._live_chart_tick)
# L1943
self._price_timer.timeout.connect(self._live_price_tick)
# L2041
self._trade_timer.timeout.connect(self._trade_monitor_tick)
# L2161
self._outcome_timer.timeout.connect(self._outcome_tick)
# L2534
dialog.pdf_requested.connect(lambda data: self._export_analysis_pdf(data, dialog))
# L2572
dialog.trade_requested.connect(self._on_trade_requested)
# L2576
dialog.ai_analysis_requested.connect(lambda _=None, value=symbol: self.analyze_scanned_symbol(value))
# L3006
dialog.analyze_requested.connect(lambda sym, tf: _act(self._coin_analyze, sym, tf))
# L3007
dialog.signal_requested.connect(lambda sym, tf: _act(self._coin_signal, sym, tf))
# L3008
dialog.chat_requested.connect(lambda sym, tf: _act(self._coin_chat, sym, tf))
# L3009
dialog.open_market_requested.connect(lambda sym: _act(self._coin_open_market, sym))
# L3010
dialog.watchlist_toggled.connect(self._coin_watchlist_toggled)
# L3172
dialog.pdf_requested.connect(lambda data: self._export_analysis_pdf(data, dialog))
# L3173
dialog.rerun_requested.connect(lambda data, dlg=dialog: self._rerun_signal_analysis(data, dlg))
# L3629
dialog.trade_requested.connect(self._on_trade_requested)
# L4603
dialog.authenticated.connect(lambda _user: self._on_user_changed())
# L5947
self._orderbook_timer.timeout.connect(self._refresh_orderbooks)
# L7263
self._keepalive_timer.timeout.connect(self._connection_keepalive)
# L7284
self._scorecard_timer.timeout.connect(self._scorecard_tick)
```

## مستندات و منابع غیرپایتونی

### `ADVANCED_FEATURES_FA.md`
عنوان‌های اصلی: پیشنهاد قابلیت‌ها و ابزارهای پیشرفته‌تر / معامله و ریسک / داده و سرعت / هوش مصنوعی / سنجش و ابزار / چیزی که عمداً پیشنهاد نمی‌شود

### `AI_HANDOVER.md`
عنوان‌های اصلی: تحویل پروژه به هوش مصنوعی بعدی / قانون کار با کاربر / برنامه چیست / اجرا / نقشهٔ کوتاه / نسخهٔ ۲.۲٫۰ — چه عوض شد / نسخهٔ ۲.۱٫۱ — چه عوض شد / نسخهٔ ۲.۱٫۰ — چه عوض شد / نسخهٔ ۲.۰٫۰ — چه عوض شد / نسخهٔ ۱.۱۰٫۰ — چه عوض شد / نسخهٔ ۱.۹.۲۳ — چه عوض شد / نسخهٔ ۱.۹.۲۲ — چه عوض شد

### `BUILD_INFO.txt`
ابتدای فایل: اطلاعات ساخت — معامله‌گر هوشمند رمزارز / ======================================= / نسخه           : 2.2.0 (نسل ۲٫۲: ترمینال حرفه‌ای — اندیکاتور/خط‌کشی/عکس نمودار، پویش دائمی فرصت‌ها، نظر هوش مصنوعی، بستن لحظه‌ای موقعیت)

### `CryptoAITrader.spec`
ابتدای فایل: # -*- mode: python ; coding: utf-8 -*- / """ / پیکربندی PyInstaller برای ساخت نسخه ویندوزی.

### `NEXT_TASK.md`
عنوان‌های اصلی: کار بعدی / وضعیت نسخهٔ ۲.۲٫۰ (۲۰۲۶-۰۹-۲۳) / باز برای نسخه‌های بعدی / وضعیت نسخهٔ ۲.۰٫۰ (۲۰۲۶-۰۹-۲۲) / باز برای نسخه‌های بعدی / وضعیت نسخهٔ ۱.۹.۲۳ (۲۰۲۶-۰۹-۲۲) / انجام شد / هنوز باز — بدون کاربر تمام نمی‌شود / پیشنهادها / بعد از تأیید کاربر

### `PROJECT_PROGRESS.md`
عنوان‌های اصلی: نسخهٔ ۲.۲.۰ — ۲۰۲۶/۰۹/۲۳ / کارت‌های سرمایه (مشکل ۱) / نمودار حرفه‌ای (مشکل ۲) / پنل تصمیم + هوش مصنوعی (مشکل ۳) / جدول فرصت‌ها همیشه زنده (مشکل ۴) / جدول موقعیت‌ها (مشکل ۵) / نمادهای مورد علاقه (مشکل ۶) / فنی / نسخهٔ ۲.۱.۱ — ۲۰۲۶/۰۹/۲۳ / چیدمان — «ترمینال حرفه‌ای» به‌جای پشتهٔ کارت / دو باگ واقعی (گزارش کاربر: «نمودار کار نمی‌کند / نمادی / تله‌های Qt که در این مسیر پیدا شد

### `README.md`
عنوان‌های اصلی: Crypto AI Trader / ⚠ پیش از هر چیز / این برنامه چه می‌کند؟ / نصب سریع / روش ۱ — فایل اجرایی (ساده‌ترین) / روش ۲ — اجرا از کد / ساخت فایل اجرایی ویندوز / اولین اجرا / حالت‌های اجرا / راهنمای صفحات / سیگنال چگونه ساخته می‌شود؟ / تحلیل هوش مصنوعی (اختیاری)

### `README_EN.md`
عنوان‌های اصلی: Crypto AI Trader / ⚠ Read this first / What it does / Quick start / Option 1 — Executable / Option 2 — From source / Building the Windows executable / First run / Run modes / The pages / How a signal is built / Optional AI analysis

### `RUN_WINDOWS.bat`
ابتدای فایل: @echo off / chcp 65001 >nul / title Crypto AI Trader

### `ai/prompts/templates/futures_signal_v1.txt`
ابتدای فایل: # قالب تولید سیگنال Futures با خروجی JSON — نسخه ۱ / # متغیرها: $symbol $exchange $data_timestamp $current_price $market_data $risk_context $analysis_context / You are a risk-aware futures signal engine. You output ONLY valid JSON — no markdown, no code fences, no commentary.

### `ai/prompts/templates/market_structure_v1.txt`
ابتدای فایل: # قالب تحلیل ساختار بازار — نسخه ۱ / # متغیرها: $symbol $timeframe $structure_data $language_instruction / You are a market structure specialist. Analyse ONLY the data given below.

### `ai/prompts/templates/risk_analysis_v1.txt`
ابتدای فایل: # قالب ارزیابی ریسک یک ستاپ معاملاتی — نسخه ۱ / # متغیرها: $symbol $setup_data $risk_parameters $language_instruction / You are a conservative risk manager reviewing a proposed trade setup.

### `ai/prompts/templates/signal_review_v1.txt`
ابتدای فایل: # قالب بازبینی سیگنال بسته‌شده — نسخه ۱ / # متغیرها: $symbol $direction $outcome $entry $stop_loss $take_profits $confidence / #           $timeframe $result_percent $realized_r $max_favorable $max_adverse

### `ai/prompts/templates/technical_analysis_v1.txt`
ابتدای فایل: # قالب تحلیل تکنیکال ساختاریافته — نسخه ۱ / # متغیرها: $symbol $exchange $data_timestamp $current_price $market_data $language_instruction / You are a disciplined technical analyst for cryptocurrency futures markets.

### `alembic.ini`
ابتدای فایل: # پیکربندی Alembic — مهاجرت پایگاه داده / # نشانی پایگاه داده در زمان اجرا از AppPaths خوانده می‌شود (migrations/env.py) / [alembic]

### `assets/README.md`
عنوان‌های اصلی: assets

### `assets/fonts/user/README.txt`
ابتدای فایل: پوشهٔ قلم‌های شخصی / ==================== / هر فایل .ttf یا .otf که در این پوشه بگذارید، هنگام اجرای برنامه خودکار

### `docs/ADD_AI_PROVIDER_FA.md`
عنوان‌های اصلی: افزودن ارائه‌دهنده هوش مصنوعی جدید / ۱. آیا اصلاً نیاز به کد جدید دارید؟ / ۲. ساختار لایه هوش مصنوعی / ۳. نوشتن کلاس / ۴. ثبت در کارخانه ارائه‌دهندگان / ۵. قواعدی که حتماً باید رعایت شوند / ۶. تنظیم اولویت و جایگزینی / ۷. آزمودن / چک‌لیست نهایی

### `docs/ADD_EXCHANGE_FA.md`
عنوان‌های اصلی: افزودن صرافی جدید / اصل طراحی / گام ۱ — ساخت پوشه / گام ۲ — ثابت‌ها / گام ۳ — کلاینت REST / گام ۴ — تبدیل داده (parser) / گام ۵ — پیاده‌سازی Provider / متدهای اجباری / گام ۶ — ثبت در رجیستری / گام ۷ — آزمون / اشتباه‌های رایج / سیاهه بررسی نهایی

### `docs/ADD_INDICATOR_FA.md`
عنوان‌های اصلی: افزودن اندیکاتور جدید / ۱. جای درست فایل / ۲. نوشتن کلاس / ۳. ثبت در رجیستری / ۴. قواعد مهم / ۵. آزمودن با داده واقعی / چک‌لیست نهایی

### `docs/AI_OMNIROUTE_FA.md`
عنوان‌های اصلی: دروازهٔ هوش مصنوعی OmniRoute / ۱) OmniRoute چیست؟ / ۲) راه‌اندازی در سه گام / گام ۱ — نصب و اجرای دروازه / گام ۲ — اتصال سرویس‌ها (اختیاری) / گام ۳ — انتخاب در برنامه / ۳) دربارهٔ کلید API / ۴) نام‌گذاری مدل‌ها / چرا `auto` بالای فهرست است؟ / ۵) ابزارهای تازهٔ عامل هوش مصنوعی / ۶) جای دروازه در معماری / ۷) عیب‌یابی

### `docs/AI_SETUP_FA.md`
عنوان‌های اصلی: راهنمای فعال‌سازی هوش مصنوعی / ۱. خلاصه سریع / ۲. Ollama — مسیر رایگان و محلی / نصب و راه‌اندازی / تنظیم در برنامه / «Ollama اجراست ولی برنامه وصل نمی‌شود» / ۳. مدل‌های رایگان ابری / سرویس‌های دارای سطح رایگان / ۴. OpenAI / وضعیت کلید شما / شارژ اعتبار / درباره «لایسنس مارکت» و سایت‌های مشابه

### `docs/ARCHITECTURE_FA.md`
عنوان‌های اصلی: معماری و تصمیم‌های طراحی / نمای کلی / تصمیم‌های کلیدی / ۱. ریشه ترکیب واحد (`Application`) / ۲. رجیستری‌ها بدون عارضه جانبی هنگام import / ۳. موتور سیگنال از هوش مصنوعی مستقل است / ۴. `WAIT` یک خروجی درجه‌یک است / ۵. «اطمینان» برچسب صادقانه دارد / ۶. حالت آفلاین یک قابلیت است، نه خطا / ۷. رابط گرافیکی هرگز نباید یخ بزند / ۸. رشته‌های رابط کاربری هرگز در کد نیستند / ۹. رمزها هرگز کنار داده نمی‌نشینند

### `docs/ASHNA_FA.md`
عنوان‌های اصلی: اتصال به «آشنا هوش مصنوعی» (AshnaAI) / راه‌اندازی در سه گام / مدل‌های موجود / پیشنهاد برای این برنامه / استفاده از ایجنت خودتان / امنیت / عیب‌یابی

### `docs/BUGFIX_SIGNALS_FA.md`
عنوان‌های اصلی: رفع سه ایراد گزارش‌شده — نسخهٔ ۱.۹.۱۵ / ۱) «تولید سیگنال» با تیک هوش مصنوعی همیشه «صبر» می‌داد / چه دیدید / علت واقعی / حالا چه می‌شود / ۲) دکمهٔ معامله هیچ چیزی باز نمی‌کرد / علت واقعی / حالا چه می‌شود / ۳) کیف پول فقط موجودی اسپات را نشان می‌داد / علت واقعی / حالا چه می‌شود / آزمون‌ها

### `docs/BUILD_INSTALLER_FA.md`
عنوان‌های اصلی: ساخت فایل نصبی و به‌روزرسانی خودکار / ۱) ربات ساخت فایل نصبی / پیش‌نیازها / اجرا / خروجی / ۲) ربات به‌روزرسانی / راه‌اندازی / چه اتفاقی می‌افتد / دو تضمین مهم / چرا مقایسهٔ نسخه عددی است / عیب‌یابی

### `docs/BUILD_WINDOWS_FA.md`
عنوان‌های اصلی: ساخت نسخهٔ ویندوزی با PyInstaller / پیش‌نیاز / ساخت / چه چیزهایی داخل بسته می‌روند / کوچک‌کردن خروجی / آزمون بستهٔ ساخته‌شده / نکته‌های رایج

### `docs/CHAT_TOOL_STEPS_FA.md`
عنوان‌های اصلی: نمایش گام‌به‌گام ابزارها در گفتگو / مسئله‌ای که حل شد / آنچه حالا دیده می‌شود / معماری / نکته‌های پیاده‌سازی / افزودن ابزار تازه

### `docs/DATABASE_FA.md`
عنوان‌های اصلی: پایگاه داده و مهاجرت‌ها / کلیات / چرا SQLite؟ / جدول‌ها (۱۳ جدول) / تنظیمات و پیکربندی / داده بازار / سیگنال‌ها / سامانه / کار با Alembic / وضعیت فعلی / اعمال مهاجرت / ساخت مهاجرت جدید

### `docs/DESIGN_ANALYSIS_FA.md`
عنوان‌های اصلی: تحلیل بستهٔ طراحی و نقشهٔ پیاده‌سازی — نسخهٔ ۱.۵ / ۱. چند پوستهٔ واقعی در تصاویر هست؟ / تفاوت‌ها فقط بصری‌اند / ۲. ده صفحهٔ هر پوسته / ۳. قابلیت‌های استخراج‌شده از تصاویر / ۳-۱ چیدمان کلی (در هر ده صفحه تکرار شده) / ۳-۲ داشبورد / ۳-۳ بازارها / ۳-۴ تحلیل / ۳-۵ سیگنال‌ها / ۳-۶ چت هوشمند / ۳-۷ تاریخچهٔ معاملات (صفحهٔ جدید)

### `docs/EXCHANGES_BITPIN_TOOBIT_FA.md`
عنوان‌های اصلی: افزودن صرافی‌های بیت‌پین (Bitpin) و توبیت (Toobit) / ۱. خلاصهٔ وضعیت / ۲. راهنمای کاربر برای اتصال حساب / توبیت / بیت‌پین / ۳. نکته‌های فنی که با آزمایش زنده کشف شد / توبیت / بیت‌پین / ۴. محدودیت کندل در بیت‌پین (تصمیم طراحی) / ۵. اصلاح جانبی: نرخ تومان / ۶. ساختار پرونده‌ها / ۷. امنیت

### `docs/FONTS_FA.md`
عنوان‌های اصلی: قلم‌های برنامه / قلم پیش‌فرض: وزیرمتن / قلم‌های همراه برنامه / ایران‌سنس — چرا همراه برنامه نیست؟ / قاعدهٔ همیشگی: هر زنجیره به وزیرمتن ختم می‌شود / افزودن قلم تازه

### `docs/HANDOVER_FA.md`
عنوان‌های اصلی: سند تحویل — ادامهٔ توسعه در گفتگوی تازه / ۱. پیام شروع در گفتگوی تازه / ۲. پروژه چیست / ۳. قواعد کار (خواستهٔ صریح کاربر) / ۴. محیط توسعه — تله‌های واقعی / ۴٫۱ جعبهٔ شنی بسته‌ها را گم می‌کند / ۴٫۲ اجرای آزمون — دستور دقیق / ۴٫۳ آزمایش زنده / ۵. تله‌های کد (هر کدام یک بار وقت گرفتند) / ۶. ساخت بستهٔ خروجی / ۷. کارهای باز / ۸. نکتهٔ مهم دربارهٔ چیزی که از دست رفت

### `docs/LBANK_API_FA.md`
عنوان‌های اصلی: راهنمای API صرافی LBank / نشانی‌ها / قالب نماد / تشخیص موفقیت پاسخ / نقاط پایانی عمومی / زمان سرور / فهرست نمادها / دقت اعشار / تیکر ۲۴ ساعته / کندل‌ها (مهم‌ترین نقطه پایانی) / تایم‌فریم‌های پشتیبانی‌شده / دفتر سفارش

### `docs/LIVE_DATA_AND_STREAMING_FA.md`
عنوان‌های اصلی: داده زنده و پاسخ جریانی / ۱) داده زندهٔ صرافی‌ها / اشکالی که رفع شد / معماری تازه / پروتکل توبیت / افزودن وب‌سوکت به صرافی تازه / ۲) پاسخ جریانی چت / چه چیزی عوض شد / مسیر داده / چرا استخراج‌گر لازم است / ایمنی نخ / بازگشت خودکار

### `docs/MARKET_SCANNER_FA.md`
عنوان‌های اصلی: پویش بازار و درجه‌بندی رنگی سیگنال‌ها / چرا پویشگر جدا از موتور سیگنال است؟ / قاعدهٔ طلایی: پویش هرگز هوش مصنوعی را صدا نمی‌زند / انتخاب نمادها بر پایهٔ گردش مالی، نه حجم / هم‌زمانی محدود / درجه‌بندی رنگی / ریسک معامله / دو دام که رفع شد / رنگ‌ها از توکن پوسته می‌آیند / پل زدن نخ‌ها

### `docs/MOBILE_FA.md`
عنوان‌های اصلی: نسخهٔ موبایل و ربات ساخت APK / خلاصه / یک تصمیم مهندسی که باید بدانید / چرا pandas روی موبایل نیست / چرا کلید API روی گوشی نیست / ساخت APK / پیش‌نیاز: WSL / اجرا / نصب روی گوشی / امکانات نسخهٔ موبایل / عیب‌یابی

### `docs/NEW_FEATURES_V1918_FA.md`
عنوان‌های اصلی: پیشنهاد قابلیت‌های تازه — پس از نسخهٔ ۱.۹.۱۸ / اولویت ۱ — سودِ فوری، کار کم / ۱. دفترچهٔ نتیجهٔ سیگنال‌ها (Signal Scorecard) / ۲. هشدار قیمت و هشدار سیگنال / ۳. حالت بازبینی تاریخی (Backtest سبک) / اولویت ۲ — کیفیت تصمیم / ۴. تشخیص رژیم بازار / ۵. همبستگی و هشدار ریسک متمرکز / ۶. تقویم رویدادهای بازار / اولویت ۳ — کار با هوش مصنوعی / ۷. حافظهٔ تحلیل‌ها / ۸. پروفایل سرعت برای سخت‌افزار ضعیف

### `docs/NEW_TOOLS_PROPOSAL_FA.md`
عنوان‌های اصلی: پیشنهاد ابزارها و امکانات تازهٔ کاربری / الف) کم‌کردن کار تکراری روزمره / الف‑۱. نوار فرمان سراسری (Ctrl+K) ⚡ / الف‑۲. مقایسهٔ کنار‌به‌کنار دو نماد ◐ / الف‑۳. برچسب و فیلتر روی سابقهٔ سیگنال ⚡ / الف‑۴. خروجی CSV از هر جدول ⚡ / ب) فهمیدن اینکه چرا برنامه این را گفت / ب‑۱. «چرا این سیگنال؟» به زبان ساده ⚡ / ب‑۲. نمایش کندلِ لحظهٔ سیگنال ⚡ / ب‑۳. کارنامهٔ هفتگی خودکار ◐ / ج) جلوگیری از اشتباه / ج‑۱. حالت تمرین با سرمایهٔ مجازی ◐

### `docs/NEW_TOOL_PROPOSAL_v195_FA.md`
عنوان‌های اصلی: پیشنهاد ابزار تازه — کارنامهٔ اعتماد سیگنال / چرا این یکی، نه چیز دیگری / ابزار پیشنهادی / چه چیزی نشان می‌دهد / چرا کم‌هزینه است / چرا قابل اعتماد است / اندازه / آنچه عمداً در آن نیست / گزینه‌های دیگری که بررسی و رد شدند / تصمیم با شماست

### `docs/PREDICTIVE_ENGINE_FA.md`
عنوان‌های اصلی: موتور هوش پیش‌بینی CryptoAITrader — سند معماری و نقشهٔ راه / ۰. اصول حاکم (ترجمهٔ فنی قوانین حیاتی) / ۱. موجودی Phase 0 — چه چیزی هست و چه چیزی نیست / ۱.۱. آنچه از قبل وجود دارد (و باید ارتقا یابد نه دوباره‌سازی) / ۱.۲. آنچه وجود ندارد (ساخته می‌شود) / ۱.۳. محدودیت‌های دادهٔ واقعی (صادقانه) / ۲. معماری هدف / ماژول‌های جدید (همه با docstring فارسی «چرا» + آزمون بدون PySide6 مگر UI) / تغییر دیتابیس / ۳. فازبندی اجرا (۱۵ فاز + یک جریان موازی) / ۴. گزارش‌های فازها / Phase 0 — بررسی کامل پروژه (۲۰۲۶-۰۹-۲۲)

### `docs/PROFESSIONAL_ROADMAP_FA.md`
عنوان‌های اصلی: قابلیت‌های پیشنهادی برای حرفه‌ای‌تر شدن سیستم / چطور از این سند استفاده کنیم / دستهٔ ۱ — موتور معاملاتی و سیگنال / ۱.۱ بک‌تست تاریخی استراتژی / ۱.۲ بهینه‌سازی وزن استراتژی‌ها / ۱.۳ هشدار قیمت و هشدار سیگنال / ۱.۴ پایش خودکار پس‌زمینه / ۱.۵ ردیابی نتیجهٔ واقعی سیگنال‌ها  ✅ انجام شد (نسخهٔ ۱.۹.۱) / ۱.۶ اندیکاتورهای پیشرفته / دستهٔ ۲ — مدیریت سرمایه و ریسک / ۲.۱ ماشین‌حساب حجم پوزیشن در خود برنامه  ✅ انجام شد (نسخهٔ ۱.۹.۰) / ۲.۲ پایش ریسک کل پرتفوی

### `docs/SCALP_FA.md`
عنوان‌های اصلی: معاملهٔ اسکلپ و خودکار / بخش اول: انتظار واقع‌بینانه / بخش دوم: پویشگر / دو درسی که از دادهٔ واقعی گرفتیم / سود نمایش‌داده‌شده خالص است / بخش سوم: معاملهٔ خودکار / تنظیم‌ها (همه دست شماست) / محافظ‌ها / دربارهٔ سفارش واقعی — صادقانه / هوش مصنوعی در این بخش / بخش پنجم: ترمینال حرفه‌ای (نسخهٔ ۲٫۲٫۰) / پویش پس‌زمینهٔ همیشگی

### `docs/SECURITY_FA.md`
عنوان‌های اصلی: امنیت / رمز عبور کاربر / نشست / کلید و رمز API صرافی / آزمون / معاملات / زبانهٔ امنیت در تنظیمات (از نسخهٔ ۱.۵.۹) / تغییر رمز عبور / نشست‌ها / حالت مهمان

### `docs/SIGNAL_AI_TROUBLESHOOTING_FA.md`
عنوان‌های اصلی: چرا هوش مصنوعی در سیگنال کار نمی‌کرد / ۱) مهلت زمانی کوتاه‌تر از چت / ۲) رابط کاربری موفقیت را فرض می‌گرفت / ۳) دکمه‌ها و کلیک در جدول پویش / اگر هنوز وصل نمی‌شود

### `docs/SIGNAL_TABLES_FA.md`
عنوان‌های اصلی: راهنمای جدول‌های سیگنال / ۱. جدول سابقهٔ سیگنال‌ها (صفحهٔ سیگنال‌ها) / ستون‌ها / مرتب‌سازی / رنگ‌بندی / ۲. عدد اطمینان چگونه ساخته می‌شود؟ / مشکل قدیمی / راه‌حل — سه لایه / تأثیر عملی / خواندن درست عدد اطمینان / ۳. پیش‌بینی تایم‌فریم بعدی / پنهان‌کردن سیگنال‌های سوخته

### `docs/THEMES_FA.md`
عنوان‌های اصلی: راهنمای پوسته‌ها / چهار پوسته / قانون طلایی / ساختار توکن‌ها / افزودن پوستهٔ تازه / ویجت‌های نقاشی‌شده / نام‌های قدیمی / شفق نیمه‌شب (`midnight_aurora`)

### `docs/TROUBLESHOOTING_FA.md`
عنوان‌های اصلی: رفع مشکلات رایج / برنامه اجرا نمی‌شود / پنجره باز می‌شود و بلافاصله بسته می‌شود / `ModuleNotFoundError: No module named 'PySide6'` / `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"` (لینوکس) / پایتون نسخه قدیمی / مشکل اتصال به بازار / وضعیت «آفلاین» می‌ماند / خطای «داده ناکافی» / قیمت‌ها به‌روز نمی‌شوند / `error_code: 10000` در لاگ / مشکل سیگنال‌ها

### `installer/CryptoAITrader.iss`
ابتدای فایل: ; ====================================================================== / ;  اسکریپت Inno Setup برای ساخت فایل نصبی ویندوز / ;  Crypto AI Trader — حسین حاج طالبی

### `localization/en/alerts.json`
کلیدهای سطح اول: `title`, `fired`, `enabled`, `add`, `remove`, `rearm`, `kind_price`, `kind_signal`, `above`, `below`, `value`, `min_confidence`, `state_armed`, `state_fired`, `empty`, `invalid`, `added`.

### `localization/en/analysis.json`
کلیدهای سطح اول: `agent_decision`, `ai_analysis`, `ai_disabled`, `ai_done`, `ai_failed`, `ai_running`, `ai_steps`, `bearish`, `breakdown`, `breakout`, `bullish`, `candles_used`, `data_source`, `done`, `engine_analysis`, `indicators`, `levels`, `low_volume`, `multi_timeframe`, `neutral`, `no_data`, `overbought`, `oversold`, `ranging`, `resistance`, `run`, `running`, `structure`, `subtitle`, `support`, `swings`, `title`, `trend`, `undefined`, `use_ai`, `volume_spike`, `select_all_indicators`, `clear_indicators`.

### `localization/en/auth.json`
کلیدهای سطح اول: `account_security`, `change_password`, `created`, `current_password`, `current_session`, `device`, `display_name`, `email`, `error`, `guest`, `guest_hint`, `have_account`, `identifier`, `identifier_hint`, `last_login`, `last_seen`, `login`, `login_success`, `logout`, `logout_success`, `new_password`, `no_account`, `password`, `password_changed`, `password_confirm`, `profile`, `register`, `register_success`, `remember_me`, `reset`, `revoke_others`, `revoke_session`, `sessions`, `strength`, `username`, `welcome`.

### `localization/en/charts.json`
کلیدهای سطح اول: `title`, `no_data`, `loading`, `price`, `volume`, `candles`, `overlays`, `levels`, `show_volume`, `show_levels`, `reset_zoom`, `candle_count`, `type_candles`, `type_line`, `type_area`, `fit`, `live_price`.

### `localization/en/chat.json`
کلیدهای سطح اول: `action_done`, `ai_disabled`, `assistant`, `clear`, `delete`, `delete_confirm`, `deleted`, `disclaimer`, `failed`, `history_empty`, `input_hint`, `mode`, `mode_analysis`, `mode_general`, `mode_learn`, `mode_signal`, `new_chat`, `no_provider`, `placeholder`, `rename`, `rename_prompt`, `run_action`, `saved`, `search_history`, `send`, `sending`, `status_active`, `subtitle`, `suggest_price`, `suggest_risk`, `suggest_signal`, `suggest_trend`, `thinking`, `tool_detail_hint`, `tool_failed`, `tool_ok`, `tool_running`, `tool_steps`, `tools`, `untitled`, `using_tool`, `welcome`, `you`.

### `localization/en/common.json`
کلیدهای سطح اول: `add`, `all`, `app_name`, `app_tagline`, `apply`, `back`, `cancel`, `change`, `close`, `collapse_sidebar`, `connected`, `connecting`, `copied`, `copy`, `delete`, `details`, `disabled`, `disconnected`, `duration_minutes`, `duration_minutes_seconds`, `duration_seconds`, `edit`, `enabled`, `exchange`, `exit_fullscreen`, `export`, `export_csv`, `export_csv_hint`, `export_done`, `export_empty`, `export_failed`, `features`, `finish`, `focus_mode`, `fullscreen`, `fullscreen_hint`, `high`, `import`, `last_tick`, `live_updates`, `loading`, `low`, `mark_all_read`, `market_count`, `minutes_short`, `never`, `next`, `no`, `no_data`, `no_notifications`, `none`, `notifications`, `of`, `offline`, `ok`, `online`, `page`, `price`, `producer`, `reconnecting`, `refresh`, `reset`, `save`, `search`, `search_placeholder`, `shortcuts`, `state`, `symbol`, `table`, `timeframe`, `toggle_theme`, `unknown`, `updated_at`, `volume`, `yes`.

### `localization/en/dashboard.json`
کلیدهای سطح اول: `ai_provider`, `block_overview`, `block_signals`, `block_stats`, `block_ticker`, `connection`, `exchange`, `last_update`, `market_overview`, `no_watchlist`, `open_detail`, `recent_signals`, `stats`, `subtitle`, `system_status`, `watchlist`.

### `localization/en/email.json`
کلیدهای سطح اول: `description`, `error`, `gmail_hint`, `not_configured_hint`, `preset`, `presets`, `sender`, `sender_name`, `smtp_host`, `smtp_password`, `smtp_port`, `smtp_tls`, `smtp_username`, `test`, `test_ok`, `title`.

### `localization/en/errors.json`
کلیدهای سطح اول: `ai`, `ai_invalid_response`, `ai_provider`, `ai_unavailable`, `authentication`, `backup`, `backup_failed`, `configuration`, `database`, `exchange`, `generic`, `indicator`, `insufficient_data`, `network`, `not_connected`, `rate_limit`, `restore_failed`, `security`, `signal_engine`, `symbol_not_found`, `timeframe`, `timeout`, `unknown`, `validation`, `websocket`.

### `localization/en/exchange.json`
کلیدهای سطح اول: `error`.

### `localization/en/help.json`
کلیدهای سطح اول: `about_body`, `about_title`, `ai_body`, `ai_title`, `chat_body`, `chat_title`, `confidence_body`, `confidence_title`, `disclaimer_body`, `disclaimer_title`, `free_models_body`, `free_models_title`, `risk_body`, `risk_title`, `security_body`, `security_title`, `signals_body`, `signals_title`, `subtitle`, `tab_guide`.

### `localization/en/layout.json`
کلیدهای سطح اول: `arrange`, `arrange_hint`, `done`, `hide`, `move_down`, `move_up`, `reset`, `saved`, `show`.

### `localization/en/markets.json`
کلیدهای سطح اول: `action_analyze`, `action_chat`, `action_open_market`, `action_signal`, `add_to_watchlist`, `add_watchlist`, `added_to_watchlist`, `all_symbols`, `already_in_watchlist`, `click_hint`, `count`, `detail_atr`, `detail_change`, `detail_ema`, `detail_macd`, `detail_resistance`, `detail_rsi`, `detail_structure`, `detail_support`, `detail_title`, `detail_trend`, `details_failed`, `high_24h`, `live`, `loading`, `loading_details`, `loading_symbols`, `low_24h`, `pairs_count`, `price_toman`, `price_usd`, `price_usdt`, `quote_volume`, `rate_manual`, `rate_source`, `rate_unavailable`, `remove_from_watchlist`, `remove_watchlist`, `removed_from_watchlist`, `search_placeholder`, `select_symbol_first`, `sort_gainers`, `sort_label`, `sort_losers`, `sort_name`, `sort_price_asc`, `sort_price_desc`, `sort_value`, `sort_volume`, `subtitle`, `tab_all`, `technical_snapshot`, `toman`, `trend`, `trend_down`, `trend_flat`, `trend_up`, `updated`, `updating`, `volume`, `watchlist_only`, `chips`.

### `localization/en/nav.json`
کلیدهای سطح اول: `dashboard`, `markets`, `analysis`, `signals`, `prediction`, `chat`, `trades`, `wallet`, `reports`, `settings`, `help`.

### `localization/en/performance.json`
کلیدهای سطح اول: `title`, `subtitle`, `period`, `period_days`, `period_all`, `refresh`, `win_rate`, `total_r`, `profit_factor`, `pending`, `decided_count`, `breakdown`, `group`, `group_confidence`, `group_symbol`, `group_timeframe`, `group_direction`, `confidence_hint`, `history`, `empty`, `total`, `wins_losses`, `average_r`, `total_percent`, `timeframe`, `status`, `result`, `r_value`, `targets`, `status_pending`, `status_target`, `status_stop`, `status_expired`, `status_cancelled`.

### `localization/en/prediction.json`
کلیدهای سطح اول: `subtitle`, `refresh`, `computing`, `no_symbol`, `empty`, `no_data`, `horizons_title`, `horizons_hint`, `direction`, `range_value`, `confidence_short`, `samples`, `agreement`, `conflict`, `volatility_short`, `method`, `disabled_row`, `market_title`, `stage_row`, `regime_row`, `alignment_row`, `alignment`, `data_quality`, `last_price`, `stage`, `regime`, `scenarios_title`, `primary_horizon`, `scenario_row`, `scenario`, `event_pressure`, `warnings_title`, `no_warnings`, `breakout_state`, `false_breakout`, `changed_title`, `no_change_data`, `probability_delta`, `direction_changed`, `factor_row`, `factor_dir`, `accuracy_title`, `no_resolved`, `accuracy_row`, `health_row`, `health`, `timeline_title`, `no_timeline`, `timeline_row`, `summary_title`, `fan_title`, `fan_legend`, `current_direction`, `probability`, `volatility`, `generated`, `col_horizon`, `col_direction`, `col_probability`, `col_confidence`, `col_p10`, `col_p50`, `col_p90`, `col_volatility`, `col_agreement`, `col_samples`, `col_method`, `col_status`, `status_active`, `disabled_title`, `accuracy_resolved`, `accuracy_direction`, `accuracy_range`, `accuracy_brier`, `expected_range_row`, `transition_row`.

### `localization/en/recommendation.json`
کلیدهای سطح اول: `title`, `action_buy`, `action_sell`, `action_wait`, `confidence`, `column`, `none`, `hint`, `superseded`.

### `localization/en/reports.json`
کلیدهای سطح اول: `average_confidence`, `by_direction`, `confidence_trend`, `days`, `direction_share`, `disclaimer`, `export_csv`, `export_excel`, `export_html`, `export_json`, `export_pdf`, `exported`, `format`, `from_date`, `generate`, `generating`, `long_share`, `no_data`, `period`, `saved`, `saved_to`, `subtitle`, `tab_export`, `title`, `to_date`, `top_symbols`, `total_signals`, `wait_share`, `formats`.

### `localization/en/review.json`
کلیدهای سطح اول: `auto_enabled`, `auto_hint`, `body`, `column`, `generate`, `generating`, `only_closed`, `pending`, `regenerate`, `reviewed_count`, `stats_title`, `title`, `unavailable`, `verdict`, `lesson`.

### `localization/en/scorecard.json`
کلیدهای سطح اول: `title`, `intro`, `refresh`, `no_data`, `col_horizon`, `col_checked`, `col_hits`, `col_rate`, `col_miss`, `verdict_calibrated`, `verdict_too_narrow`, `verdict_too_wide`, `verdict_insufficient_data`, `pending_note`, `checking`, `auto`.

### `localization/en/settings.json`
کلیدهای سطح اول: `accounts`, `advanced`, `ai`, `ai_api_key`, `ai_base_url`, `ai_credit_exhausted`, `ai_enable`, `ai_fallback`, `ai_free_only`, `ai_free_only_hint`, `ai_key_saved`, `ai_model`, `ai_model_auto`, `ai_no_free_model`, `ai_no_key_needed`, `ai_ollama_hint`, `ai_omniroute_hint`, `ai_optional_key`, `ai_priority`, `ai_provider`, `ai_section`, `ai_tier_free`, `ai_tier_low_cost`, `ai_tier_paid`, `ai_use_free_model`, `api_key`, `api_key_hint`, `api_secret`, `appearance`, `atr_multiplier`, `auto_backup`, `backup`, `backup_created`, `backup_now`, `cache_auto`, `candle_cache_ttl`, `chat_history_limit`, `chat_streaming`, `compact_mode`, `confirm_actions`, `connection_failed`, `connection_ok`, `credentials_saved`, `credentials_stored_note`, `dashboard_interval`, `data`, `display`, `editor`, `exchange`, `exchange_geo_restricted`, `exchange_hint`, `exchange_not_implemented`, `exchange_section`, `exchange_switch_failed`, `exchange_switched`, `exchange_switching`, `font_missing_hint`, `font_not_installed`, `font_scale`, `fonts`, `general`, `http_timeout`, `indicators`, `language`, `load_models`, `markets_interval`, `markets_sort`, `max_leverage`, `max_retries`, `min_rr`, `mode_ai_only`, `mode_engine`, `mode_hybrid`, `models_failed`, `models_loaded`, `models_loaded_free`, `narrative_enabled`, `no_key_needed`, `notifications`, `parallel_requests`, `performance`, `restore`, `restore_confirm`, `restore_done`, `risk`, `risk_balance`, `risk_percent`, `save_chat_history`, `saved`, `security`, `select_exchange`, `settings_preserved`, `show_toman`, `signal_ai_timeout`, `signal_mode`, `subtitle`, `test_connection`, `testing`, `theme`, `theme_dark`, `theme_descriptions`, `theme_light`, `theme_system`, `themes`, `timezone_display`, `timezone_local`, `timezone_section`, `timezone_utc`, `title`, `toman_auto`, `toman_manual_rate`, `toman_section`, `auto_detect`, `ollama_max_context`, `hide_stale_signals`, `model_fit`, `doctor`, `update`, `alerts_sound`, `ai_get_key_at`, `speed_profile`, `speed_fast`, `speed_balanced`, `speed_deep`.

### `localization/en/sidebar.json`
کلیدهای سطح اول: `ai_checking`, `ai_off`, `ai_title`.

### `localization/en/signals.json`
کلیدهای سطح اول: `act_on_trade`, `action`, `ai_disabled_hint`, `ai_driven`, `ai_fell_back`, `ai_generating`, `ai_step`, `ai_thinking`, `ai_unavailable`, `analysis`, `analysis_by_ai`, `analysis_by_template`, `analysis_empty`, `analysis_title`, `auto`, `click_row_hint`, `confidence`, `confidence_note`, `confirm_trade`, `context`, `copied`, `copy_text`, `current`, `detail_title`, `direction`, `engine_only`, `entry`, `entry_zone`, `export_pdf`, `forecast`, `forecast_note`, `generate`, `generated_at`, `generating`, `grade_fair`, `grade_good`, `grade_strong`, `grade_weak`, `group_by_direction`, `history`, `insufficient_data`, `invalidation`, `legend`, `legend_text`, `levels`, `leverage`, `long`, `market_structure`, `no_action_on_wait`, `no_signals`, `not_financial_advice`, `outcome`, `paper_trade_failed`, `paper_trade_note`, `paper_trade_opened`, `paper_trade_title`, `pdf_failed`, `pdf_saved`, `position_size`, `reason`, `reasoning`, `result`, `risk`, `risk_amount`, `risk_high`, `risk_low`, `risk_medium`, `risk_rejected`, `risk_reward`, `risk_unknown`, `scan`, `scan_ai_analyze`, `scan_ai_done`, `scan_ai_fallback`, `scan_ai_running`, `scan_cancelled`, `scan_done`, `scan_empty`, `scan_failed`, `scan_hint`, `scan_include_wait`, `scan_limit`, `scan_min_confidence`, `scan_progress`, `scan_results`, `scan_running`, `scan_stop`, `short`, `sort`, `sort_by`, `stop_loss`, `subtitle`, `take_profit`, `take_profit_n`, `timeframe_label`, `timeframes`, `tp1`, `tp2`, `tp3`, `trade`, `trend`, `view_analysis`, `wait`, `wait_no_trade`, `wait_note`, `wait_result`, `rerun_ai`, `rerun_running`, `rerun_done`, `rerun_failed`, `analysis_absent`, `rerun_saved`.

### `localization/en/sizing.json`
کلیدهای سطح اول: `capital`, `entry`, `error_capital`, `error_entry`, `error_risk`, `error_same_price`, `error_stop`, `fee_percent`, `hint`, `leverage`, `result_title`, `risk_percent`, `row_fee`, `row_liquidation`, `row_margin`, `row_notional`, `row_quantity`, `row_reward`, `row_risk_amount`, `row_risk_reward`, `row_win_rate`, `stop_loss`, `take_profit`, `title`, `warn_fees_significant`, `warn_high_leverage`, `warn_high_risk`, `warn_low_rr`, `warn_margin_exceeds_capital`, `warn_near_liquidation`, `warn_stop_beyond_liquidation`.

### `localization/en/trades.json`
کلیدهای سطح اول: `actions`, `cancel_trade`, `clear_history`, `close_hint`, `close_trade`, `closed`, `closed_manual`, `closed_stop_loss`, `closed_take_profit`, `confirm_clear`, `date`, `delete_trade`, `duration`, `empty`, `empty_hint`, `entry`, `exit`, `export_csv`, `fee`, `from_date`, `leverage`, `metrics`, `new_trade`, `no_open_trade_selected`, `note`, `opened`, `page_info`, `paper_notice`, `pnl`, `pnl_percent`, `quantity`, `side`, `sides`, `status`, `statuses`, `stop_loss`, `subtitle`, `symbol`, `take_profit`, `title`, `to_date`, `auto`.

### `localization/en/tutorial.json`
کلیدهای سطح اول: `title`, `subtitle`, `search_placeholder`, `no_results`, `progress`, `next`, `previous`, `level_basic`, `level_intermediate`, `level_advanced`, `chapters`.

### `localization/en/validity.json`
کلیدهای سطح اول: `adverse_move`, `aging_label`, `column`, `effective_rr`, `enter_before`, `entry_window_closing`, `entry_window_passed`, `expired`, `expired_label`, `expired_wait`, `explain_body`, `explain_title`, `fresh`, `fresh_label`, `invalidated_label`, `move_consumed`, `not_enterable_warning`, `stale_label`, `stop_hit`, `target_reached`, `title`, `valid_until`, `wait_active`.

### `localization/en/wallet.json`
کلیدهای سطح اول: `amount`, `asset`, `assets`, `available`, `change_24h`, `connect_account`, `deposit`, `empty_assets`, `futures`, `futures_total`, `growth`, `in_orders`, `last_sync`, `never_synced`, `no_account`, `no_account_hint`, `price`, `profit_loss`, `range`, `recent_trades`, `share`, `spot`, `spot_futures`, `spot_total`, `subtitle`, `sync`, `sync_done`, `sync_empty`, `sync_failed`, `syncing`, `title`, `toman_value`, `total_value`, `transfer`, `value`, `wallet_type`, `withdraw`.

### `localization/en/watchlist.json`
کلیدهای سطح اول: `title`, `subtitle`, `list`, `default_name`, `new`, `rename`, `delete`, `name_prompt`, `move_up`, `move_down`, `edit_note`, `note_prompt`, `remove_symbol`, `position`, `note`, `count`, `empty`, `created`, `create_failed`, `renamed`, `rename_failed`, `deleted`, `delete_confirm`, `removed`, `note_saved`, `moved`, `add_to_list`, `choose_list`.

### `localization/en/wizard.json`
کلیدهای سطح اول: `title`, `welcome_title`, `welcome_subtitle`, `welcome_body`, `appearance_title`, `appearance_subtitle`, `exchange_title`, `exchange_subtitle`, `exchange_note`, `ai_title`, `ai_subtitle`, `ai_enable`, `ai_note`, `risk_title`, `risk_subtitle`, `risk_note`, `finish_title`, `finish_subtitle`, `finish_body`.

### `localization/fa/alerts.json`
کلیدهای سطح اول: `title`, `fired`, `enabled`, `add`, `remove`, `rearm`, `kind_price`, `kind_signal`, `above`, `below`, `value`, `min_confidence`, `state_armed`, `state_fired`, `empty`, `invalid`, `added`.

### `localization/fa/analysis.json`
کلیدهای سطح اول: `agent_decision`, `ai_analysis`, `ai_disabled`, `ai_done`, `ai_failed`, `ai_running`, `ai_steps`, `bearish`, `breakdown`, `breakout`, `bullish`, `candles_used`, `data_source`, `done`, `engine_analysis`, `indicators`, `levels`, `low_volume`, `multi_timeframe`, `neutral`, `no_data`, `overbought`, `oversold`, `ranging`, `resistance`, `run`, `running`, `structure`, `subtitle`, `support`, `swings`, `title`, `trend`, `undefined`, `use_ai`, `volume_spike`, `select_all_indicators`, `clear_indicators`.

### `localization/fa/auth.json`
کلیدهای سطح اول: `account_security`, `change_password`, `created`, `current_password`, `current_session`, `device`, `display_name`, `email`, `error`, `guest`, `guest_hint`, `have_account`, `identifier`, `identifier_hint`, `last_login`, `last_seen`, `login`, `login_success`, `logout`, `logout_success`, `new_password`, `no_account`, `password`, `password_changed`, `password_confirm`, `profile`, `register`, `register_success`, `remember_me`, `reset`, `revoke_others`, `revoke_session`, `sessions`, `strength`, `username`, `welcome`.

### `localization/fa/charts.json`
کلیدهای سطح اول: `title`, `no_data`, `loading`, `price`, `volume`, `candles`, `overlays`, `levels`, `show_volume`, `show_levels`, `reset_zoom`, `candle_count`, `type_candles`, `type_line`, `type_area`, `fit`, `live_price`.

### `localization/fa/chat.json`
کلیدهای سطح اول: `action_done`, `ai_disabled`, `assistant`, `clear`, `delete`, `delete_confirm`, `deleted`, `disclaimer`, `failed`, `history_empty`, `input_hint`, `mode`, `mode_analysis`, `mode_general`, `mode_learn`, `mode_signal`, `new_chat`, `no_provider`, `placeholder`, `rename`, `rename_prompt`, `run_action`, `saved`, `search_history`, `send`, `sending`, `status_active`, `subtitle`, `suggest_price`, `suggest_risk`, `suggest_signal`, `suggest_trend`, `thinking`, `tool_detail_hint`, `tool_failed`, `tool_ok`, `tool_running`, `tool_steps`, `tools`, `untitled`, `using_tool`, `welcome`, `you`.

### `localization/fa/common.json`
کلیدهای سطح اول: `add`, `all`, `app_name`, `app_tagline`, `apply`, `back`, `cancel`, `change`, `close`, `collapse_sidebar`, `connected`, `connecting`, `copied`, `copy`, `delete`, `details`, `disabled`, `disconnected`, `duration_minutes`, `duration_minutes_seconds`, `duration_seconds`, `edit`, `enabled`, `exchange`, `exit_fullscreen`, `export`, `export_csv`, `export_csv_hint`, `export_done`, `export_empty`, `export_failed`, `features`, `finish`, `focus_mode`, `fullscreen`, `fullscreen_hint`, `high`, `import`, `last_tick`, `live_updates`, `loading`, `low`, `mark_all_read`, `market_count`, `minutes_short`, `never`, `next`, `no`, `no_data`, `no_notifications`, `none`, `notifications`, `of`, `offline`, `ok`, `online`, `page`, `price`, `producer`, `reconnecting`, `refresh`, `reset`, `save`, `search`, `search_placeholder`, `shortcuts`, `state`, `symbol`, `table`, `timeframe`, `toggle_theme`, `unknown`, `updated_at`, `volume`, `yes`.

### `localization/fa/dashboard.json`
کلیدهای سطح اول: `ai_provider`, `block_overview`, `block_signals`, `block_stats`, `block_ticker`, `connection`, `exchange`, `last_update`, `market_overview`, `no_watchlist`, `open_detail`, `recent_signals`, `stats`, `subtitle`, `system_status`, `watchlist`.

### `localization/fa/email.json`
کلیدهای سطح اول: `description`, `error`, `gmail_hint`, `not_configured_hint`, `preset`, `presets`, `sender`, `sender_name`, `smtp_host`, `smtp_password`, `smtp_port`, `smtp_tls`, `smtp_username`, `test`, `test_ok`, `title`.

### `localization/fa/errors.json`
کلیدهای سطح اول: `ai`, `ai_invalid_response`, `ai_provider`, `ai_unavailable`, `authentication`, `backup`, `backup_failed`, `configuration`, `database`, `exchange`, `generic`, `indicator`, `insufficient_data`, `network`, `not_connected`, `rate_limit`, `restore_failed`, `security`, `signal_engine`, `symbol_not_found`, `timeframe`, `timeout`, `unknown`, `validation`, `websocket`.

### `localization/fa/exchange.json`
کلیدهای سطح اول: `error`.

### `localization/fa/help.json`
کلیدهای سطح اول: `about_body`, `about_title`, `ai_body`, `ai_title`, `chat_body`, `chat_title`, `confidence_body`, `confidence_title`, `disclaimer_body`, `disclaimer_title`, `free_models_body`, `free_models_title`, `risk_body`, `risk_title`, `security_body`, `security_title`, `signals_body`, `signals_title`, `subtitle`, `tab_guide`.

### `localization/fa/layout.json`
کلیدهای سطح اول: `arrange`, `arrange_hint`, `done`, `hide`, `move_down`, `move_up`, `reset`, `saved`, `show`.

### `localization/fa/markets.json`
کلیدهای سطح اول: `action_analyze`, `action_chat`, `action_open_market`, `action_signal`, `add_to_watchlist`, `add_watchlist`, `added_to_watchlist`, `all_symbols`, `already_in_watchlist`, `click_hint`, `count`, `detail_atr`, `detail_change`, `detail_ema`, `detail_macd`, `detail_resistance`, `detail_rsi`, `detail_structure`, `detail_support`, `detail_title`, `detail_trend`, `details_failed`, `high_24h`, `live`, `loading`, `loading_details`, `loading_symbols`, `low_24h`, `pairs_count`, `price_toman`, `price_usd`, `price_usdt`, `quote_volume`, `rate_manual`, `rate_source`, `rate_unavailable`, `remove_from_watchlist`, `remove_watchlist`, `removed_from_watchlist`, `search_placeholder`, `select_symbol_first`, `sort_gainers`, `sort_label`, `sort_losers`, `sort_name`, `sort_price_asc`, `sort_price_desc`, `sort_value`, `sort_volume`, `subtitle`, `tab_all`, `technical_snapshot`, `toman`, `trend`, `trend_down`, `trend_flat`, `trend_up`, `updated`, `updating`, `volume`, `watchlist_only`, `chips`.

### `localization/fa/nav.json`
کلیدهای سطح اول: `dashboard`, `markets`, `analysis`, `signals`, `prediction`, `chat`, `trades`, `wallet`, `reports`, `settings`, `help`.

### `localization/fa/performance.json`
کلیدهای سطح اول: `title`, `subtitle`, `period`, `period_days`, `period_all`, `refresh`, `win_rate`, `total_r`, `profit_factor`, `pending`, `decided_count`, `breakdown`, `group`, `group_confidence`, `group_symbol`, `group_timeframe`, `group_direction`, `confidence_hint`, `history`, `empty`, `total`, `wins_losses`, `average_r`, `total_percent`, `timeframe`, `status`, `result`, `r_value`, `targets`, `status_pending`, `status_target`, `status_stop`, `status_expired`, `status_cancelled`.

### `localization/fa/prediction.json`
کلیدهای سطح اول: `subtitle`, `refresh`, `computing`, `no_symbol`, `empty`, `no_data`, `horizons_title`, `horizons_hint`, `direction`, `range_value`, `confidence_short`, `samples`, `agreement`, `conflict`, `volatility_short`, `method`, `disabled_row`, `market_title`, `stage_row`, `regime_row`, `alignment_row`, `alignment`, `data_quality`, `last_price`, `stage`, `regime`, `scenarios_title`, `primary_horizon`, `scenario_row`, `scenario`, `event_pressure`, `warnings_title`, `no_warnings`, `breakout_state`, `false_breakout`, `changed_title`, `no_change_data`, `probability_delta`, `direction_changed`, `factor_row`, `factor_dir`, `accuracy_title`, `no_resolved`, `accuracy_row`, `health_row`, `health`, `timeline_title`, `no_timeline`, `timeline_row`, `summary_title`, `fan_title`, `fan_legend`, `current_direction`, `probability`, `volatility`, `generated`, `col_horizon`, `col_direction`, `col_probability`, `col_confidence`, `col_p10`, `col_p50`, `col_p90`, `col_volatility`, `col_agreement`, `col_samples`, `col_method`, `col_status`, `status_active`, `disabled_title`, `accuracy_resolved`, `accuracy_direction`, `accuracy_range`, `accuracy_brier`, `expected_range_row`, `transition_row`.

### `localization/fa/recommendation.json`
کلیدهای سطح اول: `title`, `action_buy`, `action_sell`, `action_wait`, `confidence`, `column`, `none`, `hint`, `superseded`.

### `localization/fa/reports.json`
کلیدهای سطح اول: `average_confidence`, `by_direction`, `confidence_trend`, `days`, `direction_share`, `disclaimer`, `export_csv`, `export_excel`, `export_html`, `export_json`, `export_pdf`, `exported`, `format`, `from_date`, `generate`, `generating`, `long_share`, `no_data`, `period`, `saved`, `saved_to`, `subtitle`, `tab_export`, `title`, `to_date`, `top_symbols`, `total_signals`, `wait_share`, `formats`.

### `localization/fa/review.json`
کلیدهای سطح اول: `auto_enabled`, `auto_hint`, `body`, `column`, `generate`, `generating`, `only_closed`, `pending`, `regenerate`, `reviewed_count`, `stats_title`, `title`, `unavailable`, `verdict`, `lesson`.

### `localization/fa/scorecard.json`
کلیدهای سطح اول: `title`, `intro`, `refresh`, `no_data`, `col_horizon`, `col_checked`, `col_hits`, `col_rate`, `col_miss`, `verdict_calibrated`, `verdict_too_narrow`, `verdict_too_wide`, `verdict_insufficient_data`, `pending_note`, `checking`, `auto`.

### `localization/fa/settings.json`
کلیدهای سطح اول: `accounts`, `advanced`, `ai`, `ai_api_key`, `ai_base_url`, `ai_credit_exhausted`, `ai_enable`, `ai_fallback`, `ai_free_only`, `ai_free_only_hint`, `ai_key_saved`, `ai_model`, `ai_model_auto`, `ai_no_free_model`, `ai_no_key_needed`, `ai_ollama_hint`, `ai_omniroute_hint`, `ai_optional_key`, `ai_priority`, `ai_provider`, `ai_section`, `ai_tier_free`, `ai_tier_low_cost`, `ai_tier_paid`, `ai_use_free_model`, `api_key`, `api_key_hint`, `api_secret`, `appearance`, `atr_multiplier`, `auto_backup`, `backup`, `backup_created`, `backup_now`, `cache_auto`, `candle_cache_ttl`, `chat_history_limit`, `chat_streaming`, `compact_mode`, `confirm_actions`, `connection_failed`, `connection_ok`, `credentials_saved`, `credentials_stored_note`, `dashboard_interval`, `data`, `display`, `editor`, `exchange`, `exchange_geo_restricted`, `exchange_hint`, `exchange_not_implemented`, `exchange_section`, `exchange_switch_failed`, `exchange_switched`, `exchange_switching`, `font_missing_hint`, `font_not_installed`, `font_scale`, `fonts`, `general`, `http_timeout`, `indicators`, `language`, `load_models`, `markets_interval`, `markets_sort`, `max_leverage`, `max_retries`, `min_rr`, `mode_ai_only`, `mode_engine`, `mode_hybrid`, `models_failed`, `models_loaded`, `models_loaded_free`, `narrative_enabled`, `no_key_needed`, `notifications`, `parallel_requests`, `performance`, `restore`, `restore_confirm`, `restore_done`, `risk`, `risk_balance`, `risk_percent`, `save_chat_history`, `saved`, `security`, `select_exchange`, `settings_preserved`, `show_toman`, `signal_ai_timeout`, `signal_mode`, `subtitle`, `test_connection`, `testing`, `theme`, `theme_dark`, `theme_descriptions`, `theme_light`, `theme_system`, `themes`, `timezone_display`, `timezone_local`, `timezone_section`, `timezone_utc`, `title`, `toman_auto`, `toman_manual_rate`, `toman_section`, `auto_detect`, `ollama_max_context`, `hide_stale_signals`, `model_fit`, `doctor`, `update`, `alerts_sound`, `ai_get_key_at`, `speed_profile`, `speed_fast`, `speed_balanced`, `speed_deep`.

### `localization/fa/sidebar.json`
کلیدهای سطح اول: `ai_checking`, `ai_off`, `ai_title`.

### `localization/fa/signals.json`
کلیدهای سطح اول: `act_on_trade`, `action`, `ai_disabled_hint`, `ai_driven`, `ai_fell_back`, `ai_generating`, `ai_step`, `ai_thinking`, `ai_unavailable`, `analysis`, `analysis_by_ai`, `analysis_by_template`, `analysis_empty`, `analysis_title`, `auto`, `click_row_hint`, `confidence`, `confidence_note`, `confirm_trade`, `context`, `copied`, `copy_text`, `current`, `detail_title`, `direction`, `engine_only`, `entry`, `entry_zone`, `export_pdf`, `forecast`, `forecast_note`, `generate`, `generated_at`, `generating`, `grade_fair`, `grade_good`, `grade_strong`, `grade_weak`, `group_by_direction`, `history`, `insufficient_data`, `invalidation`, `legend`, `legend_text`, `levels`, `leverage`, `long`, `market_structure`, `no_action_on_wait`, `no_signals`, `not_financial_advice`, `outcome`, `paper_trade_failed`, `paper_trade_note`, `paper_trade_opened`, `paper_trade_title`, `pdf_failed`, `pdf_saved`, `position_size`, `reason`, `reasoning`, `result`, `risk`, `risk_amount`, `risk_high`, `risk_low`, `risk_medium`, `risk_rejected`, `risk_reward`, `risk_unknown`, `scan`, `scan_ai_analyze`, `scan_ai_done`, `scan_ai_fallback`, `scan_ai_running`, `scan_cancelled`, `scan_done`, `scan_empty`, `scan_failed`, `scan_hint`, `scan_include_wait`, `scan_limit`, `scan_min_confidence`, `scan_progress`, `scan_results`, `scan_running`, `scan_stop`, `short`, `sort`, `sort_by`, `stop_loss`, `subtitle`, `take_profit`, `take_profit_n`, `timeframe_label`, `timeframes`, `tp1`, `tp2`, `tp3`, `trade`, `trend`, `view_analysis`, `wait`, `wait_no_trade`, `wait_note`, `wait_result`, `rerun_ai`, `rerun_running`, `rerun_done`, `rerun_failed`, `analysis_absent`, `rerun_saved`.

### `localization/fa/sizing.json`
کلیدهای سطح اول: `capital`, `entry`, `error_capital`, `error_entry`, `error_risk`, `error_same_price`, `error_stop`, `fee_percent`, `hint`, `leverage`, `result_title`, `risk_percent`, `row_fee`, `row_liquidation`, `row_margin`, `row_notional`, `row_quantity`, `row_reward`, `row_risk_amount`, `row_risk_reward`, `row_win_rate`, `stop_loss`, `take_profit`, `title`, `warn_fees_significant`, `warn_high_leverage`, `warn_high_risk`, `warn_low_rr`, `warn_margin_exceeds_capital`, `warn_near_liquidation`, `warn_stop_beyond_liquidation`.

### `localization/fa/trades.json`
کلیدهای سطح اول: `actions`, `cancel_trade`, `clear_history`, `close_hint`, `close_trade`, `closed`, `closed_manual`, `closed_stop_loss`, `closed_take_profit`, `confirm_clear`, `date`, `delete_trade`, `duration`, `empty`, `empty_hint`, `entry`, `exit`, `export_csv`, `fee`, `from_date`, `leverage`, `metrics`, `new_trade`, `no_open_trade_selected`, `note`, `opened`, `page_info`, `paper_notice`, `pnl`, `pnl_percent`, `quantity`, `side`, `sides`, `status`, `statuses`, `stop_loss`, `subtitle`, `symbol`, `take_profit`, `title`, `to_date`, `auto`.

### `localization/fa/tutorial.json`
کلیدهای سطح اول: `title`, `subtitle`, `search_placeholder`, `no_results`, `progress`, `next`, `previous`, `level_basic`, `level_intermediate`, `level_advanced`, `chapters`.

### `localization/fa/validity.json`
کلیدهای سطح اول: `adverse_move`, `aging_label`, `column`, `effective_rr`, `enter_before`, `entry_window_closing`, `entry_window_passed`, `expired`, `expired_label`, `expired_wait`, `explain_body`, `explain_title`, `fresh`, `fresh_label`, `invalidated_label`, `move_consumed`, `not_enterable_warning`, `stale_label`, `stop_hit`, `target_reached`, `title`, `valid_until`, `wait_active`.

### `localization/fa/wallet.json`
کلیدهای سطح اول: `amount`, `asset`, `assets`, `available`, `change_24h`, `connect_account`, `deposit`, `empty_assets`, `futures`, `futures_total`, `growth`, `in_orders`, `last_sync`, `never_synced`, `no_account`, `no_account_hint`, `price`, `profit_loss`, `range`, `recent_trades`, `share`, `spot`, `spot_futures`, `spot_total`, `subtitle`, `sync`, `sync_done`, `sync_empty`, `sync_failed`, `syncing`, `title`, `toman_value`, `total_value`, `transfer`, `value`, `wallet_type`, `withdraw`.

### `localization/fa/watchlist.json`
کلیدهای سطح اول: `title`, `subtitle`, `list`, `default_name`, `new`, `rename`, `delete`, `name_prompt`, `move_up`, `move_down`, `edit_note`, `note_prompt`, `remove_symbol`, `position`, `note`, `count`, `empty`, `created`, `create_failed`, `renamed`, `rename_failed`, `deleted`, `delete_confirm`, `removed`, `note_saved`, `moved`, `add_to_list`, `choose_list`.

### `localization/fa/wizard.json`
کلیدهای سطح اول: `title`, `welcome_title`, `welcome_subtitle`, `welcome_body`, `appearance_title`, `appearance_subtitle`, `exchange_title`, `exchange_subtitle`, `exchange_note`, `ai_title`, `ai_subtitle`, `ai_enable`, `ai_note`, `risk_title`, `risk_subtitle`, `risk_note`, `finish_title`, `finish_subtitle`, `finish_body`.

### `migrations/script.py.mako`
ابتدای فایل: """${message} / Revision ID: ${up_revision} / Revises: ${down_revision | comma,n}

### `mobile/buildozer.spec`
ابتدای فایل: [app] / # --- هویت برنامه --- / title = معامله‌گر هوشمند رمزارز

### `pyproject.toml`
ابتدای فایل: [build-system] / requires = ["setuptools>=68", "wheel"] / build-backend = "setuptools.build_meta"

### `release/PR_DESCRIPTION.md`
عنوان‌های اصلی: PR: v2.2.0 — Professional auto-trading terminal + full docs & release package / Title / Body / ✨ What's new (v2.0 → v2.2 — Auto Trading page only, other pages untouched) / 📚 Docs / 📦 Release package / ✅ Tests / Scope guardrails honored

### `release/RELEASE_NOTES_FA.md`
عنوان‌های اصلی: Crypto AI Trader — نسخهٔ ۲.۲.۰ / تازه‌های این نسخه / 📊 کارت‌های سرمایه / 📈 نمودار حرفه‌ای / 🤖 هوش مصنوعی روی پنل تصمیم / 🔍 پویش فرصت‌ها — همیشه زنده / 📋 موقعیت‌های باز — کنترل لحظه‌ای / ⭐ نمادهای مورد علاقه / خلاصهٔ نسل ۲ (۲.۰ و ۲.۱) / نصب / راستی‌آزمایی بسته

### `release/SHA256SUMS.txt`
ابتدای فایل: 4c24fe90ac8a5ce82e182fc8f75192ced5c0a873e59dd14f852c7de57327f608  CryptoAITrader-v2.2.0-2026-09-23.zip

### `requirements.txt`
ابتدای فایل: # ================================================================ / #  Crypto AI Trader — وابستگی‌ها / # ================================================================

### `scripts/build.sh`
ابتدای فایل: #!/usr/bin/env bash / # ====================================================================== / #  ساخت نسخه اجرایی — Crypto AI Trader (لینوکس و مک، برای توسعه)

### `scripts/build_apk.bat`
ابتدای فایل: @echo off / chcp 65001 >nul 2>&1 / REM ======================================================================

### `scripts/build_installer.bat`
ابتدای فایل: @echo off / chcp 65001 >nul 2>&1 / REM ======================================================================

### `scripts/build_windows.bat`
ابتدای فایل: @echo off / REM ====================================================================== / REM  ساخت نسخه اجرایی ویندوز — Crypto AI Trader

### `scripts/doctor.bat`
ابتدای فایل: @echo off / chcp 65001 >nul 2>&1 / REM ======================================================================

### `scripts/migrate.sh`
ابتدای فایل: #!/usr/bin/env bash / # اجرای مهاجرت‌های پایگاه داده. / #

### `scripts/run_dev.sh`
ابتدای فایل: #!/usr/bin/env bash / # اجرای برنامه در حالت توسعه با گزارش کامل. / set -euo pipefail

### `scripts/run_tests.sh`
ابتدای فایل: #!/usr/bin/env bash / # اجرای کامل آزمون‌ها در یک پوشه داده موقت. / #



## مکمل نسخهٔ 2.3.0 (نه بازنویسی نمایهٔ مبنا)

- `market/redundant_stream.py`: RedundantStream — factory مشترک، دو client، ادغام و watchdog.
- `market/engine.py`: streaming pool، get_ticker تازه، refresh_execution_quote، stream_stats، اشتراک تفاضلی، dedup تا پایان واقعی task.
- `market/live_feed.py`: REST بدون کش و timestamp برای تیک بدون تغییر قیمت.
- `trading/universe.py`: RotatingUniverse — علاقه‌مندی‌ها/دسته‌های بازار و Selected خالی.
- `trading/auto_trader.py`: قفل ورود، خروج single-flight، اسکن مستقل، net_unrealised، محافظ هزینه/ریسک و پایش هنگام توقف ورودی‌ها.
- `trading/paper_execution.py`: خروج paper خارج موتور با quote تازه و منع live.
- `trading/price_cache.py`: سن exchange/receive، نگهداری دفتر تازه، clear هنگام سوئیچ.
- `trading/confidence_source.py` و `scalp_service.py`: چرخش و فیلتر قبل از تحلیل؛ SL/TP سیگنال حفظ می‌شوند.
- `trading/trade_monitor.py` و `app/database/repositories/trade_repository.py`: درصد/PnL خالص، حد ضرر مؤثر و سود روز UTC در DB.
- `ui/controllers/main_controller.py`: ورود/خروج مشترک، عدم پایش دوگانه، تاریخچهٔ زنده، feed/tick هم‌صرافی و اسکن AI محدود موازی.
- `ui/pages/trades_page.py`: show_open_history، تاریخچهٔ ۱۵ستونی و مودال به جای خروج روی double-click.
- `ui/dialogs/trading_dialogs.py`: جزئیات، کارمزد و منع خروج رکورد بسته.
- `tests/test_v230_execution.py`, `test_v230_streams_selection.py`, `test_v230_controller_contracts.py`: ۵۰ رگرسیون بدون لینک Qt.
- `tests/test_v230_ui.py`: سه smoke test بومی که در محیط فاقد libGL در سطح ماژول skip می‌شوند.
- جزئیات و محدودیت‌ها: `docs/RELEASE_2.3.0_FA.md`. خط‌های نمایهٔ مبنا برای فایل‌های تغییریافته معتبر فرض نشوند.

## مکمل نسخهٔ 2.3.1

- `market/engine.py`: `rate_limit_retry_after`، مکث سراسری REST، `rest_health()`، `all_tickers_fetched_at`، کش مشترک حداقل ۲ ثانیه، snapshot هر ۳۰ ثانیه.
- `market/live_feed.py`: نظرسنجی ۳ ثانیه با کش ۵ ثانیه، تازگی از REST یا WS، `data_age_seconds`، `PriceUpdate.changed`.
- `market/providers/toobit/rest_client.py`: 429/418 → `RateLimitError` با `retry_after`، بدون تکرار.
- `ui/widgets/dashboard_widgets.py`: HealthTile، StatusDot، BreadthBar، MoversList.
- `ui/pages/dashboard_page.py`: بلوک `command`، کارت movers، `set_connection_health/set_portfolio/set_engine_status/set_breadth/set_movers`.
- `ui/controllers/main_controller.py`: `summarise_market`، `_refresh_command_center`.
- آزمون‌ها: `tests/test_v231_connection.py`، `tests/test_v231_dashboard.py`.

## مکمل نسخهٔ 2.3.2

- `market/providers/lbank/constants.py`: `LBANK_WS_URLS` (رسمی `api.lbank.info` اول)، `LBANK_REST_URLS`، جدول خطای رسمی؛ `RATE_LIMIT_ERROR_CODES={10004}`، `RATE_LIMIT_RETRY_AFTER`، `REGION_BLOCKED_ERROR_CODES={10205}`.
- `market/providers/lbank/rest_client.py`: 429/418 و 10004 → `RateLimitError(retry_after)` بدون تکرار؛ `_rotate_base_url` فقط روی ConnectError/ConnectTimeout و فقط برای نشانی پیش‌فرض؛ `base_url`.
- `market/providers/lbank/provider.py`: `ping()` محدودیت نرخ را بالا می‌دهد؛ `create_websocket_client` برای هر اتصال موازی از دامنهٔ بعدی شروع می‌کند.
- `market/providers/lbank/websocket_client.py`: `urls`/`current_url`/`last_error`، چرخش دامنه وقتی اتصال بدون داده شکست بخورد، ping کلاینت هر ۲۰ ثانیه، مهلت سکوت ۶۰ ثانیه، اشتراک با فاصلهٔ ۲۰ms، پراکسی خراب → `proxy=None`.
- `market/rate_limiter.py`: پارامتر `no_retry_on` در `retry_async`.
- `market/redundant_stream.py`: `stats()` کلیدهای اختیاری `endpoints` و `last_error`.
- آزمون: `tests/test_v232_lbank.py` (بدون شبکهٔ واقعی).

## مکمل نسخهٔ 2.4.0

- `signals/scan_universe.py` (تازه): `UNIVERSE_TOP/ALL`، `normalize_universe`، `split_symbol`، `is_stable_pair`، `is_leveraged_token(symbol, known_bases)` (پسوند UP/DOWN/BULL/BEAR فقط وقتی پیشوند دارایی بازار باشد؛ SYRUP حذف نمی‌شود)، `UniverseFilter.create(min_turnover, smart, quotes)`، `priority_score` (log10 گردش + |تغییر|/25)، `build_universe(tickers, symbols, mode, limit, filters)`.
- `signals/scanner.py`: `candidate_symbols(limit, universe, filters)` — مسیر قدیمی برای top بدون پالایش دست‌نخورده؛ `_smart_candidates`؛ `scan(..., universe, filters, on_signal)`.
- `app/application.py`: `scan_market(..., universe, min_turnover, smart_filter, on_signal)` و ساخت `UniverseFilter`.
- `signals/auto_scanner.py`: `SOURCE_FOUND/MARKET/BOTH`، `normalize_source`، `MAX_FOCUS_SIZE=100`، فیلدهای `source/universe/min_turnover/smart_filter`، ویژگی‌های `sweep_active`/`focus_active`، `seed_focus(signals, replace)`؛ حالت found هرگز چرخش/bootstrap ندارد.
- `ui/pages/signals_page.py`: `scan_scope_combo`، `scan_smart_check`، `scan_turnover_spin` (هزار USDT)، `scan_universe_options()`، `scan_settings()/set_scan_settings()`، سیگنال `scan_settings_changed`، برآورد زمان در `set_scan_progress`؛ کارت خودکار: `auto_source_combo`، `auto_universe_combo`، `auto_sweep_limit_spin`، `auto_smart_check`، `auto_turnover_spin`؛ `auto_sweep_check` پنهان و هم‌گام با منبع.
- `ui/controllers/main_controller.py`: سیگنال‌های Qt `scan_partial_found`، `auto_scan_signal_found`، `auto_scan_progress`؛ `_on_scan_partial_signal`/`_flush_scan_live` (دسته‌ای ۸۰۰ms)، `stop_market_scan` نتیجهٔ نیمه‌کاره را نگه می‌دارد، `_seed_auto_focus`، `save_scan_settings`/`_load_scan_settings`، `_execute_auto_job` برای چرخش کامل universe/min_turnover/smart_filter را می‌فرستد.
- `app/config/defaults.py`: کلیدهای `signals.auto_scan_{source,universe,min_turnover,smart_filter}` و `signals.scan_{universe,limit,min_turnover,smart_filter}`.
- آزمون: `tests/test_v240_scan_universe.py`.

## مکمل نسخهٔ 2.4.1

- `market/engine.py`: `bulk_fetch()` / `is_bulk_fetch()` (ContextVar)؛ در حالت انبوه `get_candles` نه `_persist_candles` می‌کند نه در `MarketCache` می‌نویسد (خواندن از کش آزاد است).
- `signals/scanner.py`: `DEFAULT_CPU_DUTY=0.6`، `BACKGROUND_CPU_DUTY=0.35`، `CpuGovernor(duty, clock, cpu_clock)` با `time.thread_time`؛ `scan(..., cpu_duty)` داخل `bulk_fetch()` و `_scan`؛ `_wait_for_cooldown` (فقط مقدار عددی `rest_cooldown_remaining`).
- `signals/engine.py`: `_gate()` (asyncio.Lock تنبلِ متعلق به حلقه) + `_compute_timeframe`؛ بعد از هر محاسبه `sleep(0)`.
- `indicators/engine.py`: `calculate` → `_calculate(..., frame_holder, parameters)`؛ `calculate_many` یک DataFrame مشترک می‌سازد. `indicators/base.py`: تبدیل NaN→None با numpy.
- `app/application.py`: `scan_market(..., cpu_duty)`؛ هر ۲۰ ذخیره یک `sleep(0)`.
- `ui/pages/signals_page.py`: `SCAN_MAX_ROWS=200`، `scan_cap_note`، `_fill_scan_rows` با `setUpdatesEnabled(False)` و سرستون Interactive حین پرکردن.
- `ui/controllers/main_controller.py`: گزارش پیشرفت دستی ≥۰٫۱۵s و خودکار ≥۰٫۵s؛ `_flush_scan_live` فاصلهٔ تطبیقی (۰٫۸ تا ۵ ثانیه)؛ پویش خودکار با `BACKGROUND_CPU_DUTY`.
- آزمون: `tests/test_v241_performance.py`.

## مکمل نسخهٔ 2.4.2

- `signals/compute_pool.py` (تازه، بدون PySide): `compute_timeframe_job(symbol, timeframe, candles, default_parameters)` → `("ok", payload بدون candles)` یا `("error", متن)`؛ `ComputePool(workers, idle_shutdown)` با `compute_timeframe()` (None = محاسبهٔ محلی)، `shutdown()`، `disable()`، `enabled/running/jobs_done/fallbacks`؛ `default_worker_count()`؛ `lower_process_priority()`؛ `MAX_WORKERS=2`، `IDLE_SHUTDOWN_SECONDS=180`، `MAX_CONSECUTIVE_FAILURES=3`. زمینهٔ spawn.
- `signals/engine.py`: تابع سطح ماژول `compute_timeframe_analysis(indicators, symbol, timeframe, candles)`؛ `SignalEngine.set_compute_pool(pool)`؛ `_analyze_timeframe` در `is_bulk_fetch()` اول استخر را امتحان می‌کند.
- `indicators/engine.py`: `IndicatorEngine.default_parameters()` (رونوشت).
- `app/application.py`: `compute_pool()` (تنبل؛ `performance.process_pool`، `CRYPTOAI_NO_PROCESS_POOL`)، `_should_store_scanned(signal, now)`، ثابت‌های `SCAN_DEDUP_SECONDS=1800`، `SCAN_DEDUP_CONFIDENCE=5`؛ `stop()` استخر را می‌بندد.
- `main.py`: `multiprocessing.freeze_support()` زیر `__main__`.
- `ui/responsiveness.py` (تازه): `UiStallWatchdog` (ضربان ۲۵۰ms، آستانهٔ ۱٫۵s، لاگ پشتهٔ نخ رابط هر ≥۳۰s)، `ShowWatcher`.
- `ui/signal_share.py` (تازه): `signal_symbol`، `format_price`، `format_signal_text(signal, translator)`، `copy_to_clipboard`.
- `ui/dialogs/signal_detail_dialog.py`: `copy_symbol_button`، `copy_info_button`، `share_text()`، `copy_symbol()`، `copy_info()`، `_flash_copied`.
- `ui/pages/signals_page.py`: سیگنال `copy_notice(str)`؛ `scan_row_at`، `history_row_at`، `_install_copy_support`، `_show_copy_menu`، `copy_signal_symbol`، `copy_signal_info`؛ برچسب `scan_copy_hint`.
- `ui/controllers/main_controller.py`: `_refresh_outcome_view` تنبل (`_outcome_view_stale`، `run_blocking("outcome-view")`)، `_on_outcome_view_shown`، `_terminal_timer_tick`، `_stall_watchdog` در `start()`/`shutdown()`، `_on_history_double_clicked` با نگاشت شناسه، اتصال `copy_notice` → `_toast`.
- `localization/{en,fa}/signals.json`: گروه `share.*`.
- آزمون: `tests/test_v242_lightweight_and_copy.py` (۲۵)؛ `tests/conftest.py` استخر را در آزمون‌ها خاموش می‌کند.

## مکمل نسخهٔ 2.5.0

| فایل | نقش | اتصال |
|---|---|---|
| `trading/staged_targets.py` | منطق خالص اهداف پلکانی: `clean_targets`, `stage_fractions`, `next_step`, `targets_text` | `trade_monitor.evaluate_staged`، `MainController._on_trade_requested` |
| `trading/paper_account.py` | موجودی جعلی کاغذی: `PaperAccount`, `build_account`, کلیدهای `paper.*` | `MainController._paper_account/_trading_capital/_portfolio_snapshot` |
| `trading/trade_monitor.py` | `LivePosition` با `targets/targets_hit/original_quantity/realized_gross`؛ `evaluate_staged` | `MainController._trade_monitor_tick` → `_apply_trade_step` |
| `app/database/repositories/trade_repository.py` | `partial_close`, `realized_pnl_since`؛ `close_trade` سود جزئی را منظور می‌کند | پایش و کیف پول |
| `market/providers/lbank/rest_client.py` | `_handle_response(contract=True)` و کدهای خطای قرارداد | `post_contract_signed` |
| `market/providers/lbank/provider.py` | `_parse_spot_details`, `_parse_futures_details`, `last_spot_details`, `last_futures_details` | `ExchangeAccountService.sync_balances` → `extra_config.wallet_details` |
| `ui/pages/wallet_page.py` | سه زبانه، `MetricStrip`, `set_spot`, `set_futures`, `set_paper`, سیگنال `paper_sync_requested` | `MainController.refresh_wallet/_fill_wallet_tabs/_fill_paper_panel` |
| `ui/pages/trades_page.py` | `HISTORY_COLUMNS`, `HISTORY_TEXT_KEYS`, `_history_item`، به‌روزرسانی درجا | `MainController._trade_row/_trade_stage_texts` |
| `ui/dialogs/signal_detail_dialog.py` | `share_to`, `trade_payload`, `trade_opened`, منوی اشتراک | `trade_requested` → `_on_trade_requested(payload, dialog=d)` |
| `ui/signal_share.py` | `SHARE_TARGETS`, `share_url`, `share_mode`, `open_url` | مودال جزئیات |
| `ui/widgets/position_calculator.py` | TP2/TP3، `signal_entry`, `trade_values`, `set_capital_source` | مودال جزئیات |
| `ui/widgets/chrome.py` | `SearchBox` کشسان (`SEARCH_MIN/MAX_WIDTH`, `SEARCH_HEIGHT`) | `TopBar` |


## مکمل نسخهٔ 2.5.1

| فایل | نقش | اتصال |
|---|---|---|
| `market/market_rank.py` (تازه) | `MARKET_CAP_ORDER/RANK`، `split_symbol`، `turnover_usdt`، `sort_by_market_value`، `quote_usdt_prices`، `price_decimals`، `compact_number` | `MarketsPage` (حالت `market_cap`، ستون قیمت/حجم)، `MainController.refresh_markets` |
| `market/providers/lbank/rest_client.py` | `signed_headers()`؛ `post_signed` امضا را در سرآیند و بدنه می‌فرستد | همهٔ درخواست‌های خصوصی اسپات |
| `market/providers/lbank/constants.py` | `USER_INFO_ACCOUNT`، `USER_INFO_LEGACY` | زنجیرهٔ موجودی اسپات |
| `market/providers/lbank/provider.py` | `_spot_rows` (سه قالب)، `last_sync_report`، حدس فیلدهای حساب قرارداد، `fields`/`note` در گزارش | `ExchangeAccountService.sync_balances` |
| `app/core/exchange_account_service.py` | شکست یک بخش غیرکشنده؛ `details["report"]` با `_clean_report` (بدون کلید) | `MainController._fill_wallet_report` |
| `ui/pages/wallet_page.py` | `status_panel`/`set_sync_report`/`report_text`، `auto_sync_toggled`/`auto_sync_checkbox`، `spot_search`، `hide_small_checkbox`، `SMALL_BALANCE_USDT` | `MainController.start_wallet_auto_sync`، `_on_wallet_auto_sync_toggled`، `_on_wallet_activated` |
| `app/database/repositories/symbol_repository.py` | `add_to_watchlist(symbol, exchange=None)` با ساخت رکورد، `is_in_watchlist`، `remove_from_watchlist` از هر صرافی، `_normalize_symbol`، `_find_record` | `MainController.set_watchlist_membership`، `_sync_symbol_table` |
| `ui/pages/markets_page.py` | `build_context_menu`، سیگنال‌های `analyze_requested`/`signal_requested`، `_price_text`، `_high_text`، `_turnover_text`، `_quote_prices` | `MainController._coin_analyze/_coin_signal/create_price_alert/set_watchlist_membership` |
| `ui/controllers/main_controller.py` | `set_watchlist_membership`، `_sync_symbol_table`، `WALLET_AUTO_SYNC_MS`، `sync_wallet(silent=)`، `_fill_wallet_report`، `_wallet_error_hint` | صفحه‌های بازار/کیف پول/مودال نماد |

## مکمل نسخهٔ 2.5.2

| فایل | نقش | اتصال |
|---|---|---|
| `app/exceptions/errors.py` | `AccessBlockedError(NetworkError)`: رد پیش از API (Cloudflare/فایروال) | `no_retry_on` کلاینت LBank، حلقهٔ فیوچرز |
| `market/providers/lbank/rest_client.py` | `BROWSER_HEADERS`، `CLOUDFLARE_REASONS`، `_cloudflare_code`، `_classify_forbidden` (401/403) | `_handle_response`، `_contract_client` |
| `market/providers/lbank/provider.py` | `fetch_futures_balance` پس از `AccessBlockedError` می‌شکند | `ExchangeAccountService.sync_balances` |
| `ui/controllers/main_controller.py` | `_wallet_error_hint` ← `wallet.hint.blocked` / `blocked_region` | پنل گزارش کیف پول |
