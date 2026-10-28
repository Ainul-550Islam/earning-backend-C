# api/djoyalty/services/FamilyAccountService.py
"""
FamilyAccountService -- family loyalty account management।
World: Antavo Global Loyalty Report 2025 -- family accounts top desired feature।
Airlines: family miles pooling। Retail: household accounts।
"""
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class FamilyAccountService:

    @staticmethod
    @transaction.atomic
    def create_family_account(owner, name: str, pool_points: bool = True,
                               max_members: int = 5, tenant=None):
        """Create family loyalty account।"""
        from ..models.family_eco import FamilyAccount, FamilyMember

        # Transfer owner's current balance to family pool
        lp = owner.loyalty_points.first()
        initial_balance = lp.balance if lp and pool_points else Decimal('0')

        account = FamilyAccount.objects.create(
            tenant=tenant or owner.tenant,
            name=name,
            owner=owner,
            pool_points=pool_points,
            shared_balance=initial_balance,
            max_members=max_members,
        )

        # Add owner as first member
        FamilyMember.objects.create(
            family_account=account,
            customer=owner,
            role='owner',
            can_redeem=True,
            can_transfer=True,
            points_contributed=initial_balance,
        )

        logger.info('FamilyAccountService: created %s for %s', name, owner.code)
        return account

    @staticmethod
    @transaction.atomic
    def add_member(account, new_customer, role: str = 'adult', invited_by=None, tenant=None):
        """Add member to family account।"""
        from ..models.family_eco import FamilyAccount, FamilyMember
        from ..exceptions import DjoyaltyBaseError

        current_count = account.members.filter(is_active=True).count()
        if current_count >= account.max_members:
            raise DjoyaltyBaseError(f'Family account is full (max {account.max_members} members).')

        if FamilyMember.objects.filter(family_account=account, customer=new_customer).exists():
            raise DjoyaltyBaseError('Customer is already a member of this family account.')

        member = FamilyMember.objects.create(
            family_account=account,
            customer=new_customer,
            role=role,
            invited_by=invited_by,
        )

        logger.info('FamilyAccountService: %s joined family %s', new_customer.code, account.name)
        return member

    @staticmethod
    @transaction.atomic
    def pool_points_from_member(account, member_customer, points: Decimal):
        """Member এর points family pool এ contribute করো।"""
        from ..models.points import LoyaltyPoints, PointsLedger
        from ..models.family_eco import FamilyMember
        from ..exceptions import InsufficientPointsError
        from ..choices import LEDGER_DEBIT, LEDGER_CREDIT

        lp = member_customer.loyalty_points.first()
        if not lp or lp.balance < points:
            raise InsufficientPointsError(available=lp.balance if lp else 0, required=points)

        lp.debit(points)
        PointsLedger.objects.create(
            customer=member_customer,
            tenant=account.tenant,
            txn_type=LEDGER_DEBIT,
            source='transfer',
            points=points,
            balance_after=lp.balance,
            description=f'Pooled to family: {account.name}',
        )

        account.shared_balance += points
        account.shared_lifetime_earned += points
        account.save(update_fields=['shared_balance', 'shared_lifetime_earned'])

        member = FamilyMember.objects.filter(family_account=account, customer=member_customer).first()
        if member:
            member.points_contributed += points
            member.save(update_fields=['points_contributed'])

        return account.shared_balance

    @staticmethod
    def get_family_summary(account) -> dict:
        """Family account summary।"""
        members = account.members.filter(is_active=True).select_related('customer')
        return {
            'account_code': account.account_code,
            'name': account.name,
            'owner': account.owner.code,
            'shared_balance': str(account.shared_balance),
            'shared_lifetime_earned': str(account.shared_lifetime_earned),
            'member_count': members.count(),
            'members': [
                {
                    'code': m.customer.code,
                    'name': m.customer.full_name,
                    'role': m.role,
                    'contributed': str(m.points_contributed),
                }
                for m in members
            ],
        }

    @staticmethod
    def invite_member(account, email: str = '', customer_code: str = '',
                      role: str = 'adult', invited_by=None, tenant=None) -> dict:
        """
        Invite a new member to a family account by email or customer code.
        Alias wrapping add_member() with lookup logic.
        """
        try:
            from ..models.core import Customer
            from django.db.models import Q

            # Find customer by email or code
            customer = None
            if customer_code:
                customer = Customer.objects.filter(code=customer_code).first()
            elif email:
                customer = Customer.objects.filter(email=email).first()

            if not customer:
                return {'success': False, 'error': 'Customer not found with provided email/code'}

            result = FamilyAccountService.add_member(
                account=account,
                new_customer=customer,
                role=role,
                invited_by=invited_by,
                tenant=tenant,
            )
            return result if isinstance(result, dict) else {
                'success': True,
                'member': {'customer_id': customer.id, 'code': customer.code, 'role': role},
            }
        except Exception as e:
            import logging
            logging.getLogger(__name__).error('FamilyAccountService.invite_member error: %s', e)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_shared_transactions(account, limit: int = 50) -> list:
        """
        Get all transactions from all members of a family account.
        Shows pooled activity across the family.
        """
        try:
            from ..models.family_eco import FamilyMember
            from ..models.core import Txn
            from django.db.models import Q

            member_customers = FamilyMember.objects.filter(
                family_account=account, is_active=True,
            ).values_list('customer_id', flat=True)

            txns = Txn.objects.filter(
                customer_id__in=member_customers,
            ).select_related('customer').order_by('-timestamp')[:limit]

            return [
                {
                    'txn_id': t.id,
                    'customer_id': t.customer_id,
                    'customer_code': t.customer.code if t.customer else '',
                    'value': str(t.value),
                    'is_discount': t.is_discount,
                    'timestamp': t.timestamp.isoformat() if t.timestamp else None,
                }
                for t in txns
            ]
        except Exception as e:
            import logging
            logging.getLogger(__name__).error('FamilyAccountService.get_shared_transactions error: %s', e)
            return []
