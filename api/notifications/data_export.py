# earning_backend/api/notifications/data_export.py
"""Data Export — Export notification data to CSV, Excel, and JSON."""
import csv, io, json, logging
from datetime import timedelta
from django.http import StreamingHttpResponse
from django.utils import timezone
logger = logging.getLogger(__name__)

class EchoWriter:
    def write(self, v): return v

def export_notifications_csv(user=None, days=30, include_deleted=False):
    from notifications.models import Notification
    cutoff = timezone.now() - timedelta(days=days)
    qs = Notification.objects.filter(created_at__gte=cutoff)
    if user: qs = qs.filter(user=user)
    if not include_deleted: qs = qs.filter(is_deleted=False)
    qs = qs.select_related("user").order_by("-created_at")
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["ID","User","Title","Message","Type","Channel","Priority","Is Read","Is Sent","Status","Created At"])
    for n in qs.iterator(chunk_size=500):
        w.writerow([n.pk,getattr(n.user,"username",""),n.title,n.message,n.notification_type,n.channel,
                    n.priority,n.is_read,n.is_sent,n.status,n.created_at.isoformat() if n.created_at else ""])
    return out.getvalue()

def export_analytics_csv(channel=None, days=30):
    from notifications.services.NotificationAnalytics import notification_analytics
    return notification_analytics.export_analytics_csv(
        start_date=timezone.now().date()-timedelta(days=days), end_date=timezone.now().date(), channel=channel)

def export_opt_outs_csv(channel=None):
    from notifications.models.analytics import OptOutTracking
    qs = OptOutTracking.objects.filter(is_active=True).select_related("user")
    if channel: qs = qs.filter(channel=channel)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["User ID","Username","Email","Channel","Reason","Opted Out At"])
    for r in qs.iterator(chunk_size=500):
        w.writerow([r.user_id,getattr(r.user,"username",""),getattr(r.user,"email",""),
                    r.channel,r.reason,r.opted_out_at.isoformat() if r.opted_out_at else ""])
    return out.getvalue()

def export_campaign_results_json(campaign_id):
    from notifications.models import NotificationCampaign, Notification
    from django.db.models import Count, Q
    try:
        c = NotificationCampaign.objects.get(pk=campaign_id)
    except NotificationCampaign.DoesNotExist:
        return {"error":"Campaign not found"}
    stats = Notification.objects.filter(campaign_id=str(campaign_id)).aggregate(
        total=Count("id"),sent=Count("id",filter=Q(is_sent=True)),
        delivered=Count("id",filter=Q(is_delivered=True)),read=Count("id",filter=Q(is_read=True)))
    return {"campaign_id":campaign_id,"name":c.name,"status":c.status,
            "created_at":c.created_at.isoformat() if c.created_at else None,
            "total_targeted":c.total_count,"sent":c.sent_count,"failed":c.failed_count,"notifications":stats}

def export_user_data_gdpr(user):
    from notifications.models import Notification, NotificationPreference, DeviceToken
    from notifications.models.analytics import OptOutTracking, NotificationFatigue
    return {
        "user_id":user.pk,"username":user.username,"exported_at":timezone.now().isoformat(),
        "notifications":list(Notification.objects.filter(user=user).values("pk","title","notification_type","channel","priority","is_read","created_at")[:1000]),
        "opt_outs":list(OptOutTracking.objects.filter(user=user).values("channel","is_active","reason","opted_out_at")),
        "preferences":NotificationPreference.objects.filter(user=user).values().first(),
        "devices":list(DeviceToken.objects.filter(user=user).values("device_type","device_name","created_at")),
        "fatigue_stats":NotificationFatigue.objects.filter(user=user).values("sent_today","sent_this_week","sent_this_month").first(),
    }
