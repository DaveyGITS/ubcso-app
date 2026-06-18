# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0009_alter_orgphoto_options_orgphoto_caption_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='orgshowcase',
            name='description',
            field=models.TextField(default='', help_text='Description shown on hover', max_length=500),
            preserve_default=False,
        ),
    ]
