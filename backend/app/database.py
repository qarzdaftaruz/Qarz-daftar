import logging
import secrets
from typing import Optional

import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure, DuplicateKeyError
from beanie import init_beanie

from app.config import settings
from app.models import ALL_MODELS

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None


def _client_kwargs() -> dict:
    """MongoDB Atlas uchun ishonchli ulanish parametrlari."""
    kwargs = dict(
        maxPoolSize=settings.MONGO_MAX_POOL_SIZE,
        minPoolSize=settings.MONGO_MIN_POOL_SIZE,
        serverSelectionTimeoutMS=settings.MONGO_TIMEOUT_MS,
        connectTimeoutMS=settings.MONGO_TIMEOUT_MS,
        socketTimeoutMS=settings.MONGO_TIMEOUT_MS * 3,
        retryWrites=True,
        retryReads=True,
        appname="qarzdaftar",
        uuidRepresentation="standard",
    )
    # Atlas (mongodb+srv://) — TLS sertifikat zanjirini certifi bilan beramiz,
    # aks holda ba'zi konteynerlarda "certificate verify failed" xatosi chiqadi.
    if settings.MONGODB_URL.startswith("mongodb+srv://") or "mongodb.net" in settings.MONGODB_URL:
        kwargs["tls"] = True
        kwargs["tlsCAFile"] = certifi.where()
    return kwargs


def get_client() -> AsyncIOMotorClient:
    if _client is None:
        raise RuntimeError("MongoDB hali ulanmagan")
    return _client


async def init_db():
    global _client
    _client = AsyncIOMotorClient(settings.MONGODB_URL, **_client_kwargs())

    # Ulanishni darhol tekshiramiz — noto'g'ri URL bilan "jim" ishga tushmasin
    await _client.admin.command("ping")

    await init_beanie(database=_client[settings.DB_NAME], document_models=ALL_MODELS)
    logger.info("MongoDB ulandi: db=%s", settings.DB_NAME)

    await _ensure_indexes()
    await _seed_defaults()


async def close_db():
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB ulanishi yopildi")


# ─── Indekslar ────────────────────────────────────────────────────────────────

async def _create(collection, keys, **opts):
    """Indeks yaratish — muammo bo'lsa ilova baribir ishga tushadi.

    Masalan mavjud bazada dublikat yozuvlar bo'lsa, unique indeks
    yaratilmaydi. Bu sabab bilan butun tizim ishlamay qolmasligi kerak —
    ogohlantirish logga yoziladi va davom etamiz.
    """
    try:
        await collection.create_index(keys, **opts)
        return
    except (OperationFailure, DuplicateKeyError) as e:
        # TTL muddati o'zgargan bo'lsa — indeksni qayta yaratmasdan yangilaymiz
        # (masalan AUDIT_RETENTION_DAYS 365 dan 180 ga o'zgarganda)
        ttl = opts.get("expireAfterSeconds")
        name = opts.get("name")
        if ttl is not None and name and getattr(e, "code", None) == 85:
            try:
                await collection.database.command({
                    "collMod": collection.name,
                    "index": {"name": name, "expireAfterSeconds": ttl},
                })
                logger.info("TTL indeks yangilandi: %s.%s -> %s soniya", collection.name, name, ttl)
                return
            except OperationFailure as mod_err:
                e = mod_err

        logger.warning(
            "Indeks yaratilmadi (%s.%s): %s — bazadagi dublikatlarni tekshiring",
            collection.name, opts.get("name", keys), e,
        )


async def _ensure_indexes():
    """Ma'lumotlar hajmi oshganda so'rovlar sekinlashmasligi uchun indekslar."""
    from app.models import (
        User, Shop, Client, Debt, Payment, PromoCode, SupportMessage, AdminAuth
    )

    # Unikal indekslar — dublikat yozuvlarning oldini oladi
    await _create(User.get_motor_collection(), [("telegram_id", ASCENDING)], unique=True, name="uniq_telegram_id")
    await _create(User.get_motor_collection(), [("phone", ASCENDING)], name="idx_user_phone")
    await _create(User.get_motor_collection(), [("extra_phones", ASCENDING)], name="idx_user_extra_phones")

    await _create(AdminAuth.get_motor_collection(), [("username", ASCENDING)], unique=True, name="uniq_admin_username")

    await _create(PromoCode.get_motor_collection(), [("code", ASCENDING)], unique=True, name="uniq_promo_code")

    await _create(Shop.get_motor_collection(), [("owner_id", ASCENDING), ("status", ASCENDING)], name="idx_shop_owner_status")
    await _create(Shop.get_motor_collection(), [("status", ASCENDING), ("created_at", DESCENDING)], name="idx_shop_status_created")
    # O'chirilgan do'konlarni tozalash uchun
    await _create(Shop.get_motor_collection(), [("status", ASCENDING), ("deleted_at", ASCENDING)], name="idx_shop_deleted")

    # Bitta do'konda bitta raqam — faqat faol mijozlar uchun (partial unique)
    await _create(
        Client.get_motor_collection(),
        [("shop_id", ASCENDING), ("phone", ASCENDING)],
        unique=True,
        name="uniq_active_client_phone",
        partialFilterExpression={"status": "active"},
    )
    await _create(Client.get_motor_collection(), [("phone", ASCENDING), ("status", ASCENDING)], name="idx_client_phone_status")
    # Tizimdagi eng ko'p ishlatiladigan so'rov: do'konning faol mijozlari
    # (mijozlar ro'yxati, dashboard, statistika, eksport — hammasi shundan boshlanadi)
    await _create(
        Client.get_motor_collection(),
        [("shop_id", ASCENDING), ("status", ASCENDING), ("full_name", ASCENDING)],
        name="idx_client_shop_status_name",
    )

    await _create(Debt.get_motor_collection(), [("shop_id", ASCENDING), ("status", ASCENDING)], name="idx_debt_shop_status")
    await _create(Debt.get_motor_collection(), [("client_id", ASCENDING), ("status", ASCENDING)], name="idx_debt_client_status")
    await _create(Debt.get_motor_collection(), [("status", ASCENDING), ("due_date", ASCENDING)], name="idx_debt_status_due")
    await _create(Debt.get_motor_collection(), [("shop_id", ASCENDING), ("created_at", DESCENDING)], name="idx_debt_shop_created")

    await _create(Payment.get_motor_collection(), [("debt_id", ASCENDING)], name="idx_payment_debt")
    await _create(Payment.get_motor_collection(), [("client_id", ASCENDING), ("created_at", DESCENDING)], name="idx_payment_client_created")
    await _create(Payment.get_motor_collection(), [("shop_id", ASCENDING)], name="idx_payment_shop")

    await _create(SupportMessage.get_motor_collection(), [("is_read", ASCENDING), ("created_at", DESCENDING)], name="idx_support_read_created")
    await _create(SupportMessage.get_motor_collection(), [("admin_message_id", ASCENDING)], name="idx_support_admin_msg")

    # Audit log — qidiruv indekslari + TTL (eski yozuvlar avtomatik o'chadi)
    from app.models import AuditLog
    from app.core.audit import AUDIT_RETENTION_DAYS

    await _create(AuditLog.get_motor_collection(), [("action", ASCENDING), ("created_at", DESCENDING)], name="idx_audit_action")
    await _create(AuditLog.get_motor_collection(), [("actor_name", ASCENDING), ("created_at", DESCENDING)], name="idx_audit_actor")
    await _create(AuditLog.get_motor_collection(), [("shop_id", ASCENDING), ("created_at", DESCENDING)], name="idx_audit_shop")
    await _create(
        AuditLog.get_motor_collection(), [("created_at", ASCENDING)],
        name="ttl_audit", expireAfterSeconds=AUDIT_RETENTION_DAYS * 86400,
    )

    logger.info("Indekslar tekshirildi")


# ─── Boshlang'ich ma'lumotlar ─────────────────────────────────────────────────

async def _seed_defaults():
    from app.models import AdminAuth, AppSettings
    from app.core.security import get_password_hash

    generated: list[tuple[str, str]] = []

    async def _ensure_admin(username: str, password: str, telegram_id, is_super: bool):
        """Hisob bo'lmasa yaratadi. Parol berilmagan bo'lsa — tasodifiy generatsiya."""
        existing = await AdminAuth.find_one(AdminAuth.username == username)
        if existing:
            return existing
        pwd = password
        if not pwd:
            pwd = secrets.token_urlsafe(16)
            generated.append((username, pwd))
        await AdminAuth(
            username=username,
            hashed_password=get_password_hash(pwd),
            telegram_id=telegram_id,
            is_super=is_super,
            must_change_password=not password,
        ).insert()
        logger.info("Hisob yaratildi: %s (super=%s)", username, is_super)
        return await AdminAuth.find_one(AdminAuth.username == username)

    super_tid = settings.super_admin_ids[0] if settings.super_admin_ids else settings.ADMIN_TELEGRAM_ID

    # SuperAdmin — to'liq huquq
    await _ensure_admin(
        settings.SUPER_ADMIN_USERNAME, settings.SUPER_ADMIN_PASSWORD, super_tid, True
    )
    # Oddiy admin (super admindan farq qilsa)
    if settings.ADMIN_USERNAME != settings.SUPER_ADMIN_USERNAME:
        await _ensure_admin(
            settings.ADMIN_USERNAME, settings.ADMIN_PASSWORD, settings.ADMIN_TELEGRAM_ID, False
        )

    # telegram_id ni env bilan sinxronlaymiz (bot orqali parol tiklash uchun).
    # DIQQAT: parol hech qachon env'dan qayta yozilmaydi — panelda o'zgartirilgani saqlanadi.
    reg = await AdminAuth.find_one(AdminAuth.username == settings.ADMIN_USERNAME)
    if reg and reg.username != settings.SUPER_ADMIN_USERNAME:
        if reg.is_super or reg.telegram_id != settings.ADMIN_TELEGRAM_ID:
            reg.is_super = False
            reg.telegram_id = settings.ADMIN_TELEGRAM_ID
            await reg.save()

    sa = await AdminAuth.find_one(AdminAuth.username == settings.SUPER_ADMIN_USERNAME)
    if sa and (sa.telegram_id != super_tid or not sa.is_super):
        sa.telegram_id = super_tid
        sa.is_super = True
        await sa.save()

    if not await AppSettings.find_one():
        await AppSettings(
            reminder_hour=settings.REMINDER_HOUR,
            reminder_minute=settings.REMINDER_MINUTE,
            archive_duration_months=settings.ARCHIVE_DURATION_MONTHS,
            admin_telegram_id=settings.ADMIN_TELEGRAM_ID,
        ).insert()
        logger.info("Tizim sozlamalari yaratildi")

    # Generatsiya qilingan parollar faqat bir marta — logda ko'rsatiladi
    for username, pwd in generated:
        logger.warning(
            "!!! '%s' uchun vaqtinchalik parol yaratildi: %s — birinchi kirishdan keyin ALBATTA o'zgartiring !!!",
            username, pwd,
        )
