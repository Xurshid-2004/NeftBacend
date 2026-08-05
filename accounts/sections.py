"""
Admin panel bo'limlari (kategoriyalar) — ruxsatlarning yagona manbasi.

Frontenddagi nusxasi: `lib/data/admin-sections.ts`. Ikkalasi bir xil kalitlarni
ishlatadi; kalit o'zgarsa IKKALASINI ham yangilash kerak.

Muhim qoida — ORQAGA MOSLIK:
    `AccessCode.allowedSections` BO'SH yoki NULL bo'lsa, bu "cheklov yo'q"
    degani, ya'ni admin hamma bo'limga kiradi. Shu sababli bu funksiya
    qo'shilishidan oldin yaratilgan barcha kodlar avvalgidek ishlayveradi.

"boshqaruv" ataylab ro'yxatga kiritilmagan: o'sha bo'lim orqali yangi admin
yaratiladi, ya'ni uni biriktirish cheklovning o'zini ma'nosiz qilardi. Unga
faqat developer va cheklovsiz ("to'liq") admin kiradi.
"""

from __future__ import annotations

# Biriktirish mumkin bo'lgan bo'limlar.
ASSIGNABLE_SECTIONS = (
    "statistika",
    "hisobotlar",
    "xodim",
    "operator",
    "limit",
)


def normalize_sections(value) -> list[str] | None:
    """Kiruvchi qiymatni tozalaydi: faqat ma'lum kalitlar, takrorsiz, tartibli.

    Bo'sh natija `None` ga aylanadi — ya'ni "cheklov yo'q".
    """
    if not value:
        return None
    if not isinstance(value, (list, tuple, set)):
        return None
    known = [s for s in ASSIGNABLE_SECTIONS if s in {str(v).strip() for v in value}]
    return known or None


def sections_for(principal) -> set[str] | None:
    """Foydalanuvchining ruxsat etilgan bo'limlari.

    `None` qaytsa — cheklov yo'q (developer, worker/operator yoki to'liq admin).
    """
    if principal is None or not getattr(principal, "is_authenticated", False):
        return None
    # Developer hech qachon cheklanmaydi.
    if getattr(principal, "is_developer", False):
        return None
    # Cheklov faqat adminlarga tegishli — worker/operator oqimiga tegilmaydi.
    if not getattr(principal, "is_admin", False):
        return None

    from .models import AccessCode

    row = AccessCode.objects.filter(pk=getattr(principal, "code", "")).only(
        "allowedSections"
    ).first()
    if row is None:
        return None
    return set(normalize_sections(row.allowedSections) or []) or None


def has_any_section(principal, needed) -> bool:
    """Foydalanuvchida `needed` bo'limlaridan hech bo'lmasa bittasi bormi?"""
    allowed = sections_for(principal)
    if allowed is None:
        return True
    return bool(allowed & set(needed))


def is_unrestricted_admin(principal) -> bool:
    """Cheklovsiz admin yoki developer (masalan "Бошқарув" bo'limi uchun)."""
    if getattr(principal, "is_developer", False):
        return True
    if not getattr(principal, "is_admin", False):
        return False
    return sections_for(principal) is None
