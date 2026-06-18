from django.db import models

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin





class CustomUserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):

        if not email:

            raise ValueError('Email is required')

        email = self.normalize_email(email)

        user = self.model(email=email, **extra_fields)

        user.set_password(password)

        user.save(using=self._db)

        return user



    def create_superuser(self, email, password=None, **extra_fields):

        extra_fields.setdefault('is_staff', True)

        extra_fields.setdefault('is_superuser', True)

        extra_fields.setdefault('is_active', True)

        extra_fields.setdefault('is_email_verified', True)

        extra_fields.setdefault('is_cso_president', True)

        return self.create_user(email, password, **extra_fields)





class Course(models.Model):

    name = models.CharField(max_length=100)

    abbreviation = models.CharField(max_length=20, unique=True)

    department = models.CharField(max_length=100)

    is_active = models.BooleanField(default=True)



    def __str__(self):

        return self.name





class User(AbstractBaseUser, PermissionsMixin):

    email = models.EmailField(unique=True)

    first_name = models.CharField(max_length=50)

    middle_initial = models.CharField(max_length=5, blank=True, null=True)

    last_name = models.CharField(max_length=50)

    student_id = models.CharField(max_length=20, unique=True, blank=True, null=True)

    year_level = models.PositiveIntegerField(default=1)

    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True)

    # Faculty fields
    is_faculty = models.BooleanField(default=False, db_index=True)

    employee_id = models.CharField(max_length=30, unique=True, blank=True, null=True)

    department = models.CharField(max_length=100, blank=True, null=True)

    bio = models.TextField(blank=True, null=True)

    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    contact_number = models.CharField(max_length=20, blank=True, null=True)

    is_email_verified = models.BooleanField(default=False)

    is_cso_admin = models.BooleanField(default=False, db_index=True)

    is_cso_president = models.BooleanField(default=False, db_index=True)

    is_manually_granted_admin = models.BooleanField(default=False)  # True = granted via privileges page; survives role changes

    cso_admin_expiry = models.DateTimeField(blank=True, null=True)

    is_active = models.BooleanField(default=False, db_index=True)

    is_staff = models.BooleanField(default=False)

    email_notifications = models.BooleanField(default=True)

    low_data_mode = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)

    last_login = models.DateTimeField(blank=True, null=True)



    USERNAME_FIELD = 'email'

    REQUIRED_FIELDS = ['first_name', 'last_name']



    objects = CustomUserManager()



    def __str__(self):

        identifier = self.student_id or self.employee_id or self.email

        return f"{self.first_name} {self.last_name} ({identifier})"



    def get_full_name(self):

        if self.middle_initial:

            return f"{self.first_name} {self.middle_initial}. {self.last_name}"

        return f"{self.first_name} {self.last_name}"





class OTPToken(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_tokens')

    otp_code = models.CharField(max_length=6)

    created_at = models.DateTimeField(auto_now_add=True)

    expires_at = models.DateTimeField()

    is_used = models.BooleanField(default=False)



    def __str__(self):

        return f"OTP for {self.user.email}"





class ProfileCorrectionRequest(models.Model):

    STATUS_CHOICES = [

        ('pending', 'Pending'),

        ('approved', 'Approved'),

        ('rejected', 'Rejected'),

    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='correction_requests')

    field_name = models.CharField(max_length=50)

    old_value = models.CharField(max_length=255)

    new_value = models.CharField(max_length=255)

    reason = models.TextField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    rejection_reason = models.TextField(blank=True, null=True)

    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_corrections')

    created_at = models.DateTimeField(auto_now_add=True)

    reviewed_at = models.DateTimeField(blank=True, null=True)



    def __str__(self):

        return f"{self.user} - {self.field_name} correction"


class FacultyRegistrationRequest(models.Model):
    STATUS_CHOICES = [
        ('pending_otp', 'Pending OTP Verification'),
        ('pending_approval', 'Pending Admin Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=50)
    middle_initial = models.CharField(max_length=5, blank=True, null=True)
    last_name = models.CharField(max_length=50)
    employee_id = models.CharField(max_length=30)
    department = models.CharField(max_length=100)
    password_hash = models.CharField(max_length=255)  # hashed at form submission

    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_expires_at = models.DateTimeField(blank=True, null=True)
    otp_verified = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_otp', db_index=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_faculty_requests'
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_full_name(self):
        if self.middle_initial:
            return f"{self.first_name} {self.middle_initial}. {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return f"{self.get_full_name()} ({self.email}) — {self.status}"
