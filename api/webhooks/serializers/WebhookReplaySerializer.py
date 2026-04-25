"""Webhook Replay Serializer

This module contains the serializer for the WebhookReplay model.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models import WebhookReplay, WebhookReplayBatch, WebhookDeliveryLog
from ..constants import ReplayStatus

User = get_user_model()


class WebhookReplaySerializer(serializers.ModelSerializer):
    """Serializer for WebhookReplay model."""
    
    original_log_endpoint_label = serializers.CharField(source='original_log.endpoint.label', read_only=True)
    original_log_event_type = serializers.CharField(source='original_log.event_type', read_only=True)
    replayed_by_username = serializers.CharField(source='replayed_by.username', read_only=True)
    
    class Meta:
        model = WebhookReplay
        fields = [
            'id',
            'original_log',
            'original_log_endpoint_label',
            'original_log_event_type',
            'replayed_by',
            'replayed_by_username',
            'reason',
            'status',
            'new_log',
            'replayed_at',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'replayed_at',
            'replayed_by', 'new_log'
        ]
    
    def validate_reason(self, value):
        """Validate replay reason."""
        if not value:
            raise serializers.ValidationError("Reason is required for replay.")
        
        if len(value) < 3:
            raise serializers.ValidationError("Reason must be at least 3 characters long.")
        
        return value
    
    def validate_status(self, value):
        """Validate replay status."""
        valid_statuses = [status.value for status in ReplayStatus]
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Status must be one of: {valid_statuses}")
        return value


class WebhookReplayCreateSerializer(WebhookReplaySerializer):
    """Serializer for creating webhook replays."""
    
    original_log_id = serializers.UUIDField(write_only=True)
    replayed_by_id = serializers.UUIDField(write_only=True, required=False)
    
    class Meta(WebhookReplaySerializer.Meta):
        fields = [
            'original_log_id',
            'replayed_by_id',
            'reason'
        ]
    
    def validate_original_log_id(self, value):
        """Validate original log ID."""
        if not value:
            raise serializers.ValidationError("Original log ID is required.")
        
        try:
            WebhookDeliveryLog.objects.get(id=value)
        except WebhookDeliveryLog.DoesNotExist:
            raise serializers.ValidationError("Original log not found.")
        
        return value
    
    def validate_replayed_by_id(self, value):
        """Validate replayed by ID."""
        if value is None:
            return value
        
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        
        return value
    
    def create(self, validated_data):
        """Create replay instance."""
        original_log_id = validated_data.pop('original_log_id')
        replayed_by_id = validated_data.pop('replayed_by_id', None)
        
        original_log = WebhookDeliveryLog.objects.get(id=original_log_id)
        replayed_by = User.objects.get(id=replayed_by_id) if replayed_by_id else None
        
        return WebhookReplay.objects.create(
            original_log=original_log,
            replayed_by=replayed_by,
            **validated_data
        )


class WebhookReplayUpdateSerializer(WebhookReplaySerializer):
    """Serializer for updating webhook replays."""
    
    class Meta(WebhookReplaySerializer.Meta):
        fields = [
            'reason',
            'status',
            'new_log',
            'replayed_at',
            'updated_at'
        ]
        read_only_fields = ['updated_at']


class WebhookReplayDetailSerializer(WebhookReplaySerializer):
    """Detailed serializer for webhook replays."""
    
    original_log = serializers.PrimaryKeyRelatedField(queryset=WebhookDeliveryLog.objects.all())
    new_log = serializers.PrimaryKeyRelatedField(queryset=WebhookDeliveryLog.objects.all(), required=False, allow_null=True)
    replayed_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    
    class Meta(WebhookReplaySerializer.Meta):
        fields = WebhookReplaySerializer.Meta.fields


class WebhookReplayListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing webhook replays."""
    
    original_log_endpoint_label = serializers.CharField(source='original_log.endpoint.label', read_only=True)
    original_log_event_type = serializers.CharField(source='original_log.event_type', read_only=True)
    replayed_by_username = serializers.CharField(source='replayed_by.username', read_only=True)
    
    class Meta:
        model = WebhookReplay
        fields = [
            'id',
            'original_log_endpoint_label',
            'original_log_event_type',
            'replayed_by_username',
            'reason',
            'status',
            'replayed_at',
            'created_at'
        ]


class WebhookReplayBatchSerializer(serializers.ModelSerializer):
    """Serializer for WebhookReplayBatch model."""
    
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = WebhookReplayBatch
        fields = [
            'id',
            'batch_id',
            'event_type',
            'reason',
            'count',
            'status',
            'date_from',
            'date_to',
            'endpoint_filter',
            'status_filter',
            'completed_at',
            'created_by',
            'created_by_username',
            'created_at',
            'updated_at'
        ]
        read_only_fields = [
            'id', 'batch_id', 'created_at', 'updated_at',
            'created_by', 'completed_at'
        ]
    
    def validate_reason(self, value):
        """Validate batch reason."""
        if not value:
            raise serializers.ValidationError("Reason is required for replay batch.")
        
        if len(value) < 3:
            raise serializers.ValidationError("Reason must be at least 3 characters long.")
        
        return value
    
    def validate_status(self, value):
        """Validate batch status."""
        valid_statuses = [status.value for status in ReplayStatus]
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Status must be one of: {valid_statuses}")
        return value
    
    def validate_date_from(self, value):
        """Validate date from."""
        if value is None:
            return value
        
        if self.instance and self.instance.date_to and value > self.instance.date_to:
            raise serializers.ValidationError("Date from must be before date to.")
        
        return value
    
    def validate_date_to(self, value):
        """Validate date to."""
        if value is None:
            return value
        
        if self.instance and self.instance.date_from and value < self.instance.date_from:
            raise serializers.ValidationError("Date to must be after date from.")
        
        return value


class WebhookReplayBatchCreateSerializer(WebhookReplayBatchSerializer):
    """Serializer for creating webhook replay batches."""
    
    delivery_log_ids = serializers.ListField(child=serializers.UUIDField(), write_only=True)
    created_by_id = serializers.UUIDField(write_only=True, required=False)
    
    class Meta(WebhookReplayBatchSerializer.Meta):
        fields = [
            'delivery_log_ids',
            'created_by_id',
            'event_type',
            'reason'
        ]
    
    def validate_delivery_log_ids(self, value):
        """Validate delivery log IDs."""
        if not value:
            raise serializers.ValidationError("Delivery log IDs are required.")
        
        if len(value) > 1000:
            raise serializers.ValidationError("Cannot create batch with more than 1000 logs.")
        
        return value
    
    def validate_created_by_id(self, value):
        """Validate created by ID."""
        if value is None:
            return value
        
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        
        return value


class WebhookReplayBatchDetailSerializer(WebhookReplayBatchSerializer):
    """Detailed serializer for webhook replay batches."""
    
    created_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    
    class Meta(WebhookReplayBatchSerializer.Meta):
        fields = WebhookReplayBatchSerializer.Meta.fields


class WebhookReplayBatchListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing webhook replay batches."""
    
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = WebhookReplayBatch
        fields = [
            'id',
            'batch_id',
            'event_type',
            'count',
            'status',
            'created_by_username',
            'created_at'
        ]


class WebhookReplayProcessSerializer(serializers.Serializer):
    """Serializer for processing webhook replays."""
    
    force_process = serializers.BooleanField(default=False, write_only=True)
    
    def validate_force_process(self, value):
        """Validate force process option."""
        return value


class WebhookReplayStatsSerializer(serializers.Serializer):
    """Serializer for webhook replay statistics."""
    
    total_replays = serializers.IntegerField(read_only=True)
    pending_replays = serializers.IntegerField(read_only=True)
    processing_replays = serializers.IntegerField(read_only=True)
    completed_replays = serializers.IntegerField(read_only=True)
    failed_replays = serializers.IntegerField(read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    avg_processing_time = serializers.FloatField(read_only=True)
    
    class Meta:
        fields = [
            'total_replays',
            'pending_replays',
            'processing_replays',
            'completed_replays',
            'failed_replays',
            'success_rate',
            'avg_processing_time'
        ]


class WebhookReplayFilterSerializer(serializers.Serializer):
    """Serializer for filtering webhook replays."""
    
    status = serializers.CharField(required=False)
    reason = serializers.CharField(required=False)
    created_by_id = serializers.UUIDField(required=False)
    created_at_from = serializers.DateTimeField(required=False)
    created_at_to = serializers.DateTimeField(required=False)
    
    def validate_status(self, value):
        """Validate status filter."""
        if value is None:
            return value
        
        valid_statuses = [status.value for status in ReplayStatus]
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Status must be one of: {valid_statuses}")
        return value
    
    def validate_created_by_id(self, value):
        """Validate created by ID."""
        return value
    
    def validate_created_at_from(self, value):
        """Validate created_at_from filter."""
        return value
    
    def validate_created_at_to(self, value):
        """Validate created_at_to filter."""
        return value


class WebhookReplayBatchProcessSerializer(serializers.Serializer):
    """Serializer for processing webhook replay batches."""
    
    force_process = serializers.BooleanField(default=False, write_only=True)
    
    def validate_force_process(self, value):
        """Validate force process option."""
        return value


class WebhookReplayRecommendationSerializer(serializers.Serializer):
    """Serializer for webhook replay recommendations."""
    
    original_log_id = serializers.UUIDField(read_only=True)
    event_type = serializers.CharField(read_only=True)
    failure_reason = serializers.CharField(read_only=True)
    recommendation = serializers.CharField(read_only=True)
    confidence = serializers.FloatField(read_only=True)
    
    class Meta:
        fields = [
            'original_log_id',
            'event_type',
            'failure_reason',
            'recommendation',
            'confidence'
        ]
