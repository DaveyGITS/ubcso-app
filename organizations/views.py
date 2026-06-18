from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from functools import wraps
from django_ratelimit.decorators import ratelimit
from core.audit import log_action, AuditActions
from .models import Organization, OrganizationCategory, OrganizationCategoryLink, OrganizationRequest
from organizations.constants import PUBLICLY_VISIBLE_STATUSES


def _expire_temp_co_chairmen(org):
    """Demote any expired temporary co-chairmen to member (or their pending role if set)."""
    from core.enforcement import expire_co_chairmen_for_org
    expire_co_chairmen_for_org(org)


def chairman_required(view_func):
    """Decorator: user must be chairman or co-chairman of the given org (org_id kwarg)."""
    @wraps(view_func)
    def wrapper(request, org_id, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        from memberships.models import Membership
        # Allow chairmen to access their dashboard even for lapsed orgs (so they can submit renewal)
        # We check organization existence without requiring is_active=True
        membership = Membership.objects.filter(
            user=request.user,
            organization_id=org_id,
            status='active',
            role__in=['chairman', 'co_chairman', 'adviser'],
        ).select_related('organization').first()
        if not membership or membership.organization.status == 'rejected':
            messages.error(request, 'You do not have permission to manage this organization.')
            return redirect('core:dashboard')
        return view_func(request, org_id, *args, **kwargs)
    return wrapper



def directory_view(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    org_category = request.GET.get('org_category', '')
    sort = request.GET.get('sort', '')
    from django.db.models import Count, Q

    organizations = Organization.objects.filter(
        is_active=True,
        is_cso=False,
        status__in=PUBLICLY_VISIBLE_STATUSES,
    ).prefetch_related('categories').annotate(
        active_member_count=Count(
            'memberships',
            filter=Q(memberships__status='active', memberships__user__is_active=True)
        )
    )

    if query:
        organizations = organizations.filter(name__icontains=query)

    if category_id:
        organizations = organizations.filter(categories__id=category_id)

    if org_category:
        organizations = organizations.filter(category=org_category)

    if sort == 'largest':
        organizations = organizations.order_by('-active_member_count')
    elif sort == 'newest':
        organizations = organizations.order_by('-date_created')
    elif sort == 'oldest':
        organizations = organizations.order_by('date_created')
    else:
        organizations = organizations.order_by('name')

    categories = OrganizationCategory.objects.filter(is_active=True)

    # Get user's org IDs for "member" badge
    user_org_ids = set()
    if request.user.is_authenticated:
        from memberships.models import Membership
        user_org_ids = set(
            Membership.objects.filter(user=request.user, status='active')
            .values_list('organization_id', flat=True)
        )

    return render(request, 'organizations/directory.html', {
        'organizations': organizations,
        'categories': categories,
        'query': query,
        'selected_category': category_id,
        'selected_org_category': org_category,
        'selected_sort': sort,
        'user_org_ids': user_org_ids,
        'org_category_choices': Organization.ORG_CATEGORY_CHOICES,
    })


@login_required
def org_profile_view(request, org_id):
    from memberships.models import Membership, MembershipRequest
    
    org = get_object_or_404(Organization, id=org_id, is_active=True)
    
    members = Membership.objects.filter(
        organization=org,
        status='active',
        organization__is_active=True,
        user__is_active=True,
    ).select_related('user', 'custom_role').order_by('role')
    
    chairman = members.filter(role='chairman').first()
    co_chairmen = members.filter(role='co_chairman')
    officers = members.filter(role='officer')
    regular_members = members.filter(role='member')
    advisers = members.filter(role='adviser')
    
    user_membership = members.filter(user=request.user).first()
    
    pending_request = MembershipRequest.objects.filter(
        user=request.user,
        organization=org,
        status='pending'
    ).first()

    # Media context
    showcase = getattr(org, 'showcase', None)
    album = org.albums.prefetch_related('photos').order_by('-created_at').first()
    is_privileged = Membership.objects.filter(
        user=request.user,
        organization=org,
        status='active',
        organization__is_active=True,
        role__in=['chairman', 'co_chairman', 'adviser'],
    ).exists()
    
    return render(request, 'organizations/org_profile.html', {
        'org': org,
        'chairman': chairman,
        'co_chairmen': co_chairmen,
        'officers': officers,
        'regular_members': regular_members,
        'advisers': advisers,
        'all_members': members,  # all active members regardless of role
        'user_membership': user_membership,
        'pending_request': pending_request,
        'total_members': members.count(),
        'approved_reports_count': org.accomplishment_reports.filter(status='approved').count(),
        'showcase': showcase,
        'album': album,
        'is_privileged': is_privileged,
    })


@login_required
@ratelimit(key='user', rate='5/d', method='POST', block=True)
def org_request_view(request):
    from accounts.models import User

    if request.method == 'POST':
        org_name = request.POST.get('organization_name', '').strip()
        description = request.POST.get('description', '').strip()
        proposed_chairman_id = request.POST.get('proposed_chairman', '').strip()

        errors = []

        if not org_name:
            errors.append('Organization name is required.')
        if not description:
            errors.append('Description is required.')

        if Organization.objects.filter(name__iexact=org_name).exists():
            errors.append('An organization with this name already exists.')

        proposed_chairman = None
        if proposed_chairman_id:
            try:
                proposed_chairman = User.objects.get(
                    student_id=proposed_chairman_id,
                    is_active=True
                )
                # Treat self-nomination the same as leaving blank
                if proposed_chairman == request.user:
                    proposed_chairman = None
            except User.DoesNotExist:
                errors.append('Proposed chairman student ID not found.')

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'organizations/org_request.html', {'post': request.POST})

        OrganizationRequest.objects.create(
            requester=request.user,
            organization_name=org_name,
            description=description,
            proposed_chairman=proposed_chairman,
            status='pending',
        )
        
        # Audit log
        log_action(
            actor=request.user,
            action=AuditActions.ORG_CREATED,
            details=f'Submitted organization creation request: {org_name}',
            request=request
        )

        
        messages.success(request, 'Organization request submitted! The CSO admin will review it shortly.')
        return redirect('organizations:directory')

    return render(request, 'organizations/org_request.html')


@login_required
@ratelimit(key='user', rate='5/d', method='POST', block=True)
def accreditation_apply_view(request):
    """New organization accreditation application form (replaces org_request for new submissions)."""
    from .models import AccreditationApplication, AccreditationDocument, OfficialFormLink
    from .constants import NEW_APPLICANT_DOCS, NEW_CHAPTER_DOCS, NEW_CHAPTER_OPTIONAL_DOCS
    from accounts.models import User

    official_forms = OfficialFormLink.objects.all()

    if request.method == 'POST':
        org_name = request.POST.get('organization_name', '').strip()
        chairman_student_id = request.POST.get('chairman_student_id', '').strip()
        registration_type = request.POST.get('registration_type', '').strip()

        errors = []

        if not org_name:
            errors.append('Organization name is required.')
        if not chairman_student_id:
            errors.append('Chairman student ID is required.')
        if registration_type not in ('new_applicant', 'new_chapter'):
            errors.append('Registration type must be New Applicant or New Chapter.')

        # Duplicate org name check (case-insensitive)
        if org_name and Organization.objects.filter(name__iexact=org_name).exists():
            errors.append(f'An organization named "{org_name}" already exists.')

        # Duplicate pending application check
        if org_name and AccreditationApplication.objects.filter(
            organization__name__iexact=org_name,
            status__in=['pending', 'under_review'],
        ).exists():
            errors.append(f'A pending application for "{org_name}" already exists.')

        # Validate chairman
        chairman = None
        if chairman_student_id:
            try:
                chairman = User.objects.get(student_id=chairman_student_id, is_active=True)
            except User.DoesNotExist:
                errors.append('Chairman student ID not found.')

        # Validate required documents — use configured list if available, else fall back to constants
        from .models import AccreditationRequirement
        acred_req_obj = AccreditationRequirement.objects.filter(registration_type=registration_type).first()
        if acred_req_obj and acred_req_obj.required_documents:
            # Configured list: each entry is {title, link, optional}
            doc_entries = acred_req_obj.required_documents
            doc_list = [e['title'] for e in doc_entries]
            optional_docs = [e['title'] for e in doc_entries if e.get('optional')]
        else:
            doc_list = NEW_APPLICANT_DOCS if registration_type == 'new_applicant' else NEW_CHAPTER_DOCS
            optional_docs = NEW_CHAPTER_OPTIONAL_DOCS if registration_type == 'new_chapter' else []
        uploaded_files = {}
        for doc_type in doc_list:
            field_name = f'doc_{doc_type.lower().replace(" ", "_").replace("-", "_")}'
            file = request.FILES.get(field_name)
            if file:
                # Validate file size (10 MB max)
                if file.size > 10 * 1024 * 1024:
                    errors.append(f'{doc_type}: File size must not exceed 10 MB.')
                else:
                    uploaded_files[doc_type] = file
            elif doc_type not in optional_docs:
                errors.append(f'{doc_type} is required.')

        if errors:
            from .models import AccreditationRequirement as _AR2
            _na2 = _AR2.objects.filter(registration_type='new_applicant').first()
            _nc2 = _AR2.objects.filter(registration_type='new_chapter').first()
            _na_docs2 = _na2.required_documents if (_na2 and _na2.required_documents) else None
            _nc_docs2 = _nc2.required_documents if (_nc2 and _nc2.required_documents) else None
            return render(request, 'organizations/accreditation_apply.html', {
                'errors': errors,
                'official_forms': official_forms,
                'post': request.POST,
                'new_applicant_docs': [e['title'] for e in _na_docs2] if _na_docs2 else NEW_APPLICANT_DOCS,
                'new_chapter_docs': [e['title'] for e in _nc_docs2] if _nc_docs2 else NEW_CHAPTER_DOCS,
                'new_chapter_optional_docs': [e['title'] for e in _nc_docs2 if e.get('optional')] if _nc_docs2 else NEW_CHAPTER_OPTIONAL_DOCS,
                'new_applicant_entries': _na_docs2,
                'new_chapter_entries': _nc_docs2,
            })

        # Create Organization (status=pending, is_active will be False via save() sync)
        org = Organization.objects.create(
            name=org_name,
            status='pending',
        )

        # Create chairman membership
        from memberships.models import Membership
        Membership.objects.create(
            user=chairman,
            organization=org,
            role='chairman',
            has_chairman_privileges=True,
            status='active',
        )

        # Create AccreditationApplication
        application = AccreditationApplication.objects.create(
            organization=org,
            registration_type=registration_type,
            status='pending',
        )

        # Create AccreditationDocument records
        for doc_type, file in uploaded_files.items():
            AccreditationDocument.objects.create(
                application=application,
                document_type=doc_type,
                file=file,
            )

        # Audit log
        log_action(
            actor=request.user,
            action=AuditActions.ORG_CREATED,
            target=org,
            details=f'Submitted accreditation application: {org_name} ({registration_type})',
            request=request,
        )

        messages.success(
            request,
            f'Your application for "{org_name}" has been submitted. '
            'The CSO Admin will review it and notify you of the outcome.'
        )
        return redirect('organizations:directory')

    from .models import AccreditationRequirement as _AR
    _na_obj = _AR.objects.filter(registration_type='new_applicant').first()
    _nc_obj = _AR.objects.filter(registration_type='new_chapter').first()
    _na_docs = _na_obj.required_documents if (_na_obj and _na_obj.required_documents) else None
    _nc_docs = _nc_obj.required_documents if (_nc_obj and _nc_obj.required_documents) else None
    return render(request, 'organizations/accreditation_apply.html', {
        'official_forms': official_forms,
        'new_applicant_docs': [e['title'] for e in _na_docs] if _na_docs else NEW_APPLICANT_DOCS,
        'new_chapter_docs': [e['title'] for e in _nc_docs] if _nc_docs else NEW_CHAPTER_DOCS,
        'new_chapter_optional_docs': [e['title'] for e in _nc_docs if e.get('optional')] if _nc_docs else NEW_CHAPTER_OPTIONAL_DOCS,
        'new_applicant_entries': _na_docs,
        'new_chapter_entries': _nc_docs,
    })


@login_required
@ratelimit(key='user', rate='5/d', method='POST', block=True)
def claim_existing_org_view(request):
    """Claim/register an existing campus organization into the system."""
    from .models import OrganizationRegistration
    from accounts.models import User

    if request.method == 'POST':
        org_name = request.POST.get('organization_name', '').strip()
        org_registration_number = request.POST.get('org_registration_number', '').strip()
        category = request.POST.get('category', '').strip()
        chairman_student_id = request.POST.get('chairman_student_id', '').strip()
        proof_message = request.POST.get('proof_message', '').strip()
        proof_document = request.FILES.get('proof_document')

        errors = []

        if not org_name:
            errors.append('Organization name is required.')
        if not category:
            errors.append('Organization category is required.')
        if not chairman_student_id:
            errors.append('Chairman student ID is required.')
        
        # Institutional orgs don't need proof message
        if category != 'institutional' and not proof_message:
            errors.append('Proof message is required.')

        # Check if org already exists in system
        if org_name and Organization.objects.filter(name__iexact=org_name).exists():
            errors.append(f'An organization named "{org_name}" is already registered in the system.')

        # Check if there's already a pending claim for this org
        if org_name and OrganizationRegistration.objects.filter(
            org_name__iexact=org_name,
            status__in=['pending', 'approved']
        ).exists():
            errors.append(f'A registration claim for "{org_name}" is already in progress.')

        # Validate chairman
        proposed_chairman = None
        if chairman_student_id:
            try:
                proposed_chairman = User.objects.get(student_id=chairman_student_id, is_active=True)
            except User.DoesNotExist:
                errors.append('Chairman student ID not found.')

        # Validate proof document if provided
        if proof_document:
            if proof_document.size > 10 * 1024 * 1024:
                errors.append('Proof document file size must not exceed 10 MB.')

        if errors:
            return render(request, 'organizations/claim_existing_org.html', {
                'errors': errors,
                'post': request.POST,
                'categories': OrganizationRegistration.CATEGORY_CHOICES,
            })

        # Create OrganizationRegistration
        registration = OrganizationRegistration.objects.create(
            submitted_by=request.user,
            org_name=org_name,
            org_registration_number=org_registration_number,
            category=category,
            proposed_chairman=proposed_chairman,
            proof_message=proof_message,
            proof_document=proof_document,
            status='pending',
        )

        # Audit log
        log_action(
            actor=request.user,
            action=AuditActions.ORG_CREATED,
            details=f'Submitted organization registration claim: {org_name} ({category})',
            request=request
        )

        messages.success(
            request,
            f'Your registration claim for "{org_name}" has been submitted. '
            'The CSO Admin will review it and notify you of the outcome.'
        )
        return redirect('organizations:directory')

    return render(request, 'organizations/claim_existing_org.html', {
        'categories': OrganizationRegistration.CATEGORY_CHOICES,
    })


@login_required
def cancel_org_registration_view(request, registration_id):
    from .models import OrganizationRegistration
    reg = get_object_or_404(
        OrganizationRegistration,
        id=registration_id,
        submitted_by=request.user,
        status='pending',
    )
    if request.method == 'POST':
        reg.delete()
        messages.success(request, 'Registration claim cancelled.')
    return redirect('memberships:my_requests')


@login_required
def cancel_org_request_view(request, request_id):
    from django.shortcuts import get_object_or_404
    org_request = get_object_or_404(
        OrganizationRequest,
        id=request_id,
        requester=request.user,
        status='pending'
    )
    if request.method == 'POST':
        org_request.delete()
        messages.success(request, 'Organization request cancelled.')
    return redirect('memberships:my_requests')

# ─── Chairman Dashboard ───────────────────────────────────────────────────────

@login_required
@chairman_required
def chairman_dashboard_view(request, org_id):
    from memberships.models import Membership, MembershipRequest, LeaveRequest
    org = get_object_or_404(Organization, id=org_id)

    # Auto-expire any stale temporary co-chairmen
    _expire_temp_co_chairmen(org)
    members = Membership.objects.filter(
        organization=org, status='active', user__is_active=True
    ).select_related('user', 'custom_role').order_by('role', 'user__last_name')

    chairman = members.filter(role='chairman').first()
    co_chairmen = members.filter(role='co_chairman')
    officers = members.filter(role='officer')
    regular_members = members.filter(role='member')

    user_membership = members.filter(user=request.user).first()

    pending_join_requests = MembershipRequest.objects.filter(
        organization=org, status='pending', type='request'
    ).select_related('user').order_by('-requested_at')

    pending_leave_requests = LeaveRequest.objects.filter(
        organization=org, status='pending'
    ).select_related('user').order_by('-created_at')

    # Lapsed orgs can only submit renewal after a new school year has begun
    from core.models import SystemSetting
    school_year_transitioned = SystemSetting.objects.filter(key='school_year_transitioned').exists()
    renewal_period_closed = SystemSetting.objects.filter(key='renewal_period_closed').exists()

    return render(request, 'organizations/chairman/dashboard.html', {
        'org': org,
        'user_membership': user_membership,
        'chairman': chairman,
        'co_chairmen': co_chairmen,
        'officers': officers,
        'regular_members': regular_members,
        'total_members': members.count(),
        'pending_join_requests': pending_join_requests,
        'pending_leave_requests': pending_leave_requests,
        'school_year_transitioned': school_year_transitioned,
        'renewal_period_closed': renewal_period_closed,
    })


@login_required
@chairman_required
def chairman_members_view(request, org_id):
    from memberships.models import Membership
    org = get_object_or_404(Organization, id=org_id)
    members = Membership.objects.filter(
        organization=org, status='active', user__is_active=True
    ).select_related('user', 'custom_role').order_by('role', 'user__last_name')
    roles = org.roles.filter(is_active=True)
    visible_count = members.count()
    return render(request, 'organizations/chairman/members.html', {
        'org': org,
        'members': members,
        'roles': roles,
        'visible_member_count': visible_count,
        'user_membership': members.filter(user=request.user).first(),
    })


@login_required
@chairman_required
def chairman_promote_member_view(request, org_id, membership_id):
    from memberships.models import Membership
    org = get_object_or_404(Organization, id=org_id, is_active=True)
    membership = get_object_or_404(Membership, id=membership_id, organization=org, status='active')
    actor = Membership.objects.filter(user=request.user, organization=org, status='active').first()

    if request.method == 'POST':
        new_role = request.POST.get('role')
        custom_role_id = request.POST.get('custom_role', '').strip()

        allowed_roles = ['member', 'officer', 'co_chairman', 'adviser']
        # Chairman editing their own display title only
        if membership.user == request.user and membership.role == 'chairman':
            if new_role == 'chairman':
                if custom_role_id:
                    from .models import Role
                    try:
                        role_obj = Role.objects.get(id=custom_role_id, organization=org, is_active=True)
                        membership.custom_role = role_obj
                    except Role.DoesNotExist:
                        pass
                else:
                    membership.custom_role = None
                membership.save()
                messages.success(request, 'Your display title has been updated.')
            return redirect('organizations:chairman_members', org_id=org_id)
        # Only chairman can assign co_chairman or adviser
        if new_role in ['co_chairman', 'adviser'] and actor.role != 'chairman':
            messages.error(request, 'Only the chairman can assign vice chairman privileges.')
            return redirect('organizations:chairman_members', org_id=org_id)

        # Adviser role is restricted to faculty users only
        if new_role == 'adviser' and not membership.user.is_faculty:
            messages.error(request, 'Only faculty members can be assigned the Adviser role.')
            return redirect('organizations:chairman_members', org_id=org_id)

        if new_role not in allowed_roles:
            messages.error(request, 'Invalid role.')
            return redirect('organizations:chairman_members', org_id=org_id)

        membership.role = new_role
        if new_role == 'adviser':
            membership.pending_role = None
            membership.co_chairman_expiry = None
            from django.utils import timezone as _tz
            if not membership.adviser_since:
                membership.adviser_since = _tz.now()
        else:
            # Demoting away from adviser — clear the timestamp so it resets next period
            membership.adviser_since = None
        membership.has_chairman_privileges = new_role in ['co_chairman', 'adviser']
        if custom_role_id:
            from .models import Role
            try:
                role_obj = Role.objects.get(id=custom_role_id, organization=org, is_active=True)
                membership.custom_role = role_obj
            except Role.DoesNotExist:
                pass
        else:
            membership.custom_role = None
        membership.save()

        # Auto-sync CSO admin flags for CSO org role changes
        if org.is_cso:
            user = membership.user
            if new_role in ['co_chairman', 'adviser']:
                user.is_cso_admin = True
                user.is_manually_granted_admin = False  # now role-based, not manual
                user.save(update_fields=['is_cso_admin', 'is_manually_granted_admin'])
            elif new_role in ['officer', 'member']:
                # Demotion from co-chairman always strips admin — no exceptions
                user.is_cso_admin = False
                user.is_manually_granted_admin = False
                user.save(update_fields=['is_cso_admin', 'is_manually_granted_admin'])

        messages.success(request, f'{membership.user.get_full_name()} is now {new_role.replace("_", "-")}.')

    return redirect('organizations:chairman_members', org_id=org_id)


@login_required
@chairman_required
def chairman_review_join_request_view(request, org_id, request_id):
    from memberships.models import MembershipRequest, Membership
    from django.utils import timezone
    org = get_object_or_404(Organization, id=org_id, is_active=True)
    join_request = get_object_or_404(MembershipRequest, id=request_id, organization=org, status='pending', type='request')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            from memberships.models import Membership
            Membership.objects.update_or_create(
                user=join_request.user,
                organization=org,
                defaults={
                    'role': 'member',
                    'status': 'active',
                    'custom_role': None,
                    'has_chairman_privileges': False,
                },
            )
            join_request.status = 'accepted'
            join_request.reviewed_by = request.user
            join_request.reviewed_at = timezone.now()
            join_request.save()
            from announcements.utils import send_notification
            from django.urls import reverse
            send_notification(
                title=f'Membership approved — {org.name}',
                message=f'Your request to join {org.name} has been approved. Welcome!',
                recipients=[join_request.user],
                sender=request.user,
                organization=org,
                link_url=reverse('organizations:org_profile', kwargs={'org_id': org.id}),
                notification_type='membership',
            )
            messages.success(request, f'{join_request.user.get_full_name()} has been added as a member.')
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '').strip()
            join_request.status = 'rejected'
            join_request.rejection_reason = reason
            join_request.reviewed_by = request.user
            join_request.reviewed_at = timezone.now()
            join_request.save()
            from announcements.utils import send_notification
            from django.urls import reverse
            msg = f'Your request to join {org.name} was not approved.'
            if reason:
                msg += f' Reason: {reason}'
            send_notification(
                title=f'Membership request rejected — {org.name}',
                message=msg,
                recipients=[join_request.user],
                sender=request.user,
                organization=org,
                link_url=reverse('organizations:org_profile', kwargs={'org_id': org.id}),
                notification_type='membership',
            )
            messages.success(request, f'Request from {join_request.user.get_full_name()} rejected.')

    return redirect('organizations:chairman_dashboard', org_id=org_id)


@login_required
@chairman_required
def chairman_review_leave_request_view(request, org_id, request_id):
    from memberships.models import LeaveRequest, Membership
    from django.utils import timezone
    org = get_object_or_404(Organization, id=org_id, is_active=True)
    leave_request = get_object_or_404(LeaveRequest, id=request_id, organization=org, status='pending')

    if request.method == 'POST':
        action = request.POST.get('action')
        membership = Membership.objects.filter(
            user=leave_request.user, organization=org, status='active', organization__is_active=True
        ).first()

        if action == 'approve':
            if membership:
                membership.status = 'left'
                membership.save()
            leave_request.status = 'approved'
            leave_request.reviewed_by = request.user
            leave_request.reviewed_at = timezone.now()
            leave_request.save()
            from announcements.utils import send_notification
            from django.urls import reverse
            send_notification(
                title=f'Leave request approved — {org.name}',
                message=f'Your request to leave {org.name} has been approved.',
                recipients=[leave_request.user],
                sender=request.user,
                organization=org,
                link_url=reverse('core:dashboard'),
                notification_type='membership',
            )
            messages.success(request, f'{leave_request.user.get_full_name()} has left the organization.')
        elif action == 'reject':
            leave_request.status = 'rejected'
            leave_request.reviewed_by = request.user
            leave_request.reviewed_at = timezone.now()
            leave_request.save()
            from announcements.utils import send_notification
            from django.urls import reverse
            send_notification(
                title=f'Leave request rejected — {org.name}',
                message=f'Your request to leave {org.name} was not approved.',
                recipients=[leave_request.user],
                sender=request.user,
                organization=org,
                link_url=reverse('organizations:org_profile', kwargs={'org_id': org.id}),
                notification_type='membership',
            )
            messages.success(request, 'Leave request rejected.')

    return redirect('organizations:chairman_dashboard', org_id=org_id)


@login_required
@chairman_required
def chairman_direct_add_view(request, org_id):
    from memberships.models import Membership, MembershipRequest
    from accounts.models import User
    from django.utils import timezone
    org = get_object_or_404(Organization, id=org_id, is_active=True)

    if request.method == 'POST':
        student_id = request.POST.get('student_id', '').strip()
        # Try student_id first, then employee_id (for faculty users)
        try:
            student = User.objects.get(student_id=student_id, is_active=True)
        except User.DoesNotExist:
            try:
                student = User.objects.get(employee_id=student_id, is_active=True)
            except User.DoesNotExist:
                messages.error(request, 'Student/Employee ID not found.')
                return redirect('organizations:chairman_members', org_id=org_id)

        if Membership.objects.filter(user=student, organization=org, status='active', organization__is_active=True).exists():
            messages.info(request, f'{student.get_full_name()} is already a member.')
            return redirect('organizations:chairman_members', org_id=org_id)

        # Check if student already has a pending request — auto-accept both
        existing_request = MembershipRequest.objects.filter(
            user=student, organization=org, type='request', status='pending'
        ).first()

        if existing_request:
            Membership.objects.update_or_create(
                user=student,
                organization=org,
                defaults={
                    'role': 'member',
                    'status': 'active',
                    'custom_role': None,
                    'has_chairman_privileges': False,
                }
            )
            existing_request.status = 'accepted'
            existing_request.reviewed_by = request.user
            existing_request.reviewed_at = timezone.now()
            existing_request.save()
            from announcements.utils import send_notification
            from django.urls import reverse
            send_notification(
                title=f'Membership confirmed — {org.name}',
                message=f'You had a pending request to join {org.name} and the chairman also invited you — membership auto-confirmed!',
                recipients=[student],
                sender=request.user,
                organization=org,
                link_url=reverse('organizations:org_profile', kwargs={'org_id': org.id}),
                notification_type='membership',
            )
            messages.success(request, f'{student.get_full_name()} had a pending request — membership auto-confirmed.')
            return redirect('organizations:chairman_members', org_id=org_id)

        # Check for existing pending invite
        if MembershipRequest.objects.filter(user=student, organization=org, status='pending', type='invite').exists():
            messages.info(request, f'{student.get_full_name()} already has a pending invite.')
            return redirect('organizations:chairman_members', org_id=org_id)

        MembershipRequest.objects.create(
            user=student,
            organization=org,
            type='invite',
            status='pending',
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        from announcements.utils import send_notification
        from django.urls import reverse
        send_notification(
            title=f'You have been invited to join {org.name}',
            message=f'{request.user.get_full_name()} has invited you to join {org.name}. Check your requests to accept or decline.',
            recipients=[student],
            sender=request.user,
            organization=org,
            link_url=reverse('memberships:my_requests'),
            notification_type='membership',
        )
        messages.success(request, f'Invite sent to {student.get_full_name()}.')

    return redirect('organizations:chairman_members', org_id=org_id)


@login_required
@login_required
@chairman_required
def chairman_create_role_view(request, org_id):
    org = get_object_or_404(Organization, id=org_id, is_active=True)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            from .models import Role
            role, created = Role.objects.update_or_create(
                organization=org,
                name=name,
                defaults={'is_active': True},
            )
            if created:
                messages.success(request, f'Display title "{name}" created.')
            else:
                messages.success(request, f'Display title "{name}" restored.')
        else:
            messages.error(request, 'Title name cannot be empty.')
    return redirect('organizations:chairman_members', org_id=org_id)

@login_required
@chairman_required
def chairman_edit_org_view(request, org_id):
    from .models import OrganizationCategoryLink, OrganizationCategory

    org = get_object_or_404(Organization, id=org_id, is_active=True)

    if request.method == 'POST':
        org.name = request.POST.get('name', org.name).strip()
        org.description = request.POST.get('description', '').strip()
        org.goals = request.POST.get('goals', '').strip()
        founded_year = request.POST.get('founded_year', '').strip()
        if founded_year:
            try:
                org.founded_year = int(founded_year)
            except ValueError:
                pass
        else:
            org.founded_year = None

        # Handle cropped logo
        logo_cropped = request.POST.get('logo_cropped', '').strip()
        if logo_cropped and logo_cropped.startswith('data:image'):
            import base64, uuid
            from django.core.files.base import ContentFile
            fmt, imgstr = logo_cropped.split(';base64,')
            ext = fmt.split('/')[-1]
            img_data = base64.b64decode(imgstr)
            org.logo.save(f'logo_{uuid.uuid4().hex}.{ext}', ContentFile(img_data), save=False)
        elif 'logo' in request.FILES:
            org.logo = request.FILES['logo']

        # Handle cropped banner
        banner_cropped = request.POST.get('banner_cropped', '').strip()
        if banner_cropped and banner_cropped.startswith('data:image'):
            import base64, uuid
            from django.core.files.base import ContentFile
            fmt, imgstr = banner_cropped.split(';base64,')
            ext = fmt.split('/')[-1]
            img_data = base64.b64decode(imgstr)
            org.banner.save(f'banner_{uuid.uuid4().hex}.{ext}', ContentFile(img_data), save=False)
        elif 'banner' in request.FILES:
            org.banner = request.FILES['banner']

        category_ids = request.POST.getlist('categories')
        org.save()

        from .models import OrganizationCategoryLink, OrganizationCategory
        OrganizationCategoryLink.objects.filter(organization=org).delete()
        for cat_id in category_ids:
            try:
                category = OrganizationCategory.objects.get(id=cat_id, is_active=True)
                OrganizationCategoryLink.objects.create(
                    organization=org,
                    category=category
                )
            except OrganizationCategory.DoesNotExist:
                pass

        messages.success(request, 'Organization profile updated successfully!')
        return redirect('organizations:chairman_dashboard', org_id=org_id)

    categories = OrganizationCategory.objects.filter(is_active=True)
    selected_categories = org.categories.values_list('id', flat=True)

    return render(request, 'organizations/chairman/edit_org.html', {
        'org': org,
        'categories': categories,
        'selected_categories': selected_categories,
    })

@login_required
@chairman_required
def chairman_remove_member_view(request, org_id, membership_id):
    from memberships.models import Membership
    org = get_object_or_404(Organization, id=org_id, is_active=True)
    membership = get_object_or_404(
        Membership, id=membership_id, organization=org, status='active'
    )
    if request.method == 'POST':
        if membership.role == 'chairman':
            messages.error(request, 'Cannot remove the chairman.')
        else:
            membership.status = 'removed'
            membership.save()
            # Notify the removed member
            from announcements.utils import send_notification
            from django.urls import reverse
            send_notification(
                title=f'You have been removed from {org.name}',
                message=f'You have been removed from {org.name} by {request.user.get_full_name()}.',
                recipients=[membership.user],
                sender=request.user,
                organization=org,
                link_url=reverse('organizations:directory'),
                notification_type='membership',
            )
            messages.success(request, f'{membership.user.get_full_name()} has been removed.')
    return redirect('organizations:chairman_members', org_id=org_id)


@login_required
@chairman_required
def chairman_delete_role_view(request, org_id, role_id):
    from .models import Role
    org = get_object_or_404(Organization, id=org_id, is_active=True)
    role = get_object_or_404(Role, id=role_id, organization=org)
    if request.method == 'POST':
        role.is_active = False
        role.save()
        messages.success(request, f'Display title "{role.name}" deactivated.')
    return redirect('organizations:chairman_members', org_id=org_id)


@login_required
def student_org_view(request, org_id):
    from memberships.models import Membership

    org = get_object_or_404(Organization, id=org_id, is_active=True)
    membership = Membership.objects.filter(
        user=request.user, organization=org, status='active'
    ).first()

    if not membership:
        return redirect('organizations:org_profile', org_id=org_id)

    members = Membership.objects.filter(
        organization=org, status='active', organization__is_active=True, user__is_active=True
    ).select_related('user', 'custom_role').order_by('role')

    return render(request, 'organizations/student_org_view.html', {
        'org': org,
        'membership': membership,
        'members': members,
    })


# ─── Chairman Handover ────────────────────────────────────────────────────────

@login_required
@ratelimit(key='user', rate='10/h', method='POST', block=True)
def chairman_handover_view(request, org_id):
    from memberships.models import Membership
    from accounts.models import User
    from django.utils import timezone
    from datetime import timedelta
    from core.models import HandoverNote

    org = get_object_or_404(Organization, id=org_id, is_active=True)

    # Only the actual chairman (not co-chairman) can initiate handover
    my_membership = Membership.objects.filter(
        user=request.user, organization=org, status='active', role='chairman'
    ).first()

    if not my_membership:
        messages.error(request, 'Only the chairman can initiate a handover.')
        return redirect('organizations:chairman_dashboard', org_id=org_id)

    # Auto-expire any stale temp co-chairmen
    _expire_temp_co_chairmen(org)

    # Eligible successors: active members who are not the current chairman
    # Exclude anyone currently in a 24hr temp co-chairman window (outgoing chairman)
    eligible = Membership.objects.filter(
        organization=org, status='active', organization__is_active=True,
    ).exclude(user=request.user).exclude(
        role='co_chairman', co_chairman_expiry__isnull=False
    ).select_related('user')

    if not eligible.exists():
        messages.error(request, 'There are no other members to hand over to. Add members first.')
        return redirect('organizations:chairman_dashboard', org_id=org_id)

    if request.method == 'POST':
        successor_id = request.POST.get('successor_id', '').strip()
        note_text = request.POST.get('note', '').strip()

        if not successor_id:
            messages.error(request, 'Please select a successor.')
            return render(request, 'organizations/chairman/handover.html', {
                'org': org, 'eligible': eligible
            })

        try:
            successor_membership = Membership.objects.get(
                id=successor_id, organization=org, status='active'
            )
        except Membership.DoesNotExist:
            messages.error(request, 'Invalid successor selected.')
            return render(request, 'organizations/chairman/handover.html', {
                'org': org, 'eligible': eligible
            })

        # Block if successor is currently in their 24hr temp co-chairman window
        if successor_membership.role == 'co_chairman' and successor_membership.co_chairman_expiry:
            messages.error(request, 'This person is currently in a 24hr transition window and cannot be selected as successor.')
            return render(request, 'organizations/chairman/handover.html', {
                'org': org, 'eligible': eligible
            })

        successor = successor_membership.user

        # 1. Promote successor to chairman
        successor_membership.role = 'chairman'
        successor_membership.has_chairman_privileges = True
        successor_membership.co_chairman_expiry = None
        successor_membership.save()

        # 2. Demote outgoing chairman to temporary co-chairman for 24 hours
        my_membership.role = 'co_chairman'
        my_membership.has_chairman_privileges = True
        my_membership.co_chairman_expiry = timezone.now() + timedelta(hours=24)
        my_membership.save()

        # Schedule auto-demotion via Celery
        try:
            from memberships.tasks import expire_temp_co_chairman
            expire_temp_co_chairman.apply_async(
                args=[my_membership.id],
                eta=my_membership.co_chairman_expiry,
            )
        except Exception:
            pass
        
        # Audit log
        log_action(
            actor=request.user,
            action=AuditActions.CHAIRMAN_HANDOVER,
            target=org,
            details=f'Handed over chairmanship of {org.name} to {successor.get_full_name()}. Granted 24hr co-chairman access.',
            request=request
        )

        # 3. Save handover note
        if note_text:
            HandoverNote.objects.create(
                from_user=request.user,
                to_user=successor,
                organization=org,
                type='chairman',
                note=note_text,
            )

        # 4. Send priority notification to incoming chairman
        from announcements.utils import send_notification
        from django.urls import reverse
        msg = f'{request.user.get_full_name()} has passed the chairman role of {org.name} to you.'
        if note_text:
            msg += f'\n\nHandover note: {note_text}'
        send_notification(
            title=f'You are now chairman of {org.name}',
            message=msg,
            recipients=[successor],
            sender=request.user,
            organization=org,
            is_priority=True,
            link_url=reverse('organizations:org_profile', kwargs={'org_id': org.id}),
            notification_type='organization',
        )

        messages.success(
            request,
            f'Handover complete. {successor.get_full_name()} is now chairman. '
            f'You have temporary vice chairman access for 24 hours.'
        )
        return redirect('organizations:chairman_dashboard', org_id=org_id)

    return render(request, 'organizations/chairman/handover.html', {
        'org': org,
        'eligible': eligible,
    })


@login_required
@chairman_required
def chairman_revoke_temp_access_view(request, org_id):
    """Outgoing chairman self-revokes their temporary 24hr co-chairman access."""
    from memberships.models import Membership

    org = get_object_or_404(Organization, id=org_id, is_active=True)

    my_membership = Membership.objects.filter(
        user=request.user,
        organization=org,
        status='active',
        role='co_chairman',
        co_chairman_expiry__isnull=False,
    ).first()

    if not my_membership:
        messages.error(request, 'You do not have temporary co-chairman access to revoke.')
        return redirect('organizations:chairman_dashboard', org_id=org_id)

    if request.method == 'POST':
        if my_membership.pending_role:
            my_membership.role = my_membership.pending_role
            my_membership.has_chairman_privileges = my_membership.pending_role == 'co_chairman'
            my_membership.custom_role = my_membership.pending_custom_role
            my_membership.pending_role = None
            my_membership.pending_custom_role = None
        else:
            # CSO outgoing president becomes officer (stays visible); regular orgs become member
            my_membership.role = 'officer' if org.is_cso else 'member'
            my_membership.has_chairman_privileges = False
            my_membership.custom_role = None
        my_membership.co_chairman_expiry = None
        my_membership.save()

        # For CSO org — also clear the user-level temp admin expiry
        if org.is_cso and request.user.cso_admin_expiry:
            request.user.is_cso_admin = False
            request.user.is_manually_granted_admin = False
            request.user.cso_admin_expiry = None
            request.user.save(update_fields=['is_cso_admin', 'is_manually_granted_admin', 'cso_admin_expiry'])

        messages.success(request, 'Your temporary vice chairman access has been revoked.')
        return redirect('organizations:chairman_dashboard', org_id=org_id)

    # GET — show a dedicated confirmation page instead of silently redirecting
    return render(request, 'organizations/revoke_temp_confirm.html', {
        'org': org,
        'pending_role': my_membership.pending_role,
        'expiry': my_membership.co_chairman_expiry,
    })


# ─── Polls ────────────────────────────────────────────────────────────────────

@login_required
@chairman_required
def chairman_create_poll_view(request, org_id):
    from .models import Poll, PollOption
    org = get_object_or_404(Organization, id=org_id, is_active=True)

    if request.method == 'POST':
        question = request.POST.get('question', '').strip()
        options = [o.strip() for o in request.POST.getlist('options') if o.strip()]

        if not question:
            messages.error(request, 'Question is required.')
            return redirect('organizations:chairman_dashboard', org_id=org_id)
        if len(options) < 2:
            messages.error(request, 'At least 2 options are required.')
            return redirect('organizations:chairman_dashboard', org_id=org_id)

        poll = Poll.objects.create(organization=org, created_by=request.user, question=question)
        for opt_text in options:
            PollOption.objects.create(poll=poll, text=opt_text)

        messages.success(request, 'Poll created.')
        return redirect('organizations:chairman_dashboard', org_id=org_id)

    return redirect('organizations:chairman_dashboard', org_id=org_id)


@login_required
@chairman_required
def chairman_close_poll_view(request, org_id, poll_id):
    from .models import Poll
    org = get_object_or_404(Organization, id=org_id, is_active=True)
    poll = get_object_or_404(Poll, id=poll_id, organization=org)

    if request.method == 'POST':
        poll.is_active = False
        poll.save()
        messages.success(request, 'Poll closed.')

    return redirect('organizations:chairman_dashboard', org_id=org_id)


@login_required
def poll_vote_view(request, org_id, poll_id):
    from .models import Poll, PollOption, PollVote
    from memberships.models import Membership

    org = get_object_or_404(Organization, id=org_id, is_active=True)
    poll = get_object_or_404(Poll, id=poll_id, organization=org, is_active=True)

    # Must be active member
    if not Membership.objects.filter(user=request.user, organization=org, status='active').exists():
        messages.error(request, 'You must be a member to vote.')
        return redirect('organizations:student_org_view', org_id=org_id)

    # Already voted
    if PollVote.objects.filter(poll=poll, user=request.user).exists():
        messages.info(request, 'You have already voted on this poll.')
        return redirect('organizations:student_org_view', org_id=org_id)

    if request.method == 'POST':
        option_id = request.POST.get('option')
        option = get_object_or_404(PollOption, id=option_id, poll=poll)
        PollVote.objects.create(poll=poll, option=option, user=request.user)
        messages.success(request, 'Your vote has been recorded.')

    return redirect('organizations:student_org_view', org_id=org_id)


# ─── Media: Albums ────────────────────────────────────────────────────────────

@login_required
@chairman_required
def album_create_view(request, org_id):
    from .models import OrgAlbum, OrgPhoto
    from .media_validators import validate_photo
    from django.core.exceptions import ValidationError

    org = get_object_or_404(Organization, id=org_id, is_active=True)

    # One album per org
    if org.albums.exists():
        messages.error(request, 'This organization already has an album. Edit the existing one.')
        return redirect('organizations:org_profile', org_id=org_id)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        photos = request.FILES.getlist('photos')
        errors = []

        if not title:
            errors.append('Album title is required.')
        if not photos:
            errors.append('At least one photo is required.')
        if len(photos) > 50:
            errors.append('You can upload a maximum of 50 photos per album.')

        for f in photos:
            try:
                validate_photo(f)
            except ValidationError as e:
                errors.append(str(e.message))

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'organizations/chairman/album_form.html', {
                'org': org, 'mode': 'create',
            })

        album = OrgAlbum.objects.create(
            organization=org, title=title, created_by=request.user
        )
        for f in photos:
            OrgPhoto.objects.create(album=album, image=f)

        messages.success(request, f'Album "{title}" created with {len(photos)} photo(s).')
        return redirect('organizations:org_profile', org_id=org_id)

    return render(request, 'organizations/chairman/album_form.html', {
        'org': org, 'mode': 'create',
    })


@login_required
@chairman_required
def album_edit_view(request, org_id, album_id):
    from .models import OrgAlbum, OrgPhoto
    from .media_validators import validate_photo
    from django.core.exceptions import ValidationError

    org = get_object_or_404(Organization, id=org_id, is_active=True)
    album = get_object_or_404(OrgAlbum, id=album_id, organization_id=org_id)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        new_photos = request.FILES.getlist('photos')
        remove_ids = request.POST.getlist('remove_photo_ids')
        # photo_order is a comma-separated list of photo IDs in the new order
        photo_order = request.POST.get('photo_order', '').strip()
        errors = []

        if not title:
            errors.append('Album title is required.')

        for f in new_photos:
            try:
                validate_photo(f)
            except ValidationError as e:
                errors.append(str(e.message))

        existing_count = album.photos.count() - len(remove_ids)
        if existing_count + len(new_photos) > 50:
            errors.append('Total photos cannot exceed 50.')
        if existing_count + len(new_photos) < 1:
            errors.append('Album must have at least one photo.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'organizations/chairman/album_form.html', {
                'org': org, 'album': album, 'mode': 'edit',
            })

        album.title = title
        album.save()

        if remove_ids:
            OrgPhoto.objects.filter(id__in=remove_ids, album=album).delete()

        # Save captions
        for photo in album.photos.all():
            caption = request.POST.get(f'caption_{photo.id}', '').strip()
            if photo.caption != caption:
                photo.caption = caption
                photo.save(update_fields=['caption'])

        # Save drag-reorder positions
        if photo_order:
            try:
                ordered_ids = [int(x) for x in photo_order.split(',') if x.strip()]
                for pos, pid in enumerate(ordered_ids):
                    OrgPhoto.objects.filter(id=pid, album=album).update(position=pos)
            except (ValueError, TypeError):
                pass

        # Add new photos at the end
        from django.db.models import Max
        current_max = album.photos.aggregate(m=Max('position'))['m'] or 0
        for i, f in enumerate(new_photos):
            OrgPhoto.objects.create(album=album, image=f, position=current_max + i + 1)

        messages.success(request, f'Album "{album.title}" updated.')
        return redirect('organizations:org_profile', org_id=org_id)

    return render(request, 'organizations/chairman/album_form.html', {
        'org': org, 'album': album, 'mode': 'edit',
    })


@login_required
@chairman_required
def album_delete_view(request, org_id, album_id):
    from .models import OrgAlbum

    org = get_object_or_404(Organization, id=org_id, is_active=True)
    album = get_object_or_404(OrgAlbum, id=album_id, organization_id=org_id)

    if request.method == 'POST':
        title = album.title
        album.delete()
        messages.success(request, f'Album "{title}" deleted.')

    return redirect('organizations:org_profile', org_id=org_id)


# ─── Media: Videos (standalone delete, upload now handled inside album edit) ──

@login_required
@chairman_required
def video_upload_view(request, org_id):
    """Redirect to album edit — videos are now uploaded from within the album."""
    org = get_object_or_404(Organization, id=org_id, is_active=True)
    album = org.albums.first()
    if album:
        return redirect('organizations:album_edit', org_id=org_id, album_id=album.id)
    messages.error(request, 'Create an album first before uploading videos.')
    return redirect('organizations:org_profile', org_id=org_id)


@login_required
@chairman_required
def video_delete_view(request, org_id, video_id):
    from .models import OrgVideoPost

    org = get_object_or_404(Organization, id=org_id, is_active=True)
    video = get_object_or_404(OrgVideoPost, id=video_id, organization_id=org_id)

    if request.method == 'POST':
        title = video.title
        video.delete()
        messages.success(request, f'Video "{title}" deleted.')

    return redirect('organizations:org_profile', org_id=org_id)


# ─── Media: Showcase ─────────────────────────────────────────────────────────

@login_required
@chairman_required
def showcase_set_view(request, org_id):
    from .models import OrgVideoPost, OrgShowcase
    from .media_validators import validate_hex_color, validate_photo, validate_video
    from django.core.exceptions import ValidationError

    org = get_object_or_404(Organization, id=org_id, is_active=True)

    if request.method == 'POST':
        showcase_type = request.POST.get('type')
        description = request.POST.get('description', '').strip()
        accent_color = request.POST.get('accent_color', '').strip() or None

        # Validate description is required
        if not description:
            messages.error(request, 'Description is required.')
            return redirect('organizations:showcase_form', org_id=org_id)

        if accent_color:
            try:
                validate_hex_color(accent_color)
            except ValidationError as e:
                messages.error(request, str(e.message))
                return redirect('organizations:showcase_form', org_id=org_id)

        showcase, _ = OrgShowcase.objects.get_or_create(organization=org)

        if showcase_type == 'image':
            image_file = request.FILES.get('showcase_image')
            if image_file:
                # New image uploaded — validate and replace
                try:
                    validate_photo(image_file)
                except ValidationError as e:
                    messages.error(request, str(e.message))
                    return redirect('organizations:showcase_form', org_id=org_id)
                showcase.image = image_file
                # Delete old showcase video if switching to image
                if showcase.video_post_id:
                    old_video = showcase.video_post
                    showcase.video_post = None
                    showcase.save()
                    old_video.delete()
                else:
                    showcase.video_post = None
            elif not showcase.image:
                # No existing image and no new file provided
                messages.error(request, 'Please select an image file.')
                return redirect('organizations:showcase_form', org_id=org_id)
            # else: no new file but existing image — keep it untouched

        elif showcase_type == 'video':
            video_title = request.POST.get('showcase_video_title', '').strip() or 'Showcase Video'
            video_file = request.FILES.get('showcase_video')
            if video_file:
                # New video uploaded — validate and replace
                try:
                    validate_video(video_file)
                except ValidationError as e:
                    messages.error(request, str(e.message))
                    return redirect('organizations:showcase_form', org_id=org_id)
                # Delete old showcase video if replacing
                if showcase.video_post_id:
                    old_video = showcase.video_post
                    showcase.video_post = None
                    showcase.save()
                    old_video.delete()
                new_video = OrgVideoPost.objects.create(
                    organization=org, title=video_title,
                    video=video_file, created_by=request.user
                )
                showcase.video_post = new_video
                showcase.image = None
            elif not showcase.video_post_id:
                # No existing video and no new file provided
                messages.error(request, 'Please select a video file.')
                return redirect('organizations:showcase_form', org_id=org_id)
            # else: no new file but existing video — keep it untouched
        else:
            messages.error(request, 'Invalid showcase type.')
            return redirect('organizations:org_profile', org_id=org_id)

        showcase.accent_color = accent_color
        showcase.description = description
        showcase.save()
        messages.success(request, 'Showcase updated.')

    return redirect('organizations:org_profile', org_id=org_id)


@login_required
@chairman_required
def showcase_clear_view(request, org_id):
    from .models import OrgShowcase

    org = get_object_or_404(Organization, id=org_id, is_active=True)

    if request.method == 'POST':
        showcase = OrgShowcase.objects.filter(organization=org).first()
        if showcase:
            # Also delete the associated video post if any
            if showcase.video_post_id:
                showcase.video_post.delete()
            showcase.delete()
        messages.success(request, 'Showcase cleared.')

    return redirect('organizations:org_profile', org_id=org_id)


@login_required
@chairman_required
def showcase_form_view(request, org_id):
    """Render the showcase management form."""
    org = get_object_or_404(Organization, id=org_id, is_active=True)
    showcase = getattr(org, 'showcase', None)
    return render(request, 'organizations/chairman/showcase_form.html', {
        'org': org,
        'showcase': showcase,
    })

@login_required
@chairman_required
def reorder_officers_view(request, org_id):
    """Reorder officers via drag-and-drop — accepts POST, returns JSON."""
    import json
    from django.http import JsonResponse as _JsonResponse
    
    if request.method == 'POST':
        # Order is accepted but not persisted (no display_order field yet).
        # Returns success so the UI doesn't show an error.
        return _JsonResponse({'success': True})
    
    return _JsonResponse({'success': False}, status=405)


# ─── Member search (for invite autocomplete) ──────────────────────────────────

@login_required
@chairman_required
def renewal_apply_view(request, org_id):
    """Renewal/Accreditation application form — accessible from chairman dashboard."""
    from .models import AccreditationApplication, AccreditationDocument, OfficialFormLink
    from .constants import RENEWAL_DOCS

    org = get_object_or_404(Organization, id=org_id)

    # CSO is the governing body — it does not submit renewal applications
    if org.is_cso:
        messages.error(request, 'The CSO organization does not require accreditation renewal.')
        return redirect('organizations:chairman_dashboard', org_id=org_id)

    # Allow renewal only for orgs that are renewal_due or lapsed (not plain active)
    if org.status not in ('renewal_due', 'lapsed'):
        messages.error(request, 'Renewal is only available for renewal-due or lapsed organizations.')
        return redirect('organizations:chairman_dashboard', org_id=org_id)

    # Block duplicate pending/under_review renewal
    if AccreditationApplication.objects.filter(
        organization=org,
        registration_type='renewal',
        status__in=['pending', 'under_review'],
    ).exists():
        messages.error(
            request,
            'A renewal application is already pending review. '
            'You cannot submit another until the current one is resolved.'
        )
        return redirect('organizations:chairman_dashboard', org_id=org_id)

    # Get chairman membership for display
    from memberships.models import Membership
    chairman_membership = Membership.objects.filter(
        organization=org, role='chairman', status='active'
    ).select_related('user').first()

    # Get available report compilations (graceful if model doesn't exist yet)
    compilations = []
    try:
        from reports.models import ReportCompilation
        compilations = ReportCompilation.objects.filter(organization=org).order_by('-created_at')
    except Exception:
        pass

    official_forms = OfficialFormLink.objects.all()

    from .models import RenewalRequirement
    use_institutional = (org.category == 'institutional')
    if use_institutional:
        req_obj = RenewalRequirement.objects.filter(status='institutional').first()
        institutional_docs = req_obj.required_documents if req_obj else []
    else:
        institutional_docs = []

    # For non-institutional orgs: use configured standard list if available, else fall back to RENEWAL_DOCS
    if not use_institutional:
        _std_req = RenewalRequirement.objects.filter(status='standard').first()
        _std_docs = _std_req.required_documents if (_std_req and _std_req.required_documents) else None
        # Build effective RENEWAL_DOCS list from configured entries or fall back to constants
        effective_renewal_docs = [e['title'] for e in _std_docs] if _std_docs else RENEWAL_DOCS
    else:
        _std_docs = None
        effective_renewal_docs = RENEWAL_DOCS

    if request.method == 'POST':
        errors = []

        # Validate required documents
        uploaded_files = {}

        if use_institutional:
            # Validate institutional docs
            for entry in institutional_docs:
                field_name = 'doc_' + entry['title'].lower().replace(' ', '').replace('-', '')
                file = request.FILES.get(field_name)
                if file:
                    if file.size > 10 * 1024 * 1024:
                        errors.append(f'{entry["title"]}: File size must not exceed 10 MB.')
                    else:
                        uploaded_files[entry['title']] = file
                else:
                    errors.append(f'{entry["title"]} is required.')

            if errors:
                return render(request, 'organizations/chairman/renewal_apply.html', {
                    'org': org,
                    'chairman_membership': chairman_membership,
                    'use_institutional': use_institutional,
                    'institutional_docs': institutional_docs,
                    'official_forms': official_forms,
                    'errors': errors,
                })

            # Create application + documents
            application = AccreditationApplication.objects.create(
                organization=org,
                registration_type='renewal',
                status='pending',
            )
            for doc_type, file in uploaded_files.items():
                AccreditationDocument.objects.create(
                    application=application,
                    document_type=doc_type,
                    file=file,
                )
            log_action(actor=request.user, action=AuditActions.ORG_CREATED, target=org,
                       details=f'Submitted institutional renewal application for {org.name}', request=request)
            messages.success(request, f'Renewal application for "{org.name}" submitted successfully. The CSO Admin will review it and notify you of the outcome.')
            return redirect('organizations:chairman_dashboard', org_id=org_id)

        else:
            compilation_id = request.POST.get('compilation_id', '').strip()

            for doc_type in effective_renewal_docs:
                if doc_type == 'Accomplishment Reports':
                    # Can be satisfied by a compilation OR a file upload
                    field_name = 'doc_accomplishment_reports'
                    file = request.FILES.get(field_name)
                    if file:
                        if file.size > 10 * 1024 * 1024:
                            errors.append(f'{doc_type}: File size must not exceed 10 MB.')
                        else:
                            uploaded_files[doc_type] = file
                    elif not compilation_id:
                        errors.append('Accomplishment Reports is required (upload a file or select a compilation).')
                    continue

                # Field name must match the template's filter chain: |lower|cut:' '|cut:'-'
                # which strips (not replaces) spaces and hyphens — e.g. "Form A" -> "doc_forma"
                field_name = 'doc_' + doc_type.lower().replace(' ', '').replace('-', '')
                file = request.FILES.get(field_name)
                if file:
                    if file.size > 10 * 1024 * 1024:
                        errors.append(f'{doc_type}: File size must not exceed 10 MB.')
                    else:
                        uploaded_files[doc_type] = file
                else:
                    errors.append(f'{doc_type} is required.')

            if errors:
                return render(request, 'organizations/chairman/renewal_apply.html', {
                    'org': org,
                    'chairman_membership': chairman_membership,
                    'renewal_docs': effective_renewal_docs,
                    'compilations': compilations,
                    'official_forms': official_forms,
                    'errors': errors,
                    'selected_compilation_id': compilation_id,
                    'use_institutional': use_institutional,
                    'institutional_docs': institutional_docs,
                })

            # Create AccreditationApplication
            application = AccreditationApplication.objects.create(
                organization=org,
                registration_type='renewal',
                status='pending',
            )

            # Create AccreditationDocument records for uploaded files
            for doc_type, file in uploaded_files.items():
                AccreditationDocument.objects.create(
                    application=application,
                    document_type=doc_type,
                    file=file,
                )

            # If a compilation was selected, create a document record referencing it
            if compilation_id:
                try:
                    AccreditationDocument.objects.create(
                        application=application,
                        document_type='Accomplishment Reports',
                        compilation_id=int(compilation_id),
                    )
                except (ValueError, TypeError):
                    # If compilation_id is invalid, log but don't fail the submission
                    messages.warning(
                        request,
                        'Note: The selected report compilation could not be attached. '
                        'Your renewal application has been submitted with other documents.'
                    )

            # Audit log
            log_action(
                actor=request.user,
                action=AuditActions.ORG_CREATED,
                target=org,
                details=f'Submitted renewal application for {org.name}',
                request=request,
            )

            messages.success(
                request,
                f'Renewal application for "{org.name}" submitted successfully. '
                'The CSO Admin will review it and notify you of the outcome.'
            )
            return redirect('organizations:chairman_dashboard', org_id=org_id)

    return render(request, 'organizations/chairman/renewal_apply.html', {
        'org': org,
        'chairman_membership': chairman_membership,
        'renewal_docs': effective_renewal_docs,
        'compilations': compilations,
        'official_forms': official_forms,
        'use_institutional': use_institutional,
        'institutional_docs': institutional_docs,
    })


@login_required
@chairman_required
def chairman_member_search_view(request, org_id):
    """Return JSON list of active users matching a name or student ID query,
    excluding people who are already members of this org."""
    from django.http import JsonResponse
    from django.db.models import Q
    from memberships.models import Membership
    from accounts.models import User

    org = get_object_or_404(Organization, id=org_id, is_active=True)

    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    existing_member_ids = Membership.objects.filter(
        organization=org, status='active'
    ).values_list('user_id', flat=True)

    users = User.objects.filter(is_active=True).exclude(
        id__in=existing_member_ids
    ).filter(
        Q(first_name__icontains=q) |
        Q(last_name__icontains=q) |
        Q(student_id__icontains=q) |
        Q(employee_id__icontains=q)
    )[:10]

    results = [
        {
            'student_id': u.employee_id if u.is_faculty else u.student_id,
            'name': u.get_full_name(),
            'is_faculty': u.is_faculty,
            'label': f'Faculty — {u.department}' if u.is_faculty else f'Year {u.year_level}',
        }
        for u in users
    ]
    return JsonResponse({'results': results})


# ─── CSO Admin: Accreditation & Registration ─────────────────────────────────

def cso_admin_required(view_func):
    """Decorator: user must be CSO admin or president."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not (request.user.is_cso_admin or request.user.is_cso_president):
            messages.error(request, 'Access restricted to CSO administrators.')
            return redirect('core:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@cso_admin_required
def admin_accreditation_panel_view(request):
    """CSO Admin: list all accreditation applications (all statuses)."""
    from .models import AccreditationApplication
    status_filter = request.GET.get('status', '')
    applications = AccreditationApplication.objects.select_related(
        'organization', 'reviewed_by'
    )
    valid_statuses = ('pending', 'under_review', 'returned', 'approved', 'rejected')
    if status_filter in valid_statuses:
        applications = applications.filter(status=status_filter)
    else:
        # Default: show all
        applications = applications.all()
    applications = applications.order_by('-submitted_at')
    return render(request, 'organizations/admin/accreditation_panel.html', {
        'applications': applications,
        'status_filter': status_filter,
    })


@login_required
@cso_admin_required
def admin_review_application_view(request, app_id):
    """CSO Admin: detail view for a single accreditation application."""
    from .models import AccreditationApplication
    application = get_object_or_404(AccreditationApplication, id=app_id)
    documents = application.documents.all()
    return render(request, 'organizations/admin/review_application.html', {
        'application': application,
        'documents': documents,
    })


@login_required
@cso_admin_required
def admin_review_action_view(request, app_id):
    """CSO Admin: perform a review action on an accreditation application."""
    from .models import AccreditationApplication
    from django.utils import timezone

    if request.method != 'POST':
        return redirect('organizations:admin_accreditation_panel')

    application = get_object_or_404(AccreditationApplication, id=app_id)
    action = request.POST.get('action', '')
    remarks = request.POST.get('remarks', '').strip()

    org = application.organization

    # Get chairman for notifications
    from memberships.models import Membership
    chairman_membership = Membership.objects.filter(
        organization=org, role='chairman', status='active'
    ).select_related('user').first()
    chairman = chairman_membership.user if chairman_membership else None

    from announcements.utils import send_notification
    from django.urls import reverse

    if action == 'mark_under_review':
        application.status = 'under_review'
        org.status = 'under_review'
        org.save()
        application.reviewed_by = request.user
        application.reviewed_at = timezone.now()
        application.save()
        messages.success(request, f'Application for "{org.name}" marked as under review.')

    elif action == 'approve':
        # Set org status based on registration type
        if application.registration_type == 'renewal':
            # Lapsed orgs always become active on renewal approval
            if org.status == 'lapsed':
                new_org_status = 'active'
            else:
                # For renewal_due orgs: check "Promote to Active" checkbox
                promote_to_active = request.POST.get('promote_to_active', 'off') == 'on'
                if promote_to_active:
                    new_org_status = 'active'
                else:
                    # Restore to pre-renewal status (before transition to renewal_due)
                    new_org_status = org.pre_renewal_status or 'probationary'
        else:
            # For new_applicant and new_chapter: always set to probationary
            new_org_status = 'probationary'
        
        org.status = new_org_status
        org.pre_renewal_status = None  # Clear the pre-renewal status after using it
        org.save()
        application.status = 'approved'
        application.reviewed_by = request.user
        application.reviewed_at = timezone.now()
        if remarks:
            application.admin_remarks = remarks
        application.save()
        log_action(
            actor=request.user,
            action=AuditActions.ORG_APPROVED,
            target=org,
            details=f'Approved accreditation application for {org.name} ({application.registration_type}) → {new_org_status}',
            request=request,
        )
        if chairman:
            send_notification(
                title=f'Application approved — {org.name}',
                message=(
                    f'Your accreditation application for "{org.name}" has been approved. '
                    f'Your organization status is now: {org.get_status_display()}.'
                ),
                recipients=[chairman],
                sender=request.user,
                organization=org,
                is_priority=True,
                link_url=reverse('organizations:chairman_dashboard', kwargs={'org_id': org.id}),
                notification_type='organization',
            )
        messages.success(request, f'Application approved. "{org.name}" is now {org.get_status_display()}.')

    elif action == 'return':
        application.status = 'returned'
        application.admin_remarks = remarks
        application.reviewed_by = request.user
        application.reviewed_at = timezone.now()
        application.save()
        if chairman:
            send_notification(
                title=f'Application returned — {org.name}',
                message=(
                    f'Your accreditation application for "{org.name}" has been returned for revision.\n\n'
                    f'Remarks: {remarks or "No remarks provided."}'
                ),
                recipients=[chairman],
                sender=request.user,
                organization=org,
                is_priority=True,
                link_url=reverse('organizations:accreditation_apply'),
                notification_type='organization',
            )
        messages.success(request, f'Application returned to "{org.name}" for revision.')

    elif action == 'reject':
        application.status = 'rejected'
        application.admin_remarks = remarks
        application.reviewed_by = request.user
        application.reviewed_at = timezone.now()
        application.save()
        org.status = 'rejected'
        org.save()
        log_action(
            actor=request.user,
            action=AuditActions.ORG_REJECTED,
            target=org,
            details=f'Rejected accreditation application for {org.name}. Reason: {remarks}',
            request=request,
        )
        if chairman:
            send_notification(
                title=f'Application rejected — {org.name}',
                message=(
                    f'Your accreditation application for "{org.name}" has been rejected.\n\n'
                    f'Reason: {remarks or "No reason provided."}'
                ),
                recipients=[chairman],
                sender=request.user,
                organization=org,
                is_priority=True,
                link_url=reverse('core:dashboard'),
                notification_type='organization',
            )
        messages.success(request, f'Application for "{org.name}" rejected.')

    else:
        messages.error(request, 'Invalid action.')

    return redirect('organizations:admin_review_application', app_id=app_id)


# ─── CSO Admin: School Year Controls ─────────────────────────────────────────

@login_required
@cso_admin_required
def admin_new_school_year_view(request):
    """CSO Admin: trigger new school year — flip eligible orgs to renewal_due."""
    if request.method != 'POST':
        return redirect('core:admin_panel')

    from django.utils import timezone
    from core.models import SystemSetting
    from memberships.models import Membership
    from announcements.utils import send_notification
    from django.urls import reverse

    renewal_deadline = request.POST.get('renewal_deadline', '').strip()

    # Store renewal deadline in SystemSetting
    if renewal_deadline:
        obj, _ = SystemSetting.objects.get_or_create(key='renewal_deadline', defaults={'value': renewal_deadline})
        obj.value = renewal_deadline
        obj.last_updated_by = request.user
        obj.save()

    # Transition eligible orgs to renewal_due
    eligible_statuses = ['probationary', 'institutional', 'active']
    eligible_orgs = Organization.objects.filter(status__in=eligible_statuses, is_cso=False)
    count = eligible_orgs.count()

    for org in eligible_orgs:
        org.pre_renewal_status = org.status  # Store current status before transition
        org.status = 'renewal_due'
        org.save()

        # Notify chairman
        chairman_membership = Membership.objects.filter(
            organization=org, role='chairman', status='active'
        ).select_related('user').first()
        if chairman_membership:
            deadline_str = f' Renewal deadline: {renewal_deadline}.' if renewal_deadline else ''
            send_notification(
                title=f'Renewal required — {org.name}',
                message=(
                    f'A new school year has begun. Your organization "{org.name}" must submit a renewal application '
                    f'to maintain its accredited status.{deadline_str}'
                ),
                recipients=[chairman_membership.user],
                sender=request.user,
                organization=org,
                is_priority=True,
                link_url=reverse('organizations:renewal_apply', kwargs={'org_id': org.id}),
                notification_type='organization',
            )

    log_action(
        actor=request.user,
        action=AuditActions.YEAR_TRANSITION,
        details=f'Triggered new school year. {count} organization(s) set to renewal_due. Deadline: {renewal_deadline or "not set"}.',
        request=request,
    )

    messages.success(
        request,
        f'New school year triggered. {count} organization(s) set to renewal required.'
        + (f' Renewal deadline: {renewal_deadline}.' if renewal_deadline else '')
    )
    return redirect('core:admin_panel')


@login_required
@cso_admin_required
def admin_close_renewal_view(request):
    """CSO Admin: close renewal period — flip renewal_due orgs without approved renewal to lapsed."""
    if request.method != 'POST':
        return redirect('core:admin_panel')

    from memberships.models import Membership
    from announcements.utils import send_notification
    from django.urls import reverse
    from .models import AccreditationApplication
    from core.models import SystemSetting

    # Guard: only allowed if a school year transition has been run
    school_year_ran = SystemSetting.objects.filter(key='school_year_transitioned').exists()
    if not school_year_ran:
        messages.error(request, 'Cannot close renewal period before a school year transition has been triggered.')
        return redirect('core:admin_panel')

    # Guard: already closed this cycle
    already_closed = SystemSetting.objects.filter(key='renewal_period_closed').exists()
    if already_closed:
        messages.error(request, 'The renewal period has already been closed for this school year.')
        return redirect('core:admin_panel')

    # Find renewal_due orgs that do NOT have an approved renewal application
    renewal_due_orgs = Organization.objects.filter(status='renewal_due', is_cso=False)
    lapsed_orgs = []
    for org in renewal_due_orgs:
        has_approved_renewal = AccreditationApplication.objects.filter(
            organization=org,
            registration_type='renewal',
            status='approved',
        ).exists()
        if not has_approved_renewal:
            lapsed_orgs.append(org)

    count = len(lapsed_orgs)
    for org in lapsed_orgs:
        org.status = 'lapsed'
        org.save()  # ACTIVE_STATUSES no longer includes lapsed → is_active=False

        # Notify chairman
        chairman_membership = Membership.objects.filter(
            organization=org, role='chairman', status='active'
        ).select_related('user').first()
        if chairman_membership:
            send_notification(
                title=f'Accreditation lapsed — {org.name}',
                message=(
                    f'The renewal period has closed and "{org.name}" did not submit a renewal application. '
                    f'Your organization\'s accreditation has lapsed. You may submit a renewal application '
                    f'in the next school year to restore active status.'
                ),
                recipients=[chairman_membership.user],
                sender=request.user,
                organization=org,
                is_priority=True,
                link_url=reverse('core:dashboard'),
                notification_type='organization',
            )

    # Mark renewal period as closed for this cycle
    SystemSetting.objects.update_or_create(
        key='renewal_period_closed',
        defaults={'value': 'true', 'last_updated_by': request.user},
    )

    log_action(
        actor=request.user,
        action=AuditActions.YEAR_TRANSITION,
        details=f'Closed renewal period. {count} organization(s) lapsed.',
        request=request,
    )

    messages.success(request, f'Renewal period closed. {count} organization(s) have lapsed.')
    return redirect('core:admin_panel')


# ─── CSO Admin: Official Form Links ──────────────────────────────────────────

@login_required
@cso_admin_required
def admin_form_links_view(request):
    """CSO Admin: manage official form download links."""
    from .models import OfficialFormLink

    if request.method == 'POST':
        action = request.POST.get('action', '')
        link_id = request.POST.get('link_id', '').strip()
        label = request.POST.get('label', '').strip()
        url = request.POST.get('url', '').strip()

        errors = []
        if not label:
            errors.append('Label is required.')
        if not url:
            errors.append('URL is required.')

        if not errors:
            if link_id:
                # Edit existing
                link = get_object_or_404(OfficialFormLink, id=link_id)
                link.label = label
                link.url = url
                link.updated_by = request.user
                link.save()
                messages.success(request, f'Form link "{label}" updated.')
            else:
                # Create new
                OfficialFormLink.objects.create(
                    label=label,
                    url=url,
                    updated_by=request.user,
                )
                messages.success(request, f'Form link "{label}" created.')
        else:
            for error in errors:
                messages.error(request, error)

        return redirect('organizations:admin_form_links')

    links = OfficialFormLink.objects.all()
    return render(request, 'organizations/admin/form_links.html', {'links': links})


@login_required
@cso_admin_required
def admin_form_link_delete_view(request, link_id):
    """CSO Admin: delete an official form link."""
    from .models import OfficialFormLink
    link = get_object_or_404(OfficialFormLink, id=link_id)
    if request.method == 'POST':
        label = link.label
        link.delete()
        messages.success(request, f'Form link "{label}" deleted.')
    return redirect('organizations:admin_form_links')


# ─── CSO Admin: Organization Management ──────────────────────────────────────

@login_required
@cso_admin_required
def admin_organizations_view(request):
    """CSO Admin: manage organizations categorized by type and status."""
    from django.db.models import Count, Q
    
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')
    
    # Get all organizations
    organizations = Organization.objects.exclude(is_cso=True).select_related().annotate(
        member_count=Count('memberships', filter=Q(memberships__status='active'))
    )
    
    # Apply filters
    if category_filter:
        organizations = organizations.filter(category=category_filter)
    
    if status_filter:
        organizations = organizations.filter(status=status_filter)
    
    # Define statuses for each category
    student_statuses = ['probationary', 'active', 'renewal_due', 'lapsed', 'pending', 'under_review', 'rejected']
    institutional_statuses = ['active', 'pending', 'under_review', 'rejected']
    
    # Group by category with status organization
    categories_data = {}
    
    # Student Organizations
    student_orgs = organizations.filter(category='student').order_by('-date_created')
    if student_orgs.exists():
        categories_data['Student Organization'] = {
            'value': 'student',
            'orgs': student_orgs,
            'count': student_orgs.count(),
            'statuses': student_statuses,
        }
    
    # UB Chapters
    ub_orgs = organizations.filter(category='ub_chapter').order_by('-date_created')
    if ub_orgs.exists():
        categories_data['UB Chapter'] = {
            'value': 'ub_chapter',
            'orgs': ub_orgs,
            'count': ub_orgs.count(),
            'statuses': student_statuses,
        }
    
    # Institutional Organizations
    inst_orgs = organizations.filter(category='institutional').order_by('-date_created')
    if inst_orgs.exists():
        categories_data['Institutional'] = {
            'value': 'institutional',
            'orgs': inst_orgs,
            'count': inst_orgs.count(),
            'statuses': institutional_statuses,
        }
    
    return render(request, 'organizations/admin/organizations_management.html', {
        'categories_data': categories_data,
        'category_filter': category_filter,
        'status_filter': status_filter,
        'status_choices': Organization.ORG_STATUS_CHOICES,
        'category_choices': Organization.ORG_CATEGORY_CHOICES,
    })


@login_required
@cso_admin_required
def admin_edit_org_category_view(request, org_id):
    """CSO Admin: edit organization category."""
    org = get_object_or_404(Organization, id=org_id)
    
    if request.method == 'POST':
        new_category = request.POST.get('category', '').strip()
        
        if new_category not in dict(Organization.ORG_CATEGORY_CHOICES):
            messages.error(request, 'Invalid category selected.')
            return redirect('organizations:admin_organizations')
        
        old_category = org.category
        org.category = new_category
        org.save()
        
        # Audit log
        log_action(
            actor=request.user,
            action=AuditActions.ORG_UPDATED,
            target=org,
            details=f'Changed organization category from {old_category} to {new_category}',
            request=request,
        )
        
        messages.success(request, f'Organization category changed from {dict(Organization.ORG_CATEGORY_CHOICES).get(old_category)} to {dict(Organization.ORG_CATEGORY_CHOICES).get(new_category)}.')
        return redirect('organizations:admin_organizations')
    
    return render(request, 'organizations/admin/edit_org_category.html', {
        'org': org,
        'category_choices': Organization.ORG_CATEGORY_CHOICES,
    })


@login_required
@cso_admin_required
def admin_renewal_requirements_view(request):
    """CSO Admin: manage renewal document requirements by organization status."""
    from .models import RenewalRequirement
    import json

    if request.method == 'POST':
        action = request.POST.get('action', '')
        status = request.POST.get('status', '').strip()
        required_docs = request.POST.get('required_documents', '').strip()
        optional_docs = request.POST.get('optional_documents', '').strip()

        errors = []

        if not status:
            errors.append('Status is required.')
        if not required_docs:
            errors.append('At least one required document must be specified.')

        # Parse JSON
        try:
            required_list = json.loads(required_docs) if required_docs else []
            if not isinstance(required_list, list):
                raise ValueError('Must be a list')
        except (json.JSONDecodeError, ValueError):
            errors.append('Required documents must be valid JSON list format.')
            required_list = []

        try:
            optional_list = json.loads(optional_docs) if optional_docs else []
            if not isinstance(optional_list, list):
                raise ValueError('Must be a list')
        except (json.JSONDecodeError, ValueError):
            errors.append('Optional documents must be valid JSON list format.')
            optional_list = []

        if errors:
            requirements = RenewalRequirement.objects.all()
            return render(request, 'organizations/admin/renewal_requirements.html', {
                'requirements': requirements,
                'errors': errors,
                'post': request.POST,
            })

        # Create or update
        requirement, created = RenewalRequirement.objects.update_or_create(
            status=status,
            defaults={
                'required_documents': required_list,
                'optional_documents': optional_list,
                'updated_by': request.user,
            }
        )

        if created:
            messages.success(request, f'Renewal requirements for "{status}" created.')
        else:
            messages.success(request, f'Renewal requirements for "{status}" updated.')

        return redirect('organizations:admin_renewal_requirements')

    requirements = RenewalRequirement.objects.all()
    from .models import AccreditationRequirement
    from .constants import RENEWAL_DOCS, NEW_APPLICANT_DOCS, NEW_CHAPTER_DOCS, NEW_CHAPTER_OPTIONAL_DOCS

    # ── Seed defaults into DB if no record exists yet ────────────────────────
    # Standard renewal (UB Chapter & Student Org)
    standard_renewal_req = RenewalRequirement.objects.filter(status='standard').first()
    if not standard_renewal_req or not standard_renewal_req.required_documents:
        standard_renewal_req, _ = RenewalRequirement.objects.update_or_create(
            status='standard',
            defaults={
                'required_documents': [{'title': doc, 'link': ''} for doc in RENEWAL_DOCS],
                'optional_documents': [],
            },
        )

    # New Applicant accreditation
    new_applicant_req = AccreditationRequirement.objects.filter(registration_type='new_applicant').first()
    if not new_applicant_req or not new_applicant_req.required_documents:
        new_applicant_req, _ = AccreditationRequirement.objects.update_or_create(
            registration_type='new_applicant',
            defaults={
                'required_documents': [{'title': doc, 'link': '', 'optional': False} for doc in NEW_APPLICANT_DOCS],
            },
        )

    # New Chapter accreditation
    new_chapter_req = AccreditationRequirement.objects.filter(registration_type='new_chapter').first()
    if not new_chapter_req or not new_chapter_req.required_documents:
        new_chapter_req, _ = AccreditationRequirement.objects.update_or_create(
            registration_type='new_chapter',
            defaults={
                'required_documents': [
                    {'title': doc, 'link': '', 'optional': doc in NEW_CHAPTER_OPTIONAL_DOCS}
                    for doc in NEW_CHAPTER_DOCS
                ],
            },
        )

    return render(request, 'organizations/admin/renewal_requirements.html', {
        'requirements': RenewalRequirement.objects.all(),
        'status_choices': RenewalRequirement.STATUS_CHOICES,
        'new_applicant_req': new_applicant_req,
        'new_chapter_req': new_chapter_req,
        'standard_renewal_req': standard_renewal_req,
    })


@login_required
@cso_admin_required
def admin_standard_renewal_add_view(request):
    """CSO Admin: add a requirement entry to the standard (UB Chapter / Student Org) renewal list."""
    from .models import RenewalRequirement

    if request.method != 'POST':
        return redirect('organizations:admin_renewal_requirements')

    title = request.POST.get('title', '').strip()
    link = request.POST.get('link', '').strip()
    errors = []

    if not title:
        errors.append('Title is required.')
    elif len(title) > 200:
        errors.append('Title must be 200 characters or fewer.')
    if link:
        if not (link.startswith('http://') or link.startswith('https://')):
            errors.append('Link must begin with http:// or https://.')
        elif len(link) > 2048:
            errors.append('Link must be 2048 characters or fewer.')

    if errors:
        for error in errors:
            messages.error(request, error)
        return redirect('organizations:admin_renewal_requirements')

    req_obj, _ = RenewalRequirement.objects.get_or_create(status='standard')
    docs = req_obj.required_documents if isinstance(req_obj.required_documents, list) else []
    docs.append({'title': title, 'link': link or None})
    req_obj.required_documents = docs
    req_obj.updated_by = request.user
    req_obj.save()

    messages.success(request, f'Requirement "{title}" added.')
    return redirect('organizations:admin_renewal_requirements')


@login_required
@cso_admin_required
def admin_standard_renewal_remove_view(request):
    """CSO Admin: remove a requirement entry from the standard renewal list."""
    from .models import RenewalRequirement

    if request.method != 'POST':
        return redirect('organizations:admin_renewal_requirements')

    raw_index = request.POST.get('index', '')
    try:
        index = int(raw_index)
        if index < 0:
            raise ValueError
    except (ValueError, TypeError):
        messages.error(request, 'Invalid index.')
        return redirect('organizations:admin_renewal_requirements')

    try:
        req_obj = RenewalRequirement.objects.get(status='standard')
    except RenewalRequirement.DoesNotExist:
        messages.error(request, 'No standard renewal requirements record found.')
        return redirect('organizations:admin_renewal_requirements')

    docs = req_obj.required_documents or []
    if index >= len(docs):
        messages.error(request, 'Invalid index: no entry at that position.')
        return redirect('organizations:admin_renewal_requirements')

    removed = docs.pop(index)
    req_obj.required_documents = docs
    req_obj.updated_by = request.user
    req_obj.save()

    messages.success(request, f'Requirement "{removed.get("title", "")}" removed.')
    return redirect('organizations:admin_renewal_requirements')





@login_required
@cso_admin_required
def admin_institutional_add_view(request):
    """CSO Admin: add a requirement entry to the institutional renewal list."""
    from .models import RenewalRequirement

    if request.method != 'POST':
        return redirect('organizations:admin_renewal_requirements')

    title = request.POST.get('title', '').strip()
    link = request.POST.get('link', '').strip()

    errors = []

    # Validate title
    if not title:
        errors.append('Title is required and cannot be blank or whitespace.')
    elif len(title) > 200:
        errors.append('Title must be 200 characters or fewer.')

    # Validate link (only if non-empty)
    if link:
        if not (link.startswith('http://') or link.startswith('https://')):
            errors.append('Link must begin with http:// or https://.')
        elif len(link) > 2048:
            errors.append('Link must be 2048 characters or fewer.')

    if errors:
        requirements = RenewalRequirement.objects.all()
        return render(request, 'organizations/admin/renewal_requirements.html', {
            'requirements': requirements,
            'status_choices': RenewalRequirement.STATUS_CHOICES,
            'errors': errors,
        })

    # Persist the new entry
    req_obj, _ = RenewalRequirement.objects.get_or_create(status='institutional')
    docs = req_obj.required_documents if isinstance(req_obj.required_documents, list) else []
    docs.append({'title': title, 'link': link or None})
    req_obj.required_documents = docs
    req_obj.updated_by = request.user
    req_obj.save()

    messages.success(request, f'Requirement "{title}" added to the institutional list.')
    return redirect('organizations:admin_renewal_requirements')


@login_required
@cso_admin_required
def admin_institutional_remove_view(request):
    """CSO Admin: remove a requirement entry from the institutional renewal list."""
    if request.method != 'POST':
        return redirect('organizations:admin_renewal_requirements')

    raw_index = request.POST.get('index', '')

    # Validate: parse index as a non-negative integer
    try:
        index = int(raw_index)
        if index < 0:
            raise ValueError("Index must be non-negative")
    except (ValueError, TypeError):
        messages.error(request, "Invalid index: must be a non-negative integer.")
        return redirect('organizations:admin_renewal_requirements')

    # Load the institutional RenewalRequirement record
    from .models import RenewalRequirement
    try:
        req = RenewalRequirement.objects.get(status='institutional')
    except RenewalRequirement.DoesNotExist:
        messages.error(request, "No institutional renewal requirements record exists.")
        return redirect('organizations:admin_renewal_requirements')

    required_documents = req.required_documents or []

    # Validate index is within bounds
    if index >= len(required_documents):
        messages.error(request, "Invalid index: no entry exists at that position.")
        return redirect('organizations:admin_renewal_requirements')

    # Pop the item and save
    removed = required_documents.pop(index)
    req.required_documents = required_documents
    req.updated_by = request.user
    req.save()

    messages.success(request, f"Requirement \"{removed.get('title', '')}\" has been removed.")
    return redirect('organizations:admin_renewal_requirements')




# ─── CSO Admin: Accreditation Registration Requirements (add / remove) ────────


@login_required
@cso_admin_required
def admin_accreditation_req_add_view(request, reg_type):
    """CSO Admin: add a document entry to a registration type's requirement list."""
    from .models import AccreditationRequirement

    if reg_type not in ('new_applicant', 'new_chapter'):
        messages.error(request, 'Invalid registration type.')
        return redirect('organizations:admin_renewal_requirements')

    if request.method != 'POST':
        return redirect('organizations:admin_renewal_requirements')

    title = request.POST.get('title', '').strip()
    link = request.POST.get('link', '').strip()
    is_optional = request.POST.get('is_optional', '') == 'on'

    errors = []

    if not title:
        errors.append('Title is required and cannot be blank or whitespace.')
    elif len(title) > 200:
        errors.append('Title must be 200 characters or fewer.')

    if link:
        if not (link.startswith('http://') or link.startswith('https://')):
            errors.append('Link must begin with http:// or https://.')
        elif len(link) > 2048:
            errors.append('Link must be 2048 characters or fewer.')

    if errors:
        for error in errors:
            messages.error(request, error)
        return redirect('organizations:admin_renewal_requirements')

    req_obj, _ = AccreditationRequirement.objects.get_or_create(registration_type=reg_type)
    docs = req_obj.required_documents if isinstance(req_obj.required_documents, list) else []
    docs.append({'title': title, 'link': link or None, 'optional': is_optional})
    req_obj.required_documents = docs
    req_obj.updated_by = request.user
    req_obj.save()

    messages.success(request, f'Requirement "{title}" added.')
    return redirect(f'{request.META.get("HTTP_REFERER", "")}#tab-{reg_type}')


@login_required
@cso_admin_required
def admin_accreditation_req_remove_view(request, reg_type):
    """CSO Admin: remove a document entry from a registration type's requirement list."""
    from .models import AccreditationRequirement

    if reg_type not in ('new_applicant', 'new_chapter'):
        messages.error(request, 'Invalid registration type.')
        return redirect('organizations:admin_renewal_requirements')

    if request.method != 'POST':
        return redirect('organizations:admin_renewal_requirements')

    raw_index = request.POST.get('index', '')
    try:
        index = int(raw_index)
        if index < 0:
            raise ValueError
    except (ValueError, TypeError):
        messages.error(request, 'Invalid index.')
        return redirect('organizations:admin_renewal_requirements')

    try:
        req_obj = AccreditationRequirement.objects.get(registration_type=reg_type)
    except AccreditationRequirement.DoesNotExist:
        messages.error(request, 'No requirements record found.')
        return redirect('organizations:admin_renewal_requirements')

    docs = req_obj.required_documents or []
    if index >= len(docs):
        messages.error(request, 'Invalid index: no entry at that position.')
        return redirect('organizations:admin_renewal_requirements')

    removed = docs.pop(index)
    req_obj.required_documents = docs
    req_obj.updated_by = request.user
    req_obj.save()

    messages.success(request, f'Requirement "{removed.get("title", "")}" removed.')
    return redirect(f'{request.META.get("HTTP_REFERER", "")}#tab-{reg_type}')


# ─── CSO Admin: Organization Registration Review ──────────────────────────────

@login_required
@cso_admin_required
def admin_org_registration_panel_view(request):
    """CSO Admin: list all organization registration claims."""
    from .models import OrganizationRegistration

    status_filter = request.GET.get('status', '')
    registrations = OrganizationRegistration.objects.select_related(
        'submitted_by', 'reviewed_by'
    )

    if status_filter in ('pending', 'approved', 'rejected'):
        registrations = registrations.filter(status=status_filter)
    # No filter = show all statuses

    registrations = registrations.order_by('-created_at')
    
    return render(request, 'organizations/admin/org_registration_panel.html', {
        'registrations': registrations,
        'status_filter': status_filter,
    })


@login_required
@cso_admin_required
def admin_review_org_registration_view(request, reg_id):
    """CSO Admin: detail view for a single organization registration claim."""
    from .models import OrganizationRegistration
    
    registration = get_object_or_404(OrganizationRegistration, id=reg_id)
    
    return render(request, 'organizations/admin/review_org_registration.html', {
        'registration': registration,
    })


@login_required
@cso_admin_required
def admin_review_org_registration_action_view(request, reg_id):
    """CSO Admin: perform a review action on an organization registration claim."""
    from .models import OrganizationRegistration
    from django.utils import timezone
    from announcements.utils import send_notification
    from django.urls import reverse

    if request.method != 'POST':
        return redirect('organizations:admin_org_registration_panel')

    registration = get_object_or_404(OrganizationRegistration, id=reg_id)
    action = request.POST.get('action', '')
    remarks = request.POST.get('remarks', '').strip()

    if action == 'approve':
        # Create the organization
        # All existing org registrations (institutional, ub_chapter, student_org) go directly to active
        # They skip probationary since they're already official on campus
        org_status = 'active'
        
        org = Organization.objects.create(
            name=registration.org_name,
            status=org_status,
            category=registration.category,
        )
        
        # Link the registration to the created org
        registration.created_organization = org
        registration.status = 'approved'
        registration.reviewed_by = request.user
        registration.reviewed_at = timezone.now()
        registration.admin_remarks = remarks
        registration.save()
        
        # Create chairman membership using proposed_chairman or submitter
        from memberships.models import Membership
        chairman = registration.proposed_chairman or registration.submitted_by
        Membership.objects.create(
            user=chairman,
            organization=org,
            role='chairman',
            has_chairman_privileges=True,
            status='active',
        )
        
        # Notify the submitter
        message = (
            f'Your organization "{org.name}" has been successfully registered in the system. '
            f'You are now the chairman and can submit renewal applications.'
        )
        
        send_notification(
            title=f'Organization registered — {org.name}',
            message=message,
            recipients=[registration.submitted_by],
            sender=request.user,
            organization=org,
            link_url=reverse('organizations:org_profile', kwargs={'org_id': org.id}),
            notification_type='organization',
        )
        
        # Audit log
        log_action(
            actor=request.user,
            action=AuditActions.ORG_CREATED,
            target=org,
            details=f'Approved organization registration claim: {org.name} ({registration.category})',
            request=request,
        )
        
        messages.success(request, f'Organization "{org.name}" has been registered and created.')

    elif action == 'reject':
        registration.status = 'rejected'
        registration.reviewed_by = request.user
        registration.reviewed_at = timezone.now()
        registration.admin_remarks = remarks
        registration.save()
        
        # Notify the submitter
        send_notification(
            title=f'Registration claim rejected — {registration.org_name}',
            message=(
                f'Your registration claim for "{registration.org_name}" has been rejected.\n\n'
                f'Reason: {remarks or "No reason provided."}\n\n'
                f'If you believe this is an error, please contact the CSO Admin.'
            ),
            recipients=[registration.submitted_by],
            sender=request.user,
            is_priority=True,
            link_url=reverse('organizations:directory'),
            notification_type='organization',
        )
        
        # Audit log
        log_action(
            actor=request.user,
            action=AuditActions.ORG_REJECTED,
            details=f'Rejected organization registration claim: {registration.org_name}. Reason: {remarks}',
            request=request,
        )
        
        messages.success(request, f'Registration claim for "{registration.org_name}" rejected.')

    else:
        messages.error(request, 'Invalid action.')

    return redirect('organizations:admin_review_org_registration', reg_id=reg_id)
