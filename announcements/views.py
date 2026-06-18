from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Notification, NotificationRead


@login_required
def notifications_view(request):
    user_notifications = Notification.objects.filter(
        recipients__user=request.user
    ).select_related('sender', 'organization').order_by('-created_at')

    # Get read IDs for this user once — avoids N+1 queries
    read_ids = set(
        user_notifications.filter(reads__user=request.user).values_list('id', flat=True)
    )

    all_notifs = list(user_notifications)
    total_count = len(all_notifs)
    unread_count = total_count - len(read_ids)

    return render(request, 'announcements/notifications.html', {
        'notifications': all_notifs,
        'read_ids': read_ids,
        'total_count': total_count,
        'unread_count': unread_count,
    })


@login_required
def mark_all_read_view(request):
    """Mark all notifications as read."""
    from django.utils import timezone
    if request.method == 'POST':
        unread = Notification.objects.filter(
            recipients__user=request.user
        ).exclude(reads__user=request.user)
        for n in unread:
            NotificationRead.objects.get_or_create(
                notification=n,
                user=request.user,
                defaults={'read_at': timezone.now()}
            )
    return redirect('announcements:notifications')


@login_required
def mark_notification_read_view(request, notification_id):
    """AJAX endpoint — mark a single notification as read when clicked."""
    from django.http import JsonResponse
    from django.utils import timezone

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    notif = get_object_or_404(
        Notification,
        id=notification_id,
        recipients__user=request.user,
    )
    NotificationRead.objects.get_or_create(
        notification=notif,
        user=request.user,
        defaults={'read_at': timezone.now()},
    )
    return JsonResponse({'ok': True})
