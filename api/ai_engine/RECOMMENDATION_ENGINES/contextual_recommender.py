"""
api/ai_engine/RECOMMENDATION_ENGINES/contextual_recommender.py
===============================================================
Contextual Recommender — context (time, device, location) based।
User এর current context অনুযায়ী best offers/content recommend করো।
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class ContextualRecommender:
    """
    Context-aware recommendation।
    Signals: time of day, device, country, session_length, weather, event।
    """

    def recommend(self, user, context: dict, item_type: str = 'offer',
                  count: int = 10) -> List[Dict]:
        """Context-enriched recommendations।"""
        try:
            # Context signals extract করো
            hour    = context.get('hour', 12)
            device  = context.get('device', 'mobile')
            country = context.get('country', getattr(user, 'country', 'BD'))

            # Context-based filters
            filters = self._build_filters(hour, device, country)

            # Content-based base recommendations
            from .content_based_filtering import ContentBasedEngine
            base_items = ContentBasedEngine().recommend(user, item_type, count * 2, context)

            # Context score boost
            boosted = []
            for item in base_items:
                boost = self._context_boost(item, filters, hour, device)
                boosted.append({**item, 'score': round(item.get('score', 0.5) * boost, 4),
                                'engine': 'contextual'})

            return sorted(boosted, key=lambda x: x['score'], reverse=True)[:count]

        except Exception as e:
            logger.error(f"Contextual recommender error: {e}")
            from .popularity_recommender import PopularityRecommender
            return PopularityRecommender().recommend(item_type, count)

    def _build_filters(self, hour: int, device: str, country: str) -> dict:
        return {
            'is_morning':    6 <= hour <= 11,
            'is_afternoon':  12 <= hour <= 17,
            'is_evening':    18 <= hour <= 23,
            'is_mobile':     device == 'mobile',
            'country':       country,
            'prefer_short':  device == 'mobile',
        }

    def _context_boost(self, item: dict, filters: dict, hour: int, device: str) -> float:
        boost = 1.0
        difficulty = item.get('difficulty', 'medium')

        # Mobile users prefer easy/short tasks
        if filters['is_mobile'] and difficulty == 'easy':
            boost *= 1.20
        elif not filters['is_mobile'] and difficulty == 'hard':
            boost *= 1.15

        # Evening → high reward offers perform better
        if filters['is_evening'] and float(item.get('reward', 0)) > 100:
            boost *= 1.25

        # Morning → quick tasks
        if filters['is_morning'] and difficulty == 'easy':
            boost *= 1.10

        return round(boost, 4)

    def get_context_insights(self, context: dict) -> dict:
        """Current context এর recommendation strategy explain করো।"""
        hour   = context.get('hour', 12)
        device = context.get('device', 'mobile')

        if 6 <= hour <= 11:
            strategy = 'quick_morning_tasks'
            reason   = 'Morning users prefer fast, easy tasks.'
        elif 12 <= hour <= 14:
            strategy = 'lunch_break_offers'
            reason   = 'Lunch break — medium complexity offers.'
        elif 18 <= hour <= 23:
            strategy = 'evening_high_reward'
            reason   = 'Evening users have more time — high reward tasks.'
        else:
            strategy = 'passive_engagement'
            reason   = 'Off-peak hours — lightweight content.'

        return {
            'strategy':     strategy,
            'reason':       reason,
            'device':       device,
            'prefer_short': device == 'mobile',
        }
