import re
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/auth/login", auto_error=False)

# bcrypt 72 baytdan uzun parolni jim qirqadi — buni oldindan cheklaymiz
MAX_PASSWORD_BYTES = 72


# ─── Parol ────────────────────────────────────────────────────────────────────

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password[:MAX_PASSWORD_BYTES])


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain[:MAX_PASSWORD_BYTES], hashed)
    except Exception:      # noqa: BLE001 — buzilgan hash ham "noto'g'ri parol"
        return False


def validate_password_strength(password: str) -> None:
    """Zaif parolni qabul qilmaydi. Mos kelmasa HTTP 400."""
    min_len = settings.MIN_PASSWORD_LENGTH
    if len(password) < min_len:
        raise HTTPException(400, f"Parol kamida {min_len} ta belgidan iborat bo'lishi kerak")
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        raise HTTPException(400, "Parol juda uzun (maksimal 72 bayt)")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(400, "Parolda kamida bitta harf va bitta raqam bo'lishi kerak")
    if password.lower() in {
        "admin123", "password", "parol123", "qwerty123", "superadmin123",
        "12345678910", "adminadmin1",
    }:
        raise HTTPException(400, "Bu parol juda ommabop. Boshqasini tanlang")


# ─── JWT ──────────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    to_encode.update({
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": secrets.token_urlsafe(8),
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _decode(token: str) -> dict:
    """Tokenni ochish. Algoritm qat'iy belgilangan (alg=none hujumidan himoya)."""
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        options={"require_exp": True},
    )


_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sessiya tugagan yoki token noto'g'ri",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_admin(token: Optional[str] = Depends(oauth2_scheme)):
    """Tokenni tekshirib, AdminAuth hujjatini qaytaradi.

    Bazadagi holat ham tekshiriladi: hisob o'chirilgan yoki paroli
    o'zgargan bo'lsa, eski token darhol ishlamay qoladi.
    """
    from app.models import AdminAuth

    if not token:
        raise _UNAUTHORIZED
    try:
        payload = _decode(token)
    except JWTError:
        raise _UNAUTHORIZED

    sub = str(payload.get("sub", ""))
    # Mini App tokeni admin endpointlarida ishlamasin
    if payload.get("typ", "admin") != "admin" or not sub.startswith("admin:"):
        raise _UNAUTHORIZED

    username = sub.split("admin:", 1)[1]
    admin = await AdminAuth.find_one(AdminAuth.username == username)
    if not admin:
        raise _UNAUTHORIZED

    # Parol o'zgarganda token_version oshadi → eski tokenlar bekor bo'ladi
    if int(payload.get("tv", -1)) != admin.token_version:
        raise _UNAUTHORIZED

    return admin


async def get_current_admin_username(admin=Depends(get_current_admin)) -> str:
    return admin.username


async def get_current_super_admin(admin=Depends(get_current_admin)):
    """Faqat super admin uchun. Aks holda 403."""
    if not admin.is_super:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Faqat super admin uchun")
    return admin
