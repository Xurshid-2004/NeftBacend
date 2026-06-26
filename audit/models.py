"""`audit_logs` — o'zgarmas audit izi (AuditLog)."""

from django.db import models

from common.timeutil import now_ms


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("create", "create"),
        ("update", "update"),
        ("delete", "delete"),
    ]
    userId = models.CharField(max_length=64, blank=True, default="", db_index=True)
    userName = models.CharField(max_length=200, blank=True, default="")
    userRole = models.CharField(max_length=16, blank=True, default="")
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)
    entityType = models.CharField(max_length=64, db_index=True)
    entityId = models.CharField(max_length=160, blank=True, default="")
    changes = models.JSONField(default=dict, blank=True)
    timestamp = models.BigIntegerField(default=now_ms, db_index=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.action} {self.entityType}/{self.entityId}"
