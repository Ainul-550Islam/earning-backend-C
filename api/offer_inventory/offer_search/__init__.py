# api/offer_inventory/offer_search/__init__.py
"""
Offer Search & Discovery — Fast offer search using DB full-text + caching.
No Elasticsearch needed — uses PostgreSQL full-text search.
Features: keyword search, filters, ranking, personalized results.
"""
from .search_engine     import OfferSearchEngine
from .personalization   import OfferPersonalization
from .trending_offers   import TrendingOffersEngine

__all__ = ['OfferSearchEngine', 'OfferPersonalization', 'TrendingOffersEngine']
