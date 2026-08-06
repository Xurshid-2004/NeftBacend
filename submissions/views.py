"""
Submission API — firestore.rules bilan bir xil ruxsatlar:
  * worker faqat o'z stationId si uchun yozadi/o'qiydi;
  * tahrirlash faqat o'sha kun ichida (canEdit), admin istalgan vaqt;
  * o'chirish faqat admin.
"""

from __future__ import annotations

from datetime import datetime

from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAuthenticated
from common.numbers import parse_pdf_number
from common.timeutil import now_ms
from operators.services import change_balance as change_operator_balance
from operators.services import subtract as subtract_operator_balance
from operators.services import write_audit as write_operator_audit

from .models import DailySummary, FuelRecord, KorxonaWorkerCode, Submission, YearlySummary
from .serializers import (
    DailySummarySerializer,
    FuelRecordSerializer,
    KorxonaWorkerCodeSerializer,
    SubmissionSerializer,
    YearlySummarySerializer,
)
from .services import create_submission, delete_submission, update_submission


def _is_admin(user) -> bool:
    return bool(getattr(user, "is_admin", False))


# Har bir kategoriyada "berilgan yoqilg'i" qaysi maydonda kelishi — operator
# balansidan shu miqdor ayiriladi.
#
# Ilgari faqat `lokomotiv` shu yerda (serverda) ayirilardi; korxona/qurulish/
# tamirlash esa brauzerdan alohida `POST /operator/subtract/` so'rovi bilan
# ayirilardi. U so'rov "fire-and-forget" edi: tarmoq uzilsa yoki bet yopilsa
# yozuv saqlanib, yoqilg'i esa hech qachon ayirilmay qolardi (balans faqat
# brauzerda kamayib, keyingi poll uni tiklardi). Endi TO'RTALA kategoriya ham
# yozuv bilan bir joyda, serverda ayiriladi — brauzerga bog'liq emas.
_FUEL_FIELD_BY_CATEGORY = {
    "lokomotiv": "qanchaBerildi",
    "korxona": "qancha",
    "qurulish": "qanchaBerildi",
    "tamirlash": "qanchaBerildi",
}


def _fuel_amount_of(sub: Submission) -> float:
    """Yozuvda berilgan yoqilg'i (kg) — kategoriyasiga mos maydondan."""
    field = _FUEL_FIELD_BY_CATEGORY.get(sub.category)
    if not field:
        return 0.0
    return parse_pdf_number(getattr(sub, field, None))


def _sync_balance_after_edit(
    old_station: str, old_amount: float, old_counted: bool, sub: Submission, actor: dict
) -> None:
    """Yozuv tahrirlangach operator balansini to'g'rilaydi.

    Ilgari tahrirlash balansga UMUMAN ta'sir qilmasdi: miqdor 100 dan 150 ga
    o'zgartirilsa ham balansdan avvalgidek 100 ayirilgan holicha qolardi va
    kunlar o'tgani sari hisobot bilan tank qoldig'i bir-biridan uzoqlashardi.

    Qoida yozuv YARATILGANDAGI qoida bilan AYNAN bir xil: balansga faqat joriy
    kunga tegishli yozuv ta'sir qiladi (`_is_backdated`). Shundan:
      * oldin ham, keyin ham bugungi bo'lsa  -> faqat FARQ qo'llanadi,
      * bugungidan o'tgan kunga ko'chirilsa  -> eski miqdor balansga QAYTADI,
      * o'tgan kundan bugunga ko'chirilsa    -> yangi miqdor balansdan ayiriladi,
      * ikkalasi ham o'tgan kun bo'lsa       -> balansga umuman tegilmaydi.

    Stansiya yoki kategoriya o'zgarsa (buni faqat admin qila oladi) ham to'g'ri
    ishlaydi: hisob eski stansiyaga qaytariladi, yangisidan ayiriladi. Bitta
    stansiya uchun kirim va chiqim AVVAL yig'iladi, keyin bitta amalda
    qo'llanadi — oraliqda balans 0 ga urilib qolmasligi uchun.
    """
    new_station = sub.stationId
    new_amount = _fuel_amount_of(sub)
    new_counted = not _is_backdated(sub)

    deltas: dict[str, float] = {}
    if old_counted and old_station:
        deltas[old_station] = deltas.get(old_station, 0.0) + old_amount
    if new_counted and new_station:
        deltas[new_station] = deltas.get(new_station, 0.0) - new_amount

    for station_id, delta in deltas.items():
        if abs(delta) < 1e-9:
            continue
        try:
            state = change_operator_balance(station_id, delta)
        except Exception as exc:  # noqa: BLE001 — balans xatosi tahrirni buzmasin
            import logging

            logging.getLogger(__name__).warning(
                "tahrirdan keyin operator balansi to'g'rilanmadi "
                "(stansiya=%s, delta=%s, yozuv=%s): %s",
                station_id,
                delta,
                sub.pk,
                exc,
            )
            continue

        write_operator_audit(
            actor,
            "update",
            "operator_balance",
            station_id,
            {
                "amal": "yozuv tahrirlandi",
                "yozuvId": str(sub.pk),
                "kategoriya": sub.category,
                "eskiMiqdorKg": old_amount if old_counted else None,
                "yangiMiqdorKg": new_amount if new_counted else None,
                "balansgaQoshildiKg": delta,
                "yangiBalansKg": (state or {}).get("balanceKg"),
            },
        )


def _is_backdated(sub: Submission) -> bool:
    """
    Yozuv joriy kundan boshqa kunga tushganmi (ya'ni sana override ishlatilgan).

    Operator balansini himoya qilish uchun kerak: balans "hozirgi qoldiq" ni
    bildiradi va `delete_submission` uni QAYTARMAYDI. Shu sababli o'tgan kunga
    kiritilgan yozuv balansdan ayirilsa, o'sha yozuvni o'chirib ham qoldiqni
    tiklab bo'lmasdi. Joriy kunga yoziladigan oddiy yozuvlar uchun bu funksiya
    `False` qaytaradi — ular avvalgidek balansdan ayiriladi.
    """
    from common.timeutil import now_local, to_local_date_iso

    if not sub.dateISO:
        return False
    return sub.dateISO != to_local_date_iso(now_local())


def _can_edit(sub: Submission) -> bool:
    """submissions-service.ts -> canEdit: faqat shu kun (mahalliy)."""
    from django.utils import timezone

    now = timezone.localtime(timezone.now())
    ms = sub.timestamp or sub.timestampMs
    if not ms:
        return False
    sub_date = datetime.fromtimestamp(ms / 1000)
    return (now.year, now.month, now.day) == (
        sub_date.year,
        sub_date.month,
        sub_date.day,
    )


class SubmissionViewSet(viewsets.ModelViewSet):
    serializer_class = SubmissionSerializer
    filterset_fields = ["stationId", "category", "dateISO", "year", "harakatTuri", "isOverLimit", "depo"]
    ordering_fields = ["timestamp", "createdAt"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        qs = Submission.objects.all()
        user = self.request.user
        if not _is_admin(user):
            # worker faqat o'z stansiyasi
            qs = qs.filter(stationId=user.stationId or "")
        # timestamp (ms) oralig'i — hisobotlar/dashboard uchun
        start_ms = self.request.query_params.get("startMs")
        end_ms = self.request.query_params.get("endMs")
        if start_ms:
            qs = qs.filter(timestamp__gte=int(start_ms))
        if end_ms:
            qs = qs.filter(timestamp__lte=int(end_ms))
        return qs

    def create(self, request, *args, **kwargs):
        data = dict(request.data)
        user = request.user
        category = data.get("category") or request.query_params.get("category")
        if category not in ("lokomotiv", "korxona", "qurulish", "tamirlash"):
            raise ValidationError({"category": "lokomotiv|korxona|qurulish|tamirlash"})

        # worker faqat o'z stansiyasiga yozadi
        if not _is_admin(user):
            data["stationId"] = user.stationId
            data["nodeId"] = user.nodeId
            data.setdefault("staffCode", user.code)
            data.setdefault("staffName", user.displayName)
        if not data.get("stationId"):
            raise ValidationError({"stationId": "majburiy"})

        # ТЯГА — «Локомотив рақами» faqat ruxsat etilgan ro'yxatdan bo'lishi
        # kerak. Tekshiruv frontendda ham bor, lekin asosiysi shu yerda:
        # so'rovni to'g'ridan-to'g'ri API ga yuborib chetlab o'tib bo'lmaydi.
        # Ro'yxat bo'sh bo'lsa `is_raqam_allowed` doim True qaytaradi, ya'ni
        # sozlama yo'q bo'lsa yozuvlar avvalgidek saqlanaveradi.
        if category == "lokomotiv":
            from catalog.lokomotiv_raqamlar import is_raqam_allowed

            if not is_raqam_allowed(data.get("lokomotivNumber")):
                raise ValidationError(
                    {"lokomotivNumber": "Бундай локомотив рақами рўйхатда йўқ"}
                )

        # Hisobot sanasi override — admin doim, worker esa VAQTINCHALIK
        # `ALLOW_WORKER_REPORT_DATE_OVERRIDE` yoqilganda (navbardagi sana
        # tanlagichi). Bayroq o'chirilsa avvalgi holat qaytadi: faqat admin.
        override = data.pop("reportDateOverride", None)
        if not (_is_admin(user) or settings.ALLOW_WORKER_REPORT_DATE_OVERRIDE):
            override = None

        sub = create_submission(category, data, report_date_override=override)

        # Operator balansi FAQAT joriy kunga yozilgan yozuvda kamayadi.
        # O'tgan kunga kiritilgan yozuv (sana override) balansga umuman
        # tegmaydi — sabab `_is_backdated` izohida. Bugungi kunga yoziladigan
        # oddiy yozuvlar uchun bu shart har doim rost, ya'ni xatti-harakat
        # avvalgidek qoladi.
        fuel_field = _FUEL_FIELD_BY_CATEGORY.get(category)
        if fuel_field and not _is_backdated(sub):
            try:
                subtract_operator_balance(sub.stationId, data.get(fuel_field))
            except Exception as exc:  # noqa: BLE001 — balans xatosi submissionni buzmasin
                import logging

                logging.getLogger(__name__).warning("operator balansi ayirilmadi: %s", exc)

        ser = self.get_serializer(sub)
        return Response(ser.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        sub = self.get_object()
        user = request.user
        if not _is_admin(user) and not _can_edit(sub):
            raise PermissionDenied("Tahrirlash muddati tugagan (faqat shu kun).")

        # Balansni to'g'rilash uchun tahrirdan OLDINGI holat (yozuv o'zgargach
        # bu qiymatlarni olib bo'lmaydi — shuning uchun hozir saqlab qolamiz).
        old_station = sub.stationId
        old_amount = _fuel_amount_of(sub)
        old_counted = not _is_backdated(sub)

        changes = dict(request.data)
        changes.pop("reportDateOverride", None)
        if not _is_admin(user):
            # worker stationId/category ni o'zgartira olmaydi
            changes.pop("stationId", None)
            changes.pop("category", None)
        changes["isEdited"] = True
        from common.timeutil import now_ms

        changes["editedAt"] = now_ms()

        sub = update_submission(sub, changes)

        # Miqdor o'zgargan bo'lsa — operator balansi ham shunga yarasha
        # to'g'rilanadi (farq qancha bo'lsa, shuncha). Xatosi tahrirni buzmaydi.
        _sync_balance_after_edit(
            old_station,
            old_amount,
            old_counted,
            sub,
            {
                "userId": getattr(user, "code", "") or "",
                "userName": getattr(user, "displayName", "") or "",
                "userRole": getattr(user, "role", "") or "",
            },
        )

        return Response(self.get_serializer(sub).data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not _is_admin(request.user):
            raise PermissionDenied("O'chirish faqat admin uchun.")
        sub = self.get_object()
        delete_submission(sub)
        return Response(status=status.HTTP_204_NO_CONTENT)


class FuelRecordViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FuelRecordSerializer
    filterset_fields = ["locCode", "dateISO", "year", "moveType"]
    ordering = ["-createdAt"]

    def get_queryset(self):
        qs = FuelRecord.objects.all()
        user = self.request.user
        if not _is_admin(user):
            qs = qs.filter(locCode=user.stationId or "")
        # date (YYYY-MM-DD) oralig'i — hisobotlar uchun
        date_from = self.request.query_params.get("dateFrom")
        date_to = self.request.query_params.get("dateTo")
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return qs


class DailySummaryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailySummary.objects.all()
    serializer_class = DailySummarySerializer
    filterset_fields = ["stationId", "category", "dateISO", "year"]


class YearlySummaryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = YearlySummary.objects.all()
    serializer_class = YearlySummarySerializer
    filterset_fields = ["stationId", "category", "year"]


class KorxonaWorkerCodeListView(APIView):
    """
    Worker panel — korxona forma: har bir worker o'zi biriktirgan qidiruv
    raqamlarini shu yerdan o'qiydi/yozadi. Har doim JWT'dagi `staffCode`
    (token egasi) bo'yicha ishlaydi — boshqa workerning yozuvlarini na ko'radi,
    na o'zgartira oladi.

    GET  /api/korxona-worker-codes/ -> joriy workerning barcha (nom -> raqam) juftliklari
    POST /api/korxona-worker-codes/ -> bitta juftlikni yaratadi/yangilaydi;
         `code` bo'sh yuborilsa — o'sha nom uchun biriktirilgan raqam o'chiriladi
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        staff_code = getattr(request.user, "code", "") or ""
        qs = KorxonaWorkerCode.objects.filter(staffCode=staff_code)
        return Response(KorxonaWorkerCodeSerializer(qs, many=True).data)

    def post(self, request):
        staff_code = getattr(request.user, "code", "") or ""
        korxona_nomi = str(request.data.get("korxonaNomi") or "").strip()
        code = str(request.data.get("code") or "").strip()
        if not staff_code or not korxona_nomi:
            raise ValidationError({"korxonaNomi": "majburiy"})

        if not code:
            KorxonaWorkerCode.objects.filter(staffCode=staff_code, korxonaNomi=korxona_nomi).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        obj, _ = KorxonaWorkerCode.objects.update_or_create(
            staffCode=staff_code,
            korxonaNomi=korxona_nomi,
            defaults={"code": code, "updatedAt": now_ms()},
        )
        return Response(KorxonaWorkerCodeSerializer(obj).data, status=status.HTTP_201_CREATED)
