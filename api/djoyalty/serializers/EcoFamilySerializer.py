# api/djoyalty/serializers/EcoFamilySerializer.py
"""
Djoyalty Eco/Family/Charity Serializers -- NEW।
FamilyAccount, FamilyMember, EcoAction, CustomerEcoAction,
CustomerEcoStats, CharityCause, CharityDonation,
ExperientialReward, ExperientialRegistration, CustomerConsent --
all had ZERO serializers।
"""
from rest_framework import serializers
from ..models.family_eco import (
    FamilyAccount, FamilyMember,
    EcoAction, CustomerEcoAction, CustomerEcoStats,
    CharityCause, CharityDonation,
    ExperientialReward, ExperientialRegistration,
    CustomerConsent,
    ReceiptScan, ReceiptEarnRule,
)


# ─── Family Account ────────────────────────────────────────────────────────────

class FamilyMemberSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = FamilyMember
        fields = [
            'id', 'customer', 'customer_code', 'customer_name',
            'role', 'can_redeem', 'can_transfer',
            'points_contributed', 'joined_at', 'is_active',
        ]
        read_only_fields = ['id', 'customer_code', 'customer_name',
                            'points_contributed', 'joined_at']

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_customer_name(self, obj) -> str:
        return obj.customer.full_name if obj.customer else ''


class FamilyAccountSerializer(serializers.ModelSerializer):
    owner_code   = serializers.SerializerMethodField()
    members      = FamilyMemberSerializer(many=True, read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = FamilyAccount
        fields = [
            'id', 'name', 'account_code',
            'owner', 'owner_code',
            'pool_points', 'shared_balance', 'shared_lifetime_earned',
            'use_combined_tier', 'max_members',
            'is_active', 'member_count',
            'members',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'account_code', 'owner_code',
                            'shared_balance', 'shared_lifetime_earned',
                            'member_count', 'created_at', 'updated_at']

    def get_owner_code(self, obj) -> str:
        return obj.owner.code if obj.owner else ''

    def get_member_count(self, obj) -> int:
        return obj.members.filter(is_active=True).count()


class FamilyInviteSerializer(serializers.Serializer):
    """POST /family/{id}/invite/ -- invite a customer by code/email."""
    customer_code = serializers.CharField(required=False)
    email         = serializers.EmailField(required=False)
    role          = serializers.ChoiceField(
        choices=['adult', 'child'], default='adult'
    )

    def validate(self, data):
        if not data.get('customer_code') and not data.get('email'):
            raise serializers.ValidationError(
                'Provide either customer_code or email.'
            )
        return data


# ─── Eco ──────────────────────────────────────────────────────────────────────

class EcoActionSerializer(serializers.ModelSerializer):
    is_currently_valid = serializers.SerializerMethodField()

    class Meta:
        model = EcoAction
        fields = [
            'id', 'name', 'description', 'action_type',
            'points_reward', 'co2_saved_kg',
            'max_per_customer_per_day', 'requires_proof',
            'is_active', 'valid_from', 'valid_until',
            'icon', 'badge_reward',
            'is_currently_valid',
            'created_at',
        ]
        read_only_fields = ['id', 'is_currently_valid', 'created_at']

    def get_is_currently_valid(self, obj) -> bool:
        from django.utils import timezone
        now = timezone.now()
        if not obj.is_active:
            return False
        if obj.valid_from and obj.valid_from > now:
            return False
        if obj.valid_until and obj.valid_until < now:
            return False
        return True


class CustomerEcoActionSerializer(serializers.ModelSerializer):
    customer_code    = serializers.SerializerMethodField()
    action_name      = serializers.SerializerMethodField()
    action_icon      = serializers.SerializerMethodField()

    class Meta:
        model = CustomerEcoAction
        fields = [
            'id', 'customer', 'customer_code',
            'eco_action', 'action_name', 'action_icon',
            'points_awarded', 'co2_saved_kg',
            'proof_url', 'is_verified', 'verified_by',
            'location', 'completed_at', 'created_at',
        ]
        read_only_fields = fields

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_action_name(self, obj) -> str:
        return obj.eco_action.name if obj.eco_action else ''

    def get_action_icon(self, obj) -> str:
        return obj.eco_action.icon if obj.eco_action else '🌱'


class EcoActionLogSerializer(serializers.Serializer):
    """POST /eco/log/ -- log a completed eco action."""
    eco_action_id = serializers.IntegerField()
    proof_url     = serializers.URLField(required=False, allow_blank=True)
    location      = serializers.CharField(required=False, allow_blank=True, max_length=200)


class CustomerEcoStatsSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()
    trees_planted = serializers.SerializerMethodField()

    class Meta:
        model = CustomerEcoStats
        fields = [
            'id', 'customer', 'customer_code',
            'total_eco_points', 'total_co2_saved_kg',
            'total_eco_actions', 'eco_tier',
            'trees_equivalent', 'trees_planted',
            'updated_at',
        ]
        read_only_fields = fields

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_trees_planted(self, obj) -> str:
        return f'🌳 {obj.trees_equivalent:.1f} trees equivalent'


# ─── Charity ──────────────────────────────────────────────────────────────────

class CharityCauseSerializer(serializers.ModelSerializer):
    total_donors  = serializers.SerializerMethodField()
    impact_label  = serializers.SerializerMethodField()

    class Meta:
        model = CharityCause
        fields = [
            'id', 'name', 'description', 'category',
            'logo', 'website',
            'points_per_donation_unit', 'min_donation_points',
            'total_points_donated', 'total_currency_donated',
            'is_active', 'is_featured',
            'total_donors', 'impact_label',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'total_points_donated', 'total_currency_donated',
                            'total_donors', 'impact_label', 'created_at', 'updated_at']

    def get_total_donors(self, obj) -> int:
        return obj.donations.values('customer').distinct().count()

    def get_impact_label(self, obj) -> str:
        donated = float(obj.total_currency_donated)
        if donated >= 100000:
            return f'🌍 {donated/100000:.1f} lakh BDT donated'
        elif donated >= 1000:
            return f'💰 {donated/1000:.1f}k BDT donated'
        return f'💚 {donated:.0f} BDT donated'


class CharityDonationSerializer(serializers.ModelSerializer):
    customer_code  = serializers.SerializerMethodField()
    charity_name   = serializers.SerializerMethodField()

    class Meta:
        model = CharityDonation
        fields = [
            'id', 'customer', 'customer_code',
            'charity', 'charity_name',
            'points_donated', 'currency_value',
            'message', 'is_anonymous',
            'certificate_url', 'donated_at',
        ]
        read_only_fields = ['id', 'customer_code', 'charity_name',
                            'currency_value', 'certificate_url', 'donated_at']

    def get_customer_code(self, obj) -> str:
        if obj.is_anonymous:
            return 'Anonymous'
        return obj.customer.code if obj.customer else ''

    def get_charity_name(self, obj) -> str:
        return obj.charity.name if obj.charity else ''


class CharityDonateSerializer(serializers.Serializer):
    """POST /charity/{id}/donate/ -- donate points to a charity."""
    points_to_donate = serializers.DecimalField(max_digits=14, decimal_places=2)
    message          = serializers.CharField(required=False, allow_blank=True, max_length=500)
    is_anonymous     = serializers.BooleanField(default=False)

    def validate_points_to_donate(self, value):
        if value <= 0:
            raise serializers.ValidationError('Must donate a positive amount.')
        return value


# ─── Experiential Rewards ─────────────────────────────────────────────────────

class ExperientialRewardSerializer(serializers.ModelSerializer):
    slots_available    = serializers.SerializerMethodField()
    is_registered_by_me = serializers.SerializerMethodField()
    days_until_event    = serializers.SerializerMethodField()

    class Meta:
        model = ExperientialReward
        fields = [
            'id', 'name', 'description', 'experience_type',
            'points_required', 'min_tier',
            'total_slots', 'slots_remaining', 'slots_available',
            'event_date', 'event_location', 'registration_deadline',
            'image', 'video_url', 'terms',
            'status', 'is_active', 'is_featured',
            'is_registered_by_me', 'days_until_event',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'slots_remaining', 'slots_available',
                            'is_registered_by_me', 'days_until_event',
                            'created_at', 'updated_at']

    def get_slots_available(self, obj) -> int:
        return max(obj.slots_remaining, 0)

    def get_is_registered_by_me(self, obj) -> bool:
        request = self.context.get('request')
        if request and hasattr(request, 'loyalty_customer'):
            return obj.registrations.filter(
                customer=request.loyalty_customer,
                status__in=['registered', 'confirmed'],
            ).exists()
        return False

    def get_days_until_event(self, obj) -> int:
        from django.utils import timezone
        if obj.event_date:
            delta = obj.event_date.date() - timezone.now().date()
            return max(delta.days, 0)
        return 0


class ExperientialRegistrationSerializer(serializers.ModelSerializer):
    customer_code    = serializers.SerializerMethodField()
    experience_name  = serializers.SerializerMethodField()

    class Meta:
        model = ExperientialRegistration
        fields = [
            'id', 'customer', 'customer_code',
            'experience', 'experience_name',
            'points_redeemed', 'status',
            'confirmation_code', 'special_requests',
            'registered_at', 'attended_at',
            'feedback_rating', 'feedback_comment',
        ]
        read_only_fields = ['id', 'customer_code', 'experience_name',
                            'points_redeemed', 'confirmation_code', 'registered_at']

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''

    def get_experience_name(self, obj) -> str:
        return obj.experience.name if obj.experience else ''


class ExperienceRegisterSerializer(serializers.Serializer):
    """POST /experiences/{id}/register/"""
    special_requests = serializers.CharField(required=False, allow_blank=True)


class ExperienceFeedbackSerializer(serializers.Serializer):
    """POST /experiences/{id}/feedback/"""
    rating  = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True)


# ─── Customer Consent ─────────────────────────────────────────────────────────

class CustomerConsentSerializer(serializers.ModelSerializer):
    """GDPR consent management."""
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = CustomerConsent
        fields = [
            'id', 'customer', 'customer_code',
            'consent_type', 'is_granted',
            'granted_at', 'revoked_at',
            'consent_text_version', 'source',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'customer_code', 'granted_at', 'revoked_at',
                            'created_at', 'updated_at']

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''


class CustomerConsentUpdateSerializer(serializers.Serializer):
    """PATCH /consent/ -- bulk update consent preferences."""
    consents = serializers.DictField(
        child=serializers.BooleanField(),
        help_text='{"marketing_email": true, "profiling": false, ...}',
    )
    VALID_TYPES = [
        'marketing_email', 'marketing_sms', 'marketing_push',
        'data_analytics', 'data_sharing', 'profiling',
        'location', 'third_party',
    ]

    def validate_consents(self, value):
        invalid = [k for k in value if k not in self.VALID_TYPES]
        if invalid:
            raise serializers.ValidationError(
                f'Invalid consent types: {invalid}. Valid: {self.VALID_TYPES}'
            )
        return value


# ─── Receipt Scan ─────────────────────────────────────────────────────────────

class ReceiptScanSerializer(serializers.ModelSerializer):
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = ReceiptScan
        fields = [
            'id', 'customer', 'customer_code',
            'receipt_image_url',
            'merchant_name', 'total_amount', 'purchase_date', 'currency',
            'items_detected',
            'status', 'points_awarded', 'rejection_reason',
            'ai_fraud_score', 'is_ai_generated',
            'channel', 'submitted_at', 'processed_at',
        ]
        read_only_fields = [
            'id', 'customer_code',
            'merchant_name', 'total_amount', 'purchase_date',
            'items_detected',
            'status', 'points_awarded', 'rejection_reason',
            'ai_fraud_score', 'is_ai_generated',
            'submitted_at', 'processed_at',
        ]

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''


class ReceiptSubmitSerializer(serializers.Serializer):
    """POST /receipts/submit/ -- submit a receipt image."""
    receipt_image_url = serializers.URLField()
    channel           = serializers.ChoiceField(
        choices=['app', 'web', 'in_store'], default='app'
    )


class ReceiptEarnRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceiptEarnRule
        fields = [
            'id', 'name', 'description',
            'target_merchant', 'min_amount',
            'earn_type', 'points_value',
            'max_points_per_receipt', 'max_receipts_per_day',
            'is_active', 'valid_from', 'valid_until',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
