"""
PART 10: Proof Submission Fraud Gate

Integrates fraud detection directly into proof submission workflow.

Design Pattern:
✓ Run fraud checks BEFORE accepting proof
✓ Block submissions with fraud_score > 75
✓ Flag submissions 40-75 for manual review
✓ Auto-verify submissions < 40 (immediate payout)

Integration points:
• View: proof_submission_view.py
• Serializer: ProofSubmissionSerializer
• Signal: post_save(ProofSubmission) trigger async verification

This module handles:
1. Fraud check execution (parallel checks)
2. Score aggregation
3. Action decision (BLOCK/REVIEW/APPROVE)
4. FraudSignal persistence for appeal tracking
"""

import logging
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
from django.utils import timezone
from django.db import transaction

from .models import (
    ProofSubmission, TaskEventLog, UserTaskCompletion,
    FraudSignal  # Model to be created in Part 10B
)

logger = logging.getLogger(__name__)


class FraudGateService:
    """
    Real-time fraud detection gate for task proof submissions.
    
    Usage:
        service = FraudGateService()
        fraud_result = service.evaluate_proof_submission(
            user_id=123,
            task_id=456,
            proof_data={'survey_id': 'XYZ'},
            ip_address='192.168.1.1'
        )
        
        if fraud_result['action'] == 'BLOCK':
            return Response({'error': fraud_result['reason']}, status=403)
        elif fraud_result['action'] == 'REVIEW':
            proof_submission.manual_review_required = True
            proof_submission.save()
    """
    
    # Fraud Score Thresholds
    THRESHOLD_BLOCK_SUBMISSION = 75  # Score > 75: Block submission
    THRESHOLD_MANUAL_REVIEW = 40    # Score > 40: Flag for manual review
    
    def __init__(self):
        """Initialize fraud gate service"""
        self.fraud_checks = [
            self._check_high_velocity,
            self._check_reward_anomaly,
            self._check_ip_reuse,
            self._check_device_fingerprint,
            self._check_proof_anomaly,
            self._check_provider_verification,
        ]
    
    # =========================================================================
    # MAIN ENTRY POINT
    # =========================================================================
    
    def evaluate_proof_submission(
        self,
        user_id: int,
        task_id: int,
        proof_data: Dict,
        ip_address: str,
        user_agent: str = ''
    ) -> Dict:
        """
        Evaluate proof submission against all fraud checks.
        
        Args:
            user_id: User submitting proof
            task_id: Task being completed
            proof_data: Proof submission data (survey responses, etc)
            ip_address: Source IP address
            user_agent: Browser user agent string
        
        Returns:
            {
                'action': 'BLOCK' | 'REVIEW' | 'APPROVE',
                'fraud_score': int (0-100),
                'reason': str,
                'signals': [list of FraudSignal reasons],
                'evidence': {detailed_check_results}
            }
        """
        try:
            signals = []
            evidence = {}
            
            # Run all fraud checks in parallel
            for check_func in self.fraud_checks:
                result = check_func(user_id, task_id, proof_data, ip_address, user_agent)
                if result['triggered']:
                    signals.extend(result['signals'])
                    evidence[check_func.__name__] = result
            
            # Aggregate score
            fraud_score = sum([s['score'] for s in signals])
            fraud_score = min(fraud_score, 100)  # Cap at 100
            
            # Determine action
            if fraud_score > self.THRESHOLD_BLOCK_SUBMISSION:
                action = 'BLOCK'
                reason = f"Fraud score {fraud_score}/100 exceeds safety threshold"
            elif fraud_score > self.THRESHOLD_MANUAL_REVIEW:
                action = 'REVIEW'
                reason = f"Suspicious activity detected (score: {fraud_score}/100)"
            else:
                action = 'APPROVE'
                reason = "Passed fraud checks"
            
            return {
                'action': action,
                'fraud_score': fraud_score,
                'reason': reason,
                'signals': signals,
                'evidence': evidence
            }
        
        except Exception as e:
            logger.error(f"Error in fraud gate evaluation: {str(e)}", exc_info=True)
            # FAIL OPEN: If fraud check system errors, approve submission
            # (don't block legitimate users due to our bug)
            return {
                'action': 'APPROVE',
                'fraud_score': 0,
                'reason': f"Fraud check error (safe mode): {str(e)}",
                'signals': [],
                'evidence': {}
            }
    
    # =========================================================================
    # FRAUD CHECK IMPLEMENTATIONS
    # =========================================================================
    
    def _check_high_velocity(self, user_id, task_id, proof_data, ip_address, user_agent) -> Dict:
        """
        Check: User completed >20 tasks in last hour (superhuman pace).
        Indicates bot or farm account.
        """
        try:
            from django.db.models import Count
            from datetime import timedelta
            
            # Count completions in last hour
            hour_ago = timezone.now() - timedelta(hours=1)
            completion_count = UserTaskCompletion.objects.filter(
                user_id=user_id,
                status='completed',
                completed_at__gte=hour_ago
            ).count()
            
            if completion_count > 20:
                return {
                    'triggered': True,
                    'signals': [
                        {
                            'signal_type': 'HIGH_VELOCITY',
                            'score': 40,
                            'reason': f'User completed {completion_count} tasks in last hour'
                        }
                    ]
                }
            
            return {'triggered': False, 'signals': []}
        
        except Exception as e:
            logger.error(f"Error in high velocity check: {e}")
            return {'triggered': False, 'signals': []}
    
    def _check_reward_anomaly(self, user_id, task_id, proof_data, ip_address, user_agent) -> Dict:
        """
        Check: Payout is >5x platform average (unusually high reward).
        Indicates potential scam or arbitrage exploitation.
        """
        try:
            from .models import MasterTask
            from django.db.models import Avg
            
            # Get task reward
            task = MasterTask.objects.get(id=task_id)
            task_reward = task.get_reward_value('points', 0)
            
            # Get platform average
            avg_reward = MasterTask.objects.aggregate(
                avg_points=Avg('rewards__points')
            )['avg_points'] or 100
            
            if task_reward > (avg_reward * 5):
                return {
                    'triggered': True,
                    'signals': [
                        {
                            'signal_type': 'REWARD_ANOMALY',
                            'score': 30,
                            'reason': f'Reward {task_reward} is {task_reward/avg_reward:.1f}x average'
                        }
                    ]
                }
            
            return {'triggered': False, 'signals': []}
        
        except Exception as e:
            logger.error(f"Error in reward anomaly check: {e}")
            return {'triggered': False, 'signals': []}
    
    def _check_ip_reuse(self, user_id, task_id, proof_data, ip_address, user_agent) -> Dict:
        """
        Check: Same IP address used by multiple accounts in last 3 days.
        Indicates bot farm or shared device abuse.
        """
        try:
            from datetime import timedelta
            from django.db.models import Count
            
            three_days_ago = timezone.now() - timedelta(days=3)
            
            # Find other users with same IP in last 3 days
            other_users = UserTaskCompletion.objects.filter(
                ip_address=ip_address,
                completed_at__gte=three_days_ago
            ).values('user_id').distinct().count()
            
            if other_users > 5:
                return {
                    'triggered': True,
                    'signals': [
                        {
                            'signal_type': 'IP_REUSE',
                            'score': 35,
                            'reason': f'IP used by {other_users} different accounts in 3 days'
                        }
                    ]
                }
            
            return {'triggered': False, 'signals': []}
        
        except Exception as e:
            logger.error(f"Error in IP reuse check: {e}")
            return {'triggered': False, 'signals': []}
    
    def _check_device_fingerprint(self, user_id, task_id, proof_data, ip_address, user_agent) -> Dict:
        """
        Check: Device fingerprint anomalies.
        Detects if user agent/device changes unexpectedly.
        """
        try:
            # Get user's recent device fingerprints
            recent_completions = UserTaskCompletion.objects.filter(
                user_id=user_id
            ).order_by('-completed_at')[:5]
            
            user_agents = [c.user_agent for c in recent_completions]
            
            # If user agent completely changes, flag it
            if user_agents and user_agent and user_agent not in user_agents:
                return {
                    'triggered': True,
                    'signals': [
                        {
                            'signal_type': 'DEVICE_FINGERPRINT_CHANGE',
                            'score': 20,
                            'reason': 'Device/browser changed unexpectedly'
                        }
                    ]
                }
            
            return {'triggered': False, 'signals': []}
        
        except Exception as e:
            logger.error(f"Error in device fingerprint check: {e}")
            return {'triggered': False, 'signals': []}
    
    def _check_proof_anomaly(self, user_id, task_id, proof_data, ip_address, user_agent) -> Dict:
        """
        Check: Proof submission time anomalies.
        Examples:
        - Survey completed in 10% of expected time (too fast = bot)
        - Multiple identical submissions (copy/paste)
        - Missing required fields
        """
        signals = []
        
        try:
            # Example: Survey completion time check
            if 'time_seconds' in proof_data and 'survey_expected_duration' in proof_data:
                actual_time = proof_data['time_seconds']
                expected_time = proof_data['survey_expected_duration']
                completion_ratio = actual_time / expected_time if expected_time else 1
                
                if completion_ratio < 0.3:  # Less than 30% of expected time
                    signals.append({
                        'signal_type': 'PROOF_TIME_ANOMALY',
                        'score': 50,
                        'reason': f'Survey completed in {completion_ratio*100:.0f}% of expected time'
                    })
            
            if signals:
                return {'triggered': True, 'signals': signals}
            
            return {'triggered': False, 'signals': []}
        
        except Exception as e:
            logger.error(f"Error in proof anomaly check: {e}")
            return {'triggered': False, 'signals': []}
    
    def _check_provider_verification(self, user_id, task_id, proof_data, ip_address, user_agent) -> Dict:
        """
        Check: External provider verification (for surveys, offers, etc).
        Calls provider API to verify submission actually occurred.
        """
        try:
            # This is a placeholder - actual implementation depends on provider
            # Examples: Cint API, Dynata API, Pollfish API
            
            # For now, return no signals (implement provider-specific logic)
            return {'triggered': False, 'signals': []}
        
        except Exception as e:
            logger.error(f"Error in provider verification check: {e}")
            # Don't block if provider check fails (fail open)
            return {'triggered': False, 'signals': []}
    
    # =========================================================================
    # SIGNAL PERSISTENCE
    # =========================================================================
    
    @transaction.atomic
    def persist_fraud_signals(
        self,
        user_id: int,
        fraud_result: Dict
    ):
        """
        Persist fraud signals in database for audit trail and appeals.
        
        Called after fraud gate decision to maintain record of why decision was made.
        """
        try:
            for signal in fraud_result['signals']:
                FraudSignal.objects.create(
                    user_id=user_id,
                    signal_type=signal['signal_type'],
                    score_contribution=signal['score'],
                    reason=signal['reason']
                )
        
        except Exception as e:
            logger.error(f"Error persisting fraud signals: {e}")
            # Don't fail if signal persistence fails


# =========================================================================
# PROOF SUBMISSION VIEW INTEGRATION
# =========================================================================

def handle_proof_submission_with_fraud_gate(
    user_id: int,
    task_id: int,
    proof_data: Dict,
    ip_address: str,
    user_agent: str = ''
) -> Tuple[bool, Optional[str], Optional[ProofSubmission]]:
    """
    Integrated proof submission handler with fraud gate.
    
    Usage in view:
        success, error_msg, proof = handle_proof_submission_with_fraud_gate(
            user_id=request.user.id,
            task_id=request.data['task_id'],
            proof_data=request.data['proof'],
            ip_address=request.META['REMOTE_ADDR']
        )
        
        if not success:
            return Response({'error': error_msg}, status=403)
        
        return Response({
            'proof_id': proof.id,
            'status': proof.verification_status,
            'message': 'Proof submitted successfully'
        })
    
    Returns:
        (success: bool, error_msg: Optional[str], proof: ProofSubmission)
    """
    try:
        from .models import UserTaskCompletion, ProofSubmission
        from .services_lock import TaskLockService
        
        # Step 1: Verify user owns task lock
        lock_service = TaskLockService()
        is_owner, lock, ownership_error = lock_service.verify_ownership(user_id, task_id)
        
        if not is_owner:
            return False, ownership_error, None
        
        # Step 2: Run fraud gate
        fraud_service = FraudGateService()
        fraud_result = fraud_service.evaluate_proof_submission(
            user_id=user_id,
            task_id=task_id,
            proof_data=proof_data,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        # Step 3: Create ProofSubmission based on fraud result
        completion = UserTaskCompletion.objects.get(user_id=user_id, task_id=task_id)
        
        if fraud_result['action'] == 'BLOCK':
            # High fraud score - reject immediately
            proof = ProofSubmission.objects.create(
                user_task_completion=completion,
                task_id=task_id,
                user_id=user_id,
                proof_data=proof_data,
                verification_status=ProofSubmission.VerificationStatus.REJECTED,
                rejected_reason=fraud_result['reason']
            )
            
            # Log the rejection
            TaskEventLog.objects.create(
                event_type=TaskEventLog.EventType.PROOF_REJECTED_FRAUD,
                task_id=task_id,
                user_id=user_id,
                actor_type=TaskEventLog.ActorType.FRAUD_ENGINE,
                event_data={
                    'fraud_score': fraud_result['fraud_score'],
                    'reason': fraud_result['reason'],
                    'signals': [s['signal_type'] for s in fraud_result['signals']]
                }
            )
            
            # Persist signals for audit trail
            fraud_service.persist_fraud_signals(user_id, fraud_result)
            
            # Release lock
            lock_service.release_lock(lock, reason='fraud_rejected')
            
            return False, fraud_result['reason'], proof
        
        elif fraud_result['action'] == 'REVIEW':
            # Medium fraud score - flag for manual review
            proof = ProofSubmission.objects.create(
                user_task_completion=completion,
                task_id=task_id,
                user_id=user_id,
                proof_data=proof_data,
                verification_status=ProofSubmission.VerificationStatus.FLAGGED,
                manual_review_required=True
            )
            
            # Log the flag
            TaskEventLog.objects.create(
                event_type=TaskEventLog.EventType.FRAUD_CHECK_TRIGGERED,
                task_id=task_id,
                user_id=user_id,
                actor_type=TaskEventLog.ActorType.FRAUD_ENGINE,
                event_data={
                    'fraud_score': fraud_result['fraud_score'],
                    'signals': [s['signal_type'] for s in fraud_result['signals']]
                }
            )
            
            # Persist signals
            fraud_service.persist_fraud_signals(user_id, fraud_result)
            
            return True, None, proof
        
        else:  # APPROVE
            # Low fraud score - auto-verify
            proof = ProofSubmission.objects.create(
                user_task_completion=completion,
                task_id=task_id,
                user_id=user_id,
                proof_data=proof_data,
                verification_status=ProofSubmission.VerificationStatus.VERIFIED,
                verified_at=timezone.now()
            )
            
            # Log verification
            TaskEventLog.objects.create(
                event_type=TaskEventLog.EventType.PROOF_VERIFIED,
                task_id=task_id,
                user_id=user_id,
                actor_type=TaskEventLog.ActorType.FRAUD_ENGINE,
                event_data={
                    'fraud_score': fraud_result['fraud_score'],
                    'reason': 'Auto-verified (low fraud risk)'
                }
            )
            
            # TODO: Award rewards here or in async task
            # award_task_rewards(completion)
            
            # Release lock
            lock_service.release_lock(lock, reason='normal_completion')
            
            return True, None, proof
    
    except Exception as e:
        logger.error(f"Error in proof submission handler: {str(e)}", exc_info=True)
        return False, "System error processing proof (please retry)", None
