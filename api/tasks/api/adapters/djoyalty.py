"""
api/adapters/djoyalty.py
Djoyalty (Digital Loyalty) adapter for earning backend platform
"""
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
def get_loyalty_profile(request):
    """Get user's loyalty profile."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user's loyalty profile
        from djoyalty.models import LoyaltyProfile
        try:
            profile = LoyaltyProfile.objects.get(
                user=user,
                tenant_id=tenant_id
            )
        except LoyaltyProfile.DoesNotExist:
            # Create default loyalty profile
            profile = LoyaltyProfile.objects.create(
                user=user,
                tier='bronze',
                points=0,
                lifetime_points=0,
                status='active',
                tenant_id=tenant_id,
                created_at=timezone.now()
            )
        
        # Get current tier benefits
        current_tier = _get_tier_info(profile.tier, tenant_id)
        
        # Get next tier info
        next_tier = _get_next_tier(profile.tier, profile.points, tenant_id)
        
        # Get recent activity
        recent_activity = _get_recent_loyalty_activity(user, tenant_id)
        
        profile_data = {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'loyalty_profile': {
                'profile_id': profile.id,
                'tier': profile.tier,
                'current_points': profile.points,
                'lifetime_points': profile.lifetime_points,
                'status': profile.status,
                'joined_at': profile.created_at.isoformat(),
                'last_activity': profile.last_activity.isoformat() if profile.last_activity else None,
                'streak_days': profile.streak_days,
                'longest_streak': profile.longest_streak,
                'referral_count': profile.referral_count,
                'redemption_count': profile.redemption_count,
            },
            'current_tier': current_tier,
            'next_tier': next_tier,
            'points_breakdown': {
                'earned_this_month': _get_monthly_points_earned(user, tenant_id),
                'redeemed_this_month': _get_monthly_points_redeemed(user, tenant_id),
                'points_expiring': _get_expiring_points(user, tenant_id),
                'points_history': _get_points_history(user, tenant_id, limit=10),
            },
            'benefits': {
                'available_benefits': _get_available_benefits(profile.tier, tenant_id),
                'active_benefits': _get_active_benefits(user, tenant_id),
                'bonus_multipliers': _get_bonus_multipliers(profile.tier, tenant_id),
            },
            'recent_activity': recent_activity,
            'recommendations': _get_loyalty_recommendations(user, profile, tenant_id)
        }
        
        return Response({
            'success': True,
            'data': profile_data,
            'message': 'Loyalty profile retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[DjoyaltyAdapter] Error getting loyalty profile: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve loyalty profile',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_loyalty_rewards(request):
    """Get available loyalty rewards."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        category = request.GET.get('category')  # 'all', 'discounts', 'products', 'experiences', 'cashback'
        tier_required = request.GET.get('tier')  # 'all', 'bronze', 'silver', 'gold', 'platinum'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get user's current tier
        from djoyalty.models import LoyaltyProfile
        try:
            profile = LoyaltyProfile.objects.get(
                user=user,
                tenant_id=tenant_id
            )
            user_tier = profile.tier
            user_points = profile.points
        except LoyaltyProfile.DoesNotExist:
            user_tier = 'bronze'
            user_points = 0
        
        # Get rewards
        from djoyalty.models import LoyaltyReward
        queryset = LoyaltyReward.objects.filter(
            tenant_id=tenant_id,
            is_active=True,
            available_from__lte=timezone.now(),
            available_until__gte=timezone.now()
        ).order_by('-featured', '-created_at')
        
        # Apply filters
        if category and category != 'all':
            queryset = queryset.filter(category=category)
        if tier_required and tier_required != 'all':
            queryset = queryset.filter(min_tier__in=[tier_required, 'all'])
        
        # Filter by user's points
        available_rewards = []
        for reward in queryset:
            if reward.min_tier in ['all', user_tier] and user_points >= reward.points_required:
                available_rewards.append(reward)
        
        # Paginate
        rewards = available_rewards[offset:offset+limit]
        
        # Serialize rewards
        reward_data = []
        for reward in rewards:
            reward_data.append({
                'id': reward.id,
                'name': reward.name,
                'description': reward.description,
                'category': reward.category,
                'points_required': reward.points_required,
                'min_tier': reward.min_tier,
                'reward_type': reward.reward_type,
                'reward_value': str(reward.reward_value) if reward.reward_value else None,
                'discount_percentage': reward.discount_percentage,
                'cashback_rate': reward.cashback_rate,
                'expiry_date': reward.available_until.isoformat() if reward.available_until else None,
                'is_featured': reward.is_featured,
                'is_limited': reward.is_limited,
                'quantity_available': reward.quantity_available if reward.is_limited else None,
                'quantity_redeemed': reward.quantity_redeemed if reward.is_limited else None,
                'image_url': reward.image_url,
                'terms_conditions': reward.terms_conditions,
                'user_can_redeem': user_points >= reward.points_required and reward.min_tier in ['all', user_tier],
                'user_points_shortfall': max(0, reward.points_required - user_points),
                'user_tier_eligible': reward.min_tier in ['all', user_tier],
                'metadata': reward.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'rewards': reward_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': len(available_rewards),
                    'has_more': len(reward_data) == limit
                },
                'filters': {
                    'category': category,
                    'tier_required': tier_required
                },
                'user_context': {
                    'current_tier': user_tier,
                    'current_points': user_points,
                    'next_tier': _get_next_tier(user_tier, user_points, tenant_id)
                }
            },
            'message': 'Loyalty rewards retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[DjoyaltyAdapter] Error getting loyalty rewards: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve loyalty rewards',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def redeem_reward(request, reward_id):
    """Redeem a loyalty reward."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get user's loyalty profile
        from djoyalty.models import LoyaltyProfile
        try:
            profile = LoyaltyProfile.objects.get(
                user=user,
                tenant_id=tenant_id
            )
        except LoyaltyProfile.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Loyalty profile not found',
                'details': 'Please create a loyalty profile first'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get reward
        from djoyalty.models import LoyaltyReward
        try:
            reward = LoyaltyReward.objects.get(
                id=reward_id,
                tenant_id=tenant_id,
                is_active=True
            )
        except LoyaltyReward.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Reward not found',
                'details': f'Loyalty reward with ID {reward_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check eligibility
        if not _can_redeem_reward(profile, reward):
            return Response({
                'success': False,
                'error': 'Not eligible for reward',
                'details': _get_redeem_error_message(profile, reward)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create redemption
        from djoyalty.models import LoyaltyRedemption
        redemption = LoyaltyRedemption.objects.create(
            user=user,
            profile=profile,
            reward=reward,
            points_spent=reward.points_required,
            status='pending',
            redemption_code=_generate_redemption_code(),
            delivery_method=data.get('delivery_method', 'digital'),
            delivery_address=data.get('delivery_address', {}),
            metadata=data.get('metadata', {}),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Update profile
        profile.points -= reward.points_required
        profile.redemption_count += 1
        profile.last_activity = timezone.now()
        profile.save()
        
        # Update reward quantity if limited
        if reward.is_limited:
            reward.quantity_redeemed += 1
            reward.save()
        
        # Process redemption
        redemption_result = _process_redemption(redemption, user, reward, data)
        
        # Emit redemption event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('djoyalty.reward_redeemed', {
            'user_id': user.id,
            'profile_id': profile.id,
            'reward_id': reward_id,
            'redemption_id': redemption.id,
            'points_spent': reward.points_required,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'redemption_id': redemption.id,
                'reward': {
                    'id': reward.id,
                    'name': reward.name,
                    'category': reward.category,
                    'reward_type': reward.reward_type,
                },
                'points_spent': reward.points_required,
                'remaining_points': profile.points,
                'redemption_code': redemption.redemption_code,
                'status': redemption_result['status'],
                'delivery_method': redemption.delivery_method,
                'estimated_delivery': redemption_result['estimated_delivery'],
                'created_at': redemption.created_at.isoformat()
            },
            'message': 'Reward redeemed successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[DjoyaltyAdapter] Error redeeming reward: {e}")
        return Response({
            'success': False,
            'error': 'Failed to redeem reward',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_redemption_history(request):
    """Get user's redemption history."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        status_filter = request.GET.get('status')  # 'all', 'pending', 'processing', 'completed', 'cancelled'
        category = request.GET.get('category')
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get redemptions
        from djoyalty.models import LoyaltyRedemption
        queryset = LoyaltyRedemption.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).select_related('reward').order_by('-created_at')
        
        # Apply filters
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        if category:
            queryset = queryset.filter(reward__category=category)
        
        # Paginate
        redemptions = queryset[offset:offset+limit]
        
        # Serialize redemptions
        redemption_data = []
        for redemption in redemptions:
            redemption_data.append({
                'id': redemption.id,
                'reward': {
                    'id': redemption.reward.id,
                    'name': redemption.reward.name,
                    'category': redemption.reward.category,
                    'reward_type': redemption.reward.reward_type,
                    'image_url': redemption.reward.image_url,
                },
                'points_spent': redemption.points_spent,
                'status': redemption.status,
                'redemption_code': redemption.redemption_code,
                'delivery_method': redemption.delivery_method,
                'delivery_address': redemption.delivery_address,
                'tracking_number': redemption.tracking_number,
                'created_at': redemption.created_at.isoformat(),
                'processed_at': redemption.processed_at.isoformat() if redemption.processed_at else None,
                'completed_at': redemption.completed_at.isoformat() if redemption.completed_at else None,
                'estimated_delivery': redemption.estimated_delivery.isoformat() if redemption.estimated_delivery else None,
                'metadata': redemption.metadata,
                'cancellation_reason': redemption.cancellation_reason,
                'refund_points': redemption.refund_points,
                'refund_reason': redemption.refund_reason
            })
        
        return Response({
            'success': True,
            'data': {
                'redemptions': redemption_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(redemption_data) == limit
                },
                'filters': {
                    'status': status_filter,
                    'category': category
                },
                'summary': _get_redemption_summary(queryset)
            },
            'message': 'Redemption history retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[DjoyaltyAdapter] Error getting redemption history: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve redemption history',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_points_history(request):
    """Get user's points history."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        transaction_type = request.GET.get('type')  # 'all', 'earned', 'redeemed', 'expired', 'bonus'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get points history
        from djoyalty.models import PointsTransaction
        queryset = PointsTransaction.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply type filter
        if transaction_type and transaction_type != 'all':
            queryset = queryset.filter(transaction_type=transaction_type)
        
        # Paginate
        transactions = queryset[offset:offset+limit]
        
        # Serialize transactions
        transaction_data = []
        for transaction in transactions:
            transaction_data.append({
                'id': transaction.id,
                'transaction_type': transaction.transaction_type,
                'points_change': transaction.points_change,
                'points_balance': transaction.points_balance,
                'description': transaction.description,
                'reference_id': transaction.reference_id,
                'reference_type': transaction.reference_type,
                'created_at': transaction.created_at.isoformat(),
                'expires_at': transaction.expires_at.isoformat() if transaction.expires_at else None,
                'is_expired': transaction.expires_at and transaction.expires_at < timezone.now(),
                'metadata': transaction.metadata
            })
        
        return Response({
            'success': True,
            'data': {
                'transactions': transaction_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(transaction_data) == limit
                },
                'filters': {
                    'type': transaction_type
                },
                'summary': _get_points_summary(queryset)
            },
            'message': 'Points history retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[DjoyaltyAdapter] Error getting points history: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve points history',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_loyalty_analytics(request):
    """Get loyalty analytics for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get loyalty analytics
        from djoyalty.models import LoyaltyProfile, LoyaltyRedemption, PointsTransaction, LoyaltyReward
        
        # Profile analytics
        profiles = LoyaltyProfile.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        )
        
        # Redemption analytics
        redemptions = LoyaltyRedemption.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        ).select_related('reward')
        
        # Points analytics
        transactions = PointsTransaction.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        )
        
        # Calculate analytics
        analytics_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'member_analytics': {
                'total_members': LoyaltyProfile.objects.filter(tenant_id=tenant_id).count(),
                'new_members': profiles.count(),
                'active_members': profiles.filter(status='active').count(),
                'tier_distribution': list(profiles.values('tier').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'average_points_per_member': profiles.aggregate(
                    avg_points=Avg('points')
                )['avg_points'] or 0,
                'total_points_held': profiles.aggregate(
                    total=Sum('points')
                )['total'] or 0,
            },
            'redemption_analytics': {
                'total_redemptions': redemptions.count(),
                'completed_redemptions': redemptions.filter(status='completed').count(),
                'pending_redemptions': redemptions.filter(status='pending').count(),
                'cancelled_redemptions': redemptions.filter(status='cancelled').count(),
                'total_points_redeemed': redemptions.aggregate(
                    total=Sum('points_spent')
                )['total'] or 0,
                'average_points_per_redemption': redemptions.aggregate(
                    avg_points=Avg('points_spent')
                )['avg_points'] or 0,
                'popular_rewards': list(redemptions.values(
                    'reward__name',
                    'reward__category'
                ).annotate(
                    count=Count('id')
                ).order_by('-count')[:10]),
                'redemption_by_tier': list(redemptions.values(
                    'profile__tier'
                ).annotate(
                    count=Count('id')
                ).order_by('-count')),
                'daily_trends': _get_redemption_trends(redemptions, days)
            },
            'points_analytics': {
                'total_points_earned': transactions.filter(
                    points_change__gt=0
                ).aggregate(
                    total=Sum('points_change')
                )['total'] or 0,
                'total_points_redeemed': abs(transactions.filter(
                    points_change__lt=0
                ).aggregate(
                    total=Sum('points_change')
                )['total'] or 0),
                'points_expired': transactions.filter(
                    transaction_type='expired'
                ).aggregate(
                    total=Sum('points_change')
                )['total'] or 0,
                'points_by_type': list(transactions.values('transaction_type').annotate(
                    count=Count('id'),
                    total_points=Sum('points_change')
                ).order_by('-total_points')),
                'daily_trends': _get_points_trends(transactions, days)
            },
            'reward_analytics': {
                'total_rewards': LoyaltyReward.objects.filter(tenant_id=tenant_id).count(),
                'active_rewards': LoyaltyReward.objects.filter(
                    tenant_id=tenant_id,
                    is_active=True
                ).count(),
                'rewards_by_category': list(LoyaltyReward.objects.filter(
                    tenant_id=tenant_id
                ).values('category').annotate(
                    count=Count('id')
                ).order_by('-count')),
                'most_redeemed_rewards': list(redemptions.filter(
                    status='completed'
                ).values('reward__name').annotate(
                    count=Count('id')
                ).order_by('-count')[:10]),
                'rewards_by_tier': list(LoyaltyReward.objects.filter(
                    tenant_id=tenant_id
                ).values('min_tier').annotate(
                    count=Count('id')
                ).order_by('-count'))
            }
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'Loyalty analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[DjoyaltyAdapter] Error getting loyalty analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve loyalty analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions
def _get_tier_info(tier, tenant_id) -> Dict:
    """Get tier information."""
    try:
        from djoyalty.models import LoyaltyTier
        try:
            tier_info = LoyaltyTier.objects.get(
                name=tier,
                tenant_id=tenant_id
            )
            return {
                'name': tier_info.name,
                'display_name': tier_info.display_name,
                'description': tier_info.description,
                'min_points': tier_info.min_points,
                'benefits': tier_info.benefits,
                'color': tier_info.color,
                'icon': tier_info.icon,
                'bonus_multiplier': tier_info.bonus_multiplier,
                'exclusive_access': tier_info.exclusive_access
            }
        except LoyaltyTier.DoesNotExist:
            return _get_default_tier_info(tier)
    except Exception:
        return _get_default_tier_info(tier)


def _get_default_tier_info(tier) -> Dict:
    """Get default tier information."""
    tier_configs = {
        'bronze': {
            'display_name': 'Bronze',
            'description': 'Entry level with basic benefits',
            'min_points': 0,
            'benefits': ['Basic support', 'Standard rewards'],
            'color': '#CD7F32',
            'icon': 'bronze-medal',
            'bonus_multiplier': 1.0,
            'exclusive_access': []
        },
        'silver': {
            'display_name': 'Silver',
            'description': 'Enhanced benefits and exclusive rewards',
            'min_points': 1000,
            'benefits': ['Priority support', 'Enhanced rewards', 'Early access'],
            'color': '#C0C0C0',
            'icon': 'silver-medal',
            'bonus_multiplier': 1.2,
            'exclusive_access': ['silver_rewards']
        },
        'gold': {
            'display_name': 'Gold',
            'description': 'Premium benefits and VIP rewards',
            'min_points': 5000,
            'benefits': ['VIP support', 'Premium rewards', 'Exclusive events'],
            'color': '#FFD700',
            'icon': 'gold-medal',
            'bonus_multiplier': 1.5,
            'exclusive_access': ['gold_rewards', 'vip_events']
        },
        'platinum': {
            'display_name': 'Platinum',
            'description': 'Ultimate benefits and exclusive VIP access',
            'min_points': 10000,
            'benefits': ['Dedicated support', 'Ultimate rewards', 'All access'],
            'color': '#E5E4E2',
            'icon': 'platinum-medal',
            'bonus_multiplier': 2.0,
            'exclusive_access': ['platinum_rewards', 'vip_events', 'exclusive_content']
        }
    }
    
    return tier_configs.get(tier, tier_configs['bronze'])


def _get_next_tier(current_tier, current_points, tenant_id) -> Optional[Dict]:
    """Get next tier information."""
    tier_hierarchy = ['bronze', 'silver', 'gold', 'platinum']
    
    try:
        current_index = tier_hierarchy.index(current_tier)
        if current_index < len(tier_hierarchy) - 1:
            next_tier_name = tier_hierarchy[current_index + 1]
            next_tier_info = _get_tier_info(next_tier_name, tenant_id)
            
            points_needed = max(0, next_tier_info['min_points'] - current_points)
            
            return {
                'name': next_tier_name,
                'display_name': next_tier_info['display_name'],
                'points_needed': points_needed,
                'progress_percentage': min(100, (current_points / max(next_tier_info['min_points'], 1)) * 100),
                'benefits_preview': next_tier_info['benefits'][:3],  # Show first 3 benefits
            }
    except (ValueError, IndexError):
        pass
    
    return None


def _get_recent_loyalty_activity(user, tenant_id, limit=5) -> List[Dict]:
    """Get recent loyalty activity."""
    try:
        from djoyalty.models import PointsTransaction, LoyaltyRedemption
        activities = []
        
        # Get recent transactions
        transactions = PointsTransaction.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).order_by('-created_at')[:limit]
        
        for transaction in transactions:
            activities.append({
                'type': 'transaction',
                'description': transaction.description,
                'points_change': transaction.points_change,
                'created_at': transaction.created_at.isoformat(),
                'transaction_type': transaction.transaction_type
            })
        
        # Get recent redemptions
        redemptions = LoyaltyRedemption.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).select_related('reward').order_by('-created_at')[:limit]
        
        for redemption in redemptions:
            activities.append({
                'type': 'redemption',
                'description': f"Redeemed {redemption.reward.name}",
                'points_change': -redemption.points_spent,
                'created_at': redemption.created_at.isoformat(),
                'reward_name': redemption.reward.name
            })
        
        # Sort by date and return latest
        activities.sort(key=lambda x: x['created_at'], reverse=True)
        return activities[:limit]
        
    except Exception:
        return []


def _get_monthly_points_earned(user, tenant_id) -> int:
    """Get points earned this month."""
    try:
        from djoyalty.models import PointsTransaction
        from django.utils import timezone
        from datetime import timedelta
        
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        return PointsTransaction.objects.filter(
            user=user,
            tenant_id=tenant_id,
            created_at__gte=month_start,
            points_change__gt=0
        ).aggregate(
            total=Sum('points_change')
        )['total'] or 0
    except Exception:
        return 0


def _get_monthly_points_redeemed(user, tenant_id) -> int:
    """Get points redeemed this month."""
    try:
        from djoyalty.models import LoyaltyRedemption
        from django.utils import timezone
        from datetime import timedelta
        
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        return LoyaltyRedemption.objects.filter(
            user=user,
            tenant_id=tenant_id,
            created_at__gte=month_start
        ).aggregate(
            total=Sum('points_spent')
        )['total'] or 0
    except Exception:
        return 0


def _get_expiring_points(user, tenant_id) -> int:
    """Get expiring points."""
    try:
        from djoyalty.models import PointsTransaction
        from django.utils import timezone
        from datetime import timedelta
        
        thirty_days_from_now = timezone.now() + timedelta(days=30)
        
        return PointsTransaction.objects.filter(
            user=user,
            tenant_id=tenant_id,
            expires_at__lte=thirty_days_from_now,
            points_change__gt=0
        ).aggregate(
            total=Sum('points_change')
        )['total'] or 0
    except Exception:
        return 0


def _get_points_history(user, tenant_id, limit=10) -> List[Dict]:
    """Get points history."""
    try:
        from djoyalty.models import PointsTransaction
        transactions = PointsTransaction.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).order_by('-created_at')[:limit]
        
        return [
            {
                'id': transaction.id,
                'transaction_type': transaction.transaction_type,
                'points_change': transaction.points_change,
                'description': transaction.description,
                'created_at': transaction.created_at.isoformat(),
                'expires_at': transaction.expires_at.isoformat() if transaction.expires_at else None,
                'reference_id': transaction.reference_id,
                'metadata': transaction.metadata
            }
            for transaction in transactions
        ]
    except Exception:
        return []


def _get_available_benefits(tier, tenant_id) -> List[Dict]:
    """Get available benefits for tier."""
    tier_info = _get_tier_info(tier, tenant_id)
    return tier_info.get('benefits', [])


def _get_active_benefits(user, tenant_id) -> List[Dict]:
    """Get user's active benefits."""
    try:
        from djoyalty.models import LoyaltyProfile
        profile = LoyaltyProfile.objects.get(
            user=user,
            tenant_id=tenant_id
        )
        
        tier_info = _get_tier_info(profile.tier, tenant_id)
        return tier_info.get('benefits', [])
    except Exception:
        return []


def _get_bonus_multipliers(tier, tenant_id) -> Dict:
    """Get bonus multipliers for tier."""
    tier_info = _get_tier_info(tier, tenant_id)
    return {
        'points_multiplier': tier_info.get('bonus_multiplier', 1.0),
        'rewards_multiplier': tier_info.get('bonus_multiplier', 1.0),
        'discount_multiplier': tier_info.get('bonus_multiplier', 1.0)
    }


def _get_loyalty_recommendations(user, profile, tenant_id) -> List[Dict]:
    """Get loyalty recommendations for user."""
    recommendations = []
    
    # Points earning recommendations
    if profile.points < 1000:
        recommendations.append({
            'type': 'earn_points',
            'title': 'Earn More Points',
            'description': 'Complete tasks and activities to earn points',
            'priority': 'high'
        })
    
    # Tier upgrade recommendations
    next_tier = _get_next_tier(profile.tier, profile.points, tenant_id)
    if next_tier and next_tier['points_needed'] > 0:
        recommendations.append({
            'type': 'tier_upgrade',
            'title': f"Upgrade to {next_tier['display_name']}",
            'description': f"Earn {next_tier['points_needed']} more points to unlock {next_tier['display_name']} benefits",
            'priority': 'medium'
        })
    
    # Redemption recommendations
    if profile.points > 500:
        recommendations.append({
            'type': 'redeem_rewards',
            'title': 'Redeem Rewards',
            'description': 'You have enough points to redeem great rewards',
            'priority': 'low'
        })
    
    return recommendations


def _can_redeem_reward(profile, reward) -> bool:
    """Check if user can redeem reward."""
    # Check points
    if profile.points < reward.points_required:
        return False
    
    # Check tier eligibility
    if reward.min_tier not in ['all', profile.tier]:
        return False
    
    # Check availability
    if reward.is_limited and reward.quantity_available <= reward.quantity_redeemed:
        return False
    
    # Check date range
    now = timezone.now()
    if reward.available_from and now < reward.available_from:
        return False
    if reward.available_until and now > reward.available_until:
        return False
    
    return True


def _get_redeem_error_message(profile, reward) -> str:
    """Get specific error message for redemption failure."""
    if profile.points < reward.points_required:
        return f"Insufficient points. You need {reward.points_required} points but only have {profile.points}"
    
    if reward.min_tier not in ['all', profile.tier]:
        return f"This reward requires {reward.min_tier} tier or higher. Your current tier is {profile.tier}"
    
    if reward.is_limited and reward.quantity_available <= reward.quantity_redeemed:
        return "This reward is no longer available"
    
    now = timezone.now()
    if reward.available_from and now < reward.available_from:
        return f"This reward will be available on {reward.available_from.strftime('%B %d, %Y')}"
    
    if reward.available_until and now > reward.available_until:
        return "This reward has expired"
    
    return "Unable to redeem this reward"


def _generate_redemption_code() -> str:
    """Generate unique redemption code."""
    import uuid
    return str(uuid.uuid4()).upper()[:8]


def _process_redemption(redemption, user, reward, data) -> Dict:
    """Process redemption based on reward type."""
    try:
        if reward.reward_type == 'digital':
            return {
                'status': 'completed',
                'estimated_delivery': None,
                'delivery_details': {
                    'type': 'digital',
                    'download_url': f"/api/djoyalty/download/{redemption.id}/",
                    'access_code': redemption.redemption_code
                }
            }
        elif reward.reward_type == 'physical':
            return {
                'status': 'processing',
                'estimated_delivery': timezone.now() + timedelta(days=7),
                'delivery_details': {
                    'type': 'physical',
                    'address': redemption.delivery_address,
                    'tracking_number': None
                }
            }
        elif reward.reward_type == 'discount':
            return {
                'status': 'completed',
                'estimated_delivery': None,
                'delivery_details': {
                    'type': 'discount',
                    'discount_code': redemption.redemption_code,
                    'discount_value': reward.discount_percentage
                }
            }
        else:
            return {
                'status': 'processing',
                'estimated_delivery': timezone.now() + timedelta(days=1),
                'delivery_details': {
                    'type': reward.reward_type,
                    'code': redemption.redemption_code
                }
            }
    except Exception:
        return {
            'status': 'failed',
            'estimated_delivery': None,
            'delivery_details': {}
        }


def _get_redemption_summary(queryset) -> Dict:
    """Get redemption summary statistics."""
    try:
        total_redemptions = queryset.count()
        completed_redemptions = queryset.filter(status='completed').count()
        total_points_spent = queryset.aggregate(
            total=Sum('points_spent')
        )['total'] or 0
        
        return {
            'total_redemptions': total_redemptions,
            'completed_redemptions': completed_redemptions,
            'pending_redemptions': queryset.filter(status='pending').count(),
            'cancelled_redemptions': queryset.filter(status='cancelled').count(),
            'success_rate': round((completed_redemptions / max(total_redemptions, 1)) * 100, 2),
            'total_points_spent': total_points_spent,
            'average_points_per_redemption': round(total_points_spent / max(completed_redemptions, 1), 2)
        }
    except Exception:
        return {}


def _get_points_summary(queryset) -> Dict:
    """Get points summary statistics."""
    try:
        total_transactions = queryset.count()
        total_earned = queryset.filter(
            points_change__gt=0
        ).aggregate(
            total=Sum('points_change')
        )['total'] or 0
        
        total_spent = abs(queryset.filter(
            points_change__lt=0
        ).aggregate(
            total=Sum('points_change')
        )['total'] or 0)
        
        return {
            'total_transactions': total_transactions,
            'total_earned': total_earned,
            'total_spent': total_spent,
            'net_balance': total_earned - total_spent,
            'transaction_types': list(queryset.values('transaction_type').annotate(
                count=Count('id'),
                total_points=Sum('points_change')
            ).order_by('-total_points'))
        }
    except Exception:
        return {}


def _get_redemption_trends(redemptions, days) -> List[Dict]:
    """Get redemption trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = redemptions.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            count=Count('id'),
            points_spent=Sum('points_spent')
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'redemptions': trend['count'],
                'points_spent': trend['points_spent'] or 0
            }
            for trend in daily_trends
        ]
    except Exception:
        return []


def _get_points_trends(transactions, days) -> List[Dict]:
    """Get points trends."""
    try:
        from django.db.models import TruncDay
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_trends = transactions.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            earned=Sum('points_change', filter=Q(points_change__gt=0)),
            spent=Sum('points_change', filter=Q(points_change__lt=0))
        ).order_by('day')
        
        return [
            {
                'date': trend['day'].isoformat(),
                'points_earned': trend['earned'] or 0,
                'points_spent': abs(trend['spent'] or 0)
            }
            for trend in daily_trends
        ]
    except Exception:
        return []
