# FILE 100 of 257 — notifications/models.py
from django.db import models
from django.conf import settings
from core.models import TimeStampedModel

class InAppNotification(TimeStampedModel):
    user              = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payment_notifications')
    notification_type = models.CharField(max_length=50)
    title             = models.CharField(max_length=200)
    message           = models.TextField()
    is_read           = models.BooleanField(default=False)
    read_at           = models.DateTimeField(null=True, blank=True)
    metadata          = models.JSONField(default=dict, blank=True)
    class Meta:
        verbose_name='In-App Notification'; verbose_name_plural='In-App Notifications'
        ordering=['-created_at']
        indexes=[models.Index(fields=['user','is_read'])]
    def __str__(self): return f'{self.user_id} — {self.title}'

class DeviceToken(TimeStampedModel):
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='device_tokens')
    token     = models.TextField(unique=True)
    platform  = models.CharField(max_length=10, choices=(('ios','iOS'),('android','Android'),('web','Web')))
    is_active = models.BooleanField(default=True)
    class Meta: verbose_name='Device Token'; verbose_name_plural='Device Tokens'
    def __str__(self): return f'{self.user_id} — {self.platform}'
