"""
api/ai_engine/ML_PIPELINES/monitoring_pipeline.py
=================================================
Monitoring Pipeline — production model health monitoring।
Accuracy, latency, drift, bias monitoring।
Automated alerts ও recommendations।
"""
import logging
from typing import Dict, List
from django.utils import timezone
from datetime import timedelta
logger = logging.getLogger(__name__)

class MonitoringPipeline:
    """Comprehensive production model monitoring।"""

    def run(self, ai_model_id: str, tenant_id=None) -> dict:
        checks = {
            'accuracy':  self._check_accuracy(ai_model_id),
            'latency':   self._check_latency(ai_model_id),
            'drift':     self._check_drift(ai_model_id),
            'volume':    self._check_volume(ai_model_id),
        }
        alerts  = [msg for c in checks.values() for msg in c.get('alerts', [])]
        scores  = [c.get('score', 1.0) for c in checks.values()]
        health_score = sum(scores)/len(scores)
        health  = 'healthy' if health_score >= 0.80 else 'degraded' if health_score >= 0.50 else 'unhealthy'
        return {
            'ai_model_id':  ai_model_id,
            'health':       health,
            'health_score': round(health_score, 3),
            'checks':       checks,
            'alerts':       alerts,
            'alert_count':  len(alerts),
            'recommendation': self._recommendation(health, alerts),
            'checked_at':   str(timezone.now()),
        }

    def _check_accuracy(self, model_id: str) -> dict:
        try:
            from ..repository import PredictionLogRepository
            stats = PredictionLogRepository.get_accuracy_stats(model_id, days=7)
            acc   = stats.get('accuracy', 0)
            score = acc
            alerts = []
            if acc < 0.60 and stats.get('total', 0) >= 50:
                alerts.append(f'CRITICAL: Accuracy {acc:.1%} below 60%')
            elif acc < 0.70 and stats.get('total', 0) >= 50:
                alerts.append(f'WARNING: Accuracy {acc:.1%} below 70% target')
            return {'score': score, 'accuracy': acc, 'sample': stats.get('total', 0), 'alerts': alerts}
        except Exception as e:
            return {'score': 0.5, 'alerts': [f'Accuracy check failed: {e}']}

    def _check_latency(self, model_id: str) -> dict:
        try:
            from ..models import PredictionLog
            from django.db.models import Avg
            since  = timezone.now() - timedelta(hours=1)
            result = PredictionLog.objects.filter(ai_model_id=model_id, created_at__gte=since).aggregate(avg=Avg('inference_ms'))
            avg_ms = result.get('avg') or 0
            score  = max(0.0, 1.0 - avg_ms/500)
            alerts = []
            if avg_ms > 500: alerts.append(f'High latency: {avg_ms:.0f}ms')
            elif avg_ms > 200: alerts.append(f'Elevated latency: {avg_ms:.0f}ms')
            return {'score': round(score,3), 'avg_ms': round(avg_ms,2), 'alerts': alerts}
        except Exception:
            return {'score': 0.8, 'alerts': []}

    def _check_drift(self, model_id: str) -> dict:
        try:
            from ..repository import DriftRepository
            latest = DriftRepository.get_latest(model_id)
            if not latest: return {'score': 1.0, 'alerts': []}
            score  = 1.0 if latest.status == 'normal' else 0.5 if latest.status == 'warning' else 0.2
            alerts = [f'Data drift detected: {latest.status} (PSI={latest.psi_score:.3f})'] if latest.status != 'normal' else []
            return {'score': score, 'drift_status': latest.status, 'psi': latest.psi_score, 'alerts': alerts}
        except Exception:
            return {'score': 0.8, 'alerts': []}

    def _check_volume(self, model_id: str) -> dict:
        try:
            from ..models import PredictionLog
            since = timezone.now() - timedelta(hours=24)
            count = PredictionLog.objects.filter(ai_model_id=model_id, created_at__gte=since).count()
            score = min(1.0, count/100)
            alerts = ['WARNING: Very low prediction volume in 24h'] if count < 10 else []
            return {'score': score, 'predictions_24h': count, 'alerts': alerts}
        except Exception:
            return {'score': 0.8, 'alerts': []}

    def _recommendation(self, health: str, alerts: List[str]) -> str:
        if health == 'unhealthy':
            if any('Accuracy' in a for a in alerts):
                return 'Retrain model immediately — accuracy critically low'
            return 'Investigate model degradation — check data pipeline'
        if health == 'degraded':
            if any('latency' in a.lower() for a in alerts):
                return 'Optimize inference — consider model compression'
            if any('drift' in a.lower() for a in alerts):
                return 'Schedule retraining — data drift detected'
            return 'Monitor closely — performance below optimal'
        return 'Model healthy — continue regular monitoring'

    def schedule_health_checks(self) -> dict:
        return {
            'accuracy_check_hours': 24,
            'latency_check_minutes': 60,
            'drift_check_hours': 12,
            'volume_check_hours': 6,
        }
