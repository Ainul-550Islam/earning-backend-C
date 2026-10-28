"""
api/adapters/engagement.py
Engagement adapter for earning backend platform
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
@permission_classes([IsAuthenticated])
def get_engagement_metrics(request):
    """Get user's engagement metrics."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        period = request.GET.get('period', '30')  # '7', '30', '90', '365'
        
        # Get user engagement data
        from api.tasks.models import UserTaskCompletion
        from django.utils import timezone
        from datetime import timedelta
        
        # Calculate date range
        if period == '7':
            start_date = timezone.now() - timedelta(days=7)
        elif period == '30':
            start_date = timezone.now() - timedelta(days=30)
        elif period == '90':
            start_date = timezone.now() - timedelta(days=90)
        else:  # 365
            start_date = timezone.now() - timedelta(days=365)
        
        # Get engagement metrics
        completions = UserTaskCompletion.objects.filter(
            user=user,
            tenant_id=tenant_id,
            completed_at__gte=start_date,
            status='completed'
        )
        
        total_completions = completions.count()
        total_earnings = completions.aggregate(
            total=Sum(F('rewards_awarded__amount'))
        )['total'] or Decimal('0')
        
        # Calculate engagement metrics
        avg_daily_completions = total_completions / max(int(period), 1)
        avg_daily_earnings = total_earnings / max(int(period), 1)
        
        # Get session data
        sessions = _get_user_sessions(user, tenant_id, start_date)
        avg_session_duration = sessions['avg_duration'] if sessions else 0
        total_sessions = sessions['total_sessions'] if sessions else 0
        
        engagement_data = {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'period': {
                'days': period,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'activity_metrics': {
                'total_completions': total_completions,
                'total_earnings': str(total_earnings),
                'avg_daily_completions': round(avg_daily_completions, 2),
                'avg_daily_earnings': str(round(avg_daily_earnings, 2)),
                'completion_rate': _calculate_completion_rate(user, tenant_id, start_date),
                'streak_data': _get_streak_data(user, tenant_id),
                'most_active_day': _get_most_active_day(user, tenant_id, start_date),
                'peak_hours': _get_peak_hours(user, tenant_id, start_date),
            },
            'session_metrics': {
                'total_sessions': total_sessions,
                'avg_session_duration_minutes': avg_session_duration,
                'avg_sessions_per_day': round(total_sessions / max(int(period), 1), 2),
                'bounce_rate': _calculate_bounce_rate(sessions),
                'returning_user_rate': _calculate_returning_user_rate(user, tenant_id),
            },
            'engagement_score': _calculate_engagement_score(
                total_completions, total_earnings, avg_session_duration, total_sessions
            ),
            'recommendations': _get_engagement_recommendations(user, tenant_id),
            'trends': _get_engagement_trends(user, tenant_id, start_date)
        }
        
        return Response({
            'success': True,
            'data': engagement_data,
            'message': 'Engagement metrics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[EngagementAdapter] Error getting engagement metrics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve engagement metrics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_engagement_activities(request):
    """Get user's engagement activities."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        activity_type = request.GET.get('type', 'all')  # 'all', 'completions', 'logins', 'interactions'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get activities based on type
        activities = []
        
        if activity_type in ['all', 'completions']:
            activities.extend(_get_completion_activities(user, tenant_id, limit, offset))
        
        if activity_type in ['all', 'logins']:
            activities.extend(_get_login_activities(user, tenant_id, limit, offset))
        
        if activity_type in ['all', 'interactions']:
            activities.extend(_get_interaction_activities(user, tenant_id, limit, offset))
        
        return Response({
            'success': True,
            'data': {
                'user_id': user.id,
                'tenant_id': tenant_id,
                'activities': activities,
                'filters': {
                    'type': activity_type,
                    'limit': limit,
                    'offset': offset
                }
            },
            'message': 'Engagement activities retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[EngagementAdapter] Error getting engagement activities: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve engagement activities',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def track_engagement_event(request):
    """Track user engagement event."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        event_type = data.get('event_type')
        event_data = data.get('event_data', {})
        
        if not event_type:
            return Response({
                'success': False,
                'error': 'Event type required',
                'details': 'Please provide event_type'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create engagement event
        from engagement.models import EngagementEvent
        event = EngagementEvent.objects.create(
            user=user,
            event_type=event_type,
            event_data=event_data,
            ip_address=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Update user engagement score
        _update_engagement_score(user, event_type, event_data)
        
        # Emit engagement event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('engagement.event_tracked', {
            'user_id': user.id,
            'event_id': event.id,
            'event_type': event_type,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'event_id': event.id,
                'event_type': event_type,
                'tracked_at': event.created_at.isoformat()
            },
            'message': 'Engagement event tracked successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[EngagementAdapter] Error tracking engagement event: {e}")
        return Response({
            'success': False,
            'error': 'Failed to track engagement event',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_engagement_analytics(request):
    """Get engagement analytics for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get engagement analytics
        from engagement.models import EngagementEvent
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get overall metrics
        total_events = EngagementEvent.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).count()
        
        # Get event type breakdown
        event_types = EngagementEvent.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).values('event_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Get top engaged users
        top_users = User.objects.filter(
            tenant_id=tenant_id
        ).annotate(
            event_count=Count('engagementevent')
        ).order_by('-event_count')[:10]
        
        # Get daily trends
        daily_trends = EngagementEvent.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).extra({
            'day': 'date(created_at)'
        }).values('day').annotate(
            count=Count('id')
        ).order_by('day')
        
        analytics_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'summary': {
                'total_events': total_events,
                'unique_users': EngagementEvent.objects.filter(
                    tenant_id=tenant_id,
                    created_at__gte=start_date
                ).values('user').distinct().count(),
                'avg_events_per_user': round(total_events / max(
                    EngagementEvent.objects.filter(
                        tenant_id=tenant_id,
                        created_at__gte=start_date
                    ).values('user').distinct().count(), 1
                ), 2)
            },
            'event_types': list(event_types),
            'top_users': [
                {
                    'user_id': user.id,
                    'username': user.username,
                    'event_count': user.event_count,
                    'engagement_score': _calculate_user_engagement_score(user.id, tenant_id)
                }
                for user in top_users
            ],
            'daily_trends': [
                {
                    'date': trend['day'].isoformat(),
                    'event_count': trend['count']
                }
                for trend in daily_trends
            ],
            'engagement_score_distribution': _get_engagement_score_distribution(tenant_id, start_date)
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'Engagement analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[EngagementAdapter] Error getting engagement analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve engagement analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def _get_user_sessions(user, tenant_id, start_date):
    """Get user session data."""
    try:
        from engagement.models import UserSession
        sessions = UserSession.objects.filter(
            user=user,
            tenant_id=tenant_id,
            start_time__gte=start_date
        )
        
        if not sessions.exists():
            return None
        
        total_sessions = sessions.count()
        total_duration = sessions.aggregate(
            total=Sum(F('end_time') - F('start_time'))
        )['total']
        
        return {
            'total_sessions': total_sessions,
            'avg_duration': (total_duration.total_seconds() / total_sessions / 60) if total_sessions > 0 else 0
        }
    except Exception:
        return None


def _calculate_completion_rate(user, tenant_id, start_date):
    """Calculate user's completion rate."""
    try:
        from api.tasks.models import UserTaskCompletion
        total_started = UserTaskCompletion.objects.filter(
            user=user,
            tenant_id=tenant_id,
            started_at__gte=start_date
        ).count()
        
        total_completed = UserTaskCompletion.objects.filter(
            user=user,
            tenant_id=tenant_id,
            completed_at__gte=start_date,
            status='completed'
        ).count()
        
        return round((total_completed / max(total_started, 1)) * 100, 2)
    except Exception:
        return 0.0


def _get_streak_data(user, tenant_id):
    """Get user's streak data."""
    try:
        from engagement.models import UserStreak
        streak = UserStreak.objects.filter(
            user=user,
            tenant_id=tenant_id,
            is_active=True
        ).first()
        
        if not streak:
            return {
                'current_streak': 0,
                'longest_streak': 0,
                'streak_start_date': None
            }
        
        return {
            'current_streak': streak.current_streak,
            'longest_streak': streak.longest_streak,
            'streak_start_date': streak.start_date.isoformat() if streak.start_date else None
        }
    except Exception:
        return {
            'current_streak': 0,
            'longest_streak': 0,
            'streak_start_date': None
        }


def _get_most_active_day(user, tenant_id, start_date):
    """Get user's most active day."""
    try:
        from api.tasks.models import UserTaskCompletion
        from django.db.models import TruncDay
        
        daily_activity = UserTaskCompletion.objects.filter(
            user=user,
            tenant_id=tenant_id,
            completed_at__gte=start_date,
            status='completed'
        ).extra({
            'day': TruncDay('completed_at')
        }).values('day').annotate(
            count=Count('id')
        ).order_by('-count')
        
        if not daily_activity.exists():
            return None
        
        most_active = daily_activity.first()
        return {
            'date': most_active['day'].isoformat(),
            'completions': most_active['count']
        }
    except Exception:
        return None


def _get_peak_hours(user, tenant_id, start_date):
    """Get user's peak activity hours."""
    try:
        from api.tasks.models import UserTaskCompletion
        from django.db.models import TruncHour
        
        hourly_activity = UserTaskCompletion.objects.filter(
            user=user,
            tenant_id=tenant_id,
            completed_at__gte=start_date,
            status='completed'
        ).extra({
            'hour': 'hour(completed_at)'
        }).values('hour').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return [
            {
                'hour': activity['hour'],
                'count': activity['count']
            }
            for activity in hourly_activity[:5]  # Top 5 peak hours
        ]
    except Exception:
        return []


def _calculate_bounce_rate(sessions):
    """Calculate bounce rate from sessions."""
    try:
        if not sessions:
            return 0.0
        
        total_sessions = sessions.get('total_sessions', 0)
        bounced_sessions = sessions.get('bounced_sessions', 0)
        
        return round((bounced_sessions / max(total_sessions, 1)) * 100, 2)
    except Exception:
        return 0.0


def _calculate_returning_user_rate(user, tenant_id):
    """Calculate returning user rate."""
    try:
        from engagement.models import UserSession
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        total_sessions = UserSession.objects.filter(
            user=user,
            tenant_id=tenant_id,
            start_time__gte=thirty_days_ago
        ).count()
        
        if total_sessions == 0:
            return 0.0
        
        # Check if user had sessions before 30 days ago
        previous_sessions = UserSession.objects.filter(
            user=user,
            tenant_id=tenant_id,
            start_time__lt=thirty_days_ago
        ).exists()
        
        return 100.0 if previous_sessions else 0.0
    except Exception:
        return 0.0


def _calculate_engagement_score(completions, earnings, avg_duration, sessions):
    """Calculate overall engagement score."""
    try:
        # Normalize metrics to 0-100 scale
        completion_score = min(completions / 100, 1.0) * 30  # Max 30 points
        earnings_score = min(float(earnings) / 1000, 1.0) * 25  # Max 25 points
        duration_score = min(avg_duration / 30, 1.0) * 25  # Max 25 points
        session_score = min(sessions / 50, 1.0) * 20  # Max 20 points
        
        return round(completion_score + earnings_score + duration_score + session_score, 2)
    except Exception:
        return 0.0


def _get_engagement_recommendations(user, tenant_id):
    """Get engagement recommendations for user."""
    try:
        recommendations = []
        
        # Get user context
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        # Recommendations based on engagement level
        engagement_score = _calculate_user_engagement_score(user.id, tenant_id)
        
        if engagement_score < 30:
            recommendations.append({
                'type': 'increase_activity',
                'title': 'Increase Your Activity',
                'description': 'Try completing more tasks to boost your engagement score',
                'priority': 'high'
            })
        
        if ctx.wallet_balance < Decimal('50'):
            recommendations.append({
                'type': 'explore_higher_value',
                'title': 'Explore Higher Value Tasks',
                'description': 'Focus on tasks with better rewards to maximize earnings',
                'priority': 'medium'
            })
        
        if engagement_score > 70:
            recommendations.append({
                'type': 'maintain_streak',
                'title': 'Maintain Your Streak',
                'description': 'Keep up the great work to maintain your engagement streak',
                'priority': 'low'
            })
        
        return recommendations
    except Exception:
        return []


def _get_engagement_trends(user, tenant_id, start_date):
    """Get engagement trends for user."""
    try:
        from api.tasks.models import UserTaskCompletion
        from django.db.models import TruncDay
        
        daily_trends = UserTaskCompletion.objects.filter(
            user=user,
            tenant_id=tenant_id,
            completed_at__gte=start_date,
            status='completed'
        ).extra({
            'day': TruncDay('completed_at')
        }).values('day').annotate(
            completions=Count('id'),
            earnings=Sum(F('rewards_awarded__amount'))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'completions': trend['completions'],
                'earnings': str(trend['earnings'] or Decimal('0'))
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _calculate_user_engagement_score(user_id, tenant_id):
    """Calculate engagement score for a user."""
    try:
        from engagement.models import EngagementEvent
        from django.utils import timezone
        from datetime import timedelta
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        events = EngagementEvent.objects.filter(
            user_id=user_id,
            tenant_id=tenant_id,
            created_at__gte=thirty_days_ago
        )
        
        # Calculate score based on event types and frequency
        score = 0
        
        # Login events
        login_events = events.filter(event_type='login').count()
        score += min(login_events * 2, 20)  # Max 20 points for logins
        
        # Completion events
        completion_events = events.filter(event_type='task_completion').count()
        score += min(completion_events * 5, 50)  # Max 50 points for completions
        
        # Interaction events
        interaction_events = events.filter(event_type='interaction').count()
        score += min(interaction_events * 3, 30)  # Max 30 points for interactions
        
        return min(score, 100)
    except Exception:
        return 0.0


def _get_engagement_score_distribution(tenant_id, start_date):
    """Get engagement score distribution across users."""
    try:
        from engagement.models import EngagementEvent
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get all users with engagement scores
        users = User.objects.filter(tenant_id=tenant_id)
        
        scores = []
        for user in users:
            score = _calculate_user_engagement_score(user.id, tenant_id)
            scores.append(score)
        
        if not scores:
            return {}
        
        # Calculate distribution
        sorted_scores = sorted(scores)
        total_users = len(scores)
        
        return {
            'min_score': min(scores),
            'max_score': max(scores),
            'avg_score': round(sum(scores) / total_users, 2),
            'median_score': sorted_scores[total_users // 2] if total_users > 0 else 0,
            'distribution': {
                'low_engagement': len([s for s in scores if s < 30]),
                'medium_engagement': len([s for s in scores if 30 <= s < 70]),
                'high_engagement': len([s for s in scores if s >= 70])
            }
        }
    except Exception:
        return {}


def _update_engagement_score(user, event_type, event_data):
    """Update user's engagement score based on event."""
    try:
        current_score = cache.get(f'engagement_score_{user.id}', 0)
        
        # Update score based on event type
        if event_type == 'login':
            current_score += 2
        elif event_type == 'task_completion':
            current_score += 5
        elif event_type == 'interaction':
            current_score += 3
        
        # Cache updated score
        cache.set(f'engagement_score_{user.id}', current_score, timeout=86400)
    except Exception:
        pass


def _get_completion_activities(user, tenant_id, limit, offset):
    """Get completion activities for user."""
    try:
        from api.tasks.models import UserTaskCompletion
        completions = UserTaskCompletion.objects.filter(
            user=user,
            tenant_id=tenant_id,
            status='completed'
        ).order_by('-completed_at')[offset:offset+limit]
        
        return [
            {
                'id': completion.id,
                'activity_type': 'completion',
                'task_id': completion.task_id,
                'task_name': completion.task.name if completion.task else 'Unknown Task',
                'reward': str(completion.rewards_awarded) if completion.rewards_awarded else '0.00',
                'completed_at': completion.completed_at.isoformat(),
                'completion_time_minutes': (completion.completed_at - completion.started_at).total_seconds() / 60 if completion.started_at else 0
            }
            for completion in completions
        ]
    except Exception:
        return []


def _get_login_activities(user, tenant_id, limit, offset):
    """Get login activities for user."""
    try:
        from engagement.models import UserSession
        sessions = UserSession.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).order_by('-start_time')[offset:offset+limit]
        
        return [
            {
                'id': session.id,
                'activity_type': 'login',
                'login_time': session.start_time.isoformat(),
                'logout_time': session.end_time.isoformat() if session.end_time else None,
                'duration_minutes': (session.end_time - session.start_time).total_seconds() / 60 if session.end_time else None,
                'ip_address': session.ip_address,
                'user_agent': session.user_agent
            }
            for session in sessions
        ]
    except Exception:
        return []


def _get_interaction_activities(user, tenant_id, limit, offset):
    """Get interaction activities for user."""
    try:
        from engagement.models import EngagementEvent
        interactions = EngagementEvent.objects.filter(
            user=user,
            tenant_id=tenant_id,
            event_type='interaction'
        ).order_by('-created_at')[offset:offset+limit]
        
        return [
            {
                'id': event.id,
                'activity_type': 'interaction',
                'event_type': event.event_type,
                'event_data': event.event_data,
                'created_at': event.created_at.isoformat()
            }
            for event in interactions
        ]
    except Exception:
        return []


def _get_client_ip(request):
    """Get client IP address."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip
    
    return request.META.get('REMOTE_ADDR', '127.0.0.1')
