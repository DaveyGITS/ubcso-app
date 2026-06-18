from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Membership, MembershipRequest, LeaveRequest
from organizations.models import Organization


@login_required
def membership_request_view(request, org_id):
    org = get_object_or_404(Organization, id=org_id, is_active=True)

    already_member = Membership.objects.filter(
        user=request.user,
        organization=org,
        status='active',
        organization__is_active=True,
    ).exists()

    if already_member:
        messages.info(request, 'You are already a member of this organization.')
        return redirect('organizations:org_profile', org_id=org_id)

    already_requested = MembershipRequest.objects.filter(
        user=request.user,
        organization=org,
        status='pending'
    ).exists()

    if already_requested:
        messages.info(request, 'You already have a pending request for this organization.')
        return redirect('organizations:org_profile', org_id=org_id)

    if request.method == 'POST':
        from django.utils import timezone
        # Check if a pending invite already exists from the chairman — auto-accept both
        existing_invite = MembershipRequest.objects.filter(
            user=request.user,
            organization=org,
            type='invite',
            status='pending',
        ).first()

        if existing_invite:
            # Both sides want it — create membership immediately
            # CSO org members are always officers
            join_role = 'officer' if org.is_cso else 'member'
            Membership.objects.update_or_create(
                user=request.user,
                organization=org,
                defaults={
                    'role': join_role,
                    'status': 'active',
                    'custom_role': None,
                    'has_chairman_privileges': False,
                }
            )
            existing_invite.status = 'accepted'
            existing_invite.reviewed_at = timezone.now()
            existing_invite.save()
            from announcements.utils import send_notification
            from memberships.models import Membership as M
            leaders = M.objects.filter(
                organization=org, status='active', role__in=['chairman', 'co_chairman']
            ).values_list('user', flat=True)
            from accounts.models import User as U
            leader_users = list(U.objects.filter(id__in=leaders))
            if leader_users:
                from django.urls import reverse
                send_notification(
                    title=f'{request.user.get_full_name()} joined {org.name}',
                    message=f'{request.user.get_full_name()} submitted a join request while a pending invite existed — membership auto-confirmed.',
                    recipients=leader_users,
                    sender=request.user,
                    organization=org,
                    link_url=reverse('organizations:chairman_members', kwargs={'org_id': org.id}),
                    notification_type='membership',
                )
            messages.success(request, f'You had a pending invite from {org.name} — membership confirmed automatically!')
            return redirect('organizations:org_profile', org_id=org_id)

        MembershipRequest.objects.create(
            user=request.user,
            organization=org,
            type='request',
            status='pending',
        )
        from announcements.utils import send_notification
        from memberships.models import Membership as M
        leaders = M.objects.filter(
            organization=org, status='active', role__in=['chairman', 'co_chairman']
        ).values_list('user', flat=True)
        from accounts.models import User as U
        leader_users = list(U.objects.filter(id__in=leaders))
        if leader_users:
            from django.urls import reverse
            send_notification(
                title=f'New membership request — {org.name}',
                message=f'{request.user.get_full_name()} ({request.user.student_id}) has requested to join {org.name}.',
                recipients=leader_users,
                sender=request.user,
                organization=org,
                link_url=reverse('organizations:chairman_members', kwargs={'org_id': org.id}),
                notification_type='membership',
            )
        messages.success(request, f'Your request to join {org.name} has been submitted!')
        return redirect('organizations:org_profile', org_id=org_id)

    return render(request, 'memberships/membership_request.html', {'org': org})


@login_required
def my_requests_view(request):
    from organizations.models import OrganizationRequest, OrganizationRegistration, AccreditationApplication
    from memberships.models import Membership

    membership_requests = MembershipRequest.objects.filter(
        user=request.user
    ).select_related('organization').order_by('-requested_at')

    leave_requests = LeaveRequest.objects.filter(
        user=request.user
    ).select_related('organization').order_by('-created_at')

    # Legacy org creation requests
    org_requests = OrganizationRequest.objects.filter(
        requester=request.user
    ).order_by('-created_at')

    # Org registration claims (existing org)
    org_registrations = OrganizationRegistration.objects.filter(
        submitted_by=request.user
    ).order_by('-created_at')

    # Accreditation applications — user is chairman of the org
    chairman_org_ids = Membership.objects.filter(
        user=request.user,
        role='chairman',
        status='active',
    ).values_list('organization_id', flat=True)
    accreditation_applications = AccreditationApplication.objects.filter(
        organization_id__in=chairman_org_ids,
    ).select_related('organization').order_by('-submitted_at')

    pending_invites_count = membership_requests.filter(type='invite', status='pending').count()

    return render(request, 'memberships/my_requests.html', {
        'membership_requests': membership_requests,
        'leave_requests': leave_requests,
        'org_requests': org_requests,
        'org_registrations': org_registrations,
        'accreditation_applications': accreditation_applications,
        'pending_invites_count': pending_invites_count,
    })


@login_required
def leave_request_view(request, org_id):
    org = get_object_or_404(Organization, id=org_id, is_active=True)

    membership = Membership.objects.filter(
        user=request.user,
        organization=org,
        status='active',
        organization__is_active=True,
    ).first()

    if not membership:
        messages.error(request, 'You are not a member of this organization.')
        return redirect('organizations:org_profile', org_id=org_id)

    already_requested = LeaveRequest.objects.filter(
        user=request.user,
        organization=org,
        status='pending'
    ).exists()

    if already_requested:
        messages.info(request, 'You already have a pending leave request for this organization.')
        return redirect('accounts:profile')

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        LeaveRequest.objects.create(
            user=request.user,
            organization=org,
            reason=reason,
            status='pending',
        )
        messages.success(request, f'Your leave request from {org.name} has been submitted.')
        return redirect('accounts:profile')

    return render(request, 'memberships/leave_request.html', {
        'org': org,
        'membership': membership,
    })


@login_required
def cancel_membership_request_view(request, request_id):
    from django.shortcuts import get_object_or_404
    req = get_object_or_404(
        MembershipRequest,
        id=request_id,
        user=request.user,
        status='pending'
    )
    if request.method == 'POST':
        req.delete()
        messages.success(request, 'Membership request cancelled.')
    return redirect('memberships:my_requests')


@login_required
def cancel_leave_request_view(request, request_id):
    leave_req = get_object_or_404(
        LeaveRequest,
        id=request_id,
        user=request.user,
        status='pending',
    )
    if request.method == 'POST':
        leave_req.delete()
        messages.success(request, 'Leave request cancelled.')
    return redirect('memberships:my_requests')


@login_required
def respond_invite_view(request, request_id):
    invite = get_object_or_404(
        MembershipRequest,
        id=request_id,
        user=request.user,
        type='invite',
        status='pending'
    )
    if request.method == 'POST':
        action = request.POST.get('action')
        from django.utils import timezone
        if action == 'accept':
            # update_or_create handles previously removed members rejoining
            # CSO org members are always officers
            join_role = 'officer' if invite.organization.is_cso else 'member'
            Membership.objects.update_or_create(
                user=request.user,
                organization=invite.organization,
                defaults={
                    'role': join_role,
                    'status': 'active',
                    'custom_role': None,
                    'has_chairman_privileges': False,
                }
            )
            invite.status = 'accepted'
            invite.reviewed_at = timezone.now()
            invite.save()
            # Notify the chairman that the invite was accepted
            from announcements.utils import send_notification
            from memberships.models import Membership as M
            leaders = M.objects.filter(
                organization=invite.organization, status='active', role__in=['chairman', 'co_chairman']
            ).values_list('user', flat=True)
            from accounts.models import User as U
            leader_users = list(U.objects.filter(id__in=leaders))
            if leader_users:
                from django.urls import reverse
                send_notification(
                    title=f'{request.user.get_full_name()} accepted your invite',
                    message=f'{request.user.get_full_name()} has accepted the invite and joined {invite.organization.name}.',
                    recipients=leader_users,
                    sender=request.user,
                    organization=invite.organization,
                    link_url=reverse('organizations:chairman_members', kwargs={'org_id': invite.organization.id}),
                    notification_type='membership',
                )
            messages.success(request, f'You have joined {invite.organization.name}!')
        elif action == 'decline':
            invite.status = 'rejected'
            invite.reviewed_at = timezone.now()
            invite.save()
            messages.info(request, f'Invite from {invite.organization.name} declined.')
    return redirect('memberships:my_requests')