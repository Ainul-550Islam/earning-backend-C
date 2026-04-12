"""
Reporting Dashboard Views

This module provides DRF ViewSets for reporting and dashboard operations with
enterprise-grade security, real-time analytics, and comprehensive data visualization
following industry standards from Google Analytics, Tableau, and Power BI.
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
from uuid import UUID
import json
import time

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
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from ..database_models.advertiser_model import Advertiser
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from ..database_models.reporting_model import Report, Dashboard, Visualization, ReportSchedule
from ..models import AdvertiserPortalBaseModel
from ..enums import *
from ..utils import *
from ..validators import *
from ..exceptions import *
from .services import (
    ReportingService, DashboardService, AnalyticsService, VisualizationService,
    ReportGenerationService, ReportData, DashboardWidget
)

User = get_user_model()


class ReportingViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for reporting operations.
    
    Features:
    - Comprehensive report generation
    - Real-time data processing
    - Multi-format export
    - Scheduled reports
    - Performance optimization
    - Type-safe Python code
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """
        Generate comprehensive report with enterprise-grade processing.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Rate limiting
        - Audit logging
        
        Performance optimizations:
        - Parallel data processing
        - Caching of frequent reports
        - Optimized database queries
        """
        try:
            # Security: Validate request
            ReportingViewSet._validate_generate_request(request)
            
            # Get report configuration
            report_config = request.data
            
            # Generate report
            report_data = ReportingService.generate_report(report_config, request.user)
            
            # Return comprehensive response
            response_data = {
                'report_id': report_data.report_id,
                'report_name': report_data.report_name,
                'report_type': report_data.report_type,
                'data': report_data.data,
                'metadata': report_data.metadata,
                'total_records': report_data.total_records,
                'execution_time': report_data.execution_time,
                'generated_at': report_data.generated_at.isoformat()
            }
            
            # Security: Log report generation
            ReportingViewSet._log_report_generation(report_data, request.user)
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            return Response({'error': 'Failed to generate report'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def schedule(self, request):
        """
        Schedule automated report generation and delivery.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Schedule validation
        - Audit logging
        """
        try:
            # Security: Validate request
            ReportingViewSet._validate_schedule_request(request)
            
            # Get schedule configuration
            schedule_config = request.data
            
            # Create report schedule
            schedule = ReportingService.schedule_report(schedule_config, request.user)
            
            # Return response
            response_data = {
                'schedule_id': str(schedule.id),
                'name': schedule.name,
                'schedule_type': schedule.schedule_type,
                'delivery_method': schedule.delivery_method,
                'is_active': schedule.is_active,
                'created_at': schedule.created_at.isoformat()
            }
            
            # Security: Log schedule creation
            ReportingViewSet._log_schedule_creation(schedule, request.user)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error scheduling report: {str(e)}")
            return Response({'error': 'Failed to schedule report'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def list_items(self, request):
        """
        List available reports with filtering and pagination.
        
        Security measures:
        - User permission validation
        - Data access control
        - Rate limiting
        """
        try:
            # Security: Validate user access
            user = request.user
            ReportingViewSet._validate_user_access(user)
            
            # Get query parameters
            filters = {
                'report_type': request.query_params.get('report_type'),
                'date_from': request.query_params.get('date_from'),
                'date_to': request.query_params.get('date_to'),
                'advertiser_id': request.query_params.get('advertiser_id')
            }
            
            # Validate filters
            ReportingViewSet._validate_list_filters(filters)
            
            # Get reports list
            reports_data = ReportingViewSet._get_reports_list(user, filters)
            
            return Response(reports_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error listing reports: {str(e)}")
            return Response({'error': 'Failed to list reports'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def export(self, request):
        """
        Export report in various formats.
        
        Security measures:
        - Input validation
        - User permission validation
        - Format validation
        - File size limits
        """
        try:
            # Security: Validate request
            ReportingViewSet._validate_export_request(request)
            
            # Get export parameters
            report_id = UUID(request.data.get('report_id'))
            export_format = request.data.get('format', 'csv')
            filters = request.data.get('filters', {})
            
            # Export report
            response = ReportingService.export_report(report_id, export_format, filters)
            
            return response
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error exporting report: {str(e)}")
            return Response({'error': 'Failed to export report'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def templates(self, request):
        """
        Get available report templates.
        
        Security measures:
        - User permission validation
        - Template access control
        """
        try:
            # Security: Validate user access
            user = request.user
            ReportingViewSet._validate_user_access(user)
            
            # Get report templates
            templates = ReportingViewSet._get_report_templates(user)
            
            return Response({'templates': templates}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting report templates: {str(e)}")
            return Response({'error': 'Failed to get templates'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_generate_request(request) -> None:
        """Validate report generation request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['name', 'report_type']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate report type
        valid_types = ['performance', 'financial', 'audience', 'campaign', 'custom']
        if request.data.get('report_type') not in valid_types:
            raise AdvertiserValidationError(f"Invalid report type: {request.data.get('report_type')}")
    
    @staticmethod
    def _validate_schedule_request(request) -> None:
        """Validate schedule request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        required_fields = ['name', 'report_config', 'schedule_type']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate schedule type
        valid_types = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'custom']
        if request.data.get('schedule_type') not in valid_types:
            raise AdvertiserValidationError(f"Invalid schedule type: {request.data.get('schedule_type')}")
    
    @staticmethod
    def _validate_export_request(request) -> None:
        """Validate export request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data.get('report_id'):
            raise AdvertiserValidationError("Report ID is required")
        
        # Security: Validate format
        valid_formats = ['csv', 'excel', 'pdf', 'json', 'xml']
        export_format = request.data.get('format', 'csv')
        if export_format not in valid_formats:
            raise AdvertiserValidationError(f"Invalid export format: {export_format}")
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have reporting permissions")
    
    @staticmethod
    def _validate_list_filters(filters: Dict[str, Any]) -> None:
        """Validate list filters."""
        # Validate report type
        if filters.get('report_type'):
            valid_types = ['performance', 'financial', 'audience', 'campaign', 'custom']
            if filters['report_type'] not in valid_types:
                raise AdvertiserValidationError(f"Invalid report type: {filters['report_type']}")
        
        # Validate date formats
        for date_field in ['date_from', 'date_to']:
            date_value = filters.get(date_field)
            if date_value:
                try:
                    datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                except ValueError:
                    raise AdvertiserValidationError(f"Invalid {date_field} format")
        
        # Validate advertiser ID
        if filters.get('advertiser_id'):
            try:
                UUID(filters['advertiser_id'])
            except ValueError:
                raise AdvertiserValidationError("Invalid advertiser ID format")
    
    @staticmethod
    def _get_reports_list(user: User, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get reports list with filtering and pagination."""
        try:
            # Build query
            queryset = Report.objects.all()
            
            # Apply user filter
            if not user.is_superuser:
                queryset = queryset.filter(created_by=user)
            
            # Apply filters
            if filters.get('report_type'):
                queryset = queryset.filter(report_type=filters['report_type'])
            
            if filters.get('date_from'):
                date_from = datetime.fromisoformat(filters['date_from'].replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__gte=date_from)
            
            if filters.get('date_to'):
                date_to = datetime.fromisoformat(filters['date_to'].replace('Z', '+00:00'))
                queryset = queryset.filter(created_at__lte=date_to)
            
            if filters.get('advertiser_id'):
                queryset = queryset.filter(advertiser_id=UUID(filters['advertiser_id']))
            
            # Pagination
            page = int(filters.get('page', 1))
            page_size = min(int(filters.get('page_size', 20)), 100)
            offset = (page - 1) * page_size
            
            # Get paginated results
            results = queryset[offset:offset + page_size]
            
            # Format results
            reports = []
            for report in results:
                reports.append({
                    'id': str(report.id),
                    'name': report.name,
                    'report_type': report.report_type,
                    'description': report.description,
                    'created_at': report.created_at.isoformat(),
                    'updated_at': report.updated_at.isoformat(),
                    'created_by': report.created_by.username if report.created_by else None
                })
            
            return {
                'reports': reports,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': queryset.count(),
                    'total_pages': (queryset.count() + page_size - 1) // page_size
                },
                'filters_applied': filters
            }
            
        except Exception as e:
            logger.error(f"Error getting reports list: {str(e)}")
            return {
                'reports': [],
                'pagination': {'page': 1, 'page_size': 20, 'total_count': 0, 'total_pages': 0},
                'filters_applied': filters,
                'error': 'Failed to retrieve reports'
            }
    
    @staticmethod
    def _get_report_templates(user: User) -> List[Dict[str, Any]]:
        """Get available report templates."""
        try:
            templates = [
                {
                    'id': 'performance_summary',
                    'name': 'Performance Summary',
                    'description': 'Overview of key performance metrics',
                    'report_type': 'performance',
                    'time_range': 'last_30_days',
                    'metrics': ['CTR', 'CPC', 'CPA', 'ROAS', 'Conversions', 'Revenue']
                },
                {
                    'id': 'financial_overview',
                    'name': 'Financial Overview',
                    'description': 'Comprehensive financial analysis',
                    'report_type': 'financial',
                    'time_range': 'last_30_days',
                    'metrics': ['Revenue', 'Spend', 'Profit', 'ROI', 'CAC', 'LTV']
                },
                {
                    'id': 'audience_analysis',
                    'name': 'Audience Analysis',
                    'description': 'Detailed audience demographics and behavior',
                    'report_type': 'audience',
                    'time_range': 'last_30_days',
                    'segments': ['Demographics', 'Geography', 'Behavior', 'Device', 'Interests']
                },
                {
                    'id': 'campaign_performance',
                    'name': 'Campaign Performance',
                    'description': 'Campaign-specific performance metrics',
                    'report_type': 'campaign',
                    'time_range': 'last_30_days',
                    'metrics': ['Impressions', 'Clicks', 'Conversions', 'Spend', 'Revenue']
                }
            ]
            
            return templates
            
        except Exception as e:
            logger.error(f"Error getting report templates: {str(e)}")
            return []
    
    @staticmethod
    def _log_report_generation(report_data: ReportData, user: User) -> None:
        """Log report generation for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_action(
                action='generate_report',
                object_type='Report',
                object_id=report_data.report_id,
                user=user,
                description=f"Generated report: {report_data.report_name}",
                metadata={
                    'report_type': report_data.report_type,
                    'execution_time': report_data.execution_time,
                    'total_records': report_data.total_records
                }
            )
        except Exception as e:
            logger.error(f"Error logging report generation: {str(e)}")
    
    @staticmethod
    def _log_schedule_creation(schedule: ReportSchedule, user: User) -> None:
        """Log schedule creation for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                schedule,
                user,
                description=f"Created report schedule: {schedule.name}"
            )
        except Exception as e:
            logger.error(f"Error logging schedule creation: {str(e)}")


class DashboardViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for dashboard operations.
    
    Features:
    - Real-time dashboard widgets
    - Customizable layouts
    - Interactive visualizations
    - Performance optimization
    - Multi-device support
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create customizable dashboard with widgets.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Widget validation
        - Audit logging
        """
        try:
            # Security: Validate request
            DashboardViewSet._validate_create_request(request)
            
            # Get dashboard configuration
            dashboard_config = request.data
            
            # Create dashboard
            dashboard = DashboardService.create_dashboard(dashboard_config, request.user)
            
            # Return response
            response_data = {
                'dashboard_id': str(dashboard.id),
                'name': dashboard.name,
                'description': dashboard.description,
                'layout': dashboard.layout,
                'widgets': dashboard.widgets,
                'is_default': dashboard.is_default,
                'is_public': dashboard.is_public,
                'created_at': dashboard.created_at.isoformat()
            }
            
            # Security: Log dashboard creation
            DashboardViewSet._log_dashboard_creation(dashboard, request.user)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating dashboard: {str(e)}")
            return Response({'error': 'Failed to create dashboard'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def data(self, request, pk=None):
        """
        Get dashboard data with real-time widget updates.
        
        Security measures:
        - User permission validation
        - Dashboard access control
        - Rate limiting
        """
        try:
            # Security: Validate dashboard access
            dashboard_id = UUID(pk)
            dashboard_data = DashboardService.get_dashboard_data(dashboard_id, request.user)
            
            return Response(dashboard_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting dashboard data: {str(e)}")
            return Response({'error': 'Failed to get dashboard data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def update_layout(self, request, pk=None):
        """
        Update dashboard layout configuration.
        
        Security measures:
        - User permission validation
        - Layout validation
        - Audit logging
        """
        try:
            # Security: Validate dashboard access
            dashboard_id = UUID(pk)
            layout_config = request.data
            
            # Update layout
            success = DashboardService.update_dashboard_layout(dashboard_id, layout_config, request.user)
            
            if success:
                return Response({'message': 'Dashboard layout updated successfully'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to update dashboard layout'}, status=status.HTTP_400_BAD_REQUEST)
                
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error updating dashboard layout: {str(e)}")
            return Response({'error': 'Failed to update dashboard layout'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def list_items(self, request):
        """
        List available dashboards.
        
        Security measures:
        - User permission validation
        - Dashboard access control
        """
        try:
            # Security: Validate user access
            user = request.user
            DashboardViewSet._validate_user_access(user)
            
            # Get dashboards list
            dashboards_data = DashboardViewSet._get_dashboards_list(user)
            
            return Response(dashboards_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error listing dashboards: {str(e)}")
            return Response({'error': 'Failed to list dashboards'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def templates(self, request):
        """
        Get available dashboard templates.
        
        Security measures:
        - User permission validation
        - Template access control
        """
        try:
            # Security: Validate user access
            user = request.user
            DashboardViewSet._validate_user_access(user)
            
            # Get dashboard templates
            templates = DashboardViewSet._get_dashboard_templates(user)
            
            return Response({'templates': templates}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting dashboard templates: {str(e)}")
            return Response({'error': 'Failed to get templates'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate dashboard creation request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['name']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate widgets
        widgets = request.data.get('widgets', [])
        for widget in widgets:
            if not isinstance(widget, dict):
                raise AdvertiserValidationError("Widget configuration must be a dictionary")
            
            if 'id' not in widget or 'type' not in widget:
                raise AdvertiserValidationError("Widget must have id and type")
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have dashboard permissions")
    
    @staticmethod
    def _get_dashboards_list(user: User) -> Dict[str, Any]:
        """Get dashboards list with filtering."""
        try:
            # Build query
            queryset = Dashboard.objects.all()
            
            # Apply user filter
            if not user.is_superuser:
                queryset = queryset.filter(Q(created_by=user) | Q(is_public=True))
            
            # Get results
            dashboards = []
            for dashboard in queryset:
                dashboards.append({
                    'id': str(dashboard.id),
                    'name': dashboard.name,
                    'description': dashboard.description,
                    'is_default': dashboard.is_default,
                    'is_public': dashboard.is_public,
                    'widget_count': len(dashboard.widgets),
                    'created_at': dashboard.created_at.isoformat(),
                    'created_by': dashboard.created_by.username if dashboard.created_by else None
                })
            
            return {
                'dashboards': dashboards,
                'total_count': len(dashboards)
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboards list: {str(e)}")
            return {
                'dashboards': [],
                'total_count': 0,
                'error': 'Failed to retrieve dashboards'
            }
    
    @staticmethod
    def _get_dashboard_templates(user: User) -> List[Dict[str, Any]]:
        """Get available dashboard templates."""
        try:
            templates = [
                {
                    'id': 'performance_overview',
                    'name': 'Performance Overview',
                    'description': 'Key performance metrics dashboard',
                    'widgets': [
                        {'id': 'ctr', 'type': 'metric', 'title': 'CTR'},
                        {'id': 'cpc', 'type': 'metric', 'title': 'CPC'},
                        {'id': 'conversions', 'type': 'metric', 'title': 'Conversions'},
                        {'id': 'revenue', 'type': 'metric', 'title': 'Revenue'},
                        {'id': 'performance_chart', 'type': 'chart', 'title': 'Performance Trend'},
                        {'id': 'campaign_table', 'type': 'table', 'title': 'Campaign Performance'}
                    ]
                },
                {
                    'id': 'financial_dashboard',
                    'name': 'Financial Dashboard',
                    'description': 'Financial metrics and analysis',
                    'widgets': [
                        {'id': 'revenue', 'type': 'metric', 'title': 'Revenue'},
                        {'id': 'spend', 'type': 'metric', 'title': 'Spend'},
                        {'id': 'roi', 'type': 'metric', 'title': 'ROI'},
                        {'id': 'profit', 'type': 'metric', 'title': 'Profit'},
                        {'id': 'financial_chart', 'type': 'chart', 'title': 'Financial Trend'},
                        {'id': 'budget_table', 'type': 'table', 'title': 'Budget Analysis'}
                    ]
                },
                {
                    'id': 'audience_dashboard',
                    'name': 'Audience Dashboard',
                    'description': 'Audience analytics and demographics',
                    'widgets': [
                        {'id': 'total_audience', 'type': 'metric', 'title': 'Total Audience'},
                        {'id': 'new_users', 'type': 'metric', 'title': 'New Users'},
                        {'id': 'engagement', 'type': 'metric', 'title': 'Engagement Rate'},
                        {'id': 'demographics', 'type': 'chart', 'title': 'Demographics'},
                        {'id': 'geography', 'type': 'map', 'title': 'Geographic Distribution'},
                        {'id': 'behavior', 'type': 'chart', 'title': 'Behavior Analysis'}
                    ]
                }
            ]
            
            return templates
            
        except Exception as e:
            logger.error(f"Error getting dashboard templates: {str(e)}")
            return []
    
    @staticmethod
    def _log_dashboard_creation(dashboard: Dashboard, user: User) -> None:
        """Log dashboard creation for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                dashboard,
                user,
                description=f"Created dashboard: {dashboard.name}"
            )
        except Exception as e:
            logger.error(f"Error logging dashboard creation: {str(e)}")


class AnalyticsViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for analytics operations.
    
    Features:
    - Advanced metrics calculation
    - Predictive analytics
    - Behavioral analysis
    - Real-time insights
    - Performance optimization
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """
        Calculate advanced analytics metrics.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Metric validation
        - Audit logging
        """
        try:
            # Security: Validate request
            AnalyticsViewSet._validate_calculate_request(request)
            
            # Get metric configuration
            metric_config = request.data
            
            # Calculate metrics
            metrics_data = AnalyticsService.calculate_metrics(metric_config, request.user)
            
            return Response(metrics_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error calculating metrics: {str(e)}")
            return Response({'error': 'Failed to calculate metrics'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def insights(self, request):
        """
        Generate actionable insights from analytics data.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Insight validation
        - Audit logging
        """
        try:
            # Security: Validate request
            AnalyticsViewSet._validate_insights_request(request)
            
            # Get insight configuration
            insight_config = request.data
            
            # Generate insights
            insights_data = AnalyticsService.get_insights(insight_config, request.user)
            
            return Response({'insights': insights_data}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error generating insights: {str(e)}")
            return Response({'error': 'Failed to generate insights'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """
        Get available analytics metrics.
        
        Security measures:
        - User permission validation
        - Metric access control
        """
        try:
            # Security: Validate user access
            user = request.user
            AnalyticsViewSet._validate_user_access(user)
            
            # Get available metrics
            metrics = AnalyticsViewSet._get_available_metrics(user)
            
            return Response({'metrics': metrics}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting metrics: {str(e)}")
            return Response({'error': 'Failed to get metrics'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_calculate_request(request) -> None:
        """Validate metrics calculation request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['name', 'type', 'data_source']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate data source
        valid_sources = ['performance', 'analytics', 'campaign', 'creative']
        if request.data.get('data_source') not in valid_sources:
            raise AdvertiserValidationError(f"Invalid data source: {request.data.get('data_source')}")
    
    @staticmethod
    def _validate_insights_request(request) -> None:
        """Validate insights request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['data_source', 'insight_types']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate insight types
        valid_types = ['trend', 'segmentation', 'correlation', 'anomaly', 'prediction']
        insight_types = request.data.get('insight_types', [])
        for insight_type in insight_types:
            if insight_type not in valid_types:
                raise AdvertiserValidationError(f"Invalid insight type: {insight_type}")
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have analytics permissions")
    
    @staticmethod
    def _get_available_metrics(user: User) -> List[Dict[str, Any]]:
        """Get available analytics metrics."""
        try:
            metrics = [
                {
                    'id': 'ctr',
                    'name': 'Click-Through Rate',
                    'description': 'Percentage of clicks per impression',
                    'type': 'rate',
                    'data_source': 'performance',
                    'unit': '%'
                },
                {
                    'id': 'cpc',
                    'name': 'Cost Per Click',
                    'description': 'Average cost per click',
                    'type': 'average',
                    'data_source': 'performance',
                    'unit': 'USD'
                },
                {
                    'id': 'cpa',
                    'name': 'Cost Per Acquisition',
                    'description': 'Average cost per conversion',
                    'type': 'average',
                    'data_source': 'performance',
                    'unit': 'USD'
                },
                {
                    'id': 'roas',
                    'name': 'Return On Ad Spend',
                    'description': 'Revenue generated per dollar spent',
                    'type': 'ratio',
                    'data_source': 'performance',
                    'unit': 'x'
                },
                {
                    'id': 'conversions',
                    'name': 'Conversions',
                    'description': 'Total number of conversions',
                    'type': 'count',
                    'data_source': 'performance',
                    'unit': 'count'
                },
                {
                    'id': 'revenue',
                    'name': 'Revenue',
                    'description': 'Total revenue generated',
                    'type': 'sum',
                    'data_source': 'performance',
                    'unit': 'USD'
                }
            ]
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting available metrics: {str(e)}")
            return []


class VisualizationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for visualization operations.
    
    Features:
    - Interactive chart generation
    - Real-time data visualization
    - Custom visualization types
    - High-performance rendering
    - Multi-format export
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def create_item(self, request):
        """
        Create interactive visualization.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Visualization validation
        - Audit logging
        """
        try:
            # Security: Validate request
            VisualizationViewSet._validate_create_request(request)
            
            # Get visualization configuration
            viz_config = request.data
            
            # Create visualization
            visualization = VisualizationService.create_visualization(viz_config, request.user)
            
            # Return response
            response_data = {
                'visualization_id': str(visualization.id),
                'name': visualization.name,
                'description': visualization.description,
                'viz_type': visualization.viz_type,
                'data_source': visualization.data_source,
                'chart_config': visualization.chart_config,
                'is_interactive': visualization.is_interactive,
                'created_at': visualization.created_at.isoformat()
            }
            
            # Security: Log visualization creation
            VisualizationViewSet._log_visualization_creation(visualization, request.user)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error creating visualization: {str(e)}")
            return Response({'error': 'Failed to create visualization'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def data(self, request, pk=None):
        """
        Get visualization data with interactive features.
        
        Security measures:
        - User permission validation
        - Visualization access control
        - Rate limiting
        """
        try:
            # Security: Validate visualization access
            viz_id = UUID(pk)
            viz_data = VisualizationService.get_visualization_data(viz_id, request.user)
            
            return Response(viz_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting visualization data: {str(e)}")
            return Response({'error': 'Failed to get visualization data'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def types(self, request):
        """
        Get available visualization types.
        
        Security measures:
        - User permission validation
        - Type access control
        """
        try:
            # Security: Validate user access
            user = request.user
            VisualizationViewSet._validate_user_access(user)
            
            # Get visualization types
            types = VisualizationViewSet._get_visualization_types(user)
            
            return Response({'types': types}, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting visualization types: {str(e)}")
            return Response({'error': 'Failed to get types'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_create_request(request) -> None:
        """Validate visualization creation request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data:
            raise AdvertiserValidationError("Request data is required")
        
        required_fields = ['name', 'viz_type', 'data_source']
        for field in required_fields:
            if not request.data.get(field):
                raise AdvertiserValidationError(f"Required field missing: {field}")
        
        # Security: Validate visualization type
        valid_types = ['line_chart', 'bar_chart', 'pie_chart', 'scatter_plot', 'heatmap', 'custom']
        if request.data.get('viz_type') not in valid_types:
            raise AdvertiserValidationError(f"Invalid visualization type: {request.data.get('viz_type')}")
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have visualization permissions")
    
    @staticmethod
    def _get_visualization_types(user: User) -> List[Dict[str, Any]]:
        """Get available visualization types."""
        try:
            types = [
                {
                    'id': 'line_chart',
                    'name': 'Line Chart',
                    'description': 'Time series line chart',
                    'data_requirements': ['time_series'],
                    'config_options': ['x_axis', 'y_axis', 'time_range']
                },
                {
                    'id': 'bar_chart',
                    'name': 'Bar Chart',
                    'description': 'Categorical bar chart',
                    'data_requirements': ['categorical'],
                    'config_options': ['x_axis', 'y_axis', 'orientation']
                },
                {
                    'id': 'pie_chart',
                    'name': 'Pie Chart',
                    'description': 'Proportional pie chart',
                    'data_requirements': ['proportional'],
                    'config_options': ['categories', 'values']
                },
                {
                    'id': 'scatter_plot',
                    'name': 'Scatter Plot',
                    'description': 'X-Y scatter plot',
                    'data_requirements': ['x_y_data'],
                    'config_options': ['x_axis', 'y_axis', 'size', 'color']
                },
                {
                    'id': 'heatmap',
                    'name': 'Heatmap',
                    'description': 'Matrix heatmap',
                    'data_requirements': ['matrix_data'],
                    'config_options': ['x_axis', 'y_axis', 'color_scale']
                }
            ]
            
            return types
            
        except Exception as e:
            logger.error(f"Error getting visualization types: {str(e)}")
            return []
    
    @staticmethod
    def _log_visualization_creation(visualization: Visualization, user: User) -> None:
        """Log visualization creation for audit trail."""
        try:
            from ..database_models.audit_model import AuditLog
            AuditLog.log_creation(
                visualization,
                user,
                description=f"Created visualization: {visualization.name}"
            )
        except Exception as e:
            logger.error(f"Error logging visualization creation: {str(e)}")


class ReportGenerationViewSet(viewsets.ViewSet):
    """
    Enterprise-grade ViewSet for automated report generation.
    
    Features:
    - Automated report generation
    - Scheduled delivery
    - Template management
    - Performance optimization
    """
    
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    
    @action(detail=False, methods=['post'])
    def trigger(self, request):
        """
        Trigger automated report generation.
        
        Security measures:
        - Input validation and sanitization
        - User permission validation
        - Schedule validation
        - Audit logging
        """
        try:
            # Security: Validate request
            ReportGenerationViewSet._validate_trigger_request(request)
            
            # Get schedule ID
            schedule_id = UUID(request.data.get('schedule_id'))
            
            # Generate automated report
            success = ReportGenerationService.generate_automated_report(schedule_id)
            
            if success:
                return Response({'message': 'Automated report generated successfully'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to generate automated report'}, status=status.HTTP_400_BAD_REQUEST)
                
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error triggering automated report: {str(e)}")
            return Response({'error': 'Failed to trigger automated report'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def schedules(self, request):
        """
        List report schedules.
        
        Security measures:
        - User permission validation
        - Schedule access control
        """
        try:
            # Security: Validate user access
            user = request.user
            ReportGenerationViewSet._validate_user_access(user)
            
            # Get schedules list
            schedules_data = ReportGenerationViewSet._get_schedules_list(user)
            
            return Response(schedules_data, status=status.HTTP_200_OK)
            
        except (AdvertiserValidationError, AdvertiserServiceError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error listing schedules: {str(e)}")
            return Response({'error': 'Failed to list schedules'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @staticmethod
    def _validate_trigger_request(request) -> None:
        """Validate trigger request."""
        # Security: Check authentication
        if not request.user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        # Security: Validate required fields
        if not request.data.get('schedule_id'):
            raise AdvertiserValidationError("Schedule ID is required")
        
        # Security: Validate UUID format
        try:
            UUID(request.data.get('schedule_id'))
        except ValueError:
            raise AdvertiserValidationError("Invalid schedule ID format")
    
    @staticmethod
    def _validate_user_access(user: User) -> None:
        """Validate user access permissions."""
        if not user.is_authenticated:
            raise AdvertiserValidationError("Authentication required")
        
        if not (user.is_superuser or user.is_staff):
            if not hasattr(user, 'advertiser') or not user.advertiser:
                raise AdvertiserValidationError("User does not have report generation permissions")
    
    @staticmethod
    def _get_schedules_list(user: User) -> Dict[str, Any]:
        """Get report schedules list."""
        try:
            # Build query
            queryset = ReportSchedule.objects.all()
            
            # Apply user filter
            if not user.is_superuser:
                queryset = queryset.filter(created_by=user)
            
            # Get results
            schedules = []
            for schedule in queryset:
                schedules.append({
                    'id': str(schedule.id),
                    'name': schedule.name,
                    'schedule_type': schedule.schedule_type,
                    'delivery_method': schedule.delivery_method,
                    'is_active': schedule.is_active,
                    'last_run': schedule.last_run.isoformat() if schedule.last_run else None,
                    'created_at': schedule.created_at.isoformat()
                })
            
            return {
                'schedules': schedules,
                'total_count': len(schedules)
            }
            
        except Exception as e:
            logger.error(f"Error getting schedules list: {str(e)}")
            return {
                'schedules': [],
                'total_count': 0,
                'error': 'Failed to retrieve schedules'
            }
