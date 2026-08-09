# 📒 Qarz Daftar — Backend

Multi-tenant elektron qarz daftar tizimi.  
**Stack:** FastAPI · aiogram 3 · MongoDB Atlas (Beanie) · APScheduler

> 🚀 **Deploy:** MongoDB Atlas + Railway + Vercel bo'yicha to'liq qo'llanma —
> [`../DEPLOY.md`](../DEPLOY.md)

## Qo'shilgan xavfsizlik qatlamlari

| Qatlam | Fayl |
|---|---|
| Rate limit: IP bo'yicha + foydalanuvchi (telegram_id) bo'yicha | `app/core/ratelimit.py` |
| Xavfsizlik header'lari, tana hajmi limiti, global limit | `app/core/middleware.py` |
| JWT + `token_version` + `typ` (token turlari aralashmaydi) | `app/core/security.py` |
| Telegram initData imzosi (HMAC-SHA256) | `app/core/tma.py` |
| Webhook `secret_token` tekshiruvi | `app/main.py` |
| CORS faqat aniq originlar | `app/config.py` → `CORS_ORIGINS` |
| Pul amallarida qulf (ikki marta yozilishdan himoya) | `app/core/locks.py` |
| Bot flood himoyasi | `app/bot/middlewares/throttle.py` |
| Audit log + super adminga Telegram xabarnomasi | `app/core/audit.py` |
| Maxfiy qiymatlar loglarda `***` bilan yashiriladi | `app/config.py` → `__repr__` |

Startda `security_report()` xavfsizlik holatini logga chiqaradi —
Railway loglarida `[xavfsizlik/...]` qatorlarini tekshiring.

Muhim: `ENVIRONMENT=production` bo'lganda konfiguratsiya kuchsiz `SECRET_KEY`,
namunaviy parollar va `TMA_DEV_MODE=true` bilan **ishga tushmaydi** — bu ataylab.

## Audit log

Muhim amallar (qarz o'chirish, do'kon o'chirish, admin qo'shish, kirish
urinishlari, to'lovlar) `audit_logs` kolleksiyasiga yoziladi va admin
panelning **Amallar tarixi** bo'limida ko'rinadi.

- Yozuvchi modul: `app/core/audit.py`
- Yozuvlar TTL indeks orqali **1 yildan keyin avtomatik o'chadi**
  (`AUDIT_RETENTION_DAYS`)
- Audit yozuvi muvaffaqiyatsiz bo'lsa asosiy amal to'xtamaydi

## Tezlik (optimizatsiya qarorlari)

Atlas M0 + Railway 1 vCPU uchun asosiy qoida: **tarmoq orqali kamroq
ma'lumot tashish va kamroq borish**.

| Joy | Ilgari | Hozir |
|---|---|---|
| Mijozlar ro'yxati | Barcha mijozlar xotiraga, Python'da saralash | Bitta `$lookup + $facet` — faqat 20 ta hujjat qaytadi |
| Oylik statistika | Har oy uchun alohida so'rov (6 ta) | Bitta `$bucket` |
| Do'konlar ro'yxati | Har bir do'kon uchun 3 so'rov (N+1) | 4 ta jamlangan so'rov |
| `is_debtor` tekshiruvi | Barcha mos yozuvlar yuklanardi | Bitta «bormi?» so'rovi |
| `AppSettings` | 8 joyda har safar bazadan | 30 soniyalik kesh |
| `/profile/me` (frontend) | Har sahifada qayta so'raladi | Sessiya davomida bir marta |
| Excel yasash | Asosiy oqimni bloklardi | `asyncio.to_thread` — parallel ishlaydi |
| Eski qarzlarni tozalash | Har bir qarz uchun 2 so'rov | 2 ta `delete_many` |

Indekslar `app/database.py` → `_ensure_indexes()` da. Eng muhimi
`idx_client_shop_status_name` — mijozlar ro'yxati, dashboard, statistika
va eksport shundan foydalanadi (`IXSCAN`, `COLLSCAN` emas).

## Do'konni o'chirish — «chiqindi qutisi»

O'chirilgan do'kon darhol yo'q qilinmaydi:

1. Admin «O'chirish» bosadi → `status=deleted`, ma'lumot **saqlanib qoladi**
2. Do'kon egasiga xabar boradi (qachongacha qaytarish mumkinligi bilan)
3. **30 kun** ichida admin panelning «🗑 Chiqindi qutisi» bo'limidan qaytarish mumkin
4. Muddat tugagach `purge_deleted_shops` cron ishi butunlay o'chiradi

Super admin 30 kunni kutmasdan «Butunlay yo'q qilish» tugmasi bilan
darhol o'chirishi mumkin (`DELETE /shops/{id}/purge`).

## Avtomatik vazifalar (scheduler)

| Ish | Vaqt (Toshkent) | Nima qiladi |
|---|---|---|
| `overdue` | har soat | Muddati o'tgan qarzlarni belgilaydi |
| `warnings` | 08:00 | Obuna tugashiga 3 kun qolganda ogohlantiradi |
| `daily` | sozlamadagi vaqt | Do'kondorga kunlik hisobot |
| `due_reminder` | 10:30 | **Qarzdorga** «ertaga muddat tugaydi» |
| `monthly_report` | 1-sana 10:00 | **Do'kondorga Excel hisobot** |
| `cleanup` | 00:30 | Eski yopiq qarzlarni tozalaydi |
| `purge` | 01:00 | 30 kundan oshgan o'chirilgan do'konlarni yo'q qiladi |

Ommaviy yuborishlar ketma-ket, `BULK_SEND_DELAY` tanaffusi bilan bajariladi —
Telegram limitlari va Railway'ning bitta vCPU si uchun.

## Excel hisobotlar

| Kim | Qayerdan | Natija |
|---|---|---|
| Do'kondor | Mini App → Statistika → «Excel hisobotni olish» | Fayl Telegram chatiga hujjat bo'lib keladi |
| Admin | Panel → Do'konlar → «Excel» | Brauzerda yuklab olinadi |
| Super admin | Panel → Super qidiruv → do'kon → «Excel» | Do'konning qarzdorlari + qarzlari |

Generator: `app/utils/excel.py`, yig'uvchi: `app/utils/reports.py` (openpyxl).

**Server yuki cheklovlari:** bir do'kon uchun bir vaqtda 1 ta hisobot
(qulf), kuniga `EXPORT_DAILY_LIMIT` marta, maksimal `EXPORT_MAX_ROWS`
qator. Fayl alohida oqimda (`asyncio.to_thread`) yasaladi — og'ir hisobot
boshqa foydalanuvchilarning so'rovlarini kutkazib qo'ymaydi.

## Skriptlar

```bash
# Telefon raqamlarni yagona formatga keltirish (avval sinov, keyin --apply)
python scripts/migrate_phones.py
python scripts/migrate_phones.py --apply
```

---

## 📁 Tuzilma

```
backend/
├── app/
│   ├── main.py          # FastAPI app + bot webhook + lifespan
│   ├── config.py        # Pydantic-settings (.env o'qish)
│   ├── database.py      # MongoDB + Beanie init
│   ├── models/          # Barcha MongoDB collectionlar
│   ├── api/             # Admin panel REST API
│   ├── bot/
│   │   ├── main.py      # Bot + Dispatcher
│   │   ├── handlers/    # common.py, shop_owner.py
│   │   ├── keyboards/   # Reply va Inline klaviaturalar
│   │   ├── states/      # FSM holatlari
│   │   └── middlewares/ # Auth middleware
│   ├── core/
│   │   ├── security.py  # JWT, bcrypt, OTP
│   │   └── scheduler.py # APScheduler — eslatmalar, arxivlash
│   └── utils/
│       └── helpers.py   # format_money, format_date va boshqalar
├── requirements.txt
├── .env.example
└── run.py
```

---

## ⚡ Ishga tushirish (lokal)

### 1. Virtual muhit

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. .env fayl

```bash
cp .env.example .env
```

`.env` ni to'ldiring:

```env
MONGODB_URL=mongodb://localhost:27017
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_PASSWORD=xavfsiz_parol
ADMIN_TELEGRAM_ID=sizning_telegram_id
SECRET_KEY=uzun_tasodifiy_kalit
```

> **WEBHOOK_URL** ni bo'sh qoldiring — lokal muhitda polling ishlaydi.

### 3. MongoDB

```bash
# Docker orqali:
docker run -d -p 27017:27017 --name mongo mongo:7

# Yoki MongoDB Atlas M0 (bepul) ishlatish mumkin
```

### 4. Ishga tushirish

```bash
python run.py
```

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

---

## 🚂 Railway Deploy

### 1. Environment variables (Railway dashboard → Variables):

```
MONGODB_URL       = mongodb+srv://...  (Atlas connection string)
BOT_TOKEN         = ...
WEBHOOK_URL       = https://your-app.up.railway.app
SECRET_KEY        = ...
ADMIN_PASSWORD    = ...
ADMIN_TELEGRAM_ID = ...
```

### 2. Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 3. Procfile (ixtiyoriy):

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

## 🤖 Bot funksiyalari

| Buyruq/Tugma | Funksiya |
|---|---|
| `/start` | Ro'yxatdan o'tish yoki menyu |
| 👥 Mijozlar | Ro'yxat, qidiruv, sahifalash |
| 💰 Yangi qarz | Mijoz + qarz qo'shish |
| 📊 Statistika | Do'kon statistikasi |
| 📋 Kunlik hisobot | Bugungi eslatmalar |
| ⚙️ Sozlamalar | Telefon qo'shish, /contact |
| `/contact` | Adminga xabar yuborish |

---

## 🔌 Admin Panel API

| Endpoint | Tavsif |
|---|---|
| `POST /api/auth/login` | Login (JWT token) |
| `PUT /api/auth/password` | Parol o'zgartirish |
| `GET /api/dashboard` | Stats + oylik grafik |
| `GET /api/shops` | Do'konlar ro'yxati (filter bilan) |
| `POST /api/shops/{id}/approve` | Tasdiqlash |
| `POST /api/shops/{id}/reject` | Rad etish (sabab bilan) |
| `POST /api/shops/{id}/block` | Bloklash (sabab bilan) |
| `POST /api/shops/{id}/unblock` | Blokdan chiqarish |
| `GET /api/shops/{id}/export` | Excel eksport |
| `GET /api/users` | Foydalanuvchilar |
| `GET /api/promo-codes` | Promo kodlar |
| `POST /api/promo-codes` | Yangi promo kod |
| `GET /api/support` | Xabarlar |
| `GET /api/settings` | Sozlamalar |
| `PUT /api/settings` | Sozlamalarni saqlash |

---

## ⏰ Scheduler (APScheduler)

| Vaqt | Vazifa |
|---|---|
| Har kuni 09:00 | Do'kon egalari + qarzdorlarga eslatma |
| Har kuni 08:00 | Obuna tugashiga 3 kun qolganda ogohlantirish |
| Har soat | Muddati o'tgan qarzlar statusini yangilash |
| Har kuni 00:30 | Eski arxivlangan qarzlarni tozalash |

---

## 🗄️ MongoDB Collectionlar

| Collection | Tavsif |
|---|---|
| `users` | Barcha foydalanuvchilar (telegram_id, phone) |
| `shops` | Do'konlar (status, trial, subscription) |
| `clients` | Har do'konning mijozlari |
| `debts` | Qarz yozuvlari (#QRZ-0001) |
| `payments` | To'lov tarixi |
| `promo_codes` | Promo kodlar va ularning ishlatilishi |
| `app_settings` | Global tizim sozlamalari (singleton) |
| `support_messages` | /contact xabarlari |
| `admin_auth` | Admin login ma'lumotlari |

---

## 🔑 Default admin

```
Login:  admin
Parol:  admin123   (birinchi kirishda o'zgartiring!)
```
