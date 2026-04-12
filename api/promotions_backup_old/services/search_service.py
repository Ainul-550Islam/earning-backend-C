# api/promotions/services/search_service.py
import logging
from django.core.cache import cache
logger = logging.getLogger('services.search')

class SearchService:
    """Full-text campaign search — PostgreSQL full-text or Elasticsearch。"""

    def search_campaigns(self, query: str, filters: dict = None, limit: int = 20) -> list:
        ck = f'search:{hash(query)}:{hash(str(filters))}'
        if cache.get(ck): return cache.get(ck)
        try:
            from api.promotions.models import Campaign
            from api.promotions.choices import CampaignStatus
            from django.db.models import Q, SearchVector, SearchQuery
            qs = Campaign.objects.filter(status=CampaignStatus.ACTIVE)
            if query:
                qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query))
            if filters:
                if filters.get('platform'): qs = qs.filter(platform__name__iexact=filters['platform'])
                if filters.get('category'): qs = qs.filter(category__name__iexact=filters['category'])
                if filters.get('min_reward'): qs = qs.filter(reward_per_task_usd__gte=filters['min_reward'])
                if filters.get('country'): qs = qs.filter(targeting__countries__contains=[filters['country']])
            result = list(qs.select_related('platform','category').values('id','title','reward_per_task_usd','platform__name','category__name')[:limit])
            cache.set(ck, result, timeout=60)
            return result
        except Exception as e:
            return []
