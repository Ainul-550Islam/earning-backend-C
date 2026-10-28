"""
api/adapters/postback_engine.py
Postback engine adapter for earning backend platform
"""
from django.db.models import Max
from django.db.models import Min
import logging
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.db.models import Count, Sum, Avg, F, ExpressionWrapper, fields
from decimal import Decimal
from datetime import timedelta
import hashlib
import hmac
import json

logger = logging.getLogger(__name__)
User = get_user_model()


@api_view(['POST'])
@permission_classes([AllowAny])
def receive_postback(request):
    """Receive postback from external networks."""
    try:
        # Get postback data
        postback_data = request.data.copy()
        client_ip = _get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Validate postback format
        if not postback_data:
            return Response({
                'success': False,
                'error': 'Empty postback data',
                'details': 'No postback data received'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract required fields
        event_type = postback_data.get('event_type')
        user_id = postback_data.get('user_id')
        offer_id = postback_data.get('offer_id')
        amount = postback_data.get('amount')
        transaction_id = postback_data.get('transaction_id')
        signature = postback_data.get('signature')
        
        if not all([event_type, user_id, offer_id, amount]):
            return Response({
                'success': False,
                'error': 'Missing required fields',
                'details': 'event_type, user_id, offer_id, and amount are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify signature if provided
        if signature:
            if not _verify_postback_signature(postback_data, signature):
                return Response({
                    'success': False,
                    'error': 'Invalid signature',
                    'details': 'Postback signature verification failed'
                }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Log postback receipt
        postback_id = _log_postback(postback_data, client_ip, user_agent)
        
        # Process postback based on event type
        if event_type == 'conversion':
            result = _process_conversion_postback(postback_data, postback_id)
        elif event_type == 'reversal':
            result = _process_reversal_postback(postback_data, postback_id)
        elif event_type == 'click':
            result = _process_click_postback(postback_data, postback_id)
        elif event_type == 'impression':
            result = _process_impression_postback(postback_data, postback_id)
        else:
            result = {
                'success': False,
                'error': 'Unsupported event type',
                'details': f'Event type {event_type} is not supported'
            }
        
        return Response({
            'success': result.get('success', False),
            'data': {
                'postback_id': postback_id,
                'event_type': event_type,
                'processed_at': timezone.now().isoformat(),
                'result': result
            },
            'message': result.get('message', 'Postback processed')
        }, status=status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"[PostbackEngine] Error processing postback: {e}")
        return Response({
            'success': False,
            'error': 'Postback processing failed',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_postback_history(request):
    """Get postback history for admin."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        if not user.is_staff:
            return Response({
                'success': False,
                'error': 'Admin access required',
                'details': 'Only admin users can access postback history'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get query parameters
        limit = int(request.GET.get('limit', 50))
        offset = int(request.GET.get('offset', 0))
        event_type = request.GET.get('event_type')
        status = request.GET.get('status')
        
        # Get postback history
        from postback.models import PostbackLog
        queryset = PostbackLog.objects.filter(
            tenant_id=tenant_id
        ).order_by('-created_at')
        
        # Apply filters
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        if status:
            queryset = queryset.filter(status=status)
        
        # Paginate
        postbacks = queryset[offset:offset+limit]
        
        # Serialize postbacks
        postback_data = []
        for postback in postbacks:
            postback_data.append({
                'id': postback.id,
                'event_type': postback.event_type,
                'user_id': postback.user_id,
                'offer_id': postback.offer_id,
                'amount': str(postback.amount) if postback.amount else '0.00',
                'currency': postback.currency,
                'transaction_id': postback.transaction_id,
                'status': postback.status,
                'client_ip': postback.client_ip,
                'user_agent': postback.user_agent,
                'created_at': postback.created_at.isoformat(),
                'processed_at': postback.processed_at.isoformat() if postback.processed_at else None,
                'processing_time_seconds': postback.processing_time_seconds,
                'error_message': postback.error_message,
                'retry_count': postback.retry_count,
                'metadata': postback.metadata,
            })
        
        return Response({
            'success': True,
            'data': {
                'postbacks': postback_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total': queryset.count(),
                    'has_more': len(postback_data) == limit
                },
                'filters': {
                    'event_type': event_type,
                    'status': status
                }
            },
            'message': 'Postback history retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[PostbackEngine] Error getting postback history: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve postback history',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def retry_postback(request, postback_id):
    """Retry a failed postback."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        if not user.is_staff:
            return Response({
                'success': False,
                'error': 'Admin access required',
                'details': 'Only admin users can retry postbacks'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get postback
        from postback.models import PostbackLog
        try:
            postback = PostbackLog.objects.get(
                id=postback_id,
                tenant_id=tenant_id
            )
        except PostbackLog.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Postback not found',
                'details': f'Postback with ID {postback_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if postback.status != 'failed':
            return Response({
                'success': False,
                'error': 'Postback not failed',
                'details': 'Only failed postbacks can be retried'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check retry limit
        if postback.retry_count >= 3:
            return Response({
                'success': False,
                'error': 'Retry limit exceeded',
                'details': 'Postback has reached maximum retry limit (3)'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Process retry
        result = _process_postback_retry(postback, user.id)
        
        return Response({
            'success': result.get('success', False),
            'data': {
                'postback_id': postback_id,
                'retry_count': postback.retry_count + 1,
                'status': postback.status,
                'processed_at': timezone.now().isoformat(),
                'result': result
            },
            'message': result.get('message', 'Postback retry processed')
        }, status=status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"[PostbackEngine] Error retrying postback: {e}")
        return Response({
            'success': False,
            'error': 'Postback retry failed',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_postback_stats(request):
    """Get postback statistics for admin."""
    try:
        user = request.user
        tenant_id = getattr(request, 'tenant_id', None)
        
        if not user.is_staff:
            return Response({
                'success': False,
                'error': 'Admin access required',
                'details': 'Only admin users can access postback statistics'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get postback statistics
        from postback.models import PostbackLog
        queryset = PostbackLog.objects.filter(
            created_at__gte=start_date,
            tenant_id=tenant_id
        )
        
        # Calculate statistics
        total_postbacks = queryset.count()
        successful_postbacks = queryset.filter(status='success').count()
        failed_postbacks = queryset.filter(status='failed').count()
        pending_postbacks = queryset.filter(status='pending').count()
        
        # Event type breakdown
        event_breakdown = queryset.values('event_type').annotate(
            count=Count('id'),
            total_amount=Sum(F('amount'))
        ).order_by('-count')
        
        # Processing time statistics
        processing_stats = queryset.aggregate(
            avg_processing_time=Avg(F('processing_time_seconds')),
            max_processing_time=Max(F('processing_time_seconds')),
            min_processing_time=Min(F('processing_time_seconds'))
        )
        
        stats_data = {
            'tenant_id': tenant_id,
            'period': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat()
            },
            'summary': {
                'total_postbacks': total_postbacks,
                'successful_postbacks': successful_postbacks,
                'failed_postbacks': failed_postbacks,
                'pending_postbacks': pending_postbacks,
                'success_rate': round((successful_postbacks / max(total_postbacks, 1)) * 100, 2),
                'total_amount': str(queryset.aggregate(
                    total=Sum(F('amount'))
                )['total'] or Decimal('0'))
            },
            'event_breakdown': list(event_breakdown),
            'processing_stats': {
                'avg_processing_time_seconds': processing_stats['avg_processing_time'] or 0,
                'max_processing_time_seconds': processing_stats['max_processing_time'] or 0,
                'min_processing_time_seconds': processing_stats['min_processing_time'] or 0,
            },
            'recent_failures': [
                {
                    'id': postback.id,
                    'event_type': postback.event_type,
                    'error_message': postback.error_message,
                    'retry_count': postback.retry_count,
                    'failed_at': postback.created_at.isoformat(),
                }
                for postback in queryset.filter(
                    status='failed'
                ).order_by('-created_at')[:10]
            ]
        }
        
        return Response({
            'success': True,
            'data': stats_data,
            'message': 'Postback statistics retrieved successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[PostbackEngine] Error getting postback statistics: {e}")
        return Response({
            'success': False,
            'error': 'Failed to retrieve postback statistics',
            'details': str(e) if request.user.is_staff else 'Internal error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _process_conversion_postback(postback_data: Dict, postback_id: str) -> Dict:
    """Process conversion postback."""
    try:
        user_id = postback_data.get('user_id')
        offer_id = postback_data.get('offer_id')
        amount = Decimal(str(postback_data.get('amount', '0')))
        transaction_id = postback_data.get('transaction_id')
        
        # Get user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return {
                'success': False,
                'error': 'User not found',
                'details': f'User with ID {user_id} not found'
            }
        
        # Get offer
        from api.tasks.models import MasterTask
        try:
            offer = MasterTask.objects.get(task_id=offer_id)
        except MasterTask.DoesNotExist:
            return {
                'success': False,
                'error': 'Offer not found',
                'details': f'Offer with ID {offer_id} not found'
            }
        
        # Check for duplicate conversion
        from postback.models import PostbackLog
        existing_conversion = PostbackLog.objects.filter(
            user_id=user_id,
            offer_id=offer_id,
            transaction_id=transaction_id,
            status='success'
        ).exists()
        
        if existing_conversion:
            return {
                'success': False,
                'error': 'Duplicate conversion',
                'details': 'This conversion has already been processed'
            }
        
        # Process conversion
        from api.tasks.services import WalletService
        wallet_service = WalletService()
        
        # Credit user wallet
        wallet_service.credit(
            user_id=user_id,
            amount=amount,
            transaction_type='conversion',
            reference=f'conversion_{transaction_id}',
            metadata={
                'offer_id': offer_id,
                'postback_id': postback_id,
                'conversion_type': 'postback'
            }
        )
        
        # Update offer statistics
        offer.total_completions += 1
        if not PostbackLog.objects.filter(
            user_id=user_id,
            offer_id=offer_id,
            status='success'
        ).exclude(id=postback_id).exists():
            offer.unique_users_completed += 1
        offer.save()
        
        # Update postback status
        postback = PostbackLog.objects.get(id=postback_id)
        postback.status = 'success'
        postback.processed_at = timezone.now()
        postback.processing_time_seconds = (timezone.now() - postback.created_at).total_seconds()
        postback.save()
        
        # Emit conversion event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('postback.conversion_processed', {
            'user_id': user_id,
            'offer_id': offer_id,
            'postback_id': postback_id,
            'amount': str(amount),
            'transaction_id': transaction_id
        })
        
        return {
            'success': True,
            'message': 'Conversion processed successfully'
        }
        
    except Exception as e:
        logger.error(f"[PostbackEngine] Error processing conversion: {e}")
        return {
            'success': False,
            'error': 'Conversion processing failed',
            'details': str(e)
        }


def _process_reversal_postback(postback_data: Dict, postback_id: str) -> Dict:
    """Process reversal postback."""
    try:
        user_id = postback_data.get('user_id')
        offer_id = postback_data.get('offer_id')
        amount = Decimal(str(postback_data.get('amount', '0')))
        transaction_id = postback_data.get('transaction_id')
        reason = postback_data.get('reason', 'Reversal requested')
        
        # Get original conversion
        from postback.models import PostbackLog
        try:
            original_conversion = PostbackLog.objects.get(
                user_id=user_id,
                offer_id=offer_id,
                transaction_id=transaction_id,
                status='success'
            )
        except PostbackLog.DoesNotExist:
            return {
                'success': False,
                'error': 'Original conversion not found',
                'details': 'No successful conversion found for reversal'
            }
        
        # Process reversal
        from api.tasks.services import WalletService
        wallet_service = WalletService()
        
        # Debit user wallet
        wallet_service.debit(
            user_id=user_id,
            amount=amount,
            transaction_type='reversal',
            reference=f'reversal_{transaction_id}',
            metadata={
                'original_conversion_id': original_conversion.id,
                'reason': reason,
                'postback_id': postback_id
            }
        )
        
        # Update postback status
        postback = PostbackLog.objects.get(id=postback_id)
        postback.status = 'success'
        postback.processed_at = timezone.now()
        postback.processing_time_seconds = (timezone.now() - postback.created_at).total_seconds()
        postback.save()
        
        # Emit reversal event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('postback.reversal_processed', {
            'user_id': user_id,
            'offer_id': offer_id,
            'postback_id': postback_id,
            'amount': str(amount),
            'transaction_id': transaction_id,
            'reason': reason
        })
        
        return {
            'success': True,
            'message': 'Reversal processed successfully'
        }
        
    except Exception as e:
        logger.error(f"[PostbackEngine] Error processing reversal: {e}")
        return {
            'success': False,
            'error': 'Reversal processing failed',
            'details': str(e)
        }


def _process_click_postback(postback_data: Dict, postback_id: str) -> Dict:
    """Process click postback."""
    try:
        user_id = postback_data.get('user_id')
        offer_id = postback_data.get('offer_id')
        
        # Get user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return {
                'success': False,
                'error': 'User not found',
                'details': f'User with ID {user_id} not found'
            }
        
        # Update postback status
        from postback.models import PostbackLog
        postback = PostbackLog.objects.get(id=postback_id)
        postback.status = 'success'
        postback.processed_at = timezone.now()
        postback.processing_time_seconds = (timezone.now() - postback.created_at).total_seconds()
        postback.save()
        
        # Emit click event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('postback.click_processed', {
            'user_id': user_id,
            'offer_id': offer_id,
            'postback_id': postback_id
        })
        
        return {
            'success': True,
            'message': 'Click postback processed successfully'
        }
        
    except Exception as e:
        logger.error(f"[PostbackEngine] Error processing click: {e}")
        return {
            'success': False,
            'error': 'Click processing failed',
            'details': str(e)
        }


def _process_impression_postback(postback_data: Dict, postback_id: str) -> Dict:
    """Process impression postback."""
    try:
        user_id = postback_data.get('user_id')
        offer_id = postback_data.get('offer_id')
        
        # Get user
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return {
                'success': False,
                'error': 'User not found',
                'details': f'User with ID {user_id} not found'
            }
        
        # Update postback status
        from postback.models import PostbackLog
        postback = PostbackLog.objects.get(id=postback_id)
        postback.status = 'success'
        postback.processed_at = timezone.now()
        postback.processing_time_seconds = (timezone.now() - postback.created_at).total_seconds()
        postback.save()
        
        # Emit impression event
        from api.tasks.integration.event_bus import EventBus
        EventBus.emit('postback.impression_processed', {
            'user_id': user_id,
            'offer_id': offer_id,
            'postback_id': postback_id
        })
        
        return {
            'success': True,
            'message': 'Impression postback processed successfully'
        }
        
    except Exception as e:
        logger.error(f"[PostbackEngine] Error processing impression: {e}")
        return {
            'success': False,
            'error': 'Impression processing failed',
            'details': str(e)
        }


def _log_postback(postback_data: Dict, client_ip: str, user_agent: str) -> str:
    """Log postback receipt."""
    try:
        from postback.models import PostbackLog
        postback = PostbackLog.objects.create(
            event_type=postback_data.get('event_type'),
            user_id=postback_data.get('user_id'),
            offer_id=postback_data.get('offer_id'),
            amount=Decimal(str(postback_data.get('amount', '0'))),
            currency=postback_data.get('currency', 'USD'),
            transaction_id=postback_data.get('transaction_id'),
            status='pending',
            client_ip=client_ip,
            user_agent=user_agent,
            metadata=postback_data.get('metadata', {}),
            created_at=timezone.now(),
            tenant_id=postback_data.get('tenant_id')
        )
        
        return str(postback.id)
        
    except Exception as e:
        logger.error(f"[PostbackEngine] Error logging postback: {e}")
        return ""


def _verify_postback_signature(postback_data: Dict, signature: str) -> bool:
    """Verify postback signature."""
    try:
        # Get secret key from tenant settings
        tenant_id = postback_data.get('tenant_id')
        secret_key = cache.get(f'postback_secret_{tenant_id}', 'default_secret')
        
        # Create signature base string
        signature_string = '&'.join([
            f"event_type={postback_data.get('event_type')}",
            f"user_id={postback_data.get('user_id')}",
            f"offer_id={postback_data.get('offer_id')}",
            f"amount={postback_data.get('amount')}",
            f"transaction_id={postback_data.get('transaction_id')}",
            f"currency={postback_data.get('currency', 'USD')}"
        ])
        
        # Generate expected signature
        expected_signature = hmac.new(
            secret_key.encode(),
            signature_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature.encode(), signature.encode())
        
    except Exception:
        return False


def _process_postback_retry(postback, admin_user_id: int) -> Dict:
    """Process postback retry."""
    try:
        # Process retry based on event type
        if postback.event_type == 'conversion':
            result = _process_conversion_postback({
                'user_id': postback.user_id,
                'offer_id': postback.offer_id,
                'amount': str(postback.amount),
                'transaction_id': postback.transaction_id
            }, postback.id)
        elif postback.event_type == 'reversal':
            result = _process_reversal_postback({
                'user_id': postback.user_id,
                'offer_id': postback.offer_id,
                'amount': str(postback.amount),
                'transaction_id': postback.transaction_id,
                'reason': f'Retry attempt {postback.retry_count + 1}'
            }, postback.id)
        else:
            result = {
                'success': False,
                'error': 'Unsupported event type for retry',
                'details': f'Event type {postback.event_type} cannot be retried'
            }
        
        return result
        
    except Exception as e:
        logger.error(f"[PostbackEngine] Error processing retry: {e}")
        return {
            'success': False,
            'error': 'Retry processing failed',
            'details': str(e)
        }


def _get_client_ip(request) -> str:
    """Get client IP address."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip
    
    return request.META.get('REMOTE_ADDR', '127.0.0.1')
