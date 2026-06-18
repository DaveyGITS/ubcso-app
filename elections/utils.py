from django.db.models import Count, Q
from organizations.constants import PUBLICLY_VISIBLE_STATUSES


def is_election_manager(user, organization):
    """
    True if user is chairman/co_chairman of the specific org.
    CSO president only manages elections for the CSO org itself — not other orgs.
    CSO admins have no election management rights over other orgs' elections.
    """
    if not user.is_authenticated:
        return False
    from memberships.models import Membership
    return Membership.objects.filter(
        user=user,
        organization=organization,
        status='active',
        role__in=['chairman', 'co_chairman', 'adviser'],
    ).exists()


def compute_voter_pool(election):
    """
    Combines all selected voter criteria for the election.
    Returns a deduplicated User queryset.
    """
    from accounts.models import User
    from memberships.models import Membership
    from organizations.models import Organization

    pks = set()

    if election.voters_all_students:
        all_student_pks = set(User.objects.filter(
            is_active=True
        ).values_list('pk', flat=True))
        # Exclude users who are active advisers OR were advisers during the current academic period.
        # This prevents a chairman from demoting an adviser to officer right before opening the
        # election to sneak them into the voter pool.
        from core.models import AcademicPeriod
        from django.utils import timezone as _tz
        current_period = AcademicPeriod.objects.filter(is_current=True).first()
        if current_period:
            # Exclude anyone whose adviser_since falls within the current period, OR who is
            # currently an adviser regardless of adviser_since value, OR who is faculty
            adviser_pks = set(Membership.objects.filter(
                status='active',
            ).filter(
                # Currently an adviser
                Q(role='adviser') |
                # Or was promoted to adviser during this academic period
                Q(
                    adviser_since__gte=current_period.start_date,
                    adviser_since__isnull=False,
                )
            ).values_list('user_id', flat=True))
            # Also exclude all faculty users (they are advisers by nature)
            from accounts.models import User as _User
            adviser_pks |= set(_User.objects.filter(is_faculty=True, is_active=True).values_list('pk', flat=True))
        else:
            # No academic period configured — fall back to checking current role and faculty flag
            adviser_pks = set(Membership.objects.filter(
                role='adviser',
                status='active',
            ).values_list('user_id', flat=True))
            from accounts.models import User as _User
            adviser_pks |= set(_User.objects.filter(is_faculty=True, is_active=True).values_list('pk', flat=True))
        pks |= all_student_pks - adviser_pks

    if election.voters_org_members:
        # Active members of THIS org only
        pks |= set(Membership.objects.filter(
            organization=election.organization,
            status='active',
        ).values_list('user_id', flat=True))

    if election.voters_org_officers:
        # Officers + co_chairman + chairman of THIS org only
        pks |= set(Membership.objects.filter(
            organization=election.organization,
            role__in=['officer', 'co_chairman', 'chairman'],
            status='active',
        ).values_list('user_id', flat=True))

    if election.voters_all_officers:
        # Officers + co_chairman + chairman across ALL orgs (publicly visible only)
        pks |= set(Membership.objects.filter(
            role__in=['officer', 'co_chairman', 'chairman'],
            status='active',
            organization__status__in=PUBLICLY_VISIBLE_STATUSES,
        ).values_list('user_id', flat=True))

    if election.voters_all_chairmen:
        pks |= set(Membership.objects.filter(
            role='chairman', status='active',
            organization__status__in=PUBLICLY_VISIBLE_STATUSES,
        ).values_list('user_id', flat=True))

    if election.voters_cso_officers:
        cso_org = Organization.objects.filter(is_cso=True).first()
        if cso_org:
            pks |= set(Membership.objects.filter(
                organization=cso_org,
                role__in=['officer', 'co_chairman', 'chairman'],
                status='active'
            ).values_list('user_id', flat=True))

    if election.voters_specific_orgs.exists():
        pks |= set(Membership.objects.filter(
            organization__in=election.voters_specific_orgs.all(),
            organization__status__in=PUBLICLY_VISIBLE_STATUSES,
            status='active'
        ).values_list('user_id', flat=True))

    if election.voters_specific_users.exists():
        pks |= set(election.voters_specific_users.values_list('pk', flat=True))

    return User.objects.filter(pk__in=pks)


def get_voter_pool_description(election):
    """
    Returns a human-readable list of strings describing who the voters are.
    e.g. ["All registered students", "This org's members"]
    """
    parts = []
    if election.voters_all_students:
        parts.append("All registered students")
    if election.voters_org_members:
        parts.append(f"All active members of {election.organization.name}")
    if election.voters_org_officers:
        parts.append(f"Officers of {election.organization.name}")
    if election.voters_all_officers:
        parts.append("Officers across all organizations")
    if election.voters_all_chairmen:
        parts.append("Chairmen across all organizations")
    if election.voters_cso_officers:
        parts.append("CSO officers only")
    if election.voters_specific_orgs.exists():
        org_names = ", ".join(election.voters_specific_orgs.values_list('name', flat=True))
        parts.append(f"Members of: {org_names}")
    if election.voters_specific_users.exists():
        parts.append("Individually selected students")
    return parts if parts else ["No voter criteria configured"]


def get_vote_tally(election):
    """
    Returns {str(position_id): {'candidates': [...], 'is_tied': bool}}
    Each candidate: {'candidate_id', 'name', 'count', 'profile_picture'}
    is_tied is True when the top two or more candidates share the highest vote count.
    Ordered by vote count descending.
    """
    from .models import Candidate

    result = {}
    for position in election.positions.all():
        candidates = Candidate.objects.filter(
            position=position
        ).annotate(
            vote_count=Count('votes')
        ).select_related('user').order_by('-vote_count')

        candidate_list = [
            {
                'candidate_id': c.id,
                'name': c.user.get_full_name(),
                'count': c.vote_count,
                'profile_picture': c.user.profile_picture.url if c.user.profile_picture else None,
            }
            for c in candidates
        ]

        # Detect tie: top two or more candidates share the same highest count
        is_tied = (
            len(candidate_list) >= 2 and
            candidate_list[0]['count'] > 0 and
            candidate_list[0]['count'] == candidate_list[1]['count']
        )

        # Detect no contest: no votes cast at all for this position
        no_contest = len(candidate_list) > 0 and candidate_list[0]['count'] == 0

        result[str(position.id)] = {
            'candidates': candidate_list,
            'is_tied': is_tied,
            'no_contest': no_contest,
        }
    return result
