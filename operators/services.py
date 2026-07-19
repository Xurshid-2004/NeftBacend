"""
Operator balans xizmati — `operator-balance.ts` mantig'ining AYNAN nusxasi:
  * subtractOperatorStationFuel  -> subtract
  * setOperatorStationFuelBalance -> set_balance
  * changeOperatorStationFuelBalance -> change_balance

Har bir amal atomik (select_for_update) va o'zgarishdan keyin "operator"
topikiga real-time broadcast yuboradi.
"""

from __future__ import annotations

import uuid

from django.db import transaction

from common.numbers import js_round, parse_pdf_number
from common.timeutil import now_ms

from .models import OperatorShipment, OperatorStationBalance


def _norm(kg) -> float:
    """normalizeFuelKg: Math.round(kg*1000)/1000 (manfiyni 0 ga keltiradi)."""
    v = parse_pdf_number(kg)
    if v < 0:
        v = 0.0
    return js_round(v * 1000) / 1000


def _broadcast(station_id: str) -> None:
    try:
        from realtime.broadcast import broadcast

        broadcast({"topic": "operator", "action": "update", "stationId": station_id})
    except Exception:
        pass


def _state(bal: OperatorStationBalance, exceeded: float = 0.0) -> dict:
    return {
        "stationId": bal.stationId,
        "balanceKg": bal.balanceKg,
        "overlimitKg": bal.overlimitKg,
        "updatedAt": bal.updatedAt,
        "exceededKg": exceeded,
    }


def subtract(station_id, amount_kg, details: dict | None = None) -> dict | None:
    """Limitdan oshish endi kuzatilmaydi — balans shunchaki 0 gacha tushadi."""
    station_id = str(station_id or "").strip()
    amount = parse_pdf_number(amount_kg)
    if not station_id or amount <= 0:
        return None

    with transaction.atomic():
        bal, _ = OperatorStationBalance.objects.select_for_update().get_or_create(
            stationId=station_id
        )
        current = bal.balanceKg or 0.0
        bal.balanceKg = _norm(max(0.0, current - amount))
        bal.overlimitKg = 0.0
        bal.updatedAt = now_ms()
        bal.save()

    _broadcast(station_id)
    return _state(bal)


def set_balance(station_id, amount_kg) -> dict | None:
    station_id = str(station_id or "").strip()
    amount = parse_pdf_number(amount_kg)
    if not station_id or amount < 0:
        return None

    with transaction.atomic():
        bal, _ = OperatorStationBalance.objects.select_for_update().get_or_create(
            stationId=station_id
        )
        bal.balanceKg = _norm(amount)
        bal.overlimitKg = 0.0
        bal.updatedAt = now_ms()
        bal.save()

    _broadcast(station_id)
    return _state(bal)


def change_balance(station_id, delta_kg) -> dict | None:
    """Limitdan oshish endi kuzatilmaydi — balans shunchaki 0 gacha tushadi."""
    station_id = str(station_id or "").strip()
    delta = parse_pdf_number(delta_kg)
    if not station_id or delta == 0:
        return None

    with transaction.atomic():
        bal, _ = OperatorStationBalance.objects.select_for_update().get_or_create(
            stationId=station_id
        )
        balance = bal.balanceKg or 0.0
        bal.balanceKg = _norm(max(0.0, balance + delta))
        bal.overlimitKg = 0.0
        bal.updatedAt = now_ms()
        bal.save()

    _broadcast(station_id)
    return _state(bal)


def _broadcast_shipments() -> None:
    try:
        from realtime.broadcast import broadcast

        broadcast({"topic": "operator", "action": "shipments"})
    except Exception:
        pass


def list_shipments():
    """Barcha jo'natmalar (pending + accepted) — admin/operator paneli o'zi filtrlaydi."""
    return OperatorShipment.objects.all()


def create_shipment(data: dict) -> OperatorShipment | None:
    """Yangi (pending) jo'natma yaratadi. `id` odatda frontendda generatsiya qilinadi."""
    from_station_id = str(data.get("fromStationId") or "").strip()
    to_station_id = str(data.get("toStationId") or "").strip()
    amount = _norm(data.get("amountKg"))
    if not from_station_id or not to_station_id or amount <= 0:
        return None

    shipment_id = str(data.get("id") or uuid.uuid4()).strip() or str(uuid.uuid4())
    shipment = OperatorShipment.objects.create(
        id=shipment_id,
        fromStationId=from_station_id,
        fromStationName=data.get("fromStationName") or from_station_id,
        toStationId=to_station_id,
        toStationName=data.get("toStationName") or to_station_id,
        amountKg=amount,
        createdAt=now_ms(),
        status="pending",
    )
    _broadcast_shipments()
    return shipment


def accept_shipment(shipment_id: str, accepted_kg) -> tuple[OperatorShipment, OperatorStationBalance] | None:
    """
    Pending jo'natmani qabul qilingan deb belgilaydi VA manzil stansiya balansiga
    qabul qilingan miqdorni qo'shadi — ikkalasi bitta atomik tranzaksiyada.
    Frontend endi balansni o'zi hisoblamaydi, shu yerdan qaytgan qiymatni ko'rsatadi.
    """
    amount = _norm(accepted_kg)
    if not shipment_id or amount <= 0:
        return None

    with transaction.atomic():
        try:
            shipment = OperatorShipment.objects.select_for_update().get(
                id=shipment_id, status="pending"
            )
        except OperatorShipment.DoesNotExist:
            return None

        shipment.status = "accepted"
        shipment.acceptedAt = now_ms()
        shipment.acceptedKg = amount
        shipment.save()

        bal, _ = OperatorStationBalance.objects.select_for_update().get_or_create(
            stationId=shipment.toStationId
        )
        bal.balanceKg = _norm((bal.balanceKg or 0.0) + amount)
        bal.overlimitKg = 0.0
        bal.updatedAt = now_ms()
        bal.save()

    _broadcast_shipments()
    _broadcast(shipment.toStationId)
    return shipment, bal


def reset_all() -> None:
    """Demo/sinov uchun: barcha stansiya balanslari va jo'natmalarni butunlay tozalaydi."""
    with transaction.atomic():
        OperatorStationBalance.objects.all().delete()
        OperatorShipment.objects.all().delete()

    _broadcast_shipments()


def delete_shipment(shipment_id: str) -> bool:
    """Admin: jo'natma/farq yozuvini butunlay o'chiradi (statistika jadvalidan)."""
    if not shipment_id:
        return False

    deleted, _ = OperatorShipment.objects.filter(id=shipment_id).delete()
    if deleted:
        _broadcast_shipments()
    return bool(deleted)
