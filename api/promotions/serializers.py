# =============================================================================
# api/promotions/serializers.py
# DRF Serializers — models এর সাথে 100% matched, full validation
# =============================================================================

from decimal import Decimal
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as DRFValidationError

from .models import (
    PromotionCategory, Platform, RewardPolicy, AdCreative, CurrencyRate,
    Campaign, TargetingCondition, TaskStep, TaskLimit, BonusPolicy, CampaignSchedule,
    TaskSubmission, SubmissionProof, VerificationLog, Dispute,
    PromotionTransaction, EscrowWallet, AdminCommissionLog, ReferralCommissionLog,
    UserReputation, FraudReport, DeviceFingerprint, Blacklist, CampaignAnalytics,
)
from .choices import (
    CampaignStatus, SubmissionStatus, DisputeStatus,
    ProofType, TransactionType,
)
from .validators import (
    validate_http_https_url, validate_country_code, validate_currency_code,
    validate_country_code_list, validate_device_type_list, validate_os_type_list,
    validate_fingerprint_hash, validate_screen_resolution, validate_no_html_tags,
    validate_withdrawal_amount, validate_campaign_budget,
)
from .constants import CAMPAIGN_MAX_SLOTS


# =============================================================================
# ── SYSTEM FOUNDATION ────────────────────────────────────────────────────────
# =============================================================================

class PromotionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model   = PromotionCategory
        fields  = ['id', 'name', 'description', 'icon_url', 'sort_order', 'is_active']
        read_only_fields = ['id']

    def validate_name(self, value):
        return value.lower().strip()


class PlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Platform
        fields = ['id', 'name', 'base_url', 'icon_url', 'is_active']
        read_only_fields = ['id']


class RewardPolicySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.get_name_display', read_only=True)

    class Meta:
        model  = RewardPolicy
        fields = [
            'id', 'country_code', 'category', 'category_name',
            'rate_usd', 'min_payout_usd', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_country_code(self, value):
        validate_country_code(value)
        return value.upper().strip()

    def validate(self, attrs):
        rate        = attrs.get('rate_usd')
        min_payout  = attrs.get('min_payout_usd')
        if rate and min_payout and min_payout < rate:
            raise DRFValidationError({
                'min_payout_usd': _('min_payout_usd অবশ্যই rate_usd এর চেয়ে বেশি বা সমান হতে হবে।')
            })
        return attrs


class AdCreativeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AdCreative
        fields = [
            'id', 'campaign', 'type', 'file_url', 'thumbnail_url',
            'title', 'duration_sec', 'is_approved', 'created_at',
        ]
        read_only_fields = ['id', 'is_approved', 'created_at']

    def validate_file_url(self, value):
        validate_http_https_url(value)
        return value

    def validate(self, attrs):
        creative_type = attrs.get('type')
        duration      = attrs.get('duration_sec')
        if creative_type == 'video' and not duration:
            raise DRFValidationError({'duration_sec': _('Video creative এ duration_sec আবশ্যক।')})
        if creative_type != 'video' and duration:
            raise DRFValidationError({'duration_sec': _('duration_sec শুধু video type এর জন্য।')})
        return attrs


class CurrencyRateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CurrencyRate
        fields = ['id', 'from_currency', 'to_currency', 'rate', 'source', 'fetched_at']
        read_only_fields = ['id', 'fetched_at']

    def validate_from_currency(self, value):
        validate_currency_code(value)
        return value.upper()

    def validate_to_currency(self, value):
        validate_currency_code(value)
        return value.upper()

    def validate(self, attrs):
        if attrs.get('from_currency') == attrs.get('to_currency'):
            raise DRFValidationError(_('from_currency এবং to_currency একই হতে পারবে না।'))
        return attrs


# =============================================================================
# ── CAMPAIGN MANAGEMENT ──────────────────────────────────────────────────────
# =============================================================================

class TargetingConditionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TargetingCondition
        fields = [
            'campaign', 'countries', 'devices', 'os_types',
            'min_user_level', 'max_user_level', 'min_reputation_score',
        ]
        read_only_fields = ['campaign']

    def validate_countries(self, value):
        validate_country_code_list(value)
        return [c.upper() for c in value]

    def validate_devices(self, value):
        validate_device_type_list(value)
        return value

    def validate_os_types(self, value):
        validate_os_type_list(value)
        return value

    def validate(self, attrs):
        min_lvl = attrs.get('min_user_level', 1)
        max_lvl = attrs.get('max_user_level', 100)
        if min_lvl > max_lvl:
            raise DRFValidationError({
                'min_user_level': _('min_user_level অবশ্যই max_user_level এর চেয়ে কম বা সমান হতে হবে।')
            })
        return attrs


class TaskStepSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TaskStep
        fields = ['id', 'campaign', 'step_order', 'instruction', 'proof_type', 'is_required', 'hint_text']
        read_only_fields = ['id']

    def validate_instruction(self, value):
        validate_no_html_tags(value)
        if len(value.strip()) < 10:
            raise DRFValidationError(_('Instruction কমপক্ষে ১০ character হতে হবে।'))
        return value.strip()


class TaskLimitSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TaskLimit
        fields = ['campaign', 'max_per_ip', 'max_per_device', 'max_per_user', 'cooldown_hours']
        read_only_fields = ['campaign']


class BonusPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model  = BonusPolicy
        fields = [
            'id', 'campaign', 'condition_type', 'threshold_value',
            'bonus_percent', 'is_active', 'description',
        ]
        read_only_fields = ['id']

    def validate_bonus_percent(self, value):
        if value <= 0 or value > Decimal('200'):
            raise DRFValidationError(_('Bonus percent ০.০১ থেকে ২০০ এর মধ্যে হতে হবে।'))
        return value


class CampaignScheduleSerializer(serializers.ModelSerializer):
    is_currently_active = serializers.BooleanField(read_only=True)

    class Meta:
        model  = CampaignSchedule
        fields = [
            'campaign', 'start_at', 'end_at', 'timezone',
            'auto_pause_on_budget_exhaust', 'daily_budget_limit',
            'active_hours_start', 'active_hours_end', 'is_currently_active',
        ]
        read_only_fields = ['campaign']

    def validate(self, attrs):
        start = attrs.get('start_at')
        end   = attrs.get('end_at')
        if end and start and start >= end:
            raise DRFValidationError({'end_at': _('end_at অবশ্যই start_at এর পরে হতে হবে।')})

        h_start = attrs.get('active_hours_start')
        h_end   = attrs.get('active_hours_end')
        if bool(h_start) != bool(h_end):
            raise DRFValidationError(
                _('active_hours_start এবং active_hours_end দুটো একসাথে দিতে হবে।')
            )
        if h_start and h_end and h_start >= h_end:
            raise DRFValidationError({'active_hours_end': _('active_hours_end, start এর পরে হতে হবে।')})
        return attrs


# ─── Campaign — Main ──────────────────────────────────────────────────────────

class CampaignListSerializer(serializers.ModelSerializer):
    """List endpoint এর জন্য lightweight serializer।"""
    category_name  = serializers.CharField(source='category.get_name_display', read_only=True)
    platform_name  = serializers.CharField(source='platform.get_name_display', read_only=True)
    fill_percentage = serializers.FloatField(read_only=True)
    remaining_budget = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model  = Campaign
        fields = [
            'id', 'uuid', 'title', 'category_name', 'platform_name',
            'status', 'total_slots', 'filled_slots', 'fill_percentage',
            'total_budget_usd', 'remaining_budget',
            'bonus_rate', 'yield_optimization', 'risk_level', 'risk_score', 'verified', 'sparkline_data', 'promo_type', 'traffic_monitor',
            'created_at',
        ]
        read_only_fields = fields


class CampaignDetailSerializer(serializers.ModelSerializer):
    """Detail endpoint এর জন্য nested serializer।"""
    targeting  = TargetingConditionSerializer(read_only=True)
    steps      = TaskStepSerializer(many=True, read_only=True)
    limits     = TaskLimitSerializer(read_only=True)
    schedule   = CampaignScheduleSerializer(read_only=True)
    bonus_policies = BonusPolicySerializer(many=True, read_only=True)
    creatives  = AdCreativeSerializer(many=True, read_only=True)
    fill_percentage  = serializers.FloatField(read_only=True)
    remaining_budget = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_full    = serializers.BooleanField(read_only=True)
    advertiser_username = serializers.CharField(source='advertiser.username', read_only=True)

    class Meta:
        model  = Campaign
        fields = [
            'id', 'uuid', 'advertiser', 'advertiser_username',
            'title', 'description', 'category', 'platform', 'target_url',
            'total_budget_usd', 'spent_usd', 'remaining_budget',
            'profit_margin', 'total_slots', 'filled_slots',
            'fill_percentage', 'is_full', 'status', 'rejection_reason',
            'bonus_rate', 'yield_optimization', 'risk_level', 'risk_score', 'verified', 'sparkline_data', 'promo_type', 'traffic_monitor',
            'targeting', 'steps', 'limits', 'schedule',
            'bonus_policies', 'creatives',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'uuid', 'advertiser', 'spent_usd', 'filled_slots',
            'rejection_reason', 'created_at', 'updated_at',
        ]

    def validate_title(self, value):
        value = value.strip()
        validate_no_html_tags(value)
        if len(value) < 5:
            raise DRFValidationError(_('Title কমপক্ষে ৫ character হতে হবে।'))
        return value

    def validate_target_url(self, value):
        validate_http_https_url(value)
        return value

    def validate_total_budget_usd(self, value):
        validate_campaign_budget(value)
        return value

    def validate_total_slots(self, value):
        if value > CAMPAIGN_MAX_SLOTS:
            raise DRFValidationError(_(f'Slots সর্বোচ্চ {CAMPAIGN_MAX_SLOTS} হতে পারবে।'))
        return value

    def validate(self, attrs):
        # Status transition validation
        if self.instance:
            current_status = self.instance.status
            new_status     = attrs.get('status', current_status)
            valid_transitions = {
                CampaignStatus.DRAFT:      {CampaignStatus.PENDING, CampaignStatus.CANCELLED},
                CampaignStatus.PENDING:    {CampaignStatus.ACTIVE, CampaignStatus.CANCELLED, CampaignStatus.DRAFT},
                CampaignStatus.ACTIVE:     {CampaignStatus.PAUSED, CampaignStatus.COMPLETED, CampaignStatus.CANCELLED},
                CampaignStatus.PAUSED:     {CampaignStatus.ACTIVE, CampaignStatus.CANCELLED, CampaignStatus.COMPLETED},
                CampaignStatus.COMPLETED:  set(),  # Terminal state
                CampaignStatus.CANCELLED:  set(),  # Terminal state
            }
            if new_status != current_status and new_status not in valid_transitions.get(current_status, set()):
                raise DRFValidationError({
                    'status': _(f'"{current_status}" থেকে "{new_status}" তে পরিবর্তন করা যাবে না।')
                })
        return attrs


class CampaignCreateSerializer(serializers.ModelSerializer):
    """Campaign তৈরির serializer — advertiser auto-assign।"""
    targeting     = TargetingConditionSerializer(required=False)
    steps         = TaskStepSerializer(many=True, required=True)
    limits        = TaskLimitSerializer(required=False)
    schedule      = CampaignScheduleSerializer(required=False)

    class Meta:
        model  = Campaign
        fields = [
            'title', 'description', 'category', 'platform', 'target_url',
            'total_budget_usd', 'profit_margin', 'total_slots',
            'targeting', 'steps', 'limits', 'schedule',
        ]

    def validate_title(self, value):
        value = value.strip()
        validate_no_html_tags(value)
        return value

    def validate_target_url(self, value):
        validate_http_https_url(value)
        return value

    def validate_total_budget_usd(self, value):
        validate_campaign_budget(value)
        return value

    def validate_steps(self, value):
        if not value:
            raise DRFValidationError(_('কমপক্ষে একটি task step থাকতে হবে।'))
        orders = [s.get('step_order') for s in value]
        if len(orders) != len(set(orders)):
            raise DRFValidationError(_('Duplicate step_order দেওয়া যাবে না।'))
        return value

    def create(self, validated_data):
        from django.db import transaction
        targeting_data = validated_data.pop('targeting', None)
        steps_data     = validated_data.pop('steps', [])
        limits_data    = validated_data.pop('limits', None)
        schedule_data  = validated_data.pop('schedule', None)

        with transaction.atomic():
            campaign = Campaign.objects.create(
                advertiser=self.context['request'].user,
                **validated_data,
            )
            if targeting_data:
                TargetingCondition.objects.create(campaign=campaign, **targeting_data)
            for step_data in steps_data:
                TaskStep.objects.create(campaign=campaign, **step_data)
            if limits_data:
                TaskLimit.objects.create(campaign=campaign, **limits_data)
            else:
                TaskLimit.objects.create(campaign=campaign)  # defaults
            if schedule_data:
                CampaignSchedule.objects.create(campaign=campaign, **schedule_data)
        return campaign


# =============================================================================
# ── WORKER SIDE ──────────────────────────────────────────────────────────────
# =============================================================================

class SubmissionProofSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SubmissionProof
        fields = ['id', 'submission', 'step', 'proof_type', 'content', 'file_size_kb', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']

    def validate_content(self, value):
        validate_no_html_tags(value)
        if not value.strip():
            raise DRFValidationError(_('Proof content খালি হতে পারবে না।'))
        return value.strip()

    def validate(self, attrs):
        proof_type = attrs.get('proof_type')
        content    = attrs.get('content', '')
        file_size  = attrs.get('file_size_kb')

        if proof_type == ProofType.LINK:
            validate_http_https_url(content)
        if proof_type in (ProofType.SCREENSHOT, ProofType.VIDEO) and not file_size:
            raise DRFValidationError({'file_size_kb': _('Screenshot/Video এর জন্য file_size_kb দিতে হবে।')})
        return attrs


class TaskSubmissionListSerializer(serializers.ModelSerializer):
    """List view এর জন্য।"""
    worker_username = serializers.CharField(source='worker.username', read_only=True)
    total_reward    = serializers.DecimalField(max_digits=10, decimal_places=4, read_only=True)

    class Meta:
        model  = TaskSubmission
        fields = [
            'id', 'uuid', 'worker', 'worker_username', 'campaign',
            'status', 'reward_usd', 'bonus_usd', 'total_reward',
            'submitted_at', 'reviewed_at',
        ]
        read_only_fields = fields


class TaskSubmissionDetailSerializer(serializers.ModelSerializer):
    """Detail view + proofs।"""
    proofs          = SubmissionProofSerializer(many=True, read_only=True)
    total_reward    = serializers.DecimalField(max_digits=10, decimal_places=4, read_only=True)
    worker_username = serializers.CharField(source='worker.username', read_only=True)

    class Meta:
        model  = TaskSubmission
        fields = [
            'id', 'uuid', 'worker', 'worker_username', 'campaign',
            'status', 'reward_usd', 'bonus_usd', 'total_reward',
            'reviewed_at', 'reviewer', 'review_note',
            'ip_address', 'submitted_at',
            'proofs',
        ]
        read_only_fields = [
            'id', 'uuid', 'worker', 'status', 'reward_usd', 'bonus_usd',
            'reviewed_at', 'reviewer', 'review_note', 'ip_address', 'submitted_at',
        ]


class TaskSubmissionCreateSerializer(serializers.ModelSerializer):
    """Worker কর্তৃক নতুন submission।"""
    proofs = SubmissionProofSerializer(many=True, write_only=True)

    class Meta:
        model  = TaskSubmission
        fields = ['campaign', 'proofs']

    def validate_campaign(self, campaign):
        from .exceptions import (
            CampaignNotActiveException, CampaignFullException,
        )
        if campaign.status != CampaignStatus.ACTIVE:
            raise CampaignNotActiveException()
        if campaign.is_full:
            raise CampaignFullException()
        return campaign

    def create(self, validated_data):
        from django.db import transaction
        proofs_data = validated_data.pop('proofs', [])
        request     = self.context['request']

        with transaction.atomic():
            submission = TaskSubmission.objects.create(
                worker=request.user,
                ip_address=_get_client_ip_from_request(request),
                **validated_data,
            )
            for proof_data in proofs_data:
                SubmissionProof.objects.create(submission=submission, **proof_data)
        return submission


class SubmissionReviewSerializer(serializers.Serializer):
    """Admin কর্তৃক submission approve/reject।"""
    action      = serializers.ChoiceField(choices=['approve', 'reject'])
    note        = serializers.CharField(required=False, allow_blank=True, default='')
    reward_usd  = serializers.DecimalField(
        max_digits=10, decimal_places=4,
        required=False, allow_null=True,
        min_value=Decimal('0'),
    )

    def validate(self, attrs):
        if attrs['action'] == 'reject' and not attrs.get('note', '').strip():
            raise DRFValidationError({'note': _('Rejection এর কারণ (note) দেওয়া আবশ্যক।')})
        return attrs


class VerificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = VerificationLog
        fields = [
            'id', 'submission', 'verified_by', 'verifier_admin',
            'ai_model_version', 'ai_confidence_score',
            'decision', 'reason', 'verified_at',
        ]
        read_only_fields = fields


class DisputeSerializer(serializers.ModelSerializer):
    worker_username = serializers.CharField(source='worker.username', read_only=True)

    class Meta:
        model  = Dispute
        fields = [
            'id', 'submission', 'worker', 'worker_username',
            'reason', 'evidence_url', 'status',
            'admin_note', 'created_at', 'resolved_at',
        ]
        read_only_fields = [
            'id', 'worker', 'status', 'admin_note', 'created_at', 'resolved_at',
        ]

    def validate_reason(self, value):
        validate_no_html_tags(value)
        if len(value.strip()) < 20:
            raise DRFValidationError(_('কারণ কমপক্ষে ২০ character হতে হবে।'))
        return value.strip()

    def validate_evidence_url(self, value):
        if value:
            validate_http_https_url(value)
        return value

    def validate_submission(self, submission):
        from .exceptions import DisputeNotAllowedException, DisputeAlreadyExistsException
        if submission.status != SubmissionStatus.REJECTED:
            raise DisputeNotAllowedException()
        if hasattr(submission, 'dispute'):
            raise DisputeAlreadyExistsException()
        return submission


class DisputeResolveSerializer(serializers.Serializer):
    """Admin কর্তৃক dispute resolve।"""
    decision   = serializers.ChoiceField(choices=['approve', 'reject'])
    admin_note = serializers.CharField(min_length=5)


# =============================================================================
# ── FINANCE ──────────────────────────────────────────────────────────────────
# =============================================================================

class PromotionTransactionSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model  = PromotionTransaction
        fields = [
            'id', 'uuid', 'type', 'type_display', 'user', 'campaign',
            'amount_usd', 'currency_code', 'amount_local',
            'balance_after', 'reference_id', 'note',
            'is_reversed', 'created_at',
        ]
        read_only_fields = fields  # Transaction immutable — create only


class EscrowWalletSerializer(serializers.ModelSerializer):
    remaining_amount_usd = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model  = EscrowWallet
        fields = [
            'campaign', 'advertiser', 'locked_amount_usd',
            'released_amount_usd', 'remaining_amount_usd',
            'status', 'locked_at', 'released_at',
        ]
        read_only_fields = fields


class AdminCommissionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AdminCommissionLog
        fields = [
            'submission', 'campaign',
            'gross_amount_usd', 'worker_reward_usd',
            'commission_usd', 'commission_rate', 'created_at',
        ]
        read_only_fields = fields


class ReferralCommissionLogSerializer(serializers.ModelSerializer):
    referrer_username = serializers.CharField(source='referrer.username', read_only=True)
    referred_username = serializers.CharField(source='referred.username', read_only=True)

    class Meta:
        model  = ReferralCommissionLog
        fields = [
            'id', 'referrer', 'referrer_username',
            'referred', 'referred_username',
            'level', 'source_submission',
            'commission_usd', 'commission_rate',
            'status', 'paid_at', 'created_at',
        ]
        read_only_fields = fields


# =============================================================================
# ── SECURITY & ANALYTICS ─────────────────────────────────────────────────────
# =============================================================================

class UserReputationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = UserReputation
        fields = [
            'user', 'total_submissions', 'approved_count',
            'rejected_count', 'disputed_count',
            'success_rate', 'trust_score', 'level',
            'is_verified_worker', 'last_active_at', 'last_updated',
        ]
        read_only_fields = fields


class FraudReportSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FraudReport
        fields = [
            'id', 'user', 'submission', 'fraud_type',
            'ai_model_version', 'confidence_score',
            'evidence', 'action_taken',
            'reviewed_by_admin', 'admin_note', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class DeviceFingerprintSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DeviceFingerprint
        fields = [
            'id', 'user', 'fingerprint_hash',
            'device_type', 'os', 'os_version',
            'browser', 'browser_version',
            'screen_resolution',
            'first_seen', 'last_seen',
            'is_flagged', 'flag_reason', 'linked_account_count',
        ]
        read_only_fields = ['id', 'first_seen', 'last_seen', 'linked_account_count']

    def validate_fingerprint_hash(self, value):
        validate_fingerprint_hash(value)
        return value.lower()

    def validate_screen_resolution(self, value):
        if value:
            validate_screen_resolution(value)
        return value


class BlacklistSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Blacklist
        fields = [
            'id', 'type', 'value', 'reason', 'added_by',
            'severity', 'expires_at', 'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'added_by', 'created_at']

    def validate_reason(self, value):
        if len(value.strip()) < 5:
            raise DRFValidationError(_('কারণ কমপক্ষে ৫ character হতে হবে।'))
        return value.strip()

    def validate(self, attrs):
        severity   = attrs.get('severity')
        expires_at = attrs.get('expires_at')
        bl_type    = attrs.get('type')
        value      = attrs.get('value', '')

        if severity == 'temp_ban' and not expires_at:
            raise DRFValidationError({'expires_at': _('Temporary ban এ expires_at দেওয়া আবশ্যক।')})
        if severity == 'permanent' and expires_at:
            raise DRFValidationError({'expires_at': _('Permanent ban এ expires_at দেওয়া যাবে না।')})
        if bl_type == 'ip':
            from .validators import validate_ip_address
            validate_ip_address(value)
        return attrs

    def create(self, validated_data):
        validated_data['added_by'] = self.context['request'].user
        return super().create(validated_data)


class CampaignAnalyticsSerializer(serializers.ModelSerializer):
    approval_rate     = serializers.FloatField(read_only=True)
    click_through_rate = serializers.FloatField(read_only=True)

    class Meta:
        model  = CampaignAnalytics
        fields = [
            'id', 'campaign', 'date',
            'total_views', 'total_clicks', 'unique_visitors',
            'total_submissions', 'approved_count', 'rejected_count',
            'disputed_count', 'fraud_detected',
            'total_spent_usd', 'admin_commission_usd',
            'avg_completion_time_sec', 'unique_countries',
            'approval_rate', 'click_through_rate', 'updated_at',
        ]
        read_only_fields = fields


# ─── Utility ──────────────────────────────────────────────────────────────────

def _get_client_ip_from_request(request) -> str | None:
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
