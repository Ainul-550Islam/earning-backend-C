"""
🤖 OpenAI Integration Module

This module provides comprehensive OpenAI integration for the backup system.
It includes AI-powered backup analysis, intelligent recommendations, automated
reporting, and smart backup management using OpenAI's language models.

Features:
- Backup analysis and insights using GPT models
- Intelligent backup recommendations
- Automated report generation
- Natural language backup queries
- Backup optimization suggestions
- Anomaly detection and alerting
- Backup strategy optimization
- Compliance assistance and reporting
"""

import logging
import json
import asyncio
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import openai
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q, Count, Avg
from django.utils.text import slugify

# Import backup models
from .models import Backup, BackupSchedule, BackupLog, BackupAlert, BackupVerification
from .analytics import BackupAnalytics
from .monitoring import BackupMonitor
from .utils import TimeUtils

logger = logging.getLogger(__name__)


class OpenAIModel(Enum):
    """Enumeration of OpenAI models."""
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-turbo-preview"
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"


class AnalysisType(Enum):
    """Enumeration of analysis types."""
    BACKUP_PERFORMANCE = "backup_performance"
    BACKUP_HEALTH = "backup_health"
    BACKUP_OPTIMIZATION = "backup_optimization"
    BACKUP_STRATEGY = "backup_strategy"
    BACKUP_ANOMALY = "backup_anomaly"
    BACKUP_COMPLIANCE = "backup_compliance"
    BACKUP_COST = "backup_cost"
    BACKUP_SECURITY = "backup_security"


class RecommendationType(Enum):
    """Enumeration of recommendation types."""
    PERFORMANCE = "performance"
    SECURITY = "security"
    COST = "cost"
    COMPLIANCE = "compliance"
    RELIABILITY = "reliability"
    EFFICIENCY = "efficiency"
    MAINTENANCE = "maintenance"


@dataclass
class AIAnalysis:
    """AI analysis result."""
    analysis_id: str
    analysis_type: AnalysisType
    model_used: OpenAIModel
    insights: List[str]
    recommendations: List[Dict[str, Any]]
    confidence_score: float  # 0-1
    data_summary: Dict[str, Any]
    processing_time_ms: float
    created_at: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BackupQuery:
    """Natural language backup query."""
    query_id: str
    question: str
    context: Optional[str] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    model: OpenAIModel = OpenAIModel.GPT_4O_MINI
    created_at: datetime = field(default_factory=timezone.now)


@dataclass
class QueryResult:
    """Result of a natural language query."""
    query_id: str
    answer: str
    confidence: float
    supporting_data: Dict[str, Any]
    follow_up_questions: List[str]
    processing_time_ms: float
    model_used: OpenAIModel


class OpenAIClient:
    """OpenAI API client with backup-specific functionality."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'OPENAI_API_KEY', None)
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        openai.api_key = self.api_key
        self.default_model = OpenAIModel.GPT_4O_MINI
        self.max_tokens = getattr(settings, 'OPENAI_MAX_TOKENS', 2000)
        self.temperature = getattr(settings, 'OPENAI_TEMPERATURE', 0.3)
    
    async def analyze_backup_data(self, data: Dict[str, Any], 
                                analysis_type: AnalysisType,
                                model: Optional[OpenAIModel] = None) -> AIAnalysis:
        """Analyze backup data using OpenAI."""
        start_time = timezone.now()
        model = model or self.default_model
        
        try:
            # Prepare analysis prompt based on type
            prompt = self._prepare_analysis_prompt(data, analysis_type)
            
            # Call OpenAI API
            response = await openai.ChatCompletion.acreate(
                model=model.value,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(analysis_type)
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
            content = response.choices[0].message.content
            parsed_result = self._parse_analysis_response(content, analysis_type)
            
            # Calculate processing time
            processing_time = (timezone.now() - start_time).total_seconds() * 1000
            
            return AIAnalysis(
                analysis_id=f"analysis_{int(start_time.timestamp())}",
                analysis_type=analysis_type,
                model_used=model,
                insights=parsed_result.get('insights', []),
                recommendations=parsed_result.get('recommendations', []),
                confidence_score=parsed_result.get('confidence', 0.8),
                data_summary=data,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            logger.error(f"OpenAI analysis failed: {e}")
            processing_time = (timezone.now() - start_time).total_seconds() * 1000
            
            return AIAnalysis(
                analysis_id=f"analysis_{int(start_time.timestamp())}",
                analysis_type=analysis_type,
                model_used=model,
                insights=[],
                recommendations=[],
                confidence_score=0.0,
                data_summary=data,
                processing_time_ms=processing_time,
                metadata={'error': str(e)}
            )
    
    async def natural_language_query(self, query: BackupQuery) -> QueryResult:
        """Process natural language backup query."""
        start_time = timezone.now()
        
        try:
            # Get relevant data for the query
            context_data = self._get_query_context(query)
            
            # Prepare query prompt
            prompt = self._prepare_query_prompt(query.question, context_data, query.context)
            
            # Call OpenAI API
            response = await openai.ChatCompletion.acreate(
                model=query.model.value,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_query_system_prompt()
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
            content = response.choices[0].message.content
            parsed_result = self._parse_query_response(content)
            
            # Calculate processing time
            processing_time = (timezone.now() - start_time).total_seconds() * 1000
            
            return QueryResult(
                query_id=query.query_id,
                answer=parsed_result.get('answer', ''),
                confidence=parsed_result.get('confidence', 0.8),
                supporting_data=parsed_result.get('supporting_data', {}),
                follow_up_questions=parsed_result.get('follow_up_questions', []),
                processing_time_ms=processing_time,
                model_used=query.model
            )
            
        except Exception as e:
            logger.error(f"Natural language query failed: {e}")
            processing_time = (timezone.now() - start_time).total_seconds() * 1000
            
            return QueryResult(
                query_id=query.query_id,
                answer=f"I apologize, but I encountered an error processing your query: {str(e)}",
                confidence=0.0,
                supporting_data={},
                follow_up_questions=[],
                processing_time_ms=processing_time,
                model_used=query.model
            )
    
    def _get_system_prompt(self, analysis_type: AnalysisType) -> str:
        """Get system prompt for analysis type."""
        prompts = {
            AnalysisType.BACKUP_PERFORMANCE: """
            You are a backup performance analysis expert. Analyze the provided backup data and provide:
            1. Key performance insights
            2. Performance bottlenecks
            3. Optimization recommendations
            4. Confidence score (0-1)
            
            Format your response as JSON with keys: insights, recommendations, confidence
            """,
            
            AnalysisType.BACKUP_HEALTH: """
            You are a backup health assessment expert. Analyze the backup system health and provide:
            1. Health status indicators
            2. Risk factors
            3. Improvement recommendations
            4. Confidence score (0-1)
            
            Format your response as JSON with keys: insights, recommendations, confidence
            """,
            
            AnalysisType.BACKUP_OPTIMIZATION: """
            You are a backup optimization specialist. Analyze the backup configuration and provide:
            1. Optimization opportunities
            2. Resource utilization insights
            3. Cost optimization suggestions
            4. Confidence score (0-1)
            
            Format your response as JSON with keys: insights, recommendations, confidence
            """,
            
            AnalysisType.BACKUP_STRATEGY: """
            You are a backup strategy consultant. Analyze the backup strategy and provide:
            1. Strategy effectiveness assessment
            2. Strategic recommendations
            3. Risk mitigation suggestions
            4. Confidence score (0-1)
            
            Format your response as JSON with keys: insights, recommendations, confidence
            """,
            
            AnalysisType.BACKUP_ANOMALY: """
            You are a backup anomaly detection expert. Analyze the backup patterns and provide:
            1. Anomaly identification
            2. Potential causes
            3. Investigation recommendations
            4. Confidence score (0-1)
            
            Format your response as JSON with keys: insights, recommendations, confidence
            """,
            
            AnalysisType.BACKUP_COMPLIANCE: """
            You are a backup compliance expert. Analyze backup compliance and provide:
            1. Compliance status
            2. Compliance gaps
            3. Remediation recommendations
            4. Confidence score (0-1)
            
            Format your response as JSON with keys: insights, recommendations, confidence
            """,
            
            AnalysisType.BACKUP_COST: """
            You are a backup cost optimization expert. Analyze backup costs and provide:
            1. Cost analysis insights
            2. Cost optimization opportunities
            3. ROI recommendations
            4. Confidence score (0-1)
            
            Format your response as JSON with keys: insights, recommendations, confidence
            """,
            
            AnalysisType.BACKUP_SECURITY: """
            You are a backup security expert. Analyze backup security and provide:
            1. Security assessment
            2. Vulnerability identification
            3. Security recommendations
            4. Confidence score (0-1)
            
            Format your response as JSON with keys: insights, recommendations, confidence
            """
        }
        
        return prompts.get(analysis_type, prompts[AnalysisType.BACKUP_PERFORMANCE])
    
    def _get_query_system_prompt(self) -> str:
        """Get system prompt for natural language queries."""
        return """
        You are a backup system expert assistant. Answer the user's question about their backup system
        based on the provided data. Provide:
        1. Clear, concise answer
        2. Supporting data/evidence
        3. Confidence score (0-1)
        4. Relevant follow-up questions
        
        Format your response as JSON with keys: answer, confidence, supporting_data, follow_up_questions
        """
    
    def _prepare_analysis_prompt(self, data: Dict[str, Any], analysis_type: AnalysisType) -> str:
        """Prepare analysis prompt with data."""
        data_summary = json.dumps(data, indent=2, default=str)
        
        return f"""
        Analyze the following backup system data for {analysis_type.value.replace('_', ' ')}:
        
        {data_summary}
        
        Please provide insights and recommendations based on this data.
        Focus on actionable recommendations that can improve the backup system.
        """
    
    def _prepare_query_prompt(self, question: str, context_data: Dict[str, Any], 
                            additional_context: Optional[str] = None) -> str:
        """Prepare natural language query prompt."""
        context_summary = json.dumps(context_data, indent=2, default=str)
        
        prompt = f"""
        Question: {question}
        
        Backup System Data:
        {context_summary}
        """
        
        if additional_context:
            prompt += f"\n\nAdditional Context: {additional_context}"
        
        prompt += "\n\nPlease answer the question based on the provided data."
        
        return prompt
    
    def _get_query_context(self, query: BackupQuery) -> Dict[str, Any]:
        """Get relevant context data for query."""
        context = {}
        
        # Get recent backup statistics
        recent_backups = Backup.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        )
        
        context['recent_backup_count'] = recent_backups.count()
        context['successful_backups'] = recent_backups.filter(status='completed').count()
        context['failed_backups'] = recent_backups.filter(status='failed').count()
        
        # Get backup types distribution
        backup_types = recent_backups.values('backup_type').annotate(
            count=Count('backup_type')
        )
        context['backup_types'] = list(backup_types)
        
        # Get storage distribution
        storage_types = recent_backups.values('storage_type').annotate(
            count=Count('storage_type')
        )
        context['storage_types'] = list(storage_types)
        
        # Get recent alerts
        recent_alerts = BackupAlert.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        )
        context['recent_alerts'] = recent_alerts.count()
        
        # Apply filters if provided
        if query.filters:
            filtered_backups = recent_backups
            for key, value in query.filters.items():
                if hasattr(Backup, key):
                    filtered_backups = filtered_backups.filter(**{key: value})
            
            context['filtered_backup_count'] = filtered_backups.count()
        
        return context
    
    def _parse_analysis_response(self, content: str, analysis_type: AnalysisType) -> Dict[str, Any]:
        """Parse OpenAI analysis response."""
        try:
            # Try to parse as JSON
            if content.strip().startswith('{'):
                return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Fallback parsing
        return {
            'insights': [f"Analysis completed for {analysis_type.value}"],
            'recommendations': ["Review the analysis results"],
            'confidence': 0.7
        }
    
    def _parse_query_response(self, content: str) -> Dict[str, Any]:
        """Parse OpenAI query response."""
        try:
            # Try to parse as JSON
            if content.strip().startswith('{'):
                return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Fallback parsing
        return {
            'answer': content,
            'confidence': 0.7,
            'supporting_data': {},
            'follow_up_questions': []
        }


class BackupAIAssistant:
    """AI-powered backup assistant."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = OpenAIClient(api_key)
        self.analytics = BackupAnalytics()
        self.monitor = BackupMonitor()
        self.cache_timeout = getattr(settings, 'BACKUP_AI_CACHE_TIMEOUT', 3600)  # 1 hour
    
    async def analyze_backup_performance(self, days: int = 30) -> AIAnalysis:
        """Analyze backup performance using AI."""
        # Get performance data
        performance_data = self._get_performance_data(days)
        
        return await self.client.analyze_backup_data(
            performance_data,
            AnalysisType.BACKUP_PERFORMANCE
        )
    
    async def analyze_backup_health(self, days: int = 30) -> AIAnalysis:
        """Analyze backup system health using AI."""
        # Get health data
        health_data = self._get_health_data(days)
        
        return await self.client.analyze_backup_data(
            health_data,
            AnalysisType.BACKUP_HEALTH
        )
    
    async def analyze_backup_optimization(self, days: int = 30) -> AIAnalysis:
        """Analyze backup optimization opportunities using AI."""
        # Get optimization data
        optimization_data = self._get_optimization_data(days)
        
        return await self.client.analyze_backup_data(
            optimization_data,
            AnalysisType.BACKUP_OPTIMIZATION
        )
    
    async def analyze_backup_strategy(self, days: int = 30) -> AIAnalysis:
        """Analyze backup strategy using AI."""
        # Get strategy data
        strategy_data = self._get_strategy_data(days)
        
        return await self.client.analyze_backup_data(
            strategy_data,
            AnalysisType.BACKUP_STRATEGY
        )
    
    async def detect_backup_anomalies(self, days: int = 30) -> AIAnalysis:
        """Detect backup anomalies using AI."""
        # Get anomaly detection data
        anomaly_data = self._get_anomaly_data(days)
        
        return await self.client.analyze_backup_data(
            anomaly_data,
            AnalysisType.BACKUP_ANOMALY
        )
    
    async def analyze_backup_compliance(self, days: int = 30) -> AIAnalysis:
        """Analyze backup compliance using AI."""
        # Get compliance data
        compliance_data = self._get_compliance_data(days)
        
        return await self.client.analyze_backup_data(
            compliance_data,
            AnalysisType.BACKUP_COMPLIANCE
        )
    
    async def analyze_backup_costs(self, days: int = 30) -> AIAnalysis:
        """Analyze backup costs using AI."""
        # Get cost data
        cost_data = self._get_cost_data(days)
        
        return await self.client.analyze_backup_data(
            cost_data,
            AnalysisType.BACKUP_COST
        )
    
    async def analyze_backup_security(self, days: int = 30) -> AIAnalysis:
        """Analyze backup security using AI."""
        # Get security data
        security_data = self._get_security_data(days)
        
        return await self.client.analyze_backup_data(
            security_data,
            AnalysisType.BACKUP_SECURITY
        )
    
    async def ask_backup_question(self, question: str, 
                                 context: Optional[str] = None,
                                 filters: Optional[Dict[str, Any]] = None,
                                 model: Optional[OpenAIModel] = None) -> QueryResult:
        """Ask a natural language question about backups."""
        query = BackupQuery(
            query_id=f"query_{int(timezone.now().timestamp())}",
            question=question,
            context=context,
            filters=filters or {},
            model=model or OpenAIModel.GPT_4O_MINI
        )
        
        return await self.client.natural_language_query(query)
    
    async def generate_backup_report(self, report_type: str, 
                                   days: int = 30,
                                   format: str = 'summary') -> Dict[str, Any]:
        """Generate AI-powered backup report."""
        # Get comprehensive data
        report_data = self._get_comprehensive_data(days)
        
        # Generate report using AI
        prompt = f"""
        Generate a comprehensive {report_type} backup report for the last {days} days.
        
        Data: {json.dumps(report_data, indent=2, default=str)}
        
        Format: {format}
        
        Include:
        1. Executive summary
        2. Key metrics
        3. Performance analysis
        4. Issues and recommendations
        5. Future outlook
        """
        
        try:
            response = await openai.ChatCompletion.acreate(
                model=OpenAIModel.GPT_4O.value,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a backup reporting expert. Generate comprehensive, actionable backup reports."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=3000,
                temperature=0.3
            )
            
            return {
                'report': response.choices[0].message.content,
                'generated_at': timezone.now().isoformat(),
                'data_period': f"{days} days",
                'report_type': report_type
            }
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return {
                'report': f"Error generating report: {str(e)}",
                'generated_at': timezone.now().isoformat(),
                'data_period': f"{days} days",
                'report_type': report_type
            }
    
    def _get_performance_data(self, days: int) -> Dict[str, Any]:
        """Get performance data for analysis."""
        cutoff_date = timezone.now() - timedelta(days=days)
        backups = Backup.objects.filter(created_at__gte=cutoff_date)
        
        return {
            'total_backups': backups.count(),
            'successful_backups': backups.filter(status='completed').count(),
            'failed_backups': backups.filter(status='failed').count(),
            'average_duration': backups.filter(status='completed').aggregate(
                avg_duration=Avg('duration')
            )['avg_duration'] or 0,
            'average_size': backups.filter(status='completed').aggregate(
                avg_size=Avg('file_size')
            )['avg_size'] or 0,
            'backup_types': list(backups.values('backup_type').annotate(
                count=Count('backup_type')
            )),
            'storage_types': list(backups.values('storage_type').annotate(
                count=Count('storage_type')
            )),
            'daily_backup_counts': list(
                backups.extra({'date': 'date(created_at)'}).values('date').annotate(
                    count=Count('id')
                ).order_by('date')
            )
        }
    
    def _get_health_data(self, days: int) -> Dict[str, Any]:
        """Get health data for analysis."""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return {
            'backup_success_rate': self._calculate_success_rate(days),
            'recent_alerts': BackupAlert.objects.filter(
                created_at__gte=cutoff_date
            ).count(),
            'alert_types': list(BackupAlert.objects.filter(
                created_at__gte=cutoff_date
            ).values('alert_type').annotate(count=Count('alert_type'))),
            'verification_results': list(BackupVerification.objects.filter(
                verified_at__gte=cutoff_date
            ).values('is_valid').annotate(count=Count('is_valid'))),
            'storage_health': self._get_storage_health(days),
            'schedule_health': self._get_schedule_health(days)
        }
    
    def _get_optimization_data(self, days: int) -> Dict[str, Any]:
        """Get optimization data for analysis."""
        cutoff_date = timezone.now() - timedelta(days=days)
        backups = Backup.objects.filter(created_at__gte=cutoff_date)
        
        return {
            'backup_sizes': list(backups.filter(status='completed').values(
                'file_size', 'backup_type'
            )),
            'compression_ratios': list(backups.filter(
                status='completed',
                compressed_size__isnull=False
            ).values('file_size', 'compressed_size')),
            'encryption_usage': backups.filter(is_encrypted=True).count(),
            'storage_utilization': self._get_storage_utilization(),
            'backup_frequency': self._get_backup_frequency(days),
            'resource_usage': self._get_resource_usage(days)
        }
    
    def _get_strategy_data(self, days: int) -> Dict[str, Any]:
        """Get strategy data for analysis."""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return {
            'backup_schedules': list(BackupSchedule.objects.filter(
                is_active=True
            ).values('frequency', 'backup_type', 'retention_days')),
            'retention_policies': self._get_retention_policies(days),
            'backup_types_distribution': list(Backup.objects.filter(
                created_at__gte=cutoff_date
            ).values('backup_type').annotate(count=Count('backup_type'))),
            'storage_distribution': list(Backup.objects.filter(
                created_at__gte=cutoff_date
            ).values('storage_type').annotate(count=Count('storage_type'))),
            'recovery_time_objectives': self._get_rto_metrics(days),
            'recovery_point_objectives': self._get_rpo_metrics(days)
        }
    
    def _get_anomaly_data(self, days: int) -> Dict[str, Any]:
        """Get anomaly detection data."""
        cutoff_date = timezone.now() - timedelta(days=days)
        backups = Backup.objects.filter(created_at__gte=cutoff_date)
        
        return {
            'backup_patterns': list(backups.extra({
                'hour': 'hour(created_at)',
                'day_of_week': 'extract(dow from created_at)'
            }).values('hour', 'day_of_week').annotate(
                count=Count('id')
            )),
            'size_anomalies': self._detect_size_anomalies(backups),
            'duration_anomalies': self._detect_duration_anomalies(backups),
            'failure_patterns': list(backups.filter(
                status='failed'
            ).extra({'hour': 'hour(created_at)'}).values('hour').annotate(
                count=Count('id')
            )),
            'storage_anomalies': self._detect_storage_anomalies(days)
        }
    
    def _get_compliance_data(self, days: int) -> Dict[str, Any]:
        """Get compliance data for analysis."""
        from .compliance import get_compliance_summary
        
        return {
            'compliance_summary': get_compliance_summary(),
            'recent_violations': self._get_recent_violations(days),
            'audit_trail': self._get_audit_trail(days),
            'retention_compliance': self._check_retention_compliance(days),
            'encryption_compliance': self._check_encryption_compliance(days)
        }
    
    def _get_cost_data(self, days: int) -> Dict[str, Any]:
        """Get cost data for analysis."""
        cutoff_date = timezone.now() - timedelta(days=days)
        backups = Backup.objects.filter(created_at__gte=cutoff_date)
        
        return {
            'storage_costs': self._calculate_storage_costs(backups),
            'transfer_costs': self._calculate_transfer_costs(backups),
            'compute_costs': self._calculate_compute_costs(days),
            'backup_sizes': list(backups.filter(status='completed').values('file_size')),
            'storage_type_costs': self._get_storage_type_costs(backups),
            'cost_trends': self._get_cost_trends(days)
        }
    
    def _get_security_data(self, days: int) -> Dict[str, Any]:
        """Get security data for analysis."""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return {
            'encryption_coverage': Backup.objects.filter(
                created_at__gte=cutoff_date,
                is_encrypted=True
            ).count(),
            'access_logs': self._get_access_logs(days),
            'security_events': self._get_security_events(days),
            'vulnerability_scan': self._get_vulnerability_scan(days),
            'authentication_events': self._get_authentication_events(days)
        }
    
    def _get_comprehensive_data(self, days: int) -> Dict[str, Any]:
        """Get comprehensive data for reporting."""
        return {
            'performance': self._get_performance_data(days),
            'health': self._get_health_data(days),
            'optimization': self._get_optimization_data(days),
            'strategy': self._get_strategy_data(days),
            'compliance': self._get_compliance_data(days),
            'cost': self._get_cost_data(days),
            'security': self._get_security_data(days)
        }
    
    # Helper methods for data collection
    def _calculate_success_rate(self, days: int) -> float:
        """Calculate backup success rate."""
        cutoff_date = timezone.now() - timedelta(days=days)
        total = Backup.objects.filter(created_at__gte=cutoff_date).count()
        successful = Backup.objects.filter(
            created_at__gte=cutoff_date,
            status='completed'
        ).count()
        
        return (successful / total * 100) if total > 0 else 0.0
    
    def _get_storage_health(self, days: int) -> Dict[str, Any]:
        """Get storage health metrics."""
        # Placeholder implementation
        return {
            'storage_locations': 5,
            'healthy_locations': 4,
            'total_capacity': '10TB',
            'used_capacity': '6TB',
            'utilization': 60.0
        }
    
    def _get_schedule_health(self, days: int) -> Dict[str, Any]:
        """Get schedule health metrics."""
        # Placeholder implementation
        return {
            'active_schedules': BackupSchedule.objects.filter(is_active=True).count(),
            'missed_schedules': 2,
            'delayed_schedules': 1,
            'success_rate': 95.0
        }
    
    def _get_storage_utilization(self) -> Dict[str, Any]:
        """Get storage utilization data."""
        # Placeholder implementation
        return {
            'local_storage': 70.0,
            's3_storage': 45.0,
            'azure_storage': 30.0,
            'average_utilization': 48.3
        }
    
    def _get_backup_frequency(self, days: int) -> Dict[str, Any]:
        """Get backup frequency data."""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return {
            'daily_backups': Backup.objects.filter(
                created_at__gte=cutoff_date,
                backup_schedule__frequency='daily'
            ).count(),
            'weekly_backups': Backup.objects.filter(
                created_at__gte=cutoff_date,
                backup_schedule__frequency='weekly'
            ).count(),
            'monthly_backups': Backup.objects.filter(
                created_at__gte=cutoff_date,
                backup_schedule__frequency='monthly'
            ).count()
        }
    
    def _get_resource_usage(self, days: int) -> Dict[str, Any]:
        """Get resource usage data."""
        # Placeholder implementation
        return {
            'cpu_usage': 45.0,
            'memory_usage': 60.0,
            'disk_io': 75.0,
            'network_io': 55.0
        }
    
    def _get_retention_policies(self, days: int) -> Dict[str, Any]:
        """Get retention policy data."""
        # Placeholder implementation
        return {
            'average_retention_days': 90,
            'expired_backups': 15,
            'compliance_rate': 95.0
        }
    
    def _get_rto_metrics(self, days: int) -> Dict[str, Any]:
        """Get Recovery Time Objective metrics."""
        # Placeholder implementation
        return {
            'target_rto': 4.0,  # hours
            'actual_rto': 3.5,
            'compliance_rate': 87.5
        }
    
    def _get_rpo_metrics(self, days: int) -> Dict[str, Any]:
        """Get Recovery Point Objective metrics."""
        # Placeholder implementation
        return {
            'target_rpo': 1.0,  # hours
            'actual_rpo': 0.5,
            'compliance_rate': 95.0
        }
    
    def _detect_size_anomalies(self, backups) -> List[Dict[str, Any]]:
        """Detect size anomalies in backups."""
        # Placeholder implementation
        return [
            {
                'backup_id': 'example_id',
                'anomaly_type': 'unusually_large',
                'expected_size': '1GB',
                'actual_size': '5GB'
            }
        ]
    
    def _detect_duration_anomalies(self, backups) -> List[Dict[str, Any]]:
        """Detect duration anomalies in backups."""
        # Placeholder implementation
        return [
            {
                'backup_id': 'example_id',
                'anomaly_type': 'unusually_slow',
                'expected_duration': 300,  # seconds
                'actual_duration': 1800
            }
        ]
    
    def _detect_storage_anomalies(self, days: int) -> List[Dict[str, Any]]:
        """Detect storage anomalies."""
        # Placeholder implementation
        return [
            {
                'storage_type': 's3',
                'anomaly_type': 'high_latency',
                'expected_latency': 100,  # ms
                'actual_latency': 500
            }
        ]
    
    def _get_recent_violations(self, days: int) -> List[Dict[str, Any]]:
        """Get recent compliance violations."""
        # Placeholder implementation
        return [
            {
                'violation_type': 'retention_policy',
                'severity': 'medium',
                'description': 'Backup retained longer than policy allows'
            }
        ]
    
    def _get_audit_trail(self, days: int) -> List[Dict[str, Any]]:
        """Get audit trail data."""
        cutoff_date = timezone.now() - timedelta(days=days)
        logs = BackupLog.objects.filter(created_at__gte=cutoff_date)
        
        return list(logs.values('action', 'category', 'level', 'created_at')[:100])
    
    def _check_retention_compliance(self, days: int) -> Dict[str, Any]:
        """Check retention compliance."""
        # Placeholder implementation
        return {
            'compliant_backups': 85,
            'non_compliant_backups': 5,
            'compliance_rate': 94.4
        }
    
    def _check_encryption_compliance(self, days: int) -> Dict[str, Any]:
        """Check encryption compliance."""
        cutoff_date = timezone.now() - timedelta(days=days)
        total = Backup.objects.filter(created_at__gte=cutoff_date).count()
        encrypted = Backup.objects.filter(
            created_at__gte=cutoff_date,
            is_encrypted=True
        ).count()
        
        return {
            'total_backups': total,
            'encrypted_backups': encrypted,
            'compliance_rate': (encrypted / total * 100) if total > 0 else 0.0
        }
    
    def _calculate_storage_costs(self, backups) -> Dict[str, Any]:
        """Calculate storage costs."""
        # Placeholder implementation
        return {
            'total_cost': 150.0,
            'cost_per_gb': 0.023,
            'monthly_trend': '+5.2%'
        }
    
    def _calculate_transfer_costs(self, backups) -> Dict[str, Any]:
        """Calculate transfer costs."""
        # Placeholder implementation
        return {
            'total_cost': 25.0,
            'cost_per_gb': 0.09,
            'monthly_trend': '+2.1%'
        }
    
    def _calculate_compute_costs(self, days: int) -> Dict[str, Any]:
        """Calculate compute costs."""
        # Placeholder implementation
        return {
            'total_cost': 75.0,
            'daily_average': 2.5,
            'monthly_trend': '+1.8%'
        }
    
    def _get_storage_type_costs(self, backups) -> List[Dict[str, Any]]:
        """Get costs by storage type."""
        # Placeholder implementation
        return [
            {'storage_type': 's3', 'cost': 80.0},
            {'storage_type': 'azure', 'cost': 45.0},
            {'storage_type': 'local', 'cost': 25.0}
        ]
    
    def _get_cost_trends(self, days: int) -> List[Dict[str, Any]]:
        """Get cost trends over time."""
        # Placeholder implementation
        return [
            {'date': '2024-01-01', 'cost': 200.0},
            {'date': '2024-01-02', 'cost': 205.0},
            {'date': '2024-01-03', 'cost': 198.0}
        ]
    
    def _get_access_logs(self, days: int) -> List[Dict[str, Any]]:
        """Get access logs."""
        # Placeholder implementation
        return [
            {'timestamp': '2024-01-01T10:00:00Z', 'action': 'backup_access', 'user': 'admin'},
            {'timestamp': '2024-01-01T11:00:00Z', 'action': 'backup_restore', 'user': 'user1'}
        ]
    
    def _get_security_events(self, days: int) -> List[Dict[str, Any]]:
        """Get security events."""
        # Placeholder implementation
        return [
            {'event_type': 'failed_login', 'severity': 'medium', 'count': 3},
            {'event_type': 'unauthorized_access', 'severity': 'high', 'count': 1}
        ]
    
    def _get_vulnerability_scan(self, days: int) -> Dict[str, Any]:
        """Get vulnerability scan results."""
        # Placeholder implementation
        return {
            'vulnerabilities_found': 2,
            'critical_vulnerabilities': 0,
            'scan_date': timezone.now() - timedelta(days=1)
        }
    
    def _get_authentication_events(self, days: int) -> List[Dict[str, Any]]:
        """Get authentication events."""
        # Placeholder implementation
        return [
            {'timestamp': '2024-01-01T10:00:00Z', 'event': 'login_success', 'user': 'admin'},
            {'timestamp': '2024-01-01T10:05:00Z', 'event': 'login_failure', 'user': 'unknown'}
        ]


# Global AI assistant instance
_ai_assistant: Optional[BackupAIAssistant] = None


def get_backup_ai_assistant() -> BackupAIAssistant:
    """Get the global backup AI assistant instance."""
    global _ai_assistant
    if _ai_assistant is None:
        _ai_assistant = BackupAIAssistant()
    return _ai_assistant


async def analyze_backup_performance(days: int = 30) -> AIAnalysis:
    """Analyze backup performance using AI."""
    assistant = get_backup_ai_assistant()
    return await assistant.analyze_backup_performance(days)


async def analyze_backup_health(days: int = 30) -> AIAnalysis:
    """Analyze backup system health using AI."""
    assistant = get_backup_ai_assistant()
    return await assistant.analyze_backup_health(days)


async def ask_backup_question(question: str, 
                             context: Optional[str] = None,
                             filters: Optional[Dict[str, Any]] = None) -> QueryResult:
    """Ask a natural language question about backups."""
    assistant = get_backup_ai_assistant()
    return await assistant.ask_backup_question(question, context, filters)


async def generate_backup_report(report_type: str = 'executive',
                               days: int = 30,
                               format: str = 'summary') -> Dict[str, Any]:
    """Generate AI-powered backup report."""
    assistant = get_backup_ai_assistant()
    return await assistant.generate_backup_report(report_type, days, format)
