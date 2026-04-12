# api/offer_inventory/ai_optimization/smart_link_logic.py
"""
SmartLink AI — Intelligent Offer Routing Engine.

Primary Algorithm: score = EPC × CVR × Availability × Geo_Bonus × Loyalty_Multiplier

Rules enforced:
  1. Daily cap exhausted → auto-rotate to next best (zero score = excluded)
  2. EPC × CVR = real revenue signal, not just raw payout
  3. Availability = remaining_cap_slots / total_cap (0.0–1.0), 0 = excluded
  4. Geo rule violations → score = 0 (hard exclude)
  5. All math uses Decimal — no float precision errors
"""
import logging
import random
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional

from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger(__name__)

SCORE_CACHE_TTL = 120   # 2 min
CAP_CACHE_TTL   = 30    # 30 sec — keep fresh, caps change fast
EPC_CACHE_TTL   = 300   # 5 min


# ════════════════════════════════════════════════════════════════
# OFFER SCORER
# ════════════════════════════════════════════════════════════════

class OfferScorer:

    @staticmethod
    def compute_score(offer, country: str = '', device: str = '', user=None) -> Decimal:
        """
        Composite score: EPC × CVR × Availability × Geo × Loyalty
        Returns Decimal('0') if offer should be excluded.
        """
        epc          = OfferScorer._get_epc(offer)
        cvr          = max(
            Decimal(str(offer.conversion_rate or '0')) / Decimal('100'),
            Decimal('0.001')
        )
        availability = OfferScorer._get_availability(offer)

        if availability == Decimal('0'):
            return Decimal('0')   # Hard exclude — cap exhausted

        geo_bonus  = OfferScorer._get_geo_bonus(offer, country)
        if geo_bonus == Decimal('0'):
            return Decimal('0')   # Hard exclude — geo rule violated

        loyalty    = OfferScorer._get_loyalty_multiplier(user)

        score = (epc * cvr * availability * geo_bonus * loyalty).quantize(
            Decimal('0.000001'), rounding=ROUND_HALF_UP
        )
        logger.debug(
            f'Score offer={offer.id} epc={epc} cvr={cvr} '
            f'avail={availability} geo={geo_bonus} loyalty={loyalty} => {score}'
        )
        return score

    @staticmethod
    def _get_epc(offer) -> Decimal:
        """EPC = Revenue / Clicks (7 days). Cached."""
        cache_key = f'offer_epc:{offer.id}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return Decimal(str(cached))

        from datetime import timedelta
        from api.offer_inventory.models import Click, Conversion
        since = timezone.now() - timedelta(days=7)
        try:
            clicks  = Click.objects.filter(
                offer=offer, created_at__gte=since, is_fraud=False
            ).count()
            revenue = (
                Conversion.objects.filter(
                    offer=offer, created_at__gte=since, status__name='approved'
                ).aggregate(total=Sum('payout_amount'))['total'] or Decimal('0')
            )
            epc = (
                Decimal(str(revenue)) / Decimal(str(clicks))
            ).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP) if clicks > 0 else Decimal('0')
        except Exception as e:
            logger.warning(f'EPC error offer={offer.id}: {e}')
            epc = Decimal(str(offer.payout_amount or '0'))

        cache.set(cache_key, str(epc), EPC_CACHE_TTL)
        return epc

    @staticmethod
    def _get_availability(offer) -> Decimal:
        """
        Returns fraction of cap remaining (0.0–1.0).
        Returns 0 if any binding cap is exhausted.
        """
        cache_key = f'offer_avail:{offer.id}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return Decimal(str(cached))

        now  = timezone.now()
        caps = offer.caps.all()

        if not caps.exists():
            cache.set(cache_key, '1.0', CAP_CACHE_TTL)
            return Decimal('1.0')

        min_avail = Decimal('1.0')
        for cap in caps:
            if cap.reset_at and now >= cap.reset_at:
                cap.current_count = 0
                cap.save(update_fields=['current_count'])

            if cap.cap_limit <= 0:
                continue

            remaining = cap.cap_limit - cap.current_count
            if remaining <= 0:
                cache.set(cache_key, '0', CAP_CACHE_TTL)
                return Decimal('0')

            frac = (
                Decimal(str(remaining)) / Decimal(str(cap.cap_limit))
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            min_avail = min(min_avail, frac)

        cache.set(cache_key, str(min_avail), CAP_CACHE_TTL)
        return min_avail

    @staticmethod
    def _get_geo_bonus(offer, country: str) -> Decimal:
        """Country match → 1.3×, explicit exclude → 0 (hard block)."""
        if not country:
            return Decimal('1.0')
        try:
            for rule in offer.visibility_rules.filter(rule_type='country', is_active=True):
                vals = rule.values or []
                if rule.operator == 'include' and country not in vals:
                    return Decimal('0')
                if rule.operator == 'exclude' and country in vals:
                    return Decimal('0')
                if rule.operator == 'include' and country in vals:
                    return Decimal('1.3')
        except Exception:
            pass
        return Decimal('1.0')

    @staticmethod
    def _get_loyalty_multiplier(user) -> Decimal:
        if not user:
            return Decimal('1.0')
        try:
            from api.offer_inventory.models import UserProfile
            profile = UserProfile.objects.select_related('loyalty_level').get(user=user)
            if profile.loyalty_level and profile.loyalty_level.payout_bonus_pct:
                return (
                    Decimal('1') + profile.loyalty_level.payout_bonus_pct / Decimal('100')
                ).quantize(Decimal('0.01'))
        except Exception:
            pass
        return Decimal('1.0')


# ════════════════════════════════════════════════════════════════
# SMARTLINK OPTIMIZER
# ════════════════════════════════════════════════════════════════

class SmartLinkOptimizer:

    @classmethod
    def select_best_offer(
        cls,
        offers: list,
        algorithm: str,
        user=None,
        country: str = '',
        device: str  = '',
    ) -> Optional[object]:
        """
        Returns the best offer. Auto-rotates past capped offers.
        Returns None if no offers available at all.
        """
        if not offers:
            return None

        # Step 1: geo/device filter
        eligible  = cls._filter_eligible(offers, country, device)
        if not eligible:
            return None

        # Step 2: remove cap-exhausted offers (core feature)
        available = [o for o in eligible if OfferScorer._get_availability(o) > Decimal('0')]
        if not available:
            logger.warning('SmartLink: all offers capped — no rotation possible.')
            return None

        # Step 3: route by algorithm
        if algorithm in ('ai_score', 'smart'):
            return cls._select_ai(available, country, device, user)
        if algorithm == 'highest_payout':
            return max(available, key=lambda o: Decimal(str(o.payout_amount or '0')))
        if algorithm == 'best_cvr':
            return max(available, key=lambda o: Decimal(str(o.conversion_rate or '0')))
        if algorithm == 'round_robin':
            key = hashlib.md5(str([o.id for o in available]).encode()).hexdigest()[:8]
            idx = cache.get(f'rr:{key}', 0)
            cache.set(f'rr:{key}', idx + 1, 3600)
            return available[idx % len(available)]
        return random.choice(available)

    @classmethod
    def _select_ai(cls, offers: list, country: str, device: str, user) -> object:
        """Weighted random selection from top 3 scored offers."""
        import hashlib
        scored = [
            (OfferScorer.compute_score(o, country, device, user), o)
            for o in offers
        ]
        scored = [(s, o) for s, o in scored if s > 0]

        if not scored:
            # All scored 0 — fallback
            return max(offers, key=lambda o: Decimal(str(o.payout_amount or '0')))

        scored.sort(key=lambda x: x[0], reverse=True)
        top3 = scored[:3]

        if len(top3) == 1:
            return top3[0][1]

        # Weighted random — proportional to score
        weights  = [float(s) for s, _ in top3]
        total    = sum(weights)
        rand_val = random.uniform(0, total)
        running  = 0.0
        for w, (_, offer) in zip(weights, top3):
            running += w
            if rand_val <= running:
                return offer
        return top3[0][1]

    @staticmethod
    def _filter_eligible(offers: list, country: str, device: str) -> list:
        result = []
        for o in offers:
            skip = False
            try:
                for rule in o.visibility_rules.filter(is_active=True):
                    vals = rule.values or []
                    if rule.rule_type == 'country' and country:
                        if rule.operator == 'include' and country not in vals:
                            skip = True; break
                        if rule.operator == 'exclude' and country in vals:
                            skip = True; break
                    if rule.rule_type == 'device' and device:
                        if rule.operator == 'include' and device not in vals:
                            skip = True; break
                        if rule.operator == 'exclude' and device in vals:
                            skip = True; break
            except Exception:
                pass
            if not skip:
                result.append(o)
        return result


# ════════════════════════════════════════════════════════════════
# CAP ROTATION MANAGER
# ════════════════════════════════════════════════════════════════

class CapRotationManager:

    @staticmethod
    def get_next_for_smartlink(smart_link, excluded_offer=None,
                               user=None, country='', device='') -> Optional[object]:
        """Rotate away from a capped offer."""
        qs = smart_link.offers.filter(status='active')
        if excluded_offer:
            qs = qs.exclude(id=excluded_offer.id)

        candidates = list(qs.prefetch_related('caps', 'visibility_rules'))
        if not candidates:
            return None

        return SmartLinkOptimizer.select_best_offer(
            offers=candidates, algorithm=smart_link.algorithm,
            user=user, country=country, device=device,
        )

    @staticmethod
    def invalidate_cap_cache(offer):
        cache.delete(f'offer_avail:{offer.id}')
        cache.delete(f'offer_epc:{offer.id}')


# ════════════════════════════════════════════════════════════════
# AUTO PAUSE ENGINE
# ════════════════════════════════════════════════════════════════

class AutoPauseEngine:
    MIN_CLICKS   = 50
    MIN_CVR      = Decimal('0.5')    # 0.5%
    MAX_FRAUD    = Decimal('20.0')   # 20%

    @classmethod
    def evaluate_and_pause(cls) -> list:
        from api.offer_inventory.models import Offer, OfferLog
        paused = []
        for offer in Offer.objects.filter(status='active').prefetch_related('caps', 'clicks'):
            d = cls._should_pause(offer)
            if d['pause']:
                Offer.objects.filter(id=offer.id, status='active').update(status='paused')
                OfferLog.objects.create(
                    offer=offer, old_status='active', new_status='paused',
                    note=f'Auto-paused: {d["reason"]}'
                )
                CapRotationManager.invalidate_cap_cache(offer)
                paused.append({'offer_id': str(offer.id), 'reason': d['reason']})
        return paused

    @classmethod
    def _should_pause(cls, offer) -> dict:
        total  = offer.clicks.count()
        if total < cls.MIN_CLICKS:
            return {'pause': False, 'reason': 'insufficient_data'}
        fraud  = offer.clicks.filter(is_fraud=True).count()
        f_rate = Decimal(str(fraud)) / Decimal(str(total)) * Decimal('100')
        cvr    = Decimal(str(offer.conversion_rate or '0'))
        if f_rate > cls.MAX_FRAUD:
            return {'pause': True, 'reason': f'fraud_rate:{f_rate:.1f}%'}
        if cvr < cls.MIN_CVR and total >= 200:
            return {'pause': True, 'reason': f'low_cvr:{cvr:.2f}%'}
        return {'pause': False, 'reason': 'ok'}


# ════════════════════════════════════════════════════════════════
# AI RECOMMENDER
# ════════════════════════════════════════════════════════════════

class AIRecommender:

    @staticmethod
    def recommend_for_user(user, country='', device='', limit=10) -> list:
        from api.offer_inventory.models import Offer, Conversion, UserInterest
        done_ids = set(
            Conversion.objects.filter(user=user, status__name='approved')
            .values_list('offer_id', flat=True)
        )
        interest_cats = list(
            UserInterest.objects.filter(user=user).order_by('-score')
            .values_list('category_id', flat=True)[:5]
        )
        offers = list(
            Offer.objects.filter(status='active')
            .exclude(id__in=done_ids)
            .prefetch_related('caps', 'visibility_rules')
        )
        scored = []
        for o in offers:
            s = OfferScorer.compute_score(o, country, device, user)
            if s == 0:
                continue
            if str(o.category_id) in [str(c) for c in interest_cats]:
                s = s * Decimal('1.5')
            scored.append((s, o))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [o for _, o in scored[:limit]]

    @staticmethod
    def update_interests(user, offer):
        if not offer.category_id:
            return
        from api.offer_inventory.models import UserInterest
        obj, _ = UserInterest.objects.get_or_create(
            user=user, category_id=offer.category_id,
            defaults={'score': Decimal('0.5')}
        )
        obj.score = min(Decimal('1.0'), obj.score + Decimal('0.1'))
        obj.save(update_fields=['score'])
