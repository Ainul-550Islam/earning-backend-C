# api/djoyalty/services.py
"""
Business logic for djoyalty (loyalty). Move complex logic out of views.
"""
import logging
from typing import Optional, Dict, Any
from decimal import Decimal

logger = logging.getLogger(__name__)


class DjoyaltyService:
    """Service for loyalty/points operations."""

    @staticmethod
    def get_customer_balance(customer) -> Decimal:
        """Return effective balance for a customer. Override with your Txn/points model."""
        try:
            from .models import Txn
            from django.db.models import Sum
            result = Txn.objects.filter(customer=customer).aggregate(s=Sum('value'))
            return result.get('s') or Decimal('0')
        except Exception as e:
            logger.debug("Djoyalty balance: %s", e)
            return Decimal('0')
