from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/models_new/video.py
"""
VideoContent model — CPAlead AI video creator integration.
CPAlead 2025: YouTube Shorts, TikTok, Reels for premium members.
CMS owns the video content management side.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


VIDEO_PLATFORMS = [
    ('youtube_shorts', 'YouTube Shorts'),
    ('tiktok',         'TikTok'),
    ('instagram_reel', 'Instagram Reel'),
    ('generic',        'Generic Video'),
]

VIDEO_STATUS = [
    ('draft',      'Draft'),
    ('generating', 'AI Generating'),
    ('ready',      'Ready'),
    ('published',  'Published'),
    ('failed',     'Generation Failed'),
]

VIDEO_STYLES = [
    ('story',       'Story Format'),
    ('ranking',     'Ranking / Top 10'),
    ('rant',        'Rant / Opinion'),
    ('list',        'List Format'),
    ('dm_story',    'DM Story'),
    ('confession',  'Confession'),
    ('absurd_fact', 'Absurd Fact'),
]


class VideoContent(models.Model):
    """
    A piece of video content for social media monetization.
    CPAlead Premium: AI-generates YouTube Shorts/TikToks to drive offer traffic.
    Publisher earns AI video credits + offer commissions from video traffic.
    """
    uuid          = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title         = models.CharField(max_length=300)
    slug          = models.SlugField(max_length=300, blank=True)
    topic         = models.CharField(max_length=300, help_text="Topic for AI generation")
    platform      = models.CharField(max_length=25, choices=VIDEO_PLATFORMS, default='youtube_shorts', db_index=True)
    video_style   = models.CharField(max_length=25, choices=VIDEO_STYLES, default='story')
    status        = models.CharField(max_length=15, choices=VIDEO_STATUS, default='draft', db_index=True)

    # AI generation config
    ai_generated  = models.BooleanField(default=False)
    ai_prompt     = models.TextField(blank=True)
    ai_credits_used = models.IntegerField(default=0)

    # Content
    script        = models.TextField(blank=True, help_text="Video script / narration")
    thumbnail_url = models.URLField(blank=True)
    video_url     = models.URLField(blank=True)
    duration_sec  = models.PositiveIntegerField(default=0)

    # Monetization link
    cpalead_smartlink = models.ForeignKey(
        'cms.SmartLink', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='video_contents',
        help_text="CPAlead link to put in video description/bio"
    )
    tracking_url  = models.URLField(blank=True, help_text="Final monetization URL for bio link")

    # Performance
    views_count   = models.PositiveIntegerField(default=0)
    clicks_count  = models.PositiveIntegerField(default=0)
    conversions   = models.PositiveIntegerField(default=0)
    revenue_usd   = models.DecimalField(max_digits=10, decimal_places=4, default=0)

    # Scheduling
    publish_at    = models.DateTimeField(null=True, blank=True)
    published_at  = models.DateTimeField(null=True, blank=True)

    created_by    = models.ForeignKey(settings.AUTH_USER_MODEL,
                                      on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='video_contents')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Video Content"
        verbose_name_plural = "Video Contents"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['platform', 'status']),
            models.Index(fields=['created_by', 'status']),
            models.Index(fields=['publish_at']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        return f"[{self.platform}] {self.title} ({self.status})"

    @property
    def ctr(self) -> float:
        if not self.views_count:
            return 0.0
        return round(self.clicks_count / self.views_count * 100, 2)

    @property
    def conversion_rate(self) -> float:
        if not self.clicks_count:
            return 0.0
        return round(self.conversions / self.clicks_count * 100, 2)


class VideoGenerationRequest(models.Model):
    """Queue of AI video generation requests."""
    STATUS = [
        ('queued',     'Queued'),
        ('processing', 'Processing'),
        ('completed',  'Completed'),
        ('failed',     'Failed'),
    ]
    video        = models.OneToOneField(VideoContent, on_delete=models.CASCADE,
                                        related_name='generation_request')
    status       = models.CharField(max_length=15, choices=STATUS, default='queued', db_index=True)
    request_data = models.JSONField(default=dict)
    response_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    started_at   = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "cms"
        verbose_name = "Video Generation Request"

    def __str__(self):
        return f"VideoGen #{self.id} [{self.status}] for {self.video.title}"
