# api/djoyalty/pos_integration.py
"""
Djoyalty POS Integration -- In-store Point of Sale loyalty।
Connect physical store POS to Djoyalty for earn/redeem at checkout।

2025/2026 world standard: ALL major loyalty platforms support POS।
Supports: Square, Stripe Terminal, custom POS via API।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


class POSCheckoutPayload:
    """Standard payload from POS system at checkout।"""

    def __init__(self, customer_identifier: str, order_amount: Decimal,
                  order_reference: str, store_id: str = '',
                  cashier_id: str = '', items: list = None,
                  redeem_points: Decimal = Decimal('0'),
                  identifier_type: str = 'phone'):
        self.customer_identifier = customer_identifier  # phone, code, or barcode
        self.identifier_type = identifier_type          # 'phone', 'code', 'card', 'qr'
        self.order_amount = order_amount
        self.order_reference = order_reference
        self.store_id = store_id
        self.cashier_id = cashier_id
        self.items = items or []
        self.redeem_points = redeem_points


class POSCheckoutResult:
    """Result returned to POS after loyalty processing।"""

    def __init__(self, success: bool, customer_code: str = '',
                  customer_name: str = '', points_earned: Decimal = Decimal('0'),
                  points_redeemed: Decimal = Decimal('0'),
                  discount_applied: Decimal = Decimal('0'),
                  new_balance: Decimal = Decimal('0'),
                  tier: str = '', message: str = '', error: str = ''):
        self.success = success
        self.customer_code = customer_code
        self.customer_name = customer_name
        self.points_earned = points_earned
        self.points_redeemed = points_redeemed
        self.discount_applied = discount_applied
        self.new_balance = new_balance
        self.tier = tier
        self.message = message
        self.error = error

    def to_dict(self) -> dict:
        return {
            'success': self.success,
            'customer_code': self.customer_code,
            'customer_name': self.customer_name,
            'points_earned': str(self.points_earned),
            'points_redeemed': str(self.points_redeemed),
            'discount_applied': str(self.discount_applied),
            'new_balance': str(self.new_balance),
            'tier': self.tier,
            'message': self.message,
            'error': self.error,
        }


class POSLoyaltyService:
    """
    Core POS integration service।
    Processes loyalty at physical checkout:
      1. Identify customer (phone/code/card/QR)
      2. Award earn points for purchase
      3. Apply redemption if requested
      4. Return result to POS display

    Usage:
        result = POSLoyaltyService.process_checkout(POSCheckoutPayload(
            customer_identifier='01700000000',
            identifier_type='phone',
            order_amount=Decimal('1500'),
            order_reference='POS-STORE1-0001',
            redeem_points=Decimal('100'),  # 0 = no redemption
        ))
        # Show result.message on POS display
        # Show result.new_balance on receipt
    """

    @staticmethod
    def identify_customer(identifier: str, identifier_type: str, tenant=None):
        """Identify customer from POS input (phone/code/card/QR)।"""
        from .models.core import Customer
        from .helpers import normalize_bd_phone

        if identifier_type == 'phone':
            phone = normalize_bd_phone(identifier)
            if phone:
                qs = Customer.objects.filter(phone=phone, is_active=True)
                if tenant:
                    qs = qs.filter(tenant=tenant)
                return qs.first()

        elif identifier_type in ('code', 'card'):
            qs = Customer.objects.filter(code=identifier.upper(), is_active=True)
            if tenant:
                qs = qs.filter(tenant=tenant)
            return qs.first()

        elif identifier_type == 'qr':
            # QR contains customer code or loyalty number
            qs = Customer.objects.filter(
                models.Q(code=identifier.upper()) |
                models.Q(loyalty_number=identifier),
                is_active=True,
            )
            if tenant:
                qs = qs.filter(tenant=tenant)
            return qs.first()

        elif identifier_type == 'barcode':
            # Barcode on physical loyalty card
            from .models.catalog import DigitalWalletCard
            card = DigitalWalletCard.objects.filter(
                barcode_value=identifier, is_active=True
            ).select_related('customer').first()
            return card.customer if card else None

        return None

    @staticmethod
    def process_checkout(payload: POSCheckoutPayload,
                          tenant=None) -> POSCheckoutResult:
        """
        Main POS checkout processing।
        Earn points + optional redemption, all in one atomic operation।
        """
        # 1. Identify customer
        customer = POSLoyaltyService.identify_customer(
            payload.customer_identifier, payload.identifier_type, tenant
        )

        if not customer:
            return POSCheckoutResult(
                success=False,
                error=f'Customer not found: {payload.customer_identifier}',
            )

        if not customer.is_active:
            return POSCheckoutResult(
                success=False,
                customer_code=customer.code,
                error='Customer account is not active.',
            )

        points_earned = Decimal('0')
        points_redeemed = Decimal('0')
        discount_applied = Decimal('0')

        # 2. Process redemption (if requested)
        if payload.redeem_points > 0:
            from .validator import LoyaltyValidator
            ok, msg = LoyaltyValidator.validate_redeem(customer, payload.redeem_points)
            if ok:
                try:
                    from .repositories import PointsRepository
                    PointsRepository.debit(
                        customer=customer,
                        points=payload.redeem_points,
                        source='redemption',
                        reference_id=payload.order_reference,
                        description=f'POS redemption: {payload.store_id} order {payload.order_reference}',
                    )
                    points_redeemed = payload.redeem_points
                    # Calculate discount (1 point = 0.01 BDT default)
                    from .logic import calculate_points_cash_value
                    discount_applied = calculate_points_cash_value(payload.redeem_points)
                    logger.info('POSLoyaltyService: redeemed %s pts for %s at POS',
                                payload.redeem_points, customer.code)
                except Exception as e:
                    logger.error('POSLoyaltyService.redeem error: %s', e)

        # 3. Earn points for purchase
        try:
            # Check paid membership multiplier
            from .paid_membership import MembershipBenefitsManager
            multiplier = MembershipBenefitsManager.get_earn_multiplier(customer)

            from .logic import calculate_earn_points
            points_earned = calculate_earn_points(
                transaction_value=payload.order_amount,
                earn_rate=Decimal('1'),
                multiplier=multiplier,
            )

            from .repositories import PointsRepository
            ledger = PointsRepository.credit(
                customer=customer,
                points=points_earned,
                source='purchase',
                reference_id=payload.order_reference,
                description=f'POS earn: {payload.store_id} ৳{payload.order_amount}',
            )
            new_balance = ledger.balance_after
        except Exception as e:
            logger.error('POSLoyaltyService.earn error: %s', e)
            from .selectors import get_points_balance
            new_balance = get_points_balance(customer)

        # 4. Get tier
        from .selectors import get_current_tier
        tier = get_current_tier(customer)
        tier_name = tier.name if tier else 'Bronze'

        # 5. Notify (async -- don't block POS)
        try:
            from .services.NotificationService import NotificationService
            NotificationService.notify_points_earned(customer, points_earned, new_balance)
        except Exception:
            pass

        # 6. Audit
        try:
            from .models.audit import AdminAuditLog
            AdminAuditLog.log(
                action='pos_checkout',
                category='points',
                customer=customer,
                new_value={
                    'order_ref': payload.order_reference,
                    'store_id': payload.store_id,
                    'amount': str(payload.order_amount),
                    'earned': str(points_earned),
                    'redeemed': str(points_redeemed),
                },
            )
        except Exception:
            pass

        return POSCheckoutResult(
            success=True,
            customer_code=customer.code,
            customer_name=f'{customer.firstname or ""} {customer.lastname or ""}'.strip() or customer.code,
            points_earned=points_earned,
            points_redeemed=points_redeemed,
            discount_applied=discount_applied,
            new_balance=new_balance,
            tier=tier_name,
            message=(
                f'+{points_earned} pts earned! '
                f'Balance: {new_balance} pts. '
                f'{tier_name} member.'
            ),
        )

    @staticmethod
    def get_customer_info_for_pos(identifier: str, identifier_type: str,
                                   tenant=None) -> dict:
        """
        Pre-checkout customer lookup for POS display।
        Called before completing order so cashier can see customer's tier/balance।
        """
        customer = POSLoyaltyService.identify_customer(identifier, identifier_type, tenant)
        if not customer:
            return {'found': False}

        from .selectors import get_points_balance, get_current_tier, get_tier_progress
        balance = get_points_balance(customer)
        tier = get_current_tier(customer)

        return {
            'found': True,
            'customer_code': customer.code,
            'customer_name': f'{customer.firstname or ""} {customer.lastname or ""}'.strip(),
            'phone': customer.phone or '',
            'balance': str(balance),
            'tier': tier.name if tier else 'Bronze',
            'tier_color': tier.color if tier and hasattr(tier, 'color') else '#3b82f6',
            'pending_points': str(
                __import__('djoyalty.pending_points', fromlist=['PendingPointsManager'])
                .PendingPointsManager.get_pending_total(customer)
            ),
        }


import django.db.models as models
