from django.db import models
from accounts.models import User
from organizations.constants import PUBLICLY_VISIBLE_STATUSES


class OrganizationCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Organization Categories'

    def __str__(self):
        return self.name


class Organization(models.Model):
    ORG_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('probationary', 'Probationary'),
        ('institutional', 'Institutional'),
        ('active', 'Active'),
        ('renewal_due', 'Renewal Due'),
        ('lapsed', 'Lapsed'),
        ('rejected', 'Rejected'),
    ]
    ORG_CATEGORY_CHOICES = [
        ('student', 'Student Organization'),
        ('ub_chapter', 'UB Chapter'),
        ('institutional', 'Institutional'),
    ]
    ACTIVE_STATUSES = {'probationary', 'institutional', 'active', 'renewal_due'}

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    goals = models.TextField(blank=True, null=True)
    categories = models.ManyToManyField(OrganizationCategory, through='OrganizationCategoryLink', blank=True)
    category = models.CharField(max_length=20, choices=ORG_CATEGORY_CHOICES, default='normal')
    is_cso = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=ORG_STATUS_CHOICES,
        default='pending',
        db_index=True,
    )
    logo = models.ImageField(upload_to='org_logos/', blank=True, null=True)
    banner = models.ImageField(upload_to='org_banners/', blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    founded_year = models.PositiveIntegerField(blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True)
    pre_renewal_status = models.CharField(
        max_length=20,
        choices=ORG_STATUS_CHOICES,
        null=True,
        blank=True,
        help_text="Stores the status before transitioning to renewal_due for proper restoration on renewal approval",
    )

    def save(self, *args, **kwargs):
        # Sync is_active with status so existing queries on is_active continue to work
        self.is_active = self.status in self.ACTIVE_STATUSES
        super().save(*args, **kwargs)

    @property
    def status_badge(self):
        return {'probationary': 'Probationary', 'institutional': 'Institutional'}.get(self.status)

    def __str__(self):
        return self.name


class OrganizationCategoryLink(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    category = models.ForeignKey(OrganizationCategory, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('organization', 'category')

    def __str__(self):
        return f"{self.organization} — {self.category}"


class Role(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.organization})"


class OrganizationRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='org_requests')
    organization_name = models.CharField(max_length=100)
    description = models.TextField()
    proposed_chairman = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='proposed_chairman_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_org_requests')
    created_organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name='origin_request')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.organization_name} request by {self.requester}"


class Poll(models.Model):
    SCOPE_CHOICES = [
        ('system_wide', 'System Wide'),
        ('org_level', 'Org Level'),
    ]
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='polls')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_polls')
    question = models.CharField(max_length=300)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default='org_level')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.question

    @property
    def winning_option_id(self):
        """Returns the option ID with the most votes, or None if tied/empty."""
        from django.db.models import Count
        options = self.options.annotate(vote_count=Count('votes')).order_by('-vote_count')
        if not options.exists():
            return None
        top = options.first()
        if top.vote_count == 0:
            return None
        # Check for tie
        if options.count() > 1 and options[1].vote_count == top.vote_count:
            return None
        return top.id


class PollOption(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=200)

    def __str__(self):
        return self.text


class PollVote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='votes')
    option = models.ForeignKey(PollOption, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='poll_votes')
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('poll', 'user')

    def __str__(self):
        return f"{self.user} voted on {self.poll}"


# --- Media Album Models ---

def org_photo_upload_path(instance, filename):
    return f"org_albums/{instance.album.organization_id}/{filename}"


def org_video_upload_path(instance, filename):
    return f"org_videos/{instance.organization_id}/{filename}"


class OrgAlbum(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='albums')
    title = models.CharField(max_length=200)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_albums')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.organization})"

    @property
    def cover_photo(self):
        return self.photos.order_by('position', 'uploaded_at').first()

    @property
    def photo_count(self):
        return self.photos.count()


class OrgPhoto(models.Model):
    album = models.ForeignKey(OrgAlbum, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to=org_photo_upload_path)
    caption = models.CharField(max_length=300, blank=True, default='')
    position = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'uploaded_at']

    def __str__(self):
        return f"Photo in {self.album.title}"

    @property
    def cover_photo(self):
        return self.photos.order_by('position', 'uploaded_at').first()


class OrgVideoPost(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='video_posts')
    title = models.CharField(max_length=200)
    video = models.FileField(upload_to=org_video_upload_path)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_video_posts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.organization})"


class OrgShowcase(models.Model):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='showcase')
    image = models.ImageField(upload_to='org_showcase/', null=True, blank=True)
    video_post = models.ForeignKey(OrgVideoPost, on_delete=models.SET_NULL, null=True, blank=True, related_name='showcased_by')
    description = models.TextField(max_length=50, blank=True, default='', help_text="Description shown on hover (max 50 chars)")
    accent_color = models.CharField(max_length=7, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Showcase for {self.organization}"

    @property
    def is_image(self):
        return bool(self.image)

    @property
    def is_video(self):
        return self.video_post_id is not None

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.image and self.video_post_id is not None:
            raise ValidationError("A showcase cannot have both an image and a video post set simultaneously.")


# --- Accreditation & Registration Models ---

class OrganizationRegistration(models.Model):
    """For claiming/registering existing campus orgs into the system"""
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    CATEGORY_CHOICES = [
        ('student', 'Student Organization'),
        ('ub_chapter', 'UB Chapter'),
        ('institutional', 'Institutional'),
    ]
    
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='org_registrations')
    
    # Org details
    org_name = models.CharField(max_length=100)
    org_registration_number = models.CharField(max_length=50, blank=True)  # Campus ID if available
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='normal')
    
    # Chairman
    proposed_chairman = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='proposed_chairman_registrations')
    
    # Quick proof/message
    proof_message = models.TextField(help_text="Brief explanation of org's official status in campus")
    proof_document = models.FileField(upload_to='org_registration_proofs/', blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_org_registrations')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_remarks = models.TextField(blank=True, null=True)
    
    # Once approved, org is created
    created_organization = models.OneToOneField(Organization, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.org_name} — {self.status}"


class AccreditationApplication(models.Model):
    REGISTRATION_TYPE_CHOICES = [
        ('new_applicant', 'New Applicant'),
        ('new_chapter', 'New Chapter'),
        ('renewal', 'Renewal/Accreditation'),
    ]
    APPLICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('under_review', 'Under Review'),
        ('returned', 'Returned'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='accreditation_applications'
    )
    registration_type = models.CharField(max_length=20, choices=REGISTRATION_TYPE_CHOICES)
    status = models.CharField(
        max_length=20, choices=APPLICATION_STATUS_CHOICES, default='pending', db_index=True
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_accreditation_applications'
    )
    admin_remarks = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.organization.name} — {self.get_registration_type_display()} ({self.status})"


def accreditation_doc_upload_path(instance, filename):
    return f'accreditation_docs/{instance.application_id}/{filename}'


class AccreditationDocument(models.Model):
    application = models.ForeignKey(
        AccreditationApplication, on_delete=models.CASCADE, related_name='documents'
    )
    document_type = models.CharField(max_length=100)
    file = models.FileField(upload_to=accreditation_doc_upload_path, blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    # Store reference to ReportCompilation when document is a compiled report package
    compilation_id = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.document_type} — {self.application}"


class OfficialFormLink(models.Model):
    label = models.CharField(max_length=100)
    url = models.URLField()
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='updated_form_links'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['label']

    def __str__(self):
        return self.label


class AccreditationRequirement(models.Model):
    """Configurable document requirements for new applicant and new chapter registration types."""
    REGISTRATION_TYPE_CHOICES = [
        ('new_applicant', 'New Applicant'),
        ('new_chapter', 'New Chapter'),
    ]

    registration_type = models.CharField(max_length=20, choices=REGISTRATION_TYPE_CHOICES, unique=True)
    required_documents = models.JSONField(
        default=list,
        help_text="List of {title, link, optional} objects"
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_accreditation_requirements'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Accreditation Requirements'

    def __str__(self):
        return f"Accreditation Requirements — {self.get_registration_type_display()}"


class RenewalRequirement(models.Model):
    """Configurable renewal document requirements by organization status."""
    STATUS_CHOICES = [
        ('probationary', 'Probationary'),
        ('institutional', 'Institutional'),
        ('active', 'Active'),
        ('standard', 'Standard (UB Chapter & Student Org)'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, unique=True)
    required_documents = models.JSONField(
        default=list,
        help_text="List of required document types for renewal"
    )
    optional_documents = models.JSONField(
        default=list,
        blank=True,
        help_text="List of optional document types for renewal"
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_renewal_requirements'
    )
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Renewal Requirements'
    
    def __str__(self):
        return f"Renewal Requirements — {self.get_status_display()}"
