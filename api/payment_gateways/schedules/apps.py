# api/payment_gateways/schedules/apps.py
from django.apps import AppConfig

class SchedulesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.schedules'
    verbose_name       = 'Payment Schedules'
    label              = 'payment_gateways_schedules'
