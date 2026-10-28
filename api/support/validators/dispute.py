# api/support/validators/dispute.py
"""Dispute-specific validators."""
import re
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from api.support.constants import MIN_DISPUTE_AMOUNT


def validate_offer_dispute(data: dict) -> tuple:
    """
    Validate offer dispute data.
    Returns: (is_valid: bool, errors: dict, cleaned: dict)
    """
    errors  = {}
    cleaned = {}

    offer_id = (data.get('offer_id') or '').strip()
    if not offer_id:
        errors['offer_id'] = 'Offer ID is required.'
    elif len(offer_id) > 200:
        errors['offer_id'] = 'Offer ID too long (max 200).'
    else:
        cleaned['offer_id'] = offer_id

    try:
        amount = Decimal(str(data.get('expected_amount', 0)))
        if amount < MIN_DISPUTE_AMOUNT:
            errors['expected_amount'] = f'Amount must be at least {MIN_DISPUTE_AMOUNT}.'
        elif amount > Decimal('100000'):
            errors['expected_amount'] = 'Amount too large (max 100,000).'
        else:
            cleaned['expected_amount'] = amount
    except (InvalidOperation, TypeError):
        errors['expected_amount'] = 'Amount must be a valid number.'

    click_id = (data.get('click_id') or '').strip()
    if len(click_id) > 200:
        errors['click_id'] = 'Click ID too long (max 200).'
    else:
        cleaned['click_id'] = click_id

    description = (data.get('description') or '').strip()
    if len(description) < 10:
        errors['description'] = 'Description must be at least 10 characters.'
    elif len(description) > 5000:
        errors['description'] = 'Description too long (max 5,000).'
    else:
        cleaned['description'] = description

    cleaned['offer_name'] = (data.get('offer_name') or '')[:500]

    return len(errors) == 0, errors, cleaned


def validate_withdrawal_dispute(data: dict) -> tuple:
    """Validate withdrawal dispute data."""
    errors  = {}
    cleaned = {}

    txn_id = (data.get('transaction_id') or '').strip()
    if not txn_id:
        errors['transaction_id'] = 'Transaction ID is required.'
    elif not re.match(r'^[\w\-\.]{3,200}$', txn_id):
        errors['transaction_id'] = 'Invalid transaction ID format.'
    else:
        cleaned['transaction_id'] = txn_id

    try:
        amount = Decimal(str(data.get('amount', 0)))
        if amount <= 0:
            errors['amount'] = 'Amount must be positive.'
        else:
            cleaned['amount'] = amount
    except (InvalidOperation, TypeError):
        errors['amount'] = 'Amount must be a valid number.'

    method = (data.get('payment_method') or '').strip().lower()
    valid_methods = ['bkash', 'nagad', 'rocket', 'bank_transfer', 'paypal', 'other']
    cleaned['payment_method'] = method if method in valid_methods else 'other'

    account = (data.get('account_number') or '').strip()
    if account and len(account) > 100:
        errors['account_number'] = 'Account number too long.'
    else:
        cleaned['account_number'] = account

    return len(errors) == 0, errors, cleaned