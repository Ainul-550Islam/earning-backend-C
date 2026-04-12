"""
api/ai_engine/AUTOMATION_AGENTS/reinforcement_agent.py
=======================================================
Reinforcement Agent — RL-based autonomous decision making।
Offer placement, bid optimization, user engagement।
Policy gradient, Q-learning, multi-agent।
"""
import logging, random, math
from typing import List, Dict, Optional, Callable
logger = logging.getLogger(__name__)

class ReinforcementAgent:
    """
    Full Reinforcement Learning agent।
    Environment এর সাথে interact করে reward maximize করো।
    """

    def __init__(self, state_dim: int, action_dim: int,
                 learning_rate: float = 0.001,
                 gamma: float = 0.99,
                 epsilon: float = 0.10):
        self.state_dim     = state_dim
        self.action_dim    = action_dim
        self.learning_rate = learning_rate
        self.gamma         = gamma
        self.epsilon       = epsilon
        self.q_table: Dict = {}
        self.memory: List  = []   # Experience replay buffer
        self.step_count    = 0
        self.episode_rewards: List[float] = []

    def select_action(self, state: tuple) -> int:
        """ε-greedy action selection।"""
        if random.random() < self.epsilon:
            return random.randint(0, self.action_dim - 1)  # Explore
        state_key = str(state)
        if state_key not in self.q_table:
            self.q_table[state_key] = [0.0] * self.action_dim
        return int(max(range(self.action_dim), key=lambda a: self.q_table[state_key][a]))

    def update(self, state: tuple, action: int, reward: float,
               next_state: tuple, done: bool):
        """Q-value update (Q-learning)।"""
        state_key      = str(state)
        next_state_key = str(next_state)

        if state_key not in self.q_table:
            self.q_table[state_key] = [0.0] * self.action_dim
        if next_state_key not in self.q_table:
            self.q_table[next_state_key] = [0.0] * self.action_dim

        # Bellman equation
        max_next_q  = max(self.q_table[next_state_key])
        target      = reward + (0 if done else self.gamma * max_next_q)
        current_q   = self.q_table[state_key][action]
        new_q       = current_q + self.learning_rate * (target - current_q)
        self.q_table[state_key][action] = round(new_q, 8)
        self.step_count += 1

        # Store experience
        self.memory.append((state, action, reward, next_state, done))
        if len(self.memory) > 10000:
            self.memory.pop(0)

    def decay_epsilon(self, decay_rate: float = 0.995, min_epsilon: float = 0.01):
        """Epsilon decay — exploration কমাও।"""
        self.epsilon = max(min_epsilon, self.epsilon * decay_rate)

    def train_episode(self, env_step_fn: Callable,
                       initial_state: tuple,
                       max_steps: int = 200) -> dict:
        """Full episode training।"""
        state           = initial_state
        total_reward    = 0.0
        steps           = 0
        episode_history = []

        for step in range(max_steps):
            action          = self.select_action(state)
            next_state, reward, done = env_step_fn(state, action)
            self.update(state, action, reward, next_state, done)
            total_reward   += reward
            steps          += 1
            episode_history.append({"step": step, "action": action, "reward": reward})
            state           = next_state
            if done:
                break

        self.episode_rewards.append(total_reward)
        self.decay_epsilon()

        return {
            "total_reward":   round(total_reward, 4),
            "steps":          steps,
            "avg_reward":     round(total_reward / max(steps, 1), 4),
            "epsilon":        round(self.epsilon, 4),
            "q_states":       len(self.q_table),
        }

    def batch_replay(self, batch_size: int = 32):
        """Experience replay training।"""
        if len(self.memory) < batch_size:
            return
        batch = random.sample(self.memory, batch_size)
        for state, action, reward, next_state, done in batch:
            self.update(state, action, reward, next_state, done)

    def get_policy(self) -> Dict[str, int]:
        """Current policy — each state এর best action।"""
        return {
            state: max(range(self.action_dim), key=lambda a: q_vals[a])
            for state, q_vals in self.q_table.items()
        }

    def save_policy(self) -> dict:
        """Policy serialize করো।"""
        return {
            "q_table":    self.q_table,
            "epsilon":    self.epsilon,
            "step_count": self.step_count,
            "avg_recent_reward": (
                sum(self.episode_rewards[-10:]) / len(self.episode_rewards[-10:])
                if self.episode_rewards else 0.0
            ),
        }

    def load_policy(self, saved: dict):
        """Policy deserialize করো।"""
        self.q_table    = saved.get("q_table", {})
        self.epsilon    = saved.get("epsilon", 0.10)
        self.step_count = saved.get("step_count", 0)

    def offer_placement_agent(self, state: tuple,
                               offers: List[Dict]) -> Dict:
        """Offer placement RL agent।"""
        if not offers: return {}
        action = self.select_action(state)
        action = action % len(offers)  # Map to offer index
        selected = offers[action]
        return {
            "selected_offer": selected,
            "action_index":   action,
            "epsilon":        round(self.epsilon, 4),
            "exploration":    random.random() < self.epsilon,
        }

    def training_progress(self) -> dict:
        """Training progress statistics।"""
        rewards = self.episode_rewards
        if not rewards: return {"episodes": 0}
        n = len(rewards)
        return {
            "episodes":        n,
            "total_steps":     self.step_count,
            "avg_reward":      round(sum(rewards) / n, 4),
            "recent_avg":      round(sum(rewards[-10:]) / min(10, n), 4),
            "best_episode":    round(max(rewards), 4),
            "epsilon":         round(self.epsilon, 4),
            "improving":       n >= 10 and sum(rewards[-5:]) > sum(rewards[-10:-5]),
        }
