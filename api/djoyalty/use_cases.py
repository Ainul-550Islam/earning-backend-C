# api/djoyalty/use_cases.py
"""
Djoyalty Use Cases -- Application layer use cases।
Each use case = one business operation (Clean Architecture)।
Use cases orchestrate services, validators, repositories।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


# ─── Data Classes (Input/Output) ─────────────────────────────────────────────

@dataclass
class EarnPointsInput:
    customer_id: int
    txn_id: Optional[int] = None
    amount: Optional[Decimal] = None
    source: str = 'purchase'
    reference_id: str = ''
    metadata: dict = None


@dataclass
class EarnPointsOutput:
    success: bool
    points_earned: Decimal = Decimal('0')
    new_balance: Decimal = Decimal('0')
    tier_changed: bool = False
    new_tier: str = ''
    badges_earned: list = None
    error: str = ''

    def __post_init__(self):
        if self.badges_earned is None:
            self.badges_earned = []


@dataclass
class RedeemPointsInput:
    customer_id: int
    points: Decimal
    redemption_type: str = 'voucher'
    note: str = ''


@dataclass
class RedeemPointsOutput:
    success: bool
    redemption_id: Optional[int] = None
    voucher_code: str = ''
    new_balance: Decimal = Decimal('0')
    error: str = ''


@dataclass
class CashoutInput:
    customer_id: int
    points: Decimal
    method: str = 'mobile_wallet'
    wallet_id: Optional[int] = None
    bank_account_id: Optional[int] = None


@dataclass
class CashoutOutput:
    success: bool
    cashout_id: Optional[int] = None
    reference: str = ''
    cash_amount: Decimal = Decimal('0')
    error: str = ''


# ─── Use Cases ────────────────────────────────────────────────────────────────

class EarnPointsUseCase:
    """
    UC-001: Earn points for a customer।
    Orchestrates: EarnService + TierService + BadgeService + NotificationService।
    Single entry point for all points earning।
    """

    def execute(self, input_data: EarnPointsInput) -> EarnPointsOutput:
        from .models.core import Customer
        from .validator import LoyaltyValidator
        from .services.earn.EarnRuleEngine import EarnRuleEngine as EarnService
        from .services.tiers.TierEvaluationService import TierEvaluationService as TierService
        from .services.engagement.BadgeService import BadgeService
        from .services.NotificationService import NotificationService

        # 1. Get customer
        try:
            customer = Customer.objects.get(id=input_data.customer_id, is_active=True)
        except Customer.DoesNotExist:
            return EarnPointsOutput(success=False, error=f'Customer #{input_data.customer_id} not found.')

        # 2. Calculate points if not provided directly
        points = input_data.amount
        if points is None:
            return EarnPointsOutput(success=False, error='Amount or points must be provided.')

        # 3. Validate
        ok, msg = LoyaltyValidator.validate_earn(customer, points, input_data.source)
        if not ok:
            return EarnPointsOutput(success=False, error=msg)

        # 4. Award points
        try:
            ledger = EarnService.award_points(
                customer=customer,
                points=points,
                source=input_data.source,
                reference_id=input_data.reference_id,
                metadata=input_data.metadata or {},
            )
        except Exception as e:
            logger.error('EarnPointsUseCase: award_points failed: %s', e)
            return EarnPointsOutput(success=False, error=str(e))

        new_balance = ledger.balance_after

        # 5. Evaluate tier upgrade
        tier_changed = False
        new_tier = ''
        try:
            tier_result = TierService.evaluate_and_upgrade(customer)
            if tier_result.get('upgraded'):
                tier_changed = True
                new_tier = tier_result.get('new_tier', '')
        except Exception as e:
            logger.debug('EarnPointsUseCase: tier eval error: %s', e)

        # 6. Check badge unlocks
        badges_earned = []
        try:
            badges_earned = BadgeService.check_and_award(customer)
        except Exception as e:
            logger.debug('EarnPointsUseCase: badge check error: %s', e)

        # 7. Notify customer
        try:
            NotificationService.notify_points_earned(customer, points, new_balance)
            if tier_changed and new_tier:
                NotificationService.notify_tier_upgrade(customer, new_tier)
        except Exception as e:
            logger.debug('EarnPointsUseCase: notification error: %s', e)

        # 8. Fire hooks
        try:
            from .hooks import LoyaltyHooks
            LoyaltyHooks.fire('after_earn', customer=customer, points=points, source=input_data.source)
        except Exception:
            pass

        return EarnPointsOutput(
            success=True,
            points_earned=points,
            new_balance=new_balance,
            tier_changed=tier_changed,
            new_tier=new_tier,
            badges_earned=[b.name for b in badges_earned],
        )


class RedeemPointsUseCase:
    """
    UC-002: Redeem points for a reward।
    Orchestrates: RedemptionService + NotificationService + AuditLog।
    """

    def execute(self, input_data: RedeemPointsInput) -> RedeemPointsOutput:
        from .models.core import Customer
        from .validator import LoyaltyValidator
        from .services.redemption.RedemptionService import RedemptionService
        from .services.NotificationService import NotificationService
        from .models.audit import AdminAuditLog

        try:
            customer = Customer.objects.get(id=input_data.customer_id, is_active=True)
        except Customer.DoesNotExist:
            return RedeemPointsOutput(success=False, error='Customer not found.')

        ok, msg = LoyaltyValidator.validate_redeem(customer, input_data.points)
        if not ok:
            return RedeemPointsOutput(success=False, error=msg)

        try:
            result = RedemptionService.redeem_points(
                customer=customer,
                points=input_data.points,
                redemption_type=input_data.redemption_type,
                note=input_data.note,
            )
        except Exception as e:
            logger.error('RedeemPointsUseCase: %s', e)
            return RedeemPointsOutput(success=False, error=str(e))

        from .selectors import get_points_balance
        new_balance = get_points_balance(customer)

        # Notify
        try:
            if hasattr(result, 'voucher') and result.voucher:
                NotificationService.notify_voucher_issued(
                    customer, result.voucher.code, str(result.voucher.discount_value)
                )
        except Exception:
            pass

        # Audit
        try:
            AdminAuditLog.log(
                action='points_redeemed',
                category='redemption',
                customer=customer,
                old_value={'points': str(input_data.points)},
                new_value={'balance': str(new_balance)},
            )
        except Exception:
            pass

        return RedeemPointsOutput(
            success=True,
            redemption_id=result.id if result else None,
            new_balance=new_balance,
        )


class CashoutRequestUseCase:
    """
    UC-003: Request a points cashout।
    Orchestrates: Validator + CashoutService + IntegrationBridge + Notifications।
    """

    def execute(self, input_data: CashoutInput) -> CashoutOutput:
        from .models.core import Customer
        from .validator import LoyaltyValidator
        from .integration_system.bridge import loyalty_bridge

        try:
            customer = Customer.objects.get(id=input_data.customer_id, is_active=True)
        except Customer.DoesNotExist:
            return CashoutOutput(success=False, error='Customer not found.')

        ok, msg = LoyaltyValidator.validate_cashout(customer, input_data.points, input_data.method)
        if not ok:
            return CashoutOutput(success=False, error=msg)

        try:
            from .models.cashout import CashoutRequest, CashoutRate, CustomerMobileWallet
            import uuid

            rate = CashoutRate.objects.filter(
                is_active=True, cashout_method=input_data.method
            ).order_by('-effective_from').first()

            if not rate:
                return CashoutOutput(success=False, error='Cashout not available.')

            if input_data.points < rate.min_cashout_points:
                return CashoutOutput(
                    success=False,
                    error=f'Minimum cashout is {rate.min_cashout_points} points.',
                )

            cash_amount = (input_data.points / rate.points_per_unit).quantize(Decimal('0.01'))

            wallet = None
            if input_data.wallet_id:
                wallet = CustomerMobileWallet.objects.filter(
                    id=input_data.wallet_id, customer=customer
                ).first()

            cashout = CashoutRequest.objects.create(
                customer=customer,
                tenant=customer.tenant,
                points_to_redeem=input_data.points,
                cash_amount=cash_amount,
                cashout_method=input_data.method,
                mobile_wallet=wallet,
                reference=f'CO-{uuid.uuid4().hex[:8].upper()}',
            )

            return CashoutOutput(
                success=True,
                cashout_id=cashout.id,
                reference=cashout.reference,
                cash_amount=cash_amount,
            )
        except Exception as e:
            logger.error('CashoutRequestUseCase: %s', e)
            return CashoutOutput(success=False, error=str(e))


class ReferralConversionUseCase:
    """
    UC-004: Process a referral conversion।
    Awards points to both referrer and referred customer।
    """

    def execute(self, referral_code: str, referred_customer) -> dict:
        from .models.referral import ReferralLink, ReferralConversion, ReferralProgram
        from .validator import LoyaltyValidator
        from .services.earn.EarnRuleEngine import EarnRuleEngine as EarnService

        # Find referral link
        link = ReferralLink.objects.filter(code=referral_code.upper(), is_active=True).first()
        if not link:
            return {'success': False, 'error': 'Invalid referral code.'}

        referrer = link.customer
        ok, msg = LoyaltyValidator.validate_referral(referrer, referred_customer)
        if not ok:
            return {'success': False, 'error': msg}

        # Get program config
        program = ReferralProgram.objects.filter(
            is_active=True,
            tenant=referrer.tenant,
        ).first()

        referrer_pts = program.referrer_signup_points if program else Decimal('100')
        referred_pts = program.referred_welcome_points if program else Decimal('50')

        # Award points
        try:
            EarnService.award_points(referrer, referrer_pts, source='referral',
                                      reference_id=f'REF-{referred_customer.id}')
            EarnService.award_points(referred_customer, referred_pts, source='referral',
                                      reference_id=f'REF-WELCOME-{referrer.id}')
        except Exception as e:
            return {'success': False, 'error': str(e)}

        # Create conversion record
        conversion = ReferralConversion.objects.create(
            referral_link=link,
            referrer=referrer,
            referred_customer=referred_customer,
            conversion_type='signup',
            referrer_points=referrer_pts,
            referred_points=referred_pts,
            status='paid',
        )

        # Update link stats
        link.total_conversions += 1
        link.total_points_earned += referrer_pts
        link.save(update_fields=['total_conversions', 'total_points_earned'])

        return {
            'success': True,
            'conversion_id': conversion.id,
            'referrer_points': str(referrer_pts),
            'referred_points': str(referred_pts),
        }
