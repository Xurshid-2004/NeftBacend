"""
Submission domeni — `submissions` kolleksiyasi (4 toifa bitta jadvalda).

Maydon nomlari TS interfeyslari (LokomotivSubmission, KorxonaSubmission,
QurulishSubmission, TamirlashSubmission) bilan AYNAN bir xil. Barcha toifalar
bitta `submissions` jadvalida, `category` diskriminatori bilan saqlanadi —
Firestore'dagidek. Hisobotlar `category` bo'yicha filtrlaydi.

Bog'liq:
  dailySummaries  -> DailySummary  (PK = "{dateISO}_{stationId}_{category}")
  yearlySummaries -> YearlySummary (PK = "{year}_{stationId}_{category}")
  fuelRecords     -> FuelRecord    (ERJU Y.PDF uchun)
"""

from django.db import models

from common.timeutil import now_ms

CATEGORY_CHOICES = [
    ("lokomotiv", "lokomotiv"),
    ("korxona", "korxona"),
    ("qurulish", "qurulish"),
    ("tamirlash", "tamirlash"),
]


class Submission(models.Model):
    # ── Meta / umumiy ──
    staffCode = models.CharField(max_length=64, blank=True, default="")
    staffName = models.CharField(max_length=200, blank=True, default="")
    nodeId = models.CharField(max_length=64, null=True, blank=True)
    stationId = models.CharField(max_length=64, db_index=True)
    category = models.CharField(max_length=16, choices=CATEGORY_CHOICES, db_index=True)

    # ── Standart sana maydonlari (summary-service.ts) ──
    timestamp = models.BigIntegerField(default=now_ms, db_index=True)  # ms
    createdAt = models.BigIntegerField(default=now_ms)  # ms
    timestampMs = models.BigIntegerField(null=True, blank=True)
    dateISO = models.CharField(max_length=10, null=True, blank=True, db_index=True)
    year = models.IntegerField(null=True, blank=True, db_index=True)
    month = models.IntegerField(null=True, blank=True)
    day = models.IntegerField(null=True, blank=True)

    isEdited = models.BooleanField(default=False)
    editedAt = models.BigIntegerField(null=True, blank=True)

    # ── Limit metama'lumotlari (korxona/qurulish eski yozuvlar) ──
    limit = models.FloatField(null=True, blank=True)
    isOverLimit = models.BooleanField(null=True, blank=True)
    oshiqMiqdor = models.FloatField(null=True, blank=True)

    # ── Lokomotiv ──
    harakatTuri = models.CharField(max_length=16, null=True, blank=True, db_index=True)
    rusumi = models.CharField(max_length=32, null=True, blank=True)
    lokomotivNumber = models.CharField(max_length=64, null=True, blank=True)
    jadval = models.CharField(max_length=64, null=True, blank=True)
    zagranitsa = models.FloatField(null=True, blank=True)
    poyezdNumber = models.CharField(max_length=64, null=True, blank=True)
    ruxsatIndeksi = models.CharField(max_length=64, null=True, blank=True)
    poyezdVazni = models.FloatField(null=True, blank=True)
    qoldiq = models.FloatField(null=True, blank=True)
    qanchaBerildi = models.FloatField(null=True, blank=True)
    dizMasla = models.FloatField(null=True, blank=True)
    stansiya = models.CharField(max_length=120, null=True, blank=True)
    tashkilot = models.CharField(max_length=200, null=True, blank=True)
    ijarachi = models.CharField(max_length=200, null=True, blank=True)
    mashinadaYetkazildi = models.BooleanField(default=False)
    mashinaRaqami = models.CharField(max_length=64, null=True, blank=True)

    # ── Korxona ──
    korxonaNomi = models.CharField(max_length=200, null=True, blank=True)
    qancha = models.FloatField(null=True, blank=True)
    nechaSutkalik = models.FloatField(null=True, blank=True)
    buyruqNumber = models.CharField(max_length=120, null=True, blank=True)
    kimTomonidan = models.CharField(max_length=200, null=True, blank=True)
    buyruqVaqti = models.BigIntegerField(null=True, blank=True)

    # ── Qurulish ──
    seriya = models.CharField(max_length=32, null=True, blank=True)
    raqami = models.CharField(max_length=64, null=True, blank=True)
    qanchaOlindi = models.FloatField(null=True, blank=True)
    texnikaSoni = models.IntegerField(null=True, blank=True)
    obyekt = models.CharField(max_length=200, null=True, blank=True)
    masulShaxs = models.CharField(max_length=200, null=True, blank=True)
    lavozim = models.CharField(max_length=120, null=True, blank=True)
    dopLimit = models.FloatField(null=True, blank=True)

    # ── Tamirlash ──
    tamirlashTuri = models.CharField(max_length=16, null=True, blank=True)

    # Dinamik / kelajakdagi maydonlar (firestore-service generic)
    extra = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "submissions"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["stationId", "category", "-timestamp"]),
            models.Index(fields=["dateISO", "stationId", "category"]),
            models.Index(fields=["year", "stationId", "category"]),
            models.Index(fields=["category", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.category} @ {self.stationId} ({self.dateISO})"


class FuelRecord(models.Model):
    """`fuelRecords` — ERJU Y.PDF uchun yozuvlar (string maydonlar Firestore'dagidek)."""

    date = models.CharField(max_length=10, blank=True, default="")
    dateISO = models.CharField(max_length=10, blank=True, default="", db_index=True)
    year = models.IntegerField(null=True, blank=True, db_index=True)
    time = models.CharField(max_length=8, blank=True, default="")
    supplyPoint = models.CharField(max_length=120, blank=True, default="")
    staffCode = models.CharField(max_length=64, blank=True, default="")
    staffName = models.CharField(max_length=200, blank=True, default="")
    locCode = models.CharField(max_length=64, blank=True, default="", db_index=True)
    moveType = models.CharField(max_length=16, blank=True, default="")
    locoSeries = models.CharField(max_length=32, blank=True, default="")
    locoCode = models.CharField(max_length=64, blank=True, default="")
    locoNumber = models.CharField(max_length=120, blank=True, default="")
    trainIndex = models.CharField(max_length=200, blank=True, default="")
    ruxsatIndeksi = models.CharField(max_length=64, blank=True, default="")
    route = models.CharField(max_length=120, blank=True, default="")
    trainCode = models.CharField(max_length=64, blank=True, default="")
    trainNumber = models.CharField(max_length=64, blank=True, default="")
    weight = models.CharField(max_length=32, blank=True, default="")
    balanceBefore = models.CharField(max_length=32, blank=True, default="")
    fuelAmount = models.CharField(max_length=32, blank=True, default="")
    maslaAmount = models.CharField(max_length=32, blank=True, default="")
    jadval = models.CharField(max_length=64, blank=True, default="")
    zagranitsa = models.CharField(max_length=32, blank=True, default="")
    zagranitsaAmount = models.CharField(max_length=32, blank=True, default="")
    stansiya = models.CharField(max_length=120, blank=True, default="")
    tashkilot = models.CharField(max_length=200, blank=True, default="")
    ijarachi = models.CharField(max_length=200, blank=True, default="")
    mashinadaYetkazildi = models.BooleanField(default=False)
    mashinaRaqami = models.CharField(max_length=64, blank=True, default="")
    createdAt = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "fuel_records"
        ordering = ["-createdAt"]
        indexes = [
            models.Index(fields=["dateISO", "locCode"]),
            models.Index(fields=["year", "locCode"]),
        ]

    def __str__(self):
        return f"{self.moveType} @ {self.locCode} ({self.dateISO})"


class _SummaryBase(models.Model):
    docId = models.CharField(max_length=160, primary_key=True)
    stationId = models.CharField(max_length=64, db_index=True)
    nodeId = models.CharField(max_length=64, null=True, blank=True)
    category = models.CharField(max_length=16)
    totalFuelKg = models.FloatField(default=0)
    totalMaslaKg = models.FloatField(default=0)
    recordCount = models.IntegerField(default=0)
    updatedAt = models.BigIntegerField(default=now_ms)

    class Meta:
        abstract = True


class DailySummary(_SummaryBase):
    """`dailySummaries/{dateISO_stationId_category}`."""

    dateISO = models.CharField(max_length=10, db_index=True)
    year = models.IntegerField(db_index=True)

    class Meta:
        db_table = "daily_summaries"

    def __str__(self):
        return self.docId


class YearlySummary(_SummaryBase):
    """`yearlySummaries/{year_stationId_category}`."""

    year = models.IntegerField(db_index=True)

    class Meta:
        db_table = "yearly_summaries"

    def __str__(self):
        return self.docId


class KorxonaWorkerCode(models.Model):
    """
    Worker panel — korxona forma: har bir worker o'zi tanlagan qidiruv raqamini
    korxona nomiga biriktiradi (masalan 777 -> "Buxoro vagon deposi"). `staffCode`
    orqali saqlanadi, shuning uchun worker qaysi qurilmadan kirmasin o'zi
    biriktirgan raqamlarni ko'ra oladi.
    """

    staffCode = models.CharField(max_length=64, db_index=True)
    korxonaNomi = models.CharField(max_length=200)
    code = models.CharField(max_length=32)
    updatedAt = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "korxona_worker_codes"
        unique_together = [("staffCode", "korxonaNomi")]
        ordering = ["korxonaNomi"]

    def __str__(self):
        return f"{self.staffCode}: {self.korxonaNomi} -> {self.code}"
