"""
Branding Viewsets

This module contains viewsets for branding-related models including
TenantBranding, TenantDomain, TenantEmail, and TenantSocialLink.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from ..models.branding import TenantBranding, TenantDomain, TenantEmail, TenantSocialLink
from ..serializers.branding import (
    TenantBrandingSerializer, TenantDomainSerializer, TenantDomainCreateSerializer,
    TenantEmailSerializer, TenantEmailUpdateSerializer, TenantSocialLinkSerializer,
    TenantSocialLinkCreateSerializer
)
from ..services import BrandingService, DomainService


class TenantBrandingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant branding.
    """
    serializer_class = TenantBrandingSerializer
    queryset = TenantBranding.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant']
    ordering = ['-created_at']
    parser_classes = [MultiPartParser, FormParser]
    
    def get_queryset(self):
        """Filter queryset to tenant's branding."""
        if self.request.user.is_superuser:
            return TenantBranding.objects.all()
        return TenantBranding.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def upload_logo(self, request, pk=None):
        """Upload logo for tenant branding."""
        branding = self.get_object()
        logo_file = request.FILES.get('logo')
        logo_type = request.data.get('logo_type', 'main')
        
        if not logo_file:
            return Response(
                {'error': 'Logo file is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = BrandingService.upload_logo(
            branding.tenant, logo_file, logo_type, request.user
        )
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def remove_logo(self, request, pk=None):
        """Remove logo from tenant branding."""
        branding = self.get_object()
        logo_type = request.data.get('logo_type', 'main')
        
        result = BrandingService.remove_logo(
            branding.tenant, logo_type, request.user
        )
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def reset_colors(self, request, pk=None):
        """Reset colors to default."""
        branding = self.get_object()
        
        # Reset to default colors
        branding.primary_color = '#007bff'
        branding.secondary_color = '#6c757d'
        branding.accent_color = '#28a745'
        branding.background_color = '#ffffff'
        branding.text_color = '#212529'
        branding.save()
        
        return Response({'message': 'Colors reset to defaults'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def preview_theme(self, request, pk=None):
        """Preview theme changes."""
        branding = self.get_object()
        preview_data = request.data
        
        # Apply preview changes without saving
        original_values = {}
        for field, value in preview_data.items():
            if hasattr(branding, field):
                original_values[field] = getattr(branding, field)
                setattr(branding, field, value)
        
        # Get theme data
        theme_data = {
            'color_scheme': branding.get_color_scheme(),
            'typography': branding.get_typography(),
            'ui_settings': branding.get_ui_settings(),
        }
        
        # Restore original values
        for field, value in original_values.items():
            setattr(branding, field, value)
        
        return Response(theme_data, status=status.HTTP_200_OK)


class TenantDomainViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant domains.
    """
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'is_primary', 'is_active', 'dns_status', 'ssl_status']
    search_fields = ['domain', 'subdomain']
    ordering_fields = ['is_primary', 'domain']
    ordering = ['-is_primary', 'domain']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return TenantDomainCreateSerializer
        return TenantDomainSerializer
    
    def get_queryset(self):
        """Filter queryset to tenant's domains."""
        if self.request.user.is_superuser:
            return TenantDomain.objects.all()
        return TenantDomain.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def verify_dns(self, request, pk=None):
        """Verify DNS configuration for domain."""
        domain = self.get_object()
        
        result = DomainService.verify_dns_record(domain, 'TXT', domain.dns_verification_token)
        
        if result['verified']:
            # Update domain status
            domain.dns_status = 'verified'
            domain.dns_verified_at = timezone.now()
            domain.save(update_fields=['dns_status', 'dns_verified_at'])
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def setup_ssl(self, request, pk=None):
        """Setup SSL certificate for domain."""
        domain = self.get_object()
        
        result = DomainService.setup_ssl_letsencrypt(domain)
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def check_ssl(self, request, pk=None):
        """Check SSL certificate status."""
        domain = self.get_object()
        
        result = DomainService.check_ssl_certificate(domain)
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def set_primary(self, request, pk=None):
        """Set domain as primary."""
        domain = self.get_object()
        tenant = domain.tenant
        
        # Remove primary status from other domains
        TenantDomain.objects.filter(tenant=tenant, is_primary=True).update(is_primary=False)
        
        # Set this domain as primary
        domain.is_primary = True
        domain.save(update_fields=['is_primary'])
        
        return Response({'message': 'Domain set as primary'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def health_check(self, request, pk=None):
        """Get comprehensive domain health information."""
        domain = self.get_object()
        
        health = DomainService.get_domain_health(domain)
        return Response(health, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def ssl_monitoring(self, request):
        """Get SSL monitoring data for all domains."""
        if not self.request.user.is_superuser:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        expiring_domains = DomainService.monitor_ssl_expiration()
        
        return Response({
            'total_domains': TenantDomain.objects.filter(is_active=True).count(),
            'expiring_soon': len(expiring_domains),
            'domains': expiring_domains
        }, status=status.HTTP_200_OK)


class TenantEmailViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant email configuration.
    """
    serializer_class = TenantEmailSerializer
    queryset = TenantEmail.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'provider', 'is_verified']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset to tenant's email config."""
        if self.request.user.is_superuser:
            return TenantEmail.objects.all()
        return TenantEmail.objects.filter(tenant__owner=self.request.user)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action in ['update', 'partial_update']:
            return TenantEmailUpdateSerializer
        return TenantEmailSerializer
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Test email configuration connection."""
        email_config = self.get_object()
        
        result = BrandingService.test_email_connection(email_config)
        
        if result['success']:
            email_config.last_test_at = timezone.now()
            email_config.save(update_fields=['last_test_at'])
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def verify_configuration(self, request, pk=None):
        """Verify email configuration."""
        email_config = self.get_object()
        
        result = BrandingService.verify_email_domain(email_config)
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def send_test_email(self, request, pk=None):
        """Send test email."""
        email_config = self.get_object()
        
        # Send test email to tenant owner
        result = BrandingService.send_email(
            email_config.tenant,
            'test_email',
            {'message': 'This is a test email to verify your email configuration.'},
            [email_config.tenant.owner.email],
            'Test Email'
        )
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get email statistics."""
        email_config = self.get_object()
        
        stats = BrandingService.get_email_statistics(email_config.tenant)
        return Response(stats, status=status.HTTP_200_OK)


class TenantSocialLinkViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant social media links.
    """
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'platform', 'is_visible']
    search_fields = ['display_name', 'url']
    ordering_fields = ['sort_order', 'platform']
    ordering = ['sort_order', 'platform']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return TenantSocialLinkCreateSerializer
        return TenantSocialLinkSerializer
    
    def get_queryset(self):
        """Filter queryset to tenant's social links."""
        if self.request.user.is_superuser:
            return TenantSocialLink.objects.all()
        return TenantSocialLink.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def reorder(self, request, pk=None):
        """Reorder social links."""
        social_link = self.get_object()
        new_order = request.data.get('sort_order')
        
        if new_order is None:
            return Response(
                {'error': 'sort_order parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            new_order = int(new_order)
        except ValueError:
            return Response(
                {'error': 'sort_order must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        social_link.sort_order = new_order
        social_link.save(update_fields=['sort_order'])
        
        return Response({'message': 'Social link reordered'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def toggle_visibility(self, request, pk=None):
        """Toggle social link visibility."""
        social_link = self.get_object()
        
        social_link.is_visible = not social_link.is_visible
        social_link.save(update_fields=['is_visible'])
        
        return Response({
            'is_visible': social_link.is_visible,
            'message': f'Social link {"shown" if social_link.is_visible else "hidden"}'
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def platform_icons(self, request):
        """Get available platform icons and colors."""
        from ..models.branding import TenantSocialLink
        
        platforms = TenantSocialLink.PLATFORM_CHOICES
        platform_data = {}
        
        for platform_code, platform_name in platforms:
            # Create a temporary instance to get icon and color
            temp_link = TenantSocialLink(platform=platform_code)
            platform_data[platform_code] = {
                'name': platform_name,
                'icon': temp_link.platform_icon,
                'color': temp_link.platform_color,
            }
        
        return Response(platform_data, status=status.HTTP_200_OK)
