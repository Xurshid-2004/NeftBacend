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
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 100,
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S.%fZ",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Login brute-force himoyasi (kirish kodi tizimi uchun muhim)
        "login": env("THROTTLE_LOGIN", "20/min"),
        "anon": env("THROTTLE_ANON", "60/min"),
    },
}


# ── Kod-asosli JWT (Firestore "sessiya" o'rniga) ────────────────────────────
# Login: kirish kodi -> JWT. Token muddati 12 soat (frontenddagi kabi).
AUTH_JWT = {
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_LIFETIME_HOURS": int(env("JWT_ACCESS_HOURS", "12")),
    "ISSUER": env("JWT_ISSUER", "uz-temiryol"),
    "SIGNING_KEY": env("JWT_SIGNING_KEY", SECRET_KEY),
}


# ── CORS (Next.js frontend) ─────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
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


# ── Loglar ──────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", "INFO")},
}
