from django.db import transaction
from rest_framework import serializers

from common.drf import MsModelSerializer
from common.timeutil import now_ms

from . import face_service
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
    """Xodim yozuvi + Face ID ro'yxatdan o'tkazish.

    MUHIM: `photo` va `faceSamples` — FAQAT YOZISH uchun (`write_only`). Ya'ni
    `/staff/` ro'yxati AVVALGI shakli va hajmida qoladi (unga surat qo'shilmaydi),
    faqat ikkita yengil bayroq — `hasPhoto` va `hasFace` — qo'shiladi. Surat
    alohida `GET /api/staff/{id}/photo/` orqali olinadi.
    """

    photo = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=False
    )
    faceSamples = serializers.ListField(
        child=serializers.CharField(trim_whitespace=False),
        write_only=True,
        required=False,
        allow_empty=True,
    )
    hasPhoto = serializers.SerializerMethodField()
    hasFace = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = "__all__"
        extra_kwargs = {"photoUpdatedAt": {"read_only": True}}

    def get_hasPhoto(self, obj) -> bool:
        annotated = getattr(obj, "_has_photo", None)
        if annotated is not None:
            return bool(annotated)
        return bool((obj.photo or "").strip())

    def get_hasFace(self, obj) -> bool:
        annotated = getattr(obj, "_has_face", None)
        if annotated is not None:
            return bool(annotated)
        return face_service.has_template(obj.tabelNumber)

    def validate_photo(self, value):
        try:
            return face_service.validate_photo(value)
        except face_service.FaceError as exc:
            raise serializers.ValidationError(str(exc)) from None

    def _pop_face(self, validated_data):
        photo = validated_data.pop("photo", None)
        raw_samples = validated_data.pop("faceSamples", None)
        try:
            samples = face_service.parse_samples(
                raw_samples, face_service.max_samples()
            )
        except face_service.FaceError as exc:
            raise serializers.ValidationError({"faceSamples": str(exc)}) from None
        return photo, samples

    def _actor(self) -> str:
        request = self.context.get("request")
        return str(getattr(getattr(request, "user", None), "displayName", "") or "")

    def _reject_duplicate(self, code: str, samples: list) -> None:
        """Bitta surat ikki xodimga qo'yilishining oldini oladi."""
        duplicate = face_service.find_duplicate(code, samples)
        if duplicate:
            owner = (
                Staff.objects.filter(tabelNumber=duplicate)
                .values_list("fullName", flat=True)
                .first()
            )
            name = owner or duplicate
            raise serializers.ValidationError(
                {"photo": f"Bu surat allaqachon boshqa xodimga biriktirilgan: {name}."}
            )

    def create(self, validated_data):
        photo, samples = self._pop_face(validated_data)
        # Yangi xodim uchun surat MAJBURIY — shunda Face ID hamma uchun ishlaydi.
        if not (photo or "").strip():
            raise serializers.ValidationError(
                {"photo": "Xodim surati majburiy — kameradan oling yoki fayl tanlang."}
            )
        if not samples:
            raise serializers.ValidationError(
                {"faceSamples": "Suratda yuz aniqlanmadi. Boshqa surat tanlang."}
            )
        validated_data["photo"] = photo
        validated_data["photoUpdatedAt"] = now_ms()
        self._reject_duplicate(validated_data.get("tabelNumber", ""), samples)
        with transaction.atomic():
            instance = super().create(validated_data)
            face_service.enroll(
                instance.tabelNumber, samples, created_by=self._actor()
            )
        return instance

    def update(self, instance, validated_data):
        photo, samples = self._pop_face(validated_data)
        old_code = (instance.tabelNumber or "").strip()
        if photo:
            validated_data["photo"] = photo
            validated_data["photoUpdatedAt"] = now_ms()
        if samples:
            self._reject_duplicate(old_code, samples)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            new_code = (instance.tabelNumber or "").strip()
            if new_code != old_code:
                # Kirish kodi o'zgardi — shablon yangi kod bilan yashaydi.
                face_service.move(old_code, new_code)
            if samples:
                face_service.enroll(new_code, samples, created_by=self._actor())
        return instance


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


class FaceLoginSerializer(serializers.Serializer):
    """POST /api/auth/face-login — kameradan olingan kadrlar.

    Har bir kadr: 96x96 kulrang piksellar (9216 bayt) base64 ko'rinishida.
    Shablon (biometrik vektor) serverda hisoblanadi — klientdan tayyor shablon
    QABUL QILINMAYDI.
    """

    samples = serializers.ListField(
        child=serializers.CharField(trim_whitespace=False),
        allow_empty=False,
        max_length=face_service.MAX_LOGIN_FRAMES,
    )
    deviceId = serializers.CharField(
        max_length=128, required=False, allow_blank=True, default=""
    )
