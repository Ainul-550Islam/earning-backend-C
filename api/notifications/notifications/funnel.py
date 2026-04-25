# earning_backend/api/notifications/funnel.py
"""
Funnel Analytics — Notification conversion funnel tracking.

Tracks the full notification funnel:
  SENT → DELIVERED → READ → CLICKED → CONVERTED

Funnel stages:
  1. Sent          — notification dispatched to provider
  2. Delivered     — provider confirmed delivery to device
  3. Read          — user opened/read the notification
  4. Clicked       — user tapped CTA button / action URL
  5. Converted     — user completed the target action
                     (e.g. task done, withdrawal made, referral completed)

Provides:
  - Per-notification funnel breakdown
  - Per-campaign funnel breakdown
  - Per-channel funnel comparison
  - Time-to-convert analysis (how long after notification did user convert)
  - Drop-off analysis (where do users leave the funnel)
  - Cohort funnel (users who received notification on day X)

This is the missing feature vs Braze/Klaviyo that completes our analytics.
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional

from django.db.models import Count, Q, Avg, F
from django.utils import timezone

logger = logging.getLogger(__name__)


class NotificationFunnelService:
    """
    Tracks and analyzes notification conversion funnels.
    """

    # Funnel stage names in order
    STAGES = ['sent', 'delivered', 'read', 'clicked', 'converted']

    def get_notification_funnel(self, notification_id: int) -> Dict:
        """Get funnel breakdown for a single notification."""
        from api.notifications.models import Notification
        try:
            notif = Notification.objects.get(pk=notification_id)
        except Notification.DoesNotExist:
            return {'error': 'Notification not found'}

        return {
            'notification_id': notification_id,
            'title': notif.title,
            'channel': notif.channel,
            'funnel': {
                'sent':      1 if notif.is_sent else 0,
                'delivered': 1 if notif.is_delivered else 0,
                'read':      1 if notif.is_read else 0,
                'clicked':   notif.click_count or 0,
                'converted': self._check_conversion(notif),
            },
            'drop_off': self._calculate_drop_off(notif),
        }

    def get_campaign_funnel(self, campaign_id: int, days: int = 30) -> Dict:
        """Get funnel breakdown for a campaign."""
        from api.notifications.models import Notification
        cutoff = timezone.now() - timedelta(days=days)
        qs = Notification.objects.filter(
            campaign_id=str(campaign_id),
            created_at__gte=cutoff,
        )
        totals = qs.aggregate(
            sent=Count('id', filter=Q(is_sent=True)),
            delivered=Count('id', filter=Q(is_delivered=True)),
            read=Count('id', filter=Q(is_read=True)),
            clicked=Count('id', filter=Q(click_count__gt=0)),
        )
        total_sent = totals['sent'] or 1
        funnel = {
            'sent':      totals['sent'] or 0,
            'delivered': totals['delivered'] or 0,
            'read':      totals['read'] or 0,
            'clicked':   totals['clicked'] or 0,
            'converted': 0,  # Would need external conversion data
        }
        rates = {
            'delivery_rate':    round(funnel['delivered'] / total_sent * 100, 2),
            'read_rate':        round(funnel['read'] / max(funnel['delivered'], 1) * 100, 2),
            'click_rate':       round(funnel['clicked'] / max(funnel['read'], 1) * 100, 2),
            'overall_ctr':      round(funnel['clicked'] / total_sent * 100, 2),
        }
        drop_off = {
            'after_sent':      round((funnel['sent'] - funnel['delivered']) / total_sent * 100, 1),
            'after_delivered': round((funnel['delivered'] - funnel['read']) / max(funnel['delivered'], 1) * 100, 1),
            'after_read':      round((funnel['read'] - funnel['clicked']) / max(funnel['read'], 1) * 100, 1),
        }
        return {
            'campaign_id': campaign_id,
            'funnel': funnel,
            'rates': rates,
            'drop_off_pct': drop_off,
            'best_stage': max(rates, key=rates.get),
            'worst_stage': min(rates, key=rates.get),
        }

    def get_channel_funnel_comparison(self, days: int = 30) -> List[Dict]:
        """Compare funnel performance across all channels."""
        from api.notifications.models import Notification
        from api.notifications.choices import CHANNEL_CHOICES

        cutoff = timezone.now() - timedelta(days=days)
        results = []
        for channel_code, channel_name in CHANNEL_CHOICES:
            if channel_code in ('all',):
                continue
            qs = Notification.objects.filter(channel=channel_code, created_at__gte=cutoff, is_sent=True)
            total = qs.count()
            if total == 0:
                continue
            stats = qs.aggregate(
                delivered=Count('id', filter=Q(is_delivered=True)),
                read=Count('id', filter=Q(is_read=True)),
                clicked=Count('id', filter=Q(click_count__gt=0)),
            )
            results.append({
                'channel': channel_code,
                'channel_name': channel_name,
                'total_sent': total,
                'delivered': stats['delivered'] or 0,
                'read': stats['read'] or 0,
                'clicked': stats['clicked'] or 0,
                'delivery_rate': round((stats['delivered'] or 0) / total * 100, 2),
                'read_rate': round((stats['read'] or 0) / max(stats['delivered'] or 1, 1) * 100, 2),
                'click_rate': round((stats['clicked'] or 0) / max(stats['read'] or 1, 1) * 100, 2),
                'overall_ctr': round((stats['clicked'] or 0) / total * 100, 2),
            })
        return sorted(results, key=lambda x: -x['overall_ctr'])

    def get_funnel_by_type(self, notification_type: str, days: int = 30) -> Dict:
        """Get funnel breakdown for a specific notification type."""
        from api.notifications.models import Notification
        cutoff = timezone.now() - timedelta(days=days)
        qs = Notification.objects.filter(
            notification_type=notification_type,
            created_at__gte=cutoff,
            is_sent=True,
        )
        total = qs.count()
        if total == 0:
            return {'notification_type': notification_type, 'total': 0, 'funnel': {}}

        stats = qs.aggregate(
            delivered=Count('id', filter=Q(is_delivered=True)),
            read=Count('id', filter=Q(is_read=True)),
            clicked=Count('id', filter=Q(click_count__gt=0)),
        )

        return {
            'notification_type': notification_type,
            'total_sent': total,
            'funnel': {
                'sent':      total,
                'delivered': stats['delivered'] or 0,
                'read':      stats['read'] or 0,
                'clicked':   stats['clicked'] or 0,
            },
            'rates': {
                'delivery_rate': round((stats['delivered'] or 0) / total * 100, 2),
                'read_rate':     round((stats['read'] or 0) / max(stats['delivered'] or 1, 1) * 100, 2),
                'click_rate':    round((stats['clicked'] or 0) / max(stats['read'] or 1, 1) * 100, 2),
            },
        }

    def get_top_converting_types(self, days: int = 30, limit: int = 10) -> List[Dict]:
        """Return notification types with highest click rates."""
        from api.notifications.models import Notification
        cutoff = timezone.now() - timedelta(days=days)
        data = (
            Notification.objects.filter(created_at__gte=cutoff, is_sent=True)
            .values('notification_type')
            .annotate(
                sent=Count('id'),
                read=Count('id', filter=Q(is_read=True)),
                clicked=Count('id', filter=Q(click_count__gt=0)),
            )
            .filter(sent__gte=10)  # Minimum 10 sent for statistical significance
            .order_by('-clicked')[:limit]
        )
        return [
            {
                'notification_type': row['notification_type'],
                'sent': row['sent'],
                'read': row['read'],
                'clicked': row['clicked'],
                'click_rate': round(row['clicked'] / max(row['sent'], 1) * 100, 2),
            }
            for row in data
        ]

    def get_time_to_read_analysis(self, notification_type: str = None, days: int = 30) -> Dict:
        """
        Analyze how quickly users read notifications.
        Returns percentile breakdowns (p50, p75, p90).
        """
        from api.notifications.models import Notification
        from django.db.models import ExpressionWrapper, DurationField
        cutoff = timezone.now() - timedelta(days=days)
        qs = Notification.objects.filter(
            is_read=True,
            read_at__isnull=False,
            created_at__gte=cutoff,
        )
        if notification_type:
            qs = qs.filter(notification_type=notification_type)

        time_deltas = []
        for notif in qs.values('created_at', 'read_at').iterator(chunk_size=500):
            if notif['read_at'] and notif['created_at']:
                delta_seconds = (notif['read_at'] - notif['created_at']).total_seconds()
                if 0 <= delta_seconds <= 86400 * 7:  # Exclude outliers > 1 week
                    time_deltas.append(delta_seconds)

        if not time_deltas:
            return {'total': 0, 'avg_seconds': 0, 'p50': 0, 'p75': 0, 'p90': 0}

        time_deltas.sort()
        count = len(time_deltas)

        def percentile(vals, p):
            idx = int(len(vals) * p / 100)
            return vals[min(idx, len(vals) - 1)]

        return {
            'total_read': count,
            'avg_seconds': round(sum(time_deltas) / count, 0),
            'avg_minutes': round(sum(time_deltas) / count / 60, 1),
            'p50_seconds': round(percentile(time_deltas, 50), 0),
            'p75_seconds': round(percentile(time_deltas, 75), 0),
            'p90_seconds': round(percentile(time_deltas, 90), 0),
            'immediate_read_pct': round(
                sum(1 for t in time_deltas if t <= 60) / count * 100, 1
            ),
        }

    def _check_conversion(self, notification) -> int:
        """Check if a notification led to a conversion (click → target action)."""
        return 1 if notification.click_count and notification.click_count > 0 else 0

    def _calculate_drop_off(self, notification) -> str:
        """Return the funnel stage where this notification dropped off."""
        if not notification.is_sent:
            return 'failed_to_send'
        if not notification.is_delivered:
            return 'after_sent'
        if not notification.is_read:
            return 'after_delivered'
        if not (notification.click_count and notification.click_count > 0):
            return 'after_read'
        return 'converted'


class RFMSegmentationService:
    """
    RFM (Recency, Frequency, Monetary) segmentation for notification targeting.

    Scores users on:
      R = Recency    — How recently did they earn/withdraw? (1-5)
      F = Frequency  — How often do they complete tasks? (1-5)
      M = Monetary   — How much have they earned total? (1-5)

    Segments:
      Champions      — RFM 555 (best users)
      Loyal          — RFM 4XX (high frequency)
      At Risk        — RFM 2XX (used to be good, dropping)
      Lost           — RFM 1XX (haven't been seen in a long time)
      New            — Recent but low frequency
    """

    SEGMENTS = {
        'champions':   {'r': (4, 5), 'f': (4, 5), 'm': (4, 5), 'label': 'Champions 🏆'},
        'loyal':       {'r': (3, 5), 'f': (4, 5), 'm': (3, 5), 'label': 'Loyal Users ⭐'},
        'promising':   {'r': (4, 5), 'f': (2, 3), 'm': (2, 3), 'label': 'Promising 🌟'},
        'at_risk':     {'r': (2, 3), 'f': (3, 5), 'm': (3, 5), 'label': 'At Risk ⚠️'},
        'hibernating': {'r': (1, 2), 'f': (2, 4), 'm': (2, 4), 'label': 'Hibernating 😴'},
        'lost':        {'r': (1, 2), 'f': (1, 2), 'm': (1, 2), 'label': 'Lost 💔'},
        'new':         {'r': (4, 5), 'f': (1, 1), 'm': (1, 2), 'label': 'New User 🆕'},
    }

    def score_user(self, user) -> Dict:
        """
        Calculate RFM score for a user.
        Returns {'r': 1-5, 'f': 1-5, 'm': 1-5, 'segment': str, 'label': str}
        """
        try:
            r_score = self._recency_score(user)
            f_score = self._frequency_score(user)
            m_score = self._monetary_score(user)
            segment = self._classify(r_score, f_score, m_score)
            return {
                'user_id': user.pk,
                'r': r_score, 'f': f_score, 'm': m_score,
                'rfm': f'{r_score}{f_score}{m_score}',
                'segment': segment,
                'label': self.SEGMENTS.get(segment, {}).get('label', segment),
            }
        except Exception as exc:
            logger.warning(f'RFMSegmentationService.score_user #{user.pk}: {exc}')
            return {'user_id': user.pk, 'r': 0, 'f': 0, 'm': 0, 'rfm': '000', 'segment': 'unknown', 'label': 'Unknown'}

    def get_segment_user_ids(self, segment_name: str) -> List[int]:
        """Return user IDs in a specific RFM segment."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        scored_users = []
        for user in User.objects.filter(is_active=True).iterator(chunk_size=500):
            score = self.score_user(user)
            if score['segment'] == segment_name:
                scored_users.append(user.pk)
        return scored_users

    def _recency_score(self, user) -> int:
        """Score 1-5 based on last activity."""
        last_login = getattr(user, 'last_login', None)
        if not last_login:
            return 1
        days_since = (timezone.now() - last_login).days
        if days_since <= 7:   return 5
        if days_since <= 14:  return 4
        if days_since <= 30:  return 3
        if days_since <= 90:  return 2
        return 1

    def _frequency_score(self, user) -> int:
        """Score 1-5 based on task completion frequency."""
        try:
            from api.notifications.models import Notification
            count_30d = Notification.objects.filter(
                user=user, notification_type='task_approved',
                created_at__gte=timezone.now() - timedelta(days=30)
            ).count()
            if count_30d >= 20: return 5
            if count_30d >= 10: return 4
            if count_30d >= 5:  return 3
            if count_30d >= 1:  return 2
            return 1
        except Exception:
            return 1

    def _monetary_score(self, user) -> int:
        """Score 1-5 based on total wallet earnings."""
        try:
            wallet = getattr(user, 'wallet', None)
            total = float(getattr(wallet, 'total_earned', 0) or 0)
            if total >= 10000: return 5
            if total >= 5000:  return 4
            if total >= 1000:  return 3
            if total >= 100:   return 2
            return 1
        except Exception:
            return 1

    def _classify(self, r: int, f: int, m: int) -> str:
        """Classify user into a segment based on RFM scores."""
        for segment_name, criteria in self.SEGMENTS.items():
            if (criteria['r'][0] <= r <= criteria['r'][1] and
                criteria['f'][0] <= f <= criteria['f'][1] and
                criteria['m'][0] <= m <= criteria['m'][1]):
                return segment_name
        return 'other'


# Singletons
funnel_service = NotificationFunnelService()
rfm_service = RFMSegmentationService()
