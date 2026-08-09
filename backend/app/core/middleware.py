"""Xavfsizlik middleware'lari: HTTP header'lar, tana hajmi, umumiy rate limit."""
import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp
from fastapi import HTTPException, Request

from app.config import settings
from app.core.ratelimit import rate_limit

logger = logging.getLogger(__name__)

# API JSON qaytaradi — skript/stil yuklamaydi, shuning uchun eng qattiq CSP
_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
    "X-Robots-Tag": "noindex, nofollow",     # API hech qachon indekslanmasin
    "Content-Security-Policy": _API_CSP,
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Har bir javobga xavfsizlik header'larini qo'shadi."""

    # Swagger UI o'z skript/stillarini yuklaydi — qattiq CSP uni buzadi.
    # (Bu yo'llar production'da umuman mavjud emas.)
    _DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        response: Response = await call_next(request)

        is_docs = request.url.path.startswith(self._DOCS_PATHS)
        for name, value in _SECURITY_HEADERS.items():
            if is_docs and name in ("Content-Security-Policy", "X-Frame-Options"):
                continue
            response.headers.setdefault(name, value)

        if settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains; preload",
            )
        response.headers["X-Request-ID"] = request_id
        # Server versiyasini oshkor qilmaymiz
        response.headers["Server"] = "qarzdaftar"
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Katta hajmli so'rovlar bilan xotirani to'ldirishning oldini oladi."""

    def __init__(self, app: ASGIApp, max_body: int):
        super().__init__(app)
        self.max_body = max_body

    async def dispatch(self, request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > self.max_body:
            return JSONResponse(
                {"detail": "So'rov hajmi juda katta"},
                status_code=413,
            )
        return await call_next(request)


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """IP bo'yicha umumiy so'rovlar limiti (DoS/skanerlashga qarshi)."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/healthz", "/"):
            return await call_next(request)
        try:
            await rate_limit(
                request,
                scope="global",
                limit=settings.API_RATE_LIMIT,
                window=settings.API_RATE_WINDOW,
            )
        except HTTPException as exc:
            return JSONResponse(
                {"detail": exc.detail},
                status_code=exc.status_code,
                headers=exc.headers or {},
            )
        return await call_next(request)
