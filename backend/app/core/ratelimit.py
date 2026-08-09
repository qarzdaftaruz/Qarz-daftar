"""
Oddiy, tashqi xizmatsiz rate limiter (sliding window).

Railway'da bitta instans ishlaganda yetarli. Bir nechta replikaga
o'tilsa, Redis'ga ko'chirish kerak (REDIS_URL bilan) — pastdagi
`RateLimiter` interfeysi o'zgarmaydi.
"""
import time
import asyncio
import logging
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import Depends, HTTPException, Request, status

from app.config import settings
from app.core.tma import get_tma_user

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self):
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._blocked: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup = 0.0

    async def check(self, key: str, limit: int, window: int, block_seconds: int = 0) -> None:
        """Limitdan oshsa HTTP 429 ko'taradi."""
        now = time.monotonic()
        async with self._lock:
            self._cleanup(now, window)

            until = self._blocked.get(key)
            if until and until > now:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Juda ko'p urinish. {int(until - now)} soniyadan keyin qayta urining.",
                    headers={"Retry-After": str(int(until - now))},
                )

            bucket = self._hits[key]
            while bucket and now - bucket[0] > window:
                bucket.popleft()

            if len(bucket) >= limit:
                if block_seconds:
                    self._blocked[key] = now + block_seconds
                retry = block_seconds or int(window - (now - bucket[0])) + 1
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Juda ko'p so'rov. {retry} soniyadan keyin qayta urining.",
                    headers={"Retry-After": str(retry)},
                )

            bucket.append(now)

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._hits.pop(key, None)
            self._blocked.pop(key, None)

    def _cleanup(self, now: float, window: int) -> None:
        """Xotira o'smasligi uchun eskirgan kalitlarni tozalash."""
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now
        for key in list(self._hits.keys()):
            bucket = self._hits[key]
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if not bucket:
                del self._hits[key]
        for key, until in list(self._blocked.items()):
            if until <= now:
                del self._blocked[key]


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    """Railway proxy orqasidagi haqiqiy IP.

    X-Forwarded-For ni faqat ishonchli proksi (Railway edge) qo'yadi;
    birinchi qiymat — mijoz IP si.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit(
    request: Request,
    *,
    scope: str,
    limit: int,
    window: int,
    block_seconds: int = 0,
    extra: Optional[str] = None,
) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    key = f"{scope}:{client_ip(request)}"
    if extra:
        key += f":{extra}"
    await limiter.check(key, limit, window, block_seconds)


# ─── Tayyor dependency'lar ────────────────────────────────────────────────────

async def login_rate_limit(request: Request) -> None:
    """Admin login / parol tiklash — brute-force himoyasi."""
    await rate_limit(
        request,
        scope="login",
        limit=settings.LOGIN_MAX_ATTEMPTS,
        window=settings.LOGIN_WINDOW_SECONDS,
        block_seconds=settings.LOGIN_LOCKOUT_SECONDS,
    )


async def auth_rate_limit(request: Request) -> None:
    """Mini App auth — initData bilan urinishlarni cheklash."""
    await rate_limit(request, scope="tma-auth", limit=30, window=60)


async def write_rate_limit(request: Request) -> None:
    """Yozuv amallari (qarz/to'lov/xabar) uchun IP bo'yicha yumshoq limit."""
    await rate_limit(request, scope="write", limit=60, window=60)


async def user_write_rate_limit(tma: dict = Depends(get_tma_user)) -> None:
    """Yozuv amallari uchun FOYDALANUVCHI bo'yicha limit.

    IP bo'yicha limit mobil internetda yetarli emas: bir operatorning
    yuzlab mijozi bitta NAT IP orqali chiqadi — biri limitni tugatsa,
    qolganlari ham to'sib qo'yilardi. Telegram ID bo'yicha cheklash
    aniqroq va adolatliroq.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return
    await limiter.check(f"user-write:{tma['telegram_id']}", 60, 60)
