"""
Content Based Service

Implements content-based filtering personalization where
user preference vector match for offer routing system.
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple, Set
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django.core.cache import cache
from api.offer_routing.models import (
    UserPreferenceVector, ContextualSignal, PersonalizationConfig,
    OfferAffinityScore, UserOfferHistory,
)
from api.offer_routing.utils import calculate_score, normalize_score
from api.offer_routing.constants import (
    AFFINITY_CACHE_TIMEOUT, PREFERENCE_VECTOR_CACHE_TIMEOUT,
    MAX_PREFERENCE_VECTOR_SIZE,
)
from api.offer_routing.exceptions import PersonalizationError

User = get_user_model()
logger = logging.getLogger(__name__)


class ContentBasedService:
    """Service for content-based filtering personalization."""
    
    def calculate_score(self, user: User, offer: Any, context: Dict[str, Any]) -> float:
        """Calculate content-based filtering score."""
        try:
            # Get user preference vector
            user_vector = UserPreferenceVector.objects.filter(user=user).first()
            if not user_vector:
                return 0.0
            
            # Get offer features
            offer_features = self._extract_offer_features(offer)
            
            # Calculate similarity between user preferences and offer features
            similarity_score = self._calculate_content_similarity(
                user_vector.vector, offer_features
            )
            
            return min(similarity_score, 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating content-based score: {e}")
            return 0.0
    
    def _extract_offer_features(self, offer: Any) -> Dict[str, Any]:
        """Extract features from offer."""
        try:
            features = {}
            
            # Extract category
            if hasattr(offer, 'category'):
                features['category'] = offer.category
            
            # Extract tags
            if hasattr(offer, 'tags'):
                features['tags'] = offer.tags
            
            # Extract description keywords
            if hasattr(offer, 'description'):
                features['description_keywords'] = self._extract_keywords(offer.description)
            
            # Extract price range
            if hasattr(offer, 'price'):
                features['price_range'] = self._get_price_range(offer.price)
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting offer features: {e}")
            return {}
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # This would implement keyword extraction
        # For now, return placeholder
        return []
    
    def _get_price_range(self, price: float) -> str:
        """Get price range category."""
        if price < 10:
            return 'low'
        elif price < 50:
            return 'medium'
        else:
            return 'high'
    
    def _calculate_content_similarity(self, user_preferences: Dict[str, Any], 
                                    offer_features: Dict[str, Any]) -> float:
        """Calculate content similarity between user preferences and offer features."""
        try:
            similarity_score = 0.0
            total_features = 0
            
            # Category matching
            if 'category' in offer_features and 'category' in user_preferences:
                if offer_features['category'] == user_preferences['category']:
                    similarity_score += 30
                total_features += 1
            
            # Tag matching
            if 'tags' in offer_features and 'tags' in user_preferences:
                user_tags = set(user_preferences['tags'])
                offer_tags = set(offer_features['tags'])
                
                if user_tags and offer_tags:
                    tag_similarity = len(user_tags & offer_tags) / len(user_tags | offer_tags)
                    similarity_score += tag_similarity * 40
                total_features += 1
            
            # Price range matching
            if 'price_range' in offer_features and 'price_range' in user_preferences:
                if offer_features['price_range'] == user_preferences['price_range']:
                    similarity_score += 20
                total_features += 1
            
            # Keyword matching
            if 'description_keywords' in offer_features and 'keywords' in user_preferences:
                user_keywords = set(user_preferences['keywords'])
                offer_keywords = set(offer_features['description_keywords'])
                
                if user_keywords and offer_keywords:
                    keyword_similarity = len(user_keywords & offer_keywords) / len(user_keywords | offer_keywords)
                    similarity_score += keyword_similarity * 10
                total_features += 1
            
            # Normalize score
            if total_features > 0:
                similarity_score = similarity_score / total_features
            
            return similarity_score
            
        except Exception as e:
            logger.error(f"Error calculating content similarity: {e}")
            return 0.0
    
    def rebuild_preference_vectors(self) -> int:
        """Rebuild user preference vectors from content analysis."""
        try:
            rebuilt_count = 0
            
            # Get all users
            users = User.objects.all()
            
            for user in users:
                # Analyze user's interaction history
                user_history = UserOfferHistory.objects.filter(user=user)
                
                if user_history.exists():
                    # Build preference vector from content
                    preference_vector = self._build_preference_from_content(user_history)
                    
                    # Save or update preference vector
                    user_vector, created = UserPreferenceVector.objects.update_or_create(
                        user=user,
                        defaults={
                            'vector': preference_vector,
                            'category_weights': self._extract_category_weights(preference_vector)
                        }
                    )
                    
                    rebuilt_count += 1
            
            logger.info(f"Rebuilt {rebuilt_count} preference vectors")
            return rebuilt_count
            
        except Exception as e:
            logger.error(f"Error rebuilding preference vectors: {e}")
            return 0
    
    def _build_preference_from_content(self, user_history: UserOfferHistory) -> Dict[str, Any]:
        """Build preference vector from content analysis."""
        # This would implement content-based preference building
        # For now, return placeholder
        return {}
    
    def _extract_category_weights(self, preference_vector: Dict[str, Any]) -> Dict[str, float]:
        """Extract category weights from preference vector."""
        # This would extract and normalize category weights
        # For now, return placeholder
        return {}


