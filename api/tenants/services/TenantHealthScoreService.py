"""
Tenant Health Score Service

This module provides business logic for managing tenant health scores
including score calculation, monitoring, and reporting.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.utils import timezone
from django.db.models import Avg, Count, Sum
from ..models.analytics import TenantHealthScore, TenantMetric
from ..models.core import Tenant
from .base import BaseService


class TenantHealthScoreService(BaseService):
    """
    Service class for managing tenant health scores.
    
    Provides business logic for health score operations including:
    - Health score calculation and updates
    - Health trend analysis
    - Health alerts and notifications
    - Health reporting and analytics
    """
    
    @staticmethod
    def calculate_health_score(tenant, period='monthly'):
        """
        Calculate health score for a tenant.
        
        Args:
            tenant (Tenant): Tenant to calculate score for
            period (str): Period for calculation
            
        Returns:
            TenantHealthScore: Calculated health score
        """
        try:
            with transaction.atomic():
                # Get metrics for the period
                metrics = TenantHealthScoreService._get_tenant_metrics(tenant, period)
                
                # Calculate component scores
                component_scores = TenantHealthScoreService._calculate_component_scores(metrics)
                
                # Calculate overall score
                overall_score = TenantHealthScoreService._calculate_overall_score(component_scores)
                
                # Determine health grade
                health_grade = TenantHealthScoreService._determine_health_grade(overall_score)
                
                # Determine risk level
                risk_level = TenantHealthScoreService._determine_risk_level(overall_score)
                
                # Create or update health score
                health_score, created = TenantHealthScore.objects.update_or_create(
                    tenant=tenant,
                    period=period,
                    defaults={
                        'overall_score': overall_score,
                        'health_grade': health_grade,
                        'risk_level': risk_level,
                        'component_scores': component_scores,
                        'calculated_at': timezone.now(),
                        'metadata': {
                            'metrics_count': len(metrics),
                            'calculation_period': period
                        }
                    }
                )
                
                return health_score
                
        except Exception as e:
            raise ValidationError(f"Failed to calculate health score: {str(e)}")
    
    @staticmethod
    def get_health_score(tenant, period='monthly'):
        """
        Get health score for a tenant.
        
        Args:
            tenant (Tenant): Tenant to get score for
            period (str): Period for score
            
        Returns:
            TenantHealthScore or None: Health score if found
        """
        try:
            return TenantHealthScore.objects.get(tenant=tenant, period=period)
        except TenantHealthScore.DoesNotExist:
            return None
    
    @staticmethod
    def get_health_history(tenant, days=90):
        """
        Get health score history for a tenant.
        
        Args:
            tenant (Tenant): Tenant to get history for
            days (int): Number of days to look back
            
        Returns:
            QuerySet: Health score history
        """
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        return TenantHealthScore.objects.filter(
            tenant=tenant,
            calculated_at__gte=start_date
        ).order_by('calculated_at')
    
    @staticmethod
    def get_health_trends(tenant, days=30):
        """
        Get health score trends for a tenant.
        
        Args:
            tenant (Tenant): Tenant to get trends for
            days (int): Number of days to analyze
            
        Returns:
            dict: Health trend analysis
        """
        try:
            history = TenantHealthScoreService.get_health_history(tenant, days)
            
            if not history:
                return {
                    'trend': 'stable',
                    'change': 0,
                    'change_percentage': 0,
                    'data_points': 0,
                    'first_score': None,
                    'last_score': None,
                    'average_score': 0,
                    'highest_score': 0,
                    'lowest_score': 0
                }
            
            scores = list(history)
            
            if len(scores) < 2:
                return {
                    'trend': 'stable',
                    'change': 0,
                    'change_percentage': 0,
                    'data_points': len(scores),
                    'first_score': scores[0].overall_score,
                    'last_score': scores[0].overall_score,
                    'average_score': scores[0].overall_score,
                    'highest_score': scores[0].overall_score,
                    'lowest_score': scores[0].overall_score
                }
            
            first_score = scores[0].overall_score
            last_score = scores[-1].overall_score
            change = last_score - first_score
            change_percentage = (change / first_score * 100) if first_score > 0 else 0
            
            # Determine trend
            if change > 5:
                trend = 'improving'
            elif change < -5:
                trend = 'declining'
            else:
                trend = 'stable'
            
            # Calculate statistics
            score_values = [s.overall_score for s in scores]
            average_score = sum(score_values) / len(score_values)
            highest_score = max(score_values)
            lowest_score = min(score_values)
            
            return {
                'trend': trend,
                'change': change,
                'change_percentage': change_percentage,
                'data_points': len(scores),
                'first_score': first_score,
                'last_score': last_score,
                'average_score': average_score,
                'highest_score': highest_score,
                'lowest_score': lowest_score
            }
            
        except Exception as e:
            return {
                'trend': 'error',
                'error': str(e)
            }
    
    @staticmethod
    def get_health_alerts(tenant=None, risk_level='high'):
        """
        Get health alerts for tenants.
        
        Args:
            tenant (Tenant): Specific tenant (optional)
            risk_level (str): Minimum risk level to alert on
            
        Returns:
            list: Health alerts
        """
        alerts = []
        
        try:
            queryset = TenantHealthScore.objects.all()
            if tenant:
                queryset = queryset.filter(tenant=tenant)
            
            # Define risk level thresholds
            risk_thresholds = {
                'critical': 30,
                'high': 50,
                'medium': 70,
                'low': 85
            }
            
            threshold = risk_thresholds.get(risk_level, 50)
            
            for health_score in queryset:
                if health_score.overall_score <= threshold:
                    alerts.append({
                        'tenant': health_score.tenant,
                        'health_score': health_score,
                        'risk_level': health_score.risk_level,
                        'health_grade': health_score.health_grade,
                        'overall_score': health_score.overall_score,
                        'calculated_at': health_score.calculated_at,
                        'severity': health_score.risk_level
                    })
            
            return alerts
            
        except Exception as e:
            return []
    
    @staticmethod
    def get_health_summary(tenant=None):
        """
        Get health score summary.
        
        Args:
            tenant (Tenant): Specific tenant (optional)
            
        Returns:
            dict: Health summary
        """
        try:
            queryset = TenantHealthScore.objects.all()
            if tenant:
                queryset = queryset.filter(tenant=tenant)
            
            # Get latest scores for each tenant
            latest_scores = {}
            for score in queryset:
                if score.tenant.id not in latest_scores or score.calculated_at > latest_scores[score.tenant.id].calculated_at:
                    latest_scores[score.tenant.id] = score
            
            scores = list(latest_scores.values())
            
            if not scores:
                return {
                    'total_tenants': 0,
                    'average_score': 0,
                    'health_distribution': {},
                    'risk_distribution': {},
                    'grade_distribution': {}
                }
            
            # Calculate statistics
            total_tenants = len(scores)
            average_score = sum(s.overall_score for s in scores) / total_tenants
            
            # Health distribution
            health_ranges = {
                'excellent': (90, 100),
                'good': (75, 89),
                'fair': (60, 74),
                'poor': (40, 59),
                'critical': (0, 39)
            }
            
            health_distribution = {}
            for range_name, (min_score, max_score) in health_ranges.items():
                health_distribution[range_name] = len([
                    s for s in scores if min_score <= s.overall_score <= max_score
                ])
            
            # Risk distribution
            risk_levels = ['low', 'medium', 'high', 'critical']
            risk_distribution = {}
            for level in risk_levels:
                risk_distribution[level] = len([
                    s for s in scores if s.risk_level == level
                ])
            
            # Grade distribution
            grades = ['A+', 'A', 'B+', 'B', 'C+', 'C', 'D', 'F']
            grade_distribution = {}
            for grade in grades:
                grade_distribution[grade] = len([
                    s for s in scores if s.health_grade == grade
                ])
            
            return {
                'total_tenants': total_tenants,
                'average_score': round(average_score, 2),
                'health_distribution': health_distribution,
                'risk_distribution': risk_distribution,
                'grade_distribution': grade_distribution
            }
            
        except Exception as e:
            return {
                'error': str(e)
            }
    
    @staticmethod
    def calculate_all_health_scores(period='monthly'):
        """
        Calculate health scores for all tenants.
        
        Args:
            period (str): Period for calculation
            
        Returns:
            dict: Calculation results
        """
        results = {
            'total_tenants': 0,
            'calculated': 0,
            'failed': 0,
            'errors': []
        }
        
        tenants = Tenant.objects.filter(is_deleted=False, is_active=True)
        results['total_tenants'] = tenants.count()
        
        for tenant in tenants:
            try:
                TenantHealthScoreService.calculate_health_score(tenant, period)
                results['calculated'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Tenant {tenant.id}: {str(e)}")
        
        return results
    
    @staticmethod
    def get_health_recommendations(tenant):
        """
        Get health improvement recommendations for a tenant.
        
        Args:
            tenant (Tenant): Tenant to get recommendations for
            
        Returns:
            list: Health recommendations
        """
        recommendations = []
        
        try:
            health_score = TenantHealthScoreService.get_health_score(tenant)
            
            if not health_score:
                return ['No health score data available']
            
            component_scores = health_score.component_scores or {}
            
            # Analyze component scores and provide recommendations
            for component, score in component_scores.items():
                if score < 50:
                    if component == 'usage':
                        recommendations.append({
                            'category': 'Usage',
                            'priority': 'high',
                            'recommendation': 'Increase tenant usage to improve health score',
                            'score': score
                        })
                    elif component == 'engagement':
                        recommendations.append({
                            'category': 'Engagement',
                            'priority': 'high',
                            'recommendation': 'Improve user engagement through better features and support',
                            'score': score
                        })
                    elif component == 'performance':
                        recommendations.append({
                            'category': 'Performance',
                            'priority': 'high',
                            'recommendation': 'Optimize application performance and reduce response times',
                            'score': score
                        })
                    elif component == 'satisfaction':
                        recommendations.append({
                            'category': 'Satisfaction',
                            'priority': 'high',
                            'recommendation': 'Address user feedback and improve customer satisfaction',
                            'score': score
                        })
                elif score < 75:
                    if component == 'usage':
                        recommendations.append({
                            'category': 'Usage',
                            'priority': 'medium',
                            'recommendation': 'Consider implementing features to increase usage',
                            'score': score
                        })
                    elif component == 'engagement':
                        recommendations.append({
                            'category': 'Engagement',
                            'priority': 'medium',
                            'recommendation': 'Enhance user experience to improve engagement',
                            'score': score
                        })
            
            # Overall health recommendations
            if health_score.overall_score < 50:
                recommendations.append({
                    'category': 'Overall',
                    'priority': 'critical',
                    'recommendation': 'Tenant health is critical - immediate action required',
                    'score': health_score.overall_score
                })
            elif health_score.overall_score < 75:
                recommendations.append({
                    'category': 'Overall',
                    'priority': 'medium',
                    'recommendation': 'Tenant health needs improvement - focus on key areas',
                    'score': health_score.overall_score
                })
            
            return recommendations
            
        except Exception as e:
            return [f'Error generating recommendations: {str(e)}']
    
    @staticmethod
    def _get_tenant_metrics(tenant, period):
        """
        Get metrics for health score calculation.
        
        Args:
            tenant (Tenant): Tenant to get metrics for
            period (str): Period for metrics
            
        Returns:
            dict: Tenant metrics
        """
        from datetime import timedelta
        
        # Define period date ranges
        if period == 'daily':
            start_date = timezone.now() - timedelta(days=1)
        elif period == 'weekly':
            start_date = timezone.now() - timedelta(weeks=1)
        elif period == 'monthly':
            start_date = timezone.now() - timedelta(days=30)
        else:
            start_date = timezone.now() - timedelta(days=30)
        
        metrics = TenantMetric.objects.filter(
            tenant=tenant,
            date__gte=start_date.date()
        )
        
        # Group metrics by type
        metrics_data = {}
        for metric in metrics:
            if metric.metric_type not in metrics_data:
                metrics_data[metric.metric_type] = []
            metrics_data[metric.metric_type].append(metric.value)
        
        return metrics_data
    
    @staticmethod
    def _calculate_component_scores(metrics):
        """
        Calculate component scores from metrics.
        
        Args:
            metrics (dict): Tenant metrics
            
        Returns:
            dict: Component scores
        """
        component_scores = {}
        
        # Usage score (based on API calls, active users, etc.)
        usage_metrics = ['api_calls', 'active_users', 'sessions']
        usage_score = TenantHealthScoreService._calculate_usage_score(metrics, usage_metrics)
        component_scores['usage'] = usage_score
        
        # Engagement score (based on user interactions, feature usage)
        engagement_metrics = ['feature_usage', 'user_interactions', 'time_spent']
        engagement_score = TenantHealthScoreService._calculate_engagement_score(metrics, engagement_metrics)
        component_scores['engagement'] = engagement_score
        
        # Performance score (based on response times, error rates)
        performance_metrics = ['response_time', 'error_rate', 'uptime']
        performance_score = TenantHealthScoreService._calculate_performance_score(metrics, performance_metrics)
        component_scores['performance'] = performance_score
        
        # Satisfaction score (based on feedback, support tickets)
        satisfaction_metrics = ['user_satisfaction', 'support_tickets', 'churn_rate']
        satisfaction_score = TenantHealthScoreService._calculate_satisfaction_score(metrics, satisfaction_metrics)
        component_scores['satisfaction'] = satisfaction_score
        
        return component_scores
    
    @staticmethod
    def _calculate_usage_score(metrics, usage_metrics):
        """Calculate usage score from usage metrics."""
        scores = []
        
        for metric_type in usage_metrics:
            if metric_type in metrics and metrics[metric_type]:
                values = metrics[metric_type]
                avg_value = sum(values) / len(values)
                
                # Normalize to 0-100 scale (this would need proper calibration)
                if metric_type == 'api_calls':
                    # Assume 1000 calls per day is good
                    score = min(100, (avg_value / 1000) * 100)
                elif metric_type == 'active_users':
                    # Assume 10 active users is good
                    score = min(100, (avg_value / 10) * 100)
                else:
                    score = min(100, avg_value)
                
                scores.append(score)
        
        return sum(scores) / len(scores) if scores else 50
    
    @staticmethod
    def _calculate_engagement_score(metrics, engagement_metrics):
        """Calculate engagement score from engagement metrics."""
        scores = []
        
        for metric_type in engagement_metrics:
            if metric_type in metrics and metrics[metric_type]:
                values = metrics[metric_type]
                avg_value = sum(values) / len(values)
                
                # Normalize to 0-100 scale
                if metric_type == 'feature_usage':
                    score = min(100, (avg_value / 50) * 100)
                elif metric_type == 'time_spent':
                    # Assume 30 minutes per session is good
                    score = min(100, (avg_value / 30) * 100)
                else:
                    score = min(100, avg_value)
                
                scores.append(score)
        
        return sum(scores) / len(scores) if scores else 50
    
    @staticmethod
    def _calculate_performance_score(metrics, performance_metrics):
        """Calculate performance score from performance metrics."""
        scores = []
        
        for metric_type in performance_metrics:
            if metric_type in metrics and metrics[metric_type]:
                values = metrics[metric_type]
                avg_value = sum(values) / len(values)
                
                # Normalize to 0-100 scale
                if metric_type == 'response_time':
                    # Lower is better - assume 200ms is good
                    score = max(0, 100 - (avg_value / 200) * 100)
                elif metric_type == 'error_rate':
                    # Lower is better - assume 1% is good
                    score = max(0, 100 - (avg_value * 100))
                elif metric_type == 'uptime':
                    # Higher is better
                    score = min(100, avg_value)
                else:
                    score = min(100, avg_value)
                
                scores.append(score)
        
        return sum(scores) / len(scores) if scores else 50
    
    @staticmethod
    def _calculate_satisfaction_score(metrics, satisfaction_metrics):
        """Calculate satisfaction score from satisfaction metrics."""
        scores = []
        
        for metric_type in satisfaction_metrics:
            if metric_type in metrics and metrics[metric_type]:
                values = metrics[metric_type]
                avg_value = sum(values) / len(values)
                
                # Normalize to 0-100 scale
                if metric_type == 'user_satisfaction':
                    score = min(100, avg_value)
                elif metric_type == 'support_tickets':
                    # Lower is better - assume 5 tickets per month is good
                    score = max(0, 100 - (avg_value / 5) * 100)
                elif metric_type == 'churn_rate':
                    # Lower is better - assume 5% is good
                    score = max(0, 100 - (avg_value * 20))
                else:
                    score = min(100, avg_value)
                
                scores.append(score)
        
        return sum(scores) / len(scores) if scores else 50
    
    @staticmethod
    def _calculate_overall_score(component_scores):
        """Calculate overall health score from component scores."""
        if not component_scores:
            return 50
        
        # Weight components differently
        weights = {
            'usage': 0.25,
            'engagement': 0.25,
            'performance': 0.30,
            'satisfaction': 0.20
        }
        
        weighted_score = 0
        total_weight = 0
        
        for component, score in component_scores.items():
            weight = weights.get(component, 0.25)
            weighted_score += score * weight
            total_weight += weight
        
        return weighted_score / total_weight if total_weight > 0 else 50
    
    @staticmethod
    def _determine_health_grade(score):
        """Determine health grade from score."""
        if score >= 95:
            return 'A+'
        elif score >= 90:
            return 'A'
        elif score >= 85:
            return 'B+'
        elif score >= 80:
            return 'B'
        elif score >= 75:
            return 'C+'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
    
    @staticmethod
    def _determine_risk_level(score):
        """Determine risk level from score."""
        if score >= 80:
            return 'low'
        elif score >= 60:
            return 'medium'
        elif score >= 40:
            return 'high'
        else:
            return 'critical'
