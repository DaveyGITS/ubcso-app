from celery import shared_task
from django.utils import timezone


@shared_task
def auto_close_election(election_id):
    """Auto-close an election when its end_datetime is reached."""
    from .models import Election
    try:
        election = Election.objects.get(pk=election_id, status='open')
        election.status = 'closed'
        election.closed_at = timezone.now()
        election.save(update_fields=['status', 'closed_at'])
    except Election.DoesNotExist:
        pass  # Already closed or doesn't exist — no-op


@shared_task
def auto_open_election(election_id):
    """
    Auto-open a scheduled election at its start_datetime.
    Snapshots the voter pool at open time (not at scheduling time),
    sends notifications, and schedules the auto-close task.
    """
    from .models import Election, ElectionVoter
    from .utils import compute_voter_pool

    try:
        election = Election.objects.get(pk=election_id, status='draft')
    except Election.DoesNotExist:
        return  # Already opened, cancelled, or deleted — no-op

    now = timezone.now()

    # Snapshot voter pool at open time
    pool = compute_voter_pool(election)
    if not pool.exists():
        # Pool is empty — can't open, leave as draft
        import logging
        logging.getLogger(__name__).warning(
            f'auto_open_election: voter pool empty for election {election_id}, skipping open.'
        )
        return

    ElectionVoter.objects.filter(election=election).delete()
    ElectionVoter.objects.bulk_create(
        [ElectionVoter(election=election, user=user) for user in pool],
        ignore_conflicts=True,
    )

    election.status = 'open'
    election.start_datetime = now
    election.save(update_fields=['status', 'start_datetime'])

    # Schedule auto-close
    try:
        auto_close_election.apply_async(
            args=[election.id],
            eta=election.end_datetime,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f'auto_open_election: could not schedule auto-close for election {election_id}: {e}'
        )

    # Notify voters
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
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f'auto_open_election: notification failed for election {election_id}: {e}'
        )
