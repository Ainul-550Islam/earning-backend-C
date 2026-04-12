# api/offer_inventory/affiliate_advanced/ad_creative_manager.py
"""Ad Creative Manager — Manage offer banners, videos, and native creatives."""
import logging
from django.db.models import F

logger = logging.getLogger(__name__)

CREATIVE_TYPES    = ['banner', 'video', 'native', 'icon']
MAX_PER_OFFER     = 10


class AdCreativeManager:
    """Manage offer ad creative assets."""

    @staticmethod
    def add(offer_id: str, creative_type: str, asset_url: str,
             width: int = None, height: int = None,
             duration_secs: int = None) -> object:
        """Add a new creative to an offer."""
        from api.offer_inventory.models import OfferCreative, Offer

        if creative_type not in CREATIVE_TYPES:
            raise ValueError(f'Unsupported type: {creative_type}. Use: {CREATIVE_TYPES}')

        offer = Offer.objects.get(id=offer_id)
        if offer.creatives.count() >= MAX_PER_OFFER:
            raise ValueError(f'Max {MAX_PER_OFFER} creatives per offer')

        return OfferCreative.objects.create(
            offer         =offer,
            creative_type =creative_type,
            asset_url     =asset_url,
            width         =width,
            height        =height,
            duration_secs =duration_secs,
            is_approved   =False,
        )

    @staticmethod
    def approve(creative_id: str) -> bool:
        from api.offer_inventory.models import OfferCreative
        return OfferCreative.objects.filter(id=creative_id).update(is_approved=True) > 0

    @staticmethod
    def reject(creative_id: str, reason: str = '') -> bool:
        from api.offer_inventory.models import OfferCreative
        return OfferCreative.objects.filter(id=creative_id).update(
            is_approved=False
        ) > 0

    @staticmethod
    def get_best(offer, creative_type: str = 'banner'):
        """Get the highest-performing approved creative."""
        from api.offer_inventory.models import OfferCreative
        return (
            OfferCreative.objects.filter(
                offer=offer, creative_type=creative_type, is_approved=True
            )
            .order_by('-click_count').first()
        )

    @staticmethod
    def record_click(creative_id: str):
        """Increment click count for a creative."""
        from api.offer_inventory.models import OfferCreative
        OfferCreative.objects.filter(id=creative_id).update(
            click_count=F('click_count') + 1
        )

    @staticmethod
    def get_performance(offer_id: str) -> list:
        """Performance stats for all creatives of an offer."""
        from api.offer_inventory.models import OfferCreative
        return list(
            OfferCreative.objects.filter(offer_id=offer_id)
            .values('id', 'creative_type', 'asset_url',
                    'click_count', 'is_approved')
            .order_by('-click_count')
        )
