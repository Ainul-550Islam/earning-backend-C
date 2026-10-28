# api/djoyalty/management/commands/recalculate_balances.py
from django.core.management.base import BaseCommand
from decimal import Decimal


class Command(BaseCommand):
    help = 'Audit tool: recalculate LoyaltyPoints.balance from PointsLedger for all customers.'

    def add_arguments(self, parser):
        parser.add_argument('--customer-id', type=int, help='Recalculate for a single customer.')
        parser.add_argument('--fix', action='store_true', help='Apply corrections (default: audit only).')
        parser.add_argument('--tolerance', type=float, default=0.01, help='Acceptable balance discrepancy.')

    def handle(self, *args, **options):
        from djoyalty.models.core import Customer
        from djoyalty.models.points import LoyaltyPoints, PointsLedger
        from django.db.models import Sum, Q

        fix = options['fix']
        tolerance = Decimal(str(options['tolerance']))
        customer_id = options.get('customer_id')

        if fix:
            self.stdout.write(self.style.WARNING('FIX MODE: Corrections will be applied.'))
        else:
            self.stdout.write('AUDIT MODE: No changes will be made. Use --fix to apply corrections.')

        qs = Customer.objects.filter(is_active=True)
        if customer_id:
            qs = qs.filter(id=customer_id)

        mismatches = 0
        checked = 0

        for customer in qs.iterator(chunk_size=200):
            lp = LoyaltyPoints.objects.filter(customer=customer).first()
            if not lp:
                continue

            # Calculate expected balance from ledger
            credits = PointsLedger.objects.filter(
                customer=customer, txn_type='credit', is_reversed=False
            ).aggregate(s=Sum('points'))['s'] or Decimal('0')
            debits = PointsLedger.objects.filter(
                customer=customer, txn_type='debit', is_reversed=False
            ).aggregate(s=Sum('points'))['s'] or Decimal('0')
            expected_balance = credits - debits

            diff = abs(lp.balance - expected_balance)
            checked += 1

            if diff > tolerance:
                mismatches += 1
                self.stdout.write(self.style.ERROR(
                    f'MISMATCH: {customer.code} | stored={lp.balance} | calculated={expected_balance} | diff={diff}'
                ))
                if fix:
                    lp.balance = max(expected_balance, Decimal('0'))
                    lp.save(update_fields=['balance', 'updated_at'])
                    self.stdout.write(self.style.SUCCESS(f'  FIXED: {customer.code} -> {lp.balance}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nAudit complete. Checked={checked}, Mismatches={mismatches}, Fixed={mismatches if fix else 0}'
        ))
