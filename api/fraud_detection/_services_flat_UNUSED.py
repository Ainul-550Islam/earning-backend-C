# =============================================================================
# fraud_detection/services.py
# =============================================================================
"""
Service Layer for Fraud Detection System.

Provides high-level business logic services that coordinate
between repositories, use cases, and external systems.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod

from django.conf import settings
from django.utils import timezone
from django.db import transaction

from api.fraud_detection.interactors import get_interactor
from api.fraud_detection.repositories import fraud_case_repository, fraud_alert_repository
from api.fraud_detection.selectors import fraud_case_selector, fraud_alert_selector
from api.fraud_detection.webhooks import threat_intelligence_aggregator
from api.fraud_detection.sanctions import sanctions_manager
from api.fraud_detection.compliance import aml_compliance_manager
from api.fraud_detection.monitoring import record_fraud_metric
from api.fraud_detection.analytics import get_fraud_analytics
from api.fraud_detection.exceptions import ServiceError, FraudDetectionError


logger = logging.getLogger(__name__)


@dataclass
class ServiceResult:
    """Data class for service operation results."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    warnings: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()


class BaseService(ABC):
    """
    Abstract base class for fraud detection services.
    
    Provides common functionality for all service classes.
    """
    
    def __init__(self):
        """Initialize base service."""
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _create_result(self, success: bool, data: Optional[Dict[str, Any]] = None,
                       error: Optional[str] = None, warnings: Optional[List[str]] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> ServiceResult:
        """Create service result."""
        return ServiceResult(
            success=success,
            data=data,
            error=error,
            warnings=warnings,
            metadata=metadata
        )
    
    def _log_service_call(self, operation: str, **kwargs):
        """Log service method call."""
        self.logger.info(f"Service call: {operation} - {kwargs}")
    
    def _handle_exception(self, operation: str, exception: Exception) -> ServiceResult:
        """Handle service exceptions."""
        self.logger.error(f"Service error in {operation}: {exception}")
        return self._create_result(
            success=False,
            error=str(exception)
        )


class FraudDetectionService(BaseService):
    """
    Main fraud detection service.
    
    Provides high-level fraud detection operations
    coordinating multiple components.
    """
    
    def __init__(self):
        """Initialize fraud detection service."""
        super().__init__()
        self.fraud_detector = get_interactor('fraud_detection')
        self.case_manager = get_interactor('fraud_case_management')
        self.threat_intelligence = threat_intelligence_aggregator
        self.sanctions = sanctions_manager
        self.compliance = aml_compliance_manager
    
    def analyze_transaction(self, user_id: Union[int, str], 
                          transaction_data: Dict[str, Any],
                          context: Optional[Dict[str, Any]] = None) -> ServiceResult:
        """
        Analyze transaction for fraud.
        
        Args:
            user_id: User ID
            transaction_data: Transaction data
            context: Additional context
            
        Returns:
            Service result with analysis data
        """
        try:
            self._log_service_call('analyze_transaction', user_id=user_id)
            
            # Execute comprehensive fraud detection
            detection_result = self.fraud_detector.execute(user_id, transaction_data, context)
            
            # Record metrics
            record_fraud_metric('transaction_analyzed', 1, {
                'user_id': user_id,
                'risk_score': detection_result.get('final_risk_score', 0),
                'action_required': detection_result.get('action_required', False)
            })
            
            return self._create_result(
                success=True,
                data=detection_result,
                metadata={
                    'operation': 'transaction_analysis',
                    'user_id': user_id
                }
            )
            
        except Exception as e:
            return self._handle_exception('analyze_transaction', e)
    
    def create_fraud_case(self, user_id: Union[int, str], 
                         case_data: Dict[str, Any],
                         auto_assign: bool = True) -> ServiceResult:
        """
        Create fraud case.
        
        Args:
            user_id: User ID
            case_data: Case data
            auto_assign: Auto-assign case
            
        Returns:
            Service result with case data
        """
        try:
            self._log_service_call('create_fraud_case', user_id=user_id)
            
            with transaction.atomic():
                # Create case
                case = fraud_case_repository.create(
                    user_id=user_id,
                    case_type=case_data.get('case_type', 'manual'),
                    risk_score=case_data.get('risk_score', 0),
                    status='open',
                    description=case_data.get('description', ''),
                    evidence_summary=case_data.get('evidence', {}),
                    severity=case_data.get('severity', 'medium'),
                    detection_method=case_data.get('detection_method', 'manual')
                )
                
                # Auto-assign if requested
                if auto_assign:
                    available_analysts = self._get_available_analysts()
                    if available_analysts:
                        assigned_to = available_analysts[0]
                        fraud_case_repository.update(case.pk, assigned_to=assigned_to)
                
                # Send notification
                from api.fraud_detection.notifications_push import send_case_notification
                send_case_notification({
                    'case_id': case.pk,
                    'user_id': user_id,
                    'risk_score': case.risk_score,
                    'severity': case.severity
                }, 'created')
                
                record_fraud_metric('fraud_case_created', 1, {
                    'case_id': case.pk,
                    'user_id': user_id,
                    'risk_score': case.risk_score
                })
                
                return self._create_result(
                    success=True,
                    data={'case_id': case.pk, 'status': case.status},
                    metadata={'operation': 'fraud_case_created'}
                )
                
        except Exception as e:
            return self._handle_exception('create_fraud_case', e)
    
    def escalate_case(self, case_id: Union[int, str], 
                    escalation_reason: str,
                    escalated_to: Optional[Union[int, str]] = None) -> ServiceResult:
        """
        Escalate fraud case.
        
        Args:
            case_id: Case ID
            escalation_reason: Reason for escalation
            escalated_to: User to escalate to
            
        Returns:
            Service result
        """
        try:
            self._log_service_call('escalate_case', case_id=case_id)
            
            # Get case
            case = fraud_case_selector.get_by_id(case_id)
            if not case:
                return self._create_result(
                    success=False,
                    error=f"Case not found: {case_id}"
                )
            
            # Escalate case
            management_result = self.case_manager.execute(
                case_id, 'escalate', {'reason': escalation_reason, 'escalated_to': escalated_to}
            )
            
            # Send notification
            from api.fraud_detection.notifications_push import send_case_notification
            send_case_notification({
                'case_id': case_id,
                'user_id': case.user_id,
                'risk_score': case.risk_score,
                'severity': case.severity
            }, 'escalated')
            
            record_fraud_metric('fraud_case_escalated', 1, {
                'case_id': case_id,
                'user_id': case.user_id,
                'reason': escalation_reason
            })
            
            return self._create_result(
                success=True,
                data=management_result,
                metadata={'operation': 'case_escalated'}
            )
            
        except Exception as e:
            return self._handle_exception('escalate_case', e)
    
    def _get_available_analysts(self) -> List[Union[int, str]]:
        """Get available fraud analysts."""
        # Simplified - would query actual user database
        return [1, 2, 3]  # Placeholder analyst IDs


class RiskAssessmentService(BaseService):
    """
    Risk assessment service.
    
    Provides comprehensive risk assessment and profile management.
    """
    
    def __init__(self):
        """Initialize risk assessment service."""
        super().__init__()
        self.risk_updater = get_interactor('risk_profile_update')
        self.analytics = get_fraud_analytics()
    
    def update_user_risk_profile(self, user_id: Union[int, str], 
                                 update_trigger: str,
                                 trigger_data: Optional[Dict[str, Any]] = None) -> ServiceResult:
        """
        Update user risk profile.
        
        Args:
            user_id: User ID
            update_trigger: Trigger for update
            trigger_data: Additional trigger data
            
        Returns:
            Service result
        """
        try:
            self._log_service_call('update_user_risk_profile', user_id=user_id)
            
            # Update risk profile
            update_result = self.risk_updater.execute(user_id, update_trigger, trigger_data)
            
            # Record metric
            record_fraud_metric('risk_profile_updated', 1, {
                'user_id': user_id,
                'trigger': update_trigger,
                'new_score': update_result.get('update_result', {}).get('new_risk_score', 0)
            })
            
            return self._create_result(
                success=True,
                data=update_result,
                metadata={'operation': 'risk_profile_updated'}
            )
            
        except Exception as e:
            return self._handle_exception('update_user_risk_profile', e)
    
    def get_user_risk_summary(self, user_id: Union[int, str]) -> ServiceResult:
        """
        Get comprehensive risk summary for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Service result with risk summary
        """
        try:
            self._log_service_call('get_user_risk_summary', user_id=user_id)
            
            # Get risk profile
            from api.fraud_detection.selectors import fraud_risk_profile_selector
            profile = fraud_risk_profile_selector.get_profile_by_user(user_id)
            
            # Get recent cases and alerts
            recent_cases = fraud_case_selector.get_cases_by_user(user_id, limit=10)
            recent_alerts = fraud_alert_selector.get_alerts_by_user(user_id, limit=20)
            
            # Get analytics data
            overview_data = self.analytics.get_fraud_overview(period_days=30)
            
            summary_data = {
                'user_id': user_id,
                'current_risk_score': profile.risk_score if profile else 0,
                'risk_level': self._get_risk_level(profile.risk_score if profile else 0),
                'recent_cases_count': len(recent_cases),
                'recent_alerts_count': len(recent_alerts),
                'last_updated': profile.last_updated.isoformat() if profile else None,
                'trend_data': overview_data.get('trend_analysis', {}),
                'recommendations': self._get_risk_recommendations(profile.risk_score if profile else 0)
            }
            
            return self._create_result(
                success=True,
                data=summary_data,
                metadata={'operation': 'risk_summary_generated'}
            )
            
        except Exception as e:
            return self._handle_exception('get_user_risk_summary', e)
    
    def batch_assess_risk(self, user_ids: List[Union[int, str]]) -> ServiceResult:
        """
        Batch assess risk for multiple users.
        
        Args:
            user_ids: List of user IDs
            
        Returns:
            Service result with batch assessment data
        """
        try:
            self._log_service_call('batch_assess_risk', user_count=len(user_ids))
            
            # Submit batch job
            from api.fraud_detection.background_jobs import submit_batch_risk_assessment
            job = submit_batch_risk_assessment(user_ids, priority='low')
            
            return self._create_result(
                success=True,
                data={
                    'job_id': job.id,
                    'user_count': len(user_ids),
                    'status': job.status
                },
                metadata={'operation': 'batch_risk_assessment'}
            )
            
        except Exception as e:
            return self._handle_exception('batch_assess_risk', e)
    
    def _get_risk_level(self, risk_score: int) -> str:
        """Get risk level from score."""
        if risk_score >= 80:
            return 'critical'
        elif risk_score >= 60:
            return 'high'
        elif risk_score >= 40:
            return 'medium'
        else:
            return 'low'
    
    def _get_risk_recommendations(self, risk_score: int) -> List[str]:
        """Get risk-based recommendations."""
        recommendations = []
        
        if risk_score >= 80:
            recommendations.extend([
                "Immediate account suspension recommended",
                "Manual investigation required",
                "Consider SAR filing"
            ])
        elif risk_score >= 60:
            recommendations.extend([
                "Enhanced monitoring required",
                "Limit account functionality",
                "Request additional verification"
            ])
        elif risk_score >= 40:
            recommendations.extend([
                "Monitor account activity",
                "Review recent transactions"
            ])
        
        return recommendations


class ComplianceService(BaseService):
    """
    Compliance service for fraud detection.
    
    Handles AML compliance, reporting, and regulatory requirements.
    """
    
    def __init__(self):
        """Initialize compliance service."""
        super().__init__()
        self.aml_manager = aml_compliance_manager
        self.reporting_manager = fraud_reporting_manager
    
    def check_transaction_compliance(self, transaction_data: Dict[str, Any]) -> ServiceResult:
        """
        Check transaction compliance.
        
        Args:
            transaction_data: Transaction data
            
        Returns:
            Service result with compliance data
        """
        try:
            self._log_service_call('check_transaction_compliance')
            
            # Check AML compliance
            aml_result = self.aml_manager.monitor_transaction_limits(transaction_data)
            
            # Check sanctions
            sanctions_result = self.sanctions_manager.screen_transaction(transaction_data)
            
            # Combine results
            compliance_data = {
                'aml_compliance': aml_result,
                'sanctions_screening': sanctions_result,
                'overall_compliant': aml_result['compliant'] and sanctions_result['passed'],
                'requires_action': not (aml_result['compliant'] and sanctions_result['passed']),
                'recommendations': []
            }
            
            if not compliance_data['overall_compliant']:
                if not aml_result['compliant']:
                    compliance_data['recommendations'].extend(aml_result.get('recommendations', []))
                if not sanctions_result['passed']:
                    compliance_data['recommendations'].extend(sanctions_result.get('recommendations', []))
            
            record_fraud_metric('compliance_check', 1, {
                'compliant': compliance_data['overall_compliant'],
                'aml_compliant': aml_result['compliant'],
                'sanctions_passed': sanctions_result['passed']
            })
            
            return self._create_result(
                success=True,
                data=compliance_data,
                metadata={'operation': 'compliance_check'}
            )
            
        except Exception as e:
            return self._handle_exception('check_transaction_compliance', e)
    
    def generate_compliance_report(self, report_type: str, 
                                 period_days: int = 30) -> ServiceResult:
        """
        Generate compliance report.
        
        Args:
            report_type: Type of report
            period_days: Analysis period
            
        Returns:
            Service result with report data
        """
        try:
            self._log_service_call('generate_compliance_report', report_type=report_type)
            
            # Submit report generation job
            from api.fraud_detection.background_jobs import submit_compliance_report_job
            job = submit_compliance_report_job(report_type, period_days, priority='low')
            
            return self._create_result(
                success=True,
                data={
                    'job_id': job.id,
                    'report_type': report_type,
                    'period_days': period_days,
                    'status': job.status
                },
                metadata={'operation': 'compliance_report_generated'}
            )
            
        except Exception as e:
            return self._handle_exception('generate_compliance_report', e)
    
    def file_sar_report(self, case_id: Union[int, str], 
                        sar_data: Dict[str, Any]) -> ServiceResult:
        """
        File Suspicious Activity Report.
        
        Args:
            case_id: Case ID
            sar_data: SAR data
            
        Returns:
            Service result
        """
        try:
            self._log_service_call('file_sar_report', case_id=case_id)
            
            # Create SAR report
            sar_report = self.reporting_manager.create_sar_report(case_id, sar_data)
            
            record_fraud_metric('sar_filed', 1, {
                'case_id': case_id,
                'report_id': sar_report.get('report_id')
            })
            
            return self._create_result(
                success=True,
                data=sar_report,
                metadata={'operation': 'sar_filed'}
            )
            
        except Exception as e:
            return self._handle_exception('file_sar_report', e)


class ThreatIntelligenceService(BaseService):
    """
    Threat intelligence service.
    
    Provides external threat data integration and analysis.
    """
    
    def __init__(self):
        """Initialize threat intelligence service."""
        super().__init__()
        self.threat_aggregator = threat_intelligence_aggregator
    
    def check_ip_reputation(self, ip_address: str, 
                           additional_data: Optional[Dict[str, Any]] = None) -> ServiceResult:
        """
        Check IP reputation.
        
        Args:
            ip_address: IP address
            additional_data: Additional context
            
        Returns:
            Service result with reputation data
        """
        try:
            self._log_service_call('check_ip_reputation', ip_address=ip_address)
            
            # Get aggregated reputation data
            reputation_data = self.threat_aggregator.aggregate_ip_reputation(ip_address, additional_data)
            
            record_fraud_metric('ip_reputation_checked', 1, {
                'ip_address': ip_address,
                'risk_score': reputation_data.get('aggregated_reputation', {}).get('overall_score', 0)
            })
            
            return self._create_result(
                success=True,
                data=reputation_data,
                metadata={'operation': 'ip_reputation_checked'}
            )
            
        except Exception as e:
            return self._handle_exception('check_ip_reputation', e)
    
    def check_email_reputation(self, email_address: str, 
                             additional_data: Optional[Dict[str, Any]] = None) -> ServiceResult:
        """
        Check email reputation.
        
        Args:
            email_address: Email address
            additional_data: Additional context
            
        Returns:
            Service result with reputation data
        """
        try:
            self._log_service_call('check_email_reputation', email_address=email_address)
            
            # Get aggregated reputation data
            reputation_data = self.threat_aggregator.aggregate_email_reputation(email_address, additional_data)
            
            record_fraud_metric('email_reputation_checked', 1, {
                'email_address': email_address,
                'risk_score': reputation_data.get('aggregated_reputation', {}).get('overall_score', 0)
            })
            
            return self._create_result(
                success=True,
                data=reputation_data,
                metadata={'operation': 'email_reputation_checked'}
            )
            
        except Exception as e:
            return self._handle_exception('check_email_reputation', e)
    
    def update_threat_intelligence(self) -> ServiceResult:
        """
        Update threat intelligence data.
        
        Returns:
            Service result
        """
        try:
            self._log_service_call('update_threat_intelligence')
            
            # Submit background job
            from api.fraud_detection.background_jobs import update_external_threat_intelligence
            job = update_external_threat_intelligence.delay()
            
            return self._create_result(
                success=True,
                data={'job_id': job.id, 'status': job.status},
                metadata={'operation': 'threat_intelligence_updated'}
            )
            
        except Exception as e:
            return self._handle_exception('update_threat_intelligence', e)


# Service factory for dependency injection
class ServiceFactory:
    """Factory for creating service instances."""
    
    _services = {}
    
    @classmethod
    def get_service(cls, service_name: str):
        """Get service instance."""
        if service_name not in cls._services:
            if service_name == 'fraud_detection':
                cls._services[service_name] = FraudDetectionService()
            elif service_name == 'risk_assessment':
                cls._services[service_name] = RiskAssessmentService()
            elif service_name == 'compliance':
                cls._services[service_name] = ComplianceService()
            elif service_name == 'threat_intelligence':
                cls._services[service_name] = ThreatIntelligenceService()
            else:
                raise ServiceError(f"Unknown service: {service_name}")
        
        return cls._services[service_name]
    
    @classmethod
    def create_fraud_detection_service(cls) -> FraudDetectionService:
        """Create fraud detection service."""
        return FraudDetectionService()
    
    @classmethod
    def create_risk_assessment_service(cls) -> RiskAssessmentService:
        """Create risk assessment service."""
        return RiskAssessmentService()
    
    @classmethod
    def create_compliance_service(cls) -> ComplianceService:
        """Create compliance service."""
        return ComplianceService()
    
    @classmethod
    def create_threat_intelligence_service(cls) -> ThreatIntelligenceService:
        """Create threat intelligence service."""
        return ThreatIntelligenceService()


# Global service instances
fraud_detection_service = ServiceFactory.create_fraud_detection_service()
risk_assessment_service = ServiceFactory.create_risk_assessment_service()
compliance_service = ServiceFactory.create_compliance_service()
threat_intelligence_service = ServiceFactory.create_threat_intelligence_service()


# Convenience functions
def analyze_transaction_for_fraud(user_id: Union[int, str], 
                                 transaction_data: Dict[str, Any],
                                 context: Optional[Dict[str, Any]] = None) -> ServiceResult:
    """
    Convenience function for transaction analysis.
    
    Args:
        user_id: User ID
        transaction_data: Transaction data
        context: Additional context
        
    Returns:
        Service result
    """
    return fraud_detection_service.analyze_transaction(user_id, transaction_data, context)


def update_user_risk(user_id: Union[int, str], 
                        trigger: str,
                        data: Optional[Dict[str, Any]] = None) -> ServiceResult:
    """
    Convenience function for risk profile update.
    
    Args:
        user_id: User ID
        trigger: Update trigger
        data: Trigger data
        
    Returns:
        Service result
    """
    return risk_assessment_service.update_user_risk_profile(user_id, trigger, data)


def check_transaction_compliance(transaction_data: Dict[str, Any]) -> ServiceResult:
    """
    Convenience function for compliance check.
    
    Args:
        transaction_data: Transaction data
        
    Returns:
        Service result
    """
    return compliance_service.check_transaction_compliance(transaction_data)


def check_ip_threat_reputation(ip_address: str, 
                               data: Optional[Dict[str, Any]] = None) -> ServiceResult:
    """
    Convenience function for IP reputation check.
    
    Args:
        ip_address: IP address
        data: Additional data
        
    Returns:
        Service result
    """
    return threat_intelligence_service.check_ip_reputation(ip_address, data)
