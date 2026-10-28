# api/cms/models_new/sessions.py
"""User session management — track active sessions, revoke on logout."""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class UserSession(models.Model):
    """Track active user sessions for security dashboard."""
    uuid        = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user        = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.CASCADE,
                                    related_name='tracked_sessions')
    session_key = models.CharField(max_length=100, db_index=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.CharField(max_length=500, blank=True)
    device_type = models.CharField(max_length=20, default='unknown')
    country     = models.CharField(max_length=5, blank=True)
    is_active   = models.BooleanField(default=True, db_index=True)
    last_activity = models.DateTimeField(auto_now=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    revoked_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "cms"
        verbose_name = "User Session"
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.ip_address} ({self.device_type})"

    def revoke(self):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=['is_active', 'revoked_at'])

    @classmethod
    def get_active_for_user(cls, user):
        return cls.objects.filter(user=user, is_active=True).order_by('-last_activity')

    @classmethod
    def revoke_all_for_user(cls, user, except_session: str = None):
        qs = cls.objects.filter(user=user, is_active=True)
        if except_session:
            qs = qs.exclude(session_key=except_session)
        qs.update(is_active=False, revoked_at=timezone.now())
