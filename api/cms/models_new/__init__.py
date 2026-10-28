# api/cms/models_new/__init__.py
"""
CMS Models Package
Exports all models from submodules for easy import.

FIX (audit): UserProfile was imported from TWO places:
  - models_new/withdrawal.py  (now removed — only PayoutMethod, WithdrawalRequest kept)
  - models_new/user_profile.py (canonical source — kept)
This eliminated a name-collision that caused unpredictable ORM behaviour in production.
"""

# ── Core / existing models (from the monolithic models.py) ──
# These are imported from the original models.py file at the package level.
# The submodule files below add NEW models only.

# ── Blog models ──
from .blog import (
    BlogCategory,
    BlogTag,
    BlogPost,
    BlogComment,
    BlogSEO,
    BlogPostManager,
)

# ── Media models ──
from .media import (
    MediaFolder,
    MediaTag,
    MediaFile,
    MediaVariant,
    MediaUsage,
)

# ── Popup models ──
from .popup import (
    Popup,
    PopupRule,
    PopupStat,
    PopupABTest,
)

# ── Menu models ──
from .menu import (
    Menu,
    MenuItem,
    MenuVisibility,
    LandingSection,
)

# ── SEO models ──
from .seo import (
    SEOConfig,
    Sitemap,
    Redirect301,
    RobotsConfig,
)

__all__ = [
    # Blog
    'BlogCategory', 'BlogTag', 'BlogPost', 'BlogComment', 'BlogSEO', 'BlogPostManager',
    # Media
    'MediaFolder', 'MediaTag', 'MediaFile', 'MediaVariant', 'MediaUsage',
    # Popup
    'Popup', 'PopupRule', 'PopupStat', 'PopupABTest',
    # Menu
    'Menu', 'MenuItem', 'MenuVisibility', 'LandingSection',
    # SEO
    'SEOConfig', 'Sitemap', 'Redirect301', 'RobotsConfig',
]

# ── Extra CPAlead CMS Models ──
from .extras import (
    Announcement,
    Notification,
    NotificationTemplate,
    EmailTemplate,
    Testimonial,
    SocialLink,
    PopupDismissal,
    UserContentInteraction,
    ContentRating,
    CPALeadConfig,
    SiteLayoutConfig,
)

# ── CPAlead Core Models ──
from .cpalead import (
    VirtualCurrency,
    UserVirtualBalance,
    VirtualTransaction,
    OfferWallConfig,
    ContentLocker,
    LockerUnlock,
    ClickLog,
    ConversionLog,
    OfferCache,
)

# ── Referral System ──
from .referral import ReferralCode, ReferralRelationship, ReferralEarning

# ── Leaderboard + Streak ──
from .leaderboard import LeaderboardPeriod, LeaderboardEntry, EarningStreak, StreakMilestone

# ── Quiz Builder ──
from .quiz import QuizTemplate, QuizQuestion, QuizAnswer, QuizResult, QuizAttempt

# ── Approval Workflow ──
from .workflow import WorkflowState, WorkflowTransition, WorkflowRule

# ── SmartLink ──
from .smartlink import SmartLink, SmartLinkRule, SmartLinkClick

# ── Content Blocks (StreamField) ──
from .blocks import ContentBlock, BlockDefinition

# ── FormBuilder ──
from .forms import DynamicForm, FormField, FormSubmission

# ── Site Config + Calendar ──
from .site_config import SiteConfig, ContentSchedule

# ── Withdrawal — FIX: UserProfile removed here; canonical source is user_profile.py ──
# Importing UserProfile from BOTH withdrawal.py and user_profile.py caused a silent
# name-collision where the second import silently overwrote the first in sys.modules,
# leading to inconsistent ORM queries depending on import order at startup.
from .withdrawal import PayoutMethod, WithdrawalRequest

# ── Video Content (CPAlead AI video) ──
from .video import VideoContent, VideoGenerationRequest

# ── RTB Publisher Config ──
from .rtb import RTBConfig, RTBAdSlot, RTBBidLog

# ── Comments / Discussion ──
from .comments import Comment, CommentReaction

# ── API Keys ──
from .api_keys import APIKey

# ── Session Management ──
from .sessions import UserSession

# ── Landing Pages (CPAlead gaming) ──
from .landing_pages import LandingPage

# ── Real-time Offer Updates ──
from .realtime_offers import (
    RealTimeOfferUpdate,
    UserOfferSubscription,
    OfferUpdateQueue,
)

# ── A/B Testing Framework ──
from .ab_testing import (
    ABTest,
    ABTestVariant,
    ABTestParticipant,
    ABTestResult,
)

# ── Profile-based Survey System ──
from .profile_surveys import (
    Survey,
    SurveyCategory,
    SurveyTemplate,
    SurveyQuestion,
    SurveyCompletion,
    SurveyResponse,
)

# ── User Profile and Segmentation — CANONICAL source ──
# UserProfile lives HERE only. Do not re-import from withdrawal.py.
from .user_profile import (
    UserProfile,
    UserSegment,
)

# ── Survey Reward Management ──
from .survey_rewards import (
    SurveyReward,
    RewardTransaction,
    RewardPool,
)

# ── Task Management ──
from .task_management import (
    TaskSchedule,
    TaskExecution,
    TaskQueue,
    TaskLock,
)

# ── Update __all__ list with new models ──
__all__.extend([
    # Extra CPAlead
    'Announcement', 'Notification', 'NotificationTemplate', 'EmailTemplate',
    'Testimonial', 'SocialLink', 'PopupDismissal', 'UserContentInteraction',
    'ContentRating', 'CPALeadConfig', 'SiteLayoutConfig',
    # CPAlead core
    'VirtualCurrency', 'UserVirtualBalance', 'VirtualTransaction',
    'OfferWallConfig', 'ContentLocker', 'LockerUnlock',
    'ClickLog', 'ConversionLog', 'OfferCache',
    # Referral
    'ReferralCode', 'ReferralRelationship', 'ReferralEarning',
    # Leaderboard
    'LeaderboardPeriod', 'LeaderboardEntry', 'EarningStreak', 'StreakMilestone',
    # Quiz
    'QuizTemplate', 'QuizQuestion', 'QuizAnswer', 'QuizResult', 'QuizAttempt',
    # Workflow
    'WorkflowState', 'WorkflowTransition', 'WorkflowRule',
    # SmartLink
    'SmartLink', 'SmartLinkRule', 'SmartLinkClick',
    # Blocks / Forms
    'ContentBlock', 'BlockDefinition',
    'DynamicForm', 'FormField', 'FormSubmission',
    # Site Config
    'SiteConfig', 'ContentSchedule',
    # Withdrawal (UserProfile intentionally NOT here — it's under User Profile section)
    'PayoutMethod', 'WithdrawalRequest',
    # Video
    'VideoContent', 'VideoGenerationRequest',
    # RTB
    'RTBConfig', 'RTBAdSlot', 'RTBBidLog',
    # Comments
    'Comment', 'CommentReaction',
    # API Keys / Sessions / Landing
    'APIKey', 'UserSession', 'LandingPage',
    # Real-time Offer Updates
    'RealTimeOfferUpdate', 'UserOfferSubscription', 'OfferUpdateQueue',
    # A/B Testing Framework
    'ABTest', 'ABTestVariant', 'ABTestParticipant', 'ABTestResult',
    # Profile-based Survey System
    'Survey', 'SurveyCategory', 'SurveyTemplate', 'SurveyQuestion',
    'SurveyCompletion', 'SurveyResponse',
    # User Profile and Segmentation — CANONICAL
    'UserProfile', 'UserSegment',
    # Survey Reward Management
    'SurveyReward', 'RewardTransaction', 'RewardPool',
    # Task Management
    'TaskSchedule', 'TaskExecution', 'TaskQueue', 'TaskLock',
])
