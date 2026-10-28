# api/referral/serializers.py
# DRF serializers — পুরনো সব + নতুন সব models
# ============================================================

from rest_framework import serializers
from .models import (
    Referral, ReferralSettings, ReferralEarning, ReferralChain,
    ReferralLeaderboard, ReferralLink, ReferralCode, ReferralRelationship,
    ReferralTree, ReferralLevel,
    CommissionRule, CommissionLog, CommissionPayout,
    CommissionHold, CommissionClawback,
    ReferralCampaign, ReferralBonus, ReferralContest,
    ReferralReward, ContestEntry,
    ReferralFraudRule, ReferralFraudLog, ReferralBlacklist,
    SuspiciousReferral,
    ReferralInsight, ReferralConversionRate, TopReferrer, ReferralLTV,
)


# ── Core / Legacy ──────────────────────────────────────────────────────────────

class ReferralSettingsSerializer(serializers.ModelSerializer):
    lifetime_commission_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )

    class Meta:
        model = ReferralSettings
        fields = [
            'id', 'direct_signup_bonus', 'referrer_signup_bonus',
            'level1_commission_rate', 'level2_commission_rate',
            'level3_commission_rate', 'lifetime_commission_rate',
            'commission_hold_days', 'max_referral_depth',
            'min_payout_threshold', 'referral_cookie_days',
            'allow_self_referral', 'team_bonus_enabled',
            'team_bonus_min_referrals', 'team_bonus_rate',
            'is_active', 'active_campaign',
        ]
        read_only_fields = ['lifetime_commission_rate']


class ReferralSerializer(serializers.ModelSerializer):
    referrer_username = serializers.CharField(
        source='referrer.username', read_only=True
    )
    referred_user_username = serializers.CharField(
        source='referred_user.username', read_only=True
    )

    class Meta:
        model = Referral
        fields = [
            'id', 'referrer', 'referrer_username',
            'referred_user', 'referred_user_username',
            'level', 'signup_bonus_given', 'total_commission_earned',
            'registration_ip', 'is_suspicious', 'suspicious_reason',
            'created_at',
        ]
        read_only_fields = ['created_at', 'total_commission_earned']


class ReferralEarningSerializer(serializers.ModelSerializer):
    referrer_username = serializers.CharField(
        source='referrer.username', read_only=True
    )
    referred_user_username = serializers.CharField(
        source='referred_user.username', read_only=True
    )

    class Meta:
        model = ReferralEarning
        fields = [
            'id', 'referral', 'referrer', 'referrer_username',
            'referred_user', 'referred_user_username',
            'level', 'amount', 'commission_rate',
            'source_amount', 'source_type', 'source_id',
            'source_task', 'wallet_transaction_id',
            'status', 'campaign_multiplier', 'created_at',
        ]
        read_only_fields = ['created_at']


class ReferralChainSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralChain
        fields = [
            'id', 'beneficiary', 'earner', 'level', 'created_at',
        ]
        read_only_fields = ['created_at']


class ReferralLeaderboardSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ReferralLeaderboard
        fields = [
            'id', 'user', 'username', 'period', 'rank',
            'total_referrals', 'active_referrals', 'total_commission',
            'period_start', 'period_end', 'created_at',
        ]


# ── ReferralLink ───────────────────────────────────────────────────────────────

class ReferralLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralLink
        fields = [
            'id', 'user', 'code', 'custom_alias',
            'total_clicks', 'unique_clicks', 'total_signups',
            'conversion_rate', 'is_active', 'created_at',
        ]
        read_only_fields = [
            'code', 'total_clicks', 'unique_clicks',
            'total_signups', 'conversion_rate', 'created_at',
        ]


# ── ReferralCode ───────────────────────────────────────────────────────────────

class ReferralCodeSerializer(serializers.ModelSerializer):
    active_code = serializers.SerializerMethodField()
    conversion_rate = serializers.SerializerMethodField()

    class Meta:
        model = ReferralCode
        fields = [
            'id', 'user', 'code', 'custom_code', 'active_code',
            'source_tag', 'campaign',
            'clicks', 'unique_clicks', 'conversions',
            'conversion_rate', 'revenue_generated',
            'is_primary', 'is_active', 'expires_at', 'created_at',
        ]
        read_only_fields = [
            'code', 'clicks', 'unique_clicks', 'conversions',
            'revenue_generated', 'created_at',
        ]

    def get_active_code(self, obj):
        return obj.get_active_code()

    def get_conversion_rate(self, obj):
        return obj.conversion_rate


# ── Tree ───────────────────────────────────────────────────────────────────────

class ReferralRelationshipSerializer(serializers.ModelSerializer):
    referrer_username = serializers.CharField(
        source='referrer.username', read_only=True
    )
    referred_username = serializers.CharField(
        source='referred.username', read_only=True
    )

    class Meta:
        model = ReferralRelationship
        fields = [
            'id', 'referrer', 'referrer_username',
            'referred', 'referred_username',
            'level', 'commission_rate_snapshot',
            'total_commission_earned', 'is_active', 'joined_at',
        ]
        read_only_fields = ['joined_at']


class ReferralTreeSerializer(serializers.ModelSerializer):
    root_user_username = serializers.CharField(
        source='root_user.username', read_only=True
    )

    class Meta:
        model = ReferralTree
        fields = [
            'id', 'root_user', 'root_user_username',
            'depth', 'total_members',
            'level1_count', 'level2_count', 'level3_count',
            'total_earned', 'level1_earned', 'level2_earned', 'level3_earned',
            'last_rebuilt_at', 'updated_at',
        ]


class ReferralLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralLevel
        fields = [
            'id', 'level_number', 'name', 'commission_rate',
            'max_depth', 'min_activity_requirement',
            'color_code', 'icon', 'is_active',
        ]


# ── Commission ─────────────────────────────────────────────────────────────────

class CommissionRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionRule
        fields = [
            'id', 'level', 'action_type', 'rate_type', 'rate_value',
            'min_trigger_amount', 'max_commission_per_tx',
            'daily_cap_per_user', 'description', 'is_active', 'priority',
        ]


class CommissionLogSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    referred_user_username = serializers.CharField(
        source='referred_user.username', read_only=True
    )
    release_at = serializers.SerializerMethodField()

    class Meta:
        model = CommissionLog
        fields = [
            'id', 'user', 'user_username',
            'referred_user', 'referred_user_username',
            'action_type', 'amount', 'base_amount', 'commission_rate',
            'level', 'rule', 'status',
            'wallet_transaction_id', 'source_reference',
            'release_at', 'created_at',
        ]
        read_only_fields = ['created_at']

    def get_release_at(self, obj):
        try:
            if hasattr(obj, 'hold') and obj.hold:
                return obj.hold.release_at.strftime('%Y-%m-%d')
        except Exception:
            pass
        return None


class CommissionPayoutSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = CommissionPayout
        fields = [
            'id', 'user', 'user_username', 'total_amount',
            'period', 'period_start', 'period_end',
            'status', 'wallet_transaction_id', 'paid_at', 'created_at',
        ]
        read_only_fields = ['created_at', 'paid_at']


class CommissionHoldSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionHold
        fields = [
            'id', 'commission', 'hold_days', 'release_at',
            'reason', 'reason_detail', 'is_released',
            'released_at', 'created_at',
        ]


class CommissionClawbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommissionClawback
        fields = [
            'id', 'commission', 'reason', 'reason_detail',
            'clawback_amount', 'status', 'approved_by',
            'wallet_transaction_id', 'clawed_back_at', 'created_at',
        ]


# ── Campaign ───────────────────────────────────────────────────────────────────

class ReferralCampaignSerializer(serializers.ModelSerializer):
    is_currently_active = serializers.SerializerMethodField()
    remaining_budget = serializers.SerializerMethodField()

    class Meta:
        model = ReferralCampaign
        fields = [
            'id', 'name', 'slug', 'description',
            'start_date', 'end_date', 'bonus_multiplier',
            'extra_signup_bonus', 'max_budget', 'current_spend',
            'max_referrals', 'current_referrals',
            'is_active', 'is_featured', 'terms',
            'is_currently_active', 'remaining_budget',
            'created_at',
        ]
        read_only_fields = ['slug', 'current_spend', 'current_referrals', 'created_at']

    def get_is_currently_active(self, obj):
        return obj.is_currently_active()

    def get_remaining_budget(self, obj):
        return float(obj.remaining_budget())


class ReferralBonusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralBonus
        fields = [
            'id', 'campaign', 'milestone_type', 'milestone_value',
            'bonus_amount', 'reward_type', 'multiplier_value',
            'multiplier_duration_days', 'title', 'description',
            'icon', 'is_repeatable', 'is_active',
        ]


class ReferralContestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralContest
        fields = [
            'id', 'title', 'slug', 'description', 'rules',
            'start_date', 'end_date', 'prize_pool',
            'leaderboard_size', 'contest_type', 'status', 'is_public',
        ]
        read_only_fields = ['slug', 'status']


class ContestEntrySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ContestEntry
        fields = [
            'id', 'contest', 'user', 'username',
            'referral_count', 'active_referral_count',
            'commission_earned', 'ltv_score',
            'current_rank', 'final_rank', 'last_updated',
        ]


class ReferralRewardSerializer(serializers.ModelSerializer):
    winner_username = serializers.CharField(
        source='winner.username', read_only=True
    )

    class Meta:
        model = ReferralReward
        fields = [
            'id', 'contest', 'rank', 'rank_to',
            'reward_type', 'reward_value', 'reward_description',
            'winner', 'winner_username', 'status', 'distributed_at',
        ]


# ── Fraud ──────────────────────────────────────────────────────────────────────

class ReferralFraudRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralFraudRule
        fields = [
            'id', 'rule_type', 'name', 'description',
            'action', 'threshold', 'time_window_minutes',
            'fraud_score_points', 'is_active', 'priority',
        ]


class SuspiciousReferralSerializer(serializers.ModelSerializer):
    referrer_username = serializers.CharField(
        source='referral.referrer.username', read_only=True
    )
    referred_user_username = serializers.CharField(
        source='referral.referred_user.username', read_only=True
    )
    reviewed_by_username = serializers.CharField(
        source='reviewed_by.username', read_only=True
    )
    flag_list = serializers.SerializerMethodField()

    class Meta:
        model = SuspiciousReferral
        fields = [
            'id', 'referral', 'referrer_username', 'referred_user_username',
            'flags', 'flag_list', 'fraud_score', 'evidence',
            'status', 'reviewed_by', 'reviewed_by_username',
            'review_notes', 'reviewed_at', 'detected_at',
        ]

    def get_flag_list(self, obj):
        return obj.get_flag_list()


class ReferralBlacklistSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralBlacklist
        fields = [
            'id', 'pattern_type', 'pattern_value',
            'case_sensitive', 'is_regex', 'severity',
            'reason', 'hit_count', 'last_hit_at',
            'is_active', 'expires_at', 'created_at',
        ]


# ── Analytics ──────────────────────────────────────────────────────────────────

class ReferralInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralInsight
        fields = [
            'id', 'date', 'new_referrals',
            'new_referrals_l1', 'new_referrals_l2', 'new_referrals_l3',
            'commission_paid', 'commission_l1', 'commission_l2', 'commission_l3',
            'total_clicks', 'total_signups', 'conversion_rate',
            'flagged_referrals', 'blocked_referrals', 'fraud_rate',
            'active_referrers', 'milestone_bonuses_paid',
            'campaign_commissions', 'created_at',
        ]


class TopReferrerSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = TopReferrer
        fields = [
            'id', 'date', 'period', 'user', 'username',
            'rank', 'referral_count', 'active_referral_count',
            'commission_earned', 'l1_count', 'l2_count', 'l3_count',
            'l1_commission', 'l2_commission', 'l3_commission',
            'rank_change',
        ]


class ReferralLTVSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    referred_by_username = serializers.CharField(
        source='referred_by.username', read_only=True
    )

    class Meta:
        model = ReferralLTV
        fields = [
            'id', 'user', 'username', 'referred_by', 'referred_by_username',
            'lifetime_value', 'total_user_earnings',
            'task_count', 'offer_count', 'deposit_count', 'withdrawal_count',
            'engagement_score', 'days_active',
            'consecutive_active_days', 'longest_streak_days',
            'churn_risk', 'value_category',
            'first_activity_at', 'last_activity', 'updated_at',
        ]


class ReferralConversionRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralConversionRate
        fields = [
            'id', 'code', 'date', 'clicks', 'unique_clicks',
            'signups', 'offers_completed', 'tasks_completed',
            'commission_earned', 'click_to_signup_pct',
            'signup_to_offer_pct', 'conversion_pct',
        ]