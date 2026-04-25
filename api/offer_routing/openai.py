"""
OpenAI Integration for Offer Routing System

This module provides OpenAI API integration for the offer routing system,
including AI-powered content generation, analysis, and optimization.
"""

import logging
import json
import time
from typing import Dict, Any, List, Optional, Union
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model
import openai
from openai import OpenAI

logger = logging.getLogger(__name__)
User = get_user_model()


class OpenAIClient:
    """
    OpenAI API client wrapper for offer routing system.
    """
    
    def __init__(self, api_key: str = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
        self.model = model
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI client."""
        try:
            if self.api_key:
                self.client = OpenAI(api_key=self.api_key)
                logger.info("OpenAI client initialized successfully")
            else:
                logger.warning("OpenAI API key not provided")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if OpenAI service is available."""
        try:
            if not self.client:
                return False
            
            # Test with a simple request
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return True
        except Exception as e:
            logger.error(f"OpenAI service unavailable: {str(e)}")
            return False
    
    def generate_text(self, prompt: str, max_tokens: int = 100, temperature: float = 0.7) -> Optional[str]:
        """Generate text using OpenAI."""
        try:
            if not self.client:
                return None
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating text: {str(e)}")
            return None
    
    def analyze_text(self, text: str, analysis_type: str = "sentiment") -> Optional[Dict[str, Any]]:
        """Analyze text using OpenAI."""
        try:
            if not self.client:
                return None
            
            prompts = {
                "sentiment": f"Analyze the sentiment of this text and return JSON with 'sentiment' (positive/negative/neutral) and 'confidence' (0-1): {text}",
                "category": f"Categorize this text and return JSON with 'category' and 'confidence': {text}",
                "keywords": f"Extract keywords from this text and return JSON with 'keywords' array: {text}",
                "summary": f"Summarize this text and return JSON with 'summary' and 'key_points': {text}"
            }
            
            prompt = prompts.get(analysis_type, prompts["sentiment"])
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Try to parse as JSON
            try:
                return json.loads(result_text)
            except json.JSONDecodeError:
                return {"raw_response": result_text}
                
        except Exception as e:
            logger.error(f"Error analyzing text: {str(e)}")
            return None


class OfferContentGenerator:
    """
    AI-powered content generator for offers.
    """
    
    def __init__(self, openai_client: OpenAIClient = None):
        self.client = openai_client or OpenAIClient()
        self.cache_timeout = 3600  # 1 hour
    
    def generate_offer_description(self, offer_name: str, offer_type: str, target_audience: str) -> Optional[str]:
        """Generate compelling offer description."""
        cache_key = f"offer_desc:{hash(offer_name + offer_type + target_audience)}"
        
        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        prompt = f"""
        Generate a compelling description for an offer with the following details:
        - Offer Name: {offer_name}
        - Offer Type: {offer_type}
        - Target Audience: {target_audience}
        
        The description should be:
        - Engaging and persuasive
        - 100-150 words
        - Highlight key benefits
        - Include a call to action
        """
        
        description = self.client.generate_text(prompt, max_tokens=200, temperature=0.8)
        
        if description:
            cache.set(cache_key, description, self.cache_timeout)
        
        return description
    
    def generate_ad_copy(self, offer_name: str, product_category: str, benefits: List[str]) -> Optional[str]:
        """Generate ad copy for an offer."""
        cache_key = f"ad_copy:{hash(offer_name + product_category + str(benefits))}"
        
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        benefits_text = ", ".join(benefits)
        
        prompt = f"""
        Create compelling ad copy for:
        - Product: {offer_name}
        - Category: {product_category}
        - Key Benefits: {benefits_text}
        
        Requirements:
        - Attention-grabbing headline
        - 2-3 sentences body copy
        - Strong call to action
        - Under 100 words total
        """
        
        ad_copy = self.client.generate_text(prompt, max_tokens=150, temperature=0.9)
        
        if ad_copy:
            cache.set(cache_key, ad_copy, self.cache_timeout)
        
        return ad_copy
    
    def generate_email_subject(self, offer_name: str, discount_percentage: int = None) -> Optional[str]:
        """Generate email subject line."""
        cache_key = f"email_subject:{hash(offer_name + str(discount_percentage))}"
        
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        discount_text = f" with {discount_percentage}% discount" if discount_percentage else ""
        
        prompt = f"""
        Generate an email subject line for:
        - Offer: {offer_name}{discount_text}
        
        Requirements:
        - Under 50 characters
        - Create urgency or curiosity
        - Include emoji if appropriate
        - Avoid spam trigger words
        """
        
        subject = self.client.generate_text(prompt, max_tokens=50, temperature=0.8)
        
        if subject:
            cache.set(cache_key, subject, self.cache_timeout)
        
        return subject


class OfferAnalyzer:
    """
    AI-powered offer analysis and optimization.
    """
    
    def __init__(self, openai_client: OpenAIClient = None):
        self.client = openai_client or OpenAIClient()
        self.cache_timeout = 7200  # 2 hours
    
    def analyze_offer_performance(self, offer_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze offer performance and provide insights."""
        cache_key = f"offer_analysis:{hash(str(offer_data))}"
        
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Prepare data for analysis
        metrics_text = f"""
        Click Rate: {offer_data.get('click_rate', 0)}%
        Conversion Rate: {offer_data.get('conversion_rate', 0)}%
        Revenue: ${offer_data.get('revenue', 0)}
        Impressions: {offer_data.get('impressions', 0)}
        """
        
        prompt = f"""
        Analyze this offer performance data and provide actionable insights:
        {metrics_text}
        
        Return JSON with:
        - performance_rating (excellent/good/poor)
        - key_insights (array of strings)
        - optimization_suggestions (array of strings)
        - potential_issues (array of strings)
        """
        
        analysis = self.client.analyze_text(metrics_text, "sentiment")
        
        if analysis:
            cache.set(cache_key, analysis, self.cache_timeout)
        
        return analysis
    
    def predict_offer_success(self, offer_features: Dict[str, Any]) -> Optional[float]:
        """Predict the success probability of an offer."""
        cache_key = f"offer_prediction:{hash(str(offer_features))}"
        
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        features_text = json.dumps(offer_features, indent=2)
        
        prompt = f"""
        Based on these offer features, predict the success probability (0-1):
        {features_text}
        
        Consider:
        - Market demand
        - Price competitiveness
        - Target audience fit
        - Seasonal factors
        
        Return only a number between 0 and 1.
        """
        
        result = self.client.generate_text(prompt, max_tokens=10, temperature=0.3)
        
        if result:
            try:
                probability = float(result.strip())
                cache.set(cache_key, probability, self.cache_timeout)
                return probability
            except ValueError:
                pass
        
        return None
    
    def generate_audience_insights(self, audience_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate insights about target audience."""
        cache_key = f"audience_insights:{hash(str(audience_data))}"
        
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        audience_text = json.dumps(audience_data, indent=2)
        
        prompt = f"""
        Analyze this audience data and provide insights:
        {audience_text}
        
        Return JSON with:
        - audience_profile (description)
        - key_segments (array of strings)
        - engagement_prediction (high/medium/low)
        - recommended_channels (array of strings)
        - content_preferences (array of strings)
        """
        
        insights = self.client.analyze_text(audience_text, "category")
        
        if insights:
            cache.set(cache_key, insights, self.cache_timeout)
        
        return insights


class RoutingOptimizer:
    """
    AI-powered routing optimization.
    """
    
    def __init__(self, openai_client: OpenAIClient = None):
        self.client = openai_client or OpenAIClient()
        self.cache_timeout = 1800  # 30 minutes
    
    def optimize_routing_rules(self, routing_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Optimize routing rules using AI."""
        cache_key = f"routing_optimization:{hash(str(routing_data))}"
        
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        routing_text = json.dumps(routing_data, indent=2)
        
        prompt = f"""
        Analyze this routing data and suggest optimizations:
        {routing_text}
        
        Return JSON with:
        - current_performance_score (0-1)
        - optimization_opportunities (array of strings)
        - suggested_rule_changes (array of objects)
        - expected_improvement (percentage)
        - implementation_priority (high/medium/low)
        """
        
        optimization = self.client.analyze_text(routing_text, "category")
        
        if optimization:
            cache.set(cache_key, optimization, self.cache_timeout)
        
        return optimization
    
    def predict_routing_outcome(self, context: Dict[str, Any], route_options: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Predict the best routing outcome."""
        cache_key = f"routing_prediction:{hash(str(context) + str(route_options))}"
        
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        context_text = json.dumps(context, indent=2)
        options_text = json.dumps(route_options, indent=2)
        
        prompt = f"""
        Given this user context and route options, predict the best outcome:
        
        Context:
        {context_text}
        
        Route Options:
        {options_text}
        
        Return JSON with:
        - recommended_route_id
        - confidence_score (0-1)
        - expected_conversion_rate (0-1)
        - reasoning (string)
        - alternative_recommendations (array of route_ids)
        """
        
        prediction = self.client.analyze_text(context_text + options_text, "category")
        
        if prediction:
            cache.set(cache_key, prediction, self.cache_timeout)
        
        return prediction


class OpenAIService:
    """
    Main service class for OpenAI integration.
    """
    
    def __init__(self):
        self.client = OpenAIClient()
        self.content_generator = OfferContentGenerator(self.client)
        self.analyzer = OfferAnalyzer(self.client)
        self.optimizer = RoutingOptimizer(self.client)
    
    def is_service_available(self) -> bool:
        """Check if OpenAI service is available."""
        return self.client.is_available()
    
    def generate_offer_content(self, offer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate all content for an offer."""
        results = {}
        
        # Generate description
        if 'name' in offer_data and 'type' in offer_data:
            results['description'] = self.content_generator.generate_offer_description(
                offer_data['name'],
                offer_data['type'],
                offer_data.get('target_audience', 'general')
            )
        
        # Generate ad copy
        if 'name' in offer_data and 'category' in offer_data:
            results['ad_copy'] = self.content_generator.generate_ad_copy(
                offer_data['name'],
                offer_data['category'],
                offer_data.get('benefits', [])
            )
        
        # Generate email subject
        if 'name' in offer_data:
            results['email_subject'] = self.content_generator.generate_email_subject(
                offer_data['name'],
                offer_data.get('discount_percentage')
            )
        
        return results
    
    def analyze_and_optimize_offer(self, offer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze and optimize an offer."""
        results = {}
        
        # Analyze performance
        results['performance_analysis'] = self.analyzer.analyze_offer_performance(offer_data)
        
        # Predict success
        results['success_prediction'] = self.analyzer.predict_offer_success(offer_data)
        
        # Generate audience insights
        if 'audience_data' in offer_data:
            results['audience_insights'] = self.analyzer.generate_audience_insights(offer_data['audience_data'])
        
        return results
    
    def optimize_routing_strategy(self, routing_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize routing strategy."""
        results = {}
        
        # Optimize routing rules
        results['rule_optimization'] = self.optimizer.optimize_routing_rules(routing_data)
        
        # Predict routing outcome
        if 'context' in routing_data and 'route_options' in routing_data:
            results['outcome_prediction'] = self.optimizer.predict_routing_outcome(
                routing_data['context'],
                routing_data['route_options']
            )
        
        return results
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get OpenAI service status."""
        return {
            'available': self.is_service_available(),
            'model': self.client.model,
            'cache_enabled': True,
            'last_check': timezone.now()
        }


# Global service instance
openai_service = OpenAIService()


# Utility functions
def generate_offer_content(offer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate content for an offer."""
    return openai_service.generate_offer_content(offer_data)


def analyze_offer_performance(offer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze offer performance."""
    return openai_service.analyze_and_optimize_offer(offer_data)


def optimize_routing(routing_data: Dict[str, Any]) -> Dict[str, Any]:
    """Optimize routing strategy."""
    return openai_service.optimize_routing_strategy(routing_data)


def is_openai_available() -> bool:
    """Check if OpenAI service is available."""
    return openai_service.is_service_available()


# Export the main classes and functions
__all__ = [
    'OpenAIClient',
    'OfferContentGenerator',
    'OfferAnalyzer',
    'RoutingOptimizer',
    'OpenAIService',
    'openai_service',
    'generate_offer_content',
    'analyze_offer_performance',
    'optimize_routing',
    'is_openai_available',
]
