# api/admin_panel/ab_test_manager.py
"""A/B test management for offers, creatives, landing pages."""
from __future__ import annotations
import hashlib
import logging
from typing import Any, Dict, List, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class ABTestManager:
    """Admin control for A/B tests."""

    @classmethod
    def create_test(cls, name: str, variants: List[Dict], traffic_split: List[int],
                    actor=None) -> Dict:
        """Create a new A/B test."""
        if len(variants) != len(traffic_split):
            return {'success': False, 'error': 'variants and traffic_split must match'}
        if sum(traffic_split) != 100:
            return {'success': False, 'error': 'traffic_split must sum to 100'}
        try:
            from api.ai_engine.models import ABTestExperiment
            exp = ABTestExperiment.objects.create(
                name=name, variants=variants, traffic_split=traffic_split,
                status='running', started_at=timezone.now(),
            )
            if actor:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=actor, action='create_ab_test',
                                  model_name='ABTestExperiment', object_id=str(exp.pk),
                                  changes={'name': name, 'variants': len(variants)})
            return {'success': True, 'test_id': exp.pk, 'name': name}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def assign_variant(cls, test_id: Any, user_id: Any) -> Optional[str]:
        """Deterministically assign user to a variant."""
        cache_key = f'ab_test:{test_id}:{user_id}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            from api.ai_engine.models import ABTestExperiment
            exp = ABTestExperiment.objects.get(pk=test_id, status='running')
            bucket = int(hashlib.md5(f"{test_id}:{user_id}".encode()).hexdigest()[:8], 16) % 100
            cumulative = 0
            variants = exp.variants or []
            splits = exp.traffic_split or []
            for variant, split in zip(variants, splits):
                cumulative += split
                if bucket < cumulative:
                    variant_name = variant.get('name', str(variant))
                    cache.set(cache_key, variant_name, 3600)
                    return variant_name
        except Exception:
            pass
        return None

    @classmethod
    def get_test_results(cls, test_id: Any) -> Dict:
        """Get A/B test results and statistical significance."""
        try:
            from api.ai_engine.models import ABTestExperiment
            exp = ABTestExperiment.objects.get(pk=test_id)
            return {
                'test_id': test_id, 'name': exp.name,
                'status': exp.status, 'started_at': str(exp.started_at),
                'variants': exp.variants or [],
            }
        except Exception as e:
            return {'test_id': test_id, 'error': str(e)}

    @classmethod
    def stop_test(cls, test_id: Any, winner: str, actor=None) -> bool:
        try:
            from api.ai_engine.models import ABTestExperiment
            ABTestExperiment.objects.filter(pk=test_id).update(
                status='completed', winner=winner, ended_at=timezone.now()
            )
            return True
        except Exception:
            return False

    @classmethod
    def list_active_tests(cls) -> List[Dict]:
        try:
            from api.ai_engine.models import ABTestExperiment
            return list(ABTestExperiment.objects.filter(status='running').values(
                'id', 'name', 'status', 'started_at'
            )[:50])
        except Exception:
            return []


ab_test_manager = ABTestManager()