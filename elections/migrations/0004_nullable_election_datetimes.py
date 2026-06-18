from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('elections', '0003_update_voter_pool_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='election',
            name='start_datetime',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='election',
            name='end_datetime',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
