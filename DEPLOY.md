# 🚀 Deploy qo'llanmasi — MongoDB Atlas + Railway + Vercel

Arxitektura:

```
Telegram  ──►  Railway (FastAPI + aiogram bot + scheduler)  ──►  MongoDB Atlas
                          ▲
                          │  HTTPS (CORS bilan cheklangan)
                          │
Foydalanuvchi  ──►  Vercel (React SPA / Telegram Mini App)
```

---

## 1️⃣ MongoDB Atlas

1. [cloud.mongodb.com](https://cloud.mongodb.com) → **Create cluster** (M0 bepul kifoya).
2. **Database Access** → yangi foydalanuvchi (`Read and write to any database`).
   Parolda `@ : / ?` bo'lmasin, aks holda URL-encode qiling (`@` → `%40`).
3. **Network Access** → Railway'ning statik IP si yo'q, shuning uchun `0.0.0.0/0`.
   > Himoya kuchli parol + TLS orqali ta'minlanadi. Agar Railway'da statik IP
   > (Pro reja) bo'lsa, faqat o'shani qo'shing.
4. **Connect → Drivers → Python** → connection string ni nusxalang:
   ```
   mongodb+srv://user:parol@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```

Indekslar **avtomatik** yaratiladi (`app/database.py` → `_ensure_indexes`),
qo'lda hech narsa qilish shart emas.

---

## 2️⃣ Railway (backend + bot)

**Root Directory:** bo'sh qoldiring (`/` — repo ildizi).

Ildizdagi `Dockerfile` + `railway.json` `backend/` ni quradi. Railway'ning
avtomatik aniqlagichi (Railpack) ildizda ilova topa olmay
`Railpack could not determine how to build the app` xatosini bergani uchun
shunday qilingan. Agar Root Directory `backend` ga qo'yilgan bo'lsa — uni
**bo'shatib qo'ying**, aks holda ildizdagi `Dockerfile` topilmaydi.

### Variables (Settings → Variables)

| Kalit | Qiymat |
|---|---|
| `ENVIRONMENT` | `production` |
| `MONGODB_URL` | Atlas connection string |
| `DB_NAME` | `qarzdaftar` |
| `SECRET_KEY` | `python -c "import secrets;print(secrets.token_urlsafe(64))"` |
| `BOT_TOKEN` | @BotFather dan |
| `TELEGRAM_WEBHOOK_SECRET` | 32+ belgili tasodifiy satr |
| `MINI_APP_URL` | `https://<loyiha>.vercel.app` |
| `CORS_ORIGINS` | `https://<loyiha>.vercel.app` (bir nechta bo'lsa vergul bilan) |
| `ADMIN_TELEGRAM_ID` | Sizning Telegram ID |
| `SUPER_ADMIN_IDS` | Sizning Telegram ID |
| `ADMIN_PASSWORD` / `SUPER_ADMIN_PASSWORD` | **bo'sh qoldiring** (pastga qarang) |
| `TMA_DEV_MODE` | `false` |

`WEBHOOK_URL` **kerak emas** — `RAILWAY_PUBLIC_DOMAIN` dan avtomatik olinadi.
`PORT` ni ham qo'lda qo'ymang, Railway o'zi beradi.

### Birinchi ishga tushirish

Parollar bo'sh qoldirilsa, tizim tasodifiy parol generatsiya qiladi va
**Deploy Logs** da bir marta chiqaradi:

```
!!! 'Superadmin' uchun vaqtinchalik parol yaratildi: xxxxxxxx — birinchi kirishdan keyin ALBATTA o'zgartiring !!!
```

Shu parol bilan `/admin/login` ga kiring → panel darhol **Profil** sahifasiga
yo'naltiradi → yangi parol qo'ying.

> Parol o'zgargandan keyin barcha ochiq sessiyalar bekor bo'ladi (`token_version`).

### Tekshirish

```bash
curl https://<railway-domain>/health
# {"status":"ok","db":true,"version":"2.1.0"}
```

Webhook holati:
```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

---

## 3️⃣ Vercel (frontend)

**Root Directory:** `frontend` · Framework: **Vite** (avtomatik aniqlanadi)

### Environment Variables

| Kalit | Qiymat |
|---|---|
| `VITE_API_URL` | `https://<railway-domain>` (oxirida `/` bo'lmasin) |

> ⚠️ Bu **shart**. Bo'lmasa so'rovlar Vercel domeniga ketadi va 404 qaytadi.
> `VITE_` bilan boshlangan qiymatlar brauzerga tushadi — maxfiy kalit yozmang.

`vercel.json` allaqachon sozlangan: SPA rewrite, xavfsizlik header'lari,
CSP, cache siyosati, `/admin` uchun `noindex`.

### CSP ni toraytirish (tavsiya)

`vercel.json` ichida hozir `connect-src 'self' https:` turibdi. Deploy'dan keyin
uni aniq domenga almashtiring:

```json
"connect-src 'self' https://<railway-domain>"
```

---

## 4️⃣ Telegram BotFather sozlamalari

```
/setdomain      → https://<loyiha>.vercel.app
/newapp yoki /myapps → Mini App URL: https://<loyiha>.vercel.app
```

Menu button: **Ilovani ochish** → Web App URL = Vercel domeni.

---

## 5️⃣ Telefon raqamlarni standartlashtirish (bir marta)

Eski bazadagi raqamlar turli formatda saqlangan bo'lishi mumkin
(`901234567`, `+998 90 123 45 67`). Bu holda qarzdor Mini App'da
o'z qarzini ko'rmaydi. Deploy'dan keyin bir marta ishga tushiring:

```bash
# 1) Avval nima o'zgarishini ko'rish (hech narsa yozilmaydi)
railway run python scripts/migrate_phones.py

# 2) Natijani ko'rib chiqqach — qo'llash
railway run python scripts/migrate_phones.py --apply
```

Skript dublikat raqamlar haqida ham ogohlantiradi — ularni qo'lda
birlashtirish kerak, aks holda `clients` uchun unikal indeks yaratilmaydi.

---

## 6️⃣ SEO (deploy'dan keyin)

1. `frontend/index.html`, `public/robots.txt`, `public/sitemap.xml` ichidagi
   `https://qarzdaftar.vercel.app` ni **o'z domeningizga** almashtiring.
2. Quyidagi rasmlarni `frontend/public/` ga qo'shing:
   - `og-image.png` — 1200×630 (Telegram/Google preview)
   - `apple-touch-icon.png` — 180×180
3. [Google Search Console](https://search.google.com/search-console) →
   domenni qo'shing → `sitemap.xml` ni yuboring.
4. Tekshirish:
   - [Rich Results Test](https://search.google.com/test/rich-results) — JSON-LD
   - [PageSpeed Insights](https://pagespeed.web.dev/)
   - [securityheaders.com](https://securityheaders.com/)

---

## ⚠️ Muhim eslatmalar

**Railway'da `numReplicas` doim `1` bo'lsin.**
Bot va scheduler ilova ichida ishlaydi; ikkita nusxa bo'lsa har bir xabar
ikki marta yuboriladi va kunlik eslatmalar takrorlanadi.
Kelajakda kengaytirish kerak bo'lsa — bot/scheduler ni alohida servisga ajrating.

**Rate limiter xotirada ishlaydi.** Bitta instans uchun yetarli. Bir nechta
replika kerak bo'lsa Redis'ga o'tkazish lozim (`app/core/ratelimit.py`).

**`.env` hech qachon commit qilinmasin** — `.gitignore` qo'shildi.
Agar `backend/.env` ilgari GitHub'ga tushgan bo'lsa, `BOT_TOKEN` va
`SECRET_KEY` ni **almashtiring** (@BotFather → `/revoke`).
