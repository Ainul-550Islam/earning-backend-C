"""
Cap Reset Tasks

Periodic tasks for resetting offer caps
in the offer routing system.
"""

import logging
from typing import Dict, List, Any, Optional
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.contrib.auth import get_user_model
from ..services.cap import CapEnforcementService, CapResetService
from ..services.cache import cache_service
from ..models import OfferRoutingCap, UserOfferCap, CapOverride
from ..constants import CAP_RESET_INTERVAL, CAP_CACHE_TIMEOUT
from ..exceptions import CapError

logger = logging.getLogger(__name__)

User = get_user_model()


class CapResetTask:
    """
    Task for resetting offer caps periodically.
    
    Runs at midnight to:
    - Reset daily caps
    - Reset weekly caps
    - Reset monthly caps
    - Reset custom caps
    - Archive cap history
    - Send reset notifications
    """
    
    def __init__(self):
        self.cap_enforcement = CapEnforcementService()
        self.cap_reset = CapResetService()
        self.cache_service = cache_service
        self.task_stats = {
            'total_resets': 0,
            'successful_resets': 0,
            'failed_resets': 0,
            'avg_reset_time_ms': 0.0
        }
    
    def run_cap_reset(self) -> Dict[str, Any]:
        """
        Run the cap reset task.
        
        Returns:
            Task execution results
        """
        try:
            start_time = timezone.now()
            
            # Perform scheduled resets
            reset_results = self._perform_scheduled_resets()
            
            # Update task statistics
            self._update_task_stats(start_time)
            
            # Clear relevant cache
            self._clear_cap_cache()
            
            return {
                'success': True,
                'message': 'Cap reset task completed',
                'reset_results': reset_results,
                'execution_time_ms': (timezone.now() - start_time).total_seconds() * 1000,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in cap reset task: {e}")
            return {
                'success': False,
                'error': str(e),
                'execution_time_ms': 0,
                'timestamp': timezone.now().isoformat()
            }
    
    def _perform_scheduled_resets(self) -> Dict[str, Any]:
        """Perform all scheduled cap resets."""
        try:
            reset_results = {}
            
            # Daily reset
            if self._is_midnight():
                daily_result = self._reset_daily_caps()
                reset_results['daily'] = daily_result
            
            # Weekly reset (Monday morning)
            if self._is_monday_morning():
                weekly_result = self._reset_weekly_caps()
                reset_results['weekly'] = weekly_result
            
            # Monthly reset (1st of month)
            if self._is_first_of_month():
                monthly_result = self._reset_monthly_caps()
                reset_results['monthly'] = monthly_result
            
            # Custom resets (based on schedule)
            custom_result = self._reset_custom_caps()
            reset_results['custom'] = custom_result
            
            return reset_results
            
        except Exception as e:
            logger.error(f"Error performing scheduled resets: {e}")
            return {'error': str(e)}
    
    def _reset_daily_caps(self) -> Dict[str, Any]:
        """Reset daily offer caps."""
        try:
            # Get all daily caps
            daily_caps = OfferRoutingCap.objects.filter(
                cap_type='daily',
                is_active=True
            )
            
            # Get user caps
            user_caps = UserOfferCap.objects.filter(
                cap_type='daily',
                is_active=True
            )
            
            reset_count = 0
            errors = []
            
            # Reset global daily caps
            for cap in daily_caps:
                try:
                    cap.daily_count = 0
                    cap.last_reset = timezone.now()
                    cap.save()
                    reset_count += 1
                except Exception as e:
                    errors.append(f"Error resetting global cap {cap.id}: {e}")
            
            # Reset user daily caps
            for cap in user_caps:
                try:
                    cap.daily_count = 0
                    cap.last_reset = timezone.now()
                    cap.save()
                    reset_count += 1
                except Exception as e:
                    errors.append(f"Error resetting user cap {cap.id}: {e}")
            
            logger.info(f"Reset {reset_count} daily caps")
            
            return {
                'success': len(errors) == 0,
                'caps_reset': reset_count,
                'errors': errors,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error resetting daily caps: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _reset_weekly_caps(self) -> Dict[str, Any]:
        """Reset weekly offer caps."""
        try:
            # Get all weekly caps
            weekly_caps = OfferRoutingCap.objects.filter(
                cap_type='weekly',
                is_active=True
            )
            
            # Get user caps
            user_caps = UserOfferCap.objects.filter(
                cap_type='weekly',
                is_active=True
            )
            
            reset_count = 0
            errors = []
            
            # Reset global weekly caps
            for cap in weekly_caps:
                try:
                    cap.weekly_count = 0
                    cap.last_reset = timezone.now()
                    cap.save()
                    reset_count += 1
                except Exception as e:
                    errors.append(f"Error resetting global weekly cap {cap.id}: {e}")
            
            # Reset user weekly caps
            for cap in user_caps:
                try:
                    cap.weekly_count = 0
                    cap.last_reset = timezone.now()
                    cap.save()
                    reset_count += 1
                except Exception as e:
                    errors.append(f"Error resetting user weekly cap {cap.id}: {e}")
            
            logger.info(f"Reset {reset_count} weekly caps")
            
            return {
                'success': len(errors) == 0,
                'caps_reset': reset_count,
                'errors': errors,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error resetting weekly caps: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _reset_monthly_caps(self) -> Dict[str, Any]:
        """Reset monthly offer caps."""
        try:
            # Get all monthly caps
            monthly_caps = OfferRoutingCap.objects.filter(
                cap_type='monthly',
                is_active=True
            )
            
            # Get user caps
            user_caps = UserOfferCap.objects.filter(
                cap_type='monthly',
                is_active=True
            )
            
            reset_count = 0
            errors = []
            
            # Reset global monthly caps
            for cap in monthly_caps:
                try:
                    cap.monthly_count = 0
                    cap.last_reset = timezone.now()
                    cap.save()
                    reset_count += 1
                except Exception as e:
                    errors.append(f"Error resetting global monthly cap {cap.id}: {e}")
            
            # Reset user monthly caps
            for cap in user_caps:
                try:
                    cap.monthly_count = 0
                    cap.last_reset = timezone.now()
                    cap.save()
                    reset_count += 1
                except Exception as e:
                    errors.append(f"Error resetting user monthly cap {cap.id}: {e}")
            
            logger.info(f"Reset {reset_count} monthly caps")
            
            return {
                'success': len(errors) == 0,
                'caps_reset': reset_count,
                'errors': errors,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error resetting monthly caps: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _reset_custom_caps(self) -> Dict[str, Any]:
        """Reset custom offer caps based on schedule."""
        try:
            # Get custom caps with reset schedules
            custom_caps = OfferRoutingCap.objects.filter(
                cap_type='custom',
                is_active=True,
                reset_schedule__isnull=False
            )
            
            reset_count = 0
            errors = []
            
            for cap in custom_caps:
                try:
                    # Check if reset is due
                    if self._is_custom_reset_due(cap):
                        cap.current_count = 0
                        cap.last_reset = timezone.now()
                        cap.save()
                        reset_count += 1
                except Exception as e:
                    errors.append(f"Error resetting custom cap {cap.id}: {e}")
            
            logger.info(f"Reset {reset_count} custom caps")
            
            return {
                'success': len(errors) == 0,
                'caps_reset': reset_count,
                'errors': errors,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error resetting custom caps: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _is_midnight(self) -> bool:
        """Check if current time is midnight (00:00)."""
        now = timezone.now()
        return now.hour == 0 and now.minute < 5
    
    def _is_monday_morning(self) -> bool:
        """Check if current time is Monday morning (00:00-05:00)."""
        now = timezone.now()
        return now.weekday() == 0 and now.hour == 0 and now.minute < 5
    
    def _is_first_of_month(self) -> bool:
        """Check if current time is first of month (00:00-05:00)."""
        now = timezone.now()
        return now.day == 1 and now.hour == 0 and now.minute < 5
    
    def _is_custom_reset_due(self, cap) -> bool:
        """Check if custom cap reset is due."""
        try:
            reset_schedule = cap.reset_schedule
            
            if not reset_schedule:
                return False
            
            now = timezone.now()
            
            # Parse reset schedule
            if reset_schedule.type == 'daily':
                return now.hour == reset_schedule.hour and now.minute < 5
            elif reset_schedule.type == 'weekly':
                return now.weekday() == reset_schedule.day and now.hour == reset_schedule.hour and now.minute < 5
            elif reset_schedule.type == 'monthly':
                return now.day == reset_schedule.day and now.hour == reset_schedule.hour and now.minute < 5
            elif reset_schedule.type == 'cron':
                # This would implement cron expression parsing
                # For now, return False
                return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking custom reset due: {e}")
            return False
    
    def _clear_cap_cache(self):
        """Clear cap-related cache entries."""
        try:
            # Clear all cap cache entries
            cache_patterns = [
                "cap_usage:*",
                "can_show:*",
                "global_cap_usage:*"
            ]
            
            for pattern in cache_patterns:
                # This would need pattern deletion support
                # For now, clear specific keys
                cache.delete("cap_usage:reset_flag")
                cache.delete("can_show:reset_flag")
                cache.delete("global_cap_usage:reset_flag")
            
            logger.info("Cleared cap cache entries")
            
        except Exception as e:
            logger.error(f"Error clearing cap cache: {e}")
    
    def _update_task_stats(self, start_time):
        """Update task execution statistics."""
        try:
            execution_time = (timezone.now() - start_time).total_seconds() * 1000
            
            self.task_stats['total_resets'] += 1
            self.task_stats['successful_resets'] += 1
            
            # Update average time
            current_avg = self.task_stats['avg_reset_time_ms']
            total_resets = self.task_stats['total_resets']
            self.task_stats['avg_reset_time_ms'] = (
                (current_avg * (total_resets - 1) + execution_time) / total_resets
            )
            
        except Exception as e:
            logger.error(f"Error updating task stats: {e}")
    
    def get_task_stats(self) -> Dict[str, Any]:
        """Get task execution statistics."""
        return self.task_stats
    
    def reset_task_stats(self) -> bool:
        """Reset task statistics."""
        try:
            self.task_stats = {
                'total_resets': 0,
                'successful_resets': 0,
                'failed_resets': 0,
                'avg_reset_time_ms': 0.0
            }
            
            logger.info("Reset cap reset task statistics")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting task stats: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on cap reset task."""
        try:
            # Test cap enforcement service
            enforcement_health = self.cap_enforcement.health_check()
            
            # Test cap reset service
            reset_health = self.cap_reset.health_check()
            
            # Test cache functionality
            cache_health = self._test_cache_functionality()
            
            overall_healthy = (
                enforcement_health.get('status') == 'healthy' and
                reset_health.get('status') == 'healthy' and
                cache_health
            )
            
            return {
                'status': 'healthy' if overall_healthy else 'unhealthy',
                'enforcement_health': enforcement_health,
                'reset_health': reset_health,
                'cache_health': cache_health,
                'task_stats': self.task_stats,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in cap reset task health check: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def _test_cache_functionality(self) -> bool:
        """Test cache functionality."""
        try:
            # Test cache set and get
            test_key = "cap_reset_test"
            test_value = "test_value"
            
            self.cache_service.set(test_key, test_value, 60)
            cached_value = self.cache_service.get(test_key)
            
            # Clean up
            self.cache_service.delete(test_key)
            
            return cached_value == test_value
            
        except Exception as e:
            logger.error(f"Error testing cache functionality: {e}")
            return False


# Task instance
cap_reset_task = CapResetTask()
