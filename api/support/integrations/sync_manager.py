# api/support/integrations/sync_manager.py  — WORLD #1 (New)
"""
Sync Manager — Data Conflict Resolver।
Support ↔ Other apps data sync এবং conflict resolution।
"""
import logging
from typing import Any, Dict, List, Optional, Tuple
from django.utils import timezone

from .integ_exceptions import SyncConflictError

logger = logging.getLogger(__name__)


class SupportSyncManager:
    """
    Resolves data conflicts between support system and other apps.
    
    Examples:
    - Wallet balance in dispute vs actual wallet balance
    - Offer completion in postback vs in offerwall
    - KYC status in support ticket vs in kyc app
    """

    def sync_dispute_with_wallet(self, dispute) -> dict:
        """
        Verify dispute amount matches wallet transaction records.
        Returns sync result with conflict details.
        """
        result = {'synced': True, 'conflicts': [], 'action': 'none'}

        try:
            from .integ_adapter import wallet_adapter
            transactions = wallet_adapter.get_transactions(dispute.user, limit=50)

            # Check if dispute amount was already credited
            credited = [
                t for t in transactions
                if str(dispute.offer_id) in str(t.get('description',''))
                   and t.get('type') == 'credit'
                   and t.get('status') == 'approved'
            ]

            if credited:
                conflict_msg = f'Dispute amount {dispute.expected_amount} was already credited on {credited[0]["created_at"]}'
                result['synced']    = False
                result['conflicts'].append(conflict_msg)
                result['action']    = 'already_credited'
                logger.warning(f'Sync conflict: {conflict_msg}')
            return result

        except Exception as e:
            logger.error(f'sync_dispute_with_wallet failed: {e}')
            result['synced'] = False
            result['conflicts'].append(f'Sync error: {e}')
            return result

    def sync_ticket_status_with_dispute(self, ticket, dispute) -> dict:
        """Ensure ticket status matches dispute status."""
        result = {'synced': True, 'action': 'none'}

        DISPUTE_TO_TICKET_STATUS = {
            'approved':    'resolved',
            'rejected':    'resolved',
            'investigating':'in_progress',
            'pending':     'open',
            'needs_proof': 'waiting_user',
        }

        expected_ticket_status = DISPUTE_TO_TICKET_STATUS.get(dispute.status)
        if expected_ticket_status and ticket.status != expected_ticket_status:
            logger.info(f'Sync: ticket {ticket.ticket_id} status {ticket.status} → {expected_ticket_status}')
            ticket.status = expected_ticket_status
            if expected_ticket_status == 'resolved' and not ticket.resolved_at:
                ticket.resolved_at = timezone.now()
            ticket.save(update_fields=['status','resolved_at'])
            result['action'] = f'ticket_status_updated_to_{expected_ticket_status}'

        return result

    def sync_sla_with_agent_assignment(self, ticket) -> dict:
        """Ensure SLA deadlines are adjusted when agent changes tier."""
        result = {'synced': True, 'action': 'none'}
        try:
            from .auth_bridge import auth_bridge
            tier = auth_bridge.get_user_tier(ticket.user)
            from .integ_constants import TIER_SLA_HOURS
            tier_fr_hours = TIER_SLA_HOURS.get(tier, 8)
            try:
                sla = ticket.sla
                now = timezone.now()
                expected_fr_due = ticket.created_at + __import__('datetime').timedelta(hours=tier_fr_hours)
                if abs((sla.first_response_due - expected_fr_due).total_seconds()) > 3600:
                    sla.first_response_due = expected_fr_due
                    sla.save(update_fields=['first_response_due'])
                    result['action'] = f'sla_adjusted_for_tier_{tier}'
            except Exception:
                pass
        except Exception as e:
            logger.debug(f'sync_sla_with_agent_assignment: {e}')
        return result

    def resolve_conflict(self, conflict_type: str, source_value: Any, target_value: Any, **context) -> Any:
        """
        Resolve a data conflict.
        Strategy: most recent wins for status, max wins for amounts.
        """
        if conflict_type == 'status':
            STATUS_PRIORITY = {
                'approved':1,'resolved':1,'rejected':1,
                'investigating':2,'in_progress':2,
                'pending':3,'open':3,
                'closed':4,
            }
            sv = STATUS_PRIORITY.get(str(source_value), 99)
            tv = STATUS_PRIORITY.get(str(target_value), 99)
            winner = source_value if sv <= tv else target_value
            logger.info(f'Conflict resolved [{conflict_type}]: {source_value} vs {target_value} → {winner}')
            return winner

        if conflict_type == 'amount':
            return max(float(source_value), float(target_value))

        if conflict_type == 'timestamp':
            return max(source_value, target_value) if source_value and target_value else source_value or target_value

        logger.warning(f'Unknown conflict type: {conflict_type}. Using source value.')
        return source_value

    def run_full_sync(self) -> dict:
        """Full sync run — called by Celery daily task."""
        from api.support.models import OfferDispute, SupportTicket
        results = {'synced': 0, 'conflicts': 0, 'errors': 0}

        # Sync pending disputes with wallet
        disputes = OfferDispute.objects.filter(status__in=['investigating','pending']).select_related('ticket','user')
        for dispute in disputes[:100]:
            try:
                result = self.sync_dispute_with_wallet(dispute)
                if not result['synced']:
                    results['conflicts'] += 1
                    if result['action'] == 'already_credited':
                        dispute.status    = 'approved'
                        dispute.agent_notes = 'Auto-synced: already credited by another process.'
                        dispute.save(update_fields=['status','agent_notes'])
                else:
                    results['synced'] += 1
            except Exception as e:
                results['errors'] += 1
                logger.error(f'Sync error for dispute {dispute.id}: {e}')

        logger.info(f'Full sync complete: {results}')
        return results


sync_manager = SupportSyncManager()