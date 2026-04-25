"""
Cap Enforcement Service

Checks and updates offer caps for the offer
routing system to prevent over-exposure.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, Sum, F
from django.core.cache import cache
from django.db import transaction
from ....models import (
    OfferRoute, OfferRoutingCap, UserOfferCap, CapOverride,
    UserOfferHistory, RoutingDecisionLog
)
from ....constants import (
    CAP_CACHE_TIMEOUT, CAP_CHECK_CACHE_TIMEOUT,
    DEFAULT_DAILY_CAP, DEFAULT_WEEKLY_CAP, DEFAULT_MONTHLY_CAP,
    CAP_RESET_HOURS, CAP_OVERRIDE_CACHE_TIMEOUT
)
from ....exceptions import CapError, CapExceededError
from ....utils import get_cap_key, calculate_cap_usage

User = get_user_model()
logger = logging.getLogger(__name__)


class CapEnforcementService:
    """
    Service for enforcing offer caps and limits.
    
    Manages and enforces various types of caps:
    - Daily caps (per user per offer)
    - Weekly caps (per user per offer)
    - Monthly caps (per user per offer)
    - Global caps (per offer across all users)
    - Category caps (per user per category)
    - Custom caps with time windows
    
    Performance targets:
    - Cap check: <3ms per check
    - Cap update: <5ms per update
    - Cache hit rate: >95%
    """
    
    def __init__(self):
        self.cache_service = cache
        self.cap_stats = {
            'total_checks': 0,
            'total_updates': 0,
            'cache_hits': 0,
            'cap_exceeded': 0,
            'avg_check_time_ms': 0.0,
            'avg_update_time_ms': 0.0
        }
        
        # Cap types and their reset schedules
        self.cap_types = {
            'daily': {'reset_hours': 24, 'field': 'daily_count'},
            'weekly': {'reset_hours': 168, 'field': 'weekly_count'},
            'monthly': {'reset_hours': 720, 'field': 'monthly_count'},
            'hourly': {'reset_hours': 1, 'field': 'hourly_count'},
            'session': {'reset_hours': 0, 'field': 'session_count'}  # Session caps don't auto-reset
        }
    
    def can_show_offer(self, user: User, offer: OfferRoute, 
                      context: Dict[str, Any] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if offer can be shown to user based on caps.
        
        Args:
            user: User object
            offer: Offer object
            context: Additional context
            
        Returns:
            Tuple of (can_show, cap_info)
        """
        try:
            start_time = timezone.now()
            
            # Check cache first
            cache_key = get_cap_key(user.id, offer.id, 'can_show')
            cached_result = self.cache_service.get(cache_key)
            
            if cached_result is not None:
                self.cap_stats['cache_hits'] += 1
                return cached_result['can_show'], cached_result['cap_info']
            
            # Get all applicable caps
            caps = self._get_applicable_caps(user, offer)
            
            if not caps:
                result = {'can_show': True, 'cap_info': {'reason': 'no_caps'}}
                self.cache_service.set(cache_key, result, CAP_CHECK_CACHE_TIMEOUT)
                return True, result['cap_info']
            
            # Check each cap type
            cap_results = {}
            
            # Check user-specific caps
            user_cap_result = self._check_user_caps(user, offer, caps)
            cap_results['user_caps'] = user_cap_result
            
            # Check global caps
            global_cap_result = self._check_global_caps(offer, caps)
            cap_results['global_caps'] = global_cap_result
            
            # Check category caps
            category_cap_result = self._check_category_caps(user, offer, caps)
            cap_results['category_caps'] = category_cap_result
            
            # Check custom caps
            custom_cap_result = self._check_custom_caps(user, offer, caps, context)
            cap_results['custom_caps'] = custom_cap_result
            
            # Check overrides
            override_result = self._check_cap_overrides(user, offer, caps)
            cap_results['overrides'] = override_result
            
            # Determine final decision
            can_show, reason = self._make_cap_decision(cap_results, override_result)
            
            cap_info = {
                'user_id': user.id,
                'offer_id': offer.id,
                'can_show': can_show,
                'reason': reason,
                'cap_results': cap_results,
                'checked_at': timezone.now().isoformat()
            }
            
            result = {'can_show': can_show, 'cap_info': cap_info}
            
            # Cache result
            self.cache_service.set(cache_key, result, CAP_CHECK_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_check_stats(elapsed_ms)
            
            if not can_show:
                self.cap_stats['cap_exceeded'] += 1
                logger.info(f"Cap exceeded for user {user.id}, offer {offer.id}: {reason}")
            
            return can_show, cap_info
            
        except Exception as e:
            logger.error(f"Error checking caps for user {user.id}, offer {offer.id}: {e}")
            return True, {'error': str(e)}
    
    def increment_cap(self, user: User, offer: OfferRoute, 
                     context: Dict[str, Any] = None) -> bool:
        """
        Increment cap counters for a user-offer pair.
        
        Args:
            user: User object
            offer: Offer object
            context: Additional context
            
        Returns:
            True if successful, False otherwise
        """
        try:
            start_time = timezone.now()
            
            # Get applicable caps
            caps = self._get_applicable_caps(user, offer)
            
            if not caps:
                return True  # No caps to increment
            
            # Increment counters atomically
            with transaction.atomic():
                # Increment user caps
                self._increment_user_caps(user, offer, caps)
                
                # Increment global caps
                self._increment_global_caps(offer, caps)
                
                # Increment category caps
                self._increment_category_caps(user, offer, caps)
                
                # Increment custom caps
                self._increment_custom_caps(user, offer, caps, context)
            
            # Clear relevant cache
            self._clear_cap_cache(user.id, offer.id)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_update_stats(elapsed_ms)
            
            logger.debug(f"Incremented caps for user {user.id}, offer {offer.id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error incrementing caps for user {user.id}, offer {offer.id}: {e}")
            return False
    
    def _get_applicable_caps(self, user: User, offer: OfferRoute) -> List[Dict[str, Any]]:
        """Get all applicable caps for user and offer."""
        try:
            caps = []
            
            # Get offer-level caps
            offer_caps = OfferRoutingCap.objects.filter(
                offer=offer,
                is_active=True
            ).order_by('priority')
            
            for cap in offer_caps:
                caps.append({
                    'id': cap.id,
                    'type': cap.cap_type,
                    'value': cap.cap_value,
                    'time_window': cap.time_window,
                    'time_unit': cap.time_unit,
                    'reset_schedule': cap.reset_schedule,
                    'priority': cap.priority,
                    'conditions': cap.conditions or {},
                    'is_global': False
                })
            
            # Get user-specific caps
            user_caps = UserOfferCap.objects.filter(
                user=user,
                offer=offer,
                is_active=True
            ).order_by('priority')
            
            for cap in user_caps:
                caps.append({
                    'id': cap.id,
                    'type': cap.cap_type,
                    'value': cap.cap_value,
                    'time_window': cap.time_window,
                    'time_unit': cap.time_unit,
                    'reset_schedule': cap.reset_schedule,
                    'priority': cap.priority,
                    'conditions': cap.conditions or {},
                    'is_global': False,
                    'is_user_specific': True
                })
            
            # Sort by priority (lower number = higher priority)
            caps.sort(key=lambda x: x['priority'])
            
            return caps
            
        except Exception as e:
            logger.error(f"Error getting applicable caps: {e}")
            return []
    
    def _check_user_caps(self, user: User, offer: OfferRoute, 
                         caps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check user-specific caps."""
        try:
            user_cap_results = []
            
            for cap in caps:
                if cap['is_user_specific']:
                    result = self._check_single_cap(user, offer, cap)
                    user_cap_results.append(result)
            
            # Find most restrictive cap
            if user_cap_results:
                most_restrictive = min(user_cap_results, key=lambda x: x['remaining'])
                
                return {
                    'can_show': most_restrictive['remaining'] > 0,
                    'remaining': most_restrictive['remaining'],
                    'cap_type': most_restrictive['cap_type'],
                    'cap_value': most_restrictive['cap_value'],
                    'reset_time': most_restrictive['reset_time'],
                    'details': user_cap_results
                }
            
            return {
                'can_show': True,
                'remaining': float('inf'),
                'cap_type': None,
                'cap_value': None,
                'reset_time': None,
                'details': []
            }
            
        except Exception as e:
            logger.error(f"Error checking user caps: {e}")
            return {'can_show': True, 'error': str(e)}
    
    def _check_global_caps(self, offer: OfferRoute, 
                          caps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check global caps."""
        try:
            global_cap_results = []
            
            for cap in caps:
                if cap['is_global']:
                    result = self._check_global_single_cap(offer, cap)
                    global_cap_results.append(result)
            
            # Find most restrictive cap
            if global_cap_results:
                most_restrictive = min(global_cap_results, key=lambda x: x['remaining'])
                
                return {
                    'can_show': most_restrictive['remaining'] > 0,
                    'remaining': most_restrictive['remaining'],
                    'cap_type': most_restrictive['cap_type'],
                    'cap_value': most_restrictive['cap_value'],
                    'reset_time': most_restrictive['reset_time'],
                    'details': global_cap_results
                }
            
            return {
                'can_show': True,
                'remaining': float('inf'),
                'cap_type': None,
                'cap_value': None,
                'reset_time': None,
                'details': []
            }
            
        except Exception as e:
            logger.error(f"Error checking global caps: {e}")
            return {'can_show': True, 'error': str(e)}
    
    def _check_category_caps(self, user: User, offer: OfferRoute, 
                           caps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check category-based caps."""
        try:
            category_cap_results = []
            offer_category = getattr(offer, 'category', 'general')
            
            for cap in caps:
                if cap.get('category_based', False) or cap['cap_type'] == 'category':
                    result = self._check_category_single_cap(user, offer_category, cap)
                    category_cap_results.append(result)
            
            # Find most restrictive cap
            if category_cap_results:
                most_restrictive = min(category_cap_results, key=lambda x: x['remaining'])
                
                return {
                    'can_show': most_restrictive['remaining'] > 0,
                    'remaining': most_restrictive['remaining'],
                    'category': offer_category,
                    'cap_type': most_restrictive['cap_type'],
                    'cap_value': most_restrictive['cap_value'],
                    'reset_time': most_restrictive['reset_time'],
                    'details': category_cap_results
                }
            
            return {
                'can_show': True,
                'remaining': float('inf'),
                'category': offer_category,
                'cap_type': None,
                'cap_value': None,
                'reset_time': None,
                'details': []
            }
            
        except Exception as e:
            logger.error(f"Error checking category caps: {e}")
            return {'can_show': True, 'error': str(e)}
    
    def _check_custom_caps(self, user: User, offer: OfferRoute, 
                         caps: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """Check custom caps based on conditions."""
        try:
            custom_cap_results = []
            
            for cap in caps:
                if cap.get('custom_conditions', False):
                    result = self._check_custom_single_cap(user, offer, cap, context)
                    custom_cap_results.append(result)
            
            # Find most restrictive cap
            if custom_cap_results:
                most_restrictive = min(custom_cap_results, key=lambda x: x['remaining'])
                
                return {
                    'can_show': most_restrictive['remaining'] > 0,
                    'remaining': most_restrictive['remaining'],
                    'cap_type': most_restrictive['cap_type'],
                    'cap_value': most_restrictive['cap_value'],
                    'reset_time': most_restrictive['reset_time'],
                    'details': custom_cap_results
                }
            
            return {
                'can_show': True,
                'remaining': float('inf'),
                'cap_type': None,
                'cap_value': None,
                'reset_time': None,
                'details': []
            }
            
        except Exception as e:
            logger.error(f"Error checking custom caps: {e}")
            return {'can_show': True, 'error': str(e)}
    
    def _check_cap_overrides(self, user: User, offer: OfferRoute, 
                           caps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check for cap overrides."""
        try:
            # Get active overrides for user and offer
            overrides = CapOverride.objects.filter(
                Q(user=user) | Q(user__isnull=True),  # User-specific or global
                Q(offer=offer) | Q(offer__isnull=True),  # Offer-specific or global
                is_active=True,
                expires_at__gt=timezone.now()
            ).order_by('-priority')
            
            override_results = []
            
            for override in overrides:
                result = self._evaluate_override(user, offer, override)
                override_results.append(result)
            
            # Find most permissive override
            if override_results:
                most_permissive = max(override_results, key=lambda x: x['allowance_multiplier'])
                
                return {
                    'has_override': True,
                    'can_override': True,
                    'allowance_multiplier': most_permissive['allowance_multiplier'],
                    'override_reason': most_permissive['reason'],
                    'details': override_results
                }
            
            return {
                'has_override': False,
                'can_override': False,
                'allowance_multiplier': 1.0,
                'override_reason': None,
                'details': []
            }
            
        except Exception as e:
            logger.error(f"Error checking cap overrides: {e}")
            return {'has_override': False, 'error': str(e)}
    
    def _check_single_cap(self, user: User, offer: OfferRoute, 
                         cap: Dict[str, Any]) -> Dict[str, Any]:
        """Check a single cap."""
        try:
            cap_type = cap['cap_type']
            cap_value = cap['cap_value']
            
            if cap_type not in self.cap_types:
                return {'can_show': True, 'remaining': float('inf'), 'cap_type': cap_type}
            
            # Get current usage
            current_usage = self._get_cap_usage(user, offer, cap_type)
            
            # Calculate remaining
            remaining = cap_value - current_usage
            
            # Get reset time
            reset_time = self._get_reset_time(user, offer, cap_type)
            
            return {
                'can_show': remaining > 0,
                'remaining': remaining,
                'cap_type': cap_type,
                'cap_value': cap_value,
                'current_usage': current_usage,
                'reset_time': reset_time
            }
            
        except Exception as e:
            logger.error(f"Error checking single cap: {e}")
            return {'can_show': True, 'error': str(e), 'cap_type': cap.get('cap_type')}
    
    def _check_global_single_cap(self, offer: OfferRoute, cap: Dict[str, Any]) -> Dict[str, Any]:
        """Check a single global cap."""
        try:
            cap_type = cap['cap_type']
            cap_value = cap['cap_value']
            
            if cap_type not in self.cap_types:
                return {'can_show': True, 'remaining': float('inf'), 'cap_type': cap_type}
            
            # Get global usage
            global_usage = self._get_global_cap_usage(offer, cap_type)
            
            # Calculate remaining
            remaining = cap_value - global_usage
            
            # Get reset time
            reset_time = self._get_global_reset_time(offer, cap_type)
            
            return {
                'can_show': remaining > 0,
                'remaining': remaining,
                'cap_type': cap_type,
                'cap_value': cap_value,
                'current_usage': global_usage,
                'reset_time': reset_time
            }
            
        except Exception as e:
            logger.error(f"Error checking global single cap: {e}")
            return {'can_show': True, 'error': str(e), 'cap_type': cap.get('cap_type')}
    
    def _check_category_single_cap(self, user: User, category: str, 
                                cap: Dict[str, Any]) -> Dict[str, Any]:
        """Check a single category cap."""
        try:
            cap_type = cap['cap_type']
            cap_value = cap['cap_value']
            
            # Get category usage
            category_usage = self._get_category_cap_usage(user, category, cap_type)
            
            # Calculate remaining
            remaining = cap_value - category_usage
            
            # Get reset time
            reset_time = self._get_category_reset_time(user, category, cap_type)
            
            return {
                'can_show': remaining > 0,
                'remaining': remaining,
                'cap_type': cap_type,
                'cap_value': cap_value,
                'current_usage': category_usage,
                'reset_time': reset_time
            }
            
        except Exception as e:
            logger.error(f"Error checking category single cap: {e}")
            return {'can_show': True, 'error': str(e), 'cap_type': cap.get('cap_type')}
    
    def _check_custom_single_cap(self, user: User, offer: OfferRoute, 
                              cap: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Check a single custom cap."""
        try:
            conditions = cap.get('conditions', {})
            
            # Evaluate conditions
            conditions_met = self._evaluate_cap_conditions(user, offer, conditions, context)
            
            if not conditions_met:
                return {
                    'can_show': True,
                    'remaining': float('inf'),
                    'cap_type': cap['cap_type'],
                    'conditions_met': False
                }
            
            # If conditions are met, check the cap
            return self._check_single_cap(user, offer, cap)
            
        except Exception as e:
            logger.error(f"Error checking custom single cap: {e}")
            return {'can_show': True, 'error': str(e), 'cap_type': cap.get('cap_type')}
    
    def _evaluate_cap_conditions(self, user: User, offer: OfferRoute, 
                               conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate cap conditions."""
        try:
            # Time conditions
            if 'time_range' in conditions:
                time_range = conditions['time_range']
                current_hour = timezone.now().hour
                
                if 'start_hour' in time_range and 'end_hour' in time_range:
                    if not (time_range['start_hour'] <= current_hour <= time_range['end_hour']):
                        return False
            
            # Day of week conditions
            if 'days_of_week' in conditions:
                allowed_days = conditions['days_of_week']
                current_day = timezone.now().weekday()  # 0=Monday, 6=Sunday
                
                if current_day not in allowed_days:
                    return False
            
            # User segment conditions
            if 'user_segments' in conditions:
                allowed_segments = conditions['user_segments']
                user_segments = self._get_user_segments(user)
                
                if not any(segment in allowed_segments for segment in user_segments):
                    return False
            
            # Device conditions
            if 'device_types' in conditions:
                allowed_devices = conditions['device_types']
                user_device = context.get('device', {}).get('type')
                
                if user_device not in allowed_devices:
                    return False
            
            # Location conditions
            if 'locations' in conditions:
                allowed_locations = conditions['locations']
                user_location = context.get('location', {}).get('country')
                
                if user_location not in allowed_locations:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error evaluating cap conditions: {e}")
            return False
    
    def _evaluate_override(self, user: User, offer: OfferRoute, 
                          override: CapOverride) -> Dict[str, Any]:
        """Evaluate a cap override."""
        try:
            # Check if override applies
            override_applies = True
            
            # Check user condition
            if override.user and override.user != user:
                override_applies = False
            
            # Check offer condition
            if override.offer and override.offer != offer:
                override_applies = False
            
            # Check time condition
            if override.start_time and override.end_time:
                now = timezone.now()
                if not (override.start_time <= now <= override.end_time):
                    override_applies = False
            
            if not override_applies:
                return {
                    'applies': False,
                    'allowance_multiplier': 1.0,
                    'reason': 'conditions_not_met'
                }
            
            return {
                'applies': True,
                'allowance_multiplier': override.allowance_multiplier,
                'reason': override.reason or 'override_applied'
            }
            
        except Exception as e:
            logger.error(f"Error evaluating override: {e}")
            return {'applies': False, 'error': str(e)}
    
    def _make_cap_decision(self, cap_results: Dict[str, Any], 
                          override_result: Dict[str, Any]) -> Tuple[bool, str]:
        """Make final cap decision."""
        try:
            # If override allows bypass
            if override_result.get('can_override', False):
                multiplier = override_result.get('allowance_multiplier', 1.0)
                return True, f"override_applied_{multiplier}x"
            
            # Check user caps
            user_caps = cap_results.get('user_caps', {})
            if not user_caps.get('can_show', True):
                return False, f"user_cap_exceeded_{user_caps.get('cap_type')}"
            
            # Check global caps
            global_caps = cap_results.get('global_caps', {})
            if not global_caps.get('can_show', True):
                return False, f"global_cap_exceeded_{global_caps.get('cap_type')}"
            
            # Check category caps
            category_caps = cap_results.get('category_caps', {})
            if not category_caps.get('can_show', True):
                return False, f"category_cap_exceeded_{category_caps.get('category')}"
            
            # Check custom caps
            custom_caps = cap_results.get('custom_caps', {})
            if not custom_caps.get('can_show', True):
                return False, f"custom_cap_exceeded_{custom_caps.get('cap_type')}"
            
            return True, 'all_caps_ok'
            
        except Exception as e:
            logger.error(f"Error making cap decision: {e}")
            return True, 'decision_error'
    
    def _get_cap_usage(self, user: User, offer: OfferRoute, cap_type: str) -> int:
        """Get current cap usage for user and offer."""
        try:
            # Check cache first
            cache_key = f"cap_usage:{user.id}:{offer.id}:{cap_type}"
            cached_usage = self.cache_service.get(cache_key)
            
            if cached_usage is not None:
                return cached_usage
            
            # Calculate usage based on cap type
            if cap_type == 'daily':
                usage = self._get_daily_usage(user, offer)
            elif cap_type == 'weekly':
                usage = self._get_weekly_usage(user, offer)
            elif cap_type == 'monthly':
                usage = self._get_monthly_usage(user, offer)
            elif cap_type == 'hourly':
                usage = self._get_hourly_usage(user, offer)
            elif cap_type == 'session':
                usage = self._get_session_usage(user, offer)
            else:
                usage = 0
            
            # Cache result
            self.cache_service.set(cache_key, usage, CAP_CACHE_TIMEOUT)
            
            return usage
            
        except Exception as e:
            logger.error(f"Error getting cap usage: {e}")
            return 0
    
    def _get_global_cap_usage(self, offer: OfferRoute, cap_type: str) -> int:
        """Get global cap usage for offer."""
        try:
            # Check cache first
            cache_key = f"global_cap_usage:{offer.id}:{cap_type}"
            cached_usage = self.cache_service.get(cache_key)
            
            if cached_usage is not None:
                return cached_usage
            
            # Calculate global usage
            if cap_type == 'daily':
                usage = self._get_global_daily_usage(offer)
            elif cap_type == 'weekly':
                usage = self._get_global_weekly_usage(offer)
            elif cap_type == 'monthly':
                usage = self._get_global_monthly_usage(offer)
            else:
                usage = 0
            
            # Cache result
            self.cache_service.set(cache_key, usage, CAP_CACHE_TIMEOUT)
            
            return usage
            
        except Exception as e:
            logger.error(f"Error getting global cap usage: {e}")
            return 0
    
    def _get_category_cap_usage(self, user: User, category: str, cap_type: str) -> int:
        """Get category cap usage for user."""
        try:
            # Check cache first
            cache_key = f"category_cap_usage:{user.id}:{category}:{cap_type}"
            cached_usage = self.cache_service.get(cache_key)
            
            if cached_usage is not None:
                return cached_usage
            
            # Calculate category usage
            if cap_type == 'daily':
                usage = self._get_category_daily_usage(user, category)
            elif cap_type == 'weekly':
                usage = self._get_category_weekly_usage(user, category)
            elif cap_type == 'monthly':
                usage = self._get_category_monthly_usage(user, category)
            else:
                usage = 0
            
            # Cache result
            self.cache_service.set(cache_key, usage, CAP_CACHE_TIMEOUT)
            
            return usage
            
        except Exception as e:
            logger.error(f"Error getting category cap usage: {e}")
            return 0
    
    def _get_daily_usage(self, user: User, offer: OfferRoute) -> int:
        """Get daily usage for user and offer."""
        try:
            today = timezone.now().date()
            
            return UserOfferHistory.objects.filter(
                user=user,
                offer=offer,
                viewed_at__date=today
            ).count()
            
        except Exception as e:
            logger.error(f"Error getting daily usage: {e}")
            return 0
    
    def _get_weekly_usage(self, user: User, offer: OfferRoute) -> int:
        """Get weekly usage for user and offer."""
        try:
            week_start = timezone.now().date() - timezone.timedelta(days=timezone.now().weekday())
            
            return UserOfferHistory.objects.filter(
                user=user,
                offer=offer,
                viewed_at__date__gte=week_start
            ).count()
            
        except Exception as e:
            logger.error(f"Error getting weekly usage: {e}")
            return 0
    
    def _get_monthly_usage(self, user: User, offer: OfferRoute) -> int:
        """Get monthly usage for user and offer."""
        try:
            month_start = timezone.now().date().replace(day=1)
            
            return UserOfferHistory.objects.filter(
                user=user,
                offer=offer,
                viewed_at__date__gte=month_start
            ).count()
            
        except Exception as e:
            logger.error(f"Error getting monthly usage: {e}")
            return 0
    
    def _get_hourly_usage(self, user: User, offer: OfferRoute) -> int:
        """Get hourly usage for user and offer."""
        try:
            hour_start = timezone.now().replace(minute=0, second=0, microsecond=0)
            
            return UserOfferHistory.objects.filter(
                user=user,
                offer=offer,
                viewed_at__gte=hour_start
            ).count()
            
        except Exception as e:
            logger.error(f"Error getting hourly usage: {e}")
            return 0
    
    def _get_session_usage(self, user: User, offer: OfferRoute) -> int:
        """Get session usage for user and offer."""
        try:
            # Get current session ID from context or recent activity
            current_session = self._get_current_session_id(user)
            
            if not current_session:
                return 0
            
            return UserOfferHistory.objects.filter(
                user=user,
                offer=offer,
                session_id=current_session
            ).count()
            
        except Exception as e:
            logger.error(f"Error getting session usage: {e}")
            return 0
    
    def _get_global_daily_usage(self, offer: OfferRoute) -> int:
        """Get global daily usage for offer."""
        try:
            today = timezone.now().date()
            
            return UserOfferHistory.objects.filter(
                offer=offer,
                viewed_at__date=today
            ).count()
            
        except Exception as e:
            logger.error(f"Error getting global daily usage: {e}")
            return 0
    
    def _get_global_weekly_usage(self, offer: OfferRoute) -> int:
        """Get global weekly usage for offer."""
        try:
            week_start = timezone.now().date() - timezone.timedelta(days=timezone.now().weekday())
            
            return UserOfferHistory.objects.filter(
                offer=offer,
                viewed_at__date__gte=week_start
            ).count()
            
        except Exception as e:
            logger.error(f"Error getting global weekly usage: {e}")
            return 0
    
    def _get_global_monthly_usage(self, offer: OfferRoute) -> int:
        """Get global monthly usage for offer."""
        try:
            month_start = timezone.now().date().replace(day=1)
            
            return UserOfferHistory.objects.filter(
                offer=offer,
                viewed_at__date__gte=month_start
            ).count()
            
        except Exception as e:
            logger.error(f"Error getting global monthly usage: {e}")
            return 0
    
    def _get_category_daily_usage(self, user: User, category: str) -> int:
        """Get daily category usage for user."""
        try:
            today = timezone.now().date()
            
            return UserOfferHistory.objects.filter(
                user=user,
                offer__category=category,
                viewed_at__date=today
            ).count()
            
        except Exception as e:
            logger.error(f"Error getting category daily usage: {e}")
            return 0
    
    def _get_category_weekly_usage(self, user: User, category: str) -> int:
        """Get weekly category usage for user."""
        try:
            week_start = timezone.now().date() - timezone.timedelta(days=timezone.now().weekday())
            
            return UserOfferHistory.objects.filter(
                user=user,
                offer__category=category,
                viewed_at__date__gte=week_start
            ).count()
            
        except Exception as e:
            logger.error(f"Error getting category weekly usage: {e}")
            return 0
    
    def _get_category_monthly_usage(self, user: User, category: str) -> int:
        """Get monthly category usage for user."""
        try:
            month_start = timezone.now().date().replace(day=1)
            
            return UserOfferHistory.objects.filter(
                user=user,
                offer__category=category,
                viewed_at__date__gte=month_start
            ).count()
            
        except Exception as e:
            logger.error(f"Error getting category monthly usage: {e}")
            return 0
    
    def _get_reset_time(self, user: User, offer: OfferRoute, cap_type: str) -> timezone.datetime:
        """Get reset time for a cap type."""
        try:
            if cap_type not in self.cap_types:
                return timezone.now() + timezone.timedelta(days=365)  # Far future
            
            reset_hours = self.cap_types[cap_type]['reset_hours']
            
            if reset_hours == 0:  # Session caps don't reset
                return timezone.now() + timezone.timedelta(days=365)  # Far future
            
            # Get last reset time
            last_reset = self._get_last_reset_time(user, offer, cap_type)
            
            # Calculate next reset
            next_reset = last_reset + timezone.timedelta(hours=reset_hours)
            
            return next_reset
            
        except Exception as e:
            logger.error(f"Error getting reset time: {e}")
            return timezone.now() + timezone.timedelta(days=365)
    
    def _get_global_reset_time(self, offer: OfferRoute, cap_type: str) -> timezone.datetime:
        """Get global reset time for a cap type."""
        try:
            if cap_type not in self.cap_types:
                return timezone.now() + timezone.timedelta(days=365)  # Far future
            
            reset_hours = self.cap_types[cap_type]['reset_hours']
            
            if reset_hours == 0:  # Session caps don't reset
                return timezone.now() + timezone.timedelta(days=365)  # Far future
            
            # Get last global reset time
            last_reset = self._get_last_global_reset_time(offer, cap_type)
            
            # Calculate next reset
            next_reset = last_reset + timezone.timedelta(hours=reset_hours)
            
            return next_reset
            
        except Exception as e:
            logger.error(f"Error getting global reset time: {e}")
            return timezone.now() + timezone.timedelta(days=365)
    
    def _get_category_reset_time(self, user: User, category: str, cap_type: str) -> timezone.datetime:
        """Get category reset time for user."""
        try:
            if cap_type not in self.cap_types:
                return timezone.now() + timezone.timedelta(days=365)  # Far future
            
            reset_hours = self.cap_types[cap_type]['reset_hours']
            
            if reset_hours == 0:  # Session caps don't reset
                return timezone.now() + timezone.timedelta(days=365)  # Far future
            
            # Get last category reset time
            last_reset = self._get_last_category_reset_time(user, category, cap_type)
            
            # Calculate next reset
            next_reset = last_reset + timezone.timedelta(hours=reset_hours)
            
            return next_reset
            
        except Exception as e:
            logger.error(f"Error getting category reset time: {e}")
            return timezone.now() + timezone.timedelta(days=365)
    
    def _get_last_reset_time(self, user: User, offer: OfferRoute, cap_type: str) -> timezone.datetime:
        """Get last reset time for user and offer."""
        try:
            # This would typically be stored in a reset tracking table
            # For now, calculate based on current time and reset schedule
            reset_hours = self.cap_types[cap_type]['reset_hours']
            
            if reset_hours == 0:
                return timezone.now() - timezone.timedelta(days=365)  # Long ago for session caps
            
            now = timezone.now()
            
            if cap_type == 'daily':
                # Reset at midnight
                return now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif cap_type == 'weekly':
                # Reset at Monday midnight
                days_since_monday = now.weekday()
                monday = now - timezone.timedelta(days=days_since_monday)
                return monday.replace(hour=0, minute=0, second=0, microsecond=0)
            elif cap_type == 'monthly':
                # Reset at 1st of month midnight
                return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                return now - timezone.timedelta(hours=reset_hours)
            
        except Exception as e:
            logger.error(f"Error getting last reset time: {e}")
            return timezone.now() - timezone.timedelta(days=365)
    
    def _get_last_global_reset_time(self, offer: OfferRoute, cap_type: str) -> timezone.datetime:
        """Get last global reset time for offer."""
        try:
            # Similar to user reset but for global caps
            reset_hours = self.cap_types[cap_type]['reset_hours']
            
            if reset_hours == 0:
                return timezone.now() - timezone.timedelta(days=365)
            
            now = timezone.now()
            
            if cap_type == 'daily':
                return now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif cap_type == 'weekly':
                days_since_monday = now.weekday()
                monday = now - timezone.timedelta(days=days_since_monday)
                return monday.replace(hour=0, minute=0, second=0, microsecond=0)
            elif cap_type == 'monthly':
                return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                return now - timezone.timedelta(hours=reset_hours)
            
        except Exception as e:
            logger.error(f"Error getting last global reset time: {e}")
            return timezone.now() - timezone.timedelta(days=365)
    
    def _get_last_category_reset_time(self, user: User, category: str, cap_type: str) -> timezone.datetime:
        """Get last category reset time for user."""
        try:
            # Similar to user reset but for category caps
            reset_hours = self.cap_types[cap_type]['reset_hours']
            
            if reset_hours == 0:
                return timezone.now() - timezone.timedelta(days=365)
            
            now = timezone.now()
            
            if cap_type == 'daily':
                return now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif cap_type == 'weekly':
                days_since_monday = now.weekday()
                monday = now - timezone.timedelta(days=days_since_monday)
                return monday.replace(hour=0, minute=0, second=0, microsecond=0)
            elif cap_type == 'monthly':
                return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                return now - timezone.timedelta(hours=reset_hours)
            
        except Exception as e:
            logger.error(f"Error getting last category reset time: {e}")
            return timezone.now() - timezone.timedelta(days=365)
    
    def _increment_user_caps(self, user: User, offer: OfferRoute, caps: List[Dict[str, Any]]):
        """Increment user-specific caps."""
        try:
            for cap in caps:
                if cap['is_user_specific']:
                    cap_type = cap['cap_type']
                    
                    if cap_type in self.cap_types:
                        # Update user cap record
                        user_cap, created = UserOfferCap.objects.get_or_create(
                            user=user,
                            offer=offer,
                            cap_type=cap_type,
                            defaults={
                                'cap_value': cap['cap_value'],
                                'time_window': cap.get('time_window'),
                                'time_unit': cap.get('time_unit'),
                                'current_count': 0,
                                'last_reset': timezone.now()
                            }
                        )
                        
                        # Increment counter
                        user_cap.current_count = F('current_count') + 1
                        user_cap.save()
                        
                        logger.debug(f"Incremented {cap_type} cap for user {user.id}, offer {offer.id}")
            
        except Exception as e:
            logger.error(f"Error incrementing user caps: {e}")
    
    def _increment_global_caps(self, offer: OfferRoute, caps: List[Dict[str, Any]]):
        """Increment global caps."""
        try:
            for cap in caps:
                if cap['is_global']:
                    cap_type = cap['cap_type']
                    
                    if cap_type in self.cap_types:
                        # This would update a global cap tracking table
                        # For now, just log the increment
                        logger.debug(f"Incremented global {cap_type} cap for offer {offer.id}")
            
        except Exception as e:
            logger.error(f"Error incrementing global caps: {e}")
    
    def _increment_category_caps(self, user: User, offer: OfferRoute, caps: List[Dict[str, Any]]):
        """Increment category caps."""
        try:
            offer_category = getattr(offer, 'category', 'general')
            
            for cap in caps:
                if cap.get('category_based', False) or cap['cap_type'] == 'category':
                    cap_type = cap['cap_type']
                    
                    if cap_type in self.cap_types:
                        # This would update a category cap tracking table
                        # For now, just log the increment
                        logger.debug(f"Incremented category {cap_type} cap for user {user.id}, category {offer_category}")
            
        except Exception as e:
            logger.error(f"Error incrementing category caps: {e}")
    
    def _increment_custom_caps(self, user: User, offer: OfferRoute, caps: List[Dict[str, Any]], context: Dict[str, Any]):
        """Increment custom caps."""
        try:
            for cap in caps:
                if cap.get('custom_conditions', False):
                    conditions_met = self._evaluate_cap_conditions(user, offer, cap.get('conditions', {}), context)
                    
                    if conditions_met:
                        cap_type = cap['cap_type']
                        
                        if cap_type in self.cap_types:
                            # This would update a custom cap tracking table
                            # For now, just log the increment
                            logger.debug(f"Incremented custom {cap_type} cap for user {user.id}, offer {offer.id}")
            
        except Exception as e:
            logger.error(f"Error incrementing custom caps: {e}")
    
    def _clear_cap_cache(self, user_id: int, offer_id: int):
        """Clear cap cache for user and offer."""
        try:
            cache_keys = [
                f"cap_usage:{user_id}:{offer_id}:*",
                f"can_show:{user_id}:{offer_id}"
            ]
            
            for key_pattern in cache_keys:
                # This would need pattern deletion support
                logger.info(f"Cache clearing for pattern {key_pattern} not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing cap cache: {e}")
    
    def _get_current_session_id(self, user: User) -> Optional[str]:
        """Get current session ID for user."""
        try:
            # This would typically come from a session management system
            # For now, return None
            return None
            
        except Exception as e:
            logger.error(f"Error getting current session ID: {e}")
            return None
    
    def _get_user_segments(self, user: User) -> List[str]:
        """Get user segments for cap evaluation."""
        try:
            # This would integrate with user segmentation system
            # For now, return basic segments
            segments = []
            
            if getattr(user, 'is_premium', False):
                segments.append('premium')
            
            days_since_registration = (timezone.now() - user.date_joined).days
            if days_since_registration <= 30:
                segments.append('new_user')
            
            return segments
            
        except Exception as e:
            logger.error(f"Error getting user segments: {e}")
            return []
    
    def _update_check_stats(self, elapsed_ms: float):
        """Update cap check performance statistics."""
        self.cap_stats['total_checks'] += 1
        
        # Update average time
        current_avg = self.cap_stats['avg_check_time_ms']
        total_checks = self.cap_stats['total_checks']
        self.cap_stats['avg_check_time_ms'] = (
            (current_avg * (total_checks - 1) + elapsed_ms) / total_checks
        )
    
    def _update_update_stats(self, elapsed_ms: float):
        """Update cap update performance statistics."""
        self.cap_stats['total_updates'] += 1
        
        # Update average time
        current_avg = self.cap_stats['avg_update_time_ms']
        total_updates = self.cap_stats['total_updates']
        self.cap_stats['avg_update_time_ms'] = (
            (current_avg * (total_updates - 1) + elapsed_ms) / total_updates
        )
    
    def get_cap_stats(self) -> Dict[str, Any]:
        """Get cap enforcement performance statistics."""
        total_checks = self.cap_stats['total_checks']
        total_updates = self.cap_stats['total_updates']
        total_requests = total_checks + total_updates
        
        cache_hit_rate = (
            self.cap_stats['cache_hits'] / max(1, total_checks)
        )
        
        return {
            'total_checks': total_checks,
            'total_updates': total_updates,
            'total_requests': total_requests,
            'cache_hits': self.cap_stats['cache_hits'],
            'cache_misses': total_checks - self.cap_stats['cache_hits'],
            'cache_hit_rate': cache_hit_rate,
            'cap_exceeded': self.cap_stats['cap_exceeded'],
            'avg_check_time_ms': self.cap_stats['avg_check_time_ms'],
            'avg_update_time_ms': self.cap_stats['avg_update_time_ms'],
            'supported_cap_types': list(self.cap_types.keys())
        }
    
    def clear_cache(self, user_id: int = None, offer_id: int = None):
        """Clear cap enforcement cache."""
        try:
            if user_id and offer_id:
                self._clear_cap_cache(user_id, offer_id)
            elif user_id:
                # Clear all caps for user
                cache_keys = f"cap_usage:{user_id}:*"
                logger.info(f"Cache clearing for pattern {cache_keys} not implemented")
            elif offer_id:
                # Clear all caps for offer
                cache_keys = f"cap_usage:*:{offer_id}"
                logger.info(f"Cache clearing for pattern {cache_keys} not implemented")
            else:
                # Clear all cap cache
                logger.info("Cache clearing for all caps not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing cap cache: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on cap enforcement service."""
        try:
            # Test cap checking
            test_user = User(id=1, username='test')
            test_offer = OfferRoute(id=1, name='test')
            
            can_show, cap_info = self.can_show_offer(test_user, test_offer)
            
            # Test cap increment
            increment_success = self.increment_cap(test_user, test_offer)
            
            return {
                'status': 'healthy',
                'test_cap_check': isinstance(can_show, bool),
                'test_cap_increment': increment_success,
                'stats': self.get_cap_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
