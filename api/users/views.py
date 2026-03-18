from urllib import request

from rest_framework_simplejwt.authentication import JWTAuthentication
try:
    from api.audit_logs.models import AuditLog, AuditLogAction
except:
    AuditLog = None
# api/users/views.py
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.conf import settings
from datetime import datetime, timedelta
from rest_framework.permissions import AllowAny 
import json
import random
from api.users.models import UserProfile
from django.db import transaction
import string
import logging

logger = logging.getLogger(__name__)

from .utils import (
    get_client_ip, 
    get_user_agent, 
    detect_vpn, 
    get_location_from_ip,
    check_multiple_accounts,
    hash_device_id,
    generate_referral_code
)


# Import models
from .models import (
    User, OTP, LoginHistory, UserDevice,
    DeviceFingerprint, IPReputation, UserAccountLink,
    UserBehavior, FraudDetectionLog, RiskScoreHistory, RateLimitTracker,
    KYCVerification, UserLevel, NotificationSettings,
    SecuritySettings, UserStatistics, UserPreferences, User, UserActivity, UserDevice
)

# Import serializers (you need to create these)
from .serializers import (
    UserSerializer, UserProfileSerializer, UserRegistrationSerializer,
    UserLoginSerializer, OTPVerificationSerializer, PasswordResetSerializer,
    UserDeviceSerializer, KYCVerificationSerializer, UserLevelSerializer,
    NotificationSettingsSerializer, SecuritySettingsSerializer,
    UserStatisticsSerializer, UserPreferencesSerializer,
    UserDetailSerializer
)

# Import permissions and utilities
from .permissions import IsOwnerOrReadOnly, IsAdminUser, IsVerifiedUser


# ==========================================
# Authentication & Registration Views
# ==========================================

class AutoRegisterView(APIView):
    """
    Auto Register User with Device ID
    POST /api/users/register/
    Body: {
        "device_id": "abc123xyz",
        "device_model": "Samsung Galaxy S21",
        "device_brand": "Samsung",
        "os_version": "Android 12",
        "app_version": "1.0.0",
        "referral_code": "USER10001" (optional)
    }
    """
    permission_classes = [AllowAny]
    
    @transaction.atomic
    def post(self, request):
        device_id = request.data.get('device_id')
        
        # Validation
        if not device_id:
            return Response(
                {'error': 'Device ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get Client Info
        ip_address = get_client_ip(request)
        user_agent = get_user_agent(request)
        
        # Check if user already exists
        existing_user = None  # device_id field removed
        
        if existing_user:
            # Update last login
            existing_user.last_login_at = timezone.now()
            existing_user.save()
            
            # Update device info
            device = existing_user.devices.first()
            device.total_logins += 1
            device.save()
            
            # Log activity
            UserActivity.objects.create(
                user=existing_user,
                action='Login',
                description='User logged in',
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            serializer = UserDetailSerializer(existing_user)
            return Response({
                'message': 'Login successful',
                'user': serializer.data
            }, status=status.HTTP_200_OK)
        
        # Check for fraud (multiple accounts)
        is_fraud, fraud_message = check_multiple_accounts(ip_address, device_id)
        
        if is_fraud:
            return Response(
                {'error': fraud_message},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Detect VPN
        is_vpn = detect_vpn(ip_address)
        
        if is_vpn:
            return Response(
                {'error': 'VPN detected. Please disable VPN and try again.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Create new user
        user = User.objects.create(
            is_vpn_allowed=False
        )
        from .models import UserDevice
        device_model = request.data.get('device_model')
        device_brand = request.data.get('device_brand')
        os_version = request.data.get('os_version')
        app_version = request.data.get('app_version')
        device = UserDevice.objects.create(
            user=user,
            device_id=device_id,
            device_name=device_model or 'Unknown',
            device_type='android',
        )
        user.last_login_ip = ip_address or '0.0.0.0'
        user.save()
        # device info saved on create
        
        # Get location from IP
        location = get_location_from_ip(ip_address)
        device.location_city = location.get('city')
        device.location_country = location.get('country')
        device.latitude = location.get('latitude')
        device.longitude = location.get('longitude')
        device.save()
        
        # Handle referral code
        referral_code = request.data.get('referral_code')
        if referral_code:
            try:
                upline_profile = UserProfile.objects.get(referral_code=referral_code)
                user.profile.upline = upline_profile.user
                user.profile.save()
                
                # Give referral bonus to upline
                upline_wallet = upline_profile.user.wallet
                upline_wallet.bonus_balance += 5.00  # ৫ টাকা রেফারেল বোনাস
                upline_wallet.total_referral_bonus += 5.00
                upline_wallet.save()
                
                # Update upline profile
                upline_profile.referral_earning += 5.00
                upline_profile.save()
                
            except UserProfile.DoesNotExist:
                pass  # Invalid referral code, skip
        
        # Log registration activity
        UserActivity.objects.create(
            user=user,
            action='Registration',
            description='New user registered',
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        serializer = UserDetailSerializer(user)
        return Response({
            'message': 'Registration successful',
            'user': serializer.data
        }, status=status.HTTP_201_CREATED)






class UserRegistrationView(APIView):
    """User registration endpoint"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        try:
            phone = request.data.get('phone')
            password = request.data.get('password')
            email = request.data.get('email', '')
            
            # Check if user already exists
            if User.objects.filter(phone=phone).exists():
                return Response(
                    {'error': 'User with this phone number already exists'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if email and User.objects.filter(email=email).exists():
                return Response(
                    {'error': 'User with this email already exists'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create user
            user = User.objects.create_user(
                username=phone,  # Use phone as username
                phone=phone,
                email=email,
                password=password
            )
            
            # Generate referral code
            user.referral_code = self.generate_referral_code()
            user.save()
            
            # Create user profile
            UserProfile.objects.create(user=user)
            
            # Create related models
            UserLevel.objects.create(user=user)
            NotificationSettings.objects.create(user=user)
            SecuritySettings.objects.create(user=user)
            UserStatistics.objects.create(user=user)
            UserPreferences.objects.create(user=user)
            
            # Generate and send OTP
            otp_code = self.generate_otp()
            OTP.objects.create(
                user=user,
                code=otp_code,
                otp_type='phone_verify',
                expires_at=timezone.now() + timedelta(minutes=10)
            )
            
            # Send OTP (implement your SMS service here)
            # send_sms(user.phone, f"Your OTP is: {otp_code}")
            
            return Response({
                'message': 'Registration successful',
                'user_id': user.id,
                'requires_verification': True,
                'otp_sent': True
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return Response(
                {'error': 'Registration failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def generate_referral_code(self):
        """Generate unique referral code"""
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not User.objects.filter(referral_code=code).exists():
                return code
    
    def generate_otp(self):
        """Generate 6-digit OTP"""
        return ''.join(random.choices('0123456789', k=6))


class UserLoginView(APIView):
    """User login endpoint"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        try:
            phone = request.data.get('phone')
            password = request.data.get('password')
            device_id = request.data.get('device_id', '')
            device_name = request.data.get('device_name', 'Unknown')
            
            # Authenticate user
            user = authenticate(request, username=phone, password=password)
            
            if user is None:
                # Record failed login attempt
                ip_address = self.get_client_ip(request)
                self.record_failed_login(phone, ip_address)
                
                return Response(
                    {'error': 'Invalid phone number or password'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            if not user.is_active:
                return Response(
                    {'error': 'Account is disabled'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if user is verified
            if not user.is_verified:
                # Generate verification OTP
                otp_code = self.generate_otp()
                OTP.objects.create(
                    user=user,
                    code=otp_code,
                    otp_type='login',
                    expires_at=timezone.now() + timedelta(minutes=10)
                )
                
                return Response({
                    'requires_verification': True,
                    'message': 'Please verify your account',
                    'user_id': user.id
                }, status=status.HTTP_200_OK)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            # Record successful login
            ip_address = self.get_client_ip(request)
            LoginHistory.objects.create(
                user=user,
                ip_address=ip_address,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                is_successful=True
            )
            
            # Update or create user device
            if device_id:
                UserDevice.objects.update_or_create(
                    device_id=device_id,
                    defaults={
                        'user': user,
                        'device_name': device_name,
                        'device_type': self.get_device_type(request),
                        'is_active': True
                    }
                )
            
            # Update last login IP
            user.last_login_ip = ip_address
            user.save()
            if AuditLog:
                try:
                    AuditLog.objects.create(user=user, action="LOGIN", message="User logged in", user_ip=ip_address, success=True, request_method="POST", request_path="/api/auth/login/")
                except: pass
            # AuditLog
            if AuditLog:
                try:
                    AuditLog.objects.create(user=user, action='LOGIN', message='User logged in successfully', user_ip=ip_address, success=True, request_method='POST', request_path='/api/auth/login/')
                except: pass
            
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'phone': user.phone,
                    'email': user.email,
                    'balance': str(user.balance),
                    'is_verified': user.is_verified,
                    'referral_code': user.referral_code
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return Response(
                {'error': 'Login failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def record_failed_login(self, phone, ip_address):
        """Record failed login attempt"""
        try:
            # Update IP reputation
            ip_rep, _ = IPReputation.objects.get_or_create(ip_address=ip_address)
            ip_rep.failed_login_attempts += 1
            ip_rep.last_failed_login = timezone.now()
            ip_rep.save()
            
            # Log fraud attempt if too many failures
            if ip_rep.failed_login_attempts >= 5:
                FraudDetectionLog.objects.create(
                    event_type='rate_limit_exceeded',
                    severity='high',
                    ip_address=ip_address,
                    description=f'Multiple failed login attempts for phone: {phone}'
                )
        except:
            pass
    
    def get_device_type(self, request):
        """Detect device type from user agent"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        if 'android' in user_agent:
            return 'android'
        elif 'iphone' in user_agent or 'ipad' in user_agent:
            return 'ios'
        else:
            return 'web'


class OTPVerificationView(APIView):
    """OTP verification endpoint"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        try:
            user_id = request.data.get('user_id')
            otp_code = request.data.get('otp_code')
            otp_type = request.data.get('otp_type', 'phone_verify')
            
            user = get_object_or_404(User, id=user_id)
            
            # Find valid OTP
            otp = OTP.objects.filter(
                user=user,
                code=otp_code,
                otp_type=otp_type,
                is_used=False,
                expires_at__gt=timezone.now()
            ).first()
            
            if not otp:
                return Response(
                    {'error': 'Invalid or expired OTP'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mark OTP as used
            otp.is_used = True
            otp.save()
            
            # Handle different OTP types
            if otp_type == 'phone_verify':
                user.is_verified = True
                user.save()
                
                # Generate tokens for verified user
                refresh = RefreshToken.for_user(user)
                
                return Response({
                    'message': 'Phone verified successfully',
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'user': {
                        'id': user.id,
                        'phone': user.phone,
                        'is_verified': True
                    }
                }, status=status.HTTP_200_OK)
                
            elif otp_type == 'login':
                # Generate tokens for login
                refresh = RefreshToken.for_user(user)
                
                return Response({
                    'message': 'Login verified successfully',
                    'refresh': str(refresh),
                    'access': str(refresh.access_token)
                }, status=status.HTTP_200_OK)
            
            elif otp_type == 'password_reset':
                return Response({
                    'message': 'OTP verified. You can now reset your password.',
                    'verified': True
                }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"OTP verification error: {str(e)}")
            return Response(
                {'error': 'OTP verification failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PasswordResetView(APIView):
    """Password reset endpoint"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        try:
            phone = request.data.get('phone')
            new_password = request.data.get('new_password')
            otp_code = request.data.get('otp_code')
            
            user = get_object_or_404(User, phone=phone)
            
            # Verify OTP
            otp = OTP.objects.filter(
                user=user,
                code=otp_code,
                otp_type='password_reset',
                is_used=False,
                expires_at__gt=timezone.now()
            ).first()
            
            if not otp:
                return Response(
                    {'error': 'Invalid or expired OTP'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update password
            user.set_password(new_password)
            user.save()
            
            # Mark OTP as used
            otp.is_used = True
            otp.save()
            
            return Response({
                'message': 'Password reset successful'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            return Response(
                {'error': 'Password reset failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==========================================
# User Profile Views
# ==========================================
class UserProfileViewSet(viewsets.ModelViewSet):
    """User profile management"""
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get_queryset(self):
        return UserProfile.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_profile(self, request):
        """Get current user's profile"""
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(profile)
        user = request.user
        data = serializer.data
        data['username'] = user.username
        data['email'] = str(user.email)
        data['phone'] = str(user.phone or '')
        data['role'] = str(user.role or 'admin')
        data['avatar'] = request.build_absolute_uri(user.avatar.url) if user.avatar else None
        return Response(data)
    
    @action(detail=False, methods=['put'])
    # def update_profile(self, request):
    #     """Update user profile"""
    #     profile, created = UserProfile.objects.get_or_create(user=request.user)
    #     serializer = self.get_serializer(profile, data=request.data, partial=True)
        
    #     if serializer.is_valid():
    #         serializer.save()
    #         return Response(serializer.data)
        
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    def update_profile(self, request):
        """Update user profile and user fields"""
        user = request.user
        for field in ['username', 'email', 'phone']:
            if field in request.data:
                setattr(user, field, request.data[field])
        if 'avatar' in request.FILES:
            user.avatar = request.FILES['avatar']
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
        return Response({'success': True, 'username': user.username, 'email': user.email, 'phone': str(user.phone or '')})
    

# ==========================================
# KYC Verification Views
# ==========================================
class KYCVerificationViewSet(viewsets.ModelViewSet):
    """KYC verification management"""
    serializer_class = KYCVerificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return KYCVerification.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def submit_kyc(self, request):
        """Submit KYC documents"""
        try:
            # Check if KYC already exists
            if KYCVerification.objects.filter(user=request.user).exists():
                return Response(
                    {'error': 'KYC already submitted'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                kyc = serializer.save(user=request.user)
                kyc.submitted_at = timezone.now()
                kyc.save()
                
                return Response({
                    'message': 'KYC submitted successfully',
                    'status': kyc.verification_status
                }, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f"KYC submission error: {str(e)}")
            return Response(
                {'error': 'KYC submission failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get KYC status"""
        try:
            kyc = KYCVerification.objects.get(user=request.user)
            return Response({
                'status': kyc.verification_status,
                'document_type': kyc.document_type,
                'submitted_at': kyc.submitted_at,
                'reviewed_at': kyc.reviewed_at
            })
        except KYCVerification.DoesNotExist:
            return Response({
                'status': 'not_submitted',
                'message': 'KYC not submitted'
            })


# ==========================================
# User Level & Statistics Views
# ==========================================
class UserLevelView(APIView):
    """User level information"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            level_info, created = UserLevel.objects.get_or_create(user=request.user)
            serializer = UserLevelSerializer(level_info)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"User level error: {str(e)}")
            return Response(
                {'error': 'Failed to get user level'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserStatisticsView(APIView):
    """User statistics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            stats, created = UserStatistics.objects.get_or_create(user=request.user)
            stats.update_statistics()  # Update stats
            
            serializer = UserStatisticsSerializer(stats)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"User statistics error: {str(e)}")
            return Response(
                {'error': 'Failed to get user statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==========================================
# Settings Views
# ==========================================
class NotificationSettingsView(APIView):
    """Notification settings management"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            settings, created = NotificationSettings.objects.get_or_create(user=request.user)
            serializer = NotificationSettingsSerializer(settings)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Notification settings error: {str(e)}")
            return Response(
                {'error': 'Failed to get notification settings'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request):
        try:
            settings, created = NotificationSettings.objects.get_or_create(user=request.user)
            serializer = NotificationSettingsSerializer(settings, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Notification settings update error: {str(e)}")
            return Response(
                {'error': 'Failed to update notification settings'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SecuritySettingsView(APIView):
    """Security settings management"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            settings, created = SecuritySettings.objects.get_or_create(user=request.user)
            serializer = SecuritySettingsSerializer(settings)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Security settings error: {str(e)}")
            return Response(
                {'error': 'Failed to get security settings'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request):
        try:
            settings, created = SecuritySettings.objects.get_or_create(user=request.user)
            serializer = SecuritySettingsSerializer(settings, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Security settings update error: {str(e)}")
            return Response(
                {'error': 'Failed to update security settings'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserPreferencesView(APIView):
    """User preferences management"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            preferences, created = UserPreferences.objects.get_or_create(user=request.user)
            serializer = UserPreferencesSerializer(preferences)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"User preferences error: {str(e)}")
            return Response(
                {'error': 'Failed to get user preferences'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request):
        try:
            preferences, created = UserPreferences.objects.get_or_create(user=request.user)
            serializer = UserPreferencesSerializer(preferences, data=request.data, partial=True)
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"User preferences update error: {str(e)}")
            return Response(
                {'error': 'Failed to update user preferences'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==========================================
# Support Ticket Views
# ==========================================
# class SupportTicketViewSet(viewsets.ModelViewSet):
#     """Support ticket management"""
#     serializer_class = SupportTicketSerializer
#     permission_classes = [permissions.IsAuthenticated]
    
#     def get_queryset(self):
#         return SupportTicket.objects.filter(user=self.request.user)
    
#     def perform_create(self, serializer):
#         serializer.save(user=self.request.user)
    
#     @action(detail=True, methods=['get'])
#     def messages(self, request, pk=None):
#         """Get messages for a ticket"""
#         ticket = self.get_object()
#         messages = TicketMessage.objects.filter(ticket=ticket)
#         serializer = TicketMessageSerializer(messages, many=True)
#         return Response(serializer.data)
    
#     @action(detail=True, methods=['post'])
#     def add_message(self, request, pk=None):
#         """Add message to ticket"""
#         ticket = self.get_object()
        
#         if ticket.status in ['resolved', 'closed']:
#             return Response(
#                 {'error': 'Cannot add message to closed ticket'},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         serializer = TicketMessageSerializer(data=request.data)
#         if serializer.is_valid():
#             serializer.save(ticket=ticket, sender=request.user)
            
#             # Update ticket status
#             if ticket.status == 'open':
#                 ticket.status = 'waiting_response'
#                 ticket.save()
            
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
        
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==========================================
# Device Management Views
# ==========================================
class UserDeviceViewSet(viewsets.ModelViewSet):
    """User device management"""
    serializer_class = UserDeviceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return UserDevice.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a device"""
        device = self.get_object()
        device.is_active = False
        device.save()
        return Response({'message': 'Device deactivated successfully'})
    
    @action(detail=False, methods=['get'])
    def active_devices(self, request):
        """Get active devices"""
        devices = UserDevice.objects.filter(user=request.user, is_active=True)
        serializer = self.get_serializer(devices, many=True)
        return Response(serializer.data)


# ==========================================
# Referral System Views
# ==========================================
class ReferralView(APIView):
    """Referral system"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get referral information"""
        try:
            user = request.user
            
            # Get referral stats
            referrals = User.objects.filter(referred_by=user)
            
            # Calculate earnings (you need to implement this based on your logic)
            referral_earnings = 0
            
            return Response({
                'referral_code': user.referral_code,
                'total_referrals': referrals.count(),
                'active_referrals': referrals.filter(is_active=True).count(),
                'referral_earnings': referral_earnings,
                'referral_link': f"{settings.FRONTEND_URL}/register?ref={user.referral_code}",
                'referrals': UserSerializer(referrals, many=True).data
            })
            
        except Exception as e:
            logger.error(f"Referral error: {str(e)}")
            return Response(
                {'error': 'Failed to get referral information'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==========================================
# Dashboard Views
# ==========================================
class DashboardView(APIView):
    """User dashboard"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """Get dashboard data"""
        try:
            user = request.user
            
            # Get user statistics
            stats, _ = UserStatistics.objects.get_or_create(user=user)
            stats.update_statistics()
            
            # Get user level
            level, _ = UserLevel.objects.get_or_create(user=user)
            
            # Get recent activities
            recent_logins = LoginHistory.objects.filter(
                user=user
            ).order_by('-created_at')[:5]
            
            # Get pending KYC status
            try:
                kyc = KYCVerification.objects.get(user=user)
                kyc_status = kyc.verification_status
            except KYCVerification.DoesNotExist:
                kyc_status = 'not_submitted'
            
            # Get support tickets
            open_tickets = SupportTicket.objects.filter(
                user=user,
                status__in=['open', 'in_progress', 'waiting_response']
            ).count()
            
            return Response({
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'phone': user.phone,
                    'email': user.email,
                    'balance': str(user.balance),
                    'is_verified': user.is_verified,
                    'referral_code': user.referral_code
                },
                'statistics': {
                    'total_earned': str(stats.total_earned),
                    'total_withdrawn': str(stats.total_withdrawn),
                    'total_tasks_completed': stats.total_tasks_completed,
                    'current_streak': stats.current_streak,
                    'referral_count': stats.referral_count
                },
                'level': {
                    'current_level': level.current_level,
                    'level_type': level.level_type,
                    'experience_points': level.experience_points,
                    'xp_to_next_level': level.xp_to_next_level
                },
                'kyc_status': kyc_status,
                'open_tickets': open_tickets,
                'recent_activities': [
                    {
                        'type': 'login',
                        'time': login.created_at,
                        'ip': login.ip_address,
                        'successful': login.is_successful
                    }
                    for login in recent_logins
                ]
            })
            
        except Exception as e:
            logger.error(f"Dashboard error: {str(e)}")
            return Response(
                {'error': 'Failed to load dashboard'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==========================================
# Utility Views
# ==========================================
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def send_otp_view(request):
    """Send OTP to phone"""
    try:
        phone = request.data.get('phone')
        otp_type = request.data.get('otp_type', 'phone_verify')
        
        # Find user by phone
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate OTP
        otp_code = ''.join(random.choices('0123456789', k=6))
        
        # Delete previous OTPs of same type
        OTP.objects.filter(user=user, otp_type=otp_type, is_used=False).delete()
        
        # Create new OTP
        OTP.objects.create(
            user=user,
            code=otp_code,
            otp_type=otp_type,
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        
        # Send OTP via SMS (implement your SMS service)
        # send_sms(phone, f"Your OTP is: {otp_code}")
        
        return Response({
            'message': 'OTP sent successfully',
            'otp_sent_to': phone,
            'user_id': user.id
        })
        
    except Exception as e:
        logger.error(f"Send OTP error: {str(e)}")
        return Response(
            {'error': 'Failed to send OTP'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def check_username_availability(request):
    """Check if username is available"""
    username = request.GET.get('username', '')
    
    if not username:
        return Response(
            {'error': 'Username is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    is_available = not User.objects.filter(username=username).exists()
    
    return Response({
        'username': username,
        'available': is_available
    })


# ==========================================
# Admin Views (for admin users only)
# ==========================================
class AdminUserViewSet(viewsets.ModelViewSet):
    """Admin user management"""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = User.objects.all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'phone', 'email', 'referral_code']
    ordering_fields = ['created_at', 'balance', 'last_login']
    
    @action(detail=True, methods=['post'])
    def verify_user(self, request, pk=None):
        """Verify a user"""
        user = self.get_object()
        user.is_verified = True
        user.save()
        return Response({'message': 'User verified successfully'})
    
    @action(detail=True, methods=['post'])
    def deactivate_user(self, request, pk=None):
        """Deactivate a user"""
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response({'message': 'User deactivated successfully'})
    
    @action(detail=False, methods=['get'])
    def fraud_reports(self, request):
        """Get fraud detection reports"""
        fraud_logs = FraudDetectionLog.objects.all().order_by('-detected_at')[:100]
        
        data = []
        for log in fraud_logs:
            data.append({
                'id': log.id,
                'event_type': log.event_type,
                'severity': log.severity,
                'user': log.user.username if log.user else 'N/A',
                'ip_address': log.ip_address,
                'description': log.description,
                'detected_at': log.detected_at,
                'is_resolved': log.is_resolved
            })
        
        return Response(data)
    

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request):
        """Get or update current user"""
        if request.method == "GET":
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='dashboard-stats')
    def system_statistics(self, request):
        """Get system statistics"""
        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        verified_users = User.objects.filter(is_verified=True).count()
        
        today = timezone.now().date()
        new_users_today = User.objects.filter(created_at__date=today).count()
        
        total_balance = User.objects.aggregate(total=Sum('balance'))['total'] or 0
        
        fraud_events = FraudDetectionLog.objects.filter(
            detected_at__date=today,
            is_resolved=False
        ).count()
        
        return Response({
            'total_users': total_users,
            'active_users': active_users,
            'verified_users': verified_users,
            'new_users_today': new_users_today,
            'total_balance': float(total_balance),
            'fraud_events_today': fraud_events
        })

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response as R

@api_view(['GET'])
@permission_classes([IsAdminUser])
def leaderboard_view(request):
    from .models import User
    users = User.objects.order_by('-balance')[:50]
    data = [{'id':u.id,'username':u.username,'balance':str(u.balance),'rank':i+1} for i,u in enumerate(users)]
    return R({'results': data})

@api_view(['GET'])
@permission_classes([IsAdminUser])
def fraud_logs_view(request):
    from .models import FraudDetectionLog
    logs = FraudDetectionLog.objects.order_by('-detected_at')[:100]
    data = [{'id':l.id,'event_type':l.event_type,'severity':l.severity,
             'user':l.user.username if l.user else None,'ip_address':l.ip_address,
             'is_resolved':l.is_resolved,'detected_at':l.detected_at} for l in logs]
    return R({'results': data, 'count': len(data)})

@api_view(['POST'])
@permission_classes([IsAdminUser])
def resolve_fraud_log(request, pk):
    from .models import FraudDetectionLog
    try:
        log = FraudDetectionLog.objects.get(pk=pk)
        log.is_resolved = True
        log.save()
        return R({'detail': 'Resolved'})
    except FraudDetectionLog.DoesNotExist:
        return R({'detail': 'Not found'}, status=404)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def ip_reputations_view(request):
    from .models import IPReputation
    ips = IPReputation.objects.all()[:100]
    data = [{'id':ip.id,'ip_address':ip.ip_address,'is_blacklisted':ip.is_blacklisted,
             'failed_login_attempts':ip.failed_login_attempts} for ip in ips]
    return R({'results': data, 'count': len(data)})

@api_view(['GET'])
@permission_classes([IsAdminUser])
def device_fingerprints_view(request):
    from .models import UserDevice
    devices = UserDevice.objects.all()[:100]
    data = [{'id':d.id,'device_id':d.device_id,'device_model':d.device_model,
             'is_blocked':d.is_blocked,'user_id':d.user_id} for d in devices]
    return R({'results': data, 'count': len(data)})

@api_view(['GET'])
@permission_classes([IsAdminUser])
def rate_limits_view(request):
    return R({'results': [], 'count': 0})
