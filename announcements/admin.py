from django.contrib import admin
from .models import Announcement, AnnouncementReaction, Notification, NotificationRead

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'scope', 'organization', 'posted_by', 'is_active', 'created_at']
    list_filter = ['scope', 'is_active']
    search_fields = ['title']

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'sender', 'is_priority', 'delivery', 'created_at']
    list_filter = ['is_priority', 'delivery']

@admin.register(NotificationRead)
class NotificationReadAdmin(admin.ModelAdmin):
    list_display = ['notification', 'user', 'read_at']

@admin.register(AnnouncementReaction)
class AnnouncementReactionAdmin(admin.ModelAdmin):
    list_display = ['announcement', 'user', 'reaction', 'created_at']
    list_filter = ['reaction']