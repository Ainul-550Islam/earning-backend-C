# api/cms/serializers_new/RealTimeOfferSerializer.py
"""
Serializers for RealTimeOffer, ContentSchedule, and VideoGenerationRequest Models
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models_new.realtime_offers import RealTimeOfferUpdate, UserOfferSubscription, OfferUpdateQueue
from ..models_new.site_config import ContentSchedule
from ..models_new.video import VideoContent, VideoGenerationRequest

User = get_user_model()


# ── Real-Time Offers ───────────────────────────────────────────────────────────

class RealTimeOfferUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RealTimeOfferUpdate
        fields = [
            'uuid', 'offer_id', 'update_type', 'old_data', 'new_data',
            'countries', 'devices', 'min_age',
        ]
        read_only_fields = ['uuid']


class UserOfferSubscriptionSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = UserOfferSubscription
        fields = [
            'id', 'user', 'user_display', 'is_active',
            'subscribe_new_offers', 'subscribe_updated_offers',
            'subscribe_expired_offers', 'subscribe_payout_changes',
            'min_payout', 'max_payout',
        ]
        read_only_fields = ['id']

    def validate(self, data):
        min_p = data.get('min_payout', 0)
        max_p = data.get('max_payout')
        if max_p is not None and min_p > max_p:
            raise serializers.ValidationError(
                {"max_payout": "max_payout must be greater than or equal to min_payout."}
            )
        return data


class OfferUpdateQueueSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferUpdateQueue
        fields = [
            'uuid', 'batch_data', 'status', 'created_at', 'processed_at', 'error_message',
        ]
        read_only_fields = ['uuid', 'created_at', 'processed_at']


# ── ContentSchedule ───────────────────────────────────────────────────────────

class ContentScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentSchedule
        fields = [
            'uuid', 'title', 'content_type', 'content_id', 'status',
            'scheduled_at', 'published_at', 'expires_at',
        ]
        read_only_fields = ['uuid', 'published_at']

    def validate(self, data):
        if data.get('scheduled_at') and data.get('expires_at'):
            if data['scheduled_at'] >= data['expires_at']:
                raise serializers.ValidationError(
                    {"expires_at": "expires_at must be after scheduled_at."}
                )
        return data


# ── Video ─────────────────────────────────────────────────────────────────────

class VideoGenerationRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoGenerationRequest
        fields = [
            'id', 'video', 'status', 'request_data', 'response_data',
            'error_message', 'started_at', 'completed_at', 'created_at',
        ]
        read_only_fields = ['id', 'response_data', 'started_at', 'completed_at', 'created_at']
