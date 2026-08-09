"""Kalit bo'yicha asinxron qulflar.

Nima uchun kerak: pul bilan bog'liq amallar «o'qi → hisobla → yoz»
ketma-ketligidan iborat. Foydalanuvchi tugmani ikki marta bossa yoki
ikkita qurilmadan bir vaqtda ishlatsa, ikkala so'rov ham eski qoldiqni
o'qib, to'lovni IKKI MARTA yozib yuborishi mumkin.

DIQQAT: bu qulf faqat bitta jarayon ichida ishlaydi. Railway'da
`numReplicas: 1` bo'lgani uchun shu yetarli. Bir nechta replikaga
o'tilsa, MongoDB tranzaksiyalari yoki Redis qulfiga ko'chirish kerak.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

_locks: dict[str, asyncio.Lock] = {}
_MAX_LOCKS = 1000


def _get(key: str) -> asyncio.Lock:
    lock = _locks.get(key)
    if lock is None:
        lock = _locks[key] = asyncio.Lock()
    if len(_locks) > _MAX_LOCKS:
        # Ishlatilmayotgan qulflarni tozalaymiz — xotira cheksiz o'smasin
        for k in [k for k, v in _locks.items() if not v.locked()][: _MAX_LOCKS // 2]:
            _locks.pop(k, None)
    return lock


def is_locked(key: str) -> bool:
    lock = _locks.get(key)
    return bool(lock and lock.locked())


@asynccontextmanager
async def guard(key: str, timeout: float = 15.0):
    """Kalit bo'yicha eksklyuziv kirish.

    Kutish `timeout` dan oshsa foydalanuvchiga tushunarli 429 qaytadi —
    so'rov cheksiz osilib qolmaydi va 500 xato ham chiqmaydi.
    """
    from fastapi import HTTPException

    lock = _get(key)
    try:
        await asyncio.wait_for(lock.acquire(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("Qulfni kutish muddati tugadi: %s", key)
        raise HTTPException(
            429, "Amal hozir bajarilmoqda — bir necha soniyadan keyin qayta urining",
            headers={"Retry-After": "5"},
        )
    try:
        yield
    finally:
        lock.release()
