"""Bot uchun flood himoyasi.

Telegram tomonidan kelgan har bir xabar bazaga so'rov qiladi. Kimdir
skript bilan sekundiga o'nlab xabar yuborsa, Railway'ning bitta vCPU si
band bo'lib, oddiy foydalanuvchilar javob ololmay qoladi.

Chegaradan oshgan xabarlar jim tashlab yuboriladi — spamchiga javob
qaytarish uni faqat rag'batlantiradi (va yana bir Telegram so'rovi).
"""
import time
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

logger = logging.getLogger(__name__)


class ThrottleMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 15, window: float = 10.0, warn_after: int = 20):
        self.limit = limit          # `window` soniyada ruxsat etilgan xabarlar
        self.window = window
        self.warn_after = warn_after
        self._hits: dict[int, list[float]] = {}
        self._warned: dict[int, float] = {}

    def _allow(self, user_id: int) -> tuple[bool, int]:
        now = time.monotonic()
        bucket = [t for t in self._hits.get(user_id, []) if now - t < self.window]
        bucket.append(now)
        self._hits[user_id] = bucket

        # Xotira tozalash
        if len(self._hits) > 5000:
            for uid in [u for u, ts in self._hits.items() if not ts or now - ts[-1] > 300][:2500]:
                self._hits.pop(uid, None)
                self._warned.pop(uid, None)

        return len(bucket) <= self.limit, len(bucket)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[Any]],
        event: TelegramObject,
        data: dict,
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id
        allowed, count = self._allow(user_id)
        if allowed:
            return await handler(event, data)

        # Bir marta ogohlantiramiz, keyin jim tashlaymiz
        now = time.monotonic()
        if count >= self.warn_after and now - self._warned.get(user_id, 0) > 60:
            self._warned[user_id] = now
            logger.warning("Bot flood: telegram_id=%s (%s ta / %ss)", user_id, count, self.window)
            try:
                if isinstance(event, CallbackQuery):
                    await event.answer("Juda tez! Biroz kuting.", show_alert=False)
                else:
                    await event.answer("⏳ Juda tez yubormoqdasiz. Biroz kuting.")
            except Exception:      # noqa: BLE001
                pass
        return None
