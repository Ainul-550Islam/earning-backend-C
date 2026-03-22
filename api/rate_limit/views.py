from api.tenants.mixins import TenantMixin
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters import rest_framework as filters
from django.utils import timezone
from django.db.models import Count, Q, Sum
from django.contrib.auth import get_user_model
import pandas as pd
from io import BytesIO

from .models import RateLimitConfig, RateLimitLog, UserRateLimitProfile
from .serializers import (
    RateLimitConfigSerializer,
    RateLimitLogSerializer,
    UserRateLimitProfileSerializer,
    RateLimitConfigCreateSerializer,
    RateLimitBulkUpdateSerializer,
    RateLimitStatsSerializer
)
from .services import RateLimitService
from .permissions import IsAdminOrRateLimitManager


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
                from .models import RateLimitConfig
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