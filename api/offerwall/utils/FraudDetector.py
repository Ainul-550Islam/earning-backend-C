"""
Fraud detection utility for offers
"""
import logging
from django.utils import timezone
from django.db.models import Count, Sum, Q
from datetime import timedelta
from decimal import Decimal
from ..constants import *
from ..exceptions import *

logger = logging.getLogger(__name__)


class FraudDetector:
    """Fraud detection for offer completions"""
    
    def __init__(self, user=None, offer=None):
        self.user = user
        self.offer = offer
        self.fraud_indicators = []
        self.fraud_score = 0
    
    def analyze_click_pattern(self, click_data):
        """
        Analyze click patterns for fraud
        
        Args:
            click_data: Dictionary with click information
        
        Returns:
            dict: Analysis results
        """
        score = 0
        indicators = []
        
        from ..models import OfferClick
        
        # Check click frequency
        recent_clicks = OfferClick.objects.filter(
            user=self.user,
            clicked_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if recent_clicks > MAX_OFFER_CLICKS_PER_HOUR:
            score += 30
            indicators.append('excessive_click_frequency')
        
        # Check for rapid consecutive clicks
        last_clicks = OfferClick.objects.filter(
            user=self.user,
            offer=self.offer
        ).order_by('-clicked_at')[:5]
        
        if last_clicks.count() >= 3:
            time_diffs = []
            for i in range(len(last_clicks) - 1):
                diff = (last_clicks[i].clicked_at - last_clicks[i+1].clicked_at).total_seconds()
                time_diffs.append(diff)
            
            # If clicks are within 2 seconds of each other
            if time_diffs and all(d < 2 for d in time_diffs):
                score += 40
                indicators.append('rapid_consecutive_clicks')
        
        # Check for multiple clicks from same IP
        if click_data.get('ip_address'):
            ip_clicks = OfferClick.objects.filter(
                ip_address=click_data['ip_address'],
                clicked_at__gte=timezone.now() - timedelta(hours=24)
            ).values('user').distinct().count()
            
            if ip_clicks > 10:
                score += 25
                indicators.append('multiple_users_same_ip')
        
        return {
            'score': score,
            'indicators': indicators,
            'is_suspicious': score >= FRAUD_THRESHOLD_MEDIUM
        }
    
    def analyze_device_fingerprint(self, device_data):
        """
        Analyze device fingerprint for anomalies
        
        Args:
            device_data: Dictionary with device information
        
        Returns:
            dict: Analysis results
        """
        score = 0
        indicators = []
        
        from api.fraud_detection.models import DeviceFingerprint
        
        if not device_data:
            return {'score': 0, 'indicators': [], 'is_suspicious': False}
        
        # Check for VPN/Proxy
        if device_data.get('is_vpn') or device_data.get('is_proxy'):
            score += 50
            indicators.append('vpn_or_proxy_detected')
        
        # Check for bot
        if device_data.get('is_bot'):
            score += 70
            indicators.append('bot_detected')
        
        # Check for device spoofing
        device_hash = device_data.get('device_hash')
        if device_hash:
            # Check if same device used by multiple users
            device_users = DeviceFingerprint.objects.filter(
                device_hash=device_hash
            ).values('user').distinct().count()
            
            if device_users > 5:
                score += 40
                indicators.append('device_shared_multiple_users')
        
        # Check trust score
        trust_score = device_data.get('trust_score', 100)
        if trust_score < 50:
            score += 30
            indicators.append('low_device_trust_score')
        
        return {
            'score': score,
            'indicators': indicators,
            'is_suspicious': score >= FRAUD_THRESHOLD_MEDIUM
        }
    
    def analyze_completion_time(self, completion_time_seconds):
        """
        Analyze completion time for suspicious patterns
        
        Args:
            completion_time_seconds: Time taken to complete offer
        
        Returns:
            dict: Analysis results
        """
        score = 0
        indicators = []
        
        if not self.offer or not completion_time_seconds:
            return {'score': 0, 'indicators': [], 'is_suspicious': False}
        
        estimated_time = self.offer.estimated_time_minutes * 60
        
        # Too fast completion
        if completion_time_seconds < (estimated_time * 0.1):  # Less than 10% of estimated time
            score += 60
            indicators.append('suspiciously_fast_completion')
        elif completion_time_seconds < (estimated_time * 0.3):  # Less than 30%
            score += 30
            indicators.append('very_fast_completion')
        
        # Unrealistically long completion
        if completion_time_seconds > (estimated_time * 10):  # More than 10x estimated
            score += 20
            indicators.append('suspiciously_long_completion')
        
        return {
            'score': score,
            'indicators': indicators,
            'is_suspicious': score >= FRAUD_THRESHOLD_MEDIUM
        }
    
    def analyze_user_behavior(self):
        """
        Analyze user's overall behavior patterns
        
        Returns:
            dict: Analysis results
        """
        score = 0
        indicators = []
        
        from ..models import OfferConversion
        from api.fraud_detection.models import UserRiskProfile, FraudAttempt
        
        # Check user risk profile
        try:
            risk_profile = UserRiskProfile.objects.get(user=self.user)
            
            if risk_profile.overall_risk_score > FRAUD_THRESHOLD_HIGH:
                score += 50
                indicators.append('high_risk_user')
            elif risk_profile.overall_risk_score > FRAUD_THRESHOLD_MEDIUM:
                score += 25
                indicators.append('medium_risk_user')
            
            if risk_profile.is_flagged:
                score += 30
                indicators.append('user_flagged')
            
            if risk_profile.is_restricted:
                score += 40
                indicators.append('user_restricted')
        
        except UserRiskProfile.DoesNotExist:
            pass
        
        # Check for previous fraud attempts
        fraud_attempts = FraudAttempt.objects.filter(
            user=self.user,
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        if fraud_attempts > 0:
            score += min(fraud_attempts * 15, 60)
            indicators.append(f'recent_fraud_attempts_{fraud_attempts}')
        
        # Check completion patterns
        today_completions = OfferConversion.objects.filter(
            user=self.user,
            converted_at__date=timezone.now().date()
        ).count()
        
        if today_completions > MAX_USER_COMPLETIONS_PER_DAY:
            score += 35
            indicators.append('excessive_daily_completions')
        
        # Check for multiple rejections
        rejections = OfferConversion.objects.filter(
            user=self.user,
            status=CONVERSION_REJECTED,
            converted_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        if rejections > 5:
            score += 30
            indicators.append('multiple_rejections')
        
        return {
            'score': score,
            'indicators': indicators,
            'is_suspicious': score >= FRAUD_THRESHOLD_MEDIUM
        }
    
    def analyze_multi_account(self):
        """
        Detect potential multi-account fraud
        
        Returns:
            dict: Analysis results
        """
        score = 0
        indicators = []
        
        from api.fraud_detection.models import DeviceFingerprint, IPReputation
        from api.users.models import User
        
        # Check for shared devices
        user_devices = DeviceFingerprint.objects.filter(user=self.user)
        
        for device in user_devices:
            shared_users = DeviceFingerprint.objects.filter(
                device_hash=device.device_hash
            ).exclude(user=self.user).values('user').distinct().count()
            
            if shared_users > 0:
                score += min(shared_users * 20, 60)
                indicators.append(f'device_shared_with_{shared_users}_users')
                break
        
        # Check for shared IP addresses
        user_ips = user_devices.values_list('ip_address', flat=True).distinct()
        
        for ip in user_ips:
            users_on_ip = DeviceFingerprint.objects.filter(
                ip_address=ip,
                last_seen__gte=timezone.now() - timedelta(days=7)
            ).values('user').distinct().count()
            
            if users_on_ip > 3:
                score += 30
                indicators.append(f'ip_shared_with_{users_on_ip}_users')
                break
        
        return {
            'score': score,
            'indicators': indicators,
            'is_suspicious': score >= FRAUD_THRESHOLD_MEDIUM
        }
    
    def analyze_conversion_patterns(self):
        """
        Analyze conversion patterns across offers
        
        Returns:
            dict: Analysis results
        """
        score = 0
        indicators = []
        
        from ..models import OfferConversion
        
        # Check for same-offer multiple conversions
        if self.offer:
            same_offer_conversions = OfferConversion.objects.filter(
                user=self.user,
                offer=self.offer
            ).count()
            
            if same_offer_conversions > self.offer.user_limit:
                score += 70
                indicators.append('exceeded_offer_limit')
        
        # Check for suspicious conversion timing
        recent_conversions = OfferConversion.objects.filter(
            user=self.user,
            converted_at__gte=timezone.now() - timedelta(hours=1)
        ).order_by('converted_at')
        
        if recent_conversions.count() > 10:
            score += 40
            indicators.append('too_many_recent_conversions')
        
        # Check for pattern matching (all conversions at similar times)
        if recent_conversions.count() >= 5:
            times = [c.converted_at.hour for c in recent_conversions]
            if len(set(times)) <= 2:  # All at same 1-2 hours
                score += 25
                indicators.append('suspicious_time_pattern')
        
        return {
            'score': score,
            'indicators': indicators,
            'is_suspicious': score >= FRAUD_THRESHOLD_MEDIUM
        }
    
    def comprehensive_fraud_check(self, click_data=None, device_data=None, completion_time=None):
        """
        Perform comprehensive fraud detection
        
        Args:
            click_data: Click information
            device_data: Device information
            completion_time: Completion time in seconds
        
        Returns:
            dict: Complete fraud analysis
        """
        analyses = {}
        total_score = 0
        all_indicators = []
        
        # Run all checks
        if click_data:
            click_analysis = self.analyze_click_pattern(click_data)
            analyses['click_pattern'] = click_analysis
            total_score += click_analysis['score']
            all_indicators.extend(click_analysis['indicators'])
        
        if device_data:
            device_analysis = self.analyze_device_fingerprint(device_data)
            analyses['device'] = device_analysis
            total_score += device_analysis['score']
            all_indicators.extend(device_analysis['indicators'])
        
        if completion_time:
            time_analysis = self.analyze_completion_time(completion_time)
            analyses['completion_time'] = time_analysis
            total_score += time_analysis['score']
            all_indicators.extend(time_analysis['indicators'])
        
        behavior_analysis = self.analyze_user_behavior()
        analyses['user_behavior'] = behavior_analysis
        total_score += behavior_analysis['score']
        all_indicators.extend(behavior_analysis['indicators'])
        
        multi_account_analysis = self.analyze_multi_account()
        analyses['multi_account'] = multi_account_analysis
        total_score += multi_account_analysis['score']
        all_indicators.extend(multi_account_analysis['indicators'])
        
        conversion_analysis = self.analyze_conversion_patterns()
        analyses['conversion_pattern'] = conversion_analysis
        total_score += conversion_analysis['score']
        all_indicators.extend(conversion_analysis['indicators'])
        
        # Normalize score to 0-100
        normalized_score = min(100, total_score)
        
        # Determine fraud level
        if normalized_score >= FRAUD_THRESHOLD_HIGH:
            fraud_level = 'high'
            should_block = True
        elif normalized_score >= FRAUD_THRESHOLD_MEDIUM:
            fraud_level = 'medium'
            should_block = False  # Review manually
        elif normalized_score >= FRAUD_THRESHOLD_LOW:
            fraud_level = 'low'
            should_block = False
        else:
            fraud_level = 'none'
            should_block = False
        
        result = {
            'fraud_score': normalized_score,
            'fraud_level': fraud_level,
            'should_block': should_block,
            'indicators': list(set(all_indicators)),
            'analyses': analyses,
            'recommendation': self._get_recommendation(normalized_score)
        }
        
        # Log if suspicious
        if normalized_score >= FRAUD_THRESHOLD_MEDIUM:
            logger.warning(
                f"Suspicious activity detected for user {self.user.id}: "
                f"Score {normalized_score}, Indicators: {all_indicators}"
            )
        
        return result
    
    def _get_recommendation(self, score):
        """Get recommendation based on fraud score"""
        if score >= FRAUD_THRESHOLD_HIGH:
            return 'block_and_flag'
        elif score >= FRAUD_THRESHOLD_MEDIUM:
            return 'manual_review'
        elif score >= FRAUD_THRESHOLD_LOW:
            return 'monitor_closely'
        else:
            return 'approve'
    
    def create_fraud_attempt_record(self, fraud_analysis):
        """
        Create fraud attempt record if suspicious
        
        Args:
            fraud_analysis: Result from comprehensive_fraud_check
        
        Returns:
            FraudAttempt instance or None
        """
        from api.fraud_detection.models import FraudAttempt
        
        if fraud_analysis['fraud_score'] < FRAUD_THRESHOLD_MEDIUM:
            return None
        
        # Determine attempt type based on indicators
        indicators = fraud_analysis['indicators']
        
        if 'bot_detected' in indicators:
            attempt_type = 'device_spoofing'
        elif 'vpn_or_proxy_detected' in indicators:
            attempt_type = 'vpn_proxy'
        elif any('multi' in i or 'shared' in i for i in indicators):
            attempt_type = 'multi_account'
        elif 'click' in ' '.join(indicators):
            attempt_type = 'click_fraud'
        else:
            attempt_type = 'offer_abuse'
        
        fraud_attempt = FraudAttempt.objects.create(
            user=self.user,
            attempt_type=attempt_type,
            description=f"Suspicious offer activity detected: {', '.join(indicators[:3])}",
            detected_by='OfferFraudDetector',
            fraud_score=int(fraud_analysis['fraud_score']),
            confidence_score=80,
            evidence_data={
                'indicators': indicators,
                'analyses': fraud_analysis['analyses'],
                'offer_id': str(self.offer.id) if self.offer else None,
            }
        )
        
        logger.info(f"Created fraud attempt record: {fraud_attempt.attempt_id}")
        
        return fraud_attempt
    
    @staticmethod
    def check_ip_reputation(ip_address):
        """
        Check IP reputation
        
        Args:
            ip_address: IP address to check
        
        Returns:
            dict: IP reputation info
        """
        from api.fraud_detection.models import IPReputation
        
        try:
            ip_rep = IPReputation.objects.get(ip_address=ip_address)
            
            return {
                'is_blacklisted': ip_rep.is_blacklisted,
                'fraud_score': ip_rep.fraud_score,
                'spam_score': ip_rep.spam_score,
                'threat_types': ip_rep.threat_types,
            }
        
        except IPReputation.DoesNotExist:
            return {
                'is_blacklisted': False,
                'fraud_score': 0,
                'spam_score': 0,
                'threat_types': [],
            }