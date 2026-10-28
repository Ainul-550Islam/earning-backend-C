# =============================================================================
# fraud_detection/middleware.py
# =============================================================================
"""
Enterprise Fraud Detection Middleware.

Provides comprehensive fraud detection and prevention for all HTTP requests:
- Real-time risk assessment
- Device fingerprinting
- IP reputation checking
- Behavioral analysis
- Automatic fraud attempt logging
- Hash integrity verification
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)

# AdaptiveThrottlingManager — was floating, now wired
try:
    from api.fraud_detection.throttling import adaptive_throttling_manager as _adaptive_throttler
except Exception:
    _adaptive_throttler = None

# Path prefixes that require fraud check
FINANCIAL_PATHS = (
    '/api/wallet/withdraw',
    '/api/wallet/withdrawal',
    '/api/payment-request',
    '/api/payment_request',
    '/api/create_payment_request',
    '/api/offerwall/complete',
    '/api/offerwall/submit',
)

TASK_PATHS = (
    '/api/tasks/complete',
    '/api/tasks/submit',
    '/api/complete-ad',
    '/api/offer-completion',
)

HIGH_RISK_PATHS = (
    '/api/user/change-password',
    '/api/user/update-email',
    '/api/user/enable-2fa',
    '/api/auth/change-password',
)

# Paths that skip fraud check
SKIP_PATHS = (
    '/api/auth/login',
    '/api/auth/register',
    '/api/auth/token',
    '/api/auth/refresh',
    '/api/auth/otp',
    '/admin/',
    '/static/',
    '/media/',
    '/health/',
    '/metrics/',
)


def _get_client_ip(request) -> str:
    """Extract real client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


def _get_device_fingerprint(request) -> str:
    """Generate device fingerprint from request headers."""
    try:
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
        accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
        
        fingerprint_data = f"{user_agent}:{accept_language}:{accept_encoding}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:32]
    except Exception:
        return 'unknown'


def _get_user_risk(user) -> Tuple[bool, str, int]:
    """Return (allowed, reason, risk_score) for user."""
    if not user or not user.is_authenticated or isinstance(user, AnonymousUser):
        return True, "", 0
    
    try:
        from api.fraud_detection.models import UserRiskProfile
        profile = UserRiskProfile.objects.select_related('user').filter(user=user).first()
        
        if not profile:
            return True, "", 0
            
        # Check restrictions
        if profile.is_restricted:
            return False, "Account is restricted due to suspicious activity.", profile.overall_risk_score
            
        # Check flagged status with high risk
        if profile.is_flagged and profile.overall_risk_score >= 80:
            return False, "Account flagged for manual review.", profile.overall_risk_score
            
        # Check monitoring level
        if profile.monitoring_level == 'strict' and profile.overall_risk_score >= 60:
            return False, "Account under strict monitoring - action blocked.", profile.overall_risk_score
            
        return True, "", profile.overall_risk_score
        
    except ImportError as e:
        logger.debug("Fraud detection models not available: %s", e)
        return True, "", 0
    except Exception as e:
        logger.exception("User risk check failed: %s", e)
        return True, "", 0  # Fail open for availability


def _check_ip_reputation(ip_address: str) -> Tuple[bool, str, int]:
    """Check IP reputation and return (allowed, reason, score)."""
    if not ip_address:
        return True, "", 0
        
    try:
        from api.fraud_detection.models import IPReputation
        from api.fraud_detection.detectors.VPNProxyDetector import VPNProxyDetector
        
        # Check cache first
        cache_key = f'ip_rep_{ip_address}'
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Use VPNProxyDetector for comprehensive IP analysis
        vpn_detector = VPNProxyDetector()
        vpn_result = vpn_detector.check_vpn_proxy(ip_address)
        
        # Get or create IP reputation record
        ip_rep, created = IPReputation.objects.get_or_create(
            ip_address=ip_address,
            defaults={
                'fraud_score': vpn_result.get('risk_score', 0),
                'is_blacklisted': vpn_result.get('is_blacklisted', False),
                'blacklist_reason': vpn_result.get('blacklist_reason', ''),
                'threat_types': vpn_result.get('threat_types', []),
                'last_seen': timezone.now()
            }
        )
        
        if not created:
            # Update existing record with latest VPN detection results
            ip_rep.fraud_score = max(ip_rep.fraud_score, vpn_result.get('risk_score', 0))
            ip_rep.is_blacklisted = ip_rep.is_blacklisted or vpn_result.get('is_blacklisted', False)
            if vpn_result.get('is_blacklisted', False) and not ip_rep.blacklist_reason:
                ip_rep.blacklist_reason = vpn_result.get('blacklist_reason', 'VPN/Proxy detected')
            ip_rep.threat_types = list(set(ip_rep.threat_types + vpn_result.get('threat_types', [])))
            ip_rep.last_seen = timezone.now()
            ip_rep.save()
        
        # Determine result based on VPN detection and reputation
        if vpn_result.get('is_blacklisted', False):
            result = False, f"IP address {ip_address} is blacklisted: VPN/Proxy detected", ip_rep.fraud_score
        elif vpn_result.get('is_vpn', False) or vpn_result.get('is_proxy', False) or vpn_result.get('is_tor', False):
            result = False, f"IP address {ip_address} detected as VPN/Proxy/TOR", max(ip_rep.fraud_score, 70)
        elif ip_rep.fraud_score >= 80:
            result = False, f"IP address {ip_address} has high fraud score: {ip_rep.fraud_score}", ip_rep.fraud_score
        elif ip_rep.fraud_score >= 60:
            result = True, f"IP address {ip_address} has medium fraud score: {ip_rep.fraud_score}", ip_rep.fraud_score
        else:
            result = True, "", ip_rep.fraud_score
            
        # Cache result for 1 hour
        cache.set(cache_key, result, 3600)
        return result
        
    except ImportError as e:
        logger.debug("IP reputation check not available: %s", e)
        return True, "", 0
    except Exception as e:
        logger.exception("IP reputation check failed: %s", e)
        return True, "", 0


def _check_device_risk(user, device_fingerprint: str, request) -> Tuple[bool, str, int]:
    """Check device risk and return (allowed, reason, score)."""
    if not user or not user.is_authenticated or not device_fingerprint:
        return True, "", 0
        
    try:
        from api.fraud_detection.models import DeviceFingerprint
        
        device_fp = DeviceFingerprint.objects.filter(
            user=user,
            device_hash=device_fingerprint
        ).first()
        
        if not device_fp:
            # New device - create record
            return True, "New device detected", 10
            
        # Check trust score
        if device_fp.trust_score < 30:
            return False, f"Device trust score too low: {device_fp.trust_score}", 100 - device_fp.trust_score
        elif device_fp.trust_score < 50:
            return True, f"Device has low trust score: {device_fp.trust_score}", 100 - device_fp.trust_score
            
        # Check security flags
        if device_fp.is_vpn or device_fp.is_proxy or device_fp.is_tor:
            return True, f"Suspicious network detected (VPN/Proxy/Tor)", 60
            
        return True, "", 100 - device_fp.trust_score
        
    except ImportError as e:
        logger.debug("Device fingerprint check not available: %s", e)
        return True, "", 0
    except Exception as e:
        logger.exception("Device risk check failed: %s", e)
        return True, "", 0


def _log_fraud_attempt(request, risk_score: int, reason: str, blocked: bool):
    """Log fraud attempt for analysis using new services."""
    try:
        from api.fraud_detection.models import FraudAttempt
        from api.fraud_detection.services.FraudCaseService import FraudCaseService
        from api.fraud_detection.services.FraudNotificationService import FraudNotificationService
        
        user = getattr(request, 'user', None)
        ip_address = _get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Determine attempt type based on path
        path = request.path or ''
        attempt_type = 'unknown'
        if any(p.startswith(path) for p in FINANCIAL_PATHS):
            attempt_type = 'payment_fraud'
        elif any(p.startswith(path) for p in TASK_PATHS):
            attempt_type = 'offer_abuse'
        elif any(p.startswith(path) for p in HIGH_RISK_PATHS):
            attempt_type = 'account_takeover'
            
        # Create fraud attempt record
        fraud_attempt = FraudAttempt.objects.create(
            user=user if user and user.is_authenticated else None,
            attempt_type=attempt_type,
            description=f"Fraud detection middleware: {reason}",
            detected_by='middleware',
            fraud_score=min(risk_score, 100),
            confidence_score=85,  # High confidence for middleware detection
            status='detected' if not blocked else 'confirmed',
            evidence_data=json.dumps({
                'ip_address': ip_address,
                'user_agent': user_agent,
                'path': path,
                'method': request.method,
                'timestamp': timezone.now().isoformat(),
            }),
            amount_involved=0,  # Could be extracted from request data if needed
        )
        
        # Use new services for enhanced processing
        try:
            # Create fraud case if high risk using FraudCaseService
            if risk_score >= 80 and user and user.is_authenticated:
                case_service = FraudCaseService()
                case_service.create_case(
                    user_id=user.id,
                    title=f"High Risk Fraud: {attempt_type}",
                    description=f"Automated case creation for middleware detection with score {risk_score}",
                    risk_score=risk_score,
                    evidence_data={
                        'middleware_detection': True,
                        'ip_address': ip_address,
                        'path': path,
                        'reason': reason
                    }
                )
            
            # Send notification using FraudNotificationService
            if risk_score >= 70:
                notification_service = FraudNotificationService()
                notification_service.send_alert(
                    user=user,
                    alert_type='fraud_attempt',
                    title=f"Fraud Attempt Detected: {attempt_type}",
                    message=f"Risk score: {risk_score}, Reason: {reason}",
                    priority='high' if risk_score >= 80 else 'medium'
                )
                
        except ImportError:
            # Fallback if services not available
            pass
        except Exception as e:
            logger.debug("Enhanced fraud processing failed: %s", e)
        
        logger.info("Fraud attempt logged: user=%s, ip=%s, score=%d, reason=%s", 
                   getattr(user, 'id', None), ip_address, risk_score, reason)
                   
    except ImportError as e:
        logger.debug("Fraud attempt logging not available: %s", e)
    except Exception as e:
        logger.exception("Failed to log fraud attempt: %s", e)


class FraudDetectionMiddleware(MiddlewareMixin):
    """
    Enterprise Fraud Detection Middleware.
    
    Provides comprehensive fraud detection and prevention:
    - Real-time risk assessment
    - Device fingerprinting
    - IP reputation checking
    - Behavioral analysis
    - Automatic fraud attempt logging
    - Hash integrity verification
    """
    
    def process_request(self, request):
        """Process incoming request for fraud detection."""
        start_time = time.time()
        path = (request.path or '').strip()
        
        # Skip non-API paths
        if not path.startswith('/api/'):
            self._set_request_attributes(request, False, True, "", 0, 0)
            return None
            
        # Skip whitelisted paths
        if any(path.startswith(p) for p in SKIP_PATHS):
            self._set_request_attributes(request, False, True, "", 0, 0)
            return None
            
        # Determine risk level based on path
        is_financial = any(path.startswith(p) for p in FINANCIAL_PATHS)
        is_task = any(path.startswith(p) for p in TASK_PATHS)
        is_high_risk = any(path.startswith(p) for p in HIGH_RISK_PATHS)
        
        if not (is_financial or is_task or is_high_risk):
            self._set_request_attributes(request, False, True, "", 0, 0)
            return None
            
        # Perform comprehensive fraud detection
        user = getattr(request, 'user', None)
        ip_address = _get_client_ip(request)
        device_fingerprint = _get_device_fingerprint(request)
        
        # Check user risk
        user_allowed, user_reason, user_score = _get_user_risk(user)
        
        # Check IP reputation
        ip_allowed, ip_reason, ip_score = _check_ip_reputation(ip_address)
        
        # Check device risk
        device_allowed, device_reason, device_score = _check_device_risk(user, device_fingerprint, request)
        
        # Calculate combined risk score
        combined_score = max(user_score, ip_score, device_score)

        # ── GeoVelocityDetector ───────────────────────────────────────────
        # Check impossible travel on high-risk paths before allowing request
        try:
            from api.fraud_detection.signals import _run_geo_velocity_check
            if user and user.is_authenticated and ip_address:
                geo_score = _run_geo_velocity_check(user_id=user.id, ip_address=ip_address)
                if geo_score > combined_score:
                    combined_score = min(100, geo_score)
                if geo_score >= 70:
                    reasons.append(f"Impossible travel detected (geo_score={geo_score})")
        except Exception as _geo_exc:
            logger.debug("GeoVelocityDetector skipped in middleware: %s", _geo_exc)

        # ── BehavioralBiometricsAnalyzer ──────────────────────────────────
        # Cache session biometric data so signals.py can pick it up later.
        # Also check score here for real-time blocking on high-risk paths.
        try:
            if user and user.is_authenticated and is_high_risk:
                session_data = {}
                ua = request.META.get('HTTP_USER_AGENT', '')
                # Extract available signals from request headers
                if request.content_type == 'application/json':
                    import json as _json
                    try:
                        body = getattr(request, '_body', None) or request.body
                        payload = _json.loads(body)
                        if 'biometrics' in payload:
                            session_data = payload['biometrics']
                    except Exception:
                        pass
                # Store for signals.py to consume
                if session_data and user.is_authenticated:
                    from django.core.cache import cache as _cache
                    _cache.set(
                        f"biometrics:{user.id}",
                        session_data,
                        timeout=300,
                    )
                # Bot detection via user-agent heuristic (fast fallback)
                headless_ua_signals = [
                    'HeadlessChrome', 'PhantomJS', 'Selenium',
                    'Puppeteer', 'playwright', 'python-requests',
                ]
                if any(sig in ua for sig in headless_ua_signals):
                    combined_score = min(100, combined_score + 40)
                    reasons.append("Headless/automation browser detected")
        except Exception as _bio_exc:
            logger.debug("BehavioralBiometricsAnalyzer skipped in middleware: %s", _bio_exc)

        # Determine if request should be blocked
        block_high_risk = getattr(settings, 'FRAUD_MIDDLEWARE_BLOCK_HIGH_RISK', True)
        allowed = user_allowed and ip_allowed and device_allowed
        
        # Combine reasons
        reasons = []
        if user_reason:
            reasons.append(user_reason)
        if ip_reason:
            reasons.append(ip_reason)
        if device_reason:
            reasons.append(device_reason)
        combined_reason = "; ".join(reasons) if reasons else ""
        
        # Log high-risk attempts
        if combined_score >= 60 or not allowed:
            _log_fraud_attempt(request, combined_score, combined_reason, not allowed)
        
        # Set request attributes
        self._set_request_attributes(
            request, 
            True, 
            allowed, 
            combined_reason, 
            combined_score,
            time.time() - start_time
        )
        
        # Block request if not allowed and blocking is enabled
        if not allowed and block_high_risk:
            logger.warning(
                "Blocked fraud request: user=%s, ip=%s, path=%s, score=%d, reason=%s",
                getattr(user, 'id', None), ip_address, path, combined_score, combined_reason
            )
            return JsonResponse({
                'detail': combined_reason or 'Action not allowed due to fraud detection.',
                'code': 'fraud_risk',
                'risk_score': combined_score,
            }, status=403)
            
        return None
    
    def _set_request_attributes(self, request, checked: bool, allowed: bool, 
                              reason: str, score: int, processing_time: float):
        """Set fraud detection attributes on request object."""
        request.fraud_risk_checked = checked
        request.fraud_risk_allowed = allowed
        request.fraud_risk_reason = reason
        request.fraud_risk_score = score
        request.fraud_processing_time = processing_time
