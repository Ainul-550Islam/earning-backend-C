# api/offer_inventory/rtb_engine/bid_floor_manager.py
"""Bid Floor Manager — Dynamic bid floor pricing per publisher/geo/device."""
import logging
from decimal import Decimal
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Default floor prices (eCPM) by geo tier
DEFAULT_FLOORS = {
    'tier1': Decimal('2.00'),   # US, GB, CA, AU
    'tier2': Decimal('0.80'),   # IN, BD, MY, BR
    'tier3': Decimal('0.30'),   # Other
}

GEO_TIER = {
    'US': 'tier1', 'GB': 'tier1', 'CA': 'tier1', 'AU': 'tier1',
    'DE': 'tier1', 'FR': 'tier1', 'JP': 'tier1', 'SG': 'tier1',
    'IN': 'tier2', 'BD': 'tier2', 'MY': 'tier2', 'BR': 'tier2',
    'ID': 'tier2', 'PH': 'tier2', 'TH': 'tier2', 'VN': 'tier2',
}


class BidFloorManager:
    """Dynamic bid floor calculation and management."""

    @classmethod
    def get_floor(cls, publisher_id: str, country: str = '',
                   device_type: str = 'mobile') -> Decimal:
        """
        Get the bid floor for a publisher+geo+device combo.
        Publishers can set custom floors — falls back to geo defaults.
        """
        cache_key = f'rtb:floor:{publisher_id}:{country}:{device_type}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return Decimal(str(cached))

        # Check publisher custom floor
        custom = cls._get_publisher_floor(publisher_id, country, device_type)
        if custom is not None:
            cache.set(cache_key, str(custom), 300)
            return custom

        # Geo-based default
        tier  = GEO_TIER.get(country, 'tier3')
        floor = DEFAULT_FLOORS[tier]

        # Device adjustment
        if device_type == 'mobile':
            floor = (floor * Decimal('1.2')).quantize(Decimal('0.01'))

        cache.set(cache_key, str(floor), 300)
        return floor

    @staticmethod
    def _get_publisher_floor(publisher_id: str, country: str, device_type: str):
        """Look up custom floor from DB (PublisherConfig model)."""
        try:
            from api.offer_inventory.models import PublisherConfig
            config = PublisherConfig.objects.get(
                publisher_id=publisher_id, is_active=True
            )
            # Check country-specific floor
            floors = config.floor_prices or {}
            country_floor = floors.get(country) or floors.get('default')
            if country_floor:
                return Decimal(str(country_floor))
        except Exception:
            pass
        return None

    @classmethod
    def set_publisher_floor(cls, publisher_id: str, floor: Decimal,
                             country: str = 'default') -> bool:
        """Set a custom bid floor for a publisher."""
        try:
            from api.offer_inventory.models import PublisherConfig
            config, _ = PublisherConfig.objects.get_or_create(
                publisher_id=publisher_id,
                defaults={'is_active': True, 'floor_prices': {}}
            )
            floors         = config.floor_prices or {}
            floors[country] = str(floor)
            PublisherConfig.objects.filter(publisher_id=publisher_id).update(
                floor_prices=floors
            )
            # Invalidate cache
            cache.delete_many([
                f'rtb:floor:{publisher_id}:{country}:mobile',
                f'rtb:floor:{publisher_id}:{country}:desktop',
            ])
            return True
        except Exception as e:
            logger.error(f'Set publisher floor error: {e}')
            return False

    @classmethod
    def get_floor_report(cls) -> list:
        """Report of active floor prices."""
        return [
            {'geo_tier': tier, 'floor_ecpm': float(floor)}
            for tier, floor in DEFAULT_FLOORS.items()
        ]
