# api/djoyalty/services/__init__.py
"""
Djoyalty Services package — all business logic.
  DjoyaltyService  : Main facade (entry point)
  points/          : PointsEngine, Ledger, Expiry, Transfer, Conversion, Reservation, Adjustment, WalletBridge
  tiers/           : TierEvaluation, TierUpgrade, TierDowngrade, TierBenefit
  earn/            : EarnRuleEngine, EarnRuleEvaluator, BonusEvent, ReferralPoints
  redemption/      : Redemption, RedemptionApproval, Voucher, GiftCard, RewardCatalog
  engagement/      : Streak, Badge, Challenge, Milestone, Leaderboard
  advanced/        : Campaign, LoyaltyFraud, SubscriptionLoyalty, Insight
"""
from .DjoyaltyService import DjoyaltyService

__all__ = ['DjoyaltyService']
