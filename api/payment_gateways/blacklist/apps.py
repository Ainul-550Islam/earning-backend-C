# api/payment_gateways/blacklist/apps.py
from django.apps import AppConfig

class BlacklistConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.blacklist'
    verbose_name       = 'Traffic Blacklist'
    label              = 'payment_gateways_blacklist'
