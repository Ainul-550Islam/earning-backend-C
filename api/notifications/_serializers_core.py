# earning_backend/api/notifications/serializers.py
from rest_framework import serializers
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import transaction
from typing import Dict, List, Optional, Any
import json
import uuid
from django.contrib.auth import get_user_model

User = get_user_model()

from .models import (
    Notification, NotificationTemplate, NotificationPreference,
    DeviceToken, NotificationCampaign, NotificationRule,
    NotificationFeedback, NotificationAnalytics, NotificationLog
)
from ._services_core import notification_service, template_service


class BaseSerializer(serializers.ModelSerializer):
    """
    Base serializer with common functionality
    """
    def to_internal_value(self, data):
        # Handle UUID fields
        for field_name, field in self.fields.items():
            if isinstance(field, serializers.UUIDField) and field_name in data:
                try:
                    data[field_name] = str(uuid.UUID(data[field_name]))
                except (ValueError, TypeError):
                    pass
        
        return super().to_internal_value(data)


class UUIDField(serializers.Field):
    """
    Custom UUID field serializer
    """
    def to_representation(self, value):
        return str(value) if value else None
    
    def to_internal_value(self, data):
        try:
            return uuid.UUID(str(data))
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid UUID format")


class JSONField(serializers.Field):
    """
    Custom JSON field serializer
    """
    def to_representation(self, value):
        return value
    
    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid JSON string")
        return data


class TimeAgoField(serializers.Field):
    """
    Field for displaying time ago
    """
    def to_representation(self, value):
        from django.utils.timesince import timesince
        return timesince(value, timezone.now())


class NotificationSerializer(BaseSerializer):
    """
    Serializer for Notification model
    """
    id = UUIDField(read_only=True)
    # user = serializers.PrimaryKeyRelatedField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(
    queryset=User.objects.all(), # এই লাইনটি যোগ করতে হবে
    required=False, 
    allow_null=True
    
)

    is_expired = serializers.BooleanField(read_only=True)
    formatted_age = serializers.CharField(source='get_formatted_age', read_only=True)
    icon_url = serializers.SerializerMethodField()
    priority_score = serializers.IntegerField(source='get_priority_score', read_only=True)
    requires_immediate_attention = serializers.BooleanField(
        source='get_requires_immediate_attention', 
        read_only=True
    )
    thread_depth = serializers.IntegerField(source='get_thread_depth', read_only=True)
    metadata = JSONField(default=dict)
    rich_content = JSONField(default=dict)
    custom_fields = JSONField(default=dict)
    tags = JSONField(default=list)
    
    # Parent notification
    parent_notification = UUIDField(required=False, allow_null=True)
    
    # Reply count
    reply_count = serializers.SerializerMethodField()
    
    # Analytics
    analytics_summary = serializers.SerializerMethodField()
    
    # Preview
    preview = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            # Core fields
            'id', 'user', 'title', 'message',
            
            # Classification
            'notification_type', 'priority', 'channel', 'status',
            
            # Status tracking
            'is_read', 'is_sent', 'is_delivered', 'is_archived', 'is_pinned',
            'is_deleted', 'created_at', 'updated_at', 'sent_at', 'delivered_at',
            'read_at', 'archived_at', 'deleted_at', 'scheduled_for', 'expire_date',
            
            # Metadata
            'metadata', 'rich_content', 'custom_fields', 'tags',
            'group_id', 'campaign_id', 'campaign_name', 'batch_id',
            
            # Advanced features
            'image_url', 'icon_url', 'thumbnail_url', 'action_url',
            'action_text', 'deep_link', 'device_type', 'platform',
            'language', 'sound_enabled', 'sound_name', 'vibration_enabled',
            'vibration_pattern', 'led_color', 'led_blink_pattern',
            'badge_count', 'custom_style', 'position', 'animation',
            'is_dismissible', 'auto_dismiss_after', 'show_progress',
            'progress_value', 'feedback_enabled', 'feedback_options',
            
            # Parent/child relationships
            'parent_notification', 'reply_count',
            
            # Analytics
            'click_count', 'view_count', 'impression_count',
            'delivery_attempts', 'last_delivery_attempt',
            'delivery_error', 'engagement_score', 'open_rate',
            'click_through_rate', 'conversion_rate', 'cost',
            'cost_currency', 'variant', 'priority_boost',
            
            # Computed fields
            'formatted_age', 'is_expired', 'icon_url',
            'priority_score', 'requires_immediate_attention',
            'thread_depth', 'analytics_summary', 'preview',
            
            # Audit fields
            'created_by', 'modified_by', 'deleted_by', 'version',
            'previous_version', 'archive_reason',
            
            # Auto-cleanup
            'auto_delete_after_read', 'auto_delete_after_days',
            
            # Security
            'is_encrypted', 'encryption_key',
            
            # Retry configuration
            'max_retries', 'retry_interval',
        ]
        read_only_fields = [
            'id', 'user', 'created_at', 'updated_at', 'sent_at',
            'delivered_at', 'read_at', 'archived_at', 'deleted_at',
            'click_count', 'view_count', 'impression_count',
            'delivery_attempts', 'last_delivery_attempt',
            'delivery_error', 'engagement_score', 'open_rate',
            'click_through_rate', 'conversion_rate', 'is_sent',
            'is_delivered', 'created_by', 'modified_by', 'deleted_by',
            'version', 'formatted_age', 'is_expired',
            'priority_score', 'requires_immediate_attention',
            'thread_depth', 'reply_count', 'analytics_summary',
            'preview',
        ]
    
    def get_icon_url(self, obj):
        return obj.get_icon_url()
    
    def get_reply_count(self, obj):
        return obj.replies.filter(is_deleted=False).count()
    
    def get_analytics_summary(self, obj):
        return obj.get_analytics_summary()
    
    def get_preview(self, obj):
        return obj.generate_preview()
    
    def validate(self, data):
        """
        Validate notification data
        """
        # Validate expire_date
        expire_date = data.get('expire_date')
        if expire_date and expire_date < timezone.now():
            raise serializers.ValidationError({
                'expire_date': 'Expire date cannot be in the past.'
            })
        
        # Validate scheduled_for
        scheduled_for = data.get('scheduled_for')
        if scheduled_for and scheduled_for < timezone.now():
            raise serializers.ValidationError({
                'scheduled_for': 'Scheduled time cannot be in the past.'
            })
        
        # Validate progress_value
        progress_value = data.get('progress_value')
        if progress_value is not None and (progress_value < 0 or progress_value > 100):
            raise serializers.ValidationError({
                'progress_value': 'Progress value must be between 0 and 100.'
            })
        
        # Validate parent_notification
        parent_id = data.get('parent_notification')
        if parent_id:
            try:
                parent = Notification.objects.get(id=parent_id)
                # Check if parent belongs to same user
                user = self.context.get('request').user if self.context.get('request') else None
                if user and parent.user != user:
                    raise serializers.ValidationError({
                        'parent_notification': 'Parent notification does not belong to you.'
                    })
            except Notification.DoesNotExist:
                raise serializers.ValidationError({
                    'parent_notification': 'Parent notification not found.'
                })
        
        return data


class CreateNotificationSerializer(serializers.Serializer):
    """
    Serializer for creating notifications
    """
    user_id = serializers.IntegerField(required=False)
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()
    notification_type = serializers.ChoiceField(
        choices=Notification.NOTIFICATION_TYPES,
        default='general'
    )
    priority = serializers.ChoiceField(
        choices=Notification.PRIORITY_LEVELS,
        default='medium'
    )
    channel = serializers.ChoiceField(
        choices=Notification.CHANNEL_CHOICES,
        default='in_app'
    )
    
    # Optional fields
    metadata = JSONField(default=dict, required=False)
    image_url = serializers.URLField(max_length=1000, required=False, allow_blank=True)
    icon_url = serializers.URLField(max_length=1000, required=False, allow_blank=True)
    thumbnail_url = serializers.URLField(max_length=1000, required=False, allow_blank=True)
    action_url = serializers.URLField(max_length=1000, required=False, allow_blank=True)
    action_text = serializers.CharField(max_length=100, required=False, allow_blank=True)
    deep_link = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    expire_date = serializers.DateTimeField(required=False, allow_null=True)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    tags = JSONField(default=list, required=False)
    campaign_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    campaign_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    group_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    # Device info
    device_type = serializers.ChoiceField(
        choices=Notification.DEVICE_TYPES,
        default='unknown',
        required=False
    )
    platform = serializers.ChoiceField(
        choices=Notification.PLATFORM_CHOICES,
        default='web',
        required=False
    )
    language = serializers.ChoiceField(
        choices=Notification.LANGUAGE_CHOICES,
        default='en',
        required=False
    )
    
    # Settings
    is_pinned = serializers.BooleanField(default=False, required=False)
    sound_enabled = serializers.BooleanField(default=True, required=False)
    vibration_enabled = serializers.BooleanField(default=True, required=False)
    badge_count = serializers.IntegerField(
        default=1,
        min_value=0,
        max_value=999,
        required=False
    )
    
    # Content
    rich_content = JSONField(default=dict, required=False)
    custom_fields = JSONField(default=dict, required=False)
    
    # Delivery options
    check_duplicate = serializers.BooleanField(default=True, required=False)
    send_immediately = serializers.BooleanField(default=True, required=False)
    
    def validate(self, data):
        """
        Validate notification creation data
        """
        request = self.context.get('request')
        
        # Set user
        if 'user_id' in data:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                data['user'] = User.objects.get(id=data['user_id'])
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'user_id': 'User not found.'
                })
        elif request and request.user:
            data['user'] = request.user
        else:
            raise serializers.ValidationError({
                'user': 'User is required.'
            })
        
        # Validate expire_date
        expire_date = data.get('expire_date')
        if expire_date and expire_date < timezone.now():
            raise serializers.ValidationError({
                'expire_date': 'Expire date cannot be in the past.'
            })
        
        # Validate scheduled_for
        scheduled_for = data.get('scheduled_for')
        if scheduled_for and scheduled_for < timezone.now():
            raise serializers.ValidationError({
                'scheduled_for': 'Scheduled time cannot be in the past.'
            })
        
        # Check user permissions (if creating for another user)
        if data['user'] != request.user and not request.user.is_staff:
            raise serializers.ValidationError({
                'user_id': 'You do not have permission to create notifications for other users.'
            })
        
        return data
    
    def create(self, validated_data):
        """
        Create notification using service
        """
        # Extract user
        user = validated_data.pop('user')
        
        # Extract creation options
        check_duplicate = validated_data.pop('check_duplicate', True)
        send_immediately = validated_data.pop('send_immediately', True)
        
        # Create notification
        notification = notification_service.create_notification(
            user=user,
            check_duplicate=check_duplicate,
            send_immediately=send_immediately,
            **validated_data
        )
        
        if not notification:
            raise serializers.ValidationError(
                'Failed to create notification. Check user preferences or rate limits.'
            )
        
        return notification


class UpdateNotificationSerializer(BaseSerializer):
    """
    Serializer for updating notifications
    """
    is_read = serializers.BooleanField(required=False)
    is_pinned = serializers.BooleanField(required=False)
    is_archived = serializers.BooleanField(required=False)
    tags = JSONField(default=list, required=False)
    metadata = JSONField(default=dict, required=False)
    progress_value = serializers.FloatField(
        required=False,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)]
    )
    
    class Meta:
        model = Notification
        fields = [
            'is_read', 'is_pinned', 'is_archived', 'tags', 'metadata',
            'progress_value', 'action_url', 'action_text', 'icon_url',
            'image_url', 'sound_enabled', 'vibration_enabled', 'badge_count',
            'custom_style', 'position', 'animation', 'is_dismissible',
            'auto_dismiss_after', 'show_progress', 'feedback_enabled',
            'feedback_options', 'expire_date',
        ]
    
    def update(self, instance, validated_data):
        """
        Update notification
        """
        # Handle is_read separately to update read_at
        is_read = validated_data.get('is_read')
        if is_read is not None:
            if is_read and not instance.is_read:
                instance.mark_as_read()
            elif not is_read and instance.is_read:
                instance.mark_as_unread()
            validated_data.pop('is_read', None)
        
        # Handle is_archived
        is_archived = validated_data.get('is_archived')
        if is_archived is not None:
            if is_archived and not instance.is_archived:
                instance.archive()
            elif not is_archived and instance.is_archived:
                instance.unarchive()
            validated_data.pop('is_archived', None)
        
        # Handle is_pinned
        is_pinned = validated_data.get('is_pinned')
        if is_pinned is not None:
            if is_pinned and not instance.is_pinned:
                instance.pin()
            elif not is_pinned and instance.is_pinned:
                instance.unpin()
            validated_data.pop('is_pinned', None)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance


class BulkNotificationSerializer(serializers.Serializer):
    """
    Serializer for bulk notification operations
    """
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=1000
    )
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()
    notification_type = serializers.ChoiceField(
        choices=Notification.NOTIFICATION_TYPES,
        default='general'
    )
    priority = serializers.ChoiceField(
        choices=Notification.PRIORITY_LEVELS,
        default='medium'
    )
    channel = serializers.ChoiceField(
        choices=Notification.CHANNEL_CHOICES,
        default='in_app'
    )
    
    # Optional fields
    metadata = JSONField(default=dict, required=False)
    image_url = serializers.URLField(required=False, allow_blank=True)
    icon_url = serializers.URLField(required=False, allow_blank=True)
    action_url = serializers.URLField(required=False, allow_blank=True)
    action_text = serializers.CharField(max_length=100, required=False, allow_blank=True)
    expire_date = serializers.DateTimeField(required=False, allow_null=True)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    tags = JSONField(default=list, required=False)
    campaign_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    campaign_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    
    # Batch options
    batch_id = serializers.CharField(max_length=100, required=False, allow_blank=True)
    send_immediately = serializers.BooleanField(default=True, required=False)
    
    def validate_user_ids(self, value):
        """
        Validate user IDs
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Check if all users exist
        existing_users = User.objects.filter(id__in=value)
        existing_ids = set(existing_users.values_list('id', flat=True))
        
        if len(existing_ids) != len(value):
            missing_ids = set(value) - existing_ids
            raise serializers.ValidationError(
                f"Some users not found: {missing_ids}"
            )
        
        return value
    
    def create(self, validated_data):
        """
        Create bulk notifications
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get users
        user_ids = validated_data.pop('user_ids')
        users = User.objects.filter(id__in=user_ids)
        
        # Extract batch options
        batch_id = validated_data.pop('batch_id', None)
        send_immediately = validated_data.pop('send_immediately', True)
        
        # Create bulk notifications
        results = notification_service.create_bulk_notifications(
            users=list(users),
            batch_id=batch_id,
            **validated_data
        )
        
        return results


class NotificationTemplateSerializer(BaseSerializer):
    """
    Serializer for NotificationTemplate model
    """
    id = UUIDField(read_only=True)
    variables = JSONField(default=list)
    sample_data = JSONField(default=dict)
    metadata_template = JSONField(default=dict)
    allowed_groups = JSONField(default=list)
    allowed_roles = JSONField(default=list)
    tags = JSONField(default=list)
    
    # Preview
    preview = serializers.SerializerMethodField()
    rendered_example = serializers.SerializerMethodField()
    
    # Usage stats
    usage_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = NotificationTemplate
        fields = [
            # Basic info
            'id', 'name', 'description',
            
            # Content
            'template_type', 'title_en', 'title_bn', 'message_en', 'message_bn',
            'action_text_en', 'action_text_bn',
            
            # Default values
            'default_priority', 'default_channel', 'default_language',
            
            # Template configuration
            'variables', 'sample_data', 'metadata_template',
            'action_url_template', 'deep_link_template',
            
            # Visual elements
            'icon_url', 'image_url',
            
            # Categorization
            'category', 'tags',
            
            # Access control
            'is_active', 'is_public', 'allowed_groups', 'allowed_roles',
            
            # Usage tracking
            'usage_count', 'last_used',
            
            # Versioning
            'version', 'parent_template',
            
            # Audit fields
            'created_by', 'created_at', 'updated_at', 'updated_by',
            
            # Computed fields
            'preview', 'rendered_example', 'usage_rate',
        ]
        read_only_fields = [
            'id', 'usage_count', 'last_used', 'version',
            'created_by', 'created_at', 'updated_at', 'updated_by',
            'preview', 'rendered_example', 'usage_rate',
        ]
    
    def get_preview(self, obj):
        return obj.get_preview()
    
    def get_rendered_example(self, obj):
        """
        Get rendered example using sample data
        """
        try:
            from .utils import TemplateRenderer
            renderer = TemplateRenderer()
            rendered = renderer.render_template(obj, obj.sample_data)
            return rendered
        except:
            return None
    
    def get_usage_rate(self, obj):
        """
        Calculate usage rate (notifications per day)
        """
        if obj.created_at:
            days_since_creation = (timezone.now() - obj.created_at).days
            if days_since_creation > 0:
                return obj.usage_count / days_since_creation
        return 0
    
    def validate_name(self, value):
        """
        Validate template name
        """
        # Check if name is unique (excluding current instance)
        instance = getattr(self, 'instance', None)
        if instance:
            if NotificationTemplate.objects.filter(name=value).exclude(id=instance.id).exists():
                raise serializers.ValidationError(
                    "A template with this name already exists."
                )
        else:
            if NotificationTemplate.objects.filter(name=value).exists():
                raise serializers.ValidationError(
                    "A template with this name already exists."
                )
        
        return value
    
    def validate_variables(self, value):
        """
        Validate template variables
        """
        if not isinstance(value, list):
            raise serializers.ValidationError("Variables must be a list.")
        
        for var in value:
            if not isinstance(var, dict):
                raise serializers.ValidationError("Each variable must be a dictionary.")
            
            if 'name' not in var:
                raise serializers.ValidationError("Variable must have a 'name' field.")
            
            if not isinstance(var['name'], str):
                raise serializers.ValidationError("Variable name must be a string.")
            
            # Validate variable type
            var_type = var.get('type', 'string')
            if var_type not in ['string', 'number', 'boolean', 'array', 'object']:
                raise serializers.ValidationError(
                    f"Invalid variable type: {var_type}"
                )
        
        return value


class CreateTemplateSerializer(serializers.Serializer):
    """
    Serializer for creating templates
    """
    name = serializers.CharField(max_length=255)
    title_en = serializers.CharField(max_length=255)
    message_en = serializers.CharField()
    template_type = serializers.ChoiceField(
        choices=Notification.NOTIFICATION_TYPES,
        default='general'
    )
    
    # Optional fields
    description = serializers.CharField(required=False, allow_blank=True)
    title_bn = serializers.CharField(required=False, allow_blank=True)
    message_bn = serializers.CharField(required=False, allow_blank=True)
    default_priority = serializers.ChoiceField(
        choices=Notification.PRIORITY_LEVELS,
        default='medium',
        required=False
    )
    default_channel = serializers.ChoiceField(
        choices=Notification.CHANNEL_CHOICES,
        default='in_app',
        required=False
    )
    default_language = serializers.ChoiceField(
        choices=Notification.LANGUAGE_CHOICES,
        default='en',
        required=False
    )
    variables = JSONField(default=list, required=False)
    sample_data = JSONField(default=dict, required=False)
    icon_url = serializers.URLField(required=False, allow_blank=True)
    image_url = serializers.URLField(required=False, allow_blank=True)
    action_url_template = serializers.CharField(required=False, allow_blank=True)
    action_text_en = serializers.CharField(required=False, allow_blank=True)
    action_text_bn = serializers.CharField(required=False, allow_blank=True)
    deep_link_template = serializers.CharField(required=False, allow_blank=True)
    metadata_template = JSONField(default=dict, required=False)
    category = serializers.CharField(max_length=50, required=False)
    tags = JSONField(default=list, required=False)
    is_active = serializers.BooleanField(default=True, required=False)
    is_public = serializers.BooleanField(default=False, required=False)
    allowed_groups = JSONField(default=list, required=False)
    allowed_roles = JSONField(default=list, required=False)
    
    def validate(self, data):
        """
        Validate template data
        """
        # Check if template name already exists
        name = data.get('name')
        if NotificationTemplate.objects.filter(name=name).exists():
            raise serializers.ValidationError({
                'name': 'A template with this name already exists.'
            })
        
        # Validate variables
        variables = data.get('variables', [])
        for var in variables:
            if not isinstance(var, dict) or 'name' not in var:
                raise serializers.ValidationError({
                    'variables': 'Each variable must be a dictionary with a "name" field.'
                })
        
        return data
    
    def create(self, validated_data):
        """
        Create template using service
        """
        request = self.context.get('request')
        created_by = request.user if request else None
        
        template = template_service.create_template(
            created_by=created_by,
            **validated_data
        )
        
        if not template:
            raise serializers.ValidationError(
                'Failed to create template.'
            )
        
        return template


class UpdateTemplateSerializer(serializers.Serializer):
    """
    Serializer for updating templates
    """
    title_en = serializers.CharField(required=False)
    message_en = serializers.CharField(required=False)
    title_bn = serializers.CharField(required=False, allow_blank=True)
    message_bn = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    default_priority = serializers.ChoiceField(
        choices=Notification.PRIORITY_LEVELS,
        required=False
    )
    default_channel = serializers.ChoiceField(
        choices=Notification.CHANNEL_CHOICES,
        required=False
    )
    default_language = serializers.ChoiceField(
        choices=Notification.LANGUAGE_CHOICES,
        required=False
    )
    variables = JSONField(required=False)
    sample_data = JSONField(required=False)
    icon_url = serializers.URLField(required=False, allow_blank=True)
    image_url = serializers.URLField(required=False, allow_blank=True)
    action_url_template = serializers.CharField(required=False, allow_blank=True)
    action_text_en = serializers.CharField(required=False, allow_blank=True)
    action_text_bn = serializers.CharField(required=False, allow_blank=True)
    deep_link_template = serializers.CharField(required=False, allow_blank=True)
    metadata_template = JSONField(required=False)
    category = serializers.CharField(max_length=50, required=False)
    tags = JSONField(required=False)
    is_active = serializers.BooleanField(required=False)
    is_public = serializers.BooleanField(required=False)
    allowed_groups = JSONField(required=False)
    allowed_roles = JSONField(required=False)
    
    def update(self, instance, validated_data):
        """
        Update template using service
        """
        request = self.context.get('request')
        updated_by = request.user if request else None
        
        template = template_service.update_template(
            template_id=str(instance.id),
            updated_by=updated_by,
            **validated_data
        )
        
        if not template:
            raise serializers.ValidationError(
                'Failed to update template.'
            )
        
        return template


class TemplateRenderSerializer(serializers.Serializer):
    """
    Serializer for rendering templates
    """
    template_name = serializers.CharField()
    context = JSONField(default=dict)
    language = serializers.ChoiceField(
        choices=Notification.LANGUAGE_CHOICES,
        default='en'
    )
    
    def validate(self, data):
        """
        Validate template rendering data
        """
        template_name = data.get('template_name')
        
        # Get template
        template = notification_service.get_template(template_name)
        if not template:
            raise serializers.ValidationError({
                'template_name': 'Template not found or inactive.'
            })
        
        # Check if user can access template
        request = self.context.get('request')
        if request and request.user:
            if not template.is_public and not template_service._user_can_access_template(request.user, template):
                raise serializers.ValidationError({
                    'template_name': 'You do not have permission to access this template.'
                })
        
        data['template'] = template
        return data
    
    def create(self, validated_data):
        """
        Render template
        """
        template = validated_data['template']
        context = validated_data['context']
        language = validated_data['language']
        
        # Render template
        try:
            rendered = template_service.render_template(template, context, language)
            return {
                'template': template.name,
                'language': language,
                'rendered': rendered
            }
        except Exception as e:
            raise serializers.ValidationError({
                'render_error': str(e)
            })


class NotificationPreferenceSerializer(BaseSerializer):
    """
    Serializer for NotificationPreference model
    """
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    
    # Stats
    stats = serializers.SerializerMethodField()
    
    # Computed fields
    is_in_quiet_hours = serializers.BooleanField(read_only=True)
    is_in_do_not_disturb = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = NotificationPreference
        fields = [
            # Basic info
            'id', 'user',
            
            # Channel preferences
            'enable_in_app', 'enable_push', 'enable_email', 'enable_sms',
            'enable_telegram', 'enable_whatsapp', 'enable_browser',
            
            # Type preferences
            'enable_system_notifications', 'enable_financial_notifications',
            'enable_task_notifications', 'enable_security_notifications',
            'enable_marketing_notifications', 'enable_social_notifications',
            'enable_support_notifications', 'enable_achievement_notifications',
            'enable_gamification_notifications',
            
            # Priority preferences
            'enable_lowest_priority', 'enable_low_priority',
            'enable_medium_priority', 'enable_high_priority',
            'enable_urgent_priority', 'enable_critical_priority',
            
            # Notification settings
            'sound_enabled', 'vibration_enabled', 'led_enabled', 'badge_enabled',
            
            # Quiet hours
            'quiet_hours_enabled', 'quiet_hours_start', 'quiet_hours_end',
            
            # Do not disturb
            'do_not_disturb', 'do_not_disturb_until',
            
            # Language preference
            'preferred_language',
            
            # Delivery preferences
            'prefer_in_app', 'group_notifications', 'show_previews',
            
            # Auto-cleanup
            'auto_delete_read', 'auto_delete_after_days',
            
            # Notification limits
            'max_notifications_per_day', 'max_push_per_day',
            'max_email_per_day', 'max_sms_per_day',
            
            # Analytics
            'total_notifications_received', 'total_notifications_read',
            'total_notifications_clicked', 'average_open_time',
            'average_click_time',
            
            # Timestamps
            'created_at', 'updated_at',
            
            # Computed fields
            'stats', 'is_in_quiet_hours', 'is_in_do_not_disturb',
        ]
        read_only_fields = [
            'id', 'user', 'created_at', 'updated_at',
            'total_notifications_received', 'total_notifications_read',
            'total_notifications_clicked', 'average_open_time',
            'average_click_time', 'stats', 'is_in_quiet_hours',
            'is_in_do_not_disturb',
        ]
    
    def get_stats(self, obj):
        return obj.get_stats()


class UpdatePreferenceSerializer(serializers.Serializer):
    """
    Serializer for updating preferences
    """
    # Channel preferences
    enable_in_app = serializers.BooleanField(required=False)
    enable_push = serializers.BooleanField(required=False)
    enable_email = serializers.BooleanField(required=False)
    enable_sms = serializers.BooleanField(required=False)
    enable_telegram = serializers.BooleanField(required=False)
    enable_whatsapp = serializers.BooleanField(required=False)
    enable_browser = serializers.BooleanField(required=False)
    
    # Type preferences
    enable_system_notifications = serializers.BooleanField(required=False)
    enable_financial_notifications = serializers.BooleanField(required=False)
    enable_task_notifications = serializers.BooleanField(required=False)
    enable_security_notifications = serializers.BooleanField(required=False)
    enable_marketing_notifications = serializers.BooleanField(required=False)
    enable_social_notifications = serializers.BooleanField(required=False)
    enable_support_notifications = serializers.BooleanField(required=False)
    enable_achievement_notifications = serializers.BooleanField(required=False)
    enable_gamification_notifications = serializers.BooleanField(required=False)
    
    # Priority preferences
    enable_lowest_priority = serializers.BooleanField(required=False)
    enable_low_priority = serializers.BooleanField(required=False)
    enable_medium_priority = serializers.BooleanField(required=False)
    enable_high_priority = serializers.BooleanField(required=False)
    enable_urgent_priority = serializers.BooleanField(required=False)
    enable_critical_priority = serializers.BooleanField(required=False)
    
    # Notification settings
    sound_enabled = serializers.BooleanField(required=False)
    vibration_enabled = serializers.BooleanField(required=False)
    led_enabled = serializers.BooleanField(required=False)
    badge_enabled = serializers.BooleanField(required=False)
    
    # Quiet hours
    quiet_hours_enabled = serializers.BooleanField(required=False)
    quiet_hours_start = serializers.TimeField(required=False, allow_null=True)
    quiet_hours_end = serializers.TimeField(required=False, allow_null=True)
    
    # Do not disturb
    do_not_disturb = serializers.BooleanField(required=False)
    do_not_disturb_until = serializers.DateTimeField(required=False, allow_null=True)
    
    # Language preference
    preferred_language = serializers.ChoiceField(
        choices=Notification.LANGUAGE_CHOICES,
        required=False
    )
    
    # Delivery preferences
    prefer_in_app = serializers.BooleanField(required=False)
    group_notifications = serializers.BooleanField(required=False)
    show_previews = serializers.BooleanField(required=False)
    
    # Auto-cleanup
    auto_delete_read = serializers.BooleanField(required=False)
    auto_delete_after_days = serializers.IntegerField(
        min_value=1,
        max_value=365,
        required=False
    )
    
    # Notification limits
    max_notifications_per_day = serializers.IntegerField(
        min_value=1,
        max_value=1000,
        required=False
    )
    max_push_per_day = serializers.IntegerField(
        min_value=1,
        max_value=100,
        required=False
    )
    max_email_per_day = serializers.IntegerField(
        min_value=1,
        max_value=50,
        required=False
    )
    max_sms_per_day = serializers.IntegerField(
        min_value=1,
        max_value=10,
        required=False
    )
    
    def validate_quiet_hours_start(self, value):
        """
        Validate quiet hours start time
        """
        if value and not self.initial_data.get('quiet_hours_end'):
            raise serializers.ValidationError(
                "quiet_hours_end is required when setting quiet_hours_start."
            )
        return value
    
    def validate_quiet_hours_end(self, value):
        """
        Validate quiet hours end time
        """
        if value and not self.initial_data.get('quiet_hours_start'):
            raise serializers.ValidationError(
                "quiet_hours_start is required when setting quiet_hours_end."
            )
        return value
    
    def validate(self, data):
        """
        Validate quiet hours
        """
        quiet_hours_start = data.get('quiet_hours_start')
        quiet_hours_end = data.get('quiet_hours_end')
        
        if quiet_hours_start and quiet_hours_end:
            if quiet_hours_start == quiet_hours_end:
                raise serializers.ValidationError({
                    'quiet_hours_start': 'Start and end times cannot be the same.',
                    'quiet_hours_end': 'Start and end times cannot be the same.'
                })
        
        return data
    
    def update(self, instance, validated_data):
        """
        Update preferences using service
        """
        from ._services_core import preferences_service
        
        request = self.context.get('request')
        updated_by = request.user if request else None
        
        preferences = preferences_service.update_preferences(
            user=instance.user,
            updates=validated_data,
            updated_by=updated_by
        )
        
        if not preferences:
            raise serializers.ValidationError(
                'Failed to update preferences.'
            )
        
        return preferences


class DeviceTokenSerializer(BaseSerializer):
    """
    Serializer for DeviceToken model
    """
    id = UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    web_push_token = JSONField(default=dict)
    
    # Computed fields
    delivery_rate = serializers.SerializerMethodField()

    
    class Meta:
        model = DeviceToken
        fields = [
            # Basic info
            'id', 'user', 'token',
            
            # Device info
            'device_type', 'platform', 'app_version', 'os_version',
            'device_model', 'device_name', 'manufacturer',
            
            # Push tokens
            'fcm_token', 'apns_token', 'web_push_token',
            
            # Status
            'is_active', 'last_active',
            
            # Location
            'ip_address', 'country', 'city', 'timezone', 'language',
            
            # Settings
            'push_enabled', 'sound_enabled', 'vibration_enabled',
            
            # Statistics
            'push_sent', 'push_delivered', 'push_failed', 'last_push_sent',
            
            # Timestamps
            'created_at', 'updated_at',
            
            # Computed fields
            'delivery_rate',
        ]
        read_only_fields = [
            'id', 'user', 'push_sent', 'push_delivered', 'push_failed',
            'last_push_sent', 'created_at', 'updated_at', 'last_active',
            'delivery_rate',
        ]
    
    def get_delivery_rate(self, obj):
        return obj.get_delivery_rate()


class RegisterDeviceSerializer(serializers.Serializer):
    """
    Serializer for registering devices
    """
    token = serializers.CharField(max_length=500)
    device_type = serializers.ChoiceField(
        choices=Notification.DEVICE_TYPES
    )
    platform = serializers.ChoiceField(
        choices=Notification.PLATFORM_CHOICES
    )
    
    # Optional fields
    app_version = serializers.CharField(max_length=20, required=False, allow_blank=True)
    os_version = serializers.CharField(max_length=20, required=False, allow_blank=True)
    device_model = serializers.CharField(max_length=100, required=False, allow_blank=True)
    device_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    manufacturer = serializers.CharField(max_length=100, required=False, allow_blank=True)
    fcm_token = serializers.CharField(max_length=500, required=False, allow_blank=True)
    apns_token = serializers.CharField(max_length=500, required=False, allow_blank=True)
    web_push_token = JSONField(default=dict, required=False)
    ip_address = serializers.IPAddressField(required=False, allow_null=True)
    country = serializers.CharField(max_length=100, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    timezone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    language = serializers.ChoiceField(
        choices=Notification.LANGUAGE_CHOICES,
        default='en',
        required=False
    )
    push_enabled = serializers.BooleanField(default=True, required=False)
    sound_enabled = serializers.BooleanField(default=True, required=False)
    vibration_enabled = serializers.BooleanField(default=True, required=False)
    
    def create(self, validated_data):
        """
        Register device using service
        """
        from ._services_core import device_service
        
        request = self.context.get('request')
        user = request.user if request else None
        
        if not user:
            raise serializers.ValidationError(
                'User authentication required.'
            )
        
        # Add IP address from request
        if 'ip_address' not in validated_data and request:
            validated_data['ip_address'] = request.META.get('REMOTE_ADDR')
        
        device_token = device_service.register_device(
            user=user,
            **validated_data
        )
        
        if not device_token:
            raise serializers.ValidationError(
                'Failed to register device.'
            )
        
        return device_token


class UpdateDeviceSettingsSerializer(serializers.Serializer):
    """
    Serializer for updating device settings
    """
    push_enabled = serializers.BooleanField(required=False)
    sound_enabled = serializers.BooleanField(required=False)
    vibration_enabled = serializers.BooleanField(required=False)
    app_version = serializers.CharField(max_length=20, required=False, allow_blank=True)
    os_version = serializers.CharField(max_length=20, required=False, allow_blank=True)
    device_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    language = serializers.ChoiceField(
        choices=Notification.LANGUAGE_CHOICES,
        required=False
    )
    
    def update(self, instance, validated_data):
        """
        Update device settings using service
        """
        from ._services_core import device_service
        
        device_token = device_service.update_device_settings(
            token=instance.token,
            updates=validated_data
        )
        
        if not device_token:
            raise serializers.ValidationError(
                'Failed to update device settings.'
            )
        
        return device_token


class NotificationCampaignSerializer(BaseSerializer):
    """
    Serializer for NotificationCampaign model
    """
    id = UUIDField(read_only=True)
    target_segment = JSONField(default=dict)
    ab_test_variants = JSONField(default=list)
    
    # Computed fields
    progress_percentage = serializers.SerializerMethodField()
    performance_summary = serializers.SerializerMethodField()
    is_completed = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = NotificationCampaign
        fields = [
            # Basic info
            'id', 'name', 'description', 'campaign_type',
            
            # Target audience
            'target_segment', 'target_count',
            
            # Content
            'title_template', 'message_template',
            
            # Delivery settings
            'channel', 'priority', 'scheduled_for',
            
            # Status
            'status',
            
            # Progress
            'total_sent', 'total_delivered', 'total_failed',
            'total_read', 'total_clicked',
            
            # Performance metrics
            'delivery_rate', 'open_rate', 'click_through_rate', 'conversion_rate',
            
            # Cost
            'total_cost', 'cost_currency',
            
            # A/B Testing
            'ab_test_enabled', 'ab_test_variants',
            
            # Limits
            'send_limit', 'daily_limit',
            
            # Timestamps
            'created_at', 'updated_at', 'started_at', 'completed_at',
            
            # Created by
            'created_by',
            
            # Computed fields
            'progress_percentage', 'performance_summary', 'is_completed',
        ]
        read_only_fields = [
            'id', 'target_count', 'total_sent', 'total_delivered',
            'total_failed', 'total_read', 'total_clicked',
            'delivery_rate', 'open_rate', 'click_through_rate',
            'conversion_rate', 'total_cost', 'created_at', 'updated_at',
            'started_at', 'completed_at', 'created_by',
            'progress_percentage', 'performance_summary', 'is_completed',
        ]
    
    def get_progress_percentage(self, obj):
        return obj.get_progress_percentage()
    
    def get_performance_summary(self, obj):
        return obj.get_performance_summary()


class CreateCampaignSerializer(serializers.Serializer):
    """
    Serializer for creating campaigns
    """
    name = serializers.CharField(max_length=255)
    target_segment = JSONField(default=dict)
    title_template = serializers.CharField()
    message_template = serializers.CharField()
    campaign_type = serializers.ChoiceField(
        choices=[
            ('promotional', 'Promotional'),
            ('transactional', 'Transactional'),
            ('educational', 'Educational'),
            ('alert', 'Alert'),
            ('reminder', 'Reminder'),
            ('welcome', 'Welcome'),
            ('abandoned_cart', 'Abandoned Cart'),
            ('re_engagement', 'Re-engagement'),
            ('birthday', 'Birthday'),
            ('anniversary', 'Anniversary'),
            ('holiday', 'Holiday'),
            ('seasonal', 'Seasonal'),
            ('event', 'Event'),
            ('survey', 'Survey'),
            ('feedback', 'Feedback'),
            ('update', 'Update'),
        ]
    )
    channel = serializers.ChoiceField(
        choices=Notification.CHANNEL_CHOICES,
        default='in_app'
    )
    
    # Optional fields
    description = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(
        choices=Notification.PRIORITY_LEVELS,
        default='medium',
        required=False
    )
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    send_limit = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True
    )
    daily_limit = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True
    )
    ab_test_enabled = serializers.BooleanField(default=False, required=False)
    ab_test_variants = JSONField(default=list, required=False)
    
    def validate_target_segment(self, value):
        """
        Validate target segment
        """
        if not isinstance(value, dict):
            raise serializers.ValidationError("Target segment must be a dictionary.")
        
        # Validate filters structure
        filters = value.get('filters', {})
        if not isinstance(filters, dict):
            raise serializers.ValidationError("Filters must be a dictionary.")
        
        return value
    
    def create(self, validated_data):
        """
        Create campaign using service
        """
        request = self.context.get('request')
        created_by = request.user if request else None
        
        campaign = notification_service.create_campaign(
            created_by=created_by,
            **validated_data
        )
        
        if not campaign:
            raise serializers.ValidationError(
                'Failed to create campaign.'
            )
        
        return campaign


class CampaignActionSerializer(serializers.Serializer):
    """
    Serializer for campaign actions
    """
    action = serializers.ChoiceField(
        choices=['start', 'pause', 'resume', 'cancel', 'process']
    )
    
    def validate(self, data):
        """
        Validate campaign action
        """
        instance = self.instance
        action = data.get('action')
        
        if action == 'start' and instance.status != 'draft':
            raise serializers.ValidationError({
                'action': 'Only draft campaigns can be started.'
            })
        
        if action == 'pause' and instance.status != 'running':
            raise serializers.ValidationError({
                'action': 'Only running campaigns can be paused.'
            })
        
        if action == 'resume' and instance.status != 'paused':
            raise serializers.ValidationError({
                'action': 'Only paused campaigns can be resumed.'
            })
        
        if action == 'cancel' and instance.status in ['completed', 'cancelled', 'failed']:
            raise serializers.ValidationError({
                'action': f'Cannot cancel campaign in {instance.status} status.'
            })
        
        return data
    
    def update(self, instance, validated_data):
        """
        Execute campaign action
        """
        action = validated_data.get('action')
        
        if action == 'start':
            result = notification_service.start_campaign(str(instance.id))
        elif action == 'pause':
            instance.pause()
            result = {'success': True, 'message': 'Campaign paused.'}
        elif action == 'resume':
            instance.resume()
            result = {'success': True, 'message': 'Campaign resumed.'}
        elif action == 'cancel':
            instance.cancel()
            result = {'success': True, 'message': 'Campaign cancelled.'}
        elif action == 'process':
            result = notification_service.process_campaign(str(instance.id))
        else:
            result = {'success': False, 'error': 'Unknown action.'}
        
        if not result.get('success'):
            raise serializers.ValidationError(result.get('error', 'Action failed.'))
        
        return instance


class NotificationRuleSerializer(BaseSerializer):
    """
    Serializer for NotificationRule model
    """
    id = UUIDField(read_only=True)
    trigger_config = JSONField(default=dict)
    conditions = JSONField(default=list)
    action_config = JSONField(default=dict)
    target_config = JSONField(default=dict)
    
    # Computed fields
    can_execute = serializers.BooleanField(read_only=True)

    
    class Meta:
        model = NotificationRule
        fields = [
            # Basic info
            'id', 'name', 'description',
            
            # Trigger
            'trigger_type', 'trigger_config',
            
            # Conditions
            'conditions',
            
            # Action
            'action_type', 'action_config',
            
            # Target
            'target_type', 'target_config',
            
            # Status
            'is_active', 'is_enabled',
            
            # Execution
            'last_triggered', 'trigger_count', 'success_count', 'failure_count',
            
            # Limits
            'max_executions', 'execution_interval',
            
            # Timestamps
            'created_at', 'updated_at',
            
            # Created by
            'created_by',
            
            # Computed fields
            'can_execute',
        ]
        read_only_fields = [
            'id', 'last_triggered', 'trigger_count', 'success_count',
            'failure_count', 'created_at', 'updated_at', 'created_by',
            'can_execute',
        ]


class CreateRuleSerializer(serializers.Serializer):
    """
    Serializer for creating rules
    """
    name = serializers.CharField(max_length=255)
    trigger_type = serializers.ChoiceField(
        choices=[
            ('event', 'Event'),
            ('schedule', 'Schedule'),
            ('condition', 'Condition'),
            ('webhook', 'Webhook'),
        ]
    )
    trigger_config = JSONField(default=dict)
    
    # Optional fields
    description = serializers.CharField(required=False, allow_blank=True)
    conditions = JSONField(default=list, required=False)
    action_type = serializers.ChoiceField(
        choices=[
            ('send_notification', 'Send Notification'),
            ('update_notification', 'Update Notification'),
            ('delete_notification', 'Delete Notification'),
            ('archive_notification', 'Archive Notification'),
            ('send_email', 'Send Email'),
            ('call_webhook', 'Call Webhook'),
        ],
        default='send_notification'
    )
    action_config = JSONField(default=dict, required=False)
    target_type = serializers.ChoiceField(
        choices=[
            ('user', 'Specific User'),
            ('user_group', 'User Group'),
            ('all_users', 'All Users'),
            ('dynamic', 'Dynamic'),
        ],
        default='user'
    )
    target_config = JSONField(default=dict, required=False)
    is_active = serializers.BooleanField(default=True, required=False)
    is_enabled = serializers.BooleanField(default=True, required=False)
    max_executions = serializers.IntegerField(
        min_value=1,
        required=False,
        allow_null=True
    )
    execution_interval = serializers.IntegerField(
        min_value=0,
        default=0,
        required=False
    )
    
    def validate_trigger_config(self, value):
        """
        Validate trigger configuration
        """
        if not isinstance(value, dict):
            raise serializers.ValidationError("Trigger config must be a dictionary.")
        return value
    
    def validate_conditions(self, value):
        """
        Validate conditions
        """
        if not isinstance(value, list):
            raise serializers.ValidationError("Conditions must be a list.")
        
        for condition in value:
            if not isinstance(condition, dict):
                raise serializers.ValidationError("Each condition must be a dictionary.")
            
            if 'field' not in condition or 'type' not in condition:
                raise serializers.ValidationError(
                    "Condition must have 'field' and 'type' fields."
                )
        
        return value
    
    def create(self, validated_data):
        """
        Create rule
        """
        request = self.context.get('request')
        created_by = request.user if request else None
        
        rule = NotificationRule.objects.create(
            created_by=created_by,
            **validated_data
        )
        
        return rule


class RuleActionSerializer(serializers.Serializer):
    """
    Serializer for rule actions
    """
    action = serializers.ChoiceField(
        choices=['execute', 'test', 'enable', 'disable', 'activate', 'deactivate']
    )
    context = JSONField(default=dict, required=False)
    
    def validate(self, data):
        """
        Validate rule action
        """
        instance = self.instance
        action = data.get('action')
        
        if action in ['execute', 'test'] and not instance.is_active:
            raise serializers.ValidationError({
                'action': 'Rule must be active to execute or test.'
            })
        
        return data
    
    def update(self, instance, validated_data):
        """
        Execute rule action
        """
        from ._services_core import rule_service
        
        action = validated_data.get('action')
        context = validated_data.get('context', {})
        
        if action == 'execute':
            result = rule_service.execute_rule(instance, context)
        elif action == 'test':
            result = rule_service.test_rule(instance, context)
        elif action == 'enable':
            instance.is_enabled = True
            instance.save()
            result = {'success': True, 'message': 'Rule enabled.'}
        elif action == 'disable':
            instance.is_enabled = False
            instance.save()
            result = {'success': True, 'message': 'Rule disabled.'}
        elif action == 'activate':
            instance.is_active = True
            instance.save()
            result = {'success': True, 'message': 'Rule activated.'}
        elif action == 'deactivate':
            instance.is_active = False
            instance.save()
            result = {'success': True, 'message': 'Rule deactivated.'}
        else:
            result = {'success': False, 'error': 'Unknown action.'}
        
        if not result.get('success'):
            raise serializers.ValidationError(result.get('error', 'Action failed.'))
        
        return instance


class NotificationFeedbackSerializer(BaseSerializer):
    """
    Serializer for NotificationFeedback model
    """
    id = UUIDField(read_only=True)
    notification = UUIDField(read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    metadata = JSONField(default=dict)
    
    class Meta:
        model = NotificationFeedback
        fields = [
            'id', 'notification', 'user', 'rating', 'feedback',
            'feedback_type', 'is_helpful', 'would_like_more',
            'metadata', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'notification', 'user', 'created_at', 'updated_at',
        ]


class SubmitFeedbackSerializer(serializers.Serializer):
    """
    Serializer for submitting feedback
    """
    notification_id = UUIDField()
    rating = serializers.IntegerField(
        min_value=1,
        max_value=5,
        required=False,
        allow_null=True
    )
    feedback = serializers.CharField(required=False, allow_blank=True)
    feedback_type = serializers.ChoiceField(
        choices=[
            ('positive', 'Positive'),
            ('negative', 'Negative'),
            ('neutral', 'Neutral'),
            ('suggestion', 'Suggestion'),
            ('bug_report', 'Bug Report'),
            ('feature_request', 'Feature Request'),
        ],
        default='neutral'
    )
    is_helpful = serializers.BooleanField(required=False, allow_null=True)
    would_like_more = serializers.BooleanField(required=False, allow_null=True)
    metadata = JSONField(default=dict, required=False)
    
    def validate(self, data):
        """
        Validate feedback data
        """
        request = self.context.get('request')
        user = request.user if request else None
        
        if not user:
            raise serializers.ValidationError(
                'User authentication required.'
            )
        
        # Check if notification exists and belongs to user
        notification_id = data.get('notification_id')
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            data['notification'] = notification
        except Notification.DoesNotExist:
            raise serializers.ValidationError({
                'notification_id': 'Notification not found or does not belong to you.'
            })
        
        return data
    
    def create(self, validated_data):
        """
        Submit feedback using service
        """
        from ._services_core import feedback_service
        
        notification = validated_data.pop('notification')
        user = self.context.get('request').user
        
        feedback = feedback_service.submit_feedback(
            notification_id=str(notification.id),
            user=user,
            **validated_data
        )
        
        if not feedback:
            raise serializers.ValidationError(
                'Failed to submit feedback.'
            )
        
        return feedback


class NotificationAnalyticsSerializer(BaseSerializer):
    """
    Serializer for NotificationAnalytics model
    """
    id = serializers.IntegerField(read_only=True)
    by_type = JSONField(default=dict)
    by_channel = JSONField(default=dict)
    by_priority = JSONField(default=dict)
    
    # Computed fields
    summary = serializers.SerializerMethodField()
    
    class Meta:
        model = NotificationAnalytics
        fields = [
            'id', 'date',
            
            # Counts
            'total_notifications', 'total_sent', 'total_delivered',
            'total_read', 'total_clicked', 'total_failed',
            
            # Rates
            'delivery_rate', 'open_rate', 'click_through_rate',
            
            # Breakdowns
            'by_type', 'by_channel', 'by_priority',
            
            # User engagement
            'active_users', 'engaged_users', 'average_notifications_per_user',
            
            # Cost
            'total_cost', 'average_cost_per_notification',
            
            # Timestamps
            'created_at', 'updated_at',
            
            # Computed fields
            'summary',
        ]
        read_only_fields = [
            'id', 'date', 'total_notifications', 'total_sent', 'total_delivered',
            'total_read', 'total_clicked', 'total_failed', 'delivery_rate',
            'open_rate', 'click_through_rate', 'by_type', 'by_channel',
            'by_priority', 'active_users', 'engaged_users',
            'average_notifications_per_user', 'total_cost',
            'average_cost_per_notification', 'created_at', 'updated_at',
            'summary',
        ]
    
    def get_summary(self, obj):
        return obj.get_summary()


class AnalyticsRequestSerializer(serializers.Serializer):
    """
    Serializer for analytics requests
    """
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    group_by = serializers.ChoiceField(
        choices=['day', 'week', 'month', 'year'],
        default='day',
        required=False
    )
    metrics = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            'total_notifications', 'total_sent', 'total_delivered',
            'total_read', 'total_clicked', 'delivery_rate',
            'open_rate', 'click_through_rate', 'active_users',
            'engaged_users', 'total_cost'
        ]),
        required=False
    )
    
    def validate(self, data):
        """
        Validate analytics request
        """
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({
                'start_date': 'Start date cannot be after end date.',
                'end_date': 'End date cannot be before start date.'
            })
        
        return data


class NotificationLogSerializer(BaseSerializer):
    """
    Serializer for NotificationLog model
    """
    id = UUIDField(read_only=True)
    notification = UUIDField(required=False, allow_null=True)
    # user = serializers.PrimaryKeyRelatedField(required=False, allow_null=True)
    user = serializers.PrimaryKeyRelatedField(
    queryset=User.objects.all(), 
    required=False, 
    allow_null=True
)
    details = JSONField(default=dict)
    
    class Meta:
        model = NotificationLog
        
        fields = [
            'id', 'notification', 'user', 'log_type', 'log_level',
            'message', 'details', 'source', 'ip_address', 'user_agent',
            'created_at',
        ]
        read_only_fields = [
            'id', 'created_at',
        ]


class LogFilterSerializer(serializers.Serializer):
    """
    Serializer for log filtering
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    log_type = serializers.ChoiceField(
        choices=NotificationLog.LOG_TYPES,
        required=False
    )
    log_level = serializers.ChoiceField(
        choices=NotificationLog.LOG_LEVELS,
        required=False
    )
    notification_id = UUIDField(required=False)
    user_id = serializers.IntegerField(required=False)
    source = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    def validate(self, data):
        """
        Validate log filter
        """
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError({
                'start_date': 'Start date cannot be after end date.',
                'end_date': 'End date cannot be before start date.'
            })
        
        return data


class SystemStatusSerializer(serializers.Serializer):
    """
    Serializer for system status
    """
    def to_representation(self, instance):
        """
        Get system status
        """
        from ._services_core import notification_service
        
        status = notification_service.validate_notification_system()
        
        return {
            'timestamp': status['timestamp'],
            'overall_status': status['overall_status'],
            'checks': status['checks']
        }


class TestNotificationSerializer(serializers.Serializer):
    """
    Serializer for test notifications
    """
    channel = serializers.ChoiceField(
        choices=Notification.CHANNEL_CHOICES,
        default='in_app'
    )
    user_id = serializers.IntegerField(required=False)
    
    def validate(self, data):
        """
        Validate test notification request
        """
        request = self.context.get('request')
        
        # Get user
        user_id = data.get('user_id')
        if user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'user_id': 'User not found.'
                })
        else:
            user = request.user if request else None
        
        if not user:
            raise serializers.ValidationError(
                'User is required.'
            )
        
        # Check permissions
        if user != request.user and not request.user.is_staff:
            raise serializers.ValidationError(
                'You do not have permission to send test notifications to other users.'
            )
        
        data['user'] = user
        return data
    
    def create(self, validated_data):
        """
        Send test notification
        """
        user = validated_data['user']
        channel = validated_data['channel']
        
        result = notification_service.send_test_notification(user, channel)
        
        if not result.get('success'):
            raise serializers.ValidationError(result.get('error', 'Test failed.'))
        
        return result


class ExportPreferencesSerializer(serializers.Serializer):
    """
    Serializer for exporting preferences
    """
    format = serializers.ChoiceField(
        choices=['json', 'csv'],
        default='json'
    )
    
    def create(self, validated_data):
        """
        Export preferences
        """
        from ._services_core import preferences_service
        
        request = self.context.get('request')
        user = request.user if request else None
        
        if not user:
            raise serializers.ValidationError(
                'User authentication required.'
            )
        
        export_format = validated_data.get('format')
        
        if export_format == 'json':
            result = preferences_service.export_preferences(user)
        else:
            # CSV export would be implemented here
            result = {
                'success': False,
                'error': 'CSV export not implemented yet.'
            }
        
        if not result.get('success'):
            raise serializers.ValidationError(result.get('error', 'Export failed.'))
        
        return result


class ImportPreferencesSerializer(serializers.Serializer):
    """
    Serializer for importing preferences
    """
    data = JSONField()
    overwrite = serializers.BooleanField(default=False)
    
    def validate_data(self, value):
        """
        Validate import data
        """
        if not isinstance(value, dict):
            raise serializers.ValidationError("Import data must be a dictionary.")
        
        # Check required fields
        if 'preferences' not in value:
            raise serializers.ValidationError(
                "Import data must contain 'preferences' field."
            )
        
        return value
    
    def create(self, validated_data):
        """
        Import preferences
        """
        from ._services_core import preferences_service
        
        request = self.context.get('request')
        user = request.user if request else None
        
        if not user:
            raise serializers.ValidationError(
                'User authentication required.'
            )
        
        data = validated_data['data']['preferences']
        overwrite = validated_data['overwrite']
        
        if overwrite:
            success = preferences_service.import_preferences(user, data)
        else:
            # Merge with existing preferences
            # This would be more complex in real implementation
            success = False
        
        if not success:
            raise serializers.ValidationError(
                'Failed to import preferences.'
            )
        
        return {'success': True, 'message': 'Preferences imported successfully.'}


class MarkAllAsReadSerializer(serializers.Serializer):
    """
    Serializer for marking all notifications as read
    """
    def create(self, validated_data):
        """
        Mark all notifications as read
        """
        request = self.context.get('request')
        user = request.user if request else None
        
        if not user:
            raise serializers.ValidationError(
                'User authentication required.'
            )
        
        result = notification_service.mark_all_as_read(user)
        
        if not result.get('success'):
            raise serializers.ValidationError(result.get('error', 'Operation failed.'))
        
        return result


class BulkDeleteSerializer(serializers.Serializer):
    """
    Serializer for bulk deleting notifications
    """
    notification_ids = serializers.ListField(
        child=UUIDField(),
        min_length=1,
        max_length=100
    )
    
    def create(self, validated_data):
        """
        Bulk delete notifications
        """
        request = self.context.get('request')
        user = request.user if request else None
        
        if not user:
            raise serializers.ValidationError(
                'User authentication required.'
            )
        
        notification_ids = validated_data['notification_ids']
        
        # Soft delete notifications
        deleted_count = 0
        for notification_id in notification_ids:
            try:
                notification = Notification.objects.get(id=notification_id, user=user)
                notification.soft_delete(deleted_by=user)
                deleted_count += 1
            except Notification.DoesNotExist:
                continue
        
        return {
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Deleted {deleted_count} notifications.'
        }


class NotificationStatsSerializer(serializers.Serializer):
    """
    Serializer for notification statistics
    """
    def to_representation(self, instance):
        """
        Get notification statistics
        """
        from ._services_core import notification_service
        
        request = self.context.get('request')
        user = request.user if request else None
        
        if user and not user.is_staff:
            # User-specific stats
            stats = notification_service.get_user_stats(user)
        else:
            # System-wide stats
            stats = notification_service.get_system_stats()
        
        return stats


class UserEngagementSerializer(serializers.Serializer):
    """
    Serializer for user engagement report
    """
    user_id = serializers.IntegerField(required=False)
    
    def validate(self, data):
        """
        Validate user engagement request
        """
        request = self.context.get('request')
        user = request.user if request else None
        
        # Get user
        user_id = data.get('user_id')
        if user_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                target_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    'user_id': 'User not found.'
                })
        else:
            target_user = user
        
        if not target_user:
            raise serializers.ValidationError(
                'User is required.'
            )
        
        # Check permissions
        if target_user != user and not user.is_staff:
            raise serializers.ValidationError(
                'You do not have permission to view other users\' engagement data.'
            )
        
        data['target_user'] = target_user
        return data
    
    def create(self, validated_data):
        """
        Get user engagement report
        """
        from ._services_core import analytics_service
        
        target_user = validated_data['target_user']
        
        report = analytics_service.get_user_engagement_report(str(target_user.id))
        
        if 'error' in report:
            raise serializers.ValidationError(report['error'])
        
        return report


class CampaignPerformanceSerializer(serializers.Serializer):
    """
    Serializer for campaign performance report
    """
    campaign_id = UUIDField()
    
    def validate_campaign_id(self, value):
        """
        Validate campaign ID
        """
        try:
            campaign = NotificationCampaign.objects.get(id=value)
        except NotificationCampaign.DoesNotExist:
            raise serializers.ValidationError('Campaign not found.')
        
        return campaign
    
    def create(self, validated_data):
        """
        Get campaign performance report
        """
        from ._services_core import analytics_service
        
        campaign = validated_data['campaign_id']
        
        report = analytics_service.get_campaign_performance(str(campaign.id))
        
        if 'error' in report:
            raise serializers.ValidationError(report['error'])
        
        return report


class NotificationSummarySerializer(serializers.Serializer):
    """
    Serializer for notification summary
    """
    def to_representation(self, instance):
        """
        Get notification summary
        """
        return instance.to_dict()


class PaginationSerializer(serializers.Serializer):
    """
    Serializer for pagination
    """
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)
    order_by = serializers.CharField(default='-created_at')
    search = serializers.CharField(required=False, allow_blank=True)
    
    def validate_order_by(self, value):
        """
        Validate order_by field
        """
        # Remove any dangerous characters
        import re
        value = re.sub(r'[^a-zA-Z0-9_-]', '', value)
        
        # Check if field is valid
        valid_fields = [
            'created_at', '-created_at', 'updated_at', '-updated_at',
            'priority', '-priority', 'is_read', '-is_read',
            'notification_type', '-notification_type',
        ]
        
        if value not in valid_fields:
            raise serializers.ValidationError(f"Invalid order_by field: {value}")
        
        return value


class FilterSerializer(serializers.Serializer):
    """
    Serializer for filtering
    """
    is_read = serializers.BooleanField(required=False, allow_null=True)
    notification_type = serializers.ChoiceField(
        choices=Notification.NOTIFICATION_TYPES,
        required=False
    )
    priority = serializers.ChoiceField(
        choices=Notification.PRIORITY_LEVELS,
        required=False
    )
    channel = serializers.ChoiceField(
        choices=Notification.CHANNEL_CHOICES,
        required=False
    )
    status = serializers.ChoiceField(
        choices=Notification.STATUS_CHOICES,
        required=False
    )
    is_archived = serializers.BooleanField(required=False, allow_null=True)
    is_pinned = serializers.BooleanField(required=False, allow_null=True)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    include_expired = serializers.BooleanField(default=False, required=False)


# Response serializers for API responses
class SuccessResponseSerializer(serializers.Serializer):
    """
    Serializer for success responses
    """
    success = serializers.BooleanField(default=True)
    message = serializers.CharField()
    data = serializers.DictField(required=False, allow_null=True)


class ErrorResponseSerializer(serializers.Serializer):
    """
    Serializer for error responses
    """
    success = serializers.BooleanField(default=False)
    error = serializers.CharField()
    error_code = serializers.CharField(required=False)
    details = serializers.DictField(required=False, allow_null=True)


class PaginatedResponseSerializer(serializers.Serializer):
    """
    Serializer for paginated responses
    """
    count = serializers.IntegerField()
    next = serializers.URLField(required=False, allow_null=True)
    previous = serializers.URLField(required=False, allow_null=True)
    results = serializers.ListField()


# Utility serializers for specific operations
class NotificationActionSerializer(serializers.Serializer):
    """
    Serializer for notification actions
    """
    action = serializers.ChoiceField(
        choices=['read', 'unread', 'pin', 'unpin', 'archive', 'unarchive', 'delete']
    )
    
    def update(self, instance, validated_data):
        """
        Execute notification action
        """
        action = validated_data.get('action')
        
        if action == 'read':
            instance.mark_as_read()
        elif action == 'unread':
            instance.mark_as_unread()
        elif action == 'pin':
            instance.pin()
        elif action == 'unpin':
            instance.unpin()
        elif action == 'archive':
            instance.archive()
        elif action == 'unarchive':
            instance.unarchive()
        elif action == 'delete':
            instance.soft_delete()
        else:
            raise serializers.ValidationError(f"Unknown action: {action}")
        
        return instance


class BatchActionSerializer(serializers.Serializer):
    """
    Serializer for batch actions
    """
    action = serializers.ChoiceField(
        choices=['mark_read', 'mark_unread', 'pin', 'unpin', 'archive', 'delete']
    )
    notification_ids = serializers.ListField(
        child=UUIDField(),
        min_length=1,
        max_length=100
    )
    
    def create(self, validated_data):
        """
        Execute batch action
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        request = self.context.get('request')
        user = request.user if request else None
        
        if not user:
            raise serializers.ValidationError(
                'User authentication required.'
            )
        
        action = validated_data['action']
        notification_ids = validated_data['notification_ids']
        
        # Get notifications belonging to user
        notifications = Notification.objects.filter(
            id__in=notification_ids,
            user=user,
            is_deleted=False
        )
        
        updated_count = 0
        
        for notification in notifications:
            try:
                if action == 'mark_read':
                    notification.mark_as_read()
                elif action == 'mark_unread':
                    notification.mark_as_unread()
                elif action == 'pin':
                    notification.pin()
                elif action == 'unpin':
                    notification.unpin()
                elif action == 'archive':
                    notification.archive()
                elif action == 'delete':
                    notification.soft_delete(deleted_by=user)
                
                updated_count += 1
            except:
                continue
        
        return {
            'success': True,
            'action': action,
            'updated_count': updated_count,
            'total_count': len(notification_ids)
        }