# wallet/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import uuid
from datetime import timedelta

class Wallet(models.Model):
    """User wallet - auto-created on signup"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    # user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    # wallet/models.py ফাইলে
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet_wallet_user', null=True, blank=True)
    
    # v1 - Basic balances
    current_balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Available balance for withdrawal")
    pending_balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Pending approval/verification")
    total_earned = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Lifetime earnings")
    total_withdrawn = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Total amount withdrawn")
    frozen_balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Locked due to fraud/dispute")
    
    # v2 - Advanced features
    bonus_balance = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Bonus/promotional balance")
    bonus_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Wallet status
    is_locked = models.BooleanField(default=False)
    locked_reason = models.TextField(blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    
    # Currency (v2)
    currency = models.CharField(max_length=3, default='BDT', null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wallet'
        app_label = 'wallet'
    
    def __str__(self):
        return f"{self.user.username} - {self.current_balance} {self.currency}"
    
    @property
    def available_balance(self):
        """Total available for withdrawal"""
        return self.current_balance - self.frozen_balance
    
    def lock(self, reason):
        """Lock wallet"""
        self.is_locked = True
        self.locked_reason = reason
        self.locked_at = timezone.now()
        self.save()
    
    def unlock(self):
        """Unlock wallet"""
        self.is_locked = False
        self.locked_reason = ''
        self.locked_at = None
        self.save()
    
    def freeze(self, amount, reason):
        """Freeze specific amount"""
        if amount > self.current_balance:
            raise ValueError("Insufficient balance to freeze")
        
        self.frozen_balance += amount
        self.current_balance -= amount
        self.save()
        
        # Log GatewayTransaction
        WalletTransaction.objects.create(
            wallet=self,
            type='freeze',
            amount=-amount,
            status='approved',
            description=f"Frozen: {reason}"
        )
    
    def unfreeze(self, amount, reason):
        """Unfreeze amount"""
        if amount > self.frozen_balance:
            raise ValueError("Cannot unfreeze more than frozen amount")
        
        self.frozen_balance -= amount
        self.current_balance += amount
        self.save()
        
        # Log GatewayTransaction
        WalletTransaction.objects.create(
            wallet=self,
            type='unfreeze',
            amount=amount,
            status='approved',
            description=f"Unfrozen: {reason}"
        )


class WalletTransaction(models.Model):
    """WalletTransaction ledger - all wallet operations"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    
    WalletTransaction_TYPES = [
        ('earning', 'Earning'),
        ('reward', 'Reward'),
        ('referral', 'Referral Commission'),
        ('bonus', 'Bonus'),
        ('withdrawal', 'Withdrawal'),
        ('withdrawal_fee', 'Withdrawal Fee'),
        ('admin_credit', 'Admin Credit'),
        ('admin_debit', 'Admin Debit'),
        ('freeze', 'Freeze'),
        ('unfreeze', 'Unfreeze'),
        ('reversal', 'Reversal'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('reversed', 'Reversed'),
    ]
    
    # Core fields
    walletTransaction_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='%(app_label)s_%(class)s_tenant')
    
    # GatewayTransaction details
    type = models.CharField(max_length=20, choices=WalletTransaction_TYPES, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', null=True, blank=True)
    
    # References
    reference_id = models.CharField(max_length=100, blank=True, help_text="External reference", null=True)
    reference_type = models.CharField(max_length=50, null=True, blank=True)
    
    # Balances snapshot (for audit)
    balance_before = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    
    # Details
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # v2 - Double entry ledger
    debit_account = models.CharField(max_length=50, null=True, blank=True)
    credit_account = models.CharField(max_length=50, null=True, blank=True)
    
    # Reversal support
    is_reversed = models.BooleanField(default=False)
    reversed_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    reversed_at = models.DateTimeField(null=True, blank=True)
    
    # Audit
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_wallettransaction_created_by')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_wallettransaction_approved_by')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        app_label = 'wallet'
        db_table = 'WalletTransaction'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', '-created_at']),
            models.Index(fields=['walletTransaction_id']),
            models.Index(fields=['type', 'status']),
            models.Index(fields=['reference_id']),
        ]
    
    def __str__(self):
        return f"{self.WalletTransaction_id} - {self.type} - {self.amount}"
    
    def approve(self, approved_by=None):
        """Approve pending WalletTransaction"""
        if self.status != 'pending':
            raise ValueError(f"Cannot approve WalletTransaction with status: {self.status}")
        
        self.status = 'approved'
        self.approved_by = approved_by
        self.approved_at = timezone.now()
        
        # Update wallet balance
        if self.amount > 0:
            self.wallet.current_balance += self.amount
        else:
            if abs(self.amount) > self.wallet.current_balance:
                raise ValueError("Insufficient balance")
            self.wallet.current_balance += self.amount  # amount is negative
        
        self.balance_after = self.wallet.current_balance
        self.wallet.save()
        self.save()
    
    def reject(self, reason=''):
        """Reject WalletTransaction"""
        if self.status != 'pending':
            raise ValueError(f"Cannot reject WalletTransaction with status: {self.status}")
        
        self.status = 'rejected'
        self.description += f" | Rejected: {reason}"
        self.save()
    
    def reverse(self, reason='', reversed_by=None):
        """Reverse completed WalletTransaction"""
        if self.status not in ['approved', 'completed']:
            raise ValueError("Can only reverse approved/completed WalletTransactions")
        
        if self.is_reversed:
            raise ValueError("WalletTransaction already reversed")
        
        # Create reversal GatewayTransaction
        reversal = WalletTransaction.objects.create(
            wallet=self.wallet,
            type='reversal',
            amount=-self.amount,
            status='approved',
            reference_id=str(self.WalletTransaction_id),
            reference_type='reversal',
            description=f"Reversal of {self.WalletTransaction_id}: {reason}",
            balance_before=self.wallet.current_balance,
            created_by=reversed_by,
            approved_by=reversed_by,
            approved_at=timezone.now()
        )
        
        # Update wallet
        self.wallet.current_balance -= self.amount
        reversal.balance_after = self.wallet.current_balance
        self.wallet.save()
        
        # Mark original as reversed
        self.is_reversed = True
        self.reversed_by = reversal
        self.reversed_at = timezone.now()
        self.save()
        
        return reversal


# wallet/models.py এর শেষে এই মডেলগুলো যোগ করুন

class UserPaymentMethod(models.Model):
    """Payment methods for withdrawals"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    METHOD_CHOICES = [
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('rocket', 'Rocket'),
        ('upay', 'Upay'),
        ('bank', 'Bank Account'),
        ('card', 'Debit/Credit Card'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet_userpaymentmethod_user', null=True, blank=True)
    method_type = models.CharField(max_length=20, choices=METHOD_CHOICES, null=True, blank=True)
    account_number = models.CharField(max_length=50, null=True, blank=True)
    account_name = models.CharField(max_length=100, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)
    
    # Bank specific fields
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    branch_name = models.CharField(max_length=100, null=True, blank=True)
    routing_number = models.CharField(max_length=50, null=True, blank=True)
    
    # Card specific fields
    card_last_four = models.CharField(max_length=4, null=True, blank=True)
    card_expiry = models.CharField(max_length=7, null=True, blank=True)  # MM/YYYY format
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.get_method_type_display()} - {self.account_number}"
    
    class Meta:
        app_label = 'wallet'
        ordering = ['-is_primary', '-created_at']


class WalletWebhookLog(models.Model):
    """Log payment gateway webhook calls"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    WEBHOOK_TYPES = [
        ('bkash', 'bKash'),
        ('nagad', 'Nagad'),
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('sslcommerz', 'SSLCommerz'),
    ]
    
    webhook_type = models.CharField(max_length=20, choices=WEBHOOK_TYPES, null=True, blank=True)
    event_type = models.CharField(max_length=100, null=True, blank=True)
    payload = models.JSONField()
    headers = models.JSONField(default=dict, blank=True)
    
    # Status
    is_processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    
    # References
    reference_id = models.CharField(max_length=100, null=True, blank=True)
    WalletTransaction_reference = models.CharField(max_length=100, null=True, blank=True)
    
    # Timestamps
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.webhook_type} - {self.event_type} - {self.received_at}"
    
    class Meta:
        app_label = 'wallet'
        ordering = ['-received_at']


# যদি Withdrawal মডেলও লাগে:
class Withdrawal(models.Model):
    """Withdrawal requests"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('failed', 'Failed'),
    ]
    
    withdrawal_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet_withdrawal_user', null=True, blank=True)
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='wallet_withdrawal_wallet', null=True, blank=True)
    payment_method = models.ForeignKey(UserPaymentMethod, on_delete=models.SET_NULL, null=True, blank=True)
    
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    fee = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', null=True, blank=True)
    
    # GatewayTransaction reference
    wallet_transaction = models.OneToOneField(WalletTransaction, on_delete=models.CASCADE, null=True, blank=True, related_name='%(app_label)s_%(class)s_tenant'
    )
    
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
    on_delete=models.SET_NULL, 
    null=True, 
    blank=True, 
    related_name='wallet_withdrawal_processed_by'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Rejection info
    rejection_reason = models.TextField(blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    
    # Payment gateway response
    gateway_reference = models.CharField(max_length=100, null=True, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.withdrawal_id} - {self.user.username} - {self.amount}"
    
    def save(self, *args, **kwargs):
        if not self.net_amount and self.amount and self.fee:
            self.net_amount = self.amount - self.fee
        super().save(*args, **kwargs)
    
    class Meta:
        app_label = 'wallet'
        ordering = ['-created_at']
        
        
        
class WithdrawalRequest(models.Model):

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet_withdrawalrequest_user', null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="ইউজার যত টাকা তুলতে চায়", null=True, blank=True)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="উইথড্র ফি (যা অ্যাডমিনের লাভ, null=True, blank=True)")
    
    # পেমেন্ট মেথড (বিকাশ, নগদ বা রকেট হতে পারে)
    method = models.CharField(max_length=50, help_text="Payment Method (e.g., Bkash, Nagad, null=True, blank=True)")
    account_number = models.CharField(max_length=20, help_text="ইউজারের পেমেন্ট একাউন্ট নাম্বার", null=True, blank=True)
    
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending', null=True, blank=True)
    
    admin_note = models.TextField(blank=True, help_text="রিজেক্ট করলে কারণ এখানে লেখা যাবে")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.amount} ({self.status})"
    
    class Meta:
        app_label = 'wallet'

    def __str__(self):
        return f"{self.user.username} - {self.amount} ({self.status})"