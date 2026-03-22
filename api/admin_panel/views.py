from api.tenants.mixins import TenantMixin
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from core.views import BaseViewSet
from .models import AdminAction, SystemSettings, Report
from .serializers import AdminActionSerializer, SystemSettingsAdminSerializer, ReportSerializer
from .dashboard.DashboardService import DashboardService
from .dashboard.DataExporter import DataExporter
from .permissions import IsSuperAdmin
from api.users.models import UserProfile
from api.admin_panel.serializers import UserProfileSerializer
from rest_framework import viewsets, status, generics, permissions
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Q
import logging
from django.contrib.auth import authenticate, login, logout
from django.db.models import Count, Sum, Q
from datetime import timedelta

# api/core/views.py

from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.db.models import Sum
from .models import SystemSettings
from .serializers import (
    SystemSettingsPublicSerializer,
    SystemSettingsAdminSerializer,
    SystemSettingsVersionSerializer,
    SystemSettingsVersionResponseSerializer,
    SystemSettingsUpdateSerializer,
    DailyLimitsSerializer,
    PaymentGatewayStatusSerializer,
    SecuritySettingsSerializer,
    ReferralSettingsSerializer,
    RewardPointsSerializer,
    WithdrawalSettingsSerializer,
    AppConfigSerializer
)
import uuid
from .models import SiteNotification, SiteContent
from .serializers import (
    PublicSystemSettingsSerializer,
    SiteNotificationSerializer, NotificationCreateSerializer,
    SiteContentSerializer, EmailTestSerializer, SMSTestSerializer,
    MaintenanceModeSerializer, CacheClearSerializer, SystemStatsSerializer
)
from .permissions import (
    IsSystemAdmin, CanManageSystemSettings, CanManageNotifications,
    CanViewSettings, SystemAccessPermission
)

logger = logging.getLogger(__name__)




class AdminPanelViewSet(BaseViewSet):
    permission_classes = [IsAdminUser]
    queryset = []
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        stats = DashboardService.get_dashboard_stats()
        return self.success_response(data=stats)
    
    @action(detail=False, methods=['get'])
    def user_stats(self, request):
        stats = DashboardService.get_user_statistics()
        return self.success_response(data=stats)
    
    @action(detail=False, methods=['get'])
    def revenue_stats(self, request):
        stats = DashboardService.get_revenue_statistics()
        return self.success_response(data=stats)
    
    @action(detail=False, methods=['post'])
    def export_data(self, request):
        export_type = request.data.get('type', 'users')
        file_path = DataExporter.export_data(export_type)
        
        return self.success_response(
            data={'file_path': file_path},
            message='Data exported successfully'
        )


class AdminActionViewSet(BaseViewSet):
    queryset = AdminAction.objects.all()
    serializer_class = AdminActionSerializer
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Return action counts grouped by action_type"""
        from django.db.models import Count
        data = (
            AdminAction.objects.values('action_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        return Response({'stats': list(data)})


# class SystemSettingsViewSet(BaseViewSet):
#     queryset = SystemSettings.objects.all()
#     serializer_class = SystemSettingsSerializer
#     permission_classes = [IsSuperAdmin]
    
#     @action(detail=False, methods=['get'])
#     def get_setting(self, request):
#         key = request.query_params.get('key')
#         try:
#             setting = SystemSettings.objects.get(key=key)
#             serializer = self.get_serializer(setting)
#             return self.success_response(data=serializer.data)
#         except SystemSettings.DoesNotExist:
#             return self.error_response(message='Setting not found', status_code=status.HTTP_404_NOT_FOUND)


class ReportViewSet(BaseViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [IsAdminUser]
    

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download report file"""
        from django.http import FileResponse
        import os
        report = self.get_object()
        if not report.report_file:
            return Response({'error': 'No file available for this report'}, status=404)
        file_path = report.report_file.path
        if not os.path.exists(file_path):
            return Response({'error': 'Report file not found on disk'}, status=404)
        response = FileResponse(open(file_path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response

    @action(detail=True, methods=['post'])
    def regenerate(self, request, pk=None):
        """Re-generate report data and file"""
        report = self.get_object()
        report.status = 'processing'
        report.save(update_fields=['status'])
        from .tasks import generate_report_task
        generate_report_task.delay(report.id)
        return Response({'success': True, 'message': 'Report regeneration started', 'report_id': str(report.id)})

    @action(detail=False, methods=['post'])
    def generate_report(self, request):
        report_type = request.data.get('report_type')
        parameters = request.data.get('parameters', {})
        
        report = Report.objects.create(
            report_type=report_type,
            generated_by=request.user,
            parameters=parameters,
            status='processing'
        )
        
        # Trigger async task to generate report
        from .tasks import generate_report_task
        generate_report_task.delay(report.id)
        
        return self.success_response(
            data={'report_id': str(report.id)},
            message='Report generation started'
        )
        
        
        # api/admin_panel/views.py
from django.shortcuts import render

# এই ফাংশনটা আছে কিনা চেক করো
def admin_dashboard(request):
    context = {
        'active_users_24h': {
            'active_count': 125,
            'new_users_24h': 18,
            'engagement_rate': 72.5,
            'peak_hour': ['3 PM', 42],
            'sample_users': [
                {'username': 'john_doe', 'email': 'john@example.com'},
                {'username': 'jane_smith', 'email': 'jane@example.com'},
            ]
        },
        'withdrawal_summary': {
            'total_amount': 3245.50,
            'total_pending': 42,
            'today_pending': 8,
            'by_payment_method': {
                'bKash': {'count': 15, 'amount': 1245.00},
                'Nagad': {'count': 12, 'amount': 850.50},
            },
            'recent_requests': [
                {'id': 1, 'user': 'user123', 'amount': 150.00, 'payment_method': 'bKash', 'created_at': '2024-02-03'},
            ]
        },
        'offer_analysis': {
            'summary': {
                'total_conversions_7days': 1245,
                'total_payout_7days': 5240.75,
                'avg_conversion_rate': 18.5,
            },
            'top_offers': [
                {'title': 'Mobile App Install', 'ad_network': 'AdMaven', 'conversions': 420, 'conversion_rate': 22.5, 'total_payout': 2100.00},
            ]
        }
    }
    
    return render(request, 'admin/dashboard.html', context)




from .serializers import (
    UserProfileSerializer, UserProfileCreateSerializer,
    UserProfileUpdateSerializer, UserProfilePublicSerializer,
    ReferralSerializer, StatsSerializer, VerificationSerializer,
    PasswordChangeSerializer
)
from .permissions import (
    IsProfileOwner, IsVerifiedUser, ProfileAccessPermission,
    CanWithdraw, ReferralAccessPermission
)

class UserProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for UserProfile model"""
    queryset = UserProfile.objects.all().select_related('user', 'referred_by')
    serializer_class = UserProfileSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [ProfileAccessPermission]
    lookup_field = 'profile_id'
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserProfileCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserProfileUpdateSerializer
        elif self.action == 'public_profile':
            return UserProfilePublicSerializer
        return super().get_serializer_class()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters
        account_status = self.request.query_params.get('account_status')
        if account_status:
            queryset = queryset.filter(account_status=account_status)
        
        is_premium = self.request.query_params.get('is_premium')
        if is_premium is not None:
            queryset = queryset.filter(is_premium=is_premium.lower() == 'true')
        
        is_affiliate = self.request.query_params.get('is_affiliate')
        if is_affiliate is not None:
            queryset = queryset.filter(is_affiliate=is_affiliate.lower() == 'true')
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search) |
                Q(user__email__icontains=search) |
                Q(phone_number__icontains=search)
            )
        
        return queryset
    
    def get_object(self):
        # For 'me' action, return current user's profile
        if self.kwargs.get('profile_id') == 'me':
            return self.request.user.profile
        
        # For other cases, use the parent method
        return super().get_object()
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's profile"""
        profile = request.user.profile
        serializer = self.get_serializer(profile)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put', 'patch'])
    def update_profile(self, request):
        """Update current user's profile"""
        profile = request.user.profile
        serializer = UserProfileUpdateSerializer(
            profile,
            data=request.data,
            partial=True
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def public_profile(self, request, profile_id=None):
        """Get public profile information"""
        profile = self.get_object()
        serializer = UserProfilePublicSerializer(profile)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get current user's statistics"""
        profile = request.user.profile
        
        # Calculate days since joined
        days_since_joined = (timezone.now() - profile.created_at).days
        
        # Get referral count
        referral_count = profile.referrals.count()
        
        data = {
            'total_points': profile.total_points,
            'total_earnings': profile.total_earnings,
            'total_withdrawn': profile.total_withdrawn,
            'available_balance': profile.available_balance,
            'referral_count': referral_count,
            'is_premium': profile.is_premium,
            'is_affiliate': profile.is_affiliate,
            'account_status': profile.account_status,
            'days_since_joined': days_since_joined
        }
        
        serializer = StatsSerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def referrals(self, request):
        """Get current user's referrals"""
        profile = request.user.profile
        referrals = profile.referrals.all().select_related('user')
        
        page = self.paginate_queryset(referrals)
        if page is not None:
            serializer = ReferralSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ReferralSerializer(referrals, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """Handle verification requests"""
        serializer = VerificationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        profile = request.user.profile
        verification_type = serializer.validated_data['verification_type']
        
        if verification_type == 'email':
            token = serializer.validated_data.get('token')
            
            if not token:
                # Generate and send verification token
                profile.verification_token = str(uuid.uuid4())
                profile.save()
                
                # Send verification email (implement this)
                # send_verification_email(profile.user.email, profile.verification_token)
                
                return Response({
                    'message': 'Verification email sent',
                    'verification_type': 'email'
                })
            else:
                # Verify token
                if profile.verification_token == token:
                    profile.email_verified = True
                    profile.verification_token = ''
                    profile.save()
                    return Response({'message': 'Email verified successfully'})
                else:
                    return Response(
                        {'error': 'Invalid verification token'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        elif verification_type == 'phone':
            # Implement phone verification logic
            phone_number = serializer.validated_data.get('phone_number')
            
            if phone_number:
                profile.phone_number = phone_number
                # Send SMS verification (implement this)
                # send_sms_verification(phone_number)
                return Response({'message': 'SMS verification sent'})
            
            token = serializer.validated_data.get('token')
            if token:
                # Verify SMS token (implement this)
                profile.phone_verified = True
                profile.save()
                return Response({'message': 'Phone verified successfully'})
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Change user password"""
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            
            return Response({'message': 'Password changed successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def upgrade_premium(self, request):
        """Upgrade user to premium"""
        profile = request.user.profile
        
        if profile.is_premium:
            return Response(
                {'error': 'User is already premium'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has sufficient balance/points
        # Implement your upgrade logic here
        
        profile.is_premium = True
        profile.save()
        
        return Response({'message': 'Upgraded to premium successfully'})
    
    @action(detail=False, methods=['post'])
    def become_affiliate(self, request):
        """Become an affiliate"""
        profile = request.user.profile
        
        if profile.is_affiliate:
            return Response(
                {'error': 'User is already an affiliate'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check requirements for becoming affiliate
        if not (profile.email_verified and profile.phone_verified):
            return Response(
                {'error': 'Please verify your email and phone first'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        profile.is_affiliate = True
        profile.save()
        
        return Response({'message': 'Affiliate status activated'})
    
    

class SystemSettingsViewSet(viewsets.ModelViewSet):
    """System settings viewset"""
    queryset = SystemSettings.objects.all()
    
    def get_permissions(self):
        """Allow public access to specific endpoints"""
        if self.action in ['public', 'check_version', 'app_config', 'maintenance_status']:
            return [AllowAny()]
        elif self.action in ['update_settings', 'toggle_maintenance']:
            return [IsAdminUser()]
        return [IsAuthenticated()]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'public':
            return SystemSettingsPublicSerializer
        elif self.action in ['update_settings', 'partial_update']:
            return SystemSettingsUpdateSerializer
        elif self.request.user and self.request.user.is_staff:
            return SystemSettingsAdminSerializer
        return SystemSettingsPublicSerializer
    
    def get_queryset(self):
        """Return cached settings"""
        return SystemSettings.objects.all()

    def list(self, request, *args, **kwargs):
        """Return singleton settings object (not a list)"""
        instance = SystemSettings.objects.first()
        if not instance:
            return Response({}, status=200)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        """PATCH /admin/settings/ — update singleton without :id"""
        instance = SystemSettings.objects.first()
        if not instance:
            return Response({'error': 'Settings not configured'}, status=404)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def public(self, request):
        """Get public system settings (cached)"""
        cache_key = 'system_settings_public'
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            settings = SystemSettings.get_settings()
            serializer = SystemSettingsPublicSerializer(settings)
            cached_data = serializer.data
            cache.set(cache_key, cached_data, 3600)  # Cache for 1 hour
        
        return Response(cached_data)
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny], url_path='check-app-version')
    def check_version(self, request):
        """
        Check if app version is allowed
        
        POST /api/settings/check_version/
        {
            "platform": "android",
            "version_code": 15
        }
        """
        serializer = SystemSettingsVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        platform = serializer.validated_data['platform']
        version_code = serializer.validated_data['version_code']
        
        settings = SystemSettings.get_settings()
        result = settings.check_app_version(platform, version_code)
        
        # Log version check
        logger.info(
            f"Version check: {platform} v{version_code} - "
            f"Allowed: {result['is_allowed']}, Force: {result['force_update']}"
        )
        
        response_serializer = SystemSettingsVersionResponseSerializer(data=result)
        response_serializer.is_valid(raise_exception=True)
        
        return Response(response_serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def app_config(self, request):
        """
        Get complete app configuration for mobile apps
        
        GET /api/settings/app_config/?platform=android&version_code=15
        """
        platform = request.query_params.get('platform', 'android')
        version_code = request.query_params.get('version_code')
        
        settings = SystemSettings.get_settings()
        
        # Check maintenance mode first
        if settings.maintenance_mode:
            if not (request.user.is_authenticated and request.user.is_staff):
                return Response({
                    'maintenance': True,
                    'message': settings.maintenance_message,
                    'expected_end': settings.maintenance_end
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Check version if provided
        if version_code:
            try:
                version_check = settings.check_app_version(platform, int(version_code))
                
                if not version_check['is_allowed']:
                    return Response({
                        'version_check': version_check,
                        'error': 'App version not allowed'
                    }, status=status.HTTP_426_UPGRADE_REQUIRED)
            except ValueError:
                pass
        
        # Return full config
        serializer = AppConfigSerializer(
            settings,
            context={'request': request, 'platform': platform}
        )
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_limits(self, request):
        """
        Get user's daily limits status
        
        GET /api/settings/my_limits/?action_type=ads
        """
        action_type = request.query_params.get('action_type', 'earning')
        
        if action_type not in ['ads', 'videos', 'tasks', 'surveys', 'earning']:
            return Response({
                'error': 'Invalid action_type'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        settings = SystemSettings.get_settings()
        
        # Get current count
        from security.models import ClickTracker
        today = timezone.now().date()
        
        if action_type == 'ads':
            current_count = ClickTracker.get_daily_action_count(
                request.user, 'ad_click', today
            )
            daily_limit = settings.max_daily_ads
        
        elif action_type == 'videos':
            current_count = ClickTracker.get_daily_action_count(
                request.user, 'video_watch', today
            )
            daily_limit = settings.max_daily_videos
        
        elif action_type == 'tasks':
            current_count = ClickTracker.get_daily_action_count(
                request.user, 'task_complete', today
            )
            daily_limit = settings.max_daily_tasks
        
        elif action_type == 'surveys':
            current_count = ClickTracker.get_daily_action_count(
                request.user, 'survey_complete', today
            )
            daily_limit = settings.max_daily_surveys
        
        else:  # earning
            from api.transactions.models import Transaction
            daily_earning = Transaction.objects.filter(
                user=request.user,
                transaction_type='earning',
                created_at__date=today,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            current_count = float(daily_earning)
            daily_limit = float(settings.max_daily_earning_limit)
        
        remaining = max(0, daily_limit - current_count)
        percentage_used = (current_count / daily_limit * 100) if daily_limit > 0 else 0
        is_exceeded = current_count >= daily_limit
        
        data = {
            'action_type': action_type,
            'current_count': current_count,
            'daily_limit': daily_limit,
            'remaining': remaining,
            'percentage_used': round(percentage_used, 2),
            'is_exceeded': is_exceeded
        }
        
        serializer = DailyLimitsSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def payment_gateways(self, request):
        """Get available payment gateways"""
        settings = SystemSettings.get_settings()
        serializer = PaymentGatewayStatusSerializer(settings)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def security_settings(self, request):
        """Get security settings"""
        settings = SystemSettings.get_settings()
        serializer = SecuritySettingsSerializer(settings)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def referral_settings(self, request):
        """Get referral system settings"""
        settings = SystemSettings.get_settings()
        serializer = ReferralSettingsSerializer(settings)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def reward_points(self, request):
        """Get reward points for different actions"""
        settings = SystemSettings.get_settings()
        serializer = RewardPointsSerializer(settings)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def withdrawal_settings(self, request):
        """Get withdrawal settings and limits"""
        settings = SystemSettings.get_settings()
        serializer = WithdrawalSettingsSerializer(settings)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def maintenance_status(self, request):
        """Check maintenance mode status"""
        settings = SystemSettings.get_settings()
        
        return Response({
            'active': settings.maintenance_mode,
            'message': settings.maintenance_message if settings.maintenance_mode else '',
            'start': settings.maintenance_start,
            'end': settings.maintenance_end,
            'allow_admin': settings.allow_admin_during_maintenance
        })
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser], url_path='toggle-maintenance')
    def toggle_maintenance(self, request):
        """
        Toggle maintenance mode
        
        POST /api/settings/toggle_maintenance/
        {
            "enable": true,
            "message": "We're upgrading our systems",
            "expected_end": "2024-12-25T15:00:00Z"
        }
        """
        enable = request.data.get('enable', False)
        message = request.data.get('message', '')
        expected_end = request.data.get('expected_end')
        
        settings = SystemSettings.get_settings()
        settings.maintenance_mode = enable
        
        if enable:
            settings.maintenance_start = timezone.now()
            if message:
                settings.maintenance_message = message
            if expected_end:
                settings.maintenance_end = expected_end
        else:
            settings.maintenance_end = timezone.now()
        
        settings.last_modified_by = request.user
        settings.save()
        
        # Clear cache
        cache.delete('system_settings_public')
        
        logger.warning(
            f"Maintenance mode {'enabled' if enable else 'disabled'} by {request.user.username}"
        )
        
        return Response({
            'maintenance_mode': settings.maintenance_mode,
            'message': settings.maintenance_message
        })
    

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser], url_path='clear-cache')
    def clear_cache(self, request):
        """Clear Django cache"""
        from django.core.cache import cache
        cache.clear()
        return Response({'success': True, 'message': 'System cache cleared successfully'})

    @action(detail=False, methods=['patch'], permission_classes=[IsAdminUser])
    def update_settings(self, request):
        """
        Update system settings (admin only)
        
        PATCH /api/settings/update_settings/
        {
            "min_withdrawal_amount": 100,
            "max_withdrawal_amount": 5000
        }
        """
        settings = SystemSettings.get_settings()
        serializer = SystemSettingsUpdateSerializer(
            settings,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(last_modified_by=request.user)
        
        # Clear cache
        cache.delete('system_settings')
        cache.delete('system_settings_public')
        
        logger.info(f"Settings updated by {request.user.username}: {request.data}")
        
        return Response(serializer.data)


# Alternative function-based views for simple endpoints

@api_view(['GET'])
@permission_classes([AllowAny])
def get_public_settings(request):
    """Simple function view for public settings"""
    cache_key = 'system_settings_public_simple'
    cached_data = cache.get(cache_key)
    
    if cached_data is None:
        settings = SystemSettings.get_settings()
        cached_data = {
            'site_name': settings.site_name,
            'currency_code': settings.currency_code,
            'currency_symbol': settings.currency_symbol,
            'min_withdrawal': float(settings.min_withdrawal_amount),
            'max_withdrawal': float(settings.max_withdrawal_amount),
            'point_value': float(settings.point_value),
            'maintenance': settings.maintenance_mode,
        }
        cache.set(cache_key, cached_data, 3600)
    
    return Response(cached_data)


@api_view(['POST'])
@permission_classes([AllowAny])
def check_version_simple(request):
    """Simple version check endpoint"""
    platform = request.data.get('platform', 'android')
    version_code = request.data.get('version_code', 0)
    
    settings = SystemSettings.get_settings()
    result = settings.check_app_version(platform, int(version_code))
    
    return Response(result)


    @action(detail=False, methods=['get', 'post'])
    def test_sms(self, request, *args, **kwargs):
        return Response({'message': 'test_sms ok'})

    @action(detail=False, methods=['get', 'post'])
    def public_settings(self, request, *args, **kwargs):
        return Response({'message': 'public_settings ok'})

    @action(detail=False, methods=['get', 'post'])
    def stats(self, request, *args, **kwargs):
        return Response({'message': 'stats ok'})

    @action(detail=False, methods=['get', 'post'])
    def test_email(self, request, *args, **kwargs):
        return Response({'message': 'test_email ok'})

    @action(detail=False, methods=['get', 'post'])
    def update_maintenance(self, request, *args, **kwargs):
        return Response({'message': 'update_maintenance ok'})

class SiteNotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for SiteNotification"""
    queryset = SiteNotification.objects.all().order_by('-priority', '-created_at')
    serializer_class = SiteNotificationSerializer
    permission_classes = [SystemAccessPermission]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return NotificationCreateSerializer
        return super().get_serializer_class()
    

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle is_active on a site notification"""
        notif = self.get_object()
        notif.is_active = not notif.is_active
        notif.save(update_fields=['is_active'])
        return Response({'success': True, 'is_active': notif.is_active})

    @action(detail=False, methods=['get'])
    def active_notifications(self, request):
        """Get active notifications (public)"""
        notifications = SiteNotification.objects.filter(
            is_active=True,
            start_date__lte=timezone.now()
        ).filter(
            Q(end_date__gte=timezone.now()) | Q(end_date__isnull=True)
        ).order_by('-priority', '-created_at')
        
        # Cache active notifications
        cache_key = 'active_notifications'
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            serializer = self.get_serializer(notifications, many=True)
            cached_data = serializer.data
            cache.set(cache_key, cached_data, timeout=300)  # 5 minutes
        
        return Response(cached_data)
    
    @action(detail=False, methods=['get'])
    def login_notifications(self, request):
        """Get notifications to show on login"""
        notifications = SiteNotification.objects.filter(
            is_active=True,
            show_on_login=True,
            start_date__lte=timezone.now()
        ).filter(
            Q(end_date__gte=timezone.now()) | Q(end_date__isnull=True)
        ).order_by('-priority', '-created_at')
        
        page = self.paginate_queryset(notifications)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)


class SiteContentViewSet(viewsets.ModelViewSet):
    """ViewSet for SiteContent"""
    queryset = SiteContent.objects.all().order_by('order', 'title')
    serializer_class = SiteContentSerializer
    permission_classes = [SystemAccessPermission]
    lookup_field = 'identifier'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by content type
        content_type = self.request.query_params.get('content_type')
        if content_type:
            queryset = queryset.filter(content_type=content_type)
        
        # Filter by language
        language = self.request.query_params.get('language', 'en')
        queryset = queryset.filter(language=language)
        
        # Filter active only for public endpoints
        if self.action in ['get_content', 'list_public']:
            queryset = queryset.filter(is_active=True)
        
        return queryset
    

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle is_active on a site content"""
        obj = self.get_object()
        obj.is_active = not obj.is_active
        obj.save(update_fields=['is_active'])
        return Response({'success': True, 'is_active': obj.is_active})

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Bulk update ordering: body = { items: [{id, order}] }"""
        from django.db import transaction
        items = request.data.get('items', [])
        with transaction.atomic():
            for item in items:
                SiteContent.objects.filter(pk=item['id']).update(order=item['order'])
        return Response({'success': True, 'updated': len(items)})

    @action(detail=False, methods=['get'])
    def get_content(self, request, identifier=None):
        """Get content by identifier (public)"""
        language = request.query_params.get('language', 'en')
        
        cache_key = f'site_content_{identifier}_{language}'
        cached_content = cache.get(cache_key)
        
        if cached_content is None:
            try:
                content = SiteContent.objects.get(
                    identifier=identifier,
                    language=language,
                    is_active=True
                )
                serializer = self.get_serializer(content)
                cached_content = serializer.data
                cache.set(cache_key, cached_content, timeout=300)  # 5 minutes
            except SiteContent.DoesNotExist:
                return Response(
                    {'error': 'Content not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        return Response(cached_content)
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Get content by type (public)"""
        content_type = request.query_params.get('type')
        language = request.query_params.get('language', 'en')
        
        if not content_type:
            return Response(
                {'error': 'Content type parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        contents = SiteContent.objects.filter(
            content_type=content_type,
            language=language,
            is_active=True
        ).order_by('order')
        
        serializer = self.get_serializer(contents, many=True)
        return Response(serializer.data)


class SystemHealthView(generics.GenericAPIView):
    """System health check endpoint"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        """Check system health"""
        health_status = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'services': {}
        }
        
        # Check database
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_status['services']['database'] = 'healthy'
        except Exception as e:
            health_status['services']['database'] = 'unhealthy'
            health_status['status'] = 'degraded'
        
        # Check cache
        try:
            cache.set('health_check', 'ok', 10)
            if cache.get('health_check') == 'ok':
                health_status['services']['cache'] = 'healthy'
            else:
                health_status['services']['cache'] = 'unhealthy'
                health_status['status'] = 'degraded'
        except Exception:
            health_status['services']['cache'] = 'unhealthy'
            health_status['status'] = 'degraded'
        
        # Check storage (if using file storage)
        try:
            import os
            if os.access(settings.MEDIA_ROOT, os.W_OK):
                health_status['services']['storage'] = 'healthy'
            else:
                health_status['services']['storage'] = 'unhealthy'
                health_status['status'] = 'degraded'
        except Exception:
            health_status['services']['storage'] = 'unhealthy'
            health_status['status'] = 'degraded'
        
        return Response(health_status)

# ── Endpoint Toggle API ────────────────────────────────────────────────────
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.cache import cache
from .endpoint_toggle import EndpointToggle


class EndpointToggleSerializer:
    pass


from rest_framework import serializers as drf_serializers

class EndpointToggleSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = EndpointToggle
        fields = '__all__'


class EndpointToggleViewSet(viewsets.ModelViewSet):
    queryset = EndpointToggle.objects.all().order_by('group', 'path')
    serializer_class = EndpointToggleSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['post'])
    def bulk_toggle(self, request):
        """Toggle multiple endpoints at once"""
        toggles = request.data.get('toggles', [])
        updated = 0
        for item in toggles:
            try:
                obj, created = EndpointToggle.objects.get_or_create(
                    path=item['path'],
                    method=item.get('method', 'ALL'),
                    defaults={
                        'is_enabled': item['is_enabled'],
                        'group': item.get('group', 'other'),
                        'label': item.get('label', ''),
                        'disabled_message': item.get('message', 'Feature temporarily disabled.'),
                    }
                )
                if not created:
                    obj.is_enabled = item['is_enabled']
                    obj.save(update_fields=['is_enabled', 'updated_at'])
                updated += 1
            except Exception:
                pass
        cache.clear()
        return Response({'success': True, 'updated': updated})

    @action(detail=False, methods=['get'])
    def by_group(self, request):
        """Get toggles grouped by category"""
        toggles = EndpointToggle.objects.all()
        groups = {}
        for t in toggles:
            if t.group not in groups:
                groups[t.group] = []
            groups[t.group].append({
                'id': t.id,
                'path': t.path,
                'method': t.method,
                'label': t.label,
                'is_enabled': t.is_enabled,
                'disabled_message': t.disabled_message,
            })
        return Response(groups)

    @action(detail=False, methods=['post'])
    def toggle_group(self, request):
        """Enable/disable entire group"""
        group = request.data.get('group')
        is_enabled = request.data.get('is_enabled', True)
        count = EndpointToggle.objects.filter(group=group).update(is_enabled=is_enabled)
        cache.clear()
        return Response({'success': True, 'updated': count})

    @action(detail=False, methods=['post'])
    def seed_from_schema(self, request):
        """Auto-create toggles from API schema"""
        try:
            from drf_spectacular.generators import SchemaGenerator
            generator = SchemaGenerator()
            schema = generator.get_schema()
            paths = schema.get('paths', {})
            created = 0
            for path, methods in paths.items():
                for method in methods.keys():
                    if method.upper() in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']:
                        group = path.split('/')[2] if len(path.split('/')) > 2 else 'other'
                        _, c = EndpointToggle.objects.get_or_create(
                            path=path,
                            method=method.upper(),
                            defaults={
                                'group': group,
                                'label': f"{method.upper()} {path}",
                                'is_enabled': True,
                            }
                        )
                        if c:
                            created += 1
            return Response({'success': True, 'created': created})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
