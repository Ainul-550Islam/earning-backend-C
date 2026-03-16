# api/offerwall/signals.py
"""
Production-ready signals for api.offerwall.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)
