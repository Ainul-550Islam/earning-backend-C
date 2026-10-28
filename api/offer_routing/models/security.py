"""Security models for Offer Routing System."""
from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()

class SecurityEvent(models.Model):
    """Tracks security-related events in the routing system."""
    event_type = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=20, default='info')
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'offer_routing'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['event_type', 'created_at'])]

    def __str__(self):
        return f"{self.event_type} at {self.created_at}"
