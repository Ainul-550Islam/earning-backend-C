"""
Enhanced User Account Unlock Management Command
Bulk unlock user accounts after lockout period or manual intervention
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
from collections import defaultdict

from ...models import (
    SecurityLog, SecurityIncident, UserBan, RiskScore,
    PasswordHistory, TrustedDevice
)

User = get_user_model()

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Bulk unlock user accounts after lockout period or manual intervention'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--unlock-type',
            type=str,
            choices=['expired', 'manual', 'risk-score', 'all'],
            default='expired',
            help='Type of unlock operation to perform'
        )
        parser.add_argument(
            '--user-ids',
            type=str,
            help='Comma-separated list of user IDs to unlock (for manual unlock)'
        )
        parser.add_argument(
            '--usernames',
            type=str,
            help='Comma-separated list of usernames to unlock (for manual unlock)'
        )
        parser.add_argument(
            '--risk-threshold',
            type=int,
            default=30,
            help='Risk score threshold for unlocking (default: 30)'
        )
        parser.add_argument(
            '--ban-age-hours',
            type=int,
            default=24,
            help='Ban age in hours for expired unlocks (default: 24)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be unlocked without actually unlocking'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force unlock even if user has active security incidents'
        )
        parser.add_argument(
            '--reset-password',
            action='store_true',
            help='Reset user password after unlock'
        )
        parser.add_argument(
            '--clear-sessions',
            action='store_true',
            help='Clear all user sessions after unlock'
        )
        parser.add_argument(
            '--notify-users',
            action='store_true',
            help='Send email notification to unlocked users'
        )
        parser.add_argument(
            '--create-logs',
            action='store_true',
            help='Create security logs for unlock operations'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Batch size for processing (default: 100)'
        )
        parser.add_argument(
            '--exclude-ids',
            type=str,
            help='Comma-separated list of user IDs to exclude from unlock'
        )
        parser.add_argument(
            '--include-inactive',
            action='store_true',
            help='Include inactive users in unlock process'
        )
    
    def handle(self, *args, **options):
        """Execute the user unlock command"""
        self.options = options
        self.unlock_start_time = timezone.now()
        
        try:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Starting user account unlock process: {options['unlock_type']} at {self.unlock_start_time}"
                )
            )
            
            # Initialize data structures
            self.unlocked_users = []
            self.skipped_users = []
            self.error_users = []
            self.exclude_ids = set()
            
            # Parse exclude IDs
            if options['exclude_ids']:
                self.exclude_ids = set(int(id.strip()) for id in options['exclude_ids'].split(','))
            
            # Get users to unlock based on type
            users_to_unlock = self._get_users_to_unlock()
            
            # Filter users for unlocking
            filtered_users = self._filter_users_for_unlock(users_to_unlock)
            
            # Unlock users
            self._unlock_users(filtered_users)
            
            # Reset passwords if requested
            if options['reset_password']:
                self._reset_passwords()
            
            # Clear sessions if requested
            if options['clear_sessions']:
                self._clear_sessions()
            
            # Send notifications if requested
            if options['notify_users']:
                self._send_user_notifications()
            
            # Create logs if requested
            if options['create_logs']:
                self._create_unlock_logs()
            
            # Generate summary
            self._generate_summary()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"User account unlock process completed successfully"
                )
            )
            
        except Exception as e:
            logger.error(f"User account unlock failed: {str(e)}")
            raise CommandError(f"User account unlock failed: {str(e)}")
    
    def _get_users_to_unlock(self):
        """Get users to unlock based on unlock type"""
        unlock_type = self.options['unlock_type']
        
        if unlock_type == 'expired':
            return self._get_expired_ban_users()
        elif unlock_type == 'manual':
            return self._get_manual_unlock_users()
        elif unlock_type == 'risk-score':
            return self._get_risk_score_users()
        elif unlock_type == 'all':
            return self._get_all_banned_users()
        
        return []
    
    def _get_expired_ban_users(self):
        """Get users with expired bans"""
        self.stdout.write("Getting users with expired bans...")
        
        cutoff_time = timezone.now() - timedelta(hours=self.options['ban_age_hours'])
        
        # Get users with expired bans
        expired_bans = UserBan.objects.filter(
            is_active=True,
            created_at__lte=cutoff_time
        ).select_related('user').order_by('created_at')
        
        users = []
        for ban in expired_bans:
            if ban.user.id not in self.exclude_ids:
                users.append({
                    'user': ban.user,
                    'ban': ban,
                    'unlock_reason': f'expired_ban_{self.options["ban_age_hours"]}h',
                    'ban_age_hours': (timezone.now() - ban.created_at).total_seconds() / 3600
                })
        
        self.stdout.write(f"Found {len(users)} users with expired bans")
        return users
    
    def _get_manual_unlock_users(self):
        """Get users for manual unlock"""
        self.stdout.write("Getting users for manual unlock...")
        
        users = []
        
        # Get users by IDs
        if self.options['user_ids']:
            user_ids = [int(id.strip()) for id in self.options['user_ids'].split(',')]
            for user_id in user_ids:
                if user_id in self.exclude_ids:
                    continue
                
                try:
                    user = User.objects.get(id=user_id)
                    ban = UserBan.objects.filter(user=user, is_active=True).first()
                    
                    users.append({
                        'user': user,
                        'ban': ban,
                        'unlock_reason': 'manual_unlock_by_id'
                    })
                except User.DoesNotExist:
                    self.error_users.append({
                        'user_id': user_id,
                        'error': 'User not found'
                    })
        
        # Get users by usernames
        if self.options['usernames']:
            usernames = [username.strip() for username in self.options['usernames'].split(',')]
            for username in usernames:
                try:
                    user = User.objects.get(username=username)
                    if user.id in self.exclude_ids:
                        continue
                    
                    ban = UserBan.objects.filter(user=user, is_active=True).first()
                    
                    users.append({
                        'user': user,
                        'ban': ban,
                        'unlock_reason': 'manual_unlock_by_username'
                    })
                except User.DoesNotExist:
                    self.error_users.append({
                        'username': username,
                        'error': 'User not found'
                    })
        
        self.stdout.write(f"Found {len(users)} users for manual unlock")
        return users
    
    def _get_risk_score_users(self):
        """Get users with low risk scores"""
        self.stdout.write("Getting users with low risk scores...")
        
        risk_threshold = self.options['risk_threshold']
        
        # Get users with active bans and low risk scores
        banned_users = UserBan.objects.filter(
            is_active=True
        ).select_related('user')
        
        users = []
        for ban in banned_users:
            if ban.user.id in self.exclude_ids:
                continue
            
            # Get latest risk score
            latest_risk_score = RiskScore.objects.filter(
                user=ban.user
            ).order_by('-created_at').first()
            
            if latest_risk_score and latest_risk_score.current_score <= risk_threshold:
                users.append({
                    'user': ban.user,
                    'ban': ban,
                    'risk_score': latest_risk_score.current_score,
                    'unlock_reason': f'low_risk_score_{latest_risk_score.current_score}'
                })
        
        self.stdout.write(f"Found {len(users)} users with risk score <= {risk_threshold}")
        return users
    
    def _get_all_banned_users(self):
        """Get all banned users"""
        self.stdout.write("Getting all banned users...")
        
        banned_users = UserBan.objects.filter(
            is_active=True
        ).select_related('user')
        
        users = []
        for ban in banned_users:
            if ban.user.id not in self.exclude_ids:
                users.append({
                    'user': ban.user,
                    'ban': ban,
                    'unlock_reason': 'bulk_unlock_all'
                })
        
        self.stdout.write(f"Found {len(users)} banned users")
        return users
    
    def _filter_users_for_unlock(self, users):
        """Filter users that should be unlocked"""
        self.stdout.write("Filtering users for unlock...")
        
        filtered_users = []
        
        for user_data in users:
            user = user_data['user']
            
            # Skip inactive users unless requested
            if not self.options['include_inactive'] and not user.is_active:
                self.skipped_users.append({
                    'user_id': user.id,
                    'username': user.username,
                    'reason': 'user_inactive'
                })
                continue
            
            # Check for active security incidents unless force option is used
            if not self.options['force']:
                active_incidents = SecurityIncident.objects.filter(
                    user=user,
                    status__in=['open', 'investigating']
                ).count()
                
                if active_incidents > 0:
                    self.skipped_users.append({
                        'user_id': user.id,
                        'username': user.username,
                        'reason': f'active_incidents_{active_incidents}'
                    })
                    continue
            
            # Check for high recent risk score unless force option is used
            if not self.options['force']:
                recent_risk_score = RiskScore.objects.filter(
                    user=user,
                    created_at__gte=timezone.now() - timedelta(hours=24)
                ).order_by('-current_score').first()
                
                if recent_risk_score and recent_risk_score.current_score > 70:
                    self.skipped_users.append({
                        'user_id': user.id,
                        'username': user.username,
                        'reason': f'high_recent_risk_{recent_risk_score.current_score}'
                    })
                    continue
            
            filtered_users.append(user_data)
        
        self.stdout.write(f"Filtered to {len(filtered_users)} users for unlock")
        return filtered_users
    
    def _unlock_users(self, users):
        """Unlock the identified users"""
        self.stdout.write(f"Unlocking {len(users)} users...")
        
        if self.options['dry_run']:
            self.stdout.write("DRY RUN - Would unlock the following users:")
            for user_data in users:
                self.stdout.write(
                    f"  {user_data['user'].username} - Reason: {user_data['unlock_reason']}"
                )
            return
        
        batch_size = self.options['batch_size']
        
        for i in range(0, len(users), batch_size):
            batch = users[i:i + batch_size]
            
            with transaction.atomic():
                for user_data in batch:
                    try:
                        user = user_data['user']
                        ban = user_data['ban']
                        
                        # Deactivate the ban
                        if ban:
                            ban.is_active = False
                            ban.updated_at = timezone.now()
                            ban.save()
                        
                        # Reactivate user if inactive
                        if not user.is_active:
                            user.is_active = True
                            user.save()
                        
                        self.unlocked_users.append({
                            'user_id': user.id,
                            'username': user.username,
                            'email': user.email,
                            'unlock_reason': user_data['unlock_reason'],
                            'unlocked_at': timezone.now().isoformat(),
                            'ban_deactivated': ban is not None,
                            'user_reactivated': not user.is_active
                        })
                        
                    except Exception as e:
                        logger.error(f"Failed to unlock user {user_data['user'].username}: {str(e)}")
                        self.error_users.append({
                            'user_id': user_data['user'].id,
                            'username': user_data['user'].username,
                            'error': str(e)
                        })
            
            self.stdout.write(f"Processed batch {i//batch_size + 1}/{(len(users) + batch_size - 1)//batch_size}")
    
    def _reset_passwords(self):
        """Reset passwords for unlocked users"""
        self.stdout.write("Resetting passwords for unlocked users...")
        
        from django.contrib.auth.hashers import make_password
        import secrets
        import string
        
        passwords_reset = 0
        
        for user_data in self.unlocked_users:
            try:
                user = User.objects.get(id=user_data['user_id'])
                
                # Generate random password
                password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
                
                # Set new password
                user.password = make_password(password)
                user.save()
                
                # Store password for notification
                user_data['new_password'] = password
                passwords_reset += 1
                
            except Exception as e:
                logger.error(f"Failed to reset password for user {user_data['username']}: {str(e)}")
        
        self.stdout.write(f"Reset passwords for {passwords_reset} users")
    
    def _clear_sessions(self):
        """Clear all user sessions"""
        self.stdout.write("Clearing user sessions...")
        
        from django.contrib.sessions.models import Session
        from django.contrib.sessions.backends.db import SessionStore
        
        sessions_cleared = 0
        
        for user_data in self.unlocked_users:
            try:
                # Get all sessions for this user
                sessions = Session.objects.filter(
                    session_data__contains=f'"user_id": {user_data["user_id"]}'
                )
                
                # Delete sessions
                count = sessions.count()
                sessions.delete()
                sessions_cleared += count
                
            except Exception as e:
                logger.error(f"Failed to clear sessions for user {user_data['username']}: {str(e)}")
        
        self.stdout.write(f"Cleared {sessions_cleared} user sessions")
    
    def _send_user_notifications(self):
        """Send email notifications to unlocked users"""
        self.stdout.write("Sending user notifications...")
        
        notifications_sent = 0
        
        for user_data in self.unlocked_users:
            try:
                from django.core.mail import send_mail
                
                user = User.objects.get(id=user_data['user_id'])
                
                subject = "Your Account Has Been Unlocked"
                
                message = f"""
Dear {user.username},

Your account has been successfully unlocked.

Unlock Details:
- Unlock Reason: {user_data['unlock_reason']}
- Unlocked At: {user_data['unlocked_at']}
                
"""
                
                if 'new_password' in user_data:
                    message += f"- New Password: {user_data['new_password']}\n"
                    message += f"\nPlease change your password after logging in for security reasons.\n"
                
                message += f"""
If you did not request this unlock, please contact our support team immediately.

Best regards,
Security Team
                """.strip()
                
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False
                )
                
                notifications_sent += 1
                
            except Exception as e:
                logger.error(f"Failed to send notification to user {user_data['username']}: {str(e)}")
        
        self.stdout.write(f"Sent notifications to {notifications_sent} users")
    
    def _create_unlock_logs(self):
        """Create security logs for unlock operations"""
        self.stdout.write("Creating unlock logs...")
        
        logs_created = 0
        
        for user_data in self.unlocked_users:
            try:
                SecurityLog.objects.create(
                    user=User.objects.get(id=user_data['user_id']),
                    security_type='account_unlocked',
                    severity='info',
                    ip_address='127.0.0.1',  # System action
                    user_agent='Security Management Command',
                    metadata={
                        'unlock_reason': user_data['unlock_reason'],
                        'unlocked_at': user_data['unlocked_at'],
                        'command': 'unlock_user_accounts',
                        'options': self.options
                    }
                )
                
                logs_created += 1
                
            except Exception as e:
                logger.error(f"Failed to create log for user {user_data['username']}: {str(e)}")
        
        self.stdout.write(f"Created {logs_created} unlock logs")
    
    def _generate_summary(self):
        """Generate and display summary of unlock operation"""
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS("USER ACCOUNT UNLOCK SUMMARY"))
        self.stdout.write("="*80)
        
        # Configuration
        self.stdout.write("Configuration:")
        self.stdout.write(f"  Unlock Type: {self.options['unlock_type']}")
        self.stdout.write(f"  Risk Threshold: {self.options['risk_threshold']}")
        self.stdout.write(f"  Ban Age Hours: {self.options['ban_age_hours']}")
        self.stdout.write(f"  Dry Run: {self.options['dry_run']}")
        self.stdout.write(f"  Force: {self.options['force']}")
        self.stdout.write(f"  Reset Password: {self.options['reset_password']}")
        self.stdout.write(f"  Clear Sessions: {self.options['clear_sessions']}")
        self.stdout.write(f"  Notify Users: {self.options['notify_users']}")
        self.stdout.write(f"  Include Inactive: {self.options['include_inactive']}")
        
        # Results
        self.stdout.write(f"\nResults:")
        self.stdout.write(f"  Users Unlocked: {len(self.unlocked_users)}")
        self.stdout.write(f"  Users Skipped: {len(self.skipped_users)}")
        self.stdout.write(f"  Errors: {len(self.error_users)}")
        
        # Unlocked users details
        if self.unlocked_users:
            self.stdout.write(f"\nUnlocked Users:")
            for user in self.unlocked_users[:10]:
                self.stdout.write(
                    f"  {user['username']} ({user['email']}) - {user['unlock_reason']}"
                )
            if len(self.unlocked_users) > 10:
                self.stdout.write(f"  ... and {len(self.unlocked_users) - 10} more")
        
        # Skipped users details
        if self.skipped_users:
            self.stdout.write(f"\nSkipped Users:")
            for user in self.skipped_users[:5]:
                self.stdout.write(f"  {user['username']} - {user['reason']}")
            if len(self.skipped_users) > 5:
                self.stdout.write(f"  ... and {len(self.skipped_users) - 5} more")
        
        # Errors
        if self.error_users:
            self.stdout.write(f"\nErrors:")
            for user in self.error_users:
                self.stdout.write(f"  {user.get('username', user.get('user_id', 'Unknown'))}: {user['error']}")
        
        # Statistics
        if self.unlocked_users:
            # Group by unlock reason
            reason_counts = defaultdict(int)
            for user in self.unlocked_users:
                reason_counts[user['unlock_reason']] += 1
            
            self.stdout.write(f"\nUnlock Reasons:")
            for reason, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
                self.stdout.write(f"  {reason}: {count}")
            
            # Password resets
            if self.options['reset_password']:
                password_resets = len([u for u in self.unlocked_users if 'new_password' in u])
                self.stdout.write(f"\nPasswords Reset: {password_resets}")
        
        self.stdout.write("="*80)