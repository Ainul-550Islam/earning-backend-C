"""
api/adapters/authentication.py
Authentication adapter for earning backend platform
"""
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework import serializers
import jwt
import secrets

logger = logging.getLogger(__name__)
User = get_user_model()


class CustomTokenAuthentication(serializers.Serializer):
    """Custom token authentication with enhanced security."""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    tenant_id = serializers.CharField(required=False)
    device_info = serializers.JSONField(required=False)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        tenant_id = attrs.get('tenant_id')
        
        if not email or not password:
            raise serializers.ValidationError('Email and password are required')
        
        # Validate tenant if provided
        if tenant_id:
            try:
                from tenants.models import Tenant
                if not Tenant.objects.filter(id=tenant_id, is_active=True).exists():
                    raise serializers.ValidationError('Invalid tenant')
            except Exception:
                pass  # Allow if tenant model not available
        
        return attrs


@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    """Enhanced user login with tenant support."""
    try:
        serializer = CustomTokenAuthentication(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': 'Validation failed',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        tenant_id = serializer.validated_data.get('tenant_id')
        device_info = serializer.validated_data.get('device_info', {})
        
        # Authenticate user
        user = authenticate(
            request=request,
            username=email,
            password=password,
            tenant_id=tenant_id
        )
        
        if not user:
            # Log failed login attempt
            _log_login_attempt(email, False, tenant_id, device_info)
            
            return Response({
                'success': False,
                'error': 'Invalid credentials',
                'details': 'Email or password is incorrect'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Check if user is active and not suspended
        if not user.is_active:
            return Response({
                'success': False,
                'error': 'Account inactive',
                'details': 'Your account has been deactivated'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if getattr(user, 'is_suspended', False):
            return Response({
                'success': False,
                'error': 'Account suspended',
                'details': 'Your account has been suspended'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Check 2FA requirement
        if getattr(user, 'two_factor_enabled', False):
            # Generate temporary token for 2FA verification
            temp_token = secrets.token_urlsafe(32)
            cache.set(f'2fa_temp_token_{user.id}', temp_token, timeout=300)
            
            return Response({
                'success': False,
                'error': '2FA required',
                'details': 'Two-factor authentication is required',
                'temp_token': temp_token
            }, status=status.HTTP_202_ACCEPTED)
        
        # Login successful
        login(request, user)
        
        # Create or get auth token
        token, created = Token.objects.get_or_create(user=user)
        
        # Log successful login
        _log_login_attempt(email, True, tenant_id, device_info)
        
        # Update user context
        _update_user_context(user, device_info)
        
        # Emit login event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('user.login_success', {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'device_info': device_info,
            'login_time': timezone.now().isoformat()
        })
        
        return Response({
            'success': True,
            'data': {
                'token': token.key,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_staff': user.is_staff,
                    'tenant_id': getattr(user, 'tenant_id', None),
                },
                'expires_at': created.isoformat() if created else None,
                'permissions': _get_user_permissions(user),
                'session_id': _create_session_id(user)
            },
            'message': 'Login successful'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AuthenticationAdapter] Error during login: {e}")
        return Response({
            'success': False,
            'error': 'Login failed',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_2fa_login(request):
    """Verify 2FA for login completion."""
    try:
        data = request.data
        temp_token = data.get('temp_token')
        code = data.get('code')
        
        if not temp_token or not code:
            return Response({
                'success': False,
                'error': 'Missing required fields',
                'details': 'temp_token and code are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get temp token from cache
        cached_token = cache.get(f'2fa_temp_token_{temp_token}')
        if not cached_token:
            return Response({
                'success': False,
                'error': 'Invalid or expired token',
                'details': 'Temporary token not found or expired'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user_id = cached_token.get('user_id')
        
        # Get user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': 'User not found',
                'details': 'User associated with token not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verify 2FA code
        import pyotp
        totp = pyotp.TOTP(user.two_factor_secret)
        
        if not totp.verify(code, valid_window=1):
            return Response({
                'success': False,
                'error': 'Invalid 2FA code',
                'details': 'Two-factor authentication code is invalid'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Clear temp token
        cache.delete(f'2fa_temp_token_{temp_token}')
        
        # Login successful
        login(request, user)
        
        # Create auth token
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'success': True,
            'data': {
                'token': token.key,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                },
                '2fa_verified': True
            },
            'message': '2FA verification successful'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AuthenticationAdapter] Error during 2FA verification: {e}")
        return Response({
            'success': False,
            'error': '2FA verification failed',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_user(request):
    """Enhanced user logout."""
    try:
        user = request.user
        
        # Delete auth token
        try:
            token = Token.objects.get(user=user)
            token.delete()
        except Token.DoesNotExist:
            pass
        
        # Logout user
        logout(request)
        
        # Clear user context cache
        _clear_user_context(user)
        
        # Emit logout event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('user.logout', {
            'user_id': user.id,
            'tenant_id': getattr(request, 'tenant_id', None),
            'logout_time': timezone.now().isoformat()
        })
        
        return Response({
            'success': True,
            'data': {
                'message': 'Logout successful',
                'cleared_sessions': True
            },
            'message': 'Logged out successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AuthenticationAdapter] Error during logout: {e}")
        return Response({
            'success': False,
            'error': 'Logout failed',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    """Refresh authentication token."""
    try:
        # Get current token from header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Token '):
            return Response({
                'success': False,
                'error': 'Invalid token format',
                'details': 'Token must be in format: Token <token>'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        current_token = auth_header.split(' ')[1]
        
        # Get token from database
        try:
            token = Token.objects.get(key=current_token)
        except Token.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Token not found',
                'details': 'Provided token is invalid'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Check if token is expired (24 hours)
        if timezone.now() - token.created > timezone.timedelta(hours=24):
            token.delete()
            return Response({
                'success': False,
                'error': 'Token expired',
                'details': 'Token has expired, please login again'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Create new token
        token.delete()
        new_token = Token.objects.create(user=token.user)
        
        return Response({
            'success': True,
            'data': {
                'token': new_token.key,
                'expires_at': (timezone.now() + timezone.timedelta(hours=24)).isoformat(),
                'user': {
                    'id': token.user.id,
                    'username': token.user.username,
                }
            },
            'message': 'Token refreshed successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AuthenticationAdapter] Error during token refresh: {e}")
        return Response({
            'success': False,
            'error': 'Token refresh failed',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_sessions(request):
    """Get user's active sessions."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user sessions from cache
        sessions = cache.get(f'user_sessions_{user.id}', [])
        
        # Add current session
        current_session = {
            'session_id': _create_session_id(user),
            'ip_address': _get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'created_at': timezone.now().isoformat(),
            'is_current': True
        }
        
        if not sessions:
            sessions = [current_session]
        else:
            # Update existing session or add new one
            for i, session in enumerate(sessions):
                if session.get('is_current'):
                    sessions[i] = current_session
                    break
            else:
                sessions.append(current_session)
        
        # Cache updated sessions
        cache.set(f'user_sessions_{user.id}', sessions, timeout=86400)
        
        return Response({
            'success': True,
            'data': {
                'user_id': user.id,
                'tenant_id': tenant_id,
                'sessions': sessions,
                'total_sessions': len(sessions),
                'max_sessions': getattr(user, 'max_concurrent_sessions', 3)
            },
            'message': 'Sessions retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AuthenticationAdapter] Error getting sessions: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve sessions',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def revoke_session(request):
    """Revoke a specific session."""
    try:
        user = request.user
        data = request.data
        session_id = data.get('session_id')
        
        if not session_id:
            return Response({
                'success': False,
                'error': 'Session ID required',
                'details': 'Please provide session ID to revoke'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user sessions
        sessions = cache.get(f'user_sessions_{user.id}', [])
        
        # Remove specified session
        updated_sessions = [s for s in sessions if s.get('session_id') != session_id]
        
        # Cache updated sessions
        cache.set(f'user_sessions_{user.id}', updated_sessions, timeout=86400)
        
        return Response({
            'success': True,
            'data': {
                'revoked_session_id': session_id,
                'remaining_sessions': len(updated_sessions)
            },
            'message': 'Session revoked successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AuthenticationAdapter] Error revoking session: {e}")
        return Response({
            'success': False,
            'error': 'Failed to revoke session',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _log_login_attempt(email: str, success: bool, tenant_id: str = None, device_info: Dict = None):
    """Log login attempt for security monitoring."""
    try:
        attempt_data = {
            'email': email,
            'success': success,
            'tenant_id': tenant_id,
            'device_info': device_info or {},
            'ip_address': _get_client_ip_from_request(),
            'user_agent': _get_user_agent_from_request(),
            'timestamp': timezone.now().isoformat()
        }
        
        # Store in cache for security monitoring
        failed_attempts = cache.get(f'failed_login_attempts_{email}', 0)
        if not success:
            failed_attempts += 1
            cache.set(f'failed_login_attempts_{email}', failed_attempts, timeout=3600)
        else:
            cache.delete(f'failed_login_attempts_{email}')
        
        # Store attempt in audit log
        import uuid
        attempt_id = str(uuid.uuid4())
        cache.set(f'login_attempt_{attempt_id}', attempt_data, timeout=86400 * 7)  # 7 days
        
    except Exception:
        pass


def _update_user_context(user, device_info: Dict):
    """Update user context after successful login."""
    try:
        context_data = {
            'user_id': user.id,
            'tenant_id': getattr(user, 'tenant_id', None),
            'login_time': timezone.now().isoformat(),
            'device_info': device_info or {},
            'ip_address': _get_client_ip_from_request(),
            'user_agent': _get_user_agent_from_request()
        }
        
        # Cache user context
        cache.set(f'user_context_{user.id}', context_data, timeout=86400)
        
    except Exception:
        pass


def _clear_user_context(user):
    """Clear user context after logout."""
    try:
        cache.delete(f'user_context_{user.id}')
        cache.delete(f'user_sessions_{user.id}')
    except Exception:
        pass


def _get_user_permissions(user) -> List[str]:
    """Get user permissions."""
    try:
        return list(user.get_all_permissions())
    except Exception:
        return []


def _create_session_id(user) -> str:
    """Create unique session ID."""
    import uuid
    return f"{user.id}_{uuid.uuid4().hex[:8]}"


def _get_client_ip(request) -> str:
    """Get client IP address."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip
    
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def _get_client_ip_from_request() -> str:
    """Get client IP from request context."""
    # This would typically be called from context
    return '127.0.0.1'


def _get_user_agent_from_request() -> str:
    """Get user agent from request context."""
    # This would typically be called from context
    return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
