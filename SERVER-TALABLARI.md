# ⛔ ICHKI HUJJAT — BEGONAGA YUBORILMAYDI

> **Bu faylni serverchilarga bermang.** Unda tizimning ichki tuzilishi va
> himoya sxemasi yozilgan.
>
> Yuboriladigan matn alohida faylda: **`SERVERCHILARGA-XAT.md`** — u toza,
> unda parol ham, kirish kodi ham, maxfiy kalit ham yo'q. Ikkala blokni
> nusxalab yuborsangiz kifoya.

---

## Loyihaning texnik holati (nega talablar ro'yxati qisqa)

| Narsa | Holat |
|---|---|
| Til / freymvork | Python 3.13 + Django 6.0 + DRF |
| Server turi | ASGI (daphne) — HTTP **va** WebSocket bitta portda |
| Baza | PostgreSQL (lokal dev'da sqlite) |
| Face ID | **Sof Python** — numpy/opencv/dlib/GPU **kerak emas** |
| Rasm/fayl xotirasi | **Kerak emas** — suratlar bazada matn (base64) sifatida |
| Tashqi xizmatlar | **Yo'q** — Firebase/S3/SMTP/to'lov tizimi ishlatilmaydi |
| Redis | **Ixtiyoriy** (faqat ko'p-workerli rejimda) |
| RAM | 2 GB yetadi (4 GB qulay) |

---

## Xavfsizlik: nima beriladi, nima berilmaydi

### Beriladi (xavfsiz)

| Narsa | Nega xavfsiz |
|---|---|
| **SSH ochiq kaliti** (`id_ed25519.pub`) | Ochiq kalit — qulf teshigi, kalitning o'zi emas. U bilan hech kim sizning kompyuteringizga kira olmaydi. |
| Kod arxivi (`.tar.gz`) | Loyihaning o'zi baribir shu serverda ishlaydi. Lekin arxivni to'g'ri tayyorlash kerak — pastga qarang. |
| Frontend domeni (CORS uchun) | Ochiq ma'lumot. |
| `SERVERCHILARGA-XAT.md` | Maxsus tozalangan — maxfiy qiymat yo'q. |

### Berilmaydi

- ❌ **Bu fayl** (`SERVER-TALABLARI.md`) — ichki himoya sxemasi.
- ❌ GitHub akkaunti, parol yoki repozitoriyga kirish huquqi — deploy uchun **umuman kerak emas**.
- ❌ Email va uning paroli — tizim email yubormaydi, SMTP ishlatmaydi.
- ❌ SSH **maxfiy** kaliti (`id_ed25519`, `.pub` siz).
- ❌ Kirish kodlari (admin/dasturchi kodlari) — ular serverni boshqaradi, tizimga kirmaydi.
- ❌ `ADMIN_VAULT_PASSWORD`, `DJANGO_SECRET_KEY`, `DJANGO_ADMIN_URL` qiymatlari.
- ❌ Bazaning zaxira nusxasi (`.sql.gz`, `db.sqlite3`) — ichida real hisobot ma'lumotlari.

---

## Arxiv tayyorlashda NIMANI CHIQARIB TASHLASH KERAK

Serverchilarga (yoki umuman tashqariga) beriladigan `.tar.gz` ichida quyidagilar
**bo'lmasligi shart** — bularning hammasida real ma'lumot yoki sir bor:

| Chiqarib tashlanadi | Nima uchun |
|---|---|
| `.env` | Ishlayotgan `DJANGO_SECRET_KEY` shu yerda |
| `db.sqlite3`, `db.sqlite3-wal`, `db.sqlite3-shm` | Real hisobotlar, xodim suratlari, kirish kodlari |
| `db.sqlite3.backup-*` (6 ta fayl) | Xuddi shunday — eski nusxalar |
| `report_*.csv` | Real hisobot eksporti |
| `venv/`, `__pycache__/`, `staticfiles/` | Keraksiz, hajmni shishiradi |
| `.git/` | Butun tarix — ichida eski `.env` qolgan bo'lishi mumkin |

Toza arxiv yig'ish (Git Bash):

```bash
cd /c/Users/1/Desktop/OsytemBacemd
tar --exclude='.git' --exclude='.env' --exclude='venv' \
    --exclude='__pycache__' --exclude='staticfiles' \
    --exclude='db.sqlite3*' --exclude='report_*.csv' \
    --exclude='SERVER-TALABLARI.md' \
    -czf ~/Desktop/uztemiryol-backend.tar.gz bacend/
```

Yuborishdan **oldin** tekshiring — ro'yxatda yuqoridagilar chiqmasligi kerak:

```bash
tar -tzf ~/Desktop/uztemiryol-backend.tar.gz | grep -E '\.env|sqlite|\.git/|report_' || echo "TOZA"
```

---

## Serverchilar baribir ko'ra oladigan narsalar — buni bilib turing

Serverga root/sudo huquqi bo'lgan odam texnik jihatdan **shu serverdagi bazani ham
o'qiy oladi** — bu har qanday serverda shunday, buni "yopib" bo'lmaydi. Shuning uchun:

1. Barcha maxfiy qiymatlar (`DJANGO_SECRET_KEY`, baza paroli) **server ustida
   generatsiya qilinsin** (`openssl rand -hex 50`) — chat/xat orqali yuborilmasin.
2. Ishga tushgandan **keyin darhol o'zgartiring** (qiymatlar shu yerda emas —
   `deploy.sh` va `config/settings.py` dagi standartlarga qarang):
   - standart admin kirish kodi → yangi kod,
   - `ADMIN_VAULT_PASSWORD` → yangi parol,
   - `.env` ga `DJANGO_ADMIN_URL=<maxfiy-yol>/` — `/admin/` botlarga ko'rinmaydi.
3. Bazaning zaxira nusxasini vaqti-vaqti bilan **o'z kompyuteringizga** ham
   ko'chirib oling (server yo'qolsa, serverdagi backup ham yo'qoladi).
4. Serverchilar ishi tugagach: SSH kalitini almashtirish yoki ularning kirishini
   yopishni so'rash mumkinmi — buni oldindan kelishib oling.

---

## Ishga tushirilgandan keyin `.env` da bo'lishi kerak bo'lganlar

```env
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<serverda generatsiya qilinadi>
DJANGO_ALLOWED_HOSTS=api.sizning-domen,127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://api.sizning-domen
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_TIME_ZONE=Asia/Tashkent
DJANGO_ADMIN_URL=<maxfiy-yol>/

DATABASE_URL=postgres://<user>:<parol>@localhost:5432/<baza>

CORS_ALLOWED_ORIGINS=https://<saytning-domeni>
CORS_ALLOW_ALL_ORIGINS=False

ADMIN_VAULT_PASSWORD=<yangi parol>
FACE_ID_ENABLED=1
```

Frontend tomonda (Vercel yoki qayerda joylashgan bo'lsa):

```env
NEXT_PUBLIC_API_BASE_URL=https://api.sizning-domen/api
NEXT_PUBLIC_WS_BASE_URL=wss://api.sizning-domen/ws
```

## Tekshiruv (deploy tugagach)

```bash
curl https://api.sizning-domen/api/health/     # {"status": "ok"} qaytishi kerak
systemctl status uztemiryol                    # active (running)
journalctl -u uztemiryol -n 50                 # xatolik yo'qligi
```
