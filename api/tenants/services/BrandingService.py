"""
Branding Service

This service handles tenant branding operations including
customization, theme management, and asset handling.
"""

import os
import uuid
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from ..models import Tenant
from ..models.branding import TenantBranding, TenantDomain, TenantEmail, TenantSocialLink
from ..models.security import TenantAuditLog

User = get_user_model()


class BrandingService:
    """
    Service class for tenant branding operations.
    
    This service handles branding customization, domain management,
    email configuration, and social media links.
    """
    
    @staticmethod
    def update_branding(tenant, branding_data, updated_by=None):
        """
        Update tenant branding configuration.
        
        Args:
            tenant (Tenant): Tenant to update branding for
            branding_data (dict): Branding configuration data
            updated_by (User): User updating branding
            
        Returns:
            TenantBranding: Updated branding instance
            
        Raises:
            ValidationError: If data is invalid
        """
        with transaction.atomic():
            # Get or create branding
            branding, created = TenantBranding.objects.get_or_create(tenant=tenant)
            
            # Store old values for audit
            old_values = {}
            for field in ['primary_color', 'secondary_color', 'app_name', 'logo']:
                if hasattr(branding, field):
                    old_values[field] = getattr(branding, field)
            
            # Update branding fields
            updatable_fields = [
                'primary_color', 'secondary_color', 'accent_color', 'background_color',
                'text_color', 'font_family', 'font_family_heading', 'font_size_base',
                'button_radius', 'card_radius', 'border_radius',
                'email_header_color', 'email_footer_text', 'app_name', 'app_short_name',
                'app_description', 'website_url', 'support_url', 'privacy_policy_url',
                'terms_of_service_url', 'custom_css', 'custom_js',
                'meta_title', 'meta_description', 'meta_keywords'
            ]
            
            for field in updatable_fields:
                if field in branding_data:
                    setattr(branding, field, branding_data[field])
            
            branding.save()
            
            # Log update
            if updated_by:
                changes = {}
                for field, old_value in old_values.items():
                    new_value = getattr(branding, field)
                    if old_value != new_value:
                        changes[field] = {'old': str(old_value), 'new': str(new_value)}
                
                if changes:
                    TenantAuditLog.log_action(
                        tenant=tenant,
                        action='config_change',
                        actor=updated_by,
                        model_name='TenantBranding',
                        object_id=str(branding.id),
                        object_repr=str(branding),
                        changes=changes,
                        description=f"Branding updated for {tenant.name}"
                    )
            
            return branding
    
    @staticmethod
    def upload_logo(tenant, logo_file, logo_type='main', uploaded_by=None):
        """
        Upload logo for tenant.
        
        Args:
            tenant (Tenant): Tenant to upload logo for
            logo_file: Logo file to upload
            logo_type (str): Type of logo (main, dark, favicon, etc.)
            uploaded_by (User): User uploading the logo
            
        Returns:
            dict: Upload result with file URL
        """
        with transaction.atomic():
            # Get or create branding
            branding, created = TenantBranding.objects.get_or_create(tenant=tenant)
            
            # Validate file
            BrandingService._validate_image_file(logo_file)
            
            # Generate filename
            file_extension = os.path.splitext(logo_file.name)[1]
            filename = f"{tenant.slug}_{logo_type}_logo_{uuid.uuid4().hex[:8]}{file_extension}"
            
            # Upload file
            path = f"tenant_logos/{filename}"
            saved_path = default_storage.save(path, logo_file)
            file_url = default_storage.url(saved_path)
            
            # Update branding record
            if logo_type == 'main':
                branding.logo = saved_path
            elif logo_type == 'dark':
                branding.logo_dark = saved_path
            elif logo_type == 'favicon':
                branding.favicon = saved_path
            elif logo_type == 'app_store_icon':
                branding.app_store_icon = saved_path
            elif logo_type == 'splash_screen':
                branding.splash_screen = saved_path
            
            branding.save()
            
            # Log upload
            if uploaded_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='config_change',
                    actor=uploaded_by,
                    model_name='TenantBranding',
                    object_id=str(branding.id),
                    object_repr=str(branding),
                    description=f"{logo_type.title()} logo uploaded for {tenant.name}",
                    metadata={
                        'logo_type': logo_type,
                        'file_url': file_url,
                        'file_size': logo_file.size,
                    }
                )
            
            return {
                'success': True,
                'file_url': file_url,
                'logo_type': logo_type,
                'file_size': logo_file.size,
            }
    
    @staticmethod
    def _validate_image_file(file):
        """Validate uploaded image file."""
        # Check file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if file.size > max_size:
            raise ValidationError(_('Image file size cannot exceed 5MB.'))
        
        # Check file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/svg+xml']
        if file.content_type not in allowed_types:
            raise ValidationError(_('Only JPEG, PNG, GIF, and SVG images are allowed.'))
        
        # Check image dimensions if possible
        try:
            from PIL import Image
            image = Image.open(file)
            width, height = image.size
            
            # Max dimensions
            max_width, max_height = 2000, 2000
            if width > max_width or height > max_height:
                raise ValidationError(_(f'Image dimensions cannot exceed {max_width}x{max_height} pixels.'))
        except Exception:
            # If we can't validate dimensions, continue
            pass
    
    @staticmethod
    def remove_logo(tenant, logo_type='main', removed_by=None):
        """
        Remove logo for tenant.
        
        Args:
            tenant (Tenant): Tenant to remove logo for
            logo_type (str): Type of logo to remove
            removed_by (User): User removing the logo
            
        Returns:
            bool: True if successful
        """
        with transaction.atomic():
            branding = tenant.branding
            
            # Get current file path
            if logo_type == 'main':
                current_file = branding.logo
                branding.logo = None
            elif logo_type == 'dark':
                current_file = branding.logo_dark
                branding.logo_dark = None
            elif logo_type == 'favicon':
                current_file = branding.favicon
                branding.favicon = None
            elif logo_type == 'app_store_icon':
                current_file = branding.app_store_icon
                branding.app_store_icon = None
            elif logo_type == 'splash_screen':
                current_file = branding.splash_screen
                branding.splash_screen = None
            else:
                raise ValidationError(_('Invalid logo type.'))
            
            # Delete file if it exists
            if current_file:
                try:
                    default_storage.delete(str(current_file))
                except:
                    pass  # File might not exist
            
            branding.save()
            
            # Log removal
            if removed_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='config_change',
                    actor=removed_by,
                    model_name='TenantBranding',
                    object_id=str(branding.id),
                    object_repr=str(branding),
                    description=f"{logo_type.title()} logo removed for {tenant.name}",
                    metadata={'logo_type': logo_type}
                )
            
            return True
    
    @staticmethod
    def add_domain(tenant, domain_data, added_by=None):
        """
        Add custom domain for tenant.
        
        Args:
            tenant (Tenant): Tenant to add domain for
            domain_data (dict): Domain configuration data
            added_by (User): User adding the domain
            
        Returns:
            TenantDomain: Created domain instance
            
        Raises:
            ValidationError: If data is invalid
        """
        with transaction.atomic():
            # Validate domain uniqueness
            domain = domain_data.get('domain')
            if TenantDomain.objects.filter(domain=domain).exists():
                raise ValidationError(_('Domain is already in use.'))
            
            # Create domain
            domain_instance = TenantDomain.objects.create(
                tenant=tenant,
                domain=domain,
                subdomain=domain_data.get('subdomain'),
                is_primary=domain_data.get('is_primary', False),
                is_active=domain_data.get('is_active', False),
                www_redirect=domain_data.get('www_redirect', True),
                force_https=domain_data.get('force_https', True),
                google_analytics_id=domain_data.get('google_analytics_id'),
                facebook_pixel_id=domain_data.get('facebook_pixel_id'),
                metadata=domain_data.get('metadata', {}),
            )
            
            # Generate DNS verification token
            domain_instance.dns_verification_token = f"tenant-{tenant.id}-{uuid.uuid4().hex[:8]}"
            domain_instance.save()
            
            # Log addition
            if added_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='config_change',
                    actor=added_by,
                    model_name='TenantDomain',
                    object_id=str(domain_instance.id),
                    object_repr=str(domain_instance),
                    description=f"Domain {domain} added for {tenant.name}",
                    metadata={'domain': domain, 'is_primary': domain_instance.is_primary}
                )
            
            return domain_instance
    
    @staticmethod
    def verify_domain(domain, verified_by=None):
        """
        Verify domain DNS configuration.
        
        Args:
            domain (TenantDomain): Domain to verify
            verified_by (User): User verifying the domain
            
        Returns:
            dict: Verification result
        """
        with transaction.atomic():
            # This would implement actual DNS verification
            # For now, just mark as verified
            domain.verify_dns()
            
            # Setup SSL if requested
            if domain.ssl_status == 'none':
                domain.setup_ssl()
            
            # Log verification
            if verified_by:
                TenantAuditLog.log_action(
                    tenant=domain.tenant,
                    action='config_change',
                    actor=verified_by,
                    model_name='TenantDomain',
                    object_id=str(domain.id),
                    object_repr=str(domain),
                    description=f"Domain {domain.domain} verified",
                    metadata={
                        'domain': domain.domain,
                        'dns_status': domain.dns_status,
                        'ssl_status': domain.ssl_status,
                    }
                )
            
            return {
                'success': True,
                'message': f'Domain {domain.domain} verified successfully',
                'dns_status': domain.dns_status,
                'ssl_status': domain.ssl_status,
            }
    
    @staticmethod
    def update_email_config(tenant, email_data, updated_by=None):
        """
        Update tenant email configuration.
        
        Args:
            tenant (Tenant): Tenant to update email config for
            email_data (dict): Email configuration data
            updated_by (User): User updating email config
            
        Returns:
            TenantEmail: Updated email configuration
            
        Raises:
            ValidationError: If data is invalid
        """
        with transaction.atomic():
            # Get or create email config
            email_config, created = TenantEmail.objects.get_or_create(tenant=tenant)
            
            # Update email configuration
            updatable_fields = [
                'provider', 'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password',
                'smtp_use_tls', 'smtp_use_ssl', 'api_key', 'api_secret', 'api_region',
                'from_name', 'from_email', 'reply_to_email',
                'daily_limit', 'hourly_limit',
                'track_opens', 'track_clicks'
            ]
            
            for field in updatable_fields:
                if field in email_data:
                    setattr(email_config, field, email_data[field])
            
            email_config.save()
            
            # Test connection if requested
            if email_data.get('test_connection', False):
                email_config.test_connection()
            
            # Log update
            if updated_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='config_change',
                    actor=updated_by,
                    model_name='TenantEmail',
                    object_id=str(email_config.id),
                    object_repr=str(email_config),
                    description=f"Email configuration updated for {tenant.name}",
                    metadata={'provider': email_config.provider}
                )
            
            return email_config
    
    @staticmethod
    def add_social_link(tenant, social_data, added_by=None):
        """
        Add social media link for tenant.
        
        Args:
            tenant (Tenant): Tenant to add social link for
            social_data (dict): Social link data
            added_by (User): User adding social link
            
        Returns:
            TenantSocialLink: Created social link instance
            
        Raises:
            ValidationError: If data is invalid
        """
        with transaction.atomic():
            # Check if platform already exists
            platform = social_data.get('platform')
            if TenantSocialLink.objects.filter(tenant=tenant, platform=platform).exists():
                raise ValidationError(_('Social media platform already exists.'))
            
            # Create social link
            social_link = TenantSocialLink.objects.create(
                tenant=tenant,
                platform=platform,
                url=social_data.get('url'),
                is_visible=social_data.get('is_visible', True),
                display_name=social_data.get('display_name'),
                icon=social_data.get('icon'),
                color=social_data.get('color'),
                sort_order=social_data.get('sort_order', 0),
                custom_platform_name=social_data.get('custom_platform_name'),
            )
            
            # Log addition
            if added_by:
                TenantAuditLog.log_action(
                    tenant=tenant,
                    action='config_change',
                    actor=added_by,
                    model_name='TenantSocialLink',
                    object_id=str(social_link.id),
                    object_repr=str(social_link),
                    description=f"Social link {social_link.display_title} added for {tenant.name}",
                    metadata={'platform': platform, 'url': social_data.get('url')}
                )
            
            return social_link
    
    @staticmethod
    def update_social_link(social_link, social_data, updated_by=None):
        """
        Update social media link.
        
        Args:
            social_link (TenantSocialLink): Social link to update
            social_data (dict): Social link data
            updated_by (User): User updating social link
            
        Returns:
            TenantSocialLink: Updated social link instance
        """
        with transaction.atomic():
            # Store old values for audit
            old_values = {
                'url': social_link.url,
                'is_visible': social_link.is_visible,
                'display_name': social_link.display_name,
            }
            
            # Update fields
            updatable_fields = ['url', 'is_visible', 'display_name', 'icon', 'color', 'sort_order']
            for field in updatable_fields:
                if field in social_data:
                    setattr(social_link, field, social_data[field])
            
            social_link.save()
            
            # Log update
            if updated_by:
                changes = {}
                for field, old_value in old_values.items():
                    new_value = getattr(social_link, field)
                    if old_value != new_value:
                        changes[field] = {'old': str(old_value), 'new': str(new_value)}
                
                if changes:
                    TenantAuditLog.log_action(
                        tenant=social_link.tenant,
                        action='config_change',
                        actor=updated_by,
                        model_name='TenantSocialLink',
                        object_id=str(social_link.id),
                        object_repr=str(social_link),
                        changes=changes,
                        description=f"Social link {social_link.display_title} updated"
                    )
            
            return social_link
    
    @staticmethod
    def get_branding_summary(tenant):
        """
        Get comprehensive branding summary for tenant.
        
        Args:
            tenant (Tenant): Tenant to get summary for
            
        Returns:
            dict: Branding summary
        """
        summary = {
            'tenant_id': str(tenant.id),
            'tenant_name': tenant.name,
            'branding': {},
            'domains': [],
            'email_config': {},
            'social_links': [],
        }
        
        # Branding information
        if hasattr(tenant, 'branding'):
            branding = tenant.branding
            summary['branding'] = {
                'has_logo': bool(branding.logo),
                'has_dark_logo': bool(branding.logo_dark),
                'has_favicon': bool(branding.favicon),
                'primary_color': branding.primary_color,
                'secondary_color': branding.secondary_color,
                'font_family': branding.font_family,
                'app_name': branding.app_name,
                'has_custom_css': bool(branding.custom_css),
                'has_custom_js': bool(branding.custom_js),
                'setup_complete': bool(branding.logo and branding.app_name),
            }
        
        # Domain information
        domains = TenantDomain.objects.filter(tenant=tenant)
        summary['domains'] = [
            {
                'domain': domain.domain,
                'is_primary': domain.is_primary,
                'is_active': domain.is_active,
                'dns_status': domain.dns_status,
                'ssl_status': domain.ssl_status,
                'ssl_expires_at': domain.ssl_expires_at,
                'days_until_ssl_expiry': domain.days_until_ssl_expiry,
            }
            for domain in domains
        ]
        
        # Email configuration
        if hasattr(tenant, 'email_config'):
            email_config = tenant.email_config
            summary['email_config'] = {
                'provider': email_config.provider,
                'from_email': email_config.from_email,
                'is_verified': email_config.is_verified,
                'last_test_at': email_config.last_test_at,
                'setup_complete': bool(email_config.from_email and email_config.is_verified),
            }
        
        # Social links
        social_links = TenantSocialLink.objects.filter(tenant=tenant, is_visible=True)
        summary['social_links'] = [
            {
                'platform': link.platform,
                'display_title': link.display_title,
                'url': link.url,
                'icon': link.platform_icon,
                'color': link.platform_color,
            }
            for link in social_links.order_by('sort_order')
        ]
        
        return summary
    
    @staticmethod
    def validate_branding_data(data, branding=None):
        """
        Validate branding data.
        
        Args:
            data (dict): Branding data to validate
            branding (TenantBranding): Existing branding (for updates)
            
        Returns:
            tuple: (is_valid, errors)
        """
        errors = []
        
        # Validate color codes
        color_fields = ['primary_color', 'secondary_color', 'accent_color', 'background_color', 'text_color']
        for field in color_fields:
            if field in data and data[field]:
                color = data[field]
                if not color.startswith('#'):
                    color = f'#{color}'
                if len(color) != 7 or not all(c in '0123456789abcdefABCDEF' for c in color[1:]):
                    errors.append(f'Invalid color format for {field}.')
        
        # Validate URLs
        url_fields = ['website_url', 'support_url', 'privacy_policy_url', 'terms_of_service_url']
        for field in url_fields:
            if field in data and data[field]:
                from django.core.validators import URLValidator
                try:
                    URLValidator()(data[field])
                except ValidationError:
                    errors.append(f'Invalid URL format for {field}.')
        
        # Validate font size
        if 'font_size_base' in data:
            font_size = data['font_size_base']
            if not isinstance(font_size, str) or not font_size.endswith('px'):
                errors.append('Font size must end with "px" (e.g., "16px").')
        
        # Validate radius values
        radius_fields = ['button_radius', 'card_radius', 'border_radius']
        for field in radius_fields:
            if field in data and data[field]:
                radius = data[field]
                if not isinstance(radius, str) or not radius.endswith('px'):
                    errors.append(f'{field} must end with "px" (e.g., "6px").')
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_domain_data(data):
        """
        Validate domain data.
        
        Args:
            data (dict): Domain data to validate
            
        Returns:
            tuple: (is_valid, errors)
        """
        errors = []
        
        # Validate domain format
        if 'domain' in data:
            domain = data['domain']
            if not domain:
                errors.append('Domain is required.')
            else:
                # Basic domain validation
                import re
                domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
                if not re.match(domain_pattern, domain):
                    errors.append('Invalid domain format.')
        
        # Validate analytics IDs
        if 'google_analytics_id' in data and data['google_analytics_id']:
            ga_id = data['google_analytics_id']
            if not re.match(r'^[UA|G]-\w+-\d+$', ga_id):
                errors.append('Invalid Google Analytics ID format.')
        
        if 'facebook_pixel_id' in data and data['facebook_pixel_id']:
            fb_id = data['facebook_pixel_id']
            if not re.match(r'^\d+$', fb_id):
                errors.append('Invalid Facebook Pixel ID format.')
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_email_data(data):
        """
        Validate email configuration data.
        
        Args:
            data (dict): Email data to validate
            
        Returns:
            tuple: (is_valid, errors)
        """
        errors = []
        
        # Validate provider-specific requirements
        provider = data.get('provider')
        if provider == 'smtp':
            required_fields = ['smtp_host', 'smtp_port']
            for field in required_fields:
                if field not in data or not data[field]:
                    errors.append(f'{field} is required for SMTP provider.')
            
            # Validate port range
            if 'smtp_port' in data:
                port = data['smtp_port']
                if not isinstance(port, int) or port < 1 or port > 65535:
                    errors.append('SMTP port must be between 1 and 65535.')
        
        else:
            # API-based providers need API key
            if 'api_key' not in data or not data['api_key']:
                errors.append('API key is required for this provider.')
        
        # Validate email addresses
        if 'from_email' in data and data['from_email']:
            from django.core.validators import validate_email
            try:
                validate_email(data['from_email'])
            except ValidationError:
                errors.append('Invalid from email address.')
        
        if 'reply_to_email' in data and data['reply_to_email']:
            from django.core.validators import validate_email
            try:
                validate_email(data['reply_to_email'])
            except ValidationError:
                errors.append('Invalid reply-to email address.')
        
        # Validate limits
        for field in ['daily_limit', 'hourly_limit']:
            if field in data and data[field]:
                try:
                    limit = int(data[field])
                    if limit < 0:
                        errors.append(f'{field} cannot be negative.')
                except (ValueError, TypeError):
                    errors.append(f'{field} must be a valid integer.')
        
        return len(errors) == 0, errors
