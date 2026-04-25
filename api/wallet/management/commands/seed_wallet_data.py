# python manage.py seed_wallet_data  (dev/staging only)
from django.core.management.base import BaseCommand
from decimal import Decimal

class Command(BaseCommand):
    help = "Seed test wallet data (dev/staging only)"

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=10, help="Number of users to seed")

    def handle(self, *args, **options):
        from django.conf import settings
        if not settings.DEBUG:
            self.stderr.write(self.style.ERROR("This command only runs in DEBUG mode!"))
            return

        from django.contrib.auth import get_user_model
        from api.wallet.models.core import Wallet
        from api.wallet.services.core.WalletService import WalletService

        User = get_user_model()
        count = options["users"]
        self.stdout.write(f"Seeding {count} test users with wallets...")

        created = 0
        for i in range(count):
            user, new = User.objects.get_or_create(
                username=f"testuser_{i}",
                defaults={"email": f"test{i}@example.com", "is_active": True}
            )
            if new:
                user.set_password("testpass123")
                user.save()

            wallet = WalletService.get_or_create(user)
            WalletService.admin_credit(wallet, Decimal("1000"), f"Seed credit #{i}", None)
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created} wallets with 1000 BDT each"))
