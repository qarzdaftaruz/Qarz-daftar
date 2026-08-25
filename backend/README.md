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

## Proksi va IP cheklovlari

`X-Forwarded-For` sarlavhasining **birinchi** qiymatini mijozning o'zi
yozadi — proksi uni faqat oxiriga qo'shadi. Shuning uchun haqiqiy IP
oxiridan `TRUSTED_PROXY_HOPS` qadam sanab olinadi:

| Joylashuv | Qiymat |
|---|---|
| Railway (to'g'ridan-to'g'ri) | `1` |
| Cloudflare → Railway | `2` |

Noto'g'ri qiymat = IP bo'yicha barcha cheklovlar (login brute-force
himoyasi ham) chetlab o'tiladi. Start paytida `security_report()` buni
tekshiradi.

Ikkinchi qatlam: `X-Forwarded-For` **faqat** to'g'ridan-to'g'ri ulangan
tomon xususiy/loopback manzilda bo'lganda o'qiladi. Edge proksi ilova
bilan doim ichki tarmoq orqali gaplashadi; manzil ommaviy bo'lsa —
so'rov proksidan o'tmagan va sarlavhaga ishonib bo'lmaydi.

## Rate limiter

`app/core/ratelimit.py` — har bir kalit **o'z oynasini** saqlaydi.
Bu muhim: umumiy limit oynasi 60 soniya, login oynasi 900, kunlik
eksport oynasi 86400. Umumiy tozalash ularni bir xil oyna bilan
qisqartirsa, uzun oynali cheklovlar amalda ishlamay qoladi.

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
| Do'kon egasi tekshiruvi (`owner_shop`) | Har so'rovda 2 ta so'rov | 5 soniyalik kesh |
| Ommaviy eslatmalar | Har bir qarzdor uchun 3 so'rov (N+1) | Jami 3 ta so'rov |
| Xavfsizlik middleware'lari | `BaseHTTPMiddleware` (so'rovga 3 ta task-group) | Sof ASGI — qo'shimcha task yo'q |
| `/health` | Har chaqiruvda Atlas'ga `ping` | 5 soniyalik kesh |
| Qarzdor sahifasi | Barcha qarz va to'lovlar (chegarasiz) | `MAX_DEBTS` / `MAX_PAYMENTS` |
| Telegram xabarlari | So'rov ichida kutilardi (150–400 ms) | Fon navbati — so'rov darhol javob beradi |
| Audit xabarnomasi | Har bir super adminga so'rov ichida | Fon navbati + takrorlanish cheklovi |
| Arxiv tozalash | Bitta ulkan `$in` (16 MB chegarasi) | 1000 tadan bo'lib |

Fon navbati: `app/core/tasks.py`. Navbat **cheklangan** (2000 ta) —
to'lib qolsa vazifa tashlanadi va logga yoziladi, chunki cheksiz navbat
Railway konteynerining xotirasini yeb qo'yadi.

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
| `overdue` | har soat | Muddati o'tgan qarzlarni `overdue` deb belgilaydi |
| `warnings` | 08:00 | Obuna tugashiga 3 kun qolganda ogohlantiradi |
| `expire` | 07:05 va 19:05 | **Obuna muddati tugagan do'konni to'xtatadi** |
| `daily` | sozlamadagi vaqt | Do'kondorga kunlik hisobot |
| `overdue_reminder` | 09:30 | **Qarzdorga «muddat o'tdi» — HAR KUNI** |
| `due_reminder` | 10:30 | **Qarzdorga** «bugun/ertaga muddat tugaydi» |
| `monthly_report` | 1-sana 10:00 | **Do'kondorga Excel hisobot** |
| `cleanup` | 00:30 | Eski yopiq qarzlarni tozalaydi |
| `purge` | 01:00 | 30 kundan oshgan o'chirilgan do'konlarni yo'q qiladi |

Ommaviy yuborishlar ketma-ket, `BULK_SEND_DELAY` tanaffusi bilan bajariladi —
Telegram limitlari va Railway'ning bitta vCPU si uchun.

## Qarzdorga eslatmalar

Matnlar bitta joyda: `app/utils/reminders.py`. Keyinchalik SMS
qo'shilganda o'zgartirish faqat shu faylda va `helpers.notify_debtor`
ichida bo'ladi.

| Eslatma | Qachon | Necha marta |
|---|---|---|
| Yangi qarz | qarz yozilgan zahoti | 1 marta |
| «Bugun/ertaga muddat tugaydi» | muddatdan 1 kun oldin, 10:30 | 1 marta (`due_reminder_sent`) |
| **«Muddat o'tdi»** | muddat o'tgan kundan boshlab **har kuni** 09:30 | to'lanmaguncha (`OVERDUE_REMINDER_MAX_DAYS` gacha) |
| Qo'lda eslatma | do'kondor tugmani bosganda | `MANUAL_REMINDER_COOLDOWN_HOURS` da 1 marta |
| To'lov / qarz yopilishi | amal bajarilganda | 1 marta |

Muhim tafsilotlar:

- **Muddatsiz qarzlar** avtomatik eslatmani ishga tushirmaydi, lekin
  qarzdor umumiy qoldig'ini ko'rishi uchun xabarga qo'shiladi.
- Bugun yozilgan va **bugun/ertaga** muddati tugaydigan qarz kunlik
  jadvalga ulgurmaydi — shuning uchun ogohlantirish darhol yangi qarz
  xabariga qo'shiladi (`reminders.due_urgency`).
- Bir kunda ikki marta yubormaslik kafolati: `Debt.overdue_notified_at`
  bugungi kun boshidan oldin bo'lgan qarzlargina olinadi. Server qayta
  ishga tushsa ham takror ketmaydi.
- Bitta qarzdorning bitta do'kondagi barcha qarzlari **bitta xabarda**
  jamlanadi.
- Bloklangan/muddati tugagan do'kon nomidan eslatma ketmaydi.

## Obuna muddati nazorati

`SUBSCRIPTION_ENFORCE=true` (standart) bo'lganda muddati tugagan do'kon:

1. `expire` vazifasi uni `blocked` holatiga o'tkazadi
   (`block_reason = "Obuna muddati tugadi"`), egasiga xabar ketadi,
   audit logga `shop.expired` yoziladi.
2. Vazifa ishlashini kutmasdan — `owner_shop` dependency har bir
   so'rovda ham tekshiradi, ya'ni muddat tugagan zahoti panel yopiladi.
3. Admin **«Uzaytirish»** bosganda hammasi tiklanadi. Muddati tugagan
   do'konni «Blokdan chiqarish» bilan ochib bo'lmaydi — bu ataylab,
   aks holda do'kon keyingi tekshiruvda qayta yopilardi.
4. Admin tasdiqlashni kechiktirgan bo'lsa, **tasdiqlash paytida sinov
   muddati noldan boshlanadi** — do'kondor admin sekinligi uchun
   jazolanmaydi.

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
│       ├── helpers.py   # format_money, format_date, xabar yuborish
│       ├── reminders.py # qarzdorga ketadigan barcha eslatma matnlari
│       ├── reports.py   # hisobot ma'lumotlarini yig'ish
│       └── excel.py     # xlsx generatori
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

To'liq jadval yuqorida — [Avtomatik vazifalar](#avtomatik-vazifalar-scheduler).

| Vaqt | Vazifa |
|---|---|
| Har kuni 09:00 | Do'kondorga kunlik hisobot |
| Har kuni 09:30 | **Qarzdorga «muddat o'tdi» eslatmasi (har kuni)** |
| Har kuni 10:30 | Qarzdorga «bugun/ertaga muddat tugaydi» |
| Har kuni 08:00 | Obuna tugashiga 3 kun qolganda ogohlantirish |
| 07:05 va 19:05 | Obuna muddati tugagan do'konlarni to'xtatish |
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
