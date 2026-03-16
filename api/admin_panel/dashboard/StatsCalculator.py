from django.db.models import Count, Sum
from datetime import timedelta
from django.utils import timezone


class StatsCalculator:
    
    @staticmethod
    def calculate_growth_rate(model, days=30):
        """Calculate growth rate for given period"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        mid_date = start_date + timedelta(days=days//2)
        
        first_half = model.objects.filter(created_at__range=[start_date, mid_date]).count()
        second_half = model.objects.filter(created_at__range=[mid_date, end_date]).count()
        
        if first_half == 0:
            return 100 if second_half > 0 else 0
        
        growth_rate = ((second_half - first_half) / first_half) * 100
        return round(growth_rate, 2)
    
    @staticmethod
    def calculate_retention_rate(model, days=7):
        """Calculate user retention rate"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        total_users = model.objects.filter(created_at__lt=cutoff_date).count()
        active_users = model.objects.filter(
            created_at__lt=cutoff_date,
            last_login__gte=cutoff_date
        ).count()
        
        if total_users == 0:
            return 0
        
        retention_rate = (active_users / total_users) * 100
        return round(retention_rate, 2)