# api/support/integrations/data_validator.py  — WORLD #1
"""
Data Validator — তোমার apps থেকে আসা data validate করে।
Support system receives data from: postback, fraud, wallet, KYC.
এখানে সব validation logic আছে।
"""
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)


class IntegrationDataValidator:
    """Validates data exchanged between support and other apps."""

    # ── Offer Dispute Validation ──────────────────────
    def validate_offer_dispute(self, data: dict) -> Tuple[bool, str, dict]:
        """
        Validate offer dispute submission.
        Returns: (is_valid, error_message, cleaned_data)
        """
        cleaned = {}
        errors  = []

        # offer_id
        offer_id = (data.get('offer_id') or '').strip()
        if not offer_id:
            errors.append('offer_id is required.')
        elif len(offer_id) > 200:
            errors.append('offer_id too long (max 200).')
        else:
            cleaned['offer_id'] = offer_id

        # expected_amount
        amount_raw = data.get('expected_amount', 0)
        try:
            amount = Decimal(str(amount_raw))
            if amount <= 0:
                errors.append('expected_amount must be positive.')
            elif amount > Decimal('100000'):
                errors.append('expected_amount too large (max 100,000).')
            else:
                cleaned['expected_amount'] = amount
        except InvalidOperation:
            errors.append('expected_amount must be a valid number.')

        # click_id (optional but validated)
        click_id = (data.get('click_id') or '').strip()
        if click_id and len(click_id) > 200:
            errors.append('click_id too long (max 200).')
        else:
            cleaned['click_id'] = click_id

        # offer_name (optional)
        cleaned['offer_name'] = (data.get('offer_name') or '')[:500]

        # description
        description = (data.get('description') or '').strip()
        if len(description) < 10:
            errors.append('description must be at least 10 characters.')
        elif len(description) > 5000:
            errors.append('description too long (max 5,000).')
        else:
            cleaned['description'] = description

        if errors:
            return False, ' | '.join(errors), cleaned

        return True, '', cleaned

    # ── Withdrawal Dispute Validation ─────────────────
    def validate_withdrawal_dispute(self, data: dict) -> Tuple[bool, str, dict]:
        """Validate withdrawal dispute data."""
        cleaned = {}
        errors  = []

        transaction_id = (data.get('transaction_id') or '').strip()
        if not transaction_id:
            errors.append('transaction_id is required.')
        elif len(transaction_id) > 200:
            errors.append('transaction_id too long.')
        else:
            cleaned['transaction_id'] = transaction_id

        amount_raw = data.get('amount', 0)
        try:
            amount = Decimal(str(amount_raw))
            if amount <= 0:
                errors.append('amount must be positive.')
            else:
                cleaned['amount'] = amount
        except InvalidOperation:
            errors.append('amount must be a valid number.')

        payment_method = (data.get('payment_method') or '').strip()
        VALID_METHODS  = ['bkash', 'nagad', 'rocket', 'bank_transfer', 'paypal', 'other']
        if payment_method and payment_method.lower() not in VALID_METHODS:
            cleaned['payment_method'] = 'other'
        else:
            cleaned['payment_method'] = payment_method or 'other'

        account_number = (data.get('account_number') or '').strip()
        if account_number:
            # Basic format validation
            if not re.match(r'^[\d\+\-\s\w@.]{5,100}$', account_number):
                errors.append('account_number format is invalid.')
            else:
                cleaned['account_number'] = account_number
        else:
            cleaned['account_number'] = ''

        description = (data.get('description') or '').strip()
        cleaned['description'] = description[:5000]

        if errors:
            return False, ' | '.join(errors), cleaned
        return True, '', cleaned

    # ── Ticket Validation ─────────────────────────────
    def validate_ticket_data(self, data: dict) -> Tuple[bool, str, dict]:
        """Validate ticket creation data."""
        cleaned = {}
        errors  = []

        subject = (data.get('subject') or '').strip()
        if len(subject) < 5:
            errors.append('subject must be at least 5 characters.')
        elif len(subject) > 200:
            errors.append('subject too long (max 200).')
        else:
            cleaned['subject'] = subject

        description = (data.get('description') or '').strip()
        if len(description) < 10:
            errors.append('description must be at least 10 characters.')
        elif len(description) > 10000:
            errors.append('description too long (max 10,000).')
        else:
            cleaned['description'] = description

        VALID_CATEGORIES = [
            'payment','coins','account','technical','other',
            'withdrawal','fraud','kyc','referral','offer',
        ]
        category = data.get('category', 'other')
        cleaned['category'] = category if category in VALID_CATEGORIES else 'other'

        VALID_PRIORITIES = ['low','medium','high','urgent']
        priority = data.get('priority', 'medium')
        cleaned['priority'] = priority if priority in VALID_PRIORITIES else 'medium'

        VALID_CHANNELS = ['web','email','telegram','whatsapp','facebook','chat','api']
        channel = data.get('channel', 'web')
        cleaned['channel'] = channel if channel in VALID_CHANNELS else 'web'

        if errors:
            return False, ' | '.join(errors), cleaned
        return True, '', cleaned

    # ── Wallet Credit Validation ───────────────────────
    def validate_wallet_credit(self, amount: Any, reason: str = '') -> Tuple[bool, str, Decimal]:
        """Validate a wallet credit operation."""
        try:
            amount = Decimal(str(amount))
            if amount <= 0:
                return False, 'Amount must be positive.', Decimal(0)
            if amount > Decimal('100000'):
                return False, 'Amount too large (max 100,000 coins per transaction).', Decimal(0)
            if not reason or len(reason.strip()) < 3:
                return False, 'Reason is required.', Decimal(0)
            return True, '', amount
        except InvalidOperation:
            return False, 'Invalid amount format.', Decimal(0)

    # ── Webhook Payload Validation ─────────────────────
    def validate_webhook_payload(self, payload: dict, required_fields: list = None) -> Tuple[bool, str]:
        """Validate incoming webhook payload from external systems."""
        if not isinstance(payload, dict):
            return False, 'Payload must be a JSON object.'
        if required_fields:
            missing = [f for f in required_fields if f not in payload]
            if missing:
                return False, f'Missing required fields: {", ".join(missing)}'
        return True, ''

    # ── CSAT Rating Validation ─────────────────────────
    def validate_csat_rating(self, score: Any) -> Tuple[bool, str, int]:
        """Validate CSAT rating (1-5)."""
        try:
            score = int(score)
            if not 1 <= score <= 5:
                return False, 'Score must be between 1 and 5.', 0
            return True, '', score
        except (TypeError, ValueError):
            return False, 'Score must be an integer.', 0


# Singleton
data_validator = IntegrationDataValidator()