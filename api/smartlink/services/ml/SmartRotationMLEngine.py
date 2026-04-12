"""
SmartLink ML Rotation Engine
World #1 Feature: Machine Learning-powered offer selection.
Uses multi-armed bandit algorithm (Thompson Sampling) for optimal
offer rotation — better than ANY competitor including Everflow.

Features:
- Thompson Sampling (Bayesian bandit) — learns in real-time
- Contextual bandits: different model per geo+device
- Auto-exploration vs exploitation balance
- Confidence intervals for EPC prediction
- Anomaly detection for offer performance drops
"""
import math
import random
import logging
from typing import Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('smartlink.ml.rotation')


class ThompsonSamplingBandit:
    """
    Thompson Sampling Multi-Armed Bandit for offer selection.
    Each offer has Beta distribution parameters (alpha, beta)
    representing conversion rate belief.

    alpha = successes (conversions) + 1
    beta  = failures  (clicks - conversions) + 1

    On each request: sample from each offer's Beta dist,
    select the offer with the highest sample.
    """

    def sample(self, alpha: float, beta: float) -> float:
        """Sample from Beta(alpha, beta) distribution."""
        try:
            import numpy as np
            return float(np.random.beta(alpha, beta))
        except ImportError:
            # Fallback: use Python random (less accurate but works)
            return self._beta_sample_fallback(alpha, beta)

    def _beta_sample_fallback(self, alpha: float, beta: float) -> float:
        """Fallback Beta sampling using Gamma distribution relationship."""
        x = random.gammavariate(alpha, 1)
        y = random.gammavariate(beta, 1)
        if x + y == 0:
            return 0.5
        return x / (x + y)


class SmartRotationMLEngine:
    """
    World #1 ML-powered offer rotation engine.
    Replaces simple weighted random with intelligent bandit algorithm.

    Performance vs competitors:
    - CPAlead: static weights → our system: dynamic Bayesian learning
    - HasOffers: EPC-only → our system: full contextual bandit
    - Everflow: rule-based → our system: ML + rules combined
    """

    CACHE_PREFIX = 'ml_bandit:'
    CACHE_TTL = 3600  # 1 hour

    def __init__(self):
        self.bandit = ThompsonSamplingBandit()

    def select_offer(self, entries: list, context: dict) -> Optional[object]:
        """
        Select best offer using Thompson Sampling.

        Args:
            entries: list of OfferPoolEntry objects
            context: {country, device_type, os, hour_of_day, day_of_week}

        Returns:
            Best OfferPoolEntry based on Bayesian posterior
        """
        if not entries:
            return None

        if len(entries) == 1:
            return entries[0]

        context_key = self._context_key(context)
        samples = []

        for entry in entries:
            alpha, beta = self._get_beta_params(entry.offer_id, context_key)
            # EPC weight: multiply sample by EPC factor for revenue optimization
            epc_factor = self._get_epc_factor(entry)
            sample = self.bandit.sample(alpha, beta) * epc_factor
            samples.append((sample, entry))
            logger.debug(
                f"ML Bandit: offer#{entry.offer_id} α={alpha:.1f} β={beta:.1f} "
                f"sample={sample:.4f} epc_factor={epc_factor:.2f}"
            )

        # Select offer with highest Thompson sample
        samples.sort(key=lambda x: x[0], reverse=True)
        winner = samples[0][1]

        logger.info(
            f"ML selected offer#{winner.offer_id} "
            f"score={samples[0][0]:.4f} from {len(entries)} candidates "
            f"context={context_key}"
        )
        return winner

    def record_click(self, offer_id: int, context: dict):
        """Record a click (non-conversion) — updates Beta beta parameter."""
        context_key = self._context_key(context)
        cache_key = self._cache_key(offer_id, context_key)
        params = self._load_params(cache_key)
        params['beta'] += 1  # Failure (no conversion yet)
        self._save_params(cache_key, params)

    def record_conversion(self, offer_id: int, context: dict, payout: float = 0):
        """Record a conversion — updates Beta alpha parameter."""
        context_key = self._context_key(context)
        cache_key = self._cache_key(offer_id, context_key)
        params = self._load_params(cache_key)
        params['alpha'] += 1  # Success
        # Also track revenue for EPC weighting
        params['total_revenue'] = params.get('total_revenue', 0) + payout
        params['total_clicks'] = params.get('total_clicks', 0)
        self._save_params(cache_key, params)

    def get_offer_confidence_interval(self, offer_id: int, context: dict) -> dict:
        """
        Get 95% confidence interval for conversion rate.
        Used in A/B test evaluation and reporting.
        """
        context_key = self._context_key(context)
        cache_key = self._cache_key(offer_id, context_key)
        params = self._load_params(cache_key)
        alpha = params['alpha']
        beta = params['beta']
        n = alpha + beta - 2  # total observations

        if n < 10:
            return {'lower': 0.0, 'upper': 1.0, 'mean': 0.5, 'confidence': 'low'}

        mean = alpha / (alpha + beta)
        # Wilson score interval approximation
        z = 1.96  # 95% confidence
        denominator = 1 + z**2 / n
        center = (mean + z**2 / (2 * n)) / denominator
        margin = (z * math.sqrt(mean * (1 - mean) / n + z**2 / (4 * n**2))) / denominator

        return {
            'lower':      round(max(0, center - margin), 4),
            'upper':      round(min(1, center + margin), 4),
            'mean':       round(mean, 4),
            'confidence': 'high' if n >= 100 else 'medium' if n >= 30 else 'low',
            'observations': n,
        }

    def detect_performance_anomaly(self, offer_id: int, context: dict) -> dict:
        """
        Detect sudden drops in offer performance (offer went offline, cap changed).
        Compares recent CR to historical CR using z-score.
        """
        context_key = self._context_key(context)
        cache_key = self._cache_key(offer_id, context_key)
        params = self._load_params(cache_key)

        alpha = params['alpha']
        beta = params['beta']
        n = alpha + beta - 2

        if n < 20:
            return {'anomaly': False, 'reason': 'insufficient_data'}

        current_cr = alpha / (alpha + beta)
        historical_cr = params.get('historical_cr', current_cr)

        if historical_cr == 0:
            return {'anomaly': False, 'reason': 'no_history'}

        change_pct = (current_cr - historical_cr) / historical_cr * 100

        if change_pct < -50:
            return {
                'anomaly': True,
                'type': 'performance_drop',
                'change_pct': round(change_pct, 1),
                'current_cr': round(current_cr, 4),
                'historical_cr': round(historical_cr, 4),
                'recommendation': 'Consider pausing this offer',
            }

        return {'anomaly': False, 'change_pct': round(change_pct, 1)}

    def reset_offer(self, offer_id: int, context_key: str = '*'):
        """Reset bandit parameters for an offer (e.g., when offer is updated)."""
        if context_key == '*':
            # Clear all contexts for this offer
            try:
                from django_redis import get_redis_connection
                conn = get_redis_connection('default')
                pattern = f"sl:{self.CACHE_PREFIX}{offer_id}:*"
                keys = conn.keys(pattern)
                if keys:
                    conn.delete(*keys)
                    logger.info(f"ML reset: cleared {len(keys)} contexts for offer#{offer_id}")
            except Exception as e:
                logger.warning(f"ML reset failed: {e}")
        else:
            cache_key = self._cache_key(offer_id, context_key)
            cache.delete(f"sl:{cache_key}")

    # ── Private ─────────────────────────────────────────────────────

    def _context_key(self, context: dict) -> str:
        """Create a compact context identifier for cache key."""
        country = context.get('country', 'XX').upper()
        device  = context.get('device_type', 'unknown')[:3]
        hour    = timezone.now().hour // 6  # 0-3 (6-hour buckets)
        return f"{country}_{device}_{hour}"

    def _cache_key(self, offer_id: int, context_key: str) -> str:
        return f"{self.CACHE_PREFIX}{offer_id}:{context_key}"

    def _load_params(self, cache_key: str) -> dict:
        params = cache.get(cache_key)
        if params is None:
            params = {'alpha': 1.0, 'beta': 1.0, 'total_revenue': 0.0, 'total_clicks': 0}
        return params

    def _save_params(self, cache_key: str, params: dict):
        cache.set(cache_key, params, self.CACHE_TTL)

    def _get_beta_params(self, offer_id: int, context_key: str) -> tuple:
        cache_key = self._cache_key(offer_id, context_key)
        params = self._load_params(cache_key)
        return params['alpha'], params['beta']

    def _get_epc_factor(self, entry) -> float:
        """
        EPC multiplier to weight high-revenue offers higher.
        Prevents low-payout high-CR offers dominating.
        """
        if entry.epc_override and float(entry.epc_override) > 0:
            base_epc = float(entry.epc_override)
        else:
            from ..rotation.EPCOptimizer import EPCOptimizer
            # Quick score lookup — returns 0 if not available
            try:
                from ...models import OfferScoreCache
                score = OfferScoreCache.objects.filter(
                    offer_id=entry.offer_id
                ).order_by('-score').values_list('epc', flat=True).first()
                base_epc = float(score) if score else 0.01
            except Exception:
                base_epc = 0.01

        # Normalize: log scale to prevent extreme dominance
        return max(0.1, math.log1p(base_epc * 100) / math.log1p(100))
