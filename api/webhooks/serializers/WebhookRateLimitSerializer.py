# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Serializer for WebhookReplayItem.

BUG FIX: this file previously also defined WebhookRateLimitSerializer and
WebhookRetryAnalysisSerializer with a field list (total_sent, success_count,
failed_count, avg_latency_ms, date, ...) that matches neither
WebhookRateLimit nor WebhookRetryAnalysis's real fields — every list/detail
call on WebhookRateLimitViewSet or the retry-analysis viewset would have
raised a FieldError/AssertionError the first time DRF tried to build the
serializer. Correct versions already existed in WebhookAnalyticsSerializer.py
(matching the real models) — WebhookRateLimitViewSet.py now imports from
there instead, so the mismatched duplicates here were removed rather than
fixed twice.
"""
from rest_framework import serializers
from ..models.replay import WebhookReplayItem


class WebhookReplayItemSerializer(serializers.ModelSerializer):
    """
    BUG FIX: previously referenced `replayed_by`/`reason`, fields that
    live on WebhookReplay/WebhookReplayBatch, not on WebhookReplayItem
    itself — every call to WebhookReplayViewSet's items()/my_items()
    actions crashed building this serializer (a FieldError from the
    nonexistent Meta.fields entries, and items() additionally crashed
    earlier still, at its own select_related('...', 'replayed_by') call).
    """
    original_log_id = serializers.UUIDField(source='original_log.id', read_only=True)
    new_log_id      = serializers.UUIDField(source='new_log.id', read_only=True, allow_null=True)

    class Meta:
        model  = WebhookReplayItem
        fields = [
            'id', 'batch', 'original_log_id', 'new_log_id',
            'status', 'created_at', 'updated_at',
        ]
        read_only_fields = fields
