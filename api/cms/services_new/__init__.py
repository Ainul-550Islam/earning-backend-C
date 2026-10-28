# api/cms/services_new/__init__.py
"""
CMS Services Package — complete, accurate export of all service classes.
Class names verified against each service file.
"""

# ── Content / CMS core ────────────────────────────────────────────────────────
from .BlogService            import BlogService
from .PageService            import PageService
from .CMSPublishService      import CMSPublishService
from .CMSCacheService        import CMSCacheService
from .CMSAnalyticsService    import CMSAnalyticsService
from .ContentSearchService   import ContentSearchService
from .ContentCalendarService import ContentCalendarService
from .ContentBlockService    import ContentBlockService
from .VersioningService      import VersioningService
from .RedirectService        import RedirectService

# ── Media ─────────────────────────────────────────────────────────────────────
from .MediaService       import MediaService
from .MediaVariantService import MediaVariantService
from .VideoContentService import VideoContentService

# ── UI / UX ───────────────────────────────────────────────────────────────────
from .PopupService      import PopupService
from .MenuService       import MenuService
from .SEOService        import SEOService
from .FormBuilderService import FormBuilderService

# ── User / Profile — actual class name is ProfileSurveyManager ───────────────
from .ProfileSurveyService import ProfileSurveyManager as ProfileSurveyService
from .UserSegmentService   import UserSegmentService
from .WithdrawalService    import WithdrawalService, SiteConfigService, UserProfileService

# ── Gamification / Rewards ────────────────────────────────────────────────────
from .SurveyRewardService    import SurveyRewardService
from .SurveyAnalyticsService import SurveyAnalyticsService
from .LeaderboardService     import LeaderboardService, StreakService
from .ReferralService        import ReferralService
from .QuizService            import QuizService

# ── Real-time / Async ─────────────────────────────────────────────────────────
from .RealTimeOfferService import (
    RealTimeOfferWebSocketService     as RealTimeOfferService,
    RealTimeOfferNotificationService,
    RealTimeOfferAnalyticsService,
)
from .ZeroHoursSession import ZeroHoursSession as ZeroHoursSessionService

# ── Monetisation / CPAlead ────────────────────────────────────────────────────
from .CPALeadService   import (
    CPALeadService,
    FraudDetectionService,
    EarningCapService,
    VirtualCurrencyService,
)
from .RTBService       import RTBService
from .SmartLinkService import SmartLinkService

# ── A/B Testing — actual class names are ABTestingManager / ABTestingAnalytics ─
from .ABTestingService import (
    ABTestingManager   as ABTestingService,
    ABTestingAnalytics,
)

# ── Notifications ─────────────────────────────────────────────────────────────
from .NotificationService import NotificationService

# ── Task Management ───────────────────────────────────────────────────────────
from .TaskManagementService import (
    TaskManagementService,
    TaskScheduler,
    TaskMonitor,
)

# ── Misc helpers — actual class names verified ────────────────────────────────
from .MiscModelService import (
    BannerRewardService,
    BlockDefinitionService  as BlockService,        # alias used by CMSOperationsViewSet
    CommentReactionService,
    ContentPermissionService,
    FormFieldService,
    LandingPageService,
    PermissionAuditService,
    QuizQuestionService,
    SurveyQuestionService,
    VideoGenerationService,
    APIKeyService,
    UserSessionService,
)

from .WorkflowService import WorkflowService

__all__ = [
    # Content core
    'BlogService', 'PageService', 'CMSPublishService', 'CMSCacheService',
    'CMSAnalyticsService', 'ContentSearchService', 'ContentCalendarService',
    'ContentBlockService', 'VersioningService', 'RedirectService',
    # Media
    'MediaService', 'MediaVariantService', 'VideoContentService',
    # UI/UX
    'PopupService', 'MenuService', 'SEOService', 'FormBuilderService',
    # User/Profile
    'ProfileSurveyService', 'UserSegmentService', 'WithdrawalService',
    'SiteConfigService', 'UserProfileService',
    # Gamification
    'SurveyRewardService', 'SurveyAnalyticsService', 'LeaderboardService',
    'StreakService', 'ReferralService', 'QuizService',
    # Real-time
    'RealTimeOfferService', 'RealTimeOfferNotificationService',
    'RealTimeOfferAnalyticsService', 'ZeroHoursSessionService',
    # Monetisation
    'CPALeadService', 'FraudDetectionService', 'EarningCapService',
    'VirtualCurrencyService', 'RTBService', 'SmartLinkService',
    # A/B Testing
    'ABTestingService', 'ABTestingAnalytics',
    # Notifications
    'NotificationService',
    # Task management
    'TaskManagementService', 'TaskScheduler', 'TaskMonitor',
    # Misc
    'BannerRewardService', 'BlockService', 'CommentReactionService',
    'ContentPermissionService', 'FormFieldService', 'LandingPageService',
    'PermissionAuditService', 'QuizQuestionService', 'SurveyQuestionService',
    'VideoGenerationService', 'APIKeyService', 'UserSessionService',
    'WorkflowService',
]
