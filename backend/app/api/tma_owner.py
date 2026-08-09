import logging
from datetime import datetime, timedelta
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from beanie import PydanticObjectId
from beanie.operators import In

from app.models import (
    User, Shop, Client, Debt, Payment, SupportMessage,
    ShopStatus, DebtStatus, utcnow,
)
from app.core.tma import get_tma_user
from app.core.ratelimit import write_rate_limit, user_write_rate_limit
from app.core import audit, cache, locks
from app.utils.helpers import (
    generate_debt_number, format_money, notify_debtor, debt_notification,
    safe_regex, normalize_phone, is_valid_phone, esc, notify_telegram,
    month_starts, month_label, parse_due_date,
)

router = APIRouter(prefix="/api/tma/owner")
logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ["open", "partial", "overdue"]
MAX_AMOUNT = 100_000_000_000        # 100 mlrd so'm
MAX_PAGE_SIZE = 100


def _oid(value: str, label: str = "Ma'lumot") -> PydanticObjectId:
    try:
        return PydanticObjectId(value)
    except Exception:      # noqa: BLE001
        raise HTTPException(404, f"{label} topilmadi")


# ─── DEPENDENCY ───────────────────────────────────────────────────────────────

async def owner_shop(
    shop_id: str = Query(..., min_length=24, max_length=24),
    tma: dict = Depends(get_tma_user),
):
    """So'ralgan do'kon shu foydalanuvchiga tegishli ekanini tekshiradi."""
    user = await User.find_one(User.telegram_id == tma["telegram_id"])
    if not user:
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    if user.is_blocked:
        raise HTTPException(403, "Akkauntingiz bloklangan")

    shop = await Shop.get(_oid(shop_id, "Do'kon"))
    # Mavjud emas va "meniki emas" holatlari bir xil javob beradi —
    # boshqa do'konlar ID sini taxmin qilib bilib bo'lmaydi
    if not shop or shop.owner_id != user.id:
        raise HTTPException(403, "Ruxsat yo'q")

    if shop.status not in (ShopStatus.ACTIVE, ShopStatus.PENDING):
        raise HTTPException(403, f"Do'kon holati: {shop.status}")

    return user, shop


async def _bulk_update_debts(debts: list[Debt], expected: Optional[dict] = None) -> int:
    """Bir nechta qarzni bitta so'rovda yangilash.

    `expected` berilsa — har bir qarz uchun «qoldiq hali o'zgarmagan»
    sharti qo'shiladi (optimistik qulflash). Boshqa so'rov oradan o'tib
    ketgan bo'lsa, yozuv qo'llanmaydi va bu qaytarilgan sanoqdan bilinadi.
    """
    if not debts:
        return 0
    from pymongo import UpdateOne

    ops = []
    for d in debts:
        criteria: dict = {"_id": d.id}
        if expected is not None and d.id in expected:
            criteria["remaining"] = expected[d.id]
        ops.append(UpdateOne(criteria, {"$set": {
            "paid_amount": d.paid_amount,
            "remaining": d.remaining,
            "status": d.status.value if hasattr(d.status, "value") else d.status,
            "updated_at": d.updated_at,
        }}))

    res = await Debt.get_motor_collection().bulk_write(ops, ordered=False)
    return res.modified_count


async def monthly_debt_stats(match: dict, months: int = 6) -> list[dict]:
    """Oxirgi `months` oy bo'yicha qarzlar soni va yig'ilgan summa.

    Bitta aggregation — har bir oy uchun alohida so'rov yubormaydi.
    Sanalar Toshkent vaqti bo'yicha oy chegaralariga bo'linadi.
    """
    starts = month_starts(months)
    boundaries = starts + [utcnow() + timedelta(days=1)]

    rows = await Debt.get_motor_collection().aggregate([
        {"$match": {**match, "created_at": {"$gte": starts[0]}}},
        {"$bucket": {
            "groupBy": "$created_at",
            "boundaries": boundaries,
            "default": "other",
            "output": {"count": {"$sum": 1}, "collected": {"$sum": "$paid_amount"}},
        }},
    ]).to_list(length=None)

    by_start = {r["_id"]: r for r in rows if r["_id"] != "other"}
    return [
        {
            "month": month_label(s),
            "count": by_start.get(s, {}).get("count", 0),
            "collected": by_start.get(s, {}).get("collected", 0),
        }
        for s in starts
    ]


async def _group(model, match: dict, field: str, agg: dict) -> dict:
    if not match.get(field, {}).get("$in"):
        return {}
    rows = await model.get_motor_collection().aggregate([
        {"$match": match},
        {"$group": {"_id": f"${field}", **agg}},
    ]).to_list(length=None)
    return {r["_id"]: r for r in rows}


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def dashboard(ctx=Depends(owner_shop)):
    user, shop = ctx

    clients_count = await Client.find(
        Client.shop_id == shop.id, Client.status == "active"
    ).count()

    rows = await Debt.get_motor_collection().aggregate([
        {"$match": {"shop_id": shop.id, "status": {"$in": ACTIVE_STATUSES}}},
        {"$group": {"_id": "$status", "n": {"$sum": 1}, "total": {"$sum": "$remaining"}}},
    ]).to_list(length=None)
    by_status = {r["_id"]: r for r in rows}

    active_count = by_status.get("open", {}).get("n", 0) + by_status.get("partial", {}).get("n", 0)
    overdue_count = by_status.get("overdue", {}).get("n", 0)
    total_remaining = sum(r["total"] for r in rows)

    recent_debts = await Debt.find(
        Debt.shop_id == shop.id, In(Debt.status, ACTIVE_STATUSES)
    ).sort(-Debt.created_at).limit(5).to_list()

    clients = {
        c.id: c for c in
        await Client.find(In(Client.id, [d.client_id for d in recent_debts])).to_list()
    } if recent_debts else {}

    recent = [
        {
            "id": str(d.id),
            "debt_number": d.debt_number,
            "client_name": clients[d.client_id].full_name if d.client_id in clients else "?",
            "client_phone": clients[d.client_id].phone if d.client_id in clients else "",
            "remaining": d.remaining,
            "status": d.status,
            "due_date": d.due_date.isoformat() if d.due_date else None,
        }
        for d in recent_debts
    ]

    return {
        "shop_name": shop.name,
        "shop_status": shop.status,
        "stats": {
            "clients": clients_count,
            "active_debts": active_count,
            "overdue_debts": overdue_count,
            "total_remaining": total_remaining,
        },
        "recent_debts": recent,
    }


# ─── CLIENTS ──────────────────────────────────────────────────────────────────

@router.get("/clients")
async def get_clients(
    search: Optional[str] = Query(default=None, max_length=64),
    skip: int = 0,
    limit: int = 20,
    filter: Optional[Literal["all", "no_debt", "overdue"]] = None,
    ctx=Depends(owner_shop),
):
    user, shop = ctx
    skip = max(0, skip)
    limit = max(1, min(limit, MAX_PAGE_SIZE))

    match: dict = {"shop_id": shop.id, "status": "active"}
    if search and search.strip():
        pattern = safe_regex(search)
        match["$or"] = [
            {"full_name": {"$regex": pattern, "$options": "i"}},
            {"phone": {"$regex": pattern}},
        ]

    # TEZLIK: butun ish MongoDB ichida bajariladi.
    # Ilgari do'konning BARCHA mijozlari xotiraga yuklanib, Python'da
    # saralanib, keyin 20 tasi olinardi — 3000 mijozli do'konda bu
    # har bir sahifa ochilishida ~3000 hujjatni tarmoq orqali tortardi.
    pipeline = [
        {"$match": match},
        {"$lookup": {
            "from": Debt.get_motor_collection().name,
            "let": {"cid": "$_id"},
            "pipeline": [
                {"$match": {
                    "$expr": {"$eq": ["$client_id", "$$cid"]},
                    "status": {"$in": ACTIVE_STATUSES},
                }},
                {"$group": {
                    "_id": None,
                    "n": {"$sum": 1},
                    "total": {"$sum": "$remaining"},
                    "overdue": {"$sum": {"$cond": [{"$eq": ["$status", "overdue"]}, 1, 0]}},
                }},
            ],
            "as": "_d",
        }},
        {"$addFields": {
            "active_debts": {"$ifNull": [{"$first": "$_d.n"}, 0]},
            "total_remaining": {"$ifNull": [{"$first": "$_d.total"}, 0]},
            "has_overdue": {"$gt": [{"$ifNull": [{"$first": "$_d.overdue"}, 0]}, 0]},
        }},
    ]

    if filter == "no_debt":
        pipeline.append({"$match": {"total_remaining": 0}})
    elif filter == "overdue":
        pipeline.append({"$match": {"has_overdue": True}})

    pipeline += [
        {"$sort": {"total_remaining": -1, "full_name": 1}},
        {"$facet": {
            "rows": [
                {"$skip": skip},
                {"$limit": limit},
                {"$project": {
                    "full_name": 1, "phone": 1, "debt_limit": 1,
                    "active_debts": 1, "total_remaining": 1, "has_overdue": 1,
                }},
            ],
            "total": [{"$count": "n"}],
        }},
    ]

    res = await Client.get_motor_collection().aggregate(pipeline).to_list(length=1)
    facet = res[0] if res else {"rows": [], "total": []}

    clients = [
        {
            "id": str(r["_id"]),
            "full_name": r.get("full_name", ""),
            "phone": r.get("phone", ""),
            "debt_limit": r.get("debt_limit"),
            "active_debts": r.get("active_debts", 0),
            "total_remaining": r.get("total_remaining", 0),
            "has_overdue": bool(r.get("has_overdue")),
        }
        for r in facet["rows"]
    ]
    total = facet["total"][0]["n"] if facet["total"] else 0
    return {"clients": clients, "total": total}


@router.get("/clients/{client_id}")
async def get_client(client_id: str, ctx=Depends(owner_shop)):
    user, shop = ctx
    client = await Client.get(_oid(client_id, "Mijoz"))
    if not client or client.shop_id != shop.id:
        raise HTTPException(404, "Mijoz topilmadi")

    # Qarzlar navbat tartibida: eskisi yuqorida (xronologik)
    debts = await Debt.find(Debt.client_id == client.id).sort(+Debt.created_at).to_list()

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
    active = [d for d in debt_list if d["status"] in ACTIVE_STATUSES]

    # Faqat FAOL qarzlar bo'yicha "to'landi" va to'lovlar ro'yxati
    active_ids = [d.id for d in debts if d.status in ACTIVE_STATUSES]
    total_paid = sum(d.paid_amount for d in debts if d.status in ACTIVE_STATUSES)

    payments_list = []
    if active_ids:
        payments = await Payment.find(
            In(Payment.debt_id, active_ids)
        ).sort(-Payment.created_at).limit(200).to_list()
        payments_list = [
            {"amount": p.amount, "created_at": p.created_at.isoformat()} for p in payments
        ]

    return {
        "id": str(client.id),
        "full_name": client.full_name,
        "phone": client.phone,
        "debt_limit": client.debt_limit,
        "total_remaining": sum(d["remaining"] for d in active),
        "total_paid": total_paid,
        "debts": debt_list,
        "payments": payments_list,
    }


class CreateClientBody(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=7, max_length=20)
    debt_limit: Optional[int] = Field(default=None, ge=0, le=MAX_AMOUNT)
    initial_amount: Optional[int] = Field(default=None, ge=0, le=MAX_AMOUNT)
    initial_due_date: Optional[datetime] = None
    initial_note: Optional[str] = Field(default=None, max_length=200)


@router.post("/clients", dependencies=[Depends(write_rate_limit), Depends(user_write_rate_limit)])
async def create_client(body: CreateClientBody, ctx=Depends(owner_shop)):
    user, shop = ctx

    phone = normalize_phone(body.phone)
    if not is_valid_phone(phone):
        raise HTTPException(400, "Telefon raqam formati noto'g'ri (masalan: +998901234567)")

    existing = await Client.find_one(
        Client.shop_id == shop.id, Client.phone == phone, Client.status == "active"
    )
    if existing:
        raise HTTPException(400, f"Bu raqam allaqachon mavjud: {existing.full_name}")

    client = await Client(
        shop_id=shop.id,
        full_name=body.full_name.strip(),
        phone=phone,
        debt_limit=body.debt_limit or None,
    ).insert()

    debt_info = None
    if body.initial_amount and body.initial_amount > 0:
        due_date = parse_due_date(body.initial_due_date)
        number = await generate_debt_number(shop.id)
        debt = await Debt(
            debt_number=number, shop_id=shop.id, client_id=client.id,
            amount=body.initial_amount, remaining=body.initial_amount,
            due_date=due_date, note=body.initial_note, status=DebtStatus.OPEN,
        ).insert()
        await notify_debtor(
            client.phone,
            debt_notification(shop.name, body.initial_amount, due_date, debt.note),
        )
        debt_info = {"id": str(debt.id), "debt_number": debt.debt_number}
        await audit.log_owner(
            user, shop, "debt.create",
            entity_type="debt", entity_id=debt.id, entity_label=debt.debt_number,
            summary=f"{client.full_name} ({client.phone}) — boshlang'ich qarz {format_money(body.initial_amount)}",
            meta={"amount": body.initial_amount},
        )

    await audit.log_owner(
        user, shop, "client.create",
        entity_type="client", entity_id=client.id, entity_label=client.full_name,
        summary=f"Yangi mijoz: {client.full_name} ({client.phone})",
    )
    return {"id": str(client.id), "full_name": client.full_name, "debt": debt_info}


class UpdateClientBody(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    debt_limit: Optional[int] = Field(default=None, ge=0, le=MAX_AMOUNT)


@router.put("/clients/{client_id}")
async def update_client(client_id: str, body: UpdateClientBody, ctx=Depends(owner_shop)):
    user, shop = ctx
    client = await Client.get(_oid(client_id, "Mijoz"))
    if not client or client.shop_id != shop.id:
        raise HTTPException(404, "Mijoz topilmadi")

    if body.full_name:
        client.full_name = body.full_name.strip()
    if body.debt_limit is not None:
        client.debt_limit = body.debt_limit or None
    client.updated_at = utcnow()
    await client.save()
    await audit.log_owner(
        user, shop, "client.update",
        entity_type="client", entity_id=client.id, entity_label=client.full_name,
        summary=f"Mijoz o'zgartirildi: {client.full_name}",
        meta=body.model_dump(exclude_unset=True),
    )
    return {"ok": True}


@router.delete("/clients/{client_id}")
async def archive_client(client_id: str, ctx=Depends(owner_shop)):
    user, shop = ctx
    client = await Client.get(_oid(client_id, "Mijoz"))
    if not client or client.shop_id != shop.id:
        raise HTTPException(404, "Mijoz topilmadi")

    now = utcnow()
    await Debt.get_motor_collection().update_many(
        {"client_id": client.id, "status": {"$in": ACTIVE_STATUSES}},
        {"$set": {"status": DebtStatus.ARCHIVED.value, "updated_at": now}},
    )

    client.status = "archived"
    client.updated_at = now
    await client.save()

    await notify_debtor(client.phone, f"📦 {esc(shop.name)}: Sizning qarz yozuvingiz o'chirildi.")
    await audit.log_owner(
        user, shop, "client.archive",
        entity_type="client", entity_id=client.id, entity_label=client.full_name,
        summary=f"Mijoz o'chirildi (arxivlandi): {client.full_name} ({client.phone})",
    )
    return {"ok": True}


@router.post("/clients/{client_id}/clear-debts", dependencies=[Depends(write_rate_limit), Depends(user_write_rate_limit)])
async def clear_client_debts(client_id: str, ctx=Depends(owner_shop)):
    """Mijozning barcha faol qarzlarini to'liq to'langan deb belgilash."""
    user, shop = ctx
    client = await Client.get(_oid(client_id, "Mijoz"))
    if not client or client.shop_id != shop.id:
        raise HTTPException(404, "Mijoz topilmadi")

    # To'lov yozuvi yaratiladigan amal — qulf ostida (takror bosishdan himoya)
    async with locks.guard(f"client-pay:{client.id}"):
        active = await Debt.find(
            Debt.client_id == client.id, In(Debt.status, ACTIVE_STATUSES)
        ).to_list()
        if not active:
            return {"cleared_count": 0, "total_cleared": 0}

        now = utcnow()
        payments = []
        expected = {}
        total_cleared = 0
        for d in active:
            expected[d.id] = d.remaining
            if d.remaining > 0:
                payments.append(Payment(
                    debt_id=d.id, shop_id=shop.id, client_id=client.id,
                    amount=d.remaining, remaining_after=0,
                ))
                total_cleared += d.remaining
            d.paid_amount = d.amount
            d.remaining = 0
            d.status = DebtStatus.CLOSED
            d.updated_at = now

        updated = await _bulk_update_debts(active, expected)
        if updated != len(active):
            raise HTTPException(409, "Qarzlar hozirgina o'zgardi — sahifani yangilab qayta urining")
        if payments:
            await Payment.insert_many(payments)

    await notify_debtor(
        client.phone,
        f"✅ {esc(shop.name)}: Barcha qarzlaringiz ({format_money(total_cleared)}) yopildi!",
    )
    await audit.log_owner(
        user, shop, "client.clear_debts",
        entity_type="client", entity_id=client.id, entity_label=client.full_name,
        summary=f"{client.full_name} — {len(active)} ta qarz yopildi ({format_money(total_cleared)})",
        meta={"count": len(active), "total": total_cleared},
    )
    return {"cleared_count": len(active), "total_cleared": total_cleared}


# ─── DEBTS ───────────────────────────────────────────────────────────────────

class CreateDebtBody(BaseModel):
    client_id: str = Field(min_length=24, max_length=24)
    amount: int = Field(gt=0, le=MAX_AMOUNT)
    due_date: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=200)


@router.post("/debts", dependencies=[Depends(write_rate_limit), Depends(user_write_rate_limit)])
async def create_debt(body: CreateDebtBody, ctx=Depends(owner_shop)):
    user, shop = ctx

    client = await Client.get(_oid(body.client_id, "Mijoz"))
    if not client or client.shop_id != shop.id:
        raise HTTPException(404, "Mijoz topilmadi")

    limit_warning = None
    if client.debt_limit:
        rows = await Debt.get_motor_collection().aggregate([
            {"$match": {"client_id": client.id, "status": {"$in": ACTIVE_STATUSES}}},
            {"$group": {"_id": None, "total": {"$sum": "$remaining"}}},
        ]).to_list(length=1)
        current = rows[0]["total"] if rows else 0
        if current + body.amount > client.debt_limit:
            excess = (current + body.amount) - client.debt_limit
            limit_warning = f"Limit {format_money(excess)} ga oshadi"

    due_date = parse_due_date(body.due_date)
    number = await generate_debt_number(shop.id)

    debt = await Debt(
        debt_number=number, shop_id=shop.id, client_id=client.id,
        amount=body.amount, remaining=body.amount, due_date=due_date,
        note=body.note, status=DebtStatus.OPEN,
    ).insert()

    await notify_debtor(
        client.phone, debt_notification(shop.name, body.amount, due_date, debt.note)
    )
    await audit.log_owner(
        user, shop, "debt.create",
        entity_type="debt", entity_id=debt.id, entity_label=debt.debt_number,
        summary=f"{client.full_name} ({client.phone}) — yangi qarz {format_money(body.amount)}",
        meta={"amount": body.amount},
    )
    return {"id": str(debt.id), "debt_number": debt.debt_number, "warning": limit_warning}


# ─── PAYMENTS ────────────────────────────────────────────────────────────────

class CreatePaymentBody(BaseModel):
    debt_id: str = Field(min_length=24, max_length=24)
    amount: int = Field(gt=0, le=MAX_AMOUNT)


@router.post("/payments", dependencies=[Depends(write_rate_limit), Depends(user_write_rate_limit)])
async def create_payment(body: CreatePaymentBody, ctx=Depends(owner_shop)):
    user, shop = ctx

    debt = await Debt.get(_oid(body.debt_id, "Qarz"))
    if not debt or debt.shop_id != shop.id:
        raise HTTPException(404, "Qarz topilmadi")
    if debt.status in (DebtStatus.CLOSED, DebtStatus.ARCHIVED):
        raise HTTPException(400, "Qarz allaqachon yopiq")

    actual = min(body.amount, debt.remaining)
    if actual <= 0:
        raise HTTPException(400, "Qarz qoldig'i yo'q")
    new_remaining = debt.remaining - actual
    new_status = DebtStatus.CLOSED if new_remaining == 0 else DebtStatus.PARTIAL

    # Atomar yangilash: ikki qurilmadan bir vaqtda to'lov kiritilsa ham
    # qoldiq manfiy bo'lib ketmaydi (ilgari read-modify-write edi).
    res = await Debt.get_motor_collection().update_one(
        {"_id": debt.id, "remaining": debt.remaining},
        {"$set": {
            "remaining": new_remaining,
            "paid_amount": debt.paid_amount + actual,
            "status": new_status.value,
            "updated_at": utcnow(),
        }},
    )
    if res.modified_count != 1:
        raise HTTPException(409, "Qarz hozirgina o'zgardi — sahifani yangilab qayta urining")

    await Payment(
        debt_id=debt.id, shop_id=shop.id, client_id=debt.client_id,
        amount=actual, remaining_after=new_remaining,
    ).insert()

    client = await Client.get(debt.client_id)
    if client:
        if new_remaining == 0:
            msg = f"✅ {esc(shop.name)}: qarzingiz to'liq yopildi!"
        else:
            msg = (f"💳 {esc(shop.name)}: {format_money(actual)} to'lov qabul qilindi. "
                   f"Qoldiq: {format_money(new_remaining)}")
        await notify_debtor(client.phone, msg)

    await audit.log_owner(
        user, shop, "payment.create",
        entity_type="debt", entity_id=debt.id, entity_label=debt.debt_number,
        summary=f"{client.full_name if client else '?'} — to'lov {format_money(actual)}, "
                f"qoldiq {format_money(new_remaining)}",
        meta={"amount": actual, "remaining": new_remaining},
    )
    return {"paid": actual, "remaining": new_remaining, "status": new_status.value}


class TotalPaymentBody(BaseModel):
    client_id: str = Field(min_length=24, max_length=24)
    amount: int = Field(gt=0, le=MAX_AMOUNT)


async def apply_total_payment(client: Client, shop_name: str, amount: int) -> dict:
    """Umumiy qoldiqdan to'lov — eski qarzlardan boshlab taqsimlanadi.

    Admin paneli va do'kon paneli bir xil mantiqdan foydalanadi.

    XAVFSIZLIK: butun amal mijoz bo'yicha qulf ostida bajariladi.
    Aks holda tugma ikki marta bosilganda (yoki ikkita qurilmadan bir
    vaqtda) ikkala so'rov ham eski qoldiqni o'qib, to'lovni ikki marta
    yozib yuborardi — mijoz qarzi noto'g'ri kamayib ketardi.
    """
    async with locks.guard(f"client-pay:{client.id}"):
        return await _apply_total_payment_locked(client, shop_name, amount)


async def _apply_total_payment_locked(client: Client, shop_name: str, amount: int) -> dict:
    active = await Debt.find(
        Debt.client_id == client.id, In(Debt.status, ACTIVE_STATUSES)
    ).sort(+Debt.created_at).to_list()

    total_remaining = sum(d.remaining for d in active)
    if total_remaining <= 0:
        raise HTTPException(400, "Faol qarz yo'q")
    if amount > total_remaining:
        raise HTTPException(400, f"Miqdor umumiy qoldiqdan ko'p! Qoldiq: {format_money(total_remaining)}")

    now = utcnow()
    leftover = amount
    payments: list[Payment] = []
    touched: list[Debt] = []
    expected: dict = {}          # qarz id → yozishdan oldingi qoldiq

    for d in active:
        if leftover <= 0:
            break
        take = min(d.remaining, leftover)
        if take <= 0:
            continue
        new_rem = d.remaining - take
        payments.append(Payment(
            debt_id=d.id, shop_id=d.shop_id, client_id=client.id,
            amount=take, remaining_after=new_rem,
        ))
        expected[d.id] = d.remaining
        d.paid_amount += take
        d.remaining = new_rem
        d.status = DebtStatus.CLOSED if new_rem == 0 else DebtStatus.PARTIAL
        d.updated_at = now
        touched.append(d)
        leftover -= take

    # Avval qarzlarni yangilaymiz — shart bajarilmasa to'lov ham yozilmaydi
    updated = await _bulk_update_debts(touched, expected)
    if updated != len(touched):
        logger.warning(
            "To'lov qo'llanmadi (client=%s): %s/%s qarz yangilandi",
            client.id, updated, len(touched),
        )
        raise HTTPException(409, "Qarzlar hozirgina o'zgardi — sahifani yangilab qayta urining")

    if payments:
        await Payment.insert_many(payments)

    new_total = total_remaining - amount
    if new_total == 0:
        msg = f"✅ <b>{esc(shop_name)}</b>: barcha qarzlaringiz yopildi!\n💳 To'lov: {format_money(amount)}"
    else:
        msg = (f"💳 <b>{esc(shop_name)}</b>: {format_money(amount)} to'lov qabul qilindi.\n"
               f"💰 Umumiy qoldiq: <b>{format_money(new_total)}</b>")
    await notify_debtor(client.phone, msg)

    return {"paid": amount, "total_remaining": new_total}


@router.post("/payments/total", dependencies=[Depends(write_rate_limit), Depends(user_write_rate_limit)])
async def create_total_payment(body: TotalPaymentBody, ctx=Depends(owner_shop)):
    user, shop = ctx
    client = await Client.get(_oid(body.client_id, "Mijoz"))
    if not client or client.shop_id != shop.id:
        raise HTTPException(404, "Mijoz topilmadi")
    result = await apply_total_payment(client, shop.name, body.amount)
    await audit.log_owner(
        user, shop, "payment.create",
        entity_type="client", entity_id=client.id, entity_label=client.full_name,
        summary=f"{client.full_name} ({client.phone}) — umumiy to'lov {format_money(body.amount)}, "
                f"qoldiq {format_money(result['total_remaining'])}",
        meta=result,
    )
    return result


# ─── STATS ───────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(ctx=Depends(owner_shop)):
    user, shop = ctx

    rows = await Debt.get_motor_collection().aggregate([
        {"$match": {"shop_id": shop.id}},
        {"$group": {
            "_id": "$status",
            "n": {"$sum": 1},
            "remaining": {"$sum": "$remaining"},
            "paid": {"$sum": "$paid_amount"},
        }},
    ]).to_list(length=None)
    by = {r["_id"]: r for r in rows}

    def g(status, key, default=0):
        return by.get(status, {}).get(key, default)

    active_n = g("open", "n") + g("partial", "n")
    active_rem = g("open", "remaining") + g("partial", "remaining")
    overdue_rem = g("overdue", "remaining")

    # TEZLIK: ilgari har bir oy uchun alohida so'rov ketardi (6 ta borish).
    # Endi bitta aggregation oylar bo'yicha guruhlaydi.
    monthly = await monthly_debt_stats({"shop_id": shop.id})

    return {
        "clients": await Client.find(Client.shop_id == shop.id, Client.status == "active").count(),
        "active_debts": active_n,
        "overdue_debts": g("overdue", "n"),
        "closed_debts": g("closed", "n"),
        "active_remaining": active_rem,
        "overdue_remaining": overdue_rem,
        "total_remaining": active_rem + overdue_rem,
        "total_collected": sum(r["paid"] for r in rows),
        "monthly": monthly,
    }


# ─── CONTACT ─────────────────────────────────────────────────────────────────

class ContactBody(BaseModel):
    message: str = Field(min_length=3, max_length=1000)


@router.post("/contact", dependencies=[Depends(write_rate_limit), Depends(user_write_rate_limit)])
async def send_contact(body: ContactBody, ctx=Depends(owner_shop)):
    user, shop = ctx
    text = body.message.strip()

    await SupportMessage(
        shop_id=shop.id, user_telegram_id=user.telegram_id,
        user_full_name=user.full_name, shop_name=shop.name,
        user_phone=user.phone, message=text,
    ).insert()

    admin_tid = await cache.admin_telegram_id()
    if admin_tid:
        await notify_telegram(
            admin_tid,
            f"📩 <b>Yangi xabar</b>\n\n👤 {esc(user.full_name)}\n🏪 {esc(shop.name)}\n\n💬 {esc(text)}",
        )

    return {"ok": True}



# ─── EXCEL EKSPORT ───────────────────────────────────────────────────────────

@router.post("/export")
async def export_report(ctx=Depends(owner_shop)):
    """Do'kon hisobotini Excel qilib Telegram orqali yuboradi.

    Mini App ichida faylni to'g'ridan-to'g'ri yuklab olish noqulay,
    shuning uchun fayl botga hujjat sifatida jo'natiladi.

    Server yukini cheklash: bir vaqtda bitta hisobot + kuniga
    EXPORT_DAILY_LIMIT marta.
    """
    from app.config import settings
    from app.core.ratelimit import limiter
    from app.utils import reports

    user, shop = ctx
    shop_key = str(shop.id)

    # Takror bosilgan tugma serverni ikkinchi marta ishlatmasin
    if reports.is_busy(shop_key):
        raise HTTPException(429, "Hisobot allaqachon tayyorlanmoqda — biroz kuting")

    # Kunlik limit (do'kon bo'yicha, IP emas — mobil internetda IP o'zgarib turadi)
    await limiter.check(f"export:{shop_key}", settings.EXPORT_DAILY_LIMIT, 86400)

    if not user.telegram_id:
        raise HTTPException(400, "Telegram hisobingiz topilmadi")

    built = await reports.build(shop)
    if not built:
        raise HTTPException(400, "Hisobot uchun ma'lumot yo'q")

    content, filename, n_clients, n_debts = built

    from aiogram.types import BufferedInputFile
    from app.bot.main import bot
    try:
        await bot.send_document(
            user.telegram_id,
            BufferedInputFile(content, filename=filename),
            caption=(
                f"📊 <b>{esc(shop.name)}</b> — hisobot\n"
                f"👥 Qarzdorlar: {n_clients} ta\n"
                f"🧾 Qarzlar: {n_debts} ta"
            ),
        )
    except Exception as e:      # noqa: BLE001
        logger.warning("Hisobot yuborilmadi (%s): %s", user.telegram_id, e)
        raise HTTPException(502, "Fayl yuborilmadi. Botni bloklamaganingizni tekshiring.")

    await audit.log_owner(
        user, shop, "report.export",
        summary=f"Excel hisobot yuklandi ({n_debts} qarz)",
    )
    return {"ok": True, "filename": filename, "clients": n_clients, "debts": n_debts}
