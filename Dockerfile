# ── UZ Temiryo'l backend — production image ──────────────────────────────────
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Tizim bog'liqliklari (psycopg uchun)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Statik fayllarni yig'ish (DEBUG=False bilan)
RUN DJANGO_DEBUG=False DJANGO_SECRET_KEY=build-time python manage.py collectstatic --noinput || true

EXPOSE 8000

# Migratsiya + daphne (ASGI — HTTP + WebSocket).
# $PORT bo'lsa o'shanda tinglaydi (DigitalOcean App Platform / Render / Railway),
# aks holda 8000.
CMD ["sh", "-c", "python manage.py migrate --noinput && daphne -b 0.0.0.0 -p ${PORT:-8000} config.asgi:application"]
