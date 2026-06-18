from django.db import migrations


def set_org_status_from_is_active(apps, schema_editor):
    Organization = apps.get_model('organizations', 'Organization')

    # CSO orgs are always active
    Organization.objects.filter(is_cso=True).update(status='active')

    # Active non-CSO orgs
    Organization.objects.filter(is_active=True, is_cso=False).update(status='active')

    # Inactive non-CSO orgs
    Organization.objects.filter(is_active=False, is_cso=False).update(status='rejected')


def reverse_set_org_status(apps, schema_editor):
    # Reverse: restore is_active from status (best-effort)
    Organization = apps.get_model('organizations', 'Organization')
    active_statuses = {'probationary', 'institutional', 'active', 'renewal_due', 'lapsed'}
    for org in Organization.objects.all():
        org.is_active = org.status in active_statuses
        org.save()


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0012_add_accreditation_models'),
    ]

    operations = [
        migrations.RunPython(
            set_org_status_from_is_active,
            reverse_code=reverse_set_org_status,
        ),
    ]
