# cms/serializers_new/__init__.py
"""
CMS serializers_new package — exports all serializers.
Updated in v11: added OfferwallSerializer and FinanceSerializer exports.
"""

# ── A/B Testing ───────────────────────────────────────────────────────────────
from .ABTestingSerializer import (
    ABTestSerializer,
    ABTestVariantSerializer,
    ABTestParticipantSerializer,
    ABTestResultSerializer,
)

# ── Quiz ──────────────────────────────────────────────────────────────────────
from .QuizSerializer import (
    QuizTemplateSerializer,
    QuizQuestionSerializer,
    QuizAnswerSerializer,
    QuizResultSerializer,
    QuizAttemptSerializer,
)

# ── Leaderboard & Streaks ─────────────────────────────────────────────────────
from .LeaderboardSerializer import (
    LeaderboardPeriodSerializer,
    LeaderboardEntrySerializer,
    EarningStreakSerializer,
    StreakMilestoneSerializer,
)

# ── Workflow ──────────────────────────────────────────────────────────────────
from .WorkflowSerializer import (
    WorkflowStateSerializer,
    WorkflowTransitionSerializer,
    WorkflowRuleSerializer,
)

# ── SmartLink / Referral / RTB ────────────────────────────────────────────────
from .SmartLinkReferralRTBSerializer import (
    SmartLinkSerializer,
    SmartLinkRuleSerializer,
    SmartLinkClickSerializer,
    ReferralCodeSerializer,
    ReferralRelationshipSerializer,
    ReferralEarningSerializer,
    RTBConfigSerializer,
    RTBAdSlotSerializer,
    RTBBidLogSerializer,
)

# ── RealTime Offers / ContentSchedule / Video ─────────────────────────────────
from .RealTimeOfferSerializer import (
    RealTimeOfferUpdateSerializer,
    UserOfferSubscriptionSerializer,
    OfferUpdateQueueSerializer,
    ContentScheduleSerializer,
    VideoGenerationRequestSerializer,
)

# ── Forms / Blocks / Comments / Payout ───────────────────────────────────────
from .ContentAndFormSerializer import (
    DynamicFormSerializer,
    FormFieldSerializer,
    FormSubmissionSerializer,
    BlockDefinitionSerializer,
    ContentBlockSerializer,
    CommentReactionSerializer,
    PayoutMethodSerializer,
)

# ── CPAlead / Survey Profile ──────────────────────────────────────────────────
from .CPALeadAndSurveySerializer import (
    LockerUnlockSerializer,
    ZeroHoursSessionLogSerializer,
    SurveyCategorySerializer,
    SurveyTemplateSerializer,
    SurveyQuestionSerializer,
    SurveyCompletionSerializer,
    SurveyResponseSerializer,
)

# ── Permissions / BannerReward ────────────────────────────────────────────────
from .PermissionAndRewardSerializer import (
    BannerRewardSerializer,
    ContentPermissionSerializer,
    PermissionAuditLogSerializer,
    PermissionStatsSerializer,
)

# ── Virtual Currency / OfferWall / Locker / Conversion ───────────────────────
from .VirtualCurrencySerializer import (
    VirtualCurrencySerializer,
    UserVirtualBalanceSerializer,
    VirtualTransactionSerializer,
    OfferWallConfigSerializer,
    ContentLockerSerializer,
    ClickLogSerializer,
    ConversionLogSerializer,
    OfferCacheSerializer,
)

# ── Survey Reward / Task Management / User Profile ───────────────────────────
from .SurveyRewardSerializer import (
    SurveyRewardSerializer,
    RewardTransactionSerializer,
    RewardPoolSerializer,
)
from .TaskManagementSerializer import (
    TaskScheduleSerializer,
    TaskExecutionSerializer,
    TaskQueueSerializer,
    TaskLockSerializer,
)
from .UserProfileSerializer import (
    UserProfileSerializer,
)

# ── NEW v11: Offerwall App Serializers ────────────────────────────────────────
from .OfferwallSerializer import (
    OfferSerializer,
    OfferListSerializer,
    OfferDetailSerializer,
    OfferClickSerializer,
    OfferClickCreateSerializer,
    OfferConversionSerializer,
    OfferConversionListSerializer,
    OfferConversionStatusSerializer,
    OfferWallStatsSerializer,
    OfferConversionWebhookSerializer,
)

# ── NEW v11: Finance App Serializers ──────────────────────────────────────────
from .FinanceSerializer import (
    WalletSerializer,
    WalletLockSerializer,
    WalletSummarySerializer,
    TransactionSerializer,
    TransactionListSerializer,
    TransactionCreateSerializer,
    PayoutRequestSerializer,
    PayoutRequestCreateSerializer,
    PayoutRequestListSerializer,
    PayoutRequestStatusSerializer,
    ReconciliationLogSerializer,
    ReconciliationLogListSerializer,
    FinanceDashboardSerializer,
    UserFinanceSummarySerializer,
    BulkTransactionSerializer,
)


__all__ = [
    # A/B Testing
    'ABTestSerializer', 'ABTestVariantSerializer',
    'ABTestParticipantSerializer', 'ABTestResultSerializer',
    # Quiz
    'QuizTemplateSerializer', 'QuizQuestionSerializer', 'QuizAnswerSerializer',
    'QuizResultSerializer', 'QuizAttemptSerializer',
    # Leaderboard
    'LeaderboardPeriodSerializer', 'LeaderboardEntrySerializer',
    'EarningStreakSerializer', 'StreakMilestoneSerializer',
    # Workflow
    'WorkflowStateSerializer', 'WorkflowTransitionSerializer', 'WorkflowRuleSerializer',
    # SmartLink
    'SmartLinkSerializer', 'SmartLinkRuleSerializer', 'SmartLinkClickSerializer',
    # Referral
    'ReferralCodeSerializer', 'ReferralRelationshipSerializer', 'ReferralEarningSerializer',
    # RTB
    'RTBConfigSerializer', 'RTBAdSlotSerializer', 'RTBBidLogSerializer',
    # RealTime Offers
    'RealTimeOfferUpdateSerializer', 'UserOfferSubscriptionSerializer', 'OfferUpdateQueueSerializer',
    # Content & Schedule
    'ContentScheduleSerializer', 'VideoGenerationRequestSerializer',
    # Forms / Blocks / Comments / Payout
    'DynamicFormSerializer', 'FormFieldSerializer', 'FormSubmissionSerializer',
    'BlockDefinitionSerializer', 'ContentBlockSerializer',
    'CommentReactionSerializer', 'PayoutMethodSerializer',
    # CPAlead / Survey
    'LockerUnlockSerializer', 'ZeroHoursSessionLogSerializer',
    'SurveyCategorySerializer', 'SurveyTemplateSerializer', 'SurveyQuestionSerializer',
    'SurveyCompletionSerializer', 'SurveyResponseSerializer',
    # Permissions / BannerReward
    'BannerRewardSerializer', 'ContentPermissionSerializer',
    'PermissionAuditLogSerializer', 'PermissionStatsSerializer',
    # Virtual Currency / OfferWall
    'VirtualCurrencySerializer', 'UserVirtualBalanceSerializer', 'VirtualTransactionSerializer',
    'OfferWallConfigSerializer', 'ContentLockerSerializer',
    'ClickLogSerializer', 'ConversionLogSerializer', 'OfferCacheSerializer',
    # Survey Reward
    'SurveyRewardSerializer', 'RewardTransactionSerializer', 'RewardPoolSerializer',
    # Task Management
    'TaskScheduleSerializer', 'TaskExecutionSerializer', 'TaskQueueSerializer', 'TaskLockSerializer',
    # User Profile
    'UserProfileSerializer',
    # ── NEW v11: Offerwall ──
    'OfferSerializer', 'OfferListSerializer', 'OfferDetailSerializer',
    'OfferClickSerializer', 'OfferClickCreateSerializer',
    'OfferConversionSerializer', 'OfferConversionListSerializer',
    'OfferConversionStatusSerializer', 'OfferWallStatsSerializer',
    'OfferConversionWebhookSerializer',
    # ── NEW v11: Finance ──
    'WalletSerializer', 'WalletLockSerializer', 'WalletSummarySerializer',
    'TransactionSerializer', 'TransactionListSerializer', 'TransactionCreateSerializer',
    'PayoutRequestSerializer', 'PayoutRequestCreateSerializer',
    'PayoutRequestListSerializer', 'PayoutRequestStatusSerializer',
    'ReconciliationLogSerializer', 'ReconciliationLogListSerializer',
    'FinanceDashboardSerializer', 'UserFinanceSummarySerializer', 'BulkTransactionSerializer',
]
