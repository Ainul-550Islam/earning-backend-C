# =============================================================================
# fraud_detection/management/commands/seed_fraud_rules.py
# =============================================================================
"""
Seed Fraud Rules Management Command.

Populate the fraud detection system with default rule sets
for comprehensive fraud detection across different patterns and scenarios.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction

from api.fraud_detection.models import FraudRule
from api.fraud_detection.choices import RuleType, SeverityLevel, ActionOnTrigger

import json
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Seed default fraud detection rules'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--rule-type',
            type=str,
            choices=['all', 'basic', 'advanced', 'behavioral', 'transaction', 'account'],
            default='all',
            help='Type of rules to seed'
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing rules'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show rules that would be created without creating them'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output with rule details'
        )
    
    def handle(self, *args, **options):
        """Execute the fraud rules seeding command."""
        self.rule_type = options['rule_type']
        self.overwrite = options['overwrite']
        self.dry_run = options['dry_run']
        self.verbose = options['verbose']
        
        # Seeding results
        self.results = {
            'rules_created': 0,
            'rules_updated': 0,
            'rules_skipped': 0,
            'errors': []
        }
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Seeding fraud rules: {self.rule_type}'
            )
        )
        
        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No rules will be created')
            )
        
        try:
            with transaction.atomic():
                self._execute_seeding()
                
                self._print_summary()
                
        except Exception as e:
            logger.error(f"Fraud rules seeding failed: {e}")
            raise CommandError(f"Fraud rules seeding failed: {e}")
    
    def _execute_seeding(self):
        """Execute the rules seeding process."""
        if self.rule_type == 'all':
            self._seed_all_rules()
        elif self.rule_type == 'basic':
            self._seed_basic_rules()
        elif self.rule_type == 'advanced':
            self._seed_advanced_rules()
        elif self.rule_type == 'behavioral':
            self._seed_behavioral_rules()
        elif self.rule_type == 'transaction':
            self._seed_transaction_rules()
        elif self.rule_type == 'account':
            self._seed_account_rules()
    
    def _seed_all_rules(self):
        """Seed all rule types."""
        self.stdout.write('Seeding all fraud detection rules...')
        
        self._seed_basic_rules()
        self._seed_advanced_rules()
        self._seed_behavioral_rules()
        self._seed_transaction_rules()
        self._seed_account_rules()
    
    def _seed_basic_rules(self):
        """Seed basic fraud detection rules."""
        self.stdout.write('Seeding basic fraud rules...')
        
        rules = [
            {
                'name': 'High Value Transaction',
                'rule_type': RuleType.PATTERN,
                'description': 'Flag transactions with unusually high amounts',
                'condition': {
                    'field': 'amount_involved',
                    'operator': '>',
                    'value': 1000
                },
                'weight': 80,
                'threshold': 70,
                'severity': SeverityLevel.HIGH,
                'action_on_trigger': ActionOnTrigger.FLAG,
                'metadata': {
                    'category': 'financial',
                    'detection_method': 'threshold'
                }
            },
            {
                'name': 'Multiple Failed Attempts',
                'rule_type': RuleType.BEHAVIORAL,
                'description': 'Detect multiple failed login/transaction attempts',
                'condition': {
                    'field': 'failed_attempts_24h',
                    'operator': '>',
                    'value': 5
                },
                'weight': 70,
                'threshold': 60,
                'severity': SeverityLevel.MEDIUM,
                'action_on_trigger': ActionOnTrigger.FLAG,
                'metadata': {
                    'category': 'behavioral',
                    'detection_method': 'frequency'
                }
            },
            {
                'name': 'Suspicious IP Address',
                'rule_type': RuleType.NETWORK,
                'description': 'Flag connections from known malicious IP addresses',
                'condition': {
                    'field': 'ip_reputation',
                    'operator': '<',
                    'value': 30
                },
                'weight': 90,
                'threshold': 75,
                'severity': SeverityLevel.HIGH,
                'action_on_trigger': ActionOnTrigger.BLOCK,
                'metadata': {
                    'category': 'network',
                    'detection_method': 'reputation'
                }
            },
            {
                'name': 'New Account High Activity',
                'rule_type': RuleType.PATTERN,
                'description': 'Flag unusually high activity from new accounts',
                'condition': {
                    'field': 'account_age_days',
                    'operator': '<',
                    'value': 7
                },
                'weight': 60,
                'threshold': 50,
                'severity': SeverityLevel.MEDIUM,
                'action_on_trigger': ActionOnTrigger.ALERT,
                'metadata': {
                    'category': 'account',
                    'detection_method': 'temporal'
                }
            },
            {
                'name': 'Rapid Succession',
                'rule_type': RuleType.BEHAVIORAL,
                'description': 'Detect rapid successive actions',
                'condition': {
                    'field': 'action_frequency_minutes',
                    'operator': '<',
                    'value': 1
                },
                'weight': 75,
                'threshold': 65,
                'severity': SeverityLevel.MEDIUM,
                'action_on_trigger': ActionOnTrigger.FLAG,
                'metadata': {
                    'category': 'behavioral',
                    'detection_method': 'frequency'
                }
            }
        ]
        
        for rule_data in rules:
            self._create_or_update_rule(rule_data)
    
    def _seed_advanced_rules(self):
        """Seed advanced fraud detection rules."""
        self.stdout.write('Seeding advanced fraud rules...')
        
        rules = [
            {
                'name': 'Geographic Anomaly',
                'rule_type': RuleType.NETWORK,
                'description': 'Detect impossible geographic travel patterns',
                'condition': {
                    'field': 'geographic_velocity_kmh',
                    'operator': '>',
                    'value': 800  # 800 km/h is impossible
                },
                'weight': 85,
                'threshold': 80,
                'severity': SeverityLevel.HIGH,
                'action_on_trigger': ActionOnTrigger.FLAG,
                'metadata': {
                    'category': 'network',
                    'detection_method': 'geographic'
                }
            },
            {
                'name': 'Device Fingerprint Mismatch',
                'rule_type': RuleType.DEVICE,
                'description': 'Detect changes in device fingerprint',
                'condition': {
                    'field': 'device_similarity_score',
                    'operator': '<',
                    'value': 0.3
                },
                'weight': 70,
                'threshold': 60,
                'severity': SeverityLevel.MEDIUM,
                'action_on_trigger': ActionOnTrigger.FLAG,
                'metadata': {
                    'category': 'device',
                    'detection_method': 'fingerprint'
                }
            },
            {
                'name': 'VPN/Proxy Usage',
                'rule_type': RuleType.NETWORK,
                'description': 'Flag connections through VPN or proxy services',
                'condition': {
                    'field': 'is_anonymous_proxy',
                    'operator': '==',
                    'value': True
                },
                'weight': 65,
                'threshold': 55,
                'severity': SeverityLevel.MEDIUM,
                'action_on_trigger': ActionOnTrigger.ALERT,
                'metadata': {
                    'category': 'network',
                    'detection_method': 'network_analysis'
                }
            },
            {
                'name': 'Unusual Time Pattern',
                'rule_type': RuleType.BEHAVIORAL,
                'description': 'Detect activity at unusual hours',
                'condition': {
                    'field': 'off_hours_activity_percentage',
                    'operator': '>',
                    'value': 80
                },
                'weight': 60,
                'threshold': 50,
                'severity': SeverityLevel.LOW,
                'action_on_trigger': ActionOnTrigger.ALERT,
                'metadata': {
                    'category': 'behavioral',
                    'detection_method': 'temporal'
                }
            },
            {
                'name': 'Multiple Account Correlation',
                'rule_type': RuleType.PATTERN,
                'description': 'Detect correlated behavior across multiple accounts',
                'condition': {
                    'field': 'account_similarity_score',
                    'operator': '>',
                    'value': 0.8
                },
                'weight': 90,
                'threshold': 85,
                'severity': SeverityLevel.HIGH,
                'action_on_trigger': ActionOnTrigger.FLAG,
                'metadata': {
                    'category': 'account',
                    'detection_method': 'correlation'
                }
            }
        ]
        
        for rule_data in rules:
            self._create_or_update_rule(rule_data)
    
    def _seed_behavioral_rules(self):
        """Seed behavioral pattern detection rules."""
        self.stdout.write('Seeding behavioral fraud rules...')
        
        rules = [
            {
                'name': 'Bot-like Activity',
                'rule_type': RuleType.BEHAVIORAL,
                'description': 'Detect automated bot behavior patterns',
                'condition': {
                    'field': 'behavioral_consistency_score',
                    'operator': '<',
                    'value': 0.4
                },
                'weight': 85,
                'threshold': 75,
                'severity': SeverityLevel.HIGH,
                'action_on_trigger': ActionOnTrigger.BLOCK,
                'metadata': {
                    'category': 'behavioral',
                    'detection_method': 'pattern_analysis'
                }
            },
            {
                'name': 'Click Fraud Pattern',
                'rule_type': RuleType.BEHAVIORAL,
                'description': 'Detect click fraud patterns',
                'condition': {
                    'field': 'click_fraud_score',
                    'operator': '>',
                    'value': 70
                },
                'weight': 80,
                'threshold': 70,
                'severity': SeverityLevel.HIGH,
                'action_on_trigger': ActionOnTrigger.FLAG,
                'metadata': {
                    'category': 'behavioral',
                    'detection_method': 'click_analysis'
                }
            },
            {
                'name': 'Session Anomaly',
                'rule_type': RuleType.BEHAVIORAL,
                'description': 'Detect unusual session patterns',
                'condition': {
                    'field': 'session_anomaly_score',
                    'operator': '>',
                    'value': 60
                },
                'weight': 70,
                'threshold': 60,
                'severity': SeverityLevel.MEDIUM,
                'action_on_trigger': ActionOnTrigger.ALERT,
                'metadata': {
                    'category': 'behavioral',
                    'detection_method': 'session_analysis'
                }
            },
            {
                'name': 'Navigation Pattern',
                'rule_type': RuleType.BEHAVIORAL,
                'description': 'Detect unusual navigation patterns',
                'condition': {
                    'field': 'navigation_deviation_score',
                    'operator': '>',
                    'value': 0.7
                },
                'weight': 65,
                'threshold': 55,
                'severity': SeverityLevel.MEDIUM,
                'action_on_trigger': ActionOnTrigger.ALERT,
                'metadata': {
                    'category': 'behavioral',
                    'detection_method': 'navigation_analysis'
                }
            },
            {
                'name': 'Time-based Anomaly',
                'rule_type': RuleType.BEHAVIORAL,
                'description': 'Detect unusual timing patterns',
                'condition': {
                    'field': 'temporal_anomaly_score',
                    'operator': '>',
                    'value': 65
                },
                'weight': 60,
                'threshold': 50,
                'severity': SeverityLevel.MEDIUM,
                'action_on_trigger': ActionOnTrigger.ALERT,
                'metadata': {
                    'category': 'behavioral',
                    'detection_method': 'temporal_analysis'
                }
            }
        ]
        
        for rule_data in rules:
            self._create_or_update_rule(rule_data)
    
    def _seed_transaction_rules(self):
        """Seed transaction-focused fraud detection rules."""
        self.stdout.write('Seeding transaction fraud rules...')
        
        rules = [
            {
                'name': 'Unusual Amount Pattern',
                'rule_type': RuleType.PATTERN,
                'description': 'Detect unusual transaction amount patterns',
                'condition': {
                    'field': 'amount_deviation_score',
                    'operator': '>',
                    'value': 3.0  # 3x deviation from user average
                },
                'weight': 75,
                'threshold': 65,
                'severity': SeverityLevel.MEDIUM,
                'action_on_trigger': ActionOnTrigger.FLAG,
                'metadata': {
                    'category': 'transaction',
                    'detection_method': 'statistical'
                }
            },
            {
                'name': 'Round Number Amount',
                'rule_type': RuleType.PATTERN,
                'description': 'Flag suspiciously round transaction amounts',
                'condition': {
                    'field': 'is_round_number',
                    'operator': '==',
                    'value': True
                },
                'weight': 50,
                'threshold': 40,
                'severity': SeverityLevel.LOW,
                'action_on_trigger': ActionOnTrigger.ALERT,
                'metadata': {
                    'category': 'transaction',
                    'detection_method': 'pattern'
                }
            },
            {
                'name': 'High Frequency Transactions',
                'rule_type': RuleType.PATTERN,
                'description': 'Detect unusually high transaction frequency',
                'condition': {
                    'field': 'transactions_per_hour',
                    'operator': '>',
                    'value': 10
                },
                'weight': 70,
                'threshold': 60,
                'severity': SeverityLevel.MEDIUM,
                'action_on_trigger': ActionOnTrigger.FLAG,
                'metadata': {
                    'category': 'transaction',
                    'detection_method': 'frequency'
                }
            },
            {
                'name': 'Cross-border Transaction',
                'rule_type': RuleType.PATTERN,
                'description': 'Flag transactions crossing country borders',
                'condition': {
                    'field': 'is_cross_border',
                    'operator': '==',
                    'value': True
                },
                'weight': 60,
                'threshold': 50,
                'severity': SeverityLevel.MEDIUM,
                'action_on_trigger': ActionOnTrigger.ALERT,
                'metadata': {
                    'category': 'transaction',
                    'detection_method': 'geographic'
                }
            },
            {
                'name': 'Card Testing Pattern',
                'rule_type': RuleType.PATTERN,
                'description': 'Detect card testing patterns',
                'condition': {
                    'field': 'card_testing_score',
                    'operator': '>',
                    'value': 70
                },
                'weight': 85,
                'threshold': 75,
                'severity': SeverityLevel.HIGH,
                'action_on_trigger': ActionOnTrigger.BLOCK,
                'metadata': {
                    'category': 'transaction',
                    'detection_method': 'pattern'
                }
            },
            {
                'name': 'Micro Transaction Pattern',
                'rule_type': RuleType.PATTERN,
                'description': 'Detect micro-transaction fraud patterns',
                'condition': {
                    'field': 'micro_transaction_score',
                    'operator': '>',
                    'value': 60
                },
                'weight': 65,
                'threshold': 55,
                'severity': SeverityLevel.MEDIUM,
                'action_on_trigger': ActionOnTrigger.ALERT,
                'metadata': {
                    'category': 'transaction',
                    'detection_method': 'pattern'
                }
            }
        ]
        
        for rule_data in rules:
            self._create_or_update_rule(rule_data)
    
    def _seed_account_rules(self):
        """Seed account-focused fraud detection rules."""
        self.stdout.write('Seeding account fraud rules...')
        
        rules = [
            {
                'name': 'Account Takeover',
                'rule_type': RuleType.PATTERN,
                'description': 'Detect potential account takeover attempts',
                'condition': {
                    'field': 'ato_score',
                    'operator': '>',
                    'value': 70
                },
                'weight': 90,
                'threshold': 80,
                'severity': SeverityLevel.CRITICAL,
                'action_on_trigger': ActionOnTrigger.BLOCK,
                'metadata': {
                    'category': 'account',
                    'detection_method': 'behavioral'
                }
            },
            {
                'name': 'Synthetic Identity',
                'rule_type': RuleType.PATTERN,
                'description': 'Detect synthetic identity patterns',
                'condition': {
                    'field': 'synthetic_identity_score',
                    'operator': '>',
                    'value': 75
                },
                'weight': 85,
                'threshold': 75,
                'severity': SeverityLevel.HIGH,
                'action_on_trigger': ActionOnTrigger.FLAG,
                'metadata': {
                    'category': 'account',
                    'detection_method': 'identity_analysis'
                }
            },
            {
                'name': 'First Party Fraud',
                'rule_type': RuleType.PATTERN,
                'description': 'Detect first-party fraud patterns',
                'condition': {
                    'field': 'first_party_fraud_score',
                    'operator': '>',
                    'value': 65
                },
                'weight': 80,
                'threshold': 70,
                'severity': SeverityLevel.HIGH,
                'action_on_trigger': ActionOnTrigger.FLAG,
                'metadata': {
                    'category': 'account',
                    'detection_method': 'behavioral'
                }
            },
            {
                'name': 'Account Age Mismatch',
                'rule_type': RuleType.PATTERN,
                'description': 'Detect mismatch between account age and behavior',
                'condition': {
                    'field': 'age_behavior_mismatch_score',
                    'operator': '>',
                    'value': 60
                },
                'weight': 70,
                'threshold': 60,
                'severity': SeverityLevel.MEDIUM,
                'action_on_trigger': ActionOnTrigger.ALERT,
                'metadata': {
                    'category': 'account',
                    'detection_method': 'temporal'
                }
            },
            {
                'name': 'Profile Inconsistency',
                'rule_type': RuleType.PATTERN,
                'description': 'Detect inconsistencies in user profile',
                'condition': {
                    'field': 'profile_consistency_score',
                    'operator': '<',
                    'value': 0.5
                },
                'weight': 60,
                'threshold': 50,
                'severity': SeverityLevel.MEDIUM,
                'action_on_trigger': ActionOnTrigger.FLAG,
                'metadata': {
                    'category': 'account',
                    'detection_method': 'profile_analysis'
                }
            },
            {
                'name': 'Rapid Account Creation',
                'rule_type': RuleType.PATTERN,
                'description': 'Detect rapid account creation from same source',
                'condition': {
                    'field': 'rapid_creation_score',
                    'operator': '>',
                    'value': 70
                },
                'weight': 75,
                'threshold': 65,
                'severity': SeverityLevel.HIGH,
                'action_on_trigger': ActionOnTrigger.FLAG,
                'metadata': {
                    'category': 'account',
                    'detection_method': 'frequency'
                }
            }
        ]
        
        for rule_data in rules:
            self._create_or_update_rule(rule_data)
    
    def _create_or_update_rule(self, rule_data):
        """Create or update a fraud rule."""
        try:
            # Check if rule already exists
            existing_rule = FraudRule.objects.filter(name=rule_data['name']).first()
            
            if existing_rule:
                if self.overwrite:
                    # Update existing rule
                    for key, value in rule_data.items():
                        setattr(existing_rule, key, value)
                    existing_rule.save()
                    
                    self.results['rules_updated'] += 1
                    
                    if self.verbose:
                        self.stdout.write(f'  ✅ Updated rule: {rule_data["name"]}')
                else:
                    # Skip existing rule
                    self.results['rules_skipped'] += 1
                    
                    if self.verbose:
                        self.stdout.write(f'  ⏭️  Skipped existing rule: {rule_data["name"]}')
            else:
                # Create new rule
                if not self.dry_run:
                    rule = FraudRule.objects.create(**rule_data)
                    
                    self.results['rules_created'] += 1
                    
                    if self.verbose:
                        self.stdout.write(f'  ✅ Created rule: {rule_data["name"]}')
                else:
                    self.results['rules_created'] += 1
                    
                    if self.verbose:
                        self.stdout.write(f'  📋 Would create rule: {rule_data["name"]}')
                        
        except Exception as e:
            error_msg = f"Error creating rule {rule_data.get('name', 'Unknown')}: {e}"
            logger.error(error_msg)
            self.results['errors'].append(error_msg)
    
    def _print_summary(self):
        """Print seeding summary."""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('FRAUD RULES SEEDING SUMMARY'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'Rule Type: {self.rule_type}')
        self.stdout.write(f'Rules Created: {self.results["rules_created"]}')
        self.stdout.write(f'Rules Updated: {self.results["rules_updated"]}')
        self.stdout.write(f'Rules Skipped: {self.results["rules_skipped"]}')
        self.stdout.write(f'Errors: {len(self.results["errors"])}')
        
        if self.results['errors'] and self.verbose:
            self.stdout.write('\nErrors:')
            for error in self.results['errors']:
                self.stdout.write(f'  ❌ {error}')
        
        # Show rule count by type
        if not self.dry_run:
            rule_counts = {}
            for rule_type, _ in RuleType.choices:
                count = FraudRule.objects.filter(rule_type=rule_type).count()
                if count > 0:
                    rule_counts[rule_type] = count
            
            if rule_counts:
                self.stdout.write('\nRules by Type:')
                for rule_type, count in rule_counts.items():
                    self.stdout.write(f'  {rule_type}: {count}')
        
        self.stdout.write('=' * 60)
