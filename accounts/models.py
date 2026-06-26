"""
Auth / sessiya / xavfsizlik modellari.

Firestore kolleksiyalari bilan moslik:
  access_codes      -> AccessCode   (PK = code)
  staff             -> Staff
  blocked_codes     -> BlockedCode  (PK = code)
  active_sessions   -> ActiveSession (PK = uid)  — onlayn presence uchun
  security_events   -> SecurityEvent
  device_locks      -> DeviceLock   (PK = deviceId)

Maydon nomlari frontend TS interfeyslari bilan AYNAN bir xil (camelCase),
shuning uchun API javoblari Firestore hujjatlari bilan mos keladi.
"""

from django.db import models

from common.timeutil import now_ms

ROLE_CHOICES = [
    ("worker", "worker"),
    ("admin", "admin"),
    ("developer", "developer"),
]


class AccessCode(models.Model):
    """`access_codes/{code}` — admin/developer kirish kodlari."""

    code = models.CharField(max_length=64, primary_key=True)
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="admin")
    displayName = models.CharField(max_length=200, blank=True, default="")
    nodeId = models.CharField(max_length=64, null=True, blank=True)
    stationId = models.CharField(max_length=64, null=True, blank=True)
    codeType = models.CharField(
        max_length=16,
        choices=[("admin", "admin"), ("developer", "developer")],
        default="admin",
    )
    isActive = models.BooleanField(default=True)
    createdAt = models.BigIntegerField(default=now_ms)
    updatedAt = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "access_codes"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} ({self.role})"


class Staff(models.Model):
    """`staff` — tabel raqam bo'yicha worker login (StaffVaultRecord)."""

    erju = models.CharField(max_length=120, blank=True, default="")
    zapravka = models.CharField(max_length=120, blank=True, default="")
    tabelNumber = models.CharField(max_length=64, db_index=True)
    fullName = models.CharField(max_length=200, blank=True, default="")
    role = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        choices=[("worker", "worker"), ("operator", "operator")],
    )
    stationId = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        db_table = "staff"
        ordering = ["tabelNumber"]

    def __str__(self):
        return f"{self.tabelNumber} — {self.fullName}"


class BlockedCode(models.Model):
    """`blocked_codes/{code}` — bloklangan kirish kodlari."""

    code = models.CharField(max_length=64, primary_key=True)
    note = models.CharField(max_length=300, blank=True, default="")
    blockedAt = models.BigIntegerField(default=now_ms)
    blockedByDisplayName = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        db_table = "blocked_codes"
        ordering = ["-blockedAt"]

    def __str__(self):
        return self.code


class ActiveSession(models.Model):
    """`active_sessions/{uid}` — onlayn presence (heartbeat)."""

    uid = models.CharField(max_length=128, primary_key=True)
    code = models.CharField(max_length=64, blank=True, default="")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="worker")
    stationId = models.CharField(max_length=64, null=True, blank=True)
    nodeId = models.CharField(max_length=64, null=True, blank=True)
    displayName = models.CharField(max_length=200, null=True, blank=True)
    staffVaultFullName = models.CharField(max_length=200, null=True, blank=True)
    createdAt = models.BigIntegerField(default=now_ms)
    lastSeen = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "active_sessions"
        ordering = ["-lastSeen"]

    def __str__(self):
        return f"{self.uid} — {self.code}"


class SecurityEvent(models.Model):
    """`security_events` — login urinishlari / bloklash hodisalari."""

    TYPE_CHOICES = [
        ("wrong_code", "wrong_code"),
        ("device_locked", "device_locked"),
        ("successful_login", "successful_login"),
    ]
    type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    code = models.CharField(max_length=64, blank=True, default="")
    deviceId = models.CharField(max_length=128, blank=True, default="")
    timestamp = models.BigIntegerField(default=now_ms)
    meta = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "security_events"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.type} — {self.code}"


class DeviceLock(models.Model):
    """`device_locks/{deviceId}` — qurilma bloklash hisobi."""

    deviceId = models.CharField(max_length=128, primary_key=True)
    attempts = models.IntegerField(default=0)
    lockedAt = models.BigIntegerField(default=now_ms)
    lockedCode = models.CharField(max_length=64, blank=True, default="")
    isBlocked = models.BooleanField(default=False)

    class Meta:
        db_table = "device_locks"

    def __str__(self):
        return self.deviceId
