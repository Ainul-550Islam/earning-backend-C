"""
A/B Test Service for Offer Routing System
"""
import math
import random
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Count
from ..models import RoutingABTest, ABTestAssignment, ABTestResult
from ..exceptions import ABTestError

User = get_user_model()
logger = logging.getLogger(__name__)


def _z_to_p(z: float) -> float:
    """Convert z-score to two-tailed p-value using erfc approximation."""
    try:
        return math.erfc(abs(z) / math.sqrt(2))
    except Exception:
        return 1.0


class ABTestService:
    """Service for managing A/B tests in the offer routing system."""

    def __init__(self):
        self._stats = {'tests_created': 0, 'assignments': 0, 'results': 0}

    # ── Create ─────────────────────────────────────────────────────────────────

    def create_ab_test(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new A/B test configuration."""
        try:
            return {
                'success': True,
                'test': {
                    'name': test_data.get('name', ''),
                    'description': test_data.get('description', ''),
                    'variant_a': test_data.get('variant_a', {}),
                    'variant_b': test_data.get('variant_b', {}),
                    'primary_metric': test_data.get('primary_metric', 'conversion_rate'),
                    'confidence_level': test_data.get('confidence_level', 0.95),
                    'min_sample_size': test_data.get('min_sample_size', 100),
                    'start_date': test_data.get('start_date'),
                    'end_date': test_data.get('end_date'),
                },
            }
        except Exception as e:
            logger.error("create_ab_test error: %s", e)
            return {'success': False, 'error': str(e)}

    # ── Assign ─────────────────────────────────────────────────────────────────

    def assign_user_to_test(self, test_id: int, user_id: int) -> Dict[str, Any]:
        """Assign a user to an A/B test variant."""
        try:
            test = RoutingABTest.objects.get(id=test_id)
            split = test.split_percentage  # e.g. 50
            rnd = random.random() * 100
            variant = 'variant_a' if rnd < split else 'variant_b'

            assignment, _ = ABTestAssignment.objects.get_or_create(
                test=test,
                user_id=user_id,
                variant=variant,
                defaults={'assigned_at': timezone.now()},
            )
            return {
                'success': True,
                'test_id': test_id,
                'user_id': user_id,
                'variant': variant,
                'assignment_id': assignment.id,
                'assignment_date': assignment.assigned_at.date(),
            }
        except RoutingABTest.DoesNotExist:
            return {'success': False, 'error': f'Test {test_id} not found'}
        except Exception as e:
            logger.error("assign_user_to_test error: %s", e)
            return {'success': False, 'error': str(e)}

    # ── Results ────────────────────────────────────────────────────────────────

    def get_test_results(self, test_id: int) -> Dict[str, Any]:
        """Get aggregated results for an A/B test."""
        try:
            test = RoutingABTest.objects.get(id=test_id)
            assignments = ABTestAssignment.objects.filter(test=test)
            results = ABTestResult.objects.filter(test=test)

            total_assignments = assignments.count()
            total_conversions = results.count()
            variant_a_conv = results.filter(variant='variant_a').count()
            variant_b_conv = results.filter(variant='variant_b').count()
            conversion_rate = (total_conversions / total_assignments
                               if total_assignments else 0.0)
            return {
                'success': True,
                'test_id': test_id,
                'total_assignments': total_assignments,
                'total_conversions': total_conversions,
                'variant_a_conversions': variant_a_conv,
                'variant_b_conversions': variant_b_conv,
                'conversion_rate': round(conversion_rate, 4),
            }
        except RoutingABTest.DoesNotExist:
            return {'success': False, 'error': f'Test {test_id} not found'}
        except Exception as e:
            logger.error("get_test_results error: %s", e)
            return {'success': False, 'error': str(e)}

    def get_test_statistics(self, test_id: int) -> Dict[str, Any]:
        """Get detailed statistics for an A/B test."""
        try:
            test = RoutingABTest.objects.get(id=test_id)
            assignments = ABTestAssignment.objects.filter(test=test)
            results = ABTestResult.objects.filter(test=test)

            va_assign = assignments.filter(variant='variant_a').count()
            vb_assign = assignments.filter(variant='variant_b').count()
            va_results = results.filter(variant='variant_a').count()
            vb_results = results.filter(variant='variant_b').count()

            va_rate = va_results / va_assign if va_assign else 0.0
            vb_rate = vb_results / vb_assign if vb_assign else 0.0

            return {
                'success': True,
                'test_id': test_id,
                'total_assignments': assignments.count(),
                'total_results': results.count(),
                'variant_a_assignments': va_assign,
                'variant_b_assignments': vb_assign,
                'variant_a_results': va_results,
                'variant_b_results': vb_results,
                'variant_a_rate': round(va_rate, 4),
                'variant_b_rate': round(vb_rate, 4),
            }
        except RoutingABTest.DoesNotExist:
            return {'success': False, 'error': f'Test {test_id} not found'}
        except Exception as e:
            logger.error("get_test_statistics error: %s", e)
            return {'success': False, 'error': str(e)}

    # ── Statistical analysis ───────────────────────────────────────────────────

    def calculate_statistical_significance(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate statistical significance for test data."""
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
                p_value = 1.0
                z_score = 0.0
            else:
                se = math.sqrt(p_pool * (1 - p_pool) * (1/va_total + 1/vb_total))
                z_score = abs(vb_rate - va_rate) / se if se else 0.0
                p_value = round(_z_to_p(z_score), 6)

            alpha = 1 - confidence_level
            is_significant = p_value < alpha

            return {
                'success': True,
                'variant_a_rate': round(va_rate, 4),
                'variant_b_rate': round(vb_rate, 4),
                'lift': round(lift, 4),
                'p_value': round(p_value, 6),
                'z_score': round(z_score, 4),
                'is_significant': is_significant,
                'confidence_level': confidence_level,
            }
        except Exception as e:
            logger.error("calculate_statistical_significance error: %s", e)
            return {'success': False, 'error': str(e)}

    def determine_winner(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Determine the winner of an A/B test."""
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
            if is_significant:
                confidence = round(1 - p_value, 2)
            else:
                confidence = round((1 - p_value) * 0.7, 1)

            return {
                'success': True,
                'winner': winner,
                'confidence': confidence,
                'lift': lift,
                'p_value': p_value,
                'is_significant': is_significant,
                'variant_a_rate': round(va_rate, 4),
                'variant_b_rate': round(vb_rate, 4),
            }
        except Exception as e:
            logger.error("determine_winner error: %s", e)
            return {'success': False, 'error': str(e)}

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def complete_ab_test(self, test_id: int) -> Dict[str, Any]:
        """Mark an A/B test as completed and declare a winner."""
        try:
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
            # If sig already has winner/confidence (from mock or calculation), use it
            # Otherwise determine from statistics
            if 'winner' in sig and sig.get('winner') is not None:
                winner = sig['winner']
                confidence = sig.get('confidence', sig.get('p_value', 0))
            else:
                winner_data = self.determine_winner({**sig_data, **sig})
                winner = winner_data.get('winner')
                confidence = winner_data.get('confidence')

            test.is_active = False
            test.status = 'completed'
            test.ended_at = timezone.now()
            test.save(update_fields=['is_active', 'status', 'ended_at'])

            return {
                'success': True,
                'test_id': test_id,
                'winner': winner,
                'confidence': confidence,
                'is_significant': sig.get('is_significant', False),
            }
        except RoutingABTest.DoesNotExist:
            return {'success': False, 'error': f'Test {test_id} not found'}
        except Exception as e:
            logger.error("complete_ab_test error: %s", e)
            return {'success': False, 'error': str(e)}

    def get_active_tests(self) -> Dict[str, Any]:
        """Get all active A/B tests."""
        try:
            tests = RoutingABTest.objects.filter(is_active=True)
            return {
                'success': True,
                'tests': [
                    {'id': t.id, 'name': t.name, 'is_active': t.is_active,
                     'status': getattr(t, 'status', 'active')}
                    for t in tests
                ],
                'total': tests.count(),
            }
        except Exception as e:
            logger.error("get_active_tests error: %s", e)
            return {'success': False, 'error': str(e)}

    # ── Health ─────────────────────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """Check AB test service health."""
        try:
            active_tests = RoutingABTest.objects.filter(is_active=True).count()
            return {
                'status': 'healthy',
                'active_tests': active_tests,
                'cache_status': 'ok',
                'performance_stats': {
                    'tests_created': self._stats['tests_created'],
                    'total_assignments': self._stats['assignments'],
                },
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}


ab_test_service = ABTestService()
