from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django_ratelimit.decorators import ratelimit
from core.audit import log_action, AuditActions
from .models import User, Course, OTPToken


@ratelimit(key='ip', rate='20/h', method='POST', block=True)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        
        if user is not None:
            if not user.is_email_verified:
                messages.error(request, 'Please verify your email before logging in.')
                return redirect('accounts:verify_otp')
            if not user.is_active:
                messages.error(request, 'Your account has been deactivated. Please contact the CSO admin.')
                return render(request, 'accounts/login.html')
            login(request, user)
            
            # Audit log
            log_action(
                actor=user,
                action=AuditActions.USER_LOGIN,
                target=user,
                details=f'Logged in',
                request=request
            )
            
            return redirect('core:dashboard')
        else:
            messages.error(request, 'Invalid email or password.')
    
    return render(request, 'accounts/login.html')


def logout_view(request):
    if request.method == 'POST':
        logout(request)
        return redirect('core:home')
    return redirect('core:dashboard')


@login_required
def profile_view(request):
    from memberships.models import Membership
    memberships = Membership.objects.filter(
        user=request.user,
        status='active',
         organization__is_active=True,
    ).select_related('organization', 'custom_role')
    
    return render(request, 'accounts/profile.html', {
        'memberships': memberships,
    })


@login_required
def edit_profile_view(request):
    from .models import Course

    if request.method == 'POST':
        bio = request.POST.get('bio', '').strip()
        contact_number = request.POST.get('contact_number', '').strip()
        email_notifications = request.POST.get('email_notifications') == 'on'
        low_data_mode = request.POST.get('low_data_mode') == 'on'

        user = request.user
        user.bio = bio
        user.contact_number = contact_number
        user.email_notifications = email_notifications
        user.low_data_mode = low_data_mode

        # CSO admins and president can also edit locked fields directly
        if user.is_cso_admin or user.is_cso_president:
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            middle_initial = request.POST.get('middle_initial', '').strip().rstrip('.').upper()
            student_id = request.POST.get('student_id', '').strip()
            year_level = request.POST.get('year_level', '').strip()
            course_id = request.POST.get('course', '').strip()

            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
            user.middle_initial = middle_initial
            if student_id and student_id != user.student_id:
                if User.objects.filter(student_id=student_id).exclude(pk=user.pk).exists():
                    messages.error(request, 'That student ID is already taken.')
                    return redirect('accounts:edit_profile')
                user.student_id = student_id
            if year_level:
                try:
                    user.year_level = int(year_level)
                except ValueError:
                    pass
            if course_id:
                try:
                    user.course = Course.objects.get(id=int(course_id))
                except Course.DoesNotExist:
                    pass

        # Handle cropped base64 image
        cropped_data = request.POST.get('profile_picture_cropped', '').strip()
        if cropped_data and cropped_data.startswith('data:image'):
            import base64, uuid
            from django.core.files.base import ContentFile
            fmt, imgstr = cropped_data.split(';base64,')
            ext = fmt.split('/')[-1]
            img_data = base64.b64decode(imgstr)
            filename = f'profile_{uuid.uuid4().hex}.{ext}'
            user.profile_picture.save(filename, ContentFile(img_data), save=False)
        elif 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']

        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('accounts:profile')

    courses = Course.objects.filter(is_active=True).order_by('department', 'name')
    return render(request, 'accounts/edit_profile.html', {'courses': courses})

@login_required
def student_profile_view(request, user_id):
    from memberships.models import Membership
    student = get_object_or_404(User, id=user_id, is_active=True)
    memberships = Membership.objects.filter(
        user=student, status='active',  organization__is_active=True,
    ).select_related('organization', 'custom_role')
    is_own_profile = student == request.user
    return render(request, 'accounts/student_profile.html', {
        'student': student,
        'memberships': memberships,
        'is_own_profile': is_own_profile,
    })


@ratelimit(key='ip', rate='3/h', method='POST', block=True)
def register_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    from .models import Course
    courses = Course.objects.filter(is_active=True).order_by('department', 'name').distinct()   

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        middle_initial = request.POST.get('middle_initial', '').strip().rstrip('.').upper()
        last_name = request.POST.get('last_name', '').strip()
        student_id = request.POST.get('student_id', '').strip()
        year_level = request.POST.get('year_level', '').strip()
        course_id = request.POST.get('course', '').strip()
        password1 = request.POST.get('password1', '').strip()
        password2 = request.POST.get('password2', '').strip()

        errors = []

        if not email.endswith('@universityofbohol.edu.ph'):
            errors.append('You must use your university email (@universityofbohol.edu.ph).')

        if not first_name or len(first_name) < 2 or not first_name.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').isalpha():
            errors.append('First name must be at least 2 characters and contain only letters, spaces, hyphens, or parentheses.')

        if not last_name or len(last_name) < 2 or not last_name.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').isalpha():
            errors.append('Last name must be at least 2 characters and contain only letters, spaces, hyphens, or parentheses.')

        if middle_initial and (len(middle_initial) > 1 or not middle_initial.isalpha()):
            errors.append('Middle initial must be a single letter (no dot).')

        if not student_id or len(student_id) < 4:
            errors.append('Student ID must be at least 4 characters.')
        else:
            import re as _re
            if not _re.match(r'^[0-9\-]+$', student_id):
                errors.append('Student ID must contain only digits and hyphens (e.g. 2024-0001).')

        if year_level:
            try:
                yr = int(year_level)
                if yr < 1 or yr > 10:
                    errors.append('Year level must be between 1 and 10.')
            except ValueError:
                errors.append('Year level must be a valid number.')
        else:
            errors.append('Please select a year level.')

        if password1 != password2:
            errors.append('Passwords do not match.')

        if len(password1) < 8:
            errors.append('Password must be at least 8 characters.')

        from .models import User
        # Only block if the existing account is already verified/active
        # Unverified draft accounts can be overwritten by a new registration attempt
        existing_email = User.objects.filter(email=email).first()
        if existing_email and (existing_email.is_email_verified or existing_email.is_active):
            errors.append('An account with this email already exists.')
        elif existing_email and not existing_email.is_email_verified:
            # Clean up the stale unverified account so the new one can be created
            existing_email.delete()

        existing_id = User.objects.filter(student_id=student_id).first()
        if existing_id and (existing_id.is_email_verified or existing_id.is_active):
            errors.append('An account with this student ID already exists.')
        elif existing_id and not existing_id.is_email_verified:
            existing_id.delete()

        if not course_id:
            errors.append('Please select a course.')

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'accounts/register.html', {'courses': courses, 'post': request.POST})

        user = User.objects.create_user(
            email=email,
            password=password1,
            first_name=first_name,
            middle_initial=middle_initial,
            last_name=last_name,
            student_id=student_id,
            year_level=int(year_level) if year_level else 1,
            course_id=int(course_id) if course_id else None,
            is_active=False,
            is_email_verified=False,
        )
        
        # Audit log
        log_action(
            actor=user,
            action=AuditActions.USER_REGISTERED,
            target=user,
            details=f'Registered new account: {user.get_full_name()} ({user.student_id})',
            request=request
        )

        # Generate and send OTP
        import secrets
        from django.utils import timezone
        from datetime import timedelta
        from .models import OTPToken

        otp_code = str(secrets.randbelow(900000) + 100000)
        OTPToken.objects.create(
            user=user,
            otp_code=otp_code,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        # Send email
        from django.core.mail import send_mail
        send_mail(
            subject='UB-CSO Portal — Email Verification',
            message=f'Your verification code is: {otp_code}\n\nThis code expires in 10 minutes.',
            from_email='noreply@universityofbohol.edu.ph',
            recipient_list=[email],
            fail_silently=False,
        )

        request.session['verify_email'] = email
        messages.success(request, 'Account created! Please check your email for the verification code.')
        return redirect('accounts:verify_otp')

    return render(request, 'accounts/register.html', {'courses': courses})


LOCKED_FIELDS = ['first_name', 'middle_initial', 'last_name', 'student_id', 'course', 'year_level']

LOCKED_FIELD_LABELS = {
    'first_name': 'First name',
    'middle_initial': 'Middle initial',
    'last_name': 'Last name',
    'student_id': 'Student ID',
    'course': 'Course',
    'year_level': 'Year level',
}


@login_required
def submit_correction_request_view(request):
    if request.method != 'POST':
        return redirect('accounts:edit_profile')

    from .models import ProfileCorrectionRequest, Course
    from announcements.utils import send_notification

    field_name = request.POST.get('field_name', '').strip()
    new_value = request.POST.get('new_value', '').strip()
    reason = request.POST.get('reason', '').strip()

    # Validation
    if field_name not in LOCKED_FIELDS:
        messages.error(request, 'Invalid field selection.')
        return redirect('accounts:edit_profile')
    if not new_value:
        messages.error(request, 'New value cannot be empty.')
        return redirect('accounts:my_correction_requests')
    if not reason:
        messages.error(request, 'Please provide a reason for the correction.')
        return redirect('accounts:my_correction_requests')
    
    # Field-specific validation
    if field_name == 'year_level':
        try:
            year_value = int(new_value)
            if year_value < 1 or year_value > 10:
                messages.error(request, 'Year level must be between 1 and 10.')
                return redirect('accounts:my_correction_requests')
        except ValueError:
            messages.error(request, 'Year level must be a valid number.')
            return redirect('accounts:my_correction_requests')
    
    if field_name == 'middle_initial':
        if len(new_value) > 1:
            messages.error(request, 'Middle initial must be a single character.')
            return redirect('accounts:my_correction_requests')
        if not new_value.isalpha():
            messages.error(request, 'Middle initial must be a letter.')
            return redirect('accounts:my_correction_requests')
    
    if field_name == 'student_id':
        if len(new_value) < 4:
            messages.error(request, 'Student ID must be at least 4 characters.')
            return redirect('accounts:my_correction_requests')
        import re
        if not re.match(r'^[0-9\-]+$', new_value):
            messages.error(request, 'Student ID must contain only digits and hyphens (e.g. 2024-0001).')
            return redirect('accounts:my_correction_requests')
        # Check if student ID already exists
        from accounts.models import User
        if User.objects.filter(student_id=new_value).exclude(id=request.user.id).exists():
            messages.error(request, 'This student ID is already taken by another user.')
            return redirect('accounts:my_correction_requests')
    
    if field_name in ['first_name', 'last_name']:
        if len(new_value) < 2:
            messages.error(request, f'{LOCKED_FIELD_LABELS[field_name]} must be at least 2 characters.')
            return redirect('accounts:my_correction_requests')
        if not new_value.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').isalpha():
            messages.error(request, f'{LOCKED_FIELD_LABELS[field_name]} must contain only letters, spaces, hyphens, or parentheses.')
            return redirect('accounts:my_correction_requests')
    
    if field_name == 'course':
        try:
            Course.objects.get(id=int(new_value), is_active=True)
        except (Course.DoesNotExist, ValueError):
            messages.error(request, 'Invalid course selection.')
            return redirect('accounts:my_correction_requests')

    # Block duplicate pending requests for the same field
    if ProfileCorrectionRequest.objects.filter(
        user=request.user, field_name=field_name, status='pending'
    ).exists():
        messages.error(request, f'You already have a pending correction request for {LOCKED_FIELD_LABELS[field_name]}.')
        return redirect('accounts:my_correction_requests')

    # Capture old_value
    user = request.user
    if field_name == 'course':
        old_value = user.course.name if user.course else ''
    else:
        old_value = str(getattr(user, field_name, ''))

    ProfileCorrectionRequest.objects.create(
        user=user,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
        status='pending',
    )
    
    # Audit log
    log_action(
        actor=request.user,
        action=AuditActions.CORRECTION_REQUESTED,
        target=request.user,
        details=f'Requested correction for {field_name}: "{old_value}" → "{new_value}". Reason: {reason[:100]}',
        request=request
    )

    # Notify all CSO admins
    try:
        admins = list(User.objects.filter(
            is_active=True
        ).filter(
            models.Q(is_cso_admin=True) | models.Q(is_cso_president=True)
        ))
        if admins:
            from django.urls import reverse
            send_notification(
                title='New profile correction request',
                message=f'{user.get_full_name()} ({user.student_id}) submitted a correction request for {LOCKED_FIELD_LABELS[field_name]}.',
                recipients=admins,
                sender=user,
                link_url=reverse('core:admin_correction_requests'),
                notification_type='profile',
            )
    except Exception:
        pass

    messages.success(request, 'Correction request submitted successfully.')
    return redirect('accounts:my_correction_requests')


@login_required
def my_correction_requests_view(request):
    from .models import ProfileCorrectionRequest
    correction_requests = ProfileCorrectionRequest.objects.filter(
        user=request.user
    ).order_by('-created_at')
    # my_correction_requests_view
  
    courses = Course.objects.filter(is_active=True).order_by('department', 'name').distinct()
    return render(request, 'accounts/my_correction_requests.html', {
        'correction_requests': correction_requests,
        'locked_field_labels': LOCKED_FIELD_LABELS,
        'courses': courses,
    })


@login_required
def cancel_correction_request_view(request, request_id):
    from .models import ProfileCorrectionRequest
    
    if request.method != 'POST':
        return redirect('accounts:my_correction_requests')
    
    correction_request = get_object_or_404(
        ProfileCorrectionRequest,
        id=request_id,
        user=request.user,
        status='pending'
    )
    
    field_label = LOCKED_FIELD_LABELS.get(correction_request.field_name, correction_request.field_name)
    correction_request.delete()
    
    # Audit log
    log_action(
        actor=request.user,
        action=AuditActions.CORRECTION_REQUESTED,
        target=request.user,
        details=f'Cancelled correction request for {correction_request.field_name}',
        request=request
    )
    
    messages.success(request, f'Correction request for {field_label} has been cancelled.')
    return redirect('accounts:my_correction_requests')


@ratelimit(key='ip', rate='10/h', method='POST', block=True)
def verify_otp_view(request):
    email = request.session.get('verify_email')

    if not email:
        return redirect('accounts:register')

    if request.method == 'POST':
        from .models import OTPToken, User
        from django.utils import timezone

        entered_code = request.POST.get('otp_code', '').strip()

        try:
            user = User.objects.get(email=email, is_email_verified=False)
        except User.DoesNotExist:
            # Account no longer exists or was already verified — clear session and restart
            del request.session['verify_email']
            messages.error(request, 'This registration session is no longer valid. Please register again.')
            return redirect('accounts:register')

        try:
            token = OTPToken.objects.filter(
                user=user,
                is_used=False,
                expires_at__gt=timezone.now()
            ).latest('created_at')

            if token.otp_code == entered_code:
                token.is_used = True
                token.save()
                user.is_email_verified = True
                user.is_active = True
                user.save()
                del request.session['verify_email']
                messages.success(request, 'Email verified! You can now log in.')
                return redirect('accounts:login')
            else:
                messages.error(request, 'Invalid verification code. Please try again.')

        except OTPToken.DoesNotExist:
            messages.error(request, 'Your code has expired. Please request a new one.')
        except Exception:
            messages.error(request, 'Something went wrong. Please try again.')

    return render(request, 'accounts/verify_otp.html', {'email': email})


@login_required
def settings_view(request):
    if request.method == 'POST':
        user = request.user
        user.email_notifications = request.POST.get('email_notifications') == 'on'
        user.low_data_mode = request.POST.get('low_data_mode') == 'on'
        user.save(update_fields=['email_notifications', 'low_data_mode'])
        messages.success(request, 'Settings saved.')
        return redirect('accounts:settings')

    from core.models import SystemSetting
    system_settings = {s.key: s.value for s in SystemSetting.objects.filter(
        key__in=['admin_guide', 'welcome_message', 'system_rules']
    )}

    return render(request, 'accounts/settings.html', {
        'system_settings': system_settings,
    })


@ratelimit(key='ip', rate='5/h', method='POST', block=True)
def resend_otp_view(request):
    """Resend a fresh OTP to the email in the current registration session."""
    if request.method != 'POST':
        return redirect('accounts:verify_otp')

    email = request.session.get('verify_email')
    if not email:
        return redirect('accounts:register')

    from .models import OTPToken, User
    from django.utils import timezone
    from datetime import timedelta

    try:
        user = User.objects.get(email=email, is_email_verified=False)
    except User.DoesNotExist:
        del request.session['verify_email']
        messages.error(request, 'Registration session expired. Please register again.')
        return redirect('accounts:register')

    # Invalidate all existing unused tokens
    OTPToken.objects.filter(user=user, is_used=False).update(is_used=True)

    # Generate new OTP
    import secrets
    otp_code = str(secrets.randbelow(900000) + 100000)
    OTPToken.objects.create(
        user=user,
        otp_code=otp_code,
        expires_at=timezone.now() + timedelta(minutes=10),
    )

    from django.core.mail import send_mail
    send_mail(
        subject='UB-CSO Portal — New Verification Code',
        message=f'Your new verification code is: {otp_code}\n\nThis code expires in 10 minutes.',
        from_email='noreply@universityofbohol.edu.ph',
        recipient_list=[email],
        fail_silently=False,
    )

    messages.success(request, 'A new verification code has been sent to your email.')
    return redirect('accounts:verify_otp')


# ─── Faculty Registration ─────────────────────────────────────────────────────

@ratelimit(key='ip', rate='3/h', method='POST', block=True)
def faculty_register_view(request):
    """Faculty registration form — collects info, sends OTP, creates pending request."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        from .models import FacultyRegistrationRequest
        from django.utils import timezone
        from datetime import timedelta
        import secrets

        email = request.POST.get('email', '').strip().lower()
        first_name = request.POST.get('first_name', '').strip()
        middle_initial = request.POST.get('middle_initial', '').strip().rstrip('.').upper()
        last_name = request.POST.get('last_name', '').strip()
        employee_id = request.POST.get('employee_id', '').strip()
        department = request.POST.get('department', '').strip()
        password1 = request.POST.get('password1', '').strip()
        password2 = request.POST.get('password2', '').strip()

        errors = []

        if not email.endswith('@universityofbohol.edu.ph'):
            errors.append('You must use your university email (@universityofbohol.edu.ph).')
        if not first_name or len(first_name) < 2:
            errors.append('First name must be at least 2 characters.')
        if not last_name or len(last_name) < 2:
            errors.append('Last name must be at least 2 characters.')
        if not employee_id or len(employee_id) < 3:
            errors.append('Employee ID must be at least 3 characters.')
        if not department:
            errors.append('Department is required.')
        if password1 != password2:
            errors.append('Passwords do not match.')
        if len(password1) < 8:
            errors.append('Password must be at least 8 characters.')

        # Block if email already has an active account
        if User.objects.filter(email=email, is_active=True).exists():
            errors.append('An active account with this email already exists.')
        if User.objects.filter(employee_id=employee_id).exists():
            errors.append('An account with this employee ID already exists.')

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'accounts/faculty_register.html', {'post': request.POST})

        # Hash password
        from django.contrib.auth.hashers import make_password
        password_hash = make_password(password1)

        # Create or update pending request
        FacultyRegistrationRequest.objects.filter(email=email, status='pending_otp').delete()
        otp_code = str(secrets.randbelow(900000) + 100000)
        faculty_req = FacultyRegistrationRequest.objects.create(
            email=email,
            first_name=first_name,
            middle_initial=middle_initial or None,
            last_name=last_name,
            employee_id=employee_id,
            department=department,
            password_hash=password_hash,
            otp_code=otp_code,
            otp_expires_at=timezone.now() + timedelta(minutes=10),
            status='pending_otp',
        )

        # Send OTP
        from django.core.mail import send_mail
        send_mail(
            subject='UB-CSO Portal — Faculty Registration Verification',
            message=(
                f'Your verification code is: {otp_code}\n\n'
                'This code expires in 10 minutes.\n\n'
                'After verification, your registration will be reviewed by the CSO Admin.'
            ),
            from_email='noreply@universityofbohol.edu.ph',
            recipient_list=[email],
            fail_silently=False,
        )

        request.session['faculty_verify_email'] = email
        messages.success(request, 'Please check your email for the verification code.')
        return redirect('accounts:faculty_verify_otp')

    return render(request, 'accounts/faculty_register.html')


@ratelimit(key='ip', rate='10/h', method='POST', block=True)
def faculty_verify_otp_view(request):
    """Verify OTP for faculty registration request."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    email = request.session.get('faculty_verify_email')
    if not email:
        return redirect('accounts:faculty_register')

    from .models import FacultyRegistrationRequest
    from django.utils import timezone

    try:
        faculty_req = FacultyRegistrationRequest.objects.get(email=email, status='pending_otp')
    except FacultyRegistrationRequest.DoesNotExist:
        del request.session['faculty_verify_email']
        messages.error(request, 'Registration session expired. Please register again.')
        return redirect('accounts:faculty_register')

    if request.method == 'POST':
        entered_code = request.POST.get('otp_code', '').strip()

        if faculty_req.otp_expires_at < timezone.now():
            messages.error(request, 'Your code has expired. Please request a new one.')
        elif faculty_req.otp_code == entered_code:
            faculty_req.otp_verified = True
            faculty_req.status = 'pending_approval'
            faculty_req.save(update_fields=['otp_verified', 'status'])
            del request.session['faculty_verify_email']

            # Notify CSO admins
            try:
                from announcements.utils import send_notification
                from django.urls import reverse
                admins = list(User.objects.filter(
                    is_active=True
                ).filter(
                    __import__('django.db.models', fromlist=['Q']).Q(is_cso_admin=True) |
                    __import__('django.db.models', fromlist=['Q']).Q(is_cso_president=True)
                ))
                if admins:
                    send_notification(
                        title='New faculty registration request',
                        message=f'{faculty_req.get_full_name()} ({faculty_req.email}) has submitted a faculty registration request.',
                        recipients=admins,
                        link_url=reverse('core:admin_faculty_requests'),
                        notification_type='system',
                    )
            except Exception:
                pass

            messages.success(request, 'Email verified! Your registration is pending CSO Admin approval. You will be notified by email once reviewed.')
            return redirect('accounts:login')
        else:
            messages.error(request, 'Invalid verification code. Please try again.')

    return render(request, 'accounts/faculty_verify_otp.html', {'email': email})


@ratelimit(key='ip', rate='5/h', method='POST', block=True)
def faculty_resend_otp_view(request):
    """Resend OTP for faculty registration."""
    if request.method != 'POST':
        return redirect('accounts:faculty_verify_otp')

    email = request.session.get('faculty_verify_email')
    if not email:
        return redirect('accounts:faculty_register')

    from .models import FacultyRegistrationRequest
    from django.utils import timezone
    from datetime import timedelta
    import secrets

    try:
        faculty_req = FacultyRegistrationRequest.objects.get(email=email, status='pending_otp')
    except FacultyRegistrationRequest.DoesNotExist:
        del request.session['faculty_verify_email']
        return redirect('accounts:faculty_register')

    otp_code = str(secrets.randbelow(900000) + 100000)
    faculty_req.otp_code = otp_code
    faculty_req.otp_expires_at = timezone.now() + timedelta(minutes=10)
    faculty_req.save(update_fields=['otp_code', 'otp_expires_at'])

    from django.core.mail import send_mail
    send_mail(
        subject='UB-CSO Portal — New Verification Code',
        message=f'Your new verification code is: {otp_code}\n\nThis code expires in 10 minutes.',
        from_email='noreply@universityofbohol.edu.ph',
        recipient_list=[email],
        fail_silently=False,
    )

    messages.success(request, 'A new verification code has been sent to your email.')
    return redirect('accounts:faculty_verify_otp')

@ratelimit(key='ip', rate='3/h', method='POST', block=True)
def faculty_register_view(request):
    """Faculty registration form — collects info, sends OTP, creates pending request."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        from .models import FacultyRegistrationRequest
        from django.utils import timezone
        from datetime import timedelta
        import secrets
        from django.contrib.auth.hashers import make_password

        email = request.POST.get('email', '').strip().lower()
        first_name = request.POST.get('first_name', '').strip()
        middle_initial = request.POST.get('middle_initial', '').strip().rstrip('.').upper()
        last_name = request.POST.get('last_name', '').strip()
        employee_id = request.POST.get('employee_id', '').strip()
        department = request.POST.get('department', '').strip()
        password1 = request.POST.get('password1', '').strip()
        password2 = request.POST.get('password2', '').strip()

        errors = []

        if not email.endswith('@universityofbohol.edu.ph'):
            errors.append('You must use your university email (@universityofbohol.edu.ph).')
        if not first_name or len(first_name) < 2:
            errors.append('First name must be at least 2 characters.')
        if not last_name or len(last_name) < 2:
            errors.append('Last name must be at least 2 characters.')
        if not employee_id or len(employee_id) < 3:
            errors.append('Employee ID must be at least 3 characters.')
        if not department:
            errors.append('Department is required.')
        if password1 != password2:
            errors.append('Passwords do not match.')
        if len(password1) < 8:
            errors.append('Password must be at least 8 characters.')

        if User.objects.filter(email=email, is_active=True).exists():
            errors.append('An active account with this email already exists.')
        if User.objects.filter(employee_id=employee_id).exists():
            errors.append('An account with this employee ID already exists.')

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'accounts/faculty_register.html', {'post': request.POST})

        password_hash = make_password(password1)

        # Remove any stale pending_otp requests for this email
        FacultyRegistrationRequest.objects.filter(email=email, status='pending_otp').delete()

        otp_code = str(secrets.randbelow(900000) + 100000)
        from django.utils import timezone as _tz
        from datetime import timedelta as _td
        FacultyRegistrationRequest.objects.create(
            email=email,
            first_name=first_name,
            middle_initial=middle_initial or None,
            last_name=last_name,
            employee_id=employee_id,
            department=department,
            password_hash=password_hash,
            otp_code=otp_code,
            otp_expires_at=_tz.now() + _td(minutes=10),
            status='pending_otp',
        )

        from django.core.mail import send_mail
        send_mail(
            subject='UB-CSO Portal — Faculty Registration Verification',
            message=(
                f'Your verification code is: {otp_code}\n\n'
                'This code expires in 10 minutes.\n\n'
                'After verification, your request will be reviewed by the CSO Admin.'
            ),
            from_email='noreply@universityofbohol.edu.ph',
            recipient_list=[email],
            fail_silently=False,
        )

        request.session['faculty_verify_email'] = email
        messages.success(request, 'Please check your email for the verification code.')
        return redirect('accounts:faculty_verify_otp')

    return render(request, 'accounts/faculty_register.html')


@ratelimit(key='ip', rate='10/h', method='POST', block=True)
def faculty_verify_otp_view(request):
    """Verify OTP for faculty registration request."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    email = request.session.get('faculty_verify_email')
    if not email:
        return redirect('accounts:faculty_register')

    from .models import FacultyRegistrationRequest
    from django.utils import timezone as _tz

    try:
        faculty_req = FacultyRegistrationRequest.objects.get(email=email, status='pending_otp')
    except FacultyRegistrationRequest.DoesNotExist:
        if 'faculty_verify_email' in request.session:
            del request.session['faculty_verify_email']
        messages.error(request, 'Registration session expired. Please register again.')
        return redirect('accounts:faculty_register')

    if request.method == 'POST':
        entered_code = request.POST.get('otp_code', '').strip()

        if faculty_req.otp_expires_at < _tz.now():
            messages.error(request, 'Your code has expired. Please request a new one.')
        elif faculty_req.otp_code == entered_code:
            faculty_req.otp_verified = True
            faculty_req.status = 'pending_approval'
            faculty_req.save(update_fields=['otp_verified', 'status'])
            del request.session['faculty_verify_email']

            # Notify CSO admins
            try:
                from announcements.utils import send_notification
                from django.urls import reverse
                from django.db.models import Q as _Q
                admins = list(User.objects.filter(
                    is_active=True
                ).filter(_Q(is_cso_admin=True) | _Q(is_cso_president=True)))
                if admins:
                    send_notification(
                        title='New faculty registration request',
                        message=f'{faculty_req.get_full_name()} ({faculty_req.email}) submitted a faculty registration request.',
                        recipients=admins,
                        link_url=reverse('core:admin_faculty_requests'),
                        notification_type='system',
                    )
            except Exception:
                pass

            messages.success(request, 'Email verified! Your registration is pending CSO Admin approval. You will be notified by email once reviewed.')
            return redirect('accounts:login')
        else:
            messages.error(request, 'Invalid verification code. Please try again.')

    return render(request, 'accounts/faculty_verify_otp.html', {'email': email})


@ratelimit(key='ip', rate='5/h', method='POST', block=True)
def faculty_resend_otp_view(request):
    """Resend OTP for faculty registration."""
    if request.method != 'POST':
        return redirect('accounts:faculty_verify_otp')

    email = request.session.get('faculty_verify_email')
    if not email:
        return redirect('accounts:faculty_register')

    from .models import FacultyRegistrationRequest
    from django.utils import timezone as _tz
    from datetime import timedelta as _td
    import secrets

    try:
        faculty_req = FacultyRegistrationRequest.objects.get(email=email, status='pending_otp')
    except FacultyRegistrationRequest.DoesNotExist:
        if 'faculty_verify_email' in request.session:
            del request.session['faculty_verify_email']
        return redirect('accounts:faculty_register')

    otp_code = str(secrets.randbelow(900000) + 100000)
    faculty_req.otp_code = otp_code
    faculty_req.otp_expires_at = _tz.now() + _td(minutes=10)
    faculty_req.save(update_fields=['otp_code', 'otp_expires_at'])

    from django.core.mail import send_mail
    send_mail(
        subject='UB-CSO Portal — New Verification Code',
        message=f'Your new verification code is: {otp_code}\n\nThis code expires in 10 minutes.',
        from_email='noreply@universityofbohol.edu.ph',
        recipient_list=[email],
        fail_silently=False,
    )

    messages.success(request, 'A new verification code has been sent to your email.')
    return redirect('accounts:faculty_verify_otp')
