"""
api/ai_engine/AUTOMATION_AGENTS/intelligent_agent.py
=====================================================
Intelligent Agent — autonomous decision making।
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class IntelligentAgent:
    """
    Autonomous AI agent — observe → decide → act।
    """

    def __init__(self, agent_id: str, tenant_id=None):
        self.agent_id  = agent_id
        self.tenant_id = tenant_id
        self.memory:   List[dict] = []

    def run(self, observation: dict) -> dict:
        """Agent cycle: observe → reason → act।"""
        self.memory.append({'observation': observation})
        decision = self._reason(observation)
        action   = self._act(decision)
        return {'decision': decision, 'action': action, 'agent_id': self.agent_id}

    def _reason(self, obs: dict) -> dict:
        """Observation থেকে decision নাও।"""
        task = obs.get('task', 'general')
        if task == 'fraud_response':
            return self._fraud_decision(obs)
        elif task == 'retention':
            return self._retention_decision(obs)
        elif task == 'offer_optimization':
            return self._offer_decision(obs)
        return {'action': 'monitor', 'confidence': 0.5}

    def _act(self, decision: dict) -> dict:
        """Decision execute করো।"""
        action_type = decision.get('action', 'monitor')
        logger.info(f"Agent [{self.agent_id}] acting: {action_type}")
        return {'executed': action_type, 'status': 'success'}

    def _fraud_decision(self, obs: dict) -> dict:
        score = obs.get('fraud_score', 0)
        if score >= 0.9:   return {'action': 'block_user',   'confidence': 0.95}
        if score >= 0.75:  return {'action': 'flag_review',  'confidence': 0.85}
        if score >= 0.5:   return {'action': 'warn_user',    'confidence': 0.70}
        return               {'action': 'monitor',          'confidence': 0.60}

    def _retention_decision(self, obs: dict) -> dict:
        risk = obs.get('churn_risk', 0)
        if risk >= 0.8:   return {'action': 'send_urgent_offer',  'confidence': 0.90}
        if risk >= 0.6:   return {'action': 'send_retention_sms', 'confidence': 0.80}
        if risk >= 0.4:   return {'action': 'send_email_nudge',   'confidence': 0.70}
        return              {'action': 'no_action',              'confidence': 0.85}

    def _offer_decision(self, obs: dict) -> dict:
        ctr = obs.get('ctr', 0)
        if ctr < 0.01:  return {'action': 'rotate_offer',   'confidence': 0.85}
        if ctr > 0.15:  return {'action': 'scale_up_offer', 'confidence': 0.90}
        return            {'action': 'keep_current',        'confidence': 0.75}


"""
api/ai_engine/AUTOMATION_AGENTS/auto_decision_maker.py
=======================================================
Auto Decision Maker — rule + ML based decisions।
"""


class AutoDecisionMaker:
    """Automated decision making system।"""

    def decide(self, context: str, data: dict, threshold: float = 0.7) -> dict:
        """
        Context-aware automated decisions।
        context: 'fraud_alert' | 'churn_risk' | 'payment' | 'content_flag'
        """
        decision_fns = {
            'fraud_alert':   self._fraud_alert,
            'churn_risk':    self._churn_risk,
            'payment':       self._payment,
            'content_flag':  self._content_flag,
        }
        fn = decision_fns.get(context, self._default)
        result = fn(data, threshold)
        logger.info(f"AutoDecision [{context}]: {result['decision']} conf={result['confidence']:.2f}")
        return result

    def _fraud_alert(self, data: dict, threshold: float) -> dict:
        score = data.get('fraud_score', 0)
        if score >= 0.95: action, conf = 'immediate_block', 0.98
        elif score >= threshold: action, conf = 'restrict_account', 0.85
        else: action, conf = 'monitor', 0.70
        return {'decision': action, 'confidence': conf, 'auto_executed': score >= 0.95}

    def _churn_risk(self, data: dict, threshold: float) -> dict:
        prob = data.get('churn_probability', 0)
        if prob >= 0.8: action, conf = 'send_win_back_campaign', 0.90
        elif prob >= threshold: action, conf = 'send_retention_offer', 0.80
        else: action, conf = 'continue_normal', 0.85
        return {'decision': action, 'confidence': conf, 'auto_executed': True}

    def _payment(self, data: dict, threshold: float) -> dict:
        risk = data.get('payment_risk', 0)
        if risk >= 0.9: action = 'block_payment'
        elif risk >= threshold: action = 'require_2fa'
        else: action = 'approve'
        return {'decision': action, 'confidence': 1 - risk * 0.3, 'auto_executed': True}

    def _content_flag(self, data: dict, threshold: float) -> dict:
        score = data.get('violation_score', 0)
        if score >= 0.9: action = 'auto_remove'
        elif score >= threshold: action = 'send_for_review'
        else: action = 'allow'
        return {'decision': action, 'confidence': score, 'auto_executed': score >= 0.9}

    def _default(self, data: dict, threshold: float) -> dict:
        return {'decision': 'monitor', 'confidence': 0.5, 'auto_executed': False}


"""
api/ai_engine/AUTOMATION_AGENTS/reinforcement_agent.py
=======================================================
Reinforcement Learning Agent — contextual bandit for offer selection।
"""

import random


class ContextualBanditAgent:
    """
    Multi-armed bandit for offer/content selection optimization।
    Epsilon-greedy strategy।
    """

    def __init__(self, arms: List[str], epsilon: float = 0.1):
        self.arms    = arms
        self.epsilon = epsilon
        self.counts  = {arm: 0 for arm in arms}
        self.rewards = {arm: 0.0 for arm in arms}

    def select(self) -> str:
        """Epsilon-greedy arm selection।"""
        if random.random() < self.epsilon:
            return random.choice(self.arms)  # Explore
        return max(self.arms, key=lambda a: self._avg_reward(a))  # Exploit

    def update(self, arm: str, reward: float):
        """Reward receive করে model update করো।"""
        self.counts[arm]  += 1
        n = self.counts[arm]
        self.rewards[arm] = ((n - 1) * self.rewards[arm] + reward) / n

    def _avg_reward(self, arm: str) -> float:
        return self.rewards[arm] if self.counts[arm] > 0 else 1.0  # Optimism init

    def get_stats(self) -> dict:
        return {
            arm: {
                'avg_reward': round(self._avg_reward(arm), 4),
                'count':      self.counts[arm],
            }
            for arm in self.arms
        }
