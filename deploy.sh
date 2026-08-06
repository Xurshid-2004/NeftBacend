#!/usr/bin/env bash
# UZ Temiryo'l backend — DigitalOcean Droplet (Ubuntu) uchun bir bosqichli deploy.
# Ishlatish:  cd /root/NeftBacend && git pull && bash deploy.sh
# .env, baza (PostgreSQL), seed, admin kod, daphne (24/7 systemd), nginx — hammasini qiladi.
#
# Eslatma: lokal (rivojlantirish) kompyuteringiz bunga tegishli emas — u DATABASE_URL
# yo'qligi sababli hamon SQLite bilan ishlayveradi. Faqat shu server (Droplet)
# PostgreSQL'ga o'tadi.

set -e
cd /root/NeftBacend

PUBIP=209.38.204.88

echo "==> 0/10 Swap (xotira zaxirasi)"
if [ ! -f /swapfile ]; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile
fi
swapon /swapfile 2>/dev/null || true
grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab

echo "==> 1/10 PostgreSQL o'rnatish"
apt-get update -qq
apt-get install -y -qq postgresql postgresql-contrib libpq-dev
systemctl enable postgresql >/dev/null 2>&1 || true
systemctl start postgresql

echo "==> 2/10 Ma'lumotlar bazasi (PostgreSQL) va .env sozlama fayli"
if [ ! -f .env ]; then
  DB_NAME="uztemiryol"
  DB_USER="uzuser"
  DB_PASS="$(openssl rand -hex 24)"

  # Idempotent: skript qayta ishga tushirilsa ham xato bermaydi (foydalanuvchi/baza
  # allaqachon bo'lsa, qayta yaratishga urinmaydi).
  sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';"
  sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

  {
    echo "DJANGO_DEBUG=False"
    echo "DJANGO_SECRET_KEY=$(openssl rand -hex 50)"
    echo "DJANGO_ALLOWED_HOSTS=${PUBIP},localhost,127.0.0.1"
    echo "DJANGO_SECURE_SSL_REDIRECT=False"
    echo "CORS_ALLOW_ALL_ORIGINS=True"
    echo "DATABASE_URL=postgres://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"
  } > .env
  echo "    .env yaratildi (PostgreSQL: ${DB_NAME}, faqat localhost'dan kirish mumkin)"
else
  echo "    .env allaqachon bor — tegilmadi (PostgreSQL foydalanuvchi/baza ham tegilmadi)"
fi

echo "==> 3/10 Virtual muhit va kutubxonalar"
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt

echo "==> 4/10 Ma'lumotlar bazasi (migratsiya)"
venv/bin/python manage.py migrate --noinput

echo "==> 5/10 Statik fayllar"
venv/bin/python manage.py collectstatic --noinput

echo "==> 6/10 Boshlang'ich ma'lumot (uzellar/zapravkalar/savollar) + admin kod 2727"
venv/bin/python manage.py seed
venv/bin/python manage.py create_access_code 2727 --name "Admin" || true

echo "==> 7/10 daphne xizmati (24/7, o'zi qayta ishga tushadi)"
cat > /etc/systemd/system/neftbacend.service <<UNIT
[Unit]
Description=UZ Temiryol backend (daphne ASGI)
After=network.target

[Service]
WorkingDirectory=/root/NeftBacend
EnvironmentFile=/root/NeftBacend/.env
ExecStart=/root/NeftBacend/venv/bin/daphne -b 127.0.0.1 -p 8000 config.asgi:application
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable neftbacend >/dev/null 2>&1 || true
systemctl restart neftbacend

echo "==> 8/10 Nginx (port 80 -> backend, WebSocket bilan)"
cat > /etc/nginx/sites-available/neftbacend <<'NGINX'
server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 20M;

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
NGINX
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/neftbacend /etc/nginx/sites-enabled/neftbacend
nginx -t
systemctl restart nginx

echo "==> 9/10 Kunlik zaxira nusxa (pg_dump + cron)"
mkdir -p /var/backups/uztemiryol
cat > /usr/local/bin/uztemiryol-zaxira.sh <<'ZAXIRA'
#!/usr/bin/env bash
# Bazaning zaxira nusxasi. Cron har kuni 03:00 da ishga tushiradi
# (/etc/cron.d/uztemiryol-zaxira). Qo'lda ham chaqirsa bo'ladi:
#     bash /usr/local/bin/uztemiryol-zaxira.sh
#
# DIQQAT: nusxa SHU SERVERNING o'zida saqlanadi. Bu noto'g'ri o'chirib
# yuborishdan himoya qiladi, lekin serverning o'zi yo'qolsa yordam bermaydi —
# vaqti-vaqti bilan /var/backups/uztemiryol dan boshqa joyga (kompyuter yoki
# bulut) ko'chirib turing.
set -euo pipefail

ENV_FILE=/root/NeftBacend/.env
OUT_DIR=/var/backups/uztemiryol
SAQLASH_KUNI=14

DATABASE_URL="$(grep -E '^DATABASE_URL=' "$ENV_FILE" 2>/dev/null | head -n1 | cut -d= -f2- || true)"
if [ -z "${DATABASE_URL}" ]; then
  echo "zaxira: ${ENV_FILE} da DATABASE_URL topilmadi — to'xtatildi" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
FAYL="$OUT_DIR/uztemiryol-$(date +%Y%m%d-%H%M).sql.gz"

# Avval vaqtinchalik faylga yozamiz: pg_dump yarim yo'lda uzilib qolsa, nosoz
# fayl "tayyor zaxira" bo'lib qolmasin. Faqat to'liq tugagach nomi to'g'rilanadi.
pg_dump --no-owner --no-privileges "$DATABASE_URL" | gzip -9 > "$FAYL.tmp"
mv "$FAYL.tmp" "$FAYL"

# 14 kundan eski nusxalarni tozalash (disk to'lib ketmasligi uchun)
find "$OUT_DIR" -name 'uztemiryol-*.sql.gz' -mtime +${SAQLASH_KUNI} -delete

echo "zaxira tayyor: $FAYL ($(du -h "$FAYL" | cut -f1))"
ZAXIRA
chmod +x /usr/local/bin/uztemiryol-zaxira.sh

cat > /etc/cron.d/uztemiryol-zaxira <<'CRON'
# Har kuni 03:00 da bazaning zaxira nusxasi
0 3 * * * root /usr/local/bin/uztemiryol-zaxira.sh >> /var/log/uztemiryol-zaxira.log 2>&1
CRON
chmod 644 /etc/cron.d/uztemiryol-zaxira

# Darhol bitta nusxa olamiz — ishlayotganiga hozir ishonch hosil qilish uchun.
# Xato bo'lsa ham deploy to'xtamaydi.
bash /usr/local/bin/uztemiryol-zaxira.sh \
  || echo "    OGOHLANTIRISH: zaxira nusxa olinmadi — yuqoridagi xatoga qarang"

echo "==> 10/10 Tekshiruv"
sleep 2
systemctl is-active postgresql && echo "    postgresql: ishlayapti"
systemctl is-active neftbacend && echo "    backend: ishlayapti"
systemctl is-active nginx && echo "    nginx: ishlayapti"

echo ""
echo "================================================================"
echo "  TAYYOR! Backend 24/7 ishlayapti — ma'lumotlar bazasi: PostgreSQL."
echo "  Tekshiring:  http://${PUBIP}/api/health/"
echo "  Admin paneli kirish kodi:  2727"
echo "  Sozlama fayli:  /root/NeftBacend/.env  (DB parolini shu yerdan ko'rasiz)"
echo "  Zaxira nusxa:   /var/backups/uztemiryol/  (har kuni 03:00, 14 kun saqlanadi)"
echo "                  qo'lda: bash /usr/local/bin/uztemiryol-zaxira.sh"
echo "================================================================"
