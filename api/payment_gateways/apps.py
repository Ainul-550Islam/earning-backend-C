# api/payment_gateways/apps.py
from django.apps import AppConfig

class PaymentGatewaysConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.payment_gateways'
    label = 'payment_gateways'
    verbose_name = '💳 Payment Gateways Management'
    
    def ready(self):
        """Initialize payment_gateways app"""
        try:
            import api.payment_gateways.signals
            print("[OK] Payment gateways signals loaded")
        except ImportError:
            pass
        
        # Force admin registration
        try:
            from django.contrib import admin
            from .models import (
                PaymentGateway, PaymentGatewayMethod, GatewayTransaction,
                PayoutRequest, GatewayConfig, Currency, PaymentGatewayWebhookLog
            )
            
            print("[LOADING] Checking payment_gateways admin registration...")
            registered = 0
            
            # Register each model
            model_admin_pairs = [
                (PaymentGateway, 'PaymentGatewayAdmin'),
                (PaymentGatewayMethod, 'PaymentGatewayMethodAdmin'),
                (GatewayTransaction, 'GatewayTransactionAdmin'),
                (PayoutRequest, 'PayoutRequestAdmin'),
                (GatewayConfig, 'GatewayConfigAdmin'),
                (Currency, 'CurrencyAdmin'),
                (PaymentGatewayWebhookLog, 'PaymentGatewayWebhookLogAdmin'),
            ]
            
            for model, admin_name in model_admin_pairs:
                if not admin.site.is_registered(model):
                    try:
                        # Import the admin class dynamically
                        from .admin import globals
                        admin_class = globals().get(admin_name)
                        if admin_class:
                            admin.site.register(model, admin_class)
                        else:
                            admin.site.register(model)
                        registered += 1
                        print(f"[OK] Registered: {model.__name__}")
                    except Exception as e:
                        print(f"[WARN] Could not register {model.__name__}: {e}")
            
            if registered > 0:
                print(f"[OK][OK][OK] {registered} payment_gateways models registered from apps.py")
            else:
                print("[OK] All payment_gateways models already registered")
                
        except Exception as e:
            print(f"[WARN] Payment gateways admin registration error: {e}")
        try:
            from api.payment_gateways.admin import _force_register_payment_gateways
            _force_register_payment_gateways()
        except Exception as e:
            pass
