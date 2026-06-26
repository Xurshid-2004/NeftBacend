"""
Vaqt yordamchilari — frontenddagi `summary-service.ts` bilan bir xil mantiq.

Submissionlar Firestore'da quyidagi "standart sana maydonlari" bilan saqlanardi:
  timestampMs, dateISO (YYYY-MM-DD), year, month, day
Bu yerda aynan o'sha qiymatlar hisoblanadi (mahalliy vaqt zonasi bo'yicha).
"""

from __future__ import annotations

import re
from datetime import datetime

from django.utils import timezone

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def now_local() -> datetime:
    """Sozlamadagi TIME_ZONE bo'yicha hozirgi mahalliy vaqt."""
    return timezone.localtime(timezone.now())


def to_local_date_iso(dt: datetime) -> str:
    """`toLocalDateISO` — YYYY-MM-DD (mahalliy)."""
    return dt.strftime("%Y-%m-%d")


def now_ms() -> int:
    return int(timezone.now().timestamp() * 1000)


def to_ms(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    return int(dt.timestamp() * 1000)


def is_valid_report_date(value: str) -> bool:
    """`isValidReportDate` — YYYY-MM-DD va haqiqiy kalendar sana."""
    if not value or not DATE_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def build_standard_date_fields(dt: datetime | None = None) -> dict:
    """`buildStandardDateFields` ekvivalenti."""
    if dt is None:
        dt = now_local()
    else:
        dt = timezone.localtime(dt) if timezone.is_aware(dt) else dt
    return {
        "timestampMs": int(dt.timestamp() * 1000),
        "dateISO": to_local_date_iso(dt),
        "year": dt.year,
        "month": dt.month,
        "day": dt.day,
    }


def build_report_datetime(date_override: str | None = None) -> datetime:
    """
    `buildReportDate` ekvivalenti: agar admin sana override bergan bo'lsa
    (YYYY-MM-DD), o'sha kunni joriy soat bilan birlashtiradi; aks holda hozir.
    """
    base = now_local()
    if date_override and is_valid_report_date(date_override):
        y, m, d = (int(x) for x in date_override.split("-"))
        return base.replace(year=y, month=m, day=d)
    return base
