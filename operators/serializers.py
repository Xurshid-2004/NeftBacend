from rest_framework import serializers

from .models import (
    OperatorCentralPurchase,
    OperatorCentralTank,
    OperatorOverlimit,
    OperatorShipment,
    OperatorShipmentRequest,
    OperatorStationBalance,
)


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


class OperatorShipmentRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperatorShipmentRequest
        fields = [
            "id",
            "fromStationId",
            "fromStationName",
            "toStationId",
            "toStationName",
            "amountKg",
            "masulShaxs",
            "requestedByCode",
            "requestedByName",
            "createdAt",
            "status",
            "allowedKg",
            "decidedAt",
            "decidedByCode",
            "decidedByName",
            "rejectReason",
            "shipmentId",
        ]


class OperatorCentralPurchaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperatorCentralPurchase
        fields = ["id", "amountKg", "source", "createdAt"]


class OperatorCentralTankSerializer(serializers.ModelSerializer):
    purchases = serializers.SerializerMethodField()

    class Meta:
        model = OperatorCentralTank
        fields = ["balanceKg", "totalPurchasedKg", "updatedAt", "purchases"]

    def get_purchases(self, _obj):
        qs = OperatorCentralPurchase.objects.all()[:100]
        return OperatorCentralPurchaseSerializer(qs, many=True).data
