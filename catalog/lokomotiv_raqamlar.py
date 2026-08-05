"""
ТЯГА formasidagi «Локомотив рақами» uchun ruxsat etilgan raqamlar ro'yxati.

Manba tartibi (birinchi topilgani ishlatiladi):
  1. `settings/lokomotivRaqamlari` hujjati (Setting modeli) — admin API orqali
     o'zgartiradi. Bu ASOSIY manba.
  2. `catalog/reference.py: LOKOMOTIV_RAQAMLARI` — zaxira (fallback). Baza
     hujjati hali yaratilmagan bo'lsa yoki o'qishda xato bo'lsa ishlatiladi.

MUHIM — himoya klapani:
  Ro'yxat bo'sh bo'lsa tekshiruv BUTUNLAY O'CHIQ bo'ladi (har qanday raqam
  o'tadi). Ya'ni sozlama noto'g'ri/bo'sh qolib ketsa ham zapravkalar ishlashdan
  to'xtamaydi — yozuvlar avvalgidek saqlanaveradi.
"""

from __future__ import annotations

LOKOMOTIV_RAQAM_SETTING_KEY = "lokomotivRaqamlari"

# Setting hujjatidagi ro'yxat shu kalit ostida turadi:
#   {"raqamlar": ["003", "0847", ...]}
LOKOMOTIV_RAQAM_FIELD = "raqamlar"


def normalize_raqam(value) -> str:
    """Solishtirish uchun — faqat ortiqcha bo'shliqlar olib tashlanadi."""
    return str(value or "").strip()


def _from_setting() -> list[str] | None:
    """`settings/lokomotivRaqamlari` hujjatidagi ro'yxat (topilmasa None)."""
    from .models import Setting

    try:
        setting = Setting.objects.filter(pk=LOKOMOTIV_RAQAM_SETTING_KEY).first()
    except Exception:
        # Migratsiya qilinmagan baza va shunga o'xshash holatlarda ham
        # so'rov yiqilmasin — zaxira ro'yxatga o'tamiz.
        return None

    if not setting or not isinstance(setting.data, dict):
        return None

    raw = setting.data.get(LOKOMOTIV_RAQAM_FIELD)
    if not isinstance(raw, list):
        return None

    return [normalize_raqam(item) for item in raw if normalize_raqam(item)]


def get_allowed_raqamlar() -> list[str]:
    """Ruxsat etilgan raqamlar — baza hujjati, bo'lmasa zaxira ro'yxat."""
    from .reference import LOKOMOTIV_RAQAMLARI

    from_db = _from_setting()
    if from_db is not None:
        return from_db
    return [normalize_raqam(item) for item in LOKOMOTIV_RAQAMLARI]


def is_raqam_allowed(value) -> bool:
    """
    Kiritilgan raqam ro'yxatda bormi?

    Ro'yxat bo'sh bo'lsa har doim True (tekshiruv o'chiq — yuqoridagi izohga
    qarang). Solishtirish katta-kichik harfga sezgir emas, lekin bosh nollar
    muhim: "23" bilan "023" boshqa-boshqa raqam.
    """
    allowed = get_allowed_raqamlar()
    if not allowed:
        return True

    raqam = normalize_raqam(value)
    if not raqam:
        return False

    return raqam.casefold() in {item.casefold() for item in allowed}
