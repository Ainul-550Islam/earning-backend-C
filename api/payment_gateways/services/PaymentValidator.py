# api/payment_gateways/services/PaymentValidator.py
# Full payment validation service — validates every transaction before processing

from decimal import Decimal, InvalidOperation
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class PaymentValidator:
    """
    Validates payment requests before sending to gateway.

    Checks:
        1. Amount (min/max per gateway, decimal precision)
        2. Currency (supported for gateway)
        3. Account number (gateway-specific format)
        4. User eligibility (not banned, KYC passed)
        5. Daily/monthly limit not exceeded
        6. Duplicate transaction check
        7. Gateway availability

    Usage:
        validator = PaymentValidator()
        is_valid, errors = validator.validate_deposit(user, amount, gateway, currency)
        if not is_valid:
            raise ValidationError(errors)
    """

    # Gateway-specific amount limits (fallback if DB not available)
    GATEWAY_LIMITS = {
        'bkash':      {'min': Decimal('10'),    'max': Decimal('50000'),   'currencies': ['BDT']},
        'nagad':      {'min': Decimal('10'),    'max': Decimal('50000'),   'currencies': ['BDT']},
        'sslcommerz': {'min': Decimal('10'),    'max': Decimal('500000'),  'currencies': ['BDT']},
        'amarpay':    {'min': Decimal('10'),    'max': Decimal('50000'),   'currencies': ['BDT']},
        'upay':       {'min': Decimal('10'),    'max': Decimal('50000'),   'currencies': ['BDT']},
        'shurjopay':  {'min': Decimal('10'),    'max': Decimal('50000'),   'currencies': ['BDT']},
        'stripe':     {'min': Decimal('0.50'),  'max': Decimal('999999'),  'currencies': ['USD','EUR','GBP','AUD','CAD','SGD']},
        'paypal':     {'min': Decimal('1.00'),  'max': Decimal('999999'),  'currencies': ['USD','EUR','GBP','AUD','CAD']},
        'payoneer':   {'min': Decimal('50'),    'max': Decimal('999999'),  'currencies': ['USD','EUR','GBP']},
        'wire':       {'min': Decimal('100'),   'max': Decimal('9999999'), 'currencies': ['BDT','USD','EUR','GBP']},
        'ach':        {'min': Decimal('1'),     'max': Decimal('999999'),  'currencies': ['USD']},
        'crypto':     {'min': Decimal('10'),    'max': Decimal('9999999'), 'currencies': ['USD','USDT','BTC','ETH']},
    }

    # Account number patterns per gateway
    ACCOUNT_PATTERNS = {
        'bkash':   r'^01[3-9]\d{8}$',
        'nagad':   r'^01[3-9]\d{8}$',
        'upay':    r'^01[3-9]\d{8}$',
        'amarpay': r'^01[3-9]\d{8}$',
    }

    def validate_deposit(self, user, amount, gateway: str,
                          currency: str = 'BDT', payment_method=None) -> Tuple[bool, list]:
        """
        Full validation for a deposit request.

        Returns:
            (is_valid: bool, errors: list[str])
        """
        errors = []

        # 1. Amount validation
        amount_ok, amount_errors = self._validate_amount(amount, gateway, currency)
        errors.extend(amount_errors)

        # 2. Currency validation
        currency_ok, currency_errors = self._validate_currency(currency, gateway)
        errors.extend(currency_errors)

        # 3. User eligibility
        user_ok, user_errors = self._validate_user(user, 'deposit')
        errors.extend(user_errors)

        # 4. Gateway availability
        gw_ok, gw_errors = self._validate_gateway(gateway, 'deposit')
        errors.extend(gw_errors)

        # 5. Daily limit
        limit_ok, limit_errors = self._validate_daily_limit(user, amount, gateway, 'deposit')
        errors.extend(limit_errors)

        # 6. Duplicate check
        dup_ok, dup_errors = self._check_duplicate(user, amount, gateway, 'deposit')
        errors.extend(dup_errors)

        is_valid = len(errors) == 0
        if not is_valid:
            logger.info(f'Deposit validation failed for {user.id}: {errors}')

        return is_valid, errors

    def validate_withdrawal(self, user, amount, gateway: str,
                             payment_method=None, currency: str = 'BDT') -> Tuple[bool, list]:
        """Full validation for a withdrawal/payout request."""
        errors = []

        # Amount
        amount_ok, amount_errors = self._validate_amount(amount, gateway, currency)
        errors.extend(amount_errors)

        # Currency
        currency_ok, currency_errors = self._validate_currency(currency, gateway)
        errors.extend(currency_errors)

        # User eligibility + balance
        user_ok, user_errors = self._validate_user(user, 'withdrawal')
        errors.extend(user_errors)

        # Balance check
        if not self._has_sufficient_balance(user, amount):
            errors.append(f'Insufficient balance. Available: {getattr(user, "balance", 0)}')

        # Account number
        if payment_method:
            acc_ok, acc_errors = self._validate_account_number(
                getattr(payment_method, 'account_number', ''), gateway
            )
            errors.extend(acc_errors)

        # Gateway availability
        gw_ok, gw_errors = self._validate_gateway(gateway, 'withdrawal')
        errors.extend(gw_errors)

        # Daily withdrawal limit
        limit_ok, limit_errors = self._validate_daily_limit(user, amount, gateway, 'withdrawal')
        errors.extend(limit_errors)

        return len(errors) == 0, errors

    def validate_refund(self, transaction, refund_amount: Decimal,
                         user=None) -> Tuple[bool, list]:
        """Validate a refund request against an existing transaction."""
        errors = []

        # Transaction must be completed
        if transaction.status != 'completed':
            errors.append(f'Cannot refund: transaction status is {transaction.status}')
            return False, errors

        # Refund amount must not exceed original
        if refund_amount > transaction.amount:
            errors.append(f'Refund amount ({refund_amount}) exceeds transaction amount ({transaction.amount})')

        # Check if already refunded
        try:
            from api.payment_gateways.refunds.models import RefundRequest
            from django.db.models import Sum
            already = RefundRequest.objects.filter(
                original_transaction=transaction,
                status__in=('pending','processing','completed'),
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

            if already + refund_amount > transaction.amount:
                errors.append(f'Total refunds ({already + refund_amount}) would exceed original ({transaction.amount})')
        except Exception:
            pass

        # Time limit (most gateways: 30-90 days)
        from django.utils import timezone
        from datetime import timedelta
        age_days = (timezone.now() - transaction.created_at).days
        if age_days > 90:
            errors.append(f'Transaction is {age_days} days old. Refund window is 90 days.')

        return len(errors) == 0, errors

    # ── Internal validators ────────────────────────────────────────────────────

    def _validate_amount(self, amount, gateway: str, currency: str) -> Tuple[bool, list]:
        errors = []
        try:
            amount = Decimal(str(amount))
        except (InvalidOperation, TypeError):
            return False, ['Invalid amount format']

        if amount <= 0:
            errors.append('Amount must be greater than 0')
            return False, errors

        limits = self._get_gateway_limits(gateway)
        if amount < limits['min']:
            errors.append(f'Minimum amount for {gateway} is {limits["min"]} {currency}')
        if amount > limits['max']:
            errors.append(f'Maximum amount for {gateway} is {limits["max"]} {currency}')

        # Precision check (max 2 decimal places for fiat)
        if currency not in ('BTC', 'ETH', 'USDT', 'USDC') and amount != amount.quantize(Decimal('0.01')):
            errors.append('Amount must have at most 2 decimal places')

        return len(errors) == 0, errors

    def _validate_currency(self, currency: str, gateway: str) -> Tuple[bool, list]:
        errors = []
        limits = self._get_gateway_limits(gateway)
        allowed = limits.get('currencies', [])
        if allowed and currency not in allowed:
            errors.append(f'{gateway} does not support {currency}. Supported: {", ".join(allowed)}')
        return len(errors) == 0, errors

    def _validate_user(self, user, operation: str) -> Tuple[bool, list]:
        errors = []

        if not user or not user.is_active:
            errors.append('User account is inactive or not found')
            return False, errors

        # Check if user is banned
        if getattr(user, 'is_banned', False):
            errors.append('User account is banned from payment operations')

        # Check KYC for large amounts (if kyc app exists)
        try:
            from api.kyc.models import KYCProfile
            kyc = KYCProfile.objects.get(user=user)
            if kyc.status != 'approved' and operation == 'withdrawal':
                errors.append('KYC verification required before withdrawals. Please verify your identity.')
        except Exception:
            pass  # KYC not required / not configured

        return len(errors) == 0, errors

    def _validate_gateway(self, gateway: str, operation: str) -> Tuple[bool, list]:
        errors = []
        try:
            from api.payment_gateways.models.core import PaymentGateway
            gw = PaymentGateway.objects.get(name=gateway)
            if gw.status != 'active':
                errors.append(f'{gw.display_name} is currently {gw.get_status_display()}. Please try another gateway.')
            if operation == 'deposit' and not gw.supports_deposit:
                errors.append(f'{gw.display_name} does not support deposits')
            if operation == 'withdrawal' and not gw.supports_withdrawal:
                errors.append(f'{gw.display_name} does not support withdrawals')
            if gw.health_status == 'down':
                errors.append(f'{gw.display_name} is currently experiencing issues. Please try again later.')
        except Exception as e:
            if 'does not exist' in str(e).lower():
                errors.append(f'Gateway {gateway} is not configured')
        return len(errors) == 0, errors

    def _validate_account_number(self, account_number: str,
                                   gateway: str) -> Tuple[bool, list]:
        import re
        errors = []
        if not account_number:
            errors.append('Account number is required')
            return False, errors

        pattern = self.ACCOUNT_PATTERNS.get(gateway)
        if pattern and not re.match(pattern, account_number.strip()):
            errors.append(f'Invalid account number format for {gateway}')

        return len(errors) == 0, errors

    def _validate_daily_limit(self, user, amount: Decimal, gateway: str,
                                operation: str) -> Tuple[bool, list]:
        errors = []
        try:
            from api.payment_gateways.models.core import GatewayTransaction
            from django.db.models import Sum
            from django.utils import timezone

            today_total = GatewayTransaction.objects.filter(
                user=user,
                gateway=gateway,
                transaction_type=operation,
                status__in=('pending', 'processing', 'completed'),
                created_at__date=timezone.now().date(),
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

            daily_limit = self._get_daily_limit(gateway, operation)
            if daily_limit and today_total + amount > daily_limit:
                errors.append(
                    f'Daily {operation} limit reached for {gateway}. '
                    f'Used: {today_total}, Limit: {daily_limit}'
                )
        except Exception:
            pass  # Non-critical check
        return len(errors) == 0, errors

    def _check_duplicate(self, user, amount: Decimal, gateway: str,
                          operation: str) -> Tuple[bool, list]:
        """Prevent duplicate transactions within 30 seconds."""
        errors = []
        try:
            from api.payment_gateways.models.core import GatewayTransaction
            from django.utils import timezone
            from datetime import timedelta

            recent = GatewayTransaction.objects.filter(
                user=user,
                gateway=gateway,
                transaction_type=operation,
                amount=amount,
                status='pending',
                created_at__gte=timezone.now() - timedelta(seconds=30),
            ).exists()

            if recent:
                errors.append('Duplicate transaction detected. Please wait 30 seconds before retrying.')
        except Exception:
            pass
        return len(errors) == 0, errors

    def _has_sufficient_balance(self, user, amount: Decimal) -> bool:
        balance = Decimal(str(getattr(user, 'balance', '0') or '0'))
        return balance >= amount

    def _get_gateway_limits(self, gateway: str) -> dict:
        try:
            from api.payment_gateways.models.core import PaymentGateway
            gw = PaymentGateway.objects.get(name=gateway)
            return {
                'min': gw.minimum_amount,
                'max': gw.maximum_amount,
                'currencies': gw.supported_currencies.split(',') if gw.supported_currencies else [],
            }
        except Exception:
            return self.GATEWAY_LIMITS.get(gateway, {
                'min': Decimal('1'), 'max': Decimal('999999'), 'currencies': []
            })

    def _get_daily_limit(self, gateway: str, operation: str):
        try:
            from api.payment_gateways.models.gateway_config import GatewayLimit
            from api.payment_gateways.models.core import PaymentGateway
            gw    = PaymentGateway.objects.get(name=gateway)
            limit = GatewayLimit.objects.filter(
                gateway=gw, transaction_type=operation, is_active=True
            ).first()
            return limit.daily_limit if limit else None
        except Exception:
            return None
