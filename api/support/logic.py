# api/support/logic.py
"""
Business logic layer for support system.
Pure functions and logic classes — no Django model imports at module level.
Separated from services.py which handles orchestration.
Full code — no summarizing.
"""
import logging
from decimal import Decimal
from datetime import timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ── Ticket Logic ─────────────────────────────────────────────
def determine_ticket_priority(category: str, user=None, amount: Decimal = None) -> str:
    """
    Determine ticket priority based on category, user tier, and amount.
    Returns: 'urgent' | 'high' | 'medium' | 'low'
    """
    from api.support.choices import CATEGORY_PRIORITY_MAP
    base_priority = CATEGORY_PRIORITY_MAP.get(category, 'medium')

    # Check user subscription tier for priority boost
    if user:
        try:
            from api.support.integrations.project_specific.subscription_sla import subscription_sla
            tier_info = subscription_sla.get_subscription_info(user)
            plan      = tier_info.get('plan_name', '').lower()
            if 'vip' in plan or 'premium' in plan:
                # VIP users get at least medium priority
                if base_priority == 'low':
                    base_priority = 'medium'
        except Exception:
            pass

    # Amount-based upgrade for disputes
    if amount:
        if amount >= Decimal('500') and base_priority in ('low', 'medium'):
            base_priority = 'high'
        elif amount >= Decimal('1000') and base_priority != 'urgent':
            base_priority = 'urgent'

    return base_priority


def calculate_sla_due_times(priority: str, created_at=None, business_hours_only: bool = True):
    """
    Calculate SLA first_response_due and resolution_due datetimes.
    Returns: (first_response_due, resolution_due)
    """
    from django.utils import timezone
    from api.support.choices import SLA_FIRST_RESPONSE_HOURS, SLA_RESOLUTION_HOURS

    now    = created_at or timezone.now()
    fr_hrs = SLA_FIRST_RESPONSE_HOURS.get(priority, 8)
    rs_hrs = SLA_RESOLUTION_HOURS.get(priority, 48)

    fr_due  = now + timedelta(hours=fr_hrs)
    res_due = now + timedelta(hours=rs_hrs)
    return fr_due, res_due


def is_ticket_overdue(ticket) -> bool:
    """Check if a ticket is past its SLA resolution deadline."""
    from django.utils import timezone
    try:
        return (
            ticket.sla.resolution_due is not None
            and not ticket.sla.resolution_at
            and timezone.now() > ticket.sla.resolution_due
        )
    except Exception:
        return False


def get_ticket_wait_hours(ticket) -> float:
    """Get how many hours a ticket has been waiting for a response."""
    from django.utils import timezone
    if ticket.first_response_at:
        return round((ticket.first_response_at - ticket.created_at).total_seconds() / 3600, 1)
    return round((timezone.now() - ticket.created_at).total_seconds() / 3600, 1)


def should_auto_close_ticket(ticket) -> bool:
    """
    Determine if a ticket should be auto-closed.
    Conditions: waiting_user for 7 days OR resolved for 30 days.
    """
    from django.utils import timezone
    from api.support.contants import AUTO_CLOSE_WAITING_DAYS, AUTO_CLOSE_RESOLVED_DAYS
    now = timezone.now()
    if ticket.status == 'waiting_user':
        return (now - ticket.updated_at).days >= AUTO_CLOSE_WAITING_DAYS
    if ticket.status == 'resolved' and ticket.resolved_at:
        return (now - ticket.resolved_at).days >= AUTO_CLOSE_RESOLVED_DAYS
    return False


def generate_ticket_id() -> str:
    """Generate a unique ticket ID like TKT123456."""
    import random
    from api.support.contants import TICKET_ID_PREFIX, TICKET_ID_DIGITS
    from api.support.models import SupportTicket
    for _ in range(10):  # Try up to 10 times
        ticket_id = f"{TICKET_ID_PREFIX}{random.randint(10**(TICKET_ID_DIGITS-1), 10**TICKET_ID_DIGITS - 1)}"
        if not SupportTicket.objects.filter(ticket_id=ticket_id).exists():
            return ticket_id
    # Fallback with timestamp
    import time
    return f"{TICKET_ID_PREFIX}{int(time.time())}"


# ── Dispute Logic ─────────────────────────────────────────────
def can_submit_offer_dispute(user) -> tuple:
    """
    Check if user can submit a new offer dispute.
    Returns: (can_submit: bool, reason: str)
    """
    from django.utils import timezone
    from datetime import timedelta
    from api.support.models import OfferDispute
    from api.support.contants import MAX_OFFER_DISPUTES_PER_WEEK

    week_ago = timezone.now() - timedelta(days=7)
    weekly_count = OfferDispute.objects.filter(
        user=user, created_at__gte=week_ago
    ).count()

    if weekly_count >= MAX_OFFER_DISPUTES_PER_WEEK:
        return False, f'Maximum {MAX_OFFER_DISPUTES_PER_WEEK} disputes per week exceeded.'

    # Check if user has critical fraud risk
    try:
        from api.support.integrations.integ_adapter import fraud_adapter
        risk = fraud_adapter.get_risk_score(user)
        if risk.get('is_critical'):
            return False, 'Account risk too high for dispute submission.'
    except Exception:
        pass

    return True, 'OK'


def calculate_dispute_confidence(postback_result: dict, offerwall_result: dict,
                                  fraud_risk: dict, kyc_verified: bool,
                                  amount: Decimal) -> float:
    """
    Calculate a confidence score (0.0 - 1.0) for dispute auto-approval.
    Weights: postback 40%, offerwall 20%, fraud 25%, kyc 10%, amount 5%
    """
    score = 0.0

    # Postback verification (40%)
    pb_confidence = postback_result.get('confidence', 0.0)
    score += pb_confidence * 0.40

    # Offerwall check (20%)
    if offerwall_result.get('found'):
        ow_score = 0.9 if offerwall_result.get('status') == 'completed' else 0.6
    else:
        ow_score = 0.1
    score += ow_score * 0.20

    # Fraud risk (25%) — inverse: low fraud = high score
    fraud_score_raw = fraud_risk.get('score', 0)
    is_flagged      = fraud_risk.get('is_flagged', False)
    if is_flagged:
        fraud_contribution = 0.0
    else:
        fraud_contribution = max(0.0, 1.0 - fraud_score_raw / 100)
    score += fraud_contribution * 0.25

    # KYC (10%)
    score += (0.95 if kyc_verified else 0.3) * 0.10

    # Amount (5%) — smaller amounts are safer to auto-approve
    if amount <= Decimal('50'):
        amount_score = 0.95
    elif amount <= Decimal('200'):
        amount_score = 0.7
    elif amount <= Decimal('500'):
        amount_score = 0.4
    else:
        amount_score = 0.1
    score += amount_score * 0.05

    return round(min(1.0, max(0.0, score)), 3)


# ── Agent Logic ───────────────────────────────────────────────
def select_best_agent_for_ticket(ticket, available_agents) -> Optional[object]:
    """
    Select the best available agent for a ticket.
    Algorithm: skill match > least busy > round robin.
    """
    if not available_agents:
        return None

    category = ticket.category or ''

    # 1. Try skill-matched agents first
    skilled = [
        a for a in available_agents
        if category in (a.skills or [])
    ]
    if skilled:
        # Among skilled: pick least busy
        return min(skilled, key=lambda a: _count_agent_tickets(a))

    # 2. Fall back to least busy
    return min(available_agents, key=lambda a: _count_agent_tickets(a))


def _count_agent_tickets(agent) -> int:
    """Count active tickets for an agent."""
    try:
        from api.support.models import SupportTicket
        return SupportTicket.objects.filter(
            assigned_to=agent.user,
            status__in=['open', 'in_progress', 'waiting_user']
        ).count()
    except Exception:
        return 0


def is_agent_over_capacity(agent) -> bool:
    """Check if agent has reached their concurrent ticket limit."""
    current = _count_agent_tickets(agent)
    return current >= agent.max_concurrent_tickets


# ── CSAT Logic ────────────────────────────────────────────────
def calculate_csat_score(scores: list) -> dict:
    """
    Calculate CSAT metrics from a list of 1-5 scores.
    Returns: avg_score, promoters, detractors, nps
    """
    if not scores:
        return {'avg': 0.0, 'total': 0, 'promoters': 0, 'detractors': 0, 'nps': 0.0}
    total      = len(scores)
    avg        = round(sum(scores) / total, 2)
    promoters  = sum(1 for s in scores if s == 5)
    passives   = sum(1 for s in scores if s in (3, 4))
    detractors = sum(1 for s in scores if s in (1, 2))
    nps        = round((promoters - detractors) / total * 100, 1)
    return {
        'avg':        avg,
        'total':      total,
        'promoters':  promoters,
        'passives':   passives,
        'detractors': detractors,
        'nps':        nps,
    }


def should_request_csat(ticket) -> bool:
    """Determine if a CSAT survey should be sent for this ticket."""
    return (
        ticket.status == 'resolved'
        and ticket.satisfaction_rating is None
        and ticket.user.email
    )