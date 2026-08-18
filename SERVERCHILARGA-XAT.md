# Serverchilarga yuboriladigan matn — BU FAYLNI YUBORISH MUMKIN

> Maxfiy ma'lumot yo'q: parol, kirish kodi, maxfiy kalit — hech biri.
> Quyidagi blokni to'liq nusxalab yuboring.
> Ichki (yuborilmaydigan) hujjat: `SERVER-TALABLARI.md`.

```text
Assalomu alaykum.

Python/Django'da yozilgan ichki tizimni serveringizga joylashtirmoqchimiz.
Quyidagilar kerak.

── 1. SERVER ───────────────────────────────────────────────────────────────
1.1. Ubuntu 22.04 yoki 24.04 LTS (yoki Debian 12) — bo'sh VM/LXC
1.2. 4 vCPU, 6 GB RAM (8 GB tavsiya), 40 GB disk
1.3. Vaqt zonasi: Asia/Tashkent, NTP yoqilgan
1.4. 24/7 rejim, qayta yuklangandan keyin xizmatlar avtomatik ishga tushishi

── 2. PAKETLAR ─────────────────────────────────────────────────────────────
2.1. python3.12+ (3.13 tavsiya), python3-venv, python3-pip
2.2. postgresql 14+ (16/17 tavsiya), libpq-dev
2.3. nginx
2.4. build-essential, curl, certbot, python3-certbot-nginx

── 3. SSH KIRISH ───────────────────────────────────────────────────────────
3.1. Server IP yoki hostname
3.2. SSH port
3.3. Foydalanuvchi nomi
3.4. Biz yuboradigan ochiq kalitni (.pub fayl) shu foydalanuvchining
     ~/.ssh/authorized_keys fayliga qo'shing
3.5. Shu foydalanuvchida sudo huquqi
3.6. VPN talab qilinsa — VPN konfiguratsiyasi

── 4. PAPKA VA XIZMAT ──────────────────────────────────────────────────────
4.1. /opt/uztemiryol papkasi, egasi — bizning foydalanuvchi
4.2. systemd xizmatini yaratish va boshqarish ruxsati
     (xizmat 127.0.0.1:8000 da ishlaydi, Restart=always, boot'da yoqiladi)
4.3. journalctl orqali xizmat loglarini o'qish ruxsati

── 5. MA'LUMOTLAR BAZASI ───────────────────────────────────────────────────
Quyidagilardan biri:
  (a) PostgreSQL baza + foydalanuvchi + parol yaratib bering
      (kodlash UTF-8, kirish faqat localhost'dan), ulanish satrini
      xavfsiz kanal orqali bering; yoki
  (b) sudo bering — o'zimiz yaratamiz
5.1. Disk zaxirasi: yiliga ~1 GB o'sish hisobga olinsin

── 6. TARMOQ ───────────────────────────────────────────────────────────────
6.1. Server internetdan ochiq bo'lishi shart (faqat ichki tarmoq bo'lsa —
     oldindan xabar bering)
6.2. Kiruvchi portlar ochiq: 80/TCP, 443/TCP
6.3. Chiquvchi 443/TCP ochiq: pypi.org, files.pythonhosted.org,
     letsencrypt.org
     Yopiq bo'lsa — ichki PyPI mirror manzilini bering yoki xabar qiling

── 7. DOMEN VA HTTPS (majburiy) ────────────────────────────────────────────
7.1. Subdomen: api.<sizning-domeningiz>
7.2. Uning A-yozuvi (DNS) shu server IP'siga yo'naltirilsin
7.3. TLS sertifikat: Let's Encrypt (biz o'rnatamiz) yoki sizning
     sertifikatingiz
7.4. Sertifikat avtomatik yangilanishi yoqilgan bo'lsin
7.5. Domen bo'lmasa — <server-IP>.sslip.io ishlatiladi, bizga xabar bering

── 8. NGINX ────────────────────────────────────────────────────────────────
O'zimiz sozlashimiz mumkin. Siz sozlaydigan bo'lsangiz — quyidagi
konfiguratsiya aynan shu holicha bo'lsin:

    server {
        listen 443 ssl;
        server_name api.SIZNING-DOMEN;
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

Uchta band majburiy: client_max_body_size 20M, /ws/ upgrade bloki,
X-Forwarded-Proto sarlavhasi.

── 9. KOD YETKAZISH ────────────────────────────────────────────────────────
9.1. Kod arxiv (.tar.gz) sifatida beriladi yoki SSH orqali o'zimiz
     yuklaymiz — sizdan repozitoriy yoki akkaunt talab qilinmaydi
9.2. Yangilanish: yangi arxiv + migratsiya + xizmat restart
9.3. SSH bermasangiz: arxiv + bitta skript beramiz, siz ishga tushirasiz va
     ekran chiqishini bizga yuborasiz. Docker qulay bo'lsa — Dockerfile va
     docker-compose.yml tayyor, 8000-portni nginx'ga ulash kifoya

── 10. ZAXIRA NUSXA ────────────────────────────────────────────────────────
10.1. /var/backups/ ga yozish ruxsati (kunlik pg_dump, 14 kun saqlanadi)
10.2. Serverni qayta o'rnatish, ko'chirish yoki disk tozalashdan oldin
      bizga xabar bering

── 11. IXTIYORIY ───────────────────────────────────────────────────────────
11.1. Redis (localhost:6379) — hozir shart emas

── 12. ALOQA ───────────────────────────────────────────────────────────────
12.1. Mas'ul shaxs: ism, telefon/Telegram, ish vaqti
12.2. IP almashishi, port yopilishi, texnik ishlar haqida oldindan xabar

── ANKETA — to'ldirib qaytaring ────────────────────────────────────────────
 1) Server IP / hostname:                      ......................
 2) SSH port:                                  ......................
 3) SSH foydalanuvchi nomi:                    ......................
 4) Sudo huquqi:                               ha / yo'q
 5) OS va versiyasi:                           ......................
 6) Internetdan ochiqmi:                       ha / yo'q
 7) 80 va 443 portlar ochiqmi:                 ha / yo'q
 8) Serverdan internetga chiqish (pip):        ha / yo'q / proksi: ......
 9) Subdomen bera olasizmi:                    ha: ........... / yo'q
10) TLS sertifikat:                            Let's Encrypt / sizniki
11) PostgreSQL:                                bor / yo'q
12) Redis:                                     bor / yo'q
13) VPN:                                       kerak emas / kerak
14) /var/backups/ ga yozish:                   ha / yo'q
15) Mas'ul shaxs va aloqa:                     ......................

Rahmat.
```
