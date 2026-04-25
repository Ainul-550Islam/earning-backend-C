# api/payment_gateways/notifications/apps.py
from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api.payment_gateways.notifications'
    verbose_name       = 'Notifications'
    label              = 'payment_gateways_notifications'
