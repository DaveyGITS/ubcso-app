# Generated migration for adding link_url and notification_type fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('announcements', '0002_add_notification_recipient'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='link_url',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('membership', 'Membership'),
                    ('election', 'Election'),
                    ('report', 'Report'),
                    ('organization', 'Organization'),
                    ('system', 'System'),
                    ('profile', 'Profile'),
                ],
                max_length=50,
                null=True,
            ),
        ),
    ]
