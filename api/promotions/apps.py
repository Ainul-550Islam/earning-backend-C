# =============================================================================
# api/promotions/apps.py
# =============================================================================

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PromotionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.promotions'
    verbose_name       = _('Promotions')

    def ready(self):
        import api.promotions.admin
        """App ready হলে signals import করো।"""
        import api.promotions.signals  # noqa: F401
