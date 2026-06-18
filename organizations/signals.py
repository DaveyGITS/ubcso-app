from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='organizations.OrgShowcase')
def cleanup_empty_showcase(sender, instance, **kwargs):
    """Delete OrgShowcase record when both image and video_post become NULL/empty."""
    if not instance.image and instance.video_post_id is None:
        instance.delete()
