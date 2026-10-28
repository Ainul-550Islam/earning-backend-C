# api/cms/models_new/blocks.py
"""
StreamField / Content Block System — CMS owns this.
Like Wagtail StreamField: pages/blog posts get flexible content blocks.
Block types: rich_text, image, video, cta, quote, html, code, divider, gallery
Rule: এক কাজের জন্য একটাই মালিক।
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


BLOCK_TYPES = [
    ('rich_text', 'Rich Text'),
    ('image',     'Image'),
    ('video',     'Video Embed'),
    ('cta',       'Call to Action'),
    ('quote',     'Blockquote'),
    ('html',      'Raw HTML'),
    ('code',      'Code Block'),
    ('divider',   'Divider'),
    ('gallery',   'Image Gallery'),
    ('table',     'Table'),
    ('accordion', 'Accordion / FAQ'),
    ('embed',     'External Embed'),
    ('offerwall', 'CPAlead Offerwall Block'),
    ('locker',    'Content Locker Block'),
]

CONTENT_PARENT_TYPES = [
    ('page',      'CMS Page'),
    ('blog_post', 'Blog Post'),
    ('popup',     'Popup Content'),
    ('email',     'Email Template'),
]


class BlockDefinition(models.Model):
    """Reusable block template (admin defines available block types)."""
    block_type  = models.CharField(max_length=20, choices=BLOCK_TYPES, unique=True)
    label       = models.CharField(max_length=100)
    icon        = models.CharField(max_length=50, default='📝')
    schema      = models.JSONField(default=dict, help_text="JSON schema for block fields")
    is_active   = models.BooleanField(default=True)
    order       = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "cms"
        verbose_name = "Block Definition"
        ordering = ['order']

    def __str__(self):
        return f"{self.icon} {self.label}"


class ContentBlock(models.Model):
    """
    A single content block inside a page or blog post.
    Each block has a type and JSON data matching that type's schema.
    """
    uuid         = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    # Parent content (page or blog post)
    parent_type  = models.CharField(max_length=20, choices=CONTENT_PARENT_TYPES,
                                    default='page', db_index=True)
    parent_id    = models.PositiveIntegerField(db_index=True)
    block_type   = models.CharField(max_length=20, choices=BLOCK_TYPES, db_index=True)
    order        = models.PositiveIntegerField(default=0)
    # Block data — structure depends on block_type
    data         = models.JSONField(default=dict,
                                    help_text="Block content: text, url, alt, caption, etc.")
    # Common optional settings
    css_class    = models.CharField(max_length=200, blank=True)
    is_visible   = models.BooleanField(default=True)
    # Rich text content (for rich_text block — kept separate for FTS)
    text_content = models.TextField(blank=True)
    created_by   = models.ForeignKey(settings.AUTH_USER_MODEL,
                                     on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='content_blocks')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Content Block"
        ordering = ['order']
        indexes = [
            models.Index(fields=['parent_type', 'parent_id', 'order']),
            models.Index(fields=['block_type', 'is_visible']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        return f"[{self.block_type}] {self.parent_type}#{self.parent_id} order={self.order}"

    def render_preview(self) -> str:
        """Return short text preview for admin list."""
        if self.block_type == 'rich_text':
            txt = self.text_content or self.data.get('content', '')
            return txt[:100] if txt else ''
        elif self.block_type == 'image':
            return self.data.get('alt', self.data.get('url', ''))[:100]
        elif self.block_type in ('cta', 'quote'):
            return self.data.get('text', '')[:100]
        return f"{self.get_block_type_display()} block"

    @classmethod
    def get_blocks_for(cls, parent_type: str, parent_id: int):
        return cls.objects.filter(
            parent_type=parent_type,
            parent_id=parent_id,
            is_visible=True,
        ).order_by('order')
