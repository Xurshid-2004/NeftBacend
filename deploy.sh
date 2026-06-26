#!/usr/bin/env bash
# UZ Temiryo'l backend — DigitalOcean Droplet (Ubuntu) uchun bir bosqichli deploy.
# Ishlatish:  cd /root/NeftBacend && git pull && bash deploy.sh
# .env, baza (SQLite), seed, admin kod, daphne (24/7 systemd), nginx — hammasini qiladi.

set -e
cd /root/NeftBacend

PUBIP=209.38.204.88

echo "==> 0/8 Swap (xotira zaxirasi)"
if [ ! -f /swapfile ]; then
  fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile
fi
swapon /swapfile 2>/dev/null || true
grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab

echo "==> 1/8 .env sozlama fayli"
if [ ! -f .env ]; then
  {
    echo "DJANGO_DEBUG=False"
    echo "DJANGO_SECRET_KEY=$(openssl rand -hex 50)"
    echo "DJANGO_ALLOWED_HOSTS=${PUBIP},localhost,127.0.0.1"
    echo "DJANGO_SECURE_SSL_REDIRECT=False"
    echo "CORS_ALLOW_ALL_ORIGINS=True"
  } > .env
  echo "    .env yaratildi"
else
  echo "    .env allaqachon bor — tegilmadi"
fi

echo "==> 2/8 Virtual muhit va kutubxonalar"
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt

echo "==> 3/8 Ma'lumotlar bazasi (migratsiya)"
venv/bin/python manage.py migrate --noinput

echo "==> 4/8 Statik fayllar"
venv/bin/python manage.py collectstatic --noinput

echo "==> 5/8 Boshlang'ich ma'lumot (uzellar/zapravkalar/savollar) + admin kod 2727"
venv/bin/python manage.py seed
venv/bin/python manage.py create_access_code 2727 --name "Admin" || true

echo "==> 6/8 daphne xizmati (24/7, o'zi qayta ishga tushadi)"
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

echo "==> 7/8 Nginx (port 80 -> backend, WebSocket bilan)"
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

echo "==> 8/8 Tekshiruv"
sleep 2
systemctl is-active neftbacend && echo "    backend: ishlayapti"
systemctl is-active nginx && echo "    nginx: ishlayapti"

echo ""
echo "================================================================"
echo "  TAYYOR! Backend 24/7 ishlayapti."
echo "  Tekshiring:  http://${PUBIP}/api/health/"
echo "  Admin paneli kirish kodi:  2727"
echo "  Sozlama fayli:  /root/NeftBacend/.env"
echo "================================================================"
