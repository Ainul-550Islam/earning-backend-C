"""
Security OpenAI Integration
AI-powered security analysis and threat detection
Author: System Security Team
Version: 1.0.0
"""

import logging
import json
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
import openai
import tiktoken
import hashlib
import base64

logger = logging.getLogger(__name__)


class SecurityOpenAIError(Exception):
    """Base exception for OpenAI security errors"""
    pass


class SecurityOpenAIConfigError(SecurityOpenAIError):
    """Exception for OpenAI configuration errors"""
    pass


class SecurityOpenAIAPIError(SecurityOpenAIError):
    """Exception for OpenAI API errors"""
    pass


class SecurityOpenAIQuotaExceeded(SecurityOpenAIError):
    """Exception for OpenAI quota exceeded"""
    pass


class SecurityOpenAIService:
    """
    OpenAI integration for security analysis and threat detection
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize OpenAI service
        
        Args:
            config (Dict[str, Any], optional): Configuration overrides
        """
        self.config = config or {}
        self.api_key = self.config.get('api_key') or getattr(settings, 'OPENAI_API_KEY', None)
        self.model = self.config.get('model', 'gpt-4')
        self.max_tokens = self.config.get('max_tokens', 4000)
        self.temperature = self.config.get('temperature', 0.1)
        self.timeout = self.config.get('timeout', 30)
        self.cache_timeout = self.config.get('cache_timeout', 3600)
        
        # Initialize OpenAI client
        self._initialize_client()
        
        # Initialize tokenizer
        self._initialize_tokenizer()
    
    def _initialize_client(self):
        """Initialize OpenAI client"""
        try:
            if not self.api_key:
                raise SecurityOpenAIConfigError("OpenAI API key is required")
            
            openai.api_key = self.api_key
            logger.info("OpenAI client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise SecurityOpenAIConfigError(f"OpenAI initialization failed: {e}")
    
    def _initialize_tokenizer(self):
        """Initialize tokenizer for token counting"""
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model)
        except Exception as e:
            logger.warning(f"Failed to initialize tokenizer for {self.model}: {e}")
            # Fallback to a common tokenizer
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text
        
        Args:
            text (str): Text to count tokens for
            
        Returns:
            int: Number of tokens
        """
        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            logger.error(f"Error counting tokens: {e}")
            # Fallback estimation (rough: 1 token ≈ 4 characters)
            return len(text) // 4
    
    def _truncate_text(self, text: str, max_tokens: int = None) -> str:
        """
        Truncate text to fit within token limit
        
        Args:
            text (str): Text to truncate
            max_tokens (int, optional): Maximum tokens
            
        Returns:
            str: Truncated text
        """
        if max_tokens is None:
            max_tokens = self.max_tokens - 100  # Reserve tokens for response
        
        try:
            tokens = self.tokenizer.encode(text)
            if len(tokens) <= max_tokens:
                return text
            
            # Truncate to max_tokens
            truncated_tokens = tokens[:max_tokens]
            return self.tokenizer.decode(truncated_tokens)
            
        except Exception as e:
            logger.error(f"Error truncating text: {e}")
            # Fallback: simple character truncation
            max_chars = max_tokens * 4  # Rough estimate
            return text[:max_chars]
    
    def _get_cache_key(self, prefix: str, data: str) -> str:
        """
        Generate cache key for OpenAI requests
        
        Args:
            prefix (str): Cache key prefix
            data (str): Data to hash
            
        Returns:
            str: Cache key
        """
        data_hash = hashlib.sha256(data.encode()).hexdigest()[:16]
        return f"openai_security_{prefix}_{data_hash}"
    
    def _check_rate_limit(self) -> bool:
        """
        Check if we're within rate limits
        
        Returns:
            bool: True if within limits
        """
        cache_key = "openai_rate_limit"
        current_requests = cache.get(cache_key, 0)
        
        # Simple rate limiting: 100 requests per hour
        if current_requests >= 100:
            return False
        
        # Increment counter
        cache.set(cache_key, current_requests + 1, timeout=3600)
        return True
    
    async def analyze_security_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze security log using OpenAI
        
        Args:
            log_data (Dict[str, Any]): Security log data
            
        Returns:
            Dict[str, Any]: Analysis results
        """
        try:
            # Check rate limit
            if not self._check_rate_limit():
                raise SecurityOpenAIQuotaExceeded("Rate limit exceeded")
            
            # Generate cache key
            cache_key = self._get_cache_key("log_analysis", json.dumps(log_data, sort_keys=True))
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
            
            # Prepare prompt
            prompt = self._create_security_log_prompt(log_data)
            
            # Truncate if necessary
            prompt = self._truncate_text(prompt)
            
            # Call OpenAI API
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a cybersecurity expert analyzing security logs. Provide detailed analysis of security events, identify potential threats, and recommend actions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=self.timeout
            )
            
            # Parse response
            analysis = self._parse_security_log_analysis(response.choices[0].message.content)
            
            # Add metadata
            analysis.update({
                'log_id': log_data.get('id'),
                'analyzed_at': timezone.now().isoformat(),
                'model_used': self.model,
                'tokens_used': response.usage.total_tokens if response.usage else None
            })
            
            # Cache result
            cache.set(cache_key, analysis, timeout=self.cache_timeout)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing security log: {e}")
            return {
                'error': str(e),
                'log_id': log_data.get('id'),
                'analyzed_at': timezone.now().isoformat()
            }
    
    def _create_security_log_prompt(self, log_data: Dict[str, Any]) -> str:
        """
        Create prompt for security log analysis
        
        Args:
            log_data (Dict[str, Any]): Security log data
            
        Returns:
            str: Analysis prompt
        """
        prompt = f"""
Analyze the following security log entry and provide a comprehensive security assessment:

SECURITY LOG DATA:
- Event Type: {log_data.get('event_type', 'Unknown')}
- Severity: {log_data.get('severity', 'Unknown')}
- IP Address: {log_data.get('ip_address', 'Unknown')}
- User: {log_data.get('user', 'Unknown')}
- User Agent: {log_data.get('user_agent', 'Unknown')}
- Timestamp: {log_data.get('created_at', 'Unknown')}
- Country: {log_data.get('country', 'Unknown')}
- City: {log_data.get('city', 'Unknown')}

ADDITIONAL METADATA:
{json.dumps(log_data.get('metadata', {}), indent=2)}

Please provide:
1. Threat Assessment (Low/Medium/High/Critical)
2. Risk Factors Identified
3. Potential Attack Vectors
4. Recommended Actions
5. Investigation Priority
6. Related Security Concerns

Format your response as JSON with the following structure:
{{
    "threat_assessment": "High",
    "risk_factors": ["factor1", "factor2"],
    "attack_vectors": ["vector1", "vector2"],
    "recommended_actions": ["action1", "action2"],
    "investigation_priority": "High",
    "related_concerns": ["concern1", "concern2"],
    "analysis_summary": "Brief summary of the security implications"
}}
"""
        return prompt
    
    def _parse_security_log_analysis(self, response_text: str) -> Dict[str, Any]:
        """
        Parse OpenAI response for security log analysis
        
        Args:
            response_text (str): OpenAI response text
            
        Returns:
            Dict[str, Any]: Parsed analysis
        """
        try:
            # Try to extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Fallback: create basic structure from text
                return {
                    'threat_assessment': 'Unknown',
                    'risk_factors': [],
                    'attack_vectors': [],
                    'recommended_actions': [],
                    'investigation_priority': 'Medium',
                    'related_concerns': [],
                    'analysis_summary': response_text.strip()
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing OpenAI response: {e}")
            return {
                'threat_assessment': 'Unknown',
                'risk_factors': [],
                'attack_vectors': [],
                'recommended_actions': [],
                'investigation_priority': 'Medium',
                'related_concerns': [],
                'analysis_summary': response_text.strip(),
                'parse_error': str(e)
            }
    
    async def detect_anomalies(self, log_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect anomalies in security logs using OpenAI
        
        Args:
            log_entries (List[Dict[str, Any]]): List of security log entries
            
        Returns:
            Dict[str, Any]: Anomaly detection results
        """
        try:
            # Check rate limit
            if not self._check_rate_limit():
                raise SecurityOpenAIQuotaExceeded("Rate limit exceeded")
            
            # Generate cache key
            cache_key = self._get_cache_key("anomaly_detection", json.dumps(log_entries, sort_keys=True))
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
            
            # Prepare prompt
            prompt = self._create_anomaly_detection_prompt(log_entries)
            
            # Truncate if necessary
            prompt = self._truncate_text(prompt)
            
            # Call OpenAI API
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a cybersecurity expert specializing in anomaly detection. Analyze the provided security logs and identify any unusual patterns, anomalies, or potential security threats."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=self.timeout
            )
            
            # Parse response
            analysis = self._parse_anomaly_detection(response.choices[0].message.content)
            
            # Add metadata
            analysis.update({
                'analyzed_at': timezone.now().isoformat(),
                'model_used': self.model,
                'tokens_used': response.usage.total_tokens if response.usage else None,
                'log_count': len(log_entries)
            })
            
            # Cache result
            cache.set(cache_key, analysis, timeout=self.cache_timeout)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return {
                'error': str(e),
                'analyzed_at': timezone.now().isoformat(),
                'log_count': len(log_entries)
            }
    
    def _create_anomaly_detection_prompt(self, log_entries: List[Dict[str, Any]]) -> str:
        """
        Create prompt for anomaly detection
        
        Args:
            log_entries (List[Dict[str, Any]]): Security log entries
            
        Returns:
            str: Anomaly detection prompt
        """
        # Limit number of entries for analysis
        entries_to_analyze = log_entries[:20]  # Limit to 20 most recent entries
        
        prompt = f"""
Analyze the following {len(entries_to_analyze)} security log entries for anomalies and unusual patterns:

LOG ENTRIES:
"""
        
        for i, entry in enumerate(entries_to_analyze, 1):
            prompt += f"""
{i}. Event: {entry.get('event_type', 'Unknown')}
   Severity: {entry.get('severity', 'Unknown')}
   IP: {entry.get('ip_address', 'Unknown')}
   User: {entry.get('user', 'Unknown')}
   Time: {entry.get('created_at', 'Unknown')}
   Country: {entry.get('country', 'Unknown')}
"""
        
        prompt += """

Please identify:
1. Anomalies Detected (list specific unusual patterns)
2. Potential Security Threats
3. Suspicious IP Addresses or Users
4. Unusual Event Patterns
5. Recommended Investigations
6. Risk Level Assessment

Format your response as JSON:
{{
    "anomalies_detected": ["anomaly1", "anomaly2"],
    "security_threats": ["threat1", "threat2"],
    "suspicious_ips": ["ip1", "ip2"],
    "suspicious_users": ["user1", "user2"],
    "unusual_patterns": ["pattern1", "pattern2"],
    "recommended_investigations": ["investigation1", "investigation2"],
    "risk_level": "High",
    "analysis_summary": "Summary of findings"
}}
"""
        return prompt
    
    def _parse_anomaly_detection(self, response_text: str) -> Dict[str, Any]:
        """
        Parse OpenAI response for anomaly detection
        
        Args:
            response_text (str): OpenAI response text
            
        Returns:
            Dict[str, Any]: Parsed analysis
        """
        try:
            # Try to extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Fallback: create basic structure from text
                return {
                    'anomalies_detected': [],
                    'security_threats': [],
                    'suspicious_ips': [],
                    'suspicious_users': [],
                    'unusual_patterns': [],
                    'recommended_investigations': [],
                    'risk_level': 'Medium',
                    'analysis_summary': response_text.strip()
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing anomaly detection response: {e}")
            return {
                'anomalies_detected': [],
                'security_threats': [],
                'suspicious_ips': [],
                'suspicious_users': [],
                'unusual_patterns': [],
                'recommended_investigations': [],
                'risk_level': 'Medium',
                'analysis_summary': response_text.strip(),
                'parse_error': str(e)
            }
    
    async def generate_security_report(self, time_period: str, summary_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate security report using OpenAI
        
        Args:
            time_period (str): Time period for report
            summary_data (Dict[str, Any]): Security summary data
            
        Returns:
            Dict[str, Any]: Generated report
        """
        try:
            # Check rate limit
            if not self._check_rate_limit():
                raise SecurityOpenAIQuotaExceeded("Rate limit exceeded")
            
            # Generate cache key
            cache_key = self._get_cache_key("security_report", f"{time_period}_{json.dumps(summary_data, sort_keys=True)}")
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
            
            # Prepare prompt
            prompt = self._create_security_report_prompt(time_period, summary_data)
            
            # Truncate if necessary
            prompt = self._truncate_text(prompt)
            
            # Call OpenAI API
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a cybersecurity expert generating comprehensive security reports. Analyze the provided security data and create a detailed, professional security report."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=self.timeout
            )
            
            # Parse response
            report = self._parse_security_report(response.choices[0].message.content)
            
            # Add metadata
            report.update({
                'time_period': time_period,
                'generated_at': timezone.now().isoformat(),
                'model_used': self.model,
                'tokens_used': response.usage.total_tokens if response.usage else None
            })
            
            # Cache result
            cache.set(cache_key, report, timeout=self.cache_timeout)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating security report: {e}")
            return {
                'error': str(e),
                'time_period': time_period,
                'generated_at': timezone.now().isoformat()
            }
    
    def _create_security_report_prompt(self, time_period: str, summary_data: Dict[str, Any]) -> str:
        """
        Create prompt for security report generation
        
        Args:
            time_period (str): Time period for report
            summary_data (Dict[str, Any]): Security summary data
            
        Returns:
            str: Report generation prompt
        """
        prompt = f"""
Generate a comprehensive security report for the {time_period} period based on the following security data:

SECURITY SUMMARY DATA:
{json.dumps(summary_data, indent=2)}

Please create a professional security report that includes:
1. Executive Summary
2. Key Security Metrics
3. Threat Landscape Analysis
4. Incident Analysis
5. Risk Assessment
6. Recommendations
7. Action Items
8. Future Outlook

Format your response as JSON:
{{
    "executive_summary": "Brief overview of security posture",
    "key_metrics": {{
        "total_events": 1234,
        "high_risk_incidents": 56,
        "blocked_ips": 78,
        "security_score": 85
    }},
    "threat_landscape": "Analysis of current threat environment",
    "incident_analysis": "Analysis of security incidents",
    "risk_assessment": "Overall risk assessment",
    "recommendations": ["recommendation1", "recommendation2"],
    "action_items": ["action1", "action2"],
    "future_outlook": "Predictions and recommendations for future",
    "report_grade": "A",
    "security_score": 85
}}
"""
        return prompt
    
    def _parse_security_report(self, response_text: str) -> Dict[str, Any]:
        """
        Parse OpenAI response for security report
        
        Args:
            response_text (str): OpenAI response text
            
        Returns:
            Dict[str, Any]: Parsed report
        """
        try:
            # Try to extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Fallback: create basic structure from text
                return {
                    'executive_summary': response_text.strip(),
                    'key_metrics': {},
                    'threat_landscape': '',
                    'incident_analysis': '',
                    'risk_assessment': '',
                    'recommendations': [],
                    'action_items': [],
                    'future_outlook': '',
                    'report_grade': 'B',
                    'security_score': 75
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing security report response: {e}")
            return {
                'executive_summary': response_text.strip(),
                'key_metrics': {},
                'threat_landscape': '',
                'incident_analysis': '',
                'risk_assessment': '',
                'recommendations': [],
                'action_items': [],
                'future_outlook': '',
                'report_grade': 'B',
                'security_score': 75,
                'parse_error': str(e)
            }
    
    async def classify_threat(self, threat_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify security threat using OpenAI
        
        Args:
            threat_data (Dict[str, Any]): Threat data to classify
            
        Returns:
            Dict[str, Any]: Threat classification
        """
        try:
            # Check rate limit
            if not self._check_rate_limit():
                raise SecurityOpenAIQuotaExceeded("Rate limit exceeded")
            
            # Generate cache key
            cache_key = self._get_cache_key("threat_classification", json.dumps(threat_data, sort_keys=True))
            cached_result = cache.get(cache_key)
            
            if cached_result:
                return cached_result
            
            # Prepare prompt
            prompt = self._create_threat_classification_prompt(threat_data)
            
            # Truncate if necessary
            prompt = self._truncate_text(prompt)
            
            # Call OpenAI API
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a cybersecurity threat classification expert. Analyze threat indicators and classify threats into appropriate categories with confidence scores."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=self.timeout
            )
            
            # Parse response
            classification = self._parse_threat_classification(response.choices[0].message.content)
            
            # Add metadata
            classification.update({
                'classified_at': timezone.now().isoformat(),
                'model_used': self.model,
                'tokens_used': response.usage.total_tokens if response.usage else None
            })
            
            # Cache result
            cache.set(cache_key, classification, timeout=self.cache_timeout)
            
            return classification
            
        except Exception as e:
            logger.error(f"Error classifying threat: {e}")
            return {
                'error': str(e),
                'classified_at': timezone.now().isoformat()
            }
    
    def _create_threat_classification_prompt(self, threat_data: Dict[str, Any]) -> str:
        """
        Create prompt for threat classification
        
        Args:
            threat_data (Dict[str, Any]): Threat data to classify
            
        Returns:
            str: Threat classification prompt
        """
        prompt = f"""
Classify the following security threat based on the provided indicators:

THREAT DATA:
{json.dumps(threat_data, indent=2)}

Please provide:
1. Threat Category (e.g., Malware, Phishing, DDoS, Data Breach, etc.)
2. Threat Subcategory
3. Severity Level (Critical, High, Medium, Low)
4. Confidence Score (0-100)
5. Attack Vector
6. Target Type
7. Recommended Response
8. Related MITRE ATT&CK Techniques (if applicable)

Format your response as JSON:
{{
    "threat_category": "Malware",
    "threat_subcategory": "Ransomware",
    "severity_level": "High",
    "confidence_score": 85,
    "attack_vector": "Email attachment",
    "target_type": "Endpoints",
    "recommended_response": ["response1", "response2"],
    "mitre_techniques": ["T1059", "T1055"],
    "classification_summary": "Summary of threat classification"
}}
"""
        return prompt
    
    def _parse_threat_classification(self, response_text: str) -> Dict[str, Any]:
        """
        Parse OpenAI response for threat classification
        
        Args:
            response_text (str): OpenAI response text
            
        Returns:
            Dict[str, Any]: Parsed classification
        """
        try:
            # Try to extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                return json.loads(json_str)
            else:
                # Fallback: create basic structure from text
                return {
                    'threat_category': 'Unknown',
                    'threat_subcategory': 'Unknown',
                    'severity_level': 'Medium',
                    'confidence_score': 50,
                    'attack_vector': 'Unknown',
                    'target_type': 'Unknown',
                    'recommended_response': [],
                    'mitre_techniques': [],
                    'classification_summary': response_text.strip()
                }
                
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing threat classification response: {e}")
            return {
                'threat_category': 'Unknown',
                'threat_subcategory': 'Unknown',
                'severity_level': 'Medium',
                'confidence_score': 50,
                'attack_vector': 'Unknown',
                'target_type': 'Unknown',
                'recommended_response': [],
                'mitre_techniques': [],
                'classification_summary': response_text.strip(),
                'parse_error': str(e)
            }
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """
        Get OpenAI usage statistics
        
        Returns:
            Dict[str, Any]: Usage statistics
        """
        try:
            cache_key = "openai_usage_stats"
            stats = cache.get(cache_key, {
                'total_requests': 0,
                'total_tokens': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'errors': 0
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting usage statistics: {e}")
            return {
                'total_requests': 0,
                'total_tokens': 0,
                'cache_hits': 0,
                'cache_misses': 0,
                'errors': 0,
                'error': str(e)
            }
    
    def reset_usage_statistics(self):
        """Reset usage statistics"""
        try:
            cache_key = "openai_usage_stats"
            cache.delete(cache_key)
            logger.info("OpenAI usage statistics reset")
            
        except Exception as e:
            logger.error(f"Error resetting usage statistics: {e}")


# Global OpenAI service instance
security_openai_service = SecurityOpenAIService()

# Export for use in other modules
__all__ = [
    'SecurityOpenAIService',
    'security_openai_service',
    'SecurityOpenAIError',
    'SecurityOpenAIConfigError',
    'SecurityOpenAIAPIError',
    'SecurityOpenAIQuotaExceeded',
]