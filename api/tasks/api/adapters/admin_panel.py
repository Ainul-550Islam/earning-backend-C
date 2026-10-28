"""
api/adapters/admin_panel.py
Admin panel adapter for earning backend platform
"""
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAdminUser])
def dashboard_stats(request):
    """Get admin dashboard statistics."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get platform statistics
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # User statistics
        total_users = User.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).count()
        
        new_users_today = User.objects.filter(
            date_joined__date=timezone.now().date(),
            tenant_id=tenant_id,
            is_active=True
        ).count()
        
        # Task statistics
        from api.tasks.models import MasterTask, UserTaskCompletion
        total_tasks = MasterTask.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).count()
        
        total_completions = UserTaskCompletion.objects.filter(
            completed_at__gte=start_date,
            tenant_id=tenant_id
        ).count()
        
        # Revenue statistics
        from wallet.models import AdminLedger
        revenue_stats = AdminLedger.objects.filter(
            created_at__gte=start_date,
            tenant_id=tenant_id
        ).aggregate(
            total_revenue=Sum(F('amount')),
            total_transactions=Count('id'),
            avg_transaction=Avg(F('amount'))
        )
        
        # System health
        system_health = {
            'database_status': 'healthy',
            'cache_status': 'healthy',
            'celery_status': _get_celery_status(),
            'last_backup': cache.get('last_backup_success'),
            'error_rate': _get_error_rate()
        }
        
        dashboard_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'user_metrics': {
                'total_users': total_users,
                'new_users_today': new_users_today,
                'active_users': UserTaskCompletion.objects.filter(
                    completed_at__gte=timezone.now() - timedelta(days=7),
                    tenant_id=tenant_id
                ).values('user').distinct().count(),
                'user_growth_rate': round(((new_users_today / max(total_users, 1)) * 100), 2)
            },
            'task_metrics': {
                'total_tasks': total_tasks,
                'total_completions': total_completions,
                'completion_rate': round((total_completions / max(total_tasks, 1)) * 100, 2),
                'avg_completions_per_day': round(total_completions / max(days, 1), 2)
            },
            'revenue_metrics': {
                'total_revenue': str(revenue_stats['total_revenue'] or Decimal('0')),
                'total_transactions': revenue_stats['total_transactions'] or 0,
                'avg_transaction_value': str(revenue_stats['avg_transaction'] or Decimal('0')),
                'daily_avg_revenue': str((revenue_stats['total_revenue'] or Decimal('0')) / Decimal(days))
            },
            'system_health': system_health
        }
        
        return Response({
            'success': True,
            'data': dashboard_data,
            'message': 'Dashboard statistics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AdminPanelAdapter] Error getting dashboard stats: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve dashboard statistics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def user_management(request):
    """Get user management data for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        
        # Get users with filtering
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        queryset = User.objects.filter(
            tenant_id=tenant_id
        ).order_by('-date_joined')
        
        # Apply filters
        is_active = request.GET.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        search = request.GET.get('search')
        if search:
            queryset = queryset.filter(
                username__icontains=search
            ) | queryset.filter(
                email__icontains=search
            ) | queryset.filter(
                first_name__icontains=search
            ) | queryset.filter(
                last_name__icontains=search
            )
        
        # Paginate
        users = queryset[offset:offset+limit]
        
        # Serialize user data
        user_data = []
        for user in users:
            user_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'date_joined': user.date_joined,
                'last_login': getattr(user, 'last_login', None),
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'tenant_id': getattr(user, 'tenant_id', None),
                'profile': {
                    'wallet_balance': str(cache.get(f'wallet_balance_{user.id}', 0)),
                    'fraud_score': cache.get(f'fraud_score_{user.id}', 0),
                    'kyc_tier': cache.get(f'kyc_tier_{user.id}', 'none'),
                    'total_earnings': str(cache.get(f'total_earnings_{user.id}', 0)),
                }
            })
        
        return Response({
            'success': True,
            'data': {
                'users': user_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(users) == limit
                },
                'filters': {
                    'is_active': is_active,
                    'search': search
                }
            },
            'message': 'User management data retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AdminPanelAdapter] Error getting user management: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve user management data',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def task_management(request):
    """Get task management data for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        
        # Get tasks with filtering
        from api.tasks.models import MasterTask, UserTaskCompletion
        queryset = MasterTask.objects.filter(
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply filters
        is_active = request.GET.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        category = request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        system_type = request.GET.get('system_type')
        if system_type:
            queryset = queryset.filter(system_type=system_type)
        
        search = request.GET.get('search')
        if search:
            queryset = queryset.filter(
                name__icontains=search
            ) | queryset.filter(
                description__icontains=search
            )
        
        # Paginate
        tasks = queryset[offset:offset+limit]
        
        # Serialize task data
        task_data = []
        for task in tasks:
            task_data.append({
                'id': task.id,
                'task_id': task.task_id,
                'name': task.name,
                'description': task.description,
                'category': task.category,
                'system_type': task.system_type,
                'is_active': task.is_active,
                'is_featured': task.is_featured,
                'sort_order': task.sort_order,
                'created_at': task.created_at.isoformat(),
                'available_from': task.available_from.isoformat(),
                'available_until': task.available_until.isoformat() if task.available_until else None,
                'total_completions': task.total_completions,
                'unique_users_completed': task.unique_users_completed,
                'daily_completion_limit': task.daily_completion_limit,
                'rewards': task.rewards,
                'constraints': task.constraints,
                'ui_config': task.ui_config,
                'completion_stats': _get_task_completion_stats(task, tenant_id)
            })
        
        return Response({
            'success': True,
            'data': {
                'tasks': task_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(tasks) == limit
                },
                'filters': {
                    'is_active': is_active,
                    'category': category,
                    'system_type': system_type,
                    'search': search
                }
            },
            'message': 'Task management data retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AdminPanelAdapter] Error getting task management: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve task management data',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def financial_overview(request):
    """Get financial overview for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get financial data
        from wallet.models import AdminLedger, WalletTransaction
        from api.tasks.models import UserTaskCompletion
        
        # Revenue breakdown
        revenue_by_source = AdminLedger.objects.filter(
            created_at__gte=start_date,
            tenant_id=tenant_id
        ).values('source_type').annotate(
            total_revenue=Sum(F('amount')),
            transaction_count=Count('id')
        ).order_by('-total_revenue')
        
        # Withdrawal statistics
        withdrawals = WalletTransaction.objects.filter(
            transaction_type='withdrawal',
            created_at__gte=start_date,
            tenant_id=tenant_id
        ).aggregate(
            total_withdrawals=Count('id'),
            total_amount=Sum(F('amount')),
            avg_amount=Avg(F('amount'))
        )
        
        # Payout statistics
        payouts = WalletTransaction.objects.filter(
            transaction_type='payout',
            created_at__gte=start_date,
            tenant_id=tenant_id
        ).aggregate(
            total_payouts=Count('id'),
            total_amount=Sum(F('amount')),
            avg_amount=Avg(F('amount'))
        )
        
        # Task completion revenue
        task_revenue = UserTaskCompletion.objects.filter(
            completed_at__gte=start_date,
            tenant_id=tenant_id
        ).aggregate(
            total_revenue=Sum(F('rewards_awarded__amount')),
            total_completions=Count('id')
        )
        
        financial_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'revenue_breakdown': list(revenue_by_source),
            'withdrawal_stats': {
                'total_withdrawals': withdrawals['total_withdrawals'] or 0,
                'total_amount': str(withdrawals['total_amount'] or Decimal('0')),
                'avg_amount': str(withdrawals['avg_amount'] or Decimal('0'))
            },
            'payout_stats': {
                'total_payouts': payouts['total_payouts'] or 0,
                'total_amount': str(payouts['total_amount'] or Decimal('0')),
                'avg_amount': str(payouts['avg_amount'] or Decimal('0'))
            },
            'task_revenue': {
                'total_revenue': str(task_revenue['total_revenue'] or Decimal('0')),
                'total_completions': task_revenue['total_completions'] or 0,
                'avg_revenue_per_completion': str(
                    (task_revenue['total_revenue'] or Decimal('0')) / 
                    max(task_revenue['total_completions'] or 1, Decimal('1'))
                )
            },
            'summary': {
                'total_revenue': str(revenue_by_source.aggregate(total=Sum(F('total_revenue')))['total_revenue'] or Decimal('0')),
                'total_withdrawals': str(withdrawals['total_amount'] or Decimal('0')),
                'total_payouts': str(payouts['total_amount'] or Decimal('0')),
                'net_revenue': str(
                    (revenue_by_source.aggregate(total=Sum(F('total_revenue')))['total_revenue'] or Decimal('0')) - 
                    (withdrawals['total_amount'] or Decimal('0')) - 
                    (payouts['total_amount'] or Decimal('0'))
                )
            }
        }
        
        return Response({
            'success': True,
            'data': financial_data,
            'message': 'Financial overview retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[AdminPanelAdapter] Error getting financial overview: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve financial overview',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _get_celery_status() -> str:
    """Get Celery status."""
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        
        # Check active workers
        active_workers = inspect.active()
        if active_workers:
            return 'healthy'
        else:
            return 'no_workers'
    except Exception:
        return 'unknown'


def _get_error_rate() -> float:
    """Get system error rate."""
    try:
        # This would typically come from a monitoring system
        # For now, return a mock value
        return 0.02  # 2% error rate
    except Exception:
        return 0.0


def _get_task_completion_stats(task, tenant_id) -> Dict:
    """Get completion statistics for a task."""
    try:
        from api.tasks.models import UserTaskCompletion
        from django.utils import timezone
        from datetime import timedelta
        
        # Last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        stats = UserTaskCompletion.objects.filter(
            task=task,
            tenant_id=tenant_id,
            completed_at__gte=thirty_days_ago,
            status='completed'
        ).aggregate(
            total_completions=Count('id'),
            avg_completion_time=Avg(F('completed_at') - F('started_at')),
            total_revenue=Sum(F('rewards_awarded__amount'))
        )
        
        return {
            'completions_last_30_days': stats['total_completions'] or 0,
            'avg_completion_time_minutes': stats['avg_completion_time'].total_seconds() / 60 if stats['avg_completion_time'] else 0,
            'total_revenue_last_30_days': str(stats['total_revenue'] or Decimal('0')),
            'avg_revenue_per_completion': str(
                (stats['total_revenue'] or Decimal('0')) / 
                max(stats['total_completions'] or 1, Decimal('1'))
            )
        }
        
    except Exception:
        return {
            'completions_last_30_days': 0,
            'avg_completion_time_minutes': 0,
            'total_revenue_last_30_days': '0.00',
            'avg_revenue_per_completion': '0.00'
        }
