"""
Analytics Management Views

This module contains Django REST Framework ViewSets for managing
analytics operations, reporting, dashboards, and metrics.
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..database_models.analytics_model import AnalyticsReport, AnalyticsDashboard, AnalyticsAlert
from ..database_models.campaign_model import Campaign
from ..database_models.creative_model import Creative
from .services import (
    AnalyticsService, ReportingService, DashboardService,
    MetricsService, VisualizationService
)
from .serializers import *
from ..exceptions import *
from ..utils import *


class AnalyticsViewSet(viewsets.ViewSet):
    """ViewSet for managing analytics operations."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def campaign_analytics(self, request):
        """Get campaign analytics data."""
        try:
            campaign_id = request.query_params.get('campaign_id')
            date_range = {
                'start_date': request.query_params.get('start_date'),
                'end_date': request.query_params.get('end_date')
            }
            metrics = request.query_params.getlist('metrics')
            dimensions = request.query_params.getlist('dimensions')
            
            if not campaign_id:
                return Response(
                    {'error': 'campaign_id parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Filter out None values from date_range
            date_range = {k: v for k, v in date_range.items() if v is not None}
            
            analytics_data = AnalyticsService.get_campaign_analytics(
                campaign_id,
                date_range if date_range else None,
                metrics if metrics else None,
                dimensions if dimensions else None
            )
            return Response(analytics_data)
            
        except AnalyticsNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except AnalyticsServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting campaign analytics: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def creative_analytics(self, request):
        """Get creative analytics data."""
        try:
            creative_id = request.query_params.get('creative_id')
            date_range = {
                'start_date': request.query_params.get('start_date'),
                'end_date': request.query_params.get('end_date')
            }
            metrics = request.query_params.getlist('metrics')
            dimensions = request.query_params.getlist('dimensions')
            
            if not creative_id:
                return Response(
                    {'error': 'creative_id parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Filter out None values from date_range
            date_range = {k: v for k, v in date_range.items() if v is not None}
            
            analytics_data = AnalyticsService.get_creative_analytics(
                creative_id,
                date_range if date_range else None,
                metrics if metrics else None,
                dimensions if dimensions else None
            )
            return Response(analytics_data)
            
        except AnalyticsNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except AnalyticsServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting creative analytics: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def advertiser_analytics(self, request):
        """Get advertiser analytics data."""
        try:
            advertiser_id = request.query_params.get('advertiser_id')
            date_range = {
                'start_date': request.query_params.get('start_date'),
                'end_date': request.query_params.get('end_date')
            }
            metrics = request.query_params.getlist('metrics')
            dimensions = request.query_params.getlist('dimensions')
            
            if not advertiser_id:
                return Response(
                    {'error': 'advertiser_id parameter is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Filter out None values from date_range
            date_range = {k: v for k, v in date_range.items() if v is not None}
            
            analytics_data = AnalyticsService.get_advertiser_analytics(
                advertiser_id,
                date_range if date_range else None,
                metrics if metrics else None,
                dimensions if dimensions else None
            )
            return Response(analytics_data)
            
        except AnalyticsNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except AnalyticsServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting advertiser analytics: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def real_time_metrics(self, request):
        """Get real-time metrics for entity."""
        try:
            entity_type = request.query_params.get('entity_type')
            entity_id = request.query_params.get('entity_id')
            
            if not entity_type or not entity_id:
                return Response(
                    {'error': 'entity_type and entity_id parameters are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            metrics_data = AnalyticsService.get_real_time_metrics(entity_type, UUID(entity_id))
            return Response(metrics_data)
            
        except AnalyticsNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except AnalyticsServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting real-time metrics: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def calculate_attribution(self, request):
        """Calculate attribution for conversion."""
        try:
            conversion_id = request.data.get('conversion_id')
            attribution_model = request.data.get('attribution_model', 'last_click')
            
            if not conversion_id:
                return Response(
                    {'error': 'conversion_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            attribution_data = AnalyticsService.calculate_attribution(
                UUID(conversion_id),
                attribution_model
            )
            return Response(attribution_data)
            
        except AnalyticsNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except AnalyticsServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error calculating attribution: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ReportingViewSet(viewsets.ModelViewSet):
    """ViewSet for managing reporting operations."""
    
    queryset = AnalyticsReport.objects.all()
    serializer_class = AnalyticsReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['advertiser', 'campaign', 'report_type', 'is_scheduled']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name', 'last_run']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # If user is not superuser, only show reports from their advertiser
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'advertiser'):
                queryset = queryset.filter(advertiser=self.request.user.advertiser)
            else:
                # Other users see no reports
                queryset = queryset.none()
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new report."""
        try:
            # Add advertiser ID to data if not present
            if hasattr(request.user, 'advertiser'):
                request.data['advertiser'] = request.user.advertiser.id
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            report = ReportingService.create_report(
                serializer.validated_data,
                created_by=request.user
            )
            
            response_serializer = AnalyticsReportDetailSerializer(report)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except AnalyticsServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating report: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        """Generate report."""
        try:
            report = self.get_object()
            
            success = ReportingService.generate_report(
                report.id,
                generated_by=request.user
            )
            
            if success:
                response_serializer = AnalyticsReportDetailSerializer(report)
                return Response(response_serializer.data)
            else:
                return Response(
                    {'error': 'Failed to generate report'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except AnalyticsNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get report generation history."""
        try:
            report = self.get_object()
            history = ReportingService.get_report_history(report.id)
            
            return Response({'history': history})
            
        except Exception as e:
            logger.error(f"Error getting report history: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def schedule(self, request, pk=None):
        """Schedule report generation."""
        try:
            report = self.get_object()
            schedule_data = request.data
            
            success = ReportingService.schedule_report(
                report.id,
                schedule_data,
                scheduled_by=request.user
            )
            
            if success:
                response_serializer = AnalyticsReportDetailSerializer(report)
                return Response(response_serializer.data)
            else:
                return Response(
                    {'error': 'Failed to schedule report'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Error scheduling report: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DashboardViewSet(viewsets.ModelViewSet):
    """ViewSet for managing dashboard operations."""
    
    queryset = AnalyticsDashboard.objects.all()
    serializer_class = AnalyticsDashboardSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['advertiser', 'layout_type', 'theme', 'is_active', 'is_public']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # If user is not superuser, only show dashboards from their advertiser
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'advertiser'):
                queryset = queryset.filter(advertiser=self.request.user.advertiser)
            else:
                # Other users see no dashboards
                queryset = queryset.none()
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new dashboard."""
        try:
            # Add advertiser ID to data if not present
            if hasattr(request.user, 'advertiser'):
                request.data['advertiser'] = request.user.advertiser.id
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            dashboard = DashboardService.create_dashboard(
                serializer.validated_data,
                created_by=request.user
            )
            
            response_serializer = AnalyticsDashboardDetailSerializer(dashboard)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except AnalyticsServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating dashboard: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, *args, **kwargs):
        """Update dashboard."""
        try:
            dashboard = self.get_object()
            
            serializer = self.get_serializer(dashboard, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            updated_dashboard = DashboardService.update_dashboard(
                dashboard.id,
                serializer.validated_data,
                updated_by=request.user
            )
            
            response_serializer = AnalyticsDashboardDetailSerializer(updated_dashboard)
            return Response(response_serializer.data)
            
        except AnalyticsNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except AnalyticsServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating dashboard: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def data(self, request, pk=None):
        """Get dashboard data with widgets populated."""
        try:
            dashboard = self.get_object()
            
            filters = {}
            for key, value in request.query_params.items():
                if key not in ['page', 'page_size']:
                    filters[key] = value
            
            dashboard_data = DashboardService.get_dashboard_data(dashboard.id, filters)
            return Response(dashboard_data)
            
        except Exception as e:
            logger.error(f"Error getting dashboard data: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Share dashboard with other users."""
        try:
            dashboard = self.get_object()
            sharing_data = request.data
            
            success = DashboardService.share_dashboard(
                dashboard.id,
                sharing_data,
                shared_by=request.user
            )
            
            if success:
                response_serializer = AnalyticsDashboardDetailSerializer(dashboard)
                return Response(response_serializer.data)
            else:
                return Response(
                    {'error': 'Failed to share dashboard'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Error sharing dashboard: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MetricsViewSet(viewsets.ViewSet):
    """ViewSet for managing metrics operations."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """Calculate specific metric for entity."""
        try:
            entity_type = request.data.get('entity_type')
            entity_id = request.data.get('entity_id')
            metric_name = request.data.get('metric_name')
            date_range = request.data.get('date_range', {})
            
            if not entity_type or not entity_id or not metric_name:
                return Response(
                    {'error': 'entity_type, entity_id, and metric_name are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            metric_data = MetricsService.calculate_metric(
                entity_type,
                UUID(entity_id),
                metric_name,
                date_range if date_range else None
            )
            return Response(metric_data)
            
        except AnalyticsNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except AnalyticsServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error calculating metric: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def definitions(self, request):
        """Get definitions for all available metrics."""
        try:
            definitions = MetricsService.get_metric_definitions()
            return Response(definitions)
            
        except Exception as e:
            logger.error(f"Error getting metric definitions: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VisualizationViewSet(viewsets.ViewSet):
    """ViewSet for managing data visualization operations."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def create_visualization(self, request):
        """Create a new data visualization."""
        try:
            visualization = VisualizationService.create_visualization(
                request.data,
                created_by=request.user
            )
            return Response(visualization, status=status.HTTP_201_CREATED)
            
        except AnalyticsServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating visualization: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def generate_chart_data(self, request):
        """Generate data for chart visualization."""
        try:
            data_config = request.data.get('data_config', {})
            
            if not data_config:
                return Response(
                    {'error': 'data_config is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            chart_data = VisualizationService.generate_chart_data(data_config)
            return Response(chart_data)
            
        except AnalyticsServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error generating chart data: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def chart_types(self, request):
        """Get available chart types."""
        try:
            chart_types = VisualizationService.get_chart_types()
            return Response({'chart_types': chart_types})
            
        except Exception as e:
            logger.error(f"Error getting chart types: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
