# api/cms/models/media.py
"""
Media models: MediaFolder, MediaFile, MediaVariant, MediaTag, MediaUsage
Full production-ready with file handling, CDN support, and usage tracking.
"""
import uuid
import os
import mimetypes
import logging
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from imagekit.models import ProcessedImageField
from imagekit.processors import SmartResize, ResizeToFill
from core.models import TimeStampedModel

logger = logging.getLogger(__name__)


def default_list():
    return []


def default_dict():
    return {}


# ─────────────────────────────────────────────
# MediaFolder
# ─────────────────────────────────────────────

class MediaFolder(TimeStampedModel):
    """Hierarchical folder structure for media files."""
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Folder Name"), max_length=200)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='subfolders',
        verbose_name=_("Parent Folder")
    )
    path = models.CharField(
        _("Path"), max_length=1000, blank=True,
        help_text=_("Auto-generated full path")
    )
    description = models.TextField(_("Description"), blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    is_public = models.BooleanField(_("Public"), default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_media_folders',
        verbose_name=_("Created By")
    )
    # Stats
    file_count = models.PositiveIntegerField(_("File Count"), default=0)
    total_size = models.BigIntegerField(_("Total Size (bytes)"), default=0)

    class Meta:
        app_label = "cms"
        verbose_name = _("Media Folder")
        verbose_name_plural = _("Media Folders")
        ordering = ['path', 'name']
        unique_together = [['parent', 'name']]
        indexes = [
            models.Index(fields=['parent', 'is_active']),
            models.Index(fields=['path']),
            models.Index(fields=['uuid']),
            models.Index(fields=['created_by']),
        ]

    def __str__(self):
        return self.path or self.name

    def clean(self):
        if self.parent and self.parent == self:
            raise ValidationError(_("A folder cannot be its own parent."))

    def save(self, *args, **kwargs):
        # Auto-generate path
        if self.parent:
            self.path = f"{self.parent.path}/{self.name}".lstrip('/')
        else:
            self.path = self.name
        super().save(*args, **kwargs)
        cache.delete(f'media_folder_{self.id}')
        cache.delete('media_folder_tree')

    def get_full_path(self):
        """Get full folder path."""
        parts = []
        current = self
        while current:
            parts.insert(0, current.name)
            current = current.parent
        return '/'.join(parts)

    def update_stats(self):
        """Update file count and total size."""
        files = self.files.filter(is_active=True)
        self.file_count = files.count()
        self.total_size = sum(f.size_bytes or 0 for f in files)
        MediaFolder.objects.filter(id=self.id).update(
            file_count=self.file_count,
            total_size=self.total_size
        )

    def get_all_files(self, include_subfolders=True):
        """Get all files, optionally including subfolders."""
        if not include_subfolders:
            return self.files.filter(is_active=True)
        # Recursive: collect all files from subfolders
        ids = self._get_subfolder_ids()
        return MediaFile.objects.filter(
            folder_id__in=ids, is_active=True
        )

    def _get_subfolder_ids(self):
        ids = [self.id]
        for subfolder in self.subfolders.filter(is_active=True):
            ids.extend(subfolder._get_subfolder_ids())
        return ids

    @property
    def breadcrumbs(self):
        breadcrumbs = []
        current = self
        while current:
            breadcrumbs.insert(0, {'id': current.id, 'name': current.name, 'path': current.path})
            current = current.parent
        return breadcrumbs


# ─────────────────────────────────────────────
# MediaTag
# ─────────────────────────────────────────────

class MediaTag(TimeStampedModel):
    """Tags for media files."""
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Name"), max_length=80, unique=True)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Media Tag")
        verbose_name_plural = _("Media Tags")
        ordering = ['name']
        indexes = [
            models.Index(fields=['name', 'is_active']),
        ]

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
# MediaFile
# ─────────────────────────────────────────────

ALLOWED_IMAGE_TYPES = [
    'image/jpeg', 'image/png', 'image/webp', 'image/gif',
    'image/svg+xml', 'image/bmp', 'image/tiff',
]
ALLOWED_VIDEO_TYPES = [
    'video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo',
    'video/webm', 'video/ogg',
]
ALLOWED_AUDIO_TYPES = [
    'audio/mpeg', 'audio/ogg', 'audio/wav', 'audio/webm', 'audio/aac',
]
ALLOWED_DOC_TYPES = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain', 'text/csv',
    'application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed',
]


class MediaFile(TimeStampedModel):
    """Central media file management with CDN support and variant tracking."""

    FILE_TYPE_CHOICES = [
        ('image', _('Image')),
        ('video', _('Video')),
        ('audio', _('Audio')),
        ('document', _('Document')),
        ('archive', _('Archive')),
        ('other', _('Other')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # File
    file = models.FileField(
        _("File"),
        upload_to='media/%Y/%m/',
        validators=[FileExtensionValidator(
            allowed_extensions=[
                'jpg', 'jpeg', 'png', 'webp', 'gif', 'svg', 'bmp', 'tiff',
                'mp4', 'mpeg', 'mov', 'avi', 'webm', 'ogg',
                'mp3', 'wav', 'aac',
                'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
                'txt', 'csv', 'zip', 'rar', '7z',
            ]
        )]
    )
    filename = models.CharField(_("Original Filename"), max_length=500)
    file_type = models.CharField(
        _("File Type"), max_length=20,
        choices=FILE_TYPE_CHOICES, default='other',
        db_index=True
    )
    mime_type = models.CharField(_("MIME Type"), max_length=200, blank=True)
    size_bytes = models.BigIntegerField(_("Size (bytes)"), default=0)

    # Organization
    folder = models.ForeignKey(
        MediaFolder, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='files',
        verbose_name=_("Folder")
    )
    tags = models.ManyToManyField(
        MediaTag, blank=True,
        related_name='files',
        verbose_name=_("Tags")
    )

    # Metadata
    title = models.CharField(_("Title"), max_length=300, blank=True)
    alt_text = models.CharField(_("Alt Text"), max_length=500, blank=True)
    description = models.TextField(_("Description"), blank=True)
    caption = models.TextField(_("Caption"), blank=True)

    # Image-specific
    width = models.PositiveIntegerField(_("Width (px)"), null=True, blank=True)
    height = models.PositiveIntegerField(_("Height (px)"), null=True, blank=True)

    # CDN
    cdn_url = models.URLField(_("CDN URL"), blank=True)
    cdn_pushed_at = models.DateTimeField(_("CDN Pushed At"), null=True, blank=True)

    # Access
    is_active = models.BooleanField(_("Active"), default=True)
    is_public = models.BooleanField(_("Public"), default=True)

    # Ownership
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='uploaded_media',
        verbose_name=_("Uploaded By")
    )

    # Stats
    download_count = models.PositiveIntegerField(_("Download Count"), default=0)
    view_count = models.PositiveIntegerField(_("View Count"), default=0)
    usage_count = models.PositiveIntegerField(_("Usage Count"), default=0)

    class Meta:
        app_label = "cms"
        verbose_name = _("Media File")
        verbose_name_plural = _("Media Files")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['file_type', 'is_active']),
            models.Index(fields=['folder', 'file_type']),
            models.Index(fields=['uploaded_by', 'created_at']),
            models.Index(fields=['is_public', 'file_type']),
            models.Index(fields=['uuid', 'is_active']),
            models.Index(fields=['mime_type']),
        ]

    def __str__(self):
        return self.title or self.filename

    def clean(self):
        if self.file and self.size_bytes > 100 * 1024 * 1024:  # 100MB max
            raise ValidationError(_("File size cannot exceed 100MB."))

    def save(self, *args, **kwargs):
        if self.file:
            # Auto-detect filename, size, mime_type
            if not self.filename:
                self.filename = os.path.basename(self.file.name)
            self.size_bytes = self.file.size if hasattr(self.file, 'size') else 0
            mime_type, _ = mimetypes.guess_type(self.filename)
            if mime_type:
                self.mime_type = mime_type
                # Auto-detect file_type
                if mime_type in ALLOWED_IMAGE_TYPES:
                    self.file_type = 'image'
                elif mime_type in ALLOWED_VIDEO_TYPES:
                    self.file_type = 'video'
                elif mime_type in ALLOWED_AUDIO_TYPES:
                    self.file_type = 'audio'
                elif mime_type in ALLOWED_DOC_TYPES:
                    self.file_type = 'document'
                else:
                    self.file_type = 'other'
        super().save(*args, **kwargs)
        # Update folder stats
        if self.folder:
            self.folder.update_stats()

    def delete(self, *args, **kwargs):
        folder = self.folder
        super().delete(*args, **kwargs)
        if folder:
            folder.update_stats()

    def increment_download(self):
        MediaFile.objects.filter(id=self.id).update(download_count=F('download_count') + 1)
        self.refresh_from_db()

    def increment_view(self):
        MediaFile.objects.filter(id=self.id).update(view_count=F('view_count') + 1)
        self.refresh_from_db()

    def increment_usage(self):
        MediaFile.objects.filter(id=self.id).update(usage_count=F('usage_count') + 1)
        self.refresh_from_db()

    def decrement_usage(self):
        if self.usage_count > 0:
            MediaFile.objects.filter(id=self.id).update(usage_count=F('usage_count') - 1)
            self.refresh_from_db()

    @property
    def file_url(self):
        """Return CDN URL if available, else local file URL."""
        if self.cdn_url:
            return self.cdn_url
        return self.file.url if self.file else ''

    @property
    def size_human(self):
        """Human-readable file size."""
        size = self.size_bytes
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"

    @property
    def is_image(self):
        return self.file_type == 'image'

    @property
    def is_video(self):
        return self.file_type == 'video'

    @property
    def extension(self):
        return os.path.splitext(self.filename)[1].lower() if self.filename else ''

    def get_variant(self, variant_type):
        """Get a specific variant of this file."""
        try:
            return self.variants.get(variant_type=variant_type, is_active=True)
        except MediaVariant.DoesNotExist:
            return None

    def get_thumbnail_url(self):
        """Get thumbnail URL."""
        variant = self.get_variant('thumb')
        if variant:
            return variant.file_url
        return self.file_url

    def mark_cdn_pushed(self, cdn_url):
        """Mark file as pushed to CDN."""
        self.cdn_url = cdn_url
        self.cdn_pushed_at = timezone.now()
        MediaFile.objects.filter(id=self.id).update(
            cdn_url=cdn_url,
            cdn_pushed_at=self.cdn_pushed_at
        )


# ─────────────────────────────────────────────
# MediaVariant
# ─────────────────────────────────────────────

class MediaVariant(TimeStampedModel):
    """Image variants: thumbnail, medium, large, webp."""

    VARIANT_TYPES = [
        ('thumb', _('Thumbnail (150x150)')),
        ('medium', _('Medium (600x400)')),
        ('large', _('Large (1200x800)')),
        ('webp', _('WebP Optimized')),
        ('og', _('OG Image (1200x630)')),
        ('mobile', _('Mobile (480x320)')),
    ]

    VARIANT_DIMENSIONS = {
        'thumb': (150, 150),
        'medium': (600, 400),
        'large': (1200, 800),
        'webp': (1200, 800),
        'og': (1200, 630),
        'mobile': (480, 320),
    }

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    file = models.ForeignKey(
        MediaFile, on_delete=models.CASCADE,
        related_name='variants',
        verbose_name=_("Original File")
    )
    variant_type = models.CharField(
        _("Variant Type"), max_length=20,
        choices=VARIANT_TYPES
    )
    file_path = models.CharField(_("File Path"), max_length=1000)
    cdn_url = models.URLField(_("CDN URL"), blank=True)
    width = models.PositiveIntegerField(_("Width (px)"), null=True, blank=True)
    height = models.PositiveIntegerField(_("Height (px)"), null=True, blank=True)
    size_bytes = models.BigIntegerField(_("Size (bytes)"), default=0)
    mime_type = models.CharField(_("MIME Type"), max_length=100, blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    generated_at = models.DateTimeField(_("Generated At"), auto_now_add=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Media Variant")
        verbose_name_plural = _("Media Variants")
        unique_together = [['file', 'variant_type']]
        ordering = ['variant_type']
        indexes = [
            models.Index(fields=['file', 'variant_type']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        return f"{self.file.filename} - {self.get_variant_type_display()}"

    @property
    def file_url(self):
        """Return CDN URL if available."""
        if self.cdn_url:
            return self.cdn_url
        return self.file_path

    @property
    def size_human(self):
        size = self.size_bytes
        for unit in ['B', 'KB', 'MB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} GB"


# ─────────────────────────────────────────────
# MediaUsage
# ─────────────────────────────────────────────

class MediaUsage(TimeStampedModel):
    """Track where media files are used."""
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    file = models.ForeignKey(
        MediaFile, on_delete=models.CASCADE,
        related_name='usages',
        verbose_name=_("Media File")
    )
    used_in_type = models.CharField(
        _("Used In Type"), max_length=100,
        help_text=_("Model name, e.g. 'BlogPost', 'Banner'")
    )
    used_in_id = models.PositiveIntegerField(
        _("Used In ID"),
        help_text=_("Primary key of the object using this file")
    )
    field_name = models.CharField(
        _("Field Name"), max_length=100, blank=True,
        help_text=_("Field name where media is used, e.g. 'featured_image'")
    )
    used_at = models.DateTimeField(_("Used At"), default=timezone.now)
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Media Usage")
        verbose_name_plural = _("Media Usages")
        ordering = ['-used_at']
        indexes = [
            models.Index(fields=['file', 'used_in_type']),
            models.Index(fields=['used_in_type', 'used_in_id']),
            models.Index(fields=['uuid']),
            models.Index(fields=['used_at']),
        ]

    def __str__(self):
        return f"{self.file.filename} used in {self.used_in_type}:{self.used_in_id}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            MediaFile.objects.filter(id=self.file_id).update(
                usage_count=F('usage_count') + 1
            )

    def delete(self, *args, **kwargs):
        MediaFile.objects.filter(id=self.file_id).update(
            usage_count=F('usage_count') - 1
        )
        super().delete(*args, **kwargs)

    @classmethod
    def record_usage(cls, file, used_in_type, used_in_id, field_name=''):
        """Record or update media usage."""
        obj, created = cls.objects.get_or_create(
            file=file,
            used_in_type=used_in_type,
            used_in_id=used_in_id,
            field_name=field_name,
            defaults={'used_at': timezone.now()}
        )
        if not created:
            obj.used_at = timezone.now()
            obj.is_active = True
            obj.save(update_fields=['used_at', 'is_active'])
        return obj

    @classmethod
    def remove_usage(cls, file, used_in_type, used_in_id, field_name=''):
        """Remove media usage record."""
        cls.objects.filter(
            file=file,
            used_in_type=used_in_type,
            used_in_id=used_in_id,
            field_name=field_name,
        ).update(is_active=False)

    @classmethod
    def get_unused_files(cls, days=30):
        """Get files not used anywhere in last N days."""
        cutoff = timezone.now() - __import__('datetime').timedelta(days=days)
        used_ids = cls.objects.filter(
            is_active=True, used_at__gte=cutoff
        ).values_list('file_id', flat=True)
        return MediaFile.objects.filter(
            is_active=True
        ).exclude(id__in=used_ids)
