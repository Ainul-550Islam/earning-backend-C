# Create migration script: migrate_to_wallet.py

from django.core.management.base import BaseCommand
from api.models import User
from wallet.models import Wallet
from wallet.services import WalletService

class Command(BaseCommand):
    help = 'Migrate coin_balance to wallet system'
    
    def handle(self, *args, **options):
        users = User.objects.all()
        
        for user in users:
            # Create wallet if doesn't exist
            wallet, created = Wallet.objects.get_or_create(user=user)
            
            if created and user.coin_balance > 0:
                # Transfer old balance
                wallet.current_balance = user.coin_balance
                wallet.total_earned = user.total_earned or user.coin_balance
                wallet.save()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Migrated {user.username}: {user.coin_balance} coins'
                    )
                )
        
        self.stdout.write(self.style.SUCCESS('Migration complete!'))