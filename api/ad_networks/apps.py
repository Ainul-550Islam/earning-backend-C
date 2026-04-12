# api/ad_networks/apps.py
from django.apps import AppConfig

class AdNetworksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.ad_networks'
    label = 'ad_networks'
    verbose_name = '📢 Ad Networks Management'
    
    def ready(self):
        """Initialize ad_networks app"""
        # Import signals
        try:
            import api.ad_networks.signals
            print("[OK] Ad Networks signals loaded")
        except ImportError:
            pass
        
        # Force admin registration
        try:
            from django.contrib import admin
            from .models import (
                AdNetwork, AdNetworkWebhookLog, BlacklistedIP, 
                FraudDetectionRule, KnownBadIP, NetworkStatistic, 
                Offer, OfferCategory, OfferConversion, 
                OfferPerformanceAnalytics, OfferSyncLog, OfferWall,
                SmartOfferRecommendation, UserOfferEngagement, UserOfferLimit
            )
            
            print("[LOADING] Checking ad_networks admin registration...")
            
            # Try to import admin classes
            try:
                from .admin import (
                    AdNetworkAdmin, AdNetworkWebhookLogAdmin, 
                    BlacklistedIPAdmin, FraudDetectionRuleAdmin,
                    KnownBadIPAdmin, NetworkStatisticAdmin, 
                    OfferAdmin, OfferCategoryAdmin, OfferConversionAdmin,
                    OfferPerformanceAnalyticsAdmin, OfferSyncLogAdmin,
                    OfferWallAdmin, SmartOfferRecommendationAdmin,
                    UserOfferEngagementAdmin, UserOfferLimitAdmin
                )
                
                models_to_register = [
                    (AdNetwork, AdNetworkAdmin),
                    (AdNetworkWebhookLog, AdNetworkWebhookLogAdmin),
                    (BlacklistedIP, BlacklistedIPAdmin),
                    (FraudDetectionRule, FraudDetectionRuleAdmin),
                    (KnownBadIP, KnownBadIPAdmin),
                    (NetworkStatistic, NetworkStatisticAdmin),
                    (Offer, OfferAdmin),
                    (OfferCategory, OfferCategoryAdmin),
                    (OfferConversion, OfferConversionAdmin),
                    (OfferPerformanceAnalytics, OfferPerformanceAnalyticsAdmin),
                    (OfferSyncLog, OfferSyncLogAdmin),
                    (OfferWall, OfferWallAdmin),
                    (SmartOfferRecommendation, SmartOfferRecommendationAdmin),
                    (UserOfferEngagement, UserOfferEngagementAdmin),
                    (UserOfferLimit, UserOfferLimitAdmin),
                ]
                
                registered = 0
                for model, admin_class in models_to_register:
                    if not admin.site.is_registered(model):
                        try:
                            admin.site.register(model, admin_class)
                            registered += 1
                            print(f"[OK] Registered: {model.__name__} from apps.py")
                        except Exception as e:
                            print(f"[WARN] Could not register {model.__name__}: {e}")
                
                if registered > 0:
                    print(f"[OK][OK][OK] {registered} ad_networks models registered from apps.py")
                else:
                    print("[OK] All ad_networks models already registered")
                    
            except ImportError as e:
                print(f"[WARN] Could not import admin classes: {e}")
                # Fallback: register without custom admin
                for model in [AdNetwork, AdNetworkWebhookLog, BlacklistedIP, 
                            FraudDetectionRule, KnownBadIP, NetworkStatistic, 
                            Offer, OfferCategory, OfferConversion, 
                            OfferPerformanceAnalytics, OfferSyncLog, OfferWall,
                            SmartOfferRecommendation, UserOfferEngagement, UserOfferLimit]:
                    if not admin.site.is_registered(model):
                        try:
                            admin.site.register(model)
                            print(f"[OK] Registered: {model.__name__} (default)")
                        except Exception as e:
                            print(f"[WARN] Could not register {model.__name__}: {e}")
                
        except Exception as e:
            print(f"[WARN] Ad Networks admin registration error: {e}")
        try:
            from api.ad_networks.admin import _force_register_ad_networks
            _force_register_ad_networks()
        except Exception as e:
            pass
