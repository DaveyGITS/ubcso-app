from celery import shared_task


@shared_task
def publish_scheduled_announcement(announcement_id):
    """Activate a scheduled announcement at its scheduled time."""
    from .models import Announcement
    try:
        ann = Announcement.objects.get(pk=announcement_id, is_active=False)
        ann.is_active = True
        ann.save(update_fields=['is_active'])
    except Announcement.DoesNotExist:
        pass  # Already published or deleted
