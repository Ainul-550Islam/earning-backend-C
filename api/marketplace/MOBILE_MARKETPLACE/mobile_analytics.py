"""
MOBILE_MARKETPLACE/mobile_analytics.py — Mobile App Analytics
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class AppEvent(models.Model):
    EVENT_TYPES = [
        ("app_open","App Open"),("search","Search"),("product_view","Product View"),
        ("add_to_cart","Add to Cart"),("checkout_start","Checkout Start"),
        ("purchase","Purchase"),("category_view","Category View"),
        ("banner_click","Banner Click"),("share","Share Product"),
        ("review_submit","Review Submitted"),
    ]
    tenant      = models.ForeignKey("tenants.Tenant", on_delete=models.SET_NULL, null=True,
                                     related_name="app_events_tenant")
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name="app_events")
    session_id  = models.CharField(max_length=64, blank=True)
    event_type  = models.CharField(max_length=30, choices=EVENT_TYPES, db_index=True)
    platform    = models.CharField(max_length=10, choices=[("android","Android"),("ios","iOS"),("web","Web")])
    properties  = models.JSONField(default=dict, blank=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "marketplace"
        db_table  = "marketplace_app_event"
        indexes   = [
            models.Index(fields=["tenant","event_type","created_at"]),
        ]


def track_event(tenant, event_type: str, platform: str = "android",
                user=None, session_id: str = "", properties: dict = None, ip: str = None):
    AppEvent.objects.create(
        tenant=tenant, event_type=event_type, platform=platform,
        user=user, session_id=session_id,
        properties=properties or {}, ip_address=ip,
    )


def get_daily_active_users(tenant, days: int = 30) -> list:
    from django.db.models.functions import TruncDay
    from django.db.models import Count
    since = timezone.now() - timezone.timedelta(days=days)
    return list(
        AppEvent.objects.filter(tenant=tenant, event_type="app_open", created_at__gte=since)
        .annotate(day=TruncDay("created_at"))
        .values("day")
        .annotate(dau=Count("user", distinct=True))
        .order_by("day")
    )


def get_funnel(tenant, days: int = 7) -> dict:
    from django.db.models import Count
    since = timezone.now() - timezone.timedelta(days=days)
    events = ["product_view","add_to_cart","checkout_start","purchase"]
    funnel = {}
    for event in events:
        count = AppEvent.objects.filter(
            tenant=tenant, event_type=event, created_at__gte=since
        ).values("session_id").distinct().count()
        funnel[event] = count
    return funnel


def get_top_screens(tenant, days: int = 7) -> list:
    from django.db.models import Count
    since = timezone.now() - timezone.timedelta(days=days)
    return list(
        AppEvent.objects.filter(tenant=tenant, created_at__gte=since)
        .values("event_type")
        .annotate(views=Count("id"))
        .order_by("-views")[:10]
    )
