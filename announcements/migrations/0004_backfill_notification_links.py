"""
Data migration: backfill link_url and notification_type on existing notifications
by pattern-matching their titles against the known notification patterns.
"""
from django.db import migrations


def backfill_notification_links(apps, schema_editor):
    Notification = apps.get_model('announcements', 'Notification')

    for notif in Notification.objects.select_related('organization'):
        title = notif.title or ''
        t = title.lower()
        org = notif.organization
        org_id = org.id if org else None

        link_url = None
        notification_type = None

        # ── Membership ────────────────────────────────────────────────────────
        if 'new membership request' in t or ('membership request' in t and 'rejected' not in t and 'approved' not in t):
            notification_type = 'membership'
            link_url = f'/directory/{org_id}/manage/members/' if org_id else '/memberships/requests/'

        elif 'membership approved' in t:
            notification_type = 'membership'
            link_url = f'/directory/{org_id}/' if org_id else '/memberships/requests/'

        elif 'membership request rejected' in t:
            notification_type = 'membership'
            link_url = f'/directory/{org_id}/' if org_id else '/dashboard/'

        elif 'membership confirmed' in t:
            notification_type = 'membership'
            link_url = f'/directory/{org_id}/' if org_id else '/dashboard/'

        elif 'invited to join' in t:
            notification_type = 'membership'
            link_url = '/memberships/requests/'

        elif 'accepted your invite' in t:
            notification_type = 'membership'
            link_url = f'/directory/{org_id}/manage/members/' if org_id else '/dashboard/'

        elif 'joined' in t and org_id and 'auto-confirmed' in (notif.message or '').lower():
            notification_type = 'membership'
            link_url = f'/directory/{org_id}/manage/members/'

        elif 'leave request approved' in t:
            notification_type = 'membership'
            link_url = '/dashboard/'

        elif 'leave request rejected' in t:
            notification_type = 'membership'
            link_url = f'/directory/{org_id}/' if org_id else '/dashboard/'

        # ── Election ──────────────────────────────────────────────────────────
        elif 'election open' in t:
            notification_type = 'election'
            link_url = '/elections/'

        elif 'election results released' in t:
            notification_type = 'election'
            link_url = '/elections/'

        elif 'chairman role transferred' in t:
            notification_type = 'election'
            link_url = f'/directory/{org_id}/' if org_id else '/dashboard/'

        elif 'you are now chairman' in t:
            notification_type = 'election'
            link_url = f'/directory/{org_id}/' if org_id else '/dashboard/'

        # ── Report ────────────────────────────────────────────────────────────
        elif 'accomplishment report' in t:
            notification_type = 'report'
            link_url = '/reports/admin/'

        elif 'report approved' in t:
            notification_type = 'report'
            link_url = f'/reports/org/{org_id}/' if org_id else '/reports/admin/'

        elif 'report rejected' in t:
            notification_type = 'report'
            link_url = f'/reports/org/{org_id}/' if org_id else '/reports/admin/'

        # ── Organization ──────────────────────────────────────────────────────
        elif 'organization approved' in t:
            notification_type = 'organization'
            link_url = f'/directory/{org_id}/' if org_id else '/dashboard/'

        elif 'organization request rejected' in t:
            notification_type = 'organization'
            link_url = '/dashboard/'

        # ── System ────────────────────────────────────────────────────────────
        elif 'cso admin access' in t:
            notification_type = 'system'
            link_url = '/admin-panel/'

        elif 'cso admin' in t and 'revoked' in t:
            notification_type = 'system'
            link_url = '/dashboard/'

        elif 'cso president' in t or 'presidency transferred' in t:
            notification_type = 'system'
            link_url = '/admin-panel/'

        elif 'school year transition' in t:
            notification_type = 'system'
            link_url = '/auth/profile/'

        # ── Profile ───────────────────────────────────────────────────────────
        elif 'correction request' in t:
            notification_type = 'profile'
            if 'new profile correction' in t:
                link_url = '/admin-panel/correction-requests/'
            else:
                link_url = '/auth/profile/'

        # ── Noteboard ─────────────────────────────────────────────────────────
        elif 'replied to your note' in t or 'reacted to your note' in t or 'new note on' in t:
            notification_type = 'membership'
            link_url = '/noteboard/'

        if link_url or notification_type:
            notif.link_url = link_url
            notif.notification_type = notification_type
            notif.save(update_fields=['link_url', 'notification_type'])


def reverse_backfill(apps, schema_editor):
    Notification = apps.get_model('announcements', 'Notification')
    Notification.objects.all().update(link_url=None, notification_type=None)


class Migration(migrations.Migration):

    dependencies = [
        ('announcements', '0003_add_notification_link_and_type'),
    ]

    operations = [
        migrations.RunPython(backfill_notification_links, reverse_backfill),
    ]
