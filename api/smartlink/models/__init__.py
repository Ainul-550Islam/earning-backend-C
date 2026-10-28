from .smartlink import (
    SmartLink,
    SmartLinkDomain,
    SmartLinkGroup,
    SmartLinkRotation,
    SmartLinkFallback,
    SmartLinkTag,
    SmartLinkTagging,
    SmartLinkVersion,
)

# ---------------------------------------------------------------------------
# Mock Offer / Advertiser models — TESTPROJECT-ONLY.
#
# These exist so that a standalone testproject (without the real
# `offer_inventory` / `advertiser_portal` apps installed) can still resolve
# Click.offer / Click.advertiser FKs and let drf-spectacular generate a
# schema.
#
# In the real multi-app codebase, SMARTLINK_OFFER_MODEL / SMARTLINK_ADVERTISER_MODEL
# stay set to 'offer_inventory.Offer' / 'advertiser_portal.Advertiser' (the
# getattr() defaults in models/click.py), so this block is a no-op there —
# `smartlink.Offer` / `smartlink.Advertiser` are NEVER registered and no
# orphan tables/migrations are created.
# ---------------------------------------------------------------------------
from django.conf import settings as _sl_settings

if getattr(_sl_settings, 'SMARTLINK_OFFER_MODEL', 'offer_inventory.Offer') == 'smartlink.Offer':
    from .mock_offer import Offer

if getattr(_sl_settings, 'SMARTLINK_ADVERTISER_MODEL', 'advertiser_portal.Advertiser') == 'smartlink.Advertiser':
    from .mock_advertiser import Advertiser

from .targeting import (
    TargetingRule,
    GeoTargeting,
    DeviceTargeting,
    OSTargeting,
    BrowserTargeting,
    TimeTargeting,
    ISPTargeting,
    LanguageTargeting,
)
from .offer_pool import (
    OfferPool,
    OfferPoolEntry,
    OfferCapTracker,
    OfferBlacklist,
    OfferRotationLog,
    OfferScoreCache,
)
from .click import (
    Click,
    ClickMetadata,
    UniqueClick,
    ClickFraudFlag,
    ClickHeatmap,
    BotClick,
    ClickSession,
)
from .redirect import (
    RedirectLog,
    RedirectRule,
    LandingPage,
    PreLander,
    RedirectChain,
)
from .publisher import (
    PublisherSmartLink,
    PublisherSubID,
    PublisherDomain,
    PublisherAllowList,
    PublisherBlockList,
    SubPublisher,
)
from .analytics import (
    SmartLinkStat,
    SmartLinkDailyStat,
    OfferPerformanceStat,
    GeoPerformanceStat,
    DevicePerformanceStat,
    ABTestResult,
)
from .postback_log import PostbackLog

__all__ = [
    # smartlink.py
    'SmartLink', 'SmartLinkDomain', 'SmartLinkGroup',
    'SmartLinkRotation', 'SmartLinkFallback', 'SmartLinkTag',
    'SmartLinkTagging', 'SmartLinkVersion',
    # targeting.py
    'TargetingRule', 'GeoTargeting', 'DeviceTargeting',
    'OSTargeting', 'BrowserTargeting', 'TimeTargeting',
    'ISPTargeting', 'LanguageTargeting',
    # offer_pool.py
    'OfferPool', 'OfferPoolEntry', 'OfferCapTracker',
    'OfferBlacklist', 'OfferRotationLog', 'OfferScoreCache',
    # click.py
    'Click', 'ClickMetadata', 'UniqueClick', 'ClickFraudFlag',
    'ClickHeatmap', 'BotClick', 'ClickSession',
    # redirect.py
    'RedirectLog', 'RedirectRule', 'LandingPage', 'PreLander', 'RedirectChain',
    # publisher.py
    'PublisherSmartLink', 'PublisherSubID', 'PublisherDomain',
    'PublisherAllowList', 'PublisherBlockList', 'SubPublisher',
    # analytics.py
    'SmartLinkStat', 'SmartLinkDailyStat', 'OfferPerformanceStat',
    'GeoPerformanceStat', 'DevicePerformanceStat', 'ABTestResult',
    # postback_log.py
    'PostbackLog',
    # extensions
    'SmartLinkSchedule',
    'SmartLinkTemplate',
    'PublisherTier',
    # billing
    'PublisherProfile','PublisherAPIKey','PublisherWallet','PayoutRecord','PayoutBatch',
    # webhook
    'WebhookEndpoint','WebhookDeliveryLog',
    # impression
    'ImpressionLog',
]

from .extensions.smartlink_schedule import (
    SmartLinkSchedule,
    SmartLinkTemplate,
    PublisherTier,
)

from .billing import (
    PublisherProfile,
    PublisherAPIKey,
    PublisherWallet,
    PayoutRecord,
    PayoutBatch,
)
from .webhook import (
    WebhookEndpoint,
    WebhookDeliveryLog,
)
from .impression import ImpressionLog
