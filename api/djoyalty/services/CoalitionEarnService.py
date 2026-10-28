# api/djoyalty/services/CoalitionEarnService.py
"""
CoalitionEarnService -- multi-merchant coalition points processing।
"""
import logging
from decimal import Decimal
from django.db import transaction

logger = logging.getLogger(__name__)


class CoalitionEarnService:

    @staticmethod
    def earn_at_partner(api_key: str, customer_code: str, spend_amount: Decimal,
                        reference: str, currency: str = 'BDT', description: str = '') -> dict:
        """
        Partner API key দিয়ে coalition earn।
        White-label partner integration entry point।
        """
        from .PartnerMerchantService import PartnerMerchantService
        from ..models.core import Customer
        from ..exceptions import PartnerNotFoundError, CustomerNotFoundError

        partner = PartnerMerchantService.validate_api_key(api_key)
        if not partner:
            raise PartnerNotFoundError(f'Invalid or inactive API key.')

        customer = Customer.objects.filter(
            code=customer_code.strip().upper(), is_active=True
        ).first()
        if not customer:
            raise CustomerNotFoundError(f'Customer not found: {customer_code}')

        earn = PartnerMerchantService.process_partner_earn(
            customer=customer,
            partner=partner,
            spend_amount=Decimal(str(spend_amount)),
            reference=reference,
            currency=currency,
            description=description,
        )
        return {
            'success': True,
            'customer_code': customer.code,
            'partner': partner.name,
            'points_earned': str(earn.points_earned),
            'reference': earn.reference,
            'status': earn.status,
        }

    @staticmethod
    def reverse_earn(reference: str, reversed_by: str = 'system') -> bool:
        """Coalition earn reverse করো -- fraud বা error এ।"""
        from ..models.advanced import CoalitionEarn
        from ..models.points import LoyaltyPoints, PointsLedger
        from ..choices import LEDGER_DEBIT, LEDGER_SOURCE_PARTNER

        try:
            with transaction.atomic():
                earn = CoalitionEarn.objects.select_for_update().filter(
                    reference=reference, status='processed'
                ).first()
                if not earn:
                    logger.warning('CoalitionEarnService.reverse_earn: not found %s', reference)
                    return False

                lp = earn.customer.loyalty_points.first()
                if lp and earn.points_earned > 0:
                    actual = min(earn.points_earned, lp.balance)
                    if actual > 0:
                        lp.balance -= actual
                        lp.save(update_fields=['balance', 'updated_at'])
                        PointsLedger.objects.create(
                            customer=earn.customer,
                            tenant=earn.tenant,
                            txn_type=LEDGER_DEBIT,
                            source=LEDGER_SOURCE_PARTNER,
                            points=actual,
                            balance_after=lp.balance,
                            description=f'Reversed partner earn: {earn.partner.name} ref={reference}',
                            reference_id=reference,
                        )

                earn.status = 'reversed'
                earn.save(update_fields=['status'])
                logger.info('CoalitionEarnService: reversed earn %s by %s', reference, reversed_by)
                return True
        except Exception as e:
            logger.error('CoalitionEarnService.reverse_earn error: %s', e)
            return False

    @staticmethod
    def get_customer_coalition_history(customer, limit: int = 50):
        """Customer এর coalition earn history।"""
        from ..models.advanced import CoalitionEarn
        return CoalitionEarn.objects.filter(
            customer=customer
        ).select_related('partner').order_by('-created_at')[:limit]

    @staticmethod
    def get_coalition_summary(customer) -> dict:
        """Customer এর coalition earning summary।"""
        from ..models.advanced import CoalitionEarn
        from django.db.models import Sum, Count
        stats = CoalitionEarn.objects.filter(customer=customer, status='processed').aggregate(
            total_transactions=Count('id'),
            total_points=Sum('points_earned'),
            total_spend=Sum('spend_amount'),
        )
        partners = CoalitionEarn.objects.filter(
            customer=customer, status='processed'
        ).values_list('partner__name', flat=True).distinct()

        return {
            'total_coalition_transactions': stats['total_transactions'] or 0,
            'total_coalition_points': str(stats['total_points'] or 0),
            'total_coalition_spend': str(stats['total_spend'] or 0),
            'partner_count': len(list(partners)),
            'partners': list(partners),
        }
