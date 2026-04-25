"""
Advertiser Portal Serializers — auto-exports whatever serializer files exist.
"""

try:
    from .advertiser import (
        AdvertiserSerializer,
        AdvertiserProfileSerializer,
        AdvertiserVerificationSerializer,
        AdvertiserAgreementSerializer,
    )
except ImportError:
    AdvertiserSerializer = None
    AdvertiserProfileSerializer = None
    AdvertiserVerificationSerializer = None
    AdvertiserAgreementSerializer = None

try:
    from .campaign import (
        AdCampaignSerializer,
        CampaignCreativeSerializer,
        CampaignTargetingSerializer,
        CampaignBidSerializer,
        CampaignScheduleSerializer,
    )
except ImportError:
    AdCampaignSerializer = CampaignCreativeSerializer = CampaignTargetingSerializer = None
    CampaignBidSerializer = CampaignScheduleSerializer = None

try:
    from .offer import (
        AdvertiserOfferSerializer,
        OfferRequirementSerializer,
        OfferCreativeSerializer,
        OfferBlacklistSerializer,
    )
except ImportError:
    AdvertiserOfferSerializer = OfferRequirementSerializer = None
    OfferCreativeSerializer = OfferBlacklistSerializer = None

try:
    from .tracking import (
        TrackingPixelSerializer,
        S2SPostbackSerializer,
        ConversionSerializer,
        ConversionEventSerializer,
        TrackingDomainSerializer,
    )
except ImportError:
    TrackingPixelSerializer = S2SPostbackSerializer = ConversionSerializer = None
    ConversionEventSerializer = TrackingDomainSerializer = None

try:
    from .billing import (
        AdvertiserWalletSerializer,
        AdvertiserTransactionSerializer,
        AdvertiserInvoiceSerializer,
        AdvertiserDepositSerializer,
        CampaignSpendSerializer,
        BillingAlertSerializer,
    )
except ImportError:
    AdvertiserWalletSerializer = AdvertiserTransactionSerializer = None
    AdvertiserInvoiceSerializer = AdvertiserDepositSerializer = None
    CampaignSpendSerializer = BillingAlertSerializer = None

try:
    from .reporting import (
        AdvertiserReportSerializer,
        CampaignReportSerializer,
        PublisherBreakdownSerializer,
        GeoBreakdownSerializer,
        CreativePerformanceSerializer,
    )
except ImportError:
    AdvertiserReportSerializer = CampaignReportSerializer = None
    PublisherBreakdownSerializer = GeoBreakdownSerializer = CreativePerformanceSerializer = None

try:
    from .fraud_protection import (
        ConversionQualityScoreSerializer,
        AdvertiserFraudConfigSerializer,
        InvalidClickLogSerializer,
        ClickFraudSignalSerializer,
        OfferQualityScoreSerializer,
        RoutingBlacklistSerializer,
    )
except ImportError:
    try:
        from .fraud import (
            ConversionQualityScoreSerializer,
            AdvertiserFraudConfigSerializer,
            InvalidClickLogSerializer,
            ClickFraudSignalSerializer,
            OfferQualityScoreSerializer,
            RoutingBlacklistSerializer,
        )
    except ImportError:
        ConversionQualityScoreSerializer = AdvertiserFraudConfigSerializer = None
        InvalidClickLogSerializer = ClickFraudSignalSerializer = None
        OfferQualityScoreSerializer = RoutingBlacklistSerializer = None

try:
    from .notification import (
        AdvertiserNotificationSerializer,
        AdvertiserAlertSerializer,
        NotificationTemplateSerializer,
    )
except ImportError:
    AdvertiserNotificationSerializer = AdvertiserAlertSerializer = NotificationTemplateSerializer = None

try:
    from .ml import (
        UserJourneyStepSerializer,
        NetworkPerformanceCacheSerializer,
        MLModelSerializer,
        MLPredictionSerializer,
    )
except ImportError:
    UserJourneyStepSerializer = NetworkPerformanceCacheSerializer = None
    MLModelSerializer = MLPredictionSerializer = None
