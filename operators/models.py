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
