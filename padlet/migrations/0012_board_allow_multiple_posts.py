from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('padlet', '0011_add_post_title_link_url_video_attachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='board',
            name='allow_multiple_posts',
            field=models.BooleanField(default=False, help_text='Allow members to post more than once on this board'),
        ),
    ]
