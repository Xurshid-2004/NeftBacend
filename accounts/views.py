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

FACE ID (POST /api/auth/face-login/)
────────────────────────────────────
Yuz bo'yicha kirish AYNAN shu tartibga qo'shiladi, uni chetlab o'tmaydi:
kamera kadrlari -> server yuzni taniydi -> topilgan KOD yuqoridagi 0-3
qadamlardan xuddi parol kiritilgandek o'tadi (`_build_admin_session` /
`_build_staff_session`, bloklangan kod tekshiruvi, ActiveSession, JWT).
Ya'ni Face ID yangi huquq yo'li ochmaydi — u faqat "kodni yozish" qadamini
almashtiradi. Yuz topilmasa qurilmaning parol urinishlari hisobi
O'ZGARMAYDI, chunki foydalanuvchi baribir parol bilan kira olishi kerak.
"""

from __future__ import annotations

import secrets
import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.db.models import BooleanField, Case, Exists, OuterRef, Q, Value, When
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.utils import resolve_zapravka
from common.timeutil import now_ms

from . import face, face_service
from .authentication import create_access_token
from .models import (
    AccessCode,
    ActiveSession,
    BlockedCode,
    DeviceLock,
    FaceTemplate,
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
from .throttles import FaceThrottle, VaultThrottle
from .serializers import (
    AccessCodeSerializer,
    ActiveSessionSerializer,
    BlockedCodeSerializer,
    DeviceLockSerializer,
    FaceLoginSerializer,
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


def _finalize_login(
    session: dict,
    code: str,
    device_id: str,
    device_lock: DeviceLock | None,
    meta: dict | None = None,
) -> dict:
    """Sessiyani yakunlash: qurilma hisobini tozalash, presence, JWT.

    Parol bilan kirish ham, Face ID ham AYNAN shu funksiyadan o'tadi — shunda
    ikkala yo'l bir xil sessiya/JWT/presence yozuvini hosil qiladi va kelajakda
    ular bir-biridan "ajralib" ketmaydi.
    """
    # To'g'ri kirildi — shu qurilmaning oldingi xato hisobini tozalaymiz.
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
        type="successful_login",
        code=code,
        deviceId=device_id,
        timestamp=ts,
        meta=meta,
    )

    result = create_access_token(session)
    result["session"]["uid"] = uid
    result["session"]["displayName"] = session["displayName"]
    return result


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

        result = _finalize_login(session, code, device_id, device_lock)
        return Response(result, status=status.HTTP_200_OK)


# ── Face ID ─────────────────────────────────────────────────────────────────
# Qurilma bo'yicha "sovish" (cooldown): ketma-ket shuncha marta yuz topilmasa,
# shu qurilmada Face ID vaqtincha o'chadi va foydalanuvchi parol bilan kiradi.
# DIQQAT: bu DeviceLock EMAS — parol bilan kirish yo'li ochiq qoladi.
_FACE_FAIL_KEY = "face:fail:%s"
_FACE_COOL_KEY = "face:cool:%s"


def _face_ident(request, device_id: str) -> str:
    return device_id or (request.META.get("REMOTE_ADDR") or "anon")


def _face_cooldown_left(ident: str) -> int:
    until = cache.get(_FACE_COOL_KEY % ident)
    if not until:
        return 0
    left = int(until) - int(now_ms() / 1000)
    return left if left > 0 else 0


def _face_register_failure(ident: str) -> None:
    cfg = face_service.config()
    limit = int(cfg.get("DEVICE_FAILS", 6) or 6)
    window = int(cfg.get("DEVICE_COOLDOWN_SEC", 300) or 300)
    key = _FACE_FAIL_KEY % ident
    fails = int(cache.get(key) or 0) + 1
    cache.set(key, fails, timeout=window)
    if fails >= limit:
        cache.set(
            _FACE_COOL_KEY % ident,
            int(now_ms() / 1000) + window,
            timeout=window,
        )
        cache.delete(key)


def _face_clear_failures(ident: str) -> None:
    cache.delete(_FACE_FAIL_KEY % ident)
    cache.delete(_FACE_COOL_KEY % ident)


def _face_global_gate() -> bool:
    """Butun server bo'yicha daqiqalik chegara (CPU himoyasi).

    Bitta yuz tekshiruvi ~0.2-0.5 soniya protsessor vaqti oladi. Ko'p IP dan
    bir vaqtda so'rov kelsa server "band" bo'lib qolishi mumkin edi — bu
    chegara shuni oldini oladi. Oddiy foydalanuvchiga sezilmaydi (daqiqada
    o'nlab kirish), parol bilan kirish esa umuman cheklanmaydi.
    """
    limit = int(getattr(settings, "FACE_ID", {}).get("GLOBAL_PER_MIN", 90) or 90)
    key = "face:global:%d" % int(now_ms() / 60000)
    try:
        count = cache.get_or_set(key, 0, timeout=120)
        count = cache.incr(key)
    except ValueError:
        # Kalit shu orada eskirgan bo'lsa — yangidan boshlanadi.
        cache.set(key, 1, timeout=120)
        count = 1
    return count <= limit


class FaceStatusView(APIView):
    """GET /api/auth/face-status — login sahifasi tugmani ko'rsatsinmi?

    Faqat ikki bayroq qaytaradi, hech qanday shaxsiy ma'lumot yo'q.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "anon"

    def get(self, request):
        enabled = face_service.is_enabled()
        ready = enabled and FaceTemplate.objects.exists()
        return Response({"enabled": enabled, "ready": ready})


class FaceLoginView(APIView):
    """POST /api/auth/face-login  { samples: [...], deviceId? } -> login javobi.

    Javob shakli `/api/auth/login/` bilan AYNAN bir xil ({token, session}),
    shuning uchun frontend ikkala yo'lda ham bitta sessiya kodidan foydalanadi.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [FaceThrottle]

    def post(self, request):
        if not face_service.is_enabled():
            return Response(
                {"detail": "Face ID o'chirilgan. Parol bilan kiring.", "reason": "disabled"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = FaceLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device_id = str(serializer.validated_data.get("deviceId", "")).strip()

        device_lock = (
            DeviceLock.objects.filter(pk=device_id).first() if device_id else None
        )
        if device_lock and device_lock.isBlocked:
            return Response(
                {"detail": "Bu qurilma bloklangan. Administratorga murojaat qiling."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not _face_global_gate():
            return Response(
                {
                    "detail": "Tizim hozir band. Bir oz kuting yoki parol bilan kiring.",
                    "reason": "busy",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        ident = _face_ident(request, device_id)
        left = _face_cooldown_left(ident)
        if left > 0:
            return Response(
                {
                    "detail": f"Face ID vaqtincha o'chirildi ({left} soniya). Parol bilan kiring.",
                    "reason": "cooldown",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            samples = face_service.parse_samples(
                serializer.validated_data.get("samples"),
                face_service.MAX_LOGIN_FRAMES,
            )
        except face_service.FaceError as exc:
            return Response(
                {"detail": str(exc), "reason": "bad_sample"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not samples:
            return Response(
                {"detail": "Yuz kadri yuborilmadi.", "reason": "bad_sample"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if face.samples_are_replay(samples):
            # Bir xil kadr qayta-qayta yuborilgan — jonli kamera emas.
            _face_register_failure(ident)
            SecurityEvent.objects.create(
                type="wrong_code",
                code="",
                deviceId=device_id,
                timestamp=now_ms(),
                meta={"scope": "face", "reason": "replay"},
            )
            return Response(
                {"detail": "Kamera tasviri qabul qilinmadi. Qaytadan urinib ko'ring.",
                 "reason": "replay"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        enrolled = face_service.load_enrolled()
        result = face.identify(samples, enrolled, face_service.thresholds())
        matched_code = result.get("code")

        session = None
        if matched_code:
            session = _build_admin_session(matched_code) or _build_staff_session(
                matched_code
            )

        if not session:
            # Yuz topilmadi (yoki shablon eskirgan — xodim o'chirilgan/kodi o'zgargan).
            # MUHIM: DeviceLock.attempts KO'PAYTIRILMAYDI — parol bilan kirish
            # imkoniyati saqlanib qolishi shart.
            _face_register_failure(ident)
            SecurityEvent.objects.create(
                type="wrong_code",
                code=matched_code or "",
                deviceId=device_id,
                timestamp=now_ms(),
                meta={
                    "scope": "face",
                    "reason": "stale" if matched_code else result.get("reason"),
                    "d": result.get("distance"),
                    "second": result.get("second"),
                    "z": result.get("z"),
                    "cohort": result.get("cohort"),
                },
            )
            return Response(
                {
                    "detail": "Yuz tanilmadi. Qaytadan urinib ko'ring yoki parol kiriting.",
                    "reason": result.get("reason") or "no_match",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if BlockedCode.objects.filter(pk=matched_code).exists():
            SecurityEvent.objects.create(
                type="device_locked",
                code=matched_code,
                deviceId=device_id,
                timestamp=now_ms(),
                meta={"scope": "face"},
            )
            return Response(
                {"detail": "Bu kirish kodi bloklangan. Administratorga murojaat qiling."},
                status=status.HTTP_403_FORBIDDEN,
            )

        _face_clear_failures(ident)
        face_service.mark_matched(matched_code)
        payload = _finalize_login(
            session,
            matched_code,
            device_id,
            device_lock,
            meta={"via": "face", "d": result.get("distance"), "z": result.get("z")},
        )
        return Response(payload, status=status.HTTP_200_OK)


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

    def get_queryset(self):
        # `hasPhoto` / `hasFace` — bitta so'rovda hisoblanadi (N+1 so'rov yo'q).
        queryset = Staff.objects.all().annotate(
            _has_photo=Case(
                When(Q(photo="") | Q(photo__isnull=True), then=Value(False)),
                default=Value(True),
                output_field=BooleanField(),
            ),
            _has_face=Exists(
                FaceTemplate.objects.filter(code=OuterRef("tabelNumber"))
            ),
        )
        if self.action == "list":
            # Ro'yxatga surat matni UMUMAN tortilmaydi — javob hajmi avvalgidek.
            queryset = queryset.defer("photo")
        return queryset

    @action(detail=True, methods=["get"], permission_classes=[IsAdmin])
    def photo(self, request, pk=None):
        """GET /api/staff/{id}/photo/ — bitta xodim surati (faqat admin).

        Surat ro'yxatda kelmaydi, chunki 100 ta xodimda javob bir necha MB
        bo'lib ketardi va har 60 soniyalik polling'da qayta yuklanardi.
        """
        staff = self.get_object()
        return Response(
            {
                "id": str(staff.pk),
                "photo": staff.photo or "",
                "photoUpdatedAt": staff.photoUpdatedAt,
            }
        )

    def perform_destroy(self, instance):
        code = (instance.tabelNumber or "").strip()
        super().perform_destroy(instance)
        # Xodim o'chirilsa, uning Face ID shabloni ham qolmasin.
        face_service.remove(code)


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
