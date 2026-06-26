from django.contrib import admin

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


@admin.register(Uzel)
class UzelAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug")


@admin.register(Zapravka)
class ZapravkaAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "uzelId", "slug")
    list_filter = ("uzelId",)


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ("key", "updatedAt")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("category", "order", "label", "fieldKey", "fieldType", "isVisible")
    list_filter = ("category", "fieldType", "isVisible")
    ordering = ("category", "order")


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    list_display = ("stationId", "updatedAt")


@admin.register(Limit)
class LimitAdmin(admin.ModelAdmin):
    list_display = ("type", "stationId", "limit", "isActive", "updatedAt")
    list_filter = ("type", "isActive")


@admin.register(ClosedDay)
class ClosedDayAdmin(admin.ModelAdmin):
    list_display = ("docId", "updatedAt")


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = ("id", "createdAt", "updatedAt")
