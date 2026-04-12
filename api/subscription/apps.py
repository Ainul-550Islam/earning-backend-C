"""apps.py – AppConfig for the subscription module."""
from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SubscriptionConfig(AppConfig):
    name = 'api.subscription'
    label = "subscription"
    verbose_name = _("Subscriptions & Billing")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """
        Connect signal receivers.
        Called once when Django finishes loading apps.
        Import receivers here (not at module level) to avoid circular imports.
        """
        from . import receivers  # noqa: F401 – registers all receiver functions
        from .signals import (
            subscription_activated,
            subscription_cancelled,
            subscription_expired,
            subscription_renewed,
            payment_succeeded,
            payment_failed,
            trial_ending_soon,
        )

        subscription_activated.connect(
            receivers.on_subscription_activated,
            dispatch_uid="subscription.on_subscription_activated",
        )
        subscription_cancelled.connect(
            receivers.on_subscription_cancelled,
            dispatch_uid="subscription.on_subscription_cancelled",
        )
        subscription_expired.connect(
            receivers.on_subscription_expired,
            dispatch_uid="subscription.on_subscription_expired",
        )
        subscription_renewed.connect(
            receivers.on_subscription_renewed,
            dispatch_uid="subscription.on_subscription_renewed",
        )
        payment_succeeded.connect(
            receivers.on_payment_succeeded,
            dispatch_uid="subscription.on_payment_succeeded",
        )
        payment_failed.connect(
            receivers.on_payment_failed,
            dispatch_uid="subscription.on_payment_failed",
        )
        trial_ending_soon.connect(
            receivers.on_trial_ending_soon,
            dispatch_uid="subscription.on_trial_ending_soon",
        )
        try:
            from api.subscription.admin import _force_register_subscription
            _force_register_subscription()
        except Exception as e:
            pass
