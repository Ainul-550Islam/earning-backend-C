# api/djoyalty/services/__init__.py
"""
Djoyalty Services package -- all business logic।

FIXED (Audit v2): was missing 16 service exports।
Now exports ALL service classes so that:
  - `from djoyalty.services import GiftCardService` works
  - `from djoyalty.services import VoucherService` works
  - `from djoyalty.services import LeaderboardService` works
  - `from djoyalty.services import PointsTransferService` works
  - `from djoyalty.services import CashoutService` works
  ... and every other service file below।

Service domains:
DRY BASE CLASS (v3):
  DjoyaltyBaseService: All new services should inherit this base class.
  Provides: _ok(), _err(), _err_exc(), _log(), _warn(), _err_log(),
            _get_loyalty_points(), _resolve_tenant()

  Core Facade       : DjoyaltyService, LoyaltyAPIService
  Points            : PointsEngine, PointsExpiryService, PointsReservationService,
                      PointsAdjustmentService, PointsConversionService,
                      PointsLedgerService, PointsTransferService, WalletBridgeService
  Tiers             : TierEvaluationService, TierBenefitService,
                      TierUpgradeService, TierDowngradeService
  Earn              : EarnRuleEngine, EarnRuleEvaluator, ReferralPointsService,
                      BonusEventService
  Redemption        : RedemptionService, RedemptionApprovalService, RewardCatalogService,
                      GiftCardService, VoucherService
  Engagement        : BadgeService, StreakService, ChallengeService, MilestoneService,
                      LeaderboardService
  Gamification      : SpinWheelService, ScratchCardService, LotteryService, QuizService
  Advanced          : AIPersonalizationService, CampaignService, InsightService,
                      LoyaltyFraudService, SubscriptionLoyaltyService
  Notifications     : NotificationService, NotificationTriggerService
  Partner           : PartnerMerchantService, CoalitionEarnService
  Analytics         : LoyaltyAnalyticsService
  Export/Webhooks   : LoyaltyExportService, LoyaltyWebhookService
  Eco/Family        : EcoLoyaltyService, FamilyAccountService, CharityService
  OfferWall/Smart   : OfferWallService, SmartLinkService
  Cashout           : CashoutService
  Receipt           : ReceiptScanService
  QR                : QRCodeService
"""

# ─── Core Facade ──────────────────────────────────────────────────────────────
from .DjoyaltyService import DjoyaltyService

try:
    from .LoyaltyAPIService import LoyaltyAPIService
except ImportError:
    pass

# ─── Points ───────────────────────────────────────────────────────────────────
try:
    from .points.PointsEngine import PointsEngine
    PointsService = PointsEngine   # convenience alias
except ImportError:
    pass

try:
    from .points.PointsExpiryService import PointsExpiryService
except ImportError:
    pass

try:
    from .points.PointsReservationService import PointsReservationService
except ImportError:
    pass

try:
    from .points.WalletBridgeService import WalletBridgeService
except ImportError:
    pass

# ─── Points Extended (AUDIT FIX: were missing from __init__.py) ──────────────
try:
    from .points.PointsAdjustmentService import PointsAdjustmentService
except ImportError:
    pass

try:
    from .points.PointsConversionService import PointsConversionService
except ImportError:
    pass

try:
    from .points.PointsLedgerService import PointsLedgerService
except ImportError:
    pass

try:
    from .points.PointsTransferService import PointsTransferService
except ImportError:
    pass

# ─── Tiers ────────────────────────────────────────────────────────────────────
try:
    from .tiers.TierEvaluationService import TierEvaluationService
    TierService = TierEvaluationService   # convenience alias
except ImportError:
    pass

try:
    from .tiers.TierBenefitService import TierBenefitService
except ImportError:
    pass

# ─── Tiers Extended (AUDIT FIX: were missing from __init__.py) ───────────────
try:
    from .tiers.TierUpgradeService import TierUpgradeService
except ImportError:
    pass

try:
    from .tiers.TierDowngradeService import TierDowngradeService
except ImportError:
    pass

# ─── Earn ─────────────────────────────────────────────────────────────────────
try:
    from .earn.EarnRuleEngine import EarnRuleEngine
    EarnService = EarnRuleEngine   # convenience alias
except ImportError:
    pass

try:
    from .earn.ReferralPointsService import ReferralPointsService
except ImportError:
    pass

# ─── Earn Extended (AUDIT FIX: were missing from __init__.py) ────────────────
try:
    from .earn.BonusEventService import BonusEventService
except ImportError:
    pass

try:
    from .earn.EarnRuleEvaluator import EarnRuleEvaluator
except ImportError:
    pass

# ─── Redemption ───────────────────────────────────────────────────────────────
try:
    from .redemption.RedemptionService import RedemptionService
except ImportError:
    pass

try:
    from .redemption.RedemptionApprovalService import RedemptionApprovalService
except ImportError:
    pass

try:
    from .redemption.RewardCatalogService import RewardCatalogService as _RewardCatalogFromRedemption
except ImportError:
    _RewardCatalogFromRedemption = None

try:
    from .RewardCatalogService import RewardCatalogService
except ImportError:
    if _RewardCatalogFromRedemption is not None:
        RewardCatalogService = _RewardCatalogFromRedemption

# ─── Redemption Extended (AUDIT FIX: were missing from __init__.py) ──────────
try:
    from .redemption.GiftCardService import GiftCardService
except ImportError:
    pass

try:
    from .redemption.VoucherService import VoucherService
except ImportError:
    pass

# ─── Engagement ───────────────────────────────────────────────────────────────
try:
    from .engagement.BadgeService import BadgeService
except ImportError:
    pass

try:
    from .engagement.StreakService import StreakService
except ImportError:
    pass

try:
    from .engagement.ChallengeService import ChallengeService
except ImportError:
    pass

try:
    from .engagement.MilestoneService import MilestoneService
except ImportError:
    pass

# ─── Engagement Extended (AUDIT FIX: LeaderboardService was missing) ─────────
try:
    from .engagement.LeaderboardService import LeaderboardService
except ImportError:
    pass

# ─── Gamification ─────────────────────────────────────────────────────────────
try:
    from .gamification.SpinWheelService import SpinWheelService
except ImportError:
    pass

try:
    from .gamification.ScratchCardService import ScratchCardService
except ImportError:
    pass

try:
    from .gamification.LotteryService import LotteryService
except ImportError:
    pass

# ─── Gamification Extended (AUDIT FIX: QuizService was missing) ──────────────
try:
    from .gamification.QuizService import QuizService
except ImportError:
    pass

# ─── Advanced ─────────────────────────────────────────────────────────────────
try:
    from .AIPersonalizationService import AIPersonalizationService
except ImportError:
    pass

try:
    from .advanced.CampaignService import CampaignService
except ImportError:
    pass

try:
    from .advanced.InsightService import InsightService
except ImportError:
    pass

try:
    from .advanced.LoyaltyFraudService import LoyaltyFraudService
except ImportError:
    pass

try:
    from .advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService
except ImportError:
    pass

# ─── Notifications ────────────────────────────────────────────────────────────
try:
    from .NotificationService import NotificationService
except ImportError:
    pass

try:
    from .NotificationTriggerService import NotificationTriggerService
except ImportError:
    pass

# ─── Partner / Coalition ──────────────────────────────────────────────────────
try:
    from .PartnerMerchantService import PartnerMerchantService
except ImportError:
    pass

try:
    from .CoalitionEarnService import CoalitionEarnService
except ImportError:
    pass

# ─── Analytics ────────────────────────────────────────────────────────────────
try:
    from .LoyaltyAnalyticsService import LoyaltyAnalyticsService
except ImportError:
    pass

# ─── Export / Webhooks ────────────────────────────────────────────────────────
try:
    from .LoyaltyExportService import LoyaltyExportService
except ImportError:
    pass

try:
    from .LoyaltyWebhookService import LoyaltyWebhookService
except ImportError:
    pass

# ─── Eco / Family ─────────────────────────────────────────────────────────────
try:
    from .EcoLoyaltyService import EcoLoyaltyService
except ImportError:
    pass

# ─── Family Account (AUDIT FIX: was missing from __init__.py) ────────────────
try:
    from .FamilyAccountService import FamilyAccountService
except ImportError:
    pass

# ─── Charity (AUDIT FIX: was missing from __init__.py) ───────────────────────
try:
    from .CharityService import CharityService
except ImportError:
    pass

# ─── OfferWall / SmartLink ────────────────────────────────────────────────────
try:
    from .OfferWallService import OfferWallService
except ImportError:
    pass

try:
    from .SmartLinkService import SmartLinkService
except ImportError:
    pass

# ─── Cashout (AUDIT FIX: new CashoutService extracted from viewset) ──────────
try:
    from .CashoutService import CashoutService
except ImportError:
    pass

# ─── Receipt Scan (AUDIT FIX: was missing from __init__.py) ──────────────────
try:
    from .ReceiptScanService import ReceiptScanService
except ImportError:
    pass

# ─── Customer Profile ─────────────────────────────────────────────────────────
try:
    from .CustomerProfileService import CustomerProfileService
except ImportError:
    pass

# ─── QR Code ──────────────────────────────────────────────────────────────────
try:
    from .QRCodeService import QRCodeService
except ImportError:
    pass

# ─── Social / Review ─────────────────────────────────────────────────────────
try:
    from .social.SocialShareService import SocialShareService
except ImportError:
    pass

try:
    from .social.ReviewService import ReviewService
except ImportError:
    pass

# ─── Experience ──────────────────────────────────────────────────────────────
try:
    from .ExperienceService import ExperienceService
except ImportError:
    pass

# ─── notification_service (AUDIT FIX: snake_case legacy -- re-export safely) ──
# This is the snake_case file that was orphaned. We expose its content under
# a legacy alias so existing code importing from it still works.
try:
    from .notification_service import (
        send_push_notification,
        send_sms_notification,
        send_email_notification,
    )
except ImportError:
    pass

# DRY FIX (v3): Base service class — all new services inherit this
from .base import DjoyaltyBaseService

# AUDIT FIX (2.4): AnalyticsService — wraps kpi_tracker, ltv_calculator,
# cohort_analysis. All AnalyticsViewSet actions use this instead of direct imports.
try:
    from .AnalyticsService import AnalyticsService
except ImportError:
    pass
