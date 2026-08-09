import hmac
import hashlib
import json
import logging
from urllib.parse import parse_qsl
from datetime import datetime, timezone, timedelta
from typing import Optional

from jose import JWTError, jwt
from fastapi import HTTPException, Header, status

from app.config import settings

logger = logging.getLogger(__name__)


class InitDataError(ValueError):
    """initData tekshiruvidan o'tmadi."""


def verify_init_data(init_data: str) -> dict:
    """
    Telegram WebApp initData ni tekshirish.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

    DIQQAT: parse_qsl allaqachon URL-decode qiladi.
    Oldindan unquote() qilish qiymatlarni ikki marta dekodlab, imzoni
    buzadi (ismida %, + yoki emoji bo'lgan foydalanuvchilarda) —
    shuning uchun unquote ishlatilmaydi.
    """
    if not init_data or len(init_data) > 8192:
        raise InitDataError("initData bo'sh yoki juda uzun")

    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        raise InitDataError("initData formati noto'g'ri")

    parsed = dict(pairs)
    received_hash = parsed.pop("hash", "")
    if not received_hash:
        raise InitDataError("imzo (hash) yo'q")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=settings.BOT_TOKEN.encode(),
        digestmod=hashlib.sha256,
    ).digest()

    expected_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise InitDataError("initData imzosi noto'g'ri")

    # Replay hujumini cheklash — eski initData qabul qilinmaydi
    try:
        auth_date = int(parsed.get("auth_date", 0))
    except ValueError:
        raise InitDataError("auth_date noto'g'ri")

    now = int(datetime.now(timezone.utc).timestamp())
    if auth_date <= 0 or now - auth_date > settings.TMA_INITDATA_MAX_AGE:
        raise InitDataError("Sessiya muddati tugagan — ilovani qayta oching")

    try:
        user = json.loads(parsed.get("user", "{}"))
    except json.JSONDecodeError:
        raise InitDataError("user maydoni noto'g'ri")

    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        raise InitDataError("Foydalanuvchi aniqlanmadi")

    return user


def create_tma_token(telegram_id: int) -> str:
    """TMA foydalanuvchisi uchun JWT yaratish"""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": f"tg:{telegram_id}",
            "tid": telegram_id,
            # Token turi — mini app tokeni admin endpointlarida ishlatilmasin
            "typ": "tma",
            "iat": now,
            "exp": now + timedelta(minutes=settings.TMA_TOKEN_EXPIRE_MINUTES),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sessiya tugagan — ilovani qayta oching",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_tma_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    FastAPI dependency: TMA JWT ni tekshirish.
    Returns: {"telegram_id": int}
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise _UNAUTHORIZED

    token = authorization[7:].strip()
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require_exp": True},
        )
    except JWTError:
        raise _UNAUTHORIZED

    sub = str(payload.get("sub", ""))
    tid = payload.get("tid")
    # Eski tokenlarda "typ" bo'lmasligi mumkin — sub prefiksi zaxira tekshiruv
    if payload.get("typ", "tma") != "tma" or not sub.startswith("tg:") or not isinstance(tid, int):
        raise _UNAUTHORIZED

    return {"telegram_id": tid}
