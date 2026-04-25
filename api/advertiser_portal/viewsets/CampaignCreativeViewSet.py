"""
Campaign Creative ViewSet

ViewSet for campaign creative management,
including upload, approval, and management.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.files.storage import default_storage
from django.db.models import Q

from ..models.campaign import AdCampaign, CampaignCreative
from ..serializers import CampaignCreativeSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class CampaignCreativeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for campaign creative management.
    
    Handles creative upload, approval workflow,
    and creative asset management.
    """
    
    queryset = CampaignCreative.objects.all()
    serializer_class = CampaignCreativeSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all creatives
            return CampaignCreative.objects.all()
        else:
            # Advertisers can only see their own creatives
            return CampaignCreative.objects.filter(campaign__advertiser__user=user)
    
    def perform_create(self, serializer):
        """Create creative with associated campaign."""
        campaign_id = serializer.validated_data.get('campaign')
        
        if not campaign_id:
            raise ValueError("Campaign ID is required")
        
        campaign = get_object_or_404(AdCampaign, id=campaign_id)
        
        # Check permissions
        if not (self.request.user.is_staff or campaign.advertiser.user == self.request.user):
            raise PermissionError("Permission denied")
        
        creative = serializer.save()
        # Set the campaign for the serializer
        serializer.instance = creative
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Approve creative.
        
        Only staff members can approve creatives.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        creative = self.get_object()
        
        if creative.status == 'active':
            return Response(
                {'detail': 'Creative is already approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            creative.status = 'active'
            creative.is_approved = True
            creative.rejection_reason = None
            creative.approved_at = timezone.now()
            creative.save()
            
            serializer = self.get_serializer(creative)
            return Response({
                'detail': 'Creative approved successfully',
                'creative': serializer.data
            })
            
        except Exception as e:
            logger.error(f"Error approving creative: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Reject creative.
        
        Only staff members can reject creatives.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        creative = self.get_object()
        reason = request.data.get('reason', '')
        
        if not reason:
            return Response(
                {'detail': 'Rejection reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            creative.status = 'rejected'
            creative.is_approved = False
            creative.rejection_reason = reason
            creative.rejected_at = timezone.now()
            creative.save()
            
            serializer = self.get_serializer(creative)
            return Response({
                'detail': 'Creative rejected',
                'creative': serializer.data,
                'rejection_reason': reason
            })
            
        except Exception as e:
            logger.error(f"Error rejecting creative: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def upload_file(self, request, pk=None):
        """
        Upload creative file.
        
        Upload image, video, or HTML creative file.
        """
        creative = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or creative.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if 'file' not in request.FILES:
            return Response(
                {'detail': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        
        try:
            # Validate file type based on creative type
            if creative.creative_type == 'banner':
                allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
                max_size = 2 * 1024 * 1024  # 2MB
            elif creative.creative_type == 'video':
                allowed_types = ['video/mp4', 'video/webm', 'video/ogg']
                max_size = 10 * 1024 * 1024  # 10MB
            elif creative.creative_type == 'html':
                allowed_types = ['text/html', 'application/x-html']
                max_size = 1 * 1024 * 1024  # 1MB
            else:
                return Response(
                    {'detail': 'Invalid creative type'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if file.content_type not in allowed_types:
                return Response(
                    {'detail': f'Invalid file type. Allowed types: {", ".join(allowed_types)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if file.size > max_size:
                return Response(
                    {'detail': f'File too large. Maximum size is {max_size // (1024*1024)}MB'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Delete old file if exists
            if creative.file:
                default_storage.delete(creative.file.name)
            
            # Save new file
            creative.file = file
            creative.status = 'pending_review'
            creative.is_approved = False
            creative.save()
            
            # Return file URL
            file_url = creative.file.url if creative.file else None
            
            return Response({
                'detail': 'File uploaded successfully',
                'file_url': file_url,
                'status': creative.status
            })
            
        except Exception as e:
            logger.error(f"Error uploading creative file: {e}")
            return Response(
                {'detail': 'Failed to upload file'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['delete'])
    def delete_file(self, request, pk=None):
        """
        Delete creative file.
        """
        creative = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or creative.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Delete file
            if creative.file:
                default_storage.delete(creative.file.name)
                creative.file = None
                creative.status = 'draft'
                creative.save()
            
            return Response({'detail': 'File deleted successfully'})
            
        except Exception as e:
            logger.error(f"Error deleting creative file: {e}")
            return Response(
                {'detail': 'Failed to delete file'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_details(self, request, pk=None):
        """
        Update creative details.
        
        Update name, dimensions, and other properties.
        """
        creative = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or creative.campaign.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Update creative details
            details = request.data.get('details', {})
            
            if 'name' in details:
                creative.name = details['name']
            
            if 'width' in details:
                creative.width = details['width']
            
            if 'height' in details:
                creative.height = details['height']
            
            if 'headline' in details:
                creative.headline = details['headline']
            
            if 'description' in details:
                creative.description = details['description']
            
            if 'cta_text' in details:
                creative.cta_text = details['cta_text']
            
            if 'brand_name' in details:
                creative.brand_name = details['brand_name']
            
            if 'landing_page_url' in details:
                creative.landing_page_url = details['landing_page_url']
            
            creative.save()
            
            serializer = self.get_serializer(creative)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error updating creative details: {e}")
            return Response(
                {'detail': 'Failed to update creative details'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def preview(self, request, pk=None):
        """
        Get creative preview.
        
        Returns preview HTML or thumbnail.
        """
        creative = self.get_object()
        
        try:
            preview_data = {
                'id': creative.id,
                'name': creative.name,
                'creative_type': creative.creative_type,
                'width': creative.width,
                'height': creative.height,
                'headline': creative.headline,
                'description': creative.description,
                'cta_text': creative.cta_text,
                'brand_name': creative.brand_name,
                'status': creative.status,
                'is_approved': creative.is_approved,
            }
            
            # Add file URL if available
            if creative.file:
                preview_data['file_url'] = creative.file.url
                preview_data['file_type'] = creative.file.content_type
            
            # Add preview HTML for HTML creatives
            if creative.creative_type == 'html' and creative.file:
                try:
                    file_content = default_storage.open(creative.file.name, 'r')
                    preview_data['html_content'] = file_content.read()
                    file_content.close()
                except:
                    preview_data['html_content'] = 'Preview not available'
            
            return Response(preview_data)
            
        except Exception as e:
            logger.error(f"Error getting creative preview: {e}")
            return Response(
                {'detail': 'Failed to get preview'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """
        Get creative performance metrics.
        
        Returns impressions, clicks, conversions, etc.
        """
        creative = self.get_object()
        
        try:
            # This would implement actual performance tracking
            # For now, return placeholder data
            performance_data = {
                'creative_id': creative.id,
                'creative_name': creative.name,
                'period_days': 30,
                'impressions': 0,
                'clicks': 0,
                'conversions': 0,
                'ctr': 0.0,
                'conversion_rate': 0.0,
                'spend': 0.0,
                'cpc': 0.0,
                'cpa': 0.0,
            }
            
            return Response(performance_data)
            
        except Exception as e:
            logger.error(f"Error getting creative performance: {e}")
            return Response(
                {'detail': 'Failed to get performance data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Test creative.
        
        Validates creative file and settings.
        """
        creative = self.get_object()
        
        try:
            test_results = {
                'creative_id': creative.id,
                'creative_name': creative.name,
                'tests': {},
                'overall_status': 'passed',
                'errors': [],
                'warnings': [],
            }
            
            # Test file availability
            if creative.file:
                test_results['tests']['file_available'] = {
                    'status': 'passed',
                    'file_url': creative.file.url,
                    'file_size': creative.file.size,
                    'file_type': creative.file.content_type,
                }
            else:
                test_results['tests']['file_available'] = {
                    'status': 'failed',
                    'error': 'No file uploaded'
                }
                test_results['overall_status'] = 'failed'
                test_results['errors'].append('Creative file is missing')
            
            # Test dimensions
            if creative.width and creative.height:
                test_results['tests']['dimensions'] = {
                    'status': 'passed',
                    'width': creative.width,
                    'height': creative.height,
                }
            else:
                test_results['tests']['dimensions'] = {
                    'status': 'warning',
                    'warning': 'Dimensions not specified'
                }
                test_results['warnings'].append('Creative dimensions not specified')
            
            # Test landing page URL
            if creative.landing_page_url:
                test_results['tests']['landing_page'] = {
                    'status': 'passed',
                    'url': creative.landing_page_url,
                }
            else:
                test_results['tests']['landing_page'] = {
                    'status': 'warning',
                    'warning': 'Landing page URL not specified'
                }
                test_results['warnings'].append('Landing page URL not specified')
            
            # Test required fields
            required_fields = ['name', 'creative_type']
            missing_fields = []
            
            for field in required_fields:
                if not getattr(creative, field, None):
                    missing_fields.append(field)
            
            if missing_fields:
                test_results['tests']['required_fields'] = {
                    'status': 'failed',
                    'missing_fields': missing_fields
                }
                test_results['overall_status'] = 'failed'
                test_results['errors'].append(f'Missing required fields: {", ".join(missing_fields)}')
            else:
                test_results['tests']['required_fields'] = {
                    'status': 'passed'
                }
            
            return Response(test_results)
            
        except Exception as e:
            logger.error(f"Error testing creative: {e}")
            return Response(
                {'detail': 'Failed to test creative'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def pending_review(self, request):
        """
        Get creatives pending review.
        
        Only staff members can access this endpoint.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            pending_creatives = CampaignCreative.objects.filter(
                status='pending_review'
            ).select_related('campaign', 'campaign__advertiser').order_by('-created_at')
            
            serializer = self.get_serializer(pending_creatives, many=True)
            
            return Response({
                'pending_creatives': serializer.data,
                'count': pending_creatives.count()
            })
            
        except Exception as e:
            logger.error(f"Error getting pending creatives: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_approve(self, request):
        """
        Bulk approve multiple creatives.
        
        Only staff members can perform this action.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        creative_ids = request.data.get('creative_ids', [])
        
        if not creative_ids:
            return Response(
                {'detail': 'No creative IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            results = {
                'approved': 0,
                'failed': 0,
                'errors': []
            }
            
            for creative_id in creative_ids:
                try:
                    creative = CampaignCreative.objects.get(id=creative_id)
                    creative.status = 'active'
                    creative.is_approved = True
                    creative.rejection_reason = None
                    creative.approved_at = timezone.now()
                    creative.save()
                    results['approved'] += 1
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'creative_id': creative_id,
                        'error': str(e)
                    })
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Error in bulk approve: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_reject(self, request):
        """
        Bulk reject multiple creatives.
        
        Only staff members can perform this action.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        creative_ids = request.data.get('creative_ids', [])
        reason = request.data.get('reason', '')
        
        if not creative_ids:
            return Response(
                {'detail': 'No creative IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not reason:
            return Response(
                {'detail': 'Rejection reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            results = {
                'rejected': 0,
                'failed': 0,
                'errors': []
            }
            
            for creative_id in creative_ids:
                try:
                    creative = CampaignCreative.objects.get(id=creative_id)
                    creative.status = 'rejected'
                    creative.is_approved = False
                    creative.rejection_reason = reason
                    creative.rejected_at = timezone.now()
                    creative.save()
                    results['rejected'] += 1
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'creative_id': creative_id,
                        'error': str(e)
                    })
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Error in bulk reject: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def list(self, request, *args, **kwargs):
        """
        Override list to add filtering capabilities.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply additional filters
        campaign_id = request.query_params.get('campaign_id')
        creative_type = request.query_params.get('creative_type')
        status = request.query_params.get('status')
        is_approved = request.query_params.get('is_approved')
        search = request.query_params.get('search')
        
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        
        if creative_type:
            queryset = queryset.filter(creative_type=creative_type)
        
        if status:
            queryset = queryset.filter(status=status)
        
        if is_approved is not None:
            queryset = queryset.filter(is_approved=is_approved.lower() == 'true')
        
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(headline__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
