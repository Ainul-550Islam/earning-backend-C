# api/djoyalty/services/gamification/ScratchCardService.py
"""
ScratchCardService -- Issue and reveal scratch cards with prizes.
World reference: Voucherify scratch cards, Smile.io gamification.

Flow:
  1. issue()  -> creates a ScratchCard record for a customer (unrevealed)
  2. reveal() -> customer scratches, prize is determined + awarded
"""
import logging
import random
import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Prize distribution table (override per-tenant via ScratchCard.prize_config)
DEFAULT_PRIZE_TABLE = [
    {'prize_type': 'points',   'label': '50 Points',   'value': Decimal('50'),  'weight': 40},
    {'prize_type': 'points',   'label': '100 Points',  'value': Decimal('100'), 'weight': 25},
    {'prize_type': 'points',   'label': '200 Points',  'value': Decimal('200'), 'weight': 15},
    {'prize_type': 'voucher',  'label': '5% Discount', 'value': Decimal('5'),   'weight': 10},
    {'prize_type': 'voucher',  'label': '10% Discount','value': Decimal('10'),  'weight': 5},
    {'prize_type': 'no_prize', 'label': 'Try Again',   'value': Decimal('0'),   'weight': 5},
]


class ScratchCardService:

    @staticmethod
    @transaction.atomic
    def issue(customer, trigger: str = 'purchase',
              source_reference: str = '', tenant=None) -> dict:
        """
        Issue a scratch card to customer.
        Returns: {'success': True, 'card_id': int, 'card_code': str}
        """
        try:
            from ...models.gamification import ScratchCard

            # Check if customer already has an unscratched card
            existing = ScratchCard.objects.filter(
                customer=customer,
                is_scratched=False,
                expires_at__gt=timezone.now(),
            ).first()
            if existing:
                return {
                    'success': True,
                    'card_id': existing.id,
                    'card_code': existing.card_code,
                    'already_existed': True,
                }

            card_code = f'SC-{uuid.uuid4().hex[:10].upper()}'
            expires_at = timezone.now() + __import__('datetime').timedelta(days=30)

            card = ScratchCard.objects.create(
                customer=customer,
                tenant=tenant or getattr(customer, 'tenant', None),
                card_code=card_code,
                trigger=trigger,
                source_reference=source_reference,
                is_scratched=False,
                expires_at=expires_at,
            )

            logger.info('ScratchCardService.issue: card %s issued to %s',
                        card_code, customer.code)

            return {
                'success': True,
                'card_id': card.id,
                'card_code': card_code,
                'expires_at': expires_at.isoformat(),
            }

        except Exception as e:
            logger.error('ScratchCardService.issue error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    @transaction.atomic
    def reveal(customer, card_id: int = None,
               card_code: str = None, tenant=None) -> dict:
        """
        Reveal scratch card -- determine prize and award it.
        Returns: {'success': True, 'prize_type': ..., 'prize_label': ..., 'points_awarded': ...}
        """
        try:
            from ...models.gamification import ScratchCard

            # Lookup card
            qs = ScratchCard.objects.select_for_update().filter(customer=customer)
            if card_id:
                qs = qs.filter(id=card_id)
            elif card_code:
                qs = qs.filter(card_code=card_code)
            else:
                return {'success': False, 'error': 'card_id or card_code required'}

            card = qs.first()
            if not card:
                return {'success': False, 'error': 'Scratch card not found'}
            if card.is_scratched:
                return {
                    'success': False,
                    'error': 'Card already scratched',
                    'prize_type': card.prize_type,
                    'prize_label': card.prize_label,
                }
            if card.expires_at and card.expires_at < timezone.now():
                return {'success': False, 'error': 'Scratch card has expired'}

            # Determine prize
            prize_config = getattr(card, 'prize_config', None) or DEFAULT_PRIZE_TABLE
            prize = ScratchCardService._pick_prize(prize_config)

            # Mark scratched
            card.is_scratched = True
            card.scratched_at = timezone.now()
            card.prize_type = prize['prize_type']
            card.prize_label = prize['label']
            card.prize_value = prize['value']
            card.save(update_fields=[
                'is_scratched', 'scratched_at',
                'prize_type', 'prize_label', 'prize_value',
            ])

            # Award prize
            award_result = ScratchCardService._award(customer, prize, tenant)

            logger.info('ScratchCardService.reveal: %s scratched %s -> %s',
                        customer.code, card.card_code, prize['label'])

            return {
                'success': True,
                'card_code': card.card_code,
                'prize_type': prize['prize_type'],
                'prize_label': prize['label'],
                'prize_value': str(prize['value']),
                **award_result,
            }

        except Exception as e:
            logger.error('ScratchCardService.reveal error: %s', e)
            return {'success': False, 'error': str(e)}

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _pick_prize(prize_table: list) -> dict:
        """Weighted random prize selection from prize_table list."""
        try:
            weights = [p.get('weight', 1) for p in prize_table]
            total = sum(weights)
            r = random.uniform(0, total)
            cumulative = 0
            for prize, w in zip(prize_table, weights):
                cumulative += w
                if r <= cumulative:
                    return prize
            return prize_table[-1]
        except Exception as e:
            logger.error('ScratchCardService._pick_prize error: %s', e)
            return {'prize_type': 'no_prize', 'label': 'Try Again',
                    'value': Decimal('0'), 'weight': 1}

    @staticmethod
    def _award(customer, prize: dict, tenant) -> dict:
        """Award the prize to the customer."""
        result = {}
        prize_type = prize.get('prize_type', 'no_prize')

        try:
            if prize_type == 'points' and prize.get('value', 0) > 0:
                from ...services.earn.BonusEventService import BonusEventService
                BonusEventService.award_bonus(
                    customer, prize['value'],
                    reason=f'Scratch card prize: {prize["label"]}',
                    triggered_by='scratch_card',
                    tenant=tenant,
                )
                result['points_awarded'] = prize['value']

            elif prize_type == 'voucher' and prize.get('value', 0) > 0:
                from ...services.redemption.VoucherService import VoucherService
                voucher = VoucherService.create_reward_voucher(
                    customer=customer,
                    discount_value=prize['value'],
                    source='scratch_card',
                    tenant=tenant,
                )
                result['voucher_code'] = getattr(voucher, 'code', None)

        except Exception as e:
            logger.error('ScratchCardService._award error: %s', e)
            result['award_error'] = str(e)

        return result

    @staticmethod
    def scratch(card=None, card_id: int = None, customer=None) -> dict:
        """
        Alias for reveal() -- matches GamificationViewSet call signature.
        """
        cid = card_id or (card.id if hasattr(card, 'id') else None)
        cust = customer or (card.customer if hasattr(card, 'customer') else None)
        if not cust:
            return {'success': False, 'error': 'customer required'}
        return ScratchCardService.reveal(customer=cust, card_id=cid)

    @staticmethod
    def claim(card=None, card_id: int = None, customer=None) -> dict:
        """
        Alias -- in our system reveal() awards immediately. claim() confirms.
        """
        try:
            from ...models.gamification import ScratchCard
            cid = card_id or (card.id if hasattr(card, 'id') else None)
            if cid:
                sc = ScratchCard.objects.filter(id=cid).first()
                if sc and sc.is_scratched:
                    return {
                        'success': True,
                        'already_claimed': True,
                        'prize_type': sc.prize_type,
                        'prize_label': sc.prize_label,
                    }
            return {'success': True, 'already_claimed': True}
        except Exception as e:
            logger.error('ScratchCardService.claim error: %s', e)
            return {'success': False, 'error': str(e)}
