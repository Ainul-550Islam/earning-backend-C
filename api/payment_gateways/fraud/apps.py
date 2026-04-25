# FILE 88 of 257
from django.apps import AppConfig
class FraudConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.fraud'
    label              = 'payment_gateway_fraud'
    verbose_name       = 'Payment Gateway Fraud Detection'
