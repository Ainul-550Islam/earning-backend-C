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
                except:
                    pass
            
            # Try form data
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

# class BulletproofViewSet(viewsets.GenericViewSet):
class BulletproofViewSet(viewsets.ModelViewSet):
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
            
            # Create completion
            completion = UserTaskCompletion.objects.create(
                user=request.user,
                task_id=task_id,
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request),
                status='started'
            )
            
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
    from .models import MasterTask, UserTaskCompletion
    return Response({
        'active_tasks':      MasterTask.objects.filter(is_active=True).count(),
        'total_tasks':       MasterTask.objects.count(),
        'total_completions': UserTaskCompletion.objects.count(),
        'pending_completions': UserTaskCompletion.objects.filter(status='pending').count(),
        'approved_completions': UserTaskCompletion.objects.filter(status='approved').count(),
    })

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
