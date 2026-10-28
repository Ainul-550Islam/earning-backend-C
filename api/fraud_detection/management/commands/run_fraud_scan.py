# =============================================================================
# fraud_detection/management/commands/run_fraud_scan.py
# =============================================================================
"""
Run Fraud Scan Management Command.

Manual fraud scanning command for comprehensive fraud detection
across users, transactions, and system activity.
"""
from django.db import models

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction

from api.fraud_detection.models import (
    FraudAttempt, FraudAlert, UserRiskProfile, 
    FraudCase, IPReputation, DeviceFingerprint
)
from api.fraud_detection.services.FraudCaseService import FraudCaseService
from api.fraud_detection.services.IPReputationService import IPReputationService
from api.fraud_detection.calculators.FraudScoreCalculator import FraudScoreCalculator
from api.fraud_detection.detectors.ClickFraudDetector import ClickFraudDetector
from api.fraud_detection.detectors.MultiAccountDetector import MultiAccountDetector
from api.fraud_detection.detectors.VPNProxyDetector import VPNProxyDetector
from api.fraud_detection.detectors.DeviceFingerprinter import DeviceFingerprinter

import json
import logging
from datetime import timedelta
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run comprehensive fraud scan across the system'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--scan-type',
            type=str,
            choices=['all', 'users', 'transactions', 'ips', 'devices', 'patterns'],
            default='all',
            help='Type of fraud scan to run'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Specific user ID to scan (optional)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to look back for scan'
        )
        parser.add_argument(
            '--risk-threshold',
            type=int,
            default=70,
            help='Risk score threshold for alert creation'
        )
        parser.add_argument(
            '--create-cases',
            action='store_true',
            help='Create fraud cases for high-risk findings'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run scan without creating alerts or cases'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output with detailed scan results'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for processing users'
        )
    
    def handle(self, *args, **options):
        """Execute the fraud scan command."""
        self.scan_type = options['scan_type']
        self.user_id = options['user_id']
        self.days = options['days']
        self.risk_threshold = options['risk_threshold']
        self.create_cases = options['create_cases']
        self.dry_run = options['dry_run']
        self.verbose = options['verbose']
        self.batch_size = options['batch_size']
        
        self.cutoff_date = timezone.now() - timedelta(days=self.days)
        
        # Initialize services
        self.case_service = FraudCaseService()
        self.ip_service = IPReputationService()
        self.score_calculator = FraudScoreCalculator()
        
        # Initialize detectors
        self.click_detector = ClickFraudDetector()
        self.multi_account_detector = MultiAccountDetector()
        self.vpn_detector = VPNProxyDetector()
        self.device_detector = DeviceFingerprinter()
        
        # Scan results
        self.scan_results = {
            'users_scanned': 0,
            'alerts_created': 0,
            'cases_created': 0,
            'high_risk_users': 0,
            'suspicious_ips': 0,
            'suspicious_devices': 0,
            'patterns_detected': 0,
            'errors': []
        }
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting fraud scan: {self.scan_type} '
                f'(last {self.days} days, threshold: {self.risk_threshold})'
            )
        )
        
        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No alerts or cases will be created')
            )
        
        try:
            with transaction.atomic():
                self._execute_scan()
                
                self._print_summary()
                
        except Exception as e:
            logger.error(f"Fraud scan failed: {e}")
            raise CommandError(f"Fraud scan failed: {e}")
    
    def _execute_scan(self):
        """Execute the appropriate scan type."""
        if self.scan_type == 'all':
            self._scan_all()
        elif self.scan_type == 'users':
            self._scan_users()
        elif self.scan_type == 'transactions':
            self._scan_transactions()
        elif self.scan_type == 'ips':
            self._scan_ips()
        elif self.scan_type == 'devices':
            self._scan_devices()
        elif self.scan_type == 'patterns':
            self._scan_patterns()
    
    def _scan_all(self):
        """Run comprehensive fraud scan."""
        self.stdout.write('Running comprehensive fraud scan...')
        
        # Scan users
        self._scan_users()
        
        # Scan IPs
        self._scan_ips()
        
        # Scan devices
        self._scan_devices()
        
        # Scan patterns
        self._scan_patterns()
        
        # Scan transactions
        self._scan_transactions()
    
    def _scan_users(self):
        """Scan users for fraud indicators."""
        self.stdout.write('Scanning users...')
        
        # Get users to scan
        if self.user_id:
            users = User.objects.filter(id=self.user_id)
        else:
            users = User.objects.filter(
                is_active=True,
                date_joined__gte=self.cutoff_date
            )
        
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
                self._scan_user(user)
                self.scan_results['users_scanned'] += 1
            except Exception as e:
                error_msg = f"Error scanning user {user.id}: {e}"
                logger.error(error_msg)
                self.scan_results['errors'].append(error_msg)
    
    def _scan_user(self, user):
        """Scan individual user for fraud indicators."""
        user_risk_data = {}
        
        # Get or create user risk profile
        risk_profile, created = UserRiskProfile.objects.get_or_create(
            user=user,
            defaults={
                'overall_risk_score': 0,
                'monitoring_level': 'standard',
                'is_flagged': False,
                'is_restricted': False,
            }
        )
        
        # Calculate user risk score
        user_score = self.score_calculator.calculate_user_risk_score(user.id)
        user_risk_data['user_score'] = user_score
        
        # Check for multi-account activity
        multi_account_result = self.multi_account_detector.detect_multi_account_activity(user.id)
        user_risk_data['multi_account'] = multi_account_result
        
        # Check IP consistency
        recent_attempts = FraudAttempt.objects.filter(
            user=user,
            created_at__gte=self.cutoff_date
        )
        
        ip_analysis = {}
        for attempt in recent_attempts:
            evidence = attempt.evidence_data
            if isinstance(evidence, str):
                evidence = json.loads(evidence)
            
            if 'ip_address' in evidence:
                ip = evidence['ip_address']
                if ip not in ip_analysis:
                    ip_result = self.vpn_detector.detect_vpn_proxy(user.id, ip)
                    ip_analysis[ip] = ip_result
        
        user_risk_data['ip_analysis'] = ip_analysis
        
        # Check device consistency
        device_analysis = {}
        for attempt in recent_attempts:
            evidence = attempt.evidence_data
            if isinstance(evidence, str):
                evidence = json.loads(evidence)
            
            if 'device_hash' in evidence:
                device = evidence['device_hash']
                if device not in device_analysis:
                    device_result = self.device_detector.check_consistency(user.id, evidence)
                    device_analysis[device] = device_result
        
        user_risk_data['device_analysis'] = device_analysis
        
        # Calculate overall risk
        overall_risk = self._calculate_overall_user_risk(user_risk_data)
        
        # Update risk profile
        risk_profile.overall_risk_score = overall_risk
        risk_profile.is_flagged = overall_risk >= self.risk_threshold
        risk_profile.last_risk_assessment = timezone.now()
        
        # Update fraud attempt counts
        risk_profile.total_fraud_attempts = recent_attempts.count()
        risk_profile.confirmed_fraud_attempts = recent_attempts.filter(
            status='confirmed'
        ).count()
        
        risk_profile.save()
        
        # Create alert if high risk
        if overall_risk >= self.risk_threshold and not self.dry_run:
            self._create_user_alert(user, overall_risk, user_risk_data)
            self.scan_results['high_risk_users'] += 1
        
        # Create case if requested
        if self.create_cases and overall_risk >= (self.risk_threshold + 10) and not self.dry_run:
            self._create_user_case(user, overall_risk, user_risk_data)
            self.scan_results['cases_created'] += 1
        
        if self.verbose and overall_risk >= 50:
            self.stdout.write(
                f'User {user.id}: Risk {overall_risk} '
                f'(Multi-account: {multi_account_result.get("is_suspicious", False)})'
            )
    
    def _scan_transactions(self):
        """Scan transactions for fraud indicators."""
        self.stdout.write('Scanning transactions...')
        
        # Get recent fraud attempts with transaction data
        attempts = FraudAttempt.objects.filter(
            created_at__gte=self.cutoff_date,
            amount_involved__gt=0
        ).select_related('user')
        
        total_attempts = attempts.count()
        self.stdout.write(f'Processing {total_attempts} transactions...')
        
        high_risk_count = 0
        for attempt in attempts:
            try:
                # Analyze transaction
                transaction_data = {
                    'amount': attempt.amount_involved,
                    'currency': 'USD',  # Default currency
                    'user_id': attempt.user.id,
                    'time_of_day': attempt.created_at.hour,
                }
                
                # Get user history
                user_attempts = FraudAttempt.objects.filter(
                    user=attempt.user,
                    amount_involved__gt=0
                )
                
                if user_attempts.exists():
                    avg_amount = user_attempts.aggregate(
                        avg=models.Avg('amount_involved')
                    )['avg'] or 0
                    
                    transaction_data['user_history'] = {
                        'avg_transaction_amount': avg_amount,
                        'transaction_frequency': user_attempts.count(),
                        'last_transaction_hours': (
                            timezone.now() - user_attempts.latest('created_at').created_at
                        ).total_seconds() / 3600
                    }
                
                # Calculate transaction risk
                transaction_risk = self.score_calculator.calculate_transaction_risk_score(
                    transaction_data
                )
                
                # Create alert if high risk
                if transaction_risk >= self.risk_threshold and not self.dry_run:
                    self._create_transaction_alert(attempt, transaction_risk)
                    high_risk_count += 1
                
                if self.verbose and transaction_risk >= 50:
                    self.stdout.write(
                        f'Transaction {attempt.id}: Risk {transaction_risk:.1f} '
                        f'Amount: ${attempt.amount_involved}'
                    )
                    
            except Exception as e:
                error_msg = f"Error scanning transaction {attempt.id}: {e}"
                logger.error(error_msg)
                self.scan_results['errors'].append(error_msg)
        
        self.scan_results['patterns_detected'] += high_risk_count
        self.stdout.write(f'Found {high_risk_count} high-risk transactions')
    
    def _scan_ips(self):
        """Scan IP addresses for fraud indicators."""
        self.stdout.write('Scanning IP addresses...')
        
        # Get IPs with recent activity
        ips = IPReputation.objects.filter(
            last_seen__gte=self.cutoff_date
        )
        
        total_ips = ips.count()
        self.stdout.write(f'Processing {total_ips} IP addresses...')
        
        suspicious_count = 0
        for ip_rep in ips:
            try:
                # Analyze IP reputation
                analysis = self.ip_service.check_ip_risk(ip_rep.ip_address)
                
                # Update IP reputation if needed
                if analysis['fraud_score'] != ip_rep.fraud_score:
                    ip_rep.fraud_score = analysis['fraud_score']
                    ip_rep.save()
                
                # Create alert if high risk
                if analysis['fraud_score'] >= self.risk_threshold and not self.dry_run:
                    self._create_ip_alert(ip_rep, analysis)
                    suspicious_count += 1
                
                if self.verbose and analysis['fraud_score'] >= 50:
                    self.stdout.write(
                        f'IP {ip_rep.ip_address}: Risk {analysis["fraud_score"]:.1f} '
                        f'Blacklisted: {analysis["is_blacklisted"]}'
                    )
                    
            except Exception as e:
                error_msg = f"Error scanning IP {ip_rep.ip_address}: {e}"
                logger.error(error_msg)
                self.scan_results['errors'].append(error_msg)
        
        self.scan_results['suspicious_ips'] += suspicious_count
        self.stdout.write(f'Found {suspicious_count} suspicious IP addresses')
    
    def _scan_devices(self):
        """Scan devices for fraud indicators."""
        self.stdout.write('Scanning devices...')
        
        # Get devices with recent activity
        devices = DeviceFingerprint.objects.filter(
            last_seen__gte=self.cutoff_date
        ).select_related('user')
        
        total_devices = devices.count()
        self.stdout.write(f'Processing {total_devices} devices...')
        
        suspicious_count = 0
        for device in devices:
            try:
                # Analyze device patterns
                patterns = self.device_detector.detect_suspicious_patterns(device.device_hash)
                
                # Update trust score if needed
                if patterns.get('risk_score', 0) != device.trust_score:
                    device.trust_score = patterns.get('risk_score', 0)
                    device.save()
                
                # Create alert if high risk
                if patterns.get('risk_score', 0) >= (100 - self.risk_threshold) and not self.dry_run:
                    self._create_device_alert(device, patterns)
                    suspicious_count += 1
                
                if self.verbose and patterns.get('risk_score', 0) >= 30:
                    self.stdout.write(
                        f'Device {device.device_hash[:8]}...: Trust {device.trust_score} '
                        f'VPN: {device.is_vpn}'
                    )
                    
            except Exception as e:
                error_msg = f"Error scanning device {device.device_hash}: {e}"
                logger.error(error_msg)
                self.scan_results['errors'].append(error_msg)
        
        self.scan_results['suspicious_devices'] += suspicious_count
        self.stdout.write(f'Found {suspicious_count} suspicious devices')
    
    def _scan_patterns(self):
        """Scan for fraud patterns across the system."""
        self.stdout.write('Scanning fraud patterns...')
        
        # Get users with sufficient activity for pattern analysis
        active_users = User.objects.filter(
            fraudattempt__created_at__gte=self.cutoff_date
        ).distinct()
        
        pattern_count = 0
        for user in active_users:
            try:
                # Analyze behavioral patterns
                from api.fraud_detection.detectors.PatternAnalyzer import PatternAnalyzer
                analyzer = PatternAnalyzer()
                
                behavioral_patterns = analyzer.analyze_behavioral_patterns(user.id)
                
                # Create alert if suspicious patterns detected
                if behavioral_patterns.get('anomaly_score', 0) >= self.risk_threshold and not self.dry_run:
                    self._create_pattern_alert(user, behavioral_patterns)
                    pattern_count += 1
                
                if self.verbose and behavioral_patterns.get('anomaly_score', 0) >= 30:
                    self.stdout.write(
                        f'User {user.id}: Pattern anomaly {behavioral_patterns["anomaly_score"]:.1f}'
                    )
                    
            except Exception as e:
                error_msg = f"Error scanning patterns for user {user.id}: {e}"
                logger.error(error_msg)
                self.scan_results['errors'].append(error_msg)
        
        self.scan_results['patterns_detected'] += pattern_count
        self.stdout.write(f'Found {pattern_count} suspicious patterns')
    
    def _calculate_overall_user_risk(self, user_risk_data):
        """Calculate overall user risk from multiple indicators."""
        risk_scores = []
        
        # User score
        if 'user_score' in user_risk_data:
            risk_scores.append(user_risk_data['user_score'])
        
        # Multi-account risk
        if 'multi_account' in user_risk_data:
            multi_account = user_risk_data['multi_account']
            if multi_account.get('is_suspicious', False):
                risk_scores.append(multi_account.get('risk_score', 70))
        
        # IP risks
        if 'ip_analysis' in user_risk_data:
            for ip_data in user_risk_data['ip_analysis'].values():
                if ip_data.get('risk_score', 0) >= 50:
                    risk_scores.append(ip_data['risk_score'])
        
        # Device risks
        if 'device_analysis' in user_risk_data:
            for device_data in user_risk_data['device_analysis'].values():
                if device_data.get('risk_score', 0) >= 50:
                    risk_scores.append(device_data['risk_score'])
        
        # Calculate weighted average
        if risk_scores:
            return sum(risk_scores) / len(risk_scores)
        else:
            return 0
    
    def _create_user_alert(self, user, risk_score, risk_data):
        """Create fraud alert for high-risk user."""
        alert = FraudAlert.objects.create(
            user=user,
            alert_type='user_risk',
            priority='high' if risk_score >= 80 else 'medium',
            title=f'High Risk User: {user.username}',
            description=f'User risk score of {risk_score:.1f} detected',
            data={
                'risk_score': risk_score,
                'risk_data': risk_data,
                'scan_type': self.scan_type,
            }
        )
        
        self.scan_results['alerts_created'] += 1
        
        if self.verbose:
            self.stdout.write(
                self.style.WARNING(
                    f'Created alert for user {user.id} (risk: {risk_score:.1f})'
                )
            )
    
    def _create_transaction_alert(self, attempt, risk_score):
        """Create fraud alert for high-risk transaction."""
        alert = FraudAlert.objects.create(
            user=attempt.user,
            alert_type='transaction_risk',
            priority='high' if risk_score >= 80 else 'medium',
            title=f'Suspicious Transaction: ${attempt.amount_involved}',
            description=f'Transaction risk score of {risk_score:.1f} detected',
            data={
                'attempt_id': attempt.id,
                'amount': attempt.amount_involved,
                'risk_score': risk_score,
                'scan_type': self.scan_type,
            }
        )
        
        self.scan_results['alerts_created'] += 1
    
    def _create_ip_alert(self, ip_rep, analysis):
        """Create fraud alert for suspicious IP."""
        alert = FraudAlert.objects.create(
            alert_type='ip_risk',
            priority='high' if analysis['fraud_score'] >= 80 else 'medium',
            title=f'Suspicious IP: {ip_rep.ip_address}',
            description=f'IP risk score of {analysis["fraud_score"]:.1f} detected',
            data={
                'ip_address': ip_rep.ip_address,
                'analysis': analysis,
                'scan_type': self.scan_type,
            }
        )
        
        self.scan_results['alerts_created'] += 1
    
    def _create_device_alert(self, device, patterns):
        """Create fraud alert for suspicious device."""
        alert = FraudAlert.objects.create(
            user=device.user,
            alert_type='device_risk',
            priority='high' if patterns.get('risk_score', 0) >= 70 else 'medium',
            title=f'Suspicious Device: {device.device_hash[:8]}...',
            description=f'Device trust score of {device.trust_score} detected',
            data={
                'device_hash': device.device_hash,
                'patterns': patterns,
                'scan_type': self.scan_type,
            }
        )
        
        self.scan_results['alerts_created'] += 1
    
    def _create_pattern_alert(self, user, patterns):
        """Create fraud alert for suspicious patterns."""
        alert = FraudAlert.objects.create(
            user=user,
            alert_type='pattern_anomaly',
            priority='high' if patterns.get('anomaly_score', 0) >= 80 else 'medium',
            title=f'Suspicious Patterns: {user.username}',
            description=f'Pattern anomaly score of {patterns["anomaly_score"]:.1f} detected',
            data={
                'user_id': user.id,
                'patterns': patterns,
                'scan_type': self.scan_type,
            }
        )
        
        self.scan_results['alerts_created'] += 1
    
    def _create_user_case(self, user, risk_score, risk_data):
        """Create fraud case for high-risk user."""
        case = self.case_service.create_case(
            user_id=user.id,
            title=f'High Risk User: {user.username}',
            description=f'Fraud scan detected high risk score of {risk_score:.1f}',
            risk_score=int(risk_score),
            evidence_data=risk_data
        )
        
        if self.verbose:
            self.stdout.write(
                self.style.ERROR(
                    f'Created case for user {user.id} (risk: {risk_score:.1f})'
                )
            )
    
    def _print_summary(self):
        """Print scan summary."""
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('FRAUD SCAN SUMMARY'))
        self.stdout.write('=' * 50)
        self.stdout.write(f'Users Scanned: {self.scan_results["users_scanned"]}')
        self.stdout.write(f'Alerts Created: {self.scan_results["alerts_created"]}')
        self.stdout.write(f'Cases Created: {self.scan_results["cases_created"]}')
        self.stdout.write(f'High Risk Users: {self.scan_results["high_risk_users"]}')
        self.stdout.write(f'Suspicious IPs: {self.scan_results["suspicious_ips"]}')
        self.stdout.write(f'Suspicious Devices: {self.scan_results["suspicious_devices"]}')
        self.stdout.write(f'Patterns Detected: {self.scan_results["patterns_detected"]}')
        self.stdout.write(f'Errors: {len(self.scan_results["errors"])}')
        
        if self.scan_results['errors'] and self.verbose:
            self.stdout.write('\nErrors:')
            for error in self.scan_results['errors']:
                self.stdout.write(f'  - {error}')
        
        self.stdout.write('=' * 50)
