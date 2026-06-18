import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ubcso.settings')

app = Celery('ubcso')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Periodic tasks
app.conf.beat_schedule = {
    'cleanup-old-otp-tokens': {
        'task': 'accounts.tasks.cleanup_old_otp_tokens',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
    },
}
