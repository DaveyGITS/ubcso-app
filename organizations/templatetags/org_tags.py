from django import template

register = template.Library()


@register.simple_tag
def role_display(membership):
    """
    Returns the display label for a membership role.
    For CSO org, 'chairman' → 'President', 'co_chairman' → 'Vice President'.
    """
    if membership.custom_role_id and membership.custom_role:
        return membership.custom_role.name

    role = membership.role
    try:
        is_cso = membership.organization.is_cso
    except Exception:
        is_cso = False

    if is_cso:
        if role == 'chairman':
            return 'President'
        elif role == 'co_chairman':
            return 'Vice President'

    return membership.get_role_display()


@register.simple_tag
def is_privileged_user(user, org):
    """Returns True if user is an active chairman or co-chairman of the org."""
    from memberships.models import Membership
    return Membership.objects.filter(
        user=user,
        organization=org,
        status='active',
        role__in=['chairman', 'co_chairman'],
    ).exists()


@register.filter(name='doc_field_name')
def doc_field_name(title):
    """
    Converts a document title to the field name used in accreditation upload forms.
    Matches the logic in accreditation_apply_view:
      field_name = f'doc_{doc_type.lower().replace(" ", "_").replace("-", "_")}'
    Example: 'Letter of Intent' → 'doc_letter_of_intent'
             'Constitution and By-laws' → 'doc_constitution_and_by_laws'
    """
    return 'doc_' + title.lower().replace(' ', '_').replace('-', '_')
