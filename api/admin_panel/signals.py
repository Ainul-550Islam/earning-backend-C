# api/admin_panel/signals.py
"""
Production-ready signals for api.admin_panel.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)
