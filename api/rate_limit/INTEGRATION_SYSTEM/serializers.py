from typing import Dict, Any, List, Optional, Union, Tuple, Set, Callable
"""
Integration System Serializers - Django REST Framework

Serializers for the integration system API endpoints including
webhooks, health checks, audit logs, and configuration management.
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime
import json

from .integ_constants import IntegrationEvent, IntegrationStatus, IntegrationPriority
from .integ_exceptions import IntegrationError
from .webhooks_integration import webhook_manager
from .health_check import health_checker, HealthStatus
from .integ_audit_logs import audit_logger, AuditLogLevel, AuditCategory
from .sync_manager import sync_manager, ConflictType, ResolutionStrategy
from .auth_bridge import auth_bridge, PermissionType, ResourceType


class WebhookSerializer(serializers.Serializer):
    """Webhook configuration serializer."""
    url = serializers.URLField(required=True)
    events = serializers.ListField(child=serializers.CharField(), required=True)
    secret = serializers.CharField(required=False, allow_blank=True)
    active = serializers.BooleanField(default=True)
    retry_config = serializers.DictField(required=False)
    headers = serializers.DictField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    
    def validate_events(self, value):
        """Validate webhook events."""
        valid_events = [event.value for event in IntegrationEvent]
        
        for event in value:
            if event not in valid_events:
                raise serializers.ValidationError(f"Invalid event: {event}")
        
        return value
    
    def create(self, validated_data):
        """Create webhook."""
        webhook_id = webhook_manager.register_webhook(validated_data)
        return {"webhook_id": webhook_id, **validated_data}


class WebhookDetailSerializer(serializers.Serializer):
    """Webhook detail serializer."""
    webhook_id = serializers.UUIDField()
    url = serializers.URLField()
    events = serializers.ListField(child=serializers.CharField())
    active = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    last_triggered = serializers.DateTimeField(allow_null=True)
    trigger_count = serializers.IntegerField()
    success_count = serializers.IntegerField()
    failure_count = serializers.IntegerField()
    retry_config = serializers.DictField()
    headers = serializers.DictField()
    description = serializers.CharField(allow_blank=True)


class HealthCheckSerializer(serializers.Serializer):
    """Health check result serializer."""
    check_name = serializers.CharField()
    status = serializers.ChoiceField(choices=[status.value for status in HealthStatus])
    message = serializers.CharField()
    value = serializers.FloatField(allow_null=True)
    threshold = serializers.FloatField(allow_null=True)
    execution_time = serializers.FloatField()
    timestamp = serializers.DateTimeField()
    details = serializers.DictField()
    error = serializers.CharField(allow_null=True)


class SystemHealthSerializer(serializers.Serializer):
    """System health serializer."""
    status = serializers.ChoiceField(choices=[status.value for status in HealthStatus])
    score = serializers.FloatField(min_value=0, max_value=100)
    timestamp = serializers.DateTimeField()
    uptime_seconds = serializers.FloatField()
    issues = serializers.ListField(child=serializers.CharField())
    recommendations = serializers.ListField(child=serializers.CharField())
    summary = serializers.CharField()
    checks = HealthCheckSerializer(many=True)


class PerformanceMetricSerializer(serializers.Serializer):
    """Performance metric serializer."""
    name = serializers.CharField()
    value = serializers.FloatField()
    timestamp = serializers.DateTimeField()
    labels = serializers.DictField()
    unit = serializers.CharField()
    description = serializers.CharField()


class PerformanceStatsSerializer(serializers.Serializer):
    """Performance statistics serializer."""
    total_metrics = serializers.IntegerField()
    total_snapshots = serializers.IntegerField()
    average_execution_time = serializers.FloatField()
    uptime_hours = serializers.FloatField()
    metrics_by_type = serializers.DictField()
    last_snapshot_time = serializers.DateTimeField(allow_null=True)


class AuditLogSerializer(serializers.Serializer):
    """Audit log serializer."""
    log_id = serializers.CharField()
    timestamp = serializers.DateTimeField()
    level = serializers.ChoiceField(choices=[level.value for level in AuditLogLevel])
    category = serializers.ChoiceField(choices=[category.value for category in AuditCategory])
    action = serializers.CharField()
    resource_type = serializers.CharField()
    resource_id = serializers.CharField(allow_null=True)
    user_id = serializers.CharField(allow_null=True)
    ip_address = serializers.CharField(allow_null=True)
    message = serializers.CharField()
    details = serializers.DictField()
    compliance_relevant = serializers.BooleanField()


class AuditStatsSerializer(serializers.Serializer):
    """Audit statistics serializer."""
    total_logs = serializers.IntegerField()
    logs_by_level = serializers.DictField()
    logs_by_category = serializers.DictField()
    logs_by_action = serializers.DictField()
    compliance_logs = serializers.IntegerField()
    archived_logs = serializers.IntegerField()
    failed_logs = serializers.IntegerField()
    queue_size = serializers.IntegerField()


class ConflictSerializer(serializers.Serializer):
    """Conflict serializer."""
    conflict_id = serializers.CharField()
    bridge_name = serializers.CharField()
    conflict_type = serializers.ChoiceField(choices=[ct.value for ct in ConflictType])
    field_name = serializers.CharField()
    source_value = serializers.JSONField()
    target_value = serializers.JSONField()
    severity = serializers.CharField()
    detected_at = serializers.DateTimeField()
    resolved_at = serializers.DateTimeField(allow_null=True)
    resolution_strategy = serializers.ChoiceField(
        choices=[rs.value for rs in ResolutionStrategy],
        allow_null=True
    )
    resolved_value = serializers.JSONField(allow_null=True)
    auto_resolvable = serializers.BooleanField()


class SyncConflictSerializer(serializers.Serializer):
    """Sync conflict serializer."""
    sync_id = serializers.CharField()
    bridge_name = serializers.CharField()
    conflict_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    resolved_at = serializers.DateTimeField(allow_null=True)
    auto_resolved = serializers.BooleanField()
    requires_manual_intervention = serializers.BooleanField()
    resolution_summary = serializers.CharField()
    conflicts = ConflictSerializer(many=True)


class SyncStatsSerializer(serializers.Serializer):
    """Sync statistics serializer."""
    total_conflicts = serializers.IntegerField()
    auto_resolved = serializers.IntegerField()
    manually_resolved = serializers.IntegerField()
    failed_resolutions = serializers.IntegerField()
    conflicts_by_type = serializers.DictField()
    conflicts_by_severity = serializers.DictField()
    average_resolution_time = serializers.FloatField()
    unresolved_conflicts = serializers.IntegerField()


class PermissionSerializer(serializers.Serializer):
    """Permission serializer."""
    name = serializers.CharField()
    resource_type = serializers.ChoiceField(choices=[rt.value for rt in ResourceType])
    permission_type = serializers.ChoiceField(choices=[pt.value for pt in PermissionType])
    description = serializers.CharField()
    is_system = serializers.BooleanField()


class RoleSerializer(serializers.Serializer):
    """Role serializer."""
    name = serializers.CharField()
    description = serializers.CharField()
    permissions = serializers.ListField(child=serializers.CharField())
    is_system = serializers.BooleanField()
    is_active = serializers.BooleanField()


class UserPermissionSerializer(serializers.Serializer):
    """User permission serializer."""
    user_id = serializers.CharField()
    direct_permissions = serializers.ListField(child=serializers.CharField())
    roles = serializers.ListField(child=serializers.CharField())
    all_permissions = serializers.ListField(child=serializers.CharField())
    granted_at = serializers.DateTimeField()
    granted_by = serializers.CharField(allow_null=True)
    expires_at = serializers.DateTimeField(allow_null=True)


class IntegrationServiceSerializer(serializers.Serializer):
    """Integration service serializer."""
    name = serializers.CharField()
    service_type = serializers.CharField()
    protocol = serializers.CharField()
    endpoint = serializers.URLField()
    active = serializers.BooleanField()
    health_check_url = serializers.URLField(allow_null=True)
    timeout = serializers.IntegerField()
    retry_config = serializers.DictField()
    metadata = serializers.DictField()


class IntegrationInstanceSerializer(serializers.Serializer):
    """Integration instance serializer."""
    instance_id = serializers.CharField()
    service_name = serializers.CharField()
    status = serializers.ChoiceField(choices=[status.value for status in IntegrationStatus])
    created_at = serializers.DateTimeField()
    last_activity = serializers.DateTimeField(allow_null=True)
    error_count = serializers.IntegerField()
    success_count = serializers.IntegerField()
    metadata = serializers.DictField()


class IntegrationEventSerializer(serializers.Serializer):
    """Integration event serializer."""
    event_type = serializers.ChoiceField(choices=[event.value for event in IntegrationEvent])
    status = serializers.ChoiceField(choices=[status.value for status in IntegrationStatus])
    priority = serializers.ChoiceField(choices=[priority.value for priority in IntegrationPriority])
    user_id = serializers.CharField(allow_null=True)
    ip_address = serializers.CharField(allow_null=True)
    endpoint = serializers.CharField(allow_null=True)
    metadata = serializers.DictField()
    timestamp = serializers.DateTimeField(default=timezone.now)


class ConflictResolutionSerializer(serializers.Serializer):
    """Conflict resolution serializer."""
    conflict_id = serializers.CharField()
    resolution_strategy = serializers.ChoiceField(choices=[rs.value for rs in ResolutionStrategy])
    resolved_value = serializers.JSONField(allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class CircuitBreakerSerializer(serializers.Serializer):
    """Circuit breaker serializer."""
    name = serializers.CharField()
    state = serializers.CharField()
    failure_count = serializers.IntegerField()
    success_count = serializers.IntegerField()
    last_failure_time = serializers.DateTimeField(allow_null=True)
    last_success_time = serializers.DateTimeField(allow_null=True)
    recovery_timeout = serializers.IntegerField()
    failure_threshold = serializers.IntegerField()


class MessageQueueSerializer(serializers.Serializer):
    """Message queue serializer."""
    name = serializers.CharField()
    queue_type = serializers.CharField()
    size = serializers.IntegerField()
    max_size = serializers.IntegerField()
    processing_rate = serializers.FloatField()
    error_rate = serializers.FloatField()
    created_at = serializers.DateTimeField()
    last_activity = serializers.DateTimeField()


class IntegrationConfigSerializer(serializers.Serializer):
    """Integration configuration serializer."""
    service_name = serializers.CharField()
    protocol = serializers.CharField()
    endpoint = serializers.URLField()
    authentication = serializers.DictField()
    timeout = serializers.IntegerField()
    retry_config = serializers.DictField()
    health_check = serializers.DictField()
    metadata = serializers.DictField()
    
    def validate_protocol(self, value):
        """Validate protocol."""
        from .integ_constants import IntegrationProtocol
        valid_protocols = [protocol.value for protocol in IntegrationProtocol]
        
        if value not in valid_protocols:
            raise serializers.ValidationError(f"Invalid protocol: {value}")
        
        return value
    
    def validate_authentication(self, value):
        """Validate authentication configuration."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Authentication must be a dictionary")
        
        auth_type = value.get('type')
        if auth_type == 'api_key':
            if 'api_key' not in value:
                raise serializers.ValidationError("API key authentication requires 'api_key' field")
        elif auth_type == 'oauth2':
            required_fields = ['client_id', 'client_secret', 'token_url']
            for field in required_fields:
                if field not in value:
                    raise serializers.ValidationError(f"OAuth2 authentication requires '{field}' field")
        
        return value


class IntegrationStatusSerializer(serializers.Serializer):
    """Integration status overview serializer."""
    overall_status = serializers.CharField()
    total_services = serializers.IntegerField()
    active_services = serializers.IntegerField()
    total_instances = serializers.IntegerField()
    healthy_instances = serializers.IntegerField()
    total_events = serializers.IntegerField()
    successful_events = serializers.IntegerField()
    failed_events = serializers.IntegerField()
    uptime_percentage = serializers.FloatField()
    last_updated = serializers.DateTimeField()


class ExportConfigSerializer(serializers.Serializer):
    """Export configuration serializer."""
    format = serializers.ChoiceField(choices=['json', 'csv', 'xml'])
    include_sensitive = serializers.BooleanField(default=False)
    date_range = serializers.DictField(required=False)
    filters = serializers.DictField(required=False)
    
    def validate_date_range(self, value):
        """Validate date range."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Date range must be a dictionary")
        
        start_date = value.get('start_date')
        end_date = value.get('end_date')
        
        if start_date and end_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                
                if start >= end:
                    raise serializers.ValidationError("Start date must be before end date")
                    
            except ValueError:
                raise serializers.ValidationError("Invalid date format. Use ISO 8601 format.")
        
        return value


class BulkOperationSerializer(serializers.Serializer):
    """Bulk operation serializer."""
    operation = serializers.ChoiceField(choices=['create', 'update', 'delete'])
    items = serializers.ListField(child=serializers.DictField())
    options = serializers.DictField(required=False)
    
    def validate_items(self, value):
        """Validate bulk operation items."""
        if not value:
            raise serializers.ValidationError("Items list cannot be empty")
        
        max_items = 1000  # Configure based on system limits
        if len(value) > max_items:
            raise serializers.ValidationError(f"Cannot process more than {max_items} items at once")
        
        return value


class NotificationConfigSerializer(serializers.Serializer):
    """Notification configuration serializer."""
    notification_type = serializers.ChoiceField(choices=['email', 'webhook', 'slack', 'discord'])
    enabled = serializers.BooleanField()
    recipients = serializers.ListField(child=serializers.CharField())
    conditions = serializers.DictField()
    template = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.DictField(required=False)
    
    def validate_recipients(self, value):
        """Validate recipients based on notification type."""
        if not value:
            raise serializers.ValidationError("Recipients list cannot be empty")
        
        return value


class IntegrationTestSerializer(serializers.Serializer):
    """Integration test serializer."""
    test_name = serializers.CharField()
    service_name = serializers.CharField()
    test_type = serializers.ChoiceField(choices=['connectivity', 'authentication', 'data_flow', 'performance'])
    test_data = serializers.DictField(required=False)
    expected_result = serializers.DictField()
    timeout = serializers.IntegerField(default=30)
    
    def validate_test_data(self, value):
        """Validate test data."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Test data must be a dictionary")
        
        return value


class IntegrationReportSerializer(serializers.Serializer):
    """Integration report serializer."""
    report_type = serializers.ChoiceField(choices=['health', 'performance', 'audit', 'usage'])
    date_range = serializers.DictField()
    filters = serializers.DictField(required=False)
    format = serializers.ChoiceField(choices=['json', 'pdf', 'csv'], default='json')
    include_charts = serializers.BooleanField(default=True)
    
    def validate_date_range(self, value):
        """Validate date range."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Date range must be a dictionary")
        
        required_fields = ['start_date', 'end_date']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Date range must include '{field}'")
        
        return value
