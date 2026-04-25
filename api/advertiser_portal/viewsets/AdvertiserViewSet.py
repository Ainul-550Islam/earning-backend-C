"""
Advertiser ViewSet

Comprehensive ViewSet for advertiser management,
including CRUD operations, verification, and suspension.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q

from ..models.advertiser import Advertiser, AdvertiserProfile, AdvertiserVerification, AdvertiserAgreement
try:
    from ..services import AdvertiserService
except ImportError:
    AdvertiserService = None
try:
    from ..services import AdvertiserVerificationService
except ImportError:
    AdvertiserVerificationService = None
from ..serializers import AdvertiserSerializer, AdvertiserProfileSerializer, AdvertiserVerificationSerializer
from ..permissions import IsAdvertiserOrReadOnly, IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class AdvertiserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for advertiser management.
    
    Provides CRUD operations, verification workflows,
    and account management functionality.
    """
    
    queryset = Advertiser.objects.all()
    serializer_class = AdvertiserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdvertiserOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all advertisers
            return Advertiser.objects.all()
        else:
            # Advertisers can only see their own account
            return Advertiser.objects.filter(user=user)
    
    def perform_create(self, serializer):
        """Create advertiser with associated user."""
        user = self.request.user
        advertiser_service = AdvertiserService()
        
        # Create advertiser through service
        advertiser = advertiser_service.create_advertiser(user, serializer.validated_data)
        
        # Set the user for the serializer
        serializer.instance = advertiser
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Submit advertiser for verification.
        
        Upload verification documents and initiate review process.
        """
        advertiser = self.get_object()
        
        if advertiser.verification_status == 'verified':
            return Response(
                {'detail': 'Advertiser is already verified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            verification_service = AdvertiserVerificationService()
            
            # Handle document upload
            documents = request.FILES.getlist('documents')
            
            if not documents:
                return Response(
                    {'detail': 'No verification documents provided'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process each document
            for document in documents:
                verification_service.submit_verification_document(
                    advertiser, 
                    document.name.split('.')[-1],  # file extension as document type
                    document
                )
            
            return Response({
                'detail': 'Verification documents submitted successfully',
                'verification_status': advertiser.verification_status
            })
            
        except Exception as e:
            logger.error(f"Error submitting verification: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        """
        Suspend advertiser account.
        
        Only staff members can suspend accounts.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        advertiser = self.get_object()
        reason = request.data.get('reason', 'No reason provided')
        
        try:
            advertiser_service = AdvertiserService()
            suspended_advertiser = advertiser_service.suspend_advertiser(advertiser, reason)
            
            return Response({
                'detail': 'Advertiser suspended successfully',
                'status': suspended_advertiser.status,
                'suspended_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error suspending advertiser: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        """
        Reactivate suspended advertiser account.
        
        Only staff members can reactivate accounts.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        advertiser = self.get_object()
        
        if advertiser.status != 'suspended':
            return Response(
                {'detail': 'Account is not suspended'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            advertiser_service = AdvertiserService()
            reactivated_advertiser = advertiser_service.reactivate_advertiser(advertiser)
            
            return Response({
                'detail': 'Advertiser reactivated successfully',
                'status': reactivated_advertiser.status,
                'reactivated_at': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error reactivating advertiser: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def profile(self, request, pk=None):
        """
        Get advertiser profile information.
        """
        advertiser = self.get_object()
        
        try:
            profile = advertiser.profile
            serializer = AdvertiserProfileSerializer(profile)
            return Response(serializer.data)
        except AdvertiserProfile.DoesNotExist:
            return Response(
                {'detail': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def update_profile(self, request, pk=None):
        """
        Update advertiser profile.
        """
        advertiser = self.get_object()
        
        try:
            profile = advertiser.profile
            serializer = AdvertiserProfileSerializer(
                profile, 
                data=request.data, 
                partial=True
            )
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            else:
                return Response(
                    serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except AdvertiserProfile.DoesNotExist:
            return Response(
                {'detail': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def verification_status(self, request, pk=None):
        """
        Get verification status and documents.
        """
        advertiser = self.get_object()
        
        verifications = AdvertiserVerification.objects.filter(
            advertiser=advertiser
        ).order_by('-submitted_at')
        
        serializer = AdvertiserVerificationSerializer(verifications, many=True)
        
        return Response({
            'verification_status': advertiser.verification_status,
            'verifications': serializer.data,
            'required_documents': verification_service.get_required_documents(advertiser)
        })
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """
        Get advertiser statistics.
        """
        advertiser = self.get_object()
        
        try:
            advertiser_service = AdvertiserService()
            stats = advertiser_service.get_advertiser_stats(advertiser)
            
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Error getting advertiser statistics: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def agreements(self, request, pk=None):
        """
        Get advertiser agreements.
        """
        advertiser = self.get_object()
        
        agreements = AdvertiserAgreement.objects.filter(
            advertiser=advertiser
        ).order_by('-signed_at')
        
        return Response({
            'agreements': [
                {
                    'id': agreement.id,
                    'terms_version': agreement.terms_version,
                    'signed_at': agreement.signed_at.isoformat() if agreement.signed_at else None,
                    'ip_address': agreement.ip_address,
                    'status': 'active' if agreement.is_current else 'expired'
                }
                for agreement in agreements
            ]
        })
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Search advertisers.
        
        Query parameters:
        - q: Search query
        - status: Filter by status
        - verification_status: Filter by verification status
        """
        query = request.query_params.get('q', '')
        status = request.query_params.get('status')
        verification_status = request.query_params.get('verification_status')
        
        advertiser_service = AdvertiserService()
        
        filters = {}
        if status:
            filters['status'] = status
        if verification_status:
            filters['verification_status'] = verification_status
        
        try:
            advertisers = advertiser_service.search_advertisers(query, filters)
            
            # Serialize results
            serializer = self.get_serializer(advertisers, many=True)
            
            return Response({
                'results': serializer.data,
                'count': len(advertisers),
                'query': query,
                'filters': filters
            })
            
        except Exception as e:
            logger.error(f"Error searching advertisers: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def bulk_suspend(self, request):
        """
        Bulk suspend multiple advertisers.
        
        Only staff members can perform this action.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        advertiser_ids = request.data.get('advertiser_ids', [])
        reason = request.data.get('reason', 'Bulk suspension')
        
        if not advertiser_ids:
            return Response(
                {'detail': 'No advertiser IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            advertiser_service = AdvertiserService()
            
            results = {
                'suspended': 0,
                'failed': 0,
                'errors': []
            }
            
            for advertiser_id in advertiser_ids:
                try:
                    advertiser = Advertiser.objects.get(id=advertiser_id)
                    advertiser_service.suspend_advertiser(advertiser, reason)
                    results['suspended'] += 1
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append({
                        'advertiser_id': advertiser_id,
                        'error': str(e)
                    })
            
            return Response(results)
            
        except Exception as e:
            logger.error(f"Error in bulk suspend: {e}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def list(self, request, *args, **kwargs):
        """
        Override list to add filtering and search capabilities.
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply additional filters
        status = request.query_params.get('status')
        verification_status = request.query_params.get('verification_status')
        search = request.query_params.get('search')
        
        if status:
            queryset = queryset.filter(status=status)
        
        if verification_status:
            queryset = queryset.filter(verification_status=verification_status)
        
        if search:
            queryset = queryset.filter(
                Q(company_name__icontains=search) |
                Q(contact_email__icontains=search) |
                Q(website__icontains=search)
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
