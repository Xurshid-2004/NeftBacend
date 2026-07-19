"""
Submission serializerlari.

Chiqishda Firestore hujjat shaklini takrorlaymiz:
  * `id` -> string;
  * `extra` JSON ichidagi dinamik maydonlar yuqori darajaga "tekis" chiqadi;
  * qiymati None bo'lgan maydonlar tashlab yuboriladi (Firestore sanitize:
    undefined -> hujjatda yo'q). Shu sababli lokomotiv yozuvida korxona
    maydonlari ko'rinmaydi — aynan Firestore'dagidek.
"""

from rest_framework import serializers

from common.drf import MsModelSerializer

from .models import DailySummary, FuelRecord, KorxonaWorkerCode, Submission, YearlySummary


class SubmissionSerializer(MsModelSerializer):
    class Meta:
        model = Submission
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        extra = data.pop("extra", None)
        if isinstance(extra, dict):
            data.update(extra)
        # None qiymatli maydonlarni olib tashlaymiz (Firestore: undefined -> yo'q)
        return {k: v for k, v in data.items() if v is not None}


class FuelRecordSerializer(MsModelSerializer):
    class Meta:
        model = FuelRecord
        fields = "__all__"


class DailySummarySerializer(MsModelSerializer):
    id = serializers.CharField(source="docId", read_only=True)

    class Meta:
        model = DailySummary
        fields = "__all__"


class YearlySummarySerializer(MsModelSerializer):
    id = serializers.CharField(source="docId", read_only=True)

    class Meta:
        model = YearlySummary
        fields = "__all__"


class KorxonaWorkerCodeSerializer(MsModelSerializer):
    class Meta:
        model = KorxonaWorkerCode
        fields = ["korxonaNomi", "code", "updatedAt"]
