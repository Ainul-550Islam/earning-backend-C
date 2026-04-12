"""
api/ai_engine/AUTOMATION_AGENTS/self_learning_system.py
========================================================
Self-Learning System — continuously improves from feedback।
Online learning, feedback integration, model drift correction।
Marketing ও engagement strategy auto-optimize করো।
"""

import logging
from typing import List, Dict, Optional, Callable
from django.utils import timezone

logger = logging.getLogger(__name__)


class SelfLearningSystem:
    """
    Continuous learning system that adapts from user feedback।
    Reward signals → weight updates → better decisions।
    """

    def __init__(self, learning_rate: float = 0.01,
                 min_samples: int = 100,
                 update_threshold: float = 0.05):
        self.learning_rate    = learning_rate
        self.min_samples      = min_samples
        self.update_threshold = update_threshold
        self._feedback_buffer: List[Dict] = []
        self._performance_history: List[float] = []

    def learn(self, feedback_events: List[Dict]) -> dict:
        """
        Feedback events থেকে learn করো।
        feedback_events: [{'type': 'positive'/'negative', 'context': {}, 'reward': 0.0-1.0}]
        """
        if not feedback_events:
            return {'learned': False, 'reason': 'No feedback provided'}

        # Buffer এ add করো
        self._feedback_buffer.extend(feedback_events)

        positive = [e for e in feedback_events if e.get('type') == 'positive']
        negative = [e for e in feedback_events if e.get('type') == 'negative']
        neutral  = [e for e in feedback_events if e.get('type') == 'neutral']

        total         = len(feedback_events)
        pos_rate      = len(positive) / total
        learning_rate = self._adaptive_learning_rate(pos_rate)

        # Minimum sample check
        if len(self._feedback_buffer) < self.min_samples:
            return {
                'learned':       False,
                'reason':        f'Need {self.min_samples - len(self._feedback_buffer)} more samples',
                'buffer_size':   len(self._feedback_buffer),
                'min_samples':   self.min_samples,
            }

        # Performance tracking
        self._performance_history.append(pos_rate)
        trend = self._performance_trend()

        # Decide action
        action = self._decide_update_action(pos_rate, trend)
        self._execute_update(action, positive, negative)

        return {
            'learned':          True,
            'events_processed': total,
            'positive_count':   len(positive),
            'negative_count':   len(negative),
            'neutral_count':    len(neutral),
            'positive_rate':    round(pos_rate, 4),
            'learning_rate':    round(learning_rate, 6),
            'performance_trend': trend,
            'action_taken':     action,
            'buffer_size':      len(self._feedback_buffer),
        }

    def _adaptive_learning_rate(self, pos_rate: float) -> float:
        """Performance based adaptive learning rate।"""
        if pos_rate > 0.80:
            return self.learning_rate * 0.5   # Slow down — already good
        if pos_rate < 0.40:
            return self.learning_rate * 2.0   # Speed up — needs improvement
        return self.learning_rate

    def _performance_trend(self) -> str:
        """Recent performance trend calculate করো।"""
        if len(self._performance_history) < 3:
            return 'insufficient_data'
        recent   = self._performance_history[-3:]
        avg_r    = sum(recent) / len(recent)
        earlier  = self._performance_history[:-3][-3:] if len(self._performance_history) > 3 else recent
        avg_e    = sum(earlier) / len(earlier) if earlier else avg_r
        delta    = avg_r - avg_e
        if delta > 0.05:    return 'improving'
        if delta < -0.05:   return 'declining'
        return 'stable'

    def _decide_update_action(self, pos_rate: float, trend: str) -> str:
        """What action to take based on learning signal।"""
        if trend == 'declining' and pos_rate < 0.50:
            return 'major_relearn'
        if pos_rate < 0.40:
            return 'update_weights'
        if trend == 'improving':
            return 'reinforce_current'
        if abs(pos_rate - 0.5) < 0.10:
            return 'explore_new_strategy'
        return 'minor_adjustment'

    def _execute_update(self, action: str,
                         positive: List[Dict],
                         negative: List[Dict]):
        """Learning update execute করো।"""
        logger.info(f"SelfLearning: executing '{action}' "
                    f"(pos={len(positive)}, neg={len(negative)})")

        if action == 'major_relearn':
            self._clear_buffer()
            # Production এ: trigger model retraining
        elif action == 'update_weights':
            self._update_strategy_weights(positive, negative)
        elif action == 'reinforce_current':
            pass  # Keep current strategy
        elif action == 'explore_new_strategy':
            self._explore()

    def _update_strategy_weights(self, positive: List[Dict],
                                   negative: List[Dict]):
        """Strategy weights update করো based on feedback।"""
        try:
            from ..models import PersonalizationProfile
            # Positive signals থেকে popular strategies identify করো
            pos_strategies = [e.get('context', {}).get('strategy', '') for e in positive]
            neg_strategies = [e.get('context', {}).get('strategy', '') for e in negative]
            logger.info(f"Positive strategies: {set(pos_strategies)}")
            logger.info(f"Negative strategies: {set(neg_strategies)}")
        except Exception as e:
            logger.error(f"Weight update error: {e}")

    def _explore(self):
        """New strategies explore করো (epsilon-greedy)।"""
        import random
        strategies = ['content_first', 'reward_first', 'social_proof', 'urgency', 'personalized']
        chosen = random.choice(strategies)
        logger.info(f"SelfLearning: exploring strategy '{chosen}'")

    def _clear_buffer(self):
        """Feedback buffer clear করো (after major relearn)।"""
        self._feedback_buffer = []

    def register_reward(self, action: str, context: dict, reward: float):
        """Single reward signal register করো (for RL integration)।"""
        event = {
            'type':    'positive' if reward >= 0.5 else 'negative',
            'action':  action,
            'context': context,
            'reward':  reward,
            'timestamp': str(timezone.now()),
        }
        self._feedback_buffer.append(event)

        # Auto-learn trigger when buffer is large
        if len(self._feedback_buffer) >= self.min_samples * 2:
            self.learn(self._feedback_buffer[-self.min_samples:])

    def get_learning_stats(self) -> dict:
        """Learning system current stats।"""
        return {
            'buffer_size':         len(self._feedback_buffer),
            'performance_history': self._performance_history[-10:],
            'current_trend':       self._performance_trend(),
            'avg_performance':     round(
                sum(self._performance_history[-20:]) / max(len(self._performance_history[-20:]), 1), 4
            ) if self._performance_history else 0.0,
            'learning_rate':       self.learning_rate,
            'ready_for_update':    len(self._feedback_buffer) >= self.min_samples,
        }

    def suggest_next_experiment(self) -> dict:
        """Next experiment suggest করো based on learning।"""
        trend = self._performance_trend()
        suggestions = {
            'declining':          'A/B test new offer recommendation algorithm',
            'stable':             'Test push notification timing optimization',
            'improving':          'Scale successful strategy to more users',
            'insufficient_data':  'Collect more feedback signals first',
        }
        return {
            'trend':      trend,
            'suggestion': suggestions.get(trend, 'Monitor and collect data'),
            'priority':   'urgent' if trend == 'declining' else 'normal',
        }
