# =============================================================================
# auto_mod/endpoint.py
# =============================================================================

"""
API endpoints for auto moderation system.
Provides RESTful API endpoints and GraphQL integration.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.request import Request
import json

from .models import (
    SuspiciousSubmission, ModerationDecision, ModerationAppeal,
    ModerationQueue, TaskBot, AutoApprovalRule
)
from .serializers import (
    SuspiciousSubmissionSerializer, ModerationDecisionSerializer,
    ModerationAppealSerializer, ModerationQueueSerializer,
    TaskBotSerializer, AutoApprovalRuleSerializer
)
from .services import ModerationService, ScannerService, RuleEngineService
from .logic import moderation_logic, queue_logic, appeal_logic
from .exceptions import ModerationError, ValidationError
from .permissions import IsModeratorOrReadOnly

logger = logging.getLogger(__name__)


class BaseAPIView(View):
    """Base API view with common functionality."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def get_user_from_request(self, request) -> Optional[Any]:
        """Get user from request."""
        return getattr(request, 'user', None)
    
    def get_client_ip(self, request) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def success_response(self, data: Any = None, message: str = "Success") -> JsonResponse:
        """Create success response."""
        response_data = {
            'success': True,
            'message': message,
            'data': data,
            'timestamp': timezone.now().isoformat(),
        }
        return JsonResponse(response_data, status=200)
    
    def error_response(self, message: str, errors: List[str] = None, 
                      status_code: int = 400) -> JsonResponse:
        """Create error response."""
        response_data = {
            'success': False,
            'message': message,
            'errors': errors or [],
            'timestamp': timezone.now().isoformat(),
        }
        return JsonResponse(response_data, status=status_code)
    
    def validate_request_data(self, request, required_fields: List[str]) -> Dict[str, Any]:
        """Validate request data."""
        try:
            if request.method == 'GET':
                data = request.GET.dict()
            else:
                data = json.loads(request.body.decode('utf-8'))
            
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
            
            return data
            
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON data")
        except Exception as exc:
            raise ValidationError(f"Validation error: {exc}")


@method_decorator(csrf_exempt, name='dispatch')
class SubmissionEndpoint(BaseAPIView):
    """Endpoint for submission operations."""
    
    @require_http_methods(["GET", "POST"])
    def dispatch(self, request, *args, **kwargs):
        """Handle HTTP methods."""
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        """Get submissions."""
        try:
            user = self.get_user_from_request(request)
            if not user or not user.is_authenticated:
                return self.error_response("Authentication required", status_code=401)
            
            # Get query parameters
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 20))
            status_filter = request.GET.get('status')
            type_filter = request.GET.get('submission_type')
            
            # Build queryset
            queryset = SuspiciousSubmission.objects.all()
            
            # Apply filters
            if not user.is_staff:
                queryset = queryset.filter(user=user)
            
            if status_filter:
                queryset = queryset.filter(status=status_filter)
            
            if type_filter:
                queryset = queryset.filter(submission_type=type_filter)
            
            # Apply pagination
            offset = (page - 1) * page_size
            submissions = queryset[offset:offset + page_size]
            
            # Serialize data
            serializer = SuspiciousSubmissionSerializer(submissions, many=True)
            
            return self.success_response({
                'submissions': serializer.data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': queryset.count(),
                    'pages': (queryset.count() + page_size - 1) // page_size,
                }
            })
            
        except Exception as exc:
            self.logger.error(f"Get submissions failed: {exc}")
            return self.error_response(str(exc))
    
    def post(self, request):
        """Create submission."""
        try:
            user = self.get_user_from_request(request)
            if not user or not user.is_authenticated:
                return self.error_response("Authentication required", status_code=401)
            
            # Validate request data
            required_fields = ['submission_type', 'content']
            data = self.validate_request_data(request, required_fields)
            
            # Create submission
            submission_data = {
                'user': user,
                'submission_type': data['submission_type'],
                'text_content': data.get('content', ''),
                'metadata': data.get('metadata', {}),
            }
            
            submission = SuspiciousSubmission.objects.create(**submission_data)
            
            # Auto-process submission
            try:
                moderation_service = ModerationService()
                decision = moderation_service.process_submission(submission)
                
                response_data = {
                    'submission': SuspiciousSubmissionSerializer(submission).data,
                    'decision': ModerationDecisionSerializer(decision).data if decision else None,
                }
                
            except Exception as exc:
                self.logger.warning(f"Auto-processing failed: {exc}")
                response_data = {
                    'submission': SuspiciousSubmissionSerializer(submission).data,
                    'decision': None,
                }
            
            return self.success_response(response_data, "Submission created successfully")
            
        except ValidationError as exc:
            return self.error_response(str(exc))
        except Exception as exc:
            self.logger.error(f"Create submission failed: {exc}")
            return self.error_response(str(exc))


@method_decorator(csrf_exempt, name='dispatch')
class DecisionEndpoint(BaseAPIView):
    """Endpoint for decision operations."""
    
    @require_http_methods(["GET", "POST"])
    def dispatch(self, request, *args, **kwargs):
        """Handle HTTP methods."""
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        """Get decisions."""
        try:
            user = self.get_user_from_request(request)
            if not user or not user.is_authenticated:
                return self.error_response("Authentication required", status_code=401)
            
            if not user.is_staff:
                return self.error_response("Moderator access required", status_code=403)
            
            # Get query parameters
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 20))
            decision_type = request.GET.get('decision_type')
            automated = request.GET.get('is_automated')
            
            # Build queryset
            queryset = ModerationDecision.objects.all()
            
            # Apply filters
            if decision_type:
                queryset = queryset.filter(decision_type=decision_type)
            
            if automated is not None:
                queryset = queryset.filter(is_automated=automated.lower() == 'true')
            
            # Apply pagination
            offset = (page - 1) * page_size
            decisions = queryset[offset:offset + page_size]
            
            # Serialize data
            serializer = ModerationDecisionSerializer(decisions, many=True)
            
            return self.success_response({
                'decisions': serializer.data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': queryset.count(),
                    'pages': (queryset.count() + page_size - 1) // page_size,
                }
            })
            
        except Exception as exc:
            self.logger.error(f"Get decisions failed: {exc}")
            return self.error_response(str(exc))
    
    def post(self, request):
        """Create decision."""
        try:
            user = self.get_user_from_request(request)
            if not user or not user.is_authenticated:
                return self.error_response("Authentication required", status_code=401)
            
            if not user.is_staff:
                return self.error_response("Moderator access required", status_code=403)
            
            # Validate request data
            required_fields = ['submission_id', 'decision_type']
            data = self.validate_request_data(request, required_fields)
            
            # Get submission
            try:
                submission = SuspiciousSubmission.objects.get(id=data['submission_id'])
            except SuspiciousSubmission.DoesNotExist:
                return self.error_response("Submission not found", status_code=404)
            
            # Create decision
            moderation_service = ModerationService()
            decision = moderation_service.make_decision(
                submission=submission,
                decision_type=data['decision_type'],
                confidence=data.get('confidence'),
                reason=data.get('reason', ''),
                moderator=user
            )
            
            return self.success_response(
                ModerationDecisionSerializer(decision).data,
                "Decision created successfully"
            )
            
        except ValidationError as exc:
            return self.error_response(str(exc))
        except Exception as exc:
            self.logger.error(f"Create decision failed: {exc}")
            return self.error_response(str(exc))


@method_decorator(csrf_exempt, name='dispatch')
class AppealEndpoint(BaseAPIView):
    """Endpoint for appeal operations."""
    
    @require_http_methods(["GET", "POST"])
    def dispatch(self, request, *args, **kwargs):
        """Handle HTTP methods."""
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        """Get appeals."""
        try:
            user = self.get_user_from_request(request)
            if not user or not user.is_authenticated:
                return self.error_response("Authentication required", status_code=401)
            
            # Get query parameters
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 20))
            appeal_status = request.GET.get('status')
            
            # Build queryset
            queryset = ModerationAppeal.objects.all()
            
            # Apply filters
            if not user.is_staff:
                queryset = queryset.filter(user=user)
            
            if appeal_status:
                queryset = queryset.filter(status=appeal_status)
            
            # Apply pagination
            offset = (page - 1) * page_size
            appeals = queryset[offset:offset + page_size]
            
            # Serialize data
            serializer = ModerationAppealSerializer(appeals, many=True)
            
            return self.success_response({
                'appeals': serializer.data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': queryset.count(),
                    'pages': (queryset.count() + page_size - 1) // page_size,
                }
            })
            
        except Exception as exc:
            self.logger.error(f"Get appeals failed: {exc}")
            return self.error_response(str(exc))
    
    def post(self, request):
        """Create appeal."""
        try:
            user = self.get_user_from_request(request)
            if not user or not user.is_authenticated:
                return self.error_response("Authentication required", status_code=401)
            
            # Validate request data
            required_fields = ['original_decision_id', 'appeal_type', 'reason']
            data = self.validate_request_data(request, required_fields)
            
            # Get original decision
            try:
                from .models import ModerationDecision
                original_decision = ModerationDecision.objects.get(id=data['original_decision_id'])
            except ModerationDecision.DoesNotExist:
                return self.error_response("Original decision not found", status_code=404)
            
            # Check if user can appeal this decision
            if original_decision.submission.user != user and not user.is_staff:
                return self.error_response("Cannot appeal this decision", status_code=403)
            
            # Create appeal data
            appeal_data = {
                'original_decision_id': data['original_decision_id'],
                'user_id': str(user.id),
                'appeal_type': data['appeal_type'],
                'reason': data['reason'],
                'evidence': data.get('evidence', {}),
            }
            
            # Process appeal
            appeal_result = appeal_logic.process_appeal(appeal_data)
            
            return self.success_response(
                appeal_result,
                "Appeal created successfully"
            )
            
        except ValidationError as exc:
            return self.error_response(str(exc))
        except Exception as exc:
            self.logger.error(f"Create appeal failed: {exc}")
            return self.error_response(str(exc))


@method_decorator(csrf_exempt, name='dispatch')
class QueueEndpoint(BaseAPIView):
    """Endpoint for queue operations."""
    
    @require_http_methods(["GET", "POST"])
    def dispatch(self, request, *args, **kwargs):
        """Handle HTTP methods."""
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        """Get queue items."""
        try:
            user = self.get_user_from_request(request)
            if not user or not user.is_authenticated:
                return self.error_response("Authentication required", status_code=401)
            
            if not user.is_staff:
                return self.error_response("Moderator access required", status_code=403)
            
            # Get query parameters
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 20))
            queue_status = request.GET.get('status')
            priority = request.GET.get('priority')
            
            # Build queryset
            queryset = ModerationQueue.objects.all()
            
            # Apply filters
            if queue_status:
                queryset = queryset.filter(status=queue_status)
            
            if priority:
                queryset = queryset.filter(priority=priority)
            
            # Apply pagination
            offset = (page - 1) * page_size
            queue_items = queryset[offset:offset + page_size]
            
            # Serialize data
            serializer = ModerationQueueSerializer(queue_items, many=True)
            
            return self.success_response({
                'queue_items': serializer.data,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': queryset.count(),
                    'pages': (queryset.count() + page_size - 1) // page_size,
                }
            })
            
        except Exception as exc:
            self.logger.error(f"Get queue items failed: {exc}")
            return self.error_response(str(exc))
    
    def post(self, request):
        """Create queue item."""
        try:
            user = self.get_user_from_request(request)
            if not user or not user.is_authenticated:
                return self.error_response("Authentication required", status_code=401)
            
            if not user.is_staff:
                return self.error_response("Moderator access required", status_code=403)
            
            # Validate request data
            required_fields = ['submission_id']
            data = self.validate_request_data(request, required_fields)
            
            # Get submission
            try:
                submission = SuspiciousSubmission.objects.get(id=data['submission_id'])
            except SuspiciousSubmission.DoesNotExist:
                return self.error_response("Submission not found", status_code=404)
            
            # Create queue item
            queue_item = ModerationQueue.objects.create(
                submission=submission,
                priority=queue_logic.calculate_priority(submission),
                due_date=timezone.now() + timedelta(hours=24)
            )
            
            return self.success_response(
                ModerationQueueSerializer(queue_item).data,
                "Queue item created successfully"
            )
            
        except ValidationError as exc:
            return self.error_response(str(exc))
        except Exception as exc:
            self.logger.error(f"Create queue item failed: {exc}")
            return self.error_response(str(exc))


@method_decorator(csrf_exempt, name='dispatch')
class AnalyticsEndpoint(BaseAPIView):
    """Endpoint for analytics operations."""
    
    @require_http_methods(["GET"])
    def dispatch(self, request, *args, **kwargs):
        """Handle HTTP methods."""
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        """Get analytics data."""
        try:
            user = self.get_user_from_request(request)
            if not user or not user.is_authenticated:
                return self.error_response("Authentication required", status_code=401)
            
            if not user.is_staff:
                return self.error_response("Moderator access required", status_code=403)
            
            # Get query parameters
            days = int(request.GET.get('days', 30))
            metric_type = request.GET.get('metric', 'overview')
            
            # Calculate analytics
            from .analytics import analytics_engine
            
            if metric_type == 'overview':
                data = analytics_engine.get_dashboard_analytics(days=days)
            elif metric_type == 'submissions':
                data = analytics_engine.get_submission_analytics(days=days)
            elif metric_type == 'decisions':
                data = analytics_engine.get_decision_analytics(days=days)
            elif metric_type == 'appeals':
                data = analytics_engine.get_appeal_analytics(days=days)
            elif metric_type == 'queue':
                data = analytics_engine.get_queue_analytics()
            elif metric_type == 'bots':
                data = analytics_engine.get_bot_analytics()
            elif metric_type == 'content':
                data = analytics_engine.get_content_analytics(days=days)
            else:
                return self.error_response(f"Unknown metric type: {metric_type}")
            
            return self.success_response(data)
            
        except Exception as exc:
            self.logger.error(f"Get analytics failed: {exc}")
            return self.error_response(str(exc))


@method_decorator(csrf_exempt, name='dispatch')
class HealthEndpoint(BaseAPIView):
    """Endpoint for health checks."""
    
    @require_http_methods(["GET"])
    def dispatch(self, request, *args, **kwargs):
        """Handle HTTP methods."""
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        """Get system health."""
        try:
            from .monitoring import health_checker
            
            health_result = health_checker.check_system_health()
            
            return self.success_response(health_result)
            
        except Exception as exc:
            self.logger.error(f"Get health failed: {exc}")
            return self.error_response(str(exc))


# REST Framework API Views
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def submissions_api(request: Request) -> Response:
    """REST API endpoint for submissions."""
    try:
        if request.method == 'GET':
            return _get_submissions(request)
        elif request.method == 'POST':
            return _create_submission(request)
    except Exception as exc:
        logger.error(f"Submissions API failed: {exc}")
        return Response(
            {'error': str(exc)},
            status=status.HTTP_400_BAD_REQUEST
        )


def _get_submissions(request: Request) -> Response:
    """Get submissions."""
    user = request.user
    
    # Build queryset
    queryset = SuspiciousSubmission.objects.all()
    
    if not user.is_staff:
        queryset = queryset.filter(user=user)
    
    # Apply filters
    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    # Serialize
    serializer = SuspiciousSubmissionSerializer(queryset, many=True)
    
    return Response(serializer.data)


def _create_submission(request: Request) -> Response:
    """Create submission."""
    user = request.user
    
    # Validate data
    serializer = SuspiciousSubmissionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    # Create submission
    submission = serializer.save(user=user)
    
    # Process submission
    try:
        moderation_service = ModerationService()
        decision = moderation_service.process_submission(submission)
        
        return Response({
            'submission': SuspiciousSubmissionSerializer(submission).data,
            'decision': ModerationDecisionSerializer(decision).data if decision else None,
        }, status=status.HTTP_201_CREATED)
        
    except Exception as exc:
        logger.warning(f"Auto-processing failed: {exc}")
        return Response(
            SuspiciousSubmissionSerializer(submission).data,
            status=status.HTTP_201_CREATED
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsModeratorOrReadOnly])
def decisions_api(request: Request) -> Response:
    """REST API endpoint for decisions."""
    try:
        if request.method == 'GET':
            return _get_decisions(request)
        elif request.method == 'POST':
            return _create_decision(request)
    except Exception as exc:
        logger.error(f"Decisions API failed: {exc}")
        return Response(
            {'error': str(exc)},
            status=status.HTTP_400_BAD_REQUEST
        )


def _get_decisions(request: Request) -> Response:
    """Get decisions."""
    queryset = ModerationDecision.objects.all()
    
    # Apply filters
    decision_type = request.query_params.get('decision_type')
    if decision_type:
        queryset = queryset.filter(decision_type=decision_type)
    
    serializer = ModerationDecisionSerializer(queryset, many=True)
    return Response(serializer.data)


def _create_decision(request: Request) -> Response:
    """Create decision."""
    serializer = ModerationDecisionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    decision = serializer.save(decider=request.user)
    
    return Response(
        serializer.data,
        status=status.HTTP_201_CREATED
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analytics_api(request: Request) -> Response:
    """REST API endpoint for analytics."""
    try:
        days = int(request.query_params.get('days', 30))
        metric_type = request.query_params.get('metric', 'overview')
        
        from .analytics import analytics_engine
        
        if metric_type == 'overview':
            data = analytics_engine.get_dashboard_analytics(days=days)
        else:
            return Response(
                {'error': f'Unknown metric type: {metric_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(data)
        
    except Exception as exc:
        logger.error(f"Analytics API failed: {exc}")
        return Response(
            {'error': str(exc)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def health_api(request: Request) -> Response:
    """REST API endpoint for health checks."""
    try:
        from .monitoring import health_checker
        
        health_result = health_checker.check_system_health()
        
        return Response(health_result)
        
    except Exception as exc:
        logger.error(f"Health API failed: {exc}")
        return Response(
            {'error': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# GraphQL Integration (placeholder)
class GraphQLSchema:
    """GraphQL schema for auto moderation."""
    
    def __init__(self):
        self.schema = None  # Would be implemented with graphene
    
    def execute_query(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute GraphQL query."""
        # This would implement GraphQL query execution
        return {'data': {}, 'errors': []}


# Initialize logging
logger.info("Endpoints module initialized with REST API endpoints")
