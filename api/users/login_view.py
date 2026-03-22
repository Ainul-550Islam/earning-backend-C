# api/users/login_view.py (Login with Fraud Detection) - FIXED VERSION

import json
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate, login
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from datetime import timedelta

# Import fraud prevention services
from api.users.services.vpn_detector import vpn_detector
from api.users.services.device_fingerprint import device_fingerprint_service
from api.users.services.risk_scoring import RiskScoringEngine

# Import models
from api.users.models import (
    DeviceFingerprint,
    IPReputation,
    UserAccountLink,
    FraudDetectionLog,
    UserBehavior,
    RateLimitTracker
)


def get_client_ip(request):
    """Extract client IP from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ✅ FIX: View → APIView, AllowAny যোগ করা হয়েছে
class UserLoginView(APIView):
    authentication_classes = []          # ✅ No auth required
    permission_classes = [AllowAny]      # ✅ Anyone can access login

    """
    User Login with Fraud Detection

    POST /api/auth/login/
    Body: {
        "username": "john_doe",
        "password": "secure_password",
        "device_fingerprint": {...}
    }
    """

    def post(self, request):
        try:
            # ✅ FIX: json.loads(request.body) → request.data
            data = request.data
            username = data.get('username')
            password = data.get('password')
            device_fp_data = data.get('device_fingerprint')

            # Validation
            if not all([username, password]):
                return Response({
                    'success': False,
                    'error': 'Missing username or password'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get client IP
            ip_address = get_client_ip(request)

            # ====================================
            # FRAUD PREVENTION FOR LOGIN
            # ====================================

            # Step 1: Rate Limiting (prevent brute force)
            rate_limit_result = self._check_login_rate_limit(ip_address)
            if rate_limit_result['blocked']:
                return Response({
                    'success': False,
                    'error': 'Too many login attempts. Please try again later.',
                    'blocked_until': rate_limit_result.get('blocked_until')
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)

            # Step 2: Get IP Reputation
            ip_reputation, _ = IPReputation.objects.get_or_create(
                ip_address=ip_address,
                defaults={'reputation': 'neutral'}
            )

            # Check if IP is blacklisted
            if ip_reputation.is_blacklisted:
                self._log_fraud_event(
                    event_type='ip_banned',
                    severity='high',
                    ip_address=ip_address,
                    ip_reputation=ip_reputation,
                    description='Blacklisted IP attempted login'
                )
                return Response({
                    'success': False,
                    'error': 'Access denied from this IP address'
                }, status=status.HTTP_403_FORBIDDEN)

            # Step 3: Device Fingerprinting
            device = None
            if device_fp_data:
                device = device_fingerprint_service.generate_fingerprint(
                    request,
                    device_fp_data
                )

                if device.is_blocked:
                    self._log_fraud_event(
                        event_type='device_banned',
                        severity='high',
                        ip_address=ip_address,
                        device=device,
                        description='Blocked device attempted login'
                    )
                    return Response({
                        'success': False,
                        'error': 'This device has been blocked'
                    }, status=status.HTTP_403_FORBIDDEN)

            # Step 4: Authenticate user
            user = authenticate(request, username=username, password=password)

            if user is None:
                self._handle_failed_login(username, ip_address, ip_reputation, device)
                return Response({
                    'success': False,
                    'error': 'Invalid username or password'
                }, status=status.HTTP_401_UNAUTHORIZED)

            # Step 5: Check if user is active
            if not user.is_active:
                return Response({
                    'success': False,
                    'error': 'Account is not active. Please verify your email.'
                }, status=status.HTTP_403_FORBIDDEN)

            # Step 6: Behavioral Analysis
            behavior_check = self._check_login_behavior(user, ip_address, device)

            # Step 7: VPN Detection
            vpn_result = None
            if behavior_check['is_anomaly']:
                vpn_result = vpn_detector.detect_vpn(ip_address)

                self._log_fraud_event(
                    event_type='anomaly_detected',
                    severity='medium',
                    user=user,
                    ip_address=ip_address,
                    device=device,
                    ip_reputation=ip_reputation,
                    description='Suspicious login detected',
                    metadata={
                        'anomaly_reason': behavior_check['anomaly_reason'],
                        'vpn_detected': vpn_result.get('is_vpn', False)
                    }
                )

                if behavior_check['severity'] == 'high':
                    return Response({
                        'success': False,
                        'error': 'Additional verification required',
                        'verification_needed': True,
                        'reason': 'Unusual login detected from new location/device'
                    }, status=status.HTTP_403_FORBIDDEN)

            # Step 8: Update behavior profile
            self._update_user_behavior(user, ip_address, device, ip_reputation)

            # Step 9: Successful login
            login(request, user)

            ip_reputation.total_logins += 1
            ip_reputation.failed_login_attempts = 0
            ip_reputation.save()

            self._log_fraud_event(
                event_type='suspicious_ip' if behavior_check['is_anomaly'] else 'anomaly_detected',
                severity='low',
                user=user,
                ip_address=ip_address,
                device=device,
                ip_reputation=ip_reputation,
                description='Successful login',
                metadata={
                    'is_anomaly': behavior_check['is_anomaly'],
                    'vpn_detected': vpn_result.get('is_vpn', False) if vpn_result else False
                }
            )

            from rest_framework_simplejwt.tokens import RefreshToken
            refresh = RefreshToken.for_user(user)
            return Response({
                'success': True,
                'message': 'Login successful',
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': str(user.id),
                    'username': user.username,
                    'email': user.email
                },
                'security_alert': behavior_check.get('anomaly_reason') if behavior_check['is_anomaly'] else None
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'error': f'Server error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _check_login_rate_limit(self, ip_address):
        identifier = f"ip_{ip_address}"
        tracker, created = RateLimitTracker.objects.get_or_create(
            identifier=identifier,
            limit_type='login'
        )

        if tracker.is_blocked and tracker.block_until:
            if timezone.now() < tracker.block_until:
                return {
                    'blocked': True,
                    'blocked_until': tracker.block_until.isoformat()
                }
            else:
                tracker.is_blocked = False
                tracker.block_until = None
                tracker.request_count = 0
                tracker.save()

        if tracker.request_count >= 10:
            tracker.is_blocked = True
            tracker.block_until = timezone.now() + timedelta(hours=1)
            tracker.save()
            return {
                'blocked': True,
                'blocked_until': tracker.block_until.isoformat()
            }

        tracker.request_count += 1

        if timezone.now() - tracker.window_start > timedelta(hours=1):
            tracker.request_count = 1
            tracker.window_start = timezone.now()

        tracker.save()
        return {'blocked': False}

    def _handle_failed_login(self, username, ip_address, ip_reputation, device):
        ip_reputation.record_failed_login()

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

        self._log_fraud_event(
            event_type='rate_limit_exceeded',
            severity='medium',
            user=user,
            ip_address=ip_address,
            device=device,
            ip_reputation=ip_reputation,
            description=f'Failed login attempt for username: {username}'
        )

    def _check_login_behavior(self, user, ip_address, device):
        anomalies = []
        severity = 'low'

        try:
            behavior = UserBehavior.objects.get(user=user)

            known_ips = behavior.known_ips.all()
            ip_rep, _ = IPReputation.objects.get_or_create(ip_address=ip_address)

            if ip_rep not in known_ips:
                anomalies.append("Login from new IP address")
                severity = 'medium'

            if device:
                known_devices = behavior.known_devices.all()
                if device not in known_devices:
                    anomalies.append("Login from new device")
                    if severity == 'medium':
                        severity = 'high'

            current_hour = timezone.now().hour
            common_hours = behavior.common_login_hours or []

            if common_hours and current_hour not in common_hours:
                if len(common_hours) >= 5:
                    anomalies.append("Login at unusual time")

        except UserBehavior.DoesNotExist:
            pass

        return {
            'is_anomaly': len(anomalies) > 0,
            'severity': severity,
            'anomaly_reason': ', '.join(anomalies) if anomalies else None
        }

    def _update_user_behavior(self, user, ip_address, device, ip_reputation):
        try:
            behavior, created = UserBehavior.objects.get_or_create(user=user)
            behavior.total_logins += 1

            if ip_reputation and ip_reputation not in behavior.known_ips.all():
                behavior.known_ips.add(ip_reputation)

            if device and device not in behavior.known_devices.all():
                behavior.known_devices.add(device)

            current_hour = timezone.now().hour
            common_hours = behavior.common_login_hours or []

            if current_hour not in common_hours:
                common_hours.append(current_hour)
                behavior.common_login_hours = sorted(common_hours)

            behavior.save()

        except Exception as e:
            print(f"Error updating user behavior: {e}")

    def _log_fraud_event(self, event_type, severity, ip_address,
                         user=None, device=None, ip_reputation=None,
                         description='', metadata=None):
        try:
            FraudDetectionLog.objects.create(
                event_type=event_type,
                severity=severity,
                user=user,
                device=device,
                ip_reputation=ip_reputation,
                ip_address=ip_address,
                description=description,
                metadata=metadata or {}
            )
        except Exception as e:
            print(f"Error logging fraud event: {e}")


# ✅ DRF compatible function-based endpoint
from rest_framework.decorators import api_view, permission_classes

@api_view(['POST'])
@permission_classes([AllowAny])   # ✅ এটাও AllowAny দিতে হবে
def login_user_api(request):
    """DRF-compatible login endpoint"""
    view = UserLoginView()
    return view.post(request)