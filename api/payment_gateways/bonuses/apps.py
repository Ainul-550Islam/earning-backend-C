# api/payment_gateways/bonuses/apps.py
from django.apps import AppConfig

class BonusesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.bonuses'
    verbose_name       = 'Performance Bonuses'
    label              = 'payment_gateways_bonuses'
