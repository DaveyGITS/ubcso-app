from django.db import models
from django.core.exceptions import ValidationError
from accounts.models import User
from organizations.models import Organization
from core.models import AcademicPeriod


class Election(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('results_released', 'Results Released'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='elections')
    academic_period = models.ForeignKey(AcademicPeriod, on_delete=models.SET_NULL, null=True, blank=True, related_name='elections')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    start_datetime = models.DateTimeField(null=True, blank=True)
    end_datetime = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_elections')
    results_released_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='released_elections')
    results_released_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Voter pool configuration
    voters_all_students = models.BooleanField(default=False)       # All registered students (system-wide)
    voters_org_members = models.BooleanField(default=False)        # All active members of THIS org
    voters_org_officers = models.BooleanField(default=False)       # Officers+co_chairman+chairman of THIS org
    voters_all_officers = models.BooleanField(default=False)       # Officers+co_chairman+chairman across ALL orgs
    voters_all_chairmen = models.BooleanField(default=False)       # Chairmen only across ALL orgs
    voters_cso_officers = models.BooleanField(default=False)       # CSO org officers only
    voters_specific_orgs = models.ManyToManyField(
        Organization, blank=True, related_name='voter_pool_elections'
    )
    voters_specific_users = models.ManyToManyField(
        User, blank=True, related_name='individually_included_elections'
    )

    def clean(self):
        super().clean()
        if self.start_datetime and self.end_datetime:
            if self.end_datetime <= self.start_datetime:
                raise ValidationError({
                    'end_datetime': 'End time must be after start time.'
                })

    def __str__(self):
        return f"{self.title} — {self.organization}"


class ElectionPosition(models.Model):
    ROLE_CHOICES = [
        ('member', 'Member'),
        ('officer', 'Officer'),
        ('co_chairman', 'Vice Chairman'),
        ('chairman', 'Chairman'),
    ]
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='positions')
    name = models.CharField(max_length=100)
    target_role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='officer')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('election', 'name')
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.election})"


class ElectionVoter(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='voters')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='election_voters')

    class Meta:
        unique_together = ('election', 'user')

    def __str__(self):
        return f"{self.user} — voter in {self.election}"


class Candidate(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='candidates')
    position = models.ForeignKey(ElectionPosition, on_delete=models.CASCADE, related_name='candidates')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='candidacies')
    nominated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='nominations_made')
    nominated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('election', 'position', 'user')

    def __str__(self):
        return f"{self.user} for {self.position}"


class Vote(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='votes')
    position = models.ForeignKey(ElectionPosition, on_delete=models.CASCADE, related_name='votes')
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='votes')
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='votes_cast')
    cast_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['voter', 'position', 'election'],
                name='unique_vote_per_voter_per_position'
            )
        ]

    def __str__(self):
        return f"{self.voter} voted in {self.election}"
