"""
Cap Enforcement Service for Offer Routing System

This module provides cap enforcement functionality to limit
offer exposure based on various caps and limits.
"""

import logging
from typing import Dict, List, Any, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Sum, Count
from ..models import (
    OfferRoutingCap, UserOfferCap, CapOverride
)
from ..constants import DEFAULT_CAP_DAILY, CAP_CACHE_TIMEOUT
from ..exceptions import CapExceededError

User = get_user_model()
logger = logging.getLogger(__name__)


class CapEnforcementService:
    """
    Service for enforcing offer caps and limits.
    
    Provides cap checking, enforcement, and management functionality
    for both global and user-specific caps.
    """
    
    def __init__(self):
        self.cache_service = None
        
        # Initialize services
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize cap enforcement services."""
        try:
            from .cache import RoutingCacheService
            self.cache_service = RoutingCacheService()
        except ImportError as e:
            logger.error(f"Failed to initialize cap enforcement services: {e}")
    
    def check_offer_cap(self, user: User, offer: Any) -> Dict[str, Any]:
        """
        Check if user can see an offer based on caps.
        
        Args:
            user: User object
            offer: Offer object
            
        Returns:
            Dictionary with cap check result
        """
        try:
            # Check user-specific caps
            user_cap_result = self._check_user_cap(user, offer)
            
            # Check global caps
            global_cap_result = self._check_global_cap(user, offer)
            
            # Apply overrides
            override_result = self._apply_cap_overrides(user, offer)
            
            # Determine final result
            allowed = True
            cap_type = None
            cap_value = None
            current_value = None
            
            # Check if any cap is exceeded
            if not user_cap_result['allowed']:
                allowed = False
                cap_type = user_cap_result['cap_type']
                cap_value = user_cap_result['cap_value']
                current_value = user_cap_result['current_value']
            elif not global_cap_result['allowed']:
                allowed = False
                cap_type = global_cap_result['cap_type']
                cap_value = global_cap_result['cap_value']
                current_value = global_cap_result['current_value']
            
            # Apply override if available
            if override_result['override_applied']:
                allowed = override_result['allowed']
                cap_value = override_result['new_cap_value']
            
            result = {
                'allowed': allowed,
                'cap_type': cap_type,
                'cap_value': cap_value,
                'current_value': current_value,
                'override_applied': override_result['override_applied'],
                'user_cap': user_cap_result,
                'global_cap': global_cap_result,
                'override': override_result
            }
            
            # Cache result
            self._cache_cap_result(offer.id, user.id, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking offer cap: {e}")
            return {
                'allowed': True,
                'cap_type': None,
                'cap_value': None,
                'current_value': None,
                'override_applied': False,
                'error': str(e)
            }
    
    def _check_user_cap(self, user: User, offer: Any) -> Dict[str, Any]:
        """Check user-specific cap for offer."""
        try:
            # Get user cap for this offer
            user_cap = UserOfferCap.objects.filter(
                user=user,
                offer=offer
            ).first()
            
            if not user_cap:
                # Create default cap
                user_cap = UserOfferCap.objects.create(
                    user=user,
                    offer=offer,
                    max_shows_per_day=DEFAULT_CAP_DAILY
                )
            
            # Check if daily cap is reached
            if user_cap.cap_type == 'daily':
                if user_cap.is_daily_cap_reached():
                    return {
                        'allowed': False,
                        'cap_type': 'daily',
                        'cap_value': user_cap.max_shows_per_day,
                        'current_value': user_cap.shown_today
                    }
            
            return {
                'allowed': True,
                'cap_type': user_cap.cap_type,
                'cap_value': user_cap.max_shows_per_day,
                'current_value': user_cap.shown_today
            }
            
        except Exception as e:
            logger.error(f"Error checking user cap: {e}")
            return {
                'allowed': True,
                'cap_type': None,
                'cap_value': None,
                'current_value': None,
                'error': str(e)
            }
    
    def _check_global_cap(self, user: User, offer: Any) -> Dict[str, Any]:
        """Check global cap for offer."""
        try:
            # Get global cap for this offer
            global_cap = OfferRoutingCap.objects.filter(
                offer=offer,
                tenant=user.tenant,
                is_active=True
            ).first()
            
            if not global_cap:
                return {
                    'allowed': True,
                    'cap_type': None,
                    'cap_value': None,
                    'current_value': None
                }
            
            # Check if cap is exceeded
            if not global_cap.is_active():
                return {
                    'allowed': True,
                    'cap_type': global_cap.cap_type,
                    'cap_value': global_cap.cap_value,
                    'current_value': global_cap.current_count
                }
            
            remaining_capacity = global_cap.get_remaining_capacity()
            
            if remaining_capacity <= 0:
                return {
                    'allowed': False,
                    'cap_type': global_cap.cap_type,
                    'cap_value': global_cap.cap_value,
                    'current_value': global_cap.current_count
                }
            
            return {
                'allowed': True,
                'cap_type': global_cap.cap_type,
                'cap_value': global_cap.cap_value,
                'current_value': global_cap.current_count
            }
            
        except Exception as e:
            logger.error(f"Error checking global cap: {e}")
            return {
                'allowed': True,
                'cap_type': None,
                'cap_value': None,
                'current_value': None,
                'error': str(e)
            }
    
    def _apply_cap_overrides(self, user: User, offer: Any) -> Dict[str, Any]:
        """Apply cap overrides for user and offer."""
        try:
            # Get active overrides for this offer and tenant
            overrides = CapOverride.objects.filter(
                offer=offer,
                tenant=user.tenant,
                is_active=True
            )
            
            for override in overrides:
                if override.is_valid_now():
                    # Apply override
                    original_cap_value = self._get_original_cap_value(user, offer)
                    new_cap_value = override.apply_override(original_cap_value)
                    
                    return {
                        'override_applied': True,
                        'allowed': new_cap_value > 0,
                        'new_cap_value': new_cap_value,
                        'override_type': override.override_type,
                        'override_reason': override.reason
                    }
            
            return {
                'override_applied': False,
                'allowed': True,
                'new_cap_value': None,
                'override_type': None,
                'override_reason': None
            }
            
        except Exception as e:
            logger.error(f"Error applying cap overrides: {e}")
            return {
                'override_applied': False,
                'allowed': True,
                'new_cap_value': None,
                'override_type': None,
                'override_reason': None,
                'error': str(e)
            }
    
    def _get_original_cap_value(self, user: User, offer: Any) -> int:
        """Get original cap value before overrides."""
        try:
            user_cap = UserOfferCap.objects.filter(
                user=user,
                offer=offer
            ).first()
            
            if user_cap:
                return user_cap.max_shows_per_day
            
            return DEFAULT_CAP_DAILY
            
        except Exception as e:
            logger.error(f"Error getting original cap value: {e}")
            return DEFAULT_CAP_DAILY
    
    def _cache_cap_result(self, offer_id: int, user_id: int, result: Dict[str, Any]):
        """Cache cap check result."""
        try:
            if self.cache_service:
                self.cache_service.set_user_cap(offer_id, user_id, result)
        except Exception as e:
            logger.warning(f"Error caching cap result: {e}")
    
    def increment_cap_usage(self, user: User, offer: Any) -> bool:
        """Increment cap usage for user and offer."""
        try:
            # Increment user cap
            user_cap = UserOfferCap.objects.filter(
                user=user,
                offer=offer
            ).first()
            
            if user_cap and user_cap.cap_type == 'daily':
                user_cap.increment_shown()
            
            # Increment global cap
            global_cap = OfferRoutingCap.objects.filter(
                offer=offer,
                tenant=user.tenant,
                is_active=True
            ).first()
            
            if global_cap:
                global_cap.increment_count()
            
            # Invalidate cache
            if self.cache_service:
                self.cache_service.delete_user_cap(offer.id, user.id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error incrementing cap usage: {e}")
            return False
    
    def reset_daily_caps(self) -> int:
        """Reset daily caps for all users."""
        try:
            reset_count = 0
            
            # Reset user daily caps
            user_caps = UserOfferCap.objects.filter(cap_type='daily')
            
            for cap in user_caps:
                cap.reset_daily_cap()
                reset_count += 1
            
            # Reset global daily caps
            global_caps = OfferRoutingCap.objects.filter(cap_type='daily')
            
            for cap in global_caps:
                cap.reset_daily_cap()
                reset_count += 1
            
            logger.info(f"Reset {reset_count} daily caps")
            return reset_count
            
        except Exception as e:
            logger.error(f"Error resetting daily caps: {e}")
            return 0
    
    def get_cap_status(self, user: User, offer: Any) -> Dict[str, Any]:
        """Get current cap status for user and offer."""
        try:
            user_cap = UserOfferCap.objects.filter(
                user=user,
                offer=offer
            ).first()
            
            global_cap = OfferRoutingCap.objects.filter(
                offer=offer,
                tenant=user.tenant,
                is_active=True
            ).first()
            
            status = {
                'user_cap': None,
                'global_cap': None,
                'overrides': []
            }
            
            if user_cap:
                status['user_cap'] = {
                    'cap_type': user_cap.cap_type,
                    'max_shows_per_day': user_cap.max_shows_per_day,
                    'shown_today': user_cap.shown_today,
                    'remaining_today': user_cap.max_shows_per_day - user_cap.shown_today,
                    'is_daily_cap_reached': user_cap.is_daily_cap_reached(),
                    'reset_at': user_cap.reset_at
                }
            
            if global_cap:
                status['global_cap'] = {
                    'cap_type': global_cap.cap_type,
                    'cap_value': global_cap.cap_value,
                    'current_count': global_cap.current_count,
                    'remaining_capacity': global_cap.get_remaining_capacity(),
                    'is_active': global_cap.is_active(),
                    'next_reset_at': global_cap.next_reset_at
                }
            
            # Get overrides
            overrides = CapOverride.objects.filter(
                offer=offer,
                tenant=user.tenant,
                is_active=True
            )
            
            for override in overrides:
                status['overrides'].append({
                    'override_type': override.override_type,
                    'override_cap': override.override_cap,
                    'valid_from': override.valid_from,
                    'valid_to': override.valid_to,
                    'is_valid_now': override.is_valid_now(),
                    'reason': override.reason
                })
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting cap status: {e}")
            return {}
    
    def create_cap_override(self, offer: Any, tenant: User, override_data: Dict[str, Any]) -> bool:
        """Create a cap override."""
        try:
            override = CapOverride.objects.create(
                offer=offer,
                tenant=tenant,
                override_type=override_data.get('override_type', 'increase'),
                override_cap=override_data.get('override_cap'),
                valid_from=override_data.get('valid_from'),
                valid_to=override_data.get('valid_to'),
                reason=override_data.get('reason', ''),
                approved_by=override_data.get('approved_by')
            )
            
            logger.info(f"Created cap override for offer {offer.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating cap override: {e}")
            return False
    
    def get_cap_analytics(self, tenant: User, days: int = 30) -> Dict[str, Any]:
        """Get cap analytics for tenant."""
        try:
            from datetime import timedelta
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Get cap usage statistics
            user_caps = UserOfferCap.objects.filter(
                offer__tenant=tenant,
                updated_at__gte=cutoff_date
            ).aggregate(
                total_user_caps=Count('id'),
                avg_shown_today=Avg('shown_today'),
                max_shown_today=Max('shown_today'),
                caps_reached=Count('id', filter=Q(shown_today__gte=F('max_shows_per_day')))
            )
            
            global_caps = OfferRoutingCap.objects.filter(
                tenant=tenant,
                updated_at__gte=cutoff_date
            ).aggregate(
                total_global_caps=Count('id'),
                avg_current_count=Avg('current_count'),
                max_current_count=Max('current_count'),
                caps_exceeded=Count('id', filter=Q(current_count__gte=F('cap_value')))
            )
            
            # Get override statistics
            overrides = CapOverride.objects.filter(
                tenant=tenant,
                created_at__gte=cutoff_date
            ).aggregate(
                total_overrides=Count('id'),
                active_overrides=Count('id', filter=Q(is_active=True))
            )
            
            return {
                'user_caps': user_caps,
                'global_caps': global_caps,
                'overrides': overrides,
                'period_days': days
            }
            
        except Exception as e:
            logger.error(f"Error getting cap analytics: {e}")
            return {}
    
    def optimize_caps(self, tenant: User) -> int:
        """Optimize caps based on usage patterns."""
        try:
            optimized_count = 0
            
            # This would implement cap optimization logic
            # For now, return placeholder
            
            return optimized_count
            
        except Exception as e:
            logger.error(f"Error optimizing caps: {e}")
            return 0


# Singleton instance
cap_service = CapEnforcementService()
