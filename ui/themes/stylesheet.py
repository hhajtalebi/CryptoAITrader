"""
ساخت برگهٔ سبک (QSS) از روی توکن‌های پوسته.

قالب زیر تنها جایی است که ظاهر همهٔ مؤلفه‌ها تعریف می‌شود. هیچ صفحه‌ای
حق ندارد رنگ سخت‌کدشده بنویسد؛ به این ترتیب افزودن پوستهٔ تازه بدون
دست‌زدن به صفحه‌ها ممکن است.

آکولادها در QSS باید دوبل نوشته شوند چون از `str.format` استفاده می‌کنیم.
"""

from __future__ import annotations
import base64


from ui.themes.fonts import DEFAULT_FONT_KEY, font_stack
from ui.themes.tokens import ThemeTokens

#: زنجیرهٔ قلم پیش‌فرض وقتی فراخواننده چیزی نداده است
DEFAULT_FONT_STACK = font_stack(DEFAULT_FONT_KEY)

STYLESHEET_TEMPLATE = """
* {{ outline: none; }}

QWidget {{
    background-color: {bg};
    color: {text};
    font-family: {font_family};
    font-size: {font_md}px;
}}
QMainWindow, QDialog {{ background-color: {bg}; }}
QToolTip {{
    background-color: {surface_raised}; color: {text};
    border: {border_width}px solid {border_strong};
    border-radius: {radius_sm}px; padding: 5px 8px;
}}

/* ---------------------------------------------------------------- متن */
QLabel {{ background: transparent; }}
QLabel[role="title"] {{ font-size: {font_xl}px; font-weight: 800; color: {text}; }}
QLabel[role="subtitle"] {{ font-size: {font_lg}px; color: {text_muted}; font-weight: 600; }}
QLabel[role="section"] {{ font-size: {font_lg}px; font-weight: 700; color: {text}; }}
QLabel[role="metric"] {{ font-size: {font_metric}px; font-weight: 800; color: {text}; }}
QLabel[role="metric_up"] {{ font-size: {font_metric}px; font-weight: 800; color: {success}; }}
QLabel[role="metric_down"] {{ font-size: {font_metric}px; font-weight: 800; color: {danger}; }}
QLabel[role="symbol"] {{ font-weight: 700; color: {text}; }}
QLabel[role="muted"] {{ color: {text_muted}; }}
QLabel[role="faint"] {{ color: {text_faint}; font-size: {font_xs}px; }}
QLabel[role="accent"] {{ color: {accent}; font-weight: 700; }}
QLabel[role="bullish"] {{ color: {success}; font-weight: 700; }}
QLabel[role="bearish"] {{ color: {danger}; font-weight: 700; }}
QLabel[role="neutral"] {{ color: {neutral}; font-weight: 700; }}
QLabel[role="badge"] {{
    background-color: {surface_alt}; border: {border_width}px solid {border};
    border-radius: {radius_pill}px; padding: 3px 10px;
    color: {text_muted}; font-weight: 700; font-size: {font_xs}px;
}}
QLabel[role="chip_up"] {{
    background-color: {success_soft}; color: {success}; font-weight: 700;
    border-radius: {radius_pill}px; padding: 3px 10px; font-size: {font_xs}px;
}}
QLabel[role="chip_down"] {{
    background-color: {danger_soft}; color: {danger}; font-weight: 700;
    border-radius: {radius_pill}px; padding: 3px 10px; font-size: {font_xs}px;
}}
QLabel[role="chip_warn"] {{
    background-color: {warning_soft}; color: {warning}; font-weight: 700;
    border-radius: {radius_pill}px; padding: 3px 10px; font-size: {font_xs}px;
}}
QLabel[role="chip_info"] {{
    background-color: {info_soft}; color: {info}; font-weight: 700;
    border-radius: {radius_pill}px; padding: 3px 10px; font-size: {font_xs}px;
}}
QLabel[role="coin"] {{
    border-radius: {radius_pill}px; color: #ffffff;
    font-weight: 800; font-size: {font_xs}px;
}}

/* --------------------------------------------------------------- قاب‌ها */
QFrame[role="card"] {{
    background-color: {surface};
    border: {border_width}px solid {border};
    border-radius: {radius_lg}px;
}}
QFrame[role="card_accent"] {{
    background-color: {surface};
    border: {border_width}px solid {border};
    border-top: {card_top_accent}px solid {primary};
    border-radius: {radius_lg}px;
}}
QFrame[role="stat"] {{
    background-color: {surface_alt};
    border: {border_width}px solid {border};
    border-radius: {radius_md}px;
}}
QFrame[role="plain"] {{ background-color: transparent; border: none; }}
QFrame[role="separator"] {{ background-color: {border}; max-height: 1px; border: none; }}
QFrame[role="vseparator"] {{ background-color: {border}; max-width: 1px; border: none; }}

/* ------------------------------------------------------- نوار بالا/کنار */
QFrame[role="topbar"] {{
    background-color: {topbar_bg};
    border: none;
    border-bottom: {border_width}px solid {topbar_border};
    border-radius: 0px;
}}
QFrame[role="sidebar"] {{
    background-color: {sidebar_bg};
    border: none;
    border-radius: 0px;
}}
QFrame[role="sidebar"] QLabel {{ color: {sidebar_text}; }}
QFrame[role="sidebar"] QLabel[role="title"] {{ color: {sidebar_active_text}; }}
/* کارت اتصال داخل نوار کناری — رنگ مستقل تا روی نوار تیره هم خوانا بماند */
QFrame[role="connection"] {{
    background-color: {sidebar_hover};
    border: {border_width}px solid {sidebar_active_bg};
    border-radius: {radius_md}px;
}}
QFrame[role="connection"] QLabel {{ color: {sidebar_text}; }}
QFrame[role="connection"] QLabel[role="badge"] {{
    background-color: {sidebar_active_bg};
    border: none;
    color: {sidebar_active_text};
}}
QFrame[role="connection"] QLabel[role="faint"] {{ color: {sidebar_text}; }}

/* کارت وضعیت هوش مصنوعی در نوار کناری.
   حاشیهٔ رنگی سمت راست آن را از کارت اتصال صرافی جدا می‌کند بدون آنکه
   شلوغ شود؛ هر دو کارت پشت سر هم در پایین نوار می‌نشینند. */
QFrame[role="aiStatus"] {{
    background-color: {sidebar_hover};
    border: {border_width}px solid {sidebar_active_bg};
    border-right: 3px solid {accent};
    border-radius: {radius_md}px;
}}
QFrame[role="aiStatus"]:hover {{
    background-color: {sidebar_active_bg};
}}
QFrame[role="aiStatus"] QLabel {{ color: {sidebar_text}; }}
QFrame[role="aiStatus"] QLabel[role="badge"] {{
    background-color: {sidebar_active_bg};
    border: none;
    color: {sidebar_active_text};
}}
QFrame[role="aiStatus"] QLabel[role="faint"] {{ color: {sidebar_text}; }}

QFrame[role="featurebar"] {{
    background-color: {surface_alt};
    border: none;
    border-top: {border_width}px solid {border};
    border-radius: 0px;
}}

/* -------------------------------------------------------------- دکمه‌ها */
QPushButton {{
    background-color: {surface_alt};
    color: {text};
    border: {border_width}px solid {border};
    border-radius: {radius_lg}px;
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton:hover {{ background-color: {surface_raised}; border-color: {border_strong}; }}
QPushButton:pressed {{ background-color: {selection}; }}
QPushButton:disabled {{ color: {text_faint}; background-color: {surface_alt}; }}

QPushButton[role="primary"] {{
    background: {primary_bg};
    color: {primary_text};
    border: none;
    border-radius: {radius_lg}px;
    padding: 9px 20px;
    font-weight: 700;
}}
QPushButton[role="primary"]:hover {{ background: {primary_hover}; }}
QPushButton[role="primary"]:disabled {{ background: {surface_raised}; color: {text_faint}; }}

QPushButton[role="ghost"] {{
    background: transparent; border: none; color: {text_muted}; padding: 6px 10px;
}}
QPushButton[role="ghost"]:hover {{ color: {text}; background-color: {surface_alt}; }}

QPushButton[role="icon"] {{
    background-color: {surface_alt};
    border: {border_width}px solid {border};
    border-radius: {radius_md}px;
    padding: 6px;
    font-size: {font_lg}px;
}}
QPushButton[role="icon"]:hover {{ background-color: {surface_raised}; }}
QPushButton[role="icon"]:checked {{
    background-color: {selection}; border-color: {primary}; color: {primary};
}}

QPushButton[role="danger"] {{
    background-color: {danger}; color: #ffffff; border: none;
    border-radius: {radius_md}px; padding: 8px 16px; font-weight: 700;
}}
/* دکمهٔ خطرناکِ غیرفعال نباید همچنان قرمزِ پررنگ بماند، وگرنه کاربر
   فکر می‌کند قابل فشردن است. */
QPushButton[role="danger"]:disabled {{
    background-color: {surface_raised}; color: {text_faint};
}}
/* نقش «موفقیت» تا امروز قاعدهٔ پایه نداشت و دکمه خاکستری معمولی
   درمی‌آمد؛ حالا سبز است و حالت غیرفعالش هم تعریف شده. */
QPushButton[role="success"] {{
    background-color: {success}; color: #ffffff; border: none;
    border-radius: {radius_md}px; padding: 8px 16px; font-weight: 700;
}}
QPushButton[role="success"]:disabled {{
    background-color: {surface_raised}; color: {text_faint};
}}

/* تراشهٔ فیلتر و بخش‌بندی */
QPushButton[role="chip"] {{
    background-color: {surface_alt};
    border: {border_width}px solid {border};
    border-radius: {radius_pill}px;
    padding: 6px 16px;
    color: {text_muted};
    font-weight: 600;
}}
QPushButton[role="chip"]:hover {{ background-color: {surface_raised}; color: {text}; }}
QPushButton[role="chip"]:checked {{
    background: {primary_bg}; color: {primary_text}; border-color: {primary};
}}

/* بخش‌بندی تایم‌فریم (segmented control) */
QPushButton[role="segment"] {{
    background: transparent;
    border: none;
    border-radius: {radius_pill}px;
    padding: 6px 14px;
    color: {text_muted};
    font-weight: 600;
}}
QPushButton[role="segment"]:hover {{ color: {text}; }}
QPushButton[role="segment"]:checked {{
    background: {primary_bg}; color: {primary_text}; font-weight: 700;
}}

/* دکمه‌های ناوبری کناری */
QPushButton[role="nav"] {{
    background: transparent;
    border: none;
    border-radius: {radius_md}px;
    padding: 10px 14px;
    text-align: left;
    color: {sidebar_text};
    font-weight: 600;
    font-size: {font_md}px;
}}
QPushButton[role="nav"]:hover {{ background-color: {sidebar_hover}; color: {sidebar_active_text}; }}
QPushButton[role="nav"]:checked {{
    background: {sidebar_active_fill};
    color: {sidebar_active_text};
    font-weight: 700;
}}

/* -------------------------------------------------------------- ورودی‌ها */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background-color: {surface_alt};
    border: {border_width}px solid {border};
    border-radius: {radius_md}px;
    padding: 7px 10px;
    color: {text};
    selection-background-color: {selection};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
    border-color: {primary};
}}

/* ---- ورودی‌های عددی --------------------------------------------------
   کاربر گفت «این پوت انتخاب اندازه متن خراب است، علامت‌های زیاد اذیت
   می‌کند و مقدار را سنتر کن». ریشه‌اش این بود که هیچ قاعده‌ای برای
   دکمه‌های بالا/پایین نوشته نشده بود، پس Qt فلش‌های پیش‌فرض سیستمی را
   می‌کشید: دو مثلث ریز چسبیده به لبه که با بقیهٔ طراحی هم‌خوان نبود.
   حالا دکمه‌ها پهنای مشخص، جداکنندهٔ نرم و فلش ساده دارند و خود عدد
   وسط‌چین است.                                                        */
QSpinBox, QDoubleSpinBox {{
    padding: 7px 6px;
    min-height: 20px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    width: 22px;
    border: none;
    background: transparent;
    margin: 2px;
    border-radius: {radius_sm}px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-position: top right;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-position: bottom right;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {surface_raised};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({arrow_up_icon});
    width: 9px; height: 9px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({arrow_down_icon});
    width: 9px; height: 9px;
}}
QSpinBox::up-arrow:disabled, QSpinBox::down-arrow:disabled,
QDoubleSpinBox::up-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {{
    opacity: 0.3;
}}
QLineEdit[role="search"] {{
    border-radius: {radius_pill}px; padding: 8px 16px;
    background-color: {surface_alt};
}}
QLineEdit:disabled, QTextEdit:disabled {{ color: {text_faint}; }}

QComboBox {{
    background-color: {surface_alt};
    border: {border_width}px solid {border};
    border-radius: {radius_md}px;
    padding: 7px 12px;
    color: {text};
    min-height: 18px;
}}
QComboBox:hover {{ border-color: {border_strong}; }}
QComboBox:focus {{ border-color: {primary}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: {surface};
    border: {border_width}px solid {border};
    border-radius: {radius_md}px;
    color: {text};
    selection-background-color: {selection};
    outline: none;
    padding: 4px;
}}

QCheckBox, QRadioButton {{ spacing: 8px; color: {text}; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px; height: 16px;
    border: {border_width}px solid {border_strong};
    border-radius: {radius_sm}px;
    background-color: {surface_alt};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {primary}; border-color: {primary};
}}
QRadioButton::indicator {{ border-radius: 8px; }}

/* ------------------------------------------------------------- جدول‌ها */
QTableWidget, QTableView {{
    background-color: {surface};
    alternate-background-color: {surface_alt};
    border: none;
    gridline-color: transparent;
    color: {text};
    selection-background-color: {selection};
    selection-color: {text};
}}
QTableWidget::item, QTableView::item {{
    padding: 8px 6px;
    border-bottom: {fx_row_divider}px solid {border};
}}
QTableWidget::item:selected, QTableView::item:selected {{ background-color: {selection}; }}
QHeaderView {{ background-color: transparent; }}
QHeaderView::section {{
    background-color: {surface_alt};
    color: {text_muted};
    border: none;
    border-bottom: {border_width}px solid {border};
    padding: 9px 6px;
    font-weight: 700;
    font-size: {font_xs}px;
}}
QHeaderView::section:hover {{ color: {text}; }}
QTableCornerButton::section {{ background-color: {surface_alt}; border: none; }}

QListWidget, QTreeWidget {{
    background-color: {surface};
    border: {border_width}px solid {border};
    border-radius: {radius_md}px;
    color: {text};
    outline: none;
    padding: 4px;
}}
QListWidget::item {{ padding: 9px 10px; border-radius: {radius_sm}px; }}
QListWidget::item:hover {{ background-color: {surface_alt}; }}
QListWidget::item:selected {{ background-color: {selection}; color: {text}; }}

/* -------------------------------------------------------------- زبانه‌ها */
QTabWidget::pane {{ border: none; background: transparent; }}
QTabBar::tab {{
    background: transparent;
    color: {text_muted};
    padding: 9px 16px;
    margin-right: 2px;
    border: none;
    border-bottom: 2px solid transparent;
    /* گوشهٔ بالا گرد می‌شود تا هیچ لبهٔ تیزی در رابط نماند */
    border-top-left-radius: {radius_md}px;
    border-top-right-radius: {radius_md}px;
    font-weight: 600;
}}
QTabBar::tab:hover {{ color: {text}; background-color: {surface_alt}; }}
QTabBar::tab:selected {{ color: {text}; border-bottom: 2px solid {primary}; font-weight: 700; }}

/* ------------------------------------------------------------ نوار پیمایش */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {scroll}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {border_strong}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: {scroll}; border-radius: 5px; min-width: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; width: 0px; border: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ------------------------------------------------------------ نوار پیشرفت */
QProgressBar {{
    background-color: {surface_alt};
    border: none;
    border-radius: {radius_pill}px;
    height: 6px;
    text-align: center;
    color: {text_muted};
}}
QProgressBar::chunk {{ background: {primary_bg}; border-radius: {radius_pill}px; }}

QSlider::groove:horizontal {{
    background: {surface_raised}; height: 4px; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {primary}; width: 14px; height: 14px;
    margin: -5px 0; border-radius: 7px;
}}

/* ---------------------------------------------------------- نوار وضعیت */
QStatusBar {{
    background-color: {surface};
    color: {text_muted};
    border-top: {border_width}px solid {border};
}}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background-color: {border}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

QMenu {{
    background-color: {surface};
    border: {border_width}px solid {border};
    border-radius: {radius_md}px;
    padding: 6px;
    color: {text};
}}
QMenu::item {{ padding: 8px 22px; border-radius: {radius_sm}px; }}
QMenu::item:selected {{ background-color: {selection}; }}
QMenu::separator {{ height: 1px; background: {border}; margin: 5px 8px; }}

/* --------------------------------------------------------- نشان کاربر
   دکمهٔ حساب کاربری: آواتارِ ترسیمی در یک سمت می‌نشیند، پس آن سمت پدینگ
   بیشتری می‌گیرد تا نام روی آواتار نیفتد. در راست‌به‌چپ آینه می‌شود. */
QToolButton[role="user_chip"] {{
    background-color: {surface_alt};
    color: {text};
    border: {border_width}px solid {border};
    border-radius: {radius_pill}px;
    padding: 4px 14px 4px 38px;
    font-weight: 600;
}}
QToolButton[role="user_chip"]:hover {{
    background-color: {surface_raised};
    border-color: {border_strong};
}}
QToolButton[role="user_chip"]::menu-indicator {{ image: none; width: 0px; }}

/* حالت ورود و مهمان باید در یک نگاه از هم جدا باشند. کاربر واردشده قاب
   لهجه‌دار و متن پررنگ می‌گیرد؛ مهمان قاب خنثی و کم‌رنگ‌تر می‌ماند. */
QToolButton[role="user_chip"][state="signed_in"] {{
    background-color: {selection};
    border-color: {primary};
    color: {text};
}}
QToolButton[role="user_chip"][state="signed_in"]:hover {{
    background-color: {surface_raised};
    border-color: {primary_hover};
}}
QToolButton[role="user_chip"][state="guest"] {{
    background-color: {surface_alt};
    border: {border_width}px dashed {border_strong};
    color: {text_muted};
}}
QToolButton[role="user_chip"][state="guest"]:hover {{
    background-color: {surface_raised};
    color: {text};
}}

/* ------------------------------------------- ردیف‌های گفتگو (سبک ChatGPT)
   هر پیام یک ردیف تمام‌عرض است: پیام کاربر بی‌پس‌زمینه و پیام دستیار با
   پس‌زمینهٔ ملایم، تا خواندن گفتگوی بلند راحت باشد. */
QFrame[role="chat_user"] {{
    background-color: {selection};
    border: {border_width}px solid {border};
    border-radius: {radius_lg}px;
}}
QFrame[role="chat_user"] QLabel {{ color: {text}; }}
QFrame[role="chat_ai"] {{
    background-color: {surface_raised};
    border: {border_width}px solid {border};
    border-radius: {radius_lg}px;
}}
QFrame[role="chat_ai"] QLabel {{ color: {text}; }}

/* نشان گوینده */
QLabel[role="chat_avatar_user"] {{
    background-color: {primary};
    color: {primary_text};
    border-radius: 15px;
    font-size: 14px;
}}
QLabel[role="chat_avatar_ai"] {{
    background-color: {surface_alt};
    color: {accent};
    border-radius: 15px;
    font-weight: 700;
    font-size: 13px;
}}
QLabel[role="chat_author"] {{
    color: {text_muted};
    font-weight: 700;
    font-size: 12px;
}}
QFrame[role="chat_tool"] {{
    background-color: {surface_alt};
    border: {border_width}px dashed {border_strong};
    border-radius: {radius_md}px;
}}
QFrame[role="chat_tool"] QLabel {{ color: {text_muted}; font-family: monospace; }}

/* گام‌های اجرای ابزار زیر پاسخ دستیار.
   کارت‌های باریک و کم‌رنگ: باید دیده شوند ولی پاسخ را تحت‌الشعاع قرار
   ندهند. حاشیهٔ راست پررنگ، خط زمانی گام‌ها را نشان می‌دهد. */
QFrame[role="toolStep"] {{
    background-color: {surface_alt};
    border: {border_width}px solid {border};
    border-radius: {radius_md}px;
}}
QFrame[role="toolStep"]:hover {{
    border-color: {border_strong};
    background-color: {surface_raised};
}}
QLabel[role="toolStepTitle"] {{
    color: {text_muted};
    font-size: 12px;
}}
QLabel[role="toolStepDetail"] {{
    color: {text_muted};
    font-size: 11px;
    font-family: monospace;
    padding: 4px 2px 2px 2px;
}}
"""


def _arrow_data_uri(direction: str, color: str) -> str:
    """
    ساخت یک فلش کوچک SVG به‌صورت data-URI با رنگ دلخواه.

    چرا data-URI و نه فایل؟ چون رنگ فلش باید با پوسته عوض شود و نگهداری
    چند فایل PNG برای هر پوسته یعنی تکرار. ضمناً در بستهٔ PyInstaller
    مسیر فایل‌های کمکی دردسر می‌سازد ولی data-URI همیشه کار می‌کند.
    """
    points = "M2 7 L6.5 2.5 L11 7" if direction == "up" else "M2 3.5 L6.5 8 L11 3.5"
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="10" '
        f'viewBox="0 0 13 10"><path d="{points}" fill="none" stroke="{color}" '
        'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def build_stylesheet(theme: ThemeTokens, font_family: str | None = None) -> str:
    """
    ساخت QSS کامل برای یک پوسته.

    `font_family` یک زنجیرهٔ آمادهٔ QSS است (مثلاً ``"B Koodak", "Vazirmatn"``).
    جدا از پوسته نگه داشته می‌شود چون انتخاب قلم ترجیح کاربر است و باید
    روی **هر** پوسته‌ای اثر بگذارد، نه اینکه با عوض‌کردن پوسته برگردد.
    """
    values = theme.as_format_map()
    values["font_family"] = (font_family or "").strip() or DEFAULT_FONT_STACK
    # فلش‌های ورودی عددی و فهرست کشویی باید هم‌رنگ متن پوسته باشند. Qt در
    # QSS فقط `image: url(...)` می‌پذیرد و رنگ را عوض نمی‌کند، پس SVG را
    # با رنگ درست می‌سازیم و به‌صورت data-URI جاسازی می‌کنیم — بدون فایل
    # روی دیسک و بدون وابستگی به مسیر نصب.
    values["arrow_up_icon"] = _arrow_data_uri("up", theme.colors.text_muted)
    values["arrow_down_icon"] = _arrow_data_uri("down", theme.colors.text_muted)
    return STYLESHEET_TEMPLATE.format(**values)
