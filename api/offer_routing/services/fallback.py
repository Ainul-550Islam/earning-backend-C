"""
Fallback Service for Offer Routing System

This module provides fallback functionality when no primary
routes match a user's profile or context.
"""

import logging
from typing import Dict, List, Any, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..models import (
    FallbackRule, DefaultOfferPool, EmptyResultHandler
)
from ..exceptions import FallbackError

User = get_user_model()
logger = logging.getLogger(__name__)


class FallbackService:
    """
    Service for handling fallback routing when no primary routes match.
    
    Provides fallback logic, default offer pools, and empty result handling.
    """
    
    def __init__(self):
        self.cache_service = None
        
        # Initialize services
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize fallback services."""
        try:
            from .cache import RoutingCacheService
            self.cache_service = RoutingCacheService()
        except ImportError as e:
            logger.error(f"Failed to initialize fallback services: {e}")
    
    def get_fallback_offers(self, user: User, context: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        Get fallback offers when no primary routes match.
        
        Args:
            user: User object
            context: User context
            
        Returns:
            List of fallback offers or None
        """
        try:
            # Get applicable fallback rules
            fallback_rules = self._get_applicable_fallback_rules(user, context)
            
            if not fallback_rules:
                return None
            
            # Use highest priority rule
            best_rule = max(fallback_rules, key=lambda x: x.priority)
            
            # Get offers based on rule type
            if best_rule.fallback_type == 'category':
                return self._get_category_fallback_offers(user, best_rule, context)
            elif best_rule.fallback_type == 'network':
                return self._get_network_fallback_offers(user, best_rule, context)
            elif best_rule.fallback_type == 'default':
                return self._get_default_fallback_offers(user, best_rule, context)
            elif best_rule.fallback_type == 'promotion':
                return self._get_promotion_fallback_offers(user, best_rule, context)
            elif best_rule.fallback_type == 'hide_section':
                return self._handle_hide_section(user, best_rule, context)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting fallback offers: {e}")
            return None
    
    def _get_applicable_fallback_rules(self, user: User, context: Dict[str, Any]) -> List[FallbackRule]:
        """Get fallback rules that apply to user and context."""
        try:
            rules = FallbackRule.objects.filter(
                tenant=user.tenant,
                is_active=True
            )
            
            applicable_rules = []
            
            for rule in rules:
                if self._rule_applies(rule, user, context):
                    applicable_rules.append(rule)
            
            return applicable_rules
            
        except Exception as e:
            logger.error(f"Error getting applicable fallback rules: {e}")
            return []
    
    def _rule_applies(self, rule: FallbackRule, user: User, context: Dict[str, Any]) -> bool:
        """Check if fallback rule applies to user and context."""
        try:
            # Check time constraints
            if not rule.applies_now(context.get('current_time')):
                return False
            
            # Check conditions
            if rule.conditions:
                if not self._evaluate_conditions(rule.conditions, user, context):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking if rule applies: {e}")
            return False
    
    def _evaluate_conditions(self, conditions: Dict[str, Any], user: User, context: Dict[str, Any]) -> bool:
        """Evaluate fallback rule conditions."""
        try:
            # This would implement complex condition evaluation
            # For now, return True as placeholder
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating conditions: {e}")
            return False
    
    def _get_category_fallback_offers(self, user: User, rule: FallbackRule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get category-based fallback offers."""
        try:
            category = rule.category
            
            if not category:
                return []
            
            # Get offers in this category
            from ..models import OfferRoute
            offers = OfferRoute.objects.filter(
                tenant=user.tenant,
                is_active=True,
                category=category
            )[:rule.max_offers or 10]
            
            return self._format_offers_for_fallback(offers, rule)
            
        except Exception as e:
            logger.error(f"Error getting category fallback offers: {e}")
            return []
    
    def _get_network_fallback_offers(self, user: User, rule: FallbackRule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get network-based fallback offers."""
        try:
            network = rule.network
            
            if not network:
                return []
            
            # Get offers from this network
            from ..models import OfferRoute
            offers = OfferRoute.objects.filter(
                tenant=user.tenant,
                is_active=True,
                network=network
            )[:rule.max_offers or 10]
            
            return self._format_offers_for_fallback(offers, rule)
            
        except Exception as e:
            logger.error(f"Error getting network fallback offers: {e}")
            return []
    
    def _get_default_fallback_offers(self, user: User, rule: FallbackRule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get default offer pool fallback offers."""
        try:
            if not rule.default_offer_pool:
                return []
            
            pool = rule.default_offer_pool
            
            # Get offers from pool based on rotation strategy
            if pool.rotation_strategy == 'random':
                offers = pool.get_random_offers(pool.max_offers)
            elif pool.rotation_strategy == 'weighted':
                offers = pool.get_weighted_offers(pool.max_offers)
            elif pool.rotation_strategy == 'priority':
                offers = pool.get_priority_offers(pool.max_offers)
            else:  # round_robin
                offers = pool.offers.all()[:pool.max_offers]
            
            return self._format_offers_for_fallback(offers, rule)
            
        except Exception as e:
            logger.error(f"Error getting default fallback offers: {e}")
            return []
    
    def _get_promotion_fallback_offers(self, user: User, rule: FallbackRule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get promotional fallback offers."""
        try:
            # Get promotional offers
            from ..models import OfferRoute
            offers = OfferRoute.objects.filter(
                tenant=user.tenant,
                is_active=True,
                is_promotional=True
            )[:rule.max_offers or 10]
            
            return self._format_offers_for_fallback(offers, rule)
            
        except Exception as e:
            logger.error(f"Error getting promotion fallback offers: {e}")
            return []
    
    def _handle_hide_section(self, user: User, rule: FallbackRule, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Handle hide section fallback."""
        try:
            # Return empty list to hide section
            return []
            
        except Exception as e:
            logger.error(f"Error handling hide section: {e}")
            return []
    
    def _format_offers_for_fallback(self, offers: List[Any], rule: FallbackRule) -> List[Dict[str, Any]]:
        """Format offers for fallback response."""
        try:
            formatted_offers = []
            
            for offer in offers:
                formatted_offer = {
                    'offer_id': offer.id,
                    'offer_name': offer.name,
                    'fallback_applied': True,
                    'fallback_rule_id': rule.id,
                    'fallback_rule_name': rule.name,
                    'fallback_type': rule.fallback_type,
                    'priority': rule.priority,
                    'score': 50.0,  # Default fallback score
                    'rank': len(formatted_offers) + 1
                }
                
                formatted_offers.append(formatted_offer)
            
            return formatted_offers
            
        except Exception as e:
            logger.error(f"Error formatting offers for fallback: {e}")
            return []
    
    def handle_empty_result(self, user: User, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle empty result when no offers can be shown.
        
        Args:
            user: User object
            context: User context
            
        Returns:
            Dictionary with empty result handling
        """
        try:
            # Get applicable empty result handlers
            handlers = self._get_applicable_empty_handlers(user, context)
            
            if not handlers:
                return {
                    'action': 'hide_section',
                    'message': '',
                    'redirect_url': '',
                    'custom_message': ''
                }
            
            # Use highest priority handler
            best_handler = max(handlers, key=lambda x: x.priority)
            
            # Execute handler action
            if best_handler.action_type == 'hide_section':
                return {
                    'action': 'hide_section',
                    'message': best_handler.action_value,
                    'redirect_url': '',
                    'custom_message': ''
                }
            elif best_handler.action_type == 'show_promo':
                return {
                    'action': 'show_promo',
                    'message': best_handler.action_value,
                    'redirect_url': '',
                    'custom_message': ''
                }
            elif best_handler.action_type == 'redirect_url':
                return {
                    'action': 'redirect_url',
                    'message': '',
                    'redirect_url': best_handler.redirect_url,
                    'custom_message': ''
                }
            elif best_handler.action_type == 'show_default':
                # Get default offers and return them
                default_offers = self._get_default_offers_for_handler(user, best_handler)
                return {
                    'action': 'show_default',
                    'message': '',
                    'redirect_url': '',
                    'custom_message': '',
                    'offers': default_offers
                }
            elif best_handler.action_type == 'custom_message':
                return {
                    'action': 'custom_message',
                    'message': '',
                    'redirect_url': '',
                    'custom_message': best_handler.custom_message
                }
            
            return {
                'action': 'hide_section',
                'message': '',
                'redirect_url': '',
                'custom_message': ''
            }
            
        except Exception as e:
            logger.error(f"Error handling empty result: {e}")
            return {
                'action': 'hide_section',
                'message': '',
                'redirect_url': '',
                'custom_message': '',
                'error': str(e)
            }
    
    def _get_applicable_empty_handlers(self, user: User, context: Dict[str, Any]) -> List[EmptyResultHandler]:
        """Get empty result handlers that apply to user and context."""
        try:
            handlers = EmptyResultHandler.objects.filter(
                tenant=user.tenant,
                is_active=True
            )
            
            applicable_handlers = []
            
            for handler in handlers:
                if handler.should_apply(context):
                    applicable_handlers.append(handler)
            
            return applicable_handlers
            
        except Exception as e:
            logger.error(f"Error getting applicable empty handlers: {e}")
            return []
    
    def _get_default_offers_for_handler(self, user: User, handler: EmptyResultHandler) -> List[Dict[str, Any]]:
        """Get default offers for empty result handler."""
        try:
            # This would get default offers based on handler configuration
            # For now, return empty list
            return []
            
        except Exception as e:
            logger.error(f"Error getting default offers for handler: {e}")
            return []
    
    def check_fallback_health(self) -> int:
        """Check health of fallback pools and rules."""
        try:
            checked_count = 0
            
            # Check default offer pools
            pools = DefaultOfferPool.objects.filter(is_active=True)
            
            for pool in pools:
                # Check if pool has offers
                if pool.offers.exists():
                    checked_count += 1
                else:
                    logger.warning(f"Empty fallback pool: {pool.name}")
            
            # Check fallback rules
            rules = FallbackRule.objects.filter(is_active=True)
            
            for rule in rules:
                # Check if rule has valid configuration
                if self._validate_fallback_rule(rule):
                    checked_count += 1
                else:
                    logger.warning(f"Invalid fallback rule: {rule.name}")
            
            logger.info(f"Checked {checked_count} fallback configurations")
            return checked_count
            
        except Exception as e:
            logger.error(f"Error checking fallback health: {e}")
            return 0
    
    def _validate_fallback_rule(self, rule: FallbackRule) -> bool:
        """Validate fallback rule configuration."""
        try:
            if rule.fallback_type == 'category' and not rule.category:
                return False
            
            if rule.fallback_type == 'network' and not rule.network:
                return False
            
            if rule.fallback_type == 'default' and not rule.default_offer_pool:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating fallback rule: {e}")
            return False
    
    def create_fallback_rule(self, user: User, rule_data: Dict[str, Any]) -> bool:
        """Create a new fallback rule."""
        try:
            rule = FallbackRule.objects.create(
                name=rule_data.get('name'),
                description=rule_data.get('description', ''),
                tenant=user.tenant,
                fallback_type=rule_data.get('fallback_type', 'category'),
                priority=rule_data.get('priority', 5),
                category=rule_data.get('category', ''),
                network=rule_data.get('network', ''),
                default_offer_pool_id=rule_data.get('default_offer_pool_id'),
                action_type=rule_data.get('action_type', 'show_default'),
                action_value=rule_data.get('action_value', ''),
                conditions=rule_data.get('conditions', {}),
                start_time=rule_data.get('start_time'),
                end_time=rule_data.get('end_time'),
                timezone=rule_data.get('timezone', 'UTC')
            )
            
            logger.info(f"Created fallback rule: {rule.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating fallback rule: {e}")
            return False
    
    def create_default_offer_pool(self, user: User, pool_data: Dict[str, Any]) -> bool:
        """Create a new default offer pool."""
        try:
            pool = DefaultOfferPool.objects.create(
                name=pool_data.get('name'),
                description=pool_data.get('description', ''),
                tenant=user.tenant,
                pool_type=pool_data.get('pool_type', 'general'),
                max_offers=pool_data.get('max_offers', 10),
                rotation_strategy=pool_data.get('rotation_strategy', 'random')
            )
            
            # Add offers to pool
            if 'offer_ids' in pool_data:
                pool.offers.add(*pool_data['offer_ids'])
            
            logger.info(f"Created default offer pool: {pool.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating default offer pool: {e}")
            return False
    
    def get_fallback_analytics(self, user: User, days: int = 30) -> Dict[str, Any]:
        """Get fallback analytics for user."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get fallback usage statistics
            from ..models import RoutingDecisionLog
            fallback_stats = RoutingDecisionLog.objects.filter(
                user=user,
                fallback_used=True,
                created_at__gte=cutoff_date
            ).aggregate(
                total_fallback_usage=Count('id'),
                unique_fallback_offers=Count('offer_id', distinct=True),
                avg_fallback_score=Avg('score')
            )
            
            # Get fallback rule usage
            rule_usage = RoutingDecisionLog.objects.filter(
                user=user,
                fallback_used=True,
                created_at__gte=cutoff_date
            ).values('route__name').annotate(
                usage_count=Count('id')
            ).order_by('-usage_count')
            
            return {
                'fallback_stats': fallback_stats,
                'rule_usage': list(rule_usage),
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting fallback analytics: {e}")
            return {}


# Singleton instance
fallback_service = FallbackService()
