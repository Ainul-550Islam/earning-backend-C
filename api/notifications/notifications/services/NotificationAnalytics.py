# earning_backend/api/notifications/services/NotificationAnalytics.py
"""
NotificationAnalyticsService — computes and stores daily/weekly analytics.

Populates:
  - NotificationInsight  (per-channel daily metrics)
  - DeliveryRate         (pre-computed rate percentages)

Also exposes query helpers for dashboards and reports.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


class NotificationAnalyticsService:

    # ------------------------------------------------------------------
    # Daily insight generation
    # ------------------------------------------------------------------

    def generate_daily_insights(self, target_date: Optional[date] = None) -> Dict:
        """
        Compute per-channel metrics for target_date and upsert
        NotificationInsight + DeliveryRate records.

        Called by insight_tasks.py every day.

        Returns:
            Dict with: success, date, channels_processed, errors.
        """
        if target_date is None:
            target_date = (timezone.now() - timedelta(days=1)).date()

        from notifications.models import Notification
        from notifications.models.analytics import NotificationInsight, DeliveryRate

        channels = ['in_app', 'push', 'email', 'sms', 'telegram', 'whatsapp', 'browser']
        processed = 0
        errors = 0

        # Date range
        start = timezone.make_aware(
            timezone.datetime.combine(target_date, timezone.datetime.min.time())
        )
        end = timezone.make_aware(
            timezone.datetime.combine(target_date, timezone.datetime.max.time())
        )

        for channel in channels:
            try:
                qs = Notification.objects.filter(
                    channel=channel,
                    created_at__range=(start, end),
                    is_deleted=False,
                )

                total = qs.count()
                if total == 0:
                    continue

                sent = qs.filter(is_sent=True).count()
                delivered = qs.filter(is_delivered=True).count()
                read = qs.filter(is_read=True).count()
                failed = qs.filter(status='failed').count()
                clicked = qs.aggregate(total=Sum('click_count'))['total'] or 0
                unique_users = qs.values('user').distinct().count()
                total_cost = qs.aggregate(total=Sum('cost'))['total'] or Decimal('0')

                insight, _ = NotificationInsight.objects.update_or_create(
                    date=target_date,
                    channel=channel,
                    defaults={
                        'sent': sent,
                        'delivered': delivered,
                        'failed': failed,
                        'opened': read,
                        'clicked': clicked,
                        'unique_users_reached': unique_users,
                        'total_cost': total_cost,
                    },
                )

                DeliveryRate.upsert_from_insight(insight)
                processed += 1

            except Exception as exc:
                logger.error(f'NotificationAnalyticsService channel {channel}: {exc}')
                errors += 1

        return {
            'success': errors == 0,
            'date': str(target_date),
            'channels_processed': processed,
            'errors': errors,
        }

    def generate_weekly_summary(self, week_end_date: Optional[date] = None) -> Dict:
        """
        Aggregate NotificationInsight rows for the 7 days ending on week_end_date.
        Returns a per-channel summary dict.
        """
        if week_end_date is None:
            week_end_date = timezone.now().date()
        week_start = week_end_date - timedelta(days=6)

        from notifications.models.analytics import NotificationInsight
        from django.db.models import Sum as DSum

        rows = (
            NotificationInsight.objects.filter(date__range=(week_start, week_end_date))
            .values('channel')
            .annotate(
                total_sent=DSum('sent'),
                total_delivered=DSum('delivered'),
                total_opened=DSum('opened'),
                total_clicked=DSum('clicked'),
                total_failed=DSum('failed'),
                total_cost=DSum('total_cost'),
            )
        )

        summary = {}
        for row in rows:
            sent = row['total_sent'] or 0
            delivered = row['total_delivered'] or 0
            opened = row['total_opened'] or 0
            clicked = row['total_clicked'] or 0
            summary[row['channel']] = {
                'sent': sent,
                'delivered': delivered,
                'opened': opened,
                'clicked': clicked,
                'failed': row['total_failed'] or 0,
                'total_cost': float(row['total_cost'] or 0),
                'delivery_rate': round(delivered / sent * 100, 2) if sent else 0,
                'open_rate': round(opened / delivered * 100, 2) if delivered else 0,
                'click_rate': round(clicked / delivered * 100, 2) if delivered else 0,
            }

        return {
            'week_start': str(week_start),
            'week_end': str(week_end_date),
            'channels': summary,
        }

    # ------------------------------------------------------------------
    # Dashboard queries
    # ------------------------------------------------------------------

    def get_channel_stats(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        channels: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Return daily NotificationInsight rows for a date range (optionally
        filtered by channels).
        """
        from notifications.models.analytics import NotificationInsight

        if end_date is None:
            end_date = timezone.now().date()
        if start_date is None:
            start_date = end_date - timedelta(days=29)

        qs = NotificationInsight.objects.filter(
            date__range=(start_date, end_date)
        ).order_by('date', 'channel')

        if channels:
            qs = qs.filter(channel__in=channels)

        return [row.to_dict() for row in qs]

    def get_top_notification_types(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """Return the top N notification types by send volume."""
        from notifications.models import Notification

        if end_date is None:
            end_date = timezone.now().date()
        if start_date is None:
            start_date = end_date - timedelta(days=29)

        start_dt = timezone.make_aware(
            timezone.datetime.combine(start_date, timezone.datetime.min.time())
        )
        end_dt = timezone.make_aware(
            timezone.datetime.combine(end_date, timezone.datetime.max.time())
        )

        rows = (
            Notification.objects.filter(
                created_at__range=(start_dt, end_dt),
                is_deleted=False,
            )
            .values('notification_type')
            .annotate(count=Count('id'))
            .order_by('-count')[:limit]
        )
        return list(rows)

    def get_delivery_rates_trend(
        self,
        channel: str,
        days: int = 30,
    ) -> List[Dict]:
        """Return daily delivery_pct / open_pct / click_pct for a channel over N days."""
        from notifications.models.analytics import DeliveryRate

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days - 1)

        rows = DeliveryRate.objects.filter(
            channel=channel,
            date__range=(start_date, end_date),
        ).order_by('date')

        return [
            {
                'date': str(r.date),
                'delivery_pct': r.delivery_pct,
                'open_pct': r.open_pct,
                'click_pct': r.click_pct,
                'sample_size': r.sample_size,
            }
            for r in rows
        ]

    def get_unsubscribe_trends(self, days: int = 30) -> List[Dict]:
        """Return daily unsubscribe counts per channel."""
        from notifications.models.analytics import OptOutTracking
        from django.db.models.functions import TruncDate

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days - 1)

        rows = (
            OptOutTracking.objects.filter(
                opted_out_at__date__range=(start_date, end_date)
            )
            .annotate(day=TruncDate('opted_out_at'))
            .values('day', 'channel')
            .annotate(count=Count('id'))
            .order_by('day', 'channel')
        )
        return [
            {'date': str(r['day']), 'channel': r['channel'], 'count': r['count']}
            for r in rows
        ]


    # ------------------------------------------------------------------
    # Revenue Attribution
    # ------------------------------------------------------------------

    def calculate_revenue_attribution(
        self,
        notification_ids: list = None,
        days_back: int = 7,
        attribution_window_hours: int = 24,
    ) -> Dict:
        """
        Track which notifications led to task completions / withdrawals.
        Revenue attribution: notification click → task done within 24h.

        Returns: Dict with total_attributed_revenue, per_notification_revenue,
                 top_performing_types, conversion_rate.
        """
        from datetime import timedelta
        from django.utils import timezone
        from notifications.models import Notification
        from django.db.models import Sum, Count, F

        cutoff = timezone.now() - timedelta(days=days_back)
        attr_window = timedelta(hours=attribution_window_hours)

        # Get clicked notifications in the period
        clicked = Notification.objects.filter(
            click_count__gt=0,
            created_at__gte=cutoff,
            is_deleted=False,
        )
        if notification_ids:
            clicked = clicked.filter(pk__in=notification_ids)

        total_revenue = 0.0
        per_notification = []
        type_revenue = {}

        for notif in clicked.select_related('user').iterator(chunk_size=200):
            # Check if user completed a task/offer within attribution window
            revenue = self._get_user_revenue_after_notification(
                notif.user, notif.updated_at or notif.created_at, attr_window
            )
            if revenue > 0:
                total_revenue += revenue
                per_notification.append({
                    'notification_id': notif.pk,
                    'type': notif.notification_type,
                    'channel': notif.channel,
                    'attributed_revenue': revenue,
                })
                notif_type = notif.notification_type
                type_revenue[notif_type] = type_revenue.get(notif_type, 0) + revenue

        total_clicked = clicked.count()
        conversion_rate = len(per_notification) / max(total_clicked, 1) * 100

        return {
            'total_attributed_revenue': round(total_revenue, 2),
            'attribution_window_hours': attribution_window_hours,
            'total_notifications': total_clicked,
            'converted_notifications': len(per_notification),
            'conversion_rate': round(conversion_rate, 2),
            'top_notification_types': sorted(
                [{'type': t, 'revenue': r} for t, r in type_revenue.items()],
                key=lambda x: -x['revenue']
            )[:10],
            'days_back': days_back,
        }

    def _get_user_revenue_after_notification(self, user, after_dt, window) -> float:
        """Get revenue earned by user within attribution window after notification."""
        try:
            from wallet.models import WalletTransaction
            from django.db.models import Sum
            result = WalletTransaction.objects.filter(
                user=user,
                transaction_type='credit',
                created_at__range=(after_dt, after_dt + window),
            ).aggregate(total=Sum('amount'))
            return float(result['total'] or 0)
        except Exception:
            return 0.0

    def export_analytics_csv(self, start_date=None, end_date=None, channel: str = None) -> str:
        """
        Export NotificationInsight data as CSV string.
        Returns CSV content as string (save to file or return as response).
        """
        import csv, io
        from notifications.models.analytics import NotificationInsight
        from django.utils import timezone

        end = end_date or timezone.now().date()
        start = start_date or (end - __import__('datetime').timedelta(days=30))

        qs = NotificationInsight.objects.filter(date__range=(start, end))
        if channel:
            qs = qs.filter(channel=channel)
        qs = qs.order_by('-date', 'channel')

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Date', 'Channel', 'Sent', 'Delivered', 'Failed', 'Opened',
            'Clicked', 'Unsubscribed', 'Delivery Rate %', 'Open Rate %', 'Click Rate %'
        ])

        for row in qs:
            writer.writerow([
                row.date, row.channel, row.sent, row.delivered, row.failed,
                row.opened, row.clicked, row.unsubscribed,
                row.delivery_rate, row.open_rate, row.click_rate,
            ])

        return output.getvalue()


# Singleton
notification_analytics_service = NotificationAnalyticsService()
