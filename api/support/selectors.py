# api/support/selectors.py
"""
Selectors — read-only query layer (Clean Architecture pattern).
Services write. Selectors read.
All DB read queries live here — no business logic, no writes.
Views and APIs call selectors, not querysets directly.
"""
import logging
from typing import Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Ticket Selectors ──────────────────────────────────────────

def get_ticket_by_id(ticket_id: str):
    """Get single ticket by ticket_id (TKT...) or numeric id."""
    from api.support.models import SupportTicket
    try:
        if str(ticket_id).upper().startswith('TKT'):
            return SupportTicket.objects.select_related(
                'user', 'assigned_to', 'sla', 'tenant'
            ).get(ticket_id=ticket_id)
        return SupportTicket.objects.select_related(
            'user', 'assigned_to', 'sla', 'tenant'
        ).get(id=int(ticket_id))
    except (SupportTicket.DoesNotExist, ValueError, TypeError):
        return None


def get_ticket_for_user(ticket_id: str, user):
    """Get ticket only if user owns it or is staff."""
    ticket = get_ticket_by_id(ticket_id)
    if ticket is None:
        return None
    if user.is_staff or user.is_superuser or ticket.user == user:
        return ticket
    return None


def list_tickets_for_user(user, filters: dict = None):
    """All tickets for a non-staff user."""
    from api.support.models import SupportTicket
    from api.support.filters import SupportTicketFilter
    qs = SupportTicket.objects.filter(user=user).select_related(
        'assigned_to'
    ).order_by('-created_at')
    if filters:
        qs = SupportTicketFilter.apply(qs, filters)
    return qs


def list_tickets_for_agent(filters: dict = None, tenant=None):
    """All tickets for staff/agents (full access)."""
    from api.support.models import SupportTicket
    from api.support.filters import SupportTicketFilter
    qs = SupportTicket.objects.select_related(
        'user', 'assigned_to', 'sla'
    ).order_by('-created_at')
    if tenant:
        qs = qs.filter(tenant=tenant)
    if filters:
        qs = SupportTicketFilter.apply(qs, filters)
    return qs


def get_ticket_messages(ticket):
    """All messages for a ticket ordered chronologically."""
    from api.support.models import TicketMessage
    return TicketMessage.objects.filter(
        ticket=ticket
    ).select_related('sender').order_by('created_at')


def get_ticket_sla(ticket):
    """Get SLA record for a ticket."""
    try:
        return ticket.sla
    except Exception:
        return None


def get_ticket_stats(tenant=None) -> dict:
    """Aggregate ticket statistics. Uses cache."""
    from api.support.cache import get_ticket_stats
    return get_ticket_stats(tenant=tenant)


def get_open_ticket_count(user) -> int:
    """Count open tickets for a user."""
    from api.support.models import SupportTicket
    return SupportTicket.objects.filter(
        user=user, status__in=['open', 'in_progress', 'waiting_user']
    ).count()


def get_agent_workload(agent_user) -> dict:
    """Count active tickets assigned to an agent."""
    from api.support.models import SupportTicket
    qs = SupportTicket.objects.filter(assigned_to=agent_user)
    return {
        'open':        qs.filter(status='open').count(),
        'in_progress': qs.filter(status='in_progress').count(),
        'waiting':     qs.filter(status='waiting_user').count(),
        'total_active':qs.filter(status__in=['open','in_progress','waiting_user']).count(),
        'urgent':      qs.filter(priority='urgent', status__in=['open','in_progress']).count(),
        'escalated':   qs.filter(escalated=True).count(),
    }


def get_sla_breached_tickets(tenant=None):
    """All tickets currently in SLA breach."""
    from api.support.models import SupportTicket
    from django.db.models import Q
    qs = SupportTicket.objects.filter(
        Q(sla__first_response_breached=True) | Q(sla__resolution_breached=True),
        status__in=['open', 'in_progress', 'waiting_user'],
    ).select_related('user', 'assigned_to', 'sla')
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.order_by('-created_at')


# ── FAQ Selectors ─────────────────────────────────────────────

def list_active_faqs(category: str = None, tenant=None):
    """All active FAQs, optionally filtered by category."""
    from api.support.models import FAQ
    qs = FAQ.objects.filter(is_active=True)
    if category:
        qs = qs.filter(category=category)
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.order_by('order', '-created_at')


def get_faq_by_id(faq_id: int):
    """Get FAQ by id."""
    from api.support.models import FAQ
    try:
        return FAQ.objects.get(id=faq_id)
    except FAQ.DoesNotExist:
        return None


def get_faq_categories(tenant=None) -> list:
    """Distinct FAQ categories."""
    from api.support.models import FAQ
    qs = FAQ.objects.filter(is_active=True)
    if tenant:
        qs = qs.filter(tenant=tenant)
    return list(qs.values_list('category', flat=True).distinct().order_by('category'))


# ── KB Selectors ──────────────────────────────────────────────

def list_kb_articles(category_slug: str = None, search: str = None, tenant=None):
    """Published KB articles."""
    from api.support.models import KBArticle
    from django.db.models import Q
    qs = KBArticle.objects.filter(
        status='published', is_public=True
    ).select_related('category', 'author')
    if tenant:
        qs = qs.filter(tenant=tenant)
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    if search:
        qs = qs.filter(
            Q(title__icontains=search) | Q(body__icontains=search) | Q(summary__icontains=search)
        )
    return qs.order_by('-created_at')


def get_kb_article_by_slug(slug: str):
    """Get single published KB article by slug."""
    from api.support.models import KBArticle
    try:
        return KBArticle.objects.select_related('category', 'author').get(
            slug=slug, status='published', is_public=True
        )
    except KBArticle.DoesNotExist:
        return None


def list_kb_categories(tenant=None):
    """All active root KB categories."""
    from api.support.models import KBCategory
    qs = KBCategory.objects.filter(is_active=True, parent__isnull=True).prefetch_related('children')
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.order_by('sort_order', 'name')


# ── Agent Selectors ───────────────────────────────────────────

def list_available_agents(department=None, tenant=None):
    """Agents who are online and available."""
    from api.support.models import SupportAgent
    qs = SupportAgent.objects.filter(
        is_active=True, is_available=True
    ).select_related('user', 'department', 'status_record')
    if department:
        qs = qs.filter(department=department)
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs


def get_agent_by_user(user):
    """Get SupportAgent profile for a user."""
    try:
        return user.support_agent
    except Exception:
        return None


# ── Dispute Selectors ─────────────────────────────────────────

def list_user_disputes(user, dispute_type: str = 'offer'):
    """All disputes for a user."""
    if dispute_type == 'offer':
        from api.support.models import OfferDispute
        return OfferDispute.objects.filter(user=user).order_by('-created_at')
    from api.support.models import WithdrawalDispute
    return WithdrawalDispute.objects.filter(user=user).order_by('-created_at')


def get_dispute_by_id(dispute_id: int):
    """Get offer dispute by id."""
    from api.support.models import OfferDispute
    try:
        return OfferDispute.objects.select_related('user', 'ticket').get(id=dispute_id)
    except OfferDispute.DoesNotExist:
        return None


# ── Announcements Selectors ───────────────────────────────────

def list_active_announcements(tenant=None):
    """Current active network announcements."""
    from api.support.models import NetworkAnnouncement
    from django.db.models import Q
    now = timezone.now()
    qs  = NetworkAnnouncement.objects.filter(
        is_active=True, show_in_portal=True
    ).filter(
        Q(starts_at__isnull=True) | Q(starts_at__lte=now)
    ).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gte=now)
    )
    if tenant:
        qs = qs.filter(tenant=tenant)
    return qs.order_by('-created_at')


# ── Settings Selectors ────────────────────────────────────────

def get_support_settings():
    """Get support settings singleton (cached)."""
    from api.support.cache import get_settings
    return get_settings()


def get_canned_responses(search: str = None, tenant=None):
    """All active canned responses."""
    from api.support.models import CannedResponse
    from django.db.models import Q
    qs = CannedResponse.objects.filter(is_active=True)
    if tenant:
        qs = qs.filter(tenant=tenant)
    if search:
        qs = qs.filter(
            Q(shortcut__icontains=search) | Q(title__icontains=search)
        )
    return qs.order_by('shortcut')