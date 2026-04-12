# =============================================================================
# api/promotions/inventory/blacklist_manager.py
# Inventory Blacklist Manager — Slot/Domain/Category blacklist
# Harmful, irrelevant বা prohibited content block করে
# =============================================================================

import logging
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger('inventory.blacklist')
CACHE_PREFIX_INV_BL = 'inv:bl:{}'
CACHE_TTL_INV_BL    = 300


class InventoryBlacklistManager:
    """
    Inventory-level blacklist — ads.txt, content adjacency,
    brand safety rules manage করে।

    Separate from security_vault Blacklist (which is user/IP blacklist)।
    This is about AD CONTENT safety।
    """

    BRAND_UNSAFE_CATEGORIES = [
        'adult_content', 'gambling', 'weapons', 'tobacco',
        'alcohol', 'political', 'fake_news',
    ]

    def is_safe_placement(
        self,
        campaign_id:    int,
        slot_id:        str,
        page_category:  str = None,
    ) -> tuple[bool, str]:
        """Campaign + slot combination safe কিনা check করে।"""
        # Category safety check
        if page_category and page_category.lower() in self.BRAND_UNSAFE_CATEGORIES:
            return False, f'unsafe_category:{page_category}'

        # Campaign-specific slot blacklist
        blacklist_key = CACHE_PREFIX_INV_BL.format(f'camp:{campaign_id}:slots')
        blocked_slots = cache.get(blacklist_key) or []
        if slot_id in blocked_slots:
            return False, f'slot_blacklisted_for_campaign'

        # Global slot blacklist
        global_key = CACHE_PREFIX_INV_BL.format(f'slot:{slot_id}:blocked')
        if cache.get(global_key):
            return False, 'slot_globally_blocked'

        return True, 'safe'

    def blacklist_slot_for_campaign(self, campaign_id: int, slot_id: str, reason: str = '') -> None:
        """Specific campaign এর জন্য slot blacklist করে।"""
        key   = CACHE_PREFIX_INV_BL.format(f'camp:{campaign_id}:slots')
        slots = cache.get(key) or []
        if slot_id not in slots:
            slots.append(slot_id)
            cache.set(key, slots, timeout=86400)
            logger.info(f'Slot blacklisted: campaign={campaign_id} slot={slot_id} reason={reason}')

    def block_slot_globally(self, slot_id: str, reason: str = '', duration_hours: int = 24) -> None:
        """Slot globally block করে।"""
        key = CACHE_PREFIX_INV_BL.format(f'slot:{slot_id}:blocked')
        cache.set(key, {'reason': reason, 'blocked_at': __import__('time').time()},
                  timeout=duration_hours * 3600)
        logger.warning(f'Slot globally blocked: {slot_id} reason={reason}')

    def get_safe_slots_for_campaign(self, campaign_id: int, all_slots: list) -> list:
        """Campaign এর জন্য safe slots return করে।"""
        safe = []
        for slot_id in all_slots:
            is_safe, _ = self.is_safe_placement(campaign_id, slot_id)
            if is_safe:
                safe.append(slot_id)
        return safe
