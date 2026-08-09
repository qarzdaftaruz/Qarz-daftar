"""Audit log — muhim amallarni kim bajarganini yozib boradi.

Maqsad: "bu qarzni kim o'chirdi?", "do'konni kim blokladi?" kabi
savollarga aniq javob berish. Yozuv muvaffaqiyatsiz bo'lsa ham asosiy
amal to'xtamaydi — log hech qachon biznes oqimini buzmasligi kerak.
"""
import logging
from typing import Any, Optional

from fastapi import Request

from app.config import settings
from app.models import AuditLog

logger = logging.getLogger(__name__)

# Yozuvlar shuncha kundan keyin avtomatik o'chadi (TTL indeks)
AUDIT_RETENTION_DAYS = settings.AUDIT_RETENTION_DAYS

# Super adminga darhol Telegram xabarnomasi yuboriladigan amallar.
# Bu ro'yxat ataylab qisqa — har bir kichik amaldan xabar kelsa,
# muhimlari ko'zdan qochadi.
NOTIFY_ACTIONS = {
    "shop.delete":     "🗑 Do'kon o'chirildi",
    "shop.purge":      "💀 Do'kon butunlay yo'q qilindi",
    "shop.restore":    "♻️ Do'kon qaytarildi",
    "debt.delete":     "🗑 Qarz o'chirildi",
    "admin.create":    "👤 Yangi admin qo'shildi",
    "admin.delete":    "👤 Admin o'chirildi",
    "auth.locked":     "🔒 Hisob bloklandi (parol tanlash urinishi)",
}


def _ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    try:
        from app.core.ratelimit import client_ip
        return client_ip(request)
    except Exception:      # noqa: BLE001
        return None


async def log(
    action: str,
    *,
    actor_type: str = "system",
    actor_name: str = "",
    actor_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[Any] = None,
    entity_label: Optional[str] = None,
    shop_id: Optional[Any] = None,
    summary: str = "",
    meta: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    ip = _ip(request)
    try:
        await AuditLog(
            actor_type=actor_type,
            actor_name=actor_name,
            actor_id=str(actor_id) if actor_id is not None else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            entity_label=entity_label,
            shop_id=shop_id,
            summary=summary,
            meta=meta or {},
            ip=ip,
        ).insert()
    except Exception as e:      # noqa: BLE001
        logger.warning("Audit yozuvi saqlanmadi (%s): %s", action, e)

    if action in NOTIFY_ACTIONS:
        await _notify_super_admins(action, actor_type, actor_name, summary, ip)


async def _notify_super_admins(
    action: str, actor_type: str, actor_name: str, summary: str, ip: Optional[str]
) -> None:
    """Muhim amal sodir bo'lganda super adminlarga darhol Telegram xabari.

    Panelni ochib ko'rmasangiz ham, sizsiz qilingan amaldan xabardor
    bo'lasiz. Xabar yuborilmasa ham audit yozuvi baribir saqlangan.
    """
    from app.config import settings
    from app.models import AdminAuth
    from app.utils.helpers import esc, format_datetime, notify_telegram
    from app.models import utcnow

    try:
        targets: set[int] = set(settings.super_admin_ids)
        async for a in AdminAuth.find(AdminAuth.is_super == True):    # noqa: E712
            if a.telegram_id:
                targets.add(a.telegram_id)
        if not targets:
            return

        title = NOTIFY_ACTIONS[action]
        actor_label = {"super_admin": "Super admin", "admin": "Admin", "owner": "Do'kondor"}.get(
            actor_type, actor_type
        )
        text = (
            f"⚠️ <b>{title}</b>\n\n"
            f"👤 {esc(actor_name)} ({actor_label})\n"
            f"🕒 {format_datetime(utcnow())}\n"
            + (f"🌐 {esc(ip)}\n" if ip else "")
            + f"\n{esc(summary)}"
        )
        for tid in targets:
            await notify_telegram(tid, text)
    except Exception as e:      # noqa: BLE001
        logger.warning("Audit xabarnomasi yuborilmadi (%s): %s", action, e)


async def log_admin(
    admin,
    action: str,
    *,
    request: Optional[Request] = None,
    **kwargs,
) -> None:
    """Admin panel amallari uchun qisqartma."""
    await log(
        action,
        actor_type="super_admin" if getattr(admin, "is_super", False) else "admin",
        actor_name=getattr(admin, "username", "?"),
        actor_id=getattr(admin, "id", None),
        request=request,
        **kwargs,
    )


async def log_owner(user, shop, action: str, **kwargs) -> None:
    """Do'kon egasi amallari uchun qisqartma."""
    await log(
        action,
        actor_type="owner",
        actor_name=getattr(user, "full_name", "?"),
        actor_id=getattr(user, "telegram_id", None),
        shop_id=getattr(shop, "id", None),
        **kwargs,
    )
