# api/djoyalty/repositories.py
"""
Djoyalty Repositories -- Data access layer (Repository Pattern)।
Abstracts all DB queries into reusable repository classes।
Pattern: Repository (DDD / Clean Architecture)।
"Do not summarize or skip any logic. Provide the full code."
"""
from decimal import Decimal
from typing import Optional, List
from django.db.models import QuerySet


class CustomerRepository:
    """Repository for Customer data access।"""

    @staticmethod
    def get_by_id(customer_id: int, active_only: bool = True):
        from .models.core import Customer
        qs = Customer.objects.filter(id=customer_id)
        if active_only:
            qs = qs.filter(is_active=True)
        return qs.first()

    @staticmethod
    def get_by_code(code: str, tenant=None):
        from .models.core import Customer
        qs = Customer.objects.filter(code=code.upper(), is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.first()

    @staticmethod
    def get_by_phone(phone: str, tenant=None):
        from .models.core import Customer
        from .helpers import normalize_bd_phone
        normalized = normalize_bd_phone(phone)
        if not normalized:
            return None
        qs = Customer.objects.filter(phone=normalized, is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.first()

    @staticmethod
    def get_by_email(email: str, tenant=None):
        from .models.core import Customer
        qs = Customer.objects.filter(email__iexact=email.strip(), is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.first()

    @staticmethod
    def create(code: str, email: str = '', phone: str = '',
               firstname: str = '', lastname: str = '', tenant=None):
        from .models.core import Customer
        return Customer.objects.create(
            code=code.upper(),
            email=email or None,
            phone=phone or None,
            firstname=firstname or None,
            lastname=lastname or None,
            tenant=tenant,
        )

    @staticmethod
    def update(customer, **fields):
        for k, v in fields.items():
            setattr(customer, k, v)
        customer.save(update_fields=list(fields.keys()))
        return customer

    @staticmethod
    def deactivate(customer):
        customer.is_active = False
        customer.save(update_fields=['is_active'])

    @staticmethod
    def list_by_tenant(tenant, active_only: bool = True, limit: int = 100) -> QuerySet:
        from .models.core import Customer
        qs = Customer.objects.filter(tenant=tenant)
        if active_only:
            qs = qs.filter(is_active=True)
        return qs.order_by('-created_at')[:limit]

    @staticmethod
    def count(tenant=None, active_only: bool = True) -> int:
        from .models.core import Customer
        qs = Customer.objects.all()
        if active_only:
            qs = qs.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs.count()


class PointsRepository:
    """Repository for LoyaltyPoints data access।"""

    @staticmethod
    def get_or_create(customer):
        from .models.points import LoyaltyPoints
        lp, created = LoyaltyPoints.objects.get_or_create(
            customer=customer,
            defaults={'tenant': customer.tenant, 'balance': Decimal('0')},
        )
        return lp, created

    @staticmethod
    def get_balance(customer) -> Decimal:
        from .models.points import LoyaltyPoints
        lp = LoyaltyPoints.objects.filter(customer=customer).first()
        return lp.balance if lp else Decimal('0')

    @staticmethod
    def credit(customer, points: Decimal, source: str, reference_id: str = '',
                description: str = '') -> object:
        """Credit points and create ledger entry -- atomic।"""
        from django.db import transaction
        from .models.points import LoyaltyPoints, PointsLedger
        from .choices import LEDGER_CREDIT

        with transaction.atomic():
            lp, _ = LoyaltyPoints.objects.select_for_update().get_or_create(
                customer=customer,
                defaults={'tenant': customer.tenant, 'balance': Decimal('0')},
            )
            lp.balance += points
            lp.lifetime_earned += points
            lp.save(update_fields=['balance', 'lifetime_earned', 'updated_at'])

            return PointsLedger.objects.create(
                customer=customer,
                tenant=customer.tenant,
                txn_type=LEDGER_CREDIT,
                source=source,
                points=points,
                balance_after=lp.balance,
                description=description,
                reference_id=reference_id,
            )

    @staticmethod
    def debit(customer, points: Decimal, source: str, reference_id: str = '',
               description: str = '') -> object:
        """Debit points and create ledger entry -- atomic।"""
        from django.db import transaction
        from .models.points import LoyaltyPoints, PointsLedger
        from .choices import LEDGER_DEBIT

        with transaction.atomic():
            lp = LoyaltyPoints.objects.select_for_update().filter(customer=customer).first()
            if not lp or lp.balance < points:
                raise ValueError(
                    f'Insufficient balance: {lp.balance if lp else 0} < {points}'
                )
            lp.balance -= points
            lp.lifetime_redeemed += points
            lp.save(update_fields=['balance', 'lifetime_redeemed', 'updated_at'])

            return PointsLedger.objects.create(
                customer=customer,
                tenant=customer.tenant,
                txn_type=LEDGER_DEBIT,
                source=source,
                points=points,
                balance_after=lp.balance,
                description=description,
                reference_id=reference_id,
            )

    @staticmethod
    def get_ledger(customer, limit: int = 50) -> QuerySet:
        from .models.points import PointsLedger
        return PointsLedger.objects.filter(
            customer=customer, is_reversed=False
        ).order_by('-created_at')[:limit]


class VoucherRepository:
    """Repository for Voucher data access।"""

    @staticmethod
    def get_by_code(code: str, active_only: bool = True):
        from .models.redemption import Voucher
        from django.utils import timezone
        qs = Voucher.objects.filter(code=code.upper())
        if active_only:
            qs = qs.filter(status='active')
            qs = qs.filter(
                __import__('django.db.models', fromlist=['Q']).Q(expires_at__isnull=True) |
                __import__('django.db.models', fromlist=['Q']).Q(expires_at__gt=timezone.now())
            )
        return qs.first()

    @staticmethod
    def create(customer, code: str, voucher_type: str, discount_value: Decimal,
               min_purchase: Decimal = Decimal('0'), days_valid: int = 30):
        from .models.redemption import Voucher
        from django.utils import timezone
        from datetime import timedelta
        return Voucher.objects.create(
            customer=customer,
            tenant=customer.tenant,
            code=code.upper(),
            voucher_type=voucher_type,
            discount_value=discount_value,
            min_purchase_amount=min_purchase,
            status='active',
            expires_at=timezone.now() + timedelta(days=days_valid),
        )

    @staticmethod
    def mark_used(voucher, order_ref: str = ''):
        from django.utils import timezone
        voucher.status = 'used'
        voucher.used_at = timezone.now()
        if order_ref:
            voucher.used_in_order = order_ref
        voucher.save(update_fields=['status', 'used_at'])


class NotificationRepository:
    """Repository for Notification data access।"""

    @staticmethod
    def create(customer, notification_type: str, title: str, body: str,
               icon: str = '🔔', metadata: dict = None):
        from .models.notifications import NotificationCenter
        from django.utils import timezone
        return NotificationCenter.objects.create(
            customer=customer,
            tenant=customer.tenant,
            title=title,
            body=body,
            icon=icon,
            notification_type=notification_type,
            metadata=metadata or {},
            is_sent=True,
            sent_at=timezone.now(),
        )

    @staticmethod
    def get_unread(customer, limit: int = 20) -> QuerySet:
        from .models.notifications import NotificationCenter
        return NotificationCenter.objects.filter(
            customer=customer, is_read=False
        ).order_by('-created_at')[:limit]

    @staticmethod
    def mark_all_read(customer) -> int:
        from .models.notifications import NotificationCenter
        from django.utils import timezone
        return NotificationCenter.objects.filter(
            customer=customer, is_read=False
        ).update(is_read=True, read_at=timezone.now())

    @staticmethod
    def unread_count(customer) -> int:
        from .models.notifications import NotificationCenter
        return NotificationCenter.objects.filter(customer=customer, is_read=False).count()


class AuditRepository:
    """Repository for audit logging।"""

    @staticmethod
    def log(action: str, category: str = 'other', customer=None,
            performed_by: str = 'system', old_value=None,
            new_value=None, description: str = '',
            severity: str = 'info', tenant=None):
        from .models.audit import AdminAuditLog
        return AdminAuditLog.log(
            action=action, category=category, customer=customer,
            performed_by=performed_by, old_value=old_value,
            new_value=new_value, description=description,
            severity=severity, tenant=tenant,
        )

    @staticmethod
    def get_customer_history(customer, limit: int = 50) -> QuerySet:
        from .models.audit import AdminAuditLog
        return AdminAuditLog.objects.filter(
            customer=customer
        ).order_by('-timestamp')[:limit]
