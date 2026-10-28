# api/djoyalty/services/OfferWallService.py
"""
OfferWallService -- CPAlead-style offer completion + postback processing।
Handles: offer display, completion tracking, postback verification, points award।
"""
import hashlib
import hmac
import logging
from django.db import models as django_models
from django.db.models import Q as models_Q
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class OfferWallService:

    @staticmethod
    def get_available_offers(customer, offer_wall_id: int,
                              country_code: str = '', device_type: str = 'android') -> list:
        """Customer এর জন্য available offers get করো।"""
        from ..models.offerwall import Offer, OfferCompletion
        from django.utils import timezone

        qs = Offer.objects.filter(
            offer_wall_id=offer_wall_id,
            status='active',
        ).filter(
            django_models.Q(valid_from__isnull=True) | django_models.Q(valid_from__lte=timezone.now())
        ).filter(
            django_models.Q(valid_until__isnull=True) | django_models.Q(valid_until__gte=timezone.now())
        )

        # Geo filter
        if country_code:
            qs = qs.filter(
                django_models.Q(geo_targets=[]) | django_models.Q(geo_targets__contains=country_code)
            )

        # Completed offers this customer can't do again
        completed_ids = set(
            OfferCompletion.objects.filter(
                customer=customer,
                status__in=['verified', 'points_awarded'],
            ).filter(
                offer__max_completions_per_user=1,
            ).values_list('offer_id', flat=True)
        )

        if completed_ids:
            qs = qs.exclude(id__in=completed_ids)

        return list(qs.order_by('-is_featured', 'sort_order', '-points_reward'))

    @staticmethod
    @transaction.atomic
    def process_postback(offer_wall_id: int, raw_data: dict,
                          signature: str = '', ip_address: str = '') -> dict:
        """
        Process incoming postback from CPAlead/Tapjoy/Xsolla।
        Verify signature -> find customer -> award points।

        Expected raw_data format (CPAlead style):
        {
            'subid': 'customer_code',    # or user_id
            'payout': '1.50',            # USD payout
            'offer_id': '12345',
            'transaction_id': 'txn_abc',
            'ip': '1.2.3.4',
        }
        """
        from ..models.offerwall import OfferWall, Offer, OfferCompletion, OfferPostbackLog

        # Log raw postback first
        log = OfferPostbackLog.objects.create(
            offer_wall_id=offer_wall_id,
            raw_data=raw_data,
            ip_address=ip_address,
            customer_ref=raw_data.get('subid', raw_data.get('user_id', '')),
            offer_id=str(raw_data.get('offer_id', '')),
            transaction_id=raw_data.get('transaction_id', raw_data.get('txn_id', '')),
            payout=Decimal(str(raw_data.get('payout', 0))) if raw_data.get('payout') else None,
        )

        try:
            offer_wall = OfferWall.objects.get(id=offer_wall_id, is_active=True)
        except OfferWall.DoesNotExist:
            log.error_message = 'OfferWall not found'
            log.save()
            return {'success': False, 'error': 'OfferWall not found'}

        # Verify signature
        sig_valid = OfferWallService._verify_signature(offer_wall, raw_data, signature)
        log.signature_valid = sig_valid
        log.save(update_fields=['signature_valid'])

        if not sig_valid and offer_wall.postback_secret:
            log.error_message = 'Invalid signature'
            log.processed = True
            log.save()
            logger.warning('OfferWallService: invalid postback signature for wall %d', offer_wall_id)
            return {'success': False, 'error': 'Invalid signature'}

        # Find customer
        customer_ref = raw_data.get('subid', raw_data.get('user_id', ''))
        from ..models.core import Customer
        try:
            customer = Customer.objects.get(
                django_models.Q(code=customer_ref) | django_models.Q(id=customer_ref),
                is_active=True,
            )
        except Customer.DoesNotExist:
            log.error_message = f'Customer not found: {customer_ref}'
            log.processed = True
            log.save()
            return {'success': False, 'error': f'Customer not found: {customer_ref}'}

        # Find offer
        offer_id = raw_data.get('offer_id')
        txn_id = raw_data.get('transaction_id', raw_data.get('txn_id', ''))
        payout = Decimal(str(raw_data.get('payout', 0))) if raw_data.get('payout') else Decimal('0')

        offer = None
        if offer_id:
            offer = Offer.objects.filter(
                offer_wall=offer_wall,
                external_offer_id=str(offer_id),
            ).first()

        # Duplicate check
        if txn_id:
            existing = OfferCompletion.objects.filter(
                provider_transaction_id=txn_id,
            ).first()
            if existing:
                log.error_message = f'Duplicate txn: {txn_id}'
                log.processed = True
                log.save()
                return {'success': False, 'error': 'Duplicate transaction'}

        # Calculate points
        if offer:
            points = offer.points_reward
        else:
            # Use currency ratio
            points = payout * offer_wall.currency_ratio

        if points <= 0:
            log.error_message = 'Zero points calculated'
            log.processed = True
            log.save()
            return {'success': False, 'error': 'Zero points'}

        # Create completion record
        completion = OfferCompletion.objects.create(
            customer=customer,
            offer=offer or Offer.objects.filter(offer_wall=offer_wall).first(),
            offer_wall=offer_wall,
            tenant=customer.tenant,
            postback_received=True,
            postback_data=raw_data,
            provider_transaction_id=txn_id,
            advertiser_payout_received=payout,
            status='verified',
            points_awarded=points,
            ip_address=ip_address,
            postback_at=timezone.now(),
        )

        # Award points
        from ..models.points import LoyaltyPoints, PointsLedger
        from ..choices import LEDGER_CREDIT

        lp, _ = LoyaltyPoints.objects.get_or_create(
            customer=customer,
            defaults={'tenant': customer.tenant, 'balance': Decimal('0')},
        )
        lp.credit(points)

        PointsLedger.objects.create(
            customer=customer,
            tenant=customer.tenant,
            txn_type=LEDGER_CREDIT,
            source='bonus',
            points=points,
            balance_after=lp.balance,
            description=f'Offer completed: {offer.title if offer else "OfferWall"} ({payout} USD)',
            reference_id=f'OFFER-{completion.id}',
        )

        completion.status = 'points_awarded'
        completion.save(update_fields=['status'])

        log.processed = True
        log.points_credited = points
        log.processed_at = timezone.now()
        log.save()

        logger.info(
            'OfferWallService: postback processed -- %s +%s pts (txn=%s payout=$%s)',
            customer.code, points, txn_id, payout,
        )

        return {
            'success': True,
            'customer_code': customer.code,
            'points_awarded': str(points),
            'completion_id': completion.id,
        }

    @staticmethod
    def _verify_signature(offer_wall, raw_data: dict, signature: str) -> bool:
        """Verify postback signature (HMAC SHA256)।"""
        if not offer_wall.postback_secret:
            return True  # No secret configured = accept all
        if not signature:
            return False
        try:
            payload = '&'.join(f'{k}={v}' for k, v in sorted(raw_data.items()))
            expected = hmac.new(
                offer_wall.postback_secret.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception:
            return False

    @staticmethod
    def get_customer_offer_stats(customer) -> dict:
        """Customer offer stats।"""
        from ..models.offerwall import OfferCompletion
        from django.db.models import Sum, Count
        stats = OfferCompletion.objects.filter(
            customer=customer, status='points_awarded',
        ).aggregate(
            total_completions=Count('id'),
            total_points=Sum('points_awarded'),
            total_payout=Sum('advertiser_payout_received'),
        )
        return {
            'total_completions': stats['total_completions'] or 0,
            'total_points_earned': str(stats['total_points'] or 0),
            'total_advertiser_payout_usd': str(stats['total_payout'] or 0),
        }


