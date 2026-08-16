from django.contrib import admin

from .models import (
    AccessCode,
    ActiveSession,
    BlockedCode,
    DeviceLock,
    FaceTemplate,
    SecurityEvent,
    Staff,
)


@admin.register(AccessCode)
class AccessCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "role", "codeType", "displayName", "isActive")
    list_filter = ("role", "codeType", "isActive")
    search_fields = ("code", "displayName")


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("tabelNumber", "fullName", "zapravka", "erju", "stationId", "role")
    list_filter = ("erju", "role")
    search_fields = ("tabelNumber", "fullName", "zapravka")
    # Surat — uzun base64 matn; ro'yxatda ham, formada ham ochib o'tirilmaydi.
    exclude = ("photo",)


@admin.register(FaceTemplate)
class FaceTemplateAdmin(admin.ModelAdmin):
    """Face ID shablonlari. Biometrik vektor ATAYLAB ko'rsatilmaydi/tahrirlanmaydi."""

    list_display = ("code", "sampleCount", "createdByDisplayName", "updatedAt", "lastMatchedAt")
    search_fields = ("code", "createdByDisplayName")
    exclude = ("vectors",)
    readonly_fields = ("code", "sampleCount", "version", "createdAt", "updatedAt", "lastMatchedAt")

    def has_add_permission(self, request):
        return False


@admin.register(BlockedCode)
class BlockedCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "note", "blockedByDisplayName", "blockedAt")
    search_fields = ("code", "note")


@admin.register(ActiveSession)
class ActiveSessionAdmin(admin.ModelAdmin):
    list_display = ("uid", "code", "role", "stationId", "lastSeen")
    list_filter = ("role",)
    search_fields = ("code", "uid")


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ("type", "code", "deviceId", "timestamp")
    list_filter = ("type",)
    search_fields = ("code", "deviceId")


@admin.register(DeviceLock)
class DeviceLockAdmin(admin.ModelAdmin):
    list_display = ("deviceId", "attempts", "lockedCode", "isBlocked", "lockedAt")
    list_filter = ("isBlocked",)
