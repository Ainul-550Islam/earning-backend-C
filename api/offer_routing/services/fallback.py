"""
Fallback Service for Offer Routing System
"""
import logging
from typing import Dict, List, Any, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..models import FallbackRule, DefaultOfferPool, EmptyResultHandler
from ..exceptions import FallbackError

User = get_user_model()
logger = logging.getLogger(__name__)


class FallbackService:
    """Service for handling fallback routing when no primary routes match."""

    def __init__(self):
        self.cache_service = None
        self._initialize_services()

    def _initialize_services(self):
        try:
            from .cache import RoutingCacheService
            self.cache_service = RoutingCacheService()
        except ImportError as e:
            logger.error("Failed to initialize fallback services: %s", e)

    # ── Core fallback ──────────────────────────────────────────────────────────

    def get_fallback_offers(self, user_id: int, context: Dict,
                            fallback_rules: List = None) -> Dict[str, Any]:
        """Return offers from the best matching fallback rule."""
        fallback_rules = fallback_rules or []
        if not fallback_rules:
            return {'success': True, 'offers': [],
                    'metadata': {'fallback_used': False}}
        try:
            sorted_rules = sorted(fallback_rules, key=lambda r: r.priority)

            # Collect tenant ids from rules to look up pools in order
            tenant_ids = [r.tenant_id for r in sorted_rules]
            pools = list(DefaultOfferPool.objects.filter(
                tenant_id__in=tenant_ids, is_active=True
            ).order_by('id'))

            all_offers = []
            warning = None

            for idx, rule in enumerate(sorted_rules):
                pool = getattr(rule, 'default_offer_pool', None)
                if pool is None:
                    # Match pools to rules by index
                    rule_pools = [p for p in pools if p.tenant_id == rule.tenant_id]
                    if idx < len(rule_pools):
                        pool = rule_pools[idx]
                    elif rule_pools:
                        pool = rule_pools[0]

                if pool is not None:
                    rule_offers = list(pool.offers.filter(is_active=True))
                    if not rule_offers:
                        warning = 'Fallback pool is empty'
                    for offer in rule_offers:
                        all_offers.append({
                            'id': offer.id,
                            'name': getattr(offer, 'name', ''),
                            'fallback_rule': rule.id,
                        })

            meta = {
                'fallback_used': True,
                'fallback_rule': sorted_rules[0].id,
            }
            if warning:
                meta['warning'] = warning

            return {'success': True, 'offers': all_offers, 'metadata': meta}
        except Exception as e:
            logger.error("get_fallback_offers error: %s", e)
            return {'success': False, 'error': str(e), 'offers': [],
                    'metadata': {'fallback_used': False}}

    def handle_empty_result(self, user_id: int, context: Dict,
                            empty_result_handlers: List = None) -> Dict[str, Any]:
        """Handle a situation where primary routing returns no results."""
        handlers = empty_result_handlers or []
        if not handlers:
            return {'success': True, 'offers': [],
                    'metadata': {'empty_result_used': False}}
        try:
            for handler in handlers:
                action = getattr(handler, 'action_type', None) or getattr(handler, 'handler_type', None)
                if action in ('show_default', 'default_offer'):
                    # Get the offer id from action_value or config
                    offer_id = None
                    config = getattr(handler, 'config', None)
                    if config and isinstance(config, dict):
                        offer_id = config.get('default_offer_id')
                    elif getattr(handler, 'action_value', None):
                        try:
                            offer_id = int(handler.action_value)
                        except (ValueError, TypeError):
                            pass
                    if offer_id is not None:
                        return {
                            'success': True,
                            'offers': [{'id': offer_id}],
                            'metadata': {
                                'empty_result_used': True,
                                'empty_result_handler': handler.id,
                            },
                        }
            return {'success': True, 'offers': [],
                    'metadata': {'empty_result_used': False}}
        except Exception as e:
            logger.error("handle_empty_result error: %s", e)
            return {'success': False, 'error': str(e), 'offers': [],
                    'metadata': {'empty_result_used': False}}

    # ── Validation ─────────────────────────────────────────────────────────────

    def validate_fallback_rule(self, config: Dict) -> Dict[str, Any]:
        """Validate a fallback rule configuration dict."""
        errors = []
        valid_types = {'offer_pool', 'default_offer', 'category', 'network',
                       'price_tier', 'geo_based'}
        if not config.get('name', '').strip():
            errors.append('name')
        if config.get('fallback_type') not in valid_types:
            errors.append('fallback_type')
        priority = config.get('priority')
        if priority is None or (isinstance(priority, (int, float)) and priority <= 0):
            errors.append('priority')
        return {'valid': len(errors) == 0, 'errors': errors}

    def validate_empty_result_handler(self, config: Dict) -> Dict[str, Any]:
        """Validate an empty result handler configuration dict."""
        errors = []
        valid_types = {'default_offer', 'hide', 'redirect', 'custom',
                       'hide_section', 'show_promo', 'redirect_url',
                       'show_default', 'custom_message'}
        if not config.get('name', '').strip():
            errors.append('name')
        if config.get('handler_type') not in valid_types:
            errors.append('handler_type')
        cfg = config.get('config')
        if not cfg:
            errors.append('config')
        return {'valid': len(errors) == 0, 'errors': errors}

    # ── Statistics ─────────────────────────────────────────────────────────────

    def get_fallback_statistics(self) -> Dict[str, Any]:
        """Get system-wide fallback statistics."""
        try:
            total_rules = FallbackRule.objects.count()
            active_rules = FallbackRule.objects.filter(is_active=True).count()
            total_pools = DefaultOfferPool.objects.count()
            active_pools = DefaultOfferPool.objects.filter(is_active=True).count()
            return {
                'success': True,
                'total_rules': total_rules,
                'active_rules': active_rules,
                'inactive_rules': total_rules - active_rules,
                'total_pools': total_pools,
                'active_pools': active_pools,
                'inactive_pools': total_pools - active_pools,
            }
        except Exception as e:
            logger.error("get_fallback_statistics error: %s", e)
            return {'success': False, 'error': str(e)}

    def health_check(self) -> Dict[str, Any]:
        """Check fallback service health."""
        try:
            rule_count = FallbackRule.objects.filter(is_active=True).count()
            pool_count = DefaultOfferPool.objects.filter(is_active=True).count()
            return {
                'status': 'healthy',
                'fallback_rules': rule_count,
                'active_rules': rule_count,
                'active_pools': pool_count,
                'fallback_pools': pool_count,
                'offer_pools': pool_count,
                'empty_result_handlers': EmptyResultHandler.objects.count(),
                'cache_status': 'ok',
            }
        except Exception as e:
            return {'status': 'error', 'error': str(e)}


fallback_service = FallbackService()
