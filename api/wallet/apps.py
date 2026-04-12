# api/wallet/apps.py
from django.apps import AppConfig
from django.conf import settings

class WalletConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.wallet'
    label = 'wallet'
    verbose_name = 'Wallet Management'

    def ready(self):
        """Initialize wallet app - Connect signals here"""
        try:
            import api.wallet.signals
            print("[OK] Wallet app ready - signals imported")
        except ImportError as e:
            print(f"[ERROR] Failed to import wallet signals: {e}")
        try:
            from api.wallet.admin import _force_register_wallet
            _force_register_wallet()
        except Exception as e:
            pass
