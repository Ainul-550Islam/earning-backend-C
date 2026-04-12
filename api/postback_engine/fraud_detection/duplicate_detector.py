"""
fraud_detection/duplicate_detector.py
───────────────────────────────────────
Fast duplicate detection for clicks and conversions.
Separate from ConversionDeduplicator — this is a read-only pre-check.
"""
from __future__ import annotations
import logging
from django.core.cache import cache
from ..models import ClickLog, ConversionDeduplication

logger = logging.getLogger(__name__)


class DuplicateDetector:

    def is_duplicate_click(self, click_id: str) -> bool:
        """Check if click_id already converted."""
        return ClickLog.objects.filter(
            click_id=click_id, converted=True
        ).exists()

    def is_duplicate_conversion(self, network, lead_id: str) -> bool:
        """Check if lead_id already credited for this network."""
        return ConversionDeduplication.objects.filter(
            network=network, lead_id=lead_id
        ).exists()

    def is_duplicate_transaction(self, transaction_id: str) -> bool:
        """Check if transaction_id already credited globally."""
        if not transaction_id:
            return False
        return ConversionDeduplication.objects.filter(
            transaction_id=transaction_id
        ).exists()


# Module-level singleton
duplicate_detector = DuplicateDetector()
