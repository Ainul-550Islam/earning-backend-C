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
from ....models import (
    OfferRoute, UserOfferHistory, OfferScore, OfferAffinityScore,
    UserPreferenceVector, RoutingDecisionLog
)
from ....choices import PersonalizationAlgorithm, EventType
from ....constants import (
    CONTENT_BASED_CACHE_TIMEOUT, PREFERENCE_CACHE_TIMEOUT,
    MIN_CONTENT_FEATURES, CONTENT_FEATURE_WEIGHTS,
    CONTENT_SIMILARITY_THRESHOLD, CONTENT_BASED_WEIGHT
)
from ....exceptions import PersonalizationError, ContentBasedError
from ....utils import extract_offer_features, calculate_content_similarity

User = get_user_model()
logger = logging.getLogger(__name__)


class ContentBasedService:
    """
    Service for content-based filtering personalization.
    
    Provides recommendations based on offer content and user preferences:
    - Feature extraction from offers
    - User preference learning
    - Content similarity calculation
    - Profile-based recommendations
    
    Performance targets:
    - Feature extraction: <10ms per offer
    - Similarity calculation: <5ms per comparison
    - Recommendation generation: <30ms for 100 offers
    - Cache hit rate: >85%
    """
    
    def __init__(self):
        self.cache_service = cache
        self.content_stats = {
            'total_recommendations': 0,
            'cache_hits': 0,
            'errors': 0,
            'avg_calculation_time_ms': 0.0
        }
        
        # Content feature extractors
        self._initialize_feature_extractors()
        
        # Content similarity methods
        self.similarity_methods = {
            'cosine': self._cosine_similarity,
            'jaccard': self._jaccard_similarity,
            'euclidean': self._euclidean_similarity,
            'manhattan': self._manhattan_similarity,
            'pearson': self._pearson_correlation
        }
    
    def _initialize_feature_extractors(self):
        """Initialize content feature extractors."""
        self.feature_extractors = {
            'category': self._extract_category_features,
            'tags': self._extract_tag_features,
            'keywords': self._extract_keyword_features,
            'price': self._extract_price_features,
            'brand': self._extract_brand_features,
            'attributes': self._extract_attribute_features,
            'description': self._extract_description_features,
            'demographics': self._extract_demographic_features,
            'performance': self._extract_performance_features,
            'temporal': self._extract_temporal_features
        }
        
        # Feature weights for different feature types
        self.feature_weights = CONTENT_FEATURE_WEIGHTS
    
    def get_content_based_score(self, user: User, offer: OfferRoute, 
                                context: Dict[str, Any]) -> float:
        """
        Get content-based filtering score for user-offer pair.
        
        Args:
            user: User object
            offer: Offer object
            context: User context
            
        Returns:
            Content-based score (0.0-1.0)
        """
        try:
            start_time = timezone.now()
            
            # Check cache first
            cache_key = f"content_score:{user.id}:{offer.id}"
            cached_score = self.cache_service.get(cache_key)
            
            if cached_score is not None:
                self.content_stats['cache_hits'] += 1
                return float(cached_score)
            
            # Get user preferences
            user_preferences = self._get_user_preferences(user)
            
            if not user_preferences:
                return 0.5  # Default score for new users
            
            # Extract offer features
            offer_features = self._extract_offer_features(offer)
            
            if not offer_features:
                return 0.5  # Default score for offers without features
            
            # Calculate content similarity
            content_score = self._calculate_content_similarity(
                user_preferences, offer_features
            )
            
            # Apply contextual adjustments
            adjusted_score = self._apply_contextual_adjustments(
                content_score, user, offer, context
            )
            
            # Cache result
            self.cache_service.set(cache_key, adjusted_score, CONTENT_BASED_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_content_stats(elapsed_ms)
            
            return adjusted_score
            
        except Exception as e:
            logger.error(f"Error calculating content score for user {user.id}, offer {offer.id}: {e}")
            self.content_stats['errors'] += 1
            return 0.5
    
    def _get_user_preferences(self, user: User) -> Optional[Dict[str, Any]]:
        """Get user's content preferences."""
        try:
            # Check cache first
            cache_key = f"user_preferences:{user.id}"
            cached_prefs = self.cache_service.get(cache_key)
            
            if cached_prefs:
                return cached_prefs
            
            # Get preference vector
            preference_vector = UserPreferenceVector.objects.filter(user=user).first()
            
            if not preference_vector:
                return None
            
            # Get affinity scores
            affinity_scores = OfferAffinityScore.objects.filter(user=user)
            
            # Build comprehensive preference profile
            user_preferences = {
                'vector': preference_vector.vector,
                'category_weights': preference_vector.category_weights,
                'affinity_scores': {
                    affinity.category: float(affinity.score) / 100.0
                    for affinity in affinity_scores
                },
                'accuracy_score': float(preference_vector.accuracy_score or 0.0),
                'version': preference_vector.version,
                'last_updated': preference_vector.last_updated
            }
            
            # Cache result
            self.cache_service.set(cache_key, user_preferences, PREFERENCE_CACHE_TIMEOUT)
            
            return user_preferences
            
        except Exception as e:
            logger.error(f"Error getting user preferences for {user.id}: {e}")
            return None
    
    def _extract_offer_features(self, offer: OfferRoute) -> Optional[Dict[str, Any]]:
        """Extract content features from an offer."""
        try:
            # Check cache first
            cache_key = f"offer_features:{offer.id}"
            cached_features = self.cache_service.get(cache_key)
            
            if cached_features:
                return cached_features
            
            # Extract features using all extractors
            features = {}
            
            for feature_type, extractor in self.feature_extractors.items():
                try:
                    feature_data = extractor(offer)
                    if feature_data:
                        features[feature_type] = feature_data
                except Exception as e:
                    logger.warning(f"Error extracting {feature_type} features for offer {offer.id}: {e}")
                    continue
            
            # Validate minimum features
            if len(features) < MIN_CONTENT_FEATURES:
                logger.warning(f"Insufficient features for offer {offer.id}: {len(features)}")
                return None
            
            # Cache result
            self.cache_service.set(cache_key, features, CONTENT_BASED_CACHE_TIMEOUT)
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting features for offer {offer.id}: {e}")
            return None
    
    def _extract_category_features(self, offer: OfferRoute) -> Dict[str, Any]:
        """Extract category-based features."""
        try:
            category = getattr(offer, 'category', 'general')
            subcategory = getattr(offer, 'subcategory', '')
            
            return {
                'primary_category': category,
                'subcategory': subcategory,
                'category_path': f"{category}/{subcategory}" if subcategory else category,
                'is_top_category': subcategory == '',
                'category_depth': len(subcategory.split('/')) if subcategory else 1
            }
            
        except Exception as e:
            logger.error(f"Error extracting category features: {e}")
            return {}
    
    def _extract_tag_features(self, offer: OfferRoute) -> Dict[str, Any]:
        """Extract tag-based features."""
        try:
            tags = getattr(offer, 'tags', [])
            
            if not tags:
                return {}
            
            # Normalize tags
            normalized_tags = [tag.lower().strip() for tag in tags if tag and tag.strip()]
            
            return {
                'tags': normalized_tags,
                'tag_count': len(normalized_tags),
                'tag_types': {
                    'brand_tags': [tag for tag in normalized_tags if self._is_brand_tag(tag)],
                    'feature_tags': [tag for tag in normalized_tags if self._is_feature_tag(tag)],
                    'benefit_tags': [tag for tag in normalized_tags if self._is_benefit_tag(tag)],
                    'audience_tags': [tag for tag in normalized_tags if self._is_audience_tag(tag)]
                }
            }
            
        except Exception as e:
            logger.error(f"Error extracting tag features: {e}")
            return {}
    
    def _extract_keyword_features(self, offer: OfferRoute) -> Dict[str, Any]:
        """Extract keyword-based features from offer description."""
        try:
            title = getattr(offer, 'title', '')
            description = getattr(offer, 'description', '')
            
            # Combine text
            text = f"{title} {description}".lower()
            
            # Extract keywords (simple approach)
            words = text.split()
            keywords = [word.strip('.,!?()[]{}"\'') for word in words if len(word.strip('.,!?()[]{}"\'')) > 2]
            
            # Calculate keyword frequency
            keyword_freq = {}
            for keyword in keywords:
                keyword_freq[keyword] = keyword_freq.get(keyword, 0) + 1
            
            # Get top keywords
            top_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:20]
            
            return {
                'keywords': dict(top_keywords),
                'keyword_count': len(keywords),
                'unique_keywords': len(set(keywords)),
                'keyword_density': {
                    keyword: count / len(keywords) 
                    for keyword, count in top_keywords[:10]
                }
            }
            
        except Exception as e:
            logger.error(f"Error extracting keyword features: {e}")
            return {}
    
    def _extract_price_features(self, offer: OfferRoute) -> Dict[str, Any]:
        """Extract price-based features."""
        try:
            price = getattr(offer, 'price', 0.0)
            original_price = getattr(offer, 'original_price', price)
            discount_price = getattr(offer, 'discount_price', 0.0)
            
            # Calculate price metrics
            discount_percentage = 0.0
            if original_price > 0 and price < original_price:
                discount_percentage = ((original_price - price) / original_price) * 100
            
            # Price category
            if price <= 10:
                price_category = 'budget'
            elif price <= 50:
                price_category = 'mid_range'
            elif price <= 100:
                price_category = 'premium'
            else:
                price_category = 'luxury'
            
            return {
                'price': price,
                'original_price': original_price,
                'discount_price': discount_price,
                'discount_percentage': discount_percentage,
                'price_category': price_category,
                'is_discounted': discount_percentage > 0,
                'is_free': price <= 0
            }
            
        except Exception as e:
            logger.error(f"Error extracting price features: {e}")
            return {}
    
    def _extract_brand_features(self, offer: OfferRoute) -> Dict[str, Any]:
        """Extract brand-based features."""
        try:
            brand = getattr(offer, 'brand', '')
            manufacturer = getattr(offer, 'manufacturer', '')
            
            # Normalize brand
            normalized_brand = brand.lower().strip() if brand else ''
            
            return {
                'brand': normalized_brand,
                'manufacturer': manufacturer.lower().strip() if manufacturer else '',
                'is_known_brand': self._is_known_brand(normalized_brand),
                'brand_tier': self._get_brand_tier(normalized_brand),
                'brand_category': self._get_brand_category(normalized_brand)
            }
            
        except Exception as e:
            logger.error(f"Error extracting brand features: {e}")
            return {}
    
    def _extract_attribute_features(self, offer: OfferRoute) -> Dict[str, Any]:
        """Extract attribute-based features."""
        try:
            attributes = getattr(offer, 'attributes', {})
            
            if not attributes:
                return {}
            
            # Extract common attribute types
            extracted_attributes = {}
            
            for key, value in attributes.items():
                if isinstance(value, (str, int, float, bool)):
                    extracted_attributes[key] = value
                elif isinstance(value, list):
                    extracted_attributes[key] = value
                elif isinstance(value, dict):
                    extracted_attributes.update(value)
            
            return {
                'attributes': extracted_attributes,
                'attribute_count': len(extracted_attributes),
                'attribute_types': list(extracted_attributes.keys())
            }
            
        except Exception as e:
            logger.error(f"Error extracting attribute features: {e}")
            return {}
    
    def _extract_description_features(self, offer: OfferRoute) -> Dict[str, Any]:
        """Extract features from offer description."""
        try:
            description = getattr(offer, 'description', '')
            
            if not description:
                return {}
            
            # Text statistics
            words = description.split()
            sentences = description.split('.')
            
            # Sentiment analysis (simple approach)
            positive_words = ['good', 'great', 'excellent', 'amazing', 'perfect', 'best', 'quality', 'value', 'save', 'discount']
            negative_words = ['bad', 'poor', 'terrible', 'awful', 'worst', 'expensive', 'waste', 'disappoint']
            
            positive_count = sum(1 for word in words if word.lower() in positive_words)
            negative_count = sum(1 for word in words if word.lower() in negative_words)
            
            sentiment_score = 0.0
            total_sentiment_words = positive_count + negative_count
            if total_sentiment_words > 0:
                sentiment_score = (positive_count - negative_count) / total_sentiment_words
            
            return {
                'description_length': len(description),
                'word_count': len(words),
                'sentence_count': len(sentences),
                'avg_words_per_sentence': len(words) / max(1, len(sentences)),
                'sentiment_score': sentiment_score,
                'positive_words': positive_count,
                'negative_words': negative_count
            }
            
        except Exception as e:
            logger.error(f"Error extracting description features: {e}")
            return {}
    
    def _extract_demographic_features(self, offer: OfferRoute) -> Dict[str, Any]:
        """Extract demographic targeting features."""
        try:
            target_demographics = getattr(offer, 'target_demographics', {})
            
            if not target_demographics:
                return {}
            
            return {
                'target_age_range': target_demographics.get('age_range', []),
                'target_gender': target_demographics.get('gender', []),
                'target_income': target_demographics.get('income', []),
                'target_location': target_demographics.get('location', []),
                'target_interests': target_demographics.get('interests', []),
                'target_lifestyle': target_demographics.get('lifestyle', [])
            }
            
        except Exception as e:
            logger.error(f"Error extracting demographic features: {e}")
            return {}
    
    def _extract_performance_features(self, offer: OfferRoute) -> Dict[str, Any]:
        """Extract performance-based features."""
        try:
            # Get recent performance data
            thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
            
            performance_data = UserOfferHistory.objects.filter(
                offer=offer,
                created_at__gte=thirty_days_ago
            ).aggregate(
                total_views=Count('id'),
                total_clicks=Count('id', filter=Q(clicked_at__isnull=False)),
                total_conversions=Count('id', filter=Q(completed_at__isnull=False)),
                avg_conversion_value=Avg('conversion_value')
            )
            
            if not performance_data['total_views']:
                return {}
            
            # Calculate performance metrics
            click_rate = performance_data['total_clicks'] / performance_data['total_views']
            conversion_rate = performance_data['total_conversions'] / performance_data['total_views']
            
            return {
                'total_views': performance_data['total_views'],
                'click_rate': click_rate,
                'conversion_rate': conversion_rate,
                'avg_conversion_value': float(performance_data['avg_conversion_value'] or 0),
                'performance_score': (click_rate * 0.4) + (conversion_rate * 0.6),
                'is_high_performing': conversion_rate > 0.05
            }
            
        except Exception as e:
            logger.error(f"Error extracting performance features: {e}")
            return {}
    
    def _extract_temporal_features(self, offer: OfferRoute) -> Dict[str, Any]:
        """Extract temporal features."""
        try:
            created_at = getattr(offer, 'created_at', timezone.now())
            expires_at = getattr(offer, 'expires_at', None)
            
            # Time-based features
            days_since_creation = (timezone.now() - created_at).days
            
            # Seasonality
            creation_month = created_at.month
            season = self._get_season(creation_month)
            
            # Urgency
            urgency_score = 0.0
            if expires_at:
                days_until_expiry = (expires_at - timezone.now()).days
                if days_until_expiry <= 7:
                    urgency_score = 1.0
                elif days_until_expiry <= 30:
                    urgency_score = 0.7
                elif days_until_expiry <= 90:
                    urgency_score = 0.4
            
            return {
                'days_since_creation': days_since_creation,
                'creation_month': creation_month,
                'creation_year': created_at.year,
                'season': season,
                'urgency_score': urgency_score,
                'is_new_offer': days_since_creation <= 7,
                'is_seasonal': season in ['spring', 'summer', 'fall', 'winter']
            }
            
        except Exception as e:
            logger.error(f"Error extracting temporal features: {e}")
            return {}
    
    def _is_brand_tag(self, tag: str) -> bool:
        """Check if tag is a brand tag."""
        brand_indicators = ['brand', 'official', 'authentic', 'genuine']
        return any(indicator in tag for indicator in brand_indicators)
    
    def _is_feature_tag(self, tag: str) -> bool:
        """Check if tag is a feature tag."""
        feature_indicators = ['feature', 'specification', 'capability', 'function']
        return any(indicator in tag for indicator in feature_indicators)
    
    def _is_benefit_tag(self, tag: str) -> bool:
        """Check if tag is a benefit tag."""
        benefit_indicators = ['benefit', 'advantage', 'save', 'discount', 'deal', 'offer']
        return any(indicator in tag for indicator in benefit_indicators)
    
    def _is_audience_tag(self, tag: str) -> bool:
        """Check if tag is an audience tag."""
        audience_indicators = ['men', 'women', 'kids', 'teens', 'adults', 'seniors']
        return any(indicator in tag for indicator in audience_indicators)
    
    def _is_known_brand(self, brand: str) -> bool:
        """Check if brand is a known brand."""
        known_brands = [
            'apple', 'samsung', 'sony', 'nike', 'adidas', 'microsoft', 'google',
            'amazon', 'netflix', 'disney', 'mcdonalds', 'starbucks'
        ]
        return brand.lower() in known_brands
    
    def _get_brand_tier(self, brand: str) -> str:
        """Get brand tier."""
        luxury_brands = ['gucci', 'prada', 'louis vuitton', 'hermes', 'rolex']
        premium_brands = ['apple', 'sony', 'nike', 'adidas', 'microsoft']
        
        brand_lower = brand.lower()
        if brand_lower in luxury_brands:
            return 'luxury'
        elif brand_lower in premium_brands:
            return 'premium'
        else:
            return 'mainstream'
    
    def _get_brand_category(self, brand: str) -> str:
        """Get brand category."""
        tech_brands = ['apple', 'samsung', 'microsoft', 'google', 'sony']
        fashion_brands = ['nike', 'adidas', 'gucci', 'prada', 'louis vuitton']
        food_brands = ['mcdonalds', 'starbucks', 'coca-cola', 'pepsi']
        
        brand_lower = brand.lower()
        if brand_lower in tech_brands:
            return 'technology'
        elif brand_lower in fashion_brands:
            return 'fashion'
        elif brand_lower in food_brands:
            return 'food'
        else:
            return 'general'
    
    def _get_season(self, month: int) -> str:
        """Get season from month."""
        if month in [12, 1, 2]:
            return 'winter'
        elif month in [3, 4, 5]:
            return 'spring'
        elif month in [6, 7, 8]:
            return 'summer'
        else:
            return 'fall'
    
    def _calculate_content_similarity(self, user_preferences: Dict[str, Any], 
                                   offer_features: Dict[str, Any]) -> float:
        """Calculate content similarity between user preferences and offer features."""
        try:
            similarity_scores = {}
            
            # Category similarity
            if 'category_weights' in user_preferences and 'category' in offer_features:
                category_sim = self._calculate_category_similarity(
                    user_preferences['category_weights'], offer_features['category']
                )
                similarity_scores['category'] = category_sim
            
            # Tag similarity
            if 'affinity_scores' in user_preferences and 'tags' in offer_features:
                tag_sim = self._calculate_tag_similarity(
                    user_preferences['affinity_scores'], offer_features['tags']
                )
                similarity_scores['tags'] = tag_sim
            
            # Keyword similarity
            if 'vector' in user_preferences and 'keywords' in offer_features:
                keyword_sim = self._calculate_keyword_similarity(
                    user_preferences['vector'], offer_features['keywords']
                )
                similarity_scores['keywords'] = keyword_sim
            
            # Price similarity
            if 'vector' in user_preferences and 'price' in offer_features:
                price_sim = self._calculate_price_similarity(
                    user_preferences['vector'], offer_features['price']
                )
                similarity_scores['price'] = price_sim
            
            # Brand similarity
            if 'affinity_scores' in user_preferences and 'brand' in offer_features:
                brand_sim = self._calculate_brand_similarity(
                    user_preferences['affinity_scores'], offer_features['brand']
                )
                similarity_scores['brand'] = brand_sim
            
            # Weighted combination
            total_score = 0.0
            total_weight = 0.0
            
            for feature_type, score in similarity_scores.items():
                weight = self.feature_weights.get(feature_type, 1.0)
                total_score += score * weight
                total_weight += weight
            
            if total_weight > 0:
                final_score = total_score / total_weight
            else:
                final_score = 0.5  # Default score
            
            return min(1.0, max(0.0, final_score))
            
        except Exception as e:
            logger.error(f"Error calculating content similarity: {e}")
            return 0.5
    
    def _calculate_category_similarity(self, user_category_weights: Dict[str, float], 
                                   offer_category: Dict[str, Any]) -> float:
        """Calculate category similarity."""
        try:
            offer_category_name = offer_category.get('primary_category', 'general')
            
            # Get weight for offer's category
            category_weight = user_category_weights.get(offer_category_name, 0.1)
            
            return category_weight
            
        except Exception as e:
            logger.error(f"Error calculating category similarity: {e}")
            return 0.0
    
    def _calculate_tag_similarity(self, user_affinity_scores: Dict[str, float], 
                                offer_tags: Dict[str, Any]) -> float:
        """Calculate tag similarity."""
        try:
            if not offer_tags or not offer_tags.get('tags'):
                return 0.0
            
            offer_tag_list = offer_tags['tags']
            
            # Calculate similarity based on matching tags
            total_similarity = 0.0
            match_count = 0
            
            for tag in offer_tag_list:
                # Check if tag matches any user affinity
                tag_similarity = 0.0
                for category, affinity in user_affinity_scores.items():
                    if self._tag_matches_category(tag, category):
                        tag_similarity = max(tag_similarity, affinity)
                
                if tag_similarity > 0:
                    match_count += 1
                    total_similarity += tag_similarity
            
            # Average similarity for matching tags
            if match_count > 0:
                return total_similarity / match_count
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error calculating tag similarity: {e}")
            return 0.0
    
    def _tag_matches_category(self, tag: str, category: str) -> bool:
        """Check if tag matches a category."""
        try:
            # Simple matching - can be enhanced with semantic analysis
            tag_lower = tag.lower()
            category_lower = category.lower()
            
            # Exact match
            if tag_lower == category_lower:
                return True
            
            # Partial match
            if category_lower in tag_lower or tag_lower in category_lower:
                return True
            
            # Common synonyms
            synonyms = {
                'electronics': ['tech', 'gadget', 'device'],
                'fashion': ['clothing', 'apparel', 'style'],
                'food': ['restaurant', 'dining', 'cuisine'],
                'travel': ['vacation', 'trip', 'holiday']
            }
            
            for cat, syns in synonyms.items():
                if cat == category_lower and any(syn in tag_lower for syn in syns):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking tag-category match: {e}")
            return False
    
    def _calculate_keyword_similarity(self, user_vector: Dict[str, float], 
                                   offer_keywords: Dict[str, Any]) -> float:
        """Calculate keyword similarity."""
        try:
            if not offer_keywords or not offer_keywords.get('keywords'):
                return 0.0
            
            offer_keyword_dict = offer_keywords['keywords']
            
            # Calculate cosine similarity between user vector and offer keywords
            common_keywords = set(user_vector.keys()) & set(offer_keyword_dict.keys())
            
            if not common_keywords:
                return 0.0
            
            # Calculate dot product
            dot_product = sum(
                user_vector[keyword] * offer_keyword_dict[keyword]
                for keyword in common_keywords
            )
            
            # Calculate magnitudes
            user_magnitude = math.sqrt(
                sum(user_vector[keyword] ** 2 for keyword in user_vector)
            )
            offer_magnitude = math.sqrt(
                sum(offer_keyword_dict[keyword] ** 2 for keyword in offer_keyword_dict)
            )
            
            if user_magnitude == 0 or offer_magnitude == 0:
                return 0.0
            
            # Cosine similarity
            cosine_sim = dot_product / (user_magnitude * offer_magnitude)
            
            return max(0.0, min(1.0, cosine_sim))
            
        except Exception as e:
            logger.error(f"Error calculating keyword similarity: {e}")
            return 0.0
    
    def _calculate_price_similarity(self, user_vector: Dict[str, float], 
                                offer_price: Dict[str, Any]) -> float:
        """Calculate price similarity."""
        try:
            if not offer_price:
                return 0.5
            
            price = offer_price.get('price', 0.0)
            price_category = offer_price.get('price_category', 'mid_range')
            
            # Get user's price preference from vector
            price_preference = user_vector.get('price_preference', 0.5)  # 0=budget, 1=luxury
            
            # Calculate similarity based on price category
            category_scores = {
                'budget': 0.0,
                'mid_range': 0.5,
                'premium': 0.7,
                'luxury': 1.0
            }
            
            category_score = category_scores.get(price_category, 0.5)
            
            # Calculate similarity
            price_similarity = 1.0 - abs(price_preference - category_score)
            
            return price_similarity
            
        except Exception as e:
            logger.error(f"Error calculating price similarity: {e}")
            return 0.5
    
    def _calculate_brand_similarity(self, user_affinity_scores: Dict[str, float], 
                                 offer_brand: Dict[str, Any]) -> float:
        """Calculate brand similarity."""
        try:
            if not offer_brand:
                return 0.5
            
            brand_name = offer_brand.get('brand', '')
            brand_tier = offer_brand.get('brand_tier', 'mainstream')
            
            # Check if user has affinity for this brand
            brand_affinity = user_affinity_scores.get(brand_name, 0.0)
            
            # Calculate tier preference
            tier_scores = {
                'mainstream': 0.3,
                'premium': 0.6,
                'luxury': 0.9
            }
            
            tier_score = tier_scores.get(brand_tier, 0.3)
            
            # Combine brand affinity and tier preference
            brand_similarity = (brand_affinity * 0.7) + (tier_score * 0.3)
            
            return min(1.0, max(0.0, brand_similarity))
            
        except Exception as e:
            logger.error(f"Error calculating brand similarity: {e}")
            return 0.5
    
    def _apply_contextual_adjustments(self, content_score: float, user: User, 
                                    offer: OfferRoute, context: Dict[str, Any]) -> float:
        """Apply contextual adjustments to content score."""
        try:
            adjusted_score = content_score
            
            # Time-based adjustments
            current_hour = timezone.now().hour
            if 6 <= current_hour <= 12:  # Morning
                adjusted_score *= 1.05  # 5% boost
            elif 18 <= current_hour <= 22:  # Evening
                adjusted_score *= 1.03  # 3% boost
            
            # Device-based adjustments
            device_type = context.get('device', {}).get('type')
            if device_type == 'mobile':
                adjusted_score *= 1.02  # 2% boost for mobile
            
            # Location-based adjustments
            country = context.get('location', {}).get('country')
            if country in ['US', 'CA', 'UK']:  # High-value markets
                adjusted_score *= 1.04  # 4% boost
            
            # User segment adjustments
            if getattr(user, 'is_premium', False):
                adjusted_score *= 1.1  # 10% boost for premium users
            
            # Offer freshness adjustments
            if 'temporal' in offer._extract_offer_features(offer):
                temporal_features = offer._extract_offer_features(offer)['temporal']
                if temporal_features.get('is_new_offer', False):
                    adjusted_score *= 1.08  # 8% boost for new offers
            
            return min(1.0, max(0.0, adjusted_score))
            
        except Exception as e:
            logger.error(f"Error applying contextual adjustments: {e}")
            return content_score
    
    def get_content_based_recommendations(self, user: User, 
                                       limit: int = 50) -> List[Tuple[OfferRoute, float]]:
        """
        Get content-based recommendations for a user.
        
        Args:
            user: User object
            limit: Maximum number of recommendations
            
        Returns:
            List of (offer, score) tuples
        """
        try:
            start_time = timezone.now()
            
            # Check cache first
            cache_key = f"content_recs:{user.id}"
            cached_recs = self.cache_service.get(cache_key)
            
            if cached_recs:
                self.content_stats['cache_hits'] += 1
                return cached_recs
            
            # Get user preferences
            user_preferences = self._get_user_preferences(user)
            
            if not user_preferences:
                return []
            
            # Get candidate offers
            candidate_offers = OfferRoute.objects.filter(is_active=True)[:500]
            
            # Score all candidates
            scored_offers = []
            
            for offer in candidate_offers:
                content_score = self.get_content_based_score(user, offer, {})
                scored_offers.append((offer, content_score))
            
            # Sort by score and limit
            scored_offers.sort(key=lambda x: x[1], reverse=True)
            recommendations = scored_offers[:limit]
            
            # Cache result
            self.cache_service.set(cache_key, recommendations, CONTENT_BASED_CACHE_TIMEOUT)
            
            # Update stats
            elapsed_ms = (timezone.now() - start_time).total_seconds() * 1000
            self._update_content_stats(elapsed_ms)
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting content-based recommendations for user {user.id}: {e}")
            return []
    
    def _update_content_stats(self, elapsed_ms: float):
        """Update content-based filtering performance statistics."""
        self.content_stats['total_recommendations'] += 1
        
        # Update average time
        current_avg = self.content_stats['avg_calculation_time_ms']
        total_recs = self.content_stats['total_recommendations']
        self.content_stats['avg_calculation_time_ms'] = (
            (current_avg * (total_recs - 1) + elapsed_ms) / total_recs
        )
    
    def get_content_based_stats(self) -> Dict[str, Any]:
        """Get content-based filtering performance statistics."""
        total_requests = self.content_stats['total_recommendations']
        cache_hit_rate = (
            self.content_stats['cache_hits'] / max(1, total_requests)
        )
        
        return {
            'total_recommendations': total_requests,
            'cache_hits': self.content_stats['cache_hits'],
            'cache_misses': total_requests - self.content_stats['cache_hits'],
            'cache_hit_rate': cache_hit_rate,
            'errors': self.content_stats['errors'],
            'error_rate': self.content_stats['errors'] / max(1, total_requests),
            'avg_calculation_time_ms': self.content_stats['avg_calculation_time_ms'],
            'feature_extractors': list(self.feature_extractors.keys()),
            'similarity_methods': list(self.similarity_methods.keys())
        }
    
    def clear_cache(self, user_id: int = None, offer_id: int = None):
        """Clear content-based filtering cache."""
        try:
            if user_id:
                # Clear specific user cache
                cache_keys = [
                    f"user_preferences:{user_id}",
                    f"content_score:{user_id}:*",
                    f"content_recs:{user_id}"
                ]
                
                for key_pattern in cache_keys:
                    # This would need pattern deletion support
                    logger.info(f"Cache clearing for pattern {key_pattern} not implemented")
            
            if offer_id:
                # Clear specific offer cache
                cache_key = f"offer_features:{offer_id}"
                self.cache_service.delete(cache_key)
                logger.info(f"Cleared cache for offer {offer_id}")
            
            if not user_id and not offer_id:
                # Clear all content-based cache
                logger.info("Cache clearing for all content-based filtering not implemented")
                
        except Exception as e:
            logger.error(f"Error clearing content-based cache: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on content-based filtering service."""
        try:
            # Test feature extraction
            test_offer = type('MockOffer', (), {
                'id': 1,
                'category': 'electronics',
                'tags': ['tech', 'gadget'],
                'price': 99.99,
                'brand': 'TestBrand',
                'description': 'A great test product',
                'created_at': timezone.now()
            })()
            
            test_features = self._extract_offer_features(test_offer)
            
            # Test similarity calculation
            test_user_prefs = {
                'vector': {'electronics': 0.8, 'tech': 0.9},
                'category_weights': {'electronics': 0.8},
                'affinity_scores': {'TestBrand': 0.7}
            }
            
            test_similarity = self._calculate_content_similarity(test_user_prefs, test_features)
            
            # Test recommendation generation
            test_user = User(id=1, username='test')
            test_recommendations = self.get_content_based_recommendations(test_user, limit=5)
            
            return {
                'status': 'healthy',
                'test_feature_extraction': len(test_features) >= MIN_CONTENT_FEATURES,
                'test_similarity_calculation': 0.0 <= test_similarity <= 1.0,
                'test_recommendation_count': len(test_recommendations),
                'stats': self.get_content_based_stats(),
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
