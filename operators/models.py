"""
Operator yoqilg'i balansi — `lib/operator/operator-balance.ts` ning backend ko'chirmasi.

Firestore kolleksiyalari:
  operatorStationBalances/{stationId}  -> OperatorStationBalance
  operatorOverlimits/{auto}            -> OperatorOverlimit (limitdan oshish izi)
"""

from django.db import models

from common.timeutil import now_ms


class OperatorStationBalance(models.Model):
    """Har bir zapravka uchun operator ajratgan yoqilg'i qoldig'i (kg)."""

    stationId = models.CharField(max_length=64, primary_key=True)
    balanceKg = models.FloatField(default=0)
    overlimitKg = models.FloatField(default=0)
    updatedAt = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "operator_station_balances"

    def __str__(self):
        return f"{self.stationId}: {self.balanceKg}kg (over {self.overlimitKg})"


class OperatorOverlimit(models.Model):
    """Balansdan oshib ketgan sarf izi (audit/limit uchun)."""

    stationId = models.CharField(max_length=64, db_index=True)
    amountKg = models.FloatField(default=0)
    usedKg = models.FloatField(default=0)
    category = models.CharField(max_length=16, null=True, blank=True)
    staffCode = models.CharField(max_length=64, null=True, blank=True)
    staffName = models.CharField(max_length=200, null=True, blank=True)
    nodeId = models.CharField(max_length=64, null=True, blank=True)
    createdAt = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "operator_overlimits"
        ordering = ["-createdAt"]

    def __str__(self):
        return f"{self.stationId}: +{self.amountKg}kg over"


class OperatorShipment(models.Model):
    """Stansiyalar orasida (yoki realizatsiyadan stansiyaga) yoqilg'i jo'natmasi.

    Frontend `operator_pending_shipments` (localStorage) massividagi bitta
    elementga mos — id frontendda `crypto.randomUUID()` bilan yaratiladi va
    shu holicha primary key sifatida saqlanadi.
    """

    STATUS_CHOICES = [("pending", "pending"), ("accepted", "accepted")]

    id = models.CharField(max_length=64, primary_key=True)
    fromStationId = models.CharField(max_length=64, db_index=True)
    fromStationName = models.CharField(max_length=200, blank=True, default="")
    toStationId = models.CharField(max_length=64, db_index=True)
    toStationName = models.CharField(max_length=200, blank=True, default="")
    amountKg = models.FloatField(default=0)
    createdAt = models.BigIntegerField(default=now_ms)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    acceptedAt = models.BigIntegerField(null=True, blank=True)
    acceptedKg = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "operator_shipments"
        ordering = ["-createdAt"]

    def __str__(self):
        return f"{self.fromStationId} -> {self.toStationId}: {self.amountKg}kg ({self.status})"


class OperatorShipmentRequest(models.Model):
    """Zapravkadan zapravkaga dizel yuborish uchun RUXSAT SO'ROVI.

    Ishchi (yoki operator) o'zi bevosita jo'nata olmaydi: avval "shuncha
    yubormoqchiman" deb so'rov qoldiradi. Admin `/admin/overlimit/korxona`
    sahifasida ruxsat berganidan keyingina haqiqiy `OperatorShipment` yaratiladi
    va yoqilg'i balansdan ayiriladi.

    MUHIM: so'rovning o'zi balansga TEGMAYDI — ayirish faqat ruxsat berilganda,
    `services.approve_shipment_request` ichida, jo'natma bilan bitta atomik
    amalda bo'ladi. Shu sababli rad etilgan so'rovni "orqaga qaytarish" kerak emas.
    """

    # pending  — admin hali qaramagan
    # allowed  — admin "shuncha kg gacha ruxsat" berdi, ishchi hali jo'natmagan
    # approved — jo'natma yaratilgan (balansdan ayirilgan)
    # rejected — rad etilgan
    STATUS_CHOICES = [
        ("pending", "pending"),
        ("allowed", "allowed"),
        ("approved", "approved"),
        ("rejected", "rejected"),
    ]

    id = models.CharField(max_length=64, primary_key=True)
    fromStationId = models.CharField(max_length=64, db_index=True)
    fromStationName = models.CharField(max_length=200, blank=True, default="")
    toStationId = models.CharField(max_length=64, db_index=True)
    toStationName = models.CharField(max_length=200, blank=True, default="")
    amountKg = models.FloatField(default=0)
    # Modaldagi "Масъул шахс" maydoni (ma'lumot uchun, hisobga ta'sir qilmaydi).
    masulShaxs = models.CharField(max_length=200, blank=True, default="")
    requestedByCode = models.CharField(max_length=64, blank=True, default="")
    requestedByName = models.CharField(max_length=200, blank=True, default="")
    createdAt = models.BigIntegerField(default=now_ms)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="pending")
    # Admin «Бошқа қиймат» orqali bergan ruxsat chegarasi (kg). Ishchi shundan
    # ORTIQ jo'nata olmaydi — tekshiruv serverda (`send_allowed_shipment`).
    allowedKg = models.FloatField(null=True, blank=True)
    decidedAt = models.BigIntegerField(null=True, blank=True)
    decidedByCode = models.CharField(max_length=64, blank=True, default="")
    decidedByName = models.CharField(max_length=200, blank=True, default="")
    rejectReason = models.CharField(max_length=300, blank=True, default="")
    # Ruxsat berilgach yaratilgan jo'natmaning id si (kuzatish uchun).
    shipmentId = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        db_table = "operator_shipment_requests"
        ordering = ["-createdAt"]

    def __str__(self):
        return (
            f"so'rov {self.fromStationId} -> {self.toStationId}: "
            f"{self.amountKg}kg ({self.status})"
        )


class OperatorCentralTank(models.Model):
    """Markaziy (sotib olingan) yoqilg'i tanki — realizatsiya bo'limi shu tankdan tarqatadi.

    Bitta yozuv (singleton, id="main"):
      * yoqilg'i sotib olinganda balans oshadi (OperatorCentralPurchase yoziladi),
      * realizatsiya panelidan zapravkaga tarqatilganda balans kamayadi.
    """

    id = models.CharField(max_length=32, primary_key=True, default="main")
    balanceKg = models.FloatField(default=0)
    totalPurchasedKg = models.FloatField(default=0)
    updatedAt = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "operator_central_tank"

    def __str__(self):
        return f"markaziy tank: {self.balanceKg}kg"


class OperatorCentralPurchase(models.Model):
    """Markaziy tankka sotib olingan yoqilg'i tarixi (qancha, qayerdan)."""

    id = models.CharField(max_length=64, primary_key=True)
    amountKg = models.FloatField(default=0)
    source = models.CharField(max_length=200, blank=True, default="")
    createdAt = models.BigIntegerField(default=now_ms)

    class Meta:
        db_table = "operator_central_purchases"
        ordering = ["-createdAt"]

    def __str__(self):
        return f"+{self.amountKg}kg ({self.source})"
