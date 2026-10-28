# api/cms/adapters/offer_systems.py
"""
Adapters for offer/publisher systems:
  api.postback, api.postback_engine, api.webhooks,
  api.offer_routing, api.offer_inventory, api.marketplace,
  api.advertiser_portal, api.publisher_tools, api.monetization_tools,
  api.inventory
"""
import logging
from typing import Optional, Dict, Any, List

from .base import BaseAdapter

logger = logging.getLogger('api.cms.adapters')


class PostbackAdapter(BaseAdapter):
    """CMS → api.postback / api.postback_engine."""

    _system_name = 'api.postback'

    @classmethod
    def _check_available(cls):
        import api.postback  # noqa

    @classmethod
    def fire(cls, event: str, user, data: Optional[Dict] = None) -> bool:
        """Fire a postback event for a user action from CMS."""
        try:
            from api.postback.services import PostbackService
            PostbackService.fire(event=event, user=user, data=data or {})
            return True
        except ImportError:
            # Try postback_engine fallback
            try:
                from api.postback_engine.services import PostbackEngineService
                PostbackEngineService.fire(event=event, user=user, data=data or {})
                return True
            except ImportError:
                return False
        except Exception as e:
            logger.warning("[CMS→Postback] fire(%s) failed: %s", event, e)
            return False

    @classmethod
    def on_offer_converted(cls, user, offer_id: str, payout_usd: float) -> bool:
        return cls.fire('offer_converted', user, {'offer_id': offer_id, 'payout_usd': payout_usd})

    @classmethod
    def on_survey_completed(cls, user, survey_id: str) -> bool:
        return cls.fire('survey_completed', user, {'survey_id': survey_id})


class WebhooksAdapter(BaseAdapter):
    """CMS → api.webhooks — outbound webhook dispatch."""

    _system_name = 'api.webhooks'

    @classmethod
    def _check_available(cls):
        import api.webhooks  # noqa

    @classmethod
    def dispatch(cls, event: str, payload: Dict, tenant_id: str = '') -> bool:
        """Dispatch a webhook event to registered subscribers."""
        try:
            from api.webhooks.services import WebhookService
            WebhookService.dispatch(event=event, payload=payload, tenant_id=tenant_id)
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.warning("[CMS→Webhooks] dispatch(%s) failed: %s", event, e)
            return False

    @classmethod
    def content_published(cls, content_type: str, content_id: str, data: Dict) -> bool:
        return cls.dispatch('cms.content.published', {
            'content_type': content_type, 'content_id': content_id, **data
        })

    @classmethod
    def reward_issued(cls, user_id: int, amount: float, source: str) -> bool:
        return cls.dispatch('cms.reward.issued', {
            'user_id': user_id, 'amount': amount, 'source': source
        })

    @classmethod
    def conversion_recorded(cls, user_id: int, offer_id: str, payout: float) -> bool:
        return cls.dispatch('cms.offer.converted', {
            'user_id': user_id, 'offer_id': offer_id, 'payout_usd': payout
        })


class OfferRoutingAdapter(BaseAdapter):
    """CMS → api.offer_routing — smart offer selection."""

    _system_name = 'api.offer_routing'

    @classmethod
    def _check_available(cls):
        import api.offer_routing  # noqa

    @classmethod
    def get_best_offer(cls, user, context: Optional[Dict] = None) -> Optional[Dict]:
        """
        Get the best offer for a user given their context.
        Returns offer dict or None.
        """
        try:
            from api.offer_routing.services import OfferRoutingService
            return OfferRoutingService.get_best(user=user, context=context or {})
        except ImportError:
            return None
        except Exception as e:
            logger.warning("[CMS→OfferRouting] get_best_offer failed: %s", e)
            return None

    @classmethod
    def get_offers_for_wall(cls, user, limit: int = 20, context: Optional[Dict] = None) -> List[Dict]:
        """Get an ordered offer list for the CMS offerwall."""
        try:
            from api.offer_routing.services import OfferRoutingService
            return OfferRoutingService.get_wall(user=user, limit=limit, context=context or {}) or []
        except ImportError:
            return []
        except Exception as e:
            logger.warning("[CMS→OfferRouting] get_offers_for_wall failed: %s", e)
            return []


class OfferInventoryAdapter(BaseAdapter):
    """CMS → api.offer_inventory / api.inventory."""

    _system_name = 'api.offer_inventory'

    @classmethod
    def _check_available(cls):
        import api.offer_inventory  # noqa

    @classmethod
    def get_offer(cls, offer_id: str) -> Optional[Dict]:
        """Fetch a single offer by ID."""
        try:
            from api.offer_inventory.services import OfferInventoryService
            return OfferInventoryService.get(offer_id=offer_id)
        except ImportError:
            return None
        except Exception:
            return None

    @classmethod
    def search_offers(cls, filters: Optional[Dict] = None, limit: int = 50) -> List[Dict]:
        """Search available offers with filters."""
        try:
            from api.offer_inventory.services import OfferInventoryService
            return OfferInventoryService.search(filters=filters or {}, limit=limit) or []
        except ImportError:
            return []
        except Exception:
            return []


class MarketplaceAdapter(BaseAdapter):
    """CMS → api.marketplace."""

    _system_name = 'api.marketplace'

    @classmethod
    def _check_available(cls):
        import api.marketplace  # noqa

    @classmethod
    def get_featured_items(cls, limit: int = 10) -> List[Dict]:
        try:
            from api.marketplace.services import MarketplaceService
            return MarketplaceService.get_featured(limit=limit) or []
        except (ImportError, Exception):
            return []

    @classmethod
    def purchase_item(cls, user, item_id: str) -> Dict:
        try:
            from api.marketplace.services import MarketplaceService
            return MarketplaceService.purchase(user=user, item_id=item_id) or {'success': False}
        except ImportError:
            return {'success': False, 'reason': 'marketplace_unavailable'}
        except Exception as e:
            return {'success': False, 'reason': str(e)}


class AdvertiserPortalAdapter(BaseAdapter):
    """CMS → api.advertiser_portal — campaign data for CMS display."""

    _system_name = 'api.advertiser_portal'

    @classmethod
    def _check_available(cls):
        import api.advertiser_portal  # noqa

    @classmethod
    def get_campaigns(cls, status: str = 'active', limit: int = 50) -> List[Dict]:
        try:
            from api.advertiser_portal.services import CampaignService
            return CampaignService.list(status=status, limit=limit) or []
        except (ImportError, Exception):
            return []

    @classmethod
    def get_campaign(cls, campaign_id: str) -> Optional[Dict]:
        try:
            from api.advertiser_portal.services import CampaignService
            return CampaignService.get(campaign_id=campaign_id)
        except (ImportError, Exception):
            return None


class PublisherToolsAdapter(BaseAdapter):
    """CMS → api.publisher_tools — publisher statistics for CMS widgets."""

    _system_name = 'api.publisher_tools'

    @classmethod
    def _check_available(cls):
        import api.publisher_tools  # noqa

    @classmethod
    def get_stats(cls, user, period: str = 'today') -> Dict:
        try:
            from api.publisher_tools.services import PublisherService
            return PublisherService.get_stats(user=user, period=period) or {}
        except (ImportError, Exception):
            return {}

    @classmethod
    def get_earnings(cls, user, period: str = 'today') -> float:
        stats = cls.get_stats(user, period)
        return float(stats.get('earnings_usd', 0))


class MonetizationAdapter(BaseAdapter):
    """CMS → api.monetization_tools."""

    _system_name = 'api.monetization_tools'

    @classmethod
    def _check_available(cls):
        import api.monetization_tools  # noqa

    @classmethod
    def get_revenue_data(cls, period: str = 'today') -> Dict:
        try:
            from api.monetization_tools.services import MonetizationService
            return MonetizationService.get_revenue(period=period) or {}
        except (ImportError, Exception):
            return {}


class PayoutAdapter(BaseAdapter):
    """CMS → api.payout_queue — payout requests."""

    _system_name = 'api.payout_queue'

    @classmethod
    def _check_available(cls):
        import api.payout_queue  # noqa

    @classmethod
    def request_payout(cls, user, amount_usd: float, method: str, account_id: str) -> Dict:
        try:
            from api.payout_queue.services import PayoutService
            result = PayoutService.request(
                user=user, amount_usd=amount_usd, method=method, account_id=account_id
            )
            return result or {'success': False}
        except ImportError:
            return {'success': False, 'reason': 'payout_queue_unavailable'}
        except Exception as e:
            return {'success': False, 'reason': str(e)}

    @classmethod
    def get_status(cls, payout_id: str) -> str:
        try:
            from api.payout_queue.models import PayoutRequest
            payout = PayoutRequest.objects.filter(pk=payout_id).first()
            return getattr(payout, 'status', 'unknown') if payout else 'not_found'
        except (ImportError, Exception):
            return 'unknown'


class DisasterRecoveryAdapter(BaseAdapter):
    """CMS → api.disaster_recovery / api.dr_integration."""

    _system_name = 'api.disaster_recovery'

    @classmethod
    def _check_available(cls):
        import api.disaster_recovery  # noqa

    @classmethod
    def create_backup(cls, label: str = 'cms_backup') -> bool:
        try:
            from api.disaster_recovery.services import DRService
            DRService.backup(label=label)
            return True
        except ImportError:
            try:
                from api.dr_integration.services import DRService
                DRService.backup(label=label)
                return True
            except ImportError:
                return False
        except Exception as e:
            logger.warning("[CMS→DR] create_backup failed: %s", e)
            return False

    @classmethod
    def health_check(cls) -> Dict:
        try:
            from api.disaster_recovery.services import DRService
            return DRService.health_check() or {'status': 'unknown'}
        except (ImportError, Exception):
            return {'status': 'unavailable'}
