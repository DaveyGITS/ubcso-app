"""
Data migration: promote any CSO org members with role='member' to role='officer'.

These are former presidents/officers who were incorrectly demoted to 'member'
when their 24hr transition window expired. In the CSO org, 'member' is invisible
in the leadership list — they should be 'officer' at minimum.
"""
from django.db import migrations


def fix_cso_member_roles(apps, schema_editor):
    Organization = apps.get_model('organizations', 'Organization')
    Membership = apps.get_model('memberships', 'Membership')

    cso_org = Organization.objects.filter(is_cso=True).first()
    if not cso_org:
        return

    # Promote all active 'member' role people in the CSO org to 'officer'
    updated = Membership.objects.filter(
        organization=cso_org,
        role='member',
        status='active',
    ).update(role='officer')

    if updated:
        print(f'\n  Fixed {updated} CSO org member(s) → officer')


def reverse_fix(apps, schema_editor):
    # No safe reverse — leave as-is
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0013_set_org_status_from_is_active'),
        ('memberships', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(fix_cso_member_roles, reverse_code=reverse_fix),
    ]
