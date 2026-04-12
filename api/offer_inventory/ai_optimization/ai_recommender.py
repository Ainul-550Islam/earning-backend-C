# api/offer_inventory/ai_optimization/ai_recommender.py
"""
AI Offer Recommender — Full Implementation.
Personalized offer recommendations based on:
  - User past conversion history
  - Category interest scores
  - Geo/device targeting match
  - Real-time EPC × CVR scoring
  - Collaborative filtering (users with similar behavior)
"""
import logging
from decimal import Decimal
from datetime import timedelta
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

RECOMMENDATION_CACHE_TTL = 300   # 5 min
MAX_RECOMMENDATIONS      = 50    # Max offers to score


class AIRecommender:
    """
    Personalized offer recommendation engine.
    Combines collaborative filtering + content-based filtering.
    """

    @classmethod
    def recommend_for_user(cls, user, country: str = '',
                            device: str = '', limit: int = 10) -> list:
        """
        Get personalized offer list for a user.
        Returns ranked list of Offer objects.
        """
        cache_key = f'ai_rec:{user.id}:{country}:{device}:{limit}'
        cached    = cache.get(cache_key)
        if cached is not None:
            # Re-fetch fresh objects (cache stores IDs)
            from api.offer_inventory.models import Offer
            return list(Offer.objects.filter(id__in=cached, status='active'))

        from api.offer_inventory.models import Offer, Conversion, UserInterest
        from .smart_link_logic import OfferScorer

        # Step 1: Exclude already completed offers
        completed_ids = set(
            Conversion.objects.filter(
                user=user, status__name='approved'
            ).values_list('offer_id', flat=True)
        )

        # Step 2: Get user interest categories (explicit + inferred)
        interest_map = cls._get_interest_map(user)

        # Step 3: Get candidate offers
        candidates = list(
            Offer.objects.filter(status='active')
            .exclude(id__in=completed_ids)
            .prefetch_related('caps', 'visibility_rules')[:MAX_RECOMMENDATIONS]
        )

        if not candidates:
            return []

        # Step 4: Score each offer
        scored = []
        for offer in candidates:
            score = cls._score_offer(offer, user, country, device,
                                      interest_map, OfferScorer)
            if score > 0:
                scored.append((score, offer))

        # Step 5: Sort and return top N
        scored.sort(key=lambda x: x[0], reverse=True)
        result  = [o for _, o in scored[:limit]]
        id_list = [str(o.id) for o in result]
        cache.set(cache_key, id_list, RECOMMENDATION_CACHE_TTL)

        return result

    @classmethod
    def _score_offer(cls, offer, user, country: str, device: str,
                      interest_map: dict, OfferScorer) -> Decimal:
        """Multi-factor offer score for personalization."""
        # Base AI score (EPC × CVR × Availability × Geo × Loyalty)
        base = OfferScorer.compute_score(offer, country, device, user)
        if base == 0:
            return Decimal('0')

        # Interest category bonus (+50% if matches user interest)
        interest_bonus = Decimal('1.0')
        if offer.category_id:
            interest_score = interest_map.get(str(offer.category_id), Decimal('0'))
            if interest_score > Decimal('0.5'):
                interest_bonus = Decimal('1.5')
            elif interest_score > Decimal('0.2'):
                interest_bonus = Decimal('1.2')

        # Featured bonus
        featured_bonus = Decimal('1.3') if offer.is_featured else Decimal('1.0')

        # Novelty bonus (newer offers ranked higher)
        days_old = (timezone.now() - offer.created_at).days
        novelty  = Decimal('1.2') if days_old < 7 else Decimal('1.0')

        return base * interest_bonus * featured_bonus * novelty

    @staticmethod
    def _get_interest_map(user) -> dict:
        """
        Returns {category_id: score} map.
        Combines explicit preferences + inferred from conversions.
        """
        from api.offer_inventory.models import UserInterest, Conversion
        from django.db.models import Count

        interest_map = {}

        # Explicit interests
        for interest in UserInterest.objects.filter(user=user):
            interest_map[str(interest.category_id)] = Decimal(str(interest.score))

        # Infer from conversion history (last 90 days)
        since = timezone.now() - timedelta(days=90)
        conv_cats = (
            Conversion.objects.filter(
                user=user, created_at__gte=since, status__name='approved'
            )
            .values('offer__category_id')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        max_count = max((c['count'] for c in conv_cats), default=1)
        for cat in conv_cats:
            cat_id = str(cat['offer__category_id'])
            inferred_score = Decimal(str(cat['count'])) / Decimal(str(max_count))
            if cat_id in interest_map:
                # Blend explicit and inferred
                interest_map[cat_id] = (interest_map[cat_id] + inferred_score) / 2
            else:
                interest_map[cat_id] = inferred_score

        return interest_map

    @staticmethod
    def update_interests_from_conversion(user, offer):
        """
        Update UserInterest scores after a successful conversion.
        Called from signals or PayoutEngine.
        """
        if not offer or not offer.category_id:
            return
        from api.offer_inventory.models import UserInterest
        obj, created = UserInterest.objects.get_or_create(
            user=user,
            category_id=offer.category_id,
            defaults={'score': Decimal('0.5')}
        )
        # Increase score by 0.1 per conversion, max 1.0
        obj.score = min(Decimal('1.0'), obj.score + Decimal('0.1'))
        obj.save(update_fields=['score'])

        # Invalidate recommendation cache
        cache.delete_pattern(f'ai_rec:{user.id}:*') if hasattr(cache, 'delete_pattern') else None

    @staticmethod
    def get_similar_offers(offer_id: str, limit: int = 5) -> list:
        """
        Find offers similar to a given offer.
        Based on: same category, similar payout range, similar CVR.
        """
        from api.offer_inventory.models import Offer

        try:
            offer = Offer.objects.get(id=offer_id)
        except Offer.DoesNotExist:
            return []

        payout_range_low  = offer.payout_amount * Decimal('0.5')
        payout_range_high = offer.payout_amount * Decimal('2.0')

        similar = Offer.objects.filter(
            status='active',
            category=offer.category,
            payout_amount__gte=payout_range_low,
            payout_amount__lte=payout_range_high,
        ).exclude(id=offer_id).order_by('-conversion_rate')[:limit]

        return list(similar)

    @staticmethod
    def get_trending_offers(days: int = 3, limit: int = 10) -> list:
        """
        Get trending offers — most conversions in last N days.
        """
        from api.offer_inventory.models import Conversion, Offer
        from django.db.models import Count

        since = timezone.now() - timedelta(days=days)
        trending_ids = (
            Conversion.objects.filter(
                created_at__gte=since, status__name='approved'
            )
            .values('offer_id')
            .annotate(conv_count=Count('id'))
            .order_by('-conv_count')
            .values_list('offer_id', flat=True)[:limit]
        )
        return list(Offer.objects.filter(id__in=trending_ids, status='active'))

    @staticmethod
    def get_high_value_offers(limit: int = 10) -> list:
        """
        High EPC + high payout offers — best for power users.
        """
        from api.offer_inventory.models import Offer
        return list(
            Offer.objects.filter(status='active', conversion_rate__gte=1)
            .order_by('-payout_amount', '-conversion_rate')[:limit]
        )

    @classmethod
    def collaborative_filter(cls, user, limit: int = 10) -> list:
        """
        Collaborative filtering:
        Find users with similar conversion patterns →
        recommend what they converted that current user hasn't.
        """
        from api.offer_inventory.models import Conversion, Offer
        from django.db.models import Count

        # Current user's converted offer IDs
        my_offer_ids = set(
            Conversion.objects.filter(
                user=user, status__name='approved'
            ).values_list('offer_id', flat=True)
        )

        if not my_offer_ids:
            # Cold start: return trending
            return cls.get_trending_offers(limit=limit)

        # Find users who converted same offers
        similar_users = (
            Conversion.objects.filter(
                offer_id__in=my_offer_ids,
                status__name='approved'
            )
            .exclude(user=user)
            .values('user_id')
            .annotate(overlap=Count('offer_id'))
            .order_by('-overlap')
            .values_list('user_id', flat=True)[:20]
        )

        if not similar_users:
            return cls.get_high_value_offers(limit=limit)

        # Find what those similar users converted that this user hasn't
        collab_offer_ids = (
            Conversion.objects.filter(
                user_id__in=similar_users,
                status__name='approved',
            )
            .exclude(offer_id__in=my_offer_ids)
            .values('offer_id')
            .annotate(count=Count('id'))
            .order_by('-count')
            .values_list('offer_id', flat=True)[:limit]
        )

        return list(Offer.objects.filter(id__in=collab_offer_ids, status='active'))
