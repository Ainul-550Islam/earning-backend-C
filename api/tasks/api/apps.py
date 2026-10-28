"""
api/apps.py
API apps configuration for earning backend platform
"""
from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Main API configuration for earning backend platform."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.tasks.api'
    verbose_name = 'API Adapters & Integrations'
    
    def ready(self):
        """Initialize all API adapters and external integrations."""
        try:
            # Initialize API adapters
            import api.adapters.users  # noqa
            import api.adapters.security  # noqa
            import api.adapters.admin_panel  # noqa
            import api.adapters.payment_gateways  # noqa
            import api.adapters.ad_networks  # noqa
            import api.adapters.offerwall  # noqa
            import api.adapters.fraud_detection  # noqa
            import api.adapters.analytics  # noqa
            import api.adapters.referral  # noqa
            import api.adapters.engagement  # noqa
            import api.adapters.notifications  # noqa
            import api.adapters.cms  # noqa
            import api.adapters.support  # noqa
            import api.adapters.alerts  # noqa
            import api.adapters.djoyalty  # noqa
            import api.adapters.wallet  # noqa
            import api.adapters.kyc  # noqa
            import api.adapters.cache  # noqa
            import api.adapters.tasks  # noqa
            import api.adapters.rate_limit  # noqa
            import api.adapters.localization  # noqa
            import api.adapters.audit_logs  # noqa
            import api.adapters.tests  # noqa
            import api.adapters.backup  # noqa
            import api.adapters.promotions  # noqa
            import api.adapters.subscription  # noqa
            import api.adapters.gamification  # noqa
            import api.adapters.auto_mod  # noqa
            import api.adapters.version_control  # noqa
            import api.adapters.behavior_analytics  # noqa
            import api.adapters.postback  # noqa
            import api.adapters.inventory  # noqa
            import api.adapters.messaging  # noqa
            import api.adapters.payout_queue  # noqa
            import api.adapters.tenants  # noqa
            import api.adapters.webhooks  # noqa
            import api.adapters.marketplace  # noqa
            import api.adapters.postback_engine  # noqa
            import api.adapters.monetization_tools  # noqa
            import api.adapters.publisher_tools  # noqa
            import api.adapters.proxy_intelligence  # noqa
            import api.adapters.advertiser_portal  # noqa
            import api.adapters.offer_inventory  # noqa
            import api.adapters.smartlink  # noqa
            import api.adapters.disaster_recovery  # noqa
            import api.adapters.dr_integration  # noqa
            import api.adapters.ai_engine  # noqa
            import api.adapters.offer_routing  # noqa
            
            # Initialize external API clients
            import api.external.cpalead  # noqa
            import api.external.offer_toro  # noqa
            import api.external.adgate  # noqa
            import api.external.tapjoy  # noqa
            import api.external.fyber  # noqa
            import api.external.admob  # noqa
            import api.external.unity_ads  # noqa
            import api.external.chartboost  # noqa
            import api.external.ironsource  # noqa
            import api.external.kochava  # noqa
            import api.external.applovin  # noqa
            import api.external.vungle  # noqa
            import api.external.adcolony  # noqa
            
            # Initialize payment gateway adapters
            import api.payments.stripe  # noqa
            import api.payments.paypal  # noqa
            import api.payments.square  # noqa
            import api.payments.razorpay  # noqa
            import api.payments.braintree  # noqa
            import api.payments.bitpay  # noqa
            import api.payments.coinbase  # noqa
            import api.payments.crypto_com  # noqa
            import api.payments.wire_transfer  # noqa
            
            # Initialize analytics adapters
            import api.analytics.google_analytics  # noqa
            import api.analytics.mixpanel  # noqa
            import api.analytics.amplitude  # noqa
            import api.analytics.segment  # noqa
            import api.analytics.fullstory  # noqa
            import api.analytics.hotjar  # noqa
            import api.analytics.crazy_egg  # noqa
            import api.analytics.optimizely  # noqa
            import api.analytics.vwo  # noqa
            
        except ImportError as e:
            # Log missing adapters but continue
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"API adapter not available: {e}")
            
        except Exception as e:
            # Log any other errors but continue
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"API adapter initialization error: {e}")


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.users'
    verbose_name = 'Users API'


class SecurityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.security'
    verbose_name = 'Security API'


class AdminPanelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.admin_panel'
    verbose_name = 'Admin Panel API'


class PaymentGatewaysConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.payment_gateways'
    verbose_name = 'Payment Gateways API'


class AdNetworksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.ad_networks'
    verbose_name = 'Ad Networks API'


class OfferwallConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.offerwall'
    verbose_name = 'Offerwall API'


class FraudDetectionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.fraud_detection'
    verbose_name = 'Fraud Detection API'


class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.analytics'
    verbose_name = 'Analytics API'


class ReferralConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.referral'
    verbose_name = 'Referral API'


class EngagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.engagement'
    verbose_name = 'Engagement API'


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.notifications'
    verbose_name = 'Notifications API'


class CmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.cms'
    verbose_name = 'CMS API'


class SupportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.support'
    verbose_name = 'Support API'


class AlertsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.alerts'
    verbose_name = 'Alerts API'


class DjoyaltyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.djoyalty'
    verbose_name = 'Djoyalty API'


class WalletConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.wallet'
    verbose_name = 'Wallet API'


class KycConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.kyc'
    verbose_name = 'KYC API'


class CacheConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.cache'
    verbose_name = 'Cache API'


class TasksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.tasks'
    verbose_name = 'Tasks API'


class RateLimitConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.rate_limit'
    verbose_name = 'Rate Limit API'


class LocalizationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.localization'
    verbose_name = 'Localization API'


class AuditLogsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.audit_logs'
    verbose_name = 'Audit Logs API'


class TestsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.tests'
    verbose_name = 'Tests API'


class BackupConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.backup'
    verbose_name = 'Backup API'


class PromotionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.promotions'
    verbose_name = 'Promotions API'


class SubscriptionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.subscription'
    verbose_name = 'Subscription API'


class GamificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.gamification'
    verbose_name = 'Gamification API'


class AutoModConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.auto_mod'
    verbose_name = 'Auto Moderation API'


class VersionControlConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.version_control'
    verbose_name = 'Version Control API'


class BehaviorAnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.behavior_analytics'
    verbose_name = 'Behavior Analytics API'


class PostbackConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.postback'
    verbose_name = 'Postback API'


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.inventory'
    verbose_name = 'Inventory API'


class MessagingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.messaging'
    verbose_name = 'Messaging API'


class PayoutQueueConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.payout_queue'
    verbose_name = 'Payout Queue API'


class TenantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.tenants'
    verbose_name = 'Tenants API'


class WebhooksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.webhooks'
    verbose_name = 'Webhooks API'


class MarketplaceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.marketplace'
    verbose_name = 'Marketplace API'


class PostbackEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.postback_engine'
    verbose_name = 'Postback Engine API'


class MonetizationToolsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.monetization_tools'
    verbose_name = 'Monetization Tools API'


class PublisherToolsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.publisher_tools'
    verbose_name = 'Publisher Tools API'


class ProxyIntelligenceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.proxy_intelligence'
    verbose_name = 'Proxy Intelligence API'


class AdvertiserPortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.advertiser_portal'
    verbose_name = 'Advertiser Portal API'


class OfferInventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.offer_inventory'
    verbose_name = 'Offer Inventory API'


class SmartlinkConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.smartlink'
    verbose_name = 'Smartlink API'


class DisasterRecoveryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.disaster_recovery'
    verbose_name = 'Disaster Recovery API'


class DrIntegrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.dr_integration'
    verbose_name = 'DR Integration API'


class AiEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.ai_engine'
    verbose_name = 'AI Engine API'


class OfferRoutingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.offer_routing'
    verbose_name = 'Offer Routing API'
