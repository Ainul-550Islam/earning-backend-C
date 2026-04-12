# api/users/views_2fa_session.py
# ============================================================
# 2FA + Session Management API Views
# এই file টা users/views.py তে import করো অথবা users/urls.py তে directly add করো
# ============================================================

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from django.core.cache import cache
import logging

from .services.TOTPService import TOTPService
from .services.SessionService import SessionService
from .services.OTPService import OTPService
from .services.TokenService import TokenService
from .models import User, SecuritySettings, LoginHistory
from .utils import get_client_ip

logger = logging.getLogger(__name__)


# ============================================================
# 2FA SETUP VIEWS
# ============================================================

class TwoFASetupView(APIView):
    """
    POST /api/users/2fa/setup/
    2FA setup শুরু করো — QR code return করবে।
    User টা Google Authenticator এ scan করবে।
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # Check if 2FA already enabled
        sec = SecuritySettings.objects.filter(user=user).first()
        if sec and sec.two_factor_enabled:
            return Response({
                'error': '2FA ইতিমধ্যে চালু আছে। আগে disable করুন।'
            }, status=status.HTTP_400_BAD_REQUEST)

        result = TOTPService.setup_2fa(user)
        return Response({
            'success': True,
            'qr_code': result['qr_code'],
            'secret': result['secret'],
            'manual_entry_key': result['manual_entry_key'],
            'instructions': result['instructions'],
            'note': 'QR scan করার পর confirm endpoint এ code দিয়ে verify করুন।'
        })


class TwoFAConfirmView(APIView):
    """
    POST /api/users/2fa/confirm/
    Body: {"code": "123456"}
    QR scan করার পর code দিয়ে 2FA activate করো।
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '').strip()
        if not code or len(code) != 6 or not code.isdigit():
            return Response({
                'error': 'Valid 6-digit code দিন।'
            }, status=status.HTTP_400_BAD_REQUEST)

        result = TOTPService.confirm_and_enable_2fa(request.user, code)

        if not result['success']:
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'message': result['message'],
            'backup_codes': result['backup_codes'],
            'warning': result['warning']
        })


class TwoFADisableView(APIView):
    """
    POST /api/users/2fa/disable/
    Body: {"password": "your_password"}
    Password confirm করে 2FA বন্ধ করো।
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        password = request.data.get('password', '')
        if not password:
            return Response({'error': 'Password দিন।'}, status=status.HTTP_400_BAD_REQUEST)

        result = TOTPService.disable_2fa(request.user, password)

        if not result['success']:
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'message': result['message']})


class TwoFAStatusView(APIView):
    """
    GET /api/users/2fa/status/
    2FA status check করো।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        sec = SecuritySettings.objects.filter(user=user).first()

        return Response({
            'two_factor_enabled': sec.two_factor_enabled if sec else False,
            'method': sec.two_factor_method if sec else None,
            'backup_codes_remaining': len(sec.backup_codes) if sec and sec.backup_codes else 0,
        })


class TwoFARegenerateBackupCodesView(APIView):
    """
    POST /api/users/2fa/backup-codes/regenerate/
    Body: {"password": "your_password"}
    নতুন backup codes তৈরি করো (পুরনো codes invalid হবে)।
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        password = request.data.get('password', '')
        if not request.user.check_password(password):
            return Response({'error': 'Password ভুল।'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            sec = SecuritySettings.objects.get(user=request.user, two_factor_enabled=True)
        except SecuritySettings.DoesNotExist:
            return Response({'error': '2FA চালু নেই।'}, status=status.HTTP_400_BAD_REQUEST)

        raw_codes = TOTPService.generate_backup_codes(10)
        hashed = [TOTPService.hash_backup_code(c) for c in raw_codes]
        sec.backup_codes = hashed
        sec.save(update_fields=['backup_codes'])

        return Response({
            'success': True,
            'backup_codes': raw_codes,
            'warning': 'এই codes আর দেখানো হবে না। এখনই save করুন।'
        })


# ============================================================
# LOGIN WITH 2FA SUPPORT
# ============================================================

class LoginWith2FAView(APIView):
    """
    POST /api/users/auth/login/
    Step 1: username/password দিলে।
    - 2FA নেই → সরাসরি token দেয়।
    - 2FA আছে → requires_2fa: true + temp_token দেয়।

    Step 2 (2FA আছে):
    POST /api/users/auth/login/verify-2fa/
    Body: {"temp_token": "...", "code": "123456"}
    → সঠিক হলে real JWT tokens দেয়।
    """
    permission_classes = [AllowAny]

    def post(self, request):
        username_or_email = request.data.get('username') or request.data.get('email', '')
        password = request.data.get('password', '')

        if not username_or_email or not password:
            return Response({'error': 'Username/Email এবং Password দিন।'}, status=status.HTTP_400_BAD_REQUEST)

        # Rate limiting — IP based
        ip = get_client_ip(request)
        rate_key = f"login_attempts:{ip}"
        attempts = cache.get(rate_key, 0)
        if attempts >= 10:
            return Response({
                'error': 'অনেক বার চেষ্টা করেছেন। 15 মিনিট পরে আবার চেষ্টা করুন।'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # User find করো
        user = User.objects.filter(username=username_or_email).first() or \
               User.objects.filter(email=username_or_email).first()

        if not user or not user.check_password(password):
            # Failed attempt record করো
            cache.set(rate_key, attempts + 1, timeout=900)
            # Login history
            if user:
                LoginHistory.objects.create(
                    user=user,
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    is_successful=False
                )
            return Response({'error': 'Username/Email বা Password ভুল।'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({'error': 'Account suspend করা হয়েছে।'}, status=status.HTTP_403_FORBIDDEN)

        # Rate limit reset
        cache.delete(rate_key)

        # 2FA check
        if TOTPService.is_2fa_required(user):
            # Temporary token issue করো (5 minutes valid)
            temp_token = cache.get(f"2fa_temp:{user.id}")
            import secrets as sc
            temp_token = sc.token_urlsafe(32)
            cache.set(f"2fa_temp:{temp_token}", str(user.id), timeout=300)

            return Response({
                'requires_2fa': True,
                'temp_token': temp_token,
                'message': 'Authenticator app থেকে 6-digit code দিন।'
            })

        # 2FA নেই — সরাসরি login
        return self._complete_login(user, request)

    def _complete_login(self, user, request):
        tokens = TokenService.generate_tokens(user)
        refresh_token = tokens['refresh']

        # Session create করো
        session = SessionService.create_session(user, request, refresh_token)

        # Login history
        LoginHistory.objects.create(
            user=user,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            is_successful=True
        )

        user.last_login_ip = get_client_ip(request)
        user.save(update_fields=['last_login_ip'])

        return Response({
            'success': True,
            'access': tokens['access'],
            'refresh': refresh_token,
            'session_id': session['session_id'],
            'user': {
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
                'is_verified': user.is_verified,
                'role': user.role,
                'tier': user.tier,
            }
        })


class Verify2FALoginView(APIView):
    """
    POST /api/users/auth/verify-2fa/
    Body: {"temp_token": "...", "code": "123456"}
    2FA verify করে real tokens দাও।
    """
    permission_classes = [AllowAny]

    def post(self, request):
        temp_token = request.data.get('temp_token', '').strip()
        code = request.data.get('code', '').strip()

        if not temp_token or not code:
            return Response({'error': 'temp_token এবং code দিন।'}, status=status.HTTP_400_BAD_REQUEST)

        # Temp token থেকে user find করো
        user_id = cache.get(f"2fa_temp:{temp_token}")
        if not user_id:
            return Response({
                'error': 'Token expired বা invalid। আবার login করুন।'
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User পাওয়া যায়নি।'}, status=status.HTTP_401_UNAUTHORIZED)

        # 2FA verify
        if not TOTPService.verify_2fa_login(user, code):
            return Response({
                'error': 'Invalid code। আবার চেষ্টা করুন।'
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Temp token delete করো
        cache.delete(f"2fa_temp:{temp_token}")

        # Tokens generate করো
        tokens = TokenService.generate_tokens(user)
        session = SessionService.create_session(user, request, tokens['refresh'])

        LoginHistory.objects.create(
            user=user,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            is_successful=True
        )

        return Response({
            'success': True,
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'session_id': session['session_id'],
            'user': {
                'id': str(user.id),
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'tier': user.tier,
            }
        })


# ============================================================
# SESSION MANAGEMENT VIEWS
# ============================================================

class ActiveSessionsView(APIView):
    """
    GET /api/users/sessions/
    User এর সব active sessions দেখাও।
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = SessionService.get_active_sessions(request.user)
        current_session_id = request.headers.get('X-Session-ID', '')

        # Current session mark করো
        for s in sessions:
            s['is_current'] = (s['session_id'] == current_session_id)

        return Response({
            'sessions': sessions,
            'total': len(sessions)
        })


class RevokeSessionView(APIView):
    """
    DELETE /api/users/sessions/<session_id>/
    নির্দিষ্ট session revoke করো (remote logout)।
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, session_id):
        current_session_id = request.headers.get('X-Session-ID', '')
        result = SessionService.revoke_session(request.user, session_id, current_session_id)

        if not result['success']:
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'success': True, 'message': result['message']})


class RevokeAllSessionsView(APIView):
    """
    POST /api/users/sessions/revoke-all/
    সব session logout করো (current ছাড়া)।
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        current_session_id = request.headers.get('X-Session-ID', '')
        result = SessionService.revoke_all_sessions(request.user, except_session_id=current_session_id)
        return Response(result)


class LogoutView(APIView):
    """
    POST /api/users/auth/logout/
    Body: {"refresh": "refresh_token"}
    Current session logout করো।
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh', '')
        session_id = request.headers.get('X-Session-ID', '')

        # Token blacklist করো
        if refresh_token:
            TokenService.revoke_token(refresh_token)

        # Session delete করো
        if session_id:
            SessionService.revoke_session(request.user, session_id, except_self=True)

        return Response({'success': True, 'message': 'Successfully logged out।'})