"""
api/ai_engine/PERSONALIZATION/reinforcement_learning.py
========================================================
Reinforcement Learning — Q-learning for engagement optimization।
User behavior শেখে এবং reward maximize করে।
"""
import logging, random, math
from typing import List, Dict, Tuple
logger = logging.getLogger(__name__)


class QLearningAgent:
    """Simple Q-learning agent for engagement optimization।"""

    def __init__(self, states: list, actions: list,
                 alpha: float = 0.1, gamma: float = 0.9, epsilon: float = 0.1):
        self.states   = states
        self.actions  = actions
        self.alpha    = alpha
        self.gamma    = gamma
        self.epsilon  = epsilon
        self.q_table  = {s: {a: 0.0 for a in actions} for s in states}
        self.episode_rewards: List[float] = []

    def select_action(self, state: str) -> str:
        """ε-greedy action selection।"""
        if state not in self.q_table:
            return random.choice(self.actions)
        if random.random() < self.epsilon:
            return random.choice(self.actions)
        return max(self.q_table[state], key=self.q_table[state].get)

    def update(self, state: str, action: str, reward: float, next_state: str):
        """Q-value update using Bellman equation।"""
        if state not in self.q_table or next_state not in self.q_table:
            return
        current_q  = self.q_table[state][action]
        max_next_q = max(self.q_table[next_state].values())
        new_q      = current_q + self.alpha * (reward + self.gamma * max_next_q - current_q)
        self.q_table[state][action] = round(new_q, 6)

    def get_policy(self) -> Dict[str, str]:
        """Current optimal policy — each state এর best action।"""
        return {
            state: max(actions, key=actions.get)
            for state, actions in self.q_table.items()
        }

    def decay_epsilon(self, decay: float = 0.995, min_e: float = 0.01):
        """Epsilon decay — exploration কমাও।"""
        self.epsilon = max(min_e, self.epsilon * decay)

    def train_episode(self, env_fn, initial_state: str,
                       max_steps: int = 100) -> float:
        """One training episode।"""
        state        = initial_state
        total_reward = 0.0
        for _ in range(max_steps):
            action          = self.select_action(state)
            next_state, reward, done = env_fn(state, action)
            self.update(state, action, reward, next_state)
            total_reward   += reward
            state           = next_state
            if done:
                break
        self.episode_rewards.append(total_reward)
        self.decay_epsilon()
        return total_reward

    def get_best_action(self, state: str) -> Tuple[str, float]:
        """State এর best action ও value।"""
        if state not in self.q_table:
            return random.choice(self.actions), 0.0
        best = max(self.q_table[state], key=self.q_table[state].get)
        return best, round(self.q_table[state][best], 6)

    def training_summary(self) -> dict:
        rewards = self.episode_rewards
        if not rewards:
            return {'episodes': 0}
        n = len(rewards)
        return {
            'episodes':   n,
            'avg_reward': round(sum(rewards) / n, 4),
            'recent_avg': round(sum(rewards[-10:]) / min(10, n), 4),
            'best':       round(max(rewards), 4),
            'worst':      round(min(rewards), 4),
            'improving':  n >= 10 and sum(rewards[-5:]) > sum(rewards[-10:-5]),
            'epsilon':    round(self.epsilon, 4),
        }

    def save(self) -> dict:
        return {'q_table': self.q_table, 'epsilon': self.epsilon,
                'alpha': self.alpha, 'gamma': self.gamma}

    def load(self, data: dict):
        self.q_table = data.get('q_table', {})
        self.epsilon = data.get('epsilon', 0.1)
        self.alpha   = data.get('alpha', 0.1)
        self.gamma   = data.get('gamma', 0.9)
