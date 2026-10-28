# api/support/validators/chat.py
"""Chat-specific validators."""
from django.core.exceptions import ValidationError


def validate_chat_message(content: str) -> str:
    """Validate a chat message."""
    content = (content or '').strip()
    if not content:
        raise ValidationError('Message cannot be empty.')
    if len(content) > 5000:
        raise ValidationError('Message too long (max 5,000 characters).')
    return content


def validate_chat_rating(score) -> int:
    """Validate chat session rating (1-5)."""
    try:
        score = int(score)
    except (TypeError, ValueError):
        raise ValidationError('Rating must be an integer.')
    if not 1 <= score <= 5:
        raise ValidationError('Rating must be between 1 and 5.')
    return score


def validate_session_id(session_id: str) -> str:
    """Validate chat session UUID format."""
    import re
    if not session_id:
        raise ValidationError('Session ID is required.')
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if not re.match(uuid_pattern, str(session_id).lower()):
        raise ValidationError('Invalid session ID format.')
    return str(session_id)