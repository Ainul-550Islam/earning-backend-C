"""
Factory for creating Wallet and Transaction model instances.
"""

import factory
from factory import Faker, LazyAttribute, SubFactory, post_generation
from factory.django import DjangoModelFactory
from django.utils import timezone
from decimal import Decimal
import random
import string
from datetime import datetime, timedelta


class WalletFactory(DjangoModelFactory):
    """Factory for creating Wallet instances"""
    
    class Meta:
        model = 'wallet.Wallet'
        django_get_or_create = ['user']
    
    user = SubFactory('api.tests.factories.UserFactory.UserFactory')
    
    # Financial fields with realistic values
    balance = LazyAttribute(lambda x: Decimal(str(round(random.uniform(0, 10000), 2))))
    total_earned = LazyAttribute(
        lambda x: Decimal(str(round(random.uniform(x.balance * 2, x.balance * 10), 2)))
    )
    total_withdrawn = LazyAttribute(
        lambda x: Decimal(str(round(random.uniform(0, x.total_earned * 0.5), 2)))
    )
    total_deposited = LazyAttribute(
        lambda x: Decimal(str(round(random.uniform(0, x.total_earned * 0.3), 2)))
    )
    
    # Bonus and reward fields
    bonus_balance = LazyAttribute(lambda x: Decimal(str(round(random.uniform(0, 1000), 2))))
    pending_balance = LazyAttribute(lambda x: Decimal(str(round(random.uniform(0, 500), 2))))
    
    # Statistics
    total_transactions = LazyAttribute(lambda x: random.randint(0, 100))
    successful_withdrawals = LazyAttribute(lambda x: random.randint(0, 20))
    failed_withdrawals = LazyAttribute(lambda x: random.randint(0, 5))
    
    # Settings
    auto_withdraw = random.choice([True, False])
    min_withdraw_amount = Decimal('100.00')
    daily_withdraw_limit = Decimal('5000.00')
    monthly_withdraw_limit = Decimal('50000.00')
    
    # Verification
    is_verified = random.choice([True, False])
    verification_level = LazyAttribute(
        lambda x: random.choice(['basic', 'verified', 'premium']) if x.is_verified else 'basic'
    )
    
    @classmethod
    def create_with_low_balance(cls, **kwargs):
        """Create wallet with low balance"""
        return cls.create(
            balance=Decimal('10.00'),
            total_earned=Decimal('50.00'),
            total_withdrawn=Decimal('40.00'),
            **kwargs
        )
    
    @classmethod
    def create_with_high_balance(cls, **kwargs):
        """Create wallet with high balance"""
        return cls.create(
            balance=Decimal('50000.00'),
            total_earned=Decimal('200000.00'),
            total_withdrawn=Decimal('150000.00'),
            **kwargs
        )
    
    @classmethod
    def create_for_withdrawal_test(cls, **kwargs):
        """Create wallet for withdrawal testing"""
        return cls.create(
            balance=Decimal('1000.00'),
            min_withdraw_amount=Decimal('100.00'),
            daily_withdraw_limit=Decimal('5000.00'),
            monthly_withdraw_limit=Decimal('50000.00'),
            is_verified=True,
            **kwargs
        )


class TransactionFactory(DjangoModelFactory):
    """Factory for creating Transaction instances"""
    
    class Meta:
        model = 'wallet.Transaction'
    
    # Basic information
    user = SubFactory('api.tests.factories.UserFactory.UserFactory')
    wallet = SubFactory(WalletFactory)
    
    transaction_id = factory.LazyFunction(
        lambda: f"TXN{''.join(random.choices(string.digits, k=10))}"
    )
    
    # Financial details
    transaction_type = factory.Iterator(['credit', 'debit', 'transfer', 'bonus', 'refund'])
    amount = LazyAttribute(lambda x: Decimal(str(round(random.uniform(10, 5000), 2))))
    currency = factory.Iterator(['BDT', 'USD', 'EUR', 'INR'])
    
    # Status and timing
    status = factory.Iterator([
        'pending', 'completed', 'failed', 'cancelled', 'processing', 'reversed'
    ])
    created_at = factory.LazyFunction(
        lambda: timezone.now() - timedelta(days=random.randint(0, 30))
    )
    completed_at = factory.LazyAttribute(
        lambda x: x.created_at + timedelta(minutes=random.randint(1, 60))
        if x.status == 'completed' else None
    )
    
    # Source/destination details
    source_type = factory.Iterator(['offer', 'referral', 'deposit', 'bonus', 'cashback'])
    source_id = factory.LazyFunction(lambda: random.randint(1000, 9999))
    
    # Payment gateway info (for deposits/withdrawals)
    payment_method = factory.Iterator(['bkash', 'nagad', 'rocket', 'bank', 'card'])
    gateway_transaction_id = factory.LazyFunction(
        lambda: f"GATE{''.join(random.choices(string.ascii_uppercase + string.digits, k=12))}"
    )
    
    # Metadata
    description = factory.LazyFunction(
        lambda: random.choice([
            'Offer completion reward',
            'Referral commission',
            'Withdrawal to bKash',
            'Deposit from Nagad',
            'Welcome bonus',
            'Cashback reward',
            'Manual adjustment',
            'Refund processing'
        ])
    )
    
    metadata = factory.LazyFunction(
        lambda: {
            'ip_address': f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
            'device_id': ''.join(random.choices(string.ascii_letters + string.digits, k=16)),
            'location': random.choice(['Dhaka', 'Chittagong', 'Sylhet']),
            'offer_id': random.randint(1000, 9999) if random.choice([True, False]) else None,
            'referral_code': ''.join(random.choices(string.ascii_uppercase, k=8))
            if random.choice([True, False]) else None
        }
    )
    
    # Fees and taxes
    fee_amount = LazyAttribute(lambda x: x.amount * Decimal('0.02'))  # 2% fee
    tax_amount = LazyAttribute(lambda x: x.amount * Decimal('0.01'))  # 1% tax
    net_amount = LazyAttribute(
        lambda x: x.amount - x.fee_amount - x.tax_amount if x.transaction_type == 'debit' else x.amount
    )
    
    # Bank/account details (for withdrawals)
    account_number = factory.LazyFunction(
        lambda: ''.join(random.choices(string.digits, k=11)) if random.choice([True, False]) else None
    )
    account_name = factory.LazyFunction(
        lambda: random.choice(['John Doe', 'Jane Smith', 'Ali Khan', 'Fatima Ahmed'])
        if random.choice([True, False]) else None
    )
    bank_name = factory.Iterator([
        'Dutch Bangla Bank', 'BRAC Bank', 'Islami Bank', 'City Bank', 'Eastern Bank'
    ])
    branch_name = factory.LazyFunction(
        lambda: random.choice(['Gulshan', 'Banani', 'Dhanmondi', 'Motijheel', 'Uttara'])
    )
    
    @classmethod
    def create_credit_transaction(cls, **kwargs):
        """Create credit transaction"""
        return cls.create(
            transaction_type='credit',
            status='completed',
            description='Credit transaction',
            **kwargs
        )
    
    @classmethod
    def create_debit_transaction(cls, **kwargs):
        """Create debit transaction"""
        return cls.create(
            transaction_type='debit',
            status='completed',
            description='Withdrawal transaction',
            **kwargs
        )
    
    @classmethod
    def create_pending_transaction(cls, **kwargs):
        """Create pending transaction"""
        return cls.create(
            status='pending',
            completed_at=None,
            **kwargs
        )
    
    @classmethod
    def create_failed_transaction(cls, **kwargs):
        """Create failed transaction"""
        return cls.create(
            status='failed',
            description='Transaction failed due to insufficient balance',
            **kwargs
        )
    
    @classmethod
    def create_withdrawal_transaction(cls, **kwargs):
        """Create withdrawal transaction"""
        return cls.create(
            transaction_type='debit',
            payment_method=kwargs.get('payment_method', 'bkash'),
            description='Withdrawal to bKash',
            status='completed',
            **kwargs
        )
    
    @classmethod
    def create_deposit_transaction(cls, **kwargs):
        """Create deposit transaction"""
        return cls.create(
            transaction_type='credit',
            payment_method=kwargs.get('payment_method', 'nagad'),
            description='Deposit from Nagad',
            status='completed',
            **kwargs
        )
    
    @classmethod
    def create_bulk_transactions(cls, user, count=20, **kwargs):
        """Create multiple transactions for a user"""
        transactions = []
        wallet = user.wallet if hasattr(user, 'wallet') else WalletFactory.create(user=user)
        
        for i in range(count):
            transaction = cls.create(
                user=user,
                wallet=wallet,
                transaction_type=random.choice(['credit', 'debit']),
                amount=Decimal(str(round(random.uniform(10, 1000), 2))),
                status=random.choice(['completed', 'pending', 'failed']),
                created_at=timezone.now() - timedelta(days=random.randint(0, 30)),
                **kwargs
            )
            transactions.append(transaction)
        
        return transactions


class WithdrawalRequestFactory(DjangoModelFactory):
    """Factory for creating WithdrawalRequest instances"""
    
    class Meta:
        model = 'wallet.WithdrawalRequest'
    
    user = SubFactory('api.tests.factories.UserFactory.UserFactory')
    wallet = SubFactory(WalletFactory)
    
    # Request details
    request_id = factory.LazyFunction(
        lambda: f"WDR{''.join(random.choices(string.digits, k=12))}"
    )
    amount = LazyAttribute(lambda x: Decimal(str(round(random.uniform(100, 5000), 2))))
    currency = 'BDT'
    payment_method = factory.Iterator(['bkash', 'nagad', 'rocket', 'bank'])
    
    # Account details
    account_number = factory.LazyFunction(lambda: ''.join(random.choices(string.digits, k=11)))
    account_name = Faker('name')
    
    # Status
    status = factory.Iterator(['pending', 'approved', 'processing', 'completed', 'rejected', 'cancelled'])
    status_changed_at = factory.LazyAttribute(
        lambda x: timezone.now() - timedelta(hours=random.randint(1, 24))
        if x.status != 'pending' else None
    )
    
    # Processing
    processed_by = factory.LazyFunction(
        lambda: random.choice(['auto', 'admin', 'system']) if random.choice([True, False]) else None
    )
    processing_fee = LazyAttribute(lambda x: x.amount * Decimal('0.015'))  # 1.5% fee
    tax_amount = LazyAttribute(lambda x: x.amount * Decimal('0.01'))  # 1% tax
    net_amount = LazyAttribute(lambda x: x.amount - x.processing_fee - x.tax_amount)
    
    # Timeline
    requested_at = factory.LazyFunction(
        lambda: timezone.now() - timedelta(hours=random.randint(1, 72))
    )
    approved_at = factory.LazyAttribute(
        lambda x: x.requested_at + timedelta(minutes=random.randint(5, 60))
        if x.status in ['approved', 'processing', 'completed'] else None
    )
    completed_at = factory.LazyAttribute(
        lambda x: x.approved_at + timedelta(minutes=random.randint(10, 120))
        if x.status == 'completed' else None
    )
    
    # Metadata
    notes = factory.LazyFunction(
        lambda: random.choice([
            'Regular withdrawal request',
            'VIP customer request',
            'Urgent withdrawal needed',
            'First withdrawal request',
            'Monthly salary withdrawal'
        ]) if random.choice([True, False]) else ''
    )
    
    rejection_reason = factory.LazyAttribute(
        lambda x: random.choice([
            'Insufficient balance',
            'KYC verification required',
            'Invalid account details',
            'Suspicious activity detected',
            'Daily limit exceeded'
        ]) if x.status == 'rejected' else None
    )
    
    metadata = factory.LazyFunction(
        lambda: {
            'ip_address': f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
            'user_agent': random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Mozilla/5.0 (Android; Mobile; rv:91.0) Gecko/91.0 Firefox/91.0'
            ]),
            'device_type': random.choice(['mobile', 'desktop', 'tablet']),
            'app_version': f"1.{random.randint(0, 5)}.{random.randint(0, 20)}"
        }
    )
    
    @classmethod
    def create_pending_request(cls, **kwargs):
        """Create pending withdrawal request"""
        return cls.create(
            status='pending',
            approved_at=None,
            completed_at=None,
            **kwargs
        )
    
    @classmethod
    def create_completed_request(cls, **kwargs):
        """Create completed withdrawal request"""
        return cls.create(
            status='completed',
            approved_at=timezone.now() - timedelta(hours=2),
            completed_at=timezone.now() - timedelta(hours=1),
            **kwargs
        )
    
    @classmethod
    def create_rejected_request(cls, **kwargs):
        """Create rejected withdrawal request"""
        return cls.create(
            status='rejected',
            rejection_reason=kwargs.get('rejection_reason', 'Insufficient balance'),
            **kwargs
        )
    
    @classmethod
    def create_high_amount_request(cls, **kwargs):
        """Create high amount withdrawal request"""
        return cls.create(
            amount=Decimal('10000.00'),
            payment_method='bank',
            **kwargs
        )


class WalletHistoryFactory(DjangoModelFactory):
    """Factory for creating WalletHistory instances"""
    
    class Meta:
        model = 'wallet.WalletHistory'
    
    wallet = SubFactory(WalletFactory)
    
    # Snapshot details
    snapshot_date = factory.LazyFunction(
        lambda: timezone.now() - timedelta(days=random.randint(0, 365))
    )
    
    # Balance snapshot
    opening_balance = LazyAttribute(lambda x: Decimal(str(round(random.uniform(0, 5000), 2))))
    closing_balance = LazyAttribute(lambda x: x.opening_balance + Decimal(str(round(random.uniform(-500, 1000), 2))))
    
    # Transaction summary
    total_credits = LazyAttribute(lambda x: Decimal(str(round(random.uniform(0, 2000), 2))))
    total_debits = LazyAttribute(lambda x: Decimal(str(round(random.uniform(0, 1000), 2))))
    transaction_count = LazyAttribute(lambda x: random.randint(0, 50))
    
    # Statistics
    highest_balance = LazyAttribute(lambda x: max(x.opening_balance, x.closing_balance))
    lowest_balance = LazyAttribute(lambda x: min(x.opening_balance, x.closing_balance))
    average_balance = LazyAttribute(
        lambda x: (x.opening_balance + x.closing_balance) / Decimal('2')
    )
    
    # Metadata
    notes = factory.LazyFunction(
        lambda: random.choice([
            'Daily wallet snapshot',
            'End of month summary',
            'Weekly report',
            'Special bonus day'
        ]) if random.choice([True, False]) else ''
    )
    
    metadata = factory.LazyFunction(
        lambda: {
            'day_of_week': random.choice(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']),
            'is_weekend': random.choice([True, False]),
            'special_event': random.choice(['None', 'Festival', 'Holiday', 'Bonus Day', 'Promotion'])
        }
    )
    
    @classmethod
    def create_daily_snapshot(cls, wallet, date=None, **kwargs):
        """Create daily wallet snapshot"""
        if date is None:
            date = timezone.now() - timedelta(days=1)
        
        return cls.create(
            wallet=wallet,
            snapshot_date=date,
            **kwargs
        )
    
    @classmethod
    def create_monthly_summary(cls, wallet, year, month, **kwargs):
        """Create monthly wallet summary"""
        from datetime import date
        snapshot_date = date(year, month, 1)
        
        return cls.create(
            wallet=wallet,
            snapshot_date=snapshot_date,
            notes=f"Monthly summary for {year}-{month:02d}",
            **kwargs
        )