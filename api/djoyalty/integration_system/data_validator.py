# api/djoyalty/integration_system/data_validator.py
"""
Data Validator -- Input/output validation for integration layer।
Validates postbacks, payment responses, webhook data।
"""
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple
from .integ_exceptions import IntegrationDataError

logger = logging.getLogger(__name__)


class ValidationResult:
    def __init__(self, valid: bool, errors: List[str] = None, data: dict = None):
        self.valid = valid
        self.errors = errors or []
        self.data = data or {}

    def __bool__(self):
        return self.valid

    def raise_if_invalid(self):
        if not self.valid:
            raise IntegrationDataError('; '.join(self.errors))


class DataValidator:
    """
    Validates data for integration operations।
    """

    # ─── Phone Validation ─────────────────────────────────────────

    @staticmethod
    def validate_bd_phone(phone: str) -> ValidationResult:
        """Validate Bangladesh phone number (bKash/Nagad)।"""
        if not phone:
            return ValidationResult(False, ['Phone number is required'])

        # Remove spaces and dashes
        clean = re.sub(r'[\s\-\(\)]', '', phone)

        # BD numbers: 01[3-9]XXXXXXXX (11 digits) or +8801[3-9]XXXXXXXX
        patterns = [
            r'^01[3-9]\d{8}$',      # 01XXXXXXXXX
            r'^\+8801[3-9]\d{8}$',  # +8801XXXXXXXXX
            r'^8801[3-9]\d{8}$',    # 8801XXXXXXXXX
        ]

        for pattern in patterns:
            if re.match(pattern, clean):
                # Normalize to 01XXXXXXXXX format
                if clean.startswith('+88'):
                    clean = clean[3:]
                elif clean.startswith('88'):
                    clean = clean[2:]
                return ValidationResult(True, data={'phone': clean})

        return ValidationResult(False, ['Invalid Bangladesh phone number'])

    # ─── Amount Validation ────────────────────────────────────────

    @staticmethod
    def validate_amount(amount: Any, min_amount: Decimal = Decimal('0'),
                         max_amount: Decimal = None,
                         currency: str = 'BDT') -> ValidationResult:
        """Validate monetary amount।"""
        try:
            amt = Decimal(str(amount))
        except (InvalidOperation, TypeError):
            return ValidationResult(False, [f'Invalid amount: {amount}'])

        if amt <= 0:
            return ValidationResult(False, ['Amount must be positive'])

        if amt < min_amount:
            return ValidationResult(False, [f'Amount {amt} is below minimum {min_amount}'])

        if max_amount and amt > max_amount:
            return ValidationResult(False, [f'Amount {amt} exceeds maximum {max_amount}'])

        return ValidationResult(True, data={'amount': amt, 'currency': currency})

    # ─── Postback Validation ──────────────────────────────────────

    @staticmethod
    def validate_postback(data: dict, provider: str = 'generic') -> ValidationResult:
        """Validate incoming postback data।"""
        errors = []

        # Required fields by provider
        required_by_provider = {
            'cpalead': ['subid', 'payout', 'transaction_id'],
            'tapjoy':  ['user_id', 'currency'],
            'xsolla':  ['user_id', 'transaction'],
            'generic': ['customer_ref', 'payout'],
        }

        required = required_by_provider.get(provider, ['customer_ref'])
        for field in required:
            if not data.get(field):
                errors.append(f'Missing required field: {field}')

        # Validate payout
        payout = data.get('payout') or data.get('currency') or data.get('amount', 0)
        try:
            payout_val = Decimal(str(payout))
            if payout_val < 0:
                errors.append('Payout cannot be negative')
        except InvalidOperation:
            errors.append(f'Invalid payout value: {payout}')

        if errors:
            return ValidationResult(False, errors)

        return ValidationResult(True, data=data)

    # ─── Payment Validation ───────────────────────────────────────

    @staticmethod
    def validate_payment_request(data: dict) -> ValidationResult:
        """Validate payment initiation request।"""
        errors = []

        if not data.get('amount'):
            errors.append('Amount is required')
        else:
            try:
                amt = Decimal(str(data['amount']))
                if amt <= 0:
                    errors.append('Amount must be positive')
            except InvalidOperation:
                errors.append(f'Invalid amount: {data["amount"]}')

        if not data.get('reference'):
            errors.append('Reference/order ID is required')

        if errors:
            return ValidationResult(False, errors)

        return ValidationResult(True)

    # ─── Customer Data Validation ─────────────────────────────────

    @staticmethod
    def validate_customer_for_cashout(customer) -> ValidationResult:
        """Validate customer is eligible for cashout।"""
        errors = []

        if not customer.is_active:
            errors.append('Customer account is not active')

        if not customer.is_verified:
            errors.append('Customer account is not verified')

        # Check fraud flags
        try:
            from ..models.advanced import PointsAbuseLog
            recent_flag = PointsAbuseLog.objects.filter(
                customer=customer,
                is_resolved=False,
                risk_level__in=['high', 'critical'],
            ).exists()
            if recent_flag:
                errors.append('Customer has unresolved fraud flags')
        except Exception:
            pass

        if errors:
            return ValidationResult(False, errors)
        return ValidationResult(True)

    # ─── Webhook Validation ───────────────────────────────────────

    @staticmethod
    def validate_webhook_url(url: str) -> ValidationResult:
        """Validate webhook URL format।"""
        if not url:
            return ValidationResult(False, ['URL is required'])

        pattern = r'^https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(/.*)?$'
        if not re.match(pattern, url):
            return ValidationResult(False, ['Invalid URL format'])

        if not url.startswith('https://') and not url.startswith('http://localhost'):
            return ValidationResult(
                False,
                ['Production webhook URLs must use HTTPS'],
            )

        return ValidationResult(True)

    # ─── Receipt Validation ───────────────────────────────────────

    @staticmethod
    def validate_receipt_submission(data: dict, customer) -> ValidationResult:
        """Validate receipt scan submission।"""
        errors = []

        if not data.get('receipt_image_url'):
            errors.append('Receipt image URL is required')

        # Check daily limit
        try:
            from django.utils import timezone
            from ..models.family_eco import ReceiptScan
            today_count = ReceiptScan.objects.filter(
                customer=customer,
                submitted_at__date=timezone.now().date(),
                status__in=['approved', 'pending', 'processing'],
            ).count()
            if today_count >= 5:
                errors.append('Daily receipt scan limit reached (max 5 per day)')
        except Exception:
            pass

        if errors:
            return ValidationResult(False, errors)
        return ValidationResult(True)
