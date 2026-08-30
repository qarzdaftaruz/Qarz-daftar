import asyncio
import logging
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from beanie.operators import In

from app.models import utcnow

logger = logging.getLogger(__name__)
UZ_TZ = pytz.timezone("Asia/Tashkent")
scheduler = AsyncIOScheduler(timezone=UZ_TZ)

ACTIVE_STATUSES = ["open", "partial", "overdue"]
UNPAID_STATUSES = ["open", "partial"]

# Bitta ishga tushishda ko'rib chiqiladigan maksimal qarzlar soni.
# Xotira himoyasi: baza o'sganda ham ish hajmi bashorat qilinadigan bo'ladi.
MAX_BATCH = 5000


# ─── Ommaviy eslatmalar uchun umumiy yordamchi ────────────────────────────────

async def _reminder_context(debts: list) -> tuple[dict, dict, dict]:
    """Qarzlar ro'yxati uchun mijoz/do'kon/foydalanuvchi jadvallari.

    TEZLIK: ilgari har bir guruh uchun alohida `Client.get` va `Shop.get`
    ketardi (N+1), ustiga har bir xabarda foydalanuvchini topish uchun
    yana bitta so'rov. 500 qarzdorga eslatma ≈ 1500 ta borish edi.
    Endi jami 3 ta so'rov.
    """
    from app.models import Shop, Client, ShopStatus
    from app.utils.helpers import resolve_debtor_users

    client_ids = list({d.client_id for d in debts})
    shop_ids = list({d.shop_id for d in debts})
    if not client_ids:
        return {}, {}, {}

    clients = {
        c.id: c for c in
        await Client.find(In(Client.id, client_ids), Client.status == "active").to_list()
    }
    shops = {
        s.id: s for s in
        await Shop.find(In(Shop.id, shop_ids), Shop.status == ShopStatus.ACTIVE).to_list()
    }
    users = await resolve_debtor_users([c.phone for c in clients.values()])
    return clients, shops, users


def _group_by_client_shop(debts: list) -> dict:
    grouped: dict = {}
    for d in debts:
        grouped.setdefault((d.client_id, d.shop_id), []).append(d)
    return grouped


def _recipient(client, users: dict):
    """Mijoz raqamiga mos bot foydalanuvchisi (raqam turli formatda bo'lishi mumkin)."""
    from app.utils.helpers import phone_variants

    for variant in phone_variants(client.phone):
        user = users.get(variant)
        if user:
            return user
    return None


# ─── Do'kondorga kunlik hisobot ───────────────────────────────────────────────

async def send_daily_reminders():
    """Belgilangan vaqtda do'kon egalariga kunlik hisobot."""
    from app.models import Shop, Debt, Client, User, ShopStatus
    from app.utils.helpers import format_money, local_day_bounds, esc, notify_telegram

    today_start, today_end = local_day_bounds()
    active_shops = await Shop.find(Shop.status == ShopStatus.ACTIVE).to_list()

    for shop in active_shops:
        try:
            today_debts = await Debt.find(
                Debt.shop_id == shop.id,
                In(Debt.status, UNPAID_STATUSES),
                Debt.due_date >= today_start,
                Debt.due_date <= today_end,
            ).to_list()

            overdue = await Debt.find(
                Debt.shop_id == shop.id, Debt.status == "overdue"
            ).count()

            if not (today_debts or overdue):
                continue

            owner = await User.get(shop.owner_id)
            if not owner or not owner.telegram_id or owner.is_blocked:
                continue

            # TEZLIK: umumiy qoldiq — bitta aggregation.
            # Ilgari do'konning BARCHA faol qarzlari xotiraga yuklanardi.
            rows = await Debt.get_motor_collection().aggregate([
                {"$match": {"shop_id": shop.id, "status": {"$in": ACTIVE_STATUSES}}},
                {"$group": {"_id": None, "total": {"$sum": "$remaining"}}},
            ]).to_list(length=1)
            remaining_total = rows[0]["total"] if rows else 0

            msg = f"☀️ <b>{esc(shop.name)}</b> — Kunlik hisobot\n" + "─" * 28 + "\n"
            if today_debts:
                # N+1 o'rniga: kerakli mijozlar bitta so'rovda
                shown = today_debts[:5]
                names = {
                    c.id: c.full_name for c in
                    await Client.find(In(Client.id, [d.client_id for d in shown])).to_list()
                }
                msg += f"\n⚠️ <b>Bugun muddati tugaydi: {len(today_debts)} ta</b>\n"
                for d in shown:
                    msg += f"  • {esc(names.get(d.client_id, '?'))} — {format_money(d.remaining)}\n"
                if len(today_debts) > 5:
                    msg += f"  … va yana {len(today_debts) - 5} ta\n"
            if overdue:
                msg += f"\n🔴 Muddati o'tgan: <b>{overdue} ta</b>\n"
            msg += f"\n📊 Umumiy qoldiq: <b>{format_money(remaining_total)}</b>"

            await notify_telegram(owner.telegram_id, msg)

        except Exception as e:      # noqa: BLE001
            logger.error("Kunlik eslatma (shop=%s): %s", shop.id, e)


# ─── Obuna: ogohlantirish va muddat nazorati ──────────────────────────────────

async def check_subscription_warnings():
    """Obuna tugashiga 3 kun qolganda ogohlantirish."""
    from app.models import Shop, User, ShopStatus
    from app.utils.helpers import days_left, esc, notify_telegram

    shops = await Shop.find(
        Shop.status == ShopStatus.ACTIVE, Shop.warning_sent == False  # noqa: E712
    ).to_list()

    for shop in shops:
        try:
            end = shop.subscription_end or shop.trial_end
            left = days_left(end)
            if left > 3:
                continue
            owner = await User.get(shop.owner_id)
            if not owner or not owner.telegram_id:
                continue

            # XATO TUZATILDI: `days_until` manfiy kunni 0 ga qisqartirgani uchun
            # allaqachon tugagan obuna ham "0 kundan so'ng tugaydi" deb chiqardi.
            if left < 0:
                when = "muddati allaqachon tugagan"
            elif left == 0:
                when = "<b>bugun</b> tugaydi"
            else:
                when = f"<b>{left} kun</b>dan so'ng tugaydi"

            sent = await notify_telegram(
                owner.telegram_id,
                f"⚠️ <b>Obuna haqida</b>\n\n"
                f"🏪 {esc(shop.name)}\n"
                f"📅 Obunangiz {when}.\n\n"
                f"Davom ettirish uchun admin bilan bog'laning.",
            )
            if sent:
                shop.warning_sent = True
                shop.updated_at = utcnow()
                await shop.save()
        except Exception as e:      # noqa: BLE001
            logger.error("Obuna ogohlantirishi (shop=%s): %s", shop.id, e)


async def expire_subscriptions():
    """Muddati tugagan do'konlarni avtomatik to'xtatish.

    XATO TUZATILDI: ilgari trial yoki obuna tugashi HECH QANDAY oqibatga
    olib kelmasdi — admin qo'lda bloklamaguncha do'kon cheksiz ishlayverardi.
    Ya'ni 7 kunlik sinovdan keyin ham tizimdan bepul foydalanish mumkin edi.
    """
    from app.config import settings
    from app.models import Shop, User, ShopStatus
    from app.core import audit
    from app.utils.helpers import esc, notify_telegram

    if not settings.SUBSCRIPTION_ENFORCE:
        return

    cutoff = utcnow() - timedelta(days=settings.SUBSCRIPTION_GRACE_DAYS)
    shops = await Shop.find({
        "status": {"$in": [ShopStatus.ACTIVE.value, ShopStatus.PENDING.value]},
        "$or": [
            {"subscription_end": {"$ne": None, "$lt": cutoff}},
            {"subscription_end": None, "trial_end": {"$lt": cutoff}},
        ],
    }).to_list()
    if not shops:
        return

    for shop in shops:
        try:
            now = utcnow()
            shop.status = ShopStatus.BLOCKED
            shop.block_reason = "Obuna muddati tugadi"
            shop.expired_at = now
            shop.warning_sent = False      # uzaytirilgach yana ogohlantirilsin
            shop.updated_at = now
            await shop.save()

            owner = await User.get(shop.owner_id)
            if owner and owner.telegram_id:
                await notify_telegram(
                    owner.telegram_id,
                    f"⛔️ <b>Obuna muddati tugadi</b>\n\n"
                    f"🏪 {esc(shop.name)}\n\n"
                    f"Do'kon vaqtincha to'xtatildi. Ma'lumotlaringiz saqlanib turibdi — "
                    f"davom ettirish uchun admin bilan bog'laning.",
                )
            await audit.log(
                "shop.expired", actor_type="system", actor_name="Tizim",
                entity_type="shop", entity_id=shop.id, entity_label=shop.name,
                shop_id=shop.id,
                summary=f"Do'kon «{shop.name}» obuna muddati tugagani uchun avtomatik to'xtatildi",
            )
        except Exception as e:      # noqa: BLE001
            logger.error("Obuna muddati (shop=%s): %s", shop.id, e)

    logger.info("%s ta do'kon obuna muddati tugagani uchun to'xtatildi", len(shops))


# ─── Qarz holatini yangilash ──────────────────────────────────────────────────

async def update_overdue():
    """Muddati o'tgan qarzlarni 'overdue' ga o'tkazish (bitta so'rovda)."""
    from app.models import Debt

    now = utcnow()
    res = await Debt.get_motor_collection().update_many(
        {
            "status": {"$in": UNPAID_STATUSES},
            "due_date": {"$ne": None, "$lt": now},
        },
        {"$set": {"status": "overdue", "updated_at": now}},
    )
    if res.modified_count:
        logger.info("%s ta qarz 'overdue' holatiga o'tdi", res.modified_count)
    return res.modified_count


# ─── Tozalash ─────────────────────────────────────────────────────────────────

CLEANUP_BATCH = 1000


async def archive_cleanup():
    """Eski yopiq qarzlarni va ularning to'lovlarini tozalash.

    Bo'laklab bajariladi: ilgari barcha eski qarzlar bir vaqtda xotiraga
    yuklanib, bitta ulkan `$in` so'rovi yasalardi. Bir necha yildan keyin
    bu yuz minglab ID ga aylanadi — MongoDB'ning 16 MB so'rov chegarasiga
    urilib, tozalash butunlay ishlamay qolardi.
    """
    from app.models import Debt, Payment, AppSettings

    s = await AppSettings.find_one()
    months = s.archive_duration_months if s else 6
    cutoff = utcnow() - timedelta(days=months * 30)

    total = 0
    while True:
        old = await Debt.find(
            In(Debt.status, ["closed", "archived"]), Debt.updated_at < cutoff
        ).limit(CLEANUP_BATCH).to_list()
        if not old:
            break

        ids = [d.id for d in old]
        await Payment.get_motor_collection().delete_many({"debt_id": {"$in": ids}})
        await Debt.get_motor_collection().delete_many({"_id": {"$in": ids}})
        total += len(ids)

        if len(old) < CLEANUP_BATCH:
            break
        # Boshqa so'rovlar navbat kutib qolmasin
        await asyncio.sleep(0)

    if total:
        logger.info("%s ta eski qarz tozalandi", total)


async def purge_deleted_shops():
    """O'chirilgan do'konlarni muddat tugagach butunlay yo'q qilish.

    Yumshoq o'chirilgan do'kon SHOP_PURGE_DAYS kun saqlanadi — shu vaqt
    ichida admin uni qaytarishi mumkin. Muddat o'tgach ma'lumot o'chadi.
    """
    from app.config import settings
    from app.models import Shop, ShopStatus
    from app.api.admin import purge_shop_data
    from app.core import audit

    cutoff = utcnow() - timedelta(days=settings.SHOP_PURGE_DAYS)
    shops = await Shop.find(
        Shop.status == ShopStatus.DELETED, Shop.deleted_at < cutoff
    ).to_list()
    if not shops:
        return

    for shop in shops:
        try:
            counts = await purge_shop_data(shop.id)
            name, deleted_by = shop.name, shop.deleted_by
            await shop.delete()
            await audit.log(
                "shop.purge", actor_type="system", actor_name="Tizim",
                entity_type="shop", entity_label=name,
                summary=(
                    f"Do'kon «{name}» {settings.SHOP_PURGE_DAYS} kunlik muddat tugagach "
                    f"avtomatik yo'q qilindi ({counts['clients']} mijoz, {counts['debts']} qarz). "
                    f"O'chirgan: {deleted_by or '—'}"
                ),
                meta=counts,
            )
            logger.info("Do'kon avtomatik yo'q qilindi: %s", name)
        except Exception as e:      # noqa: BLE001
            logger.error("Do'konni tozalashda xato (shop=%s): %s", shop.id, e)


# ─── Qarzdorga eslatma: muddat yaqinlashdi ────────────────────────────────────

async def send_due_reminders():
    """«Bugun/ertaga muddat tugaydi» eslatmasi.

    Ilgari faqat ERTANGI kun tekshirilardi. Natijada bugun yozilgan va
    bugun muddati tugaydigan qarz eslatmasiz qolardi. Endi oyna
    «hozirdan ertangi kun oxirigacha».
    """
    from app.config import settings
    from app.models import Debt
    from app.utils import reminders
    from app.utils.helpers import local_day_bounds, send_to_user

    if not settings.DUE_REMINDER_ENABLED:
        return

    now = utcnow()
    today_end = local_day_bounds()[1]
    tomorrow_end = local_day_bounds(offset_days=1)[1]

    debts = await Debt.find(
        In(Debt.status, UNPAID_STATUSES),
        Debt.due_date >= now,
        Debt.due_date <= tomorrow_end,
        Debt.due_reminder_sent == False,              # noqa: E712
    ).limit(MAX_BATCH).to_list()
    if not debts:
        return

    clients, shops, users = await _reminder_context(debts)
    sent_ids: list = []

    for (client_id, shop_id), items in _group_by_client_shop(debts).items():
        try:
            shop = shops.get(shop_id)
            client = clients.get(client_id)
            if not shop or not client:
                continue

            user = _recipient(client, users)
            if not user:
                # Qarzdor botga ulanmagan — keyinchalik SMS shu yerdan ketadi
                continue

            total = sum(d.remaining for d in items)
            is_today = any(d.due_date and d.due_date <= today_end for d in items)
            ok = await send_to_user(
                user, reminders.due_soon_message(shop.name, items, total, today=is_today)
            )
            if ok:
                sent_ids.extend(d.id for d in items)
            await asyncio.sleep(settings.BULK_SEND_DELAY)
        except Exception as e:      # noqa: BLE001
            logger.error("Qarzdor eslatmasi (client=%s): %s", client_id, e)

    if sent_ids:
        # Takror yubormaslik uchun belgilaymiz
        await Debt.get_motor_collection().update_many(
            {"_id": {"$in": sent_ids}}, {"$set": {"due_reminder_sent": True}}
        )
        logger.info("Muddat eslatmasi: %s ta qarz bo'yicha yuborildi", len(sent_ids))


# ─── Qarzdorga eslatma: muddat o'tdi (HAR KUNI) ───────────────────────────────

async def send_overdue_reminders():
    """Muddati o'tgan qarzlar uchun qarzdorga KUNLIK ogohlantirish.

    Ilgari muddat o'tgach qarzdorga umuman xabar ketmasdi — faqat
    do'kondor ko'rardi. Endi qarz to'lanmaguncha har kuni eslatma
    boradi: qancha qarzi bor va muddat qachon tugagani.

    Takrorlanmaslik kafolati: `overdue_notified_at` bugungi kun
    boshidan oldin bo'lgan qarzlargina olinadi — server qayta ishga
    tushsa ham bir kunda ikki marta yubormaydi.
    """
    from app.config import settings
    from app.models import Debt
    from app.utils import reminders
    from app.utils.helpers import local_day_bounds, send_to_user

    if not settings.OVERDUE_REMINDER_ENABLED:
        return

    # Holatlar yangi bo'lishi shart — soatlik vazifa bilan poyga bo'lmasin
    await update_overdue()

    now = utcnow()
    today_start = local_day_bounds()[0]

    query: dict = {
        "status": "overdue",
        "$or": [
            {"overdue_notified_at": None},
            {"overdue_notified_at": {"$lt": today_start}},
        ],
    }
    # Umidsiz eski qarzlar bo'yicha yillab xabar yuborilmaydi —
    # aks holda qarzdor botni bloklaydi va boshqa hech narsa yetib bormaydi
    if settings.OVERDUE_REMINDER_MAX_DAYS > 0:
        query["due_date"] = {
            "$gte": now - timedelta(days=settings.OVERDUE_REMINDER_MAX_DAYS)
        }

    # ADOLAT: hali xabar ketmagan qarzlar (`overdue_notified_at` yo'q)
    # birinchi keladi. Qarzlar soni bir kunlik chegaradan oshsa ham,
    # doim bir xil qarzlar tashlab ketilmaydi — navbat aylanadi.
    debts = await Debt.find(query).sort("overdue_notified_at").limit(MAX_BATCH).to_list()
    if not debts:
        return

    clients, shops, users = await _reminder_context(debts)

    # Muddati kelmagan / muddatsiz qarzlar ham xabarda ko'rsatiladi —
    # qarzdor umumiy qoldig'ini bir qarashda ko'radi
    others: dict = {}
    if clients:
        for d in await Debt.find(
            In(Debt.client_id, list(clients)), In(Debt.status, UNPAID_STATUSES)
        ).limit(MAX_BATCH).to_list():
            others.setdefault((d.client_id, d.shop_id), []).append(d)

    notified_ids: list = []
    sent_count = 0

    for (client_id, shop_id), items in _group_by_client_shop(debts).items():
        try:
            shop = shops.get(shop_id)
            client = clients.get(client_id)
            if not shop or not client:
                continue

            user = _recipient(client, users)
            if not user:
                continue

            day = max((d.overdue_notice_count for d in items), default=0) + 1
            ok = await send_to_user(user, reminders.overdue_message(
                shop.name, items, others.get((client_id, shop_id), []), day=day,
            ))
            if ok:
                notified_ids.extend(d.id for d in items)
                sent_count += 1
            await asyncio.sleep(settings.BULK_SEND_DELAY)
        except Exception as e:      # noqa: BLE001
            logger.error("Muddat o'tgan eslatmasi (client=%s): %s", client_id, e)

    if notified_ids:
        await Debt.get_motor_collection().update_many(
            {"_id": {"$in": notified_ids}},
            {"$set": {"overdue_notified_at": now}, "$inc": {"overdue_notice_count": 1}},
        )
    logger.info(
        "Muddati o'tgan qarz eslatmasi: %s qarzdorga, %s ta qarz bo'yicha",
        sent_count, len(notified_ids),
    )


# ─── Oylik Excel hisobot ──────────────────────────────────────────────────────

def local_month_start() -> datetime:
    """Joriy oyning 1-sanasi (naive-UTC) — takror yuborishni aniqlash uchun."""
    from app.utils.helpers import to_local, to_naive_utc

    local = to_local(utcnow())
    return to_naive_utc(UZ_TZ.localize(datetime(local.year, local.month, 1)))


async def send_monthly_reports():
    """Har oyning 1-sanasida do'kondorlarga Excel hisobot.

    SERVER YUKI: do'konlar ketma-ket, orasida tanaffus bilan qayta ishlanadi.
    Barchasini bir vaqtda yasash Railway konteynerining xotirasini to'ldiradi.
    """
    from app.config import settings
    from app.models import Shop, User, ShopStatus
    from app.utils import reports

    if not settings.MONTHLY_REPORT_ENABLED:
        return

    shops = await Shop.find(Shop.status == ShopStatus.ACTIVE).to_list()
    month_start = local_month_start()
    sent = skipped = failed = 0

    for shop in shops:
        try:
            # Server qayta ishga tushsa ham shu oyda ikkinchi marta yubormaymiz
            if shop.last_report_at and shop.last_report_at >= month_start:
                skipped += 1
                continue

            owner = await User.get(shop.owner_id)
            if not owner or not owner.telegram_id or owner.is_blocked:
                skipped += 1
                continue

            ok = await reports.send_to_owner(shop, owner.telegram_id, caption_prefix="🗓 Oylik")
            if ok:
                shop.last_report_at = utcnow()
                await shop.save()
                sent += 1
            else:
                skipped += 1

            # Telegram limitlari va CPU uchun tanaffus
            await asyncio.sleep(settings.BULK_SEND_DELAY)
        except Exception as e:      # noqa: BLE001
            failed += 1
            logger.error("Oylik hisobot (shop=%s): %s", shop.id, e)

    logger.info("Oylik hisobotlar: %s yuborildi, %s o'tkazildi, %s xato", sent, skipped, failed)


# ─── Bot webhook nazorati ─────────────────────────────────────────────────────

async def check_webhook():
    """Webhook Telegram tomonida joyidami — yo'qolgan bo'lsa tiklaydi.

    Bot jim qolib qolgani bir necha kun sezilmasligi mumkin: chiquvchi
    eslatmalar ishlayveradi, faqat KELUVCHI xabarlar yo'qoladi. Shu
    tekshiruv nosozlikni 15 daqiqada topadi va logga ochiq yozadi.
    """
    from app.bot.main import ensure_webhook

    await ensure_webhook()


# ─── Rejalashtirish ───────────────────────────────────────────────────────────

def setup_scheduler(hour: int = 9, minute: int = 0):
    from app.config import settings

    hour = max(0, min(23, int(hour)))
    minute = max(0, min(59, int(minute)))

    def job(fn, job_id, trigger, grace=3600):
        # max_instances=1 — oldingi ishga tushish tugamagan bo'lsa yangisi boshlanmaydi
        scheduler.add_job(fn, trigger, id=job_id, replace_existing=True,
                          misfire_grace_time=grace, coalesce=True, max_instances=1)

    job(send_daily_reminders,        "daily",    CronTrigger(hour=hour, minute=minute, timezone=UZ_TZ))
    job(check_subscription_warnings, "warnings", CronTrigger(hour=8, minute=0, timezone=UZ_TZ))
    job(update_overdue,              "overdue",  CronTrigger(minute=0, timezone=UZ_TZ), grace=600)
    job(archive_cleanup,             "cleanup",  CronTrigger(hour=0, minute=30, timezone=UZ_TZ))

    # Obuna muddati tugagan do'konlarni to'xtatish (kuniga ikki marta —
    # kechqurun tugagan obuna ertalabgacha ochiq qolib ketmasin)
    job(expire_subscriptions,        "expire",   CronTrigger(hour="7,19", minute=5, timezone=UZ_TZ))

    # O'chirilgan do'konlarni muddat tugagach tozalash
    job(purge_deleted_shops,         "purge",    CronTrigger(hour=1, minute=0, timezone=UZ_TZ))

    # Qarzdorga «muddati o'tdi» — HAR KUNI, to'lanmaguncha
    job(send_overdue_reminders,      "overdue_reminder",
        CronTrigger(hour=settings.OVERDUE_REMINDER_HOUR,
                    minute=settings.OVERDUE_REMINDER_MINUTE, timezone=UZ_TZ))

    # Qarzdorga «bugun/ertaga muddat tugaydi»
    job(send_due_reminders,          "due_reminder",
        CronTrigger(hour=settings.DUE_REMINDER_HOUR, minute=30, timezone=UZ_TZ))

    # Bot webhook'i joyidami (deploy paytidagi poyga holatiga qarshi zaxira)
    if settings.webhook_full_url:
        job(check_webhook, "webhook_check", CronTrigger(minute="*/15", timezone=UZ_TZ), grace=300)

    # Har oyning 1-sanasi — Excel hisobotlar (og'ir vazifa, kengroq grace)
    job(send_monthly_reports,        "monthly_report",
        CronTrigger(day=1, hour=settings.MONTHLY_REPORT_HOUR, minute=0, timezone=UZ_TZ),
        grace=6 * 3600)

    if not scheduler.running:
        scheduler.start()
    logger.info(
        "Scheduler ishga tushdi (do'kondor hisoboti %02d:%02d, muddat o'tgan eslatmasi %02d:%02d, "
        "muddat eslatmasi %02d:30, oylik hisobot 1-sana %02d:00 — Toshkent)",
        hour, minute, settings.OVERDUE_REMINDER_HOUR, settings.OVERDUE_REMINDER_MINUTE,
        settings.DUE_REMINDER_HOUR, settings.MONTHLY_REPORT_HOUR,
    )


def reschedule_daily(hour: int, minute: int):
    """Admin paneldan eslatma vaqti o'zgarganda darhol qo'llash.

    Ilgari o'zgarish faqat serverni qayta ishga tushirgandan keyin ta'sir qilardi.
    """
    hour = max(0, min(23, int(hour)))
    minute = max(0, min(59, int(minute)))
    if scheduler.running:
        scheduler.reschedule_job("daily", trigger=CronTrigger(hour=hour, minute=minute, timezone=UZ_TZ))
        logger.info("Kunlik eslatma vaqti yangilandi: %02d:%02d", hour, minute)
