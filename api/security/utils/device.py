import requests
import logging
from datetime import timedelta
from typing import Optional, Dict, Any, List, Tuple, Callable
from django.utils import timezone
from django.conf import settings
from django.http import HttpRequest
from api.security.models import DeviceInfo, ClickTracker, SecurityLog, WithdrawalProtection
import functools

logger = logging.getLogger(__name__)

# ==================== HELPER FUNCTIONS ====================

def get_client_ip(request: HttpRequest) -> str:
    """
    Defensive function to get client IP with null object pattern
    """
    try:
        if not request or not hasattr(request, 'META'):
            logger.warning("Invalid request object provided to get_client_ip")
            return "0.0.0.0"  # Null object pattern
        
        # Multiple ways to get IP with fallbacks
        ip_sources = [
            request.META.get('HTTP_X_REAL_IP'),
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip(),
            request.META.get('HTTP_CLIENT_IP'),
            request.META.get('REMOTE_ADDR')
        ]
        
        for ip in ip_sources:
            if ip and isinstance(ip, str) and len(ip) > 6:  # Basic validation
                return ip
        
        # Default return (null object pattern)
        return "0.0.0.0"
        
    except Exception as e:
        logger.error(f"Error extracting client IP: {str(e)}")
        return "0.0.0.0"  # Graceful degradation


def check_vpn(ip_address: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Check VPN with defensive coding and type hints
    Returns: (is_vpn, details)
    """
    try:
        if not ip_address or ip_address == "0.0.0.0":
            logger.warning(f"Invalid IP address for VPN check: {ip_address}")
            return False, {'error': 'invalid_ip', 'score': 0}
        
        # Mock VPN check - in real implementation, use external service
        suspicious_ips = getattr(settings, 'SUSPICIOUS_IPS', [])
        vpn_providers = ['vpn', 'proxy', 'tor']  # Example keywords
        
        # Using dict.get() for safe dictionary access
        config = getattr(settings, 'VPN_CONFIG', {})
        api_key = config.get('api_key', '')
        endpoint = config.get('endpoint', '')
        
        if not api_key or not endpoint:
            logger.warning("VPN check configuration missing")
            return False, {'warning': 'config_missing', 'score': 0}
        
        # Simulated API call with defensive coding
        try:
            # response = requests.get(f"{endpoint}/{ip_address}", timeout=5)
            # result = response.json()
            result = {'is_vpn': False}  # Mock response
        except requests.exceptions.Timeout:
            logger.error(f"VPN check timeout for IP: {ip_address}")
            return False, {'error': 'timeout', 'score': 0}
        except requests.exceptions.RequestException as e:
            logger.error(f"VPN check failed: {str(e)}")
            return False, {'error': 'request_failed', 'score': 0}
        
        # Safe attribute access with getattr-like pattern for dict
        is_vpn = result.get('is_vpn', False)
        score = result.get('score', 0)
        provider = result.get('provider', 'unknown')
        
        return is_vpn, {
            'score': score,
            'provider': provider,
            'confidence': min(100, score * 10)
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in VPN check: {str(e)}")
        return False, {'error': 'unexpected_error', 'score': 0}


def check_proxy(ip_address: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Check proxy with defensive coding
    """
    try:
        if not ip_address or ip_address == "0.0.0.0":
            return False, {'error': 'invalid_ip'}
        
        # Mock proxy check
        result = {'is_proxy': False, 'type': None}
        
        # Using getattr with default for settings
        proxy_threshold = getattr(settings, 'PROXY_THRESHOLD', 70)
        
        return result.get('is_proxy', False), {
            'type': result.get('type', 'unknown'),
            'score': result.get('score', 0),
            'is_suspicious': result.get('score', 0) > proxy_threshold
        }
        
    except Exception as e:
        logger.error(f"Proxy check error: {str(e)}")
        return False, {'error': str(e)}


def verify_device_authenticity(device_info: Optional[DeviceInfo]) -> Tuple[bool, Dict[str, Any]]:
    """
    Verify device authenticity with null object pattern
    """
    try:
        # Null object pattern - handle None device_info
        if not device_info:
            logger.warning("Device info is None in verify_device_authenticity")
            return False, {
                'authentic': False,
                'reason': 'device_info_missing',
                'score': 0
            }
        
        # Defensive attribute access with getattr()
        is_rooted = getattr(device_info, 'is_rooted', False)
        is_emulator = getattr(device_info, 'is_emulator', False)
        device_model = getattr(device_info, 'device_model', 'unknown')
        
        authenticity_score = 100
        
        # Check rooted/jailbroken
        if is_rooted:
            authenticity_score -= 40
        
        # Check emulator
        if is_emulator:
            authenticity_score -= 30
        
        # Check app integrity
        app_signature_valid = getattr(device_info, 'app_signature_valid', True)
        if not app_signature_valid:
            authenticity_score -= 20
        
        # Check device reputation
        device_reputation = getattr(device_info, 'reputation_score', 50)
        authenticity_score = (authenticity_score + device_reputation) // 2
        
        is_authentic = authenticity_score >= 70
        
        return is_authentic, {
            'authentic': is_authentic,
            'score': authenticity_score,
            'reasons': [
                'device_rooted' if is_rooted else None,
                'emulator_detected' if is_emulator else None,
                'app_integrity_failed' if not app_signature_valid else None
            ],
            'device_model': device_model
        }
        
    except Exception as e:
        logger.error(f"Device authenticity check failed: {str(e)}")
        # Graceful degradation - assume authentic on error
        return True, {
            'authentic': True,
            'error': str(e),
            'score': 50
        }


def send_security_alert(user, security_type: str, description: str, metadata: Dict[str, Any] = None) -> bool:
    """
    Send security alert with defensive coding
    Returns: True if successful, False otherwise
    """
    try:
        if not user or not hasattr(user, 'username'):
            logger.error("Invalid user for security alert")
            return False
        
        # Null object pattern for metadata
        metadata = metadata or {}
        
        # Get additional context safely
        context = {
            'user_id': getattr(user, 'id', 'unknown'),
            'username': getattr(user, 'username', 'unknown'),
            'email': getattr(user, 'email', ''),
            'timestamp': timezone.now().isoformat(),
            **metadata  # Merge metadata safely
        }
        
        # Log security alert
        logger.warning(
            f"SECURITY ALERT - User: {context['username']} - "
            f"Type: {security_type} - Description: {description}"
        )
        
        # Create security log entry with defensive error handling
        try:
            SecurityLog.objects.create(
                user=user,
                security_type=security_type,
                severity='high',
                description=description[:500],  # Truncate if too long
                metadata=context,
                ip_address=metadata.get('ip_address', ''),
                device_info=metadata.get('device_info')
            )
        except Exception as log_error:
            logger.error(f"Failed to create security log: {str(log_error)}")
            # Continue even if log creation fails
        
        # Send notification (optional)
        try:
            # Integration with notification system
            notification_sent = True  # Mock
            return notification_sent
        except Exception as notify_error:
            logger.error(f"Failed to send notification: {str(notify_error)}")
            return True  # Still return True if log was created
        
    except Exception as e:
        logger.error(f"Security alert function failed: {str(e)}")
        return False


def extract_device_info(request: HttpRequest) -> Dict[str, Any]:
    """
    Extract device info from request with defensive coding
    """
    try:
        if not request or not hasattr(request, 'META'):
            logger.warning("Invalid request in extract_device_info")
            return {}  # Return empty dict (null object pattern)
        
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Defensive parsing of user agent
        if not isinstance(user_agent, str):
            user_agent = str(user_agent)
        
        # Determine device type
        is_mobile = any(keyword in user_agent.lower() 
                       for keyword in ['mobile', 'android', 'iphone', 'ipad'])
        
        is_tablet = 'tablet' in user_agent.lower() or 'ipad' in user_agent.lower()
        
        # Determine browser
        browser = 'Unknown'
        browser_map = {
            'chrome': 'Chrome',
            'firefox': 'Firefox',
            'safari': 'Safari',
            'edge': 'Edge',
            'opera': 'Opera'
        }
        
        for key, value in browser_map.items():
            if key in user_agent.lower():
                browser = value
                break
        
        # Determine OS
        os_name = 'Unknown'
        os_map = {
            'windows': 'Windows',
            'mac os': 'macOS',
            'linux': 'Linux',
            'android': 'Android',
            'iphone': 'iOS',
            'ipad': 'iOS'
        }
        
        for key, value in os_map.items():
            if key in user_agent.lower():
                os_name = value
                break
        
        return {
            'user_agent': user_agent[:500],  # Truncate if too long
            'is_mobile': is_mobile,
            'is_tablet': is_tablet,
            'is_desktop': not (is_mobile or is_tablet),
            'browser': browser,
            'os': os_name,
            'screen_resolution': request.META.get('HTTP_SEC_CH_UA_MOBILE', ''),
            'language': request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            'platform': request.META.get('HTTP_SEC_CH_UA_PLATFORM', '')
        }
        
    except Exception as e:
        logger.error(f"Error extracting device info: {str(e)}")
        return {
            'user_agent': '',
            'is_mobile': False,
            'browser': 'Unknown',
            'error': str(e)
        }


# ==================== FRAUD DETECTION ENGINE ====================

class FraudDetectionEngine:
    """
    Fraud detection engine with comprehensive defensive coding
    """
    
    def __init__(self, user) -> None:
        """
        Initialize with defensive user validation
        """
        try:
            # Validate user
            if not user or not hasattr(user, 'id'):
                raise ValueError("Invalid user object provided")
            
            self.user = user
            self.suspicion_score = 0
            self.suspicion_reasons: List[str] = []
            self.warnings: List[str] = []
            self.metadata: Dict[str, Any] = {}
            
        except Exception as e:
            logger.error(f"FraudDetectionEngine initialization failed: {str(e)}")
            raise
    
    def check_withdrawal_fraud(self, amount: float, ip_address: str) -> Dict[str, Any]:
        """
        Comprehensive withdrawal fraud check with type hints
        """
        try:
            # Reset for new check
            self.suspicion_score = 0
            self.suspicion_reasons = []
            self.warnings = []
            self.metadata = {
                'user_id': getattr(self.user, 'id', None),
                'username': getattr(self.user, 'username', 'unknown'),
                'amount': amount,
                'ip_address': ip_address,
                'timestamp': timezone.now().isoformat()
            }
            
            # Validate inputs
            if not isinstance(amount, (int, float)) or amount <= 0:
                self.warnings.append("Invalid amount provided")
                amount = 0.0
            
            if not ip_address or ip_address == "0.0.0.0":
                self.warnings.append("Invalid IP address")
            
            # Run fraud checks
            self._check_device_fraud()
            self._check_withdrawal_frequency(amount)
            self._check_ip_patterns(ip_address)
            self._check_click_patterns()
            self._check_behavioral_patterns()
            self._check_amount_anomalies(amount)
            
            # Determine final result
            is_suspicious = self.suspicion_score >= 50
            
            # Log the check
            self._log_fraud_check(is_suspicious)
            
            return {
                'is_suspicious': is_suspicious,
                'score': self.suspicion_score,
                'reasons': self.suspicion_reasons,
                'warnings': self.warnings,
                'metadata': self.metadata,
                'recommendation': self._get_recommendation(),
                'threshold_exceeded': self.suspicion_score >= 50,
                'severity': self._get_severity_level()
            }
            
        except Exception as e:
            logger.error(f"Withdrawal fraud check failed: {str(e)}")
            # Graceful degradation - return safe result
            return {
                'is_suspicious': False,
                'score': 0,
                'reasons': ['check_failed'],
                'warnings': [f'Error: {str(e)}'],
                'metadata': {},
                'recommendation': 'manual_review',
                'error': str(e)
            }
    
    def _check_device_fraud(self) -> None:
        """Check device-related fraud indicators"""
        try:
            # Safe query with defensive coding
            devices = DeviceInfo.objects.filter(user=self.user).only(
                'device_id_hash', 'device_model', 'is_suspicious'
            )[:10]  # Limit results
            
            device_count = devices.count()
            self.metadata['device_count'] = device_count
            
            if device_count == 0:
                self.warnings.append("No device info found for user")
                return
            
            suspicious_count = 0
            for device in devices:
                # Use getattr for safe attribute access
                device_model = getattr(device, 'device_model', 'unknown')
                
                # Check if device is suspicious
                is_suspicious_method = getattr(device, 'is_suspicious', None)
                if callable(is_suspicious_method):
                    try:
                        if is_suspicious_method():
                            suspicious_count += 1
                            self.suspicion_score += 30
                            self.suspicion_reasons.append(
                                f"Suspicious device: {device_model}"
                            )
                    except Exception as e:
                        logger.error(f"Error calling is_suspicious: {str(e)}")
                
                # Check duplicate devices
                duplicate_check_method = getattr(DeviceInfo, 'check_duplicate_devices', None)
                if callable(duplicate_check_method):
                    try:
                        device_id_hash = getattr(device, 'device_id_hash', '')
                        if device_id_hash:
                            duplicate_count = duplicate_check_method(
                                device_id_hash, 
                                exclude_user=self.user
                            )
                            if duplicate_count > 0:
                                self.suspicion_score += min(20 * duplicate_count, 50)
                                self.suspicion_reasons.append(
                                    f"Device shared with {duplicate_count} other accounts"
                                )
                    except Exception as e:
                        logger.error(f"Error checking duplicate devices: {str(e)}")
            
            self.metadata['suspicious_devices'] = suspicious_count
            
        except Exception as e:
            logger.error(f"Device fraud check error: {str(e)}")
            self.warnings.append(f"Device check incomplete: {str(e)}")
    
    def _check_withdrawal_frequency(self, amount: float) -> None:
        """Check withdrawal frequency patterns"""
        try:
            time_ago_24h = timezone.now() - timedelta(hours=24)
            time_ago_7d = timezone.now() - timedelta(days=7)
            
            # Get recent withdrawals with defensive query
            recent_24h = WithdrawalProtection.objects.filter(
                user=self.user,
                attempted_at__gte=time_ago_24h,
                status__in=['completed', 'pending']
            ).count()
            
            recent_7d = WithdrawalProtection.objects.filter(
                user=self.user,
                attempted_at__gte=time_ago_7d,
                status__in=['completed', 'pending']
            ).count()
            
            self.metadata.update({
                'withdrawals_24h': recent_24h,
                'withdrawals_7d': recent_7d
            })
            
            # Check thresholds
            thresholds = getattr(settings, 'WITHDRAWAL_THRESHOLDS', {
                '24h': 3,
                '7d': 10,
                'amount_24h': 10000
            })
            
            if recent_24h >= thresholds.get('24h', 3):
                self.suspicion_score += 25
                self.suspicion_reasons.append(
                    f"Too many withdrawals ({recent_24h}) in 24 hours"
                )
            
            if recent_7d >= thresholds.get('7d', 10):
                self.suspicion_score += 15
                self.suspicion_reasons.append(
                    f"High withdrawal frequency ({recent_7d}) in 7 days"
                )
            
            # Check amount-based patterns
            total_24h = WithdrawalProtection.objects.filter(
                user=self.user,
                attempted_at__gte=time_ago_24h,
                status='completed'
            ).aggregate(total=models.Sum('amount'))['total'] or 0
            
            if total_24h > thresholds.get('amount_24h', 10000):
                self.suspicion_score += 20
                self.suspicion_reasons.append(
                    f"Large withdrawal amount (${total_24h}) in 24 hours"
                )
            
        except Exception as e:
            logger.error(f"Withdrawal frequency check error: {str(e)}")
            self.warnings.append(f"Frequency check incomplete: {str(e)}")
    
    def _check_ip_patterns(self, current_ip: str) -> None:
        """Check IP address patterns and history"""
        try:
            if not current_ip or current_ip == "0.0.0.0":
                return
            
            # Check IP fraud history
            fraud_logs = SecurityLog.objects.filter(
                ip_address=current_ip,
                severity__in=['high', 'critical']
            ).count()
            
            self.metadata['ip_fraud_history'] = fraud_logs
            
            if fraud_logs > 0:
                self.suspicion_score += min(15 * fraud_logs, 50)
                self.suspicion_reasons.append(
                    f"IP {current_ip} has {fraud_logs} fraud history"
                )
            
            # Check IP geolocation anomalies
            user_ip_history = SecurityLog.objects.filter(
                user=self.user
            ).values('ip_address').distinct().count()
            
            if user_ip_history > 5:  # User has used many different IPs
                self.suspicion_score += 10
                self.suspicion_reasons.append(
                    f"User has used {user_ip_history} different IPs"
                )
            
            # Check VPN/Proxy
            is_vpn, vpn_details = check_vpn(current_ip)
            is_proxy, proxy_details = check_proxy(current_ip)
            
            if is_vpn:
                self.suspicion_score += 30
                self.suspicion_reasons.append(
                    f"VPN detected: {vpn_details.get('provider', 'unknown')}"
                )
            
            if is_proxy:
                self.suspicion_score += 25
                self.suspicion_reasons.append(
                    f"Proxy detected: {proxy_details.get('type', 'unknown')}"
                )
            
        except Exception as e:
            logger.error(f"IP pattern check error: {str(e)}")
            self.warnings.append(f"IP check incomplete: {str(e)}")
    
    def _check_click_patterns(self) -> None:
        """Check click patterns for fraud"""
        try:
            # Check fast clicking
            fast_click_method = getattr(ClickTracker, 'check_fast_clicking', None)
            if callable(fast_click_method):
                is_fast_clicking = fast_click_method(
                    self.user, 
                    'ad_click', 
                    time_window=60, 
                    max_clicks=5
                )
                
                if is_fast_clicking:
                    self.suspicion_score += 20
                    self.suspicion_reasons.append("Fast clicking pattern detected")
            
            # Check click consistency
            avg_clicks_per_hour = ClickTracker.objects.filter(
                user=self.user,
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count() / 24
            
            if avg_clicks_per_hour > 100:  # Unusually high
                self.suspicion_score += 15
                self.suspicion_reasons.append(
                    f"High click rate: {avg_clicks_per_hour:.1f}/hour"
                )
            
        except Exception as e:
            logger.error(f"Click pattern check error: {str(e)}")
            self.warnings.append(f"Click check incomplete: {str(e)}")
    
    def _check_behavioral_patterns(self) -> None:
        """Check behavioral patterns"""
        try:
            # Get user's typical behavior
            user_join_date = getattr(self.user, 'date_joined', timezone.now())
            account_age_days = (timezone.now() - user_join_date).days
            
            self.metadata['account_age_days'] = account_age_days
            
            # New account penalty
            if account_age_days < 7:
                self.suspicion_score += 10
                self.suspicion_reasons.append(
                    f"New account ({account_age_days} days old)"
                )
            
            # Check verification status
            is_verified = getattr(self.user, 'is_verified', False)
            if not is_verified:
                self.suspicion_score += 15
                self.suspicion_reasons.append("Account not verified")
            
        except Exception as e:
            logger.error(f"Behavioral pattern check error: {str(e)}")
            self.warnings.append(f"Behavioral check incomplete: {str(e)}")
    
    def _check_amount_anomalies(self, amount: float) -> None:
        """Check for amount anomalies"""
        try:
            if amount <= 0:
                return
            
            # Get user's typical withdrawal amounts
            typical_amounts = WithdrawalProtection.objects.filter(
                user=self.user,
                status='completed'
            ).values_list('amount', flat=True)[:20]
            
            if typical_amounts:
                avg_amount = sum(typical_amounts) / len(typical_amounts)
                
                # Check if current amount is significantly different
                if amount > avg_amount * 3:  # 3x larger than typical
                    self.suspicion_score += 20
                    self.suspicion_reasons.append(
                        f"Amount (${amount}) is unusually high "
                        f"(typically ${avg_amount:.2f})"
                    )
            
        except Exception as e:
            logger.error(f"Amount anomaly check error: {str(e)}")
            self.warnings.append(f"Amount check incomplete: {str(e)}")
    
    def _get_recommendation(self) -> str:
        """Get recommendation based on suspicion score"""
        if self.suspicion_score >= 70:
            return "block_and_review"
        elif self.suspicion_score >= 50:
            return "require_verification"
        elif self.suspicion_score >= 30:
            return "additional_monitoring"
        else:
            return "allow"
    
    def _get_severity_level(self) -> str:
        """Get severity level"""
        if self.suspicion_score >= 70:
            return "critical"
        elif self.suspicion_score >= 50:
            return "high"
        elif self.suspicion_score >= 30:
            return "medium"
        else:
            return "low"
    
    def _log_fraud_check(self, is_suspicious: bool) -> None:
        """Log fraud check result"""
        try:
            log_entry = {
                'user_id': getattr(self.user, 'id', None),
                'username': getattr(self.user, 'username', 'unknown'),
                'score': self.suspicion_score,
                'is_suspicious': is_suspicious,
                'reasons': self.suspicion_reasons,
                'timestamp': timezone.now().isoformat()
            }
            
            # Store in metadata for reference
            self.metadata['check_log'] = log_entry
            
            # Log to security system
            if is_suspicious:
                send_security_alert(
                    user=self.user,
                    security_type='fraud_detected',
                    description=f"Fraud detected: {self.suspicion_score} score",
                    metadata=self.metadata
                )
            
        except Exception as e:
            logger.error(f"Failed to log fraud check: {str(e)}")
    
    @classmethod
    def check_transaction_fraud(cls, user, amount: float, 
                               transaction_type: str, 
                               ip_address: str) -> Dict[str, Any]:
        """
        Static method for transaction fraud check
        """
        try:
            if not user:
                logger.error("No user provided for transaction fraud check")
                return {
                    'is_suspicious': False,
                    'score': 0,
                    'error': 'user_required'
                }
            
            engine = cls(user)
            
            # Add transaction type to check
            engine.metadata['transaction_type'] = transaction_type
            
            # Run standard checks
            result = engine.check_withdrawal_fraud(amount, ip_address)
            
            # Add transaction-specific checks
            if transaction_type == 'withdrawal':
                result['requires_approval'] = engine.suspicion_score >= 40
            elif transaction_type == 'transfer':
                result['requires_verification'] = engine.suspicion_score >= 30
            
            return result
            
        except Exception as e:
            logger.error(f"Transaction fraud check failed: {str(e)}")
            return {
                'is_suspicious': False,
                'score': 0,
                'error': str(e),
                'recommendation': 'manual_review'
            }


# ==================== DECORATORS ====================

def method_audit_action(action_name: str) -> Callable:
    """
    Decorator for auditing method actions with defensive coding
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)  # Preserve function metadata
        def wrapped(*args, **kwargs) -> Any:
            start_time = timezone.now()
            result = None
            error = None
            success = False
            
            try:
                # Log method entry
                logger.info(f"AUDIT START - Action: {action_name}")
                
                # Execute the function
                result = func(*args, **kwargs)
                success = True
                
                return result
                
            except Exception as e:
                error = str(e)
                logger.error(f"AUDIT ERROR - Action: {action_name} - Error: {error}")
                raise  # Re-raise the exception
                
            finally:
                # Always log audit trail (even on error)
                try:
                    duration = (timezone.now() - start_time).total_seconds()
                    
                    # Create audit log with defensive coding
                    audit_data = {
                        'action': action_name,
                        'duration_seconds': duration,
                        'success': success,
                        'error': error,
                        'timestamp': start_time.isoformat(),
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys()) if kwargs else []
                    }
                    
                    # Safely add user info if available
                    if args and len(args) > 0:
                        first_arg = args[0]
                        if hasattr(first_arg, 'username'):
                            audit_data['user'] = getattr(first_arg, 'username', 'unknown')
                        elif isinstance(first_arg, HttpRequest):
                            audit_data['ip'] = get_client_ip(first_arg)
                    
                    # Log audit entry
                    if success:
                        logger.info(f"AUDIT COMPLETE - {action_name} - {duration:.2f}s")
                    else:
                        logger.warning(f"AUDIT FAILED - {action_name} - Error: {error}")
                    
                    # Store audit log (optional)
                    try:
                        # This could be saved to database or external service
                        pass
                    except Exception as log_error:
                        logger.error(f"Failed to store audit log: {str(log_error)}")
                        
                except Exception as audit_error:
                    logger.error(f"Audit logging failed: {str(audit_error)}")
        
        return wrapped
    return decorator


def require_security_check(check_type: str = 'fraud') -> Callable:
    """
    Decorator to require security checks before method execution
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapped(self, *args, **kwargs) -> Any:
            try:
                # Extract context for security check
                request = None
                user = None
                amount = 0
                ip_address = ""
                
                # Defensive extraction of parameters
                if hasattr(self, 'request'):
                    request = self.request
                    user = getattr(request, 'user', None)
                    ip_address = get_client_ip(request)
                
                # Try to get amount from args/kwargs
                for arg in args:
                    if isinstance(arg, (int, float)):
                        amount = float(arg)
                        break
                
                amount = kwargs.get('amount', amount)
                
                # Perform security check
                if check_type == 'fraud' and user:
                    fraud_result = FraudDetectionEngine.check_transaction_fraud(
                        user=user,
                        amount=amount,
                        transaction_type=func.__name__,
                        ip_address=ip_address
                    )
                    
                    # Check if suspicious
                    if fraud_result.get('is_suspicious', False):
                        send_security_alert(
                            user=user,
                            security_type='blocked_action',
                            description=f"Blocked {func.__name__} due to fraud suspicion",
                            metadata=fraud_result
                        )
                        
                        # Return error response instead of executing function
                        if request:
                            from django.http import JsonResponse
                            return JsonResponse({
                                'error': 'security_check_failed',
                                'reason': fraud_result.get('reasons', ['Suspicious activity']),
                                'score': fraud_result.get('score', 0)
                            }, status=403)
                
                # Execute original function
                return func(self, *args, **kwargs)
                
            except Exception as e:
                logger.error(f"Security check decorator error: {str(e)}")
                # Graceful degradation - allow execution on error
                return func(self, *args, **kwargs)
        
        return wrapped
    return decorator


# ==================== USAGE EXAMPLES ====================

class TransactionService:
    """Example service using defensive coding patterns"""
    
    def __init__(self, request):
        self.request = request
        self.user = getattr(request, 'user', None)
        self.ip_address = get_client_ip(request)
    
    @method_audit_action('process_withdrawal')
    @require_security_check('fraud')
    def process_withdrawal(self, amount: float) -> Dict[str, Any]:
        """
        Process withdrawal with security checks
        """
        try:
            # Validate inputs
            if not isinstance(amount, (int, float)) or amount <= 0:
                raise ValueError("Invalid amount")
            
            if not self.user:
                raise ValueError("User not authenticated")
            
            # Get device info safely
            device_info = extract_device_info(self.request)
            
            # Verify device authenticity
            is_authentic, device_details = verify_device_authenticity(
                DeviceInfo.objects.filter(user=self.user).first()
            )
            
            if not is_authentic:
                send_security_alert(
                    user=self.user,
                    security_type='suspicious_device',
                    description="Withdrawal attempted from suspicious device",
                    metadata={
                        'amount': amount,
                        'device_info': device_info,
                        'device_details': device_details
                    }
                )
                raise PermissionError("Device not authenticated")
            
            # Check VPN/Proxy
            is_vpn, vpn_details = check_vpn(self.ip_address)
            is_proxy, proxy_details = check_proxy(self.ip_address)
            
            if is_vpn or is_proxy:
                send_security_alert(
                    user=self.user,
                    security_type='vpn_proxy_detected',
                    description="VPN/Proxy detected during withdrawal",
                    metadata={
                        'vpn': vpn_details,
                        'proxy': proxy_details,
                        'amount': amount
                    }
                )
            
            # Process withdrawal (mock)
            transaction_id = f"TXN{int(timezone.now().timestamp())}"
            
            # Log successful transaction
            logger.info(
                f"Withdrawal processed - User: {self.user.username} - "
                f"Amount: ${amount} - Transaction: {transaction_id}"
            )
            
            return {
                'success': True,
                'transaction_id': transaction_id,
                'amount': amount,
                'timestamp': timezone.now().isoformat(),
                'security_checks': {
                    'device_authentic': is_authentic,
                    'vpn_detected': is_vpn,
                    'proxy_detected': is_proxy
                }
            }
            
        except Exception as e:
            logger.error(f"Withdrawal processing failed: {str(e)}")
            
            # Send security alert for failed attempt
            send_security_alert(
                user=self.user,
                security_type='withdrawal_failed',
                description=f"Withdrawal failed: {str(e)}",
                metadata={
                    'amount': amount,
                    'error': str(e),
                    'ip_address': self.ip_address
                }
            )
            
            # Re-raise with context
            raise Exception(f"Withdrawal failed: {str(e)}")


# ==================== QUICK TEST FUNCTION ====================

def test_fraud_detection() -> None:
    """Test function to verify fraud detection engine"""
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get a test user
        test_user = User.objects.first()
        
        if not test_user:
            print("No user found for testing")
            return
        
        # Create fraud detection engine
        engine = FraudDetectionEngine(test_user)
        
        # Test withdrawal fraud check
        result = engine.check_withdrawal_fraud(
            amount=1000.0,
            ip_address="192.168.1.100"
        )
        
        print("=== Fraud Detection Test ===")
        print(f"User: {test_user.username}")
        print(f"Amount: $1000")
        print(f"Is Suspicious: {result.get('is_suspicious', False)}")
        print(f"Score: {result.get('score', 0)}")
        print(f"Reasons: {result.get('reasons', [])}")
        print(f"Recommendation: {result.get('recommendation', 'unknown')}")
        print("==========================")
        
        return result
        
    except Exception as e:
        logger.error(f"Test function failed: {str(e)}")
        return None