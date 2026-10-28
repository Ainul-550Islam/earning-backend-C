# api/cms/mixins.py
"""CMS Mixins - reusable mixins for Django views and models."""
import logging
from typing import Any, Dict, Optional, Type
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


# ── DRF ViewSet Mixins (Original) ─────────────────────────────────────

class CMSCacheMixin:
    """Cache GET responses per endpoint + query params."""
    cache_ttl = 300
    cache_key_prefix = ''

    def get_cache_key(self, request):
        prefix = self.cache_key_prefix or self.__class__.__name__
        params = request.query_params.urlencode()
        user_id = request.user.id if request.user.is_authenticated else 'anon'
        return f"cms:view:{prefix}:{user_id}:{hash(params)}"

    def list(self, request, *args, **kwargs):
        key = self.get_cache_key(request)
        cached = cache.get(key)
        if cached:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache.set(key, response.data, self.cache_ttl)
        return response


class CMSBulkCreateMixin:
    """Add bulk create endpoint to ViewSet."""
    def bulk_create(self, request, *args, **kwargs):
        items = request.data if isinstance(request.data, list) else request.data.get('items', [])
        if not items:
            return Response({'error': 'items required'}, status=400)
        serializer = self.get_serializer(data=items, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CMSSoftDeleteMixin:
    """Soft delete — sets is_active=False instead of deleting."""
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if hasattr(instance, 'is_active'):
            instance.is_active = False
            instance.save(update_fields=['is_active'])
            return Response({'deleted': True, 'id': instance.pk})
        return super().destroy(request, *args, **kwargs)


# ── Survey Mixins ─────────────────────────────────────────────

class SurveyAccessMixin:
    """Mixin to control survey access based on user permissions."""
    
    def get_queryset(self):
        """Filter queryset based on user permissions and survey status."""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Non-staff users only see active, public surveys
        if not user.is_staff:
            queryset = queryset.filter(
                status='active',
                is_public=True
            ).exclude(
                id__in=user.survey_completions.filter(
                    status='completed'
                ).values_list('survey_id', flat=True)
            )
        
        return queryset.select_related('category').prefetch_related('questions')


class SurveyValidationMixin:
    """Mixin to validate survey responses."""
    
    def validate_survey_responses(self, survey, responses):
        """Validate survey responses."""
        from .logic import validate_survey_responses
        survey_data = {
            'required_questions_count': survey.questions.filter(required=True).count()
        }
        
        return validate_survey_responses(responses, survey_data)
    
    def perform_create(self, serializer):
        """Validate survey responses before creating completion."""
        if hasattr(serializer, 'validated_data') and 'responses' in serializer.validated_data:
            survey = serializer.validated_data.get('survey')
            responses = serializer.validated_data.get('responses')
            
            validation_result = self.validate_survey_responses(survey, responses)
            
            if not validation_result['valid']:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({
                    'responses': validation_result['errors']
                })
        
        super().perform_create(serializer)


# ── Reward Mixins ─────────────────────────────────────────────

class RewardCalculationMixin:
    """Mixin to handle reward calculations."""
    
    def calculate_reward(self, survey, quality_score, user):
        """Calculate reward for survey completion."""
        from .logic import calculate_survey_reward
        
        survey_data = {
            'min_reward': survey.min_reward,
            'max_reward': survey.max_reward,
            'difficulty': survey.difficulty
        }
        
        user_data = {
            'survey_completions_count': user.survey_completions.filter(status='completed').count()
        }
        
        return calculate_survey_reward(survey_data, quality_score, user_data)
    
    def perform_create(self, serializer):
        """Calculate and create reward transaction."""
        instance = super().perform_create(serializer)
        
        if hasattr(instance, 'survey') and hasattr(instance, 'quality_score'):
            reward_data = self.calculate_reward(
                instance.survey, 
                instance.quality_score, 
                instance.user
            )
            
            # Create reward transaction
            from .models_new.survey_rewards import RewardTransaction
            RewardTransaction.objects.create(
                user=instance.user,
                amount=reward_data['final_reward'],
                transaction_type='earned',
                description=f'Survey completion: {instance.survey.title}',
                data={
                    'survey_id': str(instance.survey.uuid),
                    'completion_id': str(instance.uuid),
                    'quality_score': instance.quality_score
                }
            )
        
        return instance


class PayoutValidationMixin:
    """Mixin to validate payout requests."""
    
    def validate_payout_request(self, user, amount):
        """Validate payout request."""
        from .models_new.survey_rewards import RewardTransaction
        
        # Check minimum amount
        if amount < 1.0:
            return False, "Minimum payout amount is $1.00"
        
        # Check available balance
        earned_amount = RewardTransaction.objects.filter(
            user=user,
            transaction_type='earned',
            status='completed'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        paid_amount = RewardTransaction.objects.filter(
            user=user,
            transaction_type='payout',
            status='completed'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        available_balance = earned_amount - paid_amount
        
        if amount > available_balance:
            return False, f"Insufficient balance. Available: ${available_balance:.2f}"
        
        return True, "Valid"
    
    def create(self, request, *args, **kwargs):
        """Validate payout before creating."""
        amount = float(request.data.get('amount', 0))
        
        is_valid, message = self.validate_payout_request(request.user, amount)
        
        if not is_valid:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({
                'amount': message
            })
        
        return super().create(request, *args, **kwargs)


# ── User Profile Mixins ─────────────────────────────────────

class ProfileCompletenessMixin:
    """Mixin to handle profile completeness calculations."""
    
    def calculate_profile_completeness(self, profile):
        """Calculate profile completeness percentage."""
        from .logic import calculate_profile_completeness
        
        profile_data = {
            'first_name': profile.first_name,
            'last_name': profile.last_name,
            'email': profile.email,
            'phone_number': profile.phone_number,
            'date_of_birth': profile.date_of_birth,
            'address': profile.address
        }
        
        return calculate_profile_completeness(profile_data)
    
    def update_profile_completeness(self, profile):
        """Update profile completeness field."""
        completeness = self.calculate_profile_completeness(profile)
        profile.completeness_percentage = completeness
        profile.save(update_fields=['completeness_percentage'])
        return completeness
    
    def perform_update(self, serializer):
        """Update completeness after profile update."""
        instance = super().perform_update(serializer)
        self.update_profile_completeness(instance)
        return instance


class UserSegmentMixin:
    """Mixin to handle user segmentation."""
    
    def get_user_segments(self, user):
        """Get user segments based on profile and behavior."""
        from .logic import determine_user_segments
        
        user_data = {
            'profile': {
                'date_of_birth': getattr(user.profile, 'date_of_birth', None),
                'address': getattr(user.profile, 'address', None)
            },
            'completed_surveys_count': user.survey_completions.filter(status='completed').count(),
            'average_quality_score': user.survey_completions.filter(status='completed').aggregate(
                avg=models.Avg('quality_score')
            )['avg'] or 0.7,
            'days_since_last_activity': 0  # Would calculate from last completion
        }
        
        return determine_user_segments(user_data)
    
    def perform_update(self, serializer):
        """Update user segments after profile update."""
        instance = super().perform_update(serializer)
        
        # Update segments
        segments = self.get_user_segments(instance.user)
        
        from .models_new.user_profile import UserSegment
        UserSegment.objects.filter(user=instance.user).delete()
        
        for segment_name in segments:
            UserSegment.objects.create(
                user=instance.user,
                name=segment_name,
                segment_type='behavioral' if segment_name in ['active', 'inactive'] else 'demographic'
            )
        
        return instance


# ── Task Management Mixins ─────────────────────────────────────

class TaskExecutionMixin:
    """Mixin to handle task execution."""
    
    def execute_task(self, task):
        """Execute a task and track execution."""
        from .models_new.task_management import TaskExecution
        
        execution = TaskExecution.objects.create(
            schedule=task,
            status='running',
            worker_id='manual',
            started_at=timezone.now()
        )
        
        try:
            # Execute task logic here
            # This would integrate with actual task execution system
            result = self._run_task_logic(task)
            
            execution.status = 'success'
            execution.completed_at = timezone.now()
            execution.result_data = result
            execution.save(update_fields=['status', 'completed_at', 'result_data'])
            
            return execution
            
        except Exception as e:
            execution.status = 'failure'
            execution.error_message = str(e)
            execution.completed_at = timezone.now()
            execution.save(update_fields=['status', 'error_message', 'completed_at'])
            
            raise e
    
    def _run_task_logic(self, task):
        """Run the actual task logic."""
        # Placeholder for task execution logic
        return {'message': f'Task {task.task_name} executed successfully'}


class TaskRetryMixin:
    """Mixin to handle task retry logic."""
    
    def should_retry_task(self, task, execution):
        """Determine if a failed task should be retried."""
        from .logic import should_retry_task
        
        task_data = {
            'max_retries': task.max_retries
        }
        
        execution_data = {
            'retry_count': execution.retry_count,
            'error_message': execution.error_message
        }
        
        return should_retry_task(task_data, execution_data)
    
    def retry_task(self, task, execution):
        """Retry a failed task."""
        from .logic import calculate_retry_delay
        
        execution_data = {
            'retry_count': execution.retry_count
        }
        
        delay = calculate_retry_delay(execution_data)
        
        # Schedule retry
        # This would integrate with task scheduling system
        logger.info(f"Scheduling task {task.task_name} for retry in {delay} seconds")
        
        return delay


# ── Analytics Mixins ─────────────────────────────────────

class AnalyticsMixin:
    """Mixin to add analytics functionality."""
    
    def track_user_action(self, action: str, data: Dict[str, Any] = None):
        """Track user action for analytics."""
        user = getattr(self, 'request', {}).user if hasattr(self, 'request') else None
        
        # This would integrate with analytics service
        logger.info(f"[Analytics] Action: {action} by {user} - {data or {}}")
    
    def get_analytics_data(self, days: int = 30):
        """Get analytics data for specified period."""
        from .logic import calculate_survey_analytics, calculate_user_analytics, calculate_reward_analytics
        
        # Placeholder data - would fetch from database
        survey_data = {'total_completed': 100, 'total_started': 120, 'avg_quality': 0.75, 'total_rewards': 250.50}
        user_data = {'new_registrations': 15, 'active_users': 85, 'previous_active_users': 80}
        reward_data = {'total_earned': 500.75, 'total_paid': 350.25, 'pending_payouts': 25.00}
        
        return {
            'survey_analytics': calculate_survey_analytics(survey_data),
            'user_analytics': calculate_user_analytics(user_data),
            'reward_analytics': calculate_reward_analytics(reward_data)
        }
    
    def list(self, request, *args, **kwargs):
        """Track list view access."""
        self.track_user_action('list_view', {
            'model': self.queryset.model.__name__,
            'filters': dict(request.query_params)
        })
        return super().list(request, *args, **kwargs)


# ── API Response Mixins ─────────────────────────────────────

class APIResponseMixin:
    """Mixin to standardize API responses."""
    
    def success_response(self, data: Any = None, message: str = "Success", status_code: int = 200):
        """Return standardized success response."""
        response_data = {
            'success': True,
            'message': message,
            'timestamp': timezone.now().isoformat()
        }
        
        if data is not None:
            response_data['data'] = data
        
        return Response(response_data, status=status_code)
    
    def error_response(self, message: str, error_code: str = None, status_code: int = 400, details: Dict[str, Any] = None):
        """Return standardized error response."""
        response_data = {
            'success': False,
            'error': message,
            'timestamp': timezone.now().isoformat()
        }
        
        if error_code:
            response_data['error_code'] = error_code
        
        if details:
            response_data['details'] = details
        
        return Response(response_data, status=status_code)
    
    def validation_error_response(self, errors: Dict[str, list], message: str = "Validation failed"):
        """Return validation error response."""
        return self.error_response(
            message=message,
            error_code='validation_error',
            status_code=422,
            details={'field_errors': errors}
        )


# ── Permission Mixins ─────────────────────────────────────

class CMSPermissionMixin:
    """Mixin to handle CMS-specific permissions."""
    
    def check_permission(self, permission: str):
        """Check if user has specific permission."""
        return self.request.user.has_perm(permission)
    
    def check_object_permission(self, obj, permission: str):
        """Check if user has permission for specific object."""
        return self.request.user.has_perm(f"{obj._meta.app_label}.{permission}_{obj._meta.model_name}", obj)
    
    def get_queryset(self):
        """Filter queryset based on permissions."""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Non-staff users can only see their own data
        if not user.is_staff and hasattr(queryset.model, 'user'):
            queryset = queryset.filter(user=user)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        """Check permissions before listing."""
        if hasattr(self, 'permission_required'):
            if not self.check_permission(self.permission_required):
                return self.error_response(
                    message="Permission denied",
                    error_code="permission_denied",
                    status_code=403
                )
        
        return super().list(request, *args, **kwargs)


# Import required models for mixins
from django.db import models


class CMSAuditMixin:
    """Log all write operations to audit log."""
    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        self._log_action('create', request, response)
        return response

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        self._log_action('update', request, response)
        return response

    def destroy(self, request, *args, **kwargs):
        self._log_action('delete', request, None)
        return super().destroy(request, *args, **kwargs)

    def _log_action(self, action, request, response):
        try:
            try:
                from api.cms.INTEGRATION_SYSTEM.integ_audit_logs import AuditLogger
            except ImportError:
                pass
            AuditLogger.log(
                action=f"viewset_{action}",
                source=self.__class__.__name__,
                user=request.user,
                ip=request.META.get('REMOTE_ADDR', ''),
                success=True if response is None else response.status_code < 400,
            )
        except Exception:
            pass


class CMSStatsActionMixin:
    """Add a stats action to any ViewSet."""
    def stats(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        from django.db.models import Count
        total = queryset.count()
        return Response({'total': total})


class CMSSearchMixin:
    """Add full-text search to ViewSet list."""
    search_fields_config = []  # e.g. ['title', 'description']

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        q = self.request.query_params.get('q', '').strip()
        if q and self.search_fields_config:
            from django.db.models import Q
            query = Q()
            for field in self.search_fields_config:
                query |= Q(**{f"{field}__icontains": q})
            queryset = queryset.filter(query)
        return queryset


class CMSUserFilterMixin:
    """Filter queryset to current user's objects."""
    user_field = 'user'

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff:
            return qs
        return qs.filter(**{self.user_field: self.request.user})


class RewardOnActionMixin:
    """Award coins when a specific action is completed."""
    reward_action = 'create'
    reward_coins = 0
    reward_reason = 'Action completed'

    def perform_create(self, serializer):
        super().perform_create(serializer)
        if self.reward_coins > 0 and self.request.user.is_authenticated:
            try:
                from api.cms.services_new.CPALeadService import VirtualCurrencyService
                from decimal import Decimal
                VirtualCurrencyService.award_coins(
                    user=self.request.user,
                    amount=Decimal(str(self.reward_coins)),
                    reason=self.reward_reason,
                    tx_type='earn_bonus',
                )
            except Exception:
                pass
