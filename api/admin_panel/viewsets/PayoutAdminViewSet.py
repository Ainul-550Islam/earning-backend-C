# api/admin_panel/viewsets/PayoutAdminViewSet.py
"""
PayoutAdminViewSet — Complete payout/withdrawal admin control.
Controls: PayoutBatch, PayoutItem, withdrawal approval, bKash/Nagad/Rocket processing.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class PayoutAdminViewSet(viewsets.ViewSet):
    """Admin control for Payout Queue — withdraw approval, batch processing, gateway routing."""
    permission_classes = [IsAdminUser]

    # ==================== OVERVIEW ====================

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Payout system overview — pending amount, today's payouts, batch status."""
        try:
            from api.payout_queue.models import PayoutBatch, PayoutItem
            
            today = timezone.now().date()
            last_7d = timezone.now() - timedelta(days=7)
            
            pending = PayoutItem.objects.filter(status='QUEUED').aggregate(
                count=Count('id'), total=Sum('gross_amount')
            )
            today_paid = PayoutItem.objects.filter(
                status='SUCCESS', updated_at__date=today
            ).aggregate(count=Count('id'), total=Sum('gross_amount'))
            last_7d_paid = PayoutItem.objects.filter(
                status='SUCCESS', updated_at__gte=last_7d
            ).aggregate(count=Count('id'), total=Sum('gross_amount'))
            
            batch_summary = list(
                PayoutBatch.objects.values('status').annotate(
                    count=Count('id'), total_amount=Sum('total_amount')
                )
            )
            
            return Response({
                'success': True,
                'data': {
                    'pending': pending,
                    'today_paid': today_paid,
                    'last_7d_paid': last_7d_paid,
                    'batch_summary': batch_summary,
                }
            })
        except Exception as e:
            return Response({'success': True, 'data': {}, 'error': str(e)})

    # ==================== PAYOUT ITEMS ====================

    @action(detail=False, methods=['get'])
    def pending_withdrawals(self, request):
        """List all pending withdrawal requests."""
        try:
            from api.payout_queue.models import PayoutItem
            
            min_amount = request.query_params.get('min_amount', 0)
            gateway = request.query_params.get('gateway')
            
            qs = PayoutItem.objects.filter(status='QUEUED').select_related('user')
            if float(min_amount) > 0:
                qs = qs.filter(amount__gte=min_amount)
            if gateway:
                qs = qs.filter(gateway=gateway)
            
            items = list(qs.order_by('-amount', 'created_at').values(
                'id', 'user_id', 'amount', 'currency', 'gateway',
                'account_number', 'account_name', 'status', 'created_at',
                'priority', 'notes',
            )[:100])
            
            summary = qs.aggregate(count=Count('id'), total=Sum('gross_amount'))
            
            return Response({
                'success': True,
                'data': items,
                'summary': summary,
            })
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    @action(detail=False, methods=['post'])
    def approve_withdrawal(self, request):
        """Approve a single withdrawal request."""
        try:
            from api.payout_queue.models import PayoutItem
            item_id = request.data.get('item_id')
            transaction_ref = request.data.get('gateway_reference', '')
            
            item = PayoutItem.objects.get(pk=item_id, status='QUEUED')
            item.status = 'approved'
            item.approved_by = request.user
            item.approved_at = timezone.now()
            item.transaction_reference = transaction_ref
            item.save()
            
            # Log activity
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(
                    actor=request.user,
                    action='approve_withdrawal',
                    model_name='PayoutItem',
                    object_id=str(item_id),
                    changes={'amount': str(item.gross_amount), 'gateway': item.gateway},
                )
            except Exception:
                pass
            
            return Response({
                'success': True,
                'item_id': item_id,
                'amount': str(item.gross_amount),
                'gateway': item.gateway,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def bulk_approve_withdrawals(self, request):
        """Bulk approve multiple withdrawal requests."""
        try:
            from api.payout_queue.models import PayoutItem
            ids = request.data.get('ids', [])
            max_amount = request.data.get('max_amount')  # Only approve below this amount
            
            qs = PayoutItem.objects.filter(status='QUEUED')
            if ids:
                qs = qs.filter(pk__in=ids)
            if max_amount:
                qs = qs.filter(amount__lte=Decimal(str(max_amount)))
            
            count = qs.update(
                status='SUCCESS',
                approved_by=request.user,
                approved_at=timezone.now(),
            )
            
            total_approved = qs.aggregate(total=Sum('gross_amount'))['total'] or 0
            
            # Log activity
            try:
                from api.admin_panel.models.activity import AdminActivity
                AdminActivity.log(
                    actor=request.user,
                    action='bulk_approve_withdrawal',
                    changes={'count': count, 'total_amount': str(total_approved)},
                )
            except Exception:
                pass
            
            return Response({
                'success': True,
                'approved': count,
                'total_amount': str(total_approved),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def reject_withdrawal(self, request):
        """Reject a withdrawal request and refund to user wallet."""
        try:
            from api.payout_queue.models import PayoutItem
            item_id = request.data.get('item_id')
            reason = request.data.get('reason', 'Rejected by admin')
            refund = request.data.get('refund', True)
            
            item = PayoutItem.objects.get(pk=item_id, status='QUEUED')
            item.status = 'rejected'
            item.rejection_reason = reason
            item.rejected_by = request.user
            item.rejected_at = timezone.now()
            item.save()
            
            # Refund to wallet
            if refund:
                try:
                    from api.wallet.models.core import Wallet
                    wallet = Wallet.objects.get(user_id=item.user_id)
                    wallet.current_balance += item.gross_amount
                    wallet.save(update_fields=['balance'])
                except Exception as e:
                    logger.error(f"Refund failed for PayoutItem {item_id}: {e}")
            
            return Response({'success': True, 'item_id': item_id, 'rejected': True, 'refunded': refund})
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    # ==================== BATCH PROCESSING ====================

    @action(detail=False, methods=['post'])
    def create_batch(self, request):
        """Create a new payout batch from pending items."""
        try:
            from api.payout_queue.models import PayoutBatch, PayoutItem
            
            gateway = request.data.get('gateway', 'bkash')
            max_items = int(request.data.get('max_items', 100))
            min_amount = Decimal(str(request.data.get('min_amount', '10')))
            batch_name = request.data.get('name', f'Batch-{timezone.now().strftime("%Y%m%d-%H%M")}')
            
            # Select pending items for this gateway
            items = PayoutItem.objects.filter(
                status='SUCCESS',
                gateway=gateway,
                amount__gte=min_amount,
            )[:max_items]
            
            if not items.exists():
                return Response({'error': f'No approved {gateway} items found'}, status=400)
            
            total = items.aggregate(total=Sum('gross_amount'))['total'] or 0
            
            batch = PayoutBatch.objects.create(
                name=batch_name,
                gateway=gateway,
                total_amount=total,
                item_count=items.count(),
                status='QUEUED',
                created_by=request.user,
            )
            
            items.update(batch=batch, status='PROCESSING')
            
            return Response({
                'success': True,
                'batch_id': batch.pk,
                'name': batch_name,
                'gateway': gateway,
                'items': items.count(),
                'total': str(total),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['get'])
    def batch_list(self, request):
        """List all payout batches."""
        try:
            from api.payout_queue.models import PayoutBatch
            batches = list(
                PayoutBatch.objects.values(
                    'id', 'name', 'gateway', 'total_amount',
                    'item_count', 'status', 'created_at', 'processed_at'
                ).order_by('-created_at')[:50]
            )
            return Response({'success': True, 'data': batches})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    # ==================== GATEWAY ANALYTICS ====================

    @action(detail=False, methods=['get'])
    def gateway_stats(self, request):
        """Payout stats by payment gateway (bKash, Nagad, Rocket, etc.)."""
        try:
            from api.payout_queue.models import PayoutItem
            last_30d = timezone.now() - timedelta(days=30)
            
            gateway_breakdown = list(
                PayoutItem.objects.filter(
                    created_at__gte=last_30d
                ).values('gateway').annotate(
                    total_requests=Count('id'),
                    pending=Count('id', filter=Q(status='QUEUED')),
                    approved=Count('id', filter=Q(status='SUCCESS')),
                    paid=Count('id', filter=Q(status='SUCCESS')),
                    rejected=Count('id', filter=Q(status='FAILED')),
                    total_amount=Sum('gross_amount'),
                ).order_by('-total_amount')
            )
            
            return Response({'success': True, 'data': gateway_breakdown})
        except Exception as e:
            return Response({'success': True, 'data': [], 'error': str(e)})

    # ==================== AUTO-APPROVE RULES ====================

    @action(detail=False, methods=['post'])
    def set_auto_approve_limit(self, request):
        """Set the auto-approve amount threshold (from SystemSettings)."""
        try:
            from api.admin_panel.models.core import SystemSettings
            settings = SystemSettings.get_settings()
            amount = Decimal(str(request.data.get('amount', '100')))
            settings.withdrawal_auto_approve_limit = amount
            settings.last_modified_by = request.user
            settings.save()
            return Response({
                'success': True,
                'auto_approve_limit': str(amount),
                'message': f'Auto-approve limit set to ৳{amount}',
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)