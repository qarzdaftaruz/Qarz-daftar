import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from app.models import User

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Har bir so'rovda foydalanuvchi holatini tekshiradi.

    Bloklangan foydalanuvchi hech qanday amal bajara olmaydi (/start ham).
    Ilgari do'konlar ro'yxati ham yuklanardi — endi barcha amallar
    Mini App'da bo'lgani uchun bu keraksiz so'rovlar olib tashlandi.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[Any]],
        event: TelegramObject,
        data: dict,
    ) -> Any:
        inner = event
        if isinstance(inner, (Message, CallbackQuery)):
            tg_user = inner.from_user
        else:
            return await handler(event, data)

        if not tg_user:
            return await handler(event, data)

        user = await User.find_one(User.telegram_id == tg_user.id)
        data["user"] = user

        if user and user.is_blocked:
            if isinstance(inner, Message):
                await inner.answer(
                    "🚫 Sizning akkauntingiz bloklangan.\n"
                    "Murojaat uchun admin bilan bog'laning."
                )
            else:
                await inner.answer("Akkauntingiz bloklangan!", show_alert=True)
            return

        return await handler(event, data)
