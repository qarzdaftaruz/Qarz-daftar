import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from aiogram.types import Update

from app.config import settings
from app.database import init_db, close_db
from app.api import router
from app.bot.main import bot, dp, setup_bot
from app.core.middleware import (
    SecurityHeadersMiddleware, BodySizeLimitMiddleware, GlobalRateLimitMiddleware,
)
from app.core.scheduler import setup_scheduler, scheduler
from app.core import tasks

logging.basicConfig(
    level=logging.INFO if settings.is_production else logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s — %(message)s",
)
# Shovqinli kutubxonalarni tinchlantiramiz
for noisy in ("pymongo", "motor", "httpx", "aiogram.event", "apscheduler.executors"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

_polling_task: asyncio.Task | None = None


async def _warn_expired_shops() -> None:
    """Obuna nazorati birinchi marta yoqilganda nima bo'lishini oldindan ko'rsatadi.

    Bu tekshiruv hech narsani o'zgartirmaydi — faqat sanaydi. Deploy'dan
    keyin loglarda "N ta do'kon to'xtatiladi" degan qatorni ko'rsangiz va
    bu kutilmagan bo'lsa, vazifa ishlashidan oldin (07:05 / 19:05) muddatni
    uzaytiring yoki SUBSCRIPTION_ENFORCE=false qo'ying.
    """
    if not settings.SUBSCRIPTION_ENFORCE:
        logger.warning(
            "[obuna] SUBSCRIPTION_ENFORCE=false — muddati tugagan do'konlar "
            "to'xtatilmaydi, ya'ni trial tugagach ham foydalanish mumkin"
        )
        return
    try:
        from datetime import timedelta
        from app.models import Shop, ShopStatus, utcnow

        cutoff = utcnow() - timedelta(days=settings.SUBSCRIPTION_GRACE_DAYS)
        n = await Shop.find({
            "status": {"$in": [ShopStatus.ACTIVE.value, ShopStatus.PENDING.value]},
            "$or": [
                {"subscription_end": {"$ne": None, "$lt": cutoff}},
                {"subscription_end": None, "trial_end": {"$lt": cutoff}},
            ],
        }).count()
        if n:
            logger.warning(
                "[obuna] %s ta do'kon muddati tugagan — keyingi tekshiruvda "
                "(07:05 / 19:05, Toshkent) avtomatik to'xtatiladi va egalariga xabar ketadi",
                n,
            )
    except Exception as e:      # noqa: BLE001
        logger.warning("[obuna] muddat tekshiruvi bajarilmadi: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _polling_task
    logger.info("Tizim ishga tushmoqda… (env=%s)", settings.ENVIRONMENT)

    # Xavfsizlik holati — deploy'dan keyin loglardan bir qarashda ko'rinadi
    for level, message in settings.security_report():
        {"XATAR": logger.error, "OGOH": logger.warning}.get(level, logger.info)(
            "[xavfsizlik/%s] %s", level, message
        )

    await init_db()
    # Fon navbati — Telegram xabarlari so'rovni kutkazmasin
    await tasks.start()
    setup_bot()

    webhook_url = settings.webhook_full_url
    if webhook_url:
        await bot.set_webhook(
            webhook_url,
            drop_pending_updates=True,
            secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
            allowed_updates=dp.resolve_used_update_types(),
        )
        logger.info("Webhook o'rnatildi: %s", webhook_url)
    else:
        if settings.is_production:
            logger.warning(
                "WEBHOOK_URL yo'q — polling rejimi ishlatilmoqda. "
                "Railway'da bir nechta replika bo'lsa bot xabarlarni takrorlaydi!"
            )
        await bot.delete_webhook(drop_pending_updates=True)
        _polling_task = asyncio.create_task(
            dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        )
        logger.info("Polling rejimi ishga tushdi")

    from app.models import AppSettings
    s = await AppSettings.find_one()
    setup_scheduler(s.reminder_hour if s else 9, s.reminder_minute if s else 0)

    await _warn_expired_shops()

    try:
        yield
    finally:
        logger.info("To'xtatilmoqda…")
        if scheduler.running:
            scheduler.shutdown(wait=False)

        # Navbatdagi xabarlar yuborilib bo'lsin (qisqa muddat kutamiz)
        await tasks.stop()

        if _polling_task and not _polling_task.done():
            await dp.stop_polling()
            _polling_task.cancel()
            try:
                await _polling_task
            except (asyncio.CancelledError, Exception):   # noqa: B014
                pass

        if webhook_url:
            try:
                await bot.delete_webhook()
            except Exception as e:      # noqa: BLE001
                logger.warning("Webhook o'chirilmadi: %s", e)

        await bot.session.close()
        await close_db()
        logger.info("To'xtatildi")


app = FastAPI(
    title="Qarz Daftar API",
    version="2.1.0",
    lifespan=lifespan,
    # Production'da API hujjatlari yopiq — endpointlar ro'yxati oshkor bo'lmasin
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

# ─── Middleware (teskari tartibda bajariladi) ────────────────────────────────

if settings.is_production and settings.allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(GlobalRateLimitMiddleware)
app.add_middleware(BodySizeLimitMiddleware, max_body=settings.MAX_BODY_SIZE)

# CORS — faqat aniq originlar. Ilgari "*" + allow_credentials ishlatilgan edi;
# bu ham xavfli, ham brauzerlar tomonidan rad etiladi.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,          # token Authorization header'da keladi, cookie yo'q
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    max_age=600,
)

app.include_router(router)


# ─── Xatoliklarni bir xil formatda qaytarish ─────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Yuborilgan ma'lumot noto'g'ri"},
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    """Ichki xato tafsilotlari (stack trace, baza xabarlari) foydalanuvchiga chiqmaydi."""
    logger.exception("Kutilmagan xato: %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Serverda kutilmagan xato yuz berdi"},
    )


# ─── Telegram webhook ────────────────────────────────────────────────────────

@app.post(settings.WEBHOOK_PATH, include_in_schema=False)
async def webhook(request: Request):
    """Telegram'dan kelgan update.

    `X-Telegram-Bot-Api-Secret-Token` tekshiriladi — bu bo'lmasa
    istalgan odam soxta xabar yuborib bot nomidan ish qildira olardi.
    """
    secret = request.headers.get("x-telegram-bot-api-secret-token", "")
    if secret != settings.TELEGRAM_WEBHOOK_SECRET:
        logger.warning("Webhook: noto'g'ri secret token")
        return Response(status_code=status.HTTP_403_FORBIDDEN)

    try:
        data = await request.json()
        update = Update.model_validate(data, context={"bot": bot})
    except Exception:      # noqa: BLE001
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    # Telegram 60 soniyada javob kutadi; ishlov fon vazifasida ketadi
    await dp.feed_update(bot, update)
    return {"ok": True}


# ─── Health ──────────────────────────────────────────────────────────────────

# Bazani har bir healthcheck'da urintirmaymiz: Railway bu manzilni
# tez-tez chaqiradi va har bir "ping" Atlas'ga alohida borish demak.
# Muvaffaqiyatli natija bir necha soniya keshlanadi; xato bo'lsa
# keshlanmaydi — nosozlik darhol ko'rinadi.
_HEALTH_TTL = 5.0
_health_cache: tuple[float, bool] = (0.0, False)


async def _db_ok() -> bool:
    global _health_cache
    import time

    expires, value = _health_cache
    now = time.monotonic()
    if value and expires > now:
        return True
    try:
        from app.database import get_client
        await get_client().admin.command("ping")
        _health_cache = (now + _HEALTH_TTL, True)
        return True
    except Exception:      # noqa: BLE001
        _health_cache = (0.0, False)
        return False


@app.get("/health", include_in_schema=False)
@app.get("/healthz", include_in_schema=False)
async def health():
    """Railway healthcheck — bazaga ulanish ham tekshiriladi."""
    db_ok = await _db_ok()
    return JSONResponse(
        {"status": "ok" if db_ok else "degraded", "db": db_ok, "version": app.version},
        status_code=200 if db_ok else 503,
    )


@app.get("/", include_in_schema=False)
async def root():
    return {"service": "Qarz Daftar API", "version": app.version, "docs": None if settings.is_production else "/docs"}
