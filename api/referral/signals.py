# api/referral/signals.py
"""
Production-ready signals for api.referral.
Connect with users (signup) and wallet (bonus credit).
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

logger = logging.getLogger(__name__)


def _get_user_model():
    from django.apps import apps
    from django.conf import settings
    return apps.get_model(settings.AUTH_USER_MODEL)
