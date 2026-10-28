"""
api/support/models/notification_log.py
FILE 63/70 — Notification Audit Log Model
"""
from django.db import models
from django.conf import settings

class SupportNotificationLog(models.Model):
    CHANNEL_CHOICES = [
        ('email','Email'),('sms','SMS'),('push','Push'),
        ('telegram','Telegram'),('whatsapp','WhatsApp'),
        ('slack','Slack'),('sla_breach','SLA Breach'),('system','System'),
    ]
    STATUS_CHOICES = [('sent','Sent'),('failed','Failed'),('pending','Pending'),('skipped','Skipped')]

    user         = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                       on_delete=models.SET_NULL, related_name='notification_logs')
    ticket       = models.ForeignKey('SupportTicket', null=True, blank=True,
                       on_delete=models.SET_NULL, related_name='notification_logs')
    channel      = models.CharField(max_length=20, choices=CHANNEL_CHOICES, db_index=True)
    event        = models.CharField(max_length=100, db_index=True)
    recipient    = models.CharField(max_length=255, blank=True, default='')
    subject      = models.CharField(max_length=500, blank=True, default='')
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    error_msg    = models.TextField(blank=True, default='')
    provider     = models.CharField(max_length=50, blank=True, default='')
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label  = 'support'
        db_table   = 'support_notification_log'
        ordering   = ['-created_at']
        indexes    = [models.Index(fields=['channel','status','created_at'])]

    def __str__(self):
        return f'{self.channel}:{self.event} → {self.recipient} [{self.status}]'