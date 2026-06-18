from django.contrib import admin
from .models import Membership, MembershipRequest, LeaveRequest

@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'role', 'has_chairman_privileges', 'status']
    list_filter = ['role', 'status']
    search_fields = ['user__email', 'organization__name']

@admin.register(MembershipRequest)
class MembershipRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'type', 'status', 'requested_at']
    list_filter = ['type', 'status']

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'status', 'created_at']
    list_filter = ['status']