# api/support/interactors.py
"""
Interactors — complex multi-step operations that coordinate
multiple services, repositories, and integrations.
Higher-level than use_cases; called for complex workflows.
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class DisputeVerificationInteractor:
    """
    Orchestrates the full dispute verification flow.
    Steps: fraud check → postback verify → offerwall check → auto-approve or manual
    """

    def run(self, dispute, ticket) -> dict:
        """Execute full verification pipeline."""
        from api.support.integrations.integ_handler import integ_handler
        from api.support.integrations.project_specific.auto_approval_engine import auto_approval_engine

        logger.info(f'DisputeVerificationInteractor: dispute={dispute.id}')

        # Step 1: Get evaluation from auto-approval engine
        evaluation = auto_approval_engine.evaluate(dispute)

        # Step 2: Based on decision
        if evaluation['decision'] == 'auto_approve':
            ok = integ_handler._auto_approve_dispute(dispute, ticket)
            return {
                'status':       'auto_approved' if ok else 'error',
                'confidence':   evaluation['score'],
                'auto_approved':ok,
                'message':      'Verified and auto-approved.' if ok else 'Credit failed.',
                'details':      evaluation,
            }

        if evaluation['decision'] == 'auto_reject':
            from django.utils import timezone
            dispute.status      = 'rejected'
            dispute.resolved_at = timezone.now()
            dispute.agent_notes = f'Auto-rejected: {evaluation["reason"]}'
            dispute.save(update_fields=['status', 'resolved_at', 'agent_notes'])
            return {
                'status':     'auto_rejected',
                'confidence': evaluation['score'],
                'message':    evaluation['reason'],
                'details':    evaluation,
            }

        # Manual review
        dispute.status           = 'investigating'
        dispute.verification_status = 'pending_manual'
        dispute.confidence_score = evaluation['score']
        dispute.save(update_fields=['status', 'verification_status', 'confidence_score'])

        return {
            'status':     'manual_review',
            'confidence': evaluation['score'],
            'message':    evaluation['reason'],
            'details':    evaluation,
        }


class TicketAutoRoutingInteractor:
    """
    Routes a new ticket to the best available agent.
    Considers: department, skills, workload, priority.
    """

    def route(self, ticket) -> bool:
        """Auto-assign ticket to best available agent."""
        from api.support.repositories import agent_repo
        from api.support.logic import select_best_agent_for_ticket, is_agent_over_capacity
        from api.support.models import Department

        # Determine target department from category
        dept_slug_map = {
            'payment': 'payment', 'withdrawal': 'payment',
            'fraud': 'fraud', 'kyc': 'kyc',
            'technical': 'technical', 'account': 'account',
        }
        dept_slug = dept_slug_map.get(ticket.category, 'general')

        try:
            dept = Department.objects.get(slug=dept_slug, is_active=True)
        except Department.DoesNotExist:
            dept = None

        agents = list(agent_repo.get_available_agents(department=dept, tenant=ticket.tenant))

        if not agents:
            # Try without department filter
            agents = list(agent_repo.get_available_agents(tenant=ticket.tenant))

        if not agents:
            logger.info(f'No agents available for ticket {ticket.ticket_id}')
            return False

        # Filter out over-capacity agents
        agents = [a for a in agents if not is_agent_over_capacity(a)]
        if not agents:
            return False

        best_agent = select_best_agent_for_ticket(ticket, agents)
        if not best_agent:
            return False

        ticket.assigned_to = best_agent.user
        ticket.save(update_fields=['assigned_to'])
        logger.info(f'Ticket {ticket.ticket_id} → {best_agent.user.username}')
        return True


class SLAEnforcementInteractor:
    """
    Checks SLA compliance and triggers breach notifications.
    Called by Celery task every 15 minutes.
    """

    def run_checks(self) -> dict:
        """Check all active tickets for SLA violations."""
        from api.support.repositories import sla_repo
        from api.support.notifications import notification_service
        from api.support.models import TicketSLA, SLABreach
        from django.utils import timezone

        now     = timezone.now()
        checked = breached = notified = warned = 0

        for sla in sla_repo.get_breached():
            checked += 1
            ticket  = sla.ticket
            if ticket.status in ('closed', 'resolved', 'spam'):
                continue

            # Create breach record if not exists
            breach_type = None
            if sla.first_response_breached and not sla.first_response_at:
                breach_type = 'first_response'
            elif sla.resolution_breached:
                breach_type = 'resolution'

            if breach_type:
                overdue = max(0.0, (now - (sla.first_response_due if breach_type == 'first_response' else sla.resolution_due)).total_seconds() / 3600)
                _, created = SLABreach.objects.get_or_create(
                    ticket=ticket, breach_type=breach_type,
                    defaults={'due_at': sla.first_response_due if breach_type == 'first_response' else sla.resolution_due, 'overdue_hours': overdue}
                )
                if created:
                    breached += 1
                    notification_service.notify_sla_breach(ticket, breach_type)
                    notified += 1

        # Warn about upcoming breaches (within 1 hour)
        for sla in sla_repo.get_due_soon(hours=1):
            try:
                ticket  = sla.ticket
                if ticket.status in ('closed', 'resolved', 'spam'):
                    continue
                if not sla.warning_sent:
                    fr_hrs = None
                    if sla.first_response_due and not sla.first_response_at:
                        fr_hrs = (sla.first_response_due - now).total_seconds() / 3600
                    if fr_hrs and fr_hrs > 0:
                        notification_service.notify_sla_warning(ticket, fr_hrs)
                        TicketSLA.objects.filter(pk=sla.pk).update(warning_sent=True)
                        warned += 1
            except Exception as e:
                logger.debug(f'SLA warning: {e}')

        return {'checked': checked, 'breached': breached, 'notified': notified, 'warned': warned}


class ChurnRiskInteractor:
    """
    Identifies high-risk churning users in the support queue
    and prioritizes their tickets.
    """

    def process_ticket(self, ticket) -> dict:
        """Adjust ticket handling based on churn risk."""
        try:
            from api.support.integrations.project_specific.churn_risk_support import churn_risk_manager
            return churn_risk_manager.adjust_ticket_for_churn_risk(ticket)
        except Exception as e:
            logger.debug(f'ChurnRiskInteractor.process_ticket: {e}')
            return {}

    def post_resolution(self, ticket) -> dict:
        """Actions after high-risk churn user's ticket resolved."""
        try:
            from api.support.integrations.project_specific.churn_risk_support import churn_risk_manager
            return churn_risk_manager.post_resolution_action(ticket)
        except Exception as e:
            logger.debug(f'ChurnRiskInteractor.post_resolution: {e}')
            return {}


# Singletons
dispute_verification_interactor = DisputeVerificationInteractor()
ticket_routing_interactor        = TicketAutoRoutingInteractor()
sla_enforcement_interactor       = SLAEnforcementInteractor()
churn_risk_interactor            = ChurnRiskInteractor()