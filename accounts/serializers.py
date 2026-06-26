from rest_framework import serializers

from common.drf import MsModelSerializer

from .models import (
    AccessCode,
    ActiveSession,
    BlockedCode,
    DeviceLock,
    SecurityEvent,
    Staff,
)


class AccessCodeSerializer(MsModelSerializer):
    # Frontend AdminCodeRecord `id` ham (== code) kutadi
    id = serializers.CharField(source="code", read_only=True)

    class Meta:
        model = AccessCode
        fields = "__all__"


class StaffSerializer(MsModelSerializer):
    class Meta:
        model = Staff
        fields = "__all__"


class BlockedCodeSerializer(MsModelSerializer):
    id = serializers.CharField(source="code", read_only=True)

    class Meta:
        model = BlockedCode
        fields = "__all__"


class ActiveSessionSerializer(MsModelSerializer):
    id = serializers.CharField(source="uid", read_only=True)

    class Meta:
        model = ActiveSession
        fields = "__all__"


class SecurityEventSerializer(MsModelSerializer):
    class Meta:
        model = SecurityEvent
        fields = "__all__"


class DeviceLockSerializer(MsModelSerializer):
    id = serializers.CharField(source="deviceId", read_only=True)

    class Meta:
        model = DeviceLock
        fields = "__all__"


class LoginSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=64, trim_whitespace=True)
    deviceId = serializers.CharField(
        max_length=128, required=False, allow_blank=True, default=""
    )
