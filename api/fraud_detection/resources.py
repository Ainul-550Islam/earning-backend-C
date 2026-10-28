# =============================================================================
# fraud_detection/resources.py
# =============================================================================
"""
API Resources for Fraud Detection System.

Provides REST framework resources and API endpoints for fraud detection
with comprehensive CRUD operations and advanced functionality.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.mixins import ListModelMixin, CreateModelMixin
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from api.fraud_detection.models import (
    FraudCase, FraudAlert, FraudRule, FraudRiskProfile,
    DeviceFingerprint, FraudSuspiciousIP
)
from api.fraud_detection.serializers import (
    FraudCaseSerializer, FraudAlertSerializer, FraudRuleSerializer,
    FraudRiskProfileSerializer, DeviceFingerprintSerializer,
    FraudSuspiciousIPSerializer
)
from api.fraud_detection.services import (
    fraud_detection_service, risk_assessment_service,
    compliance_service, threat_intelligence_service
)
from api.fraud_detection.selectors import (
    fraud_case_selector, fraud_alert_selector, fraud_rule_selector
)
from api.fraud_detection.pagination import (
    FraudDetectionPagination, FraudCasePagination, FraudAlertPagination
)
from api.fraud_detection.permissions import (
    IsOwnerOrStaff, HasFraudDetectionPermission
)
from api.fraud_detection.mixins import FraudDetectionMixin, UserRiskAssessmentMixin
from api.fraud_detection.exceptions import FraudDetectionError


logger = logging.getLogger(__name__)

User = get_user_model()


class BaseResource(APIView):
    """Base API resource for fraud detection."""
    
    permission_classes = [permissions.IsAuthenticated, HasFraudDetectionPermission]
    pagination_class = FraudDetectionPagination
    
    def get_serializer_class(self):
        """Get appropriate serializer class."""
        if hasattr(self, 'serializer_class'):
            return self.serializer_class
        raise NotImplementedError("serializer_class must be defined")
    
    def get_queryset(self):
        """Get queryset for the resource."""
        if hasattr(self, 'queryset'):
            return self.queryset
        raise NotImplementedError("queryset must be defined")
    
    def handle_exception(self, exc):
        """Handle exceptions consistently."""
        if isinstance(exc, FraudDetectionError):
            return Response(
                {'error': str(exc), 'error_code': 'fraud_detection_error'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().handle_exception(exc)


class FraudCaseResource(BaseResource, ListModelMixin, CreateModelMixin):
    """Resource for fraud case operations."""
    
    serializer_class = FraudCaseSerializer
    queryset = FraudCase.objects.all()
    pagination_class = FraudCasePagination
    
    def get(self, request: Request, *args, **kwargs) -> Response:
        """Get list of fraud cases."""
        queryset = self.get_queryset()
        
        # Apply filters
        queryset = self._apply_filters(queryset, request.query_params)
        
        # Paginate results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def post(self, request: Request, *args, **kwargs) -> Response:
        """Create a new fraud case."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            case = serializer.save(
                created_by=request.user,
                created_at=timezone.now()
            )
            
            # Create audit event
            from api.fraud_detection.events import create_case_created_event
            create_case_created_event(
                case_id=str(case.pk),
                user_id=case.user_id,
                description=case.description,
                metadata={'created_by': request.user.id}
            )
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def _apply_filters(self, queryset, params):
        """Apply filters to queryset."""
        # Status filter
        status = params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Severity filter
        severity = params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        # User filter
        user_id = params.get('user_id')
        if user_id:
            if not request.user.is_staff and str(request.user.id) != user_id:
                queryset = queryset.filter(user_id=request.user.id)
            else:
                queryset = queryset.filter(user_id=user_id)
        
        # Date range filter
        created_after = params.get('created_after')
        if created_after:
            try:
                date = datetime.fromisoformat(created_after.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__gte=date)
            except ValueError:
                logger.warning("Invalid created_after date format: %s", created_after)
        
        created_before = params.get('created_before')
        if created_before:
            try:
                date = datetime.fromisoformat(created_before.replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__lte=date)
            except ValueError:
                logger.warning("Invalid created_before date format: %s", created_before)
        
        # Risk score filter
        min_risk = params.get('min_risk_score')
        if min_risk:
            try:
                queryset = queryset.filter(risk_score__gte=int(min_risk))
            except ValueError:
                logger.warning("Invalid date filter value for created_before: %s", created_before)
        
        max_risk = params.get('max_risk_score')
        if max_risk:
            try:
                queryset = queryset.filter(risk_score__lte=int(max_risk))
            except ValueError:
                logger.warning("Invalid date filter value for created_before: %s", created_before)
        
        return queryset


class FraudCaseDetailResource(BaseResource, RetrieveAPIView):
    """Resource for individual fraud case operations."""
    
    serializer_class = FraudCaseSerializer
    queryset = FraudCase.objects.all()
    
    def get(self, request: Request, pk: Union[int, str], *args, **kwargs) -> Response:
        """Get fraud case details."""
        case = self.get_object()
        
        # Check permissions
        if not request.user.is_staff and case.user_id != request.user.id:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(case)
        return Response(serializer.data)
    
    def put(self, request: Request, pk: Union[int, str], *args, **kwargs) -> Response:
        """Update fraud case."""
        case = self.get_object()
        
        # Check permissions
        if not request.user.is_staff:
            return Response(
                {'error': 'Only staff can update cases'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(case, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            serializer.save(
                updated_by=request.user,
                updated_at=timezone.now()
            )
        
        return Response(serializer.data)
    
    def delete(self, request: Request, pk: Union[int, str], *args, **kwargs) -> Response:
        """Delete fraud case."""
        case = self.get_object()
        
        # Check permissions
        if not request.user.is_staff or not request.user.has_perm('fraud_detection.delete_case'):
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        with transaction.atomic():
            case.delete()
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class FraudAlertResource(BaseResource, ListModelMixin, CreateModelMixin):
    """Resource for fraud alert operations."""
    
    serializer_class = FraudAlertSerializer
    queryset = FraudAlert.objects.all()
    pagination_class = FraudAlertPagination
    
    def get(self, request: Request, *args, **kwargs) -> Response:
        """Get list of fraud alerts."""
        queryset = self.get_queryset()
        
        # Apply filters
        queryset = self._apply_filters(queryset, request.query_params)
        
        # Paginate results
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def post(self, request: Request, *args, **kwargs) -> Response:
        """Create a new fraud alert."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            alert = serializer.save(
                created_by=request.user,
                created_at=timezone.now()
            )
            
            # Create alert event
            from api.fraud_detection.events import create_alert_generated_event
            create_alert_generated_event(
                alert_id=str(alert.pk),
                user_id=alert.user_id,
                description=alert.description,
                severity='high' if alert.severity_score >= 70 else 'medium'
            )
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def _apply_filters(self, queryset, params):
        """Apply filters to queryset."""
        # Alert type filter
        alert_type = params.get('alert_type')
        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)
        
        # Severity filter
        min_severity = params.get('min_severity_score')
        if min_severity:
            try:
                queryset = queryset.filter(severity_score__gte=int(min_severity))
            except ValueError:
                logger.warning("Invalid date filter value for filter_value: %s", filter_value)
        
        max_severity = params.get('max_severity_score')
        if max_severity:
            try:
                queryset = queryset.filter(severity_score__lte=int(max_severity))
            except ValueError:
                logger.warning("Invalid date filter value for date_filter: %s", date_filter)
        
        # Acknowledged filter
        acknowledged = params.get('acknowledged')
        if acknowledged is not None:
            if acknowledged.lower() == 'true':
                queryset = queryset.filter(acknowledged=True)
            else:
                queryset = queryset.filter(acknowledged=False)
        
        # User filter
        user_id = params.get('user_id')
        if user_id:
            if not request.user.is_staff and str(request.user.id) != user_id:
                queryset = queryset.filter(user_id=request.user.id)
            else:
                queryset = queryset.filter(user_id=user_id)
        
        return queryset


class FraudDetectionResource(BaseResource, FraudDetectionMixin, UserRiskAssessmentMixin):
    """Resource for fraud detection operations."""
    
    def post(self, request: Request, *args, **kwargs) -> Response:
        """Perform fraud detection on transaction."""
        user_id = request.data.get('user_id')
        transaction_data = request.data.get('transaction_data')
        
        if not user_id or not transaction_data:
            return Response(
                {'error': 'user_id and transaction_data are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check permissions
        if not request.user.is_staff and str(request.user.id) != str(user_id):
            return Response(
                {'error': 'Cannot perform fraud detection for other users'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Perform fraud detection
            context = self._get_request_context(request)
            detection_result = self.perform_fraud_detection(user_id, transaction_data, context)
            
            return Response({
                'success': True,
                'detection_result': detection_result,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Fraud detection failed: {e}")
            return Response(
                {'error': f'Fraud detection failed: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get(self, request: Request, *args, **kwargs) -> Response:
        """Get fraud detection status and capabilities."""
        return Response({
            'status': 'active',
            'capabilities': [
                'transaction_analysis',
                'risk_assessment',
                'pattern_detection',
                'real_time_monitoring'
            ],
            'version': '1.0',
            'timestamp': timezone.now().isoformat()
        })


class RiskAssessmentResource(BaseResource, UserRiskAssessmentMixin):
    """Resource for risk assessment operations."""
    
    def post(self, request: Request, *args, **kwargs) -> Response:
        """Assess user risk."""
        user_id = request.data.get('user_id')
        assessment_type = request.data.get('assessment_type', 'comprehensive')
        
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check permissions
        if not request.user.is_staff and str(request.user.id) != str(user_id):
            return Response(
                {'error': 'Cannot assess risk for other users'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Assess risk
            context = self._get_request_context(request)
            assessment_result = self.assess_user_risk(user_id, assessment_type, context)
            
            return Response({
                'success': True,
                'assessment_result': assessment_result,
                'assessment_type': assessment_type,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            return Response(
                {'error': f'Risk assessment failed: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get(self, request: Request, user_id: Union[int, str] = None, *args, **kwargs) -> Response:
        """Get user risk assessment."""
        target_user_id = user_id or request.user.id
        
        # Check permissions
        if not request.user.is_staff and str(request.user.id) != str(target_user_id):
            return Response(
                {'error': 'Cannot view risk assessment for other users'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Get risk profile
            risk_result = risk_assessment_service.get_user_risk_summary(target_user_id)
            
            if not risk_result.success:
                return Response(
                    {'error': risk_result.error},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            return Response({
                'success': True,
                'risk_profile': risk_result.data,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Risk profile retrieval failed: {e}")
            return Response(
                {'error': f'Risk profile retrieval failed: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ComplianceResource(BaseResource):
    """Resource for compliance operations."""
    
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def post(self, request: Request, *args, **kwargs) -> Response:
        """Perform compliance check."""
        compliance_type = request.data.get('compliance_type', 'comprehensive')
        entity_data = request.data.get('entity_data', {})
        
        if not entity_data:
            return Response(
                {'error': 'entity_data is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Perform compliance check
            compliance_result = compliance_service.check_transaction_compliance(entity_data)
            
            return Response({
                'success': True,
                'compliance_result': compliance_result.data,
                'compliance_type': compliance_type,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Compliance check failed: {e}")
            return Response(
                {'error': f'Compliance check failed: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get(self, request: Request, *args, **kwargs) -> Response:
        """Get compliance dashboard data."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Get compliance statistics
            days = int(request.query_params.get('days', 30))
            
            from api.fraud_detection.analytics import get_fraud_analytics
            analytics = get_fraud_analytics()
            
            overview = analytics.get_fraud_overview(period_days=days)
            
            compliance_data = {
                'period_days': days,
                'total_cases': overview.get('summary_statistics', {}).get('total_cases', 0),
                'regulatory_cases': overview.get('regulatory_cases', 0),
                'compliance_score': overview.get('compliance_score', 0),
                'sar_filed': overview.get('sar_filed', 0),
                'timestamp': timezone.now().isoformat()
            }
            
            return Response({
                'success': True,
                'compliance_data': compliance_data
            })
            
        except Exception as e:
            logger.error(f"Compliance dashboard failed: {e}")
            return Response(
                {'error': f'Compliance dashboard failed: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnalyticsResource(BaseResource):
    """Resource for analytics operations."""
    
    def get(self, request: Request, *args, **kwargs) -> Response:
        """Get fraud analytics data."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            analytics_type = request.query_params.get('type', 'overview')
            days = int(request.query_params.get('days', 30))
            
            from api.fraud_detection.analytics import get_fraud_analytics
            analytics = get_fraud_analytics()
            
            if analytics_type == 'overview':
                data = analytics.get_fraud_overview(period_days=days)
            elif analytics_type == 'risk_distribution':
                data = analytics.get_risk_distribution(period_days=days)
            elif analytics_type == 'alert_frequency':
                data = analytics.get_alert_frequency(period_days=days)
            else:
                return Response(
                    {'error': f'Unknown analytics type: {analytics_type}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({
                'success': True,
                'analytics_type': analytics_type,
                'period_days': days,
                'data': data,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Analytics retrieval failed: {e}")
            return Response(
                {'error': f'Analytics retrieval failed: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ThreatIntelligenceResource(BaseResource):
    """Resource for threat intelligence operations."""
    
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def post(self, request: Request, *args, **kwargs) -> Response:
        """Perform threat intelligence check."""
        check_type = request.data.get('check_type', 'ip_reputation')
        check_data = request.data.get('data', {})
        
        if not check_data:
            return Response(
                {'error': 'data is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Perform threat intelligence check
            if check_type == 'ip_reputation':
                result = threat_intelligence_service.check_ip_reputation(
                    check_data.get('ip_address', '')
                )
            elif check_type == 'sanctions':
                result = threat_intelligence_service.check_sanctions(
                    check_data
                )
            else:
                return Response(
                    {'error': f'Unknown check type: {check_type}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({
                'success': True,
                'check_type': check_type,
                'result': result.data if result.success else {'error': result.error},
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Threat intelligence check failed: {e}")
            return Response(
                {'error': f'Threat intelligence check failed: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ExportResource(BaseResource):
    """Resource for data export operations."""
    
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def post(self, request: Request, *args, **kwargs) -> Response:
        """Export fraud detection data."""
        export_type = request.data.get('export_type', 'cases')
        export_format = request.data.get('format', 'csv')
        filters = request.data.get('filters', {})
        
        try:
            # Perform export
            if export_type == 'cases':
                result = self._export_cases(export_format, filters)
            elif export_type == 'alerts':
                result = self._export_alerts(export_format, filters)
            elif export_type == 'rules':
                result = self._export_rules(export_format, filters)
            else:
                return Response(
                    {'error': f'Unknown export type: {export_type}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({
                'success': True,
                'export_type': export_type,
                'format': export_format,
                'result': result,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return Response(
                {'error': f'Export failed: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _export_cases(self, format_type: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Export fraud cases."""
        queryset = FraudCase.objects.all()
        
        # Apply filters
        if 'status' in filters:
            queryset = queryset.filter(status=filters['status'])
        if 'severity' in filters:
            queryset = queryset.filter(severity=filters['severity'])
        if 'date_from' in filters:
            queryset = queryset.filter(created_at__gte=filters['date_from'])
        if 'date_to' in filters:
            queryset = queryset.filter(created_at__lte=filters['date_to'])
        
        # Generate export
        if format_type == 'csv':
            return self._generate_csv_export(queryset, 'cases')
        elif format_type == 'excel':
            return self._generate_excel_export(queryset, 'cases')
        else:
            raise ValueError(f"Unsupported format: {format_type}")
    
    def _export_alerts(self, format_type: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Export fraud alerts."""
        queryset = FraudAlert.objects.all()
        
        # Apply filters
        if 'alert_type' in filters:
            queryset = queryset.filter(alert_type=filters['alert_type'])
        if 'acknowledged' in filters:
            queryset = queryset.filter(acknowledged=filters['acknowledged'])
        if 'date_from' in filters:
            queryset = queryset.filter(created_at__gte=filters['date_from'])
        if 'date_to' in filters:
            queryset = queryset.filter(created_at__lte=filters['date_to'])
        
        # Generate export
        if format_type == 'csv':
            return self._generate_csv_export(queryset, 'alerts')
        elif format_type == 'excel':
            return self._generate_excel_export(queryset, 'alerts')
        else:
            raise ValueError(f"Unsupported format: {format_type}")
    
    def _export_rules(self, format_type: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Export fraud rules."""
        queryset = FraudRule.objects.all()
        
        # Apply filters
        if 'enabled' in filters:
            queryset = queryset.filter(enabled=filters['enabled'])
        if 'rule_type' in filters:
            queryset = queryset.filter(rule_type=filters['rule_type'])
        
        # Generate export
        if format_type == 'csv':
            return self._generate_csv_export(queryset, 'rules')
        elif format_type == 'excel':
            return self._generate_excel_export(queryset, 'rules')
        else:
            raise ValueError(f"Unsupported format: {format_type}")
    
    def _generate_csv_export(self, queryset, export_type: str) -> Dict[str, Any]:
        """Generate CSV export."""
        import csv
        import io
        
        output = io.StringIO()
        
        if export_type == 'cases':
            fieldnames = ['id', 'user_id', 'case_type', 'severity', 'status', 'risk_score', 
                         'title', 'description', 'created_at', 'updated_at']
        elif export_type == 'alerts':
            fieldnames = ['id', 'user_id', 'alert_type', 'severity_score', 'title', 
                         'description', 'acknowledged', 'created_at']
        elif export_type == 'rules':
            fieldnames = ['id', 'name', 'rule_type', 'enabled', 'priority', 'risk_score_impact']
        else:
            raise ValueError(f"Unknown export type: {export_type}")
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for item in queryset:
            row = {}
            for field in fieldnames:
                value = getattr(item, field, '')
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                row[field] = value
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        return {
            'content': csv_content,
            'filename': f'fraud_{export_type}_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv',
            'content_type': 'text/csv',
            'size': len(csv_content)
        }
    
    def _generate_excel_export(self, queryset, export_type: str) -> Dict[str, Any]:
        """Generate Excel export (simplified implementation)."""
        # This would typically use openpyxl or similar
        # For now, return CSV content as placeholder
        return self._generate_csv_export(queryset, export_type)


# Resource registry for easy access
class ResourceRegistry:
    """Registry for API resources."""
    
    resources = {
        'cases': FraudCaseResource,
        'case_detail': FraudCaseDetailResource,
        'alerts': FraudAlertResource,
        'fraud_detection': FraudDetectionResource,
        'risk_assessment': RiskAssessmentResource,
        'compliance': ComplianceResource,
        'analytics': AnalyticsResource,
        'threat_intelligence': ThreatIntelligenceResource,
        'export': ExportResource
    }
    
    @classmethod
    def get_resource(cls, resource_name: str):
        """Get resource class by name."""
        return cls.resources.get(resource_name)
    
    @classmethod
    def register_resource(cls, name: str, resource_class: type):
        """Register a resource class."""
        cls.resources[name] = resource_class
        logger.info(f"Registered resource: {name}")
    
    @classmethod
    def list_resources(cls) -> List[str]:
        """List all registered resources."""
        return list(cls.resources.keys())


# Export all resources
__all__ = [
    # Base resources
    'BaseResource',
    
    # Main resources
    'FraudCaseResource',
    'FraudCaseDetailResource',
    'FraudAlertResource',
    'FraudDetectionResource',
    'RiskAssessmentResource',
    'ComplianceResource',
    'AnalyticsResource',
    'ThreatIntelligenceResource',
    'ExportResource',
    
    # Registry
    'ResourceRegistry',
]
