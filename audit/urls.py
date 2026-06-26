from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("audit-logs", views.AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("", include(router.urls)),
]
