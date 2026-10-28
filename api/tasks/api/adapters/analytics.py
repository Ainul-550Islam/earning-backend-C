"""
api/adapters/analytics.py
Analytics adapter for earning backend platform
"""
from django.db.models import Max
from django.db.models import Min
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_analytics(request):
    """Get user analytics and performance metrics."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range from request
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get user task completions
        from api.tasks.models import UserTaskCompletion
        completions = UserTaskCompletion.objects.filter(
            user=user,
            completed_at__gte=start_date,
            tenant_id=tenant_id
        )
        
        # Calculate analytics metrics
        total_completions = completions.count()
        total_revenue = completions.aggregate(
            total_revenue=Sum(F('rewards_awarded__amount'))
        )['total_revenue'] or Decimal('0')
        
        # Daily breakdown
        daily_stats = completions.extra({
            'day': fields.DateField('completed_at')
        }).values('day').annotate(
            completions=Count('id'),
            revenue=Sum(F('rewards_awarded__amount'))
        ).order_by('day')
        
        # Task performance
        task_performance = completions.values('task__name', 'task__category').annotate(
            completions=Count('id'),
            avg_completion_time=Avg(F('completed_at') - F('started_at')),
            total_revenue=Sum(F('rewards_awarded__amount'))
        ).order_by('-completions')[:10]
        
        analytics_data = {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'summary': {
                'total_completions': total_completions,
                'total_revenue': str(total_revenue),
                'avg_daily_completions': round(total_completions / days, 2),
                'avg_daily_revenue': str(total_revenue / Decimal(days)),
                'completion_rate': round((total_completions / max(completions.count(), 1)) * 100, 2)
            },
            'daily_breakdown': list(daily_stats),
            'top_tasks': list(task_performance),
            'engagement': {
                'active_days': completions.dates('completed_at').count(),
                'streak': _calculate_user_streak(user),
                'first_completion': completions.order_by('completed_at').first().completed_at.isoformat() if completions.exists() else None,
                'last_completion': completions.order_by('-completed_at').first().completed_at.isoformat() if completions.exists() else None,
            }
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'User analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AnalyticsAdapter] Error getting user analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve user analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def revenue_analytics(request):
    """Get revenue analytics and breakdown."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get revenue data
        from api.tasks.models import UserTaskCompletion, AdminLedger
        user_revenue = UserTaskCompletion.objects.filter(
            user=user,
            completed_at__gte=start_date,
            tenant_id=tenant_id
        ).aggregate(
            total_revenue=Sum(F('rewards_awarded__amount')),
            avg_revenue=Avg(F('rewards_awarded__amount')),
            max_revenue=Max(F('rewards_awarded__amount')),
            min_revenue=Min(F('rewards_awarded__amount'))
        )
        
        admin_revenue = AdminLedger.objects.filter(
            user=user,
            created_at__gte=start_date,
            tenant_id=tenant_id
        ).aggregate(
            total_admin_revenue=Sum(F('amount')),
            admin_transactions=Count('id')
        )
        
        # Revenue breakdown by source
        revenue_by_source = UserTaskCompletion.objects.filter(
            user=user,
            completed_at__gte=start_date,
            tenant_id=tenant_id
        ).values('task__category').annotate(
            revenue=Sum(F('rewards_awarded__amount')),
            count=Count('id')
        ).order_by('-revenue')
        
        revenue_data = {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'user_revenue': {
                'total': str(user_revenue['total_revenue'] or Decimal('0')),
                'average': str(user_revenue['avg_revenue'] or Decimal('0')),
                'maximum': str(user_revenue['max_revenue'] or Decimal('0')),
                'minimum': str(user_revenue['min_revenue'] or Decimal('0')),
                'transactions': UserTaskCompletion.objects.filter(user=user, completed_at__gte=start_date).count()
            },
            'admin_revenue': {
                'total': str(admin_revenue['total_admin_revenue'] or Decimal('0')),
                'transactions': admin_revenue['admin_transactions'] or 0
            },
            'revenue_by_source': list(revenue_by_source),
            'trends': _calculate_revenue_trends(user, days)
        }
        
        return Response({
            'success': True,
            'data': revenue_data,
            'message': 'Revenue analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AnalyticsAdapter] Error getting revenue analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve revenue analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def platform_analytics(request):
    """Get platform-wide analytics (admin only)."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get platform metrics
        from api.tasks.models import MasterTask, UserTaskCompletion, AdminLedger
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        total_users = User.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).count()
        
        total_tasks = MasterTask.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).count()
        
        total_completions = UserTaskCompletion.objects.filter(
            completed_at__gte=start_date,
            tenant_id=tenant_id
        ).count()
        
        platform_revenue = AdminLedger.objects.filter(
            created_at__gte=start_date,
            tenant_id=tenant_id
        ).aggregate(
            total_revenue=Sum(F('amount')),
            total_transactions=Count('id')
        )
        
        # User engagement metrics
        active_users = UserTaskCompletion.objects.filter(
            completed_at__gte=timezone.now() - timedelta(days=7),
            tenant_id=tenant_id
        ).values('user').distinct().count()
        
        # Task performance metrics
        task_performance = MasterTask.objects.filter(
            tenant_id=tenant_id
        ).annotate(
            completions=Count('usertaskcompletion'),
            total_revenue=Sum(F('usertaskcompletion__rewards_awarded__amount'))
        ).order_by('-completions')[:10]
        
        analytics_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'user_metrics': {
                'total_users': total_users,
                'active_users': active_users,
                'new_users': User.objects.filter(
                    date_joined__gte=start_date,
                    tenant_id=tenant_id
                ).count(),
                'user_growth_rate': round((User.objects.filter(
                    date_joined__gte=start_date,
                    tenant_id=tenant_id
                ).count() / max(total_users, 1)) * 100, 2)
            },
            'task_metrics': {
                'total_tasks': total_tasks,
                'total_completions': total_completions,
                'completion_rate': round((total_completions / max(total_tasks, 1)) * 100, 2),
                'avg_completions_per_user': round(total_completions / max(total_users, 1), 2)
            },
            'revenue_metrics': {
                'total_revenue': str(platform_revenue['total_revenue'] or Decimal('0')),
                'total_transactions': platform_revenue['total_transactions'] or 0,
                'avg_transaction_value': str(
                    (platform_revenue['total_revenue'] or Decimal('0')) / 
                    max(platform_revenue['total_transactions'] or 1, Decimal('1'))
                ),
                'revenue_per_user': str(
                    (platform_revenue['total_revenue'] or Decimal('0')) / 
                    max(total_users, 1)
                )
            },
            'top_tasks': list(task_performance),
            'engagement': {
                'daily_active_users': active_users,
                'retention_rate': round((active_users / max(total_users, 1)) * 100, 2),
                'avg_tasks_per_user': round(total_completions / max(total_users, 1), 2)
            }
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'Platform analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AnalyticsAdapter] Error getting platform analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve platform analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def real_time_analytics(request):
    """Get real-time analytics data."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get real-time data from cache
        cache_key = f"real_time_analytics_{tenant_id}_{user.id}"
        real_time_data = cache.get(cache_key, {})
        
        # If not in cache, calculate and cache
        if not real_time_data:
            real_time_data = {
                'current_streak': _calculate_user_streak(user),
                'today_earnings': _get_today_earnings(user),
                'active_tasks': _get_active_tasks(user),
                'recent_activity': _get_recent_activity(user),
                'performance_metrics': _get_performance_metrics(user),
                'alerts': _get_user_alerts(user),
                'last_updated': timezone.now().isoformat()
            }
            
            # Cache for 5 minutes
            cache.set(cache_key, real_time_data, timeout=300)
        
        return Response({
            'success': True,
            'data': real_time_data,
            'message': 'Real-time analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AnalyticsAdapter] Error getting real-time analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve real-time analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _calculate_user_streak(user) -> int:
    """Calculate user's current completion streak."""
    try:
        from api.tasks.models import UserTaskCompletion
        recent_completions = UserTaskCompletion.objects.filter(
            user=user,
            status='completed',
            completed_at__gte=timezone.now() - timedelta(days=30)
        ).order_by('-completed_at')
        
        streak = 0
        current_date = timezone.now().date()
        
        for completion in recent_completions:
            if completion.completed_at.date() == current_date - timedelta(days=streak):
                streak += 1
            elif completion.completed_at.date() == current_date - timedelta(days=streak + 1):
                streak += 1
            else:
                break
            current_date = completion.completed_at.date()
        
        return streak
        
    except Exception:
        return 0


def _get_today_earnings(user) -> Decimal:
    """Get today's earnings for user."""
    try:
        from api.tasks.models import UserTaskCompletion
        today = timezone.now().date()
        
        today_earnings = UserTaskCompletion.objects.filter(
            user=user,
            completed_at__date=today,
            status='completed'
        ).aggregate(
            total=Sum(F('rewards_awarded__amount'))
        )['total'] or Decimal('0')
        
        return today_earnings
        
    except Exception:
        return Decimal('0')


def _get_active_tasks(user) -> List[Dict]:
    """Get user's active tasks."""
    try:
        from api.tasks.models import MasterTask, UserTaskCompletion
        from django.utils import timezone
        
        # Get tasks user has started but not completed
        active_tasks = UserTaskCompletion.objects.filter(
            user=user,
            status='started'
        ).values_list('task_id', flat=True)
        
        # Get task details
        tasks = MasterTask.objects.filter(
            task_id__in=active_tasks,
            is_active=True,
            available_from__lte=timezone.now(),
            available_until__gte=timezone.now()
        ).values('task_id', 'name', 'description', 'rewards')
        
        return list(tasks)
        
    except Exception:
        return []


def _get_recent_activity(user) -> List[Dict]:
    """Get user's recent activity."""
    try:
        from api.tasks.models import UserTaskCompletion
        from django.utils import timezone
        
        recent_activity = UserTaskCompletion.objects.filter(
            user=user,
            completed_at__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-completed_at')[:10].values(
            'task__name',
            'status',
            'completed_at',
            'rewards_awarded'
        )
        
        return list(recent_activity)
        
    except Exception:
        return []


def _get_performance_metrics(user) -> Dict:
    """Get user's performance metrics."""
    try:
        from api.tasks.models import UserTaskCompletion
        from django.utils import timezone
        from decimal import Decimal
        
        # Last 30 days performance
        thirty_days_ago = timezone.now() - timedelta(days=30)
        performance = UserTaskCompletion.objects.filter(
            user=user,
            completed_at__gte=thirty_days_ago,
            status='completed'
        ).aggregate(
            total_completions=Count('id'),
            avg_completion_time=Avg(F('completed_at') - F('started_at')),
            total_revenue=Sum(F('rewards_awarded__amount'))
        )
        
        return {
            'completions_last_30_days': performance['total_completions'] or 0,
            'avg_completion_time_minutes': performance['avg_completion_time'].total_seconds() / 60 if performance['avg_completion_time'] else 0,
            'total_revenue_last_30_days': str(performance['total_revenue'] or Decimal('0')),
            'avg_revenue_per_completion': str(
                (performance['total_revenue'] or Decimal('0')) / 
                max(performance['total_completions'] or 1, Decimal('1'))
            )
        }
        
    except Exception:
        return {}


def _get_user_alerts(user) -> List[Dict]:
    """Get user's alerts and notifications."""
    try:
        alerts = []
        
        # Check for fraud alerts
        fraud_score = cache.get(f'fraud_score_{user.id}', 0)
        if fraud_score >= 60:
            alerts.append({
                'type': 'fraud',
                'level': 'high',
                'message': 'High fraud score detected',
                'timestamp': timezone.now().isoformat()
            })
        
        # Check for withdrawal alerts
        pending_withdrawals = cache.get(f'pending_withdrawals_{user.id}', 0)
        if pending_withdrawals > 0:
            alerts.append({
                'type': 'withdrawal',
                'level': 'info',
                'message': f'{pending_withdrawals} pending withdrawals',
                'timestamp': timezone.now().isoformat()
            })
        
        return alerts
        
    except Exception:
        return []


def _calculate_revenue_trends(user, days) -> Dict:
    """Calculate revenue trends for user."""
    try:
        from api.tasks.models import UserTaskCompletion
        from django.utils import timezone
        from django.db.models import Sum
        from decimal import Decimal
        
        # Get daily revenue data
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        daily_revenue = UserTaskCompletion.objects.filter(
            user=user,
            completed_at__date__range=[start_date, end_date],
            status='completed'
        ).extra({
            'day': 'date(completed_at)'
        }).values('day').annotate(
            revenue=Sum(F('rewards_awarded__amount'))
        ).order_by('day')
        
        # Calculate trends
        revenues = [float(dr['revenue'] or 0) for dr in daily_revenue]
        
        if len(revenues) < 2:
            return {'trend': 'insufficient_data'}
        
        # Simple trend calculation
        if len(revenues) >= 7:
            recent_avg = sum(revenues[-7:]) / 7
            earlier_avg = sum(revenues[-14:-7]) / 7 if len(revenues) >= 14 else sum(revenues[:-7]) / len(revenues[:-7])
            trend = 'increasing' if recent_avg > earlier_avg else 'decreasing'
        else:
            trend = 'insufficient_data'
        
        return {
            'trend': trend,
            'daily_data': list(daily_revenue),
            'average_daily_revenue': str(Decimal(sum(revenues) / len(revenues))),
            'peak_daily_revenue': str(Decimal(max(revenues))),
            'lowest_daily_revenue': str(Decimal(min(revenues)))
        }
        
    except Exception:
        return {'trend': 'error'}
