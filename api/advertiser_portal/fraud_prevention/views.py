"""
Fraud Prevention Views

This module provides DRF ViewSets for fraud prevention operations with
enterprise-grade security, real-time detection, and comprehensive analysis
following industry standards from Stripe, OgAds, and leading fraud prevention systems.
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from django.db.models import Q, Count, Sum, Avg, F, Window
from django.db.models.functions import Coalesce, RowNumber
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..database_models.fraud_model import FraudDetection, RiskScore, FraudPattern, SecurityAlert
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *
from .services import (
    FraudDetectionService, RiskScoringService, PatternAnalysisService,
    SecurityMonitoringService, FraudPreventionService, FraudDetectionResult, RiskAssessment
)

User = get_user_model()


class FraudDetectionViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for fraud detection operations.
    
    Features:
    - Real-time fraud detection
    - Comprehensive analysis
    - Security validation
    - Performance optimization
    - Type-safe Python code
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def __init__(self, **kwargs):
        """Initialize with fraud detection service."""
        super().__init__(**kwargs)
        self.detection_service = FraudDetectionService()
    
    @action(detail=False, methods=['post'])
    def detect(self, request):
        """
        Detect fraud in real-time using multiple detection methods.
        
        Security measures:
        - Input validation and sanitization
        - Rate limiting
        - Request authentication
        - Audit logging
        
        Performance optimizations:
        - Parallel processing
        - Caching of results
        - Optimized database queries
        """
        try:
            # Security: Validate request
            FraudDetectionViewSet._validate_detection_request(request)
            
            # Get event data
            event_data = request.data
            context = {
                'ip_address': FraudDetectionViewSet._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'request_id': request.META.get('HTTP_X_REQUEST_ID', ''),
                'timestamp': timezone.now()
            }
            
            # Perform fraud detection
            detection_result = self.detection_service.detect_fraud(event_data, context)
            
            # Return comprehensive response
            response_data = {
                'request_id': context['request_id'],
                'detection_result': {
                    'is_fraudulent': detection_result.is_fraudulent,
                    'risk_score': detection_result.risk_score,
                    'confidence_level': detection_result.confidence_level,
                    'detected_patterns': detection_result.detected_patterns,
                    'risk_factors': detection_result.risk_factors,
                    'recommended_actions': detection_result.recommended_actions,
                    'detection_timestamp': detection_result.detection_timestamp.isoformat()
                },
                'security_context': {
                    'ip_address': context['ip_address'],
                    'user_agent': context['user_agent'],
                    'timestamp': context['timestamp'].isoformat()
                },
                'processing_time': timezone.now().timestamp() - context['timestamp'].timestamp()
            }
            
            # Security: Log detection request
            FraudDetectionViewSet._log_detection_request(request, detection_result)
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in fraud detection: {str(e)}")
            return Response({'error': 'Fraud detection failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """
        Get fraud detection history with filtering and pagination.
        
        Security measures:
        - User authorization validation
        - Data access control
        - Rate limiting
        
        Performance optimizations:
        - Optimized database queries
        - Pagination support
        - Caching of results
        """
        try:
            # Security: Validate user access
            user = request.user
            FraudDetectionViewSet._validate_user_access(user)
            
            # Get query parameters
            filters = {
                'user_id': request.query_params.get('user_id'),
                'date_from': request.query_params.get('date_from'),
                'date_to': request.query_params.get('date_to'),
                'risk_score_min': request.query_params.get('risk_score_min'),
                'risk_score_max': request.query_params.get('risk_score_max'),
                'is_fraudulent': request.query_params.get('is_fraudulent')
            }
            
            # Validate filters
            FraudDetectionViewSet._validate_history_filters(filters)
            
            # Get fraud detection history
            history_data = FraudDetectionViewSet._get_detection_history(user, filters)
            
            return Response(history_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting fraud detection history: {str(e)}")
            return Response({'error': 'Failed to get detection history'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Get comprehensive fraud detection statistics.
        
        Performance optimizations:
        - Optimized aggregate queries
        - Database indexing utilization
        - Caching of statistics
        """
        try:
            # Security: Validate user access
            user = request.user
            FraudDetectionViewSet._validate_user_access(user)
            
            # Performance: Check cache first
            cache_key = f'fraud_detection_stats_{user.id}'
            cached_stats = cache.get(cache_key)
            if cached_stats:
                return Response(cached_stats, status=status.HTTP_200_OK)
            
            # Calculate statistics
            stats_data = FraudDetectionViewSet._calculate_detection_statistics(user)
            
            # Performance: Cache results
            cache.set(cache_key, stats_data, timeout=600)  # 10 minutes cache
            
            return Response(stats_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting fraud detection statistics: {str(e)}")
            return Response({'error': 'Failed to get statistics'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_detection_request(request) -> None:
        """Validate fraud detection request with security checks."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['event_type']
        for field in required_fields:
            if field not in request.data:
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate event type
        valid_event_types = ['login', 'transaction', 'registration', 'campaign_create', 'creative_upload']
        event_type = request.data.get('event_type')
        if event_type not in valid_event_types:
            raise AdvertiserValidationError(f"Invalid event type: {event_type}")
    
    @staticmethod
    def _get_client_ip(request) -> str:
        """Get client IP address with security considerations."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        return ip or '0.0.0.0'
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            # Check if user has fraud detection permissions
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have fraud detection permissions")
    
    @staticmethod
    def _validate_history_filters(filters: Dict[str, Any]) -> None:
        """Validate history filters."""
        # Validate date formats
        for date_field in ['date_from', 'date_to']:
            date_value = filters.get(date_field)
            if date_value:
                try:
                    datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                except ValueError:
                    raise AdvertiserValidationError(f"Invalid {date_field} format")
        
        # Validate risk score ranges
        for score_field in ['risk_score_min', 'risk_score_max']:
            score_value = filters.get(score_field)
            if score_value:
                try:
                    score_float = float(score_value)
                    if not 0 <= score_float <= 1:
                        raise AdvertiserValidationError(f"{score_field} must be between 0 and 1")
                except ValueError:
                    raise AdvertiserValidationError(f"Invalid {score_field} format")
        
        # Validate boolean field
        if filters.get('is_fraudulent') not in [None, 'true', 'false']:
            raise AdvertiserValidationError("is_fraudulent must be 'true' or 'false'")
    
    @staticmethod
    def _get_detection_history(user: User, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get fraud detection history with optimized queries."""
        try:
            # Build query
            queryset = FraudDetection.objects.all()
            
            # Apply user filter
            if not user.is_superuser:
                queryset = queryset.filter(user_id=user.advertiser.id)
            
            # Apply filters
            if filters.get('user_id'):
                queryset = queryset.filter(user_id=UUID(filters['user_id']))
            
            if filters.get('date_from'):
                date_from = datetime.fromisoformat(filters['date_from'].replace('Z', '+00:00'))
                queryset = queryset.filter(detection_timestamp__gte=date_from)
            
            if filters.get('date_to'):
                date_to = datetime.fromisoformat(filters['date_to'].replace('Z', '+00:00'))
                queryset = queryset.filter(detection_timestamp__lte=date_to)
            
            if filters.get('risk_score_min'):
                queryset = queryset.filter(risk_score__gte=float(filters['risk_score_min']))
            
            if filters.get('risk_score_max'):
                queryset = queryset.filter(risk_score__lte=float(filters['risk_score_max']))
            
            if filters.get('is_fraudulent') is not None:
                is_fraudulent = filters['is_fraudulent'].lower() == 'true'
                queryset = queryset.filter(is_fraudulent=is_fraudulent)
            
            # Performance: Use optimized ordering and pagination
            queryset = queryset.order_by('-detection_timestamp')
            
            # Pagination
            page = int(filters.get('page', 1))
            page_size = min(int(filters.get('page_size', 20)), 100)  # Max 100 per page
            offset = (page - 1) * page_size
            
            # Get paginated results
            results = queryset[offset:offset + page_size]
            
            # Format results
            history_items = []
            for result in results:
                history_items.append({
                    'id': str(result.id),
                    'user_id': str(result.user_id) if result.user_id else None,
                    'session_id': result.session_id,
                    'event_type': result.event_type,
                    'risk_score': result.risk_score,
                    'is_fraudulent': result.is_fraudulent,
                    'confidence_level': result.confidence_level,
                    'detected_patterns': result.detected_patterns,
                    'risk_factors': result.risk_factors,
                    'recommended_actions': result.recommended_actions,
                    'detection_timestamp': result.detection_timestamp.isoformat()
                })
            
            return {
                'items': history_items,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': queryset.count(),
                    'total_pages': (queryset.count() + page_size - 1) // page_size
                },
                'filters_applied': filters
            }
            
        except Exception as e:
            logger.error(f"Error getting detection history: {str(e)}")
            return {
                'items': [],
                'pagination': {'page': 1, 'page_size': 20, 'total_count': 0, 'total_pages': 0},
                'filters_applied': filters,
                'error': 'Failed to retrieve history'
            }
    
    @staticmethod
    def _calculate_detection_statistics(user: User) -> Dict[str, Any]:
        """Calculate comprehensive fraud detection statistics."""
        try:
            # Build query
            queryset = FraudDetection.objects.all()
            
            # Apply user filter
            if not user.is_superuser:
                queryset = queryset.filter(user_id=user.advertiser.id)
            
            # Calculate statistics with optimized queries
            total_detections = queryset.count()
            fraudulent_detections = queryset.filter(is_fraudulent=True).count()
            
            # Risk score distribution
            risk_distribution = queryset.aggregate(
                avg_risk=Avg('risk_score'),
                max_risk=Coalesce(Max('risk_score'), 0.0),
                min_risk=Coalesce(Min('risk_score'), 0.0)
            )
            
            # Pattern frequency
            pattern_counts = {}
            for detection in queryset:
                for pattern in detection.detected_patterns:
                    pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
            
            # Recent activity (last 24 hours)
            recent_cutoff = timezone.now() - timedelta(hours=24)
            recent_detections = queryset.filter(detection_timestamp__gte=recent_cutoff).count()
            
            # Daily trends (last 7 days)
            daily_trends = []
            for i in range(7):
                date = timezone.now().date() - timedelta(days=i)
                day_count = queryset.filter(detection_timestamp__date=date).count()
                daily_trends.append({
                    'date': date.isoformat(),
                    'count': day_count
                })
            
            return {
                'summary': {
                    'total_detections': total_detections,
                    'fraudulent_detections': fraudulent_detections,
                    'fraud_rate': (fraudulent_detections / total_detections * 100) if total_detections > 0 else 0,
                    'recent_detections_24h': recent_detections
                },
                'risk_analysis': {
                    'average_risk_score': float(risk_distribution['avg_risk'] or 0),
                    'max_risk_score': float(risk_distribution['max_risk']),
                    'min_risk_score': float(risk_distribution['min_risk'])
                },
                'pattern_analysis': {
                    'most_common_patterns': sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:10],
                    'total_unique_patterns': len(pattern_counts)
                },
                'trends': {
                    'daily_trends': list(reversed(daily_trends)),
                    'generated_at': timezone.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating detection statistics: {str(e)}")
            return {
                'summary': {'total_detections': 0, 'fraudulent_detections': 0, 'fraud_rate': 0, 'recent_detections_24h': 0},
                'risk_analysis': {'average_risk_score': 0, 'max_risk_score': 0, 'min_risk_score': 0},
                'pattern_analysis': {'most_common_patterns': [], 'total_unique_patterns': 0},
                'trends': {'daily_trends': [], 'generated_at': timezone.now().isoformat()},
                'error': 'Failed to calculate statistics'
            }
    
    @staticmethod
    def _log_detection_request(request, detection_result: FraudDetectionResult) -> None:
        """Log fraud detection request for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_action(
                action='fraud_detection_request',
                object_type='FraudDetection',
                object_id=str(detection_result.user_id) if detection_result.user_id else None,
                user=request.user,
                description=f"Fraud detection request - Risk Score: {detection_result.risk_score}",
                metadata={
                    'ip_address': FraudDetectionViewSet._get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'is_fraudulent': detection_result.is_fraudulent,
                    'detected_patterns': detection_result.detected_patterns
                }
            )
        except Exception as e:
            logger.error(f"Error logging detection request: {str(e)}")


class RiskScoringViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for risk scoring operations.
    
    Features:
    - Comprehensive risk assessment
    - Multi-dimensional analysis
    - Real-time scoring
    - Historical tracking
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """Calculate comprehensive risk score for user."""
        try:
            # Security: Validate request
            RiskScoringViewSet._validate_risk_request(request)
            
            # Get user ID and context
            user_id = UUID(request.data.get('user_id'))
            context = request.data.get('context', {})
            
            # Add request context
            context.update({
                'ip_address': RiskScoringViewSet._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'timestamp': timezone.now()
            })
            
            # Calculate risk score
            risk_assessment = RiskScoringService.calculate_risk_score(user_id, context)
            
            # Return comprehensive response
            response_data = {
                'user_id': str(user_id),
                'risk_assessment': {
                    'overall_risk_score': risk_assessment.overall_risk_score,
                    'risk_level': risk_assessment.risk_level,
                    'risk_factors': risk_assessment.risk_factors,
                    'temporal_risk': risk_assessment.temporal_risk,
                    'behavioral_risk': risk_assessment.behavioral_risk,
                    'technical_risk': risk_assessment.technical_risk,
                    'contextual_risk': risk_assessment.contextual_risk,
                    'confidence_interval': risk_assessment.confidence_interval,
                    'assessment_timestamp': risk_assessment.assessment_timestamp.isoformat()
                },
                'recommendations': RiskScoringViewSet._generate_risk_recommendations(risk_assessment)
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error calculating risk score: {str(e)}")
            return Response({'error': 'Failed to calculate risk score'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get risk scoring history for user."""
        try:
            # Security: Validate request
            user = request.user
            RiskScoringViewSet._validate_user_access(user)
            
            # Get query parameters
            user_id = request.query_params.get('user_id')
            days = int(request.query_params.get('days', 30))
            
            # Validate parameters
            if user_id:
                user_id = UUID(user_id)
            
            # Get risk history
            history_data = RiskScoringViewSet._get_risk_history(user, user_id, days)
            
            return Response(history_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting risk history: {str(e)}")
            return Response({'error': 'Failed to get risk history'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_risk_request(request) -> None:
        """Validate risk scoring request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data.get('user_id'):
            raise AdvertiserValidationError("user_id is required")
        
        # Validate UUID format
        try:
            UUID(request.data.get('user_id'))
        except ValueError:
            raise AdvertiserValidationError("Invalid user_id format")
    
    @staticmethod
    def _get_client_ip(request) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        return ip or '0.0.0.0'
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have risk scoring permissions")
    
    @staticmethod
    def _get_risk_history(user: User, user_id: Optional[UUID], days: int) -> Dict[str, Any]:
        """Get risk scoring history."""
        try:
            # Build query
            queryset = RiskScore.objects.all()
            
            # Apply user filter
            if not user.is_superuser:
                queryset = queryset.filter(user_id=user.advertiser.id)
            
            # Apply specific user filter
            if user_id:
                queryset = queryset.filter(user_id=user_id)
            
            # Apply date filter
            cutoff_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(assessment_timestamp__gte=cutoff_date)
            
            # Get results
            results = queryset.order_by('-assessment_timestamp')
            
            # Format results
            history_items = []
            for result in results:
                history_items.append({
                    'id': str(result.id),
                    'user_id': str(result.user_id),
                    'overall_risk_score': result.overall_risk_score,
                    'risk_level': result.risk_level,
                    'temporal_risk': result.temporal_risk,
                    'behavioral_risk': result.behavioral_risk,
                    'technical_risk': result.technical_risk,
                    'contextual_risk': result.contextual_risk,
                    'confidence_interval': result.confidence_interval,
                    'assessment_timestamp': result.assessment_timestamp.isoformat()
                })
            
            return {
                'items': history_items,
                'summary': {
                    'total_assessments': len(history_items),
                    'average_risk_score': sum(item['overall_risk_score'] for item in history_items) / len(history_items) if history_items else 0,
                    'date_range_days': days
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting risk history: {str(e)}")
            return {
                'items': [],
                'summary': {'total_assessments': 0, 'average_risk_score': 0, 'date_range_days': days},
                'error': 'Failed to retrieve risk history'
            }
    
    @staticmethod
    def _generate_risk_recommendations(risk_assessment: RiskAssessment) -> List[str]:
        """Generate recommendations based on risk assessment."""
        recommendations = []
        
        if risk_assessment.risk_level == 'critical':
            recommendations.extend([
                'Immediate account suspension',
                'Manual review required',
                'Enhanced monitoring',
                'Contact user for verification'
            ])
        elif risk_assessment.risk_level == 'high':
            recommendations.extend([
                'Limit account functionality',
                'Require additional verification',
                'Increased monitoring',
                'Review recent activity'
            ])
        elif risk_assessment.risk_level == 'medium':
            recommendations.extend([
                'Enhanced monitoring',
                'Periodic review',
                'Consider additional verification'
            ])
        else:
            recommendations.extend([
                'Continue normal monitoring',
                'Periodic risk assessment'
            ])
        
        return recommendations


class PatternAnalysisViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for pattern analysis operations.
    
    Features:
    - Pattern recognition
    - Anomaly detection
    - Behavioral analysis
    - Trend identification
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def analyze(self, request):
        """Analyze patterns in user behavior."""
        try:
            # Security: Validate request
            PatternAnalysisViewSet._validate_analysis_request(request)
            
            # Get user ID and parameters
            user_id = UUID(request.data.get('user_id'))
            time_range_days = int(request.data.get('time_range_days', 30))
            time_range = timedelta(days=time_range_days)
            
            # Perform pattern analysis
            analysis_result = PatternAnalysisService.analyze_patterns(user_id, time_range)
            
            return Response(analysis_result, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error analyzing patterns: {str(e)}")
            return Response({'error': 'Failed to analyze patterns'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get pattern analysis dashboard data."""
        try:
            # Security: Validate request
            user = request.user
            PatternAnalysisViewSet._validate_user_access(user)
            
            # Get dashboard data
            dashboard_data = PatternAnalysisViewSet._get_dashboard_data(user)
            
            return Response(dashboard_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting pattern dashboard: {str(e)}")
            return Response({'error': 'Failed to get dashboard data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_analysis_request(request) -> None:
        """Validate pattern analysis request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data.get('user_id'):
            raise AdvertiserValidationError("user_id is required")
        
        # Validate UUID format
        try:
            UUID(request.data.get('user_id'))
        except ValueError:
            raise AdvertiserValidationError("Invalid user_id format")
        
        # Validate time range
        time_range_days = request.data.get('time_range_days', 30)
        try:
            days = int(time_range_days)
            if not 1 <= days <= 365:
                raise AdvertiserValidationError("time_range_days must be between 1 and 365")
        except ValueError:
            raise AdvertiserValidationError("Invalid time_range_days format")
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have pattern analysis permissions")
    
    @staticmethod
    def _get_dashboard_data(user: User) -> Dict[str, Any]:
        """Get pattern analysis dashboard data."""
        try:
            # Performance: Check cache first
            cache_key = f'pattern_dashboard_{user.id}'
            cached_dashboard = cache.get(cache_key)
            if cached_dashboard:
                return cached_dashboard
            
            # Get dashboard statistics
            total_users = Advertiser.objects.filter(is_deleted=False).count()
            high_risk_users = RiskScore.objects.filter(
                risk_level='high',
                assessment_timestamp__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            # Recent patterns
            recent_patterns = FraudPattern.objects.filter(
                is_active=True,
                created_at__gte=timezone.now() - timedelta(days=7)
            ).count()
            
            # Anomaly detection
            recent_anomalies = FraudDetection.objects.filter(
                is_fraudulent=True,
                detection_timestamp__gte=timezone.now() - timedelta(days=1)
            ).count()
            
            dashboard_data = {
                'summary': {
                    'total_users': total_users,
                    'high_risk_users': high_risk_users,
                    'recent_patterns': recent_patterns,
                    'recent_anomalies': recent_anomalies
                },
                'risk_distribution': PatternAnalysisViewSet._get_risk_distribution(),
                'pattern_trends': PatternAnalysisViewSet._get_pattern_trends(),
                'generated_at': timezone.now().isoformat()
            }
            
            # Performance: Cache results
            cache.set(cache_key, dashboard_data, timeout=300)  # 5 minutes cache
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error getting dashboard data: {str(e)}")
            return {
                'summary': {'total_users': 0, 'high_risk_users': 0, 'recent_patterns': 0, 'recent_anomalies': 0},
                'risk_distribution': {},
                'pattern_trends': [],
                'generated_at': timezone.now().isoformat(),
                'error': 'Failed to load dashboard data'
            }
    
    @staticmethod
    def _get_risk_distribution() -> Dict[str, int]:
        """Get risk level distribution."""
        try:
            distribution = RiskScore.objects.filter(
                assessment_timestamp__gte=timezone.now() - timedelta(days=30)
            ).values('risk_level').annotate(count=Count('id'))
            
            return {item['risk_level']: item['count'] for item in distribution}
        except Exception:
            return {}
    
    @staticmethod
    def _get_pattern_trends() -> List[Dict[str, Any]]:
        """Get pattern trends over time."""
        try:
            trends = []
            for i in range(7):
                date = timezone.now().date() - timedelta(days=i)
                day_patterns = FraudPattern.objects.filter(
                    created_at__date=date
                ).count()
                
                trends.append({
                    'date': date.isoformat(),
                    'patterns_created': day_patterns
                })
            
            return list(reversed(trends))
        except Exception:
            return []


class SecurityMonitoringViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for security monitoring operations.
    
    Features:
    - Security alert management
    - Real-time monitoring
    - Threat intelligence
    - Incident response
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_alert(self, request):
        """Create security alert."""
        try:
            # Security: Validate request
            SecurityMonitoringViewSet._validate_alert_request(request)
            
            # Create security alert
            alert = SecurityMonitoringService.create_security_alert(
                request.data, request.user
            )
            
            return Response({
                'alert_id': str(alert.id),
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'title': alert.title,
                'status': alert.status,
                'created_at': alert.created_at.isoformat()
            }, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating security alert: {str(e)}")
            return Response({'error': 'Failed to create security alert'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def alerts(self, request):
        """Get security alerts."""
        try:
            # Security: Validate request
            user = request.user
            SecurityMonitoringViewSet._validate_user_access(user)
            
            # Get filters
            filters = {
                'severity': request.query_params.get('severity'),
                'alert_type': request.query_params.get('alert_type'),
                'status': request.query_params.get('status', 'open'),
                'date_from': request.query_params.get('date_from'),
                'date_to': request.query_params.get('date_to')
            }
            
            # Get alerts
            alerts_data = SecurityMonitoringService.get_active_alerts(filters)
            
            return Response(alerts_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting security alerts: {str(e)}")
            return Response({'error': 'Failed to get security alerts'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def update_alert(self, request):
        """Update security alert status."""
        try:
            # Security: Validate request
            SecurityMonitoringViewSet._validate_update_request(request)
            
            # Update alert
            alert_id = UUID(request.data.get('alert_id'))
            status = request.data.get('status')
            
            success = SecurityMonitoringService.update_alert_status(
                alert_id, status, request.user
            )
            
            if success:
                return Response({'message': 'Alert updated successfully'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to update alert'}, status=status.HTTP_400_BAD_REQUEST)
                
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error updating security alert: {str(e)}")
            return Response({'error': 'Failed to update security alert'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_alert_request(request) -> None:
        """Validate security alert request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        required_fields = ['alert_type', 'title', 'description']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
    
    @staticmethod
    def _validate_update_request(request) -> None:
        """Validate alert update request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data.get('alert_id'):
            raise AdvertiserValidationError("alert_id is required")
        
        if not request.data.get('status'):
            raise AdvertiserValidationError("status is required")
        
        # Validate UUID format
        try:
            UUID(request.data.get('alert_id'))
        except ValueError:
            raise AdvertiserValidationError("Invalid alert_id format")
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have security monitoring permissions")


class FraudPreventionViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for comprehensive fraud prevention.
    
    Features:
    - Unified fraud prevention interface
    - Comprehensive analysis
    - Real-time monitoring
    - Advanced security
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    def __init__(self, **kwargs):
        """Initialize with fraud prevention service."""
        super().__init__(**kwargs)
        self.fraud_prevention_service = FraudPreventionService()
    
    @action(detail=False, methods=['post'])
    def comprehensive_analysis(self, request):
        """Perform comprehensive fraud analysis."""
        try:
            # Security: Validate request
            FraudPreventionViewSet._validate_comprehensive_request(request)
            
            # Get event data and context
            event_data = request.data.get('event_data', {})
            context = request.data.get('context', {})
            
            # Add request context
            context.update({
                'ip_address': FraudPreventionViewSet._get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'request_id': request.META.get('HTTP_X_REQUEST_ID', ''),
                'timestamp': timezone.now()
            })
            
            # Perform comprehensive analysis
            analysis_result = self.fraud_prevention_service.comprehensive_fraud_analysis(
                event_data, context
            )
            
            return Response(analysis_result, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in comprehensive fraud analysis: {str(e)}")
            return Response({'error': 'Comprehensive fraud analysis failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get fraud prevention dashboard."""
        try:
            # Security: Validate request
            user = request.user
            FraudPreventionViewSet._validate_user_access(user)
            
            # Get dashboard data
            dashboard_data = FraudPreventionViewSet._get_comprehensive_dashboard(user)
            
            return Response(dashboard_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting fraud prevention dashboard: {str(e)}")
            return Response({'error': 'Failed to get dashboard data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_comprehensive_request(request) -> None:
        """Validate comprehensive analysis request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate event data
        if not request.data.get('event_data'):
            raise AdvertiserValidationError("event_data is required")
    
    @staticmethod
    def _get_client_ip(request) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        return ip or '0.0.0.0'
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have fraud prevention permissions")
    
    @staticmethod
    def _get_comprehensive_dashboard(user: User) -> Dict[str, Any]:
        """Get comprehensive fraud prevention dashboard."""
        try:
            # Performance: Check cache first
            cache_key = f'fraud_prevention_dashboard_{user.id}'
            cached_dashboard = cache.get(cache_key)
            if cached_dashboard:
                return cached_dashboard
            
            # Get comprehensive statistics
            total_detections = FraudDetection.objects.count()
            fraudulent_detections = FraudDetection.objects.filter(is_fraudulent=True).count()
            active_alerts = SecurityAlert.objects.filter(status='open').count()
            
            # Recent activity
            recent_cutoff = timezone.now() - timedelta(hours=24)
            recent_detections = FraudDetection.objects.filter(
                detection_timestamp__gte=recent_cutoff
            ).count()
            
            # Risk distribution
            risk_levels = RiskScore.objects.filter(
                assessment_timestamp__gte=timezone.now() - timedelta(days=7)
            ).values('risk_level').annotate(count=Count('id'))
            
            dashboard_data = {
                'summary': {
                    'total_detections': total_detections,
                    'fraudulent_detections': fraudulent_detections,
                    'fraud_rate': (fraudulent_detections / total_detections * 100) if total_detections > 0 else 0,
                    'active_alerts': active_alerts,
                    'recent_detections_24h': recent_detections
                },
                'risk_distribution': {item['risk_level']: item['count'] for item in risk_levels},
                'recent_activity': FraudPreventionViewSet._get_recent_activity(),
                'threat_intelligence': FraudPreventionViewSet._get_threat_intelligence(),
                'generated_at': timezone.now().isoformat()
            }
            
            # Performance: Cache results
            cache.set(cache_key, dashboard_data, timeout=300)  # 5 minutes cache
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error getting comprehensive dashboard: {str(e)}")
            return {
                'summary': {'total_detections': 0, 'fraudulent_detections': 0, 'fraud_rate': 0, 'active_alerts': 0, 'recent_detections_24h': 0},
                'risk_distribution': {},
                'recent_activity': [],
                'threat_intelligence': {},
                'generated_at': timezone.now().isoformat(),
                'error': 'Failed to load dashboard data'
            }
    
    @staticmethod
    def _get_recent_activity() -> List[Dict[str, Any]]:
        """Get recent fraud prevention activity."""
        try:
            recent_cutoff = timezone.now() - timedelta(hours=24)
            
            # Recent fraud detections
            recent_detections = FraudDetection.objects.filter(
                detection_timestamp__gte=recent_cutoff
            ).order_by('-detection_timestamp')[:10]
            
            activity = []
            for detection in recent_detections:
                activity.append({
                    'type': 'fraud_detection',
                    'id': str(detection.id),
                    'risk_score': detection.risk_score,
                    'is_fraudulent': detection.is_fraudulent,
                    'timestamp': detection.detection_timestamp.isoformat()
                })
            
            return activity
        except Exception:
            return []
    
    @staticmethod
    def _get_threat_intelligence() -> Dict[str, Any]:
        """Get threat intelligence data."""
        try:
            # Mock threat intelligence data
            return {
                'global_threat_level': 'medium',
                'active_threats': [
                    {'type': 'credential_stuffing', 'severity': 'high'},
                    {'type': 'account_takeover', 'severity': 'medium'},
                    {'type': 'synthetic_fraud', 'severity': 'low'}
                ],
                'updated_at': timezone.now().isoformat()
            }
        except Exception:
            return {}
