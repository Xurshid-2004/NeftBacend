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

from .models import (
    OperatorCentralPurchase,
    OperatorCentralTank,
    OperatorShipment,
    OperatorShipmentRequest,
    OperatorStationBalance,
)


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


def write_audit(
    actor: dict | None,
    action: str,
    entity_type: str,
    entity_id,
    changes: dict | None = None,
) -> None:
    """Operator bo'limidagi amalning o'zgarmas izi: kim, qachon, nima qildi.

    `AuditLog` jadvaliga yoziladi (Django admin panelida ko'rinadi:
    "Audit logs" -> entityType bo'yicha filtr). Ilgari bu jadvalga FAQAT brauzer
    yozardi, ya'ni yoqilg'i harakatlarining server tomonda hech qanday izi
    qolmasdi — nizo chiqsa "kim yubordi" degan savolga javob yo'q edi.

    ATAYLAB shunday:
      * amal MUVAFFAQIYATLI tugagandan KEYIN chaqiriladi,
      * tranzaksiyadan TASHQARIDA (audit yozuvi yoqilg'i harakatini qaytarib
        yubormasin),
      * xatosi yutiladi — iz muhim, lekin hisob-kitobdan muhimroq emas.
    """
    try:
        from audit.models import AuditLog

        data = actor or {}
        AuditLog.objects.create(
            userId=str(data.get("userId") or "")[:64],
            userName=str(data.get("userName") or "")[:200],
            userRole=str(data.get("userRole") or "")[:16],
            action=action,
            entityType=str(entity_type)[:64],
            entityId=str(entity_id or "")[:160],
            changes=changes or {},
            timestamp=now_ms(),
        )
    except Exception:  # noqa: BLE001 — audit xatosi asosiy amalni buzmasin
        import logging

        logging.getLogger(__name__).warning(
            "operator audit izi yozilmadi (%s %s)", action, entity_type, exc_info=True
        )


def _broadcast_shipments() -> None:
    try:
        from realtime.broadcast import broadcast

        broadcast({"topic": "operator", "action": "shipments"})
    except Exception:
        pass


def list_shipments(station_id: str | None = None):
    """Jo'natmalar (pending + accepted).

    `station_id` berilsa — faqat SHU zapravkaning oldi-berdisi: unga kelgan
    (`toStationId`) yoki undan yuborilgan (`fromStationId`) jo'natmalar. Admin
    bo'lmagan foydalanuvchi uchun view aynan shuni beradi, shunda boshqa
    zapravkalarning oldi-berdisi brauzerga umuman yetib bormaydi (avval butun
    ro'yxat hammaga qaytardi va filtrlash faqat frontendda edi).

    `None` — cheklovsiz (admin/developer paneli: barcha zapravkalar kesimi kerak).
    """
    from django.db.models import Q

    qs = OperatorShipment.objects.all()
    if station_id is not None:
        qs = qs.filter(Q(fromStationId=station_id) | Q(toStationId=station_id))
    return qs


def send_station_shipment(data: dict) -> dict:
    """Zapravkadan zapravkaga dizel jo'natish: JO'NATUVCHI balansidan ayirish +
    pending jo'natma yaratish BITTA atomik amalda.

    Ilgari ayirishni frontend alohida `/operator/change/` so'rovi bilan qilardi.
    U so'rov faqat admin/operatorga ochiq edi, shuning uchun "переход расход"
    orqali kirgan worker yuborganda 403 qaytardi: balans faqat brauzerda
    kamayib, keyingi poll serverdagi eski (kamaymagan) qiymatni qaytarardi —
    ya'ni balans "bir kamayib, yana to'lib qolardi". Endi ayirish ham, jo'natma
    ham shu yerda, serverda bajariladi.

    Balansda yetarli yoqilg'i bo'lmasa — RAD etadi (hech narsa o'zgarmaydi), shu
    tarzda ikki kishi bir vaqtda yuborsa ham balans manfiyga tushmaydi.

    Idempotent: shu `id` bilan jo'natma allaqachon bo'lsa, qayta ayirmaydi.

    Qaytaradi:
      {"ok": True,  "shipment": <OperatorShipment>, "balance": <OperatorStationBalance>}
      {"ok": False, "reason": "invalid"}
      {"ok": False, "reason": "insufficient", "available": <kg>}
    """
    from_station_id = str(data.get("fromStationId") or "").strip()
    to_station_id = str(data.get("toStationId") or "").strip()
    amount = _norm(data.get("amountKg"))
    if (
        not from_station_id
        or not to_station_id
        or from_station_id == to_station_id
        or amount <= 0
    ):
        return {"ok": False, "reason": "invalid"}

    shipment_id = str(data.get("id") or uuid.uuid4()).strip() or str(uuid.uuid4())

    with transaction.atomic():
        bal, _ = OperatorStationBalance.objects.select_for_update().get_or_create(
            stationId=from_station_id
        )

        existing = OperatorShipment.objects.filter(id=shipment_id).first()
        if existing is not None:
            # Idempotentlik: allaqachon yaratilgan, qayta ayirmaymiz.
            return {"ok": True, "shipment": existing, "balance": bal}

        available = bal.balanceKg or 0.0
        # Kichik epsilon — suzuvchi nuqta yaxlitlash chekkasi uchun.
        if amount > available + 1e-9:
            return {"ok": False, "reason": "insufficient", "available": _norm(available)}

        bal.balanceKg = _norm(max(0.0, available - amount))
        bal.overlimitKg = 0.0
        bal.updatedAt = now_ms()
        bal.save()

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
    _broadcast(from_station_id)
    return {"ok": True, "shipment": shipment, "balance": bal}


# ── Yuborishga RUXSAT SO'ROVI ───────────────────────────────────────────────
# Ishchi/operator endi bevosita jo'nata olmaydi: avval so'rov qoldiradi, admin
# ruxsat berganidan keyingina haqiqiy jo'natma yaratiladi va balansdan ayiriladi.


def _broadcast_requests() -> None:
    try:
        from realtime.broadcast import broadcast

        broadcast({"topic": "operator", "action": "shipment-requests"})
    except Exception:
        pass


def list_shipment_requests(station_id: str | None = None):
    """So'rovlar ro'yxati. `station_id` berilsa — faqat shu zapravkanikilari."""
    from django.db.models import Q

    qs = OperatorShipmentRequest.objects.all()
    if station_id is not None:
        qs = qs.filter(Q(fromStationId=station_id) | Q(toStationId=station_id))
    return qs


def create_shipment_request(data: dict) -> OperatorShipmentRequest | None:
    """Yangi (pending) ruxsat so'rovi. BALANSGA TEGMAYDI — faqat yozib qo'yadi."""
    from_station_id = str(data.get("fromStationId") or "").strip()
    to_station_id = str(data.get("toStationId") or "").strip()
    amount = _norm(data.get("amountKg"))
    if (
        not from_station_id
        or not to_station_id
        or from_station_id == to_station_id
        or amount <= 0
    ):
        return None

    request_id = str(data.get("id") or uuid.uuid4()).strip() or str(uuid.uuid4())

    # Idempotent: bir xil id bilan takroriy so'rov dublikat yaratmaydi.
    existing = OperatorShipmentRequest.objects.filter(id=request_id).first()
    if existing is not None:
        return existing

    req = OperatorShipmentRequest.objects.create(
        id=request_id,
        fromStationId=from_station_id,
        fromStationName=str(data.get("fromStationName") or from_station_id)[:200],
        toStationId=to_station_id,
        toStationName=str(data.get("toStationName") or to_station_id)[:200],
        amountKg=amount,
        masulShaxs=str(data.get("masulShaxs") or "")[:200],
        requestedByCode=str(data.get("requestedByCode") or "")[:64],
        requestedByName=str(data.get("requestedByName") or "")[:200],
        createdAt=now_ms(),
        status="pending",
    )
    _broadcast_requests()
    return req


def approve_shipment_request(request_id: str, decided_by: dict | None = None) -> dict:
    """Admin ruxsat berdi: so'rov tasdiqlanadi + haqiqiy jo'natma yaratiladi +
    jo'natuvchi balansidan ayiriladi — hammasi BITTA atomik amalda.

    Balansda yetarli yoqilg'i bo'lmasa RAD etiladi va so'rov "pending" holicha
    qoladi (keyinroq yoqilg'i kelganda qayta tasdiqlash mumkin).

    Qaytaradi:
      {"ok": True,  "request": ..., "shipment": ..., "balance": ...}
      {"ok": False, "reason": "notfound"}
      {"ok": False, "reason": "insufficient", "available": <kg>}
      {"ok": False, "reason": "invalid"}
    """
    who = decided_by or {}

    with transaction.atomic():
        try:
            req = OperatorShipmentRequest.objects.select_for_update().get(
                id=request_id, status="pending"
            )
        except OperatorShipmentRequest.DoesNotExist:
            return {"ok": False, "reason": "notfound"}

        # Jo'natma id si so'rovdan kelib chiqadi — ikki marta tasdiqlashga
        # urinilsa ham ikkinchi jo'natma yaratilmaydi (idempotentlik).
        shipment_id = f"req-{req.id}"[:64]
        result = send_station_shipment(
            {
                "id": shipment_id,
                "fromStationId": req.fromStationId,
                "fromStationName": req.fromStationName,
                "toStationId": req.toStationId,
                "toStationName": req.toStationName,
                "amountKg": req.amountKg,
            }
        )
        if not result.get("ok"):
            # Balans yetmadi yoki ma'lumot noto'g'ri — so'rov o'zgarishsiz qoladi.
            return result

        req.status = "approved"
        req.decidedAt = now_ms()
        req.decidedByCode = str(who.get("code") or "")[:64]
        req.decidedByName = str(who.get("name") or "")[:200]
        req.shipmentId = shipment_id
        req.save()

    _broadcast_requests()
    return {
        "ok": True,
        "request": req,
        "shipment": result["shipment"],
        "balance": result["balance"],
    }


def allow_shipment_request(
    request_id: str, allowed_kg, decided_by: dict | None = None
) -> OperatorShipmentRequest | str | None:
    """Admin «Бошқа қиймат»: so'ralganidan boshqa (odatda kamroq) miqdorga ruxsat.

    Jo'natma HOZIR yaratilmaydi va balansga tegilmaydi — ishchiga faqat "shuncha
    kg gacha ruxsat" beriladi. Ishchi tayyor bo'lganda o'zi jo'natadi
    (`send_allowed_shipment`), lekin shu chegaradan ORTIQ yubora olmaydi.

    Qaytaradi: yangilangan so'rov | "invalid" | None (topilmadi).
    """
    who = decided_by or {}
    amount = _norm(allowed_kg)
    if amount <= 0:
        return "invalid"

    with transaction.atomic():
        try:
            req = OperatorShipmentRequest.objects.select_for_update().get(
                id=request_id, status="pending"
            )
        except OperatorShipmentRequest.DoesNotExist:
            return None

        req.status = "allowed"
        req.allowedKg = amount
        req.decidedAt = now_ms()
        req.decidedByCode = str(who.get("code") or "")[:64]
        req.decidedByName = str(who.get("name") or "")[:200]
        req.save()

    _broadcast_requests()
    return req


def send_allowed_shipment(
    request_id: str, amount_kg, only_station_id: str | None = None
) -> dict:
    """Ishchi ruxsat berilgan miqdor doirasida jo'natadi.

    Serverda tekshiriladi (klientga ishonilmaydi):
      * so'rov "allowed" holatida bo'lishi,
      * jo'natuvchi AYNAN shu zapravka bo'lishi (`only_station_id`),
      * miqdor ruxsat etilgandan OSHMASLIGI,
      * balansda yetarli yoqilg'i bo'lishi.

    Jo'natma yaratish + balansdan ayirish + so'rovni yopish — bitta atomik amalda.

    Qaytaradi:
      {"ok": True,  "request": ..., "shipment": ..., "balance": ...}
      {"ok": False, "reason": "notfound"|"forbidden"|"over-limit"|"insufficient"|"invalid", ...}
    """
    amount = _norm(amount_kg)
    if amount <= 0:
        return {"ok": False, "reason": "invalid"}

    with transaction.atomic():
        try:
            req = OperatorShipmentRequest.objects.select_for_update().get(
                id=request_id, status="allowed"
            )
        except OperatorShipmentRequest.DoesNotExist:
            return {"ok": False, "reason": "notfound"}

        if only_station_id is not None and req.fromStationId != only_station_id:
            return {"ok": False, "reason": "forbidden"}

        limit = _norm(req.allowedKg or 0)
        # Kichik epsilon — suzuvchi nuqta yaxlitlash chekkasi uchun.
        if amount > limit + 1e-9:
            return {"ok": False, "reason": "over-limit", "allowed": limit}

        shipment_id = f"req-{req.id}"[:64]
        result = send_station_shipment(
            {
                "id": shipment_id,
                "fromStationId": req.fromStationId,
                "fromStationName": req.fromStationName,
                "toStationId": req.toStationId,
                "toStationName": req.toStationName,
                "amountKg": amount,
            }
        )
        if not result.get("ok"):
            # Balans yetmadi — so'rov "allowed" holicha qoladi, keyin urinish mumkin.
            return result

        req.status = "approved"
        req.amountKg = amount  # haqiqatda jo'natilgan miqdor
        req.shipmentId = shipment_id
        req.save()

    _broadcast_requests()
    return {
        "ok": True,
        "request": req,
        "shipment": result["shipment"],
        "balance": result["balance"],
    }


def reject_shipment_request(
    request_id: str, reason: str = "", decided_by: dict | None = None
) -> OperatorShipmentRequest | None:
    """Admin rad etdi. Balansga umuman tegilmaydi (so'rov hech qachon ayirmagan)."""
    who = decided_by or {}

    with transaction.atomic():
        try:
            req = OperatorShipmentRequest.objects.select_for_update().get(
                id=request_id, status="pending"
            )
        except OperatorShipmentRequest.DoesNotExist:
            return None

        req.status = "rejected"
        req.decidedAt = now_ms()
        req.decidedByCode = str(who.get("code") or "")[:64]
        req.decidedByName = str(who.get("name") or "")[:200]
        req.rejectReason = str(reason or "").strip()[:300]
        req.save()

    _broadcast_requests()
    return req


def accept_shipment(
    shipment_id: str, accepted_kg, only_station_id: str | None = None
) -> tuple[OperatorShipment, OperatorStationBalance] | str | None:
    """
    Pending jo'natmani qabul qilingan deb belgilaydi VA manzil stansiya balansiga
    qabul qilingan miqdorni qo'shadi — ikkalasi bitta atomik tranzaksiyada.
    Frontend endi balansni o'zi hisoblamaydi, shu yerdan qaytgan qiymatni ko'rsatadi.

    `only_station_id` berilsa (admin bo'lmagan foydalanuvchi), jo'natma AYNAN shu
    stansiyaga atalgan bo'lishi shart. Aks holda "forbidden" qaytadi: jo'natma
    id'lari hamma klientga ko'rinadi, shuning uchun bunday tekshiruvsiz bir
    zapravka xodimi boshqa zapravkaga atalgan yoqilg'ini qabul qilib, uning
    balansini oshirib yuborishi mumkin edi.
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

        if only_station_id is not None and shipment.toStationId != only_station_id:
            return "forbidden"

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


# "Hammasini tozalash" uchun majburiy tasdiq so'zi. Frontend uni foydalanuvchiga
# yozdiradi va shu holicha yuboradi; server ham aynan shu so'zni talab qiladi —
# ya'ni tasodifiy bosish yoki takroriy so'rov bazani tozalab yubora olmaydi.
RESET_CONFIRM_WORD = "TOZALASH"


def reset_all() -> dict:
    """Demo/sinov uchun: barcha stansiya balanslari va jo'natmalarni butunlay tozalaydi.

    O'chirishdan OLDIN eng muhim raqamlarning "suratini" oladi va uni qaytaradi.
    Chaqiruvchi (view) uni audit iziga yozadi — shunda xato bosilgan bo'lsa,
    qaysi zapravkada qancha yoqilg'i bo'lganini keyin ko'rish va qo'lda tiklash
    mumkin bo'ladi. Jo'natmalar tarixi tiklanmaydi, faqat soni qayd etiladi.
    """
    with transaction.atomic():
        tank = OperatorCentralTank.objects.filter(id=CENTRAL_TANK_ID).first()
        snapshot = {
            "balances": {
                row.stationId: row.balanceKg
                for row in OperatorStationBalance.objects.all()
            },
            "centralTankKg": tank.balanceKg if tank else 0,
            "totalPurchasedKg": tank.totalPurchasedKg if tank else 0,
            "shipmentCount": OperatorShipment.objects.count(),
            "purchaseCount": OperatorCentralPurchase.objects.count(),
        }

        OperatorStationBalance.objects.all().delete()
        OperatorShipment.objects.all().delete()
        OperatorCentralTank.objects.all().delete()
        OperatorCentralPurchase.objects.all().delete()

    _broadcast_shipments()
    _broadcast("central-tank")
    return snapshot


# --- Markaziy (sotib olingan) yoqilg'i tanki ---------------------------------
# Realizatsiya bo'limi shu yagona tankdan tarqatadi: sotib olinganda balans
# oshadi, zapravkaga tarqatilganda kamayadi. Stansiya balanslari bilan bir xil
# naqsh (atomik + "operator" topikiga broadcast).

CENTRAL_TANK_ID = "main"
# Realizatsiya paneli (frontenddagi REALIZATION_STATION_ID bilan bir xil) —
# markaziy tankdan tarqatilgan jo'natmalarning "from" stansiyasi.
REALIZATION_STATION_ID = "realizatsiya-paneli"
REALIZATION_STATION_NAME = "Realizatsiya paneli"


def _central_state(tank: OperatorCentralTank) -> dict:
    purchases = list(OperatorCentralPurchase.objects.all()[:100])
    return {
        "balanceKg": tank.balanceKg,
        "totalPurchasedKg": tank.totalPurchasedKg,
        "updatedAt": tank.updatedAt,
        "purchases": [
            {
                "id": p.id,
                "amountKg": p.amountKg,
                "source": p.source,
                "createdAt": p.createdAt,
            }
            for p in purchases
        ],
    }


def read_central_tank() -> dict:
    tank, _ = OperatorCentralTank.objects.get_or_create(id=CENTRAL_TANK_ID)
    return _central_state(tank)


def add_central_purchase(amount_kg, source, purchase_id=None) -> dict | None:
    """Markaziy tankka yoqilg'i sotib olinganda: balans va jami sotib olishga qo'shadi.

    Idempotent: agar shu `id` bilan sotib olish allaqachon yozilgan bo'lsa (so'rov
    qayta yuborilgan / takroriy bosilgan bo'lsa), balansni QAYTA oshirmaydi —
    mavjud holatni qaytaradi. Tank qatorini avval qulflaymiz, shuning uchun bir xil
    id bilan parallel so'rovlar ham xavfsiz (dublikat / ikki karra qo'shish bo'lmaydi).
    """
    amount = _norm(amount_kg)
    if amount <= 0:
        return None

    src = str(source or "").strip()[:200]
    pid = str(purchase_id or uuid.uuid4()).strip() or str(uuid.uuid4())

    with transaction.atomic():
        tank, _ = OperatorCentralTank.objects.select_for_update().get_or_create(
            id=CENTRAL_TANK_ID
        )
        if OperatorCentralPurchase.objects.filter(id=pid).exists():
            # Allaqachon hisoblangan — idempotentlik.
            return _central_state(tank)

        OperatorCentralPurchase.objects.create(
            id=pid, amountKg=amount, source=src, createdAt=now_ms()
        )
        tank.balanceKg = _norm((tank.balanceKg or 0.0) + amount)
        tank.totalPurchasedKg = _norm((tank.totalPurchasedKg or 0.0) + amount)
        tank.updatedAt = now_ms()
        tank.save()

    _broadcast("central-tank")
    return _central_state(tank)


def distribute_from_central(data: dict) -> dict:
    """Realizatsiyadan zapravkaga tarqatadi: markaziy tankdan ayirish + jo'natma
    yaratish BITTA atomik amalda.

    Tankda yetarli yoqilg'i bo'lmasa — RAD etadi (hech narsa o'zgarmaydi). Shu tarzda
    ikki kishi bir vaqtda tarqatsa ham tank manfiyga tushmaydi va jo'natmalar yig'indisi
    sotib olingandan oshib ketmaydi.

    Idempotent: shu `id` bilan jo'natma allaqachon bo'lsa, qayta ayirmaydi.

    Qaytaradi:
      {"ok": True,  "shipment": <OperatorShipment>, "tank": <state>}
      {"ok": False, "reason": "invalid"}
      {"ok": False, "reason": "insufficient", "available": <kg>}
    """
    to_station_id = str(data.get("toStationId") or "").strip()
    amount = _norm(data.get("amountKg"))
    if not to_station_id or amount <= 0:
        return {"ok": False, "reason": "invalid"}

    shipment_id = str(data.get("id") or uuid.uuid4()).strip() or str(uuid.uuid4())

    with transaction.atomic():
        tank, _ = OperatorCentralTank.objects.select_for_update().get_or_create(
            id=CENTRAL_TANK_ID
        )

        existing = OperatorShipment.objects.filter(id=shipment_id).first()
        if existing is not None:
            # Idempotentlik: allaqachon yaratilgan, qayta ayirmaymiz.
            return {"ok": True, "shipment": existing, "tank": _central_state(tank)}

        available = tank.balanceKg or 0.0
        # Kichik epsilon — suzuvchi nuqta yaxlitlash chekkasi uchun.
        if amount > available + 1e-9:
            return {"ok": False, "reason": "insufficient", "available": _norm(available)}

        tank.balanceKg = _norm(max(0.0, available - amount))
        tank.updatedAt = now_ms()
        tank.save()

        shipment = OperatorShipment.objects.create(
            id=shipment_id,
            fromStationId=REALIZATION_STATION_ID,
            fromStationName=REALIZATION_STATION_NAME,
            toStationId=to_station_id,
            toStationName=data.get("toStationName") or to_station_id,
            amountKg=amount,
            createdAt=now_ms(),
            status="pending",
        )

    _broadcast_shipments()
    _broadcast("central-tank")
    return {"ok": True, "shipment": shipment, "tank": _central_state(tank)}


def subtract_central(amount_kg) -> dict | None:
    """Realizatsiyadan tarqatilganda: markaziy tank balansidan ayiradi (0 gacha)."""
    amount = _norm(amount_kg)
    if amount <= 0:
        return None

    with transaction.atomic():
        tank, _ = OperatorCentralTank.objects.select_for_update().get_or_create(
            id=CENTRAL_TANK_ID
        )
        tank.balanceKg = _norm(max(0.0, (tank.balanceKg or 0.0) - amount))
        tank.updatedAt = now_ms()
        tank.save()

    _broadcast("central-tank")
    return _central_state(tank)


def delete_shipment(shipment_id: str) -> bool:
    """Admin: jo'natma/farq yozuvini butunlay o'chiradi (statistika jadvalidan)."""
    if not shipment_id:
        return False

    deleted, _ = OperatorShipment.objects.filter(id=shipment_id).delete()
    if deleted:
        _broadcast_shipments()
    return bool(deleted)
