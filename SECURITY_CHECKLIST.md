# 🔒 Xavfsizlik va deploy tekshiruv ro'yxati

**Setup:** Backend → DigitalOcean **Droplet** (`deploy.sh` + `ssl.sh`) · Frontend → **Vercel** · Baza → **PostgreSQL**

> Bu fayl faqat **ko'rsatma** — hech qanday ilova mantig'i, ko'rinishi yoki ishlash
> jarayoniga tegmaydi. Buyruqlarni serverda (Droplet) bajarasiz.

---

## ✅ Allaqachon himoyalangan (kodga tegilmagan)

| Tahdid | Himoya |
|---|---|
| SQL Injection | Faqat Django ORM — raw SQL yo'q |
| IDOR | Worker faqat o'z `stationId`; o'chirish faqat admin; korxona-kod token egasi bo'yicha |
| Brute Force | Qurilma lockout (3 xato → bloklanadi) + login throttle |
| Session Hijacking | JWT 12 soat; HTTPS (certbot); secure cookie'lar (DEBUG=False) |
| CSRF | API JWT **Bearer** ishlatadi (cookie emas) → CSRF ta'sir qilmaydi |
| File Upload | Backend fayl qabul qilmaydi — hujum yuzasi yo'q |
| XSS | JSON API + React auto-escape + PDF `esc()` |
| Header'lar | Bugun qo'shildi: `Referrer-Policy`, `X-Frame-Options: DENY`, `nosniff` (zararsiz) |

---

## ⚠️ Deploy'dan oldin QILISH SHART (operatsion — kodga tegmaydi)

### 1. 🔴 Admin kirish kodini almashtiring (ENG MUHIM)
`deploy.sh` **`2727`** kodini yaratadi — bu repoda ochiq yozilgan, oson topiladi.
Serverda kuchli (uzun, tasodifiy) kod bilan almashtiring:

```bash
cd /root/NeftBacend
# Yangi kuchli admin kod (masalan 8+ raqamli, oson topilmaydigan):
venv/bin/python manage.py create_access_code 47391026 --name "Admin"
# Eski zaif 2727 ni bloklang yoki o'chiring (admin panel → kodlar, yoki):
venv/bin/python manage.py shell -c "from accounts.models import AccessCode; AccessCode.objects.filter(pk='2727').delete()"
systemctl restart neftbacend
```

### 2. 🟠 CORS ni faqat Vercel domeniga qulflang
`deploy.sh` `CORS_ALLOW_ALL_ORIGINS=True` qo'yadi — ya'ni **istalgan sayt** API'ngizga
so'rov yubora oladi. Frontend Vercel'da bo'lgani uchun uni aniq manzilga qulflang.
`/root/NeftBacend/.env` faylini tahrirlang:

```bash
nano /root/NeftBacend/.env
```
```ini
CORS_ALLOW_ALL_ORIGINS=False
CORS_ALLOWED_ORIGINS=https://SIZNING-LOYIHA.vercel.app
CORS_ALLOWED_ORIGIN_REGEXES=
```
> Custom domeningiz bo'lsa vergul bilan qo'shing:
> `CORS_ALLOWED_ORIGINS=https://loyiha.vercel.app,https://sayt.uz`
> Keyin: `systemctl restart neftbacend`

### 3. 🟠 Admin panel maxfiy manzili (kod bugun tayyorlandi)
`/admin/` ni botlar avtomatik qidiradi. `.env` ga maxfiy yo'l qo'ying:
```ini
DJANGO_ADMIN_URL=boshqaruv-7x9k2m/
```
Endi Django admin `/admin/` da emas, `/boshqaruv-7x9k2m/` da ochiladi.
(Bo'sh qoldirsangiz standart `/admin/` ishlaydi — hech narsa buzilmaydi.)

### 4. CSRF trusted origins (admin login HTTPS ostida ishlashi uchun)
```ini
DJANGO_CSRF_TRUSTED_ORIGINS=https://209.38.204.88.sslip.io
```

### 5. Django superuser — kuchli parol
```bash
venv/bin/python manage.py createsuperuser   # uzun, murakkab parol qo'ying
```

**Har `.env` o'zgarishidan keyin:** `systemctl restart neftbacend`

---

## 🛡️ Server (Droplet OS) himoyasi — DDoS / SSH / Admin panel

### UFW firewall (faqat kerakli portlar)
```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'      # 80 + 443
ufw --force enable
```

### fail2ban (SSH va login brute-force bloklash)
```bash
apt-get install -y fail2ban
systemctl enable --now fail2ban
```

### SSH kuchaytirish — `/etc/ssh/sshd_config`
```
PermitRootLogin prohibit-password   # yoki: no
PasswordAuthentication no           # faqat SSH kalit bilan kiring
```
```bash
systemctl restart ssh
```

### Nginx rate-limit (DDoS yumshatish) — ixtiyoriy
`/etc/nginx/sites-available/neftbacend` `server { ... }` ichiga:
```nginx
# http { } blokiga (nginx.conf):  limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
location / {
    limit_req zone=api burst=60 nodelay;
    # ... mavjud proxy_pass sozlamalari o'zgarmaydi
}
```

### 🟢 Cloudflare (TEKIN) — eng kuchli DDoS himoyasi
To'liq DDoS himoyasi ilova darajasida emas, **infratuzilma**da bo'ladi:
o'z domeningizni Cloudflare'ga ulang (turuncha bulut = proxy). Bepul reja
volumetrik DDoS, bot filtri va WAF beradi. `sslip.io` o'rniga real domen tavsiya.

---

## ✅ Deploy'dan keyin tekshiruv

```bash
cd /root/NeftBacend
venv/bin/python manage.py check --deploy      # ogohlantirish bo'lmasligi kerak
curl https://209.38.204.88.sslip.io/api/health/   # {"status":"ok"}
```

- [ ] `DJANGO_DEBUG=False` (`.env` da) — xato sahifasi batafsil bo'lmasligi kerak
- [ ] `2727` admin kodi almashtirildi / bloklandi
- [ ] CORS faqat Vercel domeniga qulflangan
- [ ] `DJANGO_ADMIN_URL` maxfiy — `/admin/` endi 404 beradi
- [ ] UFW + fail2ban yoqilgan
- [ ] Vercel'da: `NEXT_PUBLIC_API_BASE_URL=https://209.38.204.88.sslip.io/api`,
      `NEXT_PUBLIC_WS_BASE_URL=wss://209.38.204.88.sslip.io/ws`

---

## Bugun kodda o'zgargan (faqat shu — logika/ko'rinishga tegmaydi)
- `config/settings.py` — zararsiz xavfsizlik header'lari + `ADMIN_URL` (default `admin/`)
- `config/urls.py` — admin manzili `settings.ADMIN_URL` dan (default `admin/`)

`deploy.sh`, `ssl.sh`, ilova mantig'i, PDF jadvallar, frontend — **tegilmadi**.
