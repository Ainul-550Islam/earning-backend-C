# api/payment_gateways/tracking/apps.py
from django.apps import AppConfig

class TrackingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.tracking'
    verbose_name       = 'Tracking & Postback'
    label              = 'payment_gateways_tracking'
