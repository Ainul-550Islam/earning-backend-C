# api/security/signals.py
"""
Enhanced Security Signals with comprehensive security model integration
Author: System Security Team
Version: 2.0.0

Production-ready signals for api.security with automatic security event handling,
real-time monitoring, and cross-app integration.
"""

import logging
from typing import Any, Optional
from datetime import datetime
from django.db.models.signals import (
    post_save, pre_save, post_delete, pre_delete, 
    m2m_changed, pre_init, post_init
)
from django.dispatch import receiver
from django.contrib.auth.signals import (
    user_logged_in, user_logged_out, user_login_failed,
    user_login_failed
)
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
import threading
from typing import Dict, List, Any, Optional, Type, Union, Callable
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from django.db import transaction
from django.dispatch import Signal, receiver
try:
    from .models import SecurityLog, SecurityIncident, ThreatIntelligence
except ImportError:
    pass
from .utils import SecurityUtils
from .helpers import TimeHelper, SecurityMetrics
from .monitoring import monitoring_manager
from .analytics import security_analytics
from typing import Dict, List, Any, Optional, Callable
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver, Signal
from django.db import models
from .helpers import SecurityMetrics
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass



logger = logging.getLogger(__name__)
User = get_user_model()

# Import security models for signal integration
try:
    from .models import (
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
    logger.warning(f"Security models import failed in signals: {e}")
    SECURITY_MODELS_AVAILABLE = False
    RiskScore = None
    FraudPattern = None
    RealTimeDetection = None
    SECURITY_MODELS_AVAILABLE = False


def _get_user_model():
    """Get user model safely"""
    try:
        from django.apps import apps
        from django.conf import settings
        return apps.get_model(settings.AUTH_USER_MODEL)
    except Exception as e:
        logger.error(f"Error getting user model: {e}")
        return None


# ============ CUSTOM SECURITY SIGNALS ============

# Custom signals for security events
security_event_detected = Signal()
security_breach_detected = Signal()
threat_intelligence_updated = Signal()
device_trust_changed = Signal()
user_risk_assessed = Signal()
security_policy_violated = Signal()
fraud_pattern_matched = Signal()
real_time_detection_triggered = Signal()
geolocation_anomaly_detected = Signal()
rate_limit_exceeded = Signal()
brute_force_detected = Signal()
pattern_learned = Signal()  # kwargs: pattern_key, pattern_info
knowledge_updated = Signal()
threat_detected = Signal()
security_insight_generated = Signal()
knowledge_base_synced = Signal()


# ============ AUTHENTICATION SIGNALS ============

@receiver(user_logged_in)
def handle_user_login(sender, request, user, **kwargs):
    """Handle successful user login"""
    try:
        if SECURITY_MODELS_AVAILABLE:
            # Log successful login
            SecurityLog.objects.create(
                user=user,
                security_type='login_success',
                severity='info',
                ip_address=_get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={
                    'login_time': timezone.now().isoformat(),
                    'session_id': request.session.session_key
                }
            )
            
            # Update device trust
            _update_device_trust_on_login(user, request)
            
            # Clear brute force counters
            _clear_brute_force_counters(user.username)
            
            # Check for suspicious login patterns
            _check_suspicious_login_patterns(user, request)
            
            logger.info(f"User login successful: {user.username}")
            
    except Exception as e:
        logger.error(f"Error handling user login: {e}")


@receiver(user_logged_out)
def handle_user_logout(sender, request, user, **kwargs):
    """Handle user logout"""
    try:
        if SECURITY_MODELS_AVAILABLE:
            # Log successful logout
            SecurityLog.objects.create(
                user=user,
                security_type='logout_success',
                severity='info',
                ip_address=_get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={
                    'logout_time': timezone.now().isoformat(),
                    'session_duration': _calculate_session_duration(request)
                }
            )
            
            # Update session activity
            _update_session_activity(user, request, 'logout')
            
            logger.info(f"User logout successful: {user.username}")
            
    except Exception as e:
        logger.error(f"Error handling user logout: {e}")


@receiver(user_login_failed)
def handle_login_failed(sender, request, credentials, **kwargs):
    """Handle failed login attempt"""
    try:
        username = credentials.get('username', 'unknown')
        
        if SECURITY_MODELS_AVAILABLE:
            # Log failed login attempt
            SecurityLog.objects.create(
                security_type='login_failed',
                severity='warning',
                ip_address=_get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={
                    'failed_time': timezone.now().isoformat(),
                    'username': username,
                    'failure_reason': 'invalid_credentials'
                }
            )
            
            # Trigger brute force check
            _trigger_brute_force_check(username, _get_client_ip(request))
            
            
            logger.warning(f"Login failed for user: {username}")
            
    except Exception as e:
        logger.error(f"Error handling login failed: {e}")


# ============ SECURITY MODEL SIGNALS ============

@receiver(post_save, sender=DeviceInfo)
def handle_device_info_saved(sender, instance, created, **kwargs):
    """Handle DeviceInfo model changes"""
    try:
        if created:
            # New device registered
            logger.info(f"New device registered for user {instance.user_id}: {instance.device_type}")
            
            # Trigger device trust evaluation
            security_event_detected.send(
                sender=sender,
                event_type='new_device_registered',
                data={
                    'device_id': instance.id,
                    'user_id': instance.user_id,
                    'device_type': instance.device_type,
                    'ip_address': instance.ip_address
                }
            )
        else:
            # Device updated
            logger.debug(f"Device info updated: {instance.id}")
            
    except Exception as e:
        logger.error(f"Error handling device info save: {e}")


@receiver(post_save, sender=SecurityLog)
def handle_security_log_saved(sender, instance, created, **kwargs):
    """Handle SecurityLog model changes"""
    try:
        if created:
            # New security event
            if instance.severity in ['high', 'critical']:
                # Trigger immediate alert for high severity events
                security_event_detected.send(
                    sender=sender,
                    event_type='high_severity_event',
                    data={
                        'log_id': instance.id,
                        'event_type': instance.security_type,
                        'severity': instance.severity,
                        'user_id': instance.user_id,
                        'ip_address': instance.ip_address
                    }
                )
            
            # Update user risk score if applicable
            if instance.user_id:
                _trigger_user_risk_assessment(instance.user)
                
    except Exception as e:
        logger.error(f"Error handling security log save: {e}")


@receiver(post_save, sender=UserBan)
def handle_user_ban_saved(sender, instance, created, **kwargs):
    """Handle UserBan model changes"""
    try:
        if created and instance.is_active:
            # New active ban
            logger.warning(f"User banned: {instance.user_id} - {instance.reason}")
            
            # Trigger security breach detection
            security_breach_detected.send(
                sender=sender,
                event_type='user_banned',
                data={
                    'ban_id': instance.id,
                    'user_id': instance.user_id,
                    'reason': instance.reason,
                    'ban_type': instance.ban_type,
                    'expires_at': instance.expires_at.isoformat() if instance.expires_at else None
                }
            )
            
            # Clear user sessions
            _clear_user_sessions(instance.user)
            
            # Invalidate trusted devices
            _invalidate_trusted_devices(instance.user)
            
    except Exception as e:
        logger.error(f"Error handling user ban save: {e}")


@receiver(post_save, sender=ThreatIntelligence)
def handle_threat_intel_saved(sender, instance, created, **kwargs):
    """Handle ThreatIntelligence model changes"""
    try:
        if created:
            # New threat intelligence
            logger.info(f"New threat intelligence: {instance.threat_type} - {instance.severity}")
            
            # Trigger threat intelligence update
            threat_intelligence_updated.send(
                sender=sender,
                event_type='new_threat_intelligence',
                data={
                    'threat_id': instance.id,
                    'threat_type': instance.threat_type,
                    'severity': instance.severity,
                    'indicators': instance.indicators,
                    'confidence': instance.confidence
                }
            )
            
            # Update related IP reputations
            _update_ip_reputations_from_threat(instance)
            
    except Exception as e:
        logger.error(f"Error handling threat intelligence save: {e}")


if RiskScore:
    @receiver(post_save, sender=RiskScore)
    def handle_risk_score_saved(sender, instance, created, **kwargs):
        """Handle RiskScore model changes"""
        try:
            user_risk_assessed.send(
                sender=sender,
                event_type='risk_score_updated',
                data={
                    'user_id': instance.user_id,
                    'current_score': instance.current_score,
                    'previous_score': instance.previous_score,
                    'calculated_at': instance.calculated_at.isoformat(),
                    'risk_factors': instance.risk_factors or []
                }
            )

            if instance.current_score >= 80:
                security_event_detected.send(
                    sender=sender,
                    event_type='high_risk_score',
                    data={
                        'user_id': instance.user_id,
                        'risk_score': instance.current_score,
                        'threshold_breached': True
                    }
                )

        except Exception as e:
            logger.error(f"Error handling risk score save: {e}")


# ============ UTILITY FUNCTIONS ============

def _get_client_ip(request) -> str:
    """Get client IP address safely"""
    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        else:
            return request.META.get('REMOTE_ADDR', '')
    except Exception:
        return ''


def _update_device_trust_on_login(user, request) -> None:
    """Update device trust on successful login"""
    try:
        if not SECURITY_MODELS_AVAILABLE:
            return
            
        device_fingerprint = _generate_device_fingerprint(request)
        if device_fingerprint:
            trusted_device = TrustedDevice.objects.filter(
                user=user,
                device_fingerprint=device_fingerprint
            ).first()
            
            if trusted_device:
                # Update last used timestamp
                trusted_device.last_used_at = timezone.now()
                trusted_device.usage_count = (trusted_device.usage_count or 0) + 1
                trusted_device.save()
            else:
                # Consider creating trusted device if usage pattern is good
                _consider_device_trust(user, device_fingerprint, request)
                
    except Exception as e:
        logger.error(f"Error updating device trust: {e}")


def _generate_device_fingerprint(request) -> str:
    """Generate device fingerprint from request"""
    try:
        import hashlib
        
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        ip_address = _get_client_ip(request)
        
        # Create fingerprint from multiple factors
        fingerprint_data = f"{user_agent}:{ip_address}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:32]
        
    except Exception as e:
        logger.error(f"Error generating device fingerprint: {e}")
        return ''


def _clear_brute_force_counters(identifier: str) -> None:
    """Clear brute force counters for identifier"""
    try:
        from django.core.cache import cache
        
        # Clear all brute force related cache keys
        patterns = ['login', 'password_reset', 'api_key', '2fa']
        for pattern in patterns:
            attempt_key = f"brute_force:{pattern}:attempts:{identifier}"
            lockout_key = f"brute_force:{pattern}:lockout:{identifier}"
            
            cache.delete(attempt_key)
            cache.delete(lockout_key)
            
        logger.info(f"Brute force counters cleared for {identifier}")
        
    except Exception as e:
        logger.error(f"Error clearing brute force counters: {e}")


def _trigger_brute_force_check(username: str, ip_address: str) -> None:
    """Trigger brute force check"""
    try:
        from ..services import EnhancedBruteForceService
        
        service = EnhancedBruteForceService()
        
        # Check both username and IP
        for identifier in [username, ip_address]:
            result = service.check_brute_force(identifier, 'login')
            if result.get('is_locked', False):
                logger.warning(f"Brute force lockout triggered for {identifier}")
                break
                
    except Exception as e:
        logger.error(f"Error triggering brute force check: {e}")


def _check_suspicious_login_patterns(user, request) -> None:
    """Check for suspicious login patterns"""
    try:
        if not SECURITY_MODELS_AVAILABLE:
            return
            
        # Check for login from unusual locations
        ip_address = _get_client_ip(request)
        recent_logins = SecurityLog.objects.filter(
            user=user,
            security_type='login_success',
            created_at__gte=timezone.now() - timezone.timedelta(hours=24)
        ).values_list('ip_address', flat=True)
        
        if len(set(recent_logins)) > 3:  # Login from 3+ different IPs
            security_event_detected.send(
                sender=None,
                event_type='suspicious_login_pattern',
                data={
                    'user_id': user.id,
                    'pattern_type': 'multiple_ips',
                    'ip_addresses': list(set(recent_logins)),
                    'time_window': '24h'
                }
            )
            
    except Exception as e:
        logger.error(f"Error checking suspicious login patterns: {e}")


def _calculate_session_duration(request) -> Optional[int]:
    """Calculate session duration"""
    try:
        if hasattr(request, 'session') and 'login_time' in request.session:
            login_time = request.session['login_time']
            if isinstance(login_time, str):
                from datetime import datetime
                login_time = datetime.fromisoformat(login_time)
            
            duration = (timezone.now() - login_time).total_seconds()
            return int(duration)
    except Exception:
        return None


def _update_session_activity(user, request, activity_type: str) -> None:
    """Update session activity"""
    try:
        if SECURITY_MODELS_AVAILABLE:
            SessionActivity.objects.create(
                user=user,
                activity_type=activity_type,
                ip_address=_get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                metadata={
                    'timestamp': timezone.now().isoformat(),
                    'session_id': request.session.session_key
                }
            )
    except Exception as e:
        logger.error(f"Error updating session activity: {e}")


def _clear_user_sessions(user) -> None:
    """Clear all user sessions"""
    try:
        from django.contrib.sessions.models import Session
        
        # Clear all sessions for this user
        Session.objects.filter(
            expire_date__gte=timezone.now()
        ).delete()
        
        logger.info(f"Cleared all sessions for user {user.id}")
        
    except Exception as e:
        logger.error(f"Error clearing user sessions: {e}")


def _invalidate_trusted_devices(user) -> None:
    """Invalidate all trusted devices for user"""
    try:
        if SECURITY_MODELS_AVAILABLE:
            TrustedDevice.objects.filter(user=user).update(is_trusted=False)
            
            device_trust_changed.send(
                sender=None,
                event_type='devices_invalidated',
                data={
                    'user_id': user.id,
                    'reason': 'user_banned',
                    'timestamp': timezone.now().isoformat()
                }
            )
            
    except Exception as e:
        logger.error(f"Error invalidating trusted devices: {e}")


def _trigger_user_risk_assessment(user) -> None:
    """Trigger user risk assessment"""
    try:
        if SECURITY_MODELS_AVAILABLE:
            from ..services import SecurityService
            
            service = SecurityService()
            risk_assessment = service.assess_user_risk(user)
            
            user_risk_assessed.send(
                sender=None,
                event_type='risk_assessment_completed',
                data=risk_assessment
            )
            
    except Exception as e:
        logger.error(f"Error triggering user risk assessment: {e}")


def _update_ip_reputations_from_threat(threat_intel) -> None:
    """Update IP reputations based on new threat intelligence"""
    try:
        if not (threat_intel and threat_intel.indicators):
            return
            
        # Update IP reputations for IPs in threat indicators
        for indicator in threat_intel.indicators:
            if ':' in indicator:  # Simple IP check
                try:
                    from api.fraud_detection.models import IPReputation
                    
                    ip_rep = IPReputation.objects.filter(
                        ip_address=indicator
                    ).first()
                    
                    if ip_rep:
                        # Update reputation based on threat
                        ip_rep.fraud_score = max(
                            ip_rep.fraud_score, 
                            _calculate_threat_score(threat_intel.severity)
                        )
                        ip_rep.is_blacklisted = (
                            ip_rep.is_blacklisted or 
                            threat_intel.severity in ['high', 'critical']
                        )
                        ip_rep.save()
                        
                except ImportError:
                    pass
                    
    except Exception as e:
        logger.error(f"Error updating IP reputations: {e}")


def _calculate_threat_score(severity: str) -> int:
    """Calculate threat score from severity"""
    severity_scores = {
        'low': 20,
        'medium': 40,
        'high': 70,
        'critical': 90
    }
    return severity_scores.get(severity, 30)


def _consider_device_trust(user, device_fingerprint: str, request) -> None:
    """Consider device for trust status"""
    try:
        if not SECURITY_MODELS_AVAILABLE:
            return
            
        # Check device usage history
        device_logs = SecurityLog.objects.filter(
            user=user,
            ip_address=_get_client_ip(request),
            security_type='login_success',
            created_at__gte=timezone.now() - timezone.timedelta(days=30)
        ).count()
        
        # Auto-trust device if used consistently for 30+ days
        if device_logs >= 20:  # ~20 logins in 30 days
            TrustedDevice.objects.get_or_create(
                user=user,
                device_fingerprint=device_fingerprint,
                defaults={
                    'is_trusted': True,
                    'trust_score': 85,
                    'device_name': request.META.get('HTTP_USER_AGENT', '')[:50]
                }
            )
            
            device_trust_changed.send(
                sender=None,
                event_type='device_auto_trusted',
                data={
                    'user_id': user.id,
                    'device_fingerprint': device_fingerprint,
                    'trust_score': 85,
                    'reason': 'consistent_usage'
                }
            )
            
    except Exception as e:
        logger.error(f"Error considering device trust: {e}")



# ============================================================================
# Content migrated from signals_cap.py
# ============================================================================


class SignalCapture:
    """Advanced signal capture and processing system"""
    
    def __init__(self):
        self.captured_signals = []
        self.signal_processors = {}
        self.signal_filters = {}
        self.signal_handlers = {}
        self.capture_enabled = True
        self.max_capture_size = 10000
        self.capture_timeout = 300  # 5 minutes
        self.lock = threading.Lock()
    
    def capture_signal(self, signal_name: str, sender: Any, **kwargs):
        """Capture and process a signal"""
        if not self.capture_enabled:
            return
        
        with self.lock:
            try:
                # Create signal record
                signal_record = {
                    'signal_name': signal_name,
                    'sender': str(sender),
                    'timestamp': timezone.now(),
                    'data': kwargs,
                    'processed': False,
                    'id': SecurityUtils.generate_uuid()
                }
                
                # Add to capture buffer
                self.captured_signals.append(signal_record)
                
                # Maintain buffer size
                if len(self.captured_signals) > self.max_capture_size:
                    self.captured_signals.pop(0)
                
                # Process signal immediately if configured
                if self.should_process_immediately(signal_name):
                    self.process_signal(signal_record)
                
                logger.debug(f"Captured signal: {signal_name} from {sender}")
                
            except Exception as e:
                logger.error(f"Error capturing signal {signal_name}: {e}")
    
    def should_process_immediately(self, signal_name: str) -> bool:
        """Check if signal should be processed immediately"""
        immediate_signals = getattr(settings, 'SECURITY_IMMEDIATE_SIGNALS', [
            'security_threat_detected',
            'security_incident_created',
            'security_breach_detected',
            'security_critical_alert'
        ])
        return signal_name in immediate_signals
    
    def process_signal(self, signal_record: Dict[str, Any]) -> Dict[str, Any]:
        """Process a captured signal"""
        try:
            signal_name = signal_record['signal_name']
            
            # Apply filters
            if not self.passes_filters(signal_record):
                signal_record['processed'] = True
                signal_record['filtered'] = True
                return {'status': 'filtered'}
            
            # Get processors for this signal
            processors = self.signal_processors.get(signal_name, [])
            
            results = []
            for processor in processors:
                try:
                    result = processor(signal_record)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error in signal processor {processor.__name__}: {e}")
                    results.append({'error': str(e)})
            
            # Mark as processed
            signal_record['processed'] = True
            signal_record['processing_results'] = results
            
            return {
                'status': 'processed',
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
            signal_record['processed'] = True
            signal_record['processing_error'] = str(e)
            return {'status': 'error', 'error': str(e)}
    
    def passes_filters(self, signal_record: Dict[str, Any]) -> bool:
        """Check if signal passes all filters"""
        signal_name = signal_record['signal_name']
        
        # Get filters for this signal
        filters = self.signal_filters.get(signal_name, [])
        
        for filter_func in filters:
            try:
                if not filter_func(signal_record):
                    return False
            except Exception as e:
                logger.error(f"Error in signal filter {filter_func.__name__}: {e}")
                return False
        
        return True
    
    def register_processor(self, signal_name: str, processor: Callable):
        """Register a signal processor"""
        if signal_name not in self.signal_processors:
            self.signal_processors[signal_name] = []
        
        self.signal_processors[signal_name].append(processor)
        logger.info(f"Registered processor for signal: {signal_name}")
    
    def register_filter(self, signal_name: str, filter_func: Callable):
        """Register a signal filter"""
        if signal_name not in self.signal_filters:
            self.signal_filters[signal_name] = []
        
        self.signal_filters[signal_name].append(filter_func)
        logger.info(f"Registered filter for signal: {signal_name}")
    
    def register_handler(self, signal_name: str, handler: Callable):
        """Register a signal handler"""
        if signal_name not in self.signal_handlers:
            self.signal_handlers[signal_name] = []
        
        self.signal_handlers[signal_name].append(handler)
        logger.info(f"Registered handler for signal: {signal_name}")
    
    def get_captured_signals(self, signal_name: str = None, 
                          start_time: datetime = None, 
                          end_time: datetime = None) -> List[Dict[str, Any]]:
        """Get captured signals with optional filtering"""
        with self.lock:
            signals = self.captured_signals.copy()
        
        # Filter by signal name
        if signal_name:
            signals = [s for s in signals if s['signal_name'] == signal_name]
        
        # Filter by time range
        if start_time:
            signals = [s for s in signals if s['timestamp'] >= start_time]
        
        if end_time:
            signals = [s for s in signals if s['timestamp'] <= end_time]
        
        return signals
    
    def get_signal_statistics(self) -> Dict[str, Any]:
        """Get signal capture statistics"""
        with self.lock:
            total_signals = len(self.captured_signals)
            processed_signals = len([s for s in self.captured_signals if s['processed']])
            
            # Count by signal type
            signal_counts = {}
            for signal in self.captured_signals:
                signal_name = signal['signal_name']
                signal_counts[signal_name] = signal_counts.get(signal_name, 0) + 1
            
            # Count by status
            status_counts = {
                'processed': len([s for s in self.captured_signals if s['processed']]),
                'unprocessed': len([s for s in self.captured_signals if not s['processed']]),
                'filtered': len([s for s in self.captured_signals if s.get('filtered', False)])
            }
            
            return {
                'total_signals': total_signals,
                'processed_signals': processed_signals,
                'processing_rate': (processed_signals / total_signals * 100) if total_signals > 0 else 0,
                'signal_counts': signal_counts,
                'status_counts': status_counts,
                'capture_enabled': self.capture_enabled,
                'buffer_size': len(self.captured_signals),
                'max_buffer_size': self.max_capture_size
            }
    
    def clear_captured_signals(self, signal_name: str = None):
        """Clear captured signals"""
        with self.lock:
            if signal_name:
                self.captured_signals = [
                    s for s in self.captured_signals 
                    if s['signal_name'] != signal_name
                ]
                logger.info(f"Cleared captured signals for: {signal_name}")
            else:
                self.captured_signals.clear()
                logger.info("Cleared all captured signals")
    
    def enable_capture(self):
        """Enable signal capture"""
        self.capture_enabled = True
        logger.info("Signal capture enabled")
    
    def disable_capture(self):
        """Disable signal capture"""
        self.capture_enabled = False
        logger.info("Signal capture disabled")
    
    def process_pending_signals(self) -> Dict[str, Any]:
        """Process all unprocessed signals"""
        with self.lock:
            unprocessed = [s for s in self.captured_signals if not s['processed']]
        
        results = {
            'processed': 0,
            'errors': 0,
            'filtered': 0
        }
        
        for signal_record in unprocessed:
            try:
                result = self.process_signal(signal_record)
                if result['status'] == 'processed':
                    results['processed'] += 1
                elif result['status'] == 'filtered':
                    results['filtered'] += 1
                else:
                    results['errors'] += 1
            except Exception as e:
                logger.error(f"Error processing pending signal: {e}")
                results['errors'] += 1
        
        return results



class SignalProcessor:
    """Base signal processor class"""
    
    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.config = {}
    
    def process(self, signal_record: Dict[str, Any]) -> Dict[str, Any]:
        """Process signal - override in subclasses"""
        raise NotImplementedError("Subclasses must implement process method")
    
    def enable(self):
        """Enable processor"""
        self.enabled = True
    
    def disable(self):
        """Disable processor"""
        self.enabled = False
    
    def set_config(self, config: Dict[str, Any]):
        """Set processor configuration"""
        self.config = config



class SecurityEventProcessor(SignalProcessor):
    """Security event signal processor"""
    
    def __init__(self):
        super().__init__("security_event_processor")
    
    def process(self, signal_record: Dict[str, Any]) -> Dict[str, Any]:
        """Process security event signal"""
        try:
            signal_name = signal_record['signal_name']
            data = signal_record['data']
            
            # Extract security event data
            user = data.get('user')
            event_type = data.get('event_type')
            severity = data.get('severity', 'info')
            
            # Create security log entry
            if event_type:
                SecurityLog.objects.create(
                    user=user,
                    security_type=event_type,
                    severity=severity,
                    description=f"Security event: {signal_name}",
                    metadata={
                        'signal_name': signal_name,
                        'signal_data': data
                    }
                )
            
            # Update monitoring metrics
            monitoring_manager.record_event(event_type, severity)
            
            # Check for immediate alerts
            if severity in ['critical', 'high']:
                self._trigger_alert(signal_record)
            
            return {
                'status': 'success',
                'action': 'security_event_processed',
                'event_type': event_type
            }
            
        except Exception as e:
            logger.error(f"Error processing security event: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _trigger_alert(self, signal_record: Dict[str, Any]):
        """Trigger immediate alert for critical events"""
        try:
            data = signal_record['data']
            severity = data.get('severity')
            
            # Create incident for critical events
            if severity == 'critical':
                SecurityIncident.objects.create(
                    title=f"Critical Security Event: {signal_record['signal_name']}",
                    incident_type='security_event',
                    severity='critical',
                    priority='critical',
                    description=str(data.get('description', 'Critical security event detected')),
                    metadata={
                        'signal_record': signal_record
                    }
                )
            
        except Exception as e:
            logger.error(f"Error triggering alert: {e}")



class ThreatIntelligenceProcessor(SignalProcessor):
    """Threat intelligence signal processor"""
    
    def __init__(self):
        super().__init__("threat_intelligence_processor")
    
    def process(self, signal_record: Dict[str, Any]) -> Dict[str, Any]:
        """Process threat intelligence signal"""
        try:
            signal_name = signal_record['signal_name']
            data = signal_record['data']
            
            # Extract threat data
            threat_type = data.get('threat_type')
            indicator = data.get('indicator')
            severity = data.get('severity', 'medium')
            source = data.get('source', 'signal_capture')
            
            # Create or update threat intelligence
            if threat_type and indicator:
                threat, created = ThreatIntelligence.objects.update_or_create(
                    indicator=indicator,
                    defaults={
                        'threat_type': threat_type,
                        'indicator_type': data.get('indicator_type', 'unknown'),
                        'severity': severity,
                        'source': source,
                        'description': data.get('description', f"Threat detected via {signal_name}"),
                        'is_active': True
                    }
                )
                
                action = 'created' if created else 'updated'
                
                # Log threat detection
                SecurityLog.objects.create(
                    security_type='threat_detected',
                    severity='high',
                    description=f"Threat intelligence {action}: {indicator}",
                    metadata={
                        'threat_id': str(threat.id),
                        'signal_name': signal_name,
                        'threat_data': data
                    }
                )
                
                return {
                    'status': 'success',
                    'action': f'threat_{action}',
                    'threat_id': str(threat.id)
                }
            
            return {
                'status': 'skipped',
                'reason': 'insufficient threat data'
            }
            
        except Exception as e:
            logger.error(f"Error processing threat intelligence: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }



class UserBehaviorProcessor(SignalProcessor):
    """User behavior signal processor"""
    
    def __init__(self):
        super().__init__("user_behavior_processor")
    
    def process(self, signal_record: Dict[str, Any]) -> Dict[str, Any]:
        """Process user behavior signal"""
        try:
            signal_name = signal_record['signal_name']
            data = signal_record['data']
            
            user = data.get('user')
            if not user:
                return {
                    'status': 'skipped',
                    'reason': 'no user data'
                }
            
            # Analyze user behavior patterns
            behavior_analysis = self._analyze_user_behavior(user, signal_record)
            
            # Update user risk score if needed
            if behavior_analysis['risk_change']:
                self._update_user_risk_score(user, behavior_analysis['risk_change'])
            
            # Check for anomaly alerts
            if behavior_analysis['anomaly_detected']:
                self._create_anomaly_alert(user, signal_record, behavior_analysis)
            
            return {
                'status': 'success',
                'action': 'user_behavior_analyzed',
                'analysis': behavior_analysis
            }
            
        except Exception as e:
            logger.error(f"Error processing user behavior: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _analyze_user_behavior(self, user: User, signal_record: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze user behavior patterns"""
        # Get recent user activity
        recent_activity = SecurityLog.objects.filter(
            user=user,
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        # Check for unusual patterns
        anomaly_detected = False
        risk_change = 0
        
        # High frequency activity
        if recent_activity > 1000:
            anomaly_detected = True
            risk_change += 10
        
        # Check signal-specific patterns
        signal_name = signal_record['signal_name']
        if 'failed' in signal_name.lower():
            risk_change += 5
        
        return {
            'recent_activity': recent_activity,
            'anomaly_detected': anomaly_detected,
            'risk_change': risk_change
        }
    
    def _update_user_risk_score(self, user: User, risk_change: int):
        """Update user risk score"""
        # This would integrate with user risk scoring system
        logger.info(f"Updating risk score for user {user.id}: {risk_change}")
    
    def _create_anomaly_alert(self, user: User, signal_record: Dict[str, Any], analysis: Dict[str, Any]):
        """Create anomaly alert"""
        SecurityLog.objects.create(
            user=user,
            security_type='anomaly_detected',
            severity='medium',
            description=f"User behavior anomaly detected: {signal_record['signal_name']}",
            metadata={
                'signal_record': signal_record,
                'analysis': analysis
            }
        )



class SignalFilter:
    """Base signal filter class"""
    
    def __init__(self, name: str):
        self.name = name
        self.enabled = True
    
    def filter(self, signal_record: Dict[str, Any]) -> bool:
        """Filter signal - return True to pass, False to block"""
        raise NotImplementedError("Subclasses must implement filter method")
    
    def enable(self):
        """Enable filter"""
        self.enabled = True
    
    def disable(self):
        """Disable filter"""
        self.enabled = False



class SeverityFilter(SignalFilter):
    """Filter signals by severity"""
    
    def __init__(self, min_severity: str = 'info'):
        super().__init__("severity_filter")
        self.min_severity = min_severity
        self.severity_levels = {
            'debug': 0,
            'info': 1,
            'warning': 2,
            'error': 3,
            'critical': 4
        }
    
    def filter(self, signal_record: Dict[str, Any]) -> bool:
        """Filter by minimum severity"""
        data = signal_record.get('data', {})
        severity = data.get('severity', 'info')
        
        min_level = self.severity_levels.get(self.min_severity, 1)
        current_level = self.severity_levels.get(severity, 1)
        
        return current_level >= min_level



class UserFilter(SignalFilter):
    """Filter signals by user"""
    
    def __init__(self, allowed_users: List[Union[int, str]] = None):
        super().__init__("user_filter")
        self.allowed_users = allowed_users or []
    
    def filter(self, signal_record: Dict[str, Any]) -> bool:
        """Filter by allowed users"""
        data = signal_record.get('data', {})
        user = data.get('user')
        
        if not self.allowed_users:
            return True  # No filter if no allowed users specified
        
        if not user:
            return False
        
        return str(user.id) in [str(u) for u in self.allowed_users]


# Global signal capture instance
signal_capture = SignalCapture()


# Register built-in processors
signal_capture.register_processor('security_event', SecurityEventProcessor().process)
signal_capture.register_processor('threat_intelligence', ThreatIntelligenceProcessor().process)
signal_capture.register_processor('user_behavior', UserBehaviorProcessor().process)

# Register built-in filters
signal_capture.register_filter('security_event', SeverityFilter('warning').filter)
signal_capture.register_filter('user_behavior', UserFilter().filter)


# Django signal integration

class DjangoSignalBridge:
    """Bridge between Django signals and capture system"""
    
    def __init__(self, capture_instance: SignalCapture):
        self.capture = capture_instance
        self._setup_django_signals()
    
    def _setup_django_signals(self):
        """Setup Django signal connections"""
        # Connect to built-in Django signals
        from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
        
        user_logged_in.connect(self._handle_user_login, sender=None)
        user_logged_out.connect(self._handle_user_logout, sender=None)
        user_login_failed.connect(self._handle_login_failed, sender=None)
        
        # Connect to model signals
        from django.db.models.signals import post_save, post_delete
        
        post_save.connect(self._handle_model_save, sender=None)
        post_delete.connect(self._handle_model_delete, sender=None)
    
    def _handle_user_login(self, sender, request, user, **kwargs):
        """Handle user login signal"""
        self.capture.capture_signal(
            'user_logged_in',
            sender=sender,
            user=user,
            request=request,
            ip_address=self._get_client_ip(request)
        )
    
    def _handle_user_logout(self, sender, request, user, **kwargs):
        """Handle user logout signal"""
        self.capture.capture_signal(
            'user_logged_out',
            sender=sender,
            user=user,
            request=request,
            ip_address=self._get_client_ip(request)
        )
    
    def _handle_login_failed(self, sender, credentials, request, **kwargs):
        """Handle login failed signal"""
        self.capture.capture_signal(
            'user_login_failed',
            sender=sender,
            credentials=credentials,
            request=request,
            ip_address=self._get_client_ip(request)
        )
    
    def _handle_model_save(self, sender, instance, created, raw, using, update_fields, **kwargs):
        """Handle model save signal"""
        self.capture.capture_signal(
            'model_saved',
            sender=sender,
            instance=instance,
            created=created,
            raw=raw,
            using=using,
            update_fields=update_fields
        )
    
    def _handle_model_delete(self, sender, instance, using, **kwargs):
        """Handle model delete signal"""
        self.capture.capture_signal(
            'model_deleted',
            sender=sender,
            instance=instance,
            using=using
        )
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# Initialize Django signal bridge
django_signal_bridge = DjangoSignalBridge(signal_capture)


# Export symbols
__all__ = [
    'SignalCapture',
    'signal_capture',
    'SignalProcessor',
    'SecurityEventProcessor',
    'ThreatIntelligenceProcessor',
    'UserBehaviorProcessor',
    'SignalFilter',
    'SeverityFilter',
    'UserFilter',
    'DjangoSignalBridge',
    'django_signal_bridge'
]



# ============================================================================
# Content migrated from signals_kb.py
# ============================================================================


class KnowledgeBaseManager:
    """Manager for security knowledge base operations"""
    
    def __init__(self):
        self.knowledge_base = {}
        self.learning_enabled = True
        self.confidence_threshold = 0.7
        self.cache_timeout = 3600  # 1 hour
    
    def add_knowledge(self, key: str, data: Dict[str, Any], confidence: float = 1.0):
        """Add knowledge to the knowledge base"""
        if confidence < self.confidence_threshold:
            logger.warning(f"Low confidence knowledge rejected: {key} ({confidence})")
            return False
        
        self.knowledge_base[key] = {
            'data': data,
            'confidence': confidence,
            'added_at': timezone.now(),
            'access_count': 0,
            'last_accessed': None
        }
        
        # Cache the knowledge
        cache.set(f"kb_{key}", self.knowledge_base[key], self.cache_timeout)
        
        logger.info(f"Added knowledge: {key} (confidence: {confidence})")
        return True
    
    def get_knowledge(self, key: str) -> Optional[Dict[str, Any]]:
        """Get knowledge from the knowledge base"""
        # Try cache first
        cached_knowledge = cache.get(f"kb_{key}")
        if cached_knowledge:
            # Update access statistics
            cached_knowledge['access_count'] += 1
            cached_knowledge['last_accessed'] = timezone.now()
            cache.set(f"kb_{key}", cached_knowledge, self.cache_timeout)
            return cached_knowledge
        
        # Try memory
        if key in self.knowledge_base:
            knowledge = self.knowledge_base[key]
            knowledge['access_count'] += 1
            knowledge['last_accessed'] = timezone.now()
            
            # Update cache
            cache.set(f"kb_{key}", knowledge, self.cache_timeout)
            
            return knowledge
        
        return None
    
    def update_knowledge(self, key: str, data: Dict[str, Any], confidence: float = None):
        """Update existing knowledge"""
        if key not in self.knowledge_base:
            return self.add_knowledge(key, data, confidence or 1.0)
        
        existing = self.knowledge_base[key]
        
        # Update with new data
        existing['data'].update(data)
        
        if confidence is not None:
            # Weight the confidence
            existing['confidence'] = (existing['confidence'] + confidence) / 2
        
        existing['updated_at'] = timezone.now()
        
        # Update cache
        cache.set(f"kb_{key}", existing, self.cache_timeout)
        
        logger.info(f"Updated knowledge: {key}")
        return True
    
    def search_knowledge(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search knowledge base"""
        results = []
        query_lower = query.lower()
        
        for key, knowledge in self.knowledge_base.items():
            # Simple text search (in production, use proper search)
            data_str = str(knowledge['data']).lower()
            
            if query_lower in data_str or query_lower in key.lower():
                results.append({
                    'key': key,
                    'knowledge': knowledge,
                    'relevance_score': self._calculate_relevance(query, key, knowledge)
                })
        
        # Sort by relevance and confidence
        results.sort(key=lambda x: (x['relevance_score'], x['knowledge']['confidence']), reverse=True)
        
        return results[:limit]
    
    def _calculate_relevance(self, query: str, key: str, knowledge: Dict[str, Any]) -> float:
        """Calculate relevance score for search results"""
        score = 0.0
        query_lower = query.lower()
        
        # Exact match in key
        if query_lower == key.lower():
            score += 1.0
        
        # Partial match in key
        elif query_lower in key.lower():
            score += 0.7
        
        # Match in data
        data_str = str(knowledge['data']).lower()
        if query_lower in data_str:
            score += 0.5
        
        # Boost by confidence
        score *= knowledge['confidence']
        
        # Boost by recent access
        if knowledge['last_accessed']:
            days_since_access = (timezone.now() - knowledge['last_accessed']).days
            if days_since_access < 7:
                score *= 1.2
        
        return score
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        total_entries = len(self.knowledge_base)
        
        if total_entries == 0:
            return {
                'total_entries': 0,
                'average_confidence': 0.0,
                'most_accessed': None,
                'recent_entries': []
            }
        
        total_confidence = sum(k['confidence'] for k in self.knowledge_base.values())
        avg_confidence = total_confidence / total_entries
        
        # Most accessed
        most_accessed = max(
            self.knowledge_base.items(),
            key=lambda x: x[1]['access_count']
        ) if self.knowledge_base else None
        
        # Recent entries (last 7 days)
        recent_cutoff = timezone.now() - timedelta(days=7)
        recent_entries = [
            (key, kb) for key, kb in self.knowledge_base.items()
            if kb.get('added_at', timezone.now()) > recent_cutoff
        ]
        
        return {
            'total_entries': total_entries,
            'average_confidence': avg_confidence,
            'most_accessed': {
                'key': most_accessed[0],
                'access_count': most_accessed[1]['access_count']
            } if most_accessed else None,
            'recent_entries': len(recent_entries)
        }



class PatternLearner:
    """Learns patterns from security events"""
    
    def __init__(self, knowledge_manager: KnowledgeBaseManager):
        self.knowledge_manager = knowledge_manager
        self.patterns = {}
        self.min_pattern_occurrences = 5
        self.learning_enabled = True
    
    def learn_from_security_log(self, log_entry: SecurityLog):
        """Learn patterns from security log entry"""
        if not self.learning_enabled:
            return
        
        # Extract features from log entry
        features = self._extract_log_features(log_entry)
        
        # Update pattern counts
        for feature, value in features.items():
            pattern_key = f"log_{feature}_{value}"
            
            if pattern_key not in self.patterns:
                self.patterns[pattern_key] = {
                    'count': 0,
                    'first_seen': timezone.now(),
                    'last_seen': timezone.now(),
                    'contexts': []
                }
            
            self.patterns[pattern_key]['count'] += 1
            self.patterns[pattern_key]['last_seen'] = timezone.now()
            
            # Add context
            context = {
                'user_id': log_entry.user.id if log_entry.user else None,
                'ip_address': log_entry.ip_address,
                'timestamp': log_entry.created_at.isoformat()
            }
            self.patterns[pattern_key]['contexts'].append(context)
        
        # Check for significant patterns
        self._check_significant_patterns()
    
    def learn_from_incident(self, incident: SecurityIncident):
        """Learn patterns from security incident"""
        if not self.learning_enabled:
            return
        
        # Extract features from incident
        features = self._extract_incident_features(incident)
        
        # Update pattern counts
        for feature, value in features.items():
            pattern_key = f"incident_{feature}_{value}"
            
            if pattern_key not in self.patterns:
                self.patterns[pattern_key] = {
                    'count': 0,
                    'first_seen': timezone.now(),
                    'last_seen': timezone.now(),
                    'contexts': []
                }
            
            self.patterns[pattern_key]['count'] += 1
            self.patterns[pattern_key]['last_seen'] = timezone.now()
            
            # Add context
            context = {
                'user_id': incident.user.id if incident.user else None,
                'incident_type': incident.incident_type,
                'severity': incident.severity,
                'timestamp': incident.opened_at.isoformat()
            }
            self.patterns[pattern_key]['contexts'].append(context)
        
        # Check for significant patterns
        self._check_significant_patterns()
    
    def _extract_log_features(self, log_entry: SecurityLog) -> Dict[str, Any]:
        """Extract features from security log"""
        features = {}
        
        # Basic features
        features['security_type'] = log_entry.security_type
        features['severity'] = log_entry.severity
        features['hour_of_day'] = log_entry.created_at.hour
        features['day_of_week'] = log_entry.created_at.weekday()
        
        # IP-based features
        if log_entry.ip_address:
            features['ip_prefix'] = '.'.join(log_entry.ip_address.split('.')[:2])
            features['is_private_ip'] = SecurityUtils.is_private_ip(log_entry.ip_address)
        
        # User-based features
        if log_entry.user:
            features['user_authenticated'] = True
            features['user_staff'] = log_entry.user.is_staff
        else:
            features['user_authenticated'] = False
        
        # Risk-based features
        if log_entry.risk_score:
            features['risk_level'] = 'high' if log_entry.risk_score > 70 else 'medium' if log_entry.risk_score > 30 else 'low'
        
        # Response time features
        if log_entry.response_time_ms:
            features['response_slow'] = log_entry.response_time_ms > 1000
        
        return features
    
    def _extract_incident_features(self, incident: SecurityIncident) -> Dict[str, Any]:
        """Extract features from security incident"""
        features = {}
        
        # Basic features
        features['incident_type'] = incident.incident_type
        features['severity'] = incident.severity
        features['priority'] = incident.priority
        features['hour_of_day'] = incident.opened_at.hour
        features['day_of_week'] = incident.opened_at.weekday()
        
        # System-based features
        if incident.affected_systems:
            features['affected_systems_count'] = len(incident.affected_systems)
            features['has_database_affected'] = 'database' in incident.affected_systems
            features['has_api_affected'] = 'api' in incident.affected_systems
        
        # Resolution-based features
        if incident.resolved_at:
            resolution_time = (incident.resolved_at - incident.opened_at).total_seconds()
            features['resolution_time_hours'] = resolution_time / 3600
            features['resolved_quickly'] = resolution_time < 3600  # Less than 1 hour
        
        return features
    
    def _check_significant_patterns(self):
        """Check for significant patterns and add to knowledge base"""
        for pattern_key, pattern_data in self.patterns.items():
            if pattern_data['count'] >= self.min_pattern_occurrences:
                # This is a significant pattern
                pattern_info = {
                    'type': 'learned_pattern',
                    'occurrences': pattern_data['count'],
                    'first_seen': pattern_data['first_seen'].isoformat(),
                    'last_seen': pattern_data['last_seen'].isoformat(),
                    'frequency': pattern_data['count'] / max(1, (timezone.now() - pattern_data['first_seen']).total_seconds()),
                    'contexts': pattern_data['contexts'][-10:]  # Last 10 contexts
                }
                
                # Add to knowledge base
                self.knowledge_manager.add_knowledge(
                    pattern_key,
                    pattern_info,
                    confidence=min(1.0, pattern_data['count'] / 20.0)  # Confidence based on occurrences
                )
                
                # Emit signal
                pattern_learned.send(
                    sender=self.__class__,
                    pattern_key=pattern_key,
                    pattern_info=pattern_info
                )



class ThreatIntelligenceLearner:
    """Learns from threat intelligence data"""
    
    def __init__(self, knowledge_manager: KnowledgeBaseManager):
        self.knowledge_manager = knowledge_manager
        self.threat_patterns = {}
        self.learning_enabled = True
    
    def learn_from_threat(self, threat: ThreatIntelligence):
        """Learn from threat intelligence"""
        if not self.learning_enabled:
            return
        
        # Extract threat features
        features = self._extract_threat_features(threat)
        
        # Update threat patterns
        for feature, value in features.items():
            pattern_key = f"threat_{feature}_{value}"
            
            if pattern_key not in self.threat_patterns:
                self.threat_patterns[pattern_key] = {
                    'count': 0,
                    'first_seen': timezone.now(),
                    'last_seen': timezone.now(),
                    'sources': set(),
                    'confidence_sum': 0.0
                }
            
            self.threat_patterns[pattern_key]['count'] += 1
            self.threat_patterns[pattern_key]['last_seen'] = timezone.now()
            self.threat_patterns[pattern_key]['sources'].add(threat.source)
            self.threat_patterns[pattern_key]['confidence_sum'] += threat.confidence
        
        # Check for significant threat patterns
        self._check_significant_threat_patterns()
    
    def _extract_threat_features(self, threat: ThreatIntelligence) -> Dict[str, Any]:
        """Extract features from threat intelligence"""
        features = {}
        
        # Basic features
        features['threat_type'] = threat.threat_type
        features['severity'] = threat.severity
        features['source'] = threat.source
        features['indicator_type'] = threat.indicator_type
        
        # IP-based features
        if threat.ip_range:
            ip_parts = threat.ip_range.split('.')
            if len(ip_parts) >= 2:
                features['ip_subnet'] = f"{ip_parts[0]}.{ip_parts[1]}"
        
        # Confidence-based features
        features['high_confidence'] = threat.confidence > 0.8
        features['medium_confidence'] = 0.5 <= threat.confidence <= 0.8
        features['low_confidence'] = threat.confidence < 0.5
        
        # Time-based features
        features['expires_soon'] = threat.expires_at and (threat.expires_at - timezone.now()).days < 7
        
        return features
    
    def _check_significant_threat_patterns(self):
        """Check for significant threat patterns"""
        for pattern_key, pattern_data in self.threat_patterns.items():
            if pattern_data['count'] >= 3:  # Significant threat pattern
                avg_confidence = pattern_data['confidence_sum'] / pattern_data['count']
                
                threat_info = {
                    'type': 'threat_pattern',
                    'occurrences': pattern_data['count'],
                    'sources': list(pattern_data['sources']),
                    'average_confidence': avg_confidence,
                    'first_seen': pattern_data['first_seen'].isoformat(),
                    'last_seen': pattern_data['last_seen'].isoformat()
                }
                
                # Add to knowledge base
                self.knowledge_manager.add_knowledge(
                    pattern_key,
                    threat_info,
                    confidence=min(1.0, avg_confidence)
                )



class SecurityInsightGenerator:
    """Generates security insights from learned patterns"""
    
    def __init__(self, knowledge_manager: KnowledgeBaseManager):
        self.knowledge_manager = knowledge_manager
        self.insight_cache = {}
        self.cache_timeout = 1800  # 30 minutes
    
    def generate_insights(self) -> List[Dict[str, Any]]:
        """Generate security insights from knowledge base"""
        insights = []
        
        # Get recent patterns
        recent_patterns = self._get_recent_patterns()
        
        # Analyze patterns for insights
        for pattern_key, pattern_data in recent_patterns.items():
            insight = self._analyze_pattern(pattern_key, pattern_data)
            if insight:
                insights.append(insight)
        
        # Get threat intelligence insights
        threat_insights = self._generate_threat_insights()
        insights.extend(threat_insights)
        
        # Get behavioral insights
        behavioral_insights = self._generate_behavioral_insights()
        insights.extend(behavioral_insights)
        
        # Sort insights by priority
        insights.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        # Cache insights
        cache_key = "security_insights"
        cache.set(cache_key, insights, self.cache_timeout)
        
        # Emit signal
        security_insight_generated.send(
            sender=self.__class__,
            insights=insights
        )
        
        return insights
    
    def _get_recent_patterns(self) -> Dict[str, Any]:
        """Get recent patterns from knowledge base"""
        recent_patterns = {}
        cutoff_time = timezone.now() - timedelta(days=7)
        
        for key, knowledge in self.knowledge_manager.knowledge_base.items():
            if knowledge.get('type') == 'learned_pattern':
                if knowledge.get('last_seen') and knowledge['last_seen'] > cutoff_time:
                    recent_patterns[key] = knowledge
        
        return recent_patterns
    
    def _analyze_pattern(self, pattern_key: str, pattern_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze a pattern for insights"""
        if not pattern_data.get('contexts'):
            return None
        
        contexts = pattern_data['contexts']
        occurrences = pattern_data['occurrences']
        
        # Generate insight based on pattern type
        if 'login_failed' in pattern_key:
            return self._analyze_login_failure_pattern(pattern_key, pattern_data)
        elif 'high_risk' in pattern_key:
            return self._analyze_high_risk_pattern(pattern_key, pattern_data)
        elif 'incident_data_breach' in pattern_key:
            return self._analyze_data_breach_pattern(pattern_key, pattern_data)
        elif 'threat_malware' in pattern_key:
            return self._analyze_malware_pattern(pattern_key, pattern_data)
        
        return None
    
    def _analyze_login_failure_pattern(self, pattern_key: str, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze login failure pattern"""
        contexts = pattern_data['contexts']
        
        # Extract unique IPs and users
        unique_ips = set(c.get('ip_address') for c in contexts if c.get('ip_address'))
        unique_users = set(c.get('user_id') for c in contexts if c.get('user_id'))
        
        # Calculate metrics
        avg_attempts_per_ip = len(contexts) / max(1, len(unique_ips))
        
        insight = {
            'type': 'security_insight',
            'category': 'authentication',
            'title': 'Suspicious Login Failure Pattern Detected',
            'description': f'Pattern {pattern_key} shows {len(contexts)} failed login attempts from {len(unique_ips)} unique IPs',
            'severity': 'high' if avg_attempts_per_ip > 5 else 'medium',
            'priority': 80 if avg_attempts_per_ip > 5 else 60,
            'recommendations': [
                'Consider implementing IP-based rate limiting',
                'Monitor these IP addresses for further suspicious activity',
                'Review user account security for affected users'
            ],
            'metrics': {
                'total_failures': len(contexts),
                'unique_ips': len(unique_ips),
                'unique_users': len(unique_users),
                'avg_attempts_per_ip': avg_attempts_per_ip
            },
            'pattern_key': pattern_key
        }
        
        return insight
    
    def _analyze_high_risk_pattern(self, pattern_key: str, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze high risk pattern"""
        contexts = pattern_data['contexts']
        
        # Extract time patterns
        hours = [c.get('timestamp', '') for c in contexts]
        hour_counts = {}
        for hour_str in hours:
            if hour_str:
                hour = datetime.fromisoformat(hour_str.replace('Z', '+00:00')).hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        peak_hour = max(hour_counts.items(), key=lambda x: x[1])[0] if hour_counts else 0
        
        insight = {
            'type': 'security_insight',
            'category': 'risk_assessment',
            'title': 'High Risk Activity Pattern Identified',
            'description': f'Pattern {pattern_key} shows {len(contexts)} high-risk events with peak activity at hour {peak_hour}',
            'severity': 'high',
            'priority': 90,
            'recommendations': [
                'Increase monitoring during peak activity hours',
                'Review security controls for affected systems',
                'Consider implementing additional authentication measures'
            ],
            'metrics': {
                'total_events': len(contexts),
                'peak_hour': peak_hour,
                'hour_distribution': hour_counts
            },
            'pattern_key': pattern_key
        }
        
        return insight
    
    def _analyze_data_breach_pattern(self, pattern_key: str, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze data breach pattern"""
        insight = {
            'type': 'security_insight',
            'category': 'data_protection',
            'title': 'Data Breach Pattern Detected',
            'description': f'Pattern {pattern_key} indicates potential data breach activity',
            'severity': 'critical',
            'priority': 95,
            'recommendations': [
                'Immediate investigation required',
                'Review data access logs',
                'Implement additional data protection measures',
                'Notify relevant stakeholders'
            ],
            'metrics': {
                'incidents': pattern_data['occurrences'],
                'frequency': pattern_data.get('frequency', 0)
            },
            'pattern_key': pattern_key
        }
        
        return insight
    
    def _analyze_malware_pattern(self, pattern_key: str, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze malware pattern"""
        insight = {
            'type': 'security_insight',
            'category': 'malware_detection',
            'title': 'Malware Activity Pattern Identified',
            'description': f'Pattern {pattern_key} shows recurring malware indicators',
            'severity': 'high',
            'priority': 85,
            'recommendations': [
                'Update antivirus signatures',
                'Scan affected systems',
                'Review network traffic patterns',
                'Implement additional malware detection rules'
            ],
            'metrics': {
                'detections': pattern_data['occurrences'],
                'sources': pattern_data.get('contexts', [])
            },
            'pattern_key': pattern_key
        }
        
        return insight
    
    def _generate_threat_insights(self) -> List[Dict[str, Any]]:
        """Generate threat intelligence insights"""
        insights = []
        
        # Get threat patterns from knowledge base
        threat_patterns = {
            key: kb for key, kb in self.knowledge_manager.knowledge_base.items()
            if kb.get('type') == 'threat_pattern'
        }
        
        # Analyze top threat types
        threat_type_counts = {}
        for pattern_key, pattern_data in threat_patterns.items():
            threat_type = pattern_key.split('_')[1] if '_' in pattern_key else 'unknown'
            threat_type_counts[threat_type] = threat_type_counts.get(threat_type, 0) + pattern_data['occurrences']
        
        if threat_type_counts:
            top_threat_type = max(threat_type_counts.items(), key=lambda x: x[1])
            
            insights.append({
                'type': 'security_insight',
                'category': 'threat_intelligence',
                'title': f'High Volume {top_threat_type[0].title()} Activity',
                'description': f'{top_threat_type[1]} {top_threat_type[0]} threats detected in recent period',
                'severity': 'medium',
                'priority': 70,
                'recommendations': [
                    'Enhance monitoring for this threat type',
                    'Review existing security controls',
                    'Update threat intelligence feeds'
                ],
                'metrics': {
                    'threat_count': top_threat_type[1],
                    'threat_type': top_threat_type[0]
                }
            })
        
        return insights
    
    def _generate_behavioral_insights(self) -> List[Dict[str, Any]]:
        """Generate behavioral insights"""
        insights = []
        
        # This would analyze user behavior patterns
        # For now, return empty list
        return insights


# Global instances
knowledge_manager = KnowledgeBaseManager()
pattern_learner = PatternLearner(knowledge_manager)
threat_learner = ThreatIntelligenceLearner(knowledge_manager)
insight_generator = SecurityInsightGenerator(knowledge_manager)


# Signal receivers
@receiver(post_save, sender=SecurityLog)
def security_log_saved(sender, instance, created, **kwargs):
    """Handle security log save"""
    if created:
        pattern_learner.learn_from_security_log(instance)


@receiver(post_save, sender=SecurityIncident)
def security_incident_saved(sender, instance, created, **kwargs):
    """Handle security incident save"""
    if created:
        pattern_learner.learn_from_incident(instance)


@receiver(post_save, sender=ThreatIntelligence)
def threat_intelligence_saved(sender, instance, created, **kwargs):
    """Handle threat intelligence save"""
    if created:
        threat_learner.learn_from_threat(instance)


# Export classes and utilities
__all__ = [
    'knowledge_updated',
    'threat_detected',
    'pattern_learned',
    'security_insight_generated',
    'knowledge_base_synced',
    'KnowledgeBaseManager',
    'PatternLearner',
    'ThreatIntelligenceLearner',
    'SecurityInsightGenerator',
    'knowledge_manager',
    'pattern_learner',
    'threat_learner',
    'insight_generator'
]