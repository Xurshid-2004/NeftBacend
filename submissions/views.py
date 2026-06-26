"""
Submission API — firestore.rules bilan bir xil ruxsatlar:
  * worker faqat o'z stationId si uchun yozadi/o'qiydi;
  * tahrirlash faqat o'sha kun ichida (canEdit), admin istalgan vaqt;
  * o'chirish faqat admin.
"""

from __future__ import annotations

from datetime import datetime

from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .models import DailySummary, FuelRecord, Submission, YearlySummary
from .serializers import (
    DailySummarySerializer,
    FuelRecordSerializer,
    SubmissionSerializer,
    YearlySummarySerializer,
)
from .services import create_submission, delete_submission, update_submission


def _is_admin(user) -> bool:
    return bool(getattr(user, "is_admin", False))


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
    filterset_fields = ["stationId", "category", "dateISO", "year", "harakatTuri", "isOverLimit"]
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

        # Hisobot sanasi override (faqat admin)
        override = None
        if _is_admin(user):
            override = data.pop("reportDateOverride", None)
        else:
            data.pop("reportDateOverride", None)

        sub = create_submission(category, data, report_date_override=override)
        ser = self.get_serializer(sub)
        return Response(ser.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        sub = self.get_object()
        user = request.user
        if not _is_admin(user) and not _can_edit(sub):
            raise PermissionDenied("Tahrirlash muddati tugagan (faqat shu kun).")

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
