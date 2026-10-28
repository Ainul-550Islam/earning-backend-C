"""
api/adapters/marketplace.py
Marketplace adapter for earning backend platform
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
def get_marketplace_listings(request):
    """Get marketplace listings for user."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get query parameters
        category = request.GET.get('category')
        listing_type = request.GET.get('type')  # 'offer', 'service', 'product'
        status = request.GET.get('status')  # 'active', 'pending', 'completed'
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get marketplace listings
        from marketplace.models import MarketplaceListing
        queryset = MarketplaceListing.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).order_by('-created_at')
        
        # Apply filters
        if category:
            queryset = queryset.filter(category=category)
        if listing_type:
            queryset = queryset.filter(listing_type=listing_type)
        if status:
            queryset = queryset.filter(status=status)
        
        # Paginate
        listings = queryset[offset:offset+limit]
        
        # Serialize listings
        listing_data = []
        for listing in listings:
            listing_data.append({
                'id': listing.id,
                'title': listing.title,
                'description': listing.description,
                'category': listing.category,
                'listing_type': listing.listing_type,
                'status': listing.status,
                'price': str(listing.price),
                'currency': listing.currency,
                'seller': {
                    'id': listing.seller.id,
                    'username': listing.seller.username,
                    'rating': listing.seller.rating,
                    'verified': listing.seller.verified,
                    'total_sales': listing.seller.total_sales,
                },
                'created_at': listing.created_at.isoformat(),
                'expires_at': listing.expires_at.isoformat() if listing.expires_at else None,
                'view_count': listing.view_count,
                'contact_count': listing.contact_count,
                'is_featured': listing.is_featured,
                'metadata': listing.metadata,
                'images': listing.images,
                'tags': listing.tags,
                'user_can_purchase': _can_user_purchase(user, listing),
                'user_can_contact': _can_user_contact(user, listing),
            })
        
        return Response({
            'success': True,
            'data': {
                'listings': listing_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(listing_data) == limit
                },
                'filters': {
                    'category': category,
                    'type': listing_type,
                    'status': status
                }
            },
            'message': 'Marketplace listings retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[MarketplaceAdapter] Error getting listings: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve marketplace listings',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_marketplace_details(request, listing_id):
    """Get detailed marketplace listing information."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        # Get listing
        from marketplace.models import MarketplaceListing
        try:
            listing = MarketplaceListing.objects.get(
                id=listing_id,
                tenant_id=tenant_id,
                is_active=True
            )
        except MarketplaceListing.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Listing not found',
                'details': f'Marketplace listing with ID {listing_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get user context
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        # Get listing interactions
        from marketplace.models import ListingInteraction
        interactions = ListingInteraction.objects.filter(
            listing=listing
        ).order_by('-created_at')[:10]
        
        # Build detailed listing data
        listing_data = {
            'id': listing.id,
            'title': listing.title,
            'description': listing.description,
            'category': listing.category,
            'listing_type': listing.listing_type,
            'status': listing.status,
            'price': str(listing.price),
            'currency': listing.currency,
            'seller': {
                'id': listing.seller.id,
                'username': listing.seller.username,
                'first_name': listing.seller.first_name,
                'last_name': listing.seller.last_name,
                'rating': listing.seller.rating,
                'verified': listing.seller.verified,
                'total_sales': listing.seller.total_sales,
                'member_since': listing.seller.date_joined.isoformat(),
                'response_time': listing.seller.avg_response_time,
                'completion_rate': listing.seller.completion_rate,
            },
            'availability': {
                'is_available': listing.is_available,
                'quantity': listing.quantity,
                'min_order': str(listing.min_order),
                'max_order': str(listing.max_order),
                'delivery_time': listing.delivery_time,
                'shipping_options': listing.shipping_options,
            },
            'media': {
                'images': listing.images,
                'videos': listing.videos,
                'documents': listing.documents,
            },
            'specifications': listing.specifications,
            'requirements': listing.requirements,
            'terms': listing.terms,
            'created_at': listing.created_at.isoformat(),
            'updated_at': listing.updated_at.isoformat(),
            'expires_at': listing.expires_at.isoformat() if listing.expires_at else None,
            'view_count': listing.view_count,
            'contact_count': listing.contact_count,
            'favorite_count': listing.favorite_count,
            'is_featured': listing.is_featured,
            'user_interactions': [
                {
                    'id': interaction.id,
                    'type': interaction.interaction_type,
                    'user': {
                        'id': interaction.user.id,
                        'username': interaction.user.username,
                    },
                    'message': interaction.message,
                    'created_at': interaction.created_at.isoformat(),
                }
                for interaction in interactions
            ],
            'user_actions': {
                'can_purchase': _can_user_purchase(user, listing),
                'can_contact': _can_user_contact(user, listing),
                'can_favorite': ctx.is_eligible_for_offers,
                'can_report': True,
                'can_review': _can_user_review(user, listing),
            },
            'tenant_id': tenant_id
        }
        
        return Response({
            'success': True,
            'data': listing_data,
            'message': 'Marketplace listing details retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[MarketplaceAdapter] Error getting listing details: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve listing details',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_marketplace_listing(request):
    """Create a new marketplace listing."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        # Validate required fields
        required_fields = ['title', 'description', 'category', 'listing_type', 'price']
        for field in required_fields:
            if field not in data:
                return Response({
                    'success': False,
                    'error': 'Missing required field',
                    'details': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user context for eligibility
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        if not ctx.is_eligible_for_offers:
            return Response({
                'success': False,
                'error': 'Not eligible to create listings',
                'details': 'Complete KYC verification to enable marketplace listings'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create listing
        from marketplace.models import MarketplaceListing
        listing = MarketplaceListing.objects.create(
            seller=user,
            title=data['title'],
            description=data['description'],
            category=data['category'],
            listing_type=data['listing_type'],
            price=Decimal(str(data['price'])),
            currency=data.get('currency', 'USD'),
            quantity=data.get('quantity', 1),
            min_order=Decimal(str(data.get('min_order', '1'))),
            max_order=Decimal(str(data.get('max_order', '999'))),
            delivery_time=data.get('delivery_time', '1-3 days'),
            shipping_options=data.get('shipping_options', []),
            specifications=data.get('specifications', {}),
            requirements=data.get('requirements', {}),
            terms=data.get('terms', ''),
            metadata=data.get('metadata', {}),
            images=data.get('images', []),
            videos=data.get('videos', []),
            documents=data.get('documents', []),
            tags=data.get('tags', []),
            status='pending',
            tenant_id=tenant_id,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30)
        )
        
        # Emit listing created event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('marketplace.listing_created', {
            'user_id': user.id,
            'listing_id': listing.id,
            'listing_type': listing.listing_type,
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'listing_id': listing.id,
                'status': 'pending',
                'created_at': listing.created_at.isoformat(),
                'expires_at': listing.expires_at.isoformat(),
                'next_steps': [
                    'Wait for admin approval',
                    'Add images and videos',
                    'Set pricing and shipping options'
                ]
            },
            'message': 'Marketplace listing created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[MarketplaceAdapter] Error creating listing: {e}")
        return Response({
            'success': False,
            'error': 'Failed to create marketplace listing',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def purchase_marketplace_item(request, listing_id):
    """Purchase an item from marketplace."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        data = request.data
        
        quantity = int(data.get('quantity', 1))
        notes = data.get('notes', '')
        
        # Get listing
        from marketplace.models import MarketplaceListing
        try:
            listing = MarketplaceListing.objects.get(
                id=listing_id,
                tenant_id=tenant_id,
                is_active=True,
                status='active'
            )
        except MarketplaceListing.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Listing not found',
                'details': f'Marketplace listing with ID {listing_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user can purchase
        if not _can_user_purchase(user, listing):
            return Response({
                'success': False,
                'error': 'Cannot purchase this item',
                'details': 'You do not meet the requirements to purchase this item'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check availability
        if listing.quantity < quantity:
            return Response({
                'success': False,
                'error': 'Insufficient quantity',
                'details': f'Only {listing.quantity} items available'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate total price
        total_price = listing.price * quantity
        
        # Check user balance
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        if ctx.wallet_balance < total_price:
            return Response({
                'success': False,
                'error': 'Insufficient balance',
                'details': f'Your balance ({ctx.wallet_balance}) is insufficient for this purchase'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create purchase
        from marketplace.models import MarketplacePurchase
        purchase = MarketplacePurchase.objects.create(
            buyer=user,
            listing=listing,
            seller=listing.seller,
            quantity=quantity,
            unit_price=listing.price,
            total_price=total_price,
            currency=listing.currency,
            status='pending',
            notes=notes,
            tenant_id=tenant_id,
            created_at=timezone.now()
        )
        
        # Update listing quantity
        listing.quantity -= quantity
        listing.save()
        
        # Create purchase event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('marketplace.item_purchased', {
            'buyer_id': user.id,
            'seller_id': listing.seller.id,
            'listing_id': listing.id,
            'purchase_id': purchase.id,
            'quantity': quantity,
            'total_price': str(total_price),
            'tenant_id': tenant_id
        })
        
        return Response({
            'success': True,
            'data': {
                'purchase_id': purchase.id,
                'status': 'pending',
                'quantity': quantity,
                'total_price': str(total_price),
                'estimated_delivery': listing.delivery_time,
                'seller_info': {
                    'id': listing.seller.id,
                    'username': listing.seller.username,
                    'rating': listing.seller.rating,
                }
            },
            'message': 'Purchase created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[MarketplaceAdapter] Error purchasing item: {e}")
        return Response({
            'success': False,
            'error': 'Failed to purchase marketplace item',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_purchase_history(request):
    """Get user's marketplace purchase history."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        limit = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        
        # Get purchases
        from marketplace.models import MarketplacePurchase
        queryset = MarketplacePurchase.objects.filter(
            buyer=user,
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply filters
        status = request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Paginate
        purchases = queryset[offset:offset+limit]
        
        # Serialize purchases
        purchase_data = []
        for purchase in purchases:
            purchase_data.append({
                'id': purchase.id,
                'listing': {
                    'id': purchase.listing.id,
                    'title': purchase.listing.title,
                    'category': purchase.listing.category,
                    'listing_type': purchase.listing.listing_type,
                },
                'seller': {
                    'id': purchase.seller.id,
                    'username': purchase.seller.username,
                    'rating': purchase.seller.rating,
                },
                'quantity': purchase.quantity,
                'unit_price': str(purchase.unit_price),
                'total_price': str(purchase.total_price),
                'currency': purchase.currency,
                'status': purchase.status,
                'notes': purchase.notes,
                'created_at': purchase.created_at.isoformat(),
                'completed_at': purchase.completed_at.isoformat() if purchase.completed_at else None,
                'tracking_info': purchase.tracking_info,
                'review': {
                    'rating': purchase.rating,
                    'review': purchase.review,
                    'reviewed_at': purchase.reviewed_at.isoformat() if purchase.reviewed_at else None,
                }
            })
        
        return Response({
            'success': True,
            'data': {
                'purchases': purchase_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(purchase_data) == limit
                },
                'summary': {
                    'total_spent': str(MarketplacePurchase.objects.filter(
                        buyer=user,
                        tenant_id=tenant_id,
                        status='completed'
                    ).aggregate(total=Sum(F('total_price')))['total'] or Decimal('0')),
                    'total_purchases': MarketplacePurchase.objects.filter(
                        buyer=user,
                        tenant_id=tenant_id
                    ).count(),
                    'pending_purchases': MarketplacePurchase.objects.filter(
                        buyer=user,
                        tenant_id=tenant_id,
                        status='pending'
                    ).count()
                }
            },
            'message': 'Purchase history retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[MarketplaceAdapter] Error getting purchase history: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve purchase history',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _can_user_purchase(user, listing) -> bool:
    """Check if user can purchase a listing."""
    try:
        # Check if user is the seller
        if user.id == listing.seller.id:
            return False
        
        # Check KYC requirements
        from api.tasks.integration.shared_context import SharedContext
        ctx = SharedContext.for_user(user.id)
        
        if not ctx.is_eligible_for_offers:
            return False
        
        # Check listing requirements
        if listing.requirements:
            user_level = getattr(user, 'level', 1)
            required_level = listing.requirements.get('min_level', 1)
            
            if user_level < required_level:
                return False
            
            required_kyc = listing.requirements.get('kyc_tier', 'none')
            if ctx.kyc_tier not in ['full', 'standard'] and required_kyc != 'none':
                return False
        
        return True
        
    except Exception:
        return False


def _can_user_contact(user, listing) -> bool:
    """Check if user can contact listing seller."""
    try:
        # Check if user is the seller
        if user.id == listing.seller.id:
            return False
        
        # Check if user has completed purchase
        from marketplace.models import MarketplacePurchase
        has_purchased = MarketplacePurchase.objects.filter(
            buyer=user,
            listing=listing,
            status='completed'
        ).exists()
        
        if not has_purchased:
            # Allow contact for certain listing types
            return listing.listing_type in ['service', 'digital']
        
        return has_purchased
        
    except Exception:
        return False


def _can_user_review(user, listing) -> bool:
    """Check if user can review a listing."""
    try:
        # Check if user has completed purchase
        from marketplace.models import MarketplacePurchase
        has_purchased = MarketplacePurchase.objects.filter(
            buyer=user,
            listing=listing,
            status='completed'
        ).exists()
        
        # Check if user is the seller
        if user.id == listing.seller.id:
            return False
        
        # Check if already reviewed
        from marketplace.models import ListingReview
        already_reviewed = ListingReview.objects.filter(
            reviewer=user,
            listing=listing
        ).exists()
        
        return has_purchased and not already_reviewed
        
    except Exception:
        return False
