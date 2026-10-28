"""
Security Fixtures Module
JSON fixtures for security module testing and development
"""

import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import (
    DeviceInfo, SecurityLog, UserBan, IPBlacklist, ThreatIntelligence,
    SecurityIncident, TrustedDevice, PasswordHistory, SecurityPolicy,
    SecurityInsight, RiskScore, UserSession, TwoFactorMethod,
    SecurityNotification, AuditTrail
)

User = get_user_model()


def create_security_fixtures():
    """Create comprehensive security fixtures for testing"""
    
    fixtures_data = {
        'users': [],
        'device_info': [],
        'security_logs': [],
        'user_bans': [],
        'ip_blacklist': [],
        'threat_intelligence': [],
        'security_incidents': [],
        'trusted_devices': [],
        'password_history': [],
        'security_policies': [],
        'security_insights': [],
        'risk_scores': [],
        'user_sessions': [],
        'two_factor_methods': [],
        'security_notifications': [],
        'audit_trails': []
    }
    
    # Create admin user
    admin_user = {
        'model': 'auth.user',
        'pk': 1,
        'fields': {
            'username': 'admin',
            'email': 'admin@example.com',
            'first_name': 'Admin',
            'last_name': 'User',
            'is_active': True,
            'is_staff': True,
            'is_superuser': True,
            'password': 'pbkdf2_sha256$260000$admin_salt$admin_hash',
            'date_joined': '2023-01-01T00:00:00Z',
            'last_login': '2024-01-01T12:00:00Z'
        }
    }
    fixtures_data['users'].append(admin_user)
    
    # Create regular users
    for i in range(1, 6):
        user = {
            'model': 'auth.user',
            'pk': i + 1,
            'fields': {
                'username': f'user{i}',
                'email': f'user{i}@example.com',
                'first_name': f'User{i}',
                'last_name': 'Test',
                'is_active': True,
                'is_staff': False,
                'is_superuser': False,
                'password': 'pbkdf2_sha256$260000$user_salt$user_hash',
                'date_joined': '2023-01-01T00:00:00Z',
                'last_login': '2024-01-01T12:00:00Z'
            }
        }
        fixtures_data['users'].append(user)
    
    # Create device info
    for i in range(1, 11):
        device_info = {
            'model': 'security.deviceinfo',
            'pk': i,
            'fields': {
                'user': i + 1 if i <= 5 else 1,
                'device_id': f'device_{i}',
                'device_id_hash': f'hash_{i}',
                'device_model': ['Samsung Galaxy S21', 'iPhone 13', 'Google Pixel 6', 'OnePlus 9', 'Xiaomi Mi 11'][i-1],
                'device_brand': ['Samsung', 'Apple', 'Google', 'OnePlus', 'Xiaomi'][i-1],
                'android_version': ['11.0', '12.0', '13.0', '14.0', '15.0'][i-1],
                'app_version': '2.1.0',
                'is_rooted': i % 3 == 0,
                'is_emulator': i % 4 == 0,
                'is_vpn': i % 5 == 0,
                'is_proxy': i % 6 == 0,
                'is_trusted': i % 2 == 0,
                'last_ip': f'192.168.1.{10 + i}',
                'fingerprint': f'fingerprint_{i}',
                'risk_score': i * 10,
                'trust_level': [1, 2, 3][i % 3],
                'last_activity': '2024-01-01T12:00:00Z',
                'created_at': '2023-12-01T00:00:00Z',
                'updated_at': '2024-01-01T12:00:00Z',
                'metadata': {
                    'screen_resolution': '1080x1920',
                    'battery_level': 85,
                    'storage_available': '32GB'
                }
            }
        }
        fixtures_data['device_info'].append(device_info)
    
    # Create security logs
    log_types = ['login_success', 'login_failed', 'logout', 'password_change', 'api_request', 'security_incident']
    severities = ['low', 'medium', 'high', 'critical']
    
    for i in range(1, 51):
        log = {
            'model': 'security.securitylog',
            'pk': i,
            'fields': {
                'user': (i % 6) + 1,
                'security_type': log_types[i % len(log_types)],
                'severity': severities[i % len(severities)],
                'ip_address': f'192.168.1.{100 + (i % 50)}',
                'description': f'Security log entry {i}',
                'risk_score': i % 100,
                'response_time_ms': 100 + (i % 500),
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'metadata': {
                    'request_id': f'req_{i}',
                    'session_id': f'sess_{i}',
                    'additional_info': f'Additional info for log {i}'
                },
                'created_at': f'2024-01-{(i % 30) + 1:02d}T{(i % 24):02d}:00:00Z'
            }
        }
        fixtures_data['security_logs'].append(log)
    
    # Create user bans
    for i in range(1, 6):
        ban = {
            'model': 'security.userban',
            'pk': i,
            'fields': {
                'user': i + 1,
                'reason': f'Ban reason {i}',
                'is_active': i % 2 == 0,
                'expires_at': f'2024-{(i % 12) + 1:02d}-01T12:00:00Z',
                'created_at': '2023-12-01T00:00:00Z'
            }
        }
        fixtures_data['user_bans'].append(ban)
    
    # Create IP blacklist
    for i in range(1, 21):
        blacklist = {
            'model': 'security.ipblacklist',
            'pk': i,
            'fields': {
                'ip_address': f'10.0.0.{i}',
                'reason': f'Blacklist reason {i}',
                'is_active': i % 3 != 0,
                'expires_at': f'2024-{(i % 12) + 1:02d}-01T12:00:00Z',
                'created_at': '2023-12-01T00:00:00Z'
            }
        }
        fixtures_data['ip_blacklist'].append(blacklist)
    
    # Create threat intelligence
    threat_types = ['malware', 'phishing', 'botnet', 'ddos', 'sql_injection', 'xss', 'zero_day']
    for i in range(1, 31):
        threat = {
            'model': 'security.threatintelligence',
            'pk': i,
            'fields': {
                'ip_range': f'172.16.0.{i}',
                'threat_type': threat_types[i % len(threat_types)],
                'source': ['VirusTotal', 'AbuseIPDB', 'Spamhaus', 'Custom'][i % 4],
                'confidence': round((i % 100) / 100, 2),
                'expires_at': f'2024-{(i % 12) + 1:02d}-01T12:00:00Z',
                'indicator': f'indicator_{i}',
                'indicator_type': ['hash', 'domain', 'ip', 'url'][i % 4],
                'severity': ['low', 'medium', 'high', 'critical'][i % 4],
                'is_active': i % 4 != 0,
                'metadata': {
                    'threat_family': f'family_{i}',
                    'cve_id': f'CVE-2023-{i:04d}',
                    'attack_vector': 'network'
                },
                'created_at': '2023-12-01T00:00:00Z',
                'updated_at': '2024-01-01T12:00:00Z'
            }
        }
        fixtures_data['threat_intelligence'].append(threat)
    
    # Create security incidents
    incident_types = ['unauthorized_access', 'data_breach', 'malware_detection', 'phishing_attempt', 'ddos_attack']
    for i in range(1, 16):
        incident = {
            'model': 'security.securityincident',
            'pk': i,
            'fields': {
                'user': (i % 6) + 1,
                'incident_type': incident_types[i % len(incident_types)],
                'severity': ['low', 'medium', 'high', 'critical'][i % 4],
                'status': ['open', 'investigating', 'contained', 'resolved'][i % 4],
                'title': f'Incident {i}',
                'description': f'Description for security incident {i}',
                'affected_systems': ['web_application', 'database', 'api'][:i % 3 + 1],
                'impact_assessment': f'Impact assessment for incident {i}',
                'mitigation_steps': [f'Step {j}' for j in range(1, i % 3 + 2)],
                'priority': ['low', 'medium', 'high', 'urgent'][i % 4],
                'opened_at': f'2024-01-{(i % 30) + 1:02d}T{(i % 24):02d}:00:00Z',
                'resolved_at': f'2024-01-{(i % 30) + 2:02d}T{(i % 24):02d}:00:00Z' if i % 3 == 0 else None,
                'metadata': {
                    'attack_source': f'192.168.1.{i}',
                    'attack_method': 'brute_force',
                    'detection_method': 'automated'
                }
            }
        }
        fixtures_data['security_incidents'].append(incident)
    
    # Create trusted devices
    for i in range(1, 11):
        device = {
            'model': 'security.trusteddevice',
            'pk': i,
            'fields': {
                'user': (i % 5) + 1,
                'device_fingerprint': f'fingerprint_{i}',
                'device_name': f'Trusted Device {i}',
                'device_type': ['mobile', 'tablet', 'desktop', 'laptop'][i % 4],
                'platform': ['Windows', 'iOS', 'Android', 'macOS'][i % 4],
                'browser': ['Chrome', 'Firefox', 'Safari', 'Edge'][i % 4],
                'ip_address': f'192.168.1.{200 + i}',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'trust_score': 80 + (i % 20),
                'is_trusted': True,
                'last_seen': f'2024-01-{(i % 30) + 1:02d}T{(i % 24):02d}:00:00Z',
                'expires_at': f'2024-{(i % 12) + 6:02d}-01T12:00:00Z',
                'metadata': {
                    'device_id': f'device_id_{i}',
                    'manufacturer': 'Manufacturer',
                    'model': 'Model'
                },
                'created_at': '2023-12-01T00:00:00Z',
                'updated_at': '2024-01-01T12:00:00Z'
            }
        }
        fixtures_data['trusted_devices'].append(device)
    
    # Create security policies
    policy_types = ['password', 'session', 'access', 'audit', 'encryption']
    for i in range(1, 11):
        policy = {
            'model': 'security.securitypolicy',
            'pk': i,
            'fields': {
                'tenant': None,  # Global policy
                'policy_key': f'policy_{i}',
                'value': {
                    'enabled': i % 2 == 0,
                    'threshold': i * 10,
                    'action': f'action_{i}'
                },
                'policy_type': policy_types[i % len(policy_types)],
                'description': f'Description for security policy {i}',
                'priority': i * 10,
                'is_active': i % 3 != 0,
                'enforced': i % 2 == 0,
                'metadata': {
                    'created_by': 'admin',
                    'last_modified': '2024-01-01T12:00:00Z'
                },
                'created_at': '2023-12-01T00:00:00Z',
                'updated_at': '2024-01-01T12:00:00Z'
            }
        }
        fixtures_data['security_policies'].append(policy)
    
    # Create security insights
    for i in range(1, 31):
        insight = {
            'model': 'security.securityinsight',
            'pk': i,
            'fields': {
                'date': f'2024-01-{i:02d}',
                'total_events': i * 10,
                'critical_count': i % 5,
                'high_count': i % 10,
                'medium_count': i % 20,
                'low_count': i % 50,
                'blocked_ips': [f'192.168.1.{j}' for j in range(1, i % 5 + 1)],
                'locked_accounts': [f'user{j}' for j in range(1, i % 3 + 1)],
                'failed_logins': i % 20,
                'successful_logins': i * 5,
                'suspicious_activities': i % 15,
                'fraud_attempts': i % 8,
                'malware_detections': i % 3,
                'phishing_attempts': i % 12,
                'ddos_attacks': i % 2,
                'data_breaches': i % 4,
                'countries_affected': ['US', 'UK', 'CA', 'AU'][:i % 4 + 1],
                'risk_score': round((i % 100) * 0.8, 2),
                'system_health_score': round(80 + (i % 20), 2),
                'avg_response_time': round(100 + (i % 1000), 2),
                'metadata': {
                    'peak_hour': i % 24,
                    'most_common_threat': f'threat_{i}',
                    'top_vulnerable_system': f'system_{i}'
                },
                'created_at': '2024-01-01T12:00:00Z',
                'updated_at': '2024-01-01T12:00:00Z'
            }
        }
        fixtures_data['security_insights'].append(insight)
    
    return fixtures_data


def save_fixtures_to_json(output_file='security_fixtures.json'):
    """Save fixtures to JSON file"""
    fixtures_data = create_security_fixtures()
    
    # Flatten all fixtures into a single list
    all_fixtures = []
    for model_type, fixtures in fixtures_data.items():
        all_fixtures.extend(fixtures)
    
    with open(output_file, 'w') as f:
        json.dump(all_fixtures, f, indent=2, default=str)
    
    return all_fixtures


def create_test_fixtures():
    """Create minimal test fixtures for unit testing"""
    
    test_fixtures = [
        # Admin user
        {
            'model': 'auth.user',
            'pk': 1,
            'fields': {
                'username': 'test_admin',
                'email': 'admin@test.com',
                'is_active': True,
                'is_staff': True,
                'is_superuser': True,
                'password': 'pbkdf2_sha256$260000$salt$hash'
            }
        },
        
        # Regular user
        {
            'model': 'auth.user',
            'pk': 2,
            'fields': {
                'username': 'test_user',
                'email': 'user@test.com',
                'is_active': True,
                'is_staff': False,
                'is_superuser': False,
                'password': 'pbkdf2_sha256$260000$salt$hash'
            }
        },
        
        # Device info
        {
            'model': 'security.deviceinfo',
            'pk': 1,
            'fields': {
                'user': 2,
                'device_id': 'test_device_1',
                'device_id_hash': 'test_hash_1',
                'device_model': 'Test Device',
                'device_brand': 'TestBrand',
                'android_version': '13.0',
                'app_version': '2.1.0',
                'is_rooted': False,
                'is_emulator': False,
                'is_vpn': False,
                'is_proxy': False,
                'is_trusted': True,
                'last_ip': '192.168.1.100',
                'fingerprint': 'test_fingerprint',
                'risk_score': 25,
                'trust_level': 2,
                'last_activity': '2024-01-01T12:00:00Z',
                'created_at': '2023-12-01T00:00:00Z',
                'updated_at': '2024-01-01T12:00:00Z'
            }
        },
        
        # Security log
        {
            'model': 'security.securitylog',
            'pk': 1,
            'fields': {
                'user': 2,
                'security_type': 'login_success',
                'severity': 'info',
                'ip_address': '192.168.1.100',
                'description': 'Test user login',
                'risk_score': 10,
                'response_time_ms': 150,
                'user_agent': 'Test User Agent',
                'metadata': {'test': True},
                'created_at': '2024-01-01T12:00:00Z'
            }
        },
        
        # Security policy
        {
            'model': 'security.securitypolicy',
            'pk': 1,
            'fields': {
                'tenant': None,
                'policy_key': 'test_policy',
                'value': {'enabled': True, 'threshold': 50},
                'policy_type': 'password',
                'description': 'Test security policy',
                'priority': 100,
                'is_active': True,
                'enforced': True,
                'metadata': {'test': True},
                'created_at': '2023-12-01T00:00:00Z',
                'updated_at': '2024-01-01T12:00:00Z'
            }
        }
    ]
    
    return test_fixtures


# Export functions
__all__ = [
    'create_security_fixtures',
    'save_fixtures_to_json',
    'create_test_fixtures'
]