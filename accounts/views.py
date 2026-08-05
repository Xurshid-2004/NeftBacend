"""
Auth oqimi (login sahifasi mantig'ining backend ko'chirmasi) + CRUD viewsetlar.

Login tartibi (frontend `app/(auth)/login/page.tsx` bilan bir xil):
  0. device_locks/{deviceId}.isBlocked bo'lsa -> 403, kod tekshirilmaydi
  1. access_codes/{code}: role admin|developer va isActive -> admin/developer sessiya
  2. staff.tabelNumber == code -> worker sessiya (stationId zapravka nomidan aniqlanadi)
  3. blocked_codes/{code} mavjud bo'lsa -> rad etiladi
  4. Hech biri mos kelmasa -> 401 "ВЫ ВЫЗВАЛИ У НАС ПОДОЗРЕНИЕ" + shu qurilmaning
     xato hisobi +1; 3-chi xatoda device_locks/{deviceId}.isBlocked=True (faqat shu
     qurilma bloklanadi, kod yoki boshqa foydalanuvchilarga taʼsir qilmaydi)
"""

from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.utils import resolve_zapravka
from common.timeutil import now_ms

from .authentication import create_access_token
from .models import (
    AccessCode,
    ActiveSession,
    BlockedCode,
    DeviceLock,
    SecurityEvent,
    Staff,
)
from .permissions import (
    IsAdmin,
    IsAdminOrReadOnly,
    IsUnrestrictedAdmin,
    section_required,
)
from .sections import normalize_sections
from .throttles import VaultThrottle
from .serializers import (
    AccessCodeSerializer,
    ActiveSessionSerializer,
    BlockedCodeSerializer,
    DeviceLockSerializer,
    SecurityEventSerializer,
    StaffSerializer,
)

# Shu qurilmadan ketma-ket shuncha marta noto'g'ri kod kiritilsa, faqat o'sha
# qurilma (deviceId) bloklanadi — boshqa foydalanuvchilarga taʼsir qilmaydi.
DEVICE_LOCKOUT_THRESHOLD = 3


def _build_admin_session(code: str) -> dict | None:
    try:
        ac = AccessCode.objects.get(pk=code)
    except AccessCode.DoesNotExist:
        return None
    if ac.role not in ("admin", "developer") or not ac.isActive:
        return None
    name = (ac.displayName or "").strip()
    if not name:
        return None
    return {
        "code": code,
        "role": ac.role,
        "nodeId": None,
        "stationId": None,
        "displayName": name,
        "codeType": ac.codeType,
        # None = cheklov yo'q (hamma bo'lim) — eski kodlar uchun shu holat.
        "allowedSections": normalize_sections(ac.allowedSections),
    }


def _build_staff_session(code: str) -> dict | None:
    staff = Staff.objects.filter(tabelNumber=code).first()
    if not staff:
        return None
    staff_code = (staff.tabelNumber or "").strip()
    staff_name = (staff.fullName or "").strip()
    staff_zap = (staff.zapravka or "").strip()
    if not staff_code or staff_code != code or not staff_name or not staff_zap:
        return None

    zap = resolve_zapravka(staff_zap)
    if not zap:
        return None

    # Operator xodimi "operator" rolida kiradi (o'z zapravka operator bo'limiga
    # tushadi); qolgan xodimlar avvalgidek "worker".
    role = "operator" if (staff.role or "").strip() == "operator" else "worker"

    return {
        "code": code,
        "role": role,
        "nodeId": zap.uzelId,
        "stationId": zap.id,
        "displayName": staff_name,
        "codeType": None,
    }


class LoginView(APIView):
    """POST /api/auth/login  { code, deviceId? } -> { token, session }"""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        code = str(request.data.get("code", "")).strip()
        device_id = str(request.data.get("deviceId", "")).strip()
        if not code:
            return Response(
                {"detail": "Kod kiritilmadi."}, status=status.HTTP_400_BAD_REQUEST
            )

        device_lock = DeviceLock.objects.filter(pk=device_id).first() if device_id else None
        if device_lock and device_lock.isBlocked:
            return Response(
                {"detail": "Bu qurilma bloklangan. Administratorga murojaat qiling."},
                status=status.HTTP_403_FORBIDDEN,
            )

        session = _build_admin_session(code) or _build_staff_session(code)

        if not session:
            SecurityEvent.objects.create(
                type="wrong_code", code=code, deviceId=device_id, timestamp=now_ms()
            )

            if device_id:
                device_lock, _ = DeviceLock.objects.get_or_create(deviceId=device_id)
                device_lock.attempts = (device_lock.attempts or 0) + 1
                device_lock.lockedCode = code

                if device_lock.attempts >= DEVICE_LOCKOUT_THRESHOLD:
                    device_lock.isBlocked = True
                    device_lock.lockedAt = now_ms()
                    device_lock.save()
                    SecurityEvent.objects.create(
                        type="device_locked", code=code, deviceId=device_id, timestamp=now_ms()
                    )
                    return Response(
                        {
                            "detail": "Bu qurilma bloklandi: 3 marta noto'g'ri kod kiritildi. "
                            "Administratorga murojaat qiling."
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )

                device_lock.save()

            return Response(
                {"detail": "ВЫ ВЫЗВАЛИ У НАС ПОДОЗРЕНИЕ"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if BlockedCode.objects.filter(pk=code).exists():
            SecurityEvent.objects.create(
                type="device_locked", code=code, deviceId=device_id, timestamp=now_ms()
            )
            return Response(
                {"detail": "Bu kirish kodi bloklangan. Administratorga murojaat qiling."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # To'g'ri kod kiritildi — shu qurilmaning oldingi xato hisobini tozalaymiz.
        if device_lock and device_lock.attempts:
            device_lock.attempts = 0
            device_lock.save()

        # Presence sessiyasi (active_sessions ekvivalenti)
        uid = uuid.uuid4().hex
        session["uid"] = uid
        ts = now_ms()
        ActiveSession.objects.create(
            uid=uid,
            code=session["code"],
            role=session["role"],
            stationId=session.get("stationId"),
            nodeId=session.get("nodeId"),
            displayName=session.get("displayName"),
            staffVaultFullName=session["displayName"]
            if session["role"] == "worker"
            else None,
            createdAt=ts,
            lastSeen=ts,
        )

        SecurityEvent.objects.create(
            type="successful_login", code=code, deviceId=device_id, timestamp=ts
        )

        result = create_access_token(session)
        result["session"]["uid"] = uid
        result["session"]["displayName"] = session["displayName"]
        return Response(result, status=status.HTTP_200_OK)


class HeartbeatView(APIView):
    """POST /api/auth/heartbeat — presence lastSeen yangilash."""

    def post(self, request):
        uid = getattr(request.user, "uid", "")
        if uid:
            ActiveSession.objects.filter(pk=uid).update(lastSeen=now_ms())
        return Response({"ok": True})


class LogoutView(APIView):
    """POST /api/auth/logout — presence sessiyani o'chirish."""

    def post(self, request):
        uid = getattr(request.user, "uid", "")
        if uid:
            ActiveSession.objects.filter(pk=uid).delete()
        return Response({"ok": True})


class VaultCheckView(APIView):
    """POST /api/auth/vault-check  { password } -> { ok: True } | 403

    "Admin qo'shish" bo'limining qo'shimcha paroli. Parol serverda qoladi —
    frontendga na o'zi, na hash'i yuborilmaydi, shu sababli uni offline
    brute-force qilib bo'lmaydi. Asosiy chegara baribir rol tekshiruvi
    (`IsAdmin`, `AccessCodeViewSet` da ham) bo'lib qoladi; bu endpoint uning
    ustiga qo'yilgan ikkinchi qatlam.
    """

    permission_classes = [IsAdmin]
    throttle_classes = [VaultThrottle]

    def post(self, request):
        password = str(request.data.get("password", ""))

        expected_hash = getattr(settings, "ADMIN_VAULT_PASSWORD_HASH", "")
        if expected_hash:
            ok = check_password(password, expected_hash)
        else:
            ok = secrets.compare_digest(password, settings.ADMIN_VAULT_PASSWORD)

        if not ok:
            # Xato urinish yozib boriladi. `SecurityEvent.type` da yangi qiymat
            # qo'shish migratsiya talab qilardi — shuning uchun mavjud
            # "wrong_code" ishlatiladi, tafsilot `meta` da ko'rsatiladi.
            SecurityEvent.objects.create(
                type="wrong_code",
                code=getattr(request.user, "code", "") or "",
                deviceId=str(request.data.get("deviceId", "")).strip(),
                timestamp=now_ms(),
                meta={"scope": "admin_vault"},
            )
            return Response(
                {"detail": "Parol xato."}, status=status.HTTP_403_FORBIDDEN
            )

        return Response({"ok": True}, status=status.HTTP_200_OK)


class MeView(APIView):
    """GET /api/auth/me — joriy sessiya ma'lumoti."""

    def get(self, request):
        p = request.user
        return Response(
            {
                "code": p.code,
                "role": p.role,
                "stationId": p.stationId,
                "nodeId": p.nodeId,
                "displayName": p.displayName,
                "codeType": p.codeType,
                "uid": p.uid,
            }
        )


# ── CRUD viewsetlar (admin boshqaruvi) ──────────────────────────────────────
class AccessCodeViewSet(viewsets.ModelViewSet):
    queryset = AccessCode.objects.all()
    serializer_class = AccessCodeSerializer
    # "Бошқарув" bo'limi: bo'limi cheklangan admin bu yerga umuman kira olmaydi,
    # aks holda u o'ziga istalgan huquqni yozib qo'ya olardi.
    permission_classes = [IsAdmin, IsUnrestrictedAdmin]
    filterset_fields = ["role", "codeType", "isActive"]
    search_fields = ["code", "displayName"]

    def perform_update(self, serializer):
        serializer.save(updatedAt=now_ms())


class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.all()
    serializer_class = StaffSerializer
    # O'qish ochiq (worker/operator oqimlari shunga tayanadi); xodim qo'shish /
    # o'zgartirish faqat "Ходим қўшиш" bo'limi biriktirilgan adminga.
    permission_classes = [IsAdminOrReadOnly, section_required("xodim")]
    filterset_fields = ["erju", "zapravka", "stationId", "role"]
    search_fields = ["tabelNumber", "fullName", "zapravka"]


class BlockedCodeViewSet(viewsets.ModelViewSet):
    queryset = BlockedCode.objects.all()
    serializer_class = BlockedCodeSerializer
    # Butunlay "Ходим қўшиш" bo'limiga tegishli — o'qish ham cheklanadi.
    permission_classes = [IsAdmin, section_required("xodim", writes_only=False)]
    search_fields = ["code", "note"]


class ActiveSessionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ActiveSession.objects.all()
    serializer_class = ActiveSessionSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ["role", "stationId", "nodeId"]


class SecurityEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SecurityEvent.objects.all()
    serializer_class = SecurityEventSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ["type", "code", "deviceId"]


class DeviceLockViewSet(viewsets.ModelViewSet):
    queryset = DeviceLock.objects.all()
    serializer_class = DeviceLockSerializer
    permission_classes = [IsAdmin]
