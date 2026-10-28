"""
openai.py – OpenAI integration for postback module.

Provides AI-powered features for postback processing including:
- Content analysis and classification
- Fraud detection using AI models
- Automated response generation
- Sentiment analysis for postback data
- Pattern recognition and anomaly detection
"""
import logging
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta

import openai
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth import get_user_model

from .exceptions import PostbackException
from .models import PostbackLog, PostbackInsight, NetworkPostbackConfig

logger = logging.getLogger(__name__)
User = get_user_model()


class OpenAIClient:
    """
    OpenAI API client for postback module AI features.
    
    Provides unified interface for various OpenAI models and capabilities
    including text analysis, classification, and content generation.
    """
    
    def __init__(self):
        """Initialize OpenAI client with configuration."""
        self.api_key = getattr(settings, 'OPENAI_API_KEY', None)
        self.model = getattr(settings, 'POSTBACK_OPENAI_MODEL', 'gpt-3.5-turbo')
        self.max_tokens = getattr(settings, 'POSTBACK_OPENAI_MAX_TOKENS', 1000)
        self.temperature = getattr(settings, 'POSTBACK_OPENAI_TEMPERATURE', 0.3)
        self.timeout = getattr(settings, 'POSTBACK_OPENAI_TIMEOUT', 30)
        
        if not self.api_key:
            logger.warning("OpenAI API key not configured")
            self.client = None
        else:
            self.client = openai.OpenAI(api_key=self.api_key)
    
    def is_configured(self) -> bool:
        """Check if OpenAI client is properly configured."""
        return self.client is not None
    
    def analyze_postback_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze postback content for patterns, anomalies, and insights.
        
        Args:
            content: Postback payload data
            
        Returns:
            Analysis results with classification and insights
        """
        if not self.is_configured():
            raise PostbackException("OpenAI client not configured")
        
        try:
            # Prepare content for analysis
            content_text = self._prepare_content_for_analysis(content)
            
            # Create analysis prompt
            prompt = self._create_analysis_prompt(content_text)
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert postback data analyst. Analyze the provided postback data for patterns, anomalies, potential fraud indicators, and insights. Provide structured JSON output."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            # Parse response
            analysis_text = response.choices[0].message.content
            analysis_result = self._parse_analysis_response(analysis_text)
            
            # Add metadata
            analysis_result.update({
                'analyzed_at': timezone.now().isoformat(),
                'model_used': self.model,
                'content_hash': self._generate_content_hash(content)
            })
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing postback content: {str(e)}")
            raise PostbackException(f"Content analysis failed: {str(e)}")
    
    def detect_fraud_indicators(self, postback_data: Dict[str, Any], user_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Detect potential fraud indicators in postback data.
        
        Args:
            postback_data: Postback payload and metadata
            user_context: Additional user context for analysis
            
        Returns:
            Fraud detection results with risk scores and indicators
        """
        if not self.is_configured():
            raise PostbackException("OpenAI client not configured")
        
        try:
            # Prepare fraud detection prompt
            prompt = self._create_fraud_detection_prompt(postback_data, user_context)
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a fraud detection specialist. Analyze the provided postback data for potential fraud indicators including IP patterns, user behavior anomalies, suspicious payloads, and timing patterns. Provide risk assessment with confidence scores."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=0.1  # Lower temperature for more consistent fraud analysis
            )
            
            # Parse response
            fraud_text = response.choices[0].message.content
            fraud_result = self._parse_fraud_response(fraud_text)
            
            # Add metadata
            fraud_result.update({
                'analyzed_at': timezone.now().isoformat(),
                'model_used': self.model,
                'risk_level': self._calculate_risk_level(fraud_result.get('risk_score', 0))
            })
            
            return fraud_result
            
        except Exception as e:
            logger.error(f"Error in fraud detection: {str(e)}")
            raise PostbackException(f"Fraud detection failed: {str(e)}")
    
    def generate_response_template(self, postback_data: Dict[str, Any], response_type: str = 'success') -> str:
        """
        Generate response template for postback processing.
        
        Args:
            postback_data: Postback data context
            response_type: Type of response to generate
            
        Returns:
            Generated response template
        """
        if not self.is_configured():
            raise PostbackException("OpenAI client not configured")
        
        try:
            # Create response generation prompt
            prompt = self._create_response_generation_prompt(postback_data, response_type)
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a postback response generator. Create a {response_type} response template for the given postback data. The response should be clear, professional, and include relevant details."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating response template: {str(e)}")
            raise PostbackException(f"Response generation failed: {str(e)}")
    
    def analyze_sentiment(self, text_content: str) -> Dict[str, Any]:
        """
        Analyze sentiment of text content from postback data.
        
        Args:
            text_content: Text to analyze for sentiment
            
        Returns:
            Sentiment analysis results
        """
        if not self.is_configured():
            raise PostbackException("OpenAI client not configured")
        
        try:
            # Create sentiment analysis prompt
            prompt = f"Analyze the sentiment of the following text and provide a detailed analysis including overall sentiment (positive/negative/neutral), confidence score, and emotional indicators:\n\n{text_content}"
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a sentiment analysis expert. Provide detailed sentiment analysis with confidence scores and emotional indicators in JSON format."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=300,
                temperature=0.1
            )
            
            # Parse response
            sentiment_text = response.choices[0].message.content
            sentiment_result = self._parse_sentiment_response(sentiment_text)
            
            # Add metadata
            sentiment_result.update({
                'analyzed_at': timezone.now().isoformat(),
                'model_used': self.model,
                'text_length': len(text_content)
            })
            
            return sentiment_result
            
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {str(e)}")
            raise PostbackException(f"Sentiment analysis failed: {str(e)}")
    
    def detect_anomalies(self, historical_data: List[Dict[str, Any]], current_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect anomalies in current postback data compared to historical patterns.
        
        Args:
            historical_data: Historical postback data for comparison
            current_data: Current postback data to analyze
            
        Returns:
            Anomaly detection results
        """
        if not self.is_configured():
            raise PostbackException("OpenAI client not configured")
        
        try:
            # Create anomaly detection prompt
            prompt = self._create_anomaly_detection_prompt(historical_data, current_data)
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an anomaly detection specialist. Compare current postback data with historical patterns and identify any anomalies, outliers, or unusual patterns. Provide detailed analysis with confidence scores."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=0.2
            )
            
            # Parse response
            anomaly_text = response.choices[0].message.content
            anomaly_result = self._parse_anomaly_response(anomaly_text)
            
            # Add metadata
            anomaly_result.update({
                'analyzed_at': timezone.now().isoformat(),
                'model_used': self.model,
                'historical_data_points': len(historical_data)
            })
            
            return anomaly_result
            
        except Exception as e:
            logger.error(f"Error in anomaly detection: {str(e)}")
            raise PostbackException(f"Anomaly detection failed: {str(e)}")
    
    # Helper methods
    def _prepare_content_for_analysis(self, content: Dict[str, Any]) -> str:
        """Prepare postback content for AI analysis."""
        # Convert content to readable format
        content_str = json.dumps(content, indent=2, default=str)
        return content_str
    
    def _create_analysis_prompt(self, content_text: str) -> str:
        """Create analysis prompt for OpenAI."""
        return f"""Analyze the following postback data and provide insights:

{content_text}

Please provide analysis in the following JSON format:
{{
    "classification": "type_of_postback",
    "confidence_score": 0.95,
    "key_patterns": ["pattern1", "pattern2"],
    "anomalies": ["anomaly1", "anomaly2"],
    "insights": ["insight1", "insight2"],
    "recommendations": ["recommendation1", "recommendation2"]
}}"""
    
    def _create_fraud_detection_prompt(self, postback_data: Dict[str, Any], user_context: Dict[str, Any] = None) -> str:
        """Create fraud detection prompt."""
        postback_str = json.dumps(postback_data, indent=2, default=str)
        user_str = json.dumps(user_context or {}, indent=2, default=str)
        
        return f"""Analyze the following postback data for fraud indicators:

Postback Data:
{postback_str}

User Context:
{user_str}

Please provide fraud analysis in the following JSON format:
{{
    "risk_score": 0.75,
    "confidence": 0.85,
    "indicators": ["indicator1", "indicator2"],
    "risk_factors": ["factor1", "factor2"],
    "recommendation": "actionable_recommendation",
    "explanation": "detailed_explanation"
}}"""
    
    def _create_response_generation_prompt(self, postback_data: Dict[str, Any], response_type: str) -> str:
        """Create response generation prompt."""
        postback_str = json.dumps(postback_data, indent=2, default=str)
        
        return f"""Generate a {response_type} response template for this postback data:

{postback_str}

The response should be professional, clear, and include relevant details from the postback data."""
    
    def _create_anomaly_detection_prompt(self, historical_data: List[Dict[str, Any]], current_data: Dict[str, Any]) -> str:
        """Create anomaly detection prompt."""
        historical_str = json.dumps(historical_data[-5:], indent=2, default=str)  # Last 5 entries
        current_str = json.dumps(current_data, indent=2, default=str)
        
        return f"""Detect anomalies by comparing current data with historical patterns:

Historical Data (last 5 entries):
{historical_str}

Current Data:
{current_str}

Please provide anomaly analysis in the following JSON format:
{{
    "is_anomaly": true,
    "confidence": 0.90,
    "anomaly_type": "type_of_anomaly",
    "anomaly_details": "detailed_description",
    "severity": "low|medium|high",
    "recommendations": ["action1", "action2"]
}}"""
    
    def _parse_analysis_response(self, response_text: str) -> Dict[str, Any]:
        """Parse analysis response from OpenAI."""
        try:
            # Try to extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Fallback if JSON parsing fails
                return {
                    'classification': 'unknown',
                    'confidence_score': 0.5,
                    'key_patterns': [],
                    'anomalies': [],
                    'insights': [response_text],
                    'recommendations': []
                }
        
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from OpenAI response")
            return {
                'classification': 'unknown',
                'confidence_score': 0.5,
                'key_patterns': [],
                'anomalies': [],
                'insights': [response_text],
                'recommendations': []
            }
    
    def _parse_fraud_response(self, response_text: str) -> Dict[str, Any]:
        """Parse fraud detection response from OpenAI."""
        try:
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                return {
                    'risk_score': 0.5,
                    'confidence': 0.5,
                    'indicators': [],
                    'risk_factors': [],
                    'recommendation': 'Manual review required',
                    'explanation': response_text
                }
        
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from fraud detection response")
            return {
                'risk_score': 0.5,
                'confidence': 0.5,
                'indicators': [],
                'risk_factors': [],
                'recommendation': 'Manual review required',
                'explanation': response_text
            }
    
    def _parse_sentiment_response(self, response_text: str) -> Dict[str, Any]:
        """Parse sentiment analysis response from OpenAI."""
        try:
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                return {
                    'sentiment': 'neutral',
                    'confidence': 0.5,
                    'emotional_indicators': [],
                    'analysis': response_text
                }
        
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from sentiment analysis response")
            return {
                'sentiment': 'neutral',
                'confidence': 0.5,
                'emotional_indicators': [],
                'analysis': response_text
            }
    
    def _parse_anomaly_response(self, response_text: str) -> Dict[str, Any]:
        """Parse anomaly detection response from OpenAI."""
        try:
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                return {
                    'is_anomaly': False,
                    'confidence': 0.5,
                    'anomaly_type': 'none',
                    'anomaly_details': response_text,
                    'severity': 'low',
                    'recommendations': []
                }
        
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON from anomaly detection response")
            return {
                'is_anomaly': False,
                'confidence': 0.5,
                'anomaly_type': 'none',
                'anomaly_details': response_text,
                'severity': 'low',
                'recommendations': []
            }
    
    def _generate_content_hash(self, content: Dict[str, Any]) -> str:
        """Generate hash for content caching."""
        import hashlib
        content_str = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def _calculate_risk_level(self, risk_score: float) -> str:
        """Calculate risk level from risk score."""
        if risk_score >= 0.8:
            return 'high'
        elif risk_score >= 0.5:
            return 'medium'
        else:
            return 'low'


class PostbackAIAnalyzer:
    """
    High-level AI analyzer for postback module.
    
    Provides convenient interface for various AI-powered analysis
    features with caching and error handling.
    """
    
    def __init__(self):
        self.openai_client = OpenAIClient()
        self.cache_timeout = getattr(settings, 'POSTBACK_AI_CACHE_TIMEOUT', 3600)  # 1 hour
    
    def analyze_postback(self, postback_log: PostbackLog) -> Dict[str, Any]:
        """
        Perform comprehensive AI analysis on a postback log.
        
        Args:
            postback_log: PostbackLog instance to analyze
            
        Returns:
            Comprehensive analysis results
        """
        try:
            # Check cache first
            cache_key = f"postback_ai_analysis_{postback_log.id}"
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
            
            # Prepare data for analysis
            postback_data = {
                'id': str(postback_log.id),
                'network': postback_log.network.network_key,
                'status': postback_log.status,
                'raw_payload': postback_log.raw_payload,
                'extracted_fields': postback_log.extracted_fields,
                'source_ip': postback_log.source_ip,
                'user_agent': postback_log.user_agent,
                'received_at': postback_log.received_at.isoformat(),
                'payout': float(postback_log.payout) if postback_log.payout else None,
                'rejection_reason': postback_log.rejection_reason,
            }
            
            # Perform analysis
            analysis_result = {
                'content_analysis': self.openai_client.analyze_postback_content(postback_data),
                'fraud_detection': self.openai_client.detect_fraud_indicators(postback_data),
                'anomaly_detection': self._detect_anomalies_for_postback(postback_log),
            }
            
            # Add sentiment analysis if text content is available
            text_content = self._extract_text_content(postback_data)
            if text_content:
                analysis_result['sentiment_analysis'] = self.openai_client.analyze_sentiment(text_content)
            
            # Add metadata
            analysis_result.update({
                'postback_id': str(postback_log.id),
                'analyzed_at': timezone.now().isoformat(),
                'analysis_version': '1.0'
            })
            
            # Cache result
            cache.set(cache_key, analysis_result, self.cache_timeout)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in postback AI analysis: {str(e)}")
            raise PostbackException(f"AI analysis failed: {str(e)}")
    
    def _detect_anomalies_for_postback(self, postback_log: PostbackLog) -> Dict[str, Any]:
        """Detect anomalies for a specific postback log."""
        try:
            # Get historical data for the same network
            historical_data = PostbackLog.objects.filter(
                network=postback_log.network,
                received_at__gte=timezone.now() - timedelta(days=7)
            ).order_by('-received_at')[:10]
            
            # Prepare historical data
            historical_list = [
                {
                    'status': log.status,
                    'payout': float(log.payout) if log.payout else 0,
                    'received_at': log.received_at.isoformat(),
                    'source_ip': log.source_ip,
                }
                for log in historical_data
            ]
            
            # Prepare current data
            current_data = {
                'status': postback_log.status,
                'payout': float(postback_log.payout) if postback_log.payout else 0,
                'received_at': postback_log.received_at.isoformat(),
                'source_ip': postback_log.source_ip,
            }
            
            return self.openai_client.detect_anomalies(historical_list, current_data)
            
        except Exception as e:
            logger.error(f"Error in anomaly detection: {str(e)}")
            return {
                'is_anomaly': False,
                'confidence': 0.0,
                'anomaly_type': 'error',
                'anomaly_details': f"Anomaly detection failed: {str(e)}",
                'severity': 'low',
                'recommendations': []
            }
    
    def _extract_text_content(self, postback_data: Dict[str, Any]) -> Optional[str]:
        """Extract text content from postback data for sentiment analysis."""
        text_parts = []
        
        # Extract text from raw payload
        if isinstance(postback_data.get('raw_payload'), dict):
            for key, value in postback_data['raw_payload'].items():
                if isinstance(value, str) and len(value) > 10:
                    text_parts.append(value)
        
        # Extract text from extracted fields
        if isinstance(postback_data.get('extracted_fields'), dict):
            for key, value in postback_data['extracted_fields'].items():
                if isinstance(value, str) and len(value) > 10:
                    text_parts.append(value)
        
        # Combine text content
        combined_text = ' '.join(text_parts)
        
        # Return if meaningful text found
        if len(combined_text) > 50:
            return combined_text[:1000]  # Limit to 1000 characters
        
        return None
    
    def generate_insight_summary(self, insights: List[PostbackInsight]) -> str:
        """
        Generate AI-powered summary of postback insights.
        
        Args:
            insights: List of PostbackInsight instances
            
        Returns:
            Generated summary text
        """
        if not self.openai_client.is_configured():
            return "AI analysis not available"
        
        try:
            # Prepare insights data
            insights_data = [
                {
                    'date': insight.date.isoformat(),
                    'network': insight.network.network_key,
                    'received_count': insight.received_count,
                    'rewarded_count': insight.rewarded_count,
                    'rejected_count': insight.rejected_count,
                    'health_score': float(insight.health_score),
                    'total_payout': float(insight.total_payout),
                    'anomaly_detected': insight.anomaly_detected,
                }
                for insight in insights
            ]
            
            # Create summary prompt
            insights_str = json.dumps(insights_data, indent=2, default=str)
            prompt = f"""Generate a comprehensive summary of the following postback insights data:

{insights_str}

Please provide a concise summary highlighting:
- Overall performance trends
- Key anomalies or issues
- Network-specific observations
- Recommendations for improvement"""
            
            # Generate summary
            response = self.openai_client.client.chat.completions.create(
                model=self.openai_client.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a postback analytics expert. Provide clear, actionable summaries of postback insights data."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=800,
                temperature=0.5
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating insight summary: {str(e)}")
            return f"Summary generation failed: {str(e)}"


# Global AI analyzer instance
ai_analyzer = PostbackAIAnalyzer()


# Convenience functions
def analyze_postback_ai(postback_log: PostbackLog) -> Dict[str, Any]:
    """Analyze postback using AI."""
    return ai_analyzer.analyze_postback(postback_log)


def generate_insight_summary_ai(insights: List[PostbackInsight]) -> str:
    """Generate insight summary using AI."""
    return ai_analyzer.generate_insight_summary(insights)


def is_ai_enabled() -> bool:
    """Check if AI features are enabled."""
    return ai_analyzer.openai_client.is_configured()


# Settings validation
def validate_openai_settings() -> Dict[str, Any]:
    """Validate OpenAI configuration settings."""
    validation_result = {
        'valid': True,
        'errors': [],
        'warnings': []
    }
    
    if not getattr(settings, 'OPENAI_API_KEY', None):
        validation_result['valid'] = False
        validation_result['errors'].append('OPENAI_API_KEY not configured')
    
    model = getattr(settings, 'POSTBACK_OPENAI_MODEL', 'gpt-3.5-turbo')
    if model not in ['gpt-3.5-turbo', 'gpt-4', 'gpt-4-turbo']:
        validation_result['warnings'].append(f'Unusual model configured: {model}')
    
    max_tokens = getattr(settings, 'POSTBACK_OPENAI_MAX_TOKENS', 1000)
    if max_tokens > 4000:
        validation_result['warnings'].append(f'High max_tokens setting: {max_tokens}')
    
    return validation_result
