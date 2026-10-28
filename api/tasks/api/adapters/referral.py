"""
api/adapters/referral.py
Referral adapter for earning backend platform
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
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def referral_profile(request):
    """Get user's referral profile and statistics."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get referral data
        from referrals.models import Referral, ReferralReward
        referrals = Referral.objects.filter(
            referrer=user,
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Calculate referral statistics
        total_referrals = referrals.count()
        active_referrals = referrals.filter(
            referred_user__is_active=True
        ).count()
        
        # Calculate total referral earnings
        referral_earnings = ReferralReward.objects.filter(
            referrer=user,
            tenant_id=tenant_id
        ).aggregate(
            total_earnings=Sum(F('amount')),
            total_rewards=Count('id')
        )
        
        # Get referral code
        referral_code = _get_or_create_referral_code(user)
        
        referral_data = {
            'user_id': user.id,
            'tenant_id': tenant_id,
            'referral_code': referral_code,
            'statistics': {
                'total_referrals': total_referrals,
                'active_referrals': active_referrals,
                'conversion_rate': round((active_referrals / max(total_referrals, 1)) * 100, 2),
                'total_earnings': str(referral_earnings['total_earnings'] or Decimal('0')),
                'total_rewards': referral_earnings['total_rewards'] or 0,
                'pending_rewards': ReferralReward.objects.filter(
                    referrer=user,
                    status='pending',
                    tenant_id=tenant_id
                ).count(),
                'paid_rewards': ReferralReward.objects.filter(
                    referrer=user,
                    status='paid',
                    tenant_id=tenant_id
                ).count()
            },
            'referral_tiers': _get_referral_tiers(user),
            'recent_referrals': [
                {
                    'id': referral.id,
                    'referred_user': {
                        'id': referral.referred_user.id,
                        'username': referral.referred_user.username,
                        'email': referral.referred_user.email,
                        'date_joined': referral.referred_user.date_joined.isoformat(),
                        'is_active': referral.referred_user.is_active,
                    },
                    'status': referral.status,
                    'created_at': referral.created_at.isoformat(),
                    'completed_at': referral.completed_at.isoformat() if referral.completed_at else None,
                    'reward_amount': str(referral.reward_amount) if referral.reward_amount else '0.00',
                    'reward_status': referral.reward_status,
                }
                for referral in referrals[:10]
            ],
            'referral_link': _generate_referral_link(user, referral_code),
            'sharing_options': _get_sharing_options(user, referral_code)
        }
        
        return Response({
            'success': True,
            'data': referral_data,
            'message': 'Referral profile retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[ReferralAdapter] Error getting referral profile: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve referral profile',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_referral(request):
    """Create a referral for new user."""
    try:
        data = request.data
        referral_code = data.get('referral_code')
        email = data.get('email')
        username = data.get('username')
        
        if not referral_code:
            return Response({
                'success': False,
                'error': 'Referral code required',
                'details': 'Please provide a referral code'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get referral code
        from referrals.models import ReferralCode
        try:
            ref_code = ReferralCode.objects.get(
                code=referral_code,
                is_active=True,
                expires_at__gte=timezone.now()
            )
        except ReferralCode.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Invalid referral code',
                'details': 'Referral code not found or expired'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            return Response({
                'success': False,
                'error': 'User already exists',
                'details': 'An account with this email already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create user account (this would typically be handled by user registration)
        # For this example, we'll assume user is already created and authenticated
        user = request.user
        
        # Create referral record
        from referrals.models import Referral
        referral = Referral.objects.create(
            referrer=ref_code.user,
            referred_user=user,
            referral_code=ref_code,
            status='pending',
            created_at=timezone.now(),
            tenant_id=getattr(request, 'tenant_id', None)
        )
        
        # Emit referral created event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('referral.created', {
            'referrer_id': ref_code.user.id,
            'referred_user_id': user.id,
            'referral_code': referral_code,
            'referral_id': referral.id,
            'tenant_id': getattr(request, 'tenant_id', None)
        })
        
        return Response({
            'success': True,
            'data': {
                'referral_id': referral.id,
                'referrer': {
                    'id': ref_code.user.id,
                    'username': ref_code.user.username,
                },
                'status': 'pending',
                'created_at': referral.created_at.isoformat(),
                'next_steps': [
                    'Complete profile setup',
                    'Complete KYC verification',
                    'Complete first task'
                ]
            },
            'message': 'Referral created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[ReferralAdapter] Error creating referral: {e}")
        return Response({
            'success': False,
            'error': 'Failed to create referral',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def referral_history(request):
    """Get user's referral history."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        
        # Get referrals
        from referrals.models import Referral
        referrals = Referral.objects.filter(
            referrer=user,
            tenant_id=tenant_id
        ).order_by('-created_at')[offset:offset+limit]
        
        # Get referral rewards
        from referrals.models import ReferralReward
        rewards = ReferralReward.objects.filter(
            referrer=user,
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        referral_data = {
            'referrals': [
                {
                    'id': referral.id,
                    'referred_user': {
                        'id': referral.referred_user.id,
                        'username': referral.referred_user.username,
                        'email': referral.referred_user.email,
                        'date_joined': referral.referred_user.date_joined.isoformat(),
                    },
                    'status': referral.status,
                    'created_at': referral.created_at.isoformat(),
                    'completed_at': referral.completed_at.isoformat() if referral.completed_at else None,
                    'reward_amount': str(referral.reward_amount) if referral.reward_amount else '0.00',
                    'reward_status': referral.reward_status,
                    'completion_requirements': referral.completion_requirements,
                }
                for referral in referrals
            ],
            'rewards': [
                {
                    'id': reward.id,
                    'referral_id': reward.referral.id,
                    'amount': str(reward.amount),
                    'reward_type': reward.reward_type,
                    'status': reward.status,
                    'created_at': reward.created_at.isoformat(),
                    'paid_at': reward.paid_at.isoformat() if reward.paid_at else None,
                    'description': reward.description,
                }
                for reward in rewards
            ],
            'pagination': {
                'limit': limit,
                'offset': offset,
                'total': Referral.objects.filter(referrer=user, tenant_id=tenant_id).count(),
                'has_more': len(referrals) == limit
            },
            'summary': {
                'total_referrals': Referral.objects.filter(referrer=user, tenant_id=tenant_id).count(),
                'completed_referrals': Referral.objects.filter(
                    referrer=user,
                    status='completed',
                    tenant_id=tenant_id
                ).count(),
                'total_earnings': str(rewards.aggregate(
                    total=Sum(F('amount'))
                )['total'] or Decimal('0')),
                'pending_earnings': str(rewards.filter(
                    status='pending',
                    tenant_id=tenant_id
                ).aggregate(total=Sum(F('amount')))['total'] or Decimal('0')),
                'paid_earnings': str(rewards.filter(
                    status='paid',
                    tenant_id=tenant_id
                ).aggregate(total=Sum(F('amount')))['total'] or Decimal('0'))
            }
        }
        
        return Response({
            'success': True,
            'data': referral_data,
            'message': 'Referral history retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[ReferralAdapter] Error getting referral history: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve referral history',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def referral_leaderboard(request):
    """Get referral leaderboard."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        limit = int(request.GET.get('limit', 50))
        period = request.GET.get('period', 'all')  # 'all', 'month', 'year'
        
        # Get date range
        start_date = None
        if period == 'month':
            start_date = timezone.now() - timedelta(days=30)
        elif period == 'year':
            start_date = timezone.now() - timedelta(days=365)
        
        # Get top referrers
        from referrals.models import Referral
        from django.db.models import Q
        queryset = Referral.objects.filter(
            tenant_id=tenant_id,
            status='completed'
        )
        
        if start_date:
            queryset = queryset.filter(completed_at__gte=start_date)
        
        leaderboard = queryset.values('referrer_id').annotate(
            total_referrals=Count('id'),
            total_earnings=Sum(F('reward_amount'))
        ).order_by('-total_referrals')[:limit]
        
        # Add user details
        leaderboard_data = []
        for entry in leaderboard:
            try:
                referrer_user = User.objects.get(id=entry['referrer_id'])
                leaderboard_data.append({
                    'rank': len(leaderboard_data) + 1,
                    'user': {
                        'id': referrer_user.id,
                        'username': referrer_user.username,
                        'first_name': referrer_user.first_name,
                        'last_name': referrer_user.last_name,
                        'avatar': getattr(referrer_user, 'avatar', None),
                    },
                    'statistics': {
                        'total_referrals': entry['total_referrals'],
                        'total_earnings': str(entry['total_earnings'] or Decimal('0')),
                        'avg_earnings_per_referral': str(
                            (entry['total_earnings'] or Decimal('0')) / 
                            max(entry['total_referrals'], 1)
                        ),
                    }
                })
            except User.DoesNotExist:
                continue
        
        return Response({
            'success': True,
            'data': {
                'leaderboard': leaderboard_data,
                'period': period,
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': timezone.now().isoformat(),
                'user_rank': _get_user_rank(request.user.id, leaderboard_data)
            },
            'message': 'Referral leaderboard retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[ReferralAdapter] Error getting referral leaderboard: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve referral leaderboard',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _get_or_create_referral_code(user) -> str:
    """Get or create referral code for user."""
    try:
        from referrals.models import ReferralCode
        code, created = ReferralCode.objects.get_or_create(
            user=user,
            defaults={
                'code': _generate_referral_code(user),
                'is_active': True,
                'expires_at': timezone.now() + timedelta(days=365),
                'created_at': timezone.now()
            }
        )
        return code.code
    except Exception:
        return f"REF{user.id:06d}"


def _generate_referral_code(user) -> str:
    """Generate unique referral code."""
    import random
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def _generate_referral_link(user, referral_code) -> str:
    """Generate referral link for user."""
    tenant_id = getattr(user, 'tenant_id', None)
    base_url = cache.get(f'tenant_base_url_{tenant_id}', 'https://earningapp.com')
    return f"{base_url}/register?ref={referral_code}&tenant={tenant_id}"


def _get_sharing_options(user, referral_code) -> Dict:
    """Get sharing options for referral."""
    referral_link = _generate_referral_link(user, referral_code)
    
    return {
        'direct_link': referral_link,
        'social_media': {
            'twitter': f"https://twitter.com/intent/tweet?text=Join%20me%20on%20EarningApp&url={referral_link}",
            'facebook': f"https://www.facebook.com/sharer/sharer.php?u={referral_link}",
            'linkedin': f"https://www.linkedin.com/sharing/share-offsite/?url={referral_link}",
            'whatsapp': f"https://wa.me/?text=Join%20me%20on%20EarningApp%20{referral_link}",
        },
        'email': {
            'subject': 'Join me on EarningApp',
            'body': f'Hi! I wanted to invite you to join EarningApp. Use my referral link: {referral_link}',
        },
        'qr_code': _generate_qr_code(referral_link)
    }


def _generate_qr_code(url) -> str:
    """Generate QR code for referral link."""
    try:
        import qrcode
        import io
        import base64
        
        qr = qrcode.QRCode(url)
        qr_image = qr.make_image()
        
        buffer = io.BytesIO()
        qr_image.save(buffer, format='PNG')
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return qr_base64
    except Exception:
        return ""


def _get_referral_tiers(user) -> List[Dict]:
    """Get referral tiers for user."""
    try:
        # This would typically come from tenant settings
        # For now, return default tiers
        return [
            {
                'tier': 1,
                'name': 'Bronze',
                'min_referrals': 1,
                'max_referrals': 5,
                'reward_per_referral': '1.00',
                'bonus_reward': '0.00',
                'current_referrals': cache.get(f'referral_count_{user.id}', 0),
                'is_achieved': cache.get(f'referral_count_{user.id}', 0) >= 1,
                'next_tier_progress': min(cache.get(f'referral_count_{user.id}', 0) / 5, 1.0)
            },
            {
                'tier': 2,
                'name': 'Silver',
                'min_referrals': 6,
                'max_referrals': 15,
                'reward_per_referral': '1.50',
                'bonus_reward': '5.00',
                'current_referrals': cache.get(f'referral_count_{user.id}', 0),
                'is_achieved': cache.get(f'referral_count_{user.id}', 0) >= 6,
                'next_tier_progress': min(max(cache.get(f'referral_count_{user.id}', 0) - 5, 0) / 10, 1.0)
            },
            {
                'tier': 3,
                'name': 'Gold',
                'min_referrals': 16,
                'max_referrals': 999,
                'reward_per_referral': '2.00',
                'bonus_reward': '20.00',
                'current_referrals': cache.get(f'referral_count_{user.id}', 0),
                'is_achieved': cache.get(f'referral_count_{user.id}', 0) >= 16,
                'next_tier_progress': min(max(cache.get(f'referral_count_{user.id}', 0) - 15, 0) / 50, 1.0)
            }
        ]
    except Exception:
        return []


def _get_user_rank(user_id: int, leaderboard: List[Dict]) -> int:
    """Get user's rank in leaderboard."""
    for i, entry in enumerate(leaderboard):
        if entry['user']['id'] == user_id:
            return i + 1
    return 0
