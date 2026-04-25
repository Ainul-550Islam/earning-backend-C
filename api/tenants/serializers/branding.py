"""
Branding Serializers

This module contains serializers for branding-related models including
TenantBranding, TenantDomain, TenantEmail, and TenantSocialLink.
"""

from rest_framework import serializers
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import URLValidator
from ..models.branding import TenantBranding, TenantDomain, TenantEmail, TenantSocialLink


class TenantBrandingSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantBranding model.
    """
    logo_url = serializers.SerializerMethodField()
    favicon_url = serializers.SerializerMethodField()
    color_scheme = serializers.SerializerMethodField()
    typography = serializers.SerializerMethodField()
    ui_settings = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantBranding
        fields = [
            'id', 'tenant', 'logo', 'logo_url', 'logo_dark', 'favicon',
            'favicon_url', 'app_store_icon', 'splash_screen', 'primary_color',
            'secondary_color', 'accent_color', 'background_color', 'text_color',
            'font_family', 'font_family_heading', 'font_size_base',
            'button_radius', 'card_radius', 'border_radius', 'email_header_color',
            'email_footer_text', 'email_logo', 'app_name', 'app_short_name',
            'app_description', 'website_url', 'support_url', 'privacy_policy_url',
            'terms_of_service_url', 'custom_css', 'custom_js', 'meta_title',
            'meta_description', 'meta_keywords', 'color_scheme', 'typography',
            'ui_settings', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']
    
    def get_logo_url(self, obj):
        """Get logo URL."""
        return obj.logo_url
    
    def get_favicon_url(self, obj):
        """Get favicon URL."""
        return obj.favicon_url
    
    def get_color_scheme(self, obj):
        """Get color scheme."""
        return obj.get_color_scheme()
    
    def get_typography(self, obj):
        """Get typography settings."""
        return obj.get_typography()
    
    def get_ui_settings(self, obj):
        """Get UI settings."""
        return obj.get_ui_settings()
    
    def validate(self, attrs):
        """Validate branding data."""
        # Validate color codes
        color_fields = [
            'primary_color', 'secondary_color', 'accent_color',
            'background_color', 'text_color', 'email_header_color'
        ]
        
        for field in color_fields:
            if field in attrs and attrs[field]:
                color = attrs[field]
                if not color.startswith('#'):
                    color = f'#{color}'
                if len(color) != 7 or not all(c in '0123456789abcdefABCDEF' for c in color[1:]):
                    raise serializers.ValidationError(f'Invalid color format for {field}.')
        
        # Validate URLs
        url_fields = ['website_url', 'support_url', 'privacy_policy_url', 'terms_of_service_url']
        validator = URLValidator()
        
        for field in url_fields:
            if field in attrs and attrs[field]:
                try:
                    validator(attrs[field])
                except:
                    raise serializers.ValidationError(f'Invalid URL format for {field}.')
        
        # Validate font size
        if 'font_size_base' in attrs:
            font_size = attrs['font_size_base']
            if not isinstance(font_size, str) or not font_size.endswith('px'):
                raise serializers.ValidationError('Font size must end with "px" (e.g., "16px").')
        
        # Validate radius values
        radius_fields = ['button_radius', 'card_radius', 'border_radius']
        for field in radius_fields:
            if field in attrs and attrs[field]:
                radius = attrs[field]
                if not isinstance(radius, str) or not radius.endswith('px'):
                    raise serializers.ValidationError(f'{field} must end with "px" (e.g., "6px").')
        
        return attrs


class TenantDomainSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantDomain model.
    """
    full_domain = serializers.SerializerMethodField()
    is_ssl_valid = serializers.SerializerMethodField()
    days_until_ssl_expiry = serializers.SerializerMethodField()
    dns_status_display = serializers.SerializerMethodField()
    ssl_status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantDomain
        fields = [
            'id', 'tenant', 'domain', 'subdomain', 'full_domain', 'is_primary',
            'is_active', 'dns_status', 'dns_status_display', 'dns_verified_at',
            'dns_verification_token', 'ssl_status', 'ssl_status_display',
            'ssl_expires_at', 'is_ssl_valid', 'days_until_ssl_expiry',
            'ssl_certificate', 'ssl_private_key', 'ssl_auto_renew',
            'www_redirect', 'force_https', 'google_analytics_id',
            'facebook_pixel_id', 'allowed_ips', 'require_https',
            'custom_headers', 'auth_type', 'auth_token', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'dns_verified_at', 'created_at', 'updated_at'
        ]
    
    def get_full_domain(self, obj):
        """Get full domain including subdomain."""
        return obj.full_domain
    
    def get_is_ssl_valid(self, obj):
        """Check if SSL certificate is valid."""
        return obj.is_ssl_valid
    
    def get_days_until_ssl_expiry(self, obj):
        """Get days until SSL certificate expires."""
        return obj.days_until_ssl_expiry
    
    def get_dns_status_display(self, obj):
        """Get DNS status display name."""
        return obj.get_dns_status_display()
    
    def get_ssl_status_display(self, obj):
        """Get SSL status display name."""
        return obj.get_ssl_status_display()
    
    def validate(self, attrs):
        """Validate domain data."""
        # Validate domain format
        domain = attrs.get('domain')
        if domain:
            import re
            domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
            if not re.match(domain_pattern, domain):
                raise serializers.ValidationError('Invalid domain format.')
        
        # Validate analytics IDs
        ga_id = attrs.get('google_analytics_id')
        if ga_id:
            import re
            if not re.match(r'^[UA|G]-\w+-\d+$', ga_id):
                raise serializers.ValidationError('Invalid Google Analytics ID format.')
        
        fb_id = attrs.get('facebook_pixel_id')
        if fb_id:
            if not re.match(r'^\d+$', fb_id):
                raise serializers.ValidationError('Invalid Facebook Pixel ID format.')
        
        return attrs


class TenantDomainCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new tenant domains.
    """
    class Meta:
        model = TenantDomain
        fields = [
            'domain', 'subdomain', 'is_primary', 'is_active', 'www_redirect',
            'force_https', 'google_analytics_id', 'facebook_pixel_id',
            'allowed_ips', 'require_https', 'custom_headers', 'auth_type',
            'auth_token', 'metadata'
        ]
    
    def validate_domain(self, value):
        """Validate domain uniqueness."""
        if TenantDomain.objects.filter(domain=value).exists():
            raise serializers.ValidationError("Domain is already in use.")
        return value


class TenantEmailSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantEmail model.
    """
    provider_display = serializers.SerializerMethodField()
    auth_type_display = serializers.SerializerMethodField()
    is_verified = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantEmail
        fields = [
            'id', 'tenant', 'provider', 'provider_display', 'smtp_host',
            'smtp_port', 'smtp_user', 'smtp_password', 'smtp_use_tls',
            'smtp_use_ssl', 'api_key', 'api_secret', 'api_region',
            'from_name', 'from_email', 'reply_to_email', 'is_verified',
            'verified_at', 'last_test_at', 'daily_limit', 'hourly_limit',
            'track_opens', 'track_clicks', 'auth_type', 'auth_type_display',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'verified_at', 'last_test_at', 'created_at',
            'updated_at'
        ]
    
    def get_provider_display(self, obj):
        """Get provider display name."""
        return obj.get_provider_display()
    
    def get_auth_type_display(self, obj):
        """Get auth type display name."""
        return obj.get_auth_type_display()
    
    def get_is_verified(self, obj):
        """Check if email configuration is verified."""
        return obj.is_verified
    
    def validate(self, attrs):
        """Validate email configuration data."""
        provider = attrs.get('provider')
        
        # Validate provider-specific requirements
        if provider == 'smtp':
            required_fields = ['smtp_host', 'smtp_port']
            for field in required_fields:
                if field not in attrs or not attrs[field]:
                    raise serializers.ValidationError(f'{field} is required for SMTP provider.')
            
            # Validate port range
            port = attrs.get('smtp_port')
            if not isinstance(port, int) or port < 1 or port > 65535:
                raise serializers.ValidationError('SMTP port must be between 1 and 65535.')
        
        else:
            # API-based providers need API key
            if 'api_key' not in attrs or not attrs['api_key']:
                raise serializers.ValidationError('API key is required for this provider.')
        
        # Validate email addresses
        email_fields = ['from_email', 'reply_to_email']
        for field in email_fields:
            if field in attrs and attrs[field]:
                from django.core.validators import validate_email
                try:
                    validate_email(attrs[field])
                except:
                    raise serializers.ValidationError(f'Invalid {field} address.')
        
        # Validate limits
        limit_fields = ['daily_limit', 'hourly_limit']
        for field in limit_fields:
            if field in attrs and attrs[field]:
                try:
                    limit = int(attrs[field])
                    if limit < 0:
                        raise serializers.ValidationError(f'{field} cannot be negative.')
                except (ValueError, TypeError):
                    raise serializers.ValidationError(f'{field} must be a valid integer.')
        
        return attrs


class TenantEmailUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating tenant email configuration.
    """
    test_connection = serializers.BooleanField(write_only=True, required=False)
    
    class Meta:
        model = TenantEmail
        fields = [
            'provider', 'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password',
            'smtp_use_tls', 'smtp_use_ssl', 'api_key', 'api_secret',
            'api_region', 'from_name', 'from_email', 'reply_to_email',
            'daily_limit', 'hourly_limit', 'track_opens', 'track_clicks',
            'test_connection'
        ]


class TenantSocialLinkSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantSocialLink model.
    """
    display_title = serializers.SerializerMethodField()
    platform_icon = serializers.SerializerMethodField()
    platform_color = serializers.SerializerMethodField()
    platform_display = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantSocialLink
        fields = [
            'id', 'tenant', 'platform', 'platform_display', 'url',
            'display_title', 'is_visible', 'display_name', 'icon',
            'color', 'platform_icon', 'platform_color', 'sort_order',
            'custom_platform_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']
    
    def get_display_title(self, obj):
        """Get display title."""
        return obj.display_title
    
    def get_platform_icon(self, obj):
        """Get platform icon."""
        return obj.platform_icon
    
    def get_platform_color(self, obj):
        """Get platform brand color."""
        return obj.platform_color
    
    def get_platform_display(self, obj):
        """Get platform display name."""
        return obj.get_platform_display()


class TenantSocialLinkCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new tenant social links.
    """
    class Meta:
        model = TenantSocialLink
        fields = [
            'platform', 'url', 'is_visible', 'display_name', 'icon',
            'color', 'sort_order', 'custom_platform_name'
        ]
    
    def validate_platform(self, value):
        """Validate platform uniqueness for tenant."""
        if self.instance and self.instance.platform == value:
            return value
        
        if self.context['request'].tenant.social_links.filter(platform=value).exists():
            raise serializers.ValidationError("Social media platform already exists.")
        return value
    
    def validate(self, attrs):
        """Validate social link data."""
        platform = attrs.get('platform')
        
        # Validate custom platform name
        if platform == 'custom':
            custom_name = attrs.get('custom_platform_name')
            if not custom_name:
                raise serializers.ValidationError('Custom platform name is required for custom platform type.')
        
        # Validate URL
        url = attrs.get('url')
        if url:
            from django.core.validators import URLValidator
            try:
                URLValidator()(url)
            except:
                raise serializers.ValidationError('Invalid URL format.')
        
        return attrs
