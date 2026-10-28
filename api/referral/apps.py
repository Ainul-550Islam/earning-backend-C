# api/referral/apps.py
from django.apps import AppConfig


class ReferralConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.referral'
    label = 'referral'
    verbose_name = '👥 Referral Management'

    def ready(self):
        """Initialize referral app when Django starts."""

        # 1. Import signals
        try:
            import api.referral.signals  # noqa: F401
            print("[OK] Referral signals loaded")
        except Exception as e:
            print(f"[WARN] Referral signals error: {e}")

        # 2. Initialize INTEGRATION_SYSTEM
        try:
            from api.referral.INTEGRATION_SYSTEM import initialize
            initialize(app_config=self)
        except Exception as e:
            print(f'[WARN] INTEGRATION_SYSTEM init error: {e}')

        # 3. Force register in custom admin sites
        try:
            from api.referral.admin import _force_register_referral
            _force_register_referral()
        except Exception:
            pass

        # 3. Import admin to trigger all @admin.register decorators
        try:
            import api.referral.admin  # noqa: F401
        except Exception as e:
            print(f"[WARN] Referral admin import error: {e}")