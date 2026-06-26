"""
Zapravka aniqlash (resolve) — `app/(auth)/login/page.tsx` mantig'ining nusxasi.
Xodimning `zapravka` matni (masalan "Toshkent zapravka") bo'yicha Zapravka topadi.
"""

from __future__ import annotations

import re

from .models import Zapravka
from .reference import ZAPRAVKA_KEY_ALIASES

_TRAILING_ZAPRAVKA = re.compile(r"\s*zapravka\s*$", re.IGNORECASE)
_APOSTROPHES = re.compile(r"[`'‘’ʻʼ]")
_NON_ALNUM = re.compile(r"[^a-z0-9]")


def normalize_zapravka_key(value: str) -> str:
    s = (value or "").strip().lower()
    s = _TRAILING_ZAPRAVKA.sub("", s)
    s = _APOSTROPHES.sub("", s)
    s = _NON_ALNUM.sub("", s)
    return s


def canonical_zapravka_key(value: str) -> str:
    key = normalize_zapravka_key(value)
    return ZAPRAVKA_KEY_ALIASES.get(key, key)


def resolve_zapravka(raw_zapravka: str) -> Zapravka | None:
    staff_key = canonical_zapravka_key(raw_zapravka)
    if not staff_key:
        return None
    for zap in Zapravka.objects.all():
        keys = {
            canonical_zapravka_key(zap.id),
            canonical_zapravka_key(zap.slug),
            canonical_zapravka_key(zap.name),
        }
        if staff_key in keys:
            return zap
    return None
