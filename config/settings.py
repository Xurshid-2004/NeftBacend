"""
UZ Temiryo'l — Django backend sozlamalari.

Firestore o'rniga DRF + PostgreSQL. Barcha muhitga bog'liq qiymatlar `.env`
faylidan o'qiladi (python-dotenv). Ishlab chiqarish (production) uchun
`DJANGO_DEBUG=False` qo'ying va `DJANGO_SECRET_KEY`, `DATABASE_URL`,
`DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` ni to'ldiring.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

# ── Asosiy yo'llar ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# .env faylini yuklash (agar mavjud bo'lsa)
load_dotenv(BASE_DIR / ".env")


# ── Kichik env-yordamchilari ────────────────────────────────────────────────
def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    return env(key, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(key: str, default: str = "") -> list[str]:
    raw = env(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ── Xavfsizlik ──────────────────────────────────────────────────────────────
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    "django-insecure-*dm5)k7lf+04c0cn!^sdi(^iozqp)cadu+=c%h5aqy@=-^r#nk",
)

DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0")

# Proxy/HTTPS orqasida (Nginx, Render, Railway ...)
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

# Admin panel manzili — production'da DJANGO_ADMIN_URL bilan MAXFIY yo'lga
# o'zgartiring (masalan "boshqaruv-7x9k/"). Avtomatik botlar "/admin/" ni topa
# olmaydi. Maxfiy manzil faqat env'da bo'ladi (git'ga tushmaydi). Lokal dev'da
# standart "admin/" qoladi — hech narsa buzilmaydi.
ADMIN_URL = env("DJANGO_ADMIN_URL", "admin/").strip().lstrip("/")
if not ADMIN_URL.endswith("/"):
    ADMIN_URL += "/"


# ── Ilovalar ────────────────────────────────────────────────────────────────
DJANGO_APPS = [
    # daphne — ASGI/WebSocket uchun runserver'ni almashtiradi (eng tepada bo'lishi shart)
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "channels",
    "rest_framework",
    "corsheaders",
    "django_filters",
]

LOCAL_APPS = [
    "accounts",
    "catalog",
    "submissions",
    "reports",
    "audit",
    "realtime",
    "operators",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ── Channels (WebSocket real-time) ──────────────────────────────────────────
# Lokal/bitta-workerli: xotira (in-memory). Production ko'p-workerli: Redis.
# Redis yoqish uchun .env da REDIS_URL=redis://localhost:6379/0 bering.
_REDIS_URL = env("REDIS_URL", "")
if _REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [_REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }


# ── Ma'lumotlar bazasi ──────────────────────────────────────────────────────
# Standart: lokal ishlab chiqish uchun sqlite. Production'da DATABASE_URL ni
# PostgreSQL bilan to'ldiring, masalan:
#   DATABASE_URL=postgres://user:parol@host:5432/uztemiryol
DATABASES = {
    "default": dj_database_url.config(
        default=env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=int(env("DB_CONN_MAX_AGE", "600")),
        conn_health_checks=True,
    )
}

# SQLite (lokal dev) konkurensiya sozlamalari — "database is locked" (500) oldini oladi.
# Bir nechta foydalanuvchi bir vaqtda ishlaganda (polling + yozuv/o'chirish) SQLite
# butun faylni qulflaydi; standart "delete" journal rejimida o'qish va yozuv bir-birini
# bloklaydi va qulf navbatida timeout bo'lsa 500 chiqadi. Yechim:
#   * WAL           — o'qish yozuvni bloklamaydi (bir yozuvchi + ko'p o'quvchi parallel)
#   * IMMEDIATE     — har bir tranzaksiya yozuv qulfini boshida oladi (qulf "upgrade"
#                     deadlock'i o'rniga navbatda kutadi, busy_timeout hurmat qilinadi)
#   * timeout=20    — qulf band bo'lsa 20 soniyagacha kutadi (5s emas)
# PostgreSQL'ga (DATABASE_URL) o'tilганda bu blok umuman ishlamaydi — production'ga ta'sirsiz.
if str(DATABASES["default"].get("ENGINE", "")).endswith("sqlite3"):
    _sqlite_opts = DATABASES["default"].setdefault("OPTIONS", {})
    _sqlite_opts.setdefault("timeout", 20)
    _sqlite_opts.setdefault("transaction_mode", "IMMEDIATE")
    _sqlite_opts.setdefault(
        "init_command",
        "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON;",
    )


# ── Parol validatsiyasi (Django admin foydalanuvchilari uchun) ──────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ── Xalqarolashtirish ───────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("DJANGO_TIME_ZONE", "Asia/Tashkent")
USE_I18N = True
USE_TZ = True


# ── Statik fayllar (WhiteNoise) ─────────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ── Django REST Framework ───────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.CodeJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ]
    + (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []),
    # LimitOffsetPagination + `limit` chegarasi (common/drf.py). Javob shakli
    # o'zgarmaydi: {count, next, previous, results} — faqat juda katta `limit`
    # so'ralganda u 5000 ga tushiriladi.
    "DEFAULT_PAGINATION_CLASS": "common.pagination.CappedLimitOffsetPagination",
    "PAGE_SIZE": 100,
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S.%fZ",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Login brute-force himoyasi (kirish kodi tizimi uchun muhim)
        "login": env("THROTTLE_LOGIN", "20/min"),
        "anon": env("THROTTLE_ANON", "60/min"),
        # "Admin qo'shish" vault paroli — kod bo'yicha cheklanadi
        "vault": env("THROTTLE_VAULT", "5/min"),
        # Face ID — IP bo'yicha cheklanadi (qurilma ID sini klient o'zgartira oladi)
        "face": env("THROTTLE_FACE", "30/min"),
    },
}


# ── Face ID (yuz bo'yicha kirish) ───────────────────────────────────────────
# Butun mantiq `accounts/face.py` + `accounts/face_service.py` da, TASHQI
# KUTUBXONASIZ (numpy/opencv/dlib YO'Q) — shuning uchun serverga o'rnatishda
# hech narsa qo'shimcha talab qilinmaydi.
#
# Chegaralarni O'ZGARTIRISH KERAK BO'LMAYDI, lekin real sharoitda (yorug'lik,
# kamera sifati) sozlash uchun `.env` da quyidagilar bor:
#   FACE_ID_ENABLED=0        — Face ID ni butunlay o'chirish (parol qoladi)
#   FACE_ABS_MAX=0.45        — masofaning mutlaq "shifti" (kattaroq = yumshoqroq)
#   FACE_STRICT_ABS=0.28     — xodimlar kam bo'lganda (statistika ishlamaydi)
#   FACE_RATIO=0.82          — 2-o'rindagi nomzoddan qanchalik yaxshi bo'lishi
#   FACE_MIN_Z=2.4           — statistik ajralish (kattaroq = qattiqroq)
#   FACE_CROSS_RATIO=0.70    — admin <-> oddiy xodim ikkilanishida qattiqroq
#                              nisbat (kichrayt = yanada qattiq)
#   FACE_ENROLL_MIN_DISTANCE=0.10 — ro'yxatga olishda: yangi yuz mavjud
#                              birovnikiga shundan yaqin bo'lsa QABUL
#                              QILINMAYDI. Asosiy chalkashlik tekshiruvi
#                              bundan qat'i nazar ishlaydi (find_conflict)
# Har bir muvaffaqiyatsiz urinishning aniq raqamlari `security_events.meta`
# ga yoziladi ({"scope":"face","d":...,"z":...}) — sozlashda shundan foydalaning.
FACE_ID = {
    "ENABLED": env_bool("FACE_ID_ENABLED", True),
    "ABS_MAX": float(env("FACE_ABS_MAX", "0.45")),
    "STRICT_ABS": float(env("FACE_STRICT_ABS", "0.28")),
    "RATIO": float(env("FACE_RATIO", "0.82")),
    "MIN_Z": float(env("FACE_MIN_Z", "2.4")),
    "MIN_COHORT": int(env("FACE_MIN_COHORT", "4")),
    "MAX_SAMPLES": int(env("FACE_MAX_SAMPLES", "5")),
    # Chalkashlikka qarshi (admin <-> xodim) — `accounts/face.py` ga qarang.
    "CROSS_RATIO": float(env("FACE_CROSS_RATIO", "0.70")),
    "ENROLL_MIN_DISTANCE": float(env("FACE_ENROLL_MIN_DISTANCE", "0.10")),
    # Qurilmada ketma-ket shuncha marta tanilmasa — Face ID vaqtincha o'chadi
    # (parol bilan kirish ochiq qoladi).
    "DEVICE_FAILS": int(env("FACE_DEVICE_FAILS", "6")),
    "DEVICE_COOLDOWN_SEC": int(env("FACE_DEVICE_COOLDOWN", "300")),
    # Butun server bo'yicha daqiqasiga necha marta yuz tekshirilishi mumkin
    # (protsessorni himoya qiladi; parol bilan kirishga taalluqli emas).
    "GLOBAL_PER_MIN": int(env("FACE_GLOBAL_PER_MIN", "90")),
}


# ── "Admin qo'shish" bo'limi paroli ─────────────────────────────────────────
# Bu parol FAQAT shu yerda (serverda) turadi — frontend bundle'iga na o'zi,
# na hash'i tushadi, shu sababli uni offline brute-force qilib bo'lmaydi.
# Tekshiruv: POST /api/auth/vault-check/ (accounts.views.VaultCheckView).
#
# Production'da .env orqali qo'ying. Ikki usul bor:
#   ADMIN_VAULT_PASSWORD=...        — oddiy matn
#   ADMIN_VAULT_PASSWORD_HASH=...   — Django PBKDF2 hash (ustunroq, agar berilsa
#                                     oddiy matn e'tiborga olinmaydi). Hash olish:
#     python manage.py shell -c "from django.contrib.auth.hashers import make_password; print(make_password('yangi-parol'))"
ADMIN_VAULT_PASSWORD = env("ADMIN_VAULT_PASSWORD", "20048200")
ADMIN_VAULT_PASSWORD_HASH = env("ADMIN_VAULT_PASSWORD_HASH", "")


# ── Kod-asosli JWT (Firestore "sessiya" o'rniga) ────────────────────────────
# Login: kirish kodi -> JWT. Token muddati 12 soat (frontenddagi kabi).
AUTH_JWT = {
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_LIFETIME_HOURS": int(env("JWT_ACCESS_HOURS", "12")),
    "ISSUER": env("JWT_ISSUER", "uz-temiryol"),
    "SIGNING_KEY": env("JWT_SIGNING_KEY", SECRET_KEY),
}


# ── VAQTINCHALIK: ishchi panelidagi sana tanlagich ──────────────────────────
# Navbardagi "Hisobot sanasi" tanlagichi ishchiga ham o'tgan kunga yozuv
# kiritishga ruxsat beradi (depo oylik hisobotini sinash uchun).
#
# O'CHIRISH: `.env` ga `ALLOW_WORKER_REPORT_DATE_OVERRIDE=0` yozish kifoya —
# shundan keyin sana override yana FAQAT admin uchun ishlaydi (avvalgi holat),
# boshqa hech narsa o'zgarmaydi.
ALLOW_WORKER_REPORT_DATE_OVERRIDE = env_bool("ALLOW_WORKER_REPORT_DATE_OVERRIDE", True)


# ── CORS (Next.js frontend) ─────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)
CORS_ALLOWED_ORIGIN_REGEXES = env_list(
    "CORS_ALLOWED_ORIGIN_REGEXES",
    r"^http://localhost:\d+$,^http://127\.0\.0\.1:\d+$",
)
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", False)
CORS_ALLOW_CREDENTIALS = True


# ── Production xavfsizlik (DEBUG=False bo'lganda yoqiladi) ───────────────────
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(env("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True


# ── Doimiy xavfsizlik sarlavhalari (dev + prod) ─────────────────────────────
# Faqat HTTP javob sarlavhalari va admin sessiya cookie bayroqlari. API JSON
# javoblariga, ilova mantig'iga yoki JWT auth'ga (Authorization header orqali)
# TA'SIR QILMAYDI — Django default qiymatlarni aniq yozadi va Referrer-Policy
# sarlavhasini qo'shadi (XSS/clickjacking/referrer-leak himoyasi).
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"


# ── Loglar ──────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
}
