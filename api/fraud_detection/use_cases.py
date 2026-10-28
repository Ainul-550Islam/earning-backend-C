# =============================================================================
# fraud_detection/use_cases.py
# =============================================================================
"""
Use Cases Layer for Fraud Detection System.

Implements complex fraud detection logic including multi-account detection,
suspicious pattern analysis, and advanced risk assessment workflows.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple, Set

from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model

from api.fraud_detection.repositories import (
    fraud_rule_repository, fraud_case_repository, fraud_alert_repository,
    fraud_risk_profile_repository, fraud_device_fingerprint_repository,
    fraud_suspicious_ip_repository
)
from api.fraud_detection.selectors import (
    fraud_rule_selector, fraud_case_selector, fraud_alert_selector,
    fraud_risk_profile_selector, fraud_device_fingerprint_selector,
    fraud_suspicious_ip_selector
)
from api.fraud_detection.encryption import (
    encrypt_ip_address, encrypt_device_id, generate_integrity_hash
)
from api.fraud_detection.choices import SeverityLevel, FraudAlertType
from api.fraud_detection.constants import (
    MAX_DEVICES_PER_USER, TIME_THRESHOLDS,
    FRAUD_SCORE_WEIGHTS, RISK_THRESHOLDS
)
from api.fraud_detection.exceptions import UseCaseError, FraudDetectionError
from api.fraud_detection.models import FraudCase, FraudAlert, FraudRiskProfile


logger = logging.getLogger(__name__)

User = get_user_model()


class BaseUseCase:
    """
    Base use case with common functionality.
    
    Provides structure for complex fraud detection workflows
    following Clean Architecture principles.
    """
    
    def __init__(self):
        """Initialize use case with dependencies."""
        self.rule_repo = fraud_rule_repository
        self.case_repo = fraud_case_repository
        self.alert_repo = fraud_alert_repository
        self.risk_profile_repo = fraud_risk_profile_repository
        self.device_repo = fraud_device_fingerprint_repository
        self.ip_repo = fraud_suspicious_ip_repository
        
        self.rule_selector = fraud_rule_selector
        self.case_selector = fraud_case_selector
        self.alert_selector = fraud_alert_selector
        self.risk_profile_selector = fraud_risk_profile_selector
        self.device_selector = fraud_device_fingerprint_selector
        self.ip_selector = fraud_suspicious_ip_selector
    
    def execute(self, *args, **kwargs) -> Any:
        """
        Execute the use case.
        
        Must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement execute method")


class MultiAccountDetectionUseCase(BaseUseCase):
    """
    Use case for detecting multi-account fraud patterns.
    
    Analyzes user behavior, device fingerprints, and IP patterns
    to identify users operating multiple accounts.
    """
    
    def execute(self, user_id: Union[int, str], 
               context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute multi-account detection analysis.
        
        Args:
            user_id: User ID to analyze
            context: Additional context data (IP, device info, etc.)
            
        Returns:
            Dictionary with detection results and recommendations
        """
        try:
            logger.info(f"Starting multi-account detection for user: {user_id}")
            
            # Get user profile
            user = self._get_user(user_id)
            if not user:
                raise UseCaseError(f"User not found: {user_id}")
            
            # Analyze device fingerprints
            device_analysis = self._analyze_device_patterns(user_id, context)
            
            # Analyze IP patterns
            ip_analysis = self._analyze_ip_patterns(user_id, context)
            
            # Analyze behavioral patterns
            behavior_analysis = self._analyze_behavioral_patterns(user_id)
            
            # Analyze temporal patterns
            temporal_analysis = self._analyze_temporal_patterns(user_id)
            
            # Calculate overall risk score
            risk_score = self._calculate_multi_account_risk(
                device_analysis, ip_analysis, behavior_analysis, temporal_analysis
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                risk_score, device_analysis, ip_analysis, behavior_analysis
            )
            
            # Create or update fraud case if high risk
            case = None
            if risk_score >= RISK_THRESHOLDS['high']:
                case = self._create_fraud_case(user_id, risk_score, {
                    'device_analysis': device_analysis,
                    'ip_analysis': ip_analysis,
                    'behavior_analysis': behavior_analysis,
                    'temporal_analysis': temporal_analysis
                })
            
            # Update risk profile
            self._update_risk_profile(user_id, risk_score, 'multi_account_detection')
            
            result = {
                'user_id': user_id,
                'risk_score': risk_score,
                'risk_level': self._get_risk_level(risk_score),
                'device_analysis': device_analysis,
                'ip_analysis': ip_analysis,
                'behavior_analysis': behavior_analysis,
                'temporal_analysis': temporal_analysis,
                'recommendations': recommendations,
                'fraud_case_id': case.pk if case else None,
                'detection_timestamp': timezone.now().isoformat()
            }
            
            logger.info(f"Multi-account detection completed for user: {user_id}, risk_score: {risk_score}")
            return result
            
        except Exception as e:
            logger.error("Multi-account detection failed for user %s: %s", user_id, e, exc_info=True)
            raise UseCaseError(f"Multi-account detection failed: {e}")
    
    def _get_user(self, user_id: Union[int, str]) -> Optional[User]:
        """Get user by ID."""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
    
    def _analyze_device_patterns(self, user_id: Union[int, str], 
                                context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze device fingerprint patterns for multi-account detection."""
        device_fingerprints = self.device_selector.get_fingerprints_for_user(user_id)
        
        analysis = {
            'total_devices': len(device_fingerprints),
            'suspicious_devices': [],
            'device_risk_score': 0,
            'findings': []
        }
        
        # Check for devices used by multiple users
        for fingerprint in device_fingerprints:
            if fingerprint.user_count > 1:
                analysis['suspicious_devices'].append({
                    'device_hash': fingerprint.device_hash,
                    'user_count': fingerprint.user_count,
                    'first_seen': fingerprint.first_seen,
                    'last_seen': fingerprint.last_seen
                })
                analysis['findings'].append(
                    f"Device used by {fingerprint.user_count} different users"
                )
        
        # Calculate device risk score
        if analysis['total_devices'] > MAX_DEVICES_PER_USER:
            analysis['device_risk_score'] += 30
            analysis['findings'].append(f"User has {analysis['total_devices']} devices (limit: {MAX_DEVICES_PER_USER})")
        
        analysis['device_risk_score'] += len(analysis['suspicious_devices']) * 25
        
        return analysis
    
    def _analyze_ip_patterns(self, user_id: Union[int, str], 
                            context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze IP address patterns for multi-account detection."""
        current_ip = context.get('ip_address') if context else None
        analysis = {
            'current_ip': current_ip,
            'suspicious_ips': [],
            'ip_risk_score': 0,
            'findings': []
        }
        
        # Check current IP if provided
        if current_ip:
            suspicious_ip = self.ip_selector.get_suspicious_ip(current_ip)
            if suspicious_ip and suspicious_ip.risk_score >= RISK_THRESHOLDS['medium']:
                analysis['suspicious_ips'].append({
                    'ip_address': current_ip,
                    'risk_score': suspicious_ip.risk_score,
                    'reason': suspicious_ip.reason
                })
                analysis['ip_risk_score'] += suspicious_ip.risk_score // 2
                analysis['findings'].append(f"Current IP {current_ip} has risk score {suspicious_ip.risk_score}")
        
        # Get user's recent IP patterns (would need session data)
        # This is a simplified version - in practice, you'd analyze session history
        recent_ips = self._get_user_recent_ips(user_id, days=30)
        
        # Check for rapid IP changes
        if len(recent_ips) > 5:
            analysis['ip_risk_score'] += 20
            analysis['findings'].append(f"User accessed from {len(recent_ips)} different IPs in 30 days")
        
        return analysis
    
    def _analyze_behavioral_patterns(self, user_id: Union[int, str]) -> Dict[str, Any]:
        """Analyze behavioral patterns for multi-account detection."""
        analysis = {
            'behavior_risk_score': 0,
            'findings': []
        }
        
        # Analyze account creation patterns
        user = self._get_user(user_id)
        if user:
            account_age = (timezone.now() - user.date_joined).days
            
            # Very new accounts with high activity
            if account_age < 7:
                analysis['behavior_risk_score'] += 15
                analysis['findings'].append("Account created very recently")
            
            # Check for similar account names (would need additional queries)
            similar_accounts = self._find_similar_accounts(user.username)
            if similar_accounts:
                analysis['behavior_risk_score'] += len(similar_accounts) * 10
                analysis['findings'].append(f"Found {len(similar_accounts)} accounts with similar usernames")
        
        return analysis
    
    def _analyze_temporal_patterns(self, user_id: Union[int, str]) -> Dict[str, Any]:
        """Analyze temporal patterns for multi-account detection."""
        analysis = {
            'temporal_risk_score': 0,
            'findings': []
        }
        
        # Get user's recent activity patterns
        recent_activity = self._get_user_activity_patterns(user_id, hours=24)
        
        # Check for unusual activity timing
        if recent_activity.get('night_activity_ratio', 0) > 0.7:
            analysis['temporal_risk_score'] += 10
            analysis['findings'].append("High activity during unusual hours")
        
        # Check for rapid successive actions
        if recent_activity.get('rapid_actions', 0) > TIME_THRESHOLDS['rapid_clicks']:
            analysis['temporal_risk_score'] += 15
            analysis['findings'].append("Rapid successive actions detected")
        
        return analysis
    
    def _calculate_multi_account_risk(self, device_analysis: Dict[str, Any],
                                    ip_analysis: Dict[str, Any],
                                    behavior_analysis: Dict[str, Any],
                                    temporal_analysis: Dict[str, Any]) -> int:
        """Calculate overall multi-account risk score."""
        risk_score = 0
        
        # Weighted risk calculation
        risk_score += device_analysis['device_risk_score'] * FRAUD_SCORE_WEIGHTS.get('device', 30) // 100
        risk_score += ip_analysis['ip_risk_score'] * FRAUD_SCORE_WEIGHTS.get('vpn', 20) // 100
        risk_score += behavior_analysis['behavior_risk_score'] * FRAUD_SCORE_WEIGHTS.get('pattern', 25) // 100
        risk_score += temporal_analysis['temporal_risk_score'] * FRAUD_SCORE_WEIGHTS.get('velocity', 25) // 100
        
        return min(risk_score, 100)  # Cap at 100
    
    def _generate_recommendations(self, risk_score: int, 
                                device_analysis: Dict[str, Any],
                                ip_analysis: Dict[str, Any],
                                behavior_analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        if risk_score >= RISK_THRESHOLDS['critical']:
            recommendations.extend([
                "Immediate account suspension recommended",
                "Require identity verification",
                "Review all associated accounts",
                "Block suspicious IP addresses"
            ])
        elif risk_score >= RISK_THRESHOLDS['high']:
            recommendations.extend([
                "Enhanced monitoring recommended",
                "Require additional verification",
                "Limit account functionality",
                "Review device fingerprints"
            ])
        elif risk_score >= RISK_THRESHOLDS['medium']:
            recommendations.extend([
                "Increase monitoring frequency",
                "Review account activity",
                "Consider CAPTCHA challenges"
            ])
        
        # Specific recommendations based on findings
        if device_analysis['total_devices'] > MAX_DEVICES_PER_USER:
            recommendations.append("Implement device limit restrictions")
        
        if ip_analysis['suspicious_ips']:
            recommendations.append("Block or flag suspicious IP addresses")
        
        return recommendations
    
    def _create_fraud_case(self, user_id: Union[int, str], risk_score: int,
                          evidence: Dict[str, Any]) -> FraudCase:
        """Create fraud case for multi-account detection."""
        case_data = {
            'user_id': user_id,
            'case_type': 'multi_account',
            'risk_score': risk_score,
            'status': 'open',
            'description': f"Multi-account fraud detection with risk score: {risk_score}",
            'evidence_summary': evidence
        }
        
        return self.case_repo.create(**case_data)
    
    def _update_risk_profile(self, user_id: Union[int, str], risk_score: int, reason: str):
        """Update user risk profile."""
        self.risk_profile_repo.update_risk_score(user_id, risk_score, reason)
    
    def _get_risk_level(self, risk_score: int) -> str:
        """Get risk level from score."""
        if risk_score >= RISK_THRESHOLDS['critical']:
            return 'critical'
        elif risk_score >= RISK_THRESHOLDS['high']:
            return 'high'
        elif risk_score >= RISK_THRESHOLDS['medium']:
            return 'medium'
        else:
            return 'low'
    
    def _get_user_recent_ips(self, user_id: Union[int, str], days: int) -> List[str]:
        """Get user's recent IP addresses (simplified)."""
        # In practice, this would query session logs or authentication logs
        # For now, return empty list as placeholder
        return []
    
    def _find_similar_accounts(self, username: str) -> List[str]:
        """Find accounts with similar usernames."""
        # Simple similarity check - in practice, use more sophisticated algorithms
        similar_accounts = User.objects.filter(
            username__icontains=username[:5]  # Check first 5 characters
        ).exclude(username=username).values_list('username', flat=True)[:5]
        
        return list(similar_accounts)
    
    def _get_user_activity_patterns(self, user_id: Union[int, str], hours: int) -> Dict[str, Any]:
        """Get user activity patterns (simplified)."""
        # In practice, this would analyze user activity logs
        # For now, return placeholder data
        return {
            'night_activity_ratio': 0.3,
            'rapid_actions': 5
        }


class SuspiciousPatternDetectionUseCase(BaseUseCase):
    """
    Use case for detecting suspicious behavioral patterns.
    
    Analyzes user behavior sequences, timing patterns, and
    anomalous activities to identify potential fraud.
    """
    
    def execute(self, user_id: Union[int, str], 
               activity_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute suspicious pattern detection.
        
        Args:
            user_id: User ID to analyze
            activity_sequence: Sequence of user activities
            
        Returns:
            Dictionary with pattern detection results
        """
        try:
            logger.info(f"Starting suspicious pattern detection for user: {user_id}")
            
            # Analyze activity sequence
            sequence_analysis = self._analyze_activity_sequence(activity_sequence)
            
            # Detect timing anomalies
            timing_analysis = self._detect_timing_anomalies(activity_sequence)
            
            # Identify behavioral outliers
            behavior_analysis = self._identify_behavioral_outliers(user_id, activity_sequence)
            
            # Calculate pattern risk score
            risk_score = self._calculate_pattern_risk(
                sequence_analysis, timing_analysis, behavior_analysis
            )
            
            # Generate alerts if necessary
            alerts = []
            if risk_score >= RISK_THRESHOLDS['medium']:
                alerts = self._generate_pattern_alerts(user_id, risk_score, {
                    'sequence_analysis': sequence_analysis,
                    'timing_analysis': timing_analysis,
                    'behavior_analysis': behavior_analysis
                })
            
            result = {
                'user_id': user_id,
                'risk_score': risk_score,
                'risk_level': self._get_risk_level(risk_score),
                'sequence_analysis': sequence_analysis,
                'timing_analysis': timing_analysis,
                'behavior_analysis': behavior_analysis,
                'alerts_generated': len(alerts),
                'detection_timestamp': timezone.now().isoformat()
            }
            
            logger.info(f"Suspicious pattern detection completed for user: {user_id}, risk_score: {risk_score}")
            return result
            
        except Exception as e:
            logger.error("Suspicious pattern detection failed for user %s: %s", user_id, e, exc_info=True)
            raise UseCaseError(f"Suspicious pattern detection failed: {e}")
    
    def _analyze_activity_sequence(self, activity_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze sequence of activities for patterns."""
        analysis = {
            'total_activities': len(activity_sequence),
            'unique_actions': set(),
            'repetitive_patterns': [],
            'sequence_risk_score': 0,
            'findings': []
        }
        
        if not activity_sequence:
            return analysis
        
        # Extract unique actions
        for activity in activity_sequence:
            action = activity.get('action', '')
            if action:
                analysis['unique_actions'].add(action)
        
        # Check for repetitive patterns
        action_counts = {}
        for activity in activity_sequence:
            action = activity.get('action', '')
            action_counts[action] = action_counts.get(action, 0) + 1
        
        for action, count in action_counts.items():
            if count > 10:  # Threshold for repetitive actions
                analysis['repetitive_patterns'].append({
                    'action': action,
                    'count': count,
                    'percentage': (count / len(activity_sequence)) * 100
                })
                analysis['sequence_risk_score'] += min(count * 2, 30)
                analysis['findings'].append(f"Repetitive action '{action}' performed {count} times")
        
        return analysis
    
    def _detect_timing_anomalies(self, activity_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect timing anomalies in activity sequence."""
        analysis = {
            'timing_risk_score': 0,
            'findings': [],
            'anomalies': []
        }
        
        if len(activity_sequence) < 2:
            return analysis
        
        # Calculate time intervals between activities
        intervals = []
        for i in range(1, len(activity_sequence)):
            current_time = activity_sequence[i].get('timestamp')
            prev_time = activity_sequence[i-1].get('timestamp')
            
            if current_time and prev_time:
                if isinstance(current_time, str):
                    current_time = datetime.fromisoformat(current_time.replace('Z', '+00:00'))
                if isinstance(prev_time, str):
                    prev_time = datetime.fromisoformat(prev_time.replace('Z', '+00:00'))
                
                interval = (current_time - prev_time).total_seconds()
                intervals.append(interval)
        
        if not intervals:
            return analysis
        
        # Detect rapid activity (very short intervals)
        rapid_intervals = [interval for interval in intervals if interval < 1]
        if len(rapid_intervals) > 5:
            analysis['timing_risk_score'] += 20
            analysis['findings'].append(f"Detected {len(rapid_intervals)} rapid successive actions")
            analysis['anomalies'].append({
                'type': 'rapid_activity',
                'count': len(rapid_intervals),
                'avg_interval': sum(rapid_intervals) / len(rapid_intervals)
            })
        
        # Detect consistent timing (potential bot behavior)
        if len(intervals) > 10:
            avg_interval = sum(intervals) / len(intervals)
            variance = sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)
            
            if variance < 0.1:  # Very low variance suggests automation
                analysis['timing_risk_score'] += 25
                analysis['findings'].append("Highly consistent activity timing detected")
                analysis['anomalies'].append({
                    'type': 'consistent_timing',
                    'avg_interval': avg_interval,
                    'variance': variance
                })
        
        return analysis
    
    def _identify_behavioral_outliers(self, user_id: Union[int, str], 
                                    activity_sequence: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Identify behavioral outliers compared to normal patterns."""
        analysis = {
            'behavior_risk_score': 0,
            'findings': [],
            'outliers': []
        }
        
        # Get user's baseline behavior (simplified)
        baseline = self._get_user_baseline_behavior(user_id)
        
        # Compare current activity to baseline
        current_actions = set(activity.get('action', '') for activity in activity_sequence)
        baseline_actions = set(baseline.get('common_actions', []))
        
        # Unusual actions
        unusual_actions = current_actions - baseline_actions
        if unusual_actions:
            analysis['behavior_risk_score'] += len(unusual_actions) * 5
            analysis['findings'].append(f"Unusual actions detected: {list(unusual_actions)}")
            analysis['outliers'].append({
                'type': 'unusual_actions',
                'actions': list(unusual_actions)
            })
        
        # Activity volume anomaly
        current_volume = len(activity_sequence)
        baseline_volume = baseline.get('avg_daily_activity', 10)
        
        if current_volume > baseline_volume * 3:
            analysis['behavior_risk_score'] += 15
            analysis['findings'].append(f"Activity volume {current_volume} significantly above baseline {baseline_volume}")
            analysis['outliers'].append({
                'type': 'volume_anomaly',
                'current': current_volume,
                'baseline': baseline_volume,
                'ratio': current_volume / baseline_volume
            })
        
        return analysis
    
    def _calculate_pattern_risk(self, sequence_analysis: Dict[str, Any],
                             timing_analysis: Dict[str, Any],
                             behavior_analysis: Dict[str, Any]) -> int:
        """Calculate overall pattern risk score."""
        risk_score = 0
        
        risk_score += sequence_analysis['sequence_risk_score']
        risk_score += timing_analysis['timing_risk_score']
        risk_score += behavior_analysis['behavior_risk_score']
        
        return min(risk_score, 100)
    
    def _generate_pattern_alerts(self, user_id: Union[int, str], risk_score: int,
                               analysis_data: Dict[str, Any]) -> List[FraudAlert]:
        """Generate fraud alerts for suspicious patterns."""
        alerts = []
        
        alert_data = {
            'user_id': user_id,
            'alert_type': FraudAlertType.BEHAVIORAL_ANOMALY,
            'severity_score': risk_score,
            'description': f"Suspicious behavioral pattern detected with risk score: {risk_score}",
            'details': analysis_data,
            'acknowledged': False
        }
        
        alert = self.alert_repo.create(**alert_data)
        alerts.append(alert)
        
        return alerts
    
    def _get_risk_level(self, risk_score: int) -> str:
        """Get risk level from score."""
        if risk_score >= RISK_THRESHOLDS['critical']:
            return 'critical'
        elif risk_score >= RISK_THRESHOLDS['high']:
            return 'high'
        elif risk_score >= RISK_THRESHOLDS['medium']:
            return 'medium'
        else:
            return 'low'
    
    def _get_user_baseline_behavior(self, user_id: Union[int, str]) -> Dict[str, Any]:
        """Get user's baseline behavior patterns (simplified)."""
        # In practice, this would analyze historical activity data
        # For now, return placeholder baseline
        return {
            'common_actions': ['login', 'view_page', 'click_button'],
            'avg_daily_activity': 10,
            'typical_session_duration': 1800  # 30 minutes
        }


class RiskAssessmentUseCase(BaseUseCase):
    """
    Use case for comprehensive risk assessment.
    
    Combines multiple detection methods to provide
    overall risk assessment for users and transactions.
    """
    
    def execute(self, user_id: Union[int, str], 
               transaction_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute comprehensive risk assessment.
        
        Args:
            user_id: User ID to assess
            transaction_data: Optional transaction data
            
        Returns:
            Dictionary with comprehensive risk assessment
        """
        try:
            logger.info(f"Starting comprehensive risk assessment for user: {user_id}")
            
            # Get existing risk profile
            risk_profile = self.risk_profile_selector.get_profile_by_user(user_id)
            current_risk_score = risk_profile.risk_score if risk_profile else 0
            
            # Multi-account detection
            multi_account_detector = MultiAccountDetectionUseCase()
            multi_account_result = multi_account_detector.execute(user_id, transaction_data)
            
            # Suspicious pattern detection
            pattern_detector = SuspiciousPatternDetectionUseCase()
            activity_sequence = transaction_data.get('activity_sequence', []) if transaction_data else []
            pattern_result = pattern_detector.execute(user_id, activity_sequence)
            
            # Transaction risk assessment
            transaction_risk = self._assess_transaction_risk(transaction_data) if transaction_data else 0
            
            # Calculate comprehensive risk score
            comprehensive_risk = self._calculate_comprehensive_risk(
                current_risk_score,
                multi_account_result['risk_score'],
                pattern_result['risk_score'],
                transaction_risk
            )
            
            # Generate assessment report
            assessment = {
                'user_id': user_id,
                'previous_risk_score': current_risk_score,
                'current_risk_score': comprehensive_risk,
                'risk_change': comprehensive_risk - current_risk_score,
                'risk_level': self._get_risk_level(comprehensive_risk),
                'multi_account_analysis': multi_account_result,
                'pattern_analysis': pattern_result,
                'transaction_risk': transaction_risk,
                'recommendations': self._generate_assessment_recommendations(comprehensive_risk),
                'assessment_timestamp': timezone.now().isoformat()
            }
            
            # Update risk profile
            self.risk_profile_repo.update_risk_score(user_id, comprehensive_risk, 'comprehensive_assessment')
            
            logger.info(f"Risk assessment completed for user: {user_id}, risk_score: {comprehensive_risk}")
            return assessment
            
        except Exception as e:
            logger.error("Risk assessment failed for user %s: %s", user_id, e, exc_info=True)
            raise UseCaseError(f"Risk assessment failed: {e}")
    
    def _assess_transaction_risk(self, transaction_data: Dict[str, Any]) -> int:
        """Assess transaction-specific risk."""
        risk_score = 0
        
        if not transaction_data:
            return risk_score
        
        # Amount-based risk
        amount = transaction_data.get('amount', 0)
        if amount > 10000:
            risk_score += 20
        elif amount > 5000:
            risk_score += 10
        elif amount > 1000:
            risk_score += 5
        
        # Location-based risk
        country = transaction_data.get('country', '')
        high_risk_countries = ['XX', 'YY', 'ZZ']  # Placeholder high-risk countries
        if country in high_risk_countries:
            risk_score += 15
        
        # Time-based risk
        transaction_time = transaction_data.get('timestamp')
        if transaction_time:
            if isinstance(transaction_time, str):
                transaction_time = datetime.fromisoformat(transaction_time.replace('Z', '+00:00'))
            
            hour = transaction_time.hour
            if hour < 6 or hour > 22:  # Unusual hours
                risk_score += 10
        
        return min(risk_score, 50)  # Cap transaction risk at 50
    
    def _calculate_comprehensive_risk(self, base_risk: int, multi_account_risk: int,
                                    pattern_risk: int, transaction_risk: int) -> int:
        """Calculate comprehensive risk score."""
        # Weighted combination of different risk factors
        weights = {
            'base': 0.3,
            'multi_account': 0.3,
            'pattern': 0.25,
            'transaction': 0.15
        }
        
        comprehensive_risk = (
            base_risk * weights['base'] +
            multi_account_risk * weights['multi_account'] +
            pattern_risk * weights['pattern'] +
            transaction_risk * weights['transaction']
        )
        
        return min(int(comprehensive_risk), 100)
    
    def _generate_assessment_recommendations(self, risk_score: int) -> List[str]:
        """Generate recommendations based on risk assessment."""
        recommendations = []
        
        if risk_score >= RISK_THRESHOLDS['critical']:
            recommendations.extend([
                "Immediate action required",
                "Consider account suspension",
                "Manual review mandatory",
                "Enhanced monitoring for all activities"
            ])
        elif risk_score >= RISK_THRESHOLDS['high']:
            recommendations.extend([
                "Increased monitoring recommended",
                "Additional verification required",
                "Limit high-risk activities",
                "Review recent transactions"
            ])
        elif risk_score >= RISK_THRESHOLDS['medium']:
            recommendations.extend([
                "Standard monitoring protocols",
                "Periodic review recommended",
                "Watch for risk escalation"
            ])
        
        return recommendations
    
    def _get_risk_level(self, risk_score: int) -> str:
        """Get risk level from score."""
        if risk_score >= RISK_THRESHOLDS['critical']:
            return 'critical'
        elif risk_score >= RISK_THRESHOLDS['high']:
            return 'high'
        elif risk_score >= RISK_THRESHOLDS['medium']:
            return 'medium'
        else:
            return 'low'


# Use case instances for dependency injection
multi_account_detection_use_case = MultiAccountDetectionUseCase()
suspicious_pattern_detection_use_case = SuspiciousPatternDetectionUseCase()
risk_assessment_use_case = RiskAssessmentUseCase()


def get_use_case(use_case_name: str) -> BaseUseCase:
    """
    Get use case instance by name.
    
    Args:
        use_case_name: Use case name
        
    Returns:
        Use case instance
        
    Raises:
        UseCaseError: If use case not found
    """
    use_case_map = {
        'multi_account_detection': multi_account_detection_use_case,
        'suspicious_pattern_detection': suspicious_pattern_detection_use_case,
        'risk_assessment': risk_assessment_use_case,
    }
    
    use_case = use_case_map.get(use_case_name.lower())
    if not use_case:
        raise UseCaseError(f"Use case not found: {use_case_name}")
    
    return use_case
