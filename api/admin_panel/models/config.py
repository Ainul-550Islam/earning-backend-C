# api/admin_panel/models/config.py
"""
Configuration & feature flag models:
  - SystemConfig
  - FeatureFlag
  - MaintenanceWindow
  - APIRateConfig
  - EmailTemplate
"""
from django.db import models
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class SystemConfig(models.Model):
    """
    Key-value system configuration store.
    Replaces hard-coded settings for runtime-configurable values.
    CPAlead-style: payment thresholds, referral rates, ad rewards, etc.
    """
    VALUE_TYPE_CHOICES = [
        ('string', 'String'),
        ('integer', 'Integer'),
        ('float', 'Float'),
        ('boolean', 'Boolean'),
        ('json', 'JSON'),
        ('url', 'URL'),
        ('email', 'Email'),
        ('text', 'Text'),
        ('color', 'Color'),
        ('date', 'Date'),
        ('datetime', 'DateTime'),
    ]

    GROUP_CHOICES = [
        ('general', 'General'),
        ('payment', 'Payment'),
        ('security', 'Security'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('notification', 'Notification'),
        ('referral', 'Referral'),
        ('earning', 'Earning'),
        ('gamification', 'Gamification'),
        ('analytics', 'Analytics'),
        ('maintenance', 'Maintenance'),
        ('api', 'API'),
        ('social', 'Social'),
        ('legal', 'Legal'),
        ('advanced', 'Advanced'),
    ]

    key = models.CharField(
        max_length=200, unique=True, db_index=True,
        verbose_name=_('Key'),
        help_text=_('Unique snake_case config key, e.g. referral_bonus_points'),
    )
    value = models.TextField(
        verbose_name=_('Value'),
        help_text=_('Stored as string; use value_type to parse correctly'),
    )
    value_type = models.CharField(
        max_length=20,
        choices=VALUE_TYPE_CHOICES,
        default='string',
        verbose_name=_('Value Type'),
    )
    group = models.CharField(
        max_length=30,
        choices=GROUP_CHOICES,
        default='general',
        db_index=True,
        verbose_name=_('Group'),
    )
    label = models.CharField(
        max_length=200, blank=True,
        verbose_name=_('Label'),
        help_text=_('Human-friendly display label'),
    )
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('What this config key controls'),
    )
    is_public = models.BooleanField(
        default=False,
        verbose_name=_('Is Public'),
        help_text=_('If True, this config is exposed via the public API'),
    )
    is_encrypted = models.BooleanField(
        default=False,
        verbose_name=_('Is Encrypted'),
        help_text=_('If True, value is stored encrypted (API keys, secrets)'),
    )
    is_readonly = models.BooleanField(
        default=False,
        verbose_name=_('Read-Only'),
        help_text=_('Prevent accidental changes to critical configs'),
    )
    validation_regex = models.CharField(
        max_length=500, blank=True,
        verbose_name=_('Validation Regex'),
        help_text=_('Optional regex to validate value before saving'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='system_configs_updated',
        verbose_name=_('Updated By'),
    )

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('System Config')
        verbose_name_plural = _('System Configs')
        ordering = ['group', 'key']
        indexes = [
            models.Index(fields=['group', 'is_public']),
        ]

    def __str__(self):
        return f"{self.key} = {self.value[:50]}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Clear individual config cache key
        cache.delete(f'admin_panel:config:{self.key}')
        cache.delete('admin_panel:config_all')

    def get_typed_value(self):
        """
        Parse stored string value to its proper Python type.
        Returns typed value based on value_type.
        """
        import json
        v = self.value
        try:
            if self.value_type == 'integer':
                return int(v)
            elif self.value_type == 'float':
                return float(v)
            elif self.value_type == 'boolean':
                return v.lower() in ('true', '1', 'yes', 'on')
            elif self.value_type == 'json':
                return json.loads(v)
            else:
                return v
        except (ValueError, TypeError, json.JSONDecodeError):
            return v

    @classmethod
    def get(cls, key: str, default=None):
        """
        Get a config value by key with caching.
        Usage: SystemConfig.get('referral_bonus_points', default=500)
        """
        cache_key = f'admin_panel:config:{key}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            config = cls.objects.get(key=key)
            typed = config.get_typed_value()
            cache.set(cache_key, typed, 600)
            return typed
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key: str, value, value_type: str = 'string', user=None):
        """
        Set a config value by key (create or update).
        """
        str_value = str(value) if not isinstance(value, str) else value
        obj, created = cls.objects.update_or_create(
            key=key,
            defaults={
                'value': str_value,
                'value_type': value_type,
                'updated_by': user,
            }
        )
        return obj


class FeatureFlag(models.Model):
    """
    Runtime feature flag with percentage rollout support.
    CPAlead-style: enable/disable referral system, leaderboard, fraud detection, etc.
    """
    flag_key = models.CharField(
        max_length=100, unique=True, db_index=True,
        verbose_name=_('Flag Key'),
        help_text=_('Unique snake_case key, e.g. referral_system'),
    )
    label = models.CharField(max_length=200, blank=True, verbose_name=_('Label'))
    description = models.TextField(blank=True, verbose_name=_('Description'))
    is_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Is Enabled'),
        help_text=_('Master on/off switch for this feature'),
    )
    rollout_pct = models.IntegerField(
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_('Rollout Percentage'),
        help_text=_('Percentage of users who see this feature (0-100). Requires is_enabled=True.'),
    )
    environments = models.JSONField(
        default=list, blank=True,
        verbose_name=_('Environments'),
        help_text=_('List of environments where flag is active, e.g. ["production", "staging"]'),
    )
    allowed_user_ids = models.JSONField(
        default=list, blank=True,
        verbose_name=_('Allowed User IDs'),
        help_text=_('Specific user IDs always granted access regardless of rollout'),
    )
    metadata = models.JSONField(
        default=dict, blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Extra flag config (A/B test variants, etc.)'),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='feature_flags_updated',
        verbose_name=_('Updated By'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Feature Flag')
        verbose_name_plural = _('Feature Flags')
        ordering = ['flag_key']

    def __str__(self):
        status = '✅' if self.is_enabled else '❌'
        return f"{status} {self.flag_key} ({self.rollout_pct}%)"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(f'admin_panel:feature_flag:{self.flag_key}')
        cache.delete('admin_panel:feature_flags')

    def is_active_for_user(self, user) -> bool:
        """
        Evaluate if this flag is active for a specific user.
        Logic:
          1. If not enabled → False
          2. If user is in allowed_user_ids → True
          3. If rollout_pct == 100 → True
          4. Hash user_id to determine rollout bucket
        """
        if not self.is_enabled:
            return False
        # Superadmins always get all features
        if hasattr(user, 'is_superuser') and user.is_superuser:
            return True
        # Check explicit allowlist
        if user.pk in (self.allowed_user_ids or []):
            return True
        # 100% rollout
        if self.rollout_pct >= 100:
            return True
        # 0% rollout
        if self.rollout_pct <= 0:
            return False
        # Hash-based bucket assignment (deterministic per user)
        import hashlib
        bucket = int(hashlib.md5(f"{self.flag_key}:{user.pk}".encode()).hexdigest(), 16) % 100
        return bucket < self.rollout_pct

    @classmethod
    def is_enabled_globally(cls, flag_key: str) -> bool:
        """Check if a flag is enabled (global, no user context)."""
        cache_key = f'admin_panel:feature_flag:{flag_key}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            flag = cls.objects.get(flag_key=flag_key)
            result = flag.is_enabled and flag.rollout_pct > 0
            cache.set(cache_key, result, 300)
            return result
        except cls.DoesNotExist:
            return False


class MaintenanceWindow(models.Model):
    """
    Scheduled maintenance windows.
    When active, non-admin users are blocked via MaintenanceModeMiddleware.
    """
    TYPE_CHOICES = [
        ('scheduled', 'Scheduled Maintenance'),
        ('emergency', 'Emergency Maintenance'),
        ('upgrade', 'System Upgrade'),
        ('backup', 'Database Backup'),
    ]

    title = models.CharField(max_length=200, verbose_name=_('Title'))
    message = models.TextField(
        verbose_name=_('User Message'),
        help_text=_('Message shown to users during maintenance'),
        default="We're currently performing maintenance. Please check back soon.",
    )
    internal_note = models.TextField(
        blank=True,
        verbose_name=_('Internal Note'),
        help_text=_('Internal description / reason (not shown to users)'),
    )
    maintenance_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default='scheduled',
        verbose_name=_('Type'),
    )
    start_at = models.DateTimeField(verbose_name=_('Start At'))
    end_at = models.DateTimeField(verbose_name=_('End At'))
    is_active = models.BooleanField(
        default=False,
        verbose_name=_('Is Active'),
        help_text=_('Manually override to force active regardless of schedule'),
    )
    notify_users = models.BooleanField(
        default=True,
        verbose_name=_('Notify Users'),
        help_text=_('Send pre-maintenance notification to users'),
    )
    notify_before_minutes = models.IntegerField(
        default=60,
        verbose_name=_('Notify Before (minutes)'),
        help_text=_('How many minutes before maintenance to notify users'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='maintenance_windows_created',
        verbose_name=_('Created By'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Maintenance Window')
        verbose_name_plural = _('Maintenance Windows')
        ordering = ['-start_at']

    def __str__(self):
        return f"{self.title} ({self.start_at:%Y-%m-%d %H:%M} → {self.end_at:%Y-%m-%d %H:%M})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_at and self.end_at and self.end_at <= self.start_at:
            raise ValidationError({'end_at': _('End time must be after start time.')})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Update maintenance mode cache
        self._sync_maintenance_cache()

    def _sync_maintenance_cache(self):
        """Sync maintenance mode status to cache."""
        now = timezone.now()
        is_in_maintenance = (
            self.is_active or
            (self.start_at <= now <= self.end_at)
        ) if self.start_at and self.end_at else self.is_active
        if is_in_maintenance:
            cache.set('admin_panel:maintenance_mode_active', True, int((self.end_at - now).total_seconds()) + 60)
            cache.set('admin_panel:maintenance_message', self.message, 3600)
        else:
            cache.delete('admin_panel:maintenance_mode_active')

    @property
    def is_currently_active(self) -> bool:
        """Check if this window is currently in effect."""
        now = timezone.now()
        if self.is_active:
            return True
        if self.start_at and self.end_at:
            return self.start_at <= now <= self.end_at
        return False

    @property
    def duration_minutes(self) -> int:
        """Return planned duration in minutes."""
        if self.start_at and self.end_at:
            return int((self.end_at - self.start_at).total_seconds() / 60)
        return 0


class APIRateConfig(models.Model):
    """
    Per-endpoint API rate limit configuration.
    Overrides default throttle settings for specific URL patterns.
    """
    endpoint_pattern = models.CharField(
        max_length=500,
        verbose_name=_('Endpoint Pattern'),
        help_text=_('URL path pattern, e.g. /api/offers/ or /api/ads/*'),
    )
    method = models.CharField(
        max_length=10,
        default='ALL',
        verbose_name=_('HTTP Method'),
        help_text=_('HTTP method (GET, POST, PUT, DELETE, ALL)'),
    )
    limit = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1)],
        verbose_name=_('Request Limit'),
        help_text=_('Maximum number of requests in the window'),
    )
    window_seconds = models.IntegerField(
        default=3600,
        validators=[MinValueValidator(1)],
        verbose_name=_('Window (seconds)'),
        help_text=_('Time window for rate limiting in seconds'),
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Is Active'))
    applies_to_admins = models.BooleanField(
        default=False,
        verbose_name=_('Applies to Admins'),
        help_text=_('If False, admin users bypass this rate limit'),
    )
    description = models.TextField(blank=True, verbose_name=_('Description'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('API Rate Config')
        verbose_name_plural = _('API Rate Configs')
        ordering = ['endpoint_pattern']

    def __str__(self):
        return f"{self.method} {self.endpoint_pattern}: {self.limit}/{self.window_seconds}s"

    @property
    def rate_per_minute(self) -> float:
        """Calculate requests per minute."""
        return round(self.limit / (self.window_seconds / 60), 2)


class EmailTemplate(models.Model):
    """
    Database-driven email templates for transactional emails.
    CPAlead-style: withdrawal approved, referral bonus, daily digest, etc.
    """
    key = models.CharField(
        max_length=100, unique=True, db_index=True,
        verbose_name=_('Template Key'),
        help_text=_('Unique key, e.g. withdrawal_approved, welcome_email'),
    )
    name = models.CharField(max_length=200, verbose_name=_('Name'))
    subject = models.CharField(max_length=300, verbose_name=_('Email Subject'))
    body_html = models.TextField(
        verbose_name=_('HTML Body'),
        help_text=_('HTML email body. Use {{variable}} for template variables.'),
    )
    body_text = models.TextField(
        blank=True,
        verbose_name=_('Plain Text Body'),
        help_text=_('Plain text fallback. Use {{variable}} for template variables.'),
    )
    variables = models.JSONField(
        default=list, blank=True,
        verbose_name=_('Variables'),
        help_text=_('List of available template variables, e.g. ["user_name", "amount"]'),
    )
    is_active = models.BooleanField(default=True, verbose_name=_('Is Active'))
    from_name = models.CharField(
        max_length=100, blank=True,
        verbose_name=_('From Name'),
        help_text=_('Override default sender name for this template'),
    )
    from_email = models.EmailField(
        blank=True,
        verbose_name=_('From Email'),
        help_text=_('Override default sender email for this template'),
    )
    reply_to = models.EmailField(
        blank=True,
        verbose_name=_('Reply-To Email'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='email_templates_updated',
        verbose_name=_('Updated By'),
    )

    class Meta:
        app_label = 'admin_panel'
        verbose_name = _('Email Template')
        verbose_name_plural = _('Email Templates')
        ordering = ['key']

    def __str__(self):
        active = '✅' if self.is_active else '❌'
        return f"{active} {self.key}: {self.name}"

    def render(self, context: dict) -> dict:
        """
        Render template with given context variables.
        Returns {'subject': ..., 'html': ..., 'text': ...}
        """
        subject = self.subject
        html = self.body_html
        text = self.body_text

        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            str_val = str(value)
            subject = subject.replace(placeholder, str_val)
            html = html.replace(placeholder, str_val)
            text = text.replace(placeholder, str_val)

        return {
            'subject': subject,
            'html': html,
            'text': text,
            'from_name': self.from_name,
            'from_email': self.from_email,
            'reply_to': self.reply_to,
        }

    @classmethod
    def get_template(cls, key: str):
        """Get an active template by key, with cache."""
        cache_key = f'admin_panel:email_template:{key}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            template = cls.objects.get(key=key, is_active=True)
            cache.set(cache_key, template, 3600)
            return template
        except cls.DoesNotExist:
            return None