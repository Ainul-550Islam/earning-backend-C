# api/djoyalty/integrations/__init__.py
"""
Djoyalty Integrations Package -- UPDATED।

FIX: All concrete adapter classes (BkashIntegration, NagadIntegration, etc.)
did NOT inherit from their abstract base classes (PaymentAdapter, SMSAdapter,
PushAdapter)। This broke the Adapter pattern and made type checking useless।

Resolution: Each concrete class now inherits from the correct abstract port。
See individual files for the inheritance fix।

Available integrations:
  bKash   -> BkashIntegration(PaymentAdapter)
  Nagad   -> NagadIntegration(PaymentAdapter)
  SSL     -> SSLCommerzIntegration(PaymentAdapter)
  FCM     -> FCMPushIntegration(PushAdapter)
  SMS     -> SMSIntegration(SMSAdapter)
"""
from .bkash import BkashIntegration
from .nagad import NagadIntegration
from .sslcommerz import SSLCommerzIntegration
from .fcm import FCMPushIntegration
from .sms import SMSIntegration

# ─── Adapter Registration ─────────────────────────────────────────────────────
# Register with integration_system's registry on import।

def register_all():
    """Register all concrete adapters with the IntegrationRegistry."""
    try:
        from ..integration_system.integ_registry import registry
        from ..integration_system.integ_adapter import PaymentAdapter, SMSAdapter, PushAdapter

        # Verify inheritance before registering (FIX: was not checked before)
        for name, cls, base in [
            ('bkash',      BkashIntegration,       PaymentAdapter),
            ('nagad',      NagadIntegration,        PaymentAdapter),
            ('sslcommerz', SSLCommerzIntegration,   PaymentAdapter),
            ('fcm',        FCMPushIntegration,       PushAdapter),
            ('sms',        SMSIntegration,           SMSAdapter),
        ]:
            if not issubclass(cls, base):
                import warnings
                warnings.warn(
                    f'FIX NEEDED: {cls.__name__} does not inherit from '
                    f'{base.__name__}. Adapter pattern broken.',
                    stacklevel=2,
                )
            registry.register(name, cls)
    except Exception:
        pass  # Registry not available in test environment -- skip silently


__all__ = [
    'BkashIntegration',
    'NagadIntegration',
    'SSLCommerzIntegration',
    'FCMPushIntegration',
    'SMSIntegration',
    'register_all',
]
