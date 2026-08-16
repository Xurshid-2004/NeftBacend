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


def _photo_field():
    return serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=False
    )


def _face_samples_field():
    return serializers.ListField(
        child=serializers.CharField(trim_whitespace=False),
        write_only=True,
        required=False,
        allow_empty=True,
    )


class FaceEnrollMixin:
    """`photo` + `faceSamples` yozishning UMUMIY mantiqi.

    Xodim (`Staff`) va admin (`AccessCode`) Face ID ni AYNAN bir xil yo'ldan
    yozadi: bir xil validatsiya, bir xil chalkashlik tekshiruvi, bir xil
    shablon qurish. Qoida bitta joyda turadi — ikki nusxa bo'lib bir-biridan
    ajralib ketmasligi uchun.

    Maydonlarning o'zi har bir serializerda alohida e'lon qilinadi (DRF
    metaklassi faqat serializer bazalaridan maydon yig'adi), lekin ularning
    ishlov berish mantiqi shu yerda.
    """

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

    #: Shu serializer qaysi guruhga yozadi — `face_service.GROUP_*`.
    face_group: str = ""

    def _reject_conflict(self, code: str, samples: list) -> None:
        """Yuz boshqa birov bilan chalkashadigan bo'lsa — SAQLAMAYDI.

        Bu — chalkashlikka qarshi eng muhim qadam: bir-biriga o'xshab
        ketadigan ikkita shablon bazaga umuman tushmasa, kirishda ham hech
        qachon chalkashmaydi. Ayniqsa admin bilan oddiy xodim orasida (qarang
        `face_service.find_conflict`).
        """
        conflict = face_service.find_conflict(code, samples, self.face_group)
        if not conflict:
            return
        other_code, reason = conflict
        owner = face_service.owner_label(other_code)
        if reason == "same":
            message = f"Bu surat allaqachon boshqasiga biriktirilgan: {owner}."
        elif reason == "cross":
            message = (
                f"Bu yuz {owner} bilan chalkashib ketishi mumkin — bunda odam "
                "o'zganing bo'limiga kirib qolardi, shuning uchun saqlanmadi. "
                "Yorug' joyda, kameraga to'g'ri qarab qayta surat oling. Agar "
                "bu AYNAN o'sha odam bo'lsa, unga ikkinchi hisob ochilmaydi."
            )
        else:
            message = (
                f"Bu yuz {owner} ga juda o'xshash — Face ID ularni chalkashtirib "
                "yuborishi mumkin. Yorug' joyda, kameraga to'g'ri qarab qayta "
                "surat oling; baribir takrorlansa, bu odam Face ID siz (faqat "
                "kod bilan) ishlashi kerak."
            )
        raise serializers.ValidationError({"photo": message})


class AccessCodeSerializer(FaceEnrollMixin, MsModelSerializer):
    """Admin/developer kirish kodi + (adminlar uchun) Face ID.

    `photo`/`faceSamples` — `StaffSerializer` dagi kabi FAQAT YOZISH uchun:
    `/access-codes/` ro'yxati avvalgi shaklida qoladi, unga faqat ikkita
    yengil bayroq (`hasPhoto`, `hasFace`) qo'shiladi.
    """

    face_group = face_service.GROUP_ADMIN

    # Frontend AdminCodeRecord `id` ham (== code) kutadi
    id = serializers.CharField(source="code", read_only=True)
    photo = _photo_field()
    faceSamples = _face_samples_field()
    hasPhoto = serializers.SerializerMethodField()
    hasFace = serializers.SerializerMethodField()

    class Meta:
        model = AccessCode
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
        return face_service.has_template(obj.code)

    def validate_code(self, value):
        """Admin kodi xodim tabel raqami bilan bir xil bo'lmasin.

        Face ID shabloni KOD bo'yicha saqlanadi va login ham avval admin
        kodini sinaydi — bir xil qiymat ikkalasini bir-biriga ulab qo'yardi.
        """
        code = (value or "").strip()
        if code and Staff.objects.filter(tabelNumber=code).exists():
            raise serializers.ValidationError(
                "Bu kod xodim kirish kodi bilan bir xil. Boshqa kod tanlang."
            )
        return value

    def create(self, validated_data):
        photo, samples = self._pop_face(validated_data)
        code = (validated_data.get("code") or "").strip()
        # Yangi ADMIN uchun surat majburiy — xodimlardagi qoida bilan bir xil.
        # Developer kodi (odatda `manage.py create_access_code` orqali, tizimni
        # birinchi marta ishga tushirishda) bu talabdan ozod: aks holda hech
        # qanday kod bo'lmagan bo'sh bazada birinchi kirishning iloji qolmasdi.
        if validated_data.get("role", "admin") == "admin":
            if not (photo or "").strip():
                raise serializers.ValidationError(
                    {"photo": "Admin surati majburiy — kameradan oling yoki fayl tanlang."}
                )
            if not samples:
                raise serializers.ValidationError(
                    {"faceSamples": "Suratda yuz aniqlanmadi. Boshqa surat tanlang."}
                )
        if photo:
            validated_data["photo"] = photo
            validated_data["photoUpdatedAt"] = now_ms()
        if samples:
            self._reject_conflict(code, samples)
        with transaction.atomic():
            instance = super().create(validated_data)
            if samples:
                face_service.enroll(instance.code, samples, created_by=self._actor())
        return instance

    def update(self, instance, validated_data):
        photo, samples = self._pop_face(validated_data)
        if photo:
            validated_data["photo"] = photo
            validated_data["photoUpdatedAt"] = now_ms()
        if samples:
            self._reject_conflict(instance.code, samples)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if samples:
                face_service.enroll(instance.code, samples, created_by=self._actor())
        return instance


class StaffSerializer(FaceEnrollMixin, MsModelSerializer):
    """Xodim yozuvi + Face ID ro'yxatdan o'tkazish.

    MUHIM: `photo` va `faceSamples` — FAQAT YOZISH uchun (`write_only`). Ya'ni
    `/staff/` ro'yxati AVVALGI shakli va hajmida qoladi (unga surat qo'shilmaydi),
    faqat ikkita yengil bayroq — `hasPhoto` va `hasFace` — qo'shiladi. Surat
    alohida `GET /api/staff/{id}/photo/` orqali olinadi.
    """

    face_group = face_service.GROUP_STAFF

    photo = _photo_field()
    faceSamples = _face_samples_field()
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

    def validate_tabelNumber(self, value):
        """Xodim kodi admin kirish kodi bilan bir xil bo'lmasin.

        `AccessCodeSerializer.validate_code` ning teskarisi — ikkala tomondan
        ham to'silsagina kodlar haqiqatan takrorlanmaydi.
        """
        code = (value or "").strip()
        current = (getattr(self.instance, "tabelNumber", "") or "").strip()
        if code and code != current and AccessCode.objects.filter(pk=code).exists():
            raise serializers.ValidationError(
                "Bu kod admin kirish kodi bilan bir xil. Boshqa kod tanlang."
            )
        return value

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
        self._reject_conflict(validated_data.get("tabelNumber", ""), samples)
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
            self._reject_conflict(old_code, samples)
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
