from rest_framework import serializers

from .models import OperatorOverlimit, OperatorShipment, OperatorStationBalance


class OperatorStationBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperatorStationBalance
        fields = ["stationId", "balanceKg", "overlimitKg", "updatedAt"]


class OperatorOverlimitSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperatorOverlimit
        fields = "__all__"


class OperatorShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperatorShipment
        fields = [
            "id",
            "fromStationId",
            "fromStationName",
            "toStationId",
            "toStationName",
            "amountKg",
            "createdAt",
            "status",
            "acceptedAt",
            "acceptedKg",
        ]
