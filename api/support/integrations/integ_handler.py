# api/support/integrations/integ_handler.py  — WORLD #1
"""
Integration Handler — Support system-এর main orchestrator।
সব integration calls এখান দিয়ে যায়।
Services এখানকার handler call করে, directly adapter call করে না।
"""
import logging
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from .integ_adapter import (
    wallet_adapter, fraud_adapter, postback_adapter,
    offerwall_adapter, notifications_adapter, kyc_adapter,
    referral_adapter, analytics_adapter,
)
from .integ_constants import (
    AUTO_APPROVE_CONFIDENCE, EVT_OFFER_DISPUTE_APPROVED,
    EVT_OFFER_DISPUTE_REJECTED,
)
from .integ_exceptions import (
    FraudRiskTooHighError, WalletLockedError, VerificationFailedError,
)
from .data_validator import data_validator
from .event_bus import event_bus

logger = logging.getLogger(__name__)


class SupportIntegrationHandler:
    """
    Main integration orchestrator for support system.
    
    Support → Handler → Adapter → App
    
    Usage:
        from api.support.integrations.integ_handler import integ_handler
        result = integ_handler.verify_and_process_offer_dispute(dispute, ticket)
    """

    # ══════════════════════════════════════════════════════
    # OFFER DISPUTE — Core CPA flow
    # ══════════════════════════════════════════════════════
    def verify_and_process_offer_dispute(self, dispute, ticket) -> dict:
        """
        Full offer dispute verification + processing.
        
        Flow:
        1. Check fraud risk of user
        2. Verify via postback logs
        3. Cross-check with offerwall completion records
        4. If confidence ≥ 85% → auto-approve + credit wallet
        5. Else → manual review
        
        Returns: {status, confidence, auto_approved, message, details}
        """
        user = dispute.user
        result = {
            'status':       'investigating',
            'confidence':   0.0,
            'auto_approved':False,
            'message':      '',
            'details':      [],
        }

        # ── Step 1: Fraud check ────────────────────────
        risk = fraud_adapter.get_risk_score(user)
        if risk.get('is_critical'):
            dispute.status = 'rejected'
            dispute.agent_notes = f'Auto-rejected: fraud risk score critical ({risk["score"]})'
            dispute.save(update_fields=['status','agent_notes'])
            event_bus.publish(EVT_OFFER_DISPUTE_REJECTED, dispute=dispute, ticket=ticket, reason='fraud_critical')
            return {**result, 'status':'rejected', 'message':'Dispute rejected: account risk too high.', 'details':['Critical fraud risk score.']}

        is_safe, safety_reason = fraud_adapter.is_safe_to_auto_approve(user, dispute.expected_amount)

        # ── Step 2: Postback verification ─────────────
        pb_result = postback_adapter.verify_offer_completion(
            user, dispute.offer_id, dispute.click_id
        )
        result['details'].extend(pb_result.get('details', []))
        confidence = pb_result.get('confidence', 0.1)

        # ── Step 3: Offerwall cross-check ─────────────
        ow_result = offerwall_adapter.check_user_completion(user, dispute.offer_id)
        if ow_result.get('found'):
            confidence = min(1.0, confidence + 0.2)
            result['details'].append(f'Offerwall completion record found: {ow_result["status"]}')
            if ow_result.get('status') == 'completed':
                confidence = min(1.0, confidence + 0.1)

        # ── Step 4: Check KYC ─────────────────────────
        if kyc_adapter.is_verified(user):
            confidence = min(1.0, confidence + 0.1)
            result['details'].append('User is KYC verified.')

        result['confidence'] = round(confidence, 2)

        # ── Step 5: Auto-approve or Manual ────────────
        if confidence >= AUTO_APPROVE_CONFIDENCE and is_safe:
            success = self._auto_approve_dispute(dispute, ticket)
            if success:
                result['status']        = 'auto_approved'
                result['auto_approved'] = True
                result['message']       = f'Verified & auto-approved! {dispute.expected_amount} credits added.'
                return result
            else:
                result['message'] = 'Verification passed but credit failed. Manual review.'
                return result

        # Manual review
        if not is_safe:
            result['details'].append(f'Manual review required: {safety_reason}')
        elif confidence < AUTO_APPROVE_CONFIDENCE:
            result['details'].append(f'Confidence {confidence:.0%} below auto-approve threshold.')

        result['message'] = 'Dispute under manual review. Response within 24 hours.'
        dispute.verification_status = pb_result.get('status','unknown')
        dispute.confidence_score    = confidence
        dispute.save(update_fields=['verification_status','confidence_score'])
        return result

    def _auto_approve_dispute(self, dispute, ticket) -> bool:
        """Credit wallet and mark dispute approved."""
        try:
            from django.utils import timezone as tz
            ok = wallet_adapter.credit(
                dispute.user,
                Decimal(str(dispute.expected_amount)),
                f'Offer dispute auto-approved: {dispute.offer_id}',
                ticket_id=ticket.ticket_id if ticket else '',
            )
            if ok:
                dispute.status      = 'approved'
                dispute.resolved_at = tz.now()
                dispute.agent_notes = 'Auto-approved by verification engine.'
                dispute.save(update_fields=['status','resolved_at','agent_notes'])
                # Notify
                event_bus.publish(EVT_OFFER_DISPUTE_APPROVED, dispute=dispute, ticket=ticket)
                # Add ticket message
                if ticket:
                    from api.support.models import TicketMessage
                    from django.contrib.auth import get_user_model
                    bot = get_user_model().objects.filter(is_superuser=True).first()
                    TicketMessage.objects.create(
                        ticket=ticket, sender=bot, is_agent=True,
                        content=(
                            f'✅ AUTO-RESOLVED\n\n'
                            f'Offer dispute verified and approved.\n'
                            f'{dispute.expected_amount} credits have been added to your wallet.\n\n'
                            f'Confidence score: {dispute.confidence_score:.0%}'
                        )
                    )
            return ok
        except Exception as e:
            logger.error(f'_auto_approve_dispute failed: {e}')
            return False

    # ══════════════════════════════════════════════════════
    # WITHDRAWAL DISPUTE
    # ══════════════════════════════════════════════════════
    def process_withdrawal_dispute(self, dispute, ticket) -> dict:
        """
        Withdrawal dispute processing.
        Check transaction history in wallet app.
        """
        user   = dispute.user
        result = {'status': 'investigating', 'message': '', 'details': []}

        # Get wallet transaction history
        transactions = wallet_adapter.get_transactions(user, limit=20)
        matching = [
            t for t in transactions
            if dispute.transaction_id in str(t.get('description', ''))
               or str(dispute.amount) in str(t.get('amount', ''))
        ]

        if matching:
            result['details'].append(f'Found {len(matching)} matching transaction(s) in wallet history.')
            # If transaction exists but status is pending — likely processing delay
            pending = [t for t in matching if t.get('status') == 'pending']
            if pending:
                result['message'] = 'Transaction found — currently processing. Expected within 1-3 business days.'
                result['status']  = 'investigating'
            else:
                result['message'] = 'Transaction found in system. Under manual review.'
        else:
            result['details'].append('No matching transaction found. Please provide transaction receipt.')
            result['message'] = 'No matching record. Manual review required. Please attach receipt.'

        return result

    # ══════════════════════════════════════════════════════
    # FRAUD CHECK (for agent use)
    # ══════════════════════════════════════════════════════
    def get_user_context_for_ticket(self, user) -> dict:
        """
        Get full user context for agent — fraud, wallet, KYC, disputes.
        Called when agent opens a ticket.
        """
        context = {}

        # Wallet info
        try:
            context['wallet'] = wallet_adapter.get_balance(user)
        except Exception as e:
            context['wallet'] = {'error': str(e)}

        # Risk info
        try:
            context['fraud_risk'] = fraud_adapter.get_risk_score(user)
        except Exception as e:
            context['fraud_risk'] = {'error': str(e)}

        # KYC info
        try:
            context['kyc'] = kyc_adapter.get_status(user)
        except Exception as e:
            context['kyc'] = {'error': str(e)}

        # Referral info
        try:
            context['referral'] = referral_adapter.get_referral_info(user)
        except Exception as e:
            context['referral'] = {'error': str(e)}

        return context

    # ══════════════════════════════════════════════════════
    # TICKET EVENTS — fire on ticket state changes
    # ══════════════════════════════════════════════════════
    def on_ticket_created(self, ticket) -> None:
        """Called by TicketService.create() after ticket is saved."""
        event_bus.publish(
            EVT_TICKET_CREATED,
            ticket=ticket,
            user=ticket.user,
        )
        analytics_adapter.track_support_event('ticket_created', ticket=ticket)

    def on_ticket_resolved(self, ticket) -> None:
        """Called by TicketService.resolve() after ticket resolved."""
        event_bus.publish(EVT_TICKET_RESOLVED, ticket=ticket)

    def on_ticket_escalated(self, ticket, reason: str = '') -> None:
        """Called when ticket is escalated."""
        event_bus.publish(EVT_TICKET_ESCALATED, ticket=ticket, reason=reason)
        # Notify agent
        if ticket.assigned_to:
            notifications_adapter.send(
                ticket.assigned_to,
                f'Ticket Escalated: #{ticket.ticket_id}',
                f'Ticket #{ticket.ticket_id} has been escalated. Immediate attention required.',
                priority='urgent',
            )

    def on_sla_breach(self, ticket, breach_type: str) -> None:
        """Called by SLAService when SLA is breached."""
        event_bus.publish(EVT_TICKET_SLA_BREACH, ticket=ticket, breach_type=breach_type)
        if ticket.assigned_to:
            notifications_adapter.send(
                ticket.assigned_to,
                f'🚨 SLA Breach: #{ticket.ticket_id}',
                f'SLA {breach_type} deadline missed for ticket #{ticket.ticket_id}.',
                priority='urgent',
            )

    # ══════════════════════════════════════════════════════
    # SEND NOTIFICATION
    # ══════════════════════════════════════════════════════
    def notify(self, user, title: str, body: str, **kwargs) -> bool:
        """Send notification to user via notifications app."""
        return notifications_adapter.send(user, title, body, **kwargs)


# ── Singleton ─────────────────────────────────────────
integ_handler = SupportIntegrationHandler()