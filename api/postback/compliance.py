"""
compliance.py – Compliance system for postback module.

Provides comprehensive compliance functionality including:
- GDPR compliance
- Data retention policies
- Audit trail management
- Compliance reporting
"""
from typing import Set
import time
import logging
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import threading
import json

from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model

from .audit_logs import audit_logger, AuditAction, AuditResource, AuditSeverity
from .integ_exceptions import IntegrationException

logger = logging.getLogger(__name__)
User = get_user_model()


class ComplianceStandard(Enum):
    """Compliance standard enumeration."""
    GDPR = "gdpr"
    CCPA = "ccpa"
    HIPAA = "hipaa"
    SOX = "sox"
    PCI_DSS = "pci_dss"
    ISO_27001 = "iso_27001"


class DataCategory(Enum):
    """Data category enumeration."""
    PERSONAL = "personal"
    SENSITIVE = "sensitive"
    FINANCIAL = "financial"
    HEALTH = "health"
    ANALYTICS = "analytics"
    SYSTEM = "system"


class RetentionPeriod(Enum):
    """Retention period enumeration."""
    IMMEDIATE = "immediate"
    DAYS_30 = "30_days"
    DAYS_90 = "90_days"
    DAYS_180 = "180_days"
    DAYS_365 = "365_days"
    YEARS_2 = "2_years"
    YEARS_5 = "5_years"
    YEARS_7 = "7_years"
    YEARS_10 = "10_years"
    PERMANENT = "permanent"


@dataclass
class ComplianceRule:
    """Compliance rule data structure."""
    id: str
    standard: ComplianceStandard
    rule_type: str
    description: str
    data_category: DataCategory
    retention_period: RetentionPeriod
    requires_consent: bool = False
    requires_encryption: bool = False
    requires_audit: bool = True
    enabled: bool = True
    conditions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'standard': self.standard.value,
            'rule_type': self.rule_type,
            'description': self.description,
            'data_category': self.data_category.value,
            'retention_period': self.retention_period.value,
            'requires_consent': self.requires_consent,
            'requires_encryption': self.requires_encryption,
            'requires_audit': self.requires_audit,
            'enabled': self.enabled,
            'conditions': self.conditions,
            'metadata': self.metadata,
        }


@dataclass
class ConsentRecord:
    """Consent record data structure."""
    id: str
    user_id: int
    data_category: DataCategory
    consent_given: bool
    consent_type: str
    purpose: str
    legal_basis: str
    given_at: datetime = field(default_factory=timezone.now)
    expires_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_valid(self) -> bool:
        """Check if consent is valid."""
        if not self.consent_given:
            return False
        
        if self.withdrawn_at:
            return False
        
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'data_category': self.data_category.value,
            'consent_given': self.consent_given,
            'consent_type': self.consent_type,
            'purpose': self.purpose,
            'legal_basis': self.legal_basis,
            'given_at': self.given_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'withdrawn_at': self.withdrawn_at.isoformat() if self.withdrawn_at else None,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'metadata': self.metadata,
        }


@dataclass
class RetentionPolicy:
    """Data retention policy data structure."""
    id: str
    data_category: DataCategory
    retention_period: RetentionPeriod
    action_after_retention: str  # delete, archive, anonymize
    conditions: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = field(default_factory=timezone.now)
    last_applied: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'data_category': self.data_category.value,
            'retention_period': self.retention_period.value,
            'action_after_retention': self.action_after_retention,
            'conditions': self.conditions,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat(),
            'last_applied': self.last_applied.isoformat() if self.last_applied else None,
            'metadata': self.metadata,
        }


class ConsentManager:
    """
    Consent manager for compliance.
    
    Handles user consent tracking and validation.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.consent_records: Dict[str, ConsentRecord] = {}
        self.consent_cache = cache
        self.consent_ttl = getattr(settings, 'CONSENT_CACHE_TTL', 3600)
    
    def record_consent(self, user_id: int, data_category: DataCategory,
                      consent_type: str, purpose: str, legal_basis: str,
                      expires_after_days: int = None, ip_address: str = None,
                      user_agent: str = None, metadata: Dict[str, Any] = None) -> str:
        """
        Record user consent.
        
        Args:
            user_id: User ID
            data_category: Data category
            consent_type: Type of consent
            purpose: Purpose of data processing
            legal_basis: Legal basis for processing
            expires_after_days: Days until consent expires
            ip_address: User IP address
            user_agent: User agent string
            metadata: Additional metadata
            
        Returns:
            Consent record ID
        """
        import uuid
        
        # Check for existing consent
        existing_consent = self.get_active_consent(user_id, data_category)
        if existing_consent:
            # Withdraw existing consent
            existing_consent.withdrawn_at = timezone.now()
            self._store_consent_record(existing_consent)
        
        # Create new consent record
        consent_id = f"consent_{uuid.uuid4().hex[:12]}"
        
        expires_at = None
        if expires_after_days:
            expires_at = timezone.now() + timedelta(days=expires_after_days)
        
        consent = ConsentRecord(
            id=consent_id,
            user_id=user_id,
            data_category=data_category,
            consent_given=True,
            consent_type=consent_type,
            purpose=purpose,
            legal_basis=legal_basis,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {}
        )
        
        # Store consent
        self._store_consent_record(consent)
        
        # Log consent
        audit_logger.log_action(
            action=AuditAction.CREATE,
            resource=AuditResource.USER,
            resource_id=str(user_id),
            user_id=user_id,
            details={
                'action': 'consent_given',
                'data_category': data_category.value,
                'consent_type': consent_type,
                'purpose': purpose,
                'legal_basis': legal_basis,
                'consent_id': consent_id,
            },
            severity=AuditSeverity.MEDIUM
        )
        
        self.logger.info(f"Consent recorded: {consent_id} for user {user_id}")
        return consent_id
    
    def withdraw_consent(self, user_id: int, data_category: DataCategory,
                        reason: str = None, ip_address: str = None) -> bool:
        """
        Withdraw user consent.
        
        Args:
            user_id: User ID
            data_category: Data category
            reason: Reason for withdrawal
            ip_address: User IP address
            
        Returns:
            True if withdrawn successfully
        """
        consent = self.get_active_consent(user_id, data_category)
        if not consent:
            return False
        
        # Update consent
        consent.consent_given = False
        consent.withdrawn_at = timezone.now()
        
        if reason:
            consent.metadata['withdrawal_reason'] = reason
        
        if ip_address:
            consent.metadata['withdrawal_ip'] = ip_address
        
        # Store updated consent
        self._store_consent_record(consent)
        
        # Log withdrawal
        audit_logger.log_action(
            action=AuditAction.UPDATE,
            resource=AuditResource.USER,
            resource_id=str(user_id),
            user_id=user_id,
            details={
                'action': 'consent_withdrawn',
                'data_category': data_category.value,
                'reason': reason,
                'consent_id': consent.id,
            },
            severity=AuditSeverity.MEDIUM
        )
        
        self.logger.info(f"Consent withdrawn: {consent.id} for user {user_id}")
        return True
    
    def check_consent(self, user_id: int, data_category: DataCategory,
                      purpose: str = None) -> bool:
        """
        Check if user has valid consent.
        
        Args:
            user_id: User ID
            data_category: Data category
            purpose: Specific purpose (optional)
            
        Returns:
            True if consent is valid
        """
        consent = self.get_active_consent(user_id, data_category)
        if not consent:
            return False
        
        # Check purpose if specified
        if purpose and consent.purpose != purpose:
            return False
        
        return consent.is_valid()
    
    def get_active_consent(self, user_id: int, data_category: DataCategory) -> Optional[ConsentRecord]:
        """Get active consent for user and category."""
        # Check cache first
        cache_key = f"consent_{user_id}_{data_category.value}"
        cached_consent = self.consent_cache.get(cache_key)
        
        if cached_consent:
            consent = ConsentRecord(**cached_consent)
            if consent.is_valid():
                return consent
            else:
                # Remove invalid consent from cache
                self.consent_cache.delete(cache_key)
        
        # Check stored records
        user_consents = [
            consent for consent in self.consent_records.values()
            if consent.user_id == user_id and consent.data_category == data_category
        ]
        
        # Sort by given date (most recent first)
        user_consents.sort(key=lambda c: c.given_at, reverse=True)
        
        for consent in user_consents:
            if consent.is_valid():
                # Cache valid consent
                self.consent_cache.set(cache_key, consent.to_dict(), timeout=self.consent_ttl)
                return consent
        
        return None
    
    def get_user_consents(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all consents for user."""
        user_consents = [
            consent for consent in self.consent_records.values()
            if consent.user_id == user_id
        ]
        
        # Sort by given date (most recent first)
        user_consents.sort(key=lambda c: c.given_at, reverse=True)
        
        return [consent.to_dict() for consent in user_consents]
    
    def _store_consent_record(self, consent: ConsentRecord):
        """Store consent record."""
        self.consent_records[consent.id] = consent
        
        # Update cache
        cache_key = f"consent_{consent.user_id}_{consent.data_category.value}"
        if consent.is_valid():
            self.consent_cache.set(cache_key, consent.to_dict(), timeout=self.consent_ttl)
        else:
            self.consent_cache.delete(cache_key)


class RetentionManager:
    """
    Data retention manager for compliance.
    
    Handles data retention policies and cleanup.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.retention_policies: Dict[str, RetentionPolicy] = {}
        self.cleanup_running = False
        self.cleanup_thread = None
        self.cleanup_interval = getattr(settings, 'RETENTION_CLEANUP_INTERVAL', 86400)  # 24 hours
        self._setup_default_policies()
    
    def _setup_default_policies(self):
        """Setup default retention policies."""
        default_policies = [
            RetentionPolicy(
                id="personal_data_30_days",
                data_category=DataCategory.PERSONAL,
                retention_period=RetentionPeriod.DAYS_30,
                action_after_retention="delete"
            ),
            RetentionPolicy(
                id="sensitive_data_90_days",
                data_category=DataCategory.SENSITIVE,
                retention_period=RetentionPeriod.DAYS_90,
                action_after_retention="delete"
            ),
            RetentionPolicy(
                id="financial_data_7_years",
                data_category=DataCategory.FINANCIAL,
                retention_period=RetentionPeriod.YEARS_7,
                action_after_retention="archive"
            ),
            RetentionPolicy(
                id="analytics_data_2_years",
                data_category=DataCategory.ANALYTICS,
                retention_period=RetentionPeriod.YEARS_2,
                action_after_retention="delete"
            ),
            RetentionPolicy(
                id="system_data_permanent",
                data_category=DataCategory.SYSTEM,
                retention_period=RetentionPeriod.PERMANENT,
                action_after_retention="archive"
            ),
        ]
        
        for policy in default_policies:
            self.retention_policies[policy.id] = policy
    
    def add_retention_policy(self, policy: RetentionPolicy):
        """Add retention policy."""
        self.retention_policies[policy.id] = policy
        self.logger.info(f"Retention policy added: {policy.id}")
    
    def remove_retention_policy(self, policy_id: str):
        """Remove retention policy."""
        if policy_id in self.retention_policies:
            del self.retention_policies[policy_id]
            self.logger.info(f"Retention policy removed: {policy_id}")
    
    def get_retention_policy(self, data_category: DataCategory) -> Optional[RetentionPolicy]:
        """Get retention policy for data category."""
        for policy in self.retention_policies.values():
            if policy.data_category == data_category and policy.enabled:
                return policy
        return None
    
    def should_retain(self, data_category: DataCategory, created_at: datetime,
                       conditions: Dict[str, Any] = None) -> bool:
        """
        Check if data should be retained.
        
        Args:
            data_category: Data category
            created_at: Data creation time
            conditions: Additional conditions
            
        Returns:
            True if data should be retained
        """
        policy = self.get_retention_policy(data_category)
        if not policy:
            return True
        
        # Check retention period
        if policy.retention_period == RetentionPeriod.PERMANENT:
            return True
        
        retention_days = self._get_retention_days(policy.retention_period)
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        if created_at > cutoff_date:
            return True
        
        # Check additional conditions
        if policy.conditions:
            return self._evaluate_conditions(policy.conditions, conditions or {})
        
        return False
    
    def apply_retention_policy(self, data_category: DataCategory, data_id: str,
                             created_at: datetime, conditions: Dict[str, Any] = None) -> bool:
        """
        Apply retention policy to data.
        
        Args:
            data_category: Data category
            data_id: Data identifier
            created_at: Data creation time
            conditions: Additional conditions
            
        Returns:
            True if action was taken
        """
        policy = self.get_retention_policy(data_category)
        if not policy:
            return False
        
        if self.should_retain(data_category, created_at, conditions):
            return False
        
        # Apply retention action
        action_taken = self._apply_retention_action(policy, data_id, data_category)
        
        if action_taken:
            policy.last_applied = timezone.now()
            
            # Log retention action
            audit_logger.log_action(
                action=AuditAction.DELETE,
                resource=AuditResource.SYSTEM,
                resource_id=data_id,
                details={
                    'action': 'retention_policy_applied',
                    'data_category': data_category.value,
                    'policy_id': policy.id,
                    'action_type': policy.action_after_retention,
                    'created_at': created_at.isoformat(),
                },
                severity=AuditSeverity.MEDIUM
            )
        
        return action_taken
    
    def _get_retention_days(self, period: RetentionPeriod) -> int:
        """Get retention days from period."""
        period_days = {
            RetentionPeriod.IMMEDIATE: 0,
            RetentionPeriod.DAYS_30: 30,
            RetentionPeriod.DAYS_90: 90,
            RetentionPeriod.DAYS_180: 180,
            RetentionPeriod.DAYS_365: 365,
            RetentionPeriod.YEARS_2: 730,
            RetentionPeriod.YEARS_5: 1825,
            RetentionPeriod.YEARS_7: 2555,
            RetentionPeriod.YEARS_10: 3650,
            RetentionPeriod.PERMANENT: -1,
        }
        return period_days.get(period, 365)
    
    def _evaluate_conditions(self, policy_conditions: Dict[str, Any],
                           data_conditions: Dict[str, Any]) -> bool:
        """Evaluate retention conditions."""
        for key, expected_value in policy_conditions.items():
            actual_value = data_conditions.get(key)
            if actual_value != expected_value:
                return False
        return True
    
    def _apply_retention_action(self, policy: RetentionPolicy, data_id: str,
                              data_category: DataCategory) -> bool:
        """Apply retention action."""
        try:
            if policy.action_after_retention == "delete":
                # This would delete the actual data
                # For now, just log the action
                self.logger.info(f"Would delete data: {data_id} ({data_category.value})")
                return True
            
            elif policy.action_after_retention == "archive":
                # This would archive the data
                self.logger.info(f"Would archive data: {data_id} ({data_category.value})")
                return True
            
            elif policy.action_after_retention == "anonymize":
                # This would anonymize the data
                self.logger.info(f"Would anonymize data: {data_id} ({data_category.value})")
                return True
            
            else:
                self.logger.warning(f"Unknown retention action: {policy.action_after_retention}")
                return False
        
        except Exception as e:
            self.logger.error(f"Error applying retention action: {str(e)}")
            return False
    
    def start_cleanup_scheduler(self):
        """Start cleanup scheduler."""
        if self.cleanup_running:
            return
        
        self.cleanup_running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        self.logger.info("Retention cleanup scheduler started")
    
    def stop_cleanup_scheduler(self):
        """Stop cleanup scheduler."""
        if not self.cleanup_running:
            return
        
        self.cleanup_running = False
        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)
        
        self.logger.info("Retention cleanup scheduler stopped")
    
    def _cleanup_loop(self):
        """Cleanup scheduler loop."""
        while self.cleanup_running:
            try:
                self._perform_cleanup()
                time.sleep(self.cleanup_interval)
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {str(e)}")
                time.sleep(300)  # Wait 5 minutes on error
    
    def _perform_cleanup(self):
        """Perform retention cleanup."""
        # This would scan all data and apply retention policies
        # For now, just log the action
        self.logger.info("Performing retention cleanup")
        
        for policy in self.retention_policies.values():
            if policy.enabled:
                self.logger.debug(f"Checking retention policy: {policy.id}")


class ComplianceManager:
    """
    Main compliance manager.
    
    Orchestrates compliance checking, reporting,
    and policy enforcement.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.consent_manager = ConsentManager()
        self.retention_manager = RetentionManager()
        self.compliance_rules: Dict[str, ComplianceRule] = []
        self.enabled_standards: Set[ComplianceStandard] = set()
        self._setup_default_rules()
        self._setup_enabled_standards()
    
    def _setup_default_rules(self):
        """Setup default compliance rules."""
        default_rules = [
            ComplianceRule(
                id="gdpr_consent",
                standard=ComplianceStandard.GDPR,
                rule_type="consent_required",
                description="GDPR requires explicit consent for personal data processing",
                data_category=DataCategory.PERSONAL,
                retention_period=RetentionPeriod.DAYS_365,
                requires_consent=True,
                requires_audit=True
            ),
            ComplianceRule(
                id="gdpr_encryption",
                standard=ComplianceStandard.GDPR,
                rule_type="encryption_required",
                description="GDPR requires encryption for sensitive personal data",
                data_category=DataCategory.SENSITIVE,
                retention_period=RetentionPeriod.DAYS_365,
                requires_encryption=True,
                requires_audit=True
            ),
            ComplianceRule(
                id="pci_data_protection",
                standard=ComplianceStandard.PCI_DSS,
                rule_type="data_protection",
                description="PCI DSS requires protection of cardholder data",
                data_category=DataCategory.FINANCIAL,
                retention_period=RetentionPeriod.YEARS_7,
                requires_encryption=True,
                requires_audit=True
            ),
        ]
        
        for rule in default_rules:
            self.compliance_rules.append(rule)
    
    def _setup_enabled_standards(self):
        """Setup enabled compliance standards."""
        enabled_standards = getattr(settings, 'COMPLIANCE_STANDARDS', ['GDPR'])
        
        for standard_str in enabled_standards:
            try:
                standard = ComplianceStandard(standard_str.lower())
                self.enabled_standards.add(standard)
            except ValueError:
                self.logger.warning(f"Unknown compliance standard: {standard_str}")
    
    def check_compliance(self, standard: ComplianceStandard = None,
                          data_category: DataCategory = None) -> Dict[str, Any]:
        """
        Check compliance status.
        
        Args:
            standard: Specific standard to check
            data_category: Specific data category to check
            
        Returns:
            Compliance status report
        """
        report = {
            'timestamp': timezone.now().isoformat(),
            'overall_compliant': True,
            'issues': [],
            'checked_rules': [],
            'recommendations': [],
        }
        
        # Filter rules to check
        rules_to_check = self.compliance_rules
        if standard:
            rules_to_check = [r for r in rules_to_check if r.standard == standard]
        if data_category:
            rules_to_check = [r for r in rules_to_check if r.data_category == data_category]
        
        # Check each rule
        for rule in rules_to_check:
            if not rule.enabled:
                continue
            
            rule_result = self._check_rule(rule)
            report['checked_rules'].append(rule_result)
            
            if not rule_result['compliant']:
                report['overall_compliant'] = False
                report['issues'].append(rule_result['issue'])
                report['recommendations'].append(rule_result['recommendation'])
        
        return report
    
    def _check_rule(self, rule: ComplianceRule) -> Dict[str, Any]:
        """Check individual compliance rule."""
        result = {
            'rule_id': rule.id,
            'standard': rule.standard.value,
            'rule_type': rule.rule_type,
            'compliant': True,
            'issue': None,
            'recommendation': None,
        }
        
        try:
            if rule.rule_type == "consent_required":
                # Check if consent management is working
                if not self.consent_manager.consent_records:
                    result['compliant'] = False
                    result['issue'] = "No consent records found"
                    result['recommendation'] = "Implement consent management system"
            
            elif rule.rule_type == "encryption_required":
                # Check if encryption is available
                try:
                    from .encryption import data_encryptor
                    if not data_encryptor.key_manager.get_current_key():
                        result['compliant'] = False
                        result['issue'] = "No encryption keys available"
                        result['recommendation'] = "Set up encryption key management"
                except ImportError:
                    result['compliant'] = False
                    result['issue'] = "Encryption system not available"
                    result['recommendation'] = "Install cryptography dependencies"
            
            elif rule.rule_type == "data_protection":
                # Check data protection measures
                if not self.retention_manager.retention_policies:
                    result['compliant'] = False
                    result['issue'] = "No retention policies defined"
                    result['recommendation'] = "Define data retention policies"
            
            elif rule.rule_type == "audit_required":
                # Check if audit logging is working
                if not audit_logger.audit_logs:
                    result['compliant'] = False
                    result['issue'] = "No audit logs found"
                    result['recommendation'] = "Enable audit logging system"
        
        except Exception as e:
            result['compliant'] = False
            result['issue'] = f"Error checking rule: {str(e)}"
            result['recommendation'] = "Review rule configuration"
        
        return result
    
    def generate_compliance_report(self, standards: List[ComplianceStandard] = None) -> Dict[str, Any]:
        """
        Generate comprehensive compliance report.
        
        Args:
            standards: Standards to include in report
            
        Returns:
            Compliance report
        """
        standards_to_check = standards or list(self.enabled_standards)
        
        report = {
            'generated_at': timezone.now().isoformat(),
            'standards': {},
            'overall_compliant': True,
            'total_issues': 0,
            'summary': {},
        }
        
        for standard in standards_to_check:
            standard_report = self.check_compliance(standard)
            report['standards'][standard.value] = standard_report
            
            if not standard_report['overall_compliant']:
                report['overall_compliant'] = False
            
            report['total_issues'] += len(standard_report['issues'])
        
        # Generate summary
        report['summary'] = {
            'checked_standards': len(standards_to_check),
            'compliant_standards': len([
                s for s in report['standards'].values()
                if s['overall_compliant']
            ]),
            'total_issues': report['total_issues'],
            'critical_issues': len([
                issue for standard in report['standards'].values()
                for issue in standard['issues']
                if 'critical' in issue.lower()
            ]),
        }
        
        return report
    
    def get_user_compliance_status(self, user_id: int) -> Dict[str, Any]:
        """Get compliance status for specific user."""
        user_consents = self.consent_manager.get_user_consents(user_id)
        
        status = {
            'user_id': user_id,
            'timestamp': timezone.now().isoformat(),
            'consent_status': {},
            'compliant': True,
            'issues': [],
        }
        
        # Check consent for each data category
        for data_category in DataCategory:
            consent = self.consent_manager.get_active_consent(user_id, data_category)
            
            if consent:
                status['consent_status'][data_category.value] = {
                    'has_consent': True,
                    'consent_type': consent.consent_type,
                    'purpose': consent.purpose,
                    'given_at': consent.given_at.isoformat(),
                    'expires_at': consent.expires_at.isoformat() if consent.expires_at else None,
                }
            else:
                status['consent_status'][data_category.value] = {
                    'has_consent': False,
                    'required': self._is_consent_required(data_category),
                }
                
                if self._is_consent_required(data_category):
                    status['compliant'] = False
                    status['issues'].append(f"Missing consent for {data_category.value}")
        
        return status
    
    def _is_consent_required(self, data_category: DataCategory) -> bool:
        """Check if consent is required for data category."""
        for rule in self.compliance_rules:
            if (rule.data_category == data_category and
                rule.enabled and
                rule.requires_consent and
                rule.standard in self.enabled_standards):
                return True
        return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get compliance statistics."""
        total_consents = len(self.consent_manager.consent_records)
        active_consents = len([
            c for c in self.consent_manager.consent_records.values()
            if c.is_valid()
        ])
        
        total_policies = len(self.retention_manager.retention_policies)
        active_policies = len([
            p for p in self.retention_manager.retention_policies.values()
            if p.enabled
        ])
        
        return {
            'consent_statistics': {
                'total_consents': total_consents,
                'active_consents': active_consents,
                'withdrawn_consents': total_consents - active_consents,
            },
            'retention_statistics': {
                'total_policies': total_policies,
                'active_policies': active_policies,
                'cleanup_running': self.retention_manager.cleanup_running,
            },
            'compliance_rules': len(self.compliance_rules),
            'enabled_standards': [s.value for s in self.enabled_standards],
        }


# Global compliance manager instance
compliance_manager = ComplianceManager()


# Convenience functions
def record_user_consent(user_id: int, data_category: DataCategory, consent_type: str,
                         purpose: str, legal_basis: str, expires_after_days: int = None,
                         ip_address: str = None, user_agent: str = None) -> str:
    """Record user consent."""
    return compliance_manager.consent_manager.record_consent(
        user_id, data_category, consent_type, purpose, legal_basis,
        expires_after_days, ip_address, user_agent
    )


def withdraw_user_consent(user_id: int, data_category: DataCategory,
                           reason: str = None, ip_address: str = None) -> bool:
    """Withdraw user consent."""
    return compliance_manager.consent_manager.withdraw_consent(
        user_id, data_category, reason, ip_address
    )


def check_user_consent(user_id: int, data_category: DataCategory,
                        purpose: str = None) -> bool:
    """Check user consent."""
    return compliance_manager.consent_manager.check_consent(
        user_id, data_category, purpose
    )


def check_compliance(standard: ComplianceStandard = None,
                     data_category: DataCategory = None) -> Dict[str, Any]:
    """Check compliance status."""
    return compliance_manager.check_compliance(standard, data_category)


def generate_compliance_report(standards: List[ComplianceStandard] = None) -> Dict[str, Any]:
    """Generate compliance report."""
    return compliance_manager.generate_compliance_report(standards)


def get_user_compliance_status(user_id: int) -> Dict[str, Any]:
    """Get user compliance status."""
    return compliance_manager.get_user_compliance_status(user_id)


def get_compliance_statistics() -> Dict[str, Any]:
    """Get compliance statistics."""
    return compliance_manager.get_statistics()
