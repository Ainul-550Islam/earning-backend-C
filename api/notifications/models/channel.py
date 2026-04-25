# earning_backend/api/notifications/models/channel.py
"""
Channel-specific delivery models:
  - PushDevice         — registered user push devices (FCM / APNs / Web)
  - PushDeliveryLog    — per-device push delivery record
  - EmailDeliveryLog   — per-email delivery + open/click tracking
  - SMSDeliveryLog     — per-SMS delivery tracking
  - InAppMessage       — rich in-app banners / modals / toasts
"""

from django.db import models
from django.conf import settings
from django.utils import timezone

# ---------------------------------------------------------------------------
# PushDevice
# ---------------------------------------------------------------------------

class PushDevice(models.Model):
    """
    A registered push-notification device belonging to a user.
    Supports FCM (Android / Web), APNs (iOS) and raw web-push subscriptions.
    """

    DEVICE_TYPE_CHOICES = (
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('web', 'Web Browser'),
        ('desktop', 'Desktop'),
        ('other', 'Other'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_devices',
    )

    device_type = models.CharField(
        max_length=20,
        choices=DEVICE_TYPE_CHOICES,
        default='android',
    )

    # FCM (Android + Web push)
    fcm_token = models.CharField(
        max_length=500,
        blank=True,
        help_text='Firebase Cloud Messaging registration token',
    )

    # APNs (iOS)
    apns_token = models.CharField(
        max_length=500,
        blank=True,
        help_text='Apple Push Notification service device token',
    )

    # Web push subscription JSON (endpoint + keys)
    web_push_subscription = models.JSONField(
        default=dict,
        blank=True,
        help_text='Web push subscription object (endpoint, p256dh, auth)',
    )

    # Device metadata
    device_name = models.CharField(max_length=150, blank=True)
    device_model = models.CharField(max_length=150, blank=True)
    os_version = models.CharField(max_length=50, blank=True)
    app_version = models.CharField(max_length=50, blank=True)

    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)

    # Push delivery tracking counters
    push_sent = models.PositiveIntegerField(default=0)
    push_delivered = models.PositiveIntegerField(default=0)
    push_failed = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'notifications'
        verbose_name = 'Push Device'
        verbose_name_plural = 'Push Devices'
        ordering = ['-last_used', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['device_type']),
            models.Index(fields=['fcm_token']),
            models.Index(fields=['apns_token']),
        ]

    def __str__(self):
        return f"{self.user} — {self.device_type} ({self.device_name or 'unnamed'})"

    def get_delivery_rate(self) -> float:
        """Return push delivery rate percentage (0.0 - 100.0)."""
        if self.push_sent == 0:
            return 0.0
        return round(self.push_delivered / self.push_sent * 100, 2)

    def increment_push_delivered(self, save=True):
        from django.db.models import F
        type(self).objects.filter(pk=self.pk).update(
            push_sent=F('push_sent') + 1,
            push_delivered=F('push_delivered') + 1,
        )

    def increment_push_failed(self, save=True):
        from django.db.models import F
        type(self).objects.filter(pk=self.pk).update(
            push_sent=F('push_sent') + 1,
            push_failed=F('push_failed') + 1,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_push_token(self):
        """Return the most appropriate token for the device type."""
        if self.device_type == 'ios':
            return self.apns_token
        if self.device_type == 'web':
            return self.web_push_subscription
        return self.fcm_token  # android / desktop / other → FCM

    def touch(self):
        """Update last_used to now."""
        self.last_used = timezone.now()
        self.save(update_fields=['last_used', 'updated_at'])

    def deactivate(self, save=True):
        """Mark device as inactive (e.g. token expired / unregistered)."""
        self.is_active = False
        if save:
            self.save(update_fields=['is_active', 'updated_at'])

    def activate(self, save=True):
        """Re-activate a previously deactivated device."""
        self.is_active = True
        if save:
            self.save(update_fields=['is_active', 'updated_at'])


# ---------------------------------------------------------------------------
# PushDeliveryLog
# ---------------------------------------------------------------------------

class PushDeliveryLog(models.Model):
    """
    Records a single push-notification delivery attempt to a specific device.
    """

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('invalid_token', 'Invalid Token'),
        ('rate_limited', 'Rate Limited'),
    )

    device = models.ForeignKey(
        PushDevice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='delivery_logs',
    )

    # Keep a FK to the core Notification using a string reference to avoid
    # circular imports when this module is imported before models.py.
    notification = models.ForeignKey(
        'notifications.Notification',
        on_delete=models.CASCADE,
        related_name='push_delivery_logs',
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
    )

    # Provider response
    provider = models.CharField(
        max_length=50,
        blank=True,
        help_text='fcm / apns / web_push',
    )
    provider_message_id = models.CharField(max_length=255, blank=True)
    error_code = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)

    delivered_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'notifications'
        verbose_name = 'Push Delivery Log'
        verbose_name_plural = 'Push Delivery Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['notification', 'status']),
            models.Index(fields=['device', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"PushDelivery #{self.pk} — {self.status}"

    def mark_delivered(self, provider_message_id='', save=True):
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        if provider_message_id:
            self.provider_message_id = provider_message_id
        if save:
            self.save(update_fields=['status', 'delivered_at', 'provider_message_id', 'updated_at'])

    def mark_failed(self, error_code='', error_message='', save=True):
        self.status = 'failed'
        self.error_code = error_code
        self.error_message = error_message
        if save:
            self.save(update_fields=['status', 'error_code', 'error_message', 'updated_at'])


# ---------------------------------------------------------------------------
# EmailDeliveryLog
# ---------------------------------------------------------------------------

class EmailDeliveryLog(models.Model):
    """
    Tracks email delivery, open, and click events for a notification.
    """

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('opened', 'Opened'),
        ('clicked', 'Clicked'),
        ('bounced', 'Bounced'),
        ('spam', 'Marked as Spam'),
        ('unsubscribed', 'Unsubscribed'),
        ('failed', 'Failed'),
    )

    notification = models.ForeignKey(
        'notifications.Notification',
        on_delete=models.CASCADE,
        related_name='email_delivery_logs',
    )

    recipient = models.EmailField()

    # Provider
    provider = models.CharField(
        max_length=50,
        blank=True,
        help_text='sendgrid / smtp / ses',
    )
    message_id = models.CharField(
        max_length=255,
        blank=True,
        help_text='Provider-assigned message ID for webhook matching',
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
    )

    # Engagement
    opened_at = models.DateTimeField(null=True, blank=True)
    open_count = models.PositiveIntegerField(default=0)
    clicked_at = models.DateTimeField(null=True, blank=True)
    click_count = models.PositiveIntegerField(default=0)

    # Bounce / failure info
    error_message = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'notifications'
        verbose_name = 'Email Delivery Log'
        verbose_name_plural = 'Email Delivery Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['notification', 'status']),
            models.Index(fields=['recipient']),
            models.Index(fields=['message_id']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"EmailDelivery to {self.recipient} — {self.status}"

    def record_open(self, save=True):
        """Record an email open event."""
        if not self.opened_at:
            self.opened_at = timezone.now()
        self.open_count += 1
        self.status = 'opened'
        if save:
            self.save(update_fields=['opened_at', 'open_count', 'status', 'updated_at'])

    def record_click(self, save=True):
        """Record an email click event."""
        if not self.clicked_at:
            self.clicked_at = timezone.now()
        self.click_count += 1
        self.status = 'clicked'
        if save:
            self.save(update_fields=['clicked_at', 'click_count', 'status', 'updated_at'])

    def mark_bounced(self, error_message='', save=True):
        self.status = 'bounced'
        self.error_message = error_message
        if save:
            self.save(update_fields=['status', 'error_message', 'updated_at'])


# ---------------------------------------------------------------------------
# SMSDeliveryLog
# ---------------------------------------------------------------------------

class SMSDeliveryLog(models.Model):
    """
    Tracks SMS delivery for a notification.
    """

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('undelivered', 'Undelivered'),
        ('invalid_number', 'Invalid Number'),
    )

    GATEWAY_CHOICES = (
        ('twilio', 'Twilio'),
        ('shoho_sms', 'ShohoSMS (Bangladesh)'),
        ('nexmo', 'Vonage / Nexmo'),
        ('aws_sns', 'AWS SNS'),
        ('other', 'Other'),
    )

    notification = models.ForeignKey(
        'notifications.Notification',
        on_delete=models.CASCADE,
        related_name='sms_delivery_logs',
    )

    phone = models.CharField(max_length=30)

    gateway = models.CharField(
        max_length=20,
        choices=GATEWAY_CHOICES,
        default='twilio',
    )

    # Provider SID / message ID
    provider_sid = models.CharField(max_length=255, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
    )

    # Cost (in USD or local currency depending on gateway)
    cost = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    cost_currency = models.CharField(max_length=10, default='USD')

    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)

    delivered_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'notifications'
        verbose_name = 'SMS Delivery Log'
        verbose_name_plural = 'SMS Delivery Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['notification', 'status']),
            models.Index(fields=['phone']),
            models.Index(fields=['gateway']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"SMSDelivery to {self.phone} via {self.gateway} — {self.status}"

    def mark_delivered(self, save=True):
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        if save:
            self.save(update_fields=['status', 'delivered_at', 'updated_at'])

    def mark_failed(self, error_code='', error_message='', save=True):
        self.status = 'failed'
        self.error_code = error_code
        self.error_message = error_message
        if save:
            self.save(update_fields=['status', 'error_code', 'error_message', 'updated_at'])


# ---------------------------------------------------------------------------
# InAppMessage
# ---------------------------------------------------------------------------

class InAppMessage(models.Model):
    """
    Rich in-app messages shown as banners, modals, or toasts inside the app.
    Different from the core Notification model — these are UI-layer artefacts
    that are displayed by the frontend and may include a call-to-action URL.
    """

    MESSAGE_TYPE_CHOICES = (
        ('banner', 'Banner'),
        ('modal', 'Modal'),
        ('toast', 'Toast'),
        ('bottom_sheet', 'Bottom Sheet'),
        ('full_screen', 'Full Screen'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='in_app_messages',
    )

    # Optional link to a core Notification
    notification = models.ForeignKey(
        'notifications.Notification',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='in_app_messages',
    )

    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPE_CHOICES,
        default='toast',
    )

    title = models.CharField(max_length=255)
    body = models.TextField()

    # Optional image / icon
    image_url = models.URLField(blank=True)
    icon_url = models.URLField(blank=True)

    # Call-to-action
    cta_text = models.CharField(max_length=100, blank=True)
    cta_url = models.URLField(blank=True)

    # Extra JSON payload for the frontend
    extra_data = models.JSONField(default=dict, blank=True)

    # State
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_dismissed = models.BooleanField(default=False)
    dismissed_at = models.DateTimeField(null=True, blank=True)

    # Expiry — null means never expires
    expires_at = models.DateTimeField(null=True, blank=True)

    # Display priority (lower number = higher priority)
    display_priority = models.PositiveSmallIntegerField(default=5)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'notifications'
        verbose_name = 'In-App Message'
        verbose_name_plural = 'In-App Messages'
        ordering = ['display_priority', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'is_dismissed']),
            models.Index(fields=['user', 'expires_at']),
            models.Index(fields=['message_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"InAppMessage ({self.message_type}) — {self.title[:60]}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def is_expired(self):
        """Return True if the message has passed its expiry datetime."""
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    def mark_read(self, save=True):
        """Mark message as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            if save:
                self.save(update_fields=['is_read', 'read_at', 'updated_at'])

    def dismiss(self, save=True):
        """Dismiss (hide) the message."""
        if not self.is_dismissed:
            self.is_dismissed = True
            self.dismissed_at = timezone.now()
            if save:
                self.save(update_fields=['is_dismissed', 'dismissed_at', 'updated_at'])

    def to_dict(self):
        """Return a serialisable dict suitable for the frontend."""
        return {
            'id': self.pk,
            'message_type': self.message_type,
            'title': self.title,
            'body': self.body,
            'image_url': self.image_url,
            'icon_url': self.icon_url,
            'cta_text': self.cta_text,
            'cta_url': self.cta_url,
            'extra_data': self.extra_data,
            'is_read': self.is_read,
            'is_dismissed': self.is_dismissed,
            'is_expired': self.is_expired(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'display_priority': self.display_priority,
            'created_at': self.created_at.isoformat(),
        }
