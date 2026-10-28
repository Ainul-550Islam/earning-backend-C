# api/djoyalty/services/PartnerMerchantService.py
"""
PartnerMerchantService -- partner merchant earn, sync, validation।
"""
import logging
from decimal import Decimal
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class PartnerMerchantService:

    @staticmethod
    def validate_api_key(api_key: str):
        """API key দিয়ে partner merchant খোঁজো।"""
        from ..models.campaigns import PartnerMerchant
        return PartnerMerchant.objects.filter(api_key=api_key, is_active=True).first()

    @staticmethod
    @transaction.atomic
    def process_partner_earn(customer, partner, spend_amount: Decimal, reference: str,
                             currency: str = 'BDT', description: str = '', tenant=None):
        """
        Partner merchant এ customer এর earn process করো।
        Points calculate করে LoyaltyPoints তে credit করে।
        CoalitionEarn record তৈরি করে।
        """
        from ..models.advanced import CoalitionEarn
        from ..models.points import LoyaltyPoints, PointsLedger
        from ..choices import LEDGER_CREDIT, LEDGER_SOURCE_PARTNER

        if CoalitionEarn.objects.filter(reference=reference).exists():
            logger.warning('PartnerMerchantService: duplicate reference %s', reference)
            raise ValueError(f'Duplicate reference: {reference}')

        earn_rate = partner.earn_rate
        points = (Decimal(str(spend_amount)) * earn_rate).quantize(Decimal('0.01'))

        lp, _ = LoyaltyPoints.objects.get_or_create(
            customer=customer,
            defaults={'tenant': tenant or customer.tenant, 'balance': Decimal('0')},
        )
        lp.credit(points)

        earn = CoalitionEarn.objects.create(
            customer=customer,
            partner=partner,
            tenant=tenant or customer.tenant,
            spend_amount=spend_amount,
            points_earned=points,
            earn_rate_applied=earn_rate,
            reference=reference,
            currency=currency,
            status='processed',
            description=description or f'Earn at {partner.name}',
            processed_at=timezone.now(),
        )

        PointsLedger.objects.create(
            customer=customer,
            tenant=tenant or customer.tenant,
            txn_type=LEDGER_CREDIT,
            source=LEDGER_SOURCE_PARTNER,
            points=points,
            balance_after=lp.balance,
            description=f'Partner earn: {partner.name} -- {spend_amount} {currency}',
            reference_id=reference,
        )

        logger.info('PartnerMerchantService: %s earned %s pts at %s', customer.code, points, partner.name)
        return earn

    @staticmethod
    def sync_partner(partner):
        """Partner এর last_sync_at update করো।"""
        try:
            partner.last_sync_at = timezone.now()
            partner.save(update_fields=['last_sync_at'])
            return True
        except Exception as e:
            logger.error('PartnerMerchantService.sync_partner error: %s', e)
            return False

    @staticmethod
    def sync_all_active():
        """সব active partners sync করো।"""
        from ..models.campaigns import PartnerMerchant
        partners = PartnerMerchant.objects.filter(is_active=True)
        count = partners.update(last_sync_at=timezone.now())
        logger.info('PartnerMerchantService: synced %d partners', count)
        return count

    @staticmethod
    def get_partner_stats(partner) -> dict:
        """Partner এর earn statistics।"""
        from ..models.advanced import CoalitionEarn
        from django.db.models import Sum, Count
        stats = CoalitionEarn.objects.filter(partner=partner, status='processed').aggregate(
            total_earns=Count('id'),
            total_points=Sum('points_earned'),
            total_spend=Sum('spend_amount'),
        )
        return {
            'partner': partner.name,
            'total_earn_transactions': stats['total_earns'] or 0,
            'total_points_issued': str(stats['total_points'] or 0),
            'total_spend': str(stats['total_spend'] or 0),
        }
