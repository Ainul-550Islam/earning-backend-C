"""
api/ai_engine/PERSONALIZATION/multi_armed_bandit.py
====================================================
Multi-Armed Bandit — exploration vs exploitation।
Offer selection, notification variant selection, pricing tests।
UCB1, Thompson Sampling, Epsilon-Greedy strategies।
"""

import logging
import math
import random
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class UCB1Bandit:
    """
    UCB1 (Upper Confidence Bound) Multi-Armed Bandit।
    Theoretically optimal exploration-exploitation।
    """

    def __init__(self, arms: List[str], c: float = 2.0):
        self.arms   = arms
        self.c      = c  # Exploration constant
        self.counts = {a: 0 for a in arms}
        self.values = {a: 0.0 for a in arms}
        self.total  = 0

    def select(self) -> str:
        """UCB1 formula দিয়ে arm select করো।"""
        # Cold start: try each arm at least once
        for arm in self.arms:
            if self.counts[arm] == 0:
                return arm

        ucb_scores = {}
        for arm in self.arms:
            exploitation = self.values[arm]
            exploration  = self.c * math.sqrt(math.log(self.total) / max(self.counts[arm], 1))
            ucb_scores[arm] = exploitation + exploration

        return max(ucb_scores, key=ucb_scores.get)

    def update(self, arm: str, reward: float):
        """Arm reward দিয়ে model update করো।"""
        self.counts[arm] += 1
        self.total       += 1
        n = self.counts[arm]
        # Incremental mean update
        self.values[arm] = ((n - 1) * self.values[arm] + reward) / n

    def get_best_arm(self) -> str:
        """Current best arm (exploit only)।"""
        if not any(self.counts.values()):
            return self.arms[0]
        return max(self.values, key=self.values.get)

    def get_stats(self) -> dict:
        return {
            arm: {
                "avg_reward": round(self.values[arm], 4),
                "pulls":      self.counts[arm],
                "ucb_score":  round(self.values[arm] + self.c * math.sqrt(
                    math.log(max(self.total, 1)) / max(self.counts[arm], 1)
                ), 4) if self.counts[arm] > 0 else 0,
            }
            for arm in self.arms
        }

    def regret(self) -> float:
        """Cumulative regret calculate করো।"""
        if not self.values:
            return 0.0
        best = max(self.values.values())
        return sum(
            (best - self.values[arm]) * self.counts[arm]
            for arm in self.arms
        )


class ThompsonSamplingBandit:
    """
    Thompson Sampling — Bayesian MAB।
    Beta distribution posterior update।
    Best for binary rewards (click/no-click)।
    """

    def __init__(self, arms: List[str], alpha_prior: float = 1.0, beta_prior: float = 1.0):
        self.arms     = arms
        self.successes = {a: alpha_prior for a in arms}
        self.failures  = {a: beta_prior  for a in arms}
        self.pulls     = {a: 0 for a in arms}

    def select(self) -> str:
        """Thompson Sampling দিয়ে arm select করো।"""
        samples = {
            arm: random.betavariate(self.successes[arm], self.failures[arm])
            for arm in self.arms
        }
        return max(samples, key=samples.get)

    def update(self, arm: str, reward: float):
        """Bernoulli reward দিয়ে Beta posterior update করো।"""
        self.pulls[arm] += 1
        if reward >= 0.5:
            self.successes[arm] += 1
        else:
            self.failures[arm] += 1

    def get_expected_reward(self, arm: str) -> float:
        """Expected reward = alpha / (alpha + beta)।"""
        return self.successes[arm] / (self.successes[arm] + self.failures[arm])

    def get_stats(self) -> dict:
        return {
            arm: {
                "successes":       self.successes[arm],
                "failures":        self.failures[arm],
                "pulls":           self.pulls[arm],
                "expected_reward": round(self.get_expected_reward(arm), 4),
            }
            for arm in self.arms
        }

    def get_best_arm(self) -> str:
        return max(self.arms, key=self.get_expected_reward)

    def credible_interval(self, arm: str, credibility: float = 0.95) -> Tuple[float, float]:
        """Bayesian credible interval।"""
        try:
            from scipy import stats
            alpha = self.successes[arm]
            beta  = self.failures[arm]
            lo    = stats.beta.ppf((1 - credibility) / 2, alpha, beta)
            hi    = stats.beta.ppf(1 - (1 - credibility) / 2, alpha, beta)
            return round(float(lo), 4), round(float(hi), 4)
        except ImportError:
            exp = self.get_expected_reward(arm)
            return round(max(0, exp - 0.1), 4), round(min(1, exp + 0.1), 4)


class EpsilonGreedyBandit:
    """
    Epsilon-Greedy MAB — simplest strategy।
    epsilon fraction of time explore, rest exploit।
    """

    def __init__(self, arms: List[str], epsilon: float = 0.10,
                  decay: float = 0.999):
        self.arms    = arms
        self.epsilon = epsilon
        self.decay   = decay   # Epsilon decays over time
        self.counts  = {a: 0 for a in arms}
        self.rewards = {a: 0.0 for a in arms}
        self.total   = 0

    def select(self) -> str:
        """Epsilon-greedy selection।"""
        if random.random() < self.epsilon:
            return random.choice(self.arms)  # Explore
        # Exploit — cold start check
        untried = [a for a in self.arms if self.counts[a] == 0]
        if untried:
            return random.choice(untried)
        return max(self.arms, key=lambda a: self.rewards[a] / max(self.counts[a], 1))

    def update(self, arm: str, reward: float):
        self.counts[arm]  += 1
        self.rewards[arm] += reward
        self.total        += 1
        self.epsilon       = max(0.01, self.epsilon * self.decay)  # Decay exploration

    def get_avg_reward(self, arm: str) -> float:
        return self.rewards[arm] / max(self.counts[arm], 1)

    def get_best_arm(self) -> str:
        return max(self.arms, key=self.get_avg_reward)

    def get_stats(self) -> dict:
        return {
            arm: {
                "avg_reward": round(self.get_avg_reward(arm), 4),
                "pulls":      self.counts[arm],
                "total_reward": round(self.rewards[arm], 4),
            }
            for arm in self.arms
        }


class OfferSelectionBandit:
    """
    Offer selection using Thompson Sampling।
    Which offer to show for max conversion।
    """

    def __init__(self, offer_ids: List[str]):
        self.bandit = ThompsonSamplingBandit(offer_ids)

    def select_offer(self) -> str:
        return self.bandit.select()

    def record_conversion(self, offer_id: str, converted: bool):
        self.bandit.update(offer_id, 1.0 if converted else 0.0)

    def get_best_offer(self) -> str:
        return self.bandit.get_best_arm()

    def get_offer_stats(self) -> dict:
        return self.bandit.get_stats()
