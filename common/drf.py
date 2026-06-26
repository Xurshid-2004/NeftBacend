"""
Umumiy DRF asoslari.

`MsModelSerializer` — Firestore hujjat shaklini saqlab qoladi:
  * integer `id` ni string sifatida qaytaradi (frontend `id: string` kutadi);
  * `null` qiymatlarni o'chirmaydi (Firestore'da bo'sh select = null).
"""

from __future__ import annotations

from rest_framework import serializers, viewsets


class MsModelSerializer(serializers.ModelSerializer):
    """`id` ni doimo string qilib chiqaradi."""

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if "id" in data and data["id"] is not None:
            data["id"] = str(data["id"])
        return data


class BaseModelViewSet(viewsets.ModelViewSet):
    """Standart CRUD; barcha app'lar shundan meros oladi."""

    pass
