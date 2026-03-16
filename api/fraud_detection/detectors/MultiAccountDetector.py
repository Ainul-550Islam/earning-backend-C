from .BaseDetector import BaseDetector
from django.db.models import Count, Q
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import hashlib
import logging
from typing import Dict, List, Any
from api.users.models import User
from api.wallet.models import WalletTransaction
from ..models import DeviceFingerprint, IPReputation

logger = logging.getLogger(__name__)

class MultiAccountDetector(BaseDetector):
    """
    Detects multi-account fraud (same user creating multiple accounts)
    Uses device fingerprinting, IP analysis, and behavioral patterns
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.threshold_similarity = config.get('threshold_similarity', 85) if config else 85
        self.max_accounts_per_ip = config.get('max_accounts_per_ip', 3) if config else 3
        self.max_accounts_per_device = config.get('max_accounts_per_device', 2) if config else 2
        
    def get_required_fields(self) -> List[str]:
        return ['user_id', 'ip_address', 'device_data']
    
    def detect(self, data: Dict) -> Dict:
        """
        Detect multi-account fraud
        """
        try:
            user_id = data.get('user_id')
            ip_address = data.get('ip_address')
            device_data = data.get('device_data', {})
            
            if not self.validate_data(data):
                return self.get_detection_result()
            
            # Run detection checks
            checks = [
                self._check_ip_sharing(ip_address, user_id),
                self._check_device_fingerprint(device_data, user_id),
                self._check_behavioral_patterns(user_id),
                self._check_registration_patterns(user_id),
                self._check_payment_patterns(user_id),
                self._check_referral_patterns(user_id)
            ]
            
            # Calculate overall score
            self._calculate_overall_score(checks)
            
            # Set detection result
            self.detected_fraud = self.fraud_score >= 70
            
            # Log detection
            self.log_detection(user_id)
            
            return self.get_detection_result()
            
        except Exception as e:
            logger.error(f"Error in MultiAccountDetector: {str(e)}")
            return {
                'detector': self.detector_name,
                'is_fraud': False,
                'fraud_score': 0,
                'confidence': 0,
                'error': str(e)
            }
    
    def _check_ip_sharing(self, ip_address: str, current_user_id: int) -> Dict:
        """
        Check if IP address is shared among multiple accounts
        """
        try:
            # Get all users from same IP in last 30 days
            thirty_days_ago = timezone.now() - timedelta(days=30)
            
            # Count users from same IP
            same_ip_users = User.objects.filter(
                Q(last_login_ip=ip_address) | 
                Q(registration_ip=ip_address)
            ).exclude(id=current_user_id)
            
            user_count = same_ip_users.count()
            
            # Get IP reputation
            ip_reputation, _ = IPReputation.objects.get_or_create(ip_address=ip_address)
            
            result = {
                'check': 'ip_sharing',
                'user_count': user_count,
                'max_allowed': self.max_accounts_per_ip,
                'ip_fraud_score': ip_reputation.fraud_score,
                'is_blacklisted': ip_reputation.is_blacklisted
            }
            
            # Evaluate risk
            if user_count >= self.max_accounts_per_ip:
                self.add_reason(f"IP {ip_address} shared by {user_count} accounts", 25)
                result['risk_score'] = 25
            elif user_count >= 2:
                self.add_warning(f"IP {ip_address} shared by {user_count} accounts")
                result['risk_score'] = 15
            else:
                result['risk_score'] = 0
            
            if ip_reputation.is_blacklisted:
                self.add_reason(f"IP {ip_address} is blacklisted: {ip_reputation.blacklist_reason}", 30)
                result['risk_score'] += 30
            
            if ip_reputation.fraud_score >= 70:
                self.add_reason(f"IP {ip_address} has high fraud score: {ip_reputation.fraud_score}", 20)
                result['risk_score'] += 20
            
            result['risk_score'] = min(100, result['risk_score'])
            
            # Add evidence
            self.add_evidence('ip_sharing_analysis', result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in IP sharing check: {e}")
            return {'check': 'ip_sharing', 'error': str(e), 'risk_score': 0}
    
    def _check_device_fingerprint(self, device_data: Dict, current_user_id: int) -> Dict:
        """
        Check device fingerprint for multi-account detection
        """
        try:
            # Generate device hash
            device_hash = self._generate_device_hash(device_data)
            
            # Find other users with same device
            same_device_users = DeviceFingerprint.objects.filter(
                device_hash=device_hash
            ).exclude(user_id=current_user_id)
            
            user_count = same_device_users.count()
            
            result = {
                'check': 'device_fingerprint',
                'device_hash': device_hash[:20] + '...',  # Truncate for logging
                'user_count': user_count,
                'max_allowed': self.max_accounts_per_device,
                'device_trust_score': 100  # Default
            }
            
            # Get trust score from first device (if exists)
            if same_device_users.exists():
                device = same_device_users.first()
                result['device_trust_score'] = device.trust_score
            
            # Evaluate risk
            if user_count >= self.max_accounts_per_device:
                self.add_reason(f"Device used by {user_count} accounts", 30)
                result['risk_score'] = 30
            elif user_count >= 1:
                self.add_warning(f"Device used by {user_count + 1} accounts")
                result['risk_score'] = 20
            else:
                result['risk_score'] = 0
            
            # Check device trust score
            trust_score = result['device_trust_score']
            if trust_score < 50:
                self.add_reason(f"Low device trust score: {trust_score}", 15)
                result['risk_score'] += 15
            elif trust_score < 70:
                self.add_warning(f"Moderate device trust score: {trust_score}")
                result['risk_score'] += 10
            
            result['risk_score'] = min(100, result['risk_score'])
            
            # Add evidence
            self.add_evidence('device_fingerprint_analysis', result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in device fingerprint check: {e}")
            return {'check': 'device_fingerprint', 'error': str(e), 'risk_score': 0}
    
    def _check_behavioral_patterns(self, user_id: int) -> Dict:
        """
        Check behavioral patterns for multi-account detection
        """
        try:
            user = User.objects.get(id=user_id)
            
            # Get user's activity patterns
            recent_activities = user.user_activities.all()[:100]
            
            # Analyze patterns
            pattern_analysis = {
                'check': 'behavioral_patterns',
                'total_activities': len(recent_activities),
                'activity_types': {},
                'time_patterns': {},
                'click_patterns': {}
            }
            
            if recent_activities:
                # Count activity types
                for activity in recent_activities:
                    activity_type = activity.activity_type
                    pattern_analysis['activity_types'][activity_type] = \
                        pattern_analysis['activity_types'].get(activity_type, 0) + 1
                
                # Check for robotic patterns
                is_robotic = self._detect_robotic_patterns(recent_activities)
                
                if is_robotic:
                    self.add_reason("Robotic behavior patterns detected", 20)
                    pattern_analysis['risk_score'] = 20
                    pattern_analysis['is_robotic'] = True
                else:
                    pattern_analysis['risk_score'] = 0
                    pattern_analysis['is_robotic'] = False
            
            else:
                pattern_analysis['risk_score'] = 5  # No activity is suspicious
                pattern_analysis['no_activity'] = True
            
            # Add evidence
            self.add_evidence('behavioral_pattern_analysis', pattern_analysis)
            
            return pattern_analysis
            
        except Exception as e:
            logger.error(f"Error in behavioral patterns check: {e}")
            return {'check': 'behavioral_patterns', 'error': str(e), 'risk_score': 0}
    
    def _check_registration_patterns(self, user_id: int) -> Dict:
        """
        Check registration patterns for fraud
        """
        try:
            user = User.objects.get(id=user_id)
            
            # Check registration time patterns
            registration_time = user.date_joined
            
            # Find registrations around same time
            time_window_start = registration_time - timedelta(minutes=5)
            time_window_end = registration_time + timedelta(minutes=5)
            
            similar_time_registrations = User.objects.filter(
                date_joined__range=[time_window_start, time_window_end]
            ).exclude(id=user_id).count()
            
            result = {
                'check': 'registration_patterns',
                'registration_time': registration_time.isoformat(),
                'similar_time_registrations': similar_time_registrations,
                'email_pattern': self._analyze_email_pattern(user.email),
                'username_pattern': self._analyze_username_pattern(user.username)
            }
            
            # Evaluate risk
            risk_score = 0
            
            if similar_time_registrations >= 3:
                self.add_reason(f"Multiple registrations at same time: {similar_time_registrations}", 25)
                risk_score += 25
            elif similar_time_registrations >= 1:
                self.add_warning(f"Registration time overlaps with {similar_time_registrations} other(s)")
                risk_score += 10
            
            # Check email pattern
            email_risk = result['email_pattern'].get('risk_score', 0)
            if email_risk >= 20:
                self.add_reason(f"Suspicious email pattern: {result['email_pattern']['reason']}", email_risk)
                risk_score += email_risk
            
            # Check username pattern
            username_risk = result['username_pattern'].get('risk_score', 0)
            if username_risk >= 15:
                self.add_reason(f"Suspicious username pattern: {result['username_pattern']['reason']}", username_risk)
                risk_score += username_risk
            
            result['risk_score'] = min(100, risk_score)
            
            # Add evidence
            self.add_evidence('registration_pattern_analysis', result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in registration patterns check: {e}")
            return {'check': 'registration_patterns', 'error': str(e), 'risk_score': 0}
    
    def _check_payment_patterns(self, user_id: int) -> Dict:
        """
        Check payment/transaction patterns
        """
        try:
            # Get user's transactions
            transactions = WalletTransaction.objects.filter(user_id=user_id)[:50]
            
            result = {
                'check': 'payment_patterns',
                'total_transactions': len(transactions),
                'transaction_types': {},
                'amount_patterns': {},
                'time_patterns': {}
            }
            
            if transactions:
                # Analyze transaction amounts
                amounts = [float(t.amount) for t in transactions]
                avg_amount = sum(amounts) / len(amounts) if amounts else 0
                
                # Check for round amounts (common in fraud)
                round_amounts = [amt for amt in amounts if amt % 10 == 0 or amt % 5 == 0]
                round_percentage = (len(round_amounts) / len(amounts)) * 100 if amounts else 0
                
                result['avg_amount'] = avg_amount
                result['round_percentage'] = round_percentage
                
                if round_percentage > 80:
                    self.add_reason(f"High percentage of round transaction amounts: {round_percentage:.1f}%", 15)
                    result['risk_score'] = 15
                else:
                    result['risk_score'] = 0
            else:
                result['risk_score'] = 0
            
            # Add evidence
            self.add_evidence('payment_pattern_analysis', result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in payment patterns check: {e}")
            return {'check': 'payment_patterns', 'error': str(e), 'risk_score': 0}
    
    def _check_referral_patterns(self, user_id: int) -> Dict:
        """
        Check referral patterns for fraud
        """
        try:
            from referral.models import Referral
            from offerwall.models import OfferCompletion
            
            # Get referral data
            referrals = Referral.objects.filter(referrer_id=user_id)
            
            result = {
                'check': 'referral_patterns',
                'total_referrals': referrals.count(),
                'successful_referrals': referrals.filter(status='completed').count(),
                'referral_conversion_rate': 0,
                'offer_completion_rate': 0
            }
            
            if referrals.exists():
                # Calculate conversion rate
                completed = referrals.filter(status='completed').count()
                conversion_rate = (completed / referrals.count()) * 100
                result['referral_conversion_rate'] = conversion_rate
                
                # Check for suspicious conversion rates
                if conversion_rate > 90:  # Unusually high
                    self.add_reason(f"Suspiciously high referral conversion rate: {conversion_rate:.1f}%", 20)
                    result['risk_score'] = 20
                elif conversion_rate > 70:
                    self.add_warning(f"High referral conversion rate: {conversion_rate:.1f}%")
                    result['risk_score'] = 10
                else:
                    result['risk_score'] = 0
                
                # Check offer completion pattern
                offer_completions = OfferCompletion.objects.filter(user_id=user_id)
                if offer_completions.exists():
                    completed_offers = offer_completions.filter(status='completed').count()
                    offer_rate = (completed_offers / offer_completions.count()) * 100
                    result['offer_completion_rate'] = offer_rate
                    
                    if offer_rate > 95:  # Unrealistically high
                        result['risk_score'] += 15
                        self.add_reason(f"Unrealistically high offer completion rate: {offer_rate:.1f}%", 15)
            else:
                result['risk_score'] = 0
            
            result['risk_score'] = min(100, result['risk_score'])
            
            # Add evidence
            self.add_evidence('referral_pattern_analysis', result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in referral patterns check: {e}")
            return {'check': 'referral_patterns', 'error': str(e), 'risk_score': 0}
    
    def _calculate_overall_score(self, checks: List[Dict]):
        """
        Calculate overall fraud score from all checks
        """
        risk_scores = [check.get('risk_score', 0) for check in checks]
        
        if risk_scores:
            # Weighted average
            weights = [1.2, 1.5, 1.0, 1.3, 0.8, 0.7]  # Different weights for different checks
            
            weighted_sum = 0
            total_weight = 0
            
            for i, score in enumerate(risk_scores[:len(weights)]):
                weight = weights[i]
                weighted_sum += score * weight
                total_weight += weight
            
            if total_weight > 0:
                self.fraud_score = int(weighted_sum / total_weight)
        
        # Adjust based on number of warnings/reasons
        if len(self.reasons) >= 3:
            self.fraud_score = min(100, self.fraud_score + 10)
        
        # Calculate confidence
        evidence_count = len([check for check in checks if 'error' not in check])
        self.confidence = self.calculate_confidence(evidence_count, 3)
    
    def _generate_device_hash(self, device_data: Dict) -> str:
        """
        Generate unique hash from device data
        """
        import json
        
        # Normalize device data
        normalized_data = {
            'user_agent': device_data.get('user_agent', ''),
            'platform': device_data.get('platform', ''),
            'browser': device_data.get('browser', ''),
            'screen_resolution': device_data.get('screen_resolution', ''),
            'timezone': device_data.get('timezone', ''),
            'language': device_data.get('language', ''),
            'canvas_hash': device_data.get('canvas_hash', ''),
            'webgl_hash': device_data.get('webgl_hash', '')
        }
        
        # Sort keys for consistent hashing
        sorted_data = json.dumps(normalized_data, sort_keys=True)
        
        # Generate SHA256 hash
        return hashlib.sha256(sorted_data.encode()).hexdigest()
    
    def _detect_robotic_patterns(self, activities) -> bool:
        """
        Detect robotic behavior patterns
        """
        if len(activities) < 10:
            return False
        
        # Check timing patterns
        timestamps = [act.timestamp for act in activities[:50]]
        
        # Calculate time differences
        time_diffs = []
        for i in range(1, len(timestamps)):
            diff = (timestamps[i] - timestamps[i-1]).total_seconds()
            time_diffs.append(diff)
        
        # Check if time differences are too consistent (robotic)
        if time_diffs:
            avg_diff = sum(time_diffs) / len(time_diffs)
            variance = sum((diff - avg_diff) ** 2 for diff in time_diffs) / len(time_diffs)
            
            # Low variance suggests robotic behavior
            return variance < 1.0  # Less than 1 second variance
        
        return False
    
    def _analyze_email_pattern(self, email: str) -> Dict:
        """
        Analyze email pattern for fraud indicators
        """
        result = {
            'email': email,
            'risk_score': 0,
            'reason': ''
        }
        
        # Check for disposable email domains
        disposable_domains = ['tempmail', 'mailinator', 'guerrillamail', 
                            '10minutemail', 'throwaway', 'fakeinbox']
        
        domain = email.split('@')[-1] if '@' in email else ''
        
        for disposable in disposable_domains:
            if disposable in domain.lower():
                result['risk_score'] = 30
                result['reason'] = 'Disposable email domain detected'
                return result
        
        # Check for pattern-based emails (common in bulk registrations)
        import re
        
        # Pattern: random characters + domain
        random_pattern = r'^[a-z0-9]{10,}@'
        if re.match(random_pattern, email.lower()):
            result['risk_score'] = 20
            result['reason'] = 'Random pattern email detected'
        
        # Check email length
        if len(email) > 50:
            result['risk_score'] = max(result['risk_score'], 15)
            result['reason'] = 'Unusually long email address'
        
        return result
    
    def _analyze_username_pattern(self, username: str) -> Dict:
        """
        Analyze username pattern for fraud indicators
        """
        result = {
            'username': username,
            'risk_score': 0,
            'reason': ''
        }
        
        import re
        
        # Check for sequential numbers
        if re.search(r'\d{5,}', username):
            result['risk_score'] = 25
            result['reason'] = 'Username contains long numeric sequence'
        
        # Check for repetitive patterns
        if re.search(r'(.)\1{3,}', username):
            result['risk_score'] = max(result['risk_score'], 20)
            result['reason'] = 'Username contains repetitive characters'
        
        # Check for common bot patterns
        bot_patterns = ['bot', 'auto', 'robot', 'test', 'demo', 'fake']
        for pattern in bot_patterns:
            if pattern in username.lower():
                result['risk_score'] = max(result['risk_score'], 30)
                result['reason'] = 'Username contains bot-like pattern'
        
        # Check username length
        if len(username) < 3:
            result['risk_score'] = max(result['risk_score'], 15)
            result['reason'] = 'Username too short'
        elif len(username) > 20:
            result['risk_score'] = max(result['risk_score'], 10)
            result['reason'] = 'Username unusually long'
        
        return result
    
    def get_detector_config(self) -> Dict:
        base_config = super().get_detector_config()
        base_config.update({
            'description': 'Detects multi-account fraud using device fingerprinting and behavioral analysis',
            'threshold_similarity': self.threshold_similarity,
            'max_accounts_per_ip': self.max_accounts_per_ip,
            'max_accounts_per_device': self.max_accounts_per_device,
            'version': '2.1.0'
        })
        return base_config