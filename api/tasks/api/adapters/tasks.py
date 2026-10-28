"""
api/adapters/tasks.py
Tasks adapter for earning backend platform
"""
from django.db.models import Max
from django.db.models import Min
from django.db.models import Q
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
@permission_classes([IsAuthenticated])
def get_user_tasks(request):
    """Get user's tasks."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        status_filter = request.GET.get('status')  # 'all', 'available', 'in_progress', 'completed', 'expired'
        category = request.GET.get('category')
        difficulty = request.GET.get('difficulty')
        reward_min = request.GET.get('reward_min')
        reward_max = request.GET.get('reward_max')
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        sort_by = request.GET.get('sort_by', 'created_at')
        sort_order = request.GET.get('sort_order', 'desc')
        
        # Get tasks
        from api.tasks.models import MasterTask, UserTaskCompletion
        queryset = MasterTask.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        )
        
        # Apply filters
        if status_filter and status_filter != 'all':
            if status_filter == 'available':
                queryset = queryset.filter(
                    available_from__lte=timezone.now(),
                    available_until__gte=timezone.now()
                ).exclude(
                    id__in=UserTaskCompletion.objects.filter(
                        user=user,
                        status__in=['in_progress', 'completed']
                    ).values_list('task_id', flat=True)
                )
            elif status_filter == 'in_progress':
                queryset = queryset.filter(
                    id__in=UserTaskCompletion.objects.filter(
                        user=user,
                        status='in_progress'
                    ).values_list('task_id', flat=True)
                )
            elif status_filter == 'completed':
                queryset = queryset.filter(
                    id__in=UserTaskCompletion.objects.filter(
                        user=user,
                        status='completed'
                    ).values_list('task_id', flat=True)
                )
            elif status_filter == 'expired':
                queryset = queryset.filter(
                    available_until__lt=timezone.now()
                )
        
        if category:
            queryset = queryset.filter(category=category)
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)
        if reward_min:
            queryset = queryset.filter(reward_amount__gte=Decimal(reward_min))
        if reward_max:
            queryset = queryset.filter(reward_amount__lte=Decimal(reward_max))
        
        # Apply sorting
        if sort_by == 'reward':
            queryset = queryset.order_by(f'-{sort_by}' if sort_order == 'desc' else sort_by)
        elif sort_by == 'difficulty':
            queryset = queryset.order_by(f'-{sort_by}' if sort_order == 'desc' else sort_by)
        elif sort_by == 'created_at':
            queryset = queryset.order_by(f'-{sort_by}' if sort_order == 'desc' else sort_by)
        else:
            queryset = queryset.order_by('-created_at')
        
        # Paginate
        tasks = queryset[offset:offset+limit]
        
        # Serialize tasks
        task_data = []
        for task in tasks:
            # Get user's completion status
            user_completion = UserTaskCompletion.objects.filter(
                user=user,
                task=task
            ).first()
            
            task_data.append({
                'id': task.id,
                'task_id': task.task_id,
                'name': task.name,
                'description': task.description,
                'category': task.category,
                'difficulty': task.difficulty,
                'reward_amount': str(task.reward_amount),
                'reward_type': task.reward_type,
                'estimated_time_minutes': task.estimated_time_minutes,
                'available_from': task.available_from.isoformat(),
                'available_until': task.available_until.isoformat(),
                'is_featured': task.is_featured,
                'is_new': task.created_at >= timezone.now() - timedelta(days=3),
                'completion_count': task.completion_count,
                'success_rate': task.success_rate,
                'user_status': user_completion.status if user_completion else 'available',
                'user_progress': {
                    'started_at': user_completion.started_at.isoformat() if user_completion else None,
                    'completed_at': user_completion.completed_at.isoformat() if user_completion else None,
                    'time_spent_minutes': (user_completion.completed_at - user_completion.started_at).total_seconds() / 60 if user_completion and user_completion.started_at and user_completion.completed_at else None,
                    'reward_earned': str(user_completion.rewards_awarded) if user_completion and user_completion.rewards_awarded else '0.00',
                    'attempts': user_completion.attempts if user_completion else 0,
                },
                'requirements': task.requirements,
                'instructions': task.instructions,
                'tags': task.tags,
                'metadata': task.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'tasks': task_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(task_data) == limit
                },
                'filters': {
                    'status': status_filter,
                    'category': category,
                    'difficulty': difficulty,
                    'reward_min': reward_min,
                    'reward_max': reward_max,
                    'sort_by': sort_by,
                    'sort_order': sort_order
                },
                'summary': _get_tasks_summary(queryset, user, tenant_id)
            },
            'message': 'Tasks retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[TasksAdapter] Error getting user tasks: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve tasks',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_task_details(request, task_id):
    """Get detailed task information."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get task
        from api.tasks.models import MasterTask, UserTaskCompletion
        try:
            task = MasterTask.objects.get(
                id=task_id,
                tenant_id=tenant_id,
                is_active=True
            )
        except MasterTask.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Task not found',
                'details': f'Task with ID {task_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get user's completion status
        user_completion = UserTaskCompletion.objects.filter(
            user=user,
            task=task
        ).first()
        
        # Get similar tasks
        similar_tasks = MasterTask.objects.filter(
            tenant_id=tenant_id,
            category=task.category,
            is_active=True
        ).exclude(id=task.id).order_by('-completion_count')[:5]
        
        # Build detailed task data
        task_data = {
            'id': task.id,
            'task_id': task.task_id,
            'name': task.name,
            'description': task.description,
            'category': task.category,
            'difficulty': task.difficulty,
            'reward_amount': str(task.reward_amount),
            'reward_type': task.reward_type,
            'estimated_time_minutes': task.estimated_time_minutes,
            'available_from': task.available_from.isoformat(),
            'available_until': task.available_until.isoformat(),
            'is_featured': task.is_featured,
            'is_new': task.created_at >= timezone.now() - timedelta(days=3),
            'completion_count': task.completion_count,
            'success_rate': task.success_rate,
            'average_completion_time_minutes': task.average_completion_time_minutes,
            'requirements': task.requirements,
            'instructions': task.instructions,
            'proof_requirements': task.proof_requirements,
            'ui_config': task.ui_config,
            'metadata': task.metadata,
            'tags': task.tags,
            'user_status': user_completion.status if user_completion else 'available',
            'user_progress': {
                'started_at': user_completion.started_at.isoformat() if user_completion else None,
                'completed_at': user_completion.completed_at.isoformat() if user_completion else None,
                'time_spent_minutes': (user_completion.completed_at - user_completion.started_at).total_seconds() / 60 if user_completion and user_completion.started_at and user_completion.completed_at else None,
                'reward_earned': str(user_completion.rewards_awarded) if user_completion and user_completion.rewards_awarded else '0.00',
                'attempts': user_completion.attempts if user_completion else 0,
                'proof_submitted': user_completion.proof_submitted if user_completion else None,
                'proof_approved': user_completion.proof_approved if user_completion else None,
                'feedback': user_completion.feedback if user_completion else None,
            },
            'similar_tasks': [
                {
                    'id': similar.id,
                    'name': similar.name,
                    'reward_amount': str(similar.reward_amount),
                    'difficulty': similar.difficulty,
                    'completion_count': similar.completion_count
                }
                for similar in similar_tasks
            ],
            'can_start': _can_start_task(user, task, user_completion),
            'can_submit_proof': _can_submit_proof(user, task, user_completion),
            'time_remaining': _get_time_remaining(task),
            'recommendations': _get_task_recommendations(user, task, user_completion)
        }
        
        return Response({
            'success': True,
            'data': task_data,
            'message': 'Task details retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[TasksAdapter] Error getting task details: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve task details',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_task(request, task_id):
    """Start a task."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get task
        from api.tasks.models import MasterTask, UserTaskCompletion
        try:
            task = MasterTask.objects.get(
                id=task_id,
                tenant_id=tenant_id,
                is_active=True
            )
        except MasterTask.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Task not found',
                'details': f'Task with ID {task_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user can start task
        existing_completion = UserTaskCompletion.objects.filter(
            user=user,
            task=task
        ).first()
        
        if existing_completion and existing_completion.status in ['in_progress', 'completed']:
            return Response({
                'success': False,
                'error': 'Task already started',
                'details': f'Task is already {existing_completion.status}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if task is available
        if not _is_task_available(task):
            return Response({
                'success': False,
                'error': 'Task not available',
                'details': 'Task is not currently available'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check user requirements
        if not _meets_task_requirements(user, task):
            return Response({
                'success': False,
                'error': 'Requirements not met',
                'details': 'You do not meet the requirements for this task'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create or update completion record
        if existing_completion:
            existing_completion.status = 'in_progress'
            existing_completion.started_at = timezone.now()
            existing_completion.attempts += 1
            existing_completion.save()
            completion = existing_completion
        else:
            completion = UserTaskCompletion.objects.create(
                user=user,
                task=task,
                status='in_progress',
                started_at=timezone.now(),
                attempts=1,
                tenant_id=tenant_id,
                created_at=timezone.now()
            )
        
        # Update task statistics
        task.start_count += 1
        task.save()
        
        # Emit task started event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('tasks.task_started', {
            'user_id': user.id,
            'task_id': task_id,
            'completion_id': completion.id,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'completion_id': completion.id,
                'task_id': task_id,
                'status': 'in_progress',
                'started_at': completion.started_at.isoformat(),
                'estimated_completion_time': (completion.started_at + timedelta(minutes=task.estimated_time_minutes)).isoformat(),
                'instructions': task.instructions,
                'requirements': task.requirements,
                'proof_requirements': task.proof_requirements
            },
            'message': 'Task started successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[TasksAdapter] Error starting task: {e}")
        return Response({
            'success': False,
            'error': 'Failed to start task',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_task_proof(request, task_id):
    """Submit proof for task completion."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get task completion record
        from api.tasks.models import MasterTask, UserTaskCompletion
        try:
            completion = UserTaskCompletion.objects.get(
                user=user,
                task_id=task_id,
                status='in_progress'
            )
        except UserTaskCompletion.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Task not in progress',
                'details': 'Please start the task before submitting proof'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate proof data
        proof_data = data.get('proof_data')
        if not proof_data:
            return Response({
                'success': False,
                'error': 'Proof data required',
                'details': 'Please provide proof data for task completion'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate proof format
        task = completion.task
        if not _validate_proof_format(proof_data, task.proof_requirements):
            return Response({
                'success': False,
                'error': 'Invalid proof format',
                'details': 'Proof data does not match required format'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update completion record
        completion.proof_submitted = proof_data
        completion.proof_submitted_at = timezone.now()
        completion.status = 'pending_verification'
        completion.save()
        
        # Process proof verification
        verification_result = _verify_task_proof(completion, task)
        
        # Update based on verification
        if verification_result['approved']:
            completion.status = 'completed'
            completion.completed_at = timezone.now()
            completion.proof_approved = True
            completion.rewards_awarded = task.reward_amount
            completion.feedback = verification_result.get('feedback', 'Task completed successfully')
        else:
            completion.status = 'rejected'
            completion.proof_approved = False
            completion.feedback = verification_result.get('feedback', 'Proof verification failed')
        
        completion.save()
        
        # Update task statistics
        if verification_result['approved']:
            task.completion_count += 1
            task.last_completion_at = timezone.now()
            task.save()
        
        # Emit proof submitted event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('tasks.proof_submitted', {
            'user_id': user.id,
            'task_id': task_id,
            'completion_id': completion.id,
            'approved': verification_result['approved'],
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'completion_id': completion.id,
                'task_id': task_id,
                'status': completion.status,
                'proof_approved': verification_result['approved'],
                'feedback': completion.feedback,
                'reward_earned': str(completion.rewards_awarded) if verification_result['approved'] else '0.00',
                'completed_at': completion.completed_at.isoformat() if verification_result['approved'] else None,
                'verification_time_ms': verification_result.get('verification_time_ms', 0)
            },
            'message': 'Task proof submitted successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[TasksAdapter] Error submitting task proof: {e}")
        return Response({
            'success': False,
            'error': 'Failed to submit task proof',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_task_history(request):
    """Get user's task completion history."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        status_filter = request.GET.get('status')  # 'all', 'completed', 'rejected', 'expired'
        category = request.GET.get('category')
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get task completions
        from api.tasks.models import UserTaskCompletion
        queryset = UserTaskCompletion.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).select_related('task').order_by('-created_at')
        
        # Apply filters
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        if category:
            queryset = queryset.filter(task__category=category)
        
        # Paginate
        completions = queryset[offset:offset+limit]
        
        # Serialize completions
        completion_data = []
        for completion in completions:
            completion_data.append({
                'id': completion.id,
                'task': {
                    'id': completion.task.id,
                    'task_id': completion.task.task_id,
                    'name': completion.task.name,
                    'category': completion.task.category,
                    'difficulty': completion.task.difficulty,
                    'reward_amount': str(completion.task.reward_amount),
                    'reward_type': completion.task.reward_type,
                },
                'status': completion.status,
                'started_at': completion.started_at.isoformat(),
                'completed_at': completion.completed_at.isoformat() if completion.completed_at else None,
                'time_spent_minutes': (completion.completed_at - completion.started_at).total_seconds() / 60 if completion.started_at and completion.completed_at else None,
                'attempts': completion.attempts,
                'proof_submitted': completion.proof_submitted,
                'proof_submitted_at': completion.proof_submitted_at.isoformat() if completion.proof_submitted_at else None,
                'proof_approved': completion.proof_approved,
                'rewards_awarded': str(completion.rewards_awarded) if completion.rewards_awarded else '0.00',
                'feedback': completion.feedback,
                'created_at': completion.created_at.isoformat(),
                'metadata': completion.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'completions': completion_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(completion_data) == limit
                },
                'filters': {
                    'status': status_filter,
                    'category': category
                },
                'summary': _get_completion_summary(queryset)
            },
            'message': 'Task history retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[TasksAdapter] Error getting task history: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve task history',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_task_analytics(request):
    """Get task analytics for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get task analytics
        from api.tasks.models import MasterTask, UserTaskCompletion
        tasks = MasterTask.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        )
        
        completions = UserTaskCompletion.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).select_related('task', 'user')
        
        # Calculate analytics
        analytics_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'task_metrics': {
                'total_tasks': tasks.count(),
                'active_tasks': tasks.filter(is_active=True).count(),
                'featured_tasks': tasks.filter(is_featured=True).count(),
                'new_tasks': tasks.filter(
                    created_at__gte=timezone.now() - timedelta(days=7)
                ).count(),
                'category_distribution': list(tasks.values('category').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'difficulty_distribution': list(tasks.values('difficulty').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'reward_distribution': {
                    'total_rewards': tasks.aggregate(
                        total=Sum(F('reward_amount'))
                    )['total'] or Decimal('0'),
                    'average_reward': tasks.aggregate(
                        avg_reward=Avg(F('reward_amount'))
                    )['avg_reward'] or Decimal('0'),
                    'max_reward': tasks.aggregate(
                        max_reward=Max(F('reward_amount'))
                    )['max_reward'] or Decimal('0'),
                    'min_reward': tasks.aggregate(
                        min_reward=Min(F('reward_amount'))
                    )['min_reward'] or Decimal('0')
                },
                'performance': {
                    'average_completion_time': tasks.aggregate(
                        avg_time=Avg(F('average_completion_time_minutes'))
                    )['avg_time'] or 0,
                    'average_success_rate': tasks.aggregate(
                        avg_rate=Avg(F('success_rate'))
                    )['avg_rate'] or 0,
                    'total_completions': tasks.aggregate(
                        total=Sum(F('completion_count'))
                    )['total'] or 0
                }
            },
            'completion_metrics': {
                'total_completions': completions.filter(status='completed').count(),
                'pending_verifications': completions.filter(status='pending_verification').count(),
                'rejected_completions': completions.filter(status='rejected').count(),
                'total_rewards_earned': completions.filter(
                    status='completed'
                ).aggregate(
                    total=Sum(F('rewards_awarded'))
                )['total'] or Decimal('0'),
                'average_completion_time': completions.filter(
                    status='completed',
                    started_at__isnull=False,
                    completed_at__isnull=False
                ).annotate(
                    completion_time=ExpressionWrapper(
                        F('completed_at') - F('started_at'),
                        output_field=fields.DurationField()
                    )
                ).aggregate(
                    avg_time=Avg('completion_time')
                )['avg_time'].total_seconds() / 60 if completions.filter(status='completed').exists() else 0,
                'success_rate': round((completions.filter(status='completed').count() / max(completions.count(), 1)) * 100, 2),
                'daily_trends': _get_completion_trends(completions, days),
                'top_performers': _get_top_performers(completions, days),
                'most_completed_tasks': _get_most_completed_tasks(completions, days)
            },
            'user_engagement': {
                'unique_users': completions.values('user').distinct().count(),
                'active_users': completions.filter(
                    created_at__gte=timezone.now() - timedelta(days=7)
                ).values('user').distinct().count(),
                'average_tasks_per_user': completions.values('user').annotate(
                    task_count=Count('id')
                ).aggregate(
                    avg_tasks=Avg('task_count')
                )['avg_tasks'] or 0,
                'user_retention': _get_user_retention_metrics(completions, days)
            }
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'Task analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[TasksAdapter] Error getting task analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve task analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def _get_tasks_summary(queryset, user, tenant_id) -> Dict:
    """Get tasks summary statistics."""
    try:
        from api.tasks.models import UserTaskCompletion
        
        total_tasks = queryset.count()
        available_tasks = queryset.filter(
            available_from__lte=timezone.now(),
            available_until__gte=timezone.now()
        ).exclude(
            id__in=UserTaskCompletion.objects.filter(
                user=user,
                status__in=['in_progress', 'completed']
            ).values_list('task_id', flat=True)
        ).count()
        
        in_progress_tasks = UserTaskCompletion.objects.filter(
            user=user,
            status='in_progress'
        ).count()
        
        completed_tasks = UserTaskCompletion.objects.filter(
            user=user,
            status='completed'
        ).count()
        
        return {
            'total_tasks': total_tasks,
            'available_tasks': available_tasks,
            'in_progress_tasks': in_progress_tasks,
            'completed_tasks': completed_tasks,
            'completion_rate': round((completed_tasks / max(completed_tasks + in_progress_tasks, 1)) * 100, 2)
        }
    except Exception:
        return {}


def _can_start_task(user, task, user_completion) -> bool:
    """Check if user can start task."""
    try:
        # Check if already in progress or completed
        if user_completion and user_completion.status in ['in_progress', 'completed']:
            return False
        
        # Check if task is available
        if not _is_task_available(task):
            return False
        
        # Check if user meets requirements
        if not _meets_task_requirements(user, task):
            return False
        
        return True
    except Exception:
        return False


def _can_submit_proof(user, task, user_completion) -> bool:
    """Check if user can submit proof."""
    try:
        # Check if task is in progress
        if not user_completion or user_completion.status != 'in_progress':
            return False
        
        # Check if enough time has passed
        if task.estimated_time_minutes > 0:
            min_time = timedelta(minutes=max(1, task.estimated_time_minutes * 0.1))
            if timezone.now() - user_completion.started_at < min_time:
                return False
        
        return True
    except Exception:
        return False


def _is_task_available(task) -> bool:
    """Check if task is currently available."""
    try:
        now = timezone.now()
        return (
            task.is_active and
            task.available_from <= now and
            task.available_until >= now
        )
    except Exception:
        return False


def _meets_task_requirements(user, task) -> bool:
    """Check if user meets task requirements."""
    try:
        # Get user context
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        # Check user level requirement
        if task.requirements.get('min_user_level', 0) > ctx.user_level:
            return False
        
        # Check KYC requirement
        if task.requirements.get('kyc_required', False) and ctx.kyc_tier == 'none':
            return False
        
        # Check wallet balance requirement
        if task.requirements.get('min_wallet_balance', 0) > float(ctx.wallet_balance):
            return False
        
        # Check completion count requirement
        if task.requirements.get('min_completed_tasks', 0) > ctx.completed_tasks:
            return False
        
        return True
    except Exception:
        return False


def _get_time_remaining(task) -> Dict:
    """Get time remaining for task."""
    try:
        now = timezone.now()
        
        if task.available_until <= now:
            return {
                'is_expired': True,
                'time_remaining_seconds': 0,
                'time_remaining_text': 'Expired'
            }
        
        time_remaining = task.available_until - now
        days = time_remaining.days
        hours = time_remaining.seconds // 3600
        minutes = (time_remaining.seconds % 3600) // 60
        
        return {
            'is_expired': False,
            'time_remaining_seconds': time_remaining.total_seconds(),
            'time_remaining_text': f'{days}d {hours}h {minutes}m',
            'expires_at': task.available_until.isoformat()
        }
    except Exception:
        return {
            'is_expired': False,
            'time_remaining_seconds': 0,
            'time_remaining_text': 'Unknown'
        }


def _get_task_recommendations(user, task, user_completion) -> List[str]:
    """Get task recommendations."""
    recommendations = []
    
    if not user_completion:
        recommendations.append('Start this task to begin earning rewards')
    elif user_completion.status == 'in_progress':
        recommendations.extend([
            'Focus on completing task requirements',
            'Submit proof for verification',
            'Check task instructions carefully'
        ])
    elif user_completion.status == 'completed':
        recommendations.extend([
            'Try similar tasks for more rewards',
            'Explore tasks in same category',
            'Check featured tasks for bonuses'
        ])
    
    return recommendations


def _validate_proof_format(proof_data, proof_requirements) -> bool:
    """Validate proof format against requirements."""
    try:
        if not proof_requirements:
            return True
        
        # Check required fields
        required_fields = proof_requirements.get('required_fields', [])
        for field in required_fields:
            if field not in proof_data:
                return False
        
        # Check file types if required
        required_file_types = proof_requirements.get('file_types', [])
        if required_file_types:
            for file_field in required_file_types:
                if file_field not in proof_data:
                    return False
        
        return True
    except Exception:
        return False


def _verify_task_proof(completion, task) -> Dict:
    """Verify task proof automatically."""
    try:
        import random
        
        # Simulate proof verification
        # In real implementation, this would use AI/ML models or manual review
        
        # Simulate verification time
        verification_time_ms = random.randint(500, 2000)
        
        # Simulate approval rate based on task difficulty
        approval_rates = {
            'easy': 0.95,
            'medium': 0.85,
            'hard': 0.75,
            'expert': 0.65
        }
        
        approval_rate = approval_rates.get(task.difficulty, 0.8)
        approved = random.random() < approval_rate
        
        if approved:
            return {
                'approved': True,
                'feedback': 'Task completed successfully',
                'verification_time_ms': verification_time_ms
            }
        else:
            feedback_options = [
                'Proof does not meet requirements',
                'Image quality is too low',
                'Required information missing',
                'Proof appears to be manipulated'
            ]
            
            return {
                'approved': False,
                'feedback': random.choice(feedback_options),
                'verification_time_ms': verification_time_ms
            }
    except Exception:
        return {
            'approved': False,
            'feedback': 'Verification error occurred',
            'verification_time_ms': 0
        }


def _get_completion_summary(queryset) -> Dict:
    """Get completion summary statistics."""
    try:
        total_completions = queryset.count()
        completed = queryset.filter(status='completed').count()
        rejected = queryset.filter(status='rejected').count()
        pending = queryset.filter(status='pending_verification').count()
        
        total_rewards = queryset.filter(
            status='completed'
        ).aggregate(
            total=Sum(F('rewards_awarded'))
        )['total'] or Decimal('0')
        
        return {
            'total_completions': total_completions,
            'completed': completed,
            'rejected': rejected,
            'pending': pending,
            'success_rate': round((completed / max(total_completions, 1)) * 100, 2),
            'total_rewards_earned': str(total_rewards),
            'average_rewards_per_completion': str(total_rewards / max(completed, 1))
        }
    except Exception:
        return {}


def _get_completion_trends(completions, days) -> List[Dict]:
    """Get completion trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = completions.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
            rejected=Count('id', filter=Q(status='rejected'))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'total_completions': trend['total'],
                'completed': trend['completed'],
                'rejected': trend['rejected'],
                'success_rate': round((trend['completed'] / max(trend['total'], 1)) * 100, 2)
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _get_top_performers(completions, days) -> List[Dict]:
    """Get top performing users."""
    try:
        top_users = completions.filter(
            status='completed'
        ).values(
            'user__username',
            'user__first_name',
            'user__last_name'
        ).annotate(
            completion_count=Count('id'),
            total_rewards=Sum(F('rewards_awarded'))
        ).order_by('-total_rewards')[:10]
        
        return [
            {
                'username': user['user__username'],
                'name': f"{user['user__first_name']} {user['user__last_name']}".strip(),
                'completion_count': user['completion_count'],
                'total_rewards': str(user['total_rewards'])
            }
            for user in top_users
        ]
    except Exception:
        return []


def _get_most_completed_tasks(completions, days) -> List[Dict]:
    """Get most completed tasks."""
    try:
        top_tasks = completions.filter(
            status='completed'
        ).values(
            'task__name',
            'task__category',
            'task__difficulty'
        ).annotate(
            completion_count=Count('id')
        ).order_by('-completion_count')[:10]
        
        return [
            {
                'task_name': task['task__name'],
                'category': task['task__category'],
                'difficulty': task['task__difficulty'],
                'completion_count': task['completion_count']
            }
            for task in top_tasks
        ]
    except Exception:
        return []


def _get_user_retention_metrics(completions, days) -> Dict:
    """Get user retention metrics."""
    try:
        from django.utils import timezone
        from datetime import timedelta
        
        # Get users who completed tasks in the period
        period_users = completions.filter(
            created_at__gte=timezone.now() - timedelta(days=days)
        ).values('user').distinct().count()
        
        # Get users who completed tasks in the last 7 days
        recent_users = completions.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).values('user').distinct().count()
        
        # Calculate retention rate
        retention_rate = round((recent_users / max(period_users, 1)) * 100, 2)
        
        return {
            'total_active_users': period_users,
            'recent_active_users': recent_users,
            'retention_rate': retention_rate,
            'retention_trend': 'stable' if retention_rate >= 70 else 'declining'
        }
    except Exception:
        return {}
