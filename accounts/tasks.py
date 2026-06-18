from celery import shared_task


@shared_task
def cleanup_old_otp_tokens():
    """Delete OTP tokens older than 7 days."""
    from accounts.models import OTPToken
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff = timezone.now() - timedelta(days=7)
    deleted_count, _ = OTPToken.objects.filter(created_at__lt=cutoff).delete()
    return f'Deleted {deleted_count} old OTP tokens'
