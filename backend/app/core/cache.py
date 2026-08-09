"""Qisqa muddatli xotira keshi.

Ba'zi ma'lumotlar deyarli o'zgarmaydi, lekin har bir so'rovda bazadan
qayta o'qiladi. Masalan `AppSettings` — 8 xil joyda so'raladi va yiliga
bir necha marta o'zgaradi. Kesh MongoDB'ga keraksiz borishlarni yo'q qiladi.

Kesh qisqa muddatli (soniyalar) — sozlama o'zgarsa bir necha soniyada
o'zi yangilanadi, bundan tashqari `invalidate()` bilan darhol tozalanadi.
"""
import time
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_store: dict[str, tuple[float, Any]] = {}


async def get_or_set(key: str, ttl: float, loader: Callable):
    """Keshdan oladi; bo'lmasa `loader()` chaqirib saqlaydi."""
    now = time.monotonic()
    hit = _store.get(key)
    if hit and hit[0] > now:
        return hit[1]

    value = await loader()
    _store[key] = (now + ttl, value)

    # Xotira cheksiz o'smasin
    if len(_store) > 500:
        for k in [k for k, (exp, _) in _store.items() if exp <= now]:
            _store.pop(k, None)
    return value


def invalidate(key: Optional[str] = None) -> None:
    """Bitta kalitni yoki butun keshni tozalaydi."""
    if key is None:
        _store.clear()
    else:
        _store.pop(key, None)


# ─── Tayyor yordamchilar ──────────────────────────────────────────────────────

SETTINGS_KEY = "app_settings"
SETTINGS_TTL = 30.0


async def app_settings():
    """Tizim sozlamalari (30 soniya keshlanadi)."""
    from app.models import AppSettings
    return await get_or_set(SETTINGS_KEY, SETTINGS_TTL, AppSettings.find_one)


def invalidate_settings() -> None:
    invalidate(SETTINGS_KEY)


async def admin_telegram_id() -> Optional[int]:
    """Xabarlar yuboriladigan asosiy admin ID si."""
    s = await app_settings()
    return s.admin_telegram_id if s else None
