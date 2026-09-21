"""
مدیریت قالب‌های Prompt نسخه‌بندی‌شده.

چرا وجود دارد؟
    کیفیت تحلیل هوش مصنوعی به شدت به Prompt وابسته است. با جدا کردن Prompt
    از کد:
        • می‌توان چند نسخه داشت و آن‌ها را مقایسه کرد
        • کاربر می‌تواند Prompt را از تنظیمات تغییر دهد
        • تغییر Prompt نیازی به ساخت مجدد فایل اجرایی ندارد

ساختار فایل‌ها:
    ai/prompts/templates/<name>_v<version>.txt
    خط‌های ابتدایی که با «#» شروع شوند، توضیح در نظر گرفته و حذف می‌شوند.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Any

from app.exceptions import ConfigurationError
from app.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class PromptTemplate:
    """یک قالب Prompt به‌همراه فراداده آن."""

    name: str
    version: int
    content: str
    description: str = ""

    @property
    def identifier(self) -> str:
        """شناسه کامل مانند technical_analysis_v1"""
        return f"{self.name}_v{self.version}"

    def render(self, **variables: Any) -> str:
        """
        جای‌گذاری متغیرها در قالب.

        از Template استاندارد پایتون با نحو $variable استفاده می‌شود که
        برخلاف format، با آکولادهای موجود در نمونه JSON تداخل ندارد.
        """
        try:
            return Template(self.content).safe_substitute(**variables)
        except Exception as exc:  # noqa: BLE001
            raise ConfigurationError(
                f"Failed to render prompt '{self.identifier}'", details={"prompt": self.identifier}
            ) from exc


class PromptManager:
    """
    بارگذاری و نگهداری قالب‌های Prompt.

    قالب‌ها یک بار خوانده و در حافظه نگه داشته می‌شوند؛ با reload می‌توان
    پس از ویرایش فایل، آن‌ها را دوباره خواند.
    """

    _FILENAME_PATTERN = re.compile(r"^(?P<name>.+)_v(?P<version>\d+)\.txt$")

    def __init__(self, templates_dir: Path | None = None) -> None:
        self._templates_dir = templates_dir or (Path(__file__).parent / "templates")
        self._templates: dict[str, PromptTemplate] = {}
        self.reload()

    def reload(self) -> int:
        """
        بارگذاری مجدد تمام قالب‌ها از دیسک.

        بازگشتی: تعداد قالب‌های بارگذاری‌شده.
        """
        self._templates.clear()
        if not self._templates_dir.exists():
            logger.warning("Prompt templates directory not found: %s", self._templates_dir)
            return 0

        for path in sorted(self._templates_dir.glob("*.txt")):
            match = self._FILENAME_PATTERN.match(path.name)
            if match is None:
                logger.warning("Ignoring prompt file with invalid name: %s", path.name)
                continue
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.error("Could not read prompt file %s: %s", path.name, exc.__class__.__name__)
                continue

            description_lines = [
                line[1:].strip() for line in raw.splitlines() if line.startswith("#")
            ]
            content = "\n".join(line for line in raw.splitlines() if not line.startswith("#")).strip()

            template = PromptTemplate(
                name=match.group("name"),
                version=int(match.group("version")),
                content=content,
                description=" ".join(description_lines),
            )
            self._templates[template.identifier] = template

        logger.info("Loaded %d prompt templates", len(self._templates))
        return len(self._templates)

    def get(self, identifier: str) -> PromptTemplate:
        """
        دریافت یک قالب بر اساس شناسه کامل یا نام (آخرین نسخه).
        """
        template = self._templates.get(identifier)
        if template is not None:
            return template

        # اگر فقط نام داده شده باشد، جدیدترین نسخه انتخاب می‌شود
        candidates = [t for t in self._templates.values() if t.name == identifier]
        if candidates:
            return max(candidates, key=lambda t: t.version)

        raise ConfigurationError(
            f"Prompt template not found: {identifier}",
            details={"available": sorted(self._templates)},
        )

    def render(self, identifier: str, **variables: Any) -> str:
        """میان‌بر دریافت و جای‌گذاری یکجای یک قالب."""
        return self.get(identifier).render(**variables)

    def available(self) -> list[str]:
        """فهرست شناسه تمام قالب‌های موجود."""
        return sorted(self._templates)

    def latest_versions(self) -> dict[str, int]:
        """آخرین نسخه هر قالب (برای نمایش در تنظیمات)."""
        versions: dict[str, int] = {}
        for template in self._templates.values():
            versions[template.name] = max(versions.get(template.name, 0), template.version)
        return versions
