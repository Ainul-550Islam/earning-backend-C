# api/payment_gateways/smartlink/apps.py
from django.apps import AppConfig

class SmartlinkConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.smartlink'
    verbose_name       = 'SmartLink'
    label              = 'payment_gateways_smartlink'
