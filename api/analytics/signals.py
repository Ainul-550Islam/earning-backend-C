# api/analytics/signals.py
"""
Production-ready signals for api.analytics.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)
