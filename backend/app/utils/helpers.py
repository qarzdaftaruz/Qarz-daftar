import re
import html
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytz

from app.models import utcnow

logger = logging.getLogger(__name__)

UZ_TZ = pytz.timezone("Asia/Tashkent")

_MONTHS = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]

# Grafik o'qlari uchun qisqa nomlar.
# Oddiy [:3] kesish "iyun" va "iyul" ni bir xil ("Iyu") qilib qo'yardi.
_MONTHS_SHORT = [
    "Yan", "Fev", "Mar", "Apr", "May", "Iyn",
    "Iyl", "Avg", "Sen", "Okt", "Noy", "Dek",
]


# ─── Vaqt bilan ishlash ───────────────────────────────────────────────────────

def as_utc(dt: datetime) -> datetime:
    """Naive sanani UTC deb belgilaydi (bazadan kelgan sanalar naive-UTC)."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def to_naive_utc(dt: datetime) -> datetime:
    """Har qanday sanani bazaga yozish uchun naive-UTC ga keltiradi."""
    return dt.replace(tzinfo=None) if dt.tzinfo is None else dt.astimezone(timezone.utc).replace(tzinfo=None)


def to_local(dt: datetime) -> datetime:
    """UTC → Toshkent vaqti."""
    return as_utc(dt).astimezone(UZ_TZ)


def local_day_bounds(now: Optional[datetime] = None, offset_days: int = 0) -> tuple[datetime, datetime]:
    """Toshkent vaqti bo'yicha kun chegaralari (naive-UTC da).

    `offset_days=1` — ertangi kun, `-1` — kecha.

    Ilgari UTC yarim tunidan hisoblangani uchun eslatmalar 5 soatga
    surilib ketardi — shu tuzatildi.
    """
    local_now = to_local(now or utcnow()) + timedelta(days=offset_days)
    start_local = UZ_TZ.localize(datetime(local_now.year, local_now.month, local_now.day, 0, 0, 0))
    end_local = UZ_TZ.localize(datetime(local_now.year, local_now.month, local_now.day, 23, 59, 59))
    return to_naive_utc(start_local), to_naive_utc(end_local)


def parse_due_date(dt: Optional[datetime]) -> Optional[datetime]:
    """Qaytarish sanasini kun oxiriga (Toshkent vaqti 23:59:59) keltiradi.

    Frontend `<input type="date">` dan faqat sana keladi (`2026-08-09`) va u
    UTC yarim tuni sifatida saqlanardi. Natijada Toshkentda soat 05:00 da
    qarz allaqachon "muddati o'tgan" bo'lib qolardi. Endi sana o'sha
    kunning oxirigacha amal qiladi.
    """
    if dt is None:
        return None
    if dt.tzinfo is None and (dt.hour, dt.minute, dt.second) == (0, 0, 0):
        end_local = UZ_TZ.localize(datetime(dt.year, dt.month, dt.day, 23, 59, 59))
        return to_naive_utc(end_local)
    return to_naive_utc(dt)


def month_starts(count: int = 6) -> list[datetime]:
    """Oxirgi `count` oyning boshlanish sanalari (naive-UTC), eskisidan yangisiga.

    Ilgari `timedelta(days=30)` ishlatilgani uchun oy nomlari
    takrorlanib/o'tkazib yuborilardi.
    """
    local_now = to_local(utcnow())
    year, month = local_now.year, local_now.month
    starts: list[datetime] = []
    for i in range(count - 1, -1, -1):
        y, m = year, month - i
        while m <= 0:
            m += 12
            y -= 1
        starts.append(to_naive_utc(UZ_TZ.localize(datetime(y, m, 1))))
    return starts


def month_label(dt: datetime, with_year: bool = False) -> str:
    local = to_local(dt)
    name = _MONTHS_SHORT[local.month - 1]
    return f"{name} {local.year}" if with_year else name


def format_date(dt: Optional[datetime]) -> str:
    if not dt:
        return "Muddatsiz"
    local = to_local(dt)
    return f"{local.day}-{_MONTHS[local.month - 1]}"


def format_datetime(dt: Optional[datetime]) -> str:
    if not dt:
        return "—"
    local = to_local(dt)
    return f"{local.day}-{_MONTHS[local.month - 1]}, {local.hour:02d}:{local.minute:02d}"


def is_overdue(due_date: Optional[datetime]) -> bool:
    if not due_date:
        return False
    return utcnow() > to_naive_utc(due_date)


def days_until(dt: datetime) -> int:
    return max(0, (to_naive_utc(dt) - utcnow()).days)


# ─── Format ───────────────────────────────────────────────────────────────────

def format_money(amount: int) -> str:
    return f"{amount:,} so'm".replace(",", " ")


def esc(text: Optional[str]) -> str:
    """Telegram HTML xabarlari uchun matnni xavfsizlash.

    Do'kon/mijoz nomida `<`, `&` bo'lsa xabar yuborilmay qolardi
    (Telegram "can't parse entities" xatosi) — bu ham HTML injeksiya edi.
    """
    return html.escape(text or "", quote=False)


def safe_regex(term: str, max_len: int = 64) -> str:
    """Foydalanuvchi qidiruv so'zini MongoDB $regex uchun xavfsizlash.

    Escape qilinmasa `(a+)+$` kabi so'rov bazani qotirishi (ReDoS) yoki
    `.*` bilan boshqa yozuvlarni ochib berishi mumkin edi.
    """
    return re.escape(term.strip()[:max_len])


# ─── Telefon ──────────────────────────────────────────────────────────────────

_PHONE_CLEAN = re.compile(r"[^\d+]")


def normalize_phone(phone: str) -> str:
    """+998901234567 ko'rinishiga keltiradi.

    Bir xil raqam turli formatda saqlanib, qarzdor o'z qarzini
    ko'rmay qolishining oldini oladi.
    """
    if not phone:
        return ""
    digits = _PHONE_CLEAN.sub("", phone.strip())
    digits = "+" + digits.lstrip("+").replace("+", "")
    body = digits[1:]
    if len(body) == 9 and body[0] in "3456789":       # 901234567
        body = "998" + body
    elif len(body) == 12 and body.startswith("998"):  # 998901234567
        pass
    elif len(body) == 13 and body.startswith("9998"):
        body = body[1:]
    return "+" + body


def is_valid_phone(phone: str) -> bool:
    return bool(re.fullmatch(r"\+\d{9,15}", phone or ""))


# ─── Qarz raqami ──────────────────────────────────────────────────────────────

async def generate_debt_number(shop_id) -> str:
    """Do'kon ichida takrorlanmaydigan qarz raqami.

    Ilgari mavjud qarzlar soni sanalardi — arxiv tozalashdan keyin yoki
    ikkita qarz bir vaqtda qo'shilganda raqamlar takrorlanib ketardi.
    Endi atomar `$inc` hisoblagichdan foydalaniladi.
    """
    from app.models import Shop, Debt

    doc = await Shop.get_motor_collection().find_one_and_update(
        {"_id": shop_id},
        {"$inc": {"debt_seq": 1}},
        projection={"debt_seq": 1},
        return_document=True,
    )
    if doc and doc.get("debt_seq"):
        seq = int(doc["debt_seq"])
    else:
        # Do'kon topilmadi (kutilmagan holat) — zaxira variant
        seq = await Debt.find(Debt.shop_id == shop_id).count() + 1

    # Eski bazalarda debt_seq 0 dan boshlanadi — mavjud raqamlar bilan to'qnashmasin
    if seq == 1:
        existing = await Debt.find(Debt.shop_id == shop_id).count()
        if existing:
            seq = existing + 1
            await Shop.get_motor_collection().update_one(
                {"_id": shop_id}, {"$set": {"debt_seq": seq}}
            )
    return f"QRZ-{seq:04d}"


# ─── Xabarlar ─────────────────────────────────────────────────────────────────

def debt_status_emoji(status: str) -> str:
    return {
        "open": "🟢", "partial": "🟡", "overdue": "🔴",
        "closed": "✅", "archived": "📦",
    }.get(status, "❓")


def debt_status_label(status: str) -> str:
    return {
        "open": "Ochiq", "partial": "Qisman to'langan", "overdue": "Muddati o'tgan",
        "closed": "Yopiq", "archived": "Arxivlangan",
    }.get(status, status)


def debt_notification(shop_name, amount, due_date=None, note=None) -> str:
    """Yangi qarz qo'shilganda qarzdorga ketadigan xabar."""
    lines = [
        f"📢 <b>{esc(shop_name)}</b>",
        f"💰 Yangi qarz: <b>{format_money(amount)}</b>",
    ]
    if due_date:
        lines.append(f"📅 Qaytarish sanasi: {format_date(due_date)}")
    if note:
        lines.append(f"📝 Izoh: {esc(note)}")
    return "\n".join(lines)


async def notify_debtor(phone: str, message_text: str):
    """Qarzdorni Telegram orqali xabardor qilish (xato bo'lsa ham oqim to'xtamaydi)."""
    try:
        from app.models import User
        from app.bot.main import bot

        normalized = normalize_phone(phone)
        candidates = list({phone, normalized})
        user = await User.find_one({
            "$or": [
                {"phone": {"$in": candidates}},
                {"extra_phones": {"$in": candidates}},
            ]
        })
        if user and user.telegram_id and not user.is_blocked:
            await bot.send_message(user.telegram_id, message_text)
    except Exception as e:      # noqa: BLE001
        logger.warning("Qarzdorga xabar yuborilmadi: %s", e)


async def notify_telegram(telegram_id: Optional[int], text: str, **kwargs) -> bool:
    """Telegram'ga xabar yuborish; xatolar yutiladi."""
    if not telegram_id:
        return False
    try:
        from app.bot.main import bot
        await bot.send_message(telegram_id, text, **kwargs)
        return True
    except Exception as e:      # noqa: BLE001
        logger.warning("Telegram xabari yuborilmadi (%s): %s", telegram_id, e)
        return False
