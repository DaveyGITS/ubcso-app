from django.contrib import admin
from .models import SystemSetting, HandoverNote, AuditLog, AcademicPeriod

@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'last_updated_by', 'last_updated_at']

@admin.register(HandoverNote)
class HandoverNoteAdmin(admin.ModelAdmin):
    list_display = ['from_user', 'to_user', 'type', 'created_at']

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['actor', 'action', 'target_type', 'created_at']
    list_filter = ['action']

@admin.register(AcademicPeriod)
class AcademicPeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date','end_date', 'is_current']