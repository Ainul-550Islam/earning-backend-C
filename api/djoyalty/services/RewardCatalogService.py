# api/djoyalty/services/RewardCatalogService.py
"""
Reward Catalog Service -- Browse, filter and redeem catalog items।
World: Open Loyalty reward catalog, Snipp rewards platform।
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class RewardCatalogService:
    """
    Reward catalog browsing and redemption।

    Usage:
        catalog = RewardCatalogService.get_for_customer(customer)
        result = RewardCatalogService.redeem(customer, item_id=5)
    """

    @staticmethod
    def get_for_customer(customer, reward_type: str = '',
                          category_id: int = None,
                          max_points: float = None) -> list:
        """
        Get catalog items available for customer।
        Filters by tier, stock, validity and customer's balance।
        """
        from ..models.catalog import RewardCatalogItem
        from django.db.models import Q

        now = timezone.now()
        qs = RewardCatalogItem.objects.filter(
            is_active=True,
        ).filter(
            Q(valid_from__isnull=True) | Q(valid_from__lte=now)
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=now)
        ).filter(
            Q(stock_quantity__isnull=True) |
            Q(stock_quantity__gt=0)
        )

        if reward_type:
            qs = qs.filter(reward_type=reward_type)
        if category_id:
            qs = qs.filter(category_id=category_id)
        if max_points is not None:
            qs = qs.filter(points_cost__lte=Decimal(str(max_points)))

        # Tier filter
        current_tier = customer.user_tiers.filter(is_current=True).select_related('tier').first()
        if current_tier:
            qs = qs.filter(
                Q(min_tier__isnull=True) |
                Q(min_tier__rank__lte=current_tier.tier.rank)
            )

        return list(qs.order_by('-is_featured', 'sort_order', 'points_cost'))

    @staticmethod
    @transaction.atomic
    def redeem(customer, item_id: int) -> dict:
        """
        Redeem a catalog item with points।
        Returns: {'success': True, 'redemption_id': int, 'item': name}
        """
        from ..models.catalog import RewardCatalogItem
        from ..models.points import LoyaltyPoints, PointsLedger
        from ..choices import LEDGER_DEBIT

        try:
            item = RewardCatalogItem.objects.select_for_update().get(id=item_id)
        except RewardCatalogItem.DoesNotExist:
            return {'success': False, 'error': 'Item not found'}

        if not item.is_available():
            return {'success': False, 'error': 'Item not currently available'}

        # Check customer already redeemed max times
        from ..models.redemption import RedemptionHistory
        already_redeemed = RedemptionHistory.objects.filter(
            customer=customer,
            description__icontains=f'Catalog#{item_id}',
        ).count()
        if already_redeemed >= item.max_per_customer:
            return {'success': False, 'error': f'Maximum redemptions ({item.max_per_customer}) reached'}

        # Check balance
        lp = LoyaltyPoints.objects.select_for_update().filter(customer=customer).first()
        if not lp or lp.balance < item.points_cost:
            balance = lp.balance if lp else Decimal('0')
            return {
                'success': False,
                'error': f'Insufficient points: {balance} / {item.points_cost} required',
            }

        # Deduct points
        old_balance = lp.balance
        lp.debit(item.points_cost)

        # Ledger entry
        PointsLedger.objects.create(
            customer=customer,
            tenant=customer.tenant,
            txn_type=LEDGER_DEBIT,
            source='redemption',
            points=item.points_cost,
            balance_after=lp.balance,
            description=f'Catalog redemption: {item.name} (#{item_id})',
        )

        # Update stock
        item.redeemed_count += 1
        item.save(update_fields=['redeemed_count'])

        # Create redemption history record
        from ..models.redemption import RedemptionHistory
        history = RedemptionHistory.objects.create(
            customer=customer,
            tenant=customer.tenant,
            redemption_type=item.reward_type,
            points_used=item.points_cost,
            cash_value=item.cash_value,
            description=f'Catalog#{item_id}: {item.name}',
            status='approved',
        )

        # Notify customer
        try:
            from .NotificationService import NotificationService
            NotificationService.send(
                customer, 'offer_available',
                title=f'🎁 {item.name} Redeemed!',
                body=f'{item.points_cost} পয়েন্ট ব্যবহার করা হয়েছে। Remaining: {lp.balance}',
                icon='🎁',
                metadata={'item_id': item_id, 'item_name': item.name},
            )
        except Exception:
            pass

        logger.info('RewardCatalogService.redeem: %s redeemed "%s" (%s pts)',
                    customer.code, item.name, item.points_cost)

        return {
            'success': True,
            'redemption_id': history.id,
            'item_name': item.name,
            'points_used': str(item.points_cost),
            'new_balance': str(lp.balance),
            'fulfillment_type': item.fulfillment_type,
        }

    @staticmethod
    def seed_default_catalog(tenant=None):
        """Seed default catalog items for a new tenant।"""
        from ..models.catalog import RewardCatalogCategory, RewardCatalogItem

        categories = [
            {'name': 'Vouchers', 'icon': '🎟️', 'sort_order': 1},
            {'name': 'Gift Cards', 'icon': '💳', 'sort_order': 2},
            {'name': 'Experiences', 'icon': '🎉', 'sort_order': 3},
            {'name': 'Charity', 'icon': '❤️', 'sort_order': 4},
        ]
        cat_objs = {}
        for cat_data in categories:
            cat, _ = RewardCatalogCategory.objects.get_or_create(
                name=cat_data['name'],
                tenant=tenant,
                defaults=cat_data,
            )
            cat_objs[cat_data['name']] = cat

        default_items = [
            {'name': '50 BDT Discount Voucher', 'reward_type': 'voucher',
             'points_cost': Decimal('500'), 'cash_value': Decimal('50'),
             'category': cat_objs.get('Vouchers')},
            {'name': '100 BDT Discount Voucher', 'reward_type': 'voucher',
             'points_cost': Decimal('1000'), 'cash_value': Decimal('100'),
             'category': cat_objs.get('Vouchers')},
            {'name': '200 BDT Gift Card', 'reward_type': 'gift_card',
             'points_cost': Decimal('2000'), 'cash_value': Decimal('200'),
             'category': cat_objs.get('Gift Cards')},
            {'name': 'Donate 50 BDT to Charity', 'reward_type': 'charity',
             'points_cost': Decimal('500'), 'cash_value': Decimal('50'),
             'category': cat_objs.get('Charity')},
        ]
        created = 0
        for item_data in default_items:
            _, was_created = RewardCatalogItem.objects.get_or_create(
                name=item_data['name'],
                tenant=tenant,
                defaults=item_data,
            )
            if was_created:
                created += 1
        logger.info('RewardCatalogService.seed: created %d items', created)
        return created
