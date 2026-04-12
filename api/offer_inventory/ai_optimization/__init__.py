# api/offer_inventory/ai_optimization/__init__.py
"""
AI Optimization Package.
Smart offer routing, auto-pause, recommendations, A/B testing.
"""
from .smart_link_logic        import SmartLinkOptimizer, OfferScorer, AutoPauseEngine, AIRecommender, CapRotationManager
from .ai_recommender          import AIRecommender as FullAIRecommender
from .auto_pause_offers       import AutoPauseEngine as FullAutoPauseEngine
from .conversion_rate_optimizer import ConversionRateOptimizer
from .dynamic_payout_manager  import DynamicPayoutManager
from .a_b_testing             import ABTestingEngine

__all__ = [
    'SmartLinkOptimizer',
    'OfferScorer',
    'AutoPauseEngine',
    'FullAutoPauseEngine',
    'AIRecommender',
    'FullAIRecommender',
    'CapRotationManager',
    'ConversionRateOptimizer',
    'DynamicPayoutManager',
    'ABTestingEngine',
]
