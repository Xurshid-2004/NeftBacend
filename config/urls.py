"""
URL konfiguratsiyasi.

Barcha REST endpointlar `/api/` ostida:
  /api/auth/login/        — kirish kodi -> JWT
  /api/auth/me/           — joriy sessiya
  /api/access-codes/      — kirish kodlari (admin)
  /api/staff/             — xodimlar
  /api/uzellar/ /zapravkalar/ /settings/ /questions/ /variants/ /limits/
  /api/submissions/       — submissionlar (worker o'z stansiyasi)
  /api/daily-summaries/ /yearly-summaries/ /fuel-records/
  /api/reports/generate/  — hisobot
  /api/audit-logs/        — audit izi
"""

from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(_request):
    return JsonResponse({"status": "ok", "service": "uz-temiryol-backend"})


urlpatterns = [
    path("", health, name="root"),  # App Platform health check uchun
    path(settings.ADMIN_URL, admin.site.urls),  # maxfiy manzil: DJANGO_ADMIN_URL
    path("api/health/", health, name="health"),
    path("api/", include("accounts.urls")),
    path("api/", include("catalog.urls")),
    path("api/", include("submissions.urls")),
    path("api/", include("reports.urls")),
    path("api/", include("audit.urls")),
    path("api/", include("operators.urls")),
]
