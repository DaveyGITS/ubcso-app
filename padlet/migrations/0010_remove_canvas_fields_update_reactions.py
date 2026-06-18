"""
Migration: Remove canvas positioning fields (pos_x, pos_y, z_index) from Post,
add 'white' color choice, and expand PostReaction emoji choices.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('padlet', '0009_reply_parent_reply'),
    ]

    operations = [
        # Remove canvas positioning fields
        migrations.RemoveField(model_name='post', name='pos_x'),
        migrations.RemoveField(model_name='post', name='pos_y'),
        migrations.RemoveField(model_name='post', name='z_index'),

        # Update Post color choices (add 'white')
        migrations.AlterField(
            model_name='post',
            name='color',
            field=models.CharField(
                choices=[
                    ('yellow', 'Yellow'),
                    ('blue', 'Blue'),
                    ('green', 'Green'),
                    ('pink', 'Pink'),
                    ('purple', 'Purple'),
                    ('white', 'White'),
                ],
                default='yellow',
                max_length=10,
            ),
        ),

        # Update Post ordering
        migrations.AlterModelOptions(
            name='post',
            options={'ordering': ['-is_pinned', '-created_at']},
        ),

        # Expand PostReaction emoji choices and field length
        migrations.AlterField(
            model_name='postreaction',
            name='emoji',
            field=models.CharField(
                choices=[
                    ('heart',       '❤️'),
                    ('laugh',       '😂'),
                    ('wow',         '😮'),
                    ('sad',         '😢'),
                    ('thumbsup',    '👍'),
                    ('thumbsdown',  '👎'),
                ],
                max_length=15,
            ),
        ),
    ]
