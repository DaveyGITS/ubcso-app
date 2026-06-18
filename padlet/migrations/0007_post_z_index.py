from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('padlet', '0006_post_pos_x_pos_y'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='z_index',
            field=models.IntegerField(default=1),
        ),
    ]
