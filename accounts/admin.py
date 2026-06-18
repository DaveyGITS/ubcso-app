from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Course, OTPToken, ProfileCorrectionRequest

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'student_id', 'is_cso_president', 'is_cso_admin', 'is_active']
    list_filter = ['is_cso_president', 'is_cso_admin', 'is_active', 'is_email_verified']
    search_fields = ['email', 'first_name', 'last_name', 'student_id']
    ordering = ['email']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'middle_initial', 'last_name', 'student_id', 'year_level', 'course', 'bio', 'profile_picture', 'contact_number')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_email_verified', 'is_cso_admin', 'is_cso_president', 'cso_admin_expiry')}),
        ('Preferences', {'fields': ('email_notifications', 'low_data_mode')}),
    )
    add_fieldsets = (
        (None, {'fields': ('email', 'password1', 'password2')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'student_id')}),
    )

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['name', 'abbreviation', 'department', 'is_active']
    search_fields = ['name', 'abbreviation']

@admin.register(OTPToken)
class OTPTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'otp_code', 'created_at', 'expires_at', 'is_used']

@admin.register(ProfileCorrectionRequest)
class ProfileCorrectionRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'field_name', 'old_value', 'new_value', 'status']
    list_filter = ['status']