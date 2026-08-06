"""
Operator balans API — `operator-balance.ts` chaqiruvlariga mos:
  GET  /api/operator/balances/   -> barcha stansiya balanslari (subscribe/poll)
  POST /api/operator/subtract/   -> ishchi yozuv saqlaganda yoqilg'i ayirish
  POST /api/operator/set/        -> admin balansni o'rnatadi
  POST /api/operator/change/     -> admin balansni o'zgartiradi (+/-)
"""

from __future__ import annotations

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin, IsAuthenticated, section_required

from . import services
from .models import OperatorShipment, OperatorStationBalance
from .serializers import (
    OperatorShipmentRequestSerializer,
    OperatorShipmentSerializer,
    OperatorStationBalanceSerializer,
)


class BalanceListView(APIView):
    """Barcha stansiya balanslari — admin/operator paneli ko'radi."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = OperatorStationBalance.objects.all()
        return Response(OperatorStationBalanceSerializer(qs, many=True).data)


class SubtractView(APIView):
    """Ishchi saqlaganda chaqiriladi — worker faqat o'z stansiyasidan ayiradi."""

    # ATAYLAB bo'lim bilan cheklanmagan: bu operator panelining amali emas,
    # yozuv saqlash oqimining bir qismi (admin yozuvni tahrirlaganda ham
    # chaqiriladi). Cheklansa oddiy tahrirlash buzilardi.
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        station_id = request.data.get("stationId")
        if not getattr(user, "is_admin", False):
            station_id = user.stationId  # worker o'z stansiyasi
        details = {
            "category": request.data.get("category"),
            "staffCode": request.data.get("staffCode") or getattr(user, "code", None),
            "staffName": request.data.get("staffName") or getattr(user, "displayName", None),
            "nodeId": request.data.get("nodeId") or getattr(user, "nodeId", None),
        }
        state = services.subtract(station_id, request.data.get("amountKg"), details)
        return Response(state or {"stationId": station_id, "balanceKg": 0, "overlimitKg": 0, "exceededKg": 0})


def _current_balance(station_id) -> float | None:
    """Audit izida "oldingi qiymat" ni ko'rsatish uchun (yozuv bo'lmasa None)."""
    row = OperatorStationBalance.objects.filter(stationId=station_id).first()
    return row.balanceKg if row else None


def _actor(request) -> dict:
    """Audit izi uchun: amalni kim bajardi (JWT dagi ma'lumot)."""
    user = getattr(request, "user", None)
    return {
        "userId": getattr(user, "code", "") or "",
        "userName": getattr(user, "displayName", "") or "",
        "userRole": getattr(user, "role", "") or "",
    }


def _station_for(request):
    """Admin: so'rovdagi stationId; operator: faqat o'z stansiyasi; aks holda 403."""
    user = request.user
    if getattr(user, "is_admin", False):
        return request.data.get("stationId")
    if getattr(user, "role", None) == "operator":
        return user.stationId
    raise PermissionDenied("Faqat admin yoki operator balansni o'zgartira oladi.")


def _require_operator_or_admin(request):
    """Markaziy tankni faqat admin/developer yoki operator o'zgartira oladi."""
    user = request.user
    if getattr(user, "is_admin", False) or getattr(user, "role", None) == "operator":
        return
    raise PermissionDenied("Faqat admin yoki operator markaziy tankni o'zgartira oladi.")


class SetView(APIView):
    """Admin yoki operator: balansni o'rnatadi (operator faqat o'z stansiyasi)."""

    permission_classes = [IsAuthenticated, section_required("operator")]

    def post(self, request):
        station_id = _station_for(request)
        before = _current_balance(station_id)
        state = services.set_balance(station_id, request.data.get("amountKg"))
        if state:
            services.write_audit(
                _actor(request),
                "update",
                "operator_balance",
                station_id,
                {"amal": "set", "oldinKg": before, "yangiKg": state.get("balanceKg")},
            )
        return Response(state or {})


class ChangeView(APIView):
    """Admin yoki operator: balansni delta bilan o'zgartiradi (operator faqat o'z stansiyasi)."""

    permission_classes = [IsAuthenticated, section_required("operator")]

    def post(self, request):
        station_id = _station_for(request)
        before = _current_balance(station_id)
        state = services.change_balance(station_id, request.data.get("deltaKg"))
        if state:
            services.write_audit(
                _actor(request),
                "update",
                "operator_balance",
                station_id,
                {
                    "amal": "change",
                    "deltaKg": request.data.get("deltaKg"),
                    "oldinKg": before,
                    "yangiKg": state.get("balanceKg"),
                },
            )
        return Response(state or {})


class ShipmentListCreateView(APIView):
    """
    GET  /api/operator/shipments/  -> barcha jo'natmalar (admin/operator paneli filtrlaydi)
    POST /api/operator/shipments/  -> yangi (pending) jo'natma yaratadi VA jo'natuvchi
         zapravka balansidan o'sha miqdorni bitta atomik amalda ayiradi. Javobga
         yangilangan balans ham qo'shiladi (`balance`) — frontend o'zi hisoblamaydi.
    """

    permission_classes = [IsAuthenticated, section_required("operator")]

    def get(self, request):
        user = request.user
        # Admin/developer — barcha zapravkalar kesimi (bosh sahifa, «Выдача
        # топлива» paneli). Operator va worker — faqat O'Z zapravkasining
        # oldi-berdisi. Stansiyasi yo'q bo'lsa "" bilan filtrlanadi, ya'ni
        # bo'sh ro'yxat qaytadi (hech qachon "hammasi" emas).
        station_id = (
            None
            if getattr(user, "is_admin", False)
            else (getattr(user, "stationId", None) or "")
        )
        qs = services.list_shipments(station_id)
        return Response(OperatorShipmentSerializer(qs, many=True).data)

    def post(self, request):
        user = request.user
        payload = dict(request.data)

        # BEVOSITA yuborish endi FAQAT admin uchun. Operator va worker o'zboshimchalik
        # bilan jo'nata olmaydi — ular `POST /operator/shipment-requests/` orqali
        # ruxsat so'raydi, admin tasdiqlagach jo'natma shu yerdagi xizmat orqali
        # (`approve_shipment_request` ichida) yaratiladi. Bu tekshiruv SERVERDA
        # turgani muhim: aks holda so'rovni to'g'ridan-to'g'ri API ga yuborib,
        # ruxsat oqimini chetlab o'tish mumkin bo'lardi.
        if not getattr(user, "is_admin", False):
            raise PermissionDenied(
                "Bevosita yuborib bo'lmaydi — avval «Дизел юборишга рухсат» "
                "so'rovini qoldiring, admin tasdiqlaganidan keyin jo'natiladi."
            )

        result = services.send_station_shipment(payload)
        if not result.get("ok"):
            if result.get("reason") == "insufficient":
                return Response(
                    {
                        "detail": "Zapravka balansida yetarli yoqilg'i yo'q.",
                        "available": result.get("available", 0),
                    },
                    status=409,
                )
            return Response({"detail": "Jo'natma ma'lumotlari noto'g'ri."}, status=400)

        shipment = result["shipment"]
        services.write_audit(
            _actor(request),
            "create",
            "operator_shipment",
            shipment.id,
            {
                "amal": "yuborildi",
                "qayerdan": shipment.fromStationId,
                "qayerga": shipment.toStationId,
                "miqdorKg": shipment.amountKg,
                "yuborgandanKeyingiBalansKg": result["balance"].balanceKg,
            },
        )

        data = OperatorShipmentSerializer(shipment).data
        data["balance"] = OperatorStationBalanceSerializer(result["balance"]).data
        return Response(data, status=201)


class ShipmentRequestListCreateView(APIView):
    """
    GET  /api/operator/shipment-requests/  -> ruxsat so'rovlari
         (admin: hammasi; operator/worker: faqat o'z zapravkasi)
    POST /api/operator/shipment-requests/  -> yangi so'rov (BALANSGA TEGMAYDI)

    Ishchi/operator endi bevosita jo'nata olmaydi — avval shu so'rovni qoldiradi,
    admin `/admin/overlimit/korxona` sahifasida ruxsat berganidan keyingina
    haqiqiy jo'natma yaratiladi.
    """

    permission_classes = [IsAuthenticated, section_required("operator")]

    def get(self, request):
        user = request.user
        station_id = (
            None
            if getattr(user, "is_admin", False)
            else (getattr(user, "stationId", None) or "")
        )
        qs = services.list_shipment_requests(station_id)
        return Response(OperatorShipmentRequestSerializer(qs, many=True).data)

    def post(self, request):
        user = request.user
        payload = dict(request.data)

        # Jo'natuvchi zapravka TOKENDAN olinadi (admin bundan mustasno) —
        # so'rovda boshqa zapravkani ko'rsatib bo'lmaydi.
        if not getattr(user, "is_admin", False):
            station_id = getattr(user, "stationId", None)
            if not station_id:
                raise PermissionDenied("Sizga zapravka biriktirilmagan.")
            payload["fromStationId"] = station_id

        payload["requestedByCode"] = getattr(user, "code", "") or ""
        payload["requestedByName"] = getattr(user, "displayName", "") or ""

        req = services.create_shipment_request(payload)
        if req is None:
            return Response({"detail": "So'rov ma'lumotlari noto'g'ri."}, status=400)

        services.write_audit(
            _actor(request),
            "create",
            "operator_shipment_request",
            req.id,
            {
                "amal": "yuborishga ruxsat so'raldi",
                "qayerdan": req.fromStationId,
                "qayerga": req.toStationId,
                "miqdorKg": req.amountKg,
                "masulShaxs": req.masulShaxs,
            },
        )
        return Response(OperatorShipmentRequestSerializer(req).data, status=201)


class ShipmentRequestApproveView(APIView):
    """
    POST /api/operator/shipment-requests/<id>/approve/ -> FAQAT ADMIN.
    So'rovni tasdiqlaydi, haqiqiy jo'natmani yaratadi va balansdan ayiradi
    (hammasi bitta atomik amalda). Balans yetmasa 409 — so'rov o'zgarmaydi.
    """

    permission_classes = [IsAdmin, section_required("operator")]

    def post(self, request, request_id):
        user = request.user
        result = services.approve_shipment_request(
            request_id,
            {
                "code": getattr(user, "code", "") or "",
                "name": getattr(user, "displayName", "") or "",
            },
        )

        if not result.get("ok"):
            reason = result.get("reason")
            if reason == "notfound":
                return Response(
                    {"detail": "So'rov topilmadi yoki allaqachon hal qilingan."}, status=404
                )
            if reason == "insufficient":
                return Response(
                    {
                        "detail": "Zapravka balansida yetarli yoqilg'i yo'q.",
                        "available": result.get("available", 0),
                    },
                    status=409,
                )
            return Response({"detail": "So'rov ma'lumotlari noto'g'ri."}, status=400)

        req = result["request"]
        services.write_audit(
            _actor(request),
            "update",
            "operator_shipment_request",
            req.id,
            {
                "amal": "ruxsat berildi",
                "qayerdan": req.fromStationId,
                "qayerga": req.toStationId,
                "miqdorKg": req.amountKg,
                "jonatmaId": req.shipmentId,
                "ruxsatdanKeyingiBalansKg": result["balance"].balanceKg,
            },
        )

        data = OperatorShipmentRequestSerializer(req).data
        data["shipment"] = OperatorShipmentSerializer(result["shipment"]).data
        data["balance"] = OperatorStationBalanceSerializer(result["balance"]).data
        return Response(data)


class ShipmentRequestAllowView(APIView):
    """
    POST /api/operator/shipment-requests/<id>/allow/ -> FAQAT ADMIN («Бошқа қиймат»).
    So'ralganidan boshqa miqdorga ruxsat beradi. Jo'natma HOZIR yaratilmaydi va
    balansga tegilmaydi — ishchi shu chegara doirasida o'zi jo'natadi.
    """

    permission_classes = [IsAdmin, section_required("operator")]

    def post(self, request, request_id):
        user = request.user
        result = services.allow_shipment_request(
            request_id,
            request.data.get("allowedKg"),
            {
                "code": getattr(user, "code", "") or "",
                "name": getattr(user, "displayName", "") or "",
            },
        )
        if result == "invalid":
            return Response({"detail": "Ruxsat miqdori noto'g'ri (0 dan katta bo'lsin)."}, status=400)
        if result is None:
            return Response(
                {"detail": "So'rov topilmadi yoki allaqachon hal qilingan."}, status=404
            )

        services.write_audit(
            _actor(request),
            "update",
            "operator_shipment_request",
            result.id,
            {
                "amal": "boshqa miqdorga ruxsat berildi",
                "qayerdan": result.fromStationId,
                "qayerga": result.toStationId,
                "soralganKg": result.amountKg,
                "ruxsatBerilganKg": result.allowedKg,
            },
        )
        return Response(OperatorShipmentRequestSerializer(result).data)


class ShipmentRequestSendView(APIView):
    """
    POST /api/operator/shipment-requests/<id>/send/ -> ishchi/operator:
    ruxsat berilgan miqdor DOIRASIDA jo'natadi.

    Chegaradan oshib ketishga urinish 409 bilan rad etiladi — tekshiruv serverda,
    ya'ni klientni chetlab o'tib ko'proq yuborib bo'lmaydi.
    """

    permission_classes = [IsAuthenticated, section_required("operator")]

    def post(self, request, request_id):
        user = request.user
        only_station_id = (
            None
            if getattr(user, "is_admin", False)
            else (getattr(user, "stationId", None) or "")
        )

        result = services.send_allowed_shipment(
            request_id, request.data.get("amountKg"), only_station_id
        )

        if not result.get("ok"):
            reason = result.get("reason")
            if reason == "forbidden":
                raise PermissionDenied("Bu so'rov sizning zapravkangizga tegishli emas.")
            if reason == "notfound":
                return Response(
                    {"detail": "So'rov topilmadi yoki ruxsat holatida emas."}, status=404
                )
            if reason == "over-limit":
                return Response(
                    {
                        "detail": "Ruxsat berilgan miqdordan ko'p yubora olmaysiz.",
                        "allowed": result.get("allowed", 0),
                    },
                    status=409,
                )
            if reason == "insufficient":
                return Response(
                    {
                        "detail": "Zapravka balansida yetarli yoqilg'i yo'q.",
                        "available": result.get("available", 0),
                    },
                    status=409,
                )
            return Response({"detail": "Ma'lumotlar noto'g'ri."}, status=400)

        req = result["request"]
        services.write_audit(
            _actor(request),
            "create",
            "operator_shipment",
            req.shipmentId,
            {
                "amal": "ruxsat doirasida yuborildi",
                "qayerdan": req.fromStationId,
                "qayerga": req.toStationId,
                "ruxsatBerilganKg": req.allowedKg,
                "yuborilganKg": req.amountKg,
                "yuborgandanKeyingiBalansKg": result["balance"].balanceKg,
            },
        )

        data = OperatorShipmentRequestSerializer(req).data
        data["shipment"] = OperatorShipmentSerializer(result["shipment"]).data
        data["balance"] = OperatorStationBalanceSerializer(result["balance"]).data
        return Response(data)


class ShipmentRequestRejectView(APIView):
    """
    POST /api/operator/shipment-requests/<id>/reject/ -> FAQAT ADMIN.
    So'rovni rad etadi (sabab bilan). Balansga umuman tegilmaydi.
    """

    permission_classes = [IsAdmin, section_required("operator")]

    def post(self, request, request_id):
        user = request.user
        req = services.reject_shipment_request(
            request_id,
            request.data.get("reason"),
            {
                "code": getattr(user, "code", "") or "",
                "name": getattr(user, "displayName", "") or "",
            },
        )
        if req is None:
            return Response(
                {"detail": "So'rov topilmadi yoki allaqachon hal qilingan."}, status=404
            )

        services.write_audit(
            _actor(request),
            "update",
            "operator_shipment_request",
            req.id,
            {
                "amal": "rad etildi",
                "qayerdan": req.fromStationId,
                "qayerga": req.toStationId,
                "miqdorKg": req.amountKg,
                "sabab": req.rejectReason,
            },
        )
        return Response(OperatorShipmentRequestSerializer(req).data)


class ShipmentAcceptView(APIView):
    """
    POST /api/operator/shipments/<id>/accept/ -> pending jo'natmani qabul qilingan
    deb belgilaydi va manzil stansiya balansini bitta atomik amalda yangilaydi.
    Javobga yangilangan balans ham qo'shiladi (`balance`) — frontend uni o'zi
    hisoblamasdan, to'g'ridan-to'g'ri ko'rsatishi uchun.
    """

    permission_classes = [IsAuthenticated, section_required("operator")]

    def post(self, request, shipment_id):
        user = request.user
        # Admin istalgan jo'natmani qabul qila oladi; operator va worker esa
        # faqat O'ZIGA atalganini (stansiya tokendan olinadi).
        only_station_id = None if getattr(user, "is_admin", False) else getattr(user, "stationId", None) or ""

        result = services.accept_shipment(
            shipment_id, request.data.get("acceptedKg"), only_station_id
        )
        if result == "forbidden":
            raise PermissionDenied("Bu jo'natma sizning zapravkangizga atalmagan.")
        if result is None:
            return Response(
                {"detail": "Jo'natma topilmadi yoki allaqachon qabul qilingan."}, status=404
            )
        shipment, balance = result
        services.write_audit(
            _actor(request),
            "update",
            "operator_shipment",
            shipment.id,
            {
                "amal": "qabul qilindi",
                "qayerdan": shipment.fromStationId,
                "qayerga": shipment.toStationId,
                "yuborilganKg": shipment.amountKg,
                "qabulQilinganKg": shipment.acceptedKg,
                "qabuldanKeyingiBalansKg": balance.balanceKg,
            },
        )

        data = OperatorShipmentSerializer(shipment).data
        data["balance"] = OperatorStationBalanceSerializer(balance).data
        return Response(data)


class ShipmentDeleteView(APIView):
    """DELETE /api/operator/shipments/<id>/ -> faqat admin: jo'natma/farq yozuvini o'chiradi."""

    permission_classes = [IsAdmin, section_required("operator")]

    def delete(self, request, shipment_id):
        # O'chirishdan OLDIN ma'lumotini olamiz — audit izida nima o'chirilgani
        # ko'rinib tursin (yozuvning o'zi qaytarib bo'lmaydigan tarzda ketadi).
        doomed = OperatorShipment.objects.filter(id=shipment_id).first()
        if not services.delete_shipment(shipment_id):
            return Response({"detail": "Jo'natma topilmadi."}, status=404)

        services.write_audit(
            _actor(request),
            "delete",
            "operator_shipment",
            shipment_id,
            {
                "amal": "jo'natma o'chirildi",
                "qayerdan": doomed.fromStationId if doomed else None,
                "qayerga": doomed.toStationId if doomed else None,
                "miqdorKg": doomed.amountKg if doomed else None,
                "holat": doomed.status if doomed else None,
            },
        )
        return Response(status=204)


class ResetAllView(APIView):
    """
    POST /api/operator/reset/ -> faqat admin: demo/sinov uchun operator bo'limidagi
    BARCHA stansiya balanslari va jo'natmalarni butunlay tozalaydi (qaytarib bo'lmaydi).

    So'rov tanasida `{"confirm": "TOZALASH"}` bo'lishi SHART. Bu so'zsiz so'rov 400
    bilan rad etiladi — tasodifiy bosish, takroriy yuborilgan so'rov yoki qo'lda
    yozilgan `curl` bazani tozalab yubora olmasin.
    """

    permission_classes = [IsAdmin, section_required("operator")]

    def post(self, request):
        confirm = str(request.data.get("confirm") or "").strip().upper()
        if confirm != services.RESET_CONFIRM_WORD:
            return Response(
                {
                    "detail": (
                        f"Tasdiqlanmadi. Tozalash uchun \"{services.RESET_CONFIRM_WORD}\" "
                        "so'zini yuborish shart."
                    )
                },
                status=400,
            )

        snapshot = services.reset_all()
        # Eng muhim audit izi: bu amal qaytarilmaydi, shuning uchun o'chishdan
        # oldingi barcha balanslar ham izda saqlanadi (kerak bo'lsa qo'lda tiklash mumkin).
        services.write_audit(
            _actor(request),
            "delete",
            "operator_reset",
            "hammasi",
            {"amal": "operator bo'limi butunlay tozalandi", "ochirishdanOldin": snapshot},
        )
        return Response(snapshot, status=200)


class CentralTankView(APIView):
    """
    GET  /api/operator/central-tank/          -> markaziy tank holati (balans + tarix)
    POST /api/operator/central-tank/purchase/ -> yoqilg'i sotib olish (balansga qo'shadi)
    POST /api/operator/central-tank/subtract/ -> realizatsiyadan ayirish
    Faqat admin/operator o'zgartiradi; hamma (autentifikatsiyalangan) o'qiy oladi.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(services.read_central_tank())


class CentralTankPurchaseView(APIView):
    """Yoqilg'i sotib olindi — markaziy tank balansiga qo'shiladi (faqat admin/operator)."""

    permission_classes = [IsAuthenticated, section_required("operator")]

    def post(self, request):
        _require_operator_or_admin(request)
        state = services.add_central_purchase(
            request.data.get("amountKg"),
            request.data.get("source"),
            request.data.get("id"),
        )
        if state is None:
            return Response({"detail": "Sotib olingan miqdor noto'g'ri."}, status=400)

        services.write_audit(
            _actor(request),
            "create",
            "operator_central_purchase",
            request.data.get("id"),
            {
                "amal": "yoqilg'i sotib olindi",
                "miqdorKg": request.data.get("amountKg"),
                "manba": request.data.get("source"),
                "tankBalansKg": state.get("balanceKg"),
            },
        )
        return Response(state)


class CentralTankSubtractView(APIView):
    """Realizatsiyadan tarqatilganda markaziy tankdan ayiradi (faqat admin/operator)."""

    permission_classes = [IsAuthenticated, section_required("operator")]

    def post(self, request):
        _require_operator_or_admin(request)
        state = services.subtract_central(request.data.get("amountKg"))
        if state is None:
            return Response({"detail": "Ayiriladigan miqdor noto'g'ri."}, status=400)

        services.write_audit(
            _actor(request),
            "update",
            "operator_central_tank",
            "main",
            {
                "amal": "markaziy tankdan ayirildi",
                "miqdorKg": request.data.get("amountKg"),
                "tankBalansKg": state.get("balanceKg"),
            },
        )
        return Response(state)


class CentralTankDistributeView(APIView):
    """
    POST /api/operator/central-tank/distribute/ -> realizatsiyadan zapravkaga
    tarqatadi: markaziy tankdan ayirish + jo'natma yaratish BITTA atomik amalda.
    Tankda yetarli yoqilg'i bo'lmasa 409 bilan RAD etadi (hech narsa o'zgarmaydi).
    """

    permission_classes = [IsAuthenticated, section_required("operator")]

    def post(self, request):
        _require_operator_or_admin(request)
        result = services.distribute_from_central(request.data)
        if not result.get("ok"):
            if result.get("reason") == "insufficient":
                return Response(
                    {
                        "detail": "Markaziy tankda yetarli yoqilg'i yo'q.",
                        "available": result.get("available", 0),
                    },
                    status=409,
                )
            return Response({"detail": "Tarqatish ma'lumotlari noto'g'ri."}, status=400)

        shipment = result["shipment"]
        services.write_audit(
            _actor(request),
            "create",
            "operator_shipment",
            shipment.id,
            {
                "amal": "«Выдача топлива»дан tarqatildi",
                "qayerga": shipment.toStationId,
                "miqdorKg": shipment.amountKg,
                "tankBalansKg": result["tank"].get("balanceKg"),
            },
        )

        data = OperatorShipmentSerializer(shipment).data
        data["tank"] = result["tank"]
        return Response(data, status=201)
