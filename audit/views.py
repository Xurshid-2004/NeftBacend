"""
Audit API — firestore.rules: yaratish istalgan autentifikatsiyalangan,
o'qish faqat admin, yangilash/o'chirish taqiqlangan (o'zgarmas iz).
"""

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdmin
from common.timeutil import now_ms

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    filterset_fields = ["userId", "entityType", "action"]
    ordering = ["-timestamp"]

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdmin()]

    def perform_create(self, serializer):
        serializer.save(timestamp=now_ms())
