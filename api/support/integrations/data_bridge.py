# api/support/integrations/data_bridge.py
import logging
logger = logging.getLogger(__name__)


class ExternalDataBridge:
    def postback_to_verification(self, postback_data: dict) -> dict:
        if not postback_data:
            return {'verified': False, 'confidence': 0.0}
        return {
            'verified':   postback_data.get('found', False),
            'confidence': postback_data.get('confidence', 0.1),
            'status':     postback_data.get('status', 'unknown'),
            'details':    postback_data.get('details', []),
        }

    def wallet_balance_to_context(self, balance_data: dict) -> dict:
        return {
            'wallet_available':    balance_data.get('available', 0),
            'wallet_total_earned': balance_data.get('total_earned', 0),
            'wallet_locked':       balance_data.get('is_locked', False),
            'wallet_currency':     balance_data.get('currency', 'BDT'),
        }

    def fraud_risk_to_context(self, risk_data: dict) -> dict:
        score = risk_data.get('score', 0)
        return {
            'risk_score':   score,
            'risk_level':   'critical' if score >= 90 else 'high' if score >= 70 else 'medium' if score >= 40 else 'low',
            'is_flagged':   risk_data.get('is_flagged', False),
            'safe_to_auto': score < 40 and not risk_data.get('is_flagged', False),
        }

    def kyc_to_context(self, kyc_data: dict) -> dict:
        return {
            'kyc_status':   kyc_data.get('status', 'unknown'),
            'kyc_verified': kyc_data.get('is_verified', False),
        }

    def build_agent_context(self, wallet=None, fraud=None, kyc=None, referral=None) -> dict:
        ctx = {}
        if wallet:   ctx.update(self.wallet_balance_to_context(wallet))
        if fraud:    ctx.update(self.fraud_risk_to_context(fraud))
        if kyc:      ctx.update(self.kyc_to_context(kyc))
        if referral: ctx['referral'] = referral
        return ctx

    def ticket_to_webhook_payload(self, ticket, event: str) -> dict:
        return {
            'event':      event,
            'ticket_id':  ticket.ticket_id,
            'status':     ticket.status,
            'priority':   ticket.priority,
            'category':   ticket.category,
            'user_id':    ticket.user_id,
            'created_at': ticket.created_at.isoformat(),
        }


data_bridge = ExternalDataBridge()