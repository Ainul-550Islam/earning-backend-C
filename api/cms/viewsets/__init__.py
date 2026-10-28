# api/cms/viewsets/__init__.py
"""
CMS ViewSets Package — All 16 ViewSets
"""
# ── Fixed/Extended existing ViewSets ──
from .PageViewSet import PageViewSet
from .BannerViewSet import BannerViewSet
from .SiteContentViewSet import SiteContentViewSet, SiteAnalyticsViewSet

# ── New Blog ViewSets ──
from .BlogPostViewSet import BlogPostViewSet, BlogCategoryViewSet

# ── New Media ViewSets ──
from .MediaFileViewSet import MediaFileViewSet, MediaFolderViewSet

# ── New Popup ViewSet ──
from .PopupViewSet import PopupViewSet

# ── New Menu / SEO / Search / Public ViewSets ──
from .MenuAndSEOViewSets import (
    MenuViewSet,
    LandingSectionViewSet,
    SEOConfigViewSet,
    SitemapViewSet,
    Redirect301ViewSet,
    RobotsConfigViewSet,
    CMSSearchViewSet,
    PublicCMSViewSet,
)


# ── Extra CPAlead ViewSets ───────────────────────────────────────
from .ExtrasViewSets import (
    ConversionLogViewSet,
    AuditLogViewSet,
    OfferWallViewSet,
    ContentLockerViewSet,
    NotificationViewSet,
    AnnouncementViewSet,
    TestimonialViewSet,
    SocialLinkViewSet,
    UserInteractionViewSet,
    CPALeadWebhookView,
    EarningCapViewSet,
    EmailTemplateViewSet,
    CPALeadConfigViewSet,
)

__all__ = [
    # Fixed existing
    'PageViewSet',
    'BannerViewSet',
    'SiteContentViewSet',
    'SiteAnalyticsViewSet',
    # Blog
    'BlogPostViewSet', 'BlogCategoryViewSet',
    # Media
    'MediaFileViewSet', 'MediaFolderViewSet',
    # Popup
    'PopupViewSet',
    # Menu & SEO
    'MenuViewSet', 'LandingSectionViewSet',
    'SEOConfigViewSet', 'SitemapViewSet',
    'Redirect301ViewSet', 'RobotsConfigViewSet',
    # Search & Public
    'CMSSearchViewSet', 'PublicCMSViewSet',
    # CPAlead extras
    'NotificationViewSet', 'AnnouncementViewSet', 'TestimonialViewSet',
    'SocialLinkViewSet', 'UserInteractionViewSet', 'CPALeadWebhookView',
    'EarningCapViewSet', 'EmailTemplateViewSet', 'CPALeadConfigViewSet',
]

from .NewFeatureViewSets import (
    ReferralViewSet, LeaderboardViewSet, QuizViewSet,
    SmartLinkViewSet, WithdrawalViewSet, UserProfileViewSet,
    SiteConfigViewSet, FormBuilderViewSet, ContentBlockViewSet,
)

# ── Floating Module ViewSets — v9 PRODUCTION (previously zero API exposure) ──
from .BusinessLogicViewSet import BusinessLogicViewSet
from .PushNotificationViewSet import PushNotificationViewSet
from .SelectorViewSet import SelectorViewSet
from .InteractorViewSet import InteractorViewSet
from .RepositoryViewSet import RepositoryViewSet
from .AdapterStatusViewSet import AdapterStatusViewSet
