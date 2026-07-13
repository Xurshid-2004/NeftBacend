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

from accounts.permissions import IsAdmin, IsAuthenticated

from . import services
from .models import OperatorStationBalance
from .serializers import OperatorShipmentSerializer, OperatorStationBalanceSerializer


class BalanceListView(APIView):
    """Barcha stansiya balanslari — admin/operator paneli ko'radi."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = OperatorStationBalance.objects.all()
        return Response(OperatorStationBalanceSerializer(qs, many=True).data)


class SubtractView(APIView):
    """Ishchi saqlaganda chaqiriladi — worker faqat o'z stansiyasidan ayiradi."""

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


def _station_for(request):
    """Admin: so'rovdagi stationId; operator: faqat o'z stansiyasi; aks holda 403."""
    user = request.user
    if getattr(user, "is_admin", False):
        return request.data.get("stationId")
    if getattr(user, "role", None) == "operator":
        return user.stationId
    raise PermissionDenied("Faqat admin yoki operator balansni o'zgartira oladi.")


class SetView(APIView):
    """Admin yoki operator: balansni o'rnatadi (operator faqat o'z stansiyasi)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        station_id = _station_for(request)
        state = services.set_balance(station_id, request.data.get("amountKg"))
        return Response(state or {})


class ChangeView(APIView):
    """Admin yoki operator: balansni delta bilan o'zgartiradi (operator faqat o'z stansiyasi)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        station_id = _station_for(request)
        state = services.change_balance(station_id, request.data.get("deltaKg"))
        return Response(state or {})


class ShipmentListCreateView(APIView):
    """
    GET  /api/operator/shipments/  -> barcha jo'natmalar (admin/operator paneli filtrlaydi)
    POST /api/operator/shipments/  -> yangi (pending) jo'natma yaratadi
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = services.list_shipments()
        return Response(OperatorShipmentSerializer(qs, many=True).data)

    def post(self, request):
        user = request.user
        payload = dict(request.data)
        # Operator faqat o'z stansiyasidan jo'natishi mumkin; admin istalgan stansiyani yubora oladi.
        if not getattr(user, "is_admin", False) and getattr(user, "role", None) == "operator":
            payload["fromStationId"] = user.stationId

        shipment = services.create_shipment(payload)
        if shipment is None:
            return Response({"detail": "Jo'natma ma'lumotlari noto'g'ri."}, status=400)
        return Response(OperatorShipmentSerializer(shipment).data, status=201)


class ShipmentAcceptView(APIView):
    """POST /api/operator/shipments/<id>/accept/ -> pending jo'natmani qabul qilingan deb belgilaydi."""

    permission_classes = [IsAuthenticated]

    def post(self, request, shipment_id):
        shipment = services.accept_shipment(shipment_id, request.data.get("acceptedKg"))
        if shipment is None:
            return Response(
                {"detail": "Jo'natma topilmadi yoki allaqachon qabul qilingan."}, status=404
            )
        return Response(OperatorShipmentSerializer(shipment).data)


class ShipmentDeleteView(APIView):
    """DELETE /api/operator/shipments/<id>/ -> faqat admin: jo'natma/farq yozuvini o'chiradi."""

    permission_classes = [IsAdmin]

    def delete(self, request, shipment_id):
        if not services.delete_shipment(shipment_id):
            return Response({"detail": "Jo'natma topilmadi."}, status=404)
        return Response(status=204)
