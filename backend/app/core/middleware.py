"""Xavfsizlik middleware'lari: HTTP header'lar, tana hajmi, umumiy rate limit.

TEZLIK: bu middleware'lar ilgari `BaseHTTPMiddleware` ustiga qurilgan edi.
Starlette uni har bir so'rov uchun alohida anyio task-group va ikkita
xotira oqimi bilan o'raydi — uchta middleware = so'rovga uchta ortiqcha
o'ram. Endi ular sof ASGI middleware: hech qanday qo'shimcha vazifa
yaratilmaydi, faqat `send` chaqiruvi o'raladi. Sekin so'rovlarda farq
sezilmaydi, lekin tez JSON so'rovlarida (ro'yxatlar, dashboard) kechikish
sezilarli kamayadi.
"""
import json
import logging
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from fastapi import HTTPException

from app.config import settings
from app.core.ratelimit import client_ip_from_scope, limiter

logger = logging.getLogger(__name__)

# API JSON qaytaradi — skript/stil yuklamaydi, shuning uchun eng qattiq CSP
_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

_SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-site"),
    (b"permissions-policy", b"geolocation=(), microphone=(), camera=(), payment=(), usb=()"),
    (b"x-robots-tag", b"noindex, nofollow"),     # API hech qachon indekslanmasin
    (b"content-security-policy", _API_CSP.encode()),
]

# Swagger UI o'z skript/stillarini yuklaydi — qattiq CSP uni buzadi.
# (Bu yo'llar production'da umuman mavjud emas.)
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
_DOCS_SKIP = {b"content-security-policy", b"x-frame-options"}

_HSTS = b"max-age=63072000; includeSubDomains; preload"


def _json_response(status_code: int, detail: str, extra: dict | None = None) -> tuple[dict, bytes]:
    """Middleware ichidan to'g'ridan-to'g'ri javob qaytarish uchun."""
    body = json.dumps({"detail": detail}).encode()
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
    ]
    for key, value in (extra or {}).items():
        headers.append((key.lower().encode(), str(value).encode()))
    return {"type": "http.response.start", "status": status_code, "headers": headers}, body


async def _send_json(send: Send, status_code: int, detail: str, extra: dict | None = None) -> None:
    start, body = _json_response(status_code, detail, extra)
    await send(start)
    await send({"type": "http.response.body", "body": body})


class SecurityHeadersMiddleware:
    """Har bir javobga xavfsizlik header'larini qo'shadi."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request_id = ""
        for key, value in scope.get("headers", []):
            if key == b"x-request-id":
                request_id = value.decode("latin-1")[:64]
                break
        if not request_id:
            request_id = uuid.uuid4().hex[:12]

        is_docs = scope.get("path", "").startswith(_DOCS_PATHS)

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _SECURITY_HEADERS:
                    if is_docs and name in _DOCS_SKIP:
                        continue
                    if name.decode() not in headers:
                        headers.append(name.decode(), value.decode())
                if settings.is_production and "strict-transport-security" not in headers:
                    headers.append("strict-transport-security", _HSTS.decode())
                headers["x-request-id"] = request_id
                # Server versiyasini oshkor qilmaymiz
                headers["server"] = "qarzdaftar"
            await send(message)

        await self.app(scope, receive, send_wrapper)


class BodySizeLimitMiddleware:
    """Katta hajmli so'rovlar bilan xotirani to'ldirishning oldini oladi."""

    def __init__(self, app: ASGIApp, max_body: int):
        self.app = app
        self.max_body = max_body

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        declared = None
        chunked = False
        for key, value in scope.get("headers", []):
            if key == b"content-length" and value.isdigit():
                declared = int(value)
            elif key == b"transfer-encoding" and b"chunked" in value.lower():
                chunked = True

        if declared is not None and declared > self.max_body:
            return await _send_json(send, 413, "So'rov hajmi juda katta")

        if not chunked and declared is not None:
            return await self.app(scope, receive, send)

        # TESHIK YOPILDI: `Content-Length` sarlavhasi bo'lmagan (chunked)
        # so'rovda tekshirish umuman ishlamasdi — cheksiz oqim yuborib
        # konteyner xotirasini to'ldirish mumkin edi. Endi oqim ham
        # sanab boriladi va limitdan oshganda uziladi.
        received = 0
        too_big = False

        async def guarded_receive() -> Message:
            nonlocal received, too_big
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body:
                    too_big = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            if too_big and message["type"] == "http.response.start":
                message = dict(message, status=413)
            await send(message)

        await self.app(scope, guarded_receive, guarded_send)


class GlobalRateLimitMiddleware:
    """IP bo'yicha umumiy so'rovlar limiti (DoS/skanerlashga qarshi)."""

    _SKIP = {"/health", "/healthz", "/"}

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in self._SKIP:
            return await self.app(scope, receive, send)

        # OPTIONS (CORS preflight) tanani ham, bazani ham ishlatmaydi —
        # limitni brauzerning texnik so'rovlari bilan to'ldirmaymiz
        if scope.get("method") == "OPTIONS":
            return await self.app(scope, receive, send)

        if settings.RATE_LIMIT_ENABLED:
            try:
                await limiter.check(
                    f"global:{client_ip_from_scope(scope)}",
                    settings.API_RATE_LIMIT,
                    settings.API_RATE_WINDOW,
                )
            except HTTPException as exc:
                return await _send_json(send, exc.status_code, exc.detail, exc.headers)

        await self.app(scope, receive, send)
