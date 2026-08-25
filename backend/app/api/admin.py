import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field, field_validator
from beanie import PydanticObjectId
from beanie.operators import In

from app.models import (
    AdminAuth, Shop, User, Client, Debt, Payment,
    PromoCode, AppSettings, SupportMessage, ShopStatus, DebtStatus, utcnow,
)
from app.core.security import (
    verify_password, create_access_token, get_password_hash,
    get_current_admin, get_current_super_admin, validate_password_strength,
)
from app.core.ratelimit import login_rate_limit, limiter, client_ip
from app.core import audit, cache
from app.config import settings
from app.utils.helpers import (
    generate_debt_number, format_money, debt_notification,
    safe_regex, month_starts, month_label, esc,
    to_naive_utc, parse_due_date, debt_status_for, subscription_expired,
    restart_trial_if_expired, notify_debtor_bg, notify_telegram_bg,
)
from app.utils import reminders

router = APIRouter(prefix="/api/admin")
logger = logging.getLogger(__name__)

_ACTIVE = ["open", "partial", "overdue"]
MAX_PAGE_SIZE = 100

# Bitta mijoz sahifasida ko'rsatiladigan maksimal yozuvlar.
# Chegarasiz yuklash uzoq yillik mijozda xotirani to'ldirardi.
MAX_CLIENT_DEBTS = 300
MAX_CLIENT_PAYMENTS = 200


def _oid(value: str, label: str = "ID") -> PydanticObjectId:
    """Noto'g'ri ObjectId 500 emas, 404 qaytarsin."""
    try:
        return PydanticObjectId(value)
    except Exception:      # noqa: BLE001
        raise HTTPException(404, f"{label} topilmadi")


def _page(skip: int, limit: int) -> tuple[int, int]:
    return max(0, skip), max(1, min(limit, MAX_PAGE_SIZE))


# ─── AUTH ─────────────────────────────────────────────────────────────────────

@router.post("/auth/login", dependencies=[Depends(login_rate_limit)])
async def login(request: Request, form: OAuth2PasswordRequestForm = Depends()):
    username = (form.username or "").strip()
    admin = await AdminAuth.find_one(AdminAuth.username == username)

    now = utcnow()
    if admin and admin.locked_until and admin.locked_until > now:
        left = int((admin.locked_until - now).total_seconds())
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Hisob vaqtincha bloklandi. {left} soniyadan keyin urining.",
        )

    if not admin or not verify_password(form.password, admin.hashed_password):
        if admin:
            admin.failed_attempts += 1
            locked = admin.failed_attempts >= settings.LOGIN_MAX_ATTEMPTS
            if locked:
                admin.locked_until = now + timedelta(seconds=settings.LOGIN_LOCKOUT_SECONDS)
                admin.failed_attempts = 0
                logger.warning("Hisob bloklandi (ko'p urinish): %s", username)
            await admin.save()
            if locked:
                # Bu jiddiy signal — super adminlarga darhol xabar ketadi
                await audit.log(
                    "auth.locked", actor_type="admin", actor_name=username,
                    summary=f"«{username}» hisobi {settings.LOGIN_MAX_ATTEMPTS} ta noto'g'ri "
                            f"paroldan keyin {settings.LOGIN_LOCKOUT_SECONDS // 60} daqiqaga bloklandi",
                    request=request,
                )
        logger.info("Muvaffaqiyatsiz login: user=%s ip=%s", username, client_ip(request))
        await audit.log(
            "auth.login_failed", actor_type="admin", actor_name=username or "?",
            summary=f"Muvaffaqiyatsiz kirish urinishi: {username or '—'}", request=request,
        )
        # Bir xil xabar — hisob bor-yo'qligini oshkor qilmaymiz
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login yoki parol noto'g'ri")

    admin.failed_attempts = 0
    admin.locked_until = None
    admin.last_login_at = now
    await admin.save()

    # Muvaffaqiyatli kirishdan keyin IP limitini bo'shatamiz
    await limiter.reset(f"login:{client_ip(request)}")
    await audit.log_admin(admin, "auth.login", summary="Panelga kirdi", request=request)

    return {
        "access_token": create_access_token({
            "sub": f"admin:{admin.username}",
            "tv": admin.token_version,
            "typ": "admin",
        }),
        "token_type": "bearer",
        "is_super": admin.is_super,
        "must_change_password": admin.must_change_password,
    }


async def _send_password_reset(admin: AdminAuth) -> None:
    from app.bot.main import request_password_change as rpc
    try:
        await rpc(admin.telegram_id, admin.username)
    except Exception as e:      # noqa: BLE001
        logger.error("Parol tiklash xabari yuborilmadi (%s): %s", admin.username, e)
        raise HTTPException(502, "Botga xabar yuborib bo'lmadi. Keyinroq urining.")


@router.post("/auth/request-password-change")
async def request_password_change(admin: AdminAuth = Depends(get_current_admin)):
    """Botdan parol tiklash (kirgan holatda)."""
    if not admin.telegram_id:
        raise HTTPException(400, "Bu hisob uchun Telegram ID sozlanmagan")
    await _send_password_reset(admin)
    return {"ok": True}


class ForgotBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)


@router.post("/auth/forgot-password", dependencies=[Depends(login_rate_limit)])
async def forgot_password(body: ForgotBody):
    """Login sahifasidan parol tiklash.

    Javob har doim bir xil — mavjud loginlarni tashqaridan aniqlab
    bo'lmasligi uchun (user enumeration himoyasi).
    """
    admin = await AdminAuth.find_one(AdminAuth.username == body.username.strip())
    if admin and admin.telegram_id:
        try:
            await _send_password_reset(admin)
        except HTTPException:
            pass
    return {"ok": True, "message": "Agar bunday hisob mavjud bo'lsa, Telegram'ga xabar yuborildi."}


@router.get("/profile/me")
async def my_profile(admin: AdminAuth = Depends(get_current_admin)):
    return {
        "username": admin.username,
        "telegram_id": admin.telegram_id,
        "is_super": admin.is_super,
        "must_change_password": admin.must_change_password,
    }


class ProfilePasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


@router.put("/profile/password")
async def change_my_password(body: ProfilePasswordBody, admin: AdminAuth = Depends(get_current_admin)):
    if not verify_password(body.current_password, admin.hashed_password):
        raise HTTPException(400, "Joriy parol noto'g'ri")
    if body.new_password == body.current_password:
        raise HTTPException(400, "Yangi parol eskisidan farq qilishi kerak")
    validate_password_strength(body.new_password)

    admin.hashed_password = get_password_hash(body.new_password)
    admin.token_version += 1        # boshqa qurilmalardagi sessiyalar bekor bo'ladi
    admin.must_change_password = False
    admin.updated_at = utcnow()
    await admin.save()
    await audit.log_admin(admin, "auth.password_changed", summary="Parolini o'zgartirdi")
    return {"ok": True, "relogin_required": True}


class ProfileUsernameBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.\-]+$")


@router.put("/profile/username")
async def change_my_username(body: ProfileUsernameBody, admin: AdminAuth = Depends(get_current_admin)):
    if not verify_password(body.current_password, admin.hashed_password):
        raise HTTPException(400, "Joriy parol noto'g'ri")

    new_username = body.new_username.strip()
    if new_username != admin.username and await AdminAuth.find_one(AdminAuth.username == new_username):
        raise HTTPException(400, "Bu login band")

    old_username = admin.username
    admin.username = new_username
    admin.token_version += 1        # eski tokendagi username endi yaroqsiz
    admin.updated_at = utcnow()
    await admin.save()
    await audit.log_admin(
        admin, "auth.username_changed",
        summary=f"Login o'zgartirildi: {old_username} → {new_username}",
    )
    return {"ok": True, "relogin_required": True}


# ─── ADMIN MANAGEMENT (faqat super admin) ─────────────────────────────────────
# XAVFSIZLIK: ilgari bu endpointlar oddiy adminga ham ochiq edi —
# har qanday admin yangi admin yaratib, huquqini kengaytira olardi.

@router.get("/admins")
async def get_admins(_: AdminAuth = Depends(get_current_super_admin)):
    admins = await AdminAuth.find_all().to_list()
    return [
        {
            "id": str(a.id),
            "username": a.username,
            "telegram_id": a.telegram_id,
            "is_super": a.is_super,
            "last_login_at": a.last_login_at.isoformat() if a.last_login_at else None,
        }
        for a in admins
    ]


class CreateAdminBody(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.\-]+$")
    password: str = Field(min_length=1, max_length=128)
    telegram_id: Optional[int] = Field(default=None, ge=1)


@router.post("/admins")
async def create_admin(body: CreateAdminBody, request: Request, current: AdminAuth = Depends(get_current_super_admin)):
    validate_password_strength(body.password)
    if await AdminAuth.find_one(AdminAuth.username == body.username):
        raise HTTPException(400, "Bu login allaqachon mavjud")
    admin = await AdminAuth(
        username=body.username,
        hashed_password=get_password_hash(body.password),
        telegram_id=body.telegram_id,
        is_super=False,          # super huquq faqat qo'lda beriladi
    ).insert()
    await audit.log_admin(
        current, "admin.create", request=request,
        entity_type="admin", entity_id=admin.id, entity_label=admin.username,
        summary=f"Yangi admin qo'shildi: {admin.username}",
    )
    return {"id": str(admin.id)}


@router.delete("/admins/{aid}")
async def delete_admin(aid: str, request: Request, current: AdminAuth = Depends(get_current_super_admin)):
    admin = await AdminAuth.get(_oid(aid, "Admin"))
    if not admin:
        raise HTTPException(404, "Admin topilmadi")
    if admin.is_super:
        raise HTTPException(400, "Super adminni o'chirib bo'lmaydi")
    if admin.id == current.id:
        raise HTTPException(400, "O'z hisobingizni o'chirib bo'lmaydi")
    await admin.delete()
    await audit.log_admin(
        current, "admin.delete", request=request,
        entity_type="admin", entity_id=admin.id, entity_label=admin.username,
        summary=f"Admin o'chirildi: {admin.username}",
    )
    return {"ok": True}


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def dashboard(_: AdminAuth = Depends(get_current_admin)):
    # TEZLIK: ilgari har bir oy uchun alohida count so'rovi ketardi.
    # Endi bitta $bucket aggregation — 6 ta borish o'rniga 1 ta.
    starts = month_starts(6)
    rows = await Shop.get_motor_collection().aggregate([
        {"$match": {"created_at": {"$gte": starts[0]}}},
        {"$bucket": {
            "groupBy": "$created_at",
            "boundaries": starts + [utcnow() + timedelta(days=1)],
            "default": "other",
            "output": {"n": {"$sum": 1}},
        }},
    ]).to_list(length=None)
    by_start = {r["_id"]: r["n"] for r in rows if r["_id"] != "other"}
    monthly = [
        {"month": month_label(s, with_year=True), "shops": by_start.get(s, 0)}
        for s in starts
    ]

    return {
        "stats": {
            # O'chirilgan do'konlar umumiy sanoqqa kirmaydi
            "total_shops": await Shop.find({"status": {"$ne": ShopStatus.DELETED.value}}).count(),
            "active": await Shop.find(Shop.status == ShopStatus.ACTIVE).count(),
            "blocked": await Shop.find(Shop.status == ShopStatus.BLOCKED).count(),
            "pending": await Shop.find(Shop.status == ShopStatus.PENDING).count(),
            "deleted": await Shop.find(Shop.status == ShopStatus.DELETED).count(),
            "total_users": await User.count(),
            "total_debts": await Debt.count(),
        },
        "monthly_growth": monthly,
    }


# ─── SHOPS ────────────────────────────────────────────────────────────────────

@router.get("/shops")
async def get_shops(
    status_filter: Optional[ShopStatus] = Query(default=None, alias="status"),
    skip: int = 0,
    limit: int = 20,
    _: AdminAuth = Depends(get_current_admin),
):
    skip, limit = _page(skip, limit)
    # "Barchasi" ro'yxatida o'chirilganlar ko'rinmaydi — ular alohida
    # «Chiqindi qutisi» bo'limida
    query = (
        {"status": status_filter.value} if status_filter
        else {"status": {"$ne": ShopStatus.DELETED.value}}
    )
    shops = await Shop.find(query).sort(-Shop.created_at).skip(skip).limit(limit).to_list()
    total = await Shop.find(query).count()

    # N+1 o'rniga: egalar va sanoqlar to'plam bo'yicha bir marta olinadi
    owner_ids = list({s.owner_id for s in shops})
    owners = {o.id: o for o in await User.find(In(User.id, owner_ids)).to_list()} if owner_ids else {}
    shop_ids = [s.id for s in shops]

    client_counts = await _group_count(Client, {"shop_id": {"$in": shop_ids}}, "shop_id")
    debt_counts = await _group_count(
        Debt, {"shop_id": {"$in": shop_ids}, "status": {"$in": _ACTIVE}}, "shop_id"
    )

    result = []
    for s in shops:
        owner = owners.get(s.owner_id)
        owner_phones = [p for p in ([owner.phone] + owner.extra_phones) if p] if owner else []
        result.append({
            "id": str(s.id),
            "name": s.name,
            "owner": owner.full_name if owner else "?",
            "owner_phone": owner.phone if owner else "?",
            "owner_phones": owner_phones,
            "status": s.status,
            "trial_end": s.trial_end.isoformat(),
            "subscription_end": s.subscription_end.isoformat() if s.subscription_end else None,
            "client_count": client_counts.get(s.id, 0),
            "active_debts": debt_counts.get(s.id, 0),
            "created_at": s.created_at.isoformat(),
            "deleted_at": s.deleted_at.isoformat() if s.deleted_at else None,
            "deleted_by": s.deleted_by,
            # Butunlay yo'q qilinishiga necha kun qolgani
            "purge_in_days": (
                max(0, settings.SHOP_PURGE_DAYS - (utcnow() - s.deleted_at).days)
                if s.deleted_at else None
            ),
            # Obuna muddati tugaganmi — avtomatik to'xtatilganlar ajralib tursin
            "is_expired": subscription_expired(s),
            "expired_at": s.expired_at.isoformat() if s.expired_at else None,
        })
    return {"shops": result, "total": total}


async def _group_count(model, match: dict, field: str) -> dict:
    """Aggregation orqali guruh bo'yicha sanoq — N+1 so'rovni almashtiradi."""
    if not match.get(field, {}).get("$in"):
        return {}
    rows = await model.get_motor_collection().aggregate([
        {"$match": match},
        {"$group": {"_id": f"${field}", "n": {"$sum": 1}}},
    ]).to_list(length=None)
    return {r["_id"]: r["n"] for r in rows}


async def _audit_shop(admin, request, action: str, shop: Shop, what: str, **meta):
    """Do'kon ustidagi amalni audit logga yozadi."""
    await audit.log_admin(
        admin, action, request=request,
        entity_type="shop", entity_id=shop.id, entity_label=shop.name,
        shop_id=shop.id, summary=f"Do'kon «{shop.name}» {what}", meta=meta,
    )


async def _notify_owner(shop: Shop, msg: str):
    # TEZLIK: Telegram javobini kutmaymiz — admin tugmasi darhol javob bersin
    owner = await User.get(shop.owner_id)
    if owner:
        notify_telegram_bg(owner.telegram_id, msg)


class ReasonBody(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=300)


async def _get_live_shop(sid: str) -> Shop:
    """Do'konni oladi; «chiqindi qutisi»dagi bo'lsa amalni rad etadi.

    XATO TUZATILDI: ilgari `approve`/`block`/`reject` do'kon holatini
    umuman tekshirmasdi. O'chirilgan do'konni «tasdiqlash» uni faol
    qilib qo'yardi, lekin `deleted_at` joyida qolardi — natijada do'kon
    ishlab turgan holda panelda «N kundan keyin butunlay o'chadi» deb
    ko'rinardi va tozalash vazifasi uni hech qachon topmasdi.
    Qaytarish uchun faqat bitta to'g'ri yo'l bor: «Tiklash» tugmasi.
    """
    shop = await Shop.get(_oid(sid, "Do'kon"))
    if not shop:
        raise HTTPException(404, "Do'kon topilmadi")
    if shop.status == ShopStatus.DELETED:
        raise HTTPException(
            400,
            "Do'kon o'chirilgan. Avval «Tiklash» tugmasi bilan chiqindi qutisidan qaytaring.",
        )
    return shop


@router.post("/shops/{sid}/approve")
async def approve(sid: str, request: Request, current: AdminAuth = Depends(get_current_admin)):
    shop = await _get_live_shop(sid)
    shop.status = ShopStatus.ACTIVE
    shop.reject_reason = None
    # Ilgari bloklangan bo'lsa sabab qolib ketardi va panelda
    # "faol, lekin blok sababi bor" degan ziddiyat ko'rinardi
    shop.block_reason = None
    # Tasdiqlash kechikkan bo'lsa sinov muddati noldan boshlanadi —
    # do'kondor admin sekinligi uchun jazolanmasin
    restart_trial_if_expired(shop)
    shop.updated_at = utcnow()
    await shop.save()
    await _notify_owner(
        shop,
        f"✅ <b>Do'koningiz tasdiqlandi!</b>\n🏪 {esc(shop.name)}\n\nPanelni oching va ishlashni boshlang.",
    )
    await _audit_shop(current, request, "shop.approve", shop, "tasdiqlandi")
    return {"ok": True}


@router.post("/shops/{sid}/reject")
async def reject(sid: str, request: Request, body: ReasonBody = ReasonBody(), current: AdminAuth = Depends(get_current_admin)):
    shop = await _get_live_shop(sid)
    shop.status = ShopStatus.REJECTED
    shop.reject_reason = body.reason
    shop.updated_at = utcnow()
    await shop.save()
    msg = "❌ <b>So'rovingiz rad etildi.</b>"
    if body.reason:
        msg += f"\n\nSabab: {esc(body.reason)}"
    await _notify_owner(shop, msg)
    await _audit_shop(current, request, "shop.reject", shop, "rad etildi", reason=body.reason)
    return {"ok": True}


@router.post("/shops/{sid}/block")
async def block(sid: str, request: Request, body: ReasonBody = ReasonBody(), current: AdminAuth = Depends(get_current_admin)):
    shop = await _get_live_shop(sid)
    shop.status = ShopStatus.BLOCKED
    shop.block_reason = body.reason
    shop.updated_at = utcnow()
    await shop.save()
    msg = "🚫 <b>Do'koningiz vaqtincha bloklandi.</b>"
    if body.reason:
        msg += f"\n\nSabab: {esc(body.reason)}"
    await _notify_owner(shop, msg)
    await _audit_shop(current, request, "shop.block", shop, "bloklandi", reason=body.reason)
    return {"ok": True}


@router.post("/shops/{sid}/unblock")
async def unblock(sid: str, request: Request, current: AdminAuth = Depends(get_current_admin)):
    shop = await _get_live_shop(sid)

    # Obuna muddati tugagan bo'lsa blokdan chiqarishning foydasi yo'q:
    # do'kon baribir ochilmaydi va keyingi tekshiruvda qayta bloklanadi.
    if subscription_expired(shop):
        raise HTTPException(
            400,
            "Obuna muddati tugagan — avval «Uzaytirish» tugmasi bilan muddatni uzaytiring.",
        )

    shop.status = ShopStatus.ACTIVE
    shop.block_reason = None
    shop.expired_at = None
    shop.updated_at = utcnow()
    await shop.save()
    await _notify_owner(shop, f"✅ Do'koningiz blokdan chiqarildi!\n🏪 {esc(shop.name)}")
    await _audit_shop(current, request, "shop.unblock", shop, "blokdan chiqarildi")
    return {"ok": True}


class ExtendBody(BaseModel):
    days: int = Field(default=30, ge=1, le=3650)


@router.post("/shops/{sid}/extend")
async def extend(sid: str, request: Request, body: ExtendBody = ExtendBody(), current: AdminAuth = Depends(get_current_admin)):
    shop = await _get_live_shop(sid)
    now = utcnow()
    end = shop.subscription_end or shop.trial_end
    if end < now:
        end = now
    shop.subscription_end = end + timedelta(days=body.days)
    shop.status = ShopStatus.ACTIVE
    shop.warning_sent = False
    # Muddat tugagani uchun to'xtatilgan bo'lsa — sabab ham tozalanadi
    shop.expired_at = None
    if shop.block_reason == "Obuna muddati tugadi":
        shop.block_reason = None
    shop.updated_at = now
    await shop.save()
    await _notify_owner(
        shop,
        f"✅ Obunangiz {body.days} kunga uzaytirildi!\n"
        f"📅 {shop.subscription_end.strftime('%d.%m.%Y')} gacha",
    )
    await _audit_shop(
        current, request, "shop.extend", shop,
        f"obuna {body.days} kunga uzaytirildi ({shop.subscription_end.strftime('%d.%m.%Y')} gacha)",
        days=body.days,
    )
    return {"ok": True}


@router.delete("/shops/{sid}")
async def delete_shop(sid: str, request: Request, current: AdminAuth = Depends(get_current_admin)):
    """Do'konni «chiqindi qutisi»ga jo'natish (yumshoq o'chirish).

    Ma'lumotlar darhol yo'q qilinmaydi — SHOP_PURGE_DAYS kun saqlanadi
    va shu muddat ichida qaytarilishi mumkin. Xato bosilgan tugma
    47 ta mijozning qarz tarixini yo'q qilib yubormasligi uchun.
    """
    shop_id = _oid(sid, "Do'kon")
    shop = await Shop.get(shop_id)
    if not shop:
        raise HTTPException(404, "Do'kon topilmadi")
    if shop.status == ShopStatus.DELETED:
        raise HTTPException(400, "Do'kon allaqachon o'chirilgan")

    counts = {
        "clients": await Client.find(Client.shop_id == shop_id).count(),
        "debts": await Debt.find(Debt.shop_id == shop_id).count(),
    }

    shop.status_before_delete = str(shop.status.value if hasattr(shop.status, "value") else shop.status)
    shop.status = ShopStatus.DELETED
    shop.deleted_at = utcnow()
    shop.deleted_by = current.username
    shop.updated_at = utcnow()
    await shop.save()

    purge_date = (shop.deleted_at + timedelta(days=settings.SHOP_PURGE_DAYS)).strftime("%d.%m.%Y")
    await _notify_owner(
        shop,
        f"🗑 <b>{esc(shop.name)}</b> do'koni tizimdan o'chirildi.\n\n"
        f"Ma'lumotlar {purge_date} gacha saqlanadi — xato bo'lsa admin bilan bog'laning.",
    )
    await _audit_shop(
        current, request, "shop.delete", shop,
        f"o'chirildi ({counts['clients']} mijoz, {counts['debts']} qarz). "
        f"{purge_date} gacha qaytarish mumkin",
        **counts, purge_date=purge_date,
    )
    return {"ok": True, "purge_date": purge_date, "restorable": True}


@router.post("/shops/{sid}/restore")
async def restore_shop(sid: str, request: Request, current: AdminAuth = Depends(get_current_admin)):
    """O'chirilgan do'konni chiqindi qutisidan qaytarish."""
    shop = await Shop.get(_oid(sid, "Do'kon"))
    if not shop:
        raise HTTPException(404, "Do'kon topilmadi")
    if shop.status != ShopStatus.DELETED:
        raise HTTPException(400, "Bu do'kon o'chirilmagan")

    # Avvalgi holatiga qaytaramiz; noma'lum bo'lsa — bloklangan holatda
    # qoldiramiz, admin o'zi faollashtirsin
    previous = shop.status_before_delete or ShopStatus.BLOCKED.value
    try:
        shop.status = ShopStatus(previous)
    except ValueError:
        shop.status = ShopStatus.BLOCKED

    shop.deleted_at = None
    shop.deleted_by = None
    shop.status_before_delete = None
    shop.updated_at = utcnow()
    await shop.save()

    await _notify_owner(shop, f"♻️ <b>{esc(shop.name)}</b> do'koni qayta tiklandi.")
    await _audit_shop(current, request, "shop.restore", shop, f"qaytarildi (holat: {shop.status})")
    return {"ok": True, "status": shop.status}


@router.delete("/shops/{sid}/purge")
async def purge_shop(sid: str, request: Request, current: AdminAuth = Depends(get_current_super_admin)):
    """Do'konni 30 kunni kutmasdan butunlay yo'q qilish.

    Faqat super admin — bu amalni ortga qaytarib bo'lmaydi.
    """
    shop_id = _oid(sid, "Do'kon")
    shop = await Shop.get(shop_id)
    if not shop:
        raise HTTPException(404, "Do'kon topilmadi")
    if shop.status != ShopStatus.DELETED:
        raise HTTPException(400, "Avval do'konni o'chiring, keyin butunlay yo'q qilish mumkin")

    counts = await purge_shop_data(shop_id)
    name = shop.name
    await shop.delete()
    await _audit_shop(
        current, request, "shop.purge", shop,
        f"BUTUNLAY YO'Q QILINDI ({counts['clients']} mijoz, {counts['debts']} qarz)",
        **counts,
    )
    logger.warning("Do'kon butunlay yo'q qilindi: %s (%s)", name, current.username)
    return {"ok": True}


async def purge_shop_data(shop_id: PydanticObjectId) -> dict:
    """Do'konga tegishli barcha yozuvlarni bazadan o'chiradi."""
    counts = {
        "clients": await Client.find(Client.shop_id == shop_id).count(),
        "debts": await Debt.find(Debt.shop_id == shop_id).count(),
    }
    await Payment.get_motor_collection().delete_many({"shop_id": shop_id})
    await Debt.get_motor_collection().delete_many({"shop_id": shop_id})
    await Client.get_motor_collection().delete_many({"shop_id": shop_id})
    await SupportMessage.get_motor_collection().delete_many({"shop_id": shop_id})
    return counts


# ─── USERS ────────────────────────────────────────────────────────────────────

@router.get("/users")
async def get_users(
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    _: AdminAuth = Depends(get_current_admin),
):
    skip, limit = _page(skip, limit)
    query: dict = {}
    if search and search.strip():
        pattern = safe_regex(search)
        query["$or"] = [
            {"full_name": {"$regex": pattern, "$options": "i"}},
            {"phone": {"$regex": pattern}},
        ]

    users = await User.find(query).sort(-User.created_at).skip(skip).limit(limit).to_list()
    total = await User.find(query).count()
    shop_counts = await _group_count(Shop, {"owner_id": {"$in": [u.id for u in users]}}, "owner_id")

    return {
        "users": [
            {
                "id": str(u.id),
                "telegram_id": u.telegram_id,
                "full_name": u.full_name,
                "phone": u.phone,
                "is_blocked": u.is_blocked,
                "shops_count": shop_counts.get(u.id, 0),
                "created_at": u.created_at.isoformat(),
            }
            for u in users
        ],
        "total": total,
    }


@router.post("/users/{uid}/block")
async def block_user(uid: str, request: Request, current: AdminAuth = Depends(get_current_admin)):
    u = await User.get(_oid(uid, "Foydalanuvchi"))
    if not u:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    u.is_blocked = True
    u.updated_at = utcnow()
    await u.save()
    await audit.log_admin(
        current, "user.block", request=request,
        entity_type="user", entity_id=u.id, entity_label=u.full_name,
        summary=f"Foydalanuvchi bloklandi: {u.full_name} ({u.phone})",
    )
    return {"ok": True}


@router.post("/users/{uid}/unblock")
async def unblock_user(uid: str, request: Request, current: AdminAuth = Depends(get_current_admin)):
    u = await User.get(_oid(uid, "Foydalanuvchi"))
    if not u:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    u.is_blocked = False
    u.updated_at = utcnow()
    await u.save()
    await audit.log_admin(
        current, "user.unblock", request=request,
        entity_type="user", entity_id=u.id, entity_label=u.full_name,
        summary=f"Foydalanuvchi blokdan chiqarildi: {u.full_name}",
    )
    return {"ok": True}


# ─── PROMO CODES ──────────────────────────────────────────────────────────────

@router.get("/promo-codes")
async def get_promos(_: AdminAuth = Depends(get_current_admin)):
    codes = await PromoCode.find_all().sort(-PromoCode.created_at).limit(MAX_PAGE_SIZE).to_list()
    return [
        {
            "id": str(c.id),
            "code": c.code,
            "expires_at": c.expires_at.isoformat(),
            "is_active": c.is_active,
            "uses_count": len(c.uses),
        }
        for c in codes
    ]


class PromoBody(BaseModel):
    code: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_\-]+$")
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def _future(cls, v: datetime) -> datetime:
        v = to_naive_utc(v)
        if v <= utcnow():
            raise ValueError("Muddat kelajakda bo'lishi kerak")
        return v


@router.post("/promo-codes")
async def create_promo(body: PromoBody, request: Request, current: AdminAuth = Depends(get_current_admin)):
    code = body.code.upper()
    if await PromoCode.find_one(PromoCode.code == code):
        raise HTTPException(400, "Bu kod allaqachon mavjud")
    p = await PromoCode(code=code, expires_at=body.expires_at).insert()
    await audit.log_admin(
        current, "promo.create", request=request,
        entity_type="promo", entity_id=p.id, entity_label=code,
        summary=f"Promokod yaratildi: {code}",
    )
    return {"id": str(p.id)}


@router.delete("/promo-codes/{pid}")
async def delete_promo(pid: str, request: Request, current: AdminAuth = Depends(get_current_admin)):
    p = await PromoCode.get(_oid(pid, "Promokod"))
    if not p:
        raise HTTPException(404, "Promokod topilmadi")
    p.is_active = False
    await p.save()
    await audit.log_admin(
        current, "promo.disable", request=request,
        entity_type="promo", entity_id=p.id, entity_label=p.code,
        summary=f"Promokod o'chirildi: {p.code}",
    )
    return {"ok": True}


# ─── SETTINGS ─────────────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings(_: AdminAuth = Depends(get_current_admin)):
    s = await AppSettings.find_one()
    if not s:
        raise HTTPException(404, "Sozlamalar topilmadi")
    return {
        "reminder_hour": s.reminder_hour,
        "reminder_minute": s.reminder_minute,
        "archive_duration_months": s.archive_duration_months,
        "admin_telegram_id": s.admin_telegram_id,
    }


class SettingsBody(BaseModel):
    reminder_hour: Optional[int] = Field(default=None, ge=0, le=23)
    reminder_minute: Optional[int] = Field(default=None, ge=0, le=59)
    archive_duration_months: Optional[int] = Field(default=None, ge=1, le=120)
    admin_telegram_id: Optional[int] = None

    @field_validator("admin_telegram_id")
    @classmethod
    def _tid(cls, v: Optional[int]) -> Optional[int]:
        # Bo'sh maydon frontend'dan 0 bo'lib keladi — uni "o'rnatilmagan" deb qabul qilamiz
        if not v:
            return None
        if v < 1:
            raise ValueError("Telegram ID musbat son bo'lishi kerak")
        return v


@router.put("/settings")
async def update_settings(body: SettingsBody, request: Request, current: AdminAuth = Depends(get_current_admin)):
    s = await AppSettings.find_one()
    if not s:
        raise HTTPException(404, "Sozlamalar topilmadi")

    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(s, key, value)
    s.updated_at = utcnow()
    await s.save()

    # Eslatma vaqti o'zgarsa — scheduler darhol yangilanadi
    # (ilgari faqat serverni qayta ishga tushirgandan keyin ta'sir qilardi)
    if "reminder_hour" in data or "reminder_minute" in data:
        from app.core.scheduler import reschedule_daily
        reschedule_daily(s.reminder_hour, s.reminder_minute)
    cache.invalidate_settings()

    await audit.log_admin(
        current, "settings.update", request=request,
        summary="Tizim sozlamalari o'zgartirildi", meta=data,
    )
    return {"ok": True}


# ─── SUPPORT ──────────────────────────────────────────────────────────────────

@router.get("/support")
async def get_support(
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 20,
    _: AdminAuth = Depends(get_current_admin),
):
    skip, limit = _page(skip, limit)
    query = {"is_read": False} if unread_only else {}
    msgs = await SupportMessage.find(query).sort(-SupportMessage.created_at).skip(skip).limit(limit).to_list()
    return {
        "messages": [
            {
                "id": str(m.id),
                "shop_name": m.shop_name,
                "user_full_name": m.user_full_name,
                "user_phone": m.user_phone,
                "message": m.message,
                "is_read": m.is_read,
                "created_at": m.created_at.isoformat(),
            }
            for m in msgs
        ],
        "total": await SupportMessage.find(query).count(),
        "unread": await SupportMessage.find({"is_read": False}).count(),
    }


@router.post("/support/{mid}/read")
async def mark_read(mid: str, _: AdminAuth = Depends(get_current_admin)):
    m = await SupportMessage.get(_oid(mid, "Xabar"))
    if not m:
        raise HTTPException(404, "Xabar topilmadi")
    m.is_read = True
    await m.save()
    return {"ok": True}


# ─── SUPER ADMIN (to'liq huquq) ───────────────────────────────────────────────

@router.get("/super/me")
async def super_check(_: AdminAuth = Depends(get_current_super_admin)):
    return {"is_super": True}


@router.get("/super/search")
async def super_search(q: str = "", _: AdminAuth = Depends(get_current_super_admin)):
    """Global qidiruv — do'kon nomi yoki qarzdor nomi/telefoni bo'yicha."""
    q = q.strip()
    if len(q) < 2:
        return {"shops": [], "clients": []}

    # Foydalanuvchi kiritgan matn escape qilinadi (ReDoS / regex injeksiya himoyasi)
    pattern = safe_regex(q)

    # O'chirilgan do'kon qidiruvda chiqmasin — u «chiqindi qutisi»da
    shops = await Shop.find({
        "name": {"$regex": pattern, "$options": "i"},
        "status": {"$ne": ShopStatus.DELETED.value},
    }).limit(20).to_list()
    shop_ids = [s.id for s in shops]
    owners = {
        o.id: o for o in await User.find(In(User.id, list({s.owner_id for s in shops}))).to_list()
    } if shops else {}

    debt_sums = await _sum_remaining(Debt, {"shop_id": {"$in": shop_ids}, "status": {"$in": _ACTIVE}}, "shop_id")
    client_counts = await _group_count(Client, {"shop_id": {"$in": shop_ids}, "status": "active"}, "shop_id")

    shop_results = [
        {
            "id": str(s.id),
            "name": s.name,
            "status": s.status,
            "owner": owners[s.owner_id].full_name if s.owner_id in owners else "?",
            "total_remaining": debt_sums.get(s.id, 0),
            "client_count": client_counts.get(s.id, 0),
        }
        for s in shops
    ]

    clients = await Client.find({
        "status": "active",
        "$or": [
            {"full_name": {"$regex": pattern, "$options": "i"}},
            {"phone": {"$regex": pattern}},
        ],
    }).limit(30).to_list()

    client_ids = [c.id for c in clients]
    c_shops = {
        s.id: s for s in await Shop.find(In(Shop.id, list({c.shop_id for c in clients}))).to_list()
    } if clients else {}
    c_sums = await _sum_remaining(Debt, {"client_id": {"$in": client_ids}, "status": {"$in": _ACTIVE}}, "client_id")
    c_overdue = await _group_count(Debt, {"client_id": {"$in": client_ids}, "status": "overdue"}, "client_id")

    client_results = [
        {
            "id": str(c.id),
            "full_name": c.full_name,
            "phone": c.phone,
            "shop_id": str(c.shop_id),
            "shop_name": c_shops[c.shop_id].name if c.shop_id in c_shops else "?",
            "total_remaining": c_sums.get(c.id, 0),
            "has_overdue": bool(c_overdue.get(c.id)),
        }
        for c in clients
    ]

    return {"shops": shop_results, "clients": client_results}


async def _sum_remaining(model, match: dict, field: str) -> dict:
    if not match.get(field, {}).get("$in"):
        return {}
    rows = await model.get_motor_collection().aggregate([
        {"$match": match},
        {"$group": {"_id": f"${field}", "total": {"$sum": "$remaining"}}},
    ]).to_list(length=None)
    return {r["_id"]: r["total"] for r in rows}


@router.get("/super/shops/{sid}/clients")
async def super_shop_clients(sid: str, _: AdminAuth = Depends(get_current_super_admin)):
    shop = await Shop.get(_oid(sid, "Do'kon"))
    if not shop:
        raise HTTPException(404, "Do'kon topilmadi")

    clients = await Client.find(Client.shop_id == shop.id, Client.status == "active").to_list()
    ids = [c.id for c in clients]
    sums = await _sum_remaining(Debt, {"client_id": {"$in": ids}, "status": {"$in": _ACTIVE}}, "client_id")
    counts = await _group_count(Debt, {"client_id": {"$in": ids}, "status": {"$in": _ACTIVE}}, "client_id")
    overdue = await _group_count(Debt, {"client_id": {"$in": ids}, "status": "overdue"}, "client_id")

    result = [
        {
            "id": str(c.id),
            "full_name": c.full_name,
            "phone": c.phone,
            "total_remaining": sums.get(c.id, 0),
            "active_debts": counts.get(c.id, 0),
            "has_overdue": bool(overdue.get(c.id)),
        }
        for c in clients
    ]
    result.sort(key=lambda x: x["total_remaining"], reverse=True)
    return {"shop_name": shop.name, "clients": result}


@router.get("/super/clients/{cid}")
async def super_client(cid: str, _: AdminAuth = Depends(get_current_super_admin)):
    client = await Client.get(_oid(cid, "Mijoz"))
    if not client:
        raise HTTPException(404, "Mijoz topilmadi")
    shop = await Shop.get(client.shop_id)

    # Chegarasiz yuklash xotirani to'ldirishi mumkin (uzoq yillik mijoz)
    debts = await Debt.find(Debt.client_id == client.id)         .sort(+Debt.created_at).limit(MAX_CLIENT_DEBTS).to_list()
    debt_list = [
        {
            "id": str(d.id),
            "debt_number": d.debt_number,
            "amount": d.amount,
            "paid_amount": d.paid_amount,
            "remaining": d.remaining,
            "status": d.status,
            "due_date": d.due_date.isoformat() if d.due_date else None,
            "note": d.note,
            "created_at": d.created_at.isoformat(),
        }
        for d in debts
    ]
    active = [d for d in debt_list if d["status"] in _ACTIVE]
    payments = await Payment.find(Payment.client_id == client.id)         .sort(-Payment.created_at).limit(MAX_CLIENT_PAYMENTS).to_list()

    return {
        "id": str(client.id),
        "full_name": client.full_name,
        "phone": client.phone,
        "shop_id": str(client.shop_id),
        "shop_name": shop.name if shop else "?",
        "total_remaining": sum(d["remaining"] for d in active),
        "total_paid": sum(d["paid_amount"] for d in debt_list),
        "debts": debt_list,
        "payments": [{"amount": p.amount, "created_at": p.created_at.isoformat()} for p in payments],
    }


MAX_AMOUNT = 100_000_000_000       # 100 mlrd so'm — kiritishdagi xatolardan himoya


class SuperDebtBody(BaseModel):
    amount: int = Field(gt=0, le=MAX_AMOUNT)
    due_date: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=200)


async def _audit_debt(admin, request, action: str, debt: Debt, client: Client, summary: str, **meta):
    """Qarz ustidagi amalni audit logga yozadi."""
    await audit.log_admin(
        admin, action, request=request,
        entity_type="debt", entity_id=debt.id, entity_label=debt.debt_number,
        shop_id=debt.shop_id,
        summary=f"{client.full_name} ({client.phone}) — {summary}",
        meta=meta,
    )


@router.post("/super/clients/{cid}/debts")
async def super_add_debt(cid: str, body: SuperDebtBody, request: Request,
                         current: AdminAuth = Depends(get_current_super_admin)):
    client = await Client.get(_oid(cid, "Mijoz"))
    if not client:
        raise HTTPException(404, "Mijoz topilmadi")
    shop = await Shop.get(client.shop_id)

    due_date = parse_due_date(body.due_date)
    urgent, urgency_text = reminders.due_urgency(due_date)
    number = await generate_debt_number(client.shop_id)
    debt = await Debt(
        debt_number=number, shop_id=client.shop_id, client_id=client.id,
        amount=body.amount, remaining=body.amount, due_date=due_date,
        note=body.note, status=DebtStatus.OPEN,
        due_reminder_sent=urgent,
    ).insert()

    notify_debtor_bg(
        client.phone,
        debt_notification(shop.name if shop else "Do'kon", body.amount, due_date, debt.note)
        + urgency_text,
    )
    await _audit_debt(
        current, request, "debt.create", debt, client,
        f"yangi qarz {format_money(body.amount)} ({debt.debt_number})", amount=body.amount,
    )
    return {"id": str(debt.id), "debt_number": debt.debt_number}


class SuperEditDebtBody(BaseModel):
    amount: Optional[int] = Field(default=None, gt=0, le=MAX_AMOUNT)
    due_date: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=200)


@router.put("/super/debts/{did}")
async def super_edit_debt(did: str, body: SuperEditDebtBody, request: Request,
                          current: AdminAuth = Depends(get_current_super_admin)):
    debt = await Debt.get(_oid(did, "Qarz"))
    if not debt:
        raise HTTPException(404, "Qarz topilmadi")

    data = body.model_dump(exclude_unset=True)
    before = {"amount": debt.amount, "due_date": str(debt.due_date), "note": debt.note}

    amount_changed = "amount" in data and data["amount"] is not None
    if amount_changed:
        if data["amount"] < debt.paid_amount:
            raise HTTPException(400, f"Miqdor to'langan summadan ({format_money(debt.paid_amount)}) kam bo'lmasligi kerak")
        debt.amount = data["amount"]
        debt.remaining = debt.amount - debt.paid_amount

    if "due_date" in data:
        debt.due_date = parse_due_date(data["due_date"])
        # Muddat o'zgardi — oldindan ogohlantirish va kunlik eslatma
        # hisoblagichi noldan boshlansin
        debt.due_reminder_sent = False
        debt.overdue_notified_at = None
        debt.overdue_notice_count = 0
    if "note" in data:
        debt.note = data["note"]

    # XATO TUZATILDI: ilgari holat faqat summaga qarab hisoblanardi —
    # muddati o'tgan qarz tahrirdan keyin `open` bo'lib qolardi va
    # eslatmalardan tushib ketardi
    if amount_changed or "due_date" in data:
        if debt.status not in (DebtStatus.ARCHIVED,):
            debt.status = DebtStatus(
                debt_status_for(debt.remaining, debt.paid_amount, debt.due_date)
            )

    debt.updated_at = utcnow()
    await debt.save()

    client = await Client.get(debt.client_id)
    if client:
        await _audit_debt(
            current, request, "debt.update", debt, client,
            f"qarz {debt.debt_number} o'zgartirildi: {format_money(before['amount'])} → {format_money(debt.amount)}",
            before=before, after={"amount": debt.amount, "due_date": str(debt.due_date), "note": debt.note},
        )
    return {"ok": True}


@router.delete("/super/debts/{did}")
async def super_delete_debt(did: str, request: Request,
                            current: AdminAuth = Depends(get_current_super_admin)):
    debt = await Debt.get(_oid(did, "Qarz"))
    if not debt:
        raise HTTPException(404, "Qarz topilmadi")

    client = await Client.get(debt.client_id)
    payments_deleted = await Payment.find(Payment.debt_id == debt.id).count()

    await Payment.get_motor_collection().delete_many({"debt_id": debt.id})
    await debt.delete()

    if client:
        await _audit_debt(
            current, request, "debt.delete", debt, client,
            f"qarz {debt.debt_number} ({format_money(debt.amount)}) O'CHIRILDI",
            amount=debt.amount, remaining=debt.remaining, payments_deleted=payments_deleted,
        )
    return {"ok": True}


class SuperPaymentBody(BaseModel):
    amount: int = Field(gt=0, le=MAX_AMOUNT)


@router.post("/super/clients/{cid}/payments")
async def super_pay(cid: str, body: SuperPaymentBody, request: Request,
                    current: AdminAuth = Depends(get_current_super_admin)):
    """Umumiy qoldiqdan to'lov — eng eski qarzdan boshlab taqsimlanadi."""
    from app.api.tma_owner import apply_total_payment

    client = await Client.get(_oid(cid, "Mijoz"))
    if not client:
        raise HTTPException(404, "Mijoz topilmadi")
    shop = await Shop.get(client.shop_id)
    result = await apply_total_payment(client, shop.name if shop else "Do'kon", body.amount)

    await audit.log_admin(
        current, "payment.create", request=request,
        entity_type="client", entity_id=client.id, entity_label=client.full_name,
        shop_id=client.shop_id,
        summary=f"{client.full_name} ({client.phone}) — to'lov {format_money(body.amount)}, "
                f"qoldiq {format_money(result['total_remaining'])}",
        meta=result,
    )
    return result


# ─── AUDIT LOG ────────────────────────────────────────────────────────────────

ACTION_LABELS = {
    "auth.login":             "Panelga kirdi",
    "auth.login_failed":      "Muvaffaqiyatsiz kirish",
    "auth.password_changed":  "Parol o'zgartirildi",
    "auth.username_changed":  "Login o'zgartirildi",
    "auth.locked":            "Hisob bloklandi",
    "admin.create":           "Admin qo'shildi",
    "admin.delete":           "Admin o'chirildi",
    "shop.approve":           "Do'kon tasdiqlandi",
    "shop.reject":            "Do'kon rad etildi",
    "shop.block":             "Do'kon bloklandi",
    "shop.unblock":           "Blokdan chiqarildi",
    "shop.extend":            "Obuna uzaytirildi",
    "shop.delete":            "Do'kon o'chirildi",
    "shop.restore":           "Do'kon qaytarildi",
    "shop.purge":             "Do'kon butunlay yo'q qilindi",
    "shop.expired":           "Obuna muddati tugadi",
    "user.block":             "Foydalanuvchi bloklandi",
    "user.unblock":           "Foydalanuvchi blokdan chiqdi",
    "promo.create":           "Promokod yaratildi",
    "promo.disable":          "Promokod o'chirildi",
    "settings.update":        "Sozlamalar o'zgardi",
    "debt.create":            "Qarz qo'shildi",
    "debt.update":            "Qarz o'zgartirildi",
    "debt.delete":            "Qarz o'chirildi",
    "payment.create":         "To'lov qabul qilindi",
    "client.create":          "Mijoz qo'shildi",
    "client.update":          "Mijoz o'zgartirildi",
    "client.archive":         "Mijoz arxivlandi",
    "client.clear_debts":     "Barcha qarzlar yopildi",
    "report.export":          "Excel hisobot yuklandi",
    "debt.remind":            "Qarzdorga eslatma yuborildi",
    "profile.phone_add":      "Telefon raqam qo'shildi",
    "profile.phone_update":   "Telefon raqam o'zgartirildi",
    "profile.phone_remove":   "Telefon raqam olib tashlandi",
    "profile.phone_reclaimed": "Raqam tasdiqlangan egasiga qaytarildi",
}

# Xavfsizlik uchun muhim, ro'yxatda ajratib ko'rsatiladigan amallar
CRITICAL_ACTIONS = {
    "shop.delete", "shop.purge", "debt.delete", "admin.create", "admin.delete",
    "auth.login_failed", "auth.locked", "client.clear_debts", "auth.username_changed",
    # Begona raqamni biriktirib boshqa odamning qarzlarini ko'rish urinishi
    # aynan shu yozuvlardan aniqlanadi
    "profile.phone_add", "profile.phone_update", "profile.phone_reclaimed",
}


@router.get("/audit")
async def get_audit_log(
    action: Optional[str] = None,
    actor: Optional[str] = None,
    entity_type: Optional[str] = None,
    critical_only: bool = False,
    skip: int = 0,
    limit: int = 30,
    _: AdminAuth = Depends(get_current_admin),
):
    """Kim, qachon, nima qilgani — nizoli holatlarni tekshirish uchun."""
    from app.models import AuditLog

    skip, limit = _page(skip, limit)
    query: dict = {}
    # XATO TUZATILDI: ilgari `critical_only` tanlangan amal filtrini
    # jimgina o'chirib yuborardi — admin bitta amalni qidirsa,
    # javobda butunlay boshqa yozuvlar chiqardi.
    if action and critical_only:
        if action not in CRITICAL_ACTIONS:
            return {"items": [], "total": 0, "actions": ACTION_LABELS}
        query["action"] = action
    elif action:
        query["action"] = action
    elif critical_only:
        query["action"] = {"$in": sorted(CRITICAL_ACTIONS)}
    if actor and actor.strip():
        query["actor_name"] = {"$regex": safe_regex(actor), "$options": "i"}
    if entity_type:
        query["entity_type"] = entity_type

    rows = await AuditLog.find(query).sort(-AuditLog.created_at).skip(skip).limit(limit).to_list()
    return {
        "items": [
            {
                "id": str(r.id),
                "action": r.action,
                "action_label": ACTION_LABELS.get(r.action, r.action),
                "is_critical": r.action in CRITICAL_ACTIONS,
                "actor_type": r.actor_type,
                "actor_name": r.actor_name,
                "entity_type": r.entity_type,
                "entity_label": r.entity_label,
                "summary": r.summary,
                "meta": r.meta,
                "ip": r.ip,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "total": await AuditLog.find(query).count(),
        "actions": ACTION_LABELS,
    }


# ─── EXCEL EKSPORT ────────────────────────────────────────────────────────────

def _xlsx_response(content: bytes, filename: str):
    from fastapi.responses import Response as FileResponse
    from urllib.parse import quote

    return FileResponse(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            # filename* — kirill/lotin maxsus belgilari bo'lgan nomlar uchun
            "Content-Disposition": f"attachment; filename=\"report.xlsx\"; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "no-store",
        },
    )


@router.get("/shops/export")
async def export_shops(
    status_filter: Optional[ShopStatus] = Query(default=None, alias="status"),
    request: Request = None,
    current: AdminAuth = Depends(get_current_admin),
):
    """Do'konlar ro'yxatini Excel qilib yuklab olish."""
    from app.utils.excel import build_shops_report

    query = (
        {"status": status_filter.value} if status_filter
        else {"status": {"$ne": ShopStatus.DELETED.value}}
    )
    shops = await Shop.find(query).sort(-Shop.created_at).limit(5000).to_list()
    if not shops:
        raise HTTPException(404, "Eksport uchun do'kon topilmadi")

    owners = {
        o.id: o for o in
        await User.find(In(User.id, list({s.owner_id for s in shops}))).to_list()
    }
    shop_ids = [s.id for s in shops]
    client_counts = await _group_count(Client, {"shop_id": {"$in": shop_ids}}, "shop_id")
    debt_counts = await _group_count(
        Debt, {"shop_id": {"$in": shop_ids}, "status": {"$in": _ACTIVE}}, "shop_id"
    )

    rows = [
        {
            "name": s.name,
            "owner": owners[s.owner_id].full_name if s.owner_id in owners else "?",
            "owner_phone": owners[s.owner_id].phone if s.owner_id in owners else "?",
            "status": s.status.value if hasattr(s.status, "value") else s.status,
            "client_count": client_counts.get(s.id, 0),
            "active_debts": debt_counts.get(s.id, 0),
            "trial_end": s.trial_end,
            "subscription_end": s.subscription_end,
            "created_at": s.created_at,
        }
        for s in shops
    ]

    await audit.log_admin(
        current, "report.export", request=request,
        summary=f"Do'konlar ro'yxati eksport qilindi ({len(rows)} ta)",
    )
    return _xlsx_response(
        build_shops_report(rows), f"dokonlar_{utcnow().strftime('%Y-%m-%d')}.xlsx"
    )


@router.get("/super/shops/{sid}/export")
async def export_shop_detail(
    sid: str,
    request: Request = None,
    current: AdminAuth = Depends(get_current_super_admin),
):
    """Bitta do'konning qarzdorlari va qarzlari — Excel."""
    from app.utils.excel import build_shop_report

    shop = await Shop.get(_oid(sid, "Do'kon"))
    if not shop:
        raise HTTPException(404, "Do'kon topilmadi")

    from app.utils import reports

    client_rows, debt_rows = await reports.collect(shop)

    await audit.log_admin(
        current, "report.export", request=request,
        entity_type="shop", entity_id=shop.id, entity_label=shop.name, shop_id=shop.id,
        summary=f"«{shop.name}» hisoboti eksport qilindi ({len(debt_rows)} qarz)",
    )
    # Fayl alohida oqimda yasaladi — og'ir hisobot boshqa so'rovlarni bloklamaydi
    content = await asyncio.to_thread(build_shop_report, shop.name, client_rows, debt_rows)
    return _xlsx_response(content, reports.safe_filename(shop.name))
