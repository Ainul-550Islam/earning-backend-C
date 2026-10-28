# api/referral/models.py
# Backward-compatible flat models.py
# ALL model classes are imported from models/ package
# Other modules should import from here:
#   from api.referral.models import Referral, CommissionLog, ...
# ============================================================

# ── Legacy models (0001 + 0002 migrations — backward compat) ─────────────────
from api.referral.models_legacy import (
    Referral,
    ReferralChain,
    ReferralEarning,
    ReferralLeaderboard,
    ReferralSettings,
)

# ── Core new models (0003_new_models migration) ───────────────────────────────
from api.referral.models.core import (
    ReferralCode,
    ReferralLink,
    ReferralRelationship,
    ReferralLevel,
)

from api.referral.models.tree import (
    ReferralTree,
    ReferralTreeSnapshot,
)

from api.referral.models.commission import (
    CommissionRule,
    CommissionLog,
    CommissionPayout,
    CommissionHold,
    CommissionClawback,
)

from api.referral.models.campaign import (
    ReferralCampaign,
    ReferralBonus,
    ReferralBonusClaim,
    ReferralContest,
    ReferralReward,
    ContestEntry,
)

from api.referral.models.fraud import (
    ReferralFraudRule,
    ReferralFraudLog,
    ReferralBlacklist,
    SuspiciousReferral,
)

from api.referral.models.analytics import (
    ReferralInsight,
    ReferralConversionRate,
    TopReferrer,
    ReferralLTV,
)

# ── World-class models (0004_world_class_models migration) ────────────────────
from api.referral.models.world_class import (
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

# ── Advanced models (0005_advanced_models migration) ─────────────────────────
from api.referral.models.advanced import (
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

# ── Public API ────────────────────────────────────────────────────────────────
__all__ = [
    # Legacy
    'Referral', 'ReferralChain', 'ReferralEarning',
    'ReferralLeaderboard', 'ReferralSettings',

    # Core
    'ReferralCode', 'ReferralLink', 'ReferralRelationship', 'ReferralLevel',
    'ReferralTree', 'ReferralTreeSnapshot',

    # Commission
    'CommissionRule', 'CommissionLog', 'CommissionPayout',
    'CommissionHold', 'CommissionClawback',

    # Campaign
    'ReferralCampaign', 'ReferralBonus', 'ReferralBonusClaim',
    'ReferralContest', 'ReferralReward', 'ContestEntry',

    # Fraud
    'ReferralFraudRule', 'ReferralFraudLog',
    'ReferralBlacklist', 'SuspiciousReferral',

    # Analytics
    'ReferralInsight', 'ReferralConversionRate', 'TopReferrer', 'ReferralLTV',

    # World-class
    'ViralCoefficient',
    'ReferralStreakBonus', 'UserStreakTracker',
    'ReferralSurgeBonus',
    'CommissionTierProgression', 'UserCommissionTier',
    'AffiliateProfile',
    'ReferralCreditBalance', 'ReferralCreditTransaction',

    # Advanced
    'ReferralSubID', 'GeoCommissionRate',
    'CommissionExpiryRule', 'ReferralCommissionExpiry',
    'DoubleSidedBonusConfig', 'ReferralAttributionConfig',
    'ReferralEmailInvitation', 'ReferralSocialShare',
    'ReferralQRCode', 'UserPayoutPreference', 'RecurringCommissionLog',
]