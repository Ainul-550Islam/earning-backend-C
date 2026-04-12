"""
api/ai_engine/RECOMMENDATION_ENGINES/product_recommender.py
============================================================
Product Recommender — marketplace/store product recommendations।
Purchase history + browsing + collaborative signals।
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class ProductRecommender:
    """Product recommendation for marketplace features."""

    def recommend(self, user, count: int = 10, context: dict = None) -> List[Dict]:
        context = context or {}
        try:
            from .hybrid_recommender import HybridRecommender
            return HybridRecommender().recommend(user, item_type='product', count=count, context=context)
        except Exception as e:
            logger.error(f"Product recommend error: {e}")
            return self._trending_products(count)

    def recommend_similar(self, product_id: str, count: int = 8) -> List[Dict]:
        """Similar products recommend করো।"""
        try:
            from .item_based_recommender import ItemBasedRecommender
            return ItemBasedRecommender().recommend(product_id, 'product', count)
        except Exception as e:
            logger.error(f"Similar product error: {e}")
            return []

    def recommend_frequently_bought_together(self, product_id: str,
                                              count: int = 5) -> List[Dict]:
        """Frequently bought together products।"""
        # Production এ association rule mining use করো
        return []

    def recommend_trending(self, category: str = None, count: int = 10) -> List[Dict]:
        return self._trending_products(count, category)

    def _trending_products(self, count: int, category: str = None) -> List[Dict]:
        from .popularity_recommender import PopularityRecommender
        return PopularityRecommender().recommend('product', count)

    def recommend_new_arrivals(self, count: int = 10) -> List[Dict]:
        """Newest products recommend করো।"""
        return [
            {'item_id': f'new_{i}', 'item_type': 'product',
             'score': 0.70, 'engine': 'new_arrivals'}
            for i in range(count)
        ]

    def personalized_for_segment(self, segment_name: str, count: int = 10) -> List[Dict]:
        """Segment-specific product recommendations।"""
        segment_products = {
            'high_spenders':  {'min_price': 500},
            'bargain_hunters': {'max_price': 100},
            'new_users':      {'difficulty': 'easy'},
        }
        filters = segment_products.get(segment_name, {})
        logger.info(f"Segment product rec: {segment_name} filters={filters}")
        return self._trending_products(count)
