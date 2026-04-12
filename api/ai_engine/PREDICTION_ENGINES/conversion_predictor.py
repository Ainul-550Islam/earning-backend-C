"""
api/ai_engine/PREDICTION_ENGINES/conversion_predictor.py
=========================================================
Conversion Predictor — offer/ad conversion probability।
"""

import logging
from ..utils import normalize_score

logger = logging.getLogger(__name__)


class ConversionPredictor:
    """
    User-Offer conversion probability prediction।
    P(convert | user, offer, context)।
    """

    def predict(self, user, offer_data: dict, context: dict = None) -> dict:
        context = context or {}

        # User signals
        offers_completed  = context.get('offers_completed', 0)
        days_since_login  = context.get('days_since_login', 0)
        engagement_score  = context.get('engagement_score', 0.5)

        # Offer signals
        offer_reward      = float(offer_data.get('reward_amount', 0))
        offer_difficulty  = offer_data.get('difficulty', 'medium')
        offer_category    = offer_data.get('category', '')

        # Base conversion rate by difficulty
        base_rates = {'easy': 0.35, 'medium': 0.20, 'hard': 0.10}
        base_rate  = base_rates.get(offer_difficulty, 0.20)

        # Adjust by user engagement
        engagement_boost = engagement_score * 0.15

        # Adjust by reward amount
        reward_boost = min(0.10, offer_reward / 1000)

        # Penalty for inactive users
        inactivity_penalty = min(0.15, days_since_login * 0.005)

        # Experience boost
        experience_boost = min(0.10, offers_completed * 0.001)

        prob = base_rate + engagement_boost + reward_boost - inactivity_penalty + experience_boost
        prob = max(0.01, min(0.99, prob))

        return {
            'conversion_probability': round(prob, 4),
            'confidence':             0.72,
            'base_rate':              base_rate,
            'offer_difficulty':       offer_difficulty,
            'signals': {
                'engagement_boost':   round(engagement_boost, 4),
                'reward_boost':       round(reward_boost, 4),
                'inactivity_penalty': round(inactivity_penalty, 4),
                'experience_boost':   round(experience_boost, 4),
            },
        }


"""
api/ai_engine/PREDICTION_ENGINES/click_predictor.py
====================================================
Click-Through Rate (CTR) Predictor।
"""


class ClickPredictor:
    """
    P(click | user, item, position, context)।
    """

    POSITION_DECAY = {1: 1.0, 2: 0.85, 3: 0.70, 4: 0.55, 5: 0.45}

    def predict(self, user, item_data: dict, position: int = 1,
                context: dict = None) -> dict:
        context = context or {}

        # Base CTR estimate
        item_type = item_data.get('type', 'offer')
        base_ctrs = {'offer': 0.08, 'ad': 0.03, 'product': 0.05, 'content': 0.06}
        base_ctr  = base_ctrs.get(item_type, 0.05)

        # Position decay
        pos_factor = self.POSITION_DECAY.get(min(position, 5), 0.35)

        # User engagement signal
        engagement = context.get('engagement_score', 0.5)
        user_factor = 0.7 + engagement * 0.6

        # Personalization boost — preferred category
        pref_categories = context.get('preferred_categories', [])
        item_category   = item_data.get('category', '')
        pref_boost      = 0.15 if item_category in pref_categories else 0.0

        # Device factor
        device = context.get('device', 'mobile')
        device_factor = {'mobile': 1.0, 'desktop': 0.85, 'tablet': 0.90}.get(device, 1.0)

        ctr = base_ctr * pos_factor * user_factor * device_factor + pref_boost
        ctr = max(0.001, min(0.99, ctr))

        return {
            'click_probability': round(ctr, 4),
            'confidence':        0.68,
            'base_ctr':          base_ctr,
            'position':          position,
            'personalization_boost': pref_boost > 0,
        }
