"""
Unified Security Classification System
Consolidates all scattered security choices and enums
Version: 1.0.0
"""

from enum import Enum
from typing import Tuple, List


class SecurityEventType(Enum):
    """Unified Security Event Types"""
    
    # Authentication Events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    
    # Two-Factor Authentication Events
    TWO_FA_ENABLE = "2fa_enable"
    TWO_FA_DISABLE = "2fa_disable"
    TWO_FA_VERIFY = "2fa_verify"
    TWO_FA_FAILED = "2fa_failed"
    
    # API Security Events
    API_KEY_ROTATE = "api_key_rotate"
    API_KEY_GENERATE = "api_key_generate"
    API_KEY_REVOKE = "api_key_revoke"
    
    # Suspicious Login Events
    SUSPICIOUS_LOGIN = "suspicious_login"
    UNUSUAL_LOCATION_LOGIN = "unusual_location_login"
    NEW_DEVICE_LOGIN = "new_device_login"
    RAPID_LOGIN_ATTEMPTS = "rapid_login_attempts"
    
    # Account Events
    ACCOUNT_CREATED = "account_created"
    ACCOUNT_UPDATED = "account_updated"
    ACCOUNT_DELETED = "account_deleted"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    
    # Security Events
    SECURITY_BREACH = "security_breach"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    MALICIOUS_REQUEST = "malicious_request"
    BRUTE_FORCE_ATTEMPT = "brute_force_attempt"
    
    # Fraud Events
    FRAUD_DETECTED = "fraud_detected"
    FRAUD_ATTEMPT = "fraud_attempt"
    WITHDRAWAL_BLOCKED = "withdrawal_blocked"
    UNUSUAL_ACTIVITY = "unusual_activity"
    
    # Network Events
    VPN_DETECTED = "vpn_detected"
    PROXY_DETECTED = "proxy_detected"
    TOR_DETECTED = "tor_detected"
    IP_BLOCKED = "ip_blocked"
    
    # Device Events
    NEW_DEVICE = "new_device"
    DEVICE_COMPROMISED = "device_compromised"
    DEVICE_TRUSTED = "device_trusted"
    DEVICE_BLOCKED = "device_blocked"
    
    # System Events
    SYSTEM_ALERT = "system_alert"
    MAINTENANCE_MODE = "maintenance_mode"
    CONFIGURATION_CHANGE = "configuration_change"
    
    # Incident Events
    INCIDENT_CREATED = "incident_created"
    INCIDENT_UPDATED = "incident_updated"
    INCIDENT_RESOLVED = "incident resolved"
    
    @classmethod
    def get_choices(cls) -> List[Tuple[str, str]]:
        """Get choices for Django model field"""
        return [
            (value.value, value.name.replace('_', ' ').title())
            for value in cls
        ]
    
    @classmethod
    def get_authentication_events(cls) -> List[str]:
        """Get authentication-related events"""
        return [
            cls.LOGIN_SUCCESS.value,
            cls.LOGIN_FAILED.value,
            cls.LOGOUT.value,
            cls.PASSWORD_CHANGE.value,
            cls.PASSWORD_RESET.value
        ]
    
    @classmethod
    def get_security_events(cls) -> List[str]:
        """Get security-related events"""
        return [
            cls.SECURITY_BREACH.value,
            cls.SUSPICIOUS_ACTIVITY.value,
            cls.MALICIOUS_REQUEST.value,
            cls.BRUTE_FORCE_ATTEMPT.value
        ]
    
    @classmethod
    def get_fraud_events(cls) -> List[str]:
        """Get fraud-related events"""
        return [
            cls.FRAUD_DETECTED.value,
            cls.FRAUD_ATTEMPT.value,
            cls.WITHDRAWAL_BLOCKED.value,
            cls.UNUSUAL_ACTIVITY.value
        ]


class RiskLevel(Enum):
    """Unified Risk Level Classification"""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    
    @classmethod
    def get_choices(cls) -> List[Tuple[str, str]]:
        """Get choices for Django model field"""
        return [
            (cls.CRITICAL.value, "🚨 Critical"),
            (cls.HIGH.value, "🔴 High"),
            (cls.MEDIUM.value, "🟠 Medium"),
            (cls.LOW.value, "🟡 Low"),
            (cls.INFO.value, "🟢 Info")
        ]
    
    @classmethod
    def get_numeric_score(cls, risk_level: str) -> int:
        """Get numeric score for risk level"""
        mapping = {
            cls.CRITICAL.value: 5,
            cls.HIGH.value: 4,
            cls.MEDIUM.value: 3,
            cls.LOW.value: 2,
            cls.INFO.value: 1
        }
        return mapping.get(risk_level, 1)
    
    @classmethod
    def from_score(cls, score: int) -> str:
        """Get risk level from numeric score"""
        if score >= 5:
            return cls.CRITICAL.value
        elif score >= 4:
            return cls.HIGH.value
        elif score >= 3:
            return cls.MEDIUM.value
        elif score >= 2:
            return cls.LOW.value
        else:
            return cls.INFO.value


class ThreatCategory(Enum):
    """Unified Threat Category Classification"""
    
    # Network Threats
    DDOS = "ddos"
    PHISHING = "phishing"
    MALWARE = "malware"
    RANSOMWARE = "ransomware"
    
    # Account Threats
    ACCOUNT_TAKEOVER = "account_takeover"
    CREDENTIAL_STUFFING = "credential_stuffing"
    BRUTE_FORCE = "brute_force"
    
    # Financial Threats
    FINANCIAL_FRAUD = "financial_fraud"
    MONEY_LAUNDERING = "money_laundering"
    PAYMENT_FRAUD = "payment_fraud"
    
    # Data Threats
    DATA_BREACH = "data_breach"
    DATA_EXFILTRATION = "data_exfiltration"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    
    # System Threats
    SYSTEM_COMPROMISE = "system_compromise"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    LATERAL_MOVEMENT = "lateral_movement"
    
    # Social Engineering
    SOCIAL_ENGINEERING = "social_engineering"
    INSIDER_THREAT = "insider_threat"
    
    # Anonymous/Unknown
    UNKNOWN = "unknown"
    
    @classmethod
    def get_choices(cls) -> List[Tuple[str, str]]:
        """Get choices for Django model field"""
        return [
            (cls.DDOS.value, "DDoS Attack"),
            (cls.PHISHING.value, "Phishing"),
            (cls.MALWARE.value, "Malware"),
            (cls.RANSOMWARE.value, "Ransomware"),
            (cls.ACCOUNT_TAKEOVER.value, "Account Takeover"),
            (cls.CREDENTIAL_STUFFING.value, "Credential Stuffing"),
            (cls.BRUTE_FORCE.value, "Brute Force"),
            (cls.FINANCIAL_FRAUD.value, "Financial Fraud"),
            (cls.MONEY_LAUNDERING.value, "Money Laundering"),
            (cls.PAYMENT_FRAUD.value, "Payment Fraud"),
            (cls.DATA_BREACH.value, "Data Breach"),
            (cls.DATA_EXFILTRATION.value, "Data Exfiltration"),
            (cls.UNAUTHORIZED_ACCESS.value, "Unauthorized Access"),
            (cls.SYSTEM_COMPROMISE.value, "System Compromise"),
            (cls.PRIVILEGE_ESCALATION.value, "Privilege Escalation"),
            (cls.LATERAL_MOVEMENT.value, "Lateral Movement"),
            (cls.SOCIAL_ENGINEERING.value, "Social Engineering"),
            (cls.INSIDER_THREAT.value, "Insider Threat"),
            (cls.UNKNOWN.value, "Unknown")
        ]
    
    @classmethod
    def get_network_threats(cls) -> List[str]:
        """Get network-related threats"""
        return [
            cls.DDOS.value,
            cls.PHISHING.value,
            cls.MALWARE.value,
            cls.RANSOMWARE.value
        ]
    
    @classmethod
    def get_account_threats(cls) -> List[str]:
        """Get account-related threats"""
        return [
            cls.ACCOUNT_TAKEOVER.value,
            cls.CREDENTIAL_STUFFING.value,
            cls.BRUTE_FORCE.value
        ]
    
    @classmethod
    def get_financial_threats(cls) -> List[str]:
        """Get financial-related threats"""
        return [
            cls.FINANCIAL_FRAUD.value,
            cls.MONEY_LAUNDERING.value,
            cls.PAYMENT_FRAUD.value
        ]


class IncidentStatus(Enum):
    """Unified Security Incident Status"""
    
    # Initial States
    OPEN = "open"
    INVESTIGATING = "investigating"
    
    # Active States
    MONITORING = "monitoring"
    CONTAINING = "containing"
    MITIGATING = "mitigating"
    
    # Resolution States
    RESOLVED = "resolved"
    CLOSED = "closed"
    
    # Special States
    ESCALATED = "escalated"
    FALSE_POSITIVE = "false_positive"
    AWAITING_ACTION = "awaiting_action"
    
    @classmethod
    def get_choices(cls) -> List[Tuple[str, str]]:
        """Get choices for Django model field"""
        return [
            (cls.OPEN.value, "🔴 Open"),
            (cls.INVESTIGATING.value, "🟡 Investigating"),
            (cls.MONITORING.value, "🔵 Monitoring"),
            (cls.CONTAINING.value, "🟠 Containing"),
            (cls.MITIGATING.value, "🟠 Mitigating"),
            (cls.RESOLVED.value, "🟢 Resolved"),
            (cls.CLOSED.value, "✅ Closed"),
            (cls.ESCALATED.value, "🚨 Escalated"),
            (cls.FALSE_POSITIVE.value, "❌ False Positive"),
            (cls.AWAITING_ACTION.value, "⏳ Awaiting Action")
        ]
    
    @classmethod
    def get_active_statuses(cls) -> List[str]:
        """Get active incident statuses"""
        return [
            cls.OPEN.value,
            cls.INVESTIGATING.value,
            cls.MONITORING.value,
            cls.CONTAINING.value,
            cls.MITIGATING.value,
            cls.AWAITING_ACTION.value
        ]
    
    @classmethod
    def get_resolved_statuses(cls) -> List[str]:
        """Get resolved incident statuses"""
        return [
            cls.RESOLVED.value,
            cls.CLOSED.value,
            cls.FALSE_POSITIVE.value
        ]
    
    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        """Check if status transition is allowed"""
        # Define allowed transitions
        transitions = {
            cls.OPEN.value: [
                cls.INVESTIGATING.value,
                cls.MONITORING.value,
                cls.ESCALATED.value,
                cls.FALSE_POSITIVE.value
            ],
            cls.INVESTIGATING.value: [
                cls.MONITORING.value,
                cls.CONTAINING.value,
                cls.MITIGATING.value,
                cls.ESCALATED.value,
                cls.RESOLVED.value,
                cls.FALSE_POSITIVE.value
            ],
            cls.MONITORING.value: [
                cls.CONTAINING.value,
                cls.MITIGATING.value,
                cls.ESCALATED.value,
                cls.RESOLVED.value
            ],
            cls.CONTAINING.value: [
                cls.MITIGATING.value,
                cls.RESOLVED.value,
                cls.ESCALATED.value
            ],
            cls.MITIGATING.value: [
                cls.RESOLVED.value,
                cls.ESCALATED.value
            ],
            cls.ESCALATED.value: [
                cls.CONTAINING.value,
                cls.MITIGATING.value,
                cls.RESOLVED.value,
                cls.CLOSED.value
            ],
            cls.RESOLVED.value: [
                cls.CLOSED.value
            ],
            cls.FALSE_POSITIVE.value: [
                cls.CLOSED.value
            ]
        }
        
        return to_status in transitions.get(from_status, [])


class ThreatIntelligenceSource(Enum):
    """Threat Intelligence Sources"""
    
    # Commercial Feeds
    RECORDSED_FUTURE = "recordsed_future"
    THREAT_CONNECT = "threat_connect"
    ANOMALI_LABS = "anomali_labs"
    MISP = "misp"
    
    # Open Source Feeds
    ABUSE_CH = "abuse_ch"
    PHISHTANK = "phishtank"
    MALWARE_DOMAIN_LIST = "malware_domain_list"
    
    # Internal Sources
    INTERNAL_ANALYSIS = "internal_analysis"
    HONEYPOT = "honeypot"
    USER_REPORT = "user_report"
    
    # Government/Official
    CERT = "cert"
    FBI_INFRAGARD = "fbi_infragard"
    
    # Community
    MALWARE_INFORMATION_SHARING = "malware_information_sharing"
    
    @classmethod
    def get_choices(cls) -> List[Tuple[str, str]]:
        """Get choices for Django model field"""
        return [
            (cls.RECORDSED_FUTURE.value, "Recorded Future"),
            (cls.THREAT_CONNECT.value, "Threat Connect"),
            (cls.ANOMALI_LABS.value, "Anomali Labs"),
            (cls.MISP.value, "MISP"),
            (cls.ABUSE_CH.value, "Abuse.ch"),
            (cls.PHISHTANK.value, "PhishTank"),
            (cls.MALWARE_DOMAIN_LIST.value, "Malware Domain List"),
            (cls.INTERNAL_ANALYSIS.value, "Internal Analysis"),
            (cls.HONEYPOT.value, "Honeypot"),
            (cls.USER_REPORT.value, "User Report"),
            (cls.CERT.value, "CERT"),
            (cls.FBI_INFRAGARD.value, "FBI InfraGard"),
            (cls.MALWARE_INFORMATION_SHARING.value, "MISL")
        ]


class IncidentSeverity(Enum):
    """Security Incident Severity Levels"""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    
    @classmethod
    def get_choices(cls) -> List[Tuple[str, str]]:
        """Get choices for Django model field"""
        return [
            (cls.CRITICAL.value, "🚨 Critical - Business Impact"),
            (cls.HIGH.value, "🔴 High - Significant Impact"),
            (cls.MEDIUM.value, "🟠 Medium - Limited Impact"),
            (cls.LOW.value, "🟡 Low - Minimal Impact")
        ]
    
    @classmethod
    def get_response_time_sla(cls, severity: str) -> int:
        """Get SLA response time in minutes"""
        mapping = {
            cls.CRITICAL.value: 15,  # 15 minutes
            cls.HIGH.value: 60,      # 1 hour
            cls.MEDIUM.value: 240,   # 4 hours
            cls.LOW.value: 1440     # 24 hours
        }
        return mapping.get(severity, 1440)


# Legacy compatibility mappings
LEGACY_EVENT_TYPE_MAPPING = {
    'LOGIN': SecurityEventType.LOGIN_SUCCESS.value,
    'LOGOUT': SecurityEventType.LOGOUT.value,
    'FAILED_LOGIN': SecurityEventType.LOGIN_FAILED.value,
    'SECURITY_BREACH': SecurityEventType.SECURITY_BREACH.value,
    'FRAUD_DETECTED': SecurityEventType.FRAUD_DETECTED.value,
    'VPN_DETECTED': SecurityEventType.VPN_DETECTED.value,
    'ACCOUNT_LOCKED': SecurityEventType.ACCOUNT_LOCKED.value,
    'ACCOUNT_UNLOCKED': SecurityEventType.ACCOUNT_UNLOCKED.value,
    'SUSPICIOUS_ACTIVITY': SecurityEventType.SUSPICIOUS_ACTIVITY.value,
    'MALICIOUS_REQUEST': SecurityEventType.MALICIOUS_REQUEST.value,
    'BRUTE_FORCE_ATTEMPT': SecurityEventType.BRUTE_FORCE_ATTEMPT.value,
    'WITHDRAWAL_BLOCKED': SecurityEventType.WITHDRAWAL_BLOCKED.value,
    'UNUSUAL_ACTIVITY': SecurityEventType.UNUSUAL_ACTIVITY.value,
    'NEW_DEVICE': SecurityEventType.NEW_DEVICE.value,
    'DEVICE_COMPROMISED': SecurityEventType.DEVICE_COMPROMISED.value,
    'DEVICE_TRUSTED': SecurityEventType.DEVICE_TRUSTED.value,
    'DEVICE_BLOCKED': SecurityEventType.DEVICE_BLOCKED.value,
    'SYSTEM_ALERT': SecurityEventType.SYSTEM_ALERT.value,
    'MAINTENANCE_MODE': SecurityEventType.MAINTENANCE_MODE.value,
    'CONFIGURATION_CHANGE': SecurityEventType.CONFIGURATION_CHANGE.value,
    'INCIDENT_CREATED': SecurityEventType.INCIDENT_CREATED.value,
    'INCIDENT_UPDATED': SecurityEventType.INCIDENT_UPDATED.value,
    'INCIDENT_RESOLVED': SecurityEventType.INCIDENT_RESOLVED.value,
}

class BlockReason(Enum):
    """Unified Block Reason Classification"""
    
    # Network-based blocks
    VPN = "vpn"
    PROXY = "proxy"
    TOR = "tor"
    DATACENTER = "datacenter"
    
    # Fraud-based blocks
    FRAUD = "fraud"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    MALICIOUS_IP = "malicious_ip"
    
    # Administrative blocks
    MANUAL = "manual"
    ADMIN = "admin"
    AUTOMATED = "automated"
    
    # Geographic blocks
    GEOGRAPHIC = "geographic"
    COUNTRY_RESTRICTION = "country_restriction"
    
    # Behavioral blocks
    RATE_LIMIT = "rate_limit"
    ABUSE = "abuse"
    VIOLATION = "violation"
    
    @classmethod
    def get_choices(cls) -> List[Tuple[str, str]]:
        """Get choices for Django model fields"""
        return [
            (cls.VPN.value, "VPN"),
            (cls.PROXY.value, "Proxy"),
            (cls.TOR.value, "Tor"),
            (cls.DATACENTER.value, "Datacenter"),
            (cls.FRAUD.value, "Fraud"),
            (cls.SUSPICIOUS_ACTIVITY.value, "Suspicious Activity"),
            (cls.MALICIOUS_IP.value, "Malicious IP"),
            (cls.MANUAL.value, "Manual"),
            (cls.ADMIN.value, "Admin"),
            (cls.AUTOMATED.value, "Automated"),
            (cls.GEOGRAPHIC.value, "Geographic"),
            (cls.COUNTRY_RESTRICTION.value, "Country Restriction"),
            (cls.RATE_LIMIT.value, "Rate Limit"),
            (cls.ABUSE.value, "Abuse"),
            (cls.VIOLATION.value, "Violation"),
        ]


LEGACY_RISK_LEVEL_MAPPING = {
    'safe': RiskLevel.INFO.value,
    'low': RiskLevel.LOW.value,
    'medium': RiskLevel.MEDIUM.value,
    'high': RiskLevel.HIGH.value,
    'critical': RiskLevel.CRITICAL.value,
}