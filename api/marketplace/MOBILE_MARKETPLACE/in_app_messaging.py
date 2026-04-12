"""
MOBILE_MARKETPLACE/in_app_messaging.py — In-App Banner & Message System
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class InAppMessage(models.Model):
    MSG_TYPES = [("banner","Banner"),("popup","Popup"),("toast","Toast"),("fullscreen","Full Screen")]
    tenant     = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                    related_name="in_app_messages_tenant")
    title      = models.CharField(max_length=200)
    body       = models.TextField()
    image_url  = models.URLField(blank=True)
    action_url = models.CharField(max_length=500, blank=True, help_text="Deep link or URL")
    action_label = models.CharField(max_length=50, blank=True, default="View")
    msg_type   = models.CharField(max_length=15, choices=MSG_TYPES, default="banner")
    target_audience = models.CharField(max_length=20, choices=[
        ("all","All Users"), ("new","New Users"), ("returning","Returning"),
        ("vip","VIP/Gold+"), ("inactive","Inactive 30+ days"),
    ], default="all")
    starts_at  = models.DateTimeField()
    ends_at    = models.DateTimeField()
    is_active  = models.BooleanField(default=True)
    priority   = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    dismissible= models.BooleanField(default=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_in_app_message"
        ordering  = ["-priority", "-created_at"]

    def __str__(self):
        return f"{self.title} ({self.msg_type})"


class MessageDismissal(models.Model):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message    = models.ForeignKey(InAppMessage, on_delete=models.CASCADE)
    dismissed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_message_dismissal"
        unique_together = [("user","message")]


def get_active_messages(tenant, user=None) -> list:
    now = timezone.now()
    qs  = InAppMessage.objects.filter(
        tenant=tenant, is_active=True,
        starts_at__lte=now, ends_at__gte=now,
    )
    if user:
        dismissed = MessageDismissal.objects.filter(user=user).values_list("message_id", flat=True)
        qs = qs.exclude(pk__in=dismissed)
    return list(qs.order_by("-priority")[:5])


def dismiss_message(user, message_id: int):
    MessageDismissal.objects.get_or_create(user=user, message_id=message_id)
