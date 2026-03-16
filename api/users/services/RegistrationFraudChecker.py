"""
Complete Registration Fraud Prevention System
Combines all fraud detection mechanisms for registration validation
"""
import logging
from typing import Dict, Tuple
from django.utils import timezone
from django.core.cache import cache
from .DeviceFingerprinting import DeviceFingerprinting
from .IPReputationChecker import IPReputationChecker
from .MultiAccountDetector import MultiAccountDetector

logger = logging.getLogger(__name__)


class RegistrationFraudChecker:
    """
    Complete fraud prevention system for user registration
    
    Performs comprehensive checks:
    1. Device fingerprinting and validation
    2. IP reputation and VPN/Proxy detection
    3. Multi-account detection
    4. Rate limiting
    5. Behavioral analysis
    6. Risk scoring
    """
    
    # Cache settings
    CACHE_PREFIX = 'reg_fraud:'
    CACHE_TIMEOUT = 3600
    
    # Fraud score thresholds
    FRAUD_SCORE_BLOCK = 80      # Block registration
    FRAUD_SCORE_REVIEW = 60     # Manual review required
    FRAUD_SCORE_MONITOR = 40    # Enhanced monitoring
    
    def __init__(self, strict_mode: bool = True, allow_vpn: bool = False):
        """
        Initialize registration fraud checker
        
        Args:
            strict_mode: If True, applies strictest fraud rules
            allow_vpn: If True, allows VPN usage (not recommended)
        """
        self.strict_mode = strict_mode
        self.allow_vpn = allow_vpn
        self.fraud_results = {
            'checks_performed': [],
            'violations': [],
            'warnings': [],
            'fraud_score': 0,
            'is_allowed': True,
            'block_reason': None,
        }
    
    def validate_registration(self, request, registration_data: Dict) -> Dict:
        """
        Complete registration validation with fraud detection
        
        Args:
            request: Django request object
            registration_data: Registration form data
        
        Returns:
            Validation results with fraud analysis
        """
        results = {
            'is_valid': True,
            'can_register': True,
            'fraud_score': 0,
            'risk_level': 'low',
            'block_reason': None,
            'warnings': [],
            'checks': {},
            'recommendations': [],
        }
        
        try:
            # Extract data
            email = registration_data.get('email', '')
            username = registration_data.get('username', '')
            
            # 1. Device Fingerprint Check
            device_check = self._check_device(request)
            results['checks']['device'] = device_check
            
            if not device_check['is_valid']:
                results['fraud_score'] += device_check.get('fraud_score', 40)
                
                if device_check.get('should_block', False):
                    results['can_register'] = False
                    results['block_reason'] = device_check.get('reason', 'Device validation failed')
                    return results
            
            # 2. IP Reputation Check
            ip_check = self._check_ip_reputation(request)
            results['checks']['ip'] = ip_check
            
            if not ip_check['is_valid']:
                results['fraud_score'] += ip_check.get('fraud_score', 30)
                
                if ip_check.get('should_block', False):
                    results['can_register'] = False
                    results['block_reason'] = ip_check.get('reason', 'IP validation failed')
                    return results
            
            # 3. Multi-Account Detection
            if device_check.get('device_hash'):
                multi_account_check = self._check_multi_account(
                    device_check['device_hash'],
                    ip_check.get('ip_address', ''),
                    email
                )
                results['checks']['multi_account'] = multi_account_check
                
                if multi_account_check['is_suspicious']:
                    results['fraud_score'] += multi_account_check.get('fraud_score', 35)
                    
                    if multi_account_check.get('should_block', False):
                        results['can_register'] = False
                        results['block_reason'] = multi_account_check.get('reason', 'Multi-account violation')
                        return results
            
            # 4. Rate Limiting Check
            rate_limit_check = self._check_rate_limits(request, email)
            results['checks']['rate_limit'] = rate_limit_check
            
            if not rate_limit_check['is_valid']:
                results['fraud_score'] += rate_limit_check.get('fraud_score', 20)
                
                if rate_limit_check.get('should_block', False):
                    results['can_register'] = False
                    results['block_reason'] = rate_limit_check.get('reason', 'Rate limit exceeded')
                    return results
            
            # 5. Email/Username Validation
            identity_check = self._check_identity(email, username)
            results['checks']['identity'] = identity_check
            
            if not identity_check['is_valid']:
                results['fraud_score'] += identity_check.get('fraud_score', 15)
                
                if identity_check.get('should_block', False):
                    results['can_register'] = False
                    results['block_reason'] = identity_check.get('reason', 'Identity validation failed')
                    return results
            
            # Calculate final fraud score
            results['fraud_score'] = min(results['fraud_score'], 100)
            
            # Determine risk level
            results['risk_level'] = self._calculate_risk_level(results['fraud_score'])
            
            # Determine if registration should be allowed
            if results['fraud_score'] >= self.FRAUD_SCORE_BLOCK:
                results['can_register'] = False
                results['block_reason'] = f"High fraud risk detected (Score: {results['fraud_score']}/100)"
            elif results['fraud_score'] >= self.FRAUD_SCORE_REVIEW:
                results['warnings'].append('Registration requires manual review')
                results['recommendations'].append('MANUAL_REVIEW')
            elif results['fraud_score'] >= self.FRAUD_SCORE_MONITOR:
                results['warnings'].append('Enhanced monitoring enabled')
                results['recommendations'].append('ENHANCED_MONITORING')
            
            # Compile warnings from all checks
            for check_name, check_data in results['checks'].items():
                if check_data.get('warnings'):
                    results['warnings'].extend(check_data['warnings'])
            
            logger.info(
                f"Registration validation completed: Score={results['fraud_score']}, "
                f"Risk={results['risk_level']}, Allowed={results['can_register']}"
            )
            
            return results
        
        except Exception as e:
            logger.error(f"Error in registration validation: {e}")
            
            # On error, fail safe - allow registration but flag for review
            return {
                'is_valid': True,
                'can_register': True,
                'fraud_score': 50,
                'risk_level': 'medium',
                'warnings': ['Fraud check encountered an error - flagged for review'],
                'recommendations': ['MANUAL_REVIEW'],
                'error': str(e)
            }
    
    def _check_device(self, request) -> Dict:
        """Check device fingerprint"""
        try:
            device_fp = DeviceFingerprinting()
            
            is_valid, reason, details = device_fp.validate_device_for_registration(
                request,
                strict_mode=self.strict_mode
            )
            
            result = {
                'is_valid': is_valid,
                'reason': reason,
                'device_hash': details.get('device_hash'),
                'fraud_score': 0,
                'should_block': False,
                'warnings': [],
            }
            
            if not is_valid:
                if reason == 'DEVICE_LIMIT_REACHED':
                    result['fraud_score'] = 50
                    result['should_block'] = True
                elif reason == 'LOW_TRUST_SCORE':
                    result['fraud_score'] = 40
                    result['should_block'] = self.strict_mode
                elif reason in ['VPN_PROXY_DETECTED', 'BOT_DETECTED']:
                    result['fraud_score'] = 45
                    result['should_block'] = True
                elif reason == 'REGISTRATION_RATE_EXCEEDED':
                    result['fraud_score'] = 35
                    result['should_block'] = True
            
            return result
        
        except Exception as e:
            logger.error(f"Device check error: {e}")
            return {
                'is_valid': True,
                'fraud_score': 20,
                'warnings': ['Device check failed'],
            }
    
    def _check_ip_reputation(self, request) -> Dict:
        """Check IP reputation"""
        try:
            # Get IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR', '')
            
            ip_checker = IPReputationChecker(ip_address)
            
            is_allowed, reason, details = ip_checker.check_ip_for_registration(
                ip_address,
                strict_mode=self.strict_mode
            )
            
            result = {
                'is_valid': is_allowed,
                'reason': reason,
                'ip_address': ip_address,
                'fraud_score': 0,
                'should_block': False,
                'warnings': [],
            }
            
            if not is_allowed:
                if reason == 'IP_BLACKLISTED':
                    result['fraud_score'] = 60
                    result['should_block'] = True
                elif reason == 'VPN_DETECTED':
                    result['fraud_score'] = 40 if not self.allow_vpn else 0
                    result['should_block'] = not self.allow_vpn
                elif reason == 'PROXY_DETECTED':
                    result['fraud_score'] = 45
                    result['should_block'] = True
                elif reason == 'TOR_DETECTED':
                    result['fraud_score'] = 50
                    result['should_block'] = True
                elif reason == 'HIGH_FRAUD_SCORE':
                    result['fraud_score'] = details.get('fraud_score', 50)
                    result['should_block'] = result['fraud_score'] >= 75
            
            return result
        
        except Exception as e:
            logger.error(f"IP check error: {e}")
            return {
                'is_valid': True,
                'fraud_score': 15,
                'warnings': ['IP check failed'],
            }
    
    def _check_multi_account(self, device_hash: str, ip_address: str, email: str) -> Dict:
        """Check for multi-account fraud"""
        try:
            detector = MultiAccountDetector()
            
            result = {
                'is_suspicious': False,
                'fraud_score': 0,
                'should_block': False,
                'violations': [],
                'warnings': [],
            }
            
            # Check device accounts
            device_suspicious, device_accounts, device_details = detector.check_device_accounts(device_hash)
            
            if device_suspicious:
                result['is_suspicious'] = True
                result['fraud_score'] += 40
                result['should_block'] = True
                result['violations'].append({
                    'type': 'DEVICE_SHARING',
                    'details': device_details
                })
            
            # Check IP accounts
            ip_suspicious, ip_accounts, ip_details = detector.check_ip_accounts(ip_address, timeframe_hours=24)
            
            if ip_suspicious:
                result['is_suspicious'] = True
                result['fraud_score'] += 25
                
                if ip_details.get('account_count', 0) > 10:
                    result['should_block'] = True
                
                result['violations'].append({
                    'type': 'IP_SHARING',
                    'details': ip_details
                })
            
            # Check email similarity
            email_suspicious, similar_emails, similarity = detector.check_email_similarity(email)
            
            if email_suspicious:
                result['is_suspicious'] = True
                result['fraud_score'] += 20
                result['warnings'].append(f'Found {len(similar_emails)} similar email patterns')
            
            return result
        
        except Exception as e:
            logger.error(f"Multi-account check error: {e}")
            return {
                'is_suspicious': False,
                'fraud_score': 10,
                'warnings': ['Multi-account check failed'],
            }
    
    def _check_rate_limits(self, request, email: str) -> Dict:
        """Check registration rate limits"""
        try:
            # Get IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR', '')
            
            result = {
                'is_valid': True,
                'fraud_score': 0,
                'should_block': False,
                'warnings': [],
            }
            
            # Check IP-based rate limit (registrations per hour)
            ip_cache_key = f"{self.CACHE_PREFIX}ip:{ip_address}"
            ip_count = cache.get(ip_cache_key, 0)
            
            if ip_count >= 5:  # Max 5 registrations per hour from same IP
                result['is_valid'] = False
                result['fraud_score'] = 30
                result['should_block'] = True
                result['reason'] = 'Too many registration attempts from this IP'
                return result
            
            # Check email-based rate limit (prevent email spam)
            email_cache_key = f"{self.CACHE_PREFIX}email:{email}"
            email_count = cache.get(email_cache_key, 0)
            
            if email_count >= 3:  # Max 3 attempts with same email
                result['is_valid'] = False
                result['fraud_score'] = 25
                result['should_block'] = True
                result['reason'] = 'Too many attempts with this email'
                return result
            
            # Increment counters
            cache.set(ip_cache_key, ip_count + 1, 3600)  # 1 hour
            cache.set(email_cache_key, email_count + 1, 3600)
            
            return result
        
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return {'is_valid': True, 'fraud_score': 0}
    
    def _check_identity(self, email: str, username: str) -> Dict:
        """Check email and username validity"""
        try:
            result = {
                'is_valid': True,
                'fraud_score': 0,
                'should_block': False,
                'warnings': [],
            }
            
            # Check disposable email domains
            disposable_domains = [
                'tempmail.com', 'guerrillamail.com', '10minutemail.com',
                'throwaway.email', 'maildrop.cc', 'mailinator.com'
            ]
            
            email_domain = email.split('@')[1].lower() if '@' in email else ''
            
            if email_domain in disposable_domains:
                result['is_valid'] = False
                result['fraud_score'] = 30
                result['should_block'] = self.strict_mode
                result['reason'] = 'Disposable email addresses are not allowed'
                result['warnings'].append('Disposable email detected')
            
            # Check username patterns
            if username:
                import re
                
                # Check for suspicious patterns
                if re.match(r'^[a-z]+\d+$', username.lower()):  # user123 pattern
                    result['warnings'].append('Suspicious username pattern')
                    result['fraud_score'] += 10
                
                # Check for very short usernames
                if len(username) < 3:
                    result['warnings'].append('Username too short')
                    result['fraud_score'] += 5
            
            return result
        
        except Exception as e:
            logger.error(f"Identity check error: {e}")
            return {'is_valid': True, 'fraud_score': 0}
    
    def _calculate_risk_level(self, fraud_score: int) -> str:
        """Calculate risk level from fraud score"""
        if fraud_score >= 80:
            return 'critical'
        elif fraud_score >= 60:
            return 'high'
        elif fraud_score >= 40:
            return 'medium'
        elif fraud_score >= 20:
            return 'low'
        else:
            return 'minimal'
    
    def save_fraud_check_record(self, user, validation_results: Dict) -> None:
        """
        Save fraud check record for audit trail
        
        Args:
            user: User instance
            validation_results: Results from validate_registration
        """
        try:
            from api.fraud_detection.models import FraudAttempt
            
            # Only save if suspicious
            if validation_results['fraud_score'] >= 40:
                FraudAttempt.objects.create(
                    user=user,
                    attempt_type='multi_account',  # or determine based on violations
                    description=f"Registration fraud check: Score {validation_results['fraud_score']}",
                    detected_by='RegistrationFraudChecker',
                    fraud_score=validation_results['fraud_score'],
                    confidence_score=85,
                    evidence_data={
                        'checks': validation_results.get('checks', {}),
                        'warnings': validation_results.get('warnings', []),
                        'risk_level': validation_results.get('risk_level', 'unknown'),
                    },
                    status='detected' if validation_results['can_register'] else 'confirmed'
                )
                
                logger.info(f"Fraud check record saved for user {user.id}")
        
        except Exception as e:
            logger.error(f"Error saving fraud check record: {e}")
    
    def get_registration_summary(self, validation_results: Dict) -> str:
        """
        Generate human-readable summary
        
        Args:
            validation_results: Validation results
        
        Returns:
            Summary string
        """
        lines = []
        lines.append("="*60)
        lines.append("REGISTRATION FRAUD CHECK SUMMARY")
        lines.append("="*60)
        lines.append(f"Fraud Score: {validation_results['fraud_score']}/100")
        lines.append(f"Risk Level: {validation_results['risk_level'].upper()}")
        lines.append(f"Registration Allowed: {'YES' if validation_results['can_register'] else 'NO'}")
        
        if validation_results.get('block_reason'):
            lines.append(f"Block Reason: {validation_results['block_reason']}")
        
        if validation_results.get('warnings'):
            lines.append("\nWarnings:")
            for warning in validation_results['warnings']:
                lines.append(f"  - {warning}")
        
        if validation_results.get('recommendations'):
            lines.append("\nRecommendations:")
            for rec in validation_results['recommendations']:
                lines.append(f"  - {rec}")
        
        lines.append("="*60)
        
        return "\n".join(lines)