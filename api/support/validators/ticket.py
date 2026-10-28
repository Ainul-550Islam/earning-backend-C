# api/support/validators/ticket.py
"""Ticket-specific validators."""
import re
from django.core.exceptions import ValidationError
from api.support.constants import MAX_SUBJECT_LENGTH, MAX_DESCRIPTION_LENGTH

VALID_CATEGORIES = [
    'payment', 'coins', 'account', 'technical', 'other',
    'withdrawal', 'fraud', 'kyc', 'referral', 'offer',
]
VALID_PRIORITIES = ['low', 'medium', 'high', 'urgent']
VALID_CHANNELS   = ['web', 'email', 'telegram', 'whatsapp', 'facebook', 'chat', 'api']


def validate_subject(value: str) -> str:
    value = (value or '').strip()
    if len(value) < 5:
        raise ValidationError('Subject must be at least 5 characters.')
    if len(value) > MAX_SUBJECT_LENGTH:
        raise ValidationError(f'Subject cannot exceed {MAX_SUBJECT_LENGTH} characters.')
    return value


def validate_description(value: str) -> str:
    value = (value or '').strip()
    if len(value) < 10:
        raise ValidationError('Description must be at least 10 characters.')
    if len(value) > MAX_DESCRIPTION_LENGTH:
        raise ValidationError(f'Description cannot exceed {MAX_DESCRIPTION_LENGTH} characters.')
    return value


def validate_category(value: str) -> str:
    value = (value or '').strip().lower()
    if value not in VALID_CATEGORIES:
        raise ValidationError(f'Invalid category. Choose from: {", ".join(VALID_CATEGORIES)}')
    return value


def validate_priority(value: str) -> str:
    value = (value or '').strip().lower()
    if value not in VALID_PRIORITIES:
        raise ValidationError(f'Invalid priority. Choose from: {", ".join(VALID_PRIORITIES)}')
    return value


def validate_channel(value: str) -> str:
    value = (value or '').strip().lower()
    if value not in VALID_CHANNELS:
        return 'web'
    return value


def validate_rating(value) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        raise ValidationError('Rating must be an integer.')
    if not 1 <= score <= 5:
        raise ValidationError('Rating must be between 1 and 5.')
    return score