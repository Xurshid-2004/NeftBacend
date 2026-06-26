from common.drf import MsModelSerializer

from .models import AuditLog


class AuditLogSerializer(MsModelSerializer):
    class Meta:
        model = AuditLog
        fields = "__all__"
        read_only_fields = ["timestamp"]
