"""
Security Signal Receivers
Django signal receivers for security monitoring and logging
"""

import logging
from datetime import datetime
from django.db.models.signals import post_save, pre_save, post_delete
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q
from typing import Dict, Any, Optional

from .models import (
    SecurityLog, DeviceInfo, UserSession, SecurityIncident,
    IPBlacklist, RiskScore, AuditTrail, PasswordHistory
)
from .hash_chain import HashChainedModel
from .utils import SecurityUtils, RateLimiter
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass



User = get_user_model()
logger = logging.getLogger('security.receivers')


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log successful user login"""
    try:
        # Get client IP and user agent
        ip_address = SecurityUtils.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Create or update device info
        device_fingerprint = SecurityUtils.generate_device_fingerprint(user_agent, ip_address)
        device, created = DeviceInfo.objects.get_or_create(
            user=user,
            device_fingerprint=device_fingerprint,
            defaults={
                'ip_address': ip_address,
                'user_agent': user_agent,
                'last_seen': timezone.now()
            }
        )
        
        if not created:
            device.last_seen = timezone.now()
            device.save(update_fields=['last_seen'])
        
        # Create user session
        session_key = request.session.session_key
        UserSession.objects.create(
            user=user,
            session_key=session_key,
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device,
            is_active=True
        )
        
        # Log security event
        SecurityLog.objects.create(
            user=user,
            security_type='login_success',
            severity='info',
            ip_address=ip_address,
            description=f'User {user.username} logged in successfully',
            metadata={
                'device_id': device.id,
                'session_key': session_key,
                'user_agent': user_agent
            }
        )
        
        # Update user risk score
        RiskScore.update_risk_score(user.id, login_success=True)
        
        # Check for suspicious login patterns
        _check_suspicious_login(user, ip_address, user_agent)
        
    except Exception as e:
        logger.error(f"Error logging user login: {e}")


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log user logout"""
    try:
        ip_address = SecurityUtils.get_client_ip(request)
        session_key = request.session.session_key
        
        # Deactivate user session
        UserSession.objects.filter(
            user=user,
            session_key=session_key,
            is_active=True
        ).update(is_active=False, ended_at=timezone.now())
        
        # Log security event
        SecurityLog.objects.create(
            user=user,
            security_type='logout',
            severity='info',
            ip_address=ip_address,
            description=f'User {user.username} logged out',
            metadata={
                'session_key': session_key
            }
        )
        
    except Exception as e:
        logger.error(f"Error logging user logout: {e}")


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    """Log failed login attempt"""
    try:
        ip_address = SecurityUtils.get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        username = credentials.get('username', 'unknown')
        
        # Check rate limiting
        cache_key = f"failed_login:{ip_address}:{username}"
        if RateLimiter.is_rate_limited(cache_key, limit=5, window=300):  # 5 attempts in 5 minutes
            # Create security incident for brute force attempt
            SecurityIncident.objects.create(
                incident_type='brute_force_attack',
                severity='high',
                title=f'Brute force attack detected for {username}',
                description=f'Multiple failed login attempts from {ip_address}',
                affected_systems=['authentication'],
                metadata={
                    'ip_address': ip_address,
                    'username': username,
                    'user_agent': user_agent,
                    'attempts': 6
                }
            )
            
            # Block IP temporarily
            IPBlacklist.objects.create(
                ip_address=ip_address,
                reason='Brute force attack',
                is_active=True,
                expires_at=timezone.now() + timezone.timedelta(hours=1)
            )
        
        # Log failed login
        SecurityLog.objects.create(
            user=None,  # User might not exist
            security_type='login_failed',
            severity='medium',
            ip_address=ip_address,
            description=f'Failed login attempt for {username}',
            metadata={
                'username': username,
                'user_agent': user_agent,
                'ip_address': ip_address
            }
        )
        
        # Update risk score if user exists
        try:
            user_obj = User.objects.get(username=username)
            RiskScore.update_risk_score(user_obj.id, login_failed=True)
        except User.DoesNotExist:
            pass
            
    except Exception as e:
        logger.error(f"Error logging failed login: {e}")


@receiver(pre_save, sender=User)
def monitor_user_changes(sender, instance, **kwargs):
    """Monitor user model changes"""
    try:
        if instance.pk:  # Only for existing users
            try:
                old_user = User.objects.get(pk=instance.pk)
                
                # Check for critical field changes
                critical_fields = ['email', 'username', 'is_active', 'is_staff', 'is_superuser']
                changes = {}
                
                for field in critical_fields:
                    old_value = getattr(old_user, field)
                    new_value = getattr(instance, field)
                    if old_value != new_value:
                        changes[field] = {
                            'old': str(old_value),
                            'new': str(new_value)
                        }
                
                if changes:
                    # Store changes in cache for post_save signal
                    cache_key = f"user_changes:{instance.pk}"
                    cache.set(cache_key, changes, timeout=60)
                    
            except User.DoesNotExist:
                pass
                
    except Exception as e:
        logger.error(f"Error monitoring user changes: {e}")


@receiver(post_save, sender=User)
def log_user_changes(sender, instance, created, **kwargs):
    """Log user creation and changes"""
    try:
        ip_address = getattr(instance, '_request_ip', '0.0.0.0')  # Get from middleware if available
        
        if created:
            # Log user creation
            SecurityLog.objects.create(
                user=instance,
                security_type='user_created',
                severity='info',
                ip_address=ip_address,
                description=f'User {instance.username} created',
                metadata={
                    'user_id': instance.id,
                    'email': instance.email
                }
            )
            
            # Initialize risk score
            RiskScore.objects.create(
                user=instance,
                current_score=50,  # Default medium risk
                risk_factors=['new_user']
            )
        else:
            # Check for changes
            cache_key = f"user_changes:{instance.pk}"
            changes = cache.get(cache_key)
            
            if changes:
                # Log user changes
                SecurityLog.objects.create(
                    user=instance,
                    security_type='user_updated',
                    severity='medium',
                    ip_address=ip_address,
                    description=f'User {instance.username} updated: {list(changes.keys())}',
                    metadata={
                        'changes': changes,
                        'user_id': instance.id
                    }
                )
                
                # Check for suspicious changes
                suspicious_changes = ['is_active', 'is_staff', 'is_superuser']
                if any(field in changes for field in suspicious_changes):
                    SecurityIncident.objects.create(
                        user=instance,
                        incident_type='privilege_escalation',
                        severity='high',
                        title=f'Privilege change detected for {instance.username}',
                        description=f'Suspicious privilege changes: {list(changes.keys())}',
                        metadata={
                            'changes': changes,
                            'ip_address': ip_address
                        }
                    )
                
                cache.delete(cache_key)
                
    except Exception as e:
        logger.error(f"Error logging user changes: {e}")


@receiver(post_save, sender=PasswordHistory)
def log_password_change(sender, instance, created, **kwargs):
    """Log password changes"""
    try:
        if created:
            ip_address = getattr(instance, '_request_ip', '0.0.0.0')
            
            # Log password change
            SecurityLog.objects.create(
                user=instance.user,
                security_type='password_changed',
                severity='medium',
                ip_address=ip_address,
                description=f'Password changed for user {instance.user.username}',
                metadata={
                    'password_id': instance.id,
                    'algorithm': instance.algorithm,
                    'strength_score': instance.strength_score
                }
            )
            
            # Update risk score (lower risk after password change)
            RiskScore.update_risk_score(instance.user.id, password_changed=True)
            
    except Exception as e:
        logger.error(f"Error logging password change: {e}")


@receiver(post_save, sender=SecurityIncident)
def handle_security_incident(sender, instance, created, **kwargs):
    """Handle security incident creation"""
    try:
        if created:
            # Log incident creation
            SecurityLog.objects.create(
                user=instance.user,
                security_type='incident_created',
                severity=instance.severity,
                description=f'Security incident created: {instance.title}',
                metadata={
                    'incident_id': instance.id,
                    'incident_type': instance.incident_type,
                    'severity': instance.severity
                }
            )
            
            # Check for automatic response
            if instance.severity == 'critical':
                _trigger_critical_incident_response(instance)
                
    except Exception as e:
        logger.error(f"Error handling security incident: {e}")


@receiver(post_save, sender=IPBlacklist)
def handle_ip_blacklist(sender, instance, created, **kwargs):
    """Handle IP blacklist changes"""
    try:
        if created:
            # Log IP blacklist
            SecurityLog.objects.create(
                security_type='ip_blacklisted',
                severity='high',
                description=f'IP {instance.ip_address} blacklisted: {instance.reason}',
                metadata={
                    'blacklist_id': instance.id,
                    'ip_address': instance.ip_address,
                    'reason': instance.reason,
                    'expires_at': instance.expires_at.isoformat() if instance.expires_at else None
                }
            )
            
            # Terminate active sessions from blacklisted IP
            UserSession.objects.filter(
                ip_address=instance.ip_address,
                is_active=True
            ).update(is_active=False, ended_at=timezone.now())
            
        elif not instance.is_active:
            # Log IP whitelist
            SecurityLog.objects.create(
                security_type='ip_whitelisted',
                severity='low',
                description=f'IP {instance.ip_address} removed from blacklist',
                metadata={
                    'blacklist_id': instance.id,
                    'ip_address': instance.ip_address
                }
            )
            
    except Exception as e:
        logger.error(f"Error handling IP blacklist: {e}")


@receiver(pre_save, sender=DeviceInfo)
def monitor_device_changes(sender, instance, **kwargs):
    """Monitor device information changes"""
    try:
        if instance.pk:  # Only for existing devices
            try:
                old_device = DeviceInfo.objects.get(pk=instance.pk)
                
                # Check for suspicious changes
                if old_device.ip_address != instance.ip_address:
                    # IP address changed - could be suspicious
                    cache_key = f"device_ip_change:{instance.pk}"
                    cache.set(cache_key, {
                        'old_ip': old_device.ip_address,
                        'new_ip': instance.ip_address,
                        'timestamp': timezone.now()
                    }, timeout=300)
                    
            except DeviceInfo.DoesNotExist:
                pass
                
    except Exception as e:
        logger.error(f"Error monitoring device changes: {e}")


@receiver(post_save, sender=DeviceInfo)
def handle_device_changes(sender, instance, created, **kwargs):
    """Handle device information changes"""
    try:
        if not created:
            # Check for IP changes
            cache_key = f"device_ip_change:{instance.pk}"
            ip_change = cache.get(cache_key)
            
            if ip_change:
                # Log suspicious IP change
                SecurityLog.objects.create(
                    user=instance.user,
                    security_type='device_ip_changed',
                    severity='medium',
                    description=f'Device IP changed from {ip_change["old_ip"]} to {ip_change["new_ip"]}',
                    metadata={
                        'device_id': instance.id,
                        'old_ip': ip_change['old_ip'],
                        'new_ip': ip_change['new_ip'],
                        'timestamp': ip_change['timestamp'].isoformat()
                    }
                )
                
                # Update risk score
                RiskScore.update_risk_score(instance.user.id, device_ip_changed=True)
                
                cache.delete(cache_key)
                
    except Exception as e:
        logger.error(f"Error handling device changes: {e}")


def _check_suspicious_login(user, ip_address, user_agent):
    """Check for suspicious login patterns"""
    try:
        suspicious_indicators = []
        
        # Check for multiple concurrent sessions
        active_sessions = UserSession.objects.filter(
            user=user,
            is_active=True
        ).count()
        
        if active_sessions > 3:
            suspicious_indicators.append('multiple_sessions')
        
        # Check for new location
        recent_sessions = UserSession.objects.filter(
            user=user,
            is_active=True,
            created_at__gte=timezone.now() - timezone.timedelta(hours=1)
        ).exclude(ip_address=ip_address)
        
        if recent_sessions.exists():
            suspicious_indicators.append('new_location')
        
        # Check for unusual time
        current_hour = timezone.now().hour
        if current_hour < 6 or current_hour > 22:  # Unusual hours
            suspicious_indicators.append('unusual_time')
        
        # Create security incident if suspicious
        if len(suspicious_indicators) >= 2:
            SecurityIncident.objects.create(
                user=user,
                incident_type='suspicious_login',
                severity='medium',
                title=f'Suspicious login detected for {user.username}',
                description=f'Login with suspicious indicators: {", ".join(suspicious_indicators)}',
                metadata={
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'indicators': suspicious_indicators,
                    'active_sessions': active_sessions
                }
            )
            
    except Exception as e:
        logger.error(f"Error checking suspicious login: {e}")


def _trigger_critical_incident_response(incident):
    """Trigger automatic response for critical incidents"""
    try:
        # Log critical incident
        SecurityLog.objects.create(
            security_type='critical_incident',
            severity='critical',
            description=f'Critical incident triggered: {incident.title}',
            metadata={
                'incident_id': incident.id,
                'incident_type': incident.incident_type,
                'auto_response': True
            }
        )
        
        # Implement automatic response based on incident type
        if incident.incident_type == 'data_breach':
            # Force password reset for affected users
            if incident.user:
                incident.user.set_unusable_password()
                incident.user.save()
        
        elif incident.incident_type == 'account_takeover':
            # Terminate all user sessions
            UserSession.objects.filter(
                user=incident.user,
                is_active=True
            ).update(is_active=False, ended_at=timezone.now())
            
            # Block suspicious IPs
            recent_sessions = UserSession.objects.filter(
                user=incident.user,
                created_at__gte=timezone.now() - timezone.timedelta(days=1)
            ).values_list('ip_address', flat=True).distinct()
            
            for ip in recent_sessions:
                IPBlacklist.objects.get_or_create(
                    ip_address=ip,
                    defaults={
                        'reason': 'Account takeover incident',
                        'is_active': True,
                        'expires_at': timezone.now() + timezone.timedelta(days=7)
                    }
                )
        
        elif incident.incident_type == 'brute_force_attack':
            # Block attacking IP
            if 'ip_address' in incident.metadata:
                IPBlacklist.objects.get_or_create(
                    ip_address=incident.metadata['ip_address'],
                    defaults={
                        'reason': 'Brute force attack',
                        'is_active': True,
                        'expires_at': timezone.now() + timezone.timedelta(days=1)
                    }
                )
        
        # Send notification (implement notification service)
        logger.warning(f"Critical incident auto-response triggered: {incident.title}")
        
    except Exception as e:
        logger.error(f"Error in critical incident response: {e}")


@receiver(pre_save)
def update_hash_chain_on_save(sender, instance, **kwargs):
    """
    Update hash chain when a HashChainedModel is saved
    """
    if isinstance(instance, HashChainedModel):
        try:
            # Update integrity hash before saving
            instance.update_integrity_hash()
            logger.debug(f"Updated hash chain for {sender.__name__}")
        except Exception as e:
            logger.error(f"Error updating hash chain: {e}")


@receiver(post_save)
def verify_hash_chain_after_save(sender, instance, created, **kwargs):
    """
    Verify hash chain after a HashChainedModel is saved
    """
    if isinstance(instance, HashChainedModel):
        try:
            # Verify integrity after save
            is_valid = instance.verify_integrity()
            
            if created:
                logger.info(f"Created new {sender.__name__} with hash chain position {instance.chain_position}")
            elif not is_valid:
                logger.warning(f"Hash chain verification failed for {sender.__name__} (position {instance.chain_position})")
                
        except Exception as e:
            logger.error(f"Error verifying hash chain: {e}")


# Export all receiver functions
__all__ = [
    'log_user_login',
    'log_user_logout', 
    'log_failed_login',
    'monitor_user_changes',
    'log_user_changes',
    'log_password_change',
    'handle_security_incident',
    'handle_ip_blacklist',
    'monitor_device_changes',
    'handle_device_changes',
    'update_hash_chain_on_save',
    'verify_hash_chain_after_save'
]