# api/payment_gateways/rtb/apps.py
from django.apps import AppConfig

class RtbConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.rtb'
    verbose_name       = 'Real-Time Bidding'
    label              = 'payment_gateways_rtb'
