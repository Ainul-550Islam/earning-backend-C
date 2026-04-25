# api/notifications/apps.py
from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.notifications'
    label = 'notifications'
    verbose_name = '🔔 Notifications Management'
    
    def ready(self):
        """Initialize notifications app"""
        # Import signals
        try:
            import api.notifications.signals
            print("[OK] Notifications signals loaded")
        except ImportError:
            pass
        
        # Force admin registration
        try:
            from django.contrib import admin
            from .models import (
                Notification, NotificationTemplate, NotificationPreference,
                DeviceToken, NotificationCampaign, NotificationAnalytics,
                NotificationRule, NotificationFeedback, NotificationLog, Notice
            )
            
            print("[LOADING] Checking notifications admin registration...")
            registered = 0
            
            # Models list
            models_to_register = [
                Notification,
                NotificationTemplate,
                NotificationPreference,
                DeviceToken,
                NotificationCampaign,
                NotificationAnalytics,
                NotificationRule,
                NotificationFeedback,
                NotificationLog,
                Notice,
            ]
            
            for model in models_to_register:
                if not admin.site.is_registered(model):
                    try:
                        admin.site.register(model)
                        registered += 1
                        print(f"[OK] Registered: {model.__name__} from apps.py")
                    except Exception as e:
                        print(f"[WARN] Could not register {model.__name__}: {e}")
            
            if registered > 0:
                print(f"[OK][OK][OK] {registered} notifications models registered from apps.py")
            else:
                print("[OK] All notifications models already registered")
                
        except Exception as e:
            print(f"[WARN] Notifications admin registration error: {e}")
        try:
            from api.notifications.admin import _force_register_notifications
            _force_register_notifications()
        except Exception as e:
            pass
