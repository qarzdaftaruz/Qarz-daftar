import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.models import (
    User, Shop, Client, PromoCode, PromoCodeUse, ShopStatus, AppSettings, utcnow,
)
from app.core.tma import verify_init_data, create_tma_token, get_tma_user, InitDataError
from app.core.ratelimit import auth_rate_limit, write_rate_limit, user_write_rate_limit
from app.core import cache, audit
from app.config import settings
from app.utils.helpers import (
    normalize_phone, is_valid_phone, esc, notify_telegram, notify_telegram_bg,
    phone_variants,
)

router = APIRouter(prefix="/api/tma")
logger = logging.getLogger(__name__)

MAX_EXTRA_PHONES = 2
# Bitta foydalanuvchi ochishi mumkin bo'lgan do'konlar soni
# (o'chirilganlar sanoqqa kirmaydi)
MAX_SHOPS_PER_USER = 10

# Bir kunda nechta raqam biriktirish/o'zgartirish mumkin.
# DIQQAT: raqam hozircha tasdiqlanmaydi — begona raqamni yozib boshqa
# odamning qarzlarini ko'rish nazariy jihatdan mumkin. Limit + audit
# yozuvi buni sezilarli qiyinlashtiradi va izsiz qoldirmaydi.
PHONE_CHANGES_PER_DAY = 5


async def _phone_change_guard(user) -> None:
    from app.core.ratelimit import limiter
    from app.config import settings as cfg

    if not cfg.RATE_LIMIT_ENABLED:
        return
    await limiter.check(f"phone-change:{user.telegram_id}", PHONE_CHANGES_PER_DAY, 86400)


class AuthRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=8192)


@router.post("/auth", dependencies=[Depends(auth_rate_limit)])
async def tma_auth(body: AuthRequest):
    """initData tekshirish → JWT + foydalanuvchi holati."""
    tg_user = None

    # Dev rejim faqat lokal muhitda ishlaydi (production'da config majburan o'chiradi)
    if settings.TMA_DEV_MODE and body.init_data.startswith("dev:"):
        raw = body.init_data.split(":", 1)[1].strip()
        if not raw.lstrip("-").isdigit():
            raise HTTPException(400, "dev: formati noto'g'ri")
        tg_user = {"id": int(raw), "first_name": "Dev", "last_name": "User"}
    else:
        try:
            tg_user = verify_init_data(body.init_data)
        except InitDataError as e:
            raise HTTPException(401, str(e))

    telegram_id = tg_user["id"]
    user = await User.find_one(User.telegram_id == telegram_id)

    if not user and settings.TMA_DEV_MODE:
        user = await User(
            telegram_id=telegram_id,
            full_name=f"{tg_user.get('first_name', '')} {tg_user.get('last_name', '')}".strip() or "Dev User",
            phone="+998900000000",
        ).insert()

    if not user:
        # Foydalanuvchi botda hali raqam ulashmagan
        return {"token": None, "has_account": False}

    if user.is_blocked:
        raise HTTPException(403, "Akkauntingiz bloklangan")

    # O'chirilgan do'konlar foydalanuvchiga ko'rinmaydi
    shops = await Shop.find(
        Shop.owner_id == user.id, Shop.status != ShopStatus.DELETED
    ).to_list()

    all_phones = _user_phones(user)
    is_debtor = False
    if all_phones:
        # TEZLIK: ilgari mos keluvchi barcha mijoz yozuvlari yuklanib,
        # Python'da tekshirilardi. Endi bitta "bormi?" so'rovi —
        # birinchi mos yozuvda to'xtaydi.
        found = await Client.find_one({
            "phone": {"$in": all_phones},
            "status": "active",
            "shop_id": {"$nin": [s.id for s in shops]},
        })
        is_debtor = found is not None

    return {
        "token": create_tma_token(telegram_id),
        "has_account": True,
        "is_debtor": is_debtor,
        "user": {
            "id": str(user.id),
            "telegram_id": telegram_id,
            "full_name": user.full_name,
            "phone": user.phone,
            "extra_phones": user.extra_phones,
        },
        "shops": [
            {
                "id": str(s.id),
                "name": s.name,
                "status": s.status,
                "trial_end": s.trial_end.isoformat(),
                "subscription_end": s.subscription_end.isoformat() if s.subscription_end else None,
                "reject_reason": s.reject_reason,
                "block_reason": s.block_reason,
            }
            for s in shops
        ],
    }


def _user_phones(user: User) -> list[str]:
    """Foydalanuvchining barcha raqamlari — normallashtirilgan va xom ko'rinishda.

    Eski yozuvlar turli formatda saqlangan bo'lishi mumkin, shuning uchun
    ikkala variant ham qidiriladi.
    """
    return sorted({v for p in [user.phone, *user.extra_phones] for v in phone_variants(p)})


# ─── Yangi do'kon yaratish ────────────────────────────────────────────────────

class NewShopBody(BaseModel):
    shop_name: str = Field(min_length=2, max_length=60)
    promo_code: str = Field(default="", max_length=32)


@router.post("/shops", dependencies=[Depends(write_rate_limit), Depends(user_write_rate_limit)])
async def create_new_shop(body: NewShopBody, tma: dict = Depends(get_tma_user)):
    """Foydalanuvchi uchun yangi do'kon (birinchi yoki qo'shimcha)."""
    user = await User.find_one(User.telegram_id == tma["telegram_id"])
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi. Avval botda /start bosing.")
    if user.is_blocked:
        raise HTTPException(403, "Akkauntingiz bloklangan")

    shop_name = body.shop_name.strip()
    if not shop_name:
        raise HTTPException(400, "Do'kon nomi kiritilishi shart")

    # O'chirilgan do'konlar chegaraga ham, nom taqqoslashga ham kirmaydi:
    # aks holda admin do'konni o'chirgach, egasi yangisini ocholmay qolardi
    user_shops = await Shop.find(
        Shop.owner_id == user.id, Shop.status != ShopStatus.DELETED
    ).to_list()
    if len(user_shops) >= MAX_SHOPS_PER_USER:
        raise HTTPException(400, "Do'konlar soni chegarasiga yetdingiz")
    if any(s.name.lower() == shop_name.lower() for s in user_shops):
        raise HTTPException(400, "Sizda shu nomli do'kon allaqachon bor")

    promo_id = None
    if body.promo_code.strip():
        code = body.promo_code.strip().upper()
        promo = await PromoCode.find_one(PromoCode.code == code, PromoCode.is_active == True)  # noqa: E712
        if promo and promo.expires_at > utcnow():
            promo_id = promo.id

    trial_start = utcnow()
    shop = await Shop(
        name=shop_name,
        owner_id=user.id,
        status=ShopStatus.PENDING,
        trial_start=trial_start,
        trial_end=trial_start + timedelta(days=settings.TRIAL_DAYS),
    ).insert()

    # ── Promokodni band qilish ────────────────────────────────────────────
    # XATO TUZATILDI (aylanma yo'l): ilgari «bu foydalanuvchi kodni
    # ishlatganmi?» degan tekshiruv o'qish, keyin yozish edi. Ikkita
    # so'rovni bir vaqtda yuborib (yoki tugmani ikki marta bosib) bitta
    # promokoddan bir necha do'konga bonus olish mumkin edi.
    # Endi tekshiruv va yozuv bitta atomar so'rovda: MongoDB bitta
    # hujjatga bir vaqtda ikkita yozuvni o'tkazmaydi.
    extra_days = 0
    if promo_id:
        claimed = await PromoCode.get_motor_collection().update_one(
            {"_id": promo_id, "uses.owner_id": {"$ne": user.id}},
            {"$push": {"uses": PromoCodeUse(shop_id=shop.id, owner_id=user.id).model_dump()}},
        )
        if claimed.modified_count == 1:
            extra_days = settings.PROMO_EXTRA_DAYS
            shop.trial_end = trial_start + timedelta(days=settings.TRIAL_DAYS + extra_days)
            shop.promo_code_id = promo_id
            await shop.save()
        else:
            promo_id = None      # allaqachon ishlatilgan — bonus yo'q

    admin_tid = await cache.admin_telegram_id()
    if admin_tid:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"shop_ok:{shop.id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"shop_no:{shop.id}"),
        ]])
        notify_telegram_bg(
            admin_tid,
            f"🆕 <b>Yangi do'kon so'rovi</b>\n\n"
            f"🏪 {esc(shop.name)}\n"
            f"👤 {esc(user.full_name)}\n"
            f"📞 {esc(user.phone)}\n"
            f"📅 Trial: {settings.TRIAL_DAYS + extra_days} kun"
            + (f"\n🎁 Promo: {esc(body.promo_code.upper())}" if extra_days else ""),
            reply_markup=kb,
        )

    return {"shop_id": str(shop.id), "status": "pending", "promo_applied": bool(promo_id)}


# ─── Profil: qo'shimcha telefon ───────────────────────────────────────────────

class PhoneBody(BaseModel):
    phone: str = Field(min_length=7, max_length=20)


async def _me(tma: dict) -> User:
    user = await User.find_one(User.telegram_id == tma["telegram_id"])
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    if user.is_blocked:
        raise HTTPException(403, "Akkauntingiz bloklangan")
    return user


@router.post("/profile/add-phone", dependencies=[Depends(write_rate_limit), Depends(user_write_rate_limit)])
async def add_phone(body: PhoneBody, tma: dict = Depends(get_tma_user)):
    user = await _me(tma)

    phone = normalize_phone(body.phone)
    if not is_valid_phone(phone):
        raise HTTPException(400, "Telefon raqam formati noto'g'ri (masalan: +998901234567)")
    if len(user.extra_phones) >= MAX_EXTRA_PHONES:
        raise HTTPException(400, f"Maksimal {MAX_EXTRA_PHONES} ta qo'shimcha raqam qo'shish mumkin")
    if phone == normalize_phone(user.phone) or phone in {normalize_phone(p) for p in user.extra_phones}:
        raise HTTPException(400, "Bu raqam allaqachon qo'shilgan")

    # Bir raqam bir nechta akkauntga biriktirilmasin — aks holda
    # boshqa odamning qarzlari ko'rinib qolishi mumkin
    taken = await User.find_one({
        "_id": {"$ne": user.id},
        "$or": [{"phone": phone}, {"extra_phones": phone}],
    })
    if taken:
        raise HTTPException(400, "Bu raqam boshqa akkauntga biriktirilgan")

    await _phone_change_guard(user)

    user.extra_phones.append(phone)
    user.updated_at = utcnow()
    await user.save()
    await audit.log(
        "profile.phone_add", actor_type="owner", actor_name=user.full_name,
        actor_id=user.telegram_id, entity_type="user", entity_id=user.id,
        entity_label=user.full_name,
        summary=f"{user.full_name} ({user.phone}) qo'shimcha raqam biriktirdi: {phone}",
        meta={"phone": phone},
    )
    return {"ok": True, "extra_phones": user.extra_phones}


@router.delete("/profile/phones/{index}", dependencies=[Depends(write_rate_limit), Depends(user_write_rate_limit)])
async def remove_phone(index: int, tma: dict = Depends(get_tma_user)):
    user = await _me(tma)
    if index < 0 or index >= len(user.extra_phones):
        raise HTTPException(400, "Noto'g'ri indeks")

    removed = user.extra_phones.pop(index)
    user.updated_at = utcnow()
    await user.save()
    await audit.log(
        "profile.phone_remove", actor_type="owner", actor_name=user.full_name,
        actor_id=user.telegram_id, entity_type="user", entity_id=user.id,
        entity_label=user.full_name,
        summary=f"{user.full_name} raqamni olib tashladi: {removed}",
        meta={"phone": removed},
    )
    return {"ok": True, "extra_phones": user.extra_phones}


@router.put("/profile/phones/{index}", dependencies=[Depends(write_rate_limit), Depends(user_write_rate_limit)])
async def update_phone(index: int, body: PhoneBody, tma: dict = Depends(get_tma_user)):
    user = await _me(tma)
    if index < 0 or index >= len(user.extra_phones):
        raise HTTPException(400, "Noto'g'ri indeks")
    # Xavfsizlik: birinchi qo'shilgan raqamni o'zgartirib bo'lmaydi
    if index == 0:
        raise HTTPException(400, "Birinchi qo'shilgan raqamni o'zgartirib bo'lmaydi")

    phone = normalize_phone(body.phone)
    if not is_valid_phone(phone):
        raise HTTPException(400, "Telefon raqam formati noto'g'ri (masalan: +998901234567)")

    others = {normalize_phone(p) for i, p in enumerate(user.extra_phones) if i != index}
    if phone == normalize_phone(user.phone) or phone in others:
        raise HTTPException(400, "Bu raqam allaqachon mavjud")

    taken = await User.find_one({
        "_id": {"$ne": user.id},
        "$or": [{"phone": phone}, {"extra_phones": phone}],
    })
    if taken:
        raise HTTPException(400, "Bu raqam boshqa akkauntga biriktirilgan")

    await _phone_change_guard(user)

    old_phone = user.extra_phones[index]
    user.extra_phones[index] = phone
    user.updated_at = utcnow()
    await user.save()
    await audit.log(
        "profile.phone_update", actor_type="owner", actor_name=user.full_name,
        actor_id=user.telegram_id, entity_type="user", entity_id=user.id,
        entity_label=user.full_name,
        summary=f"{user.full_name} raqamni o'zgartirdi: {old_phone} -> {phone}",
        meta={"from": old_phone, "to": phone},
    )
    return {"ok": True, "extra_phones": user.extra_phones}
