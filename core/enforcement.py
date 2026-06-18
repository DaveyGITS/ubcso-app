"""
Request-time enforcement for all timed features.
These functions are Celery-independent — they enforce expiry on every relevant request
so the system works correctly even if Celery is not running.
"""
from django.utils import timezone


# ─── Co-chairman 24hr window ──────────────────────────────────────────────────

def expire_co_chairmen_for_org(org):
    """
    Demote any expired temporary co-chairmen in the given org.
    Applies pending_role if set, otherwise demotes to officer (CSO) or member (regular orgs).
    Safe to call on every request — no-ops if nothing is expired.
    """
    from memberships.models import Membership
    now = timezone.now()
    # For CSO org, outgoing president becomes officer (still visible in org); for regular orgs, member
    fallback_role = 'officer' if org.is_cso else 'member'
    expired = Membership.objects.filter(
        organization=org,
        role='co_chairman',
        co_chairman_expiry__isnull=False,
        co_chairman_expiry__lte=now,
        status='active',
    )
    for m in expired:
        if m.pending_role:
            m.role = m.pending_role
            m.has_chairman_privileges = m.pending_role == 'co_chairman'
            m.custom_role = m.pending_custom_role
            m.pending_role = None
            m.pending_custom_role = None
        else:
            m.role = fallback_role
            m.has_chairman_privileges = False
            m.custom_role = None
        m.co_chairman_expiry = None
        m.save()
        # Notify the demoted user
        try:
            from announcements.utils import send_notification
            from django.urls import reverse
            send_notification(
                title=f'Your co-chairman access for {org.name} has expired',
                message=f'Your temporary co-chairman access for {org.name} has ended. You are now a {m.role.replace("_", "-")}.',
                recipients=[m.user],
                organization=org,
                link_url=reverse('organizations:org_profile', kwargs={'org_id': org.id}),
                notification_type='organization',
            )
        except Exception:
            pass  # Never block expiry logic if notification fails


def expire_all_co_chairmen():
    """
    Bulk-expire all overdue temporary co-chairmen across all orgs.
    Called on high-traffic views (dashboard, election list) to catch stragglers.
    """
    from memberships.models import Membership
    now = timezone.now()
    expired = Membership.objects.filter(
        role='co_chairman',
        co_chairman_expiry__isnull=False,
        co_chairman_expiry__lte=now,
        status='active',
    ).select_related('pending_custom_role', 'organization')
    for m in expired:
        if m.pending_role:
            m.role = m.pending_role
            m.has_chairman_privileges = m.pending_role == 'co_chairman'
            m.custom_role = m.pending_custom_role
            m.pending_role = None
            m.pending_custom_role = None
        else:
            # CSO outgoing president becomes officer (stays visible); regular orgs become member
            m.role = 'officer' if m.organization.is_cso else 'member'
            m.has_chairman_privileges = False
            m.custom_role = None
        m.co_chairman_expiry = None
        m.save()


# ─── CSO admin / temp admin expiry ───────────────────────────────────────────

def expire_cso_admin_for_user(user):
    """
    Revoke CSO admin access for a single user if their expiry has passed.
    Also demotes their CSO org co-chairman membership if applicable.
    Safe to call on every request — no-ops if not expired.
    """
    if not user.is_authenticated:
        return
    if not user.is_cso_admin or not user.cso_admin_expiry:
        return
    now = timezone.now()
    if user.cso_admin_expiry > now:
        return

    # Expiry has passed — revoke
    user.is_cso_admin = False
    user.is_manually_granted_admin = False
    user.cso_admin_expiry = None
    user.save(update_fields=['is_cso_admin', 'is_manually_granted_admin', 'cso_admin_expiry'])

    # Also demote in CSO org if they're a temp co-chairman there
    from organizations.models import Organization
    from memberships.models import Membership
    cso_org = Organization.objects.filter(is_cso=True).first()
    if cso_org:
        m = Membership.objects.filter(
            user=user,
            organization=cso_org,
            role='co_chairman',
            co_chairman_expiry__isnull=False,
            status='active',
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


def expire_all_cso_admins():
    """
    Bulk-expire all overdue temporary CSO admin users.
    Called on admin panel views.
    """
    from accounts.models import User
    from organizations.models import Organization
    from memberships.models import Membership
    now = timezone.now()
    expired_users = User.objects.filter(
        is_cso_admin=True,
        cso_admin_expiry__isnull=False,
        cso_admin_expiry__lte=now,
    )
    cso_org = Organization.objects.filter(is_cso=True).first()
    for u in expired_users:
        u.is_cso_admin = False
        u.is_manually_granted_admin = False
        u.cso_admin_expiry = None
        u.save(update_fields=['is_cso_admin', 'is_manually_granted_admin', 'cso_admin_expiry'])
        if cso_org:
            m = Membership.objects.filter(
                user=u, organization=cso_org,
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


# ─── Scheduled announcements ──────────────────────────────────────────────────

def publish_due_announcements():
    """
    Activate any scheduled announcements whose scheduled_at has passed.
    Called on announcement list/dashboard views.
    """
    from announcements.models import Announcement
    now = timezone.now()
    Announcement.objects.filter(
        is_active=False,
        scheduled_at__isnull=False,
        scheduled_at__lte=now,
    ).update(is_active=True)


# ─── Elections ────────────────────────────────────────────────────────────────

def close_overdue_elections():
    """
    Bulk-close all open elections whose end_datetime has passed.
    Called on the election list view.
    """
    from elections.models import Election
    now = timezone.now()
    Election.objects.filter(
        status='open',
        end_datetime__isnull=False,
        end_datetime__lte=now,
    ).update(status='closed', closed_at=now)


def open_scheduled_elections():
    """
    Open any draft elections whose start_datetime has arrived and snapshot
    their voter pools. Called on the election list view alongside
    close_overdue_elections so the system works without Celery.
    """
    from elections.models import Election, ElectionVoter
    from elections.utils import compute_voter_pool
    now = timezone.now()
    due = Election.objects.filter(
        status='draft',
        start_datetime__isnull=False,
        start_datetime__lte=now,
        end_datetime__gt=now,  # only open if closing time hasn't passed yet
    )
    for election in due:
        pool = compute_voter_pool(election)
        if not pool.exists():
            continue  # skip — pool empty, leave as draft
        ElectionVoter.objects.filter(election=election).delete()
        ElectionVoter.objects.bulk_create(
            [ElectionVoter(election=election, user=user) for user in pool],
            ignore_conflicts=True,
        )
        election.status = 'open'
        election.start_datetime = now
        election.save(update_fields=['status', 'start_datetime'])
        # Best-effort notification
        try:
            from announcements.utils import send_notification
            from django.urls import reverse
            voter_users = list(pool)
            if voter_users:
                send_notification(
                    title=f'Election open — {election.title}',
                    message=(
                        f'The election "{election.title}" for {election.organization.name} '
                        f'is now open. Cast your vote!'
                    ),
                    recipients=voter_users,
                    organization=election.organization,
                    link_url=reverse('elections:election_vote', kwargs={'election_id': election.id}),
                    notification_type='election:open',
                )
        except Exception:
            pass


def enforce_election_schedule(election):
    """
    Enforce schedule for a single election object.
    - Opens draft elections whose start_datetime has arrived.
    - Closes open elections whose end_datetime has passed.
    Returns the updated election.
    """
    from elections.models import ElectionVoter
    from elections.utils import compute_voter_pool
    now = timezone.now()

    if election.status == 'draft':
        if (election.start_datetime and now >= election.start_datetime
                and election.end_datetime and now < election.end_datetime):
            pool = compute_voter_pool(election)
            if pool.exists():
                ElectionVoter.objects.filter(election=election).delete()
                ElectionVoter.objects.bulk_create(
                    [ElectionVoter(election=election, user=user) for user in pool],
                    ignore_conflicts=True,
                )
                election.status = 'open'
                election.save(update_fields=['status'])

    if election.status == 'open':
        if election.end_datetime and now >= election.end_datetime:
            election.status = 'closed'
            election.closed_at = now
            election.save(update_fields=['status', 'closed_at'])

    return election
