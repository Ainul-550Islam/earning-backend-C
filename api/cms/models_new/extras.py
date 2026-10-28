from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/models/extras.py
"""
Extra CMS models for CPAlead earning site:
- Notification, NotificationTemplate
- Announcement (quick notices)
- Testimonial
- SocialLink
- FooterConfig / HeaderConfig
- PopupDismissal (per-user tracking)
- UserContentInteraction (like, bookmark)
- ContentRating
- EmailTemplate
- CPALeadConfig
"""
import uuid
import logging
from django.db import models, transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from core.models import TimeStampedModel

logger = logging.getLogger(__name__)


def default_dict():
    return {}

def default_list():
    return []


# ─────────────────────────────────────────────
# Announcement / Notice (separate from ContentPage)
# ─────────────────────────────────────────────

class Announcement(TimeStampedModel):
    """Quick site-wide announcement/notice — simpler than ContentPage."""

    TYPE_CHOICES = [
        ('info', _('Info')),
        ('success', _('Success')),
        ('warning', _('Warning')),
        ('danger', _('Danger/Alert')),
        ('promo', _('Promotion')),
        ('maintenance', _('Maintenance')),
        ('reward', _('Reward Announcement')),
        ('new_feature', _('New Feature')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    title = models.CharField(_("Title"), max_length=300)
    message = models.TextField(_("Message"))
    announcement_type = models.CharField(
        _("Type"), max_length=20, choices=TYPE_CHOICES, default='info', db_index=True
    )
    icon = models.CharField(_("Icon"), max_length=100, blank=True)
    link_url = models.URLField(_("Link URL"), blank=True)
    link_text = models.CharField(_("Link Text"), max_length=100, blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    is_pinned = models.BooleanField(_("Pinned"), default=False)
    is_dismissible = models.BooleanField(_("Dismissible"), default=True)
    show_to_all = models.BooleanField(_("Show to All"), default=True)
    show_to_logged_in = models.BooleanField(_("Show to Logged-in"), default=True)
    show_to_anonymous = models.BooleanField(_("Show to Anonymous"), default=True)
    start_date = models.DateTimeField(_("Start Date"), default=timezone.now)
    end_date = models.DateTimeField(_("End Date"), null=True, blank=True)
    view_count = models.PositiveIntegerField(_("View Count"), default=0)
    dismiss_count = models.PositiveIntegerField(_("Dismiss Count"), default=0)
    priority = models.IntegerField(_("Priority"), default=0)

    class Meta:
        app_label = "cms"
        verbose_name = _("Announcement")
        verbose_name_plural = _("Announcements")
        ordering = ['-is_pinned', '-priority', '-created_at']
        indexes = [
            models.Index(fields=['announcement_type', 'is_active']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['is_active', 'is_pinned']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_announcement_type_display()})"

    def is_active_now(self):
        if not self.is_active:
            return False
        now = timezone.now()
        if now < self.start_date:
            return False
        if self.end_date and now > self.end_date:
            return False
        return True

    def record_view(self):
        Announcement.objects.filter(id=self.id).update(view_count=F('view_count') + 1)

    def record_dismiss(self):
        Announcement.objects.filter(id=self.id).update(dismiss_count=F('dismiss_count') + 1)

    @classmethod
    def get_active(cls, user=None, limit=5):
        now = timezone.now()
        q = Q(is_active=True, start_date__lte=now) & (
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )
        if user and user.is_authenticated:
            q &= Q(show_to_logged_in=True)
        else:
            q &= Q(show_to_anonymous=True)
        return cls.objects.filter(q).order_by('-is_pinned', '-priority', '-created_at')[:limit]


# ─────────────────────────────────────────────
# Notification (in-app)
# ─────────────────────────────────────────────

class Notification(TimeStampedModel):
    """In-app notification for users — earning rewards, system alerts, etc."""

    TYPE_CHOICES = [
        ('reward', _('Reward Received')),
        ('banner_reward', _('Banner Reward')),
        ('offer_reward', _('Offer Reward')),
        ('task_reward', _('Task Reward')),
        ('blog_reward', _('Blog Read Reward')),
        ('referral_bonus', _('Referral Bonus')),
        ('withdrawal', _('Withdrawal')),
        ('system', _('System')),
        ('promo', _('Promotion')),
        ('warning', _('Warning')),
        ('milestone', _('Milestone Achieved')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='cms_notifications', verbose_name=_("User")
    )
    notification_type = models.CharField(
        _("Type"), max_length=30, choices=TYPE_CHOICES, default='system', db_index=True
    )
    title = models.CharField(_("Title"), max_length=300)
    message = models.TextField(_("Message"))
    icon = models.CharField(_("Icon"), max_length=100, blank=True)
    image = models.URLField(_("Image URL"), blank=True)
    action_url = models.URLField(_("Action URL"), blank=True)
    action_text = models.CharField(_("Action Text"), max_length=100, blank=True)
    is_read = models.BooleanField(_("Read"), default=False, db_index=True)
    read_at = models.DateTimeField(_("Read At"), null=True, blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    # Earning amount (for reward notifications)
    reward_amount = models.DecimalField(
        _("Reward Amount"), max_digits=10, decimal_places=2,
        null=True, blank=True
    )
    reward_currency = models.CharField(_("Currency"), max_length=10, blank=True)
    # Link to source object
    source_type = models.CharField(_("Source Type"), max_length=100, blank=True)
    source_id = models.PositiveIntegerField(_("Source ID"), null=True, blank=True)
    metadata = models.JSONField(_("Metadata"), default=default_dict, blank=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'is_active']),
            models.Index(fields=['user', 'notification_type', 'created_at']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        return f"[{self.get_notification_type_display()}] {self.title} → {self.user}"

    def mark_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        Notification.objects.filter(id=self.id).update(is_read=True, read_at=self.read_at)

    @classmethod
    def get_unread_count(cls, user):
        cache_key = f'notif_unread_{user.id}'
        count = cache.get(cache_key)
        if count is None:
            count = cls.objects.filter(user=user, is_read=False, is_active=True).count()
            cache.set(cache_key, count, 60)
        return count

    @classmethod
    def create_reward_notification(cls, user, amount, currency='USD', source_type='', source_id=None, title='', message=''):
        """Create a reward notification for CPAlead earning."""
        if not title:
            title = f"You earned {currency} {amount}!"
        notif = cls.objects.create(
            user=user,
            notification_type='reward',
            title=title,
            message=message or f"Congratulations! You earned {currency} {amount}.",
            reward_amount=amount,
            reward_currency=currency,
            source_type=source_type,
            source_id=source_id,
        )
        cache.delete(f'notif_unread_{user.id}')
        return notif

    @classmethod
    def bulk_create_for_users(cls, user_ids, notification_type, title, message, **kwargs):
        """Create notification for multiple users at once."""
        notifications = [
            cls(
                user_id=uid,
                notification_type=notification_type,
                title=title,
                message=message,
                **kwargs
            )
            for uid in user_ids
        ]
        return cls.objects.bulk_create(notifications, ignore_conflicts=True)


# ─────────────────────────────────────────────
# NotificationTemplate
# ─────────────────────────────────────────────

class NotificationTemplate(TimeStampedModel):
    """Reusable notification templates with variable substitution."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Template Name"), max_length=200, unique=True)
    notification_type = models.CharField(
        _("Type"), max_length=30,
        choices=Notification.TYPE_CHOICES, default='system'
    )
    title_template = models.CharField(
        _("Title Template"), max_length=300,
        help_text=_("Use {variable_name} for dynamic values")
    )
    message_template = models.TextField(
        _("Message Template"),
        help_text=_("Use {variable_name} for dynamic values")
    )
    icon = models.CharField(_("Icon"), max_length=100, blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    variables = models.JSONField(
        _("Variables"), default=default_list,
        help_text=_("List of expected variable names")
    )

    class Meta:
        app_label = "cms"
        verbose_name = _("Notification Template")
        verbose_name_plural = _("Notification Templates")
        ordering = ['name']

    def __str__(self):
        return self.name

    def render(self, context: dict):
        """Render template with context variables."""
        title = self.title_template
        message = self.message_template
        for key, value in context.items():
            title = title.replace(f'{{{key}}}', str(value))
            message = message.replace(f'{{{key}}}', str(value))
        return title, message


# ─────────────────────────────────────────────
# EmailTemplate
# ─────────────────────────────────────────────

class EmailTemplate(TimeStampedModel):
    """Transactional email templates for earning site."""

    EMAIL_TYPES = [
        ('welcome', _('Welcome Email')),
        ('reward_received', _('Reward Received')),
        ('withdrawal_requested', _('Withdrawal Requested')),
        ('withdrawal_approved', _('Withdrawal Approved')),
        ('withdrawal_rejected', _('Withdrawal Rejected')),
        ('referral_bonus', _('Referral Bonus')),
        ('daily_summary', _('Daily Earning Summary')),
        ('milestone', _('Milestone Achieved')),
        ('password_reset', _('Password Reset')),
        ('email_verify', _('Email Verification')),
        ('account_suspended', _('Account Suspended')),
        ('promo', _('Promotional Email')),
        ('newsletter', _('Newsletter')),
        ('custom', _('Custom')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Template Name"), max_length=200, unique=True)
    email_type = models.CharField(
        _("Email Type"), max_length=30, choices=EMAIL_TYPES, default='custom', db_index=True
    )
    subject = models.CharField(_("Subject"), max_length=300)
    html_body = models.TextField(_("HTML Body"))
    text_body = models.TextField(_("Plain Text Body"), blank=True)
    from_name = models.CharField(_("From Name"), max_length=100, blank=True)
    from_email = models.EmailField(_("From Email"), blank=True)
    reply_to = models.EmailField(_("Reply To"), blank=True)
    is_active = models.BooleanField(_("Active"), default=True)
    variables = models.JSONField(
        _("Variables"), default=default_list,
        help_text=_("List of variable names used in template")
    )
    send_count = models.PositiveIntegerField(_("Send Count"), default=0)
    last_sent = models.DateTimeField(_("Last Sent"), null=True, blank=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Email Template")
        verbose_name_plural = _("Email Templates")
        ordering = ['email_type', 'name']
        indexes = [
            models.Index(fields=['email_type', 'is_active']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_email_type_display()})"

    def render(self, context: dict):
        """Render email template with context variables."""
        subject = self.subject
        html = self.html_body
        text = self.text_body
        for key, value in context.items():
            subject = subject.replace(f'{{{key}}}', str(value))
            html = html.replace(f'{{{key}}}', str(value))
            text = text.replace(f'{{{key}}}', str(value))
        return subject, html, text

    def increment_send_count(self):
        EmailTemplate.objects.filter(id=self.id).update(
            send_count=F('send_count') + 1,
            last_sent=timezone.now()
        )


# ─────────────────────────────────────────────
# Testimonial
# ─────────────────────────────────────────────

class Testimonial(TimeStampedModel):
    """User testimonials for earning site social proof."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='testimonials',
        verbose_name=_("User")
    )
    # Guest testimonial (if user is None)
    author_name = models.CharField(_("Author Name"), max_length=100, blank=True)
    author_location = models.CharField(_("Location"), max_length=100, blank=True)
    author_avatar = models.ImageField(
        _("Avatar"), upload_to='testimonials/avatars/', blank=True, null=True
    )
    content = models.TextField(_("Testimonial Content"))
    rating = models.IntegerField(
        _("Rating"), default=5,
        choices=[(i, str(i)) for i in range(1, 6)]
    )
    earning_amount = models.DecimalField(
        _("Earned Amount"), max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text=_("Amount earned (for earning site testimonials)")
    )
    earning_period = models.CharField(
        _("Earning Period"), max_length=100, blank=True,
        help_text=_("e.g. 'in 30 days', 'per week'")
    )
    is_active = models.BooleanField(_("Active"), default=True)
    is_featured = models.BooleanField(_("Featured"), default=False)
    is_verified = models.BooleanField(_("Verified"), default=False)
    sort_order = models.IntegerField(_("Sort Order"), default=0)
    category = models.CharField(
        _("Category"), max_length=50, blank=True,
        help_text=_("e.g. 'offers', 'tasks', 'referral'")
    )

    class Meta:
        app_label = "cms"
        verbose_name = _("Testimonial")
        verbose_name_plural = _("Testimonials")
        ordering = ['-is_featured', 'sort_order', '-created_at']
        indexes = [
            models.Index(fields=['is_active', 'is_featured']),
            models.Index(fields=['is_verified', 'rating']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        name = self.user.username if self.user else self.author_name
        return f"Testimonial by {name} ({self.rating}★)"

    @property
    def display_name(self):
        if self.user:
            return self.user.get_full_name() or self.user.username
        return self.author_name or 'Anonymous'

    @classmethod
    def get_featured(cls, limit=6):
        cache_key = f'testimonials_featured_{limit}'
        result = cache.get(cache_key)
        if result is None:
            result = list(
                cls.objects.filter(is_active=True, is_featured=True)
                .select_related('user')
                .order_by('sort_order', '-created_at')[:limit]
            )
            cache.set(cache_key, result, 3600)
        return result


# ─────────────────────────────────────────────
# SocialLink
# ─────────────────────────────────────────────

class SocialLink(TimeStampedModel):
    """Social media links for footer/header."""

    PLATFORM_CHOICES = [
        ('facebook', 'Facebook'),
        ('twitter', 'Twitter/X'),
        ('instagram', 'Instagram'),
        ('youtube', 'YouTube'),
        ('telegram', 'Telegram'),
        ('whatsapp', 'WhatsApp'),
        ('discord', 'Discord'),
        ('tiktok', 'TikTok'),
        ('linkedin', 'LinkedIn'),
        ('reddit', 'Reddit'),
        ('github', 'GitHub'),
        ('custom', 'Custom'),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    platform = models.CharField(
        _("Platform"), max_length=30, choices=PLATFORM_CHOICES, default='custom'
    )
    name = models.CharField(_("Display Name"), max_length=100, blank=True)
    url = models.URLField(_("URL"))
    icon_class = models.CharField(
        _("Icon Class"), max_length=100, blank=True,
        help_text=_("e.g. 'fab fa-facebook' or SVG content")
    )
    is_active = models.BooleanField(_("Active"), default=True)
    sort_order = models.IntegerField(_("Sort Order"), default=0)
    location = models.CharField(
        _("Location"), max_length=20,
        choices=[('header', 'Header'), ('footer', 'Footer'), ('both', 'Both')],
        default='footer'
    )
    open_in_new_tab = models.BooleanField(_("Open in New Tab"), default=True)
    follower_count = models.CharField(_("Follower Count"), max_length=20, blank=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Social Link")
        verbose_name_plural = _("Social Links")
        ordering = ['sort_order', 'platform']
        indexes = [
            models.Index(fields=['location', 'is_active']),
            models.Index(fields=['platform']),
        ]

    def __str__(self):
        return f"{self.get_platform_display()}: {self.url}"

    @classmethod
    def get_for_location(cls, location='footer'):
        cache_key = f'social_links_{location}'
        result = cache.get(cache_key)
        if result is None:
            q = Q(is_active=True) & (Q(location=location) | Q(location='both'))
            result = list(cls.objects.filter(q).order_by('sort_order'))
            cache.set(cache_key, result, 3600)
        return result


# ─────────────────────────────────────────────
# PopupDismissal (per-user tracking)
# ─────────────────────────────────────────────

class PopupDismissal(TimeStampedModel):
    """Track which popups each user has dismissed — prevent re-showing."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    popup = models.ForeignKey(
        'cms.Popup', on_delete=models.CASCADE,
        related_name='dismissals', verbose_name=_("Popup")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='popup_dismissals',
        verbose_name=_("User")
    )
    # For anonymous users
    session_key = models.CharField(_("Session Key"), max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    dismissed_at = models.DateTimeField(_("Dismissed At"), default=timezone.now)
    show_count = models.PositiveIntegerField(_("Show Count"), default=1)
    # Cookie expires
    expires_at = models.DateTimeField(_("Expires At"), null=True, blank=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Popup Dismissal")
        verbose_name_plural = _("Popup Dismissals")
        ordering = ['-dismissed_at']
        unique_together = [['popup', 'user']]
        indexes = [
            models.Index(fields=['popup', 'user']),
            models.Index(fields=['session_key', 'popup']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Popup '{self.popup.name}' dismissed by {self.user or self.session_key}"

    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    @classmethod
    def has_dismissed(cls, popup, user=None, session_key=''):
        """Check if user/session has dismissed this popup."""
        if user and user.is_authenticated:
            qs = cls.objects.filter(popup=popup, user=user)
        elif session_key:
            qs = cls.objects.filter(popup=popup, session_key=session_key)
        else:
            return False
        dismissal = qs.first()
        if dismissal and not dismissal.is_expired():
            return True
        return False

    @classmethod
    def record_dismissal(cls, popup, user=None, session_key='', ip='', cookie_days=7):
        """Record a popup dismissal."""
        from datetime import timedelta
        expires = timezone.now() + timedelta(days=cookie_days) if cookie_days > 0 else None
        if user and user.is_authenticated:
            obj, created = cls.objects.update_or_create(
                popup=popup, user=user,
                defaults={'dismissed_at': timezone.now(), 'expires_at': expires,
                          'ip_address': ip or None}
            )
        elif session_key:
            obj, created = cls.objects.update_or_create(
                popup=popup, session_key=session_key, user=None,
                defaults={'dismissed_at': timezone.now(), 'expires_at': expires,
                          'ip_address': ip or None}
            )
            cls.objects.filter(id=obj.id).update(show_count=F('show_count') + 1)
        else:
            return None
        return obj


# ─────────────────────────────────────────────
# UserContentInteraction (like, bookmark, share)
# ─────────────────────────────────────────────

class UserContentInteraction(TimeStampedModel):
    """Track user interactions with content: like, bookmark, share."""

    INTERACTION_TYPES = [
        ('like', _('Like')),
        ('bookmark', _('Bookmark/Save')),
        ('share', _('Share')),
        ('report', _('Report')),
        ('helpful', _('Helpful')),
        ('not_helpful', _('Not Helpful')),
    ]

    CONTENT_TYPES = [
        ('page', _('CMS Page')),
        ('blog', _('Blog Post')),
        ('faq', _('FAQ')),
        ('comment', _('Comment')),
        ('banner', _('Banner')),
        ('popup', _('Popup')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='content_interactions', verbose_name=_("User")
    )
    interaction_type = models.CharField(
        _("Interaction Type"), max_length=20, choices=INTERACTION_TYPES, db_index=True
    )
    content_type = models.CharField(
        _("Content Type"), max_length=20, choices=CONTENT_TYPES, db_index=True
    )
    content_id = models.PositiveIntegerField(_("Content ID"), db_index=True)
    metadata = models.JSONField(_("Metadata"), default=default_dict, blank=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("User Content Interaction")
        verbose_name_plural = _("User Content Interactions")
        unique_together = [['user', 'interaction_type', 'content_type', 'content_id']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'interaction_type', 'content_type']),
            models.Index(fields=['content_type', 'content_id', 'interaction_type']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        return f"{self.user} {self.get_interaction_type_display()} {self.content_type}:{self.content_id}"

    @classmethod
    def toggle(cls, user, interaction_type, content_type, content_id, metadata=None):
        """Toggle interaction — create if not exists, delete if exists."""
        obj, created = cls.objects.get_or_create(
            user=user,
            interaction_type=interaction_type,
            content_type=content_type,
            content_id=content_id,
            defaults={'metadata': metadata or {}}
        )
        if not created:
            obj.delete()
            return None, False  # removed
        return obj, True  # added

    @classmethod
    def has_interaction(cls, user, interaction_type, content_type, content_id):
        return cls.objects.filter(
            user=user,
            interaction_type=interaction_type,
            content_type=content_type,
            content_id=content_id
        ).exists()

    @classmethod
    def get_count(cls, content_type, content_id, interaction_type='like'):
        return cls.objects.filter(
            content_type=content_type,
            content_id=content_id,
            interaction_type=interaction_type
        ).count()


# ─────────────────────────────────────────────
# ContentRating
# ─────────────────────────────────────────────

class ContentRating(TimeStampedModel):
    """Star rating for CMS pages and blog posts."""

    CONTENT_TYPES = [
        ('page', _('CMS Page')),
        ('blog', _('Blog Post')),
        ('faq', _('FAQ')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='content_ratings', verbose_name=_("User")
    )
    content_type = models.CharField(
        _("Content Type"), max_length=20, choices=CONTENT_TYPES, db_index=True
    )
    content_id = models.PositiveIntegerField(_("Content ID"), db_index=True)
    rating = models.PositiveSmallIntegerField(
        _("Rating"),
        choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), (4, '4 Stars'), (5, '5 Stars')]
    )
    review = models.TextField(_("Review"), blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Content Rating")
        verbose_name_plural = _("Content Ratings")
        unique_together = [['user', 'content_type', 'content_id']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'content_id']),
            models.Index(fields=['user', 'content_type']),
            models.Index(fields=['uuid']),
        ]

    def __str__(self):
        return f"{self.user} rated {self.content_type}:{self.content_id} — {self.rating}★"

    @classmethod
    def get_average(cls, content_type, content_id):
        from django.db.models import Avg
        result = cls.objects.filter(
            content_type=content_type, content_id=content_id
        ).aggregate(avg=Avg('rating'), count=models.Count('id'))
        return {
            'average': round(result['avg'] or 0, 1),
            'count': result['count'] or 0
        }

    @classmethod
    def rate(cls, user, content_type, content_id, rating, review='', ip=None):
        """Create or update a rating."""
        obj, created = cls.objects.update_or_create(
            user=user, content_type=content_type, content_id=content_id,
            defaults={'rating': rating, 'review': review, 'ip_address': ip}
        )
        return obj, created


# ─────────────────────────────────────────────
# CPALeadConfig (API Integration Settings)
# ─────────────────────────────────────────────

class CPALeadConfig(TimeStampedModel):
    """CPAlead API integration configuration per tenant/site."""

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Config Name"), max_length=200, default='Default')
    is_active = models.BooleanField(_("Active"), default=True)

    # CPAlead API credentials
    api_key = models.CharField(_("API Key"), max_length=200, blank=True)
    publisher_id = models.CharField(_("Publisher ID"), max_length=100, blank=True)
    campaign_id = models.CharField(_("Campaign ID"), max_length=100, blank=True)
    website_id = models.CharField(_("Website ID"), max_length=100, blank=True)

    # Reward settings
    default_reward_per_click = models.DecimalField(
        _("Default Reward Per Click"), max_digits=10, decimal_places=4, default=0.001
    )
    default_reward_per_view = models.DecimalField(
        _("Default Reward Per View"), max_digits=10, decimal_places=4, default=0.0001
    )
    default_reward_per_offer = models.DecimalField(
        _("Default Reward Per Offer Completion"), max_digits=10, decimal_places=4, default=0.5
    )
    reward_currency = models.CharField(_("Reward Currency"), max_length=10, default='USD')

    # Limits
    daily_click_limit_per_user = models.IntegerField(
        _("Daily Click Limit Per User"), default=50
    )
    daily_earning_cap_per_user = models.DecimalField(
        _("Daily Earning Cap Per User"), max_digits=10, decimal_places=2, default=10.0
    )
    min_withdrawal = models.DecimalField(
        _("Minimum Withdrawal"), max_digits=10, decimal_places=2, default=5.0
    )

    # Postback URL
    postback_secret = models.CharField(
        _("Postback Secret"), max_length=200, blank=True,
        help_text=_("Secret key for verifying postback requests")
    )
    postback_url = models.URLField(
        _("Postback URL"), blank=True,
        help_text=_("Your site's postback URL for CPAlead callbacks")
    )

    # Fraud detection
    enable_fraud_detection = models.BooleanField(_("Enable Fraud Detection"), default=True)
    min_time_between_clicks_seconds = models.IntegerField(
        _("Min Time Between Clicks (seconds)"), default=30
    )
    max_clicks_per_ip_per_hour = models.IntegerField(
        _("Max Clicks Per IP Per Hour"), default=10
    )

    # Analytics
    total_rewards_paid = models.DecimalField(
        _("Total Rewards Paid"), max_digits=14, decimal_places=2, default=0
    )
    total_clicks_tracked = models.PositiveIntegerField(_("Total Clicks Tracked"), default=0)
    total_offers_completed = models.PositiveIntegerField(_("Total Offers Completed"), default=0)

    class Meta:
        app_label = "cms"
        verbose_name = _("CPAlead Config")
        verbose_name_plural = _("CPAlead Configs")
        ordering = ['-created_at']

    def __str__(self):
        return f"CPAlead Config: {self.name} ({'Active' if self.is_active else 'Inactive'})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete('cpalead_config_active')

    # Sentinel stored in cache when no active config exists.
    # Distinguishes "not cached yet" (cache returns the default) from
    # "we already checked and there is no config" (cache returns this string).
    _CACHE_MISS = "__no_cpalead_config__"

    @classmethod
    def get_active(cls):
        """Return the most-recently-created active CPALeadConfig, or None.

        Caching subtlety: Django's cache.get(key) returns *None* both when the
        key is absent and when the stored value is None.  Storing None for
        "no config found" therefore makes every subsequent call treat it as a
        cache miss and re-query the DB — and, worse, a stale cache entry from a
        previous test (before a DB rollback) would be indistinguishable from a
        real config lookup.

        Fix: store the ``_CACHE_MISS`` sentinel string instead of None when no
        active config exists.  This lets a single cache.get() call distinguish
        all three states correctly:

            _CACHE_MISS sentinel  →  we looked and found nothing
            None (default)        →  never been cached; go query
            CPALeadConfig object  →  cached positive result
        """
        cached = cache.get('cpalead_config_active')      # returns None on miss
        if cached is None:
            # True cache miss — query the database.
            try:
                config = cls.objects.filter(is_active=True).latest('created_at')
            except cls.DoesNotExist:
                config = None
            # Store sentinel so next call doesn't re-query when there is no config.
            cache.set('cpalead_config_active', config if config is not None else cls._CACHE_MISS, 1800)
            return config
        # Distinguish cached "no config" from a real cached object.
        if cached == cls._CACHE_MISS:
            return None
        return cached

    def get_postback_verify_url(self, request_base_url=''):
        """Get full postback URL for CPAlead dashboard."""
        if self.postback_url:
            return self.postback_url
        return f"{request_base_url}/api/cms/webhooks/cpalead/"


# ─────────────────────────────────────────────
# HeaderConfig / FooterConfig
# ─────────────────────────────────────────────

class SiteLayoutConfig(TimeStampedModel):
    """Site header/footer configuration."""

    SECTION_TYPES = [
        ('header', _('Header')),
        ('footer', _('Footer')),
        ('sidebar', _('Sidebar')),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField(_("Name"), max_length=200)
    section_type = models.CharField(
        _("Section Type"), max_length=20, choices=SECTION_TYPES, default='header', db_index=True
    )
    config = models.JSONField(_("Configuration"), default=default_dict)
    is_active = models.BooleanField(_("Active"), default=True)
    is_default = models.BooleanField(_("Default"), default=False)
    theme = models.CharField(_("Theme"), max_length=50, blank=True, default='default')
    custom_css = models.TextField(_("Custom CSS"), blank=True)
    custom_js = models.TextField(_("Custom JS"), blank=True)

    class Meta:
        app_label = "cms"
        verbose_name = _("Site Layout Config")
        verbose_name_plural = _("Site Layout Configs")
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['section_type', 'is_active', 'is_default']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_section_type_display()})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(f'layout_config_{self.section_type}')

    @classmethod
    def get_default(cls, section_type):
        cache_key = f'layout_config_{section_type}'
        config = cache.get(cache_key)
        if config is None:
            try:
                config = cls.objects.filter(
                    section_type=section_type, is_active=True, is_default=True
                ).latest('created_at')
            except cls.DoesNotExist:
                config = None
            cache.set(cache_key, config, 3600)
        return config
