import logging
from typing import Dict, List, Any, Optional, Tuple
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from ..models import (
    FraudAttempt, UserRiskProfile, FraudRule,
    FraudAlert, IPReputation
)
from api.users.models import User
from api.wallet.models import WalletTransaction
import json

logger = logging.getLogger(__name__)

class AutoBanService:
    """
    Automated banning and restriction service
    Handles automatic actions based on fraud detection
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.now = timezone.now()
        
        # Action thresholds
        self.thresholds = {
            'auto_ban': config.get('auto_ban_threshold', 90) if config else 90,
            'auto_suspend': config.get('auto_suspend_threshold', 80) if config else 80,
            'auto_restrict': config.get('auto_restrict_threshold', 70) if config else 70,
            'auto_flag': config.get('auto_flag_threshold', 60) if config else 60
        }
        
        # Ban durations (in hours)
        self.ban_durations = {
            'first_offense': config.get('first_ban_hours', 24) if config else 24,
            'repeat_offense': config.get('repeat_ban_hours', 168) if config else 168,  # 7 days
            'severe_offense': config.get('severe_ban_hours', 720) if config else 720  # 30 days
        }
        
        # Restriction levels
        self.restrictions = {
            'level_1': ['withdrawal', 'referral', 'offer_completion'],
            'level_2': ['withdrawal', 'referral'],
            'level_3': ['withdrawal']
        }
    
    def process_fraud_attempt(self, fraud_attempt: FraudAttempt) -> Dict:
        """
        Process a fraud attempt and take appropriate action
        """
        try:
            with transaction.atomic():
                user = fraud_attempt.user
                fraud_score = fraud_attempt.fraud_score
                
                # Get user's risk profile
                risk_profile, _ = UserRiskProfile.objects.get_or_create(user=user)
                
                # Calculate action based on score and history
                action_result = self._determine_action(user, fraud_score, fraud_attempt)
                
                # Execute action
                if action_result['action'] != 'no_action':
                    self._execute_action(user, action_result, fraud_attempt)
                
                # Update fraud attempt status
                fraud_attempt.status = 'reviewing' if action_result['action'] in ['flag', 'limit'] else 'detected'
                fraud_attempt.save()
                
                # Create alert if action was taken
                if action_result['action'] != 'no_action':
                    self._create_fraud_alert(user, fraud_attempt, action_result)
                
                # Update IP reputation
                if fraud_attempt.evidence_data.get('ip_address'):
                    self._update_ip_reputation(
                        fraud_attempt.evidence_data['ip_address'],
                        fraud_score
                    )
                
                logger.info(f"Processed fraud attempt {fraud_attempt.attempt_id}: "
                          f"action={action_result['action']}, score={fraud_score}")
                
                return action_result
                
        except Exception as e:
            logger.error(f"Error processing fraud attempt: {e}")
            return {
                'action': 'no_action',
                'error': str(e)
            }
    
    def process_bulk_fraud(self, fraud_attempts: List[FraudAttempt]) -> Dict:
        """
        Process multiple fraud attempts in bulk
        """
        results = {
            'total_processed': 0,
            'actions_taken': 0,
            'banned_users': 0,
            'suspended_users': 0,
            'restricted_users': 0,
            'detailed_results': []
        }
        
        for attempt in fraud_attempts:
            try:
                result = self.process_fraud_attempt(attempt)
                results['detailed_results'].append({
                    'attempt_id': str(attempt.attempt_id),
                    'user_id': attempt.user_id,
                    'action': result['action'],
                    'score': attempt.fraud_score
                })
                
                results['total_processed'] += 1
                
                if result['action'] != 'no_action':
                    results['actions_taken'] += 1
                
                if result['action'] == 'ban':
                    results['banned_users'] += 1
                elif result['action'] == 'suspend':
                    results['suspended_users'] += 1
                elif result['action'] == 'limit':
                    results['restricted_users'] += 1
                    
            except Exception as e:
                logger.error(f"Error processing bulk fraud attempt {attempt.attempt_id}: {e}")
                results['detailed_results'].append({
                    'attempt_id': str(attempt.attempt_id),
                    'error': str(e)
                })
        
        return results
    
    def auto_ban_user(self, user: User, reason: str, duration_hours: int = None) -> Dict:
        """
        Automatically ban a user
        """
        try:
            with transaction.atomic():
                if duration_hours is None:
                    # Determine duration based on history
                    duration_hours = self._determine_ban_duration(user)
                
                ban_until = self.now + timedelta(hours=duration_hours)
                
                # Update user status
                user.is_active = False
                user.banned_until = ban_until
                user.ban_reason = reason
                user.save()
                
                # Update risk profile
                risk_profile, _ = UserRiskProfile.objects.get_or_create(user=user)
                risk_profile.is_restricted = True
                risk_profile.restrictions = {
                    'banned': True,
                    'banned_until': ban_until.isoformat(),
                    'reason': reason
                }
                risk_profile.save()
                
                # Cancel pending transactions
                self._cancel_pending_transactions(user)
                
                # Create audit log
                self._create_ban_audit_log(user, reason, duration_hours)
                
                logger.warning(f"Auto-banned user {user.id}: {reason} (until {ban_until})")
                
                return {
                    'success': True,
                    'action': 'ban',
                    'user_id': user.id,
                    'duration_hours': duration_hours,
                    'banned_until': ban_until.isoformat(),
                    'reason': reason
                }
                
        except Exception as e:
            logger.error(f"Error auto-banning user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def auto_suspend_user(self, user: User, reason: str, duration_hours: int = 24) -> Dict:
        """
        Automatically suspend a user (temporary restriction)
        """
        try:
            with transaction.atomic():
                suspend_until = self.now + timedelta(hours=duration_hours)
                
                # Update user
                user.is_suspended = True
                user.suspended_until = suspend_until
                user.suspension_reason = reason
                user.save()
                
                # Update risk profile
                risk_profile, _ = UserRiskProfile.objects.get_or_create(user=user)
                risk_profile.is_restricted = True
                risk_profile.restrictions = {
                    'suspended': True,
                    'suspended_until': suspend_until.isoformat(),
                    'reason': reason,
                    'restricted_actions': self.restrictions['level_1']
                }
                risk_profile.save()
                
                logger.warning(f"Auto-suspended user {user.id}: {reason} (until {suspend_until})")
                
                return {
                    'success': True,
                    'action': 'suspend',
                    'user_id': user.id,
                    'duration_hours': duration_hours,
                    'suspended_until': suspend_until.isoformat(),
                    'reason': reason
                }
                
        except Exception as e:
            logger.error(f"Error auto-suspending user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def auto_restrict_user(self, user: User, reason: str, restriction_level: str = 'level_1') -> Dict:
        """
        Automatically restrict user actions
        """
        try:
            with transaction.atomic():
                restrictions = self.restrictions.get(restriction_level, [])
                
                # Update risk profile
                risk_profile, _ = UserRiskProfile.objects.get_or_create(user=user)
                risk_profile.is_restricted = True
                risk_profile.restrictions = {
                    'restricted_actions': restrictions,
                    'restriction_level': restriction_level,
                    'reason': reason,
                    'restricted_since': self.now.isoformat()
                }
                risk_profile.save()
                
                logger.warning(f"Auto-restricted user {user.id}: {reason} (level: {restriction_level})")
                
                return {
                    'success': True,
                    'action': 'restrict',
                    'user_id': user.id,
                    'restriction_level': restriction_level,
                    'restricted_actions': restrictions,
                    'reason': reason
                }
                
        except Exception as e:
            logger.error(f"Error auto-restricting user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def auto_flag_user(self, user: User, reason: str) -> Dict:
        """
        Automatically flag user for review
        """
        try:
            with transaction.atomic():
                # Update risk profile
                risk_profile, _ = UserRiskProfile.objects.get_or_create(user=user)
                risk_profile.is_flagged = True
                risk_profile.warning_flags.append('auto_flagged')
                risk_profile.save()
                
                # Create review task
                self._create_review_task(user, reason)
                
                logger.info(f"Auto-flagged user {user.id} for review: {reason}")
                
                return {
                    'success': True,
                    'action': 'flag',
                    'user_id': user.id,
                    'reason': reason
                }
                
        except Exception as e:
            logger.error(f"Error auto-flagging user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def check_and_unban_users(self) -> Dict:
        """
        Check for expired bans and unban users
        """
        try:
            users_to_unban = User.objects.filter(
                is_active=False,
                banned_until__isnull=False,
                banned_until__lte=self.now
            )
            
            results = {
                'checked': users_to_unban.count(),
                'unbanned': 0,
                'failed': 0,
                'details': []
            }
            
            for user in users_to_unban:
                try:
                    with transaction.atomic():
                        # Unban user
                        user.is_active = True
                        user.banned_until = None
                        user.ban_reason = None
                        user.save()
                        
                        # Update risk profile
                        risk_profile, _ = UserRiskProfile.objects.get_or_create(user=user)
                        risk_profile.is_restricted = False
                        risk_profile.restrictions = {}
                        risk_profile.save()
                        
                        # Create audit log
                        self._create_unban_audit_log(user)
                        
                        results['unbanned'] += 1
                        results['details'].append({
                            'user_id': user.id,
                            'action': 'unbanned',
                            'timestamp': self.now.isoformat()
                        })
                        
                        logger.info(f"Auto-unbanned user {user.id}")
                        
                except Exception as e:
                    logger.error(f"Error unbanning user {user.id}: {e}")
                    results['failed'] += 1
                    results['details'].append({
                        'user_id': user.id,
                        'action': 'failed',
                        'error': str(e)
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error checking and unbanning users: {e}")
            return {
                'checked': 0,
                'unbanned': 0,
                'failed': 0,
                'error': str(e)
            }
    
    def _determine_action(self, user: User, fraud_score: int, fraud_attempt: FraudAttempt) -> Dict:
        """
        Determine appropriate action based on fraud score and history
        """
        # Get user's fraud history
        fraud_history = FraudAttempt.objects.filter(user=user)
        total_attempts = fraud_history.count()
        confirmed_attempts = fraud_history.filter(status='confirmed').count()
        
        # Get risk profile
        risk_profile, _ = UserRiskProfile.objects.get_or_create(user=user)
        
        # Determine action based on score
        if fraud_score >= self.thresholds['auto_ban']:
            return {
                'action': 'ban',
                'reason': f'Critical fraud score: {fraud_score}',
                'severity': 'critical',
                'duration_hours': self._determine_ban_duration(user)
            }
        
        elif fraud_score >= self.thresholds['auto_suspend']:
            return {
                'action': 'suspend',
                'reason': f'High fraud score: {fraud_score}',
                'severity': 'high',
                'duration_hours': 24
            }
        
        elif fraud_score >= self.thresholds['auto_restrict']:
            restriction_level = 'level_2' if total_attempts > 1 else 'level_1'
            return {
                'action': 'limit',
                'reason': f'Medium fraud score: {fraud_score}',
                'severity': 'medium',
                'restriction_level': restriction_level
            }
        
        elif fraud_score >= self.thresholds['auto_flag']:
            return {
                'action': 'flag',
                'reason': f'Elevated fraud score: {fraud_score}',
                'severity': 'elevated'
            }
        
        # Check for repeated offenses
        if total_attempts >= 3:
            return {
                'action': 'suspend',
                'reason': f'Multiple fraud attempts: {total_attempts}',
                'severity': 'high',
                'duration_hours': self.ban_durations['repeat_offense']
            }
        
        # Check for confirmed fraud
        if confirmed_attempts >= 1:
            return {
                'action': 'ban',
                'reason': f'Confirmed fraud attempt',
                'severity': 'critical',
                'duration_hours': self.ban_durations['severe_offense']
            }
        
        # Check risk profile
        if risk_profile.overall_risk_score >= 80:
            return {
                'action': 'flag',
                'reason': f'High risk profile score: {risk_profile.overall_risk_score}',
                'severity': 'high'
            }
        
        # Check fraud attempt type
        attempt_type = fraud_attempt.attempt_type
        if attempt_type in ['multi_account', 'payment_fraud', 'device_spoofing']:
            return {
                'action': 'limit',
                'reason': f'High-risk fraud type: {attempt_type}',
                'severity': 'medium',
                'restriction_level': 'level_1'
            }
        
        return {
            'action': 'no_action',
            'reason': 'Below action thresholds',
            'severity': 'low'
        }
    
    def _execute_action(self, user: User, action_result: Dict, fraud_attempt: FraudAttempt):
        """
        Execute the determined action
        """
        action = action_result['action']
        reason = action_result['reason']
        
        if action == 'ban':
            duration = action_result.get('duration_hours', 24)
            self.auto_ban_user(user, reason, duration)
            
        elif action == 'suspend':
            duration = action_result.get('duration_hours', 24)
            self.auto_suspend_user(user, reason, duration)
            
        elif action == 'limit':
            restriction_level = action_result.get('restriction_level', 'level_1')
            self.auto_restrict_user(user, reason, restriction_level)
            
        elif action == 'flag':
            self.auto_flag_user(user, reason)
    
    def _determine_ban_duration(self, user: User) -> int:
        """
        Determine ban duration based on user history
        """
        fraud_history = FraudAttempt.objects.filter(user=user)
        total_attempts = fraud_history.count()
        
        if total_attempts == 0:
            return self.ban_durations['first_offense']
        elif total_attempts <= 2:
            return self.ban_durations['repeat_offense']
        else:
            return self.ban_durations['severe_offense']
    
    def _create_fraud_alert(self, user: User, fraud_attempt: FraudAttempt, action_result: Dict):
        """
        Create fraud alert for admin
        """
        try:
            FraudAlert.objects.create(
                alert_type='rule_triggered',
                priority='high' if action_result['severity'] in ['high', 'critical'] else 'medium',
                title=f"Auto-action taken: {action_result['action'].upper()}",
                description=f"User {user.username} ({user.id}) - {action_result['reason']}",
                user=user,
                fraud_attempt=fraud_attempt,
                data={
                    'action_taken': action_result['action'],
                    'fraud_score': fraud_attempt.fraud_score,
                    'attempt_type': fraud_attempt.attempt_type,
                    'action_details': action_result
                }
            )
        except Exception as e:
            logger.error(f"Error creating fraud alert: {e}")
    
    def _update_ip_reputation(self, ip_address: str, fraud_score: int):
        """
        Update IP reputation based on fraud attempt
        """
        try:
            ip_reputation, created = IPReputation.objects.get_or_create(ip_address=ip_address)
            
            # Update fraud score (weighted average)
            current_score = ip_reputation.fraud_score
            attempt_count = ip_reputation.fraud_attempts
            
            if attempt_count == 0:
                new_score = fraud_score
            else:
                # Weighted average giving more weight to recent attempts
                new_score = int((current_score * attempt_count + fraud_score) / (attempt_count + 1))
            
            ip_reputation.fraud_score = min(100, new_score)
            ip_reputation.fraud_attempts += 1
            ip_reputation.total_requests += 1
            
            # Blacklist if score is very high
            if ip_reputation.fraud_score >= 90 and not ip_reputation.is_blacklisted:
                ip_reputation.is_blacklisted = True
                ip_reputation.blacklist_reason = f'Auto-blacklisted due to fraud score: {ip_reputation.fraud_score}'
                ip_reputation.blacklisted_at = self.now
            
            ip_reputation.save()
            
        except Exception as e:
            logger.error(f"Error updating IP reputation: {e}")
    
    def _cancel_pending_transactions(self, user: User):
        """
        Cancel user's pending transactions when banned
        """
        try:
            pending_transactions = WalletTransaction.objects.filter(
                user=user,
                status__in=['pending', 'processing']
            )
            
            for transaction in pending_transactions:
                transaction.status = 'cancelled'
                transaction.cancellation_reason = 'User banned'
                transaction.save()
                
        except Exception as e:
            logger.error(f"Error cancelling pending transactions: {e}")
    
    def _create_ban_audit_log(self, user: User, reason: str, duration_hours: int):
        """
        Create audit log for ban action
        """
        try:
            from audit_logs.models import AuditLog
            
            AuditLog.objects.create(
                user=user,
                action='AUTO_BAN',
                description=f"Auto-banned for {duration_hours} hours: {reason}",
                metadata={
                    'ban_duration_hours': duration_hours,
                    'ban_reason': reason,
                    'banned_until': (self.now + timedelta(hours=duration_hours)).isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Error creating ban audit log: {e}")
    
    def _create_unban_audit_log(self, user: User):
        """
        Create audit log for unban action
        """
        try:
            from audit_logs.models import AuditLog
            
            AuditLog.objects.create(
                user=user,
                action='AUTO_UNBAN',
                description="Auto-unbanned after ban expiration",
                metadata={
                    'unbanned_at': self.now.isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Error creating unban audit log: {e}")
    
    def _create_review_task(self, user: User, reason: str):
        """
        Create review task for flagged users
        """
        try:
            # In production, this would create a task in your task queue
            # For now, just log it
            logger.info(f"Review task created for user {user.id}: {reason}")
        except Exception as e:
            logger.error(f"Error creating review task: {e}")
    
    def get_auto_ban_stats(self, days: int = 7) -> Dict:
        """
        Get auto-ban statistics
        """
        try:
            start_date = self.now - timedelta(days=days)
            
            # Get banned users
            banned_users = User.objects.filter(
                is_active=False,
                banned_until__isnull=False,
                banned_until__gte=start_date
            ).count()
            
            # Get suspended users
            suspended_users = User.objects.filter(
                is_suspended=True,
                suspended_until__isnull=False,
                suspended_until__gte=start_date
            ).count()
            
            # Get restricted users
            restricted_users = UserRiskProfile.objects.filter(
                is_restricted=True,
                updated_at__gte=start_date
            ).count()
            
            # Get fraud attempts
            fraud_attempts = FraudAttempt.objects.filter(
                created_at__gte=start_date
            ).count()
            
            # Get auto-actions
            auto_actions = FraudAlert.objects.filter(
                created_at__gte=start_date,
                alert_type='rule_triggered',
                title__icontains='Auto-action'
            ).count()
            
            return {
                'period_days': days,
                'start_date': start_date.isoformat(),
                'end_date': self.now.isoformat(),
                'banned_users': banned_users,
                'suspended_users': suspended_users,
                'restricted_users': restricted_users,
                'fraud_attempts': fraud_attempts,
                'auto_actions': auto_actions,
                'action_rate': (auto_actions / fraud_attempts * 100) if fraud_attempts > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting auto-ban stats: {e}")
            return {
                'error': str(e)
            }
    
    def validate_config(self) -> Dict:
        """
        Validate auto-ban configuration
        """
        validation_results = {
            'thresholds_valid': True,
            'durations_valid': True,
            'restrictions_valid': True,
            'warnings': [],
            'errors': []
        }
        
        # Validate thresholds
        thresholds = list(self.thresholds.values())
        if not all(0 <= t <= 100 for t in thresholds):
            validation_results['thresholds_valid'] = False
            validation_results['errors'].append('Thresholds must be between 0 and 100')
        
        if thresholds != sorted(thresholds):
            validation_results['thresholds_valid'] = False
            validation_results['errors'].append('Thresholds must be in ascending order')
        
        # Validate durations
        durations = list(self.ban_durations.values())
        if not all(d > 0 for d in durations):
            validation_results['durations_valid'] = False
            validation_results['errors'].append('Ban durations must be positive')
        
        if durations != sorted(durations):
            validation_results['durations_valid'] = False
            validation_results['errors'].append('Ban durations must be in ascending order')
        
        # Validate restrictions
        for level, actions in self.restrictions.items():
            if not isinstance(actions, list):
                validation_results['restrictions_valid'] = False
                validation_results['errors'].append(f'Restrictions for {level} must be a list')
        
        # Check for configuration warnings
        if self.thresholds['auto_ban'] < 85:
            validation_results['warnings'].append('Auto-ban threshold is relatively low')
        
        if self.ban_durations['severe_offense'] > 744:  # More than 31 days
            validation_results['warnings'].append('Severe offense ban duration is very long')
        
        return validation_results