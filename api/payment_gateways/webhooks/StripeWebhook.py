# api/payment_gateways/webhooks/StripeWebhook.py

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import stripe
from django.conf import settings
from ..models import PaymentGatewayWebhookLog, GatewayTransaction
from django.utils import timezone
from django.db import transaction as db_transaction
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe payment webhook"""
    payload = request.body.decode('utf-8')
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    ip_address = request.META.get('REMOTE_ADDR')
    
    try:
        # Initialize Stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Log the webhook
        webhook_log = PaymentGatewayWebhookLog.objects.create(
            gateway='stripe',
            payload=json.loads(payload),
            headers=json.dumps(dict(request.headers)),
            ip_address=ip_address
        )
        
        # Verify webhook signature
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
        
        if endpoint_secret:
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, endpoint_secret
                )
            except ValueError as e:
                webhook_log.processing_error = f'Invalid payload: {str(e)}'
                webhook_log.save()
                logger.error(f'Stripe webhook invalid payload: {str(e)}')
                return HttpResponse('Invalid payload', status=400)
            except stripe.error.SignatureVerificationError as e:
                webhook_log.processing_error = f'Invalid signature: {str(e)}'
                webhook_log.save()
                logger.warning(f'Stripe webhook invalid signature from IP: {ip_address}')
                return HttpResponse('Invalid signature', status=400)
        else:
            event = json.loads(payload)
            logger.warning('Stripe webhook secret not configured - signature verification skipped')
        
        # Handle the event
        event_type = event['type']
        
        if event_type == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            process_stripe_payment_success(payment_intent, webhook_log)
        
        elif event_type == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            process_stripe_payment_failed(payment_intent, webhook_log)
        
        elif event_type == 'payment_intent.canceled':
            payment_intent = event['data']['object']
            process_stripe_payment_canceled(payment_intent, webhook_log)
        
        elif event_type == 'charge.refunded':
            charge = event['data']['object']
            process_stripe_refund(charge, webhook_log)
        
        elif event_type == 'charge.dispute.created':
            charge = event['data']['object']
            process_stripe_dispute_created(charge, webhook_log)
        
        elif event_type == 'charge.dispute.closed':
            dispute = event['data']['object']
            process_stripe_dispute_closed(dispute, webhook_log)
        
        else:
            logger.info(f'Unhandled Stripe event type: {event_type}')
        
        webhook_log.processed = True
        webhook_log.response = 'Webhook processed successfully'
        webhook_log.save()
        
        return HttpResponse('OK', status=200)
        
    except json.JSONDecodeError as e:
        logger.error(f'Stripe webhook JSON decode error: {str(e)}')
        return HttpResponse('Invalid JSON', status=400)
    except Exception as e:
        logger.exception(f'Stripe webhook error: {str(e)}')
        PaymentGatewayWebhookLog.objects.create(
            gateway='stripe',
            payload={'error': str(e)},
            headers=json.dumps(dict(request.headers)),
            ip_address=ip_address,
            processed=False,
            processing_error=str(e)
        )
        return HttpResponse('Internal server error', status=500)


def process_stripe_payment_success(payment_intent, webhook_log=None):
    """Process successful Stripe payment"""
    payment_id = payment_intent['id']
    amount = payment_intent['amount'] / 100  # Convert from cents
    currency = payment_intent.get('currency', 'usd').upper()
    metadata = payment_intent.get('metadata', {})
    
    try:
        # Try to find existing transaction
        try:
            transaction = GatewayTransaction.objects.get(
                gateway_reference=payment_id,
                gateway='stripe'
            )
            
            # Prevent duplicate processing
            if transaction.status == 'completed':
                logger.info(f'Stripe transaction {payment_id} already completed')
                return
            
            # Update transaction with atomic operation
            with db_transaction.atomic():
                transaction.status = 'completed'
                transaction.metadata['stripe_success_data'] = payment_intent
                transaction.metadata['stripe_currency'] = currency
                transaction.completed_at = timezone.now()
                transaction.save()
                
                # Update user balance
                user = transaction.user
                user.balance += transaction.net_amount
                user.save()
            
            logger.info(f'Stripe payment success: Payment ID {payment_id}, Amount {amount} {currency}')
            
        except GatewayTransaction.DoesNotExist:
            # Create new transaction if not found
            user_id = metadata.get('user_id')
            
            if not user_id:
                logger.error(f'Stripe payment {payment_id} missing user_id in metadata')
                if webhook_log:
                    webhook_log.processing_error = 'Missing user_id in metadata'
                    webhook_log.save()
                return
            
            from api.users.models import User
            
            try:
                user = User.objects.get(id=user_id)
                
                # Calculate fees (Stripe: 2.9% + $0.30)
                fee = amount * 0.029 + 0.30
                net_amount = amount - fee
                
                with db_transaction.atomic():
                    # Create transaction
                    new_transaction = GatewayTransaction.objects.create(
                        user=user,
                        transaction_type='deposit',
                        gateway='stripe',
                        amount=amount,
                        fee=fee,
                        net_amount=net_amount,
                        status='completed',
                        reference_id=f'STRIPE_{payment_id}',
                        gateway_reference=payment_id,
                        metadata={
                            'stripe_data': payment_intent,
                            'stripe_currency': currency
                        },
                        completed_at=timezone.now()
                    )
                    
                    # Update user balance
                    user.balance += net_amount
                    user.save()
                
                logger.info(f'Stripe new transaction created: {new_transaction.reference_id}, Amount {amount} {currency}')
                
            except User.DoesNotExist:
                logger.error(f'Stripe payment {payment_id} user not found: {user_id}')
                if webhook_log:
                    webhook_log.processing_error = f'User not found: {user_id}'
                    webhook_log.save()
        
        except GatewayTransaction.MultipleObjectsReturned:
            logger.error(f'Multiple Stripe transactions found for payment: {payment_id}')
            if webhook_log:
                webhook_log.processing_error = 'Multiple transactions found'
                webhook_log.save()
    
    except Exception as e:
        logger.exception(f'Error processing Stripe success: {str(e)}')
        if webhook_log:
            webhook_log.processing_error = str(e)
            webhook_log.save()


def process_stripe_payment_failed(payment_intent, webhook_log=None):
    """Process failed Stripe payment"""
    payment_id = payment_intent['id']
    error_message = payment_intent.get('last_payment_error', {}).get('message', 'Payment failed')
    error_code = payment_intent.get('last_payment_error', {}).get('code', 'unknown')
    
    try:
        transaction = GatewayTransaction.objects.get(
            gateway_reference=payment_id,
            gateway='stripe'
        )
        
        # Don't update if already in final state
        if transaction.status in ['completed', 'refunded']:
            logger.warning(f'Stripe transaction {payment_id} already in final state: {transaction.status}')
            return
        
        transaction.status = 'failed'
        transaction.metadata['stripe_failed_data'] = payment_intent
        transaction.metadata['stripe_error_message'] = error_message
        transaction.metadata['stripe_error_code'] = error_code
        transaction.save()
        
        logger.info(f'Stripe payment failed: Payment ID {payment_id}, Error: {error_code}')
        
    except GatewayTransaction.DoesNotExist:
        logger.warning(f'Stripe transaction not found for failed payment: {payment_id}')
        if webhook_log:
            webhook_log.processing_error = 'Transaction not found'
            webhook_log.save()
    except Exception as e:
        logger.exception(f'Error processing Stripe failure: {str(e)}')
        if webhook_log:
            webhook_log.processing_error = str(e)
            webhook_log.save()


def process_stripe_payment_canceled(payment_intent, webhook_log=None):
    """Process canceled Stripe payment"""
    payment_id = payment_intent['id']
    cancellation_reason = payment_intent.get('cancellation_reason', 'unknown')
    
    try:
        transaction = GatewayTransaction.objects.get(
            gateway_reference=payment_id,
            gateway='stripe'
        )
        
        # Don't update if already completed
        if transaction.status == 'completed':
            logger.warning(f'Cannot cancel completed Stripe transaction: {payment_id}')
            return
        
        transaction.status = 'cancelled'
        transaction.metadata['stripe_cancelled_data'] = payment_intent
        transaction.metadata['stripe_cancellation_reason'] = cancellation_reason
        transaction.save()
        
        logger.info(f'Stripe payment canceled: Payment ID {payment_id}, Reason: {cancellation_reason}')
        
    except GatewayTransaction.DoesNotExist:
        logger.warning(f'Stripe transaction not found for canceled payment: {payment_id}')
    except Exception as e:
        logger.exception(f'Error processing Stripe cancellation: {str(e)}')
        if webhook_log:
            webhook_log.processing_error = str(e)
            webhook_log.save()


def process_stripe_refund(charge, webhook_log=None):
    """Process Stripe refund"""
    payment_id = charge.get('payment_intent')
    charge_id = charge.get('id')
    refund_amount = charge.get('amount_refunded', 0) / 100  # Convert from cents
    currency = charge.get('currency', 'usd').upper()
    
    try:
        transaction = GatewayTransaction.objects.get(
            gateway_reference=payment_id,
            gateway='stripe',
            status='completed'
        )
        
        # Check if refund already processed
        existing_refund = GatewayTransaction.objects.filter(
            transaction_type='refund',
            gateway='stripe',
            gateway_reference=charge_id
        ).exists()
        
        if existing_refund:
            logger.info(f'Stripe refund already processed for charge: {charge_id}')
            return
        
        with db_transaction.atomic():
            # Create refund transaction
            refund_transaction = GatewayTransaction.objects.create(
                user=transaction.user,
                transaction_type='refund',
                gateway='stripe',
                amount=refund_amount,
                fee=0,
                net_amount=refund_amount,
                status='completed',
                reference_id=f'REFUND_{charge_id[:20]}',
                gateway_reference=charge_id,
                metadata={
                    'stripe_refund_data': charge,
                    'original_payment_id': payment_id,
                    'stripe_currency': currency
                },
                completed_at=timezone.now()
            )
            
            # Deduct from user balance
            transaction.user.balance -= refund_amount
            transaction.user.save()
        
        logger.info(f'Stripe refund processed: Charge {charge_id}, Amount {refund_amount} {currency}')
        
    except GatewayTransaction.DoesNotExist:
        logger.error(f'Stripe transaction not found for refund: {payment_id}')
        if webhook_log:
            webhook_log.processing_error = 'Original transaction not found'
            webhook_log.save()
    except Exception as e:
        logger.exception(f'Error processing Stripe refund: {str(e)}')
        if webhook_log:
            webhook_log.processing_error = str(e)
            webhook_log.save()


def process_stripe_dispute_created(charge, webhook_log=None):
    """Process Stripe dispute creation"""
    charge_id = charge.get('id')
    payment_id = charge.get('payment_intent')
    dispute_amount = charge.get('amount_disputed', 0) / 100
    dispute_reason = charge.get('dispute', {}).get('reason', 'unknown')
    
    try:
        transaction = GatewayTransaction.objects.get(
            gateway_reference=payment_id,
            gateway='stripe'
        )
        
        transaction.status = 'disputed'
        transaction.metadata['stripe_dispute_data'] = charge
        transaction.metadata['dispute_reason'] = dispute_reason
        transaction.metadata['dispute_amount'] = dispute_amount
        transaction.save()
        
        logger.warning(f'Stripe dispute created: Charge {charge_id}, Reason: {dispute_reason}, Amount: {dispute_amount}')
        
        # Optionally: Send notification to admin/user about dispute
        
    except GatewayTransaction.DoesNotExist:
        logger.error(f'Stripe transaction not found for dispute: {payment_id}')
    except Exception as e:
        logger.exception(f'Error processing Stripe dispute: {str(e)}')


def process_stripe_dispute_closed(dispute, webhook_log=None):
    """Process Stripe dispute closure"""
    charge_id = dispute.get('charge')
    dispute_status = dispute.get('status')  # won, lost, warning_closed, etc.
    
    try:
        transaction = GatewayTransaction.objects.filter(
            gateway='stripe',
            metadata__stripe_dispute_data__id=charge_id
        ).first()
        
        if transaction:
            if dispute_status == 'won':
                transaction.status = 'completed'
            elif dispute_status == 'lost':
                transaction.status = 'dispute_lost'
            
            transaction.metadata['dispute_closed_status'] = dispute_status
            transaction.metadata['dispute_closed_data'] = dispute
            transaction.save()
            
            logger.info(f'Stripe dispute closed: Charge {charge_id}, Status: {dispute_status}')
    
    except Exception as e:
        logger.exception(f'Error processing Stripe dispute closure: {str(e)}')