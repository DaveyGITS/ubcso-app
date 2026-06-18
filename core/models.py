from django.db import models
from django.core.exceptions import ValidationError
from accounts.models import User
from organizations.models import Organization


class SystemSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    last_updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='system_settings')
    last_updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key


class HandoverNote(models.Model):
    TYPE_CHOICES = [
        ('chairman', 'Chairman'),
        ('cso_president', 'CSO President'),
    ]
    from_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='handover_notes_sent')
    to_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='handover_notes_received')
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name='handover_notes')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Handover from {self.from_user} to {self.to_user}"


class AuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=50)
    target_id = models.IntegerField(blank=True, null=True)
    details = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.actor} — {self.action} at {self.created_at}"


class AcademicPeriod(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='academic_periods')

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        # Check for overlapping periods
        overlapping = AcademicPeriod.objects.filter(
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        ).exclude(pk=self.pk)
        
        if overlapping.exists():
            raise ValidationError('This period overlaps with an existing academic period.')

    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicPeriod.objects.filter(is_current=True).update(is_current=False)
        super().save(*args, **kwargs)