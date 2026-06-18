from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('padlet', '0005_board_color'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='pos_x',
            field=models.FloatField(default=5.0),
        ),
        migrations.AddField(
            model_name='post',
            name='pos_y',
            field=models.FloatField(default=5.0),
        ),
    ]
