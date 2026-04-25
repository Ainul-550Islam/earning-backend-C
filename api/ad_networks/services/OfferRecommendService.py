"""
api/ad_networks/services/OfferRecommendService.py
Service for recommending offers based on user profile
SaaS-ready with tenant support
"""

import logging
import json
import math
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, Count, Avg, Sum, F
from django.utils import timezone
from django.contrib.auth.models import User

from api.ad_networks.models import (
    Offer, UserOfferEngagement, OfferConversion, OfferCategory,
    UserOfferEngagement, OfferDailyLimit
)
from api.ad_networks.choices import (
    OfferStatus, EngagementStatus, NetworkCategory,
    DeviceType, Difficulty
)
from api.ad_networks.constants import (
    OFFER_CACHE_TTL,
    CACHE_KEY_PATTERNS,
    MAX_DAILY_OFFER_LIMIT
)

logger = logging.getLogger(__name__)


class OfferRecommendService:
    """
    Service for recommending offers based on user profile and behavior
    """
    
    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id
    
    def get_personalized_recommendations(self, user_id: int, limit: int = 20) -> Dict:
        """
        Get personalized offer recommendations for user
        """
        try:
            # Get user profile and behavior data
            user_data = self._get_user_profile_data(user_id)
            if not user_data['success']:
                return {
                    'success': False,
                    'error': user_data['error'],
                    'recommendations': []
                }
            
            user_profile = user_data['profile']
            
            # Get user behavior analysis
            behavior_data = self._analyze_user_behavior(user_id)
            
            # Calculate recommendation scores
            recommendations = self._calculate_recommendation_scores(
                user_profile, behavior_data, limit
            )
            
            # Apply filters and business rules
            filtered_recommendations = self._apply_business_rules(
                recommendations, user_profile, user_id
            )
            
            # Sort and limit results
            final_recommendations = sorted(
                filtered_recommendations,
                key=lambda x: x['recommendation_score'],
                reverse=True
            )[:limit]
            
            # Add recommendation metadata
            for rec in final_recommendations:
                rec['recommendation_reasons'] = self._get_recommendation_reasons(rec)
                rec['confidence_score'] = self._calculate_confidence_score(rec)
            
            # Cache recommendations
            cache_key = f'user_{user_id}_recommendations'
            cache.set(cache_key, final_recommendations, timeout=OFFER_CACHE_TTL)
            
            logger.info(f"Generated {len(final_recommendations)} recommendations for user {user_id}")
            
            return {
                'success': True,
                'user_id': user_id,
                'total_recommendations': len(final_recommendations),
                'recommendations': final_recommendations,
                'user_profile': user_profile,
                'behavior_analysis': behavior_data
            }
            
        except Exception as e:
            logger.error(f"Failed to get personalized recommendations: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'recommendations': []
            }
    
    def get_category_recommendations(self, user_id: int, category_slug: str, 
                                limit: int = 20) -> Dict:
        """
        Get recommendations for specific category
        """
        try:
            # Get user data
            user_data = self._get_user_profile_data(user_id)
            if not user_data['success']:
                return {
                    'success': False,
                    'error': user_data['error'],
                    'recommendations': []
                }
            
            # Get category
            try:
                category = OfferCategory.objects.get(slug=category_slug, is_active=True)
            except OfferCategory.DoesNotExist:
                return {
                    'success': False,
                    'error': f'Category {category_slug} not found',
                    'recommendations': []
                }
            
            # Get offers in category
            offers = Offer.objects.filter(
                category=category,
                status=OfferStatus.ACTIVE
            ).select_related('ad_network').order_by('-priority', '-created_at')
            
            # Apply user-specific filtering
            filtered_offers = self._filter_offers_for_user(offers, user_data['profile'])
            
            # Calculate category-specific scores
            recommendations = []
            for offer in filtered_offers[:limit]:
                score = self._calculate_category_score(offer, user_data['profile'], category)
                
                recommendations.append({
                    'offer_id': offer.id,
                    'title': offer.title,
                    'description': offer.description[:200],
                    'reward_amount': float(offer.reward_amount),
                    'currency': offer.reward_currency,
                    'category': category.name,
                    'network': offer.ad_network.name,
                    'network_type': offer.ad_network.network_type,
                    'difficulty': offer.difficulty,
                    'estimated_time': offer.estimated_time,
                    'thumbnail': offer.thumbnail,
                    'is_featured': offer.is_featured,
                    'is_hot': offer.is_hot,
                    'is_new': offer.is_new,
                    'recommendation_score': score,
                    'match_percentage': min(100, score * 10),
                    'countries': offer.countries,
                    'platforms': offer.platforms,
                    'device_type': offer.device_type
                })
            
            # Sort by score
            recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
            
            return {
                'success': True,
                'user_id': user_id,
                'category': category.name,
                'category_slug': category_slug,
                'total_recommendations': len(recommendations),
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Failed to get category recommendations: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'recommendations': []
            }
    
    def get_trending_offers(self, user_id: int = None, limit: int = 20) -> Dict:
        """
        Get trending offers based on recent activity
        """
        try:
            # Calculate time range for trending (last 24 hours)
            end_time = timezone.now()
            start_time = end_time - timedelta(hours=24)
            
            # Get trending offers based on recent conversions
            trending_offers = Offer.objects.filter(
                status=OfferStatus.ACTIVE
            ).annotate(
                recent_conversions=Count(
                    'userofferengagement',
                    filter=Q(
                        userofferengagement__status__in=[EngagementStatus.COMPLETED, EngagementStatus.APPROVED],
                        userofferengagement__created_at__gte=start_time,
                        userofferengagement__created_at__lte=end_time
                    )
                ),
                recent_clicks=Count(
                    'userofferengagement',
                    filter=Q(
                        userofferengagement__created_at__gte=start_time,
                        userofferengagement__created_at__lte=end_time
                    )
                )
            ).filter(
                recent_conversions__gt=0
            ).order_by('-recent_conversions', '-recent_clicks')
            
            # Apply user filtering if user_id provided
            if user_id:
                user_data = self._get_user_profile_data(user_id)
                if user_data['success']:
                    trending_offers = self._filter_offers_for_user(trending_offers, user_data['profile'])
            
            # Prepare recommendations
            recommendations = []
            for offer in trending_offers[:limit]:
                # Calculate trending score
                trending_score = self._calculate_trending_score(offer)
                
                recommendations.append({
                    'offer_id': offer.id,
                    'title': offer.title,
                    'description': offer.description[:200],
                    'reward_amount': float(offer.reward_amount),
                    'currency': offer.reward_currency,
                    'category': offer.category.name if offer.category else 'Uncategorized',
                    'network': offer.ad_network.name,
                    'network_type': offer.ad_network.network_type,
                    'difficulty': offer.difficulty,
                    'estimated_time': offer.estimated_time,
                    'thumbnail': offer.thumbnail,
                    'is_featured': offer.is_featured,
                    'is_hot': offer.is_hot,
                    'is_new': offer.is_new,
                    'trending_score': trending_score,
                    'recent_conversions': offer.recent_conversions,
                    'recent_clicks': offer.recent_clicks,
                    'conversion_rate': self._calculate_conversion_rate(offer),
                    'countries': offer.countries,
                    'platforms': offer.platforms,
                    'device_type': offer.device_type
                })
            
            return {
                'success': True,
                'user_id': user_id,
                'period_hours': 24,
                'total_recommendations': len(recommendations),
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Failed to get trending offers: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'recommendations': []
            }
    
    def get_similar_offers(self, offer_id: int, user_id: int = None, 
                          limit: int = 10) -> Dict:
        """
        Get offers similar to a specific offer
        """
        try:
            # Get reference offer
            try:
                reference_offer = Offer.objects.get(id=offer_id, status=OfferStatus.ACTIVE)
            except Offer.DoesNotExist:
                return {
                    'success': False,
                    'error': f'Offer with ID {offer_id} not found',
                    'recommendations': []
                }
            
            # Find similar offers
            similar_offers = Offer.objects.filter(
                status=OfferStatus.ACTIVE
            ).exclude(id=offer_id)
            
            # Similarity criteria
            similarity_filters = Q()
            
            # Same category
            if reference_offer.category:
                similarity_filters |= Q(category=reference_offer.category)
            
            # Same network
            similarity_filters |= Q(ad_network=reference_offer.ad_network)
            
            # Similar reward amount (±50%)
            reward_min = reference_offer.reward_amount * Decimal('0.5')
            reward_max = reference_offer.reward_amount * Decimal('1.5')
            similarity_filters |= Q(
                reward_amount__gte=reward_min,
                reward_amount__lte=reward_max
            )
            
            # Same difficulty
            similarity_filters |= Q(difficulty=reference_offer.difficulty)
            
            # Same estimated time (±50%)
            time_min = reference_offer.estimated_time * 0.5
            time_max = reference_offer.estimated_time * 1.5
            similarity_filters |= Q(
                estimated_time__gte=time_min,
                estimated_time__lte=time_max
            )
            
            similar_offers = similar_offers.filter(similarity_filters).select_related(
                'ad_network', 'category'
            ).distinct()
            
            # Apply user filtering if user_id provided
            if user_id:
                user_data = self._get_user_profile_data(user_id)
                if user_data['success']:
                    similar_offers = self._filter_offers_for_user(similar_offers, user_data['profile'])
            
            # Calculate similarity scores
            recommendations = []
            for offer in similar_offers[:limit]:
                similarity_score = self._calculate_similarity_score(offer, reference_offer)
                
                recommendations.append({
                    'offer_id': offer.id,
                    'title': offer.title,
                    'description': offer.description[:200],
                    'reward_amount': float(offer.reward_amount),
                    'currency': offer.reward_currency,
                    'category': offer.category.name if offer.category else 'Uncategorized',
                    'network': offer.ad_network.name,
                    'network_type': offer.ad_network.network_type,
                    'difficulty': offer.difficulty,
                    'estimated_time': offer.estimated_time,
                    'thumbnail': offer.thumbnail,
                    'is_featured': offer.is_featured,
                    'is_hot': offer.is_hot,
                    'is_new': offer.is_new,
                    'similarity_score': similarity_score,
                    'similarity_percentage': min(100, similarity_score * 20),
                    'similarity_reasons': self._get_similarity_reasons(offer, reference_offer),
                    'countries': offer.countries,
                    'platforms': offer.platforms,
                    'device_type': offer.device_type
                })
            
            # Sort by similarity score
            recommendations.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return {
                'success': True,
                'reference_offer_id': offer_id,
                'user_id': user_id,
                'total_recommendations': len(recommendations),
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Failed to get similar offers: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'recommendations': []
            }
    
    def _get_user_profile_data(self, user_id: int) -> Dict:
        """
        Get user profile and preference data
        """
        try:
            user = User.objects.get(id=user_id)
            
            # Basic user info
            profile_data = {
                'user_id': user.id,
                'email': user.email,
                'date_joined': user.date_joined,
                'is_active': user.is_active,
                'is_verified': getattr(user, 'is_verified', False),
            }
            
            # Extended profile data (if available)
            if hasattr(user, 'profile'):
                profile = user.profile
                profile_data.update({
                    'country': getattr(profile, 'country', None),
                    'age': getattr(profile, 'age', None),
                    'gender': getattr(profile, 'gender', None),
                    'device_type': getattr(profile, 'device_type', 'any'),
                    'interests': getattr(profile, 'interests', []),
                    'preferred_categories': getattr(profile, 'preferred_categories', []),
                    'level': getattr(profile, 'level', 'bronze'),
                    'language': getattr(profile, 'language', 'en'),
                })
            
            return {
                'success': True,
                'profile': profile_data
            }
            
        except User.DoesNotExist:
            return {
                'success': False,
                'error': f'User with ID {user_id} not found'
            }
    
    def _analyze_user_behavior(self, user_id: int) -> Dict:
        """
        Analyze user's past behavior
        """
        try:
            # Get user's engagement history
            end_time = timezone.now()
            start_time = end_time - timedelta(days=30)
            
            engagements = UserOfferEngagement.objects.filter(
                user_id=user_id,
                created_at__gte=start_time,
                created_at__lte=end_time
            ).select_related('offer', 'offer__category', 'offer__ad_network')
            
            # Calculate behavior metrics
            total_engagements = engagements.count()
            completed_engagements = engagements.filter(
                status__in=[EngagementStatus.COMPLETED, EngagementStatus.APPROVED]
            ).count()
            
            # Category preferences
            category_counts = {}
            network_counts = {}
            difficulty_counts = {}
            device_usage = {}
            
            for engagement in engagements:
                # Category preferences
                if engagement.offer and engagement.offer.category:
                    category = engagement.offer.category.name
                    category_counts[category] = category_counts.get(category, 0) + 1
                
                # Network preferences
                if engagement.offer and engagement.offer.ad_network:
                    network = engagement.offer.ad_network.name
                    network_counts[network] = network_counts.get(network, 0) + 1
                
                # Difficulty preferences
                if engagement.offer:
                    difficulty = engagement.offer.difficulty
                    difficulty_counts[difficulty] = difficulty_counts.get(difficulty, 0) + 1
                
                # Device usage
                if engagement.device_info:
                    device = engagement.device_info.get('device', 'unknown')
                    device_usage[device] = device_usage.get(device, 0) + 1
            
            # Calculate preferences (top categories, networks, etc.)
            preferred_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            preferred_networks = sorted(network_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            preferred_difficulty = sorted(difficulty_counts.items(), key=lambda x: x[1], reverse=True)[0] if difficulty_counts else None
            
            # Time patterns
            hourly_activity = {}
            for engagement in engagements:
                hour = engagement.created_at.hour
                hourly_activity[hour] = hourly_activity.get(hour, 0) + 1
            
            peak_hour = max(hourly_activity.items(), key=lambda x: x[1])[0] if hourly_activity else 12
            
            # Calculate completion rate
            completion_rate = (completed_engagements / total_engagements * 100) if total_engagements > 0 else 0
            
            behavior_analysis = {
                'total_engagements': total_engagements,
                'completed_engagements': completed_engagements,
                'completion_rate': round(completion_rate, 2),
                'preferred_categories': preferred_categories,
                'preferred_networks': preferred_networks,
                'preferred_difficulty': preferred_difficulty[0] if preferred_difficulty else 'easy',
                'device_usage': device_usage,
                'peak_activity_hour': peak_hour,
                'activity_pattern': self._classify_activity_pattern(hourly_activity)
            }
            
            return {
                'success': True,
                'analysis': behavior_analysis
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze user behavior: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_recommendation_scores(self, user_profile: Dict, 
                                   behavior_data: Dict, limit: int) -> List[Dict]:
        """
        Calculate recommendation scores for offers
        """
        try:
            # Get candidate offers
            offers = Offer.objects.filter(
                status=OfferStatus.ACTIVE
            ).select_related('ad_network', 'category')
            
            # Apply basic filtering
            filtered_offers = self._filter_offers_for_user(offers, user_profile)
            
            recommendations = []
            
            for offer in filtered_offers[:limit * 2]:  # Get more candidates than needed
                score = 0.0
                
                # Category preference score
                if behavior_data['analysis']['preferred_categories']:
                    for category, count in behavior_data['analysis']['preferred_categories']:
                        if offer.category and offer.category.name == category:
                            score += (count / behavior_data['analysis']['total_engagements']) * 0.3
                
                # Network preference score
                if behavior_data['analysis']['preferred_networks']:
                    for network, count in behavior_data['analysis']['preferred_networks']:
                        if offer.ad_network and offer.ad_network.name == network:
                            score += (count / behavior_data['analysis']['total_engagements']) * 0.2
                
                # Difficulty preference score
                preferred_difficulty = behavior_data['analysis']['preferred_difficulty']
                if offer.difficulty == preferred_difficulty:
                    score += 0.25
                
                # Device compatibility score
                if user_profile.get('device_type') and offer.device_type:
                    if user_profile['device_type'] == offer.device_type or offer.device_type == 'any':
                        score += 0.3
                    elif self._is_device_compatible(user_profile['device_type'], offer.device_type):
                        score += 0.15
                
                # Geographic compatibility score
                if user_profile.get('country') and offer.countries:
                    if user_profile['country'] in offer.countries:
                        score += 0.2
                
                # Reward amount score (based on user level)
                user_level = user_profile.get('level', 'bronze')
                level_multipliers = {
                    'bronze': 1.0,
                    'silver': 1.2,
                    'gold': 1.5,
                    'platinum': 2.0,
                    'diamond': 2.5
                }
                
                reward_score = float(offer.reward_amount) * level_multipliers.get(user_level, 1.0)
                score += min(0.3, reward_score / 100)  # Cap at 0.3
                
                # Time-based score
                current_hour = timezone.now().hour
                peak_hour = behavior_data['analysis']['peak_activity_hour']
                
                # Higher score for offers around peak activity time
                hour_difficulty = abs(current_hour - peak_hour)
                if hour_difficulty <= 2:
                    score += 0.1
                
                # Featured/hot bonus
                if offer.is_featured:
                    score += 0.2
                
                if offer.is_hot:
                    score += 0.15
                
                if offer.is_new:
                    score += 0.1
                
                recommendations.append({
                    'offer': offer,
                    'recommendation_score': score,
                    'score_breakdown': {
                        'category_preference': score * 0.3,
                        'network_preference': score * 0.2,
                        'difficulty_preference': score * 0.25,
                        'device_compatibility': score * 0.3,
                        'geographic_compatibility': score * 0.2,
                        'reward_amount': score * min(0.3, reward_score / 100),
                        'time_based': score * 0.1,
                        'featured_bonus': 0.2 if offer.is_featured else 0,
                        'hot_bonus': 0.15 if offer.is_hot else 0,
                        'new_bonus': 0.1 if offer.is_new else 0
                    }
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to calculate recommendation scores: {str(e)}")
            return []
    
    def _apply_business_rules(self, recommendations: List[Dict], 
                           user_profile: Dict, user_id: int) -> List[Dict]:
        """
        Apply business rules and filters to recommendations
        """
        filtered_recommendations = []
        
        for rec in recommendations:
            offer = rec['offer']
            
            # Check daily limits
            if self._check_daily_limit(user_id, offer.id):
                rec['daily_limit_reached'] = True
                continue
            
            # Check if user already completed
            if self._check_user_completion(user_id, offer.id):
                rec['already_completed'] = True
                continue
            
            # Check offer availability
            if offer.expires_at and offer.expires_at < timezone.now():
                rec['expired'] = True
                continue
            
            # Check minimum age requirement
            if user_profile.get('age') and offer.min_age:
                if user_profile['age'] < offer.min_age:
                    rec['age_restricted'] = True
                    continue
            
            # Add recommendation data
            rec.update({
                'offer_id': offer.id,
                'title': offer.title,
                'description': offer.description[:200],
                'reward_amount': float(offer.reward_amount),
                'currency': offer.reward_currency,
                'category': offer.category.name if offer.category else 'Uncategorized',
                'network': offer.ad_network.name,
                'network_type': offer.ad_network.network_type,
                'difficulty': offer.difficulty,
                'estimated_time': offer.estimated_time,
                'thumbnail': offer.thumbnail,
                'is_featured': offer.is_featured,
                'is_hot': offer.is_hot,
                'is_new': offer.is_new,
                'countries': offer.countries,
                'platforms': offer.platforms,
                'device_type': offer.device_type
            })
            
            filtered_recommendations.append(rec)
        
        return filtered_recommendations
    
    def _filter_offers_for_user(self, offers, user_profile: Dict):
        """
        Filter offers based on user profile
        """
        filtered_offers = offers
        
        # Geographic filtering
        if user_profile.get('country'):
            filtered_offers = filtered_offers.filter(
                Q(countries__isnull=True) | Q(countries__contains=[user_profile['country']])
            )
        
        # Device filtering
        if user_profile.get('device_type') and user_profile['device_type'] != 'any':
            filtered_offers = filtered_offers.filter(
                Q(device_type='any') | Q(device_type=user_profile['device_type'])
            )
        
        # Platform filtering
        if user_profile.get('platforms'):
            filtered_offers = filtered_offers.filter(
                platforms__overlap=user_profile['platforms']
            )
        
        return filtered_offers
    
    def _check_daily_limit(self, user_id: int, offer_id: int) -> bool:
        """
        Check if user has reached daily limit for offer
        """
        try:
            daily_limit = OfferDailyLimit.objects.filter(
                user_id=user_id,
                offer_id=offer_id
            ).first()
            
            if daily_limit:
                return daily_limit.count_today >= daily_limit.daily_limit
            
            return False
            
        except Exception:
            return False
    
    def _check_user_completion(self, user_id: int, offer_id: int) -> bool:
        """
        Check if user has already completed offer
        """
        try:
            return UserOfferEngagement.objects.filter(
                user_id=user_id,
                offer_id=offer_id,
                status__in=[EngagementStatus.COMPLETED, EngagementStatus.APPROVED]
            ).exists()
        except Exception:
            return False
    
    def _is_device_compatible(self, user_device: str, offer_device: str) -> bool:
        """
        Check if user device is compatible with offer device requirements
        """
        compatibility_matrix = {
            'mobile': ['mobile', 'any'],
            'desktop': ['desktop', 'any'],
            'tablet': ['tablet', 'mobile', 'any'],
            'any': ['mobile', 'desktop', 'tablet', 'any']
        }
        
        compatible_devices = compatibility_matrix.get(user_device, ['any'])
        return offer_device in compatible_devices
    
    def _calculate_category_score(self, offer, user_profile: Dict, category) -> float:
        """
        Calculate category-specific recommendation score
        """
        score = 0.0
        
        # Base score for category
        category_multipliers = {
            'offerwall': 1.0,
            'survey': 1.2,
            'video': 0.9,
            'gaming': 1.1,
            'app_install': 1.3,
            'cashback': 0.8
        }
        
        score += category_multipliers.get(category.slug, 1.0)
        
        # User preference for category
        preferred_categories = user_profile.get('preferred_categories', [])
        if category.name in preferred_categories:
            score += 0.5
        
        # Featured bonus
        if offer.is_featured:
            score += 0.2
        
        return score
    
    def _calculate_trending_score(self, offer) -> float:
        """
        Calculate trending score for offer
        """
        score = 0.0
        
        # Recent conversions weight
        if hasattr(offer, 'recent_conversions'):
            score += offer.recent_conversions * 0.1
        
        # Recent clicks weight
        if hasattr(offer, 'recent_clicks'):
            score += offer.recent_clicks * 0.05
        
        # Conversion rate bonus
        conversion_rate = self._calculate_conversion_rate(offer)
        if conversion_rate > 10:  # High conversion rate
            score += 0.3
        elif conversion_rate > 5:  # Good conversion rate
            score += 0.2
        
        # Network popularity
        if offer.ad_network and hasattr(offer.ad_network, 'total_conversions'):
            network_score = min(0.2, offer.ad_network.total_conversions / 1000)
            score += network_score
        
        return score
    
    def _calculate_similarity_score(self, offer1, offer2) -> float:
        """
        Calculate similarity score between two offers
        """
        score = 0.0
        
        # Category similarity
        if offer1.category and offer2.category and offer1.category == offer2.category:
            score += 0.3
        
        # Network similarity
        if offer1.ad_network and offer2.ad_network and offer1.ad_network == offer2.ad_network:
            score += 0.25
        
        # Reward amount similarity
        reward_diff = abs(float(offer1.reward_amount) - float(offer2.reward_amount))
        reward_similarity = max(0, 1 - (reward_diff / max(float(offer1.reward_amount), float(offer2.reward_amount))))
        score += reward_similarity * 0.2
        
        # Difficulty similarity
        if offer1.difficulty == offer2.difficulty:
            score += 0.15
        
        # Time similarity
        time_diff = abs(offer1.estimated_time - offer2.estimated_time)
        time_similarity = max(0, 1 - (time_diff / max(offer1.estimated_time, offer2.estimated_time)))
        score += time_similarity * 0.1
        
        return score
    
    def _calculate_conversion_rate(self, offer) -> float:
        """
        Calculate conversion rate for offer
        """
        if offer.click_count > 0:
            return (offer.total_conversions / offer.click_count) * 100
        return 0.0
    
    def _get_recommendation_reasons(self, recommendation: Dict) -> List[str]:
        """
        Get reasons for recommendation
        """
        reasons = []
        score_breakdown = recommendation.get('score_breakdown', {})
        
        if score_breakdown.get('category_preference', 0) > 0.1:
            reasons.append("Based on your preferred categories")
        
        if score_breakdown.get('network_preference', 0) > 0.1:
            reasons.append("From networks you frequently use")
        
        if score_breakdown.get('difficulty_preference', 0) > 0.2:
            reasons.append("Matches your preferred difficulty level")
        
        if score_breakdown.get('device_compatibility', 0) > 0.2:
            reasons.append("Compatible with your device")
        
        if score_breakdown.get('featured_bonus', 0) > 0:
            reasons.append("Featured offer")
        
        if score_breakdown.get('hot_bonus', 0) > 0:
            reasons.append("Popular offer")
        
        if recommendation.get('recommendation_score', 0) > 0.8:
            reasons.append("Highly recommended for you")
        
        return reasons
    
    def _get_similarity_reasons(self, offer1, offer2) -> List[str]:
        """
        Get reasons for similarity between offers
        """
        reasons = []
        
        if offer1.category and offer2.category and offer1.category == offer2.category:
            reasons.append(f"Same category: {offer1.category.name}")
        
        if offer1.ad_network and offer2.ad_network and offer1.ad_network == offer2.ad_network:
            reasons.append(f"Same network: {offer1.ad_network.name}")
        
        if offer1.difficulty == offer2.difficulty:
            reasons.append(f"Same difficulty: {offer1.difficulty}")
        
        reward_diff = abs(float(offer1.reward_amount) - float(offer2.reward_amount))
        if reward_diff < 1.0:  # Very similar reward amounts
            reasons.append("Similar reward amount")
        
        return reasons
    
    def _calculate_confidence_score(self, recommendation: Dict) -> float:
        """
        Calculate confidence score for recommendation
        """
        base_score = recommendation.get('recommendation_score', 0)
        
        # Data availability confidence
        confidence = min(1.0, base_score / 2.0)  # Base confidence from score
        
        # Boost for featured/new offers
        if recommendation.get('is_featured'):
            confidence += 0.1
        
        if recommendation.get('is_new'):
            confidence += 0.05
        
        return min(1.0, confidence)
    
    def _classify_activity_pattern(self, hourly_activity: Dict) -> str:
        """
        Classify user's activity pattern
        """
        if not hourly_activity:
            return 'unknown'
        
        # Find peak hours
        sorted_hours = sorted(hourly_activity.items(), key=lambda x: x[1], reverse=True)
        peak_hours = [hour for hour, count in sorted_hours[:3] if count > 0]
        
        # Classify pattern
        if all(9 <= hour <= 17 for hour in peak_hours):
            return 'business_hours'
        elif all(18 <= hour <= 23 for hour in peak_hours):
            return 'evening'
        elif all(0 <= hour <= 6 for hour in peak_hours):
            return 'night_owl'
        else:
            return 'mixed'
