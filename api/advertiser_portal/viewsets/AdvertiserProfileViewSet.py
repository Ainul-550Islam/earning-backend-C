"""
Advertiser Profile ViewSet

ViewSet for advertiser profile management,
including profile updates and logo management.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.files.storage import default_storage

from ..models.advertiser import Advertiser, AdvertiserProfile
from ..serializers import AdvertiserProfileSerializer
from ..permissions import IsOwnerOrReadOnly
from ..paginations import StandardResultsSetPagination

import logging
logger = logging.getLogger(__name__)


class AdvertiserProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for advertiser profile management.
    
    Handles profile updates, logo management,
    and company information.
    """
    
    queryset = AdvertiserProfile.objects.all()
    serializer_class = AdvertiserProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter queryset based on user."""
        user = self.request.user
        
        if user.is_staff:
            # Admin can see all profiles
            return AdvertiserProfile.objects.all()
        else:
            # Advertisers can only see their own profile
            return AdvertiserProfile.objects.filter(advertiser__user=user)
    
    def get_object(self):
        """Get profile based on current user or pk."""
        pk = self.kwargs.get('pk')
        
        if pk:
            return get_object_or_404(self.get_queryset(), pk=pk)
        else:
            # Get current user's profile
            try:
                return AdvertiserProfile.objects.get(advertiser__user=self.request.user)
            except AdvertiserProfile.DoesNotExist:
                return None
    
    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        """
        Get or update current user's profile.
        """
        try:
            profile = AdvertiserProfile.objects.get(advertiser__user=request.user)
        except AdvertiserProfile.DoesNotExist:
            return Response(
                {'detail': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if request.method == 'PATCH':
            serializer = self.get_serializer(
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
        else:
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def upload_logo(self, request, pk=None):
        """
        Upload company logo.
        
        Accepts image file and saves it as the company logo.
        """
        profile = self.get_object()
        
        if not profile:
            return Response(
                {'detail': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user has permission
        if not (request.user.is_staff or profile.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if 'logo' not in request.FILES:
            return Response(
                {'detail': 'No logo file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logo_file = request.FILES['logo']
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if logo_file.content_type not in allowed_types:
            return Response(
                {'detail': 'Invalid file type. Allowed types: JPEG, PNG, GIF, WebP'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if logo_file.size > max_size:
            return Response(
                {'detail': 'File too large. Maximum size is 5MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Delete old logo if exists
            if profile.logo:
                default_storage.delete(profile.logo.name)
            
            # Save new logo
            profile.logo = logo_file
            profile.save()
            
            # Return logo URL
            logo_url = profile.logo.url if profile.logo else None
            
            return Response({
                'detail': 'Logo uploaded successfully',
                'logo_url': logo_url
            })
            
        except Exception as e:
            logger.error(f"Error uploading logo: {e}")
            return Response(
                {'detail': 'Failed to upload logo'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['delete'])
    def delete_logo(self, request, pk=None):
        """
        Delete company logo.
        """
        profile = self.get_object()
        
        if not profile:
            return Response(
                {'detail': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user has permission
        if not (request.user.is_staff or profile.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Delete logo file
            if profile.logo:
                default_storage.delete(profile.logo.name)
                profile.logo = None
                profile.save()
            
            return Response({'detail': 'Logo deleted successfully'})
            
        except Exception as e:
            logger.error(f"Error deleting logo: {e}")
            return Response(
                {'detail': 'Failed to delete logo'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_company_info(self, request, pk=None):
        """
        Update company information.
        
        Updates company name, description, industry, etc.
        """
        profile = self.get_object()
        
        if not profile:
            return Response(
                {'detail': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user has permission
        if not (request.user.is_staff or profile.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Update company information
            company_info = request.data.get('company_info', {})
            
            if 'company_name' in company_info:
                profile.company_name = company_info['company_name']
            
            if 'company_description' in company_info:
                profile.company_description = company_info['company_description']
            
            if 'industry' in company_info:
                profile.industry = company_info['industry']
            
            if 'company_size' in company_info:
                profile.company_size = company_info['company_size']
            
            if 'founded_year' in company_info:
                profile.founded_year = company_info['founded_year']
            
            if 'headquarters' in company_info:
                profile.headquarters = company_info['headquarters']
            
            profile.save()
            
            # Return updated profile
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error updating company info: {e}")
            return Response(
                {'detail': 'Failed to update company information'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_contact_info(self, request, pk=None):
        """
        Update contact information.
        
        Updates contact person, phone, address, etc.
        """
        profile = self.get_object()
        
        if not profile:
            return Response(
                {'detail': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user has permission
        if not (request.user.is_staff or profile.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Update contact information
            contact_info = request.data.get('contact_info', {})
            
            if 'contact_person' in contact_info:
                profile.contact_person = contact_info['contact_person']
            
            if 'contact_phone' in contact_info:
                profile.contact_phone = contact_info['contact_phone']
            
            if 'contact_email' in contact_info:
                profile.contact_email = contact_info['contact_email']
            
            if 'address' in contact_info:
                profile.address = contact_info['address']
            
            if 'city' in contact_info:
                profile.city = contact_info['city']
            
            if 'state' in contact_info:
                profile.state = contact_info['state']
            
            if 'country' in contact_info:
                profile.country = contact_info['country']
            
            if 'postal_code' in contact_info:
                profile.postal_code = contact_info['postal_code']
            
            profile.save()
            
            # Return updated profile
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error updating contact info: {e}")
            return Response(
                {'detail': 'Failed to update contact information'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def update_social_links(self, request, pk=None):
        """
        Update social media links.
        
        Updates Facebook, Twitter, LinkedIn, etc.
        """
        profile = self.get_object()
        
        if not profile:
            return Response(
                {'detail': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user has permission
        if not (request.user.is_staff or profile.advertiser.user == request.user):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Update social links
            social_links = request.data.get('social_links', {})
            
            if 'website' in social_links:
                profile.website = social_links['website']
            
            if 'facebook' in social_links:
                profile.facebook = social_links['facebook']
            
            if 'twitter' in social_links:
                profile.twitter = social_links['twitter']
            
            if 'linkedin' in social_links:
                profile.linkedin = social_links['linkedin']
            
            if 'instagram' in social_links:
                profile.instagram = social_links['instagram']
            
            if 'youtube' in social_links:
                profile.youtube = social_links['youtube']
            
            profile.save()
            
            # Return updated profile
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Error updating social links: {e}")
            return Response(
                {'detail': 'Failed to update social links'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def completion_status(self, request, pk=None):
        """
        Get profile completion status.
        
        Returns percentage of completed profile fields
        and missing required fields.
        """
        profile = self.get_object()
        
        if not profile:
            return Response(
                {'detail': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Define required fields
            required_fields = [
                'company_name',
                'company_description',
                'industry',
                'contact_person',
                'contact_email',
                'address',
                'city',
                'country',
            ]
            
            # Define optional fields
            optional_fields = [
                'logo',
                'contact_phone',
                'state',
                'postal_code',
                'website',
                'facebook',
                'twitter',
                'linkedin',
                'instagram',
                'youtube',
                'company_size',
                'founded_year',
                'headquarters',
            ]
            
            # Calculate completion percentage
            completed_required = 0
            completed_optional = 0
            missing_required = []
            
            for field in required_fields:
                value = getattr(profile, field, None)
                if value:
                    completed_required += 1
                else:
                    missing_required.append(field)
            
            for field in optional_fields:
                value = getattr(profile, field, None)
                if value:
                    completed_optional += 1
            
            required_completion = (completed_required / len(required_fields)) * 100
            optional_completion = (completed_optional / len(optional_fields)) * 100
            overall_completion = (required_completion * 0.7) + (optional_completion * 0.3)
            
            return Response({
                'completion_percentage': round(overall_completion, 1),
                'required_completion': round(required_completion, 1),
                'optional_completion': round(optional_completion, 1),
                'missing_required_fields': missing_required,
                'is_complete': len(missing_required) == 0,
                'completed_required_count': completed_required,
                'total_required_count': len(required_fields),
                'completed_optional_count': completed_optional,
                'total_optional_count': len(optional_fields),
            })
            
        except Exception as e:
            logger.error(f"Error calculating completion status: {e}")
            return Response(
                {'detail': 'Failed to calculate completion status'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def public_profile(self, request, pk=None):
        """
        Get public profile information.
        
        Returns only public-safe profile data.
        """
        profile = self.get_object()
        
        if not profile:
            return Response(
                {'detail': 'Profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Return only public information
            public_data = {
                'company_name': profile.company_name,
                'company_description': profile.company_description,
                'industry': profile.industry,
                'logo_url': profile.logo.url if profile.logo else None,
                'website': profile.website,
                'facebook': profile.facebook,
                'twitter': profile.twitter,
                'linkedin': profile.linkedin,
                'instagram': profile.instagram,
                'youtube': profile.youtube,
                'headquarters': profile.headquarters,
                'founded_year': profile.founded_year,
                'company_size': profile.company_size,
            }
            
            return Response(public_data)
            
        except Exception as e:
            logger.error(f"Error getting public profile: {e}")
            return Response(
                {'detail': 'Failed to get public profile'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
