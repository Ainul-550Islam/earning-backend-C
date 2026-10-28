# api/support/utils.py  — WORLD #1 COMPLETE
"""Utility functions for support system."""
import logging
import random
import re
import string
from datetime import timedelta
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)

SITE_URL  = getattr(settings, 'SITE_URL', 'https://yoursite.com')
SITE_NAME = getattr(settings, 'SITE_NAME', 'Support')


# ── Ticket ID Generation ──────────────────────────────
def generate_ticket_id() -> str:
    """Generate unique ticket ID: TKT + 6 random digits"""
    return f"TKT{random.randint(100000, 999999)}"


def generate_unique_ticket_id() -> str:
    """Generate and verify uniqueness"""
    from api.support.models import SupportTicket
    for _ in range(10):
        ticket_id = generate_ticket_id()
        if not SupportTicket.objects.filter(ticket_id=ticket_id).exists():
            return ticket_id
    # Fallback: use timestamp
    import time
    return f"TKT{int(time.time()) % 1000000:06d}"


# ── Time Utilities ────────────────────────────────────
def format_duration(seconds: float) -> str:
    """Format seconds into human-readable duration."""
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds/60)}m"
    if seconds < 86400:
        h = int(seconds/3600)
        m = int((seconds % 3600) / 60)
        return f"{h}h {m}m" if m else f"{h}h"
    d = int(seconds/86400)
    h = int((seconds % 86400) / 3600)
    return f"{d}d {h}h" if h else f"{d}d"


def time_ago(dt) -> str:
    """Human-readable time ago string."""
    diff = (timezone.now() - dt).total_seconds()
    if diff < 60:     return 'just now'
    if diff < 3600:   return f'{int(diff/60)}m ago'
    if diff < 86400:  return f'{int(diff/3600)}h ago'
    if diff < 604800: return f'{int(diff/86400)}d ago'
    return dt.strftime('%d %b %Y')


def business_hours_between(start_dt, end_dt, start_hour: int = 9, end_hour: int = 18) -> float:
    """Calculate business hours between two datetimes (in hours)."""
    total = 0.0
    current = start_dt
    while current < end_dt:
        hour = current.hour
        if start_hour <= hour < end_hour and current.weekday() < 5:  # Mon-Fri
            next_tick = min(current + timedelta(hours=1), end_dt)
            total += (next_tick - current).total_seconds() / 3600
        current += timedelta(hours=1)
    return round(total, 2)


# ── Text Utilities ────────────────────────────────────
def truncate(text: str, length: int = 100, suffix: str = '...') -> str:
    """Truncate text to length."""
    if not text:
        return ''
    return text[:length] + suffix if len(text) > length else text


def sanitize_html(text: str) -> str:
    """Basic HTML sanitization (strip tags)."""
    return re.sub(r'<[^>]+>', '', text or '')


def extract_email_from_text(text: str) -> str | None:
    """Extract first email address from text."""
    match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text or '')
    return match.group(0) if match else None


def slug_from_title(title: str) -> str:
    """Generate URL slug from title."""
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[\s_-]+', '-', slug)
    return slug.strip('-')[:100]


# ── URL Helpers ───────────────────────────────────────
def ticket_url(ticket_id: str) -> str:
    return f"{SITE_URL}/support/tickets/{ticket_id}/"


def ticket_admin_url(ticket_id: str) -> str:
    return f"{SITE_URL}/admin/support/supportticket/?search={ticket_id}"


def kb_article_url(slug: str) -> str:
    return f"{SITE_URL}/support/kb/{slug}/"


def ticket_rate_url(ticket_id: str) -> str:
    return f"{SITE_URL}/support/tickets/{ticket_id}/rate/"


# ── Priority Utilities ────────────────────────────────
def get_priority_from_category(category: str) -> str:
    """Get default priority for a ticket category."""
    from api.support.choices import CATEGORY_PRIORITY_MAP
    return CATEGORY_PRIORITY_MAP.get(category, 'medium')


def get_priority_color(priority: str) -> str:
    """Return color for priority level."""
    return {
        'urgent': '#dc2626',
        'high':   '#ea580c',
        'medium': '#ca8a04',
        'low':    '#16a34a',
    }.get(priority, '#6b7280')


def get_status_emoji(status: str) -> str:
    """Return emoji for ticket status."""
    return {
        'open':         '🟡',
        'in_progress':  '🔵',
        'waiting_user': '🟠',
        'resolved':     '✅',
        'closed':       '⛔',
        'spam':         '🚫',
    }.get(status, '❓')


# ── Tenant Helpers ────────────────────────────────────
def get_user_tenant(user):
    """Safely get tenant from user."""
    return getattr(user, 'tenant', None)


# ── IP Helper ─────────────────────────────────────────
def get_client_ip(request) -> str:
    """Get real client IP from request."""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


# ── Phone Formatting ──────────────────────────────────
def format_phone_bd(phone: str) -> str:
    """Format Bangladesh phone number to international format."""
    phone = re.sub(r'[^\d+]', '', phone)
    if phone.startswith('01') and len(phone) == 11:
        return '+880' + phone[1:]
    if not phone.startswith('+'):
        return '+' + phone
    return phone


# ── Metrics ───────────────────────────────────────────
def calculate_csat_nps(ratings: list) -> dict:
    """Calculate NPS from list of 1-5 ratings."""
    if not ratings:
        return {'avg': 0, 'nps': 0, 'total': 0}
    total      = len(ratings)
    avg        = sum(ratings) / total
    promoters  = sum(1 for r in ratings if r >= 5)
    detractors = sum(1 for r in ratings if r <= 2)
    nps        = round((promoters - detractors) / total * 100, 1)
    return {
        'avg':        round(avg, 2),
        'nps':        nps,
        'total':      total,
        'promoters':  promoters,
        'detractors': detractors,
        'passives':   total - promoters - detractors,
    }