"""
api/support/models/visitor.py
FILE 61/70 — Visitor Tracking Model
"""
from django.db import models
from django.conf import settings

class VisitorSession(models.Model):
    """Real-time visitor session tracking"""
    session_id   = models.CharField(max_length=64, unique=True, db_index=True)
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                       on_delete=models.SET_NULL, related_name='visitor_sessions')
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    user_agent   = models.CharField(max_length=500, blank=True, default='')
    referrer     = models.URLField(blank=True, default='')
    current_page = models.CharField(max_length=500, blank=True, default='')
    pages_visited= models.IntegerField(default=0)
    session_min  = models.FloatField(default=0)
    idle_seconds = models.IntegerField(default=0)
    chat_opened  = models.BooleanField(default=False)
    started_at   = models.DateTimeField(auto_now_add=True)
    last_seen    = models.DateTimeField(auto_now=True)
    is_active    = models.BooleanField(default=True)

    class Meta:
        app_label   = 'support'
        db_table    = 'support_visitor_session'
        indexes     = [models.Index(fields=['user','is_active']),
                       models.Index(fields=['last_seen'])]

    def __str__(self):
        return f'Session {self.session_id[:8]} — {self.user}'

class ProactiveTriggerLog(models.Model):
    """Track which proactive triggers fired"""
    session      = models.ForeignKey(VisitorSession, on_delete=models.CASCADE, related_name='triggers')
    trigger_id   = models.CharField(max_length=50)
    page_url     = models.CharField(max_length=500)
    did_open_chat= models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        db_table  = 'support_proactive_trigger_log'