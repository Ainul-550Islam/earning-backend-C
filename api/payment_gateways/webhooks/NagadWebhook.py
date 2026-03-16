# api/payment_gateways/webhooks/NagadWebhook.py

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import hashlib
import hmac
from django.conf import settings
from ..models import PaymentGatewayWebhookLog, GatewayTransaction
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def nagad_webhook(request):
    """Handle Nagad payment webhook"""
    payload = request.body.decode('utf-8')
    headers = dict(request.headers)
    ip_address = request.META.get('REMOTE_ADDR')
    
    try:
        data = json.loads(payload)
        
        # Log the webhook
        webhook_log = PaymentGatewayWebhookLog.objects.create(
            gateway='nagad',
            payload=data,
            headers=json.dumps(headers),
            ip_address=ip_address
        )
        
        # Verify signature (implement based on Nagad docs)
        signature = headers.get('X-Nagad-Signature', '')
        if signature:
            is_valid = verify_nagad_signature(payload, signature)
            if not is_valid:
                webhook_log.processing_error = 'Invalid signature'
                webhook_log.save()
                logger.warning(f'Invalid Nagad signature from IP: {ip_address}')
                return HttpResponse('Invalid signature', status=400)
        
        # Validate required fields
        merchant_id = data.get('merchantId')
        order_id = data.get('orderId')
        payment_ref_id = data.get('paymentRefId')
        
        if not all([merchant_id, order_id, payment_ref_id]):
            webhook_log.processing_error = 'Missing required fields'
            webhook_log.save()
            logger.error(f'Nagad webhook missing required fields: {data}')
            return HttpResponse('Bad request', status=400)
        
        # Verify merchant ID
        if merchant_id != getattr(settings, 'NAGAD_MERCHANT_ID', ''):
            webhook_log.processing_error = 'Invalid merchant ID'
            webhook_log.save()
            logger.warning(f'Invalid Nagad merchant ID: {merchant_id}')
            return HttpResponse('Invalid merchant', status=400)
        
        # Process based on status code
        status_code = data.get('statusCode', '')
        
        if status_code == '000':
            # Payment successful
            process_nagad_success(data)
        elif status_code in ['001', '002', '003', '004']:
            # Payment failed/cancelled
            process_nagad_failed(data)
        elif status_code == 'Cancelled':
            # Payment cancelled
            process_nagad_cancelled(data)
        else:
            # Unknown status
            webhook_log.processing_error = f'Unknown status code: {status_code}'
            webhook_log.save()
            logger.warning(f'Unknown Nagad status code: {status_code}')
        
        webhook_log.processed = True
        webhook_log.response = 'Webhook processed successfully'
        webhook_log.save()
        
        return HttpResponse('OK', status=200)
        
    except json.JSONDecodeError as e:
        logger.error(f'Nagad webhook JSON decode error: {str(e)}')
        return HttpResponse('Invalid JSON', status=400)
    except Exception as e:
        logger.exception(f'Nagad webhook error: {str(e)}')
        PaymentGatewayWebhookLog.objects.create(
            gateway='nagad',
            payload={'error': str(e)},
            headers=json.dumps(headers),
            ip_address=ip_address,
            processed=False,
            processing_error=str(e)
        )
        return HttpResponse('Internal server error', status=500)


def verify_nagad_signature(payload, signature):
    """Verify Nagad webhook signature"""
    # Implement signature verification based on Nagad documentation
    # This is a placeholder - update based on actual Nagad specs
    secret_key = getattr(settings, 'NAGAD_SECRET_KEY', '')
    
    if not secret_key:
        logger.warning('NAGAD_SECRET_KEY not configured')
        return False
    
    expected_signature = hmac.new(
        secret_key.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


def process_nagad_success(data):
    """Process successful Nagad payment"""
    order_id = data.get('orderId')
    payment_ref_id = data.get('paymentRefId')
    amount = float(data.get('amount', 0))
    issue_date = data.get('issueDateTime')
    
    try:
        transaction = GatewayTransaction.objects.get(
            reference_id=order_id,
            gateway='nagad'
        )
        
        # Prevent duplicate processing
        if transaction.status == 'completed':
            logger.info(f'Nagad transaction {order_id} already completed')
            return
        
        # Update transaction
        transaction.status = 'completed'
        transaction.gateway_reference = payment_ref_id
        transaction.metadata['nagad_success_data'] = data
        transaction.metadata['nagad_issue_date'] = issue_date
        transaction.completed_at = timezone.now()
        transaction.save()
        
        # Update user balance
        user = transaction.user
        user.balance += transaction.net_amount
        user.save()
        
        logger.info(f'Nagad payment success: Order {order_id}, Amount {amount}')
        
    except GatewayTransaction.DoesNotExist:
        logger.error(f'Nagad transaction not found: {order_id}')
    except GatewayTransaction.MultipleObjectsReturned:
        logger.error(f'Multiple Nagad transactions found for order: {order_id}')
    except Exception as e:
        logger.exception(f'Error processing Nagad success: {str(e)}')


def process_nagad_failed(data):
    """Process failed Nagad payment"""
    order_id = data.get('orderId')
    status_code = data.get('statusCode')
    status_message = data.get('message', 'Payment failed')
    
    try:
        transaction = GatewayTransaction.objects.get(
            reference_id=order_id,
            gateway='nagad'
        )
        
        # Don't update if already processed
        if transaction.status in ['completed', 'refunded']:
            logger.warning(f'Nagad transaction {order_id} already in final state: {transaction.status}')
            return
        
        transaction.status = 'failed'
        transaction.metadata['nagad_failed_data'] = data
        transaction.metadata['nagad_failure_reason'] = status_message
        transaction.save()
        
        logger.info(f'Nagad payment failed: Order {order_id}, Status {status_code}')
        
    except GatewayTransaction.DoesNotExist:
        logger.error(f'Nagad transaction not found: {order_id}')
    except Exception as e:
        logger.exception(f'Error processing Nagad failure: {str(e)}')


def process_nagad_cancelled(data):
    """Process cancelled Nagad payment"""
    order_id = data.get('orderId')
    
    try:
        transaction = GatewayTransaction.objects.get(
            reference_id=order_id,
            gateway='nagad'
        )
        
        # Don't update if already completed
        if transaction.status == 'completed':
            logger.warning(f'Cannot cancel completed Nagad transaction: {order_id}')
            return
        
        transaction.status = 'cancelled'
        transaction.metadata['nagad_cancelled_data'] = data
        transaction.save()
        
        logger.info(f'Nagad payment cancelled: Order {order_id}')
        
    except GatewayTransaction.DoesNotExist:
        logger.error(f'Nagad transaction not found: {order_id}')
    except Exception as e:
        logger.exception(f'Error processing Nagad cancellation: {str(e)}')


def process_nagad_refund(data):
    """Process Nagad refund (if supported)"""
    order_id = data.get('orderId')
    refund_ref_id = data.get('refundRefId')
    refund_amount = float(data.get('refundAmount', 0))
    
    try:
        transaction = GatewayTransaction.objects.get(
            reference_id=order_id,
            gateway='nagad',
            status='completed'
        )
        
        # Create refund transaction
        GatewayTransaction.objects.create(
            user=transaction.user,
            transaction_type='refund',
            gateway='nagad',
            amount=refund_amount,
            fee=0,
            net_amount=refund_amount,
            status='completed',
            reference_id=f'REFUND_{order_id}',
            gateway_reference=refund_ref_id,
            metadata={'nagad_refund_data': data, 'original_order_id': order_id},
            completed_at=timezone.now()
        )
        
        # Deduct from user balance
        transaction.user.balance -= refund_amount
        transaction.user.save()
        
        logger.info(f'Nagad refund processed: Order {order_id}, Amount {refund_amount}')
        
    except GatewayTransaction.DoesNotExist:
        logger.error(f'Nagad transaction not found for refund: {order_id}')
    except Exception as e:
        logger.exception(f'Error processing Nagad refund: {str(e)}')