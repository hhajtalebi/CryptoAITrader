; ======================================================================
;  اسکریپت Inno Setup برای ساخت فایل نصبی ویندوز
;  Crypto AI Trader — حسین حاج طالبی
;
;  این فایل به‌دست tools/build_installer.py با نسخهٔ درست پر می‌شود.
;  ساخت دستی:
;      iscc installer\CryptoAITrader.iss
; ======================================================================

#define AppName        "Crypto AI Trader"
#define AppNameFa      "معامله‌گر هوشمند رمزارز"
#define AppPublisher   "حسین حاج طالبی"
#define AppExeName     "CryptoAITrader.exe"
#ifndef AppVersion
  #define AppVersion   "0.0.0"
#endif

[Setup]
AppId={{8F3B1C42-9E7A-4D51-B6C8-2A5E9F1D7C30}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\CryptoAITrader
DefaultGroupName={#AppName}
; کاربر نباید برای نصب به دسترسی مدیر نیاز داشته باشد؛ نصب در پوشهٔ
; کاربر هم کاملاً کار می‌کند و تجربهٔ نصب را ساده‌تر می‌کند.
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\installer
OutputBaseFilename=CryptoAITrader-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; رابط نصب دوزبانه؛ فارسی پیش‌فرض کاربر است.
ShowLanguageDialog=auto
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExeName}
; نسخهٔ قدیمی پیش از نصب تازه پاک می‌شود تا فایل‌های یتیم نمانند.
AppMutex=CryptoAITraderSingleInstance

[Languages]
Name: "fa"; MessagesFile: "compiler:Default.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "ساخت میان‌بر روی دسکتاپ"; GroupDescription: "میان‌برها:"
Name: "launchonstart"; Description: "اجرای خودکار هنگام روشن‌شدن ویندوز"; GroupDescription: "اختیاری:"; Flags: unchecked

[Files]
; کل خروجی PyInstaller. `recursesubdirs` لازم است چون ترجمه‌ها،
; قالب‌های پرامپت و قلم‌ها در زیرپوشه‌اند.
Source: "..\dist\CryptoAITrader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\حذف {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: launchonstart

[Run]
Filename: "{app}\{#AppExeName}"; Description: "اجرای {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; فقط فایل‌های ساخته‌شده هنگام اجرا پاک می‌شوند.
; **دادهٔ کاربر (پایگاه داده و تنظیمات) عمداً دست‌نخورده می‌ماند** —
; حذف برنامه نباید سابقهٔ سیگنال‌ها و حساب‌های صرافی را نابود کند.
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\__pycache__"
