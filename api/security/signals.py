# api/security/signals.py
"""
Production-ready signals for api.security.
Handle automatic triggers between security and other apps.
"""
import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _get_user_model():
    from django.apps import apps
    from django.conf import settings
    return apps.get_model(settings.AUTH_USER_MODEL)


# Add receivers for your security models when needed, e.g.:
# @receiver(post_save, sender='security.YourModel')
# def on_your_model_save(sender, instance, created, **kwargs): ...
