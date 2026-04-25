"""
Branding Models

This module contains tenant branding models for customization
of appearance, domains, email, and social media.
"""

import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from .base import TimeStampedModel, SoftDeleteModel

User = get_user_model()


class TenantBranding(TimeStampedModel, SoftDeleteModel):
    """
    Tenant branding and customization settings.
    
    This model allows tenants to customize their application
    appearance, colors, logos, and other visual elements.
    """
    
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='branding',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this branding belongs to')
    )
    
    # Logo and images
    logo = models.ImageField(
        upload_to='tenant_logos/',
        blank=True,
        null=True,
        verbose_name=_('Logo'),
        help_text=_('Primary logo image')
    )
    logo_dark = models.ImageField(
        upload_to='tenant_logos/',
        blank=True,
        null=True,
        verbose_name=_('Dark Logo'),
        help_text=_('Logo for dark themes')
    )
    favicon = models.ImageField(
        upload_to='tenant_favicons/',
        blank=True,
        null=True,
        verbose_name=_('Favicon'),
        help_text=_('Favicon image')
    )
    app_store_icon = models.ImageField(
        upload_to='tenant_icons/',
        blank=True,
        null=True,
        verbose_name=_('App Store Icon'),
        help_text=_('Icon for app stores')
    )
    splash_screen = models.ImageField(
        upload_to='tenant_splash/',
        blank=True,
        null=True,
        verbose_name=_('Splash Screen'),
        help_text=_('Mobile app splash screen')
    )
    
    # Color scheme
    primary_color = models.CharField(
        max_length=7,
        default='#007bff',
        verbose_name=_('Primary Color'),
        help_text=_('Primary brand color (hex)')
    )
    secondary_color = models.CharField(
        max_length=7,
        default='#6c757d',
        verbose_name=_('Secondary Color'),
        help_text=_('Secondary brand color (hex)')
    )
    accent_color = models.CharField(
        max_length=7,
        default='#28a745',
        verbose_name=_('Accent Color'),
        help_text=_('Accent color (hex)')
    )
    background_color = models.CharField(
        max_length=7,
        default='#ffffff',
        verbose_name=_('Background Color'),
        help_text=_('Background color (hex)')
    )
    text_color = models.CharField(
        max_length=7,
        default='#212529',
        verbose_name=_('Text Color'),
        help_text=_('Primary text color (hex)')
    )
    
    # Typography
    font_family = models.CharField(
        max_length=100,
        default='Inter, sans-serif',
        verbose_name=_('Font Family'),
        help_text=_('Primary font family')
    )
    font_family_heading = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Heading Font Family'),
        help_text=_('Font family for headings')
    )
    font_size_base = models.CharField(
        max_length=10,
        default='16px',
        verbose_name=_('Base Font Size'),
        help_text=_('Base font size')
    )
    
    # UI elements
    button_radius = models.CharField(
        max_length=10,
        default='6px',
        verbose_name=_('Button Radius'),
        help_text=_('Border radius for buttons')
    )
    card_radius = models.CharField(
        max_length=10,
        default='8px',
        verbose_name=_('Card Radius'),
        help_text=_('Border radius for cards')
    )
    border_radius = models.CharField(
        max_length=10,
        default='4px',
        verbose_name=_('Border Radius'),
        help_text=_('General border radius')
    )
    
    # Email branding
    email_header_color = models.CharField(
        max_length=7,
        default='#007bff',
        verbose_name=_('Email Header Color'),
        help_text=_('Header color for emails')
    )
    email_footer_text = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Email Footer Text'),
        help_text=_('Footer text for emails')
    )
    email_logo = models.ImageField(
        upload_to='tenant_email_logos/',
        blank=True,
        null=True,
        verbose_name=_('Email Logo'),
        help_text=_('Logo for email templates')
    )
    
    # Application branding
    app_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('App Name'),
        help_text=_('Custom application name')
    )
    app_short_name = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('App Short Name'),
        help_text=_('Short version of app name')
    )
    app_description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('App Description'),
        help_text=_('Application description')
    )
    
    # Social media and links
    website_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_('Website URL'),
        help_text=_('Main website URL')
    )
    support_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_('Support URL'),
        help_text=_('Support page URL')
    )
    privacy_policy_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_('Privacy Policy URL'),
        help_text=_('Privacy policy URL')
    )
    terms_of_service_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_('Terms of Service URL'),
        help_text=_('Terms of service URL')
    )
    
    # Custom CSS and JS
    custom_css = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Custom CSS'),
        help_text=_('Custom CSS for additional styling')
    )
    custom_js = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Custom JavaScript'),
        help_text=_('Custom JavaScript for additional functionality')
    )
    
    # Meta tags and SEO
    meta_title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Meta Title'),
        help_text=_('SEO meta title')
    )
    meta_description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Meta Description'),
        help_text=_('SEO meta description')
    )
    meta_keywords = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_('Meta Keywords'),
        help_text=_('SEO meta keywords')
    )
    
    class Meta:
        db_table = 'tenant_branding'
        verbose_name = _('Tenant Branding')
        verbose_name_plural = _('Tenant Branding')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Branding for {self.tenant.name}"
    
    def clean(self):
        super().clean()
        # Validate hex color codes
        color_fields = [
            'primary_color', 'secondary_color', 'accent_color',
            'background_color', 'text_color', 'email_header_color'
        ]
        
        for field_name in color_fields:
            color = getattr(self, field_name)
            if color and not color.startswith('#'):
                setattr(self, field_name, f'#{color}')
    
    @property
    def logo_url(self):
        """Get logo URL."""
        if self.logo:
            return self.logo.url
        return None
    
    @property
    def favicon_url(self):
        """Get favicon URL."""
        if self.favicon:
            return self.favicon.url
        return None
    
    def get_color_scheme(self):
        """Get complete color scheme as dictionary."""
        return {
            'primary': self.primary_color,
            'secondary': self.secondary_color,
            'accent': self.accent_color,
            'background': self.background_color,
            'text': self.text_color,
            'email_header': self.email_header_color,
        }
    
    def get_typography(self):
        """Get typography settings as dictionary."""
        return {
            'font_family': self.font_family,
            'font_family_heading': self.font_family_heading or self.font_family,
            'font_size_base': self.font_size_base,
        }
    
    def get_ui_settings(self):
        """Get UI settings as dictionary."""
        return {
            'button_radius': self.button_radius,
            'card_radius': self.card_radius,
            'border_radius': self.border_radius,
        }


class TenantDomain(TimeStampedModel, SoftDeleteModel):
    """
    Custom domain configuration for tenants.
    
    This model manages custom domains, SSL certificates,
    and DNS verification for tenant sites.
    """
    
    SSL_STATUS_CHOICES = [
        ('none', _('None')),
        ('pending', _('Pending')),
        ('verified', _('Verified')),
        ('expired', _('Expired')),
        ('error', _('Error')),
    ]
    
    DNS_STATUS_CHOICES = [
        ('unverified', _('Unverified')),
        ('pending', _('Pending')),
        ('verified', _('Verified')),
        ('failed', _('Failed')),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='domains',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this domain belongs to')
    )
    
    # Domain information
    domain = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_('Domain'),
        help_text=_('Custom domain name')
    )
    subdomain = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Subdomain'),
        help_text=_('Subdomain if using shared domain')
    )
    
    # Status and verification
    is_primary = models.BooleanField(
        default=False,
        verbose_name=_('Is Primary'),
        help_text=_('Whether this is the primary domain')
    )
    is_active = models.BooleanField(
        default=False,
        verbose_name=_('Is Active'),
        help_text=_('Whether the domain is active')
    )
    
    # DNS verification
    dns_status = models.CharField(
        max_length=20,
        choices=DNS_STATUS_CHOICES,
        default='unverified',
        verbose_name=_('DNS Status'),
        help_text=_('DNS verification status')
    )
    dns_verified_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('DNS Verified At'),
        help_text=_('When DNS was verified')
    )
    dns_verification_token = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('DNS Verification Token'),
        help_text=_('Token for DNS verification')
    )
    
    # SSL certificate
    ssl_status = models.CharField(
        max_length=20,
        choices=SSL_STATUS_CHOICES,
        default='none',
        verbose_name=_('SSL Status'),
        help_text=_('SSL certificate status')
    )
    ssl_expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('SSL Expires At'),
        help_text=_('When SSL certificate expires')
    )
    ssl_certificate = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('SSL Certificate'),
        help_text=_('SSL certificate content')
    )
    ssl_private_key = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('SSL Private Key'),
        help_text=_('SSL private key content')
    )
    ssl_auto_renew = models.BooleanField(
        default=True,
        verbose_name=_('SSL Auto Renew'),
        help_text=_('Whether to auto-renew SSL certificate')
    )
    
    # Configuration
    www_redirect = models.BooleanField(
        default=True,
        verbose_name=_('WWW Redirect'),
        help_text=_('Redirect www to non-www or vice versa')
    )
    force_https = models.BooleanField(
        default=True,
        verbose_name=_('Force HTTPS'),
        help_text=_('Force HTTPS connections')
    )
    
    # Analytics and tracking
    google_analytics_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Google Analytics ID'),
        help_text=_('Google Analytics tracking ID')
    )
    facebook_pixel_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Facebook Pixel ID'),
        help_text=_('Facebook Pixel tracking ID')
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Additional domain metadata')
    )
    
    class Meta:
        db_table = 'tenant_domains'
        verbose_name = _('Tenant Domain')
        verbose_name_plural = _('Tenant Domains')
        ordering = ['-is_primary', 'domain']
        indexes = [
            models.Index(fields=['tenant', 'is_primary'], name='idx_tenant_is_primary_1774'),
            models.Index(fields=['domain'], name='idx_domain_1775'),
            models.Index(fields=['dns_status'], name='idx_dns_status_1776'),
            models.Index(fields=['ssl_status'], name='idx_ssl_status_1777'),
            models.Index(fields=['ssl_expires_at'], name='idx_ssl_expires_at_1778'),
        ]
    
    def __str__(self):
        return f"{self.domain} ({self.tenant.name})"
    
    def clean(self):
        super().clean()
        if self.is_primary:
            # Ensure no other primary domain exists for this tenant
            existing_primary = TenantDomain.objects.filter(
                tenant=self.tenant,
                is_primary=True
            ).exclude(pk=self.pk)
            
            if existing_primary.exists():
                raise ValidationError(_('Only one primary domain is allowed per tenant.'))
    
    @property
    def is_ssl_valid(self):
        """Check if SSL certificate is valid."""
        if not self.ssl_expires_at:
            return False
        
        from django.utils import timezone
        return timezone.now() < self.ssl_expires_at
    
    @property
    def days_until_ssl_expiry(self):
        """Days until SSL certificate expires."""
        if not self.ssl_expires_at:
            return None
        
        from django.utils import timezone
        delta = self.ssl_expires_at - timezone.now()
        return max(0, delta.days)
    
    @property
    def full_domain(self):
        """Get full domain including subdomain."""
        if self.subdomain:
            return f"{self.subdomain}.{self.domain}"
        return self.domain
    
    def verify_dns(self):
        """Verify DNS configuration."""
        # This would implement actual DNS verification logic
        # For now, just mark as verified
        from django.utils import timezone
        self.dns_status = 'verified'
        self.dns_verified_at = timezone.now()
        self.save(update_fields=['dns_status', 'dns_verified_at'])
    
    def setup_ssl(self):
        """Setup SSL certificate."""
        # This would implement actual SSL setup logic
        # For now, just mark as verified
        from django.utils import timezone
        import datetime
        
        self.ssl_status = 'verified'
        self.ssl_expires_at = timezone.now() + datetime.timedelta(days=90)
        self.save(update_fields=['ssl_status', 'ssl_expires_at'])


class TenantEmail(TimeStampedModel, SoftDeleteModel):
    """
    Email configuration for tenants.
    
    This model manages SMTP settings, email templates,
    and delivery configuration for tenant emails.
    """
    
    EMAIL_PROVIDER_CHOICES = [
        ('smtp', _('SMTP')),
        ('ses', _('Amazon SES')),
        ('sendgrid', _('SendGrid')),
        ('mailgun', _('Mailgun')),
        ('postmark', _('Postmark')),
    ]
    
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='email_config',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this email config belongs to')
    )
    
    # Provider settings
    provider = models.CharField(
        max_length=20,
        choices=EMAIL_PROVIDER_CHOICES,
        default='smtp',
        verbose_name=_('Email Provider'),
        help_text=_('Email service provider')
    )
    
    # SMTP configuration
    smtp_host = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('SMTP Host'),
        help_text=_('SMTP server hostname')
    )
    smtp_port = models.IntegerField(
        blank=True,
        null=True,
        verbose_name=_('SMTP Port'),
        help_text=_('SMTP server port')
    )
    smtp_user = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('SMTP User'),
        help_text=_('SMTP username')
    )
    smtp_password = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('SMTP Password'),
        help_text=_('SMTP password')
    )
    smtp_use_tls = models.BooleanField(
        default=True,
        verbose_name=_('Use TLS'),
        help_text=_('Use TLS encryption')
    )
    smtp_use_ssl = models.BooleanField(
        default=False,
        verbose_name=_('Use SSL'),
        help_text=_('Use SSL encryption')
    )
    
    # API credentials (for non-SMTP providers)
    api_key = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('API Key'),
        help_text=_('Provider API key')
    )
    api_secret = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('API Secret'),
        help_text=_('Provider API secret')
    )
    api_region = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('API Region'),
        help_text=_('Provider API region')
    )
    
    # Default sender information
    from_name = models.CharField(
        max_length=255,
        default='Support',
        verbose_name=_('From Name'),
        help_text=_('Default sender name')
    )
    from_email = models.EmailField(
        verbose_name=_('From Email'),
        help_text=_('Default sender email')
    )
    reply_to_email = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_('Reply To Email'),
        help_text=_('Reply-to email address')
    )
    
    # Verification and status
    is_verified = models.BooleanField(
        default=False,
        verbose_name=_('Is Verified'),
        help_text=_('Whether email configuration is verified')
    )
    verified_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Verified At'),
        help_text=_('When configuration was verified')
    )
    last_test_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Last Test At'),
        help_text=_('When last test email was sent')
    )
    
    # Limits and quotas
    daily_limit = models.IntegerField(
        blank=True,
        null=True,
        verbose_name=_('Daily Limit'),
        help_text=_('Daily email sending limit')
    )
    hourly_limit = models.IntegerField(
        blank=True,
        null=True,
        verbose_name=_('Hourly Limit'),
        help_text=_('Hourly email sending limit')
    )
    
    # Tracking and analytics
    track_opens = models.BooleanField(
        default=True,
        verbose_name=_('Track Opens'),
        help_text=_('Track email opens')
    )
    track_clicks = models.BooleanField(
        default=True,
        verbose_name=_('Track Clicks'),
        help_text=_('Track email clicks')
    )
    
    class Meta:
        db_table = 'tenant_email'
        verbose_name = _('Tenant Email')
        verbose_name_plural = _('Tenant Email')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider'], name='idx_provider_1779'),
            models.Index(fields=['is_verified'], name='idx_is_verified_1780'),
            models.Index(fields=['last_test_at'], name='idx_last_test_at_1781'),
        ]
    
    def __str__(self):
        return f"Email config for {self.tenant.name}"
    
    def clean(self):
        super().clean()
        if self.provider == 'smtp':
            if not self.smtp_host or not self.smtp_port:
                raise ValidationError(_('SMTP configuration requires host and port.'))
        else:
            if not self.api_key:
                raise ValidationError(_('API-based provider requires API key.'))
    
    def test_connection(self):
        """Test email configuration."""
        # This would implement actual connection testing
        # For now, just mark as tested
        from django.utils import timezone
        self.last_test_at = timezone.now()
        self.save(update_fields=['last_test_at'])
        return True
    
    def verify_configuration(self):
        """Verify email configuration."""
        # This would implement actual verification logic
        # For now, just mark as verified
        from django.utils import timezone
        self.is_verified = True
        self.verified_at = timezone.now()
        self.save(update_fields=['is_verified', 'verified_at'])
        return True


class TenantSocialLink(TimeStampedModel, SoftDeleteModel):
    """
    Social media links for tenants.
    
    This model manages social media profile links
    and display settings for tenants.
    """
    
    PLATFORM_CHOICES = [
        ('facebook', _('Facebook')),
        ('twitter', _('Twitter')),
        ('instagram', _('Instagram')),
        ('linkedin', _('LinkedIn')),
        ('youtube', _('YouTube')),
        ('tiktok', _('TikTok')),
        ('github', _('GitHub')),
        ('discord', _('Discord')),
        ('telegram', _('Telegram')),
        ('whatsapp', _('WhatsApp')),
        ('pinterest', _('Pinterest')),
        ('reddit', _('Reddit')),
        ('medium', _('Medium')),
        ('slack', _('Slack')),
        ('custom', _('Custom')),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='social_links',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this social link belongs to')
    )
    
    # Platform and URL
    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        verbose_name=_('Platform'),
        help_text=_('Social media platform')
    )
    url = models.URLField(
        verbose_name=_('URL'),
        help_text=_('Social media profile URL')
    )
    
    # Display settings
    is_visible = models.BooleanField(
        default=True,
        verbose_name=_('Is Visible'),
        help_text=_('Whether to display this link')
    )
    display_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Display Name'),
        help_text=_('Custom display name')
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_('Icon'),
        help_text=_('Icon class or identifier')
    )
    color = models.CharField(
        max_length=7,
        blank=True,
        null=True,
        verbose_name=_('Color'),
        help_text=_('Brand color (hex)')
    )
    
    # Ordering
    sort_order = models.IntegerField(
        default=0,
        verbose_name=_('Sort Order'),
        help_text=_('Display order')
    )
    
    # Custom platform (when platform='custom')
    custom_platform_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Custom Platform Name'),
        help_text=_('Name for custom platform')
    )
    
    class Meta:
        db_table = 'tenant_social_links'
        verbose_name = _('Tenant Social Link')
        verbose_name_plural = _('Tenant Social Links')
        ordering = ['sort_order', 'platform']
        unique_together = ['tenant', 'platform']
        indexes = [
            models.Index(fields=['tenant', 'platform'], name='idx_tenant_platform_1782'),
            models.Index(fields=['is_visible'], name='idx_is_visible_1783'),
            models.Index(fields=['sort_order'], name='idx_sort_order_1784'),
        ]
    
    def __str__(self):
        return f"{self.get_platform_display()} for {self.tenant.name}"
    
    @property
    def display_title(self):
        """Get display title."""
        if self.display_name:
            return self.display_name
        
        if self.platform == 'custom' and self.custom_platform_name:
            return self.custom_platform_name
        
        return self.get_platform_display()
    
    @property
    def platform_icon(self):
        """Get platform icon."""
        if self.icon:
            return self.icon
        
        # Default icons for common platforms
        icon_map = {
            'facebook': 'fab fa-facebook',
            'twitter': 'fab fa-twitter',
            'instagram': 'fab fa-instagram',
            'linkedin': 'fab fa-linkedin',
            'youtube': 'fab fa-youtube',
            'tiktok': 'fab fa-tiktok',
            'github': 'fab fa-github',
            'discord': 'fab fa-discord',
            'telegram': 'fab fa-telegram',
            'whatsapp': 'fab fa-whatsapp',
            'pinterest': 'fab fa-pinterest',
            'reddit': 'fab fa-reddit',
            'medium': 'fab fa-medium',
            'slack': 'fab fa-slack',
        }
        
        return icon_map.get(self.platform, 'fas fa-link')
    
    @property
    def platform_color(self):
        """Get platform brand color."""
        if self.color:
            return self.color
        
        # Default colors for common platforms
        color_map = {
            'facebook': '#1877f2',
            'twitter': '#1da1f2',
            'instagram': '#e4405f',
            'linkedin': '#0077b5',
            'youtube': '#ff0000',
            'tiktok': '#000000',
            'github': '#333333',
            'discord': '#7289da',
            'telegram': '#0088cc',
            'whatsapp': '#25d366',
            'pinterest': '#bd081c',
            'reddit': '#ff4500',
            'medium': '#00ab6c',
            'slack': '#4a154b',
        }
        
        return color_map.get(self.platform, '#6c757d')
