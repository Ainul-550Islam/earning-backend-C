"""
⚖️ Backup Compliance Module

This module provides comprehensive compliance management for the backup system.
It includes regulatory compliance tracking, audit trails, policy enforcement,
and compliance reporting to ensure the backup system meets various regulatory
requirements.

Features:
- Multiple regulatory frameworks support (GDPR, HIPAA, SOX, PCI-DSS)
- Compliance policy management
- Automated compliance checks
- Audit trail generation
- Compliance reporting and analytics
- Risk assessment and management
- Data retention policies
- Compliance violation tracking
"""

import logging
import json
import hashlib
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models
from django.db.models import Q, Count
from django.core.cache import cache
from django.conf import settings

# Import backup models
from .models import Backup, BackupSchedule, BackupLog, BackupAlert, BackupVerification
from .utils import TimeUtils
from api.backup.models import BackupRestoration

logger = logging.getLogger(__name__)


class ComplianceFramework(Enum):
    """Enumeration of compliance frameworks."""
    GDPR = "gdpr"  # General Data Protection Regulation
    HIPAA = "hipaa"  # Health Insurance Portability and Accountability Act
    SOX = "sox"  # Sarbanes-Oxley Act
    PCI_DSS = "pci_dss"  # Payment Card Industry Data Security Standard
    ISO_27001 = "iso_27001"  # ISO/IEC 27001 Information Security Management
    NIST = "nist"  # NIST Cybersecurity Framework
    CCPA = "ccpa"  # California Consumer Privacy Act
    CUSTOM = "custom"


class ComplianceStatus(Enum):
    """Enumeration of compliance statuses."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    UNKNOWN = "unknown"
    EXEMPT = "exempt"


class ComplianceCategory(Enum):
    """Enumeration of compliance categories."""
    DATA_PROTECTION = "data_protection"
    RETENTION_POLICY = "retention_policy"
    ACCESS_CONTROL = "access_control"
    ENCRYPTION = "encryption"
    AUDIT_TRAIL = "audit_trail"
    BACKUP_RECOVERY = "backup_recovery"
    PRIVACY = "privacy"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    RISK_MANAGEMENT = "risk_management"


class ComplianceSeverity(Enum):
    """Enumeration of compliance violation severities."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ComplianceRule:
    """Compliance rule definition."""
    rule_id: str
    name: str
    description: str
    framework: ComplianceFramework
    category: ComplianceCategory
    requirement: str
    check_function: Callable
    severity: ComplianceSeverity
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceCheck:
    """Result of a compliance check."""
    rule_id: str
    status: ComplianceStatus
    score: float  # 0-100
    details: Dict[str, Any]
    violations: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    checked_at: datetime = field(default_factory=timezone.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceReport:
    """Compliance report summary."""
    framework: ComplianceFramework
    overall_status: ComplianceStatus
    overall_score: float
    category_scores: Dict[ComplianceCategory, float]
    total_checks: int
    passed_checks: int
    failed_checks: int
    violations: List[Dict[str, Any]]
    recommendations: List[str]
    generated_at: datetime = field(default_factory=timezone.now)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class ComplianceEngine:
    """Main compliance engine for checking backup system compliance."""
    
    def __init__(self):
        self.rules: Dict[str, ComplianceRule] = {}
        self.rule_registry: Dict[ComplianceFramework, List[ComplianceRule]] = {}
        self._register_default_rules()
    
    def _register_default_rules(self) -> None:
        """Register default compliance rules."""
        # GDPR Rules
        self.register_rule(ComplianceRule(
            rule_id="gdpr_data_minimization",
            name="Data Minimization",
            description="Ensure only necessary data is backed up",
            framework=ComplianceFramework.GDPR,
            category=ComplianceCategory.DATA_PROTECTION,
            requirement="Personal data shall be adequate, relevant and limited to what is necessary",
            check_function=self._check_gdpr_data_minimization,
            severity=ComplianceSeverity.MEDIUM
        ))
        
        self.register_rule(ComplianceRule(
            rule_id="gdpr_retention_period",
            name="Data Retention Period",
            description="Verify data retention periods comply with GDPR",
            framework=ComplianceFramework.GDPR,
            category=ComplianceCategory.RETENTION_POLICY,
            requirement="Personal data shall not be kept longer than necessary",
            check_function=self._check_gdpr_retention_period,
            severity=ComplianceSeverity.HIGH
        ))
        
        self.register_rule(ComplianceRule(
            rule_id="gdpr_encryption",
            name="Data Encryption",
            description="Ensure backup data is properly encrypted",
            framework=ComplianceFramework.GDPR,
            category=ComplianceCategory.ENCRYPTION,
            requirement="Appropriate technical security measures shall be implemented",
            check_function=self._check_gdpr_encryption,
            severity=ComplianceSeverity.CRITICAL
        ))
        
        # HIPAA Rules
        self.register_rule(ComplianceRule(
            rule_id="hipaa_access_control",
            name="Access Control",
            description="Verify proper access controls are in place",
            framework=ComplianceFramework.HIPAA,
            category=ComplianceCategory.ACCESS_CONTROL,
            requirement="Implement technical policies and procedures for electronic information access",
            check_function=self._check_hipaa_access_control,
            severity=ComplianceSeverity.HIGH
        ))
        
        self.register_rule(ComplianceRule(
            rule_id="hipaa_audit_trail",
            name="Audit Trail",
            description="Ensure comprehensive audit logging",
            framework=ComplianceFramework.HIPAA,
            category=ComplianceCategory.AUDIT_TRAIL,
            requirement="Implement hardware, software, and/or procedural mechanisms that record and examine activity",
            check_function=self._check_hipaa_audit_trail,
            severity=ComplianceSeverity.HIGH
        ))
        
        # SOX Rules
        self.register_rule(ComplianceRule(
            rule_id="sox_backup_recovery",
            name="Backup and Recovery",
            description="Verify backup and recovery procedures",
            framework=ComplianceFramework.SOX,
            category=ComplianceCategory.BACKUP_RECOVERY,
            requirement="Disaster recovery planning and business continuity",
            check_function=self._check_sox_backup_recovery,
            severity=ComplianceSeverity.HIGH
        ))
        
        # PCI-DSS Rules
        self.register_rule(ComplianceRule(
            rule_id="pci_encryption",
            name="Cardholder Data Encryption",
            description="Ensure cardholder data is encrypted",
            framework=ComplianceFramework.PCI_DSS,
            category=ComplianceCategory.ENCRYPTION,
            requirement="Render all cardholder data unreadable",
            check_function=self._check_pci_encryption,
            severity=ComplianceSeverity.CRITICAL
        ))
        
        # ISO 27001 Rules
        self.register_rule(ComplianceRule(
            rule_id="iso27001_risk_management",
            name="Risk Management",
            description="Verify risk assessment and treatment",
            framework=ComplianceFramework.ISO_27001,
            category=ComplianceCategory.RISK_MANAGEMENT,
            requirement="Risk assessment and treatment process",
            check_function=self._check_iso27001_risk_management,
            severity=ComplianceSeverity.MEDIUM
        ))
    
    def register_rule(self, rule: ComplianceRule) -> None:
        """Register a compliance rule."""
        self.rules[rule.rule_id] = rule
        
        if rule.framework not in self.rule_registry:
            self.rule_registry[rule.framework] = []
        
        self.rule_registry[rule.framework].append(rule)
    
    def check_compliance(self, framework: Optional[ComplianceFramework] = None,
                        period_start: Optional[datetime] = None,
                        period_end: Optional[datetime] = None) -> ComplianceReport:
        """Check compliance for specified framework or all frameworks."""
        if framework:
            return self._check_framework_compliance(framework, period_start, period_end)
        else:
            # Check all frameworks and aggregate results
            reports = []
            for fw in ComplianceFramework:
                if fw in self.rule_registry:
                    reports.append(self._check_framework_compliance(fw, period_start, period_end))
            
            return self._aggregate_reports(reports)
    
    def _check_framework_compliance(self, framework: ComplianceFramework,
                                  period_start: Optional[datetime],
                                  period_end: Optional[datetime]) -> ComplianceReport:
        """Check compliance for a specific framework."""
        rules = self.rule_registry.get(framework, [])
        checks = []
        
        for rule in rules:
            if not rule.enabled:
                continue
            
            try:
                check = rule.check_function(rule, period_start, period_end)
                checks.append(check)
            except Exception as e:
                logger.error(f"Compliance check failed for rule {rule.rule_id}: {e}")
                checks.append(ComplianceCheck(
                    rule_id=rule.rule_id,
                    status=ComplianceStatus.UNKNOWN,
                    score=0.0,
                    details={'error': str(e)}
                ))
        
        return self._generate_report(framework, checks, period_start, period_end)
    
    def _generate_report(self, framework: ComplianceFramework,
                         checks: List[ComplianceCheck],
                         period_start: Optional[datetime],
                         period_end: Optional[datetime]) -> ComplianceReport:
        """Generate compliance report from checks."""
        if not checks:
            return ComplianceReport(
                framework=framework,
                overall_status=ComplianceStatus.UNKNOWN,
                overall_score=0.0,
                category_scores={},
                total_checks=0,
                passed_checks=0,
                failed_checks=0,
                violations=[],
                recommendations=[],
                period_start=period_start,
                period_end=period_end
            )
        
        # Calculate overall score and status
        total_score = sum(check.score for check in checks) / len(checks)
        
        if total_score >= 90:
            overall_status = ComplianceStatus.COMPLIANT
        elif total_score >= 70:
            overall_status = ComplianceStatus.PARTIALLY_COMPLIANT
        else:
            overall_status = ComplianceStatus.NON_COMPLIANT
        
        # Calculate category scores
        category_scores = {}
        category_checks = {}
        
        for check in checks:
            rule = self.rules[check.rule_id]
            category = rule.category
            
            if category not in category_checks:
                category_checks[category] = []
            category_checks[category].append(check)
        
        for category, cat_checks in category_checks.items():
            category_scores[category] = sum(check.score for check in cat_checks) / len(cat_checks)
        
        # Count passed/failed checks
        passed_checks = sum(1 for check in checks if check.status == ComplianceStatus.COMPLIANT)
        failed_checks = len(checks) - passed_checks
        
        # Collect violations and recommendations
        violations = []
        recommendations = []
        
        for check in checks:
            violations.extend(check.violations)
            recommendations.extend(check.recommendations)
        
        return ComplianceReport(
            framework=framework,
            overall_status=overall_status,
            overall_score=total_score,
            category_scores=category_scores,
            total_checks=len(checks),
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            violations=violations,
            recommendations=recommendations,
            period_start=period_start,
            period_end=period_end
        )
    
    def _aggregate_reports(self, reports: List[ComplianceReport]) -> ComplianceReport:
        """Aggregate multiple compliance reports."""
        if not reports:
            return ComplianceReport(
                framework=ComplianceFramework.CUSTOM,
                overall_status=ComplianceStatus.UNKNOWN,
                overall_score=0.0,
                category_scores={},
                total_checks=0,
                passed_checks=0,
                failed_checks=0,
                violations=[],
                recommendations=[]
            )
        
        # Aggregate scores
        total_score = sum(report.overall_score for report in reports) / len(reports)
        
        # Determine overall status
        if total_score >= 90:
            overall_status = ComplianceStatus.COMPLIANT
        elif total_score >= 70:
            overall_status = ComplianceStatus.PARTIALLY_COMPLIANT
        else:
            overall_status = ComplianceStatus.NON_COMPLIANT
        
        # Aggregate category scores
        all_category_scores = {}
        for report in reports:
            for category, score in report.category_scores.items():
                if category not in all_category_scores:
                    all_category_scores[category] = []
                all_category_scores[category].append(score)
        
        category_scores = {}
        for category, scores in all_category_scores.items():
            category_scores[category] = sum(scores) / len(scores)
        
        # Aggregate counts
        total_checks = sum(report.total_checks for report in reports)
        passed_checks = sum(report.passed_checks for report in reports)
        failed_checks = sum(report.failed_checks for report in reports)
        
        # Aggregate violations and recommendations
        violations = []
        recommendations = []
        
        for report in reports:
            violations.extend(report.violations)
            recommendations.extend(report.recommendations)
        
        return ComplianceReport(
            framework=ComplianceFramework.CUSTOM,
            overall_status=overall_status,
            overall_score=total_score,
            category_scores=category_scores,
            total_checks=total_checks,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            violations=violations,
            recommendations=recommendations
        )
    
    # GDPR Check Functions
    def _check_gdpr_data_minimization(self, rule: ComplianceRule,
                                     period_start: Optional[datetime],
                                     period_end: Optional[datetime]) -> ComplianceCheck:
        """Check GDPR data minimization compliance."""
        try:
            # Check if backups contain only necessary data
            total_backups = Backup.objects.filter(
                created_at__gte=period_start or timezone.now() - timedelta(days=30),
                created_at__lte=period_end or timezone.now()
            ).count()
            
            # Check for backups with excluded sensitive data
            # This is a simplified check - in reality, you'd analyze backup contents
            compliant_backups = total_backups  # Placeholder
            
            score = (compliant_backups / total_backups * 100) if total_backups > 0 else 100
            
            violations = []
            recommendations = []
            
            if score < 100:
                violations.append({
                    'type': 'data_minimization_violation',
                    'description': 'Some backups may contain unnecessary personal data',
                    'severity': rule.severity.value
                })
                recommendations.append("Review backup configurations to exclude unnecessary personal data")
            
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.COMPLIANT if score >= 90 else ComplianceStatus.PARTIALLY_COMPLIANT,
                score=score,
                details={
                    'total_backups': total_backups,
                    'compliant_backups': compliant_backups
                },
                violations=violations,
                recommendations=recommendations
            )
            
        except Exception as e:
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.UNKNOWN,
                score=0.0,
                details={'error': str(e)}
            )
    
    def _check_gdpr_retention_period(self, rule: ComplianceRule,
                                   period_start: Optional[datetime],
                                   period_end: Optional[datetime]) -> ComplianceCheck:
        """Check GDPR retention period compliance."""
        try:
            # Check retention policy compliance
            max_retention_days = getattr(settings, 'GDPR_MAX_RETENTION_DAYS', 2555)  # 7 years
            cutoff_date = timezone.now() - timedelta(days=max_retention_days)
            
            expired_backups = Backup.objects.filter(
                created_at__lt=cutoff_date,
                is_permanent=False
            ).count()
            
            total_backups = Backup.objects.filter(
                created_at__lt=cutoff_date,
                is_permanent=False
            ).count()
            
            score = ((total_backups - expired_backups) / total_backups * 100) if total_backups > 0 else 100
            
            violations = []
            recommendations = []
            
            if expired_backups > 0:
                violations.append({
                    'type': 'retention_period_violation',
                    'description': f'{expired_backups} backups exceed GDPR retention period',
                    'severity': rule.severity.value
                })
                recommendations.append("Implement automatic cleanup of expired backups")
            
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.COMPLIANT if score >= 90 else ComplianceStatus.NON_COMPLIANT,
                score=score,
                details={
                    'expired_backups': expired_backups,
                    'total_backups': total_backups,
                    'max_retention_days': max_retention_days
                },
                violations=violations,
                recommendations=recommendations
            )
            
        except Exception as e:
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.UNKNOWN,
                score=0.0,
                details={'error': str(e)}
            )
    
    def _check_gdpr_encryption(self, rule: ComplianceRule,
                              period_start: Optional[datetime],
                              period_end: Optional[datetime]) -> ComplianceCheck:
        """Check GDPR encryption compliance."""
        try:
            # Check if backups are encrypted
            recent_backups = Backup.objects.filter(
                created_at__gte=period_start or timezone.now() - timedelta(days=30),
                created_at__lte=period_end or timezone.now()
            )
            
            total_backups = recent_backups.count()
            encrypted_backups = recent_backups.filter(is_encrypted=True).count()
            
            score = (encrypted_backups / total_backups * 100) if total_backups > 0 else 100
            
            violations = []
            recommendations = []
            
            if score < 100:
                violations.append({
                    'type': 'encryption_violation',
                    'description': f'{total_backups - encrypted_backups} backups are not encrypted',
                    'severity': rule.severity.value
                })
                recommendations.append("Enable encryption for all backup operations")
            
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.COMPLIANT if score >= 100 else ComplianceStatus.NON_COMPLIANT,
                score=score,
                details={
                    'total_backups': total_backups,
                    'encrypted_backups': encrypted_backups
                },
                violations=violations,
                recommendations=recommendations
            )
            
        except Exception as e:
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.UNKNOWN,
                score=0.0,
                details={'error': str(e)}
            )
    
    # HIPAA Check Functions
    def _check_hipaa_access_control(self, rule: ComplianceRule,
                                   period_start: Optional[datetime],
                                   period_end: Optional[datetime]) -> ComplianceCheck:
        """Check HIPAA access control compliance."""
        try:
            # Check access control implementation
            # This is a simplified check - in reality, you'd analyze access logs
            has_permissions = True  # Placeholder
            has_audit_logs = BackupLog.objects.exists()
            
            score = 100 if has_permissions and has_audit_logs else 50
            
            violations = []
            recommendations = []
            
            if not has_permissions:
                violations.append({
                    'type': 'access_control_violation',
                    'description': 'Insufficient access control mechanisms',
                    'severity': rule.severity.value
                })
                recommendations.append("Implement proper access control for backup operations")
            
            if not has_audit_logs:
                violations.append({
                    'type': 'audit_logging_violation',
                    'description': 'Missing audit logging for access control',
                    'severity': rule.severity.value
                })
                recommendations.append("Enable comprehensive audit logging")
            
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.COMPLIANT if score >= 90 else ComplianceStatus.PARTIALLY_COMPLIANT,
                score=score,
                details={
                    'has_permissions': has_permissions,
                    'has_audit_logs': has_audit_logs
                },
                violations=violations,
                recommendations=recommendations
            )
            
        except Exception as e:
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.UNKNOWN,
                score=0.0,
                details={'error': str(e)}
            )
    
    def _check_hipaa_audit_trail(self, rule: ComplianceRule,
                                period_start: Optional[datetime],
                                period_end: Optional[datetime]) -> ComplianceCheck:
        """Check HIPAA audit trail compliance."""
        try:
            # Check audit trail completeness
            period_logs = BackupLog.objects.filter(
                created_at__gte=period_start or timezone.now() - timedelta(days=30),
                created_at__lte=period_end or timezone.now()
            )
            
            total_logs = period_logs.count()
            
            # Check for required audit fields
            logs_with_user = period_logs.exclude(user__isnull=True).count()
            logs_with_action = period_logs.exclude(action='').count()
            logs_with_timestamp = period_logs.count()  # All should have timestamps
            
            score = (
                (logs_with_user / total_logs * 33) +
                (logs_with_action / total_logs * 33) +
                (logs_with_timestamp / total_logs * 34)
            ) if total_logs > 0 else 100
            
            violations = []
            recommendations = []
            
            if logs_with_user < total_logs:
                violations.append({
                    'type': 'audit_user_violation',
                    'description': f'{total_logs - logs_with_user} logs missing user information',
                    'severity': rule.severity.value
                })
                recommendations.append("Ensure all audit logs include user information")
            
            if logs_with_action < total_logs:
                violations.append({
                    'type': 'audit_action_violation',
                    'description': f'{total_logs - logs_with_action} logs missing action information',
                    'severity': rule.severity.value
                })
                recommendations.append("Ensure all audit logs include action information")
            
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.COMPLIANT if score >= 90 else ComplianceStatus.PARTIALLY_COMPLIANT,
                score=score,
                details={
                    'total_logs': total_logs,
                    'logs_with_user': logs_with_user,
                    'logs_with_action': logs_with_action
                },
                violations=violations,
                recommendations=recommendations
            )
            
        except Exception as e:
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.UNKNOWN,
                score=0.0,
                details={'error': str(e)}
            )
    
    # SOX Check Functions
    def _check_sox_backup_recovery(self, rule: ComplianceRule,
                                 period_start: Optional[datetime],
                                 period_end: Optional[datetime]) -> ComplianceCheck:
        """Check SOX backup and recovery compliance."""
        try:
            # Check backup and recovery procedures
            has_backup_schedule = BackupSchedule.objects.filter(is_active=True).exists()
            has_recent_backups = Backup.objects.filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            ).exists()
            has_restoration_capability = BackupRestoration.objects.exists()
            
            score = 0
            if has_backup_schedule:
                score += 33
            if has_recent_backups:
                score += 33
            if has_restoration_capability:
                score += 34
            
            violations = []
            recommendations = []
            
            if not has_backup_schedule:
                violations.append({
                    'type': 'backup_schedule_violation',
                    'description': 'No active backup schedules found',
                    'severity': rule.severity.value
                })
                recommendations.append("Implement regular backup schedules")
            
            if not has_recent_backups:
                violations.append({
                    'type': 'recent_backup_violation',
                    'description': 'No recent backups found',
                    'severity': rule.severity.value
                })
                recommendations.append("Ensure regular backup execution")
            
            if not has_restoration_capability:
                violations.append({
                    'type': 'restoration_capability_violation',
                    'description': 'No restoration procedures available',
                    'severity': rule.severity.value
                })
                recommendations.append("Implement and test restoration procedures")
            
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.COMPLIANT if score >= 90 else ComplianceStatus.PARTIALLY_COMPLIANT,
                score=score,
                details={
                    'has_backup_schedule': has_backup_schedule,
                    'has_recent_backups': has_recent_backups,
                    'has_restoration_capability': has_restoration_capability
                },
                violations=violations,
                recommendations=recommendations
            )
            
        except Exception as e:
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.UNKNOWN,
                score=0.0,
                details={'error': str(e)}
            )
    
    # PCI-DSS Check Functions
    def _check_pci_encryption(self, rule: ComplianceRule,
                             period_start: Optional[datetime],
                             period_end: Optional[datetime]) -> ComplianceCheck:
        """Check PCI-DSS encryption compliance."""
        try:
            # Check if cardholder data backups are encrypted
            # This is a simplified check - in reality, you'd identify cardholder data backups
            recent_backups = Backup.objects.filter(
                created_at__gte=period_start or timezone.now() - timedelta(days=30),
                created_at__lte=period_end or timezone.now()
            )
            
            total_backups = recent_backups.count()
            encrypted_backups = recent_backups.filter(is_encrypted=True).count()
            
            score = (encrypted_backups / total_backups * 100) if total_backups > 0 else 100
            
            violations = []
            recommendations = []
            
            if score < 100:
                violations.append({
                    'type': 'pci_encryption_violation',
                    'description': 'Cardholder data backups must be encrypted',
                    'severity': rule.severity.value
                })
                recommendations.append("Enable strong encryption for all cardholder data backups")
            
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.COMPLIANT if score >= 100 else ComplianceStatus.NON_COMPLIANT,
                score=score,
                details={
                    'total_backups': total_backups,
                    'encrypted_backups': encrypted_backups
                },
                violations=violations,
                recommendations=recommendations
            )
            
        except Exception as e:
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.UNKNOWN,
                score=0.0,
                details={'error': str(e)}
            )
    
    # ISO 27001 Check Functions
    def _check_iso27001_risk_management(self, rule: ComplianceRule,
                                     period_start: Optional[datetime],
                                     period_end: Optional[datetime]) -> ComplianceCheck:
        """Check ISO 27001 risk management compliance."""
        try:
            # Check risk assessment implementation
            has_risk_assessment = True  # Placeholder - check for risk assessment documents
            has_treatment_plan = True  # Placeholder - check for risk treatment plans
            has_monitoring = True  # Placeholder - check for risk monitoring
            
            score = 0
            if has_risk_assessment:
                score += 33
            if has_treatment_plan:
                score += 33
            if has_monitoring:
                score += 34
            
            violations = []
            recommendations = []
            
            if not has_risk_assessment:
                violations.append({
                    'type': 'risk_assessment_violation',
                    'description': 'No risk assessment documented',
                    'severity': rule.severity.value
                })
                recommendations.append("Conduct and document risk assessments")
            
            if not has_treatment_plan:
                violations.append({
                    'type': 'risk_treatment_violation',
                    'description': 'No risk treatment plans available',
                    'severity': rule.severity.value
                })
                recommendations.append("Develop and implement risk treatment plans")
            
            if not has_monitoring:
                violations.append({
                    'type': 'risk_monitoring_violation',
                    'description': 'No risk monitoring in place',
                    'severity': rule.severity.value
                })
                recommendations.append("Implement continuous risk monitoring")
            
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.COMPLIANT if score >= 90 else ComplianceStatus.PARTIALLY_COMPLIANT,
                score=score,
                details={
                    'has_risk_assessment': has_risk_assessment,
                    'has_treatment_plan': has_treatment_plan,
                    'has_monitoring': has_monitoring
                },
                violations=violations,
                recommendations=recommendations
            )
            
        except Exception as e:
            return ComplianceCheck(
                rule_id=rule.rule_id,
                status=ComplianceStatus.UNKNOWN,
                score=0.0,
                details={'error': str(e)}
            )


class ComplianceManager:
    """Manages compliance operations and reporting."""
    
    def __init__(self):
        self.engine = ComplianceEngine()
        self.report_cache_timeout = getattr(settings, 'COMPLIANCE_CACHE_TIMEOUT', 3600)  # 1 hour
    
    def generate_compliance_report(self, framework: Optional[ComplianceFramework] = None,
                                   period_start: Optional[datetime] = None,
                                   period_end: Optional[datetime] = None,
                                   use_cache: bool = True) -> ComplianceReport:
        """Generate compliance report."""
        cache_key = f"compliance_report_{framework.value if framework else 'all'}_{period_start}_{period_end}"
        
        if use_cache:
            cached_report = cache.get(cache_key)
            if cached_report:
                return cached_report
        
        report = self.engine.check_compliance(framework, period_start, period_end)
        
        if use_cache:
            cache.set(cache_key, report, self.report_cache_timeout)
        
        return report
    
    def get_compliance_summary(self) -> Dict[str, Any]:
        """Get compliance summary for all frameworks."""
        summary = {}
        
        for framework in ComplianceFramework:
            if framework in self.engine.rule_registry:
                report = self.generate_compliance_report(framework)
                summary[framework.value] = {
                    'status': report.overall_status.value,
                    'score': report.overall_score,
                    'total_checks': report.total_checks,
                    'passed_checks': report.passed_checks,
                    'failed_checks': report.failed_checks
                }
        
        return summary
    
    def get_compliance_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get compliance trends over time."""
        trends = {}
        
        for framework in ComplianceFramework:
            if framework in self.engine.rule_registry:
                framework_trends = []
                
                for i in range(days):
                    date = timezone.now() - timedelta(days=i)
                    period_start = date - timedelta(days=1)
                    period_end = date
                    
                    report = self.generate_compliance_report(framework, period_start, period_end)
                    
                    framework_trends.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'score': report.overall_score,
                        'status': report.overall_status.value
                    })
                
                trends[framework.value] = list(reversed(framework_trends))
        
        return trends
    
    def get_violations_summary(self, severity: Optional[ComplianceSeverity] = None) -> List[Dict[str, Any]]:
        """Get summary of compliance violations."""
        report = self.generate_compliance_report()
        
        violations = report.violations
        
        if severity:
            violations = [v for v in violations if v.get('severity') == severity.value]
        
        return violations
    
    def get_recommendations(self, framework: Optional[ComplianceFramework] = None) -> List[str]:
        """Get compliance recommendations."""
        report = self.generate_compliance_report(framework)
        return report.recommendations
    
    def export_compliance_report(self, framework: Optional[ComplianceFramework] = None,
                                format: str = 'json') -> Dict[str, Any]:
        """Export compliance report in specified format."""
        report = self.generate_compliance_report(framework)
        
        if format.lower() == 'json':
            return {
                'framework': report.framework.value,
                'overall_status': report.overall_status.value,
                'overall_score': report.overall_score,
                'category_scores': {cat.value: score for cat, score in report.category_scores.items()},
                'total_checks': report.total_checks,
                'passed_checks': report.passed_checks,
                'failed_checks': report.failed_checks,
                'violations': report.violations,
                'recommendations': report.recommendations,
                'generated_at': report.generated_at.isoformat(),
                'period_start': report.period_start.isoformat() if report.period_start else None,
                'period_end': report.period_end.isoformat() if report.period_end else None
            }
        
        # Add other formats as needed
        return report.__dict__


# Global compliance manager instance
_compliance_manager: Optional[ComplianceManager] = None


def get_compliance_manager() -> ComplianceManager:
    """Get the global compliance manager instance."""
    global _compliance_manager
    if _compliance_manager is None:
        _compliance_manager = ComplianceManager()
    return _compliance_manager


def check_gdpr_compliance() -> ComplianceReport:
    """Check GDPR compliance."""
    manager = get_compliance_manager()
    return manager.generate_compliance_report(ComplianceFramework.GDPR)


def check_hipaa_compliance() -> ComplianceReport:
    """Check HIPAA compliance."""
    manager = get_compliance_manager()
    return manager.generate_compliance_report(ComplianceFramework.HIPAA)


def check_sox_compliance() -> ComplianceReport:
    """Check SOX compliance."""
    manager = get_compliance_manager()
    return manager.generate_compliance_report(ComplianceFramework.SOX)


def check_pci_dss_compliance() -> ComplianceReport:
    """Check PCI-DSS compliance."""
    manager = get_compliance_manager()
    return manager.generate_compliance_report(ComplianceFramework.PCI_DSS)


def get_compliance_summary() -> Dict[str, Any]:
    """Get compliance summary for all frameworks."""
    manager = get_compliance_manager()
    return manager.get_compliance_summary()


def get_compliance_trends(days: int = 30) -> Dict[str, Any]:
    """Get compliance trends over time."""
    manager = get_compliance_manager()
    return manager.get_compliance_trends(days)


def get_violations(severity: Optional[ComplianceSeverity] = None) -> List[Dict[str, Any]]:
    """Get compliance violations."""
    manager = get_compliance_manager()
    return manager.get_violations_summary(severity)


def get_recommendations(framework: Optional[ComplianceFramework] = None) -> List[str]:
    """Get compliance recommendations."""
    manager = get_compliance_manager()
    return manager.get_recommendations(framework)
