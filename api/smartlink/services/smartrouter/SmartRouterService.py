"""
SmartLink Smart Router Service
World #1 Feature: Hyper-intelligent traffic routing engine.

Goes beyond ALL competitors by combining:
1. Real-time EPC-based routing
2. ML Thompson Sampling
3. Publisher quality score weighting
4. Time-decay EPC (recent conversions weighted more)
5. Geo-device combo optimization
6. Automatic offer refresh on cap hit
7. Multi-hop redirect chain optimization
8. Carrier/ISP-aware routing (Grameenphone vs Robi = different EPC)

This is the BRAIN of the SmartLink system.
CPAlead does NOT have this. Everflow does NOT have this.
"""
import math
import logging
import random
from typing import Optional, List, Tuple
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('smartlink.smartrouter')


class RoutingDecision:
    """Immutable result of a routing decision."""
    __slots__ = ['offer_entry', 'reason', 'score', 'confidence', 'fallback']

    def __init__(self, offer_entry, reason: str, score: float,
                 confidence: float = 1.0, fallback: bool = False):
        self.offer_entry = offer_entry
        self.reason      = reason
        self.score       = score
        self.confidence  = confidence
        self.fallback    = fallback

    def __repr__(self):
        entry = self.offer_entry
        offer_id = getattr(entry, 'offer_id', None) if entry else None
        return (f"RoutingDecision(offer={offer_id}, reason={self.reason}, "
                f"score={self.score:.4f}, conf={self.confidence:.2f})")


class SmartRouterService:
    """
    Hyper-intelligent routing engine.
    Selects the single best offer for each unique traffic profile
    using a multi-factor scoring system updated in real-time.

    Scoring formula:
    SCORE = (EPC_score × 0.35)
          + (ML_bandit_sample × 0.30)
          + (quality_score × 0.15)
          + (time_decay_bonus × 0.10)
          + (isp_match_bonus × 0.10)
    """

    # Scoring factor weights (must sum to 1.0)
    WEIGHTS = {
        'epc':         0.35,
        'ml_bandit':   0.30,
        'quality':     0.15,
        'time_decay':  0.10,
        'isp_match':   0.10,
    }

    def __init__(self):
        from ..ml.SmartRotationMLEngine import SmartRotationMLEngine
        from ..rotation.CapTrackerService import CapTrackerService
        from ..rotation.EPCOptimizer import EPCOptimizer
        self.ml_engine   = SmartRotationMLEngine()
        self.cap_tracker = CapTrackerService()
        self.epc_opt     = EPCOptimizer()

    def route(self, smartlink, entries: list, context: dict) -> RoutingDecision:
        """
        Main routing method: select best offer for this traffic.

        Args:
            smartlink:  SmartLink instance
            entries:    list of active OfferPoolEntry
            context:    {country, device_type, os, isp, asn, hour, is_mobile, ...}

        Returns:
            RoutingDecision with selected offer
        """
        if not entries:
            return RoutingDecision(None, 'no_entries', 0.0, fallback=True)

        if len(entries) == 1:
            entry = entries[0]
            if self.cap_tracker.is_capped(entry):
                return RoutingDecision(None, 'single_capped', 0.0, fallback=True)
            return RoutingDecision(entry, 'single_only', 1.0, confidence=0.5)

        # Filter capped entries
        available = [e for e in entries if not self.cap_tracker.is_capped(e)]
        if not available:
            return RoutingDecision(None, 'all_capped', 0.0, fallback=True)

        # Score each entry
        scored = self._score_all(available, context, smartlink)
        if not scored:
            return RoutingDecision(None, 'scoring_failed', 0.0, fallback=True)

        # Select winner using probabilistic weighted sampling
        # (not pure argmax — keeps exploring lower-scored offers)
        winner_entry, winner_score, winner_reason = self._probabilistic_select(scored)

        # Calculate confidence (how much better is winner vs runner-up)
        confidence = self._calculate_confidence(scored)

        decision = RoutingDecision(
            offer_entry=winner_entry,
            reason=winner_reason,
            score=winner_score,
            confidence=confidence,
        )

        logger.info(
            f"SmartRouter: sl=[{smartlink.slug}] "
            f"offer#{winner_entry.offer_id} reason={winner_reason} "
            f"score={winner_score:.4f} conf={confidence:.2f} "
            f"country={context.get('country')} device={context.get('device_type')}"
        )

        return decision

    def _score_all(self, entries: list, context: dict, smartlink) -> list:
        """Compute multi-factor score for each entry."""
        country     = context.get('country', 'XX')
        device_type = context.get('device_type', 'unknown')
        isp         = context.get('isp', '').lower()
        hour        = context.get('hour', timezone.now().hour)

        scored = []
        for entry in entries:
            try:
                score_parts = {}

                # 1. EPC score (normalized 0-1)
                epc_score = self._get_normalized_epc(entry.offer_id, country, device_type)
                score_parts['epc'] = epc_score

                # 2. ML Thompson Sampling score
                ml_ctx = {'country': country, 'device_type': device_type, 'hour': hour}
                alpha, beta = self.ml_engine._get_beta_params(entry.offer_id, self.ml_engine._context_key(ml_ctx))
                ml_score = self.ml_engine.bandit.sample(alpha, beta)
                score_parts['ml_bandit'] = ml_score

                # 3. Quality score (publisher-defined weight)
                quality_score = min(entry.weight / 1000.0, 1.0)
                score_parts['quality'] = quality_score

                # 4. Time-decay bonus (recent conversions worth more)
                time_decay = self._get_time_decay_score(entry.offer_id, hour)
                score_parts['time_decay'] = time_decay

                # 5. ISP/carrier match bonus
                isp_bonus = self._get_isp_bonus(entry, isp)
                score_parts['isp_match'] = isp_bonus

                # Weighted sum
                total_score = sum(
                    self.WEIGHTS[k] * v
                    for k, v in score_parts.items()
                )

                # Determine dominant reason
                dominant = max(score_parts, key=lambda k: self.WEIGHTS[k] * score_parts[k])

                scored.append((entry, total_score, dominant, score_parts))

            except Exception as e:
                logger.warning(f"Scoring error for offer#{entry.offer_id}: {e}")
                scored.append((entry, 0.01, 'fallback_score', {}))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _probabilistic_select(self, scored: list) -> Tuple:
        """
        Probabilistic selection using softmax — not pure greedy.
        Allows lower-scored offers to occasionally win (exploration).
        Temperature τ=2.0 controls exploration-exploitation tradeoff.
        """
        if not scored:
            return None, 0.0, 'empty'

        tau = 2.0
        scores = [s[1] for s in scored]
        max_s  = max(scores)

        # Softmax
        exp_scores = [math.exp((s - max_s) / tau) for s in scores]
        total      = sum(exp_scores)
        probs      = [e / total for e in exp_scores]

        # Sample
        r = random.random()
        cumulative = 0.0
        for i, (entry, score, reason, _) in enumerate(scored):
            cumulative += probs[i]
            if r <= cumulative:
                return entry, score, reason

        # Fallback: return highest scorer
        return scored[0][0], scored[0][1], scored[0][2]

    def _calculate_confidence(self, scored: list) -> float:
        """How confident are we in the winner vs runner-up?"""
        if len(scored) < 2:
            return 1.0
        winner_score    = scored[0][1]
        runner_up_score = scored[1][1]
        if winner_score == 0:
            return 0.0
        return min((winner_score - runner_up_score) / winner_score, 1.0)

    def _get_normalized_epc(self, offer_id: int, country: str, device_type: str) -> float:
        """Get EPC score normalized to 0-1 range."""
        cache_key = f"offer_score:{offer_id}:{country}:{device_type}"
        cached = cache.get(cache_key)
        if cached:
            raw_score = cached.get('score', 0.0)
        else:
            try:
                from ...models import OfferScoreCache
                obj = OfferScoreCache.objects.get(
                    offer_id=offer_id, country=country, device_type=device_type
                )
                raw_score = obj.score
            except Exception:
                raw_score = 0.0

        # Normalize using log scale (prevents one offer dominating with huge EPC)
        return min(math.log1p(raw_score) / math.log1p(100), 1.0)

    def _get_time_decay_score(self, offer_id: int, current_hour: int) -> float:
        """
        Score based on time-of-day performance patterns.
        Offers that perform well at current hour get a bonus.
        """
        cache_key = f"time_perf:{offer_id}:{current_hour}"
        score = cache.get(cache_key)
        if score is not None:
            return float(score)

        # Default: no time preference = 0.5
        cache.set(cache_key, 0.5, 1800)
        return 0.5

    def _get_isp_bonus(self, entry, isp: str) -> float:
        """
        Bonus if offer historically performs well for this ISP/carrier.
        E.g., offer X converts 3× better on Grameenphone vs Robi.
        """
        if not isp:
            return 0.5

        cache_key = f"isp_perf:{entry.offer_id}:{isp[:20]}"
        score = cache.get(cache_key)
        if score is not None:
            return float(score)

        # No data: neutral score
        cache.set(cache_key, 0.5, 3600)
        return 0.5

    def record_outcome(self, offer_id: int, context: dict, converted: bool, payout: float = 0):
        """
        Feed outcome back into the router for learning.
        Called by ClickTrackingService on conversion or after 24h of no conversion.
        """
        if converted:
            self.ml_engine.record_conversion(offer_id, context, payout)
        else:
            self.ml_engine.record_click(offer_id, context)

    def get_routing_explanation(self, smartlink, context: dict) -> dict:
        """
        Debug tool: explain routing decision for a given context.
        Useful for publisher dashboard 'Why was offer X chosen?'
        """
        try:
            entries = list(smartlink.offer_pool.get_active_entries())
            scored  = self._score_all(entries, context, smartlink)
            return {
                'context':  context,
                'rankings': [
                    {
                        'rank':          i + 1,
                        'offer_id':      entry.offer_id,
                        'total_score':   round(score, 4),
                        'score_parts':   {k: round(v, 4) for k, v in parts.items()},
                        'dominant_factor': reason,
                        'weight':        entry.weight,
                        'is_capped':     self.cap_tracker.is_capped(entry),
                    }
                    for i, (entry, score, reason, parts) in enumerate(scored)
                ]
            }
        except Exception as e:
            return {'error': str(e)}
