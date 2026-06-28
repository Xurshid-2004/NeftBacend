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

from accounts.permissions import IsAuthenticated

from . import services
from .models import OperatorStationBalance
from .serializers import OperatorStationBalanceSerializer


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
