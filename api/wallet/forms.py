# api/wallet/forms.py
"""
Production-ready forms for wallet app with strict validation.
Wallet limits, amount bounds, and payment method validation.
"""
import logging
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings

from .validators import validate_amount, safe_decimal

logger = logging.getLogger(__name__)


def _get_limits():
    try:
        return (
            getattr(settings, 'WALLET_WITHDRAWAL_MIN', Decimal('100.00')),
            getattr(settings, 'WALLET_WITHDRAWAL_MAX', Decimal('50000.00')),
            getattr(settings, 'WALLET_WITHDRAWAL_DAILY_LIMIT', Decimal('100000.00')),
        )
    except Exception:
        return Decimal('100.00'), Decimal('50000.00'), Decimal('100000.00')


WITHDRAWAL_MIN, WITHDRAWAL_MAX, WITHDRAWAL_DAILY_LIMIT = _get_limits()


class WithdrawalRequestForm(forms.Form):
    """User withdrawal request with strict validation."""
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=WITHDRAWAL_MIN,
        max_value=WITHDRAWAL_MAX,
        label='Amount',
        help_text=f'Between {WITHDRAWAL_MIN} and {WITHDRAWAL_MAX}'
    )
    method = forms.ChoiceField(
        choices=[
            ('bkash', 'bKash'),
            ('nagad', 'Nagad'),
            ('rocket', 'Rocket'),
            ('upay', 'Upay'),
            ('bank', 'Bank Account'),
        ],
        label='Payment method'
    )
    account_number = forms.CharField(
        max_length=50,
        min_length=10,
        strip=True,
        label='Account number'
    )
    account_name = forms.CharField(
        max_length=100,
        strip=True,
        required=False,
        label='Account holder name'
    )

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None:
            raise ValidationError('Invalid amount.')
        ok, msg, _ = validate_amount(
            amount,
            min_amount=WITHDRAWAL_MIN,
            max_amount=WITHDRAWAL_MAX
        )
        if not ok:
            raise ValidationError(msg)
        return amount

    def clean_account_number(self):
        value = (self.cleaned_data.get('account_number') or '').strip()
        if not value or len(value) < 10:
            raise ValidationError('Account number must be at least 10 characters.')
        if not value.replace(' ', '').replace('-', '').isdigit():
            raise ValidationError('Account number should contain only digits.')
        return value


class WalletAdminCreditForm(forms.Form):
    """Admin credit/debit form with validation."""
    amount = forms.DecimalField(max_digits=12, decimal_places=2, label='Amount')
    type = forms.ChoiceField(
        choices=[
            ('admin_credit', 'Credit'),
            ('admin_debit', 'Debit'),
        ],
        label='Type'
    )
    description = forms.CharField(max_length=255, required=True, strip=True)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None:
            raise ValidationError('Invalid amount.')
        amount = safe_decimal(amount)
        if amount == 0:
            raise ValidationError('Amount cannot be zero.')
        return amount
