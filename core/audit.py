# core/audit.py
"""
Audit logging utility for tracking critical system actions.
"""

from django.contrib.contenttypes.models import ContentType
from .models import AuditLog


def log_action(actor, action, target=None, details='', request=None):
    """
    Create an audit log entry.
    
    Args:
        actor: User performing the action
        action: String describing the action (e.g., 'presidency_transfer', 'org_created')
        target: Optional object that was acted upon
        details: Optional additional details
        request: Optional HTTP request object for IP tracking
    
    Returns:
        AuditLog instance
    """
    log_data = {
        'actor': actor,
        'action': action,
        'details': details,
    }
    
    # Add target information if provided
    if target:
        log_data['target_type'] = ContentType.objects.get_for_model(target)
        log_data['target_id'] = target.id
    
    # Add IP address if request provided
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            log_data['ip_address'] = x_forwarded_for.split(',')[0]
        else:
            log_data['ip_address'] = request.META.get('REMOTE_ADDR')
    
    return AuditLog.objects.create(**log_data)


# Predefined action types for consistency
class AuditActions:
    # User actions
    USER_REGISTERED = 'user_registered'
    USER_LOGIN = 'user_login'
    USER_LOGOUT = 'user_logout'
    USER_DEACTIVATED = 'user_deactivated'
    USER_REACTIVATED = 'user_reactivated'
    
    # Organization actions
    ORG_CREATED = 'org_created'
    ORG_APPROVED = 'org_approved'
    ORG_REJECTED = 'org_rejected'
    ORG_DISSOLVED = 'org_dissolved'
    ORG_UPDATED = 'org_updated'
    
    # Membership actions
    MEMBERSHIP_REQUESTED = 'membership_requested'
    MEMBERSHIP_APPROVED = 'membership_approved'
    MEMBERSHIP_REJECTED = 'membership_rejected'
    MEMBER_ADDED = 'member_added'
    MEMBER_REMOVED = 'member_removed'
    MEMBER_PROMOTED = 'member_promoted'
    MEMBER_DEMOTED = 'member_demoted'
    
    # Role actions
    CUSTOM_ROLE_CREATED = 'custom_role_created'
    CUSTOM_ROLE_ASSIGNED = 'custom_role_assigned'
    CUSTOM_ROLE_REMOVED = 'custom_role_removed'
    
    # Chairman/Leadership actions
    CHAIRMAN_HANDOVER = 'chairman_handover'
    CO_CHAIRMAN_GRANTED = 'co_chairman_granted'
    CO_CHAIRMAN_REVOKED = 'co_chairman_revoked'
    CO_CHAIRMAN_EXPIRED = 'co_chairman_expired'
    
    # Presidency actions
    PRESIDENCY_TRANSFER = 'presidency_transfer'
    TEMP_ADMIN_GRANTED = 'temp_admin_granted'
    TEMP_ADMIN_REVOKED = 'temp_admin_revoked'
    TEMP_ADMIN_EXPIRED = 'temp_admin_expired'
    
    # Admin privilege actions
    ADMIN_GRANTED = 'admin_granted'
    ADMIN_REVOKED = 'admin_revoked'
    
    # Election actions
    ELECTION_CREATED = 'election_created'
    ELECTION_OPENED = 'election_opened'
    ELECTION_CLOSED = 'election_closed'
    ELECTION_RESULTS_RELEASED = 'election_results_released'
    CANDIDATE_NOMINATED = 'candidate_nominated'
    CANDIDATE_REMOVED = 'candidate_removed'
    VOTE_CAST = 'vote_cast'
    
    # Report actions
    REPORT_SUBMITTED = 'report_submitted'
    REPORT_APPROVED = 'report_approved'
    REPORT_REJECTED = 'report_rejected'
    
    # Announcement actions
    ANNOUNCEMENT_CREATED = 'announcement_created'
    ANNOUNCEMENT_SCHEDULED = 'announcement_scheduled'
    ANNOUNCEMENT_PUBLISHED = 'announcement_published'
    ANNOUNCEMENT_DELETED = 'announcement_deleted'
    
    # Poll actions
    POLL_CREATED = 'poll_created'
    POLL_CLOSED = 'poll_closed'
    POLL_VOTED = 'poll_voted'
    
    # Leave request actions
    LEAVE_REQUESTED = 'leave_requested'
    LEAVE_APPROVED = 'leave_approved'
    LEAVE_REJECTED = 'leave_rejected'
    
    # Profile correction actions
    CORRECTION_REQUESTED = 'correction_requested'
    CORRECTION_APPROVED = 'correction_approved'
    CORRECTION_REJECTED = 'correction_rejected'
    
    # Academic period actions
    PERIOD_CREATED = 'period_created'
    PERIOD_ACTIVATED = 'period_activated'
    YEAR_TRANSITION = 'year_transition'
    
    # System settings actions
    SETTINGS_UPDATED = 'settings_updated'
    CATEGORY_CREATED = 'category_created'
    CATEGORY_DELETED = 'category_deleted'
    COURSE_CREATED = 'course_created'
    COURSE_DELETED = 'course_deleted'
