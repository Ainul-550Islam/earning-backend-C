# api/offer_inventory/offer_search/search_engine.py
"""
Offer Search Engine — PostgreSQL full-text search for offers.
Fast, no external dependencies. Uses SearchVector + SearchRank.
"""
import logging
from decimal import Decimal
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class OfferSearchEngine:
    """Full-text offer search with filters and ranking."""

    @staticmethod
    def search(query: str = '', category: str = '', network_id: str = '',
                min_reward: Decimal = None, max_reward: Decimal = None,
                device_type: str = '', country: str = '',
                page: int = 1, page_size: int = 20,
                tenant=None) -> dict:
        """
        Search offers by keyword + filters.
        Uses PostgreSQL full-text search on title + description.
        """
        from api.offer_inventory.models import Offer

        qs = Offer.objects.filter(status='active').select_related('network', 'category')
        if tenant:
            qs = qs.filter(tenant=tenant)

        # Keyword search
        if query and query.strip():
            from django.contrib.postgres.search import SearchVector, SearchRank, SearchQuery
            try:
                sv    = SearchVector('title', weight='A') + SearchVector('description', weight='B')
                sq    = SearchQuery(query.strip())
                qs    = qs.annotate(rank=SearchRank(sv, sq)).filter(rank__gte=0.1).order_by('-rank', '-is_featured')
            except Exception:
                # Fallback to icontains if full-text fails
                from django.db.models import Q
                qs = qs.filter(
                    Q(title__icontains=query) | Q(description__icontains=query)
                )

        # Filters
        if category:
            qs = qs.filter(category__slug=category)
        if network_id:
            qs = qs.filter(network_id=network_id)
        if min_reward is not None:
            qs = qs.filter(reward_amount__gte=min_reward)
        if max_reward is not None:
            qs = qs.filter(reward_amount__lte=max_reward)
        if device_type:
            qs = qs.filter(
                visibility_rules__rule_type='device',
                visibility_rules__operator='include',
                visibility_rules__values__contains=[device_type]
            ) | qs.filter(visibility_rules__isnull=True)

        # Pagination
        total  = qs.count()
        start  = (page - 1) * page_size
        offers = list(qs[start:start + page_size])

        return {
            'query'      : query,
            'total'      : total,
            'page'       : page,
            'page_size'  : page_size,
            'pages'      : (total + page_size - 1) // page_size,
            'has_next'   : (page * page_size) < total,
            'results'    : [OfferSearchEngine._serialize(o) for o in offers],
        }

    @staticmethod
    def _serialize(offer) -> dict:
        return {
            'id'           : str(offer.id),
            'title'        : offer.title,
            'description'  : (offer.description or '')[:200],
            'reward_amount': str(offer.reward_amount),
            'payout_amount': str(offer.payout_amount),
            'category'     : offer.category.name if offer.category else '',
            'network'      : offer.network.name if offer.network else '',
            'is_featured'  : offer.is_featured,
            'estimated_time': offer.estimated_time or '',
            'difficulty'   : offer.difficulty or 'easy',
            'image_url'    : offer.image_url or '',
        }

    @staticmethod
    def autocomplete(query: str, limit: int = 10, tenant=None) -> list:
        """Fast autocomplete for offer title search."""
        if not query or len(query) < 2:
            return []
        cache_key = f'offer_ac:{query[:20]}:{tenant}'
        cached    = cache.get(cache_key)
        if cached:
            return cached
        from api.offer_inventory.models import Offer
        qs = Offer.objects.filter(
            status='active', title__icontains=query
        ).values('id', 'title', 'reward_amount')[:limit]
        if tenant:
            qs = qs.filter(tenant=tenant)
        result = [{'id': str(o['id']), 'title': o['title'], 'reward': str(o['reward_amount'])} for o in qs]
        cache.set(cache_key, result, 60)
        return result

    @staticmethod
    def get_filters(tenant=None) -> dict:
        """Return all available filter options."""
        from api.offer_inventory.models import OfferCategory, OfferNetwork
        categories = list(
            OfferCategory.objects.filter(is_active=True).values('slug', 'name')
        )
        networks = list(
            OfferNetwork.objects.filter(status='active').values('id', 'name')
        )
        return {
            'categories': categories,
            'networks'  : [{'id': str(n['id']), 'name': n['name']} for n in networks],
            'devices'   : ['mobile', 'desktop', 'tablet'],
            'sort_by'   : ['reward_high', 'reward_low', 'newest', 'featured'],
        }
