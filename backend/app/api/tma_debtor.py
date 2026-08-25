import logging

from fastapi import APIRouter, Depends, HTTPException
from beanie import PydanticObjectId
from beanie.operators import In

from app.models import User, Shop, Client, Debt, Payment, ShopStatus, utcnow
from app.core.tma import get_tma_user
from app.utils.helpers import phone_variants, month_starts, month_label

router = APIRouter(prefix="/api/tma/debtor")
logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ["open", "partial", "overdue"]

# Bitta ekranda ko'rsatiladigan maksimal yozuvlar.
# Ilgari cheklov yo'q edi: yillar davomida yig'ilgan mingta to'lovi bor
# qarzdorda sahifa sekin ochilardi va javob hajmi bir necha MB bo'lardi.
MAX_DEBTS = 300
MAX_PAYMENTS = 500


async def get_debtor_user(tma: dict = Depends(get_tma_user)) -> User:
    user = await User.find_one(User.telegram_id == tma["telegram_id"])
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    if user.is_blocked:
        raise HTTPException(403, "Akkauntingiz bloklangan")
    return user


def _get_phones(user: User) -> list[str]:
    """Barcha raqamlar — xom va normallashtirilgan ko'rinishda."""
    return sorted({v for p in [user.phone, *user.extra_phones] for v in phone_variants(p)})


@router.get("/overview")
async def debtor_overview(user: User = Depends(get_debtor_user)):
    """Barcha do'konlardagi qarzlar umumiy ko'rinishi."""
    phones = _get_phones(user)
    if not phones:
        return {"shops": [], "total_remaining": 0, "total_paid": 0, "total_overdue": 0}

    owned_ids = {s.id for s in await Shop.find(Shop.owner_id == user.id).to_list()}

    clients = await Client.find({"phone": {"$in": phones}, "status": "active"}).to_list()
    # O'z do'konidagi yozuvni qarzdorlik sifatida ko'rsatmaymiz
    clients = [c for c in clients if c.shop_id not in owned_ids]
    if not clients:
        return {"shops": [], "total_remaining": 0, "total_paid": 0, "total_overdue": 0}

    # O'chirilgan do'konlar ro'yxatga tushmaydi
    shops = {
        s.id: s for s in await Shop.find(
            In(Shop.id, list({c.shop_id for c in clients})),
            Shop.status != ShopStatus.DELETED,
        ).to_list()
    }
    clients = [c for c in clients if c.shop_id in shops]
    if not clients:
        return {"shops": [], "total_remaining": 0, "total_paid": 0, "total_overdue": 0}

    client_ids = [c.id for c in clients]

    # Ilgari har bir mijoz uchun alohida so'rov ketardi
    rows = await Debt.get_motor_collection().aggregate([
        {"$match": {"client_id": {"$in": client_ids}}},
        {"$group": {
            "_id": "$client_id",
            "remaining": {"$sum": {"$cond": [
                {"$in": ["$status", ACTIVE_STATUSES]}, "$remaining", 0,
            ]}},
            "paid": {"$sum": {"$cond": [
                {"$in": ["$status", ACTIVE_STATUSES]}, "$paid_amount", 0,
            ]}},
            "active_count": {"$sum": {"$cond": [{"$in": ["$status", ACTIVE_STATUSES]}, 1, 0]}},
            "overdue": {"$sum": {"$cond": [{"$eq": ["$status", "overdue"]}, 1, 0]}},
            "overdue_remaining": {"$sum": {"$cond": [
                {"$eq": ["$status", "overdue"]}, "$remaining", 0,
            ]}},
        }},
    ]).to_list(length=None)
    stats = {r["_id"]: r for r in rows}

    shops_data = []
    total_remaining = 0
    total_paid = 0
    total_overdue = 0

    for client in clients:
        shop = shops.get(client.shop_id)
        if not shop:
            continue
        st = stats.get(client.id, {})
        remaining = st.get("remaining", 0)
        paid = st.get("paid", 0)
        overdue_remaining = st.get("overdue_remaining", 0)
        total_remaining += remaining
        total_paid += paid
        total_overdue += overdue_remaining
        shops_data.append({
            "shop_id": str(shop.id),
            "client_id": str(client.id),
            "shop_name": shop.name,
            "remaining": remaining,
            "paid": paid,
            "active_count": st.get("active_count", 0),
            "has_overdue": bool(st.get("overdue", 0)),
            "overdue_count": st.get("overdue", 0),
            "overdue_remaining": overdue_remaining,
        })

    # Muddati o'tganlar birinchi — qarzdor eng shoshilinchini darhol ko'radi
    shops_data.sort(key=lambda x: (not x["has_overdue"], -x["remaining"]))
    return {
        "shops": shops_data,
        "total_remaining": total_remaining,
        "total_paid": total_paid,
        "total_overdue": total_overdue,
    }


@router.get("/shop/{shop_id}")
async def debtor_shop_detail(shop_id: str, user: User = Depends(get_debtor_user)):
    """Bitta do'kondagi qarzlar tarixi + tahlil."""
    try:
        sid = PydanticObjectId(shop_id)
    except Exception:      # noqa: BLE001
        raise HTTPException(404, "Ma'lumot topilmadi")

    phones = _get_phones(user)
    if not phones:
        raise HTTPException(404, "Ma'lumot topilmadi")

    # XATO TUZATILDI: ilgari shop_id shartisiz find_one ishlatilgan edi —
    # bir nechta do'konda qarzi bor foydalanuvchi tasodifiy boshqa do'konning
    # yozuvini olib, "Ma'lumot topilmadi" xatosiga urilardi.
    client = await Client.find_one({
        "shop_id": sid, "phone": {"$in": phones}, "status": "active",
    })
    if not client:
        raise HTTPException(404, "Ma'lumot topilmadi")

    # O'z do'koni yoki o'chirilgan do'kon bo'lsa — ko'rsatmaymiz
    shop = await Shop.get(sid)
    if not shop or shop.owner_id == user.id or shop.status == ShopStatus.DELETED:
        raise HTTPException(404, "Ma'lumot topilmadi")

    debts = await Debt.find(Debt.client_id == client.id)         .sort(-Debt.created_at).limit(MAX_DEBTS).to_list()
    debt_ids = [d.id for d in debts]

    payments_by_debt: dict = {}
    if debt_ids:
        payments = await Payment.find(In(Payment.debt_id, debt_ids))             .sort(-Payment.created_at).limit(MAX_PAYMENTS).to_list()
        for p in payments:
            payments_by_debt.setdefault(p.debt_id, []).append({
                "amount": p.amount,
                "remaining_after": p.remaining_after,
                "created_at": p.created_at.isoformat(),
            })

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
            "payments": payments_by_debt.get(d.id, []),
        }
        for d in debts
    ]
    active = [d for d in debt_list if d["status"] in ACTIVE_STATUSES]

    # Oylik tahlil (6 oy) — kalendar oylari bo'yicha
    starts = month_starts(6)
    monthly = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else utcnow()
        m = [d for d in debts if start <= d.created_at < end]
        monthly.append({
            "month": month_label(start),
            "count": len(m),
            "amount": sum(d.amount for d in m),
        })

    return {
        "shop_name": shop.name,
        "total_remaining": sum(d["remaining"] for d in active),
        "total_paid": sum(d["paid_amount"] for d in debt_list),
        "total_debt": sum(d["amount"] for d in debt_list),
        "debts": debt_list,
        "monthly": monthly,
    }
