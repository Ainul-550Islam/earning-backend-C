# =============================================================================
# fraud_detection/management/commands/review_flagged_users.py
# =============================================================================
"""
Review Flagged Users Management Command.

Interactive command for reviewing and managing flagged users,
including case creation, status updates, and bulk operations.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.contrib.auth.models import User

from api.fraud_detection.models import UserRiskProfile, FraudCase, FraudAlert
from api.fraud_detection.services.ReviewService import ReviewService
from api.fraud_detection.services.FraudCaseService import FraudCaseService

import json
import logging
from datetime import timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Review and manage flagged users interactively'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--risk-threshold',
            type=int,
            default=70,
            help='Minimum risk score threshold for flagged users'
        )
        parser.add_argument(
            '--monitoring-level',
            type=str,
            choices=['all', 'strict', 'enhanced', 'standard'],
            default='all',
            help='Filter by monitoring level'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to look back for recent activity'
        )
        parser.add_argument(
            '--auto-review',
            action='store_true',
            help='Auto-review low-risk users without interaction'
        )
        parser.add_argument(
            '--create-cases',
            action='store_true',
            help='Automatically create cases for high-risk users'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Batch size for processing'
        )
        parser.add_argument(
            '--export',
            type=str,
            help='Export results to file (JSON format)'
        )
        parser.add_argument(
            '--non-interactive',
            action='store_true',
            help='Run without interactive prompts'
        )
    
    def handle(self, *args, **options):
        """Execute the flagged users review command."""
        self.risk_threshold = options['risk_threshold']
        self.monitoring_level = options['monitoring_level']
        self.days = options['days']
        self.auto_review = options['auto_review']
        self.create_cases = options['create_cases']
        self.batch_size = options['batch_size']
        self.export_file = options['export']
        self.non_interactive = options['non_interactive']
        
        self.cutoff_date = timezone.now() - timedelta(days=self.days)
        
        # Initialize services
        self.review_service = ReviewService()
        self.case_service = FraudCaseService()
        
        # Review results
        self.review_results = {
            'total_flagged': 0,
            'users_reviewed': 0,
            'cases_created': 0,
            'users_cleared': 0,
            'users_restricted': 0,
            'alerts_created': 0,
            'errors': [],
            'actions_taken': []
        }
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Reviewing flagged users (threshold: {self.risk_threshold}, '
                f'last {self.days} days)'
            )
        )
        
        if self.non_interactive:
            self.stdout.write(
                self.style.WARNING('NON-INTERACTIVE MODE - Using default actions')
            )
        
        try:
            self._execute_review()
            
            self._print_summary()
            
            if self.export_file:
                self._export_results()
                
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.ERROR('\nReview interrupted by user')
            )
        except Exception as e:
            logger.error(f"Flagged users review failed: {e}")
            raise CommandError(f"Flagged users review failed: {e}")
    
    def _execute_review(self):
        """Execute the flagged users review process."""
        # Get flagged users
        flagged_users = self._get_flagged_users()
        
        if not flagged_users.exists():
            self.stdout.write(
                self.style.WARNING('No flagged users found matching criteria')
            )
            return
        
        self.review_results['total_flagged'] = flagged_users.count()
        self.stdout.write(
            f'Found {flagged_users.count()} flagged users to review'
        )
        
        # Process users in batches
        for i in range(0, flagged_users.count(), self.batch_size):
            batch = flagged_users[i:i + self.batch_size]
            self._process_user_batch(batch)
            
            if not self.non_interactive:
                self.stdout.write(
                    f'\nBatch {i//self.batch_size + 1} completed. '
                    f'Press Enter to continue or Ctrl+C to exit...'
                )
                input()
    
    def _get_flagged_users(self):
        """Get flagged users based on criteria."""
        queryset = UserRiskProfile.objects.filter(
            is_flagged=True,
            overall_risk_score__gte=self.risk_threshold,
            last_risk_assessment__gte=self.cutoff_date
        ).select_related('user').order_by('-overall_risk_score')
        
        if self.monitoring_level != 'all':
            queryset = queryset.filter(monitoring_level=self.monitoring_level)
        
        return queryset
    
    def _process_user_batch(self, risk_profiles):
        """Process a batch of flagged users."""
        for risk_profile in risk_profiles:
            try:
                self._review_flagged_user(risk_profile)
                self.review_results['users_reviewed'] += 1
            except Exception as e:
                error_msg = f"Error reviewing user {risk_profile.user.id}: {e}"
                logger.error(error_msg)
                self.review_results['errors'].append(error_msg)
    
    def _review_flagged_user(self, risk_profile):
        """Review individual flagged user."""
        user = risk_profile.user
        
        # Display user information
        self._display_user_info(risk_profile)
        
        # Get user activity summary
        activity_summary = self._get_activity_summary(user)
        self._display_activity_summary(activity_summary)
        
        # Determine action
        if self.non_interactive:
            action = self._determine_auto_action(risk_profile, activity_summary)
        else:
            action = self._get_user_action(risk_profile, activity_summary)
        
        # Execute action
        self._execute_user_action(user, risk_profile, action, activity_summary)
    
    def _display_user_info(self, risk_profile):
        """Display user risk profile information."""
        user = risk_profile.user
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(
            self.style.WARNING(f'USER: {user.username} (ID: {user.id})')
        )
        self.stdout.write('=' * 60)
        self.stdout.write(f'Email: {user.email}')
        self.stdout.write(f'Risk Score: {risk_profile.overall_risk_score}')
        self.stdout.write(f'Monitoring Level: {risk_profile.monitoring_level}')
        self.stdout.write(f'Is Restricted: {risk_profile.is_restricted}')
        self.stdout.write(f'Total Fraud Attempts: {risk_profile.total_fraud_attempts}')
        self.stdout.write(f'Confirmed Fraud: {risk_profile.confirmed_fraud_attempts}')
        self.stdout.write(f'False Positives: {risk_profile.false_positives}')
        self.stdout.write(f'Last Assessment: {risk_profile.last_risk_assessment}')
        
        # Show existing cases
        existing_cases = FraudCase.objects.filter(user=user).order_by('-opened_at')
        if existing_cases.exists():
            self.stdout.write(f'\nExisting Cases: {existing_cases.count()}')
            for case in existing_cases[:3]:  # Show last 3 cases
                self.stdout.write(
                    f'  - {case.case_number}: {case.status} '
                    f'(Priority: {case.priority})'
                )
    
    def _get_activity_summary(self, user):
        """Get user activity summary."""
        from api.fraud_detection.models import FraudAttempt, DeviceFingerprint, IPReputation
        
        summary = {
            'recent_attempts': FraudAttempt.objects.filter(
                user=user,
                created_at__gte=self.cutoff_date
            ).count(),
            'confirmed_attempts': FraudAttempt.objects.filter(
                user=user,
                status='confirmed',
                created_at__gte=self.cutoff_date
            ).count(),
            'unique_ips': FraudAttempt.objects.filter(
                user=user,
                created_at__gte=self.cutoff_date
            ).values('evidence_data').distinct().count(),
            'unique_devices': DeviceFingerprint.objects.filter(
                user=user,
                last_seen__gte=self.cutoff_date
            ).count(),
            'recent_alerts': FraudAlert.objects.filter(
                user=user,
                created_at__gte=self.cutoff_date
            ).count(),
            'high_value_attempts': FraudAttempt.objects.filter(
                user=user,
                amount_involved__gte=500,
                created_at__gte=self.cutoff_date
            ).count(),
        }
        
        return summary
    
    def _display_activity_summary(self, summary):
        """Display user activity summary."""
        self.stdout.write('\nRecent Activity (last 7 days):')
        self.stdout.write(f'  Fraud Attempts: {summary["recent_attempts"]}')
        self.stdout.write(f'  Confirmed: {summary["confirmed_attempts"]}')
        self.stdout.write(f'  Unique IPs: {summary["unique_ips"]}')
        self.stdout.write(f'  Unique Devices: {summary["unique_devices"]}')
        self.stdout.write(f'  Recent Alerts: {summary["recent_alerts"]}')
        self.stdout.write(f'  High Value Attempts: {summary["high_value_attempts"]}')
        
        # Risk indicators
        risk_indicators = []
        if summary['confirmed_attempts'] >= 3:
            risk_indicators.append('Multiple confirmed fraud')
        if summary['high_value_attempts'] >= 2:
            risk_indicators.append('High value attempts')
        if summary['unique_ips'] >= 5:
            risk_indicators.append('Multiple IP addresses')
        if summary['recent_alerts'] >= 5:
            risk_indicators.append('Multiple alerts')
        
        if risk_indicators:
            self.stdout.write('\nRisk Indicators:')
            for indicator in risk_indicators:
                self.stdout.write(f'  ⚠️  {indicator}')
    
    def _determine_auto_action(self, risk_profile, summary):
        """Determine automatic action for non-interactive mode."""
        score = risk_profile.overall_risk_score
        
        # Auto-clear low risk users
        if self.auto_review and score < 50:
            return 'clear'
        
        # Auto-restrict very high risk users
        if score >= 90:
            return 'restrict'
        
        # Auto-create cases for high risk users
        if self.create_cases and score >= 70:
            return 'create_case'
        
        # Default to manual review
        return 'manual_review'
    
    def _get_user_action(self, risk_profile, summary):
        """Get user action choice interactively."""
        score = risk_profile.overall_risk_score
        
        self.stdout.write('\nAvailable Actions:')
        self.stdout.write('1. Clear flag (remove from monitoring)')
        self.stdout.write('2. Create fraud case')
        self.stdout.write('3. Restrict user')
        self.stdout.write('4. Update monitoring level')
        self.stdout.write('5. Skip (no action)')
        self.stdout.write('6. Show detailed evidence')
        
        while True:
            try:
                choice = input('\nSelect action (1-6): ').strip()
                
                if choice == '1':
                    return 'clear'
                elif choice == '2':
                    return 'create_case'
                elif choice == '3':
                    return 'restrict'
                elif choice == '4':
                    return 'update_monitoring'
                elif choice == '5':
                    return 'skip'
                elif choice == '6':
                    self._show_detailed_evidence(risk_profile.user)
                    continue
                else:
                    self.stdout.write('Invalid choice. Please select 1-6.')
                    
            except (EOFError, KeyboardInterrupt):
                return 'skip'
    
    def _show_detailed_evidence(self, user):
        """Show detailed evidence for user."""
        from api.fraud_detection.models import FraudAttempt
        
        self.stdout.write('\n' + '=' * 40)
        self.stdout.write('DETAILED EVIDENCE')
        self.stdout.write('=' * 40)
        
        # Recent fraud attempts
        attempts = FraudAttempt.objects.filter(
            user=user,
            created_at__gte=self.cutoff_date
        ).order_by('-created_at')[:10]
        
        if attempts.exists():
            self.stdout.write('\nRecent Fraud Attempts:')
            for attempt in attempts:
                evidence = attempt.evidence_data
                if isinstance(evidence, str):
                    evidence = json.loads(evidence)
                
                self.stdout.write(f'  {attempt.created_at.strftime("%Y-%m-%d %H:%M")}:')
                self.stdout.write(f'    Type: {attempt.attempt_type}')
                self.stdout.write(f'    Score: {attempt.fraud_score}')
                self.stdout.write(f'    Status: {attempt.status}')
                if attempt.amount_involved:
                    self.stdout.write(f'    Amount: ${attempt.amount_involved}')
                
                if evidence:
                    if 'ip_address' in evidence:
                        self.stdout.write(f'    IP: {evidence["ip_address"]}')
                    if 'device_hash' in evidence:
                        self.stdout.write(f'    Device: {evidence["device_hash"][:8]}...')
        else:
            self.stdout.write('No recent fraud attempts found.')
        
        self.stdout.write('=' * 40)
    
    def _execute_user_action(self, user, risk_profile, action, activity_summary):
        """Execute the chosen action for a user."""
        action_performed = False
        
        if action == 'clear':
            self._clear_user_flag(risk_profile)
            action_performed = True
            self.review_results['users_cleared'] += 1
            
        elif action == 'create_case':
            self._create_user_case(user, risk_profile, activity_summary)
            action_performed = True
            self.review_results['cases_created'] += 1
            
        elif action == 'restrict':
            self._restrict_user(risk_profile)
            action_performed = True
            self.review_results['users_restricted'] += 1
            
        elif action == 'update_monitoring':
            self._update_monitoring_level(risk_profile)
            action_performed = True
            
        elif action == 'manual_review':
            self._schedule_manual_review(risk_profile)
            action_performed = True
            
        elif action == 'skip':
            self.stdout.write('  ⏭️  Skipped')
            return
        
        if action_performed:
            self.review_results['actions_taken'].append({
                'user_id': user.id,
                'username': user.username,
                'action': action,
                'risk_score': risk_profile.overall_risk_score
            })
    
    def _clear_user_flag(self, risk_profile):
        """Clear user flag and reset monitoring."""
        risk_profile.is_flagged = False
        risk_profile.is_restricted = False
        risk_profile.monitoring_level = 'basic'
        risk_profile.overall_risk_score = max(0, risk_profile.overall_risk_score - 20)
        risk_profile.save()
        
        self.stdout.write(f'  ✅ Cleared flag for {risk_profile.user.username}')
    
    def _create_user_case(self, user, risk_profile, activity_summary):
        """Create fraud case for user."""
        case_data = {
            'user_id': user.id,
            'title': f'Flagged User Review: {user.username}',
            'description': f'User flagged with risk score {risk_profile.overall_risk_score}',
            'priority': 'high' if risk_profile.overall_risk_score >= 80 else 'medium',
            'evidence': [
                {
                    'type': 'risk_profile',
                    'data': {
                        'risk_score': risk_profile.overall_risk_score,
                        'monitoring_level': risk_profile.monitoring_level,
                        'total_attempts': risk_profile.total_fraud_attempts,
                        'confirmed_attempts': risk_profile.confirmed_fraud_attempts,
                    },
                    'description': 'User risk profile data'
                },
                {
                    'type': 'activity_summary',
                    'data': activity_summary,
                    'description': 'Recent activity summary'
                }
            ]
        }
        
        case = self.case_service.create_case(
            user_id=user.id,
            title=case_data['title'],
            description=case_data['description'],
            risk_score=risk_profile.overall_risk_score,
            evidence_data=case_data['evidence']
        )
        
        self.stdout.write(f'  📋 Created case {case.case_number} for {user.username}')
    
    def _restrict_user(self, risk_profile):
        """Restrict user account."""
        risk_profile.is_restricted = True
        risk_profile.monitoring_level = 'strict'
        risk_profile.save()
        
        # Also restrict the user account
        user = risk_profile.user
        user.is_active = False
        user.save()
        
        self.stdout.write(f'  🔒 Restricted user {user.username}')
    
    def _update_monitoring_level(self, risk_profile):
        """Update user monitoring level."""
        current_level = risk_profile.monitoring_level
        
        self.stdout.write(f'Current monitoring level: {current_level}')
        self.stdout.write('Options: basic, standard, enhanced, strict')
        
        while True:
            try:
                new_level = input('Enter new monitoring level: ').strip().lower()
                
                if new_level in ['basic', 'standard', 'enhanced', 'strict']:
                    risk_profile.monitoring_level = new_level
                    
                    # Update flag based on level
                    if new_level == 'basic':
                        risk_profile.is_flagged = False
                    elif new_level in ['enhanced', 'strict']:
                        risk_profile.is_flagged = True
                    
                    risk_profile.save()
                    
                    self.stdout.write(f'  📊 Updated monitoring level to {new_level}')
                    break
                else:
                    self.stdout.write('Invalid monitoring level.')
                    
            except (EOFError, KeyboardInterrupt):
                break
    
    def _schedule_manual_review(self, risk_profile):
        """Schedule user for manual review."""
        # Create alert for manual review
        from api.fraud_detection.models import FraudAlert
        
        alert = FraudAlert.objects.create(
            user=risk_profile.user,
            alert_type='manual_review',
            priority='high',
            title=f'Manual Review Required: {risk_profile.user.username}',
            description=f'User requires manual review due to risk score {risk_profile.overall_risk_score}',
            data={
                'risk_score': risk_profile.overall_risk_score,
                'monitoring_level': risk_profile.monitoring_level,
                'review_reason': 'Flagged user review',
            }
        )
        
        self.stdout.write(f'  👤 Scheduled manual review for {risk_profile.user.username}')
        self.review_results['alerts_created'] += 1
    
    def _print_summary(self):
        """Print review summary."""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('FLAGGED USERS REVIEW SUMMARY'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'Total Flagged Users: {self.review_results["total_flagged"]}')
        self.stdout.write(f'Users Reviewed: {self.review_results["users_reviewed"]}')
        self.stdout.write(f'Cases Created: {self.review_results["cases_created"]}')
        self.stdout.write(f'Users Cleared: {self.review_results["users_cleared"]}')
        self.stdout.write(f'Users Restricted: {self.review_results["users_restricted"]}')
        self.stdout.write(f'Alerts Created: {self.review_results["alerts_created"]}')
        self.stdout.write(f'Errors: {len(self.review_results["errors"])}')
        
        if self.review_results['actions_taken']:
            self.stdout.write('\nActions Taken:')
            for action in self.review_results['actions_taken'][:10]:  # Show first 10
                self.stdout.write(
                    f'  {action["username"]}: {action["action"]} '
                    f'(risk: {action["risk_score"]})'
                )
            
            if len(self.review_results['actions_taken']) > 10:
                self.stdout.write(f'  ... and {len(self.review_results["actions_taken"]) - 10} more actions')
        
        if self.review_results['errors'] and self.verbose:
            self.stdout.write('\nErrors:')
            for error in self.review_results['errors']:
                self.stdout.write(f'  - {error}')
        
        self.stdout.write('=' * 60)
    
    def _export_results(self):
        """Export review results to file."""
        try:
            with open(self.export_file, 'w') as f:
                json.dump(self.review_results, f, indent=2, default=str)
            
            self.stdout.write(
                self.style.SUCCESS(f'Results exported to {self.export_file}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to export results: {e}')
            )
