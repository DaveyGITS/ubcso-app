import json
import mimetypes
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Board, Post, PostAttachment, PostReaction, Reply


# ─── Permission helpers ───────────────────────────────────────────────────────

def _is_board_manager(user, board):
    """
    System boards  → CSO chairman / co-chairman (is_cso_admin or is_cso_president)
    Org boards     → CSO admin/president (oversight), org chairman, org co-chairman, or board creator
    """
    # CSO admins/presidents can manage all boards (edit/archive/delete) — but cannot post on org boards they're not members of
    if user.is_cso_admin or user.is_cso_president:
        return True

    # Org board: board creator or org chairman/co-chairman
    if board.created_by == user:
        return True
    if board.scope == 'org' and board.organization:
        from memberships.models import Membership
        return Membership.objects.filter(
            user=user,
            organization=board.organization,
            role__in=['chairman', 'co_chairman'],
            status='active',
            organization__is_active=True,
        ).exists()
    return False


def _can_post_on_board(user, board):
    """
    System boards → all students can post.
    Org boards    → active members of that org can post (managers included via membership
                    or creator shortcut).
    """
    if board.scope == 'system':
        return True

    # Board creator always allowed on org boards
    if board.created_by == user:
        return True

    from memberships.models import Membership
    return Membership.objects.filter(
        user=user, organization=board.organization, status='active', organization__is_active=True,
    ).exists()


def _can_see_board(user, board):
    """
    System boards → visible to all students.
    Org boards    → visible to active members, board creator, CSO admins, and all students if is_public=True.
    """
    if board.scope == 'system':
        return True

    # Public org boards are visible to all students
    if board.scope == 'org' and board.is_public:
        return True

    # CSO admins/presidents can see all org boards (oversight)
    if user.is_cso_admin or user.is_cso_president:
        return True

    # Board creator can always see their own board
    if board.created_by == user:
        return True

    from memberships.models import Membership
    return Membership.objects.filter(
        user=user, organization=board.organization, status='active', organization__is_active=True,
    ).exists()


def _can_create_board(user):
    """
    System boards → CSO chairman/co-chairman (is_cso_admin or is_cso_president) only.
    Org boards    → any active org member.
    Returns True if the user can create at least one type of board.
    """
    if user.is_cso_admin or user.is_cso_president:
        return True
    from memberships.models import Membership
    return Membership.objects.filter(user=user, status='active', organization__is_active=True).exists()


def _can_delete_post(user, post):
    """Post author or board manager can delete a post."""
    return post.author == user or _is_board_manager(user, post.board)


def _can_edit_post(user, post):
    """Only the post author can edit their own post."""
    return post.author == user


def _can_edit_reply(user, reply):
    """Only the reply author can edit their own reply. Board managers can delete."""
    return reply.author == user or _is_board_manager(user, reply.post.board)


def _get_next_position(board):
    """Return max position + 1 for posts on the board."""
    result = Post.objects.filter(board=board).aggregate(Max('position'))['position__max']
    return (result or 0) + 1


def _validate_attachment(file=None, url=None):
    """Validate MIME type, size, and URL format. Returns (is_valid, error_msg)."""
    from django.core.validators import URLValidator
    from django.core.exceptions import ValidationError as DjangoValidationError

    if url is not None:
        validator = URLValidator()
        try:
            validator(url)
        except DjangoValidationError:
            return False, 'Invalid URL.'
        return True, ''

    if file is not None:
        if file.size > PostAttachment.MAX_FILE_SIZE:
            max_mb = PostAttachment.MAX_FILE_SIZE / (1024 * 1024)
            return False, f'File too large. Maximum size is {int(max_mb)} MB.'
        mime_type, _ = mimetypes.guess_type(file.name)
        if mime_type not in PostAttachment.ALLOWED_MIME_TYPES:
            return False, f'File type not allowed: {mime_type}. Allowed types: images, videos (mp4, webm, mov), and documents.'
        return True, ''

    return False, 'No file or URL provided.'


def _get_user_boards(user, status='active'):
    from memberships.models import Membership
    from django.db.models import Q
    user_org_ids = Membership.objects.filter(
        user=user, status='active', organization__is_active=True,
    ).values_list('organization_id', flat=True)

    # Base query: system boards + org boards the user is a member of
    q = Q(scope='system') | Q(scope='org', organization_id__in=user_org_ids)

    # Managers (CSO admin/president or board creator) can also see boards
    # for orgs they don't belong to
    if user.is_cso_admin or user.is_cso_president:
        q |= Q(scope='org')  # see all org boards
    else:
        # Board creator can always see their own boards
        q |= Q(created_by=user)

    return Board.objects.filter(q, status=status).distinct().select_related('organization', 'created_by')


# ─── Board list ───────────────────────────────────────────────────────────────

@login_required
def padlet_list_view(request):
    from django.db.models import Count
    boards = _get_user_boards(request.user, status='active').annotate(
        post_count=Count('posts')
    ).order_by('-post_count', '-created_at')
    system_boards = [b for b in boards if b.scope == 'system']
    org_boards = [b for b in boards if b.scope == 'org']

    # Get CSO org for system board branding
    from organizations.models import Organization
    cso_org = Organization.objects.filter(is_cso=True).first()

    return render(request, 'padlet/list.html', {
        'system_boards': system_boards,
        'org_boards': org_boards,
        'can_create': _can_create_board(request.user),
        'is_cso_admin': request.user.is_cso_admin or request.user.is_cso_president,
        'cso_org': cso_org,
    })


# ─── Board detail ─────────────────────────────────────────────────────────────

@login_required
def padlet_board_view(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    if not _can_see_board(request.user, board):
        messages.error(request, 'You do not have access to this board.')
        return redirect('padlet:padlet_list')

    can_post = board.status == 'active' and _can_post_on_board(request.user, board)
    is_manager = _is_board_manager(request.user, board)

    posts = board.posts.select_related('author').prefetch_related(
        'reactions', 'attachments', 'replies__author'
    ).order_by('-is_pinned', '-created_at')

    # User reactions map: post_id -> emoji
    user_reactions = {}
    for r in PostReaction.objects.filter(post__board=board, user=request.user):
        user_reactions[r.post_id] = r.emoji

    # One note per student — check if user already posted
    user_already_posted = board.posts.filter(author=request.user).exists()

    # Get CSO org for system board branding
    from organizations.models import Organization
    cso_org = Organization.objects.filter(is_cso=True).first() if board.scope == 'system' else None

    return render(request, 'padlet/board.html', {
        'board': board,
        'posts': posts,
        'can_post': can_post and (board.allow_multiple_posts or is_manager or not user_already_posted),
        'is_manager': is_manager,
        'user_reactions': user_reactions,
        'color_choices': Post.COLOR_CHOICES,
        'reaction_choices': PostReaction.EMOJI_CHOICES,
        'cso_org': cso_org,
        'user_already_posted': user_already_posted,
    })


# ─── Add post (HTMX) ──────────────────────────────────────────────────────────

@login_required
@require_POST
def padlet_add_post_view(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    if board.status != 'active':
        return HttpResponse('Board is archived.', status=403)
    if not _can_post_on_board(request.user, board):
        return HttpResponse('Not allowed.', status=403)

    content = request.POST.get('content', '').strip()
    color = request.POST.get('color', 'yellow')
    is_anonymous = request.POST.get('is_anonymous') == 'on'
    title = request.POST.get('title', '').strip() or None
    link_url = request.POST.get('link_url', '').strip() or None

    if not content:
        return HttpResponse('Content required.', status=400)

    # Enforce one note per student per board (unless multiple posts allowed or user is a manager)
    if not board.allow_multiple_posts and not _is_board_manager(request.user, board) and board.posts.filter(author=request.user).exists():
        return HttpResponse('You have already posted a note on this board.', status=403)

    valid_colors = [c[0] for c in Post.COLOR_CHOICES]
    if color not in valid_colors:
        color = 'yellow'

    # Validate attachment BEFORE creating the post to avoid orphaned records
    attachment_file = request.FILES.get('attachment')
    if attachment_file:
        is_valid, error = _validate_attachment(file=attachment_file)
        if not is_valid:
            return JsonResponse({'error': error}, status=400)

    position = _get_next_position(board)

    post = Post.objects.create(
        board=board,
        author=request.user,
        is_anonymous=is_anonymous,
        title=title,
        content=content,
        link_url=link_url,
        color=color,
        position=position,
    )

    # Attach the validated file
    if attachment_file:
        mime_type, _ = mimetypes.guess_type(attachment_file.name)
        if mime_type and mime_type.startswith('video/'):
            att_type = 'video'
        elif mime_type and mime_type.startswith('image/'):
            att_type = 'image'
        else:
            att_type = 'file'
        PostAttachment.objects.create(
            post=post,
            attachment_type=att_type,
            file=attachment_file,
            original_filename=attachment_file.name,
        )

    # Notify board creator when someone posts (skip if creator posts on their own board)
    if board.created_by and board.created_by != request.user:
        from announcements.utils import send_notification
        from django.urls import reverse
        poster_name = 'Someone' if is_anonymous else (request.user.get_full_name() or 'Someone')
        send_notification(
            title=f'New note on "{board.title}"',
            message=f'{poster_name} added a note to your board.',
            recipients=[board.created_by],
            sender=None if is_anonymous else request.user,
            link_url=reverse('padlet:padlet_board', kwargs={'board_id': board.id}),
            notification_type='noteboard:new_post',
        )

    user_reactions = {}
    is_manager = _is_board_manager(request.user, board)

    return render(request, 'padlet/_post_card.html', {
        'post': post,
        'board': board,
        'user_reactions': user_reactions,
        'is_manager': is_manager,
        'reaction_choices': PostReaction.EMOJI_CHOICES,
        'request': request,
    })


# ─── Edit post (HTMX) ─────────────────────────────────────────────────────────

@login_required
@require_POST
def padlet_edit_post_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    board = post.board

    if board.status != 'active':
        return HttpResponse('Board is archived.', status=403)
    if not _can_edit_post(request.user, post):
        return HttpResponse('Not allowed.', status=403)

    content = request.POST.get('content', '').strip()
    color = request.POST.get('color', '').strip()
    title = request.POST.get('title', '').strip() or None
    link_url = request.POST.get('link_url', '').strip() or None

    if not content:
        return HttpResponse('Content required.', status=400)

    post.title = title
    post.content = content
    post.link_url = link_url
    valid_colors = [c[0] for c in Post.COLOR_CHOICES]
    if color in valid_colors:
        post.color = color
    post.save()

    # Handle new attachment if uploaded
    attachment_file = request.FILES.get('attachment')
    if attachment_file:
        is_valid, error = _validate_attachment(file=attachment_file)
        if not is_valid:
            return JsonResponse({'error': error}, status=400)
        mime_type, _ = mimetypes.guess_type(attachment_file.name)
        if mime_type and mime_type.startswith('video/'):
            att_type = 'video'
        elif mime_type and mime_type.startswith('image/'):
            att_type = 'image'
        else:
            att_type = 'file'
        PostAttachment.objects.create(
            post=post,
            attachment_type=att_type,
            file=attachment_file,
            original_filename=attachment_file.name,
        )

    user_reactions = {}
    for r in PostReaction.objects.filter(post=post, user=request.user):
        user_reactions[r.post_id] = r.emoji

    return render(request, 'padlet/_post_card.html', {
        'post': post,
        'board': board,
        'user_reactions': user_reactions,
        'is_manager': _is_board_manager(request.user, board),
        'reaction_choices': PostReaction.EMOJI_CHOICES,
        'request': request,
    })


# ─── Delete post ──────────────────────────────────────────────────────────────

@login_required
@require_POST
def padlet_delete_post_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    board = post.board

    if not _can_delete_post(request.user, post):
        return HttpResponse('Not allowed.', status=403)

    # Delete attached files from disk
    for att in post.attachments.all():
        if att.file:
            att.file.delete(save=False)

    post.delete()
    return HttpResponse('')


# ─── Pin/Unpin post ───────────────────────────────────────────────────────────

@login_required
@require_POST
def padlet_pin_post_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    board = post.board

    if not _is_board_manager(request.user, board):
        return HttpResponse('Not allowed.', status=403)

    post.is_pinned = not post.is_pinned
    post.save(update_fields=['is_pinned'])

    user_reactions = {}
    for r in PostReaction.objects.filter(post=post, user=request.user):
        user_reactions[r.post_id] = r.emoji

    return render(request, 'padlet/_post_card.html', {
        'post': post,
        'board': board,
        'user_reactions': user_reactions,
        'is_manager': True,
        'reaction_choices': PostReaction.EMOJI_CHOICES,
        'request': request,
    })


# ─── React (HTMX) ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def padlet_react_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    board = post.board

    if not _can_see_board(request.user, board):
        return HttpResponse('Not allowed.', status=403)

    emoji = request.POST.get('emoji', '')
    valid_emojis = [e[0] for e in PostReaction.EMOJI_CHOICES]

    existing = PostReaction.objects.filter(post=post, user=request.user).first()
    if existing:
        if existing.emoji == emoji:
            existing.delete()
            user_reaction = None
        else:
            existing.emoji = emoji
            existing.save()
            user_reaction = emoji
            # Notify post author of the reaction (skip if reacting to own post)
            if post.author and post.author != request.user and not post.is_anonymous:
                from announcements.utils import send_notification
                from django.urls import reverse
                reactor_name = request.user.get_full_name() or 'Someone'
                emoji_map = {'heart': '❤️', 'laugh': '😂', 'wow': '😮', 'sad': '😢', 'thumbsup': '👍', 'thumbsdown': '👎'}
                emoji_display = emoji_map.get(emoji, emoji)
                send_notification(
                    title=f'{reactor_name} reacted to your note',
                    message=f'{emoji_display} your note on "{post.board.title}".',
                    recipients=[post.author],
                    sender=request.user,
                    link_url=reverse('padlet:padlet_board', kwargs={'board_id': post.board.id}),
                    notification_type='noteboard:reaction',
                )
    else:
        if emoji in valid_emojis:
            PostReaction.objects.create(post=post, user=request.user, emoji=emoji)
            user_reaction = emoji
            # Notify post author of the reaction (skip if reacting to own post)
            if post.author and post.author != request.user and not post.is_anonymous:
                from announcements.utils import send_notification
                from django.urls import reverse
                reactor_name = request.user.get_full_name() or 'Someone'
                emoji_map = {'heart': '❤️', 'laugh': '😂', 'wow': '😮', 'sad': '😢', 'thumbsup': '👍', 'thumbsdown': '👎'}
                emoji_display = emoji_map.get(emoji, emoji)
                send_notification(
                    title=f'{reactor_name} reacted to your note',
                    message=f'{emoji_display} your note on "{post.board.title}".',
                    recipients=[post.author],
                    sender=request.user,
                    link_url=reverse('padlet:padlet_board', kwargs={'board_id': post.board.id}),
                    notification_type='noteboard:reaction',
                )
        else:
            user_reaction = None

    # Return updated reaction bar as HTML partial
    counts = {}
    for r in post.reactions.all():
        counts[r.emoji] = counts.get(r.emoji, 0) + 1

    return render(request, 'padlet/_reaction_bar.html', {
        'post': post,
        'reaction_choices': PostReaction.EMOJI_CHOICES,
        'reaction_counts': counts,
        'user_reaction': user_reaction,
    })


# ─── Column management (removed — columns replaced by masonry layout) ────────


@login_required
def padlet_get_replies_view(request, post_id):
    """Return replies for a post as JSON for the note modal."""
    post = get_object_or_404(Post, id=post_id)
    if not _can_see_board(request.user, post.board):
        return HttpResponse('Not allowed.', status=403)

    replies = []
    for r in post.replies.select_related('author').order_by('created_at'):
        if r.is_anonymous or not r.author:
            author = 'Anonymous'
            pic = None
        else:
            author = r.author.get_full_name() or r.author.username
            pic = r.author.profile_picture.url if r.author.profile_picture else None
        replies.append({
            'id': r.id,
            'parent_id': r.parent_reply_id,
            'author': author,
            'content': r.content,
            'date': r.created_at.strftime('%b %d, %Y'),
            'pic': pic,
            'can_delete': _can_edit_reply(request.user, r),
        })
    return JsonResponse({'replies': replies})


@login_required
def padlet_post_detail_view(request, post_id):
    """Render the note detail modal content."""
    post = get_object_or_404(Post, id=post_id)
    if not _can_see_board(request.user, post.board):
        return HttpResponse('Not allowed.', status=403)

    user_reaction = PostReaction.objects.filter(post=post, user=request.user).first()
    reaction_counts = {}
    for r in post.reactions.all():
        reaction_counts[r.emoji] = reaction_counts.get(r.emoji, 0) + 1

    replies = post.replies.select_related('author').order_by('created_at')
    is_manager = _is_board_manager(request.user, post.board)

    return render(request, 'padlet/_post_detail.html', {
        'post': post,
        'board': post.board,
        'user_reaction': user_reaction.emoji if user_reaction else None,
        'reaction_counts': reaction_counts,
        'reaction_choices': PostReaction.EMOJI_CHOICES,
        'color_choices': Post.COLOR_CHOICES,
        'replies': replies,
        'is_manager': is_manager,
        'can_edit': _can_edit_post(request.user, post),
        'can_delete': _can_delete_post(request.user, post),
        'current_user': request.user,
    })


@login_required
@require_POST
def padlet_add_reply_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    board = post.board

    if board.status != 'active':
        return HttpResponse('Board is archived.', status=403)
    if not _can_see_board(request.user, board):
        return HttpResponse('Not allowed.', status=403)

    content = request.POST.get('content', '').strip()
    is_anonymous = request.POST.get('is_anonymous') == 'on'

    if not content:
        return HttpResponse('Content required.', status=400)

    parent_reply_id = request.POST.get('parent_reply_id')
    parent_reply = None
    if parent_reply_id:
        try:
            parent_reply = Reply.objects.get(id=int(parent_reply_id), post=post)
        except (Reply.DoesNotExist, ValueError):
            pass

    reply = Reply.objects.create(
        post=post,
        author=request.user,
        is_anonymous=is_anonymous,
        content=content,
        parent_reply=parent_reply,
    )

    # Notify the post author when someone replies (skip if anonymous or self-reply)
    if not is_anonymous and post.author and post.author != request.user:
        from announcements.utils import send_notification
        from django.urls import reverse
        author_name = request.user.get_full_name() or 'Someone'
        send_notification(
            title=f'{author_name} replied to your note',
            message=f'"{content[:80]}{"…" if len(content) > 80 else ""}"',
            recipients=[post.author],
            sender=request.user,
            link_url=reverse('padlet:padlet_board', kwargs={'board_id': post.board.id}),
            notification_type='noteboard:reply',
        )

    return render(request, 'padlet/_reply_partial.html', {
        'reply': reply,
        'board': board,
        'is_manager': _is_board_manager(request.user, board),
        'current_user': request.user,
    })


@login_required
@require_POST
def padlet_edit_reply_view(request, reply_id):
    reply = get_object_or_404(Reply, id=reply_id)
    board = reply.post.board

    if not _can_edit_reply(request.user, reply):
        return HttpResponse('Not allowed.', status=403)

    content = request.POST.get('content', '').strip()
    if not content:
        return HttpResponse('Content required.', status=400)

    reply.content = content
    reply.save()

    return render(request, 'padlet/_reply_partial.html', {
        'reply': reply,
        'board': board,
        'is_manager': _is_board_manager(request.user, board),
        'current_user': request.user,
    })


@login_required
@require_POST
def padlet_delete_reply_view(request, reply_id):
    reply = get_object_or_404(Reply, id=reply_id)
    if not _can_edit_reply(request.user, reply):
        return HttpResponse('Not allowed.', status=403)

    reply.delete()
    return HttpResponse('')
# ─── Attachment views ─────────────────────────────────────────────────────────

@login_required
@require_POST
def padlet_add_attachment_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    board = post.board

    if board.status != 'active':
        return HttpResponse('Board is archived.', status=403)
    if not _can_edit_post(request.user, post):
        return HttpResponse('Not allowed.', status=403)

    if post.attachments.count() >= 5:
        return HttpResponse('Maximum 5 attachments per post.', status=400)

    attachment_type = request.POST.get('attachment_type', '')
    url_value = request.POST.get('url', '').strip()
    uploaded_file = request.FILES.get('file')

    if attachment_type == 'url':
        is_valid, error = _validate_attachment(url=url_value)
        if not is_valid:
            return HttpResponse(error, status=400)
        attachment = PostAttachment.objects.create(
            post=post,
            attachment_type='url',
            url=url_value,
        )
    elif uploaded_file:
        is_valid, error = _validate_attachment(file=uploaded_file)
        if not is_valid:
            return HttpResponse(error, status=400)

        mime_type, _ = mimetypes.guess_type(uploaded_file.name)
        if mime_type and mime_type.startswith('video/'):
            att_type = 'video'
        elif mime_type and mime_type.startswith('image/'):
            att_type = 'image'
        else:
            att_type = 'file'

        attachment = PostAttachment.objects.create(
            post=post,
            attachment_type=att_type,
            file=uploaded_file,
            original_filename=uploaded_file.name,
        )
    else:
        return HttpResponse('No file or URL provided.', status=400)

    return render(request, 'padlet/_attachment_partial.html', {
        'attachment': attachment,
        'is_manager': _is_board_manager(request.user, board),
        'current_user': request.user,
        'post': post,
    })


@login_required
@require_POST
def padlet_delete_attachment_view(request, attachment_id):
    attachment = get_object_or_404(PostAttachment, id=attachment_id)
    post = attachment.post
    board = post.board

    if not _can_edit_post(request.user, post):
        return HttpResponse('Not allowed.', status=403)

    if attachment.file:
        attachment.file.delete(save=False)
    attachment.delete()
    return HttpResponse('')


# ─── Archive list ─────────────────────────────────────────────────────────────

@login_required
def padlet_archive_view(request):
    boards = _get_user_boards(request.user, status='archived')
    return render(request, 'padlet/archive.html', {'boards': boards})


# ─── Create board ─────────────────────────────────────────────────────────────

@login_required
def padlet_create_board_view(request):
    from memberships.models import Membership
    from organizations.models import Organization

    is_cso_admin = request.user.is_cso_admin or request.user.is_cso_president

    # Orgs the user is a member of (for org-scoped boards) — exclude lapsed/inactive orgs
    user_memberships = Membership.objects.filter(
        user=request.user, status='active', organization__is_active=True,
    ).select_related('organization')
    member_orgs = [
        m.organization for m in user_memberships
        if m.organization.status not in ('lapsed', 'rejected', 'pending', 'under_review')
    ]

    # CSO admins/presidents can create boards for any active non-lapsed org
    if is_cso_admin:
        available_orgs = list(
            Organization.objects.filter(is_active=True)
            .exclude(status__in=['lapsed', 'rejected', 'pending', 'under_review'])
            .order_by('name')
        )
    else:
        available_orgs = member_orgs

    # Non-CSO-admin with no org memberships can't create any board
    if not is_cso_admin and not member_orgs:
        messages.error(request, 'You must be a member of an organization to create a board.')
        return redirect('padlet:padlet_list')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        scope = request.POST.get('scope', 'system')
        org_id = request.POST.get('organization')

        form_data = {'title': title, 'description': description, 'scope': scope, 'org_id': org_id}

        if not title:
            messages.error(request, 'Title is required.')
            return render(request, 'padlet/create.html', {'member_orgs': available_orgs, 'is_cso_admin': is_cso_admin, 'form_data': form_data})

        # Enforce scope permissions
        if scope == 'system' and not is_cso_admin:
            messages.error(request, 'Only CSO admins can create system-wide boards.')
            return render(request, 'padlet/create.html', {'member_orgs': available_orgs, 'is_cso_admin': is_cso_admin, 'form_data': form_data})

        organization = None
        if scope == 'org':
            if not org_id:
                messages.error(request, 'Please select an organization.')
                return render(request, 'padlet/create.html', {'member_orgs': available_orgs, 'is_cso_admin': is_cso_admin, 'form_data': form_data})
            organization = get_object_or_404(Organization, id=org_id)
            # Lapsed orgs cannot have new boards created
            if organization.status == 'lapsed':
                messages.error(request, 'Cannot create a board for a lapsed organization.')
                return render(request, 'padlet/create.html', {'member_orgs': available_orgs, 'is_cso_admin': is_cso_admin, 'form_data': form_data})
            # Must be a member of that org (CSO admins/presidents are exempt)
            if not is_cso_admin and not Membership.objects.filter(user=request.user, organization=organization, status='active', organization__is_active=True).exists():
                messages.error(request, 'You are not a member of that organization.')
                return render(request, 'padlet/create.html', {'member_orgs': available_orgs, 'is_cso_admin': is_cso_admin, 'form_data': form_data})

        board = Board.objects.create(
            title=title,
            description=description or None,
            scope=scope,
            organization=organization,
            created_by=request.user,
            board_color=request.POST.get('board_color', '').strip() or None,
            allow_multiple_posts=request.POST.get('allow_multiple_posts') == 'on',
            is_public=request.POST.get('is_public') == 'on' if scope == 'org' else False,
        )
        # Handle cover image — prefer cropped data URL, fall back to raw file upload
        import base64, uuid
        from django.core.files.base import ContentFile
        cover_data = request.POST.get('cover_image_data', '').strip()
        if cover_data and cover_data.startswith('data:image'):
            try:
                fmt, imgstr = cover_data.split(';base64,')
                ext = fmt.split('/')[-1]
                img_bytes = base64.b64decode(imgstr)
                fname = f"board_{uuid.uuid4().hex[:12]}.{ext}"
                board.cover_image.save(fname, ContentFile(img_bytes), save=True)
            except Exception:
                pass
        else:
            cover_image = request.FILES.get('cover_image')
            if cover_image:
                board.cover_image = cover_image
                board.save(update_fields=['cover_image'])
        messages.success(request, f'Board "{board.title}" created.')
        return redirect('padlet:padlet_board', board_id=board.id)

    return render(request, 'padlet/create.html', {'member_orgs': available_orgs, 'is_cso_admin': is_cso_admin})


# ─── Edit board ───────────────────────────────────────────────────────────────

@login_required
def padlet_edit_board_view(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    if not _is_board_manager(request.user, board):
        messages.error(request, 'You do not have permission to edit this board.')
        return redirect('padlet:padlet_board', board_id=board.id)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        if not title:
            messages.error(request, 'Title is required.')
        else:
            board.title = title
            board.description = description or None
            board.board_color = request.POST.get('board_color', '').strip() or None
            board.allow_multiple_posts = request.POST.get('allow_multiple_posts') == 'on'
            # Only update is_public for org boards
            if board.scope == 'org':
                board.is_public = request.POST.get('is_public') == 'on'
            board.save()
            # Handle cover image — prefer cropped data URL, fall back to raw file upload
            import base64, uuid
            from django.core.files.base import ContentFile
            cover_data = request.POST.get('cover_image_data', '').strip()
            if cover_data and cover_data.startswith('data:image'):
                try:
                    fmt, imgstr = cover_data.split(';base64,')
                    ext = fmt.split('/')[-1]
                    img_bytes = base64.b64decode(imgstr)
                    fname = f"board_{uuid.uuid4().hex[:12]}.{ext}"
                    if board.cover_image:
                        board.cover_image.delete(save=False)
                    board.cover_image.save(fname, ContentFile(img_bytes), save=True)
                except Exception:
                    pass
            else:
                cover_image = request.FILES.get('cover_image')
                if cover_image:
                    if board.cover_image:
                        board.cover_image.delete(save=False)
                    board.cover_image = cover_image
                    board.save(update_fields=['cover_image'])
                elif request.POST.get('remove_cover_image'):
                    if board.cover_image:
                        board.cover_image.delete(save=False)
                    board.cover_image = None
                    board.save(update_fields=['cover_image'])
            messages.success(request, 'Board updated.')
            return redirect('padlet:padlet_board', board_id=board.id)

    return render(request, 'padlet/edit.html', {'board': board})


# ─── Archive board ────────────────────────────────────────────────────────────

@login_required
@require_POST
def padlet_archive_board_view(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    if not _is_board_manager(request.user, board):
        messages.error(request, 'You do not have permission to archive this board.')
        return redirect('padlet:padlet_board', board_id=board.id)

    board.status = 'active' if board.status == 'archived' else 'archived'
    board.save()
    action = 'unarchived' if board.status == 'active' else 'archived'
    messages.success(request, f'Board "{board.title}" {action}.')
    return redirect('padlet:padlet_list')


# ─── Delete board ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def padlet_delete_board_view(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    if not _is_board_manager(request.user, board):
        messages.error(request, 'You do not have permission to delete this board.')
        return redirect('padlet:padlet_board', board_id=board.id)

    # Delete all attachment files from disk
    for post in board.posts.all():
        for att in post.attachments.all():
            if att.file:
                att.file.delete(save=False)

    title = board.title
    board.delete()
    messages.success(request, f'Board "{title}" deleted.')
    return redirect('padlet:padlet_list')
