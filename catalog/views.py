from rest_framework import viewsets

from accounts.permissions import IsAdminOrReadOnly, section_required

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
from .serializers import (
    ApprovalSerializer,
    ClosedDaySerializer,
    LimitSerializer,
    QuestionSerializer,
    SettingSerializer,
    UzelSerializer,
    VariantSerializer,
    ZapravkaSerializer,
)


class UzelViewSet(viewsets.ModelViewSet):
    queryset = Uzel.objects.all()
    serializer_class = UzelSerializer
    permission_classes = [IsAdminOrReadOnly]


class ZapravkaViewSet(viewsets.ModelViewSet):
    queryset = Zapravka.objects.all()
    serializer_class = ZapravkaSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["uzelId"]


class SettingViewSet(viewsets.ModelViewSet):
    queryset = Setting.objects.all()
    serializer_class = SettingSerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_value_regex = "[^/]+"

    # ── Депо лимити: қўшимча -> асосийга қўшилиши ───────────────────────────
    # `depoLimits` ёки `depoQoshimchaLimits` ҳужжатига ёзилганда базадаги
    # жами лимит қайта ҳисобланади (`catalog/depo_limits.py`). Бошқа
    # `settings/*` ҳужжатларига мутлақо тегилмайди.
    def _sync_depo_limits(self, key) -> None:
        from .depo_limits import SYNC_KEYS, sync_depo_limits

        if str(key or "") not in SYNC_KEYS:
            return
        sync_depo_limits()

    def perform_create(self, serializer):
        obj = serializer.save()
        self._sync_depo_limits(getattr(obj, "pk", None))

    def perform_update(self, serializer):
        obj = serializer.save()
        self._sync_depo_limits(getattr(obj, "pk", None))

    def perform_destroy(self, instance):
        key = instance.pk
        instance.delete()
        self._sync_depo_limits(key)


class QuestionViewSet(viewsets.ModelViewSet):
    """`subscribeToQuestions` ekvivalenti — category bo'yicha filtr, global savollar ham."""

    serializer_class = QuestionSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["category", "stationId", "fieldKey"]

    def get_queryset(self):
        qs = Question.objects.all()
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        station_id = self.request.query_params.get("stationId")
        if station_id:
            # global (stationId bo'sh) yoki shu stansiyaga tegishli
            from django.db.models import Q

            qs = qs.filter(Q(stationId="") | Q(stationId=station_id))
        return qs.order_by("category", "order")

    def perform_update(self, serializer):
        from common.timeutil import now_ms

        serializer.save(updatedAt=now_ms())


class VariantViewSet(viewsets.ModelViewSet):
    queryset = Variant.objects.all()
    serializer_class = VariantSerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_value_regex = "[^/]+"


class LimitViewSet(viewsets.ModelViewSet):
    queryset = Limit.objects.all()
    serializer_class = LimitSerializer
    # O'qish ochiq (worker formalari limitni o'qiydi); limit yozish/o'zgartirish
    # faqat "Лимит бериш" bo'limi biriktirilgan adminga.
    permission_classes = [IsAdminOrReadOnly, section_required("limit")]
    filterset_fields = ["type", "stationId", "isActive"]

    def perform_update(self, serializer):
        from common.timeutil import now_ms

        serializer.save(updatedAt=now_ms())


class ClosedDayViewSet(viewsets.ModelViewSet):
    queryset = ClosedDay.objects.all()
    serializer_class = ClosedDaySerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_value_regex = "[^/]+"


class ApprovalViewSet(viewsets.ModelViewSet):
    queryset = Approval.objects.all()
    serializer_class = ApprovalSerializer
    permission_classes = [IsAdminOrReadOnly, section_required("limit")]
