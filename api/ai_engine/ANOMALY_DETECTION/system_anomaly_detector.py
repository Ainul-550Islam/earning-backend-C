"""
api/ai_engine/ANOMALY_DETECTION/system_anomaly_detector.py
===========================================================
System Anomaly Detector — platform infrastructure monitoring।
API errors, latency spikes, database issues, service degradation।
Production health monitoring ও auto-alerting।
"""
import logging
from typing import List, Dict
logger = logging.getLogger(__name__)

class SystemAnomalyDetector:
    """Infrastructure ও system health anomaly detection।"""

    THRESHOLDS = {
        'error_rate_pct': 5.0, 'avg_latency_ms': 500,
        'cpu_pct': 85.0, 'memory_pct': 85.0, 'db_query_ms': 1000,
        'cache_miss_rate': 0.50, 'queue_depth': 5000,
    }

    def detect(self, metrics: dict) -> dict:
        score, flags, alerts = 0.0, [], []
        for metric, threshold in self.THRESHOLDS.items():
            value = metrics.get(metric, 0)
            if value > threshold:
                ratio = value / threshold
                contribution = min(0.40, (ratio - 1.0) * 0.20)
                score += contribution
                flags.append(f'{metric}={value:.1f} (threshold={threshold})')
                if ratio >= 2.0:
                    alerts.append(f'CRITICAL: {metric} at {value:.1f} — 2x over threshold')
                else:
                    alerts.append(f'WARNING: {metric} at {value:.1f} — above threshold')

        score = min(1.0, score)
        return {
            'anomaly_score': round(score, 4),
            'is_anomaly':    score >= 0.30,
            'severity':      'critical' if score >= 0.70 else 'high' if score >= 0.50 else 'medium' if score >= 0.30 else 'normal',
            'flags':         flags,
            'alerts':        alerts,
            'metrics':       metrics,
            'action':        self._auto_action(score, flags),
        }

    def _auto_action(self, score: float, flags: List[str]) -> str:
        if score >= 0.70: return 'IMMEDIATE: Page on-call engineer + scale infrastructure'
        if any('error_rate' in f for f in flags): return 'Check recent deployments + roll back if needed'
        if any('latency' in f for f in flags): return 'Scale inference workers + check DB indices'
        if any('memory' in f for f in flags): return 'Restart memory-heavy services + increase limits'
        if score >= 0.30: return 'Monitor closely + prepare scaling plan'
        return 'System healthy'

    def detect_api_degradation(self, endpoint_metrics: Dict[str, dict]) -> dict:
        degraded = []
        for endpoint, m in endpoint_metrics.items():
            if m.get('error_rate', 0) > 0.05 or m.get('p99_ms', 0) > 1000:
                degraded.append({'endpoint': endpoint, 'error_rate': m.get('error_rate'), 'p99_ms': m.get('p99_ms')})
        return {'degraded_endpoints': degraded, 'count': len(degraded), 'action': 'Investigate degraded endpoints' if degraded else 'All endpoints healthy'}

    def database_health(self, db_metrics: dict) -> dict:
        slow_queries = db_metrics.get('slow_query_count', 0)
        conn_pool_used = db_metrics.get('connection_pool_pct', 0)
        replication_lag = db_metrics.get('replication_lag_ms', 0)
        issues = []
        if slow_queries > 10: issues.append(f'{slow_queries} slow queries — add indices')
        if conn_pool_used > 0.90: issues.append('Connection pool near exhaustion — scale DB')
        if replication_lag > 5000: issues.append('High replication lag — check replica health')
        return {'healthy': len(issues) == 0, 'issues': issues, 'metrics': db_metrics}

    def predict_failure(self, historical_metrics: List[Dict]) -> dict:
        if len(historical_metrics) < 5: return {'prediction': 'insufficient_data'}
        error_rates = [m.get('error_rate_pct', 0) for m in historical_metrics]
        trend = (error_rates[-1] - error_rates[0]) / max(len(error_rates)-1, 1)
        projected_1h = error_rates[-1] + trend * 60
        return {
            'current_error_rate': error_rates[-1],
            'trend': 'increasing' if trend > 0 else 'decreasing' if trend < 0 else 'stable',
            'projected_1h': round(max(0, projected_1h), 4),
            'failure_likely': projected_1h > 10,
        }
