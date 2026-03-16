"""
Serializers for Audit Log models
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from .models import (
    AuditLog, AuditLogConfig, AuditLogArchive,
    AuditDashboard, AuditAlertRule, AuditLogLevel
)

User = get_user_model()


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for AuditLog model"""
    
    user = serializers.StringRelatedField(read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    changes = serializers.SerializerMethodField(read_only=True)
    content_object_info = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'anonymous_id', 'user_ip', 'action', 'action_display',
            'level', 'level_display', 'resource_type', 'resource_id',
            'message', 'old_data', 'new_data', 'changes', 'metadata',
            'status_code', 'success', 'error_message',
            'request_method', 'request_path', 'country', 'city',
            'correlation_id', 'timestamp', 'created_at',
            'response_time_ms', 'content_object_info'
        ]
        read_only_fields = fields
    
    def get_changes(self, obj):
        """Extract field changes"""
        return obj.get_changes()
    
    def get_content_object_info(self, obj):
        """Get information about the related object"""
        if not obj.content_object:
            return None
        
        try:
            return {
                'model': obj.content_type.model,
                'id': obj.object_id,
                'repr': str(obj.content_object)[:100]
            }
        except Exception:
            return None
    
    def to_representation(self, instance):
        """Custom representation"""
        data = super().to_representation(instance)
        
        # Truncate long fields for list views
        if self.context.get('view_action') == 'list':
            if data.get('message') and len(data['message']) > 200:
                data['message'] = data['message'][:200] + '...'
            if data.get('error_message') and len(data['error_message']) > 200:
                data['error_message'] = data['error_message'][:200] + '...'
        
        return data


class AuditLogDetailSerializer(AuditLogSerializer):
    """Detailed serializer with all fields"""
    
    request_headers_formatted = serializers.SerializerMethodField()
    request_body_formatted = serializers.SerializerMethodField()
    response_body_formatted = serializers.SerializerMethodField()
    user_details = serializers.SerializerMethodField()
    device_info = serializers.SerializerMethodField()
    
    class Meta(AuditLogSerializer.Meta):
        fields = AuditLogSerializer.Meta.fields + [
            'stack_trace', 'request_params', 'request_headers',
            'request_headers_formatted', 'request_body', 'request_body_formatted',
            'response_body', 'response_body_formatted', 'user_agent',
            'session_id', 'device_id', 'latitude', 'longitude',
            'retention_days', 'archived', 'user_details', 'device_info'
        ]
    
    def get_request_headers_formatted(self, obj):
        """Format request headers for display"""
        if not obj.request_headers:
            return None
        
        # Remove sensitive headers
        sensitive_headers = ['authorization', 'cookie', 'set-cookie', 'x-api-key']
        headers = dict(obj.request_headers)
        
        for header in sensitive_headers:
            if header in headers:
                headers[header] = '*** REDACTED ***'
            if header.title() in headers:
                headers[header.title()] = '*** REDACTED ***'
        
        return json.dumps(headers, indent=2, ensure_ascii=False) if isinstance(headers, dict) else headers
    
    def get_request_body_formatted(self, obj):
        """Format request body for display"""
        if not obj.request_body:
            return None
        
        if isinstance(obj.request_body, dict) and obj.request_body.get('compressed'):
            return f"[COMPRESSED DATA - {obj.request_body.get('size', 0)} bytes]"
        
        return json.dumps(obj.request_body, indent=2, ensure_ascii=False) if isinstance(obj.request_body, dict) else obj.request_body
    
    def get_response_body_formatted(self, obj):
        """Format response body for display"""
        if not obj.response_body:
            return None
        
        if isinstance(obj.response_body, dict) and obj.response_body.get('compressed'):
            return f"[COMPRESSED DATA - {obj.response_body.get('size', 0)} bytes]"
        
        # Remove sensitive data from response
        if isinstance(obj.response_body, dict):
            response = dict(obj.response_body)
            sensitive_fields = ['token', 'access_token', 'refresh_token', 'password', 'api_key']
            
            for field in sensitive_fields:
                if field in response:
                    response[field] = '*** REDACTED ***'
            
            return json.dumps(response, indent=2, ensure_ascii=False)
        
        return obj.response_body
    
    def get_user_details(self, obj):
        """Get additional user details"""
        if not obj.user:
            return None
        
        return {
            'id': obj.user.id,
            'email': obj.user.email,
            'username': obj.user.username,
            'is_active': obj.user.is_active,
            'date_joined': obj.user.date_joined
        }
    
    def get_device_info(self, obj):
        """Parse and extract device information from user_agent"""
        if not obj.user_agent:
            return None
        
        try:
            from user_agents import parse
            
            user_agent = parse(obj.user_agent)
            return {
                'browser': user_agent.browser.family,
                'browser_version': user_agent.browser.version_string,
                'os': user_agent.os.family,
                'os_version': user_agent.os.version_string,
                'device': user_agent.device.family,
                'is_mobile': user_agent.is_mobile,
                'is_tablet': user_agent.is_tablet,
                'is_pc': user_agent.is_pc,
                'is_bot': user_agent.is_bot
            }
        except ImportError:
            return {'raw': obj.user_agent[:100] + '...' if len(obj.user_agent) > 100 else obj.user_agent}
        except Exception:
            return None


class AuditLogCreateSerializer(serializers.Serializer):
    """Serializer for creating audit logs via API"""
    
    action = serializers.CharField(max_length=50)
    level = serializers.ChoiceField(choices=AuditLogLevel.choices, default=AuditLogLevel.INFO)
    message = serializers.CharField()
    
    user_id = serializers.CharField(required=False, allow_null=True)
    anonymous_id = serializers.CharField(required=False, allow_null=True)
    
    resource_type = serializers.CharField(required=False, allow_null=True)
    resource_id = serializers.CharField(required=False, allow_null=True)
    
    old_data = serializers.JSONField(required=False)
    new_data = serializers.JSONField(required=False)
    metadata = serializers.JSONField(required=False, default=dict)
    
    success = serializers.BooleanField(default=True)
    error_message = serializers.CharField(required=False, allow_null=True)
    
    user_ip = serializers.IPAddressField(required=False, allow_null=True)
    user_agent = serializers.CharField(required=False, allow_null=True)
    
    def validate(self, attrs):
        """Validate serializer data"""
        if not attrs.get('user_id') and not attrs.get('anonymous_id'):
            raise serializers.ValidationError(
                "Either user_id or anonymous_id must be provided"
            )
        
        # Validate action
        valid_actions = [action[0] for action in AuditLogAction.choices]
        if attrs['action'] not in valid_actions:
            raise serializers.ValidationError(
                f"Invalid action. Must be one of: {', '.join(valid_actions)}"
            )
        
        return attrs


class AuditLogConfigSerializer(serializers.ModelSerializer):
    """Serializer for AuditLogConfig"""
    
    class Meta:
        model = AuditLogConfig
        fields = [
            'id', 'action', 'enabled', 'log_level', 'log_request_body',
            'log_response_body', 'log_headers', 'retention_days',
            'notify_admins', 'notify_users', 'email_template'
        ]


class AuditLogArchiveSerializer(serializers.ModelSerializer):
    """Serializer for AuditLogArchive"""
    
    class Meta:
        model = AuditLogArchive
        fields = [
            'id', 'start_date', 'end_date', 'total_logs',
            'compressed_size_mb', 'original_size_mb', 'compression_ratio',
            'storage_path', 'created_at'
        ]
        read_only_fields = fields


class AuditDashboardSerializer(serializers.ModelSerializer):
    """Serializer for AuditDashboard"""
    
    created_by = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = AuditDashboard
        fields = [
            'id', 'name', 'description', 'filters', 'columns',
            'refresh_interval', 'is_default', 'created_by',
            'created_at', 'updated_at'
        ]


class AuditAlertRuleSerializer(serializers.ModelSerializer):
    """Serializer for AuditAlertRule"""
    
    class Meta:
        model = AuditAlertRule
        fields = [
            'id', 'name', 'description', 'condition', 'action',
            'action_config', 'severity', 'enabled', 'cooldown_minutes',
            'last_triggered', 'trigger_count'
        ]
    
    def validate_condition(self, value):
        """Validate condition JSON"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Condition must be a JSON object")
        
        required_fields = ['field', 'operator', 'value']
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"Condition must contain '{field}'")
        
        return value


class AuditStatsSerializer(serializers.Serializer):
    """Serializer for audit statistics"""
    
    total_logs = serializers.IntegerField()
    logs_today = serializers.IntegerField()
    logs_this_week = serializers.IntegerField()
    logs_this_month = serializers.IntegerField()
    
    error_logs = serializers.IntegerField()
    warning_logs = serializers.IntegerField()
    security_logs = serializers.IntegerField()
    
    top_actions = serializers.ListField(child=serializers.DictField())
    top_users = serializers.ListField(child=serializers.DictField())
    top_ips = serializers.ListField(child=serializers.DictField())
    
    avg_response_time = serializers.FloatField()
    success_rate = serializers.FloatField()
    
    storage_usage_mb = serializers.FloatField()
    archive_count = serializers.IntegerField()


class AuditLogExportSerializer(serializers.Serializer):
    """Serializer for log export requests"""
    
    format = serializers.ChoiceField(choices=[
        ('json', 'JSON'),
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('pdf', 'PDF')
    ], default='json')
    
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    
    filters = serializers.JSONField(required=False, default=dict)
    fields = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    
    include_archived = serializers.BooleanField(default=False)
    compression = serializers.ChoiceField(
        choices=[('none', 'None'), ('gzip', 'GZIP'), ('zip', 'ZIP')],
        default='none'
    )
    
    def validate(self, attrs):
        """Validate export parameters"""
        if attrs.get('start_date') and attrs.get('end_date'):
            if attrs['start_date'] > attrs['end_date']:
                raise serializers.ValidationError(
                    "start_date must be before end_date"
                )
            
            # Limit export range to 90 days
            max_days = 90
            delta = attrs['end_date'] - attrs['start_date']
            if delta.days > max_days:
                raise serializers.ValidationError(
                    f"Export range cannot exceed {max_days} days"
                )
        
        return attrs