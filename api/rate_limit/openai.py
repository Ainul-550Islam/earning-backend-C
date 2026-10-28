# api/rate_limit/openai.py
"""
OpenAI Integration for Rate Limit Module

Provides AI-powered analysis and insights for rate limiting data.
"""
from django.db.models import Count

import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


class OpenAIClient:
    """
    OpenAI client for rate limit analysis and insights.
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'OPENAI_API_KEY', None)
        self.model = getattr(settings, 'OPENAI_MODEL', 'gpt-3.5-turbo')
        self.max_tokens = getattr(settings, 'OPENAI_MAX_TOKENS', 1000)
        self.temperature = getattr(settings, 'OPENAI_TEMPERATURE', 0.7)
        
        if not self.api_key:
            logger.warning("OpenAI API key not configured")
            self.enabled = False
        else:
            self.enabled = True
            try:
                import openai
                self.client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                logger.error("OpenAI library not installed")
                self.enabled = False
    
    def is_enabled(self) -> bool:
        """Check if OpenAI integration is enabled."""
        return self.enabled
    
    async def analyze_rate_limit_patterns(self, logs_data: List[Dict]) -> Dict[str, Any]:
        """
        Analyze rate limit patterns using AI.
        
        Args:
            logs_data: List of rate limit log entries
            
        Returns:
            Dict containing analysis results
        """
        if not self.enabled:
            return {'error': 'OpenAI not enabled'}
        
        try:
            # Prepare data for analysis
            analysis_prompt = self._prepare_pattern_analysis_prompt(logs_data)
            
            # Call OpenAI API
            response = await self._call_openai_api(analysis_prompt)
            
            # Parse response
            analysis_result = self._parse_analysis_response(response)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in rate limit pattern analysis: {str(e)}")
            return {'error': str(e)}
    
    async def detect_abuse_patterns(self, logs_data: List[Dict]) -> Dict[str, Any]:
        """
        Detect abuse patterns using AI.
        
        Args:
            logs_data: List of rate limit log entries
            
        Returns:
            Dict containing abuse detection results
        """
        if not self.enabled:
            return {'error': 'OpenAI not enabled'}
        
        try:
            # Prepare data for abuse detection
            abuse_prompt = self._prepare_abuse_detection_prompt(logs_data)
            
            # Call OpenAI API
            response = await self._call_openai_api(abuse_prompt)
            
            # Parse response
            abuse_result = self._parse_abuse_response(response)
            
            return abuse_result
            
        except Exception as e:
            logger.error(f"Error in abuse pattern detection: {str(e)}")
            return {'error': str(e)}
    
    async def generate_insights_report(self, stats_data: Dict) -> Dict[str, Any]:
        """
        Generate insights report using AI.
        
        Args:
            stats_data: Statistics data for analysis
            
        Returns:
            Dict containing insights report
        """
        if not self.enabled:
            return {'error': 'OpenAI not enabled'}
        
        try:
            # Prepare data for insights
            insights_prompt = self._prepare_insights_prompt(stats_data)
            
            # Call OpenAI API
            response = await self._call_openai_api(insights_prompt)
            
            # Parse response
            insights_result = self._parse_insights_response(response)
            
            return insights_result
            
        except Exception as e:
            logger.error(f"Error in insights report generation: {str(e)}")
            return {'error': str(e)}
    
    async def suggest_rate_limit_adjustments(self, config_data: Dict, performance_data: Dict) -> Dict[str, Any]:
        """
        Suggest rate limit adjustments using AI.
        
        Args:
            config_data: Current rate limit configuration
            performance_data: Performance metrics
            
        Returns:
            Dict containing adjustment suggestions
        """
        if not self.enabled:
            return {'error': 'OpenAI not enabled'}
        
        try:
            # Prepare data for suggestions
            suggestions_prompt = self._prepare_suggestions_prompt(config_data, performance_data)
            
            # Call OpenAI API
            response = await self._call_openai_api(suggestions_prompt)
            
            # Parse response
            suggestions_result = self._parse_suggestions_response(response)
            
            return suggestions_result
            
        except Exception as e:
            logger.error(f"Error in rate limit suggestions: {str(e)}")
            return {'error': str(e)}
    
    def _prepare_pattern_analysis_prompt(self, logs_data: List[Dict]) -> str:
        """Prepare prompt for pattern analysis."""
        # Limit data to prevent token overflow
        limited_logs = logs_data[:100] if len(logs_data) > 100 else logs_data
        
        prompt = f"""
        Analyze the following rate limit logs and identify patterns:

        Log Data:
        {json.dumps(limited_logs, indent=2, default=str)}

        Please analyze and provide:
        1. Request frequency patterns
        2. Time-based patterns (hourly, daily)
        3. IP address patterns
        4. Endpoint-specific patterns
        5. User behavior patterns
        6. Any suspicious or anomalous patterns

        Format your response as JSON with the following structure:
        {{
            "patterns": {{
                "frequency": [description of frequency patterns],
                "time_based": [description of time patterns],
                "ip_patterns": [description of IP patterns],
                "endpoint_patterns": [description of endpoint patterns],
                "user_patterns": [description of user patterns],
                "anomalies": [description of suspicious patterns]
            }},
            "recommendations": [list of recommendations],
            "risk_assessment": {{
                "risk_level": "low|medium|high",
                "explanation": "explanation of risk level"
            }}
        }}
        """
        
        return prompt
    
    def _prepare_abuse_detection_prompt(self, logs_data: List[Dict]) -> str:
        """Prepare prompt for abuse detection."""
        # Focus on blocked and high-suspicion logs
        suspicious_logs = [
            log for log in logs_data 
            if log.get('status') == 'blocked' or log.get('suspicion_score', 0) > 50
        ]
        
        # Limit data
        limited_logs = suspicious_logs[:50] if len(suspicious_logs) > 50 else suspicious_logs
        
        prompt = f"""
        Analyze the following suspicious rate limit logs for abuse patterns:

        Suspicious Log Data:
        {json.dumps(limited_logs, indent=2, default=str)}

        Please identify:
        1. Types of abuse (bot activity, scraping, brute force, etc.)
        2. Attack patterns and techniques
        3. Source IP patterns
        4. Target endpoints
        5. Time-based attack patterns
        6. Severity assessment

        Format your response as JSON:
        {{
            "abuse_detected": true/false,
            "abuse_types": [list of detected abuse types],
            "attack_patterns": {{
                "technique": "description",
                "frequency": "high/medium/low",
                "severity": "critical/high/medium/low"
            }},
            "source_analysis": {{
                "ip_ranges": [list of suspicious IP ranges],
                "geographic_patterns": "description",
                "user_agents": [list of suspicious user agents]
            }},
            "recommendations": [list of specific recommendations],
            "immediate_actions": [list of immediate actions to take]
        }}
        """
        
        return prompt
    
    def _prepare_insights_prompt(self, stats_data: Dict) -> str:
        """Prepare prompt for insights report."""
        prompt = f"""
        Generate insights report based on the following rate limit statistics:

        Statistics Data:
        {json.dumps(stats_data, indent=2, default=str)}

        Please provide:
        1. Overall system health assessment
        2. Performance trends
        3. Key metrics analysis
        4. Areas of concern
        5. Optimization opportunities
        6. Future predictions

        Format your response as JSON:
        {{
            "health_assessment": {{
                "score": 0-100,
                "status": "excellent|good|fair|poor|critical",
                "summary": "summary of system health"
            }},
            "performance_analysis": {{
                "trends": [description of trends],
                "bottlenecks": [list of bottlenecks],
                "efficiency_score": 0-100
            }},
            "key_insights": [list of key insights],
            "concerns": [list of concerns],
            "optimization_opportunities": [list of opportunities],
            "predictions": {{
                "next_period": "prediction for next period",
                "confidence": "high/medium/low"
            }}
        }}
        """
        
        return prompt
    
    def _prepare_suggestions_prompt(self, config_data: Dict, performance_data: Dict) -> str:
        """Prepare prompt for rate limit suggestions."""
        prompt = f"""
        Provide rate limit configuration suggestions based on current configuration and performance:

        Current Configuration:
        {json.dumps(config_data, indent=2, default=str)}

        Performance Data:
        {json.dumps(performance_data, indent=2, default=str)}

        Please suggest:
        1. Rate limit adjustments
        2. Configuration optimizations
        3. New rules to implement
        4. Rules to remove or modify
        5. Performance improvements

        Format your response as JSON:
        {{
            "suggested_adjustments": [
                {{
                    "config_name": "name of config",
                    "current_limit": current_value,
                    "suggested_limit": suggested_value,
                    "reason": "reason for change",
                    "impact": "expected impact"
                }}
            ],
            "new_rules": [
                {{
                    "rule_type": "type of rule",
                    "parameters": "rule parameters",
                    "reason": "reason for new rule"
                }}
            ],
            "optimizations": [list of optimization suggestions],
            "performance_improvements": [list of performance improvements],
            "implementation_priority": "high|medium|low"
        }}
        """
        
        return prompt
    
    async def _call_openai_api(self, prompt: str) -> str:
        """Call OpenAI API asynchronously."""
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert in rate limiting and security analysis."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API call failed: {str(e)}")
            raise
    
    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse pattern analysis response."""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            return {
                'patterns': {'raw_response': response},
                'recommendations': [],
                'risk_assessment': {'risk_level': 'unknown', 'explanation': 'Failed to parse response'}
            }
    
    def _parse_abuse_response(self, response: str) -> Dict[str, Any]:
        """Parse abuse detection response."""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                'abuse_detected': False,
                'abuse_types': [],
                'attack_patterns': {},
                'source_analysis': {},
                'recommendations': [],
                'immediate_actions': [],
                'raw_response': response
            }
    
    def _parse_insights_response(self, response: str) -> Dict[str, Any]:
        """Parse insights response."""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                'health_assessment': {'score': 50, 'status': 'unknown', 'summary': 'Failed to parse response'},
                'performance_analysis': {},
                'key_insights': [],
                'concerns': [],
                'optimization_opportunities': [],
                'predictions': {},
                'raw_response': response
            }
    
    def _parse_suggestions_response(self, response: str) -> Dict[str, Any]:
        """Parse suggestions response."""
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                'suggested_adjustments': [],
                'new_rules': [],
                'optimizations': [],
                'performance_improvements': [],
                'implementation_priority': 'medium',
                'raw_response': response
            }


class RateLimitAIAnalyzer:
    """
    AI-powered analyzer for rate limiting data.
    """
    
    def __init__(self):
        self.openai_client = OpenAIClient()
        self.cache_timeout = 3600  # 1 hour
    
    async def analyze_recent_activity(self, hours: int = 24) -> Dict[str, Any]:
        """
        Analyze recent rate limit activity using AI.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Dict containing analysis results
        """
        cache_key = f"rate_limit_ai_analysis_{hours}h"
        
        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        try:
            # Get recent logs
            from api.rate_limit.models import RateLimitLog
            since_time = timezone.now() - timedelta(hours=hours)
            
            logs = RateLimitLog.objects.filter(
                timestamp__gte=since_time
            ).select_related('user', 'config')
            
            # Convert to dict format
            logs_data = []
            for log in logs:
                logs_data.append({
                    'timestamp': log.timestamp.isoformat(),
                    'ip_address': log.ip_address,
                    'user': log.user.username if log.user else 'Anonymous',
                    'endpoint': log.endpoint,
                    'method': log.request_method,
                    'status': log.status,
                    'suspicion_score': log.suspicion_score,
                    'config': log.config.name if log.config else None,
                })
            
            # Perform AI analysis
            analysis_result = await self.openai_client.analyze_rate_limit_patterns(logs_data)
            
            # Cache result
            cache.set(cache_key, analysis_result, self.cache_timeout)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error in recent activity analysis: {str(e)}")
            return {'error': str(e)}
    
    async def detect_abuse_activity(self, hours: int = 24) -> Dict[str, Any]:
        """
        Detect abuse activity using AI.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Dict containing abuse detection results
        """
        cache_key = f"rate_limit_abuse_detection_{hours}h"
        
        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        try:
            # Get recent logs
            from api.rate_limit.models import RateLimitLog
            since_time = timezone.now() - timedelta(hours=hours)
            
            logs = RateLimitLog.objects.filter(
                timestamp__gte=since_time
            ).select_related('user', 'config')
            
            # Convert to dict format
            logs_data = []
            for log in logs:
                logs_data.append({
                    'timestamp': log.timestamp.isoformat(),
                    'ip_address': log.ip_address,
                    'user': log.user.username if log.user else 'Anonymous',
                    'endpoint': log.endpoint,
                    'method': log.request_method,
                    'status': log.status,
                    'suspicion_score': log.suspicion_score,
                    'config': log.config.name if log.config else None,
                })
            
            # Perform abuse detection
            abuse_result = await self.openai_client.detect_abuse_patterns(logs_data)
            
            # Cache result
            cache.set(cache_key, abuse_result, self.cache_timeout)
            
            return abuse_result
            
        except Exception as e:
            logger.error(f"Error in abuse detection: {str(e)}")
            return {'error': str(e)}
    
    async def generate_daily_insights(self, date: datetime = None) -> Dict[str, Any]:
        """
        Generate daily insights using AI.
        
        Args:
            date: Date to generate insights for (default: today)
            
        Returns:
            Dict containing insights
        """
        if date is None:
            date = timezone.now().date()
        
        cache_key = f"rate_limit_daily_insights_{date}"
        
        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        try:
            # Get statistics for the date
            from api.rate_limit.models import RateLimitLog, RateLimitInsight
            
            start_datetime = timezone.make_aware(datetime.combine(date, datetime.min.time()))
            end_datetime = timezone.make_aware(datetime.combine(date, datetime.max.time()))
            
            logs = RateLimitLog.objects.filter(
                timestamp__gte=start_datetime,
                timestamp__lte=end_datetime
            )
            
            # Prepare statistics data
            stats_data = {
                'date': date.isoformat(),
                'total_requests': logs.count(),
                'blocked_requests': logs.filter(status='blocked').count(),
                'allowed_requests': logs.filter(status='allowed').count(),
                'unique_ips': logs.values('ip_address').distinct().count(),
                'unique_users': logs.values('user').distinct().count(),
                'top_endpoints': list(
                    logs.values('endpoint')
                    .annotate(count=Count('id'))
                    .order_by('-count')[:10]
                    .values_list('endpoint', flat=True)
                ),
                'top_ips': list(
                    logs.values('ip_address')
                    .annotate(count=Count('id'))
                    .order_by('-count')[:10]
                    .values_list('ip_address', flat=True)
                ),
                'hourly_distribution': list(
                    logs.extra({'hour': "strftime('%%H', timestamp)"})
                    .values('hour')
                    .annotate(count=Count('id'))
                    .order_by('hour')
                )
            }
            
            # Generate insights
            insights_result = await self.openai_client.generate_insights_report(stats_data)
            
            # Cache result
            cache.set(cache_key, insights_result, self.cache_timeout * 24)  # Cache for 24 hours
            
            return insights_result
            
        except Exception as e:
            logger.error(f"Error in daily insights generation: {str(e)}")
            return {'error': str(e)}
    
    async def suggest_config_optimizations(self) -> Dict[str, Any]:
        """
        Suggest configuration optimizations using AI.
        
        Returns:
            Dict containing optimization suggestions
        """
        cache_key = "rate_limit_config_suggestions"
        
        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        try:
            # Get current configurations
            from api.rate_limit.models import RateLimitConfig
            configs = RateLimitConfig.objects.filter(is_active=True)
            
            config_data = {}
            for config in configs:
                config_data[config.name] = {
                    'type': config.rate_limit_type,
                    'limit': config.requests_per_unit,
                    'time_unit': config.time_unit,
                    'time_value': config.time_value,
                    'hit_count': config.hit_count,
                    'block_count': config.block_count,
                }
            
            # Get performance data
            from api.rate_limit.models import RateLimitLog
            last_24h = timezone.now() - timedelta(hours=24)
            
            performance_data = {
                'total_requests_24h': RateLimitLog.objects.filter(
                    timestamp__gte=last_24h
                ).count(),
                'blocked_requests_24h': RateLimitLog.objects.filter(
                    timestamp__gte=last_24h,
                    status='blocked'
                ).count(),
                'top_blocked_configs': list(
                    RateLimitLog.objects.filter(
                        timestamp__gte=last_24h,
                        status='blocked'
                    ).values('config__name')
                    .annotate(count=Count('id'))
                    .order_by('-count')[:5]
                    .values_list('config__name', flat=True)
                )
            }
            
            # Generate suggestions
            suggestions_result = await self.openai_client.suggest_rate_limit_adjustments(
                config_data, performance_data
            )
            
            # Cache result
            cache.set(cache_key, suggestions_result, self.cache_timeout * 6)  # Cache for 6 hours
            
            return suggestions_result
            
        except Exception as e:
            logger.error(f"Error in config optimization suggestions: {str(e)}")
            return {'error': str(e)}


# Global instances
openai_client = OpenAIClient()
ai_analyzer = RateLimitAIAnalyzer()


# Export functions for external use
__all__ = [
    'OpenAIClient',
    'RateLimitAIAnalyzer',
    'openai_client',
    'ai_analyzer'
]
