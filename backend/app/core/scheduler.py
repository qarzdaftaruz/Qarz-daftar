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
                In(Debt.status, ["open", "partial"]),
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

            all_active = await Debt.find(
                Debt.shop_id == shop.id, In(Debt.status, ACTIVE_STATUSES)
            ).to_list()
            remaining_total = sum(d.remaining for d in all_active)

            msg = f"☀️ <b>{esc(shop.name)}</b> — Kunlik hisobot\n" + "─" * 28 + "\n"
            if today_debts:
                msg += f"\n⚠️ <b>Bugun muddati tugaydi: {len(today_debts)} ta</b>\n"
                for d in today_debts[:5]:
                    c = await Client.get(d.client_id)
                    msg += f"  • {esc(c.full_name) if c else '?'} — {format_money(d.remaining)}\n"
                if len(today_debts) > 5:
                    msg += f"  … va yana {len(today_debts) - 5} ta\n"
            if overdue:
                msg += f"\n🔴 Muddati o'tgan: <b>{overdue} ta</b>\n"
            msg += f"\n📊 Umumiy qoldiq: <b>{format_money(remaining_total)}</b>"

            await notify_telegram(owner.telegram_id, msg)

        except Exception as e:      # noqa: BLE001
            logger.error("Kunlik eslatma (shop=%s): %s", shop.id, e)


async def check_subscription_warnings():
    """Obuna tugashiga 3 kun qolganda ogohlantirish."""
    from app.models import Shop, User, ShopStatus
    from app.utils.helpers import days_until, esc, notify_telegram

    shops = await Shop.find(
        Shop.status == ShopStatus.ACTIVE, Shop.warning_sent == False  # noqa: E712
    ).to_list()

    for shop in shops:
        try:
            end = shop.subscription_end or shop.trial_end
            left = days_until(end)
            if left > 3:
                continue
            owner = await User.get(shop.owner_id)
            if not owner or not owner.telegram_id:
                continue
            sent = await notify_telegram(
                owner.telegram_id,
                f"⚠️ <b>Obuna haqida</b>\n\n"
                f"🏪 {esc(shop.name)}\n"
                f"📅 Obunangiz <b>{left} kun</b>dan so'ng tugaydi.\n\n"
                f"Davom ettirish uchun admin bilan bog'laning.",
            )
            if sent:
                shop.warning_sent = True
                shop.updated_at = utcnow()
                await shop.save()
        except Exception as e:      # noqa: BLE001
            logger.error("Obuna ogohlantirishi (shop=%s): %s", shop.id, e)


async def update_overdue():
    """Muddati o'tgan qarzlarni 'overdue' ga o'tkazish (bitta so'rovda)."""
    from app.models import Debt

    now = utcnow()
    res = await Debt.get_motor_collection().update_many(
        {
            "status": {"$in": ["open", "partial"]},
            "due_date": {"$ne": None, "$lt": now},
        },
        {"$set": {"status": "overdue", "updated_at": now}},
    )
    if res.modified_count:
        logger.info("%s ta qarz 'overdue' holatiga o'tdi", res.modified_count)


async def archive_cleanup():
    """Eski yopiq qarzlarni va ularning to'lovlarini tozalash."""
    from app.models import Debt, Payment, AppSettings

    s = await AppSettings.find_one()
    months = s.archive_duration_months if s else 6
    cutoff = utcnow() - timedelta(days=months * 30)

    old = await Debt.find(
        In(Debt.status, ["closed", "archived"]), Debt.updated_at < cutoff
    ).to_list()
    if not old:
        return

    ids = [d.id for d in old]
    # Bitta so'rovda — ilgari har bir qarz uchun alohida so'rov ketardi
    await Payment.get_motor_collection().delete_many({"debt_id": {"$in": ids}})
    await Debt.get_motor_collection().delete_many({"_id": {"$in": ids}})
    logger.info("%s ta eski qarz tozalandi", len(ids))


# ─── Chiqindi qutisini tozalash ───────────────────────────────────────────────

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


# ─── Qarzdorga eslatma ────────────────────────────────────────────────────────

async def send_due_reminders():
    """Qarzdorga «ertaga muddat tugaydi» eslatmasi.

    Ilgari eslatma faqat do'kondorga borardi. Qarzdorning o'ziga oldindan
    xabar ketsa, to'lovlar sezilarli tezlashadi.
    """
    from app.config import settings
    from app.models import Shop, Debt, Client, ShopStatus
    from app.utils.helpers import format_money, local_day_bounds, esc, notify_debtor

    if not settings.DUE_REMINDER_ENABLED:
        return

    start, end = local_day_bounds(offset_days=1)      # ertangi kun
    debts = await Debt.find(
        In(Debt.status, ["open", "partial"]),
        Debt.due_date >= start,
        Debt.due_date <= end,
        Debt.due_reminder_sent == False,              # noqa: E712
    ).to_list()
    if not debts:
        return

    # Bitta mijozning bir do'kondagi barcha qarzlari — bitta xabarda
    grouped: dict = {}
    for d in debts:
        grouped.setdefault((d.client_id, d.shop_id), []).append(d)

    shops: dict = {}
    sent_ids: list = []

    for (client_id, shop_id), items in grouped.items():
        try:
            if shop_id not in shops:
                shops[shop_id] = await Shop.get(shop_id)
            shop = shops[shop_id]
            if not shop or shop.status != ShopStatus.ACTIVE:
                continue

            client = await Client.get(client_id)
            if not client or client.status != "active":
                continue

            total = sum(d.remaining for d in items)
            if len(items) == 1:
                body = f"💰 Qarz: <b>{format_money(total)}</b>"
            else:
                body = (
                    f"💰 {len(items)} ta qarz, jami: <b>{format_money(total)}</b>\n"
                    + "\n".join(f"  • {d.debt_number} — {format_money(d.remaining)}" for d in items[:5])
                )

            await notify_debtor(
                client.phone,
                f"⏰ <b>Ertaga qarz muddati tugaydi</b>\n\n"
                f"🏪 {esc(shop.name)}\n{body}\n\n"
                f"<i>Iltimos, to'lovni unutmang.</i>",
            )
            sent_ids.extend(d.id for d in items)
            await asyncio.sleep(settings.BULK_SEND_DELAY)
        except Exception as e:      # noqa: BLE001
            logger.error("Qarzdor eslatmasi (client=%s): %s", client_id, e)

    if sent_ids:
        # Takror yubormaslik uchun belgilaymiz
        await Debt.get_motor_collection().update_many(
            {"_id": {"$in": sent_ids}}, {"$set": {"due_reminder_sent": True}}
        )
        logger.info("Qarzdorlarga %s ta eslatma yuborildi", len(sent_ids))


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

    # O'chirilgan do'konlarni muddat tugagach tozalash
    job(purge_deleted_shops,         "purge",    CronTrigger(hour=1, minute=0, timezone=UZ_TZ))

    # Qarzdorlarga «ertaga muddat tugaydi»
    job(send_due_reminders,          "due_reminder",
        CronTrigger(hour=settings.DUE_REMINDER_HOUR, minute=30, timezone=UZ_TZ))

    # Har oyning 1-sanasi — Excel hisobotlar (og'ir vazifa, kengroq grace)
    job(send_monthly_reports,        "monthly_report",
        CronTrigger(day=1, hour=settings.MONTHLY_REPORT_HOUR, minute=0, timezone=UZ_TZ),
        grace=6 * 3600)

    if not scheduler.running:
        scheduler.start()
    logger.info(
        "Scheduler ishga tushdi (kunlik %02d:%02d, qarzdor eslatmasi %02d:30, "
        "oylik hisobot 1-sana %02d:00 — Toshkent)",
        hour, minute, settings.DUE_REMINDER_HOUR, settings.MONTHLY_REPORT_HOUR,
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
