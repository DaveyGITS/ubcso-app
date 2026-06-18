# Generated migration to re-add is_public field to Board model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('padlet', '0016_board_created_by_set_null'),
    ]

    operations = [
        migrations.AddField(
            model_name='board',
            name='is_public',
            field=models.BooleanField(default=False, help_text='Make this org board visible to all students (only applies to org boards)'),
        ),
    ]
