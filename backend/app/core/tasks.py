"""Fon navbati — javobni kutkazmaydigan ishlar uchun.

MUAMMO: har bir qarz, to'lov, blok yoki tasdiqlash amalida Telegram'ga
xabar yuborilardi va bu **so'rov ichida** kutilardi. Telegram serveriga
borib-kelish odatda 150–400 ms, sekin paytda 2 soniyagacha. Ya'ni
do'kondor «Saqlash» bosganda ilova shuncha vaqt qotib turardi —
ma'lumot allaqachon bazaga yozilgan bo'lsa ham.

Yomonroq holat: `audit.log` muhim amallarda BARCHA super adminlarga
xabar yuborardi. Uchta super admin = uchta ketma-ket Telegram so'rovi
bitta so'rov ichida. Muvaffaqiyatsiz login urinishlari ham shu yo'ldan
o'tgani uchun, parol tanlash hujumi serverni Telegram so'rovlari bilan
band qilib qo'yishi mumkin edi.

YECHIM: bunday ishlar navbatga tushadi va alohida ishchilar bajaradi.
So'rov darhol javob qaytaradi.

Navbat CHEKLANGAN: to'lib qolsa yangi vazifa qabul qilinmaydi va logga
ogohlantirish yoziladi. Cheksiz navbat xotirani yeb qo'yardi — bu
Railway konteynerida butun tizimni yiqitadi.
"""
import asyncio
import logging
from typing import Coroutine, Optional

logger = logging.getLogger(__name__)

DEFAULT_WORKERS = 2
DEFAULT_MAXSIZE = 2000

_queue: Optional[asyncio.Queue] = None
_workers: list[asyncio.Task] = []
_dropped = 0


async def _worker(name: str) -> None:
    assert _queue is not None
    while True:
        coro = await _queue.get()
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception as e:      # noqa: BLE001
            # Fon vazifasining xatosi hech qachon boshqa vazifani
            # yoki asosiy oqimni to'xtatmaydi
            logger.warning("Fon vazifasi xato tugadi (%s): %s", name, e)
        finally:
            _queue.task_done()


async def start(workers: int = DEFAULT_WORKERS, maxsize: int = DEFAULT_MAXSIZE) -> None:
    global _queue
    if _queue is not None:
        return
    _queue = asyncio.Queue(maxsize=maxsize)
    for i in range(max(1, workers)):
        _workers.append(asyncio.create_task(_worker(f"bg-{i}"), name=f"bg-worker-{i}"))
    logger.info("Fon navbati ishga tushdi (%s ishchi, hajm %s)", len(_workers), maxsize)


async def stop(drain_timeout: float = 5.0) -> None:
    """Qolgan vazifalarni qisqa vaqt kutadi, keyin to'xtatadi."""
    global _queue, _dropped
    if _queue is None:
        return
    try:
        await asyncio.wait_for(_queue.join(), timeout=drain_timeout)
    except asyncio.TimeoutError:
        logger.warning("Fon navbati to'liq bo'shamadi (%s ta qoldi)", _queue.qsize())

    for task in _workers:
        task.cancel()
    await asyncio.gather(*_workers, return_exceptions=True)
    _workers.clear()
    _queue = None
    if _dropped:
        logger.warning("Jami %s ta fon vazifasi navbat to'lgani uchun tashlab yuborildi", _dropped)
    _dropped = 0
    logger.info("Fon navbati to'xtatildi")


def spawn(coro: Coroutine) -> bool:
    """Vazifani navbatga qo'yadi. Darhol qaytadi.

    `False` qaytsa — navbat to'lgan yoki tizim to'xtatilmoqda; vazifa
    bajarilmaydi. Chaqiruvchi buni e'tiborsiz qoldirishi mumkin, chunki
    bu yerga faqat "yaxshi bo'lsa bo'ldi" xabarlari tushadi.
    """
    global _dropped
    if _queue is None:
        # Navbat ishga tushmagan (masalan testlarda) — vazifani yopamiz,
        # aks holda "coroutine was never awaited" ogohlantirishi chiqadi
        coro.close()
        return False
    try:
        _queue.put_nowait(coro)
        return True
    except asyncio.QueueFull:
        coro.close()
        _dropped += 1
        if _dropped % 50 == 1:
            logger.warning("Fon navbati to'la — vazifa tashlab yuborildi (jami %s)", _dropped)
        return False


def pending() -> int:
    return _queue.qsize() if _queue is not None else 0
