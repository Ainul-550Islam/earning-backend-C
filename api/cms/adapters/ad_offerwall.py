# api/cms/adapters/ad_offerwall.py
"""
Adapters for api.ad_networks and api.offerwall

  AdNetworkAdapter  — serve/track ad impressions and clicks inside CMS pages
  OfferwallAdapter  — fetch and display offerwall offers inside CMS widgets
"""
import logging
from typing import Optional, Dict, Any, List

from .base import BaseAdapter

logger = logging.getLogger('api.cms.adapters')


# ══════════════════════════════════════════════════════════════════════════════
# AD NETWORK ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class AdNetworkAdapter(BaseAdapter):
    """CMS → api.ad_networks interface."""

    _system_name = 'api.ad_networks'

    @classmethod
    def _check_available(cls):
        import api.ad_networks  # noqa

    @classmethod
    def get_ad(cls, placement: str, user=None, context: Optional[Dict] = None) -> Optional[Dict]:
        """
        Fetch the best ad for a CMS placement slot.
        Returns {'ad_id': str, 'html': str, 'type': str, 'impression_url': str} or None.
        """
        try:
            from api.ad_networks.services import AdNetworkService
            ad = AdNetworkService.get_ad(
                placement=placement,
                user=user,
                context=context or {},
            )
            return ad
        except ImportError:
            return cls._unavailable('get_ad', None)
        except Exception as e:
            logger.debug("[CMS→AdNetworks] get_ad(%s) failed: %s", placement, e)
            return None

    @classmethod
    def record_impression(cls, ad_id: str, user=None, placement: str = '') -> bool:
        """Record an ad impression for billing/reporting."""
        try:
            from api.ad_networks.services import AdNetworkService
            AdNetworkService.record_impression(ad_id=ad_id, user=user, placement=placement)
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.debug("[CMS→AdNetworks] record_impression failed: %s", e)
            return False

    @classmethod
    def record_click(cls, ad_id: str, user=None) -> bool:
        """Record an ad click."""
        try:
            from api.ad_networks.services import AdNetworkService
            AdNetworkService.record_click(ad_id=ad_id, user=user)
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.debug("[CMS→AdNetworks] record_click failed: %s", e)
            return False

    @classmethod
    def get_revenue_for_today(cls) -> float:
        """Return today's ad network revenue (for CMS dashboard widgets)."""
        try:
            from api.ad_networks.services import AdNetworkService
            return float(AdNetworkService.get_today_revenue() or 0)
        except (ImportError, Exception):
            return 0.0

    @classmethod
    def get_placements(cls) -> List[Dict]:
        """Return all configured ad placement slots."""
        try:
            from api.ad_networks.models import AdPlacement
            placements = AdPlacement.objects.filter(is_active=True).values(
                'slug', 'name', 'placement_type', 'width', 'height',
            )
            return list(placements)
        except (ImportError, Exception):
            return []

    @classmethod
    def is_ad_eligible(cls, user, placement: str) -> bool:
        """
        Check if the user is eligible to see ads for this placement
        (frequency capping, fraud checks, etc.).
        """
        try:
            from api.ad_networks.services import AdNetworkService
            return AdNetworkService.is_eligible(user=user, placement=placement)
        except ImportError:
            return True  # default: show ads
        except Exception:
            return True


# ══════════════════════════════════════════════════════════════════════════════
# OFFERWALL ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class OfferwallAdapter(BaseAdapter):
    """CMS → api.offerwall interface."""

    _system_name = 'api.offerwall'

    @classmethod
    def _check_available(cls):
        import api.offerwall  # noqa

    @classmethod
    def get_offers(
        cls,
        user,
        limit: int = 20,
        country: str = '',
        device: str = '',
        category: str = '',
    ) -> List[Dict]:
        """
        Fetch available offers for the CMS offerwall widget.
        Returns a list of offer dicts, ordered by payout desc.
        """
        try:
            from api.offerwall.services import OfferwallService
            return OfferwallService.get_offers(
                user=user,
                limit=limit,
                country=country,
                device=device,
                category=category,
            ) or []
        except ImportError:
            return cls._unavailable('get_offers', [])
        except Exception as e:
            logger.warning("[CMS→Offerwall] get_offers failed: %s", e)
            return []

    @classmethod
    def get_featured_offers(cls, user, limit: int = 5) -> List[Dict]:
        """Fetch high-payout featured offers for CMS hero/banner placement."""
        try:
            from api.offerwall.services import OfferwallService
            return OfferwallService.get_featured(user=user, limit=limit) or []
        except ImportError:
            return []
        except Exception:
            return []

    @classmethod
    def get_offer_categories(cls) -> List[Dict]:
        """Return offer categories for CMS filter UI."""
        try:
            from api.offerwall.models import OfferCategory
            return list(
                OfferCategory.objects.filter(is_active=True).values('slug', 'name', 'icon_url')
            )
        except (ImportError, Exception):
            return []

    @classmethod
    def get_offer_detail(cls, offer_id: str, user=None) -> Optional[Dict]:
        """Fetch full detail for a single offer."""
        try:
            from api.offerwall.services import OfferwallService
            return OfferwallService.get_offer_detail(offer_id=offer_id, user=user)
        except (ImportError, Exception):
            return None

    @classmethod
    def get_click_url(cls, offer_id: str, user, subid: str = '') -> str:
        """Generate a tracked click URL for a CMS offerwall offer."""
        try:
            from api.offerwall.services import OfferwallService
            return OfferwallService.get_click_url(offer_id=offer_id, user=user, subid=subid) or ''
        except (ImportError, Exception):
            return ''

    @classmethod
    def get_user_completed_offers(cls, user, limit: int = 50) -> List[Dict]:
        """Return offers the user has already completed."""
        try:
            from api.offerwall.services import OfferwallService
            return OfferwallService.get_completed(user=user, limit=limit) or []
        except (ImportError, Exception):
            return []

    @classmethod
    def get_wall_config(cls) -> Dict:
        """
        Return offerwall display config (currency name, logo, payout ratio)
        for rendering inside CMS templates.
        """
        try:
            from api.offerwall.models import OfferwallConfig
            config = OfferwallConfig.objects.first()
            if config:
                return {
                    'title': getattr(config, 'offerwall_title', 'Earn Rewards'),
                    'currency_name': getattr(config, 'currency', {}).name if hasattr(config, 'currency') else 'Coins',
                    'publisher_id': getattr(config, 'publisher_id', ''),
                }
            return {}
        except (ImportError, Exception):
            return {}
