"""
Security Compliance Module
Compliance management and reporting system
"""

import logging
from typing import Dict, List, Any, Optional, Type, Union
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models
from django.core.cache import cache
from django.conf import settings

from .models import SecurityLog, SecurityIncident
from .utils import SecurityUtils
from .helpers import TimeHelper

User = get_user_model()
logger = logging.getLogger('security.compliance')


class ComplianceStandard:
    """Compliance standards"""
    GDPR = 'gdpr'
    HIPAA = 'hipaa'
    PCI_DSS = 'pci_dss'
    SOX = 'sox'
    ISO_27001 = 'iso_27001'
    NIST = 'nist'
    CIS = 'cis'


class ComplianceStatus:
    """Compliance status"""
    COMPLIANT = 'compliant'
    NON_COMPLIANT = 'non_compliant'
    PARTIALLY_COMPLIANT = 'partially_compliant'
    UNKNOWN = 'unknown'


class ComplianceRequirement:
    """Compliance requirement"""
    
    def __init__(self, id: str, name: str, description: str, standard: str,
                 category: str, mandatory: bool = True):
        self.id = id
        self.name = name
        self.description = description
        self.standard = standard
        self.category = category
        self.mandatory = mandatory


class ComplianceFramework:
    """Compliance framework implementation"""
    
    def __init__(self):
        self.requirements = self._initialize_requirements()
        self.cache_timeout = 3600  # 1 hour
    
    def _initialize_requirements(self) -> Dict[str, List[ComplianceRequirement]]:
        """Initialize compliance requirements"""
        requirements = {}
        
        # GDPR Requirements
        requirements[ComplianceStandard.GDPR] = [
            ComplianceRequirement(
                'gdpr_001', 'Data Protection Impact Assessment',
                'Conduct DPIA for high-risk processing activities',
                ComplianceStandard.GDPR, 'risk_assessment', True
            ),
            ComplianceRequirement(
                'gdpr_002', 'Data Breach Notification',
                'Notify supervisory authority within 72 hours of breach',
                ComplianceStandard.GDPR, 'incident_response', True
            ),
            ComplianceRequirement(
                'gdpr_003', 'Right to be Forgotten',
                'Implement data deletion mechanisms',
                ComplianceStandard.GDPR, 'data_management', True
            ),
            ComplianceRequirement(
                'gdpr_004', 'Data Portability',
                'Provide data in machine-readable format',
                ComplianceStandard.GDPR, 'data_management', True
            ),
            ComplianceRequirement(
                'gdpr_005', 'Consent Management',
                'Obtain explicit consent for data processing',
                ComplianceStandard.GDPR, 'consent', True
            ),
        ]
        
        # PCI DSS Requirements
        requirements[ComplianceStandard.PCI_DSS] = [
            ComplianceRequirement(
                'pci_001', 'Network Security',
                'Maintain secure network and systems',
                ComplianceStandard.PCI_DSS, 'network_security', True
            ),
            ComplianceRequirement(
                'pci_002', 'Data Protection',
                'Protect cardholder data',
                ComplianceStandard.PCI_DSS, 'data_protection', True
            ),
            ComplianceRequirement(
                'pci_003', 'Vulnerability Management',
                'Maintain vulnerability management program',
                ComplianceStandard.PCI_DSS, 'vulnerability_management', True
            ),
            ComplianceRequirement(
                'pci_004', 'Access Control',
                'Implement strong access control measures',
                ComplianceStandard.PCI_DSS, 'access_control', True
            ),
            ComplianceRequirement(
                'pci_005', 'Network Monitoring',
                'Regularly monitor and test networks',
                ComplianceStandard.PCI_DSS, 'monitoring', True
            ),
            ComplianceRequirement(
                'pci_006', 'Information Security Policy',
                'Maintain information security policy',
                ComplianceStandard.PCI_DSS, 'policy', True
            ),
        ]
        
        # ISO 27001 Requirements
        requirements[ComplianceStandard.ISO_27001] = [
            ComplianceRequirement(
                'iso_001', 'Information Security Policy',
                'Document and implement information security policy',
                ComplianceStandard.ISO_27001, 'policy', True
            ),
            ComplianceRequirement(
                'iso_002', 'Risk Assessment',
                'Conduct risk assessment and treatment',
                ComplianceStandard.ISO_27001, 'risk_assessment', True
            ),
            ComplianceRequirement(
                'iso_003', 'Access Control',
                'Implement access control policy',
                ComplianceStandard.ISO_27001, 'access_control', True
            ),
            ComplianceRequirement(
                'iso_004', 'Cryptography',
                'Use cryptography to protect information',
                ComplianceStandard.ISO_27001, 'cryptography', True
            ),
            ComplianceRequirement(
                'iso_005', 'Physical Security',
                'Implement physical and environmental security',
                ComplianceStandard.ISO_27001, 'physical_security', True
            ),
        ]
        
        # NIST Requirements
        requirements[ComplianceStandard.NIST] = [
            ComplianceRequirement(
                'nist_001', 'Access Control',
                'Limit access to authorized users',
                ComplianceStandard.NIST, 'access_control', True
            ),
            ComplianceRequirement(
                'nist_002', 'Audit and Accountability',
                'Create and retain audit trails',
                ComplianceStandard.NIST, 'audit', True
            ),
            ComplianceRequirement(
                'nist_003', 'Awareness and Training',
                'Provide security awareness training',
                ComplianceStandard.NIST, 'training', True
            ),
            ComplianceRequirement(
                'nist_004', 'Incident Response',
                'Establish incident response capabilities',
                ComplianceStandard.NIST, 'incident_response', True
            ),
            ComplianceRequirement(
                'nist_005', 'Risk Assessment',
                'Conduct regular risk assessments',
                ComplianceStandard.NIST, 'risk_assessment', True
            ),
        ]
        
        return requirements
    
    def get_requirements(self, standard: str) -> List[ComplianceRequirement]:
        """Get requirements for a standard"""
        return self.requirements.get(standard, [])
    
    def get_all_standards(self) -> List[str]:
        """Get all available standards"""
        return list(self.requirements.keys())


class ComplianceAssessment:
    """Compliance assessment engine"""
    
    def __init__(self, framework: ComplianceFramework):
        self.framework = framework
        self.cache_timeout = 3600  # 1 hour
    
    def assess_compliance(self, standard: str, period_days: int = 30) -> Dict[str, Any]:
        """Assess compliance for a standard"""
        cache_key = f"compliance_assessment_{standard}_{period_days}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        requirements = self.framework.get_requirements(standard)
        assessment_results = []
        
        for requirement in requirements:
            result = self._assess_requirement(requirement, period_days)
            assessment_results.append(result)
        
        # Calculate overall compliance
        total_requirements = len(requirements)
        compliant_count = len([r for r in assessment_results if r['status'] == ComplianceStatus.COMPLIANT])
        partially_compliant_count = len([r for r in assessment_results if r['status'] == ComplianceStatus.PARTIALLY_COMPLIANT])
        
        overall_score = (compliant_count + (partially_compliant_count * 0.5)) / total_requirements * 100
        
        if overall_score >= 95:
            overall_status = ComplianceStatus.COMPLIANT
        elif overall_score >= 70:
            overall_status = ComplianceStatus.PARTIALLY_COMPLIANT
        else:
            overall_status = ComplianceStatus.NON_COMPLIANT
        
        assessment = {
            'standard': standard,
            'period_days': period_days,
            'overall_status': overall_status,
            'overall_score': overall_score,
            'total_requirements': total_requirements,
            'compliant_count': compliant_count,
            'partially_compliant_count': partially_compliant_count,
            'non_compliant_count': total_requirements - compliant_count - partially_compliant_count,
            'requirements': assessment_results,
            'assessed_at': timezone.now().isoformat()
        }
        
        cache.set(cache_key, assessment, self.cache_timeout)
        return assessment
    
    def _assess_requirement(self, requirement: ComplianceRequirement, period_days: int) -> Dict[str, Any]:
        """Assess individual requirement"""
        assessment = {
            'requirement_id': requirement.id,
            'name': requirement.name,
            'description': requirement.description,
            'category': requirement.category,
            'mandatory': requirement.mandatory,
            'status': ComplianceStatus.UNKNOWN,
            'score': 0,
            'evidence': [],
            'violations': []
        }
        
        # Assess based on requirement type
        if requirement.standard == ComplianceStandard.GDPR:
            assessment.update(self._assess_gdpr_requirement(requirement, period_days))
        elif requirement.standard == ComplianceStandard.PCI_DSS:
            assessment.update(self._assess_pci_requirement(requirement, period_days))
        elif requirement.standard == ComplianceStandard.ISO_27001:
            assessment.update(self._assess_iso_requirement(requirement, period_days))
        elif requirement.standard == ComplianceStandard.NIST:
            assessment.update(self._assess_nist_requirement(requirement, period_days))
        
        return assessment
    
    def _assess_gdpr_requirement(self, requirement: ComplianceRequirement, period_days: int) -> Dict[str, Any]:
        """Assess GDPR requirement"""
        if requirement.id == 'gdpr_001':  # DPIA
            return self._check_dpia_compliance(period_days)
        elif requirement.id == 'gdpr_002':  # Data breach notification
            return self._check_breach_notification_compliance(period_days)
        elif requirement.id == 'gdpr_003':  # Right to be forgotten
            return self._check_data_deletion_compliance(period_days)
        elif requirement.id == 'gdpr_004':  # Data portability
            return self._check_data_portability_compliance(period_days)
        elif requirement.id == 'gdpr_005':  # Consent management
            return self._check_consent_compliance(period_days)
        
        return {'status': ComplianceStatus.UNKNOWN, 'score': 0}
    
    def _assess_pci_requirement(self, requirement: ComplianceRequirement, period_days: int) -> Dict[str, Any]:
        """Assess PCI DSS requirement"""
        if requirement.id == 'pci_001':  # Network security
            return self._check_network_security_compliance(period_days)
        elif requirement.id == 'pci_002':  # Data protection
            return self._check_data_protection_compliance(period_days)
        elif requirement.id == 'pci_003':  # Vulnerability management
            return self._check_vulnerability_management_compliance(period_days)
        elif requirement.id == 'pci_004':  # Access control
            return self._check_access_control_compliance(period_days)
        elif requirement.id == 'pci_005':  # Network monitoring
            return self._check_network_monitoring_compliance(period_days)
        elif requirement.id == 'pci_006':  # Information security policy
            return self._check_security_policy_compliance(period_days)
        
        return {'status': ComplianceStatus.UNKNOWN, 'score': 0}
    
    def _assess_iso_requirement(self, requirement: ComplianceRequirement, period_days: int) -> Dict[str, Any]:
        """Assess ISO 27001 requirement"""
        if requirement.id == 'iso_001':  # Information security policy
            return self._check_security_policy_compliance(period_days)
        elif requirement.id == 'iso_002':  # Risk assessment
            return self._check_risk_assessment_compliance(period_days)
        elif requirement.id == 'iso_003':  # Access control
            return self._check_access_control_compliance(period_days)
        elif requirement.id == 'iso_004':  # Cryptography
            return self._check_cryptography_compliance(period_days)
        elif requirement.id == 'iso_005':  # Physical security
            return self._check_physical_security_compliance(period_days)
        
        return {'status': ComplianceStatus.UNKNOWN, 'score': 0}
    
    def _assess_nist_requirement(self, requirement: ComplianceRequirement, period_days: int) -> Dict[str, Any]:
        """Assess NIST requirement"""
        if requirement.id == 'nist_001':  # Access control
            return self._check_access_control_compliance(period_days)
        elif requirement.id == 'nist_002':  # Audit and accountability
            return self._check_audit_compliance(period_days)
        elif requirement.id == 'nist_003':  # Awareness and training
            return self._check_training_compliance(period_days)
        elif requirement.id == 'nist_004':  # Incident response
            return self._check_incident_response_compliance(period_days)
        elif requirement.id == 'nist_005':  # Risk assessment
            return self._check_risk_assessment_compliance(period_days)
        
        return {'status': ComplianceStatus.UNKNOWN, 'score': 0}
    
    def _check_dpia_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check DPIA compliance"""
        # Check if DPIA records exist
        dpia_count = SecurityLog.objects.filter(
            security_type='dpia_conducted',
            created_at__gte=timezone.now() - timedelta(days=period_days)
        ).count()
        
        if dpia_count > 0:
            return {
                'status': ComplianceStatus.COMPLIANT,
                'score': 100,
                'evidence': [f'Found {dpia_count} DPIA records'],
                'violations': []
            }
        else:
            return {
                'status': ComplianceStatus.NON_COMPLIANT,
                'score': 0,
                'evidence': [],
                'violations': ['No DPIA records found']
            }
    
    def _check_breach_notification_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check breach notification compliance"""
        # Check for data breaches and notification times
        breaches = SecurityLog.objects.filter(
            security_type='data_breach',
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        violations = []
        compliant_count = 0
        
        for breach in breaches:
            # Check if notification was sent within 72 hours
            notification = SecurityLog.objects.filter(
                security_type='breach_notification',
                metadata__breach_id=str(breach.id)
            ).first()
            
            if notification and (notification.created_at - breach.created_at).total_seconds() <= 72 * 3600:
                compliant_count += 1
            else:
                violations.append(f'Breach {breach.id} not notified within 72 hours')
        
        if breaches.exists():
            compliance_rate = compliant_count / breaches.count()
            score = compliance_rate * 100
            status = ComplianceStatus.COMPLIANT if score >= 95 else ComplianceStatus.PARTIALLY_COMPLIANT if score >= 70 else ComplianceStatus.NON_COMPLIANT
        else:
            score = 100  # No breaches means compliant
            status = ComplianceStatus.COMPLIANT
        
        return {
            'status': status,
            'score': score,
            'evidence': [f'Processed {breaches.count()} breaches, {compliant_count} compliant notifications'],
            'violations': violations
        }
    
    def _check_data_deletion_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check data deletion compliance"""
        # Check for data deletion requests and compliance
        deletion_requests = SecurityLog.objects.filter(
            security_type='data_deletion_request',
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        violations = []
        compliant_count = 0
        
        for request in deletion_requests:
            # Check if data was deleted
            deletion = SecurityLog.objects.filter(
                security_type='data_deleted',
                metadata__request_id=str(request.id)
            ).first()
            
            if deletion:
                compliant_count += 1
            else:
                violations.append(f'Deletion request {request.id} not processed')
        
        if deletion_requests.exists():
            compliance_rate = compliant_count / deletion_requests.count()
            score = compliance_rate * 100
            status = ComplianceStatus.COMPLIANT if score >= 95 else ComplianceStatus.PARTIALLY_COMPLIANT if score >= 70 else ComplianceStatus.NON_COMPLIANT
        else:
            score = 100  # No requests means compliant
            status = ComplianceStatus.COMPLIANT
        
        return {
            'status': status,
            'score': score,
            'evidence': [f'Processed {deletion_requests.count()} deletion requests, {compliant_count} compliant'],
            'violations': violations
        }
    
    def _check_data_portability_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check data portability compliance"""
        # Check for data portability requests
        portability_requests = SecurityLog.objects.filter(
            security_type='data_portability_request',
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        violations = []
        compliant_count = 0
        
        for request in portability_requests:
            # Check if data was provided in machine-readable format
            export = SecurityLog.objects.filter(
                security_type='data_exported',
                metadata__request_id=str(request.id)
            ).first()
            
            if export:
                compliant_count += 1
            else:
                violations.append(f'Portability request {request.id} not processed')
        
        if portability_requests.exists():
            compliance_rate = compliant_count / portability_requests.count()
            score = compliance_rate * 100
            status = ComplianceStatus.COMPLIANT if score >= 95 else ComplianceStatus.PARTIALLY_COMPLIANT if score >= 70 else ComplianceStatus.NON_COMPLIANT
        else:
            score = 100  # No requests means compliant
            status = ComplianceStatus.COMPLIANT
        
        return {
            'status': status,
            'score': score,
            'evidence': [f'Processed {portability_requests.count()} portability requests, {compliant_count} compliant'],
            'violations': violations
        }
    
    def _check_consent_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check consent management compliance"""
        # Check for consent records
        consent_records = SecurityLog.objects.filter(
            security_type__in=['consent_given', 'consent_withdrawn'],
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        if consent_records.exists():
            return {
                'status': ComplianceStatus.COMPLIANT,
                'score': 100,
                'evidence': [f'Found {consent_records.count()} consent records'],
                'violations': []
            }
        else:
            return {
                'status': ComplianceStatus.NON_COMPLIANT,
                'score': 0,
                'evidence': [],
                'violations': ['No consent records found']
            }
    
    def _check_network_security_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check network security compliance"""
        # Check for network security logs
        security_logs = SecurityLog.objects.filter(
            security_type__in=['firewall_block', 'intrusion_detected', 'network_security_scan'],
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        if security_logs.exists():
            return {
                'status': ComplianceStatus.COMPLIANT,
                'score': 100,
                'evidence': [f'Found {security_logs.count()} network security logs'],
                'violations': []
            }
        else:
            return {
                'status': ComplianceStatus.PARTIALLY_COMPLIANT,
                'score': 50,
                'evidence': [],
                'violations': ['Limited network security monitoring']
            }
    
    def _check_data_protection_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check data protection compliance"""
        # Check for encryption usage
        encryption_logs = SecurityLog.objects.filter(
            security_type='data_encrypted',
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        if encryption_logs.exists():
            return {
                'status': ComplianceStatus.COMPLIANT,
                'score': 100,
                'evidence': [f'Found {encryption_logs.count()} encryption logs'],
                'violations': []
            }
        else:
            return {
                'status': ComplianceStatus.NON_COMPLIANT,
                'score': 0,
                'evidence': [],
                'violations': ['No encryption logs found']
            }
    
    def _check_vulnerability_management_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check vulnerability management compliance"""
        # Check for vulnerability scans
        vulnerability_logs = SecurityLog.objects.filter(
            security_type='vulnerability_scan',
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        if vulnerability_logs.exists():
            return {
                'status': ComplianceStatus.COMPLIANT,
                'score': 100,
                'evidence': [f'Found {vulnerability_logs.count()} vulnerability scans'],
                'violations': []
            }
        else:
            return {
                'status': ComplianceStatus.NON_COMPLIANT,
                'score': 0,
                'evidence': [],
                'violations': ['No vulnerability scans found']
            }
    
    def _check_access_control_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check access control compliance"""
        # Check for access control logs
        access_logs = SecurityLog.objects.filter(
            security_type__in=['access_granted', 'access_denied', 'permission_denied'],
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        if access_logs.exists():
            return {
                'status': ComplianceStatus.COMPLIANT,
                'score': 100,
                'evidence': [f'Found {access_logs.count()} access control logs'],
                'violations': []
            }
        else:
            return {
                'status': ComplianceStatus.NON_COMPLIANT,
                'score': 0,
                'evidence': [],
                'violations': ['No access control logs found']
            }
    
    def _check_network_monitoring_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check network monitoring compliance"""
        # Check for network monitoring logs
        monitoring_logs = SecurityLog.objects.filter(
            security_type__in=['network_monitored', 'anomaly_detected'],
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        if monitoring_logs.exists():
            return {
                'status': ComplianceStatus.COMPLIANT,
                'score': 100,
                'evidence': [f'Found {monitoring_logs.count()} network monitoring logs'],
                'violations': []
            }
        else:
            return {
                'status': ComplianceStatus.NON_COMPLIANT,
                'score': 0,
                'evidence': [],
                'violations': ['No network monitoring logs found']
            }
    
    def _check_security_policy_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check security policy compliance"""
        # Check for policy-related logs
        policy_logs = SecurityLog.objects.filter(
            security_type__in=['policy_updated', 'policy_reviewed'],
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        if policy_logs.exists():
            return {
                'status': ComplianceStatus.COMPLIANT,
                'score': 100,
                'evidence': [f'Found {policy_logs.count()} policy logs'],
                'violations': []
            }
        else:
            return {
                'status': ComplianceStatus.PARTIALLY_COMPLIANT,
                'score': 50,
                'evidence': [],
                'violations': ['Limited policy management activity']
            }
    
    def _check_cryptography_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check cryptography compliance"""
        # Check for encryption usage
        crypto_logs = SecurityLog.objects.filter(
            security_type__in=['data_encrypted', 'key_rotation'],
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        if crypto_logs.exists():
            return {
                'status': ComplianceStatus.COMPLIANT,
                'score': 100,
                'evidence': [f'Found {crypto_logs.count()} cryptography logs'],
                'violations': []
            }
        else:
            return {
                'status': ComplianceStatus.NON_COMPLIANT,
                'score': 0,
                'evidence': [],
                'violations': ['No cryptography logs found']
            }
    
    def _check_physical_security_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check physical security compliance"""
        # Check for physical security logs
        physical_logs = SecurityLog.objects.filter(
            security_type__in=['physical_access', 'security_breach'],
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        if physical_logs.exists():
            return {
                'status': ComplianceStatus.COMPLIANT,
                'score': 100,
                'evidence': [f'Found {physical_logs.count()} physical security logs'],
                'violations': []
            }
        else:
            return {
                'status': ComplianceStatus.PARTIALLY_COMPLIANT,
                'score': 50,
                'evidence': [],
                'violations': ['Limited physical security monitoring']
            }
    
    def _check_audit_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check audit compliance"""
        # Check for audit logs
        audit_logs = SecurityLog.objects.filter(
            security_type='audit_trail',
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        if audit_logs.exists():
            return {
                'status': ComplianceStatus.COMPLIANT,
                'score': 100,
                'evidence': [f'Found {audit_logs.count()} audit logs'],
                'violations': []
            }
        else:
            return {
                'status': ComplianceStatus.NON_COMPLIANT,
                'score': 0,
                'evidence': [],
                'violations': ['No audit logs found']
            }
    
    def _check_training_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check training compliance"""
        # Check for training logs
        training_logs = SecurityLog.objects.filter(
            security_type='security_training',
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        if training_logs.exists():
            return {
                'status': ComplianceStatus.COMPLIANT,
                'score': 100,
                'evidence': [f'Found {training_logs.count()} training logs'],
                'violations': []
            }
        else:
            return {
                'status': ComplianceStatus.PARTIALLY_COMPLIANT,
                'score': 50,
                'evidence': [],
                'violations': ['Limited security training activity']
            }
    
    def _check_incident_response_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check incident response compliance"""
        # Check for incident response logs
        incident_logs = SecurityLog.objects.filter(
            security_type__in=['incident_created', 'incident_resolved'],
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        if incident_logs.exists():
            return {
                'status': ComplianceStatus.COMPLIANT,
                'score': 100,
                'evidence': [f'Found {incident_logs.count()} incident response logs'],
                'violations': []
            }
        else:
            return {
                'status': ComplianceStatus.NON_COMPLIANT,
                'score': 0,
                'evidence': [],
                'violations': ['No incident response logs found']
            }
    
    def _check_risk_assessment_compliance(self, period_days: int) -> Dict[str, Any]:
        """Check risk assessment compliance"""
        # Check for risk assessment logs
        risk_logs = SecurityLog.objects.filter(
            security_type='risk_assessment',
            created_at__gte=timezone.now() - timedelta(days=period_days)
        )
        
        if risk_logs.exists():
            return {
                'status': ComplianceStatus.COMPLIANT,
                'score': 100,
                'evidence': [f'Found {risk_logs.count()} risk assessment logs'],
                'violations': []
            }
        else:
            return {
                'status': ComplianceStatus.NON_COMPLIANT,
                'score': 0,
                'evidence': [],
                'violations': ['No risk assessment logs found']
            }


class ComplianceManager:
    """Compliance management system"""
    
    def __init__(self):
        self.framework = ComplianceFramework()
        self.assessment = ComplianceAssessment(self.framework)
        self.cache_timeout = 3600  # 1 hour
    
    def get_compliance_dashboard(self) -> Dict[str, Any]:
        """Get compliance dashboard"""
        cache_key = "compliance_dashboard"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
        
        standards = self.framework.get_all_standards()
        dashboard = {
            'overall_score': 0,
            'overall_status': ComplianceStatus.UNKNOWN,
            'standards': {},
            'summary': {
                'total_standards': len(standards),
                'compliant_standards': 0,
                'partially_compliant_standards': 0,
                'non_compliant_standards': 0
            },
            'generated_at': timezone.now().isoformat()
        }
        
        total_score = 0
        compliant_count = 0
        partially_compliant_count = 0
        non_compliant_count = 0
        
        for standard in standards:
            assessment = self.assessment.assess_compliance(standard)
            dashboard['standards'][standard] = {
                'status': assessment['overall_status'],
                'score': assessment['overall_score'],
                'compliant_count': assessment['compliant_count'],
                'total_requirements': assessment['total_requirements']
            }
            
            total_score += assessment['overall_score']
            
            if assessment['overall_status'] == ComplianceStatus.COMPLIANT:
                compliant_count += 1
            elif assessment['overall_status'] == ComplianceStatus.PARTIALLY_COMPLIANT:
                partially_compliant_count += 1
            else:
                non_compliant_count += 1
        
        # Calculate overall score and status
        if standards:
            dashboard['overall_score'] = total_score / len(standards)
            
            if dashboard['overall_score'] >= 90:
                dashboard['overall_status'] = ComplianceStatus.COMPLIANT
            elif dashboard['overall_score'] >= 70:
                dashboard['overall_status'] = ComplianceStatus.PARTIALLY_COMPLIANT
            else:
                dashboard['overall_status'] = ComplianceStatus.NON_COMPLIANT
        
        dashboard['summary']['compliant_standards'] = compliant_count
        dashboard['summary']['partially_compliant_standards'] = partially_compliant_count
        dashboard['summary']['non_compliant_standards'] = non_compliant_count
        
        cache.set(cache_key, dashboard, self.cache_timeout)
        return dashboard
    
    def get_compliance_report(self, standard: str, period_days: int = 30) -> Dict[str, Any]:
        """Get detailed compliance report"""
        assessment = self.assessment.assess_compliance(standard, period_days)
        
        # Add additional analysis
        assessment['recommendations'] = self._generate_recommendations(assessment)
        assessment['trends'] = self._get_compliance_trends(standard, period_days)
        assessment['action_items'] = self._get_action_items(assessment)
        
        return assessment
    
    def _generate_recommendations(self, assessment: Dict[str, Any]) -> List[str]:
        """Generate compliance recommendations"""
        recommendations = []
        
        for requirement in assessment['requirements']:
            if requirement['status'] == ComplianceStatus.NON_COMPLIANT:
                recommendations.append(f"Address {requirement['name']} - {requirement['description']}")
            elif requirement['status'] == ComplianceStatus.PARTIALLY_COMPLIANT:
                recommendations.append(f"Improve {requirement['name']} compliance")
        
        return recommendations
    
    def _get_compliance_trends(self, standard: str, period_days: int) -> Dict[str, Any]:
        """Get compliance trends"""
        # Compare with previous period
        previous_period = period_days * 2
        current_assessment = self.assessment.assess_compliance(standard, period_days)
        previous_assessment = self.assessment.assess_compliance(standard, previous_period)
        
        score_change = current_assessment['overall_score'] - previous_assessment['overall_score']
        
        return {
            'current_score': current_assessment['overall_score'],
            'previous_score': previous_assessment['overall_score'],
            'score_change': score_change,
            'trend': 'improving' if score_change > 0 else 'declining' if score_change < 0 else 'stable'
        }
    
    def _get_action_items(self, assessment: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get action items for non-compliant requirements"""
        action_items = []
        
        for requirement in assessment['requirements']:
            if requirement['status'] == ComplianceStatus.NON_COMPLIANT:
                action_items.append({
                    'requirement_id': requirement['requirement_id'],
                    'title': f"Fix {requirement['name']}",
                    'priority': 'high' if requirement['mandatory'] else 'medium',
                    'description': requirement['description'],
                    'violations': requirement['violations']
                })
        
        return action_items


# Global compliance manager
compliance_manager = ComplianceManager()


# Export classes and utilities
__all__ = [
    'ComplianceStandard',
    'ComplianceStatus',
    'ComplianceRequirement',
    'ComplianceFramework',
    'ComplianceAssessment',
    'ComplianceManager',
    'compliance_manager'
]