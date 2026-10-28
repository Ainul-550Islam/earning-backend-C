# api/support/helpers.py
"""
Shared helper functions for support system.
Pure utility functions — no model imports at module level.
"""
import re
import logging
import hashlib
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── String helpers ────────────────────────────────────────────
def truncate(text: str, max_len: int = 100, suffix: str = '...') -> str:
    """Truncate text to max_len characters."""
    if not text:
        return ''
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len - len(suffix)] + suffix


def clean_text(text: str) -> str:
    """Remove excessive whitespace and normalize text."""
    if not text:
        return ''
    # Collapse multiple spaces/newlines
    return re.sub(r'\s+', ' ', text.strip())


def mask_email(email: str) -> str:
    """Mask email for display: ab***@gmail.com"""
    if not email or '@' not in email:
        return email or ''
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        return f'{local}***@{domain}'
    return f'{local[:2]}***@{domain}'


def mask_phone(phone: str) -> str:
    """Mask phone number: +880 ******* 89"""
    if not phone:
        return ''
    digits = re.sub(r'\D', '', phone)
    if len(digits) < 4:
        return phone
    return f'{digits[:3]}{"*" * (len(digits)-5)}{digits[-2:]}'


def mask_account(account: str) -> str:
    """Mask financial account number for display."""
    if not account or len(account) < 4:
        return account or ''
    return f'{"*" * (len(account)-4)}{account[-4:]}'


# ── Ticket helpers ────────────────────────────────────────────
def format_ticket_id(raw_id: str) -> str:
    """Ensure ticket ID has TKT prefix."""
    if not raw_id:
        return ''
    raw_id = str(raw_id).strip().upper()
    if not raw_id.startswith('TKT'):
        raw_id = f'TKT{raw_id}'
    return raw_id


def ticket_id_is_valid(ticket_id: str) -> bool:
    """Validate ticket ID format."""
    if not ticket_id:
        return False
    return bool(re.match(r'^TKT\d{6,9}$', str(ticket_id).upper()))


def hours_to_human(hours: float) -> str:
    """Convert hours to human-readable: '2h 30m', '3 days', etc."""
    if hours < 0:
        return '0m'
    if hours < 1:
        mins = round(hours * 60)
        return f'{mins}m'
    if hours < 24:
        h = int(hours)
        m = round((hours - h) * 60)
        return f'{h}h {m}m' if m else f'{h}h'
    days = int(hours / 24)
    remaining_h = round(hours % 24)
    return f'{days}d {remaining_h}h' if remaining_h else f'{days}d'


# ── IP/security helpers ───────────────────────────────────────
def get_client_ip(request) -> str:
    """Extract real client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def is_private_ip(ip: str) -> bool:
    """Check if IP is a private/local address."""
    import ipaddress
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def hash_ip(ip: str) -> str:
    """Hash IP for privacy-safe storage."""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


# ── File helpers ──────────────────────────────────────────────
def get_file_extension(filename: str) -> str:
    """Get lowercase file extension: 'pdf', 'jpg', etc."""
    if not filename or '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[1].lower()


def is_image_file(filename: str) -> bool:
    """Check if file is an image by extension."""
    return get_file_extension(filename) in ('jpg', 'jpeg', 'png', 'gif', 'webp', 'svg')


def human_file_size(bytes_size: int) -> str:
    """Convert bytes to human size: '1.5 MB', '250 KB'."""
    if bytes_size < 1024:
        return f'{bytes_size} B'
    elif bytes_size < 1024 * 1024:
        return f'{round(bytes_size/1024, 1)} KB'
    elif bytes_size < 1024 * 1024 * 1024:
        return f'{round(bytes_size/1024/1024, 1)} MB'
    return f'{round(bytes_size/1024/1024/1024, 2)} GB'


# ── Data helpers ──────────────────────────────────────────────
def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert to int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_decimal(value: Any, default=None):
    """Safely convert to Decimal."""
    from decimal import Decimal, InvalidOperation
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return default or Decimal('0')


def flatten_errors(errors: dict) -> list:
    """Flatten DRF serializer errors to list of strings."""
    flat = []
    for field, msgs in errors.items():
        if isinstance(msgs, list):
            for msg in msgs:
                flat.append(f'{field}: {msg}')
        elif isinstance(msgs, dict):
            flat.extend(flatten_errors(msgs))
        else:
            flat.append(f'{field}: {msgs}')
    return flat


# ── Pagination helpers ────────────────────────────────────────
def paginate(queryset, page: int = 1, per_page: int = 20, max_per_page: int = 100):
    """Simple pagination helper. Returns (items, total, has_next, has_prev)."""
    per_page = min(int(per_page), max_per_page)
    page     = max(int(page), 1)
    total    = queryset.count()
    start    = (page - 1) * per_page
    items    = queryset[start:start + per_page]
    return items, total, start + per_page < total, page > 1


# ── Notification template helpers ─────────────────────────────
def render_ticket_email_subject(ticket) -> str:
    """Render email subject for ticket notifications."""
    return f'[Ticket #{ticket.ticket_id}] {ticket.subject or ticket.category}'


def render_ticket_email_body(ticket, message: str = '') -> str:
    """Render email body for ticket notifications."""
    lines = [
        f'Ticket ID: {ticket.ticket_id}',
        f'Category:  {ticket.get_category_display()}',
        f'Priority:  {ticket.get_priority_display()}',
        f'Status:    {ticket.get_status_display()}',
        '',
    ]
    if message:
        lines.append(message)
    lines.extend([
        '',
        '---',
        'This is an automated message from Support System.',
    ])
    return '\n'.join(lines)