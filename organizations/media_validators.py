import re
from django.core.exceptions import ValidationError

ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
ALLOWED_VIDEO_TYPES = {'video/mp4', 'video/quicktime', 'video/webm'}
MAX_PHOTO_SIZE = 10 * 1024 * 1024   # 10 MB
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500 MB

HEX_COLOR_RE = re.compile(r'^#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})$')


def validate_photo(file):
    """Raises ValidationError if file is not an accepted image type or exceeds 10 MB."""
    content_type = getattr(file, 'content_type', None)
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError(
            f'"{file.name}" is not an accepted image format. Allowed: JPEG, PNG, WebP.'
        )
    if file.size > MAX_PHOTO_SIZE:
        size_mb = file.size / (1024 * 1024)
        raise ValidationError(
            f'"{file.name}" is {size_mb:.1f} MB — exceeds the 10 MB limit.'
        )


def validate_video(file):
    """Raises ValidationError if file is not an accepted video type or exceeds 500 MB."""
    content_type = getattr(file, 'content_type', None)
    if content_type not in ALLOWED_VIDEO_TYPES:
        raise ValidationError(
            f'"{file.name}" is not an accepted video format. Allowed: MP4, MOV, WebM.'
        )
    if file.size > MAX_VIDEO_SIZE:
        size_mb = file.size / (1024 * 1024)
        raise ValidationError(
            f'"{file.name}" is {size_mb:.0f} MB — exceeds the 500 MB limit.'
        )


def validate_hex_color(value):
    """Raises ValidationError if value is not a valid hex color (#RRGGBB or #RGB)."""
    if value and not HEX_COLOR_RE.match(value):
        raise ValidationError(
            f'"{value}" is not a valid hex color. Use format #RRGGBB or #RGB.'
        )
