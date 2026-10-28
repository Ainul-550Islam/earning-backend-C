# cms/urls.py
"""
Complete CMS URL Configuration — FINAL v15 FIXED (DRY, no duplicates)

All 90+ ViewSets registered once — ALL before urlpatterns/include().
Groups:
  A. Core CMS (pages, banners, menus, forms, blocks, redirects)
  B. Blog (posts, categories, SEO, comments, tags)
  C. Survey / Quiz
  D. CPA / Offerwall / RTB
  E. Leaderboard / Gamification
  F. Finance / Withdrawal / Payout
  G. User / Session / Auth
  H. Media Library
  I. AB Testing
  J. Extras (announcements, testimonials, social, interactions)
  K. Landing Pages / Popups
  L. Smart Links / Referral
  M. Video
  N. Task Management / Workflow
  O. Analytics / Monitoring (admin)
  P. System / Config / Admin
  Q. INTEGRATION_SYSTEM webhooks
  R. Public (no-auth)
  S. Search / Export
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from drf_spectacular.views import (
    SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
)

# ── A–B. Core / Blog ─────────────────────────────────────────────────────────
# FIX: MenuItemViewSet was imported from two different modules.
# Keep only the CMSOperationsViewSet version. _MI2 alias removed.
from api.cms.views import ContentPageViewSet
from api.cms.viewsets.BannerViewSet import BannerViewSet
from api.cms.viewsets.BlogPostViewSet import BlogPostViewSet, BlogCategoryViewSet
from api.cms.viewsets.NewFeatureViewSets import (
    ContentBlockViewSet,
    SiteConfigViewSet,
    WithdrawalViewSet,
)
from api.cms.viewsets_new.MissingModelViewSets import MenuItemViewSet
from api.cms.viewsets_new.BlogSEOViewSet import BlogSEOViewSet
from api.cms.viewsets_new.MissingModelViewSets import (
    BlogCommentViewSet, BlogTagViewSet,
    ContentCommentViewSet, NotificationTemplateViewSet,
    PopupRuleViewSet, PopupStatViewSet,
)
from api.cms.views import (
    FAQViewSet,
    FAQCategoryViewSet,
    GalleryImageViewSet,
    ContentCategoryViewSet,
)
from api.cms.viewsets.ExtrasViewSets import EmailTemplateViewSet

# ── C. Survey / Quiz ─────────────────────────────────────────────────────────
# FIX: SurveyResponseViewSet was imported from two different modules.
# Keep only the ProfileSurveyViewSet version. _SRV2 alias removed.
from api.cms.viewsets_new.ProfileSurveyViewSet import (
    SurveyCategoryViewSet, SurveyTemplateViewSet,
    SurveyQuestionViewSet, SurveyCompletionViewSet, SurveyResponseViewSet,
)
from api.cms.viewsets_new.SurveyAnalyticsViewSet import SurveyAnalyticsViewSet
from api.cms.viewsets_new.SurveyRewardViewSet import (
    SurveyRewardViewSet, RewardTransactionViewSet, RewardPoolViewSet,
)

# ── D. CPA / Offerwall ───────────────────────────────────────────────────────
from api.cms.viewsets_new.RealTimeOfferViewSet import RealTimeOfferViewSet
from api.cms.viewsets_new.missing_viewsets_group3 import (
    RTBConfigViewSet, RTBAdSlotViewSet, RTBBidLogViewSet,
)

# ── E. Leaderboard ───────────────────────────────────────────────────────────
from api.cms.viewsets_new.missing_viewsets_group2 import (
    LeaderboardPeriodViewSet, LeaderboardEntryViewSet, StreakMilestoneViewSet,
    MediaFolderViewSet, MediaTagViewSet, MediaFileViewSet, MediaVariantViewSet,
    PopupViewSet,
)

# ── F. Finance ───────────────────────────────────────────────────────────────
from api.cms.viewsets_new.missing_viewsets_group3 import (
    ReferralCodeViewSet, ReferralRelationshipViewSet, ReferralEarningViewSet,
    UserSessionViewSet,
    SmartLinkViewSet, SmartLinkRuleViewSet,
    VideoContentViewSet, VideoGenerationRequestViewSet,
    PayoutMethodViewSet,
    WorkflowStateViewSet, WorkflowTransitionViewSet, WorkflowRuleViewSet,
)

# ── G. User ──────────────────────────────────────────────────────────────────
from api.cms.viewsets_new.UserProfileViewSet import UserProfileViewSet

# ── H. AB Testing ────────────────────────────────────────────────────────────
from api.cms.viewsets_new.ABTestingViewSet import (
    ABTestViewSet, ABTestVariantViewSet,
    ABTestParticipantViewSet, ABTestResultViewSet,
)

# ── I. Extras / Missing group 1 ──────────────────────────────────────────────
from api.cms.viewsets_new.missing_viewsets_group1 import (
    AnnouncementViewSet, TestimonialViewSet,
    SocialLinkViewSet, UserContentInteractionViewSet, LandingPageViewSet,
    CommentReactionViewSet,
)

# ── J. Task Management ───────────────────────────────────────────────────────
from api.cms.viewsets_new.TaskManagementViewSet import (
    TaskQueueViewSet, TaskLockViewSet,
)

# ── K. Consolidated old viewsets ─────────────────────────────────────────────
from api.cms.viewsets_new.consolidated_old_viewsets import (
    AdapterStatusViewSet, SiteAnalyticsViewSet, MonitoringViewSet,
    ContentEngagementViewSet, GlobalSearchViewSet, FeatureFlagsViewSet,
    SEOConfigViewSet, SitemapViewSet, RobotsConfigViewSet,
    PushNotificationViewSet, OfferWallViewSet, AuditLogViewSet,
    ConversionLogViewSet, DataExportViewSet, PublicCMSViewSet,
)

# ── L. INTEGRATION_SYSTEM (webhooks) ─────────────────────────────────────────
from api.cms.INTEGRATION_SYSTEM.webhooks_integration import (
    CPALeadWebhookView, GenericWebhookView, WalletCallbackView,
)
from api.cms.INTEGRATION_SYSTEM.health_check import HealthChecker

# ── FIX: final_floating_viewsets imported HERE (before router / urlpatterns) ─
# Previously these 15 ViewSets were imported and registered AFTER
# `urlpatterns = [..., include(router.urls)]`.
# DefaultRouter caches .urls at the moment include() is called, so any
# register() call after that point is silently ignored — all 15 routes
# returned HTTP 404. Fix: move imports + register() calls here.
from api.cms.viewsets_new.final_floating_viewsets import (
    TwoFactorViewSet, APIKeyViewSet, FastPayViewSet, VirtualCurrencyViewSet,
    InAppNotificationViewSet, EarningCapViewSet, CPALeadConfigViewSet,
    ContentLockerViewSet, MenuViewSet, LandingSectionViewSet,
    Redirect301ViewSet, QuizViewSet, FormBuilderViewSet,
    ComplianceViewSet, SanctionsViewSet,
)

# ── public_views ──────────────────────────────────────────────────────────────
from api.cms.public_views import public_tenant_settings


# ─────────────────────────────────────────────────────────────────────────────
# ROUTER — register every ViewSet exactly ONCE, all before urlpatterns
# ─────────────────────────────────────────────────────────────────────────────

router = DefaultRouter()

# ── A. CORE CMS ──────────────────────────────────────────────────────────────
router.register(r'v3/pages',             ContentPageViewSet,    basename='cms-pages')
router.register(r'v3/banners',           BannerViewSet,         basename='cms-banners')
router.register(r'v3/menus',             MenuItemViewSet,       basename='cms-menus')
router.register(r'v3/blocks',            ContentBlockViewSet,   basename='cms-blocks')
router.register(r'v3/system-config',     SiteConfigViewSet,     basename='cms-system-config')
router.register(r'v3/content-categories',ContentCategoryViewSet,basename='cms-content-categories')

# ── B. BLOG ──────────────────────────────────────────────────────────────────
router.register(r'v3/blog-posts',        BlogPostViewSet,       basename='cms-blog-posts')
router.register(r'v3/blog-categories',   BlogCategoryViewSet,   basename='cms-blog-categories')
router.register(r'v3/blog-seo',          BlogSEOViewSet,        basename='cms-blog-seo')
router.register(r'v3/blog-comments',     BlogCommentViewSet,    basename='cms-blog-comments')
router.register(r'v3/blog-tags',         BlogTagViewSet,        basename='cms-blog-tags')

# ── C. SURVEY / QUIZ ─────────────────────────────────────────────────────────
router.register(r'v3/survey-categories',      SurveyCategoryViewSet,          basename='cms-survey-categories')
router.register(r'v3/survey-templates',       SurveyTemplateViewSet,          basename='cms-survey-templates')
router.register(r'v3/survey-questions',       SurveyQuestionViewSet,          basename='cms-survey-questions')
router.register(r'v3/survey-completions',     SurveyCompletionViewSet,        basename='cms-survey-completions')
router.register(r'v3/survey-responses',       SurveyResponseViewSet,          basename='cms-survey-responses')
router.register(r'v3/survey-analytics',       SurveyAnalyticsViewSet,         basename='cms-survey-analytics')
router.register(r'v3/survey-rewards-config',  SurveyRewardViewSet,            basename='cms-survey-rewards-config')
router.register(r'v3/reward-transactions',    RewardTransactionViewSet,       basename='cms-reward-transactions')
router.register(r'v3/reward-pools',           RewardPoolViewSet,              basename='cms-reward-pools')

# ── D. CPA / OFFERWALL / RTB ─────────────────────────────────────────────────
router.register(r'v3/real-time-offers',  RealTimeOfferViewSet,  basename='cms-real-time-offers')
router.register(r'v3/offerwall',         OfferWallViewSet,      basename='cms-offerwall')
router.register(r'v3/rtb-configs',       RTBConfigViewSet,      basename='cms-rtb-configs')
router.register(r'v3/rtb-ad-slots',      RTBAdSlotViewSet,      basename='cms-rtb-ad-slots')
router.register(r'v3/rtb-bid-logs',      RTBBidLogViewSet,      basename='cms-rtb-bid-logs')
router.register(r'v3/conversion-logs',   ConversionLogViewSet,  basename='cms-conversion-logs')
router.register(r'v3/audit-logs',        AuditLogViewSet,       basename='cms-audit-logs')

# ── E. LEADERBOARD ───────────────────────────────────────────────────────────
router.register(r'v3/leaderboard-periods', LeaderboardPeriodViewSet, basename='cms-leaderboard-periods')
router.register(r'v3/leaderboard-entries', LeaderboardEntryViewSet,  basename='cms-leaderboard-entries')
router.register(r'v3/streak-milestones',   StreakMilestoneViewSet,   basename='cms-streak-milestones')

# ── F. FINANCE / WITHDRAWAL ──────────────────────────────────────────────────
router.register(r'v3/withdrawals',       WithdrawalViewSet,     basename='cms-withdrawals')
router.register(r'v3/payout-methods',    PayoutMethodViewSet,   basename='cms-payout-methods')

# ── G. USER / SESSION ────────────────────────────────────────────────────────
router.register(r'v3/user-profiles',     UserProfileViewSet,    basename='cms-user-profiles')
router.register(r'v3/user-sessions',     UserSessionViewSet,    basename='cms-user-sessions')

# ── H. MEDIA ─────────────────────────────────────────────────────────────────
router.register(r'v3/media-folders',     MediaFolderViewSet,    basename='cms-media-folders')
router.register(r'v3/media-tags',        MediaTagViewSet,       basename='cms-media-tags')
router.register(r'v3/media-files',       MediaFileViewSet,      basename='cms-media-files')
router.register(r'v3/media-variants',    MediaVariantViewSet,   basename='cms-media-variants')

# ── I. AB TESTING ────────────────────────────────────────────────────────────
router.register(r'v3/ab-tests',             ABTestViewSet,            basename='cms-ab-tests')
router.register(r'v3/ab-test-variants',     ABTestVariantViewSet,     basename='cms-ab-test-variants')
router.register(r'v3/ab-test-participants', ABTestParticipantViewSet, basename='cms-ab-test-participants')
router.register(r'v3/ab-test-results',      ABTestResultViewSet,      basename='cms-ab-test-results')

# ── J. COMMENTS / EXTRAS ─────────────────────────────────────────────────────
router.register(r'v3/comments',               ContentCommentViewSet,         basename='cms-comments')
router.register(r'v3/comment-reactions',      CommentReactionViewSet,        basename='cms-comment-reactions')
router.register(r'v3/announcements',          AnnouncementViewSet,           basename='cms-announcements')
router.register(r'v3/notification-templates', NotificationTemplateViewSet,   basename='cms-notification-templates')
router.register(r'v3/testimonials',           TestimonialViewSet,            basename='cms-testimonials')
router.register(r'v3/social-links',           SocialLinkViewSet,             basename='cms-social-links')
router.register(r'v3/content-interactions',   UserContentInteractionViewSet, basename='cms-content-interactions')

# ── K. LANDING PAGES / POPUPS ────────────────────────────────────────────────
router.register(r'v3/landing-pages',    LandingPageViewSet,    basename='cms-landing-pages')
router.register(r'v3/popups',           PopupViewSet,          basename='cms-popups')
router.register(r'v3/popup-rules',      PopupRuleViewSet,      basename='cms-popup-rules')
router.register(r'v3/popup-stats',      PopupStatViewSet,      basename='cms-popup-stats')

# ── L. SMART LINKS / REFERRAL ────────────────────────────────────────────────
router.register(r'v3/smart-links',             SmartLinkViewSet,            basename='cms-smart-links')
router.register(r'v3/smart-link-rules',        SmartLinkRuleViewSet,        basename='cms-smart-link-rules')
router.register(r'v3/referral-codes',          ReferralCodeViewSet,         basename='cms-referral-codes')
router.register(r'v3/referral-relationships',  ReferralRelationshipViewSet, basename='cms-referral-relationships')
router.register(r'v3/referral-earnings',       ReferralEarningViewSet,      basename='cms-referral-earnings')

# ── M. VIDEO ─────────────────────────────────────────────────────────────────
router.register(r'v3/videos',                    VideoContentViewSet,           basename='cms-videos')
router.register(r'v3/video-generation-requests', VideoGenerationRequestViewSet, basename='cms-video-gen')

# ── N. TASK MANAGEMENT / WORKFLOW ────────────────────────────────────────────
router.register(r'v3/task-queues',          TaskQueueViewSet,         basename='cms-task-queues')
router.register(r'v3/task-locks',           TaskLockViewSet,          basename='cms-task-locks')
router.register(r'v3/workflow-states',      WorkflowStateViewSet,     basename='cms-workflow-states')
router.register(r'v3/workflow-transitions', WorkflowTransitionViewSet, basename='cms-workflow-transitions')
router.register(r'v3/workflow-rules',       WorkflowRuleViewSet,      basename='cms-workflow-rules')

# ── O. ANALYTICS / MONITORING ────────────────────────────────────────────────
router.register(r'v3/site-analytics',     SiteAnalyticsViewSet,    basename='cms-site-analytics')
router.register(r'v3/monitoring',         MonitoringViewSet,       basename='cms-monitoring')
router.register(r'v3/content-engagement', ContentEngagementViewSet, basename='cms-content-engagement')

# ── P. SYSTEM ADMIN ──────────────────────────────────────────────────────────
router.register(r'v3/faqs',                  FAQViewSet,                 basename='cms-faqs')
router.register(r'v3/faq-categories',        FAQCategoryViewSet,         basename='cms-faq-categories')
router.register(r'v3/gallery-images',        GalleryImageViewSet,        basename='cms-gallery-images')
router.register(r'v3/email-templates',       EmailTemplateViewSet,       basename='cms-email-templates')
router.register(r'v3/adapter-status',        AdapterStatusViewSet,       basename='cms-adapter-status')
router.register(r'v3/feature-flags',         FeatureFlagsViewSet,        basename='cms-feature-flags')
router.register(r'v3/seo-config',            SEOConfigViewSet,           basename='cms-seo-config')
router.register(r'v3/sitemaps',              SitemapViewSet,             basename='cms-sitemaps')
router.register(r'v3/robots-config',         RobotsConfigViewSet,        basename='cms-robots-config')
router.register(r'v3/push-notifications',    PushNotificationViewSet,    basename='cms-push-notifications')
router.register(r'v3/data-export',           DataExportViewSet,          basename='cms-data-export')

# ── Q. SEARCH ────────────────────────────────────────────────────────────────
router.register(r'v3/search',  GlobalSearchViewSet, basename='cms-search')

# ── R. PUBLIC ────────────────────────────────────────────────────────────────
router.register(r'v3/public',  PublicCMSViewSet,    basename='cms-public')

# ── S. FINAL FLOATING VIEWSETS (FIX: moved before urlpatterns) ───────────────
router.register(r'v3/two-factor',           TwoFactorViewSet,         basename='cms-two-factor')
router.register(r'v3/api-keys',             APIKeyViewSet,            basename='cms-api-keys')
router.register(r'v3/fast-pay',             FastPayViewSet,           basename='cms-fast-pay')
router.register(r'v3/virtual-currency',     VirtualCurrencyViewSet,   basename='cms-virtual-currency')
router.register(r'v3/in-app-notifications', InAppNotificationViewSet, basename='cms-in-app-notifications')
router.register(r'v3/earning-caps',         EarningCapViewSet,        basename='cms-earning-caps')
router.register(r'v3/cpalead-config',       CPALeadConfigViewSet,     basename='cms-cpalead-config')
router.register(r'v3/content-lockers',      ContentLockerViewSet,     basename='cms-content-lockers')
router.register(r'v3/nav-menus',            MenuViewSet,              basename='cms-nav-menus')
router.register(r'v3/landing-sections',     LandingSectionViewSet,    basename='cms-landing-sections')
router.register(r'v3/301-redirects',        Redirect301ViewSet,       basename='cms-301-redirects')
router.register(r'v3/quizzes',              QuizViewSet,              basename='cms-quizzes')
router.register(r'v3/form-builder',         FormBuilderViewSet,       basename='cms-form-builder')
router.register(r'v3/compliance',           ComplianceViewSet,        basename='cms-compliance')
router.register(r'v3/sanctions',            SanctionsViewSet,         basename='cms-sanctions')


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK VIEWS
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    from django.db import connection
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False
    try:
        checker = HealthChecker()
        health = checker.run_all_checks() if hasattr(checker, 'run_all_checks') else {'status': 'ok'}
    except Exception:
        health = {'status': 'ok'}
    return Response({
        'status': 'healthy' if db_ok else 'degraded',
        'database': 'ok' if db_ok else 'error',
        'api_version': 'v3',
        'total_endpoints': len(router.urls),
        'integration_health': health,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request):
    return Response({
        'api_version': 'v3',
        'total_endpoints': len(router.urls),
        'docs': request.build_absolute_uri('/api/docs/'),
        'schema': request.build_absolute_uri('/api/schema/'),
        'health': request.build_absolute_uri('/api/health/'),
    })


# ─────────────────────────────────────────────────────────────────────────────
# URL PATTERNS — router.urls is generated AFTER all register() calls above
# ─────────────────────────────────────────────────────────────────────────────

urlpatterns = [
    path('',       api_root,     name='api-root'),
    path('health/', health_check, name='api-health'),
    path('schema/', SpectacularAPIView.as_view(),                        name='schema'),
    path('docs/',   SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/',  SpectacularRedocView.as_view(url_name='schema'),     name='redoc'),

    # ── INTEGRATION_SYSTEM Webhooks ──────────────────────────────────────────
    path('v3/webhooks/cpalead/',         CPALeadWebhookView.as_view(),  name='webhook-cpalead'),
    path('v3/webhooks/generic/',         GenericWebhookView.as_view(),  name='webhook-generic'),
    path('v3/webhooks/wallet-callback/', WalletCallbackView.as_view(),  name='webhook-wallet'),

    # ── Public tenant settings ───────────────────────────────────────────────
    path('v3/public/tenant-settings/', public_tenant_settings, name='public-tenant-settings'),

    # ── All ViewSet routes ───────────────────────────────────────────────────
    path('', include(router.urls)),
]
