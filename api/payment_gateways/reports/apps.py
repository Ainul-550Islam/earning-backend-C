# api/payment_gateways/reports/apps.py
from django.apps import AppConfig

class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.reports'
    verbose_name       = 'Reports'
    label              = 'payment_gateways_reports'
