"""
api/support/models/portal.py
FILE 64/70 — Customer Portal Models
"""
from django.db import models
from django.conf import settings

class PortalSession(models.Model):
    """Customer portal session tracking"""
    user         = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                       related_name='portal_session')
    last_visit   = models.DateTimeField(auto_now=True)
    visit_count  = models.IntegerField(default=0)
    preferred_lang = models.CharField(max_length=10, default='en')
    last_ticket  = models.ForeignKey('SupportTicket', null=True, blank=True,
                       on_delete=models.SET_NULL)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'support'
        db_table  = 'support_portal_session'

    def __str__(self):
        return f'Portal: {self.user.username}'

class KBArticleFeedback(models.Model):
    """KB article helpfulness feedback"""
    article    = models.ForeignKey('KBArticle', on_delete=models.CASCADE, related_name='feedback_entries')
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                    on_delete=models.SET_NULL)
    is_helpful = models.BooleanField()
    comment    = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label       = 'support'
        db_table        = 'support_kb_feedback'
        unique_together = [['article','user']]

    def __str__(self):
        return f'{"👍" if self.is_helpful else "👎"} {self.article.title[:40]}'