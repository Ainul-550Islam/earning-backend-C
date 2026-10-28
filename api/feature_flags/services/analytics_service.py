"""
Analytics service for Feature Flags & A/B Testing.
"""
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db.models import Sum, Avg
from datetime import timedelta

from ..models.flag_analytics import FlagAnalytics
from ..models.feature_flag import FeatureFlag
from ..models.experiment import Experiment


class AnalyticsService:
    """
    Service for analytics operations.
    """
    
    def __init__(self):
        """Initialize the analytics service."""
        pass
    
    def get_flag_analytics(self, flag_name: str, days: int = 7) -> Dict[str, Any]:
        """
        Get analytics for a specific flag.
        
        Args:
            flag_name: Flag name
            days: Number of days to look back
            
        Returns:
            Dictionary with analytics data
        """
        since = timezone.now() - timedelta(days=days)
        
        try:
            flag = FeatureFlag.objects.get(name=flag_name)
        except FeatureFlag.DoesNotExist:
            return {'error': 'Flag not found'}
        
        analytics = FlagAnalytics.objects.filter(flag=flag, date__gte=since)
        
        total_evaluations = analytics.aggregate(total=Sum('evaluation_count'))['total'] or 0
        total_enabled = analytics.aggregate(total=Sum('enabled_count'))['total'] or 0
        total_unique_users = analytics.aggregate(total=Sum('unique_users'))['total'] or 0
        total_conversions = analytics.aggregate(total=Sum('conversion_count'))['total'] or 0
        
        return {
            'flag_name': flag_name,
            'period_days': days,
            'total_evaluations': total_evaluations,
            'total_enabled': total_enabled,
            'enable_rate': round((total_enabled / total_evaluations * 100) if total_evaluations > 0 else 0, 2),
            'total_unique_users': total_unique_users,
            'total_conversions': total_conversions,
            'conversion_rate': round((total_conversions / total_unique_users * 100) if total_unique_users > 0 else 0, 2)
        }
    
    def get_experiment_analytics(self, experiment_name: str) -> Dict[str, Any]:
        """
        Get analytics for an experiment.
        
        Args:
            experiment_name: Experiment name
            
        Returns:
            Dictionary with experiment analytics
        """
        try:
            experiment = Experiment.objects.get(name=experiment_name)
        except Experiment.DoesNotExist:
            return {'error': 'Experiment not found'}
        
        return {
            'experiment_name': experiment_name,
            'status': experiment.status,
            'participant_count': experiment.get_participant_count(),
            'variant_stats': experiment.get_variant_stats()
        }
    
    def get_daily_analytics(self, flag_name: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get daily analytics for a flag.
        
        Args:
            flag_name: Flag name
            days: Number of days to look back
            
        Returns:
            List of daily analytics
        """
        since = timezone.now() - timedelta(days=days)
        
        try:
            flag = FeatureFlag.objects.get(name=flag_name)
        except FeatureFlag.DoesNotExist:
            return []
        
        analytics = FlagAnalytics.objects.filter(flag=flag, date__gte=since).order_by('date')
        
        data = []
        
        for analytic in analytics:
            data.append({
                'date': analytic.date.isoformat(),
                'evaluation_count': analytic.evaluation_count,
                'enabled_count': analytic.enabled_count,
                'unique_users': analytic.unique_users,
                'conversion_count': analytic.conversion_count,
                'enable_rate': analytic.get_enable_rate(),
                'conversion_rate': analytic.get_conversion_rate()
            })
        
        return data
    
    def get_variant_comparison(self, experiment_name: str) -> Dict[str, Any]:
        """
        Get variant comparison for an experiment.
        
        Args:
            experiment_name: Experiment name
            
        Returns:
            Dictionary with variant comparison
        """
        try:
            experiment = Experiment.objects.get(name=experiment_name)
        except Experiment.DoesNotExist:
            return {'error': 'Experiment not found'}
        
        variant_stats = experiment.get_variant_stats()
        
        # Calculate statistical significance
        from ..utils import calculate_statistical_significance
        
        variants = list(variant_stats.keys())
        
        if len(variants) >= 2:
            control = variant_stats.get(variants[0], {})
            variant = variant_stats.get(variants[1], {})
            
            stats = calculate_statistical_significance(
                control.get('conversion_count', 0),
                control.get('participant_count', 1),
                variant.get('conversion_count', 0),
                variant.get('participant_count', 1)
            )
            
            return {
                'experiment_name': experiment_name,
                'variant_stats': variant_stats,
                'statistical_significance': stats
            }
        
        return {
            'experiment_name': experiment_name,
            'variant_stats': variant_stats
        }
