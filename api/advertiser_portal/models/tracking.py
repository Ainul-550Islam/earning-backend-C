"""
Tracking Models for Advertiser Portal

This module contains models for managing tracking pixels,
postback URLs, conversion events, and tracking domains.
"""

import logging
import hashlib
import secrets
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()
logger = logging.getLogger(__name__)


class TrackingPixel(models.Model):
    """
    Model for managing tracking pixels.
    
    Stores pixel configurations for impression,
    click, and conversion tracking.
    """
    
    # Core relationships
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='tracking_pixels',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this pixel belongs to')
    )
    
    offer = models.ForeignKey(
        'advertiser_portal_v2.AdvertiserOffer',
        on_delete=models.CASCADE,
        related_name='tracking_pixels',
        null=True,
        blank=True,
        verbose_name=_('Offer'),
        help_text=_('Offer this pixel belongs to')
    )
    
    # Pixel details
    pixel_type = models.CharField(
        _('Pixel Type'),
        max_length=20,
        choices=[
            ('impression', _('Impression')),
            ('click', _('Click')),
            ('conversion', _('Conversion')),
            ('view_through', _('View Through')),
            ('custom', _('Custom')),
        ],
        default='impression',
        db_index=True,
        help_text=_('Type of tracking pixel')
    )
    
    name = models.CharField(
        _('Pixel Name'),
        max_length=200,
        help_text=_('Pixel name for identification')
    )
    
    pixel_code = models.CharField(
        _('Pixel Code'),
        max_length=255,
        unique=True,
        db_index=True,
        help_text=_('Unique pixel code for tracking')
    )
    
    # Pixel configuration
    fire_on = models.CharField(
        _('Fire On'),
        max_length=50,
        choices=[
            ('page_load', _('Page Load')),
            ('click', _('Click')),
            ('form_submit', _('Form Submit')),
            ('scroll', _('Scroll')),
            ('time_on_page', _('Time on Page')),
            ('custom_event', _('Custom Event')),
        ],
        default='page_load',
        help_text=_('When pixel should fire')
    )
    
    # Pixel content
    pixel_html = models.TextField(
        _('Pixel HTML'),
        null=True,
        blank=True,
        help_text=_('HTML code for the pixel')
    )
    
    pixel_js = models.TextField(
        _('Pixel JavaScript'),
        null=True,
        blank=True,
        help_text=_('JavaScript code for the pixel')
    )
    
    pixel_img = models.URLField(
        _('Pixel Image URL'),
        max_length=500,
        null=True,
        blank=True,
        help_text=_('Image pixel URL')
    )
    
    # Status and configuration
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        db_index=True,
        help_text=_('Whether this pixel is active')
    )
    
    is_secure = models.BooleanField(
        _('Is Secure'),
        default=True,
        help_text=_('Whether pixel uses HTTPS')
    )
    
    async_firing = models.BooleanField(
        _('Async Firing'),
        default=True,
        help_text=_('Whether pixel fires asynchronously')
    )
    
    # Timing configuration
    delay_ms = models.IntegerField(
        _('Delay (ms)'),
        default=0,
        help_text=_('Delay before firing pixel in milliseconds')
    )
    
    timeout_ms = models.IntegerField(
        _('Timeout (ms)'),
        default=5000,
        help_text=_('Timeout for pixel firing in milliseconds')
    )
    
    # Custom parameters
    custom_parameters = models.JSONField(
        _('Custom Parameters'),
        default=dict,
        blank=True,
        help_text=_('Custom parameters for pixel')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this pixel was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this pixel was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_tracking_pixel'
        verbose_name = _('Tracking Pixel')
        verbose_name_plural = _('Tracking Pixels')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser', 'pixel_type'], name='idx_advertiser_pixel_type_545'),
            models.Index(fields=['offer', 'pixel_type'], name='idx_offer_pixel_type_546'),
            models.Index(fields=['pixel_code', 'is_active'], name='idx_pixel_code_is_active_547'),
            models.Index(fields=['is_active', 'created_at'], name='idx_is_active_created_at_548'),
        ]
        unique_together = [
            ['advertiser', 'pixel_code'],
        ]
    
    def __str__(self):
        return f"{self.name} ({self.pixel_type})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate pixel code
        if not self.pixel_code.strip():
            raise ValidationError(_('Pixel code cannot be empty'))
        
        # Validate delay
        if self.delay_ms < 0:
            raise ValidationError(_('Delay cannot be negative'))
        
        # Validate timeout
        if self.timeout_ms <= 0:
            raise ValidationError(_('Timeout must be positive'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Generate pixel code if not provided
        if not self.pixel_code:
            self.pixel_code = self._generate_pixel_code()
        
        super().save(*args, **kwargs)
    
    def _generate_pixel_code(self) -> str:
        """Generate unique pixel code."""
        timestamp = str(int(timezone.now().timestamp()))
        random_str = secrets.token_hex(4)
        return f"px_{timestamp}_{random_str}"
    
    @property
    def pixel_url(self) -> str:
        """Get pixel URL for tracking."""
        if self.pixel_img:
            return self.pixel_img
        
        # Generate default pixel URL
        base_url = "https://tracking.example.com/pixel"
        return f"{base_url}/{self.pixel_code}"
    
    @property
    def has_html(self) -> bool:
        """Check if pixel has HTML content."""
        return bool(self.pixel_html)
    
    @property
    def has_js(self) -> bool:
        """Check if pixel has JavaScript content."""
        return bool(self.pixel_js)
    
    @property
    def has_img(self) -> bool:
        """Check if pixel has image URL."""
        return bool(self.pixel_img)
    
    def get_pixel_code_html(self) -> str:
        """Get HTML code for pixel."""
        if self.pixel_html:
            return self.pixel_html
        
        # Generate default HTML pixel
        if self.pixel_type == 'impression':
            return f'<img src="{self.pixel_url}" width="1" height="1" border="0" alt="" />'
        elif self.pixel_type == 'click':
            return f'<script>document.addEventListener("click", function() {{ fetch("{self.pixel_url}"); }});</script>'
        else:
            return f'<script src="{self.pixel_url}"></script>'
    
    def get_pixel_code_js(self) -> str:
        """Get JavaScript code for pixel."""
        if self.pixel_js:
            return self.pixel_js
        
        # Generate default JavaScript pixel
        return f"""
        (function() {{
            var pixelUrl = "{self.pixel_url}";
            var delay = {self.delay_ms};
            
            if (delay > 0) {{
                setTimeout(function() {{
                    fetch(pixelUrl);
                }}, delay);
            }} else {{
                fetch(pixelUrl);
            }}
        }})();
        """
    
    def get_tracking_summary(self) -> dict:
        """Get tracking summary for this pixel."""
        # This would implement tracking statistics
        return {
            'pixel_type': self.pixel_type,
            'pixel_code': self.pixel_code,
            'is_active': self.is_active,
            'has_html': self.has_html,
            'has_js': self.has_js,
            'has_img': self.has_img,
            'fire_on': self.fire_on,
            'delay_ms': self.delay_ms,
            'created_at': self.created_at.isoformat(),
        }


class S2SPostback(models.Model):
    """
    Model for managing server-to-server postbacks.
    
    Stores postback URL configurations and
    parameter mappings for conversion tracking.
    """
    
    # Core relationships
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='s2s_postbacks',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this postback belongs to')
    )
    
    offer = models.ForeignKey(
        'advertiser_portal_v2.AdvertiserOffer',
        on_delete=models.CASCADE,
        related_name='s2s_postbacks',
        null=True,
        blank=True,
        verbose_name=_('Offer'),
        help_text=_('Offer this postback belongs to')
    )
    
    # Postback details
    postback_url = models.URLField(
        _('Postback URL'),
        max_length=500,
        help_text=_('URL to receive postback requests')
    )
    
    postback_method = models.CharField(
        _('Postback Method'),
        max_length=10,
        choices=[
            ('GET', _('GET')),
            ('POST', _('POST')),
        ],
        default='GET',
        help_text=_('HTTP method for postback requests')
    )
    
    # Security
    secret_key = models.CharField(
        _('Secret Key'),
        max_length=255,
        help_text=_('Secret key for postback validation')
    )
    
    use_hmac = models.BooleanField(
        _('Use HMAC'),
        default=True,
        help_text=_('Whether to use HMAC signature validation')
    )
    
    hmac_algorithm = models.CharField(
        _('HMAC Algorithm'),
        max_length=20,
        choices=[
            ('sha256', _('SHA-256')),
            ('sha1', _('SHA-1')),
            ('md5', _('MD5')),
        ],
        default='sha256',
        help_text=_('HMAC algorithm for signature')
    )
    
    # Parameter mapping
    params_map = models.JSONField(
        _('Parameters Map'),
        default=dict,
        help_text=_('Mapping of parameters to send')
    )
    
    # Status and configuration
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        db_index=True,
        help_text=_('Whether this postback is active')
    )
    
    test_mode = models.BooleanField(
        _('Test Mode'),
        default=False,
        help_text=_('Whether postback is in test mode')
    )
    
    # Retry configuration
    max_retries = models.IntegerField(
        _('Max Retries'),
        default=3,
        help_text=_('Maximum number of retry attempts')
    )
    
    retry_delay = models.IntegerField(
        _('Retry Delay'),
        default=5,
        help_text=_('Delay between retries in seconds')
    )
    
    # Response handling
    success_response = models.CharField(
        _('Success Response'),
        max_length=20,
        default='OK',
        help_text=_('Expected success response')
    )
    
    timeout_seconds = models.IntegerField(
        _('Timeout (seconds)'),
        default=30,
        help_text=_('Timeout for postback requests')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this postback was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this postback was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_s2s_postback'
        verbose_name = _('S2S Postback')
        verbose_name_plural = _('S2S Postbacks')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser', 'is_active'], name='idx_advertiser_is_active_549'),
            models.Index(fields=['offer', 'is_active'], name='idx_offer_is_active_550'),
            models.Index(fields=['is_active', 'test_mode'], name='idx_is_active_test_mode_551'),
            models.Index(fields=['created_at'], name='idx_created_at_552'),
        ]
    
    def __str__(self):
        return f"Postback: {self.advertiser.company_name}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate postback URL
        if not self.postback_url:
            raise ValidationError(_('Postback URL is required'))
        
        # Validate retry configuration
        if self.max_retries < 0:
            raise ValidationError(_('Max retries cannot be negative'))
        
        if self.retry_delay < 0:
            raise ValidationError(_('Retry delay cannot be negative'))
        
        # Validate timeout
        if self.timeout_seconds <= 0:
            raise ValidationError(_('Timeout must be positive'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Generate secret key if not provided
        if not self.secret_key:
            self.secret_key = self._generate_secret_key()
        
        super().save(*args, **kwargs)
    
    def _generate_secret_key(self) -> str:
        """Generate secure secret key."""
        return secrets.token_urlsafe(32)
    
    @property
    def has_custom_params(self) -> bool:
        """Check if postback has custom parameters."""
        return bool(self.params_map)
    
    def generate_signature(self, params: dict) -> str:
        """Generate HMAC signature for postback."""
        if not self.use_hmac:
            return ""
        
        import hmac
        
        # Sort parameters for consistent signature
        sorted_params = sorted(params.items())
        
        # Create string to sign
        string_to_sign = "&".join([f"{k}={v}" for k, v in sorted_params])
        
        # Generate signature
        if self.hmac_algorithm == 'sha256':
            signature = hmac.new(
                self.secret_key.encode(),
                string_to_sign.encode(),
                hashlib.sha256
            ).hexdigest()
        elif self.hmac_algorithm == 'sha1':
            signature = hmac.new(
                self.secret_key.encode(),
                string_to_sign.encode(),
                hashlib.sha1
            ).hexdigest()
        else:  # md5
            signature = hmac.new(
                self.secret_key.encode(),
                string_to_sign.encode(),
                hashlib.md5
            ).hexdigest()
        
        return signature
    
    def validate_signature(self, params: dict, received_signature: str) -> bool:
        """Validate received HMAC signature."""
        if not self.use_hmac:
            return True
        
        generated_signature = self.generate_signature(params)
        return hmac.compare_digest(generated_signature, received_signature)
    
    def build_postback_url(self, conversion_data: dict) -> str:
        """Build postback URL with parameters."""
        from urllib.parse import urlencode
        
        # Merge default and custom parameters
        params = {
            'conversion_id': conversion_data.get('id'),
            'payout': conversion_data.get('payout'),
            'currency': conversion_data.get('currency', 'USD'),
            'timestamp': conversion_data.get('timestamp'),
            'ip': conversion_data.get('ip'),
            'user_agent': conversion_data.get('user_agent'),
        }
        
        # Add custom parameters
        if self.params_map:
            for param_name, param_mapping in self.params_map.items():
                if param_mapping in conversion_data:
                    params[param_name] = conversion_data[param_mapping]
        
        # Add signature if using HMAC
        if self.use_hmac:
            params['signature'] = self.generate_signature(params)
        
        # Build URL
        if self.postback_method == 'GET':
            separator = '&' if '?' in self.postback_url else '?'
            return f"{self.postback_url}{separator}{urlencode(params)}"
        else:
            return self.postback_url
    
    def get_postback_summary(self) -> dict:
        """Get postback configuration summary."""
        return {
            'postback_url': self.postback_url,
            'postback_method': self.postback_method,
            'is_active': self.is_active,
            'test_mode': self.test_mode,
            'use_hmac': self.use_hmac,
            'hmac_algorithm': self.hmac_algorithm,
            'has_custom_params': self.has_custom_params,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'timeout_seconds': self.timeout_seconds,
            'created_at': self.created_at.isoformat(),
        }


class Conversion(models.Model):
    """
    Model for managing conversions.
    
    Stores conversion data including revenue, attribution,
    fraud scoring, and quality metrics.
    """
    
    # Core relationships
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='conversions',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this conversion belongs to')
    )
    
    offer = models.ForeignKey(
        'advertiser_portal_v2.AdvertiserOffer',
        on_delete=models.CASCADE,
        related_name='conversions',
        null=True,
        blank=True,
        verbose_name=_('Offer'),
        help_text=_('Offer this conversion belongs to')
    )
    
    campaign = models.ForeignKey(
        'advertiser_portal_v2.AdCampaign',
        on_delete=models.CASCADE,
        related_name='conversions',
        null=True,
        blank=True,
        verbose_name=_('Campaign'),
        help_text=_('Campaign this conversion belongs to')
    )
    
    pixel = models.ForeignKey(
        'advertiser_portal_v2.TrackingPixel',
        on_delete=models.CASCADE,
        related_name='conversions',
        null=True,
        blank=True,
        verbose_name=_('Pixel'),
        help_text=_('Pixel that triggered this conversion')
    )
    
    # Conversion details
    conversion_id = models.CharField(
        _('Conversion ID'),
        max_length=100,
        unique=True,
        db_index=True,
        help_text=_('Unique identifier for this conversion')
    )
    
    revenue = models.DecimalField(
        _('Revenue'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Revenue generated by this conversion')
    )
    
    currency = models.CharField(
        _('Currency'),
        max_length=3,
        default='USD',
        help_text=_('Currency for revenue')
    )
    
    # Tracking data
    ip_address = models.GenericIPAddressField(
        _('IP Address'),
        help_text=_('IP address of the conversion')
    )
    
    user_agent = models.TextField(
        _('User Agent'),
        blank=True,
        help_text=_('User agent string of the conversion')
    )
    
    referrer = models.URLField(
        _('Referrer'),
        max_length=500,
        blank=True,
        help_text=_('Referrer URL of the conversion')
    )
    
    # Attribution data
    click_id = models.CharField(
        _('Click ID'),
        max_length=100,
        blank=True,
        db_index=True,
        help_text=_('Click ID for attribution')
    )
    
    affiliate_id = models.CharField(
        _('Affiliate ID'),
        max_length=100,
        blank=True,
        db_index=True,
        help_text=_('Affiliate ID for attribution')
    )
    
    sub_id = models.CharField(
        _('Sub ID'),
        max_length=100,
        blank=True,
        help_text=_('Sub ID for attribution')
    )
    
    source = models.CharField(
        _('Source'),
        max_length=100,
        blank=True,
        help_text=_('Traffic source')
    )
    
    medium = models.CharField(
        _('Medium'),
        max_length=100,
        blank=True,
        help_text=_('Traffic medium')
    )
    
    campaign_name = models.CharField(
        _('Campaign Name'),
        max_length=200,
        blank=True,
        help_text=_('Campaign name from tracking')
    )
    
    # Custom parameters
    custom_parameters = models.JSONField(
        _('Custom Parameters'),
        default=dict,
        blank=True,
        help_text=_('Custom tracking parameters')
    )
    
    # Quality and fraud
    fraud_score = models.FloatField(
        _('Fraud Score'),
        default=0.0,
        help_text=_('Fraud detection score (0.0-1.0)')
    )
    
    quality_score = models.FloatField(
        _('Quality Score'),
        default=0.0,
        help_text=_('Quality score (0.0-1.0)')
    )
    
    is_flagged = models.BooleanField(
        _('Is Flagged'),
        default=False,
        help_text=_('Whether conversion is flagged for review')
    )
    
    # Status and approval
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=[
            ('pending', _('Pending')),
            ('approved', _('Approved')),
            ('rejected', _('Rejected')),
            ('flagged', _('Flagged')),
        ],
        default='pending',
        db_index=True,
        help_text=_('Current conversion status')
    )
    
    rejection_reason = models.TextField(
        _('Rejection Reason'),
        blank=True,
        help_text=_('Reason for rejection if rejected')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this conversion was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this conversion was last updated')
    )
    
    approved_at = models.DateTimeField(
        _('Approved At'),
        null=True,
        blank=True,
        help_text=_('When this conversion was approved')
    )
    
    rejected_at = models.DateTimeField(
        _('Rejected At'),
        null=True,
        blank=True,
        help_text=_('When this conversion was rejected')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        verbose_name = _('Conversion')
        verbose_name_plural = _('Conversions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser', 'created_at'], name='idx_advertiser_created_at_553'),
            models.Index(fields=['offer', 'created_at'], name='idx_offer_created_at_554'),
            models.Index(fields=['status', 'created_at'], name='idx_status_created_at_555'),
            models.Index(fields=['conversion_id'], name='idx_conversion_id_556'),
            models.Index(fields=['click_id'], name='idx_click_id_557'),
            models.Index(fields=['affiliate_id'], name='idx_affiliate_id_558'),
            models.Index(fields=['fraud_score'], name='idx_fraud_score_559'),
        ]
    
    def __str__(self):
        return f"{self.conversion_id} - {self.advertiser.company_name}"
    
    def clean(self):
        """Validate conversion data."""
        super().clean()
        
        if self.revenue < 0:
            raise ValidationError(_('Revenue cannot be negative'))
        
        if self.fraud_score < 0 or self.fraud_score > 1:
            raise ValidationError(_('Fraud score must be between 0 and 1'))
        
        if self.quality_score < 0 or self.quality_score > 1:
            raise ValidationError(_('Quality score must be between 0 and 1'))
    
    def approve(self):
        """Approve this conversion."""
        self.status = 'approved'
        self.approved_at = timezone.now()
        self.rejected_at = None
        self.rejection_reason = ''
        self.save()
    
    def reject(self, reason=''):
        """Reject this conversion."""
        self.status = 'rejected'
        self.rejected_at = timezone.now()
        self.approved_at = None
        self.rejection_reason = reason
        self.save()
    
    def flag(self):
        """Flag this conversion for review."""
        self.status = 'flagged'
        self.is_flagged = True
        self.save()
    
    @property
    def is_approved(self):
        """Check if conversion is approved."""
        return self.status == 'approved'
    
    @property
    def is_rejected(self):
        """Check if conversion is rejected."""
        return self.status == 'rejected'
    
    @property
    def is_pending(self):
        """Check if conversion is pending."""
        return self.status == 'pending'
    
    def get_attribution_data(self):
        """Get attribution data as dictionary."""
        return {
            'click_id': self.click_id,
            'affiliate_id': self.affiliate_id,
            'sub_id': self.sub_id,
            'source': self.source,
            'medium': self.medium,
            'campaign_name': self.campaign_name,
            'custom_parameters': self.custom_parameters,
        }
    
    def get_quality_metrics(self):
        """Get quality metrics."""
        return {
            'fraud_score': self.fraud_score,
            'quality_score': self.quality_score,
            'is_flagged': self.is_flagged,
            'status': self.status,
        }


class ConversionEvent(models.Model):
    """
    Model for managing conversion events.
    
    Stores conversion event configurations including
    payout amounts and deduplication rules.
    """
    
    # Core relationships
    offer = models.ForeignKey(
        'advertiser_portal_v2.AdvertiserOffer',
        on_delete=models.CASCADE,
        related_name='conversion_events',
        verbose_name=_('Offer'),
        help_text=_('Offer this event belongs to')
    )
    
    # Event details
    event_name = models.CharField(
        _('Event Name'),
        max_length=100,
        db_index=True,
        help_text=_('Name of conversion event')
    )
    
    event_type = models.CharField(
        _('Event Type'),
        max_length=50,
        choices=[
            ('install', _('App Install')),
            ('purchase', _('Purchase')),
            ('lead', _('Lead')),
            ('signup', _('Sign Up')),
            ('trial', _('Trial')),
            ('subscription', _('Subscription')),
            ('deposit', _('Deposit')),
            ('custom', _('Custom')),
        ],
        default='custom',
        help_text=_('Type of conversion event')
    )
    
    # Payout configuration
    payout_amount = models.DecimalField(
        _('Payout Amount'),
        max_digits=8,
        decimal_places=2,
        help_text=_('Amount paid for this conversion event')
    )
    
    payout_type = models.CharField(
        _('Payout Type'),
        max_length=20,
        choices=[
            ('fixed', _('Fixed')),
            ('percentage', _('Percentage')),
            ('tiered', _('Tiered')),
        ],
        default='fixed',
        help_text=_('Type of payout calculation')
    )
    
    currency = models.CharField(
        _('Currency'),
        max_length=3,
        default='USD',
        help_text=_('Currency code (ISO 4217)')
    )
    
    # Deduplication
    deduplication_window_hours = models.IntegerField(
        _('Deduplication Window (hours)'),
        default=24,
        help_text=_('Hours to deduplicate conversions')
    )
    
    deduplication_type = models.CharField(
        _('Deduplication Type'),
        max_length=20,
        choices=[
            ('ip', _('IP Address')),
            ('user_id', _('User ID')),
            ('device_id', _('Device ID')),
            ('transaction_id', _('Transaction ID')),
            ('custom', _('Custom')),
        ],
        default='ip',
        help_text=_('Field to use for deduplication')
    )
    
    # Status and configuration
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        db_index=True,
        help_text=_('Whether this event is active')
    )
    
    is_recurring = models.BooleanField(
        _('Is Recurring'),
        default=False,
        help_text=_('Whether this is a recurring event')
    )
    
    recurrence_period = models.IntegerField(
        _('Recurrence Period'),
        null=True,
        blank=True,
        help_text=_('Period for recurring events in hours')
    )
    
    # Validation rules
    validation_rules = models.JSONField(
        _('Validation Rules'),
        default=dict,
        blank=True,
        help_text=_('Rules for validating conversion events')
    )
    
    # Custom parameters
    required_params = models.JSONField(
        _('Required Parameters'),
        default=list,
        blank=True,
        help_text=_('Required parameters for this event')
    )
    
    optional_params = models.JSONField(
        _('Optional Parameters'),
        default=list,
        blank=True,
        help_text=_('Optional parameters for this event')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this event was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this event was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_conversion_event'
        verbose_name = _('Conversion Event')
        verbose_name_plural = _('Conversion Events')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['offer', 'is_active'], name='idx_offer_is_active_560'),
            models.Index(fields=['event_type', 'is_active'], name='idx_event_type_is_active_561'),
            models.Index(fields=['event_name', 'is_active'], name='idx_event_name_is_active_562'),
            models.Index(fields=['created_at'], name='idx_created_at_563'),
        ]
        unique_together = [
            ['offer', 'event_name'],
        ]
    
    def __str__(self):
        return f"{self.event_name} ({self.offer.title})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate payout amount
        if self.payout_amount <= 0:
            raise ValidationError(_('Payout amount must be positive'))
        
        # Validate deduplication window
        if self.deduplication_window_hours < 1:
            raise ValidationError(_('Deduplication window must be at least 1 hour'))
        
        # Validate recurrence period
        if self.is_recurring and not self.recurrence_period:
            raise ValidationError(_('Recurrence period is required for recurring events'))
        
        if self.recurrence_period and self.recurrence_period <= 0:
            raise ValidationError(_('Recurrence period must be positive'))
    
    @property
    def is_fixed_payout(self) -> bool:
        """Check if using fixed payout."""
        return self.payout_type == 'fixed'
    
    @property
    def is_percentage_payout(self) -> bool:
        """Check if using percentage payout."""
        return self.payout_type == 'percentage'
    
    @property
    def is_tiered_payout(self) -> bool:
        """Check if using tiered payout."""
        return self.payout_type == 'tiered'
    
    @property
    def deduplication_window_days(self) -> float:
        """Get deduplication window in days."""
        return self.deduplication_window_hours / 24
    
    def calculate_payout(self, base_amount: float = None, context: dict = None) -> float:
        """Calculate payout amount based on configuration."""
        if self.is_fixed_payout:
            return float(self.payout_amount)
        elif self.is_percentage_payout and base_amount:
            return float(base_amount * (self.payout_amount / 100))
        elif self.is_tiered_payout and context:
            # Implement tiered payout logic
            return float(self.payout_amount)
        else:
            return float(self.payout_amount)
    
    def is_duplicate_conversion(self, conversion_data: dict) -> bool:
        """Check if conversion is duplicate based on deduplication rules."""
        from django.utils import timezone as tz_utils
        
        cutoff_time = timezone.now() - timezone.timedelta(hours=self.deduplication_window_hours)
        
        # This would check against existing conversions
        # For now, return False (not duplicate)
        return False
    
    def validate_conversion_data(self, conversion_data: dict) -> dict:
        """Validate conversion data against rules."""
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Check required parameters
        for param in self.required_params:
            if param not in conversion_data:
                validation_result['is_valid'] = False
                validation_result['errors'].append(f"Missing required parameter: {param}")
        
        # Apply validation rules
        if self.validation_rules:
            for rule_name, rule_config in self.validation_rules.items():
                # Implement validation logic based on rule type
                pass
        
        return validation_result
    
    def get_event_summary(self) -> dict:
        """Get event configuration summary."""
        return {
            'event_name': self.event_name,
            'event_type': self.event_type,
            'payout_amount': float(self.payout_amount),
            'payout_type': self.payout_type,
            'currency': self.currency,
            'deduplication_window_hours': self.deduplication_window_hours,
            'deduplication_type': self.deduplication_type,
            'is_active': self.is_active,
            'is_recurring': self.is_recurring,
            'recurrence_period': self.recurrence_period,
            'has_validation_rules': bool(self.validation_rules),
            'required_params_count': len(self.required_params),
            'optional_params_count': len(self.optional_params),
            'created_at': self.created_at.isoformat(),
        }


class TrackingDomain(models.Model):
    """
    Model for managing tracking domains.
    
    Stores domain information for tracking
    including SSL status and verification.
    """
    
    # Core relationships
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='tracking_domains',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this domain belongs to')
    )
    
    # Domain details
    domain = models.CharField(
        _('Domain'),
        max_length=255,
        db_index=True,
        help_text=_('Domain name for tracking')
    )
    
    subdomain = models.CharField(
        _('Subdomain'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('Subdomain for tracking')
    )
    
    # SSL configuration
    is_verified = models.BooleanField(
        _('Is Verified'),
        default=False,
        db_index=True,
        help_text=_('Whether domain ownership is verified')
    )
    
    ssl_status = models.CharField(
        _('SSL Status'),
        max_length=20,
        choices=[
            ('not_configured', _('Not Configured')),
            ('pending', _('Pending')),
            ('valid', _('Valid')),
            ('expired', _('Expired')),
            ('invalid', _('Invalid')),
        ],
        default='not_configured',
        db_index=True,
        help_text=_('SSL certificate status')
    )
    
    ssl_expires_at = models.DateTimeField(
        _('SSL Expires At'),
        null=True,
        blank=True,
        db_index=True,
        help_text=_('When SSL certificate expires')
    )
    
    ssl_certificate = models.TextField(
        _('SSL Certificate'),
        null=True,
        blank=True,
        help_text=_('SSL certificate content')
    )
    
    # Status and configuration
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        db_index=True,
        help_text=_('Whether this domain is active')
    )
    
    is_default = models.BooleanField(
        _('Is Default'),
        default=False,
        help_text=_('Whether this is the default domain')
    )
    
    # DNS configuration
    cname_record = models.CharField(
        _('CNAME Record'),
        max_length=255,
        null=True,
        blank=True,
        help_text=_('CNAME record for verification')
    )
    
    txt_record = models.CharField(
        _('TXT Record'),
        max_length=255,
        null=True,
        blank=True,
        help_text=_('TXT record for verification')
    )
    
    # Tracking configuration
    tracking_endpoint = models.URLField(
        _('Tracking Endpoint'),
        max_length=500,
        null=True,
        blank=True,
        help_text=_('Custom tracking endpoint URL')
    )
    
    custom_headers = models.JSONField(
        _('Custom Headers'),
        default=dict,
        blank=True,
        help_text=_('Custom headers for tracking requests')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this domain was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this domain was last updated')
    )
    
    verified_at = models.DateTimeField(
        _('Verified At'),
        null=True,
        blank=True,
        help_text=_('When domain was verified')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_tracking_domain'
        verbose_name = _('Tracking Domain')
        verbose_name_plural = _('Tracking Domains')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser', 'is_active'], name='idx_advertiser_is_active_564'),
            models.Index(fields=['domain', 'is_verified'], name='idx_domain_is_verified_565'),
            models.Index(fields=['ssl_status', 'ssl_expires_at'], name='idx_ssl_status_ssl_expires_081'),
            models.Index(fields=['is_default', 'is_active'], name='idx_is_default_is_active_567'),
            models.Index(fields=['created_at'], name='idx_created_at_568'),
        ]
        unique_together = [
            ['advertiser', 'domain'],
        ]
    
    def __str__(self):
        return f"{self.domain} ({self.advertiser.company_name})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate domain format
        if not self.domain:
            raise ValidationError(_('Domain is required'))
        
        # Validate SSL expiration
        if self.ssl_expires_at and self.ssl_expires_at <= timezone.now():
            if self.ssl_status == 'valid':
                self.ssl_status = 'expired'
    
    @property
    def full_domain(self) -> str:
        """Get full domain including subdomain."""
        if self.subdomain:
            return f"{self.subdomain}.{self.domain}"
        return self.domain
    
    @property
    def is_ssl_valid(self) -> bool:
        """Check if SSL certificate is valid."""
        return (
            self.ssl_status == 'valid' and
            self.ssl_expires_at and
            self.ssl_expires_at > timezone.now()
        )
    
    @property
    def ssl_days_remaining(self) -> int:
        """Get days remaining until SSL expires."""
        if self.ssl_expires_at:
            delta = self.ssl_expires_at - timezone.now()
            return max(delta.days, 0)
        return 0
    
    @property
    def needs_ssl_renewal(self) -> bool:
        """Check if SSL needs renewal."""
        return self.ssl_days_remaining <= 30
    
    def generate_verification_code(self) -> str:
        """Generate verification code for domain."""
        timestamp = str(int(timezone.now().timestamp()))
        random_str = secrets.token_hex(4)
        return f"verify_{timestamp}_{random_str}"
    
    def verify_domain_ownership(self, verification_code: str) -> bool:
        """Verify domain ownership using provided code."""
        # This would implement domain verification logic
        # For now, return True
        return True
    
    def check_ssl_status(self) -> dict:
        """Check SSL certificate status."""
        # This would implement SSL checking logic
        # For now, return placeholder
        return {
            'status': self.ssl_status,
            'expires_at': self.ssl_expires_at.isoformat() if self.ssl_expires_at else None,
            'days_remaining': self.ssl_days_remaining,
            'is_valid': self.is_ssl_valid,
            'needs_renewal': self.needs_ssl_renewal,
        }
    
    def get_domain_summary(self) -> dict:
        """Get domain configuration summary."""
        return {
            'domain': self.domain,
            'full_domain': self.full_domain,
            'is_verified': self.is_verified,
            'is_active': self.is_active,
            'is_default': self.is_default,
            'ssl_status': self.ssl_status,
            'ssl_expires_at': self.ssl_expires_at.isoformat() if self.ssl_expires_at else None,
            'ssl_days_remaining': self.ssl_days_remaining,
            'is_ssl_valid': self.is_ssl_valid,
            'needs_ssl_renewal': self.needs_ssl_renewal,
            'has_custom_tracking': bool(self.tracking_endpoint),
            'has_custom_headers': bool(self.custom_headers),
            'created_at': self.created_at.isoformat(),
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
        }


# Signal handlers for tracking models
        app_label = 'advertiser_portal_v2'
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=TrackingPixel)
def tracking_pixel_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for tracking pixels."""
    if created:
        logger.info(f"New tracking pixel created: {instance.name}")
        
        # Send notification to advertiser
        from .notification import AdvertiserNotification
        AdvertiserNotification.objects.create(
            advertiser=instance.advertiser,
            type='pixel_created',
            title=_('New Tracking Pixel Created'),
            message=_('Your tracking pixel "{instance.name}" has been created successfully.'),
        )

@receiver(post_save, sender=S2SPostback)
def s2s_postback_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for S2S postbacks."""
    if created:
        logger.info(f"New S2S postback created: {instance.advertiser.company_name}")
        
        # Send notification to advertiser
        from .notification import AdvertiserNotification
        AdvertiserNotification.objects.create(
            advertiser=instance.advertiser,
            type='postback_created',
            title=_('New S2S Postback Created'),
            message=_('Your S2S postback has been configured successfully.'),
        )

@receiver(post_save, sender=ConversionEvent)
def conversion_event_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for conversion events."""
    if created:
        logger.info(f"New conversion event created: {instance.event_name}")
        
        # Send notification to advertiser
        from .notification import AdvertiserNotification
        AdvertiserNotification.objects.create(
            advertiser=instance.offer.advertiser,
            type='conversion_event_created',
            title=_('New Conversion Event Created'),
            message=_('Your conversion event "{instance.event_name}" has been created successfully.'),
        )

@receiver(post_save, sender=TrackingDomain)
def tracking_domain_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for tracking domains."""
    if created:
        logger.info(f"New tracking domain created: {instance.domain}")
        
        # Send notification to advertiser
        from .notification import AdvertiserNotification
        AdvertiserNotification.objects.create(
            advertiser=instance.advertiser,
            type='domain_created',
            title=_('New Tracking Domain Created'),
            message=_('Your tracking domain "{instance.domain}" has been added successfully.'),
        )

@receiver(post_delete, sender=TrackingPixel)
def tracking_pixel_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for tracking pixels."""
    logger.info(f"Tracking pixel deleted: {instance.name}")

@receiver(post_delete, sender=S2SPostback)
def s2s_postback_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for S2S postbacks."""
    logger.info(f"S2S postback deleted: {instance.advertiser.company_name}")

@receiver(post_delete, sender=ConversionEvent)
def conversion_event_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for conversion events."""
    logger.info(f"Conversion event deleted: {instance.event_name}")

@receiver(post_delete, sender=TrackingDomain)
def tracking_domain_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for tracking domains."""
    logger.info(f"Tracking domain deleted: {instance.domain}")
