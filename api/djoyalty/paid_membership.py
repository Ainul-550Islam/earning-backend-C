# api/djoyalty/paid_membership.py
"""
Djoyalty Paid Membership -- Amazon Prime / Costco style paid loyalty subscriptions।
Members pay monthly/annually for premium loyalty benefits।

2025 trend: Paid memberships with verified ROI outperform free programs।
Examples: Amazon Prime, Costco, Zalando Plus, Sephora Flash।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class MembershipPlan(models.Model):
    """
    Paid membership plan definition।
    e.g. Basic ৳99/month, Premium ৳299/month, Annual ৳999/year।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='membership_plans',
    )
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    plan_code = models.CharField(max_length=30, unique=True)

    billing_cycle = models.CharField(
        max_length=10,
        choices=[('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('annual', 'Annual')],
        default='monthly',
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='BDT')

    # Benefits
    welcome_points = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'),
                                          verbose_name='Bonus points on joining')
    monthly_bonus_points = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'),
                                                verbose_name='Monthly bonus points credit')
    earn_multiplier = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1'),
                                           verbose_name='Points earn multiplier (e.g. 2x)')
    free_cashout_per_month = models.PositiveIntegerField(default=0,
                                                          verbose_name='Free cashouts per month')
    priority_support = models.BooleanField(default=False)
    exclusive_offers = models.BooleanField(default=False, verbose_name='Access exclusive offers')
    early_access = models.BooleanField(default=False, verbose_name='Early access to new features')

    # Tier unlock
    min_tier = models.ForeignKey(
        'djoyalty.LoyaltyTier', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='membership_plans',
        verbose_name='Minimum tier required to join',
    )

    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    max_members = models.PositiveIntegerField(null=True, blank=True,
                                               verbose_name='Max members (null=unlimited)')
    current_members = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Membership Plan'
        ordering = ['sort_order', 'price']

    def get_billing_days(self) -> int:
        return {'monthly': 30, 'quarterly': 90, 'annual': 365}.get(self.billing_cycle, 30)

    def __str__(self):
        return f'MembershipPlan({self.name}: ৳{self.price}/{self.billing_cycle})'


class CustomerMembership(models.Model):
    """
    Customer's active membership subscription।
    Tracks billing, renewal, benefits usage।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='memberships',
    )
    plan = models.ForeignKey(
        MembershipPlan, on_delete=models.PROTECT,
        related_name='subscriptions',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='customer_memberships',
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('paused', 'Paused'),
            ('cancelled', 'Cancelled'),
            ('expired', 'Expired'),
            ('trial', 'Free Trial'),
        ],
        default='active',
    )

    # Billing
    started_at = models.DateTimeField(default=timezone.now)
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)

    # Payment reference
    payment_reference = models.CharField(max_length=200, null=True, blank=True)
    payment_method = models.CharField(max_length=30, default='bkash')
    auto_renew = models.BooleanField(default=True)

    # Usage tracking
    cashouts_used_this_month = models.PositiveIntegerField(default=0)
    last_bonus_credited_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer Membership'
        ordering = ['-started_at']

    @property
    def is_active(self) -> bool:
        return self.status in ('active', 'trial') and self.current_period_end > timezone.now()

    @property
    def days_remaining(self) -> int:
        if not self.is_active:
            return 0
        delta = self.current_period_end - timezone.now()
        return max(delta.days, 0)

    def renew(self, payment_ref: str = '') -> bool:
        """Renew membership for another billing cycle।"""
        if self.status not in ('active', 'expired'):
            return False
        self.current_period_start = timezone.now()
        self.current_period_end = timezone.now() + timedelta(days=self.plan.get_billing_days())
        self.status = 'active'
        self.payment_reference = payment_ref or self.payment_reference
        self.cashouts_used_this_month = 0
        self.save()
        logger.info('CustomerMembership: renewed %s -> %s', self.customer.code, self.plan.name)
        return True

    def cancel(self) -> bool:
        """Cancel membership (remains active until period end)।"""
        self.status = 'cancelled'
        self.auto_renew = False
        self.cancelled_at = timezone.now()
        self.save(update_fields=['status', 'auto_renew', 'cancelled_at'])
        logger.info('CustomerMembership: cancelled for %s', self.customer.code)
        return True

    def __str__(self):
        return f'Membership({self.customer.code}: {self.plan.name} [{self.status}])'


class MembershipBenefitsManager:
    """
    Manages paid membership benefits।
    Apply earn multipliers, credit monthly bonuses, check cashout limits।
    """

    @staticmethod
    def get_active_membership(customer) -> CustomerMembership:
        """Get customer's currently active membership।"""
        return CustomerMembership.objects.filter(
            customer=customer,
            status__in=['active', 'trial'],
            current_period_end__gt=timezone.now(),
        ).select_related('plan').first()

    @staticmethod
    def get_earn_multiplier(customer) -> Decimal:
        """Get earn multiplier from active membership (default 1x)।"""
        membership = MembershipBenefitsManager.get_active_membership(customer)
        if membership:
            return membership.plan.earn_multiplier
        return Decimal('1')

    @staticmethod
    def can_free_cashout(customer) -> bool:
        """Check if customer has remaining free cashouts this month।"""
        membership = MembershipBenefitsManager.get_active_membership(customer)
        if not membership:
            return False
        return membership.cashouts_used_this_month < membership.plan.free_cashout_per_month

    @staticmethod
    def record_cashout_used(customer):
        """Record a cashout against the free monthly allowance।"""
        membership = MembershipBenefitsManager.get_active_membership(customer)
        if membership:
            membership.cashouts_used_this_month += 1
            membership.save(update_fields=['cashouts_used_this_month'])

    @staticmethod
    @transaction.atomic
    def credit_monthly_bonus(membership: CustomerMembership) -> bool:
        """Credit monthly bonus points to member।"""
        if membership.plan.monthly_bonus_points <= 0:
            return False
        now = timezone.now()
        # Only credit once per period
        if membership.last_bonus_credited_at:
            if membership.last_bonus_credited_at >= membership.current_period_start:
                return False  # Already credited this period

        try:
            from .repositories import PointsRepository
            PointsRepository.credit(
                customer=membership.customer,
                points=membership.plan.monthly_bonus_points,
                source='subscription',
                reference_id=f'MEMBERSHIP-BONUS-{membership.id}-{now.strftime("%Y%m")}',
                description=f'Monthly membership bonus: {membership.plan.name}',
            )
            membership.last_bonus_credited_at = now
            membership.save(update_fields=['last_bonus_credited_at'])
            logger.info('MembershipBenefitsManager: credited %s bonus pts to %s',
                        membership.plan.monthly_bonus_points, membership.customer.code)
            return True
        except Exception as e:
            logger.error('MembershipBenefitsManager.credit_monthly_bonus error: %s', e)
            return False

    @staticmethod
    def join_membership(customer, plan: MembershipPlan,
                         payment_ref: str = '', trial_days: int = 0) -> CustomerMembership:
        """
        Customer joins a paid membership plan।
        Creates subscription, credits welcome points, applies tier benefits。
        """
        now = timezone.now()
        period_end = now + timedelta(days=trial_days if trial_days else plan.get_billing_days())

        membership = CustomerMembership.objects.create(
            customer=customer,
            plan=plan,
            tenant=customer.tenant,
            status='trial' if trial_days else 'active',
            current_period_start=now,
            current_period_end=period_end,
            trial_ends_at=now + timedelta(days=trial_days) if trial_days else None,
            payment_reference=payment_ref,
        )

        # Update member count
        plan.current_members += 1
        plan.save(update_fields=['current_members'])

        # Credit welcome points
        if plan.welcome_points > 0:
            try:
                from .repositories import PointsRepository
                PointsRepository.credit(
                    customer=customer,
                    points=plan.welcome_points,
                    source='subscription',
                    reference_id=f'MEMBERSHIP-WELCOME-{membership.id}',
                    description=f'Welcome bonus: {plan.name} membership',
                )
            except Exception as e:
                logger.debug('join_membership welcome points error: %s', e)

        # Notify
        try:
            from .services.NotificationService import NotificationService
            NotificationService.send(
                customer, 'campaign_active',
                title=f'🎉 {plan.name} Member!',
                body=f'স্বাগতম! আপনি {plan.name} member হয়েছেন। {plan.earn_multiplier}x points এবং আরও সুবিধা।',
                priority='high',
            )
        except Exception:
            pass

        # Audit log
        try:
            from .models.audit import AdminAuditLog
            AdminAuditLog.log(
                action='membership_joined',
                category='customer',
                customer=customer,
                new_value={'plan': plan.name, 'price': str(plan.price)},
            )
        except Exception:
            pass

        logger.info('MembershipBenefitsManager: %s joined %s', customer.code, plan.name)
        return membership
