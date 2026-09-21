"""
مخزن گفت‌وگوهای هوش مصنوعی.

کاربر خواست چت‌ها مانند ChatGPT ذخیره شوند: فهرست گفت‌وگوها بر اساس زمان،
بازگشت به هر گفت‌وگو و امکان حذف.

نکتهٔ مهم دربارهٔ خروج داده از session: تمام متدها داده را به‌صورت
dictionary برمی‌گردانند، نه شیء ORM. اگر شیء ORM از session خارج شود،
دسترسی به فیلدهایش خطای DetachedInstanceError می‌دهد. dictionary این
مشکل را ندارد و لایهٔ رابط کاربری بی‌دردسر از آن استفاده می‌کند.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from app.database.models import ChatConversationRecord, ChatMessageRecord
from app.database.repositories.base import BaseRepository
from app.logging import get_logger

logger = get_logger(__name__)

#: بیشترین طولی که از پیام کاربر برای ساختن عنوان گفت‌وگو برمی‌داریم
TITLE_MAX_LENGTH = 60


class ChatRepository(BaseRepository[ChatConversationRecord]):
    """ذخیره و بازیابی گفت‌وگوهای چت."""

    model = ChatConversationRecord

    # ------------------------------------------------------------------
    # گفت‌وگو
    # ------------------------------------------------------------------
    def create_conversation(
        self,
        *,
        title: str = "",
        symbol: str = "",
        timeframe: str = "",
    ) -> int:
        """ساخت گفت‌وگوی تازه و بازگرداندن شناسهٔ آن."""
        with self._db.session_scope() as session:
            record = ChatConversationRecord(
                title=(title or "").strip()[:TITLE_MAX_LENGTH],
                symbol=symbol or "",
                timeframe=timeframe or "",
            )
            session.add(record)
            session.flush()
            return int(record.id)

    def list_conversations(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        فهرست گفت‌وگوها، تازه‌ترین در ابتدا.

        گفت‌وگوهای سنجاق‌شده همیشه بالای فهرست می‌آیند.
        """
        with self._db.session_scope() as session:
            statement = (
                select(ChatConversationRecord)
                .order_by(
                    ChatConversationRecord.pinned.desc(),
                    ChatConversationRecord.updated_at.desc(),
                    ChatConversationRecord.id.desc(),
                )
                .limit(max(1, int(limit)))
            )
            rows = session.execute(statement).scalars().all()
            return [self._conversation_to_dict(row) for row in rows]

    def get_conversation(self, conversation_id: int) -> dict[str, Any] | None:
        """یک گفت‌وگو به همراه همهٔ پیام‌هایش."""
        with self._db.session_scope() as session:
            record = session.get(
                ChatConversationRecord,
                int(conversation_id),
                options=[selectinload(ChatConversationRecord.messages)],
            )
            if record is None:
                return None
            data = self._conversation_to_dict(record)
            data["messages"] = [self._message_to_dict(m) for m in record.messages]
            return data

    def rename_conversation(self, conversation_id: int, title: str) -> bool:
        """تغییر عنوان گفت‌وگو."""
        with self._db.session_scope() as session:
            record = session.get(ChatConversationRecord, int(conversation_id))
            if record is None:
                return False
            record.title = (title or "").strip()[:TITLE_MAX_LENGTH]
            return True

    def set_pinned(self, conversation_id: int, pinned: bool) -> bool:
        """سنجاق کردن یا برداشتن سنجاق گفت‌وگو."""
        with self._db.session_scope() as session:
            record = session.get(ChatConversationRecord, int(conversation_id))
            if record is None:
                return False
            record.pinned = bool(pinned)
            return True

    def delete_conversation(self, conversation_id: int) -> bool:
        """حذف یک گفت‌وگو به همراه تمام پیام‌هایش."""
        with self._db.session_scope() as session:
            record = session.get(ChatConversationRecord, int(conversation_id))
            if record is None:
                return False
            session.delete(record)
            return True

    def clear_all(self) -> int:
        """حذف همهٔ گفت‌وگوها. تعداد حذف‌شده برگردانده می‌شود."""
        with self._db.session_scope() as session:
            count = int(session.execute(select(func.count(ChatConversationRecord.id))).scalar() or 0)
            session.execute(delete(ChatMessageRecord))
            session.execute(delete(ChatConversationRecord))
            return count

    # ------------------------------------------------------------------
    # پیام
    # ------------------------------------------------------------------
    def add_message(
        self,
        conversation_id: int,
        *,
        role: str,
        content: str,
        tools: list[str] | None = None,
        provider: str = "",
        model: str = "",
    ) -> int:
        """
        افزودن پیام به گفت‌وگو.

        اگر گفت‌وگو هنوز عنوان ندارد و این نخستین پیام کاربر است، عنوان
        به‌صورت خودکار از متن همان پیام ساخته می‌شود.
        """
        with self._db.session_scope() as session:
            conversation = session.get(ChatConversationRecord, int(conversation_id))
            if conversation is None:
                raise ValueError(f"Conversation {conversation_id} does not exist")

            message = ChatMessageRecord(
                conversation_id=int(conversation_id),
                role=str(role or "user"),
                content=str(content or ""),
                tools=list(tools or []),
                provider=provider or "",
                model=model or "",
            )
            session.add(message)

            conversation.message_count = int(conversation.message_count or 0) + 1
            if not conversation.title and role == "user":
                conversation.title = self.make_title(content)
            # به‌روزرسانی زمان تا گفت‌وگو در فهرست بالا بیاید
            conversation.updated_at = datetime.utcnow()

            session.flush()
            return int(message.id)

    def messages(self, conversation_id: int) -> list[dict[str, Any]]:
        """همهٔ پیام‌های یک گفت‌وگو به ترتیب زمان."""
        with self._db.session_scope() as session:
            statement = (
                select(ChatMessageRecord)
                .where(ChatMessageRecord.conversation_id == int(conversation_id))
                .order_by(ChatMessageRecord.id)
            )
            rows = session.execute(statement).scalars().all()
            return [self._message_to_dict(row) for row in rows]

    def search(self, term: str, limit: int = 50) -> list[dict[str, Any]]:
        """جست‌وجو در متن پیام‌ها و بازگرداندن گفت‌وگوهای مرتبط."""
        needle = (term or "").strip()
        if not needle:
            return self.list_conversations(limit)
        with self._db.session_scope() as session:
            statement = (
                select(ChatConversationRecord)
                .join(ChatMessageRecord)
                .where(ChatMessageRecord.content.contains(needle))
                .order_by(ChatConversationRecord.updated_at.desc())
                .distinct()
                .limit(max(1, int(limit)))
            )
            rows = session.execute(statement).scalars().all()
            return [self._conversation_to_dict(row) for row in rows]

    # ------------------------------------------------------------------
    # کمکی
    # ------------------------------------------------------------------
    @staticmethod
    def make_title(text: str) -> str:
        """ساخت عنوان کوتاه و خوانا از نخستین پیام کاربر."""
        cleaned = " ".join(str(text or "").split())
        if not cleaned:
            return ""
        if len(cleaned) <= TITLE_MAX_LENGTH:
            return cleaned
        return cleaned[: TITLE_MAX_LENGTH - 1].rstrip() + "…"

    @staticmethod
    def _conversation_to_dict(record: ChatConversationRecord) -> dict[str, Any]:
        """تبدیل رکورد گفت‌وگو به dictionary مستقل از session."""
        return {
            "id": int(record.id),
            "title": record.title or "",
            "symbol": record.symbol or "",
            "timeframe": record.timeframe or "",
            "message_count": int(record.message_count or 0),
            "pinned": bool(record.pinned),
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    @staticmethod
    def _message_to_dict(record: ChatMessageRecord) -> dict[str, Any]:
        """تبدیل رکورد پیام به dictionary مستقل از session."""
        return {
            "id": int(record.id),
            "conversation_id": int(record.conversation_id),
            "role": record.role or "user",
            "content": record.content or "",
            "tools": list(record.tools or []),
            "provider": record.provider or "",
            "model": record.model or "",
            "created_at": record.created_at,
        }
