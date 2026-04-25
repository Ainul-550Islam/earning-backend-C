# api/payment_gateways/referral/apps.py
from django.apps import AppConfig

class ReferralConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.referral'
    verbose_name       = 'Referral Program'
    label              = 'payment_gateways_referral'
