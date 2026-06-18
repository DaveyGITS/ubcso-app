from celery import shared_task


@shared_task
def expire_temp_co_chairman(membership_id):
    """Auto-demote temporary co-chairman to member after 24hr window."""
    from memberships.models import Membership
    from django.utils import timezone
    try:
        membership = Membership.objects.select_related('organization').get(
            pk=membership_id,
            role='co_chairman',
            co_chairman_expiry__isnull=False,
            status='active'
        )
        if membership.co_chairman_expiry <= timezone.now():
            # Apply pending role if set, otherwise demote
            if membership.pending_role:
                membership.role = membership.pending_role
                membership.custom_role = membership.pending_custom_role
                membership.pending_role = None
                membership.pending_custom_role = None
            else:
                # CSO outgoing president becomes officer (stays visible); regular orgs become member
                membership.role = 'officer' if membership.organization.is_cso else 'member'
                membership.custom_role = None

            membership.has_chairman_privileges = False
            membership.co_chairman_expiry = None
            membership.save()
    except Membership.DoesNotExist:
        pass
