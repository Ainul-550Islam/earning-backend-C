"""
api/adapters/offerwall.py
Offerwall adapter for earning backend platform
"""
from decimal import Decimal
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
from api.tasks.models_base import UserTaskCompletion

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_offers(request):
    """Get available offers for user."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get user context for filtering
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        # Get query parameters
        category = request.GET.get('category')
        system_type = request.GET.get('system_type')
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get available tasks
        from api.tasks.models import MasterTask
        queryset = MasterTask.objects.filter(
            is_active=True,
            available_from__lte=timezone.now(),
            available_until__gte=timezone.now(),
            tenant_id=tenant_id
        )
        
        # Apply filters
        if category:
            queryset = queryset.filter(category=category)
        if system_type:
            queryset = queryset.filter(system_type=system_type)
        
        # Apply user segment filtering
        if ctx.user_segment:
            queryset = queryset.filter(
                target_user_segments__contains=[ctx.user_segment]
            )
        
        # Apply fraud filtering
        if ctx.is_fraud_flagged:
            queryset = queryset.none()  # No offers for flagged users
        
        # Order and paginate
        offers = queryset.order_by('sort_order', '-created_at')[offset:offset+limit]
        
        # Serialize offers
        offers_data = []
        for offer in offers:
            offers_data.append({
                'task_id': offer.task_id,
                'name': offer.name,
                'description': offer.description,
                'category': offer.category,
                'system_type': offer.system_type,
                'rewards': offer.rewards,
                'constraints': offer.constraints,
                'ui_config': offer.ui_config,
                'is_available': offer.is_available_now,
                'available_from': offer.available_from.isoformat(),
                'available_until': offer.available_until.isoformat() if offer.available_until else None,
                'total_completions': offer.total_completions,
                'unique_users_completed': offer.unique_users_completed,
                'daily_completion_limit': offer.daily_completion_limit,
                'user_completions': UserTaskCompletion.objects.filter(
                    user=user,
                    task=offer,
                    status='completed'
                ).count(),
                'user_can_complete': ctx.is_eligible_for_offers,
                'estimated_earnings': str(offer.rewards.get('points', 0)),
                'estimated_time': offer.ui_config.get('estimated_time', '5 minutes'),
            })
        
        return Response({
            'success': True,
            'data': {
                'offers': offers_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(offers_data) == limit
                },
                'filters': {
                    'category': category,
                    'system_type': system_type,
                    'user_segment': ctx.user_segment
                }
            },
            'message': 'Offers retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[OfferwallAdapter] Error getting offers: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve offers',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_offer_details(request, task_id):
    """Get detailed information about a specific offer."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get offer
        from api.tasks.models import MasterTask
        try:
            offer = MasterTask.objects.get(
                task_id=task_id,
                tenant_id=tenant_id,
                is_active=True
            )
        except MasterTask.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Offer not found',
                'details': f'Offer with ID {task_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get user context
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        # Get user's completion history for this offer
        from api.tasks.models import UserTaskCompletion
        user_completions = UserTaskCompletion.objects.filter(
            user=user,
            task=offer
        ).order_by('-completed_at')[:5]
        
        # Build detailed offer data
        offer_data = {
            'task_id': offer.task_id,
            'name': offer.name,
            'description': offer.description,
            'category': offer.category,
            'system_type': offer.system_type,
            'rewards': offer.rewards,
            'constraints': offer.constraints,
            'ui_config': offer.ui_config,
            'requirements': offer.task_metadata.get('requirements', {}),
            'instructions': offer.task_metadata.get('instructions', ''),
            'is_available': offer.is_available_now,
            'availability': {
                'available_from': offer.available_from.isoformat(),
                'available_until': offer.available_until.isoformat() if offer.available_until else None,
                'next_available': offer.get_next_available_time(user.id).isoformat() if not offer.is_available_now else None,
            },
            'statistics': {
                'total_completions': offer.total_completions,
                'unique_users_completed': offer.unique_users_completed,
                'daily_completion_limit': offer.daily_completion_limit,
                'user_completions': UserTaskCompletion.objects.filter(
                    user=user,
                    task=offer,
                    status='completed'
                ).count(),
                'user_can_complete': ctx.is_eligible_for_offers,
                'completion_rate': (offer.unique_users_completed / max(offer.total_completions, 1)) * 100 if offer.total_completions > 0 else 0,
            },
            'user_history': [
                {
                    'id': completion.id,
                    'status': completion.status,
                    'started_at': completion.started_at.isoformat(),
                    'completed_at': completion.completed_at.isoformat() if completion.completed_at else None,
                    'rewards_awarded': completion.rewards_awarded,
                    'proof_data': completion.proof_data,
                }
                for completion in user_completions
            ],
            'tenant_id': tenant_id
        }
        
        return Response({
            'success': True,
            'data': offer_data,
            'message': 'Offer details retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[OfferwallAdapter] Error getting offer details: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve offer details',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_offer(request, task_id):
    """Start working on an offer."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get offer
        from api.tasks.models import MasterTask, UserTaskCompletion
        try:
            offer = MasterTask.objects.get(
                task_id=task_id,
                tenant_id=tenant_id,
                is_active=True
            )
        except MasterTask.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Offer not found',
                'details': f'Offer with ID {task_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user can start this offer
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        if not ctx.is_eligible_for_offers:
            return Response({
                'success': False,
                'error': 'Not eligible for offers',
                'details': 'Complete KYC verification to enable offers'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not offer.is_available_now:
            return Response({
                'success': False,
                'error': 'Offer not available',
                'details': 'This offer is currently unavailable'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user already has active completion
        active_completion = UserTaskCompletion.objects.filter(
            user=user,
            task=offer,
            status__in=['started', 'completed']
        ).first()
        
        if active_completion:
            return Response({
                'success': False,
                'error': 'Already in progress',
                'details': 'You are already working on this offer'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create new completion
        completion = UserTaskCompletion.objects.create(
            user=user,
            task=offer,
            status='started',
            started_at=timezone.now(),
            tenant_id=tenant_id
        )
        
        # Emit offer started event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('offer.started', {
            'user_id': user.id,
            'task_id': task_id,
            'offer_name': offer.name,
            'completion_id': completion.id,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'completion_id': completion.id,
                'status': 'started',
                'started_at': completion.started_at.isoformat(),
                'estimated_completion_time': offer.ui_config.get('estimated_time', '5 minutes'),
                'next_steps': offer.task_metadata.get('next_steps', [])
            },
            'message': 'Offer started successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[OfferwallAdapter] Error starting offer: {e}")
        return Response({
            'success': False,
            'error': 'Failed to start offer',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_offer(request, task_id):
    """Complete an offer with proof."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Get offer and completion
        from api.tasks.models import MasterTask, UserTaskCompletion
        try:
            offer = MasterTask.objects.get(
                task_id=task_id,
                tenant_id=tenant_id,
                is_active=True
            )
            completion = UserTaskCompletion.objects.get(
                user=user,
                task=offer,
                status='started'
            )
        except (MasterTask.DoesNotExist, UserTaskCompletion.DoesNotExist):
            return Response({
                'success': False,
                'error': 'Offer or completion not found',
                'details': 'Offer not found or not started'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Validate completion data
        proof_data = data.get('proof_data', {})
        if not proof_data:
            return Response({
                'success': False,
                'error': 'Proof data required',
                'details': 'Please provide proof of completion'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update completion
        completion.status = 'completed'
        completion.completed_at = timezone.now()
        completion.proof_data = proof_data
        completion.rewards_awarded = offer.rewards
        
        # Calculate and update user stats
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        # Update offer statistics
        offer.total_completions += 1
        if not UserTaskCompletion.objects.filter(
            user=user,
            task=offer,
            status='completed'
        ).exclude(id=completion.id).exists():
            offer.unique_users_completed += 1
        
        offer.save()
        completion.save()
        
        # Process rewards
        from api.tasks.services import WalletService
        wallet_service = WalletService()
        
        if offer.rewards.get('points'):
            wallet_service.credit(
                user_id=user.id,
                amount=Decimal(str(offer.rewards['points'])),
                transaction_type='task_completion',
                reference=f'offer_{task_id}',
                metadata={
                    'task_id': task_id,
                    'offer_name': offer.name,
                    'completion_id': completion.id,
                    'tenant_id': tenant_id
                }
            )
        
        # Emit offer completed event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('offer.completed', {
            'user_id': user.id,
            'task_id': task_id,
            'offer_name': offer.name,
            'completion_id': completion.id,
            'rewards_awarded': offer.rewards,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'completion_id': completion.id,
                'status': 'completed',
                'completed_at': completion.completed_at.isoformat(),
                'rewards_awarded': offer.rewards,
                'new_balance': str(ctx.wallet_balance),
                'points_earned': offer.rewards.get('points', 0)
            },
            'message': 'Offer completed successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[OfferwallAdapter] Error completing offer: {e}")
        return Response({
            'success': False,
            'error': 'Failed to complete offer',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_categories(request):
    """Get available offer categories."""
    try:
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get categories
        from api.tasks.models import MasterTask
        categories = MasterTask.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).values_list('category', flat=True).distinct()
        
        # Get category counts
        category_data = []
        for category in categories:
            count = MasterTask.objects.filter(
                category=category,
                tenant_id=tenant_id,
                is_active=True
            ).count()
            
            category_data.append({
                'category': category,
                'display_name': MasterTask.TaskCategory(category).label if category else 'Unknown',
                'offer_count': count,
                'is_available': count > 0
            })
        
        return Response({
            'success': True,
            'data': {
                'categories': category_data,
                'total_categories': len(category_data)
            },
            'message': 'Categories retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[OfferwallAdapter] Error getting categories: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve categories',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_offers(request):
    """Search offers by keyword."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get search parameters
        query = request.GET.get('q', '').strip()
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        if not query:
            return Response({
                'success': False,
                'error': 'Search query required',
                'details': 'Please provide a search query'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Search offers
        from api.tasks.models import MasterTask
        from django.db.models import Q
        queryset = MasterTask.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query),
            tenant_id=tenant_id,
            is_active=True
        )
        
        # Get user context for filtering
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        # Apply user segment filtering
        if ctx.user_segment:
            queryset = queryset.filter(
                target_user_segments__contains=[ctx.user_segment]
            )
        
        # Order and paginate
        offers = queryset.order_by('sort_order', '-created_at')[offset:offset+limit]
        
        # Serialize search results
        search_data = []
        for offer in offers:
            search_data.append({
                'task_id': offer.task_id,
                'name': offer.name,
                'description': offer.description,
                'category': offer.category,
                'system_type': offer.system_type,
                'rewards': offer.rewards,
                'match_score': _calculate_match_score(offer, query),
                'user_can_complete': ctx.is_eligible_for_offers,
                'estimated_earnings': str(offer.rewards.get('points', 0)),
            })
        
        return Response({
            'success': True,
            'data': {
                'query': query,
                'offers': search_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(search_data) == limit
                }
            },
            'message': 'Search completed successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[OfferwallAdapter] Error searching offers: {e}")
        return Response({
            'success': False,
            'error': 'Failed to search offers',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _calculate_match_score(offer, query) -> float:
    """Calculate match score for search ranking."""
    try:
        query_lower = query.lower()
        name_score = 0
        description_score = 0
        
        # Name matching
        if offer.name and query_lower in offer.name.lower():
            name_score = 100
        elif query_lower in offer.name.lower():
            name_score = 80
        
        # Description matching
        if offer.description and query_lower in offer.description.lower():
            description_score = 50
        elif query_lower in offer.description.lower():
            description_score = 30
        
        return max(name_score, description_score) / 100.0
        
    except Exception:
        return 0.0
