# api/offer_inventory/publisher_sdk/publisher_payout.py
"""Publisher Payout Manager — Pay publishers their revenue share."""
import logging
from decimal import Decimal
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

MIN_PAYOUT_USD = Decimal('50')   # Minimum $50 payout to publishers


class PublisherPayoutManager:
    """Manage publisher revenue share calculations and payouts."""

    @classmethod
    def calculate_earnings(cls, publisher_id: str,
                            days: int = 30) -> dict:
        """Calculate publisher's earned revenue share."""
        from api.offer_inventory.models import BidLog
        from django.db.models import Sum, Count

        since = timezone.now() - timedelta(days=days)
        agg   = BidLog.objects.filter(
            publisher_id=publisher_id,
            created_at__gte=since,
            is_won=True,
        ).aggregate(
            wins          =Count('id'),
            gross_revenue =Sum('clearing_price'),
        )

        gross     = Decimal(str(agg['gross_revenue'] or 0))
        pub_share = (gross * Decimal('0.30')).quantize(Decimal('0.01'))

        return {
            'publisher_id' : publisher_id,
            'period_days'  : days,
            'wins'         : agg['wins'] or 0,
            'gross_revenue': float(gross),
            'publisher_share_pct': 30.0,
            'earnings'     : float(pub_share),
            'currency'     : 'USD',
            'payout_eligible': float(pub_share) >= float(MIN_PAYOUT_USD),
        }

    @classmethod
    @transaction.atomic
    def process_payout(cls, publisher_id: str) -> dict:
        """Process a publisher payout via wire transfer/PayPal."""
        from api.offer_inventory.models import Publisher, PublisherPayout

        earnings = cls.calculate_earnings(publisher_id, days=30)
        if not earnings['payout_eligible']:
            return {
                'success': False,
                'reason' : f'Below minimum payout (${MIN_PAYOUT_USD})',
                'earned' : earnings['earnings'],
            }

        try:
            publisher = Publisher.objects.get(id=publisher_id, status='active')
        except Publisher.DoesNotExist:
            return {'success': False, 'reason': 'Publisher not found'}

        payout = PublisherPayout.objects.create(
            publisher  =publisher,
            amount     =Decimal(str(earnings['earnings'])),
            currency   ='USD',
            method     =publisher.payout_method or 'wire',
            status     ='pending',
            period_end =timezone.now(),
        )
        logger.info(
            f'Publisher payout queued: {publisher_id} '
            f'${earnings["earnings"]}'
        )
        return {
            'success'   : True,
            'payout_id' : str(payout.id),
            'amount'    : earnings['earnings'],
            'currency'  : 'USD',
            'method'    : payout.method,
            'status'    : 'pending',
        }

    @staticmethod
    def get_payout_history(publisher_id: str) -> list:
        """Publisher payout history."""
        from api.offer_inventory.models import PublisherPayout
        return list(
            PublisherPayout.objects.filter(publisher_id=publisher_id)
            .values('id', 'amount', 'currency', 'method', 'status', 'created_at')
            .order_by('-created_at')[:24]
        )
