from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_add_manually_granted_admin_flag'),
    ]

    operations = [
        migrations.AddField(
            model_name='profilecorrectionrequest',
            name='rejection_reason',
            field=models.TextField(blank=True, null=True),
        ),
    ]
