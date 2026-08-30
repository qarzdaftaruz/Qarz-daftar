import os
import hmac
import hashlib
import secrets
import logging
from typing import Optional, List
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# Railway platformasi shu o'zgaruvchilarni avtomatik beradi
_RAILWAY_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN") or os.getenv("RAILWAY_STATIC_URL")


class Settings(BaseSettings):
    # ─── Muhit ────────────────────────────────────────────────────────────────
    # "production" | "development"
    ENVIRONMENT: str = "development"

    # ─── MongoDB (Atlas) ──────────────────────────────────────────────────────
    MONGODB_URL: str = "mongodb://localhost:27017"
    DB_NAME: str = "qarzdaftar"
    # Atlas uchun ulanish parametrlari
    MONGO_MAX_POOL_SIZE: int = 20
    MONGO_MIN_POOL_SIZE: int = 0
    MONGO_TIMEOUT_MS: int = 10000

    # ─── JWT ──────────────────────────────────────────────────────────────────
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720      # admin panel: 12 soat
    TMA_TOKEN_EXPIRE_MINUTES: int = 720         # mini app: 12 soat

    # ─── Telegram ─────────────────────────────────────────────────────────────
    BOT_TOKEN: str = ""
    # Bo'sh bo'lsa Railway domenidan avtomatik olinadi
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_PATH: str = "/webhook"
    # Telegram webhook'ini soxta so'rovlardan himoya qiluvchi maxfiy token.
    # Bo'sh bo'lsa startda avtomatik generatsiya qilinadi.
    TELEGRAM_WEBHOOK_SECRET: str = ""
    # initData necha soniya amal qiladi (Telegram tavsiyasi: 1 soatgacha)
    TMA_INITDATA_MAX_AGE: int = 3600

    # ─── Mini App / Frontend ──────────────────────────────────────────────────
    MINI_APP_URL: str = "https://your-mini-app.vercel.app"
    # CORS uchun ruxsat etilgan originlar (vergul bilan).
    # Bo'sh bo'lsa MINI_APP_URL ishlatiladi.
    CORS_ORIGINS: str = ""
    # Host header himoyasi (vergul bilan). Bo'sh bo'lsa tekshirilmaydi.
    ALLOWED_HOSTS: str = ""

    # ─── Admin ────────────────────────────────────────────────────────────────
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = ""
    ADMIN_TELEGRAM_ID: Optional[int] = None

    SUPER_ADMIN_IDS: str = ""
    SUPER_ADMIN_USERNAME: str = "Superadmin"
    SUPER_ADMIN_PASSWORD: str = ""

    # Parol siyosati
    MIN_PASSWORD_LENGTH: int = 8

    # ─── Server ───────────────────────────────────────────────────────────────
    APP_HOST: str = "0.0.0.0"
    # Railway PORT ni o'zi beradi — pastdagi validator uni o'qiydi
    APP_PORT: int = 8000
    # So'rov tanasi uchun maksimal hajm (bayt)
    MAX_BODY_SIZE: int = 1_000_000   # 1 MB

    # ─── Rate limit ───────────────────────────────────────────────────────────
    RATE_LIMIT_ENABLED: bool = True
    LOGIN_MAX_ATTEMPTS: int = 5          # 5 marta / 15 daqiqa
    LOGIN_WINDOW_SECONDS: int = 900
    LOGIN_LOCKOUT_SECONDS: int = 900
    API_RATE_LIMIT: int = 120            # umumiy: 120 so'rov / daqiqa / IP
    API_RATE_WINDOW: int = 60
    # Ilova oldida nechta ISHONCHLI proksi turadi (Railway edge = 1).
    # X-Forwarded-For oxiridan shuncha qadam sanaladi — mijoz o'zi yozgan
    # soxta qiymat cheklovlarni chetlab o'tolmasin. Cloudflare + Railway
    # bo'lsa 2 qilinadi.
    TRUSTED_PROXY_HOPS: int = 1

    # ─── Scheduler ────────────────────────────────────────────────────────────
    TIMEZONE: str = "Asia/Tashkent"
    REMINDER_HOUR: int = 9
    REMINDER_MINUTE: int = 0

    # ─── Biznes qoidalari ─────────────────────────────────────────────────────
    TRIAL_DAYS: int = 7
    PROMO_EXTRA_DAYS: int = 30
    ARCHIVE_DURATION_MONTHS: int = 6
    # O'chirilgan do'kon necha kun "chiqindi qutisi"da turadi
    SHOP_PURGE_DAYS: int = 30
    # Audit yozuvlari necha kun saqlanadi
    AUDIT_RETENTION_DAYS: int = 180

    # ─── Hisobotlar ───────────────────────────────────────────────────────────
    # Har oyning 1-sanasida do'kondorlarga Excel hisobot yuborish
    MONTHLY_REPORT_ENABLED: bool = True
    MONTHLY_REPORT_HOUR: int = 10
    # Qarzdorga "ertaga/bugun muddat tugaydi" eslatmasi
    DUE_REMINDER_ENABLED: bool = True
    DUE_REMINDER_HOUR: int = 10
    # Muddati o'tgan qarzlar uchun HAR KUNGI eslatma
    OVERDUE_REMINDER_ENABLED: bool = True
    OVERDUE_REMINDER_HOUR: int = 9
    OVERDUE_REMINDER_MINUTE: int = 30
    # Necha kundan keyin kunlik eslatma to'xtaydi (0 = cheksiz).
    # Umidsiz qarz bo'yicha yillab xabar yuborish botni bloklashga olib keladi.
    OVERDUE_REMINDER_MAX_DAYS: int = 60
    # Do'kondor bitta mijozga qo'lda eslatmani necha soatda bir yubora oladi
    MANUAL_REMINDER_COOLDOWN_HOURS: int = 6

    # ─── Obuna nazorati ───────────────────────────────────────────────────────
    # Muddati tugagan do'kon avtomatik to'xtatiladi.
    # DIQQAT: o'chirilsa, trial tugagach ham tizimdan bepul foydalanish mumkin.
    SUBSCRIPTION_ENFORCE: bool = True
    # Muddat tugagach necha kun "imtiyoz" beriladi (0 = darhol to'xtaydi)
    SUBSCRIPTION_GRACE_DAYS: int = 0
    # Do'kondor kuniga necha marta Excel hisobot ola oladi
    EXPORT_DAILY_LIMIT: int = 5
    # Bitta hisobotdagi maksimal qarzlar soni (xotira himoyasi)
    EXPORT_MAX_ROWS: int = 20000
    # Ommaviy yuborishda xabarlar orasidagi tanaffus (Telegram limitlari + server yuki)
    BULK_SEND_DELAY: float = 0.5

    # ─── Dev ──────────────────────────────────────────────────────────────────
    # DIQQAT: True bo'lsa initData imzosi tekshirilmaydi — faqat lokalda!
    TMA_DEV_MODE: bool = False

    model_config = {"env_file": ".env", "extra": "ignore", "case_sensitive": True}

    # ─── Validatorlar ─────────────────────────────────────────────────────────

    @field_validator("ENVIRONMENT")
    @classmethod
    def _env_norm(cls, v: str) -> str:
        v = (v or "development").strip().lower()
        if v in ("prod", "production", "live"):
            return "production"
        return "development"

    @model_validator(mode="after")
    def _apply_platform_and_guards(self):
        # 1) Railway PORT
        port = os.getenv("PORT")
        if port and port.isdigit():
            self.APP_PORT = int(port)

        # 2) Railway domeni → webhook + allowed hosts
        if not self.WEBHOOK_URL and _RAILWAY_DOMAIN:
            domain = _RAILWAY_DOMAIN.replace("https://", "").replace("http://", "").strip("/")
            self.WEBHOOK_URL = f"https://{domain}"

        # 3) Webhook path har doim "/" bilan boshlanadi
        if not self.WEBHOOK_PATH.startswith("/"):
            self.WEBHOOK_PATH = "/" + self.WEBHOOK_PATH

        # 4) SECRET_KEY
        if not self.SECRET_KEY:
            if self.is_production:
                raise RuntimeError(
                    "SECRET_KEY o'rnatilmagan! Railway Variables ichida SECRET_KEY qo'shing "
                    "(masalan: python -c \"import secrets;print(secrets.token_urlsafe(64))\")"
                )
            self.SECRET_KEY = secrets.token_urlsafe(64)
            logger.warning("SECRET_KEY yo'q — vaqtinchalik kalit generatsiya qilindi (faqat dev).")
        elif self.is_production and (len(self.SECRET_KEY) < 32 or self.SECRET_KEY in _WEAK_SECRETS):
            raise RuntimeError("SECRET_KEY juda qisqa yoki namunaviy. Kamida 32 belgili tasodifiy kalit kerak.")

        # 4b) Webhook secret — SECRET_KEY dan hosil qilinadi.
        #
        # XATO TUZATILDI: ilgari bu yerda `secrets.token_urlsafe(32)` bilan
        # HAR BIR ISHGA TUSHISHDA yangi tasodifiy qiymat yasalardi. Odatda
        # bu sezilmaydi, chunki startda `set_webhook` o'sha yangi qiymat
        # bilan chaqiriladi. Lekin `set_webhook` bir marta muvaffaqiyatsiz
        # bo'lsa (Telegram javob bermadi, tarmoq uzildi), Telegram'da ESKI
        # secret qolib ketadi va shu daqiqadan boshlab har bir update
        # 403 oladi — bot butunlay jim bo'lib qoladi va loglarda faqat
        # "noto'g'ri secret token" ko'rinadi. Endi qiymat SECRET_KEY dan
        # hosil qilinadi: qayta ishga tushirishdan keyin ham o'zgarmaydi.
        if not self.TELEGRAM_WEBHOOK_SECRET:
            self.TELEGRAM_WEBHOOK_SECRET = hmac.new(
                self.SECRET_KEY.encode(), b"telegram-webhook-secret", hashlib.sha256
            ).hexdigest()

        # 5) Production'da dev-mode QAT'IY o'chiq
        if self.is_production and self.TMA_DEV_MODE:
            logger.error("TMA_DEV_MODE production'da yoqilgan edi — majburan o'chirildi.")
            self.TMA_DEV_MODE = False

        # 6) Production'da bo'sh/oddiy parollar taqiqlanadi
        if self.is_production:
            for name, value in (
                ("ADMIN_PASSWORD", self.ADMIN_PASSWORD),
                ("SUPER_ADMIN_PASSWORD", self.SUPER_ADMIN_PASSWORD),
            ):
                if value and (len(value) < self.MIN_PASSWORD_LENGTH or value.lower() in _WEAK_PASSWORDS):
                    raise RuntimeError(
                        f"{name} juda kuchsiz. Kamida {self.MIN_PASSWORD_LENGTH} belgi, "
                        "namunaviy parollar taqiqlangan."
                    )
            if not self.BOT_TOKEN:
                raise RuntimeError("BOT_TOKEN o'rnatilmagan.")
            if "localhost" in self.MONGODB_URL or "127.0.0.1" in self.MONGODB_URL:
                raise RuntimeError("Production'da MONGODB_URL Atlas manziliga o'rnatilishi kerak.")

        return self

    # ─── Yordamchi xossalar ───────────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def super_admin_ids(self) -> List[int]:
        """SUPER_ADMIN_IDS stringini int ro'yxatiga aylantiradi."""
        ids: List[int] = []
        for part in self.SUPER_ADMIN_IDS.replace(" ", "").split(","):
            if part.lstrip("-").isdigit():
                ids.append(int(part))
        return ids

    @property
    def cors_origins(self) -> List[str]:
        """CORS uchun aniq originlar ro'yxati (hech qachon '*' emas)."""
        raw = self.CORS_ORIGINS or self.MINI_APP_URL
        origins = {o.strip().rstrip("/") for o in raw.split(",") if o.strip()}
        if not self.is_production:
            origins.update({
                "http://localhost:5174", "http://127.0.0.1:5174",
                "http://localhost:5173", "http://127.0.0.1:5173",
            })
        return sorted(o for o in origins if o.startswith("http"))

    @property
    def allowed_hosts(self) -> List[str]:
        """Host header filtri.

        Faqat ALLOWED_HOSTS aniq berilganda yoqiladi. Aks holda bo'sh
        qaytadi va middleware ulanmaydi — Railway ichki healthcheck
        so'rovlari boshqa host bilan kelib, deploy yiqilib qolmasligi uchun.
        """
        explicit = {h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()}
        if not explicit:
            return []
        hosts = set(explicit)
        for source in (_RAILWAY_DOMAIN, self.WEBHOOK_URL):
            if source:
                hosts.add(source.replace("https://", "").replace("http://", "").strip("/"))
        # Railway ichki tarmog'i va healthcheck
        hosts.update({"*.railway.app", "*.up.railway.app", "healthcheck.railway.app", "localhost", "127.0.0.1"})
        return sorted(hosts)

    @property
    def webhook_full_url(self) -> Optional[str]:
        if not self.WEBHOOK_URL:
            return None
        return f"{self.WEBHOOK_URL.rstrip('/')}{self.WEBHOOK_PATH}"

    # ─── Maxfiylik ────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        """Maxfiy qiymatlar hech qachon logga/xatoga tushmasin.

        Pydantic'ning standart repr'i barcha maydonlarni ochiq chiqaradi —
        bitta traceback BOT_TOKEN va SECRET_KEY ni oshkor qilishi mumkin edi.
        """
        shown = {
            k: ("***" if k in _SECRET_FIELDS else getattr(self, k))
            for k in self.__class__.model_fields
        }
        return f"Settings({shown})"

    __str__ = __repr__

    def security_report(self) -> list[tuple[str, str]]:
        """Startda chiqariladigan xavfsizlik holati: (daraja, xabar)."""
        issues: list[tuple[str, str]] = []

        if self.TMA_DEV_MODE:
            issues.append(("XATAR", "TMA_DEV_MODE yoqilgan — initData imzosi tekshirilmaydi"))
        if not self.is_production:
            issues.append(("INFO", "ENVIRONMENT=development — himoya qoidalari yumshoq"))
        if self.SECRET_KEY and len(self.SECRET_KEY) < 32:
            issues.append(("OGOH", "SECRET_KEY 32 belgidan qisqa"))
        if not self.RATE_LIMIT_ENABLED:
            issues.append(("OGOH", "Rate limit o'chirilgan — brute-force himoyasi yo'q"))
        if "*" in self.CORS_ORIGINS:
            issues.append(("XATAR", "CORS_ORIGINS ichida '*' bor"))
        if self.is_production and not self.WEBHOOK_URL:
            issues.append(("OGOH", "WEBHOOK_URL yo'q — bot polling rejimida (bir replika bo'lishi shart)"))
        # Botdagi «Ilovani ochish» tugmasi shu manzilga ketadi. Namunaviy
        # qiymat qolib ketsa bot tashqaridan "ishlamayotgan" bo'lib ko'rinadi:
        # tugma bosiladi, lekin ochilmaydi.
        if "your-mini-app" in self.MINI_APP_URL or not self.MINI_APP_URL.startswith("https://"):
            issues.append((
                "XATAR",
                f"MINI_APP_URL noto'g'ri ({self.MINI_APP_URL}) — botdagi "
                "«Ilovani ochish» tugmasi ochilmaydi",
            ))
        if self.is_production and not self.ALLOWED_HOSTS:
            issues.append(("INFO", "ALLOWED_HOSTS bo'sh — Host header filtri o'chiq"))
        if self.MIN_PASSWORD_LENGTH < 8:
            issues.append(("OGOH", f"MIN_PASSWORD_LENGTH juda kichik: {self.MIN_PASSWORD_LENGTH}"))
        if self.TRUSTED_PROXY_HOPS < 1:
            issues.append((
                "XATAR",
                "TRUSTED_PROXY_HOPS < 1 — mijoz yozgan X-Forwarded-For qabul qilinadi "
                "va IP bo'yicha cheklovlarni chetlab o'tish mumkin",
            ))
        elif self.is_production and self.TRUSTED_PROXY_HOPS > 3:
            issues.append((
                "OGOH",
                f"TRUSTED_PROXY_HOPS={self.TRUSTED_PROXY_HOPS} — juda katta; "
                "haqiqiy mijoz IP si o'rniga proksi IP si ishlatilishi mumkin",
            ))
        return issues


# Logga/repr'ga chiqmasligi kerak bo'lgan maydonlar
_SECRET_FIELDS = {
    "SECRET_KEY", "BOT_TOKEN", "MONGODB_URL", "TELEGRAM_WEBHOOK_SECRET",
    "ADMIN_PASSWORD", "SUPER_ADMIN_PASSWORD",
}

_WEAK_SECRETS = {
    "change-this",
    "change-this-to-a-very-long-random-string",
    "secret",
    "changeme",
}

_WEAK_PASSWORDS = {
    "admin", "admin123", "password", "parol", "12345678", "123456789",
    "superadmin", "superadmin123", "qwerty123",
}


settings = Settings()
