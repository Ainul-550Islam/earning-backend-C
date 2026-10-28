"""
api/adapters/gamification.py
Gamification adapter for earning backend platform
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
def get_user_profile(request):
    """Get user's gamification profile."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user's gamification data
        from gamification.models import UserProfile, UserLevel, UserBadge, UserStreak
        try:
            profile = UserProfile.objects.get(user=user, tenant_id=tenant_id)
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(
                user=user,
                tenant_id=tenant_id,
                level=1,
                experience_points=0,
                total_earnings=Decimal('0'),
                created_at=timezone.now()
            )
        
        # Get user's current level
        try:
            current_level = UserLevel.objects.get(level=profile.level, tenant_id=tenant_id)
        except UserLevel.DoesNotExist:
            current_level = UserLevel.objects.create(
                level=profile.level,
                name=f"Level {profile.level}",
                experience_required=profile.level * 100,
                tenant_id=tenant_id
            )
        
        # Get user's badges
        badges = UserBadge.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).select_related('badge').order_by('-earned_at')
        
        # Get user's current streak
        try:
            current_streak = UserStreak.objects.get(
                user=user,
                tenant_id=tenant_id,
                is_active=True
            )
        except UserStreak.DoesNotExist:
            current_streak = None
        
        profile_data = {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'level': {
                'current_level': profile.level,
                'current_level_name': current_level.name,
                'experience_points': profile.experience_points,
                'experience_to_next_level': current_level.experience_required - profile.experience_points,
                'progress_to_next_level': round((profile.experience_points / current_level.experience_required) * 100, 2) if current_level.experience_required > 0 else 100,
                'total_earnings': str(profile.total_earnings),
                'level_up_rewards': current_level.level_up_rewards,
            },
            'streak': {
                'current_streak': current_streak.current_streak if current_streak else 0,
                'longest_streak': current_streak.longest_streak if current_streak else 0,
                'streak_start_date': current_streak.start_date.isoformat() if current_streak else None,
                'last_activity_date': current_streak.last_activity_date.isoformat() if current_streak else None,
                'streak_multiplier': current_streak.multiplier if current_streak else 1.0,
            },
            'badges': [
                {
                    'id': badge.id,
                    'badge_id': user_badge.badge.id,
                    'badge_name': user_badge.badge.name,
                    'badge_description': user_badge.badge.description,
                    'badge_icon': user_badge.badge.icon,
                    'badge_type': user_badge.badge.badge_type,
                    'rarity': user_badge.badge.rarity,
                    'earned_at': user_badge.earned_at.isoformat(),
                    'points_value': user_badge.badge.points_value,
                    'is_equipped': user_badge.is_equipped,
                }
                for user_badge in badges
            ],
            'achievements': _get_user_achievements(user, tenant_id),
            'leaderboard_rank': _get_user_leaderboard_rank(user, tenant_id),
            'statistics': {
                'total_tasks_completed': profile.total_tasks_completed,
                'total_tasks_failed': profile.total_tasks_failed,
                'success_rate': round((profile.total_tasks_completed / max(profile.total_tasks_completed + profile.total_tasks_failed, 1)) * 100, 2),
                'average_completion_time': profile.average_completion_time_seconds,
                'total_time_spent': profile.total_time_spent_seconds,
                'favorite_category': profile.favorite_category,
                'most_completed_day': profile.most_completed_day,
            },
            'preferences': {
                'notifications_enabled': profile.notifications_enabled,
                'public_profile': profile.public_profile,
                'show_rankings': profile.show_rankings,
                'badge_display_preference': profile.badge_display_preference,
            }
        }
        
        return Response({
            'success': True,
            'data': profile_data,
            'message': 'Gamification profile retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[GamificationAdapter] Error getting user profile: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve gamification profile',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_leaderboard(request):
    """Get gamification leaderboard."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        leaderboard_type = request.GET.get('type', 'points')  # 'points', 'level', 'badges', 'streaks'
        period = request.GET.get('period', 'all')  # 'all', 'week', 'month', 'year'
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        
        # Get leaderboard data
        from gamification.models import UserProfile, UserLevel
        queryset = UserProfile.objects.filter(
            tenant_id=tenant_id
        ).select_related('user').order_by('-experience_points')
        
        # Apply period filter
        if period == 'week':
            queryset = queryset.filter(
                last_activity_date__gte=timezone.now() - timedelta(days=7)
            )
        elif period == 'month':
            queryset = queryset.filter(
                last_activity_date__gte=timezone.now() - timedelta(days=30)
            )
        elif period == 'year':
            queryset = queryset.filter(
                last_activity_date__gte=timezone.now() - timedelta(days=365)
            )
        
        # Paginate
        leaderboard_entries = queryset[offset:offset+limit]
        
        # Serialize leaderboard
        leaderboard_data = []
        for entry in leaderboard_entries:
            leaderboard_data.append({
                'rank': offset + list(leaderboard_entries).index(entry) + 1,
                'user': {
                    'id': entry.user.id,
                    'username': entry.user.username,
                    'first_name': entry.user.first_name,
                    'last_name': entry.user.last_name,
                    'avatar': getattr(entry.user, 'avatar', None),
                },
                'level': entry.level,
                'experience_points': entry.experience_points,
                'total_earnings': str(entry.total_earnings),
                'total_tasks_completed': entry.total_tasks_completed,
                'success_rate': round((entry.total_tasks_completed / max(entry.total_tasks_completed + entry.total_tasks_failed, 1)) * 100, 2),
                'current_streak': _get_user_current_streak(entry.user, tenant_id),
                'badges_count': UserBadge.objects.filter(
                    user=entry.user,
                    tenant_id=tenant_id
                ).count(),
                'achievements_count': _get_user_achievements_count(entry.user, tenant_id),
            })
        
        return Response({
            'success': True,
            'data': {
                'leaderboard_type': leaderboard_type,
                'period': period,
                'entries': leaderboard_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(leaderboard_data) == limit
                },
                'user_rank': _get_user_leaderboard_rank(request.user, tenant_id) if hasattr(request, 'user') else None,
                'summary': _get_leaderboard_summary(queryset)
            },
            'message': 'Leaderboard retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[GamificationAdapter] Error getting leaderboard: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve leaderboard',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_achievements(request):
    """Get available achievements and user's progress."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        category = request.GET.get('category')  # 'all', 'tasks', 'streaks', 'social', 'special'
        status = request.GET.get('status')  # 'all', 'unlocked', 'locked', 'in_progress'
        
        # Get achievements
        from gamification.models import Achievement, UserAchievement
        achievements = Achievement.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).order_by('category', 'points_value')
        
        # Apply category filter
        if category and category != 'all':
            achievements = achievements.filter(category=category)
        
        # Get user's achievement progress
        user_achievements = UserAchievement.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).select_related('achievement')
        
        # Build achievement data
        achievement_data = []
        for achievement in achievements:
            user_achievement = user_achievements.filter(achievement=achievement).first()
            
            achievement_data.append({
                'id': achievement.id,
                'name': achievement.name,
                'description': achievement.description,
                'category': achievement.category,
                'points_value': achievement.points_value,
                'badge_reward': {
                    'id': achievement.badge_reward.id,
                    'name': achievement.badge_reward.name,
                    'icon': achievement.badge_reward.icon,
                    'rarity': achievement.badge_reward.rarity,
                } if achievement.badge_reward else None,
                'requirements': achievement.requirements,
                'user_progress': {
                    'is_unlocked': user_achievement.is_unlocked if user_achievement else False,
                    'progress_percentage': user_achievement.progress_percentage if user_achievement else 0,
                    'current_progress': user_achievement.current_progress if user_achievement else 0,
                    'required_progress': achievement.requirements.get('required_progress', 100),
                    'unlocked_at': user_achievement.unlocked_at.isoformat() if user_achievement and user_achievement.is_unlocked else None,
                    'times_completed': user_achievement.times_completed if user_achievement else 0,
                },
                'is_hidden': achievement.is_hidden,
                'is_secret': achievement.is_secret,
                'difficulty': achievement.difficulty,
                'time_limit': achievement.time_limit_seconds,
                'created_at': achievement.created_at.isoformat(),
            })
        
        return Response({
            'success': True,
            'data': {
                'achievements': achievement_data,
                'filters': {
                    'category': category,
                    'status': status
                },
                'summary': {
                    'total_achievements': achievements.count(),
                    'unlocked_achievements': user_achievements.filter(is_unlocked=True).count(),
                    'in_progress_achievements': user_achievements.filter(is_unlocked=False, progress_percentage__gt=0).count(),
                    'total_points_possible': achievements.aggregate(total=Sum(F('points_value')))['total'] or 0,
                    'total_points_earned': user_achievements.filter(is_unlocked=True).aggregate(
                        total=Sum(F('achievement__points_value'))
                    )['total'] or 0,
                'completion_percentage': round((user_achievements.filter(is_unlocked=True).count() / max(achievements.count(), 1)) * 100, 2),
                'most_valuable_achievement': achievements.order_by('-points_value').first().name if achievements.exists() else None,
                'rarest_achievement': achievements.filter(rarity='legendary').first().name if achievements.filter(rarity='legendary').exists() else None,
                'user_rank': _get_user_achievement_rank(user, tenant_id),
                'next_achievement': _get_next_achievement(user, tenant_id),
                'achievement_streak': _get_user_achievement_streak(user, tenant_id),
                'recent_achievements': [
                    {
                        'achievement_id': ua.achievement.id,
                        'achievement_name': ua.achievement.name,
                        'unlocked_at': ua.unlocked_at.isoformat(),
                        'points_earned': ua.achievement.points_value,
                    }
                    for ua in user_achievements.filter(is_unlocked=True).order_by('-unlocked_at')[:5]
                ]
            }
        },
            'message': 'Achievements retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[GamificationAdapter] Error getting achievements: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve achievements',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_rewards(request):
    """Get available rewards and user's inventory."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        reward_type = request.GET.get('type')  # 'all', 'badges', 'titles', 'items', 'perks'
        status = request.GET.get('status')  # 'all', 'available', 'purchased', 'equipped'
        
        # Get rewards
        from gamification.models import Reward, UserReward
        rewards = Reward.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).order_by('category', 'points_cost')
        
        # Apply type filter
        if reward_type and reward_type != 'all':
            rewards = rewards.filter(reward_type=reward_type)
        
        # Get user's rewards
        user_rewards = UserReward.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).select_related('reward')
        
        # Build reward data
        reward_data = []
        for reward in rewards:
            user_reward = user_rewards.filter(reward=reward).first()
            
            reward_data.append({
                'id': reward.id,
                'name': reward.name,
                'description': reward.description,
                'category': reward.category,
                'reward_type': reward.reward_type,
                'points_cost': reward.points_cost,
                'real_money_cost': str(reward.real_money_cost) if reward.real_money_cost else None,
                'is_purchasable': reward.is_purchasable,
                'is_tradeable': reward.is_tradeable,
                'is_consumable': reward.is_consumable,
                'quantity': reward.quantity,
                'rarity': reward.rarity,
                'requirements': reward.requirements,
                'user_status': {
                    'is_owned': user_reward.is_owned if user_reward else False,
                    'is_equipped': user_reward.is_equipped if user_reward else False,
                    'quantity_owned': user_reward.quantity if user_reward else 0,
                    'purchased_at': user_reward.purchased_at.isoformat() if user_reward else None,
                    'expires_at': user_reward.expires_at.isoformat() if user_reward and user_reward.expires_at else None,
                    'times_used': user_reward.times_used if user_reward else 0,
                    'times_remaining': user_reward.times_remaining if user_reward else 0,
                },
                'media': {
                    'icon': reward.icon,
                    'image': reward.image,
                    'animation': reward.animation,
                    'sound_effect': reward.sound_effect,
                },
                'stats': {
                    'total_purchases': UserReward.objects.filter(reward=reward).count(),
                    'total_owners': UserReward.objects.filter(reward=reward).values('user').distinct().count(),
                    'popularity_score': reward.popularity_score,
                    'satisfaction_rating': reward.satisfaction_rating,
                },
                'created_at': reward.created_at.isoformat(),
                'updated_at': reward.updated_at.isoformat(),
            })
        
        return Response({
            'success': True,
            'data': {
                'rewards': reward_data,
                'filters': {
                    'type': reward_type,
                    'status': status
                },
                'summary': {
                    'total_rewards': rewards.count(),
                    'user_points_balance': _get_user_points_balance(user, tenant_id),
                    'user_rewards_count': user_rewards.count(),
                    'user_equipped_count': user_rewards.filter(is_equipped=True).count(),
                    'user_points_spent': _get_user_points_spent(user, tenant_id),
                    'most_valuable_reward': rewards.order_by('-points_cost').first().name if rewards.exists() else None,
                    'rarest_reward': rewards.filter(rarity='legendary').first().name if rewards.filter(rarity='legendary').exists() else None,
                    'next_affordable_reward': _get_next_affordable_reward(user, tenant_id),
                'user_inventory_value': _get_user_inventory_value(user, tenant_id),
                'recent_purchases': [
                    {
                        'reward_id': ur.reward.id,
                        'reward_name': ur.reward.name,
                        'points_cost': ur.reward.points_cost,
                        'purchased_at': ur.purchased_at.isoformat(),
                        'is_equipped': ur.is_equipped,
                    }
                    for ur in user_rewards.filter(is_purchased=True).order_by('-purchased_at')[:5]
                ]
            }
        },
            'message': 'Rewards retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[GamificationAdapter] Error getting rewards: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve rewards',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def purchase_reward(request, reward_id):
    """Purchase a reward."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get reward
        from gamification.models import Reward, UserReward
        try:
            reward = Reward.objects.get(
                id=reward_id,
                tenant_id=tenant_id,
                is_active=True,
                is_purchasable=True
            )
        except Reward.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Reward not found',
                'details': f'Reward with ID {reward_id} not found or not purchasable'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get user's points balance
        user_points = _get_user_points_balance(user, tenant_id)
        
        # Check if user can afford reward
        if user_points < reward.points_cost:
            return Response({
                'success': False,
                'error': 'Insufficient points',
                'details': f'You need {reward.points_cost} points but only have {user_points}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user already owns reward
        existing_reward = UserReward.objects.filter(
            user=user,
            reward=reward,
            tenant_id=tenant_id
        ).first()
        
        if existing_reward and not reward.is_consumable:
            return Response({
                'success': False,
                'error': 'Reward already owned',
                'details': 'You already own this reward'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check reward requirements
        if not _meets_reward_requirements(user, reward, tenant_id):
            return Response({
                'success': False,
                'error': 'Requirements not met',
                'details': 'You do not meet the requirements for this reward'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create user reward
        user_reward = UserReward.objects.create(
            user=user,
            reward=reward,
            quantity=1,
            points_spent=reward.points_cost,
            is_purchased=True,
            is_equipped=False,
            tenant_id=tenant_id,
            purchased_at=timezone.now()
        )
        
        # Deduct points from user
        _deduct_user_points(user, reward.points_cost, tenant_id, f'reward_purchase_{reward_id}')
        
        # Emit reward purchase event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('gamification.reward_purchased', {
            'user_id': user.id,
            'reward_id': reward_id,
            'points_spent': reward.points_cost,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'user_reward_id': user_reward.id,
                'reward': {
                    'id': reward.id,
                    'name': reward.name,
                    'points_cost': reward.points_cost,
                    'reward_type': reward.reward_type,
                },
                'points_remaining': user_points - reward.points_cost,
                'purchase_date': user_reward.purchased_at.isoformat(),
                'is_equipped': user_reward.is_equipped,
                'expires_at': user_reward.expires_at.isoformat() if user_reward.expires_at else None,
            },
            'message': 'Reward purchased successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[GamificationAdapter] Error purchasing reward: {e}")
        return Response({
            'success': False,
            'error': 'Failed to purchase reward',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def equip_reward(request, user_reward_id):
    """Equip a reward."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user reward
        from gamification.models import UserReward
        try:
            user_reward = UserReward.objects.get(
                id=user_reward_id,
                user=user,
                tenant_id=tenant_id,
                is_purchased=True
            )
        except UserReward.DoesNotExist:
            return Response({
                'success': False,
                'error': 'User reward not found',
                'details': f'User reward with ID {user_reward_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if reward is equippable
        if not user_reward.reward.is_equippable:
            return Response({
                'success': False,
                'error': 'Reward not equippable',
                'details': 'This reward cannot be equipped'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Unequip other rewards in same category
        UserReward.objects.filter(
            user=user,
            tenant_id=tenant_id,
            reward__reward_type=user_reward.reward.reward_type,
            is_equipped=True
        ).update(is_equipped=False)
        
        # Equip the reward
        user_reward.is_equipped = True
        user_reward.equipped_at = timezone.now()
        user_reward.save()
        
        return Response({
            'success': True,
            'data': {
                'user_reward_id': user_reward.id,
                'reward': {
                    'id': user_reward.reward.id,
                    'name': user_reward.reward.name,
                    'reward_type': user_reward.reward.reward_type,
                },
                'equipped_at': user_reward.equipped_at.isoformat(),
                'unequipped_rewards': _get_unequipped_rewards(user, tenant_id, user_reward.reward.reward_type),
            },
            'message': 'Reward equipped successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[GamificationAdapter] Error equipping reward: {e}")
        return Response({
            'success': False,
            'error': 'Failed to equip reward',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _get_user_current_streak(user, tenant_id) -> int:
    """Get user's current streak."""
    try:
        from gamification.models import UserStreak
        streak = UserStreak.objects.filter(
            user=user,
            tenant_id=tenant_id,
            is_active=True
        ).first()
        return streak.current_streak if streak else 0
    except Exception:
        return 0


def _get_user_leaderboard_rank(user, tenant_id) -> int:
    """Get user's ranking on leaderboard."""
    try:
        from gamification.models import UserProfile
        user_profile = UserProfile.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).first()
        
        if not user_profile:
            return 0
        
        higher_profiles = UserProfile.objects.filter(
            tenant_id=tenant_id,
            experience_points__gt=user_profile.experience_points
        ).count()
        
        return higher_profiles + 1
    except Exception:
        return 0


def _get_user_achievements(user, tenant_id) -> List[Dict]:
    """Get user's achievements."""
    try:
        from gamification.models import UserAchievement
        user_achievements = UserAchievement.objects.filter(
            user=user,
            tenant_id=tenant_id,
            is_unlocked=True
        ).select_related('achievement').order_by('-unlocked_at')
        
        return [
            {
                'achievement_id': ua.achievement.id,
                'achievement_name': ua.achievement.name,
                'unlocked_at': ua.unlocked_at.isoformat(),
                'points_value': ua.achievement.points_value,
                'badge_reward': ua.achievement.badge_reward.name if ua.achievement.badge_reward else None,
            }
            for ua in user_achievements
        ]
    except Exception:
        return []


def _get_user_achievements_count(user, tenant_id) -> int:
    """Get count of user's achievements."""
    try:
        from gamification.models import UserAchievement
        return UserAchievement.objects.filter(
            user=user,
            tenant_id=tenant_id,
            is_unlocked=True
        ).count()
    except Exception:
        return 0


def _get_leaderboard_summary(queryset) -> Dict:
    """Get leaderboard summary statistics."""
    try:
        total_users = queryset.count()
        
        if total_users == 0:
            return {}
        
        top_user = queryset.first()
        average_points = queryset.aggregate(
            avg_points=Avg(F('experience_points'))
        )['avg_points'] or 0
        
        return {
            'total_users': total_users,
            'top_score': top_user.experience_points if top_user else 0,
            'average_score': round(average_points, 2),
            'score_distribution': {
                'beginner': queryset.filter(experience_points__lt=500).count(),
                'intermediate': queryset.filter(experience_points__gte=500, experience_points__lt=1500).count(),
                'advanced': queryset.filter(experience_points__gte=1500, experience_points__lt=3000).count(),
                'expert': queryset.filter(experience_points__gte=3000).count(),
            }
        }
    except Exception:
        return {}


def _get_user_points_balance(user, tenant_id) -> int:
    """Get user's points balance."""
    try:
        from gamification.models import UserProfile
        profile = UserProfile.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).first()
        return profile.experience_points if profile else 0
    except Exception:
        return 0


def _get_user_points_spent(user, tenant_id) -> int:
    """Get total points spent by user."""
    try:
        from gamification.models import UserReward
        return UserReward.objects.filter(
            user=user,
            tenant_id=tenant_id,
            is_purchased=True
        ).aggregate(total=Sum(F('points_spent')))['total'] or 0
    except Exception:
        return 0


def _meets_reward_requirements(user, reward, tenant_id) -> bool:
    """Check if user meets reward requirements."""
    try:
        requirements = reward.requirements or {}
        
        # Check level requirement
        if 'min_level' in requirements:
            from gamification.models import UserProfile
            user_profile = UserProfile.objects.filter(
                user=user,
                tenant_id=tenant_id
            ).first()
            if not user_profile or user_profile.level < requirements['min_level']:
                return False
        
        # Check achievement requirements
        if 'required_achievements' in requirements:
            from gamification.models import UserAchievement
            required_achievements = requirements['required_achievements']
            user_achievements = UserAchievement.objects.filter(
                user=user,
                tenant_id=tenant_id,
                is_unlocked=True,
                achievement__name__in=required_achievements
            ).count()
            if user_achievements < len(required_achievements):
                return False
        
        # Check streak requirement
        if 'min_streak' in requirements:
            current_streak = _get_user_current_streak(user, tenant_id)
            if current_streak < requirements['min_streak']:
                return False
        
        return True
    except Exception:
        return False


def _get_next_achievement(user, tenant_id) -> Optional[Dict]:
    """Get next achievement user can unlock."""
    try:
        from gamification.models import Achievement, UserAchievement
        user_achievements = UserAchievement.objects.filter(
            user=user,
            tenant_id=tenant_id,
            is_unlocked=True
        ).values_list('achievement', flat=True)
        
        # Get next achievement
        next_achievement = Achievement.objects.filter(
            tenant_id=tenant_id,
            is_active=True,
            id__notin=user_achievements
        ).order_by('points_value').first()
        
        if not next_achievement:
            return None
        
        return {
            'id': next_achievement.id,
            'name': next_achievement.name,
            'description': next_achievement.description,
            'points_value': next_achievement.points_value,
            'requirements': next_achievement.requirements,
            'progress_percentage': _calculate_achievement_progress(user, next_achievement, tenant_id),
        }
    except Exception:
        return None


def _get_next_affordable_reward(user, tenant_id) -> Optional[Dict]:
    """Get next reward user can afford."""
    try:
        from gamification.models import Reward
        user_points = _get_user_points_balance(user, tenant_id)
        
        next_reward = Reward.objects.filter(
            tenant_id=tenant_id,
            is_active=True,
            is_purchasable=True,
            points_cost__lte=user_points
        ).order_by('points_cost').first()
        
        if not next_reward:
            return None
        
        return {
            'id': next_reward.id,
            'name': next_reward.name,
            'points_cost': next_reward.points_cost,
            'reward_type': next_reward.reward_type,
            'can_afford': True,
        }
    except Exception:
        return None


def _calculate_achievement_progress(user, achievement, tenant_id) -> float:
    """Calculate progress percentage for achievement."""
    try:
        from gamification.models import UserAchievement
        user_achievement = UserAchievement.objects.filter(
            user=user,
            achievement=achievement,
            tenant_id=tenant_id
        ).first()
        
        if not user_achievement:
            return 0.0
        
        return user_achievement.progress_percentage
    except Exception:
        return 0.0


def _get_user_achievement_streak(user, tenant_id) -> int:
    """Get user's achievement streak."""
    try:
        from gamification.models import UserAchievement
        last_week = timezone.now() - timedelta(days=7)
        
        recent_achievements = UserAchievement.objects.filter(
            user=user,
            tenant_id=tenant_id,
            is_unlocked=True,
            unlocked_at__gte=last_week
        ).order_by('-unlocked_at')
        
        if not recent_achievements.exists():
            return 0
        
        # Calculate consecutive days with achievements
        streak = 0
        current_date = timezone.now().date()
        
        for i in range(7):
            check_date = current_date - timedelta(days=i)
            day_achievements = recent_achievements.filter(
                unlocked_at__date=check_date
            ).count()
            
            if day_achievements > 0:
                streak += 1
            else:
                break
        
        return streak
    except Exception:
        return 0


def _get_user_inventory_value(user, tenant_id) -> Decimal:
    """Get total value of user's inventory."""
    try:
        from gamification.models import UserReward
        return UserReward.objects.filter(
            user=user,
            tenant_id=tenant_id,
            is_purchased=True,
            expires_at__gt=timezone.now()
        ).aggregate(
            total_value=Sum(F('reward__points_cost'))
        )['total_value'] or Decimal('0')
    except Exception:
        return Decimal('0')


def _get_unequipped_rewards(user, tenant_id, reward_type) -> List[Dict]:
    """Get recently unequipped rewards in same category."""
    try:
        from gamification.models import UserReward
        unequipped = UserReward.objects.filter(
            user=user,
            tenant_id=tenant_id,
            reward__reward_type=reward_type,
            is_equipped=False,
            is_purchased=True
        ).select_related('reward').order_by('-equipped_at')[:5]
        
        return [
            {
                'user_reward_id': ur.id,
                'reward_id': ur.reward.id,
                'reward_name': ur.reward.name,
                'unequipped_at': ur.equipped_at.isoformat() if ur.equipped_at else None,
            }
            for ur in unequipped
        ]
    except Exception:
        return []
