"""
api/adapters/promotions.py
Promotions adapter for earning backend platform
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
def get_promotions(request):
    """Get available promotions for user."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        promotion_type = request.GET.get('type')  # 'all', 'bonus', 'referral', 'seasonal', 'limited'
        status = request.GET.get('status')  # 'active', 'upcoming', 'expired', 'claimed'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get user context for filtering
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        # Get promotions
        from promotions.models import Promotion
        queryset = Promotion.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).order_by('-created_at')
        
        # Apply filters
        if promotion_type and promotion_type != 'all':
            queryset = queryset.filter(promotion_type=promotion_type)
        if status and status != 'all':
            if status == 'active':
                queryset = queryset.filter(
                    start_date__lte=timezone.now(),
                    end_date__gte=timezone.now()
                )
            elif status == 'upcoming':
                queryset = queryset.filter(start_date__gt=timezone.now())
            elif status == 'expired':
                queryset = queryset.filter(end_date__lt=timezone.now())
            elif status == 'claimed':
                queryset = queryset.filter(
                    promotionclaim__user=user,
                    promotionclaim__status='claimed'
                )
        
        # Apply user eligibility filters
        queryset = _apply_user_eligibility_filters(queryset, user, ctx)
        
        # Paginate
        promotions = queryset[offset:offset+limit]
        
        # Serialize promotions
        promotion_data = []
        for promotion in promotions:
            promotion_data.append({
                'id': promotion.id,
                'title': promotion.title,
                'description': promotion.description,
                'promotion_type': promotion.promotion_type,
                'status': _get_promotion_status(promotion, user),
                'start_date': promotion.start_date.isoformat(),
                'end_date': promotion.end_date.isoformat(),
                'is_featured': promotion.is_featured,
                'reward': {
                    'type': promotion.reward_type,
                    'amount': str(promotion.reward_amount),
                    'currency': promotion.currency,
                    'bonus_multiplier': promotion.bonus_multiplier,
                },
                'requirements': promotion.requirements,
                'conditions': promotion.conditions,
                'usage_limits': promotion.usage_limits,
                'user_eligibility': {
                    'is_eligible': _is_user_eligible(promotion, user, ctx),
                    'eligibility_reason': _get_eligibility_reason(promotion, user, ctx),
                    'user_status': _get_user_promotion_status(promotion, user),
                },
                'media': {
                    'banner_image': promotion.banner_image,
                    'hero_image': promotion.hero_image,
                    'gallery_images': promotion.gallery_images,
                },
                'metadata': promotion.metadata,
                'created_at': promotion.created_at.isoformat(),
                'updated_at': promotion.updated_at.isoformat(),
                'tenant_id': tenant_id
            })
        
        return Response({
            'success': True,
            'data': {
                'promotions': promotion_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(promotion_data) == limit
                },
                'filters': {
                    'type': promotion_type,
                    'status': status
                },
                'summary': _get_promotions_summary(queryset, user)
            },
            'message': 'Promotions retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[PromotionsAdapter] Error getting promotions: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve promotions',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_promotion_details(request, promotion_id):
    """Get detailed promotion information."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get promotion
        from promotions.models import Promotion
        try:
            promotion = Promotion.objects.get(
                id=promotion_id,
                tenant_id=tenant_id,
                is_active=True
            )
        except Promotion.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Promotion not found',
                'details': f'Promotion with ID {promotion_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get user context
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        # Get user's claim history
        from promotions.models import PromotionClaim
        user_claims = PromotionClaim.objects.filter(
            user=user,
            promotion=promotion
        ).order_by('-created_at')
        
        # Build detailed promotion data
        promotion_data = {
            'id': promotion.id,
            'title': promotion.title,
            'description': promotion.description,
            'promotion_type': promotion.promotion_type,
            'status': _get_promotion_status(promotion, user),
            'start_date': promotion.start_date.isoformat(),
            'end_date': promotion.end_date.isoformat(),
            'is_featured': promotion.is_featured,
            'reward': {
                'type': promotion.reward_type,
                'amount': str(promotion.reward_amount),
                'currency': promotion.currency,
                'bonus_multiplier': promotion.bonus_multiplier,
                'estimated_value': str(promotion.reward_amount * promotion.bonus_multiplier),
            },
            'requirements': promotion.requirements,
            'conditions': promotion.conditions,
            'usage_limits': promotion.usage_limits,
            'user_eligibility': {
                'is_eligible': _is_user_eligible(promotion, user, ctx),
                'eligibility_reason': _get_eligibility_reason(promotion, user, ctx),
                'user_status': _get_user_promotion_status(promotion, user),
                'remaining_claims': _get_remaining_claims(promotion, user),
                'next_claim_time': _get_next_claim_time(promotion, user),
            },
            'media': {
                'banner_image': promotion.banner_image,
                'hero_image': promotion.hero_image,
                'gallery_images': promotion.gallery_images,
                'video_url': promotion.video_url,
            },
            'statistics': {
                'total_claims': promotion.total_claims,
                'unique_claimants': promotion.unique_claimants,
                'average_claim_value': str(promotion.average_claim_value),
                'conversion_rate': promotion.conversion_rate,
                'popularity_score': promotion.popularity_score,
            },
            'user_claims': [
                {
                    'id': claim.id,
                    'status': claim.status,
                    'reward_awarded': str(claim.reward_awarded) if claim.reward_awarded else '0.00',
                    'created_at': claim.created_at.isoformat(),
                    'processed_at': claim.processed_at.isoformat() if claim.processed_at else None,
                    'metadata': claim.metadata,
                }
                for claim in user_claims[:10]
            ],
            'metadata': promotion.metadata,
            'created_at': promotion.created_at.isoformat(),
            'updated_at': promotion.updated_at.isoformat(),
            'tenant_id': tenant_id
        }
        
        return Response({
            'success': True,
            'data': promotion_data,
            'message': 'Promotion details retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[PromotionsAdapter] Error getting promotion details: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve promotion details',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def claim_promotion(request, promotion_id):
    """Claim a promotion."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get promotion
        from promotions.models import Promotion
        try:
            promotion = Promotion.objects.get(
                id=promotion_id,
                tenant_id=tenant_id,
                is_active=True
            )
        except Promotion.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Promotion not found',
                'details': f'Promotion with ID {promotion_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get user context
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        # Check eligibility
        if not _is_user_eligible(promotion, user, ctx):
            return Response({
                'success': False,
                'error': 'Not eligible for promotion',
                'details': _get_eligibility_reason(promotion, user, ctx)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check claim limits
        if not _can_claim_promotion(promotion, user):
            return Response({
                'success': False,
                'error': 'Claim limit exceeded',
                'details': 'You have reached the maximum number of claims for this promotion'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create promotion claim
        from promotions.models import PromotionClaim
        claim = PromotionClaim.objects.create(
            user=user,
            promotion=promotion,
            status='pending',
            reward_awarded=promotion.reward_amount * promotion.bonus_multiplier,
            metadata=data.get('metadata', {}),
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Process claim
        claim_result = _process_promotion_claim(claim, user, promotion)
        
        # Update promotion statistics
        if claim_result['success']:
            promotion.total_claims += 1
            if not PromotionClaim.objects.filter(
                user=user,
                promotion=promotion,
                status='claimed'
            ).exclude(id=claim.id).exists():
                promotion.unique_claimants += 1
            promotion.save()
        
        # Emit claim event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('promotion.claimed', {
            'user_id': user.id,
            'promotion_id': promotion_id,
            'claim_id': claim.id,
            'reward_awarded': str(claim_result['reward_awarded']),
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'claim_id': claim.id,
                'promotion_id': promotion_id,
                'status': claim_result['status'],
                'reward_awarded': str(claim_result['reward_awarded']),
                'processed_at': claim_result['processed_at'],
                'message': claim_result['message'],
                'next_eligible_claim': _get_next_claim_time(promotion, user)
            },
            'message': 'Promotion claimed successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[PromotionsAdapter] Error claiming promotion: {e}")
        return Response({
            'success': False,
            'error': 'Failed to claim promotion',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_promotion_history(request):
    """Get user's promotion claim history."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        status = request.GET.get('status')  # 'all', 'pending', 'claimed', 'rejected'
        
        # Get promotion claims
        from promotions.models import PromotionClaim
        queryset = PromotionClaim.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply status filter
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        
        # Paginate
        claims = queryset[offset:offset+limit]
        
        # Serialize claims
        claim_data = []
        for claim in claims:
            claim_data.append({
                'id': claim.id,
                'promotion': {
                    'id': claim.promotion.id,
                    'title': claim.promotion.title,
                    'promotion_type': claim.promotion.promotion_type,
                    'reward_type': claim.promotion.reward_type,
                },
                'status': claim.status,
                'reward_awarded': str(claim.reward_awarded) if claim.reward_awarded else '0.00',
                'created_at': claim.created_at.isoformat(),
                'processed_at': claim.processed_at.isoformat() if claim.processed_at else None,
                'metadata': claim.metadata,
                'rejection_reason': claim.rejection_reason,
                'tenant_id': tenant_id
            })
        
        return Response({
            'success': True,
            'data': {
                'claims': claim_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(claim_data) == limit
                },
                'filters': {
                    'status': status
                },
                'summary': _get_claim_summary(queryset)
            },
            'message': 'Promotion history retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[PromotionsAdapter] Error getting promotion history: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve promotion history',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_promotion_analytics(request):
    """Get promotion analytics for admin."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get promotion analytics
        from promotions.models import Promotion, PromotionClaim
        promotions = Promotion.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=start_date
        )
        
        claims = PromotionClaim.objects.filter(
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
            'promotion_metrics': {
                'total_promotions': promotions.count(),
                'active_promotions': promotions.filter(
                    start_date__lte=timezone.now(),
                    end_date__gte=timezone.now()
                ).count(),
                'featured_promotions': promotions.filter(is_featured=True).count(),
                'promotion_types': list(promotions.values_list('promotion_type', flat=True).distinct()),
            },
            'claim_metrics': {
                'total_claims': claims.count(),
                'successful_claims': claims.filter(status='claimed').count(),
                'pending_claims': claims.filter(status='pending').count(),
                'rejected_claims': claims.filter(status='rejected').count(),
                'total_rewards_awarded': str(claims.filter(
                    status='claimed'
                ).aggregate(total=Sum(F('reward_awarded')))['total'] or Decimal('0')),
                'average_reward_per_claim': str(claims.filter(
                    status='claimed'
                ).aggregate(avg_reward=Avg(F('reward_awarded')))['avg_reward'] or Decimal('0')),
                'claim_conversion_rate': round((claims.filter(status='claimed').count() / max(claims.count(), 1)) * 100, 2),
            },
            'top_performing_promotions': [
                {
                    'id': promotion.id,
                    'title': promotion.title,
                    'total_claims': PromotionClaim.objects.filter(
                        promotion=promotion,
                        status='claimed'
                    ).count(),
                    'total_rewards': str(PromotionClaim.objects.filter(
                        promotion=promotion,
                        status='claimed'
                    ).aggregate(total=Sum(F('reward_awarded')))['total'] or Decimal('0')),
                    'conversion_rate': promotion.conversion_rate,
                    'popularity_score': promotion.popularity_score,
                }
                for promotion in promotions.annotate(
                    claim_count=Count('promotionclaim')
                ).filter(claim_count__gt=0).order_by('-claim_count')[:10]
            ],
            'daily_trends': _get_daily_claim_trends(claims, days),
            'user_engagement': _get_promotion_user_engagement(claims),
        }
        
        return Response({
            'success': True,
            'data': analytics_data,
            'message': 'Promotion analytics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[PromotionsAdapter] Error getting promotion analytics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve promotion analytics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _apply_user_eligibility_filters(queryset, user, ctx) -> Any:
    """Apply user eligibility filters to promotion queryset."""
    # Filter by user level
    user_level = getattr(user, 'level', 1)
    queryset = queryset.filter(
        requirements__min_user_level__lte=user_level
    )
    
    # Filter by KYC tier
    if ctx.kyc_tier in ['standard', 'full']:
        queryset = queryset.filter(
            requirements__min_kyc_tier__in=[ctx.kyc_tier, 'none']
        )
    
    # Filter by account age
    account_age_days = ctx.account_age_days
    queryset = queryset.filter(
        requirements__min_account_age_days__lte=account_age_days
    )
    
    # Filter by wallet balance
    if ctx.wallet_balance:
        queryset = queryset.filter(
            requirements__min_wallet_balance__lte=ctx.wallet_balance
        )
    
    return queryset


def _is_user_eligible(promotion, user, ctx) -> bool:
    """Check if user is eligible for promotion."""
    try:
        # Check basic eligibility
        if not promotion.is_active:
            return False
        
        # Check date range
        now = timezone.now()
        if now < promotion.start_date or now > promotion.end_date:
            return False
        
        # Check requirements
        requirements = promotion.requirements or {}
        
        # Check user level
        min_level = requirements.get('min_user_level', 1)
        if getattr(user, 'level', 1) < min_level:
            return False
        
        # Check KYC tier
        min_kyc = requirements.get('min_kyc_tier', 'none')
        if min_kyc != 'none' and ctx.kyc_tier not in [ctx.kyc_tier, 'full']:
            return False
        
        # Check account age
        min_age = requirements.get('min_account_age_days', 0)
        if ctx.account_age_days < min_age:
            return False
        
        # Check wallet balance
        min_balance = requirements.get('min_wallet_balance', 0)
        if ctx.wallet_balance < min_balance:
            return False
        
        # Check usage limits
        usage_limits = promotion.usage_limits or {}
        if usage_limits.get('max_claims_per_user', 0) > 0:
            user_claims = PromotionClaim.objects.filter(
                user=user,
                promotion=promotion,
                status='claimed'
            ).count()
            if user_claims >= usage_limits['max_claims_per_user']:
                return False
        
        return True
        
    except Exception:
        return False


def _get_eligibility_reason(promotion, user, ctx) -> str:
    """Get eligibility reason for user."""
    if not promotion.is_active:
        return "Promotion is not active"
    
    now = timezone.now()
    if now < promotion.start_date:
        return "Promotion has not started yet"
    if now > promotion.end_date:
        return "Promotion has expired"
    
    requirements = promotion.requirements or {}
    
    min_level = requirements.get('min_user_level', 1)
    if getattr(user, 'level', 1) < min_level:
        return f"User level {getattr(user, 'level', 1)} is below required level {min_level}"
    
    min_kyc = requirements.get('min_kyc_tier', 'none')
    if min_kyc != 'none' and ctx.kyc_tier not in [ctx.kyc_tier, 'full']:
        return f"KYC tier {ctx.kyc_tier} is below required tier {min_kyc}"
    
    min_age = requirements.get('min_account_age_days', 0)
    if ctx.account_age_days < min_age:
        return f"Account age {ctx.account_age_days} days is below required {min_age} days"
    
    min_balance = requirements.get('min_wallet_balance', 0)
    if ctx.wallet_balance < min_balance:
        return f"Wallet balance {ctx.wallet_balance} is below required {min_balance}"
    
    usage_limits = promotion.usage_limits or {}
    max_claims = usage_limits.get('max_claims_per_user', 0)
    if max_claims > 0:
        user_claims = PromotionClaim.objects.filter(
            user=user,
            promotion=promotion,
            status='claimed'
        ).count()
        if user_claims >= max_claims:
            return f"Maximum claims ({max_claims}) already reached"
    
    return "User is eligible for this promotion"


def _get_user_promotion_status(promotion, user) -> str:
    """Get user's current status for promotion."""
    try:
        claim = PromotionClaim.objects.filter(
            user=user,
            promotion=promotion
        ).order_by('-created_at').first()
        
        if claim:
            return claim.status
        else:
            return "unclaimed"
    except Exception:
        return "unknown"


def _get_remaining_claims(promotion, user) -> int:
    """Get remaining claims for user."""
    try:
        usage_limits = promotion.usage_limits or {}
        max_claims = usage_limits.get('max_claims_per_user', 0)
        
        if max_claims > 0:
            user_claims = PromotionClaim.objects.filter(
                user=user,
                promotion=promotion,
                status='claimed'
            ).count()
            return max(0, max_claims - user_claims)
        
        return 0
        
    except Exception:
        return 0


def _get_next_claim_time(promotion, user) -> Optional[str]:
    """Get next eligible claim time for user."""
    try:
        usage_limits = promotion.usage_limits or {}
        cooldown_hours = usage_limits.get('claim_cooldown_hours', 0)
        
        if cooldown_hours > 0:
            last_claim = PromotionClaim.objects.filter(
                user=user,
                promotion=promotion,
                status='claimed'
            ).order_by('-created_at').first()
            
            if last_claim:
                next_claim_time = last_claim.created_at + timedelta(hours=cooldown_hours)
                if next_claim_time > timezone.now():
                    return next_claim_time.isoformat()
        
        return None
        
    except Exception:
        return None


def _get_promotion_status(promotion, user) -> str:
    """Get current status of promotion for user."""
    now = timezone.now()
    
    if not promotion.is_active:
        return "inactive"
    elif now < promotion.start_date:
        return "upcoming"
    elif now > promotion.end_date:
        return "expired"
    else:
        # Check if user has claimed
        if PromotionClaim.objects.filter(
            user=user,
            promotion=promotion,
            status='claimed'
        ).exists():
            return "claimed"
        else:
            return "available"


def _process_promotion_claim(claim, user, promotion) -> Dict:
    """Process promotion claim."""
    try:
        # Process claim based on promotion type
        if promotion.promotion_type == 'bonus':
            return _process_bonus_claim(claim, user, promotion)
        elif promotion.promotion_type == 'referral':
            return _process_referral_claim(claim, user, promotion)
        elif promotion.promotion_type == 'seasonal':
            return _process_seasonal_claim(claim, user, promotion)
        else:
            return _process_standard_claim(claim, user, promotion)
            
    except Exception as e:
        logger.error(f"[PromotionsAdapter] Error processing claim: {e}")
        return {
            'success': False,
            'status': 'failed',
            'error': str(e)
        }


def _process_bonus_claim(claim, user, promotion) -> Dict:
    """Process bonus promotion claim."""
    try:
        # Credit user wallet
        from api.tasks.services import WalletService
        wallet_service = WalletService()
        
        wallet_service.credit(
            user_id=user.id,
            amount=claim.reward_awarded,
            transaction_type='promotion_bonus',
            reference=f'promotion_{promotion.id}',
            metadata={
                'promotion_type': promotion.promotion_type,
                'claim_id': claim.id
            }
        )
        
        # Update claim status
        claim.status = 'claimed'
        claim.processed_at = timezone.now()
        claim.save()
        
        return {
            'success': True,
            'status': 'claimed',
            'reward_awarded': claim.reward_awarded,
            'processed_at': claim.processed_at.isoformat(),
            'message': 'Bonus promotion claimed successfully'
        }
        
    except Exception as e:
        logger.error(f"[PromotionsAdapter] Error processing bonus claim: {e}")
        return {
            'success': False,
            'status': 'failed',
            'error': str(e)
        }


def _process_referral_claim(claim, user, promotion) -> Dict:
    """Process referral promotion claim."""
    try:
        # Process referral-specific logic
        # This would integrate with referral system
        
        # Update claim status
        claim.status = 'claimed'
        claim.processed_at = timezone.now()
        claim.save()
        
        return {
            'success': True,
            'status': 'claimed',
            'reward_awarded': claim.reward_awarded,
            'processed_at': claim.processed_at.isoformat(),
            'message': 'Referral promotion claimed successfully'
        }
        
    except Exception as e:
        logger.error(f"[PromotionsAdapter] Error processing referral claim: {e}")
        return {
            'success': False,
            'status': 'failed',
            'error': str(e)
        }


def _process_seasonal_claim(claim, user, promotion) -> Dict:
    """Process seasonal promotion claim."""
    try:
        # Process seasonal-specific logic
        
        # Update claim status
        claim.status = 'claimed'
        claim.processed_at = timezone.now()
        claim.save()
        
        return {
            'success': True,
            'status': 'claimed',
            'reward_awarded': claim.reward_awarded,
            'processed_at': claim.processed_at.isoformat(),
            'message': 'Seasonal promotion claimed successfully'
        }
        
    except Exception as e:
        logger.error(f"[PromotionsAdapter] Error processing seasonal claim: {e}")
        return {
            'success': False,
            'status': 'failed',
            'error': str(e)
        }


def _process_standard_claim(claim, user, promotion) -> Dict:
    """Process standard promotion claim."""
    try:
        # Process standard claim logic
        
        # Update claim status
        claim.status = 'claimed'
        claim.processed_at = timezone.now()
        claim.save()
        
        return {
            'success': True,
            'status': 'claimed',
            'reward_awarded': claim.reward_awarded,
            'processed_at': claim.processed_at.isoformat(),
            'message': 'Promotion claimed successfully'
        }
        
    except Exception as e:
        logger.error(f"[PromotionsAdapter] Error processing standard claim: {e}")
        return {
            'success': False,
            'status': 'failed',
            'error': str(e)
        }


def _can_claim_promotion(promotion, user) -> bool:
    """Check if user can claim promotion."""
    try:
        usage_limits = promotion.usage_limits or {}
        max_claims = usage_limits.get('max_claims_per_user', 0)
        
        if max_claims > 0:
            user_claims = PromotionClaim.objects.filter(
                user=user,
                promotion=promotion,
                status='claimed'
            ).count()
            return user_claims < max_claims
        
        return True
        
    except Exception:
        return False


def _get_promotions_summary(queryset, user) -> Dict:
    """Get promotions summary for user."""
    try:
        total_promotions = queryset.count()
        claimed_promotions = queryset.filter(
            promotionclaim__user=user,
            promotionclaim__status='claimed'
        ).distinct().count()
        
        return {
            'total_promotions': total_promotions,
            'claimed_promotions': claimed_promotions,
            'unclaimed_promotions': total_promotions - claimed_promotions,
            'claim_rate': round((claimed_promotions / max(total_promotions, 1)) * 100, 2)
        }
        
    except Exception:
        return {}


def _get_claim_summary(queryset) -> Dict:
    """Get claim summary statistics."""
    try:
        total_claims = queryset.count()
        successful_claims = queryset.filter(status='claimed').count()
        pending_claims = queryset.filter(status='pending').count()
        rejected_claims = queryset.filter(status='rejected').count()
        
        total_rewards = queryset.filter(
            status='claimed'
        ).aggregate(total=Sum(F('reward_awarded')))['total'] or Decimal('0')
        
        return {
            'total_claims': total_claims,
            'successful_claims': successful_claims,
            'pending_claims': pending_claims,
            'rejected_claims': rejected_claims,
            'success_rate': round((successful_claims / max(total_claims, 1)) * 100, 2),
            'total_rewards_awarded': str(total_rewards),
            'average_reward_per_claim': str(total_rewards / max(successful_claims, 1))
        }
        
    except Exception:
        return {}


def _get_daily_claim_trends(claims, days) -> List[Dict]:
    """Get daily claim trends."""
    try:
        from django.db.models import TruncDay
        from django.utils import timezone
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        daily_data = claims.filter(
            created_at__gte=start_date
        ).extra({
            'day': TruncDay('created_at')
        }).values('day').annotate(
            claims=Count('id'),
            successful_claims=Count('id', filter=Q(status='claimed')),
            total_rewards=Sum(F('reward_awarded'), filter=Q(status='claimed'))
        ).order_by('day')
        
        return [
            {
                'date': item['day'].isoformat(),
                'claims': item['claims'],
                'successful_claims': item['successful_claims'],
                'total_rewards': str(item['total_rewards'] or Decimal('0')),
                'success_rate': round((item['successful_claims'] / max(item['claims'], 1)) * 100, 2)
            }
            for item in daily_data
        ]
        
    except Exception:
        return []


def _get_promotion_user_engagement(claims) -> Dict:
    """Get promotion user engagement metrics."""
    try:
        total_users = claims.values('user').distinct().count()
        active_users = claims.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).values('user').distinct().count()
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'engagement_rate': round((active_users / max(total_users, 1)) * 100, 2),
            'repeat_users': claims.values('user').annotate(
                claim_count=Count('id')
            ).filter(claim_count__gt=1).count()
        }
        
    except Exception:
        return {}
