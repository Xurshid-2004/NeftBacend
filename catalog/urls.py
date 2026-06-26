from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("uzellar", views.UzelViewSet, basename="uzel")
router.register("zapravkalar", views.ZapravkaViewSet, basename="zapravka")
router.register("settings", views.SettingViewSet, basename="setting")
router.register("questions", views.QuestionViewSet, basename="question")
router.register("variants", views.VariantViewSet, basename="variant")
router.register("limits", views.LimitViewSet, basename="limit")
router.register("closed-days", views.ClosedDayViewSet, basename="closed-day")
router.register("approvals", views.ApprovalViewSet, basename="approval")

urlpatterns = [
    path("", include(router.urls)),
]
