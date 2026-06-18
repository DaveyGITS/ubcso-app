from django.db import models
from accounts.models import User
from organizations.models import Organization


class Board(models.Model):
    SCOPE_CHOICES = [
        ('system', 'System-wide (All Students)'),
        ('org', 'Organization Members Only'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('archived', 'Archived'),
    ]

    # Org board color themes — tinted/shaded palettes
    ORG_COLOR_CHOICES = [
        # Blues
        ('blue-slate',   'Slate Blue'),
        ('blue-ocean',   'Ocean Blue'),
        ('blue-denim',   'Denim'),
        ('blue-sky',     'Sky Blue'),
        # Greens
        ('green-sage',   'Sage Green'),
        ('green-forest', 'Forest Green'),
        ('green-mint',   'Mint'),
        ('green-olive',  'Olive'),
        # Purples
        ('purple-grape', 'Grape'),
        ('purple-lavender', 'Lavender'),
        ('purple-plum',  'Plum'),
        # Reds / Pinks
        ('red-rose',     'Rose'),
        ('red-crimson',  'Crimson'),
        ('pink-blush',   'Blush'),
        # Warm neutrals
        ('warm-sand',    'Sand'),
        ('warm-terracotta', 'Terracotta'),
        ('warm-caramel', 'Caramel'),
        # Dark
        ('dark-charcoal','Charcoal'),
        ('dark-midnight','Midnight'),
    ]

    title = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    cover_image = models.ImageField(upload_to='padlet_covers/', blank=True, null=True)
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default='system')
    board_color = models.CharField(max_length=30, blank=True, null=True,
                                   help_text='Color theme for org boards')
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE,
        null=True, blank=True, related_name='boards'
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_boards')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    allow_multiple_posts = models.BooleanField(default=False, help_text='Allow members to post more than once on this board')
    is_public = models.BooleanField(default=False, help_text='Make this org board visible to all students (only applies to org boards)')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class BoardColumn(models.Model):
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='columns')
    name = models.CharField(max_length=100)
    position = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return f"{self.name} ({self.board})"


class Post(models.Model):
    COLOR_CHOICES = [
        ('yellow', 'Yellow'),
        ('blue', 'Blue'),
        ('green', 'Green'),
        ('pink', 'Pink'),
        ('purple', 'Purple'),
        ('white', 'White'),
    ]

    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='posts')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='padlet_posts')
    is_anonymous = models.BooleanField(default=False)
    title = models.CharField(max_length=200, blank=True, null=True)
    content = models.TextField()
    link_url = models.URLField(max_length=2000, blank=True, null=True)
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, default='yellow')
    is_pinned = models.BooleanField(default=False)
    position = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return f"Post on {self.board} by {self.author}"

    def reaction_counts(self):
        counts = {}
        for r in self.reactions.all():
            counts[r.emoji] = counts.get(r.emoji, 0) + 1
        return counts


class PostReaction(models.Model):
    EMOJI_CHOICES = [
        ('thumbsup',   '👍'),
        ('thumbsdown', '👎'),
    ]

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='padlet_reactions')
    emoji = models.CharField(max_length=15, choices=EMOJI_CHOICES)

    class Meta:
        unique_together = ('post', 'user')

    def __str__(self):
        return f"{self.user} reacted {self.emoji} on post {self.post_id}"


class PostAttachment(models.Model):
    TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('file', 'File'),
        ('url', 'URL Link'),
    ]
    ALLOWED_MIME_TYPES = [
        'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/avif',
        'video/mp4', 'video/webm', 'video/ogg', 'video/quicktime', 'video/x-msvideo', 'video/x-matroska',
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'text/plain',
    ]
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB (increased for videos)

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='attachments')
    attachment_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    file = models.FileField(upload_to='padlet_attachments/', null=True, blank=True)
    url = models.URLField(max_length=2000, null=True, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.attachment_type} attachment on post {self.post_id}"


class Reply(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='replies')
    parent_reply = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True, related_name='child_replies'
    )
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='padlet_replies')
    is_anonymous = models.BooleanField(default=False)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Reply on post {self.post_id} by {self.author}"
