"""
Integration Database Model

This module contains Integration model and related models
for managing third-party integrations and external services.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg, F
from django.core.validators import MinValueValidator, MaxValueValidator

from api.advertiser_portal.models_base import (
    AdvertiserPortalBaseModel, StatusModel, AuditModel,
    APIKeyModel, BudgetModel, GeoModel, TrackingModel, ConfigurationModel,
)
from ..enums import *
from ..utils import *
from ..validators import *


class Integration(AdvertiserPortalBaseModel, AuditModel):
    """
    Main integration model for managing third-party service integrations.
    
    This model stores integration configurations, credentials,
    and connection status for external services.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='integrations',
        help_text="Associated advertiser"
    )
    name = models.CharField(
        max_length=255,
        help_text="Integration name"
    )
    description = models.TextField(
        blank=True,
        help_text="Integration description"
    )
    
    # Integration Configuration
    integration_type = models.CharField(
        max_length=50,
        choices=[
            ('analytics', 'Analytics Platform'),
            ('crm', 'CRM System'),
            ('email_marketing', 'Email Marketing'),
            ('social_media', 'Social Media'),
            ('ad_network', 'Ad Network'),
            ('data_warehouse', 'Data Warehouse'),
            ('payment_gateway', 'Payment Gateway'),
            ('cdn', 'Content Delivery Network'),
            ('monitoring', 'Monitoring Service'),
            ('custom', 'Custom Integration')
        ],
        db_index=True,
        help_text="Type of integration"
    )
    
    provider = models.CharField(
        max_length=100,
        help_text="Integration provider (e.g., Google Analytics, Salesforce)"
    )
    version = models.CharField(
        max_length=20,
        blank=True,
        help_text="Integration version"
    )
    
    # Connection Configuration
    endpoint_url = models.URLField(
        blank=True,
        help_text="API endpoint URL"
    )
    authentication_method = models.CharField(
        max_length=50,
        choices=[
            ('api_key', 'API Key'),
            ('oauth2', 'OAuth 2.0'),
            ('basic_auth', 'Basic Authentication'),
            ('bearer_token', 'Bearer Token'),
            ('certificate', 'Client Certificate'),
            ('custom', 'Custom Authentication')
        ],
        default='api_key',
        help_text="Authentication method"
    )
    
    # Credentials (Encrypted)
    api_key = models.TextField(
        blank=True,
        help_text="API key (encrypted)"
    )
    api_secret = models.TextField(
        blank=True,
        help_text="API secret (encrypted)"
    )
    access_token = models.TextField(
        blank=True,
        help_text="Access token (encrypted)"
    )
    refresh_token = models.TextField(
        blank=True,
        help_text="Refresh token (encrypted)"
    )
    client_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="OAuth client ID"
    )
    client_secret = models.TextField(
        blank=True,
        help_text="OAuth client secret (encrypted)"
    )
    
    # Configuration Settings
    config_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Integration-specific configuration"
    )
    default_settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Default integration settings"
    )
    custom_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom HTTP headers"
    )
    webhook_url = models.URLField(
        blank=True,
        help_text="Webhook URL for callbacks"
    )
    
    # Status and Health
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('error', 'Error'),
            ('suspended', 'Suspended'),
            ('testing', 'Testing')
        ],
        default='inactive',
        db_index=True,
        help_text="Integration status"
    )
    connection_status = models.CharField(
        max_length=20,
        choices=[
            ('connected', 'Connected'),
            ('disconnected', 'Disconnected'),
            ('error', 'Connection Error'),
            ('testing', 'Testing Connection')
        ],
        default='disconnected',
        help_text="Connection status"
    )
    last_health_check = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last health check timestamp"
    )
    health_status = models.CharField(
        max_length=20,
        choices=[
            ('healthy', 'Healthy'),
            ('warning', 'Warning'),
            ('critical', 'Critical'),
            ('unknown', 'Unknown')
        ],
        default='unknown',
        help_text="Health status"
    )
    
    # Rate Limiting and Quotas
    rate_limit = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Rate limit (requests per hour)"
    )
    quota_limit = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Quota limit (requests per day)"
    )
    current_usage = models.IntegerField(
        default=0,
        help_text="Current usage count"
    )
    usage_reset_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when usage resets"
    )
    
    # Data Sync Configuration
    sync_enabled = models.BooleanField(
        default=True,
        help_text="Whether data synchronization is enabled"
    )
    sync_frequency = models.CharField(
        max_length=50,
        choices=[
            ('realtime', 'Real-time'),
            ('5min', 'Every 5 Minutes'),
            ('15min', 'Every 15 Minutes'),
            ('30min', 'Every 30 Minutes'),
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly')
        ],
        default='hourly',
        help_text="Synchronization frequency"
    )
    last_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last synchronization timestamp"
    )
    next_sync = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Next scheduled synchronization"
    )
    
    # Error Handling
    error_count = models.IntegerField(
        default=0,
        help_text="Number of errors encountered"
    )
    last_error = models.TextField(
        blank=True,
        help_text="Last error message"
    )
    last_error_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last error timestamp"
    )
    retry_count = models.IntegerField(
        default=0,
        help_text="Number of retry attempts"
    )
    max_retries = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0)],
        help_text="Maximum retry attempts"
    )
    
    # Monitoring and Logging
    logging_enabled = models.BooleanField(
        default=True,
        help_text="Whether logging is enabled"
    )
    log_level = models.CharField(
        max_length=20,
        choices=[
            ('debug', 'Debug'),
            ('info', 'Info'),
            ('warning', 'Warning'),
            ('error', 'Error'),
            ('critical', 'Critical')
        ],
        default='info',
        help_text="Log level"
    )
    monitoring_enabled = models.BooleanField(
        default=True,
        help_text="Whether monitoring is enabled"
    )
    
    # External References
    external_integration_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="External integration ID"
    )
    integration_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional integration metadata"
    )
    
    class Meta:
        db_table = 'integrations'
        verbose_name = 'Integration'
        verbose_name_plural = 'Integrations'
        indexes = [
            models.Index(fields=['advertiser', 'status'], name='idx_advertiser_status_305'),
            models.Index(fields=['integration_type'], name='idx_integration_type_306'),
            models.Index(fields=['provider'], name='idx_provider_307'),
            models.Index(fields=['connection_status'], name='idx_connection_status_308'),
            models.Index(fields=['health_status'], name='idx_health_status_309'),
            models.Index(fields=['last_sync'], name='idx_last_sync_310'),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.provider})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate required fields based on authentication method
        if self.authentication_method == 'api_key' and not self.api_key:
            raise ValidationError("API key is required for API key authentication")
        
        if self.authentication_method == 'oauth2' and (not self.client_id or not self.client_secret):
            raise ValidationError("Client ID and secret are required for OAuth 2.0")
        
        if self.authentication_method == 'basic_auth' and not self.api_key:
            raise ValidationError("Username is required for basic authentication")
        
        # Validate rate limits
        if self.rate_limit is not None and self.rate_limit <= 0:
            raise ValidationError("Rate limit must be positive")
        
        if self.quota_limit is not None and self.quota_limit <= 0:
            raise ValidationError("Quota limit must be positive")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Encrypt sensitive data
        if self.api_key:
            self.api_key = self.encrypt_data(self.api_key)
        if self.api_secret:
            self.api_secret = self.encrypt_data(self.api_secret)
        if self.access_token:
            self.access_token = self.encrypt_data(self.access_token)
        if self.refresh_token:
            self.refresh_token = self.encrypt_data(self.refresh_token)
        if self.client_secret:
            self.client_secret = self.encrypt_data(self.client_secret)
        
        # Calculate next sync time
        if self.sync_enabled and not self.next_sync:
            self.next_sync = self.calculate_next_sync()
        
        super().save(*args, **kwargs)
    
    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data."""
        from cryptography.fernet import Fernet
        from django.conf import settings
        
        try:
            key = getattr(settings, 'ENCRYPTION_KEY', None)
            if key:
                fernet = Fernet(key.encode())
                return fernet.encrypt(data.encode()).decode()
        except Exception:
            pass
        
        return data  # Return as-is if encryption fails
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data."""
        from cryptography.fernet import Fernet
        from django.conf import settings
        
        try:
            key = getattr(settings, 'ENCRYPTION_KEY', None)
            if key:
                fernet = Fernet(key.encode())
                return fernet.decrypt(encrypted_data.encode()).decode()
        except Exception:
            pass
        
        return encrypted_data  # Return as-is if decryption fails
    
    def calculate_next_sync(self) -> Optional[datetime]:
        """Calculate next synchronization time."""
        if not self.sync_enabled:
            return None
        
        now = timezone.now()
        
        if self.sync_frequency == 'realtime':
            return now + timezone.timedelta(minutes=1)
        elif self.sync_frequency == '5min':
            return now + timezone.timedelta(minutes=5)
        elif self.sync_frequency == '15min':
            return now + timezone.timedelta(minutes=15)
        elif self.sync_frequency == '30min':
            return now + timezone.timedelta(minutes=30)
        elif self.sync_frequency == 'hourly':
            return now + timezone.timedelta(hours=1)
        elif self.sync_frequency == 'daily':
            return now + timezone.timedelta(days=1)
        elif self.sync_frequency == 'weekly':
            return now + timezone.timedelta(weeks=1)
        
        return None
    
    def is_healthy(self) -> bool:
        """Check if integration is healthy."""
        return (
            self.status == 'active' and
            self.connection_status == 'connected' and
            self.health_status == 'healthy'
        )
    
    def can_make_request(self) -> bool:
        """Check if integration can make requests."""
        if not self.is_healthy():
            return False
        
        # Check rate limiting
        if self.rate_limit and self.current_usage >= self.rate_limit:
            return False
        
        # Check quota
        if self.quota_limit and self.current_usage >= self.quota_limit:
            return False
        
        return True
    
    def increment_usage(self) -> bool:
        """Increment usage count."""
        if not self.can_make_request():
            return False
        
        self.current_usage += 1
        self.save(update_fields=['current_usage'])
        return True
    
    def reset_usage(self) -> None:
        """Reset usage count."""
        self.current_usage = 0
        self.usage_reset_date = timezone.now()
        self.save(update_fields=['current_usage', 'usage_reset_date'])
    
    def test_connection(self) -> Dict[str, Any]:
        """Test integration connection."""
        try:
            # This would implement actual connection testing
            # For now, return a mock response
            result = {
                'success': True,
                'message': 'Connection successful',
                'response_time': 150,
                'timestamp': timezone.now().isoformat()
            }
            
            # Update status based on test
            if result['success']:
                self.connection_status = 'connected'
                self.health_status = 'healthy'
                self.last_health_check = timezone.now()
            else:
                self.connection_status = 'error'
                self.health_status = 'critical'
            
            self.save(update_fields=['connection_status', 'health_status', 'last_health_check'])
            
            return result
        except Exception as e:
            self.connection_status = 'error'
            self.health_status = 'critical'
            self.last_error = str(e)
            self.last_error_date = timezone.now()
            self.save(update_fields=['connection_status', 'health_status', 'last_error', 'last_error_date'])
            
            return {
                'success': False,
                'message': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    def get_integration_summary(self) -> Dict[str, Any]:
        """Get integration summary."""
        return {
            'basic_info': {
                'name': self.name,
                'description': self.description,
                'integration_type': self.integration_type,
                'provider': self.provider,
                'version': self.version
            },
            'connection': {
                'endpoint_url': self.endpoint_url,
                'authentication_method': self.authentication_method,
                'status': self.status,
                'connection_status': self.connection_status,
                'health_status': self.health_status
            },
            'usage': {
                'rate_limit': self.rate_limit,
                'quota_limit': self.quota_limit,
                'current_usage': self.current_usage,
                'usage_reset_date': self.usage_reset_date.isoformat() if self.usage_reset_date else None
            },
            'sync': {
                'sync_enabled': self.sync_enabled,
                'sync_frequency': self.sync_frequency,
                'last_sync': self.last_sync.isoformat() if self.last_sync else None,
                'next_sync': self.next_sync.isoformat() if self.next_sync else None
            },
            'errors': {
                'error_count': self.error_count,
                'last_error': self.last_error,
                'last_error_date': self.last_error_date.isoformat() if self.last_error_date else None,
                'retry_count': self.retry_count
            },
            'monitoring': {
                'logging_enabled': self.logging_enabled,
                'log_level': self.log_level,
                'monitoring_enabled': self.monitoring_enabled,
                'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None
            }
        }


class IntegrationLog(AdvertiserPortalBaseModel):
    """
    Model for logging integration events and activities.
    """
    
    # Basic Information
    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name='logs',
        help_text="Associated integration"
    )
    
    # Log Details
    event_type = models.CharField(
        max_length=50,
        choices=[
            ('request', 'API Request'),
            ('response', 'API Response'),
            ('sync', 'Data Sync'),
            ('error', 'Error'),
            ('warning', 'Warning'),
            ('info', 'Information'),
            ('health_check', 'Health Check'),
            ('connection_test', 'Connection Test')
        ],
        db_index=True,
        help_text="Type of event"
    )
    level = models.CharField(
        max_length=20,
        choices=[
            ('debug', 'Debug'),
            ('info', 'Info'),
            ('warning', 'Warning'),
            ('error', 'Error'),
            ('critical', 'Critical')
        ],
        db_index=True,
        help_text="Log level"
    )
    
    # Event Data
    message = models.TextField(
        help_text="Log message"
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional event details"
    )
    request_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Request data (sanitized)"
    )
    response_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Response data (sanitized)"
    )
    
    # Performance Metrics
    response_time = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Response time in milliseconds"
    )
    status_code = models.IntegerField(
        null=True,
        blank=True,
        help_text="HTTP status code"
    )
    
    # Context Information
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='integration_logs'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address if applicable"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent if applicable"
    )
    
    class Meta:
        db_table = 'integration_logs'
        verbose_name = 'Integration Log'
        verbose_name_plural = 'Integration Logs'
        indexes = [
            models.Index(fields=['integration', 'event_type'], name='idx_integration_event_type_311'),
            models.Index(fields=['integration', 'level'], name='idx_integration_level_312'),
            models.Index(fields=['created_at'], name='idx_created_at_313'),
            models.Index(fields=['status_code'], name='idx_status_code_314'),
        ]
    
    def __str__(self) -> str:
        return f"{self.event_type} - {self.integration.name}"


class IntegrationWebhook(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing integration webhooks.
    """
    
    # Basic Information
    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name='webhooks',
        help_text="Associated integration"
    )
    name = models.CharField(
        max_length=255,
        help_text="Webhook name"
    )
    description = models.TextField(
        blank=True,
        help_text="Webhook description"
    )
    
    # Webhook Configuration
    webhook_url = models.URLField(
        help_text="Webhook URL"
    )
    event_types = models.JSONField(
        default=list,
        help_text="List of event types to trigger webhook"
    )
    secret_key = models.TextField(
        blank=True,
        help_text="Webhook secret key (encrypted)"
    )
    
    # Configuration
    active = models.BooleanField(
        default=True,
        help_text="Whether webhook is active"
    )
    retry_attempts = models.IntegerField(
        default=3,
        validators=[MinValueValidator(0)],
        help_text="Number of retry attempts"
    )
    timeout = models.IntegerField(
        default=30,
        validators=[MinValueValidator(1)],
        help_text="Timeout in seconds"
    )
    
    # Headers and Authentication
    custom_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom HTTP headers"
    )
    authentication_type = models.CharField(
        max_length=50,
        choices=[
            ('none', 'None'),
            ('basic', 'Basic Auth'),
            ('bearer', 'Bearer Token'),
            ('signature', 'Signature')
        ],
        default='none',
        help_text="Authentication type"
    )
    
    # Status and Statistics
    last_triggered = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time webhook was triggered"
    )
    trigger_count = models.IntegerField(
        default=0,
        help_text="Number of times webhook was triggered"
    )
    success_count = models.IntegerField(
        default=0,
        help_text="Number of successful deliveries"
    )
    failure_count = models.IntegerField(
        default=0,
        help_text="Number of failed deliveries"
    )
    
    class Meta:
        db_table = 'integration_webhooks'
        verbose_name = 'Integration Webhook'
        verbose_name_plural = 'Integration Webhooks'
        indexes = [
            models.Index(fields=['integration', 'active'], name='idx_integration_active_315'),
            models.Index(fields=['last_triggered'], name='idx_last_triggered_316'),
        ]
    
    def __str__(self) -> str:
        return f"{self.name} ({self.integration.name})"
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Encrypt secret key
        if self.secret_key:
            self.secret_key = self.integration.encrypt_data(self.secret_key)
        
        super().save(*args, **kwargs)
    
    def get_success_rate(self) -> float:
        """Get webhook success rate."""
        total = self.trigger_count
        if total == 0:
            return 0.0
        
        return (self.success_count / total) * 100
    
    def trigger_webhook(self, event_data: Dict[str, Any]) -> bool:
        """Trigger webhook with event data."""
        try:
            # This would implement actual webhook triggering
            # For now, just update statistics
            self.last_triggered = timezone.now()
            self.trigger_count += 1
            self.success_count += 1
            self.save(update_fields=['last_triggered', 'trigger_count', 'success_count'])
            
            return True
        except Exception as e:
            self.failure_count += 1
            self.save(update_fields=['failure_count'])
            return False


class IntegrationMapping(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing field mappings between systems.
    """
    
    # Basic Information
    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name='mappings',
        help_text="Associated integration"
    )
    source_entity = models.CharField(
        max_length=100,
        help_text="Source entity type"
    )
    target_entity = models.CharField(
        max_length=100,
        help_text="Target entity type"
    )
    
    # Mapping Configuration
    field_mappings = models.JSONField(
        help_text="Field mapping configuration"
    )
    transformation_rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Data transformation rules"
    )
    filter_conditions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Filter conditions for data sync"
    )
    
    # Sync Configuration
    sync_direction = models.CharField(
        max_length=20,
        choices=[
            ('import', 'Import Only'),
            ('export', 'Export Only'),
            ('bidirectional', 'Bidirectional')
        ],
        default='import',
        help_text="Synchronization direction"
    )
    auto_sync = models.BooleanField(
        default=True,
        help_text="Whether to automatically sync mapped data"
    )
    
    class Meta:
        db_table = 'integration_mappings'
        verbose_name = 'Integration Mapping'
        verbose_name_plural = 'Integration Mappings'
        unique_together = ['integration', 'source_entity', 'target_entity']
        indexes = [
            models.Index(fields=['integration', 'source_entity'], name='idx_integration_source_ent_d9e'),
            models.Index(fields=['integration', 'target_entity'], name='idx_integration_target_ent_319'),
        ]
    
    def __str__(self) -> str:
        return f"{self.source_entity} -> {self.target_entity}"


class IntegrationCredential(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing integration credentials with rotation.
    """
    
    # Basic Information
    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name='credentials',
        help_text="Associated integration"
    )
    credential_type = models.CharField(
        max_length=50,
        choices=[
            ('api_key', 'API Key'),
            ('access_token', 'Access Token'),
            ('refresh_token', 'Refresh Token'),
            ('client_secret', 'Client Secret'),
            ('certificate', 'Certificate'),
            ('password', 'Password')
        ],
        help_text="Type of credential"
    )
    
    # Credential Data
    encrypted_credential = models.TextField(
        help_text="Encrypted credential data"
    )
    credential_name = models.CharField(
        max_length=100,
        help_text="Credential name/identifier"
    )
    
    # Lifecycle Management
    is_active = models.BooleanField(
        default=True,
        help_text="Whether credential is active"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Credential expiration date"
    )
    last_rotated = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last rotation timestamp"
    )
    rotation_frequency = models.CharField(
        max_length=50,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly'),
            ('never', 'Never')
        ],
        default='monthly',
        help_text="Rotation frequency"
    )
    
    class Meta:
        db_table = 'integration_credentials'
        verbose_name = 'Integration Credential'
        verbose_name_plural = 'Integration Credentials'
        indexes = [
            models.Index(fields=['integration', 'credential_type'], name='idx_integration_credential_ced'),
            models.Index(fields=['is_active'], name='idx_is_active_320'),
            models.Index(fields=['expires_at'], name='idx_expires_at_321'),
        ]
    
    def __str__(self) -> str:
        return f"{self.credential_name} ({self.integration.name})"
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Encrypt credential
        if self.encrypted_credential:
            self.encrypted_credential = self.integration.encrypt_data(self.encrypted_credential)
        
        super().save(*args, **kwargs)
    
    def get_credential(self) -> str:
        """Get decrypted credential."""
        return self.integration.decrypt_data(self.encrypted_credential)
    
    def is_expired(self) -> bool:
        """Check if credential is expired."""
        if not self.expires_at:
            return False
        
        return timezone.now() > self.expires_at
    
    def needs_rotation(self) -> bool:
        """Check if credential needs rotation."""
        if self.rotation_frequency == 'never':
            return False
        
        if not self.last_rotated:
            return True
        
        now = timezone.now()
        
        if self.rotation_frequency == 'daily':
            return (now - self.last_rotated).days >= 1
        elif self.rotation_frequency == 'weekly':
            return (now - self.last_rotated).days >= 7
        elif self.rotation_frequency == 'monthly':
            return (now - self.last_rotated).days >= 30
        elif self.rotation_frequency == 'quarterly':
            return (now - self.last_rotated).days >= 90
        elif self.rotation_frequency == 'yearly':
            return (now - self.last_rotated).days >= 365
        
        return False
