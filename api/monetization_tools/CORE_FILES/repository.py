"""CORE_FILES/repository.py — Re-exports all repository classes."""
from ..repository import (
    AdCampaignRepository, OfferRepository, OfferCompletionRepository,
    RevenueRepository, SubscriptionRepository, PaymentRepository,
    LeaderboardRepository, ABTestRepository, PostbackRepository,
    PayoutRepository, ReferralRepository, FraudAlertRepository,
    FlashSaleRepository, CouponRepository, SegmentRepository,
)

__all__ = [
    "AdCampaignRepository","OfferRepository","OfferCompletionRepository",
    "RevenueRepository","SubscriptionRepository","PaymentRepository",
    "LeaderboardRepository","ABTestRepository","PostbackRepository",
    "PayoutRepository","ReferralRepository","FraudAlertRepository",
    "FlashSaleRepository","CouponRepository","SegmentRepository",
]
