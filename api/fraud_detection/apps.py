# api/fraud_detection/apps.py
from django.apps import AppConfig

class FraudDetectionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.fraud_detection'
    label = 'fraud_detection'
    verbose_name = 'Fraud Detection Management'  # ✅ emoji removed

    def ready(self):
        """Initialize fraud detection app"""
        try:
            import api.fraud_detection.signals
            print("[OK] Fraud Detection signals loaded")
        except ImportError:
            pass

        try:
            from django.contrib import admin
            from .models import (
                FraudRule, FraudAttempt, FraudPattern, UserRiskProfile,
                DeviceFingerprint, IPReputation, FraudAlert, OfferCompletion
            )

            print("[LOADING] Checking fraud detection admin registration...")

            # ✅ FIX: Only import classes that exist in fraud_detection/admin.py
            try:
                from .admin import (
                    FraudRuleAdmin, FraudAttemptAdmin,
                    UserRiskProfileAdmin, IPReputationAdmin,
                )

                models_to_register = [
                    (FraudRule, FraudRuleAdmin),
                    (FraudAttempt, FraudAttemptAdmin),
                    (UserRiskProfile, UserRiskProfileAdmin),
                    (IPReputation, IPReputationAdmin),
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

            except ImportError as e:
                print(f"[WARN] Could not import admin classes: {e}")

            # ✅ Remaining models — default ModelAdmin
            for model in [FraudPattern, DeviceFingerprint, FraudAlert, OfferCompletion]:
                if not admin.site.is_registered(model):
                    try:
                        admin.site.register(model)
                        registered += 1
                        print(f"[OK] Registered: {model.__name__} (default)")
                    except Exception as e:
                        print(f"[WARN] Could not register {model.__name__}: {e}")

            print(f"[OK][OK][OK] Fraud detection models registered")

        except Exception as e:
            print(f"[WARN] Fraud Detection admin registration error: {e}")