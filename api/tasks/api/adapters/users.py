"""
api/adapters/users.py
User management adapter for earning backend platform
"""
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get user profile information."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        profile_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'date_joined': user.date_joined,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'tenant_id': tenant_id,
            'last_login': getattr(user, 'last_login', None),
        }
        
        # Add tenant-specific data
        if tenant_id:
            from api.tasks.integration.shared_context import SharedContext
            ctx = SharedContext.for_user(user.id)
            profile_data.update({
                'wallet_balance': str(ctx.wallet_balance),
                'fraud_score': ctx.fraud_score,
                'kyc_tier': ctx.kyc_tier,
                'user_level': getattr(user, 'level', 1),
                'total_earnings': str(ctx.total_earnings),
                'is_eligible_for_payout': ctx.is_eligible_for_payout,
            })
        
        return Response({
            'success': True,
            'data': profile_data,
            'message': 'User profile retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[UsersAdapter] Error getting profile: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve user profile',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """Update user profile information."""
    try:
        user = request.user
        data = request.data
        
        # Update allowed fields
        allowed_fields = ['first_name', 'last_name', 'email']
        updated_fields = []
        
        for field in allowed_fields:
            if field in data:
                setattr(user, field, data[field])
                updated_fields.append(field)
        
        if updated_fields:
            user.save()
            
            # Log profile update
            from api.tasks.integration.event_bus import EventBus
            EventBus.emit('user.profile_updated', {
                'user_id': user.id,
                'updated_fields': updated_fields,
                'updated_at': timezone.now().isoformat()
            })
            
            return Response({
                'success': True,
                'data': {'updated_fields': updated_fields},
                'message': 'Profile updated successfully'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'No valid fields to update',
                'details': 'Please provide at least one valid field'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"[UsersAdapter] Error updating profile: {e}")
        return Response({
            'success': False,
            'error': 'Failed to update profile',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_stats(request):
    """Get user statistics and analytics."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user context for stats
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        stats_data = {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'wallet': {
                'balance': str(ctx.wallet_balance),
                'total_earnings': str(ctx.total_earnings),
                'withdrawal_limit': str(ctx.withdrawal_limit),
                'preferred_payment_method': ctx.preferred_payment_method,
            },
            'engagement': {
                'account_age_days': ctx.account_age_days,
                'total_tasks_completed': cache.get(f'user_tasks_completed_{user.id}', 0),
                'active_streak': cache.get(f'user_streak_{user.id}', 0),
                'badges': ctx.badges,
                'user_level': getattr(user, 'level', 1),
                'user_segment': ctx.user_segment,
            },
            'verification': {
                'kyc_tier': ctx.kyc_tier,
                'email_verified': ctx.email_verified,
                'is_eligible_for_payout': ctx.is_eligible_for_payout,
                'is_eligible_for_offers': ctx.is_eligible_for_offers,
            },
            'security': {
                'fraud_score': ctx.fraud_score,
                'is_fraud_flagged': ctx.is_fraud_flagged,
                'is_high_risk': ctx.is_high_risk,
                'is_suspended': ctx.is_suspended,
            },
            'recommendations': {
                'recommended_offers': ctx.recommended_offers,
                'recommended_tasks': ctx.recommended_tasks,
            }
        }
        
        return Response({
            'success': True,
            'data': stats_data,
            'message': 'User statistics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[UsersAdapter] Error getting stats: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve user statistics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_preferences(request):
    """Update user preferences and settings."""
    try:
        user = request.user
        data = request.data
        
        # Update preferences
        preferences = data.get('preferences', {})
        
        # Store preferences in cache
        cache.set(f'user_preferences_{user.id}', preferences, timeout=86400)
        
        # Update user model if needed
        if 'language' in preferences:
            user.language = preferences['language']
        if 'timezone' in preferences:
            user.timezone = preferences['timezone']
        
        user.save()
        
        return Response({
            'success': True,
            'data': {'preferences': preferences},
            'message': 'Preferences updated successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[UsersAdapter] Error updating preferences: {e}")
        return Response({
            'success': False,
            'error': 'Failed to update preferences',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_activity(request):
    """Get user activity history."""
    try:
        user = request.user
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        
        # Get user task completions
        from api.tasks.models import UserTaskCompletion
        completions = UserTaskCompletion.objects.filter(
            user=user
        ).order_by('-started_at')[offset:offset+limit]
        
        activity_data = {
            'user_id': user.id,
            'total_count': UserTaskCompletion.objects.filter(user=user).count(),
            'activities': [
                {
                    'task_id': completion.task.task_id,
                    'task_name': completion.task.name,
                    'status': completion.status,
                    'started_at': completion.started_at,
                    'completed_at': completion.completed_at,
                    'rewards': completion.rewards_awarded,
                }
                for completion in completions
            ]
        }
        
        return Response({
            'success': True,
            'data': activity_data,
            'message': 'User activity retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[UsersAdapter] Error getting activity: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve user activity',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
