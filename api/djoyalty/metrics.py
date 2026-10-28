# api/djoyalty/metrics.py
"""
Djoyalty -- metrics & instrumentation।
Prometheus/StatsD বা simple logging-based metrics।
Production এ prometheus_client বা statsd দিয়ে replace করুন।
"""
import logging
import time
from contextlib import contextmanager
from decimal import Decimal

logger = logging.getLogger(__name__)


class DjoyaltyMetrics:
    """
    Simple metrics recorder।
    In production -- replace with Prometheus/StatsD।
    """

    @staticmethod
    @contextmanager
    def time_earn():
        """
        Points earn operation timing।
        Usage: with DjoyaltyMetrics.time_earn(): ...
        """
        start = time.monotonic()
        try:
            yield
        finally:
            elapsed = time.monotonic() - start
            if elapsed > 1.0:
                logger.warning('[djoyalty_metrics] slow_earn duration=%.3fs', elapsed)
            else:
                logger.debug('[djoyalty_metrics] earn duration=%.3fs', elapsed)

    @staticmethod
    def record_points_earned(
        points: Decimal,
        tenant_id=None,
        source: str = 'purchase',
        tier: str = 'bronze',
    ):
        """
        Points earn event record করো।
        """
        logger.debug(
            '[djoyalty_metrics] points_earned points=%s tenant=%s source=%s tier=%s',
            points, tenant_id, source, tier,
        )

    @staticmethod
    def record_redemption(points: Decimal, tenant_id=None, redemption_type: str = 'cashback'):
        """Redemption event record করো।"""
        logger.debug(
            '[djoyalty_metrics] redemption points=%s tenant=%s type=%s',
            points, tenant_id, redemption_type,
        )

    @staticmethod
    def record_tier_change(from_tier: str, to_tier: str, change_type: str, tenant_id=None):
        """Tier change event record করো।"""
        logger.info(
            '[djoyalty_metrics] tier_change from=%s to=%s type=%s tenant=%s',
            from_tier, to_tier, change_type, tenant_id,
        )

    @staticmethod
    def record_fraud_detected(risk_level: str, action: str, tenant_id=None):
        """Fraud detection event record করো।"""
        logger.warning(
            '[djoyalty_metrics] fraud_detected risk=%s action=%s tenant=%s',
            risk_level, action, tenant_id,
        )

    @staticmethod
    def record_api_error(endpoint: str, error_type: str):
        """API error record করো।"""
        logger.error(
            '[djoyalty_metrics] api_error endpoint=%s error=%s',
            endpoint, error_type,
        )

    @staticmethod
    def increment_counter(name: str, value: int = 1, labels: dict = None):
        """Generic counter increment।"""
        label_str = ', '.join(f'{k}={v}' for k, v in (labels or {}).items())
        logger.debug('[djoyalty_metrics] counter %s +%d {%s}', name, value, label_str)

    @staticmethod
    def record_gauge(name: str, value, labels: dict = None):
        """Generic gauge record।"""
        label_str = ', '.join(f'{k}={v}' for k, v in (labels or {}).items())
        logger.debug('[djoyalty_metrics] gauge %s = %s {%s}', name, value, label_str)
