# =============================================================================
# fraud_detection/openai.py
# =============================================================================
"""
OpenAI Integration for Fraud Detection System.

Provides AI-powered fraud analysis, pattern recognition,
and natural language processing for fraud detection workflows.
"""

from __future__ import annotations

import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone
import openai
from openai import AsyncOpenAI

from api.fraud_detection.encryption import encrypt_sensitive_data, generate_integrity_hash
from api.fraud_detection.exceptions import AIError, OpenAIError
from api.fraud_detection.caching import get_risk_score_cache


logger = logging.getLogger(__name__)


@dataclass
class AIAnalysisResult:
    """Data class for AI analysis results."""
    analysis_type: str
    confidence_score: float
    risk_assessment: str
    key_findings: List[str]
    recommendations: List[str]
    processing_time: float
    model_used: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class OpenAIFraudAnalyzer:
    """
    OpenAI-powered fraud analysis engine.
    
    Provides AI-driven fraud pattern detection, risk assessment,
    and natural language analysis for fraud detection workflows.
    """
    
    def __init__(self):
        """Initialize OpenAI fraud analyzer."""
        self.api_key = getattr(settings, 'OPENAI_API_KEY', None)
        self.model = getattr(settings, 'FRAUD_OPENAI_MODEL', 'gpt-4')
        self.max_tokens = getattr(settings, 'FRAUD_OPENAI_MAX_TOKENS', 2000)
        self.temperature = getattr(settings, 'FRAUD_OPENAI_TEMPERATURE', 0.3)
        self.cache_ttl = getattr(settings, 'FRAUD_AI_CACHE_TTL', 3600)  # 1 hour
        
        # Initialize OpenAI client
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key)
            self.sync_client = openai.OpenAI(api_key=self.api_key)
        else:
            logger.warning("OpenAI API key not configured")
            self.client = None
            self.sync_client = None
        
        # Load analysis prompts
        self.prompts = self._load_analysis_prompts()
    
    def _load_analysis_prompts(self) -> Dict[str, str]:
        """Load analysis prompts for different fraud detection scenarios."""
        default_prompts = {
            'transaction_analysis': """
            Analyze the following transaction for potential fraud indicators:
            
            Transaction Details:
            - Amount: {amount}
            - User ID: {user_id}
            - Merchant: {merchant}
            - Location: {location}
            - Device: {device}
            - Time: {timestamp}
            - Description: {description}
            
            Please analyze this transaction for:
            1. Fraud risk indicators
            2. Suspicious patterns
            3. Risk level (low/medium/high/critical)
            4. Recommended actions
            5. Confidence score (0-100)
            
            Respond in JSON format with the following structure:
            {{
                "risk_level": "high",
                "confidence_score": 85,
                "fraud_indicators": ["indicator1", "indicator2"],
                "suspicious_patterns": ["pattern1", "pattern2"],
                "recommendations": ["action1", "action2"],
                "analysis_summary": "Brief summary of findings"
            }}
            """,
            
            'user_behavior_analysis': """
            Analyze the user behavior patterns for potential fraud:
            
            User Profile:
            - User ID: {user_id}
            - Account Age: {account_age}
            - Transaction History: {transaction_history}
            - Login Patterns: {login_patterns}
            - Device Usage: {device_usage}
            - Geographic Activity: {geographic_activity}
            
            Please analyze for:
            1. Behavioral anomalies
            2. Account takeover indicators
            3. Synthetic identity patterns
            4. Money laundering indicators
            5. Risk assessment
            6. Confidence score (0-100)
            
            Respond in JSON format with the following structure:
            {{
                "behavioral_risk": "medium",
                "confidence_score": 70,
                "anomalies": ["anomaly1", "anomaly2"],
                "risk_indicators": ["indicator1", "indicator2"],
                "recommendations": ["action1", "action2"],
                "analysis_summary": "Summary of behavioral analysis"
            }}
            """,
            
            'document_analysis': """
            Analyze the following document for fraud indicators:
            
            Document Information:
            - Type: {document_type}
            - Content: {content}
            - Metadata: {metadata}
            - Source: {source}
            
            Please analyze for:
            1. Document authenticity
            2. Forgery indicators
            3. Information consistency
            4. Suspicious elements
            5. Risk assessment
            6. Confidence score (0-100)
            
            Respond in JSON format with the following structure:
            {{
                "authenticity_score": 75,
                "confidence_score": 80,
                "forgery_indicators": ["indicator1", "indicator2"],
                "inconsistencies": ["inconsistency1", "inconsistency2"],
                "risk_assessment": "medium",
                "recommendations": ["action1", "action2"],
                "analysis_summary": "Document analysis summary"
            }}
            """,
            
            'pattern_detection': """
            Analyze the following data patterns for fraud:
            
            Pattern Data:
            - Data Type: {data_type}
            - Time Series: {time_series}
            - Relationships: {relationships}
            - Anomalies: {anomalies}
            
            Please analyze for:
            1. Fraud patterns
            2. Network relationships
            3. Coordinated activity
            4. Money laundering patterns
            5. Risk assessment
            6. Confidence score (0-100)
            
            Respond in JSON format with the following structure:
            {{
                "pattern_risk": "high",
                "confidence_score": 90,
                "detected_patterns": ["pattern1", "pattern2"],
                "network_analysis": "Network analysis summary",
                "coordinated_activity": true,
                "recommendations": ["action1", "action2"],
                "analysis_summary": "Pattern detection summary"
            }}
            """
        }
        
        return getattr(settings, 'FRAUD_OPENAI_PROMPTS', default_prompts)
    
    async def analyze_transaction(self, transaction_data: Dict[str, Any]) -> AIAnalysisResult:
        """
        Analyze transaction for fraud indicators using AI.
        
        Args:
            transaction_data: Transaction data dictionary
            
        Returns:
            AI analysis result
        """
        try:
            if not self.client:
                raise OpenAIError("OpenAI client not initialized")
            
            # Check cache first
            cache_key = f"ai_transaction_analysis_{hash(str(transaction_data))}"
            cache = get_risk_score_cache()
            cached_result = cache.cache_manager.get(cache_key)
            
            if cached_result:
                logger.debug(f"AI transaction analysis cache hit for key: {cache_key}")
                return AIAnalysisResult(**cached_result)
            
            # Prepare prompt
            prompt = self.prompts['transaction_analysis'].format(**transaction_data)
            
            start_time = timezone.now()
            
            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a fraud detection expert specializing in transaction analysis."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            processing_time = (timezone.now() - start_time).total_seconds()
            
            # Parse response
            analysis_data = json.loads(response.choices[0].message.content)
            
            # Create result object
            result = AIAnalysisResult(
                analysis_type='transaction',
                confidence_score=analysis_data.get('confidence_score', 0),
                risk_assessment=analysis_data.get('risk_level', 'unknown'),
                key_findings=analysis_data.get('fraud_indicators', []) + analysis_data.get('suspicious_patterns', []),
                recommendations=analysis_data.get('recommendations', []),
                processing_time=processing_time,
                model_used=self.model,
                timestamp=timezone.now(),
                metadata={
                    'transaction_id': transaction_data.get('transaction_id'),
                    'raw_response': analysis_data
                }
            )
            
            # Cache result
            cache.cache_manager.set(cache_key, result.__dict__, self.cache_ttl)
            
            logger.info(f"AI transaction analysis completed in {processing_time:.2f}s with confidence {result.confidence_score}")
            return result
            
        except Exception as e:
            logger.error(f"Error in AI transaction analysis: {e}")
            raise OpenAIError(f"Failed to analyze transaction: {e}")
    
    async def analyze_user_behavior(self, user_data: Dict[str, Any]) -> AIAnalysisResult:
        """
        Analyze user behavior for fraud indicators using AI.
        
        Args:
            user_data: User behavior data dictionary
            
        Returns:
            AI analysis result
        """
        try:
            if not self.client:
                raise OpenAIError("OpenAI client not initialized")
            
            # Check cache
            cache_key = f"ai_behavior_analysis_{user_data.get('user_id')}"
            cache = get_risk_score_cache()
            cached_result = cache.cache_manager.get(cache_key)
            
            if cached_result:
                return AIAnalysisResult(**cached_result)
            
            # Prepare prompt
            prompt = self.prompts['user_behavior_analysis'].format(**user_data)
            
            start_time = timezone.now()
            
            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a fraud detection expert specializing in behavioral analysis."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            processing_time = (timezone.now() - start_time).total_seconds()
            
            # Parse response
            analysis_data = json.loads(response.choices[0].message.content)
            
            # Create result object
            result = AIAnalysisResult(
                analysis_type='user_behavior',
                confidence_score=analysis_data.get('confidence_score', 0),
                risk_assessment=analysis_data.get('behavioral_risk', 'unknown'),
                key_findings=analysis_data.get('anomalies', []) + analysis_data.get('risk_indicators', []),
                recommendations=analysis_data.get('recommendations', []),
                processing_time=processing_time,
                model_used=self.model,
                timestamp=timezone.now(),
                metadata={
                    'user_id': user_data.get('user_id'),
                    'raw_response': analysis_data
                }
            )
            
            # Cache result
            cache.cache_manager.set(cache_key, result.__dict__, self.cache_ttl)
            
            logger.info(f"AI behavior analysis completed for user {user_data.get('user_id')}")
            return result
            
        except Exception as e:
            logger.error(f"Error in AI behavior analysis: {e}")
            raise OpenAIError(f"Failed to analyze user behavior: {e}")
    
    async def analyze_document(self, document_data: Dict[str, Any]) -> AIAnalysisResult:
        """
        Analyze document for fraud indicators using AI.
        
        Args:
            document_data: Document data dictionary
            
        Returns:
            AI analysis result
        """
        try:
            if not self.client:
                raise OpenAIError("OpenAI client not initialized")
            
            # Check cache
            cache_key = f"ai_document_analysis_{hash(str(document_data))}"
            cache = get_risk_score_cache()
            cached_result = cache.cache_manager.get(cache_key)
            
            if cached_result:
                return AIAnalysisResult(**cached_result)
            
            # Prepare prompt
            prompt = self.prompts['document_analysis'].format(**document_data)
            
            start_time = timezone.now()
            
            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a fraud detection expert specializing in document analysis."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            processing_time = (timezone.now() - start_time).total_seconds()
            
            # Parse response
            analysis_data = json.loads(response.choices[0].message.content)
            
            # Create result object
            result = AIAnalysisResult(
                analysis_type='document',
                confidence_score=analysis_data.get('confidence_score', 0),
                risk_assessment=analysis_data.get('risk_assessment', 'unknown'),
                key_findings=analysis_data.get('forgery_indicators', []) + analysis_data.get('inconsistencies', []),
                recommendations=analysis_data.get('recommendations', []),
                processing_time=processing_time,
                model_used=self.model,
                timestamp=timezone.now(),
                metadata={
                    'document_type': document_data.get('document_type'),
                    'raw_response': analysis_data
                }
            )
            
            # Cache result
            cache.cache_manager.set(cache_key, result.__dict__, self.cache_ttl)
            
            logger.info(f"AI document analysis completed for {document_data.get('document_type')}")
            return result
            
        except Exception as e:
            logger.error(f"Error in AI document analysis: {e}")
            raise OpenAIError(f"Failed to analyze document: {e}")
    
    async def detect_patterns(self, pattern_data: Dict[str, Any]) -> AIAnalysisResult:
        """
        Detect fraud patterns using AI analysis.
        
        Args:
            pattern_data: Pattern data dictionary
            
        Returns:
            AI analysis result
        """
        try:
            if not self.client:
                raise OpenAIError("OpenAI client not initialized")
            
            # Check cache
            cache_key = f"ai_pattern_detection_{hash(str(pattern_data))}"
            cache = get_risk_score_cache()
            cached_result = cache.cache_manager.get(cache_key)
            
            if cached_result:
                return AIAnalysisResult(**cached_result)
            
            # Prepare prompt
            prompt = self.prompts['pattern_detection'].format(**pattern_data)
            
            start_time = timezone.now()
            
            # Call OpenAI API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a fraud detection expert specializing in pattern analysis."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            processing_time = (timezone.now() - start_time).total_seconds()
            
            # Parse response
            analysis_data = json.loads(response.choices[0].message.content)
            
            # Create result object
            result = AIAnalysisResult(
                analysis_type='pattern_detection',
                confidence_score=analysis_data.get('confidence_score', 0),
                risk_assessment=analysis_data.get('pattern_risk', 'unknown'),
                key_findings=analysis_data.get('detected_patterns', []),
                recommendations=analysis_data.get('recommendations', []),
                processing_time=processing_time,
                model_used=self.model,
                timestamp=timezone.now(),
                metadata={
                    'data_type': pattern_data.get('data_type'),
                    'coordinated_activity': analysis_data.get('coordinated_activity', False),
                    'raw_response': analysis_data
                }
            )
            
            # Cache result
            cache.cache_manager.set(cache_key, result.__dict__, self.cache_ttl)
            
            logger.info(f"AI pattern detection completed for {pattern_data.get('data_type')}")
            return result
            
        except Exception as e:
            logger.error(f"Error in AI pattern detection: {e}")
            raise OpenAIError(f"Failed to detect patterns: {e}")
    
    def analyze_transaction_sync(self, transaction_data: Dict[str, Any]) -> AIAnalysisResult:
        """
        Synchronous version of transaction analysis.
        
        Args:
            transaction_data: Transaction data dictionary
            
        Returns:
            AI analysis result
        """
        try:
            if not self.sync_client:
                raise OpenAIError("OpenAI sync client not initialized")
            
            # Prepare prompt
            prompt = self.prompts['transaction_analysis'].format(**transaction_data)
            
            start_time = timezone.now()
            
            # Call OpenAI API
            response = self.sync_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a fraud detection expert specializing in transaction analysis."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            processing_time = (timezone.now() - start_time).total_seconds()
            
            # Parse response
            analysis_data = json.loads(response.choices[0].message.content)
            
            # Create result object
            result = AIAnalysisResult(
                analysis_type='transaction',
                confidence_score=analysis_data.get('confidence_score', 0),
                risk_assessment=analysis_data.get('risk_level', 'unknown'),
                key_findings=analysis_data.get('fraud_indicators', []) + analysis_data.get('suspicious_patterns', []),
                recommendations=analysis_data.get('recommendations', []),
                processing_time=processing_time,
                model_used=self.model,
                timestamp=timezone.now(),
                metadata={
                    'transaction_id': transaction_data.get('transaction_id'),
                    'raw_response': analysis_data
                }
            )
            
            logger.info(f"Sync AI transaction analysis completed in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error in sync AI transaction analysis: {e}")
            raise OpenAIError(f"Failed to analyze transaction: {e}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the AI model configuration."""
        return {
            'model': self.model,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'api_key_configured': bool(self.api_key),
            'client_initialized': bool(self.client),
            'cache_ttl': self.cache_ttl,
            'available_prompts': list(self.prompts.keys())
        }
    
    def update_prompts(self, new_prompts: Dict[str, str]) -> bool:
        """Update analysis prompts."""
        try:
            self.prompts.update(new_prompts)
            logger.info(f"Updated {len(new_prompts)} analysis prompts")
            return True
        except Exception as e:
            logger.error(f"Error updating prompts: {e}")
            return False


class AIEnrichmentService:
    """
    Service for enriching fraud detection data with AI insights.
    
    Provides batch processing, result aggregation, and
    integration with existing fraud detection workflows.
    """
    
    def __init__(self):
        """Initialize AI enrichment service."""
        self.analyzer = OpenAIFraudAnalyzer()
        self.batch_size = getattr(settings, 'FRAUD_AI_BATCH_SIZE', 10)
        self.max_concurrent = getattr(settings, 'FRAUD_AI_MAX_CONCURRENT', 5)
    
    async def enrich_transaction_batch(self, transactions: List[Dict[str, Any]]) -> List[AIAnalysisResult]:
        """
        Enrich multiple transactions with AI analysis.
        
        Args:
            transactions: List of transaction data
            
        Returns:
            List of AI analysis results
        """
        results = []
        
        # Process in batches to avoid rate limits
        for i in range(0, len(transactions), self.batch_size):
            batch = transactions[i:i + self.batch_size]
            
            # Process batch concurrently
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            async def analyze_single_transaction(transaction):
                async with semaphore:
                    return await self.analyzer.analyze_transaction(transaction)
            
            batch_tasks = [analyze_single_transaction(tx) for tx in batch]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Filter out exceptions and add valid results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Error in batch analysis: {result}")
                else:
                    results.append(result)
        
        return results
    
    def aggregate_ai_insights(self, results: List[AIAnalysisResult]) -> Dict[str, Any]:
        """
        Aggregate AI analysis results into insights.
        
        Args:
            results: List of AI analysis results
            
        Returns:
            Aggregated insights dictionary
        """
        if not results:
            return {'error': 'No results to aggregate'}
        
        # Calculate statistics
        total_analyses = len(results)
        avg_confidence = sum(r.confidence_score for r in results) / total_analyses
        avg_processing_time = sum(r.processing_time for r in results) / total_analyses
        
        # Risk distribution
        risk_counts = {}
        for result in results:
            risk_counts[result.risk_assessment] = risk_counts.get(result.risk_assessment, 0) + 1
        
        # Common findings
        all_findings = []
        for result in results:
            all_findings.extend(result.key_findings)
        
        # Count most common findings
        finding_counts = {}
        for finding in all_findings:
            finding_counts[finding] = finding_counts.get(finding, 0) + 1
        
        # Sort by frequency
        top_findings = sorted(finding_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            'summary': {
                'total_analyses': total_analyses,
                'average_confidence': avg_confidence,
                'average_processing_time': avg_processing_time,
                'model_used': results[0].model_used if results else None
            },
            'risk_distribution': risk_counts,
            'top_findings': top_findings,
            'recommendations': list(set(
                rec for result in results for rec in result.recommendations
            ))[:20],
            'analysis_period': {
                'start': min(result.timestamp for result in results).isoformat(),
                'end': max(result.timestamp for result in results).isoformat()
            }
        }


# Global instances
_ai_analyzer = None
_ai_enrichment_service = None


def get_ai_analyzer() -> OpenAIFraudAnalyzer:
    """Get or create AI analyzer instance."""
    global _ai_analyzer
    if _ai_analyzer is None:
        _ai_analyzer = OpenAIFraudAnalyzer()
    return _ai_analyzer


def get_ai_enrichment_service() -> AIEnrichmentService:
    """Get or create AI enrichment service instance."""
    global _ai_enrichment_service
    if _ai_enrichment_service is None:
        _ai_enrichment_service = AIEnrichmentService()
    return _ai_enrichment_service


def analyze_transaction_with_ai(transaction_data: Dict[str, Any]) -> AIAnalysisResult:
    """
    Convenience function for transaction AI analysis.
    
    Args:
        transaction_data: Transaction data
        
    Returns:
        AI analysis result
    """
    analyzer = get_ai_analyzer()
    return analyzer.analyze_transaction_sync(transaction_data)


def enrich_fraud_data_with_ai(data_list: List[Dict[str, Any]], 
                             analysis_type: str = 'transaction') -> List[AIAnalysisResult]:
    """
    Convenience function for batch AI enrichment.
    
    Args:
        data_list: List of data to analyze
        analysis_type: Type of analysis to perform
        
    Returns:
        List of AI analysis results
    """
    service = get_ai_enrichment_service()
    
    if analysis_type == 'transaction':
        return asyncio.run(service.enrich_transaction_batch(data_list))
    else:
        raise ValueError(f"Unsupported analysis type: {analysis_type}")
