from django.db import models
from accounts.models import User
from organizations.models import Organization


class Announcement(models.Model):
    SCOPE_CHOICES = [
        ('system_wide', 'System Wide'),
        ('org_level', 'Org Level'),
    ]
    title = models.CharField(max_length=200)
    content = models.TextField()
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='org_level')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='announcements')
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='announcements')
    is_active = models.BooleanField(default=True, db_index=True)
    scheduled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class AnnouncementReaction(models.Model):
    REACTION_CHOICES = [
        ('heart', 'Heart'),
    ]
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='announcement_reactions')
    reaction = models.CharField(max_length=20, choices=REACTION_CHOICES, default='seen')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('announcement', 'user')

    def __str__(self):
        return f"{self.user} reacted {self.reaction} to {self.announcement}"


class Notification(models.Model):
    DELIVERY_CHOICES = [
        ('in_app', 'In App'),
        ('email', 'Email'),
        ('both', 'Both'),
    ]
    TYPE_CHOICES = [
        ('membership', 'Membership'),
        ('election', 'Election'),
        ('report', 'Report'),
        ('organization', 'Organization'),
        ('system', 'System'),
        ('profile', 'Profile'),
        ('noteboard', 'Noteboard'),
    ]
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_notifications')
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_priority = models.BooleanField(default=False)
    delivery = models.CharField(max_length=10, choices=DELIVERY_CHOICES, default='both')
    link_url = models.CharField(max_length=500, null=True, blank=True)
    notification_type = models.CharField(max_length=50, choices=TYPE_CHOICES, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class NotificationRead(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='reads')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notification_reads')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('notification', 'user')

    def __str__(self):
        return f"{self.user} read {self.notification}"


class NotificationRecipient(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name='recipients')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_notifications')

    class Meta:
        unique_together = ('notification', 'user')

    def __str__(self):
        return f"{self.user} — {self.notification}"