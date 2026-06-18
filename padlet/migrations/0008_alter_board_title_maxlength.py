from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('padlet', '0007_post_z_index'),
    ]

    operations = [
        migrations.AlterField(
            model_name='board',
            name='title',
            field=models.CharField(max_length=50),
        ),
    ]
