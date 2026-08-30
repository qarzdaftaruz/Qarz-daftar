"""
Oddiy, tashqi xizmatsiz rate limiter (sliding window).

Railway'da bitta instans ishlaganda yetarli. Bir nechta replikaga
o'tilsa, Redis'ga ko'chirish kerak (REDIS_URL bilan) — pastdagi
`RateLimiter` interfeysi o'zgarmaydi.
"""
import time
import asyncio
import ipaddress
import logging
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import Depends, HTTPException, Request, status

from app.config import settings
from app.core.tma import get_tma_user

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding-window limiter.

    XATO TUZATILDI (jiddiy): ilgari `_cleanup` BARCHA kalitlarni o'sha
    paytda kelgan so'rovning oynasi bilan tozalardi. Har bir so'rovda
    ishlaydigan umumiy limit oynasi 60 soniya — natijada 900 soniyalik
    login oynasi ham, 86400 soniyalik kunlik eksport oynasi ham
    60 soniyagacha qisqarib ketardi. Ya'ni:

      • `EXPORT_DAILY_LIMIT` (kuniga 5 ta hisobot) amalda ishlamasdi —
        bir daqiqa kutgan do'kondor cheksiz hisobot yasay olardi;
      • `LOGIN_MAX_ATTEMPTS` 15 daqiqada 5 marta emas, har daqiqada
        5 marta bo'lib qolgandi (soatiga 300 ta parol urinishi).

    Endi har bir kalit o'z oynasini eslab qoladi va faqat shu oyna
    bo'yicha tozalanadi.
    """

    def __init__(self):
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._windows: Dict[str, int] = {}          # kalit → o'z oynasi
        self._blocked: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup = 0.0

    async def check(self, key: str, limit: int, window: int, block_seconds: int = 0) -> None:
        """Limitdan oshsa HTTP 429 ko'taradi."""
        now = time.monotonic()
        async with self._lock:
            self._cleanup(now)

            until = self._blocked.get(key)
            if until and until > now:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Juda ko'p urinish. {int(until - now)} soniyadan keyin qayta urining.",
                    headers={"Retry-After": str(int(until - now))},
                )

            bucket = self._hits[key]
            self._windows[key] = window
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

    async def peek(self, key: str, limit: int, window: int) -> bool:
        """Hisoblagichga tegmasdan «limit tugadimi?» deb tekshiradi."""
        now = time.monotonic()
        async with self._lock:
            if (self._blocked.get(key) or 0) > now:
                return False
            bucket = self._hits.get(key)
            if not bucket:
                return True
            return sum(1 for t in bucket if now - t <= window) < limit

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._hits.pop(key, None)
            self._windows.pop(key, None)
            self._blocked.pop(key, None)

    def _cleanup(self, now: float) -> None:
        """Xotira o'smasligi uchun eskirgan kalitlarni tozalash.

        Har bir kalit O'Z oynasi bo'yicha tozalanadi.
        """
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now
        for key in list(self._hits.keys()):
            bucket = self._hits[key]
            window = self._windows.get(key, 60)
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if not bucket:
                del self._hits[key]
                self._windows.pop(key, None)
        for key, until in list(self._blocked.items()):
            if until <= now:
                del self._blocked[key]


limiter = RateLimiter()


def _is_proxy_peer(host: Optional[str]) -> bool:
    """To'g'ridan-to'g'ri ulangan tomon ishonchli proksimi.

    Railway'da (va har qanday konteyner platformasida) edge proksi ilova
    bilan ichki tarmoq orqali gaplashadi — ya'ni TCP manzili doim
    xususiy/loopback bo'ladi. Agar manzil OMMAVIY bo'lsa, demak so'rov
    proksidan o'tmay to'g'ridan-to'g'ri kelgan va uning
    `X-Forwarded-For` sarlavhasiga ishonib bo'lmaydi.

    Bu qatlam bo'lmasa, ilovaga to'g'ridan-to'g'ri yetib kelgan hujumchi
    har so'rovda boshqa IP yozib, barcha cheklovlarni chetlab o'tardi.
    """
    if not host:
        return False
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        # Manzilni o'qib bo'lmadi (unix soket, nostandart sozlama) —
        # ISHONMAYMIZ. Bu holda `X-Forwarded-For` e'tiborga olinmaydi va
        # cheklov TCP manzili bo'yicha ishlaydi: eng yomoni bir nechta
        # mijoz bitta hisoblagichni bo'lishadi, lekin hech kim cheklovni
        # chetlab o'tolmaydi.
        return False
    return addr.is_private or addr.is_loopback or addr.is_link_local


def _pick_forwarded(xff: str) -> Optional[str]:
    """`X-Forwarded-For` dan HAQIQIY mijoz IP sini ajratib olish.

    XAVFSIZLIK (jiddiy): ilgari ro'yxatning BIRINCHI qiymati olinardi.
    Bu qiymatni mijozning o'zi yozadi — proksi uni faqat oxiriga qo'shadi.
    Ya'ni har bir so'rovda tasodifiy `X-Forwarded-For: 1.2.3.4` yuborib,
    IP bo'yicha barcha cheklovlarni chetlab o'tish mumkin edi:

      • admin login uchun 15 daqiqada 5 ta urinish cheklovi,
      • umumiy DoS himoyasi (daqiqasiga 120 so'rov),
      • yozuv amallari limiti.

    Ishonchli proksilar soni `TRUSTED_PROXY_HOPS` (Railway uchun 1).
    Oxiridan shuncha qadam sanaymiz — bu qiymatni mijoz yozolmaydi.
    """
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    if not parts:
        return None
    hops = max(1, settings.TRUSTED_PROXY_HOPS)
    # hops=1 → oxirgi qiymat (edge proksi yozgan haqiqiy mijoz IP si)
    index = len(parts) - hops
    if index < 0:
        # Kutilganidan KAM qiymat: demak so'rov kutilgan proksilardan
        # o'tmagan. Bunday sarlavhaga ishonib bo'lmaydi — `None` qaytaramiz
        # va chaqiruvchi haqiqiy TCP manzilidan foydalanadi (uni soxta
        # qilib bo'lmaydi).
        return None
    return parts[index]


def client_ip(request: Request) -> str:
    """Proksi orqasidagi haqiqiy mijoz IP si."""
    peer = request.client.host if request.client else None
    xff = request.headers.get("x-forwarded-for")
    if xff and _is_proxy_peer(peer):
        found = _pick_forwarded(xff)
        if found:
            return found
    return peer or "unknown"


def client_ip_from_scope(scope) -> str:
    """IP ni to'g'ridan-to'g'ri ASGI scope'dan olish.

    TEZLIK: middleware ichida `Request` obyektini yasash shart emas —
    bizga faqat bitta header kerak.
    """
    client = scope.get("client")
    peer = client[0] if client else None
    if _is_proxy_peer(peer):
        for key, value in scope.get("headers", []):
            if key == b"x-forwarded-for":
                found = _pick_forwarded(value.decode("latin-1"))
                if found:
                    return found
                break
    return peer or "unknown"


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
    """Yozuv amallari uchun IP bo'yicha QO'POL DoS to'sig'i.

    XATO TUZATILDI: limit 60/daqiqa edi va bu O'zbekiston mobil
    operatorlarida haqiqiy muammo tug'dirardi. Ular CGNAT ishlatadi —
    yuzlab abonent bitta ommaviy IP orqali chiqadi. Ya'ni 20 ta do'kondor
    daqiqasiga 3 tadan qarz kiritsa, limit tugab, aybsiz foydalanuvchilar
    «Juda ko'p so'rov» xatosini olardi. (Loglarda bitta sessiyaning
    so'rovlari 37.110.211.138 va .146 dan kelgani ham shuni tasdiqlaydi:
    mobil IP sessiya davomida ham o'zgarib turadi.)

    Haqiqiy nazorat `user_write_rate_limit` da — u Telegram ID bo'yicha
    ishlaydi va HAR BIR yozuv endpointiga shu bilan birga qo'yilgan
    (tekshirilgan). Shuning uchun bu yerdagi IP limiti faqat qo'pol
    to'siq bo'lib qoladi: bitta manbadan kelayotgan ochiq suiiste'molni
    to'xtatadi, lekin oddiy foydalanuvchilarga tegmaydi.
    """
    await rate_limit(request, scope="write", limit=300, window=60)


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
