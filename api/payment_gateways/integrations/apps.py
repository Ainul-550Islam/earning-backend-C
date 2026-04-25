# api/payment_gateways/integrations/apps.py
from django.apps import AppConfig

class IntegrationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.integrations'
    verbose_name       = '3rd Party Integrations'
    label              = 'payment_gateways_integrations'
