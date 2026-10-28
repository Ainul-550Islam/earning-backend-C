# api/security/services.py
"""
Enhanced Security Services with comprehensive security model integration
Author: System Security Team
Version: 2.0.0

Business logic for api.security. Move complex logic out of views.
Integrates with all security models for complete security management.
"""

import logging
import json
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass



logger = logging.getLogger(__name__)

# Import security models for enhanced service integration
try:
    from ..models import (
        DeviceInfo, SecurityLog, UserBan, IPBlacklist, 
        ThreatIntelligence, SecurityIncident, TrustedDevice,
        PasswordHistory, SecurityPolicy, SecurityInsight,
        RiskScore, FraudPattern, RealTimeDetection,
        Country, GeolocationLog, CountryBlockRule,
        APIRateLimit, RateLimitLog, TwoFactorMethod,
        TwoFactorAttempt, TwoFactorRecoveryCode, UserSession,
        SessionActivity, ClickTracker, EnhancedClickTracker
    )
    SECURITY_MODELS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Security models import failed: {e}")
    SECURITY_MODELS_AVAILABLE = False


class SecurityService:
    """
    Enhanced Central Security Service with comprehensive security model integration
    Provides methods for IP risk assessment, security event logging,
    rate limiting, brute force detection, and more.
    """

    def __init__(self):
        """Initialize Security Service with configuration"""
        try:
            self.cache_timeout = getattr(settings, 'SECURITY_CACHE_TIMEOUT', 300)
            self.max_failed_attempts = getattr(settings, 'MAX_FAILED_ATTEMPTS', 5)
            self.lockout_duration = getattr(settings, 'LOCKOUT_DURATION', 900)
            self.rate_limit_window = getattr(settings, 'RATE_LIMIT_WINDOW', 3600)
            self.rate_limit_max = getattr(settings, 'RATE_LIMIT_MAX', 100)
            
            logger.info("Enhanced SecurityService initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize SecurityService: {e}")
            self.cache_timeout = 300
            self.max_failed_attempts = 5
            self.lockout_duration = 900

    @staticmethod
    def check_ip_risk(ip_address: str) -> Dict[str, Any]:
        """
        Enhanced IP risk assessment with multiple data sources
        Integrates with fraud detection, threat intelligence, and geolocation
        """
        try:
            result = {
                "risk_score": 0,
                "is_blacklisted": False,
                "country": None,
                "is_vpn": False,
                "is_proxy": False,
                "threat_level": "low",
                "reputation_score": 0,
                "last_seen": None
            }
            
            # Check IP blacklist if available
            if SECURITY_MODELS_AVAILABLE:
                blacklisted = IPBlacklist.objects.filter(
                    ip_address=ip_address,
                    is_active=True,
                    expires_at__gt=timezone.now()
                ).first()
                
                if blacklisted:
                    result.update({
                        "is_blacklisted": True,
                        "risk_score": max(result["risk_score"], 80),
                        "threat_level": "high"
                    })
                    logger.warning(f"IP {ip_address} is blacklisted")
            
            # Check threat intelligence
            if SECURITY_MODELS_AVAILABLE:
                threat_data = ThreatIntelligence.objects.filter(
                    indicators__contains=[ip_address],
                    is_active=True
                ).first()
                
                if threat_data:
                    result.update({
                        "threat_level": threat_data.severity.lower(),
                        "threat_type": threat_data.threat_type,
                        "confidence": threat_data.confidence
                    })
            
            # Check geolocation
            if SECURITY_MODELS_AVAILABLE:
                geo_log = GeolocationLog.objects.filter(
                    ip_address=ip_address
                ).order_by('-queried_at').first()
                
                if geo_log:
                    result.update({
                        "country": geo_log.country,
                        "city": geo_log.city,
                        "latitude": geo_log.latitude,
                        "longitude": geo_log.longitude
                    })
            
            # Integrate with fraud detection
            try:
                from api.fraud_detection.models import IPReputation
                rep = IPReputation.objects.filter(ip_address=ip_address).first()
                if rep:
                    result.update({
                        "reputation_score": rep.fraud_score,
                        "is_suspicious": rep.is_blacklisted
                    })
            except ImportError:
                pass
            
            return result
            
        except Exception as e:
            logger.error(f"Error in IP risk assessment: {e}")
            return {
                "risk_score": 0,
                "is_blacklisted": False,
                "country": None,
                "error": str(e)
            }

    @staticmethod
    def log_security_event(user, event_type: str, severity: str = 'info', 
                        metadata: Optional[Dict] = None, 
                        ip_address: str = None,
                        user_agent: str = None,
                        device_info: str = None) -> Optional[SecurityLog]:
        """
        Enhanced security event logging with comprehensive data
        Creates SecurityLog entry with full context and metadata
        """
        try:
            if not SECURITY_MODELS_AVAILABLE:
                logger.info(f"Security event: {event_type} - {severity}")
                return None
            
            # Create security log entry
            log_entry = SecurityLog.objects.create(
                user=user if user and user.is_authenticated else None,
                security_type=event_type,
                severity=severity,
                ip_address=ip_address,
                user_agent=user_agent,
                device_info=device_info,
                metadata=metadata or {}
            )
            
            logger.info(f"Security event logged: {log_entry.id} - {event_type}")
            return log_entry
            
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")
            return None

    @staticmethod
    def assess_user_risk(user) -> Dict[str, Any]:
        """
        Comprehensive user risk assessment using multiple factors
        Combines device trust, ban status, security incidents, and more
        """
        try:
            if not SECURITY_MODELS_AVAILABLE or not user:
                return {"risk_score": 0, "risk_factors": []}
            
            risk_factors = []
            total_risk = 0
            
            # Check user ban status
            active_bans = UserBan.objects.filter(
                user=user,
                is_active=True,
                expires_at__gt=timezone.now()
            ).count()
            
            if active_bans > 0:
                risk_factors.append("active_ban")
                total_risk += 60
            
            # Check recent security incidents
            recent_incidents = SecurityIncident.objects.filter(
                user=user,
                created_at__gte=timezone.now() - timedelta(days=30),
                severity__in=['high', 'critical']
            ).count()
            
            if recent_incidents > 0:
                risk_factors.append("recent_incidents")
                total_risk += recent_incidents * 10
            
            # Check device trust
            trusted_devices = TrustedDevice.objects.filter(
                user=user,
                is_trusted=True
            ).count()
            
            total_devices = DeviceInfo.objects.filter(user=user).count()
            if total_devices > 0:
                trust_ratio = trusted_devices / total_devices
                if trust_ratio < 0.5:
                    risk_factors.append("untrusted_devices")
                    total_risk += 20
            
            # Get risk score from model
            risk_score_entry = RiskScore.objects.filter(user=user).first()
            if risk_score_entry:
                model_risk = risk_score_entry.current_score
                total_risk = max(total_risk, model_risk)
                risk_factors.append(f"risk_score_{model_risk}")
            
            # Normalize to 0-100 scale
            normalized_risk = min(100, total_risk)
            
            return {
                "risk_score": normalized_risk,
                "risk_factors": risk_factors,
                "risk_level": SecurityService._get_risk_level(normalized_risk),
                "assessment_timestamp": timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in user risk assessment: {e}")
            return {"risk_score": 0, "risk_factors": [], "error": str(e)}

    @staticmethod
    def _get_risk_level(score: int) -> str:
        """Convert risk score to risk level"""
        if score >= 80:
            return "critical"
        elif score >= 60:
            return "high"
        elif score >= 40:
            return "medium"
        elif score >= 20:
            return "low"
        else:
            return "minimal"

    def check_device_trust(self, user, device_fingerprint: str) -> Dict[str, Any]:
        """
        Check if device is trusted for the user
        """
        try:
            if not SECURITY_MODELS_AVAILABLE:
                return {"is_trusted": False, "trust_score": 0}
            
            trusted_device = TrustedDevice.objects.filter(
                user=user,
                device_fingerprint=device_fingerprint,
                is_trusted=True
            ).first()
            
            if trusted_device:
                return {
                    "is_trusted": True,
                    "trust_score": 100,
                    "device_id": trusted_device.id,
                    "last_trusted_at": trusted_device.created_at
                }
            
            # Check if device exists in user's history
            existing_device = DeviceInfo.objects.filter(
                user=user,
                device_fingerprint=device_fingerprint
            ).first()
            
            if existing_device:
                # Calculate trust based on usage patterns
                trust_score = self._calculate_device_trust(existing_device)
                return {
                    "is_trusted": trust_score >= 70,
                    "trust_score": trust_score,
                    "device_id": existing_device.id,
                    "usage_count": existing_device.usage_count or 0
                }
            
            return {"is_trusted": False, "trust_score": 0}
            
        except Exception as e:
            logger.error(f"Error in device trust check: {e}")
            return {"is_trusted": False, "trust_score": 0}

    def _calculate_device_trust(self, device) -> int:
        """Calculate device trust score based on usage patterns"""
        try:
            trust_score = 50  # Base score
            
            # Add points for positive factors
            if device.trust_level == 'high':
                trust_score += 30
            elif device.trust_level == 'medium':
                trust_score += 15
            
            # Add points for usage history
            if device.usage_count and device.usage_count > 10:
                trust_score += 20
            
            # Subtract points for negative factors
            if device.is_suspicious:
                trust_score -= 40
            
            if device.risk_score and device.risk_score > 50:
                trust_score -= 30
            
            return max(0, min(100, trust_score))
            
        except Exception:
            return 50


class EnhancedRateLimitService:
    """
    Enhanced rate limiting service with multiple strategies and comprehensive tracking
    """

    def __init__(self):
        """Initialize Enhanced Rate Limit Service"""
        try:
            self.strategies = ['sliding_window', 'fixed_window', 'token_bucket']
            self.default_strategy = getattr(settings, 'RATE_LIMIT_STRATEGY', 'sliding_window')
            logger.info("EnhancedRateLimitService initialized")
        except Exception as e:
            logger.error(f"Failed to initialize EnhancedRateLimitService: {e}")

    def check_rate_limit(self, identifier: str, limit: int = 100, 
                       window_seconds: int = 3600, 
                       strategy: str = None) -> Dict[str, Any]:
        """
        Enhanced rate limiting with multiple strategies
        """
        try:
            strategy = strategy or self.default_strategy
            
            if strategy == 'sliding_window':
                return self._sliding_window_check(identifier, limit, window_seconds)
            elif strategy == 'fixed_window':
                return self._fixed_window_check(identifier, limit, window_seconds)
            elif strategy == 'token_bucket':
                return self._token_bucket_check(identifier, limit, window_seconds)
            else:
                return self._sliding_window_check(identifier, limit, window_seconds)
                
        except Exception as e:
            logger.error(f"Error in rate limit check: {e}")
            return {"is_limited": False, "error": str(e)}

    def _sliding_window_check(self, identifier: str, limit: int, window_seconds: int) -> Dict[str, Any]:
        """Sliding window rate limiting"""
        try:
            now = timezone.now()
            window_start = now - timedelta(seconds=window_seconds)
            
            # Count requests in the window
            cache_key = f"rate_limit_sliding:{identifier}"
            requests = cache.get(cache_key, [])
            
            # Filter old requests outside window
            recent_requests = [req_time for req_time in requests 
                            if req_time >= window_start.timestamp()]
            
            current_count = len(recent_requests)
            is_limited = current_count >= limit
            
            if is_limited:
                logger.warning(f"Rate limit exceeded for {identifier}: {current_count}/{limit}")
            else:
                # Add current request to the list
                recent_requests.append(now.timestamp())
                cache.set(cache_key, recent_requests, window_seconds)
            
            return {
                "is_limited": is_limited,
                "current_count": current_count,
                "limit": limit,
                "window_remaining": window_seconds - (now.timestamp() - min(recent_requests)) if recent_requests else window_seconds,
                "strategy": "sliding_window"
            }
            
        except Exception as e:
            logger.error(f"Error in sliding window check: {e}")
            return {"is_limited": False, "error": str(e)}

    def _fixed_window_check(self, identifier: str, limit: int, window_seconds: int) -> Dict[str, Any]:
        """Fixed window rate limiting"""
        try:
            cache_key = f"rate_limit_fixed:{identifier}"
            count = cache.get(cache_key, 0)
            
            is_limited = count >= limit
            
            if is_limited:
                logger.warning(f"Rate limit exceeded for {identifier}: {count}/{limit}")
            else:
                cache.set(cache_key, count + 1, window_seconds)
            
            return {
                "is_limited": is_limited,
                "current_count": count,
                "limit": limit,
                "window_remaining": window_seconds,
                "strategy": "fixed_window"
            }
            
        except Exception as e:
            logger.error(f"Error in fixed window check: {e}")
            return {"is_limited": False, "error": str(e)}

    def _token_bucket_check(self, identifier: str, limit: int, window_seconds: int) -> Dict[str, Any]:
        """Token bucket rate limiting"""
        try:
            cache_key = f"rate_limit_bucket:{identifier}"
            bucket_data = cache.get(cache_key, {"tokens": limit, "last_refill": timezone.now().timestamp()})
            
            # Refill tokens based on time elapsed
            now = timezone.now()
            time_elapsed = (now.timestamp() - bucket_data["last_refill"]) / window_seconds
            tokens_to_add = int(limit * time_elapsed)
            current_tokens = min(limit, bucket_data["tokens"] + tokens_to_add)
            
            is_limited = current_tokens < 1
            
            if not is_limited:
                # Consume one token
                current_tokens -= 1
                
            # Update bucket
            cache.set(cache_key, {
                "tokens": current_tokens,
                "last_refill": now.timestamp()
            }, window_seconds)
            
            return {
                "is_limited": is_limited,
                "tokens_remaining": current_tokens,
                "limit": limit,
                "strategy": "token_bucket"
            }
            
        except Exception as e:
            logger.error(f"Error in token bucket check: {e}")
            return {"is_limited": False, "error": str(e)}


class EnhancedBruteForceService:
    """
    Enhanced brute force detection with multiple attack patterns
    """

    def __init__(self):
        """Initialize Enhanced Brute Force Service"""
        try:
            self.attack_patterns = ['login', 'password_reset', 'api_key', '2fa']
            self.progressive_lockout = getattr(settings, 'PROGRESSIVE_LOCKOUT', True)
            logger.info("EnhancedBruteForceService initialized")
        except Exception as e:
            logger.error(f"Failed to initialize EnhancedBruteForceService: {e}")

    def check_brute_force(self, identifier: str, attack_type: str = 'login',
                          max_attempts: int = 5, lockout_seconds: int = 900) -> Dict[str, Any]:
        """
        Enhanced brute force detection with progressive lockout
        """
        try:
            if attack_type not in self.attack_patterns:
                raise ValueError(f"Unsupported attack type: {attack_type}")
            
            attempt_key = f"brute_force:{attack_type}:attempts:{identifier}"
            lockout_key = f"brute_force:{attack_type}:lockout:{identifier}"
            
            # Check current lockout status
            lockout_data = cache.get(lockout_key, {})
            
            if lockout_data.get('is_locked', False):
                remaining = lockout_data.get('expires_at', 0) - timezone.now().timestamp()
                if remaining > 0:
                    return {
                        "is_locked": True,
                        "remaining_time": int(remaining),
                        "lockout_level": lockout_data.get('level', 1),
                        "message": f"Account locked. Try again in {int(remaining)} seconds."
                    }
                else:
                    # Lockout expired, clear it
                    cache.delete(lockout_key)
                    cache.delete(attempt_key)
            
            # Get current attempts
            attempts = cache.get(attempt_key, 0)
            current_attempts = attempts + 1
            
            # Check if threshold exceeded
            if current_attempts >= max_attempts:
                # Progressive lockout
                lockout_level = self._calculate_lockout_level(current_attempts)
                lockout_duration = self._calculate_progressive_duration(lockout_level)
                
                lockout_data = {
                    'is_locked': True,
                    'expires_at': timezone.now().timestamp() + lockout_duration,
                    'level': lockout_level,
                    'attack_type': attack_type
                }
                
                cache.set(lockout_key, lockout_data, lockout_duration)
                cache.delete(attempt_key)
                
                logger.critical(f"Progressive brute force lockout: Level {lockout_level} for {identifier}")
                
                return {
                    "is_locked": True,
                    "remaining_time": lockout_duration,
                    "lockout_level": lockout_level,
                    "attack_type": attack_type,
                    "message": f"Account locked due to repeated failed attempts. Duration: {lockout_duration}s"
                }
            
            # Update attempt counter
            cache.set(attempt_key, current_attempts, lockout_seconds)
            
            return {
                "is_locked": False,
                "attempts": current_attempts,
                "max_attempts": max_attempts,
                "remaining_attempts": max_attempts - current_attempts,
                "attack_type": attack_type
            }
            
        except Exception as e:
            logger.error(f"Error in brute force check: {e}")
            return {"is_locked": False, "error": str(e)}

    def _calculate_lockout_level(self, attempts: int) -> int:
        """Calculate progressive lockout level"""
        if attempts >= 20:
            return 4  # Permanent lockout
        elif attempts >= 15:
            return 3  # 24 hours
        elif attempts >= 10:
            return 2  # 6 hours
        elif attempts >= 5:
            return 1  # 1 hour
        else:
            return 0

    def _calculate_progressive_duration(self, level: int) -> int:
        """Calculate progressive lockout duration"""
        durations = {
            1: 3600,    # 1 hour
            2: 21600,   # 6 hours
            3: 86400,   # 24 hours
            4: 604800    # Permanent (7 days)
        }
        return durations.get(level, 3600)

    def reset_brute_force(self, identifier: str, attack_type: str = 'login') -> None:
        """Reset brute force counters for specific attack type"""
        try:
            attempt_key = f"brute_force:{attack_type}:attempts:{identifier}"
            lockout_key = f"brute_force:{attack_type}:lockout:{identifier}"
            
            cache.delete(attempt_key)
            cache.delete(lockout_key)
            
            logger.info(f"Brute force counters reset for {identifier}:{attack_type}")
            
        except Exception as e:
            logger.error(f"Error resetting brute force counters: {e}")


# Legacy compatibility
RateLimitService = EnhancedRateLimitService