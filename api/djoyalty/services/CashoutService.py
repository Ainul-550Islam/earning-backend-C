# api/djoyalty/services/CashoutService.py
"""
CashoutService — Centralized, atomic cashout business logic।

DRY FIX (v3):
  All return dicts now use ServiceResult.ok() / ServiceResult.err() instead
  of inline dict literals।  All logging uses DjoyaltyBaseService._log() /
  ._warn() / ._err_log() instead of repeated logger.xxx() calls।
  LoyaltyPoints lookup uses DjoyaltyBaseService._get_loyalty_points()。

Before DRY fix — scattered in this file:
    return {'success': False, 'error': '...'}   × 6 times
    return {'success': True, 'cashout': ...}     × 1 time
    logger.warning('CashoutService...: %s', ...)  × 4 times
    logger.info('CashoutService...: %s ...', ...) × 1 time
    logger.error('CashoutService...: %s', ...)    × 3 times
    getattr(customer, 'tenant', None)             × 5 times

After DRY fix — all delegated to base class helpers।
"""
import uuid
import logging
from decimal import Decimal
from django.db import transaction
from .base import DjoyaltyBaseService
from ..service_result import ServiceResult

logger = logging.getLogger(__name__)


class CashoutService(DjoyaltyBaseService):
    """
    Single owner of all cashout operations。
    create_request() is the ONLY entry point for cashout creation。
    """

    @classmethod
    @transaction.atomic
    def create_request(cls, customer, points_to_redeem: Decimal,
                       cashout_method: str, bank_account=None,
                       mobile_wallet=None, rate=None, request=None) -> dict:
        """
        Create a cashout request atomically with full validation。

        Returns ServiceResult.ok(...) or ServiceResult.err(...)。
        """
        from ..models.cashout import CashoutRequest, CashoutRate, WalletTransaction
        from ..models.points import LoyaltyPoints, PointsLedger
        from ..validator import LoyaltyValidator
        from ..exceptions import InsufficientPointsError

        # ── 1. Pending-duplicate guard ─────────────────────────────────────
        if CashoutRequest.objects.filter(
            customer=customer, status__in=['pending', 'approved'],
        ).exists():
            cls._warn('create_request: duplicate pending cashout blocked for %s', customer.code)
            return cls._err(
                'A cashout request is already pending for this customer. '
                'Please wait for it to be processed before submitting a new request.',
                code='DUPLICATE_PENDING',
            )

        # ── 2. Business rule validation ────────────────────────────────────
        is_valid, error_msg = LoyaltyValidator.validate_cashout(
            customer=customer, points=points_to_redeem, method=cashout_method,
        )
        if not is_valid:
            cls._warn('create_request: validation failed for %s — %s', customer.code, error_msg)
            return cls._err(error_msg, code='VALIDATION_FAILED')

        # ── 3. Sanctions check ─────────────────────────────────────────────
        try:
            from ..sanctions import SanctionManager
            sanctioned, sanction_reason = SanctionManager.check(customer)
            if sanctioned:
                cls._warn('create_request: sanctions block for %s — %s', customer.code, sanction_reason)
                return cls._err(f'Cashout blocked: {sanction_reason}', code='SANCTIONS_BLOCK')
        except ImportError:
            pass
        except Exception as sanction_err:
            cls._warn('create_request: sanctions check error: %s', sanction_err)

        # ── 4. Rate lookup ─────────────────────────────────────────────────
        if rate is None:
            rate = CashoutRate.objects.filter(
                is_active=True, cashout_method=cashout_method,
            ).order_by('-effective_from').first()

        if not rate:
            return cls._err(f'Cashout not available for method: {cashout_method}', code='NO_RATE')

        if points_to_redeem < rate.min_cashout_points:
            return cls._err(
                f'Minimum cashout is {rate.min_cashout_points} points.',
                code='BELOW_MINIMUM',
            )

        cash_amount     = (points_to_redeem / rate.points_per_unit).quantize(Decimal('0.01'))
        conversion_rate = (Decimal('1') / rate.points_per_unit).quantize(Decimal('0.000001'))

        # ── 5. select_for_update() lock on LoyaltyPoints ──────────────────
        lp = cls._get_loyalty_points(customer, select_for_update=True)
        if not lp:
            return cls._err('Points wallet not found for customer.', code='NO_WALLET')

        # ── 6. Balance check against locked row ────────────────────────────
        available = lp.available_balance
        if available < points_to_redeem:
            return cls._err(
                f'Insufficient available balance: {available} available, '
                f'{points_to_redeem} required.',
                code='INSUFFICIENT_BALANCE',
            )

        # ── 7. Deduct points ───────────────────────────────────────────────
        balance_before   = lp.balance
        lp.balance      -= points_to_redeem
        lp.lifetime_redeemed += points_to_redeem
        lp.save(update_fields=['balance', 'lifetime_redeemed', 'updated_at'])
        balance_after = lp.balance

        # ── 8. Create CashoutRequest ───────────────────────────────────────
        tenant    = cls._resolve_tenant(customer=customer, request=request)
        reference = f'CO-{uuid.uuid4().hex.upper()}'
        cashout   = CashoutRequest.objects.create(
            customer=customer, tenant=tenant,
            points_to_redeem=points_to_redeem, cash_amount=cash_amount,
            conversion_rate=conversion_rate, currency='BDT',
            cashout_method=cashout_method, bank_account=bank_account,
            mobile_wallet=mobile_wallet, status='pending', reference=reference,
        )

        # ── 9. WalletTransaction record ────────────────────────────────────
        try:
            WalletTransaction.objects.create(
                customer=customer, tenant=tenant,
                transaction_type='cashout', points_delta=-points_to_redeem,
                cash_amount=cash_amount, currency='BDT',
                balance_before=balance_before, balance_after=balance_after,
                description=f'Cashout request {reference}',
                reference_id=reference, cashout_request=cashout,
            )
        except Exception as wallet_err:
            cls._err_log('WalletTransaction creation failed for %s: %s', reference, wallet_err)

        # ── 10. PointsLedger debit ─────────────────────────────────────────
        try:
            PointsLedger.objects.create(
                customer=customer, tenant=tenant, txn_type='debit',
                source='redemption', points=points_to_redeem,
                balance_after=balance_after,
                description=f'Cashout: {points_to_redeem} pts → {cash_amount} BDT',
                reference_id=reference,
            )
        except Exception as ledger_err:
            cls._err_log('PointsLedger entry failed for %s: %s', reference, ledger_err)

        # ── 11. Notification ───────────────────────────────────────────────
        try:
            from .NotificationTriggerService import NotificationTriggerService
            NotificationTriggerService.send(
                customer=customer, event='cashout_requested',
                context={'reference': reference, 'points': str(points_to_redeem),
                         'cash_amount': str(cash_amount), 'method': cashout_method},
            )
        except Exception as notif_err:
            cls._warn('notification failed for %s: %s', reference, notif_err)

        cls._log('create_request: SUCCESS — customer=%s ref=%s pts=%s cash=%s method=%s',
                 customer.code, reference, points_to_redeem, cash_amount, cashout_method)

        return cls._ok(
            cashout=cashout, reference=reference,
            cash_amount=str(cash_amount),
            points_deducted=str(points_to_redeem),
            balance_after=str(balance_after),
        )

    @classmethod
    @transaction.atomic
    def add_bank_account(cls, customer, data: dict, tenant=None):
        """Register a new bank account for a customer。"""
        from ..models.cashout import CustomerBankAccount
        is_primary = data.get('is_primary', False)
        if is_primary:
            CustomerBankAccount.objects.filter(
                customer=customer, is_primary=True,
            ).update(is_primary=False)
        account = CustomerBankAccount.objects.create(
            customer=customer,
            tenant=tenant or cls._resolve_tenant(customer=customer),
            bank_name=data.get('bank_name', ''),
            account_number=data.get('account_number', ''),
            account_holder_name=data.get('account_holder_name', ''),
            routing_number=data.get('routing_number'),
            branch_name=data.get('branch_name'),
            is_primary=is_primary,
        )
        cls._log('add_bank_account: customer=%s bank=%s primary=%s',
                 customer.code, account.bank_name, is_primary)
        return account

    @classmethod
    @transaction.atomic
    def add_mobile_wallet(cls, customer, data: dict, tenant=None):
        """Register a new mobile wallet for a customer。"""
        from ..models.cashout import CustomerMobileWallet
        provider   = data.get('wallet_provider', 'bkash')
        phone      = data.get('phone_number', '')
        is_primary = data.get('is_primary', False)
        if CustomerMobileWallet.objects.filter(
            customer=customer, wallet_provider=provider, phone_number=phone,
        ).exists():
            raise ValueError(
                f'Mobile wallet {phone} ({provider}) is already registered for this customer.'
            )
        if is_primary:
            CustomerMobileWallet.objects.filter(
                customer=customer, is_primary=True,
            ).update(is_primary=False)
        wallet = CustomerMobileWallet.objects.create(
            customer=customer,
            tenant=tenant or cls._resolve_tenant(customer=customer),
            wallet_provider=provider, phone_number=phone,
            account_name=data.get('account_name'), is_primary=is_primary,
        )
        cls._log('add_mobile_wallet: customer=%s provider=%s primary=%s',
                 customer.code, provider, is_primary)
        return wallet

    @classmethod
    def get_customer_rate(cls, customer, cashout_method: str):
        """Look up the applicable CashoutRate for a customer and method。"""
        from ..models.cashout import CashoutRate
        qs = CashoutRate.objects.filter(
            is_active=True, cashout_method=cashout_method,
        ).order_by('-effective_from')
        try:
            from ..models.tiers import UserTier
            user_tier = UserTier.objects.filter(customer=customer).select_related('tier').first()
            if user_tier and user_tier.tier:
                tier_rate = qs.filter(min_tier_required=user_tier.tier).first()
                if tier_rate:
                    return tier_rate
        except Exception:
            pass
        return qs.first()

    @classmethod
    def validate_destination(cls, customer, bank_account_id=None, mobile_wallet_id=None):
        """Validate that the cashout destination belongs to this customer。"""
        from ..models.cashout import CustomerBankAccount, CustomerMobileWallet
        bank_account  = None
        mobile_wallet = None
        if bank_account_id:
            bank_account = CustomerBankAccount.objects.filter(
                pk=bank_account_id, customer=customer, is_active=True,
            ).first()
            if not bank_account:
                return None, None, 'Bank account not found or does not belong to this customer.'
        if mobile_wallet_id:
            mobile_wallet = CustomerMobileWallet.objects.filter(
                pk=mobile_wallet_id, customer=customer, is_active=True,
            ).first()
            if not mobile_wallet:
                return None, None, 'Mobile wallet not found or does not belong to this customer.'
        return bank_account, mobile_wallet, None
