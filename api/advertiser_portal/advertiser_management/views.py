"""
Advertiser Management Views

This module contains Django REST Framework ViewSets for managing
advertiser accounts, verification, users, and settings.
"""

from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..database_models.advertiser_model import Advertiser, AdvertiserVerification
from ..database_models.user_model import AdvertiserUser
from ..database_models.billing_model import BillingProfile
from .services import AdvertiserService, AdvertiserVerificationService, AdvertiserUserService, AdvertiserSettingsService
from .serializers import *
from ..exceptions import *
from ..utils import *

User = get_user_model()


class AdvertiserViewSet(viewsets.ModelViewSet):
    """ViewSet for managing advertiser accounts."""

    serializer_class = AdvertiserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        from ..database_models.advertiser_model import Advertiser as _Advertiser
        return _Advertiser.objects.filter(is_deleted=False)
    filterset_fields = ['status', 'is_verified', 'account_type', 'industry']
    search_fields = ['company_name', 'contact_email', 'trade_name']
    ordering_fields = ['created_at', 'company_name', 'status']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return AdvertiserCreateSerializer
        elif self.action == 'update':
            return AdvertiserUpdateSerializer
        elif self.action in ['retrieve', 'list']:
            return AdvertiserDetailSerializer
        return self.serializer_class
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # If user is not superuser, only show advertisers they have access to
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'advertiser'):
                # Advertiser users can only see their own advertiser
                queryset = queryset.filter(id=self.request.user.advertiser.id)
            else:
                # Other users see no advertisers
                queryset = queryset.none()
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new advertiser account."""
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            advertiser = AdvertiserService.create_advertiser(
                serializer.validated_data,
                created_by=request.user
            )
            
            # Return detailed response
            response_serializer = AdvertiserDetailSerializer(advertiser)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except AdvertiserServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating advertiser: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, *args, **kwargs):
        """Update advertiser account."""
        try:
            advertiser = self.get_object()
            
            serializer = self.get_serializer(advertiser, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            updated_advertiser = AdvertiserService.update_advertiser(
                advertiser.id,
                serializer.validated_data,
                updated_by=request.user
            )
            
            response_serializer = AdvertiserDetailSerializer(updated_advertiser)
            return Response(response_serializer.data)
            
        except AdvertiserNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except AdvertiserServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating advertiser: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def destroy(self, request, *args, **kwargs):
        """Delete advertiser account."""
        try:
            advertiser = self.get_object()
            
            success = AdvertiserService.delete_advertiser(
                advertiser.id,
                deleted_by=request.user
            )
            
            if success:
                return Response(status=status.HTTP_204_NO_CONTENT)
            else:
                return Response(
                    {'error': 'Failed to delete advertiser'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except AdvertiserNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except AdvertiserServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error deleting advertiser: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def performance(self, request, pk=None):
        """Get advertiser performance summary."""
        try:
            advertiser = self.get_object()
            performance_data = AdvertiserService.get_advertiser_performance(advertiser.id)
            
            return Response(performance_data)
            
        except AdvertiserServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting advertiser performance: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def add_credit(self, request, pk=None):
        """Add credit to advertiser account."""
        try:
            advertiser = self.get_object()
            
            amount = Decimal(str(request.data.get('amount', 0)))
            credit_type = request.data.get('credit_type', 'payment')
            description = request.data.get('description', '')
            
            success = AdvertiserService.add_credit(
                advertiser.id,
                amount,
                credit_type,
                description,
                created_by=request.user
            )
            
            if success:
                return Response({'message': 'Credit added successfully'})
            else:
                return Response(
                    {'error': 'Failed to add credit'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except AdvertiserServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error adding credit: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def can_create_campaign(self, request, pk=None):
        """Check if advertiser can create campaigns."""
        try:
            advertiser = self.get_object()
            can_create = AdvertiserService.can_create_campaign(advertiser.id)
            
            return Response({
                'can_create_campaign': can_create,
                'current_campaigns': advertiser.total_campaigns,
                'max_campaigns': self._get_max_campaigns(advertiser.account_type)
            })
            
        except Exception as e:
            logger.error(f"Error checking campaign creation permission: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_max_campaigns(self, account_type: str) -> int:
        """Get maximum campaigns for account type."""
        max_campaigns = {
            'individual': 5,
            'business': 50,
            'enterprise': 500,
            'agency': 1000
        }
        return max_campaigns.get(account_type, 50)
    
    @action(detail=True, methods=['get'])
    def billing_profile(self, request, pk=None):
        """Get advertiser billing profile."""
        try:
            advertiser = self.get_object()
            billing_profile = advertiser.get_billing_profile()
            
            if billing_profile:
                serializer = BillingProfileSerializer(billing_profile)
                return Response(serializer.data)
            else:
                return Response(
                    {'error': 'Billing profile not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"Error getting billing profile: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdvertiserVerificationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing advertiser verification."""
    
    queryset = AdvertiserVerification.objects.all()
    serializer_class = AdvertiserVerificationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['verification_type', 'status']
    ordering_fields = ['created_at', 'verification_date']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'advertiser'):
                # Advertiser users can only see their own verifications
                queryset = queryset.filter(advertiser=self.request.user.advertiser)
            else:
                # Other users see no verifications
                queryset = queryset.none()
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def send_verification(self, request):
        """Send verification email to advertiser."""
        try:
            advertiser_id = request.data.get('advertiser_id')
            if not advertiser_id:
                return Response(
                    {'error': 'advertiser_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            advertiser = AdvertiserService.get_advertiser(advertiser_id)
            success = AdvertiserVerificationService.send_verification_email(advertiser)
            
            if success:
                return Response({'message': 'Verification email sent'})
            else:
                return Response(
                    {'error': 'Failed to send verification email'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except AdvertiserNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error sending verification email: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """Verify advertiser account."""
        try:
            advertiser_id = request.data.get('advertiser_id')
            token = request.data.get('token')
            
            if not advertiser_id or not token:
                return Response(
                    {'error': 'advertiser_id and token are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            success = AdvertiserVerificationService.verify_advertiser(
                advertiser_id,
                token,
                verified_by=request.user
            )
            
            if success:
                return Response({'message': 'Advertiser verified successfully'})
            else:
                return Response(
                    {'error': 'Invalid or expired verification token'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except AdvertiserNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error verifying advertiser: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def submit_documents(self, request):
        """Submit verification documents."""
        try:
            advertiser_id = request.data.get('advertiser_id')
            documents = request.data.get('documents', [])
            
            if not advertiser_id or not documents:
                return Response(
                    {'error': 'advertiser_id and documents are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            verification = AdvertiserVerificationService.submit_verification_documents(
                advertiser_id,
                documents,
                submitted_by=request.user
            )
            
            serializer = self.get_serializer(verification)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except AdvertiserNotFoundError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        except AdvertiserServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error submitting verification documents: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        """Review verification request."""
        try:
            verification = self.get_object()
            
            status = request.data.get('status')
            notes = request.data.get('notes', '')
            
            if not status:
                return Response(
                    {'error': 'status is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            success = AdvertiserVerificationService.review_verification(
                verification.id,
                status,
                notes,
                reviewed_by=request.user
            )
            
            if success:
                serializer = self.get_serializer(verification)
                return Response(serializer.data)
            else:
                return Response(
                    {'error': 'Failed to review verification'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Error reviewing verification: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdvertiserUserViewSet(viewsets.ModelViewSet):
    """ViewSet for managing advertiser users."""
    
    queryset = AdvertiserUser.objects.all()
    serializer_class = AdvertiserUserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['role', 'is_active', 'is_verified']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['created_at', 'username', 'last_login']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        if not self.request.user.is_superuser:
            if hasattr(self.request.user, 'advertiser'):
                # Advertiser users can only see users from their advertiser
                queryset = queryset.filter(advertiser=self.request.user.advertiser)
            else:
                # Other users see no users
                queryset = queryset.none()
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        """Create a new user for advertiser."""
        try:
            # Add advertiser ID to data if not present
            if hasattr(request.user, 'advertiser'):
                request.data['advertiser'] = request.user.advertiser.id
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            user = AdvertiserUserService.create_user(
                serializer.validated_data,
                created_by=request.user
            )
            
            response_serializer = self.get_serializer(user)
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
            
        except AdvertiserServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_permissions(self, request, pk=None):
        """Update user permissions."""
        try:
            user = self.get_object()
            
            permissions = request.data.get('permissions', [])
            
            success = AdvertiserUserService.update_user_permissions(
                user.id,
                permissions,
                updated_by=request.user
            )
            
            if success:
                return Response({'message': 'Permissions updated successfully'})
            else:
                return Response(
                    {'error': 'Failed to update permissions'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Error updating user permissions: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate user account."""
        try:
            user = self.get_object()
            
            success = AdvertiserUserService.deactivate_user(
                user.id,
                deactivated_by=request.user
            )
            
            if success:
                return Response({'message': 'User deactivated successfully'})
            else:
                return Response(
                    {'error': 'Failed to deactivate user'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Error deactivating user: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def activity_log(self, request, pk=None):
        """Get user activity log."""
        try:
            user = self.get_object()
            
            # Get recent activity logs
            from ..database_models.user_model import UserActivityLog
            logs = UserActivityLog.objects.filter(
                user=user
            ).order_by('-created_at')[:50]
            
            serializer = UserActivityLogSerializer(logs, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error getting user activity log: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdvertiserSettingsViewSet(viewsets.ViewSet):
    """ViewSet for managing advertiser settings."""
    
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def get_settings(self, request):
        """Get all settings for advertiser."""
        try:
            if not hasattr(request.user, 'advertiser'):
                return Response(
                    {'error': 'User is not associated with an advertiser'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            settings = AdvertiserSettingsService.get_settings(request.user.advertiser.id)
            return Response(settings)
            
        except AdvertiserServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error getting settings: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def update_settings(self, request):
        """Update advertiser settings."""
        try:
            if not hasattr(request.user, 'advertiser'):
                return Response(
                    {'error': 'User is not associated with an advertiser'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            settings = request.data.get('settings', {})
            
            success = AdvertiserSettingsService.update_settings(
                request.user.advertiser.id,
                settings,
                updated_by=request.user
            )
            
            if success:
                return Response({'message': 'Settings updated successfully'})
            else:
                return Response(
                    {'error': 'Failed to update settings'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except AdvertiserServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating settings: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def reset_settings(self, request):
        """Reset advertiser settings to defaults."""
        try:
            if not hasattr(request.user, 'advertiser'):
                return Response(
                    {'error': 'User is not associated with an advertiser'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            success = AdvertiserSettingsService.reset_settings(
                request.user.advertiser.id,
                reset_by=request.user
            )
            
            if success:
                return Response({'message': 'Settings reset successfully'})
            else:
                return Response(
                    {'error': 'Failed to reset settings'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except AdvertiserServiceError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error resetting settings: {str(e)}")
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
