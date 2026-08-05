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


# ── Bo'lim (kategoriya) ruxsatlari ──────────────────────────────────────────
# Bu klasslar MAVJUD ruxsatlarni almashtirmaydi, ularning ustiga qo'shiladi
# (DRF `permission_classes` ro'yxatini VA mantiqi bilan tekshiradi).
#
# Ular FAQAT bo'limi cheklangan adminni to'sadi. Worker, operator, developer va
# cheklovsiz ("to'liq") admin uchun hammasi avvalgidek qoladi — `has_any_section`
# ular uchun doim True qaytaradi. Shu sababli bugungi hech bir oqim buzilmaydi.


def section_required(*needed: str, writes_only: bool = True):
    """`needed` bo'limlaridan bittasi bo'lishini talab qiladigan klass yaratadi.

    writes_only=True  — faqat yozish (POST/PATCH/DELETE) cheklanadi, o'qish ochiq.
                        Worker ham o'qiydigan endpointlar uchun (limits, staff ...).
    writes_only=False — o'qish ham cheklanadi. Butunlay bitta bo'limga tegishli
                        endpointlar uchun (blocked-codes, hisobot generatsiyasi).
    """

    from .sections import has_any_section

    class _SectionPermission(permissions.BasePermission):
        message = "Bu bo'limga ruxsatingiz yo'q."

        def has_permission(self, request, view):
            if writes_only and request.method in SAFE_METHODS:
                return True
            return has_any_section(_principal(request), needed)

    _SectionPermission.__name__ = f"SectionRequired_{'_'.join(needed)}"
    return _SectionPermission


class IsUnrestrictedAdmin(permissions.BasePermission):
    """Faqat developer yoki bo'limi cheklanmagan ("to'liq") admin.

    "Бошқарув" bo'limiga tegishli endpointlar uchun — bo'limi cheklangan admin
    o'ziga yangi huquq bera olmasligi kerak.
    """

    message = "Bu amal uchun to'liq admin huquqi kerak."

    def has_permission(self, request, view):
        from .sections import is_unrestricted_admin

        return is_unrestricted_admin(_principal(request))
