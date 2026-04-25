"""
Advertiser Verification ViewSet

ViewSet for advertiser verification management,
including document upload and status tracking.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.files.storage import default_storage
from django.db.models import Q

from ..models.advertiser import Advertiser, AdvertiserVerification
try:
    from ..services import AdvertiserVerificationService
except ImportError:
    AdvertiserVerificationService = None
from ..serializers import AdvertiserVerificationSerializer
from ..permissions import IsOwnerOrReadOnly, IsStaffUser
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class AdvertiserVerificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for advertiser verification management.
    
    Handles document upload, verification status tracking,
    and review workflows.
    """
    
    queryset = AdvertiserVerification.objects.all()
    serializer_class = AdvertiserVerificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all verifications
            return AdvertiserVerification.objects.all()
        else:
            # Advertisers can only see their own verifications
            return AdvertiserVerification.objects.filter(advertiser__user=user)
    
    def create(self, request, *args, **kwargs):
        """
        Create verification document.
        
        Upload verification document for review.
        """
        advertiser = get_object_or_404(Advertiser, user=request.user)
        
        # Check if advertiser is already verified
        if advertiser.verification_status == 'verified':
            return Response(
                {'detail': 'Advertiser is already verified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        document_type = request.data.get('document_type')
        document_file = request.data.get('document')
        
        if not document_type or not document_file:
            return Response(
                {'detail': 'Document type and file are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            verification_service = AdvertiserVerificationService()
            
            # Submit verification document
            verification = verification_service.submit_verification_document(
                advertiser,
                document_type,
                document_file
            )
            
            serializer = self.get_serializer(verification)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error submitting verification document: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Approve verification document.
        
        Only staff members can approve documents.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        verification = self.get_object()
        notes = request.data.get('notes', '')
        
        try:
            verification_service = AdvertiserVerificationService()
            approved_verification = verification_service.approve_verification(
                verification,
                request.user,
                notes
            )
            
            return Response({
                'detail': 'Verification approved successfully',
                'status': approved_verification.status,
                'approved_at': approved_verification.approved_at.isoformat() if approved_verification.approved_at else None
            })
            
        except Exception as e:
            logger.error(f"Error approving verification: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Reject verification document.
        
        Only staff members can reject documents.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        verification = self.get_object()
        reason = request.data.get('reason', '')
        notes = request.data.get('notes', '')
        
        if not reason:
            return Response(
                {'detail': 'Rejection reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            verification_service = AdvertiserVerificationService()
            rejected_verification = verification_service.reject_verification(
                verification,
                request.user,
                reason,
                notes
            )
            
            return Response({
                'detail': 'Verification rejected',
                'status': rejected_verification.status,
                'rejected_at': rejected_verification.rejected_at.isoformat() if rejected_verification.rejected_at else None,
                'rejection_reason': rejected_verification.rejection_reason
            })
            
        except Exception as e:
            logger.error(f"Error rejecting verification: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def request_changes(self, request, pk=None):
        """
        Request changes to verification document.
        
        Only staff members can request changes.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        verification = self.get_object()
        requested_changes = request.data.get('requested_changes', '')
        
        if not requested_changes:
            return Response(
                {'detail': 'Requested changes description is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            verification_service = AdvertiserVerificationService()
            updated_verification = verification_service.request_changes(
                verification,
                request.user,
                requested_changes
            )
            
            return Response({
                'detail': 'Changes requested successfully',
                'status': updated_verification.status,
                'requested_changes': updated_verification.requested_changes
            })
            
        except Exception as e:
            logger.error(f"Error requesting changes: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def resubmit(self, request, pk=None):
        """
        Resubmit verification document after changes.
        
        Advertisers can resubmit their documents.
        """
        verification = self.get_object()
        
        # Check if user owns this verification
        if verification.advertiser.user != request.user:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if document can be resubmitted
        if verification.status not in ['rejected', 'changes_requested']:
            return Response(
                {'detail': 'Document cannot be resubmitted in current status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        document_file = request.data.get('document')
        
        if not document_file:
            return Response(
                {'detail': 'Document file is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            verification_service = AdvertiserVerificationService()
            
            # Delete old document
            if verification.document:
                default_storage.delete(verification.document.name)
            
            # Upload new document
            verification.document = document_file
            verification.status = 'pending_review'
            verification.submitted_at = timezone.now()
            verification.review_notes = None
            verification.approved_at = None
            verification.rejected_at = None
            verification.approved_by = None
            verification.rejected_by = None
            verification.save()
            
            serializer = self.get_serializer(verification)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error resubmitting verification: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """
        Download verification document.
        
        Only staff and document owner can download.
        """
        verification = self.get_object()
        
        # Check permissions
        if not (request.user.is_staff or verification.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not verification.document:
            return Response(
                {'detail': 'Document not available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Get file info
            file_path = verification.document.name
            file_name = file_path.split('/')[-1]
            
            # Check if file exists
            if not default_storage.exists(file_path):
                return Response(
                    {'detail': 'File not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get file content
            file_content = default_storage.open(file_path, 'rb')
            
            # Create response
            response = Response(
                file_content.read(),
                content_type='application/octet-stream'
            )
            response['Content-Disposition'] = f'attachment; filename="{file_name}"'
            response['Content-Length'] = verification.document.size
            
            return response
            
        except Exception as e:
            logger.error(f"Error downloading verification document: {e}")
            return Response(
                {'detail': 'Failed to download document'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['delete'])
    def delete_document(self, request, pk=None):
        """
        Delete verification document.
        
        Only staff can delete documents.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        verification = self.get_object()
        
        if not verification.document:
            return Response(
                {'detail': 'No document to delete'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Delete file
            default_storage.delete(verification.document.name)
            verification.document = None
            verification.status = 'draft'
            verification.save()
            
            return Response({'detail': 'Document deleted successfully'})
            
        except Exception as e:
            logger.error(f"Error deleting verification document: {e}")
            return Response(
                {'detail': 'Failed to delete document'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def required_documents(self, request):
        """
        Get list of required verification documents.
        
        Returns document types and requirements.
        """
        try:
            verification_service = AdvertiserVerificationService()
            required_docs = verification_service.get_required_document_types()
            
            return Response({
                'required_documents': required_docs,
                'description': 'These documents are required for advertiser verification'
            })
            
        except Exception as e:
            logger.error(f"Error getting required documents: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def verification_status(self, request):
        """
        Get current verification status for advertiser.
        """
        try:
            advertiser = get_object_or_404(Advertiser, user=request.user)
            
            verification_service = AdvertiserVerificationService()
            status_info = verification_service.get_verification_status(advertiser)
            
            return Response(status_info)
            
        except Exception as e:
            logger.error(f"Error getting verification status: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def pending_reviews(self, request):
        """
        Get pending verification documents for admin review.
        
        Only staff members can access this endpoint.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            pending_verifications = AdvertiserVerification.objects.filter(
                status='pending_review'
            ).select_related('advertiser', 'advertiser__user').order_by('submitted_at')
            
            serializer = self.get_serializer(pending_verifications, many=True)
            
            return Response({
                'pending_reviews': serializer.data,
                'count': pending_verifications.count()
            })
            
        except Exception as e:
            logger.error(f"Error getting pending reviews: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_approve(self, request):
        """
        Bulk approve multiple verification documents.
        
        Only staff members can perform this action.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        verification_ids = request.data.get('verification_ids', [])
        notes = request.data.get('notes', '')
        
        if not verification_ids:
            return Response(
                {'detail': 'No verification IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            verification_service = AdvertiserVerificationService()
            
            results = {
                'approved': 0,
                'failed': 0,
                'errors': []
            }
            
            for verification_id in verification_ids:
                try:
                    verification = AdvertiserVerification.objects.get(id=verification_id)
                    verification_service.approve_verification(verification, request.user, notes)
                    results['approved'] += 1
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'verification_id': verification_id,
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
        Bulk reject multiple verification documents.
        
        Only staff members can perform this action.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        verification_ids = request.data.get('verification_ids', [])
        reason = request.data.get('reason', '')
        notes = request.data.get('notes', '')
        
        if not verification_ids:
            return Response(
                {'detail': 'No verification IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not reason:
            return Response(
                {'detail': 'Rejection reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            verification_service = AdvertiserVerificationService()
            
            results = {
                'rejected': 0,
                'failed': 0,
                'errors': []
            }
            
            for verification_id in verification_ids:
                try:
                    verification = AdvertiserVerification.objects.get(id=verification_id)
                    verification_service.reject_verification(verification, request.user, reason, notes)
                    results['rejected'] += 1
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'verification_id': verification_id,
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
        status = request.query_params.get('status')
        document_type = request.query_params.get('document_type')
        search = request.query_params.get('search')
        
        if status:
            queryset = queryset.filter(status=status)
        
        if document_type:
            queryset = queryset.filter(document_type=document_type)
        
        if search:
            queryset = queryset.filter(
                Q(advertiser__company_name__icontains=search) |
                Q(document_type__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
