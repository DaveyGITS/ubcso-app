from django.db import models
from accounts.models import User
from organizations.models import Organization, Role


class Membership(models.Model):
    ROLE_CHOICES = [
        ('member', 'Member'),
        ('officer', 'Officer'),
        ('co_chairman', 'Vice Chairman'),
        ('adviser', 'Adviser'),
        ('chairman', 'Chairman'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('left', 'Left'),
        ('removed', 'Removed'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member', db_index=True)
    has_chairman_privileges = models.BooleanField(default=False)
    co_chairman_expiry = models.DateTimeField(blank=True, null=True)
    adviser_since = models.DateTimeField(
        blank=True, null=True,
        help_text="Set when promoted to adviser; cleared on demotion or school year transition. "
                  "Used to prevent chairman from bypassing adviser vote exclusion by demoting before election opens."
    )
    custom_role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='memberships')
    # Deferred role — applied when 24hr temp co-chairman window ends
    pending_role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, null=True)
    pending_custom_role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='pending_memberships')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', db_index=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'organization')

    def __str__(self):
        return f"{self.user} — {self.role} at {self.organization}"


class MembershipRequest(models.Model):
    TYPE_CHOICES = [
        ('request', 'Request'),
        ('invite', 'Invite'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='membership_requests')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='membership_requests')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='request')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_membership_requests')
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user} — {self.type} to {self.organization}"


class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='leave_requests')
    reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_leave_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user} leave request from {self.organization}"