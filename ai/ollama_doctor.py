"""
تشخیص پله‌به‌پلهٔ مشکل اولاما — منطق خالص، بدون Qt و بدون چاپ.

چرا این ماژول وجود دارد؟
    سه نسخه پشت سر هم علت «در ترمینال کار می‌کند، در برنامه نه» را از
    روی شواهد غیرمستقیم حدس زدم و هر بار بخشی را اشتباه فهمیدم. علت
    ریشه‌ای یک چیز بود: **من دستگاه کاربر را نمی‌بینم.**

    راه‌حل، حدس بهتر نیست؛ اندازه‌گیری است. این ماژول همان درخواستی را
    که برنامه می‌فرستد پله‌پله سنگین‌تر می‌کند و اولین پله‌ای که
    می‌شکند را گزارش می‌دهد. آن پله، علت را لو می‌دهد:

        شکست در پلهٔ ۱  ⇒ مشکل از خود اولاما/درایور است، نه برنامه
        شکست در پله‌های بعد ⇒ مدل زیر بار واقعی دوام نمی‌آورد

`tools/ollama_doctor.py` پوستهٔ خط‌فرمان همین منطق است.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

#: پیام سیستمی ساختگی هم‌اندازهٔ پیام واقعی برنامه (≈۱۲۰۰ توکن).
_SYSTEM_SAMPLE = "You are a trading assistant. " * 125

#: مهلت هر پله؛ بارگذاری اولیهٔ مدل روی CPU می‌تواند بسیار طول بکشد.
STEP_TIMEOUT = 300.0


@dataclass
class StepResult:
    """نتیجهٔ یک پله."""

    key: str
    prompt_chars: int
    ok: bool = False
    status: int = 0
    detail: str = ""
    seconds: float = 0.0


@dataclass
class DoctorReport:
    """گزارش کامل تشخیص."""

    reachable: bool = False
    models: list[str] = field(default_factory=list)
    loaded: list[dict[str, Any]] = field(default_factory=list)
    steps: list[StepResult] = field(default_factory=list)
    target_model: str = ""

    @property
    def first_failure(self) -> StepResult | None:
        """نخستین پله‌ای که شکست — همان که علت را نشان می‌دهد."""
        for step in self.steps:
            if not step.ok:
                return step
        return None

    @property
    def verdict_key(self) -> str:
        """کلید ترجمهٔ نتیجه‌گیری."""
        if not self.reachable:
            return "settings.doctor.verdict_offline"
        if not self.models:
            return "settings.doctor.verdict_no_models"
        failure = self.first_failure
        if failure is None:
            return "settings.doctor.verdict_healthy"
        if failure.key == "tiny":
            return "settings.doctor.verdict_broken_service"
        return "settings.doctor.verdict_load_limit"

    @property
    def cpu_offload_detected(self) -> bool:
        """
        آیا مدلی که در حافظه است، بخشی روی CPU اجرا می‌شود؟

        روی کارت‌های کم‌حافظه این حالت عادی است ولی هم کند است و هم
        اجراکننده را شکننده می‌کند — و دقیقاً همان چیزی است که کاربر
        در `ollama ps` باید ببیند.
        """
        for item in self.loaded:
            size = float(item.get("size") or 0)
            vram = float(item.get("size_vram") or 0)
            if size > 0 and vram < size * 0.99:
                return True
        return False


def _steps(model: str) -> list[tuple[str, list[dict[str, str]], dict[str, Any]]]:
    """پله‌ها از سبک به سنگین؛ هر کدام شکل واقعی درخواست برنامه."""
    return [
        ("tiny", [{"role": "user", "content": "سلام"}], {}),
        ("tiny_predict", [{"role": "user", "content": "سلام"}], {"num_predict": 1600}),
        (
            "system",
            [
                {"role": "system", "content": _SYSTEM_SAMPLE},
                {"role": "user", "content": "تحلیل BTC/USDT"},
            ],
            {"num_predict": 1600},
        ),
        (
            "full",
            [
                {"role": "system", "content": _SYSTEM_SAMPLE},
                {"role": "user", "content": "تحلیل BTC/USDT"},
                {"role": "assistant", "content": "بررسی می‌کنم."},
                {"role": "user", "content": "Tool results:\n" + "قیمت ۷۶۰۰۰ دلار. " * 400},
            ],
            {"num_predict": 1600},
        ),
    ]


async def run_diagnosis(base_url: str, model: str = "") -> DoctorReport:
    """
    اجرای کامل تشخیص روی دستگاه کاربر.

    هیچ استثنایی بیرون نمی‌دهد: خودِ شکست، داده‌ای است که می‌خواهیم.
    """
    report = DoctorReport()
    url = (base_url or "http://127.0.0.1:11434").rstrip("/")

    async with httpx.AsyncClient(base_url=url, timeout=STEP_TIMEOUT) as client:
        # ---- سرویس بالاست؟ ----
        try:
            response = await client.get("/", timeout=10.0)
            report.reachable = response.status_code == 200
        except httpx.HTTPError:
            return report

        # ---- چه مدل‌هایی نصب است؟ ----
        try:
            response = await client.get("/api/tags", timeout=30.0)
            if response.status_code == 200:
                report.models = [
                    str(item.get("name"))
                    for item in (response.json().get("models") or [])
                    if item.get("name")
                ]
        except (httpx.HTTPError, ValueError):
            pass

        if not report.models:
            return report

        # ---- چه چیزی در حافظه است و کجا اجرا می‌شود؟ ----
        try:
            response = await client.get("/api/ps", timeout=30.0)
            if response.status_code == 200:
                report.loaded = list(response.json().get("models") or [])
        except (httpx.HTTPError, ValueError):
            pass

        # ---- انتخاب مدل هدف: سبک‌ترین گزینهٔ موجود ----
        target = model if model in report.models else ""
        if not target:
            for preferred in ("gemma4:e4b-it-qat", "llama3.1:8b", "deepseek-coder:6.7b"):
                if preferred in report.models:
                    target = preferred
                    break
        report.target_model = target or report.models[0]

        # ---- پله‌ها ----
        for key, messages, options in _steps(report.target_model):
            chars = sum(len(m["content"]) for m in messages)
            step = StepResult(key=key, prompt_chars=chars)
            payload = {
                "model": report.target_model,
                "messages": messages,
                "stream": False,
                "keep_alive": "30m",
                "options": {"temperature": 0.2, **options},
            }
            try:
                response = await client.post("/api/chat", json=payload)
                step.status = response.status_code
                step.seconds = response.elapsed.total_seconds()
                step.ok = response.status_code == 200
                if not step.ok:
                    step.detail = _error_text(response)
            except httpx.HTTPError as exc:
                step.detail = f"{exc.__class__.__name__}: {exc}"
            report.steps.append(step)
            if not step.ok:
                break  # ادامه بی‌فایده است؛ پله‌های بعد سنگین‌ترند

    return report


def _error_text(response: Any) -> str:
    """متن خطای اولاما از بدنهٔ پاسخ."""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            message = payload.get("error") or payload.get("message")
            if message:
                return str(message)[:300]
    except (ValueError, AttributeError):
        pass
    return str(getattr(response, "text", ""))[:300]
