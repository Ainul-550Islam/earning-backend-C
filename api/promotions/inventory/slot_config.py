# =============================================================================
# api/promotions/inventory/slot_config.py
# Slot Configuration — Ad inventory slot define ও manage করে
# প্রতিটি platform এর কতটা slot, কোন position, কত floor price
# =============================================================================

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger('inventory.slot_config')

CACHE_PREFIX_SLOT = 'inv:slot:{}'
CACHE_TTL_SLOT    = 3600


@dataclass
class SlotDefinition:
    slot_id:         str
    platform:        str
    slot_type:       str        # banner, video, native, interstitial
    position:        int        # 1 = premium position
    max_ads:         int        # এই slot এ একসাথে কতটা ad
    floor_price_usd: Decimal
    dimensions:      dict       # {'width': 728, 'height': 90}
    targeting_caps:  dict       # Targeting limitations
    is_active:       bool       = True
    fill_rate:       float      = 0.0    # Historical fill rate
    avg_revenue:     Decimal    = Decimal('0')
    priority:        int        = 1      # Higher = served first


@dataclass
class SlotAvailability:
    slot_id:    str
    available:  bool
    reason:     str          # 'available', 'capped', 'blacklisted', 'scheduled_off'
    next_available_at: Optional[float]


class SlotConfigManager:
    """
    Ad slot configuration ও availability management।

    Slots define করে:
    - YouTube: pre-roll, mid-roll, banner
    - Facebook: news feed, story, right column
    - Play Store: banner, interstitial
    - Custom: any platform

    slot_id format: {platform}_{type}_{position}
    e.g., youtube_preroll_1, facebook_newsfeed_1
    """

    # Default slot templates
    SLOT_TEMPLATES = {
        'youtube_preroll_1': {
            'platform': 'youtube', 'slot_type': 'video', 'position': 1,
            'max_ads': 1, 'floor_price_usd': Decimal('0.05'),
            'dimensions': {'duration_sec': 15},
        },
        'youtube_banner_1': {
            'platform': 'youtube', 'slot_type': 'banner', 'position': 2,
            'max_ads': 1, 'floor_price_usd': Decimal('0.02'),
            'dimensions': {'width': 728, 'height': 90},
        },
        'facebook_newsfeed_1': {
            'platform': 'facebook', 'slot_type': 'native', 'position': 1,
            'max_ads': 3, 'floor_price_usd': Decimal('0.04'),
            'dimensions': {'width': 1200, 'height': 628},
        },
        'play_store_banner_1': {
            'platform': 'play_store', 'slot_type': 'banner', 'position': 1,
            'max_ads': 1, 'floor_price_usd': Decimal('0.06'),
            'dimensions': {'width': 320, 'height': 50},
        },
    }

    def get_slot(self, slot_id: str) -> Optional[SlotDefinition]:
        """Slot configuration return করে।"""
        cache_key = CACHE_PREFIX_SLOT.format(slot_id)
        cached    = cache.get(cache_key)
        if cached:
            return SlotDefinition(**cached)

        # Template থেকে create করো
        template = self.SLOT_TEMPLATES.get(slot_id)
        if template:
            slot = SlotDefinition(slot_id=slot_id, targeting_caps={}, **template)
            cache.set(cache_key, slot.__dict__, timeout=CACHE_TTL_SLOT)
            return slot

        # Database এ check করো
        return self._load_from_db(slot_id)

    def check_availability(self, slot_id: str) -> SlotAvailability:
        """Slot available কিনা check করে।"""
        slot = self.get_slot(slot_id)
        if not slot:
            return SlotAvailability(slot_id=slot_id, available=False, reason='not_found', next_available_at=None)
        if not slot.is_active:
            return SlotAvailability(slot_id=slot_id, available=False, reason='inactive', next_available_at=None)
        return SlotAvailability(slot_id=slot_id, available=True, reason='available', next_available_at=None)

    def get_available_slots(self, platform: str = None, category: str = None) -> list[SlotDefinition]:
        """Available slots return করে।"""
        slots = []
        for slot_id, template in self.SLOT_TEMPLATES.items():
            if platform and template['platform'] != platform.lower():
                continue
            avail = self.check_availability(slot_id)
            if avail.available:
                slots.append(self.get_slot(slot_id))
        return [s for s in slots if s]

    def update_slot_stats(self, slot_id: str, filled: bool, revenue: Decimal = Decimal('0')) -> None:
        """Slot fill/revenue stats update করে।"""
        stats_key = CACHE_PREFIX_SLOT.format(f'stats:{slot_id}')
        stats     = cache.get(stats_key) or {'fills': 0, 'total': 0, 'revenue': 0.0}
        stats['total']   += 1
        stats['revenue'] += float(revenue)
        if filled:
            stats['fills'] += 1
        cache.set(stats_key, stats, timeout=86400)

    def _load_from_db(self, slot_id: str) -> Optional[SlotDefinition]:
        """Database থেকে custom slot load করে।"""
        try:
            from api.promotions.models import AdSlot
            db_slot = AdSlot.objects.get(slot_id=slot_id, is_active=True)
            return SlotDefinition(
                slot_id=slot_id, platform=db_slot.platform.name,
                slot_type=db_slot.slot_type, position=db_slot.position,
                max_ads=db_slot.max_ads, floor_price_usd=db_slot.floor_price_usd,
                dimensions=db_slot.dimensions or {}, targeting_caps={},
                is_active=True,
            )
        except Exception:
            return None
