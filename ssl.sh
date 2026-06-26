#!/usr/bin/env bash
# Droplet'ga bepul HTTPS (SSL) qo'shadi — domen sotmasdan, sslip.io + Let's Encrypt.
# Ishlatish:  cd /root/NeftBacend && git pull && bash ssl.sh
# Natijada backend https://<ip>.sslip.io da ishlaydi (Vercel to'g'ridan-to'g'ri ulanadi).

set -e
IP=209.38.204.88
DOMAIN=${IP}.sslip.io

echo "==> 1/4 certbot o'rnatish"
apt-get update -qq
apt-get install -y -qq certbot python3-certbot-nginx

echo "==> 2/4 Nginx domenini sozlash ($DOMAIN)"
sed -i "s/server_name [^;]*;/server_name ${DOMAIN};/" /etc/nginx/sites-available/neftbacend
nginx -t
systemctl reload nginx

echo "==> 3/4 Let's Encrypt sertifikat (HTTPS yoqish)"
certbot --nginx -d "${DOMAIN}" \
  --non-interactive --agree-tos --register-unsafely-without-email --redirect

echo "==> 4/4 ALLOWED_HOSTS ga domen qo'shish + restart"
if ! grep -q "${DOMAIN}" /root/NeftBacend/.env; then
  sed -i "s|^DJANGO_ALLOWED_HOSTS=|DJANGO_ALLOWED_HOSTS=${DOMAIN},|" /root/NeftBacend/.env
fi
systemctl restart neftbacend

echo ""
echo "================================================================"
echo "  TAYYOR! Backend endi HTTPS'da ishlayapti:"
echo "    https://${DOMAIN}/api/health/"
echo "    WebSocket:  wss://${DOMAIN}/ws"
echo ""
echo "  Vercel'da quyidagi env'larni qo'ying (keyin Redeploy):"
echo "    NEXT_PUBLIC_API_BASE_URL=https://${DOMAIN}/api"
echo "    NEXT_PUBLIC_WS_BASE_URL=wss://${DOMAIN}/ws"
echo "================================================================"
