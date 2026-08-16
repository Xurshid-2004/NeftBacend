from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("access-codes", views.AccessCodeViewSet, basename="access-code")
router.register("staff", views.StaffViewSet, basename="staff")
router.register("blocked-codes", views.BlockedCodeViewSet, basename="blocked-code")
router.register("active-sessions", views.ActiveSessionViewSet, basename="active-session")
router.register("security-events", views.SecurityEventViewSet, basename="security-event")
router.register("device-locks", views.DeviceLockViewSet, basename="device-lock")

auth_patterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("face-login/", views.FaceLoginView.as_view(), name="face-login"),
    path("face-status/", views.FaceStatusView.as_view(), name="face-status"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("heartbeat/", views.HeartbeatView.as_view(), name="heartbeat"),
    path("me/", views.MeView.as_view(), name="me"),
    path("vault-check/", views.VaultCheckView.as_view(), name="vault-check"),
]

urlpatterns = [
    path("auth/", include(auth_patterns)),
    path("", include(router.urls)),
]
