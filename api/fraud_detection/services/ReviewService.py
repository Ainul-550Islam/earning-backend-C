import logging
from typing import Dict, List, Any, Optional, Tuple
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from ..models import (
    FraudAttempt, FraudAlert, UserRiskProfile,
    FraudRule, DeviceFingerprint, IPReputation
)
from api.users.models import User
from api.wallet.models import WalletTransaction
import json

logger = logging.getLogger(__name__)

class ReviewService:
    """
    Manual review service for fraud cases
    Provides tools for human review and decision making
    """
    
    def __init__(self):
        self.now = timezone.now()
        
    def get_pending_reviews(self, filters: Dict = None) -> List[Dict]:
        """
        Get pending fraud cases for review
        """
        try:
            query_filters = {
                'status': 'reviewing'
            }
            
            if filters:
                # Apply additional filters
                if filters.get('min_score'):
                    query_filters['fraud_score__gte'] = filters['min_score']
                
                if filters.get('max_score'):
                    query_filters['fraud_score__lte'] = filters['max_score']
                
                if filters.get('fraud_type'):
                    query_filters['attempt_type'] = filters['fraud_type']
                
                if filters.get('date_from'):
                    query_filters['created_at__gte'] = filters['date_from']
                
                if filters.get('date_to'):
                    query_filters['created_at__lte'] = filters['date_to']
            
            # Get fraud attempts pending review
            pending_attempts = FraudAttempt.objects.filter(
                **query_filters
            ).order_by(
                '-fraud_score', '-created_at'
            ).select_related('user')
            
            reviews = []
            for attempt in pending_attempts:
                review_data = self._prepare_review_data(attempt)
                reviews.append(review_data)
            
            return reviews
            
        except Exception as e:
            logger.error(f"Error getting pending reviews: {e}")
            return []
    
    def get_review_case(self, attempt_id: str) -> Dict:
        """
        Get detailed review case data
        """
        try:
            attempt = FraudAttempt.objects.select_related('user').get(attempt_id=attempt_id)
            
            # Prepare comprehensive review data
            review_data = self._prepare_review_data(attempt, detailed=True)
            
            # Add user's historical data
            review_data['user_history'] = self._get_user_history(attempt.user)
            
            # Add similar cases
            review_data['similar_cases'] = self._find_similar_cases(attempt)
            
            # Add risk analysis
            review_data['risk_analysis'] = self._analyze_case_risk(attempt)
            
            # Add recommendations
            review_data['recommendations'] = self._generate_recommendations(attempt)
            
            return review_data
            
        except FraudAttempt.DoesNotExist:
            logger.error(f"Fraud attempt not found: {attempt_id}")
            return {'error': 'Fraud attempt not found'}
        except Exception as e:
            logger.error(f"Error getting review case: {e}")
            return {'error': str(e)}
    
    def review_decision(self, attempt_id: str, decision: str, 
                       reviewer: User, notes: str = '', 
                       metadata: Dict = None) -> Dict:
        """
        Make a decision on a fraud case
        """
        try:
            with transaction.atomic():
                attempt = FraudAttempt.objects.get(attempt_id=attempt_id)
                user = attempt.user
                
                # Validate decision
                valid_decisions = ['confirmed', 'false_positive', 'resolved', 'escalate']
                if decision not in valid_decisions:
                    return {
                        'success': False,
                        'error': f'Invalid decision. Must be one of: {valid_decisions}'
                    }
                
                # Update fraud attempt
                attempt.status = decision
                attempt.resolved_at = self.now
                attempt.resolved_by = reviewer
                attempt.resolution_notes = notes
                
                if metadata:
                    attempt.metadata = {**attempt.metadata, **metadata}
                
                attempt.save()
                
                # Take action based on decision
                action_result = None
                if decision == 'confirmed':
                    action_result = self._handle_confirmed_fraud(user, attempt, reviewer, notes)
                elif decision == 'false_positive':
                    action_result = self._handle_false_positive(user, attempt, reviewer, notes)
                elif decision == 'escalate':
                    action_result = self._handle_escalation(user, attempt, reviewer, notes)
                
                # Create review log
                self._create_review_log(attempt, decision, reviewer, notes)
                
                # Update related alerts
                self._update_related_alerts(attempt, decision, reviewer)
                
                # Update user risk profile
                self._update_user_risk_profile(user, decision, attempt)
                
                logger.info(f"Review decision made: {attempt_id} -> {decision} by {reviewer.username}")
                
                return {
                    'success': True,
                    'decision': decision,
                    'attempt_id': attempt_id,
                    'user_id': user.id,
                    'action_taken': action_result,
                    'timestamp': self.now.isoformat()
                }
                
        except FraudAttempt.DoesNotExist:
            logger.error(f"Fraud attempt not found: {attempt_id}")
            return {'success': False, 'error': 'Fraud attempt not found'}
        except Exception as e:
            logger.error(f"Error making review decision: {e}")
            return {'success': False, 'error': str(e)}
    
    def batch_review_decisions(self, decisions: List[Dict], reviewer: User) -> Dict:
        """
        Process multiple review decisions in batch
        """
        results = {
            'total': len(decisions),
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'details': []
        }
        
        for decision_data in decisions:
            try:
                result = self.review_decision(
                    attempt_id=decision_data['attempt_id'],
                    decision=decision_data['decision'],
                    reviewer=reviewer,
                    notes=decision_data.get('notes', ''),
                    metadata=decision_data.get('metadata', {})
                )
                
                results['processed'] += 1
                
                if result['success']:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                
                results['details'].append({
                    'attempt_id': decision_data['attempt_id'],
                    'success': result['success'],
                    'decision': decision_data['decision'],
                    'error': result.get('error')
                })
                
            except Exception as e:
                logger.error(f"Error processing batch decision: {e}")
                results['failed'] += 1
                results['details'].append({
                    'attempt_id': decision_data.get('attempt_id', 'unknown'),
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def get_review_stats(self, reviewer: User = None, days: int = 30) -> Dict:
        """
        Get review statistics
        """
        try:
            start_date = self.now - timedelta(days=days)
            
            # Base query
            query = FraudAttempt.objects.filter(
                resolved_at__gte=start_date
            )
            
            if reviewer:
                query = query.filter(resolved_by=reviewer)
            
            # Get counts by decision
            decisions = query.values('status').annotate(
                count=Count('id'),
                avg_score=Avg('fraud_score'),
                avg_review_time=Avg('resolved_at' - 'created_at')
            )
            
            # Get total counts
            total_reviews = query.count()
            confirmed_fraud = query.filter(status='confirmed').count()
            false_positives = query.filter(status='false_positive').count()
            
            # Calculate metrics
            accuracy_rate = (confirmed_fraud / total_reviews * 100) if total_reviews > 0 else 0
            avg_review_duration = query.aggregate(
                avg_duration=Avg('resolved_at' - 'created_at')
            )['avg_duration']
            
            # Get reviewer stats if no specific reviewer
            if not reviewer:
                reviewer_stats = FraudAttempt.objects.filter(
                    resolved_at__gte=start_date,
                    resolved_by__isnull=False
                ).values(
                    'resolved_by__username'
                ).annotate(
                    total=Count('id'),
                    confirmed=Count('id', filter=Q(status='confirmed')),
                    false_positive=Count('id', filter=Q(status='false_positive'))
                ).order_by('-total')
            else:
                reviewer_stats = []
            
            return {
                'period_days': days,
                'total_reviews': total_reviews,
                'confirmed_fraud': confirmed_fraud,
                'false_positives': false_positives,
                'accuracy_rate': accuracy_rate,
                'average_review_duration': str(avg_review_duration) if avg_review_duration else None,
                'decision_breakdown': list(decisions),
                'reviewer_stats': list(reviewer_stats),
                'time_period': {
                    'start': start_date.isoformat(),
                    'end': self.now.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting review stats: {e}")
            return {'error': str(e)}
    
    def escalate_case(self, attempt_id: str, escalation_reason: str, 
                     escalated_by: User, priority: str = 'high') -> Dict:
        """
        Escalate a fraud case for higher review
        """
        try:
            with transaction.atomic():
                attempt = FraudAttempt.objects.get(attempt_id=attempt_id)
                
                # Update attempt status
                attempt.status = 'escalated'
                attempt.resolved_at = self.now
                attempt.resolved_by = escalated_by
                attempt.resolution_notes = f"ESCALATED: {escalation_reason}"
                attempt.save()
                
                # Create escalation alert
                FraudAlert.objects.create(
                    alert_type='manual_review',
                    priority=priority,
                    title=f"Case escalated: {attempt.attempt_type}",
                    description=f"Case {attempt_id} escalated by {escalated_by.username}: {escalation_reason}",
                    user=attempt.user,
                    fraud_attempt=attempt,
                    data={
                        'escalation_reason': escalation_reason,
                        'escalated_by': escalated_by.username,
                        'priority': priority,
                        'fraud_score': attempt.fraud_score
                    }
                )
                
                # Notify senior reviewers
                self._notify_senior_reviewers(attempt, escalation_reason, priority)
                
                logger.info(f"Case escalated: {attempt_id} by {escalated_by.username}")
                
                return {
                    'success': True,
                    'attempt_id': attempt_id,
                    'escalation_reason': escalation_reason,
                    'priority': priority,
                    'timestamp': self.now.isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error escalating case: {e}")
            return {'success': False, 'error': str(e)}
    
    def add_review_comment(self, attempt_id: str, comment: str, 
                          commenter: User, is_internal: bool = False) -> Dict:
        """
        Add comment to fraud case
        """
        try:
            attempt = FraudAttempt.objects.get(attempt_id=attempt_id)
            
            # Get existing comments
            comments = attempt.metadata.get('review_comments', [])
            
            # Add new comment
            new_comment = {
                'comment': comment,
                'commenter': commenter.username,
                'commenter_id': commenter.id,
                'is_internal': is_internal,
                'timestamp': self.now.isoformat()
            }
            
            comments.append(new_comment)
            
            # Update metadata
            attempt.metadata['review_comments'] = comments
            attempt.save()
            
            # Create comment alert if not internal
            if not is_internal:
                FraudAlert.objects.create(
                    alert_type='manual_review',
                    priority='medium',
                    title=f"Comment added to case {attempt_id}",
                    description=f"New comment by {commenter.username}",
                    user=attempt.user,
                    fraud_attempt=attempt,
                    data={
                        'comment_preview': comment[:100] + '...' if len(comment) > 100 else comment,
                        'commenter': commenter.username
                    }
                )
            
            return {
                'success': True,
                'attempt_id': attempt_id,
                'comment_id': len(comments) - 1,
                'timestamp': self.now.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error adding review comment: {e}")
            return {'success': False, 'error': str(e)}
    
    def _prepare_review_data(self, attempt: FraudAttempt, detailed: bool = False) -> Dict:
        """Prepare review case data"""
        review_data = {
            'attempt_id': str(attempt.attempt_id),
            'user_id': attempt.user_id,
            'username': attempt.user.username,
            'email': attempt.user.email,
            'fraud_type': attempt.attempt_type,
            'fraud_type_display': attempt.get_attempt_type_display(),
            'fraud_score': attempt.fraud_score,
            'confidence_score': attempt.confidence_score,
            'description': attempt.description,
            'detected_by': attempt.detected_by,
            'created_at': attempt.created_at.isoformat(),
            'status': attempt.status,
            'evidence_summary': self._summarize_evidence(attempt.evidence_data),
            'rules_triggered': list(attempt.fraud_rules.values_list('name', flat=True)),
            'amount_involved': float(attempt.amount_involved)
        }
        
        if detailed:
            # Add detailed evidence
            review_data['evidence_details'] = attempt.evidence_data
            review_data['metadata'] = attempt.metadata
            
            # Add user details
            review_data['user_details'] = {
                'date_joined': attempt.user.date_joined.isoformat(),
                'last_login': attempt.user.last_login.isoformat() if attempt.user.last_login else None,
                'is_verified': attempt.user.is_verified,
                'is_active': attempt.user.is_active
            }
            
            # Add device information if available
            if 'device_data' in attempt.evidence_data:
                review_data['device_info'] = attempt.evidence_data['device_data']
            
            # Add IP information
            if 'ip_address' in attempt.evidence_data:
                review_data['ip_info'] = self._get_ip_info(attempt.evidence_data['ip_address'])
        
        return review_data
    
    def _get_user_history(self, user: User) -> Dict:
        """Get user's fraud and transaction history"""
        try:
            # Fraud history
            fraud_history = FraudAttempt.objects.filter(user=user).order_by('-created_at')[:10]
            
            fraud_history_data = []
            for attempt in fraud_history:
                fraud_history_data.append({
                    'attempt_id': str(attempt.attempt_id),
                    'type': attempt.attempt_type,
                    'score': attempt.fraud_score,
                    'status': attempt.status,
                    'created_at': attempt.created_at.isoformat(),
                    'resolved_at': attempt.resolved_at.isoformat() if attempt.resolved_at else None
                })
            
            # Transaction history
            transaction_history = WalletTransaction.objects.filter(
                user=user
            ).order_by('-created_at')[:20]
            
            transaction_data = []
            for tx in transaction_history:
                transaction_data.append({
                    'id': tx.id,
                    'type': tx.transaction_type,
                    'amount': float(tx.amount),
                    'status': tx.status,
                    'description': tx.description,
                    'created_at': tx.created_at.isoformat()
                })
            
            # Device history
            device_history = DeviceFingerprint.objects.filter(
                user=user
            ).order_by('-last_seen')[:5]
            
            device_data = []
            for device in device_history:
                device_data.append({
                    'device_id': device.device_id[:20] + '...',
                    'trust_score': device.trust_score,
                    'is_vpn': device.is_vpn,
                    'is_proxy': device.is_proxy,
                    'last_seen': device.last_seen.isoformat(),
                    'ip_address': device.ip_address
                })
            
            return {
                'fraud_attempts': len(fraud_history_data),
                'fraud_history': fraud_history_data,
                'transaction_history': transaction_data,
                'device_history': device_data,
                'risk_profile': self._get_risk_profile_data(user)
            }
            
        except Exception as e:
            logger.error(f"Error getting user history: {e}")
            return {'error': str(e)}
    
    def _get_risk_profile_data(self, user: User) -> Dict:
        """Get user's risk profile data"""
        try:
            profile = UserRiskProfile.objects.get(user=user)
            return {
                'overall_score': profile.overall_risk_score,
                'account_score': profile.account_risk_score,
                'payment_score': profile.payment_risk_score,
                'behavior_score': profile.behavior_risk_score,
                'is_flagged': profile.is_flagged,
                'is_restricted': profile.is_restricted,
                'monitoring_level': profile.monitoring_level,
                'last_assessment': profile.last_risk_assessment.isoformat() if profile.last_risk_assessment else None
            }
        except UserRiskProfile.DoesNotExist:
            return {'overall_score': 0, 'is_flagged': False}
        except Exception as e:
            logger.error(f"Error getting risk profile: {e}")
            return {'error': str(e)}
    
    def _find_similar_cases(self, attempt: FraudAttempt) -> List[Dict]:
        """Find similar fraud cases"""
        try:
            # Find cases with similar fraud type and score
            similar_cases = FraudAttempt.objects.filter(
                attempt_type=attempt.attempt_type,
                fraud_score__gte=attempt.fraud_score - 10,
                fraud_score__lte=attempt.fraud_score + 10,
                status__in=['confirmed', 'false_positive']
            ).exclude(
                id=attempt.id
            ).order_by(
                '-fraud_score'
            )[:5]
            
            similar_data = []
            for case in similar_cases:
                similar_data.append({
                    'attempt_id': str(case.attempt_id),
                    'fraud_score': case.fraud_score,
                    'status': case.status,
                    'resolution': case.resolution_notes[:100] + '...' if case.resolution_notes else None,
                    'created_at': case.created_at.isoformat(),
                    'user_id': case.user_id
                })
            
            return similar_data
            
        except Exception as e:
            logger.error(f"Error finding similar cases: {e}")
            return []
    
    def _analyze_case_risk(self, attempt: FraudAttempt) -> Dict:
        """Analyze case risk factors"""
        risk_factors = []
        risk_score = attempt.fraud_score
        
        # Analyze evidence
        evidence = attempt.evidence_data
        
        # Check for high-risk indicators
        if evidence.get('vpn_detected', False):
            risk_factors.append({'factor': 'VPN detected', 'risk': 'high'})
            risk_score += 10
        
        if evidence.get('multiple_devices', False):
            risk_factors.append({'factor': 'Multiple devices', 'risk': 'medium'})
            risk_score += 5
        
        if evidence.get('suspicious_ip', False):
            risk_factors.append({'factor': 'Suspicious IP', 'risk': 'high'})
            risk_score += 15
        
        # Check user history
        user_history = self._get_user_history(attempt.user)
        if user_history.get('fraud_attempts', 0) > 0:
            risk_factors.append({'factor': 'Previous fraud attempts', 'risk': 'high'})
            risk_score += 20
        
        # Check amount involved
        if float(attempt.amount_involved) > 100:
            risk_factors.append({'factor': 'High amount involved', 'risk': 'medium'})
            risk_score += 10
        
        return {
            'calculated_risk_score': min(100, risk_score),
            'risk_factors': risk_factors,
            'risk_level': self._get_risk_level(risk_score),
            'recommended_priority': 'high' if risk_score >= 70 else 'medium'
        }
    
    def _generate_recommendations(self, attempt: FraudAttempt) -> List[Dict]:
        """Generate review recommendations"""
        recommendations = []
        fraud_type = attempt.attempt_type
        
        # General recommendations
        recommendations.append({
            'type': 'general',
            'priority': 'high',
            'action': 'Review all evidence thoroughly',
            'reason': 'Comprehensive evidence review is essential'
        })
        
        # Type-specific recommendations
        if fraud_type == 'multi_account':
            recommendations.append({
                'type': 'specific',
                'priority': 'high',
                'action': 'Check IP and device sharing patterns',
                'reason': 'Multi-account fraud often involves shared resources'
            })
        
        elif fraud_type == 'payment_fraud':
            recommendations.append({
                'type': 'specific',
                'priority': 'high',
                'action': 'Verify transaction patterns and amounts',
                'reason': 'Payment fraud may involve stolen payment methods'
            })
        
        elif fraud_type == 'click_fraud':
            recommendations.append({
                'type': 'specific',
                'priority': 'medium',
                'action': 'Analyze click patterns and timing',
                'reason': 'Click fraud often shows robotic patterns'
            })
        
        # Score-based recommendations
        if attempt.fraud_score >= 80:
            recommendations.append({
                'type': 'score_based',
                'priority': 'critical',
                'action': 'Consider immediate restriction',
                'reason': 'Very high fraud score indicates significant risk'
            })
        
        elif attempt.fraud_score >= 60:
            recommendations.append({
                'type': 'score_based',
                'priority': 'high',
                'action': 'Flag for enhanced monitoring',
                'reason': 'Elevated fraud score requires close attention'
            })
        
        return recommendations
    
    def _handle_confirmed_fraud(self, user: User, attempt: FraudAttempt, 
                               reviewer: User, notes: str) -> Dict:
        """Handle confirmed fraud case"""
        try:
            # Mark attempt as confirmed
            attempt.mark_as_confirmed(reviewer, notes)
            
            # Update user status
            user.is_flagged = True
            user.save()
            
            # Update risk profile
            risk_profile, _ = UserRiskProfile.objects.get_or_create(user=user)
            risk_profile.confirmed_fraud_attempts += 1
            risk_profile.is_flagged = True
            risk_profile.monitoring_level = 'strict'
            risk_profile.save()
            
            # Create confirmed fraud alert
            FraudAlert.objects.create(
                alert_type='manual_review',
                priority='critical',
                title=f"Fraud CONFIRMED: {attempt.attempt_type}",
                description=f"Fraud confirmed by {reviewer.username}: {notes}",
                user=user,
                fraud_attempt=attempt,
                data={
                    'confirmed_by': reviewer.username,
                    'confirmation_notes': notes,
                    'fraud_score': attempt.fraud_score
                }
            )
            
            # Trigger additional actions based on fraud type
            actions_taken = []
            
            if attempt.attempt_type == 'payment_fraud':
                # Reverse fraudulent transactions
                reversed_count = self._reverse_fraudulent_transactions(user, attempt)
                actions_taken.append(f'Reversed {reversed_count} transactions')
            
            elif attempt.attempt_type == 'multi_account':
                # Flag related accounts
                related_count = self._flag_related_accounts(user, attempt)
                actions_taken.append(f'Flagged {related_count} related accounts')
            
            return {
                'action': 'confirmed_fraud',
                'actions_taken': actions_taken,
                'user_flagged': True,
                'risk_profile_updated': True
            }
            
        except Exception as e:
            logger.error(f"Error handling confirmed fraud: {e}")
            return {'action': 'confirmed_fraud', 'error': str(e)}
    
    def _handle_false_positive(self, user: User, attempt: FraudAttempt,
                              reviewer: User, notes: str) -> Dict:
        """Handle false positive case"""
        try:
            # Update fraud rule statistics
            for rule in attempt.fraud_rules.all():
                rule.false_positive_count += 1
                rule.save()
            
            # Create false positive alert
            FraudAlert.objects.create(
                alert_type='manual_review',
                priority='medium',
                title=f"False Positive: {attempt.attempt_type}",
                description=f"Marked as false positive by {reviewer.username}: {notes}",
                user=user,
                fraud_attempt=attempt,
                data={
                    'marked_by': reviewer.username,
                    'false_positive_notes': notes
                }
            )
            
            # Update risk profile if needed
            risk_profile, _ = UserRiskProfile.objects.get_or_create(user=user)
            risk_profile.false_positives += 1
            
            # Adjust risk score if multiple false positives
            if risk_profile.false_positives >= 3:
                risk_profile.overall_risk_score = max(0, risk_profile.overall_risk_score - 10)
            
            risk_profile.save()
            
            return {
                'action': 'false_positive',
                'fraud_rules_updated': attempt.fraud_rules.count(),
                'risk_profile_adjusted': risk_profile.false_positives >= 3
            }
            
        except Exception as e:
            logger.error(f"Error handling false positive: {e}")
            return {'action': 'false_positive', 'error': str(e)}
    
    def _handle_escalation(self, user: User, attempt: FraudAttempt,
                          reviewer: User, notes: str) -> Dict:
        """Handle case escalation"""
        # Already handled in escalate_case method
        return {
            'action': 'escalated',
            'escalated_by': reviewer.username,
            'notes': notes
        }
    
    def _summarize_evidence(self, evidence_data: Dict) -> Dict:
        """Summarize evidence for quick review"""
        summary = {
            'key_indicators': [],
            'risk_factors': [],
            'data_points': 0
        }
        
        if not evidence_data:
            return summary
        
        # Extract key indicators
        for key, value in evidence_data.items():
            if isinstance(value, bool) and value:
                summary['key_indicators'].append(key.replace('_', ' ').title())
            
            if key in ['fraud_score', 'confidence_score', 'risk_score']:
                summary['risk_factors'].append(f"{key}: {value}")
        
        summary['data_points'] = len(evidence_data)
        
        return summary
    
    def _get_ip_info(self, ip_address: str) -> Dict:
        """Get IP address information"""
        try:
            ip_reputation = IPReputation.objects.filter(ip_address=ip_address).first()
            
            if ip_reputation:
                return {
                    'fraud_score': ip_reputation.fraud_score,
                    'is_blacklisted': ip_reputation.is_blacklisted,
                    'country': ip_reputation.country,
                    'isp': ip_reputation.isp,
                    'threat_types': ip_reputation.threat_types
                }
            
            return {
                'fraud_score': 0,
                'is_blacklisted': False,
                'status': 'No reputation data'
            }
            
        except Exception as e:
            logger.error(f"Error getting IP info: {e}")
            return {'error': str(e)}
    
    def _reverse_fraudulent_transactions(self, user: User, attempt: FraudAttempt) -> int:
        """Reverse fraudulent transactions"""
        try:
            affected_transactions = attempt.affected_transactions.filter(
                status='completed'
            )
            
            reversed_count = 0
            for transaction in affected_transactions:
                # Create reversal transaction
                reversal = WalletTransaction.objects.create(
                    user=user,
                    transaction_type='debit' if transaction.transaction_type == 'credit' else 'credit',
                    amount=transaction.amount,
                    status='completed',
                    description=f'Reversal of fraudulent transaction #{transaction.id}',
                    metadata={
                        'original_transaction_id': transaction.id,
                        'fraud_attempt_id': str(attempt.attempt_id),
                        'reversal_reason': 'Fraud confirmed'
                    }
                )
                
                # Mark original as reversed
                transaction.status = 'reversed'
                transaction.metadata = {
                    **transaction.metadata,
                    'reversed_by': str(attempt.attempt_id),
                    'reversal_transaction_id': reversal.id
                }
                transaction.save()
                
                reversed_count += 1
            
            return reversed_count
            
        except Exception as e:
            logger.error(f"Error reversing transactions: {e}")
            return 0
    
    def _flag_related_accounts(self, user: User, attempt: FraudAttempt) -> int:
        """Flag accounts related to multi-account fraud"""
        try:
            evidence = attempt.evidence_data
            flagged_count = 0
            
            # Check for shared IPs
            if 'shared_ips' in evidence:
                shared_ips = evidence['shared_ips']
                
                for ip_data in shared_ips:
                    # Find users with same IP
                    from users.models import User
                    related_users = User.objects.filter(
                        last_login_ip=ip_data['ip_address']
                    ).exclude(id=user.id)
                    
                    for related_user in related_users:
                        # Flag related user
                        risk_profile, _ = UserRiskProfile.objects.get_or_create(user=related_user)
                        risk_profile.is_flagged = True
                        risk_profile.warning_flags.append('related_to_fraud_account')
                        risk_profile.save()
                        
                        flagged_count += 1
            
            # Check for shared devices
            if 'shared_devices' in evidence:
                shared_devices = evidence['shared_devices']
                
                for device_data in shared_devices:
                    # Find users with same device
                    related_devices = DeviceFingerprint.objects.filter(
                        device_hash=device_data['device_hash']
                    ).exclude(user=user)
                    
                    for device in related_devices:
                        # Flag related user
                        risk_profile, _ = UserRiskProfile.objects.get_or_create(user=device.user)
                        risk_profile.is_flagged = True
                        risk_profile.warning_flags.append('shared_device_with_fraud_account')
                        risk_profile.save()
                        
                        flagged_count += 1
            
            return flagged_count
            
        except Exception as e:
            logger.error(f"Error flagging related accounts: {e}")
            return 0
    
    def _create_review_log(self, attempt: FraudAttempt, decision: str,
                          reviewer: User, notes: str):
        """Create review audit log"""
        try:
            from audit_logs.models import AuditLog
            
            AuditLog.objects.create(
                user=attempt.user,
                action=f'FRAUD_REVIEW_{decision.upper()}',
                description=f"Fraud case reviewed by {reviewer.username}: {notes}",
                metadata={
                    'attempt_id': str(attempt.attempt_id),
                    'fraud_type': attempt.attempt_type,
                    'fraud_score': attempt.fraud_score,
                    'reviewer': reviewer.username,
                    'decision': decision,
                    'review_notes': notes
                }
            )
        except Exception as e:
            logger.error(f"Error creating review log: {e}")
    
    def _update_related_alerts(self, attempt: FraudAttempt, decision: str, reviewer: User):
        """Update related fraud alerts"""
        try:
            related_alerts = FraudAlert.objects.filter(fraud_attempt=attempt)
            
            for alert in related_alerts:
                alert.is_resolved = True
                alert.resolved_at = self.now
                alert.resolved_by = reviewer
                alert.resolution_notes = f"Parent fraud case {decision}"
                alert.save()
                
        except Exception as e:
            logger.error(f"Error updating related alerts: {e}")
    
    def _update_user_risk_profile(self, user: User, decision: str, attempt: FraudAttempt):
        """Update user risk profile based on review decision"""
        try:
            risk_profile, _ = UserRiskProfile.objects.get_or_create(user=user)
            
            if decision == 'confirmed':
                risk_profile.confirmed_fraud_attempts += 1
                risk_profile.overall_risk_score = min(100, risk_profile.overall_risk_score + 20)
            elif decision == 'false_positive':
                risk_profile.false_positives += 1
                risk_profile.overall_risk_score = max(0, risk_profile.overall_risk_score - 10)
            
            risk_profile.save()
            
        except Exception as e:
            logger.error(f"Error updating user risk profile: {e}")
    
    def _notify_senior_reviewers(self, attempt: FraudAttempt, reason: str, priority: str):
        """Notify senior reviewers about escalated case"""
        try:
            # In production, this would send notifications via email/slack/etc.
            # For now, just log it
            logger.info(f"Senior reviewers notified about escalated case {attempt.attempt_id}: {reason}")
        except Exception as e:
            logger.error(f"Error notifying senior reviewers: {e}")
    
    def _get_risk_level(self, score: int) -> str:
        """Get risk level description"""
        if score >= 90:
            return 'critical'
        elif score >= 80:
            return 'high'
        elif score >= 70:
            return 'elevated'
        elif score >= 60:
            return 'medium'
        elif score >= 40:
            return 'low'
        else:
            return 'minimal'