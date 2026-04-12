# api/offer_inventory/ml_fraud/anomaly_detector.py
"""
Anomaly Detector — Pattern-based fraud detection for click farms and bots.
Detects: click farms, bot networks, coordinated fraud rings.
"""
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detect anomalous patterns beyond individual click scoring."""

    @staticmethod
    def detect_click_farm(hours: int = 6) -> list:
        """
        Detect click farm IPs:
        High click volume + near-zero conversion + single offer focus.
        """
        from api.offer_inventory.models import Click
        since = timezone.now() - timedelta(hours=hours)

        high_volume = list(
            Click.objects.filter(created_at__gte=since, is_fraud=False)
            .values('ip_address')
            .annotate(clicks=Count('id'))
            .filter(clicks__gte=50)
            .order_by('-clicks')[:100]
        )

        suspicious = []
        for entry in high_volume:
            ip    = entry['ip_address']
            total = entry['clicks']
            convs = Click.objects.filter(
                ip_address=ip, converted=True, created_at__gte=since
            ).count()
            cvr = convs / max(total, 1)

            if cvr < 0.01:   # <1% CVR with 50+ clicks = suspicious
                suspicious.append({
                    'ip'          : ip,
                    'clicks'      : total,
                    'conversions' : convs,
                    'cvr_pct'     : round(cvr * 100, 2),
                    'severity'    : 'high' if total >= 200 else 'medium',
                    'action'      : 'auto_block' if total >= 200 else 'review',
                })
        return suspicious

    @staticmethod
    def detect_coordinated_fraud(hours: int = 2) -> list:
        """
        Coordinated fraud: multiple users from small IP range targeting same offer.
        Pattern: many users, same /24 subnet, same offer, near-simultaneous clicks.
        """
        from api.offer_inventory.models import Click
        since = timezone.now() - timedelta(hours=hours)

        patterns = list(
            Click.objects.filter(created_at__gte=since, is_fraud=False)
            .values('offer_id')
            .annotate(
                unique_ips   =Count('ip_address', distinct=True),
                total_clicks =Count('id'),
                unique_users =Count('user_id', distinct=True),
            )
            .filter(total_clicks__gte=100, unique_ips__lte=10)
            .order_by('-total_clicks')[:20]
        )
        return [
            {**p, 'severity': 'high', 'action': 'investigate'}
            for p in patterns
        ]

    @staticmethod
    def detect_bot_network(hours: int = 1) -> list:
        """
        Bot network detection: identical user agents, rapid sequential clicks.
        """
        from api.offer_inventory.models import Click
        since = timezone.now() - timedelta(hours=hours)

        bot_uas = list(
            Click.objects.filter(created_at__gte=since)
            .exclude(user_agent='')
            .values('user_agent')
            .annotate(count=Count('id'), unique_ips=Count('ip_address', distinct=True))
            .filter(count__gte=20, unique_ips__gte=5)
            .order_by('-count')[:20]
        )
        return [
            {
                'user_agent'  : ua['user_agent'][:100],
                'click_count' : ua['count'],
                'unique_ips'  : ua['unique_ips'],
                'severity'    : 'high' if ua['count'] >= 100 else 'medium',
            }
            for ua in bot_uas
        ]

    @staticmethod
    def auto_block_detected(dry_run: bool = False) -> dict:
        """
        Auto-block IPs detected as click farms.
        dry_run=True: report only, don't block.
        """
        from api.offer_inventory.security_fraud.ip_blacklist import IPBlacklistManager

        farms   = AnomalyDetector.detect_click_farm(hours=6)
        to_block = [
            f['ip'] for f in farms
            if f['action'] == 'auto_block'
        ]

        blocked = 0
        if not dry_run:
            for ip in to_block:
                IPBlacklistManager.block(
                    ip, reason='ml_click_farm_detected', hours=72
                )
                blocked += 1

        logger.info(
            f'AnomalyDetector: {len(farms)} suspicious IPs found, '
            f'{blocked} auto-blocked (dry_run={dry_run})'
        )
        return {
            'suspicious_ips': len(farms),
            'auto_blocked'  : blocked,
            'dry_run'       : dry_run,
            'details'       : farms[:10],
        }

    @staticmethod
    def get_anomaly_summary(days: int = 7) -> dict:
        """Summary of detected anomalies."""
        from api.offer_inventory.models import FraudAttempt, BlacklistedIP
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)
        return {
            'click_farms_found'   : len(AnomalyDetector.detect_click_farm(hours=days * 24)),
            'bot_networks_found'  : len(AnomalyDetector.detect_bot_network(hours=days * 24)),
            'ips_auto_blocked'    : BlacklistedIP.objects.filter(
                reason__contains='ml_', created_at__gte=since
            ).count(),
            'period_days'         : days,
        }
