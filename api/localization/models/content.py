# models/content.py
# LocalizedContent, LocalizedImage, LocalizedSEO, ContentLocaleMapping, TranslationRequest
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class LocalizedContent(models.Model):
    """Generic content per locale — any content type can be localized"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    content_type = models.CharField(max_length=100, db_index=True, help_text=_("e.g. blog_post, product_description, email_template"))
    object_id = models.CharField(max_length=255, db_index=True, help_text=_("ID of the content object"))
    language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='localized_content')
    field_name = models.CharField(max_length=100, help_text=_("Which field is localized (e.g. title, body, description)"))
    value = models.TextField(help_text=_("Localized content value"))
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_content')
    approved_at = models.DateTimeField(null=True, blank=True)
    is_machine_translated = models.BooleanField(default=False)
    review_status = models.CharField(max_length=20, default='pending', choices=[
        ('pending','Pending'),('reviewed','Reviewed'),('approved','Approved'),('rejected','Rejected')
    ])
    word_count = models.PositiveIntegerField(null=True, blank=True)
    character_count = models.PositiveIntegerField(null=True, blank=True)
    source_locale = models.ForeignKey('localization.Language', on_delete=models.SET_NULL, null=True, blank=True, related_name='content_source')
    translation_note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ['content_type', 'object_id', 'language', 'field_name']
        ordering = ['-created_at']
        verbose_name = _("Localized Content")
        verbose_name_plural = _("Localized Contents")
        indexes = [
            models.Index(fields=['content_type', 'object_id'], name='idx_content_type_object_id_d48'),
            models.Index(fields=['language', 'is_approved'], name='idx_language_is_approved_1064'),
        ]

    def __str__(self):
        lang = getattr(self.language, 'code', '?')
        return f"[{lang}] {self.content_type}/{self.object_id}.{self.field_name}"

    def save(self, *args, **kwargs):
        if self.value:
            self.word_count = len(self.value.split())
            self.character_count = len(self.value)
        super().save(*args, **kwargs)


class LocalizedImage(models.Model):
    """Image per locale — different image for different languages/cultures"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    content_type = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=255, db_index=True)
    language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='localized_images', null=True, blank=True)
    country = models.ForeignKey('localization.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='localized_images')
    image_url = models.URLField(help_text=_("URL of the localized image"))
    alt_text = models.CharField(max_length=500, blank=True, help_text=_("Alt text for accessibility"))
    caption = models.TextField(blank=True)
    image_type = models.CharField(max_length=50, blank=True, choices=[
        ('banner','Banner'),('thumbnail','Thumbnail'),('hero','Hero'),
        ('icon','Icon'),('avatar','Avatar'),('background','Background'),
    ])
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    file_size_bytes = models.PositiveIntegerField(null=True, blank=True)
    is_default = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['sort_order']
        verbose_name = _("Localized Image")
        verbose_name_plural = _("Localized Images")
        indexes = [
            models.Index(fields=['content_type', 'object_id'], name='idx_content_type_object_id_ba2'),
            models.Index(fields=['language'], name='idx_language_1066'),
        ]

    def __str__(self):
        lang = getattr(self.language, 'code', 'default') if self.language else 'default'
        return f"[{lang}] {self.content_type}/{self.object_id} image"


class LocalizedSEO(models.Model):
    """SEO meta data per locale — title, description, keywords, OG tags"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    content_type = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=255, db_index=True)
    language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='localized_seo')
    meta_title = models.CharField(max_length=200, blank=True, help_text=_("SEO meta title (max 60 chars recommended)"))
    meta_description = models.TextField(blank=True, help_text=_("SEO meta description (max 160 chars recommended)"))
    meta_keywords = models.TextField(blank=True, help_text=_("Comma-separated keywords"))
    canonical_url = models.URLField(blank=True)
    hreflang_tags = models.JSONField(default=dict, blank=True, help_text=_("hreflang alternate URLs per locale"))
    og_title = models.CharField(max_length=200, blank=True, help_text=_("Open Graph title"))
    og_description = models.TextField(blank=True, help_text=_("Open Graph description"))
    og_image_url = models.URLField(blank=True)
    twitter_title = models.CharField(max_length=200, blank=True)
    twitter_description = models.TextField(blank=True)
    twitter_image_url = models.URLField(blank=True)
    structured_data = models.JSONField(default=dict, blank=True, help_text=_("JSON-LD structured data"))
    is_indexable = models.BooleanField(default=True, help_text=_("Allow search engines to index?"))
    is_followable = models.BooleanField(default=True)
    custom_robots = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ['content_type', 'object_id', 'language']
        verbose_name = _("Localized SEO")
        verbose_name_plural = _("Localized SEO")
        indexes = [models.Index(fields=['content_type', 'object_id'], name='idx_content_type_object_id_c6d')]

    def __str__(self):
        lang = getattr(self.language, 'code', '?')
        return f"[{lang}] SEO for {self.content_type}/{self.object_id}"


class ContentLocaleMapping(models.Model):
    """Defines which content is available in which locales"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    content_type = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=255, db_index=True)
    language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='content_mappings')
    is_available = models.BooleanField(default=True)
    is_primary_locale = models.BooleanField(default=False)
    publish_date = models.DateTimeField(null=True, blank=True)
    unpublish_date = models.DateTimeField(null=True, blank=True)
    redirect_to_language = models.ForeignKey('localization.Language', on_delete=models.SET_NULL, null=True, blank=True, related_name='redirect_mappings', help_text=_("Redirect to this language if not available"))
    override_url = models.CharField(max_length=500, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ['content_type', 'object_id', 'language']
        verbose_name = _("Content Locale Mapping")
        verbose_name_plural = _("Content Locale Mappings")

    def __str__(self):
        lang = getattr(self.language, 'code', '?')
        avail = "✓" if self.is_available else "✗"
        return f"{avail} [{lang}] {self.content_type}/{self.object_id}"


class TranslationRequest(models.Model):
    """Request professional/human translation for content"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        SUBMITTED = 'submitted', _('Submitted')
        ASSIGNED = 'assigned', _('Assigned')
        IN_PROGRESS = 'in_progress', _('In Progress')
        REVIEW = 'review', _('Under Review')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')

    class Priority(models.TextChoices):
        URGENT = 'urgent', _('Urgent')
        HIGH = 'high', _('High')
        NORMAL = 'normal', _('Normal')
        LOW = 'low', _('Low')

    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    source_language = models.ForeignKey('localization.Language', on_delete=models.CASCADE, related_name='translation_requests_source')
    target_languages = models.ManyToManyField('localization.Language', related_name='translation_requests_target')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='translation_requests')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_translation_requests')
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    word_count = models.PositiveIntegerField(null=True, blank=True)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    source_content = models.TextField(blank=True, help_text=_("The content to be translated"))
    reference_urls = models.JSONField(default=list, blank=True)
    style_notes = models.TextField(blank=True)
    glossary = models.ForeignKey('localization.TranslationGlossary', on_delete=models.SET_NULL, null=True, blank=True, related_name='translation_requests')
    vendor_name = models.CharField(max_length=100, blank=True)
    vendor_ref = models.CharField(max_length=100, blank=True)
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Translation Request")
        verbose_name_plural = _("Translation Requests")
        indexes = [
            models.Index(fields=['status', 'priority'], name='idx_status_priority_1068'),
            models.Index(fields=['due_date'], name='idx_due_date_1069'),
        ]

    def __str__(self):
        return f"{self.title} [{self.status}]"


# ── Screenshot / Visual Context ───────────────────────────────────
class TranslationScreenshot(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    """
    Translators-দের জন্য visual context।
    প্রতিটি TranslationKey-এর screenshot দেখা যায় Admin + Translator UI-তে।
    Phrase.com / Lokalise-এর Screenshot feature-এর equivalent।
    """
    translation_key = models.ForeignKey(
        'TranslationKey', on_delete=models.CASCADE,
        related_name='screenshots', null=True, blank=True
    )
    title        = models.CharField(max_length=200, blank=True)
    description  = models.TextField(blank=True)
    image_url    = models.URLField(blank=True, help_text=_('CDN URL of screenshot image'))
    image_data   = models.TextField(blank=True, help_text=_('Base64 encoded image (small)'))
    page_url     = models.URLField(blank=True, help_text=_('URL where this key is used'))
    component    = models.CharField(max_length=200, blank=True, help_text=_('React/Vue component name'))
    # Region of interest — where in the screenshot is the key
    region_x     = models.PositiveSmallIntegerField(null=True, blank=True)
    region_y     = models.PositiveSmallIntegerField(null=True, blank=True)
    region_w     = models.PositiveSmallIntegerField(null=True, blank=True)
    region_h     = models.PositiveSmallIntegerField(null=True, blank=True)
    uploaded_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='uploaded_screenshots'
    )
    tags         = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = _('Translation Screenshot')
        ordering = ['-created_at']

    def __str__(self):
        key = self.translation_key.key if self.translation_key else 'unlinked'
        return f"Screenshot: {key} — {self.title or self.page_url}"
