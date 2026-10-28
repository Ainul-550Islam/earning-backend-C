# =============================================================================
# auto_mod/openai.py
# =============================================================================

"""
OpenAI integration for auto moderation system.
Provides AI-powered content analysis using OpenAI models.
"""

import json
import logging
import time
from typing import Dict, List, Optional, Any, Union
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from .exceptions import AIServiceUnavailableError, ScanFailedError
from .dependencies import dependency_manager

logger = logging.getLogger(__name__)


class OpenAIClient:
    """
    OpenAI client for content moderation and analysis.
    """
    
    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key (defaults to settings)
            model: Model to use for analysis
        """
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
        self.model = model or getattr(settings, 'OPENAI_MODERATION_MODEL', 'gpt-4')
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the OpenAI client."""
        try:
            if dependency_manager.is_loaded('openai'):
                openai = dependency_manager.get_dependency('openai')
                self.client = openai.OpenAI(api_key=self.api_key)
                logger.info("OpenAI client initialized successfully")
            else:
                logger.warning("OpenAI dependency not available, using mock client")
                self.client = MockOpenAIClient()
        except Exception as exc:
            logger.error(f"Failed to initialize OpenAI client: {exc}")
            self.client = MockOpenAIClient()
    
    def analyze_text(self, text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze text content for moderation.
        
        Args:
            text: Text content to analyze
            context: Additional context for analysis
            
        Returns:
            Analysis results with risk assessment
        """
        try:
            if not self.client:
                raise AIServiceUnavailableError("OpenAI client not available")
            
            # Prepare analysis prompt
            prompt = self._build_text_analysis_prompt(text, context)
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.1
            )
            
            # Parse response
            analysis = self._parse_analysis_response(response.choices[0].message.content)
            
            return {
                'status': 'success',
                'analysis': analysis,
                'confidence': analysis.get('confidence', 0.0),
                'risk_score': analysis.get('risk_score', 0.0),
                'risk_level': analysis.get('risk_level', 'low'),
                'flag_reasons': analysis.get('flag_reasons', []),
                'explanation': analysis.get('explanation', ''),
                'model_used': self.model,
                'tokens_used': response.usage.total_tokens if response.usage else 0
            }
            
        except Exception as exc:
            logger.error(f"Text analysis failed: {exc}")
            return {
                'status': 'failed',
                'error': str(exc),
                'confidence': 0.0,
                'risk_score': 0.0,
                'risk_level': 'low'
            }
    
    def analyze_image(self, image_data: bytes, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze image content for moderation.
        
        Args:
            image_data: Image binary data
            context: Additional context for analysis
            
        Returns:
            Analysis results with risk assessment
        """
        try:
            if not self.client:
                raise AIServiceUnavailableError("OpenAI client not available")
            
            # Convert image to base64
            import base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Prepare analysis prompt
            prompt = self._build_image_analysis_prompt(context)
            
            # Call OpenAI Vision API
            response = self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {"role": "system", "content": self._get_vision_system_prompt()},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.1
            )
            
            # Parse response
            analysis = self._parse_analysis_response(response.choices[0].message.content)
            
            return {
                'status': 'success',
                'analysis': analysis,
                'confidence': analysis.get('confidence', 0.0),
                'risk_score': analysis.get('risk_score', 0.0),
                'risk_level': analysis.get('risk_level', 'low'),
                'flag_reasons': analysis.get('flag_reasons', []),
                'explanation': analysis.get('explanation', ''),
                'model_used': 'gpt-4-vision-preview',
                'tokens_used': response.usage.total_tokens if response.usage else 0
            }
            
        except Exception as exc:
            logger.error(f"Image analysis failed: {exc}")
            return {
                'status': 'failed',
                'error': str(exc),
                'confidence': 0.0,
                'risk_score': 0.0,
                'risk_level': 'low'
            }
    
    def moderate_content(self, content: Union[str, bytes], content_type: str = 'text', 
                        context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Moderate content using OpenAI's moderation API.
        
        Args:
            content: Content to moderate
            content_type: Type of content ('text' or 'image')
            context: Additional context
            
        Returns:
            Moderation results
        """
        try:
            if not self.client:
                raise AIServiceUnavailableError("OpenAI client not available")
            
            if content_type == 'text':
                # Use OpenAI moderation endpoint for text
                response = self.client.moderations.create(input=content)
                
                result = response.results[0]
                
                return {
                    'status': 'success',
                    'flagged': result.flagged,
                    'categories': {
                        'hate': result.categories.hate,
                        'hate/threatening': result.categories.hate_threatening,
                        'harassment': result.categories.harassment,
                        'harassment/threatening': result.categories.harassment_threatening,
                        'self-harm': result.categories.self_harm,
                        'self-harm/intent': result.categories.self_harm_intent,
                        'self-harm/instructions': result.categories.self_harm_instructions,
                        'sexual': result.categories.sexual,
                        'sexual/minors': result.categories.sexual_minors,
                        'violence': result.categories.violence,
                        'violence/graphic': result.categories.violence_graphic
                    },
                    'category_scores': {
                        'hate': result.category_scores.hate,
                        'hate/threatening': result.category_scores.hate_threatening,
                        'harassment': result.category_scores.harassment,
                        'harassment/threatening': result.category_scores.harassment_threatening,
                        'self-harm': result.category_scores.self_harm,
                        'self-harm/intent': result.category_scores.self_harm_intent,
                        'self-harm/instructions': result.category_scores.self_harm_instructions,
                        'sexual': result.category_scores.sexual,
                        'sexual/minors': result.category_scores.sexual_minors,
                        'violence': result.category_scores.violence,
                        'violence/graphic': result.category_scores.violence_graphic
                    },
                    'confidence': max(result.category_scores.values()) if result.category_scores else 0.0,
                    'risk_score': self._calculate_risk_from_categories(result.category_scores),
                    'risk_level': self._determine_risk_level(result.flagged, result.category_scores)
                }
            else:
                # For images, use vision analysis
                return self.analyze_image(content, context)
                
        except Exception as exc:
            logger.error(f"Content moderation failed: {exc}")
            return {
                'status': 'failed',
                'error': str(exc),
                'flagged': False,
                'confidence': 0.0,
                'risk_score': 0.0,
                'risk_level': 'low'
            }
    
    def extract_text_from_image(self, image_data: bytes) -> Dict[str, Any]:
        """
        Extract text from image using OCR capabilities.
        
        Args:
            image_data: Image binary data
            
        Returns:
            OCR results
        """
        try:
            if not self.client:
                raise AIServiceUnavailableError("OpenAI client not available")
            
            # Convert image to base64
            import base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # OCR prompt
            prompt = "Extract all text from this image. Return only the extracted text, nothing else."
            
            # Call OpenAI Vision API
            response = self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            extracted_text = response.choices[0].message.content.strip()
            
            return {
                'status': 'success',
                'extracted_text': extracted_text,
                'confidence': 0.8,  # Default confidence for OCR
                'model_used': 'gpt-4-vision-preview',
                'tokens_used': response.usage.total_tokens if response.usage else 0
            }
            
        except Exception as exc:
            logger.error(f"OCR extraction failed: {exc}")
            return {
                'status': 'failed',
                'error': str(exc),
                'extracted_text': '',
                'confidence': 0.0
            }
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for text analysis."""
        return """
        You are a content moderation AI assistant. Analyze the provided text and determine if it contains any problematic content.
        
        Respond with a JSON object containing:
        {
            "confidence": 0.0-1.0,
            "risk_score": 0.0-10.0,
            "risk_level": "low|medium|high|critical",
            "flag_reasons": ["reason1", "reason2"],
            "explanation": "Detailed explanation of the analysis",
            "categories": {
                "spam": boolean,
                "hate_speech": boolean,
                "violence": boolean,
                "sexual_content": boolean,
                "harassment": boolean,
                "self_harm": boolean,
                "misinformation": boolean,
                "other_issues": boolean
            }
        }
        
        Be thorough but fair in your analysis. Consider context and nuance.
        """
    
    def _get_vision_system_prompt(self) -> str:
        """Get system prompt for image analysis."""
        return """
        You are a content moderation AI assistant for images. Analyze the provided image and determine if it contains any problematic content.
        
        Respond with a JSON object containing:
        {
            "confidence": 0.0-1.0,
            "risk_score": 0.0-10.0,
            "risk_level": "low|medium|high|critical",
            "flag_reasons": ["reason1", "reason2"],
            "explanation": "Detailed explanation of what you see in the image",
            "categories": {
                "violence": boolean,
                "sexual_content": boolean,
                "hate_symbols": boolean,
                "weapons": boolean,
                "drugs": boolean,
                "inappropriate_content": boolean,
                "other_issues": boolean
            }
        }
        
        Be thorough but fair in your analysis. Consider context and artistic merit.
        """
    
    def _build_text_analysis_prompt(self, text: str, context: Dict[str, Any] = None) -> str:
        """Build prompt for text analysis."""
        prompt = f"Analyze this text for moderation:\n\n{text}\n\n"
        
        if context:
            prompt += "Additional context:\n"
            for key, value in context.items():
                prompt += f"- {key}: {value}\n"
        
        prompt += "\nProvide your analysis in the specified JSON format."
        return prompt
    
    def _build_image_analysis_prompt(self, context: Dict[str, Any] = None) -> str:
        """Build prompt for image analysis."""
        prompt = "Analyze this image for content moderation issues."
        
        if context:
            prompt += "\nAdditional context:\n"
            for key, value in context.items():
                prompt += f"- {key}: {value}\n"
        
        prompt += "\nProvide your analysis in the specified JSON format."
        return prompt
    
    def _parse_analysis_response(self, response_text: str) -> Dict[str, Any]:
        """Parse analysis response from OpenAI."""
        try:
            # Try to extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                analysis = json.loads(json_str)
                
                # Validate required fields
                required_fields = ['confidence', 'risk_score', 'risk_level', 'flag_reasons', 'explanation']
                for field in required_fields:
                    if field not in analysis:
                        analysis[field] = self._get_default_value(field)
                
                return analysis
            else:
                # Fallback parsing
                return self._fallback_parse_response(response_text)
                
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON response: {response_text}")
            return self._fallback_parse_response(response_text)
    
    def _fallback_parse_response(self, response_text: str) -> Dict[str, Any]:
        """Fallback parsing when JSON extraction fails."""
        # Simple keyword-based analysis
        risk_keywords = ['violence', 'hate', 'sexual', 'spam', 'harassment', 'threat', 'weapon']
        text_lower = response_text.lower()
        
        flag_reasons = []
        risk_score = 0.0
        
        for keyword in risk_keywords:
            if keyword in text_lower:
                flag_reasons.append(keyword)
                risk_score += 2.0
        
        risk_score = min(risk_score, 10.0)
        
        if risk_score >= 7.0:
            risk_level = 'high'
        elif risk_score >= 4.0:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        confidence = 0.5 if flag_reasons else 0.8
        
        return {
            'confidence': confidence,
            'risk_score': risk_score,
            'risk_level': risk_level,
            'flag_reasons': flag_reasons,
            'explanation': response_text[:500],  # Truncate
            'categories': {}
        }
    
    def _get_default_value(self, field: str) -> Any:
        """Get default value for missing fields."""
        defaults = {
            'confidence': 0.0,
            'risk_score': 0.0,
            'risk_level': 'low',
            'flag_reasons': [],
            'explanation': '',
            'categories': {}
        }
        return defaults.get(field, None)
    
    def _calculate_risk_from_categories(self, category_scores: Dict[str, float]) -> float:
        """Calculate risk score from category scores."""
        if not category_scores:
            return 0.0
        
        # Weight different categories differently
        weights = {
            'hate': 2.0,
            'hate/threatening': 3.0,
            'harassment': 1.5,
            'harassment/threatening': 2.5,
            'self-harm': 1.0,
            'self-harm/intent': 2.0,
            'self-harm/instructions': 2.0,
            'sexual': 1.5,
            'sexual/minors': 3.0,
            'violence': 2.0,
            'violence/graphic': 3.0
        }
        
        total_score = 0.0
        for category, score in category_scores.items():
            weight = weights.get(category, 1.0)
            total_score += score * weight
        
        # Normalize to 0-10 scale
        return min(total_score * 10, 10.0)
    
    def _determine_risk_level(self, flagged: bool, category_scores: Dict[str, float]) -> str:
        """Determine risk level from moderation results."""
        if not flagged:
            return 'low'
        
        max_score = max(category_scores.values()) if category_scores else 0.0
        
        if max_score >= 0.8:
            return 'critical'
        elif max_score >= 0.6:
            return 'high'
        elif max_score >= 0.4:
            return 'medium'
        else:
            return 'low'


class MockOpenAIClient:
    """Mock OpenAI client for testing/fallback purposes."""
    
    def __init__(self):
        self.chat = self.Chat()
        self.moderations = self.Moderations()
    
    class Chat:
        def __init__(self):
            self.completions = self.Completions()
        
        class Completions:
            def create(self, **kwargs):
                return MockCompletion()
    
    class Moderations:
        def __init__(self):
            self.create = self.Create()
        
        class Create:
            def __call__(self, **kwargs):
                return MockModerationResult()


class MockCompletion:
    """Mock completion response."""
    
    def __init__(self):
        self.choices = [MockChoice()]
        self.usage = MockUsage()


class MockChoice:
    """Mock choice response."""
    
    def __init__(self):
        self.message = MockMessage()


class MockMessage:
    """Mock message response."""
    
    def __init__(self):
        self.content = json.dumps({
            "confidence": 0.5,
            "risk_score": 3.0,
            "risk_level": "medium",
            "flag_reasons": ["mock_analysis"],
            "explanation": "This is a mock analysis result.",
            "categories": {}
        })


class MockUsage:
    """Mock usage information."""
    
    def __init__(self):
        self.total_tokens = 100


class MockModerationResult:
    """Mock moderation result."""
    
    def __init__(self):
        self.results = [MockModerationCategory()]


class MockModerationCategory:
    """Mock moderation category."""
    
    def __init__(self):
        self.flagged = False
        self.categories = MockCategories()
        self.category_scores = MockCategoryScores()


class MockCategories:
    """Mock categories."""
    
    def __init__(self):
        self.hate = False
        self.hate_threatening = False
        self.harassment = False
        self.harassment_threatening = False
        self.self_harm = False
        self.self_harm_intent = False
        self.self_harm_instructions = False
        self.sexual = False
        self.sexual_minors = False
        self.violence = False
        self.violence_graphic = False


class MockCategoryScores:
    """Mock category scores."""
    
    def __init__(self):
        self.hate = 0.1
        self.hate_threatening = 0.05
        self.harassment = 0.1
        self.harassment_threatening = 0.05
        self.self_harm = 0.1
        self.self_harm_intent = 0.05
        self.self_harm_instructions = 0.05
        self.sexual = 0.1
        self.sexual_minors = 0.05
        self.violence = 0.1
        self.violence_graphic = 0.05
    
    def values(self):
        return [0.1, 0.05, 0.1, 0.05, 0.1, 0.05, 0.05, 0.1, 0.05, 0.1, 0.05]


# Global OpenAI client instance
_openai_client = None


def get_openai_client() -> OpenAIClient:
    """Get or create OpenAI client instance."""
    global _openai_client
    
    if _openai_client is None:
        _openai_client = OpenAIClient()
    
    return _openai_client


def analyze_content_with_openai(content: Union[str, bytes], content_type: str = 'text',
                              context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Analyze content using OpenAI.
    
    Args:
        content: Content to analyze
        content_type: Type of content ('text' or 'image')
        context: Additional context
        
    Returns:
        Analysis results
    """
    client = get_openai_client()
    
    if content_type == 'text':
        return client.analyze_text(content, context)
    elif content_type == 'image':
        return client.analyze_image(content, context)
    else:
        return client.moderate_content(content, content_type, context)


def moderate_with_openai(content: Union[str, bytes], content_type: str = 'text',
                        context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Moderate content using OpenAI's moderation API.
    
    Args:
        content: Content to moderate
        content_type: Type of content
        context: Additional context
        
    Returns:
        Moderation results
    """
    client = get_openai_client()
    return client.moderate_content(content, content_type, context)


def extract_text_with_openai(image_data: bytes) -> Dict[str, Any]:
    """
    Extract text from image using OpenAI.
    
    Args:
        image_data: Image binary data
        
    Returns:
        OCR results
    """
    client = get_openai_client()
    return client.extract_text_from_image(image_data)


# Utility functions for caching and rate limiting
def cached_analysis(cache_key: str, content: Union[str, bytes], 
                  content_type: str = 'text', ttl: int = 3600) -> Dict[str, Any]:
    """
    Perform cached analysis to avoid duplicate API calls.
    
    Args:
        cache_key: Cache key for the content
        content: Content to analyze
        content_type: Type of content
        ttl: Cache TTL in seconds
        
    Returns:
        Analysis results
    """
    # Try to get from cache
    cached_result = cache.get(cache_key)
    if cached_result:
        logger.debug(f"Cache hit for OpenAI analysis: {cache_key}")
        return cached_result
    
    # Perform analysis
    result = analyze_content_with_openai(content, content_type)
    
    # Cache the result
    cache.set(cache_key, result, ttl)
    logger.debug(f"Cached OpenAI analysis: {cache_key}")
    
    return result


def generate_cache_key(content: Union[str, bytes], content_type: str = 'text') -> str:
    """
    Generate cache key for content.
    
    Args:
        content: Content to analyze
        content_type: Type of content
        
    Returns:
        Cache key
    """
    import hashlib
    
    if content_type == 'text':
        content_hash = hashlib.md5(content.encode()).hexdigest()
    else:
        content_hash = hashlib.md5(content).hexdigest()
    
    return f"openai_analysis:{content_type}:{content_hash}"
