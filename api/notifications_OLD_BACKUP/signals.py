# api/notifications/signals.py
"""
Production-ready signals for api.notifications.
Automated triggers for notification creation and delivery.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)
