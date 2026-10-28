# api/support/models/core.py  — WORLD #1
"""
Core models: SupportSettings, SupportTicket, FAQ
These are the original 3 models from api.zip, extended for World #1.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
import datetime, random, uuid

User = settings.AUTH_USER_MODEL


class SupportSettings(models.Model):
    """Admin-configurable support settings (singleton per tenant)."""
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant', db_index=True,
    )
    # Contact
    telegram_group   = models.URLField(blank=True, null=True)
    telegram_admin   = models.URLField(blank=True, null=True)
    whatsapp_number  = models.CharField(max_length=20, blank=True, null=True)
    whatsapp_group   = models.URLField(null=True, blank=True)
    facebook_page    = models.URLField(null=True, blank=True)
    email_support    = models.EmailField(blank=True)
    # Hours
    support_hours_start = models.TimeField(default=datetime.time(9, 0))
    support_hours_end   = models.TimeField(default=datetime.time(18, 0))
    support_timezone    = models.CharField(max_length=50, default='Asia/Dhaka')
    # Status
    is_support_online   = models.BooleanField(default=True)
    maintenance_mode    = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True)
    # App update
    force_update        = models.BooleanField(default=False)
    latest_version_code = models.IntegerField(default=1)
    latest_version_name = models.CharField(max_length=20, default='1.0.0', null=True, blank=True)
    update_message      = models.TextField(blank=True)
    play_store_url      = models.URLField(null=True, blank=True)
    # World #1 extras
    ai_auto_response_enabled = models.BooleanField(default=False)
    ai_auto_send_categories  = models.JSONField(default=list)
    sla_business_hours_only  = models.BooleanField(default=True)
    chat_widget_enabled      = models.BooleanField(default=True)
    chat_widget_color        = models.CharField(max_length=10, default='#6366f1')
    chat_bot_enabled         = models.BooleanField(default=True)
    support_admin_email      = models.EmailField(blank=True)
    slack_webhook_url        = models.URLField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'support'
        verbose_name_plural = 'Support Settings'

    def __str__(self):
        return 'Support Settings'


class SupportTicket(models.Model):
    """Main support ticket model."""
    STATUS_CHOICES = [
        ('open','Open'), ('in_progress','In Progress'), ('waiting_user','Waiting for User'),
        ('resolved','Resolved'), ('closed','Closed'), ('spam','Spam'),
    ]
    PRIORITY_CHOICES = [
        ('low','Low'), ('medium','Medium'), ('high','High'), ('urgent','Urgent'),
    ]
    CATEGORY_CHOICES = [
        ('payment','Payment Issue'), ('withdrawal','Withdrawal Issue'), ('coins','Coins Not Added'),
        ('account','Account Problem'), ('fraud','Fraud/Security'), ('kyc','KYC Verification'),
        ('technical','Technical Issue'), ('referral','Referral Issue'), ('offer','Offer Issue'), ('other','Other'),
    ]
    CHANNEL_CHOICES = [
        ('web','Web Portal'), ('email','Email'), ('telegram','Telegram'),
        ('whatsapp','WhatsApp'), ('facebook','Facebook'), ('chat','Live Chat'), ('api','API'),
    ]
    tenant      = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
                    related_name='%(app_label)s_%(class)s_tenant', db_index=True)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                    related_name='support_supportticket_user')
    ticket_id   = models.CharField(max_length=20, unique=True, null=True, blank=True, db_index=True)
    category    = models.CharField(max_length=50, choices=CATEGORY_CHOICES, null=True, blank=True, db_index=True)
    subject     = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField()
    screenshot  = models.ImageField(upload_to='support_tickets/', null=True, blank=True)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', db_index=True)
    priority    = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', db_index=True)
    channel     = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='web')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                    null=True, blank=True, related_name='assigned_support_tickets')
    admin_response     = models.TextField(blank=True, default='')
    admin_responded_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at  = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    # World #1
    escalated        = models.BooleanField(default=False, db_index=True)
    escalated_at     = models.DateTimeField(null=True, blank=True)
    satisfaction_rating = models.IntegerField(null=True, blank=True)
    rating_comment   = models.TextField(blank=True, default='')
    rated_at         = models.DateTimeField(null=True, blank=True)
    ai_category      = models.CharField(max_length=50, blank=True, default='')
    ai_sentiment     = models.CharField(max_length=30, blank=True, default='')
    message_count    = models.IntegerField(default=0)
    first_response_at = models.DateTimeField(null=True, blank=True)
    source_email     = models.EmailField(blank=True, default='')

    def save(self, *args, **kwargs):
        if not self.ticket_id:
            self.ticket_id = f'TKT{random.randint(100000,999999)}'
        super().save(*args, **kwargs)

    class Meta:
        app_label = 'support'
        ordering  = ['-created_at']
        indexes   = [
            models.Index(fields=['status','priority']),
            models.Index(fields=['user','status']),
            models.Index(fields=['assigned_to','status']),
        ]

    def __str__(self):
        return f'{self.ticket_id} - {self.user.username if self.user else "N/A"}'


class FAQ(models.Model):
    """Frequently Asked Questions."""
    tenant    = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
                  related_name='%(app_label)s_%(class)s_tenant', db_index=True)
    question  = models.CharField(max_length=300, null=True, blank=True)
    answer    = models.TextField()
    category  = models.CharField(max_length=50, default='general', null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True)
    order     = models.IntegerField(default=0)
    helpful_yes = models.IntegerField(default=0)
    helpful_no  = models.IntegerField(default=0)
    view_count  = models.IntegerField(default=0)
    tags        = models.JSONField(default=list)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        app_label       = 'support'
        ordering        = ['order', '-created_at']
        verbose_name    = 'FAQ'
        verbose_name_plural = 'FAQs'

    @property
    def helpful_ratio(self):
        total = self.helpful_yes + self.helpful_no
        return round(self.helpful_yes / total * 100, 1) if total else 0

    def __str__(self):
        return self.question or ''