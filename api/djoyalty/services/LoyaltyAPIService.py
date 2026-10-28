# api/djoyalty/services/LoyaltyAPIService.py
"""
LoyaltyAPIService -- white-label API facade।
Partner/external system integration entry point।
Single interface for all loyalty operations।
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class LoyaltyAPIService:
    """
    White-label API facade।
    Partner systems এই single class এর মাধ্যমে সব loyalty operations করতে পারে।
    """

    @staticmethod
    def get_customer_balance(customer_code: str, api_key: str) -> dict:
        """Customer balance API endpoint।"""
        from .PartnerMerchantService import PartnerMerchantService
        from ..models.core import Customer
        from ..exceptions import PartnerNotFoundError, CustomerNotFoundError

        partner = PartnerMerchantService.validate_api_key(api_key)
        if not partner:
            raise PartnerNotFoundError()

        customer = Customer.objects.filter(
            code=customer_code.strip().upper(), is_active=True
        ).first()
        if not customer:
            raise CustomerNotFoundError()

        lp = customer.loyalty_points.first()
        ut = customer.user_tiers.filter(is_current=True).select_related('tier').first()

        return {
            'customer_code': customer.code,
            'loyalty_number': customer.loyalty_number,
            'balance': str(lp.balance if lp else 0),
            'lifetime_earned': str(lp.lifetime_earned if lp else 0),
            'tier': ut.tier.name if ut and ut.tier else 'bronze',
            'tier_label': ut.tier.label if ut and ut.tier else 'Bronze',
        }

    @staticmethod
    def earn_points(customer_code: str, api_key: str, spend_amount: float,
                    reference: str, currency: str = 'BDT') -> dict:
        """Points earn API endpoint।"""
        from .CoalitionEarnService import CoalitionEarnService
        return CoalitionEarnService.earn_at_partner(
            api_key=api_key,
            customer_code=customer_code,
            spend_amount=Decimal(str(spend_amount)),
            reference=reference,
            currency=currency,
        )

    @staticmethod
    def redeem_points(customer_code: str, api_key: str, points: float,
                      redemption_type: str = 'cashback') -> dict:
        """Points redeem API endpoint।"""
        from .PartnerMerchantService import PartnerMerchantService
        from ..models.core import Customer
        from ..services.redemption.RedemptionService import RedemptionService
        from ..exceptions import PartnerNotFoundError, CustomerNotFoundError

        partner = PartnerMerchantService.validate_api_key(api_key)
        if not partner:
            raise PartnerNotFoundError()

        customer = Customer.objects.filter(
            code=customer_code.strip().upper(), is_active=True
        ).first()
        if not customer:
            raise CustomerNotFoundError()

        req = RedemptionService.create_request(
            customer=customer,
            points=Decimal(str(points)),
            redemption_type=redemption_type,
        )
        return {
            'success': True,
            'redemption_id': req.id,
            'customer_code': customer.code,
            'points_used': str(req.points_used),
            'reward_value': str(req.reward_value),
            'status': req.status,
        }

    @staticmethod
    def get_tier_info(customer_code: str, api_key: str) -> dict:
        """Customer tier info API endpoint।"""
        from .PartnerMerchantService import PartnerMerchantService
        from ..models.core import Customer
        from ..exceptions import PartnerNotFoundError, CustomerNotFoundError
        from ..utils import get_next_tier, get_points_needed_for_next_tier

        partner = PartnerMerchantService.validate_api_key(api_key)
        if not partner:
            raise PartnerNotFoundError()

        customer = Customer.objects.filter(
            code=customer_code.strip().upper(), is_active=True
        ).first()
        if not customer:
            raise CustomerNotFoundError()

        ut = customer.user_tiers.filter(is_current=True).select_related('tier').first()
        lp = customer.loyalty_points.first()
        tier_name = ut.tier.name if ut and ut.tier else 'bronze'
        lifetime = lp.lifetime_earned if lp else Decimal('0')
        next_tier = get_next_tier(tier_name)
        pts_needed = get_points_needed_for_next_tier(lifetime, tier_name) if next_tier else None

        return {
            'customer_code': customer.code,
            'current_tier': tier_name,
            'tier_label': ut.tier.label if ut and ut.tier else tier_name.title(),
            'earn_multiplier': str(ut.tier.earn_multiplier if ut and ut.tier else 1),
            'lifetime_earned': str(lifetime),
            'next_tier': next_tier,
            'points_needed_for_next_tier': str(pts_needed) if pts_needed is not None else None,
        }

    @staticmethod
    def validate_voucher(voucher_code: str, api_key: str) -> dict:
        """Voucher validate করো।"""
        from .PartnerMerchantService import PartnerMerchantService
        from ..models.redemption import Voucher
        from ..exceptions import PartnerNotFoundError
        from django.utils import timezone

        partner = PartnerMerchantService.validate_api_key(api_key)
        if not partner:
            raise PartnerNotFoundError()

        voucher = Voucher.objects.filter(code=voucher_code.strip().upper()).first()
        if not voucher:
            return {'valid': False, 'reason': 'Voucher not found'}
        if voucher.status != 'active':
            return {'valid': False, 'reason': f'Voucher status: {voucher.status}'}
        if voucher.expires_at and voucher.expires_at < timezone.now():
            return {'valid': False, 'reason': 'Voucher expired'}
        return {
            'valid': True,
            'code': voucher.code,
            'voucher_type': voucher.voucher_type,
            'discount_value': str(voucher.discount_value),
            'expires_at': voucher.expires_at.isoformat() if voucher.expires_at else None,
        }
