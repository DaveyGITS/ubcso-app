from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('padlet', '0003_add_is_pinned_remove_column'),
    ]

    operations = [
        migrations.AddField(
            model_name='board',
            name='cover_image',
            field=models.ImageField(blank=True, null=True, upload_to='padlet_covers/'),
        ),
    ]
