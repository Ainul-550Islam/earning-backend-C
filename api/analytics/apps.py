# api/analytics/apps.py
from django.apps import AppConfig

class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.analytics'
    label = 'analytics'
    verbose_name = '[STATS] Analytics Management'
    
    def ready(self):
        """Initialize analytics app"""
        try:
            import api.analytics.signals
            print("[OK] Analytics signals loaded")
        except ImportError:
            pass
        
        # Force admin registration
        try:
            from django.contrib import admin
            from .models import (
                AlertHistory, AlertRule, AnalyticsEvent, Dashboard,
                FunnelAnalytics, OfferPerformanceAnalytics, RealTimeMetric,
                Report, RetentionAnalytics, RevenueAnalytics, UserAnalytics
            )
            
            print("[LOADING] Checking analytics admin registration...")
            
            try:
                from .admin import (
                    AlertHistoryAdmin, AlertRuleAdmin, AnalyticsEventAdmin,
                    DashboardAdmin, FunnelAnalyticsAdmin, OfferPerformanceAnalyticsAdmin,
                    RealTimeMetricAdmin, ReportAdmin, RetentionAnalyticsAdmin,
                    RevenueAnalyticsAdmin, UserAnalyticsAdmin
                )
                
                models_to_register = [
                    (AlertHistory, AlertHistoryAdmin),
                    (AlertRule, AlertRuleAdmin),
                    (AnalyticsEvent, AnalyticsEventAdmin),
                    (Dashboard, DashboardAdmin),
                    (FunnelAnalytics, FunnelAnalyticsAdmin),
                    (OfferPerformanceAnalytics, OfferPerformanceAnalyticsAdmin),
                    (RealTimeMetric, RealTimeMetricAdmin),
                    (Report, ReportAdmin),
                    (RetentionAnalytics, RetentionAnalyticsAdmin),
                    (RevenueAnalytics, RevenueAnalyticsAdmin),
                    (UserAnalytics, UserAnalyticsAdmin),
                ]
                
                registered = 0
                for model, admin_class in models_to_register:
                    if not admin.site.is_registered(model):
                        admin.site.register(model, admin_class)
                        registered += 1
                        print(f"[OK] Registered: {model.__name__} from apps.py")
                
                if registered > 0:
                    print(f"[OK][OK][OK] {registered} analytics models registered from apps.py")
                else:
                    print("[OK] All analytics models already registered")
                    
            except ImportError as e:
                print(f"[WARN] Could not import admin classes: {e}")
                
        except Exception as e:
            print(f"[WARN] Analytics admin registration error: {e}")
        try:
            from api.analytics.admin import _force_register_analytics
            _force_register_analytics()
        except Exception as e:
            pass
