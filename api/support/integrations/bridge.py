# api/support/integrations/bridge.py  — WORLD #1
"""
Data Bridge — Support system ↔ Other apps data transformation layer।
Raw app data → Support-friendly format এবং vice versa।
"""
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SupportDataBridge:
    """
    Transforms data between support system and external apps.
    Support-এর serializer format ↔ app-এর model format।
    """

    # ── Wallet → Support ──────────────────────────────────
    def wallet_to_support_context(self, wallet_data: dict) -> dict:
        """Transform wallet data into support ticket context."""
        if not wallet_data:
            return {}
        return {
            'wallet_available':    wallet_data.get('available', 0),
            'wallet_pending':      wallet_data.get('pending', 0),
            'wallet_frozen':       wallet_data.get('frozen', 0),
            'wallet_total_earned': wallet_data.get('total_earned', 0),
            'wallet_locked':       wallet_data.get('is_locked', False),
            'wallet_currency':     wallet_data.get('currency', 'BDT'),
        }

    # ── Fraud → Support ───────────────────────────────────
    def fraud_to_support_context(self, risk_data: dict) -> dict:
        """Transform fraud risk data into support ticket context."""
        if not risk_data:
            return {}
        score = risk_data.get('score', 0)
        return {
            'risk_score':     score,
            'risk_level':     'critical' if score >= 90 else 'high' if score >= 70 else 'medium' if score >= 40 else 'low',
            'is_flagged':     risk_data.get('is_flagged', False),
            'fraud_attempts': risk_data.get('fraud_attempts', 0),
            'warning_flags':  risk_data.get('warnings', []),
            'safe_to_auto':   score < 40 and not risk_data.get('is_flagged'),
        }

    # ── KYC → Support ─────────────────────────────────────
    def kyc_to_support_context(self, kyc_data: dict) -> dict:
        """Transform KYC data into support context."""
        if not kyc_data:
            return {}
        return {
            'kyc_status':   kyc_data.get('status', 'unknown'),
            'kyc_verified': kyc_data.get('is_verified', False),
            'kyc_date':     kyc_data.get('submitted_at', ''),
        }

    # ── Postback → Support ────────────────────────────────
    def postback_to_dispute_result(self, pb_data: dict) -> dict:
        """Transform postback verification result for dispute processing."""
        if not pb_data:
            return {'verified': False, 'confidence': 0.1, 'summary': 'No data'}
        return {
            'verified':    pb_data.get('found', False),
            'confidence':  pb_data.get('confidence', 0.1),
            'status':      pb_data.get('status', 'unknown'),
            'postback_id': pb_data.get('postback_id'),
            'summary':     ' | '.join(pb_data.get('details', [])),
        }

    # ── Support Ticket → External Webhook ─────────────────
    def ticket_to_webhook_payload(self, ticket, event: str) -> dict:
        """Transform ticket to webhook payload for external systems."""
        return {
            'event':       event,
            'ticket_id':   ticket.ticket_id,
            'category':    ticket.category,
            'priority':    ticket.priority,
            'status':      ticket.status,
            'user_id':     ticket.user_id,
            'created_at':  ticket.created_at.isoformat(),
        }

    # ── Full User Context ─────────────────────────────────
    def build_agent_user_context(
        self,
        wallet_data:   dict = None,
        risk_data:     dict = None,
        kyc_data:      dict = None,
        referral_data: dict = None,
    ) -> dict:
        """Build complete user context for agent view."""
        context = {}
        if wallet_data:   context.update(self.wallet_to_support_context(wallet_data))
        if risk_data:     context.update(self.fraud_to_support_context(risk_data))
        if kyc_data:      context.update(self.kyc_to_support_context(kyc_data))
        if referral_data: context['referral'] = referral_data
        return context

    # ── Dispute Data Enrichment ────────────────────────────
    def enrich_dispute_for_agent(self, dispute, pb_result: dict = None, ow_result: dict = None) -> dict:
        """Add all context to dispute for agent review."""
        data = {
            'dispute_id':       dispute.id,
            'offer_id':         dispute.offer_id,
            'offer_name':       dispute.offer_name,
            'expected_amount':  float(dispute.expected_amount),
            'status':           dispute.status,
            'confidence':       dispute.confidence_score,
            'verification':     dispute.verification_status,
        }
        if pb_result:
            data['postback_check'] = self.postback_to_dispute_result(pb_result)
        if ow_result:
            data['offerwall_check'] = ow_result
        return data


bridge = SupportDataBridge()