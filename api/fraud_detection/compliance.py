# =============================================================================
# fraud_detection/compliance.py
# =============================================================================
"""
Compliance and Reporting Layer for Fraud Detection System.

Provides Anti-Money Laundering (AML) compliance, regulatory reporting,
and fraud incident reporting functionality.
"""

from __future__ import annotations

import logging
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from api.fraud_detection.repositories import (
    fraud_case_repository, fraud_alert_repository, fraud_risk_profile_repository
)
from api.fraud_detection.selectors import (
    fraud_case_selector, fraud_alert_selector, fraud_risk_profile_selector
)
from api.fraud_detection.encryption import encrypt_sensitive_data, generate_integrity_hash
from api.fraud_detection.choices import SeverityLevel, FraudAlertType
from api.fraud_detection.constants import RISK_THRESHOLDS, CACHE_TTL
from api.fraud_detection.exceptions import ComplianceError, ReportingError


logger = logging.getLogger(__name__)


class AMLComplianceManager:
    """
    Anti-Money Laundering compliance manager.
    
    Handles AML threshold monitoring, suspicious activity reporting,
and regulatory compliance requirements.
    """
    
    def __init__(self):
        """Initialize AML compliance manager."""
        self.thresholds = self._load_aml_thresholds()
        self.reporting_rules = self._load_reporting_rules()
        self.regulatory_bodies = self._load_regulatory_bodies()
    
    def _load_aml_thresholds(self) -> Dict[str, Any]:
        """Load AML transaction thresholds."""
        default_thresholds = {
            'single_transaction': 10000.00,  # USD
            'daily_aggregate': 15000.00,     # USD
            'weekly_aggregate': 25000.00,     # USD
            'monthly_aggregate': 50000.00,   # USD
            'suspicious_pattern_threshold': 5,  # Number of suspicious transactions
            'structuring_threshold': 3,        # Number of transactions just below threshold
        }
        return getattr(settings, 'AML_THRESHOLDS', default_thresholds)
    
    def _load_reporting_rules(self) -> Dict[str, Any]:
        """Load AML reporting rules."""
        default_rules = {
            'sar_threshold': 5000.00,        # Suspicious Activity Report threshold
            'ctr_threshold': 10000.00,       # Currency Transaction Report threshold
            'reporting_timeframe_hours': 24,  # Time to file report after detection
            'auto_file_reports': False,       # Whether to auto-file or require review
        }
        return getattr(settings, 'AML_REPORTING_RULES', default_rules)
    
    def _load_regulatory_bodies(self) -> Dict[str, Dict[str, str]]:
        """Load regulatory body contact information."""
        default_bodies = {
            'fintrac': {
                'name': 'Financial Transactions and Reports Analysis Centre',
                'email': 'reports@fintrac-canafe.gc.ca',
                'phone': '+1-855-683-4682',
                'country': 'CA'
            },
            'fincen': {
                'name': 'Financial Crimes Enforcement Network',
                'email': 'frc@fincen.gov',
                'phone': '+1-703-905-3773',
                'country': 'US'
            },
            'internal': {
                'name': 'Internal Compliance Department',
                'email': 'compliance@company.com',
                'phone': '+1-555-0123',
                'country': 'INTERNAL'
            }
        }
        return getattr(settings, 'REGULATORY_BODIES', default_bodies)
    
    def monitor_transaction_limits(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Monitor transaction against AML limits and thresholds.
        
        Args:
            transaction_data: Transaction data to monitor
            
        Returns:
            Monitoring results with compliance status
        """
        monitoring_result = {
            'compliant': True,
            'thresholds_breached': [],
            'alerts_triggered': [],
            'reporting_required': False,
            'risk_level': 'low',
            'recommendations': []
        }
        
        amount = Decimal(str(transaction_data.get('amount', 0)))
        user_id = transaction_data.get('user_id')
        transaction_time = transaction_data.get('timestamp', timezone.now())
        
        # Check single transaction threshold
        if amount >= self.thresholds['single_transaction']:
            monitoring_result['thresholds_breached'].append({
                'type': 'single_transaction',
                'amount': float(amount),
                'threshold': self.thresholds['single_transaction']
            })
            monitoring_result['reporting_required'] = True
            monitoring_result['risk_level'] = 'high'
        
        # Check daily aggregate (simplified - would need aggregation)
        daily_total = self._calculate_daily_aggregate(user_id, transaction_time)
        if daily_total >= self.thresholds['daily_aggregate']:
            monitoring_result['thresholds_breached'].append({
                'type': 'daily_aggregate',
                'amount': float(daily_total),
                'threshold': self.thresholds['daily_aggregate']
            })
            monitoring_result['reporting_required'] = True
            monitoring_result['risk_level'] = 'high'
        
        # Check for structuring patterns
        structuring_detected = self._detect_structuring_pattern(user_id, transaction_time)
        if structuring_detected:
            monitoring_result['alerts_triggered'].append({
                'type': 'structuring_pattern',
                'description': 'Potential transaction structuring detected'
            })
            monitoring_result['reporting_required'] = True
            monitoring_result['risk_level'] = 'medium'
        
        # Check for suspicious patterns
        suspicious_count = self._count_suspicious_transactions(user_id, transaction_time)
        if suspicious_count >= self.thresholds['suspicious_pattern_threshold']:
            monitoring_result['alerts_triggered'].append({
                'type': 'suspicious_pattern',
                'count': suspicious_count,
                'threshold': self.thresholds['suspicious_pattern_threshold']
            })
            monitoring_result['reporting_required'] = True
            monitoring_result['risk_level'] = 'high'
        
        # Generate recommendations
        if monitoring_result['reporting_required']:
            monitoring_result['recommendations'].extend([
                "File SAR (Suspicious Activity Report)",
                "Enhanced monitoring required",
                "Consider temporary account restrictions"
            ])
        
        # Update compliance status
        if monitoring_result['thresholds_breached'] or monitoring_result['alerts_triggered']:
            monitoring_result['compliant'] = False
        
        return monitoring_result
    
    def generate_sar_report(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate Suspicious Activity Report (SAR).
        
        Args:
            case_data: Fraud case data for SAR generation
            
        Returns:
            Generated SAR report data
        """
        sar_report = {
            'report_type': 'SAR',
            'report_id': self._generate_report_id('SAR'),
            'filing_date': timezone.now().isoformat(),
            'reporting_period': self._get_reporting_period(),
            'suspicious_activity': {
                'total_amount': case_data.get('total_suspicious_amount', 0),
                'transaction_count': case_data.get('transaction_count', 0),
                'time_period': case_data.get('activity_period', 'Unknown'),
                'nature_of_suspicion': case_data.get('suspicion_reasons', []),
            },
            'subject_information': {
                'user_id': case_data.get('user_id'),
                'account_numbers': case_data.get('account_numbers', []),
                'identification_details': case_data.get('identification_details', {}),
            },
            'suspicious_activity_details': case_data.get('suspicious_activities', []),
            'financial_institution': {
                'name': getattr(settings, 'COMPANY_NAME', 'Our Company'),
                'identification': getattr(settings, 'COMPANY_ID', 'COMP-001'),
            },
            'law_enforcement_contact': self.regulatory_bodies.get('fincen', {}),
            'report_status': 'draft',
            'integrity_hash': None
        }
        
        # Generate integrity hash
        sar_report['integrity_hash'] = generate_integrity_hash(sar_report)
        
        return sar_report
    
    def generate_ctr_report(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate Currency Transaction Report (CTR).
        
        Args:
            transaction_data: Transaction data for CTR generation
            
        Returns:
            Generated CTR report data
        """
        ctr_report = {
            'report_type': 'CTR',
            'report_id': self._generate_report_id('CTR'),
            'transaction_date': transaction_data.get('timestamp', timezone.now()).isoformat(),
            'transaction_amount': float(transaction_data.get('amount', 0)),
            'transaction_type': transaction_data.get('transaction_type', 'Unknown'),
            'subject_information': {
                'user_id': transaction_data.get('user_id'),
                'name': transaction_data.get('customer_name', 'Unknown'),
                'identification': transaction_data.get('customer_identification', {}),
            },
            'financial_institution': {
                'name': getattr(settings, 'COMPANY_NAME', 'Our Company'),
                'branch': transaction_data.get('branch', 'Main'),
            },
            'regulatory_body': self.regulatory_bodies.get('fincen', {}),
            'report_status': 'draft',
            'integrity_hash': None
        }
        
        # Generate integrity hash
        ctr_report['integrity_hash'] = generate_integrity_hash(ctr_report)
        
        return ctr_report
    
    def _calculate_daily_aggregate(self, user_id: Union[int, str], 
                                  reference_time: datetime) -> Decimal:
        """Calculate daily transaction aggregate for user."""
        try:
            # Get start and end of day
            day_start = reference_time.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            # Query user transactions for the day (simplified - would use actual transaction model)
            # This is a basic implementation - in practice, you'd query your transaction database
            daily_total = Decimal('0.00')
            
            # Example implementation (would need actual transaction model):
            # from api.transactions.models import Transaction
            # daily_transactions = Transaction.objects.filter(
            #     user_id=user_id,
            #     created_at__gte=day_start,
            #     created_at__lt=day_end,
            #     status='completed'
            # )
            # daily_total = sum(Decimal(str(t.amount)) for t in daily_transactions)
            
            # For now, simulate with a basic calculation
            # In practice, this would be replaced with actual database queries
            return daily_total
            
        except Exception as e:
            logger.error(f"Error calculating daily aggregate for user {user_id}: {e}")
            return Decimal('0.00')
    
    def _detect_structuring_pattern(self, user_id: Union[int, str], 
                                  reference_time: datetime) -> bool:
        """Detect transaction structuring patterns."""
        try:
            # Get transactions from the past 30 days
            lookback_period = reference_time - timedelta(days=30)
            
            # Query recent transactions (simplified - would use actual transaction model)
            # In practice, you'd query your transaction database
            recent_transactions = []  # Placeholder for actual transaction data
            
            # Check for structuring patterns
            structuring_indicators = []
            
            # Pattern 1: Multiple transactions just below reporting threshold
            threshold = self.thresholds['single_transaction']
            buffer_amount = threshold * 0.95  # 95% of threshold
            
            # Count transactions near threshold
            near_threshold_count = 0
            for transaction in recent_transactions:
                amount = transaction.get('amount', 0)
                if buffer_amount <= amount < threshold:
                    near_threshold_count += 1
            
            if near_threshold_count >= self.thresholds['structuring_threshold']:
                structuring_indicators.append(f"Multiple transactions near threshold: {near_threshold_count}")
            
            # Pattern 2: Regular small transactions that aggregate to large amounts
            if len(recent_transactions) >= 10:
                total_amount = sum(t.get('amount', 0) for t in recent_transactions)
                avg_amount = total_amount / len(recent_transactions)
                
                # If average is small but total is large, potential structuring
                if avg_amount < (threshold * 0.3) and total_amount >= threshold:
                    structuring_indicators.append(f"Small regular transactions aggregating to large amount: {total_amount}")
            
            # Pattern 3: Time-based structuring (multiple transactions in short period)
            if len(recent_transactions) >= 5:
                # Group transactions by hour
                hourly_counts = {}
                for transaction in recent_transactions:
                    hour = transaction.get('timestamp', reference_time).hour
                    hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
                
                # Check for hours with multiple transactions
                for hour, count in hourly_counts.items():
                    if count >= 3:  # 3+ transactions in same hour
                        structuring_indicators.append(f"Multiple transactions in hour {hour}: {count}")
            
            # Log detected patterns
            if structuring_indicators:
                logger.warning(f"Structuring patterns detected for user {user_id}: {structuring_indicators}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error detecting structuring patterns for user {user_id}: {e}")
            return False
    
    def _count_suspicious_transactions(self, user_id: Union[int, str], 
                                     reference_time: datetime) -> int:
        """Count suspicious transactions for user."""
        try:
            # Get transactions from the past 30 days
            lookback_period = reference_time - timedelta(days=30)
            
            # Query recent transactions (simplified - would use actual transaction model)
            # In practice, you'd query your transaction database
            recent_transactions = []  # Placeholder for actual transaction data
            
            suspicious_count = 0
            suspicious_indicators = []
            
            for transaction in recent_transactions:
                transaction_flags = 0
                
                # Flag 1: High risk amount
                amount = transaction.get('amount', 0)
                if amount >= self.thresholds['single_transaction']:
                    transaction_flags += 1
                    suspicious_indicators.append(f"High amount transaction: {amount}")
                
                # Flag 2: Unusual timing (late night/early morning)
                transaction_time = transaction.get('timestamp', reference_time)
                if transaction_time.hour < 6 or transaction_time.hour > 23:
                    transaction_flags += 1
                    suspicious_indicators.append(f"Unusual timing: {transaction_time.hour}:00")
                
                # Flag 3: High frequency (multiple transactions in short time)
                # This would require more complex analysis in practice
                
                # Flag 4: Geographic anomalies (would need location data)
                # Flag 5: Device anomalies (would need device data)
                
                # Count as suspicious if multiple flags
                if transaction_flags >= 2:
                    suspicious_count += 1
            
            if suspicious_count > 0:
                logger.info(f"Found {suspicious_count} suspicious transactions for user {user_id}")
                logger.debug(f"Suspicious indicators: {suspicious_indicators[:5]}")  # Limit log output
            
            return suspicious_count
            
        except Exception as e:
            logger.error(f"Error counting suspicious transactions for user {user_id}: {e}")
            return 0
    
    def _generate_report_id(self, report_type: str) -> str:
        """Generate unique report ID."""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        return f"{report_type}-{timestamp}-{timezone.now().microsecond}"
    
    def _get_reporting_period(self) -> str:
        """Get current reporting period."""
        now = timezone.now()
        if now.day <= 15:
            return f"{now.year}-{now.month:02d}-01 to {now.year}-{now.month:02d}-15"
        else:
            return f"{now.year}-{now.month:02d}-16 to {now.year}-{now.month:02d}-{now.month.days_in_month()}"


class FraudReportingManager:
    """
    Fraud incident reporting manager.
    
    Handles internal fraud reporting, external notifications,
and regulatory compliance reporting.
    """
    
    def __init__(self):
        """Initialize fraud reporting manager."""
        self.reporting_channels = self._load_reporting_channels()
        self.notification_templates = self._load_notification_templates()
        self.escalation_rules = self._load_escalation_rules()
    
    def _load_reporting_channels(self) -> Dict[str, Dict[str, Any]]:
        """Load reporting channel configurations."""
        default_channels = {
            'email': {
                'enabled': True,
                'recipients': ['fraud@company.com', 'compliance@company.com'],
                'template': 'fraud_alert_email',
            },
            'slack': {
                'enabled': False,
                'webhook_url': getattr(settings, 'SLACK_WEBHOOK_URL', ''),
                'channel': '#fraud-alerts',
            },
            'sms': {
                'enabled': False,
                'recipients': ['+1234567890'],
                'template': 'fraud_alert_sms',
            },
            'regulatory': {
                'enabled': True,
                'bodies': ['fintrac', 'fincen'],
                'auto_file': False,
            }
        }
        return getattr(settings, 'FRAUD_REPORTING_CHANNELS', default_channels)
    
    def _load_notification_templates(self) -> Dict[str, str]:
        """Load notification templates."""
        default_templates = {
            'fraud_alert_email': """
FRAUD ALERT - IMMEDIATE ATTENTION REQUIRED

Alert ID: {alert_id}
Severity: {severity}
User ID: {user_id}
Risk Score: {risk_score}
Detection Time: {timestamp}

Summary:
{summary}

Details:
{details}

Recommended Actions:
{recommendations}

Please investigate immediately.
            """.strip(),
            'fraud_alert_sms': "FRAUD ALERT: User {user_id} - Risk Score {risk_score} - {severity}",
            'sar_notification': "SAR Report {report_id} filed for user {user_id}",
        }
        return getattr(settings, 'FRAUD_NOTIFICATION_TEMPLATES', default_templates)
    
    def _load_escalation_rules(self) -> Dict[str, Any]:
        """Load escalation rules."""
        default_rules = {
            'critical_threshold': 90,
            'high_threshold': 70,
            'medium_threshold': 50,
            'escalation_timeframe_hours': 24,
            'auto_escalate_critical': True,
        }
        return getattr(settings, 'FRAUD_ESCALATION_RULES', default_rules)
    
    def create_fraud_report(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create comprehensive fraud report.
        
        Args:
            case_data: Fraud case data
            
        Returns:
            Created fraud report
        """
        try:
            fraud_report = {
                'report_id': self._generate_report_id('FRAUD'),
                'case_id': case_data.get('case_id'),
                'user_id': case_data.get('user_id'),
                'report_type': 'fraud_incident',
                'severity': case_data.get('severity', 'medium'),
                'risk_score': case_data.get('risk_score', 0),
                'created_at': timezone.now().isoformat(),
                'incident_details': {
                    'summary': case_data.get('summary', ''),
                    'description': case_data.get('description', ''),
                    'evidence': case_data.get('evidence', []),
                    'timeline': case_data.get('timeline', []),
                },
                'impact_assessment': {
                    'financial_impact': case_data.get('financial_impact', 0),
                    'affected_accounts': case_data.get('affected_accounts', []),
                    'potential_loss': case_data.get('potential_loss', 0),
                },
                'investigation_status': 'pending',
                'assigned_to': None,
                'notifications_sent': [],
                'integrity_hash': None
            }
            
            # Generate integrity hash
            fraud_report['integrity_hash'] = generate_integrity_hash(fraud_report)
            
            # Send notifications
            notifications = self._send_fraud_notifications(fraud_report)
            fraud_report['notifications_sent'] = notifications
            
            logger.info(f"Created fraud report: {fraud_report['report_id']}")
            return fraud_report
            
        except Exception as e:
            logger.error(f"Failed to create fraud report: {e}")
            raise ReportingError(f"Failed to create fraud report: {e}")
    
    def send_regulatory_report(self, report_data: Dict[str, Any], 
                             regulatory_body: str) -> bool:
        """
        Send report to regulatory body.
        
        Args:
            report_data: Report data to send
            regulatory_body: Target regulatory body
            
        Returns:
            True if sent successfully
        """
        try:
            # Get regulatory body contact info
            body_info = self.regulatory_bodies.get(regulatory_body.lower())
            if not body_info:
                raise ComplianceError(f"Unknown regulatory body: {regulatory_body}")
            
            # Prepare report submission
            submission_data = {
                'report_id': report_data.get('report_id'),
                'report_type': report_data.get('report_type'),
                'submission_date': timezone.now().isoformat(),
                'submitting_institution': getattr(settings, 'COMPANY_NAME', 'Our Company'),
                'report_content': report_data,
                'contact_information': {
                    'name': 'Compliance Officer',
                    'email': 'compliance@company.com',
                    'phone': '+1-555-0123',
                }
            }
            
            # Send via email (simplified - in practice, use secure submission channels)
            if self.reporting_channels.get('email', {}).get('enabled', False):
                success = self._send_email_report(body_info['email'], submission_data)
                if success:
                    logger.info(f"Regulatory report {report_data.get('report_id')} sent to {regulatory_body}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to send regulatory report: {e}")
            raise ReportingError(f"Failed to send regulatory report: {e}")
    
    def escalate_fraud_case(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Escalate fraud case based on severity and rules.
        
        Args:
            case_data: Fraud case data to escalate
            
        Returns:
            Escalation result
        """
        escalation_result = {
            'escalated': False,
            'escalation_level': None,
            'escalation_reason': '',
            'notifications_sent': [],
            'next_review_time': None
        }
        
        risk_score = case_data.get('risk_score', 0)
        severity = case_data.get('severity', 'low')
        
        # Determine escalation level
        if risk_score >= self.escalation_rules['critical_threshold'] or severity == 'critical':
            escalation_result['escalated'] = True
            escalation_result['escalation_level'] = 'critical'
            escalation_result['escalation_reason'] = 'Critical risk score or severity'
            escalation_result['next_review_time'] = timezone.now() + timedelta(hours=1)
        elif risk_score >= self.escalation_rules['high_threshold'] or severity == 'high':
            escalation_result['escalated'] = True
            escalation_result['escalation_level'] = 'high'
            escalation_result['escalation_reason'] = 'High risk score or severity'
            escalation_result['next_review_time'] = timezone.now() + timedelta(hours=4)
        elif risk_score >= self.escalation_rules['medium_threshold'] or severity == 'medium':
            escalation_result['escalated'] = True
            escalation_result['escalation_level'] = 'medium'
            escalation_result['escalation_reason'] = 'Medium risk score or severity'
            escalation_result['next_review_time'] = timezone.now() + timedelta(hours=24)
        
        # Send escalation notifications
        if escalation_result['escalated']:
            notifications = self._send_escalation_notifications(case_data, escalation_result)
            escalation_result['notifications_sent'] = notifications
        
        return escalation_result
    
    def _send_fraud_notifications(self, fraud_report: Dict[str, Any]) -> List[str]:
        """Send fraud report notifications."""
        notifications_sent = []
        
        # Email notifications
        if self.reporting_channels.get('email', {}).get('enabled', False):
            for recipient in self.reporting_channels['email']['recipients']:
                try:
                    subject = f"FRAUD ALERT - {fraud_report['severity'].upper()} - {fraud_report['report_id']}"
                    
                    template = self.notification_templates.get('fraud_alert_email', '')
                    message = template.format(
                        alert_id=fraud_report['report_id'],
                        severity=fraud_report['severity'].upper(),
                        user_id=fraud_report['user_id'],
                        risk_score=fraud_report['risk_score'],
                        timestamp=fraud_report['created_at'],
                        summary=fraud_report['incident_details']['summary'],
                        details=json.dumps(fraud_report['incident_details'], indent=2),
                        recommendations=self._generate_recommendations(fraud_report)
                    )
                    
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@company.com'),
                        recipient_list=[recipient],
                        fail_silently=False
                    )
                    
                    notifications_sent.append(f"email:{recipient}")
                    logger.info(f"Fraud notification sent to {recipient}")
                    
                except Exception as e:
                    logger.error(f"Failed to send email notification to {recipient}: {e}")
        
        # Slack notifications
        if self.reporting_channels.get('slack', {}).get('enabled', False):
            try:
                # Slack webhook implementation would go here
                notifications_sent.append("slack:fraud-alerts")
            except Exception as e:
                logger.error(f"Failed to send Slack notification: {e}")
        
        return notifications_sent
    
    def _send_email_report(self, recipient: str, report_data: Dict[str, Any]) -> bool:
        """Send report via email."""
        try:
            subject = f"Regulatory Report Submission - {report_data['report_id']}"
            
            message = f"""
REGULATORY REPORT SUBMISSION

Report ID: {report_data['report_id']}
Report Type: {report_data['report_type']}
Submission Date: {report_data['submission_date']}
Submitting Institution: {report_data['submitting_institution']}

Please find the report details attached or in the system.
            """.strip()
            
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@company.com'),
                recipient_list=[recipient],
                fail_silently=False
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email report to {recipient}: {e}")
            return False
    
    def _send_escalation_notifications(self, case_data: Dict[str, Any], 
                                     escalation_result: Dict[str, Any]) -> List[str]:
        """Send escalation notifications."""
        notifications_sent = []
        
        # Send to escalation recipients based on level
        escalation_recipients = {
            'critical': ['executive@company.com', 'compliance@company.com', 'security@company.com'],
            'high': ['compliance@company.com', 'security@company.com'],
            'medium': ['compliance@company.com']
        }
        
        level = escalation_result['escalation_level']
        recipients = escalation_recipients.get(level, [])
        
        for recipient in recipients:
            try:
                subject = f"ESCALATION - {level.upper()} - Case {case_data.get('case_id', 'Unknown')}"
                
                message = f"""
FRAUD CASE ESCALATION

Escalation Level: {level.upper()}
Case ID: {case_data.get('case_id', 'Unknown')}
User ID: {case_data.get('user_id', 'Unknown')}
Risk Score: {case_data.get('risk_score', 0)}
Reason: {escalation_result['escalation_reason']}
Next Review: {escalation_result['next_review_time']}

Immediate attention required.
                """.strip()
                
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@company.com'),
                    recipient_list=[recipient],
                    fail_silently=False
                )
                
                notifications_sent.append(f"escalation_email:{recipient}")
                
            except Exception as e:
                logger.error(f"Failed to send escalation notification to {recipient}: {e}")
        
        return notifications_sent
    
    def _generate_report_id(self, report_type: str) -> str:
        """Generate unique report ID."""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        return f"{report_type}-{timestamp}-{timezone.now().microsecond}"
    
    def _generate_recommendations(self, fraud_report: Dict[str, Any]) -> str:
        """Generate recommendations based on fraud report."""
        recommendations = []
        
        risk_score = fraud_report.get('risk_score', 0)
        severity = fraud_report.get('severity', 'low')
        
        if risk_score >= 90 or severity == 'critical':
            recommendations.extend([
                "1. Immediate account suspension",
                "2. Freeze all related assets",
                "3. Contact law enforcement",
                "4. File SAR within 24 hours"
            ])
        elif risk_score >= 70 or severity == 'high':
            recommendations.extend([
                "1. Enhanced monitoring",
                "2. Limit account functionality",
                "3. Request additional verification",
                "4. Consider SAR filing"
            ])
        elif risk_score >= 50 or severity == 'medium':
            recommendations.extend([
                "1. Increase monitoring frequency",
                "2. Review recent transactions",
                "3. Document findings"
            ])
        
        return '\n'.join(recommendations) if recommendations else "Standard monitoring procedures apply."


class ComplianceAuditManager:
    """
    Compliance audit and reporting manager.
    
    Handles audit trail generation, compliance reporting,
and regulatory audit preparation.
    """
    
    def __init__(self):
        """Initialize compliance audit manager."""
        self.audit_retention_days = getattr(settings, 'COMPLIANCE_AUDIT_RETENTION_DAYS', 2555)  # 7 years
    
    def generate_compliance_report(self, start_date: datetime, 
                                  end_date: datetime) -> Dict[str, Any]:
        """
        Generate comprehensive compliance report.
        
        Args:
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            Compliance report data
        """
        try:
            compliance_report = {
                'report_id': self._generate_report_id('COMPLIANCE'),
                'report_period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                },
                'generated_at': timezone.now().isoformat(),
                'summary_statistics': self._get_summary_statistics(start_date, end_date),
                'aml_compliance': self._get_aml_compliance_data(start_date, end_date),
                'fraud_cases': self._get_fraud_case_summary(start_date, end_date),
                'regulatory_filings': self._get_regulatory_filings_summary(start_date, end_date),
                'audit_trail': self._generate_audit_trail_summary(start_date, end_date),
                'recommendations': self._generate_compliance_recommendations(),
                'integrity_hash': None
            }
            
            # Generate integrity hash
            compliance_report['integrity_hash'] = generate_integrity_hash(compliance_report)
            
            logger.info(f"Generated compliance report: {compliance_report['report_id']}")
            return compliance_report
            
        except Exception as e:
            logger.error(f"Failed to generate compliance report: {e}")
            raise ComplianceError(f"Failed to generate compliance report: {e}")
    
    def _get_summary_statistics(self, start_date: datetime, 
                              end_date: datetime) -> Dict[str, Any]:
        """Get summary statistics for compliance report."""
        # In practice, this would query various databases
        # For now, return placeholder data
        return {
            'total_transactions': 0,
            'total_amount': 0.0,
            'suspicious_transactions': 0,
            'fraud_cases_opened': 0,
            'fraud_cases_closed': 0,
            'sar_reports_filed': 0,
            'ctr_reports_filed': 0,
        }
    
    def _get_aml_compliance_data(self, start_date: datetime, 
                                end_date: datetime) -> Dict[str, Any]:
        """Get AML compliance data for report."""
        return {
            'threshold_breaches': [],
            'structuring_detections': [],
            'suspicious_patterns': [],
            'regulatory_filings': [],
        }
    
    def _get_fraud_case_summary(self, start_date: datetime, 
                              end_date: datetime) -> Dict[str, Any]:
        """Get fraud case summary for report."""
        return {
            'total_cases': 0,
            'cases_by_severity': {},
            'cases_by_status': {},
            'average_resolution_time': 0,
            'total_financial_impact': 0.0,
        }
    
    def _get_regulatory_filings_summary(self, start_date: datetime, 
                                      end_date: datetime) -> Dict[str, Any]:
        """Get regulatory filings summary for report."""
        return {
            'sar_filings': [],
            'ctr_filings': [],
            'other_filings': [],
            'filing_deadlines_met': 0,
            'filing_deadlines_missed': 0,
        }
    
    def _generate_audit_trail_summary(self, start_date: datetime, 
                                    end_date: datetime) -> Dict[str, Any]:
        """Generate audit trail summary."""
        return {
            'total_audit_entries': 0,
            'access_logs': [],
            'modification_logs': [],
            'system_changes': [],
            'compliance_checks': [],
        }
    
    def _generate_compliance_recommendations(self) -> List[str]:
        """Generate compliance recommendations."""
        return [
            "Review and update AML policies annually",
            "Conduct regular staff training on compliance procedures",
            "Implement automated monitoring for threshold breaches",
            "Maintain up-to-date sanctions lists",
            "Regular testing of compliance systems",
        ]
    
    def _generate_report_id(self, report_type: str) -> str:
        """Generate unique report ID."""
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        return f"{report_type}-{timestamp}-{timezone.now().microsecond}"


# Global instances for easy access
aml_compliance_manager = AMLComplianceManager()
fraud_reporting_manager = FraudReportingManager()
compliance_audit_manager = ComplianceAuditManager()


def monitor_aml_compliance(transaction_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function for AML compliance monitoring.
    
    Args:
        transaction_data: Transaction data to monitor
        
    Returns:
        AML compliance monitoring results
    """
    return aml_compliance_manager.monitor_transaction_limits(transaction_data)


def create_fraud_incident_report(case_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function for fraud incident reporting.
    
    Args:
        case_data: Fraud case data
        
    Returns:
        Created fraud report
    """
    return fraud_reporting_manager.create_fraud_report(case_data)


def generate_monthly_compliance_report() -> Dict[str, Any]:
    """
    Convenience function for monthly compliance reporting.
    
    Returns:
        Monthly compliance report
    """
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    return compliance_audit_manager.generate_compliance_report(start_date, end_date)
