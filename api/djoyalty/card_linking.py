# api/djoyalty/card_linking.py
"""
Djoyalty Card Linking -- Card-Linked Loyalty (CLO)।
Customers link their Visa/Mastercard/bKash card।
When they pay with that card, points auto-earn।
Reference: Fidel API, Mastercard Loyalty Services, bKash card linking।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class LinkedCard(models.Model):
    """
    Customer's linked payment card for automatic earn।
    Card number stored as tokenized reference (never store raw PAN)।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='linked_cards',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='linked_cards',
    )

    # Card info (tokenized -- no raw PAN stored)
    card_token = models.CharField(max_length=200, unique=True,
                                   verbose_name='Card token from payment provider')
    card_scheme = models.CharField(
        max_length=20,
        choices=[
            ('visa', 'Visa'),
            ('mastercard', 'Mastercard'),
            ('amex', 'American Express'),
            ('bkash_card', 'bKash Card'),
            ('nagad_card', 'Nagad Card'),
        ],
        default='visa',
    )
    last_four = models.CharField(max_length=4)
    expiry_month = models.PositiveSmallIntegerField(null=True, blank=True)
    expiry_year = models.PositiveSmallIntegerField(null=True, blank=True)
    cardholder_name = models.CharField(max_length=200, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    # Earn settings
    earn_enabled = models.BooleanField(default=True)
    earn_multiplier = models.DecimalField(max_digits=5, decimal_places=2,
                                           default='1.00')

    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Linked Card'
        verbose_name_plural = 'Linked Cards'
        ordering = ['-created_at']

    def masked_number(self) -> str:
        return f'**** **** **** {self.last_four}'

    def __str__(self):
        return f'LinkedCard({self.customer.code}: {self.card_scheme} {self.masked_number()})'


class CardTransactionWebhook(models.Model):
    """
    Incoming transaction notification from card network/provider।
    When customer pays with linked card -> webhook received -> points awarded।
    """
    linked_card = models.ForeignKey(
        LinkedCard, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='transaction_webhooks',
    )
    customer = models.ForeignKey(
        'djoyalty.Customer', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='card_transactions',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='card_transaction_webhooks',
    )

    provider_transaction_id = models.CharField(max_length=200, unique=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=10, default='BDT')
    merchant_name = models.CharField(max_length=200, null=True, blank=True)
    merchant_category = models.CharField(max_length=50, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ('received', 'Received'),
            ('processed', 'Points Awarded'),
            ('declined', 'Declined (no points)'),
            ('duplicate', 'Duplicate -- skipped'),
        ],
        default='received',
    )
    points_awarded = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    raw_webhook_data = models.JSONField(default=dict)

    received_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Card Transaction Webhook'
        ordering = ['-received_at']


class CardLinkingService:
    """
    Card linking loyalty service।
    Link cards, process transactions, award points।

    Usage:
        CardLinkingService.link_card(customer, card_token='tok_visa_xxx',
                                      card_scheme='visa', last_four='4242')
        CardLinkingService.process_transaction(transaction_id='txn_123',
                                                card_token='tok_visa_xxx',
                                                amount=Decimal('1500'))
    """

    @staticmethod
    def link_card(customer, card_token: str, card_scheme: str = 'visa',
                   last_four: str = '', expiry_month: int = None,
                   expiry_year: int = None, cardholder_name: str = '') -> LinkedCard:
        """Link a payment card to a customer's loyalty account."""
        card, created = LinkedCard.objects.update_or_create(
            card_token=card_token,
            defaults={
                'customer': customer,
                'tenant': customer.tenant,
                'card_scheme': card_scheme,
                'last_four': last_four,
                'expiry_month': expiry_month,
                'expiry_year': expiry_year,
                'cardholder_name': cardholder_name,
                'is_active': True,
            },
        )
        action = 'linked' if created else 'updated'
        logger.info('CardLinkingService: %s %s card for %s',
                    action, card_scheme, customer.code)

        # Notify customer
        try:
            from .services.NotificationService import NotificationService
            NotificationService.send(
                customer, 'campaign_active',
                title='💳 Card Linked!',
                body=f'আপনার {card_scheme.title()} card (*{last_four}) loyalty এ link হয়েছে। এখন থেকে auto points!',
            )
        except Exception:
            pass

        return card

    @staticmethod
    def unlink_card(card_token: str, customer=None) -> bool:
        """Deactivate a linked card."""
        qs = LinkedCard.objects.filter(card_token=card_token)
        if customer:
            qs = qs.filter(customer=customer)
        updated = qs.update(is_active=False)
        return bool(updated)

    @staticmethod
    def process_transaction(transaction_id: str, card_token: str,
                             amount, currency: str = 'BDT',
                             merchant_name: str = '', merchant_category: str = '',
                             raw_data: dict = None) -> dict:
        """
        Process a card transaction webhook -> award loyalty points।
        Called when customer pays with linked card at any merchant।
        """
        from decimal import Decimal

        amount = Decimal(str(amount))

        # Find linked card
        card = LinkedCard.objects.filter(
            card_token=card_token, is_active=True, earn_enabled=True
        ).select_related('customer').first()

        if not card:
            return {'success': False, 'error': 'Card not found or earn disabled'}

        customer = card.customer

        # Check for duplicate
        from .idempotency import IdempotencyGuard
        guard = IdempotencyGuard('card_transaction', transaction_id=transaction_id)
        if guard.already_processed():
            return {'success': True, 'duplicate': True, **guard.get_cached_result()}

        # Create webhook record
        webhook = CardTransactionWebhook.objects.create(
            linked_card=card,
            customer=customer,
            tenant=customer.tenant,
            provider_transaction_id=transaction_id,
            amount=amount,
            currency=currency,
            merchant_name=merchant_name,
            merchant_category=merchant_category,
            raw_webhook_data=raw_data or {},
        )

        # Calculate and award points
        try:
            from .logic import calculate_earn_points
            points = calculate_earn_points(
                transaction_value=amount,
                earn_rate=Decimal('1'),
                multiplier=card.earn_multiplier,
            )

            from .repositories import PointsRepository
            ledger = PointsRepository.credit(
                customer=customer,
                points=points,
                source='card_transaction',
                reference_id=transaction_id,
                description=f'Card earn: {merchant_name or card_token[:10]} ৳{amount}',
            )

            webhook.status = 'processed'
            webhook.points_awarded = points
            webhook.processed_at = timezone.now()
            webhook.save(update_fields=['status', 'points_awarded', 'processed_at'])

            card.last_used_at = timezone.now()
            card.save(update_fields=['last_used_at'])

            result = {
                'success': True,
                'points_awarded': str(points),
                'new_balance': str(ledger.balance_after),
                'customer_code': customer.code,
            }
            guard.mark_processed(result)

            logger.info('CardLinkingService: awarded %s pts to %s for card txn %s',
                        points, customer.code, transaction_id)
            return result

        except Exception as e:
            webhook.status = 'declined'
            webhook.save(update_fields=['status'])
            logger.error('CardLinkingService.process_transaction error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_customer_cards(customer) -> list:
        """Get all active linked cards for a customer."""
        return list(
            LinkedCard.objects.filter(customer=customer, is_active=True)
            .order_by('-created_at')
        )
