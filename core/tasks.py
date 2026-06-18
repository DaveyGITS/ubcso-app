from celery import shared_task


@shared_task
def expire_temp_admin_access(user_id):
    """Auto-revoke temporary CSO admin access after 24hr window."""
    from accounts.models import User
    from django.utils import timezone
    try:
        user = User.objects.get(pk=user_id, is_cso_admin=True, cso_admin_expiry__isnull=False)
        if user.cso_admin_expiry <= timezone.now():
            # 24hr window expiry always strips admin — no exceptions
            user.is_cso_admin = False
            user.is_manually_granted_admin = False
            user.cso_admin_expiry = None
            user.save(update_fields=['is_cso_admin', 'is_manually_granted_admin', 'cso_admin_expiry'])
            # Demote in CSO org from co-chairman → member regardless
            from organizations.models import Organization
            from memberships.models import Membership
            cso_org = Organization.objects.filter(is_cso=True).first()
            if cso_org:
                m = Membership.objects.filter(
                    user=user, organization=cso_org,
                    role='co_chairman', co_chairman_expiry__isnull=False, status='active'
                ).first()
                if m:
                    if m.pending_role:
                        m.role = m.pending_role
                        m.has_chairman_privileges = m.pending_role == 'co_chairman'
                        m.custom_role = m.pending_custom_role
                        m.pending_role = None
                        m.pending_custom_role = None
                    else:
                        # CSO outgoing president becomes officer, not member
                        m.role = 'officer'
                        m.has_chairman_privileges = False
                        m.custom_role = None
                    m.co_chairman_expiry = None
                    m.save()
    except User.DoesNotExist:
        pass
