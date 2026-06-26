"""
Rolga asoslangan ruxsatlar — Firestore qoidalari (firestore.rules) ekvivalenti.

Rollar: worker, admin, developer.
  * admin/developer — to'liq boshqaruv (kodlar, limitlar, sozlamalar, hisobotlar)
  * worker — faqat o'z stansiyasi (stationId) submissionlari
"""

from rest_framework import permissions

SAFE_METHODS = permissions.SAFE_METHODS


def _principal(request):
    return getattr(request, "user", None)


class IsAuthenticated(permissions.BasePermission):
    def has_permission(self, request, view):
        p = _principal(request)
        return bool(p and getattr(p, "is_authenticated", False))


class IsAdmin(permissions.BasePermission):
    """admin yoki developer."""

    def has_permission(self, request, view):
        p = _principal(request)
        return bool(p and getattr(p, "is_admin", False))


class IsDeveloper(permissions.BasePermission):
    def has_permission(self, request, view):
        p = _principal(request)
        return bool(p and getattr(p, "is_developer", False))


class IsAdminOrReadOnly(permissions.BasePermission):
    """Hamma o'qiy oladi; faqat admin/developer yoza oladi."""

    def has_permission(self, request, view):
        p = _principal(request)
        if not (p and getattr(p, "is_authenticated", False)):
            return False
        if request.method in SAFE_METHODS:
            return True
        return getattr(p, "is_admin", False)
