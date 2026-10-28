# api/djoyalty/serializers/OfferWallSerializer.py
from rest_framework import serializers
from ..models.offerwall import OfferWall, Offer, OfferCompletion, ContentLock, ContentUnlock


class OfferWallSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferWall
        fields = [
            'id', 'name', 'description', 'currency_name', 'currency_ratio',
            'header_title', 'header_image', 'primary_color', 'provider',
            'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class OfferSerializer(serializers.ModelSerializer):
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = [
            'id', 'external_offer_id', 'title', 'description', 'short_description',
            'image_url', 'advertiser_name', 'offer_type', 'points_reward',
            'advertiser_payout', 'requirements', 'estimated_time_minutes',
            'difficulty', 'geo_targets', 'device_targets', 'max_completions_per_user',
            'status', 'valid_from', 'valid_until', 'is_featured', 'sort_order',
            'offer_url', 'is_available',
        ]
        read_only_fields = ['id', 'is_available']

    def get_is_available(self, obj):
        return obj.status == 'active'


class OfferCompletionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferCompletion
        fields = [
            'id', 'offer', 'status', 'points_awarded',
            'advertiser_payout_received', 'completed_at',
        ]
        read_only_fields = ['id', 'completed_at']


class ContentLockSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentLock
        fields = [
            'id', 'title', 'description', 'content_type',
            'unlock_method', 'required_points', 'unlock_duration_hours',
            'thumbnail', 'is_active',
        ]
        read_only_fields = ['id']


class ContentUnlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentUnlock
        fields = ['id', 'content_lock', 'points_spent', 'unlocked_at', 'expires_at', 'is_active']
        read_only_fields = ['id', 'unlocked_at']

    def validate_points_reward(self, value):
        from decimal import Decimal
        if Decimal(str(value)) < 0:
            from rest_framework import serializers
            raise serializers.ValidationError('Points reward cannot be negative.')
        return value
