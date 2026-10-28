# =============================================================================
# fraud_detection/management/commands/recalculate_risk_scores.py
# =============================================================================
"""
Recalculate Risk Scores Management Command.

Recalculates and updates risk scores for users, IPs, devices,
and other entities based on recent activity and historical data.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction

from api.fraud_detection.models import (
    UserRiskProfile, IPReputation, DeviceFingerprint,
    FraudAttempt, FraudCase, FraudAlert
)
from api.fraud_detection.services.FraudScoreCalculator import FraudScoreCalculator
from api.fraud_detection.services.FraudCaseService import FraudCaseService

import json
import logging
from datetime import timedelta
from typing import Dict, List, Any, Tuple

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Recalculate risk scores for users, IPs, and devices'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--entity-type',
            type=str,
            choices=['all', 'users', 'ips', 'devices', 'cases'],
            default='all',
            help='Type of entity to recalculate'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Specific user ID to recalculate (optional)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to look back for calculation'
        )
        parser.add_argument(
            '--force-update',
            action='store_true',
            help='Force update even if recent calculation exists'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for processing'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output with detailed results'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Calculate without updating database'
        )
    
    def handle(self, *args, **options):
        """Execute the risk score recalculation command."""
        self.entity_type = options['entity_type']
        self.user_id = options['user_id']
        self.days = options['days']
        self.force_update = options['force_update']
        self.batch_size = options['batch_size']
        self.verbose = options['verbose']
        self.dry_run = options['dry_run']
        
        self.cutoff_date = timezone.now() - timedelta(days=self.days)
        
        # Initialize calculator
        self.calculator = FraudScoreCalculator()
        
        # Recalculation results
        self.results = {
            'users_updated': 0,
            'ips_updated': 0,
            'devices_updated': 0,
            'cases_updated': 0,
            'errors': [],
            'score_changes': {
                'users': [],
                'ips': [],
                'devices': [],
                'cases': []
            }
        }
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Recalculating risk scores: {self.entity_type} '
                f'(last {self.days} days)'
            )
        )
        
        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No database updates will be performed')
            )
        
        try:
            with transaction.atomic():
                self._execute_recalculation()
                
                self._print_summary()
                
        except Exception as e:
            logger.error(f"Risk score recalculation failed: {e}")
            raise CommandError(f"Risk score recalculation failed: {e}")
    
    def _execute_recalculation(self):
        """Execute the appropriate recalculation type."""
        if self.entity_type == 'all':
            self._recalculate_all()
        elif self.entity_type == 'users':
            self._recalculate_users()
        elif self.entity_type == 'ips':
            self._recalculate_ips()
        elif self.entity_type == 'devices':
            self._recalculate_devices()
        elif self.entity_type == 'cases':
            self._recalculate_cases()
    
    def _recalculate_all(self):
        """Recalculate all entity types."""
        self.stdout.write('Recalculating all risk scores...')
        
        self._recalculate_users()
        self._recalculate_ips()
        self._recalculate_devices()
        self._recalculate_cases()
    
    def _recalculate_users(self):
        """Recalculate user risk scores."""
        self.stdout.write('Recalculating user risk scores...')
        
        # Get users to process
        if self.user_id:
            users = User.objects.filter(id=self.user_id)
        else:
            users = User.objects.filter(
                is_active=True
            ).prefetch_related('risk_profile')
        
        total_users = users.count()
        self.stdout.write(f'Processing {total_users} users...')
        
        # Process in batches
        for i in range(0, total_users, self.batch_size):
            batch = users[i:i + self.batch_size]
            self._process_user_batch(batch)
            
            if self.verbose:
                progress = min(i + self.batch_size, total_users)
                self.stdout.write(f'Processed {progress}/{total_users} users')
    
    def _process_user_batch(self, users):
        """Process a batch of users."""
        for user in users:
            try:
                self._recalculate_user_risk(user)
                self.results['users_updated'] += 1
            except Exception as e:
                error_msg = f"Error recalculating user {user.id}: {e}"
                logger.error(error_msg)
                self.results['errors'].append(error_msg)
    
    def _recalculate_user_risk(self, user):
        """Recalculate individual user risk score."""
        # Get or create risk profile
        risk_profile, created = UserRiskProfile.objects.get_or_create(
            user=user,
            defaults={
                'overall_risk_score': 0,
                'monitoring_level': 'standard',
                'is_flagged': False,
                'is_restricted': False,
            }
        )
        
        # Check if recent calculation exists
        if not self.force_update and risk_profile.last_risk_assessment:
            hours_since_calc = (timezone.now() - risk_profile.last_risk_assessment).total_seconds() / 3600
            if hours_since_calc < 24:  # Skip if calculated within last 24 hours
                if self.verbose:
                    self.stdout.write(f'Skipping user {user.id} (recent calculation)')
                return
        
        # Calculate new risk score
        new_score = self.calculator.calculate_user_risk_score(user.id)
        old_score = risk_profile.overall_risk_score
        
        # Update risk profile
        updates = {
            'overall_risk_score': new_score,
            'last_risk_assessment': timezone.now(),
        }
        
        # Update monitoring level based on score
        if new_score >= 80:
            updates['monitoring_level'] = 'strict'
            updates['is_flagged'] = True
        elif new_score >= 60:
            updates['monitoring_level'] = 'enhanced'
        elif new_score >= 40:
            updates['monitoring_level'] = 'standard'
        else:
            updates['monitoring_level'] = 'basic'
        
        # Update restriction status
        if new_score >= 90:
            updates['is_restricted'] = True
        elif new_score < 70:
            updates['is_restricted'] = False
        
        # Update fraud attempt counts
        recent_attempts = FraudAttempt.objects.filter(
            user=user,
            created_at__gte=self.cutoff_date
        )
        
        updates['total_fraud_attempts'] = recent_attempts.count()
        updates['confirmed_fraud_attempts'] = recent_attempts.filter(
            status='confirmed'
        ).count()
        updates['false_positives'] = recent_attempts.filter(
            status='false_positive'
        ).count()
        
        if not self.dry_run:
            for key, value in updates.items():
                setattr(risk_profile, key, value)
            risk_profile.save()
        
        # Track score change
        if abs(new_score - old_score) > 5:  # Significant change
            self.results['score_changes']['users'].append({
                'user_id': user.id,
                'old_score': old_score,
                'new_score': new_score,
                'change': new_score - old_score
            })
        
        if self.verbose and abs(new_score - old_score) > 10:
            self.stdout.write(
                f'User {user.id}: {old_score} → {new_score} ({new_score - old_score:+.1f})'
            )
    
    def _recalculate_ips(self):
        """Recalculate IP risk scores."""
        self.stdout.write('Recalculating IP risk scores...')
        
        # Get IPs to process
        ips = IPReputation.objects.filter(
            last_seen__gte=self.cutoff_date
        )
        
        total_ips = ips.count()
        self.stdout.write(f'Processing {total_ips} IP addresses...')
        
        # Process in batches
        for i in range(0, total_ips, self.batch_size):
            batch = ips[i:i + self.batch_size]
            self._process_ip_batch(batch)
            
            if self.verbose:
                progress = min(i + self.batch_size, total_ips)
                self.stdout.write(f'Processed {progress}/{total_ips} IPs')
    
    def _process_ip_batch(self, ips):
        """Process a batch of IP addresses."""
        for ip_rep in ips:
            try:
                self._recalculate_ip_risk(ip_rep)
                self.results['ips_updated'] += 1
            except Exception as e:
                error_msg = f"Error recalculating IP {ip_rep.ip_address}: {e}"
                logger.error(error_msg)
                self.results['errors'].append(error_msg)
    
    def _recalculate_ip_risk(self, ip_rep):
        """Recalculate individual IP risk score."""
        old_score = ip_rep.fraud_score
        
        # Calculate new risk score
        new_score = self.calculator.calculate_ip_risk_score(ip_rep.ip_address)
        
        # Update additional metrics
        recent_attempts = FraudAttempt.objects.filter(
            evidence_data__icontains=ip_rep.ip_address,
            created_at__gte=self.cutoff_date
        )
        
        updates = {
            'fraud_score': new_score,
            'total_requests': ip_rep.total_requests + recent_attempts.count(),
        }
        
        # Update fraud attempts count
        confirmed_attempts = recent_attempts.filter(status='confirmed').count()
        updates['fraud_attempts'] = confirmed_attempts
        
        # Update unique users
        unique_users = recent_attempts.values('user_id').distinct().count()
        updates['unique_users'] = max(ip_rep.unique_users, unique_users)
        
        # Auto-blacklist if score is high
        if new_score >= 90 and not ip_rep.is_blacklisted:
            updates['is_blacklisted'] = True
            updates['blacklist_reason'] = "Auto-blacklisted due to high fraud score"
            updates['blacklisted_at'] = timezone.now()
        elif new_score < 70 and ip_rep.is_blacklisted:
            updates['is_blacklisted'] = False
            updates['blacklist_reason'] = None
            updates['blacklisted_at'] = None
        
        if not self.dry_run:
            for key, value in updates.items():
                setattr(ip_rep, key, value)
            ip_rep.save()
        
        # Track score change
        if abs(new_score - old_score) > 5:
            self.results['score_changes']['ips'].append({
                'ip_address': ip_rep.ip_address,
                'old_score': old_score,
                'new_score': new_score,
                'change': new_score - old_score
            })
        
        if self.verbose and abs(new_score - old_score) > 10:
            self.stdout.write(
                f'IP {ip_rep.ip_address}: {old_score} → {new_score} ({new_score - old_score:+.1f})'
            )
    
    def _recalculate_devices(self):
        """Recalculate device risk scores."""
        self.stdout.write('Recalculating device risk scores...')
        
        # Get devices to process
        devices = DeviceFingerprint.objects.filter(
            last_seen__gte=self.cutoff_date
        ).select_related('user')
        
        total_devices = devices.count()
        self.stdout.write(f'Processing {total_devices} devices...')
        
        # Process in batches
        for i in range(0, total_devices, self.batch_size):
            batch = devices[i:i + self.batch_size]
            self._process_device_batch(batch)
            
            if self.verbose:
                progress = min(i + self.batch_size, total_devices)
                self.stdout.write(f'Processed {progress}/{total_devices} devices')
    
    def _process_device_batch(self, devices):
        """Process a batch of devices."""
        for device in devices:
            try:
                self._recalculate_device_risk(device)
                self.results['devices_updated'] += 1
            except Exception as e:
                error_msg = f"Error recalculating device {device.device_hash}: {e}"
                logger.error(error_msg)
                self.results['errors'].append(error_msg)
    
    def _recalculate_device_risk(self, device):
        """Recalculate individual device risk score."""
        old_score = device.trust_score
        new_score = 100 - old_score  # Convert trust score to risk score
        
        # Calculate risk based on user activity
        user_risk = 0
        if device.user:
            try:
                user_risk = self.calculator.calculate_user_risk_score(device.user.id)
            except Exception as e:
                logger.warning("Failed to calculate risk score: %s", e)
                user_risk = 0
        
        # Combine device and user risk
        combined_risk = (new_score + user_risk) / 2
        final_risk_score = min(100, combined_risk)
        
        # Update trust score (inverse of risk)
        new_trust_score = max(0, 100 - final_risk_score)
        
        updates = {
            'trust_score': new_trust_score,
        }
        
        # Update VPN/proxy flags based on recent activity
        recent_attempts = FraudAttempt.objects.filter(
            user=device.user,
            created_at__gte=self.cutoff_date
        )
        
        for attempt in recent_attempts:
            evidence = attempt.evidence_data
            if isinstance(evidence, str):
                evidence = json.loads(evidence)
            
            if evidence.get('is_vpn') and not device.is_vpn:
                updates['is_vpn'] = True
            if evidence.get('is_proxy') and not device.is_proxy:
                updates['is_proxy'] = True
            if evidence.get('is_tor') and not device.is_tor:
                updates['is_tor'] = True
        
        if not self.dry_run:
            for key, value in updates.items():
                setattr(device, key, value)
            device.save()
        
        # Track score change
        if abs(new_trust_score - old_score) > 5:
            self.results['score_changes']['devices'].append({
                'device_hash': device.device_hash[:8] + '...',
                'old_score': old_score,
                'new_score': new_trust_score,
                'change': new_trust_score - old_score
            })
        
        if self.verbose and abs(new_trust_score - old_score) > 10:
            self.stdout.write(
                f'Device {device.device_hash[:8]}...: {old_score} → {new_trust_score} '
                f'({new_trust_score - old_score:+.1f})'
            )
    
    def _recalculate_cases(self):
        """Recalculate case risk scores."""
        self.stdout.write('Recalculating case risk scores...')
        
        # Get cases to process
        cases = FraudCase.objects.filter(
            opened_at__gte=self.cutoff_date
        ).select_related('user')
        
        total_cases = cases.count()
        self.stdout.write(f'Processing {total_cases} cases...')
        
        # Process in batches
        for i in range(0, total_cases, self.batch_size):
            batch = cases[i:i + self.batch_size]
            self._process_case_batch(batch)
            
            if self.verbose:
                progress = min(i + self.batch_size, total_cases)
                self.stdout.write(f'Processed {progress}/{total_cases} cases')
    
    def _process_case_batch(self, cases):
        """Process a batch of cases."""
        for case in cases:
            try:
                self._recalculate_case_risk(case)
                self.results['cases_updated'] += 1
            except Exception as e:
                error_msg = f"Error recalculating case {case.id}: {e}"
                logger.error(error_msg)
                self.results['errors'].append(error_msg)
    
    def _recalculate_case_risk(self, case):
        """Recalculate individual case risk score."""
        old_score = case.risk_score
        
        # Calculate new risk score based on user risk and case factors
        user_risk = 0
        if case.user:
            try:
                user_risk = self.calculator.calculate_user_risk_score(case.user.id)
            except Exception as e:
                logger.warning("Failed to calculate risk score: %s", e)
                user_risk = 0
        
        # Case-specific risk factors
        case_factors = {
            'evidence_count': case.evidence.count(),
            'action_count': case.actions.count(),
            'days_open': (timezone.now() - case.opened_at).days,
            'has_high_value_attempts': case.fraud_attempts.filter(
                amount_involved__gte=500
            ).exists(),
        }
        
        # Calculate case risk score
        case_risk = min(100, user_risk + case_factors['evidence_count'] * 5)
        
        if case_factors['has_high_value_attempts']:
            case_risk = min(100, case_risk + 15)
        
        if case_factors['days_open'] > 30:
            case_risk = min(100, case_risk + 10)
        
        # Update priority based on new score
        new_priority = case.priority
        if case_risk >= 80:
            new_priority = 'critical'
        elif case_risk >= 60:
            new_priority = 'high'
        elif case_risk >= 40:
            new_priority = 'medium'
        else:
            new_priority = 'low'
        
        updates = {
            'risk_score': int(case_risk),
            'priority': new_priority,
        }
        
        if not self.dry_run:
            for key, value in updates.items():
                setattr(case, key, value)
            case.save()
        
        # Track score change
        if abs(case_risk - old_score) > 5:
            self.results['score_changes']['cases'].append({
                'case_id': case.id,
                'case_number': case.case_number,
                'old_score': old_score,
                'new_score': int(case_risk),
                'change': case_risk - old_score
            })
        
        if self.verbose and abs(case_risk - old_score) > 10:
            self.stdout.write(
                f'Case {case.case_number}: {old_score} → {int(case_risk)} '
                f'({case_risk - old_score:+.1f})'
            )
    
    def _print_summary(self):
        """Print recalculation summary."""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('RISK SCORE RECALCULATION SUMMARY'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'Users Updated: {self.results["users_updated"]}')
        self.stdout.write(f'IPs Updated: {self.results["ips_updated"]}')
        self.stdout.write(f'Devices Updated: {self.results["devices_updated"]}')
        self.stdout.write(f'Cases Updated: {self.results["cases_updated"]}')
        self.stdout.write(f'Errors: {len(self.results["errors"])}')
        
        # Print significant score changes
        for entity_type, changes in self.results['score_changes'].items():
            if changes:
                self.stdout.write(f'\n{entity_type.title()} Score Changes:')
                for change in changes[:5]:  # Show top 5 changes
                    entity_id = change.get('user_id') or change.get('ip_address') or change.get('device_hash') or change.get('case_number')
                    self.stdout.write(
                        f'  {entity_id}: {change["old_score"]} → {change["new_score"]} '
                        f'({change["change"]:+.1f})'
                    )
                
                if len(changes) > 5:
                    self.stdout.write(f'  ... and {len(changes) - 5} more changes')
        
        if self.results['errors'] and self.verbose:
            self.stdout.write('\nErrors:')
            for error in self.results['errors']:
                self.stdout.write(f'  - {error}')
        
        self.stdout.write('=' * 60)
