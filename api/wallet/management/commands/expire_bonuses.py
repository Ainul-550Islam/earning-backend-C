# python manage.py expire_bonuses
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Expire unclaimed bonus balances"

    def handle(self, *args, **options):
        from api.wallet.services.core.BalanceService import BalanceService
        count = BalanceService.expire_bonuses()
        self.stdout.write(self.style.SUCCESS(f"Expired {count} bonus records"))
