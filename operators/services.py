"""
Operator balans xizmati — `operator-balance.ts` mantig'ining AYNAN nusxasi:
  * subtractOperatorStationFuel  -> subtract
  * setOperatorStationFuelBalance -> set_balance
  * changeOperatorStationFuelBalance -> change_balance

Har bir amal atomik (select_for_update) va o'zgarishdan keyin "operator"
topikiga real-time broadcast yuboradi.
"""

from __future__ import annotations

from django.db import transaction

from common.numbers import js_round, parse_pdf_number
from common.timeutil import now_ms

from .models import OperatorOverlimit, OperatorStationBalance


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
    station_id = str(station_id or "").strip()
    amount = parse_pdf_number(amount_kg)
    if not station_id or amount <= 0:
        return None

    exceeded = 0.0
    with transaction.atomic():
        bal, _ = OperatorStationBalance.objects.select_for_update().get_or_create(
            stationId=station_id
        )
        current = bal.balanceKg or 0.0
        over = bal.overlimitKg or 0.0

        if amount <= current:
            next_balance = _norm(current - amount)
            next_over = _norm(over)
        else:
            exceeded = _norm(amount - current)
            next_balance = 0.0
            next_over = _norm(over + exceeded)

        bal.balanceKg = next_balance
        bal.overlimitKg = next_over
        bal.updatedAt = now_ms()
        bal.save()

        if exceeded > 0:
            d = details or {}
            OperatorOverlimit.objects.create(
                stationId=station_id,
                amountKg=exceeded,
                usedKg=amount,
                category=d.get("category"),
                staffCode=d.get("staffCode"),
                staffName=d.get("staffName"),
                nodeId=d.get("nodeId"),
                createdAt=now_ms(),
            )

    _broadcast(station_id)
    return _state(bal, exceeded)


def set_balance(station_id, amount_kg) -> dict | None:
    station_id = str(station_id or "").strip()
    amount = parse_pdf_number(amount_kg)
    if not station_id or amount < 0:
        return None

    with transaction.atomic():
        bal, _ = OperatorStationBalance.objects.select_for_update().get_or_create(
            stationId=station_id
        )
        over = bal.overlimitKg or 0.0
        covered = min(over, amount)
        bal.overlimitKg = _norm(over - covered)
        bal.balanceKg = _norm(amount - covered)
        bal.updatedAt = now_ms()
        bal.save()

    _broadcast(station_id)
    return _state(bal)


def change_balance(station_id, delta_kg) -> dict | None:
    station_id = str(station_id or "").strip()
    delta = parse_pdf_number(delta_kg)
    if not station_id or delta == 0:
        return None

    with transaction.atomic():
        bal, _ = OperatorStationBalance.objects.select_for_update().get_or_create(
            stationId=station_id
        )
        balance = bal.balanceKg or 0.0
        over = bal.overlimitKg or 0.0

        if delta > 0:
            covered = min(over, delta)
            next_over = _norm(over - covered)
            next_balance = _norm(balance + (delta - covered))
        else:
            spend = abs(delta)
            if spend <= balance:
                next_balance = _norm(balance - spend)
                next_over = _norm(over)
            else:
                exceeded = _norm(spend - balance)
                next_balance = 0.0
                next_over = _norm(over + exceeded)

        bal.balanceKg = next_balance
        bal.overlimitKg = next_over
        bal.updatedAt = now_ms()
        bal.save()

    _broadcast(station_id)
    return _state(bal)
