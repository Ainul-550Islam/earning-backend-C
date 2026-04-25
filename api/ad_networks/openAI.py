"""
api/ad_networks/openAI.py
OpenAI integration for ad networks module
SaaS-ready with tenant support
"""

import logging
import json
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model

try:
    import openai
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None
    AsyncOpenAI = None

from .models import Offer, UserOfferEngagement, OfferConversion, OfferReward
from .choices import OfferStatus, EngagementStatus, ConversionStatus, RewardStatus
from .constants import CACHE_TIMEOUTS

logger = logging.getLogger(__name__)
User = get_user_model()


class OpenAIConfig:
    """Configuration for OpenAI integration"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'OPENAI_API_KEY', None)
        self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-3.5-turbo')
        self.max_tokens = getattr(settings, 'OPENAI_MAX_TOKENS', 1000)
        self.temperature = getattr(settings, 'OPENAI_TEMPERATURE', 0.7)
        self.timeout = getattr(settings, 'OPENAI_TIMEOUT', 30)
        self.cache_timeout = CACHE_TIMEOUTS.get('openai', 3600)
        
        # Initialize OpenAI client if available
        if OPENAI_AVAILABLE and self.api_key:
            self.client = openai.OpenAI(api_key=self.api_key)
            self.async_client = AsyncOpenAI(api_key=self.api_key)
        else:
            self.client = None
            self.async_client = None
    
    def is_configured(self) -> bool:
        """Check if OpenAI is properly configured"""
        return OPENAI_AVAILABLE and self.api_key is not None


class OpenAIService:
    """Service for OpenAI operations"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.config = OpenAIConfig()
        self.cache_timeout = self.config.cache_timeout
    
    def get_cache_key(self, operation: str, identifier: str = '') -> str:
        """Generate cache key for OpenAI operations"""
        key_parts = ['openai', self.tenant_id, operation]
        if identifier:
            key_parts.append(identifier)
        return '_'.join(key_parts)
    
    def get_from_cache(self, cache_key: str) -> Any:
        """Get data from cache"""
        return cache.get(cache_key)
    
    def set_cache(self, cache_key: str, data: Any, timeout: int = None):
        """Set data in cache"""
        timeout = timeout or self.cache_timeout
        cache.set(cache_key, data, timeout)
    
    async def generate_offer_description(self, offer_data: Dict[str, Any]) -> str:
        """Generate AI-powered offer description"""
        if not self.config.is_configured():
            return self._get_fallback_description(offer_data)
        
        cache_key = self.get_cache_key('offer_description', str(hash(str(offer_data))))
        cached_description = self.get_from_cache(cache_key)
        
        if cached_description:
            return cached_description
        
        try:
            prompt = self._build_offer_description_prompt(offer_data)
            
            response = await self.config.async_client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "You are an expert copywriter specializing in mobile app and online offer descriptions."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            
            description = response.choices[0].message.content.strip()
            
            # Cache the result
            self.set_cache(cache_key, description)
            
            return description
            
        except Exception as e:
            logger.error(f"Error generating offer description: {str(e)}")
            return self._get_fallback_description(offer_data)
    
    def _build_offer_description_prompt(self, offer_data: Dict[str, Any]) -> str:
        """Build prompt for offer description generation"""
        title = offer_data.get('title', 'Unknown Offer')
        reward_amount = offer_data.get('reward_amount', 0)
        difficulty = offer_data.get('difficulty', 'easy')
        estimated_time = offer_data.get('estimated_time', 5)
        requirements = offer_data.get('requirements', '')
        
        prompt = f"""
        Generate an engaging and compelling description for the following mobile offer:
        
        Title: {title}
        Reward: ${reward_amount}
        Difficulty: {difficulty}
        Estimated Time: {estimated_time} minutes
        Requirements: {requirements}
        
        The description should:
        1. Be 2-3 sentences long
        2. Highlight the reward value
        3. Mention the difficulty level appropriately
        4. Be engaging and persuasive
        5. Be suitable for mobile users
        6. Avoid making false claims
        
        Please write the description in a professional yet engaging tone.
        """
        
        return prompt.strip()
    
    def _get_fallback_description(self, offer_data: Dict[str, Any]) -> str:
        """Get fallback description when OpenAI is unavailable"""
        title = offer_data.get('title', 'Unknown Offer')
        reward_amount = offer_data.get('reward_amount', 0)
        difficulty = offer_data.get('difficulty', 'easy')
        
        return f"Complete this {difficulty} offer and earn ${reward_amount}. {title} is waiting for you!"
    
    async def analyze_fraud_patterns(self, conversion_data: Dict[str, Any], 
                                  historical_data: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze fraud patterns using AI"""
        if not self.config.is_configured():
            return self._get_fallback_fraud_analysis(conversion_data)
        
        cache_key = self.get_cache_key('fraud_analysis', str(hash(str(conversion_data))))
        cached_analysis = self.get_from_cache(cache_key)
        
        if cached_analysis:
            return cached_analysis
        
        try:
            prompt = self._build_fraud_analysis_prompt(conversion_data, historical_data)
            
            response = await self.config.async_client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "You are an expert fraud detection analyst specializing in online offer conversions."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            
            analysis_text = response.choices[0].message.content.strip()
            
            # Parse AI response
            analysis = self._parse_fraud_analysis(analysis_text)
            
            # Cache the result
            self.set_cache(cache_key, analysis, timeout=1800)  # 30 minutes
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing fraud patterns: {str(e)}")
            return self._get_fallback_fraud_analysis(conversion_data)
    
    def _build_fraud_analysis_prompt(self, conversion_data: Dict[str, Any], 
                                   historical_data: List[Dict[str, Any]] = None) -> str:
        """Build prompt for fraud analysis"""
        user_id = conversion_data.get('user_id', 'Unknown')
        offer_title = conversion_data.get('offer_title', 'Unknown Offer')
        payout = conversion_data.get('payout', 0)
        completion_time = conversion_data.get('completion_time_seconds', 0)
        ip_address = conversion_data.get('ip_address', 'Unknown')
        user_agent = conversion_data.get('user_agent', 'Unknown')
        
        historical_text = ""
        if historical_data:
            historical_text = f"\nUser Historical Data:\n{json.dumps(historical_data, indent=2)}"
        
        prompt = f"""
        Analyze the following conversion for potential fraud indicators:
        
        User ID: {user_id}
        Offer: {offer_title}
        Payout: ${payout}
        Completion Time: {completion_time} seconds
        IP Address: {ip_address}
        User Agent: {user_agent}
        {historical_text}
        
        Please analyze and provide:
        1. Risk level (low, medium, high, critical)
        2. Fraud score (0-100)
        3. Key indicators (list specific concerns)
        4. Confidence level (low, medium, high)
        5. Recommendation (approve, review, reject)
        
        Format your response as JSON with the following structure:
        {{
            "risk_level": "string",
            "fraud_score": number,
            "indicators": ["string"],
            "confidence": "string",
            "recommendation": "string",
            "reasoning": "string"
        }}
        """
        
        return prompt.strip()
    
    def _parse_fraud_analysis(self, analysis_text: str) -> Dict[str, Any]:
        """Parse fraud analysis from AI response"""
        try:
            # Try to parse as JSON
            analysis = json.loads(analysis_text)
            
            # Validate required fields
            required_fields = ['risk_level', 'fraud_score', 'indicators', 'confidence', 'recommendation']
            for field in required_fields:
                if field not in analysis:
                    analysis[field] = None
            
            return analysis
            
        except json.JSONDecodeError:
            # Fallback parsing if JSON parsing fails
            return {
                'risk_level': 'medium',
                'fraud_score': 50,
                'indicators': ['Unable to parse AI response'],
                'confidence': 'low',
                'recommendation': 'review',
                'reasoning': 'AI response could not be parsed'
            }
    
    def _get_fallback_fraud_analysis(self, conversion_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get fallback fraud analysis when OpenAI is unavailable"""
        completion_time = conversion_data.get('completion_time_seconds', 0)
        payout = conversion_data.get('payout', 0)
        
        fraud_score = 0
        indicators = []
        
        # Basic rule-based analysis
        if completion_time < 30:
            fraud_score += 30
            indicators.append('Suspiciously fast completion')
        
        if payout > 50:
            fraud_score += 20
            indicators.append('High payout amount')
        
        risk_level = 'low'
        if fraud_score >= 70:
            risk_level = 'high'
        elif fraud_score >= 40:
            risk_level = 'medium'
        
        return {
            'risk_level': risk_level,
            'fraud_score': min(fraud_score, 100),
            'indicators': indicators,
            'confidence': 'medium',
            'recommendation': 'review' if fraud_score > 30 else 'approve',
            'reasoning': 'Rule-based analysis (OpenAI unavailable)'
        }
    
    async def generate_personalized_recommendations(self, user_id: int, 
                                                limit: int = 10) -> List[Dict[str, Any]]:
        """Generate personalized offer recommendations using AI"""
        if not self.config.is_configured():
            return self._get_fallback_recommendations(user_id, limit)
        
        cache_key = self.get_cache_key('recommendations', f"{user_id}_{limit}")
        cached_recommendations = self.get_from_cache(cache_key)
        
        if cached_recommendations:
            return cached_recommendations
        
        try:
            # Get user data
            user_data = await self._get_user_profile_data(user_id)
            available_offers = await self._get_available_offers()
            
            if not available_offers:
                return []
            
            prompt = self._build_recommendation_prompt(user_data, available_offers, limit)
            
            response = await self.config.async_client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "You are an expert recommendation engine for mobile offers and surveys."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            
            recommendations_text = response.choices[0].message.content.strip()
            
            # Parse recommendations
            recommendations = self._parse_recommendations(recommendations_text, available_offers)
            
            # Cache the result
            self.set_cache(cache_key, recommendations, timeout=1800)  # 30 minutes
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return self._get_fallback_recommendations(user_id, limit)
    
    async def _get_user_profile_data(self, user_id: int) -> Dict[str, Any]:
        """Get user profile data for recommendations"""
        try:
            user = User.objects.get(id=user_id)
            
            # Get user's offer history
            user_offers = UserOfferEngagement.objects.filter(
                user=user,
                tenant_id=self.tenant_id
            ).select_related('offer').order_by('-created_at')[:20]
            
            # Analyze preferences
            categories = {}
            difficulties = {}
            avg_payout = 0
            payout_count = 0
            
            for engagement in user_offers:
                if engagement.offer.category:
                    category = engagement.offer.category.name
                    categories[category] = categories.get(category, 0) + 1
                
                difficulty = engagement.offer.difficulty
                difficulties[difficulty] = difficulties.get(difficulty, 0) + 1
                
                if engagement.offer.reward_amount:
                    avg_payout += float(engagement.offer.reward_amount)
                    payout_count += 1
            
            if payout_count > 0:
                avg_payout /= payout_count
            
            return {
                'user_id': user_id,
                'username': user.username,
                'preferred_categories': sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5],
                'preferred_difficulties': sorted(difficulties.items(), key=lambda x: x[1], reverse=True)[:3],
                'average_payout': avg_payout,
                'total_engagements': user_offers.count()
            }
            
        except User.DoesNotExist:
            return {'user_id': user_id}
    
    async def _get_available_offers(self) -> List[Dict[str, Any]]:
        """Get available offers for recommendations"""
        offers = Offer.objects.filter(
            tenant_id=self.tenant_id,
            status=OfferStatus.ACTIVE
        ).select_related('category', 'ad_network')[:50]
        
        return [
            {
                'id': offer.id,
                'title': offer.title,
                'reward_amount': float(offer.reward_amount),
                'category': offer.category.name if offer.category else 'Unknown',
                'difficulty': offer.difficulty,
                'estimated_time': offer.estimated_time,
                'network': offer.ad_network.name
            }
            for offer in offers
        ]
    
    def _build_recommendation_prompt(self, user_data: Dict[str, Any], 
                                   available_offers: List[Dict[str, Any]], 
                                   limit: int) -> str:
        """Build prompt for recommendations"""
        user_text = json.dumps(user_data, indent=2)
        offers_text = json.dumps(available_offers, indent=2)
        
        prompt = f"""
        Based on the user profile and available offers, recommend the top {limit} offers for this user:
        
        User Profile:
        {user_text}
        
        Available Offers:
        {offers_text}
        
        Please analyze the user's preferences and history to recommend the most suitable offers.
        Consider:
        1. User's preferred categories
        2. User's preferred difficulty levels
        3. User's average payout preferences
        4. Offer relevance and engagement potential
        5. Variety in recommendations
        
        Format your response as a JSON array of offer IDs, sorted by relevance:
        [offer_id_1, offer_id_2, offer_id_3, ...]
        
        Only include offer IDs from the available offers list.
        """
        
        return prompt.strip()
    
    def _parse_recommendations(self, recommendations_text: str, 
                              available_offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse recommendations from AI response"""
        try:
            # Try to parse as JSON array
            recommended_ids = json.loads(recommendations_text)
            
            if not isinstance(recommended_ids, list):
                raise ValueError("Expected JSON array")
            
            # Map IDs back to offers
            offers_by_id = {offer['id']: offer for offer in available_offers}
            recommendations = []
            
            for offer_id in recommended_ids[:10]:  # Limit to 10
                if offer_id in offers_by_id:
                    recommendations.append(offers_by_id[offer_id])
            
            return recommendations
            
        except (json.JSONDecodeError, ValueError, KeyError):
            # Fallback: return top offers by reward amount
            return sorted(available_offers, key=lambda x: x['reward_amount'], reverse=True)[:10]
    
    def _get_fallback_recommendations(self, user_id: int, limit: int) -> List[Dict[str, Any]]:
        """Get fallback recommendations when OpenAI is unavailable"""
        # Simple fallback: return top offers by reward amount
        offers = Offer.objects.filter(
            tenant_id=self.tenant_id,
            status=OfferStatus.ACTIVE
        ).select_related('category', 'ad_network').order_by('-reward_amount')[:limit]
        
        return [
            {
                'id': offer.id,
                'title': offer.title,
                'reward_amount': float(offer.reward_amount),
                'category': offer.category.name if offer.category else 'Unknown',
                'difficulty': offer.difficulty,
                'estimated_time': offer.estimated_time,
                'network': offer.ad_network.name,
                'recommendation_score': 0.5  # Default score
            }
            for offer in offers
        ]
    
    async def generate_offer_insights(self, offer_id: int) -> Dict[str, Any]:
        """Generate AI-powered insights for an offer"""
        if not self.config.is_configured():
            return self._get_fallback_insights(offer_id)
        
        cache_key = self.get_cache_key('offer_insights', str(offer_id))
        cached_insights = self.get_from_cache(cache_key)
        
        if cached_insights:
            return cached_insights
        
        try:
            # Get offer data
            offer = Offer.objects.get(
                id=offer_id,
                tenant_id=self.tenant_id
            )
            
            # Get performance data
            performance_data = await self._get_offer_performance_data(offer_id)
            
            prompt = self._build_insights_prompt(offer, performance_data)
            
            response = await self.config.async_client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "You are an expert mobile offer analyst providing insights and recommendations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            
            insights_text = response.choices[0].message.content.strip()
            
            # Parse insights
            insights = self._parse_insights(insights_text)
            
            # Cache the result
            self.set_cache(cache_key, insights, timeout=3600)  # 1 hour
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating offer insights: {str(e)}")
            return self._get_fallback_insights(offer_id)
    
    async def _get_offer_performance_data(self, offer_id: int) -> Dict[str, Any]:
        """Get offer performance data"""
        try:
            offer = Offer.objects.get(id=offer_id, tenant_id=self.tenant_id)
            
            # Calculate performance metrics
            clicks = OfferClick.objects.filter(offer=offer).count()
            engagements = UserOfferEngagement.objects.filter(offer=offer).count()
            conversions = OfferConversion.objects.filter(engagement__offer=offer).count()
            approved_conversions = OfferConversion.objects.filter(
                engagement__offer=offer,
                conversion_status=ConversionStatus.APPROVED
            ).count()
            
            conversion_rate = (conversions / engagements * 100) if engagements > 0 else 0
            approval_rate = (approved_conversions / conversions * 100) if conversions > 0 else 0
            
            return {
                'clicks': clicks,
                'engagements': engagements,
                'conversions': conversions,
                'approved_conversions': approved_conversions,
                'conversion_rate': conversion_rate,
                'approval_rate': approval_rate
            }
            
        except Offer.DoesNotExist:
            return {}
    
    def _build_insights_prompt(self, offer, performance_data: Dict[str, Any]) -> str:
        """Build prompt for offer insights"""
        offer_text = f"""
        Title: {offer.title}
        Description: {offer.description}
        Reward: ${offer.reward_amount}
        Difficulty: {offer.difficulty}
        Estimated Time: {offer.estimated_time} minutes
        Category: {offer.category.name if offer.category else 'Unknown'}
        Network: {offer.ad_network.name}
        """
        
        performance_text = f"""
        Performance Data:
        {json.dumps(performance_data, indent=2)}
        """
        
        prompt = f"""
        Analyze this mobile offer and provide actionable insights:
        
        {offer_text}
        
        {performance_text}
        
        Please provide insights on:
        1. Performance analysis (good, average, poor)
        2. Key strengths and weaknesses
        3. Optimization recommendations
        4. Target audience fit
        5. Competitive positioning
        6. Improvement suggestions
        
        Format your response as JSON:
        {{
            "performance_rating": "string",
            "strengths": ["string"],
            "weaknesses": ["string"],
            "recommendations": ["string"],
            "target_audience": "string",
            "competitive_position": "string",
            "overall_score": number
        }}
        """
        
        return prompt.strip()
    
    def _parse_insights(self, insights_text: str) -> Dict[str, Any]:
        """Parse insights from AI response"""
        try:
            insights = json.loads(insights_text)
            
            # Validate required fields
            required_fields = ['performance_rating', 'strengths', 'weaknesses', 'recommendations']
            for field in required_fields:
                if field not in insights:
                    insights[field] = []
            
            return insights
            
        except json.JSONDecodeError:
            return {
                'performance_rating': 'unknown',
                'strengths': ['Unable to parse AI response'],
                'weaknesses': ['Unable to parse AI response'],
                'recommendations': ['Manual analysis required'],
                'target_audience': 'Unknown',
                'competitive_position': 'Unknown',
                'overall_score': 50
            }
    
    def _get_fallback_insights(self, offer_id: int) -> Dict[str, Any]:
        """Get fallback insights when OpenAI is unavailable"""
        try:
            offer = Offer.objects.get(id=offer_id, tenant_id=self.tenant_id)
            
            # Basic performance analysis
            conversions = OfferConversion.objects.filter(
                engagement__offer=offer
            ).count()
            
            if conversions > 50:
                performance_rating = 'excellent'
                overall_score = 85
            elif conversions > 20:
                performance_rating = 'good'
                overall_score = 70
            elif conversions > 5:
                performance_rating = 'average'
                overall_score = 50
            else:
                performance_rating = 'poor'
                overall_score = 25
            
            return {
                'performance_rating': performance_rating,
                'strengths': ['Available on platform'],
                'weaknesses': ['Limited data available'],
                'recommendations': ['Increase visibility', 'Optimize description'],
                'target_audience': 'General mobile users',
                'competitive_position': 'Unknown',
                'overall_score': overall_score
            }
            
        except Offer.DoesNotExist:
            return {
                'performance_rating': 'unknown',
                'strengths': [],
                'weaknesses': ['Offer not found'],
                'recommendations': ['Verify offer exists'],
                'target_audience': 'Unknown',
                'competitive_position': 'Unknown',
                'overall_score': 0
            }


# Global service instance
openai_service = OpenAIService()


# Export all classes
__all__ = [
    # Configuration
    'OpenAIConfig',
    
    # Services
    'OpenAIService',
    
    # Global instance
    'openai_service'
]
