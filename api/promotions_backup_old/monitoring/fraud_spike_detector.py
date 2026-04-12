# api/promotions/monitoring/fraud_spike_detector.py
# Fraud Spike Detector — Real-time fraud pattern anomaly detection
import logging
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone
logger = logging.getLogger('monitoring.fraud_spike')

class FraudSpikeDetector:
    """
    Real-time fraud spike detection.
    Z-score based anomaly detection on fraud submission rate.
    Alert when current rate > 3σ above baseline.
    """
    BASELINE_WINDOW_HOURS = 168   # 7 days baseline
    SPIKE_THRESHOLD_ZSCORE = 2.5

    def check_for_spike(self) -> dict:
        """Current fraud rate spike check করে।"""
        from api.promotions.models import TaskSubmission, FraudReport
        from django.db.models import Count

        now    = timezone.now()
        hour_ago = now - timedelta(hours=1)
        recent_fraud = FraudReport.objects.filter(created_at__gte=hour_ago).count()
        recent_total = TaskSubmission.objects.filter(submitted_at__gte=hour_ago).count()
        current_rate = recent_fraud / max(recent_total, 1)

        baseline = self._get_baseline()
        if not baseline or baseline['std'] == 0:
            self._update_baseline(current_rate)
            return {'spike': False, 'rate': current_rate, 'baseline': None}

        z_score = (current_rate - baseline['mean']) / baseline['std']
        is_spike = z_score > self.SPIKE_THRESHOLD_ZSCORE

        if is_spike:
            logger.critical(f'FRAUD SPIKE: rate={current_rate:.3f} z={z_score:.2f} baseline={baseline["mean"]:.3f}')
            self._trigger_alert(current_rate, z_score, recent_fraud)

        self._update_baseline(current_rate)
        return {'spike': is_spike, 'rate': round(current_rate, 4), 'z_score': round(z_score, 2), 'fraud_count': recent_fraud}

    def _get_baseline(self) -> dict | None:
        return cache.get('monitor:fraud:baseline')

    def _update_baseline(self, current_rate: float):
        baseline = cache.get('monitor:fraud:baseline') or {'rates': [], 'mean': 0.0, 'std': 0.01}
        rates    = baseline['rates'] + [current_rate]
        rates    = rates[-168:]  # 7 days of hourly data
        import statistics
        mean = statistics.mean(rates) if rates else 0.0
        std  = statistics.stdev(rates) if len(rates) > 1 else 0.01
        cache.set('monitor:fraud:baseline', {'rates': rates, 'mean': mean, 'std': std}, timeout=86400*7)

    def _trigger_alert(self, rate: float, z_score: float, count: int):
        try:
            from .alert_system import AlertSystem, AlertSeverity
            AlertSystem().send_fraud_alert(0, 0, {'score': z_score/10, 'type': f'fraud_spike rate={rate:.3f} count={count}'})
        except Exception: pass
