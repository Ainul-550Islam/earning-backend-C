"""
tasks/repository.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Repository classes that encapsulate database query logic
for task modules (offer inventory, analytics, ML drift).
Follows the Repository pattern — no business logic here.
"""

import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone
from django.db.models import Avg, Count, Sum, Q
from django.apps import apps

logger = logging.getLogger(__name__)


def _get_model(app_label: str, model_name: str):
    """Lazy model loader to avoid circular imports at module level."""
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        logger.warning(f"Model {app_label}.{model_name} not found.")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# OFFER REPOSITORY
# ══════════════════════════════════════════════════════════════════════════════

class OfferRepository:
    """
    Data-access layer for offer inventory queries.
    Used by offer_inventory_tasks.py.
    """

    @staticmethod
    def get_active_offers(tenant_id: Optional[Any] = None):
        """Return active offers, optionally filtered by tenant."""
        Offer = _get_model('offers', 'Offer')
        if Offer is None:
            return []
        qs = Offer.objects.filter(is_active=True)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return qs.select_related('category').order_by('-created_at')

    @staticmethod
    def get_offers_by_ids(offer_ids: List[Any]):
        Offer = _get_model('offers', 'Offer')
        if Offer is None:
            return []
        return Offer.objects.filter(id__in=offer_ids)

    @staticmethod
    def get_low_performing_offers(epc_threshold: float = 0.01, min_clicks: int = 100):
        Offer = _get_model('offers', 'Offer')
        if Offer is None:
            return []
        return Offer.objects.filter(
            is_active=True,
            click_count__gte=min_clicks,
            epc__lt=epc_threshold,
        )

    @staticmethod
    def get_offers_near_cap(cap_pct: float = 0.9):
        """Return offers that have consumed >= cap_pct of their daily cap."""
        Offer = _get_model('offers', 'Offer')
        if Offer is None:
            return []
        from django.db.models import F, ExpressionWrapper, FloatField
        return Offer.objects.filter(
            is_active=True,
            daily_cap__gt=0,
        ).annotate(
            cap_ratio=ExpressionWrapper(
                F('daily_conversions') * 1.0 / F('daily_cap'),
                output_field=FloatField(),
            )
        ).filter(cap_ratio__gte=cap_pct)

    @staticmethod
    def update_offer_stats(offer_id: Any, **kwargs) -> bool:
        Offer = _get_model('offers', 'Offer')
        if Offer is None:
            return False
        updated = Offer.objects.filter(id=offer_id).update(**kwargs)
        return updated > 0

    @staticmethod
    def get_due_schedules():
        """Return offer schedules that are due to fire."""
        Schedule = _get_model('offers', 'OfferSchedule')
        if Schedule is None:
            return []
        now = timezone.now()
        return Schedule.objects.filter(
            is_active=True,
            next_run__lte=now,
        ).select_related('offer')


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS REPOSITORY
# ══════════════════════════════════════════════════════════════════════════════

class AnalyticsRepository:
    """
    Data-access layer for analytics queries.
    Used by offer_inventory_tasks.py for performance data.
    """

    @staticmethod
    def get_offer_performance(offer_id: Any, days: int = 7) -> Dict:
        since = timezone.now() - timezone.timedelta(days=days)
        ClickLog = _get_model('tasks', 'ClickLog')
        result: Dict = {
            'clicks': 0,
            'conversions': 0,
            'revenue': 0,
            'epc': 0.0,
            'cvr': 0.0,
        }
        if ClickLog is None:
            return result
        try:
            agg = ClickLog.objects.filter(
                offer_id=offer_id,
                created_at__gte=since,
            ).aggregate(
                clicks=Count('id'),
                revenue=Sum('payout'),
            )
            result['clicks'] = agg.get('clicks') or 0
            result['revenue'] = float(agg.get('revenue') or 0)
            if result['clicks'] > 0:
                result['epc'] = result['revenue'] / result['clicks']
        except Exception as e:
            logger.warning(f"AnalyticsRepository.get_offer_performance error: {e}")
        return result

    @staticmethod
    def get_top_offers(limit: int = 20, days: int = 7) -> List[Dict]:
        since = timezone.now() - timezone.timedelta(days=days)
        ClickLog = _get_model('tasks', 'ClickLog')
        if ClickLog is None:
            return []
        try:
            return list(
                ClickLog.objects.filter(created_at__gte=since)
                .values('offer_id')
                .annotate(
                    clicks=Count('id'),
                    revenue=Sum('payout'),
                )
                .order_by('-revenue')[:limit]
            )
        except Exception as e:
            logger.warning(f"AnalyticsRepository.get_top_offers error: {e}")
            return []

    @staticmethod
    def get_publisher_stats(publisher_id: Any, days: int = 30) -> Dict:
        since = timezone.now() - timezone.timedelta(days=days)
        result: Dict = {'clicks': 0, 'conversions': 0, 'revenue': 0.0, 'ivt_pct': 0.0}
        ClickLog = _get_model('tasks', 'ClickLog')
        if ClickLog is None:
            return result
        try:
            agg = ClickLog.objects.filter(
                publisher_id=publisher_id,
                created_at__gte=since,
            ).aggregate(
                clicks=Count('id'),
                revenue=Sum('payout'),
                invalid=Count('id', filter=Q(is_fraud=True)),
            )
            result['clicks'] = agg.get('clicks') or 0
            result['revenue'] = float(agg.get('revenue') or 0)
            invalid = agg.get('invalid') or 0
            if result['clicks'] > 0:
                result['ivt_pct'] = (invalid / result['clicks']) * 100
        except Exception as e:
            logger.warning(f"AnalyticsRepository.get_publisher_stats error: {e}")
        return result


# ══════════════════════════════════════════════════════════════════════════════
# DRIFT REPOSITORY
# ══════════════════════════════════════════════════════════════════════════════

class DriftRepository:
    """
    Data-access layer for ML model drift detection.
    Used by ml_tasks.py to track prediction distribution shifts.
    """

    @staticmethod
    def get_recent_predictions(model_name: str, days: int = 7) -> List[Dict]:
        PredictionLog = _get_model('tasks', 'PredictionLog')
        if PredictionLog is None:
            return []
        since = timezone.now() - timezone.timedelta(days=days)
        try:
            return list(
                PredictionLog.objects.filter(
                    model_name=model_name,
                    created_at__gte=since,
                ).values('score', 'label', 'created_at')[:10000]
            )
        except Exception as e:
            logger.warning(f"DriftRepository.get_recent_predictions error: {e}")
            return []

    @staticmethod
    def get_baseline_stats(model_name: str) -> Dict:
        """Return baseline mean/std score for a model from its training window."""
        PredictionLog = _get_model('tasks', 'PredictionLog')
        if PredictionLog is None:
            return {'mean': 0.5, 'std': 0.1}
        try:
            agg = PredictionLog.objects.filter(
                model_name=model_name,
                is_baseline=True,
            ).aggregate(
                mean=Avg('score'),
            )
            return {
                'mean': float(agg.get('mean') or 0.5),
                'std': 0.1,  # simplified; extend with StdDev if needed
            }
        except Exception as e:
            logger.warning(f"DriftRepository.get_baseline_stats error: {e}")
            return {'mean': 0.5, 'std': 0.1}

    @staticmethod
    def save_drift_event(model_name: str, drift_score: float, metadata: Dict) -> bool:
        AnomalyDetectionLog = _get_model('tasks', 'AnomalyDetectionLog')
        if AnomalyDetectionLog is None:
            return False
        try:
            AnomalyDetectionLog.objects.create(
                model_name=model_name,
                drift_score=drift_score,
                metadata=metadata,
            )
            return True
        except Exception as e:
            logger.warning(f"DriftRepository.save_drift_event error: {e}")
            return False

    @staticmethod
    def get_drift_history(model_name: str, limit: int = 30) -> List[Dict]:
        AnomalyDetectionLog = _get_model('tasks', 'AnomalyDetectionLog')
        if AnomalyDetectionLog is None:
            return []
        try:
            return list(
                AnomalyDetectionLog.objects.filter(model_name=model_name)
                .order_by('-created_at')
                .values('drift_score', 'metadata', 'created_at')[:limit]
            )
        except Exception as e:
            logger.warning(f"DriftRepository.get_drift_history error: {e}")
            return []


__all__ = ['OfferRepository', 'AnalyticsRepository', 'DriftRepository']
