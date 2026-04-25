# api/payment_gateways/apps.py
from django.apps import AppConfig


class PaymentGatewaysConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways'
    verbose_name       = 'Payment Gateways — World #1'
    label              = 'payment_gateways'

    def ready(self):
        """Connect all signals and integration adapters on Django startup."""
        # Connect Django signals
        try:
            from api.payment_gateways.receivers import connect_all_receivers
            connect_all_receivers()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'Could not connect receivers: {e}')

        # Connect integration signals
        try:
            from api.payment_gateways.integration_system.integ_signals import connect_model_signals
            connect_model_signals()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'Could not connect integration signals: {e}')

        # Setup all integration adapters (wallet, notifications, fraud, etc.)
        try:
            from api.payment_gateways.integration_system.integ_adapter import IntegrationAdapter
            IntegrationAdapter().setup_all()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'Integration adapter setup failed: {e}')
