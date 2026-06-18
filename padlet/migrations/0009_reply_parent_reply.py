from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('padlet', '0008_alter_board_title_maxlength'),
    ]

    operations = [
        migrations.AddField(
            model_name='reply',
            name='parent_reply',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='child_replies',
                to='padlet.reply',
            ),
        ),
    ]
