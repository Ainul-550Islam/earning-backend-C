"""
api/ad_networks/management/commands/manage_user_wallets.py
Management command for managing user wallets
SaaS-ready with tenant support
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal

from ad_networks.models import UserWallet, OfferReward

User = get_user_model()


class Command(BaseCommand):
    help = 'Manage user wallets - balance, statistics, and maintenance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['stats', 'create-missing', 'balance-check', 'freeze-inactive', 'unfreeze-all', 'adjust-balance', 'export'],
            required=True,
            help='Action to perform'
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            default='default',
            help='Tenant ID to process (default: all tenants)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform dry run without making changes'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Specific user ID to process'
        )
        parser.add_argument(
            '--amount',
            type=str,
            help='Amount for balance adjustment'
        )
        parser.add_argument(
            '--reason',
            type=str,
            help='Reason for balance adjustment'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Days for inactivity check (default: 30)'
        )
    
    def handle(self, *args, **options):
        action = options['action']
        tenant_id = options['tenant_id']
        dry_run = options['dry_run']
        user_id = options['user_id']
        amount = options['amount']
        reason = options['reason']
        days = options['days']
        
        self.stdout.write(f"=== User Wallets Management ===")
        self.stdout.write(f"Action: {action}")
        self.stdout.write(f"Tenant ID: {tenant_id}")
        self.stdout.write(f"Dry Run: {dry_run}")
        if user_id:
            self.stdout.write(f"User ID: {user_id}")
        self.stdout.write("=" * 40)
        
        if action == 'stats':
            self.show_stats(tenant_id, user_id)
        elif action == 'create-missing':
            self.create_missing_wallets(tenant_id, user_id, dry_run)
        elif action == 'balance-check':
            self.check_balances(tenant_id, user_id)
        elif action == 'freeze-inactive':
            self.freeze_inactive_wallets(tenant_id, days, dry_run)
        elif action == 'unfreeze-all':
            self.unfreeze_all_wallets(tenant_id, dry_run)
        elif action == 'adjust-balance':
            self.adjust_balance(tenant_id, user_id, amount, reason, dry_run)
        elif action == 'export':
            self.export_wallets(tenant_id, user_id)
    
    def show_stats(self, tenant_id, user_id=None):
        """Show wallet statistics"""
        self.stdout.write("Wallet Statistics:")
        self.stdout.write("-" * 30)
        
        queryset = UserWallet.objects.all()
        if tenant_id != 'all':
            queryset = queryset.filter(tenant_id=tenant_id)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Overall stats
        total_wallets = queryset.count()
        total_balance = queryset.aggregate(
            total=models.Sum('current_balance')
        )['total_balance'] or Decimal('0')
        total_earned = queryset.aggregate(
            total=models.Sum('total_earned')
        )['total_earned'] or Decimal('0')
        total_withdrawn = queryset.aggregate(
            total=models.Sum('total_withdrawn')
        )['total_withdrawn'] or Decimal('0')
        total_pending = queryset.aggregate(
            total=models.Sum('pending_balance')
        )['total_pending'] or Decimal('0')
        
        self.stdout.write(f"Total Wallets: {total_wallets}")
        self.stdout.write(f"Total Balance: {self._format_currency(total_balance)}")
        self.stdout.write(f"Total Earned: {self._format_currency(total_earned)}")
        self.stdout.write(f"Total Withdrawn: {self._format_currency(total_withdrawn)}")
        self.stdout.write(f"Total Pending: {self._format_currency(total_pending)}")
        
        # Status breakdown
        active_count = queryset.filter(is_active=True).count()
        frozen_count = queryset.filter(is_frozen=True).count()
        inactive_count = queryset.filter(is_active=False).count()
        
        self.stdout.write(f"\nStatus:")
        self.stdout.write(f"  Active: {active_count}")
        self.stdout.write(f"  Frozen: {frozen_count}")
        self.stdout.write(f"  Inactive: {inactive_count}")
        
        # Currency breakdown
        by_currency = queryset.values('currency').annotate(
            count=models.Count('id'),
            balance=models.Sum('current_balance')
        ).order_by('-balance')
        
        self.stdout.write(f"\nBy Currency:")
        for item in by_currency:
            self.stdout.write(f"  {item['currency']}: {item['count']} wallets, {self._format_currency(item['balance'])}")
        
        # Balance ranges
        balance_ranges = [
            ('Empty', 0, 0),
            ('0-100', 0, 100),
            ('100-1000', 100, 1000),
            ('1000-10000', 1000, 10000),
            ('10000+', 10000, float('inf'))
        ]
        
        self.stdout.write(f"\nBalance Ranges:")
        for range_name, min_val, max_val in balance_ranges:
            if max_val == float('inf'):
                count = queryset.filter(current_balance__gte=min_val).count()
            else:
                count = queryset.filter(current_balance__gte=min_val, current_balance__lt=max_val).count()
            self.stdout.write(f"  {range_name}: {count} wallets")
    
    def create_missing_wallets(self, tenant_id, user_id=None, dry_run=False):
        """Create wallets for users who don't have one"""
        self.stdout.write("Creating missing wallets:")
        self.stdout.write("-" * 30)
        
        # Get users without wallets
        users = User.objects.all()
        if user_id:
            users = users.filter(id=user_id)
        
        # Filter out users who already have wallets
        existing_wallets = UserWallet.objects.all()
        if tenant_id != 'all':
            existing_wallets = existing_wallets.filter(tenant_id=tenant_id)
        
        users_with_wallets = existing_wallets.values_list('user_id', flat=True)
        users_without_wallets = users.exclude(id__in=users_with_wallets)
        
        if users_without_wallets.exists():
            self.stdout.write(f"Found {users_without_wallets.count()} users without wallets")
            
            if dry_run:
                self.stdout.write("DRY RUN - No wallets will be created")
            else:
                with transaction.atomic():
                    for user in users_without_wallets:
                        wallet = UserWallet.objects.create(
                            user=user,
                            tenant_id=tenant_id,
                            current_balance=Decimal('0.00'),
                            total_earned=Decimal('0.00'),
                            total_withdrawn=Decimal('0.00'),
                            pending_balance=Decimal('0.00'),
                            currency='BDT',
                            is_active=True,
                            is_frozen=False,
                            daily_limit=Decimal('5000.00'),
                            monthly_limit=Decimal('100000.00')
                        )
                        self.stdout.write(f"Created wallet for user: {user.username}")
                
                self.stdout.write(f"Created {users_without_wallets.count()} wallets")
        else:
            self.stdout.write("All users have wallets")
    
    def check_balances(self, tenant_id, user_id=None):
        """Check wallet balance integrity"""
        self.stdout.write("Checking wallet balances:")
        self.stdout.write("-" * 30)
        
        queryset = UserWallet.objects.all()
        if tenant_id != 'all':
            queryset = queryset.filter(tenant_id=tenant_id)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        issues = []
        
        for wallet in queryset:
            wallet_issues = []
            
            # Check available balance calculation
            expected_available = wallet.current_balance - wallet.pending_balance
            if expected_available < 0:
                wallet_issues.append("Negative available balance")
            
            # Check if pending balance exceeds total earned
            if wallet.pending_balance > wallet.total_earned:
                wallet_issues.append("Pending balance exceeds total earned")
            
            # Check if withdrawn exceeds earned
            if wallet.total_withdrawn > wallet.total_earned:
                wallet_issues.append("Withdrawn amount exceeds total earned")
            
            # Check if current balance is negative
            if wallet.current_balance < 0:
                wallet_issues.append("Negative current balance")
            
            # Check limits
            if wallet.daily_limit <= 0:
                wallet_issues.append("Invalid daily limit")
            
            if wallet.monthly_limit <= 0:
                wallet_issues.append("Invalid monthly limit")
            
            if wallet_issues:
                issues.append({
                    'wallet': wallet,
                    'issues': wallet_issues
                })
        
        if issues:
            self.stdout.write(f"Found {len(issues)} wallets with balance issues:")
            for item in issues:
                self.stdout.write(f"  User {item['wallet'].user.username}: {', '.join(item['issues'])}")
        else:
            self.stdout.write("All wallet balances are valid")
    
    def freeze_inactive_wallets(self, tenant_id, days, dry_run=False):
        """Freeze wallets for inactive users"""
        self.stdout.write(f"Freezing inactive wallets (inactive for {days} days):")
        self.stdout.write("-" * 30)
        
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        
        queryset = UserWallet.objects.all()
        if tenant_id != 'all':
            queryset = queryset.filter(tenant_id=tenant_id)
        
        # Find wallets for inactive users
        inactive_wallets = []
        for wallet in queryset:
            # Check user's last login
            if wallet.user.last_login:
                if wallet.user.last_login < cutoff_date:
                    inactive_wallets.append(wallet)
            else:
                # If no last login, check when user was created
                if wallet.user.date_joined < cutoff_date:
                    inactive_wallets.append(wallet)
        
        # Exclude already frozen wallets
        inactive_wallets = [w for w in inactive_wallets if not w.is_frozen]
        
        if inactive_wallets:
            self.stdout.write(f"Found {len(inactive_wallets)} inactive wallets to freeze")
            
            if dry_run:
                self.stdout.write("DRY RUN - No wallets will be frozen")
            else:
                with transaction.atomic():
                    for wallet in inactive_wallets:
                        wallet.is_frozen = True
                        wallet.freeze_reason = f"Inactive for {days} days"
                        wallet.frozen_at = timezone.now()
                        wallet.save(update_fields=['is_frozen', 'freeze_reason', 'frozen_at'])
                        self.stdout.write(f"Frozen wallet for user: {wallet.user.username}")
                
                self.stdout.write(f"Frozen {len(inactive_wallets)} inactive wallets")
        else:
            self.stdout.write("No inactive wallets found")
    
    def unfreeze_all_wallets(self, tenant_id, dry_run=False):
        """Unfreeze all frozen wallets"""
        self.stdout.write("Unfreezing all frozen wallets:")
        self.stdout.write("-" * 30)
        
        queryset = UserWallet.objects.filter(is_frozen=True)
        if tenant_id != 'all':
            queryset = queryset.filter(tenant_id=tenant_id)
        
        if queryset.exists():
            self.stdout.write(f"Found {queryset.count()} frozen wallets to unfreeze")
            
            if dry_run:
                self.stdout.write("DRY RUN - No wallets will be unfrozen")
            else:
                with transaction.atomic():
                    for wallet in queryset:
                        wallet.is_frozen = False
                        wallet.freeze_reason = None
                        wallet.frozen_at = None
                        wallet.save(update_fields=['is_frozen', 'freeze_reason', 'frozen_at'])
                        self.stdout.write(f"Unfrozen wallet for user: {wallet.user.username}")
                
                self.stdout.write(f"Unfrozen {queryset.count()} wallets")
        else:
            self.stdout.write("No frozen wallets found")
    
    def adjust_balance(self, tenant_id, user_id, amount, reason, dry_run=False):
        """Adjust wallet balance"""
        if not amount:
            self.stdout.write("Error: Amount is required")
            return
        
        if not user_id:
            self.stdout.write("Error: User ID is required")
            return
        
        try:
            amount = Decimal(amount)
        except:
            self.stdout.write("Error: Invalid amount format")
            return
        
        try:
            wallet = UserWallet.objects.get(user_id=user_id, tenant_id=tenant_id)
        except UserWallet.DoesNotExist:
            self.stdout.write("Error: Wallet not found")
            return
        
        self.stdout.write(f"Adjusting balance for user {wallet.user.username}:")
        self.stdout.write(f"Current balance: {self._format_currency(wallet.current_balance)}")
        self.stdout.write(f"Adjustment: {self._format_currency(amount)}")
        self.stdout.write(f"New balance: {self._format_currency(wallet.current_balance + amount)}")
        
        if reason:
            self.stdout.write(f"Reason: {reason}")
        
        if dry_run:
            self.stdout.write("DRY RUN - No balance will be adjusted")
        else:
            with transaction.atomic():
                wallet.current_balance += amount
                if amount > 0:
                    wallet.total_earned += amount
                wallet.save(update_fields=['current_balance', 'total_earned'])
                self.stdout.write("Balance adjusted successfully")
    
    def export_wallets(self, tenant_id, user_id=None):
        """Export wallet data"""
        import csv
        from django.http import HttpResponse
        
        queryset = UserWallet.objects.all()
        if tenant_id != 'all':
            queryset = queryset.filter(tenant_id=tenant_id)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Create CSV content
        output = []
        output.append(['User ID', 'Username', 'Email', 'Current Balance', 'Total Earned', 
                     'Total Withdrawn', 'Pending Balance', 'Currency', 'Status', 
                     'Is Frozen', 'Daily Limit', 'Monthly Limit', 'Created At'])
        
        for wallet in queryset:
            output.append([
                wallet.user.id,
                wallet.user.username,
                wallet.user.email,
                str(wallet.current_balance),
                str(wallet.total_earned),
                str(wallet.total_withdrawn),
                str(wallet.pending_balance),
                wallet.currency,
                'Active' if wallet.is_active else 'Inactive',
                'Yes' if wallet.is_frozen else 'No',
                str(wallet.daily_limit),
                str(wallet.monthly_limit),
                wallet.created_at.isoformat()
            ])
        
        # Write to file
        filename = f"wallets_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(output)
        
        self.stdout.write(f"Exported {queryset.count()} wallets to {filename}")
    
    def _format_currency(self, amount):
        """Format currency amount"""
        return f"BDT {amount:,.2f}"


# Add required imports
from django.db import models
