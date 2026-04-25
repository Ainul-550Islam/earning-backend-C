"""
Personalization Service for Offer Routing System

This module provides personalization functionality including
collaborative filtering, content-based filtering, and
hybrid approaches.
"""

import logging
import math
from typing import Dict, List, Any, Optional, Tuple
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Avg, Count, Sum
from ..models import (
    UserPreferenceVector, ContextualSignal, PersonalizationConfig,
    OfferAffinityScore, UserOfferHistory
)
from ..utils import calculate_score, normalize_score
from ..constants import (
    AFFINITY_CACHE_TIMEOUT, PREFERENCE_VECTOR_CACHE_TIMEOUT,
    MAX_PREFERENCE_VECTOR_SIZE
)
from ..exceptions import PersonalizationError

User = get_user_model()
logger = logging.getLogger(__name__)


class PersonalizationService:
    """
    Service for personalizing offer recommendations.
    
    Provides collaborative filtering, content-based filtering,
    and hybrid personalization approaches.
    """
    
    def __init__(self):
        self.cache_service = None
        self.collaborative_service = None
        self.content_based_service = None
        self.affinity_service = None
        
        # Initialize services
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize personalization services."""
        try:
            from .cache import RoutingCacheService
            
            self.cache_service = RoutingCacheService()
            self.collaborative_service = CollaborativeFilterService()
            self.content_based_service = ContentBasedService()
            self.affinity_service = AffinityService()
            
        except ImportError as e:
            logger.error(f"Failed to initialize personalization services: {e}")
            raise
    
    def is_enabled(self, user: User) -> bool:
        """Check if personalization is enabled for user."""
        try:
            config = PersonalizationConfig.objects.filter(
                tenant=user.tenant,
                is_active=True
            ).first()
            
            if not config:
                return False
            
            return config.algorithm != 'rule_based'
            
        except Exception as e:
            logger.error(f"Error checking personalization enabled: {e}")
            return False
    
    def apply_personalization(self, user: User, offer: Any, score_data: Dict[str, Any], 
                           context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply personalization to offer score.
        
        Args:
            user: User object
            offer: Offer object
            score_data: Current score data
            context: User context
            
        Returns:
            Dictionary with personalization data
        """
        try:
            # Get personalization config
            config = self._get_personalization_config(user)
            
            if not config or config.algorithm == 'rule_based':
                return {
                    'personalization_applied': False,
                    'personalization_score': 0.0,
                    'algorithm': 'rule_based'
                }
            
            # Calculate personalization score based on algorithm
            if config.algorithm == 'collaborative':
                personalization_score = self.collaborative_service.calculate_score(
                    user, offer, context
                )
            elif config.algorithm == 'content_based':
                personalization_score = self.content_based_service.calculate_score(
                    user, offer, context
                )
            elif config.algorithm == 'hybrid':
                personalization_score = self._calculate_hybrid_score(
                    user, offer, context, config
                )
            else:
                personalization_score = 0.0
            
            # Get contextual signals
            contextual_score = self._get_contextual_score(user, context)
            
            # Combine scores
            if config.real_time_enabled and contextual_score > 0:
                combined_score = (
                    personalization_score * (1 - config.real_time_weight) +
                    contextual_score * config.real_time_weight
                )
            else:
                combined_score = personalization_score
            
            return {
                'personalization_applied': True,
                'personalization_score': combined_score,
                'algorithm': config.algorithm,
                'components': {
                    'collaborative_score': personalization_score if config.algorithm in ['collaborative', 'hybrid'] else 0.0,
                    'content_based_score': personalization_score if config.algorithm in ['content_based', 'hybrid'] else 0.0,
                    'contextual_score': contextual_score
                }
            }
            
        except Exception as e:
            logger.error(f"Error applying personalization: {e}")
            return {
                'personalization_applied': False,
                'personalization_score': 0.0,
                'error': str(e)
            }
    
    def _get_personalization_config(self, user: User) -> Optional[PersonalizationConfig]:
        """Get personalization configuration for user."""
        try:
            return PersonalizationConfig.objects.filter(
                user=user,
                is_active=True
            ).first()
        except Exception as e:
            logger.error(f"Error getting personalization config: {e}")
            return None
    
    def _calculate_hybrid_score(self, user: User, offer: Any, context: Dict[str, Any], 
                              config: PersonalizationConfig) -> float:
        """Calculate hybrid personalization score."""
        try:
            # Get collaborative filtering score
            collaborative_score = self.collaborative_service.calculate_score(
                user, offer, context
            )
            
            # Get content-based score
            content_based_score = self.content_based_service.calculate_score(
                user, offer, context
            )
            
            # Combine using weights
            weights = config.get_effective_weights()
            
            hybrid_score = (
                collaborative_score * weights['collaborative'] +
                content_based_score * weights['content_based']
            )
            
            return min(hybrid_score, 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating hybrid score: {e}")
            return 0.0
    
    def _get_contextual_score(self, user: User, context: Dict[str, Any]) -> float:
        """Get contextual personalization score."""
        try:
            contextual_score = 0.0
            
            # Get contextual signals
            signals = ContextualSignal.objects.filter(
                user=user,
                expires_at__gt=timezone.now()
            )
            
            for signal in signals:
                signal_weight = self._get_signal_weight(signal.signal_type)
                signal_score = self._calculate_signal_score(signal, context)
                contextual_score += signal_score * signal_weight
            
            return min(contextual_score, 100.0)
            
        except Exception as e:
            logger.error(f"Error getting contextual score: {e}")
            return 0.0
    
    def _get_signal_weight(self, signal_type: str) -> float:
        """Get weight for signal type."""
        weights = {
            'time': 0.2,
            'location': 0.3,
            'device': 0.15,
            'behavior': 0.25,
            'context': 0.1
        }
        return weights.get(signal_type, 0.1)
    
    def _calculate_signal_score(self, signal: ContextualSignal, context: Dict[str, Any]) -> float:
        """Calculate score for a contextual signal."""
        try:
            if signal.signal_type == 'time':
                return self._calculate_time_signal_score(signal, context)
            elif signal.signal_type == 'location':
                return self._calculate_location_signal_score(signal, context)
            elif signal.signal_type == 'device':
                return self._calculate_device_signal_score(signal, context)
            elif signal.signal_type == 'behavior':
                return self._calculate_behavior_signal_score(signal, context)
            elif signal.signal_type == 'context':
                return self._calculate_context_signal_score(signal, context)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating signal score: {e}")
            return 0.0
    
    def _calculate_time_signal_score(self, signal: ContextualSignal, context: Dict[str, Any]) -> float:
        """Calculate time signal score."""
        # This would implement time-based scoring logic
        return signal.confidence * 100.0
    
    def _calculate_location_signal_score(self, signal: ContextualSignal, context: Dict[str, Any]) -> float:
        """Calculate location signal score."""
        # This would implement location-based scoring logic
        return signal.confidence * 100.0
    
    def _calculate_device_signal_score(self, signal: ContextualSignal, context: Dict[str, Any]) -> float:
        """Calculate device signal score."""
        # This would implement device-based scoring logic
        return signal.confidence * 100.0
    
    def _calculate_behavior_signal_score(self, signal: ContextualSignal, context: Dict[str, Any]) -> float:
        """Calculate behavior signal score."""
        # This would implement behavior-based scoring logic
        return signal.confidence * 100.0
    
    def _calculate_context_signal_score(self, signal: ContextualSignal, context: Dict[str, Any]) -> float:
        """Calculate context signal score."""
        # This would implement context-based scoring logic
        return signal.confidence * 100.0
    
    def update_user_preferences(self, user: User, interaction_data: Dict[str, Any]) -> bool:
        """Update user preferences based on interactions."""
        try:
            # Get or create preference vector
            preference_vector, created = UserPreferenceVector.objects.get_or_create(
                user=user,
                defaults={
                    'vector': {},
                    'category_weights': {}
                }
            )
            
            # Update based on interactions
            if 'offer_interactions' in interaction_data:
                self._update_preferences_from_interactions(
                    preference_vector, interaction_data['offer_interactions']
                )
            
            # Update accuracy score
            self._update_accuracy_score(preference_vector)
            
            preference_vector.save()
            
            # Cache updated preferences
            if self.cache_service:
                self.cache_service.set_preference_vector(
                    user.id, 
                    preference_vector.vector
                )
            
            logger.info(f"Updated preferences for user {user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
            return False
    
    def _update_preferences_from_interactions(self, preference_vector: UserPreferenceVector, 
                                           interactions: List[Dict[str, Any]]):
        """Update preferences from offer interactions."""
        try:
            for interaction in interactions:
                offer_category = interaction.get('category')
                interaction_type = interaction.get('type')  # click, purchase, etc.
                interaction_value = interaction.get('value', 1.0)
                
                if not offer_category:
                    continue
                
                # Update category weight based on interaction
                current_weight = preference_vector.category_weights.get(offer_category, 0.1)
                
                # Apply learning rate based on interaction type
                learning_rate = self._get_learning_rate(interaction_type)
                
                # Update weight
                new_weight = current_weight + (interaction_value * learning_rate)
                preference_vector.category_weights[offer_category] = min(new_weight, 1.0)
            
            # Normalize weights
            total_weight = sum(preference_vector.category_weights.values())
            if total_weight > 0:
                for category in preference_vector.category_weights:
                    preference_vector.category_weights[category] /= total_weight
            
        except Exception as e:
            logger.error(f"Error updating preferences from interactions: {e}")
    
    def _get_learning_rate(self, interaction_type: str) -> float:
        """Get learning rate for interaction type."""
        rates = {
            'purchase': 0.1,
            'click': 0.05,
            'view': 0.02,
            'ignore': -0.01
        }
        return rates.get(interaction_type, 0.01)
    
    def _update_accuracy_score(self, preference_vector: UserPreferenceVector):
        """Update accuracy score for preference vector."""
        try:
            # This would calculate accuracy based on recent predictions
            # For now, set a placeholder
            preference_vector.accuracy_score = 0.75
        except Exception as e:
            logger.error(f"Error updating accuracy score: {e}")


class CollaborativeFilterService:
    """Service for collaborative filtering personalization."""
    
    def calculate_score(self, user: User, offer: Any, context: Dict[str, Any]) -> float:
        """Calculate collaborative filtering score."""
        try:
            # Get similar users
            similar_users = self._get_similar_users(user)
            
            if not similar_users:
                return 0.0
            
            # Get ratings from similar users for this offer
            ratings = self._get_user_ratings_for_offer(similar_users, offer)
            
            if not ratings:
                return 0.0
            
            # Calculate weighted average
            weighted_score = 0.0
            total_weight = 0.0
            
            for similar_user, similarity, rating in ratings:
                weight = similarity * rating
                weighted_score += weight
                total_weight += similarity
            
            if total_weight == 0:
                return 0.0
            
            collaborative_score = weighted_score / total_weight
            return min(collaborative_score, 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating collaborative score: {e}")
            return 0.0
    
    def _get_similar_users(self, user: User, limit: int = 50) -> List[Tuple[User, float]]:
        """Get similar users based on preference vectors."""
        try:
            user_vector = UserPreferenceVector.objects.filter(user=user).first()
            if not user_vector:
                return []
            
            similar_users = []
            
            # Get all other users with preference vectors
            other_vectors = UserPreferenceVector.objects.exclude(user=user)
            
            for other_vector in other_vectors:
                similarity = user_vector.calculate_similarity(other_vector.vector)
                if similarity > 0.1:  # Minimum similarity threshold
                    similar_users.append((other_vector.user, similarity))
            
            # Sort by similarity and limit
            similar_users.sort(key=lambda x: x[1], reverse=True)
            return similar_users[:limit]
            
        except Exception as e:
            logger.error(f"Error getting similar users: {e}")
            return []
    
    def _get_user_ratings_for_offer(self, similar_users: List[Tuple[User, float]], 
                                   offer: Any) -> List[Tuple[User, float, float]]:
        """Get ratings from similar users for an offer."""
        try:
            ratings = []
            
            for similar_user, similarity in similar_users:
                # Get user's interaction history with this offer
                user_history = UserOfferHistory.objects.filter(
                    user=similar_user,
                    offer=offer
                ).first()
                
                if user_history:
                    # Calculate rating based on interactions
                    rating = self._calculate_user_rating(user_history)
                    ratings.append((similar_user, similarity, rating))
            
            return ratings
            
        except Exception as e:
            logger.error(f"Error getting user ratings: {e}")
            return []
    
    def _calculate_user_rating(self, user_history: UserOfferHistory) -> float:
        """Calculate user rating from interaction history."""
        try:
            rating = 0.0
            
            # Base rating from interactions
            if user_history.completed_at:
                rating += 100  # Purchase
            elif user_history.clicked_at:
                rating += 50   # Click
            elif user_history.viewed_at:
                rating += 10   # View
            
            # Adjust by conversion value
            if user_history.conversion_value > 0:
                rating += min(user_history.conversion_value * 10, 50)
            
            return min(rating, 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating user rating: {e}")
            return 0.0
    
    def update_affinity_scores(self) -> int:
        """Update user-category affinity scores."""
        try:
            updated_count = 0
            
            # Get all users with preference vectors
            users_with_vectors = UserPreferenceVector.objects.all()
            
            for user_vector in users_with_vectors:
                # Update affinity scores for each category
                for category, weight in user_vector.category_weights.items():
                    OfferAffinityScore.objects.update_or_create(
                        user=user_vector.user,
                        category=category,
                        defaults={
                            'score': weight * 100,
                            'confidence': user_vector.accuracy_score,
                            'implicit_score': weight * 100,
                            'explicit_score': 0.0,
                            'collaborative_score': weight * 100,
                            'content_based_score': 0.0,
                            'sample_size': 100  # Placeholder
                        }
                    )
                    updated_count += 1
            
            logger.info(f"Updated {updated_count} affinity scores")
            return updated_count
            
        except Exception as e:
            logger.error(f"Error updating affinity scores: {e}")
            return 0


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


class AffinityService:
    """Service for managing user-category affinity scores."""
    
    def get_affinity_score(self, user_id: int, category: str) -> Optional[Dict[str, Any]]:
        """Get affinity score for user and category."""
        try:
            affinity = OfferAffinityScore.objects.filter(
                user_id=user_id,
                category=category
            ).first()
            
            if affinity:
                return {
                    'score': affinity.score,
                    'confidence': affinity.confidence,
                    'implicit_score': affinity.implicit_score,
                    'explicit_score': affinity.explicit_score,
                    'collaborative_score': affinity.collaborative_score,
                    'content_based_score': affinity.content_based_score
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting affinity score: {e}")
            return None
    
    def update_affinity_score(self, user_id: int, category: str, score: float, 
                            confidence: float = 1.0):
        """Update affinity score for user and category."""
        try:
            OfferAffinityScore.objects.update_or_create(
                user_id=user_id,
                category=category,
                defaults={
                    'score': score,
                    'confidence': confidence,
                    'implicit_score': score,
                    'explicit_score': 0.0,
                    'collaborative_score': score,
                    'content_based_score': 0.0,
                    'sample_size': 100
                }
            )
            
        except Exception as e:
            logger.error(f"Error updating affinity score: {e}")


# Singleton instances
personalization_service = PersonalizationService()
collaborative_service = CollaborativeFilterService()
content_based_service = ContentBasedService()
affinity_service = AffinityService()
