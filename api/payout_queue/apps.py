"""Payout Queue AppConfig"""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PayoutQueueConfig(AppConfig):
    name = "api.payout_queue"
    label = "payout_queue"
    verbose_name = _("Payout Queue")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        try:
            from . import receivers  # noqa: F401
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error(
                "PayoutQueueConfig.ready(): failed to import receivers: %s", exc
            )
