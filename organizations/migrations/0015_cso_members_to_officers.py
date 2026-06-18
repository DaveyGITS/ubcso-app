"""
Data migration: promote any remaining CSO org members with role='member' to role='officer'.

CSO org is composed entirely of officers/leaders — plain 'member' role is no longer used.
"""
from django.db import migrations


def promote_cso_members_to_officers(apps, schema_editor):
    Organization = apps.get_model('organizations', 'Organization')
    Membership = apps.get_model('memberships', 'Membership')

    cso_org = Organization.objects.filter(is_cso=True).first()
    if not cso_org:
        return

    updated = Membership.objects.filter(
        organization=cso_org,
        role='member',
        status='active',
    ).update(role='officer')

    if updated:
        print(f'  Promoted {updated} CSO member(s) to officer.')


def reverse_migration(apps, schema_editor):
    # Not reversible — don't demote back to member
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0023_accreditationdocument_compilation_id_and_more'),
    ]

    operations = [
        migrations.RunPython(promote_cso_members_to_officers, reverse_migration),
    ]
