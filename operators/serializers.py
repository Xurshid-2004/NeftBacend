from rest_framework import serializers

from .models import OperatorOverlimit, OperatorStationBalance


class OperatorStationBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperatorStationBalance
        fields = ["stationId", "balanceKg", "overlimitKg", "updatedAt"]


class OperatorOverlimitSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperatorOverlimit
        fields = "__all__"
