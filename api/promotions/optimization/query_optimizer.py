# =============================================================================
# api/promotions/optimization/query_optimizer.py
# Database Query Optimizer — N+1 prevention, slow query detection, index hints
# =============================================================================

import functools
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable

from django.conf import settings
from django.core.cache import cache
from django.db import connection, reset_queries

logger = logging.getLogger('optimization.query')

SLOW_QUERY_THRESHOLD_MS = getattr(settings, 'SLOW_QUERY_THRESHOLD_MS', 100)
N_PLUS_1_THRESHOLD      = getattr(settings, 'N_PLUS_1_THRESHOLD', 10)
CACHE_PREFIX_QUERY      = 'opt:query:{}'


# =============================================================================
# ── DATA CLASSES ──────────────────────────────────────────────────────────────
# =============================================================================

@dataclass
class QueryProfile:
    total_queries:    int
    total_ms:         float
    slow_queries:     list
    duplicate_queries: list
    n_plus_1_detected: bool
    suggestions:      list[str]


# =============================================================================
# ── QUERY PROFILER ────────────────────────────────────────────────────────────
# =============================================================================

@contextmanager
def profile_queries(label: str = 'unnamed'):
    """
    Context manager — block এর ভেতরে কতটা query চলল profile করে।

    Usage:
        with profile_queries('campaign_list_view') as report:
            campaigns = Campaign.objects.all()[:20]
        print(report.total_queries, report.total_ms)
    """
    if not settings.DEBUG:
        yield QueryProfile(0, 0.0, [], [], False, [])
        return

    reset_queries()
    start = time.monotonic()
    report = QueryProfile(0, 0.0, [], [], False, [])

    try:
        yield report
    finally:
        elapsed     = (time.monotonic() - start) * 1000
        queries     = connection.queries

        slow        = [q for q in queries if float(q.get('time', 0)) * 1000 > SLOW_QUERY_THRESHOLD_MS]
        # Duplicate detection
        sql_counts  = {}
        for q in queries:
            sql = q['sql'][:100]
            sql_counts[sql] = sql_counts.get(sql, 0) + 1
        duplicates  = [sql for sql, count in sql_counts.items() if count > 2]
        n_plus_1    = len(queries) > N_PLUS_1_THRESHOLD

        suggestions = []
        if n_plus_1:
            suggestions.append(f'N+1 suspected: {len(queries)} queries — select_related/prefetch_related ব্যবহার করুন')
        if slow:
            suggestions.append(f'{len(slow)} slow queries detected — index যোগ করুন')
        if duplicates:
            suggestions.append(f'{len(duplicates)} duplicate SQL patterns — cache অথবা queryset combine করুন')

        report.total_queries   = len(queries)
        report.total_ms        = round(elapsed, 2)
        report.slow_queries    = slow
        report.duplicate_queries = duplicates
        report.n_plus_1_detected = n_plus_1
        report.suggestions     = suggestions

        if suggestions:
            logger.warning(f'[{label}] Query issues: {suggestions}')
        else:
            logger.debug(f'[{label}] {len(queries)} queries in {elapsed:.1f}ms')


# =============================================================================
# ── OPTIMIZED QUERYSETS ───────────────────────────────────────────────────────
# =============================================================================

class OptimizedQuerysets:
    """
    Pre-built optimized querysets — সব viewset এ পুনরায় লেখা না করে এখান থেকে নাও।
    প্রতিটি queryset properly select_related + prefetch_related করা।
    """

    @staticmethod
    def campaigns_list(user=None):
        """Campaign list এর জন্য optimized queryset।"""
        from api.promotions.models import Campaign
        from api.promotions.choices import CampaignStatus
        qs = (
            Campaign.objects
            .select_related('category', 'platform', 'advertiser')
            .prefetch_related('bonus_policies')
            .only(
                'id', 'title', 'status', 'total_budget_usd', 'spent_usd',
                'total_slots', 'filled_slots', 'created_at',
                'category__name', 'platform__name',
                'advertiser__username',
            )
        )
        if user and not user.is_staff:
            qs = qs.filter(status=CampaignStatus.ACTIVE)
        return qs

    @staticmethod
    def campaign_detail(campaign_id: int):
        """Campaign detail এর জন্য — সব related data একবারে।"""
        from api.promotions.models import Campaign
        return (
            Campaign.objects
            .select_related('category', 'platform', 'advertiser', 'targeting', 'limits', 'schedule')
            .prefetch_related('steps', 'bonus_policies', 'analytics')
            .get(pk=campaign_id)
        )

    @staticmethod
    def submissions_list(user=None, campaign_id: int = None):
        """Submission list — proof files ও related data সহ।"""
        from api.promotions.models import TaskSubmission
        qs = (
            TaskSubmission.objects
            .select_related(
                'campaign', 'campaign__category', 'campaign__platform',
                'worker', 'reviewed_by',
            )
            .prefetch_related('proofs')
            .only(
                'id', 'status', 'reward_usd', 'submitted_at', 'reviewed_at',
                'worker__username', 'campaign__title', 'reviewed_by__username',
                'ip_address', 'device_fingerprint',
            )
        )
        if user and not user.is_staff:
            qs = qs.filter(worker=user)
        if campaign_id:
            qs = qs.filter(campaign_id=campaign_id)
        return qs

    @staticmethod
    def user_dashboard(user_id: int) -> dict:
        """User dashboard এর সব data একটি query batch এ।"""
        from api.promotions.models import (
            TaskSubmission, PromotionTransaction, UserReputation
        )
        from api.promotions.choices import SubmissionStatus
        from django.db.models import Count, Sum, Q

        stats = TaskSubmission.objects.filter(worker_id=user_id).aggregate(
            total       = Count('id'),
            approved    = Count('id', filter=Q(status=SubmissionStatus.APPROVED)),
            pending     = Count('id', filter=Q(status=SubmissionStatus.PENDING)),
            rejected    = Count('id', filter=Q(status=SubmissionStatus.REJECTED)),
            total_earned = Sum('reward_usd', filter=Q(status=SubmissionStatus.APPROVED)),
        )
        rep = UserReputation.objects.filter(user_id=user_id).values(
            'trust_score', 'level', 'success_rate'
        ).first()

        return {
            'submission_stats': stats,
            'reputation':       rep,
        }

    @staticmethod
    def advertiser_dashboard(user_id: int) -> dict:
        """Advertiser dashboard data।"""
        from api.promotions.models import Campaign, AdminCommissionLog
        from api.promotions.choices import CampaignStatus
        from django.db.models import Count, Sum, Q

        campaign_stats = Campaign.objects.filter(advertiser_id=user_id).aggregate(
            total       = Count('id'),
            active      = Count('id', filter=Q(status=CampaignStatus.ACTIVE)),
            total_spent = Sum('spent_usd'),
            total_budget = Sum('total_budget_usd'),
        )
        return {'campaign_stats': campaign_stats}


# =============================================================================
# ── QUERY CACHE DECORATOR ─────────────────────────────────────────────────────
# =============================================================================

def cached_query(ttl: int = 300, key_prefix: str = '', vary_on_user: bool = False):
    """
    Query result cache করার decorator।

    Usage:
        @cached_query(ttl=60, key_prefix='campaign_list')
        def get_active_campaigns(category_id=None):
            return list(Campaign.objects.filter(...))
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Cache key build
            key_parts = [key_prefix or fn.__name__]
            key_parts.extend(str(a) for a in args)
            key_parts.extend(f'{k}={v}' for k, v in sorted(kwargs.items()))
            cache_key = CACHE_PREFIX_QUERY.format(':'.join(key_parts))

            cached = cache.get(cache_key)
            if cached is not None:
                return cached

            result = fn(*args, **kwargs)
            # QuerySet হলে list এ convert করো (pickle করা যায়)
            if hasattr(result, '__iter__') and hasattr(result, 'query'):
                result = list(result)
            cache.set(cache_key, result, timeout=ttl)
            return result
        return wrapper
    return decorator


# =============================================================================
# ── SLOW QUERY MIDDLEWARE ─────────────────────────────────────────────────────
# =============================================================================

class SlowQueryMiddleware:
    """
    Slow queries log করে এবং alert দেয়।
    settings.py তে DEBUG=True থাকলেই কাজ করে।
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.DEBUG:
            return self.get_response(request)

        reset_queries()
        start    = time.monotonic()
        response = self.get_response(request)
        elapsed  = (time.monotonic() - start) * 1000

        queries  = connection.queries
        slow     = [q for q in queries if float(q.get('time', 0)) * 1000 > SLOW_QUERY_THRESHOLD_MS]

        if slow:
            logger.warning(
                f'SLOW QUERIES on {request.path}: '
                f'{len(slow)} slow/{len(queries)} total in {elapsed:.0f}ms\n' +
                '\n'.join(f'  [{float(q["time"])*1000:.0f}ms] {q["sql"][:150]}' for q in slow[:3])
            )

        if len(queries) > N_PLUS_1_THRESHOLD:
            logger.warning(
                f'N+1 SUSPECTED on {request.path}: '
                f'{len(queries)} queries in {elapsed:.0f}ms'
            )

        # Response header তে query count যোগ করো (dev only)
        if settings.DEBUG:
            response['X-Query-Count'] = str(len(queries))
            response['X-Query-Ms']    = f'{elapsed:.0f}'

        return response


# =============================================================================
# ── INDEX ADVISOR ─────────────────────────────────────────────────────────────
# =============================================================================

class IndexAdvisor:
    """
    Slow queries analyze করে missing index suggest করে।
    PostgreSQL EXPLAIN ANALYZE output parse করে।
    """

    def analyze_slow_queries(self, limit: int = 20) -> list[dict]:
        """
        Django slow query log থেকে missing indexes suggest করে।
        PostgreSQL pg_stat_statements extension লাগবে।
        """
        suggestions = []
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        query,
                        calls,
                        mean_exec_time,
                        total_exec_time,
                        rows
                    FROM pg_stat_statements
                    WHERE mean_exec_time > %s
                    ORDER BY mean_exec_time DESC
                    LIMIT %s
                """, [SLOW_QUERY_THRESHOLD_MS, limit])

                for row in cursor.fetchall():
                    query, calls, mean_ms, total_ms, rows = row
                    suggestions.append({
                        'query':    query[:200],
                        'calls':    calls,
                        'mean_ms':  round(mean_ms, 2),
                        'total_ms': round(total_ms, 2),
                        'rows':     rows,
                        'suggestion': self._suggest_index(query),
                    })
        except Exception as e:
            logger.debug(f'pg_stat_statements not available: {e}')
        return suggestions

    @staticmethod
    def _suggest_index(query: str) -> str:
        """Query থেকে index suggestion তৈরি করে।"""
        import re
        # WHERE clause এর columns detect করো
        where_cols = re.findall(r'WHERE\s+[\w\.]+\s*=', query, re.IGNORECASE)
        order_cols = re.findall(r'ORDER BY\s+([\w\.,\s]+)', query, re.IGNORECASE)

        parts = []
        if where_cols:
            cols = [c.replace('WHERE', '').replace('=', '').strip() for c in where_cols]
            parts.append(f'WHERE columns এ index যোগ করুন: {", ".join(cols[:3])}')
        if order_cols:
            parts.append(f'ORDER BY column এ index: {order_cols[0][:50]}')

        return ' | '.join(parts) if parts else 'Query analyze করুন।'
