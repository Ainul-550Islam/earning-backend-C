# api/referral/models/__init__.py
# All models export — backward compatible
# ============================================================

# ── Legacy models ─────────────────────────────────────────────────────────────
from ..models_legacy import (
    Referral,
    ReferralChain,
    ReferralLeaderboard,
)

# ── Core models ────────────────────────────────────────────────────────────────
from .core import (
    ReferralSettings,
    ReferralLink,
    ReferralEarning,
)

# ── Tree models ────────────────────────────────────────────────────────────────
from .tree import (
    ReferralRelationship,
    ReferralTree,
    ReferralTreeSnapshot,
    ReferralLevel,
    ReferralCode,
)

# ── Commission models ──────────────────────────────────────────────────────────
from .commission import (
    CommissionRule,
    CommissionLog,
    CommissionPayout,
    CommissionHold,
    CommissionClawback,
)

# ── Campaign models ────────────────────────────────────────────────────────────
from .campaign import (
    ReferralCampaign,
    ReferralBonus,
    ReferralBonusClaim,
    ReferralContest,
    ReferralReward,
    ContestEntry,
)

# ── Fraud models ───────────────────────────────────────────────────────────────
from .fraud import (
    ReferralFraudRule,
    ReferralFraudLog,
    ReferralBlacklist,
    SuspiciousReferral,
)

# ── Analytics models ───────────────────────────────────────────────────────────
from .analytics import (
    ReferralInsight,
    ReferralConversionRate,
    TopReferrer,
    ReferralLTV,
)


# ── Advanced / World-class models ───────────────────────────────────────────
from .advanced import (
    ReferralSubID,
    GeoCommissionRate,
    CommissionExpiryRule,
    ReferralCommissionExpiry,
    DoubleSidedBonusConfig,
    ReferralAttributionConfig,
    ReferralEmailInvitation,
    ReferralSocialShare,
    ReferralQRCode,
    UserPayoutPreference,
    RecurringCommissionLog,
)


# ── World-Class Extra Models ───────────────────────────────────────────────────
from .world_class import (
    ViralCoefficient,
    ReferralStreakBonus,
    UserStreakTracker,
    ReferralSurgeBonus,
    CommissionTierProgression,
    UserCommissionTier,
    AffiliateProfile,
    ReferralCreditBalance,
    ReferralCreditTransaction,
)


# ── New world-class additions ──────────────────────────────────────────────────
from .advanced import (
    ReferralUTMSession,
    ReferralCoupon,
    ReferralAttributionTouch,
    ReferralAudienceSegment,
    PrivateCampaignInvite,
    AffiliateCustomField, AffiliateCustomFieldValue,
    PartnerContract, PartnerContractAcceptance,
    ReferralABTest, ReferralABTestVariant,
    ReferralRewardCatalog,
    CommissionSplitRule,
    AffiliateTaxInfo,
    MassPayoutBatch, MassPayoutBatchItem,
    CCPARequest,
    ReferralCustomDomain,
    VPNDetectionLog,
)

__all__ = [
    'Referral', 'ReferralChain', 'ReferralLeaderboard',
    'ReferralSettings', 'ReferralLink', 'ReferralEarning',
    'ReferralRelationship', 'ReferralTree', 'ReferralTreeSnapshot',
    'ReferralLevel', 'ReferralCode',
    'CommissionRule', 'CommissionLog', 'CommissionPayout',
    'CommissionHold', 'CommissionClawback',
    'ReferralCampaign', 'ReferralBonus', 'ReferralBonusClaim',
    'ReferralContest', 'ReferralReward', 'ContestEntry',
    'ReferralFraudRule', 'ReferralFraudLog', 'ReferralBlacklist',
    'SuspiciousReferral',
    'ReferralInsight', 'ReferralConversionRate', 'TopReferrer', 'ReferralLTV',
]