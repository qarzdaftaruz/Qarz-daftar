import re
import time
import logging
from typing import Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from app.config import settings
from app.core import cache
from app.utils.helpers import esc, normalize_phone

logger = logging.getLogger(__name__)

bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# Parol o'zgartirish sessiyalari: {telegram_id: (username, expires_at)}
# Muddat cheklangan — ochiq qolgan sessiya orqali parol o'zgartirib bo'lmaydi.
_pwd_sessions: dict[int, tuple[Optional[str], float]] = {}
PWD_SESSION_TTL = 300      # 5 daqiqa

_OBJECT_ID = re.compile(r"^[0-9a-fA-F]{24}$")


async def _is_bot_admin(tid: int) -> bool:
    from app.models import AdminAuth
    if tid in settings.super_admin_ids:
        return True
    admin = await AdminAuth.find_one(AdminAuth.telegram_id == tid)
    return admin is not None


class ContactState(StatesGroup):
    waiting = State()


# ─── Asosiy menyu ─────────────────────────────────────────────────────────────

async def show_main_menu(message: Message, user):
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🧾 Ilovani ochish", web_app=WebAppInfo(url=settings.MINI_APP_URL)),
    ]])
    await message.answer(
        f"👋 Xush kelibsiz, <b>{esc(user.full_name)}</b>!",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        "Boshqaruv paneliga kirish uchun tugmani bosing 👇",
        reply_markup=inline_kb,
    )


# ─── /start ───────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    from app.models import User

    tid = message.from_user.id
    if await _is_bot_admin(tid):
        await message.answer("👋 <b>Qarz Daftar</b> — admin", reply_markup=ReplyKeyboardRemove())
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🛠 Admin panel", url=f"{settings.MINI_APP_URL.rstrip('/')}/admin"),
        ]])
        await message.answer("Admin sifatida kirgansiz. Boshqaruv uchun tugmani bosing 👇", reply_markup=kb)
        return

    user = await User.find_one(User.telegram_id == tid)
    if not user or not user.phone:
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📞 Raqamni ulashish", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await message.answer(
            "👋 <b>Qarz Daftar</b>ga xush kelibsiz!\n\n"
            "Davom etish uchun telefon raqamingizni ulashing 👇",
            reply_markup=kb,
        )
        return

    await show_main_menu(message, user)


# ─── Kontakt ulashilganda ─────────────────────────────────────────────────────

@router.message(F.contact)
async def handle_contact(message: Message):
    from app.models import User, utcnow

    tid = message.from_user.id

    # XAVFSIZLIK: faqat foydalanuvchining O'Z kontakti qabul qilinadi.
    # Aks holda boshqa odamning raqamini yuborib, uning qarzlarini ko'rish mumkin edi.
    if message.contact.user_id != tid:
        await message.answer(
            "❌ Faqat o'z raqamingizni ulashing.\n"
            "Pastdagi «📞 Raqamni ulashish» tugmasidan foydalaning."
        )
        return

    phone = normalize_phone(message.contact.phone_number)
    full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip() or "Noma'lum"

    user = await User.find_one(User.telegram_id == tid)
    if not user:
        user = await User(telegram_id=tid, full_name=full_name, phone=phone).insert()
    else:
        user.phone = phone
        user.full_name = full_name
        user.updated_at = utcnow()
        await user.save()

    await message.answer("✅ Raqam qabul qilindi!", reply_markup=ReplyKeyboardRemove())
    await show_main_menu(message, user)


# ─── /contact (do'kondor → admin) ─────────────────────────────────────────────

@router.message(Command("contact"))
async def cmd_contact(message: Message, state: FSMContext):
    from app.models import User, Shop, ShopStatus

    user = await User.find_one(User.telegram_id == message.from_user.id)
    if not user:
        await message.answer("Avval /start bosib ro'yxatdan o'ting.")
        return

    shops = await Shop.find(Shop.owner_id == user.id, Shop.status == ShopStatus.ACTIVE).to_list()
    if not shops:
        await message.answer("Faqat faol do'kon egalari xabar yuborishi mumkin.")
        return

    await state.set_state(ContactState.waiting)
    await state.update_data(shop_id=str(shops[0].id), shop_name=shops[0].name)
    await message.answer("✉️ Adminga yuboriladigan xabaringizni yozing:")


@router.message(ContactState.waiting)
async def process_contact(message: Message, state: FSMContext):
    from app.models import User, SupportMessage
    from beanie import PydanticObjectId

    data = await state.get_data()
    await state.clear()

    text = (message.text or "").strip()
    if not text:
        await message.answer("❌ Faqat matnli xabar yuboring.")
        return
    text = text[:1000]

    user = await User.find_one(User.telegram_id == message.from_user.id)

    support = await SupportMessage(
        shop_id=PydanticObjectId(data["shop_id"]),
        user_telegram_id=message.from_user.id,
        user_full_name=user.full_name if user else "?",
        shop_name=data["shop_name"],
        user_phone=user.phone if user else "",
        message=text,
    ).insert()

    admin_tid = await cache.admin_telegram_id()
    if admin_tid:
        try:
            sent = await bot.send_message(
                admin_tid,
                f"📩 <b>Yangi xabar</b>\n\n"
                f"👤 {esc(support.user_full_name)}\n"
                f"🏪 {esc(support.shop_name)}\n"
                f"📞 {esc(support.user_phone) or '—'}\n\n"
                f"💬 {esc(support.message)}\n\n"
                f"<i>Reply qiling — do'kondorga ketadi</i>",
            )
            support.admin_message_id = sent.message_id
            await support.save()
        except Exception as e:      # noqa: BLE001
            logger.warning("Adminga xabar yuborilmadi: %s", e)

    await message.answer("✅ Xabaringiz adminga yuborildi!")


# ─── Admin reply → do'kondorga ────────────────────────────────────────────────

@router.message(F.reply_to_message)
async def handle_reply(message: Message):
    from app.models import SupportMessage

    if not await _is_bot_admin(message.from_user.id):
        return
    if not message.text:
        return

    support = await SupportMessage.find_one(
        SupportMessage.admin_message_id == message.reply_to_message.message_id
    )
    if not support:
        await message.answer("⚠️ Bu xabar topilmadi.")
        return

    try:
        await bot.send_message(
            support.user_telegram_id,
            f"📨 <b>Admin javobi:</b>\n\n{esc(message.text[:1000])}",
        )
        support.is_read = True
        await support.save()
        await message.answer("✅ Javob yuborildi!")
    except Exception as e:      # noqa: BLE001
        logger.warning("Javob yuborilmadi: %s", e)
        await message.answer("❌ Javob yuborilmadi (foydalanuvchi botni bloklagan bo'lishi mumkin).")


# ─── Parol o'zgartirish (web → bot) ───────────────────────────────────────────

async def request_password_change(admin_telegram_id: int, username: Optional[str] = None):
    """Web'dan parol tiklash so'rovi."""
    _pwd_sessions[admin_telegram_id] = (username, time.monotonic() + PWD_SESSION_TTL)
    label = f" (<b>{esc(username)}</b>)" if username else ""
    await bot.send_message(
        admin_telegram_id,
        f"🔐 <b>Yangi parolni kiriting{label}:</b>\n\n"
        f"<i>Xabar avtomatik o'chiriladi. So'rov {PWD_SESSION_TTL // 60} daqiqa amal qiladi.</i>",
    )


def _password_problem(pwd: str) -> Optional[str]:
    if len(pwd) < settings.MIN_PASSWORD_LENGTH:
        return f"Parol kamida {settings.MIN_PASSWORD_LENGTH} ta belgi bo'lishi kerak."
    if not re.search(r"[A-Za-z]", pwd) or not re.search(r"\d", pwd):
        return "Parolda kamida bitta harf va bitta raqam bo'lishi kerak."
    return None


@router.message(F.text)
async def handle_text(message: Message):
    tid = message.from_user.id
    session = _pwd_sessions.get(tid)
    if not session or message.reply_to_message:
        return

    username, expires_at = session
    if time.monotonic() > expires_at:
        _pwd_sessions.pop(tid, None)
        await message.answer("⏱ So'rov muddati tugadi. Qaytadan urinib ko'ring.")
        return

    new_password = (message.text or "").strip()
    problem = _password_problem(new_password)

    # Parol matnini darhol o'chiramiz (xato bo'lsa ham chatda qolmasin)
    try:
        await message.delete()
    except Exception:      # noqa: BLE001
        pass

    if problem:
        await message.answer(f"❌ {problem}")
        return

    _pwd_sessions.pop(tid, None)

    from app.models import AdminAuth, utcnow
    from app.core.security import get_password_hash

    if username:
        admin = await AdminAuth.find_one(AdminAuth.username == username)
    else:
        admin = await AdminAuth.find_one(AdminAuth.telegram_id == tid)

    # Hisob shu Telegram egasiga tegishli bo'lishi shart
    if not admin or admin.telegram_id != tid:
        await message.answer("❌ Hisob topilmadi yoki ruxsat yo'q.")
        return

    admin.hashed_password = get_password_hash(new_password)
    admin.token_version += 1        # ochiq sessiyalar bekor qilinadi
    admin.must_change_password = False
    admin.failed_attempts = 0
    admin.locked_until = None
    admin.updated_at = utcnow()
    await admin.save()

    await message.answer(
        f"✅ <b>{esc(admin.username)}</b> paroli o'zgartirildi!\n"
        f"<i>Barcha ochiq sessiyalar yopildi — qaytadan kiring.</i>"
    )


# ─── Yangi do'kon: botda tasdiqlash / rad etish ───────────────────────────────

async def _shop_from_callback(callback: CallbackQuery):
    from app.models import Shop
    raw = callback.data.split(":", 1)[1]
    if not _OBJECT_ID.match(raw):
        await callback.answer("Noto'g'ri so'rov", show_alert=True)
        return None
    shop = await Shop.get(raw)
    if not shop:
        await callback.answer("Do'kon topilmadi", show_alert=True)
        return None
    return shop


@router.callback_query(F.data.startswith("shop_ok:"))
async def cb_shop_approve(callback: CallbackQuery):
    from app.models import ShopStatus, User, utcnow

    if not await _is_bot_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    shop = await _shop_from_callback(callback)
    if not shop:
        return

    shop.status = ShopStatus.ACTIVE
    shop.reject_reason = None
    shop.updated_at = utcnow()
    await shop.save()

    owner = await User.get(shop.owner_id)
    if owner and owner.telegram_id:
        try:
            await bot.send_message(
                owner.telegram_id, f"✅ <b>Do'koningiz tasdiqlandi!</b>\n🏪 {esc(shop.name)}"
            )
        except Exception:      # noqa: BLE001
            pass

    await callback.message.edit_text(f"✅ <b>{esc(shop.name)}</b> tasdiqlandi.")
    await callback.answer("Tasdiqlandi")


@router.callback_query(F.data.startswith("shop_no:"))
async def cb_shop_reject(callback: CallbackQuery):
    from app.models import ShopStatus, User, utcnow

    if not await _is_bot_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return

    shop = await _shop_from_callback(callback)
    if not shop:
        return

    shop.status = ShopStatus.REJECTED
    shop.updated_at = utcnow()
    await shop.save()

    owner = await User.get(shop.owner_id)
    if owner and owner.telegram_id:
        try:
            await bot.send_message(
                owner.telegram_id, f"❌ <b>So'rovingiz rad etildi.</b>\n🏪 {esc(shop.name)}"
            )
        except Exception:      # noqa: BLE001
            pass

    await callback.message.edit_text(f"❌ <b>{esc(shop.name)}</b> rad etildi.")
    await callback.answer("Rad etildi")


def setup_bot():
    """Barcha do'kon-egasi/qarzdor amallari web ilovada — bot faqat kirish nuqtasi."""
    from app.bot.middlewares.auth import AuthMiddleware
    from app.bot.middlewares.throttle import ThrottleMiddleware

    # Flood himoyasi eng birinchi — bloklangan foydalanuvchini tekshirish
    # uchun ham bazaga so'rov ketadi, spamchi shu yergacha yetmasin
    throttle = ThrottleMiddleware()
    dp.message.outer_middleware(throttle)
    dp.callback_query.outer_middleware(throttle)

    # XATO TUZATILDI: ilgari middleware `dp.update` ga ulangan edi va u yerda
    # event doim `Update` bo'lgani uchun `isinstance(event, Message)` hech qachon
    # bajarilmasdi — ya'ni bloklangan foydalanuvchi tekshiruvi umuman ishlamagan.
    dp.message.outer_middleware(AuthMiddleware())
    dp.callback_query.outer_middleware(AuthMiddleware())
    dp.include_router(router)
    logger.info("Bot sozlandi")
    return bot, dp
