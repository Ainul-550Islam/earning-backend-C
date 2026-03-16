# api/cms/signals.py
"""
Production-ready signals for api.cms.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)
