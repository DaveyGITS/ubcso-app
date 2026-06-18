# Generated migration for adding pre_renewal_status field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0021_alter_accreditationapplication_registration_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='pre_renewal_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('pending', 'Pending'),
                    ('under_review', 'Under Review'),
                    ('probationary', 'Probationary'),
                    ('institutional', 'Institutional'),
                    ('active', 'Active'),
                    ('renewal_due', 'Renewal Due'),
                    ('lapsed', 'Lapsed'),
                    ('rejected', 'Rejected'),
                ],
                help_text='Stores the status before transitioning to renewal_due for proper restoration on renewal approval',
                max_length=20,
                null=True,
            ),
        ),
    ]
