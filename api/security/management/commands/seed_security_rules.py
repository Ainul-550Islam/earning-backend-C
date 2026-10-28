"""
Enhanced Security Rules Seeding Management Command
Insert default security policies and alert rules into database
Author: System Security Team
Version: 2.0.0
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model
import logging
import json
from datetime import datetime, timedelta

from ...models import (
    SecurityLog, SecurityIncident, UserBan, IPBlacklist, 
    ThreatIntelligence, RiskScore, DeviceInfo, TrustedDevice,
    PasswordHistory, SecurityPolicy, SecurityInsight
)

User = get_user_model()

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Insert default security policies and alert rules into database'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--rules-type',
            type=str,
            choices=['policies', 'alerts', 'all'],
            default='all',
            help='Type of security rules to seed'
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing rules'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be seeded without actually seeding'
        )
        parser.add_argument(
            '--config-file',
            type=str,
            help='Path to custom configuration file'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID to assign as rule creator'
        )
        parser.add_argument(
            '--active',
            action='store_true',
            default=True,
            help='Mark seeded rules as active'
        )
        parser.add_argument(
            '--environment',
            type=str,
            choices=['development', 'staging', 'production'],
            default='development',
            help='Environment-specific rules'
        )
    
    def handle(self, *args, **options):
        """Execute the security rules seeding command"""
        self.options = options
        self.seed_start_time = timezone.now()
        
        try:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting security rules seeding: {options['rules_type']} at {self.seed_start_time}"
                )
            )
            
            # Get rule creator user
            self.creator_user = self._get_creator_user()
            
            # Load configuration
            self.config = self._load_configuration()
            
            # Initialize counters
            self.rules_created = 0
            self.rules_updated = 0
            self.rules_skipped = 0
            self.errors = []
            
            # Seed rules based on type
            if options['rules_type'] in ['policies', 'all']:
                self._seed_security_policies()
            
            if options['rules_type'] in ['alerts', 'all']:
                self._seed_alert_rules()
            
            if options['rules_type'] == 'all':
                self._seed_default_threat_intelligence()
                self._seed_default_ip_blacklist()
                self._seed_risk_score_thresholds()
            
            # Generate summary
            self._generate_summary()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Security rules seeding completed successfully"
                )
            )
            
        except Exception as e:
            logger.error(f"Security rules seeding failed: {str(e)}")
            raise CommandError(f"Security rules seeding failed: {str(e)}")
    
    def _get_creator_user(self):
        """Get user to assign as rule creator"""
        if self.options['user_id']:
            try:
                return User.objects.get(id=self.options['user_id'])
            except User.DoesNotExist:
                raise CommandError(f"User with ID {self.options['user_id']} not found")
        else:
            # Try to get first superuser
            superuser = User.objects.filter(is_superuser=True).first()
            if superuser:
                return superuser
            else:
                # Create a default system user
                return User.objects.create_superuser(
                    username='security_system',
                    email='security@system.local',
                    password='temp_password_123'
                )
    
    def _load_configuration(self):
        """Load configuration from file or use defaults"""
        if self.options['config_file']:
            try:
                with open(self.options['config_file'], 'r') as f:
                    return json.load(f)
            except FileNotFoundError:
                raise CommandError(f"Configuration file not found: {self.options['config_file']}")
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON in configuration file: {str(e)}")
        else:
            return self._get_default_configuration()
    
    def _get_default_configuration(self):
        """Get default security rules configuration"""
        return {
            'security_policies': {
                'password_policy': {
                    'policy_key': 'password_policy',
                    'policy_value': {
                        'min_length': 8,
                        'max_length': 128,
                        'require_uppercase': True,
                        'require_lowercase': True,
                        'require_numbers': True,
                        'require_special_chars': True,
                        'prevent_reuse': True,
                        'reuse_limit': 12,
                        'max_age_days': 90,
                        'complexity_requirements': {
                            'min_unique_chars': 6,
                            'no_common_patterns': True,
                            'no_username_inclusion': True
                        }
                    },
                    'description': 'Default password security policy'
                },
                'session_policy': {
                    'policy_key': 'session_policy',
                    'policy_value': {
                        'timeout_minutes': 30,
                        'max_concurrent_sessions': 3,
                        'idle_timeout_minutes': 15,
                        'extend_on_activity': True,
                        'require_reauth_after': 8,
                        'secure_cookies': True,
                        'csrf_protection': True
                    },
                    'description': 'Default session management policy'
                },
                'access_policy': {
                    'policy_key': 'access_policy',
                    'policy_value': {
                        'max_login_attempts': 5,
                        'lockout_duration_minutes': 30,
                        'password_reset_required': True,
                        'two_factor_required': False,
                        'ip_whitelist_enabled': False,
                        'geo_restriction_enabled': False,
                        'business_hours_only': False
                    },
                    'description': 'Default access control policy'
                },
                'privacy_policy': {
                    'policy_key': 'privacy_policy',
                    'policy_value': {
                        'data_retention_days': 365,
                        'log_anonymization': True,
                        'audit_log_retention_days': 2555,  # 7 years
                        'personal_data_protection': True,
                        'gdpr_compliance': True,
                        'data_export_allowed': True,
                        'data_deletion_allowed': True
                    },
                    'description': 'Default privacy and data protection policy'
                }
            },
            'alert_rules': [
                {
                    'rule_name': 'High Risk User Activity',
                    'rule_type': 'user_risk',
                    'conditions': {
                        'risk_score_threshold': 80,
                        'time_window_minutes': 60
                    },
                    'actions': ['create_incident', 'notify_admins'],
                    'severity': 'high',
                    'description': 'Alert when user risk score exceeds threshold'
                },
                {
                    'rule_name': 'Multiple Failed Logins',
                    'rule_type': 'authentication',
                    'conditions': {
                        'failure_count': 5,
                        'time_window_minutes': 15
                    },
                    'actions': ['lock_account', 'notify_user', 'create_incident'],
                    'severity': 'medium',
                    'description': 'Alert on multiple failed login attempts'
                },
                {
                    'rule_name': 'Suspicious IP Activity',
                    'rule_type': 'network_security',
                    'conditions': {
                        'unique_users_threshold': 10,
                        'event_count_threshold': 50,
                        'time_window_minutes': 30
                    },
                    'actions': ['block_ip', 'create_incident', 'notify_admins'],
                    'severity': 'high',
                    'description': 'Alert on suspicious IP activity patterns'
                },
                {
                    'rule_name': 'Threat Intelligence Match',
                    'rule_type': 'threat_intelligence',
                    'conditions': {
                        'confidence_threshold': 0.8,
                        'severity_levels': ['high', 'critical']
                    },
                    'actions': ['block_ip', 'create_incident', 'notify_admins'],
                    'severity': 'critical',
                    'description': 'Alert on high-confidence threat intelligence matches'
                },
                {
                    'rule_name': 'Unusual Device Access',
                    'rule_type': 'device_security',
                    'conditions': {
                        'new_device_threshold': 1,
                        'suspicious_location': True,
                        'time_window_hours': 24
                    },
                    'actions': ['require_additional_verification', 'notify_user'],
                    'severity': 'medium',
                    'description': 'Alert on unusual device access patterns'
                },
                {
                    'rule_name': 'Security Policy Violation',
                    'rule_type': 'policy_compliance',
                    'conditions': {
                        'violation_types': ['password_policy', 'access_policy'],
                        'violation_count_threshold': 3
                    },
                    'actions': ['notify_user', 'create_incident'],
                    'severity': 'low',
                    'description': 'Alert on repeated security policy violations'
                },
                {
                    'rule_name': 'Data Access Anomaly',
                    'rule_type': 'data_security',
                    'conditions': {
                        'access_volume_threshold': 1000,
                        'unusual_time_access': True,
                        'sensitive_data_access': True
                    },
                    'actions': ['create_incident', 'notify_admins'],
                    'severity': 'high',
                    'description': 'Alert on unusual data access patterns'
                },
                {
                    'rule_name': 'System Resource Anomaly',
                    'rule_type': 'system_security',
                    'conditions': {
                        'cpu_usage_threshold': 90,
                        'memory_usage_threshold': 85,
                        'disk_usage_threshold': 80,
                        'duration_minutes': 10
                    },
                    'actions': ['create_incident', 'notify_admins'],
                    'severity': 'medium',
                    'description': 'Alert on system resource anomalies'
                }
            ],
            'threat_intelligence': {
                'default_indicators': {
                    'malicious_ips': [
                        '192.168.1.100',  # Example malicious IP
                        '10.0.0.66'      # Example malicious IP
                    ],
                    'suspicious_domains': [
                        'malicious-site.com',
                        'phishing-site.net'
                    ]
                }
            },
            'ip_blacklist': {
                'default_blocked_ips': [
                    '0.0.0.0',        # Null route
                    '255.255.255.255'  # Broadcast
                ],
                'block_reason': 'Default security blacklist'
            },
            'risk_score_thresholds': {
                'low_risk_max': 30,
                'medium_risk_max': 70,
                'high_risk_min': 71,
                'critical_risk_min': 90
            }
        }
    
    def _seed_security_policies(self):
        """Seed security policies"""
        self.stdout.write("Seeding security policies...")
        
        policies_config = self.config.get('security_policies', {})
        
        for policy_key, policy_data in policies_config.items():
            try:
                # Check if policy already exists
                existing_policy = SecurityPolicy.objects.filter(
                    policy_key=policy_data['policy_key']
                ).first()
                
                if existing_policy and not self.options['overwrite']:
                    self.rules_skipped += 1
                    self.stdout.write(f"  Skipped existing policy: {policy_key}")
                    continue
                
                # Create or update policy
                if self.options['dry_run']:
                    action = "Would create" if not existing_policy else "Would update"
                    self.stdout.write(f"  {action} policy: {policy_key}")
                    self.rules_created += 1
                else:
                    policy, created = SecurityPolicy.objects.update_or_create(
                        policy_key=policy_data['policy_key'],
                        defaults={
                            'user': self.creator_user,
                            'policy_value': json.dumps(policy_data['policy_value']),
                            'description': policy_data.get('description', ''),
                            'is_active': self.options['active'],
                            'metadata': {
                                'created_by': 'seed_security_rules_command',
                                'environment': self.options['environment'],
                                'seeded_at': self.seed_start_time.isoformat()
                            }
                        }
                    )
                    
                    if created:
                        self.rules_created += 1
                        self.stdout.write(f"  Created policy: {policy_key}")
                    else:
                        self.rules_updated += 1
                        self.stdout.write(f"  Updated policy: {policy_key}")
                
            except Exception as e:
                error_msg = f"Failed to seed policy {policy_key}: {str(e)}"
                self.errors.append(error_msg)
                logger.error(error_msg)
    
    def _seed_alert_rules(self):
        """Seed alert rules"""
        self.stdout.write("Seeding alert rules...")
        
        alert_rules = self.config.get('alert_rules', [])
        
        for rule_data in alert_rules:
            try:
                # Check if rule already exists
                if hasattr(SecurityPolicy, 'AlertRule'):  # If AlertRule model exists
                    existing_rule = SecurityPolicy.AlertRule.objects.filter(
                        rule_name=rule_data['rule_name']
                    ).first()
                    
                    if existing_rule and not self.options['overwrite']:
                        self.rules_skipped += 1
                        self.stdout.write(f"  Skipped existing rule: {rule_data['rule_name']}")
                        continue
                    
                    # Create or update rule
                    if self.options['dry_run']:
                        action = "Would create" if not existing_rule else "Would update"
                        self.stdout.write(f"  {action} rule: {rule_data['rule_name']}")
                        self.rules_created += 1
                    else:
                        rule, created = SecurityPolicy.AlertRule.objects.update_or_create(
                            rule_name=rule_data['rule_name'],
                            defaults={
                                'user': self.creator_user,
                                'rule_type': rule_data['rule_type'],
                                'conditions': rule_data['conditions'],
                                'actions': rule_data['actions'],
                                'severity': rule_data['severity'],
                                'description': rule_data.get('description', ''),
                                'is_active': self.options['active'],
                                'metadata': {
                                    'created_by': 'seed_security_rules_command',
                                    'environment': self.options['environment'],
                                    'seeded_at': self.seed_start_time.isoformat()
                                }
                            }
                        )
                        
                        if created:
                            self.rules_created += 1
                            self.stdout.write(f"  Created rule: {rule_data['rule_name']}")
                        else:
                            self.rules_updated += 1
                            self.stdout.write(f"  Updated rule: {rule_data['rule_name']}")
                else:
                    # Create as security policy if AlertRule model doesn't exist
                    policy_key = f"alert_rule_{rule_data['rule_name'].lower().replace(' ', '_')}"
                    
                    existing_policy = SecurityPolicy.objects.filter(
                        policy_key=policy_key
                    ).first()
                    
                    if existing_policy and not self.options['overwrite']:
                        self.rules_skipped += 1
                        self.stdout.write(f"  Skipped existing rule: {rule_data['rule_name']}")
                        continue
                    
                    if self.options['dry_run']:
                        action = "Would create" if not existing_policy else "Would update"
                        self.stdout.write(f"  {action} rule: {rule_data['rule_name']}")
                        self.rules_created += 1
                    else:
                        policy, created = SecurityPolicy.objects.update_or_create(
                            policy_key=policy_key,
                            defaults={
                                'user': self.creator_user,
                                'policy_value': json.dumps(rule_data),
                                'description': rule_data.get('description', ''),
                                'is_active': self.options['active'],
                                'metadata': {
                                    'type': 'alert_rule',
                                    'created_by': 'seed_security_rules_command',
                                    'environment': self.options['environment'],
                                    'seeded_at': self.seed_start_time.isoformat()
                                }
                            }
                        )
                        
                        if created:
                            self.rules_created += 1
                            self.stdout.write(f"  Created rule: {rule_data['rule_name']}")
                        else:
                            self.rules_updated += 1
                            self.stdout.write(f"  Updated rule: {rule_data['rule_name']}")
                
            except Exception as e:
                error_msg = f"Failed to seed rule {rule_data['rule_name']}: {str(e)}"
                self.errors.append(error_msg)
                logger.error(error_msg)
    
    def _seed_default_threat_intelligence(self):
        """Seed default threat intelligence"""
        self.stdout.write("Seeding default threat intelligence...")
        
        threat_config = self.config.get('threat_intelligence', {})
        indicators = threat_config.get('default_indicators', {})
        
        # Seed malicious IPs
        for ip in indicators.get('malicious_ips', []):
            try:
                existing_threat = ThreatIntelligence.objects.filter(
                    indicators__contains=[ip]
                ).first()
                
                if existing_threat and not self.options['overwrite']:
                    continue
                
                if self.options['dry_run']:
                    self.stdout.write(f"  Would create threat intelligence for IP: {ip}")
                    self.rules_created += 1
                else:
                    threat, created = ThreatIntelligence.objects.update_or_create(
                        indicators=[ip],
                        defaults={
                            'threat_type': 'malicious_ip',
                            'indicator_type': 'ip',
                            'severity': 'high',
                            'confidence': 0.9,
                            'source': 'seed_security_rules_command',
                            'description': f'Default malicious IP: {ip}',
                            'is_active': self.options['active'],
                            'metadata': {
                                'environment': self.options['environment'],
                                'seeded_at': self.seed_start_time.isoformat()
                            }
                        }
                    )
                    
                    if created:
                        self.rules_created += 1
                        self.stdout.write(f"  Created threat intelligence for IP: {ip}")
                    else:
                        self.rules_updated += 1
                
            except Exception as e:
                error_msg = f"Failed to seed threat intelligence for IP {ip}: {str(e)}"
                self.errors.append(error_msg)
                logger.error(error_msg)
        
        # Seed suspicious domains
        for domain in indicators.get('suspicious_domains', []):
            try:
                existing_threat = ThreatIntelligence.objects.filter(
                    indicators__contains=[domain]
                ).first()
                
                if existing_threat and not self.options['overwrite']:
                    continue
                
                if self.options['dry_run']:
                    self.stdout.write(f"  Would create threat intelligence for domain: {domain}")
                    self.rules_created += 1
                else:
                    threat, created = ThreatIntelligence.objects.update_or_create(
                        indicators=[domain],
                        defaults={
                            'threat_type': 'phishing',
                            'indicator_type': 'domain',
                            'severity': 'medium',
                            'confidence': 0.7,
                            'source': 'seed_security_rules_command',
                            'description': f'Default suspicious domain: {domain}',
                            'is_active': self.options['active'],
                            'metadata': {
                                'environment': self.options['environment'],
                                'seeded_at': self.seed_start_time.isoformat()
                            }
                        }
                    )
                    
                    if created:
                        self.rules_created += 1
                        self.stdout.write(f"  Created threat intelligence for domain: {domain}")
                    else:
                        self.rules_updated += 1
                
            except Exception as e:
                error_msg = f"Failed to seed threat intelligence for domain {domain}: {str(e)}"
                self.errors.append(error_msg)
                logger.error(error_msg)
    
    def _seed_default_ip_blacklist(self):
        """Seed default IP blacklist"""
        self.stdout.write("Seeding default IP blacklist...")
        
        blacklist_config = self.config.get('ip_blacklist', {})
        blocked_ips = blacklist_config.get('default_blocked_ips', [])
        block_reason = blacklist_config.get('block_reason', 'Default security blacklist')
        
        for ip in blocked_ips:
            try:
                existing_blacklist = IPBlacklist.objects.filter(
                    ip_address=ip
                ).first()
                
                if existing_blacklist and not self.options['overwrite']:
                    continue
                
                if self.options['dry_run']:
                    self.stdout.write(f"  Would blacklist IP: {ip}")
                    self.rules_created += 1
                else:
                    blacklist, created = IPBlacklist.objects.update_or_create(
                        ip_address=ip,
                        defaults={
                            'blacklist_type': 'system_default',
                            'reason': block_reason,
                            'confidence': 1.0,
                            'source': 'seed_security_rules_command',
                            'is_active': self.options['active'],
                            'metadata': {
                                'environment': self.options['environment'],
                                'seeded_at': self.seed_start_time.isoformat()
                            }
                        }
                    )
                    
                    if created:
                        self.rules_created += 1
                        self.stdout.write(f"  Blacklisted IP: {ip}")
                    else:
                        self.rules_updated += 1
                
            except Exception as e:
                error_msg = f"Failed to blacklist IP {ip}: {str(e)}"
                self.errors.append(error_msg)
                logger.error(error_msg)
    
    def _seed_risk_score_thresholds(self):
        """Seed default risk score thresholds"""
        self.stdout.write("Seeding risk score thresholds...")
        
        thresholds = self.config.get('risk_score_thresholds', {})
        
        # Create security policies for risk thresholds
        for threshold_name, threshold_value in thresholds.items():
            try:
                policy_key = f"risk_threshold_{threshold_name}"
                
                existing_policy = SecurityPolicy.objects.filter(
                    policy_key=policy_key
                ).first()
                
                if existing_policy and not self.options['overwrite']:
                    continue
                
                if self.options['dry_run']:
                    self.stdout.write(f"  Would create risk threshold policy: {threshold_name}")
                    self.rules_created += 1
                else:
                    policy, created = SecurityPolicy.objects.update_or_create(
                        policy_key=policy_key,
                        defaults={
                            'user': self.creator_user,
                            'policy_value': json.dumps({'threshold': threshold_value}),
                            'description': f'Risk score threshold: {threshold_name}',
                            'is_active': self.options['active'],
                            'metadata': {
                                'type': 'risk_threshold',
                                'created_by': 'seed_security_rules_command',
                                'environment': self.options['environment'],
                                'seeded_at': self.seed_start_time.isoformat()
                            }
                        }
                    )
                    
                    if created:
                        self.rules_created += 1
                        self.stdout.write(f"  Created risk threshold: {threshold_name}")
                    else:
                        self.rules_updated += 1
                
            except Exception as e:
                error_msg = f"Failed to create risk threshold {threshold_name}: {str(e)}"
                self.errors.append(error_msg)
                logger.error(error_msg)
    
    def _generate_summary(self):
        """Generate and display summary of seeding operation"""
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS("SECURITY RULES SEEDING SUMMARY"))
        self.stdout.write("="*80)
        
        # Configuration
        self.stdout.write("Configuration:")
        self.stdout.write(f"  Rules Type: {self.options['rules_type']}")
        self.stdout.write(f"  Environment: {self.options['environment']}")
        self.stdout.write(f"  Dry Run: {self.options['dry_run']}")
        self.stdout.write(f"  Overwrite: {self.options['overwrite']}")
        self.stdout.write(f"  Active: {self.options['active']}")
        self.stdout.write(f"  Creator User: {self.creator_user.username}")
        
        # Results
        self.stdout.write(f"\nResults:")
        self.stdout.write(f"  Rules Created: {self.rules_created}")
        self.stdout.write(f"  Rules Updated: {self.rules_updated}")
        self.stdout.write(f"  Rules Skipped: {self.rules_skipped}")
        self.stdout.write(f"  Errors: {len(self.errors)}")
        
        # Errors
        if self.errors:
            self.stdout.write(f"\nErrors:")
            for error in self.errors[:10]:
                self.stdout.write(f"  {error}")
            if len(self.errors) > 10:
                self.stdout.write(f"  ... and {len(self.errors) - 10} more")
        
        # Statistics
        total_rules = self.rules_created + self.rules_updated + self.rules_skipped
        if total_rules > 0:
            success_rate = ((self.rules_created + self.rules_updated) / total_rules) * 100
            self.stdout.write(f"\nStatistics:")
            self.stdout.write(f"  Total Rules Processed: {total_rules}")
            self.stdout.write(f"  Success Rate: {success_rate:.2f}%")
        
        self.stdout.write("="*80)