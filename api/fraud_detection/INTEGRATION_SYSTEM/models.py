# =============================================================================
# INTEGRATION_SYSTEM/models.py
# =============================================================================
"""
Django Models for Integration System.

Provides database models for persistent storage of integration
configurations, logs, and operational data.
"""

from __future__ import annotations
import asyncio

import uuid
import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db.models import JSONField, Q, F, Count, Avg, Max, Min

from .integ_constants import (
    IntegrationType, IntegrationStatus, AuthenticationType,
    CircuitBreakerState, LogLevel, Priority, DataFormat
)

User = get_user_model()


class IntegrationManager(models.Manager):
    """Custom manager for Integration model."""
    
    def get_queryset(self):
        """Get default queryset with optimizations."""
        return super().get_queryset().select_related('created_by', 'updated_by')
    
    def active(self):
        """Get active integrations."""
        return self.filter(status=IntegrationStatus.ACTIVE)
    
    def by_type(self, integration_type):
        """Get integrations by type."""
        return self.filter(integration_type=integration_type)
    
    def healthy(self):
        """Get healthy integrations."""
        return self.filter(
            status=IntegrationStatus.ACTIVE,
            health_status='healthy'
        )


class Integration(models.Model):
    """
    Integration model for managing external system connections.
    
    Stores configuration, credentials, and operational status
    for each external integration.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True, db_index=True)
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Integration configuration
    integration_type = models.CharField(
        max_length=50,
        choices=[(t.value, t.name) for t in IntegrationType],
        db_index=True
    )
    authentication_type = models.CharField(
        max_length=50,
        choices=[(t.value, t.name) for t in AuthenticationType],
        default=AuthenticationType.NONE.value
    )
    
    # Connection details
    base_url = models.URLField(max_length=500, blank=True)
    endpoint = models.CharField(max_length=500, blank=True)
    timeout = models.IntegerField(default=30)
    retry_attempts = models.IntegerField(default=3)
    retry_delay = models.IntegerField(default=5)
    
    # Status and health
    status = models.CharField(
        max_length=50,
        choices=[(s.value, s.name) for s in IntegrationStatus],
        default=IntegrationStatus.INACTIVE.value,
        db_index=True
    )
    health_status = models.CharField(
        max_length=50,
        default='unknown',
        db_index=True
    )
    last_health_check = models.DateTimeField(null=True, blank=True)
    
    # Configuration data (encrypted in production)
    config = JSONField(default=dict, blank=True)
    credentials = JSONField(default=dict, blank=True)  # Store encrypted
    
    # Rate limiting
    rate_limit_per_minute = models.IntegerField(default=60)
    rate_limit_per_hour = models.IntegerField(default=1000)
    rate_limit_per_day = models.IntegerField(default=10000)
    
    # Metadata
    version = models.CharField(max_length=50, default='1.0.0')
    tags = JSONField(default=list, blank=True)
    metadata = JSONField(default=dict, blank=True)
    
    # Audit fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_integrations'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_integrations'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = IntegrationManager()
    
    class Meta:
        db_table = 'integration_system_integrations'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['integration_type']),
            models.Index(fields=['status']),
            models.Index(fields=['health_status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['integration_type', 'status']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.display_name})"
    
    def clean(self):
        """Validate model data."""
        if self.integration_type == IntegrationType.API and not self.base_url:
            raise ValidationError("API integrations require a base URL")
        
        if self.timeout < 1 or self.timeout > 300:
            raise ValidationError("Timeout must be between 1 and 300 seconds")
        
        if self.retry_attempts < 0 or self.retry_attempts > 10:
            raise ValidationError("Retry attempts must be between 0 and 10")
    
    def is_healthy(self):
        """Check if integration is healthy."""
        return (
            self.status == IntegrationStatus.ACTIVE.value and
            self.health_status == 'healthy' and
            (not self.last_health_check or 
             (timezone.now() - self.last_health_check) < timedelta(minutes=5))
        )
    
    def get_rate_limit_key(self, period='minute'):
        """Get rate limit cache key."""
        return f"integration_rate_limit:{self.id}:{period}"
    
    @property
    def is_active(self):
        """Check if integration is active."""
        return self.status == IntegrationStatus.ACTIVE.value


class IntegrationLog(models.Model):
    """
    Integration operation logs.
    
    Tracks all integration operations, requests, responses,
    and errors for audit and debugging purposes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    
    # Operation details
    operation_type = models.CharField(max_length=100, db_index=True)
    method = models.CharField(max_length=10, blank=True)
    endpoint = models.CharField(max_length=500, blank=True)
    
    # Request/Response data
    request_data = JSONField(default=dict, blank=True)
    response_data = JSONField(default=dict, blank=True)
    headers = JSONField(default=dict, blank=True)
    
    # Status and timing
    status_code = models.IntegerField(null=True, blank=True)
    success = models.BooleanField(default=True, db_index=True)
    error_message = models.TextField(blank=True)
    execution_time_ms = models.IntegerField(null=True, blank=True)
    
    # Request metadata
    request_id = models.CharField(max_length=100, blank=True, db_index=True)
    correlation_id = models.CharField(max_length=100, blank=True, db_index=True)
    user_id = models.IntegerField(null=True, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'integration_system_logs'
        indexes = [
            models.Index(fields=['integration', 'created_at']),
            models.Index(fields=['operation_type']),
            models.Index(fields=['success']),
            models.Index(fields=['request_id']),
            models.Index(fields=['correlation_id']),
            models.Index(fields=['user_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['integration', 'success', 'created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.integration.name} - {self.operation_type} - {self.created_at}"


class WebhookConfiguration(models.Model):
    """
    Webhook configuration for integrations.
    
    Stores webhook endpoints, event subscriptions,
    and delivery settings.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name='webhooks'
    )
    
    # Webhook details
    name = models.CharField(max_length=200)
    url = models.URLField(max_length=500)
    secret = models.CharField(max_length=255, blank=True)
    
    # Event subscriptions
    events = JSONField(default=list, blank=True)  # List of event types
    event_filters = JSONField(default=dict, blank=True)  # Event filtering criteria
    
    # Delivery settings
    timeout = models.IntegerField(default=30)
    retry_attempts = models.IntegerField(default=3)
    retry_delay = models.IntegerField(default=5)
    
    # Security
    signature_header = models.CharField(
        max_length=100,
        default='X-Webhook-Signature'
    )
    signature_algorithm = models.CharField(
        max_length=50,
        default='sha256'
    )
    
    # Status
    active = models.BooleanField(default=True, db_index=True)
    last_delivery = models.DateTimeField(null=True, blank=True)
    delivery_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    
    # Metadata
    headers = JSONField(default=dict, blank=True)
    metadata = JSONField(default=dict, blank=True)
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'integration_system_webhooks'
        indexes = [
            models.Index(fields=['integration', 'active']),
            models.Index(fields=['url']),
            models.Index(fields=['active']),
            models.Index(fields=['last_delivery']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.integration.name} - {self.name}"


class WebhookDelivery(models.Model):
    """
    Webhook delivery tracking.
    
    Records each webhook delivery attempt,
    including retries and failures.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    webhook = models.ForeignKey(
        WebhookConfiguration,
        on_delete=models.CASCADE,
        related_name='deliveries'
    )
    
    # Event data
    event_id = models.CharField(max_length=100, db_index=True)
    event_type = models.CharField(max_length=100, db_index=True)
    event_data = JSONField(default=dict, blank=True)
    
    # Delivery details
    delivery_id = models.CharField(max_length=100, unique=True, db_index=True)
    attempt_count = models.IntegerField(default=1)
    status = models.CharField(
        max_length=50,
        default='pending',
        db_index=True
    )
    
    # Response details
    status_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    response_headers = JSONField(default=dict, blank=True)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    
    # Error handling
    error_message = models.TextField(blank=True)
    last_error = models.TextField(blank=True)
    
    class Meta:
        db_table = 'integration_system_webhook_deliveries'
        indexes = [
            models.Index(fields=['webhook', 'status']),
            models.Index(fields=['event_id']),
            models.Index(fields=['event_type']),
            models.Index(fields=['delivery_id']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['next_retry_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.webhook.name} - {self.event_id} - {self.status}"


class CircuitBreakerState(models.Model):
    """
    Circuit breaker state tracking.
    
    Monitors circuit breaker status for each integration
    and tracks state transitions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.OneToOneField(
        Integration,
        on_delete=models.CASCADE,
        related_name='circuit_breaker'
    )
    
    # Circuit breaker state
    state = models.CharField(
        max_length=50,
        choices=[(s.value, s.name) for s in CircuitBreakerState],
        default=CircuitBreakerState.CLOSED.value,
        db_index=True
    )
    
    # Configuration
    failure_threshold = models.IntegerField(default=5)
    recovery_timeout = models.IntegerField(default=60)
    success_threshold = models.IntegerField(default=3)
    
    # Statistics
    failure_count = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    total_requests = models.IntegerField(default=0)
    
    # Timing
    last_failure_time = models.DateTimeField(null=True, blank=True)
    last_success_time = models.DateTimeField(null=True, blank=True)
    last_state_change = models.DateTimeField(auto_now=True)
    
    # Metadata
    metadata = JSONField(default=dict, blank=True)
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'integration_system_circuit_breakers'
        indexes = [
            models.Index(fields=['integration']),
            models.Index(fields=['state']),
            models.Index(fields=['last_state_change']),
        ]
    
    def __str__(self):
        return f"{self.integration.name} - {self.state}"
    
    def is_open(self):
        """Check if circuit breaker is open."""
        return self.state == CircuitBreakerState.OPEN.value
    
    def is_half_open(self):
        """Check if circuit breaker is half-open."""
        return self.state == CircuitBreakerState.HALF_OPEN.value
    
    def is_closed(self):
        """Check if circuit breaker is closed."""
        return self.state == CircuitBreakerState.CLOSED.value
    
    def get_failure_rate(self):
        """Calculate failure rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.failure_count / self.total_requests) * 100


class IntegrationMetric(models.Model):
    """
    Integration performance metrics.
    
    Stores performance data for monitoring and analytics.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name='metrics'
    )
    
    # Metric details
    metric_name = models.CharField(max_length=100, db_index=True)
    metric_type = models.CharField(max_length=50)  # counter, gauge, histogram
    value = models.DecimalField(max_digits=20, decimal_places=6)
    unit = models.CharField(max_length=50, blank=True)
    
    # Labels and dimensions
    labels = JSONField(default=dict, blank=True)
    dimensions = JSONField(default=dict, blank=True)
    
    # Timing
    timestamp = models.DateTimeField(db_index=True)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Metadata
    metadata = JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'integration_system_metrics'
        indexes = [
            models.Index(fields=['integration', 'metric_name']),
            models.Index(fields=['metric_name']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['period_start', 'period_end']),
            models.Index(fields=['integration', 'timestamp']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.integration.name} - {self.metric_name} - {self.value}"


class IntegrationVersion(models.Model):
    """
    Integration version management.
    
    Tracks different versions of integration configurations
    and manages version compatibility.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name='versions'
    )
    
    # Version details
    version = models.CharField(max_length=50, db_index=True)
    version_number = models.CharField(max_length=50)
    is_active = models.BooleanField(default=False, db_index=True)
    
    # Configuration snapshot
    config_snapshot = JSONField(default=dict, blank=True)
    schema_version = models.CharField(max_length=50, blank=True)
    
    # Compatibility
    compatible_from_version = models.CharField(max_length=50, blank=True)
    compatible_to_version = models.CharField(max_length=50, blank=True)
    deprecated_at = models.DateTimeField(null=True, blank=True)
    
    # Migration
    migration_required = models.BooleanField(default=False)
    migration_script = models.TextField(blank=True)
    
    # Audit fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_integration_versions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'integration_system_versions'
        indexes = [
            models.Index(fields=['integration', 'version']),
            models.Index(fields=['version_number']),
            models.Index(fields=['is_active']),
            models.Index(fields=['deprecated_at']),
        ]
        ordering = ['-created_at']
        unique_together = [['integration', 'version']]
    
    def __str__(self):
        return f"{self.integration.name} - {self.version}"


class IntegrationAuditLog(models.Model):
    """
    Integration audit logs.
    
    Comprehensive audit trail for all integration
    operations and configuration changes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    integration = models.ForeignKey(
        Integration,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        null=True,
        blank=True
    )
    
    # Action details
    action = models.CharField(max_length=100, db_index=True)
    action_type = models.CharField(max_length=50, db_index=True)
    resource_type = models.CharField(max_length=50, db_index=True)
    resource_id = models.CharField(max_length=100, blank=True)
    
    # User and session
    user_id = models.IntegerField(null=True, blank=True, db_index=True)
    username = models.CharField(max_length=255, blank=True)
    session_id = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Content
    message = models.TextField()
    details = JSONField(default=dict, blank=True)
    old_values = JSONField(default=dict, blank=True)
    new_values = JSONField(default=dict, blank=True)
    
    # Classification
    level = models.CharField(
        max_length=20,
        choices=[(l.value, l.name) for l in LogLevel],
        default=LogLevel.INFO.value,
        db_index=True
    )
    category = models.CharField(max_length=50, blank=True, db_index=True)
    
    # Timing
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    correlation_id = models.CharField(max_length=100, blank=True, db_index=True)
    
    class Meta:
        db_table = 'integration_system_audit_logs'
        indexes = [
            models.Index(fields=['integration', 'timestamp']),
            models.Index(fields=['action_type']),
            models.Index(fields=['resource_type']),
            models.Index(fields=['user_id']),
            models.Index(fields=['level']),
            models.Index(fields=['category']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['correlation_id']),
            models.Index(fields=['integration', 'action_type', 'timestamp']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.action} - {self.integration.name if self.integration else 'System'} - {self.timestamp}"


class DataSyncOperation(models.Model):
    """
    Data synchronization operations.
    
    Tracks data sync operations between systems
    including conflicts and resolutions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Operation details
    sync_id = models.CharField(max_length=100, unique=True, db_index=True)
    source_system = models.CharField(max_length=100, db_index=True)
    target_system = models.CharField(max_length=100, db_index=True)
    operation_type = models.CharField(max_length=100, db_index=True)
    
    # Status and timing
    status = models.CharField(
        max_length=50,
        default='pending',
        db_index=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Statistics
    total_records = models.IntegerField(default=0)
    processed_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    conflict_records = models.IntegerField(default=0)
    
    # Configuration
    resolution_strategy = models.CharField(max_length=50, blank=True)
    batch_size = models.IntegerField(default=100)
    
    # Error handling
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    
    # Metadata
    metadata = JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'integration_system_sync_operations'
        indexes = [
            models.Index(fields=['sync_id']),
            models.Index(fields=['source_system', 'target_system']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['operation_type']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.sync_id} - {self.source_system} -> {self.target_system}"
    
    @property
    def duration(self):
        """Get operation duration."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
    
    @property
    def success_rate(self):
        """Get success rate percentage."""
        if self.total_records == 0:
            return 0.0
        return (self.processed_records / self.total_records) * 100


class DataSyncConflict(models.Model):
    """
    Data synchronization conflicts.
    
    Records conflicts detected during sync operations
    and their resolution status.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sync_operation = models.ForeignKey(
        DataSyncOperation,
        on_delete=models.CASCADE,
        related_name='conflicts'
    )
    
    # Conflict details
    conflict_id = models.CharField(max_length=100, db_index=True)
    conflict_type = models.CharField(max_length=50, db_index=True)
    field_name = models.CharField(max_length=100, blank=True)
    
    # Record data
    source_record_id = models.CharField(max_length=100, db_index=True)
    target_record_id = models.CharField(max_length=100, blank=True)
    source_data = JSONField(default=dict, blank=True)
    target_data = JSONField(default=dict, blank=True)
    
    # Resolution
    resolution_status = models.CharField(
        max_length=50,
        default='pending',
        db_index=True
    )
    resolution_strategy = models.CharField(max_length=50, blank=True)
    resolved_data = JSONField(default=dict, blank=True)
    
    # Description
    description = models.TextField()
    
    # Timing
    detected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    metadata = JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'integration_system_sync_conflicts'
        indexes = [
            models.Index(fields=['sync_operation', 'conflict_type']),
            models.Index(fields=['conflict_id']),
            models.Index(fields=['source_record_id']),
            models.Index(fields=['resolution_status']),
            models.Index(fields=['detected_at']),
        ]
        ordering = ['-detected_at']
    
    def __str__(self):
        return f"{self.conflict_id} - {self.conflict_type}"


# Signal handlers for automatic logging
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver


@receiver(post_save, sender=Integration)
def log_integration_changes(sender, instance, created, **kwargs):
    """Log integration configuration changes."""
    from .integ_audit_logs import log_audit_event, AuditActionType, AuditResourceType, AuditLogLevel
    
    action = AuditActionType.INTEGRATION_CREATED if created else AuditActionType.INTEGRATION_UPDATED
    
    asyncio.create_task(
        log_audit_event(
            level=AuditLogLevel.INFO,
            action_type=action,
            resource_type=AuditResourceType.INTEGRATION,
            message=f"Integration {instance.name} {'created' if created else 'updated'}",
            resource_id=str(instance.id),
            details={
                'integration_type': instance.integration_type,
                'status': instance.status,
                'health_status': instance.health_status
            }
        )
    )


@receiver(pre_delete, sender=Integration)
def log_integration_deletion(sender, instance, **kwargs):
    """Log integration deletion."""
    from .integ_audit_logs import log_audit_event, AuditActionType, AuditResourceType, AuditLogLevel
    
    asyncio.create_task(
        log_audit_event(
            level=AuditLogLevel.WARNING,
            action_type=AuditActionType.INTEGRATION_DELETED,
            resource_type=AuditResourceType.INTEGRATION,
            message=f"Integration {instance.name} deleted",
            resource_id=str(instance.id),
            details={
                'integration_type': instance.integration_type,
                'status': instance.status
            }
        )
    )
