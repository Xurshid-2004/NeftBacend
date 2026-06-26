from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "entityType", "entityId", "userName", "userRole", "timestamp")
    list_filter = ("action", "entityType", "userRole")
    search_fields = ("userName", "userId", "entityId")
