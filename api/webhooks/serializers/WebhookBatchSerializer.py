"""Webhook Batch Serializer

This serializer handles webhook batch CRUD operations.

FIX APPLIED:
- Added WebhookBatchCreateSerializer (for POST)
- Added WebhookBatchUpdateSerializer (for PATCH/PUT)
- Added WebhookBatchDetailSerializer (for GET single)
- Added WebhookBatchListSerializer (for GET list)
- BUG FIX (session 5): endpoint_name used source='endpoint.name' —
  WebhookEndpoint has no 'name' field (it's 'label') — crashed
  serializing any real endpoint. Fixed in all 3 places below.
- BUG FIX (session 5): item_count checked
  hasattr(obj, 'webhook_batch_items') — the real related_name is
  'items' — always silently returned 0 regardless of actual item count.
- Added event_type/created_by/priority/metadata/started_at/error_message
  fields, matching this session's WebhookBatch/WebhookBatchItem schema
  additions (see migrations/0018_batch_dispatch_consolidation.py).
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from ..models import WebhookBatch, WebhookBatchItem


class WebhookBatchSerializer(serializers.ModelSerializer):
    """Base serializer for webhook batch CRUD operations."""
    
    endpoint_name = serializers.CharField(source='endpoint.label', read_only=True)
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = WebhookBatch
        fields = [
            'id', 'batch_id', 'endpoint', 'endpoint_name', 'event_type',
            'event_count', 'status', 'priority', 'item_count', 'created_by',
            'created_at', 'started_at', 'completed_at',
        ]
        read_only_fields = ['id', 'batch_id', 'created_by', 'created_at']
    
    def get_item_count(self, obj):
        """Get count of items in batch."""
        return obj.items.count()


class WebhookBatchCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating webhook batches (POST)."""
    
    class Meta:
        model = WebhookBatch
        fields = [
            'id', 'endpoint', 'event_type', 'event_count', 'status', 'priority', 'metadata',
        ]
        read_only_fields = ['id']
    
    def validate_event_count(self, value):
        """Validate event count."""
        if value < 1:
            raise serializers.ValidationError(_('Event count must be at least 1'))
        if value > 10000:
            raise serializers.ValidationError(_('Event count cannot exceed 10000'))
        return value


class WebhookBatchUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating webhook batches (PATCH/PUT)."""
    
    class Meta:
        model = WebhookBatch
        fields = [
            'event_count', 'status', 'priority', 'metadata',
        ]
    
    def validate_event_count(self, value):
        """Validate event count."""
        if value < 1:
            raise serializers.ValidationError(_('Event count must be at least 1'))
        if value > 10000:
            raise serializers.ValidationError(_('Event count cannot exceed 10000'))
        return value


class WebhookBatchDetailSerializer(serializers.ModelSerializer):
    """Serializer for retrieving single webhook batch details (GET)."""
    
    endpoint_name = serializers.CharField(source='endpoint.label', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = WebhookBatch
        fields = [
            'id', 'batch_id', 'endpoint', 'endpoint_name', 'event_type',
            'event_count', 'status', 'status_display', 'priority', 'metadata',
            'item_count', 'created_by', 'created_at', 'started_at',
            'completed_at', 'error_message',
        ]
        read_only_fields = ['id', 'batch_id', 'endpoint', 'created_by', 'created_at', 'completed_at']
    
    def get_item_count(self, obj):
        """Get count of items in batch."""
        return obj.items.count()


class WebhookBatchListSerializer(serializers.ModelSerializer):
    """Serializer for listing webhook batches (GET list)."""
    
    endpoint_name = serializers.CharField(source='endpoint.label', read_only=True)
    item_count = serializers.SerializerMethodField()
    
    class Meta:
        model = WebhookBatch
        fields = [
            'id', 'batch_id', 'endpoint', 'endpoint_name', 'event_type',
            'event_count', 'status', 'priority', 'item_count', 'created_at',
        ]
        read_only_fields = ['id', 'batch_id', 'endpoint', 'created_at']
    
    def get_item_count(self, obj):
        """Get count of items in batch."""
        return obj.items.count()


class WebhookBatchItemSerializer(serializers.ModelSerializer):
    """Serializer for webhook batch item CRUD operations."""
    
    class Meta:
        model = WebhookBatchItem
        fields = [
            'id', 'batch', 'delivery_log', 'position', 'status',
            'sequence_number', 'started_at', 'completed_at',
            'error_message', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']
