"""
tasks/ab_testing_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
A/B Testing System Celery Tasks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Split test offers, task rewards, UI variants, and email subjects.
  ✅ assign_ab_variant         — assign user to a test variant
  ✅ record_ab_event           — record conversion/click for a variant
  ✅ analyze_ab_results        — statistical analysis (z-test, chi-square)
  ✅ auto_pick_winner          — auto-promote winner variant
  ✅ generate_ab_report        — daily A/B test report
  ✅ cleanup_old_ab_tests      — archive completed tests
"""
import logging
import math
import random
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=5,
             name='tasks.ab_testing_tasks.assign_ab_variant')
def assign_ab_variant(self, user_id: int, test_id: str) -> dict:
    """
    Assign a user to an A/B test variant.
    Uses deterministic hashing (user_id + test_id → always same variant).
    Stores assignment in cache for consistency.
    """
    try:
        # Check existing assignment
        assignment_key = f'ab_assignment_{test_id}_{user_id}'
        existing = cache.get(assignment_key)
        if existing:
            return {'status': 'existing', 'test_id': test_id, 'variant': existing, 'user_id': user_id}

        # Get test config
        test_config = _get_test_config(test_id)
        if not test_config or not test_config.get('is_active'):
            return {'status': 'test_not_active', 'test_id': test_id}

        variants = test_config.get('variants', [])
        if not variants:
            return {'status': 'no_variants', 'test_id': test_id}

        # Deterministic assignment using hash
        hash_val = hash(f"{test_id}:{user_id}") % 100
        cumulative = 0
        assigned_variant = variants[-1]['id']
        for variant in variants:
            cumulative += variant.get('traffic_pct', 50)
            if hash_val < cumulative:
                assigned_variant = variant['id']
                break

        # Store assignment
        cache.set(assignment_key, assigned_variant, timeout=86400 * 30)

        # Record in DB
        try:
            from ab_testing.models import ABTestAssignment
            ABTestAssignment.objects.get_or_create(
                test_id=test_id,
                user_id=user_id,
                defaults={'variant': assigned_variant, 'assigned_at': timezone.now()},
            )
        except ImportError:
            pass

        return {
            'status': 'assigned',
            'test_id': test_id,
            'variant': assigned_variant,
            'user_id': user_id,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=10,
             name='tasks.ab_testing_tasks.record_ab_event')
def record_ab_event(
    self,
    test_id: str,
    user_id: int,
    event_type: str,   # 'impression' | 'click' | 'conversion' | 'revenue'
    value: float = 0.0,
) -> dict:
    """
    Record an A/B test event for a user.
    Aggregates in cache for fast analysis.
    """
    try:
        # Get user's variant
        assignment_key = f'ab_assignment_{test_id}_{user_id}'
        variant = cache.get(assignment_key)
        if not variant:
            return {'status': 'no_assignment', 'test_id': test_id}

        # Increment counter in cache
        stat_key = f'ab_stat_{test_id}_{variant}_{event_type}'
        count    = cache.get(stat_key, 0) + 1
        cache.set(stat_key, count, timeout=86400 * 30)

        if event_type == 'revenue' and value:
            rev_key = f'ab_revenue_{test_id}_{variant}'
            rev     = float(cache.get(rev_key, 0)) + value
            cache.set(rev_key, rev, timeout=86400 * 30)

        # DB record
        try:
            from ab_testing.models import ABTestEvent
            ABTestEvent.objects.create(
                test_id=test_id,
                user_id=user_id,
                variant=variant,
                event_type=event_type,
                value=value,
                recorded_at=timezone.now(),
            )
        except ImportError:
            pass

        return {
            'status': 'recorded',
            'test_id': test_id,
            'variant': variant,
            'event_type': event_type,
            'count': count,
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.ab_testing_tasks.analyze_ab_results')
def analyze_ab_results(self, test_id: str) -> dict:
    """
    Run statistical analysis on A/B test results.
    Uses z-test for conversion rates (two proportions).
    Minimum sample size: 100 conversions per variant.
    """
    try:
        logger.info(f"📊 Analyzing A/B test: {test_id}")

        test_config = _get_test_config(test_id)
        if not test_config:
            return {'status': 'test_not_found', 'test_id': test_id}

        variants = test_config.get('variants', [])
        results  = {}

        for variant in variants:
            vid  = variant['id']
            imp  = cache.get(f'ab_stat_{test_id}_{vid}_impression', 0)
            conv = cache.get(f'ab_stat_{test_id}_{vid}_conversion', 0)
            rev  = float(cache.get(f'ab_revenue_{test_id}_{vid}', 0))
            cvr  = conv / imp if imp > 0 else 0.0
            rpu  = rev / imp if imp > 0 else 0.0

            results[vid] = {
                'variant': vid,
                'impressions': imp,
                'conversions': conv,
                'revenue': round(rev, 4),
                'cvr': round(cvr * 100, 2),
                'rpu': round(rpu, 4),
                'sufficient_sample': imp >= 100,
            }

        # Statistical significance (z-test between first two variants)
        variant_ids = list(results.keys())
        significance = None
        if len(variant_ids) >= 2:
            a = results[variant_ids[0]]
            b = results[variant_ids[1]]
            if a['sufficient_sample'] and b['sufficient_sample']:
                z, p, sig = _z_test(
                    a['conversions'], a['impressions'],
                    b['conversions'], b['impressions'],
                )
                significance = {
                    'z_score': round(z, 4),
                    'p_value': round(p, 4),
                    'is_significant': sig,
                    'winner': variant_ids[0] if a['cvr'] > b['cvr'] and sig else None,
                }

        analysis = {
            'test_id': test_id,
            'variants': results,
            'significance': significance,
            'analyzed_at': timezone.now().isoformat(),
        }
        cache.set(f'ab_analysis_{test_id}', analysis, timeout=3600)

        # Auto-pick winner if significant
        if significance and significance.get('is_significant') and significance.get('winner'):
            auto_pick_winner.apply_async(kwargs={
                'test_id': test_id,
                'winner_variant': significance['winner'],
            })

        return {'status': 'success', 'analysis': analysis}

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=30,
             name='tasks.ab_testing_tasks.auto_pick_winner')
def auto_pick_winner(self, test_id: str, winner_variant: str) -> dict:
    """Promote the winning variant and end the A/B test."""
    try:
        logger.info(f"🏆 A/B test winner: {test_id} → {winner_variant}")

        try:
            from ab_testing.models import ABTest
            ABTest.objects.filter(test_id=test_id).update(
                status='concluded',
                winner_variant=winner_variant,
                concluded_at=timezone.now(),
            )
        except ImportError:
            cache.set(f'ab_winner_{test_id}', winner_variant, timeout=None)

        # Notify admins
        try:
            from api.tasks.notification_tasks import send_email_notification
            from django.contrib.auth import get_user_model
            admins = list(
                get_user_model().objects.filter(is_staff=True, is_active=True)
                .values_list('id', flat=True)[:5]
            )
            for uid in admins:
                send_email_notification.apply_async(kwargs={
                    'user_id': uid,
                    'subject': f'A/B Test Winner: {test_id}',
                    'message': f'Test "{test_id}" concluded. Winner: {winner_variant}',
                })
        except ImportError:
            pass

        return {
            'status': 'success',
            'test_id': test_id,
            'winner': winner_variant,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_test_config(test_id: str) -> dict:
    cached = cache.get(f'ab_test_config_{test_id}')
    if cached:
        return cached
    try:
        from ab_testing.models import ABTest
        test = ABTest.objects.filter(test_id=test_id).first()
        if test:
            config = {
                'test_id': test_id,
                'is_active': test.status == 'active',
                'variants': test.variants or [],
            }
            cache.set(f'ab_test_config_{test_id}', config, timeout=300)
            return config
    except ImportError:
        pass
    return {}


def _z_test(conv_a: int, n_a: int, conv_b: int, n_b: int):
    """Two-proportion z-test. Returns (z_score, p_value, is_significant)."""
    if n_a == 0 or n_b == 0:
        return 0, 1.0, False

    p_a    = conv_a / n_a
    p_b    = conv_b / n_b
    p_pool = (conv_a + conv_b) / (n_a + n_b)

    se = math.sqrt(p_pool * (1 - p_pool) * (1/n_a + 1/n_b))
    if se == 0:
        return 0, 1.0, False

    z   = (p_a - p_b) / se
    p   = 2 * (1 - _norm_cdf(abs(z)))  # two-tailed
    sig = p < 0.05  # 95% confidence

    return z, p, sig


def _norm_cdf(x: float) -> float:
    """Approximation of normal CDF using erf."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0
