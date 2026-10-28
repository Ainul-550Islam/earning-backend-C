from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/viewset.py
"""Main CMS ViewSet — unified entry point for core CMS resources."""
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg

logger = logging.getLogger(__name__)


# ── Survey ViewSets ─────────────────────────────────────────────

class SurveyViewSet(viewsets.ModelViewSet):
    """ViewSet for Survey model."""
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'difficulty', 'category']
    search_fields = ['title', 'description']
    
    def get_queryset(self):
        """Get surveys based on user permissions."""
        user = self.request.user
        queryset = Survey.objects.all()
        
        if not user.is_staff:
            # Non-staff users can only see active surveys
            queryset = queryset.filter(status='active', is_public=True)
        
        return queryset.select_related('category').prefetch_related('questions')
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start a survey for current user."""
        try:
            survey = self.get_object()
            user = request.user
            
            # Check if user can start this survey
            if not self._can_start_survey(user, survey):
                return Response(
                    {'error': 'Cannot start this survey'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create survey completion
            from .services_new.ProfileSurveyService import ProfileSurveyManager
            manager = ProfileSurveyManager()
            completion = manager.start_survey(user, str(survey.uuid))
            
            return Response({
                'message': 'Survey started successfully',
                'completion_id': str(completion.uuid),
                'survey_title': survey.title,
                'estimated_minutes': survey.estimated_minutes
            })
        except Exception as e:
            logger.error(f"Error starting survey: {e}")
            return Response(
                {'error': 'Failed to start survey'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit survey responses."""
        try:
            survey = self.get_object()
            user = request.user
            responses = request.data.get('responses', [])
            
            # Validate responses
            if not responses:
                return Response(
                    {'error': 'No responses provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Submit survey
            from .services_new.ProfileSurveyService import ProfileSurveyManager
            manager = ProfileSurveyManager()
            completion = manager.submit_survey(user, str(survey.uuid), responses)
            
            return Response({
                'message': 'Survey submitted successfully',
                'completion_id': str(completion.uuid),
                'quality_score': completion.quality_score,
                'reward_earned': completion.total_reward_earned
            })
        except Exception as e:
            logger.error(f"Error submitting survey: {e}")
            return Response(
                {'error': 'Failed to submit survey'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def available(self, request):
        """Get available surveys for current user."""
        try:
            user = request.user
            limit = int(request.query_params.get('limit', 20))
            
            from .services_new.ProfileSurveyService import ProfileSurveyManager
            manager = ProfileSurveyManager()
            surveys = manager.get_available_surveys(user)[:limit]
            
            # Serialize surveys
            survey_data = []
            for survey in surveys:
                survey_data.append({
                    'id': str(survey.uuid),
                    'title': survey.title,
                    'description': survey.description,
                    'difficulty': survey.difficulty,
                    'estimated_minutes': survey.estimated_minutes,
                    'min_reward': float(survey.min_reward),
                    'max_reward': float(survey.max_reward),
                    'category': survey.category.name if survey.category else None
                })
            
            return Response({'surveys': survey_data})
        except Exception as e:
            logger.error(f"Error getting available surveys: {e}")
            return Response(
                {'error': 'Failed to get available surveys'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _can_start_survey(self, user, survey):
        """Check if user can start a survey."""
        # Check if user has already completed this survey
        completed = SurveyCompletion.objects.filter(
            user=user, survey=survey, status='completed'
        ).exists()
        
        if completed:
            return False
        
        # Check if user has an ongoing survey
        ongoing = SurveyCompletion.objects.filter(
            user=user, survey=survey, status='in_progress'
        ).exists()
        
        if ongoing:
            return False
        
        return True


class SurveyCompletionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for SurveyCompletion model."""
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'quality_score']
    
    def get_queryset(self):
        """Get user's survey completions."""
        user = self.request.user
        queryset = SurveyCompletion.objects.filter(user=user)
        
        if not user.is_staff:
            # Non-staff users can only see their own completions
            queryset = queryset.filter(user=user)
        
        return queryset.select_related('survey', 'user')


# ── Reward ViewSets ─────────────────────────────────────────────

class RewardTransactionViewSet(viewsets.ModelViewSet):
    """ViewSet for RewardTransaction model."""
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'transaction_type']
    search_fields = ['description']
    
    def get_queryset(self):
        """Get user's reward transactions."""
        user = self.request.user
        queryset = RewardTransaction.objects.all()
        
        if not user.is_staff:
            # Non-staff users can only see their own transactions
            queryset = queryset.filter(user=user)
        
        return queryset.select_related('user', 'reward_pool')
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get user's reward summary."""
        try:
            user = request.user
            days = int(request.query_params.get('days', 30))
            
            from .services_new.SurveyRewardService import SurveyRewardService
            service = SurveyRewardService()
            summary = service.get_user_reward_summary(user.id, days)
            
            return Response(summary)
        except Exception as e:
            logger.error(f"Error getting reward summary: {e}")
            return Response(
                {'error': 'Failed to get reward summary'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RewardPoolViewSet(viewsets.ModelViewSet):
    """ViewSet for RewardPool model."""
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'pool_type']
    
    def get_queryset(self):
        """Get reward pools based on user permissions."""
        user = self.request.user
        queryset = RewardPool.objects.all()
        
        if not user.is_staff:
            # Non-staff users can only see active pools
            queryset = queryset.filter(status='active')
        
        return queryset.select_related('created_by')
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get status of all reward pools."""
        try:
            from .services_new.SurveyRewardService import SurveyRewardService
            service = SurveyRewardService()
            pool_status = service.get_pool_status()
            
            return Response({'pools': pool_status})
        except Exception as e:
            logger.error(f"Error getting pool status: {e}")
            return Response(
                {'error': 'Failed to get pool status'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ── Task Management ViewSets ─────────────────────────────────────

class TaskScheduleViewSet(viewsets.ModelViewSet):
    """ViewSet for TaskSchedule model."""
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'task_type']
    search_fields = ['task_name', 'description']
    
    def get_queryset(self):
        """Get task schedules based on user permissions."""
        user = self.request.user
        queryset = TaskSchedule.objects.all()
        
        if not user.is_staff:
            # Non-staff users can only see active tasks
            queryset = queryset.filter(status='active')
        
        return queryset.select_related('created_by')
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """Execute a task immediately."""
        try:
            task = self.get_object()
            user = request.user
            
            # Check permissions
            if not user.is_staff:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Execute task
            from .services_new.TaskManagementService import TaskManagementService
            service = TaskManagementService()
            execution = service.execute_task(str(task.uuid))
            
            return Response({
                'message': 'Task execution started',
                'execution_id': str(execution.uuid),
                'task_name': task.task_name,
                'status': execution.status
            })
        except Exception as e:
            logger.error(f"Error executing task: {e}")
            return Response(
                {'error': 'Failed to execute task'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TaskExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for TaskExecution model."""
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'worker_id']
    
    def get_queryset(self):
        """Get task executions based on user permissions."""
        user = self.request.user
        queryset = TaskExecution.objects.all()
        
        if not user.is_staff:
            # Non-staff users can only see their own task executions
            queryset = queryset.filter(worker_id=str(user.id))
        
        return queryset.select_related('schedule', 'task')


# ── User Profile ViewSets ─────────────────────────────────────────

class UserProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for UserProfile model."""
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['completeness_percentage']
    
    def get_queryset(self):
        """Get user profiles based on permissions."""
        user = self.request.user
        queryset = UserProfile.objects.all()
        
        if not user.is_staff:
            # Non-staff users can only see their own profile
            queryset = queryset.filter(user=user)
        
        return queryset.select_related('user')
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's profile."""
        try:
            user = request.user
            
            from .services_new.UserProfileService import UserProfileService
            service = UserProfileService()
            profile = service.get_or_create_profile(user)
            
            # Serialize profile
            profile_data = {
                'id': str(profile.uuid),
                'user_id': user.id,
                'first_name': profile.first_name,
                'last_name': profile.last_name,
                'email': profile.email,
                'phone_number': profile.phone_number,
                'date_of_birth': profile.date_of_birth,
                'address': profile.address,
                'completeness_percentage': profile.completeness_percentage,
                'participation_score': profile.participation_score,
                'created_at': profile.created_at,
                'updated_at': profile.updated_at
            }
            
            return Response(profile_data)
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return Response(
                {'error': 'Failed to get profile'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserSegmentViewSet(viewsets.ModelViewSet):
    """ViewSet for UserSegment model."""
    
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active', 'segment_type']
    search_fields = ['name', 'description']
    
    def get_queryset(self):
        """Get user segments based on permissions."""
        user = self.request.user
        queryset = UserSegment.objects.all()
        
        if not user.is_staff:
            # Non-staff users can only see active segments
            queryset = queryset.filter(is_active=True)
        
        return queryset.select_related('created_by').prefetch_related('users')


# ── Original CMS ViewSets ─────────────────────────────────────

class CMSPageViewSet(viewsets.ReadOnlyModelViewSet):
    """Public CMS page viewset with full filtering and search."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [AllowAny]
    search_fields = ['title', 'meta_title', 'slug']
    ordering_fields = ['created_at', 'title', 'updated_at']
    ordering = ['-created_at']

    def get_queryset(self):
        try:
            from api.cms.models_new.blog import BlogPost
            return BlogPost.objects.filter(status='published').select_related('author')
        except Exception:
            from django.contrib.auth import get_user_model
            return get_user_model().objects.none()

    @action(detail=False, methods=['get'])
    def featured(self, request):
        qs = self.get_queryset().filter(is_featured=True)[:6]
        from api.cms.serializers import BlogPostSerializer
        return Response(BlogPostSerializer(qs, many=True).data)


class CMSDashboardViewSet(viewsets.GenericViewSet):
    """
    CMS admin dashboard summary.
    GET /api/cms/dashboard/summary/ — stats overview
    GET /api/cms/dashboard/revenue/ — revenue data
    GET /api/cms/dashboard/users/   — user stats
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        from django.db.models import Sum, Count
        from api.cms.models_new.cpalead import ConversionLog, UserVirtualBalance
        from api.cms.models_new.withdrawal import WithdrawalRequest, UserProfile
        try:
            from api.cms.INTEGRATION_SYSTEM.integ_audit_logs import IntegrationAuditLog, AuditLogger
        except ImportError:
            pass
        from django.utils import timezone
        from datetime import timedelta

        today = timezone.now().date()
        week_ago = timezone.now() - timedelta(days=7)

        conversions = ConversionLog.objects.filter(status='approved').aggregate(
            total=Count('id'), total_usd=Sum('payout_usd')
        )
        withdrawals = WithdrawalRequest.objects.filter(status='paid').aggregate(
            total=Count('id'), total_usd=Sum('net_usd')
        )

        return Response({
            'total_conversions': conversions['total'] or 0,
            'total_revenue_usd': float(conversions['total_usd'] or 0),
            'total_withdrawals': withdrawals['total'] or 0,
            'total_withdrawn_usd': float(withdrawals['total_usd'] or 0),
            'total_users': UserProfile.objects.count(),
            'active_this_week': UserProfile.objects.filter(
                user__last_login__gte=week_ago
            ).count(),
            'audit_stats': AuditLogger.get_stats(days=7),
        })

    @action(detail=False, methods=['get'])
    def revenue(self, request):
        from api.cms.models_new.cpalead import ConversionLog
        from django.db.models import Sum, Count, TruncDate
        days = int(request.query_params.get('days', 30))
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)

        data = (ConversionLog.objects
                .filter(status='approved', created_at__gte=cutoff)
                .annotate(date=TruncDate('created_at'))
                .values('date')
                .annotate(conversions=Count('id'), revenue=Sum('payout_usd'))
                .order_by('date'))
        return Response(list(data))

    @action(detail=False, methods=['get'])
    def users(self, request):
        from api.cms.models_new.withdrawal import UserProfile
        from django.db.models import Count
        by_level = list(
            UserProfile.objects.values('level')
            .annotate(count=Count('id'))
            .order_by('level')
        )
        by_kyc = list(
            UserProfile.objects.values('kyc_status')
            .annotate(count=Count('id'))
        )
        return Response({
            'total': UserProfile.objects.count(),
            'by_level': by_level,
            'by_kyc': by_kyc,
            'suspended': UserProfile.objects.filter(is_suspended=True).count(),
        })
