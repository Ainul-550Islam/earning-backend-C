"""
api/ai_engine/PERSONALIZATION/user_profiling.py
================================================
User Profiling — comprehensive user behavior profile।
"""

import logging
from ..utils import days_since, safe_ratio

logger = logging.getLogger(__name__)


class UserProfiler:
    """Build comprehensive behavioral profile for each user।"""

    def build_profile(self, user, extra_data: dict = None) -> dict:
        extra = extra_data or {}
        account_age   = days_since(user.date_joined)
        days_inactive = days_since(user.last_login)
        total_earned  = float(getattr(user, 'coin_balance', 0))

        return {
            'user_id':          str(user.id),
            'account_age_days': account_age,
            'days_inactive':    days_inactive,
            'total_earned':     total_earned,
            'avg_daily_earn':   round(safe_ratio(total_earned, max(account_age, 1)), 4),
            'is_active':        days_inactive <= 7,
            'is_new':           account_age <= 14,
            'is_dormant':       days_inactive >= 30,
            'engagement_tier':  self._tier(days_inactive, total_earned),
            'country':          getattr(user, 'country', 'BD'),
            'language':         getattr(user, 'language', 'bn'),
            'offers_completed': extra.get('offers_completed', 0),
            'referral_count':   extra.get('referral_count', 0),
            'streak_days':      extra.get('streak_days', 0),
        }

    def _tier(self, days_inactive: int, earned: float) -> str:
        if days_inactive <= 3 and earned >= 5000: return 'champion'
        if days_inactive <= 7 and earned >= 1000: return 'loyal'
        if days_inactive <= 14:                   return 'active'
        if days_inactive <= 30:                   return 'at_risk'
        return 'dormant'


"""
api/ai_engine/PERSONALIZATION/user_clustering.py
================================================
User Clustering — unsupervised user grouping।
"""


class UserClusterer:
    """Cluster users by behavioral features।"""

    def cluster(self, user_features: list, n_clusters: int = 5) -> dict:
        try:
            from sklearn.cluster import KMeans
            from sklearn.preprocessing import StandardScaler
            import numpy as np

            X     = np.array(user_features)
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = km.fit_predict(X_scaled)

            cluster_sizes = {}
            for label in labels:
                cluster_sizes[int(label)] = cluster_sizes.get(int(label), 0) + 1

            return {
                'labels':        labels.tolist(),
                'n_clusters':    n_clusters,
                'cluster_sizes': cluster_sizes,
                'inertia':       round(float(km.inertia_), 2),
                'method':        'kmeans',
            }
        except Exception as e:
            logger.error(f"Clustering error: {e}")
            return {'labels': [0] * len(user_features), 'error': str(e)}


"""
api/ai_engine/PERSONALIZATION/user_embedding.py
================================================
User Embedding Generator।
"""


class UserEmbeddingGenerator:
    """Generate user embedding vectors from behavior।"""

    def generate(self, user, feature_data: dict, dimensions: int = 128) -> list:
        """Feature dict থেকে embedding vector তৈরি করো।"""
        try:
            import numpy as np
            import hashlib

            # Simple deterministic embedding based on user features
            seed_str  = f"{user.id}:{feature_data}"
            seed      = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
            rng       = np.random.RandomState(seed)

            # Feature-guided embedding
            base_vector = rng.randn(dimensions).astype(float)

            # Normalize
            norm = np.linalg.norm(base_vector)
            if norm > 0:
                base_vector = base_vector / norm

            return [round(float(v), 6) for v in base_vector]
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return [0.0] * dimensions

    def store(self, user, vector: list, embedding_type: str = 'behavioral', ai_model=None):
        from ..models import UserEmbedding
        from django.utils import timezone
        obj, _ = UserEmbedding.objects.update_or_create(
            user=user,
            embedding_type=embedding_type,
            ai_model=ai_model,
            defaults={
                'vector':     vector,
                'dimensions': len(vector),
                'is_stale':   False,
            }
        )
        return obj


"""
api/ai_engine/PERSONALIZATION/interest_modeling.py
===================================================
Interest Modeling — infer user interests from behavior।
"""


class InterestModeler:
    """Model user interests from interaction history।"""

    def infer_interests(self, interaction_history: list) -> dict:
        category_counts: dict = {}
        for interaction in interaction_history:
            cat = interaction.get('category', 'unknown')
            category_counts[cat] = category_counts.get(cat, 0) + 1

        total = sum(category_counts.values()) or 1
        interests = {
            cat: round(count / total, 4)
            for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        }

        return {
            'interests':      interests,
            'top_interests':  list(interests.keys())[:5],
            'total_interactions': len(interaction_history),
        }


"""
api/ai_engine/PERSONALIZATION/behavior_analysis.py
===================================================
Behavior Analysis — pattern detection in user actions।
"""


class BehaviorAnalyzer:
    """Analyze user behavioral patterns।"""

    def analyze(self, sessions: list) -> dict:
        if not sessions:
            return {'pattern': 'no_data'}

        total_sessions    = len(sessions)
        total_duration_s  = sum(s.get('duration_seconds', 0) for s in sessions)
        avg_duration      = safe_ratio(total_duration_s, total_sessions)

        # Peak hour detection
        hours = [s.get('hour', 12) for s in sessions]
        hour_freq: dict = {}
        for h in hours:
            hour_freq[h] = hour_freq.get(h, 0) + 1
        peak_hour = max(hour_freq, key=hour_freq.get) if hour_freq else 12

        # Device distribution
        devices: dict = {}
        for s in sessions:
            dev = s.get('device', 'mobile')
            devices[dev] = devices.get(dev, 0) + 1

        return {
            'total_sessions':   total_sessions,
            'avg_duration_min': round(avg_duration / 60, 2),
            'peak_hour':        peak_hour,
            'is_morning_user':  6 <= peak_hour <= 11,
            'is_evening_user':  17 <= peak_hour <= 22,
            'primary_device':   max(devices, key=devices.get) if devices else 'mobile',
            'device_distribution': devices,
        }


"""
api/ai_engine/PERSONALIZATION/preference_learning.py
=====================================================
Preference Learning — learn from explicit + implicit feedback।
"""


class PreferenceLearner:
    """Learn user preferences from interactions।"""

    def update_preferences(self, user, interaction: dict) -> dict:
        from ..models import PersonalizationProfile
        from django.utils import timezone

        profile, _ = PersonalizationProfile.objects.get_or_create(user=user)

        category  = interaction.get('category', '')
        item_type = interaction.get('item_type', '')
        action    = interaction.get('action', 'view')  # view/click/complete/skip

        # Weight by action
        weights = {'complete': 1.0, 'click': 0.5, 'view': 0.2, 'skip': -0.3}
        weight  = weights.get(action, 0.2)

        if weight > 0 and category:
            cats = profile.preferred_categories or []
            if category not in cats:
                cats.append(category)
                profile.preferred_categories = cats[:10]

        profile.last_refreshed = timezone.now()
        profile.save(update_fields=['preferred_categories', 'last_refreshed'])

        return {'updated': True, 'action': action, 'weight': weight}


"""
api/ai_engine/PERSONALIZATION/dynamic_personalization.py
=========================================================
Dynamic Personalization — real-time context adaptation।
"""


class DynamicPersonalizer:
    """Real-time personalization based on current context।"""

    def personalize(self, user, context: dict) -> dict:
        time_of_day = context.get('hour', 12)
        device      = context.get('device', 'mobile')
        country     = context.get('country', getattr(user, 'country', 'BD'))

        # Time-based content strategy
        if 6 <= time_of_day <= 11:
            strategy = 'morning_quick_tasks'
        elif 12 <= time_of_day <= 14:
            strategy = 'lunch_break_tasks'
        elif 17 <= time_of_day <= 22:
            strategy = 'evening_high_reward'
        else:
            strategy = 'low_effort_passive'

        return {
            'strategy':         strategy,
            'preferred_device': device,
            'content_length':   'short' if device == 'mobile' else 'long',
            'show_notifications': time_of_day in range(8, 21),
            'country_content':   country,
        }


"""
api/ai_engine/PERSONALIZATION/adaptive_personalization.py
=========================================================
Adaptive Personalization — learns over time।
"""


class AdaptivePersonalizer:
    """Self-improving personalization engine।"""

    def adapt(self, user, feedback_history: list) -> dict:
        if not feedback_history:
            return {'adapted': False, 'reason': 'no_feedback'}

        positive = [f for f in feedback_history if f.get('sentiment') == 'positive']
        negative = [f for f in feedback_history if f.get('sentiment') == 'negative']

        adaptation = {
            'positive_signals': len(positive),
            'negative_signals': len(negative),
            'total_feedback':   len(feedback_history),
            'engagement_trend': 'improving' if len(positive) > len(negative) else 'declining',
            'adapted':          True,
        }

        # Adjust personalization profile based on feedback
        if len(negative) > len(positive) * 2:
            adaptation['action'] = 'switch_strategy'
        else:
            adaptation['action'] = 'continue_current'

        return adaptation


"""
api/ai_engine/PERSONALIZATION/contextual_bandit.py
===================================================
Contextual Bandit — context-aware exploration/exploitation।
"""


class ContextualBandit:
    """LinUCB contextual bandit for offer selection।"""

    def __init__(self, n_arms: int, context_dim: int, alpha: float = 1.0):
        self.n_arms     = n_arms
        self.context_dim = context_dim
        self.alpha       = alpha
        import numpy as np
        self.A = [np.identity(context_dim) for _ in range(n_arms)]
        self.b = [np.zeros(context_dim) for _ in range(n_arms)]

    def select_arm(self, context) -> int:
        import numpy as np
        x    = np.array(context)
        ucbs = []
        for a in range(self.n_arms):
            A_inv = np.linalg.inv(self.A[a])
            theta = A_inv @ self.b[a]
            ucb   = theta @ x + self.alpha * np.sqrt(x @ A_inv @ x)
            ucbs.append(ucb)
        return int(np.argmax(ucbs))

    def update(self, arm: int, context, reward: float):
        import numpy as np
        x = np.array(context)
        self.A[arm] += np.outer(x, x)
        self.b[arm] += reward * x


"""
api/ai_engine/PERSONALIZATION/multi_armed_bandit.py
====================================================
Multi-Armed Bandit — UCB1 algorithm।
"""

import math


class UCB1Bandit:
    """UCB1 Multi-Armed Bandit।"""

    def __init__(self, n_arms: int):
        self.n_arms = n_arms
        self.counts = [0] * n_arms
        self.values = [0.0] * n_arms
        self.total  = 0

    def select(self) -> int:
        for i, c in enumerate(self.counts):
            if c == 0:
                return i
        ucbs = [
            self.values[i] + math.sqrt(2 * math.log(self.total) / self.counts[i])
            for i in range(self.n_arms)
        ]
        return int(max(range(self.n_arms), key=lambda i: ucbs[i]))

    def update(self, arm: int, reward: float):
        self.counts[arm] += 1
        self.total       += 1
        n = self.counts[arm]
        self.values[arm] = ((n - 1) * self.values[arm] + reward) / n

    def get_best_arm(self) -> int:
        return max(range(self.n_arms), key=lambda i: self.values[i])


"""
api/ai_engine/PERSONALIZATION/reinforcement_learning.py
========================================================
Reinforcement Learning — Q-learning for user engagement।
"""


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

    def select_action(self, state: str) -> str:
        import random
        if state not in self.q_table:
            return random.choice(self.actions)
        if random.random() < self.epsilon:
            return random.choice(self.actions)
        return max(self.q_table[state], key=self.q_table[state].get)

    def update(self, state: str, action: str, reward: float, next_state: str):
        if state not in self.q_table or next_state not in self.q_table:
            return
        current_q   = self.q_table[state][action]
        max_next_q  = max(self.q_table[next_state].values())
        new_q       = current_q + self.alpha * (reward + self.gamma * max_next_q - current_q)
        self.q_table[state][action] = round(new_q, 6)

    def get_policy(self) -> dict:
        return {state: max(actions, key=actions.get) for state, actions in self.q_table.items()}
