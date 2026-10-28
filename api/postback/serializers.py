"""serializers.py – DRF serializers for the postback module."""
from rest_framework import serializers
from .models import (
    DuplicateLeadCheck, LeadValidator, NetworkPostbackConfig, PostbackLog,
    PostbackInsight, PostbackTemplate, PostbackIPWhitelist, PostbackRateLimit
)
from .choices import ValidatorStatus
from .validators import validate_ip_whitelist, validate_field_mapping, validate_reward_rules


class NetworkPostbackConfigListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    network_type_display = serializers.CharField(source="get_network_type_display", read_only=True)

    class Meta:
        model = NetworkPostbackConfig
        fields = [
            "id", "name", "network_key", "network_type", "network_type_display",
            "status", "status_display", "dedup_window",
            "ip_whitelist", "reward_rules", "rate_limit_per_minute",
            "signature_algorithm", "trust_forwarded_for", "require_nonce",
            "default_reward_points", "contact_email", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class NetworkPostbackConfigDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkPostbackConfig
        fields = [
            "id", "name", "network_key", "network_type", "status",
            "secret_key", "signature_algorithm", "ip_whitelist",
            "trust_forwarded_for", "require_nonce",
            "field_mapping", "required_fields", "dedup_window",
            "reward_rules", "default_reward_points",
            "rate_limit_per_minute",
            "callback_url", "callback_method",
            "contact_email", "notes",
            "metadata", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "secret_key": {"write_only": True},
            "callback_secret": {"write_only": True},
        }


class NetworkPostbackConfigWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkPostbackConfig
        fields = [
            "name", "network_key", "network_type", "status",
            "secret_key", "signature_algorithm",
            "ip_whitelist", "trust_forwarded_for", "require_nonce",
            "field_mapping", "required_fields", "dedup_window",
            "reward_rules", "default_reward_points",
            "rate_limit_per_minute", "contact_email", "notes", "metadata",
        ]
        extra_kwargs = {
            "secret_key": {"write_only": True, "allow_blank": True},
        }

    def validate_ip_whitelist(self, value):
        from django.core.exceptions import ValidationError as DjValidationError
        try:
            validate_ip_whitelist(value)
        except DjValidationError as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def validate_field_mapping(self, value):
        from django.core.exceptions import ValidationError as DjValidationError
        try:
            validate_field_mapping(value)
        except DjValidationError as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def validate_reward_rules(self, value):
        from django.core.exceptions import ValidationError as DjValidationError
        try:
            validate_reward_rules(value)
        except DjValidationError as exc:
            raise serializers.ValidationError(str(exc))
        return value


class PostbackLogSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    network_key = serializers.CharField(source="network.network_key", read_only=True)
    resolved_user_email = serializers.SerializerMethodField()

    class Meta:
        model = PostbackLog
        fields = [
            "id", "network_key", "status", "status_display",
            "lead_id", "offer_id", "transaction_id", "payout", "currency",
            "source_ip", "signature_verified", "ip_whitelisted",
            "rejection_reason", "rejection_detail",
            "points_awarded", "inventory_id",
            "retry_count", "processing_error",
            "received_at", "processed_at",
            "resolved_user_email",
        ]
        read_only_fields = fields

    def get_resolved_user_email(self, obj) -> str:
        return obj.resolved_user.email if obj.resolved_user else ""


class PostbackLogDetailSerializer(PostbackLogSerializer):
    class Meta(PostbackLogSerializer.Meta):
        fields = PostbackLogSerializer.Meta.fields + [
            "raw_payload", "request_headers", "method",
            "query_string", "next_retry_at",
            "click_id", "event_type", "conversion_status",
            "is_reversal", "reversed_log", "fire_delay_ms",
        ]


class LeadValidatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadValidator
        fields = [
            "id", "name", "validator_type", "params",
            "is_blocking", "sort_order", "is_active", "failure_reason",
        ]


class DuplicateLeadCheckSerializer(serializers.ModelSerializer):
    network_key = serializers.CharField(source="network.network_key", read_only=True)

    class Meta:
        model = DuplicateLeadCheck
        fields = ["id", "network_key", "lead_id", "first_seen_at"]
        read_only_fields = fields


# ── New Model Serializers ───────────────────────────────────────────────────────

class PostbackInsightSerializer(serializers.ModelSerializer):
    network_key = serializers.CharField(source="network.network_key", read_only=True)
    health_score_display = serializers.SerializerMethodField()

    class Meta:
        model = PostbackInsight
        fields = [
            "id", "network_key", "date",
            "received_count", "validated_count", "rewarded_count",
            "rejected_count", "duplicate_count", "failed_count",
            "total_payout", "total_points_awarded",
            "health_score", "health_score_display", "average_processing_time",
            "anomaly_detected", "anomaly_details",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_health_score_display(self, obj) -> str:
        """Return health score with percentage sign."""
        return f"{obj.health_score}%"


class PostbackInsightDetailSerializer(PostbackInsightSerializer):
    """Detailed serializer with additional analytics fields."""
    success_rate = serializers.SerializerMethodField()
    rejection_rate = serializers.SerializerMethodField()
    duplicate_rate = serializers.SerializerMethodField()

    class Meta(PostbackInsightSerializer.Meta):
        fields = PostbackInsightSerializer.Meta.fields + [
            "success_rate", "rejection_rate", "duplicate_rate"
        ]

    def get_success_rate(self, obj) -> float:
        """Calculate success rate percentage."""
        if obj.received_count == 0:
            return 0.0
        return round((obj.rewarded_count + obj.validated_count) / obj.received_count * 100, 2)

    def get_rejection_rate(self, obj) -> float:
        """Calculate rejection rate percentage."""
        if obj.received_count == 0:
            return 0.0
        return round((obj.rejected_count + obj.failed_count) / obj.received_count * 100, 2)

    def get_duplicate_rate(self, obj) -> float:
        """Calculate duplicate rate percentage."""
        if obj.received_count == 0:
            return 0.0
        return round(obj.duplicate_count / obj.received_count * 100, 2)


class PostbackTemplateSerializer(serializers.ModelSerializer):
    network_key = serializers.CharField(source="network.network_key", read_only=True)
    variable_count = serializers.SerializerMethodField()

    class Meta:
        model = PostbackTemplate
        fields = [
            "id", "network_key", "name", "description",
            "template_body", "variables", "variable_count",
            "validation_regex", "required_variables",
            "is_active", "usage_count", "last_used_at",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "usage_count", "last_used_at", "created_at", "updated_at"]

    def get_variable_count(self, obj) -> int:
        """Return the number of variables in the template."""
        return len(obj.variables or {})


class PostbackTemplateCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new templates with validation."""
    
    class Meta:
        model = PostbackTemplate
        fields = [
            "name", "description", "template_body", "variables",
            "validation_regex", "required_variables", "is_active",
        ]

    def validate_template_body(self, value):
        """Validate template syntax."""
        import re
        # Find all variables in template
        pattern = r'\{\{(\w+)\}\}'
        found_variables = re.findall(pattern, value)
        
        if not found_variables:
            raise serializers.ValidationError(
                "Template must contain at least one variable placeholder (e.g., {{lead_id}})"
            )
        
        return value


class PostbackTemplateRenderSerializer(serializers.Serializer):
    """Serializer for template rendering requests."""
    context = serializers.JSONField(
        help_text="JSON object with variable values for template rendering"
    )
    increment_usage = serializers.BooleanField(
        default=True,
        help_text="Whether to increment usage counter"
    )


class PostbackIPWhitelistSerializer(serializers.ModelSerializer):
    network_key = serializers.CharField(source="network.network_key", read_only=True)
    ip_type = serializers.SerializerMethodField()

    class Meta:
        model = PostbackIPWhitelist
        fields = [
            "id", "network_key", "name", "ip_address", "ip_type",
            "description", "is_active", "priority",
            "usage_count", "last_used_at",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "usage_count", "last_used_at", "created_at", "updated_at"]

    def get_ip_type(self, obj) -> str:
        """Determine if this is a single IP or CIDR range."""
        import ipaddress
        try:
            ipaddress.ip_network(obj.ip_address, strict=False)
            return "CIDR" if '/' in obj.ip_address else "Single IP"
        except ValueError:
            return "Invalid"


class PostbackIPWhitelistCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating IP whitelist entries with validation."""
    
    class Meta:
        model = PostbackIPWhitelist
        fields = [
            "name", "ip_address", "description", "is_active", "priority"
        ]

    def validate_ip_address(self, value):
        """Validate IP address or CIDR range format."""
        import ipaddress
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError:
            raise serializers.ValidationError(
                f"'{value}' is not a valid IP address or CIDR range"
            )
        return value


class PostbackRateLimitSerializer(serializers.ModelSerializer):
    network_key = serializers.CharField(source="network.network_key", read_only=True)
    is_currently_blocked = serializers.SerializerMethodField()
    current_utilization = serializers.SerializerMethodField()

    class Meta:
        model = PostbackRateLimit
        fields = [
            "id", "network_key", "name",
            "max_per_minute", "max_per_hour", "max_per_day",
            "current_count", "current_utilization", "is_currently_blocked",
            "is_active", "is_blocked", "blocked_until",
            "total_violations", "last_violation_at",
            "last_reset_at", "window_start",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "current_count", "total_violations", "last_violation_at",
            "last_reset_at", "window_start", "created_at", "updated_at"
        ]

    def get_is_currently_blocked(self, obj) -> bool:
        """Check if the rate limit is currently blocked."""
        if not obj.is_blocked or not obj.blocked_until:
            return False
        from django.utils import timezone
        return timezone.now() < obj.blocked_until

    def get_current_utilization(self, obj) -> float:
        """Calculate current utilization percentage."""
        if obj.max_per_minute == 0:
            return 0.0
        return round(obj.current_count / obj.max_per_minute * 100, 2)


class PostbackRateLimitCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating rate limit configurations."""
    
    class Meta:
        model = PostbackRateLimit
        fields = [
            "name", "max_per_minute", "max_per_hour", "max_per_day", "is_active"
        ]

    def validate(self, data):
        """Validate that hourly and daily limits are not less than minute limits."""
        max_per_minute = data.get('max_per_minute', 0)
        max_per_hour = data.get('max_per_hour', 0)
        max_per_day = data.get('max_per_day', 0)

        if max_per_hour > 0 and max_per_hour < max_per_minute:
            raise serializers.ValidationError({
                'max_per_hour': 'Hourly limit cannot be less than minute limit'
            })

        if max_per_day > 0 and max_per_day < max_per_hour:
            raise serializers.ValidationError({
                'max_per_day': 'Daily limit cannot be less than hourly limit'
            })

        return data


# ── PostbackS2SLog Serializer ─────────────────────────────────────────────────

class PostbackS2SLogSerializer(serializers.ModelSerializer):
    postback_log_id = serializers.UUIDField(source="postback_log.pk", read_only=True)

    class Meta:
        from .models import PostbackS2SLog
        model = PostbackS2SLog
        fields = [
            "id", "postback_log_id",
            "callback_url", "http_status", "response_body",
            "success", "attempt_number", "error_message",
            "fired_at",
        ]
        read_only_fields = fields


# ══════════════════════════════════════════════════════════════════════════════
# NEW COMPONENT SERIALIZERS
# ══════════════════════════════════════════════════════════════════════════════

from .models import (
    OfferCategory, Offer, OfferClick, UserOfferCompletion,
    PaymentMethod, WithdrawalRequest,
    ReferralProgram, UserReferral, ReferralCommission,
    UserTier, UserTierMembership,
    DailyBonusConfig, UserLoginStreak,
    LeaderboardEntry,
    GeoTargetingRule,
    SurveyRouter,
    OfferwallSDKConfig,
)


class OfferCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferCategory
        fields = ["id", "name", "slug", "icon_url", "sort_order", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class OfferListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    network_key = serializers.CharField(source="network.network_key", read_only=True)

    class Meta:
        model = Offer
        fields = [
            "id", "network_key", "category_name", "external_offer_id",
            "name", "points_reward", "payout_usd", "difficulty",
            "device_target", "icon_url", "is_active", "is_featured",
            "countries_allowed", "idfa_required", "gaid_required",
            "daily_cap", "user_daily_cap", "expires_at", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class OfferDetailSerializer(OfferListSerializer):
    class Meta(OfferListSerializer.Meta):
        fields = OfferListSerializer.Meta.fields + [
            "description", "requirements", "offer_url",
            "countries_blocked", "metadata",
        ]


class OfferClickSerializer(serializers.ModelSerializer):
    offer_name = serializers.CharField(source="offer.name", read_only=True)

    class Meta:
        model = OfferClick
        fields = [
            "id", "offer", "offer_name", "click_id",
            "source_ip", "user_agent", "country_code", "device_type",
            "idfa", "gaid", "clicked_at", "converted",
        ]
        read_only_fields = ["id", "clicked_at", "converted"]
        extra_kwargs = {
            "idfa": {"write_only": True},
            "gaid": {"write_only": True},
        }


class UserOfferCompletionSerializer(serializers.ModelSerializer):
    offer_name = serializers.CharField(source="offer.name", read_only=True)

    class Meta:
        model = UserOfferCompletion
        fields = [
            "id", "offer", "offer_name", "postback_log",
            "points_awarded", "completed_at", "is_reversed",
        ]
        read_only_fields = ["id", "completed_at", "is_reversed"]


# ── Withdrawal serializers ──────────────────────────────────────────────────

class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = [
            "id", "method_type", "account_identifier",
            "is_verified", "is_default", "created_at",
        ]
        read_only_fields = ["id", "is_verified", "created_at"]
        extra_kwargs = {"account_identifier": {"write_only": True}}


class PaymentMethodReadSerializer(PaymentMethodSerializer):
    masked_identifier = serializers.SerializerMethodField()

    class Meta(PaymentMethodSerializer.Meta):
        fields = ["id", "method_type", "masked_identifier", "is_verified", "is_default", "created_at"]

    def get_masked_identifier(self, obj):
        ident = obj.account_identifier
        if len(ident) <= 6:
            return "***"
        return ident[:3] + "***" + ident[-3:]


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    payment_method_display = serializers.CharField(
        source="payment_method.get_method_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = WithdrawalRequest
        fields = [
            "id", "payment_method", "payment_method_display",
            "points_requested", "amount_bdt", "status", "status_display",
            "admin_note", "rejection_reason",
            "processed_at", "transaction_reference", "created_at",
        ]
        read_only_fields = [
            "id", "amount_bdt", "status", "admin_note",
            "rejection_reason", "processed_at", "transaction_reference", "created_at",
        ]


class WithdrawalRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WithdrawalRequest
        fields = ["payment_method", "points_requested"]

    def validate_points_requested(self, value):
        from django.conf import settings as djsettings
        min_points = getattr(djsettings, "MIN_WITHDRAWAL_POINTS", 500)
        if value < min_points:
            raise serializers.ValidationError(
                f"Minimum withdrawal is {min_points} points."
            )
        return value


# ── Referral serializers ────────────────────────────────────────────────────

class ReferralProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralProgram
        fields = [
            "id", "name", "is_active", "commission_type", "commission_value",
            "max_referral_depth", "referral_bonus_points", "referee_bonus_points",
            "minimum_earning_for_commission",
        ]
        read_only_fields = ["id"]


class UserReferralSerializer(serializers.ModelSerializer):
    referrer_username = serializers.CharField(source="referrer.username", read_only=True)
    referee_username = serializers.CharField(source="referee.username", read_only=True)

    class Meta:
        model = UserReferral
        fields = [
            "id", "program", "referrer_username", "referee_username",
            "referral_code", "total_commission_earned", "is_active", "created_at",
        ]
        read_only_fields = ["id", "total_commission_earned", "created_at"]


class ReferralCommissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralCommission
        fields = ["id", "referral", "postback_log", "points_awarded", "commission_rate", "created_at"]
        read_only_fields = ["id", "created_at"]


# ── Tier serializers ────────────────────────────────────────────────────────

class UserTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTier
        fields = [
            "id", "name", "slug", "min_lifetime_points",
            "earnings_multiplier", "withdrawal_priority",
            "badge_color", "badge_icon", "sort_order",
        ]
        read_only_fields = ["id"]


class UserTierMembershipSerializer(serializers.ModelSerializer):
    tier = UserTierSerializer(read_only=True)

    class Meta:
        model = UserTierMembership
        fields = ["user", "tier", "lifetime_points", "tier_entered_at", "created_at"]
        read_only_fields = fields


# ── Daily bonus serializers ─────────────────────────────────────────────────

class DailyBonusConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyBonusConfig
        fields = ["id", "day_number", "points_reward", "is_milestone", "label"]
        read_only_fields = ["id"]


class UserLoginStreakSerializer(serializers.ModelSerializer):
    can_claim_today = serializers.SerializerMethodField()
    next_reward_points = serializers.SerializerMethodField()

    class Meta:
        model = UserLoginStreak
        fields = [
            "current_streak", "longest_streak", "last_claim_date",
            "total_bonuses_claimed", "total_points_from_bonus",
            "can_claim_today", "next_reward_points",
        ]
        read_only_fields = fields

    def get_can_claim_today(self, obj):
        from django.utils.timezone import localdate
        return obj.last_claim_date != localdate()

    def get_next_reward_points(self, obj):
        next_day = obj.current_streak + 1
        cfg = (
            DailyBonusConfig.objects.filter(day_number=next_day).first()
            or DailyBonusConfig.objects.order_by("-day_number").first()
        )
        return cfg.points_reward if cfg else 10


# ── Leaderboard serializers ─────────────────────────────────────────────────

class LeaderboardEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaderboardEntry
        fields = [
            "rank", "display_name", "avatar_url",
            "points_earned", "offers_completed", "period", "period_start",
        ]
        read_only_fields = fields


# ── Geo targeting serializers ───────────────────────────────────────────────

class GeoTargetingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoTargetingRule
        fields = [
            "id", "network", "country_code", "action",
            "payout_multiplier", "is_active", "priority", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# ── Survey router serializers ───────────────────────────────────────────────

class SurveyRouterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SurveyRouter
        fields = [
            "id", "name", "provider_key", "router_url_template",
            "countries_supported", "device_support",
            "min_cpi_usd", "priority", "is_active", "metadata", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {"api_key": {"write_only": True}}


# ── Offerwall SDK serializers ───────────────────────────────────────────────

class OfferwallSDKConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferwallSDKConfig
        fields = [
            "id", "network", "publisher_name", "sdk_key",
            "allowed_domains", "theme", "primary_color",
            "show_search", "show_categories", "default_category",
            "session_ttl_seconds", "is_active", "created_at",
        ]
        read_only_fields = ["id", "sdk_key", "created_at"]
        extra_kwargs = {"sdk_secret": {"write_only": True}}


class OfferwallEmbedURLSerializer(serializers.Serializer):
    user_id = serializers.CharField()
    country_code = serializers.CharField(max_length=2, required=False, default="")
    device_type = serializers.ChoiceField(
        choices=["all", "mobile", "desktop"], required=False, default="all"
    )
    sub_id1 = serializers.CharField(required=False, default="")


# ── New model serializers (Round 2) ──────────────────────────────────────────

from .models import (
    SiteConfig, CurrencyRate, ManualPointAdjustment,
    FCMDevice, OfferImpression, OfferDailyCapCounter,
)


class SiteConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteConfig
        fields = [
            "points_to_bdt_rate", "points_to_usd_rate",
            "min_withdrawal_points", "max_withdrawal_points_per_day",
            "maintenance_mode",
            "referral_program_enabled", "daily_bonus_enabled",
            "leaderboard_enabled", "survey_router_enabled", "offerwall_enabled",
            "max_completions_per_user_per_day", "max_withdrawal_requests_per_day",
            "withdrawal_fraud_hold_hours", "updated_at",
        ]
        read_only_fields = ["updated_at"]


class CurrencyRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrencyRate
        fields = [
            "id", "points_to_bdt", "points_to_usd",
            "effective_from", "note", "set_by",
        ]
        read_only_fields = ["id", "effective_from", "set_by"]


class ManualPointAdjustmentSerializer(serializers.ModelSerializer):
    performed_by_username = serializers.CharField(
        source="performed_by.username", read_only=True
    )
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = ManualPointAdjustment
        fields = [
            "id", "user", "user_username",
            "adjustment_type", "points", "reason", "note",
            "performed_by", "performed_by_username", "created_at",
        ]
        read_only_fields = ["id", "performed_by", "created_at"]


class ManualPointAdjustmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManualPointAdjustment
        fields = ["user", "adjustment_type", "points", "reason", "note"]

    def validate_points(self, value):
        if value <= 0:
            raise serializers.ValidationError("Points must be a positive integer.")
        if value > 100000:
            raise serializers.ValidationError("Cannot adjust more than 100,000 points at once.")
        return value


class FCMDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMDevice
        fields = [
            "id", "platform", "device_id",
            "is_active", "last_used_at", "created_at",
        ]
        read_only_fields = ["id", "last_used_at", "created_at"]

    def create(self, validated_data):
        # Upsert by (user, device_id) — update token if device already registered
        from django.utils import timezone
        user = self.context["request"].user
        device_id = validated_data.get("device_id", "")
        if device_id:
            obj, _ = FCMDevice.objects.update_or_create(
                user=user, device_id=device_id,
                defaults={**validated_data, "last_used_at": timezone.now()},
            )
            return obj
        return FCMDevice.objects.create(user=user, **validated_data)


class OfferImpressionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferImpression
        fields = ["id", "offer", "country_code", "device_type", "shown_at"]
        read_only_fields = ["id", "shown_at"]
