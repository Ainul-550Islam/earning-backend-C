from django.db.models.functions import TruncDate
import logging
import json
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import timedelta, datetime
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg, Prefetch, F, ExpressionWrapper, fields
from django.http import JsonResponse
from django.conf import settings
from api.tenants.mixins import TenantMixin
from rest_framework import viewsets, status, generics, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
# এই line টা আগে থেকে আছে, এখানে দুটো যোগ করুন:
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied, NotAuthenticated, AuthenticationFailed

# Import models
from .models import MasterTask, UserTaskCompletion

# Import serializers
from .serializers import (
    MasterTaskSerializer, 
    TaskCompletionSerializer, 
    TaskListSerializer,
    BulkTaskOperationSerializer,
    TaskStatisticsSerializer,
    ErrorResponseSerializer
)
from api.tasks.models_base import AdminLedger

# Setup logging
logger = logging.getLogger(__name__)

# ============ CONSTANTS (Instead of missing constants.py) ============

# Task Templates
TASK_TEMPLATES = {
    'daily_checkin': {
        'metadata': {'checkin_streak_bonus': True},
        'rewards': {'points': 5, 'experience': 2},
        'ui_config': {'icon': 'calendar_check.png'}
    },
    'spin_wheel': {
        'metadata': {'game_type': 'spin', 'segments': 8},
        'rewards': {'points': 0, 'experience': 5},
        'ui_config': {'icon': 'wheel.png'}
    },
    # Add more templates as needed
}

# System Type Mapping
SYSTEM_TYPE_MAPPING = {
    'daily_checkin': 'click_visit',
    'spin_wheel': 'gamified',
    # Add more mappings
}

# ============ UTILITY FUNCTIONS (Instead of missing utils.py) ============

def calculate_next_available_time(task: MasterTask, user_id: int) -> Optional[datetime]:
    """
    Calculate when a task will be next available for a user
    """
    try:
        # Check daily limit
        if task.daily_completion_limit:
            today_start = timezone.now().replace(hour=0, minute=0, second=0)
            
            today_completions = UserTaskCompletion.objects.filter(
                user_id=user_id,
                task=task,
                completed_at__gte=today_start
            ).count()
            
            if today_completions >= task.daily_completion_limit:
                # Next available tomorrow
                return today_start + timedelta(days=1)
        
        # Check cooldown
        cooldown = task.constraints.get('cooldown_minutes', 0) if task.constraints else 0
        if cooldown > 0:
            last_completion = UserTaskCompletion.objects.filter(
                user_id=user_id,
                task=task,
                status='completed'
            ).order_by('-completed_at').first()
            
            if last_completion and last_completion.completed_at:
                cooldown_end = last_completion.completed_at + timedelta(minutes=cooldown)
                if cooldown_end > timezone.now():
                    return cooldown_end
        
        return None
        
    except Exception as e:
        logger.error(f"Error calculating next available time: {str(e)}")
        return None


def safe_date_from_iso(date_string: Optional[str]) -> Optional[datetime]:
    """
    Safely parse ISO date string with compatibility for Python 3.6+
    """
    if not date_string:
        return None
    
    try:
        # Try Python 3.7+ method
        if hasattr(datetime, 'fromisoformat'):
            return datetime.fromisoformat(date_string)
        
        # Fallback for Python 3.6 and below
        # Format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
        import re
        if 'T' in date_string:
            # With time
            date_part, time_part = date_string.split('T')
            time_part = time_part.split('.')[0]  # Remove microseconds
            year, month, day = map(int, date_part.split('-'))
            hour, minute, second = map(int, time_part.split(':'))
            return datetime(year, month, day, hour, minute, second)
        else:
            # Date only
            year, month, day = map(int, date_string.split('-'))
            return datetime(year, month, day)
            
    except (ValueError, TypeError, AttributeError) as e:
        logger.debug(f"Error parsing date {date_string}: {str(e)}")
        return None


# ============ SENTINEL VALUE (Single definition) ============

class _Missing:
    """Sentinel value for missing data (not None)"""
    def __repr__(self):
        return '<MISSING>'
    
    def __bool__(self):
        return False

MISSING = _Missing()


# ============ HELPER FUNCTIONS ============

def safe_get_request_data(request: Request, key: str, default=None):
    """Safely get data from request (GET, POST, JSON)"""
    try:
        # Try GET params
        if request.method == 'GET':
            return request.query_params.get(key, default)
        
        # Try POST data
        if request.method == 'POST':
            # Try JSON first
            if request.content_type == 'application/json':
                try:
                    data = request.data
                    if isinstance(data, dict):
                        return data.get(key, default)
                except Exception:
                    pass
            return request.POST.get(key, default)
        
        return default
    except Exception as e:
        logger.debug(f"Error getting request data for {key}: {str(e)}")
        return default


def safe_int_from_request(request: Request, key: str, default: int = 0) -> int:
    """Safely get integer from request"""
    try:
        value = safe_get_request_data(request, key)
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def safe_bool_from_request(request: Request, key: str, default: bool = False) -> bool:
    """Safely get boolean from request"""
    try:
        value = safe_get_request_data(request, key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', '1', 'on')
        return bool(value) if value is not None else default
    except Exception:
        return default


def get_client_ip(request: Request) -> Optional[str]:
    """Get client IP address safely"""
    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
    except Exception:
        return None


def get_user_agent(request: Request) -> str:
    """Get user agent safely"""
    try:
        return request.META.get('HTTP_USER_AGENT', '')
    except Exception:
        return ''


def get_redis_connection_safe():
    """Get Redis connection with error handling"""
    try:
        from django_redis import get_redis_connection
        return get_redis_connection("default")
    except ImportError:
        logger.debug("django_redis not installed")
        return None
    except Exception as e:
        logger.debug(f"Redis connection error: {str(e)}")
        return None


# ============ CIRCUIT BREAKER PATTERN ============

class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls
    """
    
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
    
    def __call__(self, func):
        """Decorator usage"""
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        try:
            # Check if circuit is open
            if self.state == 'open':
                if self.last_failure_time and \
                   (timezone.now() - self.last_failure_time).seconds > self.recovery_timeout:
                    self.state = 'half-open'
                    logger.info(f"Circuit {self.name} moved to half-open state")
                else:
                    logger.warning(f"Circuit {self.name} is open - returning fallback")
                    return self._get_fallback_response(*args, **kwargs)
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Success - reset if half-open
            if self.state == 'half-open':
                self.state = 'closed'
                self.failure_count = 0
                logger.info(f"Circuit {self.name} closed after successful call")
            
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = timezone.now()
            
            # Check if threshold reached
            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
                logger.warning(f"Circuit {self.name} opened after {self.failure_count} failures")
            
            logger.error(f"Error in circuit breaker {self.name}: {str(e)}")
            return self._get_fallback_response(*args, **kwargs)
    
    def _get_fallback_response(self, *args, **kwargs):
        """Get fallback response when circuit is open"""
        return Response(
            ErrorResponseSerializer({
                'error': 'Service temporarily unavailable',
                'error_code': 'CIRCUIT_OPEN',
                'message': f'{self.name} is currently unavailable. Please try again later.'
            }).data,
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )


# Circuit breaker instances
task_view_circuit = CircuitBreaker('task_views', failure_threshold=10, recovery_timeout=120)


# ============ CUSTOM PAGINATION ============

class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for API responses"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        """Override to add metadata"""
        return Response({
            'status': 'success',
            'data': data,
            'pagination': {
                'current_page': self.page.number,
                'total_pages': self.page.paginator.num_pages,
                'total_items': self.page.paginator.count,
                'page_size': self.get_page_size(self.request),
                'has_next': self.page.has_next(),
                'has_previous': self.page.has_previous(),
            }
        })


class LargeResultsSetPagination(PageNumberPagination):
    """Large pagination for admin endpoints"""
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000
    page_query_param = 'page'


# ============ PERMISSIONS ============

class IsAdminUser(IsAuthenticated):
    """Custom permission for admin users"""
    
    def has_permission(self, request, view):
        is_authenticated = super().has_permission(request, view)
        if not is_authenticated:
            return False
        
        # Check if user is admin
        user = request.user
        return getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False)


# ============ BASE VIEWSET WITH BULLETPROOF PATTERNS ============

# class BulletproofViewSet(TenantMixin, viewsets.GenericViewSet):
class BulletproofViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    Base ViewSet with bulletproof patterns
    All viewsets should inherit from this
    """

    # Default pagination
    pagination_class = StandardResultsSetPagination

    def get_serializer_context(self):
        """Add request to serializer context"""
        context = super().get_serializer_context()
        context.update({
            'user_level': safe_int_from_request(self.request, 'user_level', 1),
            'user_id': getattr(self.request.user, 'id', None) if self.request.user.is_authenticated else None,
            'include_stats': safe_bool_from_request(self.request, 'include_stats', False)
        })
        return context

    def handle_exception(self, exc):
        """Custom exception handling with graceful degradation"""
        try:
            # ✅ FIX 1: NotAuthenticated / AuthenticationFailed handle করা হয়েছে
            if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
                return Response(
                    {
                        'error': 'Authentication required',
                        'error_code': 'NOT_AUTHENTICATED',
                        'details': None
                    },
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # ✅ FIX 2: ErrorResponseSerializer সরিয়ে plain dict ব্যবহার করা হয়েছে
            if isinstance(exc, ValidationError):
                return Response(
                    {
                        'error': 'Validation error',
                        'error_code': 'VALIDATION_ERROR',
                        'details': exc.detail if hasattr(exc, 'detail') else {'message': str(exc)}
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            if isinstance(exc, NotFound):
                return Response(
                    {
                        'error': 'Resource not found',
                        'error_code': 'NOT_FOUND',
                        'details': {'message': str(exc)}
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            if isinstance(exc, PermissionDenied):
                return Response(
                    {
                        'error': 'Permission denied',
                        'error_code': 'PERMISSION_DENIED',
                        'details': {'message': str(exc)}
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # ✅ FIX 3: details এ str() এর বদলে dict পাঠানো হচ্ছে
            logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
            return Response(
                {
                    'error': 'An unexpected error occurred',
                    'error_code': 'INTERNAL_ERROR',
                    'details': {'message': str(exc)} if settings.DEBUG else None
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        except Exception as e:
            logger.critical(f"Error in error handler: {str(e)}")
            return Response(
                {'error': 'Critical system error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def finalize_response(self, request, response, *args, **kwargs):
        """Add request ID to response headers"""
        response = super().finalize_response(request, response, *args, **kwargs)

        # Add request ID for tracking
        request_id = getattr(request, 'id', None)
        if request_id:
            response['X-Request-ID'] = str(request_id)

        # Add cache control headers
        if request.method == 'GET':
            response['Cache-Control'] = 'max-age=60'

        return response


# ============ MASTER TASK VIEWSET ============

class MasterTaskViewSet(BulletproofViewSet):
    """
    Unified API for all tasks with bulletproof error handling
    """
    
    queryset = MasterTask.objects.all()
    serializer_class = MasterTaskSerializer
    permission_classes = [AllowAny]
    lookup_field = 'task_id'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'task_id']
    ordering_fields = ['sort_order', 'created_at', 'total_completions', 'name']
    ordering = ['sort_order', '-created_at']
    
    # Pagination
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """
        Apply filters with safety checks
        Uses select_related and prefetch_related for optimization
        """
        try:
            queryset = super().get_queryset()
            
            # Get page size from request for prefetch limit
            page_size = self.paginator.get_page_size(self.request) if self.paginator else 20
            prefetch_limit = min(page_size * 2, 100)  # Dynamic limit based on page size
            
            # Prefetch completions with dynamic limit
            queryset = queryset.prefetch_related(
                Prefetch(
                    'completions', 
                    queryset=UserTaskCompletion.objects.filter(status='completed').order_by('-completed_at')[:prefetch_limit],
                    to_attr='recent_completions'
                )
            )
            
            # Get query params safely
            request = self.request
            
            # Filter by system type
            system_type = safe_get_request_data(request, 'system_type')
            if system_type:
                queryset = queryset.filter(system_type=system_type)
            
            # Filter by category
            category = safe_get_request_data(request, 'category')
            if category:
                queryset = queryset.filter(category=category)
            
            # Filter featured only
            featured_only = safe_bool_from_request(request, 'featured')
            if featured_only:
                queryset = queryset.filter(is_featured=True)
            
            # Filter by active status
            show_inactive = safe_bool_from_request(request, 'show_inactive')
            if not show_inactive:
                queryset = queryset.filter(is_active=True)
            
            # Filter by user level
            user_level = safe_int_from_request(request, 'user_level', 1)
            queryset = queryset.filter(
                Q(min_user_level__lte=user_level) & 
                (Q(max_user_level__isnull=True) | Q(max_user_level__gte=user_level))
            )
            
            # Filter by availability
            now = timezone.now()
            available_only = safe_bool_from_request(request, 'available_only')
            if available_only:
                queryset = queryset.filter(
                    Q(available_from__lte=now) & 
                    (Q(available_until__isnull=True) | Q(available_until__gte=now))
                )
            
            return queryset.distinct()
            
        except Exception as e:
            logger.error(f"Error filtering queryset: {str(e)}")
            # Return base queryset on error
            return MasterTask.objects.all()
    
    @task_view_circuit
    def retrieve(self, request, *args, **kwargs):
        """Get single task with circuit breaker protection"""
        try:
            instance = self.get_object()
            
            # Get user level from request
            user_level = safe_int_from_request(request, 'user_level', 1)
            user_id = request.user.id if request.user.is_authenticated else None
            
            # Check availability
            if user_id:
                is_available, reason = instance.is_available_with_cooldown(user_level, user_id)
            else:
                is_available, reason = instance.is_available_for_user(user_level)
            
            # Serialize with context
            serializer = self.get_serializer(
                instance, 
                context={
                    'user_level': user_level,
                    'user_id': user_id,
                    'include_stats': safe_bool_from_request(request, 'include_stats', False)
                }
            )
            
            response_data = serializer.data
            response_data['is_available'] = is_available
            if not is_available and reason:
                response_data['unavailable_reason'] = reason
            
            return Response({
                'status': 'success',
                'data': response_data
            })
            
        except MasterTask.DoesNotExist:
            return Response(
                ErrorResponseSerializer({
                    'error': 'Task not found',
                    'error_code': 'TASK_NOT_FOUND',
                    'details': f"Task with ID {kwargs.get('task_id')} does not exist"
                }).data,
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error retrieving task: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to retrieve task',
                    'error_code': 'RETRIEVE_ERROR',
                    'details': str(e) if settings.DEBUG else None
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='by-system')
    def by_system(self, request):
        """Get tasks grouped by system type with caching"""
        try:
            # Try cache first
            cache_key = f"tasks_by_system_{safe_int_from_request(request, 'user_level', 1)}"
            cached_data = cache.get(cache_key)
            
            if cached_data:
                return Response({
                    'status': 'success',
                    'data': cached_data,
                    'cached': True
                })
            
            # Get filtered queryset
            queryset = self.get_queryset()
            
            # Group by system type
            result = []
            for system_type, system_name in MasterTask.SystemType.choices:
                tasks = queryset.filter(system_type=system_type)
                if tasks.exists():
                    serializer = self.get_serializer(tasks, many=True)
                    result.append({
                        'system_type': system_type,
                        'system_name': system_name,
                        'tasks': serializer.data,
                        'count': tasks.count()
                    })
            
            # Cache for 5 minutes
            cache.set(cache_key, result, timeout=300)
            
            return Response({
                'status': 'success',
                'data': result,
                'total_tasks': queryset.count()
            })
            
        except Exception as e:
            logger.error(f"Error grouping tasks: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to group tasks',
                    'error_code': 'GROUPING_ERROR'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='featured')
    def featured_tasks(self, request):
        """Get featured tasks"""
        try:
            queryset = self.get_queryset().filter(is_featured=True)[:20]
            serializer = self.get_serializer(queryset, many=True)
            
            return Response({
                'status': 'success',
                'data': serializer.data,
                'count': len(serializer.data)
            })
            
        except Exception as e:
            logger.error(f"Error fetching featured tasks: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to fetch featured tasks'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'], url_path='check-availability')
    def check_availability(self, request, task_id=None):
        """Check if task is available for current user"""
        try:
            task = self.get_object()
            user_level = safe_int_from_request(request, 'user_level', 1)
            user_id = request.user.id if request.user.is_authenticated else None
            
            if user_id:
                is_available, reason = task.is_available_with_cooldown(user_level, user_id)
            else:
                is_available, reason = task.is_available_for_user(user_level)
            
            # Get next available time if not available
            next_available = None
            if not is_available and user_id:
                next_available = calculate_next_available_time(task, user_id)
            
            return Response({
                'status': 'success',
                'data': {
                    'task_id': task.task_id,
                    'is_available': is_available,
                    'reason': reason,
                    'next_available': next_available.isoformat() if next_available else None,
                    'user_level': user_level
                }
            })
            
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to check availability'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'], url_path='statistics')
    def task_statistics(self, request, task_id=None):
        """Get detailed statistics for a task"""
        try:
            task = self.get_object()
            
            stats = {
                'total_completions': task.total_completions,
                'unique_users': task.unique_users_completed,
                'completion_rate': task.get_completion_rate(),
                'unique_users_30d': task.get_unique_users_last_30_days(),
                'avg_completion_time': task.get_average_completion_time(),
                'daily_average': self._get_daily_average(task),
                'peak_hours': self._get_peak_hours(task),
                'completion_by_level': self._get_completion_by_level(task)
            }
            
            return Response({
                'status': 'success',
                'data': stats
            })
            
        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to get statistics'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_daily_average(self, task: MasterTask) -> float:
        """Get daily average completions"""
        try:
            from django.db.models.functions import TruncDate
            
            last_30_days = timezone.now() - timedelta(days=30)
            
            daily_counts = task.completions.filter(
                completed_at__gte=last_30_days,
                status='completed'
            ).annotate(
                date=TruncDate('completed_at')
            ).values('date').annotate(
                count=Count('id')
            ).order_by('date')
            
            if daily_counts:
                avg = sum(d['count'] for d in daily_counts) / len(daily_counts)
                return round(avg, 2)
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating daily average: {str(e)}")
            return 0.0
    
    def _get_peak_hours(self, task: MasterTask) -> List[Dict]:
        """Get peak completion hours"""
        try:
            from django.db.models.functions import ExtractHour
            
            hour_counts = task.completions.filter(
                status='completed',
                completed_at__isnull=False
            ).annotate(
                hour=ExtractHour('completed_at')
            ).values('hour').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            return [
                {'hour': int(h['hour']), 'count': h['count']} 
                for h in hour_counts if h['hour'] is not None
            ]
            
        except Exception as e:
            logger.error(f"Error getting peak hours: {str(e)}")
            return []
    
    def _get_completion_by_level(self, task: MasterTask) -> Dict[str, int]:
        """Get completion count by user level"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            if hasattr(User, 'level'):
                level_counts = task.completions.filter(
                    status='completed'
                ).values('user__level').annotate(
                    count=Count('id')
                ).order_by('user__level')
                
                return {
                    str(item['user__level']): item['count'] 
                    for item in level_counts 
                    if item['user__level'] is not None
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting completion by level: {str(e)}")
            return {}
    
    @action(detail=False, methods=['post'], url_path='bulk-import', permission_classes=[IsAdminUser])
    def bulk_import_tasks(self, request):
        """Bulk import tasks from templates (Admin only)"""
        try:
            imported = []
            errors = []
            
            with transaction.atomic():
                for task_key, template in TASK_TEMPLATES.items():
                    try:
                        # Check if task already exists
                        if MasterTask.objects.filter(task_id=task_key).exists():
                            continue
                        
                        # Create task
                        task = MasterTask.objects.create(
                            task_id=task_key,
                            name=task_key.replace('_', ' ').title(),
                            description=f"Complete {task_key.replace('_', ' ')} task to earn rewards",
                            system_type=SYSTEM_TYPE_MAPPING.get(task_key, 'click_visit'),
                            category=self._guess_category(task_key),
                            task_metadata=template.get('metadata', {}),
                            rewards=template.get('rewards', {'points': 10}),
                            ui_config=template.get('ui_config', {})
                        )
                        imported.append(task_key)
                        
                    except Exception as e:
                        errors.append({task_key: str(e)})
                        logger.error(f"Error importing {task_key}: {str(e)}")
            
            return Response({
                'status': 'success',
                'imported': imported,
                'count': len(imported),
                'errors': errors
            })
            
        except Exception as e:
            logger.error(f"Bulk import failed: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Bulk import failed',
                    'details': str(e) if settings.DEBUG else None
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _guess_category(self, task_key: str) -> str:
        """Guess category from task key"""
        category_mapping = {
            'daily': 'daily_retention',
            'checkin': 'daily_retention',
            'streak': 'daily_retention',
            'spin': 'gamified',
            'scratch': 'gamified',
            'slot': 'gamified',
            'game': 'gamified',
            'quiz': 'gamified',
            'math': 'gamified',
            'video': 'ads_multimedia',
            'ad': 'ads_multimedia',
            'audio': 'ads_multimedia',
            'social': 'app_social',
            'share': 'app_social',
            'follow': 'app_social',
            'subscribe': 'app_social',
            'app': 'app_social',
            'web': 'web_content',
            'article': 'web_content',
            'read': 'web_content',
            'refer': 'refer_team',
            'team': 'refer_team',
            'invite': 'refer_team',
            'offer': 'advanced_api',
            'survey': 'advanced_api',
            'prediction': 'advanced_api',
            'tiered': 'advanced_api'
        }
        
        task_key_lower = task_key.lower()
        for key, category in category_mapping.items():
            if key in task_key_lower:
                return category
        
        return 'daily_retention'


# ============ ANALYTICS VIEWSET ============

class AnalyticsViewSet(BulletproofViewSet):
    """
    Advanced analytics and reporting endpoints
    """
    
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        """Get comprehensive dashboard analytics"""
        try:
            user = request.user
            is_staff = getattr(user, 'is_staff', False)
            
            # Time range
            days = safe_int_from_request(request, 'days', 30)
            from_date = timezone.now() - timedelta(days=days)
            
            dashboard_data = {
                'user_stats': self._get_user_stats(user, from_date, is_staff),
                'task_stats': self._get_task_stats(from_date, is_staff),
                'revenue_stats': self._get_revenue_stats(user, from_date, is_staff),
                'engagement_stats': self._get_engagement_stats(from_date, is_staff),
                'performance_metrics': self._get_performance_metrics(from_date, is_staff)
            }
            
            return Response({
                'status': 'success',
                'data': dashboard_data,
                'timeframe': f'{days} days',
                'generated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Dashboard analytics error: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to generate dashboard analytics'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='real-time')
    def real_time_analytics(self, request):
        """Get real-time analytics data"""
        try:
            # Get recent activity (last 5 minutes)
            cutoff = timezone.now() - timedelta(minutes=5)
            
            recent_completions = UserTaskCompletion.objects.filter(
                completed_at__gte=cutoff,
                status='completed'
            ).select_related('task', 'user')
            
            # Calculate real-time metrics
            metrics = {
                'active_users': recent_completions.values('user_id').distinct().count(),
                'completions_per_minute': recent_completions.count() / 5,
                'popular_tasks': self._get_popular_tasks(recent_completions),
                'revenue_per_minute': self._calculate_real_time_revenue(recent_completions),
                'conversion_rates': self._get_real_time_conversion_rates(cutoff)
            }
            
            return Response({
                'status': 'success',
                'data': metrics,
                'timestamp': timezone.now().isoformat(),
                'window': '5 minutes'
            })
            
        except Exception as e:
            logger.error(f"Real-time analytics error: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to get real-time analytics'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='trends')
    def analytics_trends(self, request):
        """Get analytics trends over time"""
        try:
            days = safe_int_from_request(request, 'days', 30)
            metric = safe_get_request_data(request, 'metric', 'completions')
            
            from_date = timezone.now() - timedelta(days=days)
            
            trends_data = {
                'daily_trends': self._get_daily_trends(from_date, metric),
                'weekly_comparison': self._get_weekly_comparison(from_date, metric),
                'growth_rates': self._calculate_growth_rates(from_date, metric),
                'predictions': self._generate_predictions(metric, days)
            }
            
            return Response({
                'status': 'success',
                'data': trends_data,
                'metric': metric,
                'period': f'{days} days'
            })
            
        except Exception as e:
            logger.error(f"Trends analytics error: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to get trends analytics'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='user-behavior')
    def user_behavior_analytics(self, request):
        """Analyze user behavior patterns"""
        try:
            days = safe_int_from_request(request, 'days', 30)
            from_date = timezone.now() - timedelta(days=days)
            
            behavior_data = {
                'user_segments': self._analyze_user_segments(from_date),
                'retention_analysis': self._analyze_retention(from_date),
                'engagement_patterns': self._analyze_engagement_patterns(from_date),
                'conversion_funnel': self._analyze_conversion_funnel(from_date),
                'cohort_analysis': self._analyze_cohorts(from_date)
            }
            
            return Response({
                'status': 'success',
                'data': behavior_data,
                'analysis_period': f'{days} days'
            })
            
        except Exception as e:
            logger.error(f"User behavior analytics error: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to analyze user behavior'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_user_stats(self, user, from_date, is_staff):
        """Get user statistics"""
        try:
            if is_staff:
                # Admin sees all users
                total_users = User.objects.filter(date_joined__gte=from_date).count()
                active_users = UserTaskCompletion.objects.filter(
                    completed_at__gte=from_date,
                    status='completed'
                ).values('user_id').distinct().count()
                
                return {
                    'total_users': total_users,
                    'active_users': active_users,
                    'new_users_today': User.objects.filter(
                        date_joined__gte=timezone.now() - timedelta(days=1)
                    ).count(),
                    'user_growth_rate': self._calculate_user_growth_rate(from_date)
                }
            else:
                # Regular user sees their own stats
                user_completions = UserTaskCompletion.objects.filter(
                    user=user,
                    completed_at__gte=from_date,
                    status='completed'
                )
                
                return {
                    'total_completions': user_completions.count(),
                    'total_earned': user_completions.aggregate(
                        total=Sum('reward_amount')
                    )['total'] or 0,
                    'completion_streak': self._calculate_completion_streak(user),
                    'level': getattr(user, 'level', 1),
                    'experience_points': getattr(user, 'experience', 0)
                }
        except Exception as e:
            logger.error(f"User stats error: {str(e)}")
            return {}
    
    def _get_task_stats(self, from_date, is_staff):
        """Get task statistics"""
        try:
            tasks = MasterTask.objects.filter(is_active=True)
            
            if not is_staff:
                tasks = tasks.filter(
                    available_from__lte=timezone.now(),
                    available_until__gte=timezone.now()
                )
            
            completions = UserTaskCompletion.objects.filter(
                completed_at__gte=from_date,
                status='completed'
            )
            
            return {
                'total_tasks': tasks.count(),
                'active_tasks': tasks.filter(is_active=True).count(),
                'featured_tasks': tasks.filter(is_featured=True).count(),
                'total_completions': completions.count(),
                'average_completion_time': self._calculate_avg_completion_time(completions),
                'top_performing_tasks': self._get_top_tasks(completions, 10)
            }
        except Exception as e:
            logger.error(f"Task stats error: {str(e)}")
            return {}
    
    def _get_revenue_stats(self, user, from_date, is_staff):
        """Get revenue statistics"""
        try:
            if is_staff:
                # Admin sees all revenue
                total_revenue = UserTaskCompletion.objects.filter(
                    completed_at__gte=from_date,
                    status='completed'
                ).aggregate(total=Sum('reward_amount'))['total'] or 0
                
                admin_revenue = AdminLedger.objects.filter(
                    created_at__gte=from_date
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                return {
                    'total_revenue': float(total_revenue),
                    'admin_revenue': float(admin_revenue),
                    'payout_rate': float(admin_revenue) / float(total_revenue) if total_revenue > 0 else 0,
                    'daily_average': float(total_revenue) / 30
                }
            else:
                # Regular user sees their earnings
                user_earnings = UserTaskCompletion.objects.filter(
                    user=user,
                    completed_at__gte=from_date,
                    status='completed'
                ).aggregate(total=Sum('reward_amount'))['total'] or 0
                
                return {
                    'total_earned': float(user_earnings),
                    'daily_average': float(user_earnings) / 30,
                    'pending_earnings': UserTaskCompletion.objects.filter(
                        user=user,
                        status='pending'
                    ).aggregate(total=Sum('reward_amount'))['total'] or 0
                }
        except Exception as e:
            logger.error(f"Revenue stats error: {str(e)}")
            return {}
    
    def _get_engagement_stats(self, from_date, is_staff):
        """Get engagement statistics"""
        try:
            completions = UserTaskCompletion.objects.filter(
                completed_at__gte=from_date,
                status='completed'
            )
            
            return {
                'daily_active_users': self._calculate_dau(from_date),
                'monthly_active_users': self._calculate_mau(from_date),
                'engagement_rate': self._calculate_engagement_rate(from_date),
                'retention_rate': self._calculate_retention_rate(from_date),
                'average_session_duration': self._calculate_avg_session_duration(completions)
            }
        except Exception as e:
            logger.error(f"Engagement stats error: {str(e)}")
            return {}
    
    def _get_performance_metrics(self, from_date, is_staff):
        """Get performance metrics"""
        try:
            return {
                'api_response_time': self._get_api_response_time(),
                'error_rate': self._get_error_rate(from_date),
                'throughput': self._get_throughput(from_date),
                'cache_hit_rate': self._get_cache_hit_rate(),
                'database_query_time': self._get_db_query_time()
            }
        except Exception as e:
            logger.error(f"Performance metrics error: {str(e)}")
            return {}
    
    # Helper methods for analytics calculations
    def _get_popular_tasks(self, completions):
        """Get most popular tasks"""
        return list(
            completions.values('task__name', 'task__task_id')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
    
    def _calculate_real_time_revenue(self, completions):
        """Calculate real-time revenue"""
        total = completions.aggregate(total=Sum('reward_amount'))['total'] or 0
        return float(total) / 5  # per minute
    
    def _get_real_time_conversion_rates(self, cutoff):
        """Get real-time conversion rates"""
        started = UserTaskCompletion.objects.filter(
            started_at__gte=cutoff
        ).count()
        
        completed = UserTaskCompletion.objects.filter(
            completed_at__gte=cutoff,
            status='completed'
        ).count()
        
        return {
            'started': started,
            'completed': completed,
            'conversion_rate': (completed / started * 100) if started > 0 else 0
        }
    
    def _get_daily_trends(self, from_date, metric):
        """Get daily trends for a metric"""
        try:
            from django.db.models.functions import TruncDate
            
            if metric == 'completions':
                daily_data = UserTaskCompletion.objects.filter(
                    completed_at__gte=from_date,
                    status='completed'
                ).annotate(
                    date=TruncDate('completed_at')
                ).values('date').annotate(
                    count=Count('id')
                ).order_by('date')
                
                return [
                    {'date': item['date'].isoformat(), 'value': item['count']}
                    for item in daily_data
                ]
            
            elif metric == 'revenue':
                daily_data = UserTaskCompletion.objects.filter(
                    completed_at__gte=from_date,
                    status='completed'
                ).annotate(
                    date=TruncDate('completed_at')
                ).values('date').annotate(
                    total=Sum('reward_amount')
                ).order_by('date')
                
                return [
                    {'date': item['date'].isoformat(), 'value': float(item['total'] or 0)}
                    for item in daily_data
                ]
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting daily trends: {str(e)}")
            return []
    
    def _get_weekly_comparison(self, from_date, metric):
        """Get week-over-week comparison"""
        try:
            # Current week
            current_week_end = timezone.now()
            current_week_start = current_week_end - timedelta(days=7)
            
            # Previous week
            previous_week_end = current_week_start
            previous_week_start = previous_week_end - timedelta(days=7)
            
            def get_week_data(start, end):
                if metric == 'completions':
                    return UserTaskCompletion.objects.filter(
                        completed_at__gte=start,
                        completed_at__lt=end,
                        status='completed'
                    ).count()
                elif metric == 'revenue':
                    return UserTaskCompletion.objects.filter(
                        completed_at__gte=start,
                        completed_at__lt=end,
                        status='completed'
                    ).aggregate(total=Sum('reward_amount'))['total'] or 0
                return 0
            
            current = get_week_data(current_week_start, current_week_end)
            previous = get_week_data(previous_week_start, previous_week_end)
            
            return {
                'current_week': float(current),
                'previous_week': float(previous),
                'change': float(current - previous),
                'change_percentage': ((current - previous) / previous * 100) if previous > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting weekly comparison: {str(e)}")
            return {}
    
    def _calculate_growth_rates(self, from_date, metric):
        """Calculate growth rates"""
        try:
            # Calculate growth over different periods
            periods = {
                'daily': 1,
                'weekly': 7,
                'monthly': 30
            }
            
            growth_rates = {}
            
            for period_name, days in periods.items():
                period_end = timezone.now()
                period_start = period_end - timedelta(days=days)
                previous_start = period_start - timedelta(days=days)
                
                def get_period_total(start, end):
                    if metric == 'completions':
                        return UserTaskCompletion.objects.filter(
                            completed_at__gte=start,
                            completed_at__lt=end,
                            status='completed'
                        ).count()
                    elif metric == 'revenue':
                        return UserTaskCompletion.objects.filter(
                            completed_at__gte=start,
                            completed_at__lt=end,
                            status='completed'
                        ).aggregate(total=Sum('reward_amount'))['total'] or 0
                    return 0
                
                current = get_period_total(period_start, period_end)
                previous = get_period_total(previous_start, period_start)
                
                growth_rate = ((current - previous) / previous * 100) if previous > 0 else 0
                growth_rates[period_name] = growth_rate
            
            return growth_rates
            
        except Exception as e:
            logger.error(f"Error calculating growth rates: {str(e)}")
            return {}
    
    def _generate_predictions(self, metric, days):
        """Generate simple predictions"""
        try:
            # Get historical data for trend analysis
            historical_start = timezone.now() - timedelta(days=days*2)
            historical_end = timezone.now() - timedelta(days=days)
            
            if metric == 'completions':
                historical_data = UserTaskCompletion.objects.filter(
                    completed_at__gte=historical_start,
                    completed_at__lt=historical_end,
                    status='completed'
                ).annotate(
                    date=TruncDate('completed_at')
                ).values('date').annotate(
                    count=Count('id')
                ).order_by('date')
                
                # Simple linear trend prediction
                if len(historical_data) > 1:
                    counts = [item['count'] for item in historical_data]
                    avg_growth = sum(counts[i+1] - counts[i] for i in range(len(counts)-1)) / (len(counts)-1)
                    last_value = counts[-1]
                    
                    predictions = []
                    for i in range(days):
                        predicted_value = last_value + (avg_growth * (i + 1))
                        predictions.append(max(0, predicted_value))
                    
                    return predictions
            
            return []
            
        except Exception as e:
            logger.error(f"Error generating predictions: {str(e)}")
            return {}
    
    def _analyze_user_segments(self, from_date):
        """Analyze user segments"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            segments = {}
            
            # Segment by activity level
            total_users = User.objects.filter(date_joined__gte=from_date).count()
            active_users = UserTaskCompletion.objects.filter(
                completed_at__gte=from_date,
                status='completed'
            ).values('user_id').distinct().count()
            
            segments['activity_levels'] = {
                'highly_active': int(active_users * 0.2),  # Top 20%
                'moderately_active': int(active_users * 0.3),  # Next 30%
                'low_active': int(active_users * 0.5),  # Bottom 50%
                'inactive': total_users - active_users
            }
            
            # Segment by completion frequency
            completion_stats = UserTaskCompletion.objects.filter(
                completed_at__gte=from_date,
                status='completed'
            ).values('user_id').annotate(
                completion_count=Count('id')
            ).order_by('completion_count')
            
            if completion_stats.exists():
                counts = [item['completion_count'] for item in completion_stats]
                median_count = counts[len(counts)//2] if counts else 0
                
                segments['completion_frequency'] = {
                    'power_users': sum(1 for c in counts if c > median_count * 2),
                    'regular_users': sum(1 for c in counts if median_count <= c <= median_count * 2),
                    'casual_users': sum(1 for c in counts if c < median_count)
                }
            
            return segments
            
        except Exception as e:
            logger.error(f"Error analyzing user segments: {str(e)}")
            return {}
    
    def _analyze_retention(self, from_date):
        """Analyze user retention"""
        try:
            # Calculate day-over-day retention
            cohorts = {}
            
            # Get users who completed tasks on each day
            daily_users = UserTaskCompletion.objects.filter(
                completed_at__gte=from_date,
                status='completed'
            ).annotate(
                date=TruncDate('completed_at')
            ).values('date', 'user_id').distinct()
            
            # Group by date
            for date in set(item['date'] for item in daily_users):
                date_users = set(item['user_id'] for item in daily_users if item['date'] == date)
                cohorts[date.isoformat()] = len(date_users)
            
            # Calculate retention rates
            retention_data = {}
            dates = sorted(cohorts.keys())
            
            for i, date in enumerate(dates[:-1]):
                next_date = dates[i + 1]
                current_users = UserTaskCompletion.objects.filter(
                    completed_at__date=date,
                    status='completed'
                ).values('user_id').distinct().count()
                
                retained_users = UserTaskCompletion.objects.filter(
                    completed_at__date=next_date,
                    status='completed',
                    user_id__in=UserTaskCompletion.objects.filter(
                        completed_at__date=date,
                        status='completed'
                    ).values('user_id')
                ).values('user_id').distinct().count()
                
                retention_rate = (retained_users / current_users * 100) if current_users > 0 else 0
                retention_data[f"{date}_to_{next_date}"] = retention_rate
            
            return retention_data
            
        except Exception as e:
            logger.error(f"Error analyzing retention: {str(e)}")
            return {}
    
    def _analyze_engagement_patterns(self, from_date):
        """Analyze engagement patterns"""
        try:
            from django.db.models.functions import ExtractHour
            
            # Hourly activity patterns
            hourly_activity = UserTaskCompletion.objects.filter(
                completed_at__gte=from_date,
                status='completed'
            ).annotate(
                hour=ExtractHour('completed_at')
            ).values('hour').annotate(
                count=Count('id')
            ).order_by('hour')
            
            # Daily activity patterns
            from django.db.models.functions import ExtractWeekDay
            daily_activity = UserTaskCompletion.objects.filter(
                completed_at__gte=from_date,
                status='completed'
            ).annotate(
                day_of_week=ExtractWeekDay('completed_at')
            ).values('day_of_week').annotate(
                count=Count('id')
            ).order_by('day_of_week')
            
            return {
                'hourly_patterns': [
                    {'hour': item['hour'], 'completions': item['count']}
                    for item in hourly_activity
                ],
                'daily_patterns': [
                    {'day': item['day_of_week'], 'completions': item['count']}
                    for item in daily_activity
                ],
                'peak_hour': max(hourly_activity, key=lambda x: x['count'])['hour'] if hourly_activity else 0,
                'peak_day': max(daily_activity, key=lambda x: x['count'])['day'] if daily_activity else 0
            }
            
        except Exception as e:
            logger.error(f"Error analyzing engagement patterns: {str(e)}")
            return {}
    
    def _analyze_conversion_funnel(self, from_date):
        """Analyze conversion funnel"""
        try:
            # Define funnel stages
            funnel_stages = {
                'task_views': 0,      # Users who viewed tasks
                'task_starts': 0,     # Users who started tasks
                'task_completions': 0  # Users who completed tasks
            }
            
            # Count users at each stage
            funnel_stages['task_views'] = MasterTask.objects.filter(
                is_active=True
            ).count() * 10  # Estimate based on views
            
            funnel_stages['task_starts'] = UserTaskCompletion.objects.filter(
                started_at__gte=from_date,
                status='started'
            ).values('user_id').distinct().count()
            
            funnel_stages['task_completions'] = UserTaskCompletion.objects.filter(
                completed_at__gte=from_date,
                status='completed'
            ).values('user_id').distinct().count()
            
            # Calculate conversion rates
            conversion_rates = {}
            stages = ['task_views', 'task_starts', 'task_completions']
            
            for i in range(len(stages) - 1):
                current_stage = stages[i]
                next_stage = stages[i + 1]
                
                if funnel_stages[current_stage] > 0:
                    rate = (funnel_stages[next_stage] / funnel_stages[current_stage]) * 100
                    conversion_rates[f"{current_stage}_to_{next_stage}"] = rate
            
            return {
                'funnel_stages': funnel_stages,
                'conversion_rates': conversion_rates,
                'overall_conversion_rate': (
                    (funnel_stages['task_completions'] / funnel_stages['task_views'] * 100)
                    if funnel_stages['task_views'] > 0 else 0
                )
            }
            
        except Exception as e:
            logger.error(f"Error analyzing conversion funnel: {str(e)}")
            return {}
    
    def _analyze_cohorts(self, from_date):
        """Analyze user cohorts"""
        try:
            # Weekly cohorts
            cohorts = {}
            
            # Get users who joined in different weeks
            from django.db.models.functions import TruncWeek
            user_cohorts = User.objects.filter(
                date_joined__gte=from_date
            ).annotate(
                cohort_week=TruncWeek('date_joined')
            ).values('cohort_week').annotate(
                user_count=Count('id')
            ).order_by('cohort_week')
            
            for cohort in user_cohorts:
                cohort_week = cohort['cohort_week']
                cohort_users = User.objects.filter(
                    date_joined__gte=cohort_week,
                    date_joined__lt=cohort_week + timedelta(days=7)
                )
                
                # Calculate retention for this cohort over time
                retention_data = []
                for week_offset in range(8):  # Track for 8 weeks
                    week_start = cohort_week + timedelta(weeks=week_offset)
                    week_end = week_start + timedelta(days=7)
                    
                    retained_users = UserTaskCompletion.objects.filter(
                        user__in=cohort_users,
                        completed_at__gte=week_start,
                        completed_at__lt=week_end,
                        status='completed'
                    ).values('user_id').distinct().count()
                    
                    retention_rate = (retained_users / cohort['user_count'] * 100) if cohort['user_count'] > 0 else 0
                    retention_data.append(retention_rate)
                
                cohorts[cohort_week.isoformat()] = {
                    'initial_users': cohort['user_count'],
                    'retention_rates': retention_data
                }
            
            return cohorts
            
        except Exception as e:
            logger.error(f"Error analyzing cohorts: {str(e)}")
            return {}
    
    def _calculate_user_growth_rate(self, from_date):
        """Calculate user growth rate"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Get user counts for different periods
            current_users = User.objects.filter(date_joined__gte=from_date).count()
            previous_users = User.objects.filter(
                date_joined__gte=from_date - timedelta(days=30),
                date_joined__lt=from_date
            ).count()
            
            growth_rate = ((current_users - previous_users) / previous_users * 100) if previous_users > 0 else 0
            return growth_rate
            
        except Exception as e:
            logger.error(f"Error calculating user growth rate: {str(e)}")
            return 0.0
    
    def _calculate_completion_streak(self, user):
        """Calculate user's completion streak"""
        try:
            # Get recent completions
            completions = UserTaskCompletion.objects.filter(
                user=user,
                status='completed'
            ).order_by('-completed_at')[:30]  # Last 30 completions
            
            if not completions:
                return 0
            
            # Calculate consecutive days
            streak = 0
            current_date = timezone.now().date()
            
            for completion in completions:
                completion_date = completion.completed_at.date()
                
                if completion_date == current_date:
                    streak += 1
                    current_date -= timedelta(days=1)
                elif completion_date == current_date + timedelta(days=1):
                    # Found gap in streak
                    break
                else:
                    # Too far back
                    break
            
            return streak
            
        except Exception as e:
            logger.error(f"Error calculating completion streak: {str(e)}")
            return 0
    
    def _calculate_avg_completion_time(self, completions):
        """Calculate average completion time"""
        try:
            total_time = timedelta()
            count = 0
            
            for completion in completions:
                if completion.started_at and completion.completed_at:
                    completion_time = completion.completed_at - completion.started_at
                    total_time += completion_time
                    count += 1
            
            if count > 0:
                avg_time = total_time / count
                return avg_time.total_seconds() / 60  # Return in minutes
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating average completion time: {str(e)}")
            return 0.0
    
    def _get_top_tasks(self, completions, limit):
        """Get top performing tasks"""
        return list(
            completions.values('task__name', 'task__task_id')
            .annotate(count=Count('id'), total_reward=Sum('reward_amount'))
            .order_by('-count')[:limit]
        )
    
    def _calculate_dau(self, from_date):
        """Calculate Daily Active Users"""
        try:
            return UserTaskCompletion.objects.filter(
                completed_at__gte=from_date,
                completed_at__lt=from_date + timedelta(days=1),
                status='completed'
            ).values('user_id').distinct().count()
        except Exception as e:
            logger.error(f"Error calculating DAU: {str(e)}")
            return 0
    
    def _calculate_mau(self, from_date):
        """Calculate Monthly Active Users"""
        try:
            month_start = from_date.replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            return UserTaskCompletion.objects.filter(
                completed_at__gte=month_start,
                completed_at__lt=month_end,
                status='completed'
            ).values('user_id').distinct().count()
        except Exception as e:
            logger.error(f"Error calculating MAU: {str(e)}")
            return 0
    
    def _calculate_engagement_rate(self, from_date):
        """Calculate engagement rate"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            total_users = User.objects.filter(date_joined__gte=from_date).count()
            active_users = UserTaskCompletion.objects.filter(
                completed_at__gte=from_date,
                status='completed'
            ).values('user_id').distinct().count()
            
            return (active_users / total_users * 100) if total_users > 0 else 0.0
        except Exception as e:
            logger.error(f"Error calculating engagement rate: {str(e)}")
            return 0.0
    
    def _calculate_retention_rate(self, from_date):
        """Calculate retention rate"""
        try:
            # Simple retention: users who completed tasks today vs yesterday
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            
            today_users = set(UserTaskCompletion.objects.filter(
                completed_at__date=today,
                status='completed'
            ).values_list('user_id', flat=True))
            
            yesterday_users = set(UserTaskCompletion.objects.filter(
                completed_at__date=yesterday,
                status='completed'
            ).values_list('user_id', flat=True))
            
            if not yesterday_users:
                return 0.0
            
            retained_users = len(today_users & yesterday_users)
            return (retained_users / len(yesterday_users) * 100)
        except Exception as e:
            logger.error(f"Error calculating retention rate: {str(e)}")
            return 0.0
    
    def _calculate_avg_session_duration(self, completions):
        """Calculate average session duration"""
        try:
            total_duration = timedelta()
            count = 0
            
            for completion in completions:
                if completion.started_at and completion.completed_at:
                    duration = completion.completed_at - completion.started_at
                    total_duration += duration
                    count += 1
            
            if count > 0:
                return total_duration.total_seconds() / 60  # Return in minutes
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating average session duration: {str(e)}")
            return 0.0
    
    def _get_api_response_time(self):
        """Get API response time metrics"""
        try:
            # This would typically come from monitoring/middleware
            # For now, return a reasonable estimate
            return 0.15  # 150ms average
        except Exception as e:
            logger.error(f"Error getting API response time: {str(e)}")
            return 0.0
    
    def _get_error_rate(self, from_date):
        """Get error rate"""
        try:
            # This would typically come from logging/metrics
            # For now, estimate based on successful vs failed completions
            total_completions = UserTaskCompletion.objects.filter(
                completed_at__gte=from_date
            ).count()
            
            failed_completions = UserTaskCompletion.objects.filter(
                completed_at__gte=from_date,
                status='failed'
            ).count()
            
            if total_completions > 0:
                return (failed_completions / total_completions * 100)
            return 0.0
        except Exception as e:
            logger.error(f"Error getting error rate: {str(e)}")
            return 0.0
    
    def _get_throughput(self, from_date):
        """Get system throughput"""
        try:
            # Calculate requests per second based on task completions
            hours = (timezone.now() - from_date).total_seconds() / 3600
            if hours > 0:
                completions = UserTaskCompletion.objects.filter(
                    completed_at__gte=from_date,
                    status='completed'
                ).count()
                return completions / (hours * 3600)  # per second
            return 0.0
        except Exception as e:
            logger.error(f"Error getting throughput: {str(e)}")
            return 0.0
    
    def _get_cache_hit_rate(self):
        """Get cache hit rate"""
        try:
            # This would typically come from cache metrics
            # For now, return a reasonable estimate
            return 85.0  # 85% cache hit rate
        except Exception as e:
            logger.error(f"Error getting cache hit rate: {str(e)}")
            return 0.0
    
    def _get_db_query_time(self):
        """Get database query time"""
        try:
            # This would typically come from database monitoring
            # For now, return a reasonable estimate
            return 0.025  # 25ms average query time
        except Exception as e:
            logger.error(f"Error getting DB query time: {str(e)}")
            return 0.0


# ============ TASK COMPLETION VIEWSET ============

class TaskCompletionViewSet(BulletproofViewSet):
    """
    ViewSet for task completions with bulletproof error handling
    """
    
    queryset = UserTaskCompletion.objects.all()
    serializer_class = TaskCompletionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    
    def get_queryset(self):
        """Filter by user with optimization"""
        queryset = super().get_queryset()
        
        # Regular users can only see their own completions
        user = self.request.user
        if not user.is_staff:
            queryset = queryset.filter(user=user)
        
        # Filter by status
        status = safe_get_request_data(self.request, 'status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by date range
        from_date = safe_get_request_data(self.request, 'from_date')
        to_date = safe_get_request_data(self.request, 'to_date')
        
        from_date_obj = safe_date_from_iso(from_date)
        to_date_obj = safe_date_from_iso(to_date)
        
        if from_date_obj:
            queryset = queryset.filter(started_at__gte=from_date_obj)
        
        if to_date_obj:
            queryset = queryset.filter(started_at__lte=to_date_obj)
        
        # Always prefetch task for efficiency
        queryset = queryset.select_related('task', 'user')
        
        return queryset.order_by('-started_at')
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create task completion with transaction safety"""
        try:
            # Check if user already has this task started
            task_id = request.data.get('task')
            
            if not task_id:
                return Response(
                    ErrorResponseSerializer({
                        'error': 'Task ID is required',
                        'error_code': 'MISSING_TASK_ID'
                    }).data,
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            existing = UserTaskCompletion.objects.filter(
                user=request.user,
                task_id=task_id,
                status='started'
            ).first()
            
            if existing:
                serializer = self.get_serializer(existing)
                return Response({
                    'status': 'already_started',
                    'data': serializer.data,
                    'message': 'Task already in progress'
                }, status=status.HTTP_200_OK)
            
            # Check availability with cooldown
            try:
                task = MasterTask.objects.get(id=task_id)
            except MasterTask.DoesNotExist:
                return Response(
                    ErrorResponseSerializer({
                        'error': 'Task not found',
                        'error_code': 'TASK_NOT_FOUND'
                    }).data,
                    status=status.HTTP_404_NOT_FOUND
                )
            
            is_available, reason = task.is_available_with_cooldown(
                user_level=getattr(request.user, 'level', 1),
                user_id=request.user.id
            )
            
            if not is_available:
                return Response(
                    ErrorResponseSerializer({
                        'error': 'Task not available',
                        'error_code': 'TASK_UNAVAILABLE',
                        'details': reason
                    }).data,
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # ── Inventory cap (slot availability) ──────────────────────
            from api.tasks.api.adapters.inventory import check_slot_available, consume_slot
            if not check_slot_available(task_id):
                return Response(
                    ErrorResponseSerializer({
                        'error': 'Task slots exhausted',
                        'error_code': 'INVENTORY_EXHAUSTED',
                        'details': 'This task has reached its completion cap.'
                    }).data,
                    status=status.HTTP_400_BAD_REQUEST
                )

            # ── Task lock: এক কাজের জন্য একটাই মালিক ─────────────────
            from .models import TaskLock
            from django.db import transaction as db_transaction
            with db_transaction.atomic():
                existing_lock = (
                    TaskLock.objects
                    .select_for_update(nowait=True)
                    .filter(
                        task_id=task_id,
                        lock_type=TaskLock.LockType.EXCLUSIVE,
                        released_at__isnull=True,
                        expires_at__gt=timezone.now(),
                    )
                    .exclude(user=request.user)
                    .first()
                )
                if existing_lock:
                    return Response(
                        ErrorResponseSerializer({
                            'error': 'Task is locked by another user',
                            'error_code': 'TASK_LOCKED',
                            'details': {'expires_in_seconds': existing_lock.time_remaining_seconds}
                        }).data,
                        status=status.HTTP_409_CONFLICT
                    )

                # Create completion inside atomic block
                completion = UserTaskCompletion.objects.create(
                    user=request.user,
                    task_id=task_id,
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request),
                    status='started'
                )
                TaskLock.objects.update_or_create(
                    task_id=task_id, user=request.user, released_at=None,
                    defaults={
                        'lock_type': TaskLock.LockType.EXCLUSIVE,
                        'expires_at': timezone.now() + timezone.timedelta(hours=24),
                    }
                )
            consume_slot(task_id)
            
            serializer = self.get_serializer(completion)
            
            # Update Redis for tracking
            self._update_redis_tracking(request.user.id, task_id)
            
            return Response({
                'status': 'started',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating task completion: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to start task',
                    'details': str(e) if settings.DEBUG else None
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _update_redis_tracking(self, user_id: int, task_id: int) -> None:
        """Update Redis for tracking - with proper error handling"""
        try:
            redis_client = get_redis_connection_safe()
            if not redis_client:
                return
            
            # Track started tasks
            today = timezone.now().strftime('%Y%m%d')
            redis_key = f"user_starts:{user_id}:{today}"
            redis_client.sadd(redis_key, task_id)
            redis_client.expire(redis_key, 86400)  # 24 hours
            
        except Exception as e:
            logger.debug(f"Redis tracking error: {str(e)}")
    
    @action(detail=True, methods=['post'], url_path='complete')
    @transaction.atomic
    def mark_complete(self, request, pk=None):
        """Mark task as completed with rewards"""
        try:
            completion = self.get_object()
            
            # Verify ownership
            if completion.user != request.user and not request.user.is_staff:
                return Response(
                    ErrorResponseSerializer({
                        'error': 'Permission denied',
                        'error_code': 'PERMISSION_DENIED'
                    }).data,
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if already completed
            if completion.status == 'completed':
                return Response({
                    'status': 'already_completed',
                    'message': 'Task already completed',
                    'data': self.get_serializer(completion).data
                })
            
            # Get proof data
            proof = request.data.get('proof', {})
            
            # Complete with rewards
            result = completion.complete_with_rewards(
                proof=proof,
                metadata=request.data.get('metadata', {})
            )
            
            if result['success']:
                return Response({
                    'status': 'completed',
                    'data': self.get_serializer(completion).data,
                    'rewards': result.get('rewards'),
                    'breakdown': result.get('breakdown')
                })
            else:
                return Response({
                    'status': 'completed_with_warning',
                    'data': self.get_serializer(completion).data,
                    'warning': result.get('warning')
                })
            
        except Exception as e:
            logger.error(f"Error completing task: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to complete task',
                    'details': str(e) if settings.DEBUG else None
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'], url_path='history')
    def user_history(self, request):
        """Get task completion history for current user"""
        try:
            base_qs = self.get_queryset().filter(user=request.user)
            completions = list(base_qs[:100])
            serializer = self.get_serializer(completions, many=True)
            total_points = 0
            for c in completions:
                try:
                    if c.rewards_awarded and isinstance(c.rewards_awarded, dict):
                        total_points += c.rewards_awarded.get("points", 0)
                except Exception:
                    pass
            try:
                streak = self._calculate_streak(request.user.id)
            except Exception:
                streak = 0
            stats = {
                "total_completed": base_qs.filter(status="completed").count(),
                "total_points": total_points,
                "total_tasks": base_qs.count(),
                "completed_today": base_qs.filter(status="completed", completed_at__date=timezone.now().date()).count(),
                "streak_days": streak
            }
            
            return Response({
                'status': 'success',
                'data': serializer.data,
                'stats': stats
            })
            
        except Exception as e:
            logger.error(f"Error fetching user history: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to fetch history'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _calculate_streak(self, user_id: int) -> int:
        """Calculate user's current streak with Redis caching"""
        try:
            # Try Redis first
            redis_client = get_redis_connection_safe()
            if redis_client:
                streak_key = f"user_streak:{user_id}"
                cached_streak = redis_client.get(streak_key)
                
                if cached_streak:
                    return int(cached_streak)
            
            # Calculate from database
            today = timezone.now().date()
            streak = 0
            current_date = today
            
            while True:
                has_completion = UserTaskCompletion.objects.filter(
                    user_id=user_id,
                    status='completed',
                    completed_at__date=current_date
                ).exists()
                
                if has_completion:
                    streak += 1
                    current_date -= timedelta(days=1)
                else:
                    break
            
            # Cache in Redis if available
            if redis_client and streak > 0:
                redis_client.setex(streak_key, 3600, streak)
            
            return streak
            
        except Exception as e:
            logger.error(f"Error calculating streak: {str(e)}")
            return 0
    
    @action(detail=True, methods=['post'], url_path='verify', permission_classes=[IsAdminUser])
    @transaction.atomic
    def verify_completion(self, request, pk=None):
        """Verify task completion (Admin only)"""
        try:
            completion = self.get_object()
            
            if completion.status == 'verified':
                return Response({
                    'status': 'already_verified',
                    'message': 'Task already verified'
                })
            
            completion.verify(verified_by=request.user.username)
            
            return Response({
                'status': 'verified',
                'data': self.get_serializer(completion).data
            })
            
        except Exception as e:
            logger.error(f"Error verifying completion: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to verify task'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ============ ADMIN VIEWSETS ============

class AdminTaskViewSet(MasterTaskViewSet):
    """
    Admin viewset for task management with full CRUD
    """
    permission_classes = [IsAdminUser]
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create new task"""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            task = serializer.save()
            
            logger.info(f"Admin {request.user} created task {task.task_id}")
            
            return Response({
                'status': 'success',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating task: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to create task'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update task"""
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            task = serializer.save()
            
            logger.info(f"Admin {request.user} updated task {task.task_id}")
            
            return Response({
                'status': 'success',
                'data': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error updating task: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to update task'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """Delete task"""
        try:
            instance = self.get_object()
            task_id = instance.task_id
            
            instance.delete()
            
            logger.info(f"Admin {request.user} deleted task {task_id}")
            
            return Response({
                'status': 'success',
                'message': f'Task {task_id} deleted successfully'
            }, status=status.HTTP_204_NO_CONTENT)
            
        except Exception as e:
            logger.error(f"Error deleting task: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to delete task'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'], url_path='bulk-operation')
    @transaction.atomic
    def bulk_operation(self, request):
        """Bulk operations on tasks"""
        try:
            serializer = BulkTaskOperationSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            result = serializer.save()
            
            logger.info(f"Admin {request.user} performed bulk {result['operation']} on {result['affected_count']} tasks")
            
            return Response({
                'status': 'success',
                'data': result
            })
            
        except Exception as e:
            logger.error(f"Error in bulk operation: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to perform bulk operation'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ============ STATISTICS VIEW ============

class TaskStatisticsView(APIView):
    """
    View for task statistics
    """
    permission_classes = [AllowAny]
    
    @task_view_circuit
    def get(self, request):
        """Get task statistics"""
        try:
            # Try cache first
            cache_key = "global_task_statistics"
            cached_data = cache.get(cache_key)
            
            if cached_data:
                return Response({
                    'status': 'success',
                    'data': cached_data,
                    'cached': True
                })
            
            # Get statistics
            stats = TaskStatisticsSerializer.get_statistics()
            
            # Cache for 1 hour
            cache.set(cache_key, stats, timeout=3600)
            
            return Response({
                'status': 'success',
                'data': stats
            })
            
        except Exception as e:
            logger.error(f"Error getting statistics: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Failed to get statistics'
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ============ HEALTH CHECK VIEW ============

class HealthCheckView(APIView):
    """
    Health check endpoint
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Check system health"""
        try:
            # Check database
            db_status = self._check_database()
            
            # Check cache
            cache_status = self._check_cache()
            
            # Check Redis if configured
            redis_status = self._check_redis()
            
            status_code = status.HTTP_200_OK
            if not all([db_status['healthy'], cache_status['healthy']]):
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            
            # Get stats safely
            try:
                tasks_count = MasterTask.objects.filter(is_active=True).count()
            except:
                tasks_count = 0
            
            try:
                completions_today = UserTaskCompletion.objects.filter(
                    started_at__date=timezone.now().date()
                ).count()
            except:
                completions_today = 0
            
            return Response({
                'status': 'healthy' if status_code == 200 else 'unhealthy',
                'timestamp': timezone.now().isoformat(),
                'services': {
                    'database': db_status,
                    'cache': cache_status,
                    'redis': redis_status
                },
                'stats': {
                    'tasks_count': tasks_count,
                    'completions_today': completions_today
                }
            }, status=status_code)
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return Response(
                ErrorResponseSerializer({
                    'error': 'Health check failed',
                    'details': str(e) if settings.DEBUG else None
                }).data,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _check_database(self) -> Dict[str, Any]:
        """Check database connection"""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return {'healthy': True, 'message': 'Connected'}
        except Exception as e:
            return {'healthy': False, 'message': str(e)}
    
    def _check_cache(self) -> Dict[str, Any]:
        """Check cache connection"""
        try:
            cache.set('health_check', 'ok', 5)
            value = cache.get('health_check')
            return {'healthy': value == 'ok', 'message': 'Connected' if value == 'ok' else 'Failed'}
        except Exception as e:
            return {'healthy': False, 'message': str(e)}
    
    def _check_redis(self) -> Dict[str, Any]:
        """Check Redis connection"""
        try:
            redis_client = get_redis_connection_safe()
            if redis_client:
                redis_client.ping()
                return {'healthy': True, 'message': 'Connected'}
            return {'healthy': True, 'message': 'Not configured'}
        except Exception as e:
            return {'healthy': False, 'message': str(e)}


# ============ ERROR HANDLING MIDDLEWARE ============

class ErrorHandlingMiddleware:
    """
    Middleware for global error handling
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
            
            if settings.DEBUG:
                raise
            
            return JsonResponse(
                ErrorResponseSerializer({
                    'error': 'Internal server error',
                    'error_code': 'INTERNAL_ERROR',
                    'message': 'An unexpected error occurred. Please try again later.'
                }).data,
                status=500
            )

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response as TR
from django.db.models import Sum, Count
from django.utils import timezone
import datetime

@api_view(['GET'])
@permission_classes([IsAdminUser])
def task_dashboard_stats(request):
    try:
        from .models import MasterTask, UserTaskCompletion
        return Response({
            'active_tasks':      MasterTask.objects.filter(is_active=True).count(),
            'total_tasks':       MasterTask.objects.count(),
            'total_completions': UserTaskCompletion.objects.count(),
            'completed': UserTaskCompletion.objects.filter(status='completed').count(),
            'verified': UserTaskCompletion.objects.filter(status='verified').count(),
            'failed': UserTaskCompletion.objects.filter(status='failed').count(),
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_activate(request):
    from .models import MasterTask
    ids = request.data.get('task_ids', [])
    MasterTask.objects.filter(id__in=ids).update(is_active=True)
    return Response({'detail': f'{len(ids)} tasks activated'})

@api_view(['POST'])
@permission_classes([IsAdminUser])
def bulk_deactivate(request):
    from .models import MasterTask
    ids = request.data.get('task_ids', [])
    MasterTask.objects.filter(id__in=ids).update(is_active=False)
    return Response({'detail': f'{len(ids)} tasks deactivated'})

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_ledger_list(request):
    return Response({'results': [], 'count': 0})

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_profit_summary(request):
    days = int(request.query_params.get('days', 30))
    return Response({'days': days, 'total_profit': 0, 'total_transactions': 0})

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_daily_profit(request):
    days = int(request.query_params.get('days', 30))
    data = []
    for i in range(days):
        d = timezone.now().date() - datetime.timedelta(days=i)
        data.append({'date': str(d), 'profit': 0})
    return Response({'results': data})

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_profit_by_source(request):
    return Response({'results': []})

# ── Missing view stubs (referenced in urls.py) ────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard_view(request):
    """User dashboard: earnings summary, active tasks, recent completions."""
    from .models import UserTaskCompletion, MasterTask
    from django.db.models import Sum, Count
    user = request.user
    qs = UserTaskCompletion.objects.filter(user=user)
    total_earned = qs.filter(status='completed').aggregate(s=Sum('reward_amount'))['s'] or 0
    return Response({
        'total_earned': str(total_earned),
        'completions': qs.filter(status='completed').count(),
        'pending': qs.filter(status='pending').count(),
        'active_tasks': MasterTask.objects.filter(is_active=True).count(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile_view(request):
    """User profile with earning stats and account info."""
    user = request.user
    return Response({
        'id': user.pk,
        'username': user.username,
        'email': user.email,
        'date_joined': user.date_joined,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_achievements_view(request):
    """User achievements, badges, and gamification data."""
    return Response({'achievements': [], 'badges': [], 'level': 1, 'xp': 0})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_analytics_view(request):
    """Admin analytics overview."""
    from .models import UserTaskCompletion, MasterTask
    from django.db.models import Sum, Count
    period_days = int(request.query_params.get('days', 30))
    cutoff = timezone.now() - datetime.timedelta(days=period_days)
    total_payouts = (
        UserTaskCompletion.objects
        .filter(status='completed', completed_at__gte=cutoff)
        .aggregate(s=Sum('reward_amount'))['s'] or 0
    )
    return Response({
        'period_days': period_days,
        'total_payouts': str(total_payouts),
        'completions': UserTaskCompletion.objects.filter(completed_at__gte=cutoff).count(),
        'active_tasks': MasterTask.objects.filter(is_active=True).count(),
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_performance_view(request):
    """Admin performance metrics."""
    return Response({'tasks_per_hour': 0, 'conversion_rate': 0.0, 'fraud_rate': 0.0})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_revenue_view(request):
    """Admin revenue breakdown by platform/source."""
    return Response({'results': []})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_users_view(request):
    """Admin user list with earning stats."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    count = User.objects.count()
    return Response({'count': count, 'results': []})

# ── Platform postback views ───────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def ogads_postback_view(request):
    """OGAds S2S postback endpoint. Queues ogads_process_postback Celery task."""
    from api.external.ogads import verify_postback_ip
    from api.tasks.tasks_platform_extensions import ogads_process_postback
    client_ip = request.META.get('REMOTE_ADDR', '')
    if not verify_postback_ip(client_ip):
        return Response({'error': 'Unauthorized IP'}, status=403)
    data = request.GET.dict() if request.method == 'GET' else request.data
    ogads_process_postback.delay(dict(data))
    return Response('1')  # OGAds expects plain "1" on success


@api_view(['GET', 'POST'])
def adgate_postback_view(request):
    """AdGate Media S2S postback endpoint."""
    from api.tasks.tasks_platform_extensions import adgate_process_postback
    data = request.GET.dict() if request.method == 'GET' else request.data
    adgate_process_postback.delay(dict(data))
    return Response('OK')


@api_view(['GET', 'POST'])
def offertoro_postback_view(request):
    """OfferToro S2S postback endpoint."""
    from api.tasks.tasks_platform_extensions import offertoro_process_postback
    data = request.GET.dict() if request.method == 'GET' else request.data
    offertoro_process_postback.delay(dict(data))
    return Response('1')


@api_view(['GET', 'POST'])
def monlix_postback_view(request):
    """Monlix S2S postback endpoint (cpa/cpi/survey/cpe)."""
    from api.tasks.tasks_platform_extensions import monlix_process_postback
    data = request.GET.dict() if request.method == 'GET' else request.data
    monlix_process_postback.delay(dict(data))
    return Response('1')

# ── Internet Connectivity + Aging Task Endpoints ──────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def connectivity_status_view(request):
    """
    GET /api/connectivity/
    Returns current internet connectivity status (cached — no live probe).
    """
    from api.tasks.internet_check_tasks import get_connectivity_status, are_outbound_tasks_paused
    status_data = get_connectivity_status()
    return Response({
        'online':               status_data.get('online', True),
        'latency_ms':           status_data.get('latency_ms'),
        'passed':               status_data.get('passed'),
        'probed_at':            status_data.get('probed_at'),
        'outbound_paused':      are_outbound_tasks_paused(),
        'details':              status_data.get('details', []),
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def connectivity_probe_now_view(request):
    """
    POST /api/connectivity/probe/
    Forces a live connectivity probe (admin only).
    """
    from api.tasks.internet_check_tasks import _multi_probe_internet
    probe = _multi_probe_internet()
    return Response({'probe': probe})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def aging_tasks_report_view(request):
    """
    GET /api/aging-tasks/
    Returns cached aging task report (started/pending beyond thresholds).
    """
    from api.tasks.internet_check_tasks import aging_report
    report = aging_report()
    return Response(report)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def aging_tasks_recover_view(request):
    """
    POST /api/aging-tasks/recover/
    Triggers auto-recovery (or dry_run=true for preview).
    Body: { dry_run: bool, threshold_minutes: int }
    """
    from api.tasks.internet_check_tasks import auto_recover_aging_tasks
    dry_run            = request.data.get('dry_run', False)
    threshold_minutes  = int(request.data.get('threshold_minutes', 60))
    result = auto_recover_aging_tasks.delay(threshold_minutes=threshold_minutes,
                                            dry_run=dry_run)
    return Response({'task_id': str(result.id), 'dry_run': dry_run,
                     'threshold_minutes': threshold_minutes})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def stale_locks_report_view(request):
    """
    GET /api/stale-locks/
    Returns current stale lock count and details.
    """
    from api.tasks.models import TaskLock
    from django.db.models import Q
    threshold = int(request.query_params.get('threshold_minutes', 60))
    from django.utils import timezone as tz
    from datetime import timedelta
    cutoff = tz.now() - timedelta(minutes=threshold)
    stale_qs = TaskLock.objects.filter(
        released_at__isnull=True
    ).filter(
        Q(expires_at__lt=tz.now()) | Q(acquired_at__lt=cutoff)
    ).select_related('task', 'user')[:50]

    return Response({
        'count': stale_qs.count() if False else TaskLock.objects.filter(
            released_at__isnull=True
        ).filter(Q(expires_at__lt=tz.now()) | Q(acquired_at__lt=cutoff)).count(),
        'threshold_minutes': threshold,
        'locks': [
            {'lock_id': str(l.id), 'task': str(l.task),
             'user_id': l.user_id,
             'held_minutes': int((tz.now() - l.acquired_at).total_seconds() / 60)}
            for l in stale_qs
        ]
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def force_release_lock_view(request):
    """
    POST /api/stale-locks/force-release/
    Body: { lock_id: str, reason: str }
    """
    from api.tasks.internet_check_tasks import force_release_stuck_lock
    lock_id = request.data.get('lock_id')
    reason  = request.data.get('reason', 'admin_dashboard')
    if not lock_id:
        return Response({'error': 'lock_id required'}, status=400)
    result = force_release_stuck_lock.delay(lock_id=lock_id, reason=reason)
    return Response({'task_id': str(result.id), 'lock_id': lock_id})
