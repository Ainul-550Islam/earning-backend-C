# engagement/models/notification.py
from django.db import models
from .base import UserEngagementModel
from ..constants import NOTIF_TYPES


class Notification(UserEngagementModel):
    """In-app notification record."""

    type       = models.CharField(max_length=30, choices=NOTIF_TYPES, db_index=True)
    title      = models.CharField(max_length=200)
    body       = models.TextField(blank=True)
    icon       = models.CharField(max_length=200, blank=True)
    data       = models.JSONField(default=dict, blank=True)   # extra payload
    is_read    = models.BooleanField(default=False, db_index=True)
    read_at    = models.DateTimeField(null=True, blank=True)
    push_sent  = models.BooleanField(default=False)
    push_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes  = [
            models.Index(fields=["user", "is_read", "created_at"]),
            models.Index(fields=["tenant", "created_at"]),
        ]

    def __str__(self):
        return f"[{self.type}] {self.user} – {self.title}"

    def mark_read(self):
        from django.utils import timezone
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])


class UserPushToken(UserEngagementModel):
    """FCM / APNS push token per device."""

    PLATFORM_CHOICES = [("fcm", "Firebase"), ("apns", "Apple"), ("web", "Web Push")]

    platform   = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    token      = models.CharField(max_length=500, unique=True)
    device_id  = models.CharField(max_length=200, blank=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        unique_together = ["user", "device_id"]

    def __str__(self):
        return f"{self.user} [{self.platform}]"
