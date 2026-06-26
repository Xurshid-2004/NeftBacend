"""
Catalog serializerlari.

Setting / Variant / ClosedDay — Firestore "JSON hujjat" kolleksiyalari.
Ular `data` JSONField ichidagi maydonlarni "tekis" (flat) qilib chiqaradi,
shunda API javobi Firestore hujjati bilan bir xil ko'rinadi. Yozishda
PATCH = merge (Firestore setDoc({merge:true}) kabi), PUT = to'liq almashtirish.
"""

from __future__ import annotations

from rest_framework import serializers

from common.drf import MsModelSerializer
from common.timeutil import now_ms

from .models import (
    Approval,
    ClosedDay,
    Limit,
    Question,
    Setting,
    Uzel,
    Variant,
    Zapravka,
)

_RESERVED = {"id", "updatedAt", "createdAt"}


class JsonDocumentSerializer(serializers.Serializer):
    """`data` JSONField ni tekis hujjat sifatida ko'rsatadigan asos."""

    pk_attr = "key"  # subklassda override qilinadi

    def to_representation(self, instance):
        out = dict(instance.data or {})
        out["id"] = str(instance.pk)
        out[self.pk_attr] = str(instance.pk)
        out["updatedAt"] = instance.updatedAt
        return out

    def to_internal_value(self, data):
        payload = {k: v for k, v in data.items() if k not in _RESERVED | {self.pk_attr}}
        pk = data.get(self.pk_attr) or data.get("id")
        return {"_pk": pk, "_data": payload}

    def create(self, validated_data):
        pk = validated_data["_pk"]
        if not pk:
            raise serializers.ValidationError({self.pk_attr: "majburiy"})
        model = self.Meta.model
        obj, _ = model.objects.update_or_create(
            pk=pk,
            defaults={"data": validated_data["_data"], "updatedAt": now_ms()},
        )
        return obj

    def update(self, instance, validated_data):
        if getattr(self, "partial", False):
            merged = dict(instance.data or {})
            merged.update(validated_data["_data"])
            instance.data = merged
        else:
            instance.data = validated_data["_data"]
        instance.updatedAt = now_ms()
        instance.save()
        return instance


class SettingSerializer(JsonDocumentSerializer):
    pk_attr = "key"

    class Meta:
        model = Setting


class VariantSerializer(JsonDocumentSerializer):
    pk_attr = "stationId"

    class Meta:
        model = Variant


class ClosedDaySerializer(JsonDocumentSerializer):
    pk_attr = "docId"

    class Meta:
        model = ClosedDay


class UzelSerializer(MsModelSerializer):
    class Meta:
        model = Uzel
        fields = "__all__"


class ZapravkaSerializer(MsModelSerializer):
    class Meta:
        model = Zapravka
        fields = "__all__"


class QuestionSerializer(MsModelSerializer):
    class Meta:
        model = Question
        fields = "__all__"


class LimitSerializer(MsModelSerializer):
    class Meta:
        model = Limit
        fields = "__all__"


class ApprovalSerializer(MsModelSerializer):
    class Meta:
        model = Approval
        fields = "__all__"
