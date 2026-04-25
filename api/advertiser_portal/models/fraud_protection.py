"""
Fraud Protection Models for Advertiser Portal

This module contains models for managing fraud protection,
including fraud configurations, invalid click logs, and quality scores.
"""

import logging
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()
logger = logging.getLogger(__name__)


class AdvertiserFraudConfig(models.Model):
    """
    Model for managing advertiser fraud protection configuration.
    
    Stores fraud detection settings and rules for
    advertiser campaigns and offers.
    """
    
    # Core relationship
    advertiser = models.OneToOneField(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='fraud_config',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this fraud config belongs to')
    )
    
    # Basic fraud protection
    block_vpn = models.BooleanField(
        _('Block VPN'),
        default=True,
        help_text=_('Whether to block VPN traffic')
    )
    
    block_proxy = models.BooleanField(
        _('Block Proxy'),
        default=True,
        help_text=_('Whether to block proxy traffic')
    )
    
    block_bots = models.BooleanField(
        _('Block Bots'),
        default=True,
        help_text=_('Whether to block bot traffic')
    )
    
    # Time-based protection
    min_session_seconds = models.IntegerField(
        _('Min Session Seconds'),
        default=5,
        help_text=_('Minimum session duration in seconds')
    )
    
    max_conversions_per_ip_per_day = models.IntegerField(
        _('Max Conversions Per IP Per Day'),
        default=10,
        help_text=_('Maximum conversions per IP per day')
    )
    
    max_conversions_per_user_per_day = models.IntegerField(
        _('Max Conversions Per User Per Day'),
        default=5,
        help_text=_('Maximum conversions per user per day')
    )
    
    max_conversions_per_device_per_day = models.IntegerField(
        _('Max Conversions Per Device Per Day'),
        default=8,
        help_text=_('Maximum conversions per device per day')
    )
    
    # Geographic protection
    block_high_risk_countries = models.BooleanField(
        _('Block High Risk Countries'),
        default=False,
        help_text=_('Whether to block high-risk countries')
    )
    
    blocked_countries = models.JSONField(
        _('Blocked Countries'),
        default=list,
        blank=True,
        help_text=_('List of blocked country codes')
    )
    
    allowed_countries = models.JSONField(
        _('Allowed Countries'),
        default=list,
        blank=True,
        help_text=_('List of allowed country codes (empty = all)')
    )
    
    # Device protection
    block_high_risk_devices = models.BooleanField(
        _('Block High Risk Devices'),
        default=False,
        help_text=_('Whether to block high-risk devices')
    )
    
    blocked_devices = models.JSONField(
        _('Blocked Devices'),
        default=list,
        blank=True,
        help_text=_('List of blocked device types')
    )
    
    blocked_user_agents = models.JSONField(
        _('Blocked User Agents'),
        default=list,
        blank=True,
        help_text=_('List of blocked user agent patterns')
    )
    
    # IP-based protection
    block_known_fraud_ips = models.BooleanField(
        _('Block Known Fraud IPs'),
        default=True,
        help_text=_('Whether to block known fraudulent IP addresses')
    )
    
    block_datacenter_ips = models.BooleanField(
        _('Block Datacenter IPs'),
        default=True,
        help_text=_('Whether to block datacenter IP ranges')
    )
    
    ip_whitelist = models.JSONField(
        _('IP Whitelist'),
        default=list,
        blank=True,
        help_text=_('List of whitelisted IP addresses')
    )
    
    # Behavioral protection
    block_rapid_clicks = models.BooleanField(
        _('Block Rapid Clicks'),
        default=True,
        help_text=_('Whether to block rapid successive clicks')
    )
    
    max_clicks_per_minute = models.IntegerField(
        _('Max Clicks Per Minute'),
        default=10,
        help_text=_('Maximum clicks per minute per IP')
    )
    
    block_same_ip_conversions = models.BooleanField(
        _('Block Same IP Conversions'),
        default=True,
        help_text=_('Whether to block multiple conversions from same IP')
    )
    
    min_time_between_conversions = models.IntegerField(
        _('Min Time Between Conversions'),
        default=300,
        help_text=_('Minimum time between conversions in seconds')
    )
    
    # Advanced protection
    enable_device_fingerprinting = models.BooleanField(
        _('Enable Device Fingerprinting'),
        default=False,
        help_text=_('Whether to enable device fingerprinting')
    )
    
    enable_ip_reputation_check = models.BooleanField(
        _('Enable IP Reputation Check'),
        default=True,
        help_text=_('Whether to enable IP reputation checking')
    )
    
    enable_velocity_checking = models.BooleanField(
        _('Enable Velocity Checking'),
        default=True,
        help_text=_('Whether to enable velocity checking')
    )
    
    # Scoring thresholds
    fraud_score_threshold = models.IntegerField(
        _('Fraud Score Threshold'),
        default=70,
        help_text=_('Fraud score threshold for blocking')
    )
    
    high_risk_threshold = models.IntegerField(
        _('High Risk Threshold'),
        default=80,
        help_text=_('High risk threshold for manual review')
    )
    
    # Action configuration
    auto_block_threshold = models.IntegerField(
        _('Auto Block Threshold'),
        default=90,
        help_text=_('Auto-block threshold for fraud score')
    )
    
    manual_review_threshold = models.IntegerField(
        _('Manual Review Threshold'),
        default=70,
        help_text=_('Manual review threshold for fraud score')
    )
    
    # Notification settings
    fraud_alert_email = models.EmailField(
        _('Fraud Alert Email'),
        null=True,
        blank=True,
        help_text=_('Email address for fraud alerts')
    )
    
    webhook_url = models.URLField(
        _('Webhook URL'),
        max_length=500,
        null=True,
        blank=True,
        help_text=_('Webhook URL for real-time fraud alerts')
    )
    
    # Status
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        help_text=_('Whether this fraud config is active')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this fraud config was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this fraud config was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_fraud_config'
        verbose_name = _('Advertiser Fraud Config')
        verbose_name_plural = _('Advertiser Fraud Configs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser'], name='idx_advertiser_437'),
            models.Index(fields=['is_active'], name='idx_is_active_438'),
            models.Index(fields=['created_at'], name='idx_created_at_439'),
        ]
    
    def __str__(self):
        return f"Fraud Config: {self.advertiser.company_name}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate time thresholds
        if self.min_session_seconds < 0:
            raise ValidationError(_('Min session seconds cannot be negative'))
        
        if self.max_conversions_per_ip_per_day < 0:
            raise ValidationError(_('Max conversions per IP per day cannot be negative'))
        
        if self.max_conversions_per_user_per_day < 0:
            raise ValidationError(_('Max conversions per user per day cannot be negative'))
        
        if self.max_conversions_per_device_per_day < 0:
            raise ValidationError(_('Max conversions per device per day cannot be negative'))
        
        if self.max_clicks_per_minute < 0:
            raise ValidationError(_('Max clicks per minute cannot be negative'))
        
        if self.min_time_between_conversions < 0:
            raise ValidationError(_('Min time between conversions cannot be negative'))
        
        # Validate thresholds
        if self.fraud_score_threshold < 0 or self.fraud_score_threshold > 100:
            raise ValidationError(_('Fraud score threshold must be between 0 and 100'))
        
        if self.high_risk_threshold < 0 or self.high_risk_threshold > 100:
            raise ValidationError(_('High risk threshold must be between 0 and 100'))
        
        if self.auto_block_threshold < 0 or self.auto_block_threshold > 100:
            raise ValidationError(_('Auto block threshold must be between 0 and 100'))
        
        if self.manual_review_threshold < 0 or self.manual_review_threshold > 100:
            raise ValidationError(_('Manual review threshold must be between 0 and 100'))
    
    @property
    def is_strict_mode(self) -> bool:
        """Check if strict fraud protection is enabled."""
        return (
            self.block_vpn and
            self.block_proxy and
            self.block_bots and
            self.enable_ip_reputation_check
        )
    
    @property
    def has_geographic_protection(self) -> bool:
        """Check if geographic protection is enabled."""
        return (
            self.block_high_risk_countries or
            self.blocked_countries or
            self.allowed_countries
        )
    
    @property
    def has_device_protection(self) -> bool:
        """Check if device protection is enabled."""
        return (
            self.block_high_risk_devices or
            self.blocked_devices or
            self.blocked_user_agents
        )
    
    @property
    def has_behavioral_protection(self) -> bool:
        """Check if behavioral protection is enabled."""
        return (
            self.block_rapid_clicks or
            self.block_same_ip_conversions or
            self.enable_velocity_checking
        )
    
    def check_country_allowed(self, country_code: str) -> bool:
        """Check if country is allowed."""
        if self.block_high_risk_countries and country_code in self.blocked_countries:
            return False
        
        if self.allowed_countries and country_code not in self.allowed_countries:
            return False
        
        return True
    
    def check_device_allowed(self, device_type: str) -> bool:
        """Check if device is allowed."""
        if self.block_high_risk_devices and device_type in self.blocked_devices:
            return False
        
        return True
    
    def check_user_agent_allowed(self, user_agent: str) -> bool:
        """Check if user agent is allowed."""
        if not user_agent:
            return True
        
        for pattern in self.blocked_user_agents:
            if pattern.lower() in user_agent.lower():
                return False
        
        return True
    
    def check_ip_whitelisted(self, ip_address: str) -> bool:
        """Check if IP is whitelisted."""
        return ip_address in self.ip_whitelist
    
    def get_config_summary(self) -> dict:
        """Get fraud configuration summary."""
        return {
            'basic_protection': {
                'block_vpn': self.block_vpn,
                'block_proxy': self.block_proxy,
                'block_bots': self.block_bots,
            },
            'time_protection': {
                'min_session_seconds': self.min_session_seconds,
                'max_conversions_per_ip_per_day': self.max_conversions_per_ip_per_day,
                'max_conversions_per_user_per_day': self.max_conversions_per_user_per_day,
                'max_conversions_per_device_per_day': self.max_conversions_per_device_per_day,
            },
            'geographic_protection': {
                'block_high_risk_countries': self.block_high_risk_countries,
                'blocked_countries': self.blocked_countries,
                'allowed_countries': self.allowed_countries,
                'has_protection': self.has_geographic_protection,
            },
            'device_protection': {
                'block_high_risk_devices': self.block_high_risk_devices,
                'blocked_devices': self.blocked_devices,
                'blocked_user_agents': self.blocked_user_agents,
                'has_protection': self.has_device_protection,
            },
            'ip_protection': {
                'block_known_fraud_ips': self.block_known_fraud_ips,
                'block_datacenter_ips': self.block_datacenter_ips,
                'ip_whitelist': self.ip_whitelist,
            },
            'behavioral_protection': {
                'block_rapid_clicks': self.block_rapid_clicks,
                'max_clicks_per_minute': self.max_clicks_per_minute,
                'block_same_ip_conversions': self.block_same_ip_conversions,
                'min_time_between_conversions': self.min_time_between_conversions,
                'has_protection': self.has_behavioral_protection,
            },
            'advanced_protection': {
                'enable_device_fingerprinting': self.enable_device_fingerprinting,
                'enable_ip_reputation_check': self.enable_ip_reputation_check,
                'enable_velocity_checking': self.enable_velocity_checking,
            },
            'thresholds': {
                'fraud_score_threshold': self.fraud_score_threshold,
                'high_risk_threshold': self.high_risk_threshold,
                'auto_block_threshold': self.auto_block_threshold,
                'manual_review_threshold': self.manual_review_threshold,
            },
            'notifications': {
                'fraud_alert_email': self.fraud_alert_email,
                'webhook_url': self.webhook_url,
            },
            'is_active': self.is_active,
            'is_strict_mode': self.is_strict_mode,
        }


class InvalidClickLog(models.Model):
    """
    Model for logging invalid clicks.
    
    Stores information about blocked or suspicious clicks
    for fraud analysis and prevention.
    """
    
    # Core relationships
    offer = models.ForeignKey(
        'advertiser_portal_v2.AdvertiserOffer',
        on_delete=models.CASCADE,
        related_name='invalid_clicks',
        null=True,
        blank=True,
        verbose_name=_('Offer'),
        help_text=_('Offer this click belongs to')
    )
    
    campaign = models.ForeignKey(
        'advertiser_portal_v2.AdCampaign',
        on_delete=models.CASCADE,
        related_name='invalid_clicks',
        null=True,
        blank=True,
        verbose_name=_('Campaign'),
        help_text=_('Campaign this click belongs to')
    )
    
    # Click information
    ip_address = models.GenericIPAddressField(
        _('IP Address'),
        db_index=True,
        help_text=_('IP address of the click')
    )
    
    user_agent = models.TextField(
        _('User Agent'),
        null=True,
        blank=True,
        help_text=_('User agent string')
    )
    
    referer = models.URLField(
        _('Referer'),
        max_length=500,
        null=True,
        blank=True,
        help_text=_('Referer URL')
    )
    
    # Geographic information
    country = models.CharField(
        _('Country'),
        max_length=2,
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Country code (ISO 3166-1 alpha-2)')
    )
    
    region = models.CharField(
        _('Region'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('Region or state')
    )
    
    city = models.CharField(
        _('City'),
        max_length=100,
        null=True,
        blank=True,
        help_text=_('City name')
    )
    
    # Device information
    device_type = models.CharField(
        _('Device Type'),
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Type of device')
    )
    
    operating_system = models.CharField(
        _('Operating System'),
        max_length=50,
        null=True,
        blank=True,
        help_text=_('Operating system')
    )
    
    browser = models.CharField(
        _('Browser'),
        max_length=50,
        null=True,
        blank=True,
        help_text=_('Browser type')
    )
    
    # Blocking information
    reason = models.CharField(
        _('Reason'),
        max_length=100,
        choices=[
            ('vpn_detected', _('VPN Detected')),
            ('proxy_detected', _('Proxy Detected')),
            ('bot_detected', _('Bot Detected')),
            ('datacenter_ip', _('Datacenter IP')),
            ('rapid_clicks', _('Rapid Clicks')),
            ('same_ip_conversions', _('Same IP Conversions')),
            ('invalid_session', _('Invalid Session')),
            ('blacklisted_ip', _('Blacklisted IP')),
            ('blacklisted_device', _('Blacklisted Device')),
            ('blacklisted_user_agent', _('Blacklisted User Agent')),
            ('high_risk_country', _('High Risk Country')),
            ('velocity_check', _('Velocity Check')),
            ('reputation_check', _('Reputation Check')),
            ('fingerprint_mismatch', _('Fingerprint Mismatch')),
            ('custom_rule', _('Custom Rule')),
        ],
        help_text=_('Reason for blocking the click')
    )
    
    fraud_score = models.IntegerField(
        _('Fraud Score'),
        default=0,
        help_text=_('Fraud risk score (0-100)')
    )
    
    risk_level = models.CharField(
        _('Risk Level'),
        max_length=20,
        choices=[
            ('low', _('Low')),
            ('medium', _('Medium')),
            ('high', _('High')),
            ('critical', _('Critical')),
        ],
        default='medium',
        db_index=True,
        help_text=_('Risk level of the click')
    )
    
    # Timestamps
    click_time = models.DateTimeField(
        _('Click Time'),
        db_index=True,
        help_text=_('When the click occurred')
    )
    
    blocked_at = models.DateTimeField(
        _('Blocked At'),
        auto_now_add=True,
        db_index=True,
        help_text=_('When the click was blocked')
    )
    
    # Additional data
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional metadata about the invalid click')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_invalid_click'
        verbose_name = _('Invalid Click')
        verbose_name_plural = _('Invalid Clicks')
        ordering = ['-blocked_at']
        indexes = [
            models.Index(fields=['offer', 'blocked_at'], name='idx_offer_blocked_at_440'),
            models.Index(fields=['campaign', 'blocked_at'], name='idx_campaign_blocked_at_441'),
            models.Index(fields=['ip_address', 'blocked_at'], name='idx_ip_address_blocked_at_442'),
            models.Index(fields=['country', 'blocked_at'], name='idx_country_blocked_at_443'),
            models.Index(fields=['device_type', 'blocked_at'], name='idx_device_type_blocked_at_444'),
            models.Index(fields=['risk_level', 'blocked_at'], name='idx_risk_level_blocked_at_445'),
            models.Index(fields=['reason', 'blocked_at'], name='idx_reason_blocked_at_446'),
            models.Index(fields=['click_time'], name='idx_click_time_447'),
            models.Index(fields=['blocked_at'], name='idx_blocked_at_448'),
        ]
    
    def __str__(self):
        return f"Invalid Click: {self.ip_address} - {self.reason}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate fraud score
        if self.fraud_score < 0 or self.fraud_score > 100:
            raise ValidationError(_('Fraud score must be between 0 and 100'))
    
    @property
    def is_high_risk(self) -> bool:
        """Check if click is high risk."""
        return self.risk_level in ['high', 'critical']
    
    @property
    def is_critical_risk(self) -> bool:
        """Check if click is critical risk."""
        return self.risk_level == 'critical'
    
    @property
    def location_display(self) -> str:
        """Get formatted location."""
        parts = [self.country, self.region, self.city]
        return ', '.join(filter(None, parts))
    
    @property
    def device_info_display(self) -> str:
        """Get formatted device info."""
        parts = [self.device_type, self.operating_system, self.browser]
        return ', '.join(filter(None, parts))
    
    @property
    def reason_display(self) -> str:
        """Get human-readable reason."""
        reason_names = {
            'vpn_detected': _('VPN Detected'),
            'proxy_detected': _('Proxy Detected'),
            'bot_detected': _('Bot Detected'),
            'datacenter_ip': _('Datacenter IP'),
            'rapid_clicks': _('Rapid Clicks'),
            'same_ip_conversions': _('Same IP Conversions'),
            'invalid_session': _('Invalid Session'),
            'blacklisted_ip': _('Blacklisted IP'),
            'blacklisted_device': _('Blacklisted Device'),
            'blacklisted_user_agent': _('Blacklisted User Agent'),
            'high_risk_country': _('High Risk Country'),
            'velocity_check': _('Velocity Check'),
            'reputation_check': _('Reputation Check'),
            'fingerprint_mismatch': _('Fingerprint Mismatch'),
            'custom_rule': _('Custom Rule'),
        }
        return reason_names.get(self.reason, self.reason)
    
    @property
    def age_hours(self) -> int:
        """Get age in hours."""
        if self.blocked_at:
            return int((timezone.now() - self.blocked_at).total_seconds() / 3600)
        return 0
    
    def get_click_summary(self) -> dict:
        """Get click summary."""
        return {
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'referer': self.referer,
            'location': {
                'country': self.country,
                'region': self.region,
                'city': self.city,
                'display': self.location_display,
            },
            'device': {
                'type': self.device_type,
                'operating_system': self.operating_system,
                'browser': self.browser,
                'display': self.device_info_display,
            },
            'blocking': {
                'reason': self.reason,
                'reason_display': self.reason_display,
                'fraud_score': self.fraud_score,
                'risk_level': self.risk_level,
                'is_high_risk': self.is_high_risk,
                'is_critical_risk': self.is_critical_risk,
            },
            'timestamps': {
                'click_time': self.click_time.isoformat(),
                'blocked_at': self.blocked_at.isoformat(),
                'age_hours': self.age_hours,
            },
            'offer_id': self.offer.id if self.offer else None,
            'campaign_id': self.campaign.id if self.campaign else None,
            'metadata': self.metadata,
        }


class ConversionQualityScore(models.Model):
    """
    Model for tracking conversion quality scores.
    
    Stores quality metrics and fraud rates for
    conversions and offers.
    """
    
    # Core relationships
    offer = models.ForeignKey(
        'advertiser_portal_v2.AdvertiserOffer',
        on_delete=models.CASCADE,
        related_name='quality_scores',
        verbose_name=_('Offer'),
        help_text=_('Offer this quality score belongs to')
    )
    
    # Date information
    date = models.DateField(
        _('Date'),
        db_index=True,
        help_text=_('Date for this quality score')
    )
    
    # Quality metrics
    quality_score = models.DecimalField(
        _('Quality Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Overall quality score (0-100)')
    )
    
    fraud_rate = models.DecimalField(
        _('Fraud Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Fraud rate percentage')
    )
    
    valid_conversion_rate = models.DecimalField(
        _('Valid Conversion Rate'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Valid conversion rate percentage')
    )
    
    # Performance metrics
    total_conversions = models.IntegerField(
        _('Total Conversions'),
        default=0,
        help_text=_('Total number of conversions')
    )
    
    valid_conversions = models.IntegerField(
        _('Valid Conversions'),
        default=0,
        help_text=_('Number of valid conversions')
    )
    
    invalid_conversions = models.IntegerField(
        _('Invalid Conversions'),
        default=0,
        help_text=_('Number of invalid conversions')
    )
    
    pending_conversions = models.IntegerField(
        _('Pending Conversions'),
        default=0,
        help_text=_('Number of pending conversions')
    )
    
    # Financial metrics
    total_revenue = models.DecimalField(
        _('Total Revenue'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Total revenue from conversions')
    )
    
    valid_revenue = models.DecimalField(
        _('Valid Revenue'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Revenue from valid conversions')
    )
    
    invalid_revenue = models.DecimalField(
        _('Invalid Revenue'),
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text=_('Revenue from invalid conversions')
    )
    
    # Quality components
    ip_quality_score = models.DecimalField(
        _('IP Quality Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Quality score based on IP addresses')
    )
    
    device_quality_score = models.DecimalField(
        _('Device Quality Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Quality score based on device types')
    )
    
    geographic_quality_score = models.DecimalField(
        _('Geographic Quality Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Quality score based on geographic distribution')
    )
    
    temporal_quality_score = models.DecimalField(
        _('Temporal Quality Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Quality score based on timing patterns')
    )
    
    behavioral_quality_score = models.DecimalField(
        _('Behavioral Quality Score'),
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text=_('Quality score based on user behavior')
    )
    
    # Quality grades
    quality_grade = models.CharField(
        _('Quality Grade'),
        max_length=2,
        choices=[
            ('A+', _('A+')),
            ('A', _('A')),
            ('A-', _('A-')),
            ('B+', _('B+')),
            ('B', _('B')),
            ('B-', _('B-')),
            ('C+', _('C+')),
            ('C', _('C')),
            ('C-', _('C-')),
            ('D+', _('D+')),
            ('D', _('D')),
            ('D-', _('D-')),
            ('F', _('F')),
        ],
        default='C',
        help_text=_('Quality grade (A+ to F)')
    )
    
    fraud_grade = models.CharField(
        _('Fraud Grade'),
        max_length=2,
        choices=[
            ('A+', _('A+')),
            ('A', _('A')),
            ('A-', _('A-')),
            ('B+', _('B+')),
            ('B', _('B')),
            ('B-', _('B-')),
            ('C+', _('C+')),
            ('C', _('C')),
            ('C-', _('C-')),
            ('D+', _('D+')),
            ('D', _('D')),
            ('D-', _('D-')),
            ('F', _('F')),
        ],
        default='C',
        help_text=_('Fraud grade (A+ to F)')
    )
    
    # Trends and analysis
    quality_trend = models.CharField(
        _('Quality Trend'),
        max_length=20,
        choices=[
            ('improving', _('Improving')),
            ('stable', _('Stable')),
            ('declining', _('Declining')),
            ('volatile', _('Volatile')),
        ],
        default='stable',
        help_text=_('Quality trend over time')
    )
    
    fraud_trend = models.CharField(
        _('Fraud Trend'),
        max_length=20,
        choices=[
            ('decreasing', _('Decreasing')),
            ('stable', _('Stable')),
            ('increasing', _('Increasing')),
            ('volatile', _('Volatile')),
        ],
        default='stable',
        help_text=_('Fraud trend over time')
    )
    
    # Recommendations
    recommendations = models.JSONField(
        _('Recommendations'),
        default=list,
        blank=True,
        help_text=_('List of improvement recommendations')
    )
    
    alerts = models.JSONField(
        _('Alerts'),
        default=list,
        blank=True,
        help_text=_('List of active alerts')
    )
    
    # Additional data
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional quality metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this quality score was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this quality score was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        db_table = 'advertiser_portal_conversion_quality'
        verbose_name = _('Conversion Quality Score')
        verbose_name_plural = _('Conversion Quality Scores')
        ordering = ['-date']
        indexes = [
            models.Index(fields=['offer', 'date'], name='idx_offer_date_449'),
            models.Index(fields=['date'], name='idx_date_450'),
            models.Index(fields=['quality_score'], name='idx_quality_score_451'),
            models.Index(fields=['fraud_rate'], name='idx_fraud_rate_452'),
            models.Index(fields=['quality_grade'], name='idx_quality_grade_453'),
            models.Index(fields=['fraud_grade'], name='idx_fraud_grade_454'),
            models.Index(fields=['created_at'], name='idx_created_at_455'),
        ]
        unique_together = [
            ['offer', 'date'],
        ]
    
    def __str__(self):
        return f"Quality Score: {self.offer.title} - {self.date}"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        # Validate scores
        for field_name in ['quality_score', 'fraud_rate', 'valid_conversion_rate']:
            score = getattr(self, field_name)
            if score < 0 or score > 100:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} must be between 0 and 100'))
        
        # Validate counts
        for field_name in ['total_conversions', 'valid_conversions', 'invalid_conversions', 'pending_conversions']:
            count = getattr(self, field_name)
            if count < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
        
        # Validate revenue amounts
        for field_name in ['total_revenue', 'valid_revenue', 'invalid_revenue']:
            amount = getattr(self, field_name)
            if amount < 0:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} cannot be negative'))
        
        # Validate component scores
        for field_name in ['ip_quality_score', 'device_quality_score', 'geographic_quality_score', 
                         'temporal_quality_score', 'behavioral_quality_score']:
            score = getattr(self, field_name)
            if score < 0 or score > 100:
                raise ValidationError(_(f'{field_name.replace("_", " ").title()} must be between 0 and 100'))
    
    def save(self, *args, **kwargs):
        """Override save to add additional logic."""
        # Calculate derived metrics
        self._calculate_derived_metrics()
        
        # Calculate grades
        self._calculate_grades()
        
        # Calculate trends
        self._calculate_trends()
        
        # Generate recommendations
        self._generate_recommendations()
        
        # Generate alerts
        self._generate_alerts()
        
        super().save(*args, **kwargs)
    
    def _calculate_derived_metrics(self):
        """Calculate derived metrics."""
        # Calculate rates
        if self.total_conversions > 0:
            self.valid_conversion_rate = (self.valid_conversions / self.total_conversions) * 100
            self.fraud_rate = (self.invalid_conversions / self.total_conversions) * 100
        else:
            self.valid_conversion_rate = 0
            self.fraud_rate = 0
    
    def _calculate_grades(self):
        """Calculate quality and fraud grades."""
        # Quality grade based on quality score
        if self.quality_score >= 95:
            self.quality_grade = 'A+'
        elif self.quality_score >= 90:
            self.quality_grade = 'A'
        elif self.quality_score >= 85:
            self.quality_grade = 'A-'
        elif self.quality_score >= 80:
            self.quality_grade = 'B+'
        elif self.quality_score >= 75:
            self.quality_grade = 'B'
        elif self.quality_score >= 70:
            self.quality_grade = 'B-'
        elif self.quality_score >= 65:
            self.quality_grade = 'C+'
        elif self.quality_score >= 60:
            self.quality_grade = 'C'
        elif self.quality_score >= 55:
            self.quality_grade = 'C-'
        elif self.quality_score >= 50:
            self.quality_grade = 'D+'
        elif self.quality_score >= 45:
            self.quality_grade = 'D'
        elif self.quality_score >= 40:
            self.quality_grade = 'D-'
        else:
            self.quality_grade = 'F'
        
        # Fraud grade based on fraud rate (lower is better)
        if self.fraud_rate <= 1:
            self.fraud_grade = 'A+'
        elif self.fraud_rate <= 2:
            self.fraud_grade = 'A'
        elif self.fraud_rate <= 3:
            self.fraud_grade = 'A-'
        elif self.fraud_rate <= 5:
            self.fraud_grade = 'B+'
        elif self.fraud_rate <= 7:
            self.fraud_grade = 'B'
        elif self.fraud_rate <= 10:
            self.fraud_grade = 'B-'
        elif self.fraud_rate <= 15:
            self.fraud_grade = 'C+'
        elif self.fraud_rate <= 20:
            self.fraud_grade = 'C'
        elif self.fraud_rate <= 25:
            self.fraud_grade = 'C-'
        elif self.fraud_rate <= 35:
            self.fraud_grade = 'D+'
        elif self.fraud_rate <= 50:
            self.fraud_grade = 'D'
        elif self.fraud_rate <= 75:
            self.fraud_grade = 'D-'
        else:
            self.fraud_grade = 'F'
    
    def _calculate_trends(self):
        """Calculate quality and fraud trends."""
        # This would implement trend calculation based on historical data
        # For now, use placeholder logic
        if self.quality_score >= 80:
            self.quality_trend = 'improving'
        elif self.quality_score >= 60:
            self.quality_trend = 'stable'
        else:
            self.quality_trend = 'declining'
        
        if self.fraud_rate <= 5:
            self.fraud_trend = 'decreasing'
        elif self.fraud_rate <= 15:
            self.fraud_trend = 'stable'
        else:
            self.fraud_trend = 'increasing'
    
    def _generate_recommendations(self):
        """Generate improvement recommendations."""
        recommendations = []
        
        # Quality recommendations
        if self.quality_score < 70:
            recommendations.append("Consider improving offer quality and targeting")
        
        if self.ip_quality_score < 60:
            recommendations.append("Review IP-based fraud protection settings")
        
        if self.device_quality_score < 60:
            recommendations.append("Consider device fingerprinting for better protection")
        
        if self.geographic_quality_score < 60:
            recommendations.append("Review geographic targeting and fraud patterns")
        
        # Fraud recommendations
        if self.fraud_rate > 20:
            recommendations.append("High fraud rate detected - immediate action required")
        
        if self.fraud_rate > 10:
            recommendations.append("Consider stricter fraud protection measures")
        
        self.recommendations = recommendations
    
    def _generate_alerts(self):
        """Generate alerts for quality issues."""
        alerts = []
        
        # Critical alerts
        if self.fraud_rate > 30:
            alerts.append({
                'type': 'critical',
                'message': 'Critical fraud rate detected',
                'action_required': True
            })
        
        # High priority alerts
        if self.fraud_rate > 20:
            alerts.append({
                'type': 'high',
                'message': 'High fraud rate detected',
                'action_required': True
            })
        
        # Medium priority alerts
        if self.quality_score < 50:
            alerts.append({
                'type': 'medium',
                'message': 'Low quality score detected',
                'action_required': False
            })
        
        self.alerts = alerts
    
    @property
    def is_high_quality(self) -> bool:
        """Check if quality is high."""
        return self.quality_score >= 80
    
    @property
    def is_low_quality(self) -> bool:
        """Check if quality is low."""
        return self.quality_score < 60
    
    @property
    def is_high_fraud(self) -> bool:
        """Check if fraud rate is high."""
        return self.fraud_rate > 20
    
    @property
    def revenue_efficiency(self) -> float:
        """Calculate revenue efficiency."""
        if self.total_revenue > 0:
            return float((self.valid_revenue / self.total_revenue) * 100)
        return 0.0
    
    def get_quality_summary(self) -> dict:
        """Get quality score summary."""
        return {
            'offer_id': self.offer.id,
            'offer_title': self.offer.title,
            'date': self.date.isoformat(),
            'overall_metrics': {
                'quality_score': float(self.quality_score),
                'fraud_rate': float(self.fraud_rate),
                'valid_conversion_rate': float(self.valid_conversion_rate),
                'quality_grade': self.quality_grade,
                'fraud_grade': self.fraud_grade,
                'quality_trend': self.quality_trend,
                'fraud_trend': self.fraud_trend,
                'is_high_quality': self.is_high_quality,
                'is_low_quality': self.is_low_quality,
                'is_high_fraud': self.is_high_fraud,
            },
            'conversion_metrics': {
                'total_conversions': self.total_conversions,
                'valid_conversions': self.valid_conversions,
                'invalid_conversions': self.invalid_conversions,
                'pending_conversions': self.pending_conversions,
            },
            'financial_metrics': {
                'total_revenue': float(self.total_revenue),
                'valid_revenue': float(self.valid_revenue),
                'invalid_revenue': float(self.invalid_revenue),
                'revenue_efficiency': self.revenue_efficiency,
            },
            'component_scores': {
                'ip_quality_score': float(self.ip_quality_score),
                'device_quality_score': float(self.device_quality_score),
                'geographic_quality_score': float(self.geographic_quality_score),
                'temporal_quality_score': float(self.temporal_quality_score),
                'behavioral_quality_score': float(self.behavioral_quality_score),
            },
            'recommendations': self.recommendations,
            'alerts': self.alerts,
            'metadata': self.metadata,
        }


# Signal handlers for fraud protection models
        app_label = 'advertiser_portal_v2'
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=AdvertiserFraudConfig)
def fraud_config_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for fraud configs."""
    if created:
        logger.info(f"New fraud config created: {instance.advertiser.company_name}")
        
        # Send notification to advertiser
        from .notification import AdvertiserNotification
        AdvertiserNotification.objects.create(
            advertiser=instance.advertiser,
            type='fraud_config_created',
            title=_('Fraud Protection Configured'),
            message=_('Your fraud protection settings have been configured successfully.'),
        )

@receiver(post_save, sender=InvalidClickLog)
def invalid_click_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for invalid clicks."""
    if created:
        logger.info(f"Invalid click logged: {instance.ip_address} - {instance.reason}")
        
        # Send alert if high risk
        if instance.is_critical_risk:
            from .notification import AdvertiserNotification
            AdvertiserNotification.objects.create(
                advertiser=instance.offer.advertiser if instance.offer else None,
                type='critical_fraud',
                title=_('Critical Fraud Alert'),
                message=f'Critical fraud detected: {instance.reason}',
            )

@receiver(post_save, sender=ConversionQualityScore)
def quality_score_post_save(sender, instance, created, **kwargs):
    """Handle post-save signal for quality scores."""
    if created:
        logger.info(f"Quality score created: {instance.offer.title} - {instance.date}")
        
        # Send alert if low quality
        if instance.is_low_quality:
            from .notification import AdvertiserNotification
            AdvertiserNotification.objects.create(
                advertiser=instance.offer.advertiser,
                type='low_quality',
                title=_('Low Quality Alert'),
                message=f'Low quality detected for offer: {instance.offer.title}',
            )

@receiver(post_delete, sender=AdvertiserFraudConfig)
def fraud_config_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for fraud configs."""
    logger.info(f"Fraud config deleted: {instance.advertiser.company_name}")

@receiver(post_delete, sender=InvalidClickLog)
def invalid_click_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for invalid clicks."""
    logger.info(f"Invalid click deleted: {instance.ip_address}")

@receiver(post_delete, sender=ConversionQualityScore)
def quality_score_post_delete(sender, instance, **kwargs):
    """Handle post-delete signal for quality scores."""
    logger.info(f"Quality score deleted: {instance.offer.title} - {instance.date}")


class ClickFraudSignal(models.Model):
    """
    Model for managing click fraud signals.
    
    Stores fraud detection signals and patterns
    for real-time fraud prevention.
    """
    
    # Core relationships
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='click_fraud_signals',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this signal belongs to')
    )
    
    offer = models.ForeignKey(
        'advertiser_portal_v2.AdvertiserOffer',
        on_delete=models.CASCADE,
        related_name='click_fraud_signals',
        null=True,
        blank=True,
        verbose_name=_('Offer'),
        help_text=_('Offer this signal belongs to')
    )
    
    # Signal data
    signal_type = models.CharField(
        _('Signal Type'),
        max_length=50,
        choices=[
            ('high_velocity', _('High Velocity')),
            ('ip_suspicious', _('Suspicious IP')),
            ('user_agent_anomaly', _('User Agent Anomaly')),
            ('geo_anomaly', _('Geo Anomaly')),
            ('time_pattern', _('Time Pattern')),
            ('conversion_anomaly', _('Conversion Anomaly')),
            ('device_fingerprint', _('Device Fingerprint')),
        ],
        help_text=_('Type of fraud signal')
    )
    
    severity = models.CharField(
        _('Severity'),
        max_length=20,
        choices=[
            ('low', _('Low')),
            ('medium', _('Medium')),
            ('high', _('High')),
            ('critical', _('Critical')),
        ],
        default='medium',
        help_text=_('Severity of the signal')
    )
    
    # Detection data
    ip_address = models.GenericIPAddressField(
        _('IP Address'),
        help_text=_('IP address that triggered the signal')
    )
    
    user_agent = models.TextField(
        _('User Agent'),
        blank=True,
        help_text=_('User agent string')
    )
    
    device_fingerprint = models.CharField(
        _('Device Fingerprint'),
        max_length=500,
        blank=True,
        help_text=_('Device fingerprint hash')
    )
    
    session_id = models.CharField(
        _('Session ID'),
        max_length=100,
        blank=True,
        help_text=_('Session identifier')
    )
    
    click_id = models.CharField(
        _('Click ID'),
        max_length=100,
        blank=True,
        help_text=_('Click identifier')
    )
    
    # Geographic data
    country = models.CharField(
        _('Country'),
        max_length=2,
        blank=True,
        help_text=_('Country code')
    )
    
    region = models.CharField(
        _('Region'),
        max_length=100,
        blank=True,
        help_text=_('Region or state')
    )
    
    city = models.CharField(
        _('City'),
        max_length=100,
        blank=True,
        help_text=_('City')
    )
    
    # Time data
    timestamp = models.DateTimeField(
        _('Timestamp'),
        default=timezone.now,
        help_text=_('When the signal was detected')
    )
    
    time_window = models.PositiveIntegerField(
        _('Time Window'),
        help_text=_('Time window in seconds')
    )
    
    # Signal metrics
    score = models.FloatField(
        _('Score'),
        help_text=_('Fraud signal score (0.0-1.0)')
    )
    
    confidence = models.FloatField(
        _('Confidence'),
        help_text=_('Detection confidence (0.0-1.0)')
    )
    
    threshold = models.FloatField(
        _('Threshold'),
        help_text=_('Detection threshold')
    )
    
    # Actions taken
    action_taken = models.CharField(
        _('Action Taken'),
        max_length=50,
        choices=[
            ('none', _('None')),
            ('flagged', _('Flagged')),
            ('blocked', _('Blocked')),
            ('quarantined', _('Quarantined')),
            ('reported', _('Reported')),
        ],
        default='none',
        help_text=_('Action taken for this signal')
    )
    
    action_reason = models.TextField(
        _('Action Reason'),
        blank=True,
        help_text=_('Reason for the action taken')
    )
    
    # Additional data
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional signal metadata')
    )
    
    # Resolution
    is_resolved = models.BooleanField(
        _('Is Resolved'),
        default=False,
        help_text=_('Whether this signal has been resolved')
    )
    
    resolved_at = models.DateTimeField(
        _('Resolved At'),
        null=True,
        blank=True,
        help_text=_('When this signal was resolved')
    )
    
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_fraud_signals',
        verbose_name=_('Resolved By'),
        help_text=_('User who resolved this signal')
    )
    
    resolution_notes = models.TextField(
        _('Resolution Notes'),
        blank=True,
        help_text=_('Notes about resolution')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        verbose_name = _('Click Fraud Signal')
        verbose_name_plural = _('Click Fraud Signals')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['advertiser', 'timestamp'], name='idx_advertiser_timestamp_456'),
            models.Index(fields=['offer', 'timestamp'], name='idx_offer_timestamp_457'),
            models.Index(fields=['signal_type', 'severity'], name='idx_signal_type_severity_458'),
            models.Index(fields=['ip_address'], name='idx_ip_address_459'),
            models.Index(fields=['device_fingerprint'], name='idx_device_fingerprint_460'),
            models.Index(fields=['score'], name='idx_score_461'),
            models.Index(fields=['is_resolved'], name='idx_is_resolved_462'),
        ]
    
    def __str__(self):
        return f"{self.signal_type} - {self.ip_address} - {self.score}"
    
    def clean(self):
        """Validate signal data."""
        super().clean()
        
        if self.score < 0 or self.score > 1:
            raise ValidationError(_('Score must be between 0 and 1'))
        
        if self.confidence < 0 or self.confidence > 1:
            raise ValidationError(_('Confidence must be between 0 and 1'))
        
        if self.threshold < 0 or self.threshold > 1:
            raise ValidationError(_('Threshold must be between 0 and 1'))
    
    def resolve(self, user, notes=''):
        """Resolve this fraud signal."""
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.resolved_by = user
        self.resolution_notes = notes
        self.save()
    
    def get_signal_summary(self):
        """Get signal summary as dictionary."""
        return {
            'signal_type': self.signal_type,
            'severity': self.severity,
            'score': self.score,
            'confidence': self.confidence,
            'action_taken': self.action_taken,
            'is_resolved': self.is_resolved,
            'timestamp': self.timestamp.isoformat(),
        }


class OfferQualityScore(models.Model):
    """
    Model for managing offer quality scores.
    
    Stores quality metrics and scoring data
    for offer optimization and ML training.
    """
    
    # Core relationships
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='offer_quality_scores',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this score belongs to')
    )
    
    offer = models.ForeignKey(
        'advertiser_portal_v2.AdvertiserOffer',
        on_delete=models.CASCADE,
        related_name='quality_scores',
        verbose_name=_('Offer'),
        help_text=_('Offer this score belongs to')
    )
    
    # Score data
    overall_score = models.FloatField(
        _('Overall Score'),
        help_text=_('Overall quality score (0.0-1.0)')
    )
    
    conversion_quality = models.FloatField(
        _('Conversion Quality'),
        help_text=_('Conversion quality score (0.0-1.0)')
    )
    
    traffic_quality = models.FloatField(
        _('Traffic Quality'),
        help_text=_('Traffic quality score (0.0-1.0)')
    )
    
    fraud_risk = models.FloatField(
        _('Fraud Risk'),
        help_text=_('Fraud risk score (0.0-1.0)')
    )
    
    engagement_score = models.FloatField(
        _('Engagement Score'),
        help_text=_('User engagement score (0.0-1.0)')
    )
    
    # Component scores
    ctr_score = models.FloatField(
        _('CTR Score'),
        help_text=_('Click-through rate score (0.0-1.0)')
    )
    
    conversion_rate_score = models.FloatField(
        _('Conversion Rate Score'),
        help_text=_('Conversion rate score (0.0-1.0)')
    )
    
    retention_score = models.FloatField(
        _('Retention Score'),
        help_text=_('User retention score (0.0-1.0)')
    )
    
    satisfaction_score = models.FloatField(
        _('Satisfaction Score'),
        help_text=_('User satisfaction score (0.0-1.0)')
    )
    
    # Performance metrics
    total_conversions = models.PositiveIntegerField(
        _('Total Conversions'),
        default=0,
        help_text=_('Total number of conversions')
    )
    
    total_clicks = models.PositiveIntegerField(
        _('Total Clicks'),
        default=0,
        help_text=_('Total number of clicks')
    )
    
    total_impressions = models.PositiveIntegerField(
        _('Total Impressions'),
        default=0,
        help_text=_('Total number of impressions')
    )
    
    avg_revenue = models.DecimalField(
        _('Average Revenue'),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_('Average revenue per conversion')
    )
    
    # Quality factors
    landing_page_quality = models.FloatField(
        _('Landing Page Quality'),
        help_text=_('Landing page quality score (0.0-1.0)')
    )
    
    creative_quality = models.FloatField(
        _('Creative Quality'),
        help_text=_('Creative quality score (0.0-1.0)')
    )
    
    targeting_quality = models.FloatField(
        _('Targeting Quality'),
        help_text=_('Targeting quality score (0.0-1.0)')
    )
    
    offer_competitiveness = models.FloatField(
        _('Offer Competitiveness'),
        help_text=_('Offer competitiveness score (0.0-1.0)')
    )
    
    # Time period
    score_date = models.DateField(
        _('Score Date'),
        help_text=_('Date of the score calculation')
    )
    
    period_type = models.CharField(
        _('Period Type'),
        max_length=20,
        choices=[
            ('daily', _('Daily')),
            ('weekly', _('Weekly')),
            ('monthly', _('Monthly')),
        ],
        default='daily',
        help_text=_('Type of time period')
    )
    
    # Additional data
    factors = models.JSONField(
        _('Factors'),
        default=dict,
        blank=True,
        help_text=_('Quality factors and weights')
    )
    
    recommendations = models.JSONField(
        _('Recommendations'),
        default=list,
        blank=True,
        help_text=_('Improvement recommendations')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this score was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this score was last updated')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        verbose_name = _('Offer Quality Score')
        verbose_name_plural = _('Offer Quality Scores')
        ordering = ['-score_date']
        indexes = [
            models.Index(fields=['advertiser', 'score_date'], name='idx_advertiser_score_date_463'),
            models.Index(fields=['offer', 'score_date'], name='idx_offer_score_date_464'),
            models.Index(fields=['overall_score'], name='idx_overall_score_465'),
            models.Index(fields=['period_type'], name='idx_period_type_466'),
            models.Index(fields=['fraud_risk'], name='idx_fraud_risk_467'),
            models.Index(fields=['conversion_quality'], name='idx_conversion_quality_468'),
        ]
    
    def __str__(self):
        return f"{self.offer.name} - {self.score_date} - {self.overall_score}"
    
    def clean(self):
        """Validate score data."""
        super().clean()
        
        # Validate score ranges
        score_fields = [
            'overall_score', 'conversion_quality', 'traffic_quality', 'fraud_risk',
            'engagement_score', 'ctr_score', 'conversion_rate_score', 'retention_score',
            'satisfaction_score', 'landing_page_quality', 'creative_quality',
            'targeting_quality', 'offer_competitiveness'
        ]
        
        for field in score_fields:
            value = getattr(self, field)
            if value is not None and (value < 0 or value > 1):
                raise ValidationError(_(f'{field.replace("_", " ").title()} must be between 0 and 1'))
    
    def calculate_overall_score(self):
        """Calculate overall quality score."""
        weights = {
            'conversion_quality': 0.3,
            'traffic_quality': 0.2,
            'engagement_score': 0.2,
            'landing_page_quality': 0.1,
            'creative_quality': 0.1,
            'targeting_quality': 0.1
        }
        
        weighted_score = 0
        for field, weight in weights.items():
            field_value = getattr(self, field, 0)
            weighted_score += field_value * weight
        
        # Adjust for fraud risk
        fraud_penalty = self.fraud_risk * 0.5
        self.overall_score = max(0, weighted_score - fraud_penalty)
    
    def get_quality_grade(self):
        """Get quality grade based on overall score."""
        if self.overall_score >= 0.9:
            return 'A+'
        elif self.overall_score >= 0.8:
            return 'A'
        elif self.overall_score >= 0.7:
            return 'B+'
        elif self.overall_score >= 0.6:
            return 'B'
        elif self.overall_score >= 0.5:
            return 'C+'
        elif self.overall_score >= 0.4:
            return 'C'
        elif self.overall_score >= 0.3:
            return 'D'
        else:
            return 'F'
    
    def get_performance_metrics(self):
        """Get performance metrics as dictionary."""
        return {
            'total_conversions': self.total_conversions,
            'total_clicks': self.total_clicks,
            'total_impressions': self.total_impressions,
            'avg_revenue': float(self.avg_revenue),
            'ctr': (self.total_clicks / self.total_impressions * 100) if self.total_impressions > 0 else 0,
            'conversion_rate': (self.total_conversions / self.total_clicks * 100) if self.total_clicks > 0 else 0,
        }


class RoutingBlacklist(models.Model):
    """
    Model for managing routing blacklists.
    
    Stores blacklisted entities for offer routing
    and fraud prevention.
    """
    
    # Core relationships
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='routing_blacklists',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this blacklist belongs to')
    )
    
    # Blacklist type and entity
    blacklist_type = models.CharField(
        _('Blacklist Type'),
        max_length=50,
        choices=[
            ('ip_address', _('IP Address')),
            ('user_agent', _('User Agent')),
            ('device_fingerprint', _('Device Fingerprint')),
            ('affiliate_id', _('Affiliate ID')),
            ('sub_id', _('Sub ID')),
            ('domain', _('Domain')),
            ('country', _('Country')),
            ('region', _('Region')),
            ('isp', _('ISP')),
        ],
        help_text=_('Type of blacklist entity')
    )
    
    entity_value = models.CharField(
        _('Entity Value'),
        max_length=500,
        help_text=_('Value to blacklist')
    )
    
    # Blacklist details
    reason = models.CharField(
        _('Reason'),
        max_length=100,
        help_text=_('Reason for blacklisting')
    )
    
    severity = models.CharField(
        _('Severity'),
        max_length=20,
        choices=[
            ('low', _('Low')),
            ('medium', _('Medium')),
            ('high', _('High')),
            ('critical', _('Critical')),
        ],
        default='medium',
        help_text=_('Severity of the blacklist')
    )
    
    # Time-based controls
    is_permanent = models.BooleanField(
        _('Is Permanent'),
        default=False,
        help_text=_('Whether this blacklist is permanent')
    )
    
    expires_at = models.DateTimeField(
        _('Expires At'),
        null=True,
        blank=True,
        help_text=_('When this blacklist expires')
    )
    
    # Action settings
    block_action = models.CharField(
        _('Block Action'),
        max_length=50,
        choices=[
            ('block', _('Block')),
            ('flag', _('Flag')),
            ('quarantine', _('Quarantine')),
            ('monitor', _('Monitor')),
        ],
        default='block',
        help_text=_('Action to take when entity matches')
    )
    
    # Statistics
    hit_count = models.PositiveIntegerField(
        _('Hit Count'),
        default=0,
        help_text=_('Number of times this blacklist was matched')
    )
    
    last_hit_at = models.DateTimeField(
        _('Last Hit At'),
        null=True,
        blank=True,
        help_text=_('When this blacklist was last matched')
    )
    
    # Additional data
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional blacklist metadata')
    )
    
    # Status
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        help_text=_('Whether this blacklist is active')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this blacklist was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this blacklist was last updated')
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_blacklists',
        verbose_name=_('Created By'),
        help_text=_('User who created this blacklist')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        verbose_name = _('Routing Blacklist')
        verbose_name_plural = _('Routing Blacklists')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser', 'blacklist_type'], name='idx_advertiser_blacklist_t_579'),
            models.Index(fields=['entity_value'], name='idx_entity_value_470'),
            models.Index(fields=['is_active'], name='idx_is_active_471'),
            models.Index(fields=['expires_at'], name='idx_expires_at_472'),
            models.Index(fields=['severity'], name='idx_severity_473'),
        ]
    
    def __str__(self):
        return f"{self.blacklist_type} - {self.entity_value}"
    
    def clean(self):
        """Validate blacklist data."""
        super().clean()
        
        if not self.is_permanent and not self.expires_at:
            raise ValidationError(_('Temporary blacklist must have an expiration date'))
        
        if self.is_permanent and self.expires_at:
            raise ValidationError(_('Permanent blacklist cannot have an expiration date'))
    
    def is_expired(self):
        """Check if blacklist is expired."""
        if self.is_permanent:
            return False
        return timezone.now() > self.expires_at
    
    def record_hit(self):
        """Record a hit for this blacklist."""
        self.hit_count += 1
        self.last_hit_at = timezone.now()
        self.save(update_fields=['hit_count', 'last_hit_at'])
    
    def activate(self):
        """Activate this blacklist."""
        self.is_active = True
        self.save(update_fields=['is_active'])
    
    def deactivate(self):
        """Deactivate this blacklist."""
        self.is_active = False
        self.save(update_fields=['is_active'])
    
    def get_blacklist_summary(self):
        """Get blacklist summary as dictionary."""
        return {
            'blacklist_type': self.blacklist_type,
            'entity_value': self.entity_value,
            'reason': self.reason,
            'severity': self.severity,
            'is_permanent': self.is_permanent,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'block_action': self.block_action,
            'hit_count': self.hit_count,
            'last_hit_at': self.last_hit_at.isoformat() if self.last_hit_at else None,
            'is_active': self.is_active,
        }
        app_label = 'advertiser_portal_v2'
