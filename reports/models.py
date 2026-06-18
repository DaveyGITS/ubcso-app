from django.db import models
from accounts.models import User
from organizations.models import Organization
from core.models import AcademicPeriod


class AccomplishmentReport(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='accomplishment_reports')
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='submitted_reports')
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    rejection_reason = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_reports')
    activity_name = models.CharField(max_length=200, blank=True, default='')
    date_of_activity = models.DateField(null=True, blank=True)
    academic_year = models.CharField(max_length=20, blank=True, default='', help_text='e.g. 2024–2025')
    semester = models.CharField(
        max_length=10,
        choices=[('1st', '1st Semester'), ('2nd', '2nd Semester'), ('Summer', 'Summer')],
        blank=True,
        default='',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} — {self.organization}"


class ReportAttachment(models.Model):
    report = models.ForeignKey(AccomplishmentReport, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='report_attachments/')
    filename = models.CharField(max_length=255)
    filesize = models.PositiveIntegerField(default=0)  # bytes
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.filename} ({self.report})"


class ReportCompilation(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='report_compilations'
    )
    name = models.CharField(max_length=200)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='created_compilations'
    )
    reports = models.ManyToManyField(AccomplishmentReport, related_name='compilations', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.organization})"
