"""
api/ai_engine/ML_PIPELINES/feature_pipeline.py
===============================================
Feature Pipeline — feature computation, storage, retrieval।
Batch ও real-time feature engineering orchestration।
Feature freshness management ও versioning।
"""

import logging
from typing import List, Dict, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class FeaturePipeline:
    """
    End-to-end feature computation ও storage pipeline।
    Entity-level features compute করো এবং feature store এ save করো।
    """

    SUPPORTED_FEATURE_TYPES = [
        'behavioral', 'fraud', 'churn', 'ltv',
        'recommendation', 'demographic', 'temporal',
    ]

    def run_for_user(self, user_id: str, tenant_id=None,
                      feature_types: List[str] = None) -> dict:
        """Single user এর সব features compute ও store করো।"""
        from ..ML_MODELS.feature_engineering import FeatureEngineer
        from ..repository import FeatureRepository
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return {'success': False, 'error': f'User not found: {user_id}'}

        feature_types = feature_types or ['behavioral', 'fraud', 'churn']
        results = {}

        for feat_type in feature_types:
            try:
                engineer = FeatureEngineer(feature_type=feat_type)
                raw_data = self._collect_raw_data(user, feat_type)
                features = engineer.extract(raw_data)

                obj, created = FeatureRepository.upsert(
                    entity_id=str(user.id),
                    feature_type=feat_type,
                    features=features,
                    entity_type='user',
                    tenant_id=tenant_id,
                )
                results[feat_type] = {
                    'success':       True,
                    'feature_count': len(features),
                    'created':       created,
                }
            except Exception as e:
                logger.error(f"Feature pipeline error [{feat_type}] user={user_id}: {e}")
                results[feat_type] = {'success': False, 'error': str(e)}

        return {
            'user_id':     user_id,
            'results':     results,
            'success_count': sum(1 for r in results.values() if r.get('success')),
            'total':         len(results),
        }

    def _collect_raw_data(self, user, feature_type: str) -> dict:
        """User থেকে raw data collect করো।"""
        base_data = {
            'user_id':          str(user.id),
            'account_age_days': (timezone.now() - user.date_joined).days,
            'days_since_login': (timezone.now() - (user.last_login or user.date_joined)).days,
            'coin_balance':     float(getattr(user, 'coin_balance', 0)),
            'total_earned':     float(getattr(user, 'total_earned', 0)),
            'country':          getattr(user, 'country', 'BD'),
            'language':         getattr(user, 'language', 'bn'),
        }

        if feature_type == 'fraud':
            base_data.update({
                'device_count':   getattr(user, 'device_count', 1),
                'is_verified':    getattr(user, 'is_verified', False),
            })
        elif feature_type == 'churn':
            base_data.update({
                'streak_days':    0,
                'referral_count': 0,
            })

        return base_data

    def run_batch(self, user_ids: List[str], tenant_id=None,
                   feature_types: List[str] = None,
                   batch_size: int = 256) -> dict:
        """Batch users এর features compute করো।"""
        from ..utils import chunk_list

        total   = len(user_ids)
        success = 0
        failed  = 0
        batches = chunk_list(user_ids, batch_size)

        for batch_num, batch in enumerate(batches, 1):
            logger.info(f"Feature pipeline batch {batch_num}/{len(batches)} ({len(batch)} users)")
            for uid in batch:
                result = self.run_for_user(uid, tenant_id, feature_types)
                if result.get('success_count', 0) > 0:
                    success += 1
                else:
                    failed += 1

        return {
            'total':   total,
            'success': success,
            'failed':  failed,
            'batches': len(batches),
        }

    def check_feature_freshness(self, entity_id: str,
                                  feature_type: str,
                                  max_age_hours: int = 24) -> dict:
        """Feature data fresh কিনা check করো।"""
        from ..repository import FeatureRepository
        store = FeatureRepository.get_features(entity_id, feature_type)

        if not store:
            return {'fresh': False, 'reason': 'No features found', 'needs_refresh': True}

        age_hours = (timezone.now() - store.created_at).total_seconds() / 3600
        is_fresh  = age_hours <= max_age_hours

        return {
            'fresh':        is_fresh,
            'age_hours':    round(age_hours, 2),
            'max_age_hours': max_age_hours,
            'needs_refresh': not is_fresh,
            'last_updated': str(store.created_at),
        }

    def auto_refresh_stale_features(self, tenant_id=None,
                                     max_age_hours: int = 24) -> dict:
        """Stale features auto-refresh করো।"""
        from ..models import FeatureStore
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(hours=max_age_hours)
        stale  = FeatureStore.objects.filter(
            updated_at__lt=cutoff,
            is_active=True,
        )
        if tenant_id:
            stale = stale.filter(tenant_id=tenant_id)

        stale_list    = list(stale.values('entity_id', 'feature_type').distinct()[:500])
        refreshed     = 0

        for item in stale_list:
            result = self.run_for_user(item['entity_id'], tenant_id, [item['feature_type']])
            if result.get('success_count', 0) > 0:
                refreshed += 1

        return {
            'stale_found':  len(stale_list),
            'refreshed':    refreshed,
            'cutoff_hours': max_age_hours,
        }

    def get_pipeline_stats(self, tenant_id=None) -> dict:
        """Feature pipeline stats।"""
        from ..models import FeatureStore
        from django.db.models import Count, Avg
        from datetime import timedelta

        qs = FeatureStore.objects.filter(is_active=True)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        by_type  = qs.values('feature_type').annotate(count=Count('id'))
        cutoff   = timezone.now() - timedelta(hours=24)
        fresh    = qs.filter(updated_at__gte=cutoff).count()
        stale    = qs.filter(updated_at__lt=cutoff).count()

        return {
            'total_records':     qs.count(),
            'fresh_24h':         fresh,
            'stale_24h':         stale,
            'freshness_rate':    round(fresh / max(qs.count(), 1), 4),
            'by_type':           list(by_type),
        }
