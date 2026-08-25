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


def end_of_local_day(dt: datetime) -> datetime:
    """Berilgan sananing Toshkent vaqti bo'yicha oxiri (23:59:59), naive-UTC da."""
    return to_naive_utc(UZ_TZ.localize(datetime(dt.year, dt.month, dt.day, 23, 59, 59)))


def parse_due_date(dt: Optional[datetime]) -> Optional[datetime]:
    """Qaytarish sanasini kun oxiriga (Toshkent vaqti 23:59:59) keltiradi.

    Frontend `<input type="date">` dan faqat sana keladi (`2026-08-09`) va u
    UTC yarim tuni sifatida saqlanardi. Natijada Toshkentda soat 05:00 da
    qarz allaqachon "muddati o'tgan" bo'lib qolardi. Endi sana o'sha
    kunning oxirigacha amal qiladi.

    Sana `Z` bilan (`2026-08-09T00:00:00Z`) kelgan holat ham hisobga olinadi —
    ba'zi brauzerlar `<input type="date">` qiymatini shunday jo'natadi.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        if (dt.hour, dt.minute, dt.second) == (0, 0, 0):
            return end_of_local_day(dt)
        return to_naive_utc(dt)

    # tz-bilan kelgan yarim tun — bu ham "faqat sana" degani
    utc = dt.astimezone(timezone.utc)
    if (utc.hour, utc.minute, utc.second) == (0, 0, 0):
        return end_of_local_day(utc)
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


def days_left(dt: Optional[datetime]) -> int:
    """Muddatgacha qolgan kunlar — MANFIY bo'lishi mumkin.

    Ilgari `days_until` ishlatilardi va u manfiy kunni nolga qisqartirardi:
    allaqachon tugagan obuna ham "0 kundan so'ng tugaydi" deb ko'rinardi.
    """
    if dt is None:
        return 0
    return (to_naive_utc(dt) - utcnow()).days


def overdue_days(due_date: Optional[datetime]) -> int:
    """Muddat o'tganiga necha kun bo'ldi (kalendar kunlari, Toshkent vaqti)."""
    if not due_date:
        return 0
    due_local = to_local(due_date).date()
    today_local = to_local(utcnow()).date()
    return max(0, (today_local - due_local).days)


def subscription_end_at(shop) -> Optional[datetime]:
    """Do'kon qachongacha ishlashi mumkin: obuna bo'lsa u, aks holda trial."""
    return getattr(shop, "subscription_end", None) or getattr(shop, "trial_end", None)


def restart_trial_if_expired(shop) -> bool:
    """Tasdiqlash paytida muddati tugagan bo'lsa sinov davrini qaytadan boshlaydi.

    Nima uchun: do'kon «pending» holatida ham ishlaydi, shuning uchun u
    obuna nazoratiga kiradi. Lekin admin tasdiqlashni kechiktirsa, ayb
    do'kondorda emas — tasdiqlangan zahoti unga to'liq sinov muddati
    beriladi. Aks holda tasdiqlangan do'kon darhol yopilib qolardi.
    """
    from app.config import settings

    if not subscription_expired(shop):
        return False
    now = utcnow()
    shop.trial_start = now
    shop.trial_end = now + timedelta(days=settings.TRIAL_DAYS)
    shop.subscription_end = None
    shop.expired_at = None
    shop.warning_sent = False
    if shop.block_reason == "Obuna muddati tugadi":
        shop.block_reason = None
    return True


def subscription_expired(shop) -> bool:
    """Do'kon obunasi tugaganmi.

    Scheduler kuniga ikki marta tekshiradi, lekin so'rov vaqtida ham
    tekshiriladi — aks holda muddat tugagan do'kon keyingi vazifagacha
    (12 soatgacha) ishlayverardi.
    """
    from app.config import settings

    if not settings.SUBSCRIPTION_ENFORCE:
        return False
    end = subscription_end_at(shop)
    if not end:
        return False
    deadline = to_naive_utc(end) + timedelta(days=settings.SUBSCRIPTION_GRACE_DAYS)
    return utcnow() > deadline


def debt_status_for(remaining: int, paid_amount: int, due_date: Optional[datetime]) -> str:
    """Qarzning to'g'ri holatini hisoblaydi.

    XATO TUZATILDI: ilgari qisman to'lov qabul qilinganda holat doim
    `partial` ga o'tardi — muddati o'tgan qarz shu bilan `overdue`
    ro'yxatidan tushib qolardi. Ya'ni 1 so'm to'lab, eslatmalardan
    va "muddati o'tgan" belgisidan qutulish mumkin edi.
    """
    if remaining <= 0:
        return "closed"
    if is_overdue(due_date):
        return "overdue"
    return "partial" if paid_amount > 0 else "open"


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


def phone_variants(phone: Optional[str]) -> list[str]:
    """Raqamning bazada uchrashi mumkin bo'lgan ko'rinishlari."""
    if not phone:
        return []
    return sorted({phone, normalize_phone(phone)} - {""})


async def find_debtor_user(phone: str):
    """Telefon raqami bo'yicha bot foydalanuvchisini topadi."""
    from app.models import User

    candidates = phone_variants(phone)
    if not candidates:
        return None
    return await User.find_one({
        "$or": [
            {"phone": {"$in": candidates}},
            {"extra_phones": {"$in": candidates}},
        ]
    })


async def resolve_debtor_users(phones: list[str]) -> dict[str, "object"]:
    """Ko'p raqam → foydalanuvchi jadvali, BITTA so'rovda.

    TEZLIK: ommaviy eslatmalarda har bir qarzdor uchun alohida
    `find_one` ketardi. 500 qarzdorga eslatma = 500 ta borish edi.
    Endi barcha raqamlar bitta `$in` so'rovida topiladi.
    """
    from app.models import User

    candidates = sorted({v for p in phones for v in phone_variants(p)})
    if not candidates:
        return {}

    users = await User.find({
        "$or": [
            {"phone": {"$in": candidates}},
            {"extra_phones": {"$in": candidates}},
        ]
    }).to_list()

    by_phone: dict = {}
    for u in users:
        if u.is_blocked or not u.telegram_id:
            continue
        for p in [u.phone, *u.extra_phones]:
            for variant in phone_variants(p):
                by_phone.setdefault(variant, u)
    return by_phone


async def send_to_user(user, message_text: str) -> bool:
    """Foydalanuvchiga xabar (bloklangan/botni o'chirgan bo'lsa — False)."""
    if not user or not user.telegram_id or user.is_blocked:
        return False
    return await notify_telegram(user.telegram_id, message_text)


async def notify_debtor(phone: str, message_text: str) -> bool:
    """Qarzdorni Telegram orqali xabardor qilish.

    Xato bo'lsa ham oqim to'xtamaydi; xabar yetib borgani `True`/`False`
    bilan qaytadi — do'kondorga "eslatma yuborildimi" deb ko'rsatish uchun.

    KELAJAK: SMS qo'shilganda shu funksiya yagona kirish nuqtasi bo'ladi —
    Telegram topilmasa SMS ga tushadi, chaqiruv joylari o'zgarmaydi.
    """
    try:
        user = await find_debtor_user(phone)
        return await send_to_user(user, message_text)
    except Exception as e:      # noqa: BLE001
        logger.warning("Qarzdorga xabar yuborilmadi: %s", e)
        return False


# ─── Fon rejimi ───────────────────────────────────────────────────────────────
# TEZLIK: API so'rovi ichida Telegram javobini kutish shart emas. Qarz
# bazaga yozilgan — xabar bir necha yuz millisekunddan keyin yetib borsa
# ham hech narsa o'zgarmaydi. Kutish esa har bir «Saqlash» tugmasiga
# 150–400 ms qo'shardi.
#
# Natijaga qarab ish tutadigan joylar (masalan «eslatma yuborildimi?»
# tugmasi yoki kunlik eslatma jadvali) yuqoridagi await'li variantni
# ishlatadi — o'sha yerda javob kerak.

def notify_debtor_bg(phone: str, message_text: str) -> None:
    """Qarzdorga xabar — navbatga qo'yiladi, so'rov kutmaydi."""
    from app.core import tasks
    tasks.spawn(notify_debtor(phone, message_text))


def notify_telegram_bg(telegram_id: Optional[int], text: str, **kwargs) -> None:
    """Telegram xabari — navbatga qo'yiladi, so'rov kutmaydi."""
    if not telegram_id:
        return
    from app.core import tasks
    tasks.spawn(notify_telegram(telegram_id, text, **kwargs))


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
