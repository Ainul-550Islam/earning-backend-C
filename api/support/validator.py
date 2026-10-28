# api/support/validator.py
import re
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError


def validate_ticket_subject(value):
    value = (value or '').strip()
    if len(value) < 5:
        raise ValidationError('Subject must be at least 5 characters.')
    if len(value) > 200:
        raise ValidationError('Subject too long (max 200).')
    return value


def validate_ticket_description(value):
    value = (value or '').strip()
    if len(value) < 10:
        raise ValidationError('Description must be at least 10 characters.')
    return value


def validate_dispute_amount(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValidationError('Amount must be a valid number.')
    if amount < 10:
        raise ValidationError('Amount must be at least 10.')
    if amount > Decimal('100000'):
        raise ValidationError('Amount too large (max 100,000).')
    return amount


def validate_csat_rating(value):
    try:
        score = int(value)
    except (TypeError, ValueError):
        raise ValidationError('Rating must be an integer.')
    if not 1 <= score <= 5:
        raise ValidationError('Rating must be between 1 and 5.')
    return score


def validate_attachment(file):
    if file.size > 10 * 1024 * 1024:
        raise ValidationError('File exceeds 10MB limit.')


def validate_offer_id(value):
    value = (value or '').strip()
    if not value:
        raise ValidationError('Offer ID is required.')
    if len(value) > 200:
        raise ValidationError('Offer ID too long.')
    return value


def validate_transaction_id(value):
    value = (value or '').strip()
    if not value:
        raise ValidationError('Transaction ID is required.')
    return value