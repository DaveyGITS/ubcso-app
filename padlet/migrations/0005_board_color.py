from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('padlet', '0004_board_cover_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='board',
            name='board_color',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=30,
                help_text='Color theme for org boards',
            ),
        ),
    ]
