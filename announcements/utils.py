from .models import Notification, NotificationRecipient


def send_notification(title, message, recipients, sender=None, organization=None, is_priority=False, link_url=None, notification_type=None):
    """
    Create an in-app notification and optionally send email to recipients
    who have email_notifications enabled.
    
    Args:
        title: Notification title
        message: Notification message
        recipients: iterable of User instances
        sender: User who sent the notification (optional)
        organization: Related organization (optional)
        is_priority: Whether this is a priority notification
        link_url: URL to navigate to when notification is clicked (optional)
        notification_type: Category of notification - 'membership', 'election', 'report', 'organization', 'system', 'profile' (optional)
    """
    notification = Notification.objects.create(
        title=title,
        message=message,
        sender=sender,
        organization=organization,
        is_priority=is_priority,
        delivery='in_app',
        link_url=link_url,
        notification_type=notification_type,
    )
    NotificationRecipient.objects.bulk_create([
        NotificationRecipient(notification=notification, user=user)
        for user in recipients
    ], ignore_conflicts=True)

    # Send email to recipients who have email notifications enabled
    email_recipients = [u for u in recipients if getattr(u, 'email_notifications', True) and u.email]
    if email_recipients:
        try:
            _send_email_notification(title, message, email_recipients, organization)
        except Exception:
            pass  # Never block in-app notification if email fails

    return notification


def _send_email_notification(title, message, recipients, organization=None):
    """Send a plain email notification to a list of users."""
    from django.core.mail import send_mail
    from django.conf import settings

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@universityofbohol.edu.ph')
    org_name = organization.name if organization else 'UB-CSO'

    subject = f'[{org_name}] {title}'
    body = f'{title}\n\n{message}\n\n---\nThis is an automated notification from the UB-CSO Portal.\nTo turn off email notifications, update your preferences in your profile settings.'

    for user in recipients:
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=from_email,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            pass
