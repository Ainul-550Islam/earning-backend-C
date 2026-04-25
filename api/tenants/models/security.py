"""
Security Models

This module contains tenant security models for API keys,
webhooks, IP whitelisting, and audit logging.
"""

import uuid
import hashlib
import secrets
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils import timezone
from .base import TimeStampedModel, SoftDeleteModel

User = get_user_model()


class TenantAPIKey(TimeStampedModel, SoftDeleteModel):
    """
    API key management for tenant authentication.
    
    This model manages API keys that allow programmatic access
    to tenant resources with proper authentication and rate limiting.
    """
    
    KEY_STATUS_CHOICES = [
        ('active', _('Active')),
        ('inactive', _('Inactive')),
        ('expired', _('Expired')),
        ('revoked', _('Revoked')),
        ('suspended', _('Suspended')),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='api_keys',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this API key belongs to')
    )
    
    # Key information
    name = models.CharField(
        max_length=255,
        verbose_name=_('Key Name'),
        help_text=_('Human-readable name for the API key')
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
        help_text=_('Description of the API key purpose')
    )
    
    # Key data
    key_hash = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_('Key Hash'),
        help_text=_('Hashed version of the API key')
    )
    key_prefix = models.CharField(
        max_length=20,
        verbose_name=_('Key Prefix'),
        help_text=_('First few characters of the key for identification')
    )
    
    # Permissions and scopes
    scopes = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Scopes'),
        help_text=_('List of allowed scopes/permissions')
    )
    allowed_endpoints = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Allowed Endpoints'),
        help_text=_('List of allowed API endpoints')
    )
    
    # Rate limiting
    rate_limit_per_minute = models.IntegerField(
        default=60,
        verbose_name=_('Rate Limit Per Minute'),
        help_text=_('Maximum requests per minute')
    )
    rate_limit_per_hour = models.IntegerField(
        default=1000,
        verbose_name=_('Rate Limit Per Hour'),
        help_text=_('Maximum requests per hour')
    )
    rate_limit_per_day = models.IntegerField(
        default=10000,
        verbose_name=_('Rate Limit Per Day'),
        help_text=_('Maximum requests per day')
    )
    
    # Status and lifecycle
    status = models.CharField(
        max_length=20,
        choices=KEY_STATUS_CHOICES,
        default='active',
        verbose_name=_('Status'),
        help_text=_('Current status of the API key')
    )
    expires_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Expires At'),
        help_text=_('When the API key expires')
    )
    last_used_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Last Used At'),
        help_text=_('Last time the key was used')
    )
    
    # Usage tracking
    usage_count = models.IntegerField(
        default=0,
        verbose_name=_('Usage Count'),
        help_text=_('Total number of times the key has been used')
    )
    last_ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name=_('Last IP Address'),
        help_text=_('Last IP address that used this key')
    )
    last_user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Last User Agent'),
        help_text=_('Last user agent that used this key')
    )
    
    # Security settings
    require_https = models.BooleanField(
        default=True,
        verbose_name=_('Require HTTPS'),
        help_text=_('Require HTTPS connections')
    )
    allowed_ips = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Allowed IPs'),
        help_text=_('List of allowed IP addresses/CIDR ranges')
    )
    allowed_referers = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Allowed Referers'),
        help_text=_('List of allowed referer domains')
    )
    
    # Owner and permissions
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_api_keys',
        verbose_name=_('Created By'),
        help_text=_('User who created this API key')
    )
    
    class Meta:
        db_table = 'tenant_api_keys'
        verbose_name = _('Tenant API Key')
        verbose_name_plural = _('Tenant API Keys')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status'], name='idx_tenant_status_1841'),
            models.Index(fields=['key_hash'], name='idx_key_hash_1842'),
            models.Index(fields=['key_prefix'], name='idx_key_prefix_1843'),
            models.Index(fields=['status'], name='idx_status_1844'),
            models.Index(fields=['expires_at'], name='idx_expires_at_1845'),
            models.Index(fields=['last_used_at'], name='idx_last_used_at_1846'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"
    
    def clean(self):
        super().clean()
        if self.expires_at and self.expires_at <= timezone.now():
            raise ValidationError(_('Expiration date must be in the future.'))
    
    @classmethod
    def generate_key(cls, prefix='tk'):
        """Generate a new API key."""
        # Generate random bytes and encode as hex
        random_bytes = secrets.token_bytes(32)
        key_hex = random_bytes.hex()
        
        # Add prefix
        full_key = f"{prefix}_{key_hex}"
        
        return full_key
    
    @classmethod
    def hash_key(cls, key):
        """Hash an API key for storage."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def set_key(self, key):
        """Set the API key and store its hash."""
        self.key_hash = self.hash_key(key)
        self.key_prefix = key[:20]  # Store first 20 characters
    
    def verify_key(self, key):
        """Verify if a provided key matches this API key."""
        return self.hash_key(key) == self.key_hash
    
    def is_expired(self):
        """Check if the API key has expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        """Check if the API key is valid and active."""
        return (
            self.status == 'active' and
            not self.is_expired() and
            not self.is_deleted
        )
    
    def can_use_endpoint(self, endpoint):
        """Check if the API key can access a specific endpoint."""
        if not self.allowed_endpoints:
            return True  # No restrictions
        
        return endpoint in self.allowed_endpoints
    
    def has_scope(self, scope):
        """Check if the API key has a specific scope."""
        return scope in self.scopes
    
    def is_ip_allowed(self, ip_address):
        """Check if an IP address is allowed."""
        if not self.allowed_ips:
            return True  # No restrictions
        
        # Simple IP check (in production, use proper CIDR matching)
        return ip_address in self.allowed_ips
    
    def update_usage(self, ip_address=None, user_agent=None):
        """Update usage statistics."""
        self.usage_count += 1
        self.last_used_at = timezone.now()
        if ip_address:
            self.last_ip_address = ip_address
        if user_agent:
            self.last_user_agent = user_agent[:500]  # Limit length
        self.save(update_fields=['usage_count', 'last_used_at', 'last_ip_address', 'last_user_agent'])
    
    def revoke(self):
        """Revoke the API key."""
        self.status = 'revoked'
        self.save(update_fields=['status'])


class TenantWebhookConfig(TimeStampedModel, SoftDeleteModel):
    """
    Webhook configuration for tenant event notifications.
    
    This model manages webhook endpoints that receive
    real-time event notifications from the system.
    """
    
    WEBHOOK_STATUS_CHOICES = [
        ('active', _('Active')),
        ('inactive', _('Inactive')),
        ('suspended', _('Suspended')),
        ('failed', _('Failed')),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='webhook_configs',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this webhook belongs to')
    )
    
    # Webhook information
    name = models.CharField(
        max_length=255,
        verbose_name=_('Webhook Name'),
        help_text=_('Human-readable name for the webhook')
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
        help_text=_('Description of the webhook purpose')
    )
    
    # Endpoint configuration
    url = models.URLField(
        verbose_name=_('Webhook URL'),
        help_text=_('URL to receive webhook events')
    )
    secret = models.CharField(
        max_length=255,
        verbose_name=_('Webhook Secret'),
        help_text=_('Secret for webhook signature verification')
    )
    
    # Event configuration
    events = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Events'),
        help_text=_('List of events to send to this webhook')
    )
    
    # Delivery settings
    timeout_seconds = models.IntegerField(
        default=30,
        verbose_name=_('Timeout (seconds)'),
        help_text=_('Request timeout in seconds')
    )
    retry_count = models.IntegerField(
        default=3,
        verbose_name=_('Retry Count'),
        help_text=_('Number of retry attempts')
    )
    retry_delay_seconds = models.IntegerField(
        default=60,
        verbose_name=_('Retry Delay (seconds)'),
        help_text=_('Delay between retries in seconds')
    )
    
    # Status and monitoring
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
        help_text=_('Whether the webhook is currently active')
    )
    last_delivery_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Last Delivery At'),
        help_text=_('Last successful delivery timestamp')
    )
    last_status_code = models.IntegerField(
        blank=True,
        null=True,
        verbose_name=_('Last Status Code'),
        help_text=_('Last HTTP status code received')
    )
    
    # Statistics
    total_deliveries = models.IntegerField(
        default=0,
        verbose_name=_('Total Deliveries'),
        help_text=_('Total number of delivery attempts')
    )
    successful_deliveries = models.IntegerField(
        default=0,
        verbose_name=_('Successful Deliveries'),
        help_text=_('Number of successful deliveries')
    )
    failed_deliveries = models.IntegerField(
        default=0,
        verbose_name=_('Failed Deliveries'),
        help_text=_('Number of failed deliveries')
    )
    
    # Security settings
    allowed_ips = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_('Allowed IPs'),
        help_text=_('IP addresses allowed to trigger webhook')
    )
    require_https = models.BooleanField(
        default=True,
        verbose_name=_('Require HTTPS'),
        help_text=_('Require HTTPS for webhook URL')
    )
    
    # Headers and authentication
    custom_headers = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Custom Headers'),
        help_text=_('Custom HTTP headers to send')
    )
    auth_type = models.CharField(
        max_length=20,
        choices=[
            ('none', _('None')),
            ('bearer', _('Bearer Token')),
            ('basic', _('Basic Auth')),
            ('api_key', _('API Key')),
        ],
        default='none',
        verbose_name=_('Auth Type'),
        help_text=_('Authentication method')
    )
    auth_token = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_('Auth Token'),
        help_text=_('Authentication token')
    )
    
    class Meta:
        db_table = 'tenant_webhook_configs'
        verbose_name = _('Tenant Webhook Config')
        verbose_name_plural = _('Tenant Webhook Configs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'is_active'], name='idx_tenant_is_active_1847'),
            models.Index(fields=['url'], name='idx_url_1848'),
            models.Index(fields=['is_active'], name='idx_is_active_1849'),
            models.Index(fields=['last_delivery_at'], name='idx_last_delivery_at_1850'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
    
    def clean(self):
        super().clean()
        if self.auth_type != 'none' and not self.auth_token:
            raise ValidationError(_('Authentication token is required when auth type is not "none".'))
        
        if self.require_https and not self.url.startswith('https://'):
            raise ValidationError(_('HTTPS URL is required when require_https is enabled.'))
    
    @classmethod
    def generate_secret(cls):
        """Generate a secure webhook secret."""
        return secrets.token_urlsafe(32)
    
    def set_secret(self):
        """Generate and set a new webhook secret."""
        self.secret = self.generate_secret()
    
    def can_send_event(self, event_type):
        """Check if webhook is configured to send a specific event."""
        return event_type in self.events
    
    def update_delivery_stats(self, success=True, status_code=None):
        """Update delivery statistics."""
        self.total_deliveries += 1
        
        if success:
            self.successful_deliveries += 1
            self.last_delivery_at = timezone.now()
        else:
            self.failed_deliveries += 1
        
        if status_code:
            self.last_status_code = status_code
        
        self.save(update_fields=[
            'total_deliveries', 'successful_deliveries', 
            'failed_deliveries', 'last_delivery_at', 'last_status_code'
        ])
    
    @property
    def success_rate(self):
        """Calculate delivery success rate."""
        if self.total_deliveries == 0:
            return 0
        return (self.successful_deliveries / self.total_deliveries) * 100
    
    def get_auth_headers(self):
        """Get authentication headers for webhook requests."""
        headers = {}
        
        if self.auth_type == 'bearer' and self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        elif self.auth_type == 'api_key' and self.auth_token:
            headers['X-API-Key'] = self.auth_token
        elif self.auth_type == 'basic' and self.auth_token:
            # Basic auth would be handled in the request
            headers['Authorization'] = f'Basic {self.auth_token}'
        
        # Add custom headers
        headers.update(self.custom_headers)
        
        return headers


class TenantIPWhitelist(TimeStampedModel, SoftDeleteModel):
    """
    IP whitelist for tenant security.
    
    This model manages IP address whitelists for
    restricting access to tenant resources.
    """
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='ip_whitelists',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this IP whitelist belongs to')
    )
    
    # IP information
    ip_range = models.CharField(
        max_length=100,
        verbose_name=_('IP Range'),
        help_text=_('IP address or CIDR range')
    )
    label = models.CharField(
        max_length=255,
        verbose_name=_('Label'),
        help_text=_('Human-readable label for this IP range')
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
        help_text=_('Description of this IP range purpose')
    )
    
    # Status and settings
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Is Active'),
        help_text=_('Whether this IP range is currently active')
    )
    
    # Usage tracking
    last_access_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_('Last Access At'),
        help_text=_('Last time this IP range was used')
    )
    access_count = models.IntegerField(
        default=0,
        verbose_name=_('Access Count'),
        help_text=_('Number of times this IP range was used')
    )
    
    # Owner
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_ip_whitelists',
        verbose_name=_('Created By'),
        help_text=_('User who created this IP whitelist entry')
    )
    
    class Meta:
        db_table = 'tenant_ip_whitelists'
        verbose_name = _('Tenant IP Whitelist')
        verbose_name_plural = _('Tenant IP Whitelists')
        ordering = ['label']
        unique_together = ['tenant', 'ip_range']
        indexes = [
            models.Index(fields=['tenant', 'is_active'], name='idx_tenant_is_active_1851'),
            models.Index(fields=['ip_range'], name='idx_ip_range_1852'),
            models.Index(fields=['is_active'], name='idx_is_active_1853'),
        ]
    
    def __str__(self):
        return f"{self.label} ({self.ip_range})"
    
    def clean(self):
        super().clean()
        # Basic IP/CIDR validation
        try:
            import ipaddress
            ipaddress.ip_network(self.ip_range, strict=False)
        except ValueError:
            raise ValidationError(_('Invalid IP address or CIDR range.'))
    
    def contains_ip(self, ip_address):
        """Check if an IP address is within this range."""
        try:
            import ipaddress
            network = ipaddress.ip_network(self.ip_range, strict=False)
            ip = ipaddress.ip_address(ip_address)
            return ip in network
        except ValueError:
            return False
    
    def update_access(self):
        """Update access statistics."""
        self.access_count += 1
        self.last_access_at = timezone.now()
        self.save(update_fields=['access_count', 'last_access_at'])


class TenantAuditLog(TimeStampedModel, SoftDeleteModel):
    """
    Audit log for tenant actions and changes.
    
    This model tracks all important actions and changes
    within tenant accounts for security and compliance.
    """
    
    ACTION_CHOICES = [
        ('create', _('Create')),
        ('update', _('Update')),
        ('delete', _('Delete')),
        ('login', _('Login')),
        ('logout', _('Logout')),
        ('access', _('Access')),
        ('export', _('Export')),
        ('import', _('Import')),
        ('config_change', _('Config Change')),
        ('security_event', _('Security Event')),
        ('billing_event', _('Billing Event')),
        ('api_access', _('API Access')),
        ('webhook_event', _('Webhook Event')),
    ]
    
    SEVERITY_CHOICES = [
        ('low', _('Low')),
        ('medium', _('Medium')),
        ('high', _('High')),
        ('critical', _('Critical')),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='audit_logs',
        verbose_name=_('Tenant'),
        help_text=_('The tenant this audit log belongs to')
    )
    
    # Action information
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        verbose_name=_('Action'),
        help_text=_('Type of action performed')
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='medium',
        verbose_name=_('Severity'),
        help_text=_('Severity level of the action')
    )
    
    # Actor information
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_actions',
        verbose_name=_('Actor'),
        help_text=_('User who performed the action')
    )
    actor_type = models.CharField(
        max_length=50,
        default='user',
        verbose_name=_('Actor Type'),
        help_text=_('Type of actor (user, system, api, etc.)')
    )
    
    # Target information
    model_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Model Name'),
        help_text=_('Name of the model that was affected')
    )
    object_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Object ID'),
        help_text=_('ID of the object that was affected')
    )
    object_repr = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Object Representation'),
        help_text=_('String representation of the affected object')
    )
    
    # Change details
    old_value = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Old Value'),
        help_text=_('Previous value before the change')
    )
    new_value = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('New Value'),
        help_text=_('New value after the change')
    )
    changes = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Changes'),
        help_text=_('Detailed changes made')
    )
    
    # Request information
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name=_('IP Address'),
        help_text=_('IP address from which the action was performed')
    )
    user_agent = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('User Agent'),
        help_text=_('User agent string from the request')
    )
    request_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Request ID'),
        help_text=_('Unique request identifier')
    )
    
    # Additional information
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Description'),
        help_text=_('Detailed description of the action')
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Metadata'),
        help_text=_('Additional metadata about the action')
    )
    
    class Meta:
        db_table = 'tenant_audit_logs'
        verbose_name = _('Tenant Audit Log')
        verbose_name_plural = _('Tenant Audit Logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'action'], name='idx_tenant_action_1854'),
            models.Index(fields=['actor'], name='idx_actor_1855'),
            models.Index(fields=['model_name', 'object_id'], name='idx_model_name_object_id_1856'),
            models.Index(fields=['severity'], name='idx_severity_1857'),
            models.Index(fields=['ip_address'], name='idx_ip_address_1858'),
            models.Index(fields=['created_at'], name='idx_created_at_1859'),
        ]
    
    def __str__(self):
        return f"{self.action} on {self.model_name} by {self.actor}"
    
    @classmethod
    def log_action(cls, tenant, action, actor=None, **kwargs):
        """Create an audit log entry."""
        return cls.objects.create(
            tenant=tenant,
            action=action,
            actor=actor,
            **kwargs
        )
    
    @classmethod
    def log_security_event(cls, tenant, description, severity='high', **kwargs):
        """Log a security event."""
        return cls.log_action(
            tenant=tenant,
            action='security_event',
            severity=severity,
            description=description,
            **kwargs
        )
    
    @classmethod
    def log_api_access(cls, tenant, actor, endpoint, method='GET', **kwargs):
        """Log API access."""
        return cls.log_action(
            tenant=tenant,
            action='api_access',
            actor=actor,
            description=f"{method} {endpoint}",
            **kwargs
        )
    
    @property
    def actor_display(self):
        """Get display name for the actor."""
        if self.actor:
            return str(self.actor)
        return self.actor_type.title()
    
    @property
    def target_display(self):
        """Get display name for the target."""
        if self.object_repr:
            return self.object_repr
        if self.model_name:
            return f"{self.model_name} {self.object_id}"
        return "Unknown"
    
    def get_changes_summary(self):
        """Get a summary of changes made."""
        if not self.changes:
            return None
        
        changes_list = []
        for field, change in self.changes.items():
            if isinstance(change, dict) and 'old' in change and 'new' in change:
                changes_list.append(f"{field}: {change['old']} -> {change['new']}")
        
        return "; ".join(changes_list) if changes_list else None
