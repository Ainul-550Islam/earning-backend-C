# =============================================================================
# fraud_detection/interactors.py
# =============================================================================
"""
Interactors Layer for Fraud Detection System.

Provides additional business logic layer that coordinates between
use cases, repositories, and external services for complex workflows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple

from django.utils import timezone
from django.db import transaction

from api.fraud_detection.use_cases import (
    MultiAccountDetectionUseCase, SuspiciousPatternDetectionUseCase,
    RiskAssessmentUseCase, get_use_case
)
from api.fraud_detection.repositories import (
    fraud_rule_repository, fraud_case_repository, fraud_alert_repository,
    fraud_risk_profile_repository
)
from api.fraud_detection.selectors import (
    fraud_rule_selector, fraud_case_selector, fraud_alert_selector,
    fraud_risk_profile_selector
)
from api.fraud_detection.sanctions import sanctions_manager, ip_reputation_checker
from api.fraud_detection.compliance import aml_compliance_manager, fraud_reporting_manager
from api.fraud_detection.encryption import encrypt_sensitive_data
from api.fraud_detection.choices import SeverityLevel, FraudAlertType
from api.fraud_detection.constants import RISK_THRESHOLDS, TIME_THRESHOLDS
from api.fraud_detection.exceptions import InteractorError, FraudDetectionError


logger = logging.getLogger(__name__)


class BaseInteractor:
    """
    Base interactor with common functionality.
    
    Provides coordination between use cases, repositories,
    and external services for complex business workflows.
    """
    
    def __init__(self):
        """Initialize interactor with dependencies."""
        self.multi_account_detector = get_use_case('multi_account_detection')
        self.pattern_detector = get_use_case('suspicious_pattern_detection')
        self.risk_assessor = get_use_case('risk_assessment')
        
        self.rule_repo = fraud_rule_repository
        self.case_repo = fraud_case_repository
        self.alert_repo = fraud_alert_repository
        self.risk_profile_repo = fraud_risk_profile_repository
        
        self.rule_selector = fraud_rule_selector
        self.case_selector = fraud_case_selector
        self.alert_selector = fraud_alert_selector
        self.risk_profile_selector = fraud_risk_profile_selector
    
    def execute(self, *args, **kwargs) -> Any:
        """
        Execute the interactor workflow.
        
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement execute method")


class FraudDetectionInteractor(BaseInteractor):
    """
    Main fraud detection workflow coordinator.
    
    Orchestrates multiple detection methods and provides
    comprehensive fraud analysis results.
    """
    
    def execute(self, user_id: Union[int, str], 
               transaction_data: Optional[Dict[str, Any]] = None,
               context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute comprehensive fraud detection workflow.
        
        Args:
            user_id: User ID to analyze
            transaction_data: Optional transaction data
            context: Additional context (IP, device info, etc.)
            
        Returns:
            Comprehensive fraud detection results
        """
        try:
            logger.info(f"Starting comprehensive fraud detection for user: {user_id}")
            
            # Initialize workflow context
            workflow_context = {
                'user_id': user_id,
                'transaction_data': transaction_data or {},
                'context': context or {},
                'start_time': timezone.now(),
                'detection_results': {}
            }
            
            # Step 1: Basic risk assessment
            basic_risk = self._perform_basic_risk_assessment(workflow_context)
            workflow_context['detection_results']['basic_risk'] = basic_risk
            
            # Step 2: Multi-account detection
            multi_account_result = self.multi_account_detector.execute(user_id, context)
            workflow_context['detection_results']['multi_account'] = multi_account_result
            
            # Step 3: Suspicious pattern detection
            activity_sequence = transaction_data.get('activity_sequence', []) if transaction_data else []
            pattern_result = self.pattern_detector.execute(user_id, activity_sequence)
            workflow_context['detection_results']['patterns'] = pattern_result
            
            # Step 4: Comprehensive risk assessment
            risk_result = self.risk_assessor.execute(user_id, transaction_data)
            workflow_context['detection_results']['risk_assessment'] = risk_result
            
            # Step 5: Sanctions and compliance screening
            compliance_result = self._perform_compliance_screening(workflow_context)
            workflow_context['detection_results']['compliance'] = compliance_result
            
            # Step 6: IP and device analysis
            device_analysis = self._perform_device_analysis(workflow_context)
            workflow_context['detection_results']['device_analysis'] = device_analysis
            
            # Step 7: Aggregate results and determine final action
            final_result = self._aggregate_detection_results(workflow_context)
            
            # Step 8: Create fraud case if necessary
            if final_result['action_required']:
                fraud_case = self._create_fraud_case(workflow_context, final_result)
                final_result['fraud_case_id'] = fraud_case.pk
            
            # Step 9: Send notifications if required
            if final_result['notification_required']:
                notifications = self._send_detection_notifications(workflow_context, final_result)
                final_result['notifications_sent'] = notifications
            
            # Step 10: Log detection event
            self._log_detection_event(workflow_context, final_result)
            
            final_result['workflow_duration'] = (timezone.now() - workflow_context['start_time']).total_seconds()
            final_result['workflow_timestamp'] = timezone.now().isoformat()
            
            logger.info(f"Fraud detection workflow completed for user: {user_id}, final_risk: {final_result['final_risk_score']}")
            return final_result
            
        except Exception as e:
            logger.error(f"Fraud detection workflow failed for user {user_id}: {e}")
            raise InteractorError(f"Fraud detection workflow failed: {e}")
    
    def _perform_basic_risk_assessment(self, workflow_context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform basic risk assessment."""
        user_id = workflow_context['user_id']
        
        # Get existing risk profile
        risk_profile = self.risk_profile_selector.get_profile_by_user(user_id)
        base_risk = risk_profile.risk_score if risk_profile else 0
        
        # Get recent alerts
        recent_alerts = self.alert_selector.get_recent_alerts(hours=24)
        user_alerts = [alert for alert in recent_alerts if str(alert.user_id) == str(user_id)]
        alert_risk = len(user_alerts) * 5
        
        basic_risk_score = min(base_risk + alert_risk, 100)
        
        return {
            'base_risk_score': base_risk,
            'recent_alerts_count': len(user_alerts),
            'alert_risk_contribution': alert_risk,
            'basic_risk_score': basic_risk_score,
            'risk_level': self._get_risk_level(basic_risk_score)
        }
    
    def _perform_compliance_screening(self, workflow_context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform sanctions and compliance screening."""
        transaction_data = workflow_context['transaction_data']
        
        # Sanctions screening
        sanctions_result = sanctions_manager.screen_transaction(transaction_data)
        
        # AML compliance check
        aml_result = aml_compliance_manager.monitor_transaction_limits(transaction_data)
        
        # IP reputation check
        ip_address = transaction_data.get('ip_address', '')
        ip_reputation = ip_reputation_checker.analyze_ip_geolocation(ip_address) if ip_address else {}
        
        compliance_risk = 0
        if not sanctions_result['passed']:
            compliance_risk += 50
        if not aml_result['compliant']:
            compliance_risk += 30
        if ip_reputation.get('risk_score', 0) >= 70:
            compliance_risk += 20
        
        return {
            'sanctions_screening': sanctions_result,
            'aml_compliance': aml_result,
            'ip_reputation': ip_reputation,
            'compliance_risk_score': compliance_risk,
            'compliance_passed': sanctions_result['passed'] and aml_result['compliant']
        }
    
    def _perform_device_analysis(self, workflow_context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform device and IP analysis."""
        context = workflow_context['context']
        user_id = workflow_context['user_id']
        
        # Device fingerprint analysis
        device_fingerprint = context.get('device_fingerprint', '')
        device_risk = 0
        
        if device_fingerprint:
            # Check if device is used by multiple users
            from api.fraud_detection.repositories import fraud_device_fingerprint_repository
            fingerprint_repo = fraud_device_fingerprint_repository
            
            fingerprint_record = fingerprint_repo.get_fingerprint_by_hash(device_fingerprint)
            if fingerprint_record and fingerprint_record.user_count > 1:
                device_risk += fingerprint_record.user_count * 10
        
        # Location analysis
        current_location = context.get('location', {})
        previous_locations = context.get('previous_locations', [])
        
        location_risk = 0
        if previous_locations and current_location:
            # Check for impossible travel (simplified)
            current_country = current_location.get('country', '')
            previous_countries = [loc.get('country', '') for loc in previous_locations]
            
            if current_country in previous_countries:
                location_risk += 5
            else:
                # New country - check if high-risk
                if sanctions_manager.is_country_high_risk(current_country):
                    location_risk += 25
        
        return {
            'device_fingerprint': device_fingerprint,
            'device_risk_score': device_risk,
            'location_analysis': {
                'current_location': current_location,
                'previous_locations': previous_locations,
                'location_risk_score': location_risk
            },
            'total_device_risk': device_risk + location_risk
        }
    
    def _aggregate_detection_results(self, workflow_context: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate all detection results into final assessment."""
        detection_results = workflow_context['detection_results']
        
        # Extract risk scores from all components
        risk_scores = {
            'basic_risk': detection_results['basic_risk']['basic_risk_score'],
            'multi_account': detection_results['multi_account']['risk_score'],
            'patterns': detection_results['patterns']['risk_score'],
            'risk_assessment': detection_results['risk_assessment']['current_risk_score'],
            'compliance': detection_results['compliance']['compliance_risk_score'],
            'device_analysis': detection_results['device_analysis']['total_device_risk']
        }
        
        # Calculate weighted final risk score
        weights = {
            'basic_risk': 0.15,
            'multi_account': 0.25,
            'patterns': 0.20,
            'risk_assessment': 0.20,
            'compliance': 0.15,
            'device_analysis': 0.05
        }
        
        final_risk_score = sum(
            risk_scores[component] * weights[component]
            for component in risk_scores
        )
        
        final_risk_score = min(int(final_risk_score), 100)
        
        # Determine action requirements
        action_required = final_risk_score >= RISK_THRESHOLDS['medium']
        notification_required = final_risk_score >= RISK_THRESHOLDS['high']
        immediate_action_required = final_risk_score >= RISK_THRESHOLDS['critical']
        
        # Generate recommendations
        recommendations = self._generate_final_recommendations(final_risk_score, detection_results)
        
        return {
            'final_risk_score': final_risk_score,
            'risk_level': self._get_risk_level(final_risk_score),
            'component_scores': risk_scores,
            'action_required': action_required,
            'notification_required': notification_required,
            'immediate_action_required': immediate_action_required,
            'recommendations': recommendations,
            'workflow_summary': self._generate_workflow_summary(detection_results)
        }
    
    def _create_fraud_case(self, workflow_context: Dict[str, Any], 
                          final_result: Dict[str, Any]) -> Any:
        """Create fraud case based on detection results."""
        user_id = workflow_context['user_id']
        detection_results = workflow_context['detection_results']
        
        case_data = {
            'user_id': user_id,
            'case_type': 'automated_detection',
            'risk_score': final_result['final_risk_score'],
            'status': 'open',
            'description': f"Automated fraud detection with risk score: {final_result['final_risk_score']}",
            'evidence_summary': detection_results,
            'severity': final_result['risk_level'],
            'detection_method': 'comprehensive_workflow'
        }
        
        return self.case_repo.create(**case_data)
    
    def _send_detection_notifications(self, workflow_context: Dict[str, Any], 
                                    final_result: Dict[str, Any]) -> List[str]:
        """Send detection notifications."""
        notifications_sent = []
        
        if final_result['notification_required']:
            # Create fraud report for notification
            case_data = {
                'case_id': final_result.get('fraud_case_id'),
                'user_id': workflow_context['user_id'],
                'severity': final_result['risk_level'],
                'risk_score': final_result['final_risk_score'],
                'summary': final_result['workflow_summary'],
                'evidence': workflow_context['detection_results']
            }
            
            try:
                fraud_report = fraud_reporting_manager.create_fraud_report(case_data)
                notifications_sent.extend(fraud_report.get('notifications_sent', []))
            except Exception as e:
                logger.error(f"Failed to create fraud report for notifications: {e}")
        
        return notifications_sent
    
    def _log_detection_event(self, workflow_context: Dict[str, Any], 
                           final_result: Dict[str, Any]):
        """Log detection event for audit trail."""
        log_data = {
            'event_type': 'fraud_detection_workflow',
            'user_id': workflow_context['user_id'],
            'risk_score': final_result['final_risk_score'],
            'risk_level': final_result['risk_level'],
            'action_required': final_result['action_required'],
            'workflow_duration': final_result.get('workflow_duration', 0),
            'detection_components': list(workflow_context['detection_results'].keys()),
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(f"Fraud detection event: {log_data}")
    
    def _generate_final_recommendations(self, final_risk_score: int, 
                                      detection_results: Dict[str, Any]) -> List[str]:
        """Generate final recommendations based on all detection results."""
        recommendations = []
        
        if final_risk_score >= RISK_THRESHOLDS['critical']:
            recommendations.extend([
                "Immediate account suspension recommended",
                "Freeze all related assets",
                "Contact law enforcement",
                "File SAR within 24 hours",
                "Manual investigation required"
            ])
        elif final_risk_score >= RISK_THRESHOLDS['high']:
            recommendations.extend([
                "Enhanced monitoring required",
                "Limit account functionality",
                "Request additional verification",
                "Consider SAR filing",
                "Review all recent transactions"
            ])
        elif final_risk_score >= RISK_THRESHOLDS['medium']:
            recommendations.extend([
                "Increased monitoring frequency",
                "Implement additional security checks",
                "Review account activity patterns",
                "Consider temporary restrictions"
            ])
        
        # Add specific recommendations based on detection components
        if detection_results['multi_account']['risk_score'] >= 70:
            recommendations.append("Investigate potential multi-account fraud")
        
        if not detection_results['compliance']['compliance_passed']:
            recommendations.append("Address compliance violations immediately")
        
        if detection_results['device_analysis']['total_device_risk'] >= 30:
            recommendations.append("Review device fingerprint patterns")
        
        return recommendations
    
    def _generate_workflow_summary(self, detection_results: Dict[str, Any]) -> str:
        """Generate workflow summary."""
        summary_parts = []
        
        # Basic risk
        basic_risk = detection_results['basic_risk']
        summary_parts.append(f"Base risk: {basic_risk['basic_risk_score']} ({basic_risk['risk_level']})")
        
        # Multi-account
        multi_account = detection_results['multi_account']
        summary_parts.append(f"Multi-account risk: {multi_account['risk_score']}")
        
        # Patterns
        patterns = detection_results['patterns']
        summary_parts.append(f"Pattern risk: {patterns['risk_score']}")
        
        # Compliance
        compliance = detection_results['compliance']
        compliance_status = "PASSED" if compliance['compliance_passed'] else "FAILED"
        summary_parts.append(f"Compliance: {compliance_status}")
        
        return " | ".join(summary_parts)
    
    def _get_risk_level(self, risk_score: int) -> str:
        """Get risk level from score."""
        if risk_score >= RISK_THRESHOLDS['critical']:
            return 'critical'
        elif risk_score >= RISK_THRESHOLDS['high']:
            return 'high'
        elif risk_score >= RISK_THRESHOLDS['medium']:
            return 'medium'
        else:
            return 'low'


class FraudCaseManagementInteractor(BaseInteractor):
    """
    Fraud case management workflow coordinator.
    
    Handles case lifecycle management, escalation,
    and resolution workflows.
    """
    
    def execute(self, case_id: Union[int, str], 
               action: str, 
               action_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute fraud case management workflow.
        
        Args:
            case_id: Fraud case ID
            action: Management action (assign, investigate, resolve, escalate)
            action_data: Additional action data
            
        Returns:
            Case management result
        """
        try:
            logger.info(f"Starting case management workflow for case: {case_id}, action: {action}")
            
            # Get fraud case
            fraud_case = self.case_selector.get_by_id(case_id)
            if not fraud_case:
                raise InteractorError(f"Fraud case not found: {case_id}")
            
            workflow_result = {
                'case_id': case_id,
                'action': action,
                'previous_status': fraud_case.status,
                'workflow_start': timezone.now(),
                'action_result': None,
                'notifications_sent': [],
                'next_steps': []
            }
            
            # Execute specific action
            if action == 'assign':
                workflow_result['action_result'] = self._assign_case(fraud_case, action_data)
            elif action == 'investigate':
                workflow_result['action_result'] = self._investigate_case(fraud_case, action_data)
            elif action == 'resolve':
                workflow_result['action_result'] = self._resolve_case(fraud_case, action_data)
            elif action == 'escalate':
                workflow_result['action_result'] = self._escalate_case(fraud_case, action_data)
            else:
                raise InteractorError(f"Unknown case action: {action}")
            
            # Update case status
            self._update_case_status(fraud_case, action, workflow_result['action_result'])
            
            # Send notifications
            notifications = self._send_case_notifications(fraud_case, action, workflow_result)
            workflow_result['notifications_sent'] = notifications
            
            # Generate next steps
            workflow_result['next_steps'] = self._generate_next_steps(fraud_case, action)
            
            workflow_result['workflow_duration'] = (timezone.now() - workflow_result['workflow_start']).total_seconds()
            workflow_result['workflow_timestamp'] = timezone.now().isoformat()
            
            logger.info(f"Case management workflow completed for case: {case_id}")
            return workflow_result
            
        except Exception as e:
            logger.error(f"Case management workflow failed for case {case_id}: {e}")
            raise InteractorError(f"Case management workflow failed: {e}")
    
    def _assign_case(self, fraud_case: Any, action_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Assign fraud case to investigator."""
        assigned_to = action_data.get('assigned_to') if action_data else None
        priority = action_data.get('priority', 'normal') if action_data else 'normal'
        
        if not assigned_to:
            raise InteractorError("assigned_to is required for case assignment")
        
        # Update case
        self.case_repo.update(fraud_case.pk, assigned_to=assigned_to, priority=priority)
        
        return {
            'assigned_to': assigned_to,
            'priority': priority,
            'assignment_timestamp': timezone.now().isoformat()
        }
    
    def _investigate_case(self, fraud_case: Any, action_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Investigate fraud case."""
        investigation_notes = action_data.get('notes', '') if action_data else ''
        evidence_collected = action_data.get('evidence', []) if action_data else []
        findings = action_data.get('findings', {}) if action_data else {}
        
        # Update case with investigation data
        update_data = {
            'status': 'investigating',
            'investigation_notes': investigation_notes,
            'investigation_evidence': evidence_collected,
            'investigation_findings': findings,
            'last_investigated': timezone.now()
        }
        
        self.case_repo.update(fraud_case.pk, **update_data)
        
        return {
            'status': 'investigating',
            'evidence_count': len(evidence_collected),
            'findings_summary': findings.get('summary', ''),
            'investigation_timestamp': timezone.now().isoformat()
        }
    
    def _resolve_case(self, fraud_case: Any, action_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Resolve fraud case."""
        resolution_type = action_data.get('resolution_type', 'closed') if action_data else 'closed'
        resolution_notes = action_data.get('resolution_notes', '') if action_data else ''
        outcome = action_data.get('outcome', 'unresolved') if action_data else 'unresolved'
        
        # Update case with resolution data
        update_data = {
            'status': 'resolved',
            'resolution_type': resolution_type,
            'resolution_notes': resolution_notes,
            'outcome': outcome,
            'resolved_at': timezone.now()
        }
        
        self.case_repo.update(fraud_case.pk, **update_data)
        
        return {
            'resolution_type': resolution_type,
            'outcome': outcome,
            'resolution_timestamp': timezone.now().isoformat()
        }
    
    def _escalate_case(self, fraud_case: Any, action_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Escalate fraud case."""
        escalation_reason = action_data.get('reason', 'high_risk') if action_data else 'high_risk'
        escalated_to = action_data.get('escalated_to') if action_data else None
        
        # Update case with escalation data
        update_data = {
            'status': 'escalated',
            'escalation_reason': escalation_reason,
            'escalated_at': timezone.now()
        }
        
        if escalated_to:
            update_data['escalated_to'] = escalated_to
        
        self.case_repo.update(fraud_case.pk, **update_data)
        
        return {
            'escalation_reason': escalation_reason,
            'escalated_to': escalated_to,
            'escalation_timestamp': timezone.now().isoformat()
        }
    
    def _update_case_status(self, fraud_case: Any, action: str, action_result: Dict[str, Any]):
        """Update case status based on action."""
        status_mapping = {
            'assign': 'assigned',
            'investigate': 'investigating',
            'resolve': 'resolved',
            'escalate': 'escalated'
        }
        
        new_status = status_mapping.get(action, fraud_case.status)
        if new_status != fraud_case.status:
            self.case_repo.update(fraud_case.pk, status=new_status)
    
    def _send_case_notifications(self, fraud_case: Any, action: str, 
                               workflow_result: Dict[str, Any]) -> List[str]:
        """Send case management notifications."""
        notifications_sent = []
        
        # Create notification data
        notification_data = {
            'case_id': fraud_case.pk,
            'user_id': fraud_case.user_id,
            'action': action,
            'action_result': workflow_result['action_result'],
            'severity': getattr(fraud_case, 'severity', 'medium'),
            'risk_score': getattr(fraud_case, 'risk_score', 0)
        }
        
        try:
            # Send fraud report notification
            fraud_report = fraud_reporting_manager.create_fraud_report(notification_data)
            notifications_sent.extend(fraud_report.get('notifications_sent', []))
        except Exception as e:
            logger.error(f"Failed to send case notification: {e}")
        
        return notifications_sent
    
    def _generate_next_steps(self, fraud_case: Any, action: str) -> List[str]:
        """Generate next steps for case management."""
        next_steps = []
        
        if action == 'assign':
            next_steps.extend([
                "Begin investigation within 24 hours",
                "Review case evidence and findings",
                "Document investigation progress"
            ])
        elif action == 'investigate':
            next_steps.extend([
                "Complete investigation analysis",
                "Determine resolution approach",
                "Prepare resolution report"
            ])
        elif action == 'resolve':
            next_steps.extend([
                "Document resolution details",
                "Update risk profiles if needed",
                "Close case in system"
            ])
        elif action == 'escalate':
            next_steps.extend([
                "Notify escalation recipients",
                "Provide case context to escalated team",
                "Monitor escalation progress"
            ])
        
        return next_steps


class RiskProfileUpdateInteractor(BaseInteractor):
    """
    Risk profile update workflow coordinator.
    
    Handles automated risk profile updates based on
    detection results and user behavior changes.
    """
    
    def execute(self, user_id: Union[int, str], 
               update_trigger: str,
               trigger_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute risk profile update workflow.
        
        Args:
            user_id: User ID to update
            update_trigger: Trigger for update (fraud_detection, transaction, manual)
            trigger_data: Additional trigger data
            
        Returns:
            Risk profile update result
        """
        try:
            logger.info(f"Starting risk profile update for user: {user_id}, trigger: {update_trigger}")
            
            # Get current risk profile
            current_profile = self.risk_profile_selector.get_profile_by_user(user_id)
            current_risk = current_profile.risk_score if current_profile else 0
            
            workflow_result = {
                'user_id': user_id,
                'update_trigger': update_trigger,
                'previous_risk_score': current_risk,
                'workflow_start': timezone.now(),
                'risk_analysis': {},
                'update_result': None,
                'notifications_sent': []
            }
            
            # Perform risk analysis based on trigger
            if update_trigger == 'fraud_detection':
                workflow_result['risk_analysis'] = self._analyze_fraud_detection_risk(trigger_data)
            elif update_trigger == 'transaction':
                workflow_result['risk_analysis'] = self._analyze_transaction_risk(trigger_data)
            elif update_trigger == 'manual':
                workflow_result['risk_analysis'] = self._analyze_manual_risk(trigger_data)
            else:
                raise InteractorError(f"Unknown update trigger: {update_trigger}")
            
            # Calculate new risk score
            new_risk_score = self._calculate_new_risk_score(current_risk, workflow_result['risk_analysis'])
            
            # Update risk profile
            update_result = self._update_risk_profile(user_id, new_risk_score, update_trigger, workflow_result['risk_analysis'])
            workflow_result['update_result'] = update_result
            
            # Send notifications if significant change
            if abs(new_risk_score - current_risk) >= 20:
                notifications = self._send_risk_update_notifications(user_id, current_risk, new_risk_score, update_trigger)
                workflow_result['notifications_sent'] = notifications
            
            workflow_result['workflow_duration'] = (timezone.now() - workflow_result['workflow_start']).total_seconds()
            workflow_result['workflow_timestamp'] = timezone.now().isoformat()
            
            logger.info(f"Risk profile update completed for user: {user_id}, new_risk: {new_risk_score}")
            return workflow_result
            
        except Exception as e:
            logger.error(f"Risk profile update failed for user {user_id}: {e}")
            raise InteractorError(f"Risk profile update failed: {e}")
    
    def _analyze_fraud_detection_risk(self, trigger_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze risk from fraud detection results."""
        if not trigger_data:
            return {'risk_contribution': 0, 'analysis_type': 'fraud_detection'}
        
        detection_risk = trigger_data.get('final_risk_score', 0)
        risk_factors = trigger_data.get('component_scores', {})
        
        return {
            'risk_contribution': detection_risk * 0.7,  # Weight detection results heavily
            'analysis_type': 'fraud_detection',
            'detection_risk_score': detection_risk,
            'risk_factors': risk_factors
        }
    
    def _analyze_transaction_risk(self, trigger_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze risk from transaction data."""
        if not trigger_data:
            return {'risk_contribution': 0, 'analysis_type': 'transaction'}
        
        amount = trigger_data.get('amount', 0)
        risk_score = 0
        
        # Amount-based risk
        if amount >= 10000:
            risk_score += 30
        elif amount >= 5000:
            risk_score += 20
        elif amount >= 1000:
            risk_score += 10
        
        # Other transaction factors
        country = trigger_data.get('country', '')
        if sanctions_manager.is_country_high_risk(country):
            risk_score += 25
        
        return {
            'risk_contribution': risk_score,
            'analysis_type': 'transaction',
            'transaction_amount': amount,
            'country_risk': sanctions_manager.is_country_high_risk(country)
        }
    
    def _analyze_manual_risk(self, trigger_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze risk from manual assessment."""
        if not trigger_data:
            return {'risk_contribution': 0, 'analysis_type': 'manual'}
        
        manual_risk = trigger_data.get('manual_risk_score', 0)
        reason = trigger_data.get('reason', 'manual_review')
        
        return {
            'risk_contribution': manual_risk,
            'analysis_type': 'manual',
            'manual_risk_score': manual_risk,
            'reason': reason
        }
    
    def _calculate_new_risk_score(self, current_risk: int, risk_analysis: Dict[str, Any]) -> int:
        """Calculate new risk score based on analysis."""
        risk_contribution = risk_analysis.get('risk_contribution', 0)
        
        # Weighted average of current risk and new contribution
        new_risk = (current_risk * 0.6) + (risk_contribution * 0.4)
        
        return min(int(new_risk), 100)
    
    def _update_risk_profile(self, user_id: Union[int, str], new_risk_score: int,
                           update_trigger: str, risk_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Update risk profile with new score."""
        update_reason = f"Risk profile update via {update_trigger}"
        
        updated_profile = self.risk_profile_repo.update_risk_score(user_id, new_risk_score, update_reason)
        
        return {
            'new_risk_score': new_risk_score,
            'previous_risk_score': self.risk_profile_selector.get_profile_by_user(user_id).risk_score if self.risk_profile_selector.get_profile_by_user(user_id) else 0,
            'update_reason': update_reason,
            'risk_analysis': risk_analysis,
            'update_timestamp': timezone.now().isoformat()
        }
    
    def _send_risk_update_notifications(self, user_id: Union[int, str], 
                                       previous_risk: int, new_risk: int,
                                       update_trigger: str) -> List[str]:
        """Send risk update notifications."""
        notifications_sent = []
        
        # Create notification data
        notification_data = {
            'user_id': user_id,
            'severity': 'high' if new_risk >= 70 else 'medium',
            'risk_score': new_risk,
            'summary': f"Risk score updated from {previous_risk} to {new_risk} via {update_trigger}",
            'evidence': {'previous_risk': previous_risk, 'new_risk': new_risk, 'trigger': update_trigger}
        }
        
        try:
            # Send fraud report notification
            fraud_report = fraud_reporting_manager.create_fraud_report(notification_data)
            notifications_sent.extend(fraud_report.get('notifications_sent', []))
        except Exception as e:
            logger.error(f"Failed to send risk update notification: {e}")
        
        return notifications_sent


# Interactor instances for dependency injection
fraud_detection_interactor = FraudDetectionInteractor()
fraud_case_management_interactor = FraudCaseManagementInteractor()
risk_profile_update_interactor = RiskProfileUpdateInteractor()


def get_interactor(interactor_name: str) -> BaseInteractor:
    """
    Get interactor instance by name.
    
    Args:
        interactor_name: Interactor name
        
    Returns:
        Interactor instance
        
    Raises:
        InteractorError: If interactor not found
    """
    interactor_map = {
        'fraud_detection': fraud_detection_interactor,
        'fraud_case_management': fraud_case_management_interactor,
        'risk_profile_update': risk_profile_update_interactor,
    }
    
    interactor = interactor_map.get(interactor_name.lower())
    if not interactor:
        raise InteractorError(f"Interactor not found: {interactor_name}")
    
    return interactor
