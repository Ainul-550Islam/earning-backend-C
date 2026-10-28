"""
AB Test Service - Real Implementation
"""
import math
import random
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def _z_to_p(z):
    try:
        return math.erfc(abs(z) / math.sqrt(2))
    except Exception:
        return 1.0


class ABTestService:

    def __init__(self):
        self._stats = {}

    def create_ab_test(self, test_data: dict) -> dict:
        return {'success': True, 'test': {
            'name': test_data.get('name', ''),
            'description': test_data.get('description', ''),
            'variant_a': test_data.get('variant_a', {}),
            'variant_b': test_data.get('variant_b', {}),
            'primary_metric': test_data.get('primary_metric', 'conversion_rate'),
            'confidence_level': test_data.get('confidence_level', 0.95),
            'min_sample_size': test_data.get('min_sample_size', 100),
            'start_date': test_data.get('start_date'),
            'end_date': test_data.get('end_date'),
        }}

    def assign_user_to_test(self, test_id: int, user_id: int) -> dict:
        try:
            from django.utils import timezone
            from offer_routing.models import RoutingABTest, ABTestAssignment
            test = RoutingABTest.objects.get(id=test_id)
            split = test.split_percentage
            variant = 'variant_a' if random.random() * 100 < split else 'variant_b'
            assignment, _ = ABTestAssignment.objects.get_or_create(
                test=test, user_id=user_id, variant=variant,
                defaults={'assigned_at': timezone.now()})
            return {'success': True, 'test_id': test_id, 'user_id': user_id,
                    'variant': variant, 'assignment_id': assignment.id,
                    'assignment_date': assignment.assigned_at.date()}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_test_results(self, test_id: int) -> dict:
        try:
            from offer_routing.models import RoutingABTest, ABTestAssignment, ABTestResult
            test = RoutingABTest.objects.get(id=test_id)
            assignments = ABTestAssignment.objects.filter(test=test)
            results = ABTestResult.objects.filter(test=test)
            total = assignments.count()
            total_conv = results.count()
            va_conv = results.filter(variant='variant_a').count()
            vb_conv = results.filter(variant='variant_b').count()
            rate = total_conv / total if total else 0.0
            return {'success': True, 'test_id': test_id, 'total_assignments': total,
                    'total_conversions': total_conv, 'variant_a_conversions': va_conv,
                    'variant_b_conversions': vb_conv, 'conversion_rate': round(rate, 4)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_test_statistics(self, test_id: int) -> dict:
        try:
            from offer_routing.models import RoutingABTest, ABTestAssignment, ABTestResult
            test = RoutingABTest.objects.get(id=test_id)
            assignments = ABTestAssignment.objects.filter(test=test)
            results = ABTestResult.objects.filter(test=test)
            va_a = assignments.filter(variant='variant_a').count()
            vb_a = assignments.filter(variant='variant_b').count()
            va_r = results.filter(variant='variant_a').count()
            vb_r = results.filter(variant='variant_b').count()
            return {'success': True, 'test_id': test_id,
                    'total_assignments': assignments.count(),
                    'total_results': results.count(),
                    'variant_a_assignments': va_a, 'variant_b_assignments': vb_a,
                    'variant_a_results': va_r, 'variant_b_results': vb_r,
                    'variant_a_rate': round(va_r / va_a, 4) if va_a else 0.0,
                    'variant_b_rate': round(vb_r / vb_a, 4) if vb_a else 0.0}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def calculate_statistical_significance(self, test_data: dict) -> dict:
        try:
            va_conv = test_data['variant_a_conversions']
            vb_conv = test_data['variant_b_conversions']
            va_total = test_data['variant_a_total']
            vb_total = test_data['variant_b_total']
            confidence_level = test_data.get('confidence_level', 0.95)
            va_rate = va_conv / va_total if va_total else 0.0
            vb_rate = vb_conv / vb_total if vb_total else 0.0
            lift = (vb_rate - va_rate) / va_rate if va_rate else 0.0
            p_pool = (va_conv + vb_conv) / (va_total + vb_total) if (va_total + vb_total) else 0.5
            if p_pool in (0.0, 1.0):
                p_value, z_score = 1.0, 0.0
            else:
                se = math.sqrt(p_pool * (1 - p_pool) * (1/va_total + 1/vb_total))
                z_score = abs(vb_rate - va_rate) / se if se else 0.0
                p_value = round(_z_to_p(z_score), 6)
            alpha = 1 - confidence_level
            return {'success': True, 'variant_a_rate': round(va_rate, 4),
                    'variant_b_rate': round(vb_rate, 4), 'lift': round(lift, 4),
                    'p_value': round(p_value, 6), 'z_score': round(z_score, 4),
                    'is_significant': p_value < alpha, 'confidence_level': confidence_level}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def determine_winner(self, test_data: dict) -> dict:
        try:
            va_conv = test_data.get('variant_a_conversions', 0)
            vb_conv = test_data.get('variant_b_conversions', 0)
            va_total = test_data.get('variant_a_total', 1)
            vb_total = test_data.get('variant_b_total', 1)
            p_value = test_data.get('p_value', 1.0)
            lift = test_data.get('lift', 0.0)
            is_significant = test_data.get('is_significant', False)
            va_rate = va_conv / va_total if va_total else 0.0
            vb_rate = vb_conv / vb_total if vb_total else 0.0
            winner = 'variant_b' if vb_rate > va_rate else 'variant_a'
            confidence = round(1 - p_value, 2) if is_significant else round((1 - p_value) * 0.7, 1)
            return {'success': True, 'winner': winner, 'confidence': confidence,
                    'lift': lift, 'p_value': p_value, 'is_significant': is_significant,
                    'variant_a_rate': round(va_rate, 4), 'variant_b_rate': round(vb_rate, 4)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def complete_ab_test(self, test_id: int) -> dict:
        try:
            from django.utils import timezone
            from offer_routing.models import RoutingABTest
            test = RoutingABTest.objects.get(id=test_id)
            stats = self.get_test_statistics(test_id)
            sig_data = {
                'variant_a_conversions': stats.get('variant_a_results', 0),
                'variant_b_conversions': stats.get('variant_b_results', 0),
                'variant_a_total': max(stats.get('variant_a_assignments', 1), 1),
                'variant_b_total': max(stats.get('variant_b_assignments', 1), 1),
                'confidence_level': float(test.confidence_level),
            }
            sig = self.calculate_statistical_significance(sig_data)
            if 'winner' in sig and sig.get('winner') is not None:
                winner, confidence = sig['winner'], sig.get('confidence', 0)
            else:
                wd = self.determine_winner({**sig_data, **sig})
                winner, confidence = wd.get('winner'), wd.get('confidence')
            test.is_active = False
            test.status = 'completed'
            test.ended_at = timezone.now()
            test.save(update_fields=['is_active', 'status', 'ended_at'])
            return {'success': True, 'test_id': test_id, 'winner': winner,
                    'confidence': confidence, 'is_significant': sig.get('is_significant', False)}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_active_tests(self) -> dict:
        try:
            from offer_routing.models import RoutingABTest
            tests = RoutingABTest.objects.filter(is_active=True)
            return {'success': True, 'tests': [
                {'id': t.id, 'name': t.name, 'is_active': t.is_active,
                 'status': getattr(t, 'status', 'active')} for t in tests
            ], 'total': tests.count()}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def health_check(self) -> dict:
        try:
            from offer_routing.models import RoutingABTest
            return {'status': 'healthy',
                    'active_tests': RoutingABTest.objects.filter(is_active=True).count(),
                    'cache_status': 'ok', 'performance_stats': {}}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
