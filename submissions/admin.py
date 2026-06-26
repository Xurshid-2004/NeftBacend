from django.contrib import admin

from .models import DailySummary, FuelRecord, Submission, YearlySummary


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "stationId", "dateISO", "qanchaBerildi", "qancha", "qanchaOlindi", "isEdited")
    list_filter = ("category", "stationId", "harakatTuri", "isEdited")
    search_fields = ("staffName", "staffCode", "lokomotivNumber", "raqami", "korxonaNomi")
    date_hierarchy = None
    ordering = ("-timestamp",)


@admin.register(FuelRecord)
class FuelRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "moveType", "locCode", "dateISO", "fuelAmount", "maslaAmount")
    list_filter = ("moveType", "locCode")
    search_fields = ("staffName", "locoSeries", "locoCode")


@admin.register(DailySummary)
class DailySummaryAdmin(admin.ModelAdmin):
    list_display = ("docId", "stationId", "category", "dateISO", "totalFuelKg", "totalMaslaKg", "recordCount")
    list_filter = ("category", "stationId", "year")


@admin.register(YearlySummary)
class YearlySummaryAdmin(admin.ModelAdmin):
    list_display = ("docId", "stationId", "category", "year", "totalFuelKg", "totalMaslaKg", "recordCount")
    list_filter = ("category", "stationId", "year")
