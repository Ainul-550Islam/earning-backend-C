"""
api/adapters/security.py
Security adapter for earning backend platform
"""
import logging
from typing import Dict, Any, Optional
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.decorators import login_required

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def security_profile(request):
    """Get user security profile and settings."""
    try:
        user = request.user
        
        # Get security context
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        security_data = {
            'user_id': user.id,
            'tenant_id': getattr(request, 'tenant_id', None),
            'security_settings': {
                'two_factor_enabled': getattr(user, 'two_factor_enabled', False),
                'email_notifications': getattr(user, 'email_notifications', True),
                'sms_notifications': getattr(user, 'sms_notifications', False),
                'login_alerts': getattr(user, 'login_alerts', True),
                'session_timeout': getattr(user, 'session_timeout', 3600),
                'max_concurrent_sessions': getattr(user, 'max_concurrent_sessions', 3),
            },
            'fraud_analysis': {
                'fraud_score': ctx.fraud_score,
                'is_fraud_flagged': ctx.is_fraud_flagged,
                'is_high_risk': ctx.is_high_risk,
                'risk_factors': {
                    'suspicious_login_attempts': cache.get(f'failed_login_{user.id}', 0),
                    'unusual_device_access': cache.get(f'unusual_device_{user.id}', False),
                    'geolocation_anomaly': cache.get(f'geo_anomaly_{user.id}', False),
                    'velocity_violations': cache.get(f'velocity_violations_{user.id}', 0),
                }
            },
            'access_control': {
                'ip_whitelist': getattr(user, 'ip_whitelist', []),
                'device_restrictions': getattr(user, 'device_restrictions', {}),
                'time_restrictions': getattr(user, 'time_restrictions', {}),
                'geo_restrictions': getattr(user, 'geo_restrictions', {}),
            },
            'audit_log': {
                'last_login': getattr(user, 'last_login', None),
                'last_password_change': getattr(user, 'last_password_change', None),
                'last_2fa_setup': getattr(user, 'last_2fa_setup', None),
                'failed_login_attempts': cache.get(f'failed_login_{user.id}', 0),
                'account_locked': getattr(user, 'account_locked', False),
            }
        }
        
        return Response({
            'success': True,
            'data': security_data,
            'message': 'Security profile retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SecurityAdapter] Error getting security profile: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve security profile',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_security_settings(request):
    """Update user security settings."""
    try:
        user = request.user
        data = request.data
        
        # Update security settings
        security_settings = data.get('security_settings', {})
        
        # Update two-factor authentication
        if 'two_factor_enabled' in security_settings:
            user.two_factor_enabled = security_settings['two_factor_enabled']
            if security_settings['two_factor_enabled']:
                user.last_2fa_setup = timezone.now()
        
        # Update notification preferences
        if 'email_notifications' in security_settings:
            user.email_notifications = security_settings['email_notifications']
        if 'sms_notifications' in security_settings:
            user.sms_notifications = security_settings['sms_notifications']
        
        # Update session settings
        if 'session_timeout' in security_settings:
            user.session_timeout = security_settings['session_timeout']
        if 'max_concurrent_sessions' in security_settings:
            user.max_concurrent_sessions = security_settings['max_concurrent_sessions']
        
        user.save()
        
        # Log security setting update
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('user.security_settings_updated', {
            'user_id': user.id,
            'updated_settings': security_settings,
            'updated_at': timezone.now().isoformat()
        })
        
        return Response({
            'success': True,
            'data': {'updated_settings': security_settings},
            'message': 'Security settings updated successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SecurityAdapter] Error updating security settings: {e}")
        return Response({
            'success': False,
            'error': 'Failed to update security settings',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def setup_2fa(request):
    """Setup two-factor authentication for user."""
    try:
        user = request.user
        data = request.data
        
        # Generate 2FA secret
        import pyotp
        totp_secret = pyotp.random_base32()
        
        # Store 2FA secret (in production, encrypt this)
        user.two_factor_secret = totp_secret
        user.two_factor_enabled = True
        user.last_2fa_setup = timezone.now()
        user.save()
        
        # Generate QR code for setup
        import qrcode
        qr = qrcode.QRCode(
            f"otpauth://totp/EarningBackend:{user.username}?secret={totp_secret}&issuer=EarningBackend"
        )
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 for API response
        import io
        import base64
        buffer = io.BytesIO()
        qr_image.save(buffer, format='PNG')
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Log 2FA setup
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('user.2fa_enabled', {
            'user_id': user.id,
            'setup_method': 'totp',
            'setup_at': timezone.now().isoformat()
        })
        
        return Response({
            'success': True,
            'data': {
                'totp_secret': totp_secret,
                'qr_code': qr_base64,
                'backup_codes': [pyotp.random_base32()[:8] for _ in range(10)],
                'instructions': 'Scan QR code with your authenticator app'
            },
            'message': '2FA setup completed successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SecurityAdapter] Error setting up 2FA: {e}")
        return Response({
            'success': False,
            'error': 'Failed to setup 2FA',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_2fa(request):
    """Verify two-factor authentication code."""
    try:
        user = request.user
        data = request.data
        
        code = data.get('code')
        if not code:
            return Response({
                'success': False,
                'error': '2FA code required',
                'details': 'Please provide the 2FA code from your authenticator app'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify TOTP code
        import pyotp
        totp = pyotp.TOTP(user.two_factor_secret)
        
        if not totp.verify(code, valid_window=1):
            # Log failed 2FA attempt
            failed_attempts = cache.get(f'2fa_failed_{user.id}', 0) + 1
            cache.set(f'2fa_failed_{user.id}', failed_attempts, timeout=300)
            
            if failed_attempts >= 3:
                user.account_locked = True
                user.save()
                
                from api.tasks.integration.event_bus import EventBus
                EventBus.emit('user.account_locked', {
                    'user_id': user.id,
                    'reason': '2fa_failure_exceeded',
                    'locked_at': timezone.now().isoformat()
                })
            
            return Response({
                'success': False,
                'error': 'Invalid 2FA code',
                'details': f'Failed attempts: {failed_attempts}'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Clear failed attempts on success
        cache.delete(f'2fa_failed_{user.id}')
        
        # Log successful 2FA verification
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('user.2fa_verified', {
            'user_id': user.id,
            'verified_at': timezone.now().isoformat()
        })
        
        return Response({
            'success': True,
            'data': {'verified': True},
            'message': '2FA verification successful'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SecurityAdapter] Error verifying 2FA: {e}")
        return Response({
            'success': False,
            'error': 'Failed to verify 2FA',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def security_audit_log(request):
    """Get user security audit log."""
    try:
        user = request.user
        limit = int(request.GET.get('limit', 100))
        offset = int(request.GET.get('offset', 0))
        
        # Get security events from cache
        security_events = []
        for i in range(offset, min(offset + limit, 100)):
            event_key = f'security_event_{user.id}_{i}'
            event = cache.get(event_key)
            if event:
                security_events.append(event)
        
        return Response({
            'success': True,
            'data': {
                'user_id': user.id,
                'total_events': len(security_events),
                'events': security_events,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'has_more': len(security_events) == limit
                }
            },
            'message': 'Security audit log retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SecurityAdapter] Error getting audit log: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve audit log',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def revoke_sessions(request):
    """Revoke all active sessions except current."""
    try:
        user = request.user
        
        # Clear user cache
        cache.delete(f'user_sessions_{user.id}')
        
        # Log session revocation
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('user.sessions_revoked', {
            'user_id': user.id,
            'revoked_at': timezone.now().isoformat(),
            'revoked_by': 'user_request'
        })
        
        return Response({
            'success': True,
            'data': {'sessions_revoked': True},
            'message': 'All sessions revoked successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SecurityAdapter] Error revoking sessions: {e}")
        return Response({
            'success': False,
            'error': 'Failed to revoke sessions',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
