from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("submissions", views.SubmissionViewSet, basename="submission")
router.register("fuel-records", views.FuelRecordViewSet, basename="fuel-record")
router.register("daily-summaries", views.DailySummaryViewSet, basename="daily-summary")
router.register("yearly-summaries", views.YearlySummaryViewSet, basename="yearly-summary")

urlpatterns = [
    path("", include(router.urls)),
]
