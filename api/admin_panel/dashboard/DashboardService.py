from django.db.models import Count, Sum, Avg
from api.users.models import User
from datetime import datetime, timedelta
from django.utils import timezone


class DashboardService:
    
    @staticmethod
    def get_dashboard_stats():
        today = timezone.now().date()
        
        return {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'verified_users': User.objects.filter(is_verified=True).count(),
            'today_registrations': User.objects.filter(created_at__date=today).count(),
            'total_balance': User.objects.aggregate(total=Sum('balance'))['total'] or 0,
        }
    
    @staticmethod
    def get_user_statistics():
        last_30_days = timezone.now() - timedelta(days=30)
        
        return {
            'new_users_30d': User.objects.filter(created_at__gte=last_30_days).count(),
            'users_by_role': User.objects.values('role').annotate(count=Count('id')),
            'average_balance': User.objects.aggregate(avg=Avg('balance'))['avg'] or 0,
        }
    
    @staticmethod
    def get_revenue_statistics():
        # Placeholder - implement based on payment models
        return {
            'total_revenue': 0,
            'monthly_revenue': 0,
            'pending_payouts': 0,
        }