# api/payment_gateways/locker/apps.py
from django.apps import AppConfig

class LockerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.locker'
    verbose_name       = 'Locker & OfferWall'
    label              = 'payment_gateways_locker'
