# api/djoyalty/apps.py
from django.apps import AppConfig

class DjoyaltyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.djoyalty'
    label = 'djoyalty'
    verbose_name = '🎮 Djoyalty Management'

    def ready(self):
        try:
            import api.djoyalty.signals.core_signals
            import api.djoyalty.signals.points_signals
            import api.djoyalty.signals.tier_signals
            import api.djoyalty.signals.earn_signals
            import api.djoyalty.signals.redemption_signals
            import api.djoyalty.signals.badge_signals
            import api.djoyalty.signals.streak_signals
            print('[OK] Djoyalty signals loaded')
        except ImportError as e:
            print(f'[WARN] Djoyalty signals: {e}')

        try:
            from .events.event_handlers import register_default_handlers
            register_default_handlers()
            print('[OK] Djoyalty event handlers registered')
        except Exception as e:
            print(f'[WARN] Event handlers: {e}')

        try:
            from .admin._force_register import force_register_all
            force_register_all()
        except Exception:
            pass
