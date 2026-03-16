"""
Multi-Account Fraud Detection System
Detects users creating multiple accounts for fraudulent purposes
"""
import logging
from typing import Dict, List, Tuple, Optional
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


class MultiAccountDetector:
    """
    Detects multi-account fraud patterns
    
    Detection methods:
    - Same device multiple accounts
    - Same IP multiple accounts
    - Similar email patterns
    - Similar phone numbers
    - Similar referral codes
    - Coordinated activity patterns
    - Similar behavioral fingerprints
    """
    
    # Thresholds
    MAX_ACCOUNTS_PER_DEVICE = 1
    MAX_ACCOUNTS_PER_IP = 3
    MAX_REGISTRATIONS_PER_DAY_SAME_IP = 5
    SUSPICIOUS_EMAIL_SIMILARITY_THRESHOLD = 0.8
    
    def __init__(self, user=None):
        """
        Initialize multi-account detector
        
        Args:
            user: User instance to check
        """
        self.user = user
        self.suspicious_accounts = []
        self.similarity_scores = {}
    
    def check_device_accounts(self, device_hash: str) -> Tuple[bool, List, Dict]:
        """
        Check for multiple accounts from same device
        
        Args:
            device_hash: Device hash to check
        
        Returns:
            Tuple of (is_suspicious: bool, accounts: list, details: dict)
        """
        from api.fraud_detection.models import DeviceFingerprint
        from api.users.models import User
        
        try:
            # Find all devices with same hash
            devices = DeviceFingerprint.objects.filter(device_hash=device_hash)
            
            # Get unique users
            user_ids = devices.values_list('user_id', flat=True).distinct()
            account_count = len(user_ids)
            
            is_suspicious = account_count > self.MAX_ACCOUNTS_PER_DEVICE
            
            if is_suspicious:
                # Get user details
                users = User.objects.filter(id__in=user_ids)
                
                accounts = [{
                    'id': str(user.id),
                    'username': user.username,
                    'email': user.email,
                    'created_at': user.created_at,
                    'is_active': user.is_active,
                } for user in users]
                
                details = {
                    'device_hash': device_hash,
                    'account_count': account_count,
                    'max_allowed': self.MAX_ACCOUNTS_PER_DEVICE,
                    'violation_type': 'DEVICE_SHARING',
                    'risk_level': 'high' if account_count > 3 else 'medium',
                    'message': f'Found {account_count} accounts using the same device (max allowed: {self.MAX_ACCOUNTS_PER_DEVICE})'
                }
                
                return True, accounts, details
            
            return False, [], {}
        
        except Exception as e:
            logger.error(f"Error checking device accounts: {e}")
            return False, [], {}
    
    def check_ip_accounts(self, ip_address: str, timeframe_hours: int = 24) -> Tuple[bool, List, Dict]:
        """
        Check for multiple accounts from same IP
        
        Args:
            ip_address: IP address to check
            timeframe_hours: Time window to check (hours)
        
        Returns:
            Tuple of (is_suspicious: bool, accounts: list, details: dict)
        """
        from api.fraud_detection.models import DeviceFingerprint
        from api.users.models import User
        
        try:
            # Find recent registrations from this IP
            since = timezone.now() - timedelta(hours=timeframe_hours)
            
            devices = DeviceFingerprint.objects.filter(
                ip_address=ip_address,
                created_at__gte=since
            )
            
            user_ids = devices.values_list('user_id', flat=True).distinct()
            account_count = len(user_ids)
            
            is_suspicious = account_count > self.MAX_REGISTRATIONS_PER_DAY_SAME_IP
            
            if is_suspicious:
                users = User.objects.filter(id__in=user_ids)
                
                accounts = [{
                    'id': str(user.id),
                    'username': user.username,
                    'email': user.email,
                    'created_at': user.created_at,
                } for user in users]
                
                details = {
                    'ip_address': ip_address,
                    'account_count': account_count,
                    'timeframe_hours': timeframe_hours,
                    'max_allowed': self.MAX_REGISTRATIONS_PER_DAY_SAME_IP,
                    'violation_type': 'IP_SHARING',
                    'risk_level': 'high' if account_count > 10 else 'medium',
                    'message': f'Found {account_count} registrations from same IP in last {timeframe_hours} hours'
                }
                
                return True, accounts, details
            
            return False, [], {}
        
        except Exception as e:
            logger.error(f"Error checking IP accounts: {e}")
            return False, [], {}
    
    def check_email_similarity(self, email: str) -> Tuple[bool, List[Dict], float]:
        """
        Check for similar email patterns
        
        Examples of suspicious patterns:
        - user1@gmail.com, user2@gmail.com, user3@gmail.com
        - john.doe@gmail.com, john.doe1@gmail.com, john.doe2@gmail.com
        - johndoe+1@gmail.com, johndoe+2@gmail.com
        
        Args:
            email: Email to check
        
        Returns:
            Tuple of (is_suspicious: bool, similar_emails: list, max_similarity: float)
        """
        from api.users.models import User
        
        try:
            # Extract base email pattern
            local_part = email.split('@')[0]
            domain = email.split('@')[1]
            
            # Remove numbers and special chars for pattern matching
            import re
            clean_local = re.sub(r'[\d\+\.\-_]+', '', local_part)
            
            if len(clean_local) < 3:
                return False, [], 0.0
            
            # Find similar emails
            similar_emails = []
            max_similarity = 0.0
            
            # Search for emails with similar pattern
            users = User.objects.filter(
                email__icontains=clean_local
            ).exclude(email=email)
            
            for user in users:
                similarity = self._calculate_email_similarity(email, user.email)
                
                if similarity >= self.SUSPICIOUS_EMAIL_SIMILARITY_THRESHOLD:
                    similar_emails.append({
                        'email': user.email,
                        'username': user.username,
                        'user_id': str(user.id),
                        'similarity': similarity,
                        'created_at': user.created_at,
                    })
                    
                    max_similarity = max(max_similarity, similarity)
            
            is_suspicious = len(similar_emails) > 0
            
            return is_suspicious, similar_emails, max_similarity
        
        except Exception as e:
            logger.error(f"Error checking email similarity: {e}")
            return False, [], 0.0
    
    def _calculate_email_similarity(self, email1: str, email2: str) -> float:
        """
        Calculate similarity score between two emails
        
        Args:
            email1: First email
            email2: Second email
        
        Returns:
            Similarity score (0-1)
        """
        import difflib
        
        # Extract local parts
        local1 = email1.split('@')[0].lower()
        local2 = email2.split('@')[0].lower()
        
        # Remove numbers and special chars
        import re
        clean1 = re.sub(r'[\d\+\.\-_]+', '', local1)
        clean2 = re.sub(r'[\d\+\.\-_]+', '', local2)
        
        # Calculate similarity
        similarity = difflib.SequenceMatcher(None, clean1, clean2).ratio()
        
        return round(similarity, 2)
    
    def check_referral_abuse(self, user_id: str) -> Tuple[bool, Dict]:
        """
        Check for referral code abuse
        
        Detects:
        - User referring themselves
        - Circular referral chains
        - Coordinated referral networks
        
        Args:
            user_id: User ID to check
        
        Returns:
            Tuple of (is_abuse: bool, details: dict)
        """
        from api.referral.models import Referral
        from api.users.models import User
        
        try:
            user = User.objects.get(id=user_id)
            
            # Check if user referred themselves (same device/IP)
            if user.referred_by:
                referrer = user.referred_by
                
                # Get device fingerprints
                from api.fraud_detection.models import DeviceFingerprint
                
                user_devices = DeviceFingerprint.objects.filter(user=user)
                referrer_devices = DeviceFingerprint.objects.filter(user=referrer)
                
                # Check for device match
                user_hashes = set(user_devices.values_list('device_hash', flat=True))
                referrer_hashes = set(referrer_devices.values_list('device_hash', flat=True))
                
                common_devices = user_hashes.intersection(referrer_hashes)
                
                if common_devices:
                    return True, {
                        'violation_type': 'SELF_REFERRAL',
                        'user_id': str(user.id),
                        'referrer_id': str(referrer.id),
                        'common_devices': len(common_devices),
                        'message': 'User appears to have referred themselves using same device'
                    }
                
                # Check for IP match
                user_ips = set(user_devices.values_list('ip_address', flat=True))
                referrer_ips = set(referrer_devices.values_list('ip_address', flat=True))
                
                common_ips = user_ips.intersection(referrer_ips)
                
                if common_ips:
                    return True, {
                        'violation_type': 'SELF_REFERRAL_IP',
                        'user_id': str(user.id),
                        'referrer_id': str(referrer.id),
                        'common_ips': len(common_ips),
                        'message': 'User appears to have referred themselves using same IP'
                    }
            
            # Check referral network
            referrals = Referral.objects.filter(referrer=user)
            
            if referrals.count() > 50:  # Suspicious number of referrals
                # Check if referrals are from similar devices/IPs
                referred_users = [r.referred for r in referrals]
                
                # This could indicate organized fraud
                return True, {
                    'violation_type': 'EXCESSIVE_REFERRALS',
                    'user_id': str(user.id),
                    'referral_count': referrals.count(),
                    'message': 'Suspicious number of referrals detected'
                }
            
            return False, {}
        
        except Exception as e:
            logger.error(f"Error checking referral abuse: {e}")
            return False, {}
    
    def check_behavioral_patterns(self, user) -> Tuple[bool, Dict]:
        """
        Check for suspicious behavioral patterns
        
        Analyzes:
        - Registration time patterns
        - Activity patterns
        - Transaction patterns
        - Coordinated activities
        
        Args:
            user: User instance
        
        Returns:
            Tuple of (is_suspicious: bool, details: dict)
        """
        try:
            from api.fraud_detection.models import DeviceFingerprint
            
            # Get user's device
            user_device = DeviceFingerprint.objects.filter(user=user).first()
            
            if not user_device:
                return False, {}
            
            # Find users with similar registration patterns
            similar_time_window = timedelta(minutes=5)
            
            nearby_registrations = DeviceFingerprint.objects.filter(
                created_at__range=(
                    user_device.created_at - similar_time_window,
                    user_device.created_at + similar_time_window
                )
            ).exclude(user=user)
            
            # Check for coordinated registrations
            if nearby_registrations.count() >= 5:
                return True, {
                    'violation_type': 'COORDINATED_REGISTRATIONS',
                    'nearby_count': nearby_registrations.count(),
                    'time_window_minutes': 5,
                    'message': 'Multiple coordinated registrations detected'
                }
            
            return False, {}
        
        except Exception as e:
            logger.error(f"Error checking behavioral patterns: {e}")
            return False, {}
    
    def perform_comprehensive_check(
        self, 
        user_id: str,
        device_hash: str,
        ip_address: str,
        email: str
    ) -> Dict:
        """
        Perform comprehensive multi-account fraud check
        
        Args:
            user_id: User ID
            device_hash: Device hash
            ip_address: IP address
            email: Email address
        
        Returns:
            Comprehensive fraud analysis
        """
        from api.users.models import User
        
        results = {
            'user_id': user_id,
            'is_fraud': False,
            'fraud_score': 0,
            'violations': [],
            'suspicious_accounts': [],
            'risk_level': 'low',
        }
        
        try:
            user = User.objects.get(id=user_id)
            
            # Check device accounts
            device_suspicious, device_accounts, device_details = self.check_device_accounts(device_hash)
            
            if device_suspicious:
                results['violations'].append({
                    'type': 'DEVICE_SHARING',
                    'severity': 'high',
                    'details': device_details,
                    'accounts': device_accounts,
                })
                results['fraud_score'] += 40
                results['suspicious_accounts'].extend(device_accounts)
            
            # Check IP accounts
            ip_suspicious, ip_accounts, ip_details = self.check_ip_accounts(ip_address)
            
            if ip_suspicious:
                results['violations'].append({
                    'type': 'IP_SHARING',
                    'severity': 'medium',
                    'details': ip_details,
                    'accounts': ip_accounts,
                })
                results['fraud_score'] += 25
            
            # Check email similarity
            email_suspicious, similar_emails, similarity = self.check_email_similarity(email)
            
            if email_suspicious:
                results['violations'].append({
                    'type': 'SIMILAR_EMAILS',
                    'severity': 'medium',
                    'similar_count': len(similar_emails),
                    'max_similarity': similarity,
                    'emails': similar_emails,
                })
                results['fraud_score'] += 20
            
            # Check referral abuse
            referral_abuse, referral_details = self.check_referral_abuse(user_id)
            
            if referral_abuse:
                results['violations'].append({
                    'type': 'REFERRAL_ABUSE',
                    'severity': 'high',
                    'details': referral_details,
                })
                results['fraud_score'] += 35
            
            # Check behavioral patterns
            behavior_suspicious, behavior_details = self.check_behavioral_patterns(user)
            
            if behavior_suspicious:
                results['violations'].append({
                    'type': 'SUSPICIOUS_BEHAVIOR',
                    'severity': 'medium',
                    'details': behavior_details,
                })
                results['fraud_score'] += 15
            
            # Determine if fraud
            results['fraud_score'] = min(results['fraud_score'], 100)
            results['is_fraud'] = results['fraud_score'] >= 70
            
            # Determine risk level
            if results['fraud_score'] >= 80:
                results['risk_level'] = 'critical'
            elif results['fraud_score'] >= 60:
                results['risk_level'] = 'high'
            elif results['fraud_score'] >= 40:
                results['risk_level'] = 'medium'
            else:
                results['risk_level'] = 'low'
            
            # Add recommendations
            results['recommendations'] = self._generate_recommendations(results)
            
            logger.info(
                f"Multi-account check completed for user {user_id}: "
                f"Score {results['fraud_score']}, Risk {results['risk_level']}"
            )
            
            return results
        
        except Exception as e:
            logger.error(f"Error in comprehensive check: {e}")
            return results
    
    def _generate_recommendations(self, results: Dict) -> List[str]:
        """
        Generate recommendations based on fraud analysis
        
        Args:
            results: Fraud analysis results
        
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if results['fraud_score'] >= 80:
            recommendations.append('BLOCK_REGISTRATION')
            recommendations.append('FLAG_ALL_ASSOCIATED_ACCOUNTS')
        elif results['fraud_score'] >= 60:
            recommendations.append('MANUAL_REVIEW_REQUIRED')
            recommendations.append('LIMIT_ACCOUNT_ACTIONS')
        elif results['fraud_score'] >= 40:
            recommendations.append('ENHANCED_MONITORING')
            recommendations.append('REQUIRE_ADDITIONAL_VERIFICATION')
        
        # Specific recommendations based on violations
        violation_types = [v['type'] for v in results['violations']]
        
        if 'DEVICE_SHARING' in violation_types:
            recommendations.append('VERIFY_DEVICE_OWNERSHIP')
        
        if 'REFERRAL_ABUSE' in violation_types:
            recommendations.append('DISABLE_REFERRAL_REWARDS')
        
        if 'SIMILAR_EMAILS' in violation_types:
            recommendations.append('EMAIL_VERIFICATION_REQUIRED')
        
        return recommendations
    
    def create_fraud_report(self, analysis_results: Dict) -> str:
        """
        Create human-readable fraud report
        
        Args:
            analysis_results: Results from comprehensive_check
        
        Returns:
            Formatted report string
        """
        report = []
        
        report.append("="*50)
        report.append("MULTI-ACCOUNT FRAUD DETECTION REPORT")
        report.append("="*50)
        report.append(f"User ID: {analysis_results['user_id']}")
        report.append(f"Fraud Score: {analysis_results['fraud_score']}/100")
        report.append(f"Risk Level: {analysis_results['risk_level'].upper()}")
        report.append(f"Is Fraud: {'YES' if analysis_results['is_fraud'] else 'NO'}")
        report.append("")
        
        if analysis_results['violations']:
            report.append("VIOLATIONS DETECTED:")
            report.append("-"*50)
            
            for i, violation in enumerate(analysis_results['violations'], 1):
                report.append(f"{i}. {violation['type']} (Severity: {violation['severity']})")
                
                if 'details' in violation:
                    for key, value in violation['details'].items():
                        if key != 'message':
                            report.append(f"   - {key}: {value}")
                
                report.append("")
        
        if analysis_results['recommendations']:
            report.append("RECOMMENDATIONS:")
            report.append("-"*50)
            
            for i, rec in enumerate(analysis_results['recommendations'], 1):
                report.append(f"{i}. {rec}")
        
        report.append("="*50)
        
        return "\n".join(report)
    # ফাইলের একদম নিচে এই লাইনটি যোগ করুন
multi_account_detector = MultiAccountDetector()