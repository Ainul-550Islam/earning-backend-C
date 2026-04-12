"""
api/ai_engine/RECOMMENDATION_ENGINES/content_recommender.py
============================================================
Content Recommender — articles, videos, notifications content।
Engagement history + NLP topic modeling based।
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class ContentRecommender:
    """
    Content recommendation engine।
    Blog posts, tutorials, promotional content, notifications।
    """

    def recommend(self, user, count: int = 10, content_type: str = 'article',
                  context: dict = None) -> List[Dict]:
        context = context or {}
        try:
            from .hybrid_recommender import HybridRecommender
            items = HybridRecommender().recommend(user, item_type='content', count=count, context=context)
            return self._enrich(items, content_type)
        except Exception as e:
            logger.error(f"Content recommend error: {e}")
            return self._default_content(count, content_type)

    def _enrich(self, items: List[Dict], content_type: str) -> List[Dict]:
        return [{**item, 'content_type': content_type} for item in items]

    def _default_content(self, count: int, content_type: str) -> List[Dict]:
        return [
            {'item_id': f'content_{i}', 'item_type': 'content',
             'content_type': content_type, 'score': 0.60, 'engine': 'default'}
            for i in range(count)
        ]

    def recommend_notifications(self, user, count: int = 3) -> List[Dict]:
        """Push notification content recommendations।"""
        from ..PERSONALIZATION.user_profiling import UserProfiler
        profile = UserProfiler().build_profile(user)

        if profile.get('is_dormant'):
            return [{'type': 'win_back', 'message': 'আপনার জন্য বিশেষ অফার অপেক্ষা করছে!',
                     'priority': 'high', 'engine': 'dormant_win_back'}]
        if profile.get('is_new'):
            return [{'type': 'onboarding', 'message': 'প্রথম অফার complete করুন এবং বোনাস পান!',
                     'priority': 'medium', 'engine': 'onboarding'}]
        return [{'type': 'engagement', 'message': 'নতুন অফার এসেছে!',
                 'priority': 'low', 'engine': 'engagement'}]

    def recommend_by_topic(self, user, topics: List[str], count: int = 10) -> List[Dict]:
        """Topic-based content recommendations।"""
        items = []
        for i, topic in enumerate(topics[:count]):
            items.append({
                'item_id':   f'topic_{topic}_{i}',
                'item_type': 'content',
                'topic':     topic,
                'score':     round(0.8 - i * 0.05, 4),
                'engine':    'topic_based',
            })
        return items

    def recommend_help_articles(self, user_query: str, count: int = 5) -> List[Dict]:
        """Help center articles recommend করো।"""
        from ..NLP_ENGINES.intent_classifier import IntentClassifier
        result = IntentClassifier().classify(user_query)
        intent = result.get('intent', 'general')

        articles = {
            'withdrawal': ['How to withdraw funds', 'Minimum withdrawal amount', 'Payment methods'],
            'complaint':  ['Contact support', 'Report an issue', 'Refund policy'],
            'inquiry':    ['How to earn coins', 'Offer completion guide', 'Account setup'],
            'referral':   ['Referral program guide', 'Referral bonus details'],
        }

        relevant = articles.get(intent, articles.get('inquiry', []))
        return [
            {'item_id': f'help_{i}', 'item_type': 'help_article',
             'title': title, 'score': round(0.9 - i * 0.1, 4), 'engine': 'help_match'}
            for i, title in enumerate(relevant[:count])
        ]
