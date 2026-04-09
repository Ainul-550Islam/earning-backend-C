# api/djoyalty/management/commands/recalculate_balances.py
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Recalculate LoyaltyPoints balance from ledger (audit tool)'

    def handle(self, *args, **options):
        from django.db.models import Sum, Q
        from djoyalty.models.points import LoyaltyPoints, PointsLedger
        count = 0
        for lp in LoyaltyPoints.objects.all():
            credit = PointsLedger.objects.filter(customer=lp.customer, txn_type='credit').aggregate(t=Sum('points'))['t'] or 0
            debit = PointsLedger.objects.filter(customer=lp.customer, txn_type='debit').aggregate(t=Sum('points'))['t'] or 0
            new_balance = credit - debit
            if lp.balance != new_balance:
                self.stdout.write(f'  Fixed {lp.customer}: {lp.balance} → {new_balance}')
                lp.balance = new_balance
                lp.save(update_fields=['balance', 'updated_at'])
                count += 1
        self.stdout.write(self.style.SUCCESS(f'Recalculated {count} balances.'))
