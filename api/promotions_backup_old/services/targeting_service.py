# api/promotions/services/targeting_service.py
import logging
from django.core.cache import cache
logger = logging.getLogger('services.targeting')

class TargetingService:
    def find_matching_campaigns(self, user_id: int, platform: str, country: str, device: str) -> list:
        ck = f'target:match:{user_id}:{platform}:{country}'
        if cache.get(ck): return cache.get(ck)
        from api.promotions.models import Campaign
        from api.promotions.choices import CampaignStatus
        from django.db.models import Q
        campaigns = Campaign.objects.filter(
            status=CampaignStatus.ACTIVE,
            platform__name__iexact=platform,
        ).filter(
            Q(targeting__countries__contains=[country]) | Q(targeting__isnull=True)
        ).filter(
            Q(targeting__devices__contains=[device]) | Q(targeting__isnull=True)
        ).select_related('platform','category').values('id','title','bid_amount_usd','category__name')[:50]
        result = list(campaigns)
        cache.set(ck, result, timeout=60)
        return result

    def score_match(self, campaign_id: int, user_profile: dict) -> float:
        score = 0.5
        if user_profile.get('country') == 'BD': score += 0.1  # Example
        return min(1.0, score)
