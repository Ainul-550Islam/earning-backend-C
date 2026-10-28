# api/djoyalty/models/notifications.py
"""
Notification Center Models।
Customer notification inbox + templates + preferences।
World: all major loyalty platforms have in-app notification center।
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveManager

logger = logging.getLogger(__name__)


class NotificationTemplate(models.Model):
    """
    Reusable notification templates।
    One template -> many customers।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='notification_templates',
    )
    name = models.CharField(max_length=200, unique=True)
    event_type = models.CharField(max_length=100, verbose_name='Loyalty Event Type')
    channel = models.CharField(
        max_length=20,
        choices=[
            ('in_app', 'In-App'),
            ('push', 'Push'),
            ('email', 'Email'),
            ('sms', 'SMS'),
            ('all', 'All Channels'),
        ],
        default='in_app',
    )
    title_template = models.CharField(
        max_length=300,
        help_text='Use {firstname}, {points}, {tier}, {code} placeholders',
    )
    body_template = models.TextField(
        help_text='Use {firstname}, {points}, {tier}, {balance}, {code} etc.',
    )
    html_template = models.TextField(null=True, blank=True, verbose_name='HTML Template (email)')
    icon = models.CharField(max_length=100, default='🔔')
    action_url = models.CharField(max_length=500, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    priority = models.CharField(
        max_length=10,
        choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('critical', 'Critical')],
        default='normal',
    )

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Notification Template'
        ordering = ['name']
        # AUDIT FIX (4): (tenant, event_type) for template lookup per event;
        # (channel, event_type) for channel-specific rendering.
        indexes = [
            models.Index(fields=['tenant', 'event_type'],
                         name='notiftmpl_tenant_event_idx'),
            models.Index(fields=['channel', 'event_type'],
                         name='notiftmpl_channel_event_idx'),
        ]

    def render(self, context: dict) -> dict:
        """Render template with context variables।"""
        title = self.title_template
        body = self.body_template
        for key, val in context.items():
            title = title.replace(f'{{{key}}}', str(val))
            body = body.replace(f'{{{key}}}', str(val))
        return {'title': title, 'body': body}

    def __str__(self):
        return f'Template({self.name}: {self.event_type}/{self.channel})'


class NotificationPreference(models.Model):
    """
    Per-customer per-channel notification preferences।
    Customer controls what they receive and how।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='notification_preferences',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='notification_preferences',
    )

    # Channel preferences
    in_app_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)

    # Type preferences
    points_notifications = models.BooleanField(default=True)
    tier_notifications = models.BooleanField(default=True)
    badge_notifications = models.BooleanField(default=True)
    campaign_notifications = models.BooleanField(default=True)
    expiry_notifications = models.BooleanField(default=True)
    offer_notifications = models.BooleanField(default=True)
    cashout_notifications = models.BooleanField(default=True)
    marketing_notifications = models.BooleanField(default=False)

    # Frequency control
    max_per_day = models.PositiveIntegerField(default=5, verbose_name='Max notifications per day')
    quiet_hours_start = models.TimeField(null=True, blank=True, verbose_name='Quiet Hours Start (e.g. 22:00)')
    quiet_hours_end = models.TimeField(null=True, blank=True, verbose_name='Quiet Hours End (e.g. 08:00)')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Notification Preference'
        unique_together = [('customer', 'tenant')]
        # AUDIT FIX (4): unique_together covers (customer, tenant);
        # explicit index on customer for fast single-customer pref load.
        indexes = [
            models.Index(fields=['customer', 'tenant'],
                         name='notifpref_customer_tenant_idx'),
        ]

    def allows(self, channel: str, notif_type: str) -> bool:
        """Check if this preference allows a notification।"""
        channel_ok = getattr(self, f'{channel}_enabled', True)
        type_ok = getattr(self, f'{notif_type}_notifications', True)
        return channel_ok and type_ok

    def __str__(self):
        return f'NotifPref({self.customer.code}: push={self.push_enabled}, sms={self.sms_enabled})'


class NotificationCenter(models.Model):
    """
    Customer in-app notification inbox।
    World: all loyalty apps have notification bell with inbox।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='notification_center',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='notification_center',
    )
    template = models.ForeignKey(
        NotificationTemplate, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='sent_notifications',
    )

    # Content
    title = models.CharField(max_length=300)
    body = models.TextField()
    icon = models.CharField(max_length=100, default='🔔')
    image_url = models.URLField(null=True, blank=True)
    action_url = models.CharField(max_length=500, null=True, blank=True)

    # Type & Channel
    notification_type = models.CharField(
        max_length=30,
        choices=[
            ('points_earned', '💰 Points Earned'),
            ('points_expiring', '⚠️ Points Expiring'),
            ('tier_upgrade', '🏆 Tier Upgrade'),
            ('badge_unlocked', '🏅 Badge Unlocked'),
            ('voucher_issued', '🎟️ Voucher Issued'),
            ('challenge_completed', '✅ Challenge Done'),
            ('streak_milestone', '🔥 Streak Milestone'),
            ('cashout_complete', '💳 Cashout Complete'),
            ('offer_available', '🎁 Offer Available'),
            ('campaign_active', '📢 Campaign Active'),
            ('churn_win_back', '👋 Win-Back Offer'),
            ('birthday', '🎂 Birthday'),
            ('marketing', '📣 Marketing'),
            ('system', '⚙️ System'),
        ],
        default='system',
    )
    channel = models.CharField(
        max_length=10,
        choices=[('in_app', 'In-App'), ('push', 'Push'), ('email', 'Email'), ('sms', 'SMS')],
        default='in_app',
    )
    priority = models.CharField(
        max_length=10,
        choices=[('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('critical', 'Critical')],
        default='normal',
    )

    # Linked data
    linked_object_type = models.CharField(max_length=50, null=True, blank=True)
    linked_object_id = models.CharField(max_length=50, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    # Status
    is_read = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notification Center'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'is_read']),
            models.Index(fields=['customer', 'notification_type']),
            models.Index(fields=['created_at']),
        ]

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def __str__(self):
        return f'Notification({self.customer.code}: {self.notification_type} [{("read" if self.is_read else "unread")}])'
