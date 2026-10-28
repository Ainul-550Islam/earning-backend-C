# =============================================================================
# auto_mod/context_processors.py
# =============================================================================

"""
Context processors for auto moderation system.
Provides template context variables and global data.
"""
from django.conf import settings

import logging
from typing import Any, Dict
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache

from .models import ModerationQueue, TaskBot, SuspiciousSubmission
from .monitoring import health_checker
from .exceptions import ModerationError

logger = logging.getLogger(__name__)

User = get_user_model()


def auto_mod_context(request):
    """
    Global context processor for auto moderation.
    
    Args:
        request: Django request object
        
    Returns:
        Context dictionary
    """
    try:
        context = {}
        
        # Add moderation stats
        context['moderation_stats'] = get_moderation_stats()
        
        # Add queue stats
        context['queue_stats'] = get_queue_stats()
        
        # Add bot status
        context['bot_status'] = get_bot_status()
        
        # Add system health
        context['system_health'] = get_system_health()
        
        # Add user-specific data
        if request.user.is_authenticated:
            context['user_moderation_data'] = get_user_moderation_data(request.user)
        
        return context
        
    except Exception as exc:
        logger.error(f"Auto mod context processor failed: {exc}")
        return {}


def get_moderation_stats() -> Dict[str, Any]:
    """Get moderation statistics."""
    try:
        # Get from cache first
        cache_key = 'moderation_stats'
        stats = cache.get(cache_key)
        
        if not stats:
            # Calculate stats
            total_submissions = SuspiciousSubmission.objects.count()
            pending_submissions = SuspiciousSubmission.objects.filter(status='pending').count()
            approved_submissions = SuspiciousSubmission.objects.filter(status='approved').count()
            rejected_submissions = SuspiciousSubmission.objects.filter(status='rejected').count()
            
            stats = {
                'total_submissions': total_submissions,
                'pending_submissions': pending_submissions,
                'approved_submissions': approved_submissions,
                'rejected_submissions': rejected_submissions,
                'approval_rate': (approved_submissions / total_submissions * 100) if total_submissions > 0 else 0,
                'last_updated': timezone.now().isoformat(),
            }
            
            # Cache for 5 minutes
            cache.set(cache_key, stats, timeout=300)
        
        return stats
        
    except Exception as exc:
        logger.error(f"Get moderation stats failed: {exc}")
        return {}


def get_queue_stats() -> Dict[str, Any]:
    """Get queue statistics."""
    try:
        cache_key = 'queue_stats'
        stats = cache.get(cache_key)
        
        if not stats:
            total_items = ModerationQueue.objects.count()
            pending_items = ModerationQueue.objects.filter(status='pending').count()
            assigned_items = ModerationQueue.objects.filter(status='assigned').count()
            completed_items = ModerationQueue.objects.filter(status='completed').count()
            
            stats = {
                'total_items': total_items,
                'pending_items': pending_items,
                'assigned_items': assigned_items,
                'completed_items': completed_items,
                'completion_rate': (completed_items / total_items * 100) if total_items > 0 else 0,
                'last_updated': timezone.now().isoformat(),
            }
            
            cache.set(cache_key, stats, timeout=300)
        
        return stats
        
    except Exception as exc:
        logger.error(f"Get queue stats failed: {exc}")
        return {}


def get_bot_status() -> Dict[str, Any]:
    """Get bot status."""
    try:
        cache_key = 'bot_status'
        status = cache.get(cache_key)
        
        if not status:
            total_bots = TaskBot.objects.count()
            active_bots = TaskBot.objects.filter(status='running').count()
            idle_bots = TaskBot.objects.filter(status='idle').count()
            error_bots = TaskBot.objects.filter(status='error').count()
            
            status = {
                'total_bots': total_bots,
                'active_bots': active_bots,
                'idle_bots': idle_bots,
                'error_bots': error_bots,
                'active_rate': (active_bots / total_bots * 100) if total_bots > 0 else 0,
                'last_updated': timezone.now().isoformat(),
            }
            
            cache.set(cache_key, status, timeout=300)
        
        return status
        
    except Exception as exc:
        logger.error(f"Get bot status failed: {exc}")
        return {}


def get_system_health() -> Dict[str, Any]:
    """Get system health status."""
    try:
        cache_key = 'system_health'
        health = cache.get(cache_key)
        
        if not health:
            health_result = health_checker.check_system_health()
            
            health = {
                'status': health_result.get('status', 'unknown'),
                'overall_health': health_result.get('status', 'unknown'),
                'last_updated': timezone.now().isoformat(),
            }
            
            cache.set(cache_key, health, timeout=60)  # Update every minute
        
        return health
        
    except Exception as exc:
        logger.error(f"Get system health failed: {exc}")
        return {
            'status': 'error',
            'overall_health': 'error',
            'last_updated': timezone.now().isoformat(),
        }


def get_user_moderation_data(user) -> Dict[str, Any]:
    """Get user-specific moderation data."""
    try:
        if not user or not user.is_authenticated:
            return {}
        
        cache_key = f'user_moderation_data_{user.id}'
        user_data = cache.get(cache_key)
        
        if not user_data:
            # Get user's queue items
            user_queue_items = ModerationQueue.objects.filter(
                assigned_to=user
            ).count()
            
            # Get user's recent decisions
            recent_decisions = user.moderationdecision_set.filter(
                decided_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).count()
            
            # Get user's submissions
            user_submissions = SuspiciousSubmission.objects.filter(
                user=user
            ).count()
            
            user_data = {
                'queue_items': user_queue_items,
                'recent_decisions': recent_decisions,
                'total_submissions': user_submissions,
                'is_moderator': user.is_staff,
                'last_updated': timezone.now().isoformat(),
            }
            
            cache.set(cache_key, user_data, timeout=300)
        
        return user_data
        
    except Exception as exc:
        logger.error(f"Get user moderation data failed: {exc}")
        return {}


def moderation_navigation_context(request):
    """
    Context processor for moderation navigation.
    
    Args:
        request: Django request object
        
    Returns:
        Navigation context
    """
    try:
        if not request.user.is_authenticated:
            return {}
        
        navigation_items = []
        
        # Add navigation items based on user role
        if request.user.is_staff:
            navigation_items.extend([
                {
                    'name': 'Dashboard',
                    'url': '/auto_mod/dashboard/',
                    'icon': 'dashboard',
                    'active': request.path.startswith('/auto_mod/dashboard/'),
                },
                {
                    'name': 'Queue',
                    'url': '/auto_mod/queue/',
                    'icon': 'queue',
                    'active': request.path.startswith('/auto_mod/queue/'),
                },
                {
                    'name': 'Submissions',
                    'url': '/auto_mod/submissions/',
                    'icon': 'submissions',
                    'active': request.path.startswith('/auto_mod/submissions/'),
                },
                {
                    'name': 'Decisions',
                    'url': '/auto_mod/decisions/',
                    'icon': 'decisions',
                    'active': request.path.startswith('/auto_mod/decisions/'),
                },
                {
                    'name': 'Appeals',
                    'url': '/auto_mod/appeals/',
                    'icon': 'appeals',
                    'active': request.path.startswith('/auto_mod/appeals/'),
                },
                {
                    'name': 'Analytics',
                    'url': '/auto_mod/analytics/',
                    'icon': 'analytics',
                    'active': request.path.startswith('/auto_mod/analytics/'),
                },
            ])
        
        # Add admin-only items
        if request.user.is_superuser:
            navigation_items.extend([
                {
                    'name': 'Settings',
                    'url': '/auto_mod/settings/',
                    'icon': 'settings',
                    'active': request.path.startswith('/auto_mod/settings/'),
                },
                {
                    'name': 'Bots',
                    'url': '/auto_mod/bots/',
                    'icon': 'bots',
                    'active': request.path.startswith('/auto_mod/bots/'),
                },
                {
                    'name': 'Rules',
                    'url': '/auto_mod/rules/',
                    'icon': 'rules',
                    'active': request.path.startswith('/auto_mod/rules/'),
                },
            ])
        
        return {
            'moderation_navigation': navigation_items,
        }
        
    except Exception as exc:
        logger.error(f"Moderation navigation context failed: {exc}")
        return {}


def notification_context(request):
    """
    Context processor for notifications.
    
    Args:
        request: Django request object
        
    Returns:
        Notification context
    """
    try:
        if not request.user.is_authenticated:
            return {}
        
        # Get notification count
        notification_count = 0
        
        if request.user.is_staff:
            # Get queue items for staff
            notification_count += ModerationQueue.objects.filter(
                assigned_to=request.user,
                status='pending'
            ).count()
        
        return {
            'notification_count': notification_count,
        }
        
    except Exception as exc:
        logger.error(f"Notification context failed: {exc}")
        return {}


def feature_flags_context(request):
    """
    Context processor for feature flags.
    
    Args:
        request: Django request object
        
    Returns:
        Feature flags context
    """
    try:
        from .feature_flags import feature_flag_manager
        
        if not request.user.is_authenticated:
            return {}
        
        # Get user's enabled features
        enabled_features = feature_flag_manager.get_enabled_features(str(request.user.id))
        
        # Convert to simple dict
        features = {}
        for feature_name, feature in enabled_features.items():
            features[feature_name] = feature.to_dict()
        
        return {
            'feature_flags': features,
        }
        
    except Exception as exc:
        logger.error(f"Feature flags context failed: {exc}")
        return {}


def user_permissions_context(request):
    """
    Context processor for user permissions.
    
    Args:
        request: Django request object
        
    Returns:
        User permissions context
    """
    try:
        if not request.user.is_authenticated:
            return {}
        
        permissions = {
            'can_moderate': request.user.has_perm('auto_mod.can_moderate'),
            'can_manage_queue': request.user.has_perm('auto_mod.manage_queue'),
            'can_view_analytics': request.user.has_perm('auto_mod.view_analytics'),
            'can_manage_bots': request.user.has_perm('auto_mod.manage_bots'),
            'can_manage_rules': request.user.has_perm('auto_mod.manage_rules'),
            'can_export_data': request.user.has_perm('auto_mod.export_data'),
            'is_moderator': request.user.is_staff,
            'is_admin': request.user.is_superuser,
        }
        
        return {
            'user_permissions': permissions,
        }
        
    except Exception as exc:
        logger.error(f"User permissions context failed: {exc}")
        return {}


def theme_context(request):
    """
    Context processor for theme settings.
    
    Args:
        request: Django request object
        
    Returns:
        Theme context
    """
    try:
        # Get theme preferences
        theme = {
            'dark_mode': request.COOKIES.get('dark_mode', 'false') == 'true',
            'compact_mode': request.COOKIES.get('compact_mode', 'false') == 'true',
            'sidebar_collapsed': request.COOKIES.get('sidebar_collapsed', 'false') == 'true',
        }
        
        return {
            'theme': theme,
        }
        
    except Exception as exc:
        logger.error(f"Theme context failed: {exc}")
        return {
            'theme': {
                'dark_mode': False,
                'compact_mode': False,
                'sidebar_collapsed': False,
            }
        }


def system_info_context(request):
    """
    Context processor for system information.
    
    Args:
        request: Django request object
        
    Returns:
        System information context
    """
    try:
        from django.conf import settings
        
        system_info = {
            'version': getattr(settings, 'AUTO_MOD_VERSION', '1.0.0'),
            'environment': getattr(settings, 'ENVIRONMENT', 'development'),
            'debug': settings.DEBUG,
            'timezone': settings.TIME_ZONE,
            'language': settings.LANGUAGE_CODE,
        }
        
        return {
            'system_info': system_info,
        }
        
    except Exception as exc:
        logger.error(f"System info context failed: {exc}")
        return {}


def performance_context(request):
    """
    Context processor for performance metrics.
    
    Args:
        request: Django request object
        
    Returns:
        Performance context
    """
    try:
        # Only add performance context in debug mode
        if not getattr(settings, 'DEBUG', False):
            return {}
        
        from django.db import connection
        
        # Get database query count
        query_count = len(connection.queries)
        
        # Get request processing time
        processing_time = getattr(request, 'processing_time', 0)
        
        performance = {
            'query_count': query_count,
            'processing_time': processing_time,
            'memory_usage': getattr(request, 'memory_usage', 0),
        }
        
        return {
            'performance': performance,
        }
        
    except Exception as exc:
        logger.error(f"Performance context failed: {exc}")
        return {}


# Initialize logging
logger.info("Context processors module initialized with template context variables")
