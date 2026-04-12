"""
api/ai_engine/ML_MODELS/model_monitor.py
=========================================
Model Monitor — production model health monitoring।
Accuracy tracking, latency SLA, anomaly detection।
Auto-alert on performance degradation।
"""
import logging
from typing import Dict, List
from datetime import timedelta
from django.utils import timezone
logger = logging.getLogger(__name__)

class ModelMonitor:
    """Production ML model performance monitor।"""

    def __init__(self, ai_model_id: str):
        self.ai_model_id = ai_model_id

    def full_health_check(self) -> Dict:
        accuracy = self.get_accuracy_stats(days=7)
        latency  = self.check_latency_sla()
        volume   = self.check_prediction_volume()
        drift    = self.check_data_drift()
        scores   = [accuracy.get('score',1), latency.get('score',1), volume.get('score',1), drift.get('score',1)]
        health_score = sum(scores)/len(scores)
        health   = 'healthy' if health_score >= 0.80 else 'degraded' if health_score >= 0.50 else 'unhealthy'
        all_alerts = accuracy.get('alerts',[]) + latency.get('alerts',[]) + drift.get('alerts',[])
        return {
            'ai_model_id': self.ai_model_id,
            'health':      health,
            'health_score': round(health_score, 3),
            'accuracy':    accuracy,
            'latency':     latency,
            'volume':      volume,
            'drift':       drift,
            'alerts':      all_alerts,
            'action':      self._recommended_action(health, all_alerts),
            'checked_at':  str(timezone.now()),
        }

    def get_accuracy_stats(self, days: int = 7) -> Dict:
        try:
            from ..repository import PredictionLogRepository
            stats = PredictionLogRepository.get_accuracy_stats(self.ai_model_id, days)
            acc   = stats.get('accuracy', 0)
            score = max(0.0, (acc - 0.50) / 0.50)
            alerts = []
            if acc < 0.60 and stats.get('total', 0) >= 50: alerts.append(f'CRITICAL: Accuracy={acc:.1%}')
            elif acc < 0.70 and stats.get('total', 0) >= 50: alerts.append(f'WARNING: Accuracy={acc:.1%}')
            return {'accuracy': acc, 'sample': stats.get('total',0), 'score': round(score,3), 'alerts': alerts}
        except Exception as e:
            return {'error': str(e), 'score': 0.5, 'alerts': []}

    def check_latency_sla(self, threshold_ms: float = 200) -> Dict:
        try:
            from ..models import PredictionLog
            from django.db.models import Avg, Percentile
            since  = timezone.now() - timedelta(hours=1)
            qs     = PredictionLog.objects.filter(ai_model_id=self.ai_model_id, created_at__gte=since)
            result = qs.aggregate(avg_ms=Avg('inference_ms'))
            avg_ms = round(result.get('avg_ms') or 0, 2)
            score  = max(0.0, 1.0 - avg_ms/1000)
            alerts = [f'High latency: {avg_ms:.0f}ms > {threshold_ms}ms'] if avg_ms > threshold_ms else []
            return {'avg_ms': avg_ms, 'threshold_ms': threshold_ms, 'within_sla': avg_ms <= threshold_ms, 'score': round(score,3), 'alerts': alerts}
        except Exception:
            return {'score': 0.8, 'alerts': []}

    def check_prediction_volume(self, min_daily: int = 10) -> Dict:
        try:
            from ..models import PredictionLog
            since = timezone.now() - timedelta(hours=24)
            count = PredictionLog.objects.filter(ai_model_id=self.ai_model_id, created_at__gte=since).count()
            score = min(1.0, count/max(min_daily,1))
            alerts = [f'Low prediction volume: {count}/24h'] if count < min_daily else []
            return {'predictions_24h': count, 'score': round(score,3), 'alerts': alerts}
        except Exception:
            return {'score': 0.8, 'alerts': []}

    def check_data_drift(self) -> Dict:
        try:
            from ..repository import DriftRepository
            latest = DriftRepository.get_latest(self.ai_model_id)
            if not latest: return {'score': 1.0, 'status': 'no_data', 'alerts': []}
            score  = 1.0 if latest.status=='normal' else 0.5 if latest.status=='warning' else 0.2
            alerts = [f'Data drift: {latest.status} PSI={latest.psi_score:.3f}'] if latest.status != 'normal' else []
            return {'status': latest.status, 'psi': latest.psi_score, 'score': score, 'alerts': alerts}
        except Exception:
            return {'score': 0.8, 'alerts': []}

    def _recommended_action(self, health: str, alerts: List[str]) -> str:
        if health == 'unhealthy':
            if any('Accuracy' in a for a in alerts): return 'Retrain model — accuracy critically low'
            return 'Immediate investigation required'
        if health == 'degraded':
            if any('drift' in a.lower() for a in alerts): return 'Schedule retraining — data drift detected'
            if any('latency' in a.lower() for a in alerts): return 'Optimize inference server'
        return 'Monitor — all systems operational'
