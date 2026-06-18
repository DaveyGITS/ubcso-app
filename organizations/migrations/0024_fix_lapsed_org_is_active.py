"""
Data migration: set is_active=False for all existing lapsed organizations.

The ACTIVE_STATUSES set was updated to exclude 'lapsed', but existing rows
in the database still had is_active=True. This migration corrects them.
"""
from django.db import migrations


def fix_lapsed_orgs(apps, schema_editor):
    Organization = apps.get_model('organizations', 'Organization')
    count = Organization.objects.filter(status='lapsed', is_active=True).update(is_active=False)
    if count:
        print(f'  Set is_active=False for {count} lapsed organization(s).')


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0023_accreditationdocument_compilation_id_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_lapsed_orgs, migrations.RunPython.noop),
    ]
