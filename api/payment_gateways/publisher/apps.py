# api/payment_gateways/publisher/apps.py
from django.apps import AppConfig

class PublisherConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.publisher'
    verbose_name       = 'Publisher Profiles'
    label              = 'payment_gateways_publisher'
