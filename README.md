# UZ Temiryo'l — Django backend (NeftBacend)

Bu Firestore o'rniga ishlaydigan **Django REST + PostgreSQL** backendi.
Saytning butun logikasi, ma'lumot oqimi va hisobot (PDF jadval) hisob-kitoblari
**o'zgartirilmasdan** ko'chirilgan — frontend (Next.js) shu API'ga ulanadi.

> **Eslatma:** Bu repo **ildizi = Django loyiha ildizi** (`manage.py` shu yerda).
> Lokal monorepoda u `bacend/` papkasida turadi — README'dagi `cd bacend`
> faqat o'sha holatga tegishli; klon qilingan repoda esa to'g'ridan-to'g'ri ildizdan
> ishlaysiz.

---

## 0. Serverga joylash — qisqacha (GitHub → server)

Backend serverda **to'xtamasdan** (24/7) ishlashi uchun:

**A) Docker bilan (eng oson — DigitalOcean App Platform / istalgan Docker host):**
1. Bu reponi serverga/App Platformga ulang (GitHubdan).
2. Quyidagi muhit o'zgaruvchilarini bering (App Platform UI yoki `.env`):
   `DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY=<random>`, `DJANGO_ALLOWED_HOSTS=<domen/ip>`,
   `DATABASE_URL=<postgres url>`, `CORS_ALLOWED_ORIGINS=<frontend domeni>`,
   `REDIS_URL=<redis url>` (WebSocket ko'p-worker uchun).
3. Dockerfile o'zi `migrate` qilib, `daphne` (ASGI — HTTP + WebSocket) ni `$PORT` da ishga tushiradi.
4. Boshlang'ich ma'lumot: bir marta `python manage.py seed` va
   `python manage.py create_access_code 2727 --name "Admin"`.

**B) DigitalOcean Droplet (VPS) bilan:** pastdagi "5. Serverga joylashtirish → Variant B" ga qarang (venv + daphne + systemd + Nginx).

`SECRET_KEY` generatsiya:
```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

---

## 1. Tezkor ishga tushirish (lokal, sqlite)

```bash
# 1) Virtual muhitni faollashtirish (venv loyiha ildizida)
#    Windows PowerShell:
..\venv\Scripts\Activate.ps1
#    Git Bash:
source ../venv/Scripts/activate

# 2) Bog'liqliklarni o'rnatish
pip install -r requirements.txt

# 3) Muhit fayli (.env allaqachon sqlite uchun tayyor)
#    PostgreSQL uchun .env ichidagi DATABASE_URL ni oching (pastga qarang)

# 4) Ma'lumotlar bazasi
python manage.py migrate
python manage.py seed                 # uzellar, zapravkalar, settings, savollar
python manage.py create_access_code 778899 --name "Bosh Admin" --role admin

# 5) (ixtiyoriy) Django admin paneli uchun superuser
python manage.py createsuperuser

# 6) Serverni ishga tushirish
python manage.py runserver            # http://127.0.0.1:8000
```

Tekshirish: `http://127.0.0.1:8000/api/health/` → `{"status":"ok"}`.

---

## 2. PostgreSQL (production bazasi)

1. PostgreSQL'da baza va foydalanuvchi yarating:
   ```sql
   CREATE DATABASE uztemiryol;
   CREATE USER uzuser WITH PASSWORD 'STRONG_PASSWORD';
   GRANT ALL PRIVILEGES ON DATABASE uztemiryol TO uzuser;
   ```
2. `.env` ichida `DATABASE_URL` ni yoqing:
   ```
   DATABASE_URL=postgres://uzuser:STRONG_PASSWORD@localhost:5432/uztemiryol
   ```
3. Migratsiya va seed:
   ```bash
   python manage.py migrate
   python manage.py seed
   python manage.py create_access_code 778899 --name "Bosh Admin"
   ```

`DATABASE_URL` berilmasa avtomatik **sqlite** ishlatiladi (faqat lokal uchun).

---

## 3. Loyiha tuzilishi

```
bacend/
├── config/              # settings, urls, wsgi/asgi
├── common/              # umumiy: vaqt (timeutil), raqam (numbers), DRF asoslari
├── accounts/            # auth (kod -> JWT), kirish kodlari, xodimlar, sessiyalar
├── catalog/             # uzellar, zapravkalar, settings, savollar, variantlar, limitlar
│   ├── reference.py     #   statik ma'lumot (uzellar.ts nusxasi) + seed konstantalar
│   └── management/commands/seed.py
├── submissions/         # submissionlar (4 toifa), summary, fuelRecords + xizmat mantig'i
├── reports/             # hisobot agregatsiyasi (report-service.ts nusxasi)
├── audit/               # audit izlari
├── requirements.txt
├── .env / .env.example
├── Dockerfile / docker-compose.yml / gunicorn.conf.py
└── manage.py
```

### Firestore → Django moslik

| Firestore kolleksiya | Django model | Endpoint |
|---|---|---|
| `access_codes` | `accounts.AccessCode` | `/api/access-codes/` |
| `staff` | `accounts.Staff` | `/api/staff/` |
| `blocked_codes` | `accounts.BlockedCode` | `/api/blocked-codes/` |
| `active_sessions` | `accounts.ActiveSession` | `/api/active-sessions/` |
| `security_events` | `accounts.SecurityEvent` | `/api/security-events/` |
| `device_locks` | `accounts.DeviceLock` | `/api/device-locks/` |
| `uzellar` / `zapravkalar` | `catalog.Uzel` / `Zapravka` | `/api/uzellar/` `/api/zapravkalar/` |
| `settings` | `catalog.Setting` | `/api/settings/` |
| `questions` | `catalog.Question` | `/api/questions/` |
| `variants` | `catalog.Variant` | `/api/variants/` |
| `limits` | `catalog.Limit` | `/api/limits/` |
| `closedDays` | `catalog.ClosedDay` | `/api/closed-days/` |
| `approvals` | `catalog.Approval` | `/api/approvals/` |
| `submissions` | `submissions.Submission` | `/api/submissions/` |
| `dailySummaries` | `submissions.DailySummary` | `/api/daily-summaries/` |
| `yearlySummaries` | `submissions.YearlySummary` | `/api/yearly-summaries/` |
| `fuelRecords` | `submissions.FuelRecord` | `/api/fuel-records/` |
| `audit_logs` | `audit.AuditLog` | `/api/audit-logs/` |

---

## 4. Autentifikatsiya (kod-asosli, Firestore sessiyasi o'rniga)

- **Login:** `POST /api/auth/login/` body `{ "code": "778899", "deviceId": "..." }`
  - `access_codes` (admin/developer) yoki `staff.tabelNumber` (worker) tekshiriladi;
  - `blocked_codes` da bo'lsa rad etiladi;
  - muvaffaqiyatli bo'lsa **12 soatlik JWT** qaytadi.
- Keyingi so'rovlarda sarlavha: `Authorization: Bearer <token>`.
- `GET /api/auth/me/` — joriy sessiya. `POST /api/auth/heartbeat/` — onlayn presence.
  `POST /api/auth/logout/` — sessiyani o'chirish.

Rollar: `worker` (faqat o'z `stationId`), `admin`/`developer` (to'liq).
Tahrirlash faqat shu kun ichida (worker uchun), o'chirish faqat admin.

## Real-time (WebSocket — Django Channels)

Worker ma'lumot qo'shganda admin paneldagi jadval **darhol** yangilanadi.

- Endpoint: `ws://SERVER/ws/updates/?token=<JWT>` (token so'rov satrida).
- Backend yozuv **yaratilganda/yangilanganda/o'chirilganda** `updates` guruhiga
  xabar yuboradi: `{topic, action, id}` (`transaction.on_commit` orqali — klient
  qayta yuklaganda yangi ma'lumotni albatta ko'radi).
- Qamrab olingan **topic**lar (Django signals + submission xizmati):
  `submissions`, `presence`, `access_codes`, `blocked_codes`, `staff`,
  `limits`, `questions`, `variants`, `settings`, `closed_days`, `approvals`,
  `audit_logs`, `security_events`, `device_locks`.
  - `presence` faqat **login/logout** da (har 20s heartbeat'da emas — spam yo'q).
- Frontend `pollSubscribe(..., wsTopics="<topic>")` shu xabar kelganda darhol
  qayta yuklaydi; polling esa zaxira (fallback) bo'lib qoladi. Ulangan jadvallar:
  submission jadvallari, onlayn xodimlar (presence), admin kodlar, bloklangan
  kodlar, xodimlar, savollar, variantlar, rusum sozlamalari.
- **Dev:** `runserver` daphne (ASGI) orqali WebSocket'ni o'zi serve qiladi, channel
  layer **xotirada** (in-memory) — qo'shimcha xizmat shart emas.
- **Production:** server **daphne** (ASGI) bilan ishlaydi (Dockerfile/Procfile).
  Ko'p-workerli bo'lsa `.env` da `REDIS_URL` bering (channel layer Redis'ga o'tadi).
  docker-compose'da `redis` xizmati allaqachon ulangan.

Frontend env: `NEXT_PUBLIC_WS_BASE_URL=ws://127.0.0.1:8000/ws` (bo'sh bo'lsa
`NEXT_PUBLIC_API_BASE_URL` dan avtomatik hosil bo'ladi).

### Frontend (Next.js) ulanishi
`.env.local` ga qo'shing va Firestore chaqiruvlarini shu API'ga yo'naltiring:
```
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api
```
JWT ni `Authorization: Bearer` sarlavhasida yuboring. Javoblar Firestore hujjat
shakliga mos (camelCase maydonlar, `id` string), shuning uchun frontend modellari
o'zgarmaydi.

---

## 5. Serverga joylashtirish (production)

### Variant A — Docker (tavsiya etiladi)
```bash
# .env da DJANGO_SECRET_KEY, POSTGRES_PASSWORD, DJANGO_ALLOWED_HOSTS to'ldiring
docker compose up -d --build
docker compose exec web python manage.py seed
docker compose exec web python manage.py create_access_code 778899 --name "Bosh Admin"
```
Backend: `http://SERVER_IP:8000`. PostgreSQL konteyner ichida ko'tariladi.

### Variant B — Gunicorn + Nginx (VPS)
```bash
# Serverda:
git clone <repo> && cd <repo>/bacend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# .env (DEBUG=False, SECRET_KEY, DATABASE_URL, ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS)
nano .env

python manage.py migrate
python manage.py collectstatic --noinput
python manage.py seed
python manage.py create_access_code 778899 --name "Bosh Admin"

# daphne (ASGI — HTTP + WebSocket; systemd xizmati sifatida tavsiya etiladi)
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

> Ko'p-workerli (yuqori yuk) uchun `.env` da `REDIS_URL` bering, aks holda
> WebSocket xabarlari workerlar orasida tarqalmaydi (in-memory faqat 1 worker).

Namuna `systemd` xizmati `/etc/systemd/system/uztemiryol.service`:
```ini
[Unit]
Description=UZ Temiryol backend (ASGI)
After=network.target postgresql.service

[Service]
WorkingDirectory=/srv/uztemiryol/bacend
EnvironmentFile=/srv/uztemiryol/bacend/.env
ExecStart=/srv/uztemiryol/bacend/venv/bin/daphne -b 127.0.0.1 -p 8000 config.asgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Namuna Nginx (reverse proxy + static + **WebSocket**):
```nginx
server {
    listen 80;
    server_name api.example.uz;

    location /static/ { alias /srv/uztemiryol/bacend/staticfiles/; }

    # WebSocket (real-time)
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Production tekshiruv ro'yxati
- [ ] `DJANGO_DEBUG=False`
- [ ] Yangi `DJANGO_SECRET_KEY`
- [ ] `DJANGO_ALLOWED_HOSTS` server domeni/IP bilan
- [ ] `DATABASE_URL` PostgreSQL bilan
- [ ] `CORS_ALLOWED_ORIGINS` frontend domeni bilan
- [ ] HTTPS (Nginx + certbot), `DJANGO_CSRF_TRUSTED_ORIGINS`
- [ ] `python manage.py check --deploy` ogohlantirishlarini ko'rib chiqing
- [ ] Face ID uchun: `migrate` bajarilgan va sayt HTTPS da (pastga qarang)

### Face ID (yuz bilan kirish)

Yuz bo'yicha kirish ham XODIM (`staff.tabelNumber`), ham ADMIN
(`access_codes.code`) uchun ishlaydi. Biometrik shablon FAQAT serverda
quriladi va hech qachon API orqali tashqariga chiqmaydi; brauzer atigi
96x96 kulrang kadr yuboradi.

Face ID — QO'SHIMCHA yo'l, almashtiruvchi emas: login sahifasida yuz tugmasi
ham, kod maydoni ham doim turadi. Yuz tanilmasa (yoki kamera yo'q, HTTP,
shablon eskirgan) hech narsa bloklanmaydi — odam kodini yozib kiraveradi.

Joylashda e'tibor beriladigan narsalar:

1. **`python manage.py migrate` SHART.** Yangilanishda `access_codes` ga
   `photo` / `photoUpdatedAt` maydonlari qo'shildi — migratsiyasiz "Admin
   qo'shish" 500 xato beradi. O'sha `migrate` mavjud Face ID shablonlarini
   yangi algoritm (oval niqob) bo'yicha AVTOMATIK qayta quradi; hech kimdan
   qaytadan surat so'ralmaydi va qo'shimcha buyruq kerak emas.
2. **HTTPS majburiy.** Kamera (`getUserMedia`) faqat xavfsiz kontekstda
   ochiladi; HTTP da tugma "Kamera ishlamaydi" deydi va odamlar kod bilan
   kiraveradi.
3. **Bir nechta worker ishlatsangiz — umumiy kesh qo'ying.** Face ID ning
   tezlik chegarasi va "sovish" hisoblagichi Django keshida turadi; standart
   kesh har bir jarayonda ALOHIDA bo'lgani uchun chegara worker soniga
   ko'payadi. Redis (`django-redis`) ulansa, hisob butun server bo'yicha
   yagona bo'ladi. Bu xavfsizlik teshigi emas (asosiy himoya — yuz qarori,
   qurilma bloki va bloklangan kodlar), lekin chegara aniqroq ishlaydi.
4. **Chalkashlikka qarshi sozlamalar** (`.env`, standart qiymatlar odatda
   yetarli): `FACE_CROSS_RATIO=0.70` — admin bilan oddiy xodim orasida
   ikkilanish bo'lsa qanchalik qattiq talab qilish;
   `FACE_ENROLL_MIN_DISTANCE=0.10` — ro'yxatga olishda "bir xil odam" deb
   hisoblanadigan masofa. Barcha chegaralar `config/settings.py :: FACE_ID`
   da izohlangan.
5. **Algoritm yangilansa** (`accounts/face.py` dagi `TEMPLATE_VERSION`):
   `python manage.py rebuild_face_templates` — shablonlar saqlangan
   kadrlardan qayta quriladi, hech kimdan qaytadan surat so'ralmaydi.

---

## 6. Foydali buyruqlar

```bash
python manage.py check --deploy        # production xavfsizlik tekshiruvi
python manage.py seed --reset-questions # default savollarni qayta yozish
python manage.py createsuperuser        # /admin/ paneli uchun
```

Django admin paneli: `http://SERVER/admin/` — barcha jadvallarni qo'lda boshqarish.
