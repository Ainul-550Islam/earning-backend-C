# api/offer_inventory/optimization_scale/server_side_rendering.py
"""Server-Side Rendering Helpers — Pre-rendered data for fast initial page loads."""
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class SSRHelper:
    """Pre-render offer data for fast initial page loads."""

    @staticmethod
    def get_initial_page_data(tenant=None, country: str = '',
                               device: str = 'mobile') -> dict:
        """
        All data needed for initial page render in one call.
        Reduces round trips for mobile SDK and web clients.
        """
        cache_key = f'ssr:initial:{tenant}:{country}:{device}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        from api.offer_inventory.repository import OfferRepository, FeatureFlagRepository
        from api.offer_inventory.models import OfferCategory, LoyaltyLevel

        offers     = OfferRepository.get_active_offers(tenant=tenant, country=country, page=1)
        categories = list(OfferCategory.objects.filter(is_active=True)
                          .values('id', 'name', 'slug', 'icon_url'))
        tiers      = list(LoyaltyLevel.objects.all()
                          .order_by('level_order')
                          .values('name', 'min_points', 'payout_bonus_pct'))
        features   = {
            'offerwall': FeatureFlagRepository.is_enabled('offer_wall', tenant),
            'referral' : FeatureFlagRepository.is_enabled('referral', tenant),
            'kyc'      : FeatureFlagRepository.is_enabled('kyc', tenant),
        }
        data = {
            'offers'       : [
                {
                    'id'         : str(o.id),
                    'title'      : o.title,
                    'reward'     : str(o.reward_amount),
                    'image_url'  : o.image_url or '',
                    'is_featured': o.is_featured,
                }
                for o in offers[:10]
            ],
            'categories'   : categories,
            'loyalty_tiers': tiers,
            'features'     : features,
            'rendered_at'  : timezone.now().isoformat(),
        }
        cache.set(cache_key, data, 60)   # Cache for 1 minute
        return data

    @staticmethod
    def get_offer_detail_ssr(offer_id: str) -> dict:
        """Pre-render offer detail page data."""
        cache_key = f'ssr:offer:{offer_id}'
        cached    = cache.get(cache_key)
        if cached:
            return cached

        from api.offer_inventory.repository import OfferRepository
        offer = OfferRepository.get_offer_by_id(offer_id)
        if not offer:
            return {}

        data = {
            'id'            : str(offer.id),
            'title'         : offer.title,
            'description'   : offer.description,
            'instructions'  : offer.instructions or '',
            'payout_amount' : str(offer.payout_amount),
            'reward_amount' : str(offer.reward_amount),
            'offer_url'     : offer.offer_url,
            'category'      : offer.category.name if offer.category else '',
            'network'       : offer.network.name if offer.network else '',
            'estimated_time': offer.estimated_time or '',
            'difficulty'    : offer.difficulty or 'easy',
            'is_featured'   : offer.is_featured,
            'rendered_at'   : timezone.now().isoformat(),
        }
        cache.set(cache_key, data, 120)
        return data

    @staticmethod
    def invalidate_offer_ssr(offer_id: str):
        """Invalidate SSR cache for an offer."""
        cache.delete(f'ssr:offer:{offer_id}')

    @staticmethod
    def invalidate_initial_page(tenant=None):
        """Invalidate initial page SSR cache."""
        try:
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f'ssr:initial:{tenant}:*')
            else:
                cache.delete(f'ssr:initial:{tenant}::mobile')
                cache.delete(f'ssr:initial:{tenant}::desktop')
        except Exception:
            pass
