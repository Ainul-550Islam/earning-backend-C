import json
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters import rest_framework as filters
from django.utils import timezone
from django.db.models import Count, Q, Sum
from django.contrib.auth import get_user_model
from io import BytesIO

from api.rate_limit.models import RateLimitConfig, RateLimitLog, UserRateLimitProfile, AbuseReport, IPBlockList, RateLimitInsight, RateLimitException
from api.rate_limit.serializers import (
    RateLimitConfigSerializer,
    RateLimitLogSerializer,
    UserRateLimitProfileSerializer,
    RateLimitConfigCreateSerializer,
    RateLimitBulkUpdateSerializer,
    RateLimitStatsSerializer,
    AbuseReportSerializer,
    AbuseReportCreateSerializer,
    IPBlockListSerializer,
    IPBlockListCreateSerializer,
    IPBlockBulkCreateSerializer,
    RateLimitInsightSerializer,
    RateLimitExceptionSerializer,
    RateLimitInfoSerializer,
    TaskLimitSerializer,
    OfferLimitSerializer,
    ReferralLimitSerializer,
    AbusePatternSerializer,
)
from rest_framework import serializers
from api.rate_limit.services import RateLimitService
from api.rate_limit.permissions import IsAdminOrRateLimitManager


User = get_user_model()


class RateLimitConfigViewSet(viewsets.ModelViewSet):
    """
    রেট লিমিট কনফিগারেশন ম্যানেজমেন্ট
    """
    queryset = RateLimitConfig.objects.all().order_by('-created_at')
    serializer_class = RateLimitConfigSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['rate_limit_type', 'is_active', 'user', 'endpoint']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return RateLimitConfigCreateSerializer
        return super().get_serializer_class()
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """বাল্ক আপডেট রেট লিমিট কনফিগারেশন"""
        serializer = RateLimitBulkUpdateSerializer(data=request.data)
        if serializer.is_valid():
            configs = serializer.validated_data['configs']
            action_type = serializer.validated_data['action']
            
            updated_count = 0
            for config_data in configs:
                config_id = config_data.pop('id', None)
                if config_id:
                    try:
                        config = RateLimitConfig.objects.get(id=config_id)
                        for key, value in config_data.items():
                            setattr(config, key, value)
                        config.save()
                        updated_count += 1
                    except RateLimitConfig.DoesNotExist:
                        continue
            
            return Response({
                'success': True,
                'message': f'{updated_count}টি কনফিগারেশন আপডেট করা হয়েছে',
                'updated_count': updated_count
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def types(self, request):
        """রেট লিমিট টাইপস লিস্ট"""
        return Response({
            'types': RateLimitConfig.RATE_LIMIT_TYPES,
            'time_units': RateLimitConfig.TIME_UNITS
        })
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """ডুপ্লিকেট রেট লিমিট কনফিগারেশন"""
        config = self.get_object()
        config.pk = None
        config.name = f"{config.name} (কপি)"
        config.save()
        
        serializer = self.get_serializer(config)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """টেস্ট রেট লিমিট কনফিগারেশন"""
        config = self.get_object()
        test_data = request.data
        
        # Simulate request
        from django.test import RequestFactory
        factory = RequestFactory()
        
        test_request = factory.get(test_data.get('endpoint', '/api/test/'))
        test_request.user = request.user
        
        # Add test attributes
        for attr in ['task_id', 'offer_id', 'task_type', 'offer_wall', 'referral_code']:
            if attr in test_data:
                setattr(test_request, attr, test_data[attr])
        
        # Check rate limit
        rate_limit_service = RateLimitService()
        result = rate_limit_service.redis_limiter.check_rate_limit(test_request, config)
        
        return Response({
            'config': RateLimitConfigSerializer(config).data,
            'test_data': test_data,
            'result': {
                'is_allowed': result[0],
                'metadata': result[1]
            }
        })


class RateLimitLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    রেট লিমিট লগ ভিউ
    """
    queryset = RateLimitLog.objects.all().order_by('-timestamp')
    serializer_class = RateLimitLogSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['user', 'ip_address', 'endpoint', 'status', 'config']
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """রেট লিমিট স্ট্যাটিস্টিক্স"""
        timeframe = request.query_params.get('timeframe', '24h')
        
        if timeframe == '24h':
            since = timezone.now() - timezone.timedelta(hours=24)
        elif timeframe == '7d':
            since = timezone.now() - timezone.timedelta(days=7)
        elif timeframe == '30d':
            since = timezone.now() - timezone.timedelta(days=30)
        else:
            since = timezone.now() - timezone.timedelta(hours=24)
        
        # Aggregate statistics
        logs = RateLimitLog.objects.filter(timestamp__gte=since)
        
        total_requests = logs.count()
        blocked_requests = logs.filter(status='blocked').count()
        allowed_requests = logs.filter(status='allowed').count()
        
        # Top blocked users
        top_blocked_users = logs.filter(status='blocked').values(
            'user__username', 'user__id'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Top blocked endpoints
        top_blocked_endpoints = logs.filter(status='blocked').values(
            'endpoint'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Hourly distribution
        from django.db.models.functions import TruncHour
        hourly_data = logs.annotate(
            hour=TruncHour('timestamp')
        ).values('hour').annotate(
            total=Count('id'),
            blocked=Count('id', filter=Q(status='blocked'))
        ).order_by('hour')
        
        return Response({
            'timeframe': timeframe,
            'since': since,
            'total_requests': total_requests,
            'blocked_requests': blocked_requests,
            'allowed_requests': allowed_requests,
            'block_rate': (blocked_requests / total_requests * 100) if total_requests > 0 else 0,
            'top_blocked_users': list(top_blocked_users),
            'top_blocked_endpoints': list(top_blocked_endpoints),
            'hourly_distribution': list(hourly_data)
        })
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """এক্সপোর্ট রেট লিমিট লগ"""
        format = request.query_params.get('format', 'csv')
        logs = self.filter_queryset(self.get_queryset())
        
        if format == 'csv':
            try:
                import pandas as pd
            except ImportError:
                return Response({'error': 'pandas not installed'}, status=500)
            # Convert to DataFrame
            data = list(logs.values(
                'timestamp', 'user__username', 'ip_address', 
                'endpoint', 'request_method', 'status',
                'config__name', 'task_id', 'offer_id'
            ))
            
            df = pd.DataFrame(data)
            df.columns = ['Timestamp', 'User', 'IP Address', 'Endpoint', 
                         'Method', 'Status', 'Config', 'Task ID', 'Offer ID']
            
            # Create CSV
            output = BytesIO()
            df.to_csv(output, index=False, encoding='utf-8')
            output.seek(0)
            
            from django.http import HttpResponse
            response = HttpResponse(output, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="rate_limit_logs.csv"'
            return response
        
        elif format == 'json':
            serializer = self.get_serializer(logs, many=True)
            return Response(serializer.data)
        
        return Response({'error': 'Invalid format'}, status=400)
    
    @action(detail=False, methods=['delete'])
    def clear_old(self, request):
        """পুরানো লগ ডিলিট করুন"""
        days = int(request.query_params.get('days', 30))
        
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        deleted_count, _ = RateLimitLog.objects.filter(
            timestamp__lt=cutoff_date
        ).delete()
        
        return Response({
            'success': True,
            'message': f'{deleted_count}টি পুরানো লগ ডিলিট করা হয়েছে',
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date
        })


class UserRateLimitProfileViewSet(viewsets.ModelViewSet):
    """
    ইউজার রেট লিমিট প্রোফাইল ম্যানেজমেন্ট
    """
    queryset = UserRateLimitProfile.objects.all().order_by('-created_at')
    serializer_class = UserRateLimitProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['is_premium', 'user']
    
    @action(detail=True, methods=['post'])
    def reset_limits(self, request, pk=None):
        """রিসেট ইউজার রেট লিমিট"""
        profile = self.get_object()
        rate_limit_service = RateLimitService()
        
        rate_limit_service.reset_user_limits(profile.user)
        
        return Response({
            'success': True,
            'message': f'{profile.user.username} এর সকল রেট লিমিট রিসেট করা হয়েছে'
        })
    
    @action(detail=True, methods=['post'])
    def upgrade_premium(self, request, pk=None):
        """আপগ্রেড ইউজার টু প্রিমিয়াম"""
        profile = self.get_object()
        duration_days = request.data.get('duration_days', 30)
        
        profile.is_premium = True
        profile.premium_until = timezone.now() + timezone.timedelta(days=duration_days)
        profile.save()
        
        return Response({
            'success': True,
            'message': f'{profile.user.username} কে প্রিমিয়ামে আপগ্রেড করা হয়েছে',
            'premium_until': profile.premium_until
        })
    
    @action(detail=True, methods=['post'])
    def set_custom_limits(self, request, pk=None):
        """সেট কাস্টম লিমিট ফর ইউজার"""
        profile = self.get_object()
        
        daily_limit = request.data.get('daily_limit')
        hourly_limit = request.data.get('hourly_limit')
        
        if daily_limit:
            profile.custom_daily_limit = daily_limit
        if hourly_limit:
            profile.custom_hourly_limit = hourly_limit
        
        profile.save()
        
        return Response({
            'success': True,
            'message': f'{profile.user.username} এর কাস্টম লিমিট সেট করা হয়েছে',
            'custom_daily_limit': profile.custom_daily_limit,
            'custom_hourly_limit': profile.custom_hourly_limit
        })


class RateLimitHealthView(APIView):
    """
    রেট লিমিট সিস্টেম হেলথ চেক
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        rate_limit_service = RateLimitService()
        health_info = rate_limit_service.get_system_health()
        
        return Response(health_info)


class RateLimitTestView(APIView):
    """
    টেস্ট রেট লিমিট এন্ডপয়েন্ট
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Get user's current rate limit info
        rate_limit_service = RateLimitService()
        user_info = rate_limit_service.get_user_rate_limit_info(request.user)
        
        return Response(user_info)
    
    def post(self, request):
        # Test specific rate limit configuration
        config_name = request.data.get('config_name')
        endpoint = request.data.get('endpoint', '/api/test/')
        
        from django.test import RequestFactory
        factory = RequestFactory()
        test_request = factory.get(endpoint)
        test_request.user = request.user
        
        # Copy attributes from request data
        for attr in ['task_id', 'offer_id', 'task_type', 'offer_wall', 'referral_code']:
            if attr in request.data:
                setattr(test_request, attr, request.data[attr])
        
        rate_limit_service = RateLimitService()
        
        if config_name:
            # Test specific config
            try:
                from api.rate_limit.models import RateLimitConfig
                config = RateLimitConfig.objects.get(name=config_name, is_active=True)
                result = rate_limit_service.redis_limiter.check_rate_limit(test_request, config)
                
                return Response({
                    'config': config_name,
                    'is_allowed': result[0],
                    'metadata': result[1]
                })
            except RateLimitConfig.DoesNotExist:
                return Response({'error': 'Config not found'}, status=404)
        else:
            # Test all applicable configs
            result = rate_limit_service.check_request(test_request, log_request=False)
            return Response(result)


class RateLimitDashboardView(APIView):
    """
    রেট লিমিট ড্যাশবোর্ড ডেটা
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def get(self, request):
        # Get timeframe
        timeframe = request.query_params.get('timeframe', '24h')
        
        if timeframe == '24h':
            since = timezone.now() - timezone.timedelta(hours=24)
        elif timeframe == '7d':
            since = timezone.now() - timezone.timedelta(days=7)
        elif timeframe == '30d':
            since = timezone.now() - timezone.timedelta(days=30)
        else:
            since = timezone.now() - timezone.timedelta(hours=24)
        
        # Dashboard data
        total_configs = RateLimitConfig.objects.count()
        active_configs = RateLimitConfig.objects.filter(is_active=True).count()
        
        total_logs = RateLimitLog.objects.filter(timestamp__gte=since).count()
        blocked_logs = RateLimitLog.objects.filter(
            timestamp__gte=since, status='blocked'
        ).count()
        
        # User statistics
        user_stats = UserRateLimitProfile.objects.aggregate(
            total_users=Count('id'),
            premium_users=Count('id', filter=Q(is_premium=True)),
            avg_requests=Sum('total_requests') / Count('id')
        )
        
        # Top 5 active configs
        top_configs = RateLimitLog.objects.filter(
            timestamp__gte=since
        ).values(
            'config__name'
        ).annotate(
            count=Count('id'),
            blocked=Count('id', filter=Q(status='blocked'))
        ).order_by('-count')[:5]
        
        # Recent blocked requests
        recent_blocked = RateLimitLog.objects.filter(
            status='blocked'
        ).order_by('-timestamp')[:10]
        
        recent_blocked_data = RateLimitLogSerializer(recent_blocked, many=True).data
        
        return Response({
            'timeframe': timeframe,
            'summary': {
                'total_configs': total_configs,
                'active_configs': active_configs,
                'total_requests': total_logs,
                'blocked_requests': blocked_logs,
                'block_rate': (blocked_logs / total_logs * 100) if total_logs > 0 else 0
            },
            'user_statistics': user_stats,
            'top_configs': list(top_configs),
            'recent_blocked': recent_blocked_data
        })


# Abuse Report ViewSet
class AbuseReportViewSet(viewsets.ModelViewSet):
    """
    অ্যাবিউজ রিপোর্ট ম্যানেজমেন্ট
    """
    queryset = AbuseReport.objects.all().order_by('-created_at')
    serializer_class = AbuseReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['abuse_type', 'severity', 'is_blocked', 'is_investigated']

    def get_parsers(self):
        from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
        return [JSONParser(), MultiPartParser(), FormParser()]

    def _parse_json_fields(self, data):
        """Parse JSON string fields in multipart data."""
        try:
            mutable = data.copy()
        except AttributeError:
            return data
        for field in ['evidence', 'metadata']:
            if field in mutable and isinstance(mutable[field], str):
                try:
                    mutable[field] = json.loads(mutable[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return mutable

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsAdminOrRateLimitManager()]

    def create(self, request, *args, **kwargs):
        # Handle dict fields sent as multipart
        if hasattr(request.data, 'copy'):
            request._full_data = self._parse_json_fields(request.data)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user if self.request.user.is_authenticated else None)


# IP Block List ViewSet
class IPBlockListViewSet(viewsets.ModelViewSet):
    """
    আইপি ব্লক লিস্ট ম্যানেজমেন্ট
    """
    queryset = IPBlockList.objects.all().order_by('-created_at')
    serializer_class = IPBlockListSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['block_type', 'reason', 'is_active', 'permanent']
    
    @action(detail=False, methods=['post'])
    def bulk_block(self, request):
        """বাল্ক আইপি ব্লক"""
        ip_addresses = request.data.get('ip_addresses', [])
        reason = request.data.get('reason', 'manual')
        description = request.data.get('description', '')
        duration_days = request.data.get('duration_days', 7)
        
        from api.rate_limit.services.IPBlockService import IPBlockService
        ip_block_service = IPBlockService()
        
        blocked_count = 0
        for ip_address in ip_addresses:
            try:
                ip_block_service.block_ip(
                    ip_address=ip_address,
                    reason=reason,
                    description=description,
                    duration_days=duration_days,
                    blocked_by=request.user
                )
                blocked_count += 1
            except Exception:
                continue
        
        return Response({
            'success': True,
            'message': f'{blocked_count}টি আইপি ব্লক করা হয়েছে',
            'blocked_count': blocked_count
        })
    
    @action(detail=False, methods=['post'])
    def cleanup_expired(self, request):
        """এক্সপায়ার্ড আইপি ব্লক ক্লিনআপ"""
        from api.rate_limit.services.IPBlockService import IPBlockService
        ip_block_service = IPBlockService()
        
        cleaned_count = ip_block_service.cleanup_expired_blocks()
        
        return Response({
            'success': True,
            'message': f'{cleaned_count}টি এক্সপায়ার্ড ব্লক ক্লিন করা হয়েছে',
            'cleaned_count': cleaned_count
        })


# Rate Limit Insight ViewSet
class RateLimitInsightViewSet(viewsets.ReadOnlyModelViewSet):
    """
    রেট লিমিট ইনসাইট ভিউ
    """
    queryset = RateLimitInsight.objects.all().order_by('-date')
    serializer_class = RateLimitInsightSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['date', 'hour']
    
    @action(detail=False, methods=['post'])
    def generate(self, request):
        """ইনসাইট জেনারেট করুন"""
        from api.rate_limit.services.RateLimitInsightService import RateLimitInsightService
        service = RateLimitInsightService()
        
        date_str = request.data.get('date')
        if date_str:
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date = timezone.now().date()
        
        try:
            insight = service.generate_daily_insights(date)
            return Response({
                'success': True,
                'message': f'{date} এর জন্য ইনসাইট জেনারেট করা হয়েছে',
                'insight': insight
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=400)
    
    @action(detail=False, methods=['get'])
    def weekly_report(self, request):
        """সাপ্তাহিক রিপোর্ট"""
        from api.rate_limit.services.RateLimitInsightService import RateLimitInsightService
        service = RateLimitInsightService()
        
        try:
            report = service.generate_weekly_report()
            return Response(report)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=400)


# Rate Limit Exception ViewSet
class RateLimitExceptionViewSet(viewsets.ModelViewSet):
    """
    রেট লিমিট এক্সেপশন ম্যানেজমেন্ট
    """
    queryset = RateLimitException.objects.all().order_by('-created_at')
    serializer_class = RateLimitExceptionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['exception_type', 'is_active', 'permanent']
    
    def perform_create(self, serializer):
        serializer.save(granted_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """এক্সেপশন রিভোক করুন"""
        exception = self.get_object()
        exception.is_active = False
        exception.save()
        
        return Response({
            'success': True,
            'message': 'এক্সেপশন রিভোক করা হয়েছে'
        })


# Additional API Views
class UserRateLimitInfoView(APIView):
    """ইউজার রেট লিমিট ইনফো"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        rate_limit_service = RateLimitService()
        user_info = rate_limit_service.get_user_rate_limit_info(request.user)
        return Response(user_info)


class UserRateLimitProfileDetailView(APIView):
    """ইউজার রেট লিমিট প্রোফাইল ডিটেইল"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            profile = UserRateLimitProfile.objects.get(user=request.user)
            serializer = UserRateLimitProfileSerializer(profile)
            return Response(serializer.data)
        except UserRateLimitProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=404)


class UserRateLimitResetView(APIView):
    """ইউজার রেট লিমিট রিসেট"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        rate_limit_service = RateLimitService()
        rate_limit_service.reset_user_limits(request.user)
        
        return Response({
            'success': True,
            'message': 'আপনার রেট লিমিট রিসেট করা হয়েছে'
        })


class AbuseDetectionView(APIView):
    """অ্যাবিউজ ডিটেকশন"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def post(self, request):
        from api.rate_limit.services.AbuseDetectionService import AbuseDetectionService
        service = AbuseDetectionService()
        
        ip_address = request.data.get('ip_address')
        user_id = request.data.get('user_id')
        endpoint = request.data.get('endpoint')
        time_window = request.data.get('time_window', 3600)
        
        patterns = service.detect_abuse_patterns(
            ip_address=ip_address,
            user_id=user_id,
            endpoint=endpoint,
            time_window=time_window
        )
        
        return Response({
            'patterns': patterns,
            'risk_score': patterns.get('risk_score', 0)
        })


class AbuseInvestigationView(APIView):
    """অ্যাবিউজ ইনভেস্টিগেশন"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def post(self, request):
        report_id = request.data.get('report_id')
        action = request.data.get('action')  # 'investigate', 'block', 'close'
        
        try:
            report = AbuseReport.objects.get(id=report_id)
            
            if action == 'investigate':
                report.is_investigated = True
                report.save()
                message = 'রিপোর্ট ইনভেস্টিগেট করা হয়েছে'
            elif action == 'block':
                from api.rate_limit.services.IPBlockService import IPBlockService
                ip_block_service = IPBlockService()
                ip_block_service.block_ip(
                    ip_address=report.ip_address,
                    reason='manual',
                    description=f"Manual block from abuse investigation",
                    blocked_by=request.user
                )
                report.is_blocked = True
                report.save()
                message = 'আইপি ব্লক করা হয়েছে'
            elif action == 'close':
                report.is_investigated = True
                report.save()
                message = 'রিপোর্ট বন্ধ করা হয়েছে'
            
            return Response({
                'success': True,
                'message': message
            })
            
        except AbuseReport.DoesNotExist:
            return Response({'error': 'Report not found'}, status=404)


class CreateAbuseReportView(APIView):
    """অ্যাবিউজ রিপোর্ট তৈরি করুন"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        from api.rate_limit.services.AbuseDetectionService import AbuseDetectionService
        service = AbuseDetectionService()
        
        try:
            report = service.create_abuse_report(
                ip_address=request.data.get('ip_address'),
                user=request.user if request.user.is_authenticated else None,
                endpoint=request.data.get('endpoint'),
                abuse_type=request.data.get('abuse_type'),
                severity=request.data.get('severity', 3),
                metadata=request.data.get('metadata', {})
            )
            
            return Response({
                'success': True,
                'message': 'অ্যাবিউজ রিপোর্ট তৈরি করা হয়েছে',
                'report_id': report.id
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=400)


class IPBlockCheckView(APIView):
    """আইপি ব্লক চেক"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        from api.rate_limit.services.IPBlockService import IPBlockService
        ip_block_service = IPBlockService()
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        is_blocked, block_info = ip_block_service.is_ip_blocked(ip)
        
        return Response({
            'ip_address': ip,
            'is_blocked': is_blocked,
            'block_info': block_info
        })


class IPBlockCreateView(APIView):
    """আইপি ব্লক তৈরি করুন"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def post(self, request):
        from api.rate_limit.services.IPBlockService import IPBlockService
        ip_block_service = IPBlockService()
        
        try:
            block = ip_block_service.block_ip(
                ip_address=request.data.get('ip_address'),
                reason=request.data.get('reason', 'manual'),
                description=request.data.get('description', ''),
                duration_days=request.data.get('duration_days', 7),
                blocked_by=request.user
            )
            
            return Response({
                'success': True,
                'message': 'আইপি ব্লক করা হয়েছে',
                'block_id': block.id
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=400)


class IPBlockUnblockView(APIView):
    """আইপি আনব্লক করুন"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def post(self, request):
        from api.rate_limit.services.IPBlockService import IPBlockService
        ip_block_service = IPBlockService()
        
        ip_address = request.data.get('ip_address')
        
        try:
            result = ip_block_service.unblock_ip(ip_address, request.user)
            
            return Response({
                'success': True,
                'message': 'আইপি আনব্লক করা হয়েছে',
                'result': result
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=400)


class IPBlockCleanupView(APIView):
    """আইপি ব্লক ক্লিনআপ"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def post(self, request):
        from api.rate_limit.services.IPBlockService import IPBlockService
        ip_block_service = IPBlockService()
        
        cleaned_count = ip_block_service.cleanup_expired_blocks()
        
        return Response({
            'success': True,
            'message': f'{cleaned_count}টি এক্সপায়ার্ড ব্লক ক্লিন করা হয়েছে',
            'cleaned_count': cleaned_count
        })


class GenerateInsightsView(APIView):
    """ইনসাইট জেনারেট করুন"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def post(self, request):
        from api.rate_limit.services.RateLimitInsightService import RateLimitInsightService
        service = RateLimitInsightService()
        
        date_str = request.data.get('date')
        if date_str:
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date = timezone.now().date()
        
        try:
            insight = service.generate_daily_insights(date)
            return Response({
                'success': True,
                'message': f'{date} এর জন্য ইনসাইট জেনারেট করা হয়েছে',
                'insight': insight
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=400)


class ExportInsightsView(APIView):
    """ইনসাইট এক্সপোর্ট করুন"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def get(self, request):
        format_type = request.query_params.get('format', 'csv')
        
        insights = RateLimitInsight.objects.all().order_by('-date')
        
        if format_type == 'csv':
            data = list(insights.values(
                'date', 'total_requests', 'blocked_requests', 'unique_users',
                'unique_ips', 'abuse_reports_count'
            ))
            
            df = pd.DataFrame(data)
            df.columns = ['Date', 'Total Requests', 'Blocked Requests', 
                         'Unique Users', 'Unique IPs', 'Abuse Reports']
            
            output = BytesIO()
            df.to_csv(output, index=False, encoding='utf-8')
            output.seek(0)
            
            from django.http import HttpResponse
            response = HttpResponse(output, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="rate_limit_insights.csv"'
            return response
        
        return Response({'error': 'Invalid format'}, status=400)


class WeeklyInsightsView(APIView):
    """সাপ্তাহিক ইনসাইট"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def get(self, request):
        from api.rate_limit.services.RateLimitInsightService import RateLimitInsightService
        service = RateLimitInsightService()
        
        try:
            report = service.generate_weekly_report()
            return Response(report)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=400)


class GrantExceptionView(APIView):
    """এক্সেপশন গ্রান্ট করুন"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def post(self, request):
        try:
            exception = RateLimitException.objects.create(
                user_id=request.data.get('user_id'),
                ip_address=request.data.get('ip_address'),
                endpoint_pattern=request.data.get('endpoint_pattern'),
                exception_type=request.data.get('exception_type', 'custom'),
                reason=request.data.get('reason', ''),
                multiplier=request.data.get('multiplier', 1),
                max_requests=request.data.get('max_requests'),
                permanent=request.data.get('permanent', False),
                expires_at=timezone.now() + timezone.timedelta(days=request.data.get('duration_days', 7)),
                granted_by=request.user
            )
            
            return Response({
                'success': True,
                'message': 'এক্সেপশন গ্রান্ট করা হয়েছে',
                'exception_id': exception.id
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=400)


class RevokeExceptionView(APIView):
    """এক্সেপশন রিভোক করুন"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def post(self, request):
        exception_id = request.data.get('exception_id')
        
        try:
            exception = RateLimitException.objects.get(id=exception_id)
            exception.is_active = False
            exception.save()
            
            return Response({
                'success': True,
                'message': 'এক্সেপশন রিভোক করা হয়েছে'
            })
            
        except RateLimitException.DoesNotExist:
            return Response({'error': 'Exception not found'}, status=404)


class CheckExceptionView(APIView):
    """এক্সেপশন চেক করুন"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        try:
            exceptions = RateLimitException.objects.filter(
                Q(user=request.user) | Q(ip_address=ip),
                is_active=True
            )
            
            valid_exceptions = []
            for exception in exceptions:
                if exception.applies_to_request(request.user, ip, request.path):
                    valid_exceptions.append(exception)
            
            return Response({
                'has_exception': len(valid_exceptions) > 0,
                'exceptions': valid_exceptions
            })
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=500)


# Earning App Specific Views
class TaskRateLimitView(APIView):
    """টাস্ক রেট লিমিট চেক"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        rate_limit_service = RateLimitService()
        task_type = request.query_params.get('task_type', 'default')
        
        try:
            task_limit = rate_limit_service.check_task_completion_limit(request.user, task_type)
            return Response(task_limit)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class OfferRateLimitView(APIView):
    """অফার রেট লিমিট চেক"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        rate_limit_service = RateLimitService()
        offer_wall = request.query_params.get('offer_wall', 'default')
        
        try:
            offer_limit = rate_limit_service.check_offer_access_limit(request.user, offer_wall)
            return Response(offer_limit)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class ReferralRateLimitView(APIView):
    """রেফারেল রেট লিমিট চেক"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        rate_limit_service = RateLimitService()
        
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        try:
            referral_limit = rate_limit_service.check_referral_activity(ip)
            return Response(referral_limit)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class WithdrawalRateLimitView(APIView):
    """উত্তোলন রেট লিমিট চেক"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        rate_limit_service = RateLimitService()
        
        try:
            # Check if user has made too many withdrawal requests today
            today = timezone.now().date()
            key = f"withdrawal_requests:{request.user.id}:{today}"
            
            redis_client = rate_limit_service.redis_limiter.redis_client
            request_count = redis_client.get(key) or 0
            
            return Response({
                'requests_today': int(request_count),
                'limit': 3,
                'remaining': max(0, 3 - int(request_count))
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=500)


# Management Views
class SyncRateLimitsView(APIView):
    """রেট লিমিট সিঙ্ক করুন"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def post(self, request):
        rate_limit_service = RateLimitService()
        
        try:
            result = rate_limit_service.sync_all_configs()
            return Response({
                'success': True,
                'message': 'রেট লিমিট সিঙ্ক করা হয়েছে',
                'result': result
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=500)


class ExportRateLimitsView(APIView):
    """রেট লিমিট এক্সপোর্ট করুন"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def get(self, request):
        format_type = request.query_params.get('format', 'json')
        
        configs = RateLimitConfig.objects.all()
        
        if format_type == 'csv':
            data = list(configs.values(
                'name', 'rate_limit_type', 'requests_per_unit', 'time_unit',
                'time_value', 'is_active', 'user__username', 'endpoint'
            ))
            
            df = pd.DataFrame(data)
            df.columns = ['Name', 'Type', 'Requests', 'Time Unit', 
                         'Time Value', 'Active', 'User', 'Endpoint']
            
            output = BytesIO()
            df.to_csv(output, index=False, encoding='utf-8')
            output.seek(0)
            
            from django.http import HttpResponse
            response = HttpResponse(output, content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="rate_limit_configs.csv"'
            return response
        
        return Response({'error': 'Invalid format'}, status=400)


class ImportRateLimitsView(APIView):
    """রেট লিমিট ইমপোর্ট করুন"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def post(self, request):
        # Implementation for importing rate limits
        return Response({
            'success': True,
            'message': 'ইমপোর্ট ফাংশনালিটি এখনও ইমপ্লিমেন্ট করা হয়নি'
        })


class CleanupRateLimitsView(APIView):
    """রেট লিমিট ক্লিনআপ"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def post(self, request):
        days = request.data.get('days', 30)
        
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        deleted_count, _ = RateLimitLog.objects.filter(
            timestamp__lt=cutoff_date
        ).delete()
        
        return Response({
            'success': True,
            'message': f'{deleted_count}টি পুরানো লগ ডিলিট করা হয়েছে',
            'deleted_count': deleted_count
        })


# Configuration Views
class BulkActivateConfigsView(APIView):
    """বাল্ক অ্যাক্টিভেট কনফিগ"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def post(self, request):
        config_ids = request.data.get('config_ids', [])
        
        updated = RateLimitConfig.objects.filter(id__in=config_ids).update(is_active=True)
        
        return Response({
            'success': True,
            'message': f'{updated}টি কনফিগ অ্যাক্টিভেট করা হয়েছে',
            'updated_count': updated
        })


class SimulateImpactView(APIView):
    """ইমপ্যাক্ট সিমুলেট করুন"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def post(self, request):
        config_id = request.data.get('config_id')
        hours = request.data.get('hours', 24)
        
        try:
            config = RateLimitConfig.objects.get(id=config_id)
            simulation = config.simulate_impact(hours=hours)
            
            return Response({
                'config_name': config.name,
                'simulation': simulation
            })
            
        except RateLimitConfig.DoesNotExist:
            return Response({'error': 'Config not found'}, status=404)


class BackupConfigsView(APIView):
    """কনফিগ ব্যাকআপ করুন"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def get(self, request):
        configs = RateLimitConfig.objects.all()
        data = []
        
        for config in configs:
            config_data = {
                'name': config.name,
                'rate_limit_type': config.rate_limit_type,
                'requests_per_unit': config.requests_per_unit,
                'time_unit': config.time_unit,
                'time_value': config.time_value,
                'is_active': config.is_active,
                'user': config.user.username if config.user else None,
                'endpoint': config.endpoint,
                'ip_address': config.ip_address,
                'whitelist': config.whitelist,
                'blacklist': config.blacklist,
                'bypass_keys': config.bypass_keys
            }
            data.append(config_data)
        
        return Response({
            'configs': data,
            'exported_at': timezone.now().isoformat()
        })


class RestoreConfigsView(APIView):
    """কনফিগ রিস্টোর করুন"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def post(self, request):
        configs_data = request.data.get('configs', [])
        restored_count = 0
        
        for config_data in configs_data:
            try:
                user_id = config_data.get('user')
                user = User.objects.get(id=user_id) if user_id else None
                
                RateLimitConfig.objects.update_or_create(
                    name=config_data['name'],
                    defaults={
                        'rate_limit_type': config_data['rate_limit_type'],
                        'requests_per_unit': config_data['requests_per_unit'],
                        'time_unit': config_data['time_unit'],
                        'time_value': config_data['time_value'],
                        'is_active': config_data['is_active'],
                        'user': user,
                        'endpoint': config_data.get('endpoint'),
                        'ip_address': config_data.get('ip_address'),
                        'whitelist': config_data.get('whitelist'),
                        'blacklist': config_data.get('blacklist'),
                        'bypass_keys': config_data.get('bypass_keys')
                    }
                )
                restored_count += 1
                
            except Exception:
                continue
        
        return Response({
            'success': True,
            'message': f'{restored_count}টি কনফিগ রিস্টোর করা হয়েছে',
            'restored_count': restored_count
        })


# Analytics View
class RateLimitAnalyticsView(APIView):
    """রেট লিমিট অ্যানালিটিক্স"""
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    
    def get(self, request):
        timeframe = request.query_params.get('timeframe', '24h')
        
        if timeframe == '24h':
            since = timezone.now() - timezone.timedelta(hours=24)
        elif timeframe == '7d':
            since = timezone.now() - timezone.timedelta(days=7)
        elif timeframe == '30d':
            since = timezone.now() - timezone.timedelta(days=30)
        else:
            since = timezone.now() - timezone.timedelta(hours=24)
        
        # Analytics data
        analytics_data = {
            'timeframe': timeframe,
            'since': since,
            'total_requests': RateLimitLog.objects.filter(timestamp__gte=since).count(),
            'blocked_requests': RateLimitLog.objects.filter(
                timestamp__gte=since, status='blocked'
            ).count(),
            'abuse_reports': AbuseReport.objects.filter(
                created_at__gte=since
            ).count(),
            'active_blocks': IPBlockList.objects.filter(
                is_active=True, created_at__gte=since
            ).count(),
            'unique_users': RateLimitLog.objects.filter(
                timestamp__gte=since
            ).values('user').distinct().count(),
            'unique_ips': RateLimitLog.objects.filter(
                timestamp__gte=since
            ).values('ip_address').distinct().count()
        }
        
        return Response(analytics_data)


class RateLimitStatsView(APIView):
    """রেট লিমিট স্ট্যাটিস্টিক্স"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        rate_limit_service = RateLimitService()
        stats = rate_limit_service.get_system_stats()
        
        return Response(stats)


# Add missing serializers

# Alias for backwards compatibility
RateLimitStatsAPIView = RateLimitStatsView


class RateLimitWebhookListView(APIView):
    """List and register webhooks."""
    permission_classes = [IsAdminOrRateLimitManager]

    def get(self, request):
        from api.rate_limit.webhooks import RateLimitWebhookManager
        try:
            manager = RateLimitWebhookManager()
            webhooks = manager.list_webhooks() if hasattr(manager, 'list_webhooks') else []
        except Exception:
            webhooks = []
        return Response({'webhooks': webhooks, 'count': len(webhooks)})

    def post(self, request):
        from api.rate_limit.webhooks import RateLimitWebhookManager
        try:
            manager = RateLimitWebhookManager()
            result = manager.register_webhook(
                url=request.data.get('url', ''),
                events=request.data.get('events', []),
                secret=request.data.get('secret'),
                name=request.data.get('name', ''),
            )
        except Exception as e:
            result = {'error': str(e)}
        return Response(result, status=status.HTTP_201_CREATED)


class RateLimitWebhookDetailView(APIView):
    """Retrieve or delete a webhook."""
    permission_classes = [IsAdminOrRateLimitManager]

    def get(self, request, webhook_id):
        from api.rate_limit.webhooks import RateLimitWebhookManager
        try:
            manager = RateLimitWebhookManager()
            webhooks = manager.list_webhooks() if hasattr(manager, 'list_webhooks') else []
            webhook = next((w for w in webhooks if str(w.get('id', '')) == str(webhook_id)), None)
        except Exception:
            webhook = None
        if not webhook:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(webhook)

    def delete(self, request, webhook_id):
        from api.rate_limit.webhooks import RateLimitWebhookManager
        try:
            manager = RateLimitWebhookManager()
            if hasattr(manager, 'delete_webhook'):
                manager.delete_webhook(webhook_id)
        except Exception:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)

    def put(self, request, webhook_id):
        return self.get(request, webhook_id)
