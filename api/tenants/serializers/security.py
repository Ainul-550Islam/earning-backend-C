"""
Security Serializers

This module contains serializers for security-related models including
TenantAPIKey, TenantWebhookConfig, TenantIPWhitelist, and TenantAuditLog.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..models.security import TenantAPIKey, TenantWebhookConfig, TenantIPWhitelist, TenantAuditLog

User = get_user_model()


class TenantAPIKeySerializer(serializers.ModelSerializer):
    """
    Serializer for TenantAPIKey model.
    """
    status_display = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    days_until_expiry = serializers.SerializerMethodField()
    last_used_ago = serializers.SerializerMethodField()
    created_by_details = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantAPIKey
        fields = [
            'id', 'tenant', 'name', 'description', 'key_hash', 'key_prefix',
            'scopes', 'allowed_endpoints', 'rate_limit_per_minute',
            'rate_limit_per_hour', 'rate_limit_per_day', 'status',
            'status_display', 'expires_at', 'is_expired', 'days_until_expiry',
            'last_used_at', 'last_used_ago', 'usage_count', 'last_ip_address',
            'last_user_agent', 'require_https', 'allowed_ips', 'allowed_referers',
            'created_by', 'created_by_details', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'key_hash', 'key_prefix', 'usage_count',
            'last_used_at', 'last_ip_address', 'last_user_agent', 'created_by',
            'created_at', 'updated_at'
        ]
    
    def get_status_display(self, obj):
        """Get status display name."""
        return obj.get_status_display()
    
    def get_is_expired(self, obj):
        """Check if API key is expired."""
        return obj.is_expired()
    
    def get_days_until_expiry(self, obj):
        """Get days until expiry."""
        if obj.expires_at:
            delta = obj.expires_at - timezone.now()
            return max(0, delta.days)
        return None
    
    def get_last_used_ago(self, obj):
        """Get time since last used."""
        if obj.last_used_at:
            delta = timezone.now() - obj.last_used_at
            if delta.days > 0:
                return f"{delta.days} days ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600} hours ago"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60} minutes ago"
            else:
                return "Just now"
        return "Never"
    
    def get_created_by_details(self, obj):
        """Get created by user details."""
        if obj.created_by:
            return {
                'id': str(obj.created_by.id),
                'username': obj.created_by.username,
                'email': obj.created_by.email,
            }
        return None
    
    def validate(self, attrs):
        """Validate API key data."""
        # Validate rate limits
        rate_fields = ['rate_limit_per_minute', 'rate_limit_per_hour', 'rate_limit_per_day']
        for field in rate_fields:
            if field in attrs:
                limit = attrs[field]
                if limit < 0:
                    raise serializers.ValidationError(f"{field} cannot be negative.")
        
        # Validate expiry date
        expires_at = attrs.get('expires_at')
        if expires_at and expires_at <= timezone.now():
            raise serializers.ValidationError("Expiration date must be in the future.")
        
        # Validate IP addresses
        allowed_ips = attrs.get('allowed_ips', [])
        for ip in allowed_ips:
            try:
                import ipaddress
                ipaddress.ip_network(ip, strict=False)
            except ValueError:
                raise serializers.ValidationError(f"Invalid IP address or CIDR range: {ip}")
        
        return attrs


class TenantAPIKeyCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new API keys.
    """
    actual_key = serializers.CharField(read_only=True)
    
    class Meta:
        model = TenantAPIKey
        fields = [
            'name', 'description', 'scopes', 'allowed_endpoints',
            'rate_limit_per_minute', 'rate_limit_per_hour', 'rate_limit_per_day',
            'expires_at', 'require_https', 'allowed_ips', 'allowed_referers',
            'actual_key'
        ]
    
    def create(self, validated_data):
        """Create API key with generated key."""
        key = TenantAPIKey.generate_key()
        
        api_key = TenantAPIKey.objects.create(**validated_data)
        api_key.set_key(key)
        api_key.save()
        
        # Store the actual key for one-time display
        api_key.actual_key = key
        
        return api_key


class TenantWebhookConfigSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantWebhookConfig model.
    """
    status_display = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    last_delivery_ago = serializers.SerializerMethodField()
    created_by_details = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantWebhookConfig
        fields = [
            'id', 'tenant', 'name', 'description', 'url', 'secret', 'events',
            'timeout_seconds', 'retry_count', 'retry_delay_seconds',
            'is_active', 'status', 'status_display', 'last_delivery_at',
            'last_delivery_ago', 'last_status_code', 'total_deliveries',
            'successful_deliveries', 'failed_deliveries', 'success_rate',
            'allowed_ips', 'require_https', 'custom_headers', 'auth_type',
            'auth_token', 'created_by', 'created_by_details', 'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'total_deliveries', 'successful_deliveries',
            'failed_deliveries', 'last_delivery_at', 'last_status_code',
            'created_by', 'created_at', 'updated_at'
        ]
    
    def get_status_display(self, obj):
        """Get status display name."""
        return obj.get_status_display()
    
    def get_success_rate(self, obj):
        """Calculate delivery success rate."""
        return obj.success_rate
    
    def get_last_delivery_ago(self, obj):
        """Get time since last delivery."""
        if obj.last_delivery_at:
            delta = timezone.now() - obj.last_delivery_at
            if delta.days > 0:
                return f"{delta.days} days ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600} hours ago"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60} minutes ago"
            else:
                return "Just now"
        return "Never"
    
    def get_created_by_details(self, obj):
        """Get created by user details."""
        if obj.created_by:
            return {
                'id': str(obj.created_by.id),
                'username': obj.created_by.username,
                'email': obj.created_by.email,
            }
        return None
    
    def validate(self, attrs):
        """Validate webhook configuration data."""
        # Validate URL
        url = attrs.get('url')
        if url:
            from django.core.validators import URLValidator
            try:
                URLValidator()(url)
            except:
                raise serializers.ValidationError('Invalid URL format.')
        
        # Validate retry settings
        retry_count = attrs.get('retry_count')
        if retry_count is not None and retry_count < 0:
            raise serializers.ValidationError("Retry count cannot be negative.")
        
        retry_delay = attrs.get('retry_delay_seconds')
        if retry_delay is not None and retry_delay < 0:
            raise serializers.ValidationError("Retry delay cannot be negative.")
        
        timeout = attrs.get('timeout_seconds')
        if timeout is not None and (timeout < 1 or timeout > 300):
            raise serializers.ValidationError("Timeout must be between 1 and 300 seconds.")
        
        # Validate auth token requirement
        auth_type = attrs.get('auth_type')
        auth_token = attrs.get('auth_token')
        
        if auth_type != 'none' and not auth_token:
            raise serializers.ValidationError("Authentication token is required when auth type is not 'none'.")
        
        # Validate HTTPS requirement
        require_https = attrs.get('require_https', True)
        if require_https and url and not url.startswith('https://'):
            raise serializers.ValidationError("HTTPS URL is required when require_https is enabled.")
        
        return attrs


class TenantWebhookConfigCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new webhook configurations.
    """
    secret = serializers.CharField(read_only=True)
    
    class Meta:
        model = TenantWebhookConfig
        fields = [
            'name', 'description', 'url', 'events', 'timeout_seconds',
            'retry_count', 'retry_delay_seconds', 'is_active', 'allowed_ips',
            'require_https', 'custom_headers', 'auth_type', 'auth_token',
            'secret'
        ]
    
    def create(self, validated_data):
        """Create webhook with generated secret."""
        webhook = TenantWebhookConfig.objects.create(**validated_data)
        webhook.set_secret()
        webhook.save()
        return webhook


class TenantIPWhitelistSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantIPWhitelist model.
    """
    last_access_ago = serializers.SerializerMethodField()
    access_count_display = serializers.SerializerMethodField()
    created_by_details = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantIPWhitelist
        fields = [
            'id', 'tenant', 'ip_range', 'label', 'description', 'is_active',
            'last_access_at', 'last_access_ago', 'access_count',
            'access_count_display', 'created_by', 'created_by_details',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'tenant', 'last_access_at', 'access_count', 'created_by',
            'created_at', 'updated_at'
        ]
    
    def get_last_access_ago(self, obj):
        """Get time since last access."""
        if obj.last_access_at:
            delta = timezone.now() - obj.last_access_at
            if delta.days > 0:
                return f"{delta.days} days ago"
            elif delta.seconds > 3600:
                return f"{delta.seconds // 3600} hours ago"
            elif delta.seconds > 60:
                return f"{delta.seconds // 60} minutes ago"
            else:
                return "Just now"
        return "Never"
    
    def get_access_count_display(self, obj):
        """Get formatted access count."""
        if obj.access_count == 0:
            return "Never"
        elif obj.access_count == 1:
            return "Once"
        else:
            return f"{obj.access_count} times"
    
    def get_created_by_details(self, obj):
        """Get created by user details."""
        if obj.created_by:
            return {
                'id': str(obj.created_by.id),
                'username': obj.created_by.username,
                'email': obj.created_by.email,
            }
        return None
    
    def validate_ip_range(self, value):
        """Validate IP range format."""
        try:
            import ipaddress
            ipaddress.ip_network(value, strict=False)
        except ValueError:
            raise serializers.ValidationError("Invalid IP address or CIDR range.")
        return value


class TenantIPWhitelistCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new IP whitelist entries.
    """
    class Meta:
        model = TenantIPWhitelist
        fields = [
            'ip_range', 'label', 'description', 'is_active'
        ]
    
    def validate_ip_range(self, value):
        """Validate IP range uniqueness for tenant."""
        if self.instance and self.instance.ip_range == value:
            return value
        
        if self.context['request'].tenant.ip_whitelists.filter(ip_range=value).exists():
            raise serializers.ValidationError("IP range already exists.")
        
        try:
            import ipaddress
            ipaddress.ip_network(value, strict=False)
        except ValueError:
            raise serializers.ValidationError("Invalid IP address or CIDR range.")
        return value


class TenantAuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for TenantAuditLog model.
    """
    actor_display = serializers.SerializerMethodField()
    action_display = serializers.SerializerMethodField()
    severity_display = serializers.SerializerMethodField()
    target_display = serializers.SerializerMethodField()
    changes_summary = serializers.SerializerMethodField()
    created_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantAuditLog
        fields = [
            'id', 'tenant', 'action', 'action_display', 'severity',
            'severity_display', 'actor', 'actor_display', 'actor_type',
            'model_name', 'object_id', 'object_repr', 'target_display',
            'old_value', 'new_value', 'changes', 'changes_summary',
            'ip_address', 'user_agent', 'request_id', 'description',
            'metadata', 'created_at', 'created_ago'
        ]
        read_only_fields = [
            'id', 'tenant', 'created_at'
        ]
    
    def get_actor_display(self, obj):
        """Get actor display name."""
        return obj.actor_display
    
    def get_action_display(self, obj):
        """Get action display name."""
        return obj.get_action_display()
    
    def get_severity_display(self, obj):
        """Get severity display name."""
        return obj.get_severity_display()
    
    def get_target_display(self, obj):
        """Get target display name."""
        return obj.target_display
    
    def get_changes_summary(self, obj):
        """Get changes summary."""
        return obj.get_changes_summary()
    
    def get_created_ago(self, obj):
        """Get time since creation."""
        delta = timezone.now() - obj.created_at
        if delta.days > 0:
            return f"{delta.days} days ago"
        elif delta.seconds > 3600:
            return f"{delta.seconds // 3600} hours ago"
        elif delta.seconds > 60:
            return f"{delta.seconds // 60} minutes ago"
        else:
            return "Just now"
    
    def validate(self, attrs):
        """Validate audit log data."""
        # Validate severity
        severity = attrs.get('severity')
        if severity and severity not in ['low', 'medium', 'high', 'critical']:
            raise serializers.ValidationError("Invalid severity level.")
        
        # Validate action
        action = attrs.get('action')
        valid_actions = ['create', 'update', 'delete', 'login', 'logout', 'access',
                        'export', 'import', 'config_change', 'security_event',
                        'billing_event', 'api_access', 'webhook_event']
        if action and action not in valid_actions:
            raise serializers.ValidationError("Invalid action type.")
        
        return attrs
