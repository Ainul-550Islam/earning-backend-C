# api/payment_gateways/webhooks/BkashWebhook.py

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import hashlib
import hmac
from django.conf import settings
from ..models import PaymentGatewayWebhookLog, GatewayTransaction
from django.utils import timezone
from django.db import transaction as db_transaction
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def bkash_webhook(request):
    """Handle bKash payment webhook"""
    payload = request.body.decode('utf-8')
    headers = dict(request.headers)
    ip_address = request.META.get('REMOTE_ADDR')
    
    try:
        data = json.loads(payload)
        
        # Log the webhook
        webhook_log = PaymentGatewayWebhookLog.objects.create(
            gateway='bkash',
            payload=data,
            headers=json.dumps(headers),
            ip_address=ip_address
        )
        
        # Verify signature (implement based on bKash docs)
        signature = headers.get('X-Bkash-Signature', '')
        if signature:
            is_valid = verify_bkash_signature(payload, signature)
            
            if not is_valid:
                webhook_log.processing_error = 'Invalid signature'
                webhook_log.save()
                logger.warning(f'Invalid bKash signature from IP: {ip_address}')
                return HttpResponse('Invalid signature', status=400)
        else:
            logger.warning('bKash webhook received without signature')
        
        # Process based on event type
        event_type = data.get('type', '')
        
        if event_type == 'CHECKOUT_ORDER_CREATED':
            # Handle checkout creation
            process_checkout_created(data, webhook_log)
        
        elif event_type == 'PAYMENT_SUCCESS':
            # Handle successful payment
            process_payment_success(data, webhook_log)
        
        elif event_type == 'PAYMENT_FAILED':
            # Handle failed payment
            process_payment_failed(data, webhook_log)
        
        elif event_type == 'PAYMENT_CANCELLED':
            # Handle cancelled payment
            process_payment_cancelled(data, webhook_log)
        
        elif event_type == 'REFUND_SUCCESS':
            # Handle refund
            process_refund_success(data, webhook_log)
        
        else:
            logger.info(f'Unhandled bKash event type: {event_type}')
        
        webhook_log.processed = True
        webhook_log.response = 'Webhook processed successfully'
        webhook_log.save()
        
        return HttpResponse('OK', status=200)
        
    except json.JSONDecodeError as e:
        logger.error(f'bKash webhook JSON decode error: {str(e)}')
        return HttpResponse('Invalid JSON', status=400)
    except Exception as e:
        logger.exception(f'bKash webhook error: {str(e)}')
        # Log error
        PaymentGatewayWebhookLog.objects.create(
            gateway='bkash',
            payload={'error': str(e)},
            headers=json.dumps(headers),
            ip_address=ip_address,
            processed=False,
            processing_error=str(e)
        )
        return HttpResponse('Internal server error', status=500)


def verify_bkash_signature(payload, signature):
    """Verify bKash webhook signature"""
    # Implement signature verification based on bKash documentation
    secret_key = getattr(settings, 'BKASH_WEBHOOK_SECRET', '')
    
    if not secret_key:
        logger.warning('BKASH_WEBHOOK_SECRET not configured')
        return False
    
    expected_signature = hmac.new(
        secret_key.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


def process_checkout_created(data, webhook_log=None):
    """Process checkout created event"""
    payment_id = data.get('paymentID')
    
    if not payment_id:
        logger.error('bKash checkout created event missing paymentID')
        if webhook_log:
            webhook_log.processing_error = 'Missing paymentID'
            webhook_log.save()
        return
    
    try:
        transaction = GatewayTransaction.objects.get(
            gateway_reference=payment_id,
            gateway='bkash'
        )
        
        transaction.status = 'pending'
        transaction.metadata['bkash_checkout_data'] = data
        transaction.save()
        
        logger.info(f'bKash checkout created: Payment ID {payment_id}')
        
    except GatewayTransaction.DoesNotExist:
        logger.warning(f'bKash transaction not found for checkout: {payment_id}')
    except GatewayTransaction.MultipleObjectsReturned:
        logger.error(f'Multiple bKash transactions found for payment: {payment_id}')
    except Exception as e:
        logger.exception(f'Error processing bKash checkout: {str(e)}')
        if webhook_log:
            webhook_log.processing_error = str(e)
            webhook_log.save()


def process_payment_success(data, webhook_log=None):
    """Process successful payment"""
    payment_id = data.get('paymentID')
    trx_id = data.get('trxID')
    amount = float(data.get('amount', 0))
    customer_msisdn = data.get('customerMsisdn', '')
    merchant_invoice_number = data.get('merchantInvoiceNumber', '')
    
    if not all([payment_id, trx_id]):
        logger.error('bKash success event missing required fields')
        if webhook_log:
            webhook_log.processing_error = 'Missing required fields'
            webhook_log.save()
        return
    
    try:
        transaction = GatewayTransaction.objects.get(
            gateway_reference=payment_id,
            gateway='bkash'
        )
        
        # Prevent duplicate processing
        if transaction.status == 'completed':
            logger.info(f'bKash transaction {payment_id} already completed')
            return
        
        with db_transaction.atomic():
            # Update transaction
            transaction.status = 'completed'
            transaction.gateway_reference = trx_id
            transaction.metadata['bkash_success_data'] = data
            transaction.metadata['bkash_trx_id'] = trx_id
            transaction.metadata['bkash_customer_msisdn'] = customer_msisdn
            transaction.metadata['bkash_invoice'] = merchant_invoice_number
            transaction.completed_at = timezone.now()
            transaction.save()
            
            # Update user balance
            user = transaction.user
            user.balance += transaction.net_amount
            user.save()
        
        logger.info(f'bKash payment success: Payment ID {payment_id}, TrxID {trx_id}, Amount {amount}')
        
    except GatewayTransaction.DoesNotExist:
        logger.error(f'bKash transaction not found: {payment_id}')
        if webhook_log:
            webhook_log.processing_error = 'Transaction not found'
            webhook_log.save()
    except GatewayTransaction.MultipleObjectsReturned:
        logger.error(f'Multiple bKash transactions found for payment: {payment_id}')
        if webhook_log:
            webhook_log.processing_error = 'Multiple transactions found'
            webhook_log.save()
    except Exception as e:
        logger.exception(f'Error processing bKash success: {str(e)}')
        if webhook_log:
            webhook_log.processing_error = str(e)
            webhook_log.save()


def process_payment_failed(data, webhook_log=None):
    """Process failed payment"""
    payment_id = data.get('paymentID')
    error_message = data.get('errorMessage', 'Payment failed')
    error_code = data.get('errorCode', 'unknown')
    
    if not payment_id:
        logger.error('bKash failed event missing paymentID')
        return
    
    try:
        transaction = GatewayTransaction.objects.get(
            gateway_reference=payment_id,
            gateway='bkash'
        )
        
        # Don't update if already in final state
        if transaction.status in ['completed', 'refunded']:
            logger.warning(f'bKash transaction {payment_id} already in final state: {transaction.status}')
            return
        
        transaction.status = 'failed'
        transaction.metadata['bkash_failed_data'] = data
        transaction.metadata['bkash_error_message'] = error_message
        transaction.metadata['bkash_error_code'] = error_code
        transaction.save()
        
        logger.info(f'bKash payment failed: Payment ID {payment_id}, Error: {error_code}')
        
    except GatewayTransaction.DoesNotExist:
        logger.warning(f'bKash transaction not found for failed payment: {payment_id}')
        if webhook_log:
            webhook_log.processing_error = 'Transaction not found'
            webhook_log.save()
    except Exception as e:
        logger.exception(f'Error processing bKash failure: {str(e)}')
        if webhook_log:
            webhook_log.processing_error = str(e)
            webhook_log.save()


def process_payment_cancelled(data, webhook_log=None):
    """Process cancelled payment"""
    payment_id = data.get('paymentID')
    cancellation_reason = data.get('reason', 'User cancelled')
    
    if not payment_id:
        logger.error('bKash cancelled event missing paymentID')
        return
    
    try:
        transaction = GatewayTransaction.objects.get(
            gateway_reference=payment_id,
            gateway='bkash'
        )
        
        # Don't update if already completed
        if transaction.status == 'completed':
            logger.warning(f'Cannot cancel completed bKash transaction: {payment_id}')
            return
        
        transaction.status = 'cancelled'
        transaction.metadata['bkash_cancelled_data'] = data
        transaction.metadata['bkash_cancellation_reason'] = cancellation_reason
        transaction.save()
        
        logger.info(f'bKash payment cancelled: Payment ID {payment_id}, Reason: {cancellation_reason}')
        
    except GatewayTransaction.DoesNotExist:
        logger.warning(f'bKash transaction not found for cancelled payment: {payment_id}')
    except Exception as e:
        logger.exception(f'Error processing bKash cancellation: {str(e)}')
        if webhook_log:
            webhook_log.processing_error = str(e)
            webhook_log.save()


def process_refund_success(data, webhook_log=None):
    """Process bKash refund"""
    payment_id = data.get('paymentID')
    trx_id = data.get('originalTrxID')
    refund_trx_id = data.get('refundTrxID')
    refund_amount = float(data.get('amount', 0))
    refund_reason = data.get('reason', '')
    
    if not all([payment_id, refund_trx_id]):
        logger.error('bKash refund event missing required fields')
        if webhook_log:
            webhook_log.processing_error = 'Missing required fields'
            webhook_log.save()
        return
    
    try:
        # Find original transaction
        transaction = GatewayTransaction.objects.get(
            gateway_reference=trx_id,
            gateway='bkash',
            status='completed'
        )
        
        # Check if refund already processed
        existing_refund = GatewayTransaction.objects.filter(
            transaction_type='refund',
            gateway='bkash',
            gateway_reference=refund_trx_id
        ).exists()
        
        if existing_refund:
            logger.info(f'bKash refund already processed: {refund_trx_id}')
            return
        
        with db_transaction.atomic():
            # Create refund transaction
            refund_transaction = GatewayTransaction.objects.create(
                user=transaction.user,
                transaction_type='refund',
                gateway='bkash',
                amount=refund_amount,
                fee=0,
                net_amount=refund_amount,
                status='completed',
                reference_id=f'REFUND_{refund_trx_id[:20]}',
                gateway_reference=refund_trx_id,
                metadata={
                    'bkash_refund_data': data,
                    'original_payment_id': payment_id,
                    'original_trx_id': trx_id,
                    'refund_reason': refund_reason
                },
                completed_at=timezone.now()
            )
            
            # Deduct from user balance
            transaction.user.balance -= refund_amount
            transaction.user.save()
        
        logger.info(f'bKash refund processed: RefundTrxID {refund_trx_id}, Amount {refund_amount}')
        
    except GatewayTransaction.DoesNotExist:
        logger.error(f'bKash transaction not found for refund: {trx_id}')
        if webhook_log:
            webhook_log.processing_error = 'Original transaction not found'
            webhook_log.save()
    except Exception as e:
        logger.exception(f'Error processing bKash refund: {str(e)}')
        if webhook_log:
            webhook_log.processing_error = str(e)
            webhook_log.save()