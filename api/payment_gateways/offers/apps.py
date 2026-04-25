# api/payment_gateways/offers/apps.py
from django.apps import AppConfig

class OffersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.offers'
    verbose_name       = 'Offers & Campaigns'
    label              = 'payment_gateways_offers'
