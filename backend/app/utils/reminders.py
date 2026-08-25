"""Qarzdorga ketadigan eslatmalar — matn va yuborish mantiqi bir joyda.

Tizimda to'rt xil eslatma bor:

  • yangi qarz   — qarz yozilgan zahoti (`debt_notification`)
  • oldindan     — muddat tugashiga 1 kun qolganda yoki o'sha kuni
  • KUNLIK       — muddati o'tgan qarzlar uchun HAR KUNI, to'lanmaguncha
  • qo'lda       — do'kondor «Eslatma yuborish» tugmasini bosganda

Matn bir joyda yozilgani uchun keyinchalik SMS qo'shilganda ham
o'zgartirish faqat shu faylda bo'ladi.
"""
import logging
from datetime import datetime
from typing import Iterable, Optional

from app.models import Debt
from app.utils.helpers import (
    esc, format_date, format_money, overdue_days,
)

logger = logging.getLogger(__name__)

# Xabarda nechta qarz raqami sanab o'tiladi — qolgani "… va yana N ta"
MAX_LINES = 5


def _lines(debts: Iterable[Debt]) -> str:
    """Har bir qarz uchun bitta qator: raqam, qoldiq, muddat."""
    items = list(debts)
    out = []
    for d in items[:MAX_LINES]:
        due = f" · {format_date(d.due_date)}" if d.due_date else " · muddatsiz"
        out.append(f"  • {d.debt_number} — {format_money(d.remaining)}{due}")
    if len(items) > MAX_LINES:
        out.append(f"  • … va yana {len(items) - MAX_LINES} ta")
    return "\n".join(out)


def _body(debts: list[Debt], total: int) -> str:
    """Bitta qarz bo'lsa — qisqa; ko'p bo'lsa — ro'yxat."""
    if len(debts) == 1:
        d = debts[0]
        due = format_date(d.due_date) if d.due_date else "muddatsiz"
        return f"💰 Qarz: <b>{format_money(total)}</b>\n📅 Muddat: {due}"
    return f"💰 {len(debts)} ta qarz, jami: <b>{format_money(total)}</b>\n{_lines(debts)}"


# ─── 1) Muddat yaqinlashdi ────────────────────────────────────────────────────

def due_soon_message(shop_name: str, debts: list[Debt], total: int, *, today: bool) -> str:
    """«Bugun/ertaga muddat tugaydi» eslatmasi."""
    title = "Bugun qarz muddati tugaydi" if today else "Ertaga qarz muddati tugaydi"
    return (
        f"⏰ <b>{title}</b>\n\n"
        f"🏪 {esc(shop_name)}\n{_body(debts, total)}\n\n"
        f"<i>Iltimos, to'lovni unutmang.</i>"
    )


# ─── 2) Muddat o'tdi — kunlik eslatma ─────────────────────────────────────────

def overdue_message(
    shop_name: str,
    overdue: list[Debt],
    other: list[Debt],
    *,
    day: int = 1,
) -> str:
    """Muddati o'tgan qarzlar uchun kunlik ogohlantirish.

    `other` — muddati hali kelmagan yoki muddatsiz qarzlar. Ular
    eslatmani ishga tushirmaydi, lekin qarzdor umumiy qoldig'ini
    ko'rishi uchun xabarga qo'shiladi.
    """
    overdue_total = sum(d.remaining for d in overdue)
    grand_total = overdue_total + sum(d.remaining for d in other)

    late = max(overdue_days(d.due_date) for d in overdue) if overdue else 0
    late_text = "bugun tugadi" if late == 0 else f"<b>{late} kun</b> oldin tugagan"

    msg = (
        f"🔴 <b>Qarz muddati o'tdi</b>\n\n"
        f"🏪 {esc(shop_name)}\n"
        f"⏳ Muddat {late_text}\n\n"
        f"💰 To'lanishi kerak: <b>{format_money(overdue_total)}</b>\n"
        f"{_lines(overdue)}"
    )

    if other:
        other_total = grand_total - overdue_total
        msg += (
            f"\n\n📋 Muddati kelmagan qarzlar: {format_money(other_total)}\n"
            f"💵 Umumiy qarzingiz: <b>{format_money(grand_total)}</b>"
        )

    msg += "\n\n<i>Iltimos, do'kon bilan bog'laning yoki to'lovni amalga oshiring.</i>"

    # Kundan kunga takrorlanadigan xabar ko'zga tashlanmay qoladi —
    # nechanchi kun ekanini ko'rsatib turamiz
    if day > 1:
        msg += f"\n\n<i>Eslatma #{day}</i>"
    return msg


# ─── 3) Do'kondor qo'lda yuborgan eslatma ─────────────────────────────────────

def manual_message(shop_name: str, debts: list[Debt], total: int) -> str:
    """«Eslatma yuborish» tugmasi bosilganda ketadigan xabar."""
    has_overdue = any(d.status == "overdue" for d in debts)
    head = "🔴 <b>Qarzingiz muddati o'tgan</b>" if has_overdue else "🔔 <b>Qarz eslatmasi</b>"
    return (
        f"{head}\n\n"
        f"🏪 {esc(shop_name)}\n{_body(debts, total)}\n\n"
        f"<i>Do'kon sizga eslatma yubordi.</i>"
    )


# ─── 4) Qarz yozilganda muddat yaqin bo'lsa ───────────────────────────────────

def due_urgency(due_date: Optional[datetime]) -> tuple[bool, str]:
    """Yangi qarz uchun: eslatma jadvalini o'tkazib yuborish kerakmi?

    Muammо: eslatma jadvali kuniga bir marta (10:30) ishlaydi. Soat 14:00
    da yozilgan va bugun/ertaga muddati tugaydigan qarz oldindan
    ogohlantirishsiz qolardi — keyingi ishga tushishda u allaqachon
    «muddati o'tgan» bo'lardi.

    Yechim: bunday qarzda ogohlantirish DARHOL yangi qarz xabariga
    qo'shiladi va `due_reminder_sent` belgilanadi (takror ketmasin).

    Returns: (jadvaldan chiqarilsinmi, xabarga qo'shiladigan matn)
    """
    from app.utils.helpers import local_day_bounds

    if not due_date:
        return False, ""

    today_end = local_day_bounds()[1]
    tomorrow_end = local_day_bounds(offset_days=1)[1]

    if due_date <= today_end:
        return True, "\n\n⏰ <b>Muddat bugun tugaydi!</b>"
    if due_date <= tomorrow_end:
        return True, "\n\n⏰ <b>Muddat ertaga tugaydi.</b>"
    return False, ""
