# support/models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import datetime
from django.conf import settings



class SupportSettings(models.Model):
    """Admin can update support links without app update"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    telegram_group = models.URLField(blank=True, help_text="Telegram group/channel link", null=True)
    telegram_admin = models.URLField(blank=True, help_text="Direct admin chat link", null=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, help_text="With country code", null=True)
    whatsapp_group = models.URLField(null=True, blank=True)
    facebook_page = models.URLField(null=True, blank=True)
    email_support = models.EmailField(blank=True)
    
    # # Business hours
    # support_hours_start = models.TimeField(default=timezone.now().time())
    # support_hours_end = models.TimeField(default=timezone.now().time())
    support_hours_start = models.TimeField(default=datetime.time(9, 0))  # 9 AM
    support_hours_end = models.TimeField(default=datetime.time(18, 0))  # 6 PM
    
    # Status
    is_support_online = models.BooleanField(default=True)
    maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True)
    
    # App update
    force_update = models.BooleanField(default=False)
    latest_version_code = models.IntegerField(default=1)
    latest_version_name = models.CharField(max_length=20, default="1.0.0", null=True, blank=True)
    update_message = models.TextField(blank=True)
    play_store_url = models.URLField(null=True, blank=True)
    
    class Meta:
        verbose_name_plural = "Support Settings"
    
    def __str__(self):
        return "Support Settings"


class SupportTicket(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    CATEGORY_CHOICES = [
        ('payment', 'Payment Issue'),
        ('coins', 'Coins Not Added'),
        ('account', 'Account Problem'),
        ('technical', 'Technical Issue'),
        ('other', 'Other'),
    ]
    
    # user = models.ForeignKey('api.User', on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, # এটি ব্যবহার করলে জ্যাঙ্গো সঠিক মডেল খুঁজে পাবে
        on_delete=models.CASCADE,
        related_name='support_supportticket_user')
    ticket_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, null=True, blank=True)
    subject = models.CharField(max_length=200, null=True, blank=True)
    description = models.TextField()
    screenshot = models.ImageField(upload_to='support_tickets/', null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', null=True, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Admin response
    admin_response = models.TextField(blank=True)
    admin_responded_at = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.ticket_id:
            import random
            self.ticket_id = f"TKT{random.randint(100000, 999999)}"
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.ticket_id} - {self.user.username}"


class FAQ(models.Model):
    """Frequently Asked Questions"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    question = models.CharField(max_length=300, null=True, blank=True)
    answer = models.TextField()
    category = models.CharField(max_length=50, default='general', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
    
    def __str__(self):
        return self.question