# alerts/metrics_collector.py
from django.db.models import Count, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from .models import SystemMetrics
import psutil# pip install psutil
from django.db import connection
from api.models import User, EarningTask, PaymentRequest


class MetricsCollector:
    """Collect system metrics for monitoring"""
    
    @staticmethod
    def collect_all_metrics():
        """Collect all system metrics"""
        from api.models import User, EarningTask, PaymentRequest
        from fraud_detection.models import FraudIndicator
        from security.models import UserBan
        from django.db import connection
        
        now = timezone.now()
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)
        
        # User metrics
        total_users = User.objects.count()
        active_1h = User.objects.filter(last_login__gte=one_hour_ago).count()
        active_24h = User.objects.filter(last_login__gte=one_day_ago).count()
        new_signups = User.objects.filter(date_joined__gte=one_hour_ago).count()
        
        # Earning metrics
        earnings_1h = EarningTask.objects.filter(
            completed_at__gte=one_hour_ago
        ).aggregate(
            total=Sum('coins_earned'),
            count=Count('id')
        )
        
        avg_earning = 0
        if total_users > 0:
            total_earned = EarningTask.objects.aggregate(
                total=Sum('coins_earned')
            )['total'] or 0
            avg_earning = total_earned / total_users
        
        # Payment metrics
        pending_payments = PaymentRequest.objects.filter(status='pending').count()
        payment_requests_1h = PaymentRequest.objects.filter(
            requested_at__gte=one_hour_ago
        ).count()
        
        total_pending = PaymentRequest.objects.filter(
            status='pending'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Security metrics
        fraud_1h = FraudIndicator.objects.filter(
            detected_at__gte=one_hour_ago
        ).count()
        
        banned_24h = UserBan.objects.filter(
            banned_at__gte=one_day_ago
        ).count()
        
        # System health
        try:
            # Database connections
            db_connections = len(connection.queries)
            
            # Redis memory (if available)
            redis_memory = 0
            try:
                from django.core.cache import cache
                info = cache.client.get_client().info('memory')
                redis_memory = info.get('used_memory', 0) / (1024 * 1024)  # MB
            except:
                pass
            
        except:
            db_connections = 0
            redis_memory = 0
        
        # Create metrics record
        metrics = SystemMetrics.objects.create(
            total_users=total_users,
            active_users_1h=active_1h,
            active_users_24h=active_24h,
            new_signups_1h=new_signups,
            total_earnings_1h=earnings_1h['total'] or 0,
            total_tasks_1h=earnings_1h['count'] or 0,
            avg_earning_per_user=avg_earning,
            pending_payments=pending_payments,
            payment_requests_1h=payment_requests_1h,
            total_payout_pending=total_pending,
            fraud_indicators_1h=fraud_1h,
            banned_users_24h=banned_24h,
            db_connections=db_connections,
            redis_memory_mb=redis_memory,
        )
        
        return metrics
