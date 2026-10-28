from rest_framework import serializers
from .models import (
    OfferProvider, OfferCategory, Offer, OfferClick,
    OfferConversion, OfferWall
)
from decimal import Decimal


class OfferProviderSerializer(serializers.ModelSerializer):
    """Serializer for OfferProvider model"""

    provider_type_display = serializers.CharField(source='get_provider_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_active_status = serializers.BooleanField(source='is_active', read_only=True)

    class Meta:
        model = OfferProvider
        fields = [
            'id', 'name', 'provider_type', 'provider_type_display',
            'status', 'status_display', 'is_active_status',
            'revenue_share', 'total_offers', 'total_conversions',
            'total_revenue', 'auto_sync', 'last_sync',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_offers', 'total_conversions', 'total_revenue',
            'last_sync', 'created_at', 'updated_at'
        ]


class OfferProviderDetailSerializer(OfferProviderSerializer):
    """Detailed serializer for OfferProvider — used by admin retrieve"""

    class Meta(OfferProviderSerializer.Meta):
        fields = OfferProviderSerializer.Meta.fields + [
            'api_key', 'api_secret', 'app_id', 'publisher_id',
            'api_base_url', 'webhook_url', 'postback_url',
            # FIX: secret_key and ip_whitelist were missing — both exist in models.py
            'secret_key', 'ip_whitelist',
            'rate_limit_per_minute', 'rate_limit_per_hour',
            'sync_interval_minutes', 'config', 'notes'
        ]


class OfferCategorySerializer(serializers.ModelSerializer):
    """Serializer for OfferCategory model"""

    class Meta:
        model = OfferCategory
        fields = [
            'id', 'name', 'slug', 'description', 'icon', 'color',
            'display_order', 'is_featured', 'is_active',
            'offer_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'offer_count', 'created_at', 'updated_at']


class OfferListSerializer(serializers.ModelSerializer):
    """Serializer for Offer list view"""

    provider_name = serializers.CharField(source='provider.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    offer_type_display = serializers.CharField(source='get_offer_type_display', read_only=True)
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = [
            'id', 'title', 'short_description', 'image_url', 'thumbnail_url',
            'icon_url', 'provider_name', 'category_name', 'offer_type',
            'offer_type_display', 'platform', 'platform_display',
            'reward_amount', 'reward_currency', 'bonus_amount',
            'difficulty', 'difficulty_display', 'estimated_time_minutes',
            'is_featured', 'is_trending', 'is_recommended',
            'quality_score', 'completion_rate', 'is_available',
            'created_at'
        ]

    def get_is_available(self, obj):
        """Check if offer is available for current user"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.is_available_for_user(request.user)
        return obj.is_active()


class OfferDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Offer"""

    provider = OfferProviderSerializer(read_only=True)
    category = OfferCategorySerializer(read_only=True)
    offer_type_display = serializers.CharField(source='get_offer_type_display', read_only=True)
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_available = serializers.SerializerMethodField()
    user_completion_count = serializers.SerializerMethodField()
    can_complete = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = [
            'id', 'provider', 'external_offer_id', 'title', 'description',
            'short_description', 'category', 'offer_type', 'offer_type_display',
            'tags', 'platform', 'platform_display', 'countries',
            'image_url', 'thumbnail_url', 'icon_url', 'video_url',
            'click_url',
            # FIX: tracking_url was missing — it exists in models.py
            'tracking_url',
            'preview_url', 'payout', 'currency',
            'reward_amount', 'reward_currency', 'bonus_amount', 'bonus_condition',
            'difficulty', 'difficulty_display', 'estimated_time_minutes',
            'min_age', 'requires_signup', 'requires_card', 'requires_purchase',
            'instructions', 'steps', 'requirements_text',
            'daily_cap', 'total_cap', 'user_limit', 'status', 'status_display',
            'is_featured', 'is_trending', 'is_recommended',
            'start_date', 'end_date', 'view_count', 'click_count',
            'conversion_count', 'completion_rate', 'quality_score',
            'fraud_score', 'is_high_risk',
            'is_available', 'user_completion_count', 'can_complete',
            'created_at', 'updated_at'
        ]

    def get_is_available(self, obj):
        """Check if offer is available"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.is_available_for_user(request.user)
        return obj.is_active()

    def get_user_completion_count(self, obj):
        """Get user's completion count for this offer"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return OfferConversion.objects.filter(
                user=request.user,
                offer=obj,
                status__in=['approved', 'pending']
            ).count()
        return 0

    def get_can_complete(self, obj):
        """Check if user can complete this offer"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            completion_count = self.get_user_completion_count(obj)
            return completion_count < obj.user_limit or obj.user_limit == 0
        return False


class OfferClickSerializer(serializers.ModelSerializer):
    """Serializer for OfferClick model"""

    offer_title = serializers.CharField(source='offer.title', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = OfferClick
        fields = [
            'id', 'offer', 'offer_title', 'user', 'user_name',
            'click_id', 'ip_address', 'user_agent', 'device_type',
            'device_model', 'os', 'os_version', 'browser',
            'country', 'city', 'referrer_url', 'session_id',
            'is_converted', 'converted_at', 'clicked_at'
        ]
        read_only_fields = [
            'id', 'click_id', 'is_converted', 'converted_at', 'clicked_at'
        ]


class OfferConversionSerializer(serializers.ModelSerializer):
    """Serializer for OfferConversion model"""

    offer_title = serializers.CharField(source='offer.title', read_only=True)
    offer_image = serializers.URLField(source='offer.thumbnail_url', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = OfferConversion
        fields = [
            'id', 'offer', 'offer_title', 'offer_image', 'user', 'user_name',
            'conversion_id', 'external_WalletTransaction_id', 'payout_amount',
            'payout_currency', 'reward_amount', 'reward_currency',
            'bonus_amount', 'status', 'status_display', 'is_verified',
            'verified_at', 'transaction', 'notes', 'rejection_reason',
            'converted_at', 'approved_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'conversion_id', 'is_verified', 'verified_at',
            'transaction', 'converted_at', 'approved_at', 'updated_at'
        ]


class OfferConversionDetailSerializer(OfferConversionSerializer):
    """Detailed serializer for OfferConversion"""

    offer = OfferListSerializer(read_only=True)
    click = OfferClickSerializer(read_only=True)

    class Meta(OfferConversionSerializer.Meta):
        fields = OfferConversionSerializer.Meta.fields + [
            'click', 'provider_data', 'postback_data'
        ]


class OfferWallSerializer(serializers.ModelSerializer):
    """Serializer for OfferWall model"""

    categories_data = OfferCategorySerializer(source='categories', many=True, read_only=True)
    providers_data = OfferProviderSerializer(source='providers', many=True, read_only=True)
    offer_count = serializers.SerializerMethodField()

    class Meta:
        model = OfferWall
        fields = [
            'id', 'name', 'slug', 'description', 'title', 'subtitle',
            'banner_image', 'categories_data', 'providers_data',
            'offer_types', 'platforms', 'countries', 'min_payout',
            'offers_per_page', 'sort_by', 'is_active', 'offer_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'offer_count', 'created_at', 'updated_at']

    def get_offer_count(self, obj):
        """Get total offer count for this wall"""
        return obj.get_offers().count()


class OfferClickCreateSerializer(serializers.Serializer):
    """Serializer for creating offer click"""

    offer_id = serializers.UUIDField()
    device_type = serializers.CharField(max_length=50, required=False)
    device_model = serializers.CharField(max_length=100, required=False)
    os = serializers.CharField(max_length=50, required=False)
    os_version = serializers.CharField(max_length=50, required=False)
    browser = serializers.CharField(max_length=50, required=False)
    referrer_url = serializers.URLField(required=False)
    session_id = serializers.CharField(max_length=255, required=False)
    tracking_params = serializers.JSONField(required=False)


class OfferConversionWebhookSerializer(serializers.Serializer):
    """Serializer for offer conversion webhook"""

    offer_id = serializers.CharField()
    user_id = serializers.CharField()
    transaction_id = serializers.CharField()
    payout = serializers.DecimalField(max_digits=12, decimal_places=6)
    currency = serializers.CharField(max_length=3)
    status = serializers.CharField(required=False, default='pending')
    timestamp = serializers.CharField(required=False)
    signature = serializers.CharField(required=False)

    def validate_payout(self, value):
        """Validate payout amount"""
        if value <= Decimal('0'):
            raise serializers.ValidationError("Payout must be greater than 0")
        return value

    def validate_status(self, value):
        """Validate status"""
        valid_statuses = ['pending', 'approved', 'rejected', 'chargeback']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        return value


class OfferStatsSerializer(serializers.Serializer):
    """Serializer for offer statistics"""

    total_offers             = serializers.IntegerField(default=0)
    active_offers            = serializers.IntegerField(default=0)
    featured_offers          = serializers.IntegerField(default=0)
    total_views              = serializers.IntegerField(default=0)
    total_clicks             = serializers.IntegerField(default=0)
    total_conversions        = serializers.IntegerField(default=0)
    total_revenue            = serializers.DecimalField(
                                   max_digits=15, decimal_places=2, default=0)
    total_payout             = serializers.DecimalField(
                                   max_digits=15, decimal_places=2, default=0)
    average_completion_rate  = serializers.FloatField(default=0.0)
    average_quality_score    = serializers.FloatField(default=0.0)


class UserOfferStatsSerializer(serializers.Serializer):
    """Serializer for user offer statistics"""

    total_completions = serializers.IntegerField()
    pending_conversions = serializers.IntegerField()
    approved_conversions = serializers.IntegerField()
    rejected_conversions = serializers.IntegerField()
    total_earned = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    favorite_category = serializers.CharField()
    most_completed_offer_type = serializers.CharField()


class OfferSearchSerializer(serializers.Serializer):
    """Serializer for offer search parameters"""
    query      = serializers.CharField(required=False)
    category   = serializers.CharField(required=False)  # integer pk as string
    min_payout = serializers.DecimalField(max_digits=12, decimal_places=6, required=False)
    max_payout = serializers.DecimalField(max_digits=12, decimal_places=6, required=False)
    offer_type = serializers.CharField(required=False)
    platform   = serializers.CharField(required=False)
    difficulty = serializers.CharField(required=False)
    is_featured = serializers.BooleanField(required=False)
    is_trending = serializers.BooleanField(required=False)
    sort_by     = serializers.CharField(required=False, default='quality_score')
    page        = serializers.IntegerField(required=False, default=1)
    page_size   = serializers.IntegerField(required=False, default=20)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — MISSING SERIALIZERS
# ─────────────────────────────────────────────────────────────────────────────

class OfferBulkImportSerializer(serializers.Serializer):
    """
    Validate bulk offer import payload.
    Accepts a list of offers with minimum required fields.
    Used by admin/provider import endpoints.
    """

    class OfferImportItemSerializer(serializers.Serializer):
        external_offer_id = serializers.CharField(max_length=255)
        title             = serializers.CharField(max_length=500)
        description       = serializers.CharField(required=False, allow_blank=True)
        offer_type        = serializers.CharField(max_length=50, default='other')
        platform          = serializers.CharField(max_length=20, default='all')
        payout            = serializers.DecimalField(max_digits=12, decimal_places=6)
        reward_amount     = serializers.DecimalField(max_digits=12, decimal_places=6,
                                                     required=False)
        click_url         = serializers.URLField()
        status            = serializers.CharField(max_length=20, default='active')

        def validate_payout(self, value):
            if value < Decimal('0'):
                raise serializers.ValidationError('Payout must be >= 0')
            return value

    provider_id = serializers.UUIDField()
    offers      = OfferImportItemSerializer(many=True)
    overwrite   = serializers.BooleanField(default=False,
                      help_text='If True, overwrite existing offers with same external_offer_id')

    def validate_offers(self, value):
        if not value:
            raise serializers.ValidationError('offers list cannot be empty')
        if len(value) > 1000:
            raise serializers.ValidationError('Cannot import more than 1000 offers at once')
        return value


class ProviderSyncSerializer(serializers.Serializer):
    """
    Validate a provider sync request.
    Used by OfferProviderViewSet.sync action.
    """
    force         = serializers.BooleanField(default=False,
                        help_text='Force sync even if recently synced')
    country       = serializers.CharField(max_length=2, required=False,
                        help_text='ISO 3166-1 alpha-2 country code, e.g. US')
    platform      = serializers.ChoiceField(
                        choices=['android', 'ios', 'web', 'all'],
                        default='all')
    max_offers    = serializers.IntegerField(min_value=1, max_value=10000, default=500)

    def validate_country(self, value):
        if value and len(value) != 2:
            raise serializers.ValidationError('Country must be a 2-letter ISO code')
        return value.upper() if value else value


class ConversionBatchApprovalSerializer(serializers.Serializer):
    """
    Validate bulk conversion approval / rejection requests.
    Used by bulk_approve / bulk_reject admin actions.
    """
    conversion_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=500,
        help_text='List of conversion UUIDs to approve/reject'
    )
    action         = serializers.ChoiceField(choices=['approve', 'reject'])
    reason         = serializers.CharField(max_length=500, required=False, allow_blank=True,
                         help_text='Reason for rejection (required when action=reject)')

    def validate(self, data):
        if data.get('action') == 'reject' and not data.get('reason'):
            raise serializers.ValidationError(
                {'reason': 'Rejection reason is required when action is reject'})
        return data


class ExportRequestSerializer(serializers.Serializer):
    """
    Validate data export requests.
    Used by ExportViewSet or EarningsExportView.
    """
    FORMAT_CHOICES = [('csv', 'CSV'), ('json', 'JSON'), ('xlsx', 'Excel')]

    format       = serializers.ChoiceField(choices=FORMAT_CHOICES, default='csv')
    date_from    = serializers.DateField(required=False)
    date_to      = serializers.DateField(required=False)
    status       = serializers.ChoiceField(
                       choices=['all', 'approved', 'pending', 'rejected'],
                       default='all')
    provider_id  = serializers.UUIDField(required=False)
    include_pii  = serializers.BooleanField(default=False,
                       help_text='Include user email / username in export')

    def validate(self, data):
        date_from = data.get('date_from')
        date_to   = data.get('date_to')
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                {'date_to': 'date_to must be after date_from'})
        return data


class WebhookPayloadSerializer(serializers.Serializer):
    """
    Generic webhook payload validator.
    Used for any inbound postback to verify basic fields.
    """
    provider_type = serializers.CharField(max_length=50)
    conversion_id = serializers.CharField(max_length=255)
    user_id       = serializers.CharField(max_length=255)
    offer_id      = serializers.CharField(max_length=255)
    payout        = serializers.DecimalField(max_digits=12, decimal_places=6)
    status        = serializers.ChoiceField(
                        choices=['pending', 'approved', 'rejected', 'chargeback'],
                        default='pending')
    signature     = serializers.CharField(max_length=512, required=False, allow_blank=True)
    timestamp     = serializers.CharField(max_length=50,  required=False, allow_blank=True)

    def validate_payout(self, value):
        if value < Decimal('0'):
            raise serializers.ValidationError('Payout must be non-negative')
        return value
