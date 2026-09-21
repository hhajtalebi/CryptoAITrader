"""
استخراج تدریجی متن پاسخ از جریانِ ناقص مدل.

چرا وجود دارد؟
    عامل گفتگو از مدل می‌خواهد پاسخ را در قالب JSON بدهد:

        {"answer": "سلام ...", "action": {...}}

    ولی در حالت جریانی، متن تکه‌تکه می‌رسد و تا لحظهٔ آخر JSON ناقص است.
    اگر تکه‌های خام را مستقیم روی صفحه بگذاریم، کاربر به‌جای پاسخ، چیزی
    مثل `{"answer": "سلا` می‌بیند. این کلاس همان مقدار `answer` را در حال
    شکل‌گیری بیرون می‌کشد و فقط متن تازه را برمی‌گرداند.

    اگر مدل اصلاً JSON ندهد (که مجاز است و عامل هم می‌پذیرد)، همان متن
    خام پخش می‌شود.

طراحی:
    کلاس حالت‌دار است و با هر `feed()` فقط **دلتا** را برمی‌گرداند تا
    مصرف‌کننده بتواند سرراست به انتهای حباب اضافه کند.
"""

from __future__ import annotations

#: کلیدهایی که مقدارشان «پاسخ کاربر» است، به ترتیب اولویت.
ANSWER_KEYS = ("answer", "text")


class StreamingAnswerExtractor:
    """
    تبدیل جریان خام مدل به متن قابل نمایش.

    نمونهٔ کاربرد:

        extractor = StreamingAnswerExtractor()
        delta = extractor.feed(chunk)   # فقط متن تازه
        final = extractor.finish()      # متن کامل و پاک‌شده
    """

    def __init__(self) -> None:
        self._raw: list[str] = []
        self._emitted = ""

    # ------------------------------------------------------------------
    # ورودی
    # ------------------------------------------------------------------
    def feed(self, chunk: str) -> str:
        """
        افزودن یک تکه و گرفتن متن تازه‌ای که باید نمایش داده شود.

        رشتهٔ خالی یعنی «چیز تازه‌ای برای نشان‌دادن نیست» — مثلاً وقتی
        تکه فقط بخشی از ساختار JSON بوده است.
        """
        if not chunk:
            return ""
        self._raw.append(chunk)

        visible = self._visible_text()
        if not visible.startswith(self._emitted):
            # متن بازنویسی شده (مثلاً گریزها باز شدند). کل رشته را
            # دوباره می‌دهیم و مصرف‌کننده جایگزین می‌کند.
            self._emitted = visible
            return visible

        delta = visible[len(self._emitted) :]
        self._emitted = visible
        return delta

    def reset(self) -> None:
        """
        دور ریختن همه‌چیز.

        وقتی زنجیرهٔ جایگزینی سراغ سرویس بعدی می‌رود لازم است، وگرنه
        پاسخ دو مدل به هم می‌چسبد.
        """
        self._raw.clear()
        self._emitted = ""

    # ------------------------------------------------------------------
    # خروجی
    # ------------------------------------------------------------------
    @property
    def raw(self) -> str:
        """متن خامی که تا این لحظه رسیده است."""
        return "".join(self._raw)

    @property
    def visible(self) -> str:
        """متنی که تا این لحظه نمایش داده شده است."""
        return self._emitted

    def finish(self) -> str:
        """متن نهاییِ قابل نمایش."""
        return self._visible_text()

    # ------------------------------------------------------------------
    # درون‌سازی
    # ------------------------------------------------------------------
    def _visible_text(self) -> str:
        """
        متن قابل نمایش از روی خامِ فعلی.

        سه حالت:
        ۱. هنوز معلوم نیست JSON است یا نه → چیزی نشان نده (تا `{` اول).
        ۲. JSON است → مقدار در حال شکل‌گیریِ `answer` را بیرون بکش.
        ۳. JSON نیست → همان متن خام.
        """
        raw = self.raw
        stripped = raw.lstrip()
        if not stripped:
            return ""

        fenced = self._after_fence(stripped)
        if fenced is not None:
            stripped = fenced

        if not stripped.lstrip().startswith("{"):
            # متن ساده؛ همان را نشان بده
            return stripped

        return self._extract_answer(stripped.lstrip())

    @staticmethod
    def _after_fence(text: str) -> str | None:
        """
        عبور از حصار ```json در ابتدای پاسخ.

        بازگشتی `None` یعنی حصاری نبود. اگر حصار باشد ولی هنوز خط اولش
        کامل نشده، رشتهٔ خالی برمی‌گردد تا چیزی نشان داده نشود.
        """
        if not text.startswith("```"):
            return None
        newline = text.find("\n")
        if newline == -1:
            return ""
        return text[newline + 1 :]

    @classmethod
    def _extract_answer(cls, text: str) -> str:
        """
        بیرون کشیدن مقدار `answer` از یک JSON احتمالاً ناقص.

        دستی نوشته شده چون `json.loads` روی رشتهٔ ناقص شکست می‌خورد و ما
        دقیقاً می‌خواهیم متنِ نیمه‌کاره را ببینیم.
        """
        for key in ANSWER_KEYS:
            start = cls._value_start(text, key)
            if start is None:
                continue
            return cls._read_string(text, start)
        return ""

    @staticmethod
    def _value_start(text: str, key: str) -> int | None:
        """
        یافتن جایگاه شروع مقدار رشته‌ای یک کلید.

        بازگشتی، اندیس نخستین نویسهٔ **داخل** گیومهٔ مقدار است.
        """
        needle = f'"{key}"'
        index = text.find(needle)
        if index == -1:
            return None
        cursor = index + len(needle)
        # عبور از فاصله‌ها و دونقطه
        while cursor < len(text) and text[cursor] in " \t\r\n":
            cursor += 1
        if cursor >= len(text) or text[cursor] != ":":
            return None
        cursor += 1
        while cursor < len(text) and text[cursor] in " \t\r\n":
            cursor += 1
        if cursor >= len(text) or text[cursor] != '"':
            return None
        return cursor + 1

    @staticmethod
    def _read_string(text: str, start: int) -> str:
        """
        خواندن یک رشتهٔ JSON از `start` تا گیومهٔ پایانی یا انتهای متن.

        گریزهای استاندارد باز می‌شوند تا `\\n` واقعاً خط جدید شود و
        کاربر `\\u06cc` نبیند. گریزِ ناقص در انتهای جریان (مثل `\\u06`)
        نادیده گرفته می‌شود تا در تکهٔ بعدی کامل شود.
        """
        out: list[str] = []
        index = start
        length = len(text)
        simple = {
            '"': '"',
            "\\": "\\",
            "/": "/",
            "n": "\n",
            "t": "\t",
            "r": "\r",
            "b": "\b",
            "f": "\f",
        }
        while index < length:
            char = text[index]
            if char == '"':
                break
            if char != "\\":
                out.append(char)
                index += 1
                continue

            # --- گریز ---
            if index + 1 >= length:
                break  # ناقص؛ منتظر تکهٔ بعدی
            nxt = text[index + 1]
            if nxt in simple:
                out.append(simple[nxt])
                index += 2
                continue
            if nxt == "u":
                if index + 6 > length:
                    break  # \uXXXX هنوز کامل نشده
                code = text[index + 2 : index + 6]
                try:
                    out.append(chr(int(code, 16)))
                except ValueError:
                    out.append(code)
                index += 6
                continue
            # گریز ناشناخته: همان‌طور رد شو
            out.append(nxt)
            index += 2
        return "".join(out)
