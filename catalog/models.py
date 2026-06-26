"""
Reference / konfiguratsiya modellari.

Firestore kolleksiyalari:
  uzellar (statik) -> Uzel
  zapravkalar (statik) -> Zapravka
  settings/{key}   -> Setting     (JSON hujjat, key=PK, masalan "global")
  questions        -> Question    (FormQuestion)
  variants/{stationId} -> Variant (JSON hujjat: fieldKey -> [qiymatlar])
  limits           -> Limit
  closedDays/{id}  -> ClosedDay   (JSON hujjat — taqvim)
  approvals        -> Approval     (JSON hujjat — ruxsatnomalar)
"""

from django.db import models

from common.timeutil import now_ms


class Uzel(models.Model):
    """`uzellar` — uzel (depo guruhi)."""

    id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=120)
    slug = models.CharField(max_length=64)
    description = models.CharField(max_length=200, blank=True, default="")
    icon = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        db_table = "uzellar"
        ordering = ["id"]

    def __str__(self):
        return self.name


class Zapravka(models.Model):
    """`zapravkalar` — zapravka (stansiya)."""

    id = models.CharField(max_length=64, primary_key=True)
    uzelId = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=120)
    slug = models.CharField(max_length=64)

    class Meta:
        db_table = "zapravkalar"
        ordering = ["uzelId", "id"]

    def __str__(self):
        return self.name


class Setting(models.Model):
    """`settings/{key}` — JSON konfiguratsiya hujjati (masalan "global")."""

    key = models.CharField(max_length=64, primary_key=True)
    data = models.JSONField(default=dict, blank=True)
    updatedAt = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "settings"

    def __str__(self):
        return self.key


class Question(models.Model):
    """`questions` — dinamik forma savollari (FormQuestion)."""

    category = models.CharField(max_length=16, db_index=True)
    stationId = models.CharField(max_length=64, blank=True, default="")
    order = models.IntegerField(default=0)
    label = models.CharField(max_length=200)
    fieldKey = models.CharField(max_length=64)
    fieldType = models.CharField(max_length=16)  # text|number|dropdown|datetime|boolean
    options = models.JSONField(null=True, blank=True)
    isRequired = models.BooleanField(default=False)
    isVisible = models.BooleanField(default=True)
    showWhen = models.JSONField(null=True, blank=True)
    pdfColumn = models.CharField(max_length=120, null=True, blank=True)
    createdAt = models.BigIntegerField(default=now_ms)
    updatedAt = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "questions"
        ordering = ["category", "order"]

    def __str__(self):
        return f"{self.category}: {self.label}"


class Variant(models.Model):
    """`variants/{stationId}` — fieldKey -> qiymatlar ro'yxati (dinamik)."""

    stationId = models.CharField(max_length=64, primary_key=True)
    data = models.JSONField(default=dict, blank=True)
    updatedAt = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "variants"

    def __str__(self):
        return self.stationId


class Limit(models.Model):
    """`limits` — yoqilg'i limitlari (kg/sutka)."""

    TYPE_CHOICES = [
        ("korxona", "korxona"),
        ("qurulish", "qurulish"),
        ("lokomotiv", "lokomotiv"),
        ("stansiya", "stansiya"),
    ]
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    korxonaNomi = models.CharField(max_length=200, null=True, blank=True)
    seriya = models.CharField(max_length=64, null=True, blank=True)
    lokomotivNumber = models.CharField(max_length=64, null=True, blank=True)
    stansiyaName = models.CharField(max_length=200, null=True, blank=True)
    stationId = models.CharField(max_length=64, db_index=True)
    limit = models.FloatField(default=0)
    isActive = models.BooleanField(default=True)
    createdBy = models.CharField(max_length=120, blank=True, default="")
    createdAt = models.BigIntegerField(default=now_ms)
    updatedAt = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "limits"
        ordering = ["-updatedAt"]

    def __str__(self):
        return f"{self.type} — {self.stationId}: {self.limit}"


class ClosedDay(models.Model):
    """`closedDays/{id}` — yopilgan kunlar (taqvim). JSON hujjat."""

    docId = models.CharField(max_length=120, primary_key=True)
    data = models.JSONField(default=dict, blank=True)
    updatedAt = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "closed_days"

    def __str__(self):
        return self.docId


class Approval(models.Model):
    """`approvals` — ruxsatnomalar (dinamik JSON hujjat)."""

    data = models.JSONField(default=dict, blank=True)
    createdAt = models.BigIntegerField(default=now_ms)
    updatedAt = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "approvals"
        ordering = ["-createdAt"]

    def __str__(self):
        return f"approval#{self.pk}"
