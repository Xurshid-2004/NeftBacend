"""
`lib/utils/pdf-number.ts` -> `parsePdfNumber` ning Python ekvivalenti.

Foydalanuvchi kiritgan raqamlar vergul yoki nuqta bilan, ming ajratgich bilan
kelishi mumkin. Hisobotlar va summary'lar AYNAN shu mantiq bilan ishlaydi.
"""

from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")


def parse_pdf_number(value) -> float:
    """Har qanday kiritmani xavfsiz float'ga aylantiradi (xato bo'lsa 0.0)."""
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value) if _finite(value) else 0.0

    raw = _WS_RE.sub("", str(value).strip())
    if not raw:
        return 0.0

    normalized = _normalize(raw)
    try:
        parsed = float(normalized)
    except (TypeError, ValueError):
        return 0.0
    return parsed if _finite(parsed) else 0.0


def _finite(n) -> bool:
    try:
        f = float(n)
    except (TypeError, ValueError):
        return False
    return f == f and f not in (float("inf"), float("-inf"))


def _normalize(raw: str) -> str:
    """Vergul/nuqta aralash kiritmani standart o'nlik nuqtaga keltiradi."""
    has_comma = "," in raw
    has_dot = "." in raw

    if has_comma and has_dot:
        # Oxirgi keladigani — o'nlik ajratgich
        if raw.rfind(",") > raw.rfind("."):
            return raw.replace(".", "").replace(",", ".")
        return raw.replace(",", "")
    if has_comma:
        # Faqat vergul — o'nlik sifatida qaraladi (ming ajratgich emas)
        return raw.replace(",", ".")
    return raw


def js_round(value: float) -> float:
    """JS `Math.round` — yarmini har doim +cheksizlik tomon yaxlitlaydi."""
    import math

    return math.floor(value + 0.5)


def round2(value: float) -> float:
    """`Math.round(x * 100) / 100` ekvivalenti (JS bilan bir xil)."""
    return js_round(value * 100) / 100
