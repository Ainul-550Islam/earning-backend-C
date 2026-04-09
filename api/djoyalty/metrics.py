# api/djoyalty/metrics.py
"""
Metrics collection for Djoyalty।
Prometheus / StatsD integration।
Celery task এ ব্যবহার করুন।
"""
import logging
import time
from contextlib import contextmanager
from functools import wraps

logger = logging.getLogger('djoyalty.metrics')

# Try to import prometheus_client — optional dependency
try:
    from prometheus_client import Counter, Histogram, Gauge, Summary
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


if PROMETHEUS_AVAILABLE:
    # ==================== COUNTERS ====================
    POINTS_EARNED_TOTAL = Counter(
        'djoyalty_points_earned_total',
        'Total points earned',
        ['tenant_id', 'source', 'tier'],
    )
    POINTS_REDEEMED_TOTAL = Counter(
        'djoyalty_points_redeemed_total',
        'Total points redeemed',
        ['tenant_id', 'redemption_type'],
    )
    POINTS_EXPIRED_TOTAL = Counter(
        'djoyalty_points_expired_total',
        'Total points expired',
        ['tenant_id'],
    )
    TIER_CHANGES_TOTAL = Counter(
        'djoyalty_tier_changes_total',
        'Total tier changes',
        ['tenant_id', 'change_type', 'from_tier', 'to_tier'],
    )
    BADGES_AWARDED_TOTAL = Counter(
        'djoyalty_badges_awarded_total',
        'Total badges awarded',
        ['tenant_id', 'trigger'],
    )
    VOUCHERS_GENERATED_TOTAL = Counter(
        'djoyalty_vouchers_generated_total',
        'Total vouchers generated',
        ['tenant_id', 'voucher_type'],
    )
    FRAUD_FLAGS_TOTAL = Counter(
        'djoyalty_fraud_flags_total',
        'Total fraud flags raised',
        ['tenant_id', 'risk_level'],
    )
    API_REQUESTS_TOTAL = Counter(
        'djoyalty_api_requests_total',
        'Total API requests',
        ['endpoint', 'method', 'status'],
    )

    # ==================== GAUGES ====================
    ACTIVE_CUSTOMERS = Gauge(
        'djoyalty_active_customers',
        'Number of active customers',
        ['tenant_id'],
    )
    TOTAL_POINTS_OUTSTANDING = Gauge(
        'djoyalty_points_outstanding',
        'Total points balance across all customers',
        ['tenant_id'],
    )
    PENDING_REDEMPTIONS = Gauge(
        'djoyalty_pending_redemptions',
        'Number of pending redemption requests',
        ['tenant_id'],
    )

    # ==================== HISTOGRAMS ====================
    POINTS_EARN_DURATION = Histogram(
        'djoyalty_points_earn_duration_seconds',
        'Time to process a points earn',
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    )
    API_RESPONSE_TIME = Histogram(
        'djoyalty_api_response_time_seconds',
        'API response time',
        ['endpoint'],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
    )


class DjoyaltyMetrics:
    """Metrics facade — Prometheus বা fallback logging।"""

    @staticmethod
    def record_points_earned(points, tenant_id=None, source='purchase', tier='bronze'):
        if PROMETHEUS_AVAILABLE:
            POINTS_EARNED_TOTAL.labels(
                tenant_id=str(tenant_id or 0), source=source, tier=tier
            ).inc(float(points))
        logger.debug('METRIC points_earned amount=%s source=%s tier=%s', points, source, tier)

    @staticmethod
    def record_points_redeemed(points, tenant_id=None, redemption_type='cashback'):
        if PROMETHEUS_AVAILABLE:
            POINTS_REDEEMED_TOTAL.labels(
                tenant_id=str(tenant_id or 0), redemption_type=redemption_type
            ).inc(float(points))
        logger.debug('METRIC points_redeemed amount=%s type=%s', points, redemption_type)

    @staticmethod
    def record_tier_change(tenant_id=None, change_type='upgrade', from_tier='bronze', to_tier='silver'):
        if PROMETHEUS_AVAILABLE:
            TIER_CHANGES_TOTAL.labels(
                tenant_id=str(tenant_id or 0),
                change_type=change_type,
                from_tier=from_tier,
                to_tier=to_tier,
            ).inc()
        logger.info('METRIC tier_change %s → %s (%s)', from_tier, to_tier, change_type)

    @staticmethod
    def record_fraud_flag(risk_level='medium', tenant_id=None):
        if PROMETHEUS_AVAILABLE:
            FRAUD_FLAGS_TOTAL.labels(
                tenant_id=str(tenant_id or 0), risk_level=risk_level
            ).inc()
        logger.warning('METRIC fraud_flag risk=%s', risk_level)

    @staticmethod
    def record_badge_awarded(trigger='transaction_count', tenant_id=None):
        if PROMETHEUS_AVAILABLE:
            BADGES_AWARDED_TOTAL.labels(
                tenant_id=str(tenant_id or 0), trigger=trigger
            ).inc()

    @staticmethod
    @contextmanager
    def time_earn():
        """Context manager for timing earn operations।"""
        start = time.monotonic()
        yield
        duration = time.monotonic() - start
        if PROMETHEUS_AVAILABLE:
            POINTS_EARN_DURATION.observe(duration)
        if duration > 0.5:
            logger.warning('METRIC slow_earn duration=%.3fs', duration)


def track_metric(metric_name: str):
    """Decorator for tracking function call metrics।"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            try:
                result = func(*args, **kwargs)
                duration = time.monotonic() - start
                logger.debug('METRIC %s duration=%.3fs status=ok', metric_name, duration)
                return result
            except Exception as e:
                duration = time.monotonic() - start
                logger.warning('METRIC %s duration=%.3fs status=error error=%s', metric_name, duration, type(e).__name__)
                raise
        return wrapper
    return decorator
