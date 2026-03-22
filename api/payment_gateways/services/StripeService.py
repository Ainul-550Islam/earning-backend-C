# api/payment_gateways/services/StripeService.py

import stripe
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from .PaymentProcessor import PaymentProcessor
from ..models import GatewayTransaction as TxnModel, PayoutRequest


class StripeService(PaymentProcessor):
    """Stripe Payment Service Implementation"""
    
    def __init__(self):
        super().__init__('stripe')
        stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        self.webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        self.public_key = getattr(settings, 'STRIPE_PUBLIC_KEY', '')
    
    def process_deposit(self, user, amount, payment_method=None, **kwargs):
        """Process Stripe deposit"""
        self.validate_amount(amount)
        
        # Create txn
        txn = self.create_txn(
            user=user,
            transaction_type='deposit',
            amount=amount,
            payment_method=payment_method,
            metadata=kwargs.get('metadata', {})
        )
        
        try:
            # Convert amount to cents (Stripe uses cents)
            amount_cents = int(amount * 100)
            
            # Create Stripe Payment Intent
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency='usd',  # or 'bdt' if available
                metadata={
                    'user_id': str(user.id),
                    'GatewayTransaction_id': str(txn.id),
                    'reference_id': txn.reference_id
                },
                description=f"Deposit for {user.username}",
                statement_descriptor_suffix="DEPOSIT",
                automatic_payment_methods={
                    'enabled': True,
                    'allow_redirects': 'never'
                }
            )
            
            # Update txn
            txn.gateway_reference = payment_intent.id
            txn.metadata['stripe_payment_intent'] = {
                'id': payment_intent.id,
                'client_secret': payment_intent.client_secret,
                'status': payment_intent.status,
                'amount': payment_intent.amount / 100
            }
            txn.save()
            
            return {
                'transaction': txn,
                'client_secret': payment_intent.client_secret,
                'payment_intent_id': payment_intent.id,
                'public_key': self.public_key
            }
            
        except stripe.error.StripeError as e:
            txn.status = 'failed'
            txn.metadata['stripe_error'] = str(e)
            txn.save()
            raise Exception(f"Stripe deposit failed: {str(e)}")
    
    def process_withdrawal(self, user, amount, payment_method, **kwargs):
        """Process Stripe withdrawal (Payout)"""
        self.validate_amount(amount)
        
        with db_txn.atomic():
            # Check if user has Stripe Connect account
            stripe_account_id = user.metadata.get('stripe_account_id') if hasattr(user, 'metadata') else None
            
            if not stripe_account_id:
                raise Exception("User does not have Stripe Connect account")
            
            # Create payout request
            payout = PayoutRequest.objects.create(
                user=user,
                amount=amount,
                fee=self.calculate_fee(amount),
                net_amount=amount - self.calculate_fee(amount),
                payout_method='stripe',
                account_number=payment_method.account_number,
                account_name=payment_method.account_name,
                status='pending',
                reference_id=self.generate_reference_id()
            )
            
            # Create txn record
            txn = self.create_txn(
                user=user,
                transaction_type='withdrawal',
                amount=amount,
                payment_method=payment_method,
                metadata={
                    'payout_id': payout.id,
                    'stripe_account_id': stripe_account_id,
                    **kwargs.get('metadata', {})
                }
            )
            
            try:
                # Create Stripe Transfer
                transfer = stripe.Transfer.create(
                    amount=int(amount * 100),  # Convert to cents
                    currency='usd',
                    destination=stripe_account_id,
                    metadata={
                        'user_id': str(user.id),
                        'GatewayTransaction_id': str(txn.id),
                        'payout_id': str(payout.id)
                    },
                    description=f"Payout to {user.username}"
                )
                
                # Update txn and payout
                txn.gateway_reference = transfer.id
                txn.metadata['stripe_transfer'] = {
                    'id': transfer.id,
                    'amount': transfer.amount / 100,
                    'status': transfer.status
                }
                txn.save()
                
                payout.gateway_reference = transfer.id
                payout.status = 'processing'
                payout.save()
                
                # Deduct from user balance
                user.balance -= amount
                user.save()
                
                return {
                    'transaction': txn,
                    'payout': payout,
                    'transfer_id': transfer.id,
                    'message': 'Withdrawal processing started'
                }
                
            except stripe.error.StripeError as e:
                txn.status = 'failed'
                txn.metadata['stripe_error'] = str(e)
                txn.save()
                
                payout.status = 'failed'
                payout.save()
                
                raise Exception(f"Stripe withdrawal failed: {str(e)}")
    
    def verify_payment(self, payment_intent_id, **kwargs):
        """Verify Stripe payment"""
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            # Find txn
            try:
                txn = TxnModel.objects.get(gateway_reference=payment_intent_id)
                
                if payment_intent.status == 'succeeded':
                    txn.status = 'completed'
                    txn.completed_at = timezone.now()
                    txn.metadata['stripe_verification'] = {
                        'status': payment_intent.status,
                        'amount_received': payment_intent.amount_received / 100,
                        'payment_method': payment_intent.payment_method
                    }
                    
                    # Update user balance
                    user = txn.user
                    user.balance += txn.net_amount
                    user.save()
                elif payment_intent.status in ['canceled', 'requires_payment_method']:
                    txn.status = 'failed'
                    txn.metadata['stripe_verification'] = {
                        'status': payment_intent.status,
                        'last_payment_error': payment_intent.last_payment_error
                    }
                
                txn.save()
                return txn
                
            except TxnModel.DoesNotExist:
                return None
                
        except stripe.error.StripeError as e:
            raise Exception(f"Payment verification failed: {str(e)}")
    
    def get_payment_url(self, txn, **kwargs):
        """Get Stripe payment URL (Checkout Session)"""
        try:
            # Create Checkout Session for web payment
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': 'Account Deposit',
                        },
                        'unit_amount': int(txn.amount * 100),
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=kwargs.get('success_url', ''),
                cancel_url=kwargs.get('cancel_url', ''),
                client_reference_id=txn.reference_id,
                metadata={
                    'user_id': str(txn.user.id),
                    'GatewayTransaction_id': str(txn.id)
                }
            )
            
            txn.gateway_reference = checkout_session.id
            txn.metadata['stripe_checkout'] = {
                'id': checkout_session.id,
                'url': checkout_session.url
            }
            txn.save()
            
            return checkout_session.url
            
        except stripe.error.StripeError as e:
            raise Exception(f"Checkout session creation failed: {str(e)}")
    
    def create_customer(self, user):
        """Create Stripe customer for user"""
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.get_full_name() or user.username,
                metadata={
                    'user_id': str(user.id),
                    'username': user.username
                }
            )
            
            return customer.id
            
        except stripe.error.StripeError as e:
            raise Exception(f"Customer creation failed: {str(e)}")
    
    def create_connect_account(self, user, **kwargs):
        """Create Stripe Connect account for user"""
        try:
            account = stripe.Account.create(
                type='express',
                country='US',  # or 'BD' for Bangladesh
                email=user.email,
                capabilities={
                    'transfers': {'requested': True},
                },
                metadata={
                    'user_id': str(user.id),
                    'username': user.username
                }
            )
            
            # Create account link for onboarding
            account_link = stripe.AccountLink.create(
                account=account.id,
                refresh_url=kwargs.get('refresh_url', ''),
                return_url=kwargs.get('return_url', ''),
                type='account_onboarding'
            )
            
            return {
                'account_id': account.id,
                'onboarding_url': account_link.url
            }
            
        except stripe.error.StripeError as e:
            raise Exception(f"Connect account creation failed: {str(e)}")