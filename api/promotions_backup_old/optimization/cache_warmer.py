# =============================================================================
# api/promotions/optimization/cache_warmer.py
# Cache Warmer — App startup ও scheduled intervals এ cache pre-populate করে
# Cold start এ slow response এড়াতে critical data আগে থেকেই cache এ রাখে
# =============================================================================

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from django.core.cache import cache

logger = logging.getLogger('optimization.cache_warmer')


# =============================================================================
# ── DATA CLASSES ──────────────────────────────────────────────────────────────
# =============================================================================

@dataclass
class WarmupResult:
    key:           str
    success:       bool
    duration_ms:   float
    error:         str = ''


@dataclass
class WarmupReport:
    total:         int
    succeeded:     int
    failed:        int
    total_ms:      float
    results:       list[WarmupResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return (self.succeeded / self.total * 100) if self.total > 0 else 0.0


# =============================================================================
# ── CACHE WARMER ──────────────────────────────────────────────────────────────
# =============================================================================

class CacheWarmer:
    """
    Critical cache keys pre-populate করে।

    Strategy:
    - App startup এ run হয় (apps.py ready() method থেকে)
    - Celery beat দিয়ে every 5 minutes refresh হয়
    - Manual trigger করা যায়

    Cache priority tiers:
    - TIER 1 (critical): Campaign list, currency rates, active blacklists
    - TIER 2 (important): User reputation, analytics summaries
    - TIER 3 (nice-to-have): Category list, platform list
    """

    # ── Cache Recipes ─────────────────────────────────────────────────────────
    # প্রতিটি recipe: {'key': cache_key, 'fn': callable, 'ttl': seconds}

    def get_recipes(self) -> list[dict]:
        """সব warmup recipes return করে।"""
        return [
            # ── TIER 1: Critical ─────────────────────────────────────────
            {
                'key': 'warm:active_campaigns',
                'fn':  self._warm_active_campaigns,
                'ttl': 300,   # 5 minutes
                'tier': 1,
            },
            {
                'key': 'warm:currency_rates',
                'fn':  self._warm_currency_rates,
                'ttl': 3600,  # 1 hour
                'tier': 1,
            },
            {
                'key': 'warm:blacklist_ips',
                'fn':  self._warm_blacklist_ips,
                'ttl': 300,
                'tier': 1,
            },
            {
                'key': 'warm:reward_policies',
                'fn':  self._warm_reward_policies,
                'ttl': 3600,
                'tier': 1,
            },
            # ── TIER 2: Important ────────────────────────────────────────
            {
                'key': 'warm:categories',
                'fn':  self._warm_categories,
                'ttl': 86400,  # 24 hours
                'tier': 2,
            },
            {
                'key': 'warm:platforms',
                'fn':  self._warm_platforms,
                'ttl': 86400,
                'tier': 2,
            },
            {
                'key': 'warm:platform_stats',
                'fn':  self._warm_platform_stats,
                'ttl': 600,   # 10 minutes
                'tier': 2,
            },
            # ── TIER 3: Nice-to-have ─────────────────────────────────────
            {
                'key': 'warm:top_campaigns',
                'fn':  self._warm_top_campaigns,
                'ttl': 300,
                'tier': 3,
            },
        ]

    def warm_all(self, min_tier: int = 3) -> WarmupReport:
        """সব tiers warm up করে।"""
        recipes = [r for r in self.get_recipes() if r.get('tier', 3) <= min_tier]
        return self._run_recipes(recipes)

    def warm_critical(self) -> WarmupReport:
        """Tier 1 (critical) only warm up — startup এর জন্য।"""
        return self.warm_all(min_tier=1)

    def warm_by_keys(self, keys: list[str]) -> WarmupReport:
        """নির্দিষ্ট keys গুলো warm up করে।"""
        recipes = [r for r in self.get_recipes() if r['key'] in keys]
        return self._run_recipes(recipes)

    def invalidate(self, *keys: str) -> int:
        """Cache keys invalidate করে (এবং re-warm করে)।"""
        invalidated = 0
        for key in keys:
            if cache.delete(key):
                invalidated += 1
        logger.info(f'Cache invalidated: {invalidated} keys')
        return invalidated

    def invalidate_and_rewarm(self, *keys: str) -> WarmupReport:
        """Invalidate করে তারপর warm করে।"""
        self.invalidate(*keys)
        return self.warm_by_keys(list(keys))

    # ── Internal Runner ───────────────────────────────────────────────────────

    def _run_recipes(self, recipes: list[dict]) -> WarmupReport:
        results   = []
        total_ms  = 0.0
        succeeded = 0

        for recipe in recipes:
            key   = recipe['key']
            start = time.monotonic()
            try:
                # Already warm কিনা check
                if cache.get(key) is not None:
                    results.append(WarmupResult(key=key, success=True, duration_ms=0.0))
                    succeeded += 1
                    continue

                data = recipe['fn']()
                if data is not None:
                    cache.set(key, data, timeout=recipe.get('ttl', 300))

                ms = round((time.monotonic() - start) * 1000, 2)
                results.append(WarmupResult(key=key, success=True, duration_ms=ms))
                succeeded += 1
                total_ms  += ms
                logger.debug(f'Cache warmed: {key} ({ms}ms)')

            except Exception as e:
                ms = round((time.monotonic() - start) * 1000, 2)
                results.append(WarmupResult(key=key, success=False, duration_ms=ms, error=str(e)))
                total_ms += ms
                logger.warning(f'Cache warm failed: {key} — {e}')

        report = WarmupReport(
            total     = len(recipes),
            succeeded = succeeded,
            failed    = len(recipes) - succeeded,
            total_ms  = round(total_ms, 2),
            results   = results,
        )
        logger.info(
            f'Cache warmup complete: {succeeded}/{len(recipes)} succeeded, '
            f'total={total_ms:.0f}ms, rate={report.success_rate:.0f}%'
        )
        return report

    # ── Warm Functions ────────────────────────────────────────────────────────

    def _warm_active_campaigns(self) -> list:
        """Active campaigns list cache করে।"""
        from api.promotions.models import Campaign
        from api.promotions.choices import CampaignStatus
        campaigns = list(
            Campaign.objects.filter(status=CampaignStatus.ACTIVE)
            .select_related('category', 'platform')
            .values(
                'id', 'title', 'total_budget_usd', 'filled_slots',
                'total_slots', 'category__name', 'platform__name',
            )[:200]
        )
        return campaigns

    def _warm_currency_rates(self) -> dict:
        """Currency rates cache করে।"""
        from api.promotions.models import CurrencyRate
        rates = {}
        for rate in CurrencyRate.objects.filter(is_active=True).order_by('-fetched_at'):
            key = f'{rate.base_currency}_{rate.target_currency}'
            if key not in rates:
                rates[key] = float(rate.rate)
        return rates

    def _warm_blacklist_ips(self) -> set:
        """Active blacklisted IPs set cache করে।"""
        from api.promotions.models import Blacklist
        from api.promotions.choices import BlacklistType
        from django.utils import timezone
        ips = set(
            Blacklist.objects.filter(
                type=BlacklistType.IP,
                is_active=True,
            ).filter(
                models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
            ).values_list('value', flat=True)
        )
        return ips

    def _warm_reward_policies(self) -> list:
        """Reward policies cache করে।"""
        from api.promotions.models import RewardPolicy
        return list(
            RewardPolicy.objects.filter(is_active=True)
            .select_related('category', 'platform')
            .values('id', 'rate_usd', 'category__name', 'platform__name', 'country_code')
        )

    def _warm_categories(self) -> list:
        """Categories list cache করে।"""
        from api.promotions.models import PromotionCategory
        return list(PromotionCategory.objects.filter(is_active=True).values('id', 'name', 'slug'))

    def _warm_platforms(self) -> list:
        """Platforms list cache করে।"""
        from api.promotions.models import Platform
        return list(Platform.objects.filter(is_active=True).values('id', 'name', 'slug'))

    def _warm_platform_stats(self) -> dict:
        """Platform-wise submission stats cache করে।"""
        from api.promotions.models import TaskSubmission
        from api.promotions.choices import SubmissionStatus
        from django.db.models import Count
        stats = {}
        qs = (
            TaskSubmission.objects
            .values('campaign__platform__name')
            .annotate(
                total=Count('id'),
                approved=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(
                    status=SubmissionStatus.APPROVED
                )),
            )
        )
        for row in qs:
            plat = row['campaign__platform__name'] or 'unknown'
            stats[plat] = {
                'total':    row['total'],
                'approved': row['approved'],
                'rate':     round(row['approved'] / max(row['total'], 1) * 100, 1),
            }
        return stats

    def _warm_top_campaigns(self) -> list:
        """Top performing campaigns cache করে।"""
        from api.promotions.models import Campaign, CampaignAnalytics
        from api.promotions.choices import CampaignStatus
        from django.db.models import Sum, Avg
        top = list(
            Campaign.objects.filter(status=CampaignStatus.ACTIVE)
            .annotate(total_revenue=Sum('analytics__total_spent_usd'))
            .order_by('-total_revenue')
            .values('id', 'title', 'total_revenue', 'fill_percentage')[:20]
        )
        return top


# ── Singleton ──────────────────────────────────────────────────────────────────
cache_warmer = CacheWarmer()


# =============================================================================
# ── CELERY TASK INTEGRATION ───────────────────────────────────────────────────
# =============================================================================

def warm_cache_task():
    """
    Celery task হিসেবে register করুন।

    settings.py CELERY_BEAT_SCHEDULE তে:
        'warm-cache': {
            'task': 'api.promotions.optimization.cache_warmer.warm_cache_task',
            'schedule': crontab(minute='*/5'),
        }
    """
    report = cache_warmer.warm_all(min_tier=2)
    logger.info(
        f'Scheduled cache warmup: {report.succeeded}/{report.total} '
        f'keys warmed in {report.total_ms:.0f}ms'
    )
    return {
        'succeeded':   report.succeeded,
        'failed':      report.failed,
        'total_ms':    report.total_ms,
        'success_rate': report.success_rate,
    }
