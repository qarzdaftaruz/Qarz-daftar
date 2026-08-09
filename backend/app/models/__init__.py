from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
from enum import Enum


def utcnow() -> datetime:
    """Naive UTC vaqt.

    MongoDB sanalarni doim UTC'da saqlaydi va naive qilib qaytaradi.
    Butun tizim bo'ylab bitta ko'rinishda bo'lishi uchun shu funksiyadan
    foydalanamiz (datetime.utcnow() Python 3.12+ da deprecated).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ShopStatus(str, Enum):
    PENDING  = "pending"
    ACTIVE   = "active"
    BLOCKED  = "blocked"
    ARCHIVED = "archived"
    REJECTED = "rejected"
    # "Chiqindi qutisi": ma'lumot hali o'chmagan, 30 kun ichida qaytarish mumkin
    DELETED  = "deleted"


class DebtStatus(str, Enum):
    OPEN     = "open"
    PARTIAL  = "partial"
    CLOSED   = "closed"
    OVERDUE  = "overdue"
    ARCHIVED = "archived"


class User(Document):
    telegram_id: int
    full_name: str
    phone: str = ""
    extra_phones: List[str] = Field(default_factory=list)
    is_blocked: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "users"


class Shop(Document):
    name: str
    owner_id: PydanticObjectId
    status: ShopStatus = ShopStatus.PENDING
    trial_start: datetime = Field(default_factory=utcnow)
    trial_end: datetime
    subscription_end: Optional[datetime] = None
    promo_code_id: Optional[PydanticObjectId] = None
    block_reason: Optional[str] = None
    reject_reason: Optional[str] = None
    warning_sent: bool = False
    # Qarz raqamlarini (QRZ-0001) ketma-ket berish uchun hisoblagich.
    # Eski qarzlar o'chirilsa ham raqam takrorlanmaydi.
    debt_seq: int = 0

    # ── Yumshoq o'chirish ────────────────────────────────────────────────
    # O'chirilgan do'kon ma'lumoti darhol yo'qolmaydi: SHOP_PURGE_DAYS kun
    # "chiqindi qutisi"da turadi va shu muddat ichida qaytarilishi mumkin.
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None            # admin username
    status_before_delete: Optional[str] = None  # qaytarganda tiklash uchun

    # Oylik Excel hisobot oxirgi marta qachon yuborilgani (takror yubormaslik uchun)
    last_report_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "shops"


class Client(Document):
    shop_id: PydanticObjectId
    full_name: str
    phone: str
    debt_limit: Optional[int] = None
    status: str = "active"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "clients"


class Debt(Document):
    debt_number: str
    shop_id: PydanticObjectId
    client_id: PydanticObjectId
    amount: int
    paid_amount: int = 0
    remaining: int
    due_date: Optional[datetime] = None
    note: Optional[str] = None
    status: DebtStatus = DebtStatus.OPEN
    # Qarzdorga "ertaga muddat tugaydi" eslatmasi yuborilganmi
    due_reminder_sent: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "debts"


class Payment(Document):
    debt_id: PydanticObjectId
    shop_id: PydanticObjectId
    client_id: PydanticObjectId
    amount: int
    remaining_after: int
    created_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "payments"


class PromoCodeUse(BaseModel):
    shop_id: PydanticObjectId
    used_at: datetime = Field(default_factory=utcnow)


class PromoCode(Document):
    code: str
    expires_at: datetime
    is_active: bool = True
    uses: List[PromoCodeUse] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "promo_codes"


class AppSettings(Document):
    reminder_hour: int = 9
    reminder_minute: int = 0
    archive_duration_months: int = 6
    admin_telegram_id: Optional[int] = None
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "app_settings"


class SupportMessage(Document):
    shop_id: Optional[PydanticObjectId] = None
    user_telegram_id: int
    user_full_name: str
    shop_name: str
    user_phone: str
    message: str
    is_read: bool = False
    admin_message_id: Optional[int] = None   # Admin reply uchun
    created_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "support_messages"


class AdminAuth(Document):
    username: str
    hashed_password: str
    telegram_id: Optional[int] = None
    is_super: bool = False   # Super admin boshqa adminlarni boshqara oladi
    # Parol o'zgarganda eski JWT tokenlar bekor bo'lishi uchun
    token_version: int = 0
    must_change_password: bool = False
    # Brute-force himoyasi
    failed_attempts: int = 0
    locked_until: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "admin_auth"


class AuditLog(Document):
    """Kim, qachon, nima qilgani — nizoli holatlar uchun izoh qoldiradi.

    Yozuvlar `AUDIT_RETENTION_DAYS` dan keyin TTL indeks orqali
    avtomatik o'chadi (Atlas M0 hajmini tejash uchun).
    """
    actor_type: str                       # admin | owner | bot | system
    actor_name: str = ""                  # username yoki to'liq ism
    actor_id: Optional[str] = None        # AdminAuth.id yoki telegram_id
    action: str                           # shop.delete, debt.create, ...
    entity_type: Optional[str] = None     # shop | client | debt | payment | user | admin
    entity_id: Optional[str] = None
    entity_label: Optional[str] = None    # o'chirilgandan keyin ham tushunarli bo'lishi uchun
    shop_id: Optional[PydanticObjectId] = None
    summary: str = ""                     # odam o'qiydigan matn
    meta: dict = Field(default_factory=dict)
    ip: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "audit_logs"


ALL_MODELS = [
    User, Shop, Client, Debt, Payment,
    PromoCode, AppSettings, SupportMessage, AdminAuth, AuditLog
]
