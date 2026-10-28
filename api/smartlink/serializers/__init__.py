"""
SmartLink Serializers Package
================================
All serializers are imported here for clean cross-viewset access.
"""
from .SmartLinkSerializer import SmartLinkSerializer
from .SmartLinkDetailSerializer import SmartLinkDetailSerializer
from .SmartLinkGroupSerializer import SmartLinkGroupSerializer
from .TargetingRuleSerializer import TargetingRuleSerializer
from .GeoTargetingSerializer import GeoTargetingSerializer
from .DeviceTargetingSerializer import DeviceTargetingSerializer
from .TimeTargetingSerializer import TimeTargetingSerializer
from .OfferPoolSerializer import OfferPoolSerializer
from .OfferPoolEntrySerializer import OfferPoolEntrySerializer
from .ClickSerializer import ClickSerializer
from .ClickMetadataSerializer import ClickMetadataSerializer
from .ClickSessionSerializer import ClickSessionSerializer, ClickSessionListSerializer
from .BotClickSerializer import BotClickSerializer, BotClickSummarySerializer
from .RedirectLogSerializer import RedirectLogSerializer
from .RedirectChainSerializer import RedirectChainSerializer, RedirectChainListSerializer
from .LandingPageSerializer import LandingPageSerializer
from .PreLanderSerializer import PreLanderSerializer
from .SmartLinkStatSerializer import SmartLinkStatSerializer
from .ABTestSerializer import ABTestSerializer
from .ABTestResultSerializer import ABTestResultSerializer
from .DomainSerializer import DomainSerializer
from .PublisherSmartLinkSerializer import PublisherSmartLinkSerializer
from .PublisherAllowListSerializer import (
    PublisherAllowListSerializer,
    PublisherAllowListBulkCreateSerializer,
)
from .PublisherBlockListSerializer import (
    PublisherBlockListSerializer,
    PublisherBlockListBulkSerializer,
)
from .HeatmapSerializer import HeatmapSerializer
from .InsightSerializer import InsightSerializer
from .AdminSerializer import AdminSmartLinkSerializer
from .PublisherAPISerializer import PublisherAPISerializer
from .PostbackLogSerializer import PostbackLogSerializer, PostbackLogCreateSerializer
from .OfferRotationLogSerializer import (
    OfferRotationLogSerializer,
    OfferRotationLogListSerializer,
    OfferRotationSummarySerializer,
)
from .OfferScoreCacheSerializer import OfferScoreCacheSerializer, OfferScoreRankSerializer

# Scheduling / Templates / Tiers
from .SmartLinkScheduleSerializer import (
    SmartLinkScheduleSerializer,
    SmartLinkScheduleListSerializer,
)
from .SmartLinkTemplateSerializer import (
    SmartLinkTemplateSerializer,
    SmartLinkTemplateListSerializer,
    ApplyTemplateSerializer,
)
from .PublisherTierSerializer import (
    PublisherTierSerializer,
    PublisherTierSummarySerializer,
    ManualTierOverrideSerializer,
    TierEvaluationResultSerializer,
)

# Integrations
from .IntegrationConfigSerializer import (
    TikTokIntegrationSerializer,
    SnapchatIntegrationSerializer,
    FacebookPixelIntegrationSerializer,
    GoogleAdsIntegrationSerializer,
    PushNetworkIntegrationSerializer,
    AllIntegrationsSerializer,
    IntegrationTestResultSerializer,
)

# Utility viewset serializers
from .UtilitySerializers import (
    CurrencyConvertSerializer,
    CurrencyConvertResultSerializer,
    CurrencyListSerializer,
    CurrencyRateSerializer,
    GeoIPLookupSerializer,
    GeoIPResultSerializer,
    CacheStatsSerializer,
    WarmupResultSerializer,
    WarmupSingleSerializer,
    RateLimitBanSerializer,
    ManualBanSerializer,
    ManualUnbanSerializer,
    NotificationPreferenceSerializer,
)

# ── New dedicated billing serializers ─────────────────────────────────────────
from .BillingSerializers import (
    APIKeyListSerializer,
    APIKeyCreateSerializer,
    APIKeyCreatedSerializer,
    WebhookEndpointSerializer,
    WebhookDeliveryLogSerializer,
    PublisherProfileSerializer,
    PublisherProfileAdminSerializer,
    PayoutRecordSerializer,
    PayoutRecordListSerializer,
    PayoutBatchSerializer,
    PayoutBatchCreateSerializer,
)

# ── New: SubPublisher referral chain ──────────────────────────────────────────
from .SubPublisherSerializer import (
    SubPublisherReadSerializer,
    SubPublisherCreateSerializer,
    SubPublisherAdminSerializer,
    SubPublisherEarningsSerializer,
)

# ── New: ImpressionLog ────────────────────────────────────────────────────────
from .ImpressionLogSerializer import (
    ImpressionLogSerializer,
    ImpressionLogListSerializer,
    ImpressionSummarySerializer,
    ImpressionCreateSerializer,
)

# ── New: PublisherWallet ──────────────────────────────────────────────────────
from .PublisherWalletSerializer import (
    PublisherWalletSerializer,
    WalletTransactionSerializer,
    WalletSummarySerializer,
)

__all__ = [
    # SmartLink core
    'SmartLinkSerializer', 'SmartLinkDetailSerializer', 'SmartLinkGroupSerializer',
    # Targeting
    'TargetingRuleSerializer', 'GeoTargetingSerializer', 'DeviceTargetingSerializer',
    'TimeTargetingSerializer',
    # Offer pool
    'OfferPoolSerializer', 'OfferPoolEntrySerializer',
    # Clicks
    'ClickSerializer', 'ClickMetadataSerializer',
    'ClickSessionSerializer', 'ClickSessionListSerializer',
    'BotClickSerializer', 'BotClickSummarySerializer',
    # Redirects
    'RedirectLogSerializer',
    'RedirectChainSerializer', 'RedirectChainListSerializer',
    # Landing / pre-lander
    'LandingPageSerializer', 'PreLanderSerializer',
    # Stats / analytics
    'SmartLinkStatSerializer', 'ABTestSerializer', 'ABTestResultSerializer',
    # Publisher
    'PublisherSmartLinkSerializer',
    'PublisherAllowListSerializer', 'PublisherAllowListBulkCreateSerializer',
    'PublisherBlockListSerializer', 'PublisherBlockListBulkSerializer',
    # Domain
    'DomainSerializer',
    # Misc UI
    'HeatmapSerializer', 'InsightSerializer',
    # Admin
    'AdminSmartLinkSerializer',
    # Publisher API
    'PublisherAPISerializer',
    # Postback
    'PostbackLogSerializer', 'PostbackLogCreateSerializer',
    # Rotation & scoring
    'OfferRotationLogSerializer', 'OfferRotationLogListSerializer',
    'OfferRotationSummarySerializer',
    'OfferScoreCacheSerializer', 'OfferScoreRankSerializer',
    # Scheduling / templates / tiers
    'SmartLinkScheduleSerializer', 'SmartLinkScheduleListSerializer',
    'SmartLinkTemplateSerializer', 'SmartLinkTemplateListSerializer',
    'ApplyTemplateSerializer',
    'PublisherTierSerializer', 'PublisherTierSummarySerializer',
    'ManualTierOverrideSerializer', 'TierEvaluationResultSerializer',
    # Integrations
    'TikTokIntegrationSerializer', 'SnapchatIntegrationSerializer',
    'FacebookPixelIntegrationSerializer', 'GoogleAdsIntegrationSerializer',
    'PushNetworkIntegrationSerializer', 'AllIntegrationsSerializer',
    'IntegrationTestResultSerializer',
    # Utility
    'CurrencyConvertSerializer', 'CurrencyConvertResultSerializer',
    'CurrencyListSerializer', 'CurrencyRateSerializer',
    'GeoIPLookupSerializer', 'GeoIPResultSerializer',
    'CacheStatsSerializer', 'WarmupResultSerializer', 'WarmupSingleSerializer',
    'RateLimitBanSerializer', 'ManualBanSerializer', 'ManualUnbanSerializer',
    'NotificationPreferenceSerializer',
    # Billing (dedicated file)
    'APIKeyListSerializer', 'APIKeyCreateSerializer', 'APIKeyCreatedSerializer',
    'WebhookEndpointSerializer', 'WebhookDeliveryLogSerializer',
    'PublisherProfileSerializer', 'PublisherProfileAdminSerializer',
    'PayoutRecordSerializer', 'PayoutRecordListSerializer',
    'PayoutBatchSerializer', 'PayoutBatchCreateSerializer',
    # SubPublisher
    'SubPublisherReadSerializer', 'SubPublisherCreateSerializer',
    'SubPublisherAdminSerializer', 'SubPublisherEarningsSerializer',
    # ImpressionLog
    'ImpressionLogSerializer', 'ImpressionLogListSerializer',
    'ImpressionSummarySerializer', 'ImpressionCreateSerializer',
    # PublisherWallet
    'PublisherWalletSerializer', 'WalletTransactionSerializer', 'WalletSummarySerializer',
]

# ── NEW: Missing model serializers ────────────────────────────────────────────
from .MissingSerializers import (
    RedirectRuleSerializer,
    PublisherSubIDSerializer,
    BrowserTargetingSerializer,
    UniqueClickSerializer,
    ClickFraudFlagSerializer,
    ClickFraudFlagListSerializer,
    SmartLinkDomainSerializer,
    SmartLinkTaggingSerializer,
    OfferPerformanceStatSerializer,
    GeoPerformanceStatSerializer,
    DevicePerformanceStatSerializer,
    OfferCapTrackerSerializer,
    OfferBlacklistSerializer,
)
