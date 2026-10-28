# api/cms/viewsets_new/__init__.py
"""
CMS ViewSets Package — New API ViewSets v11c
All viewsets re-exported for a single import point.
"""

# ── Profile Survey ────────────────────────────────────────────────────
from .ProfileSurveyViewSet import (
    SurveyCategoryViewSet,
    SurveyTemplateViewSet,
    SurveyQuestionViewSet,
    SurveyCompletionViewSet,
    SurveyResponseViewSet,
)

# ── User Profile & Segmentation ───────────────────────────────────────
from .UserProfileViewSet import (
    UserProfileViewSet,
    UserSegmentViewSet,
)

# ── Survey Reward ─────────────────────────────────────────────────────
from .SurveyRewardViewSet import (
    SurveyRewardViewSet,
    RewardTransactionViewSet,
    RewardPoolViewSet,
)

# ── Task Management ───────────────────────────────────────────────────
from .TaskManagementViewSet import (
    TaskScheduleViewSet,
    TaskExecutionViewSet,
    TaskQueueViewSet,
    TaskLockViewSet,
)

# ── RealTime Offers ───────────────────────────────────────────────────
from .RealTimeOfferViewSet import (
    RealTimeOfferViewSet,
    UserOfferSubscriptionViewSet,
    OfferUpdateQueueViewSet,
    RealTimeOfferUpdateViewSet,
)

# ── A/B Testing ───────────────────────────────────────────────────────
from .ABTestingViewSet import (
    ABTestViewSet,
    ABTestVariantViewSet,
    ABTestParticipantViewSet,
    ABTestResultViewSet,
    ABTestAnalyticsViewSet,
)

# ── Survey Analytics ──────────────────────────────────────────────────
from .SurveyAnalyticsViewSet import SurveyAnalyticsViewSet

# ── NEW v11c: Previously-missing ViewSets ─────────────────────────────
from .MissingModelViewSets import (
    BlogCommentViewSet,
    BlogTagViewSet,
    ContentCommentViewSet,
    MenuItemViewSet,
    NotificationTemplateViewSet,
    PopupRuleViewSet,
    PopupStatViewSet,
)

__all__ = [
    # Profile Survey
    'SurveyCategoryViewSet', 'SurveyTemplateViewSet', 'SurveyQuestionViewSet',
    'SurveyCompletionViewSet', 'SurveyResponseViewSet',
    # User Profile
    'UserProfileViewSet', 'UserSegmentViewSet',
    # Survey Reward
    'SurveyRewardViewSet', 'RewardTransactionViewSet', 'RewardPoolViewSet',
    # Task Management
    'TaskScheduleViewSet', 'TaskExecutionViewSet', 'TaskQueueViewSet', 'TaskLockViewSet',
    # RealTime Offers
    'RealTimeOfferViewSet', 'UserOfferSubscriptionViewSet',
    'OfferUpdateQueueViewSet', 'RealTimeOfferUpdateViewSet',
    # A/B Testing
    'ABTestViewSet', 'ABTestVariantViewSet', 'ABTestParticipantViewSet',
    'ABTestResultViewSet', 'ABTestAnalyticsViewSet',
    # CMS Operations
    'BannerRewardViewSet', 'BlockDefinitionViewSet', 'ContentScheduleViewSet',
    'DynamicFormViewSet', 'FormFieldViewSet', 'FormSubmissionViewSet',
    'LeaderboardPeriodViewSet', 'LeaderboardEntryViewSet',
    'EarningStreakViewSet', 'StreakMilestoneViewSet',
    'LockerUnlockViewSet', 'OfferCacheViewSet', 'VirtualTransactionViewSet',
    'ZeroHoursSessionLogViewSet',
    # Survey Analytics
    'SurveyAnalyticsViewSet',
    # Misc Operations
    'QuizQuestionViewSet', 'QuizAnswerViewSet', 'QuizResultViewSet', 'QuizAttemptViewSet',
    'RTBAdSlotViewSet', 'RTBBidLogViewSet',
    'ReferralCodeViewSet', 'ReferralRelationshipViewSet', 'ReferralEarningViewSet',
    'SmartLinkRuleViewSet', 'SmartLinkClickViewSet', 'VideoGenerationRequestViewSet',
    'WorkflowRuleViewSet', 'WorkflowStateViewSet', 'WorkflowTransitionViewSet',
    'PermissionAuditLogViewSet', 'PermissionStatsViewSet',
    # CMS Publish/Cache/Calendar
    'CMSPublishViewSet', 'CMSCacheViewSet', 'ContentCalendarViewSet', 'MiscModelViewSet',
    # NEW v11c
    'BlogCommentViewSet', 'BlogTagViewSet', 'ContentCommentViewSet',
    'MenuItemViewSet', 'NotificationTemplateViewSet',
    'PopupRuleViewSet', 'PopupStatViewSet',
]
