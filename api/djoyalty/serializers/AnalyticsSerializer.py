# api/djoyalty/serializers/AnalyticsSerializer.py
"""
Analytics, Compliance, AI Realtime, Web3, Omnichannel, SDK, Search,
RewardCatalog, Referral, LeaderboardEntry serializers।
FIXED: All raw-dict viewsets now have proper DRF serializers।
"""
from rest_framework import serializers


# ── Analytics ────────────────────────────────────────────────────────────────

class CustomerLTVSerializer(serializers.Serializer):
    customer_id        = serializers.IntegerField(read_only=True)
    customer_code      = serializers.CharField(read_only=True)
    predicted_ltv_12m  = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    predicted_ltv_24m  = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    historical_spend   = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    avg_order_value    = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    purchase_frequency = serializers.FloatField(read_only=True)
    churn_probability  = serializers.FloatField(read_only=True)
    rfm_segment        = serializers.CharField(read_only=True)
    rfm_score          = serializers.FloatField(read_only=True, allow_null=True)
    tier               = serializers.CharField(read_only=True, allow_null=True)


class PointsAnalyticsSerializer(serializers.Serializer):
    outstanding_liability = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    issued_this_month     = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    redeemed_this_month   = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    redemption_rate       = serializers.FloatField(read_only=True)
    breakage_estimate     = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    by_source             = serializers.DictField(child=serializers.FloatField(), read_only=True)


class CohortTableSerializer(serializers.Serializer):
    cohort_month  = serializers.CharField(read_only=True)
    cohort_size   = serializers.IntegerField(read_only=True)
    retention_m1  = serializers.FloatField(read_only=True, allow_null=True)
    retention_m3  = serializers.FloatField(read_only=True, allow_null=True)
    retention_m6  = serializers.FloatField(read_only=True, allow_null=True)
    retention_m12 = serializers.FloatField(read_only=True, allow_null=True)


class CampaignAnalyticsSerializer(serializers.Serializer):
    campaign_id         = serializers.IntegerField(read_only=True)
    name                = serializers.CharField(read_only=True)
    participants        = serializers.IntegerField(read_only=True)
    total_points_issued = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)
    conversion_rate     = serializers.FloatField(read_only=True)
    roi                 = serializers.FloatField(read_only=True, allow_null=True)
    status              = serializers.CharField(read_only=True)


class AnalyticsOverviewSerializer(serializers.Serializer):
    customers = serializers.DictField(read_only=True)
    points    = PointsAnalyticsSerializer(read_only=True)


# ── Compliance ────────────────────────────────────────────────────────────────

class GDPRDataExportSerializer(serializers.Serializer):
    customer_id    = serializers.IntegerField(read_only=True)
    customer_code  = serializers.CharField(read_only=True)
    profile        = serializers.DictField(read_only=True)
    points_history = serializers.ListField(read_only=True)
    redemptions    = serializers.ListField(read_only=True)
    consents       = serializers.ListField(read_only=True)
    exported_at    = serializers.DateTimeField(read_only=True)


class GDPRDeleteSerializer(serializers.Serializer):
    customer_id   = serializers.IntegerField(read_only=True)
    deleted       = serializers.BooleanField(read_only=True)
    anonymised    = serializers.BooleanField(read_only=True)
    fields_wiped  = serializers.ListField(child=serializers.CharField(), read_only=True)
    deleted_at    = serializers.DateTimeField(read_only=True)


class RetentionPolicySerializer(serializers.Serializer):
    record_type   = serializers.CharField(read_only=True)
    retain_days   = serializers.IntegerField(read_only=True)
    description   = serializers.CharField(read_only=True, allow_null=True)


class RetentionCleanupInputSerializer(serializers.Serializer):
    dry_run = serializers.BooleanField(default=True)


# ── AI Real-time Offers ────────────────────────────────────────────────────────

class AIOfferSerializer(serializers.Serializer):
    offer_id     = serializers.CharField(read_only=True)
    title        = serializers.CharField(read_only=True)
    description  = serializers.CharField(read_only=True)
    offer_type   = serializers.CharField(read_only=True)
    trigger      = serializers.CharField(read_only=True)
    offer_value  = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    valid_until  = serializers.DateTimeField(read_only=True)
    cta_text     = serializers.CharField(read_only=True)
    ai_confidence = serializers.FloatField(read_only=True, allow_null=True)
    status       = serializers.CharField(read_only=True)


class AIOfferFeedbackInputSerializer(serializers.Serializer):
    offer_id   = serializers.CharField(required=True)
    action     = serializers.ChoiceField(
        choices=['clicked', 'dismissed', 'claimed', 'viewed'],
        required=True,
    )
    customer_id = serializers.IntegerField(required=False, allow_null=True)


class AIEngineMetricsSerializer(serializers.Serializer):
    total_generated    = serializers.IntegerField(read_only=True)
    total_sent         = serializers.IntegerField(read_only=True)
    total_accepted     = serializers.IntegerField(read_only=True)
    acceptance_rate    = serializers.FloatField(read_only=True)
    avg_confidence     = serializers.FloatField(read_only=True)
    top_trigger        = serializers.CharField(read_only=True, allow_null=True)
    top_offer_type     = serializers.CharField(read_only=True, allow_null=True)


# ── Web3 / DAO ─────────────────────────────────────────────────────────────────

class CustomerWalletSerializer(serializers.Serializer):
    id             = serializers.IntegerField(read_only=True)
    wallet_address = serializers.CharField(read_only=True)
    wallet_type    = serializers.CharField(read_only=True)
    is_verified    = serializers.BooleanField(read_only=True)
    verified_at    = serializers.DateTimeField(read_only=True, allow_null=True)
    chain_id       = serializers.IntegerField(read_only=True)
    created_at     = serializers.DateTimeField(read_only=True)


class NFTBadgeSerializer(serializers.Serializer):
    id                = serializers.IntegerField(read_only=True)
    badge_name        = serializers.CharField(source='badge.name', read_only=True)
    token_id          = serializers.CharField(read_only=True, allow_null=True)
    contract_address  = serializers.CharField(read_only=True, allow_null=True)
    blockchain        = serializers.CharField(read_only=True)
    wallet_address    = serializers.CharField(read_only=True, allow_null=True)
    transaction_hash  = serializers.CharField(read_only=True, allow_null=True)
    metadata_uri      = serializers.URLField(read_only=True, allow_null=True)
    minted            = serializers.BooleanField(read_only=True)
    minted_at         = serializers.DateTimeField(read_only=True, allow_null=True)
    earned_at         = serializers.DateTimeField(read_only=True)


class LinkWalletInputSerializer(serializers.Serializer):
    wallet_address = serializers.CharField(required=True, max_length=100)
    wallet_type    = serializers.ChoiceField(
        choices=['metamask', 'walletconnect', 'coinbase', 'custodial'],
        default='metamask',
    )
    signature      = serializers.CharField(required=False, allow_blank=True, default='')


class DAOProposalSerializer(serializers.Serializer):
    id               = serializers.IntegerField(read_only=True)
    proposal_number  = serializers.IntegerField(read_only=True)
    title            = serializers.CharField(read_only=True)
    summary          = serializers.CharField(read_only=True)
    proposal_type    = serializers.CharField(read_only=True)
    status           = serializers.CharField(read_only=True)
    votes_for        = serializers.IntegerField(read_only=True)
    votes_against    = serializers.IntegerField(read_only=True)
    votes_abstain    = serializers.IntegerField(read_only=True)
    unique_voters    = serializers.IntegerField(read_only=True)
    voting_start     = serializers.DateTimeField(read_only=True, allow_null=True)
    voting_end       = serializers.DateTimeField(read_only=True, allow_null=True)
    passing_threshold_pct = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True, allow_null=True)
    created_at       = serializers.DateTimeField(read_only=True)


class DAOCreateProposalInputSerializer(serializers.Serializer):
    title            = serializers.CharField(max_length=200)
    summary          = serializers.CharField()
    description      = serializers.CharField()
    proposal_type    = serializers.ChoiceField(
        choices=['earn_rule','tier_threshold','catalog_item','campaign',
                 'expiry_policy','charity_partner','cashout_rate','custom'],
        default='custom',
    )
    proposed_changes = serializers.DictField(default=dict)
    voting_days      = serializers.IntegerField(min_value=3, max_value=30, default=7)


class DAOVoteInputSerializer(serializers.Serializer):
    vote    = serializers.ChoiceField(choices=['for', 'against', 'abstain'])
    comment = serializers.CharField(required=False, allow_blank=True, default='')


# ── Omnichannel / PendingPoints / PointsStacking ─────────────────────────────

class OmnichannelEarnInputSerializer(serializers.Serializer):
    customer_id  = serializers.IntegerField(required=True)
    order_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=True)
    channel      = serializers.ChoiceField(
        choices=['web', 'mobile', 'pos', 'api', 'partner', 'kiosk'],
        default='web',
    )
    reference    = serializers.CharField(required=False, allow_blank=True, default='')


class OmnichannelEarnResultSerializer(serializers.Serializer):
    points_earned = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    channel       = serializers.CharField(read_only=True)
    multiplier    = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True, allow_null=True)
    new_balance   = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True, allow_null=True)


class PendingPointsHoldInputSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField(required=True)
    points      = serializers.DecimalField(max_digits=14, decimal_places=2, required=True)
    reason      = serializers.CharField(required=False, allow_blank=True, default='')
    activate_at = serializers.DateTimeField(required=False, allow_null=True, default=None)
    reference   = serializers.CharField(required=False, allow_blank=True, default='')


class PendingBucketSerializer(serializers.Serializer):
    id            = serializers.IntegerField(read_only=True)
    points        = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    reason        = serializers.CharField(read_only=True)
    status        = serializers.CharField(read_only=True)
    activate_at   = serializers.DateTimeField(read_only=True, allow_null=True)
    activated_at  = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at    = serializers.DateTimeField(read_only=True)


class PointsStackingRuleSerializer(serializers.Serializer):
    id                = serializers.IntegerField(read_only=True)
    name              = serializers.CharField(read_only=True)
    max_daily_points  = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True, allow_null=True)
    max_per_source    = serializers.DictField(child=serializers.FloatField(), read_only=True)
    cap_type          = serializers.CharField(read_only=True)
    is_active         = serializers.BooleanField(read_only=True)


# ── SDK / Search / PublicAPI ──────────────────────────────────────────────────

class SDKInitSerializer(serializers.Serializer):
    customer    = serializers.DictField(read_only=True)
    points      = serializers.DictField(read_only=True)
    tier        = serializers.DictField(read_only=True, allow_null=True)
    features    = serializers.DictField(read_only=True)
    config      = serializers.DictField(read_only=True)


class SDKEventInputSerializer(serializers.Serializer):
    event       = serializers.CharField(required=True, max_length=100)
    properties  = serializers.DictField(required=False, default=dict)
    customer_id = serializers.IntegerField(required=False, allow_null=True)


class CustomerSearchResultSerializer(serializers.Serializer):
    id          = serializers.IntegerField(read_only=True)
    code        = serializers.CharField(read_only=True)
    firstname   = serializers.CharField(read_only=True, allow_null=True)
    lastname    = serializers.CharField(read_only=True, allow_null=True)
    phone       = serializers.CharField(read_only=True, allow_null=True)
    email       = serializers.CharField(read_only=True, allow_null=True)
    balance     = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True, allow_null=True)
    tier_name   = serializers.CharField(read_only=True, allow_null=True)
    is_active   = serializers.BooleanField(read_only=True)


class TransactionSearchResultSerializer(serializers.Serializer):
    id           = serializers.IntegerField(read_only=True)
    customer_id  = serializers.IntegerField(read_only=True)
    amount       = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    source       = serializers.CharField(read_only=True)
    reference    = serializers.CharField(read_only=True, allow_null=True)
    created_at   = serializers.DateTimeField(read_only=True)


# ── Reward Catalog ────────────────────────────────────────────────────────────

class RewardCatalogItemSerializer(serializers.Serializer):
    id               = serializers.IntegerField(read_only=True)
    name             = serializers.CharField(read_only=True)
    description      = serializers.CharField(read_only=True, allow_null=True)
    reward_type      = serializers.CharField(read_only=True)
    points_cost      = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    cash_value       = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, allow_null=True)
    image_url        = serializers.URLField(read_only=True, allow_null=True)
    is_featured      = serializers.BooleanField(read_only=True)
    is_active        = serializers.BooleanField(read_only=True)
    stock_remaining  = serializers.IntegerField(read_only=True, allow_null=True)
    supplier_name    = serializers.CharField(read_only=True, allow_null=True)
    category         = serializers.SerializerMethodField()
    valid_until      = serializers.DateTimeField(read_only=True, allow_null=True)
    min_tier_rank    = serializers.IntegerField(read_only=True, allow_null=True)

    def get_category(self, obj) -> dict | None:
        try:
            c = obj.category
            return {'id': c.id, 'name': c.name} if c else None
        except Exception:
            return None


class RedeemCatalogItemInputSerializer(serializers.Serializer):
    customer_id    = serializers.IntegerField(required=True)
    quantity       = serializers.IntegerField(default=1, min_value=1)
    delivery_info  = serializers.DictField(required=False, default=dict)


class RewardCatalogCategorySerializer(serializers.Serializer):
    id           = serializers.IntegerField(read_only=True)
    name         = serializers.CharField(read_only=True)
    description  = serializers.CharField(read_only=True, allow_null=True)
    icon         = serializers.CharField(read_only=True, allow_null=True)
    item_count   = serializers.SerializerMethodField()

    def get_item_count(self, obj) -> int:
        try:
            return obj.items.filter(is_active=True).count()
        except Exception:
            return 0


# ── Referral extended ─────────────────────────────────────────────────────────

class ReferralConvertInputSerializer(serializers.Serializer):
    referral_code   = serializers.CharField(required=True, max_length=20)
    customer_id     = serializers.IntegerField(required=True)
    conversion_type = serializers.ChoiceField(
        choices=['signup', 'first_purchase', 'purchase'],
        default='signup',
    )
    order_value     = serializers.DecimalField(
        max_digits=14, decimal_places=2,
        required=False, allow_null=True, default=None,
    )
