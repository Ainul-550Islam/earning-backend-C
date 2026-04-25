"""
Cap Reset Service

Handles midnight cap reset and periodic
cap management for the offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
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
    CAP_RESET_CACHE_TIMEOUT, RESET_BATCH_SIZE,
    CAP_RESET_HOURS, DEFAULT_DAILY_CAP,
    CAP_RESET_LOCK_TIMEOUT, CAP_HISTORY_RETENTION_DAYS
)
from ....exceptions import CapError, CapResetError
from ....utils import get_cap_reset_key, calculate_reset_window

User = get_user_model()
logger = logging.getLogger(__name__)


class CapResetService:
    """
    Service for resetting caps and managing cap lifecycle.
    
    Handles various types of cap resets:
    - Daily midnight resets
    - Weekly resets
    - Monthly resets
    - Custom schedule resets
    - Manual cap resets
    - Cap history management
    - Reset notifications and logging
    
    Performance targets:
    - Cap reset: <100ms per 1000 caps
    - Reset validation: <10ms per cap
    - Batch processing: <500ms per batch
    - Cache hit rate: >95%
    """
    
    def __init__(self):
        self.cache_service = cache
        self.reset_stats = {
            'total_resets': 0,
            'batch_resets': 0,
            'cache_hits': 0,
            'errors': 0,
            'avg_reset_time_ms': 0.0,
            'last_reset_time': None
        }
        
        # Reset schedules
        self.reset_schedules = {
            'daily': {'hour': 0, 'minute': 0, 'timezone': 'UTC'},
            'weekly': {'day': 1, 'hour': 0, 'minute': 0, 'timezone': 'UTC'},  # Monday
            'monthly': {'day': 1, 'hour': 0, 'minute': 0, 'timezone': 'UTC'},  # 1st of month
            'custom': {}  # Custom schedules per cap
        }
        
        # Reset types
        self.reset_types = {
            'daily': 'daily_count',
            'weekly': 'weekly_count',
            'monthly': 'monthly_count',
            'hourly': 'hourly_count',
            'session': 'session_count'
        }
    
    def perform_scheduled_resets(self, reset_type: str = None) -> Dict[str, Any]:
        """
        Perform scheduled cap resets.
        
        Args:
            reset_type: Type of reset to perform (daily, weekly, monthly, or None for all)
            
        Returns:
            Reset results and statistics
        """
        try:
            start_time = timezone.now()
            
            if reset_type:
                return self._perform_single_reset_type(reset_type)
            else:
                return self._perform_all_scheduled_resets()
                
        except Exception as e:
            logger.error(f"Error performing scheduled resets: {e}")
            self.reset_stats['errors'] += 1
            return {'error': str(e)}
    
    def _perform_single_reset_type(self, reset_type: str) -> Dict[str, Any]:
        """Perform reset for a single cap type."""
        try:
            if reset_type not in self.reset_types:
                return {'error': f'Invalid reset type: {reset_type}'}
            
            # Check if reset is due
            if not self._is_reset_due(reset_type):
                return {'status': 'not_due', 'reset_type': reset_type}
            
            # Get reset schedule
            schedule = self.reset_schedules.get(reset_type, {})
            
            # Perform reset
            reset_results = self._reset_caps_by_type(reset_type, schedule)
            
            # Update last reset time
            self._update_last_reset_time(reset_type)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_reset_stats(elapsed_ms)
            
            return {
                'status': 'completed',
                'reset_type': reset_type,
                'schedule': schedule,
                'results': reset_results,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error performing single reset type {reset_type}: {e}")
            return {'error': str(e), 'reset_type': reset_type}
    
    def _perform_all_scheduled_resets(self) -> Dict[str, Any]:
        """Perform all scheduled resets."""
        try:
            reset_results = {}
            
            for reset_type in self.reset_types.keys():
                result = self._perform_single_reset_type(reset_type)
                reset_results[reset_type] = result
            
            return {
                'status': 'completed',
                'all_results': reset_results,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error performing all scheduled resets: {e}")
            return {'error': str(e)}
    
    def _is_reset_due(self, reset_type: str) -> bool:
        """Check if a reset type is due."""
        try:
            # Get last reset time
            last_reset = self._get_last_reset_time(reset_type)
            
            if not last_reset:
                return True  # Never reset before
            
            # Get reset schedule
            schedule = self.reset_schedules.get(reset_type, {})
            
            # Calculate next reset time
            next_reset = self._calculate_next_reset_time(last_reset, schedule)
            
            # Check if current time is past next reset
            return timezone.now() >= next_reset
            
        except Exception as e:
            logger.error(f"Error checking if reset is due for {reset_type}: {e}")
            return True  # Reset on error
    
    def _get_last_reset_time(self, reset_type: str) -> Optional[timezone.datetime]:
        """Get last reset time for a reset type."""
        try:
            # Check cache first
            cache_key = f"last_reset:{reset_type}"
            cached_time = self.cache_service.get(cache_key)
            
            if cached_time:
                self.reset_stats['cache_hits'] += 1
                return cached_time
            
            # Get from database (would typically be in a reset tracking table)
            # For now, return today's midnight for daily resets
            now = timezone.now()
            
            if reset_type == 'daily':
                last_reset = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif reset_type == 'weekly':
                # Last Monday
                days_since_monday = now.weekday()
                last_monday = now - timezone.timedelta(days=days_since_monday)
                last_reset = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
            elif reset_type == 'monthly':
                # First of this month
                last_reset = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                last_reset = now - timezone.timedelta(days=1)  # Yesterday
            
            # Cache result
            self.cache_service.set(cache_key, last_reset, CAP_RESET_CACHE_TIMEOUT)
            
            return last_reset
            
        except Exception as e:
            logger.error(f"Error getting last reset time for {reset_type}: {e}")
            return None
    
    def _calculate_next_reset_time(self, last_reset: timezone.datetime, 
                                schedule: Dict[str, Any]) -> timezone.datetime:
        """Calculate next reset time based on schedule."""
        try:
            if not schedule:
                # Default to 24 hours from last reset
                return last_reset + timezone.timedelta(hours=24)
            
            reset_hour = schedule.get('hour', 0)
            reset_minute = schedule.get('minute', 0)
            reset_timezone = schedule.get('timezone', 'UTC')
            
            # Calculate next reset based on type
            now = timezone.now()
            
            if 'day' in schedule:  # Monthly or specific day
                reset_day = schedule['day']
                
                # Find next occurrence of this day
                if reset_day >= now.day:
                    # This month
                    next_reset = now.replace(
                        day=reset_day,
                        hour=reset_hour,
                        minute=reset_minute,
                        second=0,
                        microsecond=0
                    )
                else:
                    # Next month
                    next_month = now.replace(day=28) + timezone.timedelta(days=5)  # Go to next month
                    next_reset = next_month.replace(
                        day=reset_day,
                        hour=reset_hour,
                        minute=reset_minute,
                        second=0,
                        microsecond=0
                    )
            else:  # Daily or hourly
                next_reset = now.replace(
                    hour=reset_hour,
                    minute=reset_minute,
                    second=0,
                    microsecond=0
                )
                
                # If next reset is in the past, move to next day
                if next_reset <= now:
                    next_reset += timezone.timedelta(days=1)
            
            return next_reset
            
        except Exception as e:
            logger.error(f"Error calculating next reset time: {e}")
            return timezone.now() + timezone.timedelta(days=1)
    
    def _reset_caps_by_type(self, reset_type: str, 
                           schedule: Dict[str, Any]) -> Dict[str, Any]:
        """Reset caps of a specific type."""
        try:
            reset_field = self.reset_types.get(reset_type)
            
            if not reset_field:
                return {'error': f'Unknown reset type: {reset_type}'}
            
            # Reset user caps
            user_reset_results = self._reset_user_caps(reset_field)
            
            # Reset global caps
            global_reset_results = self._reset_global_caps(reset_field)
            
            # Reset category caps
            category_reset_results = self._reset_category_caps(reset_field)
            
            # Log reset
            self._log_cap_reset(reset_type, schedule, {
                'user_resets': len(user_reset_results),
                'global_resets': len(global_reset_results),
                'category_resets': len(category_reset_results)
            })
            
            return {
                'user_resets': user_reset_results,
                'global_resets': global_reset_results,
                'category_resets': category_reset_results,
                'total_resets': len(user_reset_results) + len(global_reset_results) + len(category_reset_results)
            }
            
        except Exception as e:
            logger.error(f"Error resetting caps by type {reset_type}: {e}")
            return {'error': str(e), 'reset_type': reset_type}
    
    def _reset_user_caps(self, reset_field: str) -> List[Dict[str, Any]]:
        """Reset user-specific caps."""
        try:
            reset_results = []
            
            # Get all user caps that need reset
            user_caps = UserOfferCap.objects.filter(
                is_active=True,
                cap_type__in=['daily', 'weekly', 'monthly', 'hourly']
            )
            
            # Process in batches
            total_reset = 0
            
            for i in range(0, len(user_caps), RESET_BATCH_SIZE):
                batch = user_caps[i:i + RESET_BATCH_SIZE]
                
                with transaction.atomic():
                    for cap in batch:
                        # Reset the appropriate field
                        if hasattr(cap, reset_field):
                            setattr(cap, reset_field, 0)
                            cap.last_reset = timezone.now()
                            cap.save()
                            total_reset += 1
                
                        # Clear cache for this cap
                        self._clear_cap_cache(cap.user_id, cap.offer_id)
            
                reset_results.append({
                    'batch_number': i // RESET_BATCH_SIZE + 1,
                    'caps_reset': total_reset,
                    'batch_size': len(batch)
                })
            
            self.reset_stats['batch_resets'] += len(reset_results)
            
            return reset_results
            
        except Exception as e:
            logger.error(f"Error resetting user caps: {e}")
            return []
    
    def _reset_global_caps(self, reset_field: str) -> List[Dict[str, Any]]:
        """Reset global caps."""
        try:
            reset_results = []
            
            # Get all global caps that need reset
            global_caps = OfferRoutingCap.objects.filter(
                is_active=True,
                cap_type__in=['daily', 'weekly', 'monthly', 'hourly']
            )
            
            # Process in batches
            total_reset = 0
            
            for i in range(0, len(global_caps), RESET_BATCH_SIZE):
                batch = global_caps[i:i + RESET_BATCH_SIZE]
                
                with transaction.atomic():
                    for cap in batch:
                        # Reset the appropriate field
                        if hasattr(cap, reset_field):
                            setattr(cap, reset_field, 0)
                            cap.last_reset = timezone.now()
                            cap.save()
                            total_reset += 1
                
                        # Clear cache for this cap
                        self._clear_global_cap_cache(cap.offer_id)
            
                reset_results.append({
                    'batch_number': i // RESET_BATCH_SIZE + 1,
                    'caps_reset': total_reset,
                    'batch_size': len(batch)
                })
            
            return reset_results
            
        except Exception as e:
            logger.error(f"Error resetting global caps: {e}")
            return []
    
    def _reset_category_caps(self, reset_field: str) -> List[Dict[str, Any]]:
        """Reset category caps."""
        try:
            reset_results = []
            
            # This would reset category-specific caps
            # For now, return empty results as category caps are handled differently
            
            return reset_results
            
        except Exception as e:
            logger.error(f"Error resetting category caps: {e}")
            return []
    
    def manual_reset_cap(self, user_id: int = None, offer_id: int = None, 
                     cap_type: str = None, cap_id: int = None) -> Dict[str, Any]:
        """
        Manually reset a specific cap.
        
        Args:
            user_id: User ID (for user-specific caps)
            offer_id: Offer ID (for offer-specific caps)
            cap_type: Type of cap to reset
            cap_id: Specific cap ID to reset
            
        Returns:
            Reset result
        """
        try:
            start_time = timezone.now()
            
            # Find caps to reset
            caps_to_reset = self._find_caps_for_reset(user_id, offer_id, cap_type, cap_id)
            
            if not caps_to_reset:
                return {'error': 'No caps found to reset'}
            
            # Perform reset
            reset_results = []
            
            with transaction.atomic():
                for cap in caps_to_reset:
                    # Reset all count fields to 0
                    cap.daily_count = 0
                    cap.weekly_count = 0
                    cap.monthly_count = 0
                    cap.hourly_count = 0
                    cap.session_count = 0
                    cap.last_reset = timezone.now()
                    cap.save()
                    
                    # Clear cache
                    self._clear_cap_cache(cap.user_id, cap.offer_id)
                    
                    reset_results.append({
                        'cap_id': cap.id,
                        'cap_type': cap.cap_type,
                        'user_id': cap.user_id,
                        'offer_id': cap.offer_id,
                        'reset_time': timezone.now().isoformat()
                    })
            
            # Log manual reset
            self._log_cap_reset('manual', {
                'user_id': user_id,
                'offer_id': offer_id,
                'cap_type': cap_type,
                'cap_id': cap_id
            }, {
                'caps_reset': len(reset_results),
                'caps': reset_results
            })
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_reset_stats(elapsed_ms)
            
            return {
                'status': 'completed',
                'caps_reset': len(reset_results),
                'reset_details': reset_results,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error performing manual cap reset: {e}")
            return {'error': str(e)}
    
    def _find_caps_for_reset(self, user_id: int = None, offer_id: int = None, 
                             cap_type: str = None, cap_id: int = None) -> List[Any]:
        """Find caps that match the reset criteria."""
        try:
            caps = []
            
            # If specific cap ID provided
            if cap_id:
                cap = UserOfferCap.objects.filter(id=cap_id).first()
                if cap:
                    caps.append(cap)
            # If user ID provided
            elif user_id:
                caps = UserOfferCap.objects.filter(user_id=user_id, is_active=True)
            # If offer ID provided
            elif offer_id:
                caps = UserOfferCap.objects.filter(offer_id=offer_id, is_active=True)
            # If cap type provided
            elif cap_type:
                caps = UserOfferCap.objects.filter(cap_type=cap_type, is_active=True)
            # If no specific criteria, get all active caps
            else:
                caps = UserOfferCap.objects.filter(is_active=True)
            
            return caps
            
        except Exception as e:
            logger.error(f"Error finding caps for reset: {e}")
            return []
    
    def get_cap_reset_history(self, user_id: int = None, offer_id: int = None, 
                            days: int = 30) -> List[Dict[str, Any]]:
        """
        Get cap reset history.
        
        Args:
            user_id: User ID to filter by
            offer_id: Offer ID to filter by
            days: Number of days to look back
            
        Returns:
            List of reset history entries
        """
        try:
            # This would typically query a reset history table
            # For now, return empty list
            return []
            
        except Exception as e:
            logger.error(f"Error getting cap reset history: {e}")
            return []
    
    def _clear_cap_cache(self, user_id: int, offer_id: int):
        """Clear cap cache for user and offer."""
        try:
            cache_keys = [
                f"cap_usage:{user_id}:{offer_id}:*",
                f"can_show:{user_id}:{offer_id}",
                f"global_cap_usage:{offer_id}:*"
            ]
            
            for key_pattern in cache_keys:
                # This would need pattern deletion support
                logger.info(f"Cache clearing for pattern {key_pattern} not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing cap cache: {e}")
    
    def _clear_global_cap_cache(self, offer_id: int):
        """Clear global cap cache for offer."""
        try:
            cache_keys = [
                f"global_cap_usage:{offer_id}:*"
            ]
            
            for key_pattern in cache_keys:
                # This would need pattern deletion support
                logger.info(f"Cache clearing for pattern {key_pattern} not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing global cap cache: {e}")
    
    def _update_last_reset_time(self, reset_type: str):
        """Update last reset time for a reset type."""
        try:
            cache_key = f"last_reset:{reset_type}"
            self.cache_service.set(cache_key, timezone.now(), CAP_RESET_CACHE_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Error updating last reset time: {e}")
    
    def _log_cap_reset(self, reset_type: str, criteria: Dict[str, Any], 
                      results: Dict[str, Any]):
        """Log cap reset event."""
        try:
            log_entry = {
                'reset_type': reset_type,
                'criteria': criteria,
                'results': results,
                'timestamp': timezone.now().isoformat(),
                'user_agent': 'CapResetService'
            }
            
            # This would typically log to a reset history table
            logger.info(f"Cap reset: {log_entry}")
            
        except Exception as e:
            logger.error(f"Error logging cap reset: {e}")
    
    def _update_reset_stats(self, elapsed_ms: float):
        """Update reset performance statistics."""
        self.reset_stats['total_resets'] += 1
        self.reset_stats['last_reset_time'] = timezone.now()
        
        # Update average time
        current_avg = self.reset_stats['avg_reset_time_ms']
        total_resets = self.reset_stats['total_resets']
        self.reset_stats['avg_reset_time_ms'] = (
            (current_avg * (total_resets - 1) + elapsed_ms) / total_resets
        )
    
    def get_reset_stats(self) -> Dict[str, Any]:
        """Get cap reset performance statistics."""
        total_requests = self.reset_stats['total_resets']
        cache_hit_rate = (
            self.reset_stats['cache_hits'] / max(1, total_requests)
        )
        
        return {
            'total_resets': total_requests,
            'batch_resets': self.reset_stats['batch_resets'],
            'cache_hits': self.reset_stats['cache_hits'],
            'cache_misses': total_requests - self.reset_stats['cache_hits'],
            'cache_hit_rate': cache_hit_rate,
            'errors': self.reset_stats['errors'],
            'error_rate': self.reset_stats['errors'] / max(1, total_requests),
            'avg_reset_time_ms': self.reset_stats['avg_reset_time_ms'],
            'last_reset_time': self.reset_stats['last_reset_time'].isoformat() if self.reset_stats['last_reset_time'] else None,
            'supported_reset_types': list(self.reset_types.keys()),
            'reset_schedules': self.reset_schedules
        }
    
    def schedule_custom_reset(self, cap_id: int, reset_schedule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Schedule custom reset for a specific cap.
        
        Args:
            cap_id: Cap ID to schedule reset for
            reset_schedule: Reset schedule configuration
            
        Returns:
            Schedule result
        """
        try:
            # Validate schedule
            if not self._validate_reset_schedule(reset_schedule):
                return {'error': 'Invalid reset schedule'}
            
            # Store custom schedule
            self.reset_schedules['custom'][str(cap_id)] = reset_schedule
            
            return {
                'status': 'scheduled',
                'cap_id': cap_id,
                'schedule': reset_schedule,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error scheduling custom reset: {e}")
            return {'error': str(e)}
    
    def _validate_reset_schedule(self, schedule: Dict[str, Any]) -> bool:
        """Validate reset schedule configuration."""
        try:
            required_fields = ['hour', 'minute']
            
            for field in required_fields:
                if field not in schedule:
                    return False
                
                if not isinstance(schedule[field], int):
                    return False
                
                if field == 'hour' and not (0 <= schedule[field] <= 23):
                    return False
                
                if field == 'minute' and not (0 <= schedule[field] <= 59):
                    return False
            
            # Validate optional fields
            if 'day' in schedule:
                if not isinstance(schedule['day'], int) or not (1 <= schedule['day'] <= 31):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating reset schedule: {e}")
            return False
    
    def clear_cache(self, reset_type: str = None):
        """Clear cap reset cache."""
        try:
            if reset_type:
                # Clear specific reset type cache
                cache_key = f"last_reset:{reset_type}"
                self.cache_service.delete(cache_key)
                logger.info(f"Cleared cache for reset type {reset_type}")
            else:
                # Clear all reset cache
                logger.info("Cache clearing for all reset types not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing reset cache: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on cap reset service."""
        try:
            # Test reset due check
            test_due = self._is_reset_due('daily')
            
            # Test reset calculation
            now = timezone.now()
            last_reset = now.replace(hour=0, minute=0, second=0, microsecond=0)
            schedule = self.reset_schedules['daily']
            next_reset = self._calculate_next_reset_time(last_reset, schedule)
            
            # Test manual reset
            test_user = User(id=1, username='test')
            test_offer = OfferRoute(id=1, name='test')
            
            # Create a test cap
            from ..cap import CapEnforcementService
            cap_service = CapEnforcementService()
            
            # Test cap creation and reset
            test_cap = UserOfferCap.objects.create(
                user=test_user,
                offer=test_offer,
                cap_type='daily',
                cap_value=10,
                daily_count=5,
                is_active=True
            )
            
            manual_reset = self.manual_reset_cap(
                user_id=test_user.id,
                offer_id=test_offer.id,
                cap_type='daily'
            )
            
            return {
                'status': 'healthy',
                'test_reset_due_check': test_due,
                'test_reset_calculation': next_reset > now,
                'test_manual_reset': manual_reset.get('status') == 'completed',
                'stats': self.get_reset_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
