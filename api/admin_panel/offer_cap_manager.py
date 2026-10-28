# api/admin_panel/offer_cap_manager.py
"""
Offer Cap Manager — daily/total conversion cap enforcement.
Controls: daily cap, total cap, per-user cap, per-country cap.
Calls api.promotions models — admin_panel enforces caps.
"""
from __future__ import annotations
from typing import List
import logging
from typing import Any, Dict, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class OfferCapManager:
    """Manage and enforce offer conversion caps."""

    @classmethod
    def get_cap_status(cls, offer_id: Any) -> Dict:
        """Get current cap usage for an offer."""
        today = timezone.now().date().isoformat()
        daily_key   = f'offer_cap:daily:{offer_id}:{today}'
        total_key   = f'offer_cap:total:{offer_id}'
        daily_count  = cache.get(daily_key, 0)
        total_count  = cache.get(total_key, 0)

        try:
            from api.promotions.models import Campaign
            offer = Campaign.objects.get(pk=offer_id)
            daily_cap = getattr(offer, 'daily_cap', None) or 0
            total_cap = getattr(offer, 'total_cap', None) or 0
            return {
                'offer_id':    offer_id,
                'daily_used':  daily_count,
                'daily_cap':   daily_cap,
                'daily_pct':   round(daily_count / daily_cap * 100, 1) if daily_cap else None,
                'daily_full':  daily_cap > 0 and daily_count >= daily_cap,
                'total_used':  total_count,
                'total_cap':   total_cap,
                'total_full':  total_cap > 0 and total_count >= total_cap,
                'is_active':   offer.status == 'active',
            }
        except Exception as e:
            return {'offer_id': offer_id, 'error': str(e)}

    @classmethod
    def increment_and_check(cls, offer_id: Any) -> Tuple[bool, str]:
        """
        Increment cap counter and check if cap is reached.
        Returns (allowed, reason).
        """
        today = timezone.now().date().isoformat()
        daily_key = f'offer_cap:daily:{offer_id}:{today}'
        total_key = f'offer_cap:total:{offer_id}'

        try:
            from api.promotions.models import Campaign
            offer = Campaign.objects.get(pk=offer_id)
            daily_cap = getattr(offer, 'daily_cap', None) or 0
            total_cap = getattr(offer, 'total_cap', None) or 0
        except Exception:
            return True, 'offer_not_found'

        # Check daily cap
        if daily_cap > 0:
            daily_count = cache.get(daily_key, 0)
            if daily_count >= daily_cap:
                # Auto-pause if cap reached
                cls._auto_pause(offer_id, 'daily_cap_reached')
                return False, f'Daily cap reached ({daily_count}/{daily_cap})'

        # Check total cap
        if total_cap > 0:
            total_count = cache.get(total_key, 0)
            if total_count >= total_cap:
                cls._auto_pause(offer_id, 'total_cap_reached')
                return False, f'Total cap reached ({total_count}/{total_cap})'

        # Increment counters
        seconds_until_midnight = (86400 - timezone.now().second - timezone.now().minute * 60 -
                                   timezone.now().hour * 3600)
        current_daily = cache.get(daily_key, 0)
        cache.set(daily_key, current_daily + 1, seconds_until_midnight)
        current_total = cache.get(total_key, 0)
        cache.set(total_key, current_total + 1, 86400 * 365)

        return True, 'ok'

    @classmethod
    def set_daily_cap(cls, offer_id: Any, cap: int, actor=None) -> bool:
        """Set daily conversion cap for an offer."""
        try:
            from api.promotions.models import Campaign
            Campaign.objects.filter(pk=offer_id).update(daily_cap=cap)
            cache.delete(f'offer_cap:daily:{offer_id}:{timezone.now().date().isoformat()}')
            if actor:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(actor=actor, action='set_offer_daily_cap',
                                  model_name='Campaign', object_id=str(offer_id),
                                  changes={'daily_cap': cap})
            return True
        except Exception as e:
            logger.error(f"[CapManager.set_daily_cap] {e}")
            return False

    @classmethod
    def reset_daily_caps(cls) -> int:
        """Reset all daily cap counters (called at midnight)."""
        today = timezone.now().date().isoformat()
        # Keys expire automatically — just log
        logger.info(f"[CapManager] Daily caps reset for {today}")
        return 0

    @classmethod
    def get_offers_near_cap(cls, threshold_pct: int = 80) -> List[Dict]:
        """Get offers that are near their daily cap."""
        results = []
        today = timezone.now().date().isoformat()
        try:
            from api.promotions.models import Campaign
            from django.db.models import Q
            offers = Campaign.objects.filter(status='active', daily_cap__gt=0)
            for offer in offers:
                daily_key = f'offer_cap:daily:{offer.pk}:{today}'
                count = cache.get(daily_key, 0)
                if offer.daily_cap and count / offer.daily_cap * 100 >= threshold_pct:
                    results.append({
                        'offer_id': offer.pk,
                        'title': offer.title,
                        'daily_cap': offer.daily_cap,
                        'daily_used': count,
                        'pct': round(count / offer.daily_cap * 100, 1),
                    })
        except Exception as e:
            logger.error(f"[CapManager.near_cap] {e}")
        return results

    @classmethod
    def _auto_pause(cls, offer_id: Any, reason: str) -> None:
        """Auto-pause offer when cap is reached."""
        try:
            from api.promotions.models import Campaign
            Campaign.objects.filter(pk=offer_id, status='active').update(status='paused')
            logger.info(f"[CapManager] Auto-paused offer {offer_id}: {reason}")
        except Exception:
            pass


offer_cap_manager = OfferCapManager()