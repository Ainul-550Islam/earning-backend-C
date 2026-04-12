"""
api/ai_engine/AUTOMATION_AGENTS/auto_decision_maker.py
=======================================================
Auto Decision Maker — rule + ML hybrid automated decisions।
Fraud, churn, payment, content, campaign decisions automate করো।
"""

import logging
from typing import Dict, Any
logger = logging.getLogger(__name__)


class AutoDecisionMaker:
    """Rule + ML hybrid automated decision system।"""

    DECISION_CONTEXTS = [
        'fraud_alert', 'churn_risk', 'payment_request',
        'content_flag', 'campaign_action', 'offer_approval',
        'user_level_upgrade', 'withdrawal_request',
    ]

    def decide(self, context: str, data: dict, threshold: float = 0.70) -> dict:
        fns = {
            'fraud_alert':       self._fraud,
            'churn_risk':        self._churn,
            'payment_request':   self._payment,
            'content_flag':      self._content,
            'campaign_action':   self._campaign,
            'offer_approval':    self._offer,
            'user_level_upgrade': self._level_upgrade,
            'withdrawal_request': self._withdrawal,
        }
        fn = fns.get(context, self._default)
        result = fn(data, threshold)
        logger.info(f"AutoDecision [{context}]: {result['decision']} conf={result.get('confidence', 0):.2f}")
        return result

    def _fraud(self, d, t) -> dict:
        score = d.get('fraud_score', 0)
        if score >= 0.95: return {'decision': 'block_immediately', 'confidence': 0.98, 'auto_executed': True, 'reason': 'Extreme fraud score'}
        if score >= t:    return {'decision': 'restrict_account',  'confidence': 0.88, 'auto_executed': True, 'reason': 'High fraud score'}
        if score >= 0.50: return {'decision': 'flag_for_review',   'confidence': 0.75, 'auto_executed': False, 'reason': 'Moderate fraud risk'}
        return                   {'decision': 'monitor',            'confidence': 0.90, 'auto_executed': False, 'reason': 'Normal activity'}

    def _churn(self, d, t) -> dict:
        prob = d.get('churn_probability', 0)
        if prob >= 0.80: return {'decision': 'send_urgent_winback',   'confidence': 0.92, 'auto_executed': True}
        if prob >= t:    return {'decision': 'send_retention_offer',  'confidence': 0.85, 'auto_executed': True}
        if prob >= 0.40: return {'decision': 'send_nudge_email',       'confidence': 0.78, 'auto_executed': True}
        return                  {'decision': 'no_action',              'confidence': 0.95, 'auto_executed': False}

    def _payment(self, d, t) -> dict:
        risk = d.get('payment_risk', 0)
        amount = d.get('amount', 0)
        if risk >= 0.90 or amount > 50000: return {'decision': 'block_payment',   'confidence': 0.97, 'auto_executed': True}
        if risk >= t:                       return {'decision': 'require_2fa',     'confidence': 0.88, 'auto_executed': True}
        return                                     {'decision': 'approve',         'confidence': 0.92, 'auto_executed': True}

    def _content(self, d, t) -> dict:
        score = d.get('violation_score', 0)
        if score >= 0.90: return {'decision': 'auto_remove',     'confidence': score, 'auto_executed': True}
        if score >= t:    return {'decision': 'send_to_review',  'confidence': score, 'auto_executed': True}
        return                   {'decision': 'allow',            'confidence': 1 - score, 'auto_executed': True}

    def _campaign(self, d, t) -> dict:
        ctr = d.get('ctr', 0); cvr = d.get('cvr', 0); roi = d.get('roi', 0)
        if roi < 0:       return {'decision': 'pause_campaign',    'confidence': 0.90, 'auto_executed': True}
        if ctr < 0.01:    return {'decision': 'refresh_creatives', 'confidence': 0.85, 'auto_executed': False}
        if roi > 3.0:     return {'decision': 'scale_budget',      'confidence': 0.88, 'auto_executed': False}
        return                   {'decision': 'maintain',           'confidence': 0.80, 'auto_executed': True}

    def _offer(self, d, t) -> dict:
        quality = d.get('quality_score', 0.5)
        if quality >= 0.80: return {'decision': 'approve_and_feature', 'confidence': quality, 'auto_executed': True}
        if quality >= t:    return {'decision': 'approve',              'confidence': quality, 'auto_executed': True}
        return                     {'decision': 'reject_needs_revision','confidence': 1 - quality, 'auto_executed': True}

    def _level_upgrade(self, d, t) -> dict:
        score = d.get('eligibility_score', 0)
        if score >= t: return {'decision': 'upgrade_to_vip', 'confidence': score, 'auto_executed': True}
        return                {'decision': 'keep_current_level', 'confidence': 1 - score, 'auto_executed': False}

    def _withdrawal(self, d, t) -> dict:
        risk  = d.get('risk_score', 0)
        kyc   = d.get('kyc_verified', False)
        amount = d.get('amount', 0)
        if not kyc:        return {'decision': 'require_kyc',    'confidence': 0.99, 'auto_executed': True}
        if risk >= 0.80:   return {'decision': 'manual_review',  'confidence': 0.90, 'auto_executed': True}
        if amount > 10000: return {'decision': 'senior_approval','confidence': 0.85, 'auto_executed': True}
        return                    {'decision': 'approve',         'confidence': 0.93, 'auto_executed': True}

    def _default(self, d, t) -> dict:
        return {'decision': 'monitor', 'confidence': 0.50, 'auto_executed': False}

    def bulk_decide(self, decisions: list) -> list:
        return [self.decide(d.get('context', 'fraud_alert'), d.get('data', {})) for d in decisions]
