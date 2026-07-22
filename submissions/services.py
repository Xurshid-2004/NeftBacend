"""
Submission yozish/yangilash/o'chirish xizmati — frontend mantig'ining AYNAN nusxasi:
  * addSubmission / addLokomotivSubmission   (submissions-service.ts, lokomotiv-service.ts)
  * summary deltalar                          (summary-service.ts)
  * fuelRecords yozish                        (fuel-record-writer.ts, lokomotiv-service.ts)
  * updateSubmissionWithSummary / delete      (submission-mutations.ts)
"""

from __future__ import annotations

import re

from django.db import transaction
from django.db.models import F

from catalog.models import Zapravka
from common.numbers import parse_pdf_number
from common.timeutil import (
    build_report_datetime,
    build_standard_date_fields,
    now_ms,
    to_local_date_iso,
)

from .models import DailySummary, FuelRecord, Submission, YearlySummary

# Submission'da ustun bo'lgan maydonlar (qolganlari `extra` ga tushadi)
_MODEL_FIELDS = {f.name for f in Submission._meta.get_fields() if hasattr(f, "attname")}
_STD_DATE_KEYS = {"timestampMs", "dateISO", "year", "month", "day"}

_FLOAT_FIELDS = {
    f.name for f in Submission._meta.get_fields()
    if f.get_internal_type() == "FloatField"
}
_INT_FIELDS = {
    f.name for f in Submission._meta.get_fields()
    if f.get_internal_type() in ("IntegerField", "BigIntegerField")
}


def _coerce_types(known: dict) -> dict:
    """Klient string ("12,5") yuborsa ham raqamli ustunlarga to'g'ri yozish."""
    for key, value in list(known.items()):
        if value is None or isinstance(value, bool):
            continue
        if key in _FLOAT_FIELDS and isinstance(value, str):
            known[key] = parse_pdf_number(value)
        elif key in _INT_FIELDS and isinstance(value, str):
            known[key] = int(parse_pdf_number(value))
    return known


# ── Yoqilg'i miqdori (summary-service.ts) ───────────────────────────────────
def fuel_kg_for_submission(data: dict) -> float:
    cat = data.get("category")
    if cat == "korxona":
        raw = data.get("qancha")
    elif cat == "qurulish":
        raw = data.get("qanchaOlindi")
    else:
        raw = data.get("qanchaBerildi")
    return parse_pdf_number(raw if raw is not None else 0)


def masla_kg_for_submission(data: dict) -> float:
    return parse_pdf_number(data.get("dizMasla") if data.get("dizMasla") is not None else 0)


def _clean_doc_id(value: str) -> str:
    value = re.sub(r"[\/\s]+", "_", value)
    return re.sub(r"_+", "_", value)


def _summary_parts(data: dict):
    station_id = str(data.get("stationId") or "").strip()
    category = str(data.get("category") or "").strip()
    if not station_id or not category:
        return None
    date_iso = data.get("dateISO")
    if not (isinstance(date_iso, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", date_iso)):
        fields = build_standard_date_fields()
        date_iso = fields["dateISO"]
        year = fields["year"]
    else:
        year = data.get("year")
        if not isinstance(year, int):
            year = int(date_iso[:4])
    node_id = None if data.get("nodeId") is None else str(data.get("nodeId"))
    return {
        "stationId": station_id,
        "nodeId": node_id,
        "category": category,
        "dateISO": date_iso,
        "year": year,
    }


def _same_bucket(a, b) -> bool:
    return (
        a is not None
        and b is not None
        and a["stationId"] == b["stationId"]
        and a["category"] == b["category"]
        and a["dateISO"] == b["dateISO"]
    )


def _has_standard_marker(data: dict) -> bool:
    date_iso = data.get("dateISO")
    return (
        isinstance(date_iso, str)
        and re.match(r"^\d{4}-\d{2}-\d{2}$", date_iso) is not None
        and isinstance(data.get("timestampMs"), int)
    )


def _apply_summary_delta(data: dict, direction: int, count_delta: int) -> None:
    parts = _summary_parts(data)
    if not parts:
        return

    fuel_delta = fuel_kg_for_submission(data) * direction
    masla_delta = masla_kg_for_submission(data) * direction
    daily_id = _clean_doc_id(f'{parts["dateISO"]}_{parts["stationId"]}_{parts["category"]}')
    yearly_id = _clean_doc_id(f'{parts["year"]}_{parts["stationId"]}_{parts["category"]}')
    ts = now_ms()

    with transaction.atomic():
        daily, created = DailySummary.objects.select_for_update().get_or_create(
            docId=daily_id,
            defaults={
                "stationId": parts["stationId"],
                "nodeId": parts["nodeId"],
                "category": parts["category"],
                "dateISO": parts["dateISO"],
                "year": parts["year"],
                "totalFuelKg": fuel_delta,
                "totalMaslaKg": masla_delta,
                "recordCount": count_delta,
                "updatedAt": ts,
            },
        )
        if not created:
            DailySummary.objects.filter(docId=daily_id).update(
                totalFuelKg=F("totalFuelKg") + fuel_delta,
                totalMaslaKg=F("totalMaslaKg") + masla_delta,
                recordCount=F("recordCount") + count_delta,
                nodeId=parts["nodeId"],
                updatedAt=ts,
            )

        yearly, created = YearlySummary.objects.select_for_update().get_or_create(
            docId=yearly_id,
            defaults={
                "stationId": parts["stationId"],
                "nodeId": parts["nodeId"],
                "category": parts["category"],
                "year": parts["year"],
                "totalFuelKg": fuel_delta,
                "totalMaslaKg": masla_delta,
                "recordCount": count_delta,
                "updatedAt": ts,
            },
        )
        if not created:
            YearlySummary.objects.filter(docId=yearly_id).update(
                totalFuelKg=F("totalFuelKg") + fuel_delta,
                totalMaslaKg=F("totalMaslaKg") + masla_delta,
                recordCount=F("recordCount") + count_delta,
                nodeId=parts["nodeId"],
                updatedAt=ts,
            )


# ── fuelRecords yozish ──────────────────────────────────────────────────────
def _supply_point(station_id: str) -> str:
    zap = Zapravka.objects.filter(pk=station_id).first()
    return zap.name if zap else station_id


def _normalize_entered_time(raw) -> str:
    """Formadagi qo'lda kiritilgan soat ("HH:mm"); noto'g'ri bo'lsa "" qaytadi."""
    text = str(raw or "").strip()
    match = re.match(r"^(\d{1,2})[:.](\d{1,2})", text)
    if not match:
        return ""
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        return ""
    return f"{hours:02d}:{minutes:02d}"


def _write_fuel_record_lokomotiv(data: dict, now) -> None:
    """lokomotiv-service.ts -> addFuelRecord ekvivalenti."""
    date_iso = data.get("dateISO")
    date = date_iso if isinstance(date_iso, str) else to_local_date_iso(now)
    # Ishchi formada kiritgan soat ustuvor, bo'lmasa — yozuv vaqti.
    time = _normalize_entered_time(data.get("enteredTime")) or f"{now.hour:02d}:{now.minute:02d}"

    harakat = data.get("harakatTuri")
    if harakat == "manyovr":
        loco_number = data.get("stansiya") or ""
    elif harakat == "xojalik":
        loco_number = data.get("tashkilot") or ""
    else:
        loco_number = data.get("poyezdNumber") or ""

    FuelRecord.objects.create(
        date=date,
        dateISO=date,
        year=int(date[:4]),
        time=time,
        supplyPoint=_supply_point(data["stationId"]),
        staffCode=data.get("staffCode") or "",
        staffName=data.get("staffName") or "",
        locCode=data["stationId"],
        locoSeries=data.get("rusumi") or "",
        locoCode=data.get("lokomotivNumber") or "",
        jadval="",
        zagranitsa="",
        zagranitsaAmount="",
        moveType=data.get("harakatTuri") or "",
        locoNumber=loco_number,
        trainIndex=data.get("ruxsatIndeksi") or "",
        ruxsatIndeksi=data.get("ruxsatIndeksi") or "",
        weight="" if data.get("poyezdVazni") is None else str(data.get("poyezdVazni")),
        balanceBefore=str(data.get("qoldiq")),
        fuelAmount=str(data.get("qanchaBerildi")),
        maslaAmount=str(data.get("dizMasla")),
        stansiya=data.get("stansiya") or "",
        tashkilot=data.get("tashkilot") or "",
        ijarachi=data.get("ijarachi") or "",
        mashinadaYetkazildi=bool(data.get("mashinadaYetkazildi") or False),
        mashinaRaqami=data.get("mashinaRaqami") or "",
        route="",
        trainCode="",
        trainNumber="",
    )


def _append_fuel_record_erju(move_type: str, base: dict, now) -> None:
    """fuel-record-writer.ts -> appendFuelRecordForErjuJu ekvivalenti."""
    fuel_amount = parse_pdf_number(base.get("fuelAmountKg"))
    balance_before = parse_pdf_number(base.get("balanceBeforeKg"))
    dizmasla = 0.0 if base.get("dizMaslaKg") is None else parse_pdf_number(base.get("dizMaslaKg"))
    if fuel_amount <= 0:
        return

    date = base.get("dateISO") or to_local_date_iso(now)
    time = (
        _normalize_entered_time(base.get("enteredTime"))
        or base.get("time")
        or f"{now.hour:02d}:{now.minute:02d}"
    )

    FuelRecord.objects.create(
        date=date,
        dateISO=date,
        year=int(date[:4]),
        time=time,
        supplyPoint=_supply_point(base["stationId"]),
        staffCode=base.get("staffCode") or "",
        staffName=base.get("staffName") or "",
        locCode=base["stationId"],
        moveType=move_type,
        locoSeries=base.get("locoSeries") or "",
        locoCode=base.get("locoCode") or "",
        locoNumber=base.get("locoNumber") or "",
        trainIndex=base.get("trainIndex") or "",
        route="",
        trainCode="",
        trainNumber="",
        weight=base.get("weight") or "",
        balanceBefore=""
        if base.get("balanceBeforeKg") is None or balance_before == 0
        else str(balance_before),
        fuelAmount=str(fuel_amount),
        maslaAmount=str(dizmasla)
        if base.get("dizMaslaKg") is not None and dizmasla != 0
        else "",
    )


def _write_fuel_record(data: dict, now) -> None:
    """Formalardagi appendFuelRecordForErjuJu chaqiruvlarini takrorlaydi."""
    cat = data.get("category")
    try:
        if cat == "lokomotiv":
            _write_fuel_record_lokomotiv(data, now)
        elif cat == "korxona":
            _append_fuel_record_erju(
                "korxona",
                {
                    "stationId": data["stationId"],
                    "staffCode": data.get("staffCode"),
                    "staffName": data.get("staffName"),
                    "enteredTime": data.get("enteredTime"),
                    "locoNumber": data.get("poyezdNumber"),
                    "fuelAmountKg": data.get("qancha"),
                    "trainIndex": data.get("ruxsatIndeksi"),
                },
                now,
            )
        elif cat == "qurulish":
            _append_fuel_record_erju(
                "qurulish",
                {
                    "stationId": data["stationId"],
                    "staffCode": data.get("staffCode"),
                    "staffName": data.get("staffName"),
                    "enteredTime": data.get("enteredTime"),
                    "locoSeries": data.get("seriya"),
                    "locoCode": data.get("raqami"),
                    "fuelAmountKg": data.get("qanchaBerildi"),
                    "balanceBeforeKg": data.get("qoldiq"),
                    "trainIndex": data.get("ruxsatIndeksi"),
                    "weight": str(data.get("poyezdVazni")),
                },
                now,
            )
        elif cat == "tamirlash":
            _append_fuel_record_erju(
                "tamirlash",
                {
                    "stationId": data["stationId"],
                    "staffCode": data.get("staffCode"),
                    "staffName": data.get("staffName"),
                    "enteredTime": data.get("enteredTime"),
                    "fuelAmountKg": data.get("qanchaBerildi"),
                    "dizMaslaKg": data.get("dizMasla"),
                    "locoSeries": data.get("seriya"),
                    "locoCode": str(data.get("raqami")),
                    "trainIndex": f'{data.get("tamirlashTuri")} · {data.get("masulShaxs")}',
                },
                now,
            )
    except Exception as exc:  # noqa: BLE001 — fuelRecord xatosi submissionni buzmasin
        import logging

        logging.getLogger(__name__).warning("fuelRecord yozilmadi: %s", exc)


# ── Asosiy CRUD ─────────────────────────────────────────────────────────────
def _split_extra(data: dict) -> tuple[dict, dict]:
    known, extra = {}, {}
    for k, v in data.items():
        if k in _MODEL_FIELDS:
            known[k] = v
        elif k not in ("id", "category"):
            extra[k] = v
    return known, extra


def create_submission(category: str, data: dict, report_date_override: str | None = None) -> Submission:
    """addSubmission + summary + fuelRecord (frontend bilan bir xil tartib)."""
    now = build_report_datetime(report_date_override)
    std = build_standard_date_fields(now)
    created_ms = std["timestampMs"]

    payload = dict(data)
    payload["category"] = category
    payload.update(std)
    payload["timestamp"] = created_ms
    payload["createdAt"] = created_ms

    known, extra = _split_extra(payload)
    _coerce_types(known)
    if extra:
        known["extra"] = extra

    sub = Submission.objects.create(**known)

    delta_data = {**data, "category": category, **std}
    _apply_summary_delta(delta_data, 1, 1)
    _write_fuel_record(delta_data, now)
    _broadcast(sub, "create")
    return sub


def _broadcast(sub: Submission, action: str) -> None:
    """WebSocket orqali real-time xabar (xato bo'lsa jim o'tadi)."""
    try:
        from realtime.broadcast import broadcast_submission

        broadcast_submission(
            action,
            station_id=sub.stationId,
            category=sub.category,
            submission_id=sub.pk,
        )
    except Exception:
        pass


def _submission_to_dict(sub: Submission) -> dict:
    out = {f: getattr(sub, f) for f in _MODEL_FIELDS}
    if isinstance(sub.extra, dict):
        out.update(sub.extra)
    return out


def update_submission(sub: Submission, changes: dict) -> Submission:
    """submission-mutations.ts -> updateSubmissionWithSummary ekvivalenti."""
    before = _submission_to_dict(sub)

    # missingDatePatch — standart sana maydonlari yo'q bo'lsa to'ldirish
    fields = build_standard_date_fields()
    patch: dict = {}
    if not isinstance(before.get("dateISO"), str):
        patch["dateISO"] = fields["dateISO"]
    if not isinstance(before.get("timestampMs"), int):
        patch["timestampMs"] = fields["timestampMs"]
    if not isinstance(before.get("year"), int):
        patch["year"] = fields["year"]
    if not isinstance(before.get("month"), int):
        patch["month"] = fields["month"]
    if not isinstance(before.get("day"), int):
        patch["day"] = fields["day"]
    patch.update(changes)

    known, extra = _split_extra(patch)
    _coerce_types(known)
    for k, v in known.items():
        setattr(sub, k, v)
    if extra:
        merged = dict(sub.extra or {})
        merged.update(extra)
        sub.extra = merged
    sub.save()

    after = _submission_to_dict(sub)
    _record_updated_for_summaries(before, after)
    _broadcast(sub, "update")
    return sub


def _record_updated_for_summaries(before: dict, after: dict) -> None:
    if not _has_standard_marker(before):
        _apply_summary_delta(after, 1, 1)
        return

    bparts = _summary_parts(before)
    aparts = _summary_parts(after)
    if _same_bucket(bparts, aparts):
        fuel_delta = fuel_kg_for_submission(after) - fuel_kg_for_submission(before)
        masla_delta = masla_kg_for_submission(after) - masla_kg_for_submission(before)
        cat = after.get("category")
        delta_doc = {
            **after,
            "qanchaBerildi": fuel_delta if cat in ("lokomotiv", "tamirlash") else None,
            "qancha": fuel_delta if cat == "korxona" else None,
            "qanchaOlindi": fuel_delta if cat == "qurulish" else None,
            "dizMasla": masla_delta,
        }
        _apply_summary_delta(delta_doc, 1, 0)
        return

    _apply_summary_delta(before, -1, -1)
    _apply_summary_delta(after, 1, 1)


def delete_submission(sub: Submission) -> None:
    """submission-mutations.ts -> deleteSubmissionWithSummary ekvivalenti."""
    data = _submission_to_dict(sub)
    station_id, category, pk = sub.stationId, sub.category, sub.pk
    # Atomik: yozuvni o'chirish va summaryни kamaytirish birga bajariladi. Aks holda
    # (qulf/xato yuz bersa) yozuv o'chib, summary kamaymay qolib, hisobot chalkasharди.
    with transaction.atomic():
        sub.delete()
        if _has_standard_marker(data):
            _apply_summary_delta(data, -1, -1)
    try:
        from realtime.broadcast import broadcast_submission

        broadcast_submission("delete", station_id=station_id, category=category, submission_id=pk)
    except Exception:
        pass
