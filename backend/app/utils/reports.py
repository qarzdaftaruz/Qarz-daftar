"""Do'kon hisobotini tayyorlash va yuborish.

API (do'kondor tugmani bosganda) va scheduler (oylik avtomatik yuborish)
bir xil mantiqdan foydalanadi.

SERVER YUKI: Excel yasash — tizimdagi eng og'ir amal. Shu sababli:
  • bitta do'kon uchun bir vaqtda faqat bitta hisobot yasaladi (qulf);
  • qatorlar soni EXPORT_MAX_ROWS bilan cheklangan (xotira himoyasi);
  • ommaviy yuborishda har bir do'kon orasida tanaffus beriladi.
"""
import asyncio
import logging
from typing import Optional

from app.config import settings
from app.models import Shop, Client, Debt, utcnow
from app.utils.excel import build_shop_report

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ["open", "partial", "overdue"]

# Bir do'kon uchun bir vaqtning o'zida bitta hisobot — takror bosilgan
# tugma serverni bir necha marta ishlatib qo'ymasligi uchun
_locks: dict[str, asyncio.Lock] = {}


def _lock_for(shop_id: str) -> asyncio.Lock:
    lock = _locks.get(shop_id)
    if lock is None:
        lock = _locks[shop_id] = asyncio.Lock()
    # Xotira cheksiz o'smasin
    if len(_locks) > 500:
        for key in [k for k, v in _locks.items() if not v.locked()][:250]:
            _locks.pop(key, None)
    return lock


def is_busy(shop_id: str) -> bool:
    lock = _locks.get(shop_id)
    return bool(lock and lock.locked())


async def collect(shop: Shop) -> tuple[list[dict], list[dict]]:
    """Do'konning qarzdorlari va qarzlarini hisobot uchun yig'adi."""
    clients = await Client.find(Client.shop_id == shop.id, Client.status == "active").to_list()
    client_map = {c.id: c for c in clients}

    debts = await Debt.find(Debt.shop_id == shop.id) \
        .sort(-Debt.created_at).limit(settings.EXPORT_MAX_ROWS).to_list()

    stats: dict = {}
    if client_map:
        rows = await Debt.get_motor_collection().aggregate([
            {"$match": {"client_id": {"$in": list(client_map)}}},
            {"$group": {
                "_id": "$client_id",
                "active_n": {"$sum": {"$cond": [{"$in": ["$status", ACTIVE_STATUSES]}, 1, 0]}},
                "remaining": {"$sum": {"$cond": [{"$in": ["$status", ACTIVE_STATUSES]}, "$remaining", 0]}},
                "paid": {"$sum": "$paid_amount"},
                "overdue": {"$sum": {"$cond": [{"$eq": ["$status", "overdue"]}, 1, 0]}},
            }},
        ]).to_list(length=None)
        stats = {r["_id"]: r for r in rows}

    client_rows = sorted(
        (
            {
                "full_name": c.full_name,
                "phone": c.phone,
                "active_debts": stats.get(c.id, {}).get("active_n", 0),
                "total_remaining": stats.get(c.id, {}).get("remaining", 0),
                "total_paid": stats.get(c.id, {}).get("paid", 0),
                "has_overdue": bool(stats.get(c.id, {}).get("overdue", 0)),
            }
            for c in clients
        ),
        key=lambda x: -x["total_remaining"],
    )

    debt_rows = [
        {
            "debt_number": d.debt_number,
            "client_name": client_map[d.client_id].full_name if d.client_id in client_map else "—",
            "client_phone": client_map[d.client_id].phone if d.client_id in client_map else "",
            "amount": d.amount,
            "paid_amount": d.paid_amount,
            "remaining": d.remaining,
            "status": d.status,
            "due_date": d.due_date,
            "note": d.note,
            "created_at": d.created_at,
        }
        for d in debts
    ]
    return client_rows, debt_rows


def safe_filename(shop_name: str, suffix: str = "") -> str:
    base = "".join(ch for ch in shop_name if ch.isalnum() or ch in " -_").strip() or "dokon"
    stamp = utcnow().strftime("%Y-%m-%d")
    return f"{base}_{suffix + '_' if suffix else ''}{stamp}.xlsx"


async def build(shop: Shop) -> Optional[tuple[bytes, str, int, int]]:
    """Hisobotni yasaydi. Ma'lumot bo'lmasa None qaytaradi.

    Returns: (fayl baytlari, fayl nomi, qarzdorlar soni, qarzlar soni)
    """
    async with _lock_for(str(shop.id)):
        client_rows, debt_rows = await collect(shop)
        if not client_rows and not debt_rows:
            return None

        # CPU'ni bloklamaslik uchun alohida oqimda — bitta og'ir hisobot
        # boshqa foydalanuvchilarning so'rovlarini kutkazib qo'ymasin
        content = await asyncio.to_thread(
            build_shop_report, shop.name, client_rows, debt_rows
        )
        return content, safe_filename(shop.name), len(client_rows), len(debt_rows)


async def send_to_owner(shop: Shop, telegram_id: int, caption_prefix: str = "📊") -> bool:
    """Hisobotni do'kon egasiga Telegram hujjati sifatida yuboradi."""
    from aiogram.types import BufferedInputFile
    from app.bot.main import bot
    from app.utils.helpers import esc

    built = await build(shop)
    if not built:
        return False

    content, filename, n_clients, n_debts = built
    try:
        await bot.send_document(
            telegram_id,
            BufferedInputFile(content, filename=filename),
            caption=(
                f"{caption_prefix} <b>{esc(shop.name)}</b> — hisobot\n"
                f"👥 Qarzdorlar: {n_clients} ta\n"
                f"🧾 Qarzlar: {n_debts} ta"
            ),
        )
        return True
    except Exception as e:      # noqa: BLE001
        logger.warning("Hisobot yuborilmadi (shop=%s, tg=%s): %s", shop.id, telegram_id, e)
        return False
