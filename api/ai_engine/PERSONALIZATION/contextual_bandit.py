"""
api/ai_engine/PERSONALIZATION/contextual_bandit.py
===================================================
Contextual Bandit — context-aware exploration/exploitation।
LinUCB algorithm — user context + item features combine করো।
Offer personalization, content selection, ad targeting।
"""

import logging
import math
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ContextualBandit:
    """
    LinUCB Contextual Bandit।
    Context vector (user features) + arm (item) → reward prediction।
    """

    def __init__(self, n_arms: int, context_dim: int, alpha: float = 1.0):
        self.n_arms     = n_arms
        self.context_dim = context_dim
        self.alpha       = alpha
        self._init_matrices()

    def _init_matrices(self):
        """A ও b matrices initialize করো।"""
        try:
            import numpy as np
            self.A = [np.identity(self.context_dim) for _ in range(self.n_arms)]
            self.b = [np.zeros(self.context_dim)     for _ in range(self.n_arms)]
        except ImportError:
            # Fallback: Python lists
            self.A = [[1.0 if i == j else 0.0 for j in range(self.context_dim)]
                      for i in range(self.context_dim)]
            self.b = [0.0] * self.context_dim
            logger.warning("numpy not available — using simplified LinUCB")

    def select_arm(self, context: List[float]) -> int:
        """Context vector দিয়ে best arm select করো।"""
        try:
            import numpy as np
            x = np.array(context)
            ucbs = []
            for i in range(self.n_arms):
                A_inv  = np.linalg.inv(self.A[i])
                theta  = A_inv @ self.b[i]
                ucb    = float(theta @ x) + self.alpha * math.sqrt(float(x @ A_inv @ x))
                ucbs.append(ucb)
            return int(max(range(self.n_arms), key=lambda i: ucbs[i]))
        except Exception as e:
            logger.error(f"LinUCB select error: {e}")
            import random
            return random.randint(0, self.n_arms - 1)

    def update(self, arm: int, context: List[float], reward: float):
        """Reward দিয়ে matrices update করো।"""
        try:
            import numpy as np
            x           = np.array(context)
            self.A[arm] += np.outer(x, x)
            self.b[arm] += reward * x
        except Exception as e:
            logger.error(f"LinUCB update error: {e}")

    def get_arm_value(self, arm: int, context: List[float]) -> float:
        """Arm এর estimated value।"""
        try:
            import numpy as np
            x     = np.array(context)
            A_inv = np.linalg.inv(self.A[arm])
            theta = A_inv @ self.b[arm]
            return float(theta @ x)
        except Exception:
            return 0.0

    def get_stats(self) -> dict:
        return {
            "n_arms":      self.n_arms,
            "context_dim": self.context_dim,
            "alpha":       self.alpha,
        }


class OfferContextualBandit:
    """
    Offer selection using contextual bandit।
    User context (age, device, history) → best offer।
    """

    def __init__(self, offer_ids: List[str], context_features: List[str] = None):
        self.offer_ids       = offer_ids
        self.context_features = context_features or [
            "account_age_norm", "days_inactive_norm", "balance_norm",
            "offers_completed_norm", "is_mobile", "is_evening",
        ]
        self.bandit = ContextualBandit(
            n_arms=len(offer_ids),
            context_dim=len(self.context_features),
        )

    def select_offer(self, user_context: Dict) -> str:
        """User context দিয়ে best offer select করো।"""
        context_vector = self._build_context_vector(user_context)
        arm_idx        = self.bandit.select_arm(context_vector)
        return self.offer_ids[arm_idx]

    def record_result(self, offer_id: str, user_context: Dict, converted: bool):
        """Conversion result record করো।"""
        arm_idx        = self.offer_ids.index(offer_id) if offer_id in self.offer_ids else 0
        context_vector = self._build_context_vector(user_context)
        reward         = 1.0 if converted else 0.0
        self.bandit.update(arm_idx, context_vector, reward)

    def _build_context_vector(self, context: Dict) -> List[float]:
        """User context dict → normalized vector।"""
        vector = []
        for feat in self.context_features:
            val = float(context.get(feat, 0.0))
            vector.append(min(1.0, max(0.0, val)))
        return vector

    def get_personalized_ranking(self, user_context: Dict) -> List[Dict]:
        """All offers rank করো for a user।"""
        context_vector = self._build_context_vector(user_context)
        scored = []
        for i, offer_id in enumerate(self.offer_ids):
            value = self.bandit.get_arm_value(i, context_vector)
            scored.append({
                "offer_id": offer_id,
                "score":    round(value, 6),
                "rank":     0,
            })
        scored = sorted(scored, key=lambda x: x["score"], reverse=True)
        for i, item in enumerate(scored):
            item["rank"] = i + 1
        return scored
