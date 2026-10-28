# api/djoyalty/models/cashout.py
"""
Djoyalty Cashout / Wallet Models -- World-class cashout system।
Points -> Bank Transfer, bKash/Nagad, Mobile Wallet।

World reference: Starbucks Rewards cashout, Capital One miles redemption,
Vodafone loyalty cash withdrawal।

AUDIT FIXES (v2 -- Financial Integrity):
  CashoutRequest.customer:
    Changed on_delete=CASCADE → PROTECT।  Cashout records are permanent
    financial audit trails; a customer deletion must be blocked until records
    are archived (soft-delete on Customer model instead)।

  WalletTransaction.customer:
    Same reasoning -- wallet transaction log must survive customer deletion।

  CashoutRequest.Meta.constraints:
    1. CheckConstraint `cashout_destination_matches_method`:
       Enforces at DB level that bank_transfer method has bank_account set (not
       mobile_wallet), mobile_wallet method has mobile_wallet set (not
       bank_account), and gift_card/store_credit allow both null।
       Previously only enforced by CashoutRequestCreateSerializer.validate()
       which is bypassed for programmatic creates (admin, Celery, migrations)।

    2. UniqueConstraint `unique_active_cashout_per_customer`:
       Partial unique constraint: only one CashoutRequest per customer may be
       in status 'pending' or 'approved' at a time।  Prevents the race condition
       where a customer with spotty network submits the same cashout twice, both
       pass validation before either commits, and both deduct points।
"""
import logging
from decimal import Decimal
from django.db import models
from django.utils import timezone
from ..managers import ActiveManager, PendingManager

logger = logging.getLogger(__name__)


class CustomerBankAccount(models.Model):
    """
    Customer এর registered bank account for cashout।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='bank_accounts', verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='customer_bank_accounts',
    )
    bank_name = models.CharField(max_length=200, verbose_name='Bank Name')
    account_number = models.CharField(max_length=50, verbose_name='Account Number')
    account_holder_name = models.CharField(max_length=200, verbose_name='Account Holder Name')
    routing_number = models.CharField(max_length=30, null=True, blank=True, verbose_name='Routing/IFSC Code')
    branch_name = models.CharField(max_length=200, null=True, blank=True, verbose_name='Branch Name')
    is_verified = models.BooleanField(default=False, verbose_name='Verified')
    is_primary = models.BooleanField(default=False, verbose_name='Primary Account')
    is_active = models.BooleanField(default=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer Bank Account'
        verbose_name_plural = 'Customer Bank Accounts'
        ordering = ['-is_primary', '-created_at']
        # AUDIT FIX (v1): Added indexes -- (customer, is_primary) used on every
        # cashout to find the customer's primary account -- was causing full table scan
        indexes = [
            models.Index(fields=['customer', 'is_primary']),
            models.Index(fields=['customer', 'is_active']),
        ]

    def __str__(self):
        return f'Bank({self.customer.code}: {self.bank_name} ****{self.account_number[-4:]})'


class CustomerMobileWallet(models.Model):
    """
    Customer এর mobile wallet (bKash, Nagad, Rocket) for cashout।
    Bangladesh-specific + international support।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer', on_delete=models.CASCADE,
        related_name='mobile_wallets', verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='customer_mobile_wallets',
    )
    wallet_provider = models.CharField(
        max_length=30,
        choices=[
            ('bkash', 'bKash'),
            ('nagad', 'Nagad'),
            ('rocket', 'Rocket (Dutch-Bangla)'),
            ('upay', 'Upay'),
            ('paytm', 'Paytm'),
            ('other', 'Other'),
        ],
        default='bkash',
        verbose_name='Wallet Provider',
    )
    phone_number = models.CharField(max_length=20, verbose_name='Mobile Number')
    account_name = models.CharField(max_length=200, null=True, blank=True, verbose_name='Account Name')
    is_verified = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Customer Mobile Wallet'
        verbose_name_plural = 'Customer Mobile Wallets'
        ordering = ['-is_primary', '-created_at']
        unique_together = [('customer', 'wallet_provider', 'phone_number')]
        # AUDIT FIX (4): (customer, is_primary) covers primary-wallet lookup on
        # every cashout; (customer, is_active) covers list-wallets page.
        indexes = [
            models.Index(fields=['customer', 'is_primary'],
                         name='mobwallet_customer_primary_idx'),
            models.Index(fields=['customer', 'is_active'],
                         name='mobwallet_customer_active_idx'),
            models.Index(fields=['wallet_provider', 'is_active'],
                         name='mobwallet_provider_active_idx'),
        ]

    def __str__(self):
        return f'MobileWallet({self.customer.code}: {self.wallet_provider} {self.phone_number})'


class CashoutRequest(models.Model):
    """
    Customer এর points -> cash cashout request।
    World: Starbucks Stars -> cash, airline miles -> bank transfer।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        # AUDIT FIX (v2): CASCADE → PROTECT।  Cashout records are permanent
        # financial audit trails; customer deletion must be blocked until they
        # are archived।  Use soft-delete (is_deleted=True) on Customer instead।
        on_delete=models.PROTECT,
        related_name='cashout_requests', verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='cashout_requests',
    )

    points_to_redeem = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name='Points to Redeem',
    )
    cash_amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name='Cash Amount (calculated)',
    )
    conversion_rate = models.DecimalField(
        max_digits=10, decimal_places=6,
        verbose_name='Conversion Rate Applied',
        help_text='Cash per 1 point',
    )
    currency = models.CharField(max_length=10, default='BDT', verbose_name='Currency')

    cashout_method = models.CharField(
        max_length=20,
        choices=[
            ('bank_transfer', 'Bank Transfer'),
            ('mobile_wallet', 'Mobile Wallet (bKash/Nagad)'),
            ('gift_card', 'Gift Card'),
            ('store_credit', 'Store Credit'),
        ],
        default='bank_transfer',
        verbose_name='Cashout Method',
    )

    # Destination -- exclusively one of the two for bank_transfer / mobile_wallet
    bank_account = models.ForeignKey(
        CustomerBankAccount, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='cashout_requests',
        verbose_name='Bank Account',
    )
    mobile_wallet = models.ForeignKey(
        CustomerMobileWallet, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='cashout_requests',
        verbose_name='Mobile Wallet',
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('rejected', 'Rejected'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending',
        verbose_name='Status',
    )

    reference = models.CharField(max_length=100, null=True, blank=True, unique=True, verbose_name='Reference')
    payment_reference = models.CharField(max_length=200, null=True, blank=True, verbose_name='Payment Reference')

    reviewed_by = models.CharField(max_length=200, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)
    admin_note = models.TextField(null=True, blank=True)

    # Fraud check
    fraud_score = models.PositiveIntegerField(default=0, verbose_name='Fraud Score (0-100)')
    is_flagged = models.BooleanField(default=False, verbose_name='Flagged for Review')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()
    pending = PendingManager()

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Cashout Request'
        verbose_name_plural = 'Cashout Requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['reference']),
            # AUDIT FIX (v1): Added (tenant, status) -- used in tenant-scoped
            # admin dashboard queries
            models.Index(fields=['tenant', 'status']),
        ]
        constraints = [
            # AUDIT FIX (v2): Enforce destination-method consistency at DB level।
            # Previously only enforced in CashoutRequestCreateSerializer.validate()
            # which is bypassed for programmatic creates (admin commands, Celery,
            # data migrations)।
            # Rules:
            #   bank_transfer  -> bank_account set,    mobile_wallet null
            #   mobile_wallet  -> mobile_wallet set,   bank_account null
            #   gift_card      -> both null allowed
            #   store_credit   -> both null allowed
            models.CheckConstraint(check=(
                    (
                        models.Q(cashout_method='bank_transfer') &
                        models.Q(bank_account__isnull=False) &
                        models.Q(mobile_wallet__isnull=True)
                    ) | (
                        models.Q(cashout_method='mobile_wallet') &
                        models.Q(mobile_wallet__isnull=False) &
                        models.Q(bank_account__isnull=True)
                    ) | (
                        models.Q(cashout_method__in=['gift_card', 'store_credit'])
                    )
                ),
                name='cashout_destination_matches_method',
            ),
            # AUDIT FIX (v2): Prevent double-cashout submission।
            # Partial unique constraint: only one active (pending/approved)
            # CashoutRequest per customer at a time।  Prevents the race condition
            # where spotty network causes two simultaneous submissions।
            # Migration: 0014_financial_integrity_constraints.py
            models.UniqueConstraint(
                fields=['customer'],
                condition=models.Q(status__in=['pending', 'approved']),
                name='unique_active_cashout_per_customer',
            ),
        ]

    def __str__(self):
        return (
            f'Cashout(#{self.id}: {self.customer.code} -- '
            f'{self.points_to_redeem}pts -> {self.cash_amount} [{self.status}])'
        )


class CashoutRate(models.Model):
    """
    Configurable cashout conversion rate per tenant।
    Points -> Cash rate -- can vary by tier, amount, etc।
    """
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='cashout_rates',
    )
    cashout_method = models.CharField(
        max_length=20,
        choices=[
            ('bank_transfer', 'Bank Transfer'),
            ('mobile_wallet', 'Mobile Wallet'),
            ('gift_card', 'Gift Card'),
            ('store_credit', 'Store Credit'),
        ],
        default='bank_transfer',
    )
    points_per_unit = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('100'),
        verbose_name='Points per 1 Currency Unit',
        help_text='e.g. 100 means 100 points = 1 BDT',
    )
    min_cashout_points = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('500'),
        verbose_name='Minimum Points for Cashout',
    )
    max_cashout_points_per_day = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('10000'),
        verbose_name='Max Points Cashout per Day',
    )
    processing_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        verbose_name='Processing Fee %',
    )
    min_tier_required = models.ForeignKey(
        'djoyalty.LoyaltyTier', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='cashout_rates',
        verbose_name='Minimum Tier for Cashout',
    )
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField(default=timezone.now)

    objects = models.Manager()
    active = ActiveManager()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Cashout Rate'
        verbose_name_plural = 'Cashout Rates'
        ordering = ['-effective_from']
        # AUDIT FIX (4): (tenant, cashout_method, is_active) covers the primary
        # rate lookup on every cashout request.
        indexes = [
            models.Index(fields=['tenant', 'cashout_method'],
                         name='cashrate_tenant_method_idx'),
            models.Index(fields=['tenant', 'is_active'],
                         name='cashrate_tenant_active_idx'),
            models.Index(fields=['is_active', 'effective_from'],
                         name='cashrate_active_from_idx'),
        ]

    def __str__(self):
        return f'CashoutRate({self.cashout_method}: {self.points_per_unit} pts = 1 BDT)'


class WalletTransaction(models.Model):
    """
    Internal loyalty wallet transaction log।
    Every points credit/debit + cashout recorded here।
    World: Starbucks Stars wallet, Capital One digital wallet।
    """
    customer = models.ForeignKey(
        'djoyalty.Customer',
        # AUDIT FIX (v2): CASCADE → PROTECT।  Wallet transaction log is a
        # permanent financial audit trail; customer deletion must be blocked।
        on_delete=models.PROTECT,
        related_name='wallet_transactions', verbose_name='Customer',
    )
    tenant = models.ForeignKey(
        'djoyalty.Tenant', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='wallet_transactions',
    )

    transaction_type = models.CharField(
        max_length=20,
        choices=[
            ('earn', 'Points Earned'),
            ('redeem', 'Points Redeemed'),
            ('cashout', 'Cash Withdrawn'),
            ('transfer_in', 'Transfer Received'),
            ('transfer_out', 'Transfer Sent'),
            ('expiry', 'Points Expired'),
            ('adjustment', 'Admin Adjustment'),
            ('bonus', 'Bonus'),
            ('reversal', 'Reversal'),
        ],
        verbose_name='Transaction Type',
    )
    points_delta = models.DecimalField(
        max_digits=14, decimal_places=2,
        verbose_name='Points Change (+/-)',
    )
    cash_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Cash Amount (if cashout)',
    )
    currency = models.CharField(max_length=10, default='BDT')
    balance_before = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Balance Before',
    )
    balance_after = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Balance After',
    )
    description = models.CharField(max_length=500, null=True, blank=True)
    reference_id = models.CharField(max_length=100, null=True, blank=True)

    # Linked records
    cashout_request = models.ForeignKey(
        CashoutRequest, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='wallet_transactions',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'djoyalty'
        verbose_name = 'Wallet Transaction'
        verbose_name_plural = 'Wallet Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['reference_id']),
        ]

    def __str__(self):
        sign = '+' if self.points_delta >= 0 else ''
        return f'WalletTxn({self.customer.code}: {sign}{self.points_delta} [{self.transaction_type}])'
