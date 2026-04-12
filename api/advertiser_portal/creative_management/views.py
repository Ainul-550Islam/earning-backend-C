"""
Creative Management Views

This module contains Django REST Framework ViewSets for managing
creatives, approval workflow, optimization, and analytics.
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
from rest_framework.parsers import MultiPartParser, FormParser

from ..database_models.creative_model import Creative, CreativeAsset, CreativeApprovalLog
from ..database_models.analytics_model import AnalyticsReport
from .services import (
    CreativeService, CreativeApprovalService, CreativeOptimizationService,
    CreativeAnalyticsService, CreativeAssetService
)
from .serializers import *
from ..exceptions import *
from ..utils import *


class CreativeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing creatives."""
    
    queryset = Creative.objects.filter(is_deleted=False)
    serializer_class = CreativeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'creative_type', 'approval_status', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name', 'status', 'quality_score']
    ordering = ['-created_at']
    parser_classes = [MultiPartParser, FormParser]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return CreativeCreateSerializer
        elif self.action == 'update':
            return CreativeUpdateSerializer
        elif self.action in ['retrieve', 'list']:
            return CreativeDetailSerializer
        return self.serializer_class
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # If user is not superuser, only show creatives from their advertiser
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'advertiser'):
                queryset = queryset.filter(advertiser=self.request.user.advertiser)
            else:
                # Other users see no creatives
                queryset = queryset.none()
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new creative."""
        try:
            # Add advertiser ID to data if not present
            if hasattr(request.user, 'advertiser'):
                request.data['advertiser'] = request.user.advertiser.id
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            creative = CreativeService.create_creative(
                serializer.validated_data,
                created_by=request.user
            )
            
            response_serializer = CreativeDetailSerializer(creative)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except CreativeServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating creative: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, *args, **kwargs):
        """Update creative."""
        try:
            creative = self.get_object()
            
            serializer = self.get_serializer(creative, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            updated_creative = CreativeService.update_creative(
                creative.id,
                serializer.validated_data,
                updated_by=request.user
            )
            
            response_serializer = CreativeDetailSerializer(updated_creative)
            return Response(response_serializer.data)
            
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CreativeServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating creative: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def destroy(self, request, *args, **kwargs):
        """Delete creative."""
        try:
            creative = self.get_object()
            
            success = CreativeService.delete_creative(
                creative.id,
                deleted_by=request.user
            )
            
            if success:
                return Response(status=status.HTTP_204_NO_CONTENT)
            else:
                return Response(
                    {'error': 'Failed to delete creative'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CreativeServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error deleting creative: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate creative."""
        try:
            creative = self.get_object()
            
            success = CreativeService.activate_creative(
                creative.id,
                activated_by=request.user
            )
            
            if success:
                return Response({'message': 'Creative activated successfully'})
            else:
                return Response(
                    {'error': 'Failed to activate creative'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error activating creative: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause creative."""
        try:
            creative = self.get_object()
            
            success = CreativeService.pause_creative(
                creative.id,
                paused_by=request.user
            )
            
            if success:
                return Response({'message': 'Creative paused successfully'})
            else:
                return Response(
                    {'error': 'Failed to pause creative'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error pausing creative: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate creative."""
        try:
            creative = self.get_object()
            
            new_name = request.data.get('name')
            duplicated_creative = CreativeService.duplicate_creative(
                creative.id,
                new_name,
                duplicated_by=request.user
            )
            
            response_serializer = CreativeDetailSerializer(duplicated_creative)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CreativeServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error duplicating creative: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get creative performance metrics."""
        try:
            creative = self.get_object()
            performance_data = CreativeService.get_creative_performance(creative.id)
            
            return Response(performance_data)
            
        except CreativeServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting creative performance: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def assets(self, request, pk=None):
        """Get creative assets."""
        try:
            creative = self.get_object()
            assets = CreativeAssetService.get_assets(creative.id)
            
            serializer = CreativeAssetSerializer(assets, many=True)
            return Response(serializer.data)
            
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error getting creative assets: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def add_asset(self, request, pk=None):
        """Add asset to creative."""
        try:
            creative = self.get_object()
            
            asset_data = {
                'asset_type': request.data.get('asset_type'),
                'asset_path': request.data.get('asset_path'),
                'asset_name': request.data.get('asset_name'),
                'asset_size': request.data.get('asset_size', 0),
                'mime_type': request.data.get('mime_type'),
                'asset_url': request.data.get('asset_url')
            }
            
            asset = CreativeAssetService.add_asset(
                creative.id,
                asset_data,
                created_by=request.user
            )
            
            serializer = CreativeAssetSerializer(asset)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CreativeServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error adding creative asset: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CreativeApprovalViewSet(viewsets.ViewSet):
    """ViewSet for creative approval workflow."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def submit_for_approval(self, request):
        """Submit creative for approval."""
        try:
            creative_id = request.data.get('creative_id')
            
            if not creative_id:
                return Response(
                    {'error': 'creative_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            success = CreativeApprovalService.submit_for_approval(
                creative_id,
                submitted_by=request.user
            )
            
            if success:
                return Response({'message': 'Creative submitted for approval'})
            else:
                return Response(
                    {'error': 'Failed to submit creative for approval'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error submitting creative for approval: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def approve(self, request):
        """Approve creative."""
        try:
            creative_id = request.data.get('creative_id')
            notes = request.data.get('notes', '')
            
            if not creative_id:
                return Response(
                    {'error': 'creative_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            success = CreativeApprovalService.approve_creative(
                creative_id,
                notes,
                approved_by=request.user
            )
            
            if success:
                return Response({'message': 'Creative approved successfully'})
            else:
                return Response(
                    {'error': 'Failed to approve creative'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error approving creative: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def reject(self, request):
        """Reject creative."""
        try:
            creative_id = request.data.get('creative_id')
            rejection_reason = request.data.get('rejection_reason', '')
            
            if not creative_id:
                return Response(
                    {'error': 'creative_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            success = CreativeApprovalService.reject_creative(
                creative_id,
                rejection_reason,
                rejected_by=request.user
            )
            
            if success:
                return Response({'message': 'Creative rejected successfully'})
            else:
                return Response(
                    {'error': 'Failed to reject creative'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error rejecting creative: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def approval_history(self, request):
        """Get approval history for creative."""
        try:
            creative_id = request.query_params.get('creative_id')
            
            if not creative_id:
                return Response(
                    {'error': 'creative_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            history = CreativeApprovalService.get_approval_history(creative_id)
            return Response({'history': history})
            
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error getting approval history: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CreativeOptimizationViewSet(viewsets.ViewSet):
    """ViewSet for creative optimization operations."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def optimize(self, request):
        """Optimize creative."""
        try:
            creative_id = request.data.get('creative_id')
            optimization_type = request.data.get('type', 'auto')
            
            if not creative_id:
                return Response(
                    {'error': 'creative_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            success = CreativeOptimizationService.optimize_creative(
                creative_id,
                optimization_type,
                optimized_by=request.user
            )
            
            if success:
                return Response({'message': 'Creative optimized successfully'})
            else:
                return Response(
                    {'error': 'Failed to optimize creative'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error optimizing creative: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def optimization_report(self, request):
        """Get optimization report for creative."""
        try:
            creative_id = request.query_params.get('creative_id')
            
            if not creative_id:
                return Response(
                    {'error': 'creative_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            report = CreativeOptimizationService.get_optimization_report(creative_id)
            return Response(report)
            
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CreativeServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting optimization report: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CreativeAnalyticsViewSet(viewsets.ViewSet):
    """ViewSet for creative analytics operations."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get creative analytics data."""
        try:
            creative_id = request.query_params.get('creative_id')
            date_range = {
                'start_date': request.query_params.get('start_date'),
                'end_date': request.query_params.get('end_date')
            }
            
            if not creative_id:
                return Response(
                    {'error': 'creative_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Filter out None values from date_range
            date_range = {k: v for k, v in date_range.items() if v is not None}
            
            analytics_data = CreativeAnalyticsService.get_analytics(
                creative_id,
                date_range if date_range else None
            )
            return Response(analytics_data)
            
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CreativeServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting analytics: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def generate_report(self, request):
        """Generate creative report."""
        try:
            creative_id = request.data.get('creative_id')
            report_type = request.data.get('type', 'performance')
            date_range = {
                'start_date': request.data.get('start_date'),
                'end_date': request.data.get('end_date')
            }
            format_type = request.data.get('format', 'pdf')
            
            if not creative_id:
                return Response(
                    {'error': 'creative_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Filter out None values from date_range
            date_range = {k: v for k, v in date_range.items() if v is not None}
            
            report_file = CreativeAnalyticsService.generate_report(
                creative_id,
                report_type,
                date_range if date_range else None,
                format_type
            )
            
            return Response({
                'message': 'Report generated successfully',
                'file_path': report_file
            })
            
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CreativeServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CreativeAssetViewSet(viewsets.ViewSet):
    """ViewSet for creative asset operations."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def add_asset(self, request):
        """Add asset to creative."""
        try:
            creative_id = request.data.get('creative_id')
            asset_data = {
                'asset_type': request.data.get('asset_type'),
                'asset_path': request.data.get('asset_path'),
                'asset_name': request.data.get('asset_name'),
                'asset_size': request.data.get('asset_size', 0),
                'mime_type': request.data.get('mime_type'),
                'asset_url': request.data.get('asset_url')
            }
            
            if not creative_id:
                return Response(
                    {'error': 'creative_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            asset = CreativeAssetService.add_asset(
                creative_id,
                asset_data,
                created_by=request.user
            )
            
            serializer = CreativeAssetSerializer(asset)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except CreativeServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error adding creative asset: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def remove_asset(self, request):
        """Remove asset from creative."""
        try:
            asset_id = request.data.get('asset_id')
            
            if not asset_id:
                return Response(
                    {'error': 'asset_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            success = CreativeAssetService.remove_asset(
                asset_id,
                removed_by=request.user
            )
            
            if success:
                return Response({'message': 'Asset removed successfully'})
            else:
                return Response(
                    {'error': 'Failed to remove asset'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except CreativeServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error removing creative asset: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def get_assets(self, request):
        """Get all assets for creative."""
        try:
            creative_id = request.query_params.get('creative_id')
            
            if not creative_id:
                return Response(
                    {'error': 'creative_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            assets = CreativeAssetService.get_assets(creative_id)
            serializer = CreativeAssetSerializer(assets, many=True)
            return Response(serializer.data)
            
        except CreativeNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error getting creative assets: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
