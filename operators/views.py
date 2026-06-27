"""
Operator balans API — `operator-balance.ts` chaqiruvlariga mos:
  GET  /api/operator/balances/   -> barcha stansiya balanslari (subscribe/poll)
  POST /api/operator/subtract/   -> ishchi yozuv saqlaganda yoqilg'i ayirish
  POST /api/operator/set/        -> admin balansni o'rnatadi
  POST /api/operator/change/     -> admin balansni o'zgartiradi (+/-)
"""

from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin, IsAuthenticated

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


class SetView(APIView):
    """Admin: balansni aniq qiymatga o'rnatadi."""

    permission_classes = [IsAdmin]

    def post(self, request):
        state = services.set_balance(request.data.get("stationId"), request.data.get("amountKg"))
        return Response(state or {})


class ChangeView(APIView):
    """Admin: balansni delta bilan o'zgartiradi (+/-)."""

    permission_classes = [IsAdmin]

    def post(self, request):
        state = services.change_balance(request.data.get("stationId"), request.data.get("deltaKg"))
        return Response(state or {})
