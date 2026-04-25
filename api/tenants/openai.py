"""
Tenant OpenAI Integration - AI-Powered Features

This module contains OpenAI integration for tenant management including
content generation, analysis, chat support, and AI-powered automation.
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
import openai
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class TenantOpenAIService:
    """
    OpenAI service for tenant AI features.
    
    Provides AI-powered functionality including content generation,
    data analysis, chat support, and automation.
    """
    
    def __init__(self):
        self.client = None
        self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-4')
        self.max_tokens = getattr(settings, 'OPENAI_MAX_TOKENS', 2000)
        self.temperature = getattr(settings, 'OPENAI_TEMPERATURE', 0.7)
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize OpenAI client."""
        try:
            api_key = getattr(settings, 'OPENAI_API_KEY', None)
            if api_key:
                self.client = OpenAI(api_key=api_key)
                logger.info("OpenAI client initialized successfully")
            else:
                logger.warning("OpenAI API key not configured")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_content(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate content using OpenAI.
        
        Args:
            prompt: The prompt for content generation
            context: Additional context for the prompt
            
        Returns:
            Dictionary containing generated content and metadata
        """
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI client not initialized',
                'content': None
            }
        
        try:
            # Prepare system message
            system_message = self._get_system_message(context)
            
            # Prepare user message with context
            user_message = self._prepare_user_message(prompt, context)
            
            # Create completion
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            
            content = response.choices[0].message.content
            
            return {
                'success': True,
                'content': content,
                'model': self.model,
                'tokens_used': response.usage.total_tokens if response.usage else 0,
                'prompt_tokens': response.usage.prompt_tokens if response.usage else 0,
                'completion_tokens': response.usage.completion_tokens if response.usage else 0,
                'created_at': datetime.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to generate content: {e}")
            return {
                'success': False,
                'error': str(e),
                'content': None
            }
    
    async def analyze_tenant_data(self, tenant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze tenant data using AI.
        
        Args:
            tenant_id: ID of the tenant
            data: Tenant data to analyze
            
        Returns:
            Dictionary containing analysis results
        """
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI client not initialized',
                'analysis': None
            }
        
        try:
            # Prepare analysis prompt
            prompt = self._prepare_analysis_prompt(data)
            
            # Generate analysis
            result = await self.generate_content(
                prompt,
                {
                    'tenant_id': tenant_id,
                    'analysis_type': 'tenant_data',
                    'data_summary': self._summarize_data(data)
                }
            )
            
            if result['success']:
                # Parse analysis if it's JSON
                try:
                    analysis = json.loads(result['content'])
                except json.JSONDecodeError:
                    analysis = {'raw_analysis': result['content']}
                
                result['analysis'] = analysis
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to analyze tenant data: {e}")
            return {
                'success': False,
                'error': str(e),
                'analysis': None
            }
    
    async def generate_tenant_recommendations(self, tenant_id: int, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate AI-powered recommendations for tenant improvement.
        
        Args:
            tenant_id: ID of the tenant
            metrics: Tenant metrics and performance data
            
        Returns:
            Dictionary containing recommendations
        """
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI client not initialized',
                'recommendations': []
            }
        
        try:
            # Prepare recommendations prompt
            prompt = self._prepare_recommendations_prompt(metrics)
            
            # Generate recommendations
            result = await self.generate_content(
                prompt,
                {
                    'tenant_id': tenant_id,
                    'analysis_type': 'recommendations',
                    'metrics_summary': self._summarize_metrics(metrics)
                }
            )
            
            if result['success']:
                # Parse recommendations
                try:
                    recommendations = json.loads(result['content'])
                    if isinstance(recommendations, dict) and 'recommendations' in recommendations:
                        result['recommendations'] = recommendations['recommendations']
                    else:
                        result['recommendations'] = recommendations
                except json.JSONDecodeError:
                    # Parse text recommendations
                    result['recommendations'] = self._parse_text_recommendations(result['content'])
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate recommendations: {e}")
            return {
                'success': False,
                'error': str(e),
                'recommendations': []
            }
    
    async def chat_with_tenant(self, tenant_id: int, message: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """
        Handle chat conversations with tenants.
        
        Args:
            tenant_id: ID of the tenant
            message: User message
            conversation_history: Previous conversation history
            
        Returns:
            Dictionary containing chat response
        """
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI client not initialized',
                'response': None
            }
        
        try:
            # Get tenant context
            tenant_context = await self._get_tenant_context(tenant_id)
            
            # Prepare conversation messages
            messages = [
                {"role": "system", "content": self._get_chat_system_message(tenant_context)}
            ]
            
            # Add conversation history
            if conversation_history:
                messages.extend(conversation_history[-10:])  # Keep last 10 messages
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            # Generate response
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
            )
            
            chat_response = response.choices[0].message.content
            
            return {
                'success': True,
                'response': chat_response,
                'model': self.model,
                'tokens_used': response.usage.total_tokens if response.usage else 0,
                'timestamp': datetime.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to generate chat response: {e}")
            return {
                'success': False,
                'error': str(e),
                'response': None
            }
    
    async def generate_email_content(self, template_type: str, recipient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate email content using AI.
        
        Args:
            template_type: Type of email template
            recipient_data: Data about the recipient
            
        Returns:
            Dictionary containing email content
        """
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI client not initialized',
                'content': None
            }
        
        try:
            # Prepare email prompt
            prompt = self._prepare_email_prompt(template_type, recipient_data)
            
            # Generate content
            result = await self.generate_content(
                prompt,
                {
                    'template_type': template_type,
                    'recipient_data': recipient_data
                }
            )
            
            if result['success']:
                # Parse email content
                email_content = self._parse_email_content(result['content'])
                result['content'] = email_content
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate email content: {e}")
            return {
                'success': False,
                'error': str(e),
                'content': None
            }
    
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary containing sentiment analysis
        """
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI client not initialized',
                'sentiment': None
            }
        
        try:
            prompt = f"""
            Analyze the sentiment of the following text and provide a JSON response with:
            - sentiment (positive, negative, neutral)
            - confidence (0-1)
            - emotions (list of detected emotions)
            - key_topics (list of key topics mentioned)
            
            Text: {text}
            """
            
            result = await self.generate_content(prompt)
            
            if result['success']:
                try:
                    sentiment_data = json.loads(result['content'])
                    result['sentiment'] = sentiment_data
                except json.JSONDecodeError:
                    result['sentiment'] = {'raw_analysis': result['content']}
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to analyze sentiment: {e}")
            return {
                'success': False,
                'error': str(e),
                'sentiment': None
            }
    
    async def generate_summary(self, content: str, summary_type: str = 'general') -> Dict[str, Any]:
        """
        Generate summary of content.
        
        Args:
            content: Content to summarize
            summary_type: Type of summary (general, executive, detailed)
            
        Returns:
            Dictionary containing summary
        """
        if not self.client:
            return {
                'success': False,
                'error': 'OpenAI client not initialized',
                'summary': None
            }
        
        try:
            prompt = self._prepare_summary_prompt(content, summary_type)
            
            result = await self.generate_content(prompt)
            
            if result['success']:
                result['summary'] = result['content']
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return {
                'success': False,
                'error': str(e),
                'summary': None
            }
    
    def _get_system_message(self, context: Dict[str, Any] = None) -> str:
        """Get system message for OpenAI API."""
        base_message = "You are a helpful AI assistant for a multi-tenant platform. "
        
        if context:
            if context.get('analysis_type') == 'tenant_data':
                base_message += "You specialize in analyzing tenant data and providing insights. "
            elif context.get('analysis_type') == 'recommendations':
                base_message += "You specialize in providing actionable recommendations for tenant improvement. "
            elif context.get('template_type'):
                base_message += "You specialize in generating professional email content. "
        
        base_message += "Provide clear, concise, and helpful responses."
        return base_message
    
    def _prepare_user_message(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Prepare user message with context."""
        message = prompt
        
        if context:
            context_info = []
            
            if 'tenant_id' in context:
                context_info.append(f"Tenant ID: {context['tenant_id']}")
            
            if 'data_summary' in context:
                context_info.append(f"Data Summary: {context['data_summary']}")
            
            if 'metrics_summary' in context:
                context_info.append(f"Metrics Summary: {context['metrics_summary']}")
            
            if context_info:
                message = f"Context: {', '.join(context_info)}\n\n{message}"
        
        return message
    
    def _prepare_analysis_prompt(self, data: Dict[str, Any]) -> str:
        """Prepare prompt for data analysis."""
        return f"""
        Analyze the following tenant data and provide insights in JSON format:
        
        Data: {json.dumps(data, indent=2)}
        
        Provide analysis covering:
        - Key metrics and trends
        - Performance indicators
        - Potential issues or concerns
        - Areas for improvement
        - Comparison with typical benchmarks
        
        Format your response as a JSON object with the following structure:
        {{
            "key_metrics": {{"metric_name": "value", ...}},
            "trends": ["trend1", "trend2", ...],
            "issues": ["issue1", "issue2", ...],
            "improvements": ["improvement1", "improvement2", ...],
            "recommendations": ["recommendation1", "recommendation2", ...]
        }}
        """
    
    def _prepare_recommendations_prompt(self, metrics: Dict[str, Any]) -> str:
        """Prepare prompt for recommendations."""
        return f"""
        Based on the following tenant metrics, generate actionable recommendations for improvement:
        
        Metrics: {json.dumps(metrics, indent=2)}
        
        Provide recommendations in JSON format with the following structure:
        {{
            "recommendations": [
                {{
                    "category": "category_name",
                    "priority": "high|medium|low",
                    "title": "Recommendation title",
                    "description": "Detailed description",
                    "expected_impact": "Expected impact description",
                    "implementation_effort": "low|medium|high",
                    "timeline": "Estimated timeline"
                }}
            ]
        }}
        
        Focus on practical, actionable recommendations that can improve tenant performance and user experience.
        """
    
    def _prepare_email_prompt(self, template_type: str, recipient_data: Dict[str, Any]) -> str:
        """Prepare prompt for email generation."""
        prompts = {
            'welcome': "Generate a welcome email for a new tenant. Include:",
            'trial_expiry': "Generate a trial expiry reminder email. Include:",
            'payment_overdue': "Generate a payment overdue notification email. Include:",
            'feature_announcement': "Generate a feature announcement email. Include:",
            'support_response': "Generate a support response email. Include:",
        }
        
        base_prompt = prompts.get(template_type, "Generate an email. Include:")
        
        return f"""
        {base_prompt}
        - Professional and friendly tone
        - Clear call-to-action
        - Relevant information
        - Personalized content
        
        Recipient data: {json.dumps(recipient_data, indent=2)}
        
        Format your response as JSON with:
        {{
            "subject": "Email subject",
            "body": "Email body content",
            "call_to_action": "Call to action text",
            "personalization_elements": ["element1", "element2"]
        }}
        """
    
    def _prepare_summary_prompt(self, content: str, summary_type: str) -> str:
        """Prepare prompt for summary generation."""
        type_instructions = {
            'general': "Provide a general summary of the main points.",
            'executive': "Provide an executive summary focusing on key insights and actions.",
            'detailed': "Provide a detailed summary covering all important aspects.",
        }
        
        instruction = type_instructions.get(summary_type, type_instructions['general'])
        
        return f"""
        {instruction}
        
        Content to summarize: {content}
        
        Keep the summary concise but comprehensive, highlighting the most important information.
        """
    
    def _get_chat_system_message(self, tenant_context: Dict[str, Any]) -> str:
        """Get system message for chat."""
        return f"""
        You are a helpful AI assistant for a multi-tenant platform.
        
        Tenant Context: {json.dumps(tenant_context, indent=2)}
        
        Provide helpful, accurate, and professional responses. If you don't know something, admit it politely.
        Focus on helping the tenant with their questions about the platform, features, and best practices.
        """
    
    async def _get_tenant_context(self, tenant_id: int) -> Dict[str, Any]:
        """Get tenant context for chat."""
        try:
            from .models_improved import Tenant
            
            tenant = await Tenant.objects.aget(id=tenant_id)
            
            return {
                'tenant_name': tenant.name,
                'tenant_plan': tenant.plan,
                'tenant_status': tenant.status,
                'user_count': tenant.get_active_user_count(),
                'features': tenant.get_feature_flags(),
                'is_trial_active': tenant.is_trial_active(),
            }
            
        except Exception as e:
            logger.error(f"Failed to get tenant context: {e}")
            return {}
    
    def _summarize_data(self, data: Dict[str, Any]) -> str:
        """Summarize data for context."""
        if not data:
            return "No data available"
        
        key_points = []
        
        # Extract key metrics
        if 'user_count' in data:
            key_points.append(f"Users: {data['user_count']}")
        if 'revenue' in data:
            key_points.append(f"Revenue: ${data['revenue']}")
        if 'active_users' in data:
            key_points.append(f"Active users: {data['active_users']}")
        
        return ", ".join(key_points) if key_points else "Data available"
    
    def _summarize_metrics(self, metrics: Dict[str, Any]) -> str:
        """Summarize metrics for context."""
        if not metrics:
            return "No metrics available"
        
        key_metrics = []
        
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                key_metrics.append(f"{key}: {value}")
        
        return ", ".join(key_metrics) if key_metrics else "Metrics available"
    
    def _parse_text_recommendations(self, content: str) -> List[Dict[str, Any]]:
        """Parse text recommendations into structured format."""
        recommendations = []
        
        # Simple parsing - split by lines and create basic structure
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and (line.startswith('-') or line.startswith('*') or line.startswith('1.')):
                recommendation = {
                    'category': 'general',
                    'priority': 'medium',
                    'title': line.lstrip('-*1. ').strip(),
                    'description': line.lstrip('-*1. ').strip(),
                    'expected_impact': 'To be determined',
                    'implementation_effort': 'medium',
                    'timeline': 'To be determined'
                }
                recommendations.append(recommendation)
        
        return recommendations
    
    def _parse_email_content(self, content: str) -> Dict[str, Any]:
        """Parse email content from AI response."""
        try:
            # Try to parse as JSON first
            email_data = json.loads(content)
            
            # Ensure required fields
            if 'subject' not in email_data:
                email_data['subject'] = 'Generated Email'
            if 'body' not in email_data:
                email_data['body'] = content
            
            return email_data
            
        except json.JSONDecodeError:
            # Fallback to simple parsing
            lines = content.split('\n')
            
            subject = 'Generated Email'
            body = content
            
            # Try to extract subject from first line
            if lines and len(lines[0]) < 100:
                subject = lines[0].strip()
                body = '\n'.join(lines[1:]).strip()
            
            return {
                'subject': subject,
                'body': body,
                'call_to_action': 'Contact support for more information',
                'personalization_elements': []
            }


# Global OpenAI service instance
openai_service = TenantOpenAIService()


# Utility functions
async def generate_tenant_insights(tenant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate AI insights for tenant."""
    return await openai_service.analyze_tenant_data(tenant_id, data)


async def get_tenant_recommendations(tenant_id: int, metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Get AI recommendations for tenant."""
    return await openai_service.generate_tenant_recommendations(tenant_id, metrics)


async def chat_with_tenant_support(tenant_id: int, message: str, history: List[Dict] = None) -> Dict[str, Any]:
    """Chat with tenant support AI."""
    return await openai_service.chat_with_tenant(tenant_id, message, history)


async def generate_ai_email(template_type: str, recipient_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate AI-powered email content."""
    return await openai_service.generate_email_content(template_type, recipient_data)


def is_openai_enabled() -> bool:
    """Check if OpenAI integration is enabled."""
    return openai_service.client is not None


def get_openai_model_info() -> Dict[str, Any]:
    """Get OpenAI model information."""
    return {
        'model': openai_service.model,
        'max_tokens': openai_service.max_tokens,
        'temperature': openai_service.temperature,
        'enabled': is_openai_enabled(),
    }
