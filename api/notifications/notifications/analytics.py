# earning_backend/api/notifications/analytics.py
"""Analytics — Notification analytics aggregation and reporting."""
import logging
from datetime import timedelta
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
logger = logging.getLogger(__name__)

def get_delivery_summary(*, days=30, channel=None):
    from notifications.models.analytics import NotificationInsight
    cutoff = timezone.now().date() - timedelta(days=days)
    qs = NotificationInsight.objects.filter(date__gte=cutoff)
    if channel:
        qs = qs.filter(channel=channel)
    t = qs.aggregate(sent=Sum("sent"),delivered=Sum("delivered"),opened=Sum("opened"),clicked=Sum("clicked"),unsubscribed=Sum("unsubscribed"))
    sent = t["sent"] or 0; delivered = t["delivered"] or 0
    opened = t["opened"] or 0; clicked = t["clicked"] or 0
    return {"period_days":days,"channel":channel or "all","total_sent":sent,"total_delivered":delivered,
            "total_opened":opened,"total_clicked":clicked,"total_unsubscribed":t["unsubscribed"] or 0,
            "delivery_rate":round(delivered/max(sent,1)*100,2),
            "open_rate":round(opened/max(delivered,1)*100,2),
            "click_rate":round(clicked/max(opened,1)*100,2)}

def get_channel_comparison(*, days=30):
    from notifications.models.analytics import NotificationInsight
    cutoff = timezone.now().date() - timedelta(days=days)
    data = (NotificationInsight.objects.filter(date__gte=cutoff)
            .values("channel").annotate(sent=Sum("sent"),delivered=Sum("delivered"),opened=Sum("opened"),clicked=Sum("clicked"))
            .order_by("-sent"))
    return [{"channel":r["channel"],"sent":r["sent"] or 0,"delivered":r["delivered"] or 0,
             "opened":r["opened"] or 0,"clicked":r["clicked"] or 0,
             "delivery_rate":round((r["delivered"] or 0)/max(r["sent"] or 1,1)*100,2),
             "open_rate":round((r["opened"] or 0)/max(r["delivered"] or 1,1)*100,2)} for r in data]

def get_daily_trend(*, days=30, channel=None):
    from notifications.models.analytics import NotificationInsight
    cutoff = timezone.now().date() - timedelta(days=days)
    qs = NotificationInsight.objects.filter(date__gte=cutoff)
    if channel:
        qs = qs.filter(channel=channel)
    return list(qs.values("date").annotate(sent=Sum("sent"),delivered=Sum("delivered"),opened=Sum("opened")).order_by("date"))

def get_top_notification_types(*, days=30, limit=10):
    from notifications.models import Notification
    cutoff = timezone.now() - timedelta(days=days)
    return list(Notification.objects.filter(created_at__gte=cutoff)
                .values("notification_type").annotate(count=Count("id"),read=Count("id",filter=Q(is_read=True)))
                .order_by("-count")[:limit])

def get_fatigue_analytics():
    from notifications.models.analytics import NotificationFatigue
    total = NotificationFatigue.objects.count()
    fatigued = NotificationFatigue.objects.filter(is_fatigued=True).count()
    avg_daily = NotificationFatigue.objects.aggregate(avg=Avg("sent_today"))["avg"] or 0
    return {"total_users_tracked":total,"currently_fatigued":fatigued,
            "fatigue_rate":round(fatigued/max(total,1)*100,2),"avg_daily_sends":round(avg_daily,2)}

def get_opt_out_trends(*, days=30):
    from notifications.models.analytics import OptOutTracking
    cutoff = timezone.now() - timedelta(days=days)
    return list(OptOutTracking.objects.filter(opted_out_at__gte=cutoff)
                .values("channel").annotate(opt_outs=Count("id")).order_by("-opt_outs"))

def get_campaign_analytics(*, campaign_id=None, days=30):
    from notifications.models import NotificationCampaign
    qs = NotificationCampaign.objects.all()
    if campaign_id:
        qs = qs.filter(pk=campaign_id)
    else:
        qs = qs.filter(created_at__gte=timezone.now()-timedelta(days=days))
    t = qs.aggregate(total=Count("id"),sent=Sum("sent_count"),failed=Sum("failed_count"))
    sent = t["sent"] or 0; failed = t["failed"] or 0
    return {"total_campaigns":t["total"] or 0,"total_sent":sent,"total_failed":failed,
            "success_rate":round(sent/max(sent+failed,1)*100,2)}


def get_cohort_analysis(*, cohort_days=30, track_days=30):
    """
    Cohort analysis — group users by registration date, track notification engagement.
    Returns engagement rates for each cohort over time.
    """
    from notifications.models import Notification
    from django.contrib.auth import get_user_model
    from django.db.models import Count, Q
    from datetime import date, timedelta
    User = get_user_model()

    results = []
    today = timezone.now().date()

    for week_offset in range(0, cohort_days // 7):
        cohort_start = today - timedelta(days=(week_offset + 1) * 7)
        cohort_end = today - timedelta(days=week_offset * 7)
        cohort_users = User.objects.filter(
            date_joined__date__range=(cohort_start, cohort_end)
        ).values_list('pk', flat=True)

        if not cohort_users:
            continue

        stats = Notification.objects.filter(
            user_id__in=list(cohort_users),
            created_at__date__gte=cohort_start,
            created_at__date__lte=cohort_start + timedelta(days=track_days),
        ).aggregate(
            total=Count('id'),
            read=Count('id', filter=Q(is_read=True)),
            clicked=Count('id', filter=Q(click_count__gt=0)),
        )

        results.append({
            'cohort_week': cohort_start.isoformat(),
            'cohort_size': len(cohort_users),
            'notifications_sent': stats['total'] or 0,
            'notifications_read': stats['read'] or 0,
            'notifications_clicked': stats['clicked'] or 0,
            'read_rate': round((stats['read'] or 0) / max(stats['total'] or 1, 1) * 100, 2),
        })

    return results


def get_retention_analysis(*, days=30, period='weekly'):
    """
    Retention analysis — track if notifications reduce churn.
    Shows % of users who re-engaged after receiving notifications.
    """
    from notifications.models import Notification
    from django.db.models import Count
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=days)

    # Users who received notifications
    notified_users = set(
        Notification.objects.filter(created_at__gte=cutoff, is_sent=True)
        .values_list('user_id', flat=True).distinct()
    )

    # Of those, how many read at least one?
    re_engaged = set(
        Notification.objects.filter(
            user_id__in=notified_users,
            is_read=True,
            created_at__gte=cutoff,
        ).values_list('user_id', flat=True).distinct()
    )

    retention_rate = round(len(re_engaged) / max(len(notified_users), 1) * 100, 2)

    return {
        'period_days': days,
        'notified_users': len(notified_users),
        're_engaged_users': len(re_engaged),
        'retention_rate': retention_rate,
        'churned_users': len(notified_users) - len(re_engaged),
        'churn_rate': round(100 - retention_rate, 2),
    }


def get_send_time_heatmap(*, days=30, channel=None):
    """
    Send-time heatmap — grid of open rates by hour (0-23) and day of week (0-6).
    Used to visualize optimal send times.
    Returns: {0: {0: rate, 1: rate, ...}, 1: {...}} where outer=weekday, inner=hour
    """
    from notifications.models import Notification
    from django.db.models import Count, Q
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=days)
    qs = Notification.objects.filter(
        is_read=True, read_at__isnull=False,
        created_at__gte=cutoff,
    )
    if channel:
        qs = qs.filter(channel=channel)

    # Build heatmap: weekday → hour → {sent, read}
    heatmap = {d: {h: {'sent': 0, 'read': 0} for h in range(24)} for d in range(7)}

    # Count by read_at (local time approximation using UTC)
    for notif in qs.values('read_at').iterator(chunk_size=1000):
        if notif['read_at']:
            dt = notif['read_at']
            heatmap[dt.weekday()][dt.hour]['read'] += 1

    # Get sent counts
    for notif in Notification.objects.filter(
        is_sent=True, created_at__gte=cutoff,
        **({'channel': channel} if channel else {})
    ).values('created_at').iterator(chunk_size=1000):
        if notif['created_at']:
            dt = notif['created_at']
            heatmap[dt.weekday()][dt.hour]['sent'] += 1

    # Calculate rates
    rate_map = {}
    days_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for day in range(7):
        rate_map[days_labels[day]] = {}
        for hour in range(24):
            cell = heatmap[day][hour]
            rate_map[days_labels[day]][hour] = round(
                cell['read'] / max(cell['sent'], 1) * 100, 1
            )

    return {
        'days': days_labels,
        'hours': list(range(24)),
        'heatmap': rate_map,
        'best_time': _find_best_send_time(rate_map),
    }


def _find_best_send_time(rate_map):
    """Find the day+hour with highest open rate."""
    best_rate = 0
    best_day = 'Mon'
    best_hour = 9
    for day, hours in rate_map.items():
        for hour, rate in hours.items():
            if rate > best_rate and 7 <= hour <= 22:  # Business hours only
                best_rate = rate
                best_day = day
                best_hour = hour
    return {'day': best_day, 'hour': best_hour, 'rate': best_rate}
