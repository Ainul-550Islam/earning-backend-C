# api/payment_gateways/refunds/apps.py
# FILE 64 of 257

from django.apps import AppConfig


class RefundsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.refunds'
    label              = 'payment_gateway_refunds'
    verbose_name       = 'Payment Gateway Refunds'

    def ready(self):
        pass  # import signals here if needed
