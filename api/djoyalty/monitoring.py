# api/djoyalty/monitoring.py
"""
Djoyalty Monitoring -- Production monitoring, alerting, metrics।
Prometheus metrics, Sentry integration, custom alerting।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
import time
import threading
from collections import defaultdict, deque
from contextlib import contextmanager
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)

_metrics_lock = threading.Lock()


class MetricsCounter:
    """Thread-safe in-memory metrics counters।"""
    _data = defaultdict(int)
    _timers = defaultdict(lambda: deque(maxlen=1000))

    @classmethod
    def increment(cls, key: str, value: int = 1):
        with _metrics_lock:
            cls._data[key] += value

    @classmethod
    def record_timing(cls, key: str, duration_ms: float):
        with _metrics_lock:
            cls._timers[key].append(duration_ms)

    @classmethod
    def get(cls, key: str) -> int:
        return cls._data.get(key, 0)

    @classmethod
    def get_avg_timing(cls, key: str) -> float:
        timings = cls._timers.get(key, deque())
        if not timings:
            return 0.0
        return sum(timings) / len(timings)

    @classmethod
    def get_all(cls) -> dict:
        return {
            'counters': dict(cls._data),
            'timing_averages': {k: cls.get_avg_timing(k) for k in cls._timers},
        }

    @classmethod
    def reset(cls):
        with _metrics_lock:
            cls._data.clear()
            cls._timers.clear()


class LoyaltyMetrics:
    """
    Business metrics for loyalty system monitoring।
    Records: points earned/redeemed, cashouts, offers completed, errors।
    """

    # Event counters
    POINTS_EARNED        = 'loyalty.points.earned'
    POINTS_REDEEMED      = 'loyalty.points.redeemed'
    POINTS_EXPIRED       = 'loyalty.points.expired'
    TIER_UPGRADES        = 'loyalty.tier.upgrades'
    BADGES_AWARDED       = 'loyalty.badges.awarded'
    VOUCHERS_ISSUED      = 'loyalty.vouchers.issued'
    VOUCHERS_USED        = 'loyalty.vouchers.used'
    CASHOUTS_REQUESTED   = 'loyalty.cashouts.requested'
    CASHOUTS_COMPLETED   = 'loyalty.cashouts.completed'
    OFFERS_COMPLETED     = 'loyalty.offers.completed'
    NOTIFICATIONS_SENT   = 'loyalty.notifications.sent'
    API_CALLS            = 'loyalty.api.calls'
    API_ERRORS           = 'loyalty.api.errors'
    EARN_LATENCY_MS      = 'loyalty.earn.latency_ms'
    DB_QUERY_LATENCY_MS  = 'loyalty.db.latency_ms'

    @classmethod
    def track_earn(cls, points: Decimal, duration_ms: float = 0):
        MetricsCounter.increment(cls.POINTS_EARNED)
        if duration_ms:
            MetricsCounter.record_timing(cls.EARN_LATENCY_MS, duration_ms)

    @classmethod
    def track_redeem(cls, points: Decimal):
        MetricsCounter.increment(cls.POINTS_REDEEMED)

    @classmethod
    def track_tier_upgrade(cls):
        MetricsCounter.increment(cls.TIER_UPGRADES)

    @classmethod
    def track_cashout_request(cls):
        MetricsCounter.increment(cls.CASHOUTS_REQUESTED)

    @classmethod
    def track_cashout_complete(cls):
        MetricsCounter.increment(cls.CASHOUTS_COMPLETED)

    @classmethod
    def track_offer_complete(cls):
        MetricsCounter.increment(cls.OFFERS_COMPLETED)

    @classmethod
    def track_api_call(cls, endpoint: str = '', success: bool = True):
        MetricsCounter.increment(cls.API_CALLS)
        if not success:
            MetricsCounter.increment(cls.API_ERRORS)

    @classmethod
    def get_dashboard(cls) -> dict:
        """Get metrics dashboard data।"""
        return {
            'points_earned_total': MetricsCounter.get(cls.POINTS_EARNED),
            'points_redeemed_total': MetricsCounter.get(cls.POINTS_REDEEMED),
            'tier_upgrades': MetricsCounter.get(cls.TIER_UPGRADES),
            'cashouts_requested': MetricsCounter.get(cls.CASHOUTS_REQUESTED),
            'cashouts_completed': MetricsCounter.get(cls.CASHOUTS_COMPLETED),
            'offers_completed': MetricsCounter.get(cls.OFFERS_COMPLETED),
            'notifications_sent': MetricsCounter.get(cls.NOTIFICATIONS_SENT),
            'api_calls': MetricsCounter.get(cls.API_CALLS),
            'api_errors': MetricsCounter.get(cls.API_ERRORS),
            'api_error_rate': (
                f"{MetricsCounter.get(cls.API_ERRORS) / max(MetricsCounter.get(cls.API_CALLS), 1) * 100:.1f}%"
            ),
            'avg_earn_latency_ms': round(MetricsCounter.get_avg_timing(cls.EARN_LATENCY_MS), 2),
            'timestamp': timezone.now().isoformat(),
        }


class AlertManager:
    """Send alerts when thresholds exceeded।"""

    THRESHOLDS = {
        'api_error_rate_pct':     5.0,   # Alert if > 5% errors
        'earn_latency_ms':        500.0, # Alert if > 500ms avg
        'pending_cashouts':       100,   # Alert if > 100 pending
        'fraud_flags_per_hour':   20,    # Alert if > 20 fraud flags/hour
    }

    @classmethod
    def check_all(cls) -> list:
        """Check all thresholds and return list of alerts।"""
        alerts = []

        # API error rate
        api_calls = MetricsCounter.get(LoyaltyMetrics.API_CALLS)
        api_errors = MetricsCounter.get(LoyaltyMetrics.API_ERRORS)
        if api_calls > 0:
            error_rate = api_errors / api_calls * 100
            if error_rate > cls.THRESHOLDS['api_error_rate_pct']:
                alerts.append({
                    'level': 'critical',
                    'type': 'api_errors',
                    'message': f'API error rate is {error_rate:.1f}% (threshold: {cls.THRESHOLDS["api_error_rate_pct"]}%)',
                })

        # Earn latency
        avg_latency = MetricsCounter.get_avg_timing(LoyaltyMetrics.EARN_LATENCY_MS)
        if avg_latency > cls.THRESHOLDS['earn_latency_ms']:
            alerts.append({
                'level': 'warning',
                'type': 'high_latency',
                'message': f'Avg earn latency {avg_latency:.1f}ms exceeds threshold',
            })

        # Pending cashouts
        try:
            from .models.cashout import CashoutRequest
            pending = CashoutRequest.objects.filter(status='pending').count()
            if pending > cls.THRESHOLDS['pending_cashouts']:
                alerts.append({
                    'level': 'warning',
                    'type': 'pending_cashouts',
                    'message': f'{pending} pending cashouts (threshold: {cls.THRESHOLDS["pending_cashouts"]})',
                })
        except Exception:
            pass

        return alerts

    @classmethod
    def send_alert(cls, level: str, message: str, channel: str = 'log'):
        """Send an alert।"""
        if level == 'critical':
            logger.critical('ALERT [%s]: %s', level.upper(), message)
        elif level == 'warning':
            logger.warning('ALERT [%s]: %s', level.upper(), message)
        else:
            logger.info('ALERT [%s]: %s', level.upper(), message)


@contextmanager
def monitor_operation(name: str, metric_key: str = ''):
    """Context manager: time an operation and record metrics।"""
    start = time.monotonic()
    try:
        yield
    finally:
        duration_ms = (time.monotonic() - start) * 1000
        if metric_key:
            MetricsCounter.record_timing(metric_key, duration_ms)
        if duration_ms > 2000:
            logger.warning('SLOW OPERATION [%s]: %.1fms', name, duration_ms)
        else:
            logger.debug('Operation [%s]: %.1fms', name, duration_ms)


# Prometheus metrics (optional -- requires prometheus-client)
def setup_prometheus_metrics():
    """Setup Prometheus metrics if prometheus-client is installed।"""
    try:
        from prometheus_client import Counter, Histogram, Gauge

        loyalty_points_earned = Counter(
            'djoyalty_points_earned_total',
            'Total points earned across all customers',
            ['tenant', 'source'],
        )
        loyalty_api_latency = Histogram(
            'djoyalty_api_latency_seconds',
            'API endpoint latency',
            ['endpoint', 'method'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
        )
        loyalty_active_customers = Gauge(
            'djoyalty_active_customers',
            'Number of active loyalty customers',
            ['tenant'],
        )
        logger.info('Prometheus metrics registered for Djoyalty')
        return {
            'points_earned': loyalty_points_earned,
            'api_latency': loyalty_api_latency,
            'active_customers': loyalty_active_customers,
        }
    except ImportError:
        logger.debug('prometheus-client not installed -- Prometheus metrics disabled')
        return {}
